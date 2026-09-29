# Round 2 verification, 2026-09-27

This is local transport and structural evidence. No package was installed,
service or container started, model called, gateway database read, upstream
grader executed, or upstream test suite run. Tests use synthetic predictions,
official-report-shaped controls, mocked installation and native Git ignore
queries in temporary scratch checkouts. Nothing was staged, committed or pushed.

The source and integration choices are in [research.md](../research.md) and
[README.md](../README.md). Verdict ownership is OpenHands/benchmarks
405bae7140d7e961a75f4910a0b2e7069731db96, its SDK submodule
43376f1868ffd702746080714a59c16d3f69ec12, and official SWE-bench 4.1.0.
Our check.py only validates predictions and relays the official report.
The standalone worker remains SDK 1.49.6 at
fcc102a697874d54a357e36004e02c95040dbdc0. These environments stay separate.

All test runs used this command from the checkout root, with TMPDIR set to
the task's approved external research scratch directory:

~~~sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$RESEARCH_SCRATCH" python3 -m unittest discover -s tests -p test_runtime_worker_openhands.py -v
~~~

After the updated AGENTS.md arrived, the final two runs prefixed python3 with
rtk. The retained logs state the exact command form for each run, replacing
only private filesystem prefixes with placeholders. These are incremental
test-first snapshots; removing the old local correctness oracle changed the
suite's test count. They are not repeated evaluations of one frozen model task.

| Stage | Exit | Actual returned result |
| --- | --- | --- |
| Ownership, route and structured-output constraints, fail first | 1 | Ran 21 tests; FAILED (failures=8) |
| Official-report adapter, fail first | 1 | Ran 19 tests; FAILED (failures=5, errors=2) |
| Shared installer, task and Docker transport, fail first | 1 | Ran 22 tests; FAILED (errors=3) |
| Independent report receipt, fail first | 1 | Ran 24 tests; FAILED (failures=2) |
| Exact native LLM type and scoped headers, fail first | 1 | Ran 25 tests; FAILED (errors=1) |
| Project skill bookkeeping and conflicts, fail first | 1 | Ran 27 tests; FAILED (failures=3) |
| Final local suite | 0 | Ran 27 tests in 0.451s; OK |

[Fail-first output](round2-fail-first.txt) retains each returned failure.
The first routing output contains the tool's own 17-token truncation marker;
it is explicitly incomplete and was not reconstructed. Later retained failures
are complete returned output. [Final suite output](round2-unit-pass.txt) retains
the passing result.

Known-pass and known-fail report controls exercise schema-2 resolved, unresolved,
empty-patch, error and incomplete outcomes. Malformed, missing, conflicting,
duplicate and wrong-scope transport cannot supply a passing verdict. An empty
patch remains valid input for the real upstream grader to reject. The receipt
re-reads the official report even if a wrapper claims success. Skill names at
startup are distinct from successful native invoke_skill observations.

Shell syntax was checked separately for install.sh, install-container.sh,
install-grader.sh and run-e2e.sh with rtk bash -n; each returned exit 0 with
empty output. Each script was a separate bash invocation, so all four were
parsed. Remaining structural checks and returned results are retained in
[round2-static-checks.txt](round2-static-checks.txt).

Publication command:

~~~sh
PYTHONDONTWRITEBYTECODE=1 rtk python3 scripts/validate.py
~~~

The intermediate publication result is retained in
[round2-publication-first.txt](round2-publication-first.txt); its prose-path
false positive was corrected in research.md. The final result is retained in
[round2-publication.txt](round2-publication.txt): exit 1 with 22 hash/byte-count
mismatches only. The coordinator must refresh the 11 changed round-1 file
registrations in manifests/evidence.json and register the round-2 additions.
That shared manifest is outside this builder's
file ownership; this recipe does not change or bypass the validator.

Remaining host acceptance: merge the shared skills options/manifest and verify
its output contract; freeze an original SWE-bench instance/revision; install the
two pinned environments through their documented paths; qualify the selected
task's dependencies; run official gold/empty-patch controls before the worker
patch; observe MCP startup, skill listing and both native skill activations;
observe actual gateway headers, tool calling and max effort; capture grader
image digests; verify owned-container cleanup. Grading has not run and therefore
has no pass, quality, A/B, token-savings or crash-recovery claim.
