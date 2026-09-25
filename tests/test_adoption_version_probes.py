"""Declared, bounded version probes in both adoption bootstraps.

Found 2026-09-25: both bootstraps ended with a loop that ran `--version` on
every file in bin_dir with the caller's stdin, no bound and no comparison to
the pin. MCP Inspector 2.x has no version flag (its launcher forwards unknown
argv to the web UI, which then tries to spawn `--version` as a stdio server and
stays up), and context-mode and socraticode start their MCP stdio servers on an
unknown argument, so on an interactive terminal the report blocked forever.

The report now observes only the pins the run installed, each with the probe
declared in its pins file, runs exec probes with stdin from /dev/null in their
own process group under a wall-clock bound, reads npm-metadata probes without
running the package, lists every other bin_dir entry without running it, and
fails the run (exit 5) after writing the report when a probe fails.

The functional tests load only the report functions and the report step from
each script (never the install steps) and run them against fixture
executables: a server that forks a child and never exits, wrong and longer
versions, floors, stderr output, an npm shim, and a bin_dir entry that must
never run. They run under the host bash and, when BASH32_BINARY or a Mac's
/bin/bash provides one, under bash 3.2. No network, no installation.
"""

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "linux": ROOT / "adoption/bootstrap-linux.sh",
    "macos": ROOT / "adoption/bootstrap-macos.sh",
}
PINS = {
    "linux": ROOT / "adoption/pins-linux-x86_64.json",
    "macos": ROOT / "adoption/pins-macos-arm64.json",
}
PROBE_KEYS = {"method", "command", "args", "expect", "match", "timeout_seconds", "note"}
# No version flag: any other argument starts an MCP stdio server (and, for
# MCP Inspector, which no pin installs, the web UI).
SERVER_WITHOUT_VERSION_FLAG = {"context-mode", "socraticode", "mcp-inspector"}
SHARED_START = "version_probe_seconds=30\n"
SHARED_END = "  exit 5\nfi\n"
REPORT_START = "version_report_platform() {\n"


def shared_region(text: str) -> str:
    start = text.index(SHARED_START)
    return text[start:text.index(SHARED_END, start) + len(SHARED_END)]


def report_step(text: str) -> str:
    """The npm_package_name helper plus everything from the platform hook to the report's exit."""
    helper = re.search(r"^npm_package_name\(\) \{\n.*?^\}\n", text, re.M | re.S).group(0)
    start = text.index(REPORT_START)
    return helper + text[start:text.index(SHARED_END, start) + len(SHARED_END)]


def _find_bash32():
    for candidate in (os.environ.get("BASH32_BINARY", ""), "/bin/bash"):
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run([candidate, "--version"], capture_output=True, text=True, timeout=5)
        except OSError:
            continue
        if "version 3.2" in result.stdout:
            return candidate
    return None


BASH = shutil.which("bash")
BASH32 = _find_bash32()


class DeclaredProbeTests(unittest.TestCase):
    def test_every_pin_declares_a_supported_probe(self):
        for platform_id, path in PINS.items():
            for tool in json.loads(path.read_text())["tools"]:
                label = f"{platform_id} {tool['id']}"
                probe = tool.get("version_probe")
                self.assertIsInstance(probe, dict, f"{label}: no version_probe")
                self.assertLessEqual(set(probe), PROBE_KEYS, f"{label}: unknown version_probe keys")
                self.assertIn(probe["method"], {"exec", "npm-metadata"}, label)
                self.assertIn(probe.get("match", "exact"), {"exact", "minimum"}, label)
                if "expect" in probe:
                    self.assertTrue(isinstance(probe["expect"], str) and probe["expect"].strip(), label)
                if "timeout_seconds" in probe:
                    self.assertIsInstance(probe["timeout_seconds"], int, label)
                    self.assertTrue(30 < probe["timeout_seconds"] <= 600, f"{label}: timeout_seconds outside (30, 600]")
                if probe["method"] == "exec":
                    self.assertRegex(probe.get("command", ""), r"^[A-Za-z0-9._-]+$", label)
                    self.assertIsInstance(probe.get("args"), list, label)
                    self.assertTrue(all(isinstance(argument, str) for argument in probe["args"]), label)
                else:
                    self.assertEqual(tool["kind"], "npm", f"{label}: npm-metadata needs an npm pin")
                    self.assertNotIn("command", probe, label)
                    self.assertNotIn("args", probe, label)
                if probe.get("match") == "minimum" or "expect" in probe or "timeout_seconds" in probe or probe["method"] != "exec":
                    self.assertTrue(probe.get("note", "").strip(), f"{label}: a non-default probe says why")

    def test_servers_without_a_version_flag_are_never_executed(self):
        for platform_id, path in PINS.items():
            for tool in json.loads(path.read_text())["tools"]:
                probe = tool["version_probe"]
                if tool["id"] in SERVER_WITHOUT_VERSION_FLAG:
                    self.assertEqual(probe["method"], "npm-metadata", f"{platform_id} {tool['id']}")
                self.assertNotIn(probe.get("command"), {"context-mode", "socraticode", "mcp-inspector"},
                                 f"{platform_id} {tool['id']}")

    def test_floor_pins_compare_as_minimum(self):
        # claude-code's pin is a floor: its native launcher auto-updates.
        for platform_id, path in PINS.items():
            tools = {tool["id"]: tool for tool in json.loads(path.read_text())["tools"]}
            self.assertEqual(tools["claude-code"]["version_probe"].get("match"), "minimum", platform_id)


class ReportStructureTests(unittest.TestCase):
    def test_the_report_step_is_identical_in_both_scripts(self):
        linux, macos = (shared_region(SCRIPTS[key].read_text()) for key in ("linux", "macos"))
        self.assertEqual(linux, macos)

    def test_cleanup_stops_an_interrupted_probe_in_both_scripts(self):
        for platform_id, path in SCRIPTS.items():
            cleanup = cleanup_function(path.read_text())
            self.assertIn('for group in "${version_probe_pid:-}" "${version_watchdog_pid:-}"; do', cleanup, platform_id)
            self.assertIn('kill -KILL -- "-$group"', cleanup, platform_id)

    def test_no_script_runs_a_flag_against_every_bin_dir_entry(self):
        for platform_id, path in SCRIPTS.items():
            text = path.read_text()
            self.assertNotIn('"$installed_executable" --version', text, platform_id)
            self.assertIn('for id in ${installed_pin_ids[@]+"${installed_pin_ids[@]}"}; do', text, platform_id)
            # A kept native launcher (the Claude Code floor) returns early from
            # install_pin, so the pin must be recorded before that return.
            self.assertIn('  installed_pin_ids+=("$id")\n  [[ -z "$native_floor_kept" ]] || return 0\n', text, platform_id)
            self.assertIn('"$@" </dev/null >"$stdout_file" 2>"$stderr_file" 9>&- &', text, platform_id)
            self.assertIn('version_report="$ecosystem_root/installed-versions.txt"', text, platform_id)


def cleanup_function(text: str) -> str:
    return re.search(r"^cleanup\(\) \{\n.*?^\}\n", text, re.M | re.S).group(0)


# The bootstrap's own lock and signal setup, before its report step runs:
# Linux holds a flock on descriptor 9, macOS a lock directory plus
# INT/TERM/HUP traps that exit through cleanup.
LOCK_SETUP = {
    "linux": ('exec 9>"$ecosystem_root/bootstrap.lock"\n'
              'flock -n 9\n'
              "trap cleanup EXIT\n"),
    "macos": ('pending_migration_prefix=""\npending_migration_dest=""\n'
              'lock_dir="$ecosystem_root/bootstrap.lock.d"\nmkdir "$lock_dir"\nlock_held=1\n'
              "trap cleanup EXIT\ntrap 'exit 130' INT\ntrap 'exit 143' TERM\ntrap 'exit 129' HUP\n"),
}


class ProbeRun:
    """Runs one script's cleanup trap, lock setup and report step against a fixture install root."""

    def __init__(self, test: unittest.TestCase, shell: str, platform_id: str, seconds: int = 2):
        self.directory = Path(tempfile.mkdtemp(prefix="version-probe-test-"))
        test.addCleanup(shutil.rmtree, self.directory, True)
        self.eco = self.directory / "eco"
        self.bin = self.eco / "bin"
        self.markers = self.directory / "markers"
        for folder in (self.bin, self.eco / "staging.test", self.markers):
            folder.mkdir(parents=True)
        self.pins = self.directory / "pins.json"
        text = SCRIPTS[platform_id].read_text()
        # Sourcing runs the report step itself, so the bound is shortened in
        # the loaded copy rather than overridden afterwards.
        functions = self.directory / "report.sh"
        functions.write_text(report_step(text).replace(SHARED_START, f"version_probe_seconds={seconds}\n", 1))
        setup = LOCK_SETUP[platform_id] if platform_id == "macos" or shutil.which("flock") else "trap cleanup EXIT\n"
        self.driver = self.directory / "driver.sh"
        self.driver.write_text(
            "set -Eeuo pipefail\n"
            f"ecosystem_root='{self.eco}'\nbin_dir=\"$ecosystem_root/bin\"\n"
            "stage_dir=\"$ecosystem_root/staging.test\"\n"
            f"pins_path='{self.pins}'\nprofile_id=test\nmacos_version=15.6\nPRETTY_NAME=test\n"
            + cleanup_function(text) + setup +
            "installed_pin_ids=()\n"
            'for id in "$@"; do installed_pin_ids+=("$id"); done\n'
            f". '{functions}'\n"
        )
        self.shell = shell

    def executable(self, name: str, body: str, path: Path = None):
        path = path or self.bin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)

    def start(self, ids):
        # Keep the child's stdin open for the whole run, like an interactive
        # terminal: the old loop blocked exactly there.
        read_end, self.stdin_writer = os.pipe()
        self.started = time.monotonic()
        try:
            process = subprocess.Popen([self.shell, str(self.driver), *ids], stdin=read_end, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, start_new_session=True)
            self.session = process.pid
            return process
        finally:
            os.close(read_end)

    def run(self, ids):
        process = self.start(ids)
        try:
            stdout, stderr = process.communicate(timeout=120)
        finally:
            os.close(self.stdin_writer)
        return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr), time.monotonic() - self.started

    def report(self) -> str:
        return (self.eco / "installed-versions.txt").read_text()

    def pid(self, marker: str) -> int:
        return int((self.markers / marker).read_text())


def process_alive(pid: int) -> bool:
    """True while pid runs; a zombie awaiting its reaper counts as gone."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    status = Path(f"/proc/{pid}/status")
    try:
        return "\nState:\tZ" not in status.read_text()
    except OSError:
        return not status.parent.parent.is_dir()  # no /proc (macOS): trust kill


def exec_pin(identifier, version, command=None, **probe):
    return {"id": identifier, "version": version, "kind": "tarball",
            "version_probe": {"method": "exec", "command": command or identifier, "args": ["--version"], **probe}}


def npm_pin(identifier, version):
    return {"id": identifier, "version": version, "kind": "npm",
            "url": f"https://registry.npmjs.org/{identifier}/-/{identifier}-{version}.tgz",
            "version_probe": {"method": "npm-metadata"}}


def cases(markers: Path):
    """(pin, body of bin/<command> or None, expected start of the result line)."""
    return [
        (exec_pin("good", "1.2.3"), 'echo "good 1.2.3"\n', "verified (exact 1.2.3)"),
        # Like context-mode and socraticode: serves stdin and exits only at
        # its EOF, so it answers only when the probe's stdin is closed.
        (exec_pin("eof-reader", "1.4.0"), 'cat >/dev/null\necho "eof-reader 1.4.0"\n', "verified (exact 1.4.0)"),
        # A server that forks a child, reads stdin and never exits.
        (exec_pin("server", "1.0.0"),
         f'echo $$ > "{markers}/server"\nsleep 300 &\necho $! > "{markers}/server-child"\ncat >/dev/null\n'
         "exec sleep 300\n", "FAILED (no exit within 2s; its process group was killed)"),
        # Answers at once but leaves a child behind in its group.
        (exec_pin("forker", "1.0.0"),
         f'sleep 300 &\necho $! > "{markers}/forker-child"\necho "forker 1.0.0"\n', "verified (exact 1.0.0)"),
        # Records whether the bootstrap lock's descriptor 9 reached the probe.
        (exec_pin("lock-fd", "1.0.0"),
         f'if [ -e /proc/$$/fd/9 ]; then echo open; elif [ -d /proc/$$ ]; then echo closed; else echo unknown; fi'
         f' > "{markers}/lock-fd"\necho "lock-fd 1.0.0"\n', "verified (exact 1.0.0)"),
        (exec_pin("wrong", "1.0.0"), 'echo "wrong 9.9.9"\n', "FAILED (output does not report exact 1.0.0)"),
        (exec_pin("longer", "1.2.3"), 'echo "longer 1.2.30"\n', "FAILED (output does not report exact 1.2.3)"),
        (exec_pin("prefixed", "1.2.3"), 'echo "prefixed 11.2.3"\n', "FAILED (output does not report exact 1.2.3)"),
        (exec_pin("unescaped", "1.2.3"), 'echo "unescaped 1x2x3"\n', "FAILED (output does not report exact 1.2.3)"),
        (exec_pin("failing", "1.0.0"), 'echo "failing 1.0.0"\nexit 3\n', "FAILED (exit 3)"),
        (exec_pin("floor-low", "2.1.0", match="minimum"), 'echo "2.0.9 (x)"\n',
         "FAILED (output does not report minimum 2.1.0)"),
        (exec_pin("floor-high", "2.9.9", match="minimum"), 'echo "2.10.0 (x)"\n', "verified (minimum 2.9.9)"),
        (exec_pin("floor-equal", "2.1.280", match="minimum"), 'echo "2.1.280 (Claude Code)"\n',
         "verified (minimum 2.1.280)"),
        (exec_pin("floor-short", "2.1.0", match="minimum"), 'echo "tool 2.1"\n', "verified (minimum 2.1.0)"),
        # The first dotted version is the tool's own, not a later dependency's.
        (exec_pin("floor-first", "2.1.0", match="minimum"), 'echo "2.0.9 (node 22.1.0)"\n',
         "FAILED (output does not report minimum 2.1.0)"),
        (exec_pin("stderr-build", "b11057", expect="build 11057"),
         'echo "version: 0.4.1-dev (build 11057, commit abc)" >&2\n', "verified (exact build 11057)"),
        (exec_pin("absent", "1.0.0", command="not-installed"), None, "FAILED (exit "),
        # Answers after the 2 s default bound, within its own declared bound.
        (exec_pin("slow-first-launch", "3.1.0", timeout_seconds=8), 'sleep 3\necho "slow 3.1.0"\n',
         "verified (exact 3.1.0)"),
        (npm_pin("npm-good", "1.0.0"), None, "verified (exact 1.0.0)"),
        (npm_pin("npm-stale", "1.0.0"), None, "FAILED (npm reports 0.9.0, pinned 1.0.0)"),
        (npm_pin("npm-missing", "1.0.0"), None, "FAILED (npm reports no installed package, pinned 1.0.0)"),
        ({"id": "undeclared", "version": "1.0.0", "kind": "tarball"}, None,
         "FAILED (no supported version_probe in pins.json)"),
    ]


def parse_results(report: str) -> dict:
    results, current = {}, None
    for line in report.splitlines():
        if line.startswith("-- "):
            current = line.split()[1]
        elif line.startswith("result: "):
            results[current] = line[len("result: "):]
    return results


class ReportBehaviorMixin:
    shell = None
    platform_id = None

    def fixture(self, seconds: int = 2):
        run = ProbeRun(self, self.shell, self.platform_id, seconds)
        self.cases = cases(run.markers)
        run.pins.write_text(json.dumps({"tools": [pin for pin, _, _ in self.cases]}))
        for pin, body, _ in self.cases:
            if body is not None:
                run.executable(pin["version_probe"]["command"], body)
        # The npm-metadata probe must ask about this pin's own prefix; npm ls
        # exits 1 for tree problems while still printing the version.
        run.executable("npm", f"""prefix=""; last=""
while [ $# -gt 0 ]; do
  case "$1" in --prefix) prefix="$2"; shift 2 ;; *) last="$1"; shift ;; esac
done
case "$last:$prefix" in
  "npm-good:{run.eco}/tools/npm-good-1.0.0") echo '{{"dependencies":{{"npm-good":{{"version":"1.0.0"}}}}}}'; exit 1 ;;
  "npm-stale:{run.eco}/tools/npm-stale-1.0.0") echo '{{"dependencies":{{"npm-stale":{{"version":"0.9.0"}}}}}}' ;;
  *) echo '{{}}' ;;
esac
""")
        # Other bin_dir entries, including a live link into tools/ like every
        # real install's, are listed and never run.
        for name in ("unrelated", "linked"):
            target = run.bin / name if name == "unrelated" else run.eco / "tools/linked-1.0.0/bin/linked"
            run.executable(name, f': > "{run.markers}/{name}-ran"\ncat >/dev/null\nsleep 300\n', target)
        (run.bin / "linked").symlink_to(run.eco / "tools/linked-1.0.0/bin/linked")
        (run.bin / "dangling").symlink_to(run.eco / "tools/gone-1.0.0/bin/gone")
        return run

    def assert_gone(self, pid: int, what: str):
        deadline = time.monotonic() + 5
        while process_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertFalse(process_alive(pid), what)

    def assert_session_empty(self, session: int):
        # The driver led its own session; after it exits nothing it started
        # (probe, probe child, watchdog or the watchdog's sleep) may remain.
        deadline = time.monotonic() + 5
        while True:
            left = subprocess.run(["pgrep", "-s", str(session)], capture_output=True, text=True).stdout.split()
            left = [pid for pid in left if process_alive(int(pid))]
            if not left or time.monotonic() > deadline:
                break
            time.sleep(0.1)
        self.assertEqual(left, [], "processes from the run's session outlived it")

    def test_every_probe_is_bounded_classified_and_nothing_else_runs(self):
        run = self.fixture()
        ids = [pin["id"] for pin, _, _ in self.cases]
        result, elapsed = run.run(ids)
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        # One 2 s bound plus the 2 s KILL grace, not the old unbounded wait.
        self.assertLess(elapsed, 30)
        report = run.report()
        results = parse_results(report)
        self.assertEqual(list(results), ids)
        for pin, _, expected in self.cases:
            self.assertTrue(results[pin["id"]].startswith(expected), f"{pin['id']}: {results[pin['id']]}")
        failed = [pin["id"] for pin, _, expected in self.cases if expected.startswith("FAILED")]
        self.assertIn(f"summary: {len(ids) - len(failed)} verified, {len(failed)} failed", report)
        self.assertIn(f"Version check failed for: {' '.join(failed)}.", result.stderr)
        self.assertIn("Stopped before the PATH hint and --configure-claude-user-profile", result.stderr)
        self.assertIn("unrelated -> (file)", report)
        self.assertIn("linked -> tools/linked-1.0.0/bin/linked\n", report)
        self.assertIn("dangling -> tools/gone-1.0.0/bin/gone (missing)", report)
        self.assertFalse((run.markers / "unrelated-ran").exists())
        self.assertFalse((run.markers / "linked-ran").exists())
        self.assert_gone(run.pid("server-child"), "the server's forked child survived the bound")
        self.assert_gone(run.pid("forker-child"), "a child left by a probe that exited survived it")
        self.assertIn((run.markers / "lock-fd").read_text().strip(), {"closed", "unknown"})
        self.assert_session_empty(run.session)

    @unittest.skipUnless(shutil.which("pgrep"), "pgrep unavailable")
    def test_fast_probes_leave_no_watchdog_timer_behind(self):
        # A probe that exits at once (here: a missing command) races its
        # watchdog's start-up; stopping the watchdog must also stop the sleep
        # it may already have forked, under macOS's TERM trap too.
        run = ProbeRun(self, self.shell, self.platform_id, seconds=30)
        pins = [exec_pin(f"gone-{index}", "1.0.0") for index in range(20)]
        run.pins.write_text(json.dumps({"tools": pins}))
        result, elapsed = run.run([pin["id"] for pin in pins])
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertLess(elapsed, 25)
        self.assert_session_empty(run.session)

    def test_all_verified_exits_zero_and_writes_the_report(self):
        run = self.fixture()
        ids = [pin["id"] for pin, _, expected in self.cases if expected.startswith("verified")]
        result, _ = run.run(ids)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"summary: {len(ids)} verified, 0 failed", run.report())
        self.assertEqual(result.stdout.split("\n", 1)[1], run.report())

    def test_an_interrupt_during_a_probe_stops_it_and_frees_the_lock(self):
        # A terminal's Ctrl-C reaches only the bootstrap's own process group;
        # the probe and watchdog run in their own, so cleanup must stop them.
        run = self.fixture(seconds=30)
        process = run.start(["server"])
        try:
            deadline = time.monotonic() + 20
            while not (run.markers / "server-child").exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            os.killpg(process.pid, signal.SIGINT)
            _, stderr = process.communicate(timeout=20)
        finally:
            os.close(run.stdin_writer)
        self.assertLess(time.monotonic() - run.started, 25, "the interrupt waited for the 30 s bound")
        self.assertNotIn("Killed", stderr, "bash printed a job notice for the stopped probe")
        self.assert_session_empty(run.session)
        self.assert_gone(run.pid("server"), "the interrupted probe kept running")
        self.assert_gone(run.pid("server-child"), "the interrupted probe's child kept running")
        if self.platform_id == "macos":
            self.assertFalse((run.eco / "bootstrap.lock.d").exists())
        elif shutil.which("flock"):
            relock = subprocess.run(["flock", "-n", str(run.eco / "bootstrap.lock"), "true"], timeout=10)
            self.assertEqual(relock.returncode, 0, "the bootstrap lock is still held")


def behavior_case(platform_id: str, shell, label: str):
    reason = f"no {label} binary (set BASH32_BINARY, or run on a Mac)" if label == "bash 3.2" else "bash unavailable"
    return unittest.skipUnless(shell, reason)(type(
        f"{platform_id.capitalize()}ReportUnder{label.replace(' ', '').replace('.', '')}Tests",
        (ReportBehaviorMixin, unittest.TestCase),
        {"shell": shell, "platform_id": platform_id},
    ))


LinuxReportUnderBashTests = behavior_case("linux", BASH, "bash")
MacosReportUnderBashTests = behavior_case("macos", BASH, "bash")
LinuxReportUnderBash32Tests = behavior_case("linux", BASH32, "bash 3.2")
MacosReportUnderBash32Tests = behavior_case("macos", BASH32, "bash 3.2")


if __name__ == "__main__":
    unittest.main()
