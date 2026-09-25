"""macOS Gitleaks front end: structure, refusals, caps and the per-user lock.

Two evidence classes live here:

* structural validation - the script is present, executable and compiles,
  carries no personal home paths, ships the documented caps and exit codes,
  and lets a caller lower but never raise a cap. These run on every host; off
  macOS a scan is additionally asserted to be refused.
* local integration check - the footprint watchdog, runtime cap, per-user lock
  and exit-status propagation exercised on the macOS host running the suite,
  against stub "native" binaries (synthetic fixtures, not Gitleaks itself).

Every run points ECOSYSTEM_GITLEAKS_LOCK into a temporary directory, so the
suite never contends with a real scan for the host's per-user lock.
"""

import contextlib
import fcntl
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "adoption" / "tools" / "gitleaks-guarded-macos"
IS_MACOS = platform.system() == "Darwin"
# Built from fragments so this file can never match its own acceptance grep.
PERSONAL_HOME = re.compile("/(?:" + "home" + "|" + "Users" + ")/[A-Za-z0-9_.-]+")


def _load_guard():
    spec = importlib.util.spec_from_file_location(
        "gitleaks_guarded_macos", GUARD,
        loader=importlib.machinery.SourceFileLoader("gitleaks_guarded_macos", str(GUARD)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub(path, body):
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


class GuardStructureTests(unittest.TestCase):
    """Structural validation only; nothing here starts a scan."""

    def test_script_is_present_executable_and_compiles(self):
        self.assertTrue(GUARD.is_file(), f"{GUARD} is missing")
        self.assertTrue(os.access(GUARD, os.X_OK), f"{GUARD} is not executable")
        compile(GUARD.read_text(encoding="utf-8"), str(GUARD), "exec")

    def test_no_personal_home_paths(self):
        for path in (GUARD, Path(__file__)):
            with self.subTest(path=path.name):
                found = PERSONAL_HOME.findall(path.read_text(encoding="utf-8"))
                self.assertEqual(found, [], f"{path.name} contains personal home paths: {found}")

    def test_documented_caps_and_exit_codes(self):
        text = GUARD.read_text(encoding="utf-8")
        for token in ("MEMORY_MAX = 6 << 30", "RUNTIME_MAX = 600", "LOCK_WAIT_DEFAULT = 60",
                      "EXIT_BUSY, EXIT_REFUSED, EXIT_TIMEOUT, EXIT_MEMORY = 75, 78, 124, 137",
                      '"ecosystem-gitleaks.lock"', '"8.30.1"', "ri_phys_footprint",
                      "proc_listchildpids", "LOCK_EX | fcntl.LOCK_NB", "pass_fds=(lock,)"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_caps_can_be_lowered_but_never_raised(self):
        guard = _load_guard()
        self.assertEqual(guard.limits({}), (6 << 30, 600, 60))
        self.assertEqual(guard.limits({"ECOSYSTEM_JOB_MEMORY_MAX": "64G",
                                       "ECOSYSTEM_JOB_SECONDS": "9000"}), (6 << 30, 600, 60))
        self.assertEqual(guard.limits({"ECOSYSTEM_JOB_MEMORY_MAX": "512M",
                                       "ECOSYSTEM_JOB_SECONDS": "30",
                                       "ECOSYSTEM_GITLEAKS_LOCK_WAIT": "0"}), (512 << 20, 30, 0))
        for name, value in (("ECOSYSTEM_JOB_MEMORY_MAX", "0"), ("ECOSYSTEM_JOB_MEMORY_MAX", "6.5G"),
                            ("ECOSYSTEM_JOB_MEMORY_MAX", "6g"), ("ECOSYSTEM_JOB_MEMORY_MAX", "-1"),
                            ("ECOSYSTEM_JOB_SECONDS", "0"), ("ECOSYSTEM_JOB_SECONDS", "1.5"),
                            ("ECOSYSTEM_GITLEAKS_LOCK_WAIT", "-1")):
            with self.subTest(name=name, value=value), self.assertRaises(SystemExit) as raised, \
                    contextlib.redirect_stderr(io.StringIO()):
                guard.limits({name: value})
            self.assertEqual(raised.exception.code, 78)

    @unittest.skipIf(IS_MACOS, "the refusal branch applies off macOS")
    def test_scan_off_macos_is_refused_with_78(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            oracle = tmp / "stub-was-run"
            stub = _stub(tmp / "gitleaks", f": > {oracle}\n")
            env = dict(os.environ, GITLEAKS_NATIVE=str(stub),
                       ECOSYSTEM_GITLEAKS_LOCK=str(tmp / "scan.lock"))
            result = subprocess.run([str(GUARD), "dir", "."], env=env, capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, 78, result.stderr)
            self.assertIn("macOS only", result.stderr)
            self.assertFalse(oracle.exists(), "a scan started off macOS")


@unittest.skipUnless(IS_MACOS, "the watchdog and lock run on macOS only")
class GuardIntegrationTests(unittest.TestCase):
    """Local integration check on this macOS host, against stub native binaries."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.lock = self.tmp / "state" / "scan.lock"
        self.oracle = self.tmp / "stub-was-run"
        self.env = dict(os.environ, ECOSYSTEM_GITLEAKS_LOCK=str(self.lock))
        for name in ("ECOSYSTEM_JOB_MEMORY_MAX", "ECOSYSTEM_JOB_SECONDS",
                     "ECOSYSTEM_GITLEAKS_LOCK_WAIT"):
            self.env.pop(name, None)

    def guard(self, native, *arguments, timeout=60, **overrides):
        env = dict(self.env, GITLEAKS_NATIVE=str(native), **overrides)
        return subprocess.run([str(GUARD), *arguments], env=env, capture_output=True, text=True,
                              timeout=timeout)

    def hold_lock(self):
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.lock, os.O_RDONLY | os.O_CREAT, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(os.close, descriptor)
        return descriptor

    def test_version_execs_native_binary_without_lock_or_watchdog(self):
        stub = _stub(self.tmp / "gitleaks", f'printf "%s\\n" "$@" > {self.oracle}\n')
        result = self.guard(stub, "version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.oracle.read_text(encoding="utf-8").split(), ["version"])
        self.assertFalse(self.lock.exists(), "the fast path touched the per-user lock")

    def test_arguments_and_exit_statuses_are_preserved(self):
        stub = _stub(self.tmp / "gitleaks",
                     f'printf "%s\\n" "$@" > {self.oracle}\nexit "${{STUB_EXIT:-0}}"\n')
        for status in (0, 1, 3):
            with self.subTest(status=status):
                result = self.guard(stub, "git", "--pre-commit", "--staged", STUB_EXIT=str(status))
                self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual(self.oracle.read_text(encoding="utf-8").split(),
                         ["git", "--pre-commit", "--staged"])
        killed = _stub(self.tmp / "killed", "kill -TERM $$\n")
        self.assertEqual(self.guard(killed, "dir", ".").returncode, 143)

    def test_memory_cap_kills_the_whole_tree_with_137(self):
        grandchild = self.tmp / "grandchild.pid"
        allocate = ("import os, time; open(%r, 'w').write(str(os.getpid())); "
                    "block = bytearray(256 << 20); block[::4096] = bytes(len(block[::4096])); "
                    "time.sleep(60)") % str(grandchild)
        stub = _stub(self.tmp / "gitleaks", f'"{sys.executable}" -c "{allocate}"\nexit 0\n')
        started = time.monotonic()
        result = self.guard(stub, "dir", ".", ECOSYSTEM_JOB_MEMORY_MAX="64M")
        self.assertEqual(result.returncode, 137, result.stderr)
        self.assertIn("memory cap exceeded", result.stderr)
        self.assertLess(time.monotonic() - started, 30, "the cap did not stop the scan early")
        pid = int(grandchild.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            self.fail(f"the allocating grandchild {pid} survived the kill")

    def test_runtime_cap_stops_the_scan_with_124(self):
        stub = _stub(self.tmp / "gitleaks", "sleep 60\n")
        started = time.monotonic()
        result = self.guard(stub, "dir", ".", ECOSYSTEM_JOB_SECONDS="1")
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertIn("runtime cap of 1 s exceeded", result.stderr)
        self.assertLess(time.monotonic() - started, 15)

    def test_busy_lock_fails_with_75_before_the_scan_starts(self):
        stub = _stub(self.tmp / "gitleaks", f": > {self.oracle}\n")
        self.hold_lock()
        result = self.guard(stub, "dir", ".", ECOSYSTEM_GITLEAKS_LOCK_WAIT="0")
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertIn("another scan holds the per-user lock", result.stderr)
        self.assertFalse(self.oracle.exists(), "a scan started while the lock was held")

    def test_waiting_scan_starts_only_after_the_lock_is_released(self):
        stub = _stub(self.tmp / "gitleaks", f": > {self.oracle}\n")
        descriptor = self.hold_lock()
        env = dict(self.env, GITLEAKS_NATIVE=str(stub), ECOSYSTEM_GITLEAKS_LOCK_WAIT="20")
        waiting = subprocess.Popen([str(GUARD), "dir", "."], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            time.sleep(1.5)
            self.assertIsNone(waiting.poll(), "the scan did not wait for the lock")
            self.assertFalse(self.oracle.exists(), "a scan started while the lock was held")
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            _, stderr = waiting.communicate(timeout=20)
        finally:
            if waiting.poll() is None:
                waiting.kill()
                waiting.communicate()
        self.assertEqual(waiting.returncode, 0, stderr)
        self.assertIn("waiting up to 20 s", stderr)
        self.assertTrue(self.oracle.exists())

    def test_concurrent_scans_run_one_at_a_time(self):
        spans = self.tmp / "spans"
        stub = _stub(self.tmp / "gitleaks", f"echo start >> {spans}\nsleep 0.5\necho end >> {spans}\n")
        env = dict(self.env, GITLEAKS_NATIVE=str(stub), ECOSYSTEM_GITLEAKS_LOCK_WAIT="20")
        scans = [subprocess.Popen([str(GUARD), "dir", "."], env=env, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL) for _ in range(2)]
        self.assertEqual([scan.wait(timeout=30) for scan in scans], [0, 0])
        self.assertEqual(spans.read_text(encoding="utf-8").split(), ["start", "end"] * 2,
                         "the two scans overlapped")

    def test_the_running_scan_holds_the_lock(self):
        probe = ("import fcntl, os, sys; fd = os.open(sys.argv[1], os.O_RDONLY)\n"
                 "try:\n fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                 "except BlockingIOError:\n sys.exit(0)\nsys.exit(1)\n")
        script = self.tmp / "probe.py"
        script.write_text(probe, encoding="utf-8")
        stub = _stub(self.tmp / "gitleaks", f'exec "{sys.executable}" {script} {self.lock}\n')
        result = self.guard(stub, "dir", ".")
        self.assertEqual(result.returncode, 0, "the scan ran without the per-user lock held")

    def test_refusals_exit_78_before_any_scan(self):
        stub = _stub(self.tmp / "gitleaks", f": > {self.oracle}\n")
        (self.tmp / "state").mkdir()
        (self.tmp / "state" / "link.lock").symlink_to(self.tmp / "elsewhere.lock")
        read_only = self.tmp / "read-only"
        read_only.mkdir(mode=0o500)
        self.addCleanup(read_only.chmod, 0o700)
        cases = {
            "missing binary": (self.tmp / "absent", {}, "native binary is missing"),
            "native is the guard": (GUARD, {}, "points at this front end"),
            "symlinked lock": (stub, {"ECOSYSTEM_GITLEAKS_LOCK": str(self.tmp / "state" / "link.lock")},
                               "is a symbolic link"),
            "unusable lock": (stub, {"ECOSYSTEM_GITLEAKS_LOCK": str(read_only / "state" / "scan.lock")},
                              "is unavailable"),
            "relative lock": (stub, {"ECOSYSTEM_GITLEAKS_LOCK": "scan.lock"}, "must be absolute"),
            "invalid cap": (stub, {"ECOSYSTEM_JOB_MEMORY_MAX": "6.5G"}, "positive finite sizes"),
        }
        for name, (native, overrides, message) in cases.items():
            with self.subTest(case=name):
                result = self.guard(native, "dir", ".", **overrides)
                self.assertEqual(result.returncode, 78, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertIn("scan was not started", result.stderr)
        self.assertFalse(self.oracle.exists(), "a refused invocation started a scan")


if __name__ == "__main__":
    unittest.main()
