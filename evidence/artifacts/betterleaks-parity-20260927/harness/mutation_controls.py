#!/usr/bin/env python3
"""Failing controls for tests/test_workflow_hardening.py BetterleaksTrialJobTests (local integration
helper). Each control makes one change in the worktree, runs the one test that must catch it, puts the
exact bytes back (checked by SHA-256) and records that test's exit status. Prints control names, exit
statuses and failing test ids only. Run it alone: a control that creates a file or edits a tracked one
would disturb a concurrent scan of the worktree.

Since the coordinator repair (2026-09-28): every named test first runs green on the unchanged files (rc 0,
one test, plain OK), so a control cannot pass on a missing or skipped test; and a control counts when its
test is the only failing test id, compared as a set because subtests repeat that id."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
WORKFLOW = root / ".github/workflows/validate.yml"
TRACKED = root / "docs/lanes.md"  # any tracked text file; the marker line is appended, then removed
CLASS = "tests.test_workflow_hardening.BetterleaksTrialJobTests"
MARKER = "betterleaks" + ":allow"  # assembled, so this file does not carry the marker itself
EXIT = "test_findings_exit_0_through_the_scanners_own_option"
SCAN = "test_scan_steps_fail_only_on_a_scan_error_and_count_findings_by_rule"
FIXTURE = "test_fixture_step_reports_assertion_failures_and_fails_on_anything_else"
HISTORY_TAIL = r"""--log-opts="HEAD" \
            --redact --no-banner --report-format json --report-path "$report" --exit-code 0 || status=$?"""
DIR_TAIL = r""".gitleaksignore \
            --redact --no-banner --report-format json --report-path "$report" --exit-code 0 || status=$?"""
COUNTS = r"""jq -r '(. // []) | "Findings: \(length)", (group_by(.RuleID)[] | "- \(.[0].RuleID): \(length)")' """ + '"$report"'
HISTORY_SUMMARY = ('            echo "### betterleaks history scan (findings do not fail this job; secret-scan is the gate)"\n'
                   '            if [ -s "$report" ]; then\n              ' + COUNTS)
DIR_SUMMARY = ('            echo "### betterleaks working-tree scan (findings do not fail this job; secret-scan is the gate)"\n'
               '            if [ -s "$report" ]; then\n              ' + COUNTS)
SUMMARY_LINE = r"""            echo "${ran:-No unittest run line}; ${result:-no unittest status line}; unittest exit status $status"
"""

CONTROLS = [
    ("--redact removed from the dir scan", "test_later_steps_need_the_verified_install_and_both_scans_redact",
     r""".gitleaksignore \
            --redact --no-banner""", r""".gitleaksignore \
            --no-banner"""),
    ("--redact=0 on the dir scan", "test_later_steps_need_the_verified_install_and_both_scans_redact",
     r""".gitleaksignore \
            --redact --no-banner""", r""".gitleaksignore \
            --redact=0 --no-banner"""),
    ("--max-archive-depth 0 removed from the history scan", "test_later_steps_need_the_verified_install_and_both_scans_redact",
     '--max-archive-depth 0 --gitleaks-ignore-path .gitleaksignore --log-opts="HEAD"',
     '--gitleaks-ignore-path .gitleaksignore --log-opts="HEAD"'),
    ("--gitleaks-ignore-path removed from the dir scan", "test_later_steps_need_the_verified_install_and_both_scans_redact",
     r"""--max-archive-depth 0 --gitleaks-ignore-path .gitleaksignore \
            --redact""", r"""--max-archive-depth 0 \
            --redact"""),
    ("job given name: secret-scan", "test_is_not_a_required_context_and_cannot_be_forced_green",
     "    runs-on: ubuntu-24.04\n    # On the recording workstation",
     "    name: secret-scan\n    runs-on: ubuntu-24.04\n    # On the recording workstation"),
    ("an upload-artifact step added", "test_read_only_hardened_and_uploads_nothing",
     '          exit "$status"\n\n  sota-sources:',
     '          exit "$status"\n      - name: Upload report\n'
     '        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1\n'
     '        with:\n          name: betterleaks\n          path: ${{ runner.temp }}/betterleaks/tree.json\n'
     '\n  sota-sources:'),
    ("the job's bash default removed", "test_runs_bash_with_pipefail",
     "        shell: bash\n    steps:\n", "    steps:\n"),
    ("a step overriding the shell", "test_runs_bash_with_pipefail",
     "      - name: Scan working tree for secrets with betterleaks (findings do not fail this job)\n",
     "      - name: Scan working tree for secrets with betterleaks (findings do not fail this job)\n        shell: sh\n"),
    ("tar -xzf moved before cosign verify-blob", "test_binaries_run_only_after_verification",
     '          "$RUNNER_TEMP/cosign/cosign" verify-blob',
     '          tar -xzf "$archive" betterleaks\n          "$RUNNER_TEMP/cosign/cosign" verify-blob'),
    ("the pinned BETTERLEAKS_SHA256 check moved after extraction", "test_binaries_run_only_after_verification",
     r"""          printf '%s  %s\n' "$BETTERLEAKS_SHA256" "$archive" | sha256sum --check
          tar -xzf "$archive" betterleaks
""", r"""          tar -xzf "$archive" betterleaks
          printf '%s  %s\n' "$BETTERLEAKS_SHA256" "$archive" | sha256sum --check
"""),
    ("--certificate-github-workflow-sha removed", "test_binaries_run_only_after_verification",
     r"""            --certificate-github-workflow-sha "$SIGNER_COMMIT" \
""", ""),
    ("the cosign digest check moved after cosign's first run", "test_binaries_run_only_after_verification",
     r"""          printf '%s  %s\n' "$COSIGN_SHA256" "$RUNNER_TEMP/cosign/cosign" | sha256sum --check
          chmod +x "$RUNNER_TEMP/cosign/cosign"
          "$RUNNER_TEMP/cosign/cosign" version
""", r"""          chmod +x "$RUNNER_TEMP/cosign/cosign"
          "$RUNNER_TEMP/cosign/cosign" version
          printf '%s  %s\n' "$COSIGN_SHA256" "$RUNNER_TEMP/cosign/cosign" | sha256sum --check
"""),
    ("the history-ancestry class added to the fixture run", "test_fixture_tests_leave_out_the_unredacted_history_class",
     '"$m.GitleaksIgnoreFingerprintTests"', '"$m.GitleaksIgnoreFingerprintTests" "$m.GitleaksBranchAncestryHistoryTests"'),
    ("the whole module added to the fixture run", "test_fixture_tests_leave_out_the_unredacted_history_class",
     '"$m.GitleaksIgnoreFingerprintTests"', '"$m.GitleaksIgnoreFingerprintTests" "$m"'),
    (".betterleaksignore created at the root", "test_no_suppression_channel_that_only_betterleaks_reads",
     ("create", ".betterleaksignore"), None),
    (".betterleaks.toml created at the root", "test_no_suppression_channel_that_only_betterleaks_reads",
     ("create", ".betterleaks.toml"), None),
    ("the inline betterleaks allow comment appended to a tracked file", "test_no_suppression_channel_that_only_betterleaks_reads",
     ("append", TRACKED), None),
    # Coordinator repair (2026-09-28): the report-only mechanism.
    ("--exit-code 0 removed from the history scan", EXIT, HISTORY_TAIL, HISTORY_TAIL.replace(" --exit-code 0", "")),
    ("--exit-code 1 on the dir scan", EXIT, DIR_TAIL, DIR_TAIL.replace("--exit-code 0", "--exit-code 1")),
    ("|| true in place of || status=$? on the dir scan", EXIT, DIR_TAIL, DIR_TAIL.replace("|| status=$?", "|| true")),
    ("status reset to 0 after the dir scan", EXIT, "          fi\n          {\n" + DIR_SUMMARY,
     "          fi\n          status=0\n          {\n" + DIR_SUMMARY),
    ("the history scan step exits 0", EXIT, '          exit "$status"\n      - name: Scan working tree',
     '          exit 0\n      - name: Scan working tree'),
    ("an early exit 0 in the dir scan step", EXIT,
     """@tsv' "$report" | sort\n          fi\n""", """@tsv' "$report" | sort\n            exit 0\n          fi\n"""),
    ("--exit-code 0 removed from the history scan", SCAN, HISTORY_TAIL, HISTORY_TAIL.replace(" --exit-code 0", "")),
    ("--exit-code 1 on the dir scan", SCAN, DIR_TAIL, DIR_TAIL.replace("--exit-code 0", "--exit-code 1")),
    ("|| true in place of || status=$? on the dir scan", SCAN, DIR_TAIL, DIR_TAIL.replace("|| status=$?", "|| true")),
    ("the history scan step exits 0", SCAN, '          exit "$status"\n      - name: Scan working tree',
     '          exit 0\n      - name: Scan working tree'),
    ("the history summary also prints each finding's Secret", SCAN, HISTORY_SUMMARY,
     HISTORY_SUMMARY.replace(""")' "$report\"""", """), (.[] | .Secret)' "$report\"""")),
    ("the dir summary counts by file", SCAN, DIR_SUMMARY,
     DIR_SUMMARY.replace("group_by(.RuleID)[] | \"- \\(.[0].RuleID)", "group_by(.File)[] | \"- \\(.[0].File)")),
    ("no step summary from the history scan", SCAN,
     "          {\n" + HISTORY_SUMMARY + '\n            fi\n            echo "betterleaks exit status: $status"\n'
     '          } >> "$GITHUB_STEP_SUMMARY"\n          exit "$status"\n      - name: Scan working tree',
     '          exit "$status"\n      - name: Scan working tree'),
    ("the dir summary reads a null report without the [] default", SCAN, DIR_SUMMARY,
     DIR_SUMMARY.replace("jq -r '(. // []) | \"Findings:", "jq -r '. | \"Findings:")),
    ("the history log lists each finding's Secret instead of its line", SCAN,
     """[.RuleID, .File, (.StartLine | tostring)] | @tsv' "$report" | sort | uniq -c""",
     """[.RuleID, .File, .Secret] | @tsv' "$report" | sort | uniq -c"""),
    ("the dir summary leaves out the exit status", SCAN,
     DIR_SUMMARY + '\n            fi\n            echo "betterleaks exit status: $status"\n', DIR_SUMMARY + "\n            fi\n"),
    ("the fixture step exits 0 whatever the tests did", FIXTURE, '          exit "$status"\n      - name: Scan git history',
     '          exit 0\n      - name: Scan git history'),
    ("the report-only pattern accepts any FAILED line", FIXTURE,
     r"""failures_only='^FAILED \(failures=[0-9]+(, skipped=[0-9]+)?\)$'""", "failures_only='^FAILED'"),
    ("the report-only branch removed", FIXTURE,
     '          if [ "$status" -eq 1 ] && [[ "$result" =~ $failures_only ]]; then\n            status=0\n          fi\n', ""),
    ("any nonzero unittest exit status accepted", FIXTURE, '[ "$status" -eq 1 ]', '[ "$status" -ne 0 ]'),
    ("the betterleaks version check removed", FIXTURE, '          test "$(gitleaks version)" = "1.8.1"\n', ""),
    ("the version check moved after the step summary", FIXTURE,
     '          test "$(gitleaks version)" = "1.8.1"\n', ""),  # the second half of this move is applied below
    ("the unittest log copied into the step summary", FIXTURE, SUMMARY_LINE, SUMMARY_LINE + '            cat "$log"\n'),
    ("the status line left out of the step summary", FIXTURE, SUMMARY_LINE,
     SUMMARY_LINE.replace("; ${result:-no unittest status line}", "")),
    ("the run line left out of the step summary", FIXTURE, SUMMARY_LINE,
     SUMMARY_LINE.replace("${ran:-No unittest run line}; ", "")),
]
# A move is two replacements; the second puts the version check after the fixture step's summary block.
MOVES = {"the version check moved after the step summary":
         (SUMMARY_LINE + '          } >> "$GITHUB_STEP_SUMMARY"\n',
          SUMMARY_LINE + '          } >> "$GITHUB_STEP_SUMMARY"\n          test "$(gitleaks version)" = "1.8.1"\n')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(test):
    proc = subprocess.run([sys.executable, "-m", "unittest", f"{CLASS}.{test}"], cwd=root, capture_output=True, text=True)
    # Only this class's own headers: a failure message may quote another unittest run's output.
    failed = re.findall(rf"(?m)^(?:FAIL|ERROR): (\w+) \({re.escape(CLASS)}[.)]", proc.stderr)
    return proc.returncode, failed, proc.stderr


before = {p: sha(p) for p in (WORKFLOW, TRACKED)}
original = WORKFLOW.read_bytes()
green_before = {}
for test in dict.fromkeys(c[1] for c in CONTROLS):
    rc, failed, stderr = run(test)
    lines = stderr.strip().splitlines()
    green_before[test] = rc == 0 and not failed and "Ran 1 test in" in stderr and lines[-1] == "OK"
print(json.dumps({"green_before_each_named_test": green_before}))
results = []
for name, test, old, new in CONTROLS:
    if isinstance(old, tuple) and old[0] == "create":
        target = root / old[1]
        assert not target.exists(), target
        target.write_text("# control file\n")
        try:
            rc, failed, _ = run(test)
        finally:
            target.unlink()
    elif isinstance(old, tuple) and old[0] == "append":
        saved = old[1].read_bytes()
        old[1].write_bytes(saved + f"\n<!-- {MARKER} -->\n".encode())
        try:
            rc, failed, _ = run(test)
        finally:
            old[1].write_bytes(saved)
    else:
        text = original.decode("utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        text = text.replace(old, new)
        if name in MOVES:
            after_old, after_new = MOVES[name]
            assert text.count(after_old) == 1, (name, text.count(after_old))
            text = text.replace(after_old, after_new)
        WORKFLOW.write_text(text, encoding="utf-8")
        try:
            rc, failed, _ = run(test)
        finally:
            WORKFLOW.write_bytes(original)
    results.append({"control": name, "test": test, "rc": rc, "failed": sorted(set(failed))})
    print(json.dumps(results[-1]))
restored = all(sha(p) == h for p, h in before.items()) and not (root / ".betterleaksignore").exists() \
    and not (root / ".betterleaks.toml").exists()
green = subprocess.run([sys.executable, "-m", "unittest", CLASS], cwd=root, capture_output=True, text=True)
print(json.dumps({"controls": len(results), "all_named_tests_green_before": all(green_before.values()),
                  "all_failed_their_test": all(r["rc"] == 1 and r["failed"] == [r["test"]] for r in results),
                  "files_restored_byte_identical": restored, "green_rc": green.returncode,
                  "green_summary": [l for l in green.stderr.splitlines() if re.match(r"^(Ran |OK|FAILED)", l)]}))
