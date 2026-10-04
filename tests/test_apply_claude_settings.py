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
    earlier template installed for them, and nothing else (docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md).
    A hook is retired only when its command is a string this repository shipped, as shipped or rendered for the host's home."""

    HOME = "/home/example"
    SUB = 'python3 "/home/example/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true'
    SESSION = 'python3 "/home/example/.claude/hooks/token-lanes-session-start.py" 2>/dev/null || true'
    CARRIER = "/home/example/.claude/hooks/token-lanes-session-start.py"

    # Every carrier command the repository has shipped (git log -S over the template and the opt-in entries file, 2026-10-04),
    # as shipped, with where it first appeared: the fixture that the allowlist in apply_claude_settings.py must equal.
    HISTORY = (
        ('python3 "${HOME}/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true',
         "adoption/templates/claude.settings.template.json, 0c33b37a9 (main, #378; first written as abaa8425d)"),
        ('python3 "${HOME}/.claude/hooks/token-lanes-session-start.py" 2>/dev/null || true',
         "adoption/templates/claude.settings.template.json, 2da4aaa77 (PR 684, branch c5/token-layer-2604-wide)"),
        ('python3 "$HOME/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true',
         "adoption/hooks/claude/held-out-hook-entries.json (PR 699)"),
        ('python3 "$HOME/.claude/hooks/token-lanes-session-start.py" 2>/dev/null || true',
         "adoption/hooks/claude/held-out-hook-entries.json (PR 699)"),
    )

    def history_commands(self):
        """The shipped strings, and each as the installer renders it for HOME (tests/test_install_claude_profile.py: the
        template's ${HOME} replaced by the home directory)."""
        shipped = [command for command, _ in self.HISTORY]
        import string

        return shipped + [string.Template(command).substitute(HOME=self.HOME) for command in shipped]

    def template(self):
        return json.loads((ROOT / "adoption/templates/claude.settings.template.json").read_text(encoding="utf-8"))

    def merge(self, base, template, keep_held_out=False):
        return acs.merge_settings(base, template, keep_held_out, home=self.HOME)

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
        merged = self.merge(base, self.template())
        self.assertNotIn("token-lanes", json.dumps(merged["hooks"]))
        self.assertEqual(merged["hostOnlyKey"], "retained")
        # the hosts' own entries keep their values and order; only the carrier groups are gone
        self.assertEqual(merged["hooks"]["SubagentStart"][0], base["hooks"]["SubagentStart"][0])
        self.assertEqual(merged["hooks"]["SessionStart"][0], base["hooks"]["SessionStart"][0])
        self.assertEqual(self.merge(merged, self.template()), merged)

    def test_a_mixed_entry_loses_only_the_carrier_hook(self):
        host = {"type": "command", "command": "true", "timeout": 7}
        carrier = {"type": "command", "command": self.SUB, "timeout": 5}
        base = {"hooks": {"SubagentStart": [{"matcher": "", "hooks": [host, carrier]}]}}
        merged = self.merge(base, {"hooks": {"Stop": [{"matcher": "", "hooks": [host]}]}})
        self.assertEqual(merged["hooks"]["SubagentStart"], [{"matcher": "", "hooks": [host]}])

    def test_an_event_that_held_only_a_carrier_is_dropped(self):
        base = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": self.SESSION}]}]}}
        merged = self.merge(base, {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "x"}]}]}})
        self.assertEqual(sorted(merged["hooks"]), ["Stop"])

    def test_a_template_that_carries_the_command_keeps_it_once(self):
        # An adopter's own template opts the carrier back in: the live entry stays and is not duplicated.
        entry = {"matcher": "", "hooks": [{"type": "command", "command": self.SUB, "timeout": 5}]}
        merged = self.merge({"hooks": {"SubagentStart": [entry]}}, {"hooks": {"SubagentStart": [entry]}})
        self.assertEqual(merged["hooks"]["SubagentStart"], [entry])

    def test_the_allowlist_is_exactly_the_strings_the_repository_shipped(self):
        self.assertEqual(sorted(acs.carrier_commands(self.HOME)), sorted(set(self.history_commands())))
        self.assertEqual([command for command, _ in acs.SHIPPED_CARRIER_COMMANDS], [command for command, _ in self.HISTORY])

    def test_every_shipped_command_is_retired_as_shipped_and_as_rendered(self):
        for command in self.history_commands():
            with self.subTest(command=command):
                hook = {"type": "command", "command": command}
                self.assertTrue(acs.runs_held_out_hook(hook, self.HOME))
                base = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [hook]}]}}
                self.assertEqual(self.merge(base, {"hooks": {}}).get("hooks", {}), {})

    def test_the_shipped_files_carry_only_allowlisted_commands(self):
        # A new shipped shape fails here until it is added to SHIPPED_CARRIER_COMMANDS with its source.
        for relative in ("adoption/templates/claude.settings.template.json", "adoption/hooks/claude/held-out-hook-entries.json"):
            data = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            for groups in data.get("hooks", {}).values():
                for group in groups:
                    for hook in group.get("hooks", []):
                        if any(name in hook.get("command", "") for name in acs.HELD_OUT_HOOK_FILES):
                            with self.subTest(file=relative, command=hook["command"]):
                                self.assertTrue(acs.runs_held_out_hook(hook, self.HOME))

    def test_the_opt_in_entries_are_retired_by_a_default_apply_and_kept_with_the_flag(self):
        entries = json.loads((ROOT / "adoption/hooks/claude/held-out-hook-entries.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(len(group["hooks"]) for groups in entries["hooks"].values() for group in groups), 2)
        self.assertEqual(self.merge({"hooks": entries["hooks"]}, {"hooks": {}}).get("hooks", {}), {})
        kept = self.merge({"hooks": entries["hooks"]}, {"hooks": {}}, keep_held_out=True)
        self.assertEqual(kept["hooks"], entries["hooks"])

    def test_no_whitespace_around_a_shipped_command_is_tolerated(self):
        # The command must equal a shipped string exactly. str.strip() would also remove a no-break space, a next-line character
        # and a carriage return, which /bin/sh treats as part of a word: `\xa0python3 ...` runs a program named so.
        for command in self.history_commands():
            for padded in (" " + command, command + " ", "\t" + command, command + "\n", "\xa0" + command, "\x85" + command,
                           command + "\r", "\r" + command, command + "\xa0"):
                with self.subTest(padded=repr(padded[:12] + "..." + padded[-4:])):
                    self.kept(padded)

    def test_no_single_edit_of_a_shipped_command_is_retired(self):
        # The allowlist matches whole strings: deleting, inserting or replacing any one character of any of the six strings
        # yields a command that is not retired (an insertion of ten characters and a replacement by three, at every position).
        allowed = set(self.history_commands())
        checked = 0
        for command in sorted(allowed):
            for index in range(len(command) + 1):
                candidates = [command[:index] + extra + command[index:] for extra in (" ", ";", "x", "\n", "'", '"', "$", "&", "|", "(")]
                if index < len(command):
                    candidates.append(command[:index] + command[index + 1:])
                    candidates += [command[:index] + extra + command[index + 1:] for extra in ("x", " ", ";")]
                for candidate in candidates:
                    if candidate in allowed:
                        continue
                    checked += 1
                    self.assertFalse(acs.runs_held_out_hook({"command": candidate}, self.HOME), candidate)
        self.assertGreater(checked, 5000)

    # Commands that name a carrier path without running it, or run it among other things: retiring them would delete a
    # host's own hook (the cross-family reads of 2026-10-04 reproduced these against the committed template).
    MENTIONS = (
        "sha256sum /home/example/.claude/hooks/token-lanes-session-start.py",
        "cat ~/.claude/hooks/token-lanes-subagent-start.py",
        "python3 /home/example/bin/audit.py /home/example/.claude/hooks/token-lanes-session-start.py",
        'python3 -c "print(1)" /home/example/.claude/hooks/token-lanes-session-start.py',
        'echo "/home/example/.claude/hooks/token-lanes-session-start.py"',
        "test -f /home/example/.claude/hooks/token-lanes-session-start.py && echo present",
        'true && python3 "/home/example/.claude/hooks/token-lanes-session-start.py"',
        'python3 "/home/example/.claude/hooks/token-lanes-session-start.py"; rm -f /home/example/x',
        'python3 "/home/example/.claude/hooks/token-lanes-session-start.py"\nrm -f /home/example/x',
    )

    # The second cross-family read's 25 command shapes (job-052) and the third read's 30 (job-054): {c} is the carrier path. Under
    # the allowlist none of them is a shipped string, so every one is kept, the ones that run the carrier as well as the ones that
    # run host code: a hand-edited carrier command stays the host's (the fail-closed residual).
    SECOND_READ = (
        ("adjacent_subshell", "python3 {c};(printf host)"), ("adjacent_and_subshell", "python3 {c} &&(printf host)"),
        ("argument_substitution", 'python3 {c} "$(printf host > /home/example/marker)"'),
        ("redirection_substitution", 'python3 {c} > "$(printf host > /home/example/marker)"'),
        ("process_substitution", "python3 {c} > >(tee /home/example/log)"),
        ("inline_python_path_comment", "python3 -c 'print(\"host\") # {c}'"),
        ("xoption_data_argument", "python3 -X {c} -c 'print(\"host\")'"), ("xoption_before_script", "python3 -X utf8 {c}"),
        ("warning_option_before_script", "python3 -W ignore {c}"), ("redirection_before_script", "python3 2>/dev/null {c}"),
        ("quoted_control_argument", 'python3 {c} ";" echo host'), ("double_quoted_path", 'python3 "{c}"'),
        ("single_quoted_path", "python3 '{c}'"), ("absolute_interpreter", "/usr/bin/python3 {c}"),
        ("assignment", 'FOO=1 BAR="two words" python3 {c}'), ("trailing_redirection", "python3 {c} 2>/dev/null || true"),
        ("bash_c", "bash -c 'python3 {c}'"), ("sh_script", "sh {c}"), ("exec_wrapper", "exec python3 {c}"),
        ("nohup_wrapper", "nohup python3 {c}"), ("timeout_wrapper", "timeout 5 python3 {c}"),
        ("env_wrapper", "env FOO=1 python3 {c}"), ("redirection_data", "cat < {c}"),
        ("multiline", "python3 {c}\nprintf host"), ("ordinary_compound", "python3 {c}; printf host"),
    )
    THIRD_READ = (
        ("end_options_flag", "python3 -- -u {c}"), ("end_options_xvalue", "python3 -- -X dev {c}"),
        ("end_options_repeated", "python3 -- -- {c}"), ("end_options_after_isolation", "python3 -I -- -u {c}"),
        ("end_options_redirection_tail", "python3 -- -u 2>/dev/null {c} || true"),
        ("interpreter_spaces", "'/home/example/interpreter with spaces/python3' {c}"),
        ("isolated_dev_options", "python3 -I -E -X dev {c}"), ("unicode_interpreter", "pythоn3 {c}"),
        ("unicode_script", "python3 /home/example/.claude/hooks/token-lanes-sessiоn-start.py"),
        ("unicode_separator", "python3\xa0{c}"), ("trailing_semicolon", "python3 {c};"), ("compact_or_true", "python3 {c} ||true"),
        ("crlf", "python3 {c}\r\n"), ("crlf_then_host", "python3 {c}\r\nprintf host"),
        ("end_options_valid", "python3 -I -E -X dev -- {c}"), ("redirect_after_end_options", "python3 -- 2>/dev/null {c}"),
        ("attached_options", "python3 -Wignore -Xutf8 {c}"), ("tab_separator", "python3\t{c}"),
        ("double_spaces", "python3  {c}"), ("quoted_substitution_literal", "python3 {c} '$(printf host)'"),
        ("extra_control", "python3 {c} || true && printf host"), ("joined_quotes", "python3 {c} 'one''two'"),
        ("quoted_option_value", "python3 -X 'dev' {c}"),
        ("unquoted_home", "python3 $HOME/.claude/hooks/token-lanes-session-start.py"),
        ("unquoted_braced_home", "python3 ${HOME}/.claude/hooks/token-lanes-session-start.py"),
        ("quoted_home_control", 'python3 "$HOME/.claude/hooks/token-lanes-session-start.py"'),
        ("quoted_braced_home_control", 'python3 "${HOME}/.claude/hooks/token-lanes-session-start.py"'),
        ("tilde_control", "python3 ~/.claude/hooks/token-lanes-session-start.py"),
        ("glob_X", "python3 -X dev* {c}"), ("glob_W", "python3 -W ignore:* {c}"),
    )

    def kept(self, command):
        hook = {"type": "command", "command": command}
        self.assertFalse(acs.runs_held_out_hook(hook, self.HOME), command)
        base = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [hook]}]}}
        self.assertEqual(self.merge(base, {"hooks": {}})["hooks"]["SessionStart"], base["hooks"]["SessionStart"])

    def test_a_hook_that_merely_mentions_a_carrier_path_is_kept(self):
        for command in self.MENTIONS:
            with self.subTest(command=command):
                self.kept(command)

    def test_the_second_and_third_reads_shapes_are_all_kept(self):
        self.assertEqual(len(self.SECOND_READ), 25)
        self.assertEqual(len(self.THIRD_READ), 30)
        for label, template in self.SECOND_READ + self.THIRD_READ:
            with self.subTest(shape=label):
                self.kept(template.format(c=self.CARRIER) if "{c}" in template else template)

    def test_only_a_hook_file_under_a_claude_hooks_directory_is_retired(self):
        own = [{"type": "command", "command": "python3 /home/example/bin/token-lanes-subagent-start.py"},
               {"type": "command", "command": 'python3 "/home/example/.claude/hooks/my-token-lanes-subagent-start.py"'},
               {"type": "command", "command": "echo token-lanes-subagent-start.py"},
               {"type": "command", "command": "python3 'unterminated"}]
        base = {"hooks": {"SubagentStart": [{"matcher": "", "hooks": own}]}}
        merged = self.merge(base, {"hooks": {}})
        self.assertEqual(merged["hooks"]["SubagentStart"], [{"matcher": "", "hooks": own}])
        self.assertFalse(any(acs.runs_held_out_hook(hook, self.HOME) for hook in own))
        self.assertTrue(acs.runs_held_out_hook({"command": self.SUB}, self.HOME))

    def test_another_hosts_home_does_not_retire_a_hook(self):
        # The rendered form is the host's own: a command with another home directory is not a string this host was given.
        other = self.SUB.replace(self.HOME, "/Users/example")
        self.assertFalse(acs.runs_held_out_hook({"command": other}, self.HOME))
        self.assertTrue(acs.runs_held_out_hook({"command": other}, "/Users/example"))

    def test_a_settings_file_names_its_own_home(self):
        self.assertEqual(acs.host_home(Path("/home/example/.claude/settings.json")), "/home/example")
        self.assertIsNone(acs.host_home(Path("/home/example/settings.json")))
        self.assertIsNone(acs.host_home(Path("/tmp/x/.claude/other.json")))
        self.assertIsNone(acs.host_home(Path("/tmp/x/settings.json")))

    def carrier_for(self, home):
        return f'python3 "{home}/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true'

    def settings_with(self, path, command):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"hooks": {"SubagentStart": [{"matcher": "", "hooks": [
            {"type": "command", "command": "memory-hook"}, {"type": "command", "command": command}]}]}}), encoding="utf-8")

    def applied(self, target):
        import contextlib
        import io

        with contextlib.redirect_stderr(io.StringIO()):
            acs.apply(ROOT / "adoption/templates/claude.settings.template.json", target, dry_run=False)
        return target.read_text(encoding="utf-8")

    def test_applying_to_a_home_retires_the_carrier_rendered_for_that_home(self):
        import tempfile

        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch).resolve()
            target = home / ".claude" / "settings.json"
            self.settings_with(target, self.carrier_for(home))
            text = self.applied(target)
            self.assertNotIn("token-lanes", text)
            self.assertIn("memory-hook", text)

    def test_a_relative_target_names_the_home_it_is_in(self):
        import tempfile

        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch).resolve()
            self.settings_with(home / ".claude" / "settings.json", self.carrier_for(home))
            before = Path.cwd()
            os.chdir(home)
            try:
                self.assertEqual(acs.host_home(Path(".claude/settings.json")), str(home))
                text = self.applied(Path(".claude/settings.json"))
            finally:
                os.chdir(before)
            self.assertNotIn("token-lanes", text)

    def test_an_alias_of_a_home_names_the_real_one(self):
        import tempfile

        with tempfile.TemporaryDirectory() as scratch:
            real = Path(scratch).resolve() / "real"
            alias = Path(scratch).resolve() / "alias"
            real.mkdir()
            alias.symlink_to(real, target_is_directory=True)
            self.settings_with(real / ".claude" / "settings.json", self.carrier_for(real))
            self.assertEqual(acs.host_home(alias / ".claude" / "settings.json"), str(real))
            text = self.applied(alias / ".claude" / "settings.json")
            self.assertNotIn("token-lanes", text)

    def test_a_target_that_is_not_a_homes_claude_settings_retires_nothing(self):
        # No fallback to the operator's own home: a file outside <home>/.claude/settings.json that holds the command this user's
        # installer would have rendered keeps it, because whose file it is cannot be told.
        import tempfile

        with tempfile.TemporaryDirectory() as scratch:
            target = Path(scratch).resolve() / "elsewhere" / "settings.json"
            self.settings_with(target, self.carrier_for(Path.home()))
            text = self.applied(target)
            self.assertIn("token-lanes-subagent-start.py", text)
            self.assertIn("memory-hook", text)

    def test_a_home_with_a_trailing_slash_renders_the_same_commands(self):
        self.assertEqual(acs.carrier_commands(self.HOME + "/"), acs.carrier_commands(self.HOME))
        self.assertTrue(acs.runs_held_out_hook({"command": self.SUB}, self.HOME + "/"))
        self.assertFalse(acs.runs_held_out_hook({"command": self.SUB.replace(self.HOME, self.HOME + "/")}, self.HOME + "/"))

    def test_a_home_that_contains_a_placeholder_is_substituted_once(self):
        # render_config.py substitutes in one pass; sequential replaces would add an alias that it never writes.
        import string

        home = "/fixture/cash$HOME"
        expected = {command for command, _ in acs.SHIPPED_CARRIER_COMMANDS}
        expected |= {string.Template(command).substitute(HOME=home) for command, _ in acs.SHIPPED_CARRIER_COMMANDS}
        self.assertEqual(set(acs.carrier_commands(home)), expected)
        doubled = 'python3 "/fixture/cash/fixture/cash$HOME/.claude/hooks/token-lanes-subagent-start.py" 2>/dev/null || true'
        self.assertNotIn(doubled, acs.carrier_commands(home))
        self.assertFalse(acs.runs_held_out_hook({"command": doubled}, home))

    def test_without_a_known_home_nothing_is_retired(self):
        self.assertEqual(acs.carrier_commands(None), frozenset())
        self.assertEqual(acs.carrier_commands("relative/path"), frozenset())
        self.assertEqual(acs.carrier_commands(""), frozenset())
        hook = {"type": "command", "command": self.SUB}
        self.assertFalse(acs.runs_held_out_hook(hook))
        base = {"hooks": {"SubagentStart": [{"matcher": "", "hooks": [hook]}]}}
        merged = acs.merge_settings(base, self.template())
        self.assertIn(hook, [kept for group in merged["hooks"]["SubagentStart"] for kept in group["hooks"]])
        self.assertFalse(acs.runs_held_out_hook({"command": 'python3 "${HOME}/.claude/hooks/token-lanes-subagent-start.py" '
                                                           '2>/dev/null || true'}))

    def test_a_template_without_hooks_leaves_the_live_hooks_alone(self):
        base = {"hooks": {"SubagentStart": [{"matcher": "", "hooks": [{"type": "command", "command": self.SUB}]}]}}
        self.assertEqual(self.merge(base, {"theme": "dark"})["hooks"], base["hooks"])

    def test_malformed_hook_values_pass_through(self):
        base = {"hooks": {"Stop": [{"matcher": "", "hooks": 5}, "not-a-group"], "Other": "text"}}
        self.assertEqual(acs.retire_held_out_hooks(base["hooks"], {}, self.HOME), base["hooks"])
        self.assertEqual(acs.retire_held_out_hooks("text", {}, self.HOME), "text")


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
