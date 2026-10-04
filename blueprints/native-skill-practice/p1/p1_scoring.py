#!/usr/bin/env python3
"""P1 scoring: the frozen rules of the Jev and TypeSafe design report r1, sections 5.0 and 5.1.

Upstream implementations, pinned in requirements-scoring.lock (numpy 2.5.3, scipy 1.18.1,
scikit-learn 1.9.1):
- paired bootstrap: scipy.stats.bootstrap(paired=True, vectorized=False, n_resamples=10000,
  rng=numpy.random.default_rng(20261003)), percentile method, two-sided 95%; any best-of
  selection happens inside the statistic, so inside every resample;
- exact McNemar: scipy.stats.binomtest(b, b + c, 0.5) on the discordant pairs, which is the
  exact (binomial) form of McNemar's test;
- Wilson bounds: scipy.stats.binomtest(k, n).proportion_ci(0.95, method="wilson");
- balanced accuracy, confusion matrices, Cohen's kappa and the Brier score: sklearn.metrics
  (multiclass brier_score_loss, scale_by_half=False, columns in sklearn's alphabetical label order);
- ECE: 15 equal-width bins over top-label confidence, bin (lower, upper], weights by bin share
  (Guo et al. 2017, arXiv:1706.04599, eq. 3; gpleiss/temperature_scaling@ce1154ec,
  temperature_scaling.py:105-127). Neither scipy nor scikit-learn ships it.

Nothing here calls a model or a service. Input calls are normalized records; calls_from_promptfoo
maps a promptfoo 0.123.1 --output file onto them by the explicit case_id and repeat_index vars and
the provider label, never by row order.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, cohen_kappa_score, confusion_matrix

SEED = 20261003
N_RESAMPLES = 10_000
CONFIDENCE_LEVEL = 0.95
BOOTSTRAP_METHOD = "percentile"
LABELS = ("supported", "contradicted", "insufficient")
NON_SUPPORTED = ("contradicted", "insufficient")
CODE = {label: index for index, label in enumerate(LABELS)}
ERROR_CODE = -1
CLOSE_THRESHOLD = 0.80
ECE_BINS = 15
JEV_MODEL = "jev-1.13.0"
J_ORDERS = (0, 1, 2)
J_REPEATS = (0, 1, 2)
# Arm L scores one premise-hypothesis pair and has no option order, so rule (d)'s order-flip part does
# not apply to it (README "Open decisions"); its repeat disagreement is measured over repeated L calls,
# three per case (p1_casepack.FROZEN_LOCAL_REPEATS, `tests --local-repeats 3`).
NOT_APPLICABLE = "not_applicable"
L_REPEATS = (0, 1, 2)
CANARY_CASES = 10           # section 5.0: stop if the A1 canary flips more than 2 of 10 cases
# promptfooconfig.yaml's run commands: J-o0, J-o1 and J-o2 on the jev rows, O, S and G on the native rows,
# L on the local rows; render rows reach no arm. Each (arm, order) is one call per row.
ARM_GROUPS = {"jev": tuple(("J", order) for order in J_ORDERS), "native": (("O", 0), ("S", 0), ("G", 0)),
              "local": (("L", 0),)}
# The suffix p1/response-model.cjs adds when ../response.cjs refuses a response.
MODEL_IN_ERROR = re.compile(r'\[response model: (null|"(?:[^"\\]|\\.)*")\]')

# Section 5.1 rules (a)-(e) and the reject rule, as written. Rule (a)'s Wilson bound is compared
# at WILSON_DECIMALS decimals: unrounded, 0 of 60 gives 0.0602 > 0.060 (0 of 61 gives 0.0592),
# so the text's "at least 60 ... so the upper 95% Wilson bound is at most 0.060" holds only at
# three decimals. The coordinator decides before freeze; see README "Open decisions".
WILSON_DECIMALS = 3
RULES = {
    "a": {"false_closes": 0, "min_nonsupported": 60, "wilson_upper_max": 0.060, "wilson_decimals": WILSON_DECIMALS},
    "b": {"closure_rate_min": 0.25},
    "c": {"ba_difference_lower_min": -0.03},
    "d": {"order_flip_rate_max": 0.05, "repeat_disagreement_rate_max": 0.03},
    "e": {"median_j3_decision_latency_s_max": 0.5},
    "reject": {"false_closes_min": 2, "order_flip_rate_above": 0.10},
    "stop": {"service_error_share_above": 0.05, "canary_flips_above": 2, "model": JEV_MODEL},
}


# --------------------------------------------------------------------------- statistics primitives


def wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    if trials <= 0:
        return (math.nan, math.nan)
    interval = stats.binomtest(successes, trials).proportion_ci(confidence_level=CONFIDENCE_LEVEL, method="wilson")
    return (float(interval.low), float(interval.high))


def mcnemar_exact(truth, first, second) -> dict:
    """Exact McNemar test of two paired classifiers: binomial test of the discordant pairs at p=0.5."""
    truth, first, second = (np.asarray(item) for item in (truth, first, second))
    first_right, second_right = first == truth, second == truth
    only_first = int(np.sum(first_right & ~second_right))
    only_second = int(np.sum(~first_right & second_right))
    discordant = only_first + only_second
    p_value = float(stats.binomtest(only_first, discordant, 0.5).pvalue) if discordant else 1.0
    return {"only_first_correct": only_first, "only_second_correct": only_second, "p_value": p_value}


def balanced_accuracy(truth, predicted) -> float:
    """sklearn balanced accuracy; an error code counts as a wrong answer, never as a class."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
        return float(balanced_accuracy_score(np.asarray(truth), np.asarray(predicted)))


def paired_bootstrap(statistic, samples: list[np.ndarray]) -> dict:
    """scipy paired bootstrap over cases; the statistic sees one resample of every array at once."""
    result = stats.bootstrap(tuple(samples), statistic, paired=True, vectorized=False,
                             n_resamples=N_RESAMPLES, confidence_level=CONFIDENCE_LEVEL,
                             method=BOOTSTRAP_METHOD, rng=np.random.default_rng(SEED))
    return {"point": float(statistic(*samples)), "low": float(result.confidence_interval.low),
            "high": float(result.confidence_interval.high), "standard_error": float(result.standard_error)}


def ba_difference(truth, first, second) -> float:
    return balanced_accuracy(truth, first) - balanced_accuracy(truth, second)


def ba_minus_best_of(truth, first, native_one, native_two) -> float:
    """BA(first) minus the higher BA of the two native arms, chosen on this (re)sample."""
    return balanced_accuracy(truth, first) - max(balanced_accuracy(truth, native_one),
                                                 balanced_accuracy(truth, native_two))


def multiclass_brier(truth_labels: list[str], probability_rows: list[dict]) -> float:
    columns = sorted(LABELS)    # sklearn assumes alphabetical column order (LabelBinarizer)
    matrix = np.array([[row[label] for label in columns] for row in probability_rows], dtype=float)
    return float(brier_score_loss(list(truth_labels), matrix, labels=columns, scale_by_half=False))


def expected_calibration_error(confidences, correct, bins: int = ECE_BINS) -> dict:
    """Top-label ECE (Guo et al. 2017): sum over bins of |accuracy - mean confidence| x bin share."""
    confidences = np.asarray(confidences, dtype=float)
    correct = np.asarray(correct, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(confidences)
    ece, table = 0.0, []
    for lower, upper in zip(edges[:-1], edges[1:]):
        inside = (confidences > lower) & (confidences <= upper)
        count = int(inside.sum())
        if count:
            accuracy = float(correct[inside].mean())
            confidence = float(confidences[inside].mean())
            ece += abs(confidence - accuracy) * count / total
            table.append({"lower": float(lower), "upper": float(upper), "count": count,
                          "accuracy": accuracy, "mean_confidence": confidence})
    return {"ece": ece if total else math.nan, "bins": bins, "n": total, "table": table}


# --------------------------------------------------------------------------- answers per arm


def plurality(answers: list[str], probability_rows: list[dict | None]) -> tuple[str, float | None]:
    """Most frequent answer; a tie goes to the highest mean probability, then the label order.
    Confidence is the chosen option's mean probability over the same calls."""
    counts = Counter(answers)
    top = max(counts.values())
    tied = [label for label in LABELS if counts.get(label) == top]
    usable = [row for row in probability_rows if row]

    def mean_probability(label):
        return sum(row[label] for row in usable) / len(usable) if usable else None

    if len(tied) > 1 and usable:
        best = max(mean_probability(label) for label in tied)
        tied = [label for label in tied if mean_probability(label) == best]
    chosen = tied[0]
    return chosen, mean_probability(chosen)


def mean_probabilities(rows: list[dict]) -> dict | None:
    if not rows or any(row is None for row in rows):
        return None
    return {label: sum(row[label] for row in rows) / len(rows) for label in LABELS}


def index_calls(calls: list[dict], arm: str) -> dict[tuple[str, int, int], dict]:
    table = {}
    for call in calls:
        if call["arm"] != arm:
            continue
        key = (call["case_id"], int(call.get("order", 0)), int(call.get("repeat", 0)))
        if key in table:
            raise ValueError(f"duplicate {arm} call {key}")
        table[key] = call
    return table


def answered(call: dict | None) -> bool:
    return bool(call) and call.get("answer") in LABELS and not call.get("error")


def jev_views(calls: list[dict], case_ids: list[str]) -> dict:
    """J-1, J-3 (deployed), J-9 and the order-level answers, per case. J-3 and J-9 need every call."""
    table = index_calls(calls, "J")
    views = {}
    for case in case_ids:
        grid = {(order, repeat): table.get((case, order, repeat)) for order in J_ORDERS for repeat in J_REPEATS}
        first = grid[(0, 0)]
        view = {"J1": None, "J3": None, "J9": None, "order_answers": {}, "j3_latency_s": None}
        if answered(first):
            view["J1"] = {"answer": first["answer"], "confidence": first.get("confidence"),
                          "probabilities": first.get("probabilities")}
        deployed = [grid[(order, 0)] for order in J_ORDERS]
        if all(answered(call) for call in deployed):
            answer, confidence = plurality([call["answer"] for call in deployed],
                                           [call.get("probabilities") for call in deployed])
            view["J3"] = {"answer": answer, "confidence": confidence,
                          "probabilities": mean_probabilities([call.get("probabilities") for call in deployed])}
            latencies = [call.get("latency_s") for call in deployed]
            if all(isinstance(value, (int, float)) for value in latencies):
                # Section 5.1 "Definitions": a J-3 decision's latency is "the wall time of three concurrent
                # calls", the deployed configuration. The J run is serialized (--max-concurrency 1), so each
                # call's latency is uncontended and the slowest of the three is that wall time, not their
                # serial sum (README "Open decisions" 8 keeps this estimate a choice to confirm at freeze).
                view["j3_latency_s"] = max(latencies)
        every = list(grid.values())
        if all(answered(call) for call in every):
            answer, confidence = plurality([call["answer"] for call in every], [call.get("probabilities") for call in every])
            view["J9"] = {"answer": answer, "confidence": confidence,
                          "probabilities": mean_probabilities([call.get("probabilities") for call in every])}
        for order in J_ORDERS:
            repeats = [grid[(order, repeat)] for repeat in J_REPEATS]
            if all(answered(call) for call in repeats):
                view["order_answers"][order] = plurality([call["answer"] for call in repeats],
                                                         [call.get("probabilities") for call in repeats])[0]
        views[case] = view
    return views


def bounded_rate(events: int, incomplete: int, denominator: int) -> dict:
    """A rate over the frozen denominator. An incomplete unit (a failed call removed an answer it needs)
    is counted both ways: rate_low as no event, rate_high as an event. Rule (d) must hold at rate_high
    and the reject rule fires at rate_low, so a missing call never helps either verdict (README "Open
    decisions"). With nothing incomplete both bounds equal the frozen definition, and so does rate."""
    if not denominator:
        return {"rate": math.nan, "rate_low": math.nan, "rate_high": math.nan}
    return {"rate": events / denominator if not incomplete else None,
            "rate_low": events / denominator, "rate_high": (events + incomplete) / denominator}


def order_flip_rate(views: dict) -> dict:
    """Order flip: a case whose three order-level answers (each the plurality of that order's three
    repeats) are not all equal; the rate is over all cases (section 5.1: "rate over 120 cases")."""
    complete = [view["order_answers"] for view in views.values() if len(view["order_answers"]) == len(J_ORDERS)]
    flips = sum(1 for answers in complete if len(set(answers.values())) > 1)
    incomplete = len(views) - len(complete)
    return {"flips": flips, "cases": len(views), "complete": len(complete), "incomplete": incomplete,
            **bounded_rate(flips, incomplete, len(views))}


def repeat_disagreement_rate(calls: list[dict], case_ids: list[str]) -> dict:
    """Repeat disagreement: a (case, order) pair whose three repeats are not all equal; the rate is over
    all pairs, every case times every order (section 5.1: "rate over 360 pairs")."""
    table = index_calls(calls, "J")
    complete = disagreements = incomplete = 0
    for case in case_ids:
        for order in J_ORDERS:
            repeats = [table.get((case, order, repeat)) for repeat in J_REPEATS]
            if not all(answered(call) for call in repeats):
                incomplete += 1
                continue
            complete += 1
            disagreements += len({call["answer"] for call in repeats}) > 1
    pairs = len(case_ids) * len(J_ORDERS)
    return {"disagreements": disagreements, "pairs": pairs, "complete": complete, "incomplete": incomplete,
            **bounded_rate(disagreements, incomplete, pairs)}


def single_arm_view(calls: list[dict], arm: str, case_ids: list[str]) -> dict:
    table = index_calls(calls, arm)
    views = {}
    for case in case_ids:
        call = table.get((case, 0, 0))
        views[case] = {"answer": call["answer"], "confidence": call.get("confidence"),
                       "probabilities": call.get("probabilities")} if answered(call) else None
    return views


DIGIT = re.compile(r"\d")     # the same pattern as p1_casepack.DIGIT, the numeric-or-date stratum


def has_digit(claim: str) -> bool:
    return DIGIT.search(claim) is not None


def cascade(case_ids: list[str], claims: dict[str, str], closer: dict, opus: dict) -> dict:
    """Arm C: code sends every claim with a digit to O; otherwise the closer closes "supported" at
    mean confidence >= 0.80 and everything else goes to O (section 5.1, routing rule)."""
    routed = {}
    for case in case_ids:
        if has_digit(claims[case]):
            route = "digit_to_opus"
        else:
            view = closer.get(case)
            closes = bool(view) and view["answer"] == "supported" and (view.get("confidence") or 0.0) >= CLOSE_THRESHOLD
            route = "closed" if closes else "escalated"
        answer = "supported" if route == "closed" else (opus[case]["answer"] if opus.get(case) else None)
        routed[case] = {"route": route, "answer": answer}
    return routed


def codes(answers: list[str | None]) -> np.ndarray:
    return np.array([CODE.get(answer, ERROR_CODE) for answer in answers], dtype=int)


# --------------------------------------------------------------------------- decision rules


def wilson_bound_passes(upper: float) -> bool:
    return not math.isnan(upper) and round(upper, WILSON_DECIMALS) <= RULES["a"]["wilson_upper_max"]


def rate_bounds(value) -> tuple:
    """A rate, or (rate_low, rate_high) bounds when some units are incomplete (bounded_rate)."""
    return tuple(value) if isinstance(value, (tuple, list)) else (value, value)


def decide(false_closes: int, nonsupported: int, closure_rate: float, ba_difference_lower: float,
           order_flip, repeat_disagreement, median_latency_s: float | None) -> dict:
    """Section 5.1: adopt C for S2 only if (a)-(e) all hold; reject J for S2 on two or more false
    closes or order flips above 10%; otherwise inconclusive (including fewer than 60 non-supported).
    order_flip and repeat_disagreement are rates or (low, high) bounds: (d) uses the high bounds, the
    reject rule the low bound."""
    upper = wilson_interval(false_closes, nonsupported)[1] if nonsupported else math.nan
    flip_low, flip_high = rate_bounds(order_flip)
    repeat_high = rate_bounds(repeat_disagreement)[1]

    def ok(value):
        return value is not None and not (isinstance(value, float) and math.isnan(value))

    rules = {
        "a": false_closes == RULES["a"]["false_closes"] and nonsupported >= RULES["a"]["min_nonsupported"]
        and wilson_bound_passes(upper),
        "b": ok(closure_rate) and closure_rate >= RULES["b"]["closure_rate_min"],
        "c": ok(ba_difference_lower) and ba_difference_lower >= RULES["c"]["ba_difference_lower_min"],
        "d": ok(flip_high) and ok(repeat_high) and flip_high <= RULES["d"]["order_flip_rate_max"]
        and repeat_high <= RULES["d"]["repeat_disagreement_rate_max"],
        "e": ok(median_latency_s) and median_latency_s <= RULES["e"]["median_j3_decision_latency_s_max"],
    }
    if all(rules.values()):
        verdict = "adopt"
    elif false_closes >= RULES["reject"]["false_closes_min"] or (ok(flip_low) and flip_low > RULES["reject"]["order_flip_rate_above"]):
        verdict = "reject"
    else:
        verdict = "inconclusive"
    return {"verdict": verdict, "rules": rules,
            "values": {"false_closes": false_closes, "nonsupported": nonsupported, "wilson_upper": upper,
                       "closure_rate": closure_rate, "ba_difference_lower": ba_difference_lower,
                       "order_flip_rate": order_flip, "repeat_disagreement_rate": repeat_disagreement,
                       "median_j3_decision_latency_s": median_latency_s}}


def prescreen_qualifies(false_closes: int, nonsupported: int, closure_rate: float, ba_difference_lower: float,
                        order_flip, repeat_disagreement) -> dict:
    """Arm L as the private-text closing pre-screen: rules (a)-(d) with L in place of J. order_flip is
    NOT_APPLICABLE for an arm without option orders, which leaves (d) to repeat disagreement alone. A
    rule that was not measured (None) leaves L neither qualified nor failed on it: qualifies is None."""
    outcome = decide(false_closes, nonsupported, closure_rate, ba_difference_lower,
                     0.0 if order_flip == NOT_APPLICABLE else (math.nan if order_flip is None else order_flip),
                     math.nan if repeat_disagreement is None else repeat_disagreement, 0.0)
    rules = {key: outcome["rules"][key] for key in "abc"}
    rules["d"] = None if order_flip is None or repeat_disagreement is None else outcome["rules"]["d"]
    if not all(value is not False for value in rules.values()):
        qualifies = False
    elif any(value is None for value in rules.values()):
        qualifies = None
    else:
        qualifies = True
    values = {key: value for key, value in outcome["values"].items() if key != "median_j3_decision_latency_s"}
    values.update({"order_flip_rate": order_flip, "repeat_disagreement_rate": repeat_disagreement})
    return {"qualifies": qualifies, "rules": rules, "values": values}


def single_arm_repeat_disagreement(calls: list[dict], arm: str, case_ids: list[str],
                                   repeats: tuple[int, ...] = L_REPEATS) -> dict | None:
    """For an arm without option orders (L), each case is one unit over its frozen repeats (three L calls,
    repeat_index 0-2): it disagrees when they are not all equal. The rate is over all cases. A case without
    an answered call at every frozen repeat is incomplete (bounded_rate). The repeat count is the frozen
    one, never the count the run happens to hold: None when no case holds a call at every frozen repeat,
    because the run did not repeat the arm as frozen, so (d) stays open rather than pass on fewer repeats."""
    table = index_calls(calls, arm)
    grids = {case: [table.get((case, 0, repeat)) for repeat in repeats] for case in case_ids}
    if not any(all(call is not None for call in grid) for grid in grids.values()):
        return None
    disagreements = incomplete = 0
    for grid in grids.values():
        if not all(answered(call) for call in grid):
            incomplete += 1
            continue
        disagreements += len({call["answer"] for call in grid}) > 1
    return {"disagreements": disagreements, "pairs": len(case_ids), "repeats": len(repeats), "incomplete": incomplete,
            **bounded_rate(disagreements, incomplete, len(case_ids))}


def attempts_of(call: dict) -> int | None:
    """A call's attempt count when its record carries one; None (unknown) otherwise, never a guess of 1."""
    value = call.get("attempts")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else None


def service_error_shares(calls: list[dict], missing: int = 0) -> dict:
    """Section 5.0: "Stop if service errors exceed 5% of calls ... Any call that needed a resend counts
    toward the 5%." Both readings of "calls" are computed, and the stop fires when either is above 5%:
    - per_call, section 5.1's unit (9 J calls per case, 180 calls per native arm): a scheduled call counts
      when it failed or needed a resend (more than one recorded attempt), once;
    - per_request, where every resend is itself a call: a call with k recorded attempts sent k requests,
      the first k-1 of which were resent, and its last request's outcome is the call's. Per-attempt
      outcomes are not recorded and are not inferred: a resent request counts because the rule counts it.
    A call without an attempt record sent at least one request and an unknown number of resends; it is
    never taken as one attempt. A scheduled call with no result row (missing) has an unknown outcome. Each
    share is therefore a pair of bounds: "low" counts only failures and recorded resends, the share the
    evidence shows, and the stop fires on it; "high" also counts every call whose resends or outcome are
    unknown. per_request has no upper bound once a call's attempts are unknown or a call is missing (None)."""
    attempts = [attempts_of(call) for call in calls]
    failed = [bool(call.get("error")) or call.get("answer") not in LABELS for call in calls]
    scheduled = len(calls) + missing
    events = sum(1 for count, bad in zip(attempts, failed) if bad or (count is not None and count > 1))
    unknown = sum(1 for count, bad in zip(attempts, failed) if count is None and not bad) + missing
    per_call = {"calls": scheduled, "failed_or_resent": events, "unknown": unknown,
                "low": events / scheduled if scheduled else math.nan,
                "high": (events + unknown) / scheduled if scheduled else math.nan}
    requests = sum(1 if count is None else count for count in attempts) + missing
    resent = sum(count - 1 for count in attempts if count is not None)
    attempts_unknown = sum(1 for count in attempts if count is None)
    request_events = resent + sum(failed)
    per_request = {"requests_known": requests, "resent": resent, "failed": sum(failed),
                   "calls_attempts_unknown": attempts_unknown, "missing": missing,
                   "low": request_events / requests if requests else math.nan,
                   "high": request_events / requests if requests and not attempts_unknown and not missing else None}
    return {"per_call": per_call, "per_request": per_request,
            "above": RULES["stop"]["service_error_share_above"], "fires_on": "low"}


def stop_checks(calls: list[dict], canary_flips: int | None, missing: int = 0) -> dict:
    """Section 5.0 stop rules: service errors above 5% of calls (a resend counts; service_error_shares),
    a moved Jev model, or more than 2 of 10 canary flips; and every Jev result must be live, not cached.
    A failed call whose response never reached the contract check has no model (unknown), which is
    not a move; an answered Jev call must carry the pinned model, or its model went unverified."""
    shares = service_error_shares(calls, missing)
    jev = [call for call in calls if call["arm"] == "J"]
    moved = sorted({str(call["model"]) for call in jev if call.get("model") is not None and call["model"] != JEV_MODEL})
    unverified = sum(1 for call in jev if answered(call) and call.get("model") is None)
    not_live = sum(1 for call in jev if not call.get("error") and call.get("inference") != "live")
    reasons = []
    if any(not math.isnan(share["low"]) and share["low"] > shares["above"]
           for share in (shares["per_call"], shares["per_request"])):
        reasons.append("service_errors")
    if moved:
        reasons.append("jev_model_moved")
    if unverified:
        reasons.append("jev_model_unverified")
    if not_live:
        reasons.append("jev_result_not_live")
    if canary_flips is not None and canary_flips > RULES["stop"]["canary_flips_above"]:
        reasons.append("canary_flips")
    return {"stop": bool(reasons), "reasons": reasons, "calls": len(calls), "missing": missing,
            "service_errors": shares, "unexpected_jev_models": moved, "jev_models_unverified": unverified,
            "jev_failed_model_unknown": sum(1 for call in jev if not answered(call) and call.get("model") is None),
            "jev_results_not_live": not_live, "canary_flips": canary_flips}


def operations(calls: list[dict]) -> dict:
    """Section 5.0 "report regardless of outcome": usage, latency, errors, attempts and request IDs per
    arm. Attempts are summed over the calls that record them; the rest are counted as unknown."""
    report = {}
    for arm in sorted({call["arm"] for call in calls}):
        own = [call for call in calls if call["arm"] == arm]
        latencies = [call["latency_s"] for call in own if isinstance(call.get("latency_s"), (int, float))]
        usage: dict[str, float] = {}
        for call in own:
            for key, value in (call.get("usage") or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    usage[key] = usage.get(key, 0) + value
        known = [attempts_of(call) for call in own if attempts_of(call) is not None]
        report[arm] = {"calls": len(own), "errors": sum(1 for call in own if call.get("error") or call.get("answer") not in LABELS),
                       "resent": sum(1 for attempts in known if attempts > 1),
                       "attempts": sum(known), "attempts_unknown": len(own) - len(known),
                       "median_latency_s": statistics.median(latencies) if latencies else None,
                       "request_ids": sum(1 for call in own if call.get("request_id")), "usage": usage}
    return report


def schedule_from_rows(rows: list[dict]) -> set[tuple[str, str, int, int]]:
    """The frozen call schedule: every (arm, case, order, repeat) key the frozen promptfoo test rows (the
    promptfoo_tests role p1_freeze.py --final checks) produce under the arm-group filters (ARM_GROUPS)."""
    schedule = set()
    for row in rows:
        variables = row.get("vars") or {}
        for arm, order in ARM_GROUPS.get((row.get("metadata") or {}).get("arm_group"), ()):
            key = (arm, variables["case_id"], order, int(variables.get("repeat_index", 0)))
            if key in schedule:
                raise ValueError(f"the test rows repeat the call {key}")
            schedule.add(key)
    return schedule


def call_matrix(calls: list[dict], schedule: set) -> dict:
    """The calls against the frozen schedule. A call outside it, or two calls with one key, is refused: the
    calls are not this run's. A scheduled key without a call is missing (a truncated output or a crashed
    run): its outcome is unknown, so it is counted in the stop shares' bounds and the run decides nothing."""
    seen = Counter((call["arm"], call["case_id"], int(call.get("order", 0)), int(call.get("repeat", 0)))
                   for call in calls)
    repeated = sorted(key for key, count in seen.items() if count > 1)
    unexpected = sorted(set(seen) - set(schedule))
    if repeated or unexpected:
        raise ValueError(f"the calls do not match the frozen schedule: {len(unexpected)} unscheduled "
                         f"{unexpected[:3]}, {len(repeated)} repeated {repeated[:3]}")
    missing = sorted(set(schedule) - set(seen))
    return {"expected": len(schedule), "present": len(seen), "missing": len(missing),
            "missing_by_arm": dict(sorted(Counter(key[0] for key in missing).items())),
            "missing_keys": [list(key) for key in missing[:20]]}


def canary_count(value) -> int | None:
    """None (no canary result) or a count of the 10 A1 canary cases that flipped, 0 through 10."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= CANARY_CASES:
        raise ValueError(f"canary flips are a count of the {CANARY_CASES} canary cases, 0 through {CANARY_CASES}")
    return value


# --------------------------------------------------------------------------- report


def score(pack: dict, labels: dict[str, dict], calls: list[dict], schedule: set,
          relabels: dict[str, dict] | None = None, canary_flips: int | None = None) -> dict:
    """Score a run against its frozen schedule (schedule_from_rows). No verdict is issued, and arm L does
    not qualify, while a hold applies: a stop rule fired ("stopped"), a scheduled call has no result
    ("incomplete_call_matrix"), or the A1 canary result is absent ("canary_missing"). The partial results
    stay in the report (section 5.0)."""
    canary_flips = canary_count(canary_flips)
    cases = {case["case_id"]: case for case in pack["cases"]}
    case_ids = sorted(cases)
    unlabelled = [case for case in case_ids if case not in labels]
    if unlabelled:
        raise ValueError(f"unlabelled cases: {unlabelled[:5]}")
    # An unknown label would score as ERROR_CODE and leave the non-supported denominator; refuse it.
    invalid = [case for case in case_ids if not isinstance(labels[case], dict) or labels[case].get("label") not in LABELS]
    invalid += [f"re-label {case}" for case, record in sorted((relabels or {}).items())
                if not isinstance(record, dict) or record.get("label") not in LABELS]
    if invalid:
        raise ValueError(f"labels outside {list(LABELS)}: {invalid[:5]}")
    matrix = call_matrix(calls, schedule)
    truth_labels = [labels[case]["label"] for case in case_ids]
    truth = codes(truth_labels)
    claims = {case: cases[case]["claim"] for case in case_ids}
    nonsupported = sum(label in NON_SUPPORTED for label in truth_labels)

    j = jev_views(calls, case_ids)
    arms = {
        "J1": {case: j[case]["J1"] for case in case_ids},
        "J3": {case: j[case]["J3"] for case in case_ids},
        "J9": {case: j[case]["J9"] for case in case_ids},
    }
    for arm in ("O", "S", "G", "L", "D"):
        if any(call["arm"] == arm for call in calls):
            arms[arm] = single_arm_view(calls, arm, case_ids)
    opus = arms.get("O", {})
    routes = {"C": cascade(case_ids, claims, arms["J3"], opus)}
    if "L" in arms:
        routes["C_L"] = cascade(case_ids, claims, arms["L"], opus)
    answers = {name: [view[case]["answer"] if view.get(case) else None for case in case_ids]
               for name, view in arms.items()}
    for name, routed in routes.items():
        answers[name] = [routed[case]["answer"] for case in case_ids]
    predicted = {name: codes(values) for name, values in answers.items()}

    flips = order_flip_rate(j)
    repeats = repeat_disagreement_rate(calls, case_ids)
    latencies = [j[case]["j3_latency_s"] for case in case_ids if j[case]["j3_latency_s"] is not None]
    median_latency = statistics.median(latencies) if latencies else None

    def primary(routed):
        closed = [case for case in case_ids if routed[case]["route"] == "closed"]
        false = sum(1 for case in closed if labels[case]["label"] in NON_SUPPORTED)
        return {"closed": len(closed), "false_closes": false, "closure_rate": len(closed) / len(case_ids),
                "routes": dict(Counter(routed[case]["route"] for case in case_ids)),
                "wilson_false_close_rate": wilson_interval(false, nonsupported) if nonsupported else None,
                "escalation_rate": 1 - len(closed) / len(case_ids)}

    stop = stop_checks(calls, canary_flips, matrix["missing"])
    holds = (["stopped"] if stop["stop"] else []) + (["incomplete_call_matrix"] if matrix["missing"] else []) \
        + (["canary_missing"] if canary_flips is None else [])
    report = {"schema": "jev-p1-score/1", "frozen": {"seed": SEED, "n_resamples": N_RESAMPLES,
              "confidence_level": CONFIDENCE_LEVEL, "bootstrap_method": BOOTSTRAP_METHOD,
              "close_threshold": CLOSE_THRESHOLD, "ece_bins": ECE_BINS, "rules": RULES},
              "cases": len(case_ids), "nonsupported": nonsupported,
              "label_counts": dict(Counter(truth_labels)), "call_matrix": matrix, "stop": stop, "holds": holds,
              "operations": operations(calls)}
    primary_c = primary(routes["C"])
    report["primary_C"] = primary_c
    if "O" in predicted:
        c_vs_o = paired_bootstrap(ba_difference, [truth, predicted["C"], predicted["O"]])
        report["rule_c_bootstrap"] = c_vs_o
        report["decision_C"] = decide(primary_c["false_closes"], nonsupported, primary_c["closure_rate"],
                                      c_vs_o["low"], (flips["rate_low"], flips["rate_high"]),
                                      (repeats["rate_low"], repeats["rate_high"]), median_latency)
    else:
        report["decision_C"] = {"verdict": "inconclusive", "reason": "arm O missing"}
    if holds:
        # Section 5.0: a stopped run reports its partial results and decides nothing; so does a run with a
        # scheduled call missing, or without the canary result the stop rules need.
        report["decision_C"] = {"verdict": "inconclusive", "reason": holds[0], "reasons": holds,
                                "stop_reasons": stop["reasons"], "partial": report["decision_C"]}
    report["order_flips"] = flips
    report["repeat_disagreement"] = repeats
    report["j3_latency"] = {"median_s": median_latency, "cases": len(latencies)}
    if "C_L" in routes and "O" in predicted:
        primary_l = primary(routes["C_L"])
        l_vs_o = paired_bootstrap(ba_difference, [truth, predicted["C_L"], predicted["O"]])
        # L scores one premise-hypothesis pair, so the order-flip part of (d) does not apply; repeat
        # disagreement is measured over the three frozen L calls per case (README "Open decisions" 7).
        # With fewer it stays None, and so does qualifies: an unmeasured rule is never a pass.
        l_repeats = single_arm_repeat_disagreement(calls, "L", case_ids)
        prescreen = {"primary": primary_l, "bootstrap": l_vs_o, "order_flips": NOT_APPLICABLE,
                     "repeat_disagreement": l_repeats,
                     **prescreen_qualifies(primary_l["false_closes"], nonsupported, primary_l["closure_rate"],
                                           l_vs_o["low"], NOT_APPLICABLE,
                                           None if l_repeats is None else (l_repeats["rate_low"], l_repeats["rate_high"]))}
        if holds:
            prescreen.update({"qualifies": None, "reason": holds[0], "reasons": holds, "stop_reasons": stop["reasons"]})
        report["prescreen_L"] = prescreen
    descriptive = {"balanced_accuracy": {name: balanced_accuracy(truth, values) for name, values in predicted.items()}}
    if {"O", "S"} <= set(predicted):
        descriptive["J3_minus_best_native"] = paired_bootstrap(
            ba_minus_best_of, [truth, predicted["J3"], predicted["O"], predicted["S"]])
    descriptive["confusion_matrices"] = {
        name: {"labels_true": list(LABELS), "labels_predicted": list(LABELS) + ["error"],
               "matrix": confusion_matrix(truth, values, labels=[0, 1, 2, ERROR_CODE])[:3].tolist()}
        for name, values in predicted.items()}
    if "O" in predicted:
        descriptive["mcnemar_vs_O"] = {name: mcnemar_exact(truth, values, predicted["O"])
                                       for name, values in predicted.items() if name != "O"}
    if {"J3", "S"} <= set(predicted):
        descriptive["mcnemar_J3_vs_S"] = mcnemar_exact(truth, predicted["J3"], predicted["S"])
    descriptive["calibration"] = calibration(arms, case_ids, labels)
    descriptive["strata"] = strata_report(cases, case_ids, labels, truth, predicted)
    descriptive["natural_prevalence"] = natural_prevalence(cases, case_ids, labels)
    report["descriptive"] = descriptive
    if relabels:
        report["intra_rater"] = intra_rater(labels, relabels)
    return report


def calibration(arms: dict, case_ids: list[str], labels: dict[str, dict]) -> dict:
    """Brier score and 15-bin ECE for J (J-1, J-3, J-9) and L; no NLL (J's grid reaches 0)."""
    out = {}
    for name in ("J1", "J3", "J9", "L"):
        view = arms.get(name)
        if not view:
            continue
        rows = [(case, view[case]) for case in case_ids
                if view.get(case) and view[case].get("probabilities") and view[case].get("confidence") is not None]
        if not rows:
            continue
        truth = [labels[case]["label"] for case, _ in rows]
        out[name] = {
            "n": len(rows),
            "brier_multiclass": multiclass_brier(truth, [item["probabilities"] for _, item in rows]),
            "ece_top_label": expected_calibration_error([item["confidence"] for _, item in rows],
                                                        [item["answer"] == label for (_, item), label in zip(rows, truth)]),
        }
    return out


def strata_report(cases: dict, case_ids: list[str], labels: dict[str, dict], truth: np.ndarray,
                  predicted: dict[str, np.ndarray]) -> dict:
    keys = {
        "subset": lambda case: cases[case]["subset"],
        "universal": lambda case: cases[case]["strata"]["universal"],
        "numeric_or_date": lambda case: cases[case]["strata"]["numeric_or_date"],
        "adversarial_form": lambda case: cases[case]["strata"]["adversarial_form"],
        "adversarial_author": lambda case: cases[case]["strata"]["adversarial_author"],
        "claim_type": lambda case: labels[case].get("claim_type"),
    }
    report = {}
    for key, value_of in keys.items():
        groups: dict[str, list[int]] = {}
        for index, case in enumerate(case_ids):
            groups.setdefault(str(value_of(case)), []).append(index)
        report[key] = {value: {"n": len(rows),
                               "label_counts": dict(Counter(LABELS[truth[row]] for row in rows)),
                               "balanced_accuracy": {name: balanced_accuracy(truth[rows], values[rows])
                                                     for name, values in predicted.items()}}
                       for value, rows in sorted(groups.items())}
    return report


def natural_prevalence(cases: dict, case_ids: list[str], labels: dict[str, dict]) -> dict:
    natural = [case for case in case_ids if cases[case]["subset"] == "natural"]
    counts = Counter(labels[case]["label"] for case in natural)
    return {label: {"count": counts.get(label, 0), "share": counts.get(label, 0) / len(natural) if natural else math.nan,
                    "wilson": wilson_interval(counts.get(label, 0), len(natural))} for label in LABELS}


def intra_rater(labels: dict[str, dict], relabels: dict[str, dict]) -> dict:
    shared = sorted(set(labels) & set(relabels))
    first = [labels[case]["label"] for case in shared]
    second = [relabels[case]["label"] for case in shared]
    agree = sum(a == b for a, b in zip(first, second))
    kappa = float(cohen_kappa_score(first, second, labels=list(LABELS))) if shared and len(set(first + second)) > 1 else math.nan
    return {"n": len(shared), "agreement": agree / len(shared) if shared else math.nan, "cohen_kappa": kappa}


# --------------------------------------------------------------------------- promptfoo adapter


def model_from_error(error) -> str | None:
    """The response model p1/response-model.cjs names when ../response.cjs refused a response; None when
    the error carries none (a transport error, or a refused response without a model field)."""
    match = MODEL_IN_ERROR.search(str(error or ""))
    return json.loads(match.group(1)) if match else None


def calls_from_promptfoo(document: dict, arm_of_label: dict[str, tuple[str, int]]) -> list[dict]:
    """Normalize a promptfoo 0.123.1 --output JSON. arm_of_label maps a provider label to (arm, order).
    case_id and repeat_index come from the test vars; row order is never used. A call's model is its
    response metadata's, or on a refused response the one its error names; attempts come from the
    response metadata when a provider records them, and are unknown (None) otherwise."""
    results = document.get("results", {})
    rows = results.get("results", []) if isinstance(results, dict) else results
    calls = []
    for row in rows:
        label = (row.get("provider") or {}).get("label")
        if label not in arm_of_label:
            continue
        arm, order = arm_of_label[label]
        variables = row.get("vars") or (row.get("testCase") or {}).get("vars") or {}
        response = row.get("response") or {}
        metadata = response.get("metadata") or {}
        answer = _verdict(response.get("output"))
        error = row.get("error") or response.get("error")
        model = metadata.get("model")
        if model is None and error:
            model = model_from_error(error)
        calls.append({
            "arm": arm, "case_id": variables["case_id"], "order": order, "repeat": int(variables.get("repeat_index", 0)),
            "answer": answer if not error else None, "error": error or None,
            "confidence": metadata.get("confidence"), "probabilities": metadata.get("probabilities"),
            "model": model, "inference": metadata.get("inference"),
            "request_id": metadata.get("request_id"),
            "latency_s": (row.get("latencyMs") / 1000.0) if isinstance(row.get("latencyMs"), (int, float)) else None,
            "usage": response.get("tokenUsage"), "attempts": attempts_of(metadata),
        })
    return calls


def _verdict(output) -> str | None:
    if isinstance(output, dict):
        value = output.get("verdict")
    elif isinstance(output, str):
        try:
            parsed = json.loads(output)
        except ValueError:
            parsed = output
        value = parsed.get("verdict") if isinstance(parsed, dict) else parsed
    else:
        value = None
    return value if value in LABELS else None


def _read_records(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["labels"] if isinstance(data, dict) and "labels" in data else data


def _canary_argument(text: str) -> int:
    try:
        return canary_count(int(text))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--relabels", type=Path)
    parser.add_argument("--calls", type=Path, required=True, help="normalized calls, one JSON object per line")
    parser.add_argument("--tests", type=Path, required=True,
                        help="the frozen promptfoo test rows (promptfoo_tests role): the schedule every call is checked against")
    parser.add_argument("--canary-flips", type=_canary_argument, required=True,
                        help=f"how many of the {CANARY_CASES} A1 canary cases flipped (0-{CANARY_CASES}), from the canary run")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    labels = _read_records(args.labels)
    relabels = _read_records(args.relabels) if args.relabels else None
    calls = [json.loads(line) for line in args.calls.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [json.loads(line) for line in args.tests.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = score(pack, labels, calls, schedule_from_rows(rows), relabels, args.canary_flips)
    args.out.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict_C": report["decision_C"]["verdict"], "stop": report["stop"]["stop"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
