"""Draft contract; follows test_token_e2e_preregistration.py at 341ba641.

These are structural checks, not Claude execution or compaction acceptance.
The public seam is the JSON protocol and its human-readable contract table.
"""

import hashlib
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
    "selection_rule": "Among quality-eligible candidates meeting the 10% pooled and per-task cost margin versus A, choose the unique lowest pooled all-attempt weighted child cost per successful task; an exact cost tie yields no selection and retains A.",
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
            "run_budget_tokens": 1000000000,
            "ledger_poll_seconds": 1,
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

    def spec(self):
        return json.loads((BLUEPRINT / "preregistration.json").read_text())

    def test_budget_uses_native_tokens_and_does_not_invent_a_charge_bound(self):
        spec = self.spec()
        self.assertIn("token_budget", spec["stop_rules"])
        budget = spec["stop_rules"]["token_budget"]
        self.assertEqual(budget["limit_tokens"], 1_000_000_000)
        self.assertEqual(budget["unit"], "input + cache_creation + cache_read + output tokens")
        self.assertEqual(budget["ledger_scope"], "all_owned_requests_including_readiness")
        self.assertEqual(budget["cancel_when"], "observed_tokens + outstanding_reserve_tokens >= limit_tokens")
        self.assertEqual(budget["outstanding_bound"]["formula"],
                         "R_max * (N_active_max + ceil(lambda_max * (L_bound + P + K_bound)))")
        self.assertFalse(budget["outstanding_bound"]["qualified"])
        self.assertIsNone(budget["reporting_lag"]["measured_max_seconds"])
        self.assertIsNone(budget["outstanding_bound"]["reserve_tokens"])
        self.assertEqual(budget["unqualified_action"], "do_not_launch")
        self.assertEqual(budget["cancellation"]["signals"], ["SIGTERM", "SIGKILL"])
        self.assertEqual(budget["cancellation"]["target"], "owned_process_group_only")
        self.assertFalse(budget["cancellation"]["server_charge_stops_on_signal"])
        self.assertEqual(spec["metrics"]["weekly_quota"]["role"], "descriptive_cross_check_only")
        self.assertNotIn("weekly_hard_cap", spec["stop_rules"])

    def test_request_ledger_covers_hidden_requests_and_reconciles_once(self):
        spec = self.spec()
        self.assertIn("request_ledger", spec["metrics"])
        ledger = spec["metrics"]["request_ledger"]
        self.assertEqual(ledger["instrument"], "Claude Code native OTel api_request events")
        self.assertEqual(ledger["transport"], "existing host collector -> Loki")
        self.assertEqual(ledger["deduplication"]["key"], ["provider", "request_id"])
        self.assertEqual(ledger["deduplication"]["conflict_action"], "stop_entire_run_incomplete")
        self.assertEqual(ledger["counters"], {
            "input_tokens": "input_tokens", "output_tokens": "output_tokens",
            "cache_creation_tokens": "cache_creation_input_tokens",
            "cache_read_tokens": "cache_read_input_tokens",
        })
        self.assertTrue({"compaction", "background_preparation", "retry", "refusal", "fallback"}
                        <= set(ledger["include"]))
        self.assertIn("request_id", ledger["required_attributes"])
        self.assertIn("workflow.run_id", ledger["attribution"])
        self.assertEqual(ledger["unattributed_action"], "retain_in_run_budget_stop_comparison")
        self.assertEqual(ledger["reconciliation"]["ccusage_pin"], "v20.0.26")
        self.assertIn("--json --offline", ledger["reconciliation"]["command"])
        self.assertFalse(ledger["reconciliation"]["add_totals_to_ledger"])
        self.assertEqual(ledger["reconciliation"]["unexplained_delta_action"],
                         "stop_entire_run_incomplete")
        self.assertFalse(ledger["qualification"]["request_id_preservation_proven"])

    def test_selection_optimizes_cost_instead_of_arm_order(self):
        rule = self.spec()["decision_rule"]
        self.assertEqual(rule["selection_rule"], RULES["selection_rule"])
        self.assertEqual(rule["objective"], "minimize_pooled_all_attempt_weighted_child_cost_per_success")
        self.assertEqual(rule["tie_rule"], "exact_unrounded_tie_retain_A_no_selection")
        self.assertEqual(rule["minimum_effect_fraction_vs_A"], 0.1)
        examples = {row["id"]: row for row in rule["worked_examples"]}
        # Independent review counterexample and its symmetric/tied controls.
        self.assertEqual(examples["review_counterexample"]["cost_per_success"],
                         {"A": 100, "B": 60, "C": 89})
        self.assertEqual(examples["review_counterexample"]["selected"], "B")
        self.assertEqual(examples["C_cheapest"]["selected"], "C")
        self.assertEqual(examples["cost_tie"]["selected"], "A")
        self.assertEqual(examples["below_minimum_effect"]["selected"], "A")
        self.assertEqual(examples["cheap_quality_regression"]["selected"], "C")

    def test_inspect_oracle_contracts_have_hashed_discriminating_controls(self):
        spec = self.spec()
        self.assertIn("oracle_framework", spec)
        framework = spec["oracle_framework"]
        self.assertEqual(framework["package"], "inspect-ai==0.3.271")
        self.assertEqual(framework["scorer"], "inspect_ai.scorer.match")
        self.assertEqual(framework["scorer_args"],
                         {"location": "exact", "ignore_case": False, "numeric": False})
        self.assertFalse(framework["uses_inspect_swe_bridge"])
        self.assertFalse(framework["qualification"]["passed"])
        check_ids = {check["id"] for task in spec["tasks"] for check in task["checks"]}
        self.assertEqual(set(framework["adapters"]), check_ids)
        for check_id, adapter in framework["adapters"].items():
            with self.subTest(check=check_id):
                self.assertTrue(adapter["independent_input"])
                self.assertTrue(adapter["projection"])
                self.assertEqual(adapter["contract_sha256"], self.digest(adapter["contract"]))
                self.assertEqual(set(adapter["controls"]),
                                 {"known_pass", "known_fail", "malformed_output", "missing_output"})
                for name, control in adapter["controls"].items():
                    self.assertEqual(control["sha256"], self.digest(control["fixture"]))
                    self.assertEqual(control["expected_score"], "C" if name == "known_pass" else "I")
                good = adapter["controls"]["known_pass"]["fixture"]
                bad = adapter["controls"]["known_fail"]["fixture"]
                self.assertEqual(good["observed"], good["target"])
                self.assertNotEqual(bad["observed"], bad["target"])
                self.assertEqual(bad["target"], good["target"])
                self.assertIsNone(adapter["executable_sha256"])

    @staticmethod
    def digest(value):
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def test_three_repetitions_are_an_exploratory_pilot_not_adoption_evidence(self):
        spec = self.spec()
        self.assertIn("precision", spec["execution"])
        precision = spec["execution"]["precision"]
        self.assertEqual(precision["scope"], "exploratory_frozen_suite_pilot")
        self.assertIsNone(precision["variance_estimate"])
        self.assertIsNone(precision["confirmatory_repetitions"])
        self.assertIsNone(precision["claimed_confidence_level"])
        self.assertEqual(precision["paired_unit"], "task_by_repetition")
        self.assertEqual(precision["repetitions_per_task"], 3)
        self.assertFalse(spec["sealing"]["pilot_allows_persistent_adoption"])
        self.assertIn("exploratory", spec["decision_rule"]["interpretation"])
        self.assertIn("stability", precision)


if __name__ == "__main__":
    unittest.main()
