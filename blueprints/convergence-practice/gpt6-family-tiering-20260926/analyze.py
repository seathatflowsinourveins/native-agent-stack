#!/usr/bin/env python3
"""Paired analysis of the six GPT-6 family arms and the preregistered routing recommendation.

Standard library only. Every frozen file (both scripts, the prompt, the schema and the reused li26 and path_safety
code) is verified against plan.json before anything is read, so the analysis cannot run on changed code. The
filings, their header labels and the batch layout are rebuilt from the verified acquisition, exactly as run_arm.py
builds them. Every attempt of every batch under --state-dir is read, so no call can be left out. That includes
failed, retried, limit, unavailable, interrupted and abandoned calls. Scoring reuses li26's own functions unchanged:
per-filing counts, micro-F1, macro-F1 over codes with at least five labelled filings, and the paired percentile
bootstrap. The decision file holds aggregates only: no filing text, no reply text and no accession numbers.

Frozen rule: an arm is routable for mechanical extraction when the bootstrap 95% lower bound of
micro-F1(arm) - micro-F1(A0) is at least -0.02, its JSON-valid rate is at least 0.98 and every batch completed.
Cost is the mean billed tokens per filing: uncached input plus output, where Codex's output already includes
reasoning. A candidate is recommended only when it is routable, its token use is fully known, and its cost is
strictly below A0's; among such candidates the cheapest wins, ties going to the lower median wall time of ok calls,
then to plan order. When some of A0's token use is unknown, A0's reported cost is a lower bound: a candidate below
it is still recommended, and otherwise the result is inconclusive. Quota percentages are context only.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan.json"
CONTROL = "A0"

_SPEC = importlib.util.spec_from_file_location("gt26_run_arm_for_analysis", HERE / "run_arm.py")
run_arm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_arm)
_SPEC = importlib.util.spec_from_file_location("gt26_li26_analyze", run_arm.LI26 / "analyze.py")
li26 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(li26)


def read_json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def arm_elapsed_seconds(arm_dir):
    """The summed elapsed time of every recorded run of the arm (runs.jsonl), or None when there is none."""
    try:
        lines = (Path(arm_dir) / "runs.jsonl").read_text().splitlines()
    except OSError:
        return None
    values = []
    for line in lines:
        try:
            value = json.loads(line).get("elapsed_seconds")
        except (ValueError, AttributeError):
            continue
        if isinstance(value, (int, float)):
            values.append(value)
    return round(sum(values), 3) if values else None


def usage_summary(records, n_filings):
    """Token totals and means per filing by kind, over every call of the arm.

    Codex reports input including cached input, and output including reasoning (docs/token-practice.md), so
    billed = (input - cached input) + output. Adding reasoning again would count it twice. Every call that reported
    usage counts, whatever its outcome. A call without a report counts as zero when no billed request can have run
    (a launch failure, or a turn refused by the usage limit); any other such call (a timeout, an unavailable,
    interrupted or abandoned call) leaves the arm's usage incomplete, so its totals are only a lower bound.
    """
    totals = {key: 0 for key in run_arm.USAGE_KEYS}
    without, violations = {}, 0
    for record in records:
        usage = record.get("usage")
        if not isinstance(usage, dict) or any(not isinstance(usage.get(key), int) for key in run_arm.CORE_USAGE_KEYS):
            if not run_arm.usage_known({**record, "usage": None}):
                outcome = str(record.get("outcome"))
                without[outcome] = without.get(outcome, 0) + 1
            continue
        for key in run_arm.USAGE_KEYS:
            totals[key] += usage.get(key, 0) if isinstance(usage.get(key), int) else 0
        if (usage["cached_input_tokens"] > usage["input_tokens"]
                or usage.get("reasoning_output_tokens", 0) > usage["output_tokens"]):
            violations += 1
    uncached = totals["input_tokens"] - totals["cached_input_tokens"]
    kinds = {"input": totals["input_tokens"], "cached_input": totals["cached_input_tokens"],
             "uncached_input": uncached, "cache_write_input": totals["cache_write_input_tokens"],
             "output_including_reasoning": totals["output_tokens"],
             "reasoning": totals["reasoning_output_tokens"],
             "visible_output": totals["output_tokens"] - totals["reasoning_output_tokens"],
             "billed": uncached + totals["output_tokens"]}
    return {"totals": kinds, "per_filing": {key: value / n_filings for key, value in kinds.items()},
            "calls_without_usage": sum(without.values()), "calls_without_usage_by_outcome": without,
            "usage_complete": not without, "subset_violations": violations}


def wall_summary(records, n_filings, elapsed):
    ok = [r["wall_seconds"] for r in records if r.get("outcome") == "ok" and isinstance(r.get("wall_seconds"), (int, float))]
    every = [r["wall_seconds"] for r in records if isinstance(r.get("wall_seconds"), (int, float))]
    waits = [r["slot_wait_seconds"] for r in records if isinstance(r.get("slot_wait_seconds"), (int, float))]
    return {"median_ok_call_wall_seconds": statistics.median(ok) if ok else None,
            "total_call_wall_seconds": round(sum(every), 3),
            "call_wall_seconds_per_filing": sum(every) / n_filings,
            "slot_wait_seconds": round(sum(waits), 3), "run_elapsed_seconds": elapsed}


def evaluate_arm(plan, plan_sha256, state_dir, arm, template, batches, version):
    """One arm's attempts, batch states, per-filing predictions and every record inconsistency."""
    arm_id = arm["id"]
    arm_dir = Path(state_dir) / "arms" / arm_id
    if not arm_dir.is_dir():
        return {"arm": arm_id, "state": "not_run"}
    if run_arm.lock_held(arm_dir / "run.lock"):
        raise ValueError(f"arm {arm_id} is running; analyze after every run has exited")
    batches_dir = arm_dir / "batches"
    if not (arm_dir / "identity.json").exists() and not any(
            run_arm.attempt_dirs(path) for path in (batches_dir.iterdir() if batches_dir.is_dir() else ())):
        return {"arm": arm_id, "state": "not_run"}  # a run that stopped before its first call
    if read_json(arm_dir / "identity.json") != run_arm.identity(plan, plan_sha256, arm, batches, version):
        raise ValueError(f"arm {arm_id} ran a different plan, prompt, schema, inputs, layout or Codex version")
    retries = plan["calls"]["retries_per_batch"]
    known = {run_arm.batch_id(index) for index in range(len(batches))}
    problems = sorted(f"unexpected-batch-directory:{path.name}" for path in
                      (batches_dir.iterdir() if batches_dir.is_dir() else ()) if path.name not in known)
    records, states, predicted, status, unexpected = [], [], {}, {}, 0
    for index, batch in enumerate(batches):
        name, accessions = run_arm.batch_id(index), [row["accession"] for row in batch]
        prompt_sha256 = run_arm.sha256_bytes(run_arm.build_prompt(template, batch).encode("utf-8"))
        attempts = run_arm.attempt_dirs(batches_dir / name)
        if [number for number, _ in attempts] != list(range(1, len(attempts) + 1)):
            problems.append(f"attempt-numbers-not-consecutive:{name}")
        batch_records = []
        for number, path in attempts:
            record = run_arm.attempt_record(arm, index, batch, number, path, template)
            derived = run_arm.turn_usage(run_arm.read_events(path / "events.jsonl"))
            if (record.get("arm") != arm_id or record.get("batch") != name or record.get("attempt") != number
                    or record.get("accessions") != accessions or record.get("prompt_sha256") != prompt_sha256
                    or record.get("model") != arm["model"] or record.get("effort") != arm["effort"]):
                problems.append(f"record-mismatch:{name}:attempt-{number}")
            if record.get("usage") != derived:
                problems.append(f"usage-mismatch:{name}:attempt-{number}")
            batch_records.append((path, record))
        records += [record for _, record in batch_records]
        state = run_arm.batch_state([record for _, record in batch_records], retries)
        states.append(state)
        ok = [(path, record) for path, record in batch_records if record.get("outcome") == "ok"]
        for accession in accessions:
            predicted[accession], status[accession] = None, "invalid"
        if ok:
            path, record = ok[0]
            if len(ok) > 1 or batch_records[-1][1] is not record:
                problems.append(f"attempt-after-completion:{name}")
            reply_status, per_filing, extra = run_arm.parse_reply(run_arm.reply_text(path / "reply.json"), accessions)
            if reply_status != record.get("reply_status"):
                problems.append(f"reply-status-mismatch:{name}")
            unexpected += extra
            for accession, (items, filing_status) in per_filing.items():
                predicted[accession], status[accession] = items, filing_status
    outcomes = [record.get("outcome") for record in records]
    reasons = {}
    for record in records:
        if record.get("reason"):
            reasons[record["reason"]] = reasons.get(record["reason"], 0) + 1
    return {"arm": arm_id, "state": "incomplete" if "pending" in states else "complete",
            "records": records, "states": states, "predicted": predicted, "status": status,
            "unexpected_entries": unexpected, "problems": problems,
            "calls": {"total": len(records), **{kind: outcomes.count(kind) for kind in
                                                ("ok", "failed", "limit", "unavailable", "interrupted", "abandoned")},
                      "by_reason": dict(sorted(reasons.items())),
                      "tool_use": sum(record.get("reason") == "tool_use" for record in records)},
            "elapsed": arm_elapsed_seconds(arm_dir)}


def arm_summary(result, rows):
    order = [row["accession"] for row in rows]
    golds = [row["labels"] for row in rows]
    predictions = [result["predicted"][accession] for accession in order]
    triples = [li26.counts(gold, predicted) for gold, predicted in zip(golds, predictions)]
    scores = [li26.filing_scores(gold, predicted) for gold, predicted in zip(golds, predictions)]
    macro, per_code = li26.macro_f1(golds, predictions)
    n = len(rows)
    statuses = [result["status"][accession] for accession in order]
    states = result["states"]
    usage = usage_summary(result["records"], n)
    return {"n": n, "state": result["state"], "micro_f1": li26.micro_f1(triples), "macro_f1": macro,
            "macro_codes": sorted(per_code), "per_code_f1": per_code,
            "mean_precision": statistics.fmean(s["precision"] for s in scores),
            "mean_recall": statistics.fmean(s["recall"] for s in scores),
            "mean_f1": statistics.fmean(s["f1"] for s in scores),
            "exact_match_rate": sum(s["exact"] for s in scores) / n,
            "json_valid_rate": statuses.count("valid") / n, "fenced_valid_rate": statuses.count("fenced_valid") / n,
            "invalid_filings": statuses.count("invalid"), "unexpected_entries": result["unexpected_entries"],
            "batches": {"total": len(states), **{state: states.count(state)
                                                 for state in ("completed", "failed", "pending")}},
            "failed_batch_ids": [run_arm.batch_id(i) for i, state in enumerate(states) if state == "failed"],
            "pending_batch_ids": [run_arm.batch_id(i) for i, state in enumerate(states) if state == "pending"],
            "retried_batches": sum(1 for index in range(len(states))
                                   if any(record.get("outcome") == "failed" and record.get("batch") ==
                                          run_arm.batch_id(index) for record in result["records"])),
            "calls": result["calls"], "tokens": usage,
            "wall": wall_summary(result["records"], n, result["elapsed"]), "problems": result["problems"],
            "every_batch_completed": (result["state"] == "complete" and states.count("failed") == 0
                                      and not result["problems"])}


def triples_of(result, rows):
    return [li26.counts(row["labels"], result["predicted"][row["accession"]]) for row in rows]


def decide(plan, results, summaries, bootstraps):
    """The routable arms, the ranked candidates and the recommendation, under the frozen rule.

    A0 is the reference, not a ranked candidate: a candidate is recommended only when its cost is known and strictly
    below A0's. A0's cost counts even when some of its token use is unknown, as a lower bound of its true cost, so a
    candidate below it is still certainly cheaper; if no ranked candidate is below it, the result is inconclusive,
    because A0's true cost may lie above some of them."""
    rule = plan["decision_rule"]
    order = [arm["id"] for arm in plan["arms"]]
    control = results[CONTROL]
    if control["state"] == "not_run":
        return {"arm": None, "outcome": "inconclusive_control_not_evaluated"}, {}
    if control["state"] == "incomplete":
        return {"arm": None, "outcome": "inconclusive_control_incomplete"}, {}
    control_summary = summaries[CONTROL]
    if not (control_summary["every_batch_completed"] and control_summary["json_valid_rate"] >= rule["json_valid_min"]):
        return {"arm": None, "outcome": "inconclusive_control_invalid"}, {}
    if any(summary["tokens"]["subset_violations"] for summary in summaries.values()):
        return {"arm": None, "outcome": "inconclusive_usage_subset_rule_violated"}, {}
    criteria = {}
    for arm_id in order:
        if arm_id not in summaries:
            continue
        summary = summaries[arm_id]
        lower = 0.0 if arm_id == CONTROL else bootstraps[arm_id]["lower"]
        criteria[arm_id] = {"noninferior_micro_f1": lower >= rule["noninferiority_margin"],
                            "json_valid_rate": summary["json_valid_rate"] >= rule["json_valid_min"],
                            "every_batch_completed": summary["every_batch_completed"]}
    routable = [arm_id for arm_id in order if arm_id in criteria and all(criteria[arm_id].values())]

    def billed(arm_id):
        return summaries[arm_id]["tokens"]["per_filing"]["billed"]

    def key(arm_id):
        wall = summaries[arm_id]["wall"]["median_ok_call_wall_seconds"]
        return billed(arm_id), math.inf if wall is None else wall, order.index(arm_id)

    ranked = sorted((arm_id for arm_id in routable
                     if arm_id != CONTROL and summaries[arm_id]["tokens"]["usage_complete"]), key=key)
    control_known = control_summary["tokens"]["usage_complete"]
    context = {"routable": routable, "ranked": ranked, "control_billed_per_filing": billed(CONTROL),
               "control_usage_complete": control_known}
    cheaper = [arm_id for arm_id in ranked if billed(arm_id) < billed(CONTROL)]
    if cheaper:
        best = cheaper[0]
        arm = run_arm.arm_by_id(plan, best)
        return {"arm": best, "model": arm["model"], "effort": arm["effort"],
                "outcome": "route_mechanical_extraction", **context}, criteria
    default = run_arm.arm_by_id(plan, CONTROL)
    keep = {"arm": CONTROL, "model": default["model"], "effort": default["effort"], "outcome": "keep_default"}
    if not any(arm_id != CONTROL for arm_id in routable):
        return {**keep, "reason": "no_routable_candidate", **context}, criteria
    if not ranked:
        return {**keep, "reason": "no_candidate_with_known_usage", **context}, criteria
    if not control_known:
        return {"arm": None, "outcome": "inconclusive_control_usage_incomplete", **context}, criteria
    return {**keep, "reason": "no_candidate_below_control", **context}, criteria


def quota_context(path, plan):
    """Coordinator-read quota percentages, reported beside the decision and never used by it."""
    if path is None:
        return None
    data = json.loads(Path(path).read_text())
    ids = [arm["id"] for arm in plan["arms"]]
    readings = []
    for entry in data.get("readings", []):
        before, after = entry.get("before_percent"), entry.get("after_percent")
        if entry.get("arm") not in ids or any(not isinstance(value, (int, float)) or isinstance(value, bool)
                                              or not 0 <= value <= 100 for value in (before, after)):
            raise ValueError("quota readings need a planned arm and before/after percentages from 0 to 100")
        readings.append({"arm": entry["arm"], "window": str(entry.get("window", "")),
                         "before_percent": before, "after_percent": after,
                         "delta_percent": round(after - before, 4),
                         "before_utc": entry.get("before_utc"), "after_utc": entry.get("after_utc")})
    return {"used_by_rule": False, "attributable_to_one_arm": False, "caveat": plan["quota_context"]["caveat"],
            "source": str(data.get("source", "")), "readings": readings}


def analyze(plan, plan_sha256, acquisition, state_dir, quota_path=None):
    run_arm.check_plan(plan)
    run_arm.verify_frozen(plan)  # the scripts, the reused li26 scorers, the prompt and the schema are unchanged
    template = run_arm.prompt_template(plan)
    rows = run_arm.load_rows(plan, acquisition)
    batches = run_arm.frozen_batches(plan, template, rows)
    version = plan["codex"]["version"]
    order = [arm["id"] for arm in plan["arms"]]
    results = {arm["id"]: evaluate_arm(plan, plan_sha256, state_dir, arm, template, batches, version)
               for arm in plan["arms"]}
    summaries = {arm_id: arm_summary(result, rows) for arm_id, result in results.items()
                 if result["state"] != "not_run"}
    bootstraps = {}
    if CONTROL in summaries:
        control = triples_of(results[CONTROL], rows)
        boot = plan["decision_rule"]["bootstrap"]
        for arm_id in order:
            if arm_id != CONTROL and arm_id in summaries:
                bootstraps[arm_id] = li26.paired_bootstrap(control, triples_of(results[arm_id], rows),
                                                           boot["resamples"], boot["seed"], boot["alpha"])
    selected, criteria = decide(plan, results, summaries, bootstraps)
    arms = []
    for arm in plan["arms"]:
        entry = {"arm": arm["id"], "role": arm["role"], "model": arm["model"], "effort": arm["effort"],
                 "state": results[arm["id"]]["state"]}
        if arm["id"] in summaries:
            entry["summary"] = summaries[arm["id"]]
            entry["bootstrap_vs_control"] = bootstraps.get(arm["id"])
            entry["criteria"] = criteria.get(arm["id"])
            entry["routable"] = arm["id"] in selected.get("routable", [])
        arms.append(entry)
    return {"schema_version": 2, "kind": "gpt6_family_tiering_decision", "plan_sha256": plan_sha256,
            "frozen_inputs": dict(sorted(plan["frozen_inputs"].items())), "frozen_inputs_verified": True,
            "inputs_sha256": plan["task"]["inputs_sha256"], "layout_sha256": run_arm.layout_sha256(batches),
            "n_filings": len(rows), "n_batches": len(batches), "codex_version": version,
            "rule": plan["decision_rule"]["text"], "no_document_text": True,
            "final": all(results[arm_id]["state"] == "complete" for arm_id in order),
            "arms_not_run": [arm_id for arm_id in order if results[arm_id]["state"] == "not_run"],
            "arms_incomplete": [arm_id for arm_id in order if results[arm_id]["state"] == "incomplete"],
            "arms": arms, "selected": selected, "quota_context": quota_context(quota_path, plan)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--acquisition", type=Path, required=True, help="the frozen li26 acquisition directory")
    parser.add_argument("--state-dir", type=Path, default=run_arm.DEFAULT_STATE_DIR)
    parser.add_argument("--quota-context", type=Path, help="optional coordinator-read quota percentages (context)")
    parser.add_argument("--out", type=Path, required=True, help="the decision file; never overwritten")
    args = parser.parse_args(argv)
    raw = args.plan.read_bytes()
    decision = analyze(json.loads(raw), hashlib.sha256(raw).hexdigest(), args.acquisition, args.state_dir,
                       args.quota_context)
    with args.out.open("x") as stream:
        json.dump(decision, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"selected": decision["selected"], "final": decision["final"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
