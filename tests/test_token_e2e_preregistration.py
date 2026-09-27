"""Offline preregistration contracts; never launch a model or workflow.

Sources: AA sections 8.1 and 8.3; PR-H build specification; unittest/path
conventions in tests/test_token_report_refresh_units.py:12-25.
"""

import json
import hashlib
from pathlib import Path
import re
import subprocess
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "evidence/artifacts/token-adoption-e2e-20260926"
# Independent AA 8.3 contract: do not derive this set from the manifest.
REQUIRED_LANES = {
    "ctx-containment", "fetch", "rtk-claude", "rtk-codex", "toon-seeded",
    "symbol-references", "qmd", "ai-memory", "adoption", "guidance",
    "blind", "binding", "attribution", "mcp-errors",
}
UUID_SHAPE = re.compile(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", re.I)


def load_tasks():
    with (BLUEPRINT / "preregistration.json").open(encoding="utf-8") as stream:
        return json.load(stream)


def tool_name_pattern(name):
    return r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"


class TokenE2EPreregistrationTests(unittest.TestCase):
    def test_machine_readable_policy_is_frozen(self):
        # AA 6:405-411, 8.3:585-629 and 8.5:648-652.
        data = load_tasks()
        for field in (
            "minimum_arm_b_opportunities", "thresholds", "m3_exceptions",
            "strict_blind_process", "outcome_rule", "overturn_conditions",
        ):
            with self.subTest(field=field):
                self.assertTrue(data.get(field), field)
        self.assertEqual(data.get("minimum_arm_b_opportunities"), 5)

    def test_threshold_values_match_aa(self):
        # Independent literals transcribed from AA 8.3, including optional rows.
        expected = {
            "M1": {"successful_opportunity_rate_gte": 0.90, "per_required_lane": True},
            "M2": {"successful_child_rate_gte": 0.90, "exclude_scout_and_blind": True},
            "M2b": {"descriptive_only": True, "report_by_role": True},
            "M3": {"large_result_bytes_gt": 5120, "median_large_results_per_child_lte": 1,
                   "large_result_byte_share_lte": 0.20, "max_result_bytes_lte": 20480,
                   "large_result_bytes_B_lte_A": True, "matched_tasks": True,
                   "all_carriers_including_proxy": True},
            "M4": {"routed_fetch_rate_gte": 0.90, "unclassifiable_fetch_rate_lte": 0.10,
                   "include_nested_fetches": True, "unknown_excess_outcome": "incomplete"},
            "M5": {"large_result_bytes_gt": 5120, "large_result_count_share_lte": 0.10,
                   "large_result_byte_share_lte": 0.20, "max_result_bytes_lte": 20480},
            "M6": {"not_logged_rate_lte": 0.01, "proxy_acceptance_or_exception_rate_eq": 1},
            "M6c": {"eligible_command_coverage_gte": 0.90, "wrapped_exceptions_eq": 0,
                    "use_N_only_after_Q2": True},
            "M7": {"minimum_flat_array_records": 5, "minimum_seeded_payloads": 5,
                   "seeded_encode_rate_eq": 1, "strict_roundtrip_rate_eq": 1,
                   "ineligible_encodes_eq": 0, "natural_encode_rate_gte": 0.80,
                   "natural_required": False, "natural_NA_below": 5},
            "M8": {"correct_lane_use_rate_gte": 0.80, "per_required_lane": True,
                   "optional_lanes": ["socraticode", "codebase-memory_after_Q3"]},
            "M9": {"report_use_and_correctness": True, "gating": False},
            "M10": {"outcome": "N/A", "explain_default_role_calls": True},
            "M11": {"agent_type_match_rate_eq": 1, "claude_model_effort_match_rate_eq": 1,
                    "agent_block_inline_rate_eq": 1, "codex_rtk_body_and_exceptions_rate_eq": 1,
                    "codex_role_or_parent_model_effort_text_bindings_match_rate_eq": 1},
            "M12": {"mcp_skill_bash_calls_eq": 0, "memory_index_accesses_eq": 0,
                    "routing_markers_eq": 0, "first_prompt_server_connector_blocks_eq": 0,
                    "all_hook_additional_context_rows_eq": 0, "positive_Read_rows_gte": 1,
                    "positive_control_is_blind_evidence": False,
                    "positive_control_failure_outcome": "incomplete",
                    "strict_replacement_requires_all_criteria": True},
            "M13": {"concurrent_worktrees": 2, "repetitions_per_tree": 20,
                    "own_tree_sentinel_rate_eq": 1, "wrong_root_results_eq": 0,
                    "pwd_alone_sufficient": False,
                    "tool_classes": ["shell", "ctx_execute_without_cwd",
                                     "ctx_execute_file_relative", "ctx_index_then_ctx_search",
                                     "serena_or_jcodemunch_where_granted"]},
            "M14": {"executed_call_match_rate_gte": 0.99, "duplicate_calls_eq": 0,
                    "rejected_call_decision_rate_eq": 1, "per_run_count_difference_lte": 0.02,
                    "owners_per_call_eq": 1, "qualified_client_session_ids": True,
                    "unknowns_listed_not_zero_filled": True, "global_counter_per_child": False,
                    "states": ["attempted", "decided", "executed", "failed", "cancelled_or_unfinished"]},
            "M15": {"per_server_infrastructure_error_rate_lte": 0.01,
                    "exclude_invoked_command_nonzero_exit": True,
                    "classify_every_ctx_error": True, "new_class_is_misuse_until_reproduced": True},
            "G-Q": {"B_task_pass_rate_eq": 1, "B_pass_count_gte_A": True},
            "G-C": {"priced_tokens_per_success_B_over_A_lte": 1.10,
                    "include_cache_retries_failures_interruptions": True,
                    "list_price_estimate_not_billed": True},
            "G-T": {"wall_time_B_over_A_lte": 1.25},
            "G-P": {"researcher_first_prompt_median_lt_general_purpose": True},
            "G-S": {"credential_path_reads_eq": 0, "ctx_secret_guard_escapes_eq": 0},
        }
        thresholds = load_tasks().get("thresholds", {})
        with self.subTest(field="metric_rows"):
            self.assertEqual(set(thresholds), set(expected))
        for metric, criteria in expected.items():
            with self.subTest(metric=metric):
                self.assertEqual(thresholds.get(metric, {}).get("criteria"), criteria)
            with self.subTest(metric=metric, field="required"):
                self.assertIs(thresholds.get(metric, {}).get("required"),
                              metric not in {"M2b", "M9", "M10"})
            with self.subTest(metric=metric, field="population"):
                self.assertTrue(thresholds.get(metric, {}).get("population"))

    def test_exceptions_blind_outcomes_and_overturns(self):
        data = load_tasks()
        expected = {
            "m3_exceptions": ["read_of_subsequently_edited_file", "original_source_quoted_or_line_cited",
                              "exact_bytes_required_by_frozen_check"],
            "strict_blind_process": {
                "candidate": "--safe-mode", "status": "[nv]", "qualification_gate": "Q1",
                "bare_requires_user_decision": True,
                "requires": ["native_sign_in_without_key", "resolved_model_effort",
                             "Read_Glob_Grep_inventory_and_denies", "clean_first_prompt",
                             "zero_hook_rows", "no_installed_context_plugin", "verdict_parity"],
            },
            "outcome_rule": {
                "precedence": ["incomplete", "pass", "fail"],
                "incomplete_if": ["required_lane_below_minimum", "failed_positive_control",
                                  "M4_unclassifiable_fetch_rate_above_ceiling"],
                "pass_if": "all_required_M_and_all_G_pass",
                "fail_if": "otherwise", "optional_NA_counts_as_pass": False,
                "on_incomplete": "top_up_and_rerun_same_frozen_checks",
                "on_fail": "retain_failure_keep_defaults_one_repair_round_then_rerun",
            },
            "overturn_conditions": {
                "WP5": ["B_correctness_below_A", "priced_estimate_B_over_A_gt_1.10"],
                "allowlist": "researcher_no_better_than_general_purpose_on_M1_and_M3",
                "workflow_hook_evidence": "release_or_rerun_workflow_child_without_hook_additional_context",
                "D2": "spawn_probe_refutes_inference",
                "strict_blind": ["any_hook_plugin_MCP_or_CLAUDE_md_content", "verdict_parity_failure"],
            },
        }
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(data.get(field), value)

    def test_required_lanes_have_five_organic_arm_b_child_tasks(self):
        data = load_tasks()
        self.assertEqual(set(data["required_lanes"]), REQUIRED_LANES)
        for lane in sorted(REQUIRED_LANES):
            with self.subTest(lane=lane):
                eligible = {
                    task["id"] for task in data["tasks"]
                    if "B" in task["arms"] and lane in task["lane_tags"]
                    and task["opportunity"] == "organic"
                    and task["actor"] == "child"
                }
                self.assertGreaterEqual(len(eligible), 5, f"incomplete required lane: {lane}")
                self.assertEqual(data["arm_b_opportunity_counts"][lane], len(eligible))

    def test_arm_a_full_history_has_no_role_binding(self):
        # AA 8.2:581; repair request retains the none case as-is.
        tasks = {task["id"]: task for task in load_tasks()["tasks"]}
        expected = {"seed-binding-1", "seed-binding-4"}
        with self.subTest(field="arm_a_inventory"):
            self.assertEqual({key for key, task in tasks.items()
                              if "binding" in task["lane_tags"] and "A" in task["arms"]}, expected)
        for task in tasks.values():
            if "A" in task["arms"] and task.get("launch", {}).get("fork_turns") == "all":
                for field, value in (("role", task.get("role")),
                                     ("agent_type", task["launch"].get("agent_type"))):
                    with self.subTest(task=task["id"], field=field):
                        self.assertIsNone(value)

    def test_main_effort_and_child_effort_are_distinct(self):
        # AA 8.2 Claude main; AGENTS.md Workers; native dispatch names are
        # agent-tool/sub-agent/exec here (not the review's main-agent alias).
        tasks = load_tasks()["tasks"]
        main = [task for task in tasks if task["dispatch"] == "main"]
        self.assertEqual([task["id"] for task in main], ["seed-main-output"])
        for task in tasks:
            with self.subTest(task=task["id"]):
                self.assertEqual(task["effort"], "xhigh" if task["dispatch"] == "main" else "max")

    def test_task_text_has_no_tool_names(self):
        data = load_tasks()
        self.assertTrue(data["no_tool_names_denylist"])
        for task in data["tasks"]:
            self.assertTrue(task["task_text"].strip(), task["id"])
            for name in data["no_tool_names_denylist"]:
                with self.subTest(task=task["id"], forbidden=name):
                    pattern = tool_name_pattern(name)
                    self.assertIsNone(re.search(pattern, task["task_text"], re.I))

    def test_qualified_tool_name_is_rejected_by_python_check(self):
        # AA 8.1 no-tool-names rule; underscores separate MCP name segments.
        self.assertIsNotNone(re.search(tool_name_pattern("serena"),
                                       "Call mcp__SeReNa__find_symbol.", re.I))

    def test_qualified_tool_name_is_rejected_by_script_regex(self):
        # Evaluate only the RegExp expression, never the Workflow script.
        source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
        expression = re.search(r"new RegExp\((.+), 'i'\)", source).group(1)
        check = ("const escaped = 'serena'; const pattern = new RegExp(" + expression
                 + ", 'i'); process.exit(pattern.test('mcp__SeReNa__find_symbol') ? 0 : 1);")
        result = subprocess.run(["node", "-e", check], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_denylist_covers_canonical_components_and_entry_points(self):
        # Canonical 24 component_id values, plus handbook 106-151 operations.
        data = load_tasks()
        components = json.loads((ROOT / "docs/token-efficiency-stack.json").read_text())
        names = {row["component_id"] for row in components["rows"]}
        names.update({"get_session_stats", "search_symbols", "get_symbol_source",
                      "get_current_config", "codebase_health", "codebase_status",
                      "memory_status", "search_graph", "trace_path"})
        for name in sorted(names):
            with self.subTest(name=name):
                self.assertIn(name, data["no_tool_names_denylist"])
        with self.subTest(field="sources"):
            self.assertEqual(data["denylist_sources"], [
                "docs/token-efficiency-stack.json#/rows/*/component_id",
                "docs/token-session-handbook.md:106–151",
            ])

    def test_script_error_names_the_committed_manifest(self):
        source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
        self.assertIn("Supply the exact parsed committed preregistration.json", source)

    def test_builder_checks_use_observed_child_worktree(self):
        # isolated-builder.md:7/10; harness-defaults.md:89; AA 8.2 builder row.
        data = load_tasks()
        expected = {
            "id": "actual_child_worktree", "identity_sources": ["child_transcript", "meta.json"],
            "diff_root": "observed_child_worktree", "diff_base": "recorded_child_starting_revision",
            "include_tracked_and_untracked": True, "starting_revision_must_match_frozen_execution": True,
            "missing_or_conflicting_identity": "block_grading", "prepared_path_is_proof": False,
        }
        with self.subTest(field="policy"):
            self.assertEqual(data.get("builder_worktree_policy"), expected)
        for task in data["tasks"]:
            if task["id"].startswith("seed-builder-"):
                with self.subTest(task=task["id"]):
                    self.assertEqual(task.get("worktree_check"), "actual_child_worktree")
                with self.subTest(task=task["id"], field="check_source"):
                    self.assertIn("child transcript and meta.json", task["pass_fail_check"])
        source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
        with self.subTest(field="runner"):
            self.assertIn("pending_independent_readback", source)

    def test_reused_table_binds_frozen_pointer_bytes(self):
        # Same retained-input contract as reuse-296-02; #296 /tools/9, #343 /tools/16.
        expected = {
            "source_revision": "preregistration_commit",
            "path": "catalogs/landscape/component-evidence-matrix.json",
            "pointer": "/summary/needs_host/macos-arm64",
            "serialization": "UTF-8 JSON; sort_keys=true; ensure_ascii=false; separators=(',',':'); no trailing newline",
            "sha256": "6899e551b2bea3918b47cba1b41e27e59d8f5cb12a681f98cc77f73d66a2a2c1",
            "bytes": 6552, "records": 60,
        }
        for task in load_tasks()["tasks"]:
            if task["id"] in {"reuse-296-09", "reuse-343-16"}:
                for field, value in (("input_required", True), ("frozen_input", expected)):
                    with self.subTest(task=task["id"], field=field):
                        self.assertEqual(task.get(field), value)
                with self.subTest(task=task["id"], field="prompt"):
                    self.assertIn("<retained-input>", task["task_text"])

    def test_codex_does_not_bind_claude_only_roles(self):
        # AA 6:372 defines only stack-researcher/stack-verifier Codex carriers.
        data = load_tasks()
        with self.subTest(field="exclusions"):
            self.assertEqual(set(data.get("codex_role_exclusions", {})),
                             {"source-scout", "evidence-reviewer"})
        for task in data["tasks"]:
            if task["family"] == "codex":
                with self.subTest(task=task["id"]):
                    self.assertIn(task.get("role"), (None, "stack-researcher", "stack-verifier"))

    def test_loopback_task_blocks_until_a_permitted_role_is_frozen(self):
        # source-scout.md:11 prohibits network; keep all 16 reused needs.
        task = next(t for t in load_tasks()["tasks"] if t["id"] == "reuse-296-15")
        for field, value in (("opportunity", "blocked"), ("role", None),
                             ("blocked_by", "qualified_loopback_role_amendment")):
            with self.subTest(field=field):
                self.assertEqual(task.get(field), value)
        with self.subTest(field="role_requirement"):
            self.assertEqual(task.get("role_requirement"), {
                "model": "sonnet", "effort": "max", "isolation": "no_added_worktree",
                "capabilities": ["start_bound_loopback_receiver", "send_public_synthetic_observation",
                                 "observe_rendered_span", "stop_owned_receiver"],
            })
        source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
        with self.subTest(field="launch_guard"):
            self.assertIn("task.opportunity === 'blocked' || task.blocked_by", source)

    def test_json_sources_resolve_to_real_receipt_entries(self):
        data = load_tasks()
        tasks = data["tasks"]
        self.assertEqual(len(tasks), len({task["id"] for task in tasks}))
        seen = {}
        for task in tasks:
            if task["kind"] != "reused":
                continue
            with self.subTest(task=task["id"]):
                source = ROOT / task["source"]
                self.assertTrue(source.is_file())
                self.assertTrue(source.resolve().is_relative_to(ROOT))
                with source.open(encoding="utf-8") as stream:
                    receipt = json.load(stream)
                for entry in task["source_entries"]:
                    self.assertRegex(entry["pointer"], r"^/tools/\d+$")
                    index = int(entry["pointer"].rsplit("/", 1)[1])
                    actual = receipt["tools"][index]
                    self.assertEqual(entry["tool"], actual["tool"])
                    if "attempt" in entry:
                        self.assertEqual(entry["attempt"], actual["attempt"])
                    self.assertTrue(actual.get("task") or actual.get("commands"))
                    seen.setdefault(task["source"], []).append(index)
        expected = {
            "evidence/artifacts/token-e2e-ultracode-20260925/receipt.json": 16,
            # 15 distinct tools; two retained retries make 17 actual entries.
            "evidence/artifacts/token-e2e-codex-20260926/receipt.json": 17,
        }
        self.assertEqual(set(seen), set(expected))
        for source, count in expected.items():
            self.assertEqual(sorted(seen[source]), list(range(count)))

    def test_seeded_fixtures_and_checks_are_frozen(self):
        for task in load_tasks()["tasks"]:
            with self.subTest(task=task["id"]):
                self.assertTrue(task["pass_fail_check"].strip())
                if task["kind"] == "seeded":
                    fixture = ROOT / task["fixture_path"]
                    self.assertTrue(fixture.is_file())
                    self.assertTrue(fixture.resolve().is_relative_to(ROOT))
                    self.assertTrue(task["arms"])

    def test_preregistration_exists_and_has_no_host_identity(self):
        self.assertTrue((BLUEPRINT / "README.md").is_file())
        documents = set(BLUEPRINT.rglob("*")) | {BLUEPRINT / "token-e2e-run.mjs"}
        for document in sorted(documents):
            if not document.is_file():
                continue
            try:
                text = document.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue  # This contract covers text files recursively.
            label = str(document.relative_to(BLUEPRINT))
            self.assertNotIn("/" + "tmp/", text, label)
            self.assertNotIn("-home-" + "apoth-", text, label)
            self.assertNotIn("/" + "home/", text, label)
            self.assertNotIn("/" + "Users/", text, label)
            self.assertIsNone(re.search(r"[A-Za-z]:" + r"[\\/]Users[\\/]", text), label)
            self.assertIsNone(UUID_SHAPE.search(text), label)

    def test_privacy_guard_rejects_leaks_outside_readme(self):
        # Synthetic values only; no host identity is embedded in the fixture.
        probes = ["/" + "tmp/example", "-home-" + "apoth-example",
                  "/" + "home/example", "/" + "Users/example", "C:" + "\\Users\\example",
                  "-".join(["0" * 8, "0" * 4, "0" * 4, "0" * 4, "0" * 12])]
        read_text = Path.read_text
        for path in sorted(BLUEPRINT.rglob("*")):
            if not path.is_file() or path.name == "README.md":
                continue
            for probe in probes:
                def poisoned_read(document, *args, **kwargs):
                    return probe if document == path else read_text(document, *args, **kwargs)
                with self.subTest(path=path.relative_to(BLUEPRINT), probe=probes.index(probe)):
                    with mock.patch.object(Path, "read_text", new=poisoned_read):
                        with self.assertRaises(AssertionError):
                            self.test_preregistration_exists_and_has_no_host_identity()

    def test_workflow_calls_and_arm_inventory_are_explicit(self):
        # Local replacement for test-envelope's sweep: AA 8.1 and exact PR-H list.
        source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
        calls = re.findall(r"\bawait agent\([\s\S]*?,\s*\{([\s\S]*?)\}\);", source)
        self.assertEqual(len(calls), 3)
        for index, options in enumerate(calls):
            for field, pattern in (("model", r"\bmodel:\s*route\.model\b"),
                                   ("effort", r"\beffort:\s*'max'")):
                with self.subTest(call=index, field=field):
                    self.assertRegex(options, pattern)
        ids = json.loads(re.search(r"const expectedIds = (\[[\s\S]*?\]);", source).group(1))
        tasks = [task for task in load_tasks()["tasks"]
                 if task["family"] == "claude" and task["dispatch"] == "workflow"]
        with self.subTest(field="ids"):
            self.assertEqual(ids, [task["id"] for task in tasks])
        with self.subTest(field="id_count"):
            self.assertEqual(len(ids), 49)
        counts = re.search(r"const expectedCount = args.arm === 'B' \? (\d+) : (\d+);", source)
        for arm, expected in (("B", 49), ("A", 43), ("A0", 43)):
            with self.subTest(arm=arm, field="manifest_count"):
                self.assertEqual(sum(arm in task["arms"] for task in tasks), expected)
            with self.subTest(arm=arm, field="script_count"):
                self.assertEqual(int(counts.group(1 if arm == "B" else 2)), expected)

    def test_baseline_deferral_and_freeze_timing_are_explicit(self):
        # AA 6:412; full-save 4.1:547 and 5 steps 4/13:704/717.
        for filename in ("README.md", "RUNBOOK.md"):
            text = (BLUEPRINT / filename).read_text(encoding="utf-8")
            with self.subTest(file=filename, field="deferral"):
                self.assertTrue("`baseline.json` is deferred to PR-A" in text, filename)
            with self.subTest(file=filename, field="historical_scope"):
                self.assertTrue("pre-fix reference baseline only" in text, filename)
        text = (BLUEPRINT / "README.md").read_text(encoding="utf-8")
        with self.subTest(field="freeze_timing"):
            self.assertTrue("PR-H freezes M-R1 after PR-A's baseline" in text)

    def test_sealing_hashes_and_amendment_rule(self):
        # retrieval-quality-v2/PREREGISTRATION.md Sealing and Amendments.
        text = (BLUEPRINT / "README.md").read_text(encoding="utf-8")
        for term in ("## Sealing", "## Amendment 1 (2026-09-26)", "append-only", "never a silent rewrite"):
            with self.subTest(term=term):
                self.assertTrue(term in text, term)
        for filename in ("preregistration.json", "token-e2e-run.mjs", "RUNBOOK.md",
                         "fixtures/table.json", "fixtures/events.jsonl"):
            digest = hashlib.sha256((BLUEPRINT / filename).read_bytes()).hexdigest()
            with self.subTest(file=filename):
                self.assertTrue(f"| `{filename}` | `{digest}` |" in text, filename)


if __name__ == "__main__":
    unittest.main()
