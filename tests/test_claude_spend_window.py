"""Local receipt contracts and synthetic advisor-cohort controls, not upstream tests."""

from __future__ import annotations

import ast
import calendar
import collections
import hashlib
import json
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "evidence/artifacts/claude-spend-window-compare.py.txt"
RECEIPT = ROOT / "evidence/receipts/claude-spend-window-20261004.json"


def helpers():
    """Load only the artifact's pure functions; never open private audit inputs."""
    tree = ast.parse(ARTIFACT.read_text())
    windows = next(ast.literal_eval(n.value) for n in tree.body
                   if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "WIN" for t in n.targets))
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name in {"ep", "win_of", "advisor_totals_by_window"}]
    namespace = {"collections": collections, "calendar": calendar, "time": time, "WIN": windows}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ARTIFACT), "exec"), namespace)
    namespace["WE"] = {w: tuple(namespace["ep"](s) for s in ends) for w, ends in windows.items()}
    return namespace


class AdvisorCohortControls(unittest.TestCase):
    def test_counts_advisor_tokens_in_both_main_and_subagent_files(self):
        records = [
            {"kind": "main", "first_ts": "2026-10-01T04:00:00Z",
             "tot": {"advisor(claude-fable-5-1)": {"calls": 2, "in": 10, "out": 3},
                     "claude-opus-5-5": {"calls": 99, "in": 999}}},
            {"kind": "sub", "first_ts": "2026-10-02T12:00:00Z",
             "tot": {"advisor(claude-fable-5-1)": {"calls": 1, "in": 20, "out": 4,
                                                        "cr": 30, "cw": 40}}},
        ]
        values = helpers()["advisor_totals_by_window"](records)["A_1001-02"]
        self.assertEqual(dict(values), {
            "advisor(claude-fable-5-1)": {"calls": 3, "in": 30, "out": 7, "cr": 30, "cw": 40},
        })

    def test_boundary_is_half_open_and_missing_tot_is_empty(self):
        records = [
            {"first_ts": "2026-10-03T04:00:00Z",
             "tot": {"advisor(claude-fable-5-1)": {"calls": 1, "in": 10, "out": 2}}},
            {"first_ts": "2026-10-04T14:00:00Z",
             "tot": {"advisor(claude-fable-5-1)": {"calls": 9, "in": 900}}},
            {"first_ts": "2026-10-03T05:00:00Z"},
        ]
        values = helpers()["advisor_totals_by_window"](records)
        self.assertFalse(values["A_1001-02"])
        self.assertEqual(values["B_1003-04"]["advisor(claude-fable-5-1)"]["calls"], 1)


class SpendWindowReceiptContracts(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads(RECEIPT.read_text())
        self.data = self.receipt["data"]

    def test_advisor_counts_and_inclusive_index_are_retained(self):
        comparison = self.data["window_comparison"]["advisor_comparison"]
        a = comparison["A_1001-02"]
        b = comparison["B_1003-04"]
        self.assertEqual(a["by_model"]["advisor(claude-fable-5-1)"]["iterations"], 689)
        self.assertEqual(b["by_model"]["advisor(claude-fable-5-1)"]["iterations"], 1209)
        self.assertAlmostEqual(a["advisor_cohort_iet_per_24h"], 85917497.5)
        self.assertAlmostEqual(b["advisor_cohort_iet_per_24h"], 198931490.11764705)
        self.assertEqual(self.data["window_comparison"]["windows"]["A_1001-02"]["all"]["calls"], 33869)
        self.assertEqual(self.data["window_comparison"]["windows"]["B_1003-04"]["all"]["calls"], 58025)

    def test_session_selection_does_not_claim_token_window_membership(self):
        raw = self.data["ccusage_session_view"]["raw_view"]
        selected = self.data["ccusage_session_view"]["activity_selected_view"]
        self.assertEqual((raw["rows"], selected["rows"], selected["excluded_rows"]), (179, 162, 17))
        self.assertAlmostEqual(selected["excluded_cost_usd"], 1252.9597084)
        self.assertAlmostEqual(selected["total_cost_usd"], 11151.91622575)
        shares = {x["session_name"]: x["cost_share"] for x in selected["coordinator_trees"]}
        self.assertAlmostEqual(shares["wsl-architecture-design"], 0.6329577509200921)
        self.assertAlmostEqual(shares["native-agent-stack-5f"], 0.3378680195337099)
        self.assertIn("earlier entries", selected["selection"])

    def test_source_repair_and_day_exclusion_are_explicit(self):
        provenance = self.data["provenance"]
        self.assertEqual(provenance["artifact"]["sha256"], hashlib.sha256(ARTIFACT.read_bytes()).hexdigest())
        self.assertFalse(provenance["artifact"]["source_body_byte_identical"])
        self.assertTrue(provenance["repair_replay"]["executor_output_exact_match"])
        self.assertEqual(self.data["ccusage_daily"]["excluded_source_days"][0]["date"], "2026-09-23")
        self.assertEqual(self.data["ccusage_daily"]["unpriced_gap"]["first_source_day"], "2026-09-28")

    def test_advisor_change_keeps_historical_usage_and_supplied_readback_distinct(self):
        decision = self.data["advisor_model_decision"]
        self.assertEqual(decision["advisorModel"], "opus")
        self.assertEqual(decision["native_readback"]["stdout"], "Advisor: Opus 5.5")
        self.assertFalse(decision["native_readback"]["executed_by_this_repair"])
        self.assertAlmostEqual(decision["historical_fable_oct03"]["fable_cost_usd"], 2092.86943)


if __name__ == "__main__":
    unittest.main()
