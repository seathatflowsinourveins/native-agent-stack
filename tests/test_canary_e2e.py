"""Tests for the canary proof: tools/credentials/canary_e2e.py, canary_probe.py, canary_sinks.json and canary_workflow.js.

Local integration checks, not upstream acceptance (docs/acceptance-evidence-policy.md). Every canary, decoy, key and
sentinel is a synthetic value made at test time. The store, the run directory, the receipts and every sink live in
temporary directories named through XDG overrides inside the test process only. The consumers (claude, codex,
systemd-run) and journalctl, systemd-cat, systemctl and gh are stub executables first on PATH, and /proc is a fixture
directory. No test starts a Claude, Codex or OmniRoute session, calls the keyring, or reads a real store, journal, Loki,
RTK or ai-memory database; the stubs run the real key runner and the real probe against the temporary store. The
repair tests (review of 2026-09-29) each hold a synthetic false-zero fixture that passed before its fix and must now
make the scan or the report fail.
"""
from __future__ import annotations

import ast
import base64
import copy
import gzip
import hashlib
import http.server
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "credentials"
sys.path.insert(0, str(TOOLS))
import canary_e2e as harness  # noqa: E402
import canary_probe as probe  # noqa: E402
import credential_run as run_mod  # noqa: E402


def _load_guard():
    spec = importlib.util.spec_from_file_location("secret_path_guard_for_canary", ROOT / "scripts/hooks/secret_path_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()
HAS_RG = shutil.which("rg") is not None
HAS_GIT = shutil.which("git") is not None
SAMPLE_RUN = "canary-20260929t031500z-a1b2c3"


def _host_hands_cores_to_a_collector() -> bool:
    try:
        with open("/proc/sys/kernel/core_pattern", "rb") as handle:
            return handle.read(1) in (b"|", b"@")
    except OSError:
        return False


# As in tests/test_credential_run.py: the runner, and now the harness, refuse a host that pipes crash dumps, so there the
# stubs start them through launchers that point CORE_PATTERN_FILE at a temporary file holding "core".
HOST_PIPES_CORES = os.environ.get("CREDENTIAL_RUN_TEST_LAUNCHER") == "1" or _host_hands_cores_to_a_collector()
LAUNCHER = ("import os, sys\n"
            f"sys.path[:0] = [{str(TOOLS)!r}, {str(ROOT / 'scripts')!r}]\n"
            "import credential_run\n"
            "credential_run.CORE_PATTERN_FILE = os.environ.pop('CORE_PATTERN_TEST_FILE')\n"
            "sys.exit(credential_run.main(sys.argv[1:]))\n")
# The harness in a subprocess, with the test's sink table and /proc fixture (named by two variables that only this
# launcher reads; the harness has no such switch).
HARNESS_LAUNCHER = ("import os, sys\n"
                    f"sys.path[:0] = [{str(TOOLS)!r}, {str(ROOT / 'scripts')!r}]\n"
                    "import credential_run, canary_e2e\n"
                    "if os.environ.get('CORE_PATTERN_TEST_FILE'):\n"
                    "    credential_run.CORE_PATTERN_FILE = os.environ['CORE_PATTERN_TEST_FILE']\n"
                    "sys.exit(canary_e2e.main(sys.argv[1:], canary_e2e.Context(\n"
                    "    sinks_path=os.environ['CANARY_TEST_SINKS'], proc_root=os.environ['CANARY_TEST_PROC'])))\n")
# A command for the runner that records its environment by name and sha256 only: the probe's environment, observed.
RECORD_ENV = ("import hashlib, json, os, sys\n"
              "open(sys.argv[1], 'w').write(json.dumps({n: hashlib.sha256(v.encode()).hexdigest()\n"
              "                                          for n, v in os.environ.items()}))\n")

STUB_HELPER = r'''
import gzip, hashlib, json, os, re, sqlite3, subprocess, sys, time
TOOLS = @TOOLS@
LAUNCHER = @LAUNCHER@
HARNESS_LAUNCHER = @HARNESS_LAUNCHER@
RECORD_ENV = @RECORD_ENV@
RUN = re.compile(r"--run (canary-[0-9]{8}t[0-9]{6}z-[0-9a-f]{6})")
ECHO = re.compile(r"echo (DCOYE2E[0-9a-f]{32}) && false")
RTK = re.compile(r"--rtk (DCOYE2E[0-9a-f]{32})")

def runner_argv(*command):
    if os.environ.get("CORE_PATTERN_TEST_FILE"):
        return [sys.executable, "-I", "-S", "-c", LAUNCHER, "canary-e2e", "--", *command]
    return [sys.executable, "-I", TOOLS + "/credential_run.py", "canary-e2e", "--", *command]

def run_probe(consumer, run):
    command = [sys.executable, "-I", TOOLS + "/canary_probe.py", "--run", run, "--consumer", consumer]
    result = subprocess.run(runner_argv(*command), capture_output=True, text=True, timeout=60)
    return result.stdout + result.stderr

def probe_environment(label):
    path = os.path.join(os.environ["HOME"], "stub-env", label + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(runner_argv(sys.executable, "-I", "-c", RECORD_ENV, path), capture_output=True, timeout=60)

def harness(*args):
    return subprocess.run([sys.executable, "-I", "-c", HARNESS_LAUNCHER, *args], capture_output=True, text=True,
                          timeout=60)

def harness_decoy(consumer, run):
    return harness("decoy", "--run", run, "--consumer", consumer).stdout.strip().split(": ", 1)[1]

def store_path():
    return os.path.join(os.environ["XDG_CONFIG_HOME"], "native-agent-stack", "canary-e2e.env")

def store_digest():
    try:
        with open(store_path(), "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None

def wait_for_change(before, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        now = store_digest()
        if now is not None and now != before:
            return True
        time.sleep(0.02)
    return False

def record(name, text):
    path = os.path.join(os.environ["HOME"], name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as handle:
        handle.write(text + "\n")

def later(name, text, delay):
    code = "import os, sys, time\ntime.sleep(float(sys.argv[3]))\nos.makedirs(os.path.dirname(sys.argv[1]), exist_ok=True)\nopen(sys.argv[1], 'a').write(sys.argv[2] + '\\n')\n"
    subprocess.Popen([sys.executable, "-c", code, os.path.join(os.environ["HOME"], name), text, str(delay)],
                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def record_env(label):
    path = os.path.join(os.environ["HOME"], "stub-env", label + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(json.dumps({n: hashlib.sha256(v.encode()).hexdigest() for n, v in os.environ.items()}))

def write_recall(command, output):
    path = os.path.join(os.environ["HOME"], "rtk", "recall.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS recall (hash TEXT, command TEXT, codec TEXT, blob BLOB)")
        connection.execute("INSERT INTO recall VALUES (?, ?, ?, ?)", ("h", command, "gzip", gzip.compress(output.encode())))
    connection.close()

def flag(name):
    return os.path.exists(os.path.join(os.environ["HOME"], name))
'''

STUB_CLAUDE = r'''
import json, os, sys, time
sys.path.insert(0, @BIN@)
from _stubs import *
if sys.argv[1:2] == ["--version"]:
    print("2.1.284 (Claude Code)")
    raise SystemExit(0)
record_env("fresh-claude-session")
if flag("slow-claude"):
    record("claude.pid", str(os.getpid()))
    time.sleep(120)
prompt = sys.stdin.read()
run = RUN.search(prompt).group(1)
decoy = ECHO.search(prompt).group(1)
rtk_decoy = RTK.search(prompt)
lines = []
def emit(obj):
    text = json.dumps(obj)
    lines.append(text)
    print(text, flush=True)
emit({"type": "system", "subtype": "init", "model": "claude-sonnet-5-5-stub", "session_id": "s1"})
emit({"type": "user", "message": {"content": [{"type": "tool_result", "content": decoy, "is_error": True}]}})
if rtk_decoy:  # the `rtk err ... decoy --rtk` step, as RTK would record it
    rtk = harness("decoy", "--run", run, "--consumer", "fresh-claude-session", "--rtk", rtk_decoy.group(1))
    write_recall("python3 tools/credentials/canary_e2e.py decoy --rtk " + rtk_decoy.group(1), rtk.stdout)
    emit({"type": "user", "message": {"content": [{"type": "tool_result", "content": rtk.stdout[-200:], "is_error": True}]}})
before = store_digest()
emit({"type": "user", "message": {"content": [{"type": "tool_result", "content": run_probe("fresh-claude-session", run)}]}})
probe_environment("probe-environment")
if not wait_for_change(before):
    raise SystemExit(9)
sub_decoy = harness_decoy("subagent", run)
sub = [json.dumps({"type": "user", "parent_tool_use_id": "t1", "message": {"content": [{"type": "tool_result", "content": sub_decoy}]}})]
sub_out = run_probe("subagent", run)
emit({"type": "assistant", "parent_tool_use_id": "t1", "message": {"model": "claude-sonnet-5-5-stub-sub", "content": [{"type": "text", "text": sub_out}]}})
emit({"type": "result", "subtype": "success"})
record("transcripts/session.jsonl", "\n".join(lines))
record("transcripts/subagents/agent.jsonl", "\n".join(sub))
later("async/archive.txt", decoy, 0.4)
'''

STUB_CODEX = r'''
import json, sys
sys.path.insert(0, @BIN@)
from _stubs import *
if sys.argv[1:2] == ["--version"]:
    print("codex-cli 0.157.1")
    raise SystemExit(0)
args = sys.argv[1:]
prompt = sys.stdin.read() if args[-1] == "-" else args[-1]
run = RUN.search(prompt).group(1)
consumer = "omniroute-lane" if "-p" in args else "codex-exec"
decoy = ECHO.search(prompt).group(1)
record_env(consumer)
if flag("careless-codex"):  # a client that logs the key it can see on its own stderr
    with open(store_path()) as handle:
        sys.stderr.write("debug: " + handle.read())
lines = [json.dumps({"type": "thread.started", "thread_id": "t"}),
         json.dumps({"type": "item.completed", "item": {"type": "command_execution", "aggregated_output": decoy + "\n", "exit_code": 1}}),
         json.dumps({"type": "item.completed", "item": {"type": "command_execution", "aggregated_output": run_probe(consumer, run), "exit_code": 0}}),
         json.dumps({"type": "turn.completed", "usage": {}})]
for line in lines:
    print(line, flush=True)
record("codex/sessions/rollout-" + consumer + ".jsonl", "\n".join(lines))
if consumer == "omniroute-lane":
    record("omni-data/call_logs.txt", prompt)
'''

STUB_SYSTEMD_RUN = r'''
import os, sys
sys.path.insert(0, @BIN@)
from _stubs import *
record_env("systemd-run")
args = sys.argv[1:]
index = 0
while index < len(args) and args[index].startswith("-"):
    index += 2 if args[index] == "-p" else 1
command = args[index:]
if os.environ.get("CORE_PATTERN_TEST_FILE"):
    command = [sys.executable, "-I", "-S", "-c", LAUNCHER] + command[3:]
os.execv(command[0], command)
'''

STUB_JOURNALCTL = r'''
import os, sys
sys.path.insert(0, @BIN@)
from _stubs import *
if "--version" in sys.argv:
    print("systemd 255 (255.4-1ubuntu8.17)")
    raise SystemExit(0)
record_env("journalctl")
if flag("journal-fails"):
    raise SystemExit(1)
try:
    with open(os.environ["CANARY_TEST_JOURNAL"], "rb") as handle:
        sys.stdout.buffer.write(handle.read())
except FileNotFoundError:
    pass
'''

STUB_SYSTEMD_CAT = r'''
import os, sys
data = sys.stdin.read()
with open(os.environ["CANARY_TEST_JOURNAL"], "a") as handle:
    for line in data.splitlines():
        handle.write("__CURSOR=s\nSYSLOG_IDENTIFIER=canary\nMESSAGE=" + line + "\n\n")
'''

STUB_SYSTEMCTL = r'''
import os, sys
sys.path.insert(0, @BIN@)
from _stubs import *
if "--version" in sys.argv:
    print("systemd 255 (255.4-1ubuntu8.17)")
elif "show-environment" in sys.argv:
    record_env("systemctl")
    print("HOME=/home/example\nPATH=/usr/bin\nLANG=C.UTF-8")
    if flag("manager-has-canary-name"):
        print("CANARY_E2E_KEY=not-a-value-the-scanner-reads")
'''

STUB_GH = r'''
import sys
sys.path.insert(0, @BIN@)
from _stubs import *
record_env("gh")
print("[]")
'''


def stable_interiors(raw: bytes) -> list:
    """The base64 and base64url characters that depend only on raw, at each byte alignment (this test's own copy)."""
    found = []
    for altchars in (None, b"-_"):
        for align in (0, 1, 2):
            encoded = base64.b64encode(b"\0" * align + raw, altchars=altchars)
            found.append(encoded[(0, 2, 3)[align]:(8 * (align + len(raw))) // 6])
    return found


def secret_forms(value: str) -> list:
    """The forms no harness output, receipt or stderr may hold: raw, base64 (whole and stable interiors), hex, percent."""
    raw = value.encode("ascii")
    forms = [raw, base64.b64encode(raw), base64.urlsafe_b64encode(raw), raw.hex().encode(), raw.hex().upper().encode(),
             urllib.parse.quote(value, safe="").encode(), urllib.parse.quote(value, safe="").lower().encode(),
             urllib.parse.quote_plus(value).encode()]
    return forms + stable_interiors(raw)


def inventory_sentinels() -> dict:
    """A synthetic value under every inventory variable, every must_not_be_set name and every pointer variable."""
    inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text())
    names = set(inventory["must_not_be_set"])
    for entry in inventory["entries"]:
        names.update(entry["variables"], entry["optional_variables"], entry["pointer_variables"])
    return {name: f"SENTINEL-{name}-" + os.urandom(6).hex() for name in sorted(names)}


class CanaryCase(unittest.TestCase):
    """A temporary host: home, XDG directories, a 0700 runtime directory, stub executables and a fixture /proc. Its
    environment carries a sentinel under every inventory, must_not_be_set and pointer name, which no environment the
    harness builds may keep."""

    maxDiff = None

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home = self.base / "home"
        self.config = self.home / ".config"
        self.state = self.home / ".local" / "state"
        self.runtime = self.base / "runtime"
        self.codex_home = self.home / ".codex"
        self.bin = self.base / "bin"
        self.proc = self.base / "proc"
        for directory in (self.home, self.config, self.state, self.runtime, self.codex_home, self.bin, self.proc):
            directory.mkdir(parents=True, exist_ok=True)
        self.runtime.chmod(0o700)
        self.journal = self.base / "journal.export"
        self.core_pattern = self.base / "core_pattern"
        self.core_pattern.write_text("core\n")
        self.sinks_file = self.base / "sinks.json"
        self.sentinels = inventory_sentinels()
        self.env = {"PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", "HOME": str(self.home),
                    "XDG_CONFIG_HOME": str(self.config), "XDG_STATE_HOME": str(self.state),
                    "XDG_RUNTIME_DIR": str(self.runtime), "XDG_DATA_HOME": str(self.home / ".local" / "share"),
                    "XDG_CACHE_HOME": str(self.home / ".cache"), "CODEX_HOME": str(self.codex_home),
                    "CANARY_TEST_JOURNAL": str(self.journal), "CANARY_TEST_SINKS": str(self.sinks_file),
                    "CANARY_TEST_PROC": str(self.proc), "LANG": "C.UTF-8", **self.sentinels}
        if HOST_PIPES_CORES:
            self.env["CORE_PATTERN_TEST_FILE"] = str(self.core_pattern)
            patcher = mock.patch.object(run_mod, "CORE_PATTERN_FILE", str(self.core_pattern))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.outputs: list = []
        self.write_stubs()
        self.write_sinks(self.default_sinks())
        self.clock_offset = 0.0

    # -- fixtures ------------------------------------------------------------------------------------------------------

    def write_stubs(self):
        helper = (STUB_HELPER.replace("@TOOLS@", repr(str(TOOLS))).replace("@LAUNCHER@", repr(LAUNCHER))
                  .replace("@HARNESS_LAUNCHER@", repr(HARNESS_LAUNCHER)).replace("@RECORD_ENV@", repr(RECORD_ENV)))
        (self.bin / "_stubs.py").write_text(helper)
        for name, body in (("claude", STUB_CLAUDE), ("codex", STUB_CODEX), ("systemd-run", STUB_SYSTEMD_RUN),
                           ("journalctl", STUB_JOURNALCTL), ("systemd-cat", STUB_SYSTEMD_CAT),
                           ("systemctl", STUB_SYSTEMCTL), ("gh", STUB_GH)):
            path = self.bin / name
            path.write_text(f"#!{sys.executable}\n" + body.replace("@BIN@", repr(str(self.bin))))
            path.chmod(0o755)

    def sink(self, identifier, kind, paths=(), controls=(), access="agent", **extra):
        row = {"id": identifier, "kind": kind, "access": access, "paths": list(paths), "path_class": f"test/{identifier}",
               "persisted": True, "controls": list(controls), "async": False, "retention": "test", "fact": "test"}
        row.update(extra)
        return row

    def default_sinks(self):
        return [self.sink("T01-transcripts", "files", ["$HOME/transcripts"], ["claude", "subagent"]),
                self.sink("T02-rollouts", "files", ["$HOME/codex/sessions"], ["codex", "omni"]),
                self.sink("T03-archive", "files", ["$HOME/async"], ["claude"], **{"async": True}),
                self.sink("T04-journal", "journal", [], ["journal"], scope="user"),
                self.sink("T05-databases", "sqlite", ["$HOME/dbs"]),
                self.sink("T06-repository", "git", ["$HOME/repo"]),
                self.sink("T07-call-logs", "files", ["$HOME/omni-data"], ["omni"], access="user_run"),
                self.sink("T08-manager", "manager_environment", access="user_run", persisted=False),
                self.sink("T09-github", "github"),
                self.sink("T10-remote", "not_scanned", access="not_scanned"),
                self.sink("T11-covered", "covered"),
                self.sink("T12-proc", "during_consume", persisted=False),
                self.sink("T13-absent", "files", ["$HOME/no-such-directory"]),
                self.sink("T14-sudo-only", "files", ["$HOME/sudo-only"], access="sudo"),
                self.sink("T15-rtk-recall", "sqlite", ["$HOME/rtk/recall.db*"], ["rtk"], control_in="decoded_blobs")]

    def write_sinks(self, sinks, exclude=()):
        table = {"schema_version": 1, "kind": "canary_sink_table",
                 "exclude": ["${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack", "$HOME/.ssh", *exclude],
                 "exclude_names": ["shell_snapshots", "config.v2.json"], "sinks": sinks}
        self.sinks_file.write_text(json.dumps(table))

    def context(self, tty=False):
        out, err = io.StringIO(), io.StringIO()
        self.outputs.append((out, err))
        return harness.Context(self.env, sinks_path=self.sinks_file, proc_root=self.proc, out=out, err=err,
                               clock=lambda: time.time() + self.clock_offset, tty=lambda: tty)

    def harness(self, *argv, tty=False):
        """(exit code, stdout, stderr) of one subcommand run in process."""
        context = self.context(tty=tty)
        code = harness.main(list(argv), context)
        return code, context.out.getvalue(), context.err.getvalue()

    def launch(self, *argv) -> subprocess.Popen:
        """The harness in a subprocess, with this test's table and /proc fixture."""
        process = subprocess.Popen([sys.executable, "-I", "-c", HARNESS_LAUNCHER, *argv], env=self.env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def reap():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=30)

        self.addCleanup(reap)
        return process

    def prepare(self, *extra):
        code, out, err = self.harness("prepare", *extra)
        self.assertEqual(code, 0, out + err)
        run = out.strip()
        self.assertRegex(run, r"^canary-[0-9]{8}t[0-9]{6}z-[0-9a-f]{6}$")
        return run

    def run_dir(self, run):
        for directory in probe.run_directories(run, self.env):
            if directory.is_dir():
                return directory
        self.fail("no run directory")

    def canary(self, run, consumer):
        return (self.run_dir(run) / "patterns" / f"c-{consumer}.pat").read_text().split("\n", 1)[0]

    def decoy(self, run, name):
        return (self.run_dir(run) / "patterns" / f"d-{name}.pat").read_text().split("\n", 1)[0]

    def store_file(self):
        return self.config / "native-agent-stack" / "canary-e2e.env"

    def codex_config(self, base=False, profile=False):
        (self.codex_home / "config.toml").write_text(f"[features]\nshell_snapshot = {str(base).lower()}\n")
        (self.codex_home / "omniroute.config.toml").write_text(f"[features]\nshell_snapshot = {str(profile).lower()}\n")

    def ran(self, run, consumer, **extra):
        """A consume record for a consumer that ran (planting its decoy), as a scan-only test needs."""
        record = {"ran": True, "started_epoch": time.time() - 10, "ended_epoch": time.time() - 5, "sequence": 1}
        record.update(extra)
        harness.write_json(self.run_dir(run) / "results" / f"consume-{consumer}.json", record)

    def all_output(self) -> str:
        return "".join(out.getvalue() + err.getvalue() for out, err in self.outputs)

    def forbidden(self, run) -> list:
        """Every canary form, and every tag and tag prefix that any probe wrote, for this run."""
        found = []
        for consumer in probe.CONSUMERS:
            found += secret_forms(self.canary(run, consumer))
        for tag_file in (self.run_dir(run) / "tags").glob("*.tag"):
            full = tag_file.read_text().strip()
            found += [full.encode(), full[:16].encode()]
        return found

    def assert_value_free(self, forbidden, *texts):
        for text in texts:
            data = text if isinstance(text, bytes) else text.encode("utf-8", "surrogateescape")
            for form in forbidden:
                self.assertNotIn(form, data)


class PatternAndTagTests(CanaryCase):
    def test_patterns_cover_raw_base64_alignments_and_hex(self):
        canary = harness.new_canary()
        self.assertRegex(canary, r"^CNRYE2E[0-9a-f+/=]{35}$")
        for symbol in "+/=":
            self.assertEqual(canary.count(symbol), 1)
        self.assertIsNotNone(harness.writer.BARE_VALUE.match(canary))  # the store writer's bare grammar
        patterns = harness.forms(canary)
        raw = canary.encode()
        self.assertEqual(patterns[0], raw)
        percent = urllib.parse.quote(canary, safe="")
        for form in stable_interiors(raw) + [raw.hex().encode(), raw.hex().upper().encode(), percent.encode(),
                                             re.sub(r"%[0-9A-F]{2}", lambda m: m.group(0).lower(), percent).encode(),
                                             urllib.parse.quote(canary).encode(),
                                             json.dumps(canary)[1:-1].replace("/", "\\/").encode()]:
            self.assertIn(form, patterns)
        self.assertEqual(len(patterns), len(set(patterns)))
        self.assertTrue(all(len(p) >= run_mod.LENGTH_MIN and b"\n" not in p for p in patterns))
        # the scanned forms are the forms the runner masks: every needle of the runner is a pattern
        self.assertEqual({n for n, _ in run_mod.needles_for({"V": canary}, ["V"])}, set(patterns))
        self.assertNotEqual(harness.new_canary(), canary)
        self.assertRegex(harness.new_decoy(), r"^DCOYE2E[0-9a-f]{32}$")

    def test_matcher_prefilter_never_hides_a_pattern(self):
        sets = {f"c-{i}": harness.forms(harness.new_canary()) for i in range(6)}
        sets["d-x"] = harness.forms(harness.new_decoy())
        matcher = harness.Matcher(sets)
        self.assertTrue(matcher.anchors)  # the prefilter is on
        for name, patterns in sets.items():
            for pattern in patterns:
                self.assertEqual(matcher.hits(b"<" + pattern + b">"), {name})
        self.assertEqual(matcher.hits(b"CNRYE2E but nothing else"), set())

    def test_prepare_makes_independent_private_canaries_and_prints_only_the_run_id(self):
        run = self.prepare()
        directory = self.run_dir(run)
        self.assertEqual(directory.parent, self.runtime / "native-agent-stack" / "canary")
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        canaries = [self.canary(run, consumer) for consumer in probe.CONSUMERS]
        self.assertEqual(len(set(canaries)), 6)
        nonces = [(directory / "nonce" / consumer).read_text().strip() for consumer in probe.CONSUMERS]
        self.assertEqual(len(set(nonces)), 6)
        for path in (directory / "patterns").iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path.name)
        self.assertFalse(self.store_file().exists())  # nothing is armed yet
        self.assertEqual(self.all_output().strip(), run)
        self.assert_value_free(self.forbidden(run), self.all_output())

    @unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
    def test_harness_messages_never_contain_the_canary(self):
        run = self.prepare()
        for step in (("controls", "--run", run), ("baseline", "--run", run), ("decoy", "--run", run, "--consumer",
                     "subagent"), ("verify", "--run", run), ("scan", "--sink", "T01-transcripts", "--run", run)):
            self.harness(*step)
        self.assert_value_free(self.forbidden(run), self.all_output())
        self.assertIn(f"decoy subagent: {self.decoy(run, 'subagent')}", self.all_output())  # decoys are meant to show
        # the last line of defence: a line that holds canary material is withheld, whatever produced it
        context = self.context()
        context.hold(harness.load_sets(self.run_dir(run))["c-codex-exec"])
        context.say("careless " + base64.b64encode(b"us" + self.canary(run, "codex-exec").encode()).decode())
        context.warn("ordinary line")
        self.assertEqual(context.out.getvalue(), "[line withheld: it held canary material]\n")
        self.assertEqual(context.err.getvalue(), "ordinary line\n")

    def test_hmac_tag_binds_run_and_consumer(self):
        canary, nonce = harness.new_canary(), "0" * 32
        base = probe.tag(canary, SAMPLE_RUN, "codex-exec", nonce)
        self.assertEqual(len(base), 64)
        for changed in (probe.tag(canary, "canary-20260929t031500z-000000", "codex-exec", nonce),
                        probe.tag(canary, SAMPLE_RUN, "omniroute-lane", nonce),
                        probe.tag(canary, SAMPLE_RUN, "codex-exec", "1" * 32),
                        probe.tag(harness.new_canary(), SAMPLE_RUN, "codex-exec", nonce)):
            self.assertNotEqual(changed, base)

    def run_probe(self, run, consumer, extra_env=None, *probe_args):
        env = {**self.env, **(extra_env or {})}
        return subprocess.run([sys.executable, "-I", str(TOOLS / "canary_probe.py"), "--run", run, "--consumer",
                               consumer, *probe_args], env=env, capture_output=True, text=True, timeout=60)

    def test_stale_or_copied_tags_fail_verify(self):
        run = self.prepare()
        directory = self.run_dir(run)
        valid = self.run_probe(run, "codex-exec", {"CANARY_E2E_KEY": self.canary(run, "codex-exec")})
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(self.harness("verify", "--run", run, "--consumer", "codex-exec")[0], 0)
        tag_file = directory / "tags" / "codex-exec.tag"
        good = tag_file.read_text()
        # stale: the nonce is rotated for the next arming, so the old tag no longer verifies
        harness.rotate_nonce(directory, "codex-exec")
        tag_file.write_text(good)
        code, out, _ = self.harness("verify", "--run", run, "--consumer", "codex-exec")
        self.assertEqual((code, "tag invalid" in out), (1, True), out)
        # copied: another consumer's valid tag, under this consumer's name
        other = self.run_probe(run, "omniroute-lane", {"CANARY_E2E_KEY": self.canary(run, "omniroute-lane")})
        self.assertEqual(other.returncode, 0, other.stderr)
        (directory / "tags" / "codex-exec.tag").write_text((directory / "tags" / "omniroute-lane.tag").read_text())
        self.assertEqual(self.harness("verify", "--run", run, "--consumer", "codex-exec")[0], 1)
        # the right tag of the right consumer, computed with the wrong canary (the store held another one)
        wrong = self.run_probe(run, "codex-exec", {"CANARY_E2E_KEY": self.canary(run, "subagent")})
        self.assertEqual(wrong.returncode, 0)
        self.assertEqual(self.harness("verify", "--run", run, "--consumer", "codex-exec")[0], 1)
        self.assert_value_free(self.forbidden(run), self.all_output())

    def test_probe_reads_only_its_variable_and_never_prints_it(self):
        run = self.prepare()
        canary = self.canary(run, "fresh-claude-session")
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text())
        sentinels = {name: f"SENTINEL{index:02d}" + os.urandom(8).hex()
                     for index, name in enumerate(sorted({n for e in inventory["entries"]
                                                          for n in e["variables"] + e["optional_variables"]}
                                                         - {"CANARY_E2E_KEY"}))}
        result = self.run_probe(run, "fresh-claude-session", {**sentinels, "CANARY_E2E_KEY": canary})
        self.assertEqual(result.returncode, 0, result.stderr)
        nonce = (self.run_dir(run) / "nonce" / "fresh-claude-session").read_text().strip()
        full = probe.tag(canary, run, "fresh-claude-session", nonce)
        self.assertEqual(result.stdout, f"canary-probe fresh-claude-session: tag {full[:16]}\n")
        self.assertEqual(result.stderr, "")
        tag_file = self.run_dir(run) / "tags" / "fresh-claude-session.tag"
        self.assertEqual(tag_file.read_text().strip(), full)
        self.assertEqual(stat.S_IMODE(tag_file.stat().st_mode), 0o600)
        for text in (result.stdout, tag_file.read_text()):
            self.assert_value_free(secret_forms(canary) + [v.encode() for v in sentinels.values()], text)
        absent = subprocess.run([sys.executable, "-I", str(TOOLS / "canary_probe.py"), "--run", run, "--consumer",
                                 "fresh-claude-session"], capture_output=True, text=True, timeout=60,
                                env={**{k: v for k, v in self.env.items() if k != "CANARY_E2E_KEY"}, **sentinels})
        self.assertEqual(absent.returncode, 3)
        self.assertNotIn("SENTINEL", absent.stdout + absent.stderr)
        # The source reads the process environment in two places only: os.environ.get(VARIABLE), the one secret by its
        # hard-coded name, and the `env = os.environ if env is None else env` default of the location helpers, whose
        # only reads are env.get of three literal location names. Nothing iterates or copies the environment.
        source = (TOOLS / "canary_probe.py").read_text()
        tree = ast.parse(source)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        reads = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("environ", "environb", "getenv"):
                parent = parents[node]
                if isinstance(parent, ast.Attribute) and parent.attr == "get":
                    argument = parents[parent].args[0]
                    self.assertIsInstance(argument, ast.Name, f"line {node.lineno}")
                    reads.append(argument.id)
                else:
                    self.assertIsInstance(parent, ast.IfExp, f"the probe reads the environment another way, line {node.lineno}")
                    reads.append("default")
        self.assertEqual(sorted(reads), ["VARIABLE", "default"])
        self.assertEqual(probe.VARIABLE, "CANARY_E2E_KEY")
        self.assertEqual(set(re.findall(r"\benv\.(\w+)\(", source)), {"get"})
        self.assertEqual(set(re.findall(r'\benv\.get\("([A-Z_]+)"\)', source)), {"XDG_RUNTIME_DIR", "XDG_STATE_HOME", "HOME"})

    def test_probe_refuses_without_isolation_and_leak_check_for_other_consumers(self):
        run = self.prepare()
        env = {**self.env, "CANARY_E2E_KEY": self.canary(run, "codex-exec")}
        loose = subprocess.run([sys.executable, str(TOOLS / "canary_probe.py"), "--run", run, "--consumer", "codex-exec"],
                               env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(loose.returncode, 2)
        leak = self.run_probe(run, "codex-exec", {"CANARY_E2E_KEY": self.canary(run, "codex-exec")}, "--leak-check")
        self.assertEqual(leak.returncode, 2)
        self.assertEqual(leak.stdout, "")


class ScannerTests(CanaryCase):
    @unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
    def test_scanners_find_planted_decoys(self):
        run = self.prepare()
        code, out, err = self.harness("controls", "--run", run)
        self.assertEqual(code, 0, out + err)
        controls = json.loads((self.run_dir(run) / "results" / "controls.json").read_text())
        for name in ("text", "gz", "sqlite", "git"):
            self.assertGreaterEqual(controls[name]["found"], 1, name)
            self.assertEqual(controls[name]["after_removal"], 0, name)
            self.assertTrue(controls[name]["ok"], name)
        # SQLite: the decoy was only in the WAL of an open, unchekpointed connection, and one cell was gzip-compressed
        self.assertEqual((controls["sqlite"]["in_main_file"], controls["sqlite"]["in_wal"]), (False, True))
        self.assertGreaterEqual(controls["sqlite"]["found"], 2)
        self.assertGreaterEqual(controls["journal"]["found"], 1)
        self.assertIsNone(controls["journal"]["after_removal"])  # a journal line cannot be deleted
        for line in out.splitlines():
            self.assertRegex(line, r"^control [a-z]+: (ok|FAILED)")
        self.assert_value_free(self.forbidden(run), self.all_output())

    @unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
    def test_failing_control_is_not_a_sink_or_scanned_wrongly(self):
        run = self.prepare()
        self.assertEqual(self.harness("controls", "--run", run)[0], 0)
        sink = {"id": "X01", "kind": "files", "controls": ["claude"], "path_class": "x"}
        judged = harness.judge(sink, {"status": "scanned", "counts": {}}, planted={"claude"}, class_ok={"files": True})
        self.assertEqual((judged["verdict"], judged["fails"]), ("not a sink, or scanned wrongly", True))
        found = harness.judge(sink, {"status": "scanned", "counts": {"d-claude": 2}}, {"claude"}, {"files": True})
        self.assertEqual((found["verdict"], found["fails"]), ("clean (control passed)", False))
        self.assertEqual(found["proven_for"], ["fresh-claude-session"])
        leak = harness.judge(sink, {"status": "scanned", "counts": {"d-claude": 2, "c-codex-exec": 1}}, {"claude"},
                             {"files": True})
        self.assertEqual((leak["verdict"], leak["fails"], leak["canary"]["codex-exec"]), ("LEAK", True, 1))
        wrong = harness.judge(sink, {"status": "scanned", "counts": {"d-claude": 2}}, {"claude"}, {"files": False})
        self.assertTrue(wrong["fails"])
        self.assertIn("scanned wrongly", wrong["verdict"])
        bare = harness.judge({**sink, "controls": []}, {"status": "scanned", "counts": {}}, {"claude"}, {"files": True})
        self.assertEqual((bare["verdict"], bare["fails"]), ("uncontrolled: a zero here proves nothing", False))
        # end to end: the claude decoy was planted (a consumer ran) but this sink never received it
        (self.home / "transcripts").mkdir()
        self.write_sinks([self.sink("X01-empty", "files", ["$HOME/transcripts"], ["claude"])])
        self.assertEqual(self.harness("baseline", "--run", run)[0], 0)
        self.ran(run, "fresh-claude-session")
        code, out, _ = self.harness("scan", "--sink", "X01-empty", "--run", run)
        self.assertEqual(code, 1, out)
        self.assertIn("X01-empty [test/X01-empty]: not a sink, or scanned wrongly", out)

    @unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
    def test_scan_output_is_counts_only(self):
        run = self.prepare()
        self.assertEqual(self.harness("controls", "--run", run)[0], 0)
        self.assertEqual(self.harness("baseline", "--run", run)[0], 0)
        canary = self.canary(run, "codex-exec")
        leaked = self.home / "transcripts" / "careless.jsonl"
        leaked.parent.mkdir()
        leaked.write_text("line one\n" + json.dumps({"out": base64.b64encode(b"u" + canary.encode()).decode()}) + "\n")
        (self.home / "dbs").mkdir()
        with sqlite3.connect(self.home / "dbs" / "tool.db") as connection:
            connection.execute("CREATE TABLE t (v BLOB)")
            connection.execute("INSERT INTO t VALUES (?)", (gzip.compress(f"x {canary} y".encode()),))
        connection.close()
        self.write_sinks([self.sink("L01-transcripts", "files", ["$HOME/transcripts"]),
                          self.sink("L02-databases", "sqlite", ["$HOME/dbs"])])
        code, out, err = self.harness("scan", "--sink", "L01-transcripts", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("L01-transcripts [test/L01-transcripts]: LEAK; canary 1 (codex-exec=1)", out)
        code, out, err = self.harness("scan", "--sink", "L02-databases", "--run", run)
        self.assertEqual(code, 1)
        self.assertIn("LEAK; canary 1 (codex-exec=1)", out)  # found only after decompressing the cell
        text = self.all_output()
        self.assertNotIn(str(leaked), text)
        self.assertNotIn("careless", text)
        self.assertNotIn(str(self.home), text)
        self.assert_value_free(self.forbidden(run), text)

    @unittest.skipUnless(HAS_RG, "the file scanner needs rg")
    def test_scanners_never_read_an_excluded_path(self):
        # The store, the run directory, a shell_snapshots directory and a container config.v2.json hold the canary, and
        # the scans that cover them count nothing: excluded paths are pruned by the scanner itself.
        run = self.prepare()
        harness.write_json(self.run_dir(run) / "results" / "controls.json",
                           {k: {"ok": True} for k in ("text", "gz", "sqlite", "git", "journal")})
        canary = self.canary(run, "codex-exec")
        store = self.config / "native-agent-stack"
        store.mkdir(mode=0o700)
        (store / "other.env").write_text(f"export K={canary}\n")
        for relative in ("transcripts/shell_snapshots/s.sh", "docker/containers/abc/config.v2.json"):
            path = self.home / relative
            path.parent.mkdir(parents=True)
            path.write_text(f"declare -x K={canary}\n")
        (self.home / "transcripts" / "ok.txt").write_text("nothing\n")
        self.write_sinks([self.sink("E01-config", "files", ["$HOME/.config"]),
                          self.sink("E02-runtime", "files", [str(self.runtime)]),
                          self.sink("E03-transcripts", "files", ["$HOME/transcripts"]),
                          self.sink("E04-docker", "files", ["$HOME/docker"])])
        for sink in ("E01-config", "E02-runtime", "E03-transcripts", "E04-docker"):
            code, out, err = self.harness("scan", "--sink", sink, "--run", run)
            self.assertEqual(code, 0, out + err)
            self.assertIn("canary 0", out)

    def test_omniroute_scan_refuses_without_tty(self):
        run = self.prepare()
        code, out, err = self.harness("scan", "--sink", "omniroute", "--run", run, tty=False)
        self.assertEqual(code, 2)
        self.assertIn("user-run only", out + err)
        self.assertFalse((self.run_dir(run) / "results" / "scan-user-run.json").exists())
        cli = subprocess.run([sys.executable, "-I", "-c", HARNESS_LAUNCHER, "scan", "--sink", "omniroute", "--run", run],
                             env=self.env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(cli.returncode, 2, cli.stdout + cli.stderr)
        self.assertIn(harness.user_run_command(run), cli.stdout + cli.stderr)

    @unittest.skipUnless(HAS_RG, "the file scanner needs rg")
    def test_user_run_scan_in_a_terminal_counts_only(self):
        run = self.prepare()
        (self.home / "omni-data").mkdir()
        (self.home / "omni-data" / "call_logs.txt").write_text(self.decoy(run, "omni") + "\n")
        harness.write_json(self.run_dir(run) / "results" / "controls.json",
                           {k: {"ok": True} for k in ("text", "gz", "sqlite", "git", "journal")})
        self.ran(run, "omniroute-lane")
        code, out, err = self.harness("scan", "--sink", "omniroute", "--run", run, tty=True)
        self.assertEqual(code, 0, out + err)
        self.assertIn("T07-call-logs [test/T07-call-logs]: clean (control passed); canary 0; controls omni=found", out)
        self.assertIn("T08-manager [test/T08-manager]:", out)  # the manager's environment is user-run now, names only
        self.assertTrue((self.run_dir(run) / "results" / "scan-user-run.json").exists())

    def test_cleanup_removes_only_the_canary_file(self):
        run = self.prepare()
        store = self.config / "native-agent-stack"
        store.mkdir(mode=0o700, exist_ok=True)
        other = store / "tavily.env"
        other.write_text("export TAVILY_API_KEY=tvly-" + os.urandom(12).hex() + "\n")
        other.chmod(0o600)
        before = (other.read_bytes(), other.stat().st_mtime_ns, stat.S_IMODE(other.stat().st_mode))
        harness.arm(self.context(), self.run_dir(run), "codex-exec")
        self.assertTrue(self.store_file().exists())
        self.assertEqual(stat.S_IMODE(self.store_file().stat().st_mode), 0o600)
        self.assertEqual(self.store_file().read_text(), f"export CANARY_E2E_KEY={self.canary(run, 'codex-exec')}\n")
        receipts = self.state / "native-agent-stack" / "canary"
        receipts.mkdir(parents=True)
        (receipts / "00000001-x.json").write_text("{}")
        code, out, err = self.harness("cleanup", "--run", run)
        self.assertEqual(code, 0, out + err)
        self.assertFalse(self.store_file().exists())
        self.assertEqual((other.read_bytes(), other.stat().st_mtime_ns, stat.S_IMODE(other.stat().st_mode)), before)
        self.assertEqual(sorted(p.name for p in store.iterdir()), ["tavily.env"])
        self.assertFalse(any(d.exists() for d in probe.run_directories(run, self.env)))
        self.assertTrue((receipts / "00000001-x.json").exists())
        # a symbolic link in the canary file's place is refused and left, and its target is untouched
        run = self.prepare()
        target = self.base / "target"
        target.write_text("untouched")
        self.store_file().symlink_to(target)
        code, out, err = self.harness("cleanup", "--run", run)
        self.assertEqual(code, 1)
        self.assertTrue(self.store_file().is_symlink())
        self.assertEqual(target.read_text(), "untouched")

    def test_arming_is_create_only(self):
        run = self.prepare()
        directory = self.run_dir(run)
        harness.arm(self.context(), directory, "codex-exec")
        first = self.store_file().read_bytes()
        with self.assertRaises(harness.Refused):
            harness.arm(self.context(), directory, "omniroute-lane")
        self.assertEqual(self.store_file().read_bytes(), first)
        code, out, err = self.harness("prepare")
        self.assertEqual(code, 1)  # a new run refuses while a canary file is in the store
        self.assertTrue(harness.disarm(self.context(), directory))
        self.assertFalse(harness.disarm(self.context(), directory))

    def test_proc_cmdline_sampler_counts_only(self):
        run = self.prepare()
        sets = harness.load_sets(self.run_dir(run))
        canary = self.canary(run, "systemd-user-unit")
        for pid, argv in (("101", [b"python3", b"-I", b"probe.py"]), ("102", [b"echo", canary.encode()]),
                          ("103", [b"x", base64.b64encode(canary.encode())])):
            (self.proc / pid).mkdir()
            (self.proc / pid / "cmdline").write_bytes(b"\0".join(argv) + b"\0")
        (self.proc / "self").mkdir()
        sampler = harness.ProcSampler(self.context(), {k: v for k, v in sets.items() if k.startswith("c-")})
        sampler.sample_once()
        sampler.sample_once()
        summary = sampler.summary()
        self.assertEqual(summary["cmdline_hits"], {"systemd-user-unit": 2})
        self.assertEqual(summary["samples"], 2)
        self.assert_value_free(self.forbidden(run), json.dumps(summary))

    def test_codex_consumers_refuse_unless_shell_snapshots_are_off(self):
        run = self.prepare()
        # (shell_snapshot in config.toml, in omniroute.config.toml, the profile used, whether snapshots are off)
        cases = ((None, None, None, False),              # unset: on by default at 0.157.1
                 ("false", None, None, True), ("true", None, None, False),
                 ("false", "true", "omniroute", False),  # the profile layer turns them back on
                 ("true", "false", "omniroute", True),   # the profile layer turns them off
                 ("false", None, "omniroute", True),     # no profile file: the base value holds
                 ("true", "false", None, False))         # a profile file is read only for its profile
        for base, layer, profile, expected in cases:
            with self.subTest(base=base, layer=layer, profile=profile):
                for name in ("config.toml", "omniroute.config.toml"):
                    (self.codex_home / name).unlink(missing_ok=True)
                if base is not None:
                    (self.codex_home / "config.toml").write_text(f"model = \"m\"\n[features]\nshell_snapshot = {base}\n")
                if layer is not None:
                    (self.codex_home / "omniroute.config.toml").write_text(f"[features]\nshell_snapshot = {layer}\n")
                self.assertEqual(harness.codex_shell_snapshot_off(self.codex_home, profile), expected)
        (self.codex_home / "config.toml").write_text("[profiles.omniroute.features]\nshell_snapshot = true\n")
        (self.codex_home / "omniroute.config.toml").unlink()
        self.assertFalse(harness.codex_shell_snapshot_off(self.codex_home, "omniroute"))  # a legacy profile table
        self.codex_config(base=True, profile=True)  # snapshots on: refused before anything is armed
        code, out, err = self.harness("consume", "codex-exec", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("shell_snapshot", out + err)
        self.assertFalse(self.store_file().exists())

    def test_sink_table_follows_the_verified_list(self):
        table = json.loads((TOOLS / "canary_sinks.json").read_text())
        ids = [row["id"] for row in table["sinks"]]
        self.assertEqual(len(ids), len(set(ids)))
        numbers = {int(m.group(1)) for m in (re.match(r"S(\d\d)-", i) for i in ids) if m}
        self.assertEqual(numbers, set(range(1, 50)))  # every research_sinks row, S01 to S49
        for missed in ("M01-docker-config", "M02-systemd-user-units", "M03-user-manager-environment", "M04-environment-d",
                       "M05-claude-plugins", "M07-grand-dashboard-publisher"):
            self.assertIn(missed, ids)
        self.assertEqual(harness.table_errors(table), [])
        rows = {row["id"]: row for row in table["sinks"]}
        # Stores that the guard denies to agents, and every scan that would pass a real value through the harness's
        # memory (the user manager's environment, container configurations), run only in the user's terminal.
        self.assertEqual({i for i, r in rows.items() if r["access"] == "user_run"},
                         {"S14-codex-shell-snapshots", "S25-omniroute-main", "S26-omniroute-fw", "M01-docker-config",
                          "M03-user-manager-environment", "S37-docker-container-configs"})
        self.assertIn("config.v2.json", table["exclude_names"])
        self.assertIn("hostconfig.json", table["exclude_names"])
        for identifier, row in rows.items():
            if row["access"] in ("agent", "sudo"):
                for template in row["paths"]:
                    self.assertIsNone(guard.check(f"cat {template}"), (identifier, template))
        self.assertEqual({i for i, r in rows.items() if r["async"]}, {"S17-ai-memory", "S21-agentsview", "S28-loki"})
        self.assertIn("never swept", rows["S02-claude-prompt-history"]["retention"])
        self.assertIn("90 days", rows["S18-rtk-history"]["retention"])
        self.assertIn("30 days", rows["S18-rtk-recall"]["retention"])
        self.assertEqual((rows["S18-rtk-recall"]["controls"], rows["S18-rtk-recall"]["control_in"]),
                         (["rtk"], "decoded_blobs"))
        for template in ("$HOME/.ssh", "$HOME/.gnupg", "${XDG_CONFIG_HOME:-$HOME/.config}/gh",
                         "${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack",
                         "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.credentials.json", "${CODEX_HOME:-$HOME/.codex}/auth.json"):
            self.assertIn(template, table["exclude"])
        broken = copy.deepcopy(table)
        broken["sinks"][0]["controls"] = ["nonexistent"]
        broken["sinks"][1]["kind"] = "telepathy"
        self.assertEqual(len(harness.table_errors(broken)), 2)
        agent_manager = copy.deepcopy(table)
        next(r for r in agent_manager["sinks"] if r["kind"] == "manager_environment")["access"] = "agent"
        self.assertEqual(len(harness.table_errors(agent_manager)), 1)  # names or not, it reads real values


class LokiTests(CanaryCase):
    def serve(self, entries, seen):
        """A Loki stub: query_range honours start (inclusive), end and limit, forward; push is recorded."""

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                seen["queries"].append(self.path)
                start, end, limit = int(query["start"][0]), int(query["end"][0]), int(query["limit"][0])
                page = [[str(ts), line] for ts, line in entries if start <= ts <= end][:limit]
                data = json.dumps({"status": "success", "data": {"result": [{"stream": {"service_name": "x"},
                                                                              "values": page}]}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                seen["pushes"].append(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(204)
                self.end_headers()

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_loki_dump_matches_locally_and_the_push_carries_only_the_decoy(self):
        run = self.prepare()
        sets = harness.load_sets(self.run_dir(run))
        decoy = self.decoy(run, "loki")
        canary = self.canary(run, "codex-exec")
        seen = {"queries": [], "pushes": []}
        now = int(time.time() * 1e9)
        url = self.serve([(now - 3, f"line {decoy}"), (now - 2, f"leaked {canary}"), (now - 1, "ordinary")], seen)
        sink = self.sink("T-loki", "loki", controls=["loki"], url=url)
        self.assertTrue(harness.loki_push(self.context(), sink, decoy))
        result = harness.scan_sink(self.context(), self.run_dir(run), sink, sets, agent_pass=True, seen_git=set(),
                                   since_epoch=time.time() - 60)
        self.assertEqual((result["counts"]["d-loki"], result["counts"]["c-codex-exec"], result["status"]),
                         (1, 1, "scanned"))
        for query in seen["queries"]:
            self.assert_value_free(secret_forms(canary) + secret_forms(decoy), urllib.parse.unquote(query))
        self.assertEqual(len(seen["pushes"]), 1)
        self.assertIn(decoy.encode(), seen["pushes"][0])
        self.assert_value_free(secret_forms(canary), seen["pushes"][0])
        with self.assertRaises(harness.Refused):  # decoys go to a loopback Loki only
            harness.loki_push(self.context(), {**sink, "url": "http://example.com"}, decoy)

    def test_loki_pages_keep_boundary_entries_and_an_unfinished_dump_is_incomplete(self):
        # Review finding 8: paging from the last timestamp plus one skipped entries that shared it, and a spent page
        # budget still read as scanned. Boundary entries are kept and deduplicated; what cannot be paged is INCOMPLETE.
        run = self.prepare()
        sets = harness.load_sets(self.run_dir(run))
        canary = self.canary(run, "codex-exec")
        base = int((time.time() - 30) * 1e9)
        sink = lambda url: self.sink("T-loki", "loki", controls=[], url=url)  # noqa: E731
        with mock.patch.object(harness, "LOKI_LIMIT", 2):
            url = self.serve([(base, "a"), (base + 1, "b"), (base + 1, f"leaked {canary}"), (base + 2, "d")],
                             {"queries": [], "pushes": []})
            result = harness.scan_sink(self.context(), self.run_dir(run), sink(url), sets, agent_pass=True,
                                       seen_git=set(), since_epoch=time.time() - 60)
            self.assertEqual(result["counts"]["c-codex-exec"], 1)  # the entry that shares the page's last timestamp
            url = self.serve([(base, "a"), (base, "b"), (base, f"leaked {canary}")], {"queries": [], "pushes": []})
            result = harness.scan_sink(self.context(), self.run_dir(run), sink(url), sets, agent_pass=True,
                                       seen_git=set(), since_epoch=time.time() - 60)
            self.assertEqual(result["status"], "incomplete")  # a full page on one timestamp cannot be paged past
            judged = harness.judge(sink(url), result, set(), {})
            self.assertTrue(judged["fails"])
        with mock.patch.object(harness, "LOKI_LIMIT", 2), mock.patch.object(harness, "LOKI_PAGES", 1):
            url = self.serve([(base, "a"), (base + 1, "b"), (base + 2, "c"), (base + 3, "d")],
                             {"queries": [], "pushes": []})
            result = harness.scan_sink(self.context(), self.run_dir(run), sink(url), sets, agent_pass=True,
                                       seen_git=set(), since_epoch=time.time() - 60)
            self.assertEqual((result["status"], result["reasons"]), ("incomplete", ["page budget spent"]))


@unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
class IncompleteScanTests(CanaryCase):
    """Review findings 4 and 11: an unreadable path, a failed scanner or an expired deadline is INCOMPLETE and fails."""

    def ready(self):
        run = self.prepare()
        self.assertEqual(self.harness("controls", "--run", run)[0], 0)
        return run

    @unittest.skipIf(os.geteuid() == 0, "root reads a 000 file")
    def test_an_unreadable_file_makes_the_sink_incomplete(self):
        run = self.ready()
        directory = self.home / "mixed"
        directory.mkdir()
        (directory / "readable.txt").write_text(self.decoy(run, "claude") + "\n")
        hidden = directory / "hidden.txt"
        hidden.write_text(self.canary(run, "codex-exec") + "\n")
        hidden.chmod(0)
        self.addCleanup(hidden.chmod, 0o600)
        self.write_sinks([self.sink("I01-mixed", "files", ["$HOME/mixed"], ["claude"])])
        self.ran(run, "fresh-claude-session")
        code, out, err = self.harness("scan", "--sink", "I01-mixed", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("I01-mixed [test/I01-mixed]: INCOMPLETE", out)

    def test_a_failed_scanner_fails_the_baseline_and_consume_refuses_without_a_clean_one(self):
        run = self.ready()
        (self.home / "journal-fails").write_text("")
        code, out, err = self.harness("baseline", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("T04-journal [test/T04-journal]: INCOMPLETE", out)
        self.assertFalse(json.loads((self.run_dir(run) / "results" / "baseline.json").read_text())["ok"])
        self.codex_config()
        code, out, err = self.harness("consume", "codex-exec", "--run", run)
        self.assertEqual(code, 1)
        self.assertIn("baseline", out + err)
        self.assertFalse(self.store_file().exists())

    def test_a_fifo_is_never_handed_to_a_scanner_and_a_deadline_makes_a_sink_incomplete(self):
        run = self.ready()
        root = self.home / "fifo-root"
        (root / "excluded").mkdir(parents=True)
        (root / "note.txt").write_text("nothing\n")
        os.mkfifo(root / "pipe")
        self.write_sinks([self.sink("F01-fifo", "files", ["$HOME/fifo-root"]),
                          self.sink("F02-late", "files", ["$HOME/fifo-root"], deadline_seconds=0)],
                         exclude=["$HOME/fifo-root/excluded"])
        process = self.launch("scan", "--sink", "F01-fifo", "--run", run)
        try:
            out, err = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            self.fail("the scan blocked on a FIFO")
        self.assertEqual(process.returncode, 0, out + err)
        self.assertIn(b"special files skipped 1", out)
        code, out, err = self.harness("scan", "--sink", "F02-late", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("F02-late [test/F02-late]: INCOMPLETE", out)
        self.assertIn("deadline", out)


@unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
class CompressionAndNameTests(CanaryCase):
    """Review findings 5, 6 and 7: every compressed member is decoded or the cell is unreadable; names are matched
    locally, never copied into a scanner's argv, and a newline in a name hides nothing."""

    def ready(self):
        run = self.prepare()
        harness.write_json(self.run_dir(run) / "results" / "controls.json",
                           {k: {"ok": True} for k in ("text", "gz", "sqlite", "git", "journal")})
        return run

    def database(self, name, *values):
        directory = self.home / "blobs"
        directory.mkdir(exist_ok=True)
        with sqlite3.connect(directory / name) as connection:
            connection.execute("CREATE TABLE t (v BLOB)")
            for value in values:
                connection.execute("INSERT INTO t VALUES (?)", (value,))
        connection.close()

    def test_every_gzip_member_is_decoded_and_a_limit_makes_the_cell_unreadable(self):
        run = self.ready()
        canary = self.canary(run, "codex-exec").encode()
        self.database("members.db", gzip.compress(b"harmless") + gzip.compress(b"x " + canary + b" y"))
        self.write_sinks([self.sink("Z01-blobs", "sqlite", ["$HOME/blobs"])])
        code, out, err = self.harness("scan", "--sink", "Z01-blobs", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("LEAK; canary 1 (codex-exec=1)", out)  # found in the second member
        (self.home / "blobs" / "members.db").unlink()
        self.database("big.db", gzip.compress(b"0" * 5000 + canary))
        with mock.patch.object(harness, "MAX_DECOMPRESSED", 1024):
            code, out, err = self.harness("scan", "--sink", "Z01-blobs", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("INCOMPLETE", out)  # never a quiet drop of the suffix
        (self.home / "blobs" / "big.db").unlink()
        self.database("cut.db", gzip.compress(b"1" * 4000 + canary)[:-12])
        code, out, err = self.harness("scan", "--sink", "Z01-blobs", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("INCOMPLETE", out)  # a truncated stream is unreadable, not empty

    def test_a_name_is_matched_locally_and_never_reaches_a_scanner_argv(self):
        run = self.ready()
        real_rg = shutil.which("rg")
        (self.bin / "rg").write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                                     f"open({str(self.base / 'rg-argv.jsonl')!r}, 'a').write(json.dumps(sys.argv) + '\\n')\n"
                                     f"os.execv({real_rg!r}, [{real_rg!r}] + sys.argv[1:])\n")
        (self.bin / "rg").chmod(0o755)
        canary = self.canary(run, "codex-exec")
        directory = self.home / "names"
        directory.mkdir()
        (directory / canary.encode().hex()).write_text(self.decoy(run, "codex") + "\n")  # a name holds the canary
        (directory / f"new\nline-{os.urandom(4).hex()}.txt").write_text(f"x {self.canary(run, 'subagent')} y\n")
        self.write_sinks([self.sink("N01-names", "files", ["$HOME/names"])])
        code, out, err = self.harness("scan", "--sink", "N01-names", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("LEAK; canary 2 (subagent=1, codex-exec=1)", out)
        argv = (self.base / "rg-argv.jsonl").read_text()
        self.assertTrue(argv)
        self.assert_value_free(secret_forms(canary) + secret_forms(self.canary(run, "subagent")), argv)
        self.assertNotIn("names/", argv.replace(str(self.home / "names"), ""))  # only the configured root, never a name


class RtkControlTests(CanaryCase):
    """Review finding 9: RTK keeps the output of a failed command of 500 bytes or more; the recall control must be
    found in the decoded recall blobs, never in the command column."""

    def recall(self, command: str, output: bytes):
        path = self.home / "rtk" / "recall.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE recall (hash TEXT, command TEXT, codec TEXT, blob BLOB)")
            connection.execute("INSERT INTO recall VALUES ('h', ?, 'gzip', ?)", (command, gzip.compress(output)))
        connection.close()

    def test_the_decoy_command_fails_with_enough_output_for_rtk(self):
        run = self.prepare()
        value = self.decoy(run, "rtk")
        code, out, err = self.harness("decoy", "--run", run, "--consumer", "fresh-claude-session", "--rtk", value)
        self.assertEqual(code, 1)
        self.assertGreaterEqual(len(out.encode()), 600)  # rtk-ai/rtk@v0.50.0 MIN_FAILURE_BYTES = 500
        self.assertGreaterEqual(out.count(value), 8)
        self.assertEqual(self.harness("decoy", "--run", run, "--consumer", "fresh-claude-session", "--rtk",
                                      harness.new_decoy())[0], 2)  # a mistyped value is refused, never printed
        command = harness.rtk_decoy_command(run, value)
        self.assertTrue(command.startswith("rtk err python3 tools/credentials/canary_e2e.py decoy "))
        self.assertIsNone(guard.check(command))
        self.assertIn(command, harness.claude_prompt(run, self.decoy(run, "claude"), value))

    @unittest.skipUnless(HAS_RG, "the file scanner needs rg")
    def test_the_recall_control_counts_only_decoded_blobs(self):
        run = self.prepare()
        harness.write_json(self.run_dir(run) / "results" / "controls.json",
                           {k: {"ok": True} for k in ("text", "gz", "sqlite", "git", "journal")})
        self.ran(run, "fresh-claude-session")
        value = self.decoy(run, "rtk")
        self.write_sinks([self.sink("R01-recall", "sqlite", ["$HOME/rtk/recall.db*"], ["rtk"],
                                    control_in="decoded_blobs")])
        self.recall(f"python3 decoy --rtk {value}", b"x" * 600)  # the command column alone: no recall control
        code, out, err = self.harness("scan", "--sink", "R01-recall", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("R01-recall [test/R01-recall]: not a sink, or scanned wrongly", out)
        shutil.rmtree(self.home / "rtk")
        self.recall("python3 decoy --rtk <elided>", (f"line {value}\n" * 12).encode())
        code, out, err = self.harness("scan", "--sink", "R01-recall", "--run", run)
        self.assertEqual(code, 0, out + err)
        self.assertIn("R01-recall [test/R01-recall]: clean (control passed)", out)


class SafetyTests(CanaryCase):
    """Review findings 10, 12 and 13: the crash-collector refusal, interruption, and which run owns the store file."""

    def test_a_host_that_pipes_crash_dumps_is_refused_before_any_canary_exists(self):
        pattern = self.base / "pipe_pattern"
        pattern.write_text("|/usr/lib/systemd/systemd-coredump %P\n")
        with mock.patch.object(run_mod, "CORE_PATTERN_FILE", str(pattern)):
            code, out, err = self.harness("prepare")
        self.assertEqual(code, 1)
        self.assertIn("core_pattern_pipe", err)
        self.assertFalse((self.runtime / "native-agent-stack").exists())

    def test_cleanup_and_prepare_respect_the_run_that_armed_the_store(self):
        first, second = self.prepare(), self.prepare()
        harness.arm(self.context(), self.run_dir(first), "codex-exec")
        code, out, err = self.harness("cleanup", "--run", second)
        self.assertEqual(code, 1, out + err)
        self.assertIn(f"armed by run {first}", err)
        self.assertTrue(self.store_file().exists())
        self.assertTrue(self.run_dir(second).exists())
        self.assertEqual(self.harness("prepare")[0], 1)
        self.codex_config()
        code, out, err = self.harness("consume", "codex-exec", "--run", second)
        self.assertEqual(code, 1)
        self.assertIn(f"armed by run {first}", err)
        self.assertEqual(self.harness("cleanup", "--run", first)[0], 0)
        self.assertFalse(self.store_file().exists())

    @unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
    def test_a_terminated_consume_ends_its_client_disarms_and_marks_the_run(self):
        run = self.prepare()
        for step in (("controls", "--run", run), ("baseline", "--run", run)):
            self.assertEqual(self.harness(*step)[0], 0)
        (self.home / "slow-claude").write_text("")
        process = self.launch("consume", "fresh-claude-session", "--run", run)
        pid_file, deadline = self.home / "claude.pid", time.time() + 30
        while not pid_file.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.store_file().exists())
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=30)
        self.assertEqual(process.returncode, 128 + signal.SIGTERM)
        pid = int(pid_file.read_text().split()[0])
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail("the client was left running")
        self.assertFalse(self.store_file().exists())
        self.assertTrue((self.run_dir(run) / "results" / "interrupted.json").exists())
        code, out, err = self.harness("report", "--run", run)
        self.assertEqual(code, 1)
        self.assertIn("interrupted", err)

    @unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
    def test_an_interrupted_workflow_wait_disarms(self):
        run = self.prepare()
        for step in (("controls", "--run", run), ("baseline", "--run", run)):
            self.assertEqual(self.harness(*step)[0], 0)
        process = self.launch("consume", "workflow-child", "--run", run, "--timeout", "60")
        deadline = time.time() + 30
        while not self.store_file().exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.store_file().exists())
        process.send_signal(signal.SIGINT)
        process.communicate(timeout=30)
        self.assertEqual(process.returncode, 130)
        self.assertFalse(self.store_file().exists())
        self.assertTrue((self.run_dir(run) / "results" / "interrupted.json").exists())


@unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
class FullRun(CanaryCase):
    """The whole proof with stub consumers that run the real runner and the real probe against a temporary store."""

    ALLOWED = {
        "schema_version", "kind", "run", "recorded_at", "keep_across_restart", "checkout_revision", "versions",
        "versions.*", "consumers", "consumers.*", "consumers.*.ran", "consumers.*.started_at", "consumers.*.ended_at",
        "consumers.*.exit_code", "consumers.*.sequence", "consumers.*.tag", "consumers.*.tag_channel",
        "consumers.*.model_id", "consumers.*.model_id_source", "consumers.*.stream_canary_hits",
        "consumers.*.cmdline_hits", "consumers.*.transient_unit_hits", "consumers.*.decoy_echoed", "after_restart",
        "after_restart.ran", "after_restart.exit_code", "after_restart.boot_changed", "after_restart.masked",
        "after_restart.pattern_hits", "after_restart.tag", "leak_check", "leak_check.pattern_hits",
        "leak_check.printed_form_hits", "leak_check.markers", "leak_check.partial_markers", "leak_check.forms_printed",
        "leak_check.masked", "captures", "captures.*", "captures.*.canary", "captures.*.control", "controls",
        "controls.*", "controls.*.found", "controls.*.after_removal", "controls.*.ok", "controls.*.in_main_file",
        "controls.*.in_wal", "baseline", "baseline.canary_hits", "baseline.sinks", "baseline.incomplete", "baseline.ok",
        "settle", "settle.arrival_seconds", "settle.arrival_seconds.*", "settle.pass1_delay_seconds",
        "settle.pass2_delay_seconds", "settle.max_wait_seconds", "passes", "passes.*", "passes.*.ran_at", "passes.*.ok",
        "passes.*.sinks", "passes.*.sinks.*", "passes.*.sinks.*.canary", "passes.*.sinks.*.canary_by_consumer",
        "passes.*.sinks.*.canary_by_consumer.*", "passes.*.sinks.*.controls", "passes.*.sinks.*.controls.*",
        "passes.*.sinks.*.verdict", "passes.*.sinks.*.proven_for", "passes.*.sinks.*.unreadable", "user_run",
        "user_run.ran", "user_run.ran_at", "user_run.ok", "user_run.sinks", "user_run.sinks.*",
        "user_run.sinks.*.canary", "user_run.sinks.*.canary_by_consumer", "user_run.sinks.*.canary_by_consumer.*",
        "user_run.sinks.*.controls", "user_run.sinks.*.controls.*", "user_run.sinks.*.verdict",
        "user_run.sinks.*.proven_for", "user_run.sinks.*.unreadable", "checks_not_run", "result", "reasons", "claim",
        "not_covered", "manager_environment", "manager_environment.canary_name_present",
        "manager_environment.inventory_names_present",
    }

    def key_paths(self, value, prefix=""):
        if isinstance(value, dict):
            for key, item in value.items():
                dynamic = (prefix in ("versions", "consumers", "controls", "passes", "captures",
                                      "settle.arrival_seconds")
                           or re.fullmatch(r"(passes\.\*|user_run)\.sinks"
                                           r"|(passes\.\*|user_run)\.sinks\.\*\.(canary_by_consumer|controls)", prefix))
                path = f"{prefix}.*" if dynamic else (f"{prefix}.{key}" if prefix else key)
                yield path
                yield from self.key_paths(item, path)

    def full_run(self, keep=False):
        """Every step of the window through stubs; returns (run, {step: (code, out, err)})."""
        self.codex_config()
        (self.home / "dbs").mkdir()
        with sqlite3.connect(self.home / "dbs" / "notes.db") as connection:
            connection.execute("CREATE TABLE notes (body TEXT)")
            connection.execute("INSERT INTO notes VALUES ('nothing to see')")
        connection.close()
        subprocess.run(["git", "init", "-q", str(self.home / "repo")], check=True)
        run = self.prepare(*(["--keep-across-restart"] if keep else []))
        steps = {}

        def step(name, *argv):
            steps[name] = self.harness(*argv)
            return steps[name]

        step("controls", "controls", "--run", run)
        step("baseline", "baseline", "--run", run)
        step("claude", "consume", "fresh-claude-session", "--run", run, "--timeout", "120")

        def workflow_child():  # the Workflow tool's probe stage, emulated once the store holds this consumer's canary
            deadline = time.time() + 30
            while time.time() < deadline and not self.store_file().exists():
                time.sleep(0.02)
            command = [sys.executable, "-I", str(TOOLS / "canary_probe.py"), "--run", run, "--consumer", "workflow-child"]
            runner = ([sys.executable, "-I", "-S", "-c", LAUNCHER] if HOST_PIPES_CORES
                      else [sys.executable, "-I", str(TOOLS / "credential_run.py")])
            subprocess.run(runner + ["canary-e2e", "--", *command], env=self.env, capture_output=True, timeout=60)

        helper = threading.Thread(target=workflow_child)
        helper.start()
        step("workflow", "consume", "workflow-child", "--run", run, "--timeout", "60")
        helper.join()
        step("codex", "consume", "codex-exec", "--run", run)
        step("omniroute", "consume", "omniroute-lane", "--run", run)
        step("unit", "consume", "systemd-user-unit", "--run", run)
        step("verify", "verify", "--run", run)
        step("settle", "settle", "--run", run, "--max-wait", "20", "--interval", "0.2")
        step("early", "scan", "--pass", "1", "--run", run)
        self.clock_offset = 10 ** 6  # after both passes are due
        step("pass1", "scan", "--pass", "1", "--run", run)
        step("pass2", "scan", "--pass", "2", "--run", run)
        step("report", "report", "--run", run, "--model", "workflow-child=claude-sonnet-5-5")
        return run, steps

    def receipts(self):
        directory = self.state / "native-agent-stack" / "canary"
        return sorted(p for p in directory.iterdir() if p.suffix == ".json")

    def last_receipt(self) -> dict:
        return json.loads(self.receipts()[-1].read_text())


class EndToEndStubTests(FullRun):
    def test_six_consumers_through_stubs_to_a_value_free_receipt(self):
        run, steps = self.full_run()
        for name in ("controls", "baseline", "claude", "workflow", "codex", "omniroute", "unit", "verify", "settle",
                     "pass1", "pass2", "report"):
            self.assertEqual(steps[name][0], 0, f"{name}: {steps[name][1]}{steps[name][2]}")
        early = steps["early"]
        self.assertEqual(early[0], 2, early[1] + early[2])  # a pass does not run before its measured due time
        self.assertIn("is due at", early[1] + early[2])
        tags = {p.stem: p.read_text().strip() for p in (self.run_dir(run) / "tags").glob("*.tag")}
        self.assertEqual(set(tags), set(probe.CONSUMERS))
        forbidden = self.forbidden(run)
        [receipt_path] = self.receipts()
        self.assertEqual(stat.S_IMODE(receipt_path.stat().st_mode), 0o600)
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["result"], "zero", receipt.get("reasons"))
        for consumer in probe.CONSUMERS:
            row = receipt["consumers"][consumer]
            self.assertEqual((row["ran"], row["tag"], row["stream_canary_hits"], row["cmdline_hits"]),
                             (True, "valid", 0, 0), consumer)
        self.assertEqual(receipt["consumers"]["fresh-claude-session"]["model_id"], "claude-sonnet-5-5-stub")
        self.assertEqual(receipt["consumers"]["subagent"]["model_id"], "claude-sonnet-5-5-stub-sub")
        self.assertEqual(receipt["consumers"]["workflow-child"]["model_id_source"], "coordinator")
        leak = receipt["leak_check"]
        self.assertEqual((leak["pattern_hits"], leak["printed_form_hits"], leak["masked"]), (0, 0, True))
        self.assertGreaterEqual(leak["markers"] + leak["partial_markers"], leak["forms_printed"])
        pass1 = receipt["passes"]["1"]["sinks"]
        self.assertEqual(pass1["T01-transcripts"]["controls"], {"claude": "found", "subagent": "found"})
        self.assertEqual(pass1["T02-rollouts"]["controls"], {"codex": "found", "omni": "found"})
        self.assertEqual(pass1["T04-journal"]["verdict"], "clean (control passed)")
        self.assertEqual(pass1["T15-rtk-recall"]["controls"], {"rtk": "found"})
        self.assertIsNotNone(receipt["settle"]["arrival_seconds"]["T03-archive"])
        self.assertNotIn("T07-call-logs", pass1)  # user-run only
        self.assertNotIn("T14-sudo-only", pass1)  # only with --with-sudo
        # every capture of every consumer was scanned, each with its positive control, and none holds a canary
        self.assertTrue(receipt["captures"])
        for name, row in receipt["captures"].items():
            self.assertEqual((row["canary"], row["control"]), (0, "found"), name)
        self.assertIn("codex-exec.stderr", receipt["captures"])
        # the user-run scan did not run: the receipt and the claim say so, by sink id
        self.assertFalse(receipt["user_run"]["ran"])
        self.assertEqual(receipt["checks_not_run"], ["T07-call-logs", "T08-manager"])
        self.assertIn("cooperative", receipt["claim"])
        self.assertIn("T07-call-logs", receipt["claim"])
        self.assertIn("W03-wsl-swap-and-pagefile", receipt["not_covered"])
        for path in self.key_paths(receipt):
            self.assertIn(path, self.ALLOWED)
        extra = [t.encode() for t in tags.values()] + [t[:16].encode() for t in tags.values()]
        self.assert_value_free(forbidden + extra, receipt_path.read_bytes())
        self.assert_value_free(forbidden + extra, self.all_output())
        # Review finding 14: no environment the harness built kept a sentinel, by name or by value; the OmniRoute lane
        # got only the loopback placeholder, and the probe got CANARY_E2E_KEY from the runner and nothing else of them.
        hashes = {hashlib.sha256(v.encode()).hexdigest() for v in self.sentinels.values()}
        labels = ("fresh-claude-session", "codex-exec", "omniroute-lane", "systemd-run", "journalctl", "gh",
                  "probe-environment")
        for label in labels:
            seen = json.loads((self.home / "stub-env" / f"{label}.json").read_text())
            allowed = {"OMNIROUTE_API_KEY"} if label == "omniroute-lane" else set()
            allowed |= {"CANARY_E2E_KEY"} if label == "probe-environment" else set()
            self.assertEqual(set(seen) & set(self.sentinels), allowed, label)
            self.assertEqual(set(seen.values()) & hashes, set(), label)
            self.assertNotIn("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", seen)
        self.assertFalse(self.store_file().exists())
        code, out, err = self.harness("cleanup", "--run", run)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.receipts(), [receipt_path])


class EvidenceIntegrityTests(FullRun):
    """Review findings 1, 2 and 3: captures are scanned, every executed check enters the verdict, and re-runs
    invalidate the evidence that predates them."""

    def test_a_canary_in_a_client_stderr_capture_fails_consume_and_the_report(self):
        (self.home / "careless-codex").write_text("")
        run, steps = self.full_run()
        self.assertEqual(steps["codex"][0], 1, steps["codex"][1] + steps["codex"][2])
        receipt = self.last_receipt()
        self.assertEqual(receipt["result"], "leak", receipt["reasons"])
        self.assertEqual(receipt["captures"]["codex-exec.stderr"]["canary"], 1)
        self.assert_value_free(self.forbidden(run), self.all_output())

    def test_a_user_run_scan_that_finds_a_canary_makes_the_report_a_leak(self):
        run, steps = self.full_run()
        self.assertEqual(self.last_receipt()["result"], "zero")
        with open(self.home / "omni-data" / "call_logs.txt", "a") as handle:
            handle.write(f"echoed back {self.canary(run, 'omniroute-lane')}\n")
        code, out, err = self.harness("scan", "--sink", "omniroute", "--run", run, tty=True)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.harness("report", "--run", run)[0], 1)
        receipt = self.last_receipt()
        self.assertEqual(receipt["result"], "leak", receipt["reasons"])
        self.assertTrue(receipt["user_run"]["ran"])
        self.assertEqual(receipt["checks_not_run"], [])

    def test_a_kept_run_without_its_after_restart_check_is_not_zero(self):
        run, steps = self.full_run(keep=True)
        self.assertEqual(steps["report"][0], 1)
        receipt = self.last_receipt()
        self.assertEqual(receipt["result"], "incomplete")
        self.assertIn("after_restart_missing", receipt["reasons"])
        self.assertEqual(self.harness("cleanup", "--run", run)[0], 0)

    def test_classify_accepts_only_evidence_of_the_latest_consumption(self):
        # The second layer behind the move to results/stale/: a pass or a verification recorded for an earlier
        # consumption never counts, even if its file were still in place.
        passing = {"verdict": "clean (control passed)"}
        evidence = {"latest": {c: 1 for c in probe.CONSUMERS},
                    "consumers": {c: {"ran": True, "tag": "valid", "stream_canary_hits": 0, "cmdline_hits": 0,
                                      "transient_unit_hits": 0} for c in probe.CONSUMERS},
                    "verified_sequences": {c: 1 for c in probe.CONSUMERS},
                    "leak_check": {"pattern_hits": 0, "printed_form_hits": 0, "masked": True}, "after_restart": None,
                    "keep": False, "captures": {"x.jsonl": {"canary": 0, "control": "found"}},
                    "controls": {"text": {"ok": True}}, "baseline": {"canary_hits": 0, "ok": True},
                    "passes": {n: {"ok": True, "sinks": {"S": passing}, "sequences": {c: 1 for c in probe.CONSUMERS}}
                               for n in ("1", "2")}, "user_run": None}
        self.assertEqual(harness.classify(evidence), ("zero", []))
        evidence["latest"] = {**evidence["latest"], "codex-exec": 2}
        result, reasons = harness.classify(evidence)
        self.assertEqual(result, "incomplete")
        self.assertIn("pass1_predates_the_latest_consumption", reasons)
        self.assertIn("tag_not_verified_for_the_latest_consumption:codex-exec", reasons)

    def test_a_re_consumed_consumer_invalidates_the_verification_and_scans_before_it(self):
        run, steps = self.full_run()
        self.assertEqual(self.last_receipt()["result"], "zero")
        code, out, err = self.harness("consume", "codex-exec", "--run", run)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.harness("verify", "--run", run)[0], 0)  # a fresh verify alone is not enough
        self.assertEqual(self.harness("report", "--run", run)[0], 1)
        receipt = self.last_receipt()
        self.assertEqual(receipt["result"], "incomplete")
        self.assertIn("pass1_missing", receipt["reasons"])
        self.assertTrue((self.run_dir(run) / "results" / "stale").is_dir())


@unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
class RestartVariantTests(CanaryCase):
    def test_kept_canary_serves_the_unit_again_after_a_restart(self):
        run = self.prepare("--keep-across-restart")
        directory = self.run_dir(run)
        self.assertEqual(directory, self.state / "native-agent-stack" / "canary" / "keep" / run)  # not the tmpfs
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        for step in (("controls", "--run", run), ("baseline", "--run", run)):
            self.assertEqual(self.harness(*step)[0], 0)
        self.assertEqual(self.harness("consume", "systemd-user-unit", "--after-restart", "--run", run)[0], 1)
        code, out, err = self.harness("consume", "systemd-user-unit", "--run", run)
        self.assertEqual(code, 0, out + err)
        self.assertTrue(self.store_file().exists())  # kept for the restart check
        self.assertIn("consume systemd-user-unit --after-restart --run " + run, out)
        with self.assertRaises(harness.Refused):  # nothing else may arm while the kept file is there
            harness.arm(self.context(), directory, "codex-exec")
        code, out, err = self.harness("consume", "systemd-user-unit", "--after-restart", "--run", run)
        self.assertEqual(code, 0, out + err)
        self.assertFalse(self.store_file().exists())
        after = json.loads((directory / "results" / "consume-systemd-user-unit-after-restart.json").read_text())
        self.assertEqual((after["leak_check"]["masked"], after["boot_changed"]), (True, False))  # same boot here
        self.assertEqual(self.harness("verify", "--run", run, "--consumer", "systemd-user-unit")[0], 0)
        self.assertEqual(self.harness("consume", "codex-exec", "--after-restart", "--run", run)[0], 2)
        self.assert_value_free(self.forbidden(run), self.all_output())


class DocumentedCommandTests(unittest.TestCase):
    """Amendment 15: every command documented for an agent or an operator passes today's guard.check."""

    def section(self) -> str:
        text = (ROOT / "docs/secret-storage.md").read_text()
        match = re.search(r"^## Proof run \(canary\)\n(.*?)(?=^## )", text, re.S | re.M)
        self.assertIsNotNone(match, "docs/secret-storage.md has no Proof run (canary) section")
        return match.group(1)

    def documented(self) -> list:
        commands = []
        for block in re.findall(r"```sh\n(.*?)```", self.section(), re.S):
            for line in block.splitlines():
                line = line.split("  #", 1)[0].strip()
                if line and not line.startswith("#"):
                    commands.append(line.replace("<id>", SAMPLE_RUN).replace("<model id>", "claude-sonnet-5-5"))
        return commands

    def workflow_commands(self) -> list:
        text = (TOOLS / "canary_workflow.js").read_text()
        return [c + SAMPLE_RUN + tail for c, tail in re.findall(r"'(python3 [^']*--run )' \+ run \+ '([^']*)'", text)]

    def test_documented_commands_pass_the_guard(self):
        commands = self.documented()
        self.assertGreaterEqual(len(commands), 10)
        decoy = harness.new_decoy()
        harness_commands = [harness.probe_command(SAMPLE_RUN, c) for c in probe.CONSUMERS]
        harness_commands += [harness.probe_command(SAMPLE_RUN, "systemd-user-unit", leak=True),
                             harness.decoy_command(SAMPLE_RUN, "subagent"), harness.user_run_command(SAMPLE_RUN),
                             harness.rtk_decoy_command(SAMPLE_RUN, decoy), f"echo {decoy} && false"]
        workflow = self.workflow_commands()
        self.assertEqual(len(workflow), 3)
        for command in commands + harness_commands + workflow:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))
                self.assertNotIn("CANARY_E2E_KEY", command)
        for command in commands:
            if command.startswith("python3 tools/credentials/canary_e2e.py "):
                harness.build_parser().parse_args(command.split()[2:])  # a real subcommand with real options

    def test_documented_order_covers_every_consumer(self):
        section = self.section()
        for consumer in probe.CONSUMERS:
            if consumer != "subagent":
                self.assertIn(f"consume {consumer} --run <id>", section)
        for phrase in ("cooperative", "not covered", "--leak-check", "scan --sink omniroute", "shell_snapshot",
                       "INCOMPLETE", "user manager", "container configurations", "rtk err"):
            self.assertIn(phrase, section)

    def test_workflow_script_dispatch_and_syntax(self):
        text = (TOOLS / "canary_workflow.js").read_text()
        calls = re.findall(r"\{ label: '[a-z]+'[^}]*\}", text)
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertIn("agentType: 'source-scout'", call)
            self.assertIn("model: 'sonnet'", call)
            self.assertIn("effort: 'max'", call)
        for forbidden in ("Date.now", "Math.random", "new Date()", "import("):
            self.assertNotIn(forbidden, text)
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not on PATH")
        checked = subprocess.run([node, str(ROOT / "examples/claude-native/workflows/check-syntax.mjs"),
                                  str(TOOLS / "canary_workflow.js")], capture_output=True, text=True, timeout=60)
        self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == "__main__":
    unittest.main()
