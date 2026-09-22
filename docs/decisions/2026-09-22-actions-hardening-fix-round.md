# Decision: fix round for report-only Actions hardening (2026-09-22)

**Decided by:** unit `actions-hardening`, an owned worktree checkout of this
repository, branch `claude/gap-actions-hardening-20260922`, fixing findings
against commit `90ce605` ("Adopt report-only Scorecard, harden-runner and
dependency-review lanes").

**Scope:** a coordinator fix-round packet with five findings against
`90ce605`. This record resolves the two majors and the one minor that fit
this worker's allowed paths (`.github/workflows/*.yml`,
`docs/github-automation.md`, `docs/decisions/`); the blocker and the other
major require editing `tests/`, which is outside this worker's allowed
paths, and are handed back to the coordinator below with the exact fix
prepared.

## Resolved in this fix round

### Major: `harden-runner` missing from downloading jobs the decision's own rule covers

Per `docs/decisions/2026-09-22-actions-hardening.md` section 2, the rule is
"every `ubuntu-24.04` job that downloads binaries or packages" gets
`step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 #
v2.21.1` as the first step with `egress-policy: audit`. Four such jobs were
found uncovered and are now covered:

| Job | Workflow | Downloads |
| --- | --- | --- |
| `secret-scan` | `validate.yml` | gitleaks release tarball via `curl` |
| `python` | `action-compatibility.yml` | upstream `setup-python` test scripts via `curl` |
| `go` | `action-compatibility.yml` | upstream `setup-go` test script via `curl` |
| `nautilus-offline-replay` | `native-foundation-e2e.yml` | pip wheels (`nautilus_trader` et al.), upstream quickstart source via `curl` |

Each got the identical first-step block already used by the five originally
hardened jobs (`egress-policy: audit`, never `block`); audit mode only logs
observed egress and cannot fail a step, so this cannot change any job's
existing pass/fail result -- unchanged from the original decision's mode
argument.

**`source` (`native-offhost-app-state.yml`) tried, then reverted.** This job
was named in the coordinator's finding evidence and initially given the same
harden-runner step. That broke `python3 -m unittest`:
`tests/test_active_recovery_plans.py::test_default_application_plan_passes_actual_dispatch_source_guard`
calls `run.py`'s `verify_frozen()`, which asserts
`.github/workflows/native-offhost-app-state.yml`'s exact SHA-256
(`76a49ffe92288eb5e5c337523797770e2474b23c6e0b58a4fc5e80a5ce7acd70`, pinned
in `blueprints/convergence-practice/offhost-app-state/plan.json`'s
`frozen_sources` list) against the checked-out file, and any edit to that
workflow changes its hash. Updating that pin means writing
`blueprints/convergence-practice/offhost-app-state/plan.json`, which is
outside this worker's allowed paths (`.github/workflows/*.yml`,
`docs/github-automation.md`, `docs/decisions/`, and `manifests/evidence.json`
/ `docs/ecosystem/index.html` only through repository scripts). The
harden-runner step was reverted from `source` rather than left in with a
broken acceptance run; confirmed by re-running `sha256sum
.github/workflows/native-offhost-app-state.yml`, which now matches the
pinned hash again, and by the unittest re-run below.

**Not extended in this fix round (recorded gap, not fixed):** four more
`ubuntu-24.04` jobs also download packages or binaries and remain
unhardened: `synthetic-restore` (`native-offhost-restore.yml`, `apt-get
install bubblewrap` plus a restic install helper), `owned-guest-reboot`
(`native-service-reboot.yml`, `apt-get install` of QEMU/cloud-image
tooling), and `source` and `destination` (`native-offhost-app-state.yml`,
both call the same `run.py install` helper, and both are covered by the
same `plan.json` frozen-hash pin problem as above -- `destination`'s content
is separately unpinned but was left untouched for symmetry with `source`
rather than hardening only one of a matched pair). `synthetic-restore` and
`owned-guest-reboot` were not named in the coordinator's finding evidence
(scoped to a grep of `validate.yml`, `action-compatibility.yml`,
`native-foundation-e2e.yml`, and `native-offhost-app-state.yml`); extending
to them is outside this fix round's bounded objective.
`docs/github-automation.md` is worded to name the exact nine covered jobs
and list these four plus `bootstrap-macos` (platform-unsupported) as
explicitly excluded, rather than repeating the inaccurate blanket "every
job" claim the finding flagged.

**Evidence that would overturn this gap-not-fixed choice:** a coordinator
instruction to extend the bounded objective and update
`blueprints/convergence-practice/offhost-app-state/plan.json`'s frozen hash
in the same follow-up commit, or a following fix round that adds these jobs
to the finding list.

**Integration follow-up (coordinator, 2026-09-22).** The coordinator's
review found the hardening had no regression test. `tests/test_workflow_hardening.py`
now fails when any downloading `ubuntu` job does not start with harden-runner
in audit mode, when any workflow sets `egress-policy: block`, when Scorecard
publishes or escalates permissions, when dependency review blocks or runs
outside `pull_request`, or when a third-party action is not pinned by full
SHA. Its first run found `owned-guest-reboot` (`native-service-reboot.yml`)
still unhardened. That workflow's retained `freeze.json` files pin an older
hash (`33fc35a6…`) that the current file (`6aa1b1b9…` before this change)
already did not match, and no plan pins its current bytes, so the step was
added there. `native-offhost-app-state.yml` (`76a49ffe…`, `plan.json`) and
`native-offhost-restore.yml` (`91ecb7bd…`, `hosted-plan.json`) stay exempt
by name, and a companion test asserts each still matches its pinning plan, so
the exemption expires the moment either workflow is edited. Overturn: a
re-run of the offhost evidence that re-pins both workflows with the step in
place.

### Major: stale "every `ubuntu-24.04` job" claim in `docs/github-automation.md` and the decision record

`docs/github-automation.md`'s "Report-only Actions hardening, 2026-09-22"
section and `docs/decisions/2026-09-22-actions-hardening.md` section 2 both
said harden-runner covered "every `ubuntu-24.04` job that downloads binaries
or packages," which was false before this fix round (five uncovered jobs
above) and remains not-quite-true after it (three more, listed above).
`docs/github-automation.md` is rewritten to name the exact ten covered jobs
and explicitly list the excluded ones with reasons instead of repeating the
universal claim. `docs/decisions/2026-09-22-actions-hardening.md` gets a
dated correction appendix (matching the pattern its own section 2's
"Excluded jobs" note and section "Correcting a stale statement" already use
in that file) rather than a rewrite of its original evidence.

### Minor: `scorecard.yml` concurrency group never deduplicates

`scorecard.yml`'s `concurrency.group` included `${{ github.run_id }}`, which
is unique per run, so the group could never match a second run and the
`concurrency` block had no effect. Changed to
`${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}`, which
groups by the same ref across the workflow's `schedule`, `push`, and
`workflow_dispatch` triggers (there is no `pull_request` trigger on this
workflow, so `github.ref` is stable for a given trigger rather than needing
a PR-number fallback like `validate.yml` uses). `cancel-in-progress: false`
is unchanged from the original decision's reasoning (do not cancel a
Scorecard run mid-scan).

## Not resolved in this fix round (handed back to the coordinator)

### Blocker: `python3 -m unittest` fails against `tests/test_workflow_security_coverage.py`

`test_all_published_workflows_are_listed_and_covered` (lines 42-61 of that
file) hardcodes the 12 `*.yml` filenames that existed before `90ce605`.
`90ce605` added `scorecard.yml` and `dependency-review.yml`, so
`.github/workflows/*.yml` now globs 14 files and the equality assertion
fails. This worker's allowed paths are `.github/workflows/*.yml`,
`docs/github-automation.md`, `docs/decisions/`, and (through repository
scripts only) `manifests/evidence.json` / `docs/ecosystem/index.html` --
`tests/` is not in that list, so this worker did not edit it. Confirmed by
re-running the suite in this worktree after the fixes above (see
"Re-run" below): identical single failure, same cause.

**Fix ready for a coordinator follow-up commit** (widen the allowed paths or
apply directly on this branch):

```diff
--- a/tests/test_workflow_security_coverage.py
+++ b/tests/test_workflow_security_coverage.py
@@
             "action-compatibility.yml",
             "publish-catalog.yml",
             "adoption-bootstrap.yml",
+            "scorecard.yml",
+            "dependency-review.yml",
         }
```

### Major: no test pins the new harden-runner / Scorecard / dependency-review properties

No test under `tests/` checks that harden-runner is present as the first
step with `egress-policy: audit` on the named jobs, that `scorecard.yml`
keeps `publish_results: false` and `contents: read` only, that
`dependency-review.yml` stays `warn-only: true` on `pull_request` only, or
that the touched workflows keep full-SHA action pins. `grep -rlE
'harden-runner|scorecard|dependency-review' tests` still returns nothing in
this worktree, confirming the gap is unchanged by this fix round. Adding
such a test also requires writing to `tests/`, outside this worker's
allowed paths, so it is handed back with the blocker fix above rather than
added here. A minimal version would parse each workflow YAML (matching the
loader `tests/test_workflow_security.py` already uses for `validate.yml`)
and assert: job's first step is `step-security/harden-runner@<pinned-sha>`
with `with.egress-policy == 'audit'` for the ten named jobs;
`scorecard.yml`'s `analysis` job step `ossf/scorecard-action` has
`publish_results: false` and the job/workflow permissions are `contents:
read` only; `dependency-review.yml`'s trigger is `pull_request` only and its
step has `warn-only: true`.

## Re-run of the acceptance commands after the fixes above

- `python3 -m unittest` -- still fails, same single failure as the
  coordinator's finding (`test_all_published_workflows_are_listed_and_covered`),
  for the reason above; not fixed by this worker for the allowed-paths
  reason above.
- `python3 scripts/validate.py`, `python3 scripts/landscape.py --root .`,
  `python3 tools/sota-convergence/build_verdicts.py --check`, `python3
  scripts/build_ecosystem.py --check`, `zizmor`, `actionlint`: see the
  structured result for this fix round's exact commands and exit codes.

## Evidence class

`local_static_analysis` for the workflow syntax/security checks (`zizmor`,
`actionlint`, matching `validate.yml`'s own invocation) and for the
`grep`/manual review of the additional unhardened jobs listed above. No
`scorecard.yml`, `dependency-review.yml`, or `harden-runner`-added step has
executed on GitHub Actions yet from this fix round either; their actual
hosted behavior remains unobserved until the first hosted run after
integration, unchanged from the original decision record.
