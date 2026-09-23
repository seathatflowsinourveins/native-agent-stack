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
  check. Off PRs, the same scan writes SARIF, which the job keeps as a 1-day
  artifact; the separate `osv-sarif-upload` job (`needs: osv-scanner`,
  `!cancelled()` so a findings failure still uploads) downloads it and uploads
  it with `github/codeql-action/upload-sarif@1c5b675653bb5c22dbe9b12b556ec555138e09fd`
  (v4.38.1, annotated tag `c23de5a8…` dereferenced), category `osv-scanner`.
  CodeQL Action v3 is deprecated in December 2026
  ([changelog](https://github.blog/changelog/2025-10-28-upcoming-deprecation-of-codeql-action-v3/)).
- **Write scope (2026-09-23 split).** Until this change the `osv-scanner` job
  itself held `security-events: write`, so the token that can dismiss the
  CodeQL alerts gated by the `code_scanning` rule was present in the job that
  runs the curl-installed OSV-Scanner binary on every event, PRs included
  (job-level permissions apply whether or not the upload step runs). It was
  never the only holder: `git show <c>:.github/workflows/security-scan.yml |
  grep -c 'security-events: write'` returns 2 at `e4737e5`, `da000f8`,
  `ad72b16`, `4e4aab0` and the squash merge `4970ba0` (`zizmor-online`, later
  `zizmor-sarif-upload`, held it too). Now both scan jobs are `contents: read`,
  and the two upload jobs hold the write scope and run no shell step or
  installed tool (`tests/test_workflow_hardening.py`
  `test_the_write_token_never_reaches_an_installed_tool`). The split adds no
  scan: the job already ran `osv-scanner scan source` twice off PRs (the
  table run for the exit status, then `--format sarif`).
- **Alternatives.** Dependency review only (sees only a PR's changes). grype
  over every lock (it needs SBOMs per ecosystem). Keep the upload step inside
  the scan job (rejected on 2026-09-23: it leaves the write-scoped token in the
  job that runs the installed binary, which the zizmor split in section 4
  already rejected for the same reason, and splitting costs no extra scan).
- **Decision.** Scan in a read-only job; upload from a tool-free job.
- **Overturn.** GitHub adds step-scoped permissions, so the upload step alone
  can hold the write scope; or OSV-Scanner fixes its version ordering, so
  resolved results match a pip resolution of the same manifest (then drop
  `--no-resolve`); or 30 days of PR runs produce only findings that another
  required check also reports.

## 4. `security-scan.yml`: zizmor online

- **Evidence.** zizmor 1.30.1 (2026-09-09) is reused from
  `.github/requirements-ci.lock`. Online audits need a token
  ([usage](https://docs.zizmor.sh/usage/)). With `--format sarif`, findings exit
  0 locally; `--no-exit-codes` makes that explicit, so only an analyzer failure
  fails the job. It runs on push, schedule and dispatch, with `GH_TOKEN` from
  `github.token` through `env`, and uploads SARIF with category `zizmor`.
  `validate.yml`'s offline `regular` gate on every PR is unchanged.
- **Token split (2026-09-23 review).** zizmor runs in a `contents: read` job and
  hands its SARIF over as a 1-day artifact; a separate `zizmor-sarif-upload` job
  holds `security-events: write` and runs no shell step or installed tool (only
  harden-runner, checkout, download-artifact and upload-sarif, asserted by
  `tests/test_workflow_hardening.py`). A write-scoped token handed to a
  pip-installed analyzer could dismiss the CodeQL alerts that the target
  `code_scanning` rule gates on. Found by comparing this branch with an
  independently built alternative; an analyzer crash still skips the upload.
- **OSV failure path fixed (same review).** `shell: bash` implies `-e`, so the
  earlier `set -uo pipefail` let a findings exit (1) end the step before the
  SARIF run; code scanning would have received OSV results only when there were
  none. The step now uses `set +e -u -o pipefail`, captures the status, writes
  the SARIF and exits with the table run's status. Found independently by the
  alternative-branch comparison and the Codex cross-family review; reproduced
  with `bash --noprofile --norc -eo pipefail -c 'set -uo pipefail; false; echo reached'`
  (prints nothing) and guarded by a test assertion that fails if the old line returns.
- **Result.** 0 online findings on `168a3a8` and on this branch.
- **Alternatives.** Give `zizmor-online` the write scope directly (rejected:
  hands a pip-installed analyzer's token the power to dismiss CodeQL alerts,
  see "Token split" above). Run zizmor online as a PR gate (rejected: online
  audits need network egress and a token on every PR, and 0 findings on
  `168a3a8` give no evidence yet that it would not be noisy). Drop online
  zizmor and keep only `validate.yml`'s offline `regular` gate (rejected:
  offline analysis covers no online-only audit class, such as impostor
  commit, known-vulnerable action or ref-confusion checks that need the
  GitHub API and an advisory database; zizmor's secrets audits, such as
  `secrets-inherit`, `overprovisioned-secrets` and `unredacted-secrets`, are
  static and already run offline in `validate.yml`).
- **Decision.** Keep the two-job split: `zizmor-online` (`contents: read`,
  push/schedule/dispatch only) produces the SARIF artifact, and
  `zizmor-sarif-upload` (`security-events: write`, no shell step or
  installed tool) uploads it, per the "Token split" evidence above.
- **Overturn.** An online-only finding class (impostor commit, known-vulnerable
  action, ref-version mismatch) appears. Then it becomes a PR gate.

## 5. Scorecard SARIF

- **Evidence.** `scorecard.yml`'s `analysis` job runs
  `ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc` (v2.4.4,
  the latest release; Scorecard itself is at v5.5.0) with `results_format:
  sarif` and `publish_results: false`, then uploads `results.sarif` both as a
  5-day workflow artifact and, in the same job, through
  `github/codeql-action/upload-sarif@1c5b675653bb5c22dbe9b12b556ec555138e09fd`
  (v4.38.1). The upload step and its job-scoped `security-events: write` were
  added on `main` in commit `4970ba0` (PR #108). The layout matches the example
  that `ossf/scorecard-action`'s README (pinned SHA
  `2d1146689b8cda280b9bc96326124645441f03bc`, section "Workflow Example") links:
  `ossf/scorecard` `.github/workflows/scorecard-analysis.yml` at
  `d13ba3f3355b958d5d62edc47282a2e7ed9fa7c1`, where the action writes
  `results_file: results.sarif` and the same job, holding `security-events:
  write`, uploads it with `github/codeql-action/upload-sarif`. The README's
  Inputs table (`results_file`, `results_format`) and its list of approved
  steps say the same, and its private-repository snippet marks
  `security-events: write` as "Required when publishing results (badge / API /
  code scanning)". Observed upload: `gh api --paginate
  "repos/seathatflowsinourveins/native-agent-stack/code-scanning/analyses?ref=refs/heads/main&per_page=100"`
  lists Scorecard analyses for commit `4970ba0`: `supply-chain/branch-protection`
  (1 result, analysis 1823007546), `supply-chain/local` (5, 1823007605) and
  `supply-chain/online-scm` (3, 1823007675), with `osv-scanner` (0, 1823007099)
  and `zizmor` (0, 1823008464) on the same commit, read 2026-09-23. `analysis` is the only job in
  the workflow and the only one with `security-events: write`
  (`tests/test_workflow_hardening.py` `ScorecardTests`). Unlike the two
  security-scan uploads, it is not split: `ossf/scorecard-action` itself takes
  `repo_token` (default `github.token`) in that job, as its upstream layout
  prescribes; a split would need the action to run in a read-only job, which
  its README does not document. **Keep-but-compare:** measured comparison is a
  dispatch run with the action in a `contents: read` job plus a separate upload
  job; if it produces the same analyses, split it.
- **Alternatives.** Set `publish_results: true` (rejected: publishes to the
  public `api.scorecard.dev` dataset and badge, which this unit's scope
  keeps off). Keep the artifact only, with no code-scanning upload (rejected:
  findings would sit in a 5-day artifact nobody is required to open, instead
  of surfacing next to CodeQL/OSV/zizmor alerts).
- **Decision.** Keep `publish_results: false` and the 5-day artifact, and add
  the code-scanning upload in the same job that already ran Scorecard so no
  second run or separate job is needed.
- **Overturn.** Duplicate or noisy alerts that nobody triages for 30 days.

## 6. Dependency review gate

- **Evidence.** `warn-only: true` "overrid[es] `fail-on-severity`" (`action.yml`
  at `a1d282b3`). The graph has been on since the PR #78 correction. It passed
  on #97 and #98 (12-17 s).
- **Alternatives.** Keep `warn-only: true` and report-only status (rejected:
  the graph correction removed the only blocker to gating, and a report-only
  advisory scan that nobody must act on does not close the gap). Gate at
  `critical` instead of `high` (rejected: leaves high-severity advisories
  with a fix available unblocked; #97 and #98 are the only measured samples
  of the gate running at `high`, and both are Dependabot security-fix PRs
  that passed in 12-17 s, so they show the gate's latency is low, not that
  a `high` threshold would stay quiet on a PR introducing a new advisory).
  Gate at `moderate` (rejected,
  keep-but-compare: no measured 30-day run at `moderate` exists yet to show
  its false-positive rate on this repository's dependency set).
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

- **Stale lane text, recorded here only.** The lane-sourced Dependabot
  alternative in `catalogs/landscape/foundation.json` (rendered into
  `catalogs/sota-convergence/layer-verdicts-20260922.json` and the handbook's
  generated verdict block) still says Dependabot owns only GitHub Actions
  references. Since the 2026-09-23 fixture entry that is no longer exact. Sealed
  lane outputs are not edited by hand; the next recorded lane run for that layer
  replaces the text, and this bullet is the correction until then.

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
- **harden-runner stays audit** on 21 of 25 ubuntu jobs (measured 2026-09-23
  at HEAD, counting every job across `.github/workflows/*.yml` whose
  `runs-on` is a literal `ubuntu-` label with `tests/test_workflow_hardening.py`'s
  own job/first-step parser); the other 4 are hash-frozen exemptions
  (`native-offhost-app-state.yml`'s `source` and `destination`,
  `native-offhost-restore.yml`'s `synthetic-restore`, and
  `native-token-e2e.yml`'s `native-token-tools`). Block mode needs a per-job
  allow-list backed by audit runs.
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

## Post-merge verification (2026-09-23)

Hosted and live results after merge. Evidence class: hosted runs and GitHub API readbacks.

- **CodeQL alerts (#104, merged `7dc8317`).** Alerts 1, 3, 4, 5 and 8 are `fixed` on main.
  Alerts 2, 6, 7, 9 and 10 are dismissed with recorded reasons. An independent second triage
  of all ten ran 20 adversarial refutation votes and refuted none of them.
  Open CodeQL alerts: 0.
- **This change (#108, merged `4970ba0`).** The first push runs on `4970ba0` succeeded:
  - `security-scan.yml`: the OSV-Scanner SARIF has 0 results and the zizmor SARIF has 0 results,
    and both analyses appear under code scanning;
  - the supply-chain grype `--fail-on high` gate;
  - Scorecard, with its SARIF uploaded;
  - CodeQL;
  - validate.
- **Target ruleset applied.** Ruleset 23739774 was updated at 2026-09-23T05:42:42Z after the
  owner of the other open PRs confirmed they had rebased.
  - Required checks: `validate`, `token-report`, `secret-scan`, `dependency-review`, `osv-scanner`.
  - `code_scanning` rule: CodeQL, `high_or_higher` / `errors`. The API accepted this rule on a
    personal public repository.
  - `strict` is off, and there is no `required_signatures` rule.
- **Release job.** Tag `v2026.09.23` on `4970ba0` ran publish-catalog run 35823698627, and
  both the `publish` and `release` jobs succeeded. The release has `isDraft: false`,
  `isImmutable: true` and exactly two assets, the archive and the SPDX SBOM, each with its
  sha256 digest. `gh attestation verify` on the downloaded archive exited 0.
- **Dependabot.** 0 open alerts: 1-6 were fixed by #99, and 7-15 are the fixture alerts,
  dismissed as `not_used`.
- **Scorecard after (dispatch run 35824151483 plus the open Scorecard alerts).**

  | Check | Score | Cause |
  | --- | --- | --- |
  | SAST | 4 (was 0) | Rises as newly analysed commits replace the unanalysed history |
  | Vulnerabilities | 1 | All 9 advisories are the deliberate grype positive-control fixture. The remedy, a fixture-local `osv-scanner.toml`, belongs to the fixture owner |
  | Branch-Protection | 3 | Solo repository, so there are no approvals or code-owner reviews |
  | Code-Review | 0 | Same reason |
  | Maintained | 0 | The repository is under 90 days old |
  | CII-Best-Practices | 0 | Optional registration by the user |
  | Fuzzing | 0 | Not applicable yet |
  | Pinned-Dependencies | 9 | `npm install` in the bootstrap scripts, part of the macOS PR's scope |

- **Related setting, owned elsewhere.** `can_approve_pull_request_reviews` was set to true by
  the bot-PR live test (#95, recorded in #110). It is not part of this change's target.

## Blind comparison (2026-09-23)

- **Why.** Two independent implementations of the same approved
  GitHub-automation plan existed per repository (the merged one above and an
  unmerged one built in parallel by a side agent of the same session). The
  user asked for a blind comparison and to merge the winner.
- **Protocol.** Preregistered before evaluation (`PREREGISTRATION.md`, with
  Amendment 1 recorded after the first run and before re-judging: neutral
  protocol ids after a repository-name leak, two harness defects fixed,
  frozen per-command results added; metrics, thresholds and closure rule
  unchanged). Arms had opaque labels; the key stayed sealed. Metrics:
  `defect_weight` (10/3/1 per confirmed high/medium/low; confirmed = single-arm
  reviewer claim not refuted by an independent source-reading refuter),
  `battery_pass_rate` (identical fixed battery emulating the workflows with
  fake scanners; the agent-lab hermetic check ran under bubblewrap with host
  paths hidden), `requirements_met_rate` (shared requirement list), and
  `own_suite_pass`. Closure by `tools/compare/closure.mjs`: the challenger
  overturns only if better on defects AND not worse on the other three.
- **Harness validation.** Positive controls reproduced known outcomes (the
  pre-fix commit's findings-path report loss; the hermetic failure a hosted
  run had shown).
- **Results (run `wf_40347d59-2e8`, second pass).** Catalog `cmp-a`:
  incumbent `defect_weight` 5, battery 1.0 (13/13), requirements 0.90, own
  suite 1; challenger 10, 0.9231 (fails the analyzer-crash check), 0.8333,
  1 -> closure "retain". agent-lab `cmp-b`: incumbent 10, 1.0 (8/8),
  requirements 0.90, own suite 1; challenger 7, 1.0, 0.80, 1 -> closure
  "retain" (challenger better on defects only). Publication gate passed for
  both: 3 of 3 blind refuters did not refute, 0 leak votes, judge leak false.
- **Outcome.** The merged implementation is the winner in both repositories,
  so nothing is replaced; the winner's confirmed defects are fixed in this
  change (the preregistered graft rule).
- **Limitations.** The battery was authored by the coordinator, who had seen
  earlier review findings on both arms; the challenger branches were built on
  older bases; one incumbent acceptance-command result was dropped when the
  packet was built (the battery file shows all 10 commands exit 0, so
  `own_suite_pass` is unaffected); the completeness critic ran before closure
  files existed.

## verdict-review-gate (2026-09-23)

- **Evidence.** The coordinator's audit found that a PR changing layer-verdict rows could merge
  with 0 reviews. The live ruleset readback (`gh api .../rulesets/23739774`, 2026-09-23T15:16Z)
  shows `required_approving_review_count: 0` and `require_code_owner_review: false`. The required
  checks are `validate`, `token-report`, `secret-scan`, `dependency-review` and `osv-scanner`.
  `gh api .../collaborators` returns 1 collaborator. Review of #122 (findings 1, 2, 4 and 6) showed
  that CI compared the hashes of a new-wave row but not its agreement, its winners, its
  single-lane authorization or earlier wave registry entries.
- **Alternatives.**
  - Required approvals: they block the only maintainer, who cannot approve their own PR.
  - CODEOWNERS review: the existing `*` rule already names the only owner, so requesting a
    review from the author adds nothing.
  - Relying on `validate` alone: `scripts/landscape.py` checks what a row claims against its own
    files. It does not compare the row with the base, and it does not recompute agreement or
    winners from the sealed returns.
- **Decision.** The new `verdict-review-gate` job in `validate.yml` runs
  `scripts/verdict_review_gate.py` on every pull request, with no path filter, and on each push
  to `main`. Any row that is added or changed outside the grandfathered 20260922 wave needs all
  of the following:
  - a registered wave document and a registered run manifest that lists the row;
  - registered, hash-matching sealed returns from two distinct model families;
  - an agreement that matches the one recomputed from the two sealed returns, and winners that
    match the chosen lane's keys resolved through the sealed packet, with the candidate's
    repository, recipe reference and pin and that lane's evidence class and `why_selected`. With no
    sealed packet the row fails closed until finding 6 lands;
  - published `alternatives`, `verdict_overturn_when` and `overturn_protocol` equal to what
    `record_verdicts.py` derives from the sealed returns (`open_gaps` is re-checked with the row,
    not re-derived);
  - for a `disagree` row, an adjudication in which judges from both lane families agree in both
    presentation orders with no refuting vote. A third-family judge is recorded but not required;
  - for a `codex_absent` row, a `docs/decisions/` record that carries
    `single-lane-authorization: <catalog>/<layer_id>`.

  Every changed `platform_status` value must be the one `scripts/platform_status.py` derives.
  Every base wave entry except the newest must be unchanged (the newest too once the PR registers
  a newer wave; review of #135, M1). The rows always come from `build_verdicts.LEDGER_FILES`, and the head's landscape manifest must name exactly those files,
  so a decoy ledger cannot be validated in place of the published one. The job runs the base
  commit's copy of the gate against the PR checkout. A PR that changes verdict rows, waves or
  sealed artifacts together with the gate's trust base (the gate, the modules it imports and
  runs, the verdict tools, `validate.yml`) fails. `.github/main-ruleset.json` adds the
  check. The coordinator applies the ruleset after merge, and until then the check reports but
  does not block.
- **Review of the gate (2026-09-23).** An independent review found a decoy-ledger bypass (the
  manifest could point `scripts/landscape.py` at a copy while the published ledger changed), that
  the gate ran the PR's own code, that a winner's repository and recipe reference and the published
  alternatives were not tied to the sealed evidence, and that a base read error counted as an absent
  file. All four are closed with a negative-control test each. It also noted that
  `strict_required_status_checks_policy` stays `false` (a standing choice asserted by
  `tests/test_workflow_hardening.py`): a squash merged after `main` gained or changed a wave is then
  judged against the older base, and only the push-to-`main` run catches it, after the merge.
- **Measured.** `tests/test_verdict_review_gate.py` has 61 synthetic-fixture tests (45 before the review). They cover the
  negative controls (missing, stale or unregistered lane files, same-family lanes, adjudications
  that are missing, one-order, one-family or refuted, a row missing from its run manifest, an
  unregistered wave, a declared platform upgrade, edited winner fields, a relabelled agreement, mismatched packets,
  swapped winners, missing packets, the single-lane path rules and a rewritten earlier wave) and
  the positive controls. Two mutations of the real checkout both exit 1 and were then restored:
  moving `foundation/workers` into an unsealed 20260923 wave, and deleting one of its sealed
  20260922 lane files. After the review, further real-checkout mutations also exit 1: a decoy
  landscape manifest with an unevidenced real-ledger edit, and a head that widens
  `GRANDFATHERED_RUN_IDS` judged by the base's gate.
- **Second review of the gate (2026-09-23).** A second independent review raised six findings.
  All six are closed here, and finding 2 is closed as an accepted residual.
  - **Finding 1 (row rollback or deletion, medium).** Every `(catalog, layer_id)` row at the
    base must still exist at the head, and there is one row per layer. The head row's run id may
    not be older than the base row's; the grandfathered 20260922 is the oldest. A run id may
    change only to the newest registered wave, and the row then needs the full new-wave
    evidence. A row may not move from a new wave to grandfathered content.
  - **Finding 3 (generator format changes, low).** Rows, wave documents and the registry are
    compared on parsed values, and a frozen document's registry sha256 must match its reformatted
    bytes. A pure reformat therefore passes and is not a verdict change for the trust-base rule.
    `build_verdicts.py --check` still runs on it.
  - **Finding 4 (trust base, low).** `TRUST_PATHS` adds `scripts/validate.py` (imported through
    `scripts/host_receipts.py`), `tools/sota-convergence/lane-provenance.json` and
    `adoption/host-receipt.schema.json`. A test derives the transitive repository imports of the
    gate and its validators, and the rule inputs they read, from the modules themselves.
  - **Finding 5 (base selection, low).** On `pull_request` the base is the checked-out merge
    commit's first parent. The payload `base.sha` must be an ancestor of it, and the job fails
    closed when neither is available. On a push to `main` the base is `github.event.before`, and
    the job fails closed on an empty or all-zero value.
  - **Finding 6 (alignment with the tooling owner's #124, low).** A row's packet is resolved
    through its run-manifest entry (`packet_sha256`, `retained_packets`, `packets_sha256sums`),
    not an assumed file name. A sealed packet a changed row relies on may carry no withheld key at
    any depth. `lanes.run_manifest_sha256`, `lanes.adjudication_sha256` (bound also to the run
    manifest's `adjudication`) and `lanes.single_lane_decision_sha256` are required and must
    match. The names are #124's module constants, and a test compares them with
    `scripts/landscape.py` once #124 defines them there.
- **Measured (second review, 2026-09-23).** `tests/test_verdict_review_gate.py` has 92
  synthetic-fixture tests (61 before), and `tests/test_workflow_hardening.py` has 7
  `VerdictReviewGateTests`. The new negative controls cover a rollback to 20260922 content, a
  deleted grandfathered or new-wave row, a downgrade to an older non-grandfathered wave, a move
  to an unregistered wave or to a registered wave that is not the newest, two rows for one layer,
  a stale frozen-document sha256, a missing or wrong `run_manifest_sha256`, `adjudication_sha256`
  or `single_lane_decision_sha256`, a packet missing from the run manifest, a packet or
  SHA256SUMS other than the run manifest's, and seven withheld-key packets. Positive controls
  cover a pure reformat with its sha256 updated and a generator change together with its
  regenerated documents. Real-checkout mutations were run in a scratch worktree with
  `--base HEAD` and then restored:
  - deleting `foundation/workers` exits 1;
  - rolling it back from a committed 20260923 base to its 20260922 content exits 1;
  - downgrading it from 20260924 to 20260923 exits 1;
  - moving it to an unregistered 20260925 wave exits 1;
  - reformatting both real ledgers exits 0, with `scripts/landscape.py` and
    `build_verdicts.py --check` run and passing.

  With #124's `scripts/landscape.py` and `tools/sota-convergence/` (origin
  `claude/verdict-integrity-2-20260923` at 238c754) overlaid in a scratch worktree, the 92 tests
  also pass, including the constant-name comparison. This is a local integration check of the
  unmerged branch, not of its merged form.
- **Third review of the gate (2026-09-23).** A third independent review raised one medium
  and four low findings. All are closed except the second, which is recorded as documented scope.
  - **Finding 1 (relabelled status, medium).** A recorded newest-wave row could be relabelled
    `pending_lanes` or `no_selection` with its winners, alternatives and overturn text cleared,
    and it passed, because nothing derived `verdict_status` from the sealed evidence. The gate
    now derives the status `record_verdicts.py` writes (`recorded` for agreeing lanes, an
    adjudicated disagreement or an authorized single lane, unless no indexed alternative remains;
    `pending_lanes` otherwise) and fails a row with any other status. A new-wave row is never
    `no_selection`. Negative controls: an agreeing row relabelled `pending_lanes` and relabelled
    `no_selection`, an adjudicated disagreement relabelled `pending_lanes`, a single-lane row
    relabelled `pending_lanes` with its decision hash dropped, an added `no_selection` row, and a
    `recorded` row with no remaining alternative.
  - **Finding 2 (free-form published fields, low).** `open_gaps` text and the wave document's
    `title`, `group`, `overturn_when` and `checked_at` are not re-derived within the newest wave.
    This is now stated in `docs/github-automation.md`; frozen waves are compared whole.
  - **Finding 3 (fail-open git error, low).** A failing `git diff` or `git ls-files` while
    listing changed paths raises a read error (exit 2) instead of counting as no change.
  - **Finding 4 (duplicate JSON keys, low).** Every parse in the gate uses
    `catalog_decisions.unique_json`; a duplicate key is not equivalent and a malformed ledger or
    registry exits 2.
  - **Finding 5 (empty name-alignment test, low).** #124's constant values at 238c754 are
    pinned as literals and asserted unconditionally; the comparison with `scripts/landscape.py`
    skips with a reason until #124 defines the names there.
  - *Residual.* A `codex_absent` row relabelled `pending_lanes` with `lanes.single_lane_decision`
    removed is what `record_verdicts.py` writes without `--allow-single-lane`, and the run manifest
    does not record the decision, so it cannot be told apart and passes. It withdraws a
    single-family verdict. It cannot add one only since the fourth review (G2): until then the
    authorization was read from the head alone, so a PR could add it with the row it authorized.
- **Fourth review of the gate (2026-09-23).** A fourth independent review raised two medium and
  two low findings. All four are closed.
  - **G1 (platform_status forgery, medium).** The gate compared a winner's repository, recipe
    reference, evidence class, `why_selected` and packet pin, but not its `evidence_refs`, and not
    its pin when the packet had none. `platform_status` was then derived from the head winner's own
    refs and pin. A row could cite any registered `evidence/` file, or add a pin matching some host
    receipt, and raise its status. Each winner apart from `platform_status` must now equal
    `record_verdicts.build_winners` output (refs normalized against the head, the packet pin, else
    the row's v1 candidate pin, else `unpinned`, and no other key). `platform_status` is derived
    from the sealed refs and a sealed pin: the packet pin, else a pin the base's row candidates
    already carry, else `unpinned`, which binds no receipt. A platform-only change is resolved the
    same way.
  - **G2 (same-PR single-lane authorization, medium).** The decision record named by
    `lanes.single_lane_decision` must exist at the base with the same bytes (`git show
    <base>:<path>`). An authorization added or edited in the PR that adds its row fails, and the
    derived status is then `pending_lanes`.
  - **G3 (hand-written read list, low).** The test that claimed to derive the rule inputs listed
    three constants. It now records every file opened (a `sys.addaudithook`, in a subprocess)
    while the gate judges a fixture that reaches the agreeing, adjudicated and single-lane paths,
    and while `scripts/landscape.py` and `build_verdicts.py --check` check this checkout. Every
    head-side read of the gate must be a `TRUST_PATHS` file or verdict data named in
    `HEAD_DATA_BINDINGS` with what binds it. Every code, schema or tool-registry read of the
    validators must be a `TRUST_PATHS` file. The derivation found two unbound rule inputs, both
    now bound. The first is the canonical repository index (`sources.repository_index`), which
    decides the derived alternatives and status: a changed row must derive the same alternatives
    with the base's index. The second is `adoption/manifest.json#/platform_profiles`, read by
    `host_receipts.platform_profile_map` to decide a receipt's platform identity. It is a
    `RULE_INPUT_FIELDS` entry under the trust-base rule; the rest of that file stays data.
  - **G4 (merge-commit premise, low).** On `pull_request` the job now requires HEAD to have
    exactly two parents, the second equal to the payload's `pull_request.head.sha` (through
    `env`), and fails closed otherwise. `tests/test_workflow_hardening.py` asserts the text and
    executes the step's script against a scratch repository. The merge commit passes and calls
    the gate with its first parent. Three cases exit 1 without calling it: the PR head checked
    out, a merge commit of another head, and an empty payload head.
  - *Round-three lows, re-checked.* Fail-open git errors: the base tree read now uses
    `git ls-tree` and exits 2 when the listing fails, because `git cat-file -e` exits 128 both for
    an absent path and for a broken repository. Duplicate JSON keys: every gate parse, including
    the new base index and platform profiles reads, uses `unique_json`. The name-alignment test
    still asserts #124's pinned literals unconditionally. The free-form published fields remain
    the recorded residual: `open_gaps` text and the wave document's `title`, `group`,
    `overturn_when` (the handbook fallback) and `checked_at` are layer metadata or recording
    dates that no sealed lane return produces, so there is nothing to derive them from.
- **Measured (fourth review, 2026-09-23).** `tests/test_verdict_review_gate.py` has 127
  synthetic-fixture tests (107 before), and `tests/test_workflow_hardening.py` has 9
  `VerdictReviewGateTests` (7 before). Run against the pre-fix gate (09ff4e9), all nine new
  negative controls fail and the four positive controls pass. The negative controls are forged
  `evidence_refs`, a pin added where the packet has none (with and without a matching head
  candidate), a pin changed to match an unrelated receipt, an extra winner key, an authorization
  added or edited in the same PR, an index edit that withdraws a verdict, and a `platform_profiles`
  change with a verdict change.

  Real-checkout mutations ran in a scratch detached worktree of b76cd704, which was then
  removed. It held a committed decision record and a constructed sealed 20260923 wave for four
  real foundation layers, laid out as the gate requires (#124's retained packets). On it, the
  gate's own rules (`evaluate`, validators off) pass all four rows. Mutations against that
  base, gate's own rules:
  - forged `evidence_refs` on `workers` (a registered `evidence/receipts/` file) with linux
    `accepted`: fails on the refs and on the derived `conditional`. The pre-fix gate passes it;
  - `token-efficiency`'s `rtk` pin set to 0.49.0 (the real `evidence/hosts` rtk receipt) with
    linux `conditional`: fails on the pin and on the derived `not_established`. With a head
    candidate `source_pin` added too, it fails on the status alone, derived at the sealed pin
    `unpinned`. The pre-fix gate passes both;
  - `quality-evaluation`'s `shellcheck` pin changed from the packet's 0.10.0 to the receipt's
    0.11.0: fails on the pin and on the status. The pre-fix gate fails on the pin only;
  - the single-lane record edited in the same comparison: fails (`differs from its base copy`).
    The pre-fix gate passes it;
  - the same wave judged against the commit before the record landed (authorization in the same
    PR): fails (`is not at the base`). The pre-fix gate passes it;
  - control, an `open_gaps` edit: passes.

  The CLI runs with validators, and every one of these runs, the control included, exits 1. The
  reason is that `scripts/landscape.py` and `build_verdicts.py --check` reject the constructed
  wave itself: its placeholder wave document and its lane returns have no lane provenance. That
  exit code is therefore not evidence for these findings. The evidence is the gate's own
  violation list.
- **Fifth review of the gate (2026-09-23).** A fifth independent review of the fourth-round
  change raised one medium and three low findings. The medium and two lows are closed; the third
  low is an accepted residual (below).
  - **Sealed citation resolved at the head (medium, the rest of G1).** A sealed
    `winner_evidence_refs` citation counts only if the cited file exists, and
    `platform_status` accepts it when `manifests/evidence.json` registers it. Both were read at
    the head. A citation to a file that did not exist when the row was recorded (so
    `record_verdicts.py` dropped it) could be made to count by a PR that adds and registers the
    file, copies it into the row's `evidence_refs` and raises linux to `accepted`. The row's
    `evidence_refs` still follow `build_winners` at the head. But a changed `platform_status`
    value may now rank no higher than what `platform_status()` derives from evidence refs that
    are already at the base with the same bytes (`git ls-tree` blob id) and registered there with
    that sha256. Negative controls: the citation's file added with the raise, the file added with
    the row, the cited file rewritten in the same PR, and a base file the base does not register.
    Positive: the cited file already at the base.
  - **Same-PR host receipts (low).** Receipts are read from the head, so a receipt added in the
    PR that raises a status supported it. The same base rule now applies to receipts: a raised
    value is derived again from only the receipts at the base with the same bytes and registered
    there. This follows the G2 principle: evidence that raises a status lands in its own earlier
    PR. A lower or unchanged value is not held to the base. Negative control: the qualifying
    receipt added with the raise. Positive: the receipt at the base.
  - **`sota_components` (low).** `build_verdicts.py` publishes each row's `sota_components` from
    the SOTA manifest the wave's registry entry names, and the newest wave's document may be
    regenerated, so its manifest could be edited. The manifest every base registry entry names,
    the newest included, must now keep its pointer and its parsed value. Negative controls: the
    newest wave's manifest edited, its pointer moved, the grandfathered manifest edited.
    Positive: a pure reformat. *Residual:* a wave registered for the first time in a PR brings
    its manifest with it, and nothing binds that manifest to the sealed packets built from it.
    Proposed fix for the tooling owner (`tools/sota-convergence/record_verdicts.py`, #124's run
    manifest): record the SOTA manifest's path and sha256 in `run-manifest.json`, which the gate
    would then compare with the registry entry.
  - **Self-attested sealed files (low).** Recorded as the accepted residual below. The
    overturn line and the `validate.yml` comment now describe a consistency check.
  - *Round-three lows, re-checked again.* `merge_base()` falls back to the given base only when
    `git merge-base` exits 1 with no output (no common history; comparing with the base tip then
    reports more changes, not fewer). Any other failure exits 2 (`MergeBaseTests`). Duplicate
    JSON keys: the new base-registry read uses `unique_json`. The free-form published fields
    residual now also names `sota_components` of a newly registered wave, above. The
    name-alignment test is unchanged: it asserts #124's pinned literals unconditionally, and the
    comparison with `scripts/landscape.py` skips with its reason until #124 defines the names.
- **Measured (fifth review, 2026-09-23).** `tests/test_verdict_review_gate.py` has 139
  synthetic-fixture tests (127 before). Three positive controls were rebased so their evidence or
  receipt is at the base, since they had added it in the same comparison. Run against the pre-fix
  gate (7eadf1e6), all nine new negative controls fail. They are five `platform_status` cases
  (a late citation, evidence added with the row, rewritten, or unregistered at the base, and a
  same-PR receipt), three SOTA manifest cases and the merge-base git failure. The positive
  controls pass on both gates.

  Real-checkout mutations ran in a scratch detached worktree of b316f3f9, which was then
  removed. It held a committed decision record and the constructed sealed 20260923 wave for four
  real foundation layers, whose `workers` claude return cites `evidence/scratch-new.json`, absent
  when the row was recorded. Results of the gate's own rules (`evaluate`, validators off), new
  gate against the 7eadf1e6 gate:
  - the late citation's file added and registered, copied into `workers`' `evidence_refs`, with
    linux `accepted`: the new gate fails, deriving `conditional`; the old gate passes it;
  - the same with the file already at the base: passes on the new gate;
  - a schema-valid `shellcheck` install receipt at the sealed pin 0.10.0 added with
    `quality-evaluation` linux raised to `conditional`: the new gate fails, deriving
    `not_established`; the old gate passes it. With the receipt at the base, the raise passes;
  - `manifest-20260923.json` (registered by the wave) edited: the new gate fails; the old gate
    passes it;
  - G2 re-run: the single-lane record edited in the same comparison, and the wave judged against
    the commit before the record landed, both fail on both gates;
  - control, an `open_gaps` edit: passes on both.

  As in the fourth round, the CLI exits 1 on every run, the control included. The cause is that
  `scripts/landscape.py` and `build_verdicts.py --check` reject the constructed wave. Only the
  gate's own violation list is evidence here.
- **Sixth review (2026-09-23, coordinator-applied).**
  - *Fixed, medium:* a pin change behind an unchanged declared status. The no-packet-pin fallback
    now comes from the base row's candidates, so a candidates-only pin change fails the pin check
    and has to land in its own PR. An unchanged platform value is now skipped only when the
    winner's `pin`, `evidence_refs` and `evidence_class` are unchanged too; otherwise it is
    re-derived.
    - Negative controls: a candidates pin moved to 9.10 with a same-PR 9.10 receipt; changed
      evidence_refs behind an unchanged status; a re-sealed pin 1.0 to 2.0 behind an unchanged
      `accepted`.
    - Each is mutation-checked: reverting either half of the fix makes its test fail.
  - *Recorded, low: grandfathered rows.* A changed row of the grandfathered 20260922 wave gets no
    row check of its own. Only `build_verdicts.py --check`'s frozen projection covers it. That wave
    is superseded at the 20260923 re-record, which is when this residual ends.
  - *Recorded, low: single-lane authorization scope.* An authorization line
    `single-lane-authorization: <catalog>/<layer_id>` is not scoped to a wave. Once it is at the
    base, it also authorizes a later wave's `codex_absent` row for that layer.
    - Proposed fix for the tooling owner: include the run id in the line, as
      `<catalog>/<layer_id>@<run-id>`, and have landscape.py and this gate require it.
- **Review of #135 (2026-09-23, evidence-reviewer Opus/high; fixes in the same PR).**
  - *Fixed, high (H1): a retargeted PR reused a stale green gate.* The `pull_request` trigger had
    no `types`, so a base-branch change (the `edited` event) did not re-run the job, and the job
    never checked the base branch. A PR from `f` to `t`, where `t` already held a rule-breaking
    change and `f` only a harmless file, passed; `gh pr edit --base main` then kept that result.
    The trigger now lists `[opened, synchronize, reopened, edited]`, and the job fails closed on a
    `pull_request` event whose base branch (`GITHUB_BASE_REF`, passed as `PR_BASE_REF` through the
    step's `env`, never interpolated into `run:`) is not `main`. Push-to-`main` runs are unchanged.
    Tests: the trigger lists `edited`; the executed step script fails for `develop`, `main-copy` and
    an empty base ref and runs the gate for `main`. Reproduced live on GitHub below (round 2).
    - Round 2 (low, defence in depth): the step only checked that the payload `base.sha` is an
      ancestor of the merge commit's first parent, so a merge commit still built on a stacked
      branch that contains `main`'s tip would have been judged against that branch. The first
      parent must now also be an ancestor of `refs/remotes/origin/main` (fetched by
      `actions/checkout` with `fetch-depth: 0`, whose pinned revision fetches
      `+refs/heads/*:refs/remotes/origin/*`), or the job fails closed. Test: a merge of the PR
      head into a stacked branch fails; the merge into `main` runs the gate.
    - Live on GitHub (hosted runs, 2026-09-23, throwaway draft PR #143). The head was `b241106b`,
      an empty commit on this branch at `b1bd5e26`. The PR was opened against the stacked
      branch `claude/h1-live-stacked` (`b1bd5e26`, which contains `main`), then retargeted.
      1. `opened` against the stacked base: the gate failed closed with "the pull request's
         base branch is 'claude/h1-live-stacked', not main" (run 35907554093, job 107338919327).
      2. `gh pr edit --base main`: an `edited` run fired, which confirms that a retarget emits the
         `edited` type. It checked out `refs/pull/143/merge` at the **stale** merge commit
         `ca990006` ("Merge b241106b into b1bd5e26"), still built on the old base, while its
         payload already said `base.ref=main` and `base.sha=3956c924`. The payload base is an
         ancestor of that first parent, so only the round-2 check stopped it: "the base
         b1bd5e26… is not a commit on origin/main; failing closed" (run 35907626904, job
         107339795307).
         - Without that check the gate would have judged the retargeted PR against the stacked
           branch. The H1 bypass would have stayed open through the `edited` run, as the round-2
           reviewer predicted. The check is load-bearing, not only defence in depth.
         - A re-run keeps the same `GITHUB_SHA`, so it cannot recover.
      3. Close and reopen: the `reopened` run checked out the rebuilt merge commit `660d58d8`
         ("Merge b241106b into 3956c924"), and the gate ran and passed (run 35908075608, job
         107340867643).
      - The error message now names this recovery: close and reopen, or push a commit.
      - #143 was then closed and both branches were deleted.
  - *Fixed, medium (M1): the base's newest wave was rewritable by a PR that registers a newer
    wave.* Every wave document holds all rows, and once a wave is no longer current
    `build_verdicts.py --check` checks only its own rows and its registry sha256. When the head
    registers a wave newer than the base's newest, that newest (non-grandfathered) wave is now
    frozen: its registry entry, sha256 included, is type-strictly unchanged and its document is
    byte-identical. Negative controls: a row edited inside the base-newest document with its
    registry sha256 updated and a newer wave registered fails; a pure reformat of it in that case
    fails too; registering a newer wave without touching it passes.
    - Round 2 (medium): the freeze covered only base waves, and only the current wave is
      regenerated by `build_verdicts.py --check`, so a PR could register two new waves (a forged
      `20260923` with its correct sha256 beside an honest `20260924`) or one backdated wave and
      publish a document no check compares with the generator. A newly registered wave must now
      be the only new run id, the head's newest, and newer than every base wave. Negative
      controls: two new waves fail; a backdated new wave fails; one new current wave passes.
    - Round 2 (builder note, closed by the coordinator): with no newer wave registered, the
      base's newest wave was skipped entirely, so a change that only unregistered it passed the
      gate. A fixture probe with stub validators confirmed this. Its rows would have stayed in
      the ledgers with no registered document. The base's newest wave may still change, but
      removing it now fails.
      - Test: unregistering it fails.
      - Mutation-checked.
  - *Fixed, low (L4): the bootstrap fallback failed open.* The job runs the head's gate only when
    the base lacks `scripts/verdict_review_gate.py` and `git diff --no-renames --name-status -z
    <base>...HEAD` shows it added (`A`); any other base without the gate fails closed. Tests: an
    adding PR bootstraps, a PR that does not add it fails, a base with the gate runs the base copy.
  - *Fixed, low (L5): number and boolean values compared equal.* Frozen values (rows, wave
    documents, the registry, rule-input fields and a winner's binding fields) now compare as their
    canonical `json.dumps(..., sort_keys=True)` text, so `1`, `1.0` and `true` differ. Test: a frozen
    wave document rewritten `1` to `1.0`, `true` to `1` or `1` to `true` fails.
    - Round 2 (low, closed by the coordinator): the comparisons of a changed row with what the
      sealed returns derive were still Python `==`, so a type-only rewrite passed them. These are
      the winner fields, the published alternatives, `verdict_overturn_when` and
      `overturn_protocol`. They now use the same helper.
      - Hardening, not a closed bypass: the gate's own two-family check now applies
        `judge_adjudication`'s integer rule to `refuting_votes`. `false` and `0.0` already failed
        in `scripts/landscape.py`'s `judge_adjudication`, which the gate also calls.
      - Tests (synthetic fixtures):
        - a sealed `overturn_protocol` number rewritten `12` to `12.0` or `true` fails;
        - a sealed alternative's `why_not_default` rewritten `1` to `1.0` or `true` fails;
        - the sealed values pass;
        - a judgment with `refuting_votes` `false` or `0.0` fails the gate's own check.
      - Each test was mutation-checked.
      - Not covered by a type-only test: the six winner fields. `scripts/landscape.py` requires
        a text pin and an exact `(component_id, repository)` set.
      - Residual, outside this PR's paths: the gate freezes wave documents, not ledger rows. A
        changed row that names a grandfathered wave is reported and skipped. Only
        `tools/sota-convergence/build_verdicts.py` `check_frozen_rows` compares such rows with
        their frozen document, and it uses `!=` after `normalized()`. A type-only rewrite of a
        number or boolean in a grandfathered row is therefore not caught by this gate. The
        lane-return schema is all strings, so the exposure is small. The tooling owner
        (agent-lab-17) was notified to make that comparison type-strict.
  - *Hardening:* the changed-path listings use `git diff -z` and `git ls-files -z`, split on NUL. Test:
    a tracked and an untracked path with a space, a newline and a non-ASCII character are listed as
    themselves.
  - *Recorded, low (L3): the self-edit residual.* Confirmed: every required check is defined by the
    head, including the tests that pin the job and the gate, so a PR can edit the job and its pinning
    test together. It stays the accepted residual below.
  - Each new negative control was mutation-checked: reverting its fix makes its test fail.
- **Accepted residual: sealed lane returns are self-attested (fifth review, 2026-09-23).** The
  gate checks consistency, not provenance. A sealed lane return must match the row's
  `sealed_sha256` and be registered in the head's `manifests/evidence.json`, which the PR can
  edit. Its model family is the one the return declares. `scripts/landscape.py` checks that its
  provenance names a `workflow_path` and sha256 listed in `lane-provenance.json`, not that the
  return came from that run. A PR that writes its own lane returns (a new wave, or a rewrite of
  the newest wave with its registrations) and declares a `codex` family passes. The gate does
  not show that a cross-family review happened.
  - *Alternatives.* Lane returns produced and attested in CI (GitHub artifact attestations of
    the lane run), signed returns verified against a key outside the repository, or a
    base-registered list of lane-return hashes, so each wave's returns land in their own earlier
    PR. None is adopted. The lanes run on local native clients, not in CI. A signing key would
    have to live outside the repository and the single maintainer's own sessions. A base
    hash list moves the same self-attestation one PR earlier.
  - *Overturn.* The lane runs move into CI with attested outputs, or a second maintainer or
    external reviewer can countersign a wave. Either makes the provenance checkable and would
    replace this residual with a verification step.
- **Accepted residual: the PR's own workflow can disable the job (finding 2, 2026-09-23).** A
  `pull_request` run takes the job definition from the PR's `validate.yml`. A PR that edits the
  `verdict-review-gate` job so that it no longer runs the base's gate is therefore not blocked by
  this check.
  - *Alternatives, all rejected.* A `pull_request_target` or `workflow_run` job would take its
    definition from the base, but the repository's strict zizmor gate (`--no-config --no-ignores`,
    `tests/test_workflow_hardening.py`) rejects these dangerous triggers. A ruleset "require
    workflows" rule is available only to organizations, and this is a personal repository.
    Required code-owner review would block the single maintainer, who cannot approve their own PR.
  - *Mitigations in place.* They narrow the residual but do not close it. First, the job
    executes the base branch's copy of the gate script, and that copy imports the base's trusted
    modules. A PR that leaves the job running therefore cannot change the rules that judge it.
    Second, the trust-base rule fails a PR that changes gate-trust files (which include
    `validate.yml`) together with verdict data, as long as the job still runs the base's gate. To
    get past it, a PR has to rewrite the job's own step, a visible edit of a workflow file. That
    was not the only path: until the review of #135 (H1, in the "Review of #135" entry above), retargeting a PR whose gate had
    passed against another base branch reused that green run with no workflow edit at all. The
    `edited` trigger type and the job's fail-closed check on a base branch other than `main` close
    that path. The tests that pin the job's shape and the gate's rules
    (`tests/test_workflow_hardening.py`, `tests/test_verdict_review_gate.py`) are defined by the
    head too, so the PR that rewrites the step can rewrite them with it; the cost stays two visible
    file edits (review of #135, L3).
    Third, the push-to-`main` run re-checks after merge (asserted by
    `tests/test_workflow_hardening.py`). It catches a merge judged against a stale base, but it
    runs the merged commit's job, so it does not catch a PR that disabled that job.
  - *Overturn.* The repository moves to an organization with required workflows, or GitHub offers
    base-defined required checks for personal repositories.
- **Overturn.** A merged PR whose changed verdict row is inconsistent with the sealed evidence
  its wave registers, while this check was required (the gate checks consistency; the
  self-attestation residual above bounds what that shows). The other trigger is a second maintainer joining, which would
  make required approvals possible. The accepted residual above has its own overturn.
