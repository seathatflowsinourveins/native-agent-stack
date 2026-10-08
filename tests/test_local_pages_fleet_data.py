"""Offline contracts for the fleet page's native source adapter."""

import importlib.util
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("local_pages_fleet_data", ROOT / "tools/local-pages/fleet_data.py")
fleet_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fleet_data)


class NativeRunner:
    def __init__(self, direct):
        self.direct = direct
        self.runs = []
        self.commands = []
        self.fleet_fail = False
        self.gh_fail = False

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        if command[0] == "python3":
            return subprocess.CompletedProcess(command, 1 if self.fleet_fail else 0, json.dumps(self.direct), "")
        if self.gh_fail:
            return subprocess.CompletedProcess(command, 1, "", "private error text must not be retained")
        return subprocess.CompletedProcess(command, 0, json.dumps(self.runs), "")


class FleetDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.state, self.cache, self.root = base / "state", base / "cache", base / "repo"
        self.now = 1791497400.0
        self.direct = {
            "schema": "coop-fleet/1", "at": "2026-10-08T22:10:00Z",
            "lanes_live": [{"lane": "g5-stars-gap", "status": "active", "tier": "standard", "cli_version": "0.162.0", "account": "10-09T00:00:00Z", "subagents_running": 1, "lane_model": "cx/gpt-6.1-sol"}],
            "lanes_parked": ["grand-catalog", "parked-default"],
            "claude_sessions": [{"name": "cc", "status": "active"}],
            "claude_subagents_running": {"coop": ["not-directly-visible"], "cc": ["review-a"], "api_actions": None},
            "exec_reads_in_flight": [], "sdk_jobs_running": None,
            "pool_accounts": [{"account": "10-09T00:00:00Z", "used_pct": 30.0}],
        }
        self.snapshot = {**self.direct, "at": "2026-10-08T22:00:00Z", "claude_subagents_running": {"coop": ["coop-read-a", "coop-read-b"], "cc": ["old-review"], "api_actions": None}}
        self.write_json("coordination/ns2604-coop/watchers/fleet-now.json", self.snapshot)
        self.write_json("coordination/command-center/pages/cc-now.json", {"schema": "cc-now/1", "updated_utc": "2026-10-08T22:02:00Z", "cc_agents": {"running": [{"name": "review-a", "type": "Explore", "task": "PRIVATE-TASK"}]}})
        self.write_json("coordination/command-center/lane-tiers.json", {"schema": "lane-tiers/1", "updated_utc": "2026-10-08T22:03:00Z", "default": "default", "fast": [], "parking": {"idle_minutes_default": 45, "idle_minutes_when_memory_tight": 15, "keep_alive": ["g5-stars-gap"]}, "codex_version": {"default": "0.162.0", "hold": {"grand-catalog": "0.161.0"}, "hold_until": {"grand-catalog": "gate opens"}}})
        workflows = self.root / ".github/workflows"
        workflows.mkdir(parents=True)
        (workflows / "audit.yml").write_text("name: harness-audit\njobs:\n  review:\n    steps:\n      - uses: anthropics/claude-code-action@pin\n", encoding="utf-8")
        self.runner = NativeRunner(self.direct)

    def write_json(self, relative, value):
        path = self.state / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def collect(self, offset=0):
        with patch.object(fleet_data.time, "time", return_value=self.now + offset):
            return fleet_data.collect(self.state, self.cache, self.root, self.runner)

    def test_direct_sections_and_separately_dated_coop_subagents(self):
        view = self.collect()
        self.assertEqual(view["fleet_source"], "direct native")
        self.assertEqual(view["at"], self.direct["at"])
        self.assertEqual(view["claude_subagents_running"]["coop"], {"names": ["coop-read-a", "coop-read-b"], "count": 2, "read_utc": self.snapshot["at"], "source": "snapshot"})
        self.assertEqual(view["claude_subagents_running"]["cc"]["names"], ["review-a"])
        self.assertEqual(view["source_times"]["fleet_direct"], self.direct["at"])
        self.assertEqual(view["source_times"]["fleet_snapshot"], self.snapshot["at"])
        self.assertTrue(all(command[-2:] == ["--json", "--no-gh"] for command in self.runner.commands if command[0] == "python3"))

    def test_failed_direct_read_falls_back_without_retiming_snapshot(self):
        self.runner.fleet_fail = True
        view = self.collect()
        self.assertEqual(view["fleet_source"], "snapshot fallback")
        self.assertEqual(view["at"], self.snapshot["at"])
        self.assertIsNone(view["source_times"]["fleet_direct"])
        self.assertEqual(view["claude_subagents_running"]["cc"]["names"], ["old-review"])

    def test_missing_tokens_and_missing_subagent_counts_are_unknown(self):
        self.direct["lanes_live"][0].pop("subagents_running")
        lane = self.collect()["lanes_live"][0]
        for key in ["subagents_running", "subagents_spawned", "subagent_uncached_share_pct", "subagent_uncached_tokens", "lane_uncached_tokens"]:
            self.assertIsNone(lane[key])

    def test_no_ledger_is_zero_spend_and_unknown_ceiling_and_job_count(self):
        sdk = self.collect()["sdk"]
        self.assertEqual(sdk["status"], "no spend yet")
        self.assertEqual(sdk["spend_usd"], 0)
        self.assertIsNone(sdk["ceiling_usd"])
        self.assertIsNone(sdk["jobs_running"])

    def test_existing_unrecognized_ledger_does_not_invent_zero_spend(self):
        self.write_json("coordination/api-actions-20261008/api-actions-ledger.jsonl", {"event": "job-started", "prompt": "PRIVATE-PROMPT"})
        sdk = self.collect()["sdk"]
        self.assertEqual(sdk["status"], "ledger spend not observed")
        self.assertIsNone(sdk["spend_usd"])
        self.assertIsNone(sdk["ceiling_usd"])

    def test_explicit_cumulative_ledger_amount_and_ceiling(self):
        path = self.state / "coordination/api-actions-20261008/api-actions-ledger.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('\n'.join(json.dumps(row) for row in [{"spend_usd": 1.25, "ceiling_usd": 10}, {"spend_usd": 2.5}]), encoding="utf-8")
        sdk = self.collect()["sdk"]
        self.assertEqual(sdk["spend_usd"], 2.5)
        self.assertEqual(sdk["ceiling_usd"], 10)

    def test_single_native_actions_call_and_cache_ttl(self):
        self.collect()
        self.collect(30)
        self.collect(599)
        self.assertEqual(sum(command[0] == "gh" for command in self.runner.commands), 1)
        self.collect(600)
        gh_commands = [command for command in self.runner.commands if command[0] == "gh"]
        self.assertEqual(len(gh_commands), 2)
        self.assertEqual(gh_commands[0][-1], fleet_data.RUN_FIELDS)
        self.assertNotIn("displayTitle", gh_commands[0][-1])
        self.assertEqual(sum(command[0] == "python3" for command in self.runner.commands), 4)

    def test_concurrent_refreshes_share_one_actions_call(self):
        with patch.object(fleet_data.time, "time", return_value=self.now):
            with ThreadPoolExecutor(max_workers=4) as workers:
                views = list(workers.map(lambda _: fleet_data.collect(self.state, self.cache, self.root, self.runner), range(4)))
        self.assertEqual(len(views), 4)
        self.assertEqual(sum(command[0] == "gh" for command in self.runner.commands), 1)

    def test_failure_retains_old_run_time_and_suppresses_retry_until_ttl(self):
        original = self.collect()["actions"]["read_utc"]
        self.runner.gh_fail = True
        failed = self.collect(600)
        self.assertEqual(failed["actions"]["read_utc"], original)
        self.assertTrue(failed["actions"]["stale"])
        self.assertEqual(len(failed["API_errors"]), 1)
        next_view = self.collect(601)
        self.assertEqual(next_view["API_errors"], [])
        self.assertEqual(sum(command[0] == "gh" for command in self.runner.commands), 2)
        self.assertNotIn("private error text", json.dumps(next_view))

    def test_whitelist_excludes_tasks_prompts_emails_and_opaque_tokens(self):
        self.direct.update({"text": "PRIVATE-PROMPT", "prompt": "PRIVATE-PROMPT", "task": "PRIVATE-TASK"})
        self.direct["lanes_live"][0].update({"task": "PRIVATE-TASK", "account": "operator@example.test", "flags": ["operator@example.test", "PRIVATE PROMPT"], "subagent_models": {"abcdefghijklmnopqrstuvwx1234567890": 1}})
        self.direct["pool_accounts"].append({"account": "operator@example.test", "used_pct": 10})
        self.runner.runs = [{"workflowName": "harness-audit", "status": "completed", "conclusion": "success", "databaseId": 123, "startedAt": "2026-10-08T21:00:00Z", "updatedAt": "2026-10-08T21:02:00Z", "url": "https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/123", "displayTitle": "PRIVATE-PROMPT", "headBranch": "operator@example.test"}]
        view = self.collect()
        serialized = json.dumps(view) + (self.cache / "fleet-actions.json").read_text()
        for text in ["PRIVATE-PROMPT", "PRIVATE-TASK", "operator@example.test", "abcdefghijklmnopqrstuvwx1234567890", "displayTitle", "headBranch"]:
            self.assertNotIn(text, serialized)
        self.assertEqual(len(view["actions"]["runs"]), 1)
        self.assertEqual(view["cc_agents"]["running"], [{"name": "review-a", "type": "Explore"}])

    def test_workflow_name_mentions_and_commented_invocations_are_excluded(self):
        workflows = self.root / ".github/workflows"
        (workflows / "plain.yml").write_text("name: claude-review\n# codex exec example\njobs:\n  test:\n    steps:\n      - run: python3 -m unittest\n", encoding="utf-8")
        self.runner.runs = [{"workflowName": "claude-review", "status": "completed", "databaseId": 12}, {"workflowName": "harness-audit", "status": "queued", "databaseId": 13}]
        view = self.collect()["actions"]
        self.assertEqual(view["workflow_names"], ["harness-audit"])
        self.assertEqual([row["workflowName"] for row in view["runs"]], ["harness-audit"])
        self.assertIn("Newest 100", view["scope"])

    def test_current_anonymous_pool_labels_preserve_all_six_accounts(self):
        labels = ["position 1", "fresh(21:00:52)", "fresh(21:00:58)", "fresh(21:03:04)", "fresh(21:03:06)", "fresh(21:03:07)"]
        self.direct["pool_accounts"] = [{"account": label, "used_pct": 25} for label in labels] + [{"account": label, "used_pct": 25} for label in ["operator@example.test", "PRIVATE PROMPT", "abcdefghijklmnopqrstuvwx1234567890", "fresh(99:99:99)"]]
        self.direct["lanes_live"][0]["account"] = labels[1]
        view = self.collect()
        self.assertEqual([row["account"] for row in view["pool_accounts"]], labels)
        self.assertEqual(view["lanes_live"][0]["account"], labels[1])

    def test_parked_actual_cli_unknown_and_hold_policy_is_separate(self):
        parked = self.collect()["lanes_parked"]
        self.assertIsNone(parked[0]["cli_version"])
        self.assertEqual(parked[0]["expected_cli_version"], "0.161.0")
        self.assertEqual(parked[1]["expected_cli_version"], "0.162.0")


if __name__ == "__main__":
    unittest.main()
