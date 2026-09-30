"""Offline recipe contract, frozen before the recipe exists.

References: OpenHands/software-agent-sdk v1.49.6 examples
01_standalone_sdk/{01_hello_world,07_mcp_integration,14_context_condenser}.py;
the user's 2026-09-27 runtime-worker acceptance contract. These are local
structural/fixture checks, not upstream SDK or live gateway acceptance.
"""

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
import errno
import hashlib
import http.server
import io
import json
import os
import importlib.util
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
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


# Plan G5 (repair R3) fixtures. OmniRoute@045aa81f3 and @dd6e9607e (identical
# files): providers served with a synthetic credential and no
# provider_connections row, src/shared/constants/providers/noauth.ts (noAuth)
# and apikey/gateways.ts:741,756, apikey/specialty-media.ts:56, oauth.ts:243
# (anonymousFallback).
NO_AUTH_PROVIDERS = {"devin-cli-agentic": "dva", "opencode": "oc", "duckduckgo-web": "ddgw",
                     "cloudflare-playground": "cfp", "veoaifree-web": "veo-free", "auggie": "aug", "zcode": "zc",
                     "codex-app-server": "cxa", "uncloseai": "unc", "aihorde": "horde"}
ANONYMOUS_FALLBACK_PROVIDERS = {"opencode-zen": "opencode-zen", "opencode-go": "opencode-go",
                                "pollinations": "pol", "kilocode": "kc"}
GATEWAY_SECRETS = ("SECRET-ACCESS", "SECRET-REFRESH", "SECRET-API-KEY", "SECRET-ID-TOKEN", "SECRET-PSD",
                   "SECRET-OIDC", "SECRET-COMBO")
ENGINES_NODE = "openai-compatible-responses-" + str(uuid.UUID(int=7))


def gateway_store(path, providers, *, combos=0, blocked=tuple(NO_AUTH_PROVIDERS),
                  fallback=tuple(ANONYMOUS_FALLBACK_PROVIDERS), settings=None, tables=None):
    """A fixture OmniRoute storage.sqlite (src/lib/db/core.ts schema subset), with credential columns filled."""
    connection = sqlite3.connect(path)
    try:
        connection.executescript(tables or """
            CREATE TABLE provider_connections (id TEXT PRIMARY KEY, provider TEXT NOT NULL, auth_type TEXT,
              access_token TEXT, refresh_token TEXT, api_key TEXT, id_token TEXT, provider_specific_data TEXT,
              is_active INTEGER);
            CREATE TABLE key_value (namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
              PRIMARY KEY (namespace, key));
            CREATE TABLE combos (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, data TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        """)
        for number, provider in enumerate(providers):
            connection.execute("INSERT INTO provider_connections VALUES (?, ?, 'oauth', 'SECRET-ACCESS', "
                               "'SECRET-REFRESH', 'SECRET-API-KEY', 'SECRET-ID-TOKEN', '{\"t\":\"SECRET-PSD\"}', 1)",
                               (f"connection-{number}", provider))
        for number in range(combos):
            connection.execute("INSERT INTO combos VALUES (?, ?, '{\"models\":[\"SECRET-COMBO\"]}', 0, 't', 't')",
                               (f"combo-{number}", f"combo-{number}"))
        values = {"oidcClientSecret": json.dumps("SECRET-OIDC")}
        if blocked is not None:
            values["blockedProviders"] = json.dumps(list(blocked))
        if fallback is not None:
            values["noAuthFallbackDisabledProviders"] = json.dumps(list(fallback))
        values.update(settings or {})
        for key, value in values.items():
            connection.execute("INSERT INTO key_value VALUES ('settings', ?, ?)", (key, value))
        connection.commit()
    finally:
        connection.close()
    return path


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
        # Phase 2 (F21 refresh): both arms call the proxy alias, whose upstream
        # port selects the arm. The 20129 apply record read back at
        # 2026-09-28T03:50:11Z has seven header-selected combos and all twelve
        # engines globally off; default-caveman is outside that set.
        helpers = load_recipe_module("recipe.py")
        cfg = self.read_json("config/worker.json")
        self.assertEqual(helpers.COMPRESSION_COMBOS, frozenset({
            "allow-lossy", "fw-ccr", "fw-codex-responses", "fw-headroom", "fw-lite", "fw-rtk", "fw-session-dedup"}))
        for arm, model, port, headers in (
            ("control", "cx/gpt-6-astra-max", 20128, {}),
            ("engines-on", "sharedgw/gpt-6-astra-max", 20129,
             {"x-omniroute-compression": "allow-lossy"}),
        ):
            with self.subTest(arm=arm):
                selected = helpers.arm_config(arm)
                self.assertEqual(selected["requested_model"], model)
                self.assertEqual(selected["base_url"], "http://gw:8081/v1")
                self.assertEqual(selected["gateway_port"], port)
                self.assertEqual(selected["gateway_upstream"], f"http://10.0.2.2:{port}/v1")
                self.assertEqual(selected["headers"], headers)
                llm = helpers.llm_config(cfg, arm=arm)
                self.assertEqual(llm["model"], "openai/" + model)
                self.assertEqual(llm["base_url"], "http://gw:8081/v1")
                self.assertEqual(llm["api_key"], "local-loopback")
                self.assertEqual(llm["reasoning_effort"], "max")
                self.assertEqual(llm["extra_headers"], headers)
        for combo in sorted(helpers.COMPRESSION_COMBOS):
            with self.subTest(combo=combo):
                selected = helpers.arm_config("engines-on", compression=combo)
                self.assertEqual(selected["compression_combo"], combo)
                self.assertEqual(selected["headers"], {"x-omniroute-compression": combo})
        self.assertIsNone(helpers.arm_config("control")["compression_combo"])
        for kwargs in (
            {"arm": "engines-on", "model": "sharedgw/cx/gpt-6-astra-max"},
            {"arm": "engines-on", "model": "sharedgw/claude-opus-5-5"},
            {"arm": "control", "model": "sharedgw/gpt-6-astra-max"},
            {"arm": "engines-on", "base_url": "http://10.0.2.2:20129/v1"},
            {"arm": "control", "base_url": "http://10.0.2.2:20128/v1"},
            {"arm": "control", "base_url": "https://example.invalid/v1"},
            {"arm": "control", "compression": "allow-lossy"},
            {"arm": "engines-on", "compression": "default-caveman"},
            {"arm": "engines-on", "compression": ""},
            {"arm": "engines-on", "compression": "ALLOW-LOSSY"},
            {"arm": "other"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                helpers.llm_config(cfg, **kwargs)
        cfg["llm"]["reasoning_effort"] = "high"
        with self.assertRaises(ValueError):
            helpers.llm_config(cfg)

    def test_gateway_model_and_container_topology(self):
        config = self.read_json("config/worker.json")
        self.assertEqual(config["llm"]["base_url"], "http://gw:8081/v1")
        self.assertEqual(config["llm"]["model"], "cx/gpt-6-astra-max")
        self.assertEqual(config["model_env"], "OPENHANDS_MODEL")
        self.assertEqual(config["llm"]["api_key"], "local-loopback")
        self.assertEqual(config["llm"]["api_mode"], "responses")
        self.assertIsNone(config["llm"].get("temperature"))
        self.assertNotEqual(config["llm"].get("reasoning_effort"), "auto")
        self.assertEqual(config["runtime"]["gateway_base_url"], "http://gw:8081/v1")
        self.assertEqual(config["runtime"]["agent_loop"], "container")
        # Only the proxy publishes, on loopback, to its host-driver server.
        self.assertEqual(config["runtime"]["published_ports"], ["127.0.0.1:3730:8080"])
        self.assertEqual(config["arm_env"], "OPENHANDS_ARM")
        self.assertEqual(config["compression_env"], "OPENHANDS_COMPRESSION")
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
        # Phase 2 (O1): host services have no route from the internal run
        # network, so both remote servers are documented as unreachable by
        # design; no proxy route is added for them.
        for name in ("ai-memory", "socraticode"):
            with self.subTest(server=name):
                self.assertIs(policy[name]["enabled"], False)
                self.assertIn("unreachable by design", policy[name]["reason"])
                self.assertIn("internal run network", policy[name]["reason"])

    def test_environment_selection_maps_empty_compression_to_unset(self):
        # One helper serves host.run and the container worker, so both sides
        # read OPENHANDS_COMPRESSION the same way ("" means unset).
        helpers = load_recipe_module("recipe.py")
        self.assertIsNone(helpers.environment_selection({"OPENHANDS_COMPRESSION": ""})["compression_combo"])
        self.assertEqual(helpers.environment_selection({}, "engines-on")["compression_combo"], "allow-lossy")
        self.assertEqual(helpers.environment_selection({"OPENHANDS_ARM": "control"}, "engines-on")["arm"], "engines-on")
        selected = helpers.environment_selection({"OPENHANDS_ARM": "engines-on", "OPENHANDS_COMPRESSION": "fw-lite"})
        self.assertEqual((selected["arm"], selected["compression_combo"]), ("engines-on", "fw-lite"))
        self.assertEqual(selected["headers"], {"x-omniroute-compression": "fw-lite"})
        for environment in ({"OPENHANDS_COMPRESSION": "fw-lite"},
                            {"OPENHANDS_ARM": "engines-on", "OPENHANDS_COMPRESSION": "fw-unknown"},
                            {"OPENHANDS_ARM": "engines-on", "OPENHANDS_BASE_URL": "http://10.0.2.2:20129/v1"}):
            with self.subTest(environment=environment), self.assertRaises(ValueError):
                helpers.environment_selection(environment)

    def test_immutable_artifacts(self):
        pins = self.read_json("pins.json")
        self.assertEqual(pins["version"], "1.50.0")
        self.assertRegex(pins["commit"], r"^[0-9a-f]{40}$")
        for name in ("source_archive", "uv_lock"):
            self.assertRegex(pins[name]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(pins["image"]["ref"], r"^ghcr\.io/openhands/agent-server@sha256:[0-9a-f]{64}$")
        # Phase 2: the gateway proxy image is pinned by index digest, with its
        # linux/amd64 manifest and config digests for pinned_image_identity.
        proxy = pins["gateway_proxy"]
        self.assertRegex(proxy["ref"], r"^ghcr\.io/nginx/nginx-unprivileged@sha256:[0-9a-f]{64}$")
        self.assertEqual(proxy["platform"], "linux/amd64")
        for key in ("manifest_sha256", "config_sha256"):
            self.assertRegex(proxy[key], r"^[0-9a-f]{64}$")
            self.assertNotEqual(proxy[key], proxy["ref"].rsplit(":", 1)[1])

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
            self.assertEqual(cfg["base_url"], "http://gw:8081/v1")
        selected = worker.worker_llm_config({"OPENHANDS_ARM": "engines-on", "OPENHANDS_COMPRESSION": "fw-rtk"}, "d")
        self.assertEqual(selected["extra_headers"]["x-omniroute-compression"], "fw-rtk")
        unset = worker.worker_llm_config({"OPENHANDS_ARM": "control", "OPENHANDS_COMPRESSION": ""}, "d")
        self.assertNotIn("x-omniroute-compression", unset["extra_headers"])
        with self.assertRaises(ValueError):
            worker.worker_llm_config({"OPENHANDS_ARM": "control", "OPENHANDS_COMPRESSION": "fw-rtk"}, "d")
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
        self.assertEqual(result["base_url"], "http://gw:8081/v1")
        pattern = re.compile(helpers.tool_filter(self.read_json("config/mcp-policy.json")))
        for name in ("terminal", "file_editor", "context-mode_ctx_execute", "serena_find_symbol", "qmd_query", "jcodemunch_order"):
            self.assertIsNotNone(pattern.fullmatch(name), name)
        # Phase 2 contract change: tools of the unreachable host services are
        # no longer admitted by the native filter either.
        for name in ("context-mode_ctx_upgrade", "context-mode_ctx_purge", "ai-memory_memory_query", "ai-memory_memory_write",
                     "socraticode_codebase_health", "socraticode_codebase_index", "jcodemunch_delete_index",
                     "headroom_headroom_compress", "memory_query", "qmd_query_evil"):
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

    def test_model_container_is_nonroot_and_network_is_per_attempt(self):
        # Plan E1: "none", or one of the attempt's own two networks for exactly
        # the roles that need it. No shared or cross-attempt network is allowed.
        host = load_recipe_module("host.py")
        pins = self.read_json("pins.json")
        args = host.docker_args(pins, "rw-openhands-fixture")
        self.assertEqual(args[args.index("--user") + 1], "10001:10001")
        self.assertIn("--network=none", args)
        self.assertIn("--cap-drop=ALL", args)
        self.assertIn("--security-opt=no-new-privileges", args)
        self.assertIn("HOME=/state/home", args)
        stem = "rw-openhands-fixture-control"
        for name, network in ((stem + "-server", stem + "-int"), (stem + "-probe-int", stem + "-int"),
                              (stem + "-probe-gw", stem + "-gw"), (stem + "-request", "none")):
            with self.subTest(name=name, network=network):
                self.assertIn("--network=" + network, host.docker_args(pins, name, network=network))
        for name, network in (("rw-openhands-agent", "bridge"), (stem + "-server", stem + "-gw"),
                              (stem + "-request", stem + "-int"), (stem + "-qmd", stem + "-gw"),
                              (stem + "-server", "rw-openhands-other-control-int"),
                              ("rw-openhands-other-control-server", stem + "-int"),
                              (stem + "-server", "rw-openhands-egress-control"), (stem + "-server", "host"),
                              (stem + "-server", stem + "-int-x"),
                              ("rw-openhands-fixture-other-server", "rw-openhands-fixture-other-int")):
            with self.subTest(name=name, network=network), self.assertRaises(ValueError):
                host.docker_args(pins, name, network=network)

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

    def test_host_template_has_no_firewall_receipt_contract(self):
        # F19 superseded (plan section 5): containment comes from the
        # per-attempt topology and its probe, not a DOCKER-USER receipt.
        host = self.read_json("config/host.example.json")
        self.assertNotIn("egress", host)
        source = (RECIPE / "host.py").read_text()
        for retired in ("model_network", "docker-user-iptables", "policy_receipt", "rw-openhands-egress-"):
            self.assertNotIn(retired, source)
        # The pointer variables are retired: the driver generates the key files.
        for name in ("host.py", "dispatch.py"):
            text = (RECIPE / name).read_text()
            self.assertNotIn("OPENHANDS_SERVER_ENV", text)
            self.assertNotIn("OPENHANDS_HEADERS", text)

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
        # Historical scan is retained against its original immutable input;
        # it is not acceptance of the new 1.50.0 image.
        all_pins = self.read_json("evidence/pins-1.49.6.json")
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

    def test_proxy_image_evidence_matches_the_pin_and_is_publishable(self):
        # Phase 2: the gateway_proxy pin rests on registry byte hashes, a pull
        # by digest and pinned_image_identity (evidence/phase2-commands.json).
        from scripts.validate import PRIVATE_CONTENT
        pins = self.read_json("pins.json")["gateway_proxy"]
        record = self.read_json("evidence/phase2-commands.json")
        commands = {item["id"]: item for item in record["commands"]}
        self.assertEqual(len(commands), len(record["commands"]))
        registry = commands["15-registry-bytes"]
        index = pins["ref"].rsplit("@", 1)[1]
        self.assertIn(index, registry["command"])
        found = registry["output_excerpt"]
        self.assertEqual((found["top_sha256_of_bytes"], found["top_bytes_match_reference"]), (index, True))
        self.assertEqual((found["amd64_manifest"]["sha256_of_bytes"], found["amd64_manifest"]["bytes_match"]),
                         ("sha256:" + pins["manifest_sha256"], True))
        self.assertEqual((found["config"]["sha256_of_bytes"], found["config"]["bytes_match"], found["config"]["os_arch"]),
                         ("sha256:" + pins["config_sha256"], True, pins["platform"]))
        self.assertIn("gateway_proxy store=containerd", commands["17-pull-and-identity"]["output"])
        self.assertEqual(record["base"], "efa73f40453911d3ac9583218530273677983053")
        text = json.dumps(record, ensure_ascii=False)
        for description, pattern in PRIVATE_CONTENT:
            self.assertIsNone(pattern.search(text), description)
        for document in ("README.md", "research.md"):
            self.assertIn("evidence/phase2-commands.json", (RECIPE / document).read_text())

    def test_repair_round_evidence_pairs_each_red_run_with_a_green_commit(self):
        # The repair round on e45c3cd1: every code item's failing run, then the
        # suite on the commit that fixed it. Our integration checks, publishable.
        from scripts.validate import PRIVATE_CONTENT
        name = "evidence/repair-round-commands.json"
        record = self.read_json(name)
        self.assertEqual(record["base"], "e45c3cd1c274aff47b82129bf8d22ed374bd577b")
        commands = {item["id"]: item for item in record["commands"]}
        self.assertEqual(len(commands), len(record["commands"]))
        self.assertTrue(record["item_runs"])
        for item, (red, green) in record["item_runs"].items():
            with self.subTest(item=item):
                self.assertEqual(commands[red]["exit_code"], 1)
                self.assertTrue(commands[red]["summary"][-1].startswith("FAILED"))
                self.assertTrue(commands[red]["non_ok_tests"])
                self.assertEqual((commands[green]["exit_code"], commands[green]["summary"][-1]), (0, "OK"))
                commit = re.match(r"Commit ([0-9a-f]{40})\b", commands[green]["tree"])
                self.assertIsNotNone(commit)
                self.assertIn(commit.group(1), record["commits"].values())
        text = json.dumps(record, ensure_ascii=False)
        for description, pattern in PRIVATE_CONTENT:
            self.assertIsNone(pattern.search(text), description)
        self.assertIn(name, (RECIPE / "research.md").read_text())
        self.assertIn(name, (ROOT / "docs/decisions/2026-09-28-openhands-resolver-isolation.md").read_text())


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
        # docker-py 7.1.0 models/containers.py:686-694: network_mode "none" is
        # "No networking for this container".
        self.assertEqual(set(changed) - set(original), {"labels", "network_mode"})
        self.assertEqual(changed["network_mode"], "none")
        self.assertEqual(original["name"], "sweb.eval.django__django-11333.attempt")
        self.assertEqual(module.owned_container_options({**original, "network_mode": "none"})["network_mode"], "none")
        for update in ({"ports": {"8000/tcp": 3710}}, {"name": "unowned"}, {"volumes": {"unowned": {}}},
                       {"network_mode": "bridge"}, {"network_mode": "host"}, {"network_mode": "default"},
                       {"network_mode": "container:rw-openhands-other"}, {"network": "bridge"},
                       {"networking_config": {"bridge": {}}}, {"network_disabled": True}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                module.owned_container_options({**original, **update})

    def networked(self, mode, networks):
        removed = []
        container = SimpleNamespace(attrs={"HostConfig": {"NetworkMode": mode},
                                           "NetworkSettings": {"Networks": networks}},
                                    remove=lambda force: removed.append(force))
        return container, removed

    def test_grader_container_is_created_with_network_none_and_inspected(self):
        module = load_recipe_module("e2e/docker_grader.py")
        image_id = "sha256:" + "a" * 64
        collection = SimpleNamespace(client=SimpleNamespace(images=SimpleNamespace(
            get=lambda image: SimpleNamespace(id=image_id))))
        record = self.result / "docker-created.jsonl"
        spec = {"name": "sweb.eval.django__django-11333.attempt", "image": "swebench/example:latest",
                "detach": True, "command": "tail -f /dev/null"}
        created = []
        # moby docker-v29.8.1 daemon/create.go:251 and container_operations.go:363-406:
        # mode "none" is recorded as the single NetworkSettings.Networks entry "none".
        good, removed = self.networked("none", {"none": {"IPAddress": ""}})

        def create(collection, *args, **kwargs):
            created.append(kwargs)
            return good
        self.assertIs(module.owned_create(create, collection, (), spec, image_id, record), good)
        self.assertEqual(created[0]["network_mode"], "none")
        self.assertEqual(created[0]["name"], "rw-openhands-" + spec["name"])
        self.assertEqual(json.loads(record.read_text()), {"name": "rw-openhands-" + spec["name"]})
        self.assertEqual(removed, [])
        # A spec that asks for any network is refused before the Docker call.
        for update in ({"network_mode": "bridge"}, {"network": "rw-openhands-other"}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                module.owned_create(create, collection, (), {**spec, **update}, image_id, record)
        self.assertEqual(len(created), 1)
        # Refuse to grade when the created container's inspect shows another network.
        for mode, networks in (("default", {"bridge": {"IPAddress": "172.17.0.2"}}),
                               ("none", {"none": {}, "bridge": {}}), ("none", {}), ("none", None),
                               ("bridge", {"none": {}})):
            bad, removed = self.networked(mode, networks)
            with self.subTest(mode=mode, networks=networks):
                with self.assertRaisesRegex(ValueError, "grader_container_network_not_none"):
                    module.owned_create(lambda collection, *a, **k: bad, collection, (), spec, image_id, record)
                self.assertEqual(removed, [True])

    def test_grader_sdk_create_body_requires_network_none(self):
        module = load_recipe_module("e2e/docker_grader.py")
        # docker-py 7.1.0 types/containers.py:351 writes NetworkMode (default "default");
        # api/container.py:445-457 posts that body to /containers/create.
        config = {"Image": "swebench/example:latest", "HostConfig": {"NetworkMode": "none"}}
        self.assertIs(module.checked_create_config(config), config)
        for bad in ({"HostConfig": {"NetworkMode": "default"}}, {"HostConfig": {"NetworkMode": "bridge"}},
                    {"HostConfig": {"NetworkMode": "host"}}, {"HostConfig": {}}, {}, None,
                    {"HostConfig": {"NetworkMode": "none"}, "NetworkingConfig": {"EndpointsConfig": {"bridge": {}}}}):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "grader_container_requires_network_none"):
                module.checked_create_config(bad)

    def test_grader_main_installs_the_network_none_transport(self):
        module = load_recipe_module("e2e/docker_grader.py")
        image_id = "sha256:" + "a" * 64
        posted, created = [], []

        class APIClient:
            def create_container_from_config(self, config, name=None, platform=None):
                posted.append(config)
                return {"Id": "fixture"}

            def build(self, *args, **kwargs):
                return "built"

        class ContainerCollection:
            client = SimpleNamespace(images=SimpleNamespace(get=lambda image: SimpleNamespace(id=image_id)))

            def create(self, image, command=None, **kwargs):
                created.append(kwargs)
                return SimpleNamespace(attrs={"HostConfig": {"NetworkMode": kwargs.get("network_mode")},
                                              "NetworkSettings": {"Networks": {"none": {}}}})

        class Other:
            def pull(self, *args, **kwargs):
                return "pulled"

            def create(self, *args, **kwargs):
                return "created"

        modules = {name: SimpleNamespace() for name in (
            "docker", "docker.models", "docker.api", "docker.models.containers", "docker.models.networks",
            "docker.models.volumes", "docker.models.images", "docker.api.client")}
        modules["docker.models.containers"].ContainerCollection = ContainerCollection
        modules["docker.api.client"].APIClient = APIClient
        networks, volumes, images = type("N", (Other,), {}), type("V", (Other,), {}), type("I", (Other,), {})
        modules["docker.models.networks"].NetworkCollection = networks
        modules["docker.models.volumes"].VolumeCollection = volumes
        modules["docker.models.images"].ImageCollection = images
        ran = []
        with patch.dict(sys.modules, modules), \
                patch.object(module.importlib.metadata, "version", return_value="4.1.0"), \
                patch.object(module.runpy, "run_module", side_effect=lambda *a, **k: ran.append(a)), \
                patch.dict(os.environ, {"OPENHANDS_GRADER_IMAGE_ID": image_id}), \
                contextlib.chdir(self.result):
            module.main()
            ContainerCollection().create("swebench/example:latest", name="sweb.eval.fixture.run")
            with self.assertRaises(ValueError):
                ContainerCollection().create("swebench/example:latest", name="sweb.eval.fixture.run",
                                             network_mode="bridge")
            with self.assertRaisesRegex(ValueError, "grader_container_requires_network_none"):
                APIClient().create_container_from_config({"HostConfig": {"NetworkMode": "default"}})
            APIClient().create_container_from_config({"HostConfig": {"NetworkMode": "none"}})
            for forbidden in (APIClient().build, images().pull, volumes().create, networks().create):
                with self.subTest(forbidden=forbidden), self.assertRaises(RuntimeError):
                    forbidden()
        self.assertEqual(ran, [("swebench.harness.run_evaluation",)])
        self.assertEqual([options["network_mode"] for options in created], ["none"])
        self.assertEqual(posted, [{"HostConfig": {"NetworkMode": "none"}}])

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

    def run_to_probe(self, host, probe_passed):
        """host.run through prepare and the P0-P2 probe, with every host and Docker step mocked."""
        prefix, state = self.result / "prefix", self.result / "state"
        (prefix / "venv/bin").mkdir(parents=True)
        (prefix / "venv/bin/python").write_text("")
        state.mkdir()
        pins = json.loads((RECIPE / "pins.json").read_text())
        (state / "installation.json").write_text(json.dumps({"exit_code": 0, "requirements_sha256": pins["requirements_sha256"]}))
        task_file = self.result / "task.json"
        task_file.write_text("[]")
        stack = self.result / "stack"
        (stack / "blueprints/runtime-workers/skills").mkdir(parents=True)
        (stack / "blueprints/runtime-workers/skills/manifest.json").write_text("{}")
        task = {"instance_id": self.INSTANCE, "repo": "django/django", "base_commit": "a" * 40}
        output = io.StringIO()
        with contextlib.ExitStack() as stack_context:
            enter = stack_context.enter_context
            enter(patch.dict(os.environ, {"OPENHANDS_TASK_FILE": str(task_file), "OPENHANDS_TASK_SHA256": "0" * 64,
                                          "OPENHANDS_STACK_ROOT": str(stack)}))
            for name in ("OPENHANDS_ARM", "OPENHANDS_MODEL", "OPENHANDS_BASE_URL", "OPENHANDS_COMPRESSION"):
                os.environ.pop(name, None)
            enter(patch.object(host, "preflight", return_value=(
                pins, {"variables": {"HOST_PATH": "/usr/bin"}, "mcp_readonly_mounts": [], "qmd_collections": {}}, {})))
            enter(patch.object(host, "pinned_image_identity", return_value="containerd"))
            enter(patch.object(host, "load_task", return_value=task))
            enter(patch.object(host, "clone_command", return_value=["true"]))
            enter(patch.object(host, "logged_command", return_value=0))
            enter(patch.object(host.subprocess, "check_output",
                               side_effect=lambda argv, **kwargs: "" if "tag" in argv else "a" * 40 + "\n"))
            enter(patch.object(host, "install_workspace_skills"))
            enter(patch.object(host, "workspace_skills", return_value={}))
            enter(patch.object(host, "worker_instruction", return_value="task"))
            enter(patch.object(host, "model_visible"))
            enter(patch.object(host, "execute_container", return_value=0))
            prepare = enter(patch.object(host, "prepare_native_dispatch"))
            probe = enter(patch.object(host, "run_probe", return_value=probe_passed))
            teardown = enter(patch.object(host, "teardown_attempt", return_value=True))
            enter(patch.object(host, "create_receipt", side_effect=self.absent_gateway_receipt()))
            enter(contextlib.redirect_stdout(output))
            code = host.run(prefix, state, run_id="rw-openhands-probe", arm="control", prepare_only=True)
        return SimpleNamespace(code=code, prepare=prepare, probe=probe, teardown=teardown, prefix=prefix, state=state,
                               pins=pins, result=state / "runs/rw-openhands-probe/control",
                               output=json.loads(output.getvalue()))

    def test_probe_failure_in_run_tears_down_once_and_exits_3(self):
        # Plan E1/G7: a failed containment probe leaves no prepared attempt.
        host = load_recipe_module("host.py")
        run = self.run_to_probe(host, probe_passed=False)
        self.assertEqual(run.code, 3)
        run.prepare.assert_called_once()
        run.probe.assert_called_once_with(run.state, "rw-openhands-probe", "control", run.prefix, run.pins)
        run.teardown.assert_called_once_with(run.state, "rw-openhands-probe", "control")
        status = json.loads((run.result / "status.json").read_text())
        self.assertEqual((status["status"], status["failure_stage"]), ("failed", "probe"))
        self.assertEqual(json.loads((run.result / "receipt.json").read_text())["failure_stage"], "probe")
        self.assertEqual(run.output["failure_stage"], "probe")

    def test_probe_pass_in_run_leaves_the_attempt_prepared(self):
        host = load_recipe_module("host.py")
        run = self.run_to_probe(host, probe_passed=True)
        self.assertEqual(run.code, 0)
        run.probe.assert_called_once()
        run.teardown.assert_not_called()
        self.assertIsNone(run.output["failure_stage"])

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
                if accepted:
                    self.assertEqual(host.check_server_env(env), env)
                    continue
                with self.assertRaises(ValueError) as caught:
                    host.check_server_env(env)
                self.assertNotIn(marker, str(caught.exception))
        env.write_text(f"{name}={marker}\n")
        env.chmod(0o644)
        with self.assertRaises(ValueError):
            host.check_server_env(env)

    def test_session_key_is_generated_per_attempt_and_never_returned(self):
        # Plan E2: generated with Python's secrets module, written with
        # O_CREAT|O_EXCL|O_NOFOLLOW at 0600 under the state root, in docker
        # env-file syntax (N4), plus the curl header file. SDK@fcc102a
        # agent_server/dependencies.py:19 names the X-Session-API-Key header.
        host = load_recipe_module("host.py")
        env_path, headers_path = host.generate_session_files(self.result, "rw-openhands-fixture", "control")
        self.assertEqual((env_path, headers_path), host.session_files(self.result, "rw-openhands-fixture", "control"))
        self.assertEqual(env_path.parent, self.result / "secrets")
        self.assertEqual(stat.S_IMODE(env_path.parent.stat().st_mode), 0o700)
        for path in (env_path, headers_path):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(host.private_file(path), path)
        name, value = env_path.read_text().rstrip("\n").split("=", 1)
        self.assertEqual(name, "OH_SESSION_API_KEYS_0")
        self.assertRegex(value, r"^[A-Za-z0-9_-]{43}$")
        self.assertEqual(env_path.read_text().count("\n"), 1)
        self.assertEqual(headers_path.read_text(), "X-Session-API-Key: " + value + "\n")
        self.assertEqual(host.check_server_env(env_path), env_path)
        with self.assertRaises(FileExistsError):
            host.generate_session_files(self.result, "rw-openhands-fixture", "control")
        other, _ = host.generate_session_files(self.result, "rw-openhands-fixture", "engines-on")
        self.assertNotEqual(other.read_text().split("=", 1)[1], value + "\n")
        # A planted symlink is neither followed nor replaced.
        target = self.result / "planted-target"
        target.write_text("unchanged")
        host.session_files(self.result, "rw-openhands-planted", "control")[0].symlink_to(target)
        with self.assertRaises(OSError):
            host.generate_session_files(self.result, "rw-openhands-planted", "control")
        self.assertEqual(target.read_text(), "unchanged")
        for run_id, arm in (("../escape", "control"), ("rw-openhands-fixture", "other"), ("rw-openhands-A", "control")):
            with self.subTest(run_id=run_id, arm=arm), self.assertRaises(ValueError):
                host.session_files(self.result, run_id, arm)

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
    def image_inspect(pins, store, key="image"):
        image = pins[key]
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

    def install_with(self, host, pins, plain, selected, root, proxy=None):
        """Run install() on mocked inspect output; no Docker command runs."""
        views = {pins["image"]["ref"]: (plain, selected),
                 pins["gateway_proxy"]["ref"]: proxy or self.image_inspect(pins, "containerd", "gateway_proxy")}

        def inspect(argv, **kwargs):
            self.assertEqual(argv[:len(host.DOCKER) + 2], [*host.DOCKER, "image", "inspect"])
            found_plain, found_selected = views[argv[-1]]
            return json.dumps([found_selected if "--platform" in argv else found_plain])

        with patch.object(host, "preflight", return_value=(pins, {}, {})), \
                patch.object(host, "download_verified"), patch.object(host.subprocess, "run") as run, \
                patch.object(host.subprocess, "check_output", side_effect=inspect) as calls, \
                patch.object(host, "execute_container", return_value=0) as execute, \
                contextlib.redirect_stdout(io.StringIO()):
            self.install_runs = run
            try:
                host.install(root / "prefix", root / "state")
            except ValueError as exc:
                return str(exc), execute, calls
        return None, execute, calls

    def test_install_accepts_the_pinned_image_on_containerd_and_classic_stores(self):
        host = load_recipe_module("host.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        ref, proxy = pins["image"]["ref"], pins["gateway_proxy"]["ref"]
        for store in ("containerd", "classic"):
            with self.subTest(store=store):
                error, execute, calls = self.install_with(host, pins, *self.image_inspect(pins, store),
                                                          self.result / store,
                                                          self.image_inspect(pins, store, "gateway_proxy"))
                self.assertIsNone(error)
                execute.assert_called_once()
                argv = [call.args[0] for call in calls.call_args_list]
                self.assertEqual(argv, [[*host.DOCKER, "image", "inspect", ref],
                                        [*host.DOCKER, "image", "inspect", "--platform", "linux/amd64", ref],
                                        [*host.DOCKER, "image", "inspect", proxy],
                                        [*host.DOCKER, "image", "inspect", "--platform", "linux/amd64", proxy]])
                pulls = [call.args[0] for call in self.install_runs.call_args_list if "pull" in call.args[0]]
                self.assertEqual(pulls, [[*host.DOCKER, "pull", "--platform", "linux/amd64", ref],
                                         [*host.DOCKER, "pull", "--platform", "linux/amd64", proxy]])
                installed = json.loads((self.result / store / "state/installation.json").read_text())
                self.assertEqual(installed["image_store"], store)
                self.assertEqual((installed["gateway_proxy"], installed["gateway_proxy_store"]), (proxy, store))

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
        # The gateway proxy pin goes through the same identity check.
        proxy_repo = pins["gateway_proxy"]["ref"].split("@", 1)[0]
        for number, (view, change, expected) in enumerate((
                ("plain", {"RepoDigests": [proxy_repo + ":1.30.5-alpine"]}, "image_repo_digest_mismatch"),
                ("plain", {"Id": other}, "image_configuration_hash_mismatch"),
                ("platform", {"Architecture": "arm64"}, "image_platform_manifest_mismatch"))):
            with self.subTest(proxy=view, change=change):
                proxy_plain, proxy_selected = self.image_inspect(pins, "containerd", "gateway_proxy")
                (proxy_plain if view == "plain" else proxy_selected).update(change)
                error, execute, _ = self.install_with(host, pins, *self.image_inspect(pins, "containerd"),
                                                      self.result / f"proxy-refused-{number}",
                                                      (proxy_plain, proxy_selected))
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
        # Pulls stay forbidden once the transport is installed (see
        # test_grader_main_installs_the_network_none_transport for main()).
        images = type("ImageCollection", (), {"pull": lambda self, *a, **k: "pulled"})
        others = [type(name, (), {"create": lambda self, *a, **k: "created"}) for name in ("C", "V", "N")]
        api = type("APIClient", (), {"build": lambda self: "built", "create_container_from_config": lambda self, c: c})
        module.install_transport(others[0], api, images, others[1], others[2], "sha256:" + "a" * 64)
        with self.assertRaisesRegex(RuntimeError, "use_prebuilt_images"):
            images().pull("swebench/example:latest")

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


class OpenHandsIsolationTests(unittest.TestCase):
    """Phase-2 O1 topology with Docker mocked: our integration checks only.

    Nothing here creates a network or container; the live probe sequence in
    README "Security posture" is the evidence for the topology itself.
    """
    OWNER = {"com.native-agent-stack.owner": "gpt6-omniroute-framework-integration"}
    ISOLATED = "com.docker.network.bridge.gateway_mode_ipv4"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name).resolve()
        self.run_id, self.arm = "rw-openhands-fixture", "control"
        self.stem = self.run_id + "-" + self.arm
        self.result = self.state / "runs" / self.run_id / self.arm
        self.result.mkdir(parents=True)

    def network_view(self, name, **changes):
        internal = name.endswith("-int")
        view = {"id": hashlib.sha256(name.encode()).hexdigest(), "name": name, "driver": "bridge",
                "internal": internal, "ipv6": False, "options": {self.ISOLATED: "isolated"} if internal else {},
                "labels": dict(self.OWNER), "ipam": [{"Subnet": "172.30.0.0/16", "Gateway": "172.30.0.1"}]}
        view.update(changes)
        return view

    def test_topology_creates_an_isolated_internal_network_and_a_gateway_network(self):
        # docker/docs@4e9a5751 port-publishing.md:186-192 (plan N1): no bridge
        # address in gateway mode isolated; network_create.md: --internal.
        host = load_recipe_module("host.py")
        commands = []
        views = {self.stem + kind: self.network_view(self.stem + kind) for kind in ("-int", "-gw")}
        with patch.object(host, "logged_command", side_effect=lambda argv, *a, **k: commands.append(argv) or 0), \
                patch.object(host.subprocess, "check_output",
                             side_effect=lambda argv, **k: json.dumps(views[argv[-1]])) as inspect:
            networks = host.create_topology(self.result, self.stem)
        label = "com.native-agent-stack.owner=gpt6-omniroute-framework-integration"
        self.assertEqual(commands, [
            [*host.DOCKER, "network", "create", "--internal", "--ipv6=false",
             "-o", "com.docker.network.bridge.gateway_mode_ipv4=isolated", "--label", label, self.stem + "-int"],
            [*host.DOCKER, "network", "create", "--ipv6=false", "--label", label, self.stem + "-gw"]])
        self.assertEqual([call.args[0] for call in inspect.call_args_list],
                         [[*host.DOCKER, "network", "inspect", "--format", host.NETWORK_FORMAT, self.stem + kind]
                          for kind in ("-int", "-gw")])
        self.assertEqual({kind: view["name"] for kind, view in networks.items()},
                         {"int": self.stem + "-int", "gw": self.stem + "-gw"})

    def test_topology_fails_closed_when_the_isolated_gateway_mode_is_rejected(self):
        host = load_recipe_module("host.py")
        commands = []
        with patch.object(host, "logged_command", side_effect=lambda argv, *a, **k: commands.append(argv) or 1), \
                patch.object(host.subprocess, "check_output") as inspect, self.assertRaises(RuntimeError):
            host.create_topology(self.result, self.stem)
        # No retry without the option (never a plain --internal fallback).
        self.assertEqual(len(commands), 1)
        inspect.assert_not_called()

    def test_topology_refuses_networks_whose_inspect_differs(self):
        host = load_recipe_module("host.py")
        for kind, change in (("-int", {"internal": False}), ("-int", {"options": {}}),
                             ("-int", {"options": {self.ISOLATED: "nat"}}), ("-int", {"ipv6": True}),
                             ("-int", {"labels": {}}), ("-int", {"driver": "macvlan"}),
                             ("-int", {"name": "other"}), ("-int", {"id": "short"}),
                             ("-gw", {"internal": True}), ("-gw", {"ipv6": True}), ("-gw", {"labels": {}})):
            with self.subTest(kind=kind, change=change):
                views = {self.stem + k: self.network_view(self.stem + k) for k in ("-int", "-gw")}
                views[self.stem + kind].update(change)
                with patch.object(host, "logged_command", return_value=0), \
                        patch.object(host.subprocess, "check_output",
                                     side_effect=lambda argv, **k: json.dumps(views[argv[-1]])), \
                        self.assertRaises(ValueError):
                    host.create_topology(self.result, self.stem)

    @staticmethod
    def proxy_blocks():
        text = (RECIPE / "config/proxy-nginx.conf").read_text()
        body = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
        return text, body, body[body.index("listen 8081;"):body.index("listen 8080;")], body[body.index("listen 8080;"):]

    def test_proxy_template_is_the_three_route_v1_allowlist(self):
        text, body, agent, host_side = self.proxy_blocks()
        placeholders = re.findall(r"@[A-Z]+@", text)
        self.assertEqual(sorted(set(placeholders)), ["@COMPRESSION@", "@PORT@", "@RUN@", "@SERVER@"])
        self.assertEqual(text.count("@"), 2 * len(placeholders))
        self.assertEqual(re.findall(r"listen\s+([^;]+);", body), ["8081", "8080"])
        self.assertEqual(re.findall(r"location\s+(=?)\s*(\S+)\s*\{", agent),
                         [("=", "/v1/responses"), ("=", "/v1/chat/completions"), ("=", "/v1/models"), ("", "/")])
        for route, method in (("/v1/responses", "POST"), ("/v1/chat/completions", "POST"), ("/v1/models", "GET")):
            self.assertRegex(agent, r"location = " + re.escape(route) + r"\s*\{\s*limit_except " + method
                             + r"\s*\{ deny all; \}\s*proxy_pass http://10\.0\.2\.2:@PORT@" + re.escape(route) + r";\s*\}")
        self.assertRegex(agent, r"location / \{ return 403; \}")
        self.assertRegex(agent, r"if \(\$is_args\) \{ return 403; \}")
        self.assertIn("proxy_pass_request_headers off;", agent)
        self.assertEqual(dict(re.findall(r'proxy_set_header\s+(\S+)\s+("[^"]*"|\$\w+);', agent)), {
            "Host": '"10.0.2.2:@PORT@"', "Content-Type": "$content_type", "Accept": "$http_accept",
            "Idempotency-Key": "$http_idempotency_key", "Authorization": '"Bearer local-loopback"',
            "X-Correlation-Id": '"@RUN@"', "x-omniroute-session": '"@RUN@"',
            "x-omniroute-compression": '"@COMPRESSION@"'})
        self.assertEqual(agent.count("proxy_set_header"), 8)
        self.assertEqual(set(re.findall(r"\$http_\w+", agent)), {"$http_accept", "$http_idempotency_key"})
        # The host side carries the event-search query string, so it refuses none.
        self.assertNotIn("$is_args", host_side)
        self.assertNotIn("proxy_pass_request_headers", host_side)
        self.assertRegex(host_side, r"location / \{ proxy_pass http://@SERVER@:8000; \}")
        self.assertNotIn("resolver", body)
        self.assertIn("server_tokens off;", body)
        self.assertIn("pid /tmp/nginx.pid;", body)
        for path in re.findall(r"_temp_path\s+(\S+);", body):
            self.assertTrue(path.startswith("/tmp/"), path)

    def test_host_side_access_log_records_no_request_line(self):
        # GPT-6 review session-key-logging: the combined format logs "$request"
        # (nginx release-1.30.5 src/http/modules/ngx_http_log_module.c:230-232),
        # so a URI sent to gw:8080 would reach the retained proxy log whole.
        _, body, agent, host_side = self.proxy_blocks()
        http_level = body[:body.index("listen 8081;")]
        formats = dict(re.findall(r"log_format\s+(\w+)\s+'([^']*)';", body))
        self.assertEqual(list(formats), ["ingress"])
        self.assertIn("log_format ingress", http_level)
        self.assertEqual(re.findall(r"\$\w+", formats["ingress"]), ["$time_iso8601", "$request_method", "$status"])
        self.assertEqual(re.findall(r"access_log\s+([^;]+);", host_side), ["/dev/stdout ingress"])
        # P5 triages the agent side's full request lines, so 8081 keeps the combined default.
        self.assertEqual(re.findall(r"access_log\s+([^;]+);", http_level), ["/dev/stdout"])
        self.assertEqual(re.findall(r"access_log\s+([^;]+);", agent), [])

    def test_proxy_render_fills_each_placeholder_from_the_arm_selection(self):
        host = load_recipe_module("host.py")
        recipe = load_recipe_module("recipe.py")
        for selection, port, other, combo in (
                (recipe.arm_config("control"), 20128, 20129, ""),
                (recipe.arm_config("engines-on"), 20129, 20128, "allow-lossy"),
                (recipe.arm_config("engines-on", compression="fw-rtk"), 20129, 20128, "fw-rtk")):
            with self.subTest(arm=selection["arm"], combo=combo):
                stem = self.run_id + "-" + selection["arm"]
                text = host.render_proxy_config(selection, self.run_id)
                self.assertNotIn("@", text)
                self.assertEqual(text.count(f"proxy_pass http://10.0.2.2:{port}/v1/"), 3)
                self.assertNotIn(f"10.0.2.2:{other}", text)
                self.assertIn(f"proxy_pass http://{stem}-server:8000;", text)
                values = dict(re.findall(r'proxy_set_header\s+(\S+)\s+"([^"]*)";', text))
                self.assertEqual(values, {"Host": f"10.0.2.2:{port}", "Authorization": "Bearer local-loopback",
                                          "X-Correlation-Id": self.run_id, "x-omniroute-session": self.run_id,
                                          "x-omniroute-compression": combo})

    def test_proxy_render_refuses_values_outside_their_patterns(self):
        host = load_recipe_module("host.py")
        recipe = load_recipe_module("recipe.py")
        control, engines = recipe.arm_config("control"), recipe.arm_config("engines-on")
        for run_id in ("rw-openhands-UPPER", "rw-openhands-x;", "rw-openhands-x\n", 'rw-openhands-x"',
                       "rw-openhands-x}", "other-run", "rw-openhands-" + "a" * 65):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                host.render_proxy_config(control, run_id)
        for forged in (dict(control, gateway_port=20129), dict(engines, gateway_port=20128),
                       dict(control, compression_combo="allow-lossy"), dict(engines, compression_combo=None),
                       dict(engines, compression_combo="default-caveman"), dict(engines, compression_combo='x";'),
                       dict(control, arm="other"), dict(control, base_url="http://10.0.2.2:20128/v1"),
                       dict(control, gateway_upstream="http://10.0.2.2:20129/v1")):
            with self.subTest(forged=forged), self.assertRaises(ValueError):
                host.render_proxy_config(forged, self.run_id)
        template = self.result / "proxy-template.conf"
        template.write_text((RECIPE / "config/proxy-nginx.conf").read_text() + "# @EXTRA@\n")
        with patch.object(host, "PROXY_TEMPLATE", template), self.assertRaises(ValueError):
            host.render_proxy_config(control, self.run_id)

    def test_rendered_proxy_config_is_host_owned_0644_outside_model_mounts(self):
        host = load_recipe_module("host.py")
        text = "events {}\n"
        path, sha = host.write_proxy_config(self.result, text)
        self.assertEqual(path, self.result / "proxy/nginx.conf")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(path.stat().st_uid, os.getuid())
        self.assertEqual(sha, hashlib.sha256(text.encode()).hexdigest())
        with self.assertRaises(FileExistsError):
            host.write_proxy_config(self.result, text)

    def test_proxy_launch_is_create_connect_start_with_loopback_ingress_only(self):
        host = load_recipe_module("host.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        config = self.result / "proxy/nginx.conf"
        create, connect, start = host.proxy_commands(pins, self.stem, config, 3740)
        self.assertEqual(create[:len(host.DOCKER) + 1], [*host.DOCKER, "create"])
        for flag in ("--pull=never", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                     "--network=" + self.stem + "-gw"):
            self.assertIn(flag, create)
        options = {create[i]: create[i + 1] for i in range(len(create) - 1) if create[i].startswith("--")}
        self.assertEqual(options["--name"], self.stem + "-proxy")
        self.assertEqual(options["--label"], "com.native-agent-stack.owner=gpt6-omniroute-framework-integration")
        self.assertEqual(options["--publish"], "127.0.0.1:3740:8080")
        self.assertEqual(options["--platform"], "linux/amd64")
        self.assertEqual(options["--tmpfs"], "/tmp:rw,nosuid,nodev,mode=1777")
        self.assertEqual((options["--pids-limit"], options["--memory"]), ("64", "256m"))
        self.assertEqual(options["--mount"], f"type=bind,src={config},dst=/etc/nginx/nginx.conf,readonly")
        self.assertEqual(options["--entrypoint"], "nginx")
        self.assertEqual(create[-3:], [pins["gateway_proxy"]["ref"], "-g", "daemon off;"])
        self.assertEqual(sum(arg == "--publish" or re.match(r"-p\b", arg) is not None for arg in create), 1)
        self.assertEqual(connect, [*host.DOCKER, "network", "connect", "--alias", "gw", self.stem + "-int",
                                   self.stem + "-proxy"])
        self.assertEqual(start, [*host.DOCKER, "start", self.stem + "-proxy"])
        for port in (3729, 3800, True):
            with self.subTest(port=port), self.assertRaises(ValueError):
                host.proxy_commands(pins, self.stem, config, port)
        with self.assertRaises(ValueError):
            host.proxy_commands(pins, self.run_id, config, 3740)

    def docker_run_fake(self, host, *, removed=True, listed=""):
        calls = []

        def run(argv, **kwargs):
            calls.append(list(argv))
            tail = argv[len(host.DOCKER):]
            if tail[:1] == ["rm"]:
                return subprocess.CompletedProcess(argv, 0 if removed else 1)
            if tail[:1] == ["ps"]:
                return subprocess.CompletedProcess(argv, 0, stdout="" if removed else "still-there\n")
            if tail[:2] == ["network", "ls"]:
                return subprocess.CompletedProcess(argv, 0, stdout="bridge\nhost\nnone\n" + listed)
            return subprocess.CompletedProcess(argv, 0, stdout="")
        return calls, run

    def test_teardown_removes_proxy_then_server_then_networks_by_exact_name(self):
        host = load_recipe_module("host.py")
        keys = host.generate_session_files(self.state, self.run_id, self.arm)
        calls, run = self.docker_run_fake(host)
        with patch.object(host.subprocess, "run", side_effect=run):
            self.assertTrue(host.teardown_attempt(self.state, self.run_id, self.arm))
        self.assertEqual([argv[len(host.DOCKER):] for argv in calls], [
            ["logs", self.stem + "-proxy"], ["rm", "-f", self.stem + "-proxy"],
            ["logs", self.stem + "-server"], ["rm", "-f", self.stem + "-server"],
            ["network", "rm", self.stem + "-int"], ["network", "ls", "--format", "{{.Name}}"],
            ["network", "rm", self.stem + "-gw"], ["network", "ls", "--format", "{{.Name}}"]])
        self.assertNotIn("prune", json.dumps(calls))
        for record in ("proxy.log.cleanup.json", "server.log.cleanup.json",
                       "network-int.cleanup.json", "network-gw.cleanup.json"):
            self.assertIs(json.loads((self.result / record).read_text())["confirmed_removed"], True, record)
        self.assertFalse(any(path.exists() for path in keys))

    def test_teardown_keeps_key_files_while_removal_is_unconfirmed(self):
        host = load_recipe_module("host.py")
        keys = host.generate_session_files(self.state, self.run_id, self.arm)
        calls, run = self.docker_run_fake(host, removed=False, listed=self.stem + "-int\n")
        with patch.object(host.subprocess, "run", side_effect=run):
            self.assertFalse(host.teardown_attempt(self.state, self.run_id, self.arm))
        self.assertTrue(all(path.exists() for path in keys))
        self.assertIs(json.loads((self.result / "server.log.cleanup.json").read_text())["confirmed_removed"], False)
        self.assertIs(json.loads((self.result / "network-int.cleanup.json").read_text())["confirmed_removed"], False)
        self.assertIs(json.loads((self.result / "network-gw.cleanup.json").read_text())["confirmed_removed"], True)


class OpenHandsProbeTests(unittest.TestCase):
    """Locally composed P0-P2 probe and dispatch gate (plan section 1, E1, G7).

    Our integration checks with Docker mocked, not upstream tests. Nothing here
    creates a container or network or sends a gateway request; the HTTP
    fixture is an in-process server on 127.0.0.1. The live probe sequence in
    README "Security posture" is the evidence for the topology itself.
    """
    OWNER = {"com.native-agent-stack.owner": "gpt6-omniroute-framework-integration"}
    ISOLATED = "com.docker.network.bridge.gateway_mode_ipv4"
    # The plan's P1 denied list (section 1), in its order.
    PLAN_DENIED = (
        *(("GET", target) for target in (
            "/api/settings", "/api/providers", "/api/keys", "/dashboard", "/v1/ws", "/v1/alpha/search",
            "/v1/files", "/V1/models", "/v1/models/", "/v1/responses/x", "/v1/../api/settings",
            "/v1/%2e%2e/api/settings", "/v1/models/../../api/keys", "//api/settings", "/codex/responses",
            "/api/v1/responses", "/v1/models?x=1", "/v1/models?0")),
        *(("POST", target) for target in (
            "/responses", "/chat/completions", "/api/v1/responses", "/api/settings/require-login",
            "/v1/responses?provider=x")),
        ("DELETE", "/v1/models"), ("PUT", "/v1/responses"), ("GET", "/v1/responses"))
    # iproute2 output shapes; 192.0.2.20 is an RFC 5737 documentation address.
    SS = ("LISTEN 0      4096       127.0.0.1:20128      0.0.0.0:*\n"
          "LISTEN 0      511            [::1]:3000          [::]:*\n"
          "LISTEN 0      4096               *:8080             *:*\n"
          "LISTEN 0      128    127.0.0.53%lo:53         0.0.0.0:*\n"
          "LISTEN 0      4096 [::ffff:127.0.0.1]:9000          *:*\n"
          "LISTEN 0      4096       127.0.0.1:3730       0.0.0.0:*\n"
          "LISTEN 0      4096         0.0.0.0:20128      0.0.0.0:*\n")
    IP = ("1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever\n"
          "1: lo    inet 10.255.255.254/32 brd 10.255.255.254 scope global lo\\       valid_lft forever preferred_lft forever\n"
          "2: eth0    inet 192.0.2.20/24 brd 192.0.2.255 scope global noprefixroute eth0\\       valid_lft forever preferred_lft forever\n"
          "3: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\       valid_lft forever preferred_lft forever\n")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name).resolve()
        self.run_id, self.arm = "rw-openhands-fixture", "control"
        self.stem = self.run_id + "-" + self.arm
        self.result = self.state / "runs" / self.run_id / self.arm
        self.result.mkdir(parents=True)
        self.pins = json.loads((RECIPE / "pins.json").read_text())
        # G5 fixtures only; no unit test opens a live gateway store.
        self.stores = {"control": gateway_store(self.state / "omniroute.sqlite", ["codex"] * 6),
                       "engines-on": gateway_store(self.state / "omniroute-fw.sqlite", [ENGINES_NODE])}
        self.host_file = self.state / "host.json"
        self.host_file.write_text(json.dumps({"gateway_providers": {
            "control": ["codex"], "engines-on": ["openai-compatible-responses-*"]}}))
        self.host_file.chmod(0o600)

    @staticmethod
    def closed_port():
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    def serve(self, replies):
        """In-process HTTP fixture on 127.0.0.1:0 recording each raw request line."""
        seen = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def reply(self):
                # self.path rewrites a leading "//" (CPython gh-87389); the raw
                # request line keeps the target byte-identical.
                method, target, _ = self.requestline.split(" ", 2)
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                seen.append((method, target, body, self.headers.get("Content-Type")))
                status, route = replies.get((method, target), (403, None))
                payload = b"fixture-body-never-recorded"
                self.send_response(status)
                if route:
                    self.send_header("x-omniroute-route-class", route)
                self.send_header("Set-Cookie", "session=fixture-cookie")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_PUT = do_DELETE = reply

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address[1], seen

    def test_netprobe_lists_are_the_plan_lists_and_import_does_no_work(self):
        with patch("socket.socket", side_effect=AssertionError("socket at import")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("dns at import")), \
                patch("socket.create_connection", side_effect=AssertionError("connect at import")):
            netprobe = load_recipe_module("e2e/netprobe.py")
        self.assertEqual(netprobe.DENIED, self.PLAN_DENIED)
        self.assertEqual(len(netprobe.DENIED), 26)
        self.assertEqual(netprobe.P1_EXPECTED, (("gw", 8081, "GET", "/v1/models", 200, "CLIENT_API"),
                                                *(("gw", 8081, m, t, 403, None) for m, t in self.PLAN_DENIED)))
        self.assertEqual(netprobe.p0_expected(20129), (("10.0.2.2", 20129, "GET", "/v1/models", 200, "CLIENT_API"),
                                                        ("10.0.2.2", 20129, "GET", "/api/settings", None, "MANAGEMENT")))
        self.assertEqual(netprobe.dns_expected(self.stem + "-server"), (
            ("example.com", False), ("github.com", False), ("host.docker.internal", False),
            ("gw", True), (self.stem + "-server", True)))
        self.assertEqual(netprobe.FIXED_ADDRESSES, ("10.0.2.2", "10.0.2.3", "172.17.0.1", "10.0.0.1", "10.255.255.254"))
        self.assertEqual(netprobe.EXTRA_PORTS, (53,))
        # Repair R4: off-subnet connects must fail for want of a route, not time out.
        self.assertEqual(netprobe.UNREACHABLE, ("ENETUNREACH", "EHOSTUNREACH"))
        self.assertEqual(netprobe.UDP_TARGET, ("10.0.2.3", 53))
        self.assertEqual(netprobe.ROUTES, "/proc/net/route")
        # RFC 1035 section 4.1.1-4.1.2: one recursive A/IN question for example.com.
        self.assertEqual(netprobe.DNS_QUERY[2:12], bytes.fromhex("01000001000000000000"))
        self.assertEqual(netprobe.DNS_QUERY[12:], b"\x07example\x03com\x00\x00\x01\x00\x01")
        # P3 is implemented but only runs in the explicitly owned container;
        # fixture/import checks never make live model calls or certify P3.
        with self.assertRaises(ValueError):
            netprobe.p3_control_call({}, "rw-openhands-fixture")

    def test_netprobe_sends_raw_targets_verbatim_and_never_records_bodies(self):
        netprobe = load_recipe_module("e2e/netprobe.py")
        port, seen = self.serve({("GET", "/v1/models"): (200, "CLIENT_API"), ("GET", "/management-class"): (200, "MANAGEMENT"),
                                 ("GET", "/other-class"): (403, "SOMETHING-ELSE")})
        pairs = (("GET", "/v1/models"), ("GET", "/management-class"), ("GET", "/other-class"), *self.PLAN_DENIED)
        records = [netprobe.http_probe("127.0.0.1", port, method, target) for method, target in pairs]
        self.assertEqual([(method, target) for method, target, _, _ in seen], list(pairs))
        for raw in ("/v1/%2e%2e/api/settings", "//api/settings", "/v1/models?0", "/V1/models", "/v1/../api/settings"):
            self.assertIn(("GET", raw), [(method, target) for method, target, _, _ in seen])
        self.assertEqual([(body, kind) for method, _, body, kind in seen if method == "POST"],
                         [(b"{}", "application/json")] * 5)
        self.assertEqual([(r["status"], r["route_class"]) for r in records[:3]],
                         [(200, "CLIENT_API"), (200, "MANAGEMENT"), (403, "<other>")])
        self.assertTrue(all(r["status"] == 403 and r["route_class"] is None and r["error"] is None for r in records[3:]))
        self.assertEqual(set(records[0]), {"host", "port", "method", "target", "status", "route_class", "error"})
        text = json.dumps(records)
        for marker in ("fixture-body-never-recorded", "fixture-cookie", "Set-Cookie"):
            self.assertNotIn(marker, text)
        refused = netprobe.http_probe("127.0.0.1", self.closed_port(), "GET", "/v1/models")
        self.assertEqual((refused["status"], refused["route_class"], refused["error"]), (None, None, "ECONNREFUSED"))

    def test_netprobe_connects_resolves_and_reads_ipv6_without_defaults(self):
        netprobe = load_recipe_module("e2e/netprobe.py")
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        open_port, closed = listener.getsockname()[1], self.closed_port()
        records = netprobe.connect_all([("127.0.0.1", open_port), ("127.0.0.1", closed)], timeout=2, workers=2)
        self.assertEqual([(r["address"], r["port"], r["connected"], r["error"]) for r in records],
                         [("127.0.0.1", open_port, True, None), ("127.0.0.1", closed, False, "ECONNREFUSED")])
        with patch.object(netprobe.socket, "getaddrinfo", side_effect=socket.gaierror(socket.EAI_NONAME, "fixture")):
            self.assertEqual(netprobe.resolve("example.com"), {"name": "example.com", "resolved": False, "error": "EAI_NONAME"})
        # Addendum (b): a temporary failure stays distinguishable from "no such name".
        with patch.object(netprobe.socket, "getaddrinfo", side_effect=socket.gaierror(socket.EAI_AGAIN, "fixture")):
            self.assertEqual(netprobe.resolve("github.com"), {"name": "github.com", "resolved": False, "error": "EAI_AGAIN"})
        with patch.object(netprobe.socket, "getaddrinfo",
                          return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.30.0.3", 0))]):
            self.assertEqual(netprobe.resolve("gw"), {"name": "gw", "resolved": True, "error": None})
        # /proc/net/if_inet6: address, ifindex, prefix, scope, flags, name.
        lo = "00000000000000000000000000000001 01 80 10 80       lo\n"
        link = "fe80000000000000004200fffeac1e02 02 40 20 80     eth0\n"
        other = "20010db8000000000000000000000005 02 40 00 00     eth0\n"
        self.assertEqual(netprobe.ipv6_summary(lo), {"available": True, "loopback": 1, "non_loopback": 0, "link_local": 0})
        self.assertEqual(netprobe.ipv6_summary(lo + link), {"available": True, "loopback": 1, "non_loopback": 1, "link_local": 1})
        self.assertEqual(netprobe.ipv6_summary(lo + link + other)["non_loopback"], 2)
        with self.assertRaises(ValueError):
            netprobe.ipv6_summary("garbage\n")

    @staticmethod
    def closed_udp_port():
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    def test_netprobe_reads_routes_sends_one_udp_query_and_runs_the_positive_control(self):
        netprobe = load_recipe_module("e2e/netprobe.py")
        # linux@v6.18 net/ipv4/fib_trie.c:2940-3000 writes /proc/net/route from the main table:
        # iface, destination, gateway, flags, refcnt, use, metric, mask, mtu, window, irtt.
        header = "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT".ljust(127) + "\n"
        subnet = "eth0\t00001EAC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0".ljust(127) + "\n"
        default = "eth0\t00000000\t01001EAC\t0003\t0\t0\t0\t00000000\t0\t0\t0".ljust(127) + "\n"
        via = "eth0\t0002000A\t01001EAC\t0003\t0\t0\t0\t00FFFFFF\t0\t0\t0".ljust(127) + "\n"
        self.assertEqual(netprobe.route_summary(header + subnet),
                         {"available": True, "routes": 1, "default": 0, "gateway": 0})
        self.assertEqual(netprobe.route_summary(header + subnet + default),
                         {"available": True, "routes": 2, "default": 1, "gateway": 1})
        self.assertEqual(netprobe.route_summary(header + subnet + via),
                         {"available": True, "routes": 2, "default": 0, "gateway": 1})
        self.assertEqual(netprobe.route_summary(header), {"available": True, "routes": 0, "default": 0, "gateway": 0})
        for bad in ("", "garbage\n", header + "eth0\t0\t0\n", header + subnet.replace("\t0001\t", "\tzz01\t")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                netprobe.route_summary(bad)
        with patch.object(netprobe, "ROUTES", str(self.result / "absent-route-table")):
            self.assertEqual(netprobe.read_routes(), {"available": False, "routes": 0, "default": 0, "gateway": 0})
        # One DNS datagram: answered, refused by ICMP, and unroutable.
        answering = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(answering.close)
        answering.bind(("127.0.0.1", 0))
        received = []

        def answer():
            data, peer = answering.recvfrom(512)
            received.append(data)
            answering.sendto(data[:2] + b"\x81\x80" + data[4:], peer)
        thread = threading.Thread(target=answer, daemon=True)
        thread.start()
        port = answering.getsockname()[1]
        self.assertEqual(netprobe.udp_probe("127.0.0.1", port, timeout=2),
                         {"address": "127.0.0.1", "port": port, "answered": True, "error": None})
        thread.join(2)
        self.assertEqual(received, [netprobe.DNS_QUERY])
        # Whether a closed loopback port reports ICMP refusal or stays silent differs
        # between hosts (this WSL2 host times out); both are "no answer".
        silent = netprobe.udp_probe("127.0.0.1", self.closed_udp_port(), timeout=0.5)
        self.assertEqual(silent["answered"], False)
        self.assertIn(silent["error"], ("timeout", "ECONNREFUSED"))
        with patch.object(netprobe.socket.socket, "recv", side_effect=ConnectionRefusedError(errno.ECONNREFUSED, "fixture")):
            refused = netprobe.udp_probe("127.0.0.1", self.closed_udp_port())
        self.assertEqual((refused["answered"], refused["error"]), (False, "ECONNREFUSED"))
        with patch.object(netprobe.socket.socket, "connect", side_effect=OSError(errno.ENETUNREACH, "fixture")):
            self.assertEqual(netprobe.udp_probe("10.0.2.3", 53),
                             {"address": "10.0.2.3", "port": 53, "answered": False, "error": "ENETUNREACH"})
        # The positive control connects to gw:8081 by name; here a local listener stands in.
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with patch.object(netprobe, "PROXY_HOST", "127.0.0.1"), \
                patch.object(netprobe, "PROXY_PORT", listener.getsockname()[1]):
            self.assertEqual(netprobe.control_probe(timeout=2), {"host": "127.0.0.1", "port": listener.getsockname()[1],
                                                                 "connected": True, "error": None})
        closed = self.closed_port()
        with patch.object(netprobe, "PROXY_HOST", "127.0.0.1"), patch.object(netprobe, "PROXY_PORT", closed):
            self.assertEqual(netprobe.control_probe(timeout=2), {"host": "127.0.0.1", "port": closed,
                                                                 "connected": False, "error": "ECONNREFUSED"})

    def expected_http(self, host_name, port, method, target):
        status = 200 if (method, target) == ("GET", "/v1/models") else 403
        return {"host": host_name, "port": port, "method": method, "target": target, "status": status,
                "route_class": "CLIENT_API" if status == 200 else None, "error": None}

    def test_netprobe_stops_at_the_first_unexpected_result(self):
        netprobe = load_recipe_module("e2e/netprobe.py")
        out = self.result / "probe-output"
        out.mkdir()
        target = out / "observations.json"

        def forwarded(host_name, port, method, path, **kwargs):
            record = self.expected_http(host_name, port, method, path)
            return dict(record, status=404) if (method, path) == ("GET", "/v1/files") else record
        previous = os.umask(0o077)
        self.addCleanup(os.umask, previous)
        with patch.object(netprobe, "http_probe", side_effect=forwarded) as http, \
                patch.object(netprobe, "control_probe") as control, patch.object(netprobe, "udp_probe") as udp, \
                patch.object(netprobe, "connect_all") as connects, patch.object(netprobe, "resolve") as resolve:
            code = netprobe.main(["int", "--out", str(target), "--server", self.stem + "-server",
                                  "--addresses", "10.0.2.2", "--ports", "20128", "--subnets", "172.30.0.0/16"])
        self.assertEqual(code, 1)
        stop = self.PLAN_DENIED.index(("GET", "/v1/files")) + 2
        data = json.loads(target.read_text())
        self.assertEqual(len(data["p1"]), stop)
        self.assertEqual(http.call_count, stop)
        for later in (control, udp, connects, resolve):
            later.assert_not_called()
        self.assertNotIn("p2", data)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_netprobe_int_mode_passes_only_when_everything_is_refused(self):
        netprobe = load_recipe_module("e2e/netprobe.py")
        server = self.stem + "-server"
        routes = {"available": True, "routes": 1, "default": 0, "gateway": 0}
        cases = {"contained": {}, "connect": {"connected": True}, "off-subnet timeout": {"error": "timeout"},
                 "dns": {"resolvable": True}, "ipv6": {"ipv6": 1}, "control refused": {"control": False},
                 "udp answered": {"answered": True}, "udp timeout": {"udp_error": "timeout"},
                 "default route": {"routes": dict(routes, default=1, gateway=1)},
                 "gateway route": {"routes": dict(routes, gateway=1)},
                 "no route table": {"routes": {"available": False, "routes": 0, "default": 0, "gateway": 0}}}
        for label, case in cases.items():
            with self.subTest(label):
                target = self.result / (label.replace(" ", "-") + ".json")
                connected, reached = case.get("connected", False), case.get("control", True)

                def connects(pairs, **kwargs):
                    return [{"address": a, "port": p, "connected": connected,
                             "error": None if connected else case.get("error", "ENETUNREACH")} for a, p in pairs]

                def resolve(name):
                    ok = name in {"gw", server} or case.get("resolvable", False)
                    return {"name": name, "resolved": ok, "error": None if ok else "EAI_AGAIN"}
                control = {"host": "gw", "port": 8081, "connected": reached, "error": None if reached else "ECONNREFUSED"}
                udp = {"address": "10.0.2.3", "port": 53, "answered": case.get("answered", False),
                       "error": None if case.get("answered") else case.get("udp_error", "ENETUNREACH")}
                with patch.object(netprobe, "http_probe", side_effect=self.expected_http), \
                        patch.object(netprobe, "control_probe", return_value=control), \
                        patch.object(netprobe, "connect_all", side_effect=connects) as batch, \
                        patch.object(netprobe, "udp_probe", return_value=udp) as datagram, \
                        patch.object(netprobe, "resolve", side_effect=resolve), \
                        patch.object(netprobe, "read_ipv6", return_value={
                            "available": True, "loopback": 1, "non_loopback": case.get("ipv6", 0),
                            "link_local": case.get("ipv6", 0)}), \
                        patch.object(netprobe, "read_routes", return_value=case.get("routes", routes)):
                    code = netprobe.main(["int", "--out", str(target), "--server", server,
                                          "--addresses", "10.0.2.2,192.0.2.20", "--ports", "53,20128",
                                          "--subnets", "172.30.0.0/16"])
                self.assertEqual(code, 0 if label == "contained" else 1)
                if reached:
                    self.assertEqual(batch.call_args.args[0], [("10.0.2.2", 53), ("10.0.2.2", 20128),
                                                               ("192.0.2.20", 53), ("192.0.2.20", 20128)])
                else:  # The positive control failed, so nothing negative is attempted.
                    batch.assert_not_called()
                data = json.loads(target.read_text())
                verdict = netprobe.evaluate_p2(data.get("p2"), ["10.0.2.2", "192.0.2.20"], [53, 20128], server,
                                               ["172.30.0.0/16"])
                self.assertEqual(verdict["passed"], label == "contained")
                if label == "contained":
                    datagram.assert_called_once_with("10.0.2.3", 53)
                    self.assertEqual({key: verdict[key] for key in (
                        "control_connected", "off_subnet", "off_subnet_unreachable", "udp_answered", "udp_errors",
                        "dns_errors", "routes_available", "routes", "default_routes", "gateway_routes")}, {
                        "control_connected": True, "off_subnet": 4, "off_subnet_unreachable": 4,
                        "udp_answered": False, "udp_errors": {"ENETUNREACH": 1}, "dns_errors": {"EAI_AGAIN": 3},
                        "routes_available": True, "routes": 1, "default_routes": 0, "gateway_routes": 0})
        # A target inside the run subnet (a host address that collides with it) may time out, never connect.
        inside = {"control": {"host": "gw", "port": 8081, "connected": True, "error": None},
                  "connects": [{"address": "10.0.2.2", "port": 53, "connected": False, "error": "ENETUNREACH"},
                               {"address": "172.30.0.9", "port": 53, "connected": False, "error": "timeout"}],
                  "udp": {"address": "10.0.2.3", "port": 53, "answered": False, "error": "EHOSTUNREACH"},
                  "dns": [{"name": name, "resolved": ok, "error": None if ok else "EAI_NONAME"}
                          for name, ok in netprobe.dns_expected(server)],
                  "ipv6": {"available": True, "loopback": 1, "non_loopback": 0, "link_local": 0}, "routes": routes}
        verdict = netprobe.evaluate_p2(inside, ["10.0.2.2", "172.30.0.9"], [53], server, ["172.30.0.0/16"])
        self.assertEqual((verdict["passed"], verdict["off_subnet"], verdict["off_subnet_unreachable"]), (True, 1, 1))
        inside["connects"][1].update(connected=True, error=None)
        self.assertFalse(netprobe.evaluate_p2(inside, ["10.0.2.2", "172.30.0.9"], [53], server, ["172.30.0.0/16"])["passed"])
        base = ["--server", server, "--addresses", "10.0.2.2", "--ports", "53", "--subnets", "172.30.0.0/16"]
        for index, change in enumerate(({"--server": "other"}, {"--addresses": "gw"}, {"--ports": "0"},
                                        {"--subnets": ""}, {"--subnets": "172.30.0.1/16"}, {"--subnets": "gw"})):
            argv = ["int", "--out", str(self.result / f"refused-{index}.json")]
            for flag, value in zip(base[::2], base[1::2]):
                argv += [flag, change.get(flag, value)]
            with self.subTest(change=change), patch.object(netprobe, "http_probe") as http, self.assertRaises(ValueError):
                netprobe.main(argv)
            http.assert_not_called()

    def test_probe_targets_come_from_ss_ip_and_the_attempt_networks(self):
        host = load_recipe_module("host.py")
        self.assertEqual(host.listener_ports(self.SS), [53, 3000, 3730, 8080, 9000, 20128])
        # Container loopback is its own namespace: 127.0.0.0/8 is excluded by address.
        self.assertEqual(host.host_ipv4_addresses(self.IP), ["10.255.255.254", "172.17.0.1", "192.0.2.20"])
        views = self.views()
        networks = {"int": views[("network", self.stem + "-int")], "gw": views[("network", self.stem + "-gw")]}
        own = {"server_int": "172.30.0.1", "proxy_int": "172.30.0.2", "proxy_gw": "172.31.0.2"}
        addresses, ports, excluded = host.probe_targets(networks, self.SS, self.IP, own)
        # Repair R2: only recorded IPAM gateways are added. The isolated $S-int has none,
        # and its first endpoint, the server, holds 172.30.0.1.
        self.assertEqual(addresses, ["10.0.0.1", "10.0.2.2", "10.0.2.3", "10.255.255.254", "172.17.0.1",
                                     "172.31.0.1", "192.0.2.20"])
        self.assertEqual(ports, [53, 3000, 3730, 8080, 9000, 20128])
        self.assertEqual(excluded, [])
        self.assertEqual(host.ipv4_subnets(networks["int"]), ["172.30.0.0/16"])
        gatewayed = dict(networks, int=dict(networks["int"], ipam=[{"Subnet": "172.29.0.0/16", "Gateway": "172.29.0.1"}]))
        self.assertIn("172.29.0.1", host.probe_targets(gatewayed, self.SS, self.IP, own)[0])
        # An attempt container's own address is excluded and recorded by role, never refused.
        addresses, _, excluded = host.probe_targets(networks, self.SS, self.IP, dict(own, proxy_gw="192.0.2.20"))
        self.assertNotIn("192.0.2.20", addresses)
        self.assertEqual(excluded, ["proxy_gw"])
        addresses, _, excluded = host.probe_targets(networks, self.SS, self.IP, dict(own, proxy_gw="172.31.0.1"))
        self.assertEqual((excluded, "172.31.0.1" in addresses), (["proxy_gw"], False))
        for bad in ("LISTEN 0 4096 127.0.0.1:notaport 0.0.0.0:*\n", "garbage\n", "LISTEN 0 4096 127.0.0.1:70000 0.0.0.0:*\n"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                host.listener_ports(bad)
        with self.assertRaises(ValueError):
            host.probe_targets(dict(networks, int=dict(networks["int"], ipam=[])), self.SS, self.IP, own)
        for role in own:
            with self.subTest(role=role), self.assertRaises(ValueError):
                host.probe_targets(networks, self.SS, self.IP, dict(own, **{role: ""}))
        with self.assertRaises(ValueError):
            host.probe_targets(networks, self.SS, self.IP, {"server_int": "172.30.0.1"})

    def test_probe_containers_use_the_agent_image_hardening_and_only_their_mounts(self):
        host = load_recipe_module("host.py")
        prefix = self.state / "prefix"
        for role, network in (("gw", self.stem + "-gw"), ("int", self.stem + "-int")):
            with self.subTest(role=role):
                output = self.result / "probes" / role
                name, argv = host.probe_command(self.pins, prefix, self.stem, role, output, ["--upstream-port", "20128"])
                self.assertEqual(name, f"{self.stem}-probe-{role}")
                self.assertEqual(argv[:len(host.DOCKER) + 2], [*host.DOCKER, "run", "--rm"])
                for flag in ("--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pull=never",
                             "--network=" + network):
                    self.assertIn(flag, argv)
                self.assertEqual(argv[argv.index("--user") + 1], "10001:10001")
                mounts = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--mount"]
                self.assertEqual(mounts, [f"type=bind,src={prefix}/venv,dst={prefix}/venv,readonly",
                                          f"type=bind,src={host.HERE},dst=/recipe,readonly",
                                          f"type=bind,src={output},dst=/probe-output"])
                self.assertFalse(any(arg == "--publish" or arg.startswith(("-p", "--publish=", "--env-file"))
                                     for arg in argv))
                self.assertEqual(argv[argv.index("--entrypoint") + 1], f"{prefix}/venv/bin/python")
                tail = argv[argv.index(self.pins["image"]["ref"]):]
                self.assertEqual(tail, [self.pins["image"]["ref"], "/recipe/e2e/netprobe.py", role,
                                        "--out", "/probe-output/observations.json", "--upstream-port", "20128"])
        for role in ("server", "proxy", "gw-int"):
            with self.subTest(role=role), self.assertRaises(ValueError):
                host.probe_command(self.pins, prefix, self.stem, role, self.result, [])

    def views(self):
        """Selected-field inspect views (host.NETWORK_FORMAT, host.CONTAINER_FORMAT) of one attempt."""
        names = {role: f"{self.stem}-{role}" for role in ("int", "gw", "server", "proxy")}
        ids = {role: hashlib.sha256(name.encode()).hexdigest() for role, name in names.items()}

        def network(role, prefix, internal):
            # moby@464cd50c (docker-v29.8.1): gateway mode isolated allocates no gateway
            # (bridge_linux.go:700-713, network.go:1594-1602), so the first endpoint takes .1.
            ipam = {"Subnet": prefix + ".0.0/16"} if internal else {"Subnet": prefix + ".0.0/16", "Gateway": prefix + ".0.1"}
            return {"id": ids[role], "name": names[role], "driver": "bridge", "internal": internal, "ipv6": False,
                    "options": {self.ISOLATED: "isolated"} if internal else {}, "labels": dict(self.OWNER),
                    "ipam": [ipam]}

        def endpoint(role, address, aliases=None):
            return {"NetworkID": ids[role], "IPAddress": address, "Aliases": aliases}
        return {
            ("network", names["int"]): network("int", "172.30", True),
            ("network", names["gw"]): network("gw", "172.31", False),
            ("container", names["server"]): {
                "id": ids["server"], "name": "/" + names["server"], "running": True, "labels": dict(self.OWNER),
                "networks": {names["int"]: endpoint("int", "172.30.0.1")}},
            ("container", names["proxy"]): {
                "id": ids["proxy"], "name": "/" + names["proxy"], "running": True, "labels": dict(self.OWNER),
                "networks": {names["gw"]: endpoint("gw", "172.31.0.2"),
                             names["int"]: endpoint("int", "172.30.0.2", ["gw"])}},
        }

    def commands(self, host, views):
        """subprocess.check_output fake: selected-field inspects, ss and ip; nothing else."""
        templates = {"network": host.NETWORK_FORMAT, "container": host.CONTAINER_FORMAT}

        def check_output(argv, **kwargs):
            argv = list(argv)
            if argv[:len(host.DOCKER)] == host.DOCKER:
                kind, verb, flag, template, name = argv[len(host.DOCKER):]
                # Never a full inspect: the server's Config.Env holds the session key.
                self.assertEqual((verb, flag, template), ("inspect", "--format", templates[kind]))
                return json.dumps(views[(kind, name)])
            if argv == ["ss", "-ltnH"]:
                return self.SS
            if argv == ["ip", "-4", "-o", "addr"]:
                return self.IP
            raise AssertionError(argv)
        return check_output

    def prepared(self, port=3740):
        """A prepared attempt's host files, as host.prepare_native_dispatch writes them."""
        host = load_recipe_module("host.py")
        selection = load_recipe_module("recipe.py").arm_config(self.arm)
        _, sha = host.write_proxy_config(self.result, host.render_proxy_config(selection, self.run_id))
        (self.result / "status.json").write_text(json.dumps({
            "run_id": self.run_id, "arm": self.arm, "status": "prepared", "server_name": self.stem + "-server",
            "proxy_name": self.stem + "-proxy", "port": port, "proxy_config_sha256": sha}))
        self.stage_gates(host)
        return host

    def stage_gates(self, host, **changes):
        """<state>/stage-gates.json as the coordinator records it after live P3-P5, G2 and G5 (repair R6)."""
        when = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        probe = {"passed": True, "recorded_at": when, "gateway_build": "045aa81f3",
                 "proxy_image": self.pins["gateway_proxy"]["ref"],
                 "proxy_template_sha256": hashlib.sha256((RECIPE / "config/proxy-nginx.conf").read_bytes()).hexdigest()}
        gates = {"schema": "openhands-stage-gates-v1",
                 "g2": {ref: {"passed": True, "recorded_at": when}
                        for ref in (self.pins["image"]["ref"], self.pins["gateway_proxy"]["ref"])},
                 "probes": {name: dict(probe) for name in ("p3", "p4", "p5")},
                 "g5": {arm: {"passed": True, "recorded_at": when} for arm in ("control", "engines-on")}}
        gates.update(changes)
        host.write_private_json(self.state / "stage-gates.json", gates)
        return gates

    @staticmethod
    def option(argv, flag):
        return argv[argv.index(flag) + 1]

    def observations(self, netprobe, argv):
        """What netprobe writes when every result is the expected one."""
        mode = argv[argv.index("/recipe/e2e/netprobe.py") + 1]

        def record(item):
            host_name, port, method, target, status, route = item
            return {"host": host_name, "port": port, "method": method, "target": target,
                    "status": 200 if status is None else status, "route_class": route, "error": None}
        if mode == "gw":
            return {"probe": "netprobe-v1", "mode": mode,
                    "p0": [record(item) for item in netprobe.p0_expected(int(self.option(argv, "--upstream-port")))]}
        addresses = self.option(argv, "--addresses").split(",")
        ports = [int(port) for port in self.option(argv, "--ports").split(",")]
        return {"probe": "netprobe-v1", "mode": mode, "p1": [record(item) for item in netprobe.P1_EXPECTED],
                "p2": {"control": {"host": "gw", "port": 8081, "connected": True, "error": None},
                       "connects": [{"address": a, "port": p, "connected": False, "error": "ENETUNREACH"}
                                    for a in addresses for p in ports],
                       "udp": {"address": "10.0.2.3", "port": 53, "answered": False, "error": "ENETUNREACH"},
                       "dns": [{"name": name, "resolved": ok, "error": None if ok else "EAI_NONAME"}
                               for name, ok in netprobe.dns_expected(self.option(argv, "--server"))],
                       "ipv6": {"available": True, "loopback": 1, "non_loopback": 0, "link_local": 0},
                       "routes": {"available": True, "routes": 1, "default": 0, "gateway": 0}}}

    def probe(self, host, views=None, mutate=None, codes=None):
        """host.run_probe with the two probe containers faked through execute_container."""
        netprobe = load_recipe_module("e2e/netprobe.py")
        runs = []

        def execute(argv, name, logfile, timeout):
            runs.append((name, list(argv)))
            mounts = [dict(part.split("=", 1) for part in argv[i + 1].split(",") if "=" in part)
                      for i, arg in enumerate(argv) if arg == "--mount"]
            output = Path(next(m["src"] for m in mounts if m["dst"] == "/probe-output"))
            data = self.observations(netprobe, argv)
            if mutate:
                mutate(data)
            (output / "observations.json").write_text(json.dumps(data))
            return (codes or {}).get(data["mode"], 0)
        with patch.object(host.subprocess, "check_output", side_effect=self.commands(host, views or self.views())), \
                patch.object(host, "execute_container", side_effect=execute):
            passed = host.run_probe(self.state, self.run_id, self.arm, self.state / "prefix", self.pins)
        return passed, runs

    def gate(self, host, now, views=None):
        with patch.object(host.subprocess, "check_output", side_effect=self.commands(host, views or self.views())), \
                patch.dict(os.environ, {"OPENHANDS_HOST_FILE": str(self.host_file)}), \
                patch.object(host, "gateway_database", side_effect=lambda arm: self.stores[arm]):
            return host.verify_isolation(self.state, self.run_id, self.arm, 3740, now=now)

    def test_gate_runs_the_g5_provider_preflight_on_fixture_stores(self):
        # Repair R3: the provider surface is read at each start, before any Docker read.
        host = self.prepared()
        passed, _ = self.probe(host)
        self.assertTrue(passed)
        soon = host.time_value(json.loads((self.result / "isolation-probe.json").read_text())["verified_at"])
        soon += timedelta(seconds=60)
        self.gate(host, soon)
        gateway_store(self.state / "wider.sqlite", ["codex", "openai"])
        with patch.object(host, "attempt_bindings") as docker, self.assertRaisesRegex(
                ValueError, "gateway_provider_outside_allowlist"):
            self.stores["control"] = self.state / "wider.sqlite"
            self.gate(host, soon)
        docker.assert_not_called()
        self.stores["control"] = gateway_store(self.state / "unblocked.sqlite", ["codex"], blocked=["opencode"])
        with self.assertRaisesRegex(ValueError, "gateway_no_auth_provider_not_blocked"):
            self.gate(host, soon)
        self.stores["control"] = self.state / "omniroute.sqlite"
        with patch.dict(os.environ, {"OPENHANDS_HOST_FILE": ""}), \
                patch.object(host.subprocess, "check_output", side_effect=self.commands(host, self.views())), \
                patch.object(host, "gateway_database", side_effect=lambda arm: self.stores[arm]), \
                self.assertRaisesRegex(ValueError, "OPENHANDS_HOST_FILE_required"):
            host.verify_isolation(self.state, self.run_id, self.arm, 3740, now=soon)

    def test_probe_receipt_is_bound_owner_only_and_accepted_by_the_gate(self):
        host = self.prepared()
        previous = os.umask(0o022)
        self.addCleanup(os.umask, previous)
        passed, runs = self.probe(host)
        self.assertTrue(passed)
        path = self.result / "isolation-probe.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        receipt = json.loads(path.read_text())
        views = self.views()
        self.assertEqual({key: receipt[key] for key in (
            "mechanism", "run_id", "arm", "run_network_id", "gw_network_id", "server_container_id",
            "proxy_container_id", "proxy_image", "proxy_config_sha256", "probe_script_sha256", "upstream",
            "host_ingress", "exit_codes", "passed")}, {
            "mechanism": "internal-isolated+nginx-v1-allowlist", "run_id": self.run_id, "arm": self.arm,
            "run_network_id": views[("network", self.stem + "-int")]["id"],
            "gw_network_id": views[("network", self.stem + "-gw")]["id"],
            "server_container_id": views[("container", self.stem + "-server")]["id"],
            "proxy_container_id": views[("container", self.stem + "-proxy")]["id"],
            "proxy_image": self.pins["gateway_proxy"]["ref"],
            "proxy_config_sha256": hashlib.sha256((self.result / "proxy/nginx.conf").read_bytes()).hexdigest(),
            "probe_script_sha256": hashlib.sha256((RECIPE / "e2e/netprobe.py").read_bytes()).hexdigest(),
            "upstream": "10.0.2.2:20128", "host_ingress": "127.0.0.1:3740", "exit_codes": {"gw": 0, "int": 0},
            "passed": True})
        self.assertEqual((receipt["p0"]["requests"], receipt["p1"]["requests"]), (2, 27))
        self.assertEqual(receipt["targets"], {"addresses": 7, "ports": [53, 3000, 3730, 8080, 9000, 20128], "pairs": 42,
                                              "excluded": {}})
        self.assertEqual((receipt["p2"]["connects"], receipt["p2"]["connected"], receipt["p2"]["dns_matched"]), (42, 0, 5))
        self.assertEqual({key: receipt["p2"][key] for key in (
            "control_connected", "off_subnet", "off_subnet_unreachable", "udp_answered", "dns_errors",
            "routes_available", "default_routes", "gateway_routes")}, {
            "control_connected": True, "off_subnet": 42, "off_subnet_unreachable": 42, "udp_answered": False,
            "dns_errors": {"EAI_NONAME": 3}, "routes_available": True, "default_routes": 0, "gateway_routes": 0})
        self.assertTrue(all(receipt[section]["passed"] for section in ("p0", "p1", "p2")))
        for address in ("192.0.2.20", "172.30.0.1", "172.30.0.2", "172.31.0.2", "10.255.255.254", "172.30.0.0"):
            self.assertNotIn(address, path.read_text())
        # One container per network, each with an output directory of its own.
        self.assertEqual([name for name, _ in runs], [self.stem + "-probe-gw", self.stem + "-probe-int"])
        self.assertIn("--network=" + self.stem + "-gw", runs[0][1])
        self.assertIn("--network=" + self.stem + "-int", runs[1][1])
        outputs = [arg for _, argv in runs for arg in argv if "dst=/probe-output" in arg]
        self.assertEqual(len(set(outputs)), 2)
        self.assertEqual(self.option(runs[0][1], "--upstream-port"), "20128")
        self.assertEqual(self.option(runs[1][1], "--ports"), "53,3000,3730,8080,9000,20128")
        self.assertEqual(self.option(runs[1][1], "--server"), self.stem + "-server")
        self.assertEqual(self.option(runs[1][1], "--subnets"), "172.30.0.0/16")
        # The gate accepts the real writer's output while the live IDs match.
        verified = host.time_value(receipt["verified_at"])
        self.assertEqual(self.gate(host, verified + timedelta(seconds=900))["passed"], True)

    def test_gate_refuses_stale_future_mismatched_or_rebound_receipts(self):
        host = self.prepared()
        passed, _ = self.probe(host)
        self.assertTrue(passed)
        path = self.result / "isolation-probe.json"
        original = json.loads(path.read_text())
        verified = host.time_value(original["verified_at"])
        soon = verified + timedelta(seconds=60)
        self.gate(host, soon)
        rebound = self.views()
        new_id = hashlib.sha256(b"re-created network").hexdigest()
        rebound[("network", self.stem + "-int")]["id"] = new_id
        for key in (("container", self.stem + "-server"), ("container", self.stem + "-proxy")):
            rebound[key]["networks"][self.stem + "-int"]["NetworkID"] = new_id
        for label, now, views in (("901 s old", verified + timedelta(seconds=901), None),
                                  ("future-dated", verified - timedelta(seconds=1), None),
                                  ("re-created network", soon, rebound)):
            with self.subTest(label), self.assertRaises(ValueError):
                self.gate(host, now, views)
        p2, targets = original["p2"], original["targets"]
        for label, change in (("cross-arm upstream", {"upstream": "10.0.2.2:20129"}),
                              ("other arm", {"arm": "engines-on"}),
                              ("not passed", {"passed": False}),
                              ("p2 not passed", {"p2": dict(p2, passed=False)}),
                              ("other mechanism", {"mechanism": "docker-user-v1"}),
                              ("other ingress", {"host_ingress": "127.0.0.1:3730"}),
                              ("other probe script", {"probe_script_sha256": "0" * 64}),
                              ("other proxy image", {"proxy_image": "nginx:latest"}),
                              ("other server", {"server_container_id": "f" * 64}),
                              # The gate re-derives the verdict from the counts; passed flags alone are not trusted.
                              ("a connect succeeded", {"p2": dict(p2, connected=1)}),
                              ("no observations", {"p2": dict(p2, connects=0, observed=0, errors={}),
                                                   "targets": dict(targets, addresses=0, pairs=0)}),
                              ("probe exit code", {"exit_codes": {"gw": 0, "int": 1}}),
                              ("probe exit code missing", {"exit_codes": {"gw": 0}}),
                              ("p0 unobserved", {"p0": {"passed": True}}),
                              ("p1 short", {"p1": dict(original["p1"], observed=26, matched=26)}),
                              ("pairs inconsistent", {"targets": dict(targets, pairs=1)}),
                              ("connects short", {"p2": dict(p2, observed=41)}),
                              ("errors do not cover every connect", {"p2": dict(p2, errors={"ENETUNREACH": 1})}),
                              ("an off-subnet connect timed out", {"p2": dict(p2, off_subnet_unreachable=41)}),
                              ("nothing off-subnet", {"p2": dict(p2, off_subnet=0, off_subnet_unreachable=0)}),
                              ("positive control failed", {"p2": dict(p2, control_connected=False)}),
                              ("udp answered", {"p2": dict(p2, udp_answered=True)}),
                              ("dns short", {"p2": dict(p2, dns_matched=4)}),
                              ("ipv6 present", {"p2": dict(p2, ipv6_non_loopback=1)}),
                              ("default route", {"p2": dict(p2, default_routes=1)}),
                              ("gateway route", {"p2": dict(p2, gateway_routes=1)}),
                              ("route table unread", {"p2": dict(p2, routes_available=False)})):
            with self.subTest(label):
                host.write_private_json(path, {**original, **change})
                with self.assertRaises(ValueError):
                    self.gate(host, soon)
        host.write_private_json(path, original)
        self.gate(host, soon)
        config = self.result / "proxy/nginx.conf"
        saved = config.read_text()
        config.write_text(saved + "# changed\n")
        with self.assertRaises(ValueError):
            self.gate(host, soon)
        config.write_text(saved)
        status = json.loads((self.result / "status.json").read_text())
        (self.result / "status.json").write_text(json.dumps({**status, "proxy_config_sha256": "0" * 64}))
        with self.assertRaises(ValueError):
            self.gate(host, soon)
        (self.result / "status.json").write_text(json.dumps(status))
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            self.gate(host, soon)
        path.unlink()
        with self.assertRaises(OSError):
            self.gate(host, soon)

    def test_gate_requires_the_host_recorded_stage_gates(self):
        # Repair R6 (plan G7's P3 half, G2 and G5): a host-owned file the coordinator records live.
        host = self.prepared()
        passed, _ = self.probe(host)
        self.assertTrue(passed)
        soon = host.time_value(json.loads((self.result / "isolation-probe.json").read_text())["verified_at"])
        soon += timedelta(seconds=60)
        self.gate(host, soon)
        gates = json.loads((self.state / "stage-gates.json").read_text())
        agent, proxy = self.pins["image"]["ref"], self.pins["gateway_proxy"]["ref"]
        later = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        def probe(**change):
            return dict(gates, probes={**gates["probes"], "p3": dict(gates["probes"]["p3"], **change)})
        cases = (("other schema", dict(gates, schema="openhands-stage-gates-v0")),
                 ("agent image not scanned", dict(gates, g2={proxy: gates["g2"][proxy]})),
                 ("proxy scan not passed", dict(gates, g2={**gates["g2"], proxy: {"passed": False,
                                                                                  "recorded_at": gates["g2"][proxy]["recorded_at"]}})),
                 ("scan recorded in the future", dict(gates, g2={**gates["g2"], agent: {"passed": True, "recorded_at": later}})),
                 ("p3 not passed", probe(passed=False)),
                 ("p3 under another proxy template", probe(proxy_template_sha256="0" * 64)),
                 ("p3 under another proxy image", probe(proxy_image="nginx:latest")),
                 ("p3 recorded in the future", probe(recorded_at=later)),
                 ("p3 without a gateway build", probe(gateway_build="main")),
                 ("p3 absent", dict(gates, probes={"p4": gates["probes"]["p4"], "p5": gates["probes"]["p5"]})),
                 ("g5 for the other arm only", dict(gates, g5={"engines-on": gates["g5"]["engines-on"]})),
                 ("not an object", []))
        for label, value in cases:
            with self.subTest(label):
                host.write_private_json(self.state / "stage-gates.json", value)
                with self.assertRaises(ValueError):
                    self.gate(host, soon)
        # P4 and P5 bind only the engines-on arm.
        host.write_private_json(self.state / "stage-gates.json", dict(gates, probes={"p3": gates["probes"]["p3"]}))
        self.gate(host, soon)
        with self.assertRaises(ValueError):
            host.verify_stage_gates(self.state, "engines-on", now=soon)
        host.write_private_json(self.state / "stage-gates.json", gates)
        self.assertEqual(host.verify_stage_gates(self.state, "engines-on", now=soon), gates)
        # Owner-only and present, or refused.
        (self.state / "stage-gates.json").chmod(0o644)
        with self.assertRaises(ValueError):
            self.gate(host, soon)
        (self.state / "stage-gates.json").unlink()
        with self.assertRaisesRegex(ValueError, "stage_gates_not_recorded"):
            self.gate(host, soon)
        # The recipe only reads the file; the resolver PR's live run records it.
        self.assertEqual(host.STAGE_GATES, "stage-gates.json")
        for source in RECIPE.rglob("*.py"):
            with self.subTest(source=source.name):
                self.assertNotRegex(source.read_text(),
                                    r"(?:write\w*|open|replace|rename|touch)\([^)\n]*(?:STAGE_GATES|stage-gates)")

    def test_any_unexpected_observation_fails_the_probe_and_the_gate(self):
        host = self.prepared()

        def inside(change):
            return lambda data: change(data) if data["mode"] == "int" else None
        cases = (
            ("host port reachable", inside(lambda d: d["p2"]["connects"][5].update(connected=True)), None),
            ("denied path forwarded", inside(lambda d: d["p1"][3].update(status=404)), None),
            ("management answered", inside(lambda d: d["p1"][2].update(route_class="MANAGEMENT")), None),
            ("public name resolved", inside(lambda d: d["p2"]["dns"][0].update(resolved=True)), None),
            ("server unresolvable", inside(lambda d: d["p2"]["dns"][4].update(resolved=False)), None),
            ("ipv6 link-local", inside(lambda d: d["p2"]["ipv6"].update(non_loopback=1, link_local=1)), None),
            ("truncated connects", inside(lambda d: d["p2"]["connects"].pop()), None),
            ("reordered denied list", inside(lambda d: d["p1"].reverse()), None),
            ("probe exit code", None, {"int": 1}),
            ("off-subnet connect timed out", inside(lambda d: d["p2"]["connects"][0].update(error="timeout")), None),
            ("default route", inside(lambda d: d["p2"]["routes"].update(default=1, gateway=1)), None),
            ("gateway route", inside(lambda d: d["p2"]["routes"].update(gateway=1)), None),
            ("route table unread", inside(lambda d: d["p2"]["routes"].update(available=False)), None),
            ("positive control refused", inside(lambda d: d["p2"]["control"].update(connected=False)), None),
            ("positive control missing", inside(lambda d: d["p2"].pop("control")), None),
            ("udp answered", inside(lambda d: d["p2"]["udp"].update(answered=True, error=None)), None),
            ("udp timed out", inside(lambda d: d["p2"]["udp"].update(error="timeout")), None),
        )
        for label, mutate, codes in cases:
            with self.subTest(label):
                passed, runs = self.probe(host, mutate=mutate, codes=codes)
                self.assertFalse(passed)
                self.assertEqual(len(runs), 2)
                receipt = json.loads((self.result / "isolation-probe.json").read_text())
                self.assertFalse(receipt["passed"])
                with self.assertRaises(ValueError):
                    self.gate(host, host.time_value(receipt["verified_at"]))
        # A blind negative control stops before the internal probe runs.
        blind = lambda data: data["p0"][1].update(route_class=None) if data["mode"] == "gw" else None
        passed, runs = self.probe(host, mutate=blind)
        self.assertFalse(passed)
        self.assertEqual([name for name, _ in runs], [self.stem + "-probe-gw"])
        receipt = json.loads((self.result / "isolation-probe.json").read_text())
        self.assertEqual((receipt["p0"]["passed"], receipt["p1"]["observed"], receipt["exit_codes"]["int"]),
                         (False, 0, None))

    def test_probe_excludes_and_records_its_own_attempt_containers(self):
        # Repair R2: in isolated mode the server holds 172.30.0.1, which is no target
        # and never a refusal.
        host = self.prepared()
        views = self.views()
        self.assertEqual(views[("container", self.stem + "-server")]["networks"][self.stem + "-int"]["IPAddress"],
                         "172.30.0.1")
        passed, runs = self.probe(host, views=views)
        self.assertTrue(passed)
        self.assertNotIn("172.30.0.1", self.option(runs[1][1], "--addresses").split(","))
        # A host address that an attempt container also holds is excluded and recorded by role.
        views[("container", self.stem + "-proxy")]["networks"][self.stem + "-gw"]["IPAddress"] = "192.0.2.20"
        passed, runs = self.probe(host, views=views)
        self.assertTrue(passed)
        self.assertNotIn("192.0.2.20", self.option(runs[1][1], "--addresses").split(","))
        path = self.result / "isolation-probe.json"
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["targets"], {"addresses": 6, "ports": [53, 3000, 3730, 8080, 9000, 20128],
                                              "pairs": 36, "excluded": {"proxy_gw": 1}})
        self.assertNotIn("192.0.2.20", path.read_text())
        # A container with no address on its own network breaks the live contract.
        views[("container", self.stem + "-server")]["networks"][self.stem + "-int"]["IPAddress"] = ""
        with patch.object(host.subprocess, "check_output", side_effect=self.commands(host, views)), \
                patch.object(host, "execute_container") as execute, self.assertRaises(ValueError):
            host.run_probe(self.state, self.run_id, self.arm, self.state / "prefix", self.pins)
        execute.assert_not_called()

    def test_probe_requires_each_attempt_container_on_its_own_networks(self):
        host = self.prepared()
        server, proxy = ("container", self.stem + "-server"), ("container", self.stem + "-proxy")
        internal, gateway = self.stem + "-int", self.stem + "-gw"
        cases = (
            ("proxy lacks the gw alias", proxy, lambda v: v["networks"][internal].update(Aliases=["other"])),
            ("server also on the gateway network", server,
             lambda v: v["networks"].update({gateway: {"NetworkID": "e" * 64, "IPAddress": "172.31.0.9"}})),
            ("proxy not on the internal network", proxy, lambda v: v["networks"].pop(internal)),
            ("server stopped", server, lambda v: v.update(running=False)),
            ("proxy unlabelled", proxy, lambda v: v.update(labels={})),
            ("other name", server, lambda v: v.update(name="/other")),
            ("endpoint on another network", server, lambda v: v["networks"][internal].update(NetworkID="f" * 64)),
            ("short id", proxy, lambda v: v.update(id="abc")),
        )
        for label, key, update in cases:
            with self.subTest(label):
                views = self.views()
                update(views[key])
                with patch.object(host.subprocess, "check_output", side_effect=self.commands(host, views)), \
                        patch.object(host, "execute_container") as execute, self.assertRaises(ValueError):
                    host.run_probe(self.state, self.run_id, self.arm, self.state / "prefix", self.pins)
                execute.assert_not_called()
        # moby@464cd50c api/swagger.yaml:5637-5643: the name "may be" prefixed with "/".
        views = self.views()
        views[server]["name"] = self.stem + "-server"
        self.assertTrue(self.probe(host, views=views)[0])
        # Only a prepared attempt is probed.
        status = json.loads((self.result / "status.json").read_text())
        (self.result / "status.json").write_text(json.dumps({**status, "status": "running"}))
        with patch.object(host.subprocess, "check_output") as docker, self.assertRaises(ValueError):
            host.run_probe(self.state, self.run_id, self.arm, self.state / "prefix", self.pins)
        docker.assert_not_called()

    def test_probe_action_needs_an_explicit_prepared_attempt(self):
        host = load_recipe_module("host.py")
        output = io.StringIO()
        (self.result / "status.json").write_text(json.dumps({"run_id": self.run_id, "arm": self.arm, "status": "running"}))
        with patch.object(host, "run_probe") as probe, patch.object(host, "teardown_attempt") as teardown, \
                patch.object(host, "preflight") as preflight, contextlib.redirect_stdout(output):
            self.assertEqual(host.probe_action(self.state / "prefix", self.state, None, self.arm), 3)
            self.assertEqual(host.probe_action(self.state / "prefix", self.state, "rw-openhands-absent", self.arm), 3)
            self.assertEqual(host.probe_action(self.state / "prefix", self.state, self.run_id, self.arm), 3)
        probe.assert_not_called()
        teardown.assert_not_called()
        preflight.assert_not_called()
        self.assertEqual(json.loads((self.result / "status.json").read_text())["status"], "running")
        self.assertFalse((self.state / "runs" / "rw-openhands-absent").exists())
        self.assertEqual([json.loads(line)["failure_stage"] for line in output.getvalue().splitlines()],
                         ["preflight", "probe", "probe"])
        args = host.build_parser().parse_args(["probe", "--prefix", "/p", "--state", "/s", "--run-id", self.run_id])
        self.assertEqual((args.action, args.run_id), ("probe", self.run_id))

    def test_probe_action_failure_tears_down_and_records_the_probe_stage(self):
        host = self.prepared()
        status = json.loads((self.result / "status.json").read_text())
        (self.result / "window.json").write_text(json.dumps({
            "run_id": self.run_id, "arm": self.arm, "started_at": "2026-09-28T18:00:00Z", "finished_at": None}))
        (self.result / "check.json").write_text(json.dumps({"upstream_resolved": None, "grader_exit_code": None}))
        receipts = load_recipe_module("receipt.py")
        for label, outcome in (("passed", {"return_value": True}), ("failed", {"return_value": False}),
                               ("raised", {"side_effect": ValueError("attempt_container_contract_mismatch")})):
            with self.subTest(label):
                (self.result / "status.json").write_text(json.dumps(status))
                with patch.object(host, "preflight", return_value=(self.pins, {}, {})), \
                        patch.object(host, "run_probe", **outcome) as probe, \
                        patch.object(host, "teardown_attempt", return_value=True) as teardown, \
                        patch.object(host, "create_receipt", side_effect=lambda result: receipts.create_receipt(
                            result, database=result / "absent.sqlite")), \
                        contextlib.redirect_stdout(io.StringIO()):
                    code = host.probe_action(self.state / "prefix", self.state, self.run_id, self.arm)
                probe.assert_called_once_with(self.state, self.run_id, self.arm, self.state / "prefix", self.pins)
                current = json.loads((self.result / "status.json").read_text())
                if label == "passed":
                    self.assertEqual(code, 0)
                    teardown.assert_not_called()
                    self.assertEqual(current, status)
                    continue
                self.assertEqual(code, 3)
                teardown.assert_called_once_with(self.state, self.run_id, self.arm)
                self.assertEqual((current["status"], current["failure_stage"]), ("failed", "probe"))
                self.assertEqual(json.loads((self.result / "receipt.json").read_text())["failure_stage"], "probe")

    def test_teardown_action_refuses_while_a_conversation_may_be_live(self):
        host = self.prepared()
        status = json.loads((self.result / "status.json").read_text())
        lock = self.state / "active-dispatch.json"
        linked = self.state / "runs" / "rw-openhands-linked"
        linked.mkdir()
        (linked / self.arm).symlink_to(self.result, target_is_directory=True)
        cases = [(self.run_id, json.dumps({**status, "status": value}), None)
                 for value in ("starting", "running", "terminal")]
        cases += [(self.run_id, json.dumps(status), json.dumps({"run_id": self.run_id, "arm": self.arm})),
                  (self.run_id, json.dumps(status), "{not json"),
                  (self.run_id, "{not json", None),
                  (self.run_id, json.dumps(["prepared"]), None),
                  ("rw-openhands-absent", json.dumps(status), None),
                  ("rw-openhands-linked", json.dumps(status), None),
                  ("not-an-owned-run", json.dumps(status), None)]
        for run_id, text, reservation in cases:
            with self.subTest(run_id=run_id, status=text, reservation=reservation):
                (self.result / "status.json").write_text(text)
                lock.unlink(missing_ok=True)
                if reservation is not None:
                    lock.write_text(reservation)
                output = io.StringIO()
                with patch.object(host, "teardown_attempt") as teardown, patch.object(host.subprocess, "run") as run, \
                        patch.object(host.subprocess, "check_output") as check_output, contextlib.redirect_stdout(output):
                    self.assertEqual(host.teardown_action(self.state, run_id, self.arm), 3)
                teardown.assert_not_called()
                run.assert_not_called()
                check_output.assert_not_called()
                self.assertEqual((self.result / "status.json").read_text(), text)
                self.assertEqual(json.loads(output.getvalue())["teardown"], "refused")
        self.assertFalse((self.state / "runs" / "rw-openhands-absent").exists())

    def test_teardown_action_removes_the_attempt_once_and_retires_a_prepared_status(self):
        host = self.prepared()
        status = json.loads((self.result / "status.json").read_text())
        dispatch = load_recipe_module("dispatch.py")
        path = self.result / "status.json"
        (self.result / "window.json").write_text(json.dumps({"run_id": self.run_id, "arm": self.arm}))
        # Another attempt's serial reservation does not block this teardown.
        (self.state / "active-dispatch.json").write_text(json.dumps({"run_id": "rw-openhands-other", "arm": self.arm}))
        for label, before, outcome, code, after in (
                ("confirmed", status, {"return_value": True}, 0, "torn_down"),
                ("unconfirmed", status, {"return_value": False}, 3, "torn_down"),
                ("raised", status, {"side_effect": subprocess.SubprocessError()}, 3, "torn_down"),
                ("failed attempt", {**status, "status": "failed", "failure_stage": "probe"},
                 {"return_value": True}, 0, "failed"),
                ("repeat", {**status, "status": "torn_down"}, {"return_value": True}, 0, "torn_down"),
                ("no status", None, {"return_value": True}, 0, None)):
            with self.subTest(label):
                path.unlink(missing_ok=True)
                if before is not None:
                    path.write_text(json.dumps(before))
                output = io.StringIO()
                with patch.object(host, "teardown_attempt", **outcome) as teardown, contextlib.redirect_stdout(output):
                    self.assertEqual(host.teardown_action(self.state, self.run_id, self.arm), code)
                teardown.assert_called_once_with(self.state, self.run_id, self.arm)
                self.assertEqual(json.loads(output.getvalue())["teardown"], "confirmed" if code == 0 else "unconfirmed")
                if after is None:
                    self.assertFalse(path.exists())
                    continue
                self.assertEqual(json.loads(path.read_text()), {**before, "status": after})
        # A retired attempt can neither start a conversation nor refresh its probe.
        path.write_text(json.dumps({**status, "status": "torn_down"}))
        with patch.object(dispatch, "verify_isolation") as gate, patch.object(host, "run_probe") as probe, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.execute("start", self.state, self.run_id, self.arm), 3)
            self.assertEqual(host.probe_action(self.state / "prefix", self.state, self.run_id, self.arm), 3)
        gate.assert_not_called()
        probe.assert_not_called()
        args = host.build_parser().parse_args(["teardown", "--prefix", "/p", "--state", "/s", "--run-id", self.run_id])
        self.assertEqual((args.action, args.run_id), ("teardown", self.run_id))


class OpenHandsGatewaySurfaceTests(unittest.TestCase):
    """Plan G5 (repair R3): each arm's provider surface from fixture OmniRoute stores.

    Our integration checks on synthetic sqlite files, never the live stores.
    """
    ALLOWLISTS = {"control": ("codex",), "engines-on": ("openai-compatible-responses-*",)}

    def setUp(self):
        self.host = load_recipe_module("host.py")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_provider_lists_are_the_omniroute_source_lists(self):
        self.assertEqual(self.host.NO_AUTH_PROVIDERS, NO_AUTH_PROVIDERS)
        self.assertEqual(self.host.ANONYMOUS_FALLBACK_PROVIDERS, ANONYMOUS_FALLBACK_PROVIDERS)
        self.assertEqual(self.host.GATEWAY_CHAIN, {"control": ("control",), "engines-on": ("engines-on", "control")})

    def test_surface_reads_only_the_provider_column_combo_count_and_two_settings_keys(self):
        path = gateway_store(self.root / "store.sqlite", ["codex", "codex", ENGINES_NODE], combos=2,
                             blocked=["zc", "opencode"], fallback=["kc"])
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        statements, real = [], sqlite3.connect

        def traced(*args, **kwargs):
            connection = real(*args, **kwargs)
            connection.set_trace_callback(statements.append)
            return connection
        with patch.object(self.host.sqlite3, "connect", side_effect=traced) as connect:
            surface = self.host.gateway_surface(path)
        self.assertEqual(connect.call_args.args[0], path.as_uri() + "?mode=ro")
        self.assertIs(connect.call_args.kwargs["uri"], True)
        self.assertEqual(statements, [
            "PRAGMA query_only = ON",
            "SELECT provider FROM provider_connections",
            "SELECT count(*) FROM combos",
            "SELECT value FROM key_value WHERE namespace = 'settings' AND key = 'blockedProviders'",
            "SELECT value FROM key_value WHERE namespace = 'settings' AND key = 'noAuthFallbackDisabledProviders'"])
        self.assertEqual(surface, {"providers": ["codex", ENGINES_NODE], "combos": 2,
                                   "blockedProviders": ["opencode", "zc"], "noAuthFallbackDisabledProviders": ["kc"]})
        text = json.dumps(surface)
        for secret in GATEWAY_SECRETS:
            self.assertNotIn(secret, text)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        for bad in (self.root / "absent.sqlite",):
            with self.assertRaises(ValueError):
                self.host.gateway_surface(bad)
        link = self.root / "link.sqlite"
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            self.host.gateway_surface(link)
        # A store without the combos table is refused rather than read as empty.
        bare = gateway_store(self.root / "bare.sqlite", ["codex"], tables="""
            CREATE TABLE provider_connections (id TEXT PRIMARY KEY, provider TEXT NOT NULL, auth_type TEXT,
              access_token TEXT, refresh_token TEXT, api_key TEXT, id_token TEXT, provider_specific_data TEXT,
              is_active INTEGER);
            CREATE TABLE key_value (namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
              PRIMARY KEY (namespace, key));""")
        with self.assertRaises(sqlite3.Error):
            self.host.gateway_surface(bare)

    def test_provider_allowlist_refuses_every_other_served_provider(self):
        check = self.host.check_gateway_surface
        control, engines = self.ALLOWLISTS["control"], self.ALLOWLISTS["engines-on"]

        def surface(providers, **options):
            return self.host.gateway_surface(gateway_store(self.root / (uuid.uuid4().hex + ".sqlite"),
                                                           providers, **options))
        self.assertEqual(check(surface(["codex"] * 6), control), {"providers": 1, "combos": 0})
        self.assertEqual(check(surface([ENGINES_NODE]), engines), {"providers": 1, "combos": 0})
        # Blocking by alias is enough (OmniRoute noAuthProviders.ts isProviderBlockedByIdOrAlias).
        self.assertEqual(check(surface(["codex"], blocked=list(NO_AUTH_PROVIDERS.values()),
                                       fallback=list(ANONYMOUS_FALLBACK_PROVIDERS.values())), control)["combos"], 0)
        refusals = (
            ("other provider row", surface(["codex", "openai"]), control, "gateway_provider_outside_allowlist"),
            ("chat node on engines-on", surface(["openai-compatible-chat-x"]), engines,
             "gateway_provider_outside_allowlist"),
            ("codex on engines-on", surface(["codex"]), engines, "gateway_provider_outside_allowlist"),
            ("routing combo", surface(["codex"], combos=1), control, "gateway_routing_combo_refused"),
            ("subprocess no-auth provider open", surface(["codex"], blocked=[p for p in NO_AUTH_PROVIDERS if p != "zcode"]),
             control, "gateway_no_auth_provider_not_blocked"),
            ("no-auth settings absent", surface(["codex"], blocked=None), control,
             "gateway_no_auth_provider_not_blocked"),
            ("no-auth settings not a list", surface(["codex"], blocked=None, settings={"blockedProviders": "{}"}),
             control, "gateway_no_auth_provider_not_blocked"),
            ("no-auth settings not JSON", surface(["codex"], blocked=None, settings={"blockedProviders": "zcode"}),
             control, "gateway_no_auth_provider_not_blocked"),
            ("anonymous fallback open", surface(["codex"], fallback=["opencode-zen", "opencode-go", "pol"]),
             control, "gateway_anonymous_fallback_not_disabled"),
            ("anonymous fallback blocked but not disabled",
             surface(["codex"], blocked=[*NO_AUTH_PROVIDERS, *ANONYMOUS_FALLBACK_PROVIDERS], fallback=[]),
             control, "gateway_anonymous_fallback_not_disabled"),
        )
        for label, value, allowed, reason in refusals:
            with self.subTest(label), self.assertRaisesRegex(ValueError, reason):
                check(value, allowed)

    def test_engines_on_also_checks_the_control_store_it_forwards_to(self):
        stores = {"control": gateway_store(self.root / "control.sqlite", ["codex"] * 6),
                  "engines-on": gateway_store(self.root / "fw.sqlite", [ENGINES_NODE])}
        read = []

        def database(arm):
            read.append(arm)
            return stores[arm]
        with patch.object(self.host, "gateway_database", side_effect=database):
            self.host.verify_gateway_providers("engines-on", self.ALLOWLISTS)
            self.assertEqual(read, ["engines-on", "control"])
            read.clear()
            self.host.verify_gateway_providers("control", self.ALLOWLISTS)
            self.assertEqual(read, ["control"])
            stores["control"] = gateway_store(self.root / "wider.sqlite", ["codex", "openrouter"])
            for arm in ("control", "engines-on"):
                with self.subTest(arm=arm), self.assertRaisesRegex(ValueError, "gateway_provider_outside_allowlist"):
                    self.host.verify_gateway_providers(arm, self.ALLOWLISTS)

    def test_host_file_allowlists_are_exact_arms_and_bounded_patterns(self):
        template = json.loads((RECIPE / "config/host.example.json").read_text())
        self.assertEqual(self.host.gateway_allowlists(template), self.ALLOWLISTS)
        for bad in ({}, {"control": ["codex"]}, {"control": ["codex"], "engines-on": []},
                    {"control": ["*"], "engines-on": ["openai-compatible-responses-*"]},
                    {"control": ["co*dex"], "engines-on": ["openai-compatible-responses-*"]},
                    {"control": ["codex"], "engines-on": ["openai-compatible-responses-*"], "other": ["x"]},
                    {"control": "codex", "engines-on": ["openai-compatible-responses-*"]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.host.gateway_allowlists({"gateway_providers": bad})
        path = self.root / "host.json"
        path.write_text(json.dumps({"gateway_providers": {"control": ["codex"],
                                                          "engines-on": ["openai-compatible-responses-*"]}}))
        for mode, expected in ((0o600, None), (0o644, "private_host_file_requires_mode_0600")):
            path.chmod(mode)
            with self.subTest(mode=oct(mode)), patch.dict(os.environ, {"OPENHANDS_HOST_FILE": str(path)}):
                if expected:
                    with self.assertRaisesRegex(ValueError, expected):
                        self.host.read_host_file()
                else:
                    self.assertIn("gateway_providers", self.host.read_host_file())


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

    def test_responses_rows_keep_window_attribution_because_the_gateway_replaces_caller_ids(self):
        # Repair R5, source-checked. At OmniRoute@045aa81f3 and @dd6e9607e the
        # /v1/responses route hands handleChat a fresh randomUUID
        # (src/app/api/v1/responses/route.ts:193,213; src/shared/utils/requestId.ts:100-102),
        # and call_logs.correlation_id records it (chatCore/attemptLogging.ts:611).
        # The proxy's fixed run id never reaches that column, so filtering on it
        # would turn this attempt's usage into a false empty window.
        module = load_recipe_module("receipt.py")
        # Built at runtime, like the gateway's own IDs (publication identifier policy).
        generated = (str(uuid.uuid4()), str(uuid.uuid4()))
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp).resolve()
            db = result / "fixture.sqlite"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE call_logs (timestamp, path, status, model, reasoning_effort_requested, reasoning_effort_upstream, tokens_in, tokens_cache_read, tokens_reasoning, correlation_id)")
            connection.executemany("INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                ("2026-09-28T18:00:01Z", "/v1/responses", 200, "gpt-6-astra-max", "max", "max", 30, 20, 4, generated[0]),
                ("2026-09-28T18:00:02Z", "/v1/responses", 200, "gpt-6-astra-max", None, None, 10, 0, 0, generated[1])))
            connection.commit()
            connection.close()
            (result / "check.json").write_text("{}")
            (result / "window.json").write_text(json.dumps({
                "arm": "control", "run_id": "rw-openhands-fixture", "instance_id": "django__django-11333",
                "started_at": "2026-09-28T18:00:00Z", "finished_at": "2026-09-28T18:00:03Z"}))
            gateway = module.create_receipt(result, database=db)["gateway"]
        self.assertEqual(gateway["status"], "observed")
        self.assertEqual(len(gateway["rows"]), 2)
        self.assertEqual(gateway["totals"], {"tokens_in": 40, "tokens_cache_read": 20, "tokens_reasoning": 4})
        for phrase in ("/v1/responses", "gateway-generated", "concurrent callers"):
            self.assertIn(phrase, gateway["attribution"])
        self.assertFalse(any(value in json.dumps(gateway) for value in generated))

    def test_skills_and_mcp_require_observations(self):
        # Phase 2 disables the unreachable host services in the policy, so the
        # fixture uses a container-local server the native filter still admits.
        module = load_recipe_module("receipt.py")
        action = {"kind": "ActionEvent", "tool_name": "jcodemunch_order"}
        observed = {"kind": "ObservationEvent", "tool_name": "jcodemunch_order", "observation": {"is_error": False}}
        disabled = {"kind": "ObservationEvent", "tool_name": "ai-memory_memory_query", "observation": {"is_error": False}}
        skill = {"kind": "ObservationEvent", "tool_name": "invoke_skill", "observation": {"skill_name": "tdd", "is_error": False}}
        self.assertEqual(module.observations([action])["mcp_calls_observed"], {})
        report = module.observations([action, observed, disabled, skill], ["tdd"])
        self.assertEqual(report["mcp_calls_observed"], {"jcodemunch_order": 1})
        self.assertEqual(report["skills_observed"], {"tdd": 1})

    def test_receipt_records_proxy_base_url_and_selected_compression_combo(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp).resolve()
            (result / "check.json").write_text("{}")
            for window, combo, port in (({"arm": "engines-on", "compression_combo": "fw-rtk"}, "fw-rtk", 20129),
                                        ({"arm": "engines-on"}, "allow-lossy", 20129),
                                        ({"arm": "control"}, None, 20128)):
                with self.subTest(window=window):
                    (result / "window.json").write_text(json.dumps({
                        **window, "base_url": "http://gw:8081/v1",
                        "started_at": "2026-09-28T18:00:00Z", "finished_at": "2026-09-28T18:00:01Z"}))
                    receipt = module.create_receipt(result, database=result / "absent.sqlite")
                    self.assertEqual(receipt["schema_version"], 7)
                    self.assertEqual(receipt["base_url"], "http://gw:8081/v1")
                    self.assertEqual(receipt["gateway_upstream"], f"http://10.0.2.2:{port}/v1")
                    self.assertEqual(receipt["compression_combo"], combo)
                    self.assertEqual(receipt["gateway"]["entry_port"], port)

    def test_receipt_counts_network_removal_separately_from_containers(self):
        module = load_recipe_module("receipt.py")
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp).resolve()
            (result / "check.json").write_text("{}")
            (result / "window.json").write_text(json.dumps({
                "started_at": "2026-09-28T18:00:00Z", "finished_at": "2026-09-28T18:00:01Z"}))
            for name, removed in (("server.log.cleanup.json", True), ("proxy.log.cleanup.json", True),
                                  ("network-int.cleanup.json", True), ("network-gw.cleanup.json", False)):
                (result / name).write_text(json.dumps({"confirmed_removed": removed, "error_type": None}))
            receipt = module.create_receipt(result, database=result / "absent.sqlite")
        self.assertEqual(receipt["container_cleanup"], {"attempts": 2, "confirmed_removed": 2, "complete": True})
        self.assertEqual(receipt["network_cleanup"], {"attempts": 2, "confirmed_removed": 1, "complete": False})

    def test_receipt_summarizes_the_isolation_probe_without_ids_or_addresses(self):
        module = load_recipe_module("receipt.py")
        ids = {key: hashlib.sha256(key.encode()).hexdigest()
               for key in ("run_network_id", "gw_network_id", "server_container_id", "proxy_container_id")}
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp).resolve()
            (result / "check.json").write_text("{}")
            (result / "window.json").write_text(json.dumps({
                "arm": "control", "failure_stage": "probe",
                "started_at": "2026-09-28T18:00:00Z", "finished_at": "2026-09-28T18:00:01Z"}))
            receipt = module.create_receipt(result, database=result / "absent.sqlite")
            self.assertEqual(receipt["failure_stage"], "probe")
            self.assertEqual(receipt["isolation"], {"status": "absent"})
            probe = {"mechanism": "internal-isolated+nginx-v1-allowlist", **ids, "run_id": "rw-openhands-fixture",
                     "verified_at": "2026-09-28T17:59:00.000Z", "passed": True, "upstream": "10.0.2.2:20128",
                     "host_ingress": "127.0.0.1:3730", "exit_codes": {"gw": 0, "int": 0},
                     "p0": {"requests": 2, "observed": 2, "matched": 2, "passed": True},
                     "p1": {"requests": 27, "observed": 27, "matched": 27, "passed": True},
                     "p2": {"control_connected": True, "connects": 16, "observed": 16, "connected": 0,
                            "errors": {"ENETUNREACH": 16}, "off_subnet": 16, "off_subnet_unreachable": 16,
                            "udp_answered": False, "udp_errors": {"ENETUNREACH": 1}, "dns": 5, "dns_matched": 5,
                            "dns_errors": {"EAI_AGAIN": 3}, "ipv6_non_loopback": 0, "ipv6_link_local": 0,
                            "ipv6_loopback": 1, "routes_available": True, "routes": 1, "default_routes": 0,
                            "gateway_routes": 0, "passed": True},
                     "targets": {"addresses": 8, "ports": [53, 20128], "pairs": 16, "excluded": {"proxy_gw": 1}}}
            (result / "isolation-probe.json").write_text(json.dumps(probe))
            (result / "probes/probe-fixture").mkdir(parents=True)
            (result / "probes/probe-fixture/gw.log.cleanup.json").write_text(
                json.dumps({"confirmed_removed": True, "error_type": None}))
            receipt = module.create_receipt(result, database=result / "absent.sqlite")
        self.assertEqual(receipt["isolation"], {
            "status": "observed", "mechanism": "internal-isolated+nginx-v1-allowlist",
            "verified_at": "2026-09-28T17:59:00.000Z", "passed": True, "exit_codes": {"gw": 0, "int": 0},
            "p0": probe["p0"], "p1": probe["p1"], "p2": probe["p2"], "targets": probe["targets"]})
        text = json.dumps(receipt)
        for value in ids.values():
            self.assertNotIn(value, text)
        self.assertNotIn("rw-openhands-fixture", text)
        # Probe containers count with the attempt's other container removals.
        self.assertEqual(receipt["container_cleanup"], {"attempts": 1, "confirmed_removed": 1, "complete": True})


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
                patch.object(dispatch, "verify_isolation", return_value={"passed": True}) as gate, \
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
        # Only start is gated on the probe receipt (plan E1, G7).
        gate.assert_called_once_with(self.state, self.run_id, self.arm, 3730)
        for row in output.getvalue().splitlines():
            self.assertEqual(json.loads(row)["receipt"], str(self.result / "receipt.json"))
        self.assertEqual(json.loads((self.result / "status.json").read_text())["status"], "collected")
        self.assertNotIn(FIXTURE_CONVERSATION_ID, (self.result / "receipt.json").read_text())

    def test_start_requires_a_fresh_owner_only_probe_receipt(self):
        # Plan E1/G7: refused before the serial lock, with nothing mutated.
        dispatch = load_recipe_module("dispatch.py")
        host = load_recipe_module("host.py")
        status = {"run_id": self.run_id, "arm": self.arm, "status": "prepared", "port": 3740,
                  "proxy_config_sha256": "0" * 64}
        receipt = self.result / "isolation-probe.json"
        now = datetime.now(timezone.utc)
        for label, verified_at, mode in (("missing", None, None),
                                         ("901 s old", (now - timedelta(seconds=901)).isoformat(), 0o600),
                                         ("mode 0644", now.isoformat(), 0o644)):
            with self.subTest(label):
                receipt.unlink(missing_ok=True)
                if verified_at:
                    host.write_private_json(receipt, {"mechanism": "internal-isolated+nginx-v1-allowlist",
                                                      "verified_at": verified_at, "passed": True})
                    receipt.chmod(mode)
                (self.result / "status.json").write_text(json.dumps(status))
                (self.result / "window.json").write_text(json.dumps({"arm": self.arm, "run_id": self.run_id}))
                (self.result / "start.json").write_text("{}")
                output = io.StringIO()
                with patch.object(dispatch, "api_request") as api, patch.object(dispatch, "stop_server") as stop, \
                        patch("subprocess.check_output") as docker, contextlib.redirect_stdout(output):
                    self.assertEqual(dispatch.execute("start", self.state, self.run_id, self.arm), 3)
                api.assert_not_called()
                stop.assert_not_called()
                docker.assert_not_called()
                self.assertEqual(json.loads((self.result / "status.json").read_text()), status)
                self.assertFalse((self.state / "active-dispatch.json").exists())
                self.assertFalse((self.result / "receipt.json").exists())
                self.assertEqual(json.loads(output.getvalue())["failure_stage"], "probe")

    def test_native_routes_pair_each_path_with_its_one_method(self):
        # Plan E3: POST only creates or interrupts a conversation; GET only reads.
        dispatch = load_recipe_module("dispatch.py")
        base = f"/api/conversations/{FIXTURE_CONVERSATION_ID}"
        allowed = (("POST", "/api/conversations"), ("POST", base + "/interrupt"), ("GET", base),
                   ("GET", base + "/agent_final_response"), ("GET", base + self.ERROR_SEARCH))
        refused = (("GET", "/api/conversations"), ("POST", base), ("POST", base + "/agent_final_response"),
                   ("GET", base + "/interrupt"), ("POST", base + self.ERROR_SEARCH), ("DELETE", base),
                   ("PUT", "/api/conversations"), ("PATCH", base), ("get", base), ("HEAD", base),
                   ("GET", "/api/conversations/../settings"), ("POST", "/api/conversations?x=1"))
        headers = self.result / "headers"
        with patch.object(dispatch, "curl_json", return_value={}) as curl:
            for method, path in allowed:
                dispatch.api_request(method, path, headers=headers, port=3740)
            self.assertEqual([(call.kwargs["method"], call.args[0]) for call in curl.call_args_list],
                             [(method, "http://127.0.0.1:3740" + path) for method, path in allowed])
            curl.reset_mock()
            for method, path in refused:
                with self.subTest(method=method, path=path), self.assertRaises(ValueError):
                    dispatch.api_request(method, path, headers=headers, port=3740)
            curl.assert_not_called()

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
        stem = self.run_id + "-control"
        args = dispatch.server_command(pins, stem + "-server", [], stem + "-int", "/private/server.env")
        self.assertNotIn("--entrypoint", args)
        # Plan E1: the agent-server publishes nothing; only the proxy does.
        self.assertFalse(any(arg == "--publish" or arg.startswith(("--publish=", "-p")) for arg in args))
        self.assertIn("--network=" + stem + "-int", args)
        self.assertEqual(args[-4:], ["--extra-python-path", "/recipe", "--import-modules", "server_transport"])
        self.assertEqual(args[args.index("--env-file") + 1], "/private/server.env")
        with self.assertRaises(ValueError):
            dispatch.server_command(pins, stem + "-server", [], stem + "-gw", "/private/server.env")

    def test_compression_delta_is_separate_and_missing_or_reset_is_unknown(self):
        dispatch = load_recipe_module("dispatch.py")
        before = {"totalRequests": 3, "totalTokensSaved": 10}
        after = {"totalRequests": 5, "totalTokensSaved": 25}
        self.assertEqual(dispatch.compression_delta(before, after)["delta"], {"totalRequests": 2, "totalTokensSaved": 15})
        self.assertIsNone(dispatch.compression_delta(None, after)["delta"])
        self.assertIsNone(dispatch.compression_delta(after, before)["delta"])

    def prepare(self, port=3730, render_exit=0, arm=None):
        """prepare_native_dispatch with Docker mocked; no container or network."""
        host = load_recipe_module("host.py")
        dispatch = load_recipe_module("dispatch.py")
        pins = json.loads((RECIPE / "pins.json").read_text())
        arm = arm or self.arm
        result = self.state / "runs" / self.run_id / arm
        (result / "worker").mkdir(parents=True, exist_ok=True)
        stem = self.run_id + "-" + arm
        rendered, commands = [], []

        def render(args, name, log, timeout):
            rendered.append(args)
            (result / "worker/start.json").write_text(json.dumps({"agent": {"llm": {}}, "workspace": {}, "initial_message": {}}))
            return render_exit

        topology = {kind: {"name": f"{stem}-{kind}", "id": hashlib.sha256(kind.encode()).hexdigest()}
                    for kind in ("int", "gw")}
        with patch.dict(sys.modules, {"dispatch": dispatch}), \
                patch.object(host, "execute_container", side_effect=render), \
                patch.object(host, "create_topology", return_value=topology) as create, \
                patch.object(host, "logged_command", side_effect=lambda argv, *a, **k: commands.append(argv) or 0), \
                patch.object(dispatch, "check_server", return_value=None) as check:
            host.prepare_native_dispatch(self.state, self.run_id, load_recipe_module("recipe.py").arm_config(arm),
                                         self.state / "prefix", pins, [], {"variables": {"HOST_PATH": "/usr/bin"}},
                                         port=port)
        return SimpleNamespace(host=host, dispatch=dispatch, result=result, stem=stem, rendered=rendered,
                               commands=commands, create=create, check=check, pins=pins)

    def test_prepare_serializes_body_offline_then_launches_native_server(self):
        prepared = self.prepare()
        host, result, stem, commands = prepared.host, prepared.result, prepared.stem, prepared.commands
        request = prepared.rendered[0]
        self.assertIn("--network=none", request)
        self.assertIn("OPENHANDS_ARM=engines-on", request)
        self.assertIn("OPENHANDS_BASE_URL=http://gw:8081/v1", request)
        self.assertIn("OPENHANDS_COMPRESSION=allow-lossy", request)
        self.assertEqual(request[-1], "--request")
        prepared.create.assert_called_once_with(result, stem)
        # Order: server on the internal network, then proxy create/connect/start.
        server, create, connect, start = commands
        self.assertNotIn("--entrypoint", server)
        self.assertIn("--network=" + stem + "-int", server)
        self.assertFalse(any(arg == "--publish" or arg.startswith("-p") for arg in server))
        env_file, headers = host.session_files(self.state, self.run_id, self.arm)
        self.assertEqual(server[server.index("--env-file") + 1], str(env_file))
        self.assertEqual(create[len(host.DOCKER)], "create")
        self.assertIn("--network=" + stem + "-gw", create)
        self.assertEqual(create[create.index("--publish") + 1], "127.0.0.1:3730:8080")
        self.assertIn(f"type=bind,src={result}/proxy/nginx.conf,dst=/etc/nginx/nginx.conf,readonly", create)
        self.assertEqual(connect[len(host.DOCKER):], ["network", "connect", "--alias", "gw", stem + "-int", stem + "-proxy"])
        self.assertEqual(start[len(host.DOCKER):], ["start", stem + "-proxy"])
        # The key is generated per attempt and is never part of any argv.
        value = env_file.read_text().split("=", 1)[1].strip()
        self.assertTrue(value and headers.is_file())
        for argv in prepared.rendered + commands:
            self.assertNotIn(value, " ".join(map(str, argv)))
        # The rendered proxy config sits outside every model mount.
        config = result / "proxy/nginx.conf"
        self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o644)
        self.assertIn("proxy_pass http://10.0.2.2:20129/v1/responses;", config.read_text())
        for argv in [request, server]:
            self.assertFalse(any(f"src={result}/proxy" in arg for arg in argv))
        prepared.check.assert_called_once()
        self.assertEqual(prepared.check.call_args.kwargs["port"], 3730)
        self.assertTrue((result / "start.json").exists())
        status = json.loads((result / "status.json").read_text())
        self.assertEqual(status["status"], "prepared")
        self.assertEqual((status["server_name"], status["proxy_name"], status["port"]),
                         (stem + "-server", stem + "-proxy", 3730))
        self.assertEqual(status["proxy_config_sha256"], hashlib.sha256(config.read_bytes()).hexdigest())

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
        class NativeService:
            async def start_goal_loop(self, *args, **kwargs):
                return kwargs
            async def resume_goal_loop(self, *args, **kwargs):
                return kwargs
        modules = {"openhands.sdk": SimpleNamespace(LLM="native-llm"),
                   "openhands.agent_server.event_service": SimpleNamespace(EventService=NativeService),
                   "worker": SimpleNamespace(gateway_transport=factory, capture_correlation="callback",
                                             register_worker_agents=MagicMock())}
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {
                    "OPENHANDS_OWNED_CONTAINER": "1", "OPENHANDS_RUN_ID": "rw-openhands-fixture"}), \
                patch("atexit.register") as register:
            load_recipe_module("server_transport.py")
        factory.assert_called_once_with("native-llm", correlation_callback="callback")
        context.__enter__.assert_called_once()
        self.assertEqual(register.call_count, 2)

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
        with self.assertRaises(RuntimeError):
            self.prepare(render_exit=7)
        # Nothing was created: no network, key file, server or proxy.
        host = load_recipe_module("host.py")
        self.assertFalse((self.state / "secrets").exists())
        self.assertFalse(any(path.exists() for path in host.session_files(self.state, self.run_id, self.arm)))
        self.assertFalse((self.result / "status.json").exists())
        self.assertFalse((self.result / "proxy").exists())

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
        prepared = self.prepare(port=3740)
        dispatch, commands = prepared.dispatch, prepared.commands
        published = [argv[argv.index("--publish") + 1] for argv in commands if "--publish" in argv]
        self.assertEqual(published, ["127.0.0.1:3740:8080"])
        self.assertEqual(prepared.check.call_args.kwargs["port"], 3740)
        self.assertEqual(json.loads((self.result / "status.json").read_text())["port"], 3740)
        (self.result / "window.json").write_text(json.dumps({"arm": self.arm, "run_id": self.run_id}))
        headers = prepared.host.session_files(self.state, self.run_id, self.arm)[1]
        with patch.object(dispatch, "api_request", return_value={"id": FIXTURE_CONVERSATION_ID}) as api, \
                patch.object(dispatch, "verify_isolation", return_value={"passed": True}), \
                patch.object(dispatch, "compression_snapshot", return_value=None), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.execute("start", self.state, self.run_id, self.arm), 0)
        self.assertEqual(api.call_args.kwargs["port"], 3740)
        # The headers path is derived from the attempt identity, never read
        # from status.json or the environment.
        self.assertEqual(api.call_args.kwargs["headers"], headers)
        status = json.loads((self.result / "status.json").read_text())
        (self.result / "status.json").write_text(json.dumps({**status, "port": 8000}))
        with patch.object(dispatch, "api_request") as api, patch.object(dispatch, "stop_server"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dispatch.execute("wait", self.state, self.run_id, self.arm), 3)
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
