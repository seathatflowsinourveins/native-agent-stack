"""Run the fenced sampler only with an isolated stub client and synthetic identities."""
import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ClaudeUsageSamplerTests(unittest.TestCase):
    def setUp(self):
        self.sampler = importlib.import_module("observability.claude_usage_sampler")
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.binary = self.root / "bin"
        self.binary.mkdir()
        self.client = self.binary / "claude"
        self.config = self.root / "fixture-runtime"
        self.config.mkdir()
        self.identity = self.root / "identity.txt"
        self.private = "fixture-account@example.invalid"
        self.identity.write_text(self.private)
        self.identity.chmod(0o600)
        self.workdir = self.root / "probe"
        self.workdir.mkdir(mode=0o700)
        self.ledger = self.root / "ledger.jsonl"
        self.ledger.write_text("")
        self.state = self.root / "sampler.json"
        self.output = self.root / "usage.prom"
        self.calls = self.root / "stub-calls.jsonl"
        self.accounts = self.root / "accounts.json"
        self.accounts.write_text(json.dumps([{"identity_file": str(self.identity), "config_dir": str(self.config)}]))
        # The sole executable selected by this PATH is our stub. No real account/client is opened.
        self.environment = {"PATH": str(self.binary), "HOME": str(self.root), "CLAUDECODE": "fixture-parent"}
        self.stub()

    def stub(self, status="rejected", *, fail=False, timeout=False):
        info = {"status": status, "rateLimitType": "five_hour", "resetsAt": 4000}
        self.client.write_text(f"#!{sys.executable}\n" +
            "import json,os,sys,time\nfrom pathlib import Path\n" +
            f"p=Path({str(self.calls)!r})\n" +
            "with p.open('a') as f: f.write(json.dumps({'args':sys.argv[1:],'cwd':os.getcwd(),"
            "'env_names':sorted(os.environ)})+'\\n')\n" +
            ("time.sleep(5)\n" if timeout else "") +
            f"print({json.dumps({'type':'assistant','response':self.private})!r})\n" +
            f"print({self.private!r},file=sys.stderr)\n" +
            ("sys.exit(2)\n" if fail else f"print({json.dumps({'type':'rate_limit_event','rate_limit_info':info})!r})\nsys.exit(1 if {status!r}=='rejected' else 0)\n"))
        self.client.chmod(0o700)

    def run_once(self, now=2000, timeout=1):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, self.environment, clear=True), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.sampler.sample(self.accounts, self.ledger, self.state, self.output,
                                self.workdir, now=now, timeout=timeout)
        return stdout.getvalue() + stderr.getvalue()

    def test_p2_sampler_derives_one_way_index_runs_fenced_and_writes_private_textfile(self):
        logs = self.run_once()
        text = self.output.read_text()
        self.assertIn('claude_max_utilization_ratio{account="acct-1",window="five_hour"} 1.0', text)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(1, len(calls))
        args = calls[0]["args"]
        for option, value in (("--permission-mode", "dontAsk"), ("--tools", ""), ("--setting-sources", "local"),
                              ("--max-turns", "1"), ("--output-format", "stream-json")):
            self.assertEqual(value, args[args.index(option) + 1])
        self.assertIn("--strict-mcp-config", args)
        self.assertIn("--no-session-persistence", args)
        self.assertNotIn("CLAUDECODE", calls[0]["env_names"])
        state = json.loads(self.state.read_text())
        self.assertIn(hashlib.sha256(self.private.encode()).hexdigest(), state["account_indexes"])
        self.assertEqual("acct-1", next(iter(state["account_indexes"].values()))["index"])
        for path in self.root.rglob("*"):
            if path.is_file() and path not in (self.identity, self.client, self.accounts):
                self.assertNotIn(self.private, path.read_text())
        self.assertNotIn(self.private, logs)
        self.assertNotIn("assistant", text)

    def test_cadence_guard_survives_retry_restart_and_failed_client(self):
        self.stub(fail=True)
        self.run_once(2000)
        self.run_once(2899)
        self.assertEqual(1, len(self.calls.read_text().splitlines()))
        self.assertIn('claude_max_capture_success{account="acct-1"} 0.0', self.output.read_text())
        self.run_once(2900)
        self.assertEqual(2, len(self.calls.read_text().splitlines()))
        self.assertIn('claude_max_account_present{account="acct-1",window="seven_day"} 1.0', self.output.read_text())

    def test_local_settings_fence_and_symlink_refuse_before_client_launch(self):
        settings = self.workdir / ".claude/settings.local.json"
        settings.parent.mkdir()
        for symlink in (False, True):
            if symlink:
                settings.symlink_to(self.root / "absent")
            else:
                settings.write_text("{fixture}")
            with self.subTest(symlink=symlink), self.assertRaises(self.sampler.InputError):
                self.run_once()
            self.assertFalse(self.calls.exists())
            settings.unlink()

    def test_ancestor_local_settings_are_metadata_checked_and_never_read(self):
        settings = self.root / ".claude/settings.local.json"
        settings.parent.mkdir()
        settings.write_text("private-settings-fixture")
        with self.assertRaises(self.sampler.InputError):
            self.run_once()
        self.assertFalse(self.calls.exists())

    def test_identity_index_stays_stable_when_the_pool_grows_and_paths_change(self):
        self.run_once()
        second = self.root / "second-identity"
        second.write_text("another-fixture@example.invalid")
        second.chmod(0o600)
        other_config = self.root / "other-runtime"
        other_config.mkdir()
        moved = self.root / "moved-identity"
        self.identity.rename(moved)
        self.accounts.write_text(json.dumps([
            {"identity_file": str(moved), "config_dir": str(self.config)},
            {"identity_file": str(second), "config_dir": str(other_config)}]))
        self.run_once(2900)
        entries = json.loads(self.state.read_text())["account_indexes"]
        self.assertEqual("acct-1", entries[hashlib.sha256(self.private.encode()).hexdigest()]["index"])
        self.assertEqual("acct-2", entries[hashlib.sha256(second.read_bytes()).hexdigest()]["index"])

    def test_sanitizer_retains_only_bounded_fields_and_errors_never_private_text(self):
        output = (json.dumps({"type": "rate_limit_event", "rate_limit_info": {
            "status": "rejected", "rateLimitType": self.private, "prompt": self.private,
            "unifiedWindows": {"five_hour": {"status": self.private, "utilization": self.private},
                               self.private: {"utilization": 1}}}}) + "\nprivate-fixture-non-json").encode()
        text = self.sampler.sanitized_events(output)
        self.assertNotIn(self.private, text)
        self.assertNotIn("private-fixture-non-json", text)
        self.assertIn("{invalid}", text)

    def test_api_credential_environment_is_not_forwarded_to_the_client(self):
        # These values are invented fixture strings, never host credentials.
        self.environment.update(ANTHROPIC_API_KEY="fixture-api-material", CLAUDE_CODE_OAUTH_TOKEN="fixture-token")
        self.run_once()
        call = json.loads(self.calls.read_text().splitlines()[0])
        self.assertNotIn("ANTHROPIC_API_KEY", call["env_names"])
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", call["env_names"])

    def test_timeout_is_bounded_and_failed_output_does_not_reveal_text(self):
        self.stub(timeout=True)
        self.assertNotIn(self.private, self.run_once(timeout=.05))
        self.assertIn('claude_max_capture_success{account="acct-1"} 0.0', self.output.read_text())

    def test_main_success_and_bounded_missing_identity_failure(self):
        args = ["sampler", "--accounts-file", str(self.accounts), "--ledger", str(self.ledger),
                "--state", str(self.state), "--output", str(self.output), "--working-directory", str(self.workdir)]
        with patch.dict(os.environ, self.environment, clear=True), patch("sys.argv", args):
            self.assertEqual(0, self.sampler.main())
        self.identity.unlink()
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, self.environment, clear=True), patch("sys.argv", args), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(1, self.sampler.main())
        self.assertNotIn(self.private, stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(str(self.root), stderr.getvalue())


class ClaudeUsageDeploymentTests(unittest.TestCase):
    def test_user_timer_and_loopback_collection_configs_are_installable_files(self):
        root = ROOT / "observability/claude-usage"
        timer = (root / "claude-usage.timer").read_text()
        self.assertIn("OnCalendar=*-*-* *:00,15,30,45:00 UTC", timer)
        self.assertIn("Persistent=false", timer)
        service = (root / "claude-usage.service").read_text()
        self.assertIn("claude_usage_sampler.py", service)
        self.assertNotIn("uv run", service)
        node = (root / "claude-usage-node-exporter.service").read_text()
        self.assertIn("--web.listen-address=127.0.0.1:29101", node)
        self.assertIn("--collector.textfile.directory=", node)
        import yaml
        scrape = yaml.safe_load((root / "prometheus-scrape.yaml").read_text())["scrape_configs"][0]
        self.assertEqual(["127.0.0.1:29101"], scrape["static_configs"][0]["targets"])
        self.assertEqual("claude-usage", scrape["job_name"])

    def test_hashed_runtime_installer_invokes_only_stub_install_commands(self):
        script = ROOT / "observability/claude-usage/install-runtime.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin"
            binary.mkdir()
            log = root / "commands.jsonl"
            stub = f"#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\n" + \
                f"p=Path({str(log)!r})\nwith p.open('a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n"
            python = binary / "python3"
            python.write_text(stub +
                "if sys.argv[1:3]==['-m','venv']:\n target=Path(sys.argv[3])/'bin/python'\n target.parent.mkdir(parents=True)\n target.write_text(Path(sys.argv[0]).read_text())\n target.chmod(0o700)\n")
            python.chmod(0o700)
            installer = binary / "install"
            installer.write_text(stub)
            installer.chmod(0o700)
            result = subprocess.run(["/bin/sh", str(script), str(root / "runtime")],
                                    env={"PATH": f"{binary}:/usr/bin:/bin"}, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            pip = next(call for call in calls if call[:3] == ["-m", "pip", "install"])
            self.assertIn("--require-hashes", pip)
            self.assertIn("--only-binary=:all:", pip)
            self.assertEqual(str(ROOT / "observability/claude-usage/requirements.txt"), pip[pip.index("-r") + 1])

    @unittest.skipUnless(shutil.which("systemd-analyze"), "unit syntax integration needs systemd-analyze")
    def test_native_unit_verification_with_fixture_executables_installs_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / ".local/share/native-agent-stack/claude-usage-runtime/bin/python"
            node = root / ".local/bin/node_exporter"
            for path in (runtime, node):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("#!/bin/sh\nexit 99\n")
                path.chmod(0o700)
            units = []
            for name in ("claude-usage.service", "claude-usage.timer", "claude-usage-node-exporter.service"):
                unit = root / name
                unit.write_text((ROOT / "observability/claude-usage" / name).read_text().replace("%h", str(root)).replace("%t", str(root)))
                units.append(str(unit))
            result = subprocess.run(["systemd-analyze", "--user", "--man=no", "verify", *units],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / "sampler.json").exists())


if __name__ == "__main__":
    unittest.main()
