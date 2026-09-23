# Decision: let catalog-freshness open a reviewable evidence PR (2026-09-23)

**Decided by:** unit `catalog-refresh-pr-20260923`, catalog worktree branch
`claude/catalog-refresh-pr-20260923`; the coordinator integrates it into
`agent-lab`'s tracked native-agent-stack checkout. Revised the same day after
an independent Opus review (H1/H2/M1/L1-L6/T1-T3 findings) and a Codex
cross-family review (P1: the original dispatch design is refuted by primary
GitHub documentation) -- see "Corrected claim" below.

**Scope:** `.github/workflows/catalog-freshness.yml`'s new `propose` job and
`scripts/freshness_propose.py` only. It never writes
`catalogs/sota-convergence/*`, `catalogs/landscape/*.json`,
`manifests/stack.json`, or `layer-verdicts*` -- those stay owned by the
separate SOTA-convergence lane review
(`recipes/sota-convergence-practice.md`). It adds files only under
`evidence/artifacts/` and `evidence/receipts/`, and updates
`manifests/evidence.json`'s registration and receipt list. `freshness`'s own
job keeps writing nothing to the repository.

## Corrected claim

The first version of this record asserted that dispatching
`gh workflow run validate.yml --ref automation/catalog-freshness` (and the
same for `token-report.yml`) after pushing the evidence branch would supply
"the same review evidence opening the PR normally would have produced" --
i.e., that those dispatched runs would satisfy the main ruleset's required
status checks on the resulting PR. **This is refuted by GitHub's own
documentation**, found during the Codex cross-family review and confirmed
independently against the primary source (fetched 2026-09-23):

> "For checks created by workflow jobs to be evaluated for a pull request,
> the workflow run must be triggered by one of these events: `push`,
> `pull_request`, `pull_request_review`, `pull_request_target`,
> `deployment`, `deployment_status`"
> -- [Troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)

`workflow_dispatch` is not on that list. A dispatched run's checks therefore
never satisfy a required status check on the PR, regardless of whether they
pass -- the design would have produced a green-looking but not-actually-
required run, while the PR's own real `pull_request`-triggered checks (the
ones the ruleset actually requires) never ran at all. The `gh workflow run`
dispatch step has been removed entirely; see "Decision" below for the
corrected design.

## Decision

Give `catalog-freshness.yml` a second job, `propose`, that is off by default
(`needs.freshness.outputs.drift == 'true'`, an unbounded and error-free
freshness fetch, and either an explicit `workflow_dispatch` `open_pr: true`
or a scheduled run with the repository variable
`CATALOG_FRESHNESS_PROPOSE == 'true'`) and, when it does run, opens or
updates a single evidence branch/PR (`automation/catalog-freshness`) using
the job's own default `GITHUB_TOKEN` -- not a GitHub App token and not a
personal access token. The job:

- has job-scoped `permissions: contents: write, pull-requests: write` (no
  `actions: write`; the workflow's top-level `permissions:` stays
  `contents: read`);
- supplies the token to `git push` only through
  `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0`
  (`http.https://github.com/.extraheader`, built at runtime and masked with
  `::add-mask::` before use), never a persisted credential helper
  (`actions/checkout` keeps `persist-credentials: false`);
- pushes with `--force-with-lease=automation/catalog-freshness:<observed-sha>`
  against the remote branch tip it just observed with `git ls-remote`, not a
  plain `--force`, so a concurrent run's push is rejected rather than
  silently overwritten; the workflow's single `${{ github.workflow }}`
  concurrency group (`cancel-in-progress: false`, no `event_name` in the
  group key) already serializes every run of this workflow regardless of
  trigger, and the lease is a second, independent guard against the same
  race, not the only one;
- writes a `scripts/validate.py`-shaped receipt whose claim states plainly
  that the run is report-only and that a pin bump needs its own separately
  qualified receipt, with `component_ids` limited to this run's drifted ids
  that are real `manifests/stack.json` components -- raising (no PR, no
  branch push) rather than falling back to an unrelated fixed component set
  when none match; and
- does **not** dispatch any other workflow. Instead, it relies on the PR's
  own `pull_request`-triggered runs and prints the PR URL plus an explicit
  note that a write-access collaborator must approve them (see "Corrected
  claim" above and "Evidence" below for why).

## Evidence

[GitHub's `GITHUB_TOKEN` reference](https://docs.github.com/en/actions/concepts/security/github_token)
states: "When you use the repository's `GITHUB_TOKEN` to perform tasks,
events triggered by the `GITHUB_TOKEN`, with the exception of
`workflow_dispatch` and `repository_dispatch`, will not create a new
workflow run" -- confirming `propose`'s push/PR alone does not itself
produce a `pull_request`-triggered `validate`/`token-report`/`secret-scan`
run. The same document additionally states, for the specific case of a PR
created by a `GITHUB_TOKEN`-driven workflow: "the resulting `pull_request`
event creates workflow runs in an **approval-required** state ... a user
with write access to the repository can start the runs by selecting
**Approve workflows to run**." So the PR's own `pull_request` runs *are*
created (unlike a naive reading of the first sentence alone might suggest),
but they wait for a write-access approval rather than running immediately.
This is the mechanism `propose` now relies on instead of dispatching.

[Troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
(quoted in full under "Corrected claim") is why dispatching a separate
`workflow_dispatch` run was abandoned: it cannot substitute for the
approval-gated `pull_request` run for the purpose of satisfying a required
status check.

The REST API reference for [approving a workflow run](https://docs.github.com/en/rest/actions/workflow-runs)
documents exactly one relevant endpoint, `POST
/repos/{owner}/{repo}/actions/runs/{run_id}/approve`, whose own description
reads "Approves a workflow run for a pull request from a public fork of a
first time contributor." This repository's evidence PR is a same-repository
branch, not a fork PR, so **this documentation does not establish that this
endpoint (or any documented endpoint) covers approving a GITHUB_TOKEN-created
same-repo PR's pending run.** Rather than assume it works and script an
automatic approval call that might 404 or silently no-op, `propose` prints
the PR URL and instructs a human to use the Actions tab's "Approve and run
workflow" UI action instead -- documented, unambiguous, and the same
mechanism GitHub's own fork-PR guidance describes for the UI path.

[GitHub's repository Actions settings documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#preventing-github-actions-from-creating-or-approving-pull-requests)
documents the separate, one-time repository setting this job depends on:
"You can also prevent GitHub Actions from creating or approving pull
requests... By default, this setting is disabled." I.e. without a
maintainer first enabling **"Allow GitHub Actions to create and approve pull
requests"** (Settings -> Actions -> General -> Workflow permissions),
`propose`'s `gh pr create` step fails even with `pull-requests: write`
granted at the job level; this is recorded here as a required, coordinator-only
precondition rather than something this unit's tests can exercise.

## Alternatives considered

- **Approval-required `pull_request` runs (chosen).** No new credential and
  no new automation surface: it reuses the token and the checkout the job
  already has, and turns the "someone must review this bot PR" principle
  this whole design is built on into an actual required gate -- the PR's
  checks cannot run at all until a human explicitly approves them. The cost
  is one manual click per run that opens a PR (not per scheduled run that
  finds no drift, and not at all when `propose` never runs).
- **A GitHub App token (via `actions/create-github-app-token` or
  equivalent).** Its workflow-run events are on the eligible-events list for
  required status checks (unlike `workflow_dispatch`), and are not subject to
  the `GITHUB_TOKEN` approval-required gate the way a `GITHUB_TOKEN`-created
  PR is, so it would let the PR's checks run immediately rather than waiting
  on manual approval. Not adopted yet: it requires provisioning and storing a
  GitHub App's private key as a repository secret, which is a standing
  credential this catalog does not currently hold or need for any other
  automation, for a single weekly/manually-triggered job. Deferred until the
  overturn condition below is observed.
- **A personal access token (classic or fine-grained) stored as a
  secret.** Same triggering benefit as a GitHub App token, with a strictly
  worse security profile: it is tied to one human account, does not rotate
  automatically, and typically carries broader scope than this job needs.
  Rejected outright; not revisited unless the App-token alternative is also
  rejected for an unrelated reason.
- **Stay report-only (the prior state).** Zero new permissions, zero new
  attack surface, and the original, simplest design. Rejected as the sole
  path forward because a report-only artifact that nobody is prompted to act
  on tends to go unread -- the explicit goal here is for the catalog to keep
  evolving from evidence, which needs a concrete, reviewable next step
  (a PR) rather than a 30-day workflow artifact. Kept as the *default*
  behavior (the job does not run without an explicit opt-in), so this is a
  strictly additive capability, not a replacement of the existing report-only
  lane.

## Evidence that would overturn this decision

- **The approval path does not actually produce required checks on the PR
  head** (for example, approving the pending run does not make
  `validate`/`token-report`/`secret-scan` show as passing status checks the
  ruleset recognizes on that PR, or the pending run never appears for a
  write-access user to approve at all) -> a GitHub App token becomes a user
  decision, since it is not subject to the `GITHUB_TOKEN` approval gate and
  its events are on the required-status-check eligible-events list.
- **Approval cannot be done through the API** in a way that is actually
  scoped to this same-repo GITHUB_TOKEN-PR case (the fork-PR `approve`
  endpoint 404s or otherwise does not apply) *and* the manual UI step proves
  to be an unacceptable operational burden -> revisit whether a GitHub App
  token's immediate-run behavior is worth its credential cost, per the
  alternative above.
- **A second, unrelated automation** needs the same or a broader scope of
  write access from the default `GITHUB_TOKEN` in the same run window,
  making the combined blast radius of ambient-token write access harder to
  reason about than a single scoped App token would be.
- **A `secret-scan` or `zizmor` finding** against this specific job once it
  has run live (not just the current offline/static passes recorded below).

## Evidence class

`local_integration` / static analysis only, recorded before any live
dispatch of this job:

- `python3 -m unittest` (full suite) including the rewritten
  `tests/test_catalog_freshness_propose.py` (52 tests: pure-function unit
  tests for `scripts/freshness_propose.py`'s drift-table parsing,
  drift-vs-unfetched classification, `md_cell()` escaping, component-id
  selection with its raise-not-fallback rule, receipt shape, symlink-refusal
  on every write destination, an end-to-end fixture that runs
  `scripts.validate.validate()` against `apply()`'s output, a real-subprocess
  suite against a throwaway git-tracked repository copy that reproduces the
  H1 stdout-contract fix, and text-level checks of the committed workflow
  YAML including the full normalized `if:` expression), plus the pre-existing
  `tests/test_workflow_hardening.py`, `tests/test_workflow_security.py`,
  `tests/test_workflow_security_coverage.py`, and
  `tests/test_catalog_freshness_pins.py`, all still green. Exact counts and
  the full acceptance command list are in the unit's final report.
- `scripts/validate.py`, `scripts/validate_catalogs.py`,
  `scripts/validate_foundation.py --root . --json`, `scripts/landscape.py
  --root .`, `scripts/validate_convergence.py --all-recorded --root .
  --json`, `scripts/build_ecosystem.py --check`,
  `tools/sota-convergence/build_verdicts.py --check`,
  `python3 scripts/host_receipts.py validate`, and
  `scripts/component_matrix.py --check` all pass against the edited
  repository state, and separately against a full-history scratch clone
  after running `apply()` with a synthetic drift fixture.
- `zizmor --offline --no-config --no-ignores --persona regular
  --strict-collection` on `.github/workflows/catalog-freshness.yml` (and the
  full `.github/workflows` directory) returns `[]` (zero findings);
  `actionlint` (1.7.12) returns clean on the same files.
- No live dispatch of `propose` has been observed: no PR has actually been
  opened, no branch actually pushed with a live `GITHUB_TOKEN`, the
  one-time "Allow GitHub Actions to create and approve pull requests"
  repository setting has not been confirmed enabled, and the
  approval-required flow has not been exercised against a real pending run.
  That first live run is the concrete gap the overturn condition above
  names.
