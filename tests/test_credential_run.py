"""Tests for tools/credentials/credential_run.py, the id-based key runner.

Local integration checks, not upstream acceptance (docs/acceptance-evidence-policy.md). Every value is a synthetic
fake generated per test. The store is a temporary XDG_CONFIG_HOME that exists only in the environment of the runner
these tests start, and no test reads a real store, a real *.env file, the kernel keyring or a native sign-in.
"""
from __future__ import annotations

import ast
import base64
import contextlib
import hashlib
import io
import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "credentials"
TOOL = TOOLS / "credential_run.py"
sys.path.insert(0, str(TOOLS))
import credential_run as run_mod  # noqa: E402
import set_credential as writer  # noqa: E402

INJECTABLE_IDS = {"alpaca-paper", "alpaca-paper-2", "sec-contact", "databento", "typesafe", "omniroute", "tavily"}
NOT_INJECTABLE_IDS = ("grafana-admin", "nativestack-generation-key", "openhands-session", "claude-native",
                      "codex-native", "gh-native", "huggingface-native", "huggingface-native-stored", "ibkr-gateway",
                      "github-actions")
MARK = b"[REDACTED:TAVILY_API_KEY]"
PARTIAL = b"[REDACTED-PARTIAL:TAVILY_API_KEY]"
STORE_LINE = re.compile(rb"export +[A-Za-z_]")


def _host_hands_cores_to_a_collector() -> bool:
    """This host's own core_pattern, read here without the tool: a `|` (systemd-coredump, apport) or `@` (a core socket)."""
    try:
        with open("/proc/sys/kernel/core_pattern", "rb") as handle:
            return handle.read(1) in (b"|", b"@")
    except OSError:
        return False


# The runner refuses to start on such a host (review of 2026-09-29, finding 2), and CI runners commonly are one. There
# the tests start it through this launcher, which points CORE_PATTERN_FILE at a temporary file that holds "core"; the
# two tests of the real re-execution skip. The refusal itself is tested in process with its own pattern files.
# CREDENTIAL_RUN_TEST_LAUNCHER=1 forces the launcher on any host, to exercise this path.
HOST_PIPES_CORES = os.environ.get("CREDENTIAL_RUN_TEST_LAUNCHER") == "1" or _host_hands_cores_to_a_collector()
LAUNCHER = ("import os, sys\n"
            f"sys.path[:0] = [{str(TOOLS)!r}, {str(ROOT / 'scripts')!r}]\n"
            "import credential_run\n"
            "credential_run.CORE_PATTERN_FILE = os.environ.pop('CORE_PATTERN_TEST_FILE')\n"
            "sys.exit(credential_run.main(sys.argv[1:]))\n")

# A child that reports what reached its environment by sha256 only, so no test output holds a value.
REPORT = ("import hashlib, json, os, sys\n"
          "names = json.loads(sys.argv[1])\n"
          "print(json.dumps({n: hashlib.sha256(os.environ[n].encode()).hexdigest() if n in os.environ else None\n"
          "                  for n in names}, sort_keys=True))\n")
# A careless child: it prints its own key raw and in the encodings the masker cites, on both streams.
FORMS = ("import base64, json, os, re, sys, urllib.parse\n"
         "v = os.environ['TAVILY_API_KEY']\n"
         "raw = v.encode()\n"
         "lines = [v]\n"
         "for prefix in (b'', b'u', b'us', b'use', b'user:'):\n"
         "    lines.append(base64.b64encode(prefix + raw + b'!').decode())\n"
         "    lines.append(base64.urlsafe_b64encode(prefix + raw + b'?').decode())\n"
         "q = urllib.parse.quote(v, safe='')\n"
         "lines += [q, re.sub('%[0-9A-F]{2}', lambda m: m.group().lower(), q), json.dumps({'key': v}),\n"
         "          raw.hex(), raw.hex().upper()]\n"
         "for stream in (sys.stdout, sys.stderr):\n"
         "    for line in lines:\n"
         "        stream.write('form ' + line + '\\n')\n")


def fake(prefix: str = "", tail: str = "") -> str:
    return prefix + os.urandom(12).hex() + tail


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def py(code: str, *args: str) -> list[str]:
    """`-- python3 -I -c code args...`: the runner's command part."""
    return ["--", sys.executable, "-I", "-c", code, *args]


def stable_interiors(raw: bytes) -> list[bytes]:
    """The characters of base64/base64url that depend only on raw, at each byte alignment (the test's own copy)."""
    found = []
    for altchars in (None, b"-_"):
        for align in (0, 1, 2):
            encoded = base64.b64encode(b"\0" * align + raw, altchars=altchars)
            found.append(encoded[(0, 2, 3)[align]:(8 * (align + len(raw))) // 6])
    return found


class RunnerCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.config = self.base / "cfg"
        self.store = self.config / "native-agent-stack"
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.base / "home"),
                    "XDG_CONFIG_HOME": str(self.config)}
        self.core_pattern = self.base / "core_pattern"  # read only through the launcher (HOST_PIPES_CORES)
        self.core_pattern.write_text("core\n")
        self.values: list[str] = []  # every planted value, for the never-echoed checks

    def command(self, *args: str) -> list[str]:
        """The argv that starts the runner: the tool itself, or the launcher on a host that pipes crash dumps."""
        if HOST_PIPES_CORES:
            return [sys.executable, "-I", "-S", "-c", LAUNCHER, *args]
        return [sys.executable, str(TOOL), *args]

    def tool_environment(self, extra: dict | None = None) -> dict:
        environment = {**self.env, **(extra or {})}
        if HOST_PIPES_CORES:
            environment["CORE_PATTERN_TEST_FILE"] = str(self.core_pattern)
        return environment

    def plant(self, entry_id: str, text: str | bytes, mode: int = 0o600, store: Path | None = None) -> Path:
        store = self.store if store is None else store
        store.mkdir(parents=True, exist_ok=True)
        store.chmod(0o700)
        path = store / f"{entry_id}.env"
        path.write_bytes(text if isinstance(text, bytes) else text.encode("ascii"))
        path.chmod(mode)
        return path

    def tavily(self, value: str | None = None) -> str:
        value = fake("tvly-", "/+=:@" + os.urandom(4).hex()) if value is None else value
        self.values.append(value)
        self.plant("tavily", f"export TAVILY_API_KEY={value}\n")
        return value

    def alpaca(self, base_url: str | None = "https://paper-api.alpaca.markets") -> tuple[str, str]:
        key, secret = fake("PK"), fake("", "/x+y=")
        self.values += [key, secret]
        text = f"# written by hand\nexport APCA_API_KEY_ID={key}\nexport APCA_API_SECRET_KEY=\"{secret}\"\n"
        if base_url is not None:
            text += f"export APCA_API_BASE_URL={base_url}\n"
        self.plant("alpaca-paper", text)
        return key, secret

    def run_tool(self, *args: str, input: bytes | None = None, env: dict | None = None,
                 timeout: float = 60) -> subprocess.CompletedProcess:
        stdin = subprocess.DEVNULL if input is None else None
        return subprocess.run(self.command(*args), input=input, stdin=stdin, capture_output=True,
                              env=self.tool_environment(env), timeout=timeout)

    def start_tool(self, *args: str) -> subprocess.Popen:
        process = subprocess.Popen(self.command(*args), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.tool_environment())

        def reap():  # a failed assertion must not leave the runner or its pipes behind
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=30)

        self.addCleanup(reap)
        return process

    def read_until(self, stream, needle: bytes, seconds: float = 20.0) -> bytes:
        """Bytes read from stream until needle arrives (or the deadline passes)."""
        data, deadline = b"", time.monotonic() + seconds
        while needle not in data and time.monotonic() < deadline:
            ready, _, _ = select.select([stream], [], [], 0.2)
            if ready:
                chunk = os.read(stream.fileno(), 65536)
                if not chunk:
                    break
                data += chunk
        return data

    def assert_never_echoed(self, *texts, paths: bool = True):
        # Neither a value nor any six-character piece of one, and (unless a child printed its own environment, which
        # holds this test's HOME) no path under the temporary store.
        for text in texts:
            text = text.decode("latin-1") if isinstance(text, bytes) else text
            if paths:
                self.assertNotIn(str(self.base), text)
            for value in self.values:
                self.assertNotIn(value, text)
                pieces = {value[i:i + 6] for i in range(len(value) - 5)}
                self.assertEqual(sorted(piece for piece in pieces if piece in text), [])


class InjectionTests(RunnerCase):
    def test_injects_only_the_ids_declared_variables(self):
        key, secret = self.alpaca()
        names = ["APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL", "TAVILY_API_KEY", "SEC_USER_AGENT"]
        result = self.run_tool("alpaca-paper", *py(REPORT, json.dumps(names)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "APCA_API_KEY_ID": sha(key), "APCA_API_SECRET_KEY": sha(secret),
            "APCA_API_BASE_URL": sha("https://paper-api.alpaca.markets"), "TAVILY_API_KEY": None,
            "SEC_USER_AGENT": None})
        self.assertEqual(result.stderr, b"")  # no banner, no path
        # The public base URL is injected unmasked; the key pair is masked.
        shown = self.run_tool("alpaca-paper", *py(
            "import os\nfor n in ('APCA_API_KEY_ID', 'APCA_API_SECRET_KEY', 'APCA_API_BASE_URL'):\n"
            "    print(n + '=' + os.environ[n])\n"))
        self.assertEqual(shown.stdout, b"APCA_API_KEY_ID=[REDACTED:APCA_API_KEY_ID]\n"
                                       b"APCA_API_SECRET_KEY=[REDACTED:APCA_API_SECRET_KEY]\n"
                                       b"APCA_API_BASE_URL=https://paper-api.alpaca.markets\n")
        self.assert_never_echoed(result.stdout, result.stderr, shown.stdout, shown.stderr)

    def test_strips_other_inventory_names_from_the_child(self):
        value = self.tavily()
        stray = {"TAVILY_API_KEY": fake("tvly-"), "APCA_API_KEY_ID": fake("PK"), "APCA_API_SECRET_KEY": fake(),
                 "GF_SECURITY_ADMIN_PASSWORD": fake(), "GITHUB_TOKEN": fake("ghp_"), "OPENAI_API_KEY": fake("sk-"),
                 "ALPACA_API_KEY": fake(), "UNRELATED_SETTING": "kept-as-is", "PAPER_ENV_FILE": "/nonexistent/p.env"}
        self.values += [v for k, v in stray.items() if k not in ("UNRELATED_SETTING", "PAPER_ENV_FILE")]
        result = self.run_tool("tavily", *py(REPORT, json.dumps(sorted(stray))), env=stray)
        self.assertEqual(result.returncode, 0, result.stderr)
        seen = json.loads(result.stdout)
        self.assertEqual(seen.pop("TAVILY_API_KEY"), sha(value))  # the file's value, never the caller's
        self.assertEqual(seen.pop("UNRELATED_SETTING"), sha("kept-as-is"))
        self.assertEqual(seen.pop("PAPER_ENV_FILE"), sha("/nonexistent/p.env"))  # a pointer is a path, not a value
        self.assertEqual(seen, dict.fromkeys(seen))  # every other inventory and must_not_be_set name is gone
        self.assert_never_echoed(result.stdout, result.stderr)

    def test_only_narrows_to_declared_names(self):
        key, _secret = self.alpaca()
        names = json.dumps(["APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL"])
        result = self.run_tool("alpaca-paper", "--only", "APCA_API_KEY_ID", *py(REPORT, names))
        self.assertEqual(json.loads(result.stdout), {"APCA_API_KEY_ID": sha(key), "APCA_API_SECRET_KEY": None,
                                                     "APCA_API_BASE_URL": None})
        both = self.run_tool("alpaca-paper", "--only", "APCA_API_KEY_ID", "--only", "APCA_API_BASE_URL",
                             *py(REPORT, names))
        self.assertEqual(json.loads(both.stdout)["APCA_API_SECRET_KEY"], None)
        self.assertEqual(json.loads(both.stdout)["APCA_API_BASE_URL"], sha("https://paper-api.alpaca.markets"))
        # A name the entry does not declare (another entry's, or a value pasted where a name belongs) is a usage
        # error that never repeats the word.
        pasted = fake("PK").upper()
        self.values.append(pasted)
        for word in ("TAVILY_API_KEY", pasted):
            refused = self.run_tool("alpaca-paper", "--only", word, "--", "true")
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertNotIn(word.encode(), refused.stdout + refused.stderr)
            self.assertIn(b"APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL", refused.stderr)
        self.assertEqual(self.run_tool("alpaca-paper", "--only").returncode, 2)
        # A declared optional variable that the file does not hold is refused, not silently left out.
        self.alpaca(base_url=None)
        absent = self.run_tool("alpaca-paper", "--only", "APCA_API_BASE_URL", "--", "true")
        self.assertEqual(absent.returncode, 1)
        self.assertIn(b"only_variable_absent: APCA_API_BASE_URL", absent.stderr)
        self.assert_never_echoed(result.stdout, both.stdout, refused.stderr, absent.stderr)

    def test_parser_never_expands(self):
        # Characters a shell would expand or glob, inside a quoted value, reach the child literally.
        quoted = fake("q-") + " ~/x * ? [a] {b} ! # % & ( ) | < > ; ' , ^ " + fake()
        single = "single quoted " + fake()
        contact = "Jane Tester jane.tester@example.invalid " + fake()
        self.values += [quoted, single, contact]
        self.plant("tavily", f'export TAVILY_API_KEY="{quoted}"\n')
        self.plant("sec-contact", f"export SEC_USER_AGENT='{single}'\n  export EDGAR_IDENTITY=\"{contact}\"  \n")
        tavily = self.run_tool("tavily", *py(REPORT, '["TAVILY_API_KEY"]'))
        self.assertEqual(json.loads(tavily.stdout), {"TAVILY_API_KEY": sha(quoted)}, tavily.stderr)
        sec = self.run_tool("sec-contact", *py(REPORT, '["SEC_USER_AGENT", "EDGAR_IDENTITY"]'))
        self.assertEqual(json.loads(sec.stdout), {"SEC_USER_AGENT": sha(single), "EDGAR_IDENTITY": sha(contact)})
        # Both are masked, including the form-encoded (space as +) copy of the contact.
        spaced = self.run_tool("sec-contact", *py(
            "import os, urllib.parse\nv = os.environ['EDGAR_IDENTITY']\nprint(v)\nprint(urllib.parse.quote_plus(v))\n"))
        self.assertEqual(spaced.stdout, b"[REDACTED:EDGAR_IDENTITY]\n[REDACTED:EDGAR_IDENTITY]\n")
        self.assert_never_echoed(tavily.stdout, tavily.stderr, sec.stdout, sec.stderr, spaced.stdout)


class RefusalTests(RunnerCase):
    def test_refuses_unknown_bad_and_engine_only_ids(self):
        marker = self.base / "child-ran"
        child = py(f"open({str(marker)!r}, 'w').close()")
        for bad in ("Tavily", "../tavily", "tavily;id", "tavily env", "", "TAVILY_API_KEY", "tvly_x"):
            with self.subTest(id=bad):
                result = self.run_tool(bad, *child)
                self.assertEqual(result.returncode, 2, result.stderr)
                if bad:
                    self.assertNotIn(bad.encode(), result.stdout + result.stderr)
        pasted = fake("tvly-")  # a lowercase value typed where the id belongs matches the id pattern
        self.values.append(pasted)
        for unknown in ("no-such-entry", "get", "print", "list", "token", pasted):
            with self.subTest(id=unknown):
                result = self.run_tool(unknown, *child)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"unknown inventory id", result.stderr)
                self.assertNotIn(unknown.encode(), result.stdout + result.stderr)
        for held in NOT_INJECTABLE_IDS:
            with self.subTest(id=held):
                result = self.run_tool(held, *child)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f"credential_run: {held}: refused: not_injectable".encode(), result.stderr)
        # The hint names the engine or native client that holds the key.
        self.assertIn(b"observability/backends/configure.py", self.run_tool("grafana-admin", *child).stderr)
        self.assertIn(b"(claude)", self.run_tool("claude-native", *child).stderr)
        self.assertIn(b"GitHub Actions", self.run_tool("github-actions", *child).stderr)
        self.assertFalse(marker.exists(), "a refused run started its command")

    def test_refuses_unsafe_files(self):
        self.tavily()
        path = self.store / "tavily.env"
        marker = self.base / "child-ran"
        child = py(f"open({str(marker)!r}, 'w').close()")
        outputs = []

        def refused(reason: bytes, **kwargs):
            result = self.run_tool("tavily", *child, timeout=20, **kwargs)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b"credential_run: tavily: unsafe: " + reason, result.stderr)
            outputs.extend((result.stdout, result.stderr))

        path.chmod(0o644)
        refused(b"mode_not_0600")
        path.chmod(0o600)
        aside = self.base / "aside.env"
        os.replace(path, aside)
        os.symlink(aside, path)
        refused(b"symlink_refused")
        path.unlink()
        os.replace(aside, path)
        os.link(path, self.store / "second-name")
        refused(b"hard_link")
        (self.store / "second-name").unlink()
        self.store.chmod(0o755)
        refused(b"store_directory_not_private")
        self.store.chmod(0o700)
        path.rename(aside)
        os.mkfifo(path, 0o600)  # a FIFO would block a plain open(); it is refused without waiting for a writer
        refused(b"not_regular_file")
        path.unlink()
        path.write_text("#" * (64 * 1024) + "\n")
        path.chmod(0o600)
        refused(b"too_large")
        path.unlink()
        os.replace(aside, path)
        moved = self.config / "real-store"
        os.replace(self.store, moved)
        os.symlink(moved, self.store)
        refused(b"store_directory_symlink")
        self.store.unlink()
        os.replace(moved, self.store)
        repo = self.base / "repo"
        (repo / ".git").mkdir(parents=True)
        self.plant("tavily", path.read_bytes(), store=repo / "cfg" / "native-agent-stack")
        refused(b"inside_git_worktree", env={"XDG_CONFIG_HOME": str(repo / "cfg")})
        self.assertFalse(marker.exists(), "a refused run started its command")
        self.assert_never_echoed(*outputs)

    def test_refuses_lines_outside_the_grammar(self):
        value = fake("tvly-")
        as_name = value.upper().replace("-", "_")  # a value pasted where a name belongs
        self.values += [value, as_name]
        cases = [
            (f"TAVILY_API_KEY={value}\n", 1, b"not_an_export_line"),
            (f"# a comment\n\nexport TAVILY_API_KEY {value}\n", 3, b"not_an_export_line"),
            (f"set -a\nexport TAVILY_API_KEY={value}\n", 1, b"not_an_export_line"),
            (f"export TAVILY_API_KEY={value}\n. other.env\n", 2, b"not_an_export_line"),
            (f"export TAVILY_API_KEY={value}\r\n", 1, b"control_character"),
            (f"export TAVILY_API_KEY=\t{value}\n", 1, b"control_character"),
            (f"export TAVILY_API_KEY={value}\x00\n", 1, b"control_character"),
            (f"export TAVILY_API_KEY={value}\nexport TAVILY_API_KEY={value}\n", 2, b"duplicate_variable"),
            (f"export TAVILY_API_KEY={value}\nexport {as_name}=x\n", 2, b"undeclared_variable"),
            ("export TAVILY_API_KEY=\n", 1, b"empty_value"),
            ('export TAVILY_API_KEY=""\n', 1, b"empty_value"),
        ]
        outputs = []
        for text, line, reason in cases:
            with self.subTest(text=text.replace(value, "<value>").replace(as_name, "<value>")):
                self.plant("tavily", text)
                result = self.run_tool("tavily", "--", "true")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"line %d: %s" % (line, reason), result.stderr)
                outputs.extend((result.stdout, result.stderr))
        self.plant("tavily", b"export TAVILY_API_KEY=" + value.encode() + b"\xc3\xa9\n")
        result = self.run_tool("tavily", "--", "true")
        self.assertIn(b"line 1: not_ascii", result.stderr)
        self.plant("tavily", "# nothing stored\n")
        missing = self.run_tool("tavily", "--", "true")
        self.assertEqual(missing.returncode, 1)
        self.assertIn(b"credential_run: tavily: missing: required_variable_missing: TAVILY_API_KEY", missing.stderr)
        self.assert_never_echoed(*outputs, result.stderr, missing.stderr)
        for text in outputs:
            self.assertIsNone(STORE_LINE.search(text))  # never a store line

    def test_refuses_values_outside_the_writer_grammar(self):
        # R8: the reader shares set_credential.py's grammar, so a hand edit cannot smuggle shell syntax into a value;
        # the value is refused, never expanded or run.
        ran = self.base / "value-ran"
        marker = self.base / "child-ran"
        child = py(f"open({str(marker)!r}, 'w').close()")
        tail = fake()
        values = [f"abc$(touch {ran}){tail}", f'"abc$(touch {ran}){tail}"', f"abc`touch {ran}`{tail}",
                  f'"abc`touch {ran}`{tail}"', f"abc\\{tail}", f'"abc\\n{tail}"', f'"abc"def{tail}"',
                  f"abc def{tail}", f"abc;touch {ran};{tail}", f"'abc'def{tail}'", f"${{HOME}}{tail}",
                  f'"${{HOME}}{tail}"', f"'$HOME-{tail}'", f'"  {tail}"', f"~/{tail}", f'"{tail}', f"'{tail}"]
        outputs = []
        for raw in values:
            with self.subTest(value=raw.replace(tail, "<tail>")):
                self.plant("tavily", f"export TAVILY_API_KEY={raw}\n")
                result = self.run_tool("tavily", *child)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"credential_run: tavily: unsafe: line 1: outside_writer_grammar", result.stderr)
                self.assertNotIn(raw.encode(), result.stdout + result.stderr)
                outputs.extend((result.stdout, result.stderr))
        self.assertFalse(ran.exists(), "a value was executed")
        self.assertFalse(marker.exists(), "a refused run started its command")
        self.values.append(tail)
        self.assert_never_echoed(*outputs)

    def test_short_values_are_refused(self):
        # Buildkite's LengthMin: a masked value under 6 bytes would mask ordinary output, so it is refused.
        self.plant("tavily", "export TAVILY_API_KEY=abcde\n")
        short = self.run_tool("tavily", "--", "true")
        self.assertEqual(short.returncode, 1)
        self.assertIn(b"credential_run: tavily: unsafe: value_too_short_to_mask: TAVILY_API_KEY", short.stderr)
        self.assertNotIn(b"abcde", short.stdout + short.stderr)
        self.plant("tavily", "export TAVILY_API_KEY=abcdef\n")
        self.assertEqual(self.run_tool("tavily", "--", "true").returncode, 0)
        # A masked optional variable counts too; a public one is not masked, so any length passes.
        self.plant("sec-contact", f'export SEC_USER_AGENT="{fake("Jane ")}"\nexport EDGAR_IDENTITY=abc\n')
        optional = self.run_tool("sec-contact", "--", "true")
        self.assertIn(b"value_too_short_to_mask: EDGAR_IDENTITY", optional.stderr)
        self.alpaca(base_url="x")
        self.assertEqual(self.run_tool("alpaca-paper", "--", "true").returncode, 0)

    def test_usage_errors_never_repeat_arguments(self):
        self.tavily()
        pasted = fake("--tvly-")
        self.values.append(pasted)
        for args in ((), ("tavily",), ("tavily", "--"), ("tavily", pasted, "--", "true"),
                     ("tavily", "--check", "--", "true"), ("tavily", "--only"), ("tavily", "true")):
            with self.subTest(args=len(args)):
                result = self.run_tool(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(b"usage:", result.stderr)
                self.assert_never_echoed(result.stdout, result.stderr)
        for flag in ("--help", "-h"):
            shown = self.run_tool(flag)
            self.assertEqual((shown.returncode, shown.stderr), (0, b""))
            self.assertIn(b"credential_run.py <inventory-id> [--only NAME]... -- <command> [args...]", shown.stdout)

    def test_spawn_failures_have_their_own_codes(self):
        self.tavily()
        plain = self.base / "not-executable"
        plain.write_text("#!/bin/sh\necho no\n")
        plain.chmod(0o644)
        for command, code in (("/nonexistent/no-such-command", 127), (str(plain), 126), (str(self.base), 126)):
            with self.subTest(code=code):
                result = self.run_tool("tavily", "--", command)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertIn(b"credential_run: tavily: cannot start the command", result.stderr)
                self.assert_never_echoed(result.stdout, result.stderr)


class MaskingTests(RunnerCase):
    def test_masks_raw_and_encoded_forms_on_both_streams(self):
        value = self.tavily()
        result = self.run_tool("tavily", *py(FORMS))
        self.assertEqual(result.returncode, 0, result.stderr)
        for stream in (result.stdout, result.stderr):
            lines = stream.splitlines()
            self.assertEqual(len(lines), 16)
            for line in lines:
                self.assertIn(MARK, line)  # every printed form was masked
            for form in stable_interiors(value.encode()):
                self.assertNotIn(form, stream)
            hex_form = value.encode().hex()
            for start in range(0, len(hex_form) - 11):  # no six value bytes in hex, either case
                self.assertNotIn(hex_form[start:start + 12].encode(), stream.lower())
        self.assert_never_echoed(result.stdout, result.stderr)

    def test_an_environment_dump_shows_masked_values(self):
        self.tavily()
        dump = self.run_tool("tavily", *py("import os\nfor k, v in sorted(os.environ.items()):\n    print(k + '=' + v)\n"))
        self.assertIn(b"TAVILY_API_KEY=" + MARK + b"\n", dump.stdout)
        commands = [["--", shutil.which("env") or "/usr/bin/env"], ["--", shutil.which("printenv") or "printenv"]]
        for command in commands:
            result = self.run_tool("tavily", *command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"TAVILY_API_KEY=" + MARK, result.stdout)
            self.assert_never_echoed(result.stdout, result.stderr, paths=False)
        self.assert_never_echoed(dump.stdout, dump.stderr, paths=False)

    def test_masks_a_value_split_across_writes(self):
        self.tavily()
        code = ("import os, sys, time\nv = os.environ['TAVILY_API_KEY']\nh = len(v) // 2\n"
                "for s in (sys.stdout, sys.stderr):\n    s.write('before ' + v[:h]); s.flush()\n"
                "time.sleep(0.4)\n"
                "for s in (sys.stdout, sys.stderr):\n    s.write(v[h:] + ' after\\n'); s.flush()\n")
        result = self.run_tool("tavily", *py(code))
        self.assertEqual(result.stdout, b"before " + MARK + b" after\n")
        self.assertEqual(result.stderr, b"before " + MARK + b" after\n")
        self.assert_never_echoed(result.stdout, result.stderr)

    def test_flushes_an_unterminated_tail_at_eof(self):
        self.tavily()
        # "d" starts the base64 of every Tavily key ("tvly-") and "t" the key itself: a last byte that could begin a
        # value's form is held, then written at the end, because a tail of 3 bytes or less is not held back for good.
        plain = self.run_tool("tavily", *py("import sys\nsys.stdout.write('no newline at the end')\n"))
        self.assertEqual(plain.stdout, b"no newline at the end")
        last_t = self.run_tool("tavily", *py("import sys\nsys.stdout.write('ends with t')\n"))
        self.assertEqual(last_t.stdout, b"ends with t")
        whole = self.run_tool("tavily", *py("import os, sys\nsys.stdout.write('key ' + os.environ['TAVILY_API_KEY'])\n"))
        self.assertEqual(whole.stdout, b"key " + MARK)
        # A held tail (the start of the value) is never printed at EOF: it becomes a partial marker.
        held = self.run_tool("tavily", *py("import os, sys\nsys.stdout.write('tail ' + os.environ['TAVILY_API_KEY'][:9])\n"))
        self.assertEqual(held.stdout, b"tail " + PARTIAL)
        self.assert_never_echoed(plain.stdout, whole.stdout, held.stdout)

    def test_idle_flush_is_bounded(self):
        value = self.tavily()
        # A held tail of 3 bytes or less is written after about 100 ms without new data, while the child still runs;
        # the rest of the value is still masked when it arrives later.
        short = self.start_tool("tavily", *py(
            "import os, sys, time\nv = os.environ['TAVILY_API_KEY']\n"
            "sys.stdout.write(v[:3]); sys.stdout.flush(); time.sleep(3)\n"
            "sys.stdout.write(v[3:] + '\\n')\n"))
        started = time.monotonic()
        early = self.read_until(short.stdout, value[:3].encode(), seconds=2.5)
        self.assertEqual(early, value[:3].encode())
        self.assertLess(time.monotonic() - started, 2.5)
        rest, _ = short.communicate(timeout=30)
        self.assertEqual(early + rest, value[:3].encode() + MARK + b"\n")
        # A held tail of 4 bytes or more is never written on the idle timer.
        long = self.start_tool("tavily", *py(
            "import os, sys, time\nv = os.environ['TAVILY_API_KEY']\n"
            "sys.stdout.write('x' + v[:8]); sys.stdout.flush(); time.sleep(2.5)\nsys.stdout.write('\\n')\n"))
        first = self.read_until(long.stdout, b"never-arrives", seconds=1.5)
        self.assertEqual(first, b"x")
        rest, _ = long.communicate(timeout=30)
        self.assertEqual(first + rest, b"x" + value[:8].encode() + b"\n")  # released once the next byte ends the match

    def test_a_child_killed_mid_write_never_prints_a_held_partial(self):
        self.tavily()
        killed = self.run_tool("tavily", *py(
            "import os, signal, sys, time\nv = os.environ['TAVILY_API_KEY']\n"
            "sys.stdout.write('partial ' + v[:len(v) // 2]); sys.stdout.flush(); time.sleep(0.3)\n"
            "os.kill(os.getpid(), signal.SIGKILL)\n"))
        self.assertEqual(killed.returncode, 128 + signal.SIGKILL)
        self.assertEqual(killed.stdout, b"partial " + PARTIAL)
        # The runner itself is stopped: it forwards the signal, and the child's held partial is still never printed.
        runner = self.start_tool("tavily", *py(
            "import os, sys, time\nv = os.environ['TAVILY_API_KEY']\n"
            "sys.stdout.write('ready\\n' + v[:10]); sys.stdout.flush(); time.sleep(30)\n"))
        ready = self.read_until(runner.stdout, b"ready\n")
        time.sleep(0.3)
        runner.send_signal(signal.SIGTERM)
        rest, err = runner.communicate(timeout=30)
        self.assertEqual(runner.returncode, 128 + signal.SIGTERM)
        self.assertEqual(ready + rest, b"ready\n" + PARTIAL)
        self.assert_never_echoed(killed.stdout, killed.stderr, ready + rest, err)

    def test_non_utf8_bytes_pass_through_intact(self):
        self.tavily()
        result = self.run_tool("tavily", *py(
            "import os, sys\nv = os.environ['TAVILY_API_KEY'].encode()\n"
            "sys.stdout.buffer.write(b'\\xff\\xfex' + v + b'\\x80\\xc3\\x28\\n')\n"
            "sys.stderr.buffer.write(b'\\xed\\xa0\\x80' + v + b'\\x00\\n')\n"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"\xff\xfex" + MARK + b"\x80\xc3\x28\n")
        self.assertEqual(result.stderr, b"\xed\xa0\x80" + MARK + b"\x00\n")

    def test_masker_merges_overlaps_and_never_cuts_a_match(self):
        # In process: a complete short match inside a longer needle's partial is held with it, then masked as one.
        masker = run_mod.Masker([(b"abcdef", "SHORT"), (b"abcdefgh12", "LONG")])
        out = masker.feed(b"x abcdefgh1", 0.0)
        self.assertEqual(out, b"x ")
        out += masker.feed(b"2 y\n", 0.0)
        self.assertEqual(out, b"x [REDACTED:LONG] y\n")
        overlapping = run_mod.Masker([(b"abcdef", "A"), (b"defghi", "B")])
        self.assertEqual(overlapping.feed(b"<abcdefghi>\n", 0.0) + overlapping.close(), b"<[REDACTED:A]>\n")
        # A complete match that runs into a held tail is held with it (dotenvx safeBoundary): cutting there would mask
        # A and then print its last bytes "def" raw once "X" ends B's partial match.
        straddle = run_mod.Masker([(b"abcdef", "A"), (b"defghijk", "B")])
        self.assertEqual(straddle.feed(b"abcdefgh", 0.0) + straddle.feed(b"X\n", 0.0), b"[REDACTED:A]ghX\n")
        # After an idle flush of a short tail, the rest of the value is still masked.
        tail = run_mod.Masker([(b"abcdefgh", "K")])
        self.assertEqual(tail.feed(b"abc", 1.0), b"")
        self.assertEqual(tail.idle_due(), 1.0 + run_mod.IDLE_FLUSH_SECONDS)
        self.assertEqual(tail.idle_flush(), b"abc")
        self.assertEqual(tail.feed(b"defgh\n", 2.0), b"[REDACTED:K]\n")
        # A held tail of 4 bytes or more is never written, on the timer or at the end; a shorter one is, both ways.
        held = run_mod.Masker([(b"abcdefgh", "K")])
        self.assertEqual(held.feed(b"abcd", 1.0), b"")
        self.assertIsNone(held.idle_due())
        self.assertEqual(held.close(), b"[REDACTED-PARTIAL:K]")
        short = run_mod.Masker([(b"abcdefgh", "K")])
        self.assertEqual(short.feed(b"the end: abc", 1.0) + short.close(), b"the end: abc")
        continued = run_mod.Masker([(b"abcdefgh", "K")])
        self.assertEqual(continued.feed(b"abc", 1.0) + continued.idle_flush() + continued.feed(b"d", 2.0)
                         + continued.close(), b"abc[REDACTED-PARTIAL:K]")


class ProcessTests(RunnerCase):
    def test_exit_code_and_signal_propagate(self):
        self.tavily()
        self.assertEqual(self.run_tool("tavily", *py("raise SystemExit(7)")).returncode, 7)
        self.assertEqual(self.run_tool("tavily", *py(
            "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n")).returncode, 128 + signal.SIGTERM)
        for sig, code in ((signal.SIGTERM, 5), (signal.SIGINT, 6), (signal.SIGHUP, 8)):
            with self.subTest(signal=sig.name):
                runner = self.start_tool("tavily", *py(
                    "import signal, sys, time\n"
                    f"signal.signal({int(sig)}, lambda *_: (print('got {sig.name}', flush=True), sys.exit({code})))\n"
                    "print('ready', flush=True)\ntime.sleep(30)\n"))
                ready = self.read_until(runner.stdout, b"ready\n")
                runner.send_signal(sig)
                rest, _ = runner.communicate(timeout=30)
                self.assertEqual(runner.returncode, code)
                self.assertEqual(ready + rest, f"ready\ngot {sig.name}\n".encode())

    def test_stdin_passes_through(self):
        self.tavily()
        data = b"line one\n\xff\xfe\x00binary\nlast line without newline"
        result = self.run_tool("tavily", *py("import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n"),
                               input=data)
        self.assertEqual((result.returncode, result.stdout), (0, data))

    def test_a_descendant_holding_a_pipe_cannot_hang_the_runner(self):
        self.tavily()
        started = time.monotonic()
        result = self.run_tool("tavily", *py(
            "import subprocess, sys\n"
            "grandchild = subprocess.Popen(['sleep', '60'])\n"  # inherits the runner's pipes and keeps them open
            "print('grandchild', grandchild.pid, flush=True)\n"), timeout=45)
        elapsed = time.monotonic() - started
        pid = int(result.stdout.split()[1])
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 20)

    def test_child_runs_in_a_new_session_without_core_dumps(self):
        self.tavily()
        result = self.run_tool("tavily", *py(
            "import json, os, resource\n"
            "print(json.dumps([resource.getrlimit(resource.RLIMIT_CORE), os.getsid(0) == os.getpid()]))\n"))
        self.assertEqual(json.loads(result.stdout), [[0, 0], True])


class CheckAndIsolationTests(RunnerCase):
    def test_check_mode_prints_names_only(self):
        marker = self.base / "child-ran"
        missing = self.run_tool("tavily", "--check")
        self.assertEqual((missing.returncode, missing.stdout),
                         (1, b"tavily: missing (<store>/tavily.env); add it with: "
                             b"bash tools/credentials/open_credential_terminal.sh tavily\n"))
        self.tavily()
        ok = self.run_tool("tavily", "--check")
        self.assertEqual((ok.returncode, ok.stdout, ok.stderr),
                         (0, b"tavily: ok; would inject TAVILY_API_KEY (masked)\n", b""))
        self.alpaca()
        pair = self.run_tool("alpaca-paper", "--check")
        self.assertEqual(pair.stdout, b"alpaca-paper: ok; would inject APCA_API_KEY_ID (masked), "
                                      b"APCA_API_SECRET_KEY (masked), APCA_API_BASE_URL (public)\n")
        narrowed = self.run_tool("alpaca-paper", "--check", "--only", "APCA_API_KEY_ID")
        self.assertEqual(narrowed.stdout, b"alpaca-paper: ok; would inject APCA_API_KEY_ID (masked)\n")
        (self.store / "tavily.env").chmod(0o644)
        unsafe = self.run_tool("tavily", "--check")
        self.assertEqual((unsafe.returncode, unsafe.stdout), (1, b"tavily: unsafe (mode_not_0600)\n"))
        self.plant("tavily", "export TAVILY_API_KEY=$(id)\n")
        grammar = self.run_tool("tavily", "--check")
        self.assertEqual((grammar.returncode, grammar.stdout), (1, b"tavily: unsafe (line 1: outside_writer_grammar)\n"))
        engine = self.run_tool("grafana-admin", "--check")
        self.assertEqual(engine.returncode, 1)
        self.assertTrue(engine.stdout.startswith(b"grafana-admin: refused (not_injectable: "))
        # --check starts no command.
        self.assertEqual(self.run_tool("tavily", "--check", *py(f"open({str(marker)!r}, 'w').close()")).returncode, 2)
        self.assertFalse(marker.exists())
        self.assert_never_echoed(*(r.stdout + r.stderr for r in (missing, ok, pair, narrowed, unsafe, grammar, engine)))

    def test_messages_never_contain_values_or_paths(self):
        # Every refusal and every normal run, collected: no value, no piece of one, no store path, no store line.
        value = self.tavily()
        outputs = []
        scenarios = [("tavily", "--check"), ("tavily", *py("print('ok')")), ("tavily", "--", "/no/such/cmd"),
                     ("alpaca-paper", "--check"), ("alpaca-paper", "--", "true"), ("no-such", "--", "true")]
        for text in (f"export TAVILY_API_KEY={value} trailing\n", f"TAVILY_API_KEY={value}\n",
                     f"export TAVILY_API_KEY=\"{value}\n", f"export TAVILY_API_KEY={value[:5]}\n",
                     f"export OTHER_NAME={value}\n"):
            self.plant("tavily", text)
            for args in scenarios:
                result = self.run_tool(*args)
                outputs.extend((result.stdout, result.stderr))
        self.assert_never_echoed(*outputs)
        for text in outputs:
            self.assertIsNone(STORE_LINE.search(text))
            self.assertNotIn(b"native-agent-stack/", text)
        self.assertTrue(any(b"<store>/alpaca-paper.env" in text for text in outputs))

    @unittest.skipIf(HOST_PIPES_CORES, "the real re-execution is refused on a host that pipes crash dumps")
    def test_isolated_before_reading(self):
        # The first, non-isolated start runs a poisoned sitecustomize; it records every *.env open through an audit
        # hook. The runner must re-execute under -I -S before it opens the store, and the isolated run imports none
        # of the poisoned modules.
        value = self.tavily()
        poison, log = self.base / "poison", self.base / "poison.log"
        poison.mkdir()
        (poison / "sitecustomize.py").write_text(
            "import os, sys\n"
            f"LOG = {str(log)!r}\n"
            "with open(LOG, 'a') as f: f.write(f'start isolated={sys.flags.isolated}\\n')\n"
            "def hook(event, args):\n"
            "    if event == 'open' and str(args[0]).endswith('.env'):\n"
            "        with open(LOG, 'a') as f: f.write('opened a store file\\n')\n"
            "sys.addaudithook(hook)\n")
        for module in ("json", "selectors", "subprocess", "base64", "credential_status", "set_credential"):
            (poison / f"{module}.py").write_text(f"open({str(log)!r}, 'a').write('imported {module}\\n')\n")
        result = self.run_tool("tavily", *py(REPORT, '["TAVILY_API_KEY"]'), env={"PYTHONPATH": str(poison)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"TAVILY_API_KEY": sha(value)})
        self.assertEqual(log.read_text(), "start isolated=0\n")

    @unittest.skipIf(HOST_PIPES_CORES, "the real re-execution is refused on a host that pipes crash dumps")
    def test_site_packages_code_never_runs_in_the_reading_interpreter(self):
        # A .pth line of the interpreter's own site-packages runs even under -I; -S skips it. In a throwaway venv whose
        # site-packages this test may write (as tests/test_credential_tools.py does for set_credential.py), the line
        # records each start: only the first, non-isolated one may run it, never the re-executed one that reads.
        value = self.tavily()
        venv = self.base / "venv"
        made = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)],
                              capture_output=True, text=True, timeout=120)
        if made.returncode != 0:
            self.skipTest("python3 -m venv is not available")
        python = venv / "bin" / "python"
        purelib = subprocess.run([str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                                 capture_output=True, text=True, timeout=60, check=True).stdout.strip()
        record = self.base / "starts"
        Path(purelib, "zz_probe.pth").write_text(
            f"import sys; open({str(record)!r}, 'a').write('site ran, isolated=%d;' % sys.flags.isolated)\n")
        result = subprocess.run([str(python), str(TOOL), "tavily", *py(REPORT, '["TAVILY_API_KEY"]')],
                                stdin=subprocess.DEVNULL, capture_output=True, env=self.env, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"TAVILY_API_KEY": sha(value)})
        # A set of start kinds: a Linux venv reaches its site-packages twice (lib and the lib64 link), so one start
        # can run the line twice. Only the first, non-isolated start ran it; the -I -S interpreter never did.
        self.assertEqual({start for start in record.read_text().split(";") if start}, {"site ran, isolated=0"})


class CoreDumpTests(RunnerCase):
    """Review of 2026-09-29, finding 2: RLIMIT_CORE 0 stops a core file, not a collector. The kernel ignores the limit
    for a `|` pattern and for an `@` core socket (torvalds/linux@v6.16 fs/coredump.c L795-820, L242-243 and L919), and
    systemd-coredump then journals the crashing process's environment (systemd@v257 src/coredump/coredump.c L472-479
    and L1458-1459), so the runner refuses such a host. Patterns are files of these tests, never this host's."""

    PIPE = b"|/usr/lib/systemd/systemd-coredump %P %u %g %s %t %c %h\n"

    def pattern(self, text: bytes | None) -> Path:
        path = self.base / "pattern-under-test"
        if text is not None:
            path.write_bytes(text)
        return path

    def refusal(self, text: bytes | None) -> str:
        with self.assertRaises(run_mod.Refused) as caught:
            run_mod.check_core_pattern(str(self.pattern(text)))
        return str(caught.exception)

    def test_a_piped_or_socket_pattern_is_refused_without_naming_it(self):
        for text, reason in ((self.PIPE, "core_pattern_pipe"), (b"|/bin/true", "core_pattern_pipe"),
                             (b"|", "core_pattern_pipe"), (b"@/run/systemd/coredump.socket\n", "core_pattern_socket"),
                             (b"@@/run/systemd/coredump\n", "core_pattern_socket")):
            with self.subTest(pattern=text[:12]):
                message = self.refusal(text)
                self.assertTrue(message.startswith(reason + ": "), message)
                self.assertIn("inspect /proc/sys/kernel/core_pattern", message)
                self.assertNotIn("systemd", message)  # never a value of the file

    def test_file_patterns_and_a_missing_file_are_accepted(self):
        for text in (b"core", b"core\n", b"core.%p", b"/var/crash/core.%e.%p.%t\n", b"", b"core|not-a-pipe",
                     b" |only the first byte counts"):
            with self.subTest(pattern=text[:12]):
                run_mod.check_core_pattern(str(self.pattern(text)))
        run_mod.check_core_pattern(str(self.base / "no" / "such" / "core_pattern"))  # macOS: no /proc at all
        run_mod.check_core_pattern(str(self.pattern(b"core") / "not-a-directory"))

    def test_an_unreadable_pattern_file_is_refused(self):
        directory = self.base / "a-directory"  # exists, but cannot be read as a file (also refused when run as root)
        directory.mkdir()
        with self.assertRaises(run_mod.Refused) as caught:
            run_mod.check_core_pattern(str(directory))
        self.assertTrue(str(caught.exception).startswith("core_pattern_unreadable: "))
        self.assertIn("inspect that file", str(caught.exception))
        self.assertIn("/proc/sys/kernel/core_pattern", str(caught.exception))

    def main_in_process(self, *args: str, pattern: bytes = b"core\n"):
        """run_mod.main(args) with the store and the core_pattern path of this test: (code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env), \
                mock.patch.object(run_mod, "CORE_PATTERN_FILE", str(self.pattern(pattern))), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run_mod.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_a_refused_host_never_reads_the_store_or_starts_the_command(self):
        self.tavily()
        marker = self.base / "child-ran"
        child = py(f"open({str(marker)!r}, 'w').close()")
        secret_path = self.store / "tavily.env"
        with mock.patch.object(run_mod, "read_store", side_effect=AssertionError("the store was read")):
            for text, reason in ((self.PIPE, "core_pattern_pipe"), (b"@/run/x.socket", "core_pattern_socket")):
                code, out, err = self.main_in_process("tavily", *child, pattern=text)
                self.assertEqual(code, 1, err)
                self.assertIn(f"credential_run: tavily: refused: {reason}: ", err)
                self.assertNotIn("systemd", out + err)
                self.assertNotIn(str(secret_path), out + err)
                code, out, err = self.main_in_process("tavily", "--check", pattern=text)
                self.assertEqual((code, err), (1, ""))
                self.assertTrue(out.startswith(f"tavily: refused ({reason}: "), out)
        self.assertFalse(marker.exists(), "a refused run started its command")

    def test_a_limit_that_cannot_be_set_is_refused(self):
        self.tavily()
        marker = self.base / "child-ran"
        for failure in (OSError(1, "Operation not permitted"), ValueError("current limit exceeds maximum limit")):
            with self.subTest(failure=type(failure).__name__), \
                    mock.patch.object(run_mod.resource, "setrlimit", side_effect=failure):
                code, out, err = self.main_in_process("tavily", *py(f"open({str(marker)!r}, 'w').close()"))
                self.assertEqual(code, 1, err)
                self.assertIn("credential_run: tavily: refused: core_limit_not_set: ", err)
                self.assertNotIn("Operation not permitted", out + err)
        self.assertFalse(marker.exists(), "a refused run started its command")

    def test_the_real_tool_follows_this_hosts_own_pattern(self):
        # The real /proc file through the real tool, no launcher: a collector host is refused with the file named,
        # any other host starts (--check reads the pattern before the store, as a run does).
        self.tavily()
        real = subprocess.run([sys.executable, str(TOOL), "tavily", "--check"], stdin=subprocess.DEVNULL,
                              capture_output=True, env=self.env, timeout=60)
        self.assertEqual(real.stderr, b"")
        if _host_hands_cores_to_a_collector():
            self.assertEqual(real.returncode, 1)
            self.assertRegex(real.stdout, rb"^tavily: refused \(core_pattern_(pipe|socket): ")
            self.assertIn(b"inspect /proc/sys/kernel/core_pattern", real.stdout)
        else:
            self.assertEqual((real.returncode, real.stdout), (0, b"tavily: ok; would inject TAVILY_API_KEY (masked)\n"))


class StandardDescriptorTests(RunnerCase):
    """Review of 2026-09-29, finding 7: a standard descriptor closed at start is reopened on /dev/null, and the command
    must inherit it (os.open's descriptor is close-on-exec, which the exec would close again: EBADF, not EOF)."""

    def start_with_closed(self, redirect: str, code: str) -> subprocess.CompletedProcess:
        command = ["/bin/sh", "-c", f'exec "$@" {redirect}', "sh", *self.command("tavily", *py(code))]
        return subprocess.run(command, capture_output=True, env=self.tool_environment(), timeout=60)

    def test_a_closed_stdin_reads_end_of_file_in_the_command(self):
        self.tavily()
        result = self.start_with_closed("<&-", (
            "import os\ntry:\n    print('eof' if os.read(0, 8) == b'' else 'data')\n"
            "except OSError as error:\n    print('errno', error.errno)\n"))
        self.assertEqual((result.returncode, result.stdout), (0, b"eof\n"), result.stderr)

    def test_a_closed_stdout_or_stderr_leaves_the_other_stream_relayed(self):
        self.tavily()
        both = "import sys\nsys.stdout.write('out\\n')\nsys.stderr.write('err\\n')\n"
        closed_out = self.start_with_closed(">&-", both)
        self.assertEqual((closed_out.returncode, closed_out.stdout, closed_out.stderr), (0, b"", b"err\n"))
        closed_err = self.start_with_closed("2>&-", both)
        self.assertEqual((closed_err.returncode, closed_err.stdout, closed_err.stderr), (0, b"out\n", b""))


class InventoryAndGrammarTests(unittest.TestCase):
    def test_every_injected_name_is_masked_or_public(self):
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text(encoding="utf-8"))
        injectable, classified = set(), {}
        for entry in inventory["entries"]:
            if not run_mod.injectable(entry):
                continue
            injectable.add(entry["id"])
            injected = entry["variables"] + entry["optional_variables"]
            public = entry.get("public_variables", [])
            masked = run_mod.masked_names(entry)
            with self.subTest(id=entry["id"]):
                self.assertEqual(sorted(masked + public), sorted(injected))
                self.assertEqual(set(masked) & set(public), set())
                self.assertLessEqual(set(entry["variables"]), set(masked))  # a required variable is always masked
                values = {name: fake("v-") for name in injected}
                self.assertEqual({name for _needle, name in run_mod.needles_for(values, masked)}, set(masked))
            classified.update({(entry["id"], name): "public" if name in public else "masked"
                               for name in entry["optional_variables"]})
        self.assertEqual(injectable, INJECTABLE_IDS)
        # Every optional variable of an injectable entry, classified; a new one must be reviewed here.
        self.assertEqual(classified, {("alpaca-paper", "APCA_API_BASE_URL"): "public",
                                      ("alpaca-paper-2", "APCA_API_BASE_URL"): "public",
                                      ("sec-contact", "EDGAR_IDENTITY"): "masked"})

    def test_a_required_variable_is_masked_even_when_a_planted_entry_lists_it_public(self):
        # Review of 2026-09-29: masked_names() trusted public_variables as written. It now comes from the schema
        # module, where a public name is only ever an optional variable that is not also required.
        entry = {"variables": ["KEY_ID", "SECRET_KEY"], "optional_variables": ["BASE_URL", "KEY_ID"],
                 "public_variables": ["BASE_URL", "KEY_ID", "SECRET_KEY", "NOT_DECLARED"]}
        self.assertEqual(run_mod.masked_names(entry), ["KEY_ID", "SECRET_KEY"])
        self.assertEqual(run_mod.public_names(entry), ["BASE_URL"])

    def test_writer_and_reader_share_one_grammar(self):
        entry = {"id": "tavily", "variables": ["TAVILY_API_KEY"], "optional_variables": []}
        candidates = ["plain-Value_1.2+3/4=5:6@7", "with space inside", "semi;colon", "tilde~home", "quote'single",
                      "dollar$sign", "back`tick", "back\\slash", 'double"quote', " padded", "tab\there", "caf\u00e9",
                      "bell\x07"]
        for value in candidates:
            with self.subTest(value=value):
                try:
                    line = writer.encode("TAVILY_API_KEY", value)
                except writer.Refused:
                    for text in (f"export TAVILY_API_KEY={value}\n", f'export TAVILY_API_KEY="{value}"\n'):
                        with self.assertRaises(run_mod.Refused):
                            run_mod.parse("tavily", text.encode("utf-8"), entry)
                else:
                    self.assertEqual(run_mod.parse("tavily", line.encode("ascii"), entry), {"TAVILY_API_KEY": value})

    def test_grammar_is_python_3_9_compatible(self):
        # The Claude hook and a Mac's Command Line Tools python3 may be 3.9 (docs/decisions/2026-09-29-key-management.md).
        ast.parse(TOOL.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_unexpected_errors_print_only_the_type(self):
        secret = fake("tvly-")
        err = io.StringIO()
        with mock.patch.object(run_mod, "read_store", side_effect=RuntimeError(f"boom {secret}")), \
                mock.patch.object(run_mod, "disable_core_dumps"), contextlib.redirect_stderr(err):
            code = run_mod.main(["tavily", "--", "true"])
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", err.getvalue())
        self.assertIn("internal_error", err.getvalue())
        self.assertNotIn(secret, err.getvalue())
        self.assertNotIn("boom", err.getvalue())


if __name__ == "__main__":
    unittest.main()
