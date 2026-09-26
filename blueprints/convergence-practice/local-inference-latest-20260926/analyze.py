#!/usr/bin/env python3
"""Paired analysis of the frozen arms and the preregistered replacement decision.

Standard library only. Reads each arm's public metrics.json (eval_arm.py) and
window.json/memory.csv (window.sh); writes one public decision file. Inference
speed alone never passes: quality non-inferiority, faster median decode, JSON
validity and a clean memory/deadline record are all required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan.json"
CONTROL = "C0"
FAILURE_FREE_STATUS = "completed"


def counts(gold, predicted):
    gold, predicted = set(gold), set(predicted or ())
    return len(gold & predicted), len(predicted - gold), len(gold - predicted)


def f1_from(tp, fp, fn):
    denominator = 2 * tp + fp + fn
    return 2 * tp / denominator if denominator else 1.0


def filing_scores(gold, predicted):
    """Per-filing precision (0 when nothing valid is predicted), recall, F1 and exact match."""
    tp, fp, fn = counts(gold, predicted)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 1.0,
            "f1": f1_from(tp, fp, fn),
            "exact": set(gold) == set(predicted or ())}


def micro_f1(triples):
    tp = sum(t[0] for t in triples)
    fp = sum(t[1] for t in triples)
    fn = sum(t[2] for t in triples)
    return f1_from(tp, fp, fn)


def macro_f1(golds, predictions, min_support=5):
    """Mean per-code F1 over codes declared by at least `min_support` filings."""
    support = {}
    for gold in golds:
        for code in set(gold):
            support[code] = support.get(code, 0) + 1
    codes = sorted(code for code, count in support.items() if count >= min_support)
    per_code = {}
    for code in codes:
        tp = fp = fn = 0
        for gold, predicted in zip(golds, predictions):
            in_gold, in_pred = code in gold, code in (predicted or ())
            tp += in_gold and in_pred
            fp += in_pred and not in_gold
            fn += in_gold and not in_pred
        per_code[code] = f1_from(tp, fp, fn)
    value = statistics.fmean(per_code.values()) if per_code else None
    return value, per_code


def nearest_rank(sorted_values, fraction):
    """Nearest-rank percentile: the ceil(fraction * B)-th smallest value (1-based)."""
    rank = min(len(sorted_values), max(1, math.ceil(fraction * len(sorted_values) - 1e-9)))
    return sorted_values[rank - 1]


def paired_bootstrap(control, arm, resamples=10000, seed=20260926, alpha=0.05):
    """Percentile bootstrap of micro-F1(arm) - micro-F1(control) over paired filings.

    Filings are in accession order; each resample is random.Random(seed).choices
    over their indices, applied to both arms.
    """
    if len(control) != len(arm) or not control:
        raise ValueError("paired filings required")
    rng = random.Random(seed)
    indices = range(len(control))
    differences = []
    for _ in range(resamples):
        a_tp = a_fp = a_fn = c_tp = c_fp = c_fn = 0
        for i in rng.choices(indices, k=len(control)):
            a_tp += arm[i][0]
            a_fp += arm[i][1]
            a_fn += arm[i][2]
            c_tp += control[i][0]
            c_fp += control[i][1]
            c_fn += control[i][2]
        differences.append(f1_from(a_tp, a_fp, a_fn) - f1_from(c_tp, c_fp, c_fn))
    differences.sort()
    return {"point": micro_f1(arm) - micro_f1(control),
            "lower": nearest_rank(differences, alpha / 2),
            "upper": nearest_rank(differences, 1 - alpha / 2),
            "resamples": resamples, "seed": seed}


def memory_summary(path):
    """Whole-device peak use and minimum free from the 1 Hz `epoch_ms,used_mib,free_mib` samples."""
    used, free = [], []
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split(",")
            if len(parts) == 3 and all(part.strip().isdigit() for part in parts):
                used.append(int(parts[1]))
                free.append(int(parts[2]))
    return {"samples": len(used), "peak_device_used_mib": max(used, default=None),
            "min_device_free_mib": min(free, default=None)}


def arm_summary(metrics, window, memory):
    filings = metrics["filings"]
    triples = [counts(f["gold"], f["predicted"]) for f in filings]
    scores = [filing_scores(f["gold"], f["predicted"]) for f in filings]
    macro, per_code = macro_f1([f["gold"] for f in filings], [f["predicted"] for f in filings])
    speeds = [f["predicted_per_second"] for f in filings
              if f.get("http_status") == 200 and (f.get("predicted_n") or 0) >= 1
              and isinstance(f.get("predicted_per_second"), (int, float))]
    ttft = [f["prompt_ms"] for f in filings if f.get("http_status") == 200
            and isinstance(f.get("prompt_ms"), (int, float))]
    n = len(filings)
    failures = list(metrics.get("events", [])) + list((window or {}).get("guard_events", []))
    if metrics.get("status") != FAILURE_FREE_STATUS:
        failures.append("eval-" + str(metrics.get("status")))
    if window is None:
        failures.append("window-record-missing")
    elif window.get("status") != FAILURE_FREE_STATUS:
        failures.append("window-" + str(window.get("status")))
    cold = (window or {}).get("cold_load_ms")
    return {"n": n, "micro_f1": micro_f1(triples), "macro_f1": macro, "macro_codes": sorted(per_code),
            "per_code_f1": per_code,
            "mean_precision": statistics.fmean(s["precision"] for s in scores) if n else None,
            "mean_recall": statistics.fmean(s["recall"] for s in scores) if n else None,
            "mean_f1": statistics.fmean(s["f1"] for s in scores) if n else None,
            "exact_match_rate": sum(s["exact"] for s in scores) / n if n else None,
            "json_valid_rate": sum(f["parse_status"] == "valid" for f in filings) / n if n else 0.0,
            "fenced_valid_rate": sum(f["parse_status"] == "fenced_valid" for f in filings) / n if n else 0.0,
            "error_count": sum(f.get("error") is not None for f in filings),
            "median_decode_tokens_per_second": statistics.median(speeds) if speeds else None,
            "median_ttft_ms": statistics.median(ttft) if ttft else None,
            "cold_load_seconds": None if cold is None else cold / 1000,
            **memory,
            "failures": failures, "failure_free": not failures}


def criteria(bootstrap, arm, control, rule):
    return {
        "noninferior_micro_f1": bootstrap["lower"] >= rule["noninferiority_margin"],
        "faster_median_decode": (arm["median_decode_tokens_per_second"] is not None
                                 and control["median_decode_tokens_per_second"] is not None
                                 and arm["median_decode_tokens_per_second"]
                                 > control["median_decode_tokens_per_second"]),
        "json_valid_rate": arm["json_valid_rate"] >= rule["json_valid_min"],
        "no_memory_or_deadline_failure": arm["failure_free"],
    }


def outcome(role, passed):
    """All four criteria or nothing; a same-model profile arm changes only the serving profile."""
    if not all(passed.values()):
        return "retain_control"
    return {"serving_profile_candidate": "change_serving_profile",
            "model_candidate": "replace_model"}[role]


def select(results, order):
    """Fastest passing arm; ties go to higher micro-F1, then to plan order."""
    passing = [r for r in results if r["outcome"] != "retain_control"]
    if not passing:
        return {"arm": None, "outcome": "retain_control"}
    best = max(passing, key=lambda r: (r["summary"]["median_decode_tokens_per_second"],
                                        r["summary"]["micro_f1"], -order.index(r["arm"])))
    return {"arm": best["arm"], "outcome": best["outcome"]}


def load_arm(directory):
    directory = Path(directory)
    window_path, metrics_path = directory / "window.json", directory / "eval" / "metrics.json"
    window = json.loads(window_path.read_text()) if window_path.exists() else None
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else None
    return metrics, window, memory_summary(directory / "memory.csv")


def analyze(plan, plan_sha256, arm_dirs):
    rule = plan["decision_rule"]
    loaded, not_evaluated = {}, []
    for directory in arm_dirs:
        metrics, window, memory = load_arm(directory)
        if metrics is None:
            # Refused at admission, failed at startup or stopped before evaluation.
            not_evaluated.append({"arm": (window or {}).get("arm"), "window_status": (window or {}).get("status"),
                                  "guard_events": (window or {}).get("guard_events")})
            continue
        if metrics["arm"] in loaded:
            raise ValueError(f"duplicate arm {metrics['arm']}")
        if metrics["plan_sha256"] != plan_sha256 or metrics["prompt_sha256"] != plan["prompt_sha256"]:
            raise ValueError(f"arm {metrics['arm']} ran a different plan or prompt")
        loaded[metrics["arm"]] = (metrics, window, memory)
    base = {"schema_version": 1, "kind": "local_inference_latest_decision", "plan_sha256": plan_sha256,
            "rule": rule["text"], "arms_not_evaluated": not_evaluated, "no_document_text": True,
            "arms_not_run": [arm["id"] for arm in plan["arms"] if arm["id"] not in loaded]}
    if CONTROL not in loaded:
        return {**base, "inputs_sha256": None, "n_filings": 0, "control": None, "arms": [],
                "selected": {"arm": None, "outcome": "inconclusive_control_not_evaluated"}}
    control_metrics = loaded[CONTROL][0]
    keys = [(f["accession"], tuple(f["gold"])) for f in control_metrics["filings"]]
    for arm_id, (metrics, _, _) in loaded.items():
        if metrics["inputs_sha256"] != control_metrics["inputs_sha256"] or \
                [(f["accession"], tuple(f["gold"])) for f in metrics["filings"]] != keys:
            raise ValueError(f"arm {arm_id} is not paired with the control filings")
    summaries = {arm_id: arm_summary(*values) for arm_id, values in loaded.items()}
    control = summaries[CONTROL]
    order = [arm["id"] for arm in plan["arms"]]
    roles = {arm["id"]: arm["role"] for arm in plan["arms"]}
    control_triples = [counts(f["gold"], f["predicted"]) for f in control_metrics["filings"]]
    results = []
    for arm_id in [a for a in order if a in loaded and a != CONTROL]:
        triples = [counts(f["gold"], f["predicted"]) for f in loaded[arm_id][0]["filings"]]
        bootstrap = paired_bootstrap(control_triples, triples, rule["bootstrap"]["resamples"],
                                     rule["bootstrap"]["seed"], rule["bootstrap"]["alpha"])
        passed = criteria(bootstrap, summaries[arm_id], control, rule)
        results.append({"arm": arm_id, "summary": summaries[arm_id], "bootstrap": bootstrap,
                        "criteria": passed, "outcome": outcome(roles[arm_id], passed)})
    if not control["failure_free"]:
        selected = {"arm": None, "outcome": "inconclusive_control_invalid"}
    else:
        selected = select(results, order)
    return {**base, "inputs_sha256": control_metrics["inputs_sha256"], "n_filings": len(keys),
            "control": {"arm": CONTROL, "summary": control}, "arms": results, "selected": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--arm-dir", type=Path, action="append", required=True,
                        help="one window.sh arm directory (repeat; C0 required)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.plan.read_bytes()
    decision = analyze(json.loads(raw), hashlib.sha256(raw).hexdigest(), args.arm_dir)
    with args.out.open("x") as stream:
        json.dump(decision, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(decision["selected"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
