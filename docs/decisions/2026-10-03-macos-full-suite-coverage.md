# What may change in the required macOS check, decided by measurement (2026-10-03)

Lane: foundation. North-star action served: a reliable, fast landing path for every unit that moves the stack toward
the north star (each unit lands as a pull request behind the required checks). Status: decided. O4 proceeds; O2 is a
pre-registered fallback, not adopted; O1 and O3 are rejected; R1 to R6 are proposals for their owners. This record
changes no workflow, test, ruleset, required check or repository setting; each change it names lands in its own
reviewed pull request.

## Measured findings

Measured on 2026-10-03 with read-only `gh` REST GET calls over the runs created 2026-09-25 to 2026-10-02 UTC (8,782
runs; every query partition stayed under the 1,000-result cap). The counts are recorded in
[`evidence/receipts/github-ci-measurements-20261003.json`](../../evidence/receipts/github-ci-measurements-20261003.json),
with the compiled measurement input published byte-identical beside it
([`input.json`](../../evidence/artifacts/github-ci-measurements-20261003/input.json)). The measurement kept neither its
returned payloads nor its per-call argument vectors, so the counts can be re-derived from GitHub only while the run
records exist (up to 90 days here); after that the receipt is a recorded summary that can be quoted but not re-checked. Its
`queries` section gives the request forms as reconstructed templates, not a transcript. The counts cover that 8-day
window; the duration samples below (12 macOS and 3 Linux pull-request runs) are the newest runs at measurement time,
created on 2026-10-02 and 2026-10-03 (up to 2026-10-03T01:18Z for the macOS sample; the Linux sample's creation range is
inferred from run ids above the macOS sample's last id). The push and pull-request wall-time medians in Reductions are
the first three successful runs per event at measurement time.

- **Both required test jobs run the whole suite serially in one process.** The Linux `validate` job
  (`python3 -m unittest`, `.github/workflows/validate.yml:218-219`) took 1,727-1,745 s on sampled pull-request runs
  and 1,167-1,828 s on push runs, against a 2,400 s limit (`validate.yml:31`; 1,828 s is 76% of it). The macOS
  `validate-macos` job (`.github/workflows/adoption-bootstrap.yml:606-753`, `macos-15`) took 1,932-2,394 s, a median
  of 2,154 s over 12 pull-request runs, against 3,600 s (`adoption-bootstrap.yml:610`). Its full-suite step
  (`:732-745`) is 84% of the median job; with the step that gates on the adoption test modules (`:725-731`), the two
  test steps are 90%.
- **The suite keeps growing.** The serial macOS run went from 5,596 tests in 489 s on 2026-09-25 to 9,483 tests in
  1,830 s on 2026-10-02 (0.087 to 0.193 s per test); the latest log seen ran 9,750 tests.
- **Churn, not failure.** Pull-request runs of "Validate published evidence" were 1,354 (816 success, 88 failure, 449
  cancelled, 1 action_required) and of "Adoption bootstrap smoke" 1,028 (700, 75, 252, 1): 6.5% and 7.3% failed, and
  33% and 25% were cancelled (46% and 36% on 2026-10-01 and 2026-10-02). 672 of all 712 cancelled runs in the window (94.4%;
  701 of the 712 were pull-request runs of these two workflows) were superseded by a newer run of the same workflow,
  branch and event. For Validate, 241 of its 425 superseded
  pull-request runs were replaced by a run on the same head SHA, against 2 of 243 for Adoption. Validate adds
  `edited` to its pull-request types (`validate.yml:9`) and Adoption keeps the default types, which fits that
  difference; the runs API does not expose the action type, so the link is an inference.
- **No timeouts were recorded.** No run concluded `timed_out` and no failing job had a cancelled step; the longest
  failing Validate job ran 1,787 s and the longest failing `validate-macos` job 2,302 s. Timeouts among the cancelled
  runs were not classified.
- **The macOS leg fails where Linux passes.** Of 1,025 pull-request head SHAs paired across the Linux
  `validate` run and the macOS run, 695 passed both, 46 failed both, 30 failed only on macOS (2.9% of SHAs, 3.9% of
  the 779 decisive pairs), 8 failed only on Linux and 246 were incomplete (146 cancelled on both, 80 where Linux
  passed and the macOS run was cancelled before a verdict, 12 where Linux failed and macOS was cancelled, and 8
  other). 29 of the 30 failed in the full-suite step and 1 in the bootstrap recording smoke. The failing tests read
  from the log artifacts for 17 of the 30 (15 read by the measuring agent, 2 more read for this record) range from tests the pull request
  itself added (`tests.test_new_wsl_client_config.CodexMergeTests`, 2026-10-02) and a recurring
  `ChildUsageNodeSuite.test_node_suite_passes` (4 SHAs on 2026-09-30) to timing and signal tests:
  `tests.test_secret_path_guard.K4GuardTests.test_k4_timing` on two SHAs and the `SIGQUIT` subtest of
  `tests.test_credential_run.ProcessTests.test_exit_code_and_signal_propagate` on one.
- **Push runs on `main` are never collapsed.** There were 350 Validate and 339 Adoption push runs in 8 days, up to 90
  a day, and 1 of these 689 runs was cancelled: a push run's concurrency group ends in its run id
  (`validate.yml:15-17`, `adoption-bootstrap.yml:49-51`).

## Decision

- **O4, keep the full suite on macOS for every pull request and shorten both required test jobs: proceed.** On 30 of
  1,025 pull-request head SHAs in 8 days the macOS leg failed while the Linux leg passed, so coverage stays as it is.
  Time-to-green is bounded by the slower of two serial suites, so the lever is to run both suites faster with the same
  tests and the same required check names. That speed-up is decided by its own preregistered trial in its own pull
  request; this record does not depend on its outcome.
- **O1 and O3: rejected** (see Alternatives).
- **O2: a pre-registered fallback, not adopted.** Its adoption rule is fixed under Preregistered checks before any
  evidence for it is read.
- **R1 to R6** go to their owners as proposals (see Reductions); this record makes none of those changes.

## Alternatives

- **O1, gate the whole `validate-macos` job by changed paths** (a `paths` filter, `needs:` on the `changes` job or a
  job-level `if:`). Rejected:
  - `tests/test_workflow_hardening.py:1247-1255` forbids `needs:` and a job-level `if:` on `validate-macos`, so the
    required check is reachable on every pull request, and `:1242-1245` forbids a `paths` filter on the
    pull-request trigger.
  - GitHub reports a job skipped by a conditional as "Success", and leaves the checks of a workflow skipped by path
    filtering "Pending". On a pull request, a skipped `validate-macos` would be a green required check with nothing
    run, which `docs/acceptance-evidence-policy.md:42-53` rejects as a vacuous pass.
  - The `changes` job's bootstrap pattern list (`adoption-bootstrap.yml:98-119`) covers bootstrap inputs, not what a
    suite of more than 9,000 tests depends on.
- **O2, always run the validators and the bootstrap smoke on macOS and gate only the full-suite step.** A
  pre-registered fallback, not adopted.
  - An in-job, fail-safe step would skip the full-suite step (`adoption-bootstrap.yml:732-745`) only when every
    changed path is on a frozen INERT list. An unknown path, an empty diff, an error in the gate step or a
    non-pull-request event runs the suite. The job itself still runs on every pull request; only that step can be
    skipped, and only after O2 is adopted: in the dry-run phase under Preregistered checks the gate skips nothing and
    only reports what it would have skipped.
  - Prose is not inherently inert. 124 of the 237 Python files under `tests/` mention `.md`, and
    `tests/test_adoption_docs_consistency.py:70-71` reads `adoption/**/*.md`, `docs/next-host-stages.md`,
    `docs/contributing-evidence.md` and `recipes/host-request-lane.md`. INERT is therefore derived by excluding every
    path any test reads, not by file type, and the owner freezes it before any dry-run evidence is read.
  - Before a gate script is written, a recorded head-to-head compares the in-repository reference implementation,
    the `changes` job's fail-safe script (`adoption-bootstrap.yml:86-155`), with a maintained upstream path-filter
    action (a third-party action also needs an allow-list entry).
  - Controls, if it is built: unit tests of the extracted script in a temporary git repository (local integration);
    a hosted positive control (during the dry run, a docs-only commit makes the gate report would-skip while the
    full-suite step still runs; once skipping is enabled, the same commit shows the step `skipped`); a hosted negative
    control (a planted `skipUnless(sys.platform == "darwin")` failing test on a non-inert path turns `validate-macos`
    red). A failing control on a non-inert path cannot reveal a wrong INERT classification; only the dry-run phase can.
- **O3, run the full suite on macOS only after merge and weekly.** Rejected: its own rule needs zero macOS-only
  failures over at least 100 distinct pull requests since full-suite gating began (#126), and the first 8-day sample
  shows 30 among 1,025 pull-request head SHAs.
- **A merge queue, so the heavy suite runs once per merge group.** Not available here: GitHub offers merge queues in
  public repositories owned by an organization and in private repositories of organizations on Enterprise Cloud, and
  `gh api --method GET repos/seathatflowsinourveins/native-agent-stack --jq .owner.type` returned `User`
  (2026-10-03).

## Reductions

| Item | Proposal | Measured basis | Owner and default |
| --- | --- | --- | --- |
| R1 | Collapse concurrent push runs on `main` with a push-scoped concurrency group without `queue: max`, in `validate.yml`, `token-report.yml`, `security-scan.yml` and `adoption-bootstrap.yml` | 350 Validate and 339 Adoption push runs in 8 days, up to 90 a day, 1 of the 689 cancelled; median wall time 1,740 s and 2,163 s | The repository owner, because it conflicts with `docs/github-automation.md:77` ("Run on the integrated revision"); default no change until measured |
| R2 | Run the report-only betterleaks trial (`secret-scan-betterleaks`, `validate.yml:394`) only after merge | It has no job-level condition, so it runs on every pull-request event; its minutes were not measured here | The automation maintainer, with P1 of `docs/decisions/2026-10-02-github-automation-practice.md` |
| R3 | Move the `sota-sources` job (`validate.yml:564`), which reads the pull-request description, into its own small workflow that runs on `edited`, keeping the job name so the required context is unchanged, so a description edit stops restarting the 29-minute `validate` job | 241 of Validate's 425 superseded pull-request runs were replaced by a run on the same head SHA, against 2 of 243 for Adoption; in the failure anatomy, which classified 80 of Validate's 88 failed pull-request runs, 13 of 86 failing job instances were the `sota-sources` gate, which a description edit fixes; the 8 runs it left out each failed only in `sota-sources` and a later run on the same head SHA passed, so over all 88 runs the gate has 21 of 94 instances (reclassified 2026-10-03) | The automation maintainer, after the speed-up. Unresolved: `edited` is also how a retargeted pull request is judged again against its new base (`validate.yml:6-9`; `tests/test_workflow_hardening.py:539-544`, review of #135, H1), so dropping it from the heavy workflow needs a replacement for that run. Never gate a job on `github.event.action`: a skipped job reports Success and can put a green check on a red SHA |
| R4 | Run `bootstrap-macos-brew` (`adoption-bootstrap.yml:536`) only on push and on the weekly schedule (`:42-43`) | It runs on a pull request whenever a bootstrap path changed (`:541`); its minutes were not measured here | The adoption owner; `tests/test_workflow_hardening.py:1257-1288` changes with it |
| R5 | Extend `scripts/git-hooks/pre-push`, which already runs three registry tests on each pushed tip, with the fast validators that fail in CI, and with a non-empty SOTA sources check when the description is drafted first | In the failure anatomy (80 classified of Validate's 88 failed pull-request runs, all 75 of Adoption's), validator and lint steps failed 18 times in Validate (host evidence receipts 4, new-host grand list 3, convergence evidence 3, release-due report 2, landscape choices 2, manifests and evidence integrity 2, actionlint 1, capability claims 1) and 15 times in `validate-macos` (convergence evidence 4, host receipts 4, grand list 2, landscape choices 2, manifests 2, capability claims 1; the 3 failures of its adoption-module gate step count as test failures), one commit can fail both, and `sota-sources` 13 times (21 over all 88 runs); it cannot reach the dominant class, the test steps (47 failing instances in Validate's unittest step, also 47 over all 88 runs; 54 in the macOS full-suite step and 3 in its adoption-module gate step) | The automation maintainer |
| R6 | De-flake or fix the timing and signal tests that fail only on macOS | `K4GuardTests.test_k4_timing` failed only on macOS on two SHAs and the `SIGQUIT` subtest of `ProcessTests.test_exit_code_and_signal_propagate` on one; each failure costs a whole required cycle (the macOS job's median is 2,154 s) | The owners of `tests/test_secret_path_guard.py` and `tests/test_credential_run.py` |

The failure counts in R3 and R5 come from the receipt's failure anatomy, which classified 80 of Validate's 88 failed
pull-request runs, all 75 of Adoption's and 10 of the 76 failures of other workflows. The measurement did not record
why 8 Validate runs were left out. A later reclassification of all 88 (2026-10-03, rule and rows in the receipt) shows
that the 80 are the failed runs that no later run on the same head SHA turned green, and that each of the other 8
failed only in `sota-sources`; including them strengthens R3 and leaves R5's ordering unchanged. The 66 unclassified
failures of other workflows (64 security-scan, 2 dependency-review) are outside both counts; whether R5's pre-push
check would reach any of them is unknown.

## Preregistered checks

O2 can be adopted only through this rule, fixed now, before any evidence for it is read; adoption would be its own
decision record.

- **Retrospective window, a preliminary signal only.** At least 14 days of pull-request history from 2026-09-25, so
  readable from 2026-10-09: the frozen INERT list is applied to past pull requests to see which ones the gate would
  have skipped and whether any of those failed only on macOS. It cannot adopt O2.
- **Prospective dry-run phase, required for adoption.** For 14 days after the gate exists, the gate only computes
  and reports, on every pull request, whether it would skip the full-suite step. The required `validate-macos` job
  keeps running the full suite on every pull request, so coverage never drops during the phase and a Darwin-only
  failure still blocks the merge. The pull requests the gate would have skipped form the gated-out set, and their
  full-suite results, read from the required job, are the held-out evidence E_G. The gate starts to skip only after
  the thresholds below pass, in a later, separately reviewed change with its own decision record; until then O2 stays
  a non-adopted fallback. A shadow design, in which the required job skips the step and a non-required job runs the
  suite, is not used: a Darwin-only failure found only by a non-required job would not block the merge, so O2 would
  be in effect before its thresholds pass.
- **Thresholds, all required over the dry-run phase:**
  - N_PR >= 100 distinct pull requests with a paired, decisive Linux and macOS verdict;
  - N_G >= 30 distinct gated-out pull requests (the gate reported that it would skip);
  - E_G = 0 macOS-only failures of the required job's full-suite step in the gated-out set;
  - B >= 0.25, the share of paired pull-request heads gated out (B is measured over heads; the other thresholds count
    distinct pull requests).
- **Escape bound, frozen in advance.** With zero failures in N gated-out pull requests, the exact one-sided 95% upper
  bound on the escape rate is 1 - 0.05^(1/N) (the exact binomial limit with zero defects): 9.50% at N_G = 30 and
  2.95% at N_G = 100, close to the rule of three, 3/N. The owner freezes the acceptable bound before the dry-run phase
  starts; a 5% bound needs N_G >= 59.
- **Counting and queries.** Count distinct pull requests, not reruns. Slice every history query by `created` day and
  require each slice's `total_count` to be under 1,000, because the list-runs endpoint returns at most 1,000 results
  per search with the `created`, `event` or `head_sha` filters; split a slice that reaches the cap instead of reading
  it as complete.
- **Never adopt** if E_G >= 1, if the sample falls short of any threshold, or if B < 0.25.
- **What the history cannot show**, so the rule does not cover it: new Darwin-specific failure classes; runner-image
  or Python updates; filename-case collisions on APFS; and how pull requests change once they are not gated.

## Overturn

Revisit this record when any of these happens:
- O2's rule passes in the dry-run phase (adopt it in a new record), or the owner sets a time budget that the speed-up
  cannot meet;
- the speed-up trial fails its own rule, or a required test job times out (raise `timeout-minutes` as the stopgap and
  reconsider O2);
- after R6 lands, a prospective window of at least 100 distinct pull requests shows zero macOS-only failures. This is a
  new condition this record adds: O3's own rule (zero since #126) cannot be met retrospectively, because the
  failures above already exist;
- `tests/test_workflow_hardening.py:1242-1255` changes by its own reviewed decision, or GitHub changes how a skipped
  job or a skipped workflow reports to a required check;
- the required checks, the runner labels (`macos-15`, `ubuntu-24.04`) or the concurrent macOS job limit (5 on the
  Free and Pro plans) change;
- a merge queue becomes available to this repository;
- the owner decides R1 against `docs/github-automation.md:77`.

## Evidence class

Measured: the run, job and step counts and durations come from read-only `gh` REST GET calls on 2026-10-03 over
GitHub's own Actions records and the full-suite log artifacts (platform records, the Independent observation class of
`docs/acceptance-evidence-policy.md`). What the measurement kept is a recorded summary (the receipt and its published
input), not its returned payloads or per-call argument vectors, so it does not meet the exact-vector and
returned-output rule of `docs/acceptance-evidence-policy.md:57-60`. Later observation, after the measurement: read-only
GET calls on 2026-10-03, kept with exact argument vectors, times, exit codes and payload hashes in
`evidence/artifacts/github-ci-measurements-20261003/later-reads-20261003.json`, reclassified all 88 failed Validate
pull-request runs and placed the 712 cancelled runs by workflow and event, and read both cache endpoints and the
retention setting. The 1,025-SHA pairing was cross-checked on two endpoints. The
pull-request conclusion counts for 2026-10-01 and 2026-10-02 were recomputed independently with identical cells; an
independent run-level pairing of those two days found 4 macOS-only failures among 140 decisive pairs, against the
measuring agent's 5 among 143 decisive pairs (218 paired heads), a difference this record does not reconcile (likely run-level against job-level pairing
or list completeness; that cause is an inference). Source reads: the workflow and test lines
cited here, at `56473e4b`. Computed, not measured: the escape bounds. Local integration: none for this record; the O2
gate-script unit tests would be local integration if built. GitHub's documentation statements were read on
2026-10-03. Nothing here is upstream acceptance.

## SOTA sources

- GitHub documentation, read 2026-10-03:
  - Skipped jobs and workflows on required checks:
    https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks
  - Workflow concurrency (`cancel-in-progress`, `queue`):
    https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
  - Actions limits (job execution time, concurrent macOS jobs by plan): https://docs.github.com/en/actions/reference/limits
  - Events that trigger workflows (default `pull_request` activity types):
    https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
  - Workflow syntax (`jobs.<job_id>.if`, `jobs.<job_id>.needs`, `timeout-minutes`):
    https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
  - Merge queues:
    https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
  - Listing workflow runs (up to 1,000 results per search): https://docs.github.com/en/rest/actions/workflow-runs
  - Retention of checks, workflow runs and commit statuses from 2026-10-01:
    https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository
- Rule of three: Hanley JA, Lippman-Hand A. If nothing goes wrong, is everything all right? Interpreting zero
  numerators. JAMA 1983;249(13):1743-1745. https://doi.org/10.1001/jama.1983.03330370053031
- Exact binomial confidence limits: NIST/SEMATECH e-Handbook of Statistical Methods, 7.2.4.1 Confidence intervals,
  https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm
- In-repository: `tests/test_workflow_hardening.py`, `docs/acceptance-evidence-policy.md`,
  `docs/decisions/2026-10-02-github-automation-practice.md`, the receipt above and its two artifacts under
  `evidence/artifacts/github-ci-measurements-20261003/`.
