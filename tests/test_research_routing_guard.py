"""Native stdin/stdout protocol checks, isolated from host credentials/settings.

These are repository integration fixtures, not upstream Claude acceptance. Every
case launches the shipped hook as a command; no model/provider is contacted.
"""

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "adoption/hooks/claude/research-routing-guard.py"
SESSION = "synthetic-native-coordinator-session"


class ResearchRoutingGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state_root = Path(self.temporary.name) / "state"
        self.env = dict(os.environ)
        self.env.update({
            "XDG_STATE_HOME": str(self.state_root),
            "NAS_RESEARCH_COORDINATOR_ROLE": "command-center",
            "NAS_RESEARCH_COORDINATOR_SESSION_ID": SESSION,
        })

    def run_guard(self, event=None, *, env=None, raw=None):
        result = subprocess.run(
            [sys.executable, str(GUARD)], input=raw if raw is not None else json.dumps(event),
            text=True, capture_output=True, env=env or self.env, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout) if result.stdout else None

    def event(self, tool="WebSearch", tool_input=None, **changes):
        return {"session_id": SESSION, "hook_event_name": "PreToolUse", "tool_name": tool,
                "tool_input": tool_input or {}, **changes}

    def fetch(self, url="https://code.claude.com/docs/en/hooks", **changes):
        return self.event("WebFetch", {"url": url, "prompt": "Check the native deny output."}, **changes)

    def directory(self):
        directories = list((self.state_root / "native-agent-stack/research-routing").iterdir())
        self.assertEqual(len(directories), 1)
        self.assertTrue(directories[0].is_dir())
        return directories[0]

    def records(self):
        return [json.loads(line) for line in
                (self.directory() / "verification.jsonl").read_text().splitlines()]

    def test_absent_invalid_and_inherited_markers_are_silent_without_state(self):
        for role, marker, changes in [
            (None, None, {}), ("lane", SESSION, {}), ("command-center", "", {}),
            ("command-center", SESSION, {"session_id": "a-different-research-session"}),
            ("co-op", SESSION, {"agent_id": "an-explicit-native-subagent"}),
            ("command-center", SESSION, {"session_id": None}),
        ]:
            with self.subTest(role=role, marker=marker, changes=changes):
                env = dict(self.env)
                env.pop("NAS_RESEARCH_COORDINATOR_ROLE", None)
                env.pop("NAS_RESEARCH_COORDINATOR_SESSION_ID", None)
                if role is not None:
                    env["NAS_RESEARCH_COORDINATOR_ROLE"] = role
                if marker is not None:
                    env["NAS_RESEARCH_COORDINATOR_SESSION_ID"] = marker
                self.assertIsNone(self.run_guard(self.fetch(**changes), env=env))
                self.assertFalse(self.state_root.exists())

    def test_both_coordinator_roles_receive_native_websearch_deny_and_redirect(self):
        for role in ["command-center", "co-op"]:
            with self.subTest(role=role):
                result = self.run_guard(self.event(), env={**self.env, "NAS_RESEARCH_COORDINATOR_ROLE": role})
                fields = result["hookSpecificOutput"]
                self.assertEqual(fields["hookEventName"], "PreToolUse")
                self.assertEqual(fields["permissionDecision"], "deny")
                self.assertIn("tools/research/dispatch --question", fields["permissionDecisionReason"])
                self.assertNotIn("decision", result)
                self.assertNotIn("updatedInput", fields)
                self.assertFalse(self.state_root.exists())

    def test_search_denial_does_not_depend_on_writable_state(self):
        self.state_root.write_text("not a directory")
        result = self.run_guard(self.event())
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_targeted_webfetch_logs_claim_without_granting_permission(self):
        self.assertIsNone(self.run_guard(self.fetch()))
        record = self.records()[0]
        self.assertEqual(record["session_id"], SESSION)
        self.assertEqual(record["role"], "command-center")
        self.assertEqual(record["url"], "https://code.claude.com/docs/en/hooks")
        self.assertEqual(record["claim_checked"], "Check the native deny output.")
        self.assertEqual(record["claim_source"], "prompt")
        self.assertEqual(record["stage"], "requested")
        self.assertRegex(record["utc"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual((self.directory() / "verification.jsonl").stat().st_mode & 0o777, 0o600)

    def test_actual_context_fetch_names_and_missing_claim(self):
        for tool in ["mcp__context_mode__ctx_fetch_and_index", "mcp__context-mode__ctx_fetch_and_index",
                     "mcp__plugin_context-mode_context-mode__ctx_fetch_and_index"]:
            with self.subTest(tool=tool):
                result = self.run_guard(self.event(tool, {"url": "https://docs.example.test/native"}))
                if result:
                    self.assertNotIn("permissionDecision", result["hookSpecificOutput"])
                record = self.records()[-1]
                self.assertEqual(record["tool"], tool)
                self.assertEqual(record["claim_checked"], "unprovided")
                self.assertEqual(record["claim_source"], "unprovided")

    def test_warning_on_third_fetch_and_reset_on_native_user_prompt(self):
        self.assertIsNone(self.run_guard(self.fetch()))
        self.assertIsNone(self.run_guard(self.fetch()))
        warning = self.run_guard(self.fetch())["hookSpecificOutput"]
        self.assertEqual(warning["hookEventName"], "PreToolUse")
        self.assertIn("this turn: 3", warning["additionalContext"])
        self.assertIn("Three or more fetches in one turn counts as research; use", warning["additionalContext"])
        self.assertNotIn("permissionDecision", warning)
        self.assertNotIn("updatedInput", warning)
        self.assertIsNone(self.run_guard({"session_id": SESSION, "hook_event_name": "UserPromptSubmit",
                                          "prompt": "New user turn"}))
        self.assertIsNone(self.run_guard(self.fetch()))
        self.assertEqual(self.records()[-1]["fetches_this_turn"], 1)
        self.assertIsNotNone(self.records()[-1]["turn_started_utc"])

    def test_batch_counts_each_url_and_preserves_each_supplied_source(self):
        event = self.event("mcp__plugin_context-mode_context-mode__ctx_fetch_and_index", {"requests": [
            {"url": "https://docs.example.test/one", "source": "Verify one"},
            {"url": "https://docs.example.test/two", "source": "Verify two"},
            {"url": "https://docs.example.test/three", "source": "Verify three"},
        ]})
        output = self.run_guard(event)["hookSpecificOutput"]
        self.assertIn("this turn: 3", output["additionalContext"])
        self.assertNotIn("permissionDecision", output)
        records = self.records()
        self.assertEqual([r["claim_checked"] for r in records], ["Verify one", "Verify two", "Verify three"])
        self.assertEqual([r["fetches_this_turn"] for r in records], [1, 2, 3])

    def test_urls_and_claims_omit_credentials_and_headers(self):
        event = self.event("WebFetch", {
            "url": "https://fixture-user:fixture-password@docs.example.test/page?q=public&token=fixture-token#private",
            "prompt": "Check https://docs.example.test/page?api_key=fixture-key&q=public and token=fixture-claim-secret",
            "headers": {"Authorization": "Bearer fixture-header-secret"},
        })
        self.assertIsNone(self.run_guard(event))
        text = (self.directory() / "verification.jsonl").read_text()
        self.assertNotIn("fixture-", text)
        self.assertNotIn("Authorization", text)
        record = self.records()[0]
        self.assertEqual(record["url"], "https://docs.example.test/page?q=public")
        self.assertIn("token=[omitted]", record["claim_checked"])
        self.assertNotIn("#private", text)

    def test_marked_state_failure_warns_explicitly_without_denying_fetch_or_turn(self):
        self.state_root.write_text("not a directory")
        for event in [self.fetch(), {"session_id": SESSION, "hook_event_name": "UserPromptSubmit"}]:
            with self.subTest(event=event["hook_event_name"]):
                result = self.run_guard(event)
                self.assertNotIn("additionalContext", result)
                fields = result["hookSpecificOutput"]
                self.assertEqual(fields["hookEventName"], event["hook_event_name"])
                self.assertIn("verification unavailable", fields["additionalContext"])
                self.assertNotIn("permissionDecision", fields)
                self.assertNotIn("decision", fields)

    def test_malformed_marked_tool_input_warns_without_creating_state(self):
        event = self.event("mcp__context_mode__ctx_fetch_and_index", {"requests": [{"source": "Missing URL"}]})
        fields = self.run_guard(event)["hookSpecificOutput"]
        self.assertIn("verification unavailable", fields["additionalContext"])
        self.assertNotIn("permissionDecision", fields)
        self.assertFalse(self.state_root.exists())

    def test_malformed_native_input_reports_payload_free_error_but_unmarked_is_silent(self):
        invalid = "this is not JSON with fixture-sensitive-text"
        result = subprocess.run([sys.executable, str(GUARD)], input=invalid, text=True,
                                capture_output=True, env=self.env, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("scope could not be established", result.stderr)
        self.assertNotIn("fixture-sensitive-text", result.stderr)
        env = dict(self.env)
        env.pop("NAS_RESEARCH_COORDINATOR_ROLE")
        self.assertIsNone(self.run_guard(env=env, raw=invalid))

    def test_unrelated_tool_and_event_are_silent_without_state(self):
        for event in [self.event("Bash"), self.event("WebSearch", hook_event_name="PostToolUse"),
                      self.event("mcp__unrelated__ctx_fetch_and_index")]:
            self.assertIsNone(self.run_guard(event))
        self.assertFalse(self.state_root.exists())

    def test_parallel_native_calls_do_not_lose_fetch_counts_or_log_records(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(self.run_guard, self.fetch(f"https://docs.example.test/{n}"))
                       for n in range(16)]
            for future in futures:
                future.result()
        records = self.records()
        self.assertEqual(len(records), 16)
        self.assertEqual([r["fetches_this_turn"] for r in records], list(range(1, 17)))
        self.assertEqual(len({r["url"] for r in records}), 16)
        self.assertEqual(json.loads((self.directory() / "turn.json").read_text())["fetches"], 16)

    def test_session_path_is_hashed_and_verification_log_is_bounded(self):
        unusual_session = "../../a-session-with-slashes"
        env = {**self.env, "NAS_RESEARCH_COORDINATOR_SESSION_ID": unusual_session}
        requests = [{"url": f"https://docs.example.test/{n}", "source": "Bounded public reference"}
                    for n in range(270)]
        output = self.run_guard(self.event("mcp__context_mode__ctx_fetch_and_index", {"requests": requests},
                                           session_id=unusual_session), env=env)
        self.assertIn("this turn: 270", output["hookSpecificOutput"]["additionalContext"])
        self.assertRegex(self.directory().name, r"^[0-9a-f]{64}$")
        records = self.records()
        self.assertEqual(len(records), 256)
        self.assertEqual(records[0]["fetches_this_turn"], 15)
        self.assertEqual(records[-1]["fetches_this_turn"], 270)


if __name__ == "__main__":
    unittest.main()
