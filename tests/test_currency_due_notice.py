"""Subprocess contract for the session-start currency notice, its Claude registration and its Codex template.

The hook (adoption/hooks/claude/currency-due-notice.py) reads the due-file that the daily stack-currency
timer writes (scripts/currency_due.py, unit A2: {generated_at, due: {pins_behind, stale_receipts, due_layers,
reopen_triggers}, summary_line, details}) and prints only its summary_line as SessionStart additional context.
It is run here the way both clients run a command hook, as tests/test_effort_default_guard.py runs its guard:
event JSON on stdin under a temporary HOME, stdout read back, exit 0 always.

Only the Claude registration (settings template, installer hook map, SHA256SUMS) is applied by the Claude profile.
adoption/templates/codex.hooks.template.json is a template only, not applied by any installer; B1 applies no Codex
hook. CodexParityTests therefore check that Codex 0.157.1 would parse and hash the template as the config template's
trusted_hash says, not that any host runs it.

Output and input contracts:
- Claude Code: https://code.claude.com/docs/en/hooks#sessionstart (read 2026-09-30): SessionStart input carries
  the common fields plus `source`; `hookSpecificOutput.additionalContext` adds context.
- Codex 0.157.1 (openai/codex tag rust-v0.157.1, commit 36650394c5b38c2990ccf2a3457165ca3e9d9726):
  codex-rs/hooks/schema/generated/session-start.command.input.schema.json (session_id, transcript_path, cwd,
  hook_event_name, model, permission_mode, source) and session-start.command.output.schema.json
  (hookSpecificOutput with hookEventName "SessionStart" and additionalContext, additionalProperties false);
  hooks.json trust keys and hashes follow scripts/adoption_status.py codex_hook_hashes, read from
  codex-rs/hooks/src/engine/discovery.rs and codex-rs/config/src/hook_config.rs.
"""

import ast
import contextlib
import io
import json
import os
import re
import shutil
import statistics
import string
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import install_claude_profile as icp  # noqa: E402
from scripts import adoption_status  # noqa: E402

NAME = "currency-due-notice.py"
HOOK = ROOT / "adoption" / "hooks" / "claude" / NAME
SHA256SUMS = ROOT / "adoption" / "hooks" / "claude" / "SHA256SUMS"
CLAUDE_TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"
CODEX_HOOKS_TEMPLATE = ROOT / "adoption" / "templates" / "codex.hooks.template.json"
CODEX_CONFIG_TEMPLATE = ROOT / "adoption" / "templates" / "codex.config.template.toml"
DUE_FILE = Path("native-agent-stack") / "currency-due.json"
BUDGET_MS = 50  # the hook's own runtime budget: its median over a bare `python3 -c pass` start
CEILING_MS = 1000  # a coarse bound on the whole process, past which a hang or a heavy import is the likely cause
# The key Codex gives the template's handler once it is hand-appended after ai-memory's one SessionStart group in
# the user hooks.json: <hooks.json path>:<event>:<group>:<handler> (discovery.rs; adoption_status.py L146-149).
CODEX_KEY = "${HOME}/.codex/hooks.json:session_start:1:0"
# What the Codex template, its trust entry and the hook's docstring say about who applies the template: nobody.
TEMPLATE_ONLY = "template only, not applied by any installer; B1 applies no Codex hook"
SUMMARY = "Stack currency: 2 pins behind, 1 stale receipt; run python3 scripts/currency_due.py --json"
# Neutral paths and ids: scripts/validate.py rejects personal home paths and UUID-shaped session ids.
CLAUDE_EVENT = {"session_id": "fixture-session", "transcript_path": "/srv/project/.transcript.jsonl",
                "cwd": "/srv/project", "hook_event_name": "SessionStart", "source": "startup",
                "model": "claude-opus-5-5"}
CODEX_EVENT = {"session_id": "fixture-thread", "transcript_path": None, "cwd": "/srv/project",
               "hook_event_name": "SessionStart", "model": "gpt-6.1-sol", "permission_mode": "default",
               "source": "startup"}
# The standard modules the hook may import; nothing that opens a connection or starts a process may be loaded.
ALLOWED_IMPORTS = {"datetime", "json", "os", "stat", "sys"}
NETWORK_MODULES = ("socket", "_socket", "ssl", "_ssl", "http", "http.client", "urllib.request", "select",
                   "selectors", "asyncio", "subprocess", "_posixsubprocess")


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def due(summary=SUMMARY, generated=None, **extra) -> dict:
    record = {"generated_at": generated if generated is not None else iso(datetime.now(timezone.utc)),
              "due": {"pins_behind": 2, "stale_receipts": 1, "due_layers": 0, "reopen_triggers": 0},
              "summary_line": summary, "details": [{"kind": "pin", "id": "fixture"}]}
    record.update(extra)
    return record


def expected(line: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": line}}


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="currency-notice-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {**os.environ, "HOME": str(self.home)}
        self.env.pop("XDG_STATE_HOME", None)

    def default_path(self) -> Path:
        return self.home / ".local" / "state" / DUE_FILE

    def install(self) -> str:
        """The installer's guard step for this one hook, into the temporary home; its progress line is dropped."""
        with contextlib.redirect_stdout(io.StringIO()):
            return icp.install_guard(self.home, dry_run=False, name=NAME)

    def write(self, content, path=None, mode=0o600) -> Path:
        path = path or self.default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(path):  # replaced, as the writer's rename does; an earlier case may have left it 0400
            path.unlink()
        data = content if isinstance(content, bytes) else json.dumps(content).encode("utf-8")
        path.write_bytes(data)
        path.chmod(mode)
        return path

    def run_hook(self, event=None, env=None, script=HOOK, cwd=None, stdin=None) -> str:
        stdin = stdin if stdin is not None else json.dumps(CLAUDE_EVENT if event is None else event)
        result = subprocess.run([sys.executable, str(script)], input=stdin, capture_output=True, text=True,
                                timeout=10, env=env or self.env, cwd=cwd or self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def assertPrints(self, line, **kwargs):
        stdout = self.run_hook(**kwargs)
        self.assertEqual(len(stdout.splitlines()), 1, stdout)
        self.assertTrue(stdout.endswith("\n"))
        self.assertEqual(json.loads(stdout), expected(line))

    def assertSilent(self, **kwargs):
        self.assertEqual(self.run_hook(**kwargs), "")


class CurrencyNoticeTests(Harness):
    def test_missing_file_or_state_directory_prints_nothing(self):
        self.assertSilent()
        self.default_path().parent.mkdir(parents=True)
        self.assertSilent()

    def test_valid_file_prints_only_the_summary_line_for_claude_and_codex_input(self):
        self.write(due())
        for name, event in (("claude", CLAUDE_EVENT), ("codex", CODEX_EVENT)):
            with self.subTest(client=name):
                self.assertPrints(SUMMARY, event=event)

    def test_output_has_exactly_the_keys_both_clients_accept(self):
        # Codex's output wire sets additionalProperties false at both levels; Claude Code documents the same pair.
        self.write(due())
        output = json.loads(self.run_hook(event=CODEX_EVENT))
        self.assertEqual(set(output), {"hookSpecificOutput"})
        self.assertEqual(set(output["hookSpecificOutput"]), {"hookEventName", "additionalContext"})
        self.assertNotIn("details", json.dumps(output))
        self.assertNotIn("pins_behind", json.dumps(output))

    def test_summary_line_length_and_shape(self):
        # str.isprintable() also rejects what a newline, tab and BEL case does not show: the Unicode line and
        # paragraph separators (U+2028, U+2029), the C1 control NEL (U+0085) and the bidirectional format
        # characters (U+202E, U+2066). They sit inside the line: str.strip() removes them at either end, so an
        # end-placed one would only test the padding rule.
        for line, prints in (("x" * 160, True), ("x" * 161, False), ("", False), ("   ", False),
                             ("two\nlines", False), ("tab\there", False), ("bell\x07", False),
                             ("line separator", False), ("paragraph separator", False),
                             ("next\u0085line", False), ("right-to-left‮override", False),
                             ("isolate⁦mark", False),
                             ("  padded line  ", True), ("naïve résumé", True)):
            with self.subTest(line=line):
                self.write(due(summary=line))
                if prints:
                    self.assertPrints(line.strip())
                else:
                    self.assertSilent()

    def test_malformed_files_print_nothing(self):
        now = iso(datetime.now(timezone.utc))
        cases = {
            "not json": b"{not json",
            "empty": b"",
            "array": b"[]",
            "string": b'"line"',
            "invalid utf-8": b'{"summary_line": "\xff", "generated_at": "' + now.encode() + b'"}',
            "no summary_line": {"generated_at": now},
            "summary_line not a string": due(summary=["a"]),
            "no generated_at": {"summary_line": SUMMARY},
            "generated_at not a string": due(generated=1759190400),
            "generated_at not a time": due(generated="yesterday"),
            "generated_at empty": due(generated=""),
            "deeply nested": b"[" * 100_000,
            "oversized": b'{"summary_line": "' + SUMMARY.encode() + b'", "generated_at": "' + now.encode()
                         + b'", "details": "' + b"x" * (1 << 20) + b'"}',
        }
        for label, content in cases.items():
            with self.subTest(case=label):
                self.write(content)
                self.assertSilent()

    def test_stale_or_far_future_file_prints_nothing(self):
        now = datetime.now(timezone.utc)
        for moment, prints in ((now - timedelta(days=8, minutes=1), False),
                               (now - timedelta(days=7, hours=23), True),
                               (now + timedelta(hours=23), True),
                               (now + timedelta(days=1, minutes=1), False)):
            with self.subTest(generated_at=iso(moment)):
                self.write(due(generated=iso(moment)))
                if prints:
                    self.assertPrints(SUMMARY)
                else:
                    self.assertSilent()

    def test_generated_at_accepts_iso_8601_forms(self):
        # A2 fixes no timestamp form; a naive time is read as UTC.
        now = datetime.now(timezone.utc).replace(microsecond=0)
        for text in (iso(now), now.isoformat(), now.astimezone(timezone(timedelta(hours=-7))).isoformat(),
                     now.replace(tzinfo=None).isoformat(), now.isoformat(timespec="microseconds"),
                     iso(now).replace("Z", "z")):
            with self.subTest(generated_at=text):
                self.write(due(generated=text))
                self.assertPrints(SUMMARY)

    def test_unreadable_or_non_regular_paths_print_nothing(self):
        path = self.default_path()
        path.parent.mkdir(parents=True)
        valid = self.write(due(), path=self.tmp / "valid.json")

        def clear():
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            elif os.path.lexists(path):
                path.unlink()

        cases = {"directory": path.mkdir,
                 "fifo without a writer": lambda: os.mkfifo(path),  # a blocking open would hang until the timeout
                 "link to a valid due-file": lambda: path.symlink_to(valid),
                 "link to a character device": lambda: path.symlink_to(os.devnull),
                 "dangling link": lambda: path.symlink_to(self.tmp / "absent.json")}
        if os.geteuid() != 0:  # root reads a mode-000 file
            cases["mode 000"] = lambda: self.write(due(), mode=0o000)
        for label, make in cases.items():
            with self.subTest(case=label):
                clear()
                make()
                self.assertSilent()

    def test_a_file_others_can_write_or_another_user_owns_prints_nothing(self):
        # The line enters the model's context, so the file gets the owner and mode check OpenSSH's StrictModes
        # applies to a user's files (sshd_config(5)); the due-file writer creates it 0600.
        for mode, prints in ((0o600, True), (0o644, True), (0o400, True), (0o620, False), (0o602, False),
                             (0o666, False)):
            with self.subTest(mode=oct(mode)):
                self.write(due(), mode=mode)
                if prints:
                    self.assertPrints(SUMMARY)
                else:
                    self.assertSilent()
        # Another owner, observed in-process: os.geteuid reports a different user than the file's.
        self.write(due())
        driver = ("import importlib.util, os, sys\n"
                  "real = os.geteuid()\n"
                  "os.geteuid = lambda: real + 1\n"
                  "spec = importlib.util.spec_from_file_location('notice', sys.argv[1])\n"
                  "module = importlib.util.module_from_spec(spec)\n"
                  "spec.loader.exec_module(module)\n"
                  "module.main()\n")
        result = subprocess.run([sys.executable, "-c", driver, str(HOOK)], input=json.dumps(CLAUDE_EVENT),
                                capture_output=True, text=True, timeout=10, env=self.env, cwd=self.tmp)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_state_directory_follows_the_xdg_rules(self):
        # https://specifications.freedesktop.org/basedir-spec/latest/: unset or empty means $HOME/.local/state,
        # and a relative value is invalid and ignored.
        custom = self.tmp / "xdg-state"
        self.write(due(summary="from XDG_STATE_HOME"), path=custom / DUE_FILE)
        self.write(due(summary="from the default"))
        relative = self.tmp / "relative-state"
        self.write(due(summary="from a relative value"), path=relative / DUE_FILE)
        for value, line in ((str(custom), "from XDG_STATE_HOME"), ("", "from the default"),
                            ("relative-state", "from the default")):
            with self.subTest(XDG_STATE_HOME=value):
                self.assertPrints(line, env={**self.env, "XDG_STATE_HOME": value}, cwd=self.tmp)

    def test_a_relative_home_is_refused_rather_than_resolved_against_the_working_directory(self):
        # Without a usable XDG_STATE_HOME the state directory is $HOME/.local/state. A relative HOME would then
        # name a file under the hook's working directory, which the session does not choose, so the hook reads
        # nothing (print nothing, exit 0). The due-file below is valid and sits exactly where that path resolves.
        relative_home = "relative-home"
        self.write(due(summary="from a relative HOME"), path=self.tmp / relative_home / ".local" / "state" / DUE_FILE)
        for label, extra in (("XDG_STATE_HOME unset", {}), ("XDG_STATE_HOME empty", {"XDG_STATE_HOME": ""}),
                             ("XDG_STATE_HOME relative", {"XDG_STATE_HOME": "elsewhere"})):
            with self.subTest(case=label):
                self.assertSilent(env={**self.env, "HOME": relative_home, **extra}, cwd=self.tmp)
        # The refusal is on the resulting path, not on the HOME value alone: an absolute XDG_STATE_HOME never
        # consults HOME, and the same absolute file is read whatever a relative HOME says.
        absolute = self.tmp / "xdg-state"
        self.write(due(summary="from an absolute XDG_STATE_HOME"), path=absolute / DUE_FILE)
        self.assertPrints("from an absolute XDG_STATE_HOME",
                          env={**self.env, "HOME": relative_home, "XDG_STATE_HOME": str(absolute)}, cwd=self.tmp)
        # Control: the same fixture through an absolute HOME is read, so the silence above is the refusal.
        self.assertPrints("from a relative HOME", env={**self.env, "HOME": str(self.tmp / relative_home)},
                          cwd=self.tmp)

    def test_other_events_and_malformed_input_print_nothing(self):
        self.write(due())
        for label, stdin in (("not json", "not json"), ("empty", ""), ("array", "[]"), ("null", "null"),
                             ("no event name", json.dumps({"source": "startup"})),
                             ("subagent start", json.dumps({**CODEX_EVENT, "hook_event_name": "SubagentStart"})),
                             ("session end", json.dumps({**CLAUDE_EVENT, "hook_event_name": "SessionEnd"}))):
            with self.subTest(case=label):
                self.assertSilent(stdin=stdin)

    def test_imports_only_light_standard_modules_and_opens_no_network(self):
        tree = ast.parse(HOOK.read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertLessEqual(imported, ALLOWED_IMPORTS)
        # In-process: after the allowed modules are imported, running main() on a valid due-file loads nothing more,
        # and no network or process module is loaded at all.
        self.write(due())
        driver = ("import importlib.util, json, sys\n"
                  f"import {', '.join(sorted(ALLOWED_IMPORTS))}\n"
                  "before = set(sys.modules)\n"
                  "spec = importlib.util.spec_from_file_location('notice', sys.argv[1])\n"
                  "module = importlib.util.module_from_spec(spec)\n"
                  "spec.loader.exec_module(module)\n"
                  "module.main()\n"
                  "sys.stderr.write(json.dumps([sorted(set(sys.modules) - before), sorted(sys.modules)]))\n")
        result = subprocess.run([sys.executable, "-c", driver, str(HOOK)], input=json.dumps(CLAUDE_EVENT),
                                capture_output=True, text=True, timeout=10, env=self.env, cwd=self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), expected(SUMMARY))
        added, loaded = json.loads(result.stderr)
        self.assertEqual(set(added) - {"notice"}, set())
        self.assertEqual(set(loaded) & set(NETWORK_MODULES), set())

    def test_runtime_stays_within_the_budget(self):
        # Median wall time of the whole process, interpreter start included, with and without the due-file. The
        # absolute figure is printed, not held to the 50 ms brief: it moves with the host's load and Python build
        # (interpreter start alone is most of it). What is held is the hook's own share over `python3 -c
        # pass` (BUDGET_MS) and a coarse ceiling on the whole process (CEILING_MS) that only a hang or a heavy
        # import would cross; test_imports_only_light_standard_modules_and_opens_no_network pins the imports.
        def median_ms(argv, stdin):
            samples = []
            for _ in range(9):
                start = time.perf_counter()
                subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=10, env=self.env,
                               cwd=self.tmp)
                samples.append((time.perf_counter() - start) * 1000)
            return statistics.median(samples)

        bare = median_ms([sys.executable, "-c", "pass"], "")
        stdin = json.dumps(CLAUDE_EVENT)
        for label, present in (("without the due-file", False), ("with the due-file", True)):
            with self.subTest(case=label):
                if present:
                    self.write(due())
                hook = median_ms([sys.executable, str(HOOK)], stdin)
                print(f"\n{NAME} {label}: median {hook:.1f} ms (bare interpreter {bare:.1f} ms)", file=sys.stderr)
                self.assertLessEqual(hook - bare, BUDGET_MS)
                self.assertLessEqual(hook, CEILING_MS)


class ClaudeRegistrationTests(Harness):
    def template(self) -> dict:
        return json.loads(string.Template(CLAUDE_TEMPLATE.read_text(encoding="utf-8")).safe_substitute(
            HOME=str(self.home)))

    def test_sha256sums_pins_the_script_and_the_installer_copies_it(self):
        self.assertIn(NAME, SHA256SUMS.read_text(encoding="utf-8").split())
        self.assertEqual(icp.expected_sha256(HOOK), icp.sha256_of(HOOK))
        self.assertEqual(icp.HOOKS[NAME], HOOK)
        self.assertEqual(self.install(), "installed")
        self.assertEqual((self.home / ".claude" / "hooks" / NAME).read_bytes(), HOOK.read_bytes())

    def test_template_registers_one_startup_group_that_merges_once(self):
        import apply_claude_settings as acs
        template = self.template()
        wanted = f'python3 "{self.home}/.claude/hooks/{NAME}" 2>/dev/null || true'
        groups = [group for group in template["hooks"]["SessionStart"]
                  if any(acs.command_key(hook["command"]) == acs.command_key(wanted) for hook in group["hooks"])]
        self.assertEqual(groups, [{"matcher": "startup", "hooks": [
            {"type": "command", "command": wanted, "timeout": 5}]}])
        for event, event_groups in template["hooks"].items():
            if event != "SessionStart":
                with self.subTest(event=event):
                    self.assertNotIn(NAME, json.dumps(event_groups))
        merged = {}
        for application in (1, 2):
            previous, merged = merged, acs.merge_settings(merged, template)
            keys = [acs.command_key(hook["command"]) for group in merged["hooks"]["SessionStart"]
                    for hook in group["hooks"]]
            with self.subTest(application=application):
                self.assertEqual(keys.count(acs.command_key(wanted)), 1)
                if application == 2:
                    self.assertEqual(merged, previous)

    def test_installed_hook_runs_from_the_template_command(self):
        # The rendered command through a POSIX shell, as Claude Code runs a command hook: absent script, no
        # due-file and a due-file.
        (group,) = [group for group in self.template()["hooks"]["SessionStart"] if NAME in json.dumps(group)]
        command = group["hooks"][0]["command"]
        stdin = json.dumps(CLAUDE_EVENT)

        def run():
            result = subprocess.run(["/bin/sh", "-c", command], input=stdin, capture_output=True, text=True,
                                    timeout=10, env=self.env, cwd=self.tmp)
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            return result.stdout

        self.assertEqual(run(), "")  # not installed yet: exits 0 and adds nothing
        self.install()
        self.assertEqual(run(), "")
        self.write(due())
        self.assertEqual(json.loads(run()), expected(SUMMARY))


class CodexParityTests(Harness):
    def template_text(self) -> str:
        return CODEX_HOOKS_TEMPLATE.read_text(encoding="utf-8")

    def handler(self) -> dict:
        (group,) = json.loads(self.template_text())["hooks"]["SessionStart"]
        (handler,) = group["hooks"]
        return handler

    def test_template_is_one_startup_group_codex_parses(self):
        events = adoption_status.codex_hooks_json(self.template_text())  # raises CodexRejects where Codex would
        self.assertEqual(set(events), {"SessionStart"})
        ((matcher, handlers),) = events["SessionStart"]
        self.assertEqual(matcher, "startup")
        self.assertIs(adoption_status.codex_matcher_loads(matcher), True)
        (handler,) = handlers
        self.assertEqual(handler["type"], "command")
        self.assertEqual(handler["command"], f'python3 "$HOME/.claude/hooks/{NAME}" 2>/dev/null || true')
        # An explicit timeout: Codex hashes the normalized value (600 s when absent), so it is part of the trust.
        self.assertEqual(handler["timeout"], 5)
        # The description must not promise more than the file does: nothing applies it, and its trust key holds
        # only at the second SessionStart group (a hand-append after two groups gets key 2:0, untrusted).
        description = " ".join(json.loads(self.template_text())["description"].split())
        for phrase in (TEMPLATE_ONLY, "session_start:1:0", "session_start:2:0", "untrusted until it is reviewed"):
            self.assertIn(phrase, description)

    def test_template_needs_no_rendering(self):
        # The command is hashed as written, so it names the home through the shell ($HOME), not a ${...}
        # placeholder that tools/adoption/render_config.py would substitute per host.
        self.assertNotIn("${", self.template_text())
        self.assertIn("$HOME/", self.handler()["command"])

    def test_hook_docstring_says_the_template_is_not_applied(self):
        docstring = " ".join(ast.get_docstring(ast.parse(HOOK.read_text(encoding="utf-8"))).split())
        self.assertIn(TEMPLATE_ONLY, docstring)
        self.assertIn("codex.hooks.template.json", docstring)

    def test_config_template_trusts_exactly_the_appended_handler(self):
        # ai-memory's installer writes one SessionStart group (evidence/artifacts/gap-wave2-20260923/
        # foundation__quality-evaluation/support/reconciliation/codex-user-hooks-registration.txt), so the
        # appended template group is group 1; its trusted_hash is Codex's hook hash of that handler.
        user_hooks = {"hooks": {"SessionStart": [
            {"matcher": "", "hooks": [{"type": "command",
                                       "command": "ai-memory hook --event session-start --agent codex"}]},
            *json.loads(self.template_text())["hooks"]["SessionStart"]]}}
        hashes = adoption_status.codex_hook_hashes(
            "${HOME}/.codex/hooks.json", adoption_status.codex_hooks_json(json.dumps(user_hooks)))
        event, loads, digest, ai_memory = hashes[CODEX_KEY]
        self.assertEqual((event, loads, ai_memory), ("SessionStart", True, False))
        config = CODEX_CONFIG_TEMPLATE.read_text(encoding="utf-8")
        entries = re.findall(r'^\[hooks\.state\."([^"]+)"\]\ntrusted_hash = "([^"]+)"$', config, re.M)
        self.assertIn((CODEX_KEY, digest), entries)
        self.assertEqual([key for key, _ in entries].count(CODEX_KEY), 1)
        # The entry's own comment says the same as the template: the pre-trust is inert unless the group is
        # hand-appended as the second SessionStart group.
        comment = config.split(f'[hooks.state."{CODEX_KEY}"]')[0].rstrip().rsplit("\n\n", 1)[-1]
        comment = " ".join(line.lstrip("# ") for line in comment.splitlines())
        self.assertIn(TEMPLATE_ONLY, comment)
        self.assertIn("session_start:2:0", comment)
        # The hash does not depend on the group index, so a host whose hooks.json holds other groups first
        # finds the handler untrusted until it is reviewed in /hooks, not trusted under another key.
        alone = adoption_status.codex_hook_hashes(
            "${HOME}/.codex/hooks.json", adoption_status.codex_hooks_json(self.template_text()))
        self.assertEqual(alone["${HOME}/.codex/hooks.json:session_start:0:0"][2], digest)

    def test_command_runs_through_codex_login_shell(self):
        # Codex runs a command hook as `$SHELL -lc <command>`, else `/bin/sh -lc` (codex-rs/hooks/src/engine/
        # command_runner.rs L435-440 at rust-v0.157.1); HOME is the temporary home, so no host profile is read.
        command = self.handler()["command"]
        stdin = json.dumps(CODEX_EVENT)
        env = {**self.env, "SHELL": "/bin/sh"}

        def run():
            result = subprocess.run(["/bin/sh", "-lc", command], input=stdin, capture_output=True, text=True,
                                    timeout=10, env=env, cwd=self.tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

        self.assertEqual(run(), "")  # the Claude profile has not installed the script: exits 0, adds nothing
        self.install()
        self.write(due())
        self.assertEqual(json.loads(run()), expected(SUMMARY))


if __name__ == "__main__":
    unittest.main()
