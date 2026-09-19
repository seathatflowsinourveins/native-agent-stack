#!/usr/bin/env python3
"""Chronological raw-price label controls. This is not an execution/P&L simulator."""
import argparse
import csv
import datetime as dt
from decimal import Decimal
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def verify_inputs(root, expected):
    result = {}
    for name, sha in expected.items():
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()) or digest(path) != sha:
            raise ValueError("input hash mismatch: " + name)
        result[name] = {"sha256": sha, "bytes": path.stat().st_size}
    return result


def validate_panel(panel):
    if not panel:
        raise ValueError("empty panel")
    expected = None
    for asset, rows in panel.items():
        dates = [r["date"] for r in rows]
        if not dates or dates != sorted(set(dates)):
            raise ValueError("duplicate or unsorted calendar: " + asset)
        if expected is not None and expected != dates:
            raise ValueError("asset calendar mismatch: " + asset)
        expected = dates
        for r in rows:
            dt.date.fromisoformat(r["date"])
            if any(not r[k].is_finite() or r[k] <= 0 for k in ["open", "close"]):
                raise ValueError("nonfinite or nonpositive price")
    return expected


def check_auxiliary(factors, mapping, start, end, asset):
    # LEAN factor/map rows apply up to their date (inclusive), not forward from it.
    start, end = start.replace("-", ""), end.replace("-", "")
    def covering(text):
        rows = list(csv.reader(io.StringIO(text)))
        dates = [r[0] for r in rows]
        if dates != sorted(set(dates)) or dates[-1] < end:
            raise ValueError("incomplete or unsorted auxiliary dates")
        result, prior = [], "00000000"
        for row in rows:
            if prior < end and row[0] >= start:
                result.append(row)
            prior = row[0]
        return result
    fs, ms = covering(factors), covering(mapping)
    splits = {Decimal(r[2]) for r in fs}
    if len(splits) != 1 or any(not x.is_finite() or x <= 0 for x in splits):
        raise ValueError("split factor transition in raw-price study")
    if {r[1].upper() for r in ms} != {asset}:
        raise ValueError("ticker mapping transition")
    return {"covering_factor_rows": len(fs), "split_factors": [str(x) for x in sorted(splits)],
            "covering_map_rows": len(ms), "price_factor_values": len({r[1] for r in fs})}


def load_panel(root, plan):
    panel, auxiliary = {}, {}
    for asset in plan["assets"]:
        stem = "Data/equity/usa/"
        with zipfile.ZipFile(root / (stem + "daily/" + asset.lower() + ".zip")) as z:
            if len(z.namelist()) != 1:
                raise ValueError("expected one daily member")
            records = list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))))
        rows = []
        for r in records:
            if len(r) != 6:
                raise ValueError("unexpected daily schema")
            date = dt.datetime.strptime(r[0], "%Y%m%d %H:%M").date().isoformat()
            if not plan["data_start"] <= date <= plan["reserved_end"]:
                continue
            op, hi, lo, close = [Decimal(x) / 10000 for x in r[1:5]]
            if not all(x.is_finite() for x in [op, hi, lo, close]) or not 0 < lo <= min(op, close) <= max(op, close) <= hi:
                raise ValueError("invalid OHLC")
            if int(r[5]) < 0:
                raise ValueError("negative volume")
            rows.append({"date": date, "open": op, "close": close})
        panel[asset] = rows
        auxiliary[asset] = check_auxiliary(
            (root / (stem + "factor_files/" + asset.lower() + ".csv")).read_text(),
            (root / (stem + "map_files/" + asset.lower() + ".csv")).read_text(),
            plan["data_start"], plan["reserved_end"], asset)
    dates = validate_panel(panel)
    expected = {"2014": 252, "2015": 252, "2016": 252, "2017": 251, "2018": 251, "2019": 252, "2020": 253, "2021": 61}
    counts = {y: sum(d.startswith(y) for d in dates) for y in expected}
    if counts != expected:
        raise ValueError("pinned sample session counts changed")
    return panel, dates, auxiliary, counts


def weights(panel, t, candidate):
    if candidate == "cash":
        return {}
    if candidate == "equalweight":
        names = sorted(panel)
        result = {s: Decimal(1)/len(names) for s in names[:-1]}
        result[names[-1]] = Decimal(1)-sum(result.values())
        return result
    if candidate not in {"momentum20", "momentum60", "momentum120"}:
        raise ValueError("unknown candidate")
    lookback = int(candidate.removeprefix("momentum"))
    if t < lookback:
        raise ValueError("insufficient warmup")
    scores = {s: rows[t]["close"]/rows[t-lookback]["close"]-1 for s, rows in panel.items()}
    best = min(scores, key=lambda s: (-scores[s], s))
    return {best: Decimal(1)} if scores[best] > 0 else {}


def label(panel, t, candidate, cost):
    dates = next(iter(panel.values()))
    w = weights(panel, t, candidate)
    result = {"candidate": candidate, "decision": dates[t]["date"],
              "weights": {k: str(v) for k, v in w.items()}}
    if t+6 >= len(dates):
        return dict(result, status="censored", reason="exit beyond evaluation boundary")
    gross = sum((v*(panel[s][t+6]["open"]/panel[s][t+1]["open"]-1) for s, v in w.items()), Decimal(0))
    charge = cost * sum(w.values(), Decimal(0))
    return dict(result, status="observed", entry=dates[t+1]["date"], exit=dates[t+6]["date"],
                gross_price_label=str(gross), cost_proxy=str(charge), net_proxy=str(gross-charge))


def choose(rows, candidates, cutoff):
    if any(r["decision"] >= cutoff or r["exit"] >= cutoff for r in rows):
        raise ValueError("training label overlap with evaluation decision")
    grouped = {c: [Decimal(r["net_proxy"]) for r in rows if r["candidate"] == c] for c in candidates}
    if any(not x for x in grouped.values()) or len({len(x) for x in grouped.values()}) != 1:
        raise ValueError("empty or unequal training candidate counts")
    if any(not x.is_finite() for values in grouped.values() for x in values):
        raise ValueError("nonfinite training label")
    means = {c: sum(x)/len(x) for c, x in grouped.items()}
    chosen = max(candidates, key=lambda c: means[c])
    return {"chosen": chosen, "training_episode_count": len(grouped[chosen]),
            "scores": {c: str(v) for c, v in means.items()}, "evaluation_cutoff": cutoff,
            "latest_training_exit": max(r["exit"] for r in rows)}


def summaries(rows, candidates):
    result = {}
    for c in candidates:
        selected = [r for r in rows if r["candidate"] == c]
        observed = [r for r in selected if r["status"] == "observed"]
        if not observed:
            raise ValueError("no complete evaluation episodes")
        result[c] = {"observed_episodes": len(observed), "censored_episodes": len(selected)-len(observed),
                     "invested_episodes": sum(bool(r["weights"]) for r in observed),
                     "mean_raw_price_label": str(sum(Decimal(r["gross_price_label"]) for r in observed)/len(observed)),
                     "mean_net_cost_proxy_label": str(sum(Decimal(r["net_proxy"]) for r in observed)/len(observed))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    import pandas as pd
    from skfolio.model_selection import WalkForward
    if importlib.metadata.version("skfolio") != "1.2.9":
        raise ValueError("use the accepted skfolio version")
    root, out = args.lean_source.resolve(), args.out.resolve()
    if out.exists() or out.is_relative_to(root) or out.is_relative_to(Path(sys.prefix)):
        raise ValueError("use a fresh private output directory outside engine/environment")
    os.umask(0o077)
    out.mkdir(parents=True, mode=0o700)
    plan = json.loads((HERE/"plan.json").read_text())
    input_receipt = verify_inputs(root, plan["inputs"])
    # The freeze exists before parsing or scoring any price values.
    write_new(out/"freeze.json", {"frozen_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "plan": plan, "plan_sha256": digest(HERE/"plan.json"), "inputs": input_receipt,
        "source_sha256": digest(HERE/"evaluate.py"), "lock_sha256": digest(HERE/"requirements.lock")})
    panel, dates, auxiliary, counts = load_panel(root, plan)
    eligible = [i for i, d in enumerate(dates) if plan["eligible_start"] <= d <= plan["development_end"]]
    reserved = [i for i, d in enumerate(dates) if plan["reserved_start"] <= d <= plan["reserved_end"]]
    if min(eligible) < max(plan["lookbacks"]) or len(reserved) != 61:
        raise ValueError("warmup or reserved interval mismatch")
    anchor = eligible[0]
    def episodes(indices):
        return [int(i) for i in indices if (i-anchor) % 5 == 0]
    def prefix(cutoff):
        size = next((i for i, d in enumerate(dates) if d >= cutoff), len(dates))
        return {s: rows[:size] for s, rows in panel.items()}
    cost = Decimal(plan["round_trip_cost_fraction"])
    candidates = plan["candidates"]
    frame = pd.DataFrame({"session": [dates[i] for i in eligible]}, index=pd.to_datetime([dates[i] for i in eligible]))
    spec = plan["splitter"]
    splitter = WalkForward(**{k: spec[k] for k in ["train_size", "test_size", "purged_size", "reduce_test"]})
    folds, all_rows = [], []
    def evaluate_fold(name, train, test, eval_panel):
        cutoff = dates[int(test[0])]
        training_panel = prefix(cutoff)
        training = [label(training_panel, i, c, cost) for i in episodes(train) for c in candidates]
        if any(r["status"] != "observed" for r in training):
            raise ValueError("incomplete training label")
        selection = choose(training, plan["selection_candidates"], cutoff)
        selection.update({"id": name, "plan_sha256": digest(HERE/"plan.json"),
            "train_first": dates[int(train[0])], "train_last": dates[int(train[-1])],
            "test_first": cutoff, "test_last": dates[int(test[-1])], "train_sessions": len(train), "test_sessions": len(test)})
        write_new(out/(name+".selection.json"), selection)
        # Evaluation labels are materialized only after immutable selection is persisted.
        evaluation = [label(eval_panel, i, c, cost) for i in episodes(test) for c in candidates]
        for phase, records in [("train", training), ("evaluation", evaluation)]:
            all_rows.extend(dict(r, fold=name, phase=phase) for r in records)
        summary = summaries(evaluation, candidates)
        selected = summary[selection["chosen"]]
        return dict(selection, selection_sha256=digest(out/(name+".selection.json")), all_candidates=summary, selected=selected)
    development_panel = prefix(plan["reserved_start"])
    for j, (train, test) in enumerate(splitter.split(frame)):
        folds.append(evaluate_fold("development-"+str(j+1), [eligible[int(i)] for i in train], [eligible[int(i)] for i in test], development_panel))
    reserved_train = eligible[-(252+6):-6]
    heldout = evaluate_fold("reserved-2021q1", reserved_train, reserved, panel)
    write_new(out/"candidate-ledger.json", all_rows)
    unchanged = verify_inputs(root, plan["inputs"]) == input_receipt
    result = {"kind": "raw-price-label-study", "plan_sha256": digest(HERE/"plan.json"), "freeze_sha256": digest(out/"freeze.json"),
        "versions": {p: importlib.metadata.version(p) for p in ["skfolio", "pandas", "numpy", "scikit-learn"]},
        "session_counts": counts, "assets": plan["assets"], "auxiliary": auxiliary,
        "development_folds": folds, "reserved": heldout, "ledger_records": len(all_rows),
        "inputs_unchanged": unchanged, "ledger_sha256": digest(out/"candidate-ledger.json"),
        "no_pnl_or_execution_claim": True}
    write_new(out/"results.json", result)
    print(json.dumps({"folds": len(folds), "ledger_records": len(all_rows), "reserved_selection": heldout["chosen"],
        "reserved_candidates": heldout["all_candidates"], "inputs_unchanged": unchanged}, indent=2))


if __name__ == "__main__":
    main()
