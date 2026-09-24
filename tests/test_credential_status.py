"""Credential status checker: lstat-only, names-only, never prints or opens values.

Local integration class: temporary fixture files carry fake sentinel values
generated at test time; no real credential store is read.
"""

import builtins
import copy
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import credential_status as cs

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/credential_status.py"


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                   cwd=cwd, check=True, capture_output=True)


class CredentialStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "home"
        self.config = self.home / ".config"
        self.store = self.config / "native-agent-stack"
        self.store.mkdir(parents=True)
        self.store.chmod(0o700)
        self.inventory = json.loads((ROOT / cs.INVENTORY).read_text())
        self.key = "SENTINELKEY" + secrets.token_hex(12)
        self.secret = "SENTINELSECRET" + secrets.token_hex(12)
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config)}

    def write_alpaca(self, mode=0o600):
        path = self.store / "alpaca-paper.env"
        path.unlink(missing_ok=True)
        path.write_text(f"export APCA_API_KEY_ID={self.key}\nexport APCA_API_SECRET_KEY={self.secret}\n")
        path.chmod(mode)
        return path

    def report(self, env=None, **kwargs):
        return cs.inspect(ROOT, self.inventory, self.env if env is None else env, **kwargs)

    def entry(self, report, identifier="alpaca-paper"):
        return next(e for e in report["entries"] if e["id"] == identifier)

    def assert_no_values(self, *texts):
        for text in texts:
            self.assertNotIn(self.key, text)
            self.assertNotIn(self.secret, text)
            self.assertNotIn(str(self.home), text)

    def run_cli(self, *args):
        env = {"PATH": os.environ.get("PATH", ""), **self.env}
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(ROOT), *args],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assert_no_values(result.stdout, result.stderr)
        return result

    def test_real_inventory_is_valid(self):
        self.assertEqual(cs.inventory_errors(self.inventory, ROOT), [])
        ids = {e["id"] for e in self.inventory["entries"]}
        self.assertTrue({"alpaca-paper", "sec-contact", "claude-native", "codex-native", "gh-native"} <= ids)

    def test_inventory_rejects_non_home_template_and_bad_names(self):
        broken = copy.deepcopy(self.inventory)
        broken["entries"][0]["store"]["path_template"] = "/srv/shared/alpaca.env"
        broken["entries"][1]["variables"] = ["SEC_USER_AGENT=someone"]
        errors = cs.inventory_errors(broken, ROOT)
        self.assertTrue(any("home-anchored" in e for e in errors))
        self.assertTrue(any("uppercase variable names" in e for e in errors))

    def test_missing_required_file_is_informational(self):
        entry = self.entry(self.report())
        self.assertEqual(entry["state"], "missing")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("missing   alpaca-paper", result.stdout)

    def test_private_file_is_ok_and_output_is_value_free(self):
        self.write_alpaca()
        report = self.report()
        entry = self.entry(report)
        self.assertEqual(entry["state"], "ok")
        self.assertEqual(entry["mode"], "0600")
        self.assertEqual(entry["directory_mode"], "0700")
        self.assertFalse(entry["inside_git_worktree"])
        self.assertFalse(report["values_read"])
        self.assert_no_values(json.dumps(report), cs.render_text(report))
        result = self.run_cli("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"], "ok")

    def test_group_readable_required_file_fails_closed(self):
        for mode in (0o644, 0o640, 0o400):
            with self.subTest(mode=oct(mode)):
                self.write_alpaca(mode)
                entry = self.entry(self.report())
                self.assertEqual(entry["state"], "unsafe")
                self.assertIn("mode_not_0600", entry["findings"])
        self.write_alpaca(0o644)
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("mode_not_0600", result.stdout)

    def test_open_store_directory_is_unsafe(self):
        self.write_alpaca()
        self.store.chmod(0o755)
        self.assertIn("directory_group_or_other_access", self.entry(self.report())["findings"])

    def test_foreign_owner_is_unsafe(self):
        self.write_alpaca()
        entry = self.entry(self.report(uid=os.getuid() + 1))
        self.assertIn("foreign_owner", entry["findings"])

    def test_symlink_is_refused_not_followed(self):
        target = self.home / "elsewhere.env"
        target.write_text(f"export APCA_API_KEY_ID={self.key}\n")
        target.chmod(0o600)
        (self.store / "alpaca-paper.env").symlink_to(target)
        entry = self.entry(self.report())
        self.assertEqual(entry["state"], "unsafe")
        self.assertIn("symlink_refused", entry["findings"])

    def test_store_inside_git_worktree_and_tracked_is_unsafe(self):
        git(self.home, "init", "-q")
        path = self.write_alpaca()
        entry = self.entry(self.report())
        self.assertIn("inside_git_worktree", entry["findings"])
        self.assertNotIn("tracked_by_git", entry["findings"])
        git(self.home, "add", "-f", str(path))
        entry = self.entry(self.report())
        self.assertIn("tracked_by_git", entry["findings"])

    def test_linked_worktree_git_file_counts_as_worktree(self):
        (self.config / ".git").write_text("gitdir: /nonexistent/worktrees/x\n")
        self.write_alpaca()
        self.assertIn("inside_git_worktree", self.entry(self.report())["findings"])

    def test_old_file_is_a_warning_not_a_failure(self):
        path = self.write_alpaca()
        old = time.time() - 120 * 86400
        os.utime(path, (old, old))
        entry = self.entry(self.report())
        self.assertEqual(entry["state"], "ok")
        self.assertIn("older_than_90_days", entry["warnings"])

    def test_exported_names_reported_without_values(self):
        env = {**self.env, "APCA_API_KEY_ID": self.key, "GH_TOKEN": self.secret}
        report = self.report(env)
        self.assertEqual(self.entry(report)["variables_in_environment"], ["APCA_API_KEY_ID"])
        self.assertEqual(report["environment"]["must_not_be_set_present"], ["GH_TOKEN"])
        self.assert_no_values(json.dumps(report), cs.render_text(report))
        cli_env = {"APCA_API_KEY_ID": self.key, "GH_TOKEN": self.secret}
        with patch.dict(self.env, cli_env):
            result = self.run_cli("--json")
        self.assertIn("GH_TOKEN", result.stdout)

    def test_never_opens_or_reads_credential_files(self):
        self.write_alpaca()
        opened = []
        real_open, real_os_open = builtins.open, os.open

        def watch_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_open(file, *args, **kwargs)

        def watch_os_open(file, *args, **kwargs):
            opened.append(str(file))
            return real_os_open(file, *args, **kwargs)

        with patch("builtins.open", watch_open), patch("os.open", watch_os_open), \
                patch.object(Path, "read_text", side_effect=AssertionError("read_text called")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes called")):
            self.report()
        self.assertFalse([p for p in opened if str(self.store) in p])

    def test_client_guards_reports_booleans_only(self):
        claude = self.home / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text(json.dumps({
            "permissions": {"deny": ["Read(~/.config/native-agent-stack/**)"]},
            "env": {"SOME_TOKEN": self.secret}}))
        codex = self.home / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_text('[shell_environment_policy]\ninherit = "none"\n')
        report = self.report(with_client_guards=True)
        self.assertEqual(report["client_guards"], {"claude_user_deny_rules": True,
                                                   "claude_sandbox_enabled": False,
                                                   "codex_shell_environment_policy": True})
        self.assert_no_values(json.dumps(report))

    def test_tracked_sensitive_names_match_basenames_only(self):
        repo = self.home / "repo"
        (repo / "evidence/secrets-credentials").mkdir(parents=True)
        (repo / "docs").mkdir()
        for name in ("leak.env", "evidence/secrets-credentials/receipt.json",
                     "docs/alpaca-paper.env.example", "service.key"):
            (repo / name).write_text("placeholder\n")
        git(repo, "init", "-q")
        git(repo, "add", "-f", ".")
        self.assertEqual(cs.tracked_sensitive_names(repo), ["leak.env", "service.key"])

    def test_repository_has_no_tracked_sensitive_names(self):
        self.assertEqual(cs.tracked_sensitive_names(ROOT), [])


if __name__ == "__main__":
    unittest.main()
