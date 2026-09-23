"""Portable guarded runners: structure, refusal, and host containment.

Two evidence classes live here and are labelled at each assertion:

* structural validation - ShellCheck, absence of personal home paths, the exact
  strict-mode line the scripts ship, and the usage exit code. These prove
  artifact consistency only.
* local integration check - the containment behaviour actually exercised on the
  host running the suite. The suite never skips it; it takes one of two
  branches and prints which one, because a host without a native
  ``systemd --user`` bus can only demonstrate the refusal property. The
  containment branch reads its evidence from inside the job (cgroup, systemd
  unit properties, kernel limit files), so a runner that executed the command
  uncontained fails instead of passing unnoticed.
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
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "adoption" / "tools"
BOUNDED_RUN = TOOLS / "ecosystem-bounded-run"
GITLEAKS_GUARDED = TOOLS / "gitleaks-guarded"
SCRIPTS = (BOUNDED_RUN, GITLEAKS_GUARDED)
SHELLCHECK = shutil.which("shellcheck")

# Built from fragments so this file can never match its own acceptance grep.
PERSONAL_HOME = re.compile("/(?:" + "home" + "|" + "Users" + ")/[A-Za-z0-9_.-]+")
# The shipped scripts do NOT carry ``set -Eeuo pipefail``. Both open with the
# literal line ``set -euo pipefail``, and they are kept as close to their source
# as the README provenance section records (only the listed divergences), so
# this asserts the bytes actually shipped rather than the stricter line. Neither
# script installs an ERR trap, which is what makes the absent ``-E``
# behaviourally inert, and that inertness is asserted below rather than
# assumed; adding ``-E`` here would be an unrecorded divergence from the source. The README evidence paragraph states the same
# divergence. A future upstream sync that does adopt ``-E`` must update this
# line deliberately.
STRICT_MODE_LINE = "set -euo pipefail"
STRICT_MODE = re.compile(r"^set -euo pipefail$", re.M)
ERR_TRAP = re.compile(r"^[ \t]*trap\b.*\bERR\b", re.M)

# The launcher names its transient unit ecosystem-job-<uid>-<pid>-<random>.scope
# (see ``job_unit=`` in ecosystem-bounded-run); that name is also the leaf of the
# cgroup v2 path a contained job reads from /proc/self/cgroup.
SCOPE_UNIT = re.compile(r"ecosystem-job-[0-9]+-[0-9]+-[0-9]+\.scope")

# ecosystem-bounded-run's own defaults, as the kernel and systemd report them.
EXPECTED_MEMORY_MAX = str(6 * 1024 ** 3)
EXPECTED_TASKS_MAX = "256"

RUNTIME_BUS = Path(f"/run/user/{os.getuid()}/bus")


def _user_scope_available():
    """True when this host can actually place a job in a systemd user scope.

    Any failure of the probe itself - no ``systemd-run`` on PATH, a denied exec,
    a probe that hangs until its timeout - means this host cannot be shown to
    contain a job, so the suite takes the refusal branch instead of raising at
    import time and taking every other test down with it.
    """
    if not Path("/sys/fs/cgroup/cgroup.controllers").is_file():
        return False
    try:
        if not stat.S_ISSOCK(os.stat(RUNTIME_BUS).st_mode):
            return False
    except OSError:
        return False
    try:
        probe = subprocess.run(
            ["systemd-run", "--user", "--scope", "true"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        # SubprocessError covers TimeoutExpired; OSError covers a missing or
        # non-executable systemd-run.
        return False
    return probe.returncode == 0


CONTAINMENT_AVAILABLE = _user_scope_available()


def _run(argv, **kwargs):
    return subprocess.run(
        argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=120, check=False, **kwargs,
    )


def _live_tasks(unit, cgroup_path, cgroup_root=Path("/sys/fs/cgroup")):
    """Live task count for one unit, or 0 only when that is demonstrated.

    Returns systemd's TasksCurrent when the query succeeds with a number.
    When systemd reports no number (``[not set]`` once the unit is gone), 0 is
    returned only if the job's own cgroup directory has also disappeared, so
    nothing can still be running in it. A failed query, or a missing number for
    a cgroup that still exists, raises AssertionError instead of being read as
    "holds no tasks".
    """
    shown = _run(["systemctl", "--user", "show", unit,
                  "-p", "TasksCurrent", "-p", "LoadState", "-p", "ControlGroup"])
    if shown.returncode != 0:
        raise AssertionError(
            f"systemctl --user show {unit} failed with exit {shown.returncode}: "
            f"{(shown.stderr or shown.stdout).strip()!r}; its task count is unknown")
    properties = dict(line.split("=", 1) for line in shown.stdout.splitlines()
                      if "=" in line)
    tasks = properties.get("TasksCurrent", "")
    if tasks.isdigit():
        return int(tasks)
    leaf = Path(f"{cgroup_root}{cgroup_path}")
    if not leaf.exists():
        return 0
    raise AssertionError(
        f"{unit} reported TasksCurrent={tasks!r} while its cgroup {leaf} still "
        f"exists; properties were {properties!r}")


class GuardedRunnerStructureTests(unittest.TestCase):
    """Structural validation only; nothing here executes a contained job."""

    def test_scripts_are_present_and_executable(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                self.assertTrue(script.is_file(), f"{script} is missing")
                self.assertTrue(os.access(script, os.X_OK), f"{script} is not executable")

    # SC2317 (info, "command appears to be unreachable") is excluded: the bounded runner's
    # cleanup function is reached only through `trap`, which the shellcheck release on
    # GitHub-hosted runners reports as unreachable while shellcheck 0.11.0 is clean.
    @unittest.skipUnless(
        SHELLCHECK,
        "native shellcheck unavailable; the hosted runner uses its image's shellcheck "
        "(not pinned by any workflow)",
    )
    def test_shellcheck_is_clean_at_style_severity(self):
        result = _run([SHELLCHECK, "-S", "style", "-e", "SC2317", str(BOUNDED_RUN), str(GITLEAKS_GUARDED)])
        self.assertEqual(
            result.returncode, 0,
            f"shellcheck -S style reported findings:\n{result.stdout}{result.stderr}",
        )

    def test_no_personal_home_paths(self):
        for path in (BOUNDED_RUN, GITLEAKS_GUARDED, TOOLS / "README.md", Path(__file__)):
            with self.subTest(path=path.name):
                found = PERSONAL_HOME.findall(path.read_text(encoding="utf-8"))
                self.assertEqual(found, [], f"{path.name} contains personal home paths: {found}")

    def test_strict_mode_is_the_line_actually_shipped(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                text = script.read_text(encoding="utf-8")
                self.assertRegex(
                    text, STRICT_MODE,
                    f"{script.name} does not ship the literal line "
                    f"{STRICT_MODE_LINE!r}",
                )
                self.assertIsNone(
                    ERR_TRAP.search(text),
                    f"{script.name} installs an ERR trap, so the shipped "
                    f"{STRICT_MODE_LINE!r} (no -E) is no longer inert and the "
                    "strict-mode line must be revisited",
                )

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
    """Branch-aware local integration check; never skipped, always reported.

    The containment branch proves containment *from inside the job*: the job
    reports its own cgroup, the systemd properties of the unit it is running in,
    and the limit values the kernel actually applied to it. A silently
    uncontained run therefore fails instead of passing unnoticed. Everything the
    branch inspects afterwards is scoped to the one unit name this run used, so
    a concurrent guarded scan by the same user elsewhere can neither fail nor
    mask it.
    """

    def _list_units(self):
        result = _run(["systemctl", "--user", "list-units",
                       "ecosystem-job-*", "--all", "--no-legend"])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    @staticmethod
    def _is_listed(unit, listing):
        """True when `unit` appears as a unit name in a list-units listing."""
        return any(unit in line.split() for line in listing.splitlines())

    def _wait_for_release(self, unit, deadline=45.0):
        """Poll until `unit` leaves the listing.

        Returns (seconds, listing) once it is gone, or (None, listing) if it is
        still listed at the deadline. `--collect` teardown is asynchronous and
        its latency is unbounded (over 30s observed on this host), so a unit
        still listed immediately after the job exits is not by itself a failure.
        """
        started = time.monotonic()
        while True:
            listing = self._list_units()
            elapsed = time.monotonic() - started
            if not self._is_listed(unit, listing):
                return elapsed, listing
            if elapsed > deadline:
                return None, listing
            time.sleep(0.05)

    def _run_self_reporting_job(self, tmp):
        """Run one job that records, from inside itself, where it is contained.

        Returns the transient scope unit name the job actually ran in and the
        cgroup v2 path it reported for itself.
        """
        cgroup_oracle = tmp / "job-cgroup"
        unit_oracle = tmp / "job-unit-properties"
        limit_oracle = tmp / "job-kernel-limits"

        # The $ORACLE_* names are expanded by the job's own shell: systemd-run is
        # invoked with --expand-environment=no, and a transient scope inherits
        # the caller's environment.
        script = (
            'set -eu\n'
            'cat /proc/self/cgroup > "$ORACLE_CGROUP"\n'
            'job_path=$(cut -d: -f3 /proc/self/cgroup)\n'
            '/usr/bin/systemctl --user show "${job_path##*/}"'
            ' -p TasksCurrent -p MemoryMax -p SubState --value > "$ORACLE_UNIT"\n'
            'cat "/sys/fs/cgroup$job_path/memory.max"'
            ' "/sys/fs/cgroup$job_path/pids.max" > "$ORACLE_LIMITS"\n'
        )
        # The documented defaults are what is asserted below, so any ambient
        # ECOSYSTEM_JOB_* override is dropped rather than silently measured.
        environment = {k: v for k, v in os.environ.items()
                       if not k.startswith("ECOSYSTEM_JOB_")}
        environment.update(ORACLE_CGROUP=str(cgroup_oracle),
                           ORACLE_UNIT=str(unit_oracle),
                           ORACLE_LIMITS=str(limit_oracle))
        result = _run([str(BOUNDED_RUN), "sh", "-c", script], env=environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(
            cgroup_oracle.is_file(),
            "the job wrote no cgroup record, so it cannot be shown to have run",
        )

        # 1. The job's own cgroup leaf must be the launcher's transient scope.
        cgroup = cgroup_oracle.read_text(encoding="utf-8").strip()
        self.assertTrue(cgroup.startswith("0::"),
                        f"not a cgroup v2 record: {cgroup!r}")
        job_path = cgroup.split(":", 2)[2]
        unit = job_path.rsplit("/", 1)[-1]
        self.assertIsNotNone(
            SCOPE_UNIT.fullmatch(unit),
            "the job did not run inside an ecosystem-job-*.scope; its own "
            f"cgroup was {cgroup!r}",
        )

        # 2. systemd-run really created that unit: systemd reports it as a live
        #    scope holding this job while the job is still inside it.
        self.assertTrue(unit_oracle.is_file(),
                        "the job could not query its own systemd unit")
        properties = unit_oracle.read_text(encoding="utf-8").split()
        self.assertEqual(
            len(properties), 3,
            f"systemd did not report {unit} as a unit: {properties!r}",
        )
        tasks_inside, memory_max, sub_state = properties
        self.assertTrue(
            tasks_inside.isdigit() and int(tasks_inside) >= 1,
            f"{unit} reported TasksCurrent={tasks_inside!r} while the job ran",
        )
        self.assertEqual(sub_state, "running",
                         f"{unit} was {sub_state!r} while the job ran")
        self.assertEqual(
            memory_max, EXPECTED_MEMORY_MAX,
            f"{unit} carries MemoryMax={memory_max!r}, not the 6G default",
        )

        # 3. The kernel applied the limits to that cgroup, not just systemd.
        self.assertTrue(limit_oracle.is_file(),
                        "the job could not read its own cgroup limit files")
        limits = limit_oracle.read_text(encoding="utf-8").split()
        self.assertEqual(
            limits, [EXPECTED_MEMORY_MAX, EXPECTED_TASKS_MAX],
            f"{unit} kernel limits were {limits!r}, not the documented "
            f"MemoryMax=6G / TasksMax=256",
        )
        return unit, job_path

    def test_containment_or_refusal(self):
        if CONTAINMENT_AVAILABLE:
            print("\n[branch] containment: cgroup v2 and a native systemd --user bus are present")

            failing = _run([str(BOUNDED_RUN), "sh", "-c", "exit 3"])
            self.assertEqual(failing.returncode, 3, failing.stdout + failing.stderr)

            succeeding = _run([str(BOUNDED_RUN), "true"])
            self.assertEqual(succeeding.returncode, 0, succeeding.stdout + succeeding.stderr)

            with tempfile.TemporaryDirectory() as tmp:
                unit, job_path = self._run_self_reporting_job(Path(tmp))
            print(f"[branch] job ran inside {unit} with MemoryMax="
                  f"{EXPECTED_MEMORY_MAX} and pids.max={EXPECTED_TASKS_MAX}")

            # Only this run's unit is inspected, so a concurrent guarded scan by
            # the same user cannot fail or mask the assertion. The property that
            # matters after the job returns is that no *process* survives it.
            settled, listing = self._wait_for_release(unit)
            if settled is None:
                tasks_left = _live_tasks(unit, job_path)
                self.assertFalse(
                    tasks_left,
                    f"{unit} still holds {tasks_left} live task(s) after the "
                    f"job returned:\n{listing}")
                print(f"[branch] {unit} still awaiting systemd GC after 45s "
                      f"and holds no tasks (TasksCurrent={tasks_left})")
            else:
                print(f"[branch] {unit} released after {settled:.3f}s")
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



def _instrumented_runner(tmp, launcher_body):
    """A copy of the runner whose only change is the systemd-run it calls.

    The shipped runner names /usr/bin/systemd-run absolutely, so a stand-in
    launcher can only be reached by rewriting that one path in a scratch copy.
    """
    launcher = tmp / "systemd-run-stand-in"
    launcher.write_text("#!/usr/bin/env bash\n" + launcher_body, encoding="utf-8")
    launcher.chmod(0o755)
    text = BOUNDED_RUN.read_text(encoding="utf-8")
    assert text.count("/usr/bin/systemd-run") == 1, "expected exactly one launcher path"
    runner = tmp / "ecosystem-bounded-run"
    runner.write_text(text.replace("/usr/bin/systemd-run", str(launcher)),
                      encoding="utf-8")
    runner.chmod(0o755)
    return runner


# Passes every argument through to the real launcher except the four resource
# properties, so a real transient scope is created with no memory or task cap.
# That is the state systemd leaves a scope in when an ancestor does not
# delegate the memory or pids controller: the unit starts, the limit is masked.
_DROP_LIMITS = (
    "args=()\n"
    "for arg in \"$@\"; do\n"
    "  case $arg in\n"
    "    --property=MemoryHigh=*|--property=MemoryMax=*|"
    "--property=MemorySwapMax=*|--property=TasksMax=*) ;;\n"
    "    *) args+=(\"$arg\") ;;\n"
    "  esac\n"
    "done\n"
    "exec /usr/bin/systemd-run \"${args[@]}\"\n"
)
# Skips systemd-run's own options and runs the command directly: no scope.
_NO_SCOPE = (
    "while [[ $# -gt 0 && $1 != -- ]]; do shift; done\n"
    "shift\n"
    "exec \"$@\"\n"
)
# What /usr/bin/systemd-run printed and returned on this host when pointed at a
# stale user-bus socket (probed 2026-09-22 with systemd 255): exit 1.
_STALE_BUS = (
    "printf 'Failed to connect to bus: Connection refused\\n' >&2\n"
    "exit 1\n"
)


class BoundedRunSetupRefusalTests(unittest.TestCase):
    """Local integration check: 78 means the command was not started.

    A launcher failure, or a scope whose kernel limits are not the requested
    ones, must refuse with 78 and never run the command; a command that did run
    keeps its own exit status.
    """

    def _assert_refused(self, result, oracle):
        self.assertEqual(result.returncode, 78, result.stdout + result.stderr)
        self.assertIn("was not started", result.stderr)
        self.assertFalse(oracle.exists(), "the command ran although it was refused")

    def test_launcher_setup_failure_is_refused_with_78(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            runner = _instrumented_runner(tmp, _STALE_BUS)
            oracle = tmp / "command-ran"
            result = _run([str(runner), "sh", "-c", f"touch {oracle}"])
            self._assert_refused(result, oracle)

    def test_command_run_outside_any_scope_is_refused_with_78(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            runner = _instrumented_runner(tmp, _NO_SCOPE)
            oracle = tmp / "command-ran"
            result = _run([str(runner), "sh", "-c", f"touch {oracle}"])
            self._assert_refused(result, oracle)

    @unittest.skipUnless(CONTAINMENT_AVAILABLE, "needs a native systemd --user scope")
    def test_scope_without_the_requested_kernel_limits_is_refused_with_78(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            runner = _instrumented_runner(tmp, _DROP_LIMITS)
            oracle = tmp / "command-ran"
            result = _run([str(runner), "sh", "-c", f"touch {oracle}"])
            self._assert_refused(result, oracle)

    @unittest.skipUnless(CONTAINMENT_AVAILABLE, "needs a native systemd --user scope")
    def test_workload_exit_statuses_are_preserved(self):
        for status in (1, 78, 127):
            with self.subTest(status=status):
                result = _run([str(BOUNDED_RUN), "sh", "-c", f"exit {status}"])
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertNotIn("was not started", result.stderr)

    @unittest.skipUnless(CONTAINMENT_AVAILABLE, "needs a native systemd --user scope")
    def test_missing_command_is_refused_with_78(self):
        result = _run([str(BOUNDED_RUN), "ecosystem-bounded-run-no-such-command"])
        self.assertEqual(result.returncode, 78, result.stdout + result.stderr)
        self.assertIn("was not started", result.stderr)

    @unittest.skipUnless(CONTAINMENT_AVAILABLE, "needs a native systemd --user scope")
    def test_builtin_without_an_executable_file_is_refused_with_78(self):
        # `cd` is a shell builtin with no file on PATH; exec cannot run it, so the
        # runner must refuse before the start marker rather than return 127.
        result = _run([str(BOUNDED_RUN), "cd", "/"])
        self.assertEqual(result.returncode, 78, result.stdout + result.stderr)
        self.assertIn("command not found: cd", result.stderr)

    def test_builtin_name_with_an_executable_file_still_runs(self):
        result = _run([str(BOUNDED_RUN), "true"])
        if CONTAINMENT_AVAILABLE:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertEqual(result.returncode, 78, result.stdout + result.stderr)

    @unittest.skipUnless(CONTAINMENT_AVAILABLE, "needs a native systemd --user scope")
    def test_non_default_and_unaligned_limits_are_verified_and_run(self):
        # 1000001K is not a whole number of pages; the kernel stores
        # memory.max rounded down to a page, which the check must allow.
        with tempfile.TemporaryDirectory() as tmp:
            oracle = Path(tmp) / "limits"
            environment = {k: v for k, v in os.environ.items()
                           if not k.startswith("ECOSYSTEM_JOB_")}
            environment.update(ECOSYSTEM_JOB_MEMORY_HIGH="512M",
                               ECOSYSTEM_JOB_MEMORY_MAX="1000001K",
                               ECOSYSTEM_JOB_TASKS_MAX="64")
            script = ('p=$(cut -d: -f3 /proc/self/cgroup); '
                      f'cat "/sys/fs/cgroup$p/memory.max" "/sys/fs/cgroup$p/pids.max" > {oracle}')
            result = _run([str(BOUNDED_RUN), "sh", "-c", script], env=environment)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            page = os.sysconf("SC_PAGE_SIZE")
            self.assertEqual(oracle.read_text(encoding="utf-8").split(),
                             [str(1000001 * 1024 // page * page), "64"])


class LiveTaskQueryTests(unittest.TestCase):
    """Structural check of the post-run task probe; systemctl is stubbed."""

    UNIT = "ecosystem-job-1-1-1.scope"

    def _query(self, returncode, stdout, cgroup_exists, stderr=""):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if cgroup_exists:
                (root / "user.slice" / self.UNIT).mkdir(parents=True)
            shown = subprocess.CompletedProcess([], returncode, stdout, stderr)
            with mock.patch(f"{__name__}._run", return_value=shown):
                return _live_tasks(self.UNIT, f"/user.slice/{self.UNIT}", root)

    def test_failed_query_is_not_read_as_no_tasks(self):
        with self.assertRaises(AssertionError):
            self._query(1, "", cgroup_exists=True,
                        stderr="Failed to connect to bus: Connection refused")

    def test_failed_query_fails_even_when_the_cgroup_is_gone(self):
        with self.assertRaises(AssertionError):
            self._query(1, "", cgroup_exists=False)

    def test_unreported_count_for_a_live_cgroup_fails(self):
        with self.assertRaises(AssertionError):
            self._query(0, "TasksCurrent=[not set]\nLoadState=loaded\nControlGroup=/x\n",
                        cgroup_exists=True)

    def test_explicit_zero_is_accepted(self):
        self.assertEqual(
            self._query(0, "TasksCurrent=0\nLoadState=loaded\nControlGroup=\n",
                        cgroup_exists=True), 0)

    def test_live_count_is_returned(self):
        self.assertEqual(
            self._query(0, "TasksCurrent=2\nLoadState=loaded\nControlGroup=/x\n",
                        cgroup_exists=True), 2)

    def test_unit_and_cgroup_both_gone_count_as_zero(self):
        # What systemd 255 printed for a collected unit on this host.
        self.assertEqual(
            self._query(0, "ControlGroup=\nTasksCurrent=[not set]\nLoadState=not-found\n",
                        cgroup_exists=False), 0)


if __name__ == "__main__":
    unittest.main()
