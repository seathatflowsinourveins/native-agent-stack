"""Offline contracts for the fleet page's native source adapter."""

import importlib.util
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
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
        if command[0] == sys.executable:
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
        producer = self.state / "coordination/ns2604-coop/tools/fleet_block.py"
        producer.parent.mkdir(parents=True)
        producer.write_text("# isolated fixture producer; transport is mocked\n", encoding="utf-8")
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

    def test_cc_credit_policy_supplies_ceiling_without_changing_actual_spend(self):
        self.write_json("coordination/command-center/pages/cc-now.json", {"schema": "cc-now/1", "updated_utc": "2026-10-08T22:02:00Z", "api_credit": {"ceiling_usd": 200, "stop_and_report_at_usd": 150, "table_at_caps_usd": 194.41, "table_expected_usd": 117, "key": "PRIVATE-FORBIDDEN"}})
        sdk = self.collect()["sdk"]
        self.assertEqual(sdk["ceiling_usd"], 200)
        self.assertEqual(sdk["stop_and_report_at_usd"], 150)
        self.assertIsNone(sdk["spend_usd"])
        self.assertEqual(sdk["status"], "ledger unavailable")
        self.assertNotIn("PRIVATE-FORBIDDEN", json.dumps(sdk))
        self.assertEqual(sdk["ceiling_read_utc"], "2026-10-08T22:02:00Z")

    def test_native_ledger_actual_sum_is_used_without_counting_reserved_caps(self):
        self.direct["api_spend_ledger"] = {"rows": 368, "last": "2026-10-08T22:09:00Z", "sums": {"actual_usd": 17.4321, "max_usd": 800}}
        sdk = self.collect()["sdk"]
        self.assertEqual(sdk["spend_usd"], 17.4321)
        self.assertEqual(sdk["ledger_rows"], 368)
        self.assertEqual(sdk["ledger_source"], "coop-fleet api_spend_ledger")
        self.assertIsNone(sdk["jobs_running"])

    def test_direct_sections_and_separately_dated_coop_subagents(self):
        view = self.collect()
        self.assertEqual(view["fleet_source"], "direct native")
        self.assertEqual(view["at"], self.direct["at"])
        self.assertEqual(view["claude_subagents_running"]["coop"], {"names": ["coop-read-a", "coop-read-b"], "count": 2, "read_utc": self.snapshot["at"], "source": "snapshot"})
        self.assertEqual(view["claude_subagents_running"]["cc"]["names"], ["review-a"])
        self.assertEqual(view["source_times"]["fleet_direct"], self.direct["at"])
        self.assertEqual(view["source_times"]["fleet_snapshot"], self.snapshot["at"])
        self.assertTrue(all(command[-2:] == ["--json", "--no-gh"] for command in self.runner.commands if command[0] == sys.executable))

    def test_failed_direct_read_falls_back_without_retiming_snapshot(self):
        self.runner.fleet_fail = True
        view = self.collect()
        self.assertEqual(view["fleet_source"], "snapshot fallback")
        self.assertEqual(view["at"], self.snapshot["at"])
        self.assertIsNone(view["source_times"]["fleet_direct"])
        self.assertEqual(view["claude_subagents_running"]["cc"]["names"], ["review-a"])
        self.assertEqual(view["claude_subagents_running"]["cc"]["source"], "cc-now")
        self.assertEqual(view["claude_subagents_running"]["native_cc"]["names"], ["old-review"])

    def test_missing_tokens_and_missing_subagent_counts_are_unknown(self):
        self.direct["lanes_live"][0].pop("subagents_running")
        lane = self.collect()["lanes_live"][0]
        for key in ["subagents_running", "subagents_spawned", "subagent_uncached_share_pct", "subagent_uncached_tokens", "lane_uncached_tokens"]:
            self.assertIsNone(lane[key])

    def test_missing_ledger_keeps_spend_ceiling_and_job_count_unknown(self):
        sdk = self.collect()["sdk"]
        self.assertEqual(sdk["status"], "ledger unavailable")
        self.assertIsNone(sdk["spend_usd"])
        self.assertIsNone(sdk["read_utc"])
        self.assertIsNone(sdk["ceiling_usd"])
        self.assertIsNone(sdk["jobs_running"])

    def test_existing_unrecognized_ledger_does_not_invent_zero_spend(self):
        self.write_json("coordination/api-actions-20261008/api-actions-ledger.jsonl", {"event": "job-started", "prompt": "PRIVATE-PROMPT"})
        sdk = self.collect()["sdk"]
        self.assertEqual(sdk["status"], "ledger spend not observed")
        self.assertIsNone(sdk["spend_usd"])
        self.assertIsNone(sdk["ceiling_usd"])

    def test_explicit_native_ledger_actual_events_and_reserved_caps(self):
        path = self.state / "coordination/api-actions-20261008/api-actions-ledger.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('\n'.join(json.dumps(row) for row in [{"actual_usd": 1.25, "max_usd": 10}, {"actual_usd": 2.5}]), encoding="utf-8")
        sdk = self.collect()["sdk"]
        self.assertEqual(sdk["spend_usd"], 3.75)
        self.assertEqual(sdk["reserved_max_usd"], 10)
        self.assertIsNone(sdk["ceiling_usd"])

    def test_single_native_actions_call_and_cache_ttl(self):
        self.collect()
        self.collect(30)
        self.collect(539)
        self.assertEqual(sum(command[0] == "gh" for command in self.runner.commands), 1)
        self.collect(540)
        gh_commands = [command for command in self.runner.commands if command[0] == "gh"]
        self.assertEqual(len(gh_commands), 2)
        self.assertEqual(gh_commands[0][-1], fleet_data.RUN_FIELDS)
        self.assertNotIn("displayTitle", gh_commands[0][-1])
        self.assertEqual(sum(command[0] == sys.executable for command in self.runner.commands), 4)

    def test_concurrent_refreshes_share_one_actions_call(self):
        with patch.object(fleet_data.time, "time", return_value=self.now):
            with ThreadPoolExecutor(max_workers=4) as workers:
                views = list(workers.map(lambda _: fleet_data.collect(self.state, self.cache, self.root, self.runner), range(4)))
        self.assertEqual(len(views), 4)
        self.assertEqual(sum(command[0] == "gh" for command in self.runner.commands), 1)

    def test_failure_retains_old_run_time_and_suppresses_retry_until_ttl(self):
        original = self.collect()["actions"]["read_utc"]
        self.runner.gh_fail = True
        failed = self.collect(540)
        self.assertEqual(failed["actions"]["read_utc"], original)
        self.assertTrue(failed["actions"]["stale"])
        self.assertEqual(len(failed["API_errors"]), 1)
        next_view = self.collect(541)
        self.assertEqual(next_view["API_errors"], [])
        self.assertEqual(sum(command[0] == "gh" for command in self.runner.commands), 2)
        self.assertNotIn("private error text", json.dumps(next_view))

    def test_whitelist_excludes_tasks_prompts_emails_and_opaque_tokens(self):
        self.direct.update({"text": "PRIVATE-PROMPT", "prompt": "PRIVATE-PROMPT", "task": "PRIVATE-TASK"})
        self.direct["lanes_live"][0].update({"task": "PRIVATE-TASK", "account": "operator@example.test", "flags": ["operator@example.test", "PRIVATE PROMPT"], "subagent_models": {"ghp_" + "X" * 40: 1}})
        self.direct["pool_accounts"].append({"account": "operator@example.test", "used_pct": 10})
        self.runner.runs = [{"workflowName": "harness-audit", "status": "completed", "conclusion": "success", "databaseId": 123, "startedAt": "2026-10-08T21:00:00Z", "updatedAt": "2026-10-08T21:02:00Z", "url": "https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/123", "displayTitle": "PRIVATE-PROMPT", "headBranch": "operator@example.test"}]
        view = self.collect()
        serialized = json.dumps(view) + (self.cache / "fleet-actions.json").read_text()
        for text in ["PRIVATE-PROMPT", "PRIVATE-TASK", "operator@example.test", "ghp_" + "X" * 40, "displayTitle", "headBranch"]:
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

    def test_real_exec_read_labels_keep_name_and_tier(self):
        self.direct["exec_reads_in_flight"] = ["read-a[fast]", "read-b[standard]"]
        view = self.collect()
        self.assertEqual(view["exec_reads_in_flight"], [{"name": "read-a", "tier": "fast"}, {"name": "read-b", "tier": "standard"}])

    def test_cc_current_roster_uses_cc_time_when_native_source_disagrees(self):
        self.write_json("coordination/command-center/pages/cc-now.json", {"schema": "cc-now/1", "updated_utc": "2026-10-08T22:02:00Z", "cc_agents": {"running": [{"name": "cc-current", "type": "Explore"}]}})
        view = self.collect()
        group = view["claude_subagents_running"]["cc"]
        self.assertEqual(group["names"], ["cc-current"])
        self.assertEqual(group["read_utc"], "2026-10-08T22:02:00Z")
        self.assertEqual(group["source"], "cc-now")
        self.assertEqual(view["claude_subagents_running"]["native_cc"]["names"], ["review-a"])

    def test_absent_null_and_malformed_rosters_remain_unknown_without_fallback(self):
        (self.state / "coordination/ns2604-coop/watchers/fleet-now.json").unlink()
        for field in ("lanes_live", "lanes_parked", "claude_sessions"):
            original = self.direct.pop(field)
            try:
                for value in (None, {}, "invalid"):
                    with self.subTest(field=field, value=value):
                        self.direct[field] = value
                        view = self.collect()
                        self.assertIsNone(view[field])
                        self.assertEqual(view["availability"][field]["status"], "not reported")
            finally:
                self.direct[field] = original

    def test_explicit_empty_rosters_are_reported_zero_and_zero_subagents_survive(self):
        self.direct.update(lanes_live=[], lanes_parked=[], claude_sessions=[])
        view = self.collect()
        for field in ("lanes_live", "lanes_parked", "claude_sessions"):
            self.assertEqual(view[field], [])
            self.assertEqual(view["availability"][field]["status"], "reported")
        self.direct["lanes_live"] = [{"lane": "active", "subagents_running": 0}]
        self.assertEqual(self.collect()["lanes_live"][0]["subagents_running"], 0)

    def test_snapshot_ledger_keeps_snapshot_date_and_missing_tiers_are_unknown(self):
        self.snapshot["api_spend_ledger"] = {"rows": 1, "last": "2026-10-08T21:59:00Z", "sums": {"actual_usd": 2.5}}
        self.write_json("coordination/ns2604-coop/watchers/fleet-now.json", self.snapshot)
        (self.state / "coordination/command-center/lane-tiers.json").unlink()
        self.runner.fleet_fail = True
        view = self.collect()
        self.assertEqual(view["sdk"]["read_utc"], self.snapshot["at"])
        self.assertEqual(view["source_times"]["api_ledger"], self.snapshot["at"])
        self.assertEqual(view["tiers"]["availability"], "not reported")
        self.assertIsNone(view["tiers"]["fast"])

    def test_snapshot_symlink_cannot_read_outside_synthetic_credentials(self):
        outside = self.state.parent / "outside/credentials.json"
        outside.parent.mkdir()
        outside.write_text(json.dumps({**self.direct, "lanes_live": [{"lane": "outside-read-sentinel"}]}), encoding="utf-8")
        snapshot = self.state / "coordination/ns2604-coop/watchers/fleet-now.json"
        snapshot.unlink()
        snapshot.symlink_to(outside)
        self.runner.fleet_fail = True
        view = self.collect()
        self.assertNotIn("outside-read-sentinel", json.dumps(view))
        self.assertIsNone(view["lanes_live"])

    def test_predictable_cache_temporary_symlink_does_not_overwrite_outside_file(self):
        self.cache.mkdir()
        outside = self.state.parent / "outside-cache-sentinel"
        outside.write_text("untouched outside fixture", encoding="utf-8")
        (self.cache / "fleet-actions.json.tmp").symlink_to(outside)
        self.collect()
        self.assertEqual(outside.read_text(), "untouched outside fixture")
        self.assertTrue((self.cache / "fleet-actions.json").is_file())

    def test_symlink_lock_and_cache_destinations_skip_native_actions(self):
        self.cache.mkdir()
        outside = self.state.parent / "outside-lock-fixture"
        outside.write_text("untouched", encoding="utf-8")
        for name in ("fleet-actions.lock", "fleet-actions.json"):
            with self.subTest(name=name):
                path = self.cache / name
                if path.exists():
                    path.unlink()
                path.symlink_to(outside)
                self.runner.commands.clear()
                view = self.collect()
                self.assertFalse(any(command[0] == "gh" for command in self.runner.commands))
                self.assertTrue(view["actions"]["stale"])
                self.assertEqual(outside.read_text(), "untouched")
                path.unlink()

    def test_symlink_producer_and_workflow_are_not_opened_or_executed(self):
        outside = self.state.parent / "outside-producer.py"
        outside.write_text("# controlled external fixture\n", encoding="utf-8")
        producer = self.state / "coordination/ns2604-coop/tools/fleet_block.py"
        producer.unlink()
        producer.symlink_to(outside)
        workflows = self.root / ".github/workflows"
        (workflows / "audit.yml").unlink()
        workflow = self.state.parent / "outside-workflow.yml"
        workflow.write_text("name: outside-model-workflow\nsteps:\n - uses: anthropics/claude-code-action@pin\n", encoding="utf-8")
        (workflows / "audit.yml").symlink_to(workflow)
        view = self.collect()
        self.assertFalse(any(command[0] == sys.executable for command in self.runner.commands))
        self.assertEqual(view["actions"]["workflow_names"], [])
        self.assertEqual(view["fleet_source"], "snapshot fallback")

    def test_every_snapshot_child_is_bounded_regular_and_receipted(self):
        paths = [
            "coordination/ns2604-coop/watchers/fleet-now.json",
            "coordination/command-center/pages/cc-now.json",
            "coordination/command-center/lane-tiers.json",
            "coordination/api-actions-20261008/api-actions-ledger.jsonl",
        ]
        outside = self.state.parent / "outside/credentials.json"
        outside.parent.mkdir()
        outside.write_text(json.dumps({"spend_usd": 999, "default": "outside-policy", "schema": "cc-now/1", "cc_agents": {"running": [{"name": "outside-agent"}]}}), encoding="utf-8")
        for relative in paths:
            with self.subTest(relative=relative):
                path = self.state / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                original = path.read_bytes() if path.is_file() else None
                if path.exists():
                    path.unlink()
                path.symlink_to(outside)
                try:
                    view = self.collect()
                    source = next(row for row in view["source_inputs"] if row["path"] == str(path))
                    self.assertEqual(source["status"], "unavailable")
                    self.assertIsNone(source["sha256"])
                    self.assertNotIn("outside-agent", json.dumps(view))
                    self.assertNotEqual(view["sdk"]["spend_usd"], 999)
                finally:
                    path.unlink()
                    if original is not None:
                        path.write_bytes(original)
        view = self.collect()
        cc = self.state / paths[1]
        source = next(row for row in view["source_inputs"] if row["path"] == str(cc))
        self.assertEqual(source["sha256"], hashlib.sha256(cc.read_bytes()).hexdigest())
        self.assertEqual(source["bytes"], cc.stat().st_size)
        self.assertEqual(source["status"], "reported")

    def test_symlink_ancestor_cannot_supply_a_snapshot_or_actions_cache(self):
        watchers = self.state / "coordination/ns2604-coop/watchers"
        outside = self.state.parent / "outside-watchers"
        watchers.rename(outside)
        watchers.symlink_to(outside, target_is_directory=True)
        self.runner.fleet_fail = True
        outside_cache = self.state.parent / "outside-cache"
        outside_cache.mkdir()
        self.cache.symlink_to(outside_cache, target_is_directory=True)
        view = self.collect()
        self.assertIsNone(view["lanes_live"])
        self.assertTrue(view["actions"]["stale"])
        self.assertEqual(list(outside_cache.iterdir()), [])
        self.assertFalse(any(command[0] == "gh" for command in self.runner.commands))

    def test_fifo_and_oversized_json_do_not_block_or_read_as_rosters(self):
        snapshot = self.state / "coordination/ns2604-coop/watchers/fleet-now.json"
        snapshot.unlink()
        os.mkfifo(snapshot)
        self.runner.fleet_fail = True
        view = self.collect()
        self.assertIsNone(view["lanes_live"])
        snapshot.unlink()
        snapshot.write_text("x" * (fleet_data.MAX_SOURCE_BYTES + 1), encoding="utf-8")
        view = self.collect()
        self.assertIsNone(view["lanes_live"])
        self.assertTrue(all(row["status"] == "unavailable" for row in view["source_inputs"] if row["path"] == str(snapshot)))

    def test_null_fast_list_preserves_unknown_policy_and_observed_running_tier(self):
        self.write_json("coordination/command-center/lane-tiers.json", {"schema": "lane-tiers/1", "default": "standard", "fast": None})
        view = self.collect()
        self.assertIsNone(view["tiers"]["fast"])
        self.assertEqual(view["tiers"]["availability"], "not reported")
        self.assertEqual(view["lanes_live"][0]["tier"], "standard")

    def test_malformed_named_groups_are_unknown_and_have_source_reasons(self):
        self.write_json("coordination/command-center/pages/cc-now.json", {"schema": "cc-now/1", "updated_utc": "2026-10-08T22:02:00Z", "cc_agents": {"running": [{"bad": "fixture"}]}})
        view = self.collect()
        self.assertIsNone(view["cc_agents"]["running_count"])
        self.assertIsNone(view["claude_subagents_running"]["cc"]["names"])
        self.assertEqual(view["availability"]["cc_agents"]["status"], "not reported")

    def test_producer_execution_receipt_matches_sealed_bytes_and_public_arguments(self):
        view = self.collect()
        producer = self.state / "coordination/ns2604-coop/tools/fleet_block.py"
        source = next(row for row in view["source_inputs"] if row["path"] == str(producer))
        self.assertEqual(source["execution"]["sha256"], hashlib.sha256(producer.read_bytes()).hexdigest())
        self.assertEqual(source["execution"]["bytes"], producer.stat().st_size)
        self.assertEqual(source["execution"]["status"], "completed")
        command = next(command for command in self.runner.commands if command[0] == sys.executable)
        self.assertEqual(command[1:3], ["-I", "-c"])
        self.assertEqual(command[-2:], ["--json", "--no-gh"])
        self.assertNotEqual(command[1], str(producer))


if __name__ == "__main__":
    unittest.main()
