"""Integration-contract fixtures, not upstream tests or live provider acceptance."""
import ast
import io
import json
from pathlib import Path
import tomllib
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
# The repository's offline CI does not install the optional SDK. Exercise the
# actual pure route helpers, using the existing observability test's AST pattern;
# the receipt separately records imports and native execution of the real SDK.
SOURCE = ast.parse((ROOT / "blueprints/us-equities/workers/native_worker.py").read_text())
HELPERS = {"gateway_base_url", "route_overrides", "gateway_readiness"}
WORKER = types.ModuleType("native_worker_route")
WORKER.__dict__.update(json=json, tomllib=tomllib, urlsplit=urlsplit, urlopen=urlopen)
BODY = [node for node in SOURCE.body if
        isinstance(node, ast.FunctionDef) and node.name in HELPERS or
        isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "GATEWAY_MODEL"
            for target in node.targets)]
exec(compile(ast.Module(body=BODY, type_ignores=[]), "native_worker.py", "exec"),
     WORKER.__dict__)


class NativeWorkerRouteTests(unittest.TestCase):
    def test_keyless_route_rejects_external_hosts_and_embedded_credentials(self):
        for value in (
            "https://example.com/v1", "http://example.com:20128/v1",
            "http://user:secret@127.0.0.1:20128/v1", "http://127.0.0.1/v1",
            "http://127.0.0.1:20128/v1?route=other", "http://127.0.0.1:20128/v1#other",
            "http://127.0.0.1:20128/other", "http://127.0.0.1:bad/v1",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                WORKER.gateway_base_url(value)
        self.assertEqual(WORKER.gateway_base_url("http://127.0.0.1:20128/v1/"),
                         "http://127.0.0.1:20128/v1")

    def test_native_provider_config_uses_responses_max_and_no_native_auth(self):
        overrides = WORKER.route_overrides("omniroute", "http://127.0.0.1:20128/v1", ())
        parsed = tomllib.loads("\n".join(overrides))
        self.assertEqual(parsed["model_provider"], "omniroute")
        self.assertEqual(parsed["model_reasoning_effort"], "max")
        provider = parsed["model_providers"]["omniroute"]
        self.assertEqual(provider["wire_api"], "responses")
        self.assertFalse(provider["requires_openai_auth"])
        self.assertEqual(provider["base_url"], "http://127.0.0.1:20128/v1")

    def test_extra_settings_cannot_replace_the_selected_route(self):
        for setting in (
            'model_provider="openai"', '"model_provider"="openai"',
            'model_reasoning_effort="low"', 'model="other"',
            'model_providers.omniroute.base_url="http://example.com/v1"',
            'model_providers."omniroute".base_url="http://example.com/v1"',
        ):
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                WORKER.route_overrides("omniroute", "http://127.0.0.1:20128/v1", (setting,))
        settings = ('mcp_servers.example.command="node"',)
        self.assertEqual(WORKER.route_overrides("openai", "unused", settings),
                         (*settings, 'model_reasoning_effort="max"'))
        self.assertIn(settings[0], WORKER.route_overrides(
            "omniroute", "http://127.0.0.1:20128/v1", settings))

    def test_gateway_discovery_is_explicitly_metadata_only(self):
        for available in (True, False):
            listing = {"data": [{"id": WORKER.GATEWAY_MODEL}] if available else []}
            with patch.object(WORKER, "urlopen", return_value=io.BytesIO(json.dumps(listing).encode())) as call:
                result = WORKER.gateway_readiness("http://127.0.0.1:20128/v1")
            call.assert_called_once_with("http://127.0.0.1:20128/v1/models", timeout=10)
            self.assertEqual(result["ready"], available)
            self.assertEqual(result["evidence_level"], "advertised_model_only")
            self.assertNotIn("ordinary_usage_allowed", result)


if __name__ == "__main__":
    unittest.main()
