#!/usr/bin/env python3
"""Paired analysis of the R02 promptfoo results and the preregistered decision.

  analyze_r02.py ids --results RESULTS.json [RESULTS.json ...]
  uv run --with scipy==1.18.1 --with statsmodels==0.15.0 --with numpy python analyze_r02.py analyze \
      --results-ab AB.json --results-ba BA.json [--call-logs CALL_LOGS.json] [--repeats 3] [--out DECISION.json]

Inputs are promptfoo 0.123.1 `-o <file>.json` outputs (promptfoo@0.123.1:src/util/output.ts:465-494, rows in
results.results) and, optionally, `call_logs_by_correlation.py --rows` output. The `ids` command needs only the
standard library.

- Rows. The arm is the provider label (r02-A, r02-B), which error rows carry too (src/evaluator.ts:808-832).
  Both arms of one filing and repeat share a testIdx, which promptfoo advances once per test and repeat
  (src/evaluator.ts:2674-2696); the repeat is the rank of that testIdx among the filing's testIdx values.
  failureReason 2 is a provider error and 1 a rejected assertion (src/types/index.ts:376-383;
  src/evaluator.ts:608-612, 1342-1346, 1799-1830).
- Errors. transform_r02.js returns its own prefixed errors with metadata. promptfoo throws before the transform
  on a 429 when maxRetries is 0 ("Rate limit exceeded: HTTP 429" or "Quota exceeded: HTTP 429",
  src/util/fetch/index.ts:681-714, 768-770; src/util/fetch/errors.ts:164-211), on a 200 that carries a
  rate-limit-remaining 0 header ("Rate limited: ...", index.ts:375-388, 712-714) and on a timeout ("Request
  timed out after <ms> ms", index.ts:355, 804). A thrown error keeps no response headers, so those calls
  have no correlation id. A failure after the gateway committed a slow-path 200 stream arrives in-band as a
  data-only error chunk (OmniRoute@dd6e9607e:open-sse/utils/earlyStreamKeepalive.ts:664-685), which the
  transform reports as sse_error_event with the correlation id; only call_logs shows whether it was a 429.
- Scores. li26's own eval_arm.parse_items and analyze.filing_scores rescore every returned output; the
  assertion's namedScores must agree. A call without output scores as filing_scores(gold, None), li26's rule
  for a call that returned nothing usable.
- Quality. Per filing, TP/FP/FN are summed over repeats; micro-F1 comes from the summed counts (li26
  analyze.micro_f1), never from an average of filing F1. The difference is B - A, B being cx/gpt-6-astra-max.
- Statistics (scipy 1.18.1, scipy/stats/_resampling.py): bootstrap at :300 with paired=True, the filing as the
  resampling unit, method="percentile", alternative="greater" and confidence_level=0.95, so the lower end is
  the 5th percentile and the upper end is +inf (:651-683), n_resamples=10000 and a seeded numpy Generator as
  rng; permutation_test at :1679 with permutation_type="samples" as the secondary check. Each filing's two
  arms are rows of one count table and the samples carry those row indices, which stay integers (:202,
  :225-230, :1570-1604), so resampling or swapping a filing moves both arms' counts together.
- Holm (statsmodels 0.15.0 statsmodels/stats/multitest.py:99, multipletests(method="holm")) applies only to a
  family of roles; R02 has one role, so it is recorded as not applied.
- Costs come from the provider's own usage fields kept in metadata.r02.usage, not promptfoo's
  tokenUsage.cached, which counts promptfoo's cache hits (src/providers/openai/util.ts:998-1044). One call
  processes one filing once, so the mean per call is the cost per filing. completion_tokens is reasoning plus
  output; visible output is completion minus completion_tokens_details.reasoning_tokens. The gateway's
  Responses-to-chat translator writes completion_tokens_details only when reasoning tokens are above 0 and
  prompt_tokens_details only when cache reads are above 0 (OmniRoute@dd6e9607e:open-sse/translator/response/
  openai-responses.ts:1403-1419), so on a call that returned usage an absent detail is 0.
- Effective effort. The primary measure is the client-observed reasoning_tokens per call; completion_tokens
  is a second view. Both use the same paired filing bootstrap and permutation test, one-sided for B above A.
  A zero on one call is not a defect (about 14% of max-effort turns return 0 reasoning tokens as model
  behaviour, as relayed by the coordinator from token-save-practice-gpt6, 2026-09-27; not measured here).
  call_logs effort columns are a secondary check: they are filled only when the response carried encrypted
  reasoning (OmniRoute@dd6e9607e:src/lib/usage/callLogs.ts:646-653), so a NULL is no observation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import platform
import statistics
import sys

HERE = Path(__file__).resolve().parent
LI26 = HERE.parent / "local-inference-latest-20260926"
ARM_LABELS = {"r02-A": "A", "r02-B": "B"}
ERROR = 2
TRANSFORM_ERRORS = ("sse_error_event", "malformed_sse_chunks", "missing_terminal_chunk", "missing_usage",
                    "not_an_sse_stream")
USAGE_KEYS = ("prompt", "completion", "reasoning", "cached", "visible_output", "uncached_input")
SEED = 20260927
RESAMPLES = 10000
CONFIDENCE = 0.95
MARGIN = 0.02
ROLES = ("fw-chat-completions",)
RULE = ("adopt_max if the one-sided 95% lower bound of micro-F1(B) - micro-F1(A) is above 0; otherwise "
        "keep_medium if the lower bound of micro-F1(A) - micro-F1(B) is at least -0.02 and A's mean completion "
        "(reasoning plus output) tokens per filing are below B's; otherwise inconclusive, and B is not adopted")

_ANALYZE = []


def li26():
    """li26's analyze.py, which loads its eval_arm.py (analyze.py:27-29)."""
    if not _ANALYZE:
        spec = importlib.util.spec_from_file_location("r02_analysis_li26_analyze", LI26 / "analyze.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ANALYZE.append(module)
    return _ANALYZE[0]


def result_rows(data):
    return data["results"]["results"]


def r02_metadata(row):
    response = row.get("response") or {}
    return (response.get("metadata") or {}).get("r02") or (row.get("metadata") or {}).get("r02") or {}


def error_kind(row):
    """None for a graded call; otherwise the class of the provider error."""
    if row.get("failureReason") != ERROR:
        return None
    message = row.get("error") or ""
    if message.startswith("http_status_"):
        return "http_" + message[len("http_status_"):].split(":", 1)[0]
    for prefix in TRANSFORM_ERRORS:
        if message.startswith(prefix):
            return prefix
    if "HTTP 429" in message:
        return "http_429"
    if "Rate limited: " in message:
        return "rate_limit_header"
    if "timed out" in message:
        return "timeout"
    return "other"


def finite(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def usage_fields(usage):
    """Token fields of one call; every field is None when the call returned no usage."""
    if not isinstance(usage, dict):
        return {**dict.fromkeys(USAGE_KEYS), "reasoning_reported": False, "cached_reported": False}
    prompt = finite(usage.get("prompt_tokens"))
    completion = finite(usage.get("completion_tokens"))
    reported_reasoning = finite((usage.get("completion_tokens_details") or {}).get("reasoning_tokens"))
    reported_cached = finite((usage.get("prompt_tokens_details") or {}).get("cached_tokens"))
    reasoning = 0 if reported_reasoning is None else reported_reasoning
    cached = 0 if reported_cached is None else reported_cached
    return {"prompt": prompt, "completion": completion, "reasoning": reasoning, "cached": cached,
            "visible_output": None if completion is None else completion - reasoning,
            "uncached_input": None if prompt is None else prompt - cached,
            "reasoning_reported": reported_reasoning is not None, "cached_reported": reported_cached is not None}


def call_record(row, run):
    """One call: arm, filing, counts from li26's rescoring, status, tokens, latency and correlation id."""
    analyze = li26()
    arm = ARM_LABELS[row["provider"]["label"]]
    variables = row["vars"]
    gold = json.loads(variables["labels_json"])
    kind = error_kind(row)
    response = row.get("response") or {}
    problems = []
    if kind is None:
        predicted, status = analyze.eval_arm.parse_items(response.get("output"))
        scores = analyze.filing_scores(gold, predicted)
        named = row.get("namedScores") or {}
        if (named.get("tp"), named.get("fp"), named.get("fn")) != (scores["tp"], scores["fp"], scores["fn"]) or \
                named.get(f"status_{status}") != 1:
            problems.append("assertion scores differ from li26 rescoring")
        if named.get("prompt_ok") != 1:
            problems.append("prompt differs from the recorded li26 prompt")
    else:
        status = "error"
        scores = analyze.filing_scores(gold, None)
    meta = r02_metadata(row)
    return {"run": run, "arm": arm, "test_idx": row["testIdx"], "accession": variables["accession"],
            "tp": scores["tp"], "fp": scores["fp"], "fn": scores["fn"], "status": status, "error_kind": kind,
            "latency_ms": finite(row.get("latencyMs")), "usage": usage_fields(meta.get("usage")),
            "correlation_id": meta.get("correlation_id"), "problems": problems}


def pair_calls(runs, repeats):
    """Pair A and B on (run, testIdx); the repeat is the rank of the testIdx among the filing's."""
    problems, pairs = [], []
    for run, calls in runs.items():
        by_step = {}
        for call in calls:
            slot = by_step.setdefault(call["test_idx"], {})
            if call["arm"] in slot:
                problems.append(f"{run}: two {call['arm']} calls at testIdx {call['test_idx']}")
            slot[call["arm"]] = call
        steps_by_filing = {}
        for step, slot in sorted(by_step.items()):
            if set(slot) != {"A", "B"}:
                problems.append(f"{run}: testIdx {step} lacks an arm")
                continue
            if slot["A"]["accession"] != slot["B"]["accession"]:
                problems.append(f"{run}: testIdx {step} pairs different filings")
                continue
            steps_by_filing.setdefault(slot["A"]["accession"], []).append(step)
        for accession, steps in sorted(steps_by_filing.items()):
            if len(steps) != repeats:
                problems.append(f"{run}: {accession} has {len(steps)} complete repeats, expected {repeats}")
            for repeat, step in enumerate(sorted(steps)):
                pairs.append({"run": run, "accession": accession, "repeat": repeat,
                              "A": by_step[step]["A"], "B": by_step[step]["B"]})
    accessions = [{pair["accession"] for pair in pairs if pair["run"] == run} for run in runs]
    if len(accessions) == 2 and accessions[0] & accessions[1]:
        problems.append("a filing appears in both runs")
    return pairs, problems


def filing_table(pairs):
    """Per filing, TP/FP/FN summed over repeats, for each arm, in accession order."""
    filings = sorted({pair["accession"] for pair in pairs})
    sums = {accession: {"A": [0, 0, 0], "B": [0, 0, 0]} for accession in filings}
    for pair in pairs:
        for arm in ("A", "B"):
            for index, key in enumerate(("tp", "fp", "fn")):
                sums[pair["accession"]][arm][index] += pair[arm][key]
    return filings, [sums[accession]["A"] for accession in filings], [sums[accession]["B"] for accession in filings]


def filing_means(pairs, key):
    """Per filing, each arm's mean of a usage field over the repeats that returned usage; filings where an arm
    has no such repeat are left out and counted."""
    values = {}
    for pair in pairs:
        for arm in ("A", "B"):
            value = pair[arm]["usage"][key]
            if value is not None:
                values.setdefault(pair["accession"], {"A": [], "B": []})[arm].append(value)
    filings = sorted(accession for accession, arms in values.items() if arms["A"] and arms["B"])
    left_out = len({pair["accession"] for pair in pairs}) - len(filings)
    return ([statistics.fmean(values[accession]["A"]) for accession in filings],
            [statistics.fmean(values[accession]["B"]) for accession in filings], left_out)


def micro_f1(counts):
    """li26's micro-F1 from summed counts (analyze.micro_f1)."""
    return li26().micro_f1([tuple(row) for row in counts])


def decide(lower_b_minus_a, lower_a_minus_b, completion_a, completion_b, margin=MARGIN):
    """The preregistered rule (RULE)."""
    if lower_b_minus_a > 0:
        return "adopt_max"
    if lower_a_minus_b >= -margin and completion_a is not None and completion_b is not None and \
            completion_a < completion_b:
        return "keep_medium"
    return "inconclusive"


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.fmean(values) if values else None


def distribution(values, np):
    values = [value for value in values if value is not None]
    if not values:
        return {"n": 0}
    return {"n": len(values), "mean": statistics.fmean(values), "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95, method="linear")),
            "zero_share": sum(value == 0 for value in values) / len(values)}


def arm_summary(calls, np):
    latencies = [call["latency_ms"] for call in calls if call["latency_ms"] is not None]
    usage = [call["usage"] for call in calls]
    returned = [entry for entry in usage if entry["prompt"] is not None]
    prompt_total = sum(entry["prompt"] for entry in returned)
    errors = Counter(call["error_kind"] for call in calls if call["error_kind"])
    return {
        "calls": len(calls),
        "status": dict(sorted(Counter(call["status"] for call in calls).items())),
        "strict_schema_validity": sum(call["status"] == "valid" for call in calls) / len(calls) if calls else None,
        "errors": dict(sorted(errors.items())),
        "timeouts": errors.get("timeout", 0),
        "http_429_client": errors.get("http_429", 0),
        "latency_ms": {"p50": float(np.percentile(latencies, 50, method="linear")) if latencies else None,
                       "p95": float(np.percentile(latencies, 95, method="linear")) if latencies else None,
                       "n": len(latencies)},
        "tokens_per_filing": {key: mean(entry[key] for entry in usage) for key in USAGE_KEYS},
        "calls_with_usage": len(returned),
        "calls_with_details": {"reasoning_tokens": sum(entry["reasoning_reported"] for entry in usage),
                               "cached_tokens": sum(entry["cached_reported"] for entry in usage)},
        "cached_input_share": sum(entry["cached"] for entry in returned) / prompt_total if prompt_total else None,
        "reasoning_tokens": distribution([entry["reasoning"] for entry in usage], np),
        "completion_tokens": distribution([entry["completion"] for entry in usage], np),
    }


def call_log_summary(call_logs, calls):
    """Status and effort per arm from call_logs rows joined on the correlation id. A NULL effort column is no
    observation, never "no effort"."""
    rows = {}
    for entry in call_logs.values():
        for row in entry.get("matched_rows", []):
            rows.setdefault(row["correlation_id"], []).append(row)
    report = {}
    for arm in ("A", "B"):
        arm_calls = [call for call in calls if call["arm"] == arm]
        ids = [call["correlation_id"] for call in arm_calls if call["correlation_id"]]
        matched = [row for identifier in ids for row in rows.get(identifier, [])]
        report[arm] = {
            "calls_with_id": len(ids),
            "calls_without_id": len(arm_calls) - len(ids),
            "ids_matched": sum(identifier in rows for identifier in ids),
            "rows": len(matched),
            "status": dict(sorted(Counter(str(row["status"]) for row in matched).items())),
            "http_429_rows": sum(1 for row in matched if row["status"] == 429),
            "model": dict(sorted(Counter(str(row["model"]) for row in matched).items())),
            "effort_observed": {
                column: dict(sorted(Counter(row[f"reasoning_effort_{column}"] for row in matched
                                            if row[f"reasoning_effort_{column}"] is not None).items()))
                for column in ("requested", "upstream")},
            "effort_not_observed_rows": {column: sum(row[f"reasoning_effort_{column}"] is None for row in matched)
                                         for column in ("requested", "upstream")},
        }
    return report


def paired_tests(sample_a, sample_b, statistic, np, stats):
    """The preregistered paired bootstrap (both one-sided bounds) and the samples permutation test."""
    settings = {"paired": True, "vectorized": True, "n_resamples": RESAMPLES, "method": "percentile",
                "confidence_level": CONFIDENCE, "alternative": "greater"}

    def reverse(first, second, axis=-1):
        return -statistic(first, second, axis=axis)

    def number(value):
        return float(value) + 0.0  # reports 0.0 rather than -0.0

    b_minus_a = stats.bootstrap((sample_a, sample_b), statistic, rng=np.random.default_rng(SEED), **settings)
    a_minus_b = stats.bootstrap((sample_a, sample_b), reverse, rng=np.random.default_rng(SEED), **settings)
    permutation = stats.permutation_test((sample_a, sample_b), statistic, permutation_type="samples",
                                         vectorized=True, n_resamples=RESAMPLES, alternative="greater",
                                         rng=np.random.default_rng(SEED))
    return {
        "b_minus_a": {"point": number(statistic(sample_a, sample_b)),
                      "lower_one_sided_95": number(b_minus_a.confidence_interval.low),
                      "standard_error": number(b_minus_a.standard_error)},
        "a_minus_b": {"point": number(reverse(sample_a, sample_b)),
                      "lower_one_sided_95": number(a_minus_b.confidence_interval.low)},
        "permutation_b_minus_a": {"statistic": number(permutation.statistic),
                                  "p_value_greater": number(permutation.pvalue)},
    }


def settings_record():
    return {"bootstrap": {"paired": True, "vectorized": True, "n_resamples": RESAMPLES, "method": "percentile",
                          "confidence_level": CONFIDENCE, "alternative": "greater",
                          "rng": f"numpy.random.default_rng({SEED})", "resampling_unit": "filing (both arms together)"},
            "permutation_test": {"permutation_type": "samples", "n_resamples": RESAMPLES, "alternative": "greater",
                                 "rng": f"numpy.random.default_rng({SEED})"}}


def quality_tests(table_a, table_b):
    import numpy as np
    from scipy import stats

    table = np.asarray(table_a + table_b, dtype=float)
    n = len(table_a)

    def f1(counts):
        tp, fp, fn = counts[..., 0], counts[..., 1], counts[..., 2]
        denominator = 2 * tp + fp + fn
        return np.where(denominator > 0, 2 * tp / np.where(denominator > 0, denominator, 1), 1.0)

    def micro_f1_difference(first, second, axis=-1):
        first = np.moveaxis(np.asarray(first), axis, -1)
        second = np.moveaxis(np.asarray(second), axis, -1)
        return f1(table[second].sum(axis=-2)) - f1(table[first].sum(axis=-2))

    return {"filings": n, **paired_tests(np.arange(n), np.arange(n, 2 * n), micro_f1_difference, np, stats),
            "settings": settings_record()}


def effort_tests(pairs):
    """Effective effort: per-filing mean tokens over repeats, B - A, for reasoning and completion tokens."""
    import numpy as np
    from scipy import stats

    def mean_difference(first, second, axis=-1):
        return np.mean(second, axis=axis) - np.mean(first, axis=axis)

    report = {"primary": "reasoning_tokens", "statistic": "mean over filings of the per-filing mean, B - A",
              "settings": settings_record()}
    for key in ("reasoning", "completion"):
        sample_a, sample_b, left_out = filing_means(pairs, key)
        entry = {"filings": len(sample_a), "filings_left_out": left_out}
        if len(sample_a) < 2:
            entry["computed"] = False
        else:
            entry.update(paired_tests(np.asarray(sample_a, dtype=float), np.asarray(sample_b, dtype=float),
                                      mean_difference, np, stats))
        report[f"{key}_tokens"] = entry
    return report


def installed(distribution_name):
    try:
        return importlib.metadata.version(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def holm(p_values):
    if len(p_values) < 2:
        return {"applied": False, "roles": len(p_values),
                "reason": "one role; Holm applies only to a family of roles"}
    from statsmodels.stats.multitest import multipletests
    reject, corrected, _, _ = multipletests(list(p_values.values()), alpha=1 - CONFIDENCE, method="holm")
    return {"applied": True, "roles": {role: {"p_holm": float(p), "reject": bool(r)}
                                       for role, p, r in zip(p_values, corrected, reject)}}


def analyze(results_by_run, repeats, call_logs=None):
    import numpy as np

    runs = {run: [call_record(row, run) for row in result_rows(data)] for run, data in results_by_run.items()}
    calls = [call for run_calls in runs.values() for call in run_calls]
    pairs, problems = pair_calls(runs, repeats)
    problems += sorted({f"{call['run']} {call['arm']} {call['accession']}: {problem}"
                        for call in calls for problem in call["problems"]})
    filings, table_a, table_b = filing_table(pairs)
    tests = quality_tests(table_a, table_b)
    arms = {arm: arm_summary([pair[arm] for pair in pairs], np) for arm in ("A", "B")}
    completion = {arm: arms[arm]["tokens_per_filing"]["completion"] for arm in ("A", "B")}
    report = {
        "status": "analysis" if not problems else "analysis-with-problems",
        "problems": problems,
        "pairs": len(pairs), "filings": len(filings), "repeats": repeats,
        "runs": {run: {"calls": len(run_calls), "eval_id": results_by_run[run].get("evalId")}
                 for run, run_calls in runs.items()},
        "micro_f1": {"A": micro_f1(table_a), "B": micro_f1(table_b)},
        "tests": tests,
        "holm": holm({ROLES[0]: tests["permutation_b_minus_a"]["p_value_greater"]}),
        "effort": effort_tests(pairs),
        "arms": arms,
        "decision": {"rule": RULE, "margin": MARGIN, "completion_tokens_per_filing": completion,
                     "result": decide(tests["b_minus_a"]["lower_one_sided_95"],
                                      tests["a_minus_b"]["lower_one_sided_95"], completion["A"], completion["B"])},
        "versions": {"python": platform.python_version(), "numpy": installed("numpy"), "scipy": installed("scipy"),
                     "statsmodels": installed("statsmodels")},
    }
    if call_logs is not None:
        report["call_logs"] = call_log_summary(call_logs, calls)
    return report


def correlation_ids(paths):
    ids = {"A": [], "B": []}
    for path in paths:
        for row in result_rows(json.loads(Path(path).read_text())):
            identifier = r02_metadata(row).get("correlation_id")
            if identifier:
                ids[ARM_LABELS[row["provider"]["label"]]].append(identifier)
    return ids


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    ids = commands.add_parser("ids", help="correlation ids per arm, for call_logs_by_correlation.py")
    ids.add_argument("--results", nargs="+", required=True)
    run = commands.add_parser("analyze", help="paired statistics and the preregistered decision")
    run.add_argument("--results-ab", required=True)
    run.add_argument("--results-ba", required=True)
    run.add_argument("--call-logs")
    run.add_argument("--repeats", type=int, default=3)
    run.add_argument("--out")
    args = parser.parse_args(argv)
    if args.command == "ids":
        print(json.dumps(correlation_ids(args.results), indent=2))
        return 0
    results = {"ab": json.loads(Path(args.results_ab).read_text()), "ba": json.loads(Path(args.results_ba).read_text())}
    call_logs = json.loads(Path(args.call_logs).read_text()) if args.call_logs else None
    text = json.dumps(analyze(results, args.repeats, call_logs), indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
