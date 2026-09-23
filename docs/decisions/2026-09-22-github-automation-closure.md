# Decision: GitHub automation closure (2026-09-22)

**Decided by:** unit `catalog-automation`, an owned worktree of this
repository, branch `claude/github-automation-closure`, cut from `168a3a8` and
rebased on 2026-09-23 onto `origin/main` `8faca90` (after #96, #99-#104, #106).
Repository settings were applied by the coordinator on 2026-09-22 at about
23:35 EDT (2026-09-23 03:35 UTC), with before/after `gh api` GETs. This unit
changed files only. Timestamps from GitHub are UTC, so several fall on
2026-09-23.

**Scope:** the approved GitHub automation target for
`seathatflowsinourveins/native-agent-stack` (public, personal account). It
covers repository settings, a new `security-scan.yml`, gates in
`dependency-review.yml` and `supply-chain.yml`, Scorecard SARIF upload, a
Dependabot cooldown, a tag-only immutable release job in `publish-catalog.yml`,
the target main ruleset and the split tag rulesets.

**Supersedes:** "CodeQL is NOT activated" (`docs/github-automation.md`,
"Recorded decisions, 2026-09-22"; the `github/codeql-action` entry that was in
`catalogs/foundation/automation.json`'s `considered_not_activated`;
`docs/decisions/2026-09-22-actions-hardening.md`, "CodeQL default setup as a
substitute for Scorecard"), dependency review's `warn-only: true`, and the
grype threshold "pending" decision. **Keeps:** "Dependabot pip not
activated", now with the #97/#98 evidence below.

Primary sources were read on 2026-09-22. Documentation pages carry no date;
changelog dates are given where they exist.

## 1. Repository settings (applied by the coordinator)

| Setting | Before | After |
| --- | --- | --- |
| CodeQL default setup | `not-configured` | `configured`; `default` suite; weekly schedule. Fresh `gh api repos/seathatflowsinourveins/native-agent-stack/code-scanning/default-setup` at 2026-09-23T04:47:34Z: languages `actions`, `csharp`, `go`, `javascript`, `javascript-typescript`, `python`, `rust`, `typescript`, `query_suite: default`, `schedule: weekly`, `updated_at` 2026-09-23T04:40:46Z (an earlier GET at 04:24:29Z listed six languages without `go`/`rust`; the GET right after configuration showed `languages: []`, `schedule: null`); setup run 35815088202 (success, `168a3a8`); first-analysis alerts resolved in #104 ([record](2026-09-22-codeql-first-analysis.md)) |
| Dependabot security updates | `disabled` | `enabled` |
| Actions `sha_pinning_required` | `false` | `true` |
| Merge methods | merge, squash, rebase; no auto-merge; branches kept | squash only; `allow_auto_merge: true`; `delete_branch_on_merge: true` |
| Immutable releases | `enabled: false` | `enabled: true` |
| Private vulnerability reporting | enabled earlier on 2026-09-22 | `{"enabled":true}` (re-read 2026-09-23) |
| Secret scanning / push protection | enabled / enabled | unchanged; non-provider patterns and validity checks `disabled` |

- **Evidence.** CodeQL default setup is free for public repositories
  ([configuring default setup](https://docs.github.com/en/code-security/code-scanning/enabling-code-scanning/configuring-default-setup-for-code-scanning)),
  and its `actions` language has been GA since 2025-04-22
  ([changelog](https://github.blog/changelog/2025-04-22-github-actions-workflow-security-analysis-with-codeql-is-now-generally-available/)).
  Dependabot security updates are free
  ([about security updates](https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/about-dependabot-security-updates);
  uv support since [2025-12-16](https://github.blog/changelog/2025-12-16-dependabot-security-updates-now-support-uv/)).
  SHA-pinning enforcement shipped 2025-08-15
  ([changelog](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)).
  Immutable releases went GA on 2025-10-28
  ([changelog](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/)).
  Every `uses:` here was already SHA-pinned (`tests/test_workflow_hardening.py`
  `PinningTests`), so the enforcement changes no workflow.
- **Alternatives.** Keep the settings off. Keep merge commits and rebase.
- **Decision.** Keep the applied settings. Squash-only merging matches the
  existing `required_linear_history`. The target ruleset does **not** add
  `required_signatures` (keep-but-compare, section 10): the last 10 `main`
  commits are GitHub-signed squash merges (`verification.verified: true`,
  committer `GitHub`), but a measured run showed that this does not satisfy
  the rule for unsigned branch commits.
- **Overturn.** A required workflow that cannot be SHA-pinned; a merge that
  needs a merge commit; a release that needs mutable assets.

## 2. CodeQL default setup, compared with zizmor on the same commit

The previous decision rejected CodeQL for three reasons: `security-events:
write`, a floating bundle, and no served application. Default setup is a
repository setting. It needs no workflow here and no write scope on our jobs.
The bundle it runs is GitHub-managed (latest `codeql-bundle-v2.27.1`,
2026-09-22) and outside this repository's pins. The "no application" premise
was tested on this repository's first analysis.

The comparison ran on commit `168a3a8`: CodeQL default-setup analyses
1822610416, 1822611872, 1822612791 and 1822613119, with their SARIF read
through `gh api -H "Accept: application/sarif+json"`. zizmor 1.30.1 ran
locally with `GH_TOKEN` set and no `--offline`, using
`--no-config --no-ignores --persona regular --strict-collection` over
`.github/workflows`.

| Tool / scope | Rule | Results on `168a3a8` |
| --- | --- | --- |
| CodeQL `actions` (17 rules) | any | 0 |
| CodeQL `csharp` (52 rules) | any | 0 |
| CodeQL `javascript-typescript` (87 rules) | `js/xss-through-dom` | 2 (`docs/ecosystem/template.html` 145, 512) |
| CodeQL `python` (43 rules) | `py/bad-tag-filter` | 3 (`scripts/build_ecosystem.py`, `tests/test_claude_repository_evidence.py`, `tests/test_ecosystem_manifest.py`) |
| CodeQL `python` | `py/clear-text-storage-sensitive-data` | 1 (`tests/test_validate.py`) |
| CodeQL `python` | `py/clear-text-logging-sensitive-data` | 1 (`blueprints/convergence-practice/wsl-restore/run.py`) |
| CodeQL `python` | `py/incomplete-url-substring-sanitization` | 1 (`tests/test_lifecycle_capture.py`) |
| zizmor online, `regular` | any | 0 |
| zizmor online, `auditor` (comparison only) | `anonymous-definition` / `concurrency-limits` / `secrets-outside-env` | 21 / 7 / 3 |

- **What each tool uniquely catches.** CodeQL alone reports source-code
  findings: 8 on `168a3a8`, in Python and in the explorer template's
  JavaScript, a surface zizmor does not analyze. After `796f759`, the
  alert list (`/code-scanning/alerts?tool_name=CodeQL`) had 10 open alerts,
  all `high` security severity; Python rose to 8 results. zizmor alone reports
  the stricter-persona workflow findings that the 17-rule CodeQL `actions`
  suite did not report. At the gating levels (zizmor `regular`, CodeQL
  default suite), both returned 0 for workflows. The branch's workflows,
  including `security-scan.yml`, also return 0 online findings at `regular`.
- **Decision.** Keep CodeQL default setup, plus the target ruleset's
  `code_scanning` rule (`tool: CodeQL`, `security_alerts_threshold:
  high_or_higher`, `alerts_threshold: errors`), and keep zizmor. The 10
  first-analysis alerts were triaged and resolved in #104
  ([codeql-first-analysis](2026-09-22-codeql-first-analysis.md)); this unit
  neither dismissed nor fixed them.
- **Alternatives.** Advanced setup through a pinned `codeql-action/analyze`
  workflow (pins the action, not the bundle; adds a job with
  `security-events: write`). zizmor only (sees no source code).
- **Overturn.** Across the next 10 PRs, CodeQL raises no true positive beyond
  zizmor or the tests, or its PR analysis blocks merges without results.

## 3. `security-scan.yml`: OSV-Scanner

- **Tool.** OSV-Scanner v2.6.0 (latest, 2026-09-14). `osv-scanner_linux_amd64`
  SHA-256 `ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108`
  comes from the release's `osv-scanner_SHA256SUMS`. It is installed with
  `validate.yml`'s curl and `sha256sum --check` pattern.
- **Inventory.** `.github/osv-scanner-lockfiles.json` lists 37 lockfiles:
  `.github/requirements-ci.lock`, `adoption/sdk/*`, the application-delivery
  `pnpm-lock.yaml`/`uv.lock`, the us-equities `requirements*`, 23 NuGet
  `packages.lock.json` files (`alpaca.packages.lock.json` and the 22
  `lean-locks`) and both `tools/mlx-smoke` files. Names OSV cannot infer carry
  `requirements.txt` or `packages.lock.json` parsers (`--lockfile=<parser>:<path>`,
  [scan-source docs](https://github.com/google/osv-scanner/blob/v2.6.0/docs/scan-source.md)).
  `package.json` and `pyproject.toml` have no v2.6.0 source extractor
  ("could not determine extractor"), so they appear under
  `covered_by_lockfile` with their sibling lock. `tests/test_osv_lockfile_coverage.py`
  fails when a tracked lockfile is not listed. A negative control that
  deleted one entry failed as expected.
- **Excluded fixture (2026-09-23).** #101 added
  `blueprints/gap-wave2-20260923/grype-known-cve-fixture/requirements.txt`,
  a deliberately vulnerable positive control (`urllib3==1.26.4`, gap
  ci-supply-chain[13]) that `tests/test_grype_known_cve_fixture.py` requires
  grype to flag. Scanned on its own, OSV-Scanner 2.6.0 `--no-resolve` exits 1
  with 9 advisories (GHSA-q2q7-5pp4-w6pg and eight others). Nothing installs
  it, so it is listed under the inventory's `excluded` key with a reason and
  an evidence path instead of being ignored per advisory. The unit test
  accepts an exclusion only for a tracked lockfile, only with a non-empty
  reason naming a fixture and an existing evidence file, and never for a file
  that is also scanned; every other tracked lockfile still fails the test
  when unlisted. Negative controls: emptying `excluded` failed the coverage
  test on that path, and a reason without "fixture" failed the exclusion
  test. **Overturn:** the fixture becomes an installed dependency, or a second
  exclusion is proposed for a file that is not a test fixture.
- **`--no-resolve` (measured).** With transitive resolution, three unlocked
  manifests reported versions that no lockfile installs. OSV's resolver picked
  `httpx2`/`httpcore2` 2.9.1 (PyPI latest 2.13.0) and `six` 1.9.0 (latest
  1.17.0) for `blueprints/us-equities/workers/requirements.txt` (12 IDs),
  `idna` 3.9.0 for `adaptive-paper/requirements.txt` (2 IDs), and `requests`
  2.9.2 and `anyio` 4.9.0 for `tools/mlx-smoke/requirements.in` (22 IDs); the
  lock pins 2.34.2 and 4.15.1. With `--no-resolve` all three return 0, and every
  lockfile result is unchanged.
- **Base-commit result (`168a3a8`, `--no-resolve`, the CI command).** Exit 1.
  Of 37 files, 36 returned no vulnerability. One file had findings:
  `tools/mlx-smoke/requirements.lock.txt`, "2 packages affected by 6 known
  vulnerabilities (2 Critical, 4 High)". Those are mlx 0.29.3
  (PYSEC-2025-138, PYSEC-2025-139) and transformers 5.0.0rc1 (PYSEC-2026-2288,
  -2289, -2290, -3929). OSV filtered 175 local packages, exactly the 175 NuGet
  `"type": "Project"` entries. Package counts per file are in the unit's
  handoff. The six advisories are **not ignored**. The relock on
  `claude/mlx-smoke-security-20260923` (`0a40330`, merged as #99) scanned
  clean: its lock and `requirements.in` both returned exit 0.
- **Rebased-head result (2026-09-23, on `8faca90`).** The CI command over the
  37 listed lockfiles (the excluded fixture is not among them) exited 0,
  "No issues found", 175 local packages filtered. #99's relock of
  `tools/mlx-smoke` (mlx-lm 0.31.3) removed the six base-commit advisories.
- **Ignores.** None. `.github/osv-scanner.toml` documents the policy: `id`,
  a concrete `reason`, and `ignoreUntil` no more than 90 days away, all
  enforced by the unit test.
- **Triggers and permissions.** `pull_request` (no path filter), push to
  `main`, Wednesday `37 5 * * 3`, and dispatch. The PR run is the required
  check. Off PRs, the same scan writes SARIF, uploaded by
  `github/codeql-action/upload-sarif@1c5b675653bb5c22dbe9b12b556ec555138e09fd`
  (v4.38.1, annotated tag `c23de5a8…` dereferenced) with category
  `osv-scanner`. Only that job holds `security-events: write`. CodeQL Action
  v3 is deprecated in December 2026
  ([changelog](https://github.blog/changelog/2025-10-28-upcoming-deprecation-of-codeql-action-v3/)).
- **Alternatives.** Dependency review only (sees only a PR's changes). grype
  over every lock (it needs SBOMs per ecosystem). A separate upload job, which
  keeps `security-events: write` off the PR run but scans twice.
- **Overturn.** OSV-Scanner fixes its version ordering, so resolved results
  match a pip resolution of the same manifest (then drop `--no-resolve`). Or
  30 days of PR runs produce only findings that another required check also
  reports.

## 4. `security-scan.yml`: zizmor online

- **Evidence.** zizmor 1.30.1 (2026-09-09) is reused from
  `.github/requirements-ci.lock`. Online audits need a token
  ([usage](https://docs.zizmor.sh/usage/)). With `--format sarif`, findings exit
  0 locally; `--no-exit-codes` makes that explicit, so only an analyzer failure
  fails the job. It runs on push, schedule and dispatch, with `GH_TOKEN` from
  `github.token` through `env`, and uploads SARIF with category `zizmor`.
  `validate.yml`'s offline `regular` gate on every PR is unchanged.
- **Result.** 0 online findings on `168a3a8` and on this branch.
- **Overturn.** An online-only finding class (impostor commit, known-vulnerable
  action, ref-version mismatch) appears. Then it becomes a PR gate.

## 5. Scorecard SARIF

`scorecard.yml` keeps `publish_results: false` and the 5-day artifact. It now
also uploads `results.sarif` through the same `upload-sarif` SHA. Only the
`analysis` job has `security-events: write`. Scorecard v5.5.0 and
scorecard-action v2.4.4 are the latest releases. **Overturn:** duplicate or
noisy alerts that nobody triages for 30 days.

## 6. Dependency review gate

- **Evidence.** `warn-only: true` "overrid[es] `fail-on-severity`" (`action.yml`
  at `a1d282b3`). The graph has been on since the PR #78 correction. It passed
  on #97 and #98 (12-17 s).
- **Decision.** `fail-on-severity: high`, `warn-only` removed, and
  `dependency-review` is a required check in the target ruleset.
- **Overturn.** A high-severity block with no fix path that needs an
  allow-list (`allow-ghsas`) more than twice in 30 days.

## 7. grype threshold

- **Evidence.** The latest successful run, 35799579095 (push, `8889cf0`), was
  downloaded with `gh run download`. Its `grype-findings.json` had 0 Critical,
  0 High, 5 Medium and 1 Low. All six are in pip 25.0.1 (GHSA-4xh5-x5gv-qwph,
  GHSA-wf93-45jw-7689, GHSA-qwm4-qh6w-59xr, GHSA-jp4c-xjxw-mgf9 and
  GHSA-58qw-9mgm-455v are Medium; GHSA-6vgw-5pg2-w6jp is Low), the venv's
  seeded installer and not a runtime dependency. Local grype 0.119.0 on the
  same SBOM and DB (v6.1.9, built 2026-09-22T06:30:41Z) with
  `--config .grype.yaml --fail-on high` exited 0. A negative control with
  `--fail-on medium` exited 2. The ignore-rule fields come from `grype config`
  at 0.119.0.
- **Decision.** `--fail-on high` with a reviewed `.grype.yaml`. **Ignores: none**
  (every match is below the gate). Re-review by 2026-12-21. The scan now runs
  `grype db update` and `db status` before the gated scan, so the status file
  exists when the gate fails. `.grype.yaml` is in the workflow's `push` and
  `pull_request` path filters (asserted by `tests/test_workflow_hardening.py`
  `SupplyChainGateTests`), so a PR that changes an ignore rule runs the gate.
- **Alternatives.** Stay report-only. Gate at medium, which would fail today
  on the seeded pip that no runtime uses.
- **Overturn.** A High that is unreachable in this venv. Add a scoped
  `.grype.yaml` rule and list it here.

## 8. Dependabot: cooldown and pip

- **Cooldown.** `cooldown: default-days: 7` for `github-actions`, the key names
  from the Dependabot options reference and agent-lab's file
  ([2025-07-01](https://github.blog/changelog/2025-07-01-dependabot-supports-configuration-of-a-minimum-package-age/);
  the [2026-07-14 default](https://github.blog/changelog/2026-07-14-dependabot-version-updates-introduce-default-package-cooldown/)
  is 3 days). The weekly schedule was observed in run 35583086998 (Monday
  2026-09-21 09:24 UTC, success, no PR). A nonempty group is still unobserved.
- **pip stays off (kept, with new evidence).** Security updates opened #97
  (mlx 0.29.3 -> 0.29.4) and #98 (transformers 5.0.0rc1 -> 5.10.1) within
  minutes. In `gh pr checks 97` and `98`, validate, secret-scan, token-report,
  dependency-review, linux-profile and both Socket checks passed. `macos-profile`
  failed (runs 35815152321 and 35815162857) in the "Verify the hash-locked
  mlx-lm requirements resolve for this platform" diff. The lock is
  uv-compiled with hashes and an `--exclude-newer` cutoff, and a single-package
  bump does not reproduce it. The reviewed relock (#99) fixed the advisories.
  Both PRs are closed.
- **Redundant mlx branch dropped.** This unit's own mlx relock branch was not
  integrated because #99 landed the same fix first. A read-only
  `gh api .../dependabot/alerts` at 2026-09-23T04:47:34Z shows alerts 1-6
  (`tools/mlx-smoke/requirements.lock.txt`) `fixed` at 03:47:28-03:47:30Z and
  0 open alerts: 6 -> 0 after #99.
- **Fixture alerts dismissed.** Alerts 7-15, all on the #101 positive-control
  fixture `blueprints/gap-wave2-20260923/grype-known-cve-fixture/requirements.txt`,
  were dismissed by the coordinator as `not_used`, and Dependabot PR #105
  ("Bump urllib3 from 1.26.4 to 2.7.0", closed 2026-09-23T04:40:57Z) was
  closed: upgrading urllib3 would destroy the fixture's purpose, and nothing
  installs the file (same reason as the OSV exclusion in section 3).
- **Fixture kept out of future security PRs.** `.github/dependabot.yml` adds a
  pip entry scoped to the fixture directory with `open-pull-requests-limit: 0`
  and `ignore: urllib3`. The Dependabot options reference (read 2026-09-23)
  marks `ignore` as also applying to security updates, while `exclude-paths`
  and the PR limit apply to version updates only. New advisories still raise
  alerts on the fixture; those are dismissed `not_used`. Requested by the
  gap-resolution session that owns the fixture.
- **Security updates stay on.** Dependabot security updates are free, gave the
  fastest signal here (#97/#98 within minutes of enabling), and auto-close
  their alerts when a fix lands (alerts 1-6 closed on #99's merge). The cost is
  a PR that fails `macos-profile` on a hash-locked uv lock and must be closed
  by hand. **Overturn:** recurring unfixable security-update PRs (more than
  two in 30 days that must be closed without merging for a reason other than
  a fixture).
- **Overturn.** A Dependabot pip or uv PR passes the recompile-and-diff check on
  a real lock.

## 9. Tag-only immutable release

- **Evidence.** In gh v2.101.0 (`pkg/cmd/release/create/create.go`, lines
  497-559, ref `v2.101.0`), `create` with files and without `--draft`
  sets `draft: true`, uploads, publishes, and deletes the draft if an upload
  fails. The command help says immutability applies only after publish.
  `--verify-tag` aborts if the tag is missing. Immutable releases reject
  assets added after publish, so the files are attached at creation.
- **Design.** A `release` job, `needs: publish`, only for `refs/tags/v*`, with
  job permissions `contents: write` only. It downloads the two artifacts by
  the IDs the publish job output (`actions/download-artifact@3e5f45b2…`
  v8.0.1, `digest-mismatch: error`), re-checks each with `sha256sum --check
  --strict` against the SHA-256 the publish job attested, and runs
  `gh release create "$tag" archive sbom --verify-tag`. It then requires
  `isDraft == false`, `isImmutable == true` and exactly two assets with those
  digests. The notes carry `gh attestation verify` for both files and
  `gh release verify-asset`.
- **Result.** Local simulation only: note rendering, a two-file
  `sha256sum --check --strict`, and the jq assertion (pass on matching
  digests, fail on a changed one). No hosted tag run yet.
- **Alternatives.** Explicit `--draft`, `gh release upload`, then
  `gh release edit --draft=false`: equivalent, more steps, and no automatic
  cleanup. Attaching assets after publish is impossible under immutability.
- **Overturn.** A hosted tag run publishes without both assets, or gh changes
  the sequencing.

## 10. Rulesets

- `.github/tag-ruleset.json` equals live 23829417 (`deletion`,
  `non_fast_forward`, `update`; no bypass). `.github/tag-creation-ruleset.json`
  equals live 23859358 (`creation`; bypass `RepositoryRole` 5 `always`). Both
  were compared field by field after stripping the server fields.
- `.github/main-ruleset.json` is the **target** for 23739774. It keeps the live
  rules, including the server defaults `required_reviewers: []` and
  `require_extra_approval_for_unattributed_changes: true`. It adds
  `dependency-review` and `osv-scanner` (integration 15368), keeps
  `strict_required_status_checks_policy: false` (see below), and adds `code_scanning`
  (CodeQL, `high_or_higher`, `errors`) and `allowed_merge_methods:
  ["squash"]`. The coordinator applies it after merge
  ([available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)).
- **Overturn.** The `code_scanning` rule blocks a PR that introduces no alert.
- **Strict up-to-date checks: off (2026-09-23).** An earlier draft set
  `strict_required_status_checks_policy: true`. With auto-merge on and no
  merge queue (unavailable for personal repositories, section 11), strict
  mode makes every open PR stall on a manual branch update whenever `main`
  moves, and this host runs many concurrent PR sessions (#96 and #99-#104,
  seven PRs, merged between 03:41 and 04:42 UTC on 2026-09-23 while this
  change was open, per `gh pr list --state merged`). No `main`
  failure has been traced to merge skew; every required check still runs on
  each PR and on push to `main`. **Alternatives:** strict on (serializes
  merges by hand); a merge queue (unavailable). **Overturn:** a `main` failure
  traced to two PRs merging close together.
- **`can_approve_pull_request_reviews`** (the Actions workflow-permissions
  setting) is owned by another session's #95 and is deliberately not part of
  this target; this change neither reads nor sets it.
- **`required_signatures`: not in the target (keep-but-compare, 2026-09-23).**
  An earlier draft of this change added it because every `main` commit is a
  GitHub-signed squash merge. The coordinator measured the rule on agent-lab
  (2026-09-23T04:00Z): PRs #19 and #20, each with one unsigned branch commit,
  green checks and 0 unresolved threads, were `BLOCKED` under ruleset 23859430
  with `required_signatures`; removing only that rule made both `CLEAN` within
  8 s. A GitHub-signed squash merge therefore does not satisfy the rule for
  unsigned branch commits. This change's own commits are unsigned, and no
  writer worktree sets `commit.gpgsign` or `gpg.format`, so applying the rule
  would block every agent-authored PR. **Alternatives:** apply it now (blocks
  every current writer); apply it after every writer signs (a registered SSH
  signing key plus `commit.gpgsign=true` in each worktree). **Overturn:** add
  the rule once a signed-commit workflow is set up for every writer and one
  signed PR is observed to merge under it. The measurement is the
  coordinator's `required-signatures-finding.txt` (2026-09-23T04:00Z) with
  the before/after ruleset GETs for agent-lab ruleset 23859430.

## 11. Recorded non-adoptions and verdicts

- **Socket Security app:** free and advisory. Its "Project Report" and "Pull
  Request Alerts" checks passed on #97 and #98. It is not required.
  **Overturn:** remove it if its PR alerts add nothing beyond
  dependency-review across the next 10 PRs.
- **harden-runner stays audit** on 18 of 22 ubuntu jobs; the other 4 are
  hash-frozen exemptions. Block mode needs a per-job allow-list backed by
  audit runs.
- **Renovate stays deferred.** No custom-manager gap is shown; Mend's hosted
  app is free, but it would duplicate Dependabot's ownership
  ([comparison](https://docs.renovatebot.com/bot-comparison/)).
- **Merge queue is unavailable.** It needs an organization-owned public
  repository or Enterprise Cloud
  ([docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)).
- **Non-provider secret patterns and validity checks are not free** (Secret
  Protection is $19 per committer per month, Team or Enterprise only;
  [2025-03-04](https://github.blog/changelog/2025-03-04-introducing-github-secret-protection-and-github-code-security/)).
  gitleaks `secret-scan` stays the required gate.
- **SaaS verdict: none needed.** Every selected control is free for this public
  repository. No paid plan, hosted scanner or external service is adopted.

## 12. Catalog rows and the gap ledger (2026-09-23)

An earlier draft appended "Update 2026-09-22" sentences to four
`ci-supply-chain` `open_gaps` entries in `catalogs/landscape/foundation.json`
(gaps 2, 4, 5 and 6 in [the crosswalk](../gap-crosswalk-92bb279.md) numbering).
`open_gaps` is lane-recorded text, and the landscape row schema
(`scripts/landscape.py`) has no field for a resolved or superseded gap, so the
lane text is restored verbatim and the resolution is recorded here and in the
gap ledgers instead:

- **Gap 2 (no hosted `sbom-vuln` run ID)** and **gap 5 (offline zizmor misses
  online audits)** are already recorded as `advanced` in the wave-2 ledger
  [`catalogs/landscape/gap-wave2-20260923--gap-resolution.json`](../../catalogs/landscape/gap-wave2-20260923--gap-resolution.json)
  (receipts `supply-chain-hosted-run-and-wider-syft` and `zizmor-online-audit`).
  That zizmor receipt found `known-vulnerable-actions` did not fire on a known
  compromised action, so this change's `zizmor-online` job does not settle gap 5.
- **Gap 4 (Dependabot timing and grouping)** is `time_gated` and **gap 6 (no
  vulnerability threshold policy)** is `needs_user_decision` in the crosswalk;
  `tools/sota-convergence/gap_wave_ledger.py` tracks only `executable_now`
  gaps, so neither has a ledger row. Their resolution is sections 7-8 above:
  the weekly run is observed with no nonempty group, and the threshold policy
  is committed (grype `--fail-on high`, dependency review `high`, OSV-Scanner
  on every listed lockfile) with no hosted gate run yet. Both stay open in the
  row until a re-record.
- The rows' `catalogs/foundation/automation.json line N` citations went stale
  when this change edited that file. They now name the entry by JSON path at
  the row's recording revision, for example
  `catalogs/foundation/automation.json@92bb279 considered_not_activated[repository=github/codeql-action].decision`
  (the cited entries start at the same line numbers at `92bb279` and
  `168a3a8`). Their
  `docs/github-automation.md lines N` citations are left unchanged: several did
  not match that file even at `92bb279`, so they predate this change and need
  the lane's own source revision to repair.
- `catalogs/sota-convergence/layer-verdicts-20260922.json` and the handbook's
  generated verdict section were regenerated with
  `python3 tools/sota-convergence/build_verdicts.py --write`, then `--check`.
- `catalogs/foundation/automation.json` now keeps gating lanes (`sbom-vuln`,
  `osv-scanner`, `dependency-review`) in `security_gate_lanes`, each with a
  boolean `required_check` (the live state) and `target_required_check` (the
  target ruleset). `scheduled_report_only_lanes` keeps only lanes that do not
  fail on findings.

## Evidence class

`documented_api_check` covers the settings, ruleset, alert, run and PR GETs.
`local_static_analysis` covers actionlint 1.7.12, offline zizmor and the unit
tests. `local_native_run` covers OSV-Scanner 2.6.0 and grype 0.119.0 on the
recorded inputs and the online zizmor run. The hosted CodeQL analyses of
`168a3a8` are GitHub's own runs. No hosted run of `security-scan.yml`, the
Scorecard upload, the dependency-review gate on a failing PR or the release
job exists yet. They follow merge and the next `v*` tag.
