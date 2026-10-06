"""Execute actual worker CLI parsing with inert SDK/provider imports.

Local/synthetic configuration checks only: no model, network or credential read.
The config fixture uses the canonical gpt-gateway-topology/v1 endpoint field.
"""

import contextlib
from enum import Enum
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
from string import Template
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FALLBACK = "http://127.0.0.1:21128/v1"
TOPOLOGY = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002/config/gpt-gateway-topology.json"


def provider_forbidden(*args, **kwargs):
    raise AssertionError("configuration test attempted a provider/runtime call")


def imports_without_providers():
    """Only imported SDK enum data is needed by the real Codex parser."""
    approval = Enum("ApprovalMode", {"deny_all": "never"})
    sandbox = Enum("Sandbox", {"read_only": "read-only", "workspace_write": "workspace-write"})
    effort = Enum("ReasoningEffort", {"max": "max", "ultra": "ultra"})
    exports = {
        "openai_codex": {"ApprovalMode": approval, "Sandbox": sandbox,
                         "AsyncCodex": provider_forbidden, "CodexConfig": provider_forbidden},
        "openai_codex.async_client": {"AsyncCodexClient": provider_forbidden},
        "openai_codex.generated": {},
        "openai_codex.generated.v2_all": {
            name: provider_forbidden for name in
            ("ConfigReadResponse", "ListMcpServerStatusResponse", "SkillsListResponse")
        },
        "openai_codex.types": {"ReasoningEffort": effort},
        "deepagents": {name: provider_forbidden for name in
                       ("GeneralPurposeSubagentProfile", "HarnessProfile", "create_deep_agent", "register_harness_profile")},
        "deepagents.backends": {"FilesystemBackend": provider_forbidden},
        "langchain": {},
        "langchain.agents": {},
        "langchain.agents.middleware": {"ToolCallLimitMiddleware": provider_forbidden},
        "langchain_core": {},
        "langchain_core.load": {"dumps": json.dumps},
        "langchain_openai": {"ChatOpenAI": provider_forbidden},
        "langgraph": {},
        "langgraph.checkpoint": {},
        "langgraph.checkpoint.sqlite": {"SqliteSaver": provider_forbidden},
        "anyio": {"run": provider_forbidden},
        "claude_agent_sdk": {
            "ClaudeAgentOptions": SimpleNamespace,
            "ClaudeSDKClient": provider_forbidden,
            **{name: type(name, (), {}) for name in
               ("AssistantMessage", "ResultMessage", "SystemMessage", "ToolResultBlock",
                "ToolUseBlock", "UserMessage")},
        },
    }
    modules = {}
    for name, values in exports.items():
        module = ModuleType(name)
        module.__path__ = []
        module.__dict__.update(values)
        modules[name] = module
    return modules


class GatewayWorkerDefaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workers = {}
        strict = os.environ.get("LANGGRAPH_STRICT_MSGPACK")
        try:
            with patch.dict(sys.modules, imports_without_providers()):
                for name, directory in (("codex", "omniroute-codex-sdk"),
                                        ("deepagents", "deepagents-omniroute"),
                                        ("claude", "claude-runtime-sdk")):
                    spec = importlib.util.spec_from_file_location(
                        "gateway_default_" + name, ROOT / "examples" / directory / "worker.py"
                    )
                    module = importlib.util.module_from_spec(spec)
                    # dataclasses resolves the module while decorating Observation.
                    with patch.dict(sys.modules, {spec.name: module}):
                        spec.loader.exec_module(module)
                    cls.workers[name] = module
        finally:
            if strict is None:
                os.environ.pop("LANGGRAPH_STRICT_MSGPACK", None)
            else:
                os.environ["LANGGRAPH_STRICT_MSGPACK"] = strict

    def selected_url(self, name, topology, explicit=None):
        worker = self.workers[name]
        if name == "claude":
            argv = ["--cwd", str(ROOT)]
            if explicit is not None:
                argv.extend(["--gateway", explicit.removesuffix("/v1")])
            with patch.object(worker, "GATEWAY_TOPOLOGY", topology), \
                    patch.dict(os.environ, {}, clear=True):
                options = worker.build_options(worker.parser().parse_args(argv))
            root = options.env["ANTHROPIC_BASE_URL"]
            self.assertEqual(urlsplit(root).path, "")
            return root + "/v1"
        argv = ["--workspace", str(ROOT)]
        if explicit is not None:
            argv.extend(["--base-url", explicit])
        with patch.object(worker, "GATEWAY_TOPOLOGY", topology):
            if name == "codex":
                return worker.parse_args(argv).base_url
            argv.extend(["--checkpoint", "unused.sqlite", "--thread-id", "fixture",
                         "--skill", "unused-skill", "--describe"])
            output = io.StringIO()
            with patch.object(sys, "argv", ["worker.py", *argv]), \
                    patch("importlib.metadata.version", return_value="synthetic"), \
                    contextlib.redirect_stdout(output):
                worker.main()
            config = json.loads(output.getvalue())["native"]
            self.assertEqual(config["underlying_lane"], worker.default_gateway_base_url())
            return config["base_url"]

    def test_no_base_url_uses_canonical_topology(self):
        expected = json.loads(TOPOLOGY.read_text())["gateway"]["endpoint"]
        self.assertNotIn(urlsplit(expected).port, {20128, 20129})
        for name in self.workers:
            with self.subTest(worker=name):
                self.assertEqual(self.selected_url(name, TOPOLOGY), expected)

    def test_missing_topology_falls_back_to_2604(self):
        with tempfile.TemporaryDirectory() as directory:
            absent = Path(directory) / "absent.json"
            for name in self.workers:
                with self.subTest(worker=name):
                    self.assertEqual(self.selected_url(name, absent), FALLBACK)

    def test_configured_endpoint_and_explicit_cli_override(self):
        with tempfile.TemporaryDirectory() as directory:
            topology = Path(directory) / "topology.json"
            topology.write_text(json.dumps({"gateway": {"endpoint": "http://127.0.0.1:21188/v1"}}))
            for name in self.workers:
                with self.subTest(worker=name):
                    self.assertEqual(self.selected_url(name, topology), "http://127.0.0.1:21188/v1")
                    for explicit in ("http://127.0.0.1:24444/v1", "http://127.0.0.1:20128/v1",
                                     "http://127.0.0.1:20129/v1"):
                        self.assertEqual(self.selected_url(name, topology, explicit), explicit)

    def test_stale_legacy_or_malformed_topology_never_defaults_to_nativestack(self):
        with tempfile.TemporaryDirectory() as directory:
            topology = Path(directory) / "topology.json"
            malformed_urls = (
                "http://127.0.0.1:20128/v1",
                "http://127.0.0.1:20129/v1",
                "http://127.0.0.1/v1",
                "https://127.0.0.1:21188/v1",
                "http://remote.example.invalid:21188/v1",
                "http://127.0.0.1:21188/not-v1",
                "http://127.0.0.1:21188/v1?fixture=1",
                "http://127.0.0.1:not-a-port/v1",
            )
            texts = [json.dumps({"gateway": {"endpoint": url}}) for url in malformed_urls]
            for text in [*texts, '{"gateway":{"endpoint":null}}', '{}', '{broken']:
                topology.write_text(text)
                for name in self.workers:
                    with self.subTest(worker=name, topology=text):
                        self.assertEqual(self.selected_url(name, topology), FALLBACK)

    def test_shallow_worker_copies_import_and_fall_back(self):
        strict = os.environ.get("LANGGRAPH_STRICT_MSGPACK")
        try:
            for name, original in self.workers.copy().items():
                with self.subTest(worker=name):
                    module = ModuleType("gateway_default_shallow_" + name)
                    module.__file__ = "/worker.py"
                    source = Path(original.__file__).read_text(encoding="utf-8")
                    imports = imports_without_providers()
                    imports[module.__name__] = module
                    with patch.dict(sys.modules, imports):
                        exec(compile(source, module.__file__, "exec"), module.__dict__)
                    with patch.dict(self.workers, {name: module}):
                        self.assertEqual(self.selected_url(name, module.GATEWAY_TOPOLOGY), FALLBACK)
                        self.assertEqual(
                            self.selected_url(name, module.GATEWAY_TOPOLOGY,
                                              "http://127.0.0.1:24444/v1"),
                            "http://127.0.0.1:24444/v1",
                        )
        finally:
            if strict is None:
                os.environ.pop("LANGGRAPH_STRICT_MSGPACK", None)
            else:
                os.environ["LANGGRAPH_STRICT_MSGPACK"] = strict

    def test_dagu_documented_binding_targets_2604_in_both_steps(self):
        kit = ROOT / "examples/omniroute-codex-sdk"
        # Select the documented HTTP binding, then exercise the actual CLI
        # commands. Native Dagu validation covers YAML syntax separately.
        endpoints = re.findall(r"`(http://[^`]+)`", (kit / "enhancements.md").read_text())
        self.assertEqual(len(endpoints), 1)
        graph = (kit / "runtime-worker.yaml").read_text()
        commands = re.findall(r"(?m)^    run: >-\n((?:^      .*\n)+)", graph)
        self.assertEqual(len(commands), 2)
        private = tempfile.TemporaryDirectory()
        self.addCleanup(private.cleanup)
        bindings = {
            "STACK_ROOT": str(ROOT), "WORKER_PROJECT": str(ROOT),
            "WORKER_CODEX_HOME": private.name,
            "WORKER_RESULT": str(Path(private.name) / "fixture-result.json"),
            "WORKER_TASK_FILE": str(Path(private.name) / "fixture-task.txt"),
        }
        for supplied, expected in ((endpoints[0], FALLBACK), ("http://127.0.0.1:24444/v1", "http://127.0.0.1:24444/v1")):
            for command in commands:
                with self.subTest(binding=supplied, command=command.strip()):
                    rendered = Template(" ".join(command.splitlines())).substitute(
                        bindings, WORKER_BASE_URL=supplied
                    )
                    argv = shlex.split(rendered)
                    argv = argv[argv.index("--workspace"):]
                    if "<" in argv:
                        argv = argv[:argv.index("<")]
                    self.assertEqual(self.workers["codex"].parse_args(argv).base_url, expected)

    def test_deepagents_models_have_distinct_countable_conversation_markers(self):
        worker = self.workers["deepagents"]
        with patch.dict(os.environ, {"FIXTURE_KEY": "synthetic-not-a-credential"}, clear=True), \
                patch.object(worker, "ChatOpenAI") as model, \
                patch.object(worker, "register_harness_profile"), \
                patch.object(worker, "GeneralPurposeSubagentProfile"), \
                patch.object(worker, "HarnessProfile"), \
                patch.object(worker, "FilesystemBackend"), \
                patch.object(worker, "ToolCallLimitMiddleware"), \
                patch.object(worker, "create_deep_agent"):
            worker.build_graph(ROOT, [], object(), "FIXTURE_KEY", FALLBACK)
            worker.build_graph(ROOT, [], object(), "FIXTURE_KEY", FALLBACK)
        self.assertEqual(model.call_count, 4)
        tags = [call.kwargs["default_headers"]["X-OmniRoute-Session-Id"]
                for call in model.call_args_list]
        self.assertEqual(len(set(tags)), 4)
        for tag in tags:
            self.assertRegex(tag, r"^nas-deepagents-omniroute-[0-9a-f]{32}$")

    def test_claude_native_header_keeps_a_distinct_invocation_marker(self):
        worker = self.workers["claude"]
        with patch.dict(os.environ, {}, clear=True):
            options = [worker.build_options(worker.parser().parse_args(["--cwd", str(ROOT)]))
                       for _ in range(2)]
        headers = [option.env["ANTHROPIC_CUSTOM_HEADERS"] for option in options]
        self.assertNotEqual(headers[0], headers[1])
        for header in headers:
            self.assertRegex(header, r"^X-OmniRoute-Session-Id: nas-claude-runtime-sdk-[0-9a-f]{32}$")


if __name__ == "__main__":
    unittest.main()
