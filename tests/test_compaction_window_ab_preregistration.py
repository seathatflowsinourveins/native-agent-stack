"""Draft contract; follows test_token_e2e_preregistration.py at 341ba641.

These are structural checks, not Claude execution or compaction acceptance.
The public seam is the JSON protocol and its human-readable contract table.
"""

import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/compaction-window-ab"
VARIABLE = "CLAUDE_CODE_AUTO_COMPACT_WINDOW"
EXPECTED_ARMS = {"A": None, "B": "400000", "C": "200000"}
RULES = {
    "quality_rule": "For every task and check, any pass in A requires a pass in every repetition of the candidate.",
    "pass_count_rule": "Candidate total passed checks and successful tasks must each be at least A's totals.",
    "cost_rule": "All-attempt weighted child cost per successful task must be at least 10% lower than A, both pooled and for each task.",
    "selection_rule": "Among quality-eligible candidates meeting the 10% pooled and per-task cost margin versus A, choose the unique lowest pooled all-attempt weighted child cost per successful task; an exact cost tie yields no selection and leaves the incumbent host setting B unchanged.",
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
        self.assertTrue({"compaction", "background_preparation", "terminal_retry_chain", "refusal", "fallback"}
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
        self.assertEqual(rule["tie_rule"], "exact_unrounded_tie_no_selection_incumbent_B_unchanged")
        self.assertEqual(rule["minimum_effect_fraction_vs_A"], 0.1)
        examples = {row["id"]: row for row in rule["worked_examples"]}
        # Independent review counterexample and its symmetric/tied controls.
        self.assertEqual(examples["review_counterexample"]["cost_per_success"],
                         {"A": 100, "B": 60, "C": 89})
        self.assertEqual(examples["review_counterexample"]["selected"], "B")
        self.assertEqual(examples["C_cheapest"]["selected"], "C")
        self.assertIsNone(examples["cost_tie"]["selected"])
        self.assertIsNone(examples["below_minimum_effect"]["selected"])
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

    def test_live_host_condition_and_arm_readback_are_launch_gates(self):
        spec = self.spec()
        self.assertIn("host_condition", spec)
        host = spec["host_condition"]
        self.assertTrue(host["frozen_design_condition"])
        self.assertEqual(host["variable"], VARIABLE)
        self.assertEqual(host["value"], "400000")
        self.assertEqual(host["settings_file"], "~/.claude/settings.json")
        self.assertEqual(host["settings_scope"], "user")
        self.assertEqual(host["mechanism"], "env")
        self.assertEqual(host["activated_at"], "2026-09-27T18:59:00Z")
        self.assertEqual(host["incumbent_arm"], "B")
        observation = host["coordinator_observation"]
        self.assertEqual(observation["shell_value"], "400000")
        self.assertEqual(observation["first_request_auto_compaction_tokens"], 902612)
        self.assertEqual(observation["provenance"], "coordinator_supplied_not_replayed")

        isolation = spec["native_lever"]["settings_isolation"]
        self.assertEqual(isolation["setting_sources"], ["project"])
        self.assertEqual(isolation["excluded_settings_sources"], ["user", "local"])
        self.assertTrue(isolation["same_packet_all_arms"])
        self.assertFalse(isolation["packet_contains_window_env"])
        self.assertFalse(isolation["edits_host_settings"])
        self.assertEqual(spec["shared_controls"]["common_cli"]["setting_sources"], "project")
        self.assertTrue({"claude_settings", "claude_cli", "claude_config_dir"}
                        <= set(isolation["source_ids"]))
        gate = spec["native_lever"]["arm_readback_gate"]
        self.assertEqual(gate["expected_values"], EXPECTED_ARMS)
        self.assertEqual(gate["every"], "task_arm_repetition")
        self.assertTrue(gate["prelaunch_settings_and_environment_readback"])
        self.assertTrue(gate["effective_coordinator_and_child_readback_required"])
        self.assertFalse(gate["qualified"])
        self.assertEqual(gate["unqualified_action"], "do_not_launch")
        self.assertEqual(gate["mismatch_action"], "stop_entire_run_incomplete")
        self.assertEqual(spec["decision_rule"]["no_selection_host_action"],
                         "leave_incumbent_B_unchanged_no_reversion_to_A")

    def test_B1_observes_untracked_and_ignored_paths_and_projects_predicates(self):
        spec = self.spec()
        adapter = spec["oracle_framework"]["adapters"]["B1"]
        contract = adapter["contract"]
        self.assertIn("changed_path_derivation", contract)
        derivation = contract["changed_path_derivation"]
        self.assertEqual(derivation["status_argv"], [
            "git", "status", "--porcelain=v1", "--untracked-files=all",
            "--ignored=traditional", "-z",
        ])
        self.assertEqual(derivation["base_revision"], spec["reference_revision"])
        self.assertEqual(derivation["include_statuses"], ["tracked", "untracked", "ignored"])
        self.assertEqual(derivation["ignored_file_policy"], "compare_before_after_paths_and_sha256")
        self.assertEqual(derivation["rename_policy"], "include_both_paths")
        self.assertFalse(derivation["index_writes_required"])
        check = spec["tasks"][0]["checks"][0]
        self.assertEqual(contract["procedure"], check["procedure"])
        self.assertNotIn("final git diff names", check["procedure"])
        good = adapter["controls"]["known_pass"]["fixture"]
        target = good["target"]
        self.assertNotIn("red_exit", target)
        self.assertNotIn("changed_paths", target)
        self.assertIs(target["red_exit_nonzero"], True)
        self.assertIs(target["changed_paths_subset_including_reader"], True)
        reader = "examples/claude-native/workflows/child-usage.mjs"
        regression = "examples/claude-native/workflows/test-compaction-summary.mjs"
        self.assertEqual(set(derivation["allowed_paths"]), {reader, regression})
        # Independent boundary examples check the written projection, not an
        # unmaterialized adapter. Exit 2 is as valid a red result as exit 1.
        cases = contract["predicate_examples"]
        self.assertTrue(any(row["red_exit"] == 2 for row in cases))
        self.assertTrue(any(row["changed_paths"] == [reader] for row in cases))
        self.assertTrue(any("forbidden.py" in row["changed_paths"] for row in cases))
        for row in cases:
            with self.subTest(example=row["id"]):
                paths = set(row["changed_paths"])
                self.assertEqual(row["red_exit_nonzero"], row["red_exit"] != 0)
                self.assertEqual(row["changed_paths_subset_including_reader"],
                                 reader in paths and paths <= {reader, regression})

    def test_R1_tolerances_and_pinned_source_are_boolean_predicates(self):
        adapter = self.spec()["oracle_framework"]["adapters"]["R1"]
        contract = adapter["contract"]
        target = adapter["controls"]["known_pass"]["fixture"]["target"]
        self.assertNotIn("citation_spans", target)
        self.assertIs(target["cites_pinned_reader_sha"], True)
        self.assertEqual(target["citation_predicates"], [True, True, True])
        self.assertEqual(contract["extra_lines_each_side_max"], 5)
        self.assertEqual(contract["required_source_spans"], [[458, 458], [460, 460], [542, 548]])
        source = contract["citation_source"]
        self.assertEqual(source["path"], "examples/claude-native/workflows/child-usage.mjs")
        self.assertEqual(source["revision"], self.spec()["reference_revision"])
        self.assertEqual(source["sha256"], "f5ea9c3a1b47cab91e90a515f455bcf6a960fb696db89717e04b7424e4ff42a0")
        cases = contract["predicate_examples"]
        self.assertTrue(any(row["spans"][0] == [456, 460] for row in cases))
        self.assertTrue(any(not row["cites_pinned_reader_sha"] for row in cases))
        self.assertTrue(any(False in row["citation_predicates"] for row in cases))
        for row in cases:
            with self.subTest(example=row["id"]):
                predicates = [
                    max(1, required_start - 5) <= start <= required_start
                    and required_end <= end <= required_end + 5
                    for (start, end), (required_start, required_end)
                    in zip(row["spans"], contract["required_source_spans"], strict=True)
                ]
                self.assertEqual(row["citation_predicates"], predicates)
                self.assertEqual(row["cites_pinned_reader_sha"], row["source"] == source)

    def test_collector_gate_covers_every_used_log_attribute(self):
        ledger = self.spec()["metrics"]["request_ledger"]
        gate = ledger["qualification"]
        self.assertIn("required_log_attributes", gate)
        required = set(gate["required_log_attributes"])
        self.assertTrue({
            "request_id", "client_request_id", "server_fallback_hop", "speed",
            "workflow.run_id", "query_source", "attempt", "model", "session.id",
            "event.name", "event.timestamp", "event.sequence", "input_tokens",
            "output_tokens", "cache_creation_tokens", "cache_read_tokens",
        } <= required)
        collector = (ROOT / "observability/collector/collector.yaml").read_text()
        lists = re.findall(r"keep_keys\(attributes, (\[[^\n]+\])\)", collector)
        log_keys = next(set(json.loads(keys)) for keys in lists if '"event.name"' in keys)
        self.assertEqual(set(gate["template_missing_log_attributes"]), required - log_keys)
        self.assertFalse(gate["attribute_preservation_proven"])
        self.assertEqual(gate["unqualified_action"], "do_not_launch")
        self.assertTrue(gate["missing_applicable_attribute_is_unknown"])
        self.assertTrue({"agent_id", "parent_agent_id"}.isdisjoint(ledger["attribution"]))
        self.assertNotIn("attempt", ledger["required_attributes"])
        self.assertIn("speed", ledger["required_attributes"])

    def test_log_ledger_does_not_claim_intermediate_retry_or_error_usage(self):
        spec = self.spec()
        ledger = spec["metrics"]["request_ledger"]
        self.assertIn("retry_observability", ledger)
        retry = ledger["retry_observability"]
        self.assertEqual(retry["scope"], "terminal_chains_only")
        self.assertFalse(retry["intermediate_attempts_observed"])
        self.assertFalse(retry["traces_collected"])
        self.assertFalse(retry["api_request_has_attempt"])
        self.assertFalse(retry["api_error_has_token_counters"])
        self.assertEqual(retry["api_error_attempt_meaning"], "total_attempts_including_initial")
        self.assertEqual(retry["terminal_error_action"], "stop_entire_run_incomplete")
        self.assertEqual(spec["stop_rules"]["on_terminal_api_error"], "stop_entire_run_incomplete")
        self.assertNotIn("retry", ledger["include"])
        self.assertNotIn("client_request_id plus attempt", ledger["join"])
        self.assertFalse(retry["complete_retry_accounting_qualified"])
        self.assertEqual(retry["unqualified_action"], "do_not_launch")

    def test_provider_key_is_a_sealed_run_constant_and_missing_ids_stay_unknown(self):
        ledger = self.spec()["metrics"]["request_ledger"]
        self.assertIn("run_constants", ledger)
        self.assertEqual(ledger["run_constants"]["provider"], "anthropic_api")
        self.assertEqual(ledger["deduplication"]["key"], ["provider", "request_id"])
        missing = ledger["deduplication"]["missing_request_id"]
        self.assertEqual(missing["holding_key"], ["session.id", "event.sequence", "event.name"])
        self.assertFalse(missing["holding_key_is_usage_dedup_key"])
        self.assertEqual(missing["action"], "stop_entire_run_incomplete")

    def test_cache_write_price_is_unknown_without_request_ttl_split(self):
        cost = self.spec()["metrics"]["weighted_cost"]
        self.assertIn("cache_write_ttl_evidence", cost)
        ttl = cost["cache_write_ttl_evidence"]
        self.assertEqual(ttl["status"], "not_evaluable_from_current_ledger")
        self.assertFalse(ttl["otel_has_ttl_split"])
        self.assertIsNone(ttl["qualified_per_request_source"])
        self.assertFalse(ttl["configuration_proves_ttl"])
        self.assertEqual(ttl["missing_action"], "weighted_cost_unknown_no_selection")
        self.assertEqual(ttl["unqualified_action"], "do_not_launch")

    def test_wall_budget_includes_all_washouts_and_qualified_drains(self):
        spec = self.spec()
        stops = spec["stop_rules"]
        self.assertIn("whole_run_wall_cap", stops)
        wall = stops["whole_run_wall_cap"]
        attempts = spec["execution"]["planned_attempts"]
        self.assertEqual(wall["attempts"], attempts)
        self.assertEqual(wall["washouts"], attempts - 1)
        self.assertEqual(wall["drains"], attempts)
        self.assertEqual(wall["fixed_seconds"],
                         attempts * stops["attempt_wall_cap_seconds"]
                         + (attempts - 1) * spec["thresholds"]["washout_seconds"])
        self.assertEqual(wall["fixed_seconds"], 271800)
        self.assertEqual(wall["formula"], "271800 + 36 * qualified_drain_bound_seconds + qualified_readiness_bound_seconds")
        self.assertIsNone(wall["qualified_drain_bound_seconds"])
        self.assertIsNone(wall["qualified_readiness_bound_seconds"])
        self.assertIsNone(stops["whole_run_wall_cap_seconds"])
        self.assertFalse(wall["qualified"])
        self.assertEqual(wall["unqualified_action"], "do_not_launch")


if __name__ == "__main__":
    unittest.main()
