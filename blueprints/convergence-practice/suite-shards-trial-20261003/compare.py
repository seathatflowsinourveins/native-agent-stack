#!/usr/bin/env python3
"""Independent, stdlib-only oracle of the suite-shards trial (2026-10-03).

It reads the run directories of actual GitHub-hosted runs, decides whether each sharded arm ran exactly the
tests the serial production command (arm S) ran on the same OS, with exactly the same outcomes, and applies
the preregistered speed rule. README.md states every rule and the input layout.

  python3 compare.py verdict --results DIR --inventory DIR --expected-sha SHA --run-attempt N [--os OS]
                     [--needs FILE] --out result.json [--summary-md FILE] [--checkout-status FILE]
  python3 compare.py controls --artifact DIR --os OS --job-result RESULT [--expected-sha SHA] [--out FILE]

--results is the directory the compare job downloads the artifacts into without merging them: one directory
arm-<run name> per arm artifact, holding exactly the run directory <run name>, and the directory `controls`
(the control artifact), holding exactly <os>-controls. --run-attempt is the compare job's own
GITHUB_RUN_ATTEMPT; any value but 1 makes every OS incomplete.

verdict exits 0 when result.json was written (the outcome is inside it) and 2 for unusable arguments.
controls exits 0 when the control run met every expectation and 1 otherwise.

Every log is parsed by logparse.py, the first trial's parser copied unchanged. The shard lists come from the
inventory artifact and are re-derived with make_shards.py, this directory's frozen generator.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import re
import shlex
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import logparse  # noqa: E402
import make_shards  # noqa: E402

SCHEMA = "suite-shards-oracle/1"
OSES = tuple(make_shards.ARMS)
SERIAL_ARM = "S"
SERIAL_COMMAND = ("python3", "-m", "unittest", "-v")
REPEATS = 3
# The speed rule's thresholds as exact rationals: no ratio is rounded before it is compared.
MEDIAN_RATIO_MAX = Fraction(3, 5)
MAX_RATIO_MAX = Fraction(3, 4)
# The monotonic and wall-clock lengths of a test phase must agree within max(5 s, 1 % of the wall clock).
CLOCK_TOLERANCE_NS = 5 * 10 ** 9
CLOCK_TOLERANCE_PART = Fraction(1, 100)
RUN_DIR_RE = re.compile(r"^(?P<os>macos-15|ubuntu-24\.04)-(?:(?P<arm>[A-Za-z0-9]+)-r(?P<rep>[1-9][0-9]*)"
                        r"|(?P<controls>controls))$")
# Artifact layout (README.md, "Run directory contract"): arm artifact `arm-<run name>` holds exactly the run
# directory <run name>; the control artifact `controls` holds exactly <os>-controls. A run directory that reaches
# the oracle by any other path (a bare directory, another artifact) is not attributed and does not count.
ARM_ARTIFACT_PREFIX = "arm-"
CONTROL_ARTIFACT = "controls"
JOB_STATUSES = ("success", "failure", "cancelled")
# The jobs of each trial workflow, as the compare job's needs context names them, and the results under which
# the rule applies. A cancelled or skipped job makes the run incomplete, never a rule outcome.
NEEDS_RESULTS = {"inventory": ("success", "failure"), "serial": ("success", "failure"),
                 "shards": ("success", "failure"), "controls": ("success", "failure"),
                 "controls-check": ("success", "failure")}
# The step ids the finish steps record from the steps context (meta.json "steps"): the clock-start step of every
# timed job, after which the test phase begins, and the control job's foreground probe step, after which its
# parallel group begins. Any outcome but success means the test phase or the group never started.
START_STEP = "start"
FOREGROUND_STEP = "foreground"
# The control run (README.md, "Controls"): four shards of one parallel group, each one control module run with
# the arms' shard command in an empty directory, each step with its own id and expected outcome. The job is
# expected to fail.
CONTROL_JOB_RESULT = "failure"
CONTROL_SHARDS = (
    {"module": "test_ctl_pass", "expect": "pass", "step": "control-0", "outcome": "success",
     "records": (("test", "test_ctl_pass.Pass.test_one", "ok"), ("test", "test_ctl_pass.Pass.test_two", "ok"))},
    {"module": "test_ctl_fail", "expect": "fail", "step": "control-1", "outcome": "failure",
     "records": (("test", "test_ctl_fail.Fail.test_fails", "FAIL"), ("test", "test_ctl_fail.Fail.test_passes", "ok"))},
    {"module": "test_ctl_crash", "expect": "crash", "step": "control-2", "outcome": "failure",
     "started": "test_ctl_crash.Crash.test_exits", "exit": 3},
    {"module": "test_ctl_hang", "expect": "killed", "step": "control-3", "outcome": "failure",
     "started": "test_ctl_hang.Hang.test_sleeps"},
)
CONTROL_ENV_NAME = "SUITE_SHARDS_ENV_PROBE"
# The failing control (control shard 1) can fail no sooner than this after its own probe: its failing test first
# sleeps 90 s (controls/test_ctl_fail.py, SLEEP_SECONDS). The crashing control ends itself 120 s after its start.
FAIL_CONTROL_AFTER_NS = 90 * 10 ** 9
# The four control steps must start together: every probe within this span of the others. The hang step is stopped
# at most 70 s after its start (the 60 s limit, then SIGINT, up to 7.5 s, SIGTERM, up to 2.5 s and a kill:
# ProcessInvoker.cs at v2.337.0, lines 443-465 and 855-869), so 15 s keeps the failing control (90 s) running past
# that stop and the crashing control (120 s) running past the failing control's failure.
CONTROL_START_SPREAD_MAX_NS = 15 * 10 ** 9
# The hang control (control shard 3): its step was stopped when its shell ended, which heartbeat.json shows as the
# first heartbeat with another parent pid (or, when the test process ended with its shell, as its last heartbeat).
# That stop must come at least HANG_STOP_MIN_NS after the step's probe (the 60 s step limit less 10 s for the
# heartbeat interval and the step's start-up: the step was not stopped before its limit) and before the failing
# control's probe plus FAIL_CONTROL_AFTER_NS (before any sibling could fail, so the limit stopped it). The control
# job's finish step, which runs only after the whole group ended, must begin less than HANG_GROUP_MAX_NS after the
# hang step's probe, so the group did not wait for the test's 300 s sleep.
HANG_STOP_MIN_NS = 50 * 10 ** 9
HANG_GROUP_MAX_NS = 240 * 10 ** 9
SIGNALS = ("SIGINT", "SIGQUIT")
LIST_CAP = 200
# The two run-level problems that a shard step without an exit status brings with it (read_run and
# compare_with_baseline write them), which unfinished_steps attributes to that step when its modules own the ids.
NEVER_RAN_RE = re.compile(r"^[0-9]+ inventory ids never ran: ")
DIFFER_RE = re.compile(r"^[0-9]+ ids differ from the S baseline: ")


def arms_of(os_name: str) -> tuple:
    """The preregistered arms of an OS: S, then the shard arms in make_shards.ARMS order (G before GT)."""
    return (SERIAL_ARM,) + tuple(make_shards.ARMS[os_name])


def _cap(items, cap: int = 5) -> str:
    items = list(items)
    shown = ", ".join(str(item) for item in items[:cap])
    return f"[{shown}{', ...' if len(items) > cap else ''}] ({len(items)})"


def sha256_of(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def read_json(path: Path):
    """The parsed JSON at path, or None when it is missing or invalid."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def read_exit(path: Path) -> tuple:
    """(exit status or None, problem or None) from a one-integer file."""
    raw = read_text(path)
    if raw is None:
        return None, f"{path.name} is missing"
    if not re.fullmatch(r"-?[0-9]+", raw.strip()):
        return None, f"{path.name} is not one integer: {raw.strip()[:40]!r}"
    return int(raw.strip()), None


def command_tokens(text: str | None):
    try:
        return shlex.split(text) if text is not None else None
    except ValueError:
        return None


# --------------------------------------------------------------------------- inventory


@dataclasses.dataclass
class Inventory:
    ids: set
    count: int
    module_ids: dict
    lists: dict  # {arm: {"shards": [[module, ...], ...], "tail": [module, ...]}}
    report: dict | None
    problems: list
    sha256: dict


def load_inventory(directory: Path, os_name: str | None, weights: Path | None) -> Inventory:
    """The inventory artifact: the discovery ids, the file-to-ids map and every shard arm's lists of os_name.
    weights, when given, re-derives the lists with make_shards.py. Any problem gives the OS no verdict."""
    problems = []
    text = read_text(directory / "inventory.txt")
    ids = []
    if text is None:
        problems.append("inventory.txt is missing")
    else:
        ids = text.split("\n")
        if ids and ids[-1] == "":
            ids.pop()
        if not ids or ids != sorted(set(ids)) or any(not item or item != item.strip() for item in ids):
            problems.append("inventory.txt is empty or not the sorted, de-duplicated id list inventory.py writes")
    module_ids = read_json(directory / "module_ids.json")
    if not isinstance(module_ids, dict) or not all(isinstance(owned, list) for owned in module_ids.values()):
        problems.append("module_ids.json is missing or not {module: [ids]}")
        module_ids = {}
    owners = collections.Counter(item for owned in module_ids.values() for item in owned)
    if module_ids and (set(owners) != set(ids) or any(count > 1 for count in owners.values())):
        problems.append("module_ids.json does not give every inventory id exactly one test file")
    report = read_json(directory / "report.json")
    if not isinstance(report, dict) or report.get("ok") is not True or report.get("parity") is not True:
        problems.append("report.json is missing or does not record a passed inventory gate (ok and parity true)")
    elif os_name and report.get("os") != os_name:
        problems.append(f"report.json is for {report.get('os')!r}, not {os_name}")
    lists = {}
    if os_name:
        modules = sorted(module_ids)
        for arm, spec in make_shards.ARMS[os_name].items():
            try:
                shards = [make_shards.read_list(directory / "shards" / arm / f"shard-{index}.txt")
                          for index in range(spec["shards"])]
                tail = make_shards.read_list(directory / "shards" / arm / "tail.txt")
            except (OSError, make_shards.ShardError) as error:
                problems.append(f"shards/{arm}: unreadable lists ({error})")
                continue
            lists[arm] = {"shards": shards, "tail": tail}
            problems.extend(f"shards/{arm}: {problem}" for problem in make_shards.coverage_problems(modules, lists[arm]))
            if tail != list(spec["tail"]):
                problems.append(f"shards/{arm}: tail {tail} is not the preregistered tail {list(spec['tail'])}")
        if weights is not None and modules:
            try:
                plan = make_shards.plan_for(os_name, modules, make_shards.load_weights(weights))
                for arm, arm_plan in plan.items():
                    if lists.get(arm) != {"shards": arm_plan["shards"], "tail": arm_plan["tail"]}:
                        problems.append(f"shards/{arm}: the lists are not make_shards.py's lists for these test "
                                        "files and the frozen weights")
            except make_shards.ShardError as error:
                problems.append(f"make_shards.py: {error}")
    return Inventory(set(ids), len(ids), module_ids, lists, report if isinstance(report, dict) else None, problems,
                     {name: sha256_of(directory / name) for name in ("inventory.txt", "module_ids.json", "report.json")})


# --------------------------------------------------------------------------- run directories


@dataclasses.dataclass
class Log:
    label: str
    modules: list
    command: str | None = None
    exit_code: int | None = None
    parsed: logparse.ParsedLog | None = None
    probe: dict | None = None
    problems: list = dataclasses.field(default_factory=list)
    exit_missing: bool = False  # the step never wrote its exit status file


@dataclasses.dataclass
class Run:
    name: str
    os: str
    arm: str
    repeat: int
    meta: dict | None = None
    runtime: dict | None = None
    timing: dict | None = None
    checkout_status: str | None = None
    logs: list = dataclasses.field(default_factory=list)
    problems: list = dataclasses.field(default_factory=list)
    unstarted: list = dataclasses.field(default_factory=list)
    mismatches: list = dataclasses.field(default_factory=list)
    mismatch_total: int = 0
    mismatch_keys: list = dataclasses.field(default_factory=list)  # every differing key, uncapped
    missing_ids: list = dataclasses.field(default_factory=list)
    extra_ids: list = dataclasses.field(default_factory=list)
    repeated_ids: list = dataclasses.field(default_factory=list)

    @property
    def attempt(self):
        return attempt_of(self.runtime)

    @property
    def step_ns(self) -> int | None:
        value = (self.timing or {}).get("step_ns")
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    @property
    def python_version(self):
        return (self.meta or {}).get("python_version")

    @property
    def job_status(self):
        return (self.meta or {}).get("job_status")


def common_problems(path: Path, os_name: str, arm: str, repeat: int, expected_sha: str | None, timed: bool) -> tuple:
    """(meta, runtime, timing, checkout status, problems) for the files every run directory holds."""
    problems = []
    meta = read_json(path / "meta.json")
    if not isinstance(meta, dict):
        problems.append("meta.json is missing or not a JSON object")
        meta = None
    else:
        for field, wanted in (("os", os_name), ("arm", arm), ("repeat", repeat)):
            if meta.get(field) != wanted:
                problems.append(f"meta.json {field} {meta.get(field)!r} differs from the directory name ({wanted!r})")
        if not isinstance(meta.get("python_version"), str) or not meta["python_version"]:
            problems.append("meta.json python_version is missing")
        if meta.get("job_status") not in JOB_STATUSES:
            problems.append(f"meta.json job_status {meta.get('job_status')!r} is not one of {list(JOB_STATUSES)}")
        elif meta["job_status"] == "cancelled":
            problems.append("the job was cancelled (job_status cancelled): a partial run")
        if expected_sha and meta.get("checkout_sha") != expected_sha:
            problems.append(f"checkout_sha {meta.get('checkout_sha')!r} is not the pull request head {expected_sha}")
    runtime = read_json(path / "runtime.json")
    if not isinstance(runtime, dict):
        problems.append("runtime.json is missing or not JSON: the run attempt is unrecorded")
        runtime = None
    elif runtime.get("run_attempt") != "1":
        # GITHUB_RUN_ATTEMPT is "1" for a run's first attempt (github/docs contexts.md at 03d2e24b, line 209).
        problems.append(f"run_attempt {runtime.get('run_attempt')!r}: only a run's first attempt counts (a job re-run "
                        "voids the run)")
    timing = None
    if timed:
        timing = read_json(path / "timing.json")
        problems.extend(timing_problems(timing))
        if not isinstance(timing, dict):
            timing = None
    status = read_text(path / "git-status.txt")
    if status is None:
        problems.append("git-status.txt is missing: the checkout status after the run is unrecorded")
    elif status.strip() == "git status failed":
        problems.append("git-status.txt says git status failed: the checkout status after the run is unrecorded")
    elif status != "":
        problems.append(f"the checkout was not clean after the run: {_cap(status.splitlines())}")
    return meta, runtime, timing, status, problems


def timing_problems(timing) -> list:
    if not isinstance(timing, dict):
        return ["timing.json is missing or not JSON: the test phase was not timed"]
    problems = [f"timing.json: {problem}" for problem in timing.get("problems") or []]
    step, wall = timing.get("step_ns"), timing.get("wall_ns")
    if not isinstance(step, int) or isinstance(step, bool) or step <= 0:
        problems.append("timing.json step_ns is not a positive integer")
    elif not isinstance(wall, int) or isinstance(wall, bool) or wall <= 0:
        problems.append("timing.json wall_ns is not a positive integer")
    elif abs(step - wall) > max(CLOCK_TOLERANCE_NS, CLOCK_TOLERANCE_PART * wall):
        problems.append(f"the monotonic ({step} ns) and wall-clock ({wall} ns) lengths of the test phase disagree")
    return problems


def attempt_of(runtime):
    """The run attempt runtime.json records (GITHUB_RUN_ATTEMPT), or None when it is unrecorded."""
    return runtime.get("run_attempt") if isinstance(runtime, dict) else None


def step_outcome(meta, step_id: str):
    """The outcome meta.json records for the step with this id (from the steps context), or None."""
    steps = meta.get("steps") if isinstance(meta, dict) else None
    entry = steps.get(step_id) if isinstance(steps, dict) else None
    return entry.get("outcome") if isinstance(entry, dict) else None


def unstarted_reasons(meta, step_id: str) -> list:
    """Why the runner's own record does not show that the step before the test phase (or the control group)
    succeeded; [] when it does. A run that never reached its test phase failed in setup: it is partial, never
    ineligible (README.md, "Decision rule", rule 5)."""
    if not isinstance(meta, dict):
        return ["meta.json is missing or not JSON: whether the test phase started is unrecorded"]
    if not isinstance(meta.get("steps"), dict):
        return ["meta.json records no step outcomes: whether the test phase started is unrecorded"]
    outcome = step_outcome(meta, step_id)
    if outcome != "success":
        return [f"the {step_id!r} step's outcome is {outcome!r}, not 'success': the test phase never started"]
    return []


def read_log(path: Path, label: str, prefix: str | None, modules: list) -> Log:
    """One command's files and the per-log rules. prefix None is the S layout (log.txt, exit-code.txt,
    command.txt, no probe); otherwise <prefix>.log, <prefix>.exit, <prefix>.command and <prefix>.probe.json."""
    names = (("log.txt", "exit-code.txt", "command.txt", None) if prefix is None
             else (f"{prefix}.log", f"{prefix}.exit", f"{prefix}.command", f"{prefix}.probe.json"))
    log_name, exit_name, command_name, probe_name = names
    log = Log(label, list(modules))
    text = read_text(path / log_name)
    if text is None:
        log.problems.append(f"{log_name} is missing")
    elif not text.strip():
        log.problems.append(f"{log_name} is empty")
    else:
        log.parsed = logparse.parse_log(text)
    log.exit_code, problem = read_exit(path / exit_name)
    log.exit_missing = not (path / exit_name).is_file()
    if problem:
        log.problems.append(problem)
    log.command = read_text(path / command_name)
    if log.command is None:
        log.problems.append(f"{command_name} is missing")
    elif command_tokens(log.command) != list(SERIAL_COMMAND) + list(modules):
        log.problems.append(f"{command_name} is not the preregistered command `python3 -m unittest -v`"
                            f"{' followed by its ' + str(len(modules)) + ' listed modules' if modules else ''}")
    if probe_name is not None:
        log.probe = read_json(path / probe_name)
        if not isinstance(log.probe, dict):
            log.problems.append(f"{probe_name} is missing or not JSON")
            log.probe = None
    parsed = log.parsed
    if parsed is not None:
        log.problems.extend(f"{log_name}: {anomaly}" for anomaly in parsed.anomalies)
        if parsed.mode != "serial":
            log.problems.append(f"{log_name}: a unittest-parallel header in a unittest log")
        if parsed.status_word is not None and log.exit_code is not None:
            # Zero versus non-zero: CPython's unittest exits 1 on failure and 5 when no test ran (CPY main.py,
            # v3.13.16 :271-277, v3.12.3 :282-288, as the first trial's oracle cites).
            if (parsed.status_word == "OK") != (log.exit_code == 0):
                log.problems.append(f"{log_name}: exit status {log.exit_code} disagrees with the status line "
                                    f"{parsed.status_word}")
    return log


def covered_ids(parsed: logparse.ParsedLog, candidates) -> set:
    """Ids behind a failed or skipped setUpClass or setUpModule, which CPY suite.py:117-118 never runs."""
    covered = set()
    for key, outcome in parsed.fixtures:
        name, _, parent = key.partition(" (")
        parent = parent[:-1]
        if name in ("setUpClass", "setUpModule") and outcome in ("ERROR", "skipped"):
            covered.update(item for item in candidates if item.startswith(parent + "."))
    return covered


def read_run(path: Path, os_name: str, arm: str, repeat: int, inventory: Inventory, expected_sha: str | None) -> Run:
    run = Run(path.name, os_name, arm, repeat)
    run.meta, run.runtime, run.timing, run.checkout_status, run.problems = common_problems(
        path, os_name, arm, repeat, expected_sha, timed=True)
    # Never started: the clock-start step did not succeed (the runner's record), or the finish step found no clock
    # start (timing.json step_ns None). Then a setup step failed or the job stopped before the test phase.
    run.unstarted = unstarted_reasons(run.meta, START_STEP)
    if run.timing is None or run.timing.get("step_ns") is None:
        run.unstarted.append("timing.json records no clock start: the test phase never started")
    if arm not in arms_of(os_name):
        run.problems.append(f"arm {arm} is not preregistered for {os_name}")
        return run
    if arm == SERIAL_ARM:
        run.logs = [read_log(path, "S", None, [])]
    else:
        wanted = inventory.lists.get(arm)
        if wanted is None:
            run.problems.append(f"the inventory holds no lists for {arm}")
            return run
        try:
            mine = {"shards": [make_shards.read_list(path / f"shard-{index}.txt")
                               for index in range(len(wanted["shards"]))],
                    "tail": make_shards.read_list(path / "tail.txt")}
        except (OSError, make_shards.ShardError) as error:
            mine = None
            run.problems.append(f"the run's shard lists are missing or invalid ({error})")
        if mine is not None and mine != wanted:
            run.problems.append("the run's shard lists are not the inventory artifact's lists for this arm")
        for index, modules in enumerate(wanted["shards"]):
            run.logs.append(read_log(path, f"shard-{index}", f"shard-{index}", modules))
        if wanted["tail"]:
            run.logs.append(read_log(path, "tail", "tail", wanted["tail"]))
        elif (path / "tail.log").exists():
            run.problems.append("tail.log exists although the arm has no tail")
    for log in run.logs:
        run.problems.extend(f"{log.label}: {problem}" for problem in log.problems)
        if log.probe is not None and log.probe.get("python_version") != run.python_version:
            run.problems.append(f"{log.label}: the step ran python {log.probe.get('python_version')!r}, the job "
                                f"recorded {run.python_version!r}")
        if arm != SERIAL_ARM and log.parsed is not None:
            wanted_ids = {item for module in log.modules for item in inventory.module_ids.get(module, [])}
            accounted = log.parsed.started_ids() | covered_ids(log.parsed, wanted_ids)
            if accounted != wanted_ids:
                run.problems.append(f"{log.label}: its executed ids are not its modules' ids (missing "
                                    f"{_cap(sorted(wanted_ids - accounted))}, extra "
                                    f"{_cap(sorted(accounted - wanted_ids))})")
    started = collections.Counter(ex.test_id for log in run.logs if log.parsed for ex in log.parsed.executions)
    accounted = set(started)
    for log in run.logs:
        if log.parsed is not None:
            accounted |= covered_ids(log.parsed, inventory.ids)
    run.repeated_ids = sorted(item for item, count in started.items() if count > 1)
    run.missing_ids = sorted(inventory.ids - accounted)
    run.extra_ids = sorted(accounted - inventory.ids)
    if run.repeated_ids:
        run.problems.append(f"{len(run.repeated_ids)} ids ran more than once: {_cap(run.repeated_ids)}")
    if run.missing_ids:
        run.problems.append(f"{len(run.missing_ids)} inventory ids never ran: {_cap(run.missing_ids)}")
    if run.extra_ids:
        run.problems.append(f"{len(run.extra_ids)} ids outside the inventory ran: {_cap(run.extra_ids)}")
    return run


def groups(logs: list) -> dict:
    """Records of all logs grouped by test id (subtests under their test) or fixture key, as sorted tuples."""
    grouped = collections.defaultdict(list)
    for log in logs:
        if log.parsed is None:
            continue
        for kind, key, outcome in log.parsed.records():
            grouped[key.split(" ", 1)[0] if kind == "subtest" else key].append((kind, key, outcome))
    return {group: tuple(sorted(items)) for group, items in grouped.items()}


# --------------------------------------------------------------------------- controls


def is_count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def hang_report(path: Path, probe_ns, fail_probe_ns) -> tuple:
    """(report, problems) for the hang control (control shard 3) from heartbeat.json, which the control job's
    finish step writes after the whole group ended: its test process's heartbeats, each `[monotonic ns, parent pid]`,
    the finish step's own monotonic start and the heartbeat count after a short recheck. fail_probe_ns is the failing
    control's (control shard 1's) probe.

    The step's stop is the first heartbeat with another parent pid (its shell ended while the test process lived on,
    re-parented) or, when the parent never changed, the last heartbeat (the process ended with its shell). Judged: the
    stop came at least HANG_STOP_MIN_NS after the step's probe (the step was not stopped before its 60 s limit) and
    before fail_probe_ns + FAIL_CONTROL_AFTER_NS (before the failing control could fail, so the limit stopped it, not a
    sibling's failure), and the finish step began less than HANG_GROUP_MAX_NS after the probe (the group did not wait
    for the 300 s sleep). A process that kept its parent and still beat when the group ended gives a late stop and
    fails: nothing then shows that its step was stopped at its limit. Reported only: whether the process outlived its
    step (its parent pid changed, or it still beat during the recheck)."""
    data = read_json(path / "heartbeat.json")
    data = data if isinstance(data, dict) else {}
    beats = [item for item in data.get("beats") or []
             if isinstance(item, list) and len(item) == 2 and all(is_count(value) for value in item)]
    end_ns, after = data.get("end_monotonic_ns"), data.get("beats_after_recheck")
    report = {"beats": len(beats), "beats_after_recheck": after if is_count(after) else None,
              "alive_after_probe_seconds": None, "stop_after_probe_seconds": None, "stop_seen_as": None,
              "stop_deadline_after_probe_seconds": None, "group_end_after_probe_seconds": None,
              "parent_lost_after_probe_seconds": None, "outlived_step": None}
    problems = []
    if not is_count(probe_ns):
        problems.append("shard-3.probe.json holds no monotonic timestamp of the step's start")
    if not is_count(fail_probe_ns):
        problems.append("shard-1.probe.json holds no monotonic timestamp: the hang control's stop cannot be placed "
                        "before the failing control's failure")
    if not beats:
        problems.append("heartbeat.json is missing or holds no heartbeat: the hang control's process was never observed")
    if not is_count(end_ns):
        problems.append("heartbeat.json holds no monotonic timestamp of the finish step")
    if problems:
        return report, problems
    lost = next((ns for ns, parent in beats if parent != beats[0][1]), None)
    stop = lost if lost is not None else beats[-1][0]
    deadline = fail_probe_ns + FAIL_CONTROL_AFTER_NS
    group = end_ns - probe_ns
    report.update(alive_after_probe_seconds=round((beats[-1][0] - probe_ns) / 1e9, 3),
                  stop_after_probe_seconds=round((stop - probe_ns) / 1e9, 3),
                  stop_seen_as="parent pid changed" if lost is not None else "last heartbeat",
                  stop_deadline_after_probe_seconds=round((deadline - probe_ns) / 1e9, 3),
                  group_end_after_probe_seconds=round(group / 1e9, 3),
                  parent_lost_after_probe_seconds=None if lost is None else round((lost - probe_ns) / 1e9, 3),
                  outlived_step=lost is not None or (report["beats_after_recheck"] or 0) > len(beats))
    seen = ("its shell ended (the parent pid changed)" if lost is not None
            else "its process's last heartbeat, with the parent pid unchanged")
    if stop - probe_ns < HANG_STOP_MIN_NS:
        problems.append(f"shard-3: the hang control's step stopped {(stop - probe_ns) / 1e9:.1f} s after it started "
                        f"({seen}), under {HANG_STOP_MIN_NS // 10 ** 9} s: the step was stopped before its 1-minute "
                        "limit")
    if stop >= deadline:
        problems.append(f"shard-3: the hang control's step stopped {(stop - probe_ns) / 1e9:.1f} s after it started "
                        f"({seen}), not before {(deadline - probe_ns) / 1e9:.1f} s, when the failing control could "
                        "fail: the stop is not attributable to the 1-minute limit")
    if group >= HANG_GROUP_MAX_NS:
        problems.append(f"shard-3: the finish step began {group / 1e9:.1f} s after the hang control's step started, "
                        f"not under {HANG_GROUP_MAX_NS // 10 ** 9} s: the group waited for the hang")
    return report, problems


def check_controls(artifact: Path, os_name: str, job_result: str | None, expected_sha: str | None = None) -> dict:
    """The control artifact against CONTROL_SHARDS (README.md, "Controls"): it must hold exactly <os>-controls,
    which passes only when every expectation holds. "started" is False when the group never started (the
    foreground probe step did not succeed or left no probe), which makes the OS incomplete, never a rule outcome.
    "unmeasurable" is True when the run records the foreground step's outcome (success) but none of the four control
    steps' outcomes, and every other expectation holds: the steps context then carries no background step's outcome,
    so the controls cannot be judged on this platform, which gives the OS no verdict (verdict_for_os). Any other
    failed expectation, a recorded wrong step outcome included, fails the controls."""
    path = artifact / f"{os_name}-controls"
    strays = sorted(entry.name for entry in artifact.iterdir() if entry.name != path.name) if artifact.is_dir() else []
    if not path.is_dir():
        return {"passed": False, "present": False, "started": False, "unstarted": [], "run_attempt": None,
                "job_status": None, "unmeasurable": False, "outcomes_unrecorded": None,
                "problems": ["no control run directory"], "shards": [], "job_result": job_result}
    meta, runtime, _timing, _status, problems = common_problems(path, os_name, "controls", 1, expected_sha, timed=False)
    if strays:
        problems.append(f"the control artifact holds entries besides {path.name}: {_cap(strays)}")
    unstarted = unstarted_reasons(meta, FOREGROUND_STEP)
    foreground = read_json(path / "foreground.probe.json")
    if not isinstance(foreground, dict):
        unstarted.append("foreground.probe.json is missing or not JSON: the group never started")
        problems.append("foreground.probe.json is missing or not JSON")
        foreground = {}
    if job_result != CONTROL_JOB_RESULT:
        problems.append(f"the control job's result is {job_result!r}, expected {CONTROL_JOB_RESULT!r} (a failing, a "
                        "crashing and a killed shard must fail the job)")
    shards, outcome_problems = [], []
    for index, spec in enumerate(CONTROL_SHARDS):
        label = f"shard-{index}"
        listed = read_text(path / f"{label}.txt")
        log = read_log(path, label, label, [spec["module"]])
        probe = log.probe or {}
        signals = probe.get("signals") or {}
        entry = {"shard": index, "module": spec["module"], "expect": spec["expect"], "exit_code": log.exit_code,
                 "ran": log.parsed.ran if log.parsed else None,
                 "status_word": log.parsed.status_word if log.parsed else None,
                 "step": spec["step"], "step_outcome": step_outcome(meta, spec["step"]),
                 "probe_monotonic_ns": probe.get("monotonic_ns"),
                 "signals": {name: (signals.get(name) or {}).get("handler") for name in SIGNALS},
                 "ignored": {name: (signals.get(name) or {}).get("ignored") for name in SIGNALS},
                 "env_propagated": (probe.get("env_present") or {}).get(CONTROL_ENV_NAME),
                 "python_version": probe.get("python_version")}
        # read_log's own messages: "<label>.command ..." for the command rule, "<label>.probe.json ..." for the probe.
        command_and_probe = [problem for problem in log.problems
                             if problem.startswith((f"{label}.command", f"{label}.probe.json"))]
        others = [problem for problem in log.problems if problem not in command_and_probe]
        mine = list(command_and_probe)
        if listed is None or listed.split() != [spec["module"]]:
            mine.append(f"{label}.txt does not list exactly {spec['module']}")
        if entry["step_outcome"] != spec["outcome"]:
            # The runner's own outcome of this step (steps.<id>.outcome after the group's implicit wait): each control
            # must fail or pass on its own, so a masked failure cannot hide behind another shard's.
            mine.append(f"{label}: the step's own outcome is {entry['step_outcome']!r}, expected {spec['outcome']!r}")
            outcome_problems.append(mine[-1])
        if log.probe is not None:
            if entry["env_propagated"] is not True:
                mine.append(f"{label}: {CONTROL_ENV_NAME}, exported through GITHUB_ENV by an earlier step, is not set "
                            "in this background step")
            if entry["python_version"] != foreground.get("python_version"):
                mine.append(f"{label}: python {entry['python_version']!r} in the background step, "
                            f"{foreground.get('python_version')!r} in the foreground step")
        parsed = log.parsed
        if parsed is None:
            mine.append(f"{label}.log is missing or empty")
        elif spec["expect"] in ("pass", "fail"):
            mine.extend(others)
            got, want = collections.Counter(parsed.records()), collections.Counter(spec["records"])
            if got != want:
                mine.append(f"{label}: records differ (missing {_cap(sorted(map(str, (want - got).elements())))}, "
                            f"unexpected {_cap(sorted(map(str, (got - want).elements())))})")
            if spec["expect"] == "pass" and (parsed.status_word != "OK" or log.exit_code != 0):
                mine.append(f"{label}: expected OK and exit 0, got {parsed.status_word} and {log.exit_code}")
            if spec["expect"] == "fail" and (parsed.status_word != "FAILED" or log.exit_code in (None, 0)):
                mine.append(f"{label}: expected FAILED and a non-zero exit, got {parsed.status_word} and {log.exit_code}")
        else:
            if spec["started"] not in parsed.started_ids():
                mine.append(f"{label}: {spec['started']} never started")
            if parsed.status_word is not None:
                mine.append(f"{label}: a summary ({parsed.status_word}) although the test should have ended the process")
            if spec["expect"] == "crash" and log.exit_code != spec["exit"]:
                mine.append(f"{label}: exit status {log.exit_code}, expected {spec['exit']} from os._exit")
            if spec["expect"] == "killed" and (path / f"{label}.exit").exists():
                mine.append(f"{label}: an exit status ({log.exit_code}) was written, so the 1-minute step limit did "
                            "not stop the step")
        entry["problems"], entry["passed"] = mine, not mine
        problems.extend(mine)
        shards.append(entry)
    starts = [entry["probe_monotonic_ns"] for entry in shards]
    spread = max(starts) - min(starts) if all(is_count(value) for value in starts) else None
    if spread is None:
        problems.append("a control step's probe holds no monotonic timestamp: their concurrency is unrecorded")
    elif spread > CONTROL_START_SPREAD_MAX_NS:
        problems.append(f"the control steps started {spread / 1e9:.1f} s apart, more than "
                        f"{CONTROL_START_SPREAD_MAX_NS // 10 ** 9} s: they did not run together")
    hang, hang_problems = hang_report(path, shards[3]["probe_monotonic_ns"], shards[1]["probe_monotonic_ns"])
    problems.extend(hang_problems)
    unrecorded = (step_outcome(meta, FOREGROUND_STEP) == "success"
                  and all(entry["step_outcome"] is None for entry in shards))
    unmeasurable = unrecorded and not unstarted and all(problem in outcome_problems for problem in problems)
    return {"passed": not problems, "present": True, "started": not unstarted, "unstarted": unstarted,
            "outcomes_unrecorded": unrecorded, "unmeasurable": unmeasurable,
            "job_status": (meta or {}).get("job_status"),
            "problems": problems[:LIST_CAP], "job_result": job_result, "run_attempt": attempt_of(runtime),
            "start_spread_seconds": None if spread is None else round(spread / 1e9, 3), "hang": hang,
            "foreground_signals": {name: ((foreground.get("signals") or {}).get(name) or {}).get("handler")
                                   for name in SIGNALS},
            "background_ignores_sigint": any(entry["ignored"].get("SIGINT") is True for entry in shards),
            "background_ignores_sigquit": any(entry["ignored"].get("SIGQUIT") is True for entry in shards),
            "shards": shards}


# --------------------------------------------------------------------------- verdict


def exact_median(values: list) -> Fraction:
    ordered = sorted(Fraction(value) for value in values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def seconds(value: Fraction | None):
    return None if value is None else round(float(value), 3)


def ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def job_result(needs, job: str):
    entry = needs.get(job) if isinstance(needs, dict) else None
    return entry.get("result") if isinstance(entry, dict) else None


def unrecorded_attempt(attempt) -> bool:
    return attempt is None or attempt == ""


def rerun_reasons(runs: list, controls: dict, compare_attempt) -> list:
    """Every sign of a re-run (README.md, "Trigger, repetition and re-runs"): the compare job's own run attempt other
    than "1", or a recorded run_attempt of any run or control directory other than "1". Checked first, before the
    inventory gate and every other condition: a re-run is never a rule outcome. An unrecorded attempt (no runtime.json,
    or none in it) is not a re-run but a partial run (partial_reasons)."""
    reasons = []
    if compare_attempt != "1":
        reasons.append(f"the compare job's own run attempt is {compare_attempt!r}, not '1'")
    for run in runs:
        if not unrecorded_attempt(run.attempt) and run.attempt != "1":
            reasons.append(f"{run.name}: run_attempt {run.attempt!r}")
    attempt = controls.get("run_attempt")
    if controls.get("present") and not unrecorded_attempt(attempt) and attempt != "1":
        reasons.append(f"the control run: run_attempt {attempt!r}")
    return reasons


def partial_reasons(os_name: str, runs: list, needs, controls: dict, min_repeats: int) -> list:
    """Why this OS's workflow run is cancelled or partial (then no rule outcome applies), else []."""
    reasons = []
    if isinstance(needs, dict):
        for job, allowed in NEEDS_RESULTS.items():
            result = job_result(needs, job)
            if result not in allowed:
                reasons.append(f"job {job}: result {result!r}")
    present = {(run.arm, run.repeat) for run in runs}
    for arm in arms_of(os_name):
        missing = [str(repeat) for repeat in range(1, min_repeats + 1) if (arm, repeat) not in present]
        if missing:
            reasons.append(f"arm {arm}: no run directory for repeat {', '.join(missing)}")
    cancelled = sorted(run.name for run in runs if run.job_status == "cancelled")
    if controls.get("present") and controls.get("job_status") == "cancelled":
        cancelled.append(f"{os_name}-controls")
    if cancelled:
        reasons.append(f"cancelled jobs: {', '.join(cancelled)}")
    for run in runs:
        if unrecorded_attempt(run.attempt):
            why = ("runtime.json is missing or not JSON" if run.runtime is None
                   else "runtime.json records no run_attempt")
            reasons.append(f"{run.name}: the run attempt is unrecorded ({why})")
    if controls.get("present") and unrecorded_attempt(controls.get("run_attempt")):
        reasons.append("the control run: the run attempt is unrecorded (runtime.json is missing, not JSON or "
                       "records no run_attempt)")
    for run in runs:
        if run.unstarted:
            reasons.append(f"{run.name}: {'; '.join(run.unstarted)}")
    if not controls.get("present"):
        reasons.append("no control run directory")
    elif not controls.get("started"):
        reasons.append("the control run's parallel group never started: " + "; ".join(controls.get("unstarted") or []))
    if controls.get("passed") and isinstance(needs, dict) and job_result(needs, "controls-check") == "failure":
        # compare.py's own check of the same control artifact passed, so the check job failed outside the checks it
        # repeats: a setup step, the head assertion, the download or the runner.
        reasons.append("job controls-check: result 'failure', although compare.py's own check of the same control "
                       "artifact passed: the check job failed outside its checks (a setup step, the download or the "
                       "runner)")
    return reasons


def incomplete_reasons(reruns: list, partial: list) -> list:
    return ((["a re-run, never a rule outcome: " + "; ".join(reruns)] if reruns else [])
            + (["a cancelled or partial run, not a rule outcome: " + "; ".join(partial)] if partial else []))


def compare_with_baseline(os_name: str, by_arm: dict, baseline: dict) -> None:
    """Flaky ids from the eligible S runs; every sharded run's records against the first eligible S run."""
    serial = [run for run in by_arm[SERIAL_ARM] if not run.problems]
    versions = sorted({run.python_version for run in serial})
    baseline.update(s_runs=len(by_arm[SERIAL_ARM]), s_eligible=len(serial), python_versions=versions)
    if len(versions) > 1:
        for run in serial:
            run.problems.append(f"the eligible S runs used different python versions {versions}")
        serial = []
    reference, flaky = None, set()
    if serial:
        grouped = [groups(run.logs) for run in serial]
        keys = set().union(*grouped)
        flaky = {key for key in keys if len({g.get(key, ()) for g in grouped}) > 1}
        baseline["flaky_ids"], baseline["flaky_total"] = sorted(flaky)[:1000], len(flaky)
        reference = grouped[0]
    for arm in arms_of(os_name)[1:]:
        for run in by_arm[arm]:
            if reference is None:
                run.problems.append("no eligible S baseline on this OS")
                continue
            if run.python_version not in versions:
                run.problems.append(f"python {run.python_version!r} differs from S {versions}")
            mine = groups(run.logs)
            diffs = [{"id": key, "S": [list(r) for r in reference.get(key, ())], "arm": [list(r) for r in mine.get(key, ())]}
                     for key in sorted((set(reference) | set(mine)) - flaky) if reference.get(key) != mine.get(key)]
            run.mismatch_total, run.mismatches = len(diffs), diffs[:LIST_CAP]
            run.mismatch_keys = [diff["id"] for diff in diffs]
            if diffs:
                run.problems.append(f"{len(diffs)} ids differ from the S baseline: {_cap([d['id'] for d in diffs])}")


def unfinished_steps(run: Run, inventory: Inventory) -> list:
    """The labels of a sharded run's steps that never wrote an exit status (they never reached their command, or were
    stopped before its end), when those steps alone make the run ineligible; [] otherwise. Alone means: the run's test
    phase started, and each of its problems is a file such a step never wrote, a parse anomaly of such a step's
    unfinished log or its unexecuted ids, or a count of inventory ids that never ran, or that differ from the S
    baseline, all of which such a step's modules own. Reported for the outcome record (README.md, rule 5), never judged:
    the run stays ineligible."""
    if run.arm == SERIAL_ARM or run.unstarted:
        return []
    stopped = {log.label: log for log in run.logs if log.exit_missing}
    if not stopped:
        return []
    owned = {item for log in stopped.values() for module in log.modules
             for item in inventory.module_ids.get(module, [])}

    def owns(key: str) -> bool:
        # A test id, or a fixture key such as "setUpClass (tests.test_x.Class)" whose parent prefixes owned ids.
        _name, _, parent = key.partition(" (")
        return key in owned or bool(parent) and any(item.startswith(parent[:-1] + ".") for item in owned)

    for problem in run.problems:
        label, _, rest = problem.partition(": ")
        if label in stopped:
            if (rest in (f"{label}.log is missing", f"{label}.log is empty", f"{label}.exit is missing",
                         f"{label}.command is missing", f"{label}.probe.json is missing or not JSON")
                    or rest.startswith(f"{label}.log: ") and "unittest-parallel" not in rest
                    or rest.startswith("its executed ids are not its modules' ids")):
                continue
            return []
        if NEVER_RAN_RE.match(problem) and set(run.missing_ids) <= owned:
            continue
        if DIFFER_RE.match(problem) and all(owns(key) for key in run.mismatch_keys):
            continue
        return []
    return sorted(stopped)


def verdict_for_os(os_name: str, runs: list, inventory: Inventory, controls: dict, needs, min_repeats: int,
                   compare_attempt) -> dict:
    """The outcome for one OS, in the preregistered order (README.md, "Decision rule", rule 5): re-runs first; then a
    failed or unreported inventory gate; then the other incomplete conditions; then an unusable inventory artifact, an
    ineligible S baseline or unmeasurable controls (no verdict); then the rule (reject or adopt)."""
    report = {"outcome": None, "selected_arm": None, "reasons": [], "arms": {}, "flags": [],
              "baseline": {"flaky_ids": [], "flaky_total": 0}}
    reruns = rerun_reasons(runs, controls, compare_attempt)
    if job_result(needs, "inventory") == "failure":
        gate = inventory.report if isinstance(inventory.report, dict) else {}
        findings = gate.get("problems") if isinstance(gate.get("problems"), list) else []
        if reruns:
            report.update(outcome="incomplete", reasons=incomplete_reasons(reruns, []))
        elif gate.get("ok") is False and findings:
            report.update(outcome="no verdict", reasons=[
                f"the inventory gate failed on {len(findings)} findings (job inventory: result 'failure', report.json "
                "ok false), so no arm ran"])
        else:
            # The job failed before its gate reported a finding: a setup step, the upload, or the gate's own child
            # interpreter stopped from outside (report.json execution_problems): a partial run.
            stopped = gate.get("execution_problems") if isinstance(gate.get("execution_problems"), list) else []
            report.update(outcome="incomplete", reasons=incomplete_reasons([], [
                "job inventory: result 'failure' without a report.json that records a gate finding, so the gate "
                "never reported a finding and no arm ran"
                + (f" (execution problems: {'; '.join(str(item)[:300] for item in stopped[:3])})" if stopped else "")]))
        return report
    if inventory.problems:
        partial = partial_reasons(os_name, runs, needs, controls, min_repeats)
        report.update(outcome="incomplete" if reruns or partial else "no verdict",
                      reasons=["the inventory artifact is unusable: " + "; ".join(inventory.problems[:10])]
                      + incomplete_reasons(reruns, partial))
        return report
    by_arm = {arm: sorted((run for run in runs if run.arm == arm), key=lambda run: run.repeat)
              for arm in arms_of(os_name)}
    compare_with_baseline(os_name, by_arm, report["baseline"])
    s_times = [Fraction(run.step_ns, 10 ** 9) for run in by_arm[SERIAL_ARM] if run.step_ns is not None]
    medians = {}
    for arm in arms_of(os_name):
        mine = by_arm[arm]
        eligible = [run for run in mine if not run.problems]
        times = [Fraction(run.step_ns, 10 ** 9) for run in mine if run.step_ns is not None]
        reasons = []
        if len(mine) < min_repeats:
            reasons.append(f"{len(mine)} runs, the preregistration needs {min_repeats}")
        if len(eligible) != len(mine):
            reasons.append(f"{len(mine) - len(eligible)} ineligible runs")
        if arm != SERIAL_ARM and not controls.get("passed"):
            reasons.append("the controls of this OS are unmeasurable" if controls.get("unmeasurable")
                           else "the controls of this OS did not pass")
        entry = {"runs": len(mine), "eligible_runs": len(eligible), "eligible": not reasons, "reasons": reasons,
                 "seconds": [seconds(value) for value in times]}
        if arm != SERIAL_ARM:
            unfinished = {run.name: unfinished_steps(run, inventory) for run in mine if run.problems}
            entry["unfinished_steps"] = {name: labels for name, labels in unfinished.items() if labels}
            # Ineligible only because steps never wrote an exit status (a runner fault looks so): flagged below.
            entry["ineligible_only_through_unfinished_steps"] = (
                bool(unfinished) and all(unfinished.values()) and reasons == [f"{len(unfinished)} ineligible runs"])
        if times and len(times) == len(mine):
            medians[arm] = exact_median(times)
            entry.update(median_seconds=seconds(medians[arm]), min_seconds=seconds(min(times)),
                         max_seconds=seconds(max(times)))
            if arm != SERIAL_ARM and s_times:
                median_ratio = medians[arm] / exact_median(s_times)
                max_ratio = max(times) / min(s_times)
                entry.update(median_vs_s_median=round(float(median_ratio), 4), max_vs_s_fastest=round(float(max_ratio), 4),
                             median_vs_s_median_exact=ratio_text(median_ratio),
                             max_vs_s_fastest_exact=ratio_text(max_ratio),
                             meets_speed_rule=median_ratio <= MEDIAN_RATIO_MAX and max_ratio <= MAX_RATIO_MAX)
        report["arms"][arm] = entry
    partial = partial_reasons(os_name, runs, needs, controls, min_repeats)
    if reruns or partial:
        report.update(outcome="incomplete", reasons=incomplete_reasons(reruns, partial))
        return report
    no_verdict = []
    if not report["arms"][SERIAL_ARM]["eligible"]:
        no_verdict.append("the S baseline is not eligible: " + "; ".join(report["arms"][SERIAL_ARM]["reasons"]))
    if controls.get("unmeasurable"):
        no_verdict.append("the controls are unmeasurable: the control run records the foreground step's outcome but "
                          "none of the four control steps' outcomes (the steps context carries no background step's "
                          "outcome), and every other control expectation holds")
    if no_verdict:
        report.update(outcome="no verdict", reasons=no_verdict)
        return report
    order = arms_of(os_name)
    candidates = [arm for arm in order[1:] if report["arms"][arm]["eligible"] and arm in medians]
    fastest = min(candidates, key=lambda arm: (medians[arm], order.index(arm))) if candidates else None
    for arm in order[1:]:
        entry = report["arms"][arm]
        if arm != fastest and entry.get("ineligible_only_through_unfinished_steps"):
            # Reported, never judged (README.md, rule 5): the outcome record must address whether a runner fault that
            # stopped these steps before their command or exit status decided this outcome. The arm's median is shown
            # as recorded; a run with an unfinished step did less, or stalled, work, so it is not compared.
            steps = "; ".join(name + ": " + ", ".join(labels) for name, labels in entry["unfinished_steps"].items())
            other = (f"the fastest eligible arm {fastest}'s {report['arms'][fastest].get('median_seconds')} s"
                     if fastest else "no sharded arm eligible")
            report["flags"].append(f"arm {arm} was ineligible only because steps never wrote an exit status ({steps}); "
                                   f"its median step time {entry.get('median_seconds')} s, {other}: the outcome record "
                                   "must address it")
    if not candidates:
        report.update(outcome="reject", reasons=["no sharded arm is eligible"])
        return report
    report["fastest_eligible_arm"] = fastest
    entry = report["arms"][fastest]
    if not entry.get("meets_speed_rule"):
        report.update(outcome="reject", reasons=[
            f"the fastest eligible arm {fastest} misses the speed rule (median {entry.get('median_vs_s_median_exact')} "
            f"of the S median, slowest {entry.get('max_vs_s_fastest_exact')} of the fastest S run; the rule allows "
            f"{ratio_text(MEDIAN_RATIO_MAX)} and {ratio_text(MAX_RATIO_MAX)})"])
        return report
    report.update(outcome="adopt", selected_arm=fastest)
    return report


def run_summary(run: Run) -> dict:
    item = {"name": run.name, "os": run.os, "arm": run.arm, "repeat": run.repeat, "eligible": not run.problems,
            "reasons": run.problems[:LIST_CAP], "reasons_total": len(run.problems), "step_ns": run.step_ns,
            "step_seconds": seconds(Fraction(run.step_ns, 10 ** 9)) if run.step_ns else None,
            "run_attempt": run.attempt, "job_status": run.job_status, "test_phase_started": not run.unstarted,
            "unstarted_reasons": run.unstarted, "steps": (run.meta or {}).get("steps"),
            "checkout_clean": None if run.checkout_status is None else run.checkout_status == "",
            "mismatch_total": run.mismatch_total, "mismatches": run.mismatches, "missing_total": len(run.missing_ids),
            "missing_ids": run.missing_ids[:LIST_CAP], "extra_total": len(run.extra_ids),
            "extra_ids": run.extra_ids[:LIST_CAP], "repeated_total": len(run.repeated_ids), "logs": []}
    for field in ("python_version", "platform", "runner_image", "checkout_sha"):
        item[field] = (run.meta or {}).get(field)
    item["clock"] = (run.timing or {}).get("clock")
    for log in run.logs:
        parsed = log.parsed
        signals = (log.probe or {}).get("signals") or {}
        item["logs"].append({"label": log.label, "modules": len(log.modules), "exit_code": log.exit_code,
                             "ran": parsed.ran if parsed else None, "status_word": parsed.status_word if parsed else None,
                             "status_counts": parsed.status_counts if parsed else None,
                             "notes_total": len(parsed.notes) if parsed else None,
                             "python_version": (log.probe or {}).get("python_version"),
                             "sigint_ignored": (signals.get("SIGINT") or {}).get("ignored"),
                             "sigquit_ignored": (signals.get("SIGQUIT") or {}).get("ignored"),
                             "env_present": (log.probe or {}).get("env_present")})
    return item


def arm_artifacts(results: Path) -> tuple:
    """([(artifact name, run directory, its other entries)], [ignored entries]) of the downloaded arm artifacts.

    The compare job downloads `arm-*` without merge-multiple, so each artifact lands in its own directory named
    after it (actions/download-artifact src/download-artifact.ts at 3e5f45b2, lines 186-195) and must hold exactly
    the run directory its name gives. When only one artifact matches, that action extracts it without the
    directory; such a bare run directory is not attributed and is ignored, and the missing runs make the OS
    incomplete. The control artifact's directory is read by check_controls."""
    found, ignored = [], []
    for entry in sorted(results.iterdir()) if results.is_dir() else []:
        if entry.name == CONTROL_ARTIFACT and entry.is_dir():
            continue
        name = entry.name[len(ARM_ARTIFACT_PREFIX):] if entry.name.startswith(ARM_ARTIFACT_PREFIX) else ""
        match = RUN_DIR_RE.match(name) if entry.is_dir() else None
        if not match or match.group("controls"):
            ignored.append(entry.name)
        elif not (entry / name).is_dir():
            ignored.append(f"{entry.name} (holds no {name} directory)")
        else:
            found.append((entry.name, entry / name, sorted(child.name for child in entry.iterdir() if child.name != name)))
    return found, ignored


def load_runs(results: Path, os_name: str, inventory: Inventory, expected_sha: str | None) -> tuple:
    """(runs of os_name, ignored entries) from the arm artifacts; a run whose artifact holds anything besides its
    run directory is ineligible, because another job's files would otherwise pass as this run's."""
    runs = []
    found, ignored = arm_artifacts(results)
    for artifact, path, others in found:
        match = RUN_DIR_RE.match(path.name)
        if match.group("os") != os_name:
            continue
        run = read_run(path, os_name, match.group("arm"), int(match.group("rep")), inventory, expected_sha)
        if others:
            run.problems.append(f"its artifact {artifact} holds entries besides its run directory: {_cap(others)}")
        runs.append(run)
    return runs, ignored


def checkout_report(results: Path) -> dict:
    """The clean-checkout rule on its own: every attributed run directory's git-status.txt exists and is empty."""
    items = []
    directories = [path for _artifact, path, _others in arm_artifacts(results)[0]]
    control = results / CONTROL_ARTIFACT
    directories += [entry for entry in sorted(control.iterdir()) if entry.is_dir()] if control.is_dir() else []
    for entry in directories:
        status = read_text(entry / "git-status.txt")
        clean = status == ""
        items.append({"name": entry.name, "clean": clean, "status": None if status is None else status[:4000],
                      "reason": None if clean else ("git-status.txt is missing" if status is None else
                                                    "the checkout was not clean after the run")})
    dirty = [item["name"] for item in items if not item["clean"]]
    return {"schema": "suite-shards-checkout-status/1", "rule": "every run directory's git-status.txt exists and is empty",
            "runs": items, "dirty": dirty, "ok": bool(items) and not dirty}


def build_result(results: Path, inventory_dir: Path, expected_sha: str | None, os_name: str | None, needs,
                 min_repeats: int = REPEATS, weights: Path | None = HERE / "weights.json",
                 compare_attempt: str | None = None) -> dict:
    """result.json for the artifacts under results. compare_attempt is the compare job's own GITHUB_RUN_ATTEMPT;
    anything but "1" (None included) makes every measured OS incomplete."""
    probe = load_inventory(inventory_dir, None, None)
    control = results / CONTROL_ARTIFACT
    runs_seen = sorted({RUN_DIR_RE.match(path.name).group("os") for _artifact, path, _others in arm_artifacts(results)[0]}
                       | {RUN_DIR_RE.match(entry.name).group("os") for entry in
                          (control.iterdir() if control.is_dir() else []) if RUN_DIR_RE.match(entry.name)})
    measured = [os_name] if os_name else runs_seen
    controls, verdicts, all_runs, ignored = {}, {}, [], arm_artifacts(results)[1]
    for os_key in OSES:
        if os_key not in measured:
            verdicts[os_key] = {"outcome": "no verdict", "selected_arm": None, "arms": {}, "flags": [],
                                "baseline": {"flaky_ids": [], "flaky_total": 0},
                                "reasons": [f"no run directory: this result covers {', '.join(measured) or 'no OS'}; "
                                            f"{os_key} is measured by its own trial workflow"]}
            continue
        inventory = load_inventory(inventory_dir, os_key, weights)
        mine, ignored = load_runs(results, os_key, inventory, expected_sha)
        all_runs.extend(mine)
        # This job checks the control artifact itself; "passed" is that check. The controls-check job's result is kept
        # beside it: when it failed although this check passed, the check job failed outside the checks it repeats,
        # which makes the OS incomplete (partial_reasons); when both failed, the controls failed.
        controls[os_key] = check_controls(control, os_key, job_result(needs, "controls"), expected_sha)
        controls[os_key]["controls_check_result"] = job_result(needs, "controls-check")
        verdicts[os_key] = verdict_for_os(os_key, mine, inventory, controls[os_key], needs, min_repeats, compare_attempt)
        probe = inventory
    return {
        "schema": SCHEMA,
        "decision_rule": {
            "serial_baseline": "S needs three runs, each with a complete summary, an exit status that agrees with its "
                               "status line, executed ids equal to the inventory with each id once, the exact command "
                               "python3 -m unittest -v, a clean checkout, run_attempt 1, the pull request head and a "
                               "valid step time; the eligible S runs share one python version",
            "sharded_arm": "every run eligible: every shard log (and the tail) complete, its exit status consistent with "
                           "its status line, the exact command python3 -m unittest -v <its list>, its list equal to the "
                           "inventory's, its executed ids equal to its modules' ids, the union over all logs equal to "
                           "the inventory with each id once, its (kind, key, outcome) records equal to the first "
                           "eligible S run outside the flaky ids, the same python version as S in every step, a clean "
                           "checkout, run_attempt 1, the pull request head and a valid step time; at least three runs; "
                           "the controls of the OS passed",
            "speed": "take the eligible sharded arm with the smallest median step time (a tie goes to the arm without "
                     "a tail); adopt it only if its median <= 3/5 of the S median and its slowest run <= 3/4 of the "
                     "fastest S run, compared as exact fractions; otherwise reject, with no fall-through; no eligible "
                     "sharded arm rejects",
            "order": "re-runs first; then a failed or unreported inventory gate; then the other incomplete "
                     "conditions; then an unusable inventory artifact, an ineligible S baseline or unmeasurable "
                     "controls (no verdict); then the speed rule",
            "incomplete": "a re-run (the compare job's own run attempt other than 1, or a recorded run_attempt of any "
                          "run or control directory other than 1), a cancelled or skipped job, a missing run "
                          "directory, a job status cancelled (of an arm run or of the control run), an unrecorded run "
                          "attempt (runtime.json missing or without run_attempt), a run whose test phase never started "
                          "(its clock-start step did not succeed or timing.json records no start), a missing control "
                          "run or one whose parallel group never started, a controls-check job that failed although "
                          "this job's own check of the same control artifact passed, or an inventory job that failed "
                          "without a report.json that records a gate finding (the gate never reported, or its own "
                          "child interpreter was stopped from outside) makes the OS incomplete, which is recorded as "
                          "such and is never a rule outcome",
            "no_verdict": "an inventory gate that failed on a finding, an unusable inventory artifact, an ineligible S "
                          "baseline, or unmeasurable controls (the control run records the foreground step's outcome "
                          "but none of the four control steps' outcomes, and every other control expectation holds)",
            "flags": "a sharded arm that was ineligible only because steps never wrote an exit status is flagged when "
                     "the rule rejects or adopts; the outcome record must address it; reported, never judged",
            "protocol": "a run cancelled by hand, or by a reopen made while it was in progress, after its first "
                        "serial, shards or controls job started is a protocol deviation that ends that OS's trial "
                        "without a verdict; the outcome record judges it, not compare.py, whose result for that run "
                        "stays incomplete",
        },
        "inputs": {"expected_sha": expected_sha, "os": os_name, "min_repeats": min_repeats,
                   "compare_run_attempt": compare_attempt,
                   "inventory": {"ids": probe.count, "test_files": len(probe.module_ids), "sha256": probe.sha256,
                                 "problems": probe.problems[:LIST_CAP],
                                 "python_version": (probe.report or {}).get("python_version"),
                                 "lists_recomputed": weights is not None},
                   "needs": needs, "ignored_entries": ignored},
        "controls": controls,
        "runs": [run_summary(run) for run in all_runs],
        "verdicts": verdicts,
    }


def summary_markdown(result: dict) -> str:
    def number(value, digits=1):
        return "-" if value is None else (f"{value:.{digits}f}" if isinstance(value, float) else str(value))

    lines = ["### Suite-shards oracle (compare.py)", "",
             "| OS | Arm | Runs | Eligible runs | Median s | Min s | Max s | Median / S median | Max / S fastest "
             "| Arm eligible |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for os_name, verdict in result["verdicts"].items():
        for arm, entry in verdict["arms"].items():
            lines.append(f"| {os_name} | {arm} | {entry['runs']} | {entry['eligible_runs']} | "
                         f"{number(entry.get('median_seconds'))} | {number(entry.get('min_seconds'))} | "
                         f"{number(entry.get('max_seconds'))} | {number(entry.get('median_vs_s_median'), 3)} | "
                         f"{number(entry.get('max_vs_s_fastest'), 3)} | {'yes' if entry['eligible'] else 'no'} |")
    lines.append("")
    for os_name, verdict in result["verdicts"].items():
        reasons = "; ".join(verdict["reasons"])
        lines.append(f"- **{os_name}**: {verdict['outcome']}"
                     f"{' ' + verdict['selected_arm'] if verdict['selected_arm'] else ''}"
                     f"{' (' + reasons + ')' if reasons else ''}; flaky ids in S: {verdict['baseline']['flaky_total']}")
        for flag in verdict.get("flags") or []:
            lines.append(f"- FLAG {os_name}: {flag}")
    for os_name, control in result["controls"].items():
        exits = ", ".join(f"{item['module']} {'killed (no exit status)' if item['exit_code'] is None else item['exit_code']}"
                          f" (step {item.get('step_outcome')})" for item in control.get("shards", []))
        hang = control.get("hang") or {}
        state = ("passed" if control.get("passed") else "UNMEASURABLE (no control step outcome recorded)"
                 if control.get("unmeasurable") else "FAILED")
        lines.append(f"- controls {os_name}: {state} (job result {control.get('job_result')}, controls-check "
                     f"{control.get('controls_check_result')}; {exits or 'no shard'}); background steps ignore SIGINT: "
                     f"{control.get('background_ignores_sigint')}, SIGQUIT: {control.get('background_ignores_sigquit')}; "
                     f"steps started within {control.get('start_spread_seconds')} s; hang step stopped "
                     f"{hang.get('stop_after_probe_seconds')} s after its start (seen as: {hang.get('stop_seen_as')}; "
                     f"deadline {hang.get('stop_deadline_after_probe_seconds')} s), its process last beat at "
                     f"{hang.get('alive_after_probe_seconds')} s, group ended by "
                     f"{hang.get('group_end_after_probe_seconds')} s, its process outlived its step: "
                     f"{hang.get('outlived_step')}")
    bad = [run["name"] for run in result["runs"] if not run["eligible"]]
    lines.append(f"- ineligible arm-runs: {', '.join(bad) if bad else 'none'}")
    inventory = result["inputs"]["inventory"]
    lines.append(f"- inventory: {inventory['ids']} ids in {inventory['test_files']} test files; "
                 f"problems: {len(inventory['problems'])}")
    lines.append(f"- compare job run attempt: {result['inputs'].get('compare_run_attempt')}")
    lines.append("- This summary is a rendering; result.json, the exit files and the job results are the record.")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    verdict = commands.add_parser("verdict")
    verdict.add_argument("--results", required=True, type=Path)
    verdict.add_argument("--inventory", required=True, type=Path)
    verdict.add_argument("--expected-sha", required=True)
    verdict.add_argument("--run-attempt", required=True,
                         help="the compare job's own GITHUB_RUN_ATTEMPT; anything but 1 makes every OS incomplete")
    verdict.add_argument("--os", choices=OSES, help="the OS this workflow measures (default: every OS with runs)")
    verdict.add_argument("--needs", type=Path, help="the compare job's needs context as JSON")
    verdict.add_argument("--out", required=True, type=Path)
    verdict.add_argument("--summary-md", type=Path)
    verdict.add_argument("--checkout-status", type=Path)
    verdict.add_argument("--min-repeats", type=int, default=REPEATS)
    verdict.add_argument("--skip-list-recompute", action="store_true",
                         help="do not re-derive the inventory's lists with make_shards.py (for local checks of "
                              "lists made elsewhere; result.json records it)")
    controls = commands.add_parser("controls")
    controls.add_argument("--artifact", required=True, type=Path,
                          help="the downloaded control artifact, holding exactly <os>-controls")
    controls.add_argument("--os", required=True, choices=OSES)
    controls.add_argument("--job-result", required=True)
    controls.add_argument("--expected-sha")
    controls.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "controls":
        report = check_controls(args.artifact, args.os, args.job_result, args.expected_sha)
        if args.out:
            args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        state = ("passed" if report["passed"] else "UNMEASURABLE (no control step outcome recorded)"
                 if report["unmeasurable"] else "FAILED")
        print(f"controls {args.os}: {state}")
        for problem in report["problems"]:
            print(f"  {problem}")
        return 0 if report["passed"] else 1
    needs = None
    if args.needs is not None:
        needs = read_json(args.needs)
        if not isinstance(needs, dict):
            print("compare.py: --needs is not a JSON object", file=sys.stderr)
            return 2
    result = build_result(args.results, args.inventory, args.expected_sha, args.os, needs, args.min_repeats,
                          None if args.skip_list_recompute else HERE / "weights.json", args.run_attempt)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.summary_md:
        args.summary_md.write_text(summary_markdown(result), encoding="utf-8")
    if args.checkout_status:
        args.checkout_status.write_text(json.dumps(checkout_report(args.results), indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
    for os_name, entry in result["verdicts"].items():
        print(f"{os_name}: {entry['outcome']} {entry['selected_arm'] or ''}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
