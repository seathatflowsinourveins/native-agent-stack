# Decision: let catalog-freshness open a reviewable evidence PR (2026-09-23)

**Decided by:** unit `catalog-refresh-pr-20260923`, catalog worktree branch
`claude/catalog-refresh-pr-20260923`; the coordinator integrates it into
`agent-lab`'s tracked native-agent-stack checkout.

**Scope:** `.github/workflows/catalog-freshness.yml`'s new `propose` job and
`scripts/freshness_propose.py` only. It never writes
`catalogs/sota-convergence/*`, `catalogs/landscape/*.json`,
`manifests/stack.json`, or `layer-verdicts*` -- those stay owned by the
separate SOTA-convergence lane review
(`recipes/sota-convergence-practice.md`). It adds files only under
`evidence/artifacts/` and `evidence/receipts/`, and updates
`manifests/evidence.json`'s registration and receipt list. `freshness`'s own
job keeps writing nothing to the repository.

## Decision

Give `catalog-freshness.yml` a second job, `propose`, that is off by default
(`needs.freshness.outputs.drift == 'true'` and either an explicit
`workflow_dispatch` `open_pr: true` or a scheduled run with the repository
variable `CATALOG_FRESHNESS_PROPOSE == 'true'`) and, when it does run, opens
or updates a single evidence branch/PR (`automation/catalog-freshness`)
using the job's own default `GITHUB_TOKEN` -- not a GitHub App token and not
a personal access token. The job:

- has job-scoped `permissions: contents: write, pull-requests: write,
  actions: write` (the workflow's top-level `permissions:` stays
  `contents: read`);
- supplies the token to `git push` only through
  `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0`
  (`http.https://github.com/.extraheader`, built at runtime), never a
  persisted credential helper (`actions/checkout` keeps
  `persist-credentials: false`);
- writes a `scripts/validate.py`-shaped receipt whose claim states plainly
  that the run is report-only and that a pin bump needs its own separately
  qualified receipt; and
- dispatches `validate.yml`/`token-report.yml` on the new branch with
  `gh workflow run`, because a push made with the default `GITHUB_TOKEN`
  does not trigger a `pull_request`-event run.

## Evidence

[GitHub's GITHUB_TOKEN reference](https://docs.github.com/en/actions/concepts/security/github_token)
states: "When you use the repository's `GITHUB_TOKEN` to perform tasks,
events triggered by the `GITHUB_TOKEN`, with the exception of `workflow_dispatch`
and `repository_dispatch`, will not create a new workflow run." This is why
`propose`'s push/PR alone would not produce a `pull_request`-triggered
`validate`/`token-report` run, and why the job explicitly calls
`gh workflow run validate.yml --ref automation/catalog-freshness` and
`gh workflow run token-report.yml --ref automation/catalog-freshness`
afterward -- a `workflow_dispatch` call is exempted from that restriction and
always creates a run.

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

- **A GitHub App token (via `actions/create-github-app-token` or
  equivalent).** Would let the evidence branch's push trigger ordinary
  `pull_request`-event runs of `validate.yml`/`token-report.yml` directly,
  matching what a human-opened PR gets, and can be scoped more narrowly than
  the ambient job `GITHUB_TOKEN`. Not adopted yet: it requires provisioning
  and storing a GitHub App's private key as a repository secret, which is a
  standing credential this catalog does not currently hold or need for any
  other automation, for a single weekly/manually-triggered job. Deferred
  until the overturn condition below is observed.
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

- **The first live bot PR's dispatched checks do not satisfy the main
  ruleset's required checks** (for example, `gh workflow run` produces a run
  that GitHub does not associate with the PR the way a `pull_request`-event
  run would, so `validate`/`token-report`/`secret-scan` never show as passing
  status checks on the PR itself) -> a GitHub App token becomes a user
  decision, since only it (not `gh workflow run` dispatch) can make the
  triggered runs first-class `pull_request` checks on the PR.
- **A second, unrelated automation** needs the same or a broader scope of
  write access from the default `GITHUB_TOKEN` in the same run window,
  making the combined blast radius of ambient-token write access harder to
  reason about than a single scoped App token would be.
- **A `secret-scan` or `zizmor` finding** against this specific job once it
  has run live (not just the current offline/static passes recorded below).

## Evidence class

`local_integration` / static analysis only, recorded before any live
dispatch of this job:

- `python3 -m unittest` (2384 tests, `OK (skipped=318)`) including the new
  `tests/test_catalog_freshness_propose.py` (28 tests: pure-function unit
  tests for `scripts/freshness_propose.py`'s drift-table parsing,
  component-id selection, receipt shape, an end-to-end fixture that runs
  `scripts.validate.validate()` against `apply()`'s output, and text-level
  checks of the committed workflow YAML), plus the pre-existing
  `tests/test_workflow_hardening.py`, `tests/test_workflow_security.py`,
  `tests/test_workflow_security_coverage.py`, and
  `tests/test_catalog_freshness_pins.py`, all still green.
- `scripts/validate.py`, `scripts/validate_catalogs.py`,
  `scripts/validate_foundation.py --root . --json`, `scripts/landscape.py
  --root .`, `scripts/validate_convergence.py --all-recorded --root .
  --json`, `scripts/build_ecosystem.py --check`,
  `tools/sota-convergence/build_verdicts.py --check`,
  `python3 scripts/host_receipts.py validate`, and
  `scripts/component_matrix.py --check` all pass against the edited
  repository state.
- `zizmor --offline --no-config --no-ignores --persona regular
  --strict-collection` on `.github/workflows/catalog-freshness.yml` returns
  `[]` (zero findings); `actionlint` (1.7.12) returns clean on the same
  file.
- No live dispatch of `propose` has been observed: no PR has actually been
  opened, no branch actually pushed with a live `GITHUB_TOKEN`, and the
  one-time "Allow GitHub Actions to create and approve pull requests"
  repository setting has not been confirmed enabled. That first live run,
  and confirming its dispatched checks land as expected on the PR, is the
  concrete gap the overturn condition above names.
