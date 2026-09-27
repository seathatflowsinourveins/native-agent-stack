"""Guard the scope and sanitization of the dated AgentsView qualification.

Sources: kenn-io/agentsview v0.44.0 (413a87f7bfbd67b2815b1119ac51abc1efbeeaba),
internal/mcp/tools.go:705-726, cmd/agentsview/usage.go:163-168,
cmd/agentsview/serve_runtime.go:57-65; ccusage/ccusage v20.0.24
(ecb676cce27cb5dd0090c7804a5cecc35e8ba805), rust/adapters/codex/src/parser.rs.
Structural checks follow docs/acceptance-evidence-policy.md:31-69 and the
negative-control pattern in Python's unittest.TestCase.assertRaises:
https://docs.python.org/3.13/library/unittest.html#unittest.TestCase.assertRaises
These check artifact consistency, not upstream execution or provider runs.
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
        self.assertEqual(receipt["gates"]["upstream_broad_tests"], "passed_outside_codex_sandbox")
        self.assertEqual(receipt["gates"]["fresh_four_native_lanes"], "blocked")
        self.assertEqual(receipt["gates"]["independent_gpt6_review"], "not_completed")
        self.assertEqual(receipt["gates"]["independent_claude_review"], "incomplete")
        self.assertEqual(receipt["gates"]["unchanged_full_save_runner"], "not_run")
        self.assertEqual(receipt["evidence_class"], "multi_class_summary")
        self.assertEqual(receipt["repository_tests"]["evidence_class"], "structural_validation")
        self.assertTrue(receipt["residuals"])
        self.assertTrue(receipt["errata"])

    def test_review_attempts_cannot_be_promoted_to_completed_reviews(self):
        reviews = self.read("qualification.json")["reviews"]
        self.assertEqual(reviews["gpt6"]["status"], "not_completed")
        self.assertNotIn("verdict", reviews["gpt6"])
        self.assertNotIn("independently_checked", reviews["gpt6"])
        self.assertFalse(reviews["gpt6"]["returned_report_retained"])
        self.assertEqual(len(reviews["native_codex_attempts"]), 2)
        for attempt in reviews["native_codex_attempts"]:
            self.assertEqual(attempt["exit_code"], 1)
            self.assertEqual(attempt["jsonl_bytes"], 0)
            self.assertFalse(attempt["last_message_exists"])
            self.assertTrue(attempt["stderr_ref"].endswith(".stderr"))
        claude = reviews["claude"]
        self.assertEqual(claude["stopped_by"], "build_session")
        self.assertEqual(claude["signal"], "SIGINT")
        self.assertEqual(claude["exit_code"], 130)
        self.assertEqual(claude["tools"], ["Read", "Agent"])
        self.assertEqual(claude["launch_context"], "inside_builder_codex_sandbox")
        self.assertEqual(claude["requalification_context"], "outside_codex_sandbox")

    def test_prior_verdict_and_future_pin_locations_are_reconciled(self):
        receipt = self.read("qualification.json")
        prior = receipt["prior_records"][0]
        self.assertEqual(prior["path"], "evidence/artifacts/sota-refresh-20260923/pins-tools/agentsview.json")
        self.assertEqual(prior["verdict"], "qualified")
        self.assertEqual(prior["governing_repin_record"], "qualification.json")
        self.assertFalse(prior["satisfies_full_qualification"])
        self.assertIn("limits[0]", prior["scope_basis"])
        required = {"manifests/stack.json", "scripts/native_token_ci.py", "recipes/README.md",
                    "docs/token-efficiency-stack.json", "docs/stack.md"}
        self.assertTrue(required.issubset(receipt["repository_pin_locations"]["files"]))
        rewire = receipt["required_future_recipe_rewire"]["files"]
        self.assertTrue({"recipes/README.md", "docs/token-efficiency-stack.json", "docs/stack.md"}.issubset(rewire))
        self.assertEqual(rewire["docs/token-efficiency-stack.json"]["fields"],
                         ["install", "install_note", "use"])

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
        fixture = checks["synthetic_fixture"]
        self.assertEqual(fixture["expected_automated_sessions"], {"0.43.0": 0, "0.44.0": 2})
        frozen = fixture["frozen_inputs"]
        self.assertEqual(frozen["capture_stage"], "repair_after_original_trial")
        self.assertEqual(len(frozen["files"]), 23)
        self.assertEqual(sum(f["kind"] == "session_log" for f in frozen["files"]), 5)
        self.assertEqual(len({f["label"] for f in frozen["files"]}), 23)
        for entry in frozen["files"]:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(entry["bytes"], 0)
        for version in ("0.43.0", "0.44.0"):
            self.assertEqual(fixture["versions"][version]["inclusive_sessions"], 5)
            self.assertEqual(fixture["versions"][version]["automated_sessions"],
                             fixture["expected_automated_sessions"][version])

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
        self.assertEqual(upstream["broad_attempt"]["failure_class"], "environmental")
        self.assertFalse(upstream["confirming_subprocess_rerun"]["raw_bytes_retained"])
        self.assertIn("gpt6-build-events.jsonl", upstream["confirming_subprocess_rerun"]["summary_ref"])
        controls = upstream["coordinator_runs"]
        self.assertEqual(controls["execution_context"], "outside_codex_sandbox")
        self.assertTrue(controls["environment"]["TMPDIR"].startswith("/var/tmp/"))
        self.assertTrue(controls["tracked_source_clean_before_and_after"])
        expected = {
            "v0.44.0": (4575, "8529d7daa9b6c60ec2730066330f2e347adbc17a4af64ae2d906708221bb7190"),
            "v0.43.0": (4387, "ace5a04c6183b31924856f9f36ba79cbbe812317ef9d5d813262e6aa892e4ec4"),
        }
        for run in controls["broad"]:
            count, digest = expected[run["tag"]]
            self.assertEqual(run["exit_code"], 0)
            self.assertEqual(run["top_level_counts"], {"passed": count, "failed": 0, "skipped": 32})
            self.assertEqual(run["stdout_sha256"], digest)
            self.assertTrue(run["stdout_ref"].endswith(".jsonl"))
        self.assertEqual({r["tag"] for r in controls["broad"]}, set(expected))
        serve = controls["serve_runtime"]
        self.assertEqual(serve["exit_code"], 0)
        self.assertEqual(serve["top_level_counts"], {"passed": 5, "failed": 0, "skipped": 0})
        self.assertEqual(serve["stdout_sha256"], "533a163412c06f37a6155d0cc18f4b776d7a4854d4784ae8b3f130553ebbd485")
        self.assertIn("TestPrepareRunServeRuntimeConfigRestartPreservesConfiguredURLRewrite", serve["test_names"])
        self.assertEqual(upstream["diagnosis"]["status"], "environmental_failure_discriminated")

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

        def check(text, is_json):
            self.assertNotRegex(text, r"/(?:home|Users)/[^/\s]+")
            self.assertNotRegex(text, r"/tmp/claude-\d+")
            self.assertNotRegex(text, r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b")
            self.assertNotRegex(text, r"(?i)bearer\s+[a-z0-9._~+/=-]+")
            if is_json:
                visit(json.loads(text))

        # Generated violations exercise the very same checks as published files.
        # Source: unittest.TestCase.assertRaises; no real private value is used.
        planted = {
            "home_path": {"nested": ["/".join(("", "home", "planted", "receipt"))]},
            "uuid": {"nested": ["-".join("0" * n for n in (8, 4, 4, 4, 12))]},
            "forbidden_key": {"nested": [{"request_body": "planted"}]},
        }
        for label, value in planted.items():
            with self.subTest(planted=label), self.assertRaises(AssertionError):
                check(json.dumps(value), True)

        paths = list(ARTIFACT.iterdir())
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            with self.subTest(path=path.name):
                check(path.read_text(), path.suffix == ".json")


if __name__ == "__main__":
    unittest.main()
