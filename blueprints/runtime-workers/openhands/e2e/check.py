"""Independent frozen fixture oracle. Run in the pinned image with no network.

The local test runner follows CPython unittest's TestLoader/TextTestRunner public
interfaces. This is a synthetic task check, never an upstream acceptance suite.
It reexecutes the frozen tests and checks bytes against the pristine fixture.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recipe import inventory, read_json  # noqa: E402


HERE = Path(__file__).resolve().parent


def run_tests(workspace):
    """Isolated child imports candidate code, bounded by time and container scope."""
    command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--test-child", str(workspace)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    lines = completed.stdout.splitlines()
    try:
        report = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        report = {"tests_run": 0, "failures": None, "errors": None, "skipped": None}
    report["exit_code"] = completed.returncode
    report["stdout"] = completed.stdout
    report["stderr"] = completed.stderr
    return report


def test_child(workspace):
    # -I ignores environment/site/user paths; insert only the owned fixture.
    sys.path.insert(0, str(workspace))
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(workspace / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    print(json.dumps({
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses), "output": stream.getvalue(),
    }))
    return 0 if result.wasSuccessful() else 1


def test_first(events, pristine, command):
    """Require an actual failing terminal observation while bytes were pristine."""
    pending = {}
    for event in events:
        if event.get("workspace") != pristine:
            return False
        if event.get("kind") == "ActionEvent":
            pending[event.get("tool_call_id")] = event
        elif event.get("kind") == "ObservationEvent":
            action = pending.get(event.get("tool_call_id"), {})
            obs = event.get("observation", {})
            if (
                action.get("tool_name") == "terminal"
                and action.get("action", {}).get("command", "").strip() == command
                and obs.get("exit_code") == 1
                and "FAILED (failures=1)" in json.dumps(obs)
                and "test_ranges_follow_the_spec" in json.dumps(obs)
            ):
                return True
    return False


def check(result):
    failures = []
    required = [result / "workspace", result / "baseline.json", result / "worker/events.jsonl"]
    if not all(path.exists() for path in required):
        return {"passed": False, "failures": ["missing_result"]}
    frozen = read_json(HERE / "frozen.json")
    pristine = inventory(HERE / "fixture-repo")
    expected = {**frozen["files"], "tests/": "directory"}
    if pristine != expected:
        failures.append("frozen_fixture_changed")
    current = inventory(result / "workspace")
    changed = sorted(name for name in set(pristine) | set(current) if pristine.get(name) != current.get(name))
    if not changed or not set(changed) <= set(frozen["allowed_files"]):
        failures.append("diff_outside_allowed_files_or_empty")
    if any(value in ("symlink", "special") for value in current.values()):
        failures.append("nonregular_result")
    baseline = read_json(result / "baseline.json")
    if not (baseline.get("exit_code") == 1 and baseline.get("tests_run") == 1
            and baseline.get("failures") == 1 and baseline.get("errors") == 0 and baseline.get("skipped") == 0):
        failures.append("baseline_not_one_failing_test")
    events = [json.loads(line) for line in (result / "worker/events.jsonl").read_text().splitlines() if line]
    if not test_first(events, pristine, frozen["test_command"]):
        failures.append("no_native_test_failure_before_edit")
    # Never execute a scope-violating submission, even inside the checker container.
    report = None
    if not failures:
        before = inventory(result / "workspace")
        report = run_tests(result / "workspace")
        if before != inventory(result / "workspace"):
            failures.append("tests_mutated_workspace")
        if not (report.get("exit_code") == 0 and report.get("tests_run") == frozen["expected_test_count"]
                and all(report.get(key) == 0 for key in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes"))):
            failures.append("tests_not_passing_unskipped")
    return {"passed": not failures, "failures": failures, "changed_files": changed, "tests": report}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--test-child", type=Path)
    args = parser.parse_args()
    if args.test_child:
        return test_child(args.test_child)
    try:
        if args.baseline:
            report = run_tests(args.baseline)
            print(json.dumps(report))
            return report["exit_code"]
        if args.result is None:
            parser.error("--result is required")
        report = check(args.result)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        report = {"passed": False, "failures": ["invalid_or_incomplete_result"]}
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
