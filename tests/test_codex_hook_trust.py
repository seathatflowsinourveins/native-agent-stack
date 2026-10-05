"""tools/adoption/codex_hook_trust.py: trust the named hooks of one Codex home through config/batchWrite and read it back.

The app-server is a fake that answers hooks/list and config/batchWrite the way the released codex-cli 0.159.3 does (the field
names are those of its hooks/list response; the write shape is the TUI's write_hook_trusts); no real Codex, no real home, no
network: local integration checks, not upstream tests. The real client was run against scratch homes in
evidence/artifacts/token-stack-fresh-session-e2e-20261004/.
"""

from __future__ import annotations

import contextlib
import copy
import io
import os
import stat
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

    def run_tool(self, server, *extra: str, running=()):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(trust.lane, "AppServer", return_value=server), \
                mock.patch.object(trust.lane, "codex_processes", return_value=list(running)):
            code = trust.main(["--codex", str(self.codex), "--codex-home", str(self.home), "--command", RTK, *extra])
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


class ExecutionRuleTests(Case):
    """The hook rewrites a command to `rtk <command>` before Codex matches execution rules (codex-rs/core/src/tools/registry.rs L603-L660 at rust-v0.160.0;
    codex-rs/core/src/exec_policy.rs L316-L420 matches the rules against the rewritten command's words), so a rule on `git push` does not match
    `rtk git push`. Trusting the hook is what activates it, so --apply refuses while the user layer's rules directory holds a rules file."""

    def rules(self, name="default.rules", body='prefix_rule(pattern = ["git", "push"], decision = "forbidden")\n'):
        directory = self.home / "rules"
        directory.mkdir(exist_ok=True)
        (directory / name).write_text(body, encoding="utf-8")

    def test_a_rules_file_refuses_the_apply_before_any_write_or_backup(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 2)
        self.assertIn("default.rules", err)
        self.assertIn("rtk git push", err)
        self.assertIn("--allow-exec-rules", err)
        self.assertEqual(server.writes(), [])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])  # no backup

    def test_the_flag_lets_the_apply_through(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply", "--allow-exec-rules")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(server.writes()), 1)
        self.assertIn("trusted 1 hook(s)", out)

    def test_a_dry_run_and_a_check_name_the_rules_and_are_not_refused(self):
        self.rules()
        for extra in ((), ("--check",)):
            with self.subTest(extra=extra):
                server = FakeServer([hook(KEY, RTK)])
                code, out, err = self.run_tool(server, *extra)
                self.assertEqual(code, 0 if not extra else 5, err)
                self.assertIn("default.rules", out + err)
                self.assertEqual(server.writes(), [])

    def test_no_rules_directory_an_empty_one_and_other_files_do_not_refuse(self):
        (self.home / "rules").mkdir()
        (self.home / "rules" / "notes.txt").write_text("not a rules file\n", encoding="utf-8")
        (self.home / "rules" / "empty.rules").write_text("  \n", encoding="utf-8")
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)

    def test_every_rules_file_is_named(self):
        self.rules("default.rules")
        self.rules("team.rules", 'prefix_rule(pattern = ["git", "commit"], decision = "prompt")\n')
        code, _, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("default.rules", err)
        self.assertIn("team.rules", err)

    def test_an_already_trusted_hook_is_nothing_to_do_even_with_rules(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK, "trusted")])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)


if __name__ == "__main__":
    unittest.main()
