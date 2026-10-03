"""P1 scoring rules on synthetic fixtures (scikit-learn and scipy).

The scoring code needs numpy, scipy and scikit-learn from
blueprints/native-skill-practice/p1/requirements-scoring.lock. Without them this module skips; with
JEV_P1_REQUIRE_SCORING_DEPS=1 a missing dependency fails the import instead, so a run that claims
these tests passed cannot have skipped them (docs/acceptance-evidence-policy.md: a skipped check is
untested, not passed). Every rule, statistic and adapter checked here is paired with a negative control
that must fail or differ, in the same test; FrozenConstantsTests.test_frozen_values only pins constants.
"""

from __future__ import annotations

import importlib.util
import math
import os
import random
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
P1 = ROOT / "blueprints" / "native-skill-practice" / "p1"
REQUIRED = os.environ.get("JEV_P1_REQUIRE_SCORING_DEPS") == "1"

try:
    import numpy as np
    from scipy import stats
    from sklearn.calibration import calibration_curve

    spec = importlib.util.spec_from_file_location("jev_p1_scoring", P1 / "p1_scoring.py")
    scoring = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scoring)
    MISSING = None
except ImportError as error:  # pragma: no cover - depends on the interpreter
    if REQUIRED:
        raise ImportError(f"JEV_P1_REQUIRE_SCORING_DEPS=1 but the scoring dependencies are missing: {error}")
    MISSING = str(error)


def probabilities(answer: str, top: float = 0.9) -> dict:
    rest = (1 - top) / 2
    return {label: (top if label == answer else rest) for label in ("supported", "contradicted", "insufficient")}


@unittest.skipIf(MISSING, f"scoring dependencies missing ({MISSING}); install requirements-scoring.lock")
class FrozenConstantsTests(unittest.TestCase):
    def test_frozen_values(self):
        self.assertEqual((scoring.SEED, scoring.N_RESAMPLES, scoring.CONFIDENCE_LEVEL), (20261003, 10_000, 0.95))
        self.assertEqual((scoring.CLOSE_THRESHOLD, scoring.ECE_BINS, scoring.BOOTSTRAP_METHOD), (0.80, 15, "percentile"))

    def test_bootstrap_call_is_paired_with_10000_resamples_and_the_seed(self):
        calls = []
        real = stats.bootstrap

        def spy(*args, **kwargs):
            calls.append({**kwargs, "rng_state": kwargs["rng"].bit_generator.state})
            return real(*args, **{**kwargs, "n_resamples": 50})

        truth = np.array([0, 1, 2, 0, 1, 2])
        with mock.patch.object(scoring.stats, "bootstrap", side_effect=spy):
            scoring.paired_bootstrap(scoring.ba_difference, [truth, truth, truth])
        kwargs = calls[0]
        self.assertEqual((kwargs["paired"], kwargs["n_resamples"], kwargs["method"], kwargs["vectorized"],
                          kwargs["confidence_level"]), (True, 10_000, "percentile", False, 0.95))
        self.assertEqual(kwargs["rng_state"], np.random.default_rng(20261003).bit_generator.state)
        self.assertNotEqual(kwargs["rng_state"], np.random.default_rng(20261004).bit_generator.state)


@unittest.skipIf(MISSING, f"scoring dependencies missing ({MISSING}); install requirements-scoring.lock")
class RuleTests(unittest.TestCase):
    PASSING = dict(false_closes=0, nonsupported=80, closure_rate=0.30, ba_difference_lower=-0.01,
                   order_flip=0.02, repeat_disagreement=0.01, median_latency_s=0.3)

    def outcome(self, **change):
        return scoring.decide(**{**self.PASSING, **change})

    def test_adopt_only_when_a_to_e_hold(self):
        self.assertEqual(self.outcome()["verdict"], "adopt")
        for change in ({"closure_rate": 0.24}, {"ba_difference_lower": -0.031}, {"order_flip": 0.051},
                       {"repeat_disagreement": 0.031}, {"median_latency_s": 0.51}, {"nonsupported": 59},
                       {"false_closes": 1}):
            with self.subTest(change=change):
                self.assertEqual(self.outcome(**change)["verdict"], "inconclusive")

    def test_boundaries_hold_inclusively(self):
        result = self.outcome(closure_rate=0.25, ba_difference_lower=-0.03, order_flip=0.05,
                              repeat_disagreement=0.03, median_latency_s=0.5)
        self.assertEqual(result["verdict"], "adopt")

    def test_reject(self):
        self.assertEqual(self.outcome(false_closes=2)["verdict"], "reject")
        self.assertEqual(self.outcome(order_flip=0.11)["verdict"], "reject")
        self.assertEqual(self.outcome(false_closes=2, nonsupported=40)["verdict"], "reject")
        self.assertEqual(self.outcome(order_flip=0.10)["verdict"], "inconclusive")
        self.assertEqual(self.outcome(false_closes=1, nonsupported=40)["verdict"], "inconclusive")

    def test_rule_a_wilson_bound_at_60_and_61(self):
        z = stats.norm.ppf(0.975)
        for trials in (60, 61, 80):
            upper = scoring.wilson_interval(0, trials)[1]
            self.assertAlmostEqual(upper, z * z / (trials + z * z), places=12)
        self.assertGreater(scoring.wilson_interval(0, 60)[1], 0.060)
        self.assertTrue(self.outcome(nonsupported=60)["rules"]["a"])     # holds at three decimals only
        self.assertLess(scoring.wilson_interval(0, 61)[1], 0.060)
        with mock.patch.object(scoring, "WILSON_DECIMALS", 12):
            self.assertFalse(self.outcome(nonsupported=60)["rules"]["a"])
            self.assertTrue(self.outcome(nonsupported=61)["rules"]["a"])
        self.assertAlmostEqual(scoring.wilson_interval(1, 60)[1], 0.0886, places=4)
        self.assertAlmostEqual(scoring.wilson_interval(1, 80)[1], 0.0675, places=4)
        self.assertFalse(self.outcome(false_closes=1, nonsupported=80)["rules"]["a"])

    def test_rule_d_uses_the_high_bound_and_reject_the_low_bound(self):
        # 2 known flips and 4 incomplete cases of 120: low 0.017, high 0.050.
        self.assertTrue(self.outcome(order_flip=(2 / 120, 6 / 120))["rules"]["d"])
        self.assertFalse(self.outcome(order_flip=(2 / 120, 7 / 120))["rules"]["d"])
        self.assertFalse(self.outcome(repeat_disagreement=(0.0, 0.031))["rules"]["d"])
        self.assertEqual(self.outcome(order_flip=(0.11, 0.20))["verdict"], "reject")
        # Negative control: incomplete cases alone never reject (low 0.05, high 0.20).
        self.assertEqual(self.outcome(order_flip=(0.05, 0.20))["verdict"], "inconclusive")

    def test_prescreen_l_rule_d_without_an_order(self):
        na = scoring.NOT_APPLICABLE
        self.assertTrue(scoring.prescreen_qualifies(0, 80, 0.3, -0.01, na, 0.0)["qualifies"])
        self.assertTrue(scoring.prescreen_qualifies(0, 80, 0.3, -0.01, na, (0.0, 0.03))["qualifies"])
        # Negative controls: repeats that disagree fail (d); unmeasured repeats leave (d) open, never a pass.
        self.assertFalse(scoring.prescreen_qualifies(0, 80, 0.3, -0.01, na, (0.0, 0.04))["qualifies"])
        open_d = scoring.prescreen_qualifies(0, 80, 0.3, -0.01, na, None)
        self.assertEqual((open_d["qualifies"], open_d["rules"]["d"]), (None, None))
        self.assertEqual(scoring.prescreen_qualifies(0, 80, 0.3, -0.01, None, 0.0)["qualifies"], None)
        self.assertFalse(scoring.prescreen_qualifies(1, 80, 0.3, -0.01, na, 0.0)["qualifies"])


@unittest.skipIf(MISSING, f"scoring dependencies missing ({MISSING}); install requirements-scoring.lock")
class StatisticsTests(unittest.TestCase):
    def test_exact_mcnemar(self):
        truth = np.zeros(10, dtype=int)
        first = np.array([0] * 8 + [1, 1])
        second = np.array([0, 0] + [1] * 8)
        result = scoring.mcnemar_exact(truth, first, second)
        self.assertEqual((result["only_first_correct"], result["only_second_correct"]), (6, 0))
        expected = min(1.0, 2 * sum(math.comb(6, k) for k in range(0, 1)) / 2 ** 6)
        self.assertAlmostEqual(result["p_value"], expected, places=12)
        self.assertEqual(scoring.mcnemar_exact(truth, first, first)["p_value"], 1.0)
        swapped = scoring.mcnemar_exact(truth, second, first)
        self.assertEqual((swapped["only_first_correct"], swapped["p_value"]), (0, result["p_value"]))

    def test_balanced_accuracy_counts_errors_as_wrong(self):
        truth = np.array([0, 0, 1, 1])
        self.assertEqual(scoring.balanced_accuracy(truth, np.array([0, 0, 1, 1])), 1.0)
        self.assertEqual(scoring.balanced_accuracy(truth, np.array([0, -1, 1, -1])), 0.5)

    def test_bootstrap_is_seeded_and_best_of_sits_inside_each_resample(self):
        rng = random.Random(3)
        truth = np.array([rng.randrange(3) for _ in range(60)])
        jev = np.array([value if rng.random() < 0.8 else (value + 1) % 3 for value in truth])
        opus = np.array([value if index < 30 else (value + 1) % 3 for index, value in enumerate(truth)])
        sol = np.array([value if index >= 30 else (value + 1) % 3 for index, value in enumerate(truth)])
        with mock.patch.object(scoring, "N_RESAMPLES", 300):
            first = scoring.paired_bootstrap(scoring.ba_minus_best_of, [truth, jev, opus, sol])
            again = scoring.paired_bootstrap(scoring.ba_minus_best_of, [truth, jev, opus, sol])
            fixed = scoring.paired_bootstrap(scoring.ba_difference, [truth, jev, opus])
            with mock.patch.object(scoring, "SEED", 20261004):
                other = scoring.paired_bootstrap(scoring.ba_minus_best_of, [truth, jev, opus, sol])
        self.assertEqual(first, again)
        self.assertNotEqual((first["low"], first["high"]), (other["low"], other["high"]))
        # best-of is never better for J than a fixed native arm, so its bounds sit at or below fixed O's.
        self.assertLessEqual(first["high"], fixed["high"] + 1e-12)
        self.assertLess(first["low"], fixed["low"])
        manual = scoring.balanced_accuracy(truth, jev) - max(scoring.balanced_accuracy(truth, opus),
                                                             scoring.balanced_accuracy(truth, sol))
        self.assertAlmostEqual(first["point"], manual, places=12)

    def test_brier_and_ece(self):
        truth = ["supported", "contradicted", "insufficient"]
        perfect = [{"supported": 1.0, "contradicted": 0.0, "insufficient": 0.0},
                   {"supported": 0.0, "contradicted": 1.0, "insufficient": 0.0},
                   {"supported": 0.0, "contradicted": 0.0, "insufficient": 1.0}]
        self.assertEqual(scoring.multiclass_brier(truth, perfect), 0.0)
        flat = [{label: 1 / 3 for label in perfect[0]} for _ in truth]
        self.assertAlmostEqual(scoring.multiclass_brier(truth, flat), (2 / 3) ** 2 + 2 * (1 / 3) ** 2, places=12)
        confidences = [0.9] * 10
        correct = [True] * 7 + [False] * 3
        self.assertAlmostEqual(scoring.expected_calibration_error(confidences, correct)["ece"], 0.2, places=12)
        self.assertNotAlmostEqual(scoring.expected_calibration_error([0.7] * 10, correct)["ece"], 0.2, places=6)

    def test_ece_bins_match_sklearn_calibration_curve(self):
        rng = random.Random(5)
        confidences = [round(rng.uniform(0.34, 1.0), 2) for _ in range(200)]
        correct = [rng.random() < value for value in confidences]
        table = scoring.expected_calibration_error(confidences, correct)["table"]
        accuracy, confidence = calibration_curve(correct, confidences, n_bins=15, strategy="uniform")
        self.assertEqual(len(table), len(accuracy))
        for row, (acc, conf) in zip(table, zip(accuracy, confidence)):
            self.assertAlmostEqual(row["accuracy"], acc, places=12)
            self.assertAlmostEqual(row["mean_confidence"], conf, places=12)
        # Negative control: ten bins put the same data in other bins, which the comparison detects.
        accuracy_10, confidence_10 = calibration_curve(correct, confidences, n_bins=10, strategy="uniform")
        self.assertFalse(len(table) == len(accuracy_10) and all(
            abs(row["mean_confidence"] - conf) < 1e-12 for row, conf in zip(table, confidence_10)))


def jev_calls(case: str, answers: dict[tuple[int, int], str], latency: float = 0.2) -> list[dict]:
    return [{"arm": "J", "case_id": case, "order": order, "repeat": repeat, "answer": answer,
             "probabilities": probabilities(answer), "confidence": 0.9, "latency_s": latency + 0.01 * order,
             "model": "jev-1.13.0", "inference": "live", "request_id": f"r-{case}-{order}-{repeat}",
             "usage": {"prompt": 100, "completion": 1}} for (order, repeat), answer in answers.items()]


def grid(answer: str = "supported", **changes) -> dict[tuple[int, int], str]:
    cells = {(order, repeat): answer for order in range(3) for repeat in range(3)}
    for key, value in changes.items():
        order, repeat = int(key[1]), int(key[3])
        cells[(order, repeat)] = value
    return cells


@unittest.skipIf(MISSING, f"scoring dependencies missing ({MISSING}); install requirements-scoring.lock")
class DefinitionTests(unittest.TestCase):
    def test_order_flip_and_repeat_disagreement(self):
        calls = jev_calls("c1", grid()) + jev_calls("c2", grid(o1r0="contradicted", o1r1="contradicted"))
        calls += jev_calls("c3", grid(o2r2="insufficient"))
        views = scoring.jev_views(calls, ["c1", "c2", "c3"])
        flips = scoring.order_flip_rate(views)
        self.assertEqual((flips["flips"], flips["cases"], flips["rate"]), (1, 3, 1 / 3))
        repeats = scoring.repeat_disagreement_rate(calls, ["c1", "c2", "c3"])
        self.assertEqual((repeats["disagreements"], repeats["pairs"], repeats["rate"]), (2, 9, 2 / 9))
        mutated = jev_calls("c1", grid(o0r1="insufficient")) + calls[9:]
        self.assertEqual(scoring.repeat_disagreement_rate(mutated, ["c1", "c2", "c3"])["disagreements"], 3)

    def test_incomplete_calls_stay_in_the_frozen_denominators(self):
        cells = grid()
        del cells[(1, 2)]
        calls = jev_calls("c1", cells) + jev_calls("c2", grid())
        views = scoring.jev_views(calls, ["c1", "c2"])
        self.assertIsNotNone(views["c1"]["J3"])
        self.assertIsNone(views["c1"]["J9"])
        flips = scoring.order_flip_rate(views)
        self.assertEqual((flips["cases"], flips["incomplete"], flips["rate"]), (2, 1, None))
        self.assertEqual((flips["rate_low"], flips["rate_high"]), (0.0, 0.5))
        repeats = scoring.repeat_disagreement_rate(calls, ["c1", "c2"])
        self.assertEqual((repeats["pairs"], repeats["incomplete"], repeats["rate_low"], repeats["rate_high"]),
                         (6, 1, 0.0, 1 / 6))
        # Negative control: with every call present the bounds meet at the frozen rate.
        complete = scoring.repeat_disagreement_rate(jev_calls("c1", grid()) + jev_calls("c2", grid()), ["c1", "c2"])
        self.assertEqual((complete["rate"], complete["rate_low"], complete["rate_high"]), (0.0, 0.0, 0.0))

    def test_plurality_tie_breaks(self):
        rows = [probabilities("supported", 0.5), probabilities("contradicted", 0.6), probabilities("insufficient", 0.4)]
        self.assertEqual(scoring.plurality(["supported", "contradicted", "insufficient"], rows)[0], "contradicted")
        flat = [{label: 1 / 3 for label in ("supported", "contradicted", "insufficient")}] * 3
        self.assertEqual(scoring.plurality(["insufficient", "contradicted", "supported"], flat)[0], "supported")
        answer, confidence = scoring.plurality(["contradicted", "contradicted", "supported"], rows)
        self.assertEqual(answer, "contradicted")
        self.assertAlmostEqual(confidence, (0.25 + 0.6 + 0.3) / 3, places=12)

    def test_j3_latency_is_the_slowest_of_three(self):
        views = scoring.jev_views(jev_calls("c1", grid(), latency=0.3), ["c1"])
        self.assertAlmostEqual(views["c1"]["j3_latency_s"], 0.32, places=12)
        self.assertNotAlmostEqual(views["c1"]["j3_latency_s"], 0.31, places=6)     # control: not the mean

    def test_cascade_routes(self):
        claims = {"c1": "Codex 0.160 ships", "c2": "The gate closes", "c3": "The gate closes", "c4": "The gate opens"}
        closer = {"c1": {"answer": "supported", "confidence": 0.99}, "c2": {"answer": "supported", "confidence": 0.80},
                  "c3": {"answer": "supported", "confidence": 0.7999}, "c4": {"answer": "contradicted", "confidence": 0.99}}
        opus = {case: {"answer": "insufficient"} for case in claims}
        routed = scoring.cascade(list(claims), claims, closer, opus)
        self.assertEqual({case: value["route"] for case, value in routed.items()},
                         {"c1": "digit_to_opus", "c2": "closed", "c3": "escalated", "c4": "escalated"})
        self.assertEqual(routed["c2"]["answer"], "supported")
        self.assertEqual(routed["c1"]["answer"], "insufficient")

    def test_stop_rules(self):
        live = {"model": "jev-1.13.0", "inference": "live"}
        calls = [{"arm": "J", "answer": "supported", **live} for _ in range(95)]
        calls += [{"arm": "J", "answer": None, "error": "HTTP 500", **live} for _ in range(4)]
        calls.append({"arm": "J", "answer": "supported", "attempts": 2, **live})
        self.assertFalse(scoring.stop_checks(calls, 2)["stop"])                  # 5 of 100 is not above 5%
        calls.append({"arm": "J", "answer": None, "error": "timeout", **live})
        self.assertEqual(scoring.stop_checks(calls, None)["reasons"], ["service_errors"])
        self.assertIn("canary_flips", scoring.stop_checks(calls[:95], 3)["reasons"])
        moved = calls[:95] + [{"arm": "J", "answer": "supported", "model": "jev-latest", "inference": "live"}]
        self.assertIn("jev_model_moved", scoring.stop_checks(moved, 0)["reasons"])
        cached = calls[:95] + [{"arm": "J", "answer": "supported", "model": "jev-1.13.0", "inference": "cache"}]
        self.assertEqual(scoring.stop_checks(cached, 0)["reasons"], ["jev_result_not_live"])

    def test_a_failed_call_without_a_model_is_not_a_move(self):
        live = {"model": "jev-1.13.0", "inference": "live"}
        calls = [{"arm": "J", "answer": "supported", **live} for _ in range(99)]
        calls.append({"arm": "J", "answer": None, "error": "HTTP call failed with status 503", "model": None})
        result = scoring.stop_checks(calls, 0)
        self.assertEqual((result["stop"], result["unexpected_jev_models"], result["jev_failed_model_unknown"]),
                         (False, [], 1))
        # Negative controls: a refused response that names another model is a move, and an answered
        # call whose model was never recorded is unverified.
        refused = calls[:99] + [{"arm": "J", "answer": None, "error": "contract", "model": "jev-latest"}]
        self.assertEqual(scoring.stop_checks(refused, 0)["reasons"], ["jev_model_moved"])
        silent = calls[:99] + [{"arm": "J", "answer": "supported", "inference": "live"}]
        self.assertEqual(scoring.stop_checks(silent, 0)["reasons"], ["jev_model_unverified"])

    def test_operations_summary(self):
        calls = jev_calls("c1", grid()) + [{"arm": "O", "case_id": "c1", "answer": None, "error": "x", "attempts": 2}]
        calls.append({"arm": "O", "case_id": "c2", "answer": "supported", "attempts": 1})
        summary = scoring.operations(calls)
        self.assertEqual((summary["J"]["calls"], summary["J"]["request_ids"], summary["J"]["usage"]["prompt"]), (9, 9, 900))
        self.assertEqual((summary["O"]["errors"], summary["O"]["resent"], summary["O"]["attempts"]), (1, 1, 3))
        # Negative control: calls that record no attempt count are unknown, never counted as one attempt.
        self.assertEqual((summary["J"]["attempts"], summary["J"]["attempts_unknown"], summary["O"]["attempts_unknown"]),
                         (0, 9, 0))

    def test_promptfoo_adapter_reads_triples_not_row_order(self):
        def row(label, case, repeat, output, metadata=None, latency=200):
            return {"provider": {"id": "x", "label": label}, "vars": {"case_id": case, "repeat_index": repeat},
                    "response": {"output": output, "metadata": metadata or {}}, "latencyMs": latency}
        verdict = '{"verdict":"supported","eligible":true}'
        rows = [row("J-o2", "c1", 1, verdict, {"model": "jev-1.13.0", "confidence": 0.9}),
                row("O", "c1", 0, '{"verdict":"insufficient"}'), row("render-check", "c1", 0, "text"),
                row("J-o0", "c1", 0, verdict, {"model": "jev-1.13.0"})]
        arms = {"J-o0": ("J", 0), "J-o1": ("J", 1), "J-o2": ("J", 2), "O": ("O", 0)}
        calls = scoring.calls_from_promptfoo({"results": {"results": rows}}, arms)
        reordered = scoring.calls_from_promptfoo({"results": {"results": list(reversed(rows))}}, arms)
        key = lambda call: (call["arm"], call["order"], call["repeat"])
        self.assertEqual(sorted(calls, key=key), sorted(reordered, key=key))
        self.assertEqual(sorted((call["arm"], call["order"], call["repeat"], call["answer"]) for call in calls),
                         [("J", 0, 0, "supported"), ("J", 2, 1, "supported"), ("O", 0, 0, "insufficient")])
        self.assertIsNone(scoring._verdict('{"verdict":"maybe"}'))
        self.assertEqual({call["attempts"] for call in calls}, {None})          # no metadata, no guess

    def test_promptfoo_adapter_reads_the_model_a_refused_response_named(self):
        def failed(error, metadata=None):
            return {"provider": {"label": "J-o0"}, "vars": {"case_id": "c1", "repeat_index": 0},
                    "error": error, "response": {"metadata": metadata or {}}}

        moved = ('Error: Unexpected TypeSafe model or answer contract [response model: "jev-latest"]\n\n'
                 "Error: Unexpected TypeSafe model or answer contract [response model: \"jev-latest\"]\n    at x")
        rows = [failed(moved), failed('Error: Invalid TypeSafe probability distribution [response model: null]'),
                failed("Error: HTTP call failed with status 503 Service Unavailable"),
                {**failed(None, {"model": "jev-1.13.0", "attempts": 2}), "error": None,
                 "response": {"output": "supported", "metadata": {"model": "jev-1.13.0", "attempts": 2}}}]
        calls = scoring.calls_from_promptfoo({"results": {"results": rows}}, {"J-o0": ("J", 0)})
        self.assertEqual([call["model"] for call in calls], ["jev-latest", None, None, "jev-1.13.0"])
        self.assertEqual([call["attempts"] for call in calls], [None, None, None, 2])
        self.assertEqual(scoring.stop_checks(calls, 0)["unexpected_jev_models"], ["jev-latest"])
        # Negative control: without the moved row, neither the null model nor the transport error is a move.
        self.assertNotIn("jev_model_moved", scoring.stop_checks(calls[1:], 0)["reasons"])


@unittest.skipIf(MISSING, f"scoring dependencies missing ({MISSING}); install requirements-scoring.lock")
class EndToEndTests(unittest.TestCase):
    def test_score_reports_every_section(self):
        rng = random.Random(9)
        labels, cases, calls = {}, [], []
        for index in range(30):
            case = f"c{index + 1:03d}"
            label = ("supported", "contradicted", "insufficient")[index % 3]
            labels[case] = {"label": label, "claim_type": "literal"}
            cases.append({"case_id": case, "subset": "natural" if index < 20 else "enriched",
                          "claim": "The gate closes" if index % 2 else "Version 2 ships",
                          "strata": {"universal": False, "numeric_or_date": index % 2 == 0,
                                     "adversarial_form": None, "adversarial_author": None}})
            calls += jev_calls(case, grid(label))
            for arm in ("O", "S", "G"):
                answer = label if rng.random() < 0.9 else "insufficient"
                calls.append({"arm": arm, "case_id": case, "order": 0, "repeat": 0, "answer": answer})
            calls.append({"arm": "L", "case_id": case, "order": 0, "repeat": 0, "answer": label,
                          "probabilities": probabilities(label), "confidence": 0.9})
        with mock.patch.object(scoring, "N_RESAMPLES", 200):
            report = scoring.score({"cases": cases}, labels, calls, relabels={"c001": labels["c001"]})
        self.assertEqual(report["decision_C"]["verdict"], "inconclusive")     # 20 non-supported < 60
        self.assertFalse(report["decision_C"]["rules"]["a"])
        self.assertEqual(report["primary_C"]["false_closes"], 0)
        self.assertEqual(report["order_flips"]["flips"], 0)
        for section in ("balanced_accuracy", "J3_minus_best_native", "confusion_matrices", "mcnemar_vs_O",
                        "calibration", "strata", "natural_prevalence"):
            self.assertIn(section, report["descriptive"])
        self.assertIsNone(report["prescreen_L"]["rules"]["d"])
        unlabelled = dict(labels)
        del unlabelled["c001"]
        with self.assertRaises(ValueError):
            scoring.score({"cases": cases}, unlabelled, calls)

    @staticmethod
    def l_fixture(repeats: int, disagreeing: int = 0):
        """90 digit-free cases (30 supported, 60 non-supported); L and O answer every case correctly."""
        labels, cases, calls = {}, [], []
        for index in range(90):
            case = f"c{index + 1:03d}"
            label = "supported" if index < 30 else ("contradicted", "insufficient")[index % 2]
            labels[case] = {"label": label, "claim_type": "literal"}
            cases.append({"case_id": case, "subset": "natural", "claim": "The gate closes",
                          "strata": {"universal": False, "numeric_or_date": False,
                                     "adversarial_form": None, "adversarial_author": None}})
            calls += jev_calls(case, grid(label))
            calls.append({"arm": "O", "case_id": case, "order": 0, "repeat": 0, "answer": label})
            for repeat in range(repeats):
                answer = "insufficient" if repeat == 2 and index < disagreeing else label
                calls.append({"arm": "L", "case_id": case, "order": 0, "repeat": repeat, "answer": answer,
                              "probabilities": probabilities(answer), "confidence": 0.9})
        return {"cases": cases}, labels, calls

    def test_arm_l_qualifies_once_l_is_repeated(self):
        with mock.patch.object(scoring, "N_RESAMPLES", 200):
            repeated = scoring.score(*self.l_fixture(repeats=3))
            single = scoring.score(*self.l_fixture(repeats=1))
            noisy = scoring.score(*self.l_fixture(repeats=3, disagreeing=3))
        self.assertEqual(repeated["prescreen_L"]["primary"]["false_closes"], 0)
        self.assertEqual((repeated["prescreen_L"]["rules"]["d"], repeated["prescreen_L"]["qualifies"]), (True, True))
        self.assertEqual(repeated["prescreen_L"]["repeat_disagreement"]["pairs"], 90)
        # Negative controls: unrepeated L leaves (d) open; 3 of 90 disagreeing cases (3.3%) fail it.
        self.assertEqual((single["prescreen_L"]["rules"]["d"], single["prescreen_L"]["qualifies"]), (None, None))
        self.assertEqual((noisy["prescreen_L"]["rules"]["d"], noisy["prescreen_L"]["qualifies"]), (False, False))

    def test_a_stopped_run_decides_nothing(self):
        pack, labels, calls = self.l_fixture(repeats=3)
        calls = [dict(call, model="jev-latest") if call["arm"] == "J" and call["case_id"] == "c001" else call
                 for call in calls]
        with mock.patch.object(scoring, "N_RESAMPLES", 200):
            stopped = scoring.score(pack, labels, calls)
            running = scoring.score(*self.l_fixture(repeats=3))
        self.assertEqual((stopped["decision_C"]["verdict"], stopped["decision_C"]["reason"]), ("inconclusive", "stopped"))
        self.assertIn("jev_model_moved", stopped["decision_C"]["stop_reasons"])
        self.assertIn("rules", stopped["decision_C"]["partial"])                  # partial results stay reported
        self.assertIsNone(stopped["prescreen_L"]["qualifies"])
        # Negative control: the same data without the moved model is not stopped.
        self.assertFalse(running["stop"]["stop"])
        self.assertNotEqual(running["decision_C"].get("reason"), "stopped")
        self.assertTrue(running["prescreen_L"]["qualifies"])


if __name__ == "__main__":
    unittest.main()
