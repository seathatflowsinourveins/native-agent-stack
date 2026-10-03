#!/usr/bin/env python3
"""Run-directory recorder of the suite-shards trial workflows (2026-10-03), stdlib only.

  python3 record.py runtime DIR                      DIR/runtime.json  (before the test phase)
  python3 record.py start DIR                        DIR/timing-start.json (the step before the test phase)
  python3 record.py probe DIR NAME                   DIR/NAME.probe.json (inside a step, before its command)
  python3 record.py finish DIR --os OS --arm ARM --repeat N [--heartbeat FILE]
                                                     DIR/timing.json, DIR/meta.json, DIR/git-status.txt and,
                                                     with --heartbeat, DIR/heartbeat.json
                                                     (the step after the test phase, `if: always()`)

runtime.json keeps the run attempt (GITHUB_RUN_ATTEMPT: 1 for a run's first attempt, one more for each re-run;
github/docs contexts.md at 03d2e24b, line 209), the runner image, architecture and CPU count, and the
interpreter. The fields follow the recorder steps of the first trial's workflow
(.github/workflows/macos-suite-parallel-trial.yml at 1e4bb5ab, lines 686-732) without its package list.

The timer reads time.monotonic_ns() in two processes, start and finish, and keeps their difference as the
test phase's length. CPython takes that clock from clock_gettime(CLOCK_MONOTONIC) on Linux and
mach_absolute_time() on macOS (Python/pytime.c at v3.13.16 lines 1164-1170 and 1202-1203; v3.12.3 lines
1105-1111 and 1145-1146), both system-wide clocks, so two processes on one runner read the same clock;
timing.json also keeps the wall-clock difference and the clock's implementation name, and compare.py checks
that the two differences agree.

A probe records what one step's processes inherit, for the oracle and the first-run checks: the interpreter
version and path, whether SIGINT and SIGQUIT are ignored, by name only whether each variable of ENV_NAMES is set
(never a value), and the step's start as time.monotonic_ns() and time.time_ns().

finish takes the end timestamp first, then records the job status (JOB_STATUS, from the job context's
status: success, failure or cancelled; contexts.md line 384), the outcome and conclusion of every step that has an
`id` (STEPS_JSON, the workflow's `toJSON(steps)`; outputs are dropped), the checkout's HEAD and its
`git status --porcelain=v1 --untracked-files=all` (the text "git status failed" when git fails). With
--heartbeat it also reads the hang control's heartbeat file twice, HEARTBEAT_RECHECK_SECONDS apart, and writes
every `<monotonic ns> <parent pid>` line of the first read, the line count of the second and its own end
timestamp to heartbeat.json, so the oracle can tell a test process that was stopped from one still running.
"""

from __future__ import annotations

import time

_END_NS = time.monotonic_ns()  # finish: the end of the test phase, before anything else is imported

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import platform  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

# The four exports the suite-environment steps write to GITHUB_ENV, the control job's own export, and the two
# variables the runner sets for every step, which some tests read (for example IN_CI in tests/test_secret_path_guard.py).
ENV_NAMES = ("CHILD_USAGE_SHELL_PARSER", "LANDSCAPE_SWEEP_SKILLS_YAML", "PROMOTION_GATE_PYTHON",
             "REQUIRE_PROMOTION_GATE_VENV", "SUITE_SHARDS_ENV_PROBE", "GITHUB_ACTIONS", "CI")
HEARTBEAT_RECHECK_SECONDS = 3


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def runtime(out: Path) -> None:
    write_json(out / "runtime.json", {
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""), "image_os": os.environ.get("ImageOS", ""),
        "image_version": os.environ.get("ImageVersion", ""), "runner_os": os.environ.get("RUNNER_OS", ""),
        "runner_arch": os.environ.get("RUNNER_ARCH", ""), "cpu_count": os.cpu_count(),
        "python_executable": sys.executable, "python_full_version": sys.version,
        "python_version": platform.python_version(), "platform": platform.platform(), "machine": platform.machine()})


def start(out: Path) -> None:
    write_json(out / "timing-start.json", {"clock": time.get_clock_info("monotonic").implementation,
                                           "start_monotonic_ns": time.monotonic_ns(), "wall_start_ns": time.time_ns()})


def disposition(signum) -> dict:
    handler = signal.getsignal(signum)
    # repr, not str: since CPython 3.11 str() of the Handlers IntEnum is the bare number.
    return {"handler": repr(handler), "ignored": handler == signal.SIG_IGN,
            "default": handler in (signal.SIG_DFL, signal.default_int_handler)}


def probe(out: Path, name: str) -> None:
    write_json(out / f"{name}.probe.json", {
        "clock": time.get_clock_info("monotonic").implementation, "monotonic_ns": time.monotonic_ns(),
        "wall_ns": time.time_ns(), "python_full_version": sys.version, "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "signals": {"SIGINT": disposition(signal.SIGINT), "SIGQUIT": disposition(signal.SIGQUIT)},
        "env_present": {key: key in os.environ for key in ENV_NAMES}})


def step_outcomes(text: str | None):
    """{step id: {"outcome", "conclusion"}} from the steps context as JSON, or None when it is absent or invalid."""
    try:
        steps = json.loads(text) if text else None
    except ValueError:
        return None
    if not isinstance(steps, dict):
        return None
    return {str(key): {"outcome": value.get("outcome"), "conclusion": value.get("conclusion")}
            for key, value in steps.items() if isinstance(value, dict)}


def heartbeat_lines(path: Path) -> list:
    """Every complete `<monotonic ns> <parent pid>` line of the heartbeat file, in order ([] when it is missing)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    beats = []
    for line in text.split("\n")[:-1]:  # the last element is "" or a line still being written
        fields = line.split()
        if len(fields) == 2 and all(field.isdigit() for field in fields):
            beats.append([int(fields[0]), int(fields[1])])
    return beats


def heartbeat(out: Path, path: Path, end_ns: int) -> None:
    beats = heartbeat_lines(path)
    time.sleep(HEARTBEAT_RECHECK_SECONDS)
    write_json(out / "heartbeat.json", {"file": path.name, "end_monotonic_ns": end_ns, "beats": beats,
                                        "recheck_seconds": HEARTBEAT_RECHECK_SECONDS,
                                        "beats_after_recheck": len(heartbeat_lines(path))})


def git(*args):
    done = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else None


def finish(out: Path, os_name: str, arm: str, repeat: int, end_ns: int) -> None:
    wall_end = time.time_ns()
    timing = {"clock": time.get_clock_info("monotonic").implementation, "end_monotonic_ns": end_ns,
              "wall_end_ns": wall_end, "start_monotonic_ns": None, "wall_start_ns": None,
              "step_ns": None, "step_seconds": None, "wall_ns": None, "problems": []}
    try:
        begun = json.loads((out / "timing-start.json").read_text(encoding="utf-8"))
        timing["start_monotonic_ns"] = begun["start_monotonic_ns"]
        timing["wall_start_ns"] = begun["wall_start_ns"]
        if begun.get("clock") != timing["clock"]:
            timing["problems"].append(f"start clock {begun.get('clock')!r} differs from end clock {timing['clock']!r}")
        timing["step_ns"] = end_ns - begun["start_monotonic_ns"]
        timing["wall_ns"] = wall_end - begun["wall_start_ns"]
        timing["step_seconds"] = f"{timing['step_ns'] / 1e9:.3f}"
    except (OSError, ValueError, KeyError, TypeError):
        timing["problems"].append("timing-start.json is missing or unreadable: the test phase was never timed")
    write_json(out / "timing.json", timing)
    head = git("rev-parse", "HEAD")
    write_json(out / "meta.json", {
        "os": os_name, "arm": arm, "repeat": repeat, "checkout_sha": head.strip() if head else None,
        "python_version": platform.python_version(), "platform": platform.platform(),
        "runner_image": os.environ.get("ImageVersion", ""), "job_status": os.environ.get("JOB_STATUS", ""),
        "steps": step_outcomes(os.environ.get("STEPS_JSON"))})
    status = git("status", "--porcelain=v1", "--untracked-files=all")
    (out / "git-status.txt").write_text(status if status is not None else "git status failed\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("runtime", "start"):
        commands.add_parser(name).add_argument("dir", type=Path)
    probe_parser = commands.add_parser("probe")
    probe_parser.add_argument("dir", type=Path)
    probe_parser.add_argument("name")
    finish_parser = commands.add_parser("finish")
    finish_parser.add_argument("dir", type=Path)
    finish_parser.add_argument("--os", required=True)
    finish_parser.add_argument("--arm", required=True)
    finish_parser.add_argument("--repeat", required=True, type=int)
    finish_parser.add_argument("--heartbeat", type=Path, help="the hang control's heartbeat file (control job only)")
    args = parser.parse_args(argv)
    args.dir.mkdir(parents=True, exist_ok=True)
    if args.command == "runtime":
        runtime(args.dir)
    elif args.command == "start":
        start(args.dir)
    elif args.command == "probe":
        if not args.name.replace("-", "").isalnum():
            parser.error("a probe name is letters, digits and hyphens")
        probe(args.dir, args.name)
    else:
        finish(args.dir, args.os, args.arm, args.repeat, _END_NS)
        if args.heartbeat is not None:
            heartbeat(args.dir, args.heartbeat, _END_NS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
