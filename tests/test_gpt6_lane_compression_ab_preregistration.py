"""Local structural checks, not a model run or upstream harness acceptance.

Reference seam: tests/test_token_e2e_preregistration.py at 0f76651d;
the #416 compaction draft supplies document structure only.
"""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/gpt6-lane-compression-ab"
ENGINES = {
    "session-dedup", "ccr", "lite", "rtk", "codex-responses", "headroom",
    "relevance", "caveman", "aggressive", "llmlingua", "ultra", "omniglyph",
}
SAFE_LABELS = {"session-dedup", "ccr", "lite", "headroom"}
ROLES = {"builder", "reviewer", "researcher"}


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


class CompressionPreregistrationTests(unittest.TestCase):
    def test_draft_contract(self):
        # Fail first at the public document boundary, before either file exists.
        self.assertTrue((BLUEPRINT / "preregistration.json").is_file(),
                        "preregistration.json does not exist yet")
        self.assertTrue((BLUEPRINT / "PREREGISTRATION.md").is_file())
        data = json.loads((BLUEPRINT / "preregistration.json").read_text())
        prose = (BLUEPRINT / "PREREGISTRATION.md").read_text()

        with self.subTest(contract="honest draft"):
            self.assertEqual(data["status"], "DRAFT")
            self.assertFalse(data["frozen"])
            self.assertFalse(data["run_started"])
            self.assertFalse(data["execution_authorized"])
            self.assertIsNone(data["results"])
            self.assertIsNone(data["sealing"]["sealed_at"])
            self.assertIn("DRAFT", prose)
            self.assertEqual(data["client"]["version"], "0.157.1")
            self.assertEqual(data["client"]["profile"], "stack-worker")
            self.assertEqual(data["client"]["effort"], "max")

        cells = {cell["id"]: cell for cell in data["cells"]}
        with self.subTest(contract="clean control and crossed factors"):
            self.assertEqual(set(cells), {"C", "D0", "D1", "A0", "A1"})
            self.assertEqual(cells["C"]["base_url"], "http://127.0.0.1:20128/v1")
            self.assertEqual(cells["C"]["model"], "cx/gpt-6-astra-max")
            self.assertEqual(cells["C"]["engines"], [])
            for cell_id in ("D0", "D1", "A0", "A1"):
                cell = cells[cell_id]
                self.assertEqual(cell["classification"], "confirmatory")
                self.assertEqual(cell["base_url"], "http://127.0.0.1:20129/v1")
                self.assertEqual(cell["model"], "sharedgw/gpt-6-astra-max")
                self.assertEqual(set(cell["engines"]),
                                 SAFE_LABELS if cell_id[0] == "D" else ENGINES)
                self.assertEqual(cell["compression_header"],
                                 None if cell_id[0] == "D" else "allow-lossy")
                self.assertEqual(cell["output_styles_on"], cell_id.endswith("1"))
            self.assertFalse(data["factorization"]["header_off_is_clean_control"])
            self.assertEqual(set(data["exploratory"]["single_engine_order"]),
                             ENGINES - SAFE_LABELS)
            self.assertEqual(data["factorization"]["keyed_live_zone"]["ttl_minutes"], 60)
            self.assertEqual(data["factorization"]["keyed_live_zone"]["key_file_mode"], "0600")
            self.assertFalse(data["exploratory"]["allows_promotion"])

        with self.subTest(contract="frozen task packets and controls"):
            self.assertEqual(set(data["task_sets"]), ROLES)
            for role, packet in data["task_sets"].items():
                self.assertEqual(packet["sha256"], digest(packet["packet"]), role)
                self.assertIn(packet["sha256"], prose)
                tasks = packet["packet"]["tasks"]
                self.assertGreaterEqual(len(tasks), 3)
                self.assertEqual(len(tasks), len({t["id"] for t in tasks}))
                for task in tasks:
                    self.assertTrue(task["prompt"])
                    self.assertTrue(task["oracle"])
                    self.assertTrue(task["source_ids"])
                    if role != "builder":
                        examples = task["grader_controls"]
                        self.assertEqual(json.loads(examples[0]["output"]),
                                         task["expected"])
                        self.assertNotEqual(json.loads(examples[1]["output"]),
                                            task["expected"])
                        with self.assertRaises(json.JSONDecodeError):
                            json.loads(examples[2]["output"])
                controls = packet["packet"]["controls"]
                self.assertEqual({c["kind"] for c in controls},
                                 {"known-pass", "known-fail", "malformed"})
                self.assertEqual([c["expected_accept"] for c in controls],
                                 [True, False, False])
                self.assertNotEqual(controls[0]["input"], controls[1]["input"])
                self.assertNotEqual(controls[0]["input"], controls[2]["input"])
            canaries = data["canaries"]
            self.assertEqual(canaries["sha256"], digest(canaries["packet"]))
            self.assertIn("1234567890123456711", canaries["packet"]["numeric_tool_output"])
            self.assertIn("1.50", canaries["packet"]["numeric_tool_output"])
            self.assertGreater(len(canaries["packet"]["long_tool_output"]), 2000)
            self.assertGreater(canaries["packet"]["long_tool_output"].index("TAIL_PIN="), 2000)
            self.assertEqual(set(canaries["packet"]["roles"]), ROLES)
            self.assertIn("multipart", canaries["packet"]["dedup_probe"])
            numeric = canaries["packet"]["numeric_engine_tool_output"]
            self.assertGreater(len(numeric.encode()), 512)
            lexical = json.loads(numeric, parse_int=str, parse_float=str)
            self.assertEqual(lexical["integer"], "1234567890123456711")
            self.assertEqual(lexical["decimal"], "1.50")

        with self.subTest(contract="measurement boundaries"):
            metrics = {m["id"] for m in data["metrics"]}
            self.assertTrue({"task_success", "apply_patch_failures", "verification_failures",
                             "schema_retries", "tool_output_recall", "tokens_in",
                             "tokens_cache_read", "tokens_reasoning", "compression_savings",
                             "latency", "cancellations"} <= metrics)
            accounting = data["accounting"]
            self.assertEqual(accounting["usage_authority"], {
                "C": "20128.call_logs", "D0": "20129.call_logs",
                "D1": "20129.call_logs", "A0": "20129.call_logs",
                "A1": "20129.call_logs",
            })
            self.assertEqual(accounting["savings_authority"],
                             "20129.call_logs.tokens_compressed")
            self.assertFalse(accounting["add_savings_to_usage"])
            self.assertTrue(accounting["cache_read_is_input_subset"])
            self.assertTrue(accounting["reasoning_is_output_subset"])
            self.assertIsNone(accounting["output_column_verified_on_host"])
            self.assertIn("tokens_out", accounting["required_additional_columns"])
            self.assertIn("tokens_in - tokens_cache_read", accounting["uncached_input_formula"])
            self.assertEqual(accounting["total_billed_tokens_formula"],
                             "sum(tokens_in + tokens_out)")
            self.assertTrue(accounting["include_failed_retried_cancelled_attempts"])

        with self.subTest(contract="multi-turn transport and role gates"):
            multi = data["multi_turn"]
            self.assertGreaterEqual(multi["user_turns"], 3)
            self.assertTrue(multi["tools_required_each_turn"])
            self.assertEqual(multi["aggregation_unit"], "task/session/user_turn")
            self.assertTrue({"prompt_cache_key", "session_headers", "affinity_headers",
                             "store", "include", "encrypted_reasoning", "turn_2_tool_roundtrip"}
                            <= set(multi["required_checks"]))
            self.assertEqual(data["role_policy"]["early_canary_roles"], ["builder"])
            self.assertTrue({"reviewer", "researcher", "judgment", "verification", "evidence"}
                            <= set(data["role_policy"]["control_until_pass"]))
            self.assertTrue(data["role_policy"]["record_outputs_require_exact_preservation"])

        with self.subTest(contract="statistics and stopping are specified"):
            analysis = data["analysis"]
            self.assertIsNone(analysis["planned_repetitions_per_role_cell"])
            self.assertIsNone(analysis["expected_repetitions_per_task_cell"])
            self.assertIn("independent", analysis["sampling"])
            self.assertIsNone(analysis["total_confirmatory_sessions"])
            self.assertEqual(analysis["success_ni_margin"], 0.05)
            self.assertEqual(analysis["failure_ni_margin"], 0.05)
            self.assertEqual(analysis["multiplicity"]["method"], "holm")
            self.assertEqual(analysis["multiplicity"]["comparisons"], 12)
            self.assertTrue(analysis["degenerate_interval_guard"])
            self.assertIn("bootstrap", analysis["upstream_functions"])
            self.assertIn("permutation_test", analysis["upstream_functions"])
            self.assertTrue(data["decision_rule"]["per_role"])
            self.assertEqual(data["decision_rule"]["objective"],
                             "minimum total billed tokens among non-inferior cells")
            self.assertTrue(data["decision_rule"]["tie_rule"])
            self.assertEqual(data["decision_rule"]["minimum_absolute_combined_success_rate"],
                             0.90)
            budget = data["budget"]
            self.assertIsNone(budget["total_token_cap"])
            self.assertIsNone(budget["allocations"])
            self.assertEqual(budget["max_concurrent_sessions"], 1)
            self.assertTrue(budget["owned_process_cancellation"])
            self.assertTrue(budget["stop_conditions"])

        with self.subTest(contract="source-backed hazards and unresolved acceptance"):
            sources = {s["id"]: s for s in data["sources"]}
            self.assertTrue({"harbor-codex", "promptfoo-responses", "scipy", "statsmodels"}
                            <= set(sources))
            self.assertEqual({h["id"] for h in data["hazards"]},
                             {"H1", "H2", "H3", "H4", "H5", "H6"})
            for hazard in data["hazards"]:
                self.assertTrue(hazard["checks"])
                self.assertTrue(hazard["verification_status"])
                self.assertIsNone(hazard["live_result"])
                for source_id in hazard["source_ids"]:
                    self.assertIn(source_id, sources)
            for gate in data["open_host_gates"]:
                self.assertIsNone(gate["passed"])
            self.assertTrue(data["anti_pattern_log"])
            # Every source-backed contract addition must resolve to the inventory.
            def check_sources(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key in {"source_id", "source_ids"}:
                            for name in [item] if isinstance(item, str) else item:
                                self.assertIn(name, sources)
                        check_sources(item)
                elif isinstance(value, list):
                    for item in value:
                        check_sources(item)

            check_sources(data)

    def read_contract(self):
        return json.loads((BLUEPRINT / "preregistration.json").read_text())

    def test_b1_per_hop_names_and_unqualified_runner_cannot_seal(self):
        data = self.read_contract()
        self.assertEqual(data["client"].get("model_hops"), {
            "client_to_20129": "sharedgw/gpt-6-astra-max",
            "20129_to_20128": "gpt-6-astra-max",
            "control_C": "cx/gpt-6-astra-max",
        })
        runner = data["harnesses"]["primary"]
        self.assertEqual(runner["runner_choice"], "harbor-with-route-qualification")
        self.assertEqual(runner["actual_model_argument"], "gpt-6-astra-max")
        self.assertTrue(runner["sealing_blocked"])
        gate = runner["route_qualification"]
        self.assertIsNone(gate["result"])
        self.assertIn("prompt-input", gate["checks"])
        self.assertIn("live-200-max", gate["checks"])
        self.assertIn("control-route-equivalence", gate["checks"])
        self.assertTrue(runner["overturn_condition"])
        self.assertEqual(len(runner["alternatives"]), 3)

    def test_b2_merge_launch_network_and_native_resume(self):
        data = self.read_contract()
        merge = data["client"].get("profile_merge", {})
        self.assertEqual(merge.get("inputs"), ["config.toml", "stack-worker.config.toml"])
        self.assertEqual(set(merge["forbidden_keys"]), {"profile", "profiles"})
        self.assertIsNone(merge["sha256"])
        self.assertEqual(set(merge["equivalence"]["compare"]),
                         {"resolved-config", "prompt-input"})
        self.assertIsNone(merge["equivalence"]["result"])
        argv = data["client"]["argv_contract"]
        self.assertEqual(argv[:2], ["codex", "exec"])
        for flag in ("--dangerously-bypass-approvals-and-sandbox",
                     "--skip-git-repo-check", "--json", "--enable"):
            self.assertIn(flag, argv)
        self.assertNotIn("-p", argv)
        self.assertIn("unified_exec", argv)
        network = data["harnesses"]["primary"]["network"]
        self.assertEqual(network["overlay"]["services"]["main"]["network_mode"], "host")
        self.assertTrue(network["reachability_probe"])
        self.assertTrue(network["admin_api_exposure"])
        self.assertIsNone(network["result"])
        multi = data["multi_turn"]
        self.assertEqual(multi["native_route"], "Harbor [[steps]]")
        self.assertTrue(multi["resume_trajectory"])
        self.assertEqual(multi["task_turn_mapping"]["B-hello-multi-step-simple"],
                         ["create-file", "append-content", "exact-record"])

    def test_b3_pilot_sizes_complete_cohort_and_removes_priming(self):
        data = self.read_contract()
        pilot = data.get("qualification_pilot", {})
        self.assertEqual(pilot.get("phase"), "pre-confirmatory-data")
        self.assertTrue(pilot["excluded_from_confirmation"])
        self.assertEqual(set(pilot["cells"]), {"C", "D0", "D1", "A0", "A1"})
        self.assertTrue({"tokens", "wall_seconds", "paired_outcomes", "operational_events"}
                        <= set(pilot["measure"]))
        self.assertIsNone(pilot["results"])
        self.assertTrue(data["budget"]["sizing_rule"])
        self.assertIsNone(data["budget"]["whole_run_wall_seconds"])
        self.assertEqual(data["analysis"]["priming_sessions"], 0)
        self.assertEqual(data["analysis"]["cache_strata"], [1, 2, 3])

    def test_b4_entry_joins_effort_body_and_unknown_usage(self):
        accounting = self.read_contract()["accounting"]
        self.assertIn("correlation_id", accounting["required_columns"])
        self.assertEqual(accounting["correlation_capture"]["header"], "X-Correlation-Id")
        self.assertTrue(accounting["correlation_capture"]["source_ids"])
        self.assertIsNone(accounting["correlation_capture"]["qualified"])
        self.assertFalse(accounting["add_downstream_hop"])
        self.assertEqual(accounting["effort"]["field"], "reasoning.effort")
        self.assertEqual(accounting["effort"]["hops"], [20129, 20128])
        self.assertFalse(accounting["effort"]["null_column_is_drift"])
        self.assertTrue(accounting["effort"]["request_detail_route"])
        missing = accounting["missing_usage"]
        self.assertFalse(missing["zero_fill"])
        self.assertTrue(missing["request_size_is_not_total_bound"])
        self.assertTrue(missing["worst_case_ranking_required"])

    def test_b5_net_difference_power_and_unrecovered_failure(self):
        analysis = self.read_contract()["analysis"]
        ni = analysis.get("paired_net_test", {})
        self.assertEqual(ni.get("method"), "scipy.stats.bootstrap")
        self.assertTrue(ni["paired"])
        self.assertEqual(ni["alternative"], "less")
        self.assertEqual(ni["statistic"], "mean(control_success - candidate_success)")
        self.assertIn("beneficial", ni["exact_fallback"])
        self.assertEqual(analysis["multiplicity"]["unit"], "role-candidate intersection-union")
        self.assertTrue(analysis["operational_failure"]["unrecovered_only"])
        power = analysis["power_simulation"]
        self.assertGreaterEqual(power["target_power"], .80)
        self.assertTrue(power["joint_paired_outcomes"])
        self.assertTrue(power["margin_null_calibration"])
        self.assertIsNone(power["selected_n"])
        self.assertIsNone(power["results"])

    def test_keyed_confirmatory_env_and_no_ambient_openai_key(self):
        data = self.read_contract()
        key_name = "OMNIROUTE_FW_API_KEY"
        for cell in data["cells"]:
            if cell["id"] == "C":
                continue
            self.assertEqual(cell["principal"], "registered-lane-key")
            self.assertEqual(cell["env_key"], key_name)
            self.assertEqual(cell["live_zone_ttl_minutes"], 60)
        auth = data["client"]["environment_contract"]
        self.assertEqual(auth["extra_env"][key_name], "${" + key_name + "}")
        self.assertIn("OPENAI_API_KEY", auth["must_be_unset"])
        self.assertFalse(auth["static_auth_headers"])

    def test_canaries_have_reachable_shape_gates_and_valid_collision(self):
        data = self.read_contract()
        packet = data["canaries"]["packet"]
        self.assertEqual({row["shape"] for row in packet.get("numeric_shapes", [])},
                         {"shell", "mcp-text", "mcp-structuredContent", "custom-tool"})
        for row in packet["numeric_shapes"]:
            self.assertIsNone(row["native_result"])
            self.assertTrue(row["qualification"])
        messages = packet["dedup_messages"]
        self.assertEqual(len(messages[0]["content"]), 2)
        self.assertIn("EARLIER_USER_PIN=", messages[0]["content"][1]["text"])
        self.assertEqual(messages[1]["content"], messages[2]["content"])
        self.assertNotIn(messages[1]["content"], messages[0]["content"][1]["text"])
        self.assertEqual(packet["dedup_assert_unchanged"], "messages[0].content[1].text")
        self.assertTrue(data["oracle_contract"]["score_exactness_when_engine_not_applied"])
        self.assertTrue(data["oracle_contract"]["engine_coverage_separate"])
        self.assertEqual(data["factorization"]["sharedgw_wire_api"], "responses")

    def test_sensitivity_affinity_and_scope_are_explicit(self):
        data = self.read_contract()
        ranges = data["accounting"].get("sensitivity", {})
        self.assertEqual(ranges.get("cache_ratio"), [0.0, 1.0])
        self.assertEqual(ranges["output_ratio"], [1.0, 10.0])
        self.assertFalse(ranges["actual_price_claim"])
        affinity = data["multi_turn"]["affinity"]
        self.assertEqual(affinity["connection_pin"], "x-omniroute-connection")
        self.assertNotIn(affinity["connection_pin"], affinity["session_headers"])
        self.assertTrue(affinity["account_spread_by_arm"])
        self.assertTrue(affinity["body_derived_live_zone_fallback"])
        self.assertEqual(data["decision_rule"]["scope_ceiling"], "named synthetic task domains only")
        self.assertEqual(data["decision_rule"]["review_research_style_scope"], "JSON-only records")

    def test_all_review_findings_have_cited_round_dispositions(self):
        data = self.read_contract()
        round_record = data.get("repair_round_20260927", {})
        rows = round_record.get("findings", [])
        self.assertEqual({r["id"] for r in rows},
                         {f"B{i}" for i in range(1, 6)} |
                         {f"M{i}" for i in range(1, 11)} |
                         {f"m{i}" for i in range(1, 9)})
        self.assertEqual(len(rows), 23)
        for row in rows:
            self.assertIn(row["outcome"], {"fixed", "fixed by gating", "declined"})
            self.assertTrue(row["reason"])
            self.assertTrue(row["citations"])
            self.assertTrue(row["verification"])
        self.assertFalse(round_record["model_inference_performed"])
        self.assertFalse(round_record["git_metadata_written"])
        self.assertEqual(round_record["installed_hashes_checked"], 17)
        self.assertEqual(set(round_record["remaining_gates"]),
                         {gate["id"] for gate in data["open_host_gates"]})
        prose = (BLUEPRINT / "PREREGISTRATION.md").read_text()
        for row in rows:
            self.assertIn(f"| {row['id']} | {row['outcome']} |", prose)
        for gate in round_record["remaining_gates"]:
            self.assertIn(f"**{gate}**", prose)


if __name__ == "__main__":
    unittest.main()
