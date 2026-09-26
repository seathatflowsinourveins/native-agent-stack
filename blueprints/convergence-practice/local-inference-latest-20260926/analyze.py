#!/usr/bin/env python3
"""Paired analysis of the frozen arms and the preregistered replacement decision.

Standard library only. Scans every window that window.sh recorded under
--state-dir, so no attempt can be left out, rebuilds each arm's segment chain
(eval/metrics.json, window.json, memory.csv) and writes one public decision
file. Inference speed alone never passes: quality non-inferiority, faster median
decode, JSON validity and a complete, failure-free record with verified memory
evidence are all required.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics
import sys

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan.json"
CONTROL = "C0"

_SPEC = importlib.util.spec_from_file_location("li26_eval_arm_for_analysis", HERE / "eval_arm.py")
eval_arm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(eval_arm)


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


def memory_evidence(arm_dir, record, window):
    """1 Hz `epoch_ms,used_mib,free_mib` samples of one started segment, and every problem with them.

    Missing, malformed, unordered, gappy or non-covering samples, a sampled reserve
    breach and an unverified memory limit are all failures, whatever the events say.
    """
    reserve, max_gap_ms = window["minimum_free_mib"], window["monitor_max_gap_seconds"] * 1000
    problems, samples = [], []
    try:
        lines = (Path(arm_dir) / "memory.csv").read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        lines = []
    if not lines:
        problems.append("memory-samples-missing")
    for line in lines:
        parts = line.split(",")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            problems.append("memory-samples-malformed")
            break
        samples.append(tuple(int(part) for part in parts))
    if samples:
        times = [sample[0] for sample in samples]
        if any(later < earlier for earlier, later in zip(times, times[1:])):
            problems.append("memory-samples-unordered")
        elif max((later - earlier for earlier, later in zip(times, times[1:])), default=0) > max_gap_ms:
            problems.append("memory-monitor-gap")
        started, stopped = record.get("server_started_ms"), record.get("monitor_stopped_ms")
        if (type(started) is not int or type(stopped) is not int
                or times[0] - started > max_gap_ms or stopped - times[-1] > max_gap_ms):
            problems.append("memory-monitor-coverage")
        if min(sample[2] for sample in samples) < reserve:
            problems.append("device-memory-reserve-breached-in-samples")
    if record.get("memory_max_verified") is not True:
        problems.append("memory-limit-unverified")
    return {"samples": len(samples), "peak_device_used_mib": max((s[1] for s in samples), default=None),
            "min_device_free_mib": min((s[2] for s in samples), default=None)}, problems


def carry_problems(chain):
    """Each segment must carry every earlier result verbatim and add results only under its own number."""
    problems, previous = [], None
    for position, attempt in enumerate(chain, 1):
        metrics = attempt["metrics"]
        if metrics is None:
            previous = None
            continue
        filings = metrics.get("filings") or []
        if any(entry.get("segment") not in (None, *range(1, position + 1)) for entry in filings):
            problems.append(f"segment-number-in-filings:{attempt['window']}")
        if previous is not None:
            before = {entry["accession"]: entry for entry in previous.get("filings") or []}
            if [entry["accession"] for entry in filings] != list(before):
                problems.append(f"segment-filings-changed:{attempt['window']}")
            for entry in filings:
                old = before.get(entry["accession"])
                if old is not None and old.get("segment") is not None and old != entry:
                    problems.append(f"segment-carry-mismatch:{attempt['window']}")
                    break
                if (old is None or old.get("segment") is None) and entry.get("segment") not in (None, position):
                    problems.append(f"segment-carry-mismatch:{attempt['window']}")
                    break
        previous = metrics
    return problems


def evaluate_chain(plan, state_dir, arm_id):
    """An arm's state (not_run, completed, incomplete, failed), its final metrics and all its failures."""
    window = plan["window"]
    attempts = eval_arm.arm_attempts(state_dir, arm_id)
    not_started = [{"window": a["window"], "status": a["status"],
                    "admission_required_mib": (a["window_record"] or {}).get("admission_required_mib"),
                    "free_mib_at_admission": (a["window_record"] or {}).get("free_mib_at_admission")}
                   for a in attempts if a["kind"] == "not_started"]
    chain, problems = eval_arm.read_chain(plan, state_dir, arm_id)
    if not chain:
        return {"arm": arm_id, "state": "not_run", "not_started": not_started, "segments": [], "failures": [],
                "metrics": None}
    failures = list(problems) + carry_problems(chain)
    segments = []
    for position, attempt in enumerate(chain, 1):
        record = attempt["window_record"] or {}
        if attempt["kind"] == "failed":
            failures.append(f"attempt-{attempt['status'] or 'unrecorded'}:{attempt['window']}")
        failures += [str(event) for event in record.get("guard_events") or []]
        failures += [str(event) for event in (attempt["metrics"] or {}).get("events") or []]
        memory, memory_problems = memory_evidence(attempt["dir"], record, window)
        failures += memory_problems
        cold = record.get("cold_load_ms")
        segments.append({"segment": position, "window": attempt["window"], "status": attempt["status"],
                         "cold_load_seconds": cold / 1000 if type(cold) is int else None, **memory})
    last = chain[-1]
    if last["kind"] == "completed":
        state = "completed"
    elif last["kind"] == "boundary" and len(chain) < window["max_segments"]:
        state = "incomplete"
    else:
        state = "failed"
        if last["kind"] == "boundary":
            failures.append("segments-exhausted")
    metrics = next((attempt["metrics"] for attempt in reversed(chain) if attempt["metrics"] is not None), None)
    return {"arm": arm_id, "state": state, "not_started": not_started, "segments": segments,
            "failures": list(dict.fromkeys(failures)), "metrics": metrics}


def arm_summary(result):
    filings = result["metrics"]["filings"]
    triples = [counts(f["gold"], f["predicted"]) for f in filings]
    scores = [filing_scores(f["gold"], f["predicted"]) for f in filings]
    macro, per_code = macro_f1([f["gold"] for f in filings], [f["predicted"] for f in filings])
    speeds = [f["predicted_per_second"] for f in filings
              if f.get("http_status") == 200 and (f.get("predicted_n") or 0) >= 1
              and isinstance(f.get("predicted_per_second"), (int, float))]
    ttft = [f["prompt_ms"] for f in filings if f.get("http_status") == 200
            and isinstance(f.get("prompt_ms"), (int, float))]
    segments = result["segments"]
    peaks = [s["peak_device_used_mib"] for s in segments if s["peak_device_used_mib"] is not None]
    lows = [s["min_device_free_mib"] for s in segments if s["min_device_free_mib"] is not None]
    n = len(filings)
    complete = result["state"] == "completed" and all(f.get("segment") is not None for f in filings)
    return {"n": n, "state": result["state"], "segments": len(segments),
            "micro_f1": micro_f1(triples), "macro_f1": macro, "macro_codes": sorted(per_code),
            "per_code_f1": per_code,
            "mean_precision": statistics.fmean(s["precision"] for s in scores) if n else None,
            "mean_recall": statistics.fmean(s["recall"] for s in scores) if n else None,
            "mean_f1": statistics.fmean(s["f1"] for s in scores) if n else None,
            "exact_match_rate": sum(s["exact"] for s in scores) / n if n else None,
            "json_valid_rate": sum(f["parse_status"] == "valid" for f in filings) / n if n else 0.0,
            "fenced_valid_rate": sum(f["parse_status"] == "fenced_valid" for f in filings) / n if n else 0.0,
            "context_overflow_count": sum(f.get("error") == "context_overflow" for f in filings),
            "not_attempted_count": sum(f.get("error") == "not_attempted" for f in filings),
            "median_decode_tokens_per_second": statistics.median(speeds) if speeds else None,
            "median_ttft_ms": statistics.median(ttft) if ttft else None,
            "cold_load_seconds": segments[0]["cold_load_seconds"] if segments else None,
            "segment_cold_load_seconds": [s["cold_load_seconds"] for s in segments],
            "memory_samples": sum(s["samples"] for s in segments),
            "peak_device_used_mib": max(peaks, default=None), "min_device_free_mib": min(lows, default=None),
            "failures": result["failures"], "failure_free": complete and not result["failures"]}


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
    passing = [r for r in results if r["outcome"] in ("change_serving_profile", "replace_model")]
    if not passing:
        return {"arm": None, "outcome": "retain_control"}
    best = max(passing, key=lambda r: (r["summary"]["median_decode_tokens_per_second"],
                                        r["summary"]["micro_f1"], -order.index(r["arm"])))
    return {"arm": best["arm"], "outcome": best["outcome"]}


def analyze(plan, plan_sha256, state_dir):
    eval_arm.check_plan(plan)
    rule = plan["decision_rule"]
    order = [arm["id"] for arm in plan["arms"]]
    roles = {arm["id"]: arm["role"] for arm in plan["arms"]}
    chains = {arm_id: evaluate_chain(plan, state_dir, arm_id) for arm_id in order}
    for arm_id, result in chains.items():
        metrics = result["metrics"]
        if metrics is not None and (metrics.get("plan_sha256") != plan_sha256
                                    or metrics.get("prompt_sha256") != plan["prompt_sha256"]):
            raise ValueError(f"arm {arm_id} ran a different plan or prompt")
    base = {"schema_version": 1, "kind": "local_inference_latest_decision", "plan_sha256": plan_sha256,
            "rule": rule["text"], "no_document_text": True,
            "arms_not_run": [{"arm": arm_id, "not_started": chains[arm_id]["not_started"]}
                             for arm_id in order if chains[arm_id]["state"] == "not_run"],
            "arms_incomplete": [arm_id for arm_id in order if chains[arm_id]["state"] == "incomplete"]}
    base["final"] = not base["arms_incomplete"]
    control = chains[CONTROL]
    if control["metrics"] is None:
        reason = ("inconclusive_control_not_evaluated" if control["state"] == "not_run"
                  else "inconclusive_control_invalid")
        return {**base, "inputs_sha256": None, "n_filings": 0,
                "control": {"arm": CONTROL, "state": control["state"], "failures": control["failures"]},
                "arms": [], "selected": {"arm": None, "outcome": reason}}
    keys = [(f["accession"], tuple(f["gold"])) for f in control["metrics"]["filings"]]
    for arm_id, result in chains.items():
        metrics = result["metrics"]
        if metrics is not None and (metrics["inputs_sha256"] != control["metrics"]["inputs_sha256"]
                                    or [(f["accession"], tuple(f["gold"])) for f in metrics["filings"]] != keys):
            raise ValueError(f"arm {arm_id} is not paired with the control filings")
    summaries = {arm_id: arm_summary(result) for arm_id, result in chains.items() if result["metrics"] is not None}
    control_summary = summaries[CONTROL]
    control_triples = [counts(f["gold"], f["predicted"]) for f in control["metrics"]["filings"]]
    results = []
    for arm_id in [a for a in order if a in summaries and a != CONTROL]:
        triples = [counts(f["gold"], f["predicted"]) for f in chains[arm_id]["metrics"]["filings"]]
        bootstrap = paired_bootstrap(control_triples, triples, rule["bootstrap"]["resamples"],
                                     rule["bootstrap"]["seed"], rule["bootstrap"]["alpha"])
        passed = criteria(bootstrap, summaries[arm_id], control_summary, rule)
        decided = "incomplete" if chains[arm_id]["state"] == "incomplete" else outcome(roles[arm_id], passed)
        results.append({"arm": arm_id, "summary": summaries[arm_id], "bootstrap": bootstrap,
                        "criteria": passed, "outcome": decided})
    if control["state"] == "incomplete":
        selected = {"arm": None, "outcome": "inconclusive_control_incomplete"}
    elif not control_summary["failure_free"]:
        selected = {"arm": None, "outcome": "inconclusive_control_invalid"}
    else:
        selected = select(results, order)
    return {**base, "inputs_sha256": control["metrics"]["inputs_sha256"], "n_filings": len(keys),
            "control": {"arm": CONTROL, "summary": control_summary}, "arms": results, "selected": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--state-dir", type=Path, required=True,
                        help="the --state-dir given to window.sh; every window under runs/ is read")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.plan.read_bytes()
    decision = analyze(json.loads(raw), hashlib.sha256(raw).hexdigest(), args.state_dir)
    with args.out.open("x") as stream:
        json.dump(decision, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"selected": decision["selected"], "final": decision["final"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
