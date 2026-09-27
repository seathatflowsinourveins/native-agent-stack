"""Offline recipe contract, frozen before the recipe exists.

References: OpenHands/software-agent-sdk v1.49.6 examples
01_standalone_sdk/{01_hello_world,07_mcp_integration,14_context_condenser}.py;
the user's 2026-09-27 runtime-worker acceptance contract. These are local
structural/fixture checks, not upstream SDK or live gateway acceptance.
"""

import json
import importlib.util
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "blueprints/runtime-workers/openhands"


def load_recipe_module(filename):
    name = "openhands_recipe_test_" + filename.replace("/", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(name, RECIPE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(RECIPE))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class OpenHandsRecipeTests(unittest.TestCase):
    def read_json(self, relative):
        return json.loads((RECIPE / relative).read_text())

    def test_gateway_model_and_container_topology(self):
        config = self.read_json("config/worker.json")
        self.assertEqual(config["llm"]["base_url"], "http://127.0.0.1:20128/v1")
        self.assertEqual(config["llm"]["model"], "cx/gpt-6-astra-max")
        self.assertEqual(config["model_env"], "OPENHANDS_MODEL")
        self.assertEqual(config["llm"]["api_key"], "local-loopback")
        self.assertEqual(config["llm"]["api_mode"], "responses")
        self.assertIsNone(config["llm"].get("temperature"))
        self.assertNotEqual(config["llm"].get("reasoning_effort"), "auto")
        self.assertEqual(config["runtime"]["gateway_base_url"], "http://10.0.2.2:20128/v1")
        self.assertEqual(config["runtime"]["agent_loop"], "container")
        self.assertEqual(config["runtime"]["published_ports"], [])
        self.assertEqual(config["condenser"]["kind"], "LLMSummarizingCondenser")
        self.assertGreater(config["condenser"]["max_tokens"], 0)

    def test_mcp_limits(self):
        policy = self.read_json("config/mcp-policy.json")
        self.assertEqual(set(policy["context-mode"]["disabled_tools"]), {"ctx_upgrade", "ctx_purge"})
        self.assertEqual(set(policy["ai-memory"]["enabled_tools"]), {
            "memory_query", "memory_read_page", "memory_recent", "memory_status", "memory_briefing",
        })
        self.assertEqual(set(policy["socraticode"]["enabled_tools"]), {
            "codebase_search", "codebase_status", "codebase_list_projects", "codebase_health",
        })
        self.assertEqual(policy["socraticode"]["env"]["SOCRATICODE_WATCHER"], "manual")
        self.assertEqual(set(policy["jcodemunch"]["enabled_tools"]), {"route", "menu", "order"})
        self.assertEqual(set(policy["qmd"]["collections"]), {
            "foundation-docs", "foundation-adoption", "us-equities-foundation", "us-equities-catalog",
        })
        self.assertFalse(policy["headroom"]["enabled"])
        self.assertEqual(set(policy["headroom"]["enabled_tools"]), {
            "headroom_compress", "headroom_retrieve", "headroom_stats",
        })
        self.assertIn("serena", policy)

    def test_immutable_artifacts(self):
        pins = self.read_json("pins.json")
        self.assertEqual(pins["version"], "1.49.6")
        self.assertRegex(pins["commit"], r"^[0-9a-f]{40}$")
        for name in ("source_archive", "uv_lock"):
            self.assertRegex(pins[name]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(pins["image"]["ref"], r"^ghcr\.io/openhands/agent-server@sha256:[0-9a-f]{64}$")

    def test_installer_and_runtime_are_scoped(self):
        for filename in ("install.sh", "run-e2e.sh"):
            text = (RECIPE / filename).read_text()
            self.assertIn("set -euo pipefail", text)
            self.assertNotRegex(text, r"(?m)^\s*sudo\s")
        installer = (RECIPE / "install.sh").read_text()
        self.assertIn(".local/share/codex-ecosystem/tools/openhands-", installer)
        self.assertIn(".local/state/native-agent-stack/runtime-workers/openhands", installer)
        self.assertIn("umask 077", installer)
        self.assertIn("sha256", installer)
        self.assertIn("rootless", installer)
        driver = (RECIPE / "worker.py").read_text()
        self.assertIn("Idempotency-Key", driver)
        self.assertIn("x-omniroute-session", driver)
        self.assertIn("filter_tools_regex", driver)
        self.assertIn("mcp_config", driver)

    def test_no_public_binds_or_secret_material(self):
        self.assertTrue(RECIPE.is_dir())
        paths = [p for p in RECIPE.rglob("*") if p.is_file() and p.suffix in {".json", ".py", ".sh", ".toml"}]
        self.assertGreater(len(paths), 5)
        for path in paths:
            text = path.read_text()
            with self.subTest(file=path.name):
                self.assertNotIn("0.0.0.0", text)
                self.assertNotIn("BEGIN PRIVATE KEY", text)
                self.assertIsNone(re.search(r"sk-[A-Za-z0-9]{20,}", text))

    def test_checker_rejects_an_empty_result(self):
        checker = RECIPE / "e2e/check.py"
        self.assertTrue(checker.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(checker), "--result", tmp],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["passed"])
        self.assertIn("missing_result", report["failures"])

    def test_fresh_call_headers_keep_session_affinity(self):
        worker = load_recipe_module("worker.py")
        original = {"x-omniroute-session": "fixture-session"}
        first = worker.headers_for_call(original)
        second = worker.headers_for_call(original)
        self.assertNotEqual(first["Idempotency-Key"], second["Idempotency-Key"])
        self.assertEqual(first["x-omniroute-session"], second["x-omniroute-session"])
        self.assertEqual(original, {"x-omniroute-session": "fixture-session"})

    def test_runtime_model_override_and_native_tool_filter(self):
        helpers = load_recipe_module("recipe.py")
        result = helpers.llm_config(self.read_json("config/worker.json"), "cx/future-model-max")
        self.assertEqual(result["model"], "openai/cx/future-model-max")
        self.assertEqual(result["base_url"], "http://10.0.2.2:20128/v1")
        pattern = re.compile(helpers.tool_filter(self.read_json("config/mcp-policy.json")))
        for name in ("terminal", "file_editor", "context-mode_ctx_execute", "serena_find_symbol", "ai-memory_memory_query", "qmd_query", "socraticode_codebase_health", "jcodemunch_order"):
            self.assertIsNotNone(pattern.fullmatch(name), name)
        for name in ("context-mode_ctx_upgrade", "context-mode_ctx_purge", "ai-memory_memory_write", "socraticode_codebase_index", "jcodemunch_delete_index", "headroom_headroom_compress", "memory_query", "qmd_query_evil"):
            self.assertIsNone(pattern.fullmatch(name), name)

    def test_qmd_guard_requires_explicit_scope_and_lexical_query(self):
        guard = load_recipe_module("mcp_guard.py")
        params = {"collections": ["foundation-docs"], "searches": [{"type": "lex", "query": "fixture"}], "rerank": False}
        event = {"tool_name": "qmd_query", "tool_input": {"data": params}}
        self.assertTrue(guard.permitted(event))
        for patch in ({"collections": []}, {"collections": ["private"]}, {"rerank": True}, {"query": "expand"}, {"searches": [{"type": "vec", "query": "fixture"}]}):
            self.assertFalse(guard.permitted({"tool_name": "qmd_query", "tool_input": {"data": {**params, **patch}}}))

    def test_serena_activates_plain_fixture_and_keeps_metadata_outside_it(self):
        config = self.read_json("config/mcp.template.json")["serena"]
        self.assertNotIn("--project-from-cwd", config["args"])
        self.assertEqual(config["args"][config["args"].index("--project") + 1], "/workspace")
        self.assertEqual(config["env"]["SERENA_HOME"], "/state/mcp/serena/home")
        native = (RECIPE / "config/serena_config.yml").read_text()
        self.assertIn("/state/mcp/serena/projects/$projectFolderName", native)
        self.assertNotIn("$projectDir/.serena", native)


class OpenHandsFrozenOracleTests(unittest.TestCase):
    # Synthetic positive control for the oracle only. This implementation is
    # outside the mounted recipe; a real E2E always starts with the broken copy.
    FIX = '''def compress_ranges(values):
    ranges = []
    for value in sorted(set(values)):
        if ranges and value == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], value)
        else:
            ranges.append((value, value))
    return ranges
'''

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.result = Path(self.tmp.name)
        self.checker = load_recipe_module("e2e/check.py")
        self.helpers = load_recipe_module("recipe.py")
        shutil.copytree(RECIPE / "e2e/fixture-repo", self.result / "workspace")
        (self.result / "worker").mkdir()
        baseline = self.checker.run_tests(self.result / "workspace")
        self.assertEqual((baseline["exit_code"], baseline["tests_run"], baseline["failures"], baseline["errors"]), (1, 1, 1, 0))
        (self.result / "baseline.json").write_text(json.dumps(baseline))
        pristine = self.helpers.inventory(RECIPE / "e2e/fixture-repo")
        self.events = [
            {"kind": "ActionEvent", "tool_name": "terminal", "tool_call_id": "synthetic", "action": {"command": "python -B -m unittest discover -s tests -v"}, "workspace": pristine},
            {"kind": "ObservationEvent", "tool_name": "terminal", "tool_call_id": "synthetic", "observation": {"exit_code": 1, "text": "test_ranges_follow_the_spec FAILED (failures=1)"}, "workspace": pristine},
        ]
        self.write_events()
        (self.result / "workspace/range_utils.py").write_text(self.FIX)

    def write_events(self):
        (self.result / "worker/events.jsonl").write_text("\n".join(map(json.dumps, self.events)) + "\n")

    def test_fixed_copy_passes_and_frozen_source_stays_broken(self):
        verdict = self.checker.check(self.result)
        self.assertTrue(verdict["passed"], verdict)
        self.assertEqual(verdict["changed_files"], ["range_utils.py"])
        self.assertEqual(verdict["tests"]["tests_run"], 1)

    def test_no_native_red_observation_cannot_pass(self):
        self.events = self.events[:1]
        self.write_events()
        verdict = self.checker.check(self.result)
        self.assertIn("no_native_test_failure_before_edit", verdict["failures"])

    def test_red_after_edit_cannot_pass(self):
        self.events[0]["workspace"] = self.helpers.inventory(self.result / "workspace")
        self.write_events()
        self.assertFalse(self.checker.check(self.result)["passed"])

    def test_deleted_or_skipped_test_and_extra_files_are_rejected(self):
        test = self.result / "workspace/tests/test_ranges.py"
        original = test.read_text()
        for content in ("", "import unittest\n" + original.replace("    def test_ranges", "    @unittest.skip('removed')\n    def test_ranges")):
            test.write_text(content)
            self.assertIn("diff_outside_allowed_files_or_empty", self.checker.check(self.result)["failures"])
        test.write_text(original)
        (self.result / "workspace/extra.txt").write_text("outside contract")
        self.assertFalse(self.checker.check(self.result)["passed"])

    def test_broken_answer_and_symlink_cannot_pass(self):
        source = self.result / "workspace/range_utils.py"
        source.write_text("def compress_ranges(values):\n    return []\n")
        self.assertIn("tests_not_passing_unskipped", self.checker.check(self.result)["failures"])
        source.unlink()
        source.symlink_to(RECIPE / "e2e/fixture-repo/range_utils.py")
        self.assertIn("nonregular_result", self.checker.check(self.result)["failures"])


class OpenHandsReceiptTests(unittest.TestCase):
    def test_truncated_native_summary_retains_failed_attempt_receipt(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp)
            (result / "worker").mkdir()
            (result / "window.json").write_text(json.dumps({"started_at": "2026-09-27T18:00:00Z", "finished_at": "2026-09-27T18:00:01Z", "worker_exit_code": 124}))
            (result / "check.json").write_text(json.dumps({"passed": False, "exit_code": 1, "failures": ["missing_result"]}))
            (result / "worker/native-summary.json").write_text('{"versions":')
            report = module.create_receipt(result, database=result / "absent.sqlite")
            self.assertFalse(report["task_passed"])
            self.assertFalse(report["evidence_complete"])
            self.assertIsNone(report["observed_versions"])
            self.assertEqual(report["gateway"]["status"], "unavailable")

    def test_cleanup_timeout_does_not_erase_primary_exit(self):
        host = load_recipe_module("host.py")
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "worker.log"
            effects = [subprocess.CompletedProcess(["synthetic"], 7), subprocess.TimeoutExpired(["synthetic-cleanup"], 30)]
            with patch.object(host.subprocess, "run", side_effect=effects):
                self.assertEqual(host.execute_container(["synthetic"], "fixture", log, 1), 7)
            cleanup = json.loads(log.with_suffix(".log.cleanup.json").read_text())
            self.assertFalse(cleanup["confirmed_removed"])

    def test_gateway_reads_only_authorized_columns_and_preserves_unknown_usage(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "fixture.sqlite"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE call_logs (timestamp, path, status, model, reasoning_effort_requested, reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, forbidden_prompt)")
            connection.execute("CREATE TABLE forbidden_credentials (secret)")
            row = ("2026-09-27T18:00:01Z", "/v1/responses", 200, "cx/gpt-6-astra-max", "max", "max", 30, 20, None, "private")
            connection.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
            connection.commit()
            connection.close()
            before = db.read_bytes()
            rows = module.gateway_rows(db, "2026-09-27T18:00:00Z", "2026-09-27T18:00:02Z")
            self.assertEqual(db.read_bytes(), before)
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]), set(module.COLUMNS))
            self.assertIsNone(rows[0]["tokens_reasoning"])
            self.assertNotIn("private", json.dumps(rows))
            self.assertEqual(module.gateway_rows(db, "2026-09-27T19:00:00Z", "2026-09-27T19:00:01Z"), [])
        source = (RECIPE / "receipt.py").read_text()
        self.assertNotIn("SELECT *", source)
        self.assertNotIn("sqlite_master", source)
        self.assertIn("?mode=ro", source)

    def test_skills_and_mcp_require_observations(self):
        module = load_recipe_module("receipt.py")
        action = {"kind": "ActionEvent", "tool_name": "ai-memory_memory_query"}
        observed = {"kind": "ObservationEvent", "tool_name": "ai-memory_memory_query", "observation": {"is_error": False}}
        skill = {"kind": "ObservationEvent", "tool_name": "invoke_skill", "observation": {"skill_name": "tdd", "is_error": False}}
        self.assertEqual(module.observations([action])["mcp_calls_observed"], {})
        report = module.observations([action, observed, skill])
        self.assertEqual(report["mcp_calls_observed"], {"ai-memory_memory_query": 1})
        self.assertEqual(report["skills_observed"], {"tdd": 1})


if __name__ == "__main__":
    unittest.main()
