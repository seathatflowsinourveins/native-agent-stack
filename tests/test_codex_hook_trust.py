"""tools/adoption/codex_hook_trust.py: trust the named hooks of one Codex home through config/batchWrite and read it back.

The app-server is a fake that answers hooks/list and config/batchWrite the way the released codex-cli 0.159.3 does (the field
names are those of its hooks/list response; the write shape is the TUI's write_hook_trusts); the rule review's two programs are
local stand-ins too (FakeTools: `rtk hook check --agent codex` and `codex execpolicy check`, with the output shapes of rtk 0.51.0 and
codex-rs/execpolicy); no real Codex, no real rtk, no real home, no network: synthetic local checks, not upstream tests. The real
client and the real tools were run against scratch homes in evidence/artifacts/token-stack-fresh-session-e2e-20261004/.
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


class FakeTools:
    """The two programs the rule review runs. `rtk hook check --agent codex <command>` rewrites the commands whose first word is in
    ``rewrites`` to `rtk <command>` (stdout, exit 0) and says `No rewrite for: <command>` on stderr with exit 1 for the others, as rtk
    0.51.0 does. `codex execpolicy check --rules F ... -- <argv>` reads prefix_rule calls from the files, merges them, takes the
    strictest decision (decision defaults to allow) and answers with the JSON shape of codex-rs/execpolicy/README.md."""

    ORDER = {"forbidden": 3, "prompt": 2, "allow": 1}

    def __init__(self, rewrites=("git",), rtk_exit=None, codex_exit=None, rewrite_to=None):
        self.rewrites, self.rtk_exit, self.codex_exit, self.rewrite_to = set(rewrites), rtk_exit, codex_exit, rewrite_to
        self.calls, self.settings = [], []

    def run(self, command, **kwargs):
        self.calls.append(list(command))
        self.settings.append(kwargs.get("env"))
        return self.rtk(command) if Path(command[0]).name == "rtk" else self.codex(command)

    def rtk(self, command):
        assert command[1:5] == ["hook", "check", "--agent", "codex"], command
        asked = command[5]
        if self.rtk_exit is not None:
            return completed(command, self.rtk_exit, "", "rtk: boom\n")
        if asked.split()[0] in self.rewrites:
            return completed(command, 0, (self.rewrite_to(asked) if self.rewrite_to else "rtk " + asked) + "\n")
        return completed(command, 1, "", f"No rewrite for: {asked}\n")

    def codex(self, command):
        assert command[1:3] == ["execpolicy", "check"], command
        if self.codex_exit is not None:
            return completed(command, self.codex_exit, "", "Error: failed to parse policy at x.rules\n\nCaused by:\n    error: invalid decision: oops\n")
        files = [command[i + 1] for i, token in enumerate(command) if token == "--rules"]
        argv = command[command.index("--") + 1:]
        matched = []
        for path in files:
            for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
                if node.value.func.id != "prefix_rule":
                    continue
                keywords = {k.arg: ast.literal_eval(k.value) for k in node.value.keywords}
                pattern = keywords["pattern"]
                if len(argv) >= len(pattern) and all(argv[i] in (p if isinstance(p, list) else [p]) for i, p in enumerate(pattern)):
                    matched.append((argv[:len(pattern)], keywords.get("decision", "allow")))
        if not matched:
            return completed(command, 0, json.dumps({"matchedRules": []}))
        rules = [{"prefixRuleMatch": {"matchedPrefix": prefix, "decision": decision}} for prefix, decision in matched]
        strictest = max((decision for _, decision in matched), key=self.ORDER.get)
        return completed(command, 0, json.dumps({"matchedRules": rules, "decision": strictest}))


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
        self.tools = tools or FakeTools()
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
HCOM_DENY_RULES = (ROOT / "evidence" / "artifacts" / "token-stack-fresh-session-e2e-20261004" / "fixtures" / "hcom-deny.rules") \
    .read_text(encoding="utf-8")
GIT_PUSH_FORBIDDEN = 'prefix_rule(pattern = ["git", "push"], decision = "forbidden")\n'
GIT_PUSH_TWIN = 'prefix_rule(pattern = ["rtk", "git", "push"], decision = "forbidden")\n'


class ExecutionRuleTests(Case):
    """The hook rewrites a command to `rtk <command>` before Codex matches execution rules (codex-rs/core/src/tools/registry.rs L603-L660 at
    rust-v0.160.0; codex-rs/core/src/exec_policy.rs L316-L420 matches the rules against the rewritten command's words), so a `forbidden` or
    `prompt` rule on `git push` does not match `rtk git push`. Trusting the hook activates it, so the tool reviews the user layer's rules first:
    for each command a rule names, and a sample of the commands rtk rewrites, it compares the decision on the original with the decision on
    the rewrite, and refuses (--apply, before the app-server starts) or fails (--check) only when a restricting decision gets weaker."""

    def rules(self, name="default.rules", body=GIT_PUSH_FORBIDDEN):
        directory = self.home / "rules"
        directory.mkdir(exist_ok=True)
        (directory / name).write_text(body, encoding="utf-8")

    def assert_refused_before_anything_was_written(self, code, server):
        self.assertEqual(code, 2)
        self.app_server.assert_not_called()
        self.assertEqual(server.requests, [])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])  # no backup, nothing created

    # the CC's three controls
    def test_hcom_style_rules_that_rtk_does_not_rewrite_let_the_apply_through(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(server.writes()), 1)
        self.assertIn("hcom-deny.rules; 4 rule(s)", out)
        self.assertIn("every rule keeps its decision under the rewrite", out)

    def test_a_forbid_rule_without_an_rtk_twin_is_refused_before_the_server_starts(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("exposed: `git push origin main` is forbidden (git push), its rewrite `rtk git push origin main` is matched by no rule", out)
        self.assertIn("--allow-exec-rules", err)
        self.assertIn("rtk form", err)

    def test_a_twin_covered_rule_lets_the_apply_through(self):
        self.rules("default.rules", GIT_PUSH_FORBIDDEN + GIT_PUSH_TWIN)
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertIn("every rule keeps its decision under the rewrite", out)

    # what counts as a bypass
    def test_a_broad_rule_is_seen_through_the_sample_though_its_head_is_not_rewritten(self):
        self.rules("default.rules", 'prefix_rule(pattern = ["git"], decision = "prompt")\n')
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)
        self.assertIn("`git commit -m x` is prompt (git), its rewrite `rtk git commit -m x` is matched by no rule", out)

    def test_a_twin_that_is_weaker_than_the_rule_is_still_exposed(self):
        self.rules("default.rules", GIT_PUSH_FORBIDDEN + 'prefix_rule(pattern = ["rtk", "git", "push"], decision = "prompt")\n')
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("its rewrite `rtk git push origin main` is prompt", out)

    def test_a_stricter_twin_is_not_an_exposure(self):
        self.rules("default.rules", 'prefix_rule(pattern = ["git", "push"], decision = "prompt")\n' + GIT_PUSH_TWIN)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)

    def test_an_allow_rule_whose_rewrite_matches_nothing_is_a_note_not_a_refusal(self):
        self.rules("default.rules", 'prefix_rule(pattern = ["git", "status"], decision = "allow")\n')
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 0, err)
        self.assertIn("note: `git status` is allow (git status), its rewrite `rtk git status` is matched by no rule", out)
        self.assertEqual(len(server.writes()), 1)

    def test_match_examples_and_every_spelling_of_a_pattern_are_probed(self):
        self.rules("default.rules", 'prefix_rule(pattern = ["git", ["push", "pull"]], decision = "forbidden", '
                                    'match = ["git push --tags", ["git", "pull", "--rebase"]])\n')
        _, out, _ = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        for command in ("git push --tags", "git pull --rebase", "git push", "git pull"):
            self.assertIn(f"exposed: `{command}` is forbidden", out)

    def test_every_rules_file_is_evaluated_together_so_a_twin_in_another_file_counts(self):
        self.rules("default.rules")
        self.rules("team.rules", GIT_PUSH_TWIN)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertIn("default.rules, team.rules", out)
        evaluations = [call for call in self.tools.calls if call[1:3] == ["execpolicy", "check"]]
        self.assertTrue(evaluations)
        for call in evaluations:
            self.assertEqual(call.count("--rules"), 2)

    # the flag and the other modes
    def test_the_flag_accepts_an_exposure_and_the_report_still_names_it(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK)])
        code, out, err = self.run_tool(server, "--apply", "--allow-exec-rules")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(server.writes()), 1)
        self.assertIn("exposed: `git push origin main`", out)

    def test_a_check_is_5_for_an_untrusted_hook_and_6_for_a_trusted_one_beside_an_exposure(self):
        self.rules()
        self.assertEqual(self.run_tool(FakeServer([hook(KEY, RTK)]), "--check")[0], 5)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 6)
        self.assertIn("exposed: `git push origin main`", out)
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
        self.assertIn("exposed: `git push origin main`", out)
        self.assertIn("--apply would refuse", out)
        self.assertEqual(server.writes(), [])

    def test_an_already_trusted_hook_is_still_refused_by_apply_because_the_review_comes_first(self):
        self.rules()
        server = FakeServer([hook(KEY, RTK, "trusted")])
        code, out, err = self.run_tool(server, "--apply")
        self.assert_refused_before_anything_was_written(code, server)

    # no rule files: nothing is run
    def test_without_a_rules_directory_neither_rtk_nor_the_evaluator_runs(self):
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tools.calls, [])
        self.assertNotIn("execution rules", out)

    def test_other_files_empty_comment_only_files_and_non_files_are_no_rules_to_review(self):
        directory = self.home / "rules"
        directory.mkdir()
        (directory / "notes.txt").write_text(GIT_PUSH_FORBIDDEN, encoding="utf-8")
        (directory / "empty.rules").write_text("  \n", encoding="utf-8")
        (directory / "comments.rules").write_text("# nothing here\n", encoding="utf-8")
        (directory / "dir.rules").mkdir()
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tools.calls, [])  # no rule: nothing to compare

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
        self.assertEqual(self.tools.calls, [])

    # fail closed (review of #705, finding P1: a failed listing used to read as no rules)
    def test_a_listing_error_is_not_no_rules_it_refuses_before_any_write(self):
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

    def test_an_error_on_one_entry_is_a_listing_error_too(self):
        class Entry:
            name = "x.rules"

            def is_file(self, follow_symlinks=True):
                raise PermissionError(13, "Permission denied")

        class Listing:
            def __enter__(self):
                return iter([Entry()])

            def __exit__(self, *exc):
                return False

        server = FakeServer([hook(KEY, RTK)])
        with mock.patch.object(trust.os, "scandir", return_value=Listing()):
            code, out, err = self.run_tool(server, "--apply")
        self.assertEqual(code, 2)
        self.assertIn("cannot list", out)
        self.assertEqual(server.requests, [])

    def test_a_rules_path_that_is_a_file_is_a_listing_error_but_a_missing_one_is_not(self):
        (self.home / "rules").write_text("not a directory\n", encoding="utf-8")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("cannot list", out)

    def test_rules_the_tool_cannot_read_as_literals_fail_closed(self):
        for name, body in (("assign", "NAMES = [\"git\"]\nprefix_rule(pattern = NAMES)\n"), ("syntax", "prefix_rule(pattern = [\n"),
                           ("other", 'network_rule(host = "x")\n'), ("positional", 'prefix_rule(["git"])\n'),
                           ("empty pattern", "prefix_rule(pattern = [])\n"), ("no pattern", 'prefix_rule(decision = "allow")\n')):
            with self.subTest(name=name):
                self.rules("default.rules", body)
                server = FakeServer([hook(KEY, RTK)])
                code, out, err = self.run_tool(server, "--apply")
                self.assertEqual(code, 2)
                self.assertIn("cannot read the rules of default.rules", out)
                self.app_server.assert_not_called()

    def test_a_pattern_with_too_many_spellings_fails_closed(self):
        alternatives = ", ".join(f'"a{i}"' for i in range(30))
        self.rules("default.rules", f"prefix_rule(pattern = [[{alternatives}], [{alternatives}]])\n")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply")
        self.assertEqual(code, 2)
        self.assertIn("spells 900 commands", out)

    def test_rules_without_an_rtk_executable_fail_closed(self):
        self.rules()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(trust.lane, "AppServer") as app_server, mock.patch.object(trust.shutil, "which", return_value=None):
            code = trust.main(["--codex", str(self.codex), "--codex-home", str(self.home), "--command", RTK, "--apply"])
        self.assertEqual(code, 2)
        self.assertIn("no rtk executable", out.getvalue())
        app_server.assert_not_called()

    def test_a_failing_rtk_or_evaluator_fails_closed(self):
        self.rules()
        for name, tools in (("rtk exit", FakeTools(rtk_exit=2)), ("codex exit", FakeTools(codex_exit=1))):
            with self.subTest(name=name):
                code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply", tools=tools)
                self.assertEqual(code, 2)
                self.assertIn("cannot check:", out)
                self.app_server.assert_not_called()
        self.assertIn("invalid decision: oops", out)  # the evaluator's own reason is shown

    def test_a_response_that_is_not_the_evaluators_shape_fails_closed(self):
        self.rules()

        class Odd(FakeTools):
            def codex(self, command):
                return completed(command, 0, json.dumps({"matchedRules": [], "decision": "forbidden"}))

        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply", tools=Odd())
        self.assertEqual(code, 2)
        self.assertIn("answered unexpectedly", out)

    def test_a_compound_rewrite_is_not_compared_and_fails_closed(self):
        self.rules()
        tools = FakeTools(rewrite_to=lambda asked: f"rtk {asked} && rtk git status")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply", tools=tools)
        self.assertEqual(code, 2)
        self.assertIn("compound command", out)

    def test_a_rewrite_that_does_not_split_into_words_fails_closed(self):
        self.rules()
        tools = FakeTools(rewrite_to=lambda asked: f"rtk {asked} 'unbalanced")
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply", tools=tools)
        self.assertEqual(code, 2)
        self.assertIn("does not split into words", out)

    def test_output_that_is_not_text_fails_closed_instead_of_raising(self):
        self.rules()

        class Binary(FakeTools):
            def rtk(self, command):
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK)]), "--apply", tools=Binary())
        self.assertEqual(code, 2)
        self.assertIn("cannot run /opt/rtk/bin/rtk", out)

    # the review leaves the home alone, and the sample is the measured one
    def test_the_evaluator_runs_in_a_throwaway_codex_home_not_the_reviewed_one(self):
        self.rules("hcom-deny.rules", HCOM_DENY_RULES)
        code, out, err = self.run_tool(FakeServer([hook(KEY, RTK, "trusted")]), "--check")
        self.assertEqual(code, 0, err)
        homes = {env["CODEX_HOME"] for call, env in zip(self.tools.calls, self.tools.settings) if call[1:3] == ["execpolicy", "check"]}
        self.assertTrue(homes)
        self.assertNotIn(str(self.home), homes)
        for path in homes:
            self.assertFalse(Path(path).exists())
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["config.toml", "rules"])

    def test_the_rewrite_sample_is_the_set_rtk_0_51_0_rewrote_in_the_retained_probe(self):
        record = json.loads((ROOT / "evidence" / "artifacts" / "token-stack-fresh-session-e2e-20261004" / "rtk-behaviour-probe.json")
                            .read_text(encoding="utf-8"))
        rewritten = [row["command"] for row in record["codex_hook_check"]["upstream_defaults"] if row.get("rewritten_to")]
        self.assertEqual(len(rewritten), 36)
        self.assertEqual(sorted(trust.REWRITE_SAMPLE), sorted(rewritten))

    def test_read_rules_spells_patterns_and_reads_both_example_shapes(self):
        self.rules("default.rules", 'host_executable(name = "git", paths = ["/usr/bin/git"])\n'
                                    'prefix_rule(pattern = ["a", ["b", "c"], "d"], match = ["a b d x", ["a", "c", "d"]])\n'
                                    'prefix_rule(pattern = ["z"], decision = "prompt", justification = "why", not_match = ["z y"])\n')
        count, heads, examples = trust.read_rules(self.home / "rules" / "default.rules")
        self.assertEqual(count, 2)
        self.assertEqual(heads, [("a", "b", "d"), ("a", "c", "d"), ("z",)])
        self.assertEqual(examples, [("a", "b", "d", "x"), ("a", "c", "d")])


if __name__ == "__main__":
    unittest.main()
