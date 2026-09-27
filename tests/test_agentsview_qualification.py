"""Guard the scope and sanitization of the dated AgentsView qualification.

Sources: kenn-io/agentsview v0.44.0 (413a87f7bfbd67b2815b1119ac51abc1efbeeaba),
internal/mcp/tools.go:705-726, cmd/agentsview/usage.go:163-168,
cmd/agentsview/serve_runtime.go:57-65; ccusage/ccusage v20.0.24
(ecb676cce27cb5dd0090c7804a5cecc35e8ba805), rust/adapters/codex/src/parser.rs.
These are repository evidence checks, not upstream tests or provider runs.
"""

import json
from pathlib import Path
import unittest


ARTIFACT = Path(__file__).resolve().parents[1] / "evidence/artifacts/agentsview-044-qualification-20260927"


class AgentsviewQualificationTests(unittest.TestCase):
    def read(self, name):
        return json.loads((ARTIFACT / name).read_text())

    def test_incomplete_gates_cannot_be_presented_as_a_qualified_repin(self):
        receipt = self.read("qualification.json")
        self.assertFalse(receipt["qualified"])
        self.assertFalse(receipt["pin_change_prepared"])
        self.assertFalse(receipt["host_switch_performed"])
        self.assertEqual(receipt["verdict"], "hold")
        self.assertEqual(receipt["gates"]["upstream_broad_tests"], "failed")
        self.assertEqual(receipt["gates"]["fresh_four_native_lanes"], "blocked")
        self.assertEqual(receipt["gates"]["independent_claude_review"], "incomplete")
        self.assertTrue(receipt["residuals"])

    def test_copied_archive_parity_counts_cached_input_once(self):
        observed = self.read("native-checks.json")["copied_archive"]
        expected = {"inputTokens": 20965, "cacheReadTokens": 58752,
                    "cacheCreationTokens": 0, "outputTokens": 556}
        for version in ("0.43.0", "0.44.0"):
            self.assertEqual(observed["versions"][version]["cli_tokens"], expected)
            self.assertEqual(observed["versions"][version]["inclusive_sessions"], 2)
        ccusage = observed["ccusage"]
        self.assertEqual({k: ccusage[k] for k in expected}, expected)
        self.assertEqual(ccusage["totalTokens"], sum(expected.values()))
        self.assertEqual(ccusage["reasoningOutputTokens"], 64)
        self.assertTrue(observed["session_keys_preserved"])
        self.assertTrue(observed["source_copies_byte_identical"])
        self.assertEqual(observed["fresh_provider_executions"], 0)

    def test_mcp_gap_port_change_and_failed_fixture_are_retained(self):
        checks = self.read("native-checks.json")
        archive = checks["copied_archive"]["versions"]
        self.assertEqual(archive["0.44.0"]["mcp_tokens"]["outputTokens"], 0)
        self.assertEqual(archive["0.43.0"]["mcp_tokens"]["outputTokens"], 556)
        self.assertEqual(checks["occupied_port"]["0.43.0"]["exit_code"], 0)
        self.assertEqual(checks["occupied_port"]["0.44.0"]["exit_code"], 1)
        self.assertEqual(checks["synthetic_fixture"]["ccusage_parity"], "failed")
        self.assertEqual(checks["synthetic_fixture"]["expected_sessions"], 5)
        for version in ("0.43.0", "0.44.0"):
            self.assertEqual(checks["synthetic_fixture"]["versions"][version]["inclusive_sessions"], 5)

    def test_upstream_failures_stay_distinct_from_targeted_success(self):
        upstream = self.read("upstream-tests.json")
        self.assertEqual(upstream["evidence_class"], "unchanged_upstream_tests")
        self.assertTrue(upstream["tracked_source_unchanged"])
        self.assertEqual(upstream["targeted_classification"]["top_level_tests_passed"], 4)
        self.assertEqual(upstream["targeted_classification"]["test_events_passed"], 13)
        self.assertEqual(upstream["broad_attempt"]["exit_code"], 1)
        self.assertEqual(upstream["broad_attempt"]["top_level_counts"]["failed"], 21)
        self.assertEqual(upstream["broad_attempt"]["test_event_counts"]["failed"], 25)
        self.assertEqual(len(upstream["broad_attempt"]["failed_test_events"]), 25)

    def test_published_artifacts_use_whitelisted_aggregates(self):
        forbidden_keys = {
            "session_id", "sessionId", "parent_session_id", "connection_id",
            "machineName", "machine_name", "account_id", "email", "uuid",
            "request_body", "requestBody", "messages", "inclusive_rows",
            "project", "project_id", "content", "prompt", "api_key",
        }

        def visit(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden_keys.intersection(value))
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        for path in ARTIFACT.iterdir():
            with self.subTest(path=path.name):
                text = path.read_text()
                self.assertNotRegex(text, r"/(?:home|Users)/[^/\s]+")
                self.assertNotRegex(text, r"/tmp/claude-\d+")
                self.assertNotRegex(text, r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b")
                self.assertNotRegex(text, r"(?i)bearer\s+[a-z0-9._~+/=-]+")
                if path.suffix == ".json":
                    visit(json.loads(text))


if __name__ == "__main__":
    unittest.main()
