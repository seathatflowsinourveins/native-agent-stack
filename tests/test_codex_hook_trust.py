"""tools/adoption/codex_hook_trust.py: trust the named hooks of one Codex home through config/batchWrite and read it back.

The app-server is a fake that answers hooks/list and config/batchWrite the way the released codex-cli 0.159.3 does (the field
names are those of its hooks/list response; the write shape is the TUI's write_hook_trusts); the rule review's two rtk commands are a
local stand-in too (FakeRtk: `rtk --version` and `rtk config`, with the output shapes of rtk 0.51.0); no real Codex, no real rtk, no real
home, no network: synthetic local checks, not upstream tests. The real client and the real tools were run against scratch homes in
evidence/artifacts/token-stack-fresh-session-e2e-20261004/.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import apply_codex_lane as lane  # noqa: E402
import codex_hook_trust as trust  # noqa: E402

RTK = "rtk hook codex"
KEY = "/home/example/.codex/hooks.json:pre_tool_use:1:0"
MEMORY_KEY = "/home/example/.codex/hooks.json:pre_tool_use:0:0"


def hook(key: str, command: str, status: str = "untrusted", **changes) -> dict:
    row = {"key": key, "command": command, "trustStatus": status, "source": "user", "isManaged": False,
           "eventName": "preToolUse", "matcher": "Bash", "currentHash": "sha256:" + "b" * 64, "handlerType": "command",
           "enabled": True}
    row.update(changes)
    return row


class FakeServer:
    """hooks/list, config/batchWrite and the user layer of one in-memory Codex home."""

    def __init__(self, hooks, *, fail_write: dict | None = None, ignore_write: bool = False, after_write=None,
                 errors: list | None = None, errors_after_write: list | None = None):
        self.hooks, self.version, self.requests = hooks, "v1", []
        self.fail_write, self.ignore_write = fail_write, ignore_write
        # after_write(server) runs once the write has been applied: a change of the hooks file that lands during it
        # (expectedVersion guards config.toml, not the file a hook is defined in). errors are the discovery errors hooks/list
        # reports, and errors_after_write the ones it reports once the write is done.
        self.after_write, self.errors, self.errors_after_write, self.written = after_write, errors or [], errors_after_write, False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def user_layer(self):
        return self.version, {}

    def request(self, method, params):
        self.requests.append((method, copy.deepcopy(params)))
        if method == "hooks/list":
            errors = self.errors_after_write if self.written and self.errors_after_write is not None else self.errors
            return {"data": [{"cwd": params["cwds"][0], "hooks": copy.deepcopy(self.hooks), "errors": copy.deepcopy(errors),
                              "warnings": []}]}
        if method == "config/batchWrite":
            if self.fail_write:
                raise lane.AppServerError(method, self.fail_write)
            if not self.ignore_write:
                for edit in params["edits"]:
                    for key, state in edit["value"].items():
                        for row in self.hooks:
                            if row["key"] == key:
                                row["trustStatus"] = "trusted" if state["trusted_hash"] == row["currentHash"] else "modified"
            self.version, self.written = "v2", True
            if self.after_write:
                self.after_write(self)
            return {"status": "ok", "version": self.version}
        raise AssertionError(method)

    def writes(self):
        return [params for method, params in self.requests if method == "config/batchWrite"]


def completed(command, code, out="", err=""):
    return subprocess.CompletedProcess(command, code, out, err)


class FakeRtk:
    """The two commands the rule review runs of rtk: `rtk --version` and `rtk config` (a `Config: <path>` line, then the configuration as TOML, as
    src/core/config.rs show_config prints it in v0.51.0). The review asks rtk only for a file on the reviewed list, and only these two things."""

    def __init__(self, config_dir, version="rtk 0.51.0", prefixes=(), version_exit=0, config_exit=0, config_body=None):
        self.config_dir, self.version, self.prefixes = Path(config_dir), version, list(prefixes)
        self.version_exit, self.config_exit, self.config_body = version_exit, config_exit, config_body
        self.calls = []

    def run(self, command, **kwargs):
        self.calls.append(list(command))
        if command[1:] == ["--version"]:
            return completed(command, self.version_exit, self.version + "\n", "boom\n" if self.version_exit else "")
        if command[1:] == ["config"]:
            prefixes = ", ".join(json.dumps(prefix) for prefix in self.prefixes)
            body = self.config_body if self.config_body is not None else (
                f"Config: {self.config_dir / 'config.toml'}\n\n[hooks]\nexclude_commands = []\ntransparent_prefixes = [{prefixes}]\n"
                f"suppress_hook_warning = false\n")
            return completed(command, self.config_exit, body, "boom\n" if self.config_exit else "")
        raise AssertionError(command)


class Case(unittest.TestCase):
    def setUp(self):
        self._scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self._scratch.cleanup)
        self.dir = Path(self._scratch.name)
        self.home = self.dir / "home"
        self.home.mkdir()
        self.config = self.home / "config.toml"
        self.config.write_text('model = "x"\n', encoding="utf-8")
        self.codex = self.dir / "codex"
        self.codex.write_text("#!/bin/sh\nexit 9\n", encoding="utf-8")
        self.codex.chmod(0o700)

    def run_tool(self, server, *extra: str, running=(), tools=None):
        out, err = io.StringIO(), io.StringIO()
        self.tools = tools or FakeRtk(self.dir / "rtk-config")
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(trust.lane, "AppServer", return_value=server) as self.app_server, \
                mock.patch.object(trust.lane, "codex_processes", return_value=list(running)), \
                mock.patch.object(trust.subprocess, "run", side_effect=self.tools.run):
            code = trust.main(["--codex", str(self.codex), "--codex-home", str(self.home), "--rtk", "/opt/rtk/bin/rtk",
                               "--command", RTK, *extra])
        return code, out.getvalue(), err.getvalue()


class DryRunTests(Case):
    def test_a_dry_run_lists_the_match_and_makes_no_trust_or_config_edit(self):
        server = FakeServer([hook(MEMORY_KEY, "ai-memory --data-dir x", "trusted"), hook(KEY, RTK)])
        code, out, err = self.run_tool(server)
        self.assertEqual(code, 0, err)
        self.assertIn(f"{KEY}: preToolUse Bash 'rtk hook codex' is untrusted", out)
        self.assertNotIn(MEMORY_KEY, out)  # a hook whose command was not named is not even listed
        self.assertIn("1 hook(s) would be trusted", out)
        self.assertEqual(server.writes(), [])
        self.assertEqual([p.name for p in self.home.iterdir()], ["config.toml"])

    def test_every_named_hook_already_trusted_is_nothing_to_do(self):
        server = FakeServer([hook(KEY, RTK, "trusted")])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(server.writes(), [])
        self.assertEqual([p.name for p in self.home.iterdir()], ["config.toml"])  # not even a backup

    def test_no_hook_with_the_named_command_is_exit_4(self):
        server = FakeServer([hook(MEMORY_KEY, "ai-memory --data-dir x", "trusted")])
        code, _, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 4)
        self.assertIn("register it first", err)
        self.assertEqual(server.writes(), [])


class ApplyTests(Case):
    def test_apply_backs_up_writes_the_tuis_edit_and_reads_back(self):
        server = FakeServer([hook(MEMORY_KEY, "ai-memory --data-dir x", "trusted"), hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        (write,) = server.writes()
        self.assertEqual(write["expectedVersion"], "v1")
        self.assertEqual(write["edits"], [{"keyPath": "hooks.state", "mergeStrategy": "upsert",
                                           "value": {KEY: {"trusted_hash": "sha256:" + "b" * 64}}}])
        self.assertEqual([row["trustStatus"] for row in server.hooks], ["trusted", "trusted"])
        self.assertIn("trusted 1 hook(s)", out)
        (backup,) = [p for p in self.home.iterdir() if p.name.startswith("config.toml.bak.")]
        self.assertEqual(backup.read_text(encoding="utf-8"), 'model = "x"\n')
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)

    def test_only_the_named_hooks_are_trusted(self):
        other = hook("/home/example/.codex/hooks.json:stop:0:0", "ai-memory --data-dir x", eventName="stop", matcher="")
        server = FakeServer([other, hook(KEY, RTK)])
        code, _, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        (write,) = server.writes()
        self.assertEqual(list(write["edits"][0]["value"]), [KEY])
        self.assertEqual(server.hooks[0]["trustStatus"], "untrusted")

    def test_a_modified_hook_is_trusted_again_at_its_current_hash(self):
        server = FakeServer([hook(KEY, RTK, "modified", currentHash="sha256:" + "c" * 64)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(server.writes()[0]["edits"][0]["value"][KEY]["trusted_hash"], "sha256:" + "c" * 64)
        self.assertEqual(server.hooks[0]["trustStatus"], "trusted")

    def test_a_project_hook_a_managed_hook_and_a_non_command_handler_are_never_trusted(self):
        rows = [hook("/p/.codex/hooks.json:pre_tool_use:0:0", RTK, source="project"),
                hook("managed:pre_tool_use:0:0", RTK, "managed", source="system", isManaged=True),
                hook("/home/example/.codex/config.toml:pre_tool_use:0:0", RTK, handlerType="mcp_tool")]
        server = FakeServer(rows)
        code, _, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 4, err)
        self.assertEqual(server.writes(), [])

    def test_two_commands_may_be_named(self):
        second = hook("/home/example/.codex/hooks.json:stop:1:0", "other-hook", eventName="stop", matcher="")
        server = FakeServer([hook(KEY, RTK), second])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(trust.lane, "AppServer", return_value=server), \
                mock.patch.object(trust.lane, "codex_processes", return_value=[]):
            code = trust.main(["--codex", str(self.codex), "--codex-home", str(self.home), "--command", RTK,
                               "--command", "other-hook", "--apply"])
        self.assertEqual(code, 0, err.getvalue())
        self.assertEqual(sorted(server.writes()[0]["edits"][0]["value"]), sorted([KEY, second["key"]]))

    def test_a_running_codex_refuses_before_any_write(self):
        server = FakeServer([hook(KEY, RTK)])
        code, _, err = self.run_tool(server, "--apply", running=["4242"])
        self.assertEqual(code, 2)
        self.assertIn("4242", err)
        self.assertEqual(server.writes(), [])
        self.assertEqual([p.name for p in self.home.iterdir()], ["config.toml"])

    def test_a_running_codex_does_not_block_a_dry_run_or_a_no_op(self):
        for hooks, extra in (([hook(KEY, RTK)], ()), ([hook(KEY, RTK, "trusted")], ("--apply",))):
            with self.subTest(extra=extra):
                code, _, err = self.run_tool(FakeServer(hooks), *extra, running=["4242"])
                self.assertEqual(code, 0, err)

    def test_a_failed_write_is_exit_3_and_names_the_backup(self):
        server = FakeServer([hook(KEY, RTK)], fail_write={"message": "version conflict", "code": -32600})
        code, _, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 3)
        self.assertIn("version conflict", err)
        self.assertIn("config.toml.bak.", err)
        self.assertEqual(server.hooks[0]["trustStatus"], "untrusted")

    def test_a_hook_the_writer_still_reports_untrusted_is_a_failure(self):
        server = FakeServer([hook(KEY, RTK)], ignore_write=True)
        code, _, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 3)
        self.assertIn("still reports not trusted", err)
        self.assertIn(KEY, err)

    def test_a_hook_whose_definition_changed_during_the_write_is_a_failure(self):
        # The second hooks/list is read by key and hash, not by command again: a hook that now has another command is `modified`
        # (trusted_hash was written for the old definition) and must not drop out of the check.
        def change(server):
            server.hooks[0].update(command="rtk hook other", currentHash="sha256:" + "d" * 64, trustStatus="modified")

        server = FakeServer([hook(KEY, RTK)], after_write=change)
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 3)
        self.assertIn(KEY, err)
        self.assertIn("changed during the write", err)
        self.assertNotIn("trusted 1 hook", out)
        self.assertIn("config.toml.bak.", err)

    def test_a_hook_that_vanished_during_the_write_is_a_failure(self):
        server = FakeServer([hook(KEY, RTK)], after_write=lambda s: s.hooks.clear())
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 3)
        self.assertIn(KEY, err)
        self.assertIn("no longer listed", err)
        self.assertNotIn("trusted 1 hook", out)

    def test_a_hook_that_left_the_user_layer_during_the_write_is_a_failure(self):
        for change in ({"source": "project"}, {"isManaged": True}, {"handlerType": "prompt"}):
            with self.subTest(change=change):
                server = FakeServer([hook(KEY, RTK)], after_write=lambda s, c=change: s.hooks[0].update(c))
                code, out, err = self.run_tool(server, "--apply")
                self.assertEqual(code, 3)
                self.assertIn("no longer a user-layer command hook", err)
                self.assertNotIn("trusted 1 hook", out)

    def test_an_already_trusted_hook_that_vanished_during_the_write_is_a_failure(self):
        other = hook("/home/example/.codex/hooks.json:stop:0:0", "other-hook", "trusted", eventName="stop", matcher="")

        def drop_other(server):
            server.hooks[:] = [row for row in server.hooks if row["key"] == KEY]

        server = FakeServer([hook(KEY, RTK), other], after_write=drop_other)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(trust.lane, "AppServer", return_value=server), \
                mock.patch.object(trust.lane, "codex_processes", return_value=[]):
            code = trust.main(["--codex", str(self.codex), "--codex-home", str(self.home), "--command", RTK,
                               "--command", "other-hook", "--apply"])
        self.assertEqual(code, 3, out.getvalue())
        self.assertIn(other["key"], err.getvalue())
        self.assertIn("no longer listed", err.getvalue())

    def test_a_discovery_error_that_appears_with_the_write_is_a_failure(self):
        error = {"path": "/home/example/.codex/hooks.json", "message": "expected value at line 3 column 1"}
        server = FakeServer([hook(KEY, RTK)], errors_after_write=[error])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 3)
        self.assertIn("expected value at line 3 column 1", err)
        self.assertIn("/home/example/.codex/hooks.json", err)
        self.assertNotIn("trusted 1 hook", out)

    def test_a_discovery_error_that_was_already_there_is_reported_and_is_not_a_failure(self):
        error = {"path": "/work/proj/.codex/hooks.json", "message": "unrelated parse error"}
        server = FakeServer([hook(KEY, RTK)], errors=[error])
        for extra in ((), ("--apply",)):
            with self.subTest(extra=extra):
                code, out, err = self.run_tool(server, *extra)
                self.assertEqual(code, 0, err)
                self.assertIn("unrelated parse error", out)
                self.assertIn("/work/proj/.codex/hooks.json", out)

    def test_the_read_back_names_the_hash_it_trusted(self):
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertIn("read back from hooks/list by key and hash", out)

    def test_a_home_without_a_config_file_gets_no_backup(self):
        self.config.unlink()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertNotIn("backup:", out)
        self.assertEqual(os.listdir(self.home), [])

    def test_no_codex_executable_is_refused(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(trust.shutil, "which", return_value=None):
            code = trust.main(["--codex-home", str(self.home), "--command", RTK])
        self.assertEqual(code, 2)
        self.assertIn("no codex executable", err.getvalue())

    def test_two_backups_in_one_second_do_not_overwrite_each_other(self):
        with mock.patch.object(trust.lane, "utc_stamp", return_value="20261004T000000Z"):
            first = trust.write_backup(self.config)
            self.config.write_text('model = "y"\n', encoding="utf-8")
            second = trust.write_backup(self.config)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_text(encoding="utf-8"), 'model = "x"\n')
        self.assertEqual(second.read_text(encoding="utf-8"), 'model = "y"\n')


class CheckTests(Case):
    """--check verifies and nothing else: no edit, no backup, no refusal beside a running codex."""

    def test_every_named_hook_trusted_is_exit_0_and_writes_nothing(self):
        server = FakeServer([hook(KEY, RTK, "trusted")])
        code, out, err = self.run_tool(server, "--check", running=["4242"])
        self.assertEqual(code, 0, err)
        self.assertIn("every named hook is trusted", out)
        self.assertEqual(server.writes(), [])
        self.assertEqual([p.name for p in self.home.iterdir()], ["config.toml"])

    def test_an_untrusted_or_modified_hook_is_exit_5_naming_the_key_and_writes_nothing(self):
        for status in ("untrusted", "modified"):
            with self.subTest(status=status):
                server = FakeServer([hook(MEMORY_KEY, "ai-memory --data-dir x", "trusted"), hook(KEY, RTK, status)])
                code, out, err = self.run_tool(server, "--check")
                self.assertEqual(code, 5)
                self.assertIn(KEY, err)
                self.assertIn(status, err)
                self.assertEqual(server.writes(), [])
                self.assertEqual([p.name for p in self.home.iterdir()], ["config.toml"])

    def test_no_hook_with_the_named_command_is_exit_4(self):
        server = FakeServer([hook(MEMORY_KEY, "ai-memory --data-dir x", "trusted")])
        code, _, err = self.run_tool(server, "--check")
        self.assertEqual(code, 4)
        self.assertIn("register it first", err)

    def test_check_and_apply_together_are_refused_by_the_parser(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            trust.main(["--codex", str(self.codex), "--codex-home", str(self.home), "--command", RTK, "--check", "--apply"])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("not allowed with", err.getvalue())

    def test_a_check_after_an_apply_agrees_with_it(self):
        server = FakeServer([hook(KEY, RTK)])
        self.assertEqual(self.run_tool(server, "--check")[0], 5)
        self.assertEqual(self.run_tool(server, "--apply")[0], 0)
        self.assertEqual(self.run_tool(server, "--check")[0], 0)


E2E = ROOT / "evidence" / "artifacts" / "token-stack-fresh-session-e2e-20261004"
REVIEWED = ROOT / "tools" / "adoption" / "exec_rules_reviewed.json"
PLAN_CONFIG = ROOT / "evidence" / "artifacts" / "new-wsl-install-plan-20261002" / "config"
# The one file on the reviewed list: #713's config/hcom-deny.rules at head 5f295f254 (a copy; #713 is not merged yet). Every rule is a prefix rule on
# `hcom ...` or `uvx hcom ...`.
HCOM_DENY_RULES = (E2E / "fixtures" / "hcom-deny.rules").read_bytes()
GIT_PUSH_FORBIDDEN = b'prefix_rule(pattern = ["git", "push"], decision = "forbidden")\n'
GIT_PUSH_TWIN = b'prefix_rule(pattern = ["rtk", "git", "push"], decision = "forbidden")\n'
# The counterexamples of the three GPT reads of the analysing versions (each was run against the real codex-cli 0.159.3 evaluator or the real rtk 0.51.0):
# 705e: the argument expression of host_executable registers a rule, so Codex forbids `git push origin main`.
NESTED_HOST_EXECUTABLE = (b'host_executable(name = prefix_rule(pattern = ["git", "push"], decision = "forbidden") or "git", '
                          b'paths = ["/usr/bin/git"])\n')
# 705f: a raw CR inside a triple-quoted string, which Codex's Starlark lexer drops (the pattern is `git push`) and Python's reader turns into a newline.
RAW_CR = b'prefix_rule(pattern = ["""gi\rt""", "push"], decision = "forbidden")\n'
# 705f: Codex matches an assignment-prefixed script against the whole shell argv, and rtk rewrites the script's `git push`.
BASH_LC = b'prefix_rule(pattern = ["/bin/bash", "-lc", "FOO=1 git push origin main"], decision = "forbidden")\n'
# 705f: rtk normalizes `phpunit.exe` to its PHP tool word and rewrites the command.
PHPUNIT_EXE = b'prefix_rule(pattern = ["phpunit.exe", "tests/"], decision = "forbidden")\n'
# 705f: rtk's Rust regex word boundary rewrites `g++` followed by a combining mark; Python's `\w` does not include it.
UNICODE_GXX = 'prefix_rule(pattern = ["g++\u0301"], decision = "forbidden")\n'.encode("utf-8")
# 705e: rtk leaves `git -C .` alone and rewrites `git -C . push origin main`.
GIT_GLOBAL_OPTION = b'prefix_rule(pattern = ["git", "-C", "."], decision = "forbidden")\n'
# Codex's own default.rules (codex-rs/execpolicy/src/amend.rs blocking_append_allow_prefix_rule): one allow rule per line, no comment.
CODEX_ALLOW = b'prefix_rule(pattern=["ls"], decision="allow")\nprefix_rule(pattern=["echo", "Hello, world!"], decision="allow")\n'
# hcom's own hcom.rules, reproduced from the installer's source (aannoo/hcom 7151660a3: src/hooks/codex.rs build_codex_rules L1508-L1534 with
# HCOM_TOOL_NAMES L578-L585, and src/hooks/common.rs SAFE_HCOM_COMMANDS L52-L72): one comment line, then allow rules, for the prefix hcom writes
# (`["hcom"]`, or `["uvx", "hcom"]`). Synthetic: the installer itself was not run here.
SAFE_HCOM_COMMANDS = ("send", "start", "help", "--help", "-h", "list", "events", "listen", "relay", "config", "transcript", "archive", "bundle", "status",
                      "term", "hooks", "--version", "-v", "--new-terminal")
HCOM_TOOL_NAMES = ("claude", "gemini", "codex", "opencode", "antigravity", "agy")


def hcom_own_rules(prefix: tuple[str, ...]) -> bytes:
    parts = ", ".join(f'"{word}"' for word in prefix)
    rules = ["# hcom integration - auto-approve safe commands"]
    rules += [f'prefix_rule(pattern=[{parts}, "{command}"], decision="allow")' for command in SAFE_HCOM_COMMANDS]
    for tool in HCOM_TOOL_NAMES:
        rules += [f'prefix_rule(pattern=[{parts}, "{tool}", "--help"], decision="allow")', f'prefix_rule(pattern=[{parts}, "{tool}", "-h"], decision="allow")']
    return ("\n".join(rules) + "\n").encode("ascii")


HCOM_OWN = hcom_own_rules(("hcom",))
# Files that are not Codex's allow-only format byte for byte, each of which the tool treats as an exposure.
NOT_ALLOW_ONLY = (
    ("an allow rule that names rtk, which matches the rewritten command and not the original", b'prefix_rule(pattern=["rtk"], decision="allow")\n'),
    ("an allow rule that names rtk after a wrapper", b'prefix_rule(pattern=["time", "rtk", "git"], decision="allow")\n'),
    ("an allow rule that names rtk beside a fine one", CODEX_ALLOW + b'prefix_rule(pattern=["rtk", "git", "status"], decision="allow")\n'),
    ("a prompt rule beside an allow rule", CODEX_ALLOW + b'prefix_rule(pattern=["git"], decision="prompt")\n'),
    ("a forbidden rule in Codex's own spelling", b'prefix_rule(pattern=["git", "push"], decision="forbidden")\n'),
    ("spaces around =", b'prefix_rule(pattern = ["ls"], decision = "allow")\n'),
    ("a CRLF line end", b'prefix_rule(pattern=["ls"], decision="allow")\r\n'),
    ("a raw CR in a comment", b"# a\rb\n"),
    ("a tab-indented line", b'\tprefix_rule(pattern=["ls"], decision="allow")\n'),
    ("a tab in a comment", b"# a\tb\n"),
    ("a trailing space", b'prefix_rule(pattern=["ls"], decision="allow") \n'),
    ("an escaped quote in a token", b'prefix_rule(pattern=["a\\"b"], decision="allow")\n'),
    ("an escaped backslash in a token", b'prefix_rule(pattern=["a\\\\b"], decision="allow")\n'),
    ("another escape in a token", b'prefix_rule(pattern=["a\\nb"], decision="allow")\n'),
    ("no space after a comma", b'prefix_rule(pattern=["a","b"], decision="allow")\n'),
    ("two spaces after a comma", b'prefix_rule(pattern=["a",  "b"], decision="allow")\n'),
    ("a backslash in a comment", b"# continues \\\n"),
    ("a non-ASCII byte", 'prefix_rule(pattern=["é"], decision="allow")\n'.encode("utf-8")),
    ("a non-ASCII byte in a comment", "# é\n".encode("utf-8")),
    ("an empty token", b'prefix_rule(pattern=[""], decision="allow")\n'),
    ("an empty pattern", b'prefix_rule(pattern=[], decision="allow")\n'),
    ("a list of alternatives", b'prefix_rule(pattern=[["a", "b"]], decision="allow")\n'),
    ("a justification", b'prefix_rule(pattern=["ls"], decision="allow", justification="x")\n'),
    ("a second statement on the line", b'prefix_rule(pattern=["ls"], decision="allow"); x = 1\n'),
    ("a triple-quoted token", b'prefix_rule(pattern=["""a"""], decision="allow")\n'),
    ("a whitespace-only line", b"  \n"),
    ("a NUL byte", b"\x00"),
    ("host_executable", b'host_executable(name = "git", paths = ["/usr/bin/git"])\n'),
    ("an assignment", b"X = 1\n"),
)


class FakeEntry:
    """An entry of os.scandir: stat(follow_symlinks=False) answers with a file mode or raises (Codex asks the entry's own file type)."""

    def __init__(self, name, mode=stat.S_IFREG | 0o644, error=None):
        self.name, self._mode, self._error = name, mode, error

    def stat(self, follow_symlinks=True):
        assert follow_symlinks is False  # a symlink is not followed: Codex does not load it
        if self._error:
            raise self._error
        return os.stat_result((self._mode, 0, 0, 1, 0, 0, 0, 0, 0, 0))


class FakeListing:
    """What os.scandir returns: a context manager and an iterator that yields the entries, then raises ``after`` when it has one."""

    def __init__(self, entries, after=None):
        self.entries, self.after = list(entries), after

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return self

    def __next__(self):
        if self.entries:
            return self.entries.pop(0)
        if self.after:
            raise self.after
        raise StopIteration


class RuleReviewTests(Case):
    """The hook rewrites a command to `rtk <command>` before Codex matches execution rules (codex-rs/core/src/tools/registry.rs L603-L660 at
    rust-v0.160.0; codex-rs/core/src/exec_policy.rs L316-L420 matches the rules against the rewritten command's words), so a `forbidden` or `prompt` rule
    on a command rtk rewrites no longer matches it. Three GPT reads each found a bypass in an analysing version of this review, so the tool parses nothing:
    it accepts a rule file by its sha256 on a reviewed list or when it is Codex's own allow-only format byte for byte, and refuses (--apply, before the
    app-server starts) or fails (--check) otherwise."""

    def rules(self, name="default.rules", body=GIT_PUSH_FORBIDDEN):
        directory = self.home / "rules"
        directory.mkdir(exist_ok=True)
        (directory / name).write_bytes(body)

    def assert_refused_before_anything_was_written(self, code, server):
        self.assertEqual(code, 2)
        self.app_server.assert_not_called()
        self.assertEqual(server.requests, [])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])  # no backup, nothing created

    # the reviewed list
    def test_a_reviewed_file_passes_on_the_reviewed_rtk_and_the_apply_proceeds(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(server.writes()), 1)
        self.assertIn("hcom-deny.rules; 1 on the reviewed list, 0 Codex allow-only, 0 not accepted", out)
        self.assertIn("every rule file is accepted", out)
        self.assertEqual(self.tools.calls, [["/opt/rtk/bin/rtk", "--version"], ["/opt/rtk/bin/rtk", "config"]])

    def test_a_file_is_reviewed_by_its_bytes_not_by_its_name(self):
        self.rules("renamed.rules", HCOM_DENY_RULES)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 0, err)
        self.assertIn("1 on the reviewed list", out)

    def test_one_changed_byte_ends_the_review_of_a_reviewed_file(self):
        for label, body in (("a comment appended", HCOM_DENY_RULES + b"# note\n"),
                            ("a rule appended", HCOM_DENY_RULES + GIT_PUSH_FORBIDDEN),
                            ("a space after a keyword", HCOM_DENY_RULES.replace(b"decision", b"decision ", 1)),
                            ("CRLF line ends", HCOM_DENY_RULES.replace(b"\n", b"\r\n")),
                            ("the first line dropped", HCOM_DENY_RULES.split(b"\n", 1)[1])):
            with self.subTest(label):
                self.rules("hcom-deny.rules", body)
                server = FakeServer([hook(KEY, RTK)])
                code, out, err = self.run_tool(server, "--apply")
                self.assert_refused_before_anything_was_written(code, server)
                self.assertIn("is not on the reviewed list", out)
                self.assertEqual(self.tools.calls, [])

    def test_the_counterexamples_of_the_three_reads_are_refused_before_anything_is_written(self):
        for label, body in (("git push forbidden (705e)", GIT_PUSH_FORBIDDEN),
                            ("the same with its rtk twin", GIT_PUSH_FORBIDDEN + GIT_PUSH_TWIN),
                            ("git -C . forbidden (705e)", GIT_GLOBAL_OPTION),
                            ("a prompt rule on uv (705e)", b'prefix_rule(pattern = ["uv"], decision = "prompt")\n'),
                            ("a nested prefix_rule in host_executable (705e)", NESTED_HOST_EXECUTABLE),
                            ("a raw CR in a string (705f)", RAW_CR),
                            ("a bash -lc script (705f)", BASH_LC),
                            ("phpunit.exe (705f)", PHPUNIT_EXE),
                            ("g++ and a combining mark (705f)", UNICODE_GXX)):
            with self.subTest(label):
                self.rules("default.rules", body)
                server = FakeServer([hook(KEY, RTK)])
                code, out, err = self.run_tool(server, "--apply")
                self.assert_refused_before_anything_was_written(code, server)
                self.assertIn("not on the reviewed list", out)
                self.assertIn("a rule file of the user layer is not accepted", err)
                self.assertEqual(self.tools.calls, [])  # no reviewed file: rtk is not run

    def test_a_reviewed_file_beside_an_unreviewed_one_is_still_a_refusal(self):
        self.rules("a-hcom.rules", HCOM_DENY_RULES)
        self.rules("b-push.rules", GIT_PUSH_FORBIDDEN)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("a-hcom.rules, b-push.rules; 1 on the reviewed list, 0 Codex allow-only, 1 not accepted", out)
        self.assertIn("exposed: b-push.rules", out)

    # Codex's own allow-only format
    def test_allow_only_files_pass_and_rtk_is_not_run(self):
        for label, body in (("default.rules as Codex writes it", CODEX_ALLOW), ("hcom's own hcom.rules", HCOM_OWN), ("an empty file", b""),
                            ("a comment-only file", b"# nothing here\n"), ("blank lines", b"\n\n"),
                            ("no final newline", b'prefix_rule(pattern=["ls"], decision="allow")')):
            with self.subTest(label):
                self.rules("default.rules", body)
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
                self.assertEqual(code, 0, err)
                self.assertIn("1 Codex allow-only", out)
                self.assertEqual(self.tools.calls, [])

    def test_the_allow_only_grammar_is_byte_for_byte(self):
        for body in (CODEX_ALLOW, HCOM_OWN, b"", b"\n", b"# a comment\n", b"# rtk is only a word here\n",
                     b'prefix_rule(pattern=["rtkx"], decision="allow")\n', b'prefix_rule(pattern=["xrtk", "a"], decision="allow")\n',
                     b'prefix_rule(pattern=["RTK"], decision="allow")\n', b'prefix_rule(pattern=["a", "rtk-x"], decision="allow")\n',
                     b'prefix_rule(pattern=["a", "x rtk"], decision="allow")\n'):
            self.assertTrue(trust.is_allow_only(body), body)
        for label, body in NOT_ALLOW_ONLY:
            with self.subTest(label):
                self.assertFalse(trust.is_allow_only(body), body)

    def test_a_file_outside_the_grammar_is_refused_by_the_flow_too(self):
        for label, body in NOT_ALLOW_ONLY:
            with self.subTest(label):
                self.rules("default.rules", body)
                server = FakeServer([hook(KEY, RTK)])
                code, out, err = self.run_tool(server, "--apply")
                self.assert_refused_before_anything_was_written(code, server)

    def test_the_hcom_installers_own_file_is_accepted_as_allow_only_with_either_prefix(self):
        for prefix in (("hcom",), ("uvx", "hcom")):
            body = hcom_own_rules(prefix)
            self.assertTrue(trust.is_allow_only(body), prefix)
            self.assertEqual(body.count(b"\nprefix_rule("), len(SAFE_HCOM_COMMANDS) + 2 * len(HCOM_TOOL_NAMES))
            self.rules("hcom.rules", body)
            code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
            self.assertEqual(code, 0, err)
            self.assertEqual(self.tools.calls, [])

    def test_hcoms_safe_commands_never_hold_a_character_the_grammar_refuses(self):
        for word in SAFE_HCOM_COMMANDS + HCOM_TOOL_NAMES + ("hcom", "uvx"):
            self.assertRegex(word, r'^[ !#-\[\]-~]+$')
            self.assertNotEqual(word, "rtk")

    # the flag and the other modes
    def test_the_flag_accepts_an_exposure_and_the_report_still_names_it(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply", "--allow-exec-rules")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(server.writes()), 1)
        self.assertIn("exposed: default.rules (sha256 ", out)

    def test_a_check_is_5_for_an_untrusted_hook_and_6_for_a_trusted_one_beside_an_exposure(self):
        self.rules()
        self.assertEqual(self.run_tool(FakeServer([hook(KEY, RTK)]), "--check")[0], 5)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 6)
        self.assertIn("exposed: default.rules (sha256 ", out)
        self.assertIn("execution-rule exposure", err)
        self.assertEqual(self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check", "--allow-exec-rules")[0], 0)

    def test_a_check_beside_a_reviewed_file_is_0_and_names_it(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 0, err)
        self.assertIn("hcom-deny.rules; 1 on the reviewed list", out)

    def test_a_rule_file_added_after_the_grant_makes_the_check_6_and_the_apply_refuse(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        server = FakeServer([hook(KEY, RTK, "trusted")])
        self.assertEqual(self.run_tool(server, "--check")[0], 0)
        self.rules("default.rules", GIT_PUSH_FORBIDDEN)
        self.assertEqual(self.run_tool(server, "--check")[0], 6)
        self.assert_refused_before_anything_was_written_by_apply(server)

    def assert_refused_before_anything_was_written_by_apply(self, server):
        before = len(server.requests)
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 2)  # the hook is already trusted and the review still comes first
        self.app_server.assert_not_called()
        self.assertEqual(len(server.requests), before)
        self.assertEqual(server.writes(), [])

    def test_a_dry_run_reports_and_says_the_apply_would_refuse(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server)
        self.assertEqual(code, 0, err)
        self.assertIn("exposed: default.rules (sha256 ", out)
        self.assertIn("--apply would refuse", out)
        self.assertEqual(server.writes(), [])

    # what a reviewed file depends on: the rtk it was reviewed for
    def test_another_rtk_version_ends_the_review_of_a_reviewed_file(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply", tools=FakeRtk(self.dir / "rtk-config", version="rtk 0.52.0"))
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("rtk reports 'rtk 0.52.0', but the reviewed rule file was reviewed for rtk 0.51.0", out)

    def test_a_failing_version_command_is_not_the_reviewed_version(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply", tools=FakeRtk(self.dir / "rtk-config", version_exit=1))
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("was reviewed for rtk 0.51.0", out)

    def test_rtk_config_failures_fail_closed(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        for label, tools in (("a failing config command", FakeRtk(self.dir / "rtk-config", config_exit=1)),
                             ("no Config line", FakeRtk(self.dir / "rtk-config", config_body="[hooks]\ntransparent_prefixes = []\n")),
                             ("empty output", FakeRtk(self.dir / "rtk-config", config_body=""))):
            with self.subTest(label):
                server = FakeServer([hook(KEY, RTK)])
                code, out, err = self.run_tool(server, "--apply", tools=tools)
                self.assert_refused_before_anything_was_written(code, server)
                self.assertIn("cannot check: cannot read the configuration `rtk config` reports", out)

    def test_a_configured_transparent_prefix_ends_the_review(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply", tools=FakeRtk(self.dir / "rtk-config", prefixes=["sudo"]))
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("transparent_prefixes is not empty", out)

    def test_a_config_that_does_not_say_transparent_prefixes_is_empty_ends_the_review(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        for label, body in (("the key is missing", f"Config: {self.dir / 'rtk-config' / 'config.toml'}\n\n[hooks]\nexclude_commands = []\n"),
                            ("a spaced empty list", f"Config: {self.dir / 'rtk-config' / 'config.toml'}\n\n[hooks]\ntransparent_prefixes = [ ]\n"),
                            ("a commented key", f"Config: {self.dir / 'rtk-config' / 'config.toml'}\n\n# transparent_prefixes = []\n")):
            with self.subTest(label):
                server = FakeServer([hook(KEY, RTK)])
                code, out, err = self.run_tool(server, "--apply", tools=FakeRtk(self.dir / "rtk-config", config_body=body))
                self.assert_refused_before_anything_was_written(code, server)
                self.assertIn("transparent_prefixes is not empty, or `rtk config` does not say it is", out)

    def test_user_global_toml_filters_end_the_review_and_comments_and_the_schema_line_do_not(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        config = self.dir / "rtk-config"
        config.mkdir()
        for label, body, accepted in (("a template of comments", "# rtk filters\n# schema_version = 1\n\n", True),
                                      ("only the schema line", "schema_version = 1\n", True),
                                      ("the schema line with a comment", "schema_version = 1  # the format\n", True),
                                      ("an empty file", "", True),
                                      ("a filter", 'schema_version = 1\n[filters.x]\nmatch_command = "^hcom"\n', False),
                                      ("a table header alone", "[filters.x]\n", False),
                                      ("another key", "x = 1\n", False),
                                      ("a string with a comment sign", 'x = "#"\n', False)):
            with self.subTest(label):
                (config / "filters.toml").write_text(body, encoding="utf-8")
                server = FakeServer([hook(KEY, RTK, "trusted")])
                code, out, err = self.run_tool(server, "--check")
                self.assertEqual(code, 0 if accepted else 6, out)
                if not accepted:
                    self.assertIn("rtk has user TOML filters", out)

    def test_a_filters_file_that_cannot_be_read_fails_closed(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        config = self.dir / "rtk-config"
        config.mkdir()
        (config / "filters.toml").write_bytes(b"\xff\xfe")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 6)
        self.assertIn("cannot check: cannot read rtk's filters.toml", out)
        (config / "filters.toml").unlink()
        (config / "filters.toml").mkdir()
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 6)
        self.assertIn("cannot check: cannot read rtk's filters.toml", out)

    def test_a_reviewed_file_without_a_usable_rtk_executable_fails_closed(self):
        (self.home / "rules").mkdir()
        (self.home / "rules" / "hcom-deny.rules").write_bytes(HCOM_DENY_RULES)
        with mock.patch.object(trust.shutil, "which", return_value=None):
            review = trust.review_rules(self.home, None, FakeRtk(self.dir / "rtk-config").run)
        self.assertTrue(review.blocked)
        self.assertIn("no rtk executable on PATH", " ".join(review.problems))
        for error in (FileNotFoundError(2, "No such file"), PermissionError(13, "Permission denied"), ValueError("not text"),
                      subprocess.TimeoutExpired("rtk", 30)):
            with self.subTest(type(error).__name__):
                review = trust.review_rules(self.home, "/opt/rtk/bin/rtk", mock.Mock(side_effect=error))
                self.assertTrue(review.blocked)
                self.assertIn("cannot run /opt/rtk/bin/rtk", " ".join(review.problems))

    def test_rtk_is_found_on_the_path_when_no_flag_names_it(self):
        (self.home / "rules").mkdir()
        (self.home / "rules" / "hcom-deny.rules").write_bytes(HCOM_DENY_RULES)
        tools = FakeRtk(self.dir / "rtk-config")
        with mock.patch.object(trust.shutil, "which", return_value="/usr/local/bin/rtk"):
            review = trust.review_rules(self.home, None, tools.run)
        self.assertFalse(review.blocked, review.lines(self.home))
        self.assertEqual(tools.calls[0][0], "/usr/local/bin/rtk")

    def test_rtk_runs_with_telemetry_off_and_without_a_terminal(self):
        (self.home / "rules").mkdir()
        (self.home / "rules" / "hcom-deny.rules").write_bytes(HCOM_DENY_RULES)
        seen = []

        def runner(command, **kwargs):
            seen.append(kwargs)
            return FakeRtk(self.dir / "rtk-config").run(command)
        trust.review_rules(self.home, "/opt/rtk/bin/rtk", runner)
        self.assertEqual(len(seen), 2)
        for kwargs in seen:
            self.assertEqual(kwargs["env"]["RTK_TELEMETRY_DISABLED"], "1")
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(kwargs["timeout"], 30)
            self.assertIs(kwargs["check"], False)

    # no rule files: nothing is run
    def test_without_a_rules_directory_nothing_is_run_and_the_list_is_not_read(self):
        with mock.patch.object(trust, "REVIEWED_FILE", self.dir / "no-such-list.json"):
            code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tools.calls, [])
        self.assertNotIn("execution rules", out)

    def test_other_files_and_non_files_hold_no_rule_and_are_not_read(self):
        directory = self.home / "rules"
        directory.mkdir()
        (directory / "notes.txt").write_bytes(GIT_PUSH_FORBIDDEN)
        (directory / "rules").write_bytes(GIT_PUSH_FORBIDDEN)  # no extension
        (directory / "default.rules.bak").write_bytes(GIT_PUSH_FORBIDDEN)
        (directory / "dir.rules").mkdir()
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tools.calls, [])
        self.assertNotIn("execution rules", out)

    def test_a_symlinked_rules_file_is_not_loaded_by_codex_so_it_is_not_reviewed(self):
        (self.home / "rules").mkdir()
        real = self.dir / "elsewhere.rules"
        real.write_bytes(GIT_PUSH_FORBIDDEN)
        try:
            (self.home / "rules" / "link.rules").symlink_to(real)
        except OSError:
            self.skipTest("no symlinks here")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertNotIn("execution rules", out)

    def test_a_named_pipe_is_not_loaded_and_is_never_opened(self):
        (self.home / "rules").mkdir()
        try:
            os.mkfifo(self.home / "rules" / "pipe.rules")
        except (AttributeError, OSError):
            self.skipTest("no named pipes here")

        def stuck(signum, frame):
            raise TimeoutError("the review opened a named pipe")
        old = signal.signal(signal.SIGALRM, stuck)
        signal.alarm(10)
        try:
            code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        self.assertEqual(code, 0, err)
        self.assertNotIn("execution rules", out)

    def test_a_rule_file_that_cannot_be_read_fails_closed_and_so_does_any_other_file(self):
        self.rules("a-ok.rules", CODEX_ALLOW)
        self.rules("b-hidden.rules", CODEX_ALLOW)
        real = trust.Path.read_bytes

        def read_bytes(path):
            if path.name == "b-hidden.rules":
                raise PermissionError(13, "Permission denied")
            return real(path)
        server = FakeServer([hook(KEY, RTK)])
        with mock.patch.object(trust.Path, "read_bytes", read_bytes):
            code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("cannot check: cannot read b-hidden.rules", out)
        self.assertIn("1 Codex allow-only", out)

    # the reviewed list itself fails closed
    def test_a_missing_or_malformed_reviewed_list_fails_closed_even_for_an_allow_only_file(self):
        self.rules("default.rules", CODEX_ALLOW)
        good_entry = json.loads(REVIEWED.read_text(encoding="utf-8"))["entries"][0]
        bad = {"missing file": None, "not json": "not json", "no entries": "{}", "entries not a list": '{"entries": 3}',
               "an entry without a hash": json.dumps({"entries": [{k: v for k, v in good_entry.items() if k != "sha256"}]}),
               "a malformed hash": json.dumps({"entries": [{**good_entry, "sha256": "abc"}]}),
               "a hash that is too long": json.dumps({"entries": [{**good_entry, "sha256": good_entry["sha256"] + "0"}]}),
               "an uppercase hash": json.dumps({"entries": [{**good_entry, "sha256": good_entry["sha256"].upper()}]}),
               "no reviewed_for": json.dumps({"entries": [{k: v for k, v in good_entry.items() if k != "reviewed_for"}]}),
               "a version output that is not rtk's": json.dumps({"entries": [{**good_entry, "reviewed_for": {"rtk_version_output": "0.51.0"}}]})}
        for label, text in bad.items():
            with self.subTest(label):
                path = self.dir / "exec_rules_reviewed.json"
                path.unlink(missing_ok=True)
                if text is not None:
                    path.write_text(text, encoding="utf-8")
                server = FakeServer([hook(KEY, RTK)])
                with mock.patch.object(trust, "REVIEWED_FILE", path):
                    code, out, err = self.run_tool(server, "--apply")
                self.assert_refused_before_anything_was_written(code, server)
                self.assertIn("cannot check: cannot read exec_rules_reviewed.json", out)

    def test_the_review_writes_nothing_into_the_home_it_reviews(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        before = {p.name: p.read_bytes() for p in (self.home / "rules").iterdir()}
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])
        self.assertEqual({p.name: p.read_bytes() for p in (self.home / "rules").iterdir()}, before)

    # listing (705e finding 1 and the earlier P1: only opening the directory may say it is missing; 705f P2: DirEntry.is_file() suppresses the error)
    def refused_listing(self, listing, *extra):
        (self.home / "rules").mkdir(exist_ok=True)
        server = FakeServer([hook(KEY, RTK)])
        with mock.patch.object(trust.os, "scandir", return_value=listing):
            code, out, err = self.run_tool(server, "--apply", *extra)
        return server, code, out, err

    def test_705f_p2_an_entry_that_vanished_is_a_listing_failure_not_no_rules(self):
        server, code, out, err = self.refused_listing(FakeListing([FakeEntry("restricted.rules", error=FileNotFoundError(2, "No such file"))]))
        self.assertEqual(code, 2)
        self.assertIn("cannot list", out)
        self.assertIn("could not be checked", err)
        self.app_server.assert_not_called()
        self.assertEqual(server.requests, [])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])  # no backup

    def test_every_entrys_file_type_is_asked_before_its_extension_so_an_error_on_any_entry_fails(self):
        for entry in (FakeEntry("notes.txt", error=PermissionError(13, "Permission denied")), FakeEntry("x.rules", error=OSError(5, "I/O error")),
                      FakeEntry("noext", error=FileNotFoundError(2, "No such file"))):
            with self.subTest(entry=entry.name):
                server, code, out, err = self.refused_listing(FakeListing([entry]))
                self.assertEqual(code, 2)
                self.assertIn("cannot list", out)
                self.app_server.assert_not_called()

    def test_an_error_during_the_iteration_is_a_listing_failure_even_after_some_entries(self):
        for error in (FileNotFoundError(2, "No such file"), PermissionError(13, "Permission denied")):
            with self.subTest(error=type(error).__name__):
                server, code, out, err = self.refused_listing(FakeListing([FakeEntry("a.txt")], after=error))
                self.assertEqual(code, 2)
                self.assertIn("cannot list", out)
                self.assertEqual(server.requests, [])

    def test_only_a_regular_file_with_the_rules_extension_is_listed(self):
        entries = [FakeEntry("a.rules"), FakeEntry("b.rules", mode=stat.S_IFLNK | 0o777), FakeEntry("c.rules", mode=stat.S_IFDIR | 0o755),
                   FakeEntry("d.rules", mode=stat.S_IFIFO | 0o644), FakeEntry("e.RULES"), FakeEntry("f.rules.bak"), FakeEntry("rules"),
                   FakeEntry("g.txt"), FakeEntry("h.rules", mode=stat.S_IFSOCK | 0o644), FakeEntry("i.rules", mode=stat.S_IFCHR | 0o644)]
        with mock.patch.object(trust.os, "scandir", return_value=FakeListing(entries)):
            self.assertEqual([path.name for path in trust.rule_files(self.home)], ["a.rules"])

    def test_the_listing_is_sorted_and_names_the_directory(self):
        with mock.patch.object(trust.os, "scandir", return_value=FakeListing([FakeEntry("z.rules"), FakeEntry("a.rules")])):
            self.assertEqual(trust.rule_files(self.home), [self.home / "rules" / "a.rules", self.home / "rules" / "z.rules"])

    def test_only_opening_the_directory_may_report_it_missing(self):
        (self.home / "rules").mkdir()
        with mock.patch.object(trust.os, "scandir", side_effect=FileNotFoundError(2, "No such file")):
            code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)  # Codex: a missing rules directory is no rules (collect_policy_files L1125)

    def test_an_open_error_is_not_no_rules_it_refuses_before_any_write(self):
        (self.home / "rules").mkdir()
        server = FakeServer([hook(KEY, RTK)])
        with mock.patch.object(trust.os, "scandir", side_effect=PermissionError(13, "Permission denied")):
            code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 2)
        self.assertIn("cannot list", out)
        self.assertIn("could not be checked", err)
        self.app_server.assert_not_called()
        self.assertEqual(server.requests, [])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])  # no backup

    def test_a_rules_path_that_is_a_file_is_a_listing_error_but_a_missing_one_is_not(self):
        (self.home / "rules").write_text("not a directory\n", encoding="utf-8")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("cannot list", out)


class ReviewedListTests(unittest.TestCase):
    """tools/adoption/exec_rules_reviewed.json: each entry is the review of one exact file for one rtk version."""

    def setUp(self):
        self.listed = json.loads(REVIEWED.read_text(encoding="utf-8"))
        self.entries = self.listed["entries"]

    def test_the_list_has_its_schema_and_unique_well_formed_hashes(self):
        self.assertEqual(self.listed["schema"], "exec-rules-reviewed/1")
        digests = [entry["sha256"] for entry in self.entries]
        self.assertEqual(len(digests), len(set(digests)))
        for digest in digests:
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(sorted(trust.load_reviewed()), sorted(digests))

    def test_the_hcom_entry_is_the_exact_file_of_the_fixture_and_nothing_else(self):
        self.assertEqual([entry["name"] for entry in self.entries], ["hcom-deny.rules"])
        self.assertEqual(self.entries[0]["sha256"], hashlib.sha256(HCOM_DENY_RULES).hexdigest())

    def test_every_rule_of_the_fixture_starts_with_a_first_token_of_its_entry(self):
        text = HCOM_DENY_RULES.decode("utf-8")
        starts = re.findall(r'^\s*pattern\s*=\s*\["([^"]+)"', text, re.M)
        self.assertEqual(len(starts), text.count("prefix_rule("))
        self.assertEqual(len(starts), 4)
        self.assertLessEqual(set(starts), set(self.entries[0]["first_tokens"]))

    def test_every_entry_is_reviewed_for_the_pinned_rtk(self):
        pins = json.loads((ROOT / "adoption" / "pins-linux-x86_64.json").read_text(encoding="utf-8"))
        rtk = next(tool for tool in pins["tools"] if tool["id"] == "rtk")
        for entry in self.entries:
            self.assertEqual(entry["reviewed_for"]["rtk_version_output"], f"rtk {rtk['version']}", "a pin move re-reviews the list")
            self.assertIn(entry["reviewed_for"]["rtk_commit"], rtk["install_note"])

    def test_every_entry_cites_evidence_that_exists(self):
        for entry in self.entries:
            self.assertTrue(entry["evidence"])
            for cited in entry["evidence"]:
                self.assertTrue((ROOT / cited).is_file(), cited)

    def test_the_retained_binary_check_covers_every_entry_and_rewrote_none_of_its_commands(self):
        record = json.loads((E2E / "rtk-rewrite-heads-check.json").read_text(encoding="utf-8"))
        self.assertTrue(record["ok"])
        reviewed = record["reviewed_entries"]
        self.assertEqual(reviewed["sha256"], [entry["sha256"] for entry in self.entries])
        self.assertEqual(reviewed["first_tokens"], sorted({token for entry in self.entries for token in entry["first_tokens"]}))
        self.assertEqual(reviewed["rewritten"], [])
        self.assertGreater(reviewed["commands"], 300)
        for entry in self.entries:
            self.assertEqual(record["rtk"], entry["reviewed_for"]["rtk_version_output"])

    def test_every_rule_file_of_the_install_plan_is_on_the_list_or_allow_only(self):
        """Vacuous until a plan row ships a rule file (#713's config/hcom-deny.rules): then it fails if the file differs from the reviewed bytes."""
        listed = {entry["sha256"] for entry in self.entries}
        for path in sorted(PLAN_CONFIG.glob("*.rules")):
            data = path.read_bytes()
            self.assertTrue(hashlib.sha256(data).hexdigest() in listed or trust.is_allow_only(data), str(path))


class ToolShapeTests(unittest.TestCase):
    """The design property that survived three reads: the tool reads no rule file as a language."""

    def test_the_tool_parses_no_rule_file_and_reads_no_derived_head_list(self):
        source = (ROOT / "tools" / "adoption" / "codex_hook_trust.py").read_text(encoding="utf-8")
        for needle in ("import ast", "import tomllib", "rtk_rewrite_heads", "rtk-rewrite-heads"):
            self.assertNotIn(needle, source, needle)

    def test_the_heads_are_evidence_beside_the_check_and_not_beside_the_tool(self):
        self.assertTrue((E2E / "rtk-rewrite-heads.json").is_file())
        self.assertFalse((ROOT / "tools" / "adoption" / "rtk_rewrite_heads.json").exists())


class EvidenceTests(unittest.TestCase):
    """The review evidence for the list, kept beside the check that produced it (neither file is read by the tool)."""

    def setUp(self):
        self.fixture = json.loads((E2E / "rtk-rewrite-heads.json").read_text(encoding="utf-8"))

    def test_the_heads_are_derived_for_the_pinned_rtk(self):
        pins = json.loads((ROOT / "adoption" / "pins-linux-x86_64.json").read_text(encoding="utf-8"))
        rtk = next(tool for tool in pins["tools"] if tool["id"] == "rtk")
        self.assertEqual(self.fixture["rtk_version_output"], f"rtk {rtk['version']}")
        self.assertIn(self.fixture["source"]["commit"], rtk["install_note"])
        self.assertEqual(self.fixture["source"]["tag"], f"v{rtk['version']}")

    def test_every_head_has_line_provenance_in_the_pinned_source(self):
        self.assertGreater(len(self.fixture["heads"]), 100)
        for entry in self.fixture["heads"]:
            self.assertTrue(entry["from"], entry)
            for source in entry["from"]:
                self.assertRegex(source, r"^src/(discover/(rules|registry)\.rs|filters/[a-z0-9-]+\.toml):L\d+")
        self.assertEqual(self.fixture["source"]["rules_patterns"], 94)
        for digest in self.fixture["source"]["blobs_sha256"].values():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_the_retained_binary_check_agrees_with_the_fixture(self):
        record = json.loads((E2E / "rtk-rewrite-heads-check.json").read_text(encoding="utf-8"))
        self.assertTrue(record["ok"])
        self.assertEqual(record["fixture_rtk"], self.fixture["rtk_version_output"])
        self.assertEqual(record["rtk"], self.fixture["rtk_version_output"])
        self.assertEqual(record["heads"], len(self.fixture["heads"]))
        self.assertEqual(record["scan"]["gaps"], [])
        self.assertEqual(record["wrappers"]["gaps"], [])
        self.assertEqual(record["positive_controls"]["without_a_rewrite"], [])
        self.assertEqual(record["positive_controls"]["patterns"], self.fixture["source"]["rules_patterns"])
        self.assertEqual(record["hcom_commands_rewritten"], [])
        self.assertEqual(record["variants"]["gaps"], [])
        self.assertGreater(record["variants"]["rewritten"], 400)
        for form in ("exe", "EXE", "bat", "cmd", "ps1", "winpath", "dotslash_win", "abs", "rel", "slash", "dash"):
            self.assertIn(form, record["variants"]["forms_rewritten"])


if __name__ == "__main__":
    unittest.main()
