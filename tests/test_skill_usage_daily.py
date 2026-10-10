"""Counts-only daily native reports and rendered timer, with no live clients."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/skill-usage"))
import skill_usage as usage


def daily_module():
    spec = importlib.util.spec_from_file_location("daily_skill_usage", ROOT / "tools/skill-usage/daily_skill_usage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginUsageTests(unittest.TestCase):
    def test_native_plugin_namespace_is_joined_to_its_trial_name(self):
        manifest = usage.load_manifest(ROOT / "tests/fixtures/skill_usage/manifest.json")
        skill = dict(manifest["skills"][0], name="claude-api", claude_skill_name="claude-api:claude-api", codex_enabled=False)
        manifest["skills"] = [skill]
        report = usage.build_report(manifest, claude={"rows": {"claude-api:claude-api": {
            "uses": 3, "context_tokens": 10, "last_used": "today"}}},
            codex_scan=usage.scan_codex_roots([], ["claude-api"], now=usage.parse_iso("2026-10-11T00:00:00Z"),
                                              windows=[7, 30]),
            lock_installed_at={"claude-api": "2026-10-10T00:00:00Z"},
            now=usage.parse_iso("2026-10-11T00:00:00Z"), windows=[7])
        self.assertEqual(3, report["skills"][0]["claude"]["uses"])
        self.assertEqual(1, report["skills"][0]["age_days"])


class CodexUseTests(unittest.TestCase):
    def test_duplicate_rollout_parts_share_one_session_skill_use(self):
        now = usage.parse_iso("2026-10-10T00:00:00Z")
        rows = [{"type": "session_meta", "payload": {"id": "synthetic-session"}},
                {"timestamp": "2026-10-09T23:00:00Z", "type": "response_item", "payload": {
                    "type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": "/fixture/gh-fix-ci/SKILL.md"})}}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(2):
                (root / f"rollout-part-{index}.jsonl").write_text("\n".join(map(json.dumps, rows)))
            scan = usage.scan_codex_roots([root], ["gh-fix-ci"], now=now, windows=[7])
            self.assertEqual(2, scan["counts"]["gh-fix-ci"][7]["skill_md_reads"])
            self.assertEqual(1, scan["uses"]["gh-fix-ci"][7])

    def test_bulk_scan_inflates_raw_reads_but_not_once_per_session_use(self):
        names = ["gh-fix-ci", "typesafe-ai", *["document-" + str(i) for i in range(50)]]
        now = usage.parse_iso("2026-10-10T00:00:00Z")
        def record(payload):
            return {"timestamp": "2026-10-09T23:00:00Z", "type": "response_item", "payload": payload}
        def call(text):
            return record({"type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": text})})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bulk = " ".join("/fixture/" + name + "/SKILL.md" for name in names)
            (root / "rollout-bulk.jsonl").write_text("\n".join(json.dumps(r) for r in [call(bulk), call(bulk)]))
            scan = usage.scan_codex_roots([root], names, now=now, windows=[7])
            self.assertEqual(2, scan["counts"]["gh-fix-ci"][7]["skill_md_reads"])
            self.assertEqual(0, scan["uses"]["gh-fix-ci"][7])
            normal = [call("/fixture/gh-fix-ci/SKILL.md")] * 3 + [record({"type": "message", "role": "user",
                      "content": [{"type": "input_text", "text": "$gh-fix-ci and $typesafe-ai"}]})]
            (root / "rollout-normal.jsonl").write_text("\n".join(json.dumps(r) for r in normal))
            scan = usage.scan_codex_roots([root], names, now=now, windows=[7])
            self.assertEqual(5, scan["counts"]["gh-fix-ci"][7]["skill_md_reads"])
            self.assertEqual(1, scan["uses"]["gh-fix-ci"][7])
            self.assertEqual(1, scan["uses"]["typesafe-ai"][7])


class DailyProjectionTests(unittest.TestCase):
    def test_groups_keep_names_and_counts_and_unknown_is_not_zero(self):
        daily = daily_module()
        host = {"kind": "skill_invoke_rate_report", "skills": [{"name": "gh-fix-ci", "claude": {"uses": 0},
                "codex": {"counts": {"7": {"skill_md_reads": 4, "name_mentions": 1}}, "use_counts": {"7": 1}}, "prompt": "PRIVATE"}],
                "codex_use_groups": {"7": {"workers": {"gh-fix-ci": 1}, "workers_by_role": {"worker": {"gh-fix-ci": 1}}}}}
        codex = {"kind": "codex_lane_usage_report", "groups": {"workers": {"sessions": 2,
                 "skill_md_reads": {"gh-fix-ci": 4, "bad/account": 99}}, "workers_by_role": {
                 "worker": {"sessions": 2, "skill_md_reads": {"gh-fix-ci": 4}}}}}
        claude = {"kind": "claude_child_lane_usage", "groups": {"by_spawn_and_agent_type": {
                  "workflow": {"security-reviewer": {"children": 1, "skill_calls": {"security-audit": 2}}}}},
                  "main": {"skill_calls": {}}, "actors": [{"prompt": "PRIVATE", "path": "/private/credential"}]}
        report = daily.project_reports(host, codex, claude, now="2026-10-10T00:00:00Z", window=7)
        self.assertEqual(1, report["lanes"][0]["skills"][0]["count"])
        self.assertEqual(4, report["lanes"][0]["skills"][0]["raw_reads"])
        self.assertTrue(any(row["lane"] == "workflow:security-reviewer" and row["skills"][0]["count"] == 2
                            for row in report["lanes"]))
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertNotIn("bad/account", json.dumps(report))
        self.assertNotIn("credential", json.dumps(report))
        unknown = daily.project_reports(None, None, None, now="2026-10-10T00:00:00Z", window=7)
        self.assertIsNone(unknown["host"])
        self.assertIsNone(unknown["lanes"])

    def test_daily_run_uses_the_three_existing_native_tools(self):
        daily = daily_module()
        commands = []
        def runner(command, **kwargs):
            commands.append(command)
            if "--run-skill-doctor" in command:
                result = {"kind": "skill_invoke_rate_report", "skills": []}
            elif "--lanes" in command:
                result = {"kind": "codex_lane_usage_report", "groups": {}}
            else:
                result = {"kind": "claude_child_lane_usage", "groups": {}}
            return subprocess.CompletedProcess(command, 0, json.dumps(result), "")
        daily.collect_reports([Path("/fixture/codex")], [Path("/fixture/claude")], window=7,
                              now=usage.parse_iso("2026-10-10T00:00:00Z"), runner=runner)
        self.assertEqual(3, len(commands))
        self.assertIn("--run-skill-doctor", commands[0])
        self.assertIn("--window", commands[0])
        self.assertIn("--lanes", commands[1])
        self.assertIn("--lanes-sweep", commands[2])
        self.assertIn("--since", commands[2])

    def test_timer_render_targets_the_selected_live_clone(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            daily.render_units(dest, Path("/fixture/live clone"), Path(sys.executable), Path("/fixture/bin/node"))
            service = (dest / "skill-invoke-rate.service").read_text()
            timer = (dest / "skill-invoke-rate.timer").read_text()
            self.assertIn('"/fixture/live clone/tools/skill-usage/daily_skill_usage.py"', service)
            self.assertIn("--codex-root", service)
            self.assertIn("--claude-root", service)
            self.assertIn("OnCalendar=daily", timer)
            self.assertNotIn("@REPOSITORY@", service)

    @unittest.skipUnless(shutil.which("systemd-analyze"), "native systemd verifier unavailable")
    def test_native_user_unit_verification_needs_no_session_or_install(self):
        daily = daily_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            daily.render_units(root, ROOT, Path(sys.executable), Path(shutil.which("node")))
            result = subprocess.run([shutil.which("systemd-analyze"), "--user", "--man=no", "verify",
                                     str(root / "skill-invoke-rate.service"), str(root / "skill-invoke-rate.timer")],
                                    env={"HOME": str(root), "PATH": os.defpath, "XDG_RUNTIME_DIR": str(runtime)},
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / ".config/systemd/user").exists())


if __name__ == "__main__":
    unittest.main()
