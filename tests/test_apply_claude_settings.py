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
        self.assertEqual(len(groups), 4)
        self.assertNotIn("matcher", groups[0])
        self.assertEqual([h["command"] for h in groups[0]["hooks"]], ["a"])
        self.assertEqual([h["command"] for h in groups[1]["hooks"]], ["b"])
        self.assertNotIn("matcher", groups[2])
        self.assertEqual([h["command"] for h in groups[2]["hooks"]], ["c"])
        self.assertEqual(groups[3]["matcher"], "")
        self.assertEqual([h["command"] for h in groups[3]["hooks"]], ["d"])

    def canonical_memory_and_other_entries(self):
        """The template's native-memory SubagentStart entry and a second entry with the same matcher, so one event holds
        two ownership groups (the carrier that used to be the second entry is held out of the default)."""
        memory = json.loads((ROOT / "adoption/templates/claude.settings.template.json")
                            .read_text(encoding="utf-8"))["hooks"]["SubagentStart"]
        self.assertEqual(len(memory), 1)
        other = {"matcher": "", "hooks": [{"type": "command", "timeout": 5,
                                           "command": 'python3 "${HOME}/.claude/hooks/example-subagent-hook.py" 2>/dev/null || true'}]}
        return memory + [other]

    def test_same_matcher_keeps_native_memory_and_other_entries_separate(self):
        canonical = self.canonical_memory_and_other_entries()
        base = {"hooks": {"SubagentStart": [canonical[0]]}}
        merged = acs.merge_settings(base, {"hooks": {"SubagentStart": canonical}})
        self.assertEqual(merged["hooks"]["SubagentStart"], canonical)
        self.assertEqual(acs.merge_settings(merged, {"hooks": {"SubagentStart": canonical}}), merged)

    def test_existing_mixed_entry_is_split_without_changing_hook_values_or_order(self):
        canonical = self.canonical_memory_and_other_entries()
        host = {"type": "command", "command": "true", "timeout": 7}
        original = canonical[0]["hooks"] + canonical[1]["hooks"] + [host]
        base = {"theme": "retained", "hooks": {"SubagentStart": [
            {"matcher": "", "hooks": original},
        ]}}
        incoming = {"hooks": {"SubagentStart": [canonical[1]]}}
        merged = acs.merge_settings(base, incoming)
        groups = merged["hooks"]["SubagentStart"]
        self.assertEqual(len(groups), 3)
        self.assertEqual([h for group in groups for h in group["hooks"]], original)
        self.assertTrue(all(group["matcher"] == "" for group in groups))
        self.assertEqual(merged["theme"], "retained")
        self.assertEqual(acs.merge_settings(merged, incoming), merged)

    def test_list_union_inserts_a_new_template_entry_after_its_template_neighbour(self):
        # Base entries keep their order; a template entry the base lacks lands right after the template
        # entry that precedes it (else right before the one that follows it), never simply at the end.
        base = {"permissions": {"deny": ["A", "C", "H"]}}
        template = {"permissions": {"deny": ["A", "B", "C", "D"]}}
        self.assertEqual(acs.merge_settings(base, template)["permissions"]["deny"], ["A", "B", "C", "D", "H"])
        base = {"permissions": {"deny": ["H", "C"]}}
        template = {"permissions": {"deny": ["B", "C"]}}
        self.assertEqual(acs.merge_settings(base, template)["permissions"]["deny"], ["H", "B", "C"])
        # With no template entry in the base, template entries follow the host's, as before.
        base = {"permissions": {"allow": ["Bash(ls)"]}}
        template = {"permissions": {"allow": ["Bash(pwd)", "Bash(date)"]}}
        self.assertEqual(acs.merge_settings(base, template)["permissions"]["allow"],
                         ["Bash(ls)", "Bash(pwd)", "Bash(date)"])

    def test_credential_twins_merge_before_an_existing_hosts_carve_outs(self):
        # A host applied before the Context Mode twins existed already holds the `.env` rules and their `!`
        # carve-outs. The twins must land before the carve-outs: a carve-out reaches only rules listed before
        # it (code.claude.com/docs/en/permissions), so an appended `Read(**/.env.*)` would deny .env.example.
        template_deny = json.loads((ROOT / "adoption/templates/claude.settings.template.json")
                                   .read_text(encoding="utf-8"))["permissions"]["deny"]
        twins = [rule for rule in template_deny if rule.startswith("Read(**/")]
        self.assertIn("Read(**/.env)", twins)
        self.assertIn("Read(**/.env.*)", twins)
        host_only = "Read(~/private/notes/**)"
        base = {"permissions": {"deny": [rule for rule in template_deny if rule not in twins] + [host_only]}}
        merged = acs.merge_settings(base, {"permissions": {"deny": template_deny}})["permissions"]["deny"]
        self.assertEqual(merged, template_deny + [host_only])
        for twin in ("Read(**/.env)", "Read(**/.env.*)"):
            for carve_out in ("Read(!.env.example)", "Read(!.env.*.example)"):
                self.assertLess(merged.index(twin), merged.index(carve_out))
        self.assertEqual(acs.merge_settings({"permissions": {"deny": merged}},
                                            {"permissions": {"deny": template_deny}})["permissions"]["deny"], merged)

    def test_a_status_line_refresh_interval_joins_the_hosts_status_line(self):
        # Synthesis H8/B1 (2026-09-27): a partial template with only the refresh interval keeps the host's own
        # status-line command; the full template's scalars win as for every nested object.
        base = {"statusLine": {"type": "command", "command": "host-hud", "padding": 1}}
        merged = acs.merge_settings(base, {"statusLine": {"refreshInterval": 5}})
        self.assertEqual(merged["statusLine"], {"type": "command", "command": "host-hud", "padding": 1,
                                                "refreshInterval": 5})
        full = acs.merge_settings(base, {"statusLine": {"type": "command", "command": "tpl", "refreshInterval": 5}})
        self.assertEqual(full["statusLine"], {"type": "command", "command": "tpl", "padding": 1, "refreshInterval": 5})

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


class HeldOutHookTests(unittest.TestCase):
    """The token-lane carriers are held out of the clean default: applying the template removes the hook objects an
    earlier template installed for them, and nothing else (docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md)."""

    SUB = 'python3 "/home/example/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true'
    SESSION = 'python3 "/home/example/.claude/hooks/token-lanes-session-start.py" 2>/dev/null || true'

    def template(self):
        return json.loads((ROOT / "adoption/templates/claude.settings.template.json").read_text(encoding="utf-8"))

    def test_the_template_runs_no_held_out_file(self):
        text = (ROOT / "adoption/templates/claude.settings.template.json").read_text(encoding="utf-8")
        for name in acs.HELD_OUT_HOOK_FILES:
            self.assertNotIn(name, text)
        self.assertEqual(len(self.template()["hooks"]["SubagentStart"]), 1)

    def test_a_host_that_applied_the_older_template_ends_clean(self):
        base = {"hostOnlyKey": "retained", "hooks": {
            "SubagentStart": [{"matcher": "", "hooks": [{"type": "command", "command": "memory-hook"}]},
                              {"matcher": "", "hooks": [{"type": "command", "command": self.SUB, "timeout": 5}]}],
            "SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": "host-hook"}]},
                             {"matcher": "startup|resume|clear|compact|fork",
                              "hooks": [{"type": "command", "command": self.SESSION, "timeout": 5}]}],
        }}
        merged = acs.merge_settings(base, self.template())
        self.assertNotIn("token-lanes", json.dumps(merged["hooks"]))
        self.assertEqual(merged["hostOnlyKey"], "retained")
        # the hosts' own entries keep their values and order; only the carrier groups are gone
        self.assertEqual(merged["hooks"]["SubagentStart"][0], base["hooks"]["SubagentStart"][0])
        self.assertEqual(merged["hooks"]["SessionStart"][0], base["hooks"]["SessionStart"][0])
        self.assertEqual(acs.merge_settings(merged, self.template()), merged)

    def test_a_mixed_entry_loses_only_the_carrier_hook(self):
        host = {"type": "command", "command": "true", "timeout": 7}
        carrier = {"type": "command", "command": self.SUB, "timeout": 5}
        base = {"hooks": {"SubagentStart": [{"matcher": "", "hooks": [host, carrier]}]}}
        merged = acs.merge_settings(base, {"hooks": {"Stop": [{"matcher": "", "hooks": [host]}]}})
        self.assertEqual(merged["hooks"]["SubagentStart"], [{"matcher": "", "hooks": [host]}])

    def test_an_event_that_held_only_a_carrier_is_dropped(self):
        base = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": self.SESSION}]}]}}
        merged = acs.merge_settings(base, {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "x"}]}]}})
        self.assertEqual(sorted(merged["hooks"]), ["Stop"])

    def test_a_template_that_carries_the_command_keeps_it_once(self):
        # An adopter's own template opts the carrier back in: the live entry stays and is not duplicated.
        entry = {"matcher": "", "hooks": [{"type": "command", "command": self.SUB, "timeout": 5}]}
        merged = acs.merge_settings({"hooks": {"SubagentStart": [entry]}}, {"hooks": {"SubagentStart": [entry]}})
        self.assertEqual(merged["hooks"]["SubagentStart"], [entry])

    def test_only_a_hook_file_under_a_claude_hooks_directory_is_retired(self):
        own = [{"type": "command", "command": "python3 /home/example/bin/token-lanes-subagent-start.py"},
               {"type": "command", "command": 'python3 "/home/example/.claude/hooks/my-token-lanes-subagent-start.py"'},
               {"type": "command", "command": "echo token-lanes-subagent-start.py"},
               {"type": "command", "command": "python3 'unterminated"}]
        base = {"hooks": {"SubagentStart": [{"matcher": "", "hooks": own}]}}
        merged = acs.merge_settings(base, {"hooks": {}})
        self.assertEqual(merged["hooks"]["SubagentStart"], [{"matcher": "", "hooks": own}])
        self.assertFalse(any(acs.runs_held_out_hook(hook) for hook in own))
        self.assertTrue(acs.runs_held_out_hook({"command": self.SUB}))

    def test_a_template_without_hooks_leaves_the_live_hooks_alone(self):
        base = {"hooks": {"SubagentStart": [{"matcher": "", "hooks": [{"type": "command", "command": self.SUB}]}]}}
        self.assertEqual(acs.merge_settings(base, {"theme": "dark"})["hooks"], base["hooks"])

    def test_malformed_hook_values_pass_through(self):
        base = {"hooks": {"Stop": [{"matcher": "", "hooks": 5}, "not-a-group"], "Other": "text"}}
        self.assertEqual(acs.retire_held_out_hooks(base["hooks"], {}), base["hooks"])
        self.assertEqual(acs.retire_held_out_hooks("text", {}), "text")


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
