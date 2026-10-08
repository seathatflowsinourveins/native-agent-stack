---
status: accepted
date: 2026-10-07
decision-makers: command center
---

# Report frozen dependency evidence separately from required production scans

The command center accepted option C in item 234931Z on 2026-10-07. This record
serves foundation landings before north-star research and independently qualified
paper operation. Implementation and its native hosted acceptance remain distinct
from the policy decision.

## Superseded scope

Supersede only the frozen group's worst-exit-status gating in
[`2026-09-22-github-automation-closure.md`](2026-09-22-github-automation-closure.md),
`native-agent-stack@28327acc67e85c480fbf3f9410c65f3d76b5cca4:docs/decisions/2026-09-22-github-automation-closure.md:343`.
The original decided text, relock results, historical scans and captured input
bytes remain unchanged. Live dependency vulnerability failures still block the
required `osv-scanner` context.

The 2026-10-07 incident lasted from approximately 21:28Z until #837's native merge at
22:35:48Z, about 68 minutes. Its retained receipt,
`evidence/receipts/osv-frozen-macos-next-1638-20261007.json`, records ordinary 0,
frozen 1: six new advisory identities against captured `next` 16.3.5, while the
live application lock already pins 16.3.8. This is historical evidence, not a
new execution or a statement that the vulnerable captured package became safe.

## Current behavior

The existing inventory remains exhaustive and disjoint. Entries without a
dedicated config are scanned under the ordinary production config in the
required workflow. Hash-bound, inactive captured inputs are scanned by the
separate `frozen-evidence-risk.yml` workflow with an explicit empty report
config, without advisory or package exceptions. That workflow's risk check is
non-required; native findings and scanner/data errors stay visible, and its
JSON/SARIF/logs are retained even on failure. An absent report is unknown, not
zero findings. Keeping it separate prevents its overall failure from changing
the required workflow's conclusion.

Required coverage preflight retains frozen path/digest/evidence/inactive-policy
checks. The current entry is
`evidence/artifacts/macos-application-20260924/variant/pnpm-lock.yaml`, SHA-256
`f1c707b8295e85bd396e49b990de92dc82bc0d58eca1e4e4bef31262d9898cd2`.
`FROZEN_LOCKS` now binds it to `.github/osv-scanner-frozen-report.toml`, its
historical receipt, owner and disposition review deadline. A supported consumer,
changed input or lapsed inactive disposition must enter required vulnerability
coverage before installation, build, execution or replay. Requalification does
not retain an inactive exemption.

No supported consuming route was found in the retained review. That does not
prove universal unreachability: the artifact does not retain the whole source
and the direct-reference tripwire has stated limits. Historical execution does
not authorize reusing it as a current runtime.

## Former exception configuration

`.github/osv-scanner-frozen-macos.toml` is retained byte-identical as a retired
historical configuration (SHA-256
`a00d1e2df72d7aca121ae39380e9c0f761a5d3d32d0392fa598502bdae2a89c6`).
Its nine dated entries, including #837's six, are superseded for current scan
execution. Maintained workflows and inventory select the new empty report
config; none invokes this retired config. Earlier receipts continue to describe
their actual exception bytes and results.

Tests retain the artifact and historical-config digests. Current `FROZEN_LOCKS`
advisory identities are historical controls for detecting accidental ordinary
suppression, not the list of findings allowed in the fresh report. New advisory
identities remain visible. Existing ordinary ignore policy and production input
bindings are unchanged.

## Finding review and delivery

Operational owner: `github-ci-finalize`. Each actual reporting run computes its
finding/error review due time from its native run clock, within 24 hours, and
retains it beside the owner, input hash and native artifacts. A finding must
reach the assigned receiver, with a durable review/disposition before that due
time; a job summary by itself is not claimed as delivery.

In item 001955Z on 2026-10-08, the command center assigned one native tracking
issue, following `saturation-tracking.yml:128-185`, linking the existing
`osv-scanner-frozen-macos` code-scanning alerts with owner and due date.
The GitHub assignee is `seathatflowsinourveins`; the reviewer is the command
center. Its review is a ledger row naming each advisory's disposition within
24 hours of the report attempt. Findings are stored once as SARIF; the issue
links alerts and does not copy finding or log text. It carries only public
metadata and links.

The advisory review deadline is an operational command-center obligation,
recorded in its ledger. Hosted eligibility checks do not read that private
ledger or claim to automate per-advisory disposition; they enforce the separate
artifact identity and inactive-disposition review bound below.

Only trusted main, schedule and dispatch runs write the issue. The automatic
workflow token has `issues: write` on that delivery job alone; PR scans remain
read-only and have no issue delivery job. Missing reports stay unknown and
cannot mint a completed review. Native delivery and read-back remain pending
until the workflow is hosted. A monitored native notification channel with a
named receiver was the unselected alternative.

Trusted delivery also requires `refs/heads/main`. A manual dispatch can select
another branch, so its event name alone does not authorize a write. Other-ref
dispatches retain read-only scan artifacts and do not publish an issue or SARIF.

Disposition review uses the existing 2026-12-24 bound. It is a policy review
deadline, distinct from a scanner exception expiry; required eligibility checks
reject lapse until the disposition is renewed or the input returns to required
coverage. The reporting job itself does not fabricate a safe result at expiry.

## Alternatives and overturn

Per-advisory ignores were rejected as the default for immutable inactive inputs:
new non-aliased findings repeatedly block unrelated production fixes and are
filtered out of result JSON. Exact-version `PackageOverrides` with bounded
`effectiveUntil` is supported by OSV 2.6.0, but also removes future findings on the
matching tuple; its version field selects a version rather than replacing it.
It would need a second unsuppressed report anyway. Whole-package ignore also
removes license reporting. The selected split keeps current risk visible.

Overturn if any frozen input is installed, built or executed again; a supported
consumer or changed digest appears; findings/errors are unavailable or are not
reviewed by their due date; or downstream automation still couples archival
failure to production publishing. Such an input must re-enter required coverage;
its historical bytes/results are not rewritten. The native acceptance records
must show live vulnerability/error failure remains blocking, frozen findings
are visible without exceptions, and actual workflow consumers respect the split.

## Declared contract changes

The accepted policy requires changing the former two-required-scan contracts.
These are intentional kind 3 changes, declared for exact-head review; they are
not fixes made merely to turn a red test green. No existing test method is
removed. Historical method names are retained where useful for compatibility.

In `tests.test_osv_lockfile_coverage`, the changed methods are:

| Method | New contract |
| --- | --- |
| `FrozenScanTests.test_the_ordinary_config_has_no_exception_for_a_frozen_advisory` | Reviewed historical identities still cannot be suppressed in ordinary coverage. |
| `FrozenScanTests.test_each_frozen_config_holds_exactly_the_advisories_of_its_locks` | Active frozen report config is exactly empty; no advisory or package suppression. |
| `FrozenScanTests.test_each_frozen_lock_matches_its_reviewed_digest_and_names_evidence` | Same artifact digest and evidence are preserved with the new config binding. |
| `FrozenScanTests.test_the_workflow_scans_each_config_in_its_own_invocation` | Ordinary inputs gate their workflow; frozen inputs report separately under an empty config. |
| `SyntheticWorkflowInvocationTests.test_two_invocations_keep_every_input_and_parser_separate` | Required caller sends exactly ordinary inputs and preserves parser prefixes; separate report fixtures cover the frozen caller. |
| `SyntheticWorkflowInvocationTests.test_each_primary_and_sarif_status_is_retained` | Every ordinary primary/SARIF outcome still affects the required exit code. |
| `SyntheticWorkflowInvocationTests.test_pr_collects_both_primary_statuses_without_sarif` | Required PR caller runs ordinary primary only; frozen native outcomes are retained separately. |
| `SyntheticWorkflowInvocationTests.test_the_step_catches_a_mutant_of_itself` | Caller mutation controls enforce the new exhaustive group separation. |
| `FrozenPolicyMutationTests.test_frozen_advisory_or_package_override_cannot_leak_to_ordinary_inputs` | Historical identities remain forbidden ordinary suppressions; active frozen suppression is rejected. |
| `FrozenPolicyMutationTests.test_expired_config_is_rejected_by_the_actual_preflight_guard` | The actual required guard rejects an expired inactive-disposition review rather than an inactive historical ignore expiry. |

In `tests.test_workflow_hardening`, these kind 3 methods retain the token,
failure and upload protections while moving the frozen part to its new workflow:

- `SecurityScanTests.test_the_write_token_never_reaches_an_installed_tool`
- `SecurityScanTests.test_osv_scanner_fails_on_findings_and_uploads_sarif_off_pull_requests`
- `SecurityScanTests.test_failure_path_semantics_keep_findings_uploadable`

Inventory extensions are kind 1:
`tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests.test_all_published_workflows_are_listed_and_covered`,
the `WRITE_GRANTS` table, and exact reviewed reference-line hashes in
`tests.test_frozen_macos_variant_no_use.PINNED_LINES`. They add the new workflow
without broadening a regex or removing a guard. New disposition mutation and
reporting tests are additions, with synthetic fixtures kept distinct from an
unchanged upstream test or hosted native scan.

## SOTA sources

- `google/osv-scanner@e840a6e8adb14b7777c78e26cfbf6e2abc1d1fc6` (v2.6.0),
  [configuration.md:45](https://github.com/google/osv-scanner/blob/e840a6e8adb14b7777c78e26cfbf6e2abc1d1fc6/docs/configuration.md#L45),
  `internal/config/config.go:38-80,114-156` and
  `internal/config/manager.go:26-69,113-126`: exact matching, expiry and scope.
- Same pin, `internal/scalibrannotator/filter/filter.go:125-168`,
  `pkg/osvscanner/vulnerability_result.go:73-89` and `pkg/osvscanner/filter.go:39-87`: ignored
  packages/advisories are removed from results; filtering is not risk absence.
- [GitHub required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)
  and [job conditions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions),
  read 2026-10-07: non-required reporting is separate from required context health;
  skipped-success is not used as proof of a passed scan.
- [GitHub CLI in workflows](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli)
  and [scheduled issue creation](https://docs.github.com/en/actions/tutorials/manage-your-work/schedule-issue-creation),
  read 2026-10-08: native issue delivery, assignment and job-scoped automatic token.
  `native-agent-stack@36654a8174b5cad1380bd13ed1fffc0f135aac2c:.github/workflows/saturation-tracking.yml:128`
  supplies the existing single-issue upsert pattern.
- [Manual workflow runs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow#running-a-workflow),
  read 2026-10-08: a dispatch selects its branch; both publishing jobs require
  the main ref as well as a trusted event.
- `native-agent-stack@28327acc67e85c480fbf3f9410c65f3d76b5cca4:evidence/receipts/osv-frozen-macos-next-1638-20261007.json`
  and the earlier closure record above retain actual scan results and limits.
