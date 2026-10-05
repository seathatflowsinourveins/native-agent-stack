"""tools/adoption/codex_hook_trust.py: trust the named hooks of one Codex home through config/batchWrite and read it back.

The app-server is a fake that answers hooks/list and config/batchWrite the way the released codex-cli 0.159.3 does (the field
names are those of its hooks/list response; the write shape is the TUI's write_hook_trusts); the rule review's two rtk commands are a
local stand-in too (FakeRtk: `rtk --version` and `rtk config`, with the output shapes of rtk 0.51.0); no real Codex, no real rtk, no real
home, no network: synthetic local checks, not upstream tests. The real client and the real tools were run against scratch homes in
evidence/artifacts/token-stack-fresh-session-e2e-20261004/.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import io
import json
import os
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
    src/core/config.rs show_config prints it in v0.51.0). The review decides from the heads fixture, so nothing else of rtk is needed."""

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


# The rules of #713's config/hcom-deny.rules (head 5f295f254), kept as the positive control: prefix rules on `hcom ...` and `uvx hcom ...`
# that rtk does not rewrite. #713 is not merged yet, so the fixture is a copy.
E2E = ROOT / "evidence" / "artifacts" / "token-stack-fresh-session-e2e-20261004"
HCOM_DENY_RULES = (E2E / "fixtures" / "hcom-deny.rules").read_text(encoding="utf-8")
GIT_PUSH_FORBIDDEN = 'prefix_rule(pattern = ["git", "push"], decision = "forbidden")\n'
GIT_PUSH_TWIN = 'prefix_rule(pattern = ["rtk", "git", "push"], decision = "forbidden")\n'
# 705e's counterexample: the real codex-cli 0.159.3 evaluator accepts it and forbids `git push origin main`, because the argument expression
# registers a rule.
NESTED_HOST_EXECUTABLE = ('host_executable(name = prefix_rule(pattern = ["git", "push"], decision = "forbidden") or "git", '
                          'paths = ["/usr/bin/git"])\n')


class FakeEntry:
    """An entry of os.scandir: is_file() answers or raises."""

    def __init__(self, name, is_file=True, error=None):
        self.name, self._is_file, self._error = name, is_file, error

    def is_file(self, follow_symlinks=True):
        assert follow_symlinks is False  # Codex asks the entry's own file type, which does not follow symlinks
        if self._error:
            raise self._error
        return self._is_file


class FakeListing:
    """What os.scandir returns: a context manager and an iterator that yields the entries, then raises ``after`` when it has one."""

    def __init__(self, entries, after=None):
        self.entries, self.after, self.asked = list(entries), after, []

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


class ExecutionRuleTests(Case):
    """The hook rewrites a command to `rtk <command>` before Codex matches execution rules (codex-rs/core/src/tools/registry.rs L603-L660 at
    rust-v0.160.0; codex-rs/core/src/exec_policy.rs L316-L420 matches the rules against the rewritten command's words), so a `forbidden` or
    `prompt` rule on a command rtk rewrites no longer matches it, and the rewrite space (global options, wrappers, absolute paths, word-changing
    rewrites) is not finite. The tool therefore refuses (--apply, before the app-server starts) or fails (--check) unless every forbidden or prompt
    rule starts with a word that rtk 0.51.0 cannot route at all, read from the heads fixture derived from rtk's source."""

    def rules(self, name="default.rules", body=GIT_PUSH_FORBIDDEN):
        directory = self.home / "rules"
        directory.mkdir(exist_ok=True)
        (directory / name).write_text(body, encoding="utf-8")

    def assert_refused_before_anything_was_written(self, code, server):
        self.assertEqual(code, 2)
        self.app_server.assert_not_called()
        self.assertEqual(server.requests, [])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])  # no backup, nothing created

    # the controls
    def test_hcom_rules_pass_the_review_and_the_apply_proceeds(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(server.writes()), 1)
        self.assertIn("hcom-deny.rules; 4 rule(s), 4 forbidden or prompt; checked against the commands rtk 0.51.0 can rewrite", out)
        self.assertIn("no forbidden or prompt rule starts with a command rtk 0.51.0 can rewrite", out)
        self.assertEqual([call[1:] for call in self.tools.calls], [["--version"], ["config"]])

    def test_a_forbid_rule_on_git_push_is_refused_before_the_server_starts(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn('exposed: default.rules:1: forbidden rule ["git", "push"] starts with `git`, a command rtk can rewrite '
                      "(src/discover/rules.rs:L61)", out)
        self.assertIn("--allow-exec-rules", err)

    def test_an_rtk_twin_does_not_save_a_rule_because_a_twin_cannot_be_shown_to_cover_every_rewrite(self):
        self.rules("default.rules", GIT_PUSH_FORBIDDEN + GIT_PUSH_TWIN)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("exposed: default.rules:1:", out)
        self.assertNotIn("default.rules:2:", out)  # the twin itself starts with `rtk`, which is not a head

    def test_705e_a_prefix_rtk_leaves_alone_but_extends_is_refused(self):
        # `git -C .` is not rewritten, `git -C . push origin main` is (rtk hook check, exit 1 and exit 0): a prefix probe saw nothing.
        self.rules("default.rules", 'prefix_rule(pattern = ["git", "-C", "."], decision = "forbidden")\n')
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn('forbidden rule ["git", "-C", "."] starts with `git`', out)

    def test_705e_broad_rules_on_uv_and_npx_are_refused(self):
        self.rules("default.rules", 'prefix_rule(pattern = ["uv"], decision = "prompt")\nprefix_rule(pattern = [["npx", "bunx"]], decision = "forbidden")\n')
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn('prompt rule ["uv"] starts with `uv`', out)
        self.assertIn('forbidden rule [["npx", "bunx"]] starts with `npx`', out)

    # which words count
    def test_every_kind_of_head_is_refused(self):
        for token, source in (("git", "rules.rs"), ("yadm", "rules.rs"), ("cat", "rules.rs"), ("nice", "PROCESS_WRAPPERS"), ("timeout", "PROCESS_WRAPPERS"),
                              ("command", "SHELL_KEYWORD_PREFIXES"), ("noglob", "SHELL_KEYWORD_PREFIXES"), ("env", "ENV_PREFIX"), ("FOO=1", "ENV_PREFIX"),
                              ("/usr/bin/git", "rules.rs"), ("./vendor/bin/phpunit", "rules.rs"), ("python3.11", "rules.rs"), ("pnpx", "rules.rs"),
                              ("gcc-13", "gcc.toml"), ("g++", "gcc.toml"), ("jq", "jq.toml"), ("ssh", "ssh.toml"), ("mise", "mise.toml"), ("sbt", "rules.rs:L575"),
                              ("du-sh", "rules.rs")):
            with self.subTest(token=token):
                self.rules("default.rules", f"prefix_rule(pattern = [{json.dumps(token)}, \"x\"], decision = \"forbidden\")\n")
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
                self.assertEqual(code, 2)
                self.assertIn(f"starts with `{token}`, a command rtk can rewrite (", out)
                self.assertIn(source, out)

    def test_a_first_token_that_is_a_list_of_alternatives_is_refused_when_any_alternative_is_a_head(self):
        self.rules("default.rules", 'prefix_rule(pattern = [["hcom", "git"], "push"], decision = "forbidden")\n')
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("starts with `git`", out)

    def test_words_rtk_cannot_route_pass(self):
        for token in ("hcom", "uvx", "rtk", "sudo", "doas", "xargs", "watch", "bash", "node", "codex", "claude", "hcom-x", "gitx", "makepkg"):
            with self.subTest(token=token):
                self.rules("default.rules", f"prefix_rule(pattern = [{json.dumps(token)}, \"x\"], decision = \"forbidden\")\n")
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
                self.assertEqual(code, 0, out + err)

    def test_prompt_rules_restrict_like_forbidden_rules(self):
        self.rules("default.rules", 'prefix_rule(pattern = ["git", "commit"], decision = "prompt")\n')
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("prompt rule", out)

    def test_an_allow_rule_on_a_head_is_a_note_not_a_refusal_and_needs_no_rtk(self):
        for body in ('prefix_rule(pattern = ["git", "status"], decision = "allow")\n', 'prefix_rule(pattern = ["git", "status"])\n'):  # allow is the default
            with self.subTest(body=body):
                self.rules("default.rules", body)
                server = FakeServer([hook(KEY, RTK)])
                code, out, err = self.run_tool(server, "--apply")
                self.assertEqual(code, 0, err)
                self.assertIn('note: default.rules:1: allow rule ["git", "status"] starts with `git`, a command rtk can rewrite (', out)
                self.assertEqual(self.tools.calls, [])
                self.assertEqual(len(server.writes()), 1)

    # the gate and rtk's own configuration
    def test_another_rtk_version_fails_closed_because_the_heads_were_derived_for_one(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply", tools=FakeRtk(self.dir / "c", version="rtk 0.52.0"))
        self.assertEqual(code, 2)
        self.assertIn("rtk reports 'rtk 0.52.0', but the head set was derived for 'rtk 0.51.0'", out)

    def test_rtk_failures_fail_closed(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        for name, tools in (("version exit", FakeRtk(self.dir / "c", version_exit=1)), ("config exit", FakeRtk(self.dir / "c", config_exit=1)),
                            ("config not toml", FakeRtk(self.dir / "c", config_body="Config: x/config.toml\n\nnot toml at all\n")),
                            ("no Config line", FakeRtk(self.dir / "c", config_body="[hooks]\ntransparent_prefixes = []\n")),
                            ("prefixes not a list", FakeRtk(self.dir / "c", config_body="Config: x/config.toml\n\n[hooks]\ntransparent_prefixes = 3\n"))):
            with self.subTest(name=name):
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply", tools=tools)
                self.assertEqual(code, 2)
                self.assertIn("cannot check:", out)
                self.app_server.assert_not_called()

    def test_rules_without_an_rtk_executable_fail_closed(self):
        self.rules()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(trust.lane, "AppServer") as app_server, mock.patch.object(trust.shutil, "which", return_value=None):
            code = trust.main(["--codex", str(self.codex), "--codex-home", str(self.home), "--command", RTK, "--apply"])
        self.assertEqual(code, 2)
        self.assertIn("no rtk executable", out.getvalue())
        app_server.assert_not_called()

    def test_a_configured_transparent_prefix_adds_its_first_word_as_a_head(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply", tools=FakeRtk(self.dir / "c", prefixes=["hcom run"]))
        self.assertEqual(code, 2)
        self.assertIn("starts with `hcom`, a command rtk can rewrite ([hooks].transparent_prefixes of the rtk config)", out)

    def test_user_global_toml_filters_add_their_first_word_as_a_head(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        config = self.dir / "rtk-config"
        config.mkdir()
        (config / "filters.toml").write_text('schema_version = 1\n[filters.mine]\nmatch_command = "^hcom\\\\b"\n', encoding="utf-8")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("starts with `hcom`, a command rtk can rewrite (filter mine in filters.toml)", out)

    def test_a_filters_file_without_filters_a_missing_one_and_a_template_are_fine(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        config = self.dir / "rtk-config"
        config.mkdir()
        for body in (None, "# only comments\nschema_version = 1\n# [filters.x]\n# match_command = \"^x\\\\b\"\n"):
            with self.subTest(body=body):
                if body is not None:
                    (config / "filters.toml").write_text(body, encoding="utf-8")
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
                self.assertEqual(code, 0, out + err)

    def test_a_filter_whose_pattern_is_not_a_plain_word_or_a_file_that_is_not_toml_fails_closed(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        config = self.dir / "rtk-config"
        config.mkdir()
        for body in ('schema_version = 1\n[filters.f]\nmatch_command = "^(a|b)\\\\b"\n', "not toml ["):
            with self.subTest(body=body):
                (config / "filters.toml").write_text(body, encoding="utf-8")
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
                self.assertEqual(code, 2)
                self.assertIn("cannot check:", out)

    # the flag and the other modes
    def test_the_flag_accepts_an_exposure_and_the_report_still_names_it(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply", "--allow-exec-rules")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(server.writes()), 1)
        self.assertIn("exposed: default.rules:1:", out)

    def test_a_check_is_5_for_an_untrusted_hook_and_6_for_a_trusted_one_beside_an_exposure(self):
        self.rules()
        self.assertEqual(self.run_tool(FakeServer([hook(KEY, RTK)]), "--check")[0], 5)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 6)
        self.assertIn("exposed: default.rules:1:", out)
        self.assertIn("execution-rule exposure", err)
        self.assertEqual(self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check", "--allow-exec-rules")[0], 0)

    def test_a_check_beside_rules_that_hold_is_0_and_names_them(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 0, err)
        self.assertIn("hcom-deny.rules; 4 rule(s)", out)

    def test_a_dry_run_reports_and_says_the_apply_would_refuse(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server)
        self.assertEqual(code, 0, err)
        self.assertIn("exposed: default.rules:1:", out)
        self.assertIn("--apply would refuse", out)
        self.assertEqual(server.writes(), [])

    def test_an_already_trusted_hook_is_still_refused_by_apply_because_the_review_comes_first(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK, "trusted")])
        code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)

    # no rule files: nothing is run
    def test_without_a_rules_directory_rtk_is_not_run(self):
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tools.calls, [])
        self.assertNotIn("execution rules", out)

    def test_other_files_empty_and_comment_only_rules_files_and_non_files_hold_no_rule(self):
        directory = self.home / "rules"
        directory.mkdir()
        (directory / "notes.txt").write_text(GIT_PUSH_FORBIDDEN, encoding="utf-8")
        (directory / "empty.rules").write_text("  \n", encoding="utf-8")
        (directory / "comments.rules").write_text("# nothing here\n", encoding="utf-8")
        (directory / "dir.rules").mkdir()
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tools.calls, [])  # no restricting rule: rtk is not asked

    def test_a_symlinked_rules_file_is_not_loaded_by_codex_so_it_is_not_reviewed(self):
        (self.home / "rules").mkdir()
        real = self.dir / "elsewhere.rules"
        real.write_text(GIT_PUSH_FORBIDDEN, encoding="utf-8")
        try:
            (self.home / "rules" / "link.rules").symlink_to(real)
        except OSError:
            self.skipTest("no symlinks here")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)

    # fail closed on the listing (705e finding 1 and the earlier P1: only opening the directory may say it is missing)
    def refused_listing(self, listing, *extra):
        (self.home / "rules").mkdir(exist_ok=True)
        server = FakeServer([hook(KEY, RTK)])
        with mock.patch.object(trust.os, "scandir", return_value=listing):
            code, out, err = self.run_tool(server, "--apply", *extra)
        return server, code, out, err

    def test_an_entry_that_raises_file_not_found_is_a_listing_failure_not_no_rules(self):
        server, code, out, err = self.refused_listing(FakeListing([FakeEntry("restricted.rules", error=FileNotFoundError(2, "No such file"))]))
        self.assertEqual(code, 2)
        self.assertIn("cannot list", out)
        self.assertIn("could not be checked", err)
        self.app_server.assert_not_called()
        self.assertEqual(server.requests, [])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])  # no backup

    def test_every_entrys_file_type_is_asked_before_its_extension_so_an_error_on_any_entry_fails(self):
        for entry in (FakeEntry("notes.txt", error=PermissionError(13, "Permission denied")), FakeEntry("x.rules", error=OSError(5, "I/O error"))):
            with self.subTest(entry=entry.name):
                server, code, out, err = self.refused_listing(FakeListing([entry]))
                self.assertEqual(code, 2)
                self.assertIn("cannot list", out)
                self.app_server.assert_not_called()

    def test_an_error_during_the_iteration_is_a_listing_failure_even_after_some_entries(self):
        for error in (FileNotFoundError(2, "No such file"), PermissionError(13, "Permission denied")):
            with self.subTest(error=type(error).__name__):
                server, code, out, err = self.refused_listing(FakeListing([FakeEntry("a.txt", is_file=True)], after=error))
                self.assertEqual(code, 2)
                self.assertIn("cannot list", out)
                self.assertEqual(server.requests, [])

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

    # fail closed on what cannot be read (705e finding 2: Codex evaluates argument expressions, so a nested call can register a rule)
    def test_705e_a_prefix_rule_nested_in_host_executable_is_refused(self):
        self.rules("default.rules", NESTED_HOST_EXECUTABLE)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("the name argument of host_executable() is not a literal", out)

    def test_every_argument_of_both_builtins_must_be_a_literal(self):
        nested = 'prefix_rule(pattern = ["git", "push"], decision = "forbidden")'
        for name, body in (("justification", f'prefix_rule(pattern = ["a"], justification = {nested} or "why")\n'),
                           ("decision", 'prefix_rule(pattern = ["a"], decision = "allow" if True else "x")\n'),
                           ("not_match", f'prefix_rule(pattern = ["a"], not_match = [{nested}])\n'),
                           ("match", f'prefix_rule(pattern = ["a"], match = [{nested}])\n'),
                           ("pattern", 'prefix_rule(pattern = ["a"] + ["b"])\n'),
                           ("paths", f'host_executable(name = "git", paths = [{nested}])\n'),
                           ("name", 'host_executable(name = "g" + "it", paths = [])\n')):
            with self.subTest(argument=name):
                self.rules("default.rules", body)
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
                self.assertEqual(code, 2)
                self.assertIn("is not a literal", out)
                self.app_server.assert_not_called()

    def test_forms_this_tool_does_not_read_are_refused(self):
        for name, body in (("assign", 'NAMES = ["git"]\nprefix_rule(pattern = NAMES)\n'), ("syntax", "prefix_rule(pattern = [\n"),
                           ("other call", 'network_rule(host = "x")\n'), ("positional", 'prefix_rule(["git"])\n'), ("star star", 'prefix_rule(**{"pattern": ["git"]})\n'),
                           ("unknown argument", 'prefix_rule(pattern = ["a"], extra = 1)\n'), ("unknown host argument", 'host_executable(name = "git", paths = [], x = 1)\n'),
                           ("empty pattern", "prefix_rule(pattern = [])\n"), ("no pattern", 'prefix_rule(decision = "allow")\n'),
                           ("bad decision", 'prefix_rule(pattern = ["a"], decision = "oops")\n'), ("if", 'if True:\n    prefix_rule(pattern = ["git"])\n'),
                           ("def", 'def prefix_rule(**kw):\n    pass\n')):
            with self.subTest(name=name):
                self.rules("default.rules", body)
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
                self.assertEqual(code, 2)
                self.assertIn("cannot read the rules of default.rules", out)
                self.app_server.assert_not_called()

    def test_host_executable_with_literal_arguments_is_accepted(self):
        self.rules("default.rules", 'host_executable(name = "git", paths = ["/usr/bin/git"])\n' + HCOM_DENY_RULES)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertIn("4 rule(s)", out)

    def test_every_rules_file_is_read_and_a_bad_one_fails_the_review_although_another_is_fine(self):
        self.rules("a-hcom.rules", HCOM_DENY_RULES)
        self.rules("b-bad.rules", "X = 1\n")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("cannot read the rules of b-bad.rules", out)

    def test_read_rules_returns_the_patterns_decisions_and_lines(self):
        self.rules("default.rules", 'host_executable(name = "git", paths = ["/usr/bin/git"])\n'
                                    'prefix_rule(pattern = ["a", ["b", "c"]], match = ["a b"], not_match = [["a", "x"]], justification = "why")\n'
                                    'prefix_rule(pattern = ["z"], decision = "prompt")\n')
        rules = trust.read_rules(self.home / "rules" / "default.rules")
        self.assertEqual([(rule.line, rule.pattern, rule.decision) for rule in rules],
                         [(2, ["a", ["b", "c"]], "allow"), (3, ["z"], "prompt")])

    # the heads fixture and what it is derived for
    def test_the_review_writes_nothing_into_the_home_it_reviews(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])


class HeadsFixtureTests(unittest.TestCase):
    """tools/adoption/rtk_rewrite_heads.json: the command heads rtk can rewrite, derived from rtk's source at the pin
    (evidence/artifacts/token-stack-fresh-session-e2e-20261004/derive_rtk_rewrite_heads.py) and checked against the real binary there."""

    def setUp(self):
        self.fixture, self.compiled = trust.load_heads()

    def test_it_is_derived_for_the_pinned_rtk_so_a_pin_move_must_re_derive_it(self):
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

    def test_known_heads_are_heads_and_hcom_uvx_rtk_and_sudo_are_not(self):
        for word in ("git", "yadm", "gh", "uv", "npx", "bunx", "cat", "ls", "python3", "python3.11", "pytest", "make", "gcc", "gcc-13", "jq", "ssh", "nice",
                     "timeout", "time", "nohup", "env", "command", "FOO=1", "pnpm", "sbt", "docker", "kubectl", "terraform"):
            self.assertIsNotNone(trust.head_of(word, self.compiled), word)
        for word in ("hcom", "uvx", "rtk", "sudo", "xargs", "node", "bash", "gitx", "makepkg", "hcom-x"):
            self.assertIsNone(trust.head_of(word, self.compiled), word)

    def test_a_path_is_reduced_to_its_basename(self):
        for word in ("/usr/bin/git", "./gradlew", "vendor/bin/phpunit", "/opt/x/bin/gcc-13"):
            self.assertIsNotNone(trust.head_of(word, self.compiled), word)
        self.assertIsNone(trust.head_of("/usr/bin/hcom", self.compiled))

    def test_every_command_rtk_rewrote_in_the_retained_probe_starts_with_a_head(self):
        record = json.loads((E2E / "rtk-behaviour-probe.json").read_text(encoding="utf-8"))
        rewritten = [row["command"] for row in record["codex_hook_check"]["upstream_defaults"] if row.get("rewritten_to")]
        self.assertEqual(len(rewritten), 36)
        for command in rewritten:
            self.assertIsNotNone(trust.head_of(command.split()[0], self.compiled), command)

    def test_the_retained_binary_check_agrees_with_this_fixture(self):
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


if __name__ == "__main__":
    unittest.main()
