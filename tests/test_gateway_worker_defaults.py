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
import sys
import tempfile
from types import ModuleType
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
                for name, directory in (("codex", "omniroute-codex-sdk"), ("deepagents", "deepagents-omniroute")):
                    spec = importlib.util.spec_from_file_location(
                        "gateway_default_" + name, ROOT / "examples" / directory / "worker.py"
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    cls.workers[name] = module
        finally:
            if strict is None:
                os.environ.pop("LANGGRAPH_STRICT_MSGPACK", None)
            else:
                os.environ["LANGGRAPH_STRICT_MSGPACK"] = strict

    def selected_url(self, name, topology, explicit=None):
        worker = self.workers[name]
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


if __name__ == "__main__":
    unittest.main()
