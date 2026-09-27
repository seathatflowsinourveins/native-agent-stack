"""Offline recipe contract, frozen before the recipe exists.

References: OpenHands/software-agent-sdk v1.49.6 examples
01_standalone_sdk/{01_hello_world,07_mcp_integration,14_context_condenser}.py;
the user's 2026-09-27 runtime-worker acceptance contract. These are local
structural/fixture checks, not upstream SDK or live gateway acceptance.
"""

import asyncio
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

    def test_fresh_call_headers_keep_session_affinity(self):
        worker = load_recipe_module("worker.py")
        original = {"x-omniroute-session": "fixture-session"}
        first = worker.headers_for_call(original)
        second = worker.headers_for_call(original)
        self.assertNotEqual(first["Idempotency-Key"], second["Idempotency-Key"])
        self.assertEqual(first["x-omniroute-session"], second["x-omniroute-session"])
        self.assertEqual(original, {"x-omniroute-session": "fixture-session"})

    def test_header_transport_preserves_exact_native_llm_type_and_restores_methods(self):
        worker = load_recipe_module("worker.py")

        class NativeLLM:
            extra_headers = {"x-omniroute-session": "control-conversation"}

            def generate(self, **kwargs):
                return kwargs

            async def agenerate(self, **kwargs):
                return kwargs

        original_sync, original_async = NativeLLM.generate, NativeLLM.agenerate
        agent, condenser = NativeLLM(), NativeLLM()
        # The real SDK uses "type(obj) is LLM" for native usage/context binding.
        with worker.gateway_transport(NativeLLM):
            self.assertIs(type(agent), NativeLLM)
            self.assertIs(type(condenser), NativeLLM)
            calls = [agent.generate(), condenser.generate(), asyncio.run(agent.agenerate())]
            keys = {call["extra_headers"]["Idempotency-Key"] for call in calls}
            self.assertEqual(len(keys), 3)
            self.assertEqual({call["extra_headers"]["x-omniroute-session"] for call in calls},
                             {"control-conversation"})
            for kwargs in ({"response_format": {"type": "json_object"}},
                           {"text": {"format": {"type": "json_schema"}}}, {"temperature": 0.1}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    agent.generate(**kwargs)
        self.assertIs(NativeLLM.generate, original_sync)
        self.assertIs(NativeLLM.agenerate, original_async)

    def test_runtime_model_override_and_native_tool_filter(self):
        helpers = load_recipe_module("recipe.py")
        result = helpers.llm_config(self.read_json("config/worker.json"), "cx/gpt-6-sol-max")
        self.assertEqual(result["model"], "openai/cx/gpt-6-sol-max")
        self.assertEqual(result["base_url"], "http://10.0.2.2:20128/v1")
        pattern = re.compile(helpers.tool_filter(self.read_json("config/mcp-policy.json")))
        for name in ("terminal", "file_editor", "context-mode_ctx_execute", "serena_find_symbol", "ai-memory_memory_query", "qmd_query", "socraticode_codebase_health", "jcodemunch_order"):
            self.assertIsNotNone(pattern.fullmatch(name), name)
        for name in ("context-mode_ctx_upgrade", "context-mode_ctx_purge", "ai-memory_memory_write", "socraticode_codebase_index", "jcodemunch_delete_index", "headroom_headroom_compress", "memory_query", "qmd_query_evil"):
            self.assertIsNone(pattern.fullmatch(name), name)

    def test_gateway_rejects_non_gpt6_models_and_unsafe_structured_modes(self):
        helpers = load_recipe_module("recipe.py")
        for model in ("claude-opus-5-5", "cx/claude-opus-5-5", "cx/gpt-5", "openai/cx/gpt-6-astra-max"):
            with self.subTest(model=model), self.assertRaises(ValueError):
                helpers.llm_config(self.read_json("config/worker.json"), model)
        for change in ({"temperature": 0.1}, {"response_format": {"type": "json_object"}}, {"native_tool_calling": False}):
            config = self.read_json("config/worker.json")
            config["llm"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                helpers.llm_config(config)

    def test_every_container_is_owned_and_has_no_published_port(self):
        host = load_recipe_module("host.py")
        args = host.docker_args(self.read_json("pins.json"), "rw-openhands-control")
        self.assertIn("com.native-agent-stack.owner=gpt6-omniroute-framework-integration", args)
        self.assertNotIn("-p", args)
        self.assertNotIn("--publish", args)
        with self.assertRaises(ValueError):
            host.docker_args(self.read_json("pins.json"), "unowned")

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


class OpenHandsUpstreamAdapterTests(unittest.TestCase):
    """Synthetic transport controls from SWE-bench 4.1.0 reporting.py.

    These exercise our parser only; they are not upstream grader executions.
    """
    INSTANCE = "django__django-11333"

    def setUp(self):
        self.checker = load_recipe_module("e2e/check.py")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.result = Path(self.tmp.name)

    def report(self, bucket):
        data = {key: [] for key in ("resolved_ids", "unresolved_ids", "error_ids", "empty_patch_ids", "incomplete_ids", "submitted_ids")}
        data["submitted_ids"] = [self.INSTANCE]
        data["schema_version"] = 2
        data[bucket] = [self.INSTANCE]
        data["total_instances"] = 500
        # The upstream report can include unsubmitted IDs from the full split.
        if bucket != "incomplete_ids":
            data["incomplete_ids"] = ["unsubmitted-other-task"]
        return data

    def invoke(self, data):
        path = self.result / "report.json"
        path.write_text(json.dumps(data))
        return subprocess.run([sys.executable, str(RECIPE / "e2e/check.py"),
                               "--report", str(path), "--instance-id", self.INSTANCE],
                              capture_output=True, text=True)

    def test_known_pass_relays_upstream_resolution(self):
        completed = self.invoke(self.report("resolved_ids"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertIs(result["upstream_resolved"], True)
        self.assertEqual(result["verdict_source"], "swebench==4.1.0")

    def test_known_fail_is_not_a_successful_process_verdict(self):
        for bucket in ("unresolved_ids", "empty_patch_ids", "error_ids", "incomplete_ids"):
            with self.subTest(bucket=bucket):
                completed = self.invoke(self.report(bucket))
                self.assertEqual(completed.returncode, 1, completed.stderr)
                self.assertIs(json.loads(completed.stdout)["upstream_resolved"], False)

    def test_malformed_missing_duplicate_and_conflicting_outputs_fail_closed(self):
        conflict = self.report("resolved_ids")
        conflict["unresolved_ids"] = [self.INSTANCE]
        wrong = self.report("resolved_ids")
        wrong["submitted_ids"] = ["wrong-task"]
        for value in ({}, [], {"resolved_ids": "true"}, conflict, wrong):
            with self.subTest(value=value):
                self.assertEqual(self.invoke(value).returncode, 2)
        path = self.result / "broken.json"
        path.write_text('{"resolved_ids": [')
        with self.assertRaises(ValueError):
            self.checker.read_report(path, self.INSTANCE)

    def test_input_sanity_does_not_grade_the_patch(self):
        path = self.result / "output.jsonl"
        for patch_text in ("", "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-broken\n+fixed\n"):
            path.write_text(json.dumps({"instance_id": self.INSTANCE, "test_result": {"git_patch": patch_text}}) + "\n")
            checked = self.checker.check_input(path, self.INSTANCE)
            self.assertIs(checked["ready_to_grade"], True)
            self.assertNotIn("passed", checked)
        for content in ("", "{", json.dumps({"instance_id": self.INSTANCE}),
                        json.dumps({"instance_id": self.INSTANCE, "test_result": {"git_patch": 1}})):
            path.write_text(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.checker.check_input(path, self.INSTANCE)
        row = json.dumps({"instance_id": self.INSTANCE, "test_result": {"git_patch": ""}})
        path.write_text(row + "\n" + row + "\n")
        with self.assertRaises(ValueError):
            self.checker.check_input(path, self.INSTANCE)

    def test_shared_skills_installer_is_the_only_install_path(self):
        host = load_recipe_module("host.py")
        workspace = self.result / "workspace"
        (workspace / ".git/info").mkdir(parents=True)
        with patch.object(host.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            host.install_workspace_skills(ROOT, workspace)
        self.assertEqual(run.call_args.args[0], [
            sys.executable, str(ROOT / "tools/adoption/install_skills.py"),
            "--manifest", "blueprints/runtime-workers/skills/manifest.json",
            "--project-dir", str(workspace), "--agent", "universal",
        ])
        self.assertEqual(run.call_args.kwargs["cwd"], ROOT)
        source = (RECIPE / "host.py").read_text()
        self.assertNotIn('Path.home() / ".agents/skills"', source)
        self.assertNotIn("link.symlink_to", source)

    def test_project_skills_bookkeeping_is_excluded_from_worker_patch(self):
        host = load_recipe_module("host.py")
        workspace = self.result / "workspace"
        subprocess.run(["git", "init", "--quiet", str(workspace)], check=True, capture_output=True)

        def installed(*args, **kwargs):
            (workspace / ".agents/skills/tdd").mkdir(parents=True)
            (workspace / ".agents/skills/tdd/SKILL.md").write_text("synthetic skill control\n")
            (workspace / "skills-lock.json").write_text("{}\n")
            return subprocess.CompletedProcess([], 0)

        with patch.object(host.subprocess, "run", side_effect=installed):
            host.install_workspace_skills(ROOT, workspace)
        # Vercel skills 1.7.0 writes exactly these root setup paths. Ask Git
        # which would be ignored; never stage or commit this synthetic checkout.
        checked = subprocess.run(["git", "-C", str(workspace), "check-ignore", "--no-index", "--stdin"],
                                 input=".agents/skills/tdd/SKILL.md\nskills-lock.json\nnested/skills-lock.json\n",
                                 capture_output=True, text=True)
        self.assertEqual(checked.stdout.splitlines(), [".agents/skills/tdd/SKILL.md", "skills-lock.json"])

    def test_project_skills_install_refuses_task_path_conflicts(self):
        host = load_recipe_module("host.py")
        for reserved in (".agents", "skills-lock.json"):
            with self.subTest(reserved=reserved):
                workspace = self.result / reserved.replace(".", "_")
                workspace.mkdir()
                (workspace / reserved).write_text("preexisting task content\n")
                with patch.object(host.subprocess, "run") as run, self.assertRaises(ValueError):
                    host.install_workspace_skills(ROOT, workspace)
                run.assert_not_called()
                self.assertEqual((workspace / reserved).read_text(), "preexisting task content\n")

    def test_official_grader_container_transport_preserves_upstream_settings(self):
        module = load_recipe_module("e2e/docker_grader.py")
        original = {"name": "sweb.eval.django__django-11333.attempt", "image": "swebench/example:latest",
                    "platform": "linux/amd64", "detach": True}
        changed = module.owned_container_options(original)
        self.assertEqual(changed["name"], "rw-openhands-sweb.eval.django__django-11333.attempt")
        self.assertEqual(changed["labels"]["com.native-agent-stack.owner"],
                         "gpt6-omniroute-framework-integration")
        self.assertEqual(changed["image"], original["image"])
        self.assertEqual(original["name"], "sweb.eval.django__django-11333.attempt")
        for update in ({"ports": {"8000/tcp": 3710}}, {"name": "unowned"}, {"volumes": {"unowned": {}}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                module.owned_container_options({**original, **update})

    def test_task_adapter_hides_oracle_and_requires_frozen_original_bytes(self):
        module = load_recipe_module("e2e/task.py")
        row = {"instance_id": self.INSTANCE, "repo": "django/django", "base_commit": "a" * 40,
               "problem_statement": "Fix the selected issue.", "version": "1.7",
               "patch": "gold-hidden", "test_patch": "test-hidden",
               "FAIL_TO_PASS": '["private-test"]', "PASS_TO_PASS": "[]"}
        path = self.result / "task.json"
        path.write_text(json.dumps([row]))
        import hashlib
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        task = module.load_task(path, digest)
        prompt = module.worker_instruction(task)
        self.assertIn(row["problem_statement"], prompt)
        for secret in ("gold-hidden", "test-hidden", "private-test"):
            self.assertNotIn(secret, prompt)
        with self.assertRaises(ValueError):
            module.load_task(path, "0" * 64)
        path.write_text(json.dumps([row, row]))
        with self.assertRaises(ValueError):
            module.load_task(path, hashlib.sha256(path.read_bytes()).hexdigest())


class OpenHandsReceiptTests(unittest.TestCase):
    def test_local_pass_field_is_never_a_worker_verdict(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp)
            (result / "window.json").write_text(json.dumps({
                "started_at": "2026-09-27T18:00:00Z", "finished_at": "2026-09-27T18:00:02Z",
                "worker_exit_code": 0,
            }))
            (result / "check.json").write_text(json.dumps({"passed": True, "exit_code": 0}))
            receipt = module.create_receipt(result, database=result / "absent.sqlite")
            self.assertFalse(receipt["task_passed"])
            self.assertIsNone(receipt["upstream_grader"]["upstream_resolved"])

    def test_verdict_is_read_from_official_report_even_when_wrapper_claims_pass(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp)
            instance = "django__django-11333"
            (result / "window.json").write_text(json.dumps({
                "started_at": "2026-09-27T18:00:00Z", "finished_at": "2026-09-27T18:00:02Z",
                "worker_exit_code": 0, "run_id": "rw-openhands-control", "instance_id": instance,
            }))
            (result / "check.json").write_text(json.dumps({
                "upstream_resolved": True, "grader_exit_code": 0, "conversion_exit_code": 0,
            }))
            data = {"schema_version": 2, "submitted_ids": [instance], "resolved_ids": [],
                    "unresolved_ids": [instance], "empty_patch_ids": [], "error_ids": [], "incomplete_ids": []}
            report = result / "OpenHands.rw-openhands-control.json"
            report.write_text(json.dumps(data))
            self.assertFalse(module.create_receipt(result, database=result / "absent.sqlite")["task_passed"])
            data.update(resolved_ids=[instance], unresolved_ids=[])
            report.write_text(json.dumps(data))
            self.assertTrue(module.create_receipt(result, database=result / "absent.sqlite")["task_passed"])

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
        report = module.observations([action, observed, skill], ["tdd"])
        self.assertEqual(report["mcp_calls_observed"], {"ai-memory_memory_query": 1})
        self.assertEqual(report["skills_observed"], {"tdd": 1})


if __name__ == "__main__":
    unittest.main()
