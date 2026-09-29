"""Tests for the canary proof: tools/credentials/canary_e2e.py, canary_probe.py, canary_sinks.json and canary_workflow.js.

Local integration checks, not upstream acceptance (docs/acceptance-evidence-policy.md). Every canary, decoy and key is a
synthetic value made at test time. The store, the run directory, the receipts and every sink live in temporary
directories named through XDG overrides inside the test process only. The consumers (claude, codex, systemd-run) and
journalctl, systemd-cat, systemctl and gh are stub executables first on PATH, and /proc is a fixture directory. No test
starts a Claude, Codex or OmniRoute session, calls the keyring, or reads a real store, journal, Loki, RTK or ai-memory
database; the stubs run the real key runner and the real probe against the temporary store.
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


# As in tests/test_credential_run.py: the runner refuses a host that pipes crash dumps, so there the stubs start it
# through a launcher that points CORE_PATTERN_FILE at a temporary file holding "core".
HOST_PIPES_CORES = os.environ.get("CREDENTIAL_RUN_TEST_LAUNCHER") == "1" or _host_hands_cores_to_a_collector()
LAUNCHER = ("import os, sys\n"
            f"sys.path[:0] = [{str(TOOLS)!r}, {str(ROOT / 'scripts')!r}]\n"
            "import credential_run\n"
            "credential_run.CORE_PATTERN_FILE = os.environ.pop('CORE_PATTERN_TEST_FILE')\n"
            "sys.exit(credential_run.main(sys.argv[1:]))\n")

STUB_HELPER = r'''
import hashlib, json, os, re, subprocess, sys, time
TOOLS = @TOOLS@
LAUNCHER = @LAUNCHER@
RUN = re.compile(r"--run (canary-[0-9]{8}t[0-9]{6}z-[0-9a-f]{6})")
ECHO = re.compile(r"echo (DCOYE2E[0-9a-f]{32}) && false")

def runner_argv(consumer, run, leak=False):
    command = [sys.executable, "-I", TOOLS + "/canary_probe.py", "--run", run, "--consumer", consumer]
    command += ["--leak-check"] if leak else []
    if os.environ.get("CORE_PATTERN_TEST_FILE"):
        return [sys.executable, "-I", "-S", "-c", LAUNCHER, "canary-e2e", "--", *command]
    return [sys.executable, "-I", TOOLS + "/credential_run.py", "canary-e2e", "--", *command]

def run_probe(consumer, run):
    result = subprocess.run(runner_argv(consumer, run), capture_output=True, text=True, timeout=60)
    return result.stdout + result.stderr

def harness_decoy(consumer, run):
    result = subprocess.run([sys.executable, TOOLS + "/canary_e2e.py", "decoy", "--run", run, "--consumer", consumer],
                            capture_output=True, text=True, timeout=60)
    return result.stdout.strip().split(": ", 1)[1]

def store_digest():
    path = os.path.join(os.environ["XDG_CONFIG_HOME"], "native-agent-stack", "canary-e2e.env")
    try:
        with open(path, "rb") as handle:
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

def names_seen(consumer):
    record("stub-env/" + consumer + ".json", json.dumps(sorted(os.environ)))
'''

STUB_CLAUDE = r'''
import json, sys
sys.path.insert(0, @BIN@)
from _stubs import *
if sys.argv[1:2] == ["--version"]:
    print("2.1.284 (Claude Code)")
    raise SystemExit(0)
prompt = sys.stdin.read()
run = RUN.search(prompt).group(1)
decoy = ECHO.search(prompt).group(1)
names_seen("fresh-claude-session")
lines = []
def emit(obj):
    text = json.dumps(obj)
    lines.append(text)
    print(text, flush=True)
emit({"type": "system", "subtype": "init", "model": "claude-sonnet-5-5-stub", "session_id": "s1"})
emit({"type": "user", "message": {"content": [{"type": "tool_result", "content": decoy, "is_error": True}]}})
before = store_digest()
emit({"type": "user", "message": {"content": [{"type": "tool_result", "content": run_probe("fresh-claude-session", run)}]}})
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
names_seen(consumer)
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
if "--version" in sys.argv:
    print("systemd 255 (255.4-1ubuntu8.17)")
    raise SystemExit(0)
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
if "--version" in sys.argv:
    print("systemd 255 (255.4-1ubuntu8.17)")
elif "show-environment" in sys.argv:
    print("HOME=/home/example\nPATH=/usr/bin\nLANG=C.UTF-8")
    if os.path.exists(os.environ["HOME"] + "/manager-has-canary-name"):
        print("CANARY_E2E_KEY=not-a-value-the-scanner-reads")
'''

STUB_GH = r'''
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


class CanaryCase(unittest.TestCase):
    """A temporary host: home, XDG directories, a 0700 runtime directory, stub executables and a fixture /proc."""

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
        self.env = {"PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", "HOME": str(self.home),
                    "XDG_CONFIG_HOME": str(self.config), "XDG_STATE_HOME": str(self.state),
                    "XDG_RUNTIME_DIR": str(self.runtime), "XDG_DATA_HOME": str(self.home / ".local" / "share"),
                    "XDG_CACHE_HOME": str(self.home / ".cache"), "CODEX_HOME": str(self.codex_home),
                    "CANARY_TEST_JOURNAL": str(self.journal), "LANG": "C.UTF-8"}
        if HOST_PIPES_CORES:
            self.env["CORE_PATTERN_TEST_FILE"] = str(self.core_pattern)
        self.outputs: list = []
        self.write_stubs()
        self.sinks_file = self.base / "sinks.json"
        self.write_sinks(self.default_sinks())
        self.clock_offset = 0.0

    # -- fixtures ------------------------------------------------------------------------------------------------------

    def write_stubs(self):
        helper = STUB_HELPER.replace("@TOOLS@", repr(str(TOOLS))).replace("@LAUNCHER@", repr(LAUNCHER))
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
                self.sink("T08-manager", "manager_environment", persisted=False),
                self.sink("T09-github", "github"),
                self.sink("T10-remote", "not_scanned", access="not_scanned"),
                self.sink("T11-covered", "covered"),
                self.sink("T12-proc", "during_consume", persisted=False),
                self.sink("T13-absent", "files", ["$HOME/no-such-directory"]),
                self.sink("T14-sudo-only", "files", ["$HOME/sudo-only"], access="sudo")]

    def write_sinks(self, sinks):
        table = {"schema_version": 1, "kind": "canary_sink_table",
                 "exclude": ["${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack", "$HOME/.ssh"],
                 "exclude_names": ["shell_snapshots"], "sinks": sinks}
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
        absent = self.run_probe(run, "fresh-claude-session", sentinels)
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
        harness.write_json(self.run_dir(run) / "results" / "consume-fresh-claude-session.json",
                           {"ran": True, "ended_epoch": time.time() - 5, "started_epoch": time.time() - 10})
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
        # excluded places hold the canary too and must never be read: the store, the run directory, shell_snapshots
        (self.home / "transcripts" / "shell_snapshots").mkdir()
        (self.home / "transcripts" / "shell_snapshots" / "s.sh").write_text(f"declare -x K={canary}\n")
        store = self.config / "native-agent-stack"
        store.mkdir(mode=0o700)
        (store / "other.env").write_text(f"export K={canary}\n")
        self.write_sinks([self.sink("L01-transcripts", "files", ["$HOME/transcripts"]),
                          self.sink("L02-databases", "sqlite", ["$HOME/dbs"]),
                          self.sink("L03-config", "files", ["$HOME/.config"]),
                          self.sink("L04-runtime", "files", [str(self.runtime)])])
        code, out, err = self.harness("scan", "--sink", "L01-transcripts", "--run", run)
        self.assertEqual(code, 1, out + err)
        self.assertIn("L01-transcripts [test/L01-transcripts]: LEAK; canary 1 (codex-exec=1)", out)
        code, out, err = self.harness("scan", "--sink", "L02-databases", "--run", run)
        self.assertEqual(code, 1)
        self.assertIn("LEAK; canary 1 (codex-exec=1)", out)  # found only after decompressing the cell
        for excluded in ("L03-config", "L04-runtime"):
            code, out, err = self.harness("scan", "--sink", excluded, "--run", run)
            self.assertEqual(code, 0, out + err)
            self.assertIn("canary 0", out)
        text = self.all_output()
        self.assertNotIn(str(leaked), text)
        self.assertNotIn("careless", text)
        self.assertNotIn(str(self.home), text)
        self.assert_value_free(self.forbidden(run), text)

    def test_omniroute_scan_refuses_without_tty(self):
        run = self.prepare()
        code, out, err = self.harness("scan", "--sink", "omniroute", "--run", run, tty=False)
        self.assertEqual(code, 2)
        self.assertIn("user-run only", out + err)
        self.assertFalse((self.run_dir(run) / "results" / "scan-user-run.json").exists())
        cli = subprocess.run([sys.executable, str(TOOLS / "canary_e2e.py"), "scan", "--sink", "omniroute", "--run", run],
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
        harness.write_json(self.run_dir(run) / "results" / "consume-omniroute-lane.json",
                           {"ran": True, "ended_epoch": time.time(), "started_epoch": time.time()})
        code, out, err = self.harness("scan", "--sink", "omniroute", "--run", run, tty=True)
        self.assertEqual(code, 0, out + err)
        self.assertIn("T07-call-logs [test/T07-call-logs]: clean (control passed); canary 0; controls omni=found", out)
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
        harness.arm(self.context(), self.run_dir(run), "codex-exec")
        first = self.store_file().read_bytes()
        with self.assertRaises(harness.Refused):
            harness.arm(self.context(), self.run_dir(run), "omniroute-lane")
        self.assertEqual(self.store_file().read_bytes(), first)
        code, out, err = self.harness("prepare")
        self.assertEqual(code, 1)  # a new run refuses while a canary file is in the store
        self.assertTrue(harness.disarm(self.context()))
        self.assertFalse(harness.disarm(self.context()))

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
        # stores that the guard denies to agents are scanned only by the user, in a terminal
        self.assertEqual({i for i, r in rows.items() if r["access"] == "user_run"},
                         {"S14-codex-shell-snapshots", "S25-omniroute-main", "S26-omniroute-fw", "M01-docker-config"})
        for identifier, row in rows.items():
            if row["access"] in ("agent", "sudo"):
                for template in row["paths"]:
                    self.assertIsNone(guard.check(f"cat {template}"), (identifier, template))
        self.assertEqual({i for i, r in rows.items() if r["async"]}, {"S17-ai-memory", "S21-agentsview", "S28-loki"})
        self.assertIn("never swept", rows["S02-claude-prompt-history"]["retention"])
        self.assertIn("90 days", rows["S18-rtk"]["retention"])
        self.assertIn("30 days", rows["S18-rtk"]["retention"])
        for template in ("$HOME/.ssh", "$HOME/.gnupg", "${XDG_CONFIG_HOME:-$HOME/.config}/gh",
                         "${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack",
                         "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.credentials.json", "${CODEX_HOME:-$HOME/.codex}/auth.json"):
            self.assertIn(template, table["exclude"])
        broken = copy.deepcopy(table)
        broken["sinks"][0]["controls"] = ["nonexistent"]
        broken["sinks"][1]["kind"] = "telepathy"
        self.assertEqual(len(harness.table_errors(broken)), 2)

    def test_split_roots_never_hand_an_excluded_path_to_a_scanner(self):
        tree = self.base / "tree"
        for part in ("a/keep.txt", "b/secret/x.env", "b/ok/y.txt", "c.txt"):
            (tree / part).parent.mkdir(parents=True, exist_ok=True)
            (tree / part).write_text("x")
        (tree / "link").symlink_to(tree / "b" / "secret")
        parts = harness.split_roots(tree, [Path(os.path.realpath(tree / "b" / "secret"))])
        self.assertEqual(sorted(str(p.relative_to(os.path.realpath(tree))) for p in parts), ["a", "b/ok", "c.txt"])
        self.assertEqual(harness.split_roots(tree / "b" / "secret" / "x.env", [Path(os.path.realpath(tree / "b"))]), [])


class LokiTests(CanaryCase):
    def test_loki_dump_matches_locally_and_the_push_carries_only_the_decoy(self):
        run = self.prepare()
        sets = harness.load_sets(self.run_dir(run))
        decoy = self.decoy(run, "loki")
        canary = self.canary(run, "codex-exec")
        seen = {"queries": [], "pushes": []}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                seen["queries"].append(self.path)
                body = {"status": "success", "data": {"result": [{"stream": {"service_name": "x"},
                        "values": [["1", f"line {decoy}"], ["2", f"leaked {canary}"], ["3", "ordinary"]]}]}}
                data = json.dumps(body).encode()
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
        url = f"http://127.0.0.1:{server.server_address[1]}"
        sink = self.sink("T-loki", "loki", controls=["loki"], url=url)
        self.assertTrue(harness.loki_push(self.context(), sink, decoy))
        result = harness.scan_sink(self.context(), self.run_dir(run), sink, sets, agent_pass=True, seen_git=set(),
                                   since_epoch=time.time() - 60)
        self.assertEqual((result["counts"]["d-loki"], result["counts"]["c-codex-exec"]), (1, 1))
        for query in seen["queries"]:
            self.assert_value_free(secret_forms(canary) + secret_forms(decoy), urllib.parse.unquote(query))
        self.assertEqual(len(seen["pushes"]), 1)
        self.assertIn(decoy.encode(), seen["pushes"][0])
        self.assert_value_free(secret_forms(canary), seen["pushes"][0])
        with self.assertRaises(harness.Refused):  # decoys go to a loopback Loki only
            harness.loki_push(self.context(), {**sink, "url": "http://example.com"}, decoy)


@unittest.skipUnless(HAS_RG and HAS_GIT, "the scanners need rg and git")
class EndToEndStubTests(CanaryCase):
    """The whole proof with stub consumers that run the real runner and the real probe against a temporary store."""

    ALLOWED = {
        "schema_version", "kind", "run", "recorded_at", "keep_across_restart", "checkout_revision", "versions",
        "versions.*", "consumers", "consumers.*", "consumers.*.ran", "consumers.*.started_at", "consumers.*.ended_at",
        "consumers.*.exit_code", "consumers.*.tag", "consumers.*.tag_channel", "consumers.*.model_id",
        "consumers.*.model_id_source", "consumers.*.stream_canary_hits", "consumers.*.cmdline_hits",
        "consumers.*.transient_unit_hits", "consumers.*.decoy_echoed", "after_restart", "leak_check",
        "leak_check.pattern_hits", "leak_check.printed_form_hits", "leak_check.markers", "leak_check.partial_markers",
        "leak_check.forms_printed", "leak_check.masked", "controls", "controls.*", "controls.*.found",
        "controls.*.after_removal", "controls.*.ok", "controls.*.in_main_file", "controls.*.in_wal", "baseline",
        "baseline.canary_hits", "baseline.sinks", "baseline.ok", "settle", "settle.arrival_seconds",
        "settle.arrival_seconds.*", "settle.pass1_delay_seconds", "settle.pass2_delay_seconds",
        "settle.max_wait_seconds", "passes", "passes.*", "passes.*.ran_at", "passes.*.ok", "passes.*.sinks",
        "passes.*.sinks.*", "passes.*.sinks.*.canary", "passes.*.sinks.*.canary_by_consumer",
        "passes.*.sinks.*.canary_by_consumer.*", "passes.*.sinks.*.controls", "passes.*.sinks.*.controls.*",
        "passes.*.sinks.*.verdict", "passes.*.sinks.*.proven_for", "passes.*.sinks.*.unreadable", "user_run",
        "user_run.ran", "user_run.ran_at", "user_run.ok", "user_run.sinks", "user_run.sinks.*",
        "user_run.sinks.*.canary", "user_run.sinks.*.canary_by_consumer", "user_run.sinks.*.canary_by_consumer.*",
        "user_run.sinks.*.controls", "user_run.sinks.*.controls.*", "user_run.sinks.*.verdict",
        "user_run.sinks.*.proven_for", "user_run.sinks.*.unreadable", "after_restart.ran", "after_restart.exit_code",
        "after_restart.boot_changed", "after_restart.masked", "after_restart.pattern_hits",
        "result", "reasons", "claim", "not_covered", "manager_environment",
        "manager_environment.canary_name_present", "manager_environment.inventory_names_present",
    }

    def key_paths(self, value, prefix=""):
        if isinstance(value, dict):
            for key, item in value.items():
                dynamic = (prefix in ("versions", "consumers", "controls", "passes", "settle.arrival_seconds")
                           or re.fullmatch(r"(passes\.\*|user_run)\.sinks"
                                           r"|(passes\.\*|user_run)\.sinks\.\*\.(canary_by_consumer|controls)", prefix))
                path = f"{prefix}.*" if dynamic else (f"{prefix}.{key}" if prefix else key)
                yield path
                yield from self.key_paths(item, path)

    def full_run(self):
        self.codex_config()
        (self.home / "dbs").mkdir()
        with sqlite3.connect(self.home / "dbs" / "notes.db") as connection:
            connection.execute("CREATE TABLE notes (body TEXT)")
            connection.execute("INSERT INTO notes VALUES ('nothing to see')")
        subprocess.run(["git", "init", "-q", str(self.home / "repo")], check=True)
        run = self.prepare()
        tags = {}
        steps = [("controls", "--run", run), ("baseline", "--run", run),
                 ("consume", "fresh-claude-session", "--run", run, "--timeout", "120")]
        for step in steps:
            code, out, err = self.harness(*step)
            self.assertEqual(code, 0, f"{step}: {out}{err}")

        def workflow_child():  # the Workflow tool's probe stage, emulated once the store holds this consumer's canary
            deadline = time.time() + 30
            while time.time() < deadline and not self.store_file().exists():
                time.sleep(0.02)
            env = {**self.env}
            command = [sys.executable, "-I", str(TOOLS / "canary_probe.py"), "--run", run, "--consumer", "workflow-child"]
            runner = ([sys.executable, "-I", "-S", "-c", LAUNCHER] if HOST_PIPES_CORES
                      else [sys.executable, "-I", str(TOOLS / "credential_run.py")])
            subprocess.run(runner + ["canary-e2e", "--", *command], env=env, capture_output=True, timeout=60)

        helper = threading.Thread(target=workflow_child)
        helper.start()
        code, out, err = self.harness("consume", "workflow-child", "--run", run, "--timeout", "60")
        helper.join()
        self.assertEqual(code, 0, out + err)
        for step in (("consume", "codex-exec", "--run", run), ("consume", "omniroute-lane", "--run", run),
                     ("consume", "systemd-user-unit", "--run", run)):
            code, out, err = self.harness(*step)
            self.assertEqual(code, 0, f"{step}: {out}{err}")
        for tag_file in (self.run_dir(run) / "tags").glob("*.tag"):
            tags[tag_file.stem] = tag_file.read_text().strip()
        forbidden = self.forbidden(run)
        code, out, err = self.harness("verify", "--run", run)
        self.assertEqual(code, 0, out + err)
        code, out, err = self.harness("settle", "--run", run, "--max-wait", "20", "--interval", "0.2")
        self.assertEqual(code, 0, out + err)
        early = self.harness("scan", "--pass", "1", "--run", run)
        self.clock_offset = 10 ** 6  # after both passes are due
        results = [early]
        for step in (("scan", "--pass", "1", "--run", run), ("scan", "--pass", "2", "--run", run),
                     ("report", "--run", run, "--model", "workflow-child=claude-sonnet-5-5")):
            results.append(self.harness(*step))
        return run, forbidden, tags, results

    def test_six_consumers_through_stubs_to_a_value_free_receipt(self):
        run, forbidden, tags, results = self.full_run()
        early, pass1, pass2, report = results
        self.assertEqual(early[0], 2, early[1] + early[2])  # a pass does not run before its measured due time
        self.assertIn("is due at", early[1] + early[2])
        self.assertEqual(pass1[0], 0, pass1[1] + pass1[2])
        self.assertEqual(pass2[0], 0, pass2[1] + pass2[2])
        self.assertEqual(report[0], 0, report[1] + report[2])
        self.assertEqual(set(tags), set(probe.CONSUMERS))
        directory = self.state / "native-agent-stack" / "canary"
        [receipt_path] = [p for p in directory.iterdir() if p.suffix == ".json"]
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
        self.assertIsNotNone(receipt["settle"]["arrival_seconds"]["T03-archive"])
        self.assertNotIn("T07-call-logs", pass1)  # user-run only
        self.assertNotIn("T14-sudo-only", pass1)  # only with --with-sudo
        self.assertFalse(receipt["user_run"]["ran"])
        self.assertIn("cooperative", receipt["claim"])
        self.assertIn("W03-wsl-swap-and-pagefile", receipt["not_covered"])
        # the receipt holds only allowlisted keys, and no canary, tag or pattern in any form
        for path in self.key_paths(receipt):
            self.assertIn(path, self.ALLOWED)
        self.assert_value_free(forbidden + [t.encode() for t in tags.values()] + [t[:16].encode() for t in tags.values()],
                               receipt_path.read_bytes())
        # nor any printed line or stderr of any subcommand
        self.assert_value_free(forbidden + [t.encode() for t in tags.values()] + [t[:16].encode() for t in tags.values()],
                               self.all_output())
        # the launch environments held no inventory name; the OmniRoute lane got only the loopback placeholder
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text())
        names = {n for e in inventory["entries"] for n in e["variables"] + e["optional_variables"]}
        for consumer in ("fresh-claude-session", "codex-exec", "omniroute-lane"):
            seen = set(json.loads((self.home / "stub-env" / f"{consumer}.json").read_text().splitlines()[-1]))
            expected = {"OMNIROUTE_API_KEY"} if consumer == "omniroute-lane" else set()
            self.assertEqual(seen & names, expected, consumer)
            self.assertNotIn("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", seen)
        self.assertFalse(self.store_file().exists())
        code, out, err = self.harness("cleanup", "--run", run)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sorted(p.name for p in directory.iterdir() if p.suffix == ".json"), [receipt_path.name])


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
        harness_commands = [harness.probe_command(SAMPLE_RUN, c) for c in probe.CONSUMERS]
        harness_commands += [harness.probe_command(SAMPLE_RUN, "systemd-user-unit", leak=True),
                             harness.decoy_command(SAMPLE_RUN, "subagent"), harness.user_run_command(SAMPLE_RUN),
                             f"echo {harness.new_decoy()} && false"]
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
        for phrase in ("cooperative", "not covered", "--leak-check", "scan --sink omniroute", "shell_snapshot"):
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
