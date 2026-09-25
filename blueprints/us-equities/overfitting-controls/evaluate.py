#!/usr/bin/env python3
"""Deflated Sharpe ratio and CSCV PBO over the retained research-evaluation ledger.

Offline: reads only the hash-pinned ledger, the research-evaluation receipt and
params.json. Prints deterministic results JSON (no timestamps) to stdout.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def _library():
    spec = importlib.util.spec_from_file_location("overfitting_controls", HERE / "overfitting.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


of = _library()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pointer(document, path):
    node = document
    for token in path.strip("/").split("/"):
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def load_inputs(root, params):
    src = params["source"]
    ledger_path, receipt_path = root / src["ledger_path"], root / src["research_receipt_path"]
    if sha256(ledger_path) != src["ledger_sha256"]:
        raise ValueError("ledger hash mismatch")
    receipt = json.loads(receipt_path.read_text())
    if pointer(receipt, src["research_receipt_ledger_pointer"]) != src["ledger_sha256"]:
        raise ValueError("research receipt does not name this ledger")
    ledger = json.loads(ledger_path.read_text())
    if len(ledger) != src["ledger_records"]:
        raise ValueError("ledger record count mismatch")
    return ledger, receipt


def episode_values(ledger, development_end):
    """One net_proxy per (candidate, decision) in the development segment; conflicts are errors."""
    values = {}
    for row in ledger:
        if row["status"] != "observed" or row["decision"] > development_end:
            continue
        key = (row["candidate"], row["decision"])
        value = Decimal(row["net_proxy"])
        if key in values and values[key] != value:
            raise ValueError("conflicting duplicate episode label: %s %s" % key)
        values[key] = value
    return values


def aligned_matrix(values, trials):
    dates = sorted({d for (c, d) in values if c in trials})
    missing = [(c, d) for c in trials for d in dates if (c, d) not in values]
    if missing or not dates:
        raise ValueError("trial series are not aligned")
    return dates, [[float(values[(c, d)]) for c in trials] for d in dates]


def dsr_block(trials, matrix):
    columns = list(zip(*matrix))
    per_trial = {}
    for name, column in zip(trials, columns):
        m = of.moments(column)
        per_trial[name] = dict(m, sharpe=of.sharpe_from(m["mean"], m["std"]))
    srs = [per_trial[t]["sharpe"] for t in trials]
    best = max(range(len(trials)), key=lambda i: (srs[i], -i))
    selected = per_trial[trials[best]]
    mean_sr = math.fsum(srs) / len(srs)
    variance = math.fsum((s - mean_sr) ** 2 for s in srs) / (len(srs) - 1)
    dsr, sr0 = of.deflated_sharpe(selected["sharpe"], selected["n"], selected["skew"],
                                  selected["kurtosis"], len(trials), variance)
    psr0 = of.probabilistic_sharpe(selected["sharpe"], selected["n"], selected["skew"], selected["kurtosis"], 0.0)
    return {"trials": list(trials), "observations": len(matrix), "per_trial": per_trial,
            "selected_trial": trials[best], "selected_sharpe": selected["sharpe"],
            "trial_sharpe_variance_ddof1": variance, "expected_max_sharpe_sr0": sr0,
            "psr_vs_zero": psr0, "dsr": dsr}


def pbo_block(matrix, partitions, metric):
    result = of.cscv_pbo(matrix, partitions, metric)
    logits = result.pop("logits")
    histogram = {}
    for x in logits:
        key = "%.6f" % x
        histogram[key] = histogram.get(key, 0) + 1
    result["lambda_histogram"] = dict(sorted(histogram.items(), key=lambda kv: float(kv[0])))
    return result


def walk_forward_block(ledger, receipt):
    folds = receipt["results"]["development_folds"]
    chosen = {f["id"]: f["chosen"] for f in folds}
    series = sorted((r["decision"], float(Decimal(r["net_proxy"])), r["fold"])
                    for r in ledger if r["phase"] == "evaluation" and r["status"] == "observed"
                    and r["fold"] in chosen and r["candidate"] == chosen[r["fold"]])
    decisions = [d for d, _, _ in series]
    if len(set(decisions)) != len(decisions):
        raise ValueError("overlapping walk-forward evaluation episodes")
    values = [v for _, v, _ in series]
    m = of.moments(values)
    sr = of.sharpe_from(m["mean"], m["std"])
    return {"folds": len(chosen), "chosen_counts": {c: list(chosen.values()).count(c) for c in sorted(set(chosen.values()))},
            "observations": len(values), "first_decision": decisions[0], "last_decision": decisions[-1],
            "moments": m, "sharpe": sr, "psr_vs_zero": of.probabilistic_sharpe(sr, m["n"], m["skew"], m["kurtosis"], 0.0)}


def compute(root=ROOT, params_path=HERE / "params.json"):
    params = json.loads(Path(params_path).read_text())
    ledger, receipt = load_inputs(root, params)
    values = episode_values(ledger, params["series"]["development_end"])
    dsr, pbo = {}, {}
    grid = [params["pbo"]["partitions_primary"]] + params["pbo"]["partitions_sensitivity"]
    metrics = [params["pbo"]["metric_primary"]] + params["pbo"]["metric_sensitivity"]
    dates = None
    for name, trials in params["trial_sets"].items():
        set_dates, matrix = aligned_matrix(values, trials)
        if dates is None:
            dates = set_dates
        elif dates != set_dates:
            raise ValueError("trial sets cover different decision dates")
        dsr[name] = dsr_block(trials, matrix)
        pbo[name] = {"%s_S%d" % (metric, s): pbo_block(matrix, s, metric) for metric in metrics for s in grid}
    primary = pbo["primary"]["%s_S%d" % (params["pbo"]["metric_primary"], params["pbo"]["partitions_primary"])]
    return {
        "inputs": {"params_sha256": sha256(params_path),
                   "ledger_sha256": sha256(root / params["source"]["ledger_path"]),
                   "research_receipt_sha256": sha256(root / params["source"]["research_receipt_path"]),
                   "overfitting_py_sha256": sha256(HERE / "overfitting.py"),
                   "evaluate_py_sha256": sha256(HERE / "evaluate.py")},
        "ledger_records": len(ledger),
        "development_episodes": len(dates), "first_decision": dates[0], "last_decision": dates[-1],
        "dsr": dsr, "pbo": pbo,
        "primary": {"dsr": dsr["primary"]["dsr"], "dsr_selected_trial": dsr["primary"]["selected_trial"],
                    "pbo": primary["pbo"], "pbo_strict": primary["pbo_strict"],
                    "probability_oos_loss": primary["probability_oos_loss"]},
        "walk_forward": walk_forward_block(ledger, receipt),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(compute(args.root.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
