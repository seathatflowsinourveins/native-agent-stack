"""Credential status checker: lstat-only, names-only, never prints or opens values.

Local integration class: temporary fixture files carry fake sentinel values
generated at test time; no real credential store is read.
"""

import builtins
import copy
import json
import os
from pathlib import Path
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
        # Fake sentinels generated per test; the checker must never echo them.
        self.fake_a = "SENTINELA" + os.urandom(12).hex()
        self.fake_b = "SENTINELB" + os.urandom(12).hex()
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config)}

    def write_alpaca(self, mode=0o600):
        path = self.store / "alpaca-paper.env"
        path.unlink(missing_ok=True)
        path.write_text(f"export APCA_API_KEY_ID={self.fake_a}\nexport APCA_API_SECRET_KEY={self.fake_b}\n")
        path.chmod(mode)
        return path

    def report(self, env=None, **kwargs):
        return cs.inspect(ROOT, self.inventory, self.env if env is None else env, **kwargs)

    def entry(self, report, identifier="alpaca-paper"):
        return next(e for e in report["entries"] if e["id"] == identifier)

    def assert_no_values(self, *texts):
        for text in texts:
            self.assertNotIn(self.fake_a, text)
            self.assertNotIn(self.fake_b, text)
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

    def test_unsafe_optional_file_also_fails_but_missing_optional_does_not(self):
        path = self.store / "typesafe.env"
        path.write_text(f"export TYPESAFE_API_KEY={self.fake_a}\n")
        path.chmod(0o644)
        report = self.report()
        self.assertEqual(self.entry(report, "typesafe")["state"], "unsafe")
        self.assertEqual(report["unsafe_stored"], ["typesafe"])
        self.assertEqual(report["unsafe_required"], [])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        path.unlink()
        self.assertEqual(self.entry(self.report(), "typesafe")["state"], "missing")
        self.assertEqual(self.run_cli().returncode, 0)

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
        target.write_text(f"export APCA_API_KEY_ID={self.fake_a}\n")
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
        env = {**self.env, "APCA_API_KEY_ID": self.fake_a, "GH_TOKEN": self.fake_b}
        report = self.report(env)
        self.assertEqual(self.entry(report)["variables_in_environment"], ["APCA_API_KEY_ID"])
        self.assertEqual(report["environment"]["must_not_be_set_present"], ["GH_TOKEN"])
        self.assert_no_values(json.dumps(report), cs.render_text(report))
        cli_env = {"APCA_API_KEY_ID": self.fake_a, "GH_TOKEN": self.fake_b}
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
        (claude / "hooks").mkdir(parents=True)
        (claude / "hooks" / "secret_path_guard.py").write_text("# stand-in\n")
        (claude / "settings.json").write_text(json.dumps({
            "permissions": {"deny": ["Read(~/.config/native-agent-stack/**)"]},
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python3 /h/.claude/hooks/secret_path_guard.py"}]}]},
            "env": {"SOME_PROVIDER_VALUE": self.fake_b, "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
                    "OTEL_LOG_TOOL_CONTENT": "1", "OTEL_LOG_RAW_API_BODIES": f"file:/tmp/{self.fake_b}",
                    "OTEL_LOG_USER_PROMPTS": "false"}}))
        codex = self.home / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_text('[shell_environment_policy]\ninherit = "none"\n')
        report = self.report(with_client_guards=True)
        self.assertEqual(report["client_guards"], {
            "claude_user_deny_rules": True,
            "claude_user_secret_guard_hook": True,
            "claude_sandbox_enabled": False,
            "claude_telemetry_logs_content": True,
            "claude_telemetry_content_flags": {
                "OTEL_LOG_TOOL_CONTENT": True, "OTEL_LOG_TOOL_DETAILS": False,
                "OTEL_LOG_USER_PROMPTS": False, "OTEL_LOG_ASSISTANT_RESPONSES": False,
                "OTEL_LOG_RAW_API_BODIES": True},
            "codex_shell_environment_inherit_none": True})
        self.assert_no_values(json.dumps(report))
        self.assert_no_values(cs.render_text(report))
        self.assertIn("claude telemetry logs content: true", cs.render_text(report))

    def write_client_settings(self):
        claude = self.home / ".claude"
        (claude / "hooks").mkdir(parents=True)
        (claude / "hooks" / "secret_path_guard.py").write_text("# stand-in\n")
        (claude / "settings.json").write_text(json.dumps({
            "permissions": {"deny": ["Read(~/.config/native-agent-stack/**)"]},
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python3 /h/.claude/hooks/secret_path_guard.py"}]}]},
            "env": {"SOME_PROVIDER_VALUE": self.fake_a, "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
                    "OTEL_LOG_TOOL_CONTENT": "1", "OTEL_LOG_RAW_API_BODIES": f"file:/tmp/{self.fake_b}"}}))
        codex = self.home / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_text(f'[shell_environment_policy]\ninherit = "none"\n# {self.fake_b}\n')

    def test_cli_output_never_contains_values_in_any_mode(self):
        self.write_alpaca()
        self.write_client_settings()
        exported = {"APCA_API_KEY_ID": self.fake_a, "GH_TOKEN": self.fake_b}
        for args in ((), ("--json",), ("--client-guards",), ("--json", "--client-guards")):
            with self.subTest(args=args), patch.dict(self.env, exported):
                result = self.run_cli(*args)  # run_cli asserts both fake values are absent
                # The store is safe (0600 in 0700), so the verdict is 0; the exported
                # must-not-be-set name is reported by name, never by value.
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("APCA_API_KEY_ID", result.stdout)
                if "--json" not in args:
                    self.assertIn("result: ", result.stdout)
                    if "--client-guards" in args:
                        self.assertIn("client guards: ", result.stdout)
                if "--json" in args:
                    report = json.loads(result.stdout)
                    if "--client-guards" in args:
                        self.assertTrue(cs.only_booleans(report["client_guards"]))
                        self.assertTrue(report["client_guards"]["claude_telemetry_logs_content"])

    def test_wrong_type_settings_fields_do_not_crash(self):
        claude = self.home / ".claude"
        claude.mkdir(exist_ok=True)
        (claude / "settings.json").write_text(json.dumps({"permissions": {"deny": 3}, "hooks": {"PreToolUse": 7}}))
        self.assertIsNone(cs.claude_guard_booleans(claude))

    def test_settings_env_is_reduced_to_key_names(self):
        present, enabled = cs.enabled_names({"SOME_PROVIDER_VALUE": self.fake_a, "OFF": "0", 3: "x"})
        self.assertEqual(present, {"SOME_PROVIDER_VALUE", "OFF"})
        self.assertEqual(enabled, {"SOME_PROVIDER_VALUE"})
        self.assertEqual(cs.enabled_names("not a dict"), (frozenset(), frozenset()))

    def test_telemetry_flags_need_telemetry_enabled_and_follow_documented_fallback(self):
        off = cs.telemetry_content_logging({"OTEL_LOG_TOOL_CONTENT": "1"})
        self.assertFalse(off["logs_content"])
        self.assertTrue(off["flags"]["OTEL_LOG_TOOL_CONTENT"])
        fallback = cs.telemetry_content_logging({"CLAUDE_CODE_ENABLE_TELEMETRY": "1",
                                                 "OTEL_LOG_USER_PROMPTS": "1"})
        self.assertTrue(fallback["flags"]["OTEL_LOG_ASSISTANT_RESPONSES"])
        self.assertTrue(fallback["logs_content"])
        redacted = cs.telemetry_content_logging({"CLAUDE_CODE_ENABLE_TELEMETRY": "1", "OTEL_LOG_TOOL_CONTENT": "0",
                                                 "OTEL_LOG_RAW_API_BODIES": "false", "OTEL_LOG_TOOL_DETAILS": ""})
        self.assertFalse(redacted["logs_content"])
        self.assertEqual(cs.telemetry_content_logging(None)["flags"]["OTEL_LOG_USER_PROMPTS"], False)

    def test_codex_counts_only_inherit_none_as_guarded(self):
        codex = self.home / ".codex"
        codex.mkdir()
        for body, expected in (('inherit = "none"\n', True), ('inherit = "core"\n', False),
                               ('inherit = "all"\nignore_default_excludes = false\nexclude = ["*KEY*"]\n', False),
                               ('', False)):
            with self.subTest(body=body):
                (codex / "config.toml").write_text("[shell_environment_policy]\n" + body)
                guards = self.report(with_client_guards=True)["client_guards"]
                self.assertIs(guards["codex_shell_environment_inherit_none"], expected)

    def test_guard_hook_needs_registration_and_installed_file(self):
        claude = self.home / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "python3 /h/.claude/hooks/secret_path_guard.py"}]}]}}))
        guards = self.report(with_client_guards=True)["client_guards"]
        self.assertFalse(guards["claude_user_secret_guard_hook"])
        self.assertIsNone(guards["codex_shell_environment_inherit_none"])

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
