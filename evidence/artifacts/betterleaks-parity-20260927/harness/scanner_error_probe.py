#!/usr/bin/env python3
"""The cross-family review's probe of the betterleaks trial's fixture step, repeated and extended (local
integration helper; not an upstream test). No scanner runs.

Part 1, as the review did: for each scanner outcome below, a child `python3 -m unittest -v` runs one
positive fixture test of TREE's tests/test_gitleaks_config.py
(GitleaksConfigContextRestrictionTests.test_a_non_allowlisted_path_hex_secrets_are_detected), with
subprocess.run replaced in memory for scanner calls only. A `gitleaks` that is never run comes first on
PATH, so the test class does not skip. The fixture step's own status handling, cut verbatim from TREE's
validate.yml (from its `ran=` line to the end of the step), then reads that unittest output and exit status
under GitHub's command for `shell: bash`: `bash --noprofile --norc -eo pipefail -c`.

Part 2, end to end: TREE's whole fixture step runs through TREE's own BetterleaksTrialJobTests.run_step
(GitHub's command for `shell: bash`) over TREE's real test module, copied with .gitleaks.toml and
.gitleaksignore into a checkout outside any repository, with a stand-in scanner process in place of the
verified binary. SIGKILL stands for a signal there, because a real SIGSEGV would start the host's crash
reporter.

Prints one JSON line per outcome: unittest's status line and exit status, and the step's exit status.
Nothing from a report or a failure message is printed. Usage: scanner_error_probe.py TREE"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
TEST = ("tests.test_gitleaks_config.GitleaksConfigContextRestrictionTests."
        "test_a_non_allowlisted_path_hex_secrets_are_detected")
# adoption/tools/gitleaks-guarded, lines 27-28: the launcher's busy-lock message, with exit status 75.
BUSY = "gitleaks: another scan holds the per-user lock; retry after it finishes\n"
OUTCOMES = [  # name, exit status, report text (None: no report file), stderr
    ("killed by SIGSEGV", -11, None, ""),
    ("exit 139", 139, None, ""),
    ("exit 1 without a report", 1, None, ""),
    ("exit 1 after writing its report (a partial scan)", 1, "null\n", ""),
    ("exit 0 without a report", 0, None, ""),
    ("exit 2 with the Go runtime's deadlock message", 2, None, "fatal error: all goroutines are asleep - deadlock!\n"),
    ("control: exit 0 with an empty report (a detection difference)", 0, "null\n", ""),
    ("control: the guarded launcher's busy lock", 75, None, BUSY),
]
CHILD = r'''
import json, os, subprocess, sys, unittest
from pathlib import Path
sys.path.insert(0, os.getcwd())
import tests.test_gitleaks_config as module
name, status, report, stderr = json.loads(os.environ["PROBE_OUTCOME"])
real_run = subprocess.run
def run(argv, *args, **kwargs):
    if isinstance(argv, (list, tuple)) and argv and argv[0] == module.GITLEAKS:
        argv = list(argv)
        if report is not None:
            Path(argv[argv.index("--report-path") + 1]).write_text(report)
        return subprocess.CompletedProcess(argv, status, "", stderr)
    return real_run(argv, *args, **kwargs)
subprocess.run = run
unittest.main(module=None, argv=["python3 -m unittest", "-v", sys.argv[1]])
'''

sys.path.insert(0, str(tree))
from tests.test_workflow_hardening import jobs, step_block  # noqa: E402  (TREE's own helpers)

job = jobs((tree / ".github/workflows/validate.yml").read_text(encoding="utf-8"))["secret-scan-betterleaks"]
block = step_block(job, "fixture tests with betterleaks")
lines = [line[10:] for line in block.split("\n        run: |\n", 1)[1].splitlines()]
start = next(index for index, line in enumerate(lines) if line.startswith("ran="))
handling = "\n".join(lines[start:]) + "\n"
print(json.dumps({"tree": tree.name, "status_handling_lines": len(lines) - start,
                  "status_handling_first": lines[start], "status_handling_last": lines[-1]}))

with tempfile.TemporaryDirectory() as scratch_name:
    scratch = Path(scratch_name)
    (scratch / "bin").mkdir()
    never_run = scratch / "bin" / "gitleaks"
    never_run.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    never_run.chmod(0o755)
    for name, status, report, stderr in OUTCOMES:
        env = dict(os.environ, PATH=f"{scratch / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}",
                   GITLEAKS_TESTS_REQUIRED="1", PYTHONDONTWRITEBYTECODE="1",
                   PROBE_OUTCOME=json.dumps([name, status, report, stderr]))
        child = subprocess.run([sys.executable, "-c", CHILD, TEST], cwd=tree, env=env, capture_output=True, text=True)
        log = scratch / "fixtures.log"
        log.write_text(child.stdout + child.stderr, encoding="utf-8")
        summary = scratch / "summary.md"
        summary.write_text("", encoding="utf-8")
        step = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c",
                               f"log={shlex.quote(str(log))}\nstatus={child.returncode}\n" + handling],
                              env=dict(env, GITHUB_STEP_SUMMARY=str(summary)), capture_output=True, text=True)
        status_lines = [line for line in log.read_text(encoding="utf-8").splitlines()
                        if re.match(r"^(OK|FAILED|NO TESTS RAN)", line)]
        print(json.dumps({"part": 1, "outcome": name, "scanner_exit_status": status,
                          "unittest_status_line": status_lines[-1] if status_lines else None,
                          "unittest_exit_status": child.returncode, "step_exit_status": step.returncode}))

# Part 2. The stand-in answers `version` as the step's check needs, then ends each scan as STUB_MODE says.
STUB = """#!/usr/bin/env bash
[ "$1" = version ] && echo 1.8.1 && exit 0
report=""
while [ "$#" -gt 0 ]; do
  [ "$1" = --report-path ] && report="$2"
  shift
done
case "$STUB_MODE" in
  detections-missing) echo null > "$report"; exit 0 ;;
  partial-scan) echo null > "$report"; exit 1 ;;
  scan-error) exit 1 ;;
  no-report) exit 0 ;;
  exit-139) exit 139 ;;
  killed) kill -KILL "$$" ;;
  deadlock) echo 'fatal error: all goroutines are asleep - deadlock!' >&2; exit 2 ;;
esac
exit 99
"""
from tests.test_workflow_hardening import BetterleaksTrialJobTests  # noqa: E402

helper = BetterleaksTrialJobTests("test_is_not_a_required_context_and_cannot_be_forced_green")
with tempfile.TemporaryDirectory() as checkout_name:
    checkout = Path(checkout_name).resolve()
    (checkout / "tests").mkdir()
    (checkout / "tests" / "__init__.py").write_text("", encoding="utf-8")
    for name in ("tests/test_gitleaks_config.py", ".gitleaks.toml", ".gitleaksignore"):
        (checkout / name).write_bytes((tree / name).read_bytes())
    for mode in ("detections-missing", "partial-scan", "scan-error", "no-report", "exit-139", "killed", "deadlock"):
        rc, _output, summary = helper.run_step(helper.FIXTURE_STEP, STUB,
                                               {"GITLEAKS_TESTS_REQUIRED": "1", "STUB_MODE": mode,
                                                "GIT_CEILING_DIRECTORIES": str(checkout.parent)}, cwd=checkout)
        found = re.search(r"(?m)^(Ran \d+ tests?) in [\d.]+s; (.+); unittest exit status (\d+)$", summary)
        print(json.dumps({"part": 2, "stub_mode": mode, "unittest_run": found and found.group(1),
                          "unittest_status_line": found and found.group(2),
                          "unittest_exit_status": found and int(found.group(3)), "step_exit_status": rc}))
    helper.doCleanups()
