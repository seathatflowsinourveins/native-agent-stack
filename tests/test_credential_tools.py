"""Tests for tools/credentials: hidden-prompt storage, the read-only rate-limit probe and
the terminal launcher. Every value is a random fake generated per test."""
from __future__ import annotations

import email.message
import http.client
import http.server
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "credentials"
sys.path.insert(0, str(TOOLS))
import alpaca_rate_limit_probe as probe_mod  # noqa: E402
import set_credential as store_mod  # noqa: E402


def fake_token(prefix: str = "") -> str:
    return prefix + os.urandom(12).hex()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.env = {"HOME": str(base / "home"), "XDG_CONFIG_HOME": str(base / "cfg")}
        self.store = base / "cfg" / "native-agent-stack"

    def tearDown(self):
        self.tmp.cleanup()

    def run_store(self, entry, answers):
        answers = iter(answers)
        out = io.StringIO()
        code = store_mod.run(entry, env=self.env, prompt=lambda _p: next(answers), out=out)
        return code, out.getvalue()

    def test_stores_values_atomically_with_private_modes(self):
        key_value, other_value = fake_token("PK"), fake_token()
        code, output = self.run_store("alpaca-paper", [key_value, other_value, ""])
        self.assertEqual(code, 0)
        path = self.store / "alpaca-paper.env"
        self.assertEqual(stat.S_IMODE(os.lstat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.lstat(self.store).st_mode), 0o700)
        self.assertEqual(path.read_text(),
                         f"export APCA_API_KEY_ID={key_value}\nexport APCA_API_SECRET_KEY={other_value}\n")
        self.assertEqual(probe_mod.read_env_file(path), (key_value, other_value))  # round-trips
        self.assertIn("APCA_API_KEY_ID", output)
        for value in (key_value, other_value):
            self.assertNotIn(value, output)
        self.assertNotIn("warning", output)
        self.assertEqual([p.name for p in self.store.iterdir()], ["alpaca-paper.env"])  # no temp left

    def test_prefix_mismatch_warns_without_echoing(self):
        key_value = fake_token("AK")
        code, output = self.run_store("alpaca-paper", [key_value, fake_token(), ""])
        self.assertEqual(code, 0)
        self.assertIn("does not start with PK", output)
        self.assertNotIn(key_value, output)

    def test_replacing_needs_the_hidden_word_replace(self):
        self.run_store("alpaca-paper", [fake_token("PK"), fake_token(), ""])
        path = self.store / "alpaca-paper.env"
        before = path.read_text()
        code, _ = self.run_store("alpaca-paper", ["y"])
        self.assertEqual(code, 1)
        self.assertEqual(path.read_text(), before)
        code, _ = self.run_store("alpaca-paper", ["replace", fake_token("PK"), fake_token(), ""])
        self.assertEqual(code, 0)
        self.assertNotEqual(path.read_text(), before)

    def test_refuses_store_inside_git_worktree(self):
        repo = Path(self.tmp.name) / "repo"
        (repo / ".git").mkdir(parents=True)
        self.env["XDG_CONFIG_HOME"] = str(repo / "cfg")
        with self.assertRaises(store_mod.Refused):
            self.run_store("alpaca-paper", [fake_token("PK"), fake_token(), ""])

    def test_refuses_symlinked_store(self):
        target = Path(self.tmp.name) / "elsewhere"
        target.mkdir()
        self.store.parent.mkdir(parents=True)
        self.store.symlink_to(target)
        with self.assertRaises(store_mod.Refused):
            self.run_store("alpaca-paper", [fake_token("PK"), fake_token(), ""])
        self.assertEqual(list(target.iterdir()), [])

    def test_only_operator_supplied_stored_entries(self):
        for entry in ("alpaca-live", "grafana-admin", "claude-native", "no-such-entry"):
            with self.subTest(entry=entry), self.assertRaises(store_mod.Refused):
                store_mod.load_entry(entry, env=self.env)
        self.assertEqual(store_mod.load_entry("typesafe", env=self.env)["id"], "typesafe")

    def test_value_encoding(self):
        self.assertEqual(store_mod.encode("A", "abc-123"), "export A=abc-123\n")
        self.assertEqual(store_mod.encode("A", "project name a@b.example"),
                         'export A="project name a@b.example"\n')
        # `~` never goes out bare (a sourcing shell would expand it); quoted, bash leaves it alone.
        self.assertEqual(store_mod.encode("A", "tilde~home"), 'export A="tilde~home"\n')
        for bad in ("", " padded", "has\nnewline", "has\ttab", 'has"quote', "has$dollar", "has`tick",
                    "back\\slash", "café bar", "nul\x00"):
            with self.subTest(bad=bad), self.assertRaises(store_mod.Refused):
                store_mod.encode("A", bad)

    def test_cli_refuses_without_a_terminal(self):
        result = subprocess.run([sys.executable, str(TOOLS / "set_credential.py"), "alpaca-paper"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
                                env={"PATH": os.environ.get("PATH", ""), **self.env})
        self.assertEqual(result.returncode, 2)
        self.assertIn("interactive terminal", result.stderr)
        self.assertFalse(self.store.exists())


class _Response:
    def __init__(self, status, headers):
        self.status, self.headers = status, headers

    def close(self):
        pass

    def read(self):  # pragma: no cover - the probe must never read the body
        raise AssertionError("body read")


def headers(**values):
    message = email.message.Message()
    for name, value in values.items():
        message[name.replace("_", "-")] = value
    return message


class ProbeFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "store"
        self.dir.mkdir(mode=0o700)
        os.chmod(self.dir, 0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, mode=0o600, name="paper.env", directory=None):
        path = (directory or self.dir) / name
        path.write_text(text)
        os.chmod(path, mode)
        return path

    def pair(self):
        return fake_token("PK"), fake_token()

    def test_reads_the_two_values(self):
        val_a, val_b = self.pair()
        path = self.write(f'# comment\nexport APCA_API_KEY_ID={val_a}\nAPCA_API_SECRET_KEY="{val_b}"\n')
        self.assertEqual(probe_mod.read_env_file(path), (val_a, val_b))

    def test_refuses_unsafe_files(self):
        val_a, val_b = self.pair()
        body = f"APCA_API_KEY_ID={val_a}\nAPCA_API_SECRET_KEY={val_b}\n"
        cases = {"0644": self.write(body, mode=0o644, name="a.env"),
                 "0400": self.write(body, mode=0o400, name="b.env"),
                 "half": self.write(f"APCA_API_KEY_ID={val_a}\n", name="c.env"),
                 "not a token": self.write(f"APCA_API_KEY_ID=has space\nAPCA_API_SECRET_KEY={val_b}\n",
                                           name="d.env"),
                 "absent": self.dir / "absent.env"}
        link = self.dir / "link.env"
        link.symlink_to(self.write(body, name="real.env"))
        cases["symlink"] = link
        hard = self.write(body, name="hard.env")
        os.link(hard, self.dir / "hard-2.env")
        cases["two links"] = hard
        for label, path in cases.items():
            with self.subTest(label), self.assertRaises(probe_mod.Refused):
                probe_mod.read_env_file(path)

    def test_refuses_loose_or_repository_directories(self):
        val_a, val_b = self.pair()
        loose = Path(self.tmp.name) / "loose"
        loose.mkdir()
        os.chmod(loose, 0o755)
        with self.assertRaises(probe_mod.Refused):
            probe_mod.read_env_file(self.write(f"APCA_API_KEY_ID={val_a}\nAPCA_API_SECRET_KEY={val_b}\n",
                                               directory=loose))
        repo = Path(self.tmp.name) / "repo"
        (repo / ".git").mkdir(parents=True)
        inside = repo / "cfg"
        inside.mkdir(mode=0o700)
        os.chmod(inside, 0o700)
        with self.assertRaises(probe_mod.Refused):
            probe_mod.read_env_file(self.write(f"APCA_API_KEY_ID={val_a}\nAPCA_API_SECRET_KEY={val_b}\n",
                                               directory=inside))


class ProbeRequestTests(unittest.TestCase):
    def test_sends_one_get_and_keeps_only_rate_limit_headers(self):
        seen = []

        class Opener:
            def open(self, request, timeout):
                seen.append(request)
                return _Response(200, headers(x_ratelimit_limit="1000", x_ratelimit_remaining="999",
                                              x_ratelimit_reset="1790260000", x_request_id="rid"))

        val_a, val_b = fake_token("PK"), fake_token()
        result = probe_mod.probe(val_a, val_b, opener=Opener())
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].get_method(), "GET")
        self.assertEqual(seen[0].full_url, "https://paper-api.alpaca.markets/v2/account")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(sorted(result["rate_limit_headers"]),
                         ["x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"])
        self.assertEqual(result["interpretation"], "1000 calls/min")
        rendered = json.dumps(result)
        for value in (val_a, val_b):
            self.assertNotIn(value, rendered)

    def test_http_error_still_reports_headers(self):
        class Opener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized",
                                             headers(x_ratelimit_limit="200"), None)

        result = probe_mod.probe("a", "b", opener=Opener())
        self.assertEqual(result["http_status"], 401)
        self.assertEqual(result["rate_limit_headers"], {"x-ratelimit-limit": "200"})
        self.assertIn("HTTP 401", result["interpretation"])

    def test_failures_report_only_the_error_type(self):
        for error in (urllib.error.URLError("down"), http.client.BadStatusLine("junk"), ValueError("x")):
            class Opener:
                def open(self, request, timeout, _error=error):
                    raise _error

            with self.subTest(error=type(error).__name__):
                result = probe_mod.probe("a", "b", opener=Opener())
                self.assertIsNone(result["http_status"])
                self.assertEqual(result["error"], type(error).__name__)

    def test_redirects_are_never_followed_end_to_end(self):
        hits = {"origin": 0, "target": 0}

        def handler(name, redirect_to=None):
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    hits[name] += 1
                    if redirect_to:
                        self.send_response(302)
                        self.send_header("Location", redirect_to())
                    else:
                        self.send_response(200)
                    self.end_headers()

                def log_message(self, *args):
                    pass
            return Handler

        target = http.server.HTTPServer(("127.0.0.1", 0), handler("target"))
        origin = http.server.HTTPServer(("127.0.0.1", 0), handler(
            "origin", lambda: f"http://127.0.0.1:{target.server_address[1]}/stolen"))
        servers = [target, origin]
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            opener = urllib.request.build_opener(probe_mod._NoRedirect())
            request = urllib.request.Request(f"http://127.0.0.1:{origin.server_address[1]}/v2/account",
                                             headers={"APCA-API-KEY-ID": "k", "APCA-API-SECRET-KEY": "s"})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                opener.open(request, timeout=5)
            self.assertEqual(caught.exception.code, 302)
            caught.exception.close()
            self.assertEqual(hits, {"origin": 1, "target": 0})
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()

    def test_only_the_fixed_paper_host(self):
        self.assertEqual(probe_mod.HOST, "https://paper-api.alpaca.markets")


class ProbeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "store"
        self.dir.mkdir(mode=0o700)
        os.chmod(self.dir, 0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def test_there_is_no_live_option(self):
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr), self.assertRaises(SystemExit) as caught:
            probe_mod.main(["--account", "live"])
        self.assertEqual(caught.exception.code, 2)

    def test_paper_file_writes_private_result_without_following_symlinks(self):
        val_a, val_b = fake_token("PK"), fake_token()
        path = self.dir / "paper.env"
        path.write_text(f"export APCA_API_KEY_ID={val_a}\nexport APCA_API_SECRET_KEY={val_b}\n")
        os.chmod(path, 0o600)
        results = Path(self.tmp.name) / "results"
        results.mkdir()
        victim = Path(self.tmp.name) / "victim.txt"
        victim.write_text("untouched")
        out = results / "paper.json"
        out.symlink_to(victim)

        class Opener:
            def open(self, request, timeout):
                return _Response(200, headers(x_ratelimit_limit="200"))

        stdout = io.StringIO()
        with mock.patch.object(probe_mod.urllib.request, "build_opener", return_value=Opener()), \
                mock.patch("sys.stdout", stdout):
            code = probe_mod.main(["--env-file", str(path), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertEqual(victim.read_text(), "untouched")
        self.assertFalse(out.is_symlink())
        self.assertEqual(stat.S_IMODE(os.lstat(out).st_mode), 0o600)
        for text in (stdout.getvalue(), out.read_text()):
            self.assertNotIn(val_a, text)
            self.assertNotIn(val_b, text)
        self.assertEqual(json.loads(out.read_text())["interpretation"], "200 calls/min: standard tier")


class LauncherTests(unittest.TestCase):
    def run_launcher(self, *args, state):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"),
               "XDG_STATE_HOME": str(state)}
        if os.environ.get("WSL_DISTRO_NAME"):  # exercise the WSL launcher branch on WSL hosts
            env["WSL_DISTRO_NAME"] = os.environ["WSL_DISTRO_NAME"]
        return subprocess.run(["bash", str(TOOLS / "open_credential_terminal.sh"), *args],
                              capture_output=True, text=True, timeout=60, env=env)

    def test_store_mode_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_launcher("alpaca-paper", "--probe", "--dry-run", state=Path(tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            out = result.stdout
            self.assertIn("python3 -I tools/credentials/set_credential.py alpaca-paper", out)
            self.assertIn("alpaca_rate_limit_probe.py --out", out)
            self.assertIn("git status --porcelain -- tools/credentials", out)
            self.assertIn("unset PYTHONPATH", out)
            sessions = Path(tmp) / "native-agent-stack" / "credential-sessions"
            self.assertEqual(stat.S_IMODE(os.lstat(sessions).st_mode), 0o700)
            self.assertEqual(list(sessions.iterdir()), [])

    def test_rejects_bad_arguments_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            for args in (("../etc",), ("typesafe", "--probe"), ("--live-rate-limit",),
                         ("alpaca-paper", "--bogus"), ("alpaca-paper", "typesafe"), ()):
                with self.subTest(args=args):
                    self.assertEqual(self.run_launcher(*args, state=Path(tmp)).returncode, 2)
            unsafe = Path(tmp) / "has space"
            unsafe.mkdir()
            result = self.run_launcher("typesafe", "--dry-run", state=unsafe)
            self.assertEqual(result.returncode, 2)
            self.assertIn("cannot pass safely", result.stderr)


if __name__ == "__main__":
    unittest.main()
