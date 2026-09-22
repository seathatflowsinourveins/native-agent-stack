"""Portable guarded runners: structure, refusal, and host containment.

Two evidence classes live here and are labelled at each assertion:

* structural validation - ShellCheck, absence of personal home paths, strict
  mode, and the usage exit code. These prove artifact consistency only.
* local integration check - the containment behaviour actually exercised on the
  host running the suite. The suite never skips it; it takes one of two
  branches and prints which one, because a host without a native
  ``systemd --user`` bus can only demonstrate the refusal property.
"""

import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "adoption" / "tools"
BOUNDED_RUN = TOOLS / "ecosystem-bounded-run"
GITLEAKS_GUARDED = TOOLS / "gitleaks-guarded"
SCRIPTS = (BOUNDED_RUN, GITLEAKS_GUARDED)
SHELLCHECK = shutil.which("shellcheck")

# Built from fragments so this file can never match its own acceptance grep.
PERSONAL_HOME = re.compile("/(?:" + "home" + "|" + "Users" + ")/[A-Za-z0-9_.-]+")
# The sources ship ``set -euo pipefail`` and are copied byte-for-byte, so this
# asserts the bytes actually shipped. Neither script installs an ERR trap, so the
# absent ``-E`` is behaviourally inert here; adding it would break the
# byte-fidelity guarantee the provenance section records. A future upstream sync
# that does add ``-E`` must update this line deliberately.
STRICT_MODE = re.compile(r"^set -euo pipefail$", re.M)

RUNTIME_BUS = Path(f"/run/user/{os.getuid()}/bus")


def _user_scope_available():
    """True when this host can actually place a job in a systemd user scope."""
    if not Path("/sys/fs/cgroup/cgroup.controllers").is_file():
        return False
    try:
        if not stat.S_ISSOCK(os.stat(RUNTIME_BUS).st_mode):
            return False
    except OSError:
        return False
    probe = subprocess.run(
        ["systemd-run", "--user", "--scope", "true"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=60, check=False,
    )
    return probe.returncode == 0


CONTAINMENT_AVAILABLE = _user_scope_available()


def _run(argv, **kwargs):
    return subprocess.run(
        argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=120, check=False, **kwargs,
    )


class GuardedRunnerStructureTests(unittest.TestCase):
    """Structural validation only; nothing here executes a contained job."""

    def test_scripts_are_present_and_executable(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                self.assertTrue(script.is_file(), f"{script} is missing")
                self.assertTrue(os.access(script, os.X_OK), f"{script} is not executable")

    @unittest.skipUnless(SHELLCHECK, "native shellcheck unavailable; CI installs the pinned analyzer")
    def test_shellcheck_is_clean_at_style_severity(self):
        result = _run([SHELLCHECK, "-S", "style", str(BOUNDED_RUN), str(GITLEAKS_GUARDED)])
        self.assertEqual(
            result.returncode, 0,
            f"shellcheck -S style reported findings:\n{result.stdout}{result.stderr}",
        )

    def test_no_personal_home_paths(self):
        for path in (BOUNDED_RUN, GITLEAKS_GUARDED, TOOLS / "README.md", Path(__file__)):
            with self.subTest(path=path.name):
                found = PERSONAL_HOME.findall(path.read_text(encoding="utf-8"))
                self.assertEqual(found, [], f"{path.name} contains personal home paths: {found}")

    def test_strict_mode_is_enabled(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                text = script.read_text(encoding="utf-8")
                self.assertRegex(text, STRICT_MODE)

    def test_guarded_gitleaks_resolves_runner_beside_itself(self):
        text = GITLEAKS_GUARDED.read_text(encoding="utf-8")
        self.assertIn('gitleaks_native="${GITLEAKS_NATIVE:-', text)
        self.assertIn('${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}', text)
        self.assertIn('BASH_SOURCE[0]', text)
        self.assertIn("/ecosystem-bounded-run", text)

    def test_documented_limits_and_exit_codes_are_unchanged(self):
        bounded = BOUNDED_RUN.read_text(encoding="utf-8")
        guarded = GITLEAKS_GUARDED.read_text(encoding="utf-8")
        for token in ("ECOSYSTEM_JOB_MEMORY_HIGH:-4G", "ECOSYSTEM_JOB_MEMORY_MAX:-6G",
                      "ECOSYSTEM_JOB_SWAP_MAX:-0", "ECOSYSTEM_JOB_SECONDS:-600",
                      "ECOSYSTEM_JOB_TASKS_MAX:-256", "exit 64", "exit 78",
                      "/usr/bin/systemd-run", "/usr/bin/systemctl", "/usr/bin/timeout"):
            with self.subTest(token=token):
                self.assertIn(token, bounded)
        for token in ("/usr/bin/flock", "--conflict-exit-code 75", "exit 78",
                      "ECOSYSTEM_JOB_MEMORY_HIGH=4G", "ECOSYSTEM_JOB_MEMORY_MAX=6G"):
            with self.subTest(token=token):
                self.assertIn(token, guarded)

    def test_usage_error_exits_64(self):
        result = _run([str(BOUNDED_RUN)])
        self.assertEqual(result.returncode, 64, result.stderr)
        self.assertIn("Usage: ecosystem-bounded-run", result.stderr)


class GuardedGitleaksFastPathTests(unittest.TestCase):
    """Local integration check: ``version`` execs the native binary directly."""

    def test_version_execs_native_binary_without_the_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub_oracle = tmp / "stub-was-run"
            runner_oracle = tmp / "runner-was-invoked"

            stub = tmp / "gitleaks-stub"
            stub.write_text(
                "#!/usr/bin/env bash\n"
                f"printf '%s\\n' \"$@\" > {stub_oracle}\n"
                "exit 0\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)

            # An instrumented stand-in for the runner: reaching it at all is the
            # failure we are testing for, so it only records that it was called.
            sentinel_runner = tmp / "ecosystem-bounded-run"
            sentinel_runner.write_text(
                "#!/usr/bin/env bash\n"
                f"printf 'invoked\\n' > {runner_oracle}\n"
                "exit 0\n",
                encoding="utf-8",
            )
            sentinel_runner.chmod(0o755)

            # Byte-for-byte copy of the owned script, so line 6 resolves the
            # sentinel beside it rather than the real runner.
            guarded = tmp / "gitleaks-guarded"
            guarded.write_bytes(GITLEAKS_GUARDED.read_bytes())
            guarded.chmod(0o755)

            environment = dict(os.environ, GITLEAKS_NATIVE=str(stub))
            result = _run([str(guarded), "version"], env=environment)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(stub_oracle.is_file(), "native binary was not executed")
            self.assertEqual(stub_oracle.read_text(encoding="utf-8").split(), ["version"])
            self.assertFalse(
                runner_oracle.exists(),
                "the containment runner was invoked for a non-scanning subcommand",
            )

    def test_missing_native_binary_refuses_with_78(self):
        with tempfile.TemporaryDirectory() as tmp:
            environment = dict(os.environ, GITLEAKS_NATIVE=str(Path(tmp) / "absent"))
            result = _run([str(GITLEAKS_GUARDED), "version"], env=environment)
            self.assertEqual(result.returncode, 78, result.stdout + result.stderr)
            self.assertIn("native binary or containment runner is missing", result.stderr)


def _write_stub(path, oracle):
    """An executable that records the arguments it was given, then succeeds."""
    path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$@\" > {oracle}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


class GuardedGitleaksSymlinkInstallTests(unittest.TestCase):
    """Local integration check of the documented symlink install boundary.

    ``${BASH_SOURCE[0]}`` is the invocation path and is *not* symlink-resolved,
    so a ``gitleaks`` link only finds the runner when the link sits in the same
    directory as ``ecosystem-bounded-run``. The README states that boundary;
    these two tests measure both sides of it so the claim cannot rot.
    """

    def _lay_out(self, tmp):
        stub_oracle = tmp / "stub-was-run"
        stub = tmp / "gitleaks-stub"
        _write_stub(stub, stub_oracle)

        runner_oracle = tmp / "runner-was-invoked"
        sentinel_runner = tmp / "ecosystem-bounded-run"
        _write_stub(sentinel_runner, runner_oracle)

        guarded = tmp / "gitleaks-guarded"
        guarded.write_bytes(GITLEAKS_GUARDED.read_bytes())
        guarded.chmod(0o755)
        return stub, stub_oracle, guarded

    def test_symlink_beside_the_runner_resolves_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub, stub_oracle, guarded = self._lay_out(tmp)

            # Exactly the README's `ln -sfn` recipe: link and runner share a dir.
            link = tmp / "gitleaks"
            link.symlink_to(guarded)

            result = _run([str(link), "version"],
                          env=dict(os.environ, GITLEAKS_NATIVE=str(stub)))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(stub_oracle.is_file(), "native binary was not executed")

    def test_symlink_from_another_directory_refuses_with_78(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub, stub_oracle, guarded = self._lay_out(tmp)

            elsewhere = tmp / "elsewhere"
            elsewhere.mkdir()
            link = elsewhere / "gitleaks"
            link.symlink_to(guarded)

            # The native binary is present and executable, so the runner beside
            # the link is the only thing missing.
            result = _run([str(link), "version"],
                          env=dict(os.environ, GITLEAKS_NATIVE=str(stub)))
            self.assertEqual(result.returncode, 78, result.stdout + result.stderr)
            self.assertIn("native binary or containment runner is missing", result.stderr)
            self.assertFalse(
                stub_oracle.exists(),
                "a scan path was entered even though the runner could not be found",
            )


class BoundedRunContainmentTests(unittest.TestCase):
    """Branch-aware local integration check; never skipped, always reported."""

    def _list_units(self):
        result = _run(["systemctl", "--user", "list-units",
                       "ecosystem-job-*", "--all", "--no-legend"])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def _wait_for_collection(self, deadline=15.0):
        """Return (seconds, listing); seconds is None when scopes survived."""
        started = time.monotonic()
        while True:
            listing = self._list_units()
            elapsed = time.monotonic() - started
            if not listing.strip():
                return elapsed, listing
            if elapsed > deadline:
                return None, listing
            time.sleep(0.02)

    def _live_tasks(self, listing):
        """Units from ``listing`` that still hold at least one process."""
        busy = []
        for line in listing.splitlines():
            unit = line.split()[0] if line.split() else ""
            if not unit.endswith(".scope"):
                continue
            shown = _run(["systemctl", "--user", "show", unit,
                          "-p", "TasksCurrent", "-p", "SubState", "--value"]).stdout
            fields = shown.split()
            tasks = next((f for f in fields if f.isdigit()), None)
            if tasks is not None and int(tasks) > 0:
                busy.append(f"{unit} TasksCurrent={tasks}")
        return busy

    def test_containment_or_refusal(self):
        if CONTAINMENT_AVAILABLE:
            print("\n[branch] containment: cgroup v2 and a native systemd --user bus are present")

            failing = _run([str(BOUNDED_RUN), "sh", "-c", "exit 3"])
            self.assertEqual(failing.returncode, 3, failing.stdout + failing.stderr)

            succeeding = _run([str(BOUNDED_RUN), "true"])
            self.assertEqual(succeeding.returncode, 0, succeeding.stdout + succeeding.stderr)

            # `--collect` removes the scope asynchronously and the unit object
            # can outlive its cgroup by a long, unbounded interval (measured on
            # this host from 0.03s to over 30s for the same command). The
            # property that matters is that no *process* survives the runner, so
            # a surviving unit only fails when it still holds tasks.
            settled, listing = self._wait_for_collection()
            if settled is None:
                busy = self._live_tasks(listing)
                self.assertEqual(
                    busy, [],
                    "a transient scope still holds live processes after the job "
                    f"returned:\n{listing}")
                print("[branch] scope units awaiting systemd GC hold no tasks "
                      f"(not collected within 15s):\n{listing.rstrip()}")
            else:
                print(f"[branch] transient scopes collected after {settled:.3f}s")
        else:
            print("\n[branch] refusal: no usable systemd --user scope; asserting the uncontained guard")

            with tempfile.TemporaryDirectory() as tmp:
                oracle = Path(tmp) / "command-ran-uncontained"
                result = _run([str(BOUNDED_RUN), "sh", "-c", f"touch {oracle}"])
                self.assertEqual(result.returncode, 78, result.stdout + result.stderr)
                self.assertIn("was not started", result.stderr)
                self.assertFalse(
                    oracle.exists(),
                    "the command ran even though containment was unavailable",
                )


if __name__ == "__main__":
    unittest.main()
