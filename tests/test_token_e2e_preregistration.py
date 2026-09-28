"""Offline preregistration contracts; never launch a model or workflow.

Sources: AA sections 8.1 and 8.3; PR-H build specification; unittest/path
conventions in tests/test_token_report_refresh_units.py:12-25. Amendment 2
(README, 2026-09-27): the #402 role bodies at d022295a and the sub-agents
reference (https://code.claude.com/docs/en/sub-agents: scope priority, working
directory, `isolation` and model resolution order).
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
# A client project-directory name for any user (Linux -home-<user>-..., macOS -Users-<user>-...), so the
# guard holds on every host without publishing this host's user name.
PROJECT_DIR_SHAPE = re.compile(r"-(?:home|Users)-[A-Za-z0-9_]+-")
# Amendment 2 literals, independent of the manifest. Models: #402's definitions
# at d022295a (adoption/agents/claude/{stack-verifier,isolated-builder}.md:5 say
# opus, source-scout.md:5 says sonnet) and the user's Opus rule for build and
# verification stages.
AMENDED_CLAUDE_ROLE_MODELS = {
    "stack-researcher": "opus", "stack-verifier": "opus", "isolated-builder": "opus",
    "evidence-reviewer": "opus", "source-scout": "sonnet",
    "blind-lane-reviewer": "opus", "blind-judge": "opus",
}
AMENDED_ROLE_TABLE = [
    "| stack-researcher | opus | max | #376 role body, after merge/install proof; unchanged by #402 |",
    "| stack-verifier | opus | max | #402 role body at d022295a |",
    "| isolated-builder | opus | max | #402 role body at d022295a |",
    "| evidence-reviewer | opus | max | Existing role body; unchanged by #402 |",
    "| source-scout | sonnet | max | #402 role body at d022295a |",
    "| blind-lane-reviewer / blind-judge | opus | max | Existing stripped blind bodies; no skill preload |",
]
# Repair 1 builder policy (Amendment 1, finding 3). Amendment 2 only adds fields.
REPAIR_1_BUILDER_POLICY = {
    "id": "actual_child_worktree", "identity_sources": ["child_transcript", "meta.json"],
    "diff_root": "observed_child_worktree", "diff_base": "recorded_child_starting_revision",
    "include_tracked_and_untracked": True, "starting_revision_must_match_frozen_execution": True,
    "missing_or_conflicting_identity": "block_grading", "prepared_path_is_proof": False,
}
AMENDMENT_2_BUILDER_POLICY = {
    "brief_binding": "worktree_paths", "base_binding": "worktree_bases",
    "harness_created_tree_expected": False,
    "observed_child_worktree_must_equal_prepared_path": True,
    "observed_worktree_other_than_prepared_path": "conflicting_identity",
    "hooks_preflight_and_restore_required": True, "per_tree_sentinel_checks_required": True,
    "amended_by": "Amendment 2 (2026-09-27)",
}
# Amendment 2 repair round (2026-09-27), GPT-6 finding 1: #402's builder stops
# when `git -C <path> rev-parse HEAD` is not the brief's base
# (isolated-builder.md:12 at d022295a), so both builder briefs add one clause
# after the prepared path. Everything else is the unchanged Amendment 1 text.
BUILDER_TEXT_BEFORE_REPAIR = (
    "Use the isolated checkout actually assigned by the harness. If the harness creates no "
    "separate checkout, use the prepared control checkout <assigned-worktree>. Verify and report "
    "the actual working directory and starting revision before editing; stay inside that "
    "checkout. There, change fixtures/before.py so greeting('{name}') returns 'Hello, {name}!'. "
    "Confirm the complete result matches fixtures/after.py and test another name. Do not commit."
)
BASE_CLAUSE = ", prepared at the exact base <assigned-base>"
BUILDER_NAMES = {"seed-builder-1": "Ada", "seed-builder-2": "Grace"}
# Repair round, evidence-reviewer finding 2: SHA256 of each executed role body,
# `git show d022295a:adoption/agents/claude/<file> | sha256sum`; #402 made each
# .claude/agents copy the same blob. Table rows, for the reason given below.
ROLE_BODY_ROWS = (
    "| `stack-verifier.md` | `a4cc7f5024af7fdea544a0963d8ff6f712c9eb460812582fd93368870eeeabcc` |",
    "| `isolated-builder.md` | `57452a64ca8b97996aeb35916fb1f1f4d06452857178d6ad6dc7c49723d84cf7` |",
    "| `source-scout.md` | `f79cead4a3f9c14986bb28815d046eacf8bf79c92fe923094f66f97a64c06341` |",
    "| `stack-researcher.md` | `a35b015fcf7e8d608b5cf60e4172c6f1033bf4d9b3b8047a008efc5e89dcb446` |",
    "| `evidence-reviewer.md` | `3aa5e3f0aac4b43f7196cb46aee3ce1ef06e795ae93ba2a925ea53ac62f5e256` |",
)
# The README amendment rule preserves every earlier seal table: the Repair 1
# rows, verbatim. Kept as table rows, not "name": "digest" pairs, which the
# pre-commit gitleaks generic-api-key rule reads as a keyed secret.
REPAIR_1_SEAL_ROWS = (
    "| `preregistration.json` | `e04c1a08de610356e2f24cf8d1f59a70e8b630e093c93934cd03ab0a8091bee4` |",
    "| `token-e2e-run.mjs` | `6ca129d94d51c6c99c5a9430e2b7fb0d23b0919001acf789bf5d59d74c7cb828` |",
    "| `RUNBOOK.md` | `a8ee0e09ce001db21269f66dc5ec4a4aa39abc3020e86e37d610a4aa9236c5a4` |",
    "| `fixtures/table.json` | `fdf314394a9854039da18b2f827f8caf2d8ffb3651594733eb84699f74c09448` |",
    "| `fixtures/events.jsonl` | `81ef838c18cc81006269024e7270b991dbdfcb72bf223dec324f2fba9307930e` |",
)
SEALED_FILES = tuple(row.split("`")[1] for row in REPAIR_1_SEAL_ROWS)


def load_tasks():
    with (BLUEPRINT / "preregistration.json").open(encoding="utf-8") as stream:
        return json.load(stream)


def tool_name_pattern(name):
    return r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"


def section(text, start, end):
    """Text after the first start marker, up to the next end marker; empty if absent."""
    _, found, rest = text.partition(start)
    return rest.split(end, 1)[0] if found else ""


def flat(text):
    """Collapse Markdown line wrapping so phrase checks ignore line breaks."""
    return " ".join(text.split())


def builder_text(task_id):
    """Frozen builder brief after the repair round: one clause after the path."""
    return (BUILDER_TEXT_BEFORE_REPAIR.format(name=BUILDER_NAMES[task_id])
            .replace("<assigned-worktree>", "<assigned-worktree>" + BASE_CLAUSE))


def runnable_copy():
    """In-memory manifest copy only; reuse-296-15 stays blocked on disk."""
    data = load_tasks()
    for task in data["tasks"]:
        if task["id"] == "reuse-296-15":
            task.update(opportunity="organic", blocked_by=None, role="source-scout")
    return data


def synthetic_bindings(data, arm):
    """Neutral per-arm bindings; each base is a derived 40-hex value, not a revision."""
    tasks = [task for task in data["tasks"] if task["family"] == "claude"
             and task["dispatch"] == "workflow" and arm in task["arms"]]
    return {
        "arm": arm,
        "worktree_paths": {task["id"]: f"/synthetic/{arm}/{task['id']}"
                           for task in tasks if task.get("worktree_required")},
        "worktree_bases": {task["id"]: hashlib.sha256(task["id"].encode()).hexdigest()[:40]
                           for task in tasks if task.get("worktree_required")},
        "input_paths": {task["id"]: f"/synthetic/input/{task['id']}"
                        for task in tasks if task.get("input_required")},
    }


def run_stubbed_runner(data, bindings):
    """Evaluate the runner body under Node with stub agent/phase/log.

    No model, Workflow or child runs: the stub agent() only records each prompt.
    """
    source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
    harness = (
        "const args = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
        "const calls = [];\n"
        "const agent = async (prompt, options) => {\n"
        "  calls.push({ prompt, label: options.label });\n"
        "  return { answer: '', evidence: [] };\n"
        "};\n"
        "const phase = () => {};\n"
        "const log = () => {};\n"
        "(async () => {\n" + source.replace("export const meta", "const meta", 1) + "\n})().then(\n"
        "  () => process.stdout.write(JSON.stringify({ error: null, calls })),\n"
        "  failure => process.stdout.write(JSON.stringify({ error: String(failure), calls })),\n"
        ");\n"
    )
    args = {"run": "synthetic", "attempt": 1, "preregistration_commit": "synthetic",
            "gates_verified": True, "frozen_tasks": data, **bindings}
    result = subprocess.run(["node", "-e", harness], input=json.dumps(args),
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


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

    def test_amendment_2_role_models(self):
        # Amendment 2 change 1: verifier and builder tasks move to Opus (effort
        # stays max); the scout stays Sonnet; Codex tasks keep gpt-6-astra; the
        # blocked loopback slot keeps its frozen model.
        tasks = load_tasks()["tasks"]
        claude = [task for task in tasks if task["family"] == "claude" and task.get("role")]
        for task in claude:
            with self.subTest(task=task["id"]):
                self.assertEqual(task["model"], AMENDED_CLAUDE_ROLE_MODELS.get(task["role"]))
        for role, count in (("stack-verifier", 6), ("isolated-builder", 2), ("source-scout", 3)):
            with self.subTest(role=role, field="claude_task_count"):
                self.assertEqual(sum(task["role"] == role for task in claude), count)
        for task in tasks:
            if task["family"] == "codex":
                with self.subTest(task=task["id"], field="codex_model"):
                    self.assertEqual(task["model"], "gpt-6-astra")
        blocked = next(task for task in tasks if task["id"] == "reuse-296-15")
        with self.subTest(task=blocked["id"], field="blocked_slot_model"):
            self.assertEqual((blocked["role"], blocked["model"]), (None, "sonnet"))

    def test_runner_role_map_agrees_with_json(self):
        # Every Workflow agent() call passes route.model, and a per-invocation
        # model outranks the definition's (sub-agents, model resolution order),
        # so the runner's map, not the agent file, decides each child's model.
        source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
        block = re.search(r"const routes = \{\n([\s\S]*?)\n\};", source)
        self.assertIsNotNone(block)
        lines = block.group(1).splitlines()
        routes = {}
        for line in lines:
            match = re.fullmatch(r"  '([a-z-]+)': \{ agentType: '([a-z-]+)', model: '([a-z0-9-]+)' \},", line)
            with self.subTest(line=line):
                self.assertIsNotNone(match)
            if match:
                routes[match.group(1)] = (match.group(2), match.group(3))
        with self.subTest(field="role_map"):
            self.assertEqual(routes, {role: (role, model)
                                      for role, model in AMENDED_CLAUDE_ROLE_MODELS.items()})
        for task in load_tasks()["tasks"]:
            if task["family"] == "claude" and task["dispatch"] == "workflow" and task.get("role"):
                with self.subTest(task=task["id"], field="json_agreement"):
                    self.assertEqual(routes.get(task["role"], (None, None))[1], task["model"])

    def test_readme_role_table_carriers_agree_with_json(self):
        # Amendment 2 changes 1-2: #402 carriers for verifier, builder and scout;
        # researcher and reviewer rows stay, marked unchanged by #402.
        text = (BLUEPRINT / "README.md").read_text(encoding="utf-8")
        table = section(text, "| Frozen role in B | Explicit model | Explicit effort | Carrier |\n", "\n\n")
        rows = [line for line in table.splitlines() if not line.startswith("| ---")]
        with self.subTest(field="rows"):
            self.assertEqual(rows, AMENDED_ROLE_TABLE)
        models = {}
        for row in rows:
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            for role in cells[0].split(" / "):
                models[role] = cells[1]
        for task in load_tasks()["tasks"]:
            if task["family"] == "claude" and task.get("role"):
                with self.subTest(task=task["id"], field="json_agreement"):
                    self.assertEqual(models.get(task["role"]), task["model"])

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
        # isolated-builder.md:3,12 at d022295a (#402: no frontmatter isolation;
        # edits only in the owned checkout its brief names); harness-defaults.md:91;
        # AA 8.2 builder row. Amendment 2 change 3 adds to the Repair 1 policy only.
        data = load_tasks()
        policy = data.get("builder_worktree_policy") or {}
        with self.subTest(field="repair_1_fields_unchanged"):
            self.assertEqual({key: policy.get(key) for key in REPAIR_1_BUILDER_POLICY},
                             REPAIR_1_BUILDER_POLICY)
        with self.subTest(field="policy"):
            self.assertEqual(policy, {**REPAIR_1_BUILDER_POLICY, **AMENDMENT_2_BUILDER_POLICY})
        for task in data["tasks"]:
            if task["id"].startswith("seed-builder-"):
                with self.subTest(task=task["id"]):
                    self.assertEqual(task.get("worktree_check"), "actual_child_worktree")
                with self.subTest(task=task["id"], field="check_source"):
                    self.assertIn("child transcript and meta.json", task["pass_fail_check"])
                with self.subTest(task=task["id"], field="brief_binding"):
                    self.assertIs(task.get("worktree_required"), True)
                    self.assertIn("<assigned-worktree>", task["task_text"])
        source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
        with self.subTest(field="runner"):
            self.assertIn("pending_independent_readback", source)
        with self.subTest(field="runner_brief_binding"):
            self.assertIn("prompt = prompt.replaceAll('<assigned-worktree>', path);", source)

    def test_builder_worktree_text_follows_amendment_2(self):
        # Amendment 2 change 3: every arm's brief names the prepared path, the
        # observed edit tree must be that path, and the hooks preflight/restore
        # and per-tree sentinels stay; the superseded isolation rule is gone.
        runbook = (BLUEPRINT / "RUNBOOK.md").read_text(encoding="utf-8")
        builder = section(runbook, "### Builder worktrees and hooks restoration\n", "\n### ")
        for phrase in (
            "Amendment 2 (2026-09-27)", "isolated-builder.md:3,12", "`worktree_paths`",
            "must be the frozen prepared path", "**[nv]**", "per-tree sentinels",
            "git config --show-origin --get core.hooksPath",
            "git config --local --get-all core.hooksPath",
            "git config --local --unset-all core.hooksPath",
            'git config --local --add core.hooksPath "${HOOKS_PATH_BEFORE}"',
            "Never write global/system config.",
        ):
            with self.subTest(file="RUNBOOK.md", phrase=phrase):
                self.assertIn(phrase, builder)
        with self.subTest(file="RUNBOOK.md", field="superseded_rule"):
            self.assertNotIn("Keep `isolation: worktree`", builder)
        readme = (BLUEPRINT / "README.md").read_text(encoding="utf-8")
        body = readme.partition("## Sealing")[0]
        for superseded in ("B's `isolation: worktree` may create another tree",
                           "Keep the role's isolation"):
            with self.subTest(file="README.md", superseded=superseded):
                self.assertNotIn(superseded, body)
        with self.subTest(file="README.md", field="prepared_path"):
            self.assertIn("require that tree to be the prepared path", body)

    def test_builder_briefs_name_prepared_path_and_base(self):
        # Repair round, finding 1: both builder texts gain only BASE_CLAUSE after
        # the prepared path; no other task carries the base placeholder.
        for task in load_tasks()["tasks"]:
            if task["id"] in BUILDER_NAMES:
                with self.subTest(task=task["id"], field="text"):
                    self.assertEqual(task["task_text"], builder_text(task["id"]))
            else:
                with self.subTest(task=task["id"], field="no_base_placeholder"):
                    self.assertNotIn("<assigned-base>", task["task_text"])
        body = flat((BLUEPRINT / "README.md").read_text(encoding="utf-8").partition("## Sealing")[0])
        with self.subTest(file="README.md", field="bound_placeholders"):
            self.assertIn("bind `<assigned-worktree>`, `<assigned-base>`, `<retained-input>` "
                          "and `<run-token>`", body)

    def test_runner_requires_base_binding_before_any_child(self):
        # dispatch_policy.workflow binds only frozen neutral placeholders; the
        # refusal sits in the prompt loop, before phase() and the first agent().
        source = (BLUEPRINT / "token-e2e-run.mjs").read_text(encoding="utf-8")
        for fragment in (
            "const base = args.worktree_bases?.[task.id];",
            "!/^[0-9a-f]{40}$/.test(base)",
            "(task.worktree_check && !prompt.includes('<assigned-base>'))",
            "throw new Error('Supply the frozen worktree base binding: ' + task.id);",
            "prompt = prompt.replaceAll('<assigned-base>', base);",
            "throw new Error('Unbound frozen base placeholder: ' + task.id);",
            "prepared_base: args.worktree_bases[task.id]",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, source)
        with self.subTest(field="refusal_before_first_child"):
            refusal = source.find("Supply the frozen worktree base binding")
            self.assertGreater(refusal, 0)
            self.assertLess(refusal, source.index("phase('Frozen child tasks');"))
        with self.subTest(field="every_arm_sends_the_bound_prompt"):
            self.assertEqual(re.findall(r"\bawait agent\(([^,]+),", source),
                             ["prompts.get(task.id)"] * 3)

    def test_runner_binds_base_and_refuses_without_it(self):
        # Local synthetic harness: stub agent/phase/log under Node over an
        # in-memory manifest copy; never a Workflow run or a model call.
        data = runnable_copy()
        for arm, count in (("B", 49), ("A", 43), ("A0", 43)):
            bindings = synthetic_bindings(data, arm)
            outcome = run_stubbed_runner(data, bindings)
            with self.subTest(arm=arm, field="complete_bindings_start"):
                self.assertIsNone(outcome["error"])
                self.assertEqual(len(outcome["calls"]), count)
            prompts = {call["label"].split(".")[2]: call["prompt"] for call in outcome["calls"]}
            for task_id in BUILDER_NAMES:
                expected = (builder_text(task_id)
                            .replace("<assigned-worktree>", bindings["worktree_paths"][task_id])
                            .replace("<assigned-base>", bindings["worktree_bases"][task_id]))
                with self.subTest(arm=arm, task=task_id, field="bound_brief"):
                    self.assertEqual(prompts.get(task_id), expected)
            with self.subTest(arm=arm, field="no_unbound_placeholder"):
                self.assertEqual([key for key, prompt in prompts.items() if "<assigned-" in prompt], [])
        complete = synthetic_bindings(data, "B")
        refusals = {
            "no_bases": ({**complete, "worktree_bases": None}, "reuse-296-00"),
            "reused_task_base_missing": (
                {**complete, "worktree_bases": {key: value for key, value in
                                                complete["worktree_bases"].items()
                                                if key != "reuse-296-11"}}, "reuse-296-11"),
            "builder_base_missing": (
                {**complete, "worktree_bases": {key: value for key, value in
                                                complete["worktree_bases"].items()
                                                if key != "seed-builder-1"}}, "seed-builder-1"),
            "abbreviated_base": (
                {**complete, "worktree_bases": {**complete["worktree_bases"],
                                                "seed-builder-2": "0" * 12}}, "seed-builder-2"),
        }
        for case, (bindings, task_id) in refusals.items():
            outcome = run_stubbed_runner(data, bindings)
            with self.subTest(case=case):
                self.assertEqual(outcome["error"],
                                 "Error: Supply the frozen worktree base binding: " + task_id)
                self.assertEqual(outcome["calls"], [])
        # Mutation checks on the in-memory text only: a builder text without the
        # placeholder, and a placeholder on a task with no worktree binding.
        mutated = runnable_copy()
        plain = next(task for task in mutated["tasks"] if task["family"] == "claude"
                     and task["dispatch"] == "workflow" and "B" in task["arms"]
                     and not task.get("worktree_required")
                     and not task.get("input_required") and not task.get("run_binding"))
        for task in mutated["tasks"]:
            if task["id"] == "seed-builder-1":
                task["task_text"] = task["task_text"].replace(BASE_CLAUSE, "")
        outcome = run_stubbed_runner(mutated, complete)
        with self.subTest(case="builder_text_without_placeholder"):
            self.assertEqual(outcome["error"],
                             "Error: Supply the frozen worktree base binding: seed-builder-1")
            self.assertEqual(outcome["calls"], [])
        mutated = runnable_copy()
        for task in mutated["tasks"]:
            if task["id"] == plain["id"]:
                task["task_text"] += " <assigned-base>"
        outcome = run_stubbed_runner(mutated, complete)
        with self.subTest(case="unbound_placeholder", task=plain["id"]):
            self.assertEqual(outcome["error"],
                             "Error: Unbound frozen base placeholder: " + plain["id"])
            self.assertEqual(outcome["calls"], [])

    def test_capability_probe_uses_frozen_builder_brief_shape(self):
        # Repair round, findings 1 and 3: the base binding is frozen with the
        # paths, the builder section keeps the role's base refusal, and the B-route
        # builder probe uses the frozen brief shape.
        runbook = (BLUEPRINT / "RUNBOOK.md").read_text(encoding="utf-8")
        capability = flat(section(runbook, "## Capability qualification and launch", "\n### "))
        for phrase in ("B-route `isolated-builder` probe must use exactly the frozen brief shape",
                       "the prepared path plus `<assigned-base>`", "and no other base text"):
            with self.subTest(section="capability", phrase=phrase):
                self.assertIn(phrase, capability)
        with self.subTest(section="freeze"):
            self.assertIn("(`worktree_bases`)", section(runbook, "## Freeze and preflight", "\n## "))
        with self.subTest(section="args"):
            self.assertIn("| worktree_bases |", runbook)
        builder = flat(section(runbook, "### Builder worktrees and hooks restoration\n", "\n### "))
        for phrase in ("`<assigned-base>`", "`worktree_bases`",
                       "The role's refusal when `HEAD` is not the brief's base is kept",
                       "receive the same bound placeholders"):
            with self.subTest(section="builder", phrase=phrase):
                self.assertIn(phrase, builder)
        with self.subTest(section="builder", superseded="no_base_revision"):
            self.assertNotIn("names that path but no base revision", builder)
        with self.subTest(section="codex"):
            self.assertIn("No Codex task text carries `<assigned-base>`",
                          flat(section(runbook, "### Codex launches", "\n## ")))

    def test_amendment_2_pins_executed_role_bodies(self):
        # Repair round, finding 2: the README table pins the d022295a blobs, the
        # freeze requires every executed copy to equal them, and the repository
        # copies still do; a later change needs another dated amendment.
        readme = (BLUEPRINT / "README.md").read_text(encoding="utf-8")
        amendment_2 = section(readme, "## Amendment 2 (2026-09-27)", "\n## ")
        for row in ROLE_BODY_ROWS:
            filename, digest = row.split("`")[1], row.split("`")[3]
            with self.subTest(file=filename, field="readme_row"):
                self.assertIn(row, amendment_2)
            for copy in ("adoption/agents/claude", ".claude/agents"):
                with self.subTest(file=filename, copy=copy):
                    self.assertEqual(
                        hashlib.sha256((ROOT / copy / filename).read_bytes()).hexdigest(), digest)
        with self.subTest(file="README.md", field="carrier_rule"):
            self.assertIn("must equal Amendment 2's role-body SHA256 table",
                          flat(readme.partition("## Sealing")[0]))
        freeze = flat(section((BLUEPRINT / "RUNBOOK.md").read_text(encoding="utf-8"),
                              "## Freeze and preflight", "\n## "))
        for phrase in ("must also equal the SHA256 recorded there for `d022295a`",
                       "byte identity at the execution HEAD alone does not suffice",
                       "requires another dated amendment"):
            with self.subTest(file="RUNBOOK.md", phrase=phrase):
                self.assertIn(phrase, freeze)

    def test_amendment_2_records_builder_base_binding(self):
        # Repair round: the change table states the input binding and its limits;
        # the first-round statements it supersedes are gone.
        amendment_2 = flat(section((BLUEPRINT / "README.md").read_text(encoding="utf-8"),
                                   "## Amendment 2 (2026-09-27)", "\n## "))
        for phrase in ("pre-execution input binding", "No organic result was observed",
                       "this changes no eligibility, lane, threshold or check",
                       "receive the same bound placeholders",
                       "except the frozen `<assigned-base>` placeholder"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, amendment_2)
        for superseded in ("(runner binding and task text unchanged)",
                           "against a brief that names no base is",
                           "Tasks and their text, eligibility"):
            with self.subTest(superseded=superseded):
                self.assertNotIn(superseded, amendment_2)

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
            self.assertIsNone(PROJECT_DIR_SHAPE.search(text), label)
            self.assertNotIn("/" + "home/", text, label)
            self.assertNotIn("/" + "Users/", text, label)
            self.assertIsNone(re.search(r"[A-Za-z]:" + r"[\\/]Users[\\/]", text), label)
            self.assertIsNone(UUID_SHAPE.search(text), label)

    def test_privacy_guard_rejects_leaks_outside_readme(self):
        # Synthetic values only; no host identity is embedded in the fixture.
        probes = ["/" + "tmp/example", "-home-" + "example-x", "-Users-" + "example-x",
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

    def test_freeze_records_project_and_user_role_definitions(self):
        # Amendment 2 change 4: sub-agents "Choose the subagent scope" (project
        # .claude/agents/ priority 3 outranks user ~/.claude/agents/ priority 4);
        # #402 added the project-scope copies.
        runbook = (BLUEPRINT / "RUNBOOK.md").read_text(encoding="utf-8")
        freeze = section(runbook, "## Freeze and preflight", "\n## ")
        for phrase in ("Amendment 2 (2026-09-27)", "`d022295a`", "`.claude/agents/*.md`",
                       "`~/.claude/agents/*.md`", "`adoption/agents/claude/*.md`", "shadow",
                       "byte-identical", "read back", "execution HEAD", "blocks capability probes and launch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, freeze)

    def test_sealing_hashes_and_amendment_rule(self):
        # retrieval-quality-v2/PREREGISTRATION.md Sealing and Amendments: the
        # Repair 1 seal stays; the Amendment 2 seal holds the current hashes.
        text = (BLUEPRINT / "README.md").read_text(encoding="utf-8")
        for term in ("## Sealing", "## Amendment 1 (2026-09-26)", "## Amendment 2 (2026-09-27)",
                     "append-only", "never a silent rewrite"):
            with self.subTest(term=term):
                self.assertTrue(term in text, term)
        repair_1 = section(text, "## Sealing", "## Amendment 1 (2026-09-26)")
        for filename, row in zip(SEALED_FILES, REPAIR_1_SEAL_ROWS):
            with self.subTest(seal="repair_1", file=filename):
                self.assertTrue(row in repair_1, filename)
        amendment_2 = section(text, "## Amendment 2 (2026-09-27)", "\n## ")
        for filename in SEALED_FILES:
            digest = hashlib.sha256((BLUEPRINT / filename).read_bytes()).hexdigest()
            with self.subTest(seal="amendment_2", file=filename):
                self.assertTrue(f"| `{filename}` | `{digest}` |" in amendment_2, filename)
        for term in ("`c7b78854`", "2026-09-27T06:39:20Z", "`d022295a`", "2026-09-27T14:04:25Z",
                     "no result was observed"):
            with self.subTest(field="chronology", term=term):
                self.assertIn(term, amendment_2)


if __name__ == "__main__":
    unittest.main()
