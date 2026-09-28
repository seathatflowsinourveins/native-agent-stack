"""Draft contract; follows test_token_e2e_preregistration.py at 341ba641.

These are structural checks, not Claude execution or compaction acceptance.
The public seam is the JSON protocol and its human-readable contract table.
"""

from fractions import Fraction
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
    "selection_rule": "Among quality-eligible candidates meeting the 10% pooled and per-task cost margin versus A, choose the unique lowest pooled all-attempt weighted child cost per successful task; an exact cost tie yields no selection and leaves the incumbent host setting A unchanged.",
    "incomplete_rule": "Any stopped, invalid, underlength, or unmeasured run is incomplete; no adoption result.",
}
# 2026-09-27 host-condition amendment. The coordinator-supplied /context
# display on 2.1.283 shows a constant 33k autocompact buffer, so each expected
# automatic trigger is window - 33000 (A uses the model's 1M window).
MODEL_WINDOW = 1000000
AMENDMENT_HEADING = "Amendment 2026-09-27 — host-condition change (incumbent A), still DRAFT"
EXPECTED_TRIGGERS = {"A": 967000, "B": 367000, "C": 167000}
# Partition bands: lower = 0.9 x trigger; upper = the next-higher arm's lower
# bound (exclusive); A's upper bound is the model window (inclusive).
EXPECTED_BANDS = {
    "C": {"lower_tokens": 150300, "upper_tokens": 330300, "upper_inclusive": False},
    "B": {"lower_tokens": 330300, "upper_tokens": 870300, "upper_inclusive": False},
    "A": {"lower_tokens": 870300, "upper_tokens": 1000000, "upper_inclusive": True},
}
ARM_TABLE_HEADER = ("| Arm | CLAUDE_CODE_AUTO_COMPACT_WINDOW | Expected threshold "
                    "| Validity band for automatic preTokens |")
ABSENT_IN_EVERY_ARM = {
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "CLAUDE_CODE_MAX_OUTPUT_TOKENS", "CLAUDE_CODE_DISABLE_1M_CONTEXT",
}
# Current (non-history) text must not keep B as the incumbent or forbid a
# "reversion to A"; dated history and superseded records are excluded.
FORBIDDEN_CURRENT_WORDING = (
    re.compile(r"(?i:incumbent)[^.,;:\n]{0,24}?(?<![A-Za-z0-9])B(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])(?i:revers?(?:ion|t|ting|ted))(?:[\s_/]+[\w-]+){0,5}?"
               r"[\s_]+to[\s_]+A(?![A-Za-z0-9])"),
)
JSON_HISTORY_PATHS = {("anti_pattern_log",), ("host_condition", "superseded_conditions")}


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
                "A": "window 1000000 (model); trigger about 967000 tokens",
                "B": "window 400000; trigger about 367000 tokens",
                "C": "window 200000; trigger about 167000 tokens",
            }[arm["id"]]
            band = {"A": "[870300, 1000000]", "B": "[330300, 870300)", "C": "[150300, 330300)"}[arm["id"]]
            self.assertIn(f"| {arm['id']} | {value} | {threshold} | {band} |", markdown)
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
            "observed_autocompact_buffer_tokens": 33000,
            "B_expected_trigger_tokens": 367000,
            "C_expected_trigger_tokens": 167000,
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

    @staticmethod
    def markdown():
        return (BLUEPRINT / "PREREGISTRATION.md").read_text()

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
        self.assertEqual(rule["tie_rule"], "exact_unrounded_tie_no_selection_incumbent_A_unchanged")
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
        # Amended 2026-09-27: the user-settings key is absent, so the host
        # incumbent is A (native default); the 18:59Z record is superseded history.
        self.assertEqual(host["incumbent_arm"], "A")
        self.assertIsNone(host["value"])
        self.assertEqual(host["value"], EXPECTED_ARMS[host["incumbent_arm"]])
        self.assertEqual(host["settings_value_state"], "absent")
        self.assertEqual(host["settings_file"], "~/.claude/settings.json")
        self.assertEqual(host["settings_scope"], "user")
        self.assertEqual(host["mechanism"], "env")
        self.assertEqual(host["amendment"], AMENDMENT_HEADING)
        self.assertIn(f"## {AMENDMENT_HEADING}", self.markdown())
        change = host["change"]
        self.assertEqual(change["provenance"], "coordinator_supplied_not_replayed")
        self.assertEqual(change["settings_file_mtime_utc"], "2026-09-27T23:21:57Z")
        self.assertIsNone(change["change_instant_utc"])
        observation = host["coordinator_observation"]
        self.assertEqual(observation["provenance"], "coordinator_supplied_not_replayed")
        self.assertEqual(observation["settings_readback_output"], "absent")
        self.assertEqual(observation["coordinator_shell_value"], "400000")
        self.assertEqual(host["drift_action"],
                         "do_not_launch_until_dated_amendment_records_new_host_condition")
        superseded = host["superseded_conditions"]
        self.assertEqual(len(superseded), 1)
        old = superseded[0]
        self.assertEqual(old["superseded_by"], AMENDMENT_HEADING)
        self.assertEqual(old["value"], "400000")
        self.assertEqual(old["activated_at"], "2026-09-27T18:59:00Z")
        self.assertEqual(old["incumbent_arm"], "B")
        self.assertEqual(old["coordinator_observation"]["shell_value"], "400000")
        self.assertEqual(old["coordinator_observation"]["first_request_auto_compaction_tokens"], 902612)
        self.assertEqual(old["coordinator_observation"]["provenance"], "coordinator_supplied_not_replayed")
        # Sessions started before the removal keep 400000 in their process
        # environment, so A still strips the key from its launch environment.
        per_arm = spec["native_lever"]["settings_isolation"]["per_arm_environment"]
        self.assertIn("env -u CLAUDE_CODE_AUTO_COMPACT_WINDOW", per_arm["A"])
        self.assertIn("400000", per_arm["A"])

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
        self.assertEqual(spec["decision_rule"]["no_selection_host_action"], "leave_incumbent_A_unchanged")
        self.assertIn("incumbent A", spec["evidence"]["receipt_status_meaning"]["complete_no_change"])
        adoption = spec["sealing"]["adoption_rule"]
        self.assertIn("confirmatory cohort", adoption)
        self.assertIn("non-inferior quality", adoption)

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

    @staticmethod
    def contains(band, value):
        lower, upper = band["lower_tokens"], band["upper_tokens"]
        above = value >= lower if band["lower_inclusive"] else value > lower
        below = value <= upper if band["upper_inclusive"] else value < upper
        return above and below

    @staticmethod
    def notation(band):
        opening = "[" if band["lower_inclusive"] else "("
        closing = "]" if band["upper_inclusive"] else ")"
        return f"{opening}{band['lower_tokens']}, {band['upper_tokens']}{closing}"

    @staticmethod
    def table_rows(markdown, header):
        lines = markdown.splitlines()
        rows = []
        for line in lines[lines.index(header) + 2:]:
            if not line.startswith("|"):
                break
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        return rows

    @staticmethod
    def bands(spec):
        return spec["native_lever"]["treatment_proof"]["validity_bands"]

    def test_expected_triggers_are_window_minus_observed_buffer(self):
        spec = self.spec()
        thresholds = spec["thresholds"]
        self.assertIn("observed_autocompact_buffer_tokens", thresholds)
        buffer = thresholds["observed_autocompact_buffer_tokens"]
        self.assertEqual(buffer, 33000)
        self.assertEqual(thresholds["B_expected_trigger_tokens"], thresholds["B_window_tokens"] - buffer)
        self.assertEqual(thresholds["C_expected_trigger_tokens"], thresholds["C_window_tokens"] - buffer)
        # Corroborates the documented "about 967K" default of a native 1M window.
        self.assertEqual(thresholds["default_approx_tokens"], MODEL_WINDOW - buffer)
        lever = spec["native_lever"]
        self.assertIn("autocompact_buffer_observation", lever)
        observation = lever["autocompact_buffer_observation"]
        self.assertEqual(observation["provenance"], "coordinator_supplied_not_replayed")
        self.assertEqual(observation["evidence_class"], "native_display_observation_not_a_compaction_event")
        self.assertEqual(observation["client_version"], spec["shared_controls"]["client_version"])
        self.assertEqual(observation["buffer_tokens"], buffer)
        self.assertEqual(observation["model_window_tokens"], MODEL_WINDOW)
        self.assertEqual(set(observation["returned_lines"]), {"unset", "400000", "200000", "100000"})
        for window, lines in observation["returned_lines"].items():
            with self.subTest(window=window):
                self.assertEqual(sum(line.startswith("| Autocompact buffer | 33k |") for line in lines), 1)
        self.assertEqual(observation["expected_trigger_tokens"], EXPECTED_TRIGGERS)
        for arm_id, band in self.bands(spec)["arms"].items():
            with self.subTest(arm=arm_id):
                self.assertEqual(band["expected_trigger_tokens"], band["window_tokens"] - buffer)
        gate = lever["arm_readback_gate"]
        self.assertEqual(gate["expected_effective_window_tokens"], {"A": MODEL_WINDOW, "B": 400000, "C": 200000})
        self.assertEqual(gate["expected_automatic_trigger_tokens"], EXPECTED_TRIGGERS)
        # A peer's binary reading is recorded as undocumented and not relied on.
        self.assertIs(observation["relies_on_undocumented_implementation_reading"], False)
        reading = observation["peer_implementation_reading"]
        self.assertEqual(reading["provenance"], "peer_supplied_undocumented_implementation_reading")
        self.assertIs(reading["relied_on"], False)

    def test_partition_bands_anchor_below_each_trigger_and_tile_the_range(self):
        spec = self.spec()
        proof = spec["native_lever"]["treatment_proof"]
        self.assertIn("validity_bands", proof)
        bands = proof["validity_bands"]
        self.assertEqual(bands["rule"], "partition")
        arms = bands["arms"]
        self.assertEqual(set(arms), {"A", "B", "C"})
        thresholds = spec["thresholds"]
        triggers = {"A": thresholds["default_approx_tokens"], "B": thresholds["B_expected_trigger_tokens"],
                    "C": thresholds["C_expected_trigger_tokens"]}
        self.assertEqual(triggers, EXPECTED_TRIGGERS)
        for arm_id, band in arms.items():
            with self.subTest(arm=arm_id):
                self.assertEqual(band["expected_trigger_tokens"], triggers[arm_id])
                # A 10% tolerance below the trigger, in exact integer arithmetic.
                self.assertEqual(band["lower_tokens"] * 10, band["expected_trigger_tokens"] * 9)
                self.assertIs(band["lower_inclusive"], True)
                self.assertEqual({key: band[key] for key in EXPECTED_BANDS[arm_id]}, EXPECTED_BANDS[arm_id])
                self.assertEqual(band["notation"], self.notation(band))
        # Contiguous: each upper bound is the next-higher arm's lower bound, exclusive.
        self.assertEqual(arms["C"]["upper_tokens"], arms["B"]["lower_tokens"])
        self.assertEqual(arms["B"]["upper_tokens"], arms["A"]["lower_tokens"])
        self.assertIs(arms["C"]["upper_inclusive"], False)
        self.assertIs(arms["B"]["upper_inclusive"], False)
        # Disjoint: every bound, and the value just below it, lies in exactly one band.
        bounds = {band[key] for band in arms.values() for key in ("lower_tokens", "upper_tokens")}
        probes = bounds | {bound - 1 for bound in bounds if bound - 1 >= arms["C"]["lower_tokens"]}
        for value in sorted(probes):
            with self.subTest(value=value):
                self.assertEqual(sum(self.contains(band, value) for band in arms.values()), 1)
        # A is unchanged: 870300..1000000 inclusive, capped at the model window.
        self.assertEqual((arms["A"]["lower_tokens"], arms["A"]["upper_tokens"]), (870300, MODEL_WINDOW))
        self.assertIs(arms["A"]["upper_inclusive"], True)
        self.assertIn("870300..1000000", proof["A"])
        self.assertIn("validity rule, not an upstream guarantee", bands["scope"])
        self.assertIn("dated amendment", bands["client_change_rule"])

    def test_bands_hold_each_trigger_and_relayed_native_event_in_exactly_one_arm(self):
        spec = self.spec()
        lever = spec["native_lever"]
        self.assertIn("relayed_native_auto_compaction_events", lever)
        events = lever["relayed_native_auto_compaction_events"]
        self.assertEqual(events["provenance"], "peer_a9_value_level_coordinator_relayed_not_replayed")
        running_b = events["sessions_running_400000"]
        self.assertEqual((running_b["n"], running_b["min"], running_b["median"], running_b["max"]),
                         (31, 366209, 368563, 432724))
        default = events["before_key_added"]
        self.assertEqual((default["min"], default["max"]), (966908, 971662))
        transition = events["pre_switch_launched_sessions"]
        self.assertEqual(transition["attribution_status"], "transition_documented_mechanism")
        self.assertIn("applies new and changed settings env values when the file is saved", transition["attribution"])
        self.assertIn("--setting-sources project", transition["arm_consequence"])
        self.assertLess(transition["max"], default["min"],
                        "a transition event at or above the lowest default-window trigger would need its own attribution")
        bands = self.bands(spec)
        arms = bands["arms"]
        members = {
            "C": [EXPECTED_TRIGGERS["C"]],
            "B": [EXPECTED_TRIGGERS["B"], running_b["min"], running_b["median"], running_b["max"]],
            "A": [EXPECTED_TRIGGERS["A"], default["min"], default["max"]],
        }
        for arm_id, values in members.items():
            for value in values:
                with self.subTest(arm=arm_id, value=value):
                    self.assertEqual([name for name, band in arms.items() if self.contains(band, value)], [arm_id])
        # Why the rule changed before any cohort: the superseded window-centred C
        # band excluded C's own trigger, and the considered symmetric 10% B band
        # would have excluded the relayed 432724 event.
        self.assertEqual(bands["superseded_window_centred"], {"B": [360000, 440000], "C": [180000, 220000]})
        low, high = bands["superseded_window_centred"]["C"]
        self.assertFalse(low <= EXPECTED_TRIGGERS["C"] <= high)
        self.assertEqual(bands["considered_symmetric_ten_percent"], {"B": [330300, 403700], "C": [150300, 183700]})
        low, high = bands["considered_symmetric_ten_percent"]["B"]
        self.assertFalse(low <= running_b["max"] <= high)

    def test_markdown_tables_match_json_windows_triggers_bands_and_thresholds(self):
        spec = self.spec()
        markdown = self.markdown()
        current = markdown.split("\n## Amendment ", 1)[0]
        self.assertIn(ARM_TABLE_HEADER, markdown.splitlines())
        arms = self.bands(spec)["arms"]
        rows = self.table_rows(markdown, ARM_TABLE_HEADER)
        self.assertEqual([row[0] for row in rows], ["A", "B", "C"])
        for arm_id, value, threshold, band in rows:
            with self.subTest(arm=arm_id):
                record = arms[arm_id]
                expected = EXPECTED_ARMS[arm_id]
                self.assertEqual(value, "unset" if expected is None else expected)
                if expected is not None:
                    self.assertEqual(record["window_tokens"], int(expected))
                window = f"{record['window_tokens']} (model)" if expected is None else expected
                self.assertEqual(threshold,
                                 f"window {window}; trigger about {record['expected_trigger_tokens']} tokens")
                self.assertEqual(band, record["notation"])
                self.assertIn(f"{arm_id} **{record['notation']}**", current)
        contract = dict(self.table_rows(markdown, "| Key | Value |"))
        for key in ("observed_autocompact_buffer_tokens", "B_expected_trigger_tokens", "C_expected_trigger_tokens"):
            self.assertIn(key, contract)
        for key, value in spec["thresholds"].items():
            with self.subTest(key=key):
                self.assertEqual(contract[key], str(value))
        for key in RULES:
            self.assertEqual(contract[key], spec["decision_rule"][key])

    def json_text(self, value, path=()):
        if path in JSON_HISTORY_PATHS:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                yield path + (key,), key
                yield from self.json_text(item, path + (key,))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from self.json_text(item, path + (index,))
        elif isinstance(value, str):
            yield path, value

    def test_current_text_names_A_as_incumbent_without_reversion_wording(self):
        # Discriminating controls for the wording patterns themselves.
        for text in ("leave_incumbent_B_unchanged_no_reversion_to_A",
                     "exact_unrounded_tie_no_selection_incumbent_B_unchanged",
                     "leaves the incumbent host setting B unchanged",
                     "The incumbent host arm is **B**",
                     "reverting the already-active incumbent B to A",
                     "it does not retain/revert to A or newly adopt B"):
            self.assertTrue(any(p.search(text) for p in FORBIDDEN_CURRENT_WORDING), text)
        for text in ("leave_incumbent_A_unchanged",
                     "leaves incumbent A (key absent, native default) unchanged. Setting B or C",
                     "Sessions started before the removal keep 400000"):
            self.assertFalse(any(p.search(text) for p in FORBIDDEN_CURRENT_WORDING), text)
        for path, text in self.json_text(self.spec()):
            for pattern in FORBIDDEN_CURRENT_WORDING:
                self.assertIsNone(pattern.search(text), f"{'/'.join(map(str, path))}: {text}")
        markdown = self.markdown()
        self.assertIn("\n## Amendment ", markdown)
        current = markdown.split("\n## Amendment ", 1)[0]
        for pattern in FORBIDDEN_CURRENT_WORDING:
            match = pattern.search(current)
            self.assertIsNone(match, match and current[max(0, match.start() - 80):match.end() + 20])

    def test_size07_utilization_is_a_descriptive_secondary_outcome_outside_selection(self):
        spec = self.spec()
        self.assertIn("context_utilization_secondary", spec["metrics"])
        outcome = spec["metrics"]["context_utilization_secondary"]
        self.assertEqual(outcome["role"], "descriptive_secondary_outcome_only")
        self.assertIs(outcome["enters_selection"], False)
        self.assertIs(outcome["powered_for_size_07_overturn"], False)
        self.assertIs(outcome["adds_quality_superiority_selection_path"], False)
        self.assertEqual(outcome["utilization_denominator_tokens"], MODEL_WINDOW)
        self.assertEqual(set(outcome["reported_per_task_and_arm"]), {
            "check_outcomes", "focal_child_peak_prompt_tokens", "focal_child_peak_window_utilization",
        })
        sources = {source["id"]: source for source in spec["sources"]}
        self.assertEqual(set(outcome["source_ids"]), {"size_07", "community_sweep_m3"})
        self.assertEqual((sources["size_07"]["path"], sources["size_07"]["line"]),
                         ("docs/harness-rules-convergence-20260922.md", 207))
        self.assertEqual((sources["community_sweep_m3"]["path"], sources["community_sweep_m3"]["line"]),
                         ("docs/decisions/2026-09-24-community-sweep.md", 172))
        # The A eligibility rule (> 400000 prompt tokens) and the B/C triggers
        # already contrast utilization above and below 40% of the 1M window.
        thresholds = spec["thresholds"]
        forty_percent = Fraction(2, 5)
        self.assertEqual(Fraction(thresholds["long_child_prompt_tokens_exclusive"], MODEL_WINDOW), forty_percent)
        self.assertLess(Fraction(thresholds["B_expected_trigger_tokens"], MODEL_WINDOW), forty_percent)
        self.assertLess(Fraction(thresholds["C_expected_trigger_tokens"], MODEL_WINDOW), forty_percent)
        self.assertNotIn("utilization", json.dumps(spec["decision_rule"]).lower())
        # The current protocol paragraph itself, not the amendment record, must
        # carry both limits.
        current = self.markdown().split("\n## Amendment ", 1)[0]
        heading = "**Secondary descriptive outcome (SIZE-07).**"
        self.assertIn(heading, current)
        paragraph = current[current.index(heading):].split("\n\n", 1)[0]
        self.assertIn("**not powered**", paragraph)
        self.assertIn("does not enter selection", paragraph)

    def test_readback_gate_requires_window_modifiers_absent_in_every_arm(self):
        spec = self.spec()
        gate = spec["native_lever"]["arm_readback_gate"]
        self.assertIn("must_be_absent_in_every_arm", gate)
        absent = gate["must_be_absent_in_every_arm"]
        self.assertEqual(set(absent), ABSENT_IN_EVERY_ARM)
        must_be_unset = spec["shared_controls"]["must_be_unset"]
        for key, reason in absent.items():
            with self.subTest(key=key):
                self.assertIn(key, must_be_unset)
                self.assertTrue(reason.strip())
        self.assertIn("can't raise the threshold", absent["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"])
        self.assertIn("reduces the effective context window", absent["CLAUDE_CODE_MAX_OUTPUT_TOKENS"])
        current = self.markdown().split("\n## Amendment ", 1)[0]
        for key in ABSENT_IN_EVERY_ARM:
            self.assertIn(f"`{key}`", current)


if __name__ == "__main__":
    unittest.main()
