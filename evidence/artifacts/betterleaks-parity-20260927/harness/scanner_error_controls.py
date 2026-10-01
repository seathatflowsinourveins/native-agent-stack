#!/usr/bin/env python3
"""Failing controls for the scanner-error repair (local integration helper). Each control puts one part of
the reviewed bug back into tests/test_gitleaks_config.py, runs each test that must catch it, puts the exact
bytes back (checked by SHA-256) and records each test's exit status and failing test ids. The last control
is the whole pre-repair file from BASE_REV. Every named test first runs green on the unchanged files. Prints
control names, exit statuses and test ids only. Run it alone: it edits a tracked file in the worktree.
Usage: scanner_error_controls.py WORKTREE BASE_REV"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

root, base_rev = Path(sys.argv[1]), sys.argv[2]
MODULE = root / "tests/test_gitleaks_config.py"
UNIT = "tests.test_gitleaks_config.ScannerErrorTests."
A = UNIT + "test_a_nonzero_exit_status_is_a_scanner_error_with_or_without_a_report"
B = UNIT + "test_b_exit_0_needs_a_written_report"
C = UNIT + "test_c_only_the_guarded_launchers_busy_lock_skips"
D = UNIT + "test_d_a_detection_test_errors_when_its_scan_does_not_complete"
E = UNIT + "test_e_every_scan_in_this_module_goes_through_scan_findings"
STEP = ("tests.test_workflow_hardening.BetterleaksTrialJobTests."
        "test_fixture_step_fails_when_a_scan_does_not_complete_in_the_real_fixture_module")
MISSING = ('    if not report.strip():\n'
           '        raise _ScannerError(f"gitleaks {scan_args[0]} exited 0 without writing its report: {stderr_tail}")\n')
CONTROLS = [
    ("_ScannerError subclasses AssertionError", [A, D, STEP],
     "class _ScannerError(Exception):", "class _ScannerError(AssertionError):"),
    ("exit status 1 accepted again", [A, D, STEP],
     "    if proc.returncode != 0:\n", "    if proc.returncode not in (0, 1):\n"),
    ("a missing or empty report read as no findings", [B, D, STEP],
     MISSING, "    if not report.strip():\n        return []\n"),
    ("any stderr naming a lock read as the busy lock", [C, STEP],
     "    if proc.returncode == LOCK_BUSY_STATUS and LOCK_BUSY_MESSAGE in proc.stderr:\n",
     '    if "lock" in proc.stderr.lower():\n'),
    ("a direct scanner call beside _scan_findings", [E],
     '\n\nif __name__ == "__main__":\n',
     '\n\ndef _direct_scan():\n    return subprocess.run([GITLEAKS, "dir", "."], capture_output=True)\n'
     '\n\nif __name__ == "__main__":\n'),
    ("the whole pre-repair file", [STEP], None, None),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(test):
    proc = subprocess.run([sys.executable, "-B", "-m", "unittest", test], cwd=root, capture_output=True, text=True)
    name = test.rsplit(".", 2)
    # Only this test's own headers: the fixture step test quotes the real module's output, indented.
    failed = re.findall(rf"(?m)^(?:FAIL|ERROR): ({re.escape(name[-1])}) \({re.escape(test)}", proc.stderr)
    last = (proc.stderr.strip().splitlines() or [""])[-1]
    return proc.returncode, sorted(set(failed)), last


original = MODULE.read_bytes()
base = subprocess.run(["git", "-C", str(root), "show", f"{base_rev}:tests/test_gitleaks_config.py"],
                      capture_output=True, check=True).stdout
named = list(dict.fromkeys(test for _, tests, _, _ in CONTROLS for test in tests))
green = {}
for test in named:
    rc, failed, last = run(test)
    green[test.rsplit(".", 1)[-1]] = rc == 0 and not failed and last == "OK"
print(json.dumps({"green_before_each_named_test": green}))
results = []
for name, tests, old, new in CONTROLS:
    text = original.decode("utf-8")
    if old is None:
        changed = base
    else:
        assert text.count(old) == 1, name
        changed = text.replace(old, new).encode("utf-8")
    MODULE.write_bytes(changed)
    try:
        outcome = []
        for test in tests:
            rc, failed, last = run(test)
            outcome.append({"test": test.rsplit(".", 1)[-1], "rc": rc, "failed": failed, "last_line": last})
    finally:
        MODULE.write_bytes(original)
    results.append({"control": name, "tests": outcome,
                    "each_test_failed": all(o["rc"] != 0 and o["failed"] == [o["test"]] for o in outcome)})
    print(json.dumps(results[-1]))
print(json.dumps({"controls": len(results), "all_named_tests_green_before": all(green.values()),
                  "every_control_failed_each_of_its_tests": all(r["each_test_failed"] for r in results),
                  "module_restored_byte_identical": sha(MODULE.read_bytes()) == sha(original)}))
