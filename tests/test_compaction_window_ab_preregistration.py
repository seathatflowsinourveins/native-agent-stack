"""Draft contract; follows test_token_e2e_preregistration.py at 341ba641.

These are structural checks, not Claude execution or compaction acceptance.
The public seam is the JSON protocol and its human-readable contract table.
"""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/compaction-window-ab"
VARIABLE = "CLAUDE_CODE_AUTO_COMPACT_WINDOW"
EXPECTED_ARMS = {"A": None, "B": "400000", "C": "200000"}
RULES = {
    "quality_rule": "For every task and check, any pass in A requires a pass in every repetition of the candidate.",
    "pass_count_rule": "Candidate total passed checks and successful tasks must each be at least A's totals.",
    "cost_rule": "All-attempt weighted child cost per successful task must be at least 10% lower than A, both pooled and for each task.",
    "selection_rule": "Choose C if eligible, otherwise B if eligible, otherwise retain A.",
    "incomplete_rule": "Any stopped, invalid, underlength, or unmeasured run is incomplete; no adoption result.",
}


class CompactionWindowPreregistrationTests(unittest.TestCase):
    def test_draft_contract(self):
        # This assertion was run before either artifact existed (red evidence).
        self.assertTrue((BLUEPRINT / "preregistration.json").is_file())
        self.assertTrue((BLUEPRINT / "PREREGISTRATION.md").is_file())
        spec = json.loads((BLUEPRINT / "preregistration.json").read_text())
        markdown = (BLUEPRINT / "PREREGISTRATION.md").read_text()
        self.assertEqual(spec["status"], "DRAFT")
        self.assertFalse(spec["frozen"])
        self.assertFalse(spec["run_started"])
        self.assertIn("Status: DRAFT", markdown)
        self.assertIn("not frozen", markdown)

        # A common immutable configuration plus one environment patch makes the
        # experimental difference explicit; no arm-specific model/tool overrides.
        self.assertEqual(len(spec["arms"]), 3)
        self.assertEqual({a["id"] for a in spec["arms"]}, set(EXPECTED_ARMS))
        for arm in spec["arms"]:
            self.assertEqual(set(arm), {"id", "environment"})
            self.assertEqual(arm["environment"], {VARIABLE: EXPECTED_ARMS[arm["id"]]})
            value = "unset" if arm["id"] == "A" else EXPECTED_ARMS[arm["id"]]
            threshold = {
                "A": "about 967000 tokens", "B": "400000 tokens", "C": "200000 tokens"
            }[arm["id"]]
            self.assertIn(f"| {arm['id']} | {value} | {threshold} |", markdown)
        controls = spec["shared_controls"]
        self.assertEqual(controls["client_version"], "2.1.283")
        self.assertEqual(controls["coordinator"]["effort"], "xhigh")
        self.assertEqual(controls["common_cli"]["autocompact"], "auto")
        for role in ("judgment", "builder", "verification", "research", "source_review"):
            self.assertEqual(controls["roles"][role]["model"], "claude-opus-5-5")
            self.assertEqual(controls["roles"][role]["effort"], "max")
        self.assertEqual(controls["roles"]["command_wrapper"]["model"], "claude-sonnet-5")
        self.assertIn("CLAUDE_CODE_DISABLE_1M_CONTEXT", controls["must_be_unset"])
        self.assertIn("CLAUDE_CODE_EFFORT_LEVEL", controls["must_be_unset"])

        expected_thresholds = {
            "default_approx_tokens": 967000,
            "B_window_tokens": 400000,
            "C_window_tokens": 200000,
            "long_child_prompt_tokens_exclusive": 400000,
            "cost_reduction_min_fraction": 0.1,
            "repetitions_per_task_arm": 3,
            "washout_seconds": 360,
            "weekly_usage_cap_percentage_points": 20,
            "weekly_usage_cancel_percentage_points": 18,
        }
        self.assertEqual(spec["thresholds"], expected_thresholds)
        for key, value in expected_thresholds.items():
            self.assertIn(f"| {key} | {value} |", markdown)
        for key, value in RULES.items():
            self.assertEqual(spec["decision_rule"][key], value)
            self.assertIn(f"| {key} | {value} |", markdown)
        self.assertTrue(spec["decision_rule"]["overturn_conditions"])

        tasks = spec["tasks"]
        self.assertEqual({t["kind"] for t in tasks}, {
            "test_first_builder", "web_research", "command_verification", "long_source_review"
        })
        self.assertEqual(len({t["id"] for t in tasks}), 4)
        source = json.loads((ROOT / spec["reused_task_source"]).read_text())
        source_ids = {t["id"] for t in source["tasks"]}
        for task in tasks:
            with self.subTest(task=task["id"]):
                frozen_input = task["frozen_input"]
                self.assertEqual(frozen_input["revision"], "341ba64186b5631f52c11bd290a4f32fd405b7b1")
                self.assertTrue(frozen_input["paths"])
                for path in frozen_input["paths"]:
                    self.assertTrue((ROOT / path).exists(), path)
                self.assertTrue(task["prompt"])
                self.assertTrue(task["long_child_workload"])
                self.assertEqual(task["underlength_action"], "incomplete_no_replacement")
                self.assertEqual(task["checks_frozen_before_run"], True)
                self.assertTrue(task["checks"])
                self.assertEqual(len({c["id"] for c in task["checks"]}), len(task["checks"]))
                for check in task["checks"]:
                    self.assertTrue(check["procedure"])
                    self.assertTrue(check["expected"])
                    self.assertIn(check["evidence_class"], {"local_integration_check", "independent_observation"})
                for source_id in task["source_task_ids"]:
                    self.assertIn(source_id, source_ids)

        orders = spec["execution"]["order_by_task"]
        self.assertEqual(set(orders), {t["id"] for t in tasks})
        counts = {}
        for permutations in orders.values():
            self.assertEqual(len(permutations), 3)
            for permutation in permutations:
                self.assertEqual(sorted(permutation), ["A", "B", "C"])
                counts[permutation] = counts.get(permutation, 0) + 1
            for position in range(3):
                self.assertEqual({p[position] for p in permutations}, {"A", "B", "C"})
        self.assertEqual(counts, {s: 2 for s in ("ABC", "BCA", "CAB", "ACB", "CBA", "BAC")})
        self.assertEqual(spec["execution"]["planned_attempts"], 36)
        self.assertTrue(spec["execution"]["fresh_process_per_attempt"])
        self.assertEqual(spec["execution"]["not_before"], "2026-09-30T21:00:00-04:00")
        self.assertEqual(spec["stop_rules"]["on_usage_limit_error"], "stop_entire_run_incomplete")
        self.assertEqual(spec["stop_rules"]["unknown_usage"], "stop_entire_run_incomplete")
        self.assertTrue(spec["sealing"]["append_only_dated_amendments"])
        self.assertFalse(spec["sealing"]["execution_authorized_by_this_draft"])
        self.assertIn("Sealing and Amendments", markdown)
        self.assertIn("| Artifact | SHA256 |", markdown)

        # Only source/method records belong in this draft, never private logs.
        for path in BLUEPRINT.glob("*"):
            if path.is_file():
                text = path.read_text()
                self.assertNotRegex(text, r"/(?:home|tmp)/")
                self.assertNotRegex(text, r"\bwf_[0-9a-f-]+\b")
                self.assertNotRegex(text, r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b")


if __name__ == "__main__":
    unittest.main()
