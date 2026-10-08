---
status: proposed
date: 2026-10-08
---

# Report frozen findings successfully and keep operational failures visible

The inactive-evidence report completes successfully when OSV finishes both
native formats with exit 0 or 1. Native findings remain in report.json,
JSON/SARIF, logs, code witnesses and the existing review/alert path. Scanner,
eligibility, installation, missing-output and malformed-report failures remain
failures. The required live osv-scanner workflow keeps its vulnerability gate.

This refinement follows OSV 2.6.0's native distinction: ErrVulnerabilitiesFound
returns 1; ErrNoPackagesFound returns 128; ErrAPIFailed returns 129.
GitHub uses the shell exit to determine step success. The report therefore
normalizes only the final findings exit 1 to 0 after recording both raw outcomes.
It adds no continue-on-error or advisory/package suppression.

## Measured problem

[Run 37821865072](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37821865072)
failed only its frozen scan step. Preflight, pinned scanner installation,
summary and artifact retention passed. Its report says findings, available,
errors=[], native JSON 1/SARIF 1 and nine advisories across three packages.
The frozen lock remains f1c707b8295e85bd396e49b990de92dc82bc0d58eca1e4e4bef31262d9898cd2;
the empty report config remains c0ea1976499ea0d41b10b169ed206f821437e5a418ba33957100c2bd500abf64.

The native artifact ZIP digest 07cbf2156d4a73254e9ea32d5a3a438fa80321dccb29a97a030b5ea393b71016
matches GitHub's digest. API PR head 7a3027f4e4ded104519dfdbc57308e3c05f5f95e
and report merge input 442b16d55be06c73d681648f97799af3d5de345b are bound
separately in the receipt. No operational scan failure was observed.

[The prior design](2026-10-07-frozen-evidence-osv-reporting.md) separated frozen
risk from required production scans and deliberately retained non-required
failure visibility. It did not promise a green report. The dated optimization
trigger on 2026-10-08 asks for a completed report to have a successful check
outcome while retaining all risk data; the historical record and input bytes
remain intact.

## Validation and declared change

The existing recording-double harness executes the actual checked-in scan shell.
Eight before/after cases cover clear results, finding-only outcomes, errors and
mixed-format errors. Finding-only scan exits change 1 to 0; errors 2/7 remain
nonzero. Every raw JSON/SARIF/log/code-witness digest is identical before/after.
The native source's 128/129 error cases also pass the expanded control.

254 targeted reporting, lock coverage, frozen-consumer tripwire and workflow
policy tests pass, with one existing skip. The added native-source cases pass
the changed method separately. kjanat/actionlint 1.17.0 passes this workflow.
These are local integration/synthetic controls, not a hosted after measurement.

Only this existing method changes contract (kind 3):
tests.test_frozen_evidence_reporting.FrozenReportWorkflowTests.test_native_findings_errors_and_both_logs_are_retained.
Its invocation-count/code/log assertions remain; its matrix grows from four to
ten cases. Running all 13 unchanged base reporting methods against the candidate
produces exactly its two declared old subtest failures, JSON 1/SARIF 0 and
JSON 0/SARIF 1, with no errors. No method is removed.

The summary's malformed/missing-data control still fails unknown with exit 2.
Operational scanner codes remain nonzero. The ordinary required workflow,
frozen inventory/config/digests, native report serialization, artifact retention
and trusted main-only issue/SARIF write guards retain their bytes/contracts.

## Inverse, limits and acceptance

The native inverse patch was applied to the two owned implementation files and
both hashes matched the base. Reapplying the forward patch restored both
candidate hashes. After a landing, use a reviewed inverse PR for this change,
re-register its evidence hashes, and land through the CC/5f path.

The [receipt](../../evidence/artifacts/github-ci-opt6-report-status-20261008.json)
separates native hosted before, local fixture after, tests and inverse.
The actual hosted after remains pending until an explicit workflow landing cue
and applicable run. A successful report does not say the archived packages are
safe. Native findings and their owner/deadline remain; per-advisory disposition
and delivery are separate acceptance duties.

A broad continue-on-error was rejected because it would hide scanner and
reporting failures. Updating/suppressing the frozen input was rejected because
it would rewrite captured evidence or remove risk. Report outcome normalization
uses the existing vendor scanner and workflow rather than a replacement.

## SOTA sources

- [google/osv-scanner 2.6.0](https://github.com/google/osv-scanner/tree/e840a6e8adb14b7777c78e26cfbf6e2abc1d1fc6),
  cmd/osv-scanner/main.go and cmd/osv-scanner/internal/cmd/run.go;
  the latter's pinned Git blob e57f6818d06afe80a1effe1e6d7d9b49e1cf3211
  defines native findings/error exit codes.
- [GitHub workflow shell semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsrun)
  and [job conditions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions):
  explicit exit handling and preserved always/trusted-event guards.
- [PR 845](https://github.com/seathatflowsinourveins/native-agent-stack/pull/845)
  and its dated frozen-report decision retain the preceding scope and historical
  acceptance. The native run and artifact above provide the measured baseline.
