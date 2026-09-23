#!/usr/bin/env python3
"""Gap 5: score the preregistered extended reserved window (plan-extended.json) exactly once.

Uses the unchanged research-evaluation evaluate.py functions (verify_inputs, check_auxiliary,
validate_panel, label, choose, summaries, write_new) imported from the file itself. evaluate.py's
main() is hard-wired to plan.json and its 2014-2021 session counts, so this driver supplies only the
new window, the reserved-only selection and the predeclared significance tests.
"""
import argparse
import csv
import datetime as dt
from decimal import Decimal
import importlib.metadata
import io
import json
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan-extended.json"
PLAN_SHA256 = "a2f698706bb8809f91facf48fc8028c3a374ff4fb9db9edb7b48c5a0d662e38d"
PRE_SESSIONS, RESERVED_SESSIONS = 385, 250


def load_panel(ev, root, plan):
    panel, auxiliary = {}, {}
    for asset in plan["assets"]:
        stem = "Data/equity/usa/"
        with zipfile.ZipFile(root / (stem + "daily/" + asset.lower() + ".zip")) as z:
            records = list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode("utf-8"))))
        rows = []
        for r in records:
            date = dt.datetime.strptime(r[0], "%Y%m%d %H:%M").date().isoformat()
            if not plan["data_start"] <= date <= plan["reserved_end"]:
                continue
            op, hi, lo, close = [Decimal(x) / 10000 for x in r[1:5]]
            if not all(x.is_finite() for x in [op, hi, lo, close]) or not 0 < lo <= min(op, close) <= max(op, close) <= hi:
                raise ValueError("invalid OHLC")
            rows.append({"date": date, "open": op, "close": close})
        panel[asset] = rows
        auxiliary[asset] = ev.check_auxiliary(
            (root / (stem + "factor_files/" + asset.lower() + ".csv")).read_text(),
            (root / (stem + "map_files/" + asset.lower() + ".csv")).read_text(),
            plan["data_start"], plan["reserved_end"], asset)
    dates = ev.validate_panel(panel)
    pre = sum(d < plan["reserved_start"] for d in dates)
    res = sum(plan["reserved_start"] <= d <= plan["reserved_end"] for d in dates)
    if (pre, res) != (PRE_SESSIONS, RESERVED_SESSIONS):
        raise ValueError(f"session counts changed: {pre}, {res}")
    return panel, dates, auxiliary


def holm(pvalues):
    order = sorted(pvalues, key=pvalues.get)
    adjusted, running = {}, 0.0
    for rank, key in enumerate(order):
        running = max(running, min(1.0, (len(order) - rank) * pvalues[key]))
        adjusted[key] = running
    return adjusted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--harness-test-plan", type=Path,
                        help="Dry-run the harness on an already-inspected development window instead of the frozen plan")
    args = parser.parse_args()
    global PLAN, PLAN_SHA256, PRE_SESSIONS, RESERVED_SESSIONS
    if importlib.metadata.version("skfolio") != "1.2.9":
        raise SystemExit("use the accepted skfolio environment")
    if args.harness_test_plan:
        test = json.loads(args.harness_test_plan.read_text())
        PLAN, PLAN_SHA256 = args.harness_test_plan, common.digest(args.harness_test_plan)
        PRE_SESSIONS, RESERVED_SESSIONS = test["harness_test_counts"]
    if common.digest(PLAN) != PLAN_SHA256:
        raise SystemExit("plan-extended.json is not the frozen file")
    out = args.out.resolve()
    if out.exists():
        raise SystemExit("refusing an existing output directory: the window is scored exactly once")
    os.umask(0o077)
    out.mkdir(parents=True, mode=0o700)
    ev = common.load_evaluate()
    plan = json.loads(PLAN.read_text())
    root = common.LEAN_DEFAULT.resolve()
    inputs = ev.verify_inputs(root, plan["inputs"])
    ev.write_new(out / "freeze.json", {"frozen_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "plan": plan,
                 "plan_sha256": PLAN_SHA256, "inputs": inputs, "evaluate_sha256": common.digest(common.EVAL_DIR / "evaluate.py"),
                 "driver_sha256": common.digest(__file__), "common_sha256": common.digest(HERE / "common.py")})
    panel, dates, auxiliary = load_panel(ev, root, plan)
    reserved = [i for i, d in enumerate(dates) if plan["reserved_start"] <= d <= plan["reserved_end"]]
    anchor = reserved[0]
    train = list(range(anchor - 6 - 252, anchor - 6))
    if train[0] < max(plan["lookbacks"]):
        raise ValueError("insufficient warm-up")

    def episodes(indices):
        return [i for i in indices if (i - anchor) % 5 == 0]
    cost = Decimal(plan["round_trip_cost_fraction"])
    candidates = plan["candidates"]
    cutoff = dates[anchor]
    training_panel = {s: rows[:anchor] for s, rows in panel.items()}
    training = [ev.label(training_panel, i, c, cost) for i in episodes(train) for c in candidates]
    if any(r["status"] != "observed" for r in training):
        raise ValueError("incomplete training label")
    selection = ev.choose(training, plan["selection_candidates"], cutoff)
    selection.update({"id": "reserved-extended", "plan_sha256": PLAN_SHA256, "train_first": dates[train[0]],
                      "train_last": dates[train[-1]], "test_first": cutoff, "test_last": dates[reserved[-1]],
                      "train_sessions": len(train), "test_sessions": len(reserved)})
    ev.write_new(out / "reserved-extended.selection.json", selection)
    # Reserved labels are materialized only after the immutable selection is persisted.
    evaluation = [ev.label(panel, i, c, cost) for i in episodes(reserved) for c in candidates]
    summary = ev.summaries(evaluation, candidates)
    if min(v["observed_episodes"] for v in summary.values()) < plan["minimum_completed_episodes_per_candidate"]:
        raise ValueError("fewer than the preregistered minimum completed episodes")
    ev.write_new(out / "candidate-ledger.json", [dict(r, phase="train") for r in training] + [dict(r, phase="reserved") for r in evaluation])

    from scipy import stats
    observed = {c: {r["decision"]: float(Decimal(r["net_proxy"])) for r in evaluation if r["candidate"] == c and r["status"] == "observed"}
                for c in candidates}
    chosen = selection["chosen"]
    common_days = sorted(set(observed[chosen]) & set(observed["equalweight"]))
    diffs = [observed[chosen][d] - observed["equalweight"][d] for d in common_days]
    t = stats.ttest_1samp(diffs, 0.0)
    try:
        w = stats.wilcoxon(diffs, zero_method="wilcox")
        wilcoxon = {"statistic": float(w.statistic), "pvalue": float(w.pvalue)}
    except ValueError as exc:
        wilcoxon = {"error": str(exc)}
    invested = [c for c in candidates if c != "cash"]
    per = {}
    for c in invested:
        values = list(observed[c].values())
        r = stats.ttest_1samp(values, 0.0)
        per[c] = {"n": len(values), "mean_net_proxy": sum(values) / len(values), "t": float(r.statistic), "pvalue": float(r.pvalue)}
    adjusted = holm({c: per[c]["pvalue"] for c in invested})
    for c in invested:
        per[c]["holm_pvalue"] = adjusted[c]
    result = {"kind": "extended-reserved-raw-price-label-study", "plan_sha256": PLAN_SHA256,
              "freeze_sha256": common.digest(out / "freeze.json"), "auxiliary": auxiliary,
              "selection": selection, "selection_sha256": common.digest(out / "reserved-extended.selection.json"),
              "reserved_candidates": summary, "ledger_sha256": common.digest(out / "candidate-ledger.json"),
              "primary_test": {"test": "two-sided one-sample t-test on paired net_proxy(selected) - net_proxy(equalweight)",
                               "selected": chosen, "n_pairs": len(diffs), "mean_difference": sum(diffs) / len(diffs),
                               "t": float(t.statistic), "pvalue": float(t.pvalue), "alpha": 0.05,
                               "reject_null_at_alpha": bool(t.pvalue < 0.05)},
              "secondary_wilcoxon": wilcoxon, "secondary_per_candidate_vs_zero": per,
              "consequence": plan["significance_test"]["consequence"],
              "versions": {p: importlib.metadata.version(p) for p in ["skfolio", "scipy", "numpy", "pandas"]},
              "inputs_unchanged": ev.verify_inputs(root, plan["inputs"]) == inputs, "no_pnl_or_execution_claim": True}
    ev.write_new(out / "results.json", result)
    print(json.dumps({"selected": chosen, "reserved_candidates": summary, "primary_test": result["primary_test"],
                      "secondary_wilcoxon": wilcoxon, "per_candidate": per, "inputs_unchanged": result["inputs_unchanged"]}, indent=1))


if __name__ == "__main__":
    main()
