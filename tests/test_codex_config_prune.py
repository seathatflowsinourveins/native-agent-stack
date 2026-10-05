"""tools/adoption/codex_config_prune.py: a Codex home's [features] keys that `codex features list` reports as removed.

The listing lines are the shape of the released rust-v0.160.0 binary's output (a name, a stage of one or two words, a default).
The app-server is a fake with the user_layer and batch_write the real client has; no real Codex, no real home, no network:
local integration checks, not upstream tests.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import codex_config_prune as prune  # noqa: E402

LISTING = """\
agent_message_board                      under development  false
analytics_plan_history                   experimental       false
daemon_auto_start                        stable             true
hooks                                    stable             true
plugin_hooks                             removed            false
shell_snapshot                           stable             true
old_experiment                           removed            true
"""

CONFIG = """model = "gpt-6.1-sol"

[features]
hooks = true
plugin_hooks = true   # a removed flag
daemon_auto_start = false

[profiles.worker.features]
plugin_hooks = false

[plugins."context-mode@context-mode"]
plugin_hooks = true
"""


def fake_codex(directory: Path, listing: str = LISTING, code: int = 0) -> Path:
    path = directory / "codex"
    path.write_text("#!" + sys.executable + "\nimport json, os, sys\n"
                    f"seen = {str(directory / 'seen.json')!r}\n"
                    "if sys.argv[1:] == ['features', 'list']:\n"
                    "    json.dump({'HOME': os.environ.get('HOME'), 'CODEX_HOME': os.environ.get('CODEX_HOME'),\n"
                    "               'cwd': os.getcwd()}, open(seen, 'w'))\n"
                    f"    sys.stdout.write({listing!r}); sys.exit({code})\n"
                    "sys.exit(9)\n", encoding="utf-8")
    path.chmod(0o700)
    return path


class FakeServer:
    """The two calls of apply_codex_lane.AppServer that the tool uses, over one in-memory config."""

    def __init__(self, config: dict):
        self.config, self.version, self.writes = config, "v1", []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def user_layer(self):
        return self.version, self.config

    def batch_write(self, edits, expected_version):
        self.writes.append((edits, expected_version))
        for edit in edits:
            node = self.config
            for part in edit["key"][:-1]:
                node = node[part]
            if edit["value"] is None:
                node.pop(edit["key"][-1], None)
        self.version = "v2"
        return {"status": "ok"}


class Case(unittest.TestCase):
    def setUp(self):
        self._scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self._scratch.cleanup)
        self.dir = Path(self._scratch.name)
        self.home = self.dir / "home"
        self.home.mkdir()
        self.config = self.home / "config.toml"
        self.config.write_text(CONFIG, encoding="utf-8")
        self.codex = fake_codex(self.dir)

    def run_tool(self, *extra: str):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = prune.main(["--codex", str(self.codex), "--codex-home", str(self.home), *extra])
        return code, out.getvalue(), err.getvalue()


class ParsingTests(unittest.TestCase):
    def test_removed_names_are_the_ones_whose_stage_is_removed(self):
        self.assertEqual(prune.parse_removed(LISTING), ["plugin_hooks", "old_experiment"])
        self.assertEqual(prune.parse_removed(""), [])
        # a two-word stage, a missing default and a name that contains the word are not removed features
        self.assertEqual(prune.parse_removed("under_development_feature under development false\nremoved_x stable true\n"
                                             "broken removed\n"), [])

    def test_only_the_base_features_table_is_read(self):
        import tomllib
        live = tomllib.loads(CONFIG)
        self.assertEqual(prune.stale_keys(live, ["plugin_hooks", "old_experiment"]), ["plugin_hooks"])
        self.assertEqual(prune.stale_keys({}, ["plugin_hooks"]), [])
        self.assertEqual(prune.stale_keys({"features": "text"}, ["plugin_hooks"]), [])


class RemovedFeaturesTests(Case):
    def test_codex_is_asked_in_an_empty_home_and_a_failure_is_an_error(self):
        self.assertEqual(prune.removed_features(str(self.codex)), ["plugin_hooks", "old_experiment"])
        seen = json.loads((self.dir / "seen.json").read_text())
        self.assertEqual(seen["HOME"], seen["CODEX_HOME"])
        self.assertNotEqual(seen["HOME"], str(self.home))
        self.assertNotEqual(seen["HOME"], str(Path.home()))
        bad = fake_codex(self.dir, code=3)
        with self.assertRaises(prune.lane.Failed):
            prune.removed_features(str(bad))


class DryRunTests(Case):
    def test_a_dry_run_names_the_key_and_writes_nothing(self):
        before = self.config.read_bytes()
        with mock.patch.object(prune.lane, "AppServer", side_effect=AssertionError("a dry run starts no app-server")):
            code, out, err = self.run_tool()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("plugin_hooks = True", out)
        self.assertIn("stage `removed`", out)
        self.assertIn("dry run: 1 key(s) would be deleted", out)
        self.assertNotIn("old_experiment", out)       # removed upstream, but this config does not have it
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual([p.name for p in self.home.iterdir()], ["config.toml"])

    def test_nothing_stale_is_a_quiet_success(self):
        self.config.write_text("[features]\nhooks = true\n", encoding="utf-8")
        code, out, _ = self.run_tool("--apply")
        self.assertEqual(code, 0)
        self.assertIn("nothing to prune", out)

    def test_a_missing_or_unreadable_config_is_handled(self):
        self.config.unlink()
        self.assertEqual(self.run_tool()[0], 0)
        self.config.write_text("not = [valid toml", encoding="utf-8")
        code, _, err = self.run_tool()
        self.assertEqual(code, 2)
        self.assertIn("does not parse", err)

    def test_no_codex_is_refused(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(prune.shutil, "which", return_value=None), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            self.assertEqual(prune.main(["--codex-home", str(self.home)]), 2)
        self.assertIn("no codex executable", err.getvalue())


class ApplyTests(Case):
    def server(self):
        import tomllib
        return FakeServer(tomllib.loads(CONFIG))

    def test_apply_backs_up_then_deletes_through_the_writer_and_reads_back(self):
        server = self.server()
        with mock.patch.object(prune.lane, "AppServer", return_value=server), \
                mock.patch.object(prune.lane, "codex_processes", return_value=[]):
            code, out, err = self.run_tool("--apply")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(server.writes, [([{"key": ["features", "plugin_hooks"], "value": None}], "v1")])
        self.assertNotIn("plugin_hooks", server.config["features"])
        self.assertIn("pruned plugin_hooks", out)
        backups = [p for p in self.home.iterdir() if ".bak." in p.name]
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), CONFIG)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        # the profile's table and the plugin's table are not the base features table: untouched
        self.assertIn("plugin_hooks", server.config["profiles"]["worker"]["features"])
        self.assertIn("plugin_hooks", server.config["plugins"]["context-mode@context-mode"])

    def test_a_running_codex_refuses_before_any_write(self):
        with mock.patch.object(prune.lane, "AppServer", side_effect=AssertionError("must not start")), \
                mock.patch.object(prune.lane, "codex_processes", return_value=["4242"]):
            code, _, err = self.run_tool("--apply")
        self.assertEqual(code, 2)
        self.assertIn("pids 4242", err)
        self.assertEqual([p.name for p in self.home.iterdir()], ["config.toml"])

    def test_a_failed_write_is_reported_with_the_backup(self):
        server = self.server()
        server.batch_write = mock.Mock(side_effect=prune.lane.Failed("config changed under us"))
        with mock.patch.object(prune.lane, "AppServer", return_value=server), \
                mock.patch.object(prune.lane, "codex_processes", return_value=[]):
            code, _, err = self.run_tool("--apply")
        self.assertEqual(code, 3)
        self.assertIn("config changed under us", err)
        self.assertEqual(len([p for p in self.home.iterdir() if ".bak." in p.name]), 1)

    def test_a_key_the_writer_still_reports_is_a_failure(self):
        server = self.server()
        server.batch_write = lambda edits, version: {"status": "ok"}   # accepts, deletes nothing
        with mock.patch.object(prune.lane, "AppServer", return_value=server), \
                mock.patch.object(prune.lane, "codex_processes", return_value=[]):
            code, _, err = self.run_tool("--apply")
        self.assertEqual(code, 3)
        self.assertIn("still reports plugin_hooks", err)

    def test_two_backups_in_one_second_do_not_overwrite_each_other(self):
        with mock.patch.object(prune.lane, "utc_stamp", return_value="20261004T000000Z"):
            first, second = prune.write_backup(self.config), prune.write_backup(self.config)
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file() and second.is_file())


if __name__ == "__main__":
    unittest.main()
