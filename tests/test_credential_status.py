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
        self.assertTrue({"alpaca-paper", "sec-contact", "claude-native", "codex-native", "gh-native",
                         "huggingface-native", "huggingface-native-stored"} <= ids)
        self.assertIn("HUGGING_FACE_HUB_TOKEN", self.inventory["must_not_be_set"])
        self.assertIn("HF_TOKEN", self.inventory["must_not_be_set"])

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
        (repo / "cache/huggingface").mkdir(parents=True)
        for name in ("leak.env", "evidence/secrets-credentials/receipt.json",
                     "docs/alpaca-paper.env.example", "service.key",
                     "cache/huggingface/stored_tokens", "cache/huggingface/token"):
            (repo / name).write_text("placeholder\n")
        git(repo, "init", "-q")
        git(repo, "add", "-f", ".")
        # stored_tokens is caught like the other credential-shaped basenames; the bare
        # `token` basename is deliberately not in SENSITIVE_BASENAME (too generic to flag
        # repo-wide, matching .gitignore's own choice), so it is not reported.
        self.assertEqual(cs.tracked_sensitive_names(repo),
                         ["cache/huggingface/stored_tokens", "leak.env", "service.key"])

    def test_repository_has_no_tracked_sensitive_names(self):
        self.assertEqual(cs.tracked_sensitive_names(ROOT), [])


class HuggingFaceNativeStoreTests(unittest.TestCase):
    """The two Hugging Face rows: lstat-only checks of hf's own token files in a fake home."""

    IDS = ("huggingface-native", "huggingface-native-stored")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "home"
        self.home.mkdir()
        self.hf_home = self.home / ".cache" / "huggingface"
        self.inventory = json.loads((ROOT / cs.INVENTORY).read_text())
        self.fake = "SENTINELHF" + os.urandom(12).hex()  # never shaped like a real token
        self.env = {"HOME": str(self.home)}

    def sign_in(self, directory=None, mode=0o600, directory_mode=0o700):
        """What `hf auth login` leaves behind: both files 0600, their directory 0700."""
        directory = directory or self.hf_home
        directory.mkdir(parents=True, exist_ok=True)
        for name, text in (("token", self.fake), ("stored_tokens", f"[host]\nhf_token = {self.fake}\n")):
            (directory / name).write_text(text)
            (directory / name).chmod(mode)
        directory.chmod(directory_mode)
        return directory

    def report(self, env=None):
        return cs.inspect(ROOT, self.inventory, self.env if env is None else env)

    def entry(self, report, identifier="huggingface-native"):
        return next(e for e in report["entries"] if e["id"] == identifier)

    def run_cli(self, env=None, *args):
        cli_env = {"PATH": os.environ.get("PATH", ""), **(self.env if env is None else env)}
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(ROOT), *args],
                                env=cli_env, capture_output=True, text=True, timeout=60)
        for text in (result.stdout, result.stderr):
            self.assertNotIn(self.fake, text)
            self.assertNotIn(str(self.home), text)
        return result

    def test_rows_are_native_stores_that_render_as_missing_before_sign_in(self):
        rows = {e["id"]: e for e in self.inventory["entries"] if e["id"] in self.IDS}
        self.assertEqual(set(rows), set(self.IDS))
        for row in rows.values():
            self.assertEqual((row["class"], row["status"], row["store"]["kind"]),
                             ("native_signin", "native", "native_store"))
            self.assertEqual(row["pointer_variables"], ["HF_TOKEN_PATH"])
            self.assertEqual(row["variables"], [])
        report = self.report()
        for identifier in self.IDS:
            self.assertEqual(self.entry(report, identifier)["state"], "missing")
        self.assertEqual(report["result"], "ok")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("missing   huggingface-native          native", result.stdout)
        self.assertIn("missing   huggingface-native-stored   native", result.stdout)
        self.assertIn("${HF_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/huggingface}/token", result.stdout)

    def test_signed_in_store_is_ok_and_read_by_lstat_only(self):
        self.sign_in()
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
            report = self.report()
        self.assertFalse([p for p in opened if str(self.hf_home) in p])
        for identifier in self.IDS:
            entry = self.entry(report, identifier)
            self.assertEqual((entry["state"], entry["mode"], entry["directory_mode"]), ("ok", "0600", "0700"))
            self.assertEqual(entry["findings"], [])
        self.assertNotIn(self.fake, json.dumps(report) + cs.render_text(report))
        self.assertEqual(self.run_cli().returncode, 0)

    def test_group_or_world_readable_token_is_a_finding_and_fails(self):
        self.sign_in()
        (self.hf_home / "token").chmod(0o644)
        report = self.report()
        entry = self.entry(report)
        self.assertEqual(entry["state"], "unsafe")
        self.assertIn("group_or_other_access", entry["findings"])
        self.assertEqual(self.entry(report, "huggingface-native-stored")["state"], "ok")
        self.assertEqual(report["unsafe_stored"], ["huggingface-native"])
        self.assertEqual(report["unsafe_required"], [])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("group_or_other_access", result.stdout)

    def test_template_follows_hf_home_then_xdg_cache_home_like_huggingface_hub(self):
        template = next(e for e in self.inventory["entries"]
                        if e["id"] == "huggingface-native")["store"]["path_template"]
        cache = self.home / "xdg-cache"
        custom = self.home / "hf-home"
        cases = (({}, self.hf_home), ({"XDG_CACHE_HOME": str(cache)}, cache / "huggingface"),
                 ({"XDG_CACHE_HOME": str(cache), "HF_HOME": str(custom)}, custom))
        for extra, directory in cases:
            with self.subTest(extra=extra):
                env = {**self.env, **extra}
                self.assertEqual(cs.expand_template(template, env), directory / "token")
        # Single-level templates expand exactly as before.
        self.assertEqual(cs.expand_template("${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack/x.env", self.env),
                         self.home / ".config" / "native-agent-stack" / "x.env")
        self.sign_in(cache / "huggingface")
        report = self.report({**self.env, "XDG_CACHE_HOME": str(cache)})
        self.assertEqual(self.entry(report)["state"], "ok")
        self.assertEqual(self.entry(self.report())["state"], "missing")

    def test_token_path_override_is_reported_by_name_only(self):
        elsewhere = self.home / "elsewhere"
        self.sign_in(elsewhere)
        env = {**self.env, "HF_TOKEN_PATH": str(elsewhere / "token"),
               # Our own stores are found through pointer variables on purpose; not an override.
               "PAPER_ENV_FILE": str(self.home / "paper.env")}
        report = self.report(env)
        self.assertEqual(report["environment"]["native_store_path_overrides_present"], ["HF_TOKEN_PATH"])
        for identifier in self.IDS:
            entry = self.entry(report, identifier)
            self.assertEqual(entry["state"], "missing")
            self.assertIn("store_path_overridden", entry["warnings"])
        self.assertNotIn("store_path_overridden", self.entry(report, "alpaca-paper")["warnings"])
        text = cs.render_text(report)
        self.assertIn("environment native store path overrides present: HF_TOKEN_PATH", text)
        self.assertNotIn(str(elsewhere), json.dumps(report) + text)
        self.assertEqual(self.report()["environment"]["native_store_path_overrides_present"], [])
        result = self.run_cli(env, "--json")
        self.assertEqual(json.loads(result.stdout)["environment"]["native_store_path_overrides_present"],
                         ["HF_TOKEN_PATH"])

    def test_token_variables_are_flagged_by_name_only(self):
        other = "SENTINELHF" + os.urandom(12).hex()
        env = {**self.env, "HUGGING_FACE_HUB_TOKEN": self.fake, "HF_TOKEN": other}
        report = self.report(env)
        self.assertEqual(report["environment"]["must_not_be_set_present"],
                         ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"])
        self.assertNotIn(self.fake, json.dumps(report) + cs.render_text(report))
        self.assertNotIn(other, json.dumps(report) + cs.render_text(report))
        result = self.run_cli({**self.env, "HUGGING_FACE_HUB_TOKEN": self.fake})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("environment must_not_be_set present: HUGGING_FACE_HUB_TOKEN", result.stdout)


if __name__ == "__main__":
    unittest.main()
