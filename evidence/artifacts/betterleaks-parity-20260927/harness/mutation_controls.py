#!/usr/bin/env python3
"""Failing controls for tests/test_workflow_hardening.py BetterleaksTrialJobTests (local integration
helper). Each control makes one change in the worktree, runs the one test that must catch it, puts the
exact bytes back (checked by SHA-256) and records that test's exit status. Prints control names, exit
statuses and failing test ids only. Run it alone: a control that creates a file or edits a tracked one
would disturb a concurrent scan of the worktree."""
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
     "      - name: Scan working tree for secrets with betterleaks\n",
     "      - name: Scan working tree for secrets with betterleaks\n        shell: sh\n"),
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
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(test):
    proc = subprocess.run([sys.executable, "-m", "unittest", f"{CLASS}.{test}"], cwd=root, capture_output=True, text=True)
    failed = re.findall(r"(?m)^(?:FAIL|ERROR): (\w+) ", proc.stderr)
    return proc.returncode, failed


before = {p: sha(p) for p in (WORKFLOW, TRACKED)}
original = WORKFLOW.read_bytes()
results = []
for name, test, old, new in CONTROLS:
    if isinstance(old, tuple) and old[0] == "create":
        target = root / old[1]
        assert not target.exists(), target
        target.write_text("# control file\n")
        try:
            rc, failed = run(test)
        finally:
            target.unlink()
    elif isinstance(old, tuple) and old[0] == "append":
        saved = old[1].read_bytes()
        old[1].write_bytes(saved + f"\n<!-- {MARKER} -->\n".encode())
        try:
            rc, failed = run(test)
        finally:
            old[1].write_bytes(saved)
    else:
        text = original.decode("utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        WORKFLOW.write_text(text.replace(old, new), encoding="utf-8")
        try:
            rc, failed = run(test)
        finally:
            WORKFLOW.write_bytes(original)
    results.append({"control": name, "test": test, "rc": rc, "failed": failed})
    print(json.dumps(results[-1]))
restored = all(sha(p) == h for p, h in before.items()) and not (root / ".betterleaksignore").exists() \
    and not (root / ".betterleaks.toml").exists()
green = subprocess.run([sys.executable, "-m", "unittest", CLASS], cwd=root, capture_output=True, text=True)
print(json.dumps({"controls": len(results), "all_failed_their_test": all(r["rc"] == 1 and r["failed"] == [r["test"]]
                                                                       for r in results),
                  "files_restored_byte_identical": restored, "green_rc": green.returncode,
                  "green_summary": [l for l in green.stderr.splitlines() if re.match(r"^(Ran |OK|FAILED)", l)]}))
