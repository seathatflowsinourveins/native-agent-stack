"""Offline recipe contract, frozen before the recipe exists.

References: OpenHands/software-agent-sdk v1.49.6 examples
01_standalone_sdk/{01_hello_world,07_mcp_integration,14_context_condenser}.py;
the user's 2026-09-27 runtime-worker acceptance contract. These are local
structural/fixture checks, not upstream SDK or live gateway acceptance.
"""

import asyncio
import contextlib
import io
import json
import os
import importlib.util
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch, mock_open


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "blueprints/runtime-workers/openhands"
FIXTURE_CONVERSATION_ID = str(uuid.UUID(int=1))


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

    def test_dispatch_fixtures_pass_publication_identifier_policy(self):
        # Reuse the repository policy; synthetic native IDs must be constructed
        # at runtime so published source cannot be mistaken for session state.
        from scripts.validate import PRIVATE_CONTENT
        pattern = dict(PRIVATE_CONTENT)["local session identifier"]
        self.assertIsNone(pattern.search(Path(__file__).read_text()))

    def test_grader_sync_keeps_the_hash_seeded_interpreter(self):
        # benchmarks@405bae7 .python-version:1 requests 3.12; our hashed
        # build tools were seeded into 3.13. uv must retain that interpreter.
        script = (RECIPE / "install-grader.sh").read_text()
        sync = next(line for line in script.splitlines() if line.startswith("uv sync "))
        self.assertIn('--python "$grader_dir/.venv/bin/python"', sync)

    def test_explicit_arms_keep_one_slash_routes_and_compression_separate(self):
        helpers = load_recipe_module("recipe.py")
        cfg = self.read_json("config/worker.json")
        for arm, model, port, headers in (
            ("control", "cx/gpt-6-astra-max", 20128, {}),
            ("engines-on", "sharedgw/gpt-6-astra-max", 20129,
             {"x-omniroute-compression": "allow-lossy"}),
        ):
            with self.subTest(arm=arm):
                selected = helpers.arm_config(arm)
                self.assertEqual(selected["requested_model"], model)
                self.assertEqual(selected["base_url"], f"http://10.0.2.2:{port}/v1")
                self.assertEqual(selected["headers"], headers)
                llm = helpers.llm_config(cfg, arm=arm)
                self.assertEqual(llm["model"], "openai/" + model)
                self.assertEqual(llm["reasoning_effort"], "max")
                self.assertEqual(llm["extra_headers"], headers)
        for kwargs in (
            {"arm": "engines-on", "model": "sharedgw/cx/gpt-6-astra-max"},
            {"arm": "engines-on", "model": "sharedgw/claude-opus-5-5"},
            {"arm": "control", "model": "sharedgw/gpt-6-astra-max"},
            {"arm": "engines-on", "base_url": "http://10.0.2.2:20128/v1"},
            {"arm": "control", "base_url": "https://example.invalid/v1"},
            {"arm": "other"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                helpers.llm_config(cfg, **kwargs)
        cfg["llm"]["reasoning_effort"] = "high"
        with self.assertRaises(ValueError):
            helpers.llm_config(cfg)

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
        self.assertEqual(config["runtime"]["published_ports"], ["127.0.0.1:3730:8000"])
        self.assertEqual(config["arm_env"], "OPENHANDS_ARM")
        self.assertEqual(config["base_url_env"], "OPENHANDS_BASE_URL")
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

    def test_worker_arm_headers_and_response_correlation_capture(self):
        worker = load_recipe_module("worker.py")
        for arm in ("control", "engines-on"):
            cfg = worker.worker_llm_config({"OPENHANDS_ARM": arm}, "dispatch-fixture")
            self.assertEqual(cfg["extra_headers"]["x-omniroute-session"], "dispatch-fixture")
            self.assertEqual("x-omniroute-compression" in cfg["extra_headers"], arm == "engines-on")
        response = SimpleNamespace(raw_response=SimpleNamespace(
            _hidden_params={"headers": {"X-Correlation-Id": "opaque-response-id"}}))

        class NativeLLM:
            extra_headers = {"x-omniroute-session": "fixture"}

            def generate(self, **kwargs):
                return response

            async def agenerate(self, **kwargs):
                return response

        captured = []
        with worker.gateway_transport(NativeLLM, correlation_callback=captured.append):
            self.assertIs(NativeLLM().generate(), response)
            self.assertIs(asyncio.run(NativeLLM().agenerate()), response)
        self.assertEqual(captured, ["opaque-response-id", "opaque-response-id"])
        self.assertIsNone(worker.response_correlation(SimpleNamespace(raw_response=object())))

    def test_native_start_request_uses_sdk_serialization_and_shared_agent(self):
        worker = load_recipe_module("worker.py")
        created = []

        class NativeModel:
            def __init__(self, **kwargs):
                self.fields = kwargs
                created.append(self)

            def model_dump(self, **kwargs):
                self.dump_options = kwargs
                return self.fields

        modules = {
            "openhands.sdk": SimpleNamespace(TextContent=NativeModel),
            "openhands.sdk.workspace": SimpleNamespace(LocalWorkspace=NativeModel),
            "openhands.sdk.conversation.request": SimpleNamespace(
                StartConversationRequest=NativeModel, SendMessageRequest=NativeModel),
        }
        with patch.dict(sys.modules, modules), patch.object(worker, "build_agent", return_value=("native-agent", {}, [])), \
                patch.object(worker, "worker_hooks", return_value="native-hooks"):
            body = worker.start_request("Fix the issue", "rw-openhands-fixture", "engines-on")
        self.assertEqual(body["agent"], "native-agent")
        self.assertEqual(body["workspace"].fields["working_dir"], "/workspace")
        self.assertTrue(body["initial_message"].fields["run"])
        self.assertEqual(body["max_iterations"], 40)
        self.assertEqual(body["tags"], {"source": "ultracode", "dispatch": "rw-openhands-fixture", "arm": "engines-on"})
        self.assertEqual(body["hook_config"], "native-hooks")
        self.assertEqual(created[-1].dump_options,
                         {"exclude_defaults": True, "mode": "json", "context": {"expose_secrets": True}})

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

    def test_model_container_is_nonroot_and_network_is_explicit(self):
        host = load_recipe_module("host.py")
        pins = self.read_json("pins.json")
        args = host.docker_args(pins, "rw-openhands-fixture")
        self.assertEqual(args[args.index("--user") + 1], "10001:10001")
        self.assertIn("--network=none", args)
        with self.assertRaises(ValueError):
            host.docker_args(pins, "rw-openhands-agent", network="bridge")
        args = host.docker_args(pins, "rw-openhands-agent", network="rw-openhands-egress-control")
        self.assertIn("--network=rw-openhands-egress-control", args)
        self.assertIn("--cap-drop=ALL", args)
        self.assertIn("--security-opt=no-new-privileges", args)
        self.assertIn("HOME=/state/home", args)

    def test_mount_allowlist_checks_resolved_targets_and_secret_ancestors(self):
        host = load_recipe_module("host.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            eco = root / "ecosystem"
            good = eco / "bin"
            good.mkdir(parents=True)
            self.assertEqual(host.checked_mount(good, [good]), good.resolve())
            home = root / "home"
            secret = home / ".config/native-agent-stack"
            secret.mkdir(parents=True)
            alias = root / "alias"
            alias.symlink_to(secret, target_is_directory=True)
            with patch.object(Path, "home", return_value=home):
                for path in (home.parent, home, home / ".config", alias, secret):
                    with self.subTest(path=path), self.assertRaises(ValueError):
                        host.checked_mount(path, [path])
            with self.assertRaises(ValueError):
                host.checked_mount(eco, [good])

    def test_remote_mcp_services_are_not_registered_in_model_network(self):
        helper = load_recipe_module("recipe.py")
        variables = self.read_json("config/host.example.json")["variables"]
        mcp = helper.render_mcp(variables)
        self.assertFalse(mcp["ai-memory"]["enabled"])
        self.assertFalse(mcp["socraticode"]["enabled"])

    def test_host_template_names_the_two_required_network_policy_receipts(self):
        host = self.read_json("config/host.example.json")
        self.assertEqual(set(host["egress"]), {"control", "engines-on"})
        for arm, entry in host["egress"].items():
            self.assertEqual(entry["network"], "rw-openhands-egress-" + arm)
            self.assertIn("policy_receipt", entry)

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

    def test_round1_orphans_are_not_shipped(self):
        # F20: `git grep -F` at 45d40f6c found no reference to these round-1
        # files outside evidence logs and manifests/evidence.json.
        for relative in ("config/skills.lock.json", "e2e/frozen.json", "e2e/task.txt",
                         "e2e/fixture-repo/README.md", "e2e/fixture-repo/range_utils.py",
                         "e2e/fixture-repo/tests/test_ranges.py", "e2e/fixture-repo"):
            with self.subTest(path=relative):
                self.assertFalse(os.path.lexists(RECIPE / relative))

    def test_agent_server_image_scan_receipt_matches_the_pinned_digest(self):
        # F18: the relock covers only the recipe venv. The image's server binary
        # is built from upstream's unchanged uv.lock, so the digest is scanned.
        from scripts.validate import PRIVATE_CONTENT
        name = "evidence/agent-server-image-grype-20260928.json"
        all_pins = self.read_json("pins.json")
        pins = all_pins["image"]
        receipt = self.read_json(name)
        keys = ("ref", "platform", "manifest_sha256", "config_sha256")
        self.assertEqual({k: receipt["image"][k] for k in keys}, {k: pins[k] for k in keys})
        # A containerd image store reports the index digest as .Id, so identity
        # rests on the platform descriptor and the cataloged config bytes.
        identity = receipt["image"]["identity"]
        self.assertIn(pins["ref"], identity["daemon_repo_digests"])
        self.assertEqual(identity["daemon_platform_descriptor_digest"], "sha256:" + pins["manifest_sha256"])
        self.assertEqual(identity["cataloged_image_id"], "sha256:" + pins["config_sha256"])
        self.assertEqual(identity["cataloged_config_sha256"], pins["config_sha256"])
        self.assertEqual({k: receipt["scanner"][k] for k in ("name", "version", "repository")},
                         {"name": "grype", "version": "0.119.0", "repository": "https://github.com/anchore/grype"})
        self.assertRegex(receipt["database"]["built"], r"^\d{4}-\d{2}-\d{2}T")
        counts = receipt["counts"]
        self.assertEqual(set(counts["by_severity"]), {"Critical", "High", "Medium", "Low", "Negligible", "Unknown"})
        self.assertEqual(sum(counts["by_severity"].values()), counts["total"])
        self.assertEqual(sum(sum(p["by_severity"].values()) for p in receipt["flagged_packages"]), counts["total"])
        self.assertEqual(len(receipt["flagged_packages"]), counts["flagged_packages"])
        self.assertEqual(receipt["upstream_lock"]["sha256"], all_pins["uv_lock"]["sha256"])
        self.assertEqual({p["name"]: p["version"] for p in receipt["upstream_lock_flagged"]},
                         {"anyio": "4.11.0", "click": "8.1.8", "pypdf": "6.14.2", "soupsieve": "2.8.4"})
        # The PyInstaller archive is opaque to the cataloger: lock evidence, not an image observation.
        self.assertTrue(all(p["observed_by_cataloger"] is False for p in receipt["upstream_lock_flagged"]))
        text = json.dumps(receipt)
        for description, pattern in PRIVATE_CONTENT:
            self.assertIsNone(pattern.search(text), description)
        self.assertIn(name, (RECIPE / "README.md").read_text())


class OpenHandsUpstreamAdapterTests(unittest.TestCase):
    """Synthetic transport controls from SWE-bench 4.1.0 reporting.py.

    These exercise our parser only; they are not upstream grader executions.
    """
    INSTANCE = "django__django-11333"

    # Temp roots are realpath-resolved throughout: read_bounded refuses every symlink hop from "/", and macOS temp
    # dirs sit under the /var -> /private/var symlink.
    def setUp(self):
        self.checker = load_recipe_module("e2e/check.py")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.result = Path(self.tmp.name).resolve()

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
                self.assertEqual(completed.returncode, 3 if bucket in {"error_ids", "incomplete_ids"} else 1, completed.stderr)
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
        with patch.object(host.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
                patch.object(Path, "open", mock_open()):
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
        # Round 3 forbids writing Git metadata, even in synthetic checkouts.
        # Verify the exported exclusion contract with an in-memory stream.
        output = mock_open()
        with patch.object(host.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), \
                patch.object(Path, "open", output):
            host.install_workspace_skills(ROOT, workspace)
        output().write.assert_called_once_with("\n/.agents/\n/skills-lock.json\n")

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
        self.assertEqual(set(changed) - set(original), {"labels"})
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

    def absent_gateway_receipt(self):
        # Never open a live gateway database from a unit test.
        receipts = load_recipe_module("receipt.py")
        return lambda result: receipts.create_receipt(result, database=result / "absent.sqlite")

    def test_preflight_failure_still_has_status_receipt_and_setup_exit(self):
        host = load_recipe_module("host.py")
        output = io.StringIO()
        run_id = "rw-openhands-fixture"
        with patch.object(host, "preflight", side_effect=ValueError("synthetic_setup_failure")), \
                patch.object(host, "create_receipt", side_effect=self.absent_gateway_receipt()), \
                contextlib.redirect_stdout(output):
            code = host.run(self.result / "prefix", self.result, run_id=run_id, arm="engines-on")
        self.assertEqual(code, 3)
        returned = json.loads(output.getvalue())
        path = self.result / "runs" / run_id / "engines-on"
        self.assertEqual(returned["receipt"], str(path / "receipt.json"))
        self.assertEqual(returned["run_id"], run_id)
        self.assertEqual(returned["arm"], "engines-on")
        self.assertEqual(returned["failure_stage"], "preflight")
        self.assertFalse(returned["task_passed"])
        self.assertEqual(json.loads((path / "status.json").read_text())["status"], "failed")
        self.assertTrue((path / "receipt.json").is_file())
        for result, expected in (({"task_passed": True, "evidence_complete": True}, 0),
                                 ({"task_passed": True, "evidence_complete": False}, 2),
                                 ({"upstream_grader": {"upstream_resolved": False, "upstream_bucket": "unresolved_ids"}}, 1),
                                 ({"upstream_grader": {"upstream_resolved": False, "upstream_bucket": "unresolved_ids", "grader_exit_code": 124}}, 3),
                                 ({"failure_stage": "preflight"}, 3)):
            self.assertEqual(host.result_exit(result), expected)

    def test_agent_limit_terminations_are_graded_but_never_success(self):
        # F16: an officially graded partial patch after an agent limit exits 1;
        # grading infrastructure failures keep exit 3.
        host = load_recipe_module("host.py")
        graded = {"grader_exit_code": 0, "conversion_exit_code": 0}
        for termination in ("stuck", "max_iterations_reached"):
            for verdict, expected in (({"upstream_resolved": True, "upstream_bucket": "resolved_ids", **graded}, 1),
                                      ({"upstream_resolved": False, "upstream_bucket": "unresolved_ids", **graded}, 1),
                                      ({"upstream_resolved": False, "upstream_bucket": "empty_patch_ids", **graded}, 1),
                                      ({"upstream_resolved": False, "upstream_bucket": "error_ids", **graded}, 3),
                                      ({"upstream_resolved": None, "grader_exit_code": 124}, 3)):
                with self.subTest(termination=termination, verdict=verdict):
                    self.assertEqual(host.result_exit({
                        "agent_termination": termination, "failure_stage": None, "task_passed": False,
                        "evidence_complete": False, "upstream_grader": verdict}), expected)

    def test_session_key_preflight_checks_the_variable_name_only(self):
        # SDK@fcc102a agent_server/__main__.py:282-285 binds all interfaces only
        # with a session key; config.py:24 names OH_SESSION_API_KEYS_0. File
        # format: docker/cli@v29.8.1 pkg/kvfile/kvfile.go:92-124.
        host = load_recipe_module("host.py")
        name = "OH_SESSION_API_KEYS_0"
        marker = "-".join(("synthetic", "fixture", "marker"))
        env = self.result / "server.env"
        for text, accepted in ((f"{name}={marker}\n", True),
                               (f"\N{BYTE ORDER MARK} \t{name}={marker}\r\n", True),
                               (f"OTHER_NAME=1\n{name}={marker}", True),
                               (f"# {name}={marker}\n", False),
                               (f"{name}\n", False),
                               (f"{name}_1={marker}\n", False),
                               (f" {name} ={marker}\n", False),
                               (f"OTHER_NAME={marker}\x0c{name}={marker}\n", False),
                               ("", False)):
            with self.subTest(text=text.replace(marker, "<marker>")):
                env.write_text(text)
                env.chmod(0o600)
                with patch.dict(os.environ, {"OPENHANDS_SERVER_ENV": str(env)}):
                    if accepted:
                        self.assertEqual(host.check_server_env(), env)
                        continue
                    with self.assertRaises(ValueError) as caught:
                        host.check_server_env()
                self.assertNotIn(marker, str(caught.exception))
        env.write_text(f"{name}={marker}\n")
        env.chmod(0o644)
        with patch.dict(os.environ, {"OPENHANDS_SERVER_ENV": str(env)}), self.assertRaises(ValueError):
            host.check_server_env()
        with patch.dict(os.environ, {"OPENHANDS_SERVER_ENV": ""}), self.assertRaises(ValueError):
            host.check_server_env()

    def test_missing_session_key_name_stops_preflight_without_exposing_values(self):
        host = load_recipe_module("host.py")
        marker = "-".join(("synthetic", "fixture", "marker"))
        env = self.result / "server.env"
        env.write_text(f"OTHER_NAME={marker}\n")
        env.chmod(0o600)
        output = io.StringIO()
        with patch.object(host, "preflight", return_value=({}, {}, {})), \
                patch.object(host, "read_json") as read_json, \
                patch.object(host, "create_receipt", side_effect=self.absent_gateway_receipt()), \
                patch.dict(os.environ, {"OPENHANDS_SERVER_ENV": str(env)}), contextlib.redirect_stdout(output):
            code = host.run(self.result / "prefix", self.result, run_id="rw-openhands-fixture", arm="control")
        self.assertEqual(code, 3)
        read_json.assert_not_called()  # Stopped before the installation record.
        path = self.result / "runs/rw-openhands-fixture/control"
        self.assertEqual(json.loads(output.getvalue())["failure_stage"], "preflight")
        self.assertEqual(json.loads((path / "window.json").read_text())["failure_type"], "ValueError")
        for text in (output.getvalue(), *(p.read_text() for p in path.glob("*.json"))):
            self.assertNotIn(marker, text)

    def test_port_outside_owned_range_fails_in_preflight(self):
        # PR #428 crawl4ai host.py:44-45: exact int (bool refused) in 3730..3799.
        host = load_recipe_module("host.py")
        self.assertEqual(host.DEFAULT_PORT, 3730)
        for port in (3730, 3740, 3799):
            self.assertEqual(host.owned_port(port), port)
        self.assertEqual(host.cli_port("3740"), 3740)
        for index, port in enumerate((3729, 3800, True, 3740.0, "3740", None, host.cli_port("37x0"))):
            with self.subTest(port=port):
                with self.assertRaises(ValueError):
                    host.owned_port(port)
                output = io.StringIO()
                with patch.object(host, "preflight") as preflight, \
                        patch.object(host, "create_receipt", side_effect=self.absent_gateway_receipt()), \
                        contextlib.redirect_stdout(output):
                    code = host.run(self.result / "prefix", self.result, run_id=f"rw-openhands-port-{index}",
                                    arm="control", port=port)
                self.assertEqual(code, 3)
                self.assertEqual(json.loads(output.getvalue())["failure_stage"], "preflight")
                preflight.assert_not_called()

    def test_clone_uses_pinned_swebench_branch_mapping(self):
        host = load_recipe_module("host.py")
        task = {"repo": "pytest-dev/pytest", "base_commit": "a" * 40}
        with patch.object(host.subprocess, "check_output", return_value='"4.6.x"\n') as call:
            argv = host.clone_command(self.result, task, self.result / "workspace")
        self.assertEqual(argv[argv.index("--branch") + 1], "4.6.x")
        self.assertIn("REPO_BASE_COMMIT_BRANCH", call.call_args.args[0][2])

    def test_installer_mounts_exclude_snapshot_from_writable_paths(self):
        host = load_recipe_module("host.py")
        prefix, state = self.result / "prefix", self.result / "state"
        mounts = host.install_mounts(prefix, state)
        writable = [v for v in mounts if v.startswith("type=bind") and not v.endswith(",readonly")]
        self.assertEqual(len(writable), 2)
        self.assertTrue(any(f"src={prefix}/venv," in v for v in writable))
        self.assertFalse(any(f"src={prefix}," in v for v in writable))

    # Docker image inspect shapes for the pinned agent-server image. moby
    # docker-v29.8.1 (464cd50c) containerd store: daemon/containerd/
    # image_inspect.go:28,71-73,95,97 report the pulled index as Id/Descriptor,
    # or the platform manifest when --platform is given (this host's probe,
    # 2026-09-28). Classic store: daemon/images/image_inspect.go:59 reports the
    # config digest (daemon/internal/image/store.go:152,160; fs.go:120) and no
    # Descriptor (api/swagger.yaml:1839-1850); a pull by index digest records
    # the index reference in RepoDigests (distribution/pull_v2.go:431-434).
    @staticmethod
    def image_inspect(pins, store):
        image = pins["image"]
        index = "sha256:" + image["ref"].rsplit("@sha256:", 1)[1]
        manifest, config = "sha256:" + image["manifest_sha256"], "sha256:" + image["config_sha256"]
        common = {"RepoDigests": [image["ref"]], "Os": "linux", "Architecture": "amd64"}
        if store == "classic":
            return {**common, "Id": config}, {**common, "Id": config}
        return ({**common, "Id": index, "Descriptor": {
                    "mediaType": "application/vnd.oci.image.index.v1+json", "digest": index, "size": 1609}},
                {**common, "Id": manifest, "Descriptor": {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json", "digest": manifest, "size": 4313,
                    "platform": {"architecture": "amd64", "os": "linux"}}})

    def install_with(self, host, pins, plain, selected, root):
        """Run install() on mocked inspect output; no Docker command runs."""
        def inspect(argv, **kwargs):
            self.assertEqual(argv[:len(host.DOCKER) + 2], [*host.DOCKER, "image", "inspect"])
            self.assertEqual(argv[-1], pins["image"]["ref"])
            return json.dumps([selected if "--platform" in argv else plain])

        with patch.object(host, "preflight", return_value=(pins, {}, {})), \
                patch.object(host, "download_verified"), patch.object(host.subprocess, "run"), \
                patch.object(host.subprocess, "check_output", side_effect=inspect) as calls, \
                patch.object(host, "execute_container", return_value=0) as execute, \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                host.install(root / "prefix", root / "state")
            except ValueError as exc:
                return str(exc), execute, calls
        return None, execute, calls

    def test_install_accepts_the_pinned_image_on_containerd_and_classic_stores(self):
        host = load_recipe_module("host.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        ref = pins["image"]["ref"]
        for store in ("containerd", "classic"):
            with self.subTest(store=store):
                error, execute, calls = self.install_with(host, pins, *self.image_inspect(pins, store),
                                                          self.result / store)
                self.assertIsNone(error)
                execute.assert_called_once()
                argv = [call.args[0] for call in calls.call_args_list]
                self.assertEqual(argv, [[*host.DOCKER, "image", "inspect", ref],
                                        [*host.DOCKER, "image", "inspect", "--platform", "linux/amd64", ref]])
                installed = json.loads((self.result / store / "state/installation.json").read_text())
                self.assertEqual(installed["image_store"], store)

    def test_install_refuses_each_image_identity_mismatch_before_any_container(self):
        host = load_recipe_module("host.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        image = pins["image"]
        repo, index = image["ref"].split("@", 1)
        manifest, config = "sha256:" + image["manifest_sha256"], "sha256:" + image["config_sha256"]
        other = "sha256:" + "0" * 64
        cases = []
        for store in ("containerd", "classic"):
            # Each case changes one field of a passing shape.
            for digests in ([], None, ["docker.io/" + image["ref"]], ["ghcr.io/openhands/other@" + index],
                            [repo + "@" + manifest], [repo + "@" + config], [repo + ":1.49.6-python"]):
                cases.append((store, "plain", {"RepoDigests": digests}, "image_repo_digest_mismatch"))
            cases.append((store, "platform", {"RepoDigests": [repo + "@" + other]}, "image_repo_digest_mismatch"))
            for value in (manifest, other, None):
                cases.append((store, "plain", {"Id": value}, "image_configuration_hash_mismatch"))
            cases.append((store, "platform", {"Architecture": "arm64"}, "image_platform_manifest_mismatch"))
        wrong = {"mediaType": "application/vnd.oci.image.manifest.v1+json", "digest": other, "size": 4313,
                 "platform": {"architecture": "amd64", "os": "linux"}}
        cases += [("containerd", "platform", {"Id": other}, "image_platform_manifest_mismatch"),
                  ("containerd", "platform", {"Descriptor": wrong}, "image_platform_manifest_mismatch"),
                  ("containerd", "platform", {"Descriptor": None}, "image_platform_manifest_mismatch"),
                  ("classic", "platform", {"Id": manifest}, "image_configuration_hash_mismatch"),
                  ("classic", "platform", {"Descriptor": dict(wrong, digest=manifest)}, "image_platform_manifest_mismatch")]
        for number, (store, view, change, expected) in enumerate(cases):
            with self.subTest(store=store, view=view, change=change):
                plain, selected = self.image_inspect(pins, store)
                (plain if view == "plain" else selected).update(change)
                error, execute, _ = self.install_with(host, pins, plain, selected, self.result / f"refused-{number}")
                self.assertEqual(error, expected)
                execute.assert_not_called()

    def test_install_actually_uses_narrow_mounts_and_grader_lock(self):
        host = load_recipe_module("host.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        prefix, state = self.result / "prefix", self.result / "state"
        _, execute, _ = self.install_with(host, pins, *self.image_inspect(pins, "containerd"), self.result)
        args = execute.call_args.args[0]
        self.assertNotIn(f"type=bind,src={prefix},dst={prefix}", args)
        self.assertIn(f"type=bind,src={prefix}/venv,dst={prefix}/venv", args)
        self.assertIn("--network=bridge", args)
        script = (RECIPE / "install-grader.sh").read_text()
        for flag in ("--locked", "--no-build-isolation", "--require-hashes", "UV_PYTHON_DOWNLOADS=never"):
            self.assertIn(flag, script)
        self.assertNotIn('make -C "$grader_dir" build', script)
        self.assertRegex(pins["grader"]["uv_lock_sha256"], r"^[a-f0-9]{64}$")

    def test_grader_refuses_unpinned_images_and_does_not_pull_mutable_tags(self):
        module = load_recipe_module("e2e/docker_grader.py")
        collection = SimpleNamespace(client=SimpleNamespace(images=SimpleNamespace(
            get=lambda image: SimpleNamespace(id="sha256:" + "a" * 64))))
        self.assertEqual(module.checked_image(collection, "swebench/example:latest", "sha256:" + "a" * 64),
                         "sha256:" + "a" * 64)
        with self.assertRaises(ValueError):
            module.checked_image(collection, "swebench/example:latest", "sha256:" + "b" * 64)
        with self.assertRaises(ValueError):
            module.checked_image(collection, "swebench/example:latest", None)
        self.assertIn("ImageCollection.pull = forbidden", (RECIPE / "e2e/docker_grader.py").read_text())

    def test_egress_policy_missing_or_wrong_arm_fails_before_model_start(self):
        host = load_recipe_module("host.py")
        with self.assertRaises(ValueError):
            host.model_network({}, "control")
        with self.assertRaises(ValueError):
            host.model_network({"egress": {"control": {"network": "bridge"}}}, "control")

    def test_frozen_grader_digest_is_checked_before_retagging(self):
        host = load_recipe_module("host.py")
        ref = "docker.io/swebench/sweb.eval.x86_64.django_1776_django-11333@sha256:" + "a" * 64
        tag = "swebench/sweb.eval.x86_64.django_1776_django-11333:latest"
        pinfile = self.result / "image.json"
        pinfile.write_text(json.dumps({"instance_id": self.INSTANCE, "ref": ref, "tag": tag,
                                       "source": "frozen registry digest fixture"}))
        environment = {"OPENHANDS_GRADER_IMAGE_FILE": str(pinfile), "OPENHANDS_GRADER_IMAGE_SHA256": host.digest(pinfile)}
        info = [{"Id": "sha256:" + "b" * 64, "RepoDigests": [ref], "Architecture": "amd64", "Os": "linux"}]
        with patch.dict(os.environ, environment), patch.object(host.subprocess, "check_output", return_value=json.dumps(info)), \
                patch.object(host.subprocess, "run") as run:
            selected = host.prepare_grader_image(self.result, self.INSTANCE)
        self.assertEqual(selected["image_id"], info[0]["Id"])
        self.assertEqual(run.call_args.args[0][-3:], ["tag", ref, tag])
        with patch.dict(os.environ, environment), patch.object(host.subprocess, "check_output", return_value='[]'), \
                patch.object(host.subprocess, "run") as run, self.assertRaises(ValueError):
            host.prepare_grader_image(self.result, self.INSTANCE)
        run.assert_not_called()

    def test_mount_roots_match_selected_adoption_layout(self):
        host = load_recipe_module("host.py")
        roots = host.selected_mcp_roots(Path("/ecosystem"))
        self.assertIn(Path("/ecosystem/tools/node-24.21.0"), roots)
        self.assertIn(Path("/ecosystem/python-tools/serena"), roots)
        self.assertNotIn(Path("/ecosystem"), roots)

    def test_shell_entrypoints_forward_stable_dispatch_flags(self):
        self.assertIn('"$@"', (RECIPE / "run-e2e.sh").read_text())
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", (RECIPE / "install.sh").read_text())
        self.assertIn("locked grader", (RECIPE / "install.sh").read_text())


class OpenHandsReceiptTests(unittest.TestCase):
    def test_entry_gateway_usage_and_effort_are_counted_once_without_ids(self):
        module = load_recipe_module("receipt.py")
        helpers = load_recipe_module("recipe.py")
        self.assertEqual(module.gateway_database("engines-on"),
                         Path.home() / ".local/share/omniroute-fw/storage.sqlite")
        rows = [dict(timestamp="2026-09-27T18:00:01Z", path="/v1/responses", status=200,
                     model="gpt-6-astra-max", tokens_in=30, tokens_cache_read=20,
                     tokens_reasoning=4, reasoning_effort_requested="max",
                     reasoning_effort_upstream="max", correlation_id="private-id"),
                dict(timestamp="2026-09-27T18:00:02Z", path="/v1/responses", status=200,
                     model="gpt-6-astra-max", tokens_in=10, tokens_cache_read=0,
                     tokens_reasoning=0, reasoning_effort_requested=None,
                     reasoning_effort_upstream=None, correlation_id="another-private-id")]
        for arm in ("control", "engines-on"):
            selection = helpers.arm_config(arm)
            summary = module.summarize_gateway(rows, selection)
            self.assertEqual(summary["totals"], {"tokens_in": 40, "tokens_cache_read": 20, "tokens_reasoning": 4})
            self.assertEqual(summary["reasoning_rows"], 1)
            self.assertEqual(summary["no_returned_reasoning_rows"], 1)
            self.assertTrue(summary["effort_verified"])
            self.assertNotIn("private-id", json.dumps(summary))
            rows[0]["tokens_in"] = None
            self.assertIsNone(module.summarize_gateway(rows, selection)["totals"])
            rows[0]["tokens_in"] = 30
            rows[0]["reasoning_effort_upstream"] = "high"
            self.assertFalse(module.summarize_gateway(rows, selection)["effort_verified"])
            rows[0]["reasoning_effort_upstream"] = "max"
        self.assertIsNone(module.summarize_gateway([], selection)["totals"])

    def test_worker_evidence_cannot_complete_receipt_and_symlinks_are_rejected(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "target").write_text("sensitive")
            (root / "link").symlink_to(root / "target")
            with self.assertRaises((ValueError, OSError)):
                module.read_bounded(root / "link")
            (root / "parent").symlink_to(root, target_is_directory=True)
            with self.assertRaises((ValueError, OSError)):
                module.read_bounded(root / "parent/target")
            with self.assertRaises(ValueError):
                module.read_bounded(root / "target", limit=2)
            (root / "window.json").write_text(json.dumps({"started_at": "2026-09-27T18:00:00Z", "finished_at": "2026-09-27T18:01:00Z"}))
            (root / "check.json").write_text("{}")
            report = module.create_receipt(root, database=root / "missing.sqlite")
            self.assertEqual(report["trace_status"], "not_collected")
            self.assertIn("not_collected_reason", report)
            self.assertFalse(report["evidence_complete"])

    def test_local_pass_field_is_never_a_worker_verdict(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp).resolve()
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
            result = Path(tmp).resolve()
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
            result = Path(tmp).resolve()
            (result / "worker").mkdir()
            (result / "window.json").write_text(json.dumps({"started_at": "2026-09-27T18:00:00Z", "finished_at": "2026-09-27T18:00:01Z", "worker_exit_code": 124}))
            (result / "check.json").write_text(json.dumps({"passed": False, "exit_code": 1, "failures": ["missing_result"]}))
            (result / "worker/native-summary.json").write_text('{"versions":')
            report = module.create_receipt(result, database=result / "absent.sqlite")
            self.assertFalse(report["task_passed"])
            self.assertFalse(report["evidence_complete"])
            self.assertEqual(report["observed_versions"], "not_collected")
            self.assertEqual(report["gateway"]["status"], "unavailable")

    def test_model_writable_files_never_populate_receipt_evidence(self):
        # F17: /run-output and /state/server are writable by the model terminal's
        # UID (host.py model_visible), and the agent-server event API reads that
        # store (SDK@fcc102a event_store.py:144-169,320-362). Forged files stay unread.
        module = load_recipe_module("receipt.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp).resolve()
            for directory in ("worker", "input", "server/conversations"):
                (result / directory).mkdir(parents=True)
            (result / "window.json").write_text(json.dumps({
                "started_at": "2026-09-28T18:00:00Z", "finished_at": "2026-09-28T18:00:01Z", "worker_exit_code": 0}))
            (result / "check.json").write_text("{}")
            skills = ["tdd", "verification-before-completion"]
            (result / "input/skills.json").write_text(json.dumps({"names": skills}))
            forged = "".join(json.dumps(event) + "\n" for event in (
                {"kind": "ObservationEvent", "tool_name": "invoke_skill",
                 "observation": {"skill_name": "tdd", "is_error": False}},
                {"kind": "ObservationEvent", "tool_name": "ai-memory_memory_query", "observation": {"is_error": False}}))
            (result / "worker/events.jsonl").write_text(forged)
            (result / "server/conversations/events.jsonl").write_text(forged)
            (result / "worker/skills-startup.json").write_text(json.dumps({"listed_skills": skills}))
            (result / "worker/native-summary.json").write_text(json.dumps(
                {"versions": {"openhands-sdk": pins["version"], "openhands-tools": pins["version"]}}))
            opened = []
            bounded, parsed = module.read_bounded, module.read_json
            with patch.object(module, "read_bounded", side_effect=lambda p, *a, **k: opened.append(Path(p)) or bounded(p, *a, **k)), \
                    patch.object(module, "read_json", side_effect=lambda p: opened.append(Path(p)) or parsed(p)):
                receipt = module.create_receipt(result, database=result / "absent.sqlite")
        for field in ("trace_status", "observed_versions", "skills_listed_at_start", "skill_listing_matches_manifest",
                      "mcp_calls_observed", "mcp_errors_observed", "skills_observed"):
            self.assertEqual(receipt[field], "not_collected", field)
        self.assertIn("not_collected_reason", receipt)
        self.assertFalse(receipt["evidence_complete"])
        self.assertEqual([p for p in opened if p.is_relative_to(result / "worker") or p.is_relative_to(result / "server")], [])

    def test_cleanup_timeout_does_not_erase_primary_exit(self):
        host = load_recipe_module("host.py")
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp).resolve() / "worker.log"
            effects = [subprocess.CompletedProcess(["synthetic"], 7), subprocess.TimeoutExpired(["synthetic-cleanup"], 30)]
            with patch.object(host.subprocess, "run", side_effect=effects):
                self.assertEqual(host.execute_container(["synthetic"], "fixture", log, 1), 7)
            cleanup = json.loads(log.with_suffix(".log.cleanup.json").read_text())
            self.assertFalse(cleanup["confirmed_removed"])

    def test_gateway_reads_only_authorized_columns_and_preserves_unknown_usage(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp).resolve() / "fixture.sqlite"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE call_logs (timestamp, path, status, model, reasoning_effort_requested, reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, correlation_id, forbidden_prompt)")
            connection.execute("CREATE TABLE forbidden_credentials (secret)")
            row = ("2026-09-27T18:00:01Z", "/v1/responses", 200, "cx/gpt-6-astra-max", "max", "max", 30, 20, None, "private-id", "private")
            connection.execute("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
            connection.commit()
            connection.close()
            before = db.read_bytes()
            rows = module.gateway_rows(db, "2026-09-27T18:00:00Z", "2026-09-27T18:00:02Z")
            self.assertEqual(db.read_bytes(), before)
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]), set(module.COLUMNS) - {"correlation_id"})
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


class OpenHandsDispatchTests(unittest.TestCase):
    """Synthetic native REST transport, not an agent-server/model execution."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name).resolve()
        self.run_id = "rw-openhands-fixture"
        self.arm = "engines-on"
        self.result = self.state / "runs" / self.run_id / self.arm
        self.result.mkdir(parents=True)

    def test_start_wait_result_use_native_routes_and_deterministic_host_files(self):
        dispatch = load_recipe_module("dispatch.py")
        (self.result / "status.json").write_text(json.dumps({"status": "prepared", "server_name": "rw-openhands-fixture-engines-on-server"}))
        (self.result / "window.json").write_text(json.dumps({"arm": self.arm, "run_id": self.run_id}))
        (self.result / "start.json").write_text("{}")
        replies = [{"id": FIXTURE_CONVERSATION_ID}, {"execution_status": "finished"}, {"response": "Done"}]
        output = io.StringIO()
        with patch.object(dispatch, "api_request", side_effect=replies) as api, \
                patch.object(dispatch, "compression_snapshot", return_value={"totalRequests": 5, "totalTokensSaved": 12}), \
                patch.object(dispatch, "finish_result", return_value={"task_passed": True, "evidence_complete": False, "failure_stage": None}), \
                contextlib.redirect_stdout(output):
            self.assertEqual(dispatch.execute("start", self.state, self.run_id, self.arm), 0)
            self.assertEqual(dispatch.execute("wait", self.state, self.run_id, self.arm), 0)
            self.assertEqual(dispatch.execute("result", self.state, self.run_id, self.arm), 2)
        routes = [call.args[:2] for call in api.call_args_list]
        self.assertEqual(routes, [("POST", "/api/conversations"),
                                 ("GET", f"/api/conversations/{FIXTURE_CONVERSATION_ID}"),
                                 ("GET", f"/api/conversations/{FIXTURE_CONVERSATION_ID}/agent_final_response")])
        for row in output.getvalue().splitlines():
            self.assertEqual(json.loads(row)["receipt"], str(self.result / "receipt.json"))
        self.assertEqual(json.loads((self.result / "status.json").read_text())["status"], "collected")
        self.assertNotIn(FIXTURE_CONVERSATION_ID, (self.result / "receipt.json").read_text())

    def test_wait_deadline_interrupts_and_emits_setup_failure(self):
        dispatch = load_recipe_module("dispatch.py")
        (self.result / "status.json").write_text(json.dumps({"status": "running", "conversation_id": FIXTURE_CONVERSATION_ID, "deadline": 0}))
        (self.result / "window.json").write_text(json.dumps({"arm": self.arm, "run_id": self.run_id}))
        with patch.object(dispatch, "api_request", return_value={}) as api, \
                patch.object(dispatch, "stop_server"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.execute("wait", self.state, self.run_id, self.arm), 3)
        self.assertEqual(api.call_args.args[:2], ("POST", f"/api/conversations/{FIXTURE_CONVERSATION_ID}/interrupt"))
        self.assertEqual(json.loads((self.result / "receipt.json").read_text())["failure_stage"], "deadline")

    def test_server_preserves_native_entrypoint_and_uses_supported_preload(self):
        dispatch = load_recipe_module("dispatch.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        args = dispatch.server_command(pins, "rw-openhands-fixture-server", [],
                                       "rw-openhands-egress-control", "/private/server.env")
        self.assertNotIn("--entrypoint", args)
        self.assertIn("127.0.0.1:3730:8000", args)
        self.assertEqual(args[-4:], ["--extra-python-path", "/recipe", "--import-modules", "server_transport"])
        self.assertIn("--env-file", args)

    def test_compression_delta_is_separate_and_missing_or_reset_is_unknown(self):
        dispatch = load_recipe_module("dispatch.py")
        before = {"totalRequests": 3, "totalTokensSaved": 10}
        after = {"totalRequests": 5, "totalTokensSaved": 25}
        self.assertEqual(dispatch.compression_delta(before, after)["delta"], {"totalRequests": 2, "totalTokensSaved": 15})
        self.assertIsNone(dispatch.compression_delta(None, after)["delta"])
        self.assertIsNone(dispatch.compression_delta(after, before)["delta"])

    def test_prepare_serializes_body_offline_then_launches_native_server(self):
        host = load_recipe_module("host.py")
        dispatch = load_recipe_module("dispatch.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        (self.result / "worker").mkdir()
        selection = load_recipe_module("recipe.py").arm_config("engines-on")
        calls = []

        def rendered(args, name, log, timeout):
            calls.append(args)
            (self.result / "worker/start.json").write_text(json.dumps({"agent": {"llm": {}}, "workspace": {}, "initial_message": {}}))
            return 0

        with patch.dict(sys.modules, {"dispatch": dispatch}), \
                patch.object(host, "execute_container", side_effect=rendered), \
                patch.object(host, "logged_command", return_value=0) as launch, \
                patch.object(dispatch, "private_file", side_effect=lambda x: Path(x)), \
                patch.object(dispatch, "check_server", return_value=None), \
                patch.dict(os.environ, {"OPENHANDS_SERVER_ENV": "/private/server.env", "OPENHANDS_HEADERS": "/private/headers"}):
            host.prepare_native_dispatch(self.result, self.state / "prefix", pins, [],
                                         "rw-openhands-egress-engines-on", {"variables": {"HOST_PATH": "/usr/bin"}},
                                         selection, self.run_id)
        self.assertIn("--network=none", calls[0])
        self.assertIn("OPENHANDS_ARM=engines-on", calls[0])
        self.assertEqual(calls[0][-1], "--request")
        launched = launch.call_args.args[0]
        self.assertNotIn("--entrypoint", launched)
        self.assertTrue((self.result / "start.json").exists())
        self.assertEqual(json.loads((self.result / "status.json").read_text())["status"], "prepared")

    def test_model_mount_permissions_do_not_follow_symlinks(self):
        host = load_recipe_module("host.py")
        workspace = self.result / "workspace"
        workspace.mkdir(mode=0o700)
        (workspace / "owned").write_text("fixture")
        private = self.result / "private"
        private.write_text("private fixture")
        private.chmod(0o600)
        (workspace / "link").symlink_to(private)
        host.model_visible(workspace, writable=True)
        self.assertEqual(workspace.stat().st_mode & 0o777, 0o777)
        self.assertEqual((workspace / "owned").stat().st_mode & 0o777, 0o666)
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)

    def test_preload_installs_dynamic_call_adapter_through_upstream_hook(self):
        from unittest.mock import MagicMock
        context = MagicMock()
        factory = MagicMock(return_value=context)
        modules = {"openhands.sdk": SimpleNamespace(LLM="native-llm"),
                   "worker": SimpleNamespace(gateway_transport=factory, capture_correlation="callback")}
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {"OPENHANDS_OWNED_CONTAINER": "1"}), \
                patch("atexit.register") as register:
            load_recipe_module("server_transport.py")
        factory.assert_called_once_with("native-llm", correlation_callback="callback")
        context.__enter__.assert_called_once()
        register.assert_called_once()

    def test_duplicate_start_keeps_running_status_and_serial_lock(self):
        dispatch = load_recipe_module("dispatch.py")
        original = {"status": "running", "conversation_id": FIXTURE_CONVERSATION_ID}
        (self.result / "status.json").write_text(json.dumps(original))
        (self.result / "window.json").write_text(json.dumps({"arm": self.arm, "run_id": self.run_id}))
        lock = self.state / "active-dispatch.json"
        lock.write_text(json.dumps({"arm": self.arm, "run_id": self.run_id}))
        with patch.object(dispatch, "api_request") as api, patch.object(dispatch, "stop_server") as stop, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.execute("start", self.state, self.run_id, self.arm), 3)
        api.assert_not_called()
        stop.assert_not_called()
        self.assertTrue(lock.exists())
        self.assertEqual(json.loads((self.result / "status.json").read_text()), original)

    def test_result_retry_preserves_collected_official_receipt(self):
        # Native result retrieval is a GET (SDK@fcc102a conversation_router.py:
        # 202-228). Retrying the host collection must not erase its verdict.
        dispatch = load_recipe_module("dispatch.py")
        (self.result / "status.json").write_text(json.dumps({"status": "collected"}))
        (self.result / "window.json").write_text(json.dumps({"arm": self.arm, "run_id": self.run_id}))
        receipt = {"task_passed": True, "evidence_complete": False, "failure_stage": None,
                   "upstream_grader": {"upstream_resolved": True, "grader_exit_code": 0}}
        (self.result / "receipt.json").write_text(json.dumps(receipt))
        output = io.StringIO()
        with patch.object(dispatch, "api_request") as api, patch.object(dispatch, "finish_result") as finish, \
                patch.object(dispatch, "stop_server") as stop, contextlib.redirect_stdout(output):
            self.assertEqual(dispatch.execute("result", self.state, self.run_id, self.arm), 2)
        api.assert_not_called()
        finish.assert_not_called()
        stop.assert_not_called()
        self.assertEqual(json.loads((self.result / "receipt.json").read_text()), receipt)
        self.assertTrue(json.loads(output.getvalue())["task_passed"])

    def test_result_refuses_export_until_container_removal_is_confirmed(self):
        dispatch = load_recipe_module("dispatch.py")
        window = {"arm": self.arm, "run_id": self.run_id, "started_at": "2026-09-27T18:00:00Z", "finished_at": "2026-09-27T18:00:01Z"}
        with patch.object(dispatch, "stop_server", return_value=False), \
                patch.object(dispatch, "logged_command") as command, patch.object(dispatch, "grade") as grade, \
                patch.object(dispatch, "create_receipt", side_effect=lambda result: json.loads((result / "window.json").read_text())):
            report = dispatch.finish_result(self.result, {"execution_status": "finished"}, window)
        command.assert_not_called()
        grade.assert_not_called()
        self.assertEqual(report["failure_stage"], "export")

    def test_request_serialization_failure_cannot_leave_prepared_receipt(self):
        host = load_recipe_module("host.py")
        dispatch = load_recipe_module("dispatch.py")
        with patch.dict(sys.modules, {"dispatch": dispatch}), \
                patch.object(dispatch, "private_file", side_effect=lambda x: Path(x)), \
                patch.dict(os.environ, {"OPENHANDS_SERVER_ENV": "/private/server.env", "OPENHANDS_HEADERS": "/private/headers"}), \
                patch.object(host, "execute_container", return_value=7), \
                patch.object(host, "logged_command") as launch, self.assertRaises(RuntimeError):
            host.prepare_native_dispatch(self.result, self.state / "prefix", json.loads((RECIPE / "pins.json").read_text()), [],
                                         "rw-openhands-egress-engines-on", {"variables": {"HOST_PATH": "/usr/bin"}},
                                         load_recipe_module("recipe.py").arm_config(self.arm), self.run_id)
        launch.assert_not_called()

    def test_patch_export_cannot_use_host_git_filters_or_external_diff(self):
        dispatch = load_recipe_module("dispatch.py")
        (self.result / "task-identity.json").write_text(json.dumps({"instance_id": "django__django-11333", "base_commit": "a" * 40}))
        (self.result / "dataset.json").write_text("[]")
        window = {"arm": self.arm, "run_id": self.run_id}
        with patch.object(dispatch, "stop_server", return_value=True), \
                patch.object(dispatch, "logged_command", return_value=0) as command, \
                patch.object(dispatch.subprocess, "check_output", return_value="patch") as diff, \
                patch.object(dispatch, "grade", return_value={}), patch.object(dispatch, "create_receipt", return_value={}):
            dispatch.finish_result(self.result, {"execution_status": "finished"}, window)
        self.assertEqual(command.call_args.kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(command.call_args.kwargs["env"]["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertIn("--no-ext-diff", diff.call_args.args[0])
        self.assertIn("--no-textconv", diff.call_args.args[0])

    # SDK@fcc102a local_conversation.py:2021-2043,2339-2360 emit this event;
    # utils/models.py:202-205 serializes kind as the class name.
    LIMIT_EVENT = {"kind": "ConversationErrorEvent", "source": "environment", "code": "MaxIterationsReached",
                   "detail": "Agent reached maximum iterations limit (40)."}
    ERROR_SEARCH = ("/events/search?kind=openhands.sdk.event.conversation_error.ConversationErrorEvent"
                    "&sort_order=TIMESTAMP_DESC&limit=1")

    def terminal_attempt(self, execution):
        (self.result / "status.json").write_text(json.dumps({
            "status": "terminal", "execution_status": execution, "conversation_id": FIXTURE_CONVERSATION_ID,
            "server_name": "rw-openhands-fixture-engines-on-server"}))
        (self.result / "window.json").write_text(json.dumps({
            "arm": self.arm, "run_id": self.run_id, "instance_id": "django__django-11333",
            "started_at": "2026-09-28T18:00:00Z", "finished_at": "2026-09-28T18:00:01Z"}))
        (self.result / "task-identity.json").write_text(json.dumps({"instance_id": "django__django-11333", "base_commit": "a" * 40}))
        (self.result / "dataset.json").write_text("[]")

    @staticmethod
    def synthetic_report(bucket):
        """Writes a SWE-bench 4.1.0 schema-2 report fixture; no grader runs."""
        def grade(prefix, result, dataset, instance_id, run_id):
            report = {key: [] for key in ("resolved_ids", "unresolved_ids", "error_ids", "empty_patch_ids", "incomplete_ids")}
            report.update({"schema_version": 2, "submitted_ids": [instance_id], bucket: [instance_id]})
            (result / ("OpenHands." + run_id + ".json")).write_text(json.dumps(report))
            return {"upstream_resolved": bucket == "resolved_ids", "grader_exit_code": 0, "conversion_exit_code": 0}
        return grade

    def collect(self, dispatch, replies, grader=None):
        receipts = load_recipe_module("receipt.py")
        with patch.object(dispatch, "api_request", side_effect=replies) as api, \
                patch.object(dispatch, "stop_server", return_value=True), \
                patch.object(dispatch, "logged_command", return_value=0), \
                patch.object(dispatch.subprocess, "check_output", return_value=""), \
                patch.object(dispatch, "grade", side_effect=grader) as grade, \
                patch.object(dispatch, "create_receipt",
                             side_effect=lambda result: receipts.create_receipt(result, database=result / "absent.sqlite")), \
                contextlib.redirect_stdout(io.StringIO()):
            code = dispatch.execute("result", self.state, self.run_id, self.arm)
        return code, api, grade, json.loads((self.result / "receipt.json").read_text())

    def test_agent_limit_terminations_grade_the_partial_patch_and_exit_1(self):
        # F16. SDK@fcc102a conversation/state.py:48-79 terminal statuses;
        # local_conversation.py:753-755 sets STUCK; :2021-2043 and :2339-2360
        # set ERROR plus ConversationErrorEvent code "MaxIterationsReached".
        dispatch = load_recipe_module("dispatch.py")
        final, limit = {"response": ""}, {"items": [self.LIMIT_EVENT], "next_page_id": None}
        for execution, replies, bucket, termination in (
                ("stuck", [final], "unresolved_ids", "stuck"),
                ("error", [final, limit], "empty_patch_ids", "max_iterations_reached"),
                ("error", [final, limit], "resolved_ids", "max_iterations_reached")):
            with self.subTest(execution=execution, bucket=bucket):
                self.terminal_attempt(execution)
                code, api, grade, receipt = self.collect(dispatch, replies, self.synthetic_report(bucket))
                self.assertEqual(code, 1)
                grade.assert_called_once()
                self.assertEqual(receipt["agent_termination"], termination)
                self.assertIsNone(receipt["failure_stage"])
                self.assertFalse(receipt["task_passed"])
                self.assertEqual(receipt["upstream_grader"]["upstream_bucket"], bucket)
                self.assertEqual(api.call_count, len(replies))
                if execution == "error":
                    self.assertEqual(api.call_args.args[:2],
                                     ("GET", f"/api/conversations/{FIXTURE_CONVERSATION_ID}{self.ERROR_SEARCH}"))

    def test_other_native_errors_stay_ungraded_infrastructure_failures(self):
        # SDK@fcc102a local_conversation.py:2044-2057 emits LLMAuthenticationError.
        dispatch = load_recipe_module("dispatch.py")
        other = dict(self.LIMIT_EVENT, code="LLMAuthenticationError")
        for page in ({"items": [other], "next_page_id": None}, {"items": [], "next_page_id": None},
                     {"items": [dict(self.LIMIT_EVENT, source="agent")]},
                     {"items": [dict(self.LIMIT_EVENT, kind="MessageEvent")]},
                     {"items": [self.LIMIT_EVENT, self.LIMIT_EVENT]}, [self.LIMIT_EVENT]):
            with self.subTest(page=page):
                self.terminal_attempt("error")
                code, _, grade, receipt = self.collect(dispatch, [{"response": ""}, page])
                self.assertEqual(code, 3)
                grade.assert_not_called()
                self.assertEqual(receipt["failure_stage"], "agent")
                self.assertEqual(receipt["agent_termination"], "error")

    def test_only_the_rest_status_can_admit_a_pass(self):
        # F16 bound. A label derived from the model-writable event store may
        # refine REST "error" into an agent limit (exit 3 -> 1) but can never
        # stand in for REST "finished", even with an officially resolved patch.
        dispatch = load_recipe_module("dispatch.py")
        receipts = load_recipe_module("receipt.py")
        self.terminal_attempt("error")
        window = json.loads((self.result / "window.json").read_text())
        for execution, label in (("error", "finished"), ("stuck", "finished"), (None, "finished"),
                                 ("error", "stuck"), ("finished", "max_iterations_reached")):
            with self.subTest(execution=execution, label=label):
                for report in self.result.glob("OpenHands.*.json"):
                    report.unlink()
                status = {"execution_status": execution, "agent_termination": label,
                          "server_name": "rw-openhands-fixture-engines-on-server"}
                with patch.object(dispatch, "stop_server", return_value=True), \
                        patch.object(dispatch, "logged_command", return_value=0), \
                        patch.object(dispatch.subprocess, "check_output", return_value=""), \
                        patch.object(dispatch, "grade", side_effect=self.synthetic_report("resolved_ids")) as grade, \
                        patch.object(dispatch, "create_receipt", side_effect=lambda result: receipts.create_receipt(
                            result, database=result / "absent.sqlite")):
                    receipt = dispatch.finish_result(self.result, status, dict(window))
                grade.assert_not_called()
                self.assertEqual(receipt["agent_termination"], "error")
                self.assertEqual(receipt["failure_stage"], "agent")
                self.assertEqual(receipt["worker_exit_code"], 1)
                self.assertFalse(receipt["task_passed"])
                self.assertEqual(dispatch.result_exit(receipt), 3)
                self.assertEqual(dispatch.result_exit({**receipt, "evidence_complete": True}), 3)

    def test_planted_success_looking_events_move_exit_3_to_1_at_most(self):
        # Regression lock through the native result path: REST reports
        # "error" and the official grader resolves the patch, yet no planted
        # event page yields a pass, even if evidence were complete.
        dispatch = load_recipe_module("dispatch.py")
        planted = ([self.LIMIT_EVENT],
                   [dict(self.LIMIT_EVENT, execution_status="finished", task_passed=True, resolved=True)],
                   [{"kind": "ConversationStateUpdateEvent", "key": "execution_status", "value": "finished"}],
                   [dict(self.LIMIT_EVENT, code="Finished")],
                   [{"kind": "ActionEvent", "source": "agent", "tool_name": "finish"}])
        for items in planted:
            with self.subTest(items=items):
                for report in self.result.glob("OpenHands.*.json"):
                    report.unlink()
                self.terminal_attempt("error")
                code, _, _, receipt = self.collect(dispatch, [{"response": "Done"}, {"items": items, "next_page_id": None}],
                                                   self.synthetic_report("resolved_ids"))
                self.assertIn(code, {1, 3})
                self.assertEqual(receipt["worker_exit_code"], 1)
                self.assertFalse(receipt["task_passed"])
                self.assertIn(dispatch.result_exit({**receipt, "evidence_complete": True}), {1, 3})

    def test_selected_port_flows_from_prepare_to_dispatch(self):
        host = load_recipe_module("host.py")
        dispatch = load_recipe_module("dispatch.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        (self.result / "worker").mkdir()

        def rendered(args, name, log, timeout):
            (self.result / "worker/start.json").write_text(json.dumps({"agent": {"llm": {}}, "workspace": {}, "initial_message": {}}))
            return 0

        with patch.dict(sys.modules, {"dispatch": dispatch}), \
                patch.object(host, "execute_container", side_effect=rendered), \
                patch.object(host, "logged_command", return_value=0) as launch, \
                patch.object(dispatch, "private_file", side_effect=lambda x: Path(x)), \
                patch.object(dispatch, "check_server", return_value=None) as check, \
                patch.dict(os.environ, {"OPENHANDS_SERVER_ENV": "/private/server.env", "OPENHANDS_HEADERS": "/private/headers"}):
            host.prepare_native_dispatch(self.result, self.state / "prefix", pins, [], "rw-openhands-egress-engines-on",
                                         {"variables": {"HOST_PATH": "/usr/bin"}},
                                         load_recipe_module("recipe.py").arm_config(self.arm), self.run_id, port=3740)
        self.assertIn("127.0.0.1:3740:8000", launch.call_args.args[0])
        self.assertNotIn("127.0.0.1:3730:8000", launch.call_args.args[0])
        self.assertEqual(check.call_args.kwargs["port"], 3740)
        self.assertEqual(json.loads((self.result / "status.json").read_text())["port"], 3740)
        (self.result / "window.json").write_text(json.dumps({"arm": self.arm, "run_id": self.run_id}))
        with patch.object(dispatch, "api_request", return_value={"id": FIXTURE_CONVERSATION_ID}) as api, \
                patch.object(dispatch, "compression_snapshot", return_value=None), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.execute("start", self.state, self.run_id, self.arm), 0)
        self.assertEqual(api.call_args.kwargs["port"], 3740)
        status = json.loads((self.result / "status.json").read_text())
        (self.result / "status.json").write_text(json.dumps({**status, "port": 8000}))
        with patch.object(dispatch, "api_request") as api, patch.object(dispatch, "stop_server"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.execute("wait", self.state, self.run_id, self.arm), 3)
        api.assert_not_called()
        args = dispatch.server_command(pins, "rw-openhands-fixture-server", [], "rw-openhands-egress-control",
                                       "/private/server.env")
        self.assertIn("127.0.0.1:3730:8000", args)


if __name__ == "__main__":
    unittest.main()
