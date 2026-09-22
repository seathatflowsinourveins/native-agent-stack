# Decision: report-only GitHub Actions security hardening (2026-09-22)

**Decided by:** unit `actions-hardening`, an owned worktree checkout of this
repository, branch `claude/gap-actions-hardening-20260922`, base commit
`bdd04ca`.

**Scope:** three new/changed GitHub Actions lanes on
`seathatflowsinourveins/native-agent-stack`: `.github/workflows/scorecard.yml`
(new), `.github/workflows/dependency-review.yml` (new), and a
`step-security/harden-runner` first step added to five existing jobs
(`validate` in `validate.yml`, `sbom-vuln` in `supply-chain.yml`, `publish`
in `publish-catalog.yml`, `freshness` in `catalog-freshness.yml`, and
`bootstrap-linux` in `adoption-bootstrap.yml`). All three lanes are
report-only: none is added to `required_status_checks`, none blocks a merge
by itself.

## Decision

### 1. OpenSSF Scorecard (`scorecard.yml`)

Adopt `ossf/scorecard-action`, pinned to the full commit SHA of `v2.4.4`.

- **SHA verification.** `gh api repos/ossf/scorecard-action/git/ref/tags/v2.4.4`
  returned an annotated-tag object
  (`{"object":{"sha":"55891bbd73f2425e97637d96e306fc9d491d0b21","type":"tag"}}`).
  Annotated tags point at a tag object, not a commit, so it was dereferenced
  with `gh api repos/ossf/scorecard-action/git/tags/55891bbd73f2425e97637d96e306fc9d491d0b21`,
  which returned `{"object":{"sha":"2d1146689b8cda280b9bc96326124645441f03bc","type":"commit"},"tag":"v2.4.4"}`.
  The workflow pins `ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc # v2.4.4`.
- **Trigger.** Weekly schedule (`13 5 * * 1`), `workflow_dispatch`, and push
  to `main` -- matching the task's required event set. (Upstream's own
  README, read at the pinned SHA via
  `gh api repos/ossf/scorecard-action/contents/README.md?ref=<sha>`, notes
  `pull_request` and `workflow_dispatch` are "experimental" and forks are
  unsupported; `pull_request` was therefore not added.)
- **Publication.** `publish_results: false` -- this run's results are never
  published to the public `api.scorecard.dev` dataset or badge, and
  `id-token: write` (required only for `publish_results: true`, per the
  pinned README's "Breaking changes in v2" section) is not requested.
- **Permissions.** `contents: read` at the workflow top level and again at
  job level; no `security-events: write` and no GitHub Advanced Security
  dependency. The pinned README's "Additional permissions for private
  repositories" block (`security-events: write`, `id-token: write`,
  `issues: read`, `pull-requests: read`, `checks: read`) is documented as
  needed only for **private** repositories or when publishing; this
  repository is public (see check 3 below), so it is not applied.
- **Results.** Written as `results.sarif` and uploaded only as a workflow
  artifact (`actions/upload-artifact`, already pinned at the SHA this
  repository's other workflows use); never routed to `github/codeql-action/upload-sarif`
  or the Security tab, so no code-scanning alert surface is created.

### 2. `step-security/harden-runner`, audit mode

Add `step-security/harden-runner` as the literal first step (before
`actions/checkout`) with `egress-policy: audit` to every `ubuntu-24.04` job
that downloads binaries or packages:

| Job | Workflow | Downloads |
| --- | --- | --- |
| `validate` | `validate.yml` | pinned pip CI-analyzer wheels, actionlint tarball |
| `sbom-vuln` | `supply-chain.yml` | pip wheels (nautilus_trader et al.), syft, grype |
| `publish` | `publish-catalog.yml` | syft |
| `freshness` | `catalog-freshness.yml` | `gh api` calls, pip |
| `bootstrap-linux` | `adoption-bootstrap.yml` | `adoption/bootstrap-linux.sh`'s pinned downloads |

- **SHA verification.** `gh api repos/step-security/harden-runner/releases/latest`
  returned `tag_name: v2.21.1`; `gh api repos/step-security/harden-runner/git/ref/tags/v2.21.1`
  returned a commit-typed ref directly:
  `{"object":{"sha":"e14015d583714f6e62063499dc959a02595150a1","type":"commit"}}`.
  The workflows pin `step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 # v2.21.1`.
  `action.yml` at that SHA (`gh api
  repos/step-security/harden-runner/contents/action.yml?ref=<sha>`) confirms
  `egress-policy` defaults to `block` and accepts `audit`; no extra
  permission (e.g. `id-token: write`) is needed for plain `egress-policy:
  audit` -- that is only required by the separate `policy:` policy-store
  input, which is not used here.
- **Mode.** `audit`, never `block`. Audit mode only logs observed egress
  destinations; per `action.yml`'s own description it cannot fail a step or
  block a network call, so this change cannot alter any job's existing
  pass/fail result -- consistent with "report-only" for this unit.
- **Excluded jobs.** `secret-scan` (`validate.yml`) and `bootstrap-macos`
  (`adoption-bootstrap.yml`) are outside the task's named job list;
  `bootstrap-macos` also runs on `macos-15`, which `harden-runner` does not
  support (Linux-only network-egress monitoring). Not adding it there is a
  platform limitation, not an oversight.

### 3. `actions/dependency-review-action` (`dependency-review.yml`)

Adopt `actions/dependency-review-action`, pinned to the full commit SHA of
its latest release `v5.0.0`, on `pull_request` only, `warn-only: true`,
`contents: read`, not added to `required_status_checks`.

- **SHA verification.** `gh api repos/actions/dependency-review-action/releases/latest`
  returned `tag_name: v5.0.0`; `gh api
  repos/actions/dependency-review-action/git/ref/tags/v5.0.0` returned a
  commit-typed ref directly:
  `{"object":{"sha":"a1d282b36b6f3519aa1f3fc636f609c47dddb294","type":"commit"}}`.
  The workflow pins `actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0`.
- **Repository-visibility precondition (checked before adopting).**
  `gh api repos/seathatflowsinourveins/native-agent-stack --jq .visibility`
  returned `public`. Because the repository is public, the private-repo
  conditional in this unit's task ("if it is private and the dependency
  graph or Advanced Security is not enabled, do NOT add dependency review")
  does not apply: GitHub enables the dependency graph automatically and
  without charge for all public repositories, and
  `dependency-review-action` reads it through the standard dependency-graph
  API with no GitHub Advanced Security requirement. For completeness the
  `security_and_analysis` block was still read:
  `gh api repos/seathatflowsinourveins/native-agent-stack --jq
  .security_and_analysis` returned
  `{"dependabot_security_updates":{"status":"disabled"},"secret_scanning":{"status":"enabled"},"secret_scanning_non_provider_patterns":{"status":"disabled"},"secret_scanning_push_protection":{"status":"enabled"},"secret_scanning_validity_checks":{"status":"disabled"}}`
  (this endpoint does not itself surface a `dependency_graph` field for a
  public repo, because there is nothing to toggle). Had the repository been
  private with no dependency graph or Advanced Security, this section would
  instead record that finding and withhold the workflow.
- **Correction from the first hosted run (2026-09-22, coordinator).** The
  premise above was wrong for this repository: on PR #78 the job failed in
  7 s with `Dependency review is not supported on this repository. Please
  ensure that Dependency graph is enabled` (run 35797766463), and
  `gh api repos/seathatflowsinourveins/native-agent-stack/dependency-graph/sbom`
  returned 404, so the graph was off despite public visibility.
  It was enabled with `gh api -X PUT
  repos/seathatflowsinourveins/native-agent-stack/vulnerability-alerts`
  (HTTP 204; this also turns on Dependabot alerts; rollback is the same path
  with `-X DELETE`). The SBOM export then listed 60 packages, and the re-run
  job succeeded ("did not detect any vulnerable packages with severity level
  \"low\" or higher"; no denied licenses).
- **Scope.** `pull_request` trigger only (no `push`); `warn-only: true`
  means the job "will always complete with success, overriding
  `fail-on-severity`" (per `action.yml`'s own input description read at the
  pinned SHA); it is not listed in `main-ruleset.json`'s or the applied
  ruleset's `required_status_checks` (`validate`, `token-report`,
  `secret-scan` only -- see the stale-statement correction below), so a
  failing or skipped run of this job cannot block a merge.

### Correcting a stale statement in `docs/github-automation.md`

`docs/github-automation.md`'s "Secret and supply-chain scanning, 2026-09-22"
section said `secret-scan` "is not yet a required check in the *active,
applied* branch-protection ruleset." Re-checked for this decision:
`gh api repos/seathatflowsinourveins/native-agent-stack/rules/branches/main`
returns a `required_status_checks` rule (ruleset id `23739774`) whose
`required_status_checks` array is
`[{"context":"validate",...},{"context":"token-report",...},{"context":"secret-scan",...}]`.
That statement was stale against the same document's later "Ruleset upgrade,
2026-09-22" section, which already records the 2026-09-22 application of
this ruleset. The stale sentence is corrected in place (see
`docs/github-automation.md`'s updated "Secret and supply-chain scanning"
section); no ruleset API call that changes repository settings was made by
this unit.

## Alternatives considered

- **`publish_results: true` for Scorecard, with a public badge.** Rejected
  for this batch: it requires `id-token: write` and replaces the OSSF team's
  own weekly public scan of this repository with a self-reported one; the
  task asked for a report-only artifact, not a public badge/API commitment.
- **`harden-runner` in `block` mode with an explicit allow-list.** Rejected
  for this batch: block mode requires enumerating every legitimate egress
  endpoint per job (PyPI, GitHub Releases CDN mirrors, `gh api`, etc.) and a
  wrong or incomplete allow-list would turn a report-only hardening change
  into a job-breaking one; the task explicitly specified audit mode.
- **Adding `dependency-review-action` to `required_status_checks` or as a
  `push`-triggered job.** Rejected: the task specifies warn-only and
  pull-request-only, and a required dependency-review check with no severity
  threshold set (`fail-on-severity` was intentionally left unset here) would
  not gate anything meaningful yet.
- **CodeQL default setup as a substitute for Scorecard.** Out of scope for
  this decision and already rejected in this same document's "Recorded
  decisions, 2026-09-22" section (`security-events: write` requirement, no
  served application surface); not revisited here.

## Evidence that would overturn this decision

- **Scorecard:** a future need for the public Scorecard badge/REST API
  (`publish_results: true`) or a demonstrated false-negative gap in the
  `contents: read`-only permission set (e.g. a check that always errors
  without `issues: read`/`pull-requests: read`/`checks: read` even on a
  public repository) would justify adding those job-level permissions.
- **`harden-runner`:** an observed, actionable set of unexpected outbound
  destinations across several audit-mode runs would justify moving one or
  more of these jobs to `egress-policy: block` with an explicit allow-list.
- **`dependency-review-action`:** the repository becoming private, or its
  dependency graph/Advanced Security being disabled, would require removing
  or re-scoping this workflow per the same conditional; a decision to gate
  merges on dependency findings would require setting `fail-on-severity`
  and adding the check to `required_status_checks` as a separate, explicit
  decision.

## Correction, fix round 2026-09-22 (later same day)

A review of this branch (commit `90ce605`) found the "Excluded jobs" note
above stale in the same way section 3's correction found
`docs/github-automation.md` stale: it read the task's job list as exhaustive
rather than as the jobs actually covered so far. `secret-scan`
(`validate.yml`) downloads and runs an unauthenticated binary (the gitleaks
release tarball) and is also a required check, so it is a stronger case for
`egress-policy: audit` than several jobs already covered, not a weaker one.
This branch's fix round (see
[`docs/decisions/2026-09-22-actions-hardening-fix-round.md`](2026-09-22-actions-hardening-fix-round.md))
adds `harden-runner` to `secret-scan` plus three more downloading jobs found
during that review (`python` and `go` in `action-compatibility.yml` and
`nautilus-offline-replay` in `native-foundation-e2e.yml`) that were never
covered by this original decision, not because they were newly added by it.
`bootstrap-macos` remains excluded for the unchanged platform-support
reason. That fix round also tried and reverted the same step on `source`
(`native-offhost-app-state.yml`) after it broke a frozen-source-hash test,
and records `source`, `destination`, `synthetic-restore`, and
`owned-guest-reboot` as an out-of-bounded-scope gap for a later decision.

## Evidence class

`local_static_analysis` for the workflow syntax/security checks
(`zizmor --offline --no-config --no-ignores --persona regular
--strict-collection .github/workflows` reported "No findings to report" for
all 14 workflow files including the two new ones; `actionlint` at the
repository's pinned `v1.7.12` reported no findings). `documented_api_check`
for the three `gh api` lookups quoted above (tag/release SHA resolution,
repository visibility, `security_and_analysis`, and the applied ruleset's
`required_status_checks`) -- each is a read-only GitHub API call, not a
hosted workflow run; no `scorecard.yml`, `dependency-review.yml`, or
`harden-runner`-added step has executed on GitHub Actions yet, so their
actual hosted behavior (Scorecard's computed score, harden-runner's audit
log contents, dependency-review's PR comment) remains unobserved until the
first hosted run after integration.
