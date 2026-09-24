"""Unit tests for tools/adoption/apply_claude_settings.py's merge, backup,
symlink-refusal, atomic-write and idempotency behavior. All I/O happens in a
temporary directory; no real ~/.claude/settings.json is ever touched.
"""

import json
import os
import stat
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import apply_claude_settings as acs  # noqa: E402


class MergeSettingsTests(unittest.TestCase):
    def test_template_scalar_wins(self):
        base = {"model": "old-model", "effortLevel": "medium"}
        template = {"model": "opus[1m]", "effortLevel": "xhigh"}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["model"], "opus[1m]")
        self.assertEqual(merged["effortLevel"], "xhigh")

    def test_base_only_scalar_is_kept(self):
        base = {"theme": "dark", "customField": "keep-me"}
        template = {"theme": "dark"}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["customField"], "keep-me")

    def test_model_settings_deep_merge(self):
        base = {"modelSettings": {"claude-sonnet-5": {"effortLevel": "xhigh"}}}
        template = {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["modelSettings"]["claude-sonnet-5"]["effortLevel"], "xhigh")
        self.assertEqual(merged["modelSettings"]["claude-opus-5-5"]["effortLevel"], "xhigh")

    def test_model_settings_template_field_wins_within_same_model(self):
        base = {"modelSettings": {"claude-opus-5-5": {"effortLevel": "medium", "other": "keep"}}}
        template = {"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["modelSettings"]["claude-opus-5-5"]["effortLevel"], "xhigh")
        self.assertEqual(merged["modelSettings"]["claude-opus-5-5"]["other"], "keep")

    def test_env_merges_with_template_precedence(self):
        base = {"env": {"CUSTOM": "1", "OVERRIDDEN": "old"}}
        template = {"env": {"OVERRIDDEN": "new", "TEMPLATE_ONLY": "2"}}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["env"]["CUSTOM"], "1")
        self.assertEqual(merged["env"]["OVERRIDDEN"], "new")
        self.assertEqual(merged["env"]["TEMPLATE_ONLY"], "2")

    def test_hooks_combine_per_event_deduplicated_by_command(self):
        base = {
            "hooks": {
                "SessionStart": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "existing-hook"}]},
                ],
            }
        }
        template = {
            "hooks": {
                "SessionStart": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "existing-hook"}]},
                    {"matcher": "startup|resume", "hooks": [{"type": "command", "command": "guard-hook"}]},
                ],
            }
        }
        merged = acs.merge_settings(base, template)
        session_start = merged["hooks"]["SessionStart"]
        matcher_empty = next(g for g in session_start if g.get("matcher") == "")
        commands = [h["command"] for h in matcher_empty["hooks"]]
        self.assertEqual(commands, ["existing-hook"])  # not duplicated
        matcher_guard = next(g for g in session_start if g.get("matcher") == "startup|resume")
        self.assertEqual([h["command"] for h in matcher_guard["hooks"]], ["guard-hook"])

    def test_hooks_new_event_is_added_wholesale(self):
        base = {"hooks": {}}
        template = {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "x"}]}]}}
        merged = acs.merge_settings(base, template)
        self.assertIn("Stop", merged["hooks"])

    def test_permissions_deny_rule_is_kept_when_template_repeats_it(self):
        base = {"permissions": {"deny": ["Agent(codex:codex-rescue)"], "defaultMode": "bypassPermissions"}}
        template = {"permissions": {"deny": ["Agent(codex:codex-rescue)"], "defaultMode": "bypassPermissions"}}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["permissions"]["deny"], ["Agent(codex:codex-rescue)"])

    def test_hook_is_deduplicated_across_groups_of_the_event(self):
        # The host runs the guard under an unmatched group; the template lists it
        # under "startup|resume": it must not be added a second time.
        base = {"hooks": {"SessionEnd": [
            {"matcher": "", "hooks": [{"type": "command", "command": "memory-hook"}]},
            {"hooks": [{"type": "command", "command": "python3 /h/.claude/hooks/guard.py 2>/dev/null || true"}]},
        ]}}
        template = {"hooks": {"SessionEnd": [
            {"matcher": "", "hooks": [{"type": "command", "command": "memory-hook"}]},
            {"hooks": [{"type": "command", "command": 'python3 "/h/.claude/hooks/guard.py" 2>/dev/null || true'}]},
        ]}}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["hooks"], base["hooks"])

    def test_absent_and_empty_matchers_keep_their_own_groups(self):
        base = {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "a"}]},
            {"matcher": "", "hooks": [{"type": "command", "command": "b"}]},
        ]}}
        template = {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "c"}]},
            {"matcher": "", "hooks": [{"type": "command", "command": "d"}]},
        ]}}
        groups = acs.merge_settings(base, template)["hooks"]["SessionStart"]
        self.assertEqual(len(groups), 2)
        self.assertNotIn("matcher", groups[0])
        self.assertEqual([h["command"] for h in groups[0]["hooks"]], ["a", "c"])
        self.assertEqual([h["command"] for h in groups[1]["hooks"]], ["b", "d"])

    def test_host_only_nested_keys_are_kept(self):
        base = {"permissions": {"allow": ["Bash(ls)"], "deny": ["X"], "defaultMode": "default"},
                "enabledPlugins": {"host@plugin": True},
                "statusLine": {"type": "command", "command": "old", "padding": 1}}
        template = {"permissions": {"deny": ["X", "Y"], "defaultMode": "bypassPermissions"},
                    "enabledPlugins": {"tpl@plugin": True},
                    "statusLine": {"type": "command", "command": "new"}}
        merged = acs.merge_settings(base, template)
        self.assertEqual(merged["permissions"], {"allow": ["Bash(ls)"], "deny": ["X", "Y"], "defaultMode": "bypassPermissions"})
        self.assertEqual(merged["enabledPlugins"], {"host@plugin": True, "tpl@plugin": True})
        self.assertEqual(merged["statusLine"], {"type": "command", "command": "new", "padding": 1})


class ApplyIOTests(unittest.TestCase):
    def _write(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def test_refuses_a_symlinked_target(self):
        with self._tmp() as tmp:
            real = tmp / "real-settings.json"
            self._write(real, {})
            link = tmp / "settings.json"
            link.symlink_to(real)
            template = tmp / "template.json"
            self._write(template, {"model": "opus[1m]"})
            with self.assertRaises(acs.ApplyError):
                acs.apply(template, link, dry_run=False)

    def test_dry_run_writes_nothing(self):
        with self._tmp() as tmp:
            target = tmp / "settings.json"
            self._write(target, {"model": "old"})
            template = tmp / "template.json"
            self._write(template, {"model": "opus[1m]"})
            acs.apply(template, target, dry_run=True)
            on_disk = json.loads(target.read_text())
            self.assertEqual(on_disk["model"], "old")
            backups = list(tmp.glob("settings.json.bak.*"))
            self.assertEqual(backups, [])

    def test_apply_backs_up_and_writes_atomically_preserving_mode(self):
        with self._tmp() as tmp:
            target = tmp / "settings.json"
            self._write(target, {"model": "old"})
            os.chmod(target, 0o640)
            template = tmp / "template.json"
            self._write(template, {"model": "opus[1m]", "effortLevel": "xhigh"})
            acs.apply(template, target, dry_run=False)
            merged = json.loads(target.read_text())
            self.assertEqual(merged["model"], "opus[1m]")
            self.assertEqual(merged["effortLevel"], "xhigh")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
            backups = list(tmp.glob("settings.json.bak.*"))
            self.assertEqual(len(backups), 1)
            backed_up = json.loads(backups[0].read_text())
            self.assertEqual(backed_up["model"], "old")

    def test_apply_on_missing_target_creates_it(self):
        with self._tmp() as tmp:
            target = tmp / "nested" / "settings.json"
            template = tmp / "template.json"
            self._write(template, {"model": "opus[1m]"})
            acs.apply(template, target, dry_run=False)
            self.assertTrue(target.is_file())
            self.assertEqual(json.loads(target.read_text())["model"], "opus[1m]")

    def test_applying_twice_is_idempotent(self):
        with self._tmp() as tmp:
            target = tmp / "settings.json"
            self._write(target, {
                "model": "old",
                "hooks": {"SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "x"}]}]},
            })
            template = tmp / "template.json"
            self._write(template, {
                "model": "opus[1m]",
                "hooks": {"SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "x"}]}]},
            })
            acs.apply(template, target, dry_run=False)
            first = json.loads(target.read_text())
            acs.apply(template, target, dry_run=False)
            second = json.loads(target.read_text())
            self.assertEqual(first, second)
            matcher_empty = next(g for g in second["hooks"]["SessionStart"] if g.get("matcher") == "")
            self.assertEqual([h["command"] for h in matcher_empty["hooks"]], ["x"])

    def test_never_touches_a_different_named_file(self):
        with self._tmp() as tmp:
            claude_json = tmp / ".claude.json"
            self._write(claude_json, {"oauthAccount": "should-not-be-touched"})
            target = tmp / "settings.json"
            self._write(target, {"model": "old"})
            template = tmp / "template.json"
            self._write(template, {"model": "opus[1m]"})
            acs.apply(template, target, dry_run=False)
            self.assertEqual(json.loads(claude_json.read_text())["oauthAccount"], "should-not-be-touched")

    class _tmp:
        def __enter__(self):
            import tempfile
            self._ctx = tempfile.TemporaryDirectory()
            return Path(self._ctx.name)

        def __exit__(self, *exc):
            self._ctx.cleanup()
            return False


class BackupTests(unittest.TestCase):
    def test_same_second_backups_never_overwrite(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "settings.json"
            target.write_text('{"v": 1}')
            first = acs.write_backup(target)
            target.write_text('{"v": 2}')
            second = acs.write_backup(target)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(), '{"v": 1}')
            self.assertEqual(second.read_text(), '{"v": 2}')


class RobustnessTests(unittest.TestCase):
    def test_malformed_hook_groups_do_not_crash(self):
        base = {"hooks": {"Stop": [{"matcher": "", "hooks": 5}, "not-a-group"]}}
        template = {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "x"}]}]}}
        merged = acs.merge_settings(base, template)
        commands = [h["command"] for g in merged["hooks"]["Stop"] if isinstance(g, dict)
                    for h in (g["hooks"] if isinstance(g["hooks"], list) else [])]
        self.assertEqual(commands, ["x"])

    def test_dangling_symlink_backup_name_is_skipped(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "settings.json"
            target.write_text("{}")
            with mock.patch.object(acs.time, "strftime", return_value="20260923T000000Z"):
                (Path(tmp) / "settings.json.bak.20260923T000000Z").symlink_to(Path(tmp) / "missing")
                backup = acs.write_backup(target)
            self.assertEqual(backup.name, "settings.json.bak.20260923T000000Z.1")
            self.assertEqual(backup.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()
