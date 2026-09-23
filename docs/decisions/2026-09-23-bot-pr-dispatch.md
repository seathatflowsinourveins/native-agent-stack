# Decision: let catalog-freshness open a reviewable evidence PR (2026-09-23)

**Decided by:** unit `catalog-refresh-pr-20260923`, catalog worktree branch
`claude/catalog-refresh-pr-20260923`; the coordinator integrates it into
`agent-lab`'s tracked native-agent-stack checkout. Revised twice the same
day: first after an independent Opus review (H1/H2/M1/L1-L6/T1-T3 findings)
and a Codex cross-family review (P1: the original dispatch design is
refuted by primary GitHub documentation -- see "Corrected claim" below);
then after a second Opus pass-with-findings review (N1-N4) and a Codex
re-review (two reproductions of N1/N2, plus P2-3: a pending opt-in run can
be silently discarded) -- see "Second fix round" at the end.

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
  silently overwritten -- this is the actual data-safety guard against a
  race; a job-scoped `concurrency:` group on `propose` (keyed on manual vs.
  scheduled, see "Second fix round") additionally queues most overlapping
  runs so they do not even attempt to race in the first place;
- writes a `scripts/validate.py`-shaped receipt whose claim states plainly
  that the run is report-only and that a pin bump needs its own separately
  qualified receipt, with `component_ids` limited to this run's actually-
  drifted ids that are real `manifests/stack.json` components -- raising (no
  PR, no branch push) rather than falling back to an unrelated fixed
  component set when none match (see "Second fix round" for the corrected
  drift-vs-unfetched-vs-no-release classification this depends on); and
- does **not** dispatch any other workflow. Instead, it relies on the PR's
  own `pull_request`-triggered runs and prints the PR URL plus an explicit
  note that a write-access collaborator must approve them (see "Corrected
  claim" above and "Evidence" below for why).

## Evidence

[GitHub's `GITHUB_TOKEN` reference](https://docs.github.com/en/actions/concepts/security/github_token)
states (current wording as fetched 2026-09-23; the first version of this
record quoted an older paraphrase, "with the exception of `workflow_dispatch`
and `repository_dispatch`," corrected here to the exact current text):
"events triggered by the `GITHUB_TOKEN` will not create a new workflow run,
with the following exceptions:" followed by a list including
"`workflow_dispatch` and `repository_dispatch` events always create workflow
runs" and "`pull_request` events with the `opened`, `synchronize`, or
`reopened` activity types: when a workflow using `GITHUB_TOKEN` creates or
updates a pull request, the resulting `pull_request` event creates workflow
runs in an **approval-required** state." So the PR's own `pull_request` runs
*are* created (unlike a naive reading of only the lead sentence might
suggest), but they wait for a write-access approval rather than running
immediately. This is the mechanism `propose` now relies on instead of
dispatching.

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
the PR URL and instructs a human to use the documented UI path instead: per
[GitHub's fork-PR approval guidance](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)
(the same UI flow it also documents for a non-fork GITHUB_TOKEN-created PR's
approval-required runs), a collaborator with write access opens the pull
request and uses the approval banner in its merge box (the GITHUB_TOKEN
page's wording), selecting **"Approve workflows to run"**; the fork-approval
page reaches the same action through an **"Awaiting approval"** button that
opens the merge status panel -- not the Actions tab directly. The same page states that "workflow
runs that have been awaiting approval for more than 30 days are
automatically deleted," so an evidence PR left unreviewed that long needs a
fresh `propose` run before its checks can run.

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

## Second fix round (Opus N1-N4, Codex P2-3), 2026-09-23

An independent Opus re-review of the first fix round returned
**pass-with-findings** (every earlier H/M/L/T finding closed) but raised
four new findings (N1, N2, N2b, N3, N4); a Codex cross-family re-review
independently reproduced N1 and N2 with concrete fixtures and raised one
new finding, P2-3.

**N1/N2 bug (medium): `compute_drift` hid real pin changes and mislabeled
legitimate no-release repositories.** The prior `compute_drift` skipped a
row entirely whenever the *rebuilt* row's `upstream.latest` was `None`,
before ever comparing `pin`. This had two failure modes, both reproduced as
regression tests in `tests/test_catalog_freshness_propose.py`:

- **N1** (Opus, reproduced by Codex by changing `skills-ref`'s pin from
  `0.1.0` to `0.1.1`): a repository with no GitHub releases or tags at all
  (`upstream.latest` is `None` on both sides) has real fetch data --
  `upstream.pushed_at` is set -- and 7 such rows already exist in
  `catalogs/sota-convergence/manifest-20260922.json` (`tavily-cli`,
  `skills-ref`, `poppler`, and 4 others). A pin bump on one of these was
  silently invisible to the drift report.
- **N2** (Opus, reproduced by Codex with a synthetic `503` on the releases
  endpoint followed by a successful tags-endpoint fallback): when a
  repository's releases fetch fails but its tags fetch succeeds,
  `github_freshness.py` records the failure in `partial_errors` but still
  populates `upstream.latest` from the tag fallback. The prior code treated
  this as ordinary, reliable data (since `latest` was not `None`), so a
  transient-failure-derived value could silently read as either drift or a
  clean match.

Fixed by giving `compute_drift()` three buckets instead of two -- `drifted`,
`unfetched`, `no_release` -- documented in that function's own docstring and
in `docs/github-automation.md`. `pin` is now compared for every fetched row regardless of
`latest` (a row moved to `unfetched` is reported, not compared). A row is `unfetched` only when the rebuilt row lacks fetch
evidence (`upstream.pushed_at is None`) *or* its raw `github-freshness.json`
record shows a fetch problem (`error` or `partial_errors`, matched by exact
URL or normalized GitHub slug -- `_freshness_record_has_error()`, mirroring
`build_manifest.py`'s own `compute_upstream()` matching, independently
reimplemented for the same reason that module's own copy is independent of
`github_freshness.py`'s). Everything else with a known `latest` of `None` on
both sides is `no_release`: fetched reliably, genuinely has no release/tag,
not drift.

**N2 (job-level gate): `partial_errors` was not gated at all.** Per-row
exclusion (above) keeps a single flaky repository's row out of the drift
table, but nothing previously stopped `propose` from opening a PR when
*any* repository had a partial fetch problem this run. `freshness` now also
emits a `partial_errors` job output (`scripts/freshness_propose.py`'s
`upstream_partial_error_count()`, reading the same top-level count
`github_freshness.py` already writes), and `propose`'s `if:` requires
`needs.freshness.outputs.partial_errors == '0'` alongside the existing
`upstream_errors == '0'` check.

**N2b: fail closed, not zero, on a missing/broken freshness document.** The
prior `upstream_error_count()` returned `0` (a false "no problems" signal)
when `github-freshness.json` was missing or malformed. `_load_freshness_document()`
now raises `FreshnessProposeError` in that case (missing file, unreadable,
not a JSON object, or a non-integer `errors`/`partial_errors` field),
covered by `tests/test_catalog_freshness_propose.py`'s
`LoadFreshnessDocumentTests`/`IntFieldTests` (or equivalent) fail-closed
tests.

**N3: the approval instructions and GITHUB_TOKEN quote were wrong/outdated.**
Corrected in `catalog-freshness.yml`, `docs/github-automation.md` and this
record: the current `GITHUB_TOKEN` docs phrase the exceptions as "...will
not create a new workflow run, with the following exceptions: ..." (not
"with the exception of ... will not create"), and the actual UI path to
approve a pending run is on the pull request itself -- the approval banner
in the merge box, selecting **"Approve workflows to run"** -- not the repository's Actions tab.
Runs left awaiting approval for more than 30 days are automatically
deleted (also now stated in the workflow's job summary and in
`docs/github-automation.md`).

**N4: an absolute `$RUNNER_TEMP` path was being written into committed
evidence.** `render_drift_markdown()` received the full rebuilt-manifest
path (`work_dir / "manifest-*.json"`, an absolute, host-specific path under
the runner's temp directory) and embedded it verbatim in `drift.md`, which
`propose` then commits. Fixed by passing only `rebuilt_path.name` (the
published-manifest path stays a safe, relative repository path and is kept
in full, since it is genuinely useful for a reader to click through).

**P2-3 (Codex): a pending opt-in run could be silently discarded.** The
first fix round's single workflow-level `${{ github.workflow }}`
concurrency group with `cancel-in-progress: false` relies on GitHub's
default concurrency `queue: single`: "at most one job or workflow run can
be `pending` in the concurrency group. When a new job or workflow run is
queued, any existing `pending` job or workflow run in the same group is
canceled and replaced" ([Control workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
fetched 2026-09-23). Sequence: an in-progress run, then a manual
`open_pr: true` dispatch queues behind it, then an ordinary scheduled
activation queues too -- and *replaces* the manual request's pending slot,
so the opt-in run never executes at all. `queue: max` ("up to 100 jobs or
workflow runs can be `pending`") is the documented fix, but is rejected by
this repository's pinned `actionlint` 1.7.12 (`unexpected key "queue" for
"concurrency" section` -- checked directly, not assumed) -- and `queue: max`
with `cancel-in-progress: true` is independently documented as a validation
error, which was never this workflow's combination anyway.

**Chosen fix:** move the concurrency group off the workflow level entirely
and onto the `propose` job only (`freshness` reads/reports only and is safe
to run in parallel across overlapping triggers), keyed on manual vs.
scheduled: `${{ github.workflow }}-propose-${{ inputs.open_pr == true &&
'manual' || 'scheduled' }}`. A manual and a scheduled run are now in
different groups and can never replace each other's pending slot; two runs
*within* the same category can still replace each other, an accepted,
lower-stakes loss (the later same-category request already supersedes the
earlier one, and a lost duplicate report-only run is not a lost user
request). This reintroduces the possibility that a manual and a scheduled
run execute `propose` concurrently in the rare case both are triggered
close together -- `--force-with-lease` (already in place from the first fix
round) is the actual data-safety guard for that case; the concurrency group
is a queueing optimization, not the correctness mechanism. Alternatives
considered: keeping the workflow-level group and accepting the discard risk
(rejected -- silently dropping a human's explicit request is worse than the
now-only-theoretical concurrent-push race `--force-with-lease` already
covers); re-checking `queue` support on every future actionlint upgrade and
switching to it then (recorded as a live follow-up, not implemented, since
it is not needed for correctness once keyed-by-category queuing is in
place).

**Overturn condition (additive to the one above):** if a future actionlint
release (checked directly, not assumed) accepts the `queue` key, re-adopt
`queue: max` at the workflow level (simpler, and closes the residual
same-category replacement gap) and drop the per-job keying.

**Evidence class (second fix round):** `local_integration` / static
analysis only, same as above. `tests/test_catalog_freshness_propose.py`
gained regression tests for the exact N1 (`skills-ref`-style pin change with
`latest=None`) and N2 (`partial_errors`-with-tag-fallback) reproductions,
the N2b fail-closed behavior, the N4 relative-path fix, and a text-level
test asserting the job-scoped, category-keyed concurrency group. Full
`python3 -m unittest`, all validators, `zizmor`, `actionlint` and the
guarded `gitleaks` scans were re-run after this round; exact counts and
results are in the unit's final report.

## Codex verification of 7a483f7 (2026-09-23): two further corrections

- **A pin change on a row with unreliable upstream data was still hidden.** Codex's original repro (skills-ref 0.1.0 to 0.1.1 with no `pushed_at`) returned `drifted=[]` and `unfetched=['skills-ref']`. The pin comes from the local catalogs, not upstream, so `compute_drift` now reports a pin change as drift for every row. For a row whose fetch was unreliable, the fresh upstream fields are nulled and the row is also listed as unfetched. A regression test reproduces the original input exactly.
- **Overlapping manual and scheduled proposals could mismatch the PR description.** Run A pushes, then run B observes A's commit and pushes with a successful lease, then A overwrites the PR body with its older report. The PR step now compares the remote branch head with this run's pushed commit, and only the run that is still the head updates the description. A window of seconds remains between that check and `gh pr edit`. Serialising the push and PR update across both triggers would need a single concurrency group, which reintroduces pending-run displacement across categories, because the pinned actionlint rejects `concurrency.queue`. Overturn condition: an actionlint release that accepts `queue`, or an observed mismatched description.
- **Two pending manual requests can still replace each other** (GitHub's default single pending slot). This is accepted and documented: the later request supersedes the earlier one.

## Codex verification of 52d136a (2026-09-23): run-independent PR description

The branch-head check narrowed the overlap race without closing it. One ordering still leaves a mismatch: A checks the head, then B pushes and writes its body, then A writes its body. The check has therefore been removed. The PR description now embeds no run-specific report or receipt. It points at the evidence the branch head carries: the drift report and receipt in the PR's diff, with the run linked from the receipt. Overlapping manual and scheduled runs can no longer leave the description describing an older commit. The skip path and its misleading "PR opened" summary are gone with the check. The drift report wording now says that a pin change on an unfetched row is still listed as drift.
