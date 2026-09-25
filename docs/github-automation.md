# GitHub automation for the native research foundation

Use GitHub to maintain reproducible recipes and qualify selected changes. The
useful result is a working research task, current instructions or a recoverable
artifact. A green PR alone establishes only the checks that actually ran.

The [automation manifest](../catalogs/foundation/automation.json) is the current
inventory of selected interfaces, ownership, qualification and limitations. Use
the [dependency resolution record](tasks/2026-09-20-automation-resolution.md) for
the reviewed setup-action upgrades and their exact hosted acceptance.

Start with [current verification and limitations](tasks/2026-09-20-github-automation.md),
[publication provenance](catalog-provenance.md),
[research-task acceptance](research-task-acceptance.md), and the
[bounded upstream pilot](upstream-maintenance-pilot.md).
The [PR #26 qualification record](https://github.com/seathatflowsinourveins/native-agent-stack/pull/26)
links the final hosted revision, integration and publication outcomes; local
implementation records below remain dated observations.

## Event and execution policy

The four ordinary workflows run on pull requests, relevant pushes to `main`,
and explicit manual dispatch. Native tool and engine workflows retain their
existing changed-path filters. A feature-branch push without an open PR does
not automatically run them; opening the PR supplies the review check.

| Event | Ordinary validation and token-report checks | Native tool/engine checks | Recovery trials |
| --- | --- | --- | --- |
| Open or update a PR | Run; cancel an older run of the same workflow for that PR | Run only for existing matching paths; allow completion | No automatic run |
| Push to `main` | Run on the integrated revision | Run only for existing matching paths | No automatic run |
| Manual dispatch | Run independently | Run independently | Run only the selected trial |

Concurrency groups include the workflow and event. PR runs share their PR number;
other runs use a unique run ID. The two short validation workflows and the bounded
Action compatibility workflow cancel superseded PR runs. Native trials retain their existing completion and
artifact/cleanup behavior. PR validation and validation after integration are
different revision checks; branch-push duplication is removed.

`action-compatibility.yml` runs on PR/main changes to itself or the three recovery
workflows that consume the selected Python/Go actions, and on manual dispatch.
It runs unchanged upstream Python 3.13 verifiers and checks both selected Go
versions with the unchanged upstream verifier plus Go's `fmt` tests. It does not
dispatch a recovery trial. Node setup is covered by the existing native-token
fixture workflow when its own file changes. These filtered jobs are additional
review evidence; they are not unconditional required checks that could remain
pending on unrelated PRs. Failure artifacts use `always()` and fourteen-day
retention; platform logs are the fallback when setup/upload itself fails.

This uses GitHub's [branch/path filters](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
and [native concurrency controls](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
The configuration expresses intended scheduling. Confirm actual run counts on
the first PR/update/merge; local static analysis is not hosted scheduling evidence.

## Upstream updates with limited noise

[Dependabot configuration](../.github/dependabot.yml) checks GitHub Actions weekly
on Monday at 09:00 UTC, groups minor/patch updates and limits simultaneous version
update PRs to two. Major versions remain separate. The initial scans succeeded
after integration and opened PRs #29 and #30. Their integrity failures identified
unreviewed workflow hashes; the coordinated resolution retains those failures.
The weekly schedule is now observed: run 35583086998 (Monday 2026-09-21, 09:24
UTC) succeeded and opened no PR, so a nonempty minor/patch group remains
unobserved. A 7-day `cooldown` (`default-days: 7`, as in agent-lab) delays each
version-update PR until the release is a week old; security updates are exempt.
Repository-level Dependabot security updates were enabled separately on
2026-09-22 (see "Automation closure, 2026-09-22" below). Repository auto-merge is
allowed, but no Dependabot PR is auto-merged, and this configuration does not
update every version in the grand catalog.

Retain full commit-SHA action pins and their release comments. Dependabot supports
updating these references. Review release/source changes, run the affected upstream
or native checks, and update the reviewed hashes in `manifests/evidence.json`.
An initial bot PR may correctly fail those hash checks until the changed source is
reviewed and registered. Do not remove integrity checks or add a privileged
untrusted-PR writer merely to make the bot's first check green.

One maintenance writer owns an upgrade batch: inspect release notes and exact
source interfaces, reuse matching upstream run evidence, test only the affected
local/hosted behavior, then refresh hashes for the reviewed files. Combine related
bot proposals in one review branch when they touch the shared evidence registry;
retain their commits and close the original proposals after the replacement
merges. Record the replacement PR and old failures in the manifest/task record.
Check the active default trial plan's frozen-source bindings after a workflow
edit; update only the prospective plan and preserve historical plans and receipts
at their original revisions. The local active-plan checks invoke the actual
manual-run source guards; they do not execute or certify native recovery.
Do not blindly regenerate all file hashes or rewrite historical runtime receipts.

Primary references: [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference),
[supported SHA updates](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories),
and [GitHub's action security guidance](https://docs.github.com/en/actions/reference/security/secure-use).
For a demonstrated need to update custom catalog pins, evaluate
[Renovate's custom manager](https://docs.renovatebot.com/modules/manager/regex/)
against the existing maintenance task. Assign each dependency one updater.

## Native workflow validation

Use installed upstream checks; avoid a home-grown workflow parser as the primary
validator. The existing pinned zizmor lane checks workflow security. Upstream
[actionlint](https://github.com/rhysd/actionlint) checks workflow syntax, expressions
and action usage. Neither executes a job or establishes model-task quality.

The upstream [binary installation procedure](https://github.com/rhysd/actionlint/blob/v1.7.12/docs/install.md)
supports a task-local download and provenance verification, with no global install:

```sh
gh release download --repo rhysd/actionlint --pattern '*_linux_amd64.tar.gz' --pattern '*_checksums.txt' v1.7.12
gh attestation verify -R rhysd/actionlint actionlint_1.7.12_linux_amd64.tar.gz
sha256sum --check --ignore-missing actionlint_1.7.12_checksums.txt
tar -xzf actionlint_1.7.12_linux_amd64.tar.gz actionlint
./actionlint -version
```

Run the download in an empty owned temporary directory. From the repository,
invoke that binary on the selected workflow files, then use the existing check:

```sh
zizmor --offline --no-config --no-ignores --no-progress --persona regular --strict-collection --format json .github/workflows
python3 scripts/validate.py
```

The `validate` job now downloads that same pinned release, verifies the recorded
archive SHA-256 and runs actionlint across all workflows before integrity checks.
This closes the gap between an optional local check and routine PR acceptance.
The existing checksum-locked zizmor 1.30.1 lane remains independent. Actionlint's
embedded shellcheck found two existing sudo/redirection warnings when expanding
from four to all workflows; `tee` now retains the same apt logs under Bash pipefail.
No analyzer suppression or integrity exemption was added.

Record exact returned results and the revision. Installation/version output alone
does not prove the workflows passed. The optional analyzer is not a new required
runtime component for ordinary Codex/Claude tasks.

Local verification on 2026-09-20 used actionlint 1.7.12, source
`914e7df21a07ef503a81201c76d2b11c789d3fca`. The Linux AMD64 archive SHA-256 was
`8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`.
The native checksum check and `gh attestation verify` returned exit 0; the verified
attestation named that source, tag and upstream release workflow. Actionlint
returned exit 0 with empty stdout/stderr for the four changed workflows. The
installed zizmor returned exit 0 and `[]` for all six workflows. The existing
workflow-security/registry tests ran 49 tests and returned `OK`. These are local
static and integrity results, not hosted scheduling or improved research results.

The `validate` job also provisions the fail-closed promotion gate's isolated venv (pinned/checksummed `uv`, `uv pip sync --require-hashes` against `blueprints/us-equities/data/requirements.lock`) before running the test suite and sets `REQUIRE_PROMOTION_GATE_VENV=1`, so `tests/test_promotion_gate.py`'s fixture tests fail instead of silently skipping if that provisioning ever breaks. Locally (cold `uv` cache, this machine's network, not a hosted runner), that venv creation plus hash-verified sync of the 20 locked packages measured about 1.4-2.2 s.

## Advanced automation: bounded upstream adoption

[GitHub Agentic Workflows](https://github.com/github/gh-aw) is the upstream candidate
for reasoning over repository changes. Its supported authoring path installs
workflow skills/instructions with `gh aw init`, compiles Markdown to a locked
Actions workflow and supports declared outputs such as a proposed PR. The
[official creation guide](https://docs.github.com/en/copilot/how-tos/github-agentic-workflows/creating-github-agentic-workflows)
also documents importing maintained examples from
[githubnext/agentics](https://github.com/githubnext/agentics).

As checked on 2026-09-20, this is public preview. No agentic workflow is activated
by this guide. A useful initial pilot is one source-cited report on a material
upstream change affecting an accepted component, with the relevant acceptance
commands and explicit missing evidence. Start manually with read-only access and
a bounded model allowance, then assess useful findings, false positives and cost.
The existing ACTIVE daily 09:00 America/New_York Codex task, **Maintain native
foundation and trading catalogs**, already owns this responsibility. Its saved
scope covers source changes, retained acceptance, both catalogs and quiet operation
unless actionable. Keep that owner; no second schedule or competing writer was
created. The [pilot](upstream-maintenance-pilot.md) evaluates one concrete change.

Keep deterministic checks in supported Actions and native commands. Agent-written
summaries do not substitute for returned test output or separate observation.
Cloud engine authentication and billing are distinct from local Desktop sign-in;
do not transfer a native client's credential store.

## Publication and practical acceptance

As of a dated 2026-09-23 GET (see below), the active [main ruleset](https://github.com/seathatflowsinourveins/native-agent-stack/rules/23739774)
(id 23739774, updated 2026-09-22T11:08:22-04:00) requires the `validate`,
`token-report` and `secret-scan` jobs from GitHub Actions (app ID 15368), plus
`deletion`, `non_fast_forward`, `required_linear_history` and a `pull_request`
rule (`required_approving_review_count: 0`, `dismiss_stale_reviews_on_push: true`,
`require_code_owner_review: false`, `require_last_push_approval: false`,
`required_review_thread_resolution: true`, `allowed_merge_methods: ["squash", "rebase"]`).
It adds no human approval count or strict up-to-date requirement, and no bypass
actor. Native path-filtered and manually dispatched checks are not global
requirements. Require native acceptance separately when its capability changes.
No merge queue is enabled; add `merge_group` support before adopting one.
Merge queues are not available for this personal repository (see "Automation
closure, 2026-09-22"). A separate [tag ruleset](https://github.com/seathatflowsinourveins/native-agent-stack/rules/23829417)
(id 23829417, created 2026-09-22T11:08:53-04:00) is also active.

The committed [main-ruleset.json](../.github/main-ruleset.json) is the reviewed
*target*, not this applied state: it adds `dependency-review`, `osv-scanner`
and (2026-09-25) `validate-macos` to the required checks, keeps the strict
up-to-date policy off, and adds a CodeQL `code_scanning` rule and squash-only
merges (see "Automation closure, 2026-09-22" below, and "validate-macos
required (2026-09-25)" in that same decision record). It does not add `required_signatures`: a measured run
blocked PRs whose branch commits are unsigned, even with signed squash merges. The coordinator applies it after
the change that adds `security-scan.yml` merges; until then the GET above is
the ground truth. [tag-ruleset.json](../.github/tag-ruleset.json) (ruleset
23829417) and [tag-creation-ruleset.json](../.github/tag-creation-ruleset.json)
(ruleset 23859358) match their live rulesets field by field.

The prior state had no rulesets and returned `Branch not protected` for main.
After applying the configuration, a separate `GET /repos/OWNER/REPO/rules/branches/main`
confirmed both required contexts and their expected app. A dated re-check on
2026-09-23 (`gh api repos/seathatflowsinourveins/native-agent-stack/rulesets/23739774`
and `.../rules/branches/main`, both exit 0) reconfirmed the same live state.
This verifies settings, not an experimentally attempted blocked merge.
GitHub's [rules REST interface](https://docs.github.com/en/rest/repos/rules)
and [status-check behavior](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
define these controls.

Maintenance commands, from a reviewed checkout with native `gh` sign-in:

```sh
gh api repos/seathatflowsinourveins/native-agent-stack/rulesets/23739774
gh api --method PUT repos/seathatflowsinourveins/native-agent-stack/rulesets/23739774 --input .github/main-ruleset.json
gh api repos/seathatflowsinourveins/native-agent-stack/rules/branches/main
```

Update the existing ID instead of creating duplicates. To roll back only this
ruleset, use `gh api --method DELETE repos/seathatflowsinourveins/native-agent-stack/rulesets/23739774`;
leave unrelated settings intact. Reverting the workflow/dependency commit restores
prior scheduling. Dependabot has no auto-merge; its version PRs still need reviewed
source/hash updates. The automation maintainer owns the actionlint release/checksum,
CI lock and ruleset; Dependabot owns GitHub Actions references. The grype
positive-control fixture at `blueprints/gap-wave2-20260923/grype-known-cve-fixture`
is named `requirements.txt.fixture`, so Dependabot's pip manifest discovery
never finds it there and `.github/dependabot.yml` needs no dedicated `pip`
entry or `ignore: urllib3` rule for it (removed 2026-09-25); Dependabot owns
no real Python or binary pin.

[Native artifact attestations](catalog-provenance.md) identify the producing
workflow and revision for a manually published catalog/evidence archive. The
workflow is prepared for trusted-main execution; issuance, download verification
and tamper rejection must be recorded from that hosted event in the qualification
record. Local checks alone do not establish them. Attestations prove
provenance, not the truth or adequacy of the archive's claims.

For ecosystem usefulness, use the [native research acceptance guide](research-task-acceptance.md).
It preserves an existing declared baseline, source/quality rubric, elapsed time,
available native usage and failures. Hosted fixtures, local runtime activation,
provider consumption and artifact/token estimates remain distinct. Apply the
[acceptance evidence policy](acceptance-evidence-policy.md) throughout.

## Workflow review, 2026-09-21

All nine workflows were rechecked with the upstream scanners and every action pin was
compared with upstream. zizmor 1.30.1 (the latest release) reports no finding at the
`regular` persona used by CI. actionlint 1.7.12 (the latest release) was downloaded
task-locally by the procedure above: `gh attestation verify` and the checksum check
returned 0, the archive SHA-256 equals the recorded
`8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`, and it returned 0
with empty output across all workflows.

Each of the seven pinned actions resolves to the commit of its named release, and each
is at its latest release. Some release comments name only the moving major tag
(`# v7`, `# v8`). In `native-service-reboot.yml` and `native-foundation-e2e.yml` they now
name the exact release of the unchanged SHA (`# v7.0.1`) so a later pin update reads as a
version change. The same edit was reverted in three files whose current bytes are
hash-bound. `native-offhost-restore.yml` and `native-offhost-app-state.yml` are frozen
sources of active recovery plans, and the repository's tests failed with "frozen source
changed" and "frozen local source differs". `native-token-e2e.yml` is bound by no plan or
test, but its current SHA-256 is recorded in four execution receipts and artifacts, so
an edit would detach the file from its dated run evidence. A cosmetic comment does not
justify re-freezing a plan or detaching a receipt, so those six comments wait for the
next functional change. The
publication job's two write permissions now carry explanatory comments. No SHA,
permission, trigger or step changed.

Findings that appear only at zizmor's stricter personas are retained with reasons in
[github-automation-evidence.json](github-automation-evidence.json) under
`workflow_review_20260921`: secrets outside deployment environments in the three
manual off-host workflows (a repository settings decision for the automation
maintainer), concurrency limits on stateful or manually dispatched workflows, and
informational naming notes. Static checks execute no job; a pull request's own runs
remain the execution evidence.

## Scheduled report-only lanes, 2026-09-22

Three lanes run on a schedule and are not required checks: `catalog-freshness.yml`
(Mondays 06:17 UTC, plus manual dispatch with a `max_repos` bound), the
`sbom-vuln` job in `supply-chain.yml` (weekly, plus push/PR when its own paths
change) and `adoption-bootstrap.yml`'s `bootstrap-linux`, `bootstrap-macos` and
`bootstrap-macos-brew` jobs (weekly Monday 06:47 UTC, plus push when
`adoption/**` or `blueprints/convergence-practice/wsl-native-tools/pins.json`
change, or on a pull request that touches the same paths -- described in full
further below). None of these appear in `main-ruleset.json`'s required status
checks; a required check must run on every PR, and a scheduled or path-gated
lane does not. Update 2026-09-22: `sbom-vuln` is no longer report-only; it
fails its own job on a High or Critical grype match (see "Secret and
supply-chain scanning"), but it is still not a required check.
`adoption-bootstrap.yml`'s fourth job, `validate-macos`, is the exception
(2026-09-25): its workflow's `pull_request` trigger carries no `paths:` filter
at all, so `validate-macos` itself reports a status on every pull request and
is a required check (see "validate-macos required (2026-09-25)" in
[docs/decisions/2026-09-22-github-automation-closure.md](decisions/2026-09-22-github-automation-closure.md)).
A `changes` job, added in the same workflow, diffs the pull request's base and
head with plain `git` (no new third-party action) to keep the other three jobs
path-gated on `pull_request` the same way GitHub's own `paths:` filter already
path-gates them on `push`.

`catalog-freshness.yml` reuses `tools/sota-convergence/extract_layers.py` and
`github_freshness.py` unchanged, then rebuilds a manifest with
`build_manifest.py --lanes <empty {"lanes": [], "critic": null, "lost": []}>`.
`build_manifest.py`'s pin-vs-upstream baseline is computed directly from the
extracted foundation/trading layers and the freshness snapshot, not from
`lanes.json` (`lanes.json` only carries lane-proposed *candidates*), so an
empty lanes record still recomputes the real drift while skipping the
interactive lane-review step -- exactly the "Monthly ... skip a full lane
re-review if no selection changed" bounded check
[recipes/sota-convergence-practice.md](../recipes/sota-convergence-practice.md)
documents. The job diffs the rebuilt manifest's per-component `pin` /
`upstream.latest` / `pin_behind_upstream` against the published
`catalogs/sota-convergence/manifest-20260922.json`, writes `drift.md`, appends
a fixed-tool pin table (actionlint, gitleaks, syft, zizmor, grype,
`nautilus_trader` vs each `gh api repos/<owner>/<repo>/releases/latest`) to
`$GITHUB_STEP_SUMMARY`, and uploads both as a 30-day artifact. It opens no
issue and writes nothing back to the repository; a maintainer reads the
summary/artifact and decides whether a real lane review is warranted.

`catalog-freshness.yml`'s `python3 -m unittest` step runs on this job's
`setup-python 3.13` interpreter, which has no `requests` package installed
and no pip-install step for it. `tests/test_broad_universe_scan.py` marks
its `requests`-dependent cases with `@unittest.skipUnless(HAS_REQUESTS, ...)`
(the same convention the module already uses for its `duckdb`-dependent
cases), so those cases report skipped rather than erroring on this
interpreter -- `SymbolBatching`, `ProviderScreens`, and
`NewsFetch.test_bounded_pages_and_capped_flag`. `validate.yml`'s `validate`
job runs the same suite on a system Python that already has `requests`
available, so those cases still execute there; only this report-only
freshness lane's copy of the run has reduced coverage, and that reduction is
not currently visible anywhere the job's own output is read.

`sbom-vuln` reproduces `native-foundation-e2e.yml`'s pinned
download/verify/install steps for the exact same `nautilus_trader==2.0.0rc5`
wheel set into an isolated venv (no bwrap sandbox -- this job only needs an
installed environment to scan, not to execute the engine), generates an SPDX
and a CycloneDX SBOM with syft 1.52.0, scans both with grype (see pin below),
and writes `summary.json` (versions, `grype db status`, package count,
findings by severity). Since 2026-09-22 it runs grype with `--config .grype.yaml
--fail-on high`, so a High or Critical match fails the job; the job is
path-filtered, so it is not a required check (see "Automation closure,
2026-09-22").

## Secret and supply-chain scanning, 2026-09-22

`validate.yml`'s `secret-scan` job runs gitleaks 8.30.1 (SHA-256 verified
against `blueprints/convergence-practice/wsl-native-tools/pins.json`,
`components[name=gitleaks].archive.sha256`,
`551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`) in `git`
mode (full history, `fetch-depth: 0`) and `dir` mode (working tree), both
`--redact`. Since 2026-09-23 the `git` mode passes `--log-opts="HEAD"`, so it
scans the history of what the run would land: a pull request's merge commit,
or `main` on push. gitleaks' default scans every fetched ref, and with
`fetch-depth: 0` that includes every other open branch, so one branch's
finding failed every pull request (PR #116's branch failed PR #117). Each
branch is still scanned by its own pull request's run. The redacted JSON report is uploaded with `if: always()` so a
failed scan still leaves the report retrievable; it never prints a matched
secret to the job log. Unlike `sbom-vuln` below, this job fails on any
detection (no `--exit-code` override, so gitleaks' non-zero default stands)
and is named in `main-ruleset.json`'s `required_status_checks`. As of the
"Ruleset upgrade, 2026-09-22" section below, this is also a required check in
the *active, applied* branch-protection ruleset: `gh api
repos/seathatflowsinourveins/native-agent-stack/rules/branches/main`
(re-checked 2026-09-22 for `docs/decisions/2026-09-22-actions-hardening.md`)
returns a `required_status_checks` rule listing `validate`, `token-report`
and `secret-scan` under ruleset id 23739774.

`supply-chain.yml`'s `sbom-vuln` job uses syft 1.52.0 (linux_amd64 tarball
SHA-256 `caeedb81fb0491615f1ebd1761e4145d41ee86dd2cc7bf80669f9f5ad9d6133d`,
read from `https://github.com/anchore/syft/releases/download/v1.52.0/syft_1.52.0_checksums.txt`)
and grype 0.119.0 (linux_amd64 tarball SHA-256
`3fa2dc4b924621ab65404cf08d0b8438d896d80ab949c9d5a4ca283c36004c9b`, read from
`https://github.com/anchore/grype/releases/download/v0.119.0/grype_0.119.0_checksums.txt`).
Like the other pins on this page, grype is a fixed, checksum-verified
version, not a floating "latest" reference; `sbom-vuln` itself never compares
its pinned grype binary against upstream, it only runs the pinned binary to
scan the SBOMs it generates. `catalog-freshness.yml`'s fixed-tool table
covers grype's pin drift against upstream instead (see "Recorded decisions"
below), so nothing about grype's vulnerability-scanning role (a
`--fail-on high` gate since 2026-09-22) exempts its own version pin from
freshness tracking.

Receipts land as workflow artifacts only: `secret-scan-<run_id>` (30-day
retention) and `supply-chain-<run_id>` (90-day retention, matching the SBOM's
longer useful life). Neither report is committed to the repository.
The earlier report-only `sbom-vuln` policy and its **pending** threshold
decision are superseded (2026-09-22): the job now fails on a High or Critical
grype match not ignored in the reviewed `.grype.yaml`, and reports lower
severities in `summary.json` only. The latest run before the change
(35799579095) had 0 Critical, 0 High, 5 Medium and 1 Low, all in the venv's
seeded pip 25.0.1, so the gate passes with no ignore. `secret-scan` fails its
own job on any detection (see above).

`native-foundation-e2e.yml`'s package set has no dedicated lock file (its
pins live inline in the workflow's `packages=(...)` array); the task that
requested a "SDK lock file" for `supply-chain.yml`'s path filter found none,
so the filter instead watches the workflow file itself.

## Repository policy files

[`.github/CODEOWNERS`](../.github/CODEOWNERS) names the automation maintainer
as the default owner and again for `.github/` and `adoption/` (the built
adoption-bootstrap lane's own directory).
[`SECURITY.md`](../SECURITY.md) documents scope (a catalog, not a deployed
service), the private vulnerability reporting link (enabled;
`gh api repos/seathatflowsinourveins/native-agent-stack/private-vulnerability-reporting`
returned `{"enabled":true}` on 2026-09-23), supported refs (`main` and the
latest `v*` tag) and the `gh attestation verify` and `gh release verify-asset`
commands for the immutable tag releases. [`.github/pull_request_template.md`](../.github/pull_request_template.md)
requires scope, base commit, a per-claim evidence-class table, exact local
commands run, a decision-record path and a checklist covering SHA pins,
`contents: read`, no secrets, no paid hosting and preserved peer-owned
untracked files.

## Ruleset upgrade, 2026-09-22

[`.github/main-ruleset.json`](../.github/main-ruleset.json) gained
`deletion`, `non_fast_forward`, `required_linear_history`, a `pull_request`
rule (`required_approving_review_count: 0` -- unchanged from today's
zero-approval practice, `dismiss_stale_reviews_on_push: true`,
`require_code_owner_review: false`, `require_last_push_approval: false`,
`required_review_thread_resolution: true`,
`allowed_merge_methods: ["squash", "rebase"]`) and `secret-scan` added to
`required_status_checks`. A new [`.github/tag-ruleset.json`](../.github/tag-ruleset.json)
targets `refs/tags/*` with only `deletion` and `non_fast_forward` -- protects
published tags without adding a tag-level review requirement. Neither
ruleset file was applied by the PR that added them; both are coordinator-only.
**Both were applied on 2026-09-22** (main ruleset 23739774 updated 11:08 ET; tag
ruleset 23829417 created 11:08 ET). The live rulesets were compared field by
field with the committed files through the GitHub API: rule types and every
committed parameter match; the live `pull_request` rule also carries the
server-side defaults `required_reviewers: []` and
`require_extra_approval_for_unattributed_changes: true`. Required checks are
`validate`, `token-report` and `secret-scan`. Private vulnerability reporting was
enabled the same day. Apply and verify with:

```sh
gh api --method PUT repos/seathatflowsinourveins/native-agent-stack/rulesets/23739774 --input .github/main-ruleset.json
gh api repos/seathatflowsinourveins/native-agent-stack/rules/branches/main

# First application of the tag ruleset creates it; record the returned id
# and reuse it (PUT .../rulesets/<id>) for any future edit instead of
# creating a duplicate.
gh api --method POST repos/seathatflowsinourveins/native-agent-stack/rulesets --input .github/tag-ruleset.json
gh api repos/seathatflowsinourveins/native-agent-stack/rules/branches/main
```

On 2026-09-22 the tag ruleset was split: 23829417 ("Native foundation tag
protection") now carries `deletion`, `non_fast_forward` and `update` with no
bypass, and 23859358 ("Native foundation tag creation") carries `creation`
with the repository admin role (`RepositoryRole` 5) as an `always` bypass, so
only an admin can create a `v*` tag. Both committed files match the live GETs.
Edit them in place:

```sh
gh api --method PUT repos/seathatflowsinourveins/native-agent-stack/rulesets/23829417 --input .github/tag-ruleset.json
gh api --method PUT repos/seathatflowsinourveins/native-agent-stack/rulesets/23859358 --input .github/tag-creation-ruleset.json
```

## Recorded decisions, 2026-09-22

**Dependabot's `pip` ecosystem is NOT activated** (re-affirmed 2026-09-22 with
the measured security-update PRs below). Dependabot's `pip`
ecosystem discovers ordinary requirements/lock files by name; the checksum
lock actually used here is `.github/requirements-ci.lock`, a name Dependabot
does not recognize as a Python dependency file, and four of the five pinned
CI binaries (actionlint, gitleaks, syft, grype) are curl-downloaded release
tarballs with no manifest Dependabot understands at all. The new
`catalog-freshness.yml` drift table covers all five (actionlint, gitleaks,
syft, zizmor, grype) plus `nautilus_trader` against each tool's latest
upstream release (see "Secret and supply-chain scanning" above for why
grype's own pin is fixed like the others whatever `sbom-vuln`'s gating
role), so the gap is covered by a different, already-built lane
rather than by Dependabot.
Precondition to revisit: rename `.github/requirements-ci.lock` to a
Dependabot-discoverable name (e.g. `requirements-ci.txt` with a
`--require-hashes` format Dependabot's pip ecosystem parses) and re-evaluate.
Security updates, enabled 2026-09-22, did open pip PRs: #97 (mlx 0.29.3 ->
0.29.4) and #98 (transformers 5.0.0rc1 -> 5.10.1) against
`tools/mlx-smoke/requirements.lock.txt`. `gh pr checks 97` and `98` show every
check passing except `macos-profile` (runs 35815152321 and 35815162857): that
lock is uv-compiled with hashes and an `--exclude-newer` cutoff from
`requirements.in`, and `hardware-profile-smoke.yml` recompiles and diffs it, so
a single-package bump fails. The advisories were fixed by a reviewed relock
(#99) instead. A pip version-update entry would repeat that failure for every
uv-compiled lock.

**Superseded 2026-09-22: CodeQL default setup is now configured** (see
"Automation closure, 2026-09-22" and the closure decision record). The original
2026-09-22 decision is kept below for its reasoning. **CodeQL is NOT
activated.** GitHub's default CodeQL setup needs
`security-events: write` (this repository's workflows are `contents: read`
only) and pins no exact CodeQL bundle version by default (violates the "no
floating pin" rule every other lane here follows). The scannable surface is
stdlib-only Python (`scripts/`, `tools/`) and a handful of `.mjs` files with
no served application, no user input boundary and no authentication code --
exactly the profile `docs/github-automation.md`'s existing web-application
scanning discussion (above) already excludes. Re-evaluate if this repository
ever serves a live application path (e.g. a hosted dashboard) rather than
generating catalogs and running local scripts.

**Ownership.** The GitHub automation maintainer owns binary pins (actionlint,
gitleaks, syft, grype, and workflow-declared package pins like
`nautilus_trader`) and repository rulesets. Dependabot owns GitHub Actions
references; it does not, and per the decision above still does not, own any
real Python or binary pin. The intentionally vulnerable
`grype-known-cve-fixture` pin is retained as `requirements.txt.fixture` (not
`requirements.txt`), so it never surfaces as a Dependabot/dependency-graph
manifest at all and `.github/dependabot.yml` needs no dedicated `pip` entry
or `ignore: urllib3` for it (removed 2026-09-25, replacing the 2026-09-22
entry). (2026-09-22: repository-level security updates may now propose a fix
for an alerted lock; a maintainer still owns the reviewed relock.)

Each decision above names its evidence (the exact filename/permission gap
checked), the alternative considered (activate now) and the exact
observation that would overturn it (a renamed lock file; a served
application path), per this project's adoption-decision convention.
## Publication on tags

`publish-catalog.yml` now runs on `push: tags: ['v*']` in addition to its
existing `workflow_dispatch`, and its job condition is
`startsWith(github.ref, 'refs/tags/v') || github.ref == 'refs/heads/main'` so a
pushed release tag or the trusted-main dispatch path both qualify; any other
ref still short-circuits. Creating and pushing a `v*` tag is a coordinator-only
action: the ruleset above protects `main`, the tag creation ruleset (23859358,
2026-09-22) lets only the admin role create a tag, and only a maintainer with push
access to tag refs can trigger this path — a fork or an unprivileged
contributor cannot cause a publication run by opening a pull request. Treat a
tag push the same as the manual dispatch it extends: it still requires
`github.repository == 'seathatflowsinourveins/native-agent-stack'` and the
job's `contents: read`, `id-token: write`, `attestations: write` permissions
are unchanged.

A separate `release` job runs only for `refs/tags/v*` (after `publish`; job
permissions `contents: write` only). It downloads the archive and SBOM
artifacts by the IDs the `publish` job output, re-checks both with
`sha256sum --check --strict` against the digests that job attested, and runs
`gh release create <tag> <archive> <sbom> --verify-tag`. In gh 2.101.0
(`pkg/cmd/release/create/create.go`), a create with files and no `--draft`
makes a draft, uploads the files and then publishes, deleting the draft if an
upload fails. Immutable releases (enabled 2026-09-22) forbid adding assets
after publication, so both files are attached before the release is published.
The job then checks `gh release view --json isDraft,isImmutable,assets`:
published, immutable, exactly those two assets with the attested digests. The
release notes carry the `gh attestation verify` and `gh release verify-asset`
commands. No hosted tag run of this job exists yet.

The job now produces two attested artifacts per run, not one. After the
existing archive-and-hash step, a SHA-256-checked download of syft 1.52.0
(`syft_1.52.0_linux_amd64.tar.gz`, verified against the upstream
`syft_1.52.0_checksums.txt` and pinned in-workflow to
`caeedb81fb0491615f1ebd1761e4145d41ee86dd2cc7bf80669f9f5ad9d6133d`) scans the
checked-out tree and writes
`native-agent-stack-${GITHUB_SHA}.spdx.json`. A second `actions/attest` step
(same pinned action SHA as the archive's) attests that SBOM with
`predicate-type: https://spdx.dev/Document`, `push-to-registry: false`, and no
storage record, mirroring the archive attestation's `subject-path`/predicate
shape. Both attestations are verified in-run with `gh attestation verify`
(archive and SBOM each get their own `GH_TOKEN`-scoped step) before the SBOM is
uploaded next to the archive artifact and its digest is matched, the same
upload-then-match pattern already used for the archive. A verify command an
operator can reuse after download:

```sh
gh attestation verify native-agent-stack-<sha>.spdx.json \
  --repo seathatflowsinourveins/native-agent-stack \
  --signer-workflow seathatflowsinourveins/native-agent-stack/.github/workflows/publish-catalog.yml \
  --source-digest <sha> \
  --predicate-type https://spdx.dev/Document
```

`gh attestation verify` defaults `--predicate-type` to
`https://slsa.dev/provenance/v1`; the SBOM attestation's predicate is
`https://spdx.dev/Document`, so the flag above is required or verification
fails.

`adoption-bootstrap.yml` is a separate, lower-stakes job
(`bootstrap-linux`, 20-minute timeout, plain `ubuntu-24.04`, no elevated
permissions) that runs `adoption/bootstrap-linux.sh --profile foundation-cpu`
into `$RUNNER_TEMP/eco` on push to `main`, on pull requests touching
`adoption/**` or `blueprints/convergence-practice/wsl-native-tools/pins.json`,
weekly (Monday 06:47 UTC), and on manual dispatch, then asserts every
`foundation-cpu` required command is present via
`scripts/adoption_status.py --profile foundation-cpu --json`. Its workflow
header records this as synthetic/local-integration evidence on a disposable
runner, not a second-machine developer-laptop acceptance.

### Secret-scan coverage boundary (2026-09-22, updated 2026-09-23)

The first hosted run of the `secret-scan` job was cancelled by its own timeout while
scanning history: every commit re-diffs the 11 MB generated explorer
`docs/ecosystem/index.html`. The job now passes `--config .gitleaks.toml` and
`--max-target-megabytes 2`.

As of 2026-09-23 (`docs/decisions/2026-09-23-generated-explorer-sorted-manifest.md`),
`docs/ecosystem/index.html` is generated locally with
`python3 scripts/build_ecosystem.py --write` and is no longer committed: it is
`.gitignore`d, and `publish-catalog.yml` builds and publishes it as its own attested
workflow artifact instead (7-day retention, `workflow_dispatch`/`v*`-tag runs
only). `gitleaks dir .` (working-tree mode) therefore has nothing
generated left to skip in the current tree, and a `gitleaks git .` scan of any commit
made after this change has nothing generated to skip either. The size-based skip
remains an **incomplete-coverage boundary only for the repository's existing git
history**: every commit before this change still carries the old committed
`docs/ecosystem/index.html` (up to ~13 MB) inside `git`'s object history, so a full
`gitleaks git .` history scan still skips those old blobs at `--max-target-megabytes 2`.
`--max-target-megabytes 2` itself is kept as a general guard against any other
oversized file that might be committed in the future, not specifically for the
explorer any more.

Gitleaks' size-based skip only ever applied to *git* scanning, and never covered
the published artifact itself (gitleaks never saw a gitignored file at all,
regardless of size). A fix round on 2026-09-22 found that the built,
soon-to-be-attested explorer therefore went through neither `validate.py`'s
private-content scan (`scan_publication()` only walks git-tracked/listed
paths) nor gitleaks before publication -- the same class of finding that
`validation-attempts.json` recorded against the committed file once already.
`publish-catalog.yml` now runs `python3 scripts/validate.py --scan-file
"$explorer"` (the same `PRIVATE_CONTENT` patterns `scan_publication()` uses,
applied directly to the built file's bytes) immediately after building the
explorer and before attesting/uploading it, closing that gap without a
gitleaks scan of a moving, in-memory build artifact.

Suppression lives in two files. `.gitleaks.toml` holds the rule allowlists, each
scoped to a path and an anchored key shape. The root `.gitleaksignore` holds
commit-qualified fingerprints (`commit:path:rule:line`) for reviewed historical
false positives in two narrative evidence files; they replaced a regex allowlist
that review rounds showed could not exclude same-string secrets in RE2. A secret
added in any later commit gets a new fingerprint and is reported. Add a
fingerprint only after reviewing the finding, never for a real secret.

`.gitleaks.toml`'s own header comment is the single canonical source for the
dated full-history counts (default-rule baseline, allowlist breakdown, and the
post-config scan results); this doc does not duplicate those numbers so they
cannot drift out of sync here. As of this unit's last re-measurement (recorded
in `.gitleaks.toml`), the branch-ancestry-scoped scan (`--log-opts="HEAD"`) is
the acceptance-relevant result for this unit and reports zero findings; the
unrestricted default-log-opts scan of this shared, concurrently used repository
currently reports one residual finding attributable to a different, active
sibling branch (not an ancestor of this branch and not a path this unit owns),
which the `.gitleaks.toml` header records as a coordinator decision pending
resolution before merge, not something this unit can fix. The coordinator resolved it on 2026-09-23 by
making CI scan only `--log-opts="HEAD"` (see above). Local scans on this
host go through the guarded `gitleaks` launcher (memory-capped, one scan per
user); do not raise its limits to retry a failed scan.

## Report-only Actions hardening, 2026-09-22

Three GitHub Actions security lanes were adopted, each report-only (none was a
required check) and recorded in
[`docs/decisions/2026-09-22-actions-hardening.md`](decisions/2026-09-22-actions-hardening.md)
with the exact evidence, alternatives and overturn condition. Update
2026-09-22: dependency review stopped being report-only. It now fails on high
advisories and is a required check in the target `main-ruleset.json` (see
"Automation closure, 2026-09-22"); Scorecard and harden-runner still gate
nothing.

**`scorecard.yml` (OpenSSF Scorecard).** Runs `ossf/scorecard-action` pinned
to the full commit SHA of `v2.4.4`
(`2d1146689b8cda280b9bc96326124645441f03bc`, verified by dereferencing the
annotated tag with `gh api repos/ossf/scorecard-action/git/tags/<sha>`) on a
weekly schedule, `workflow_dispatch`, and push to `main`. `publish_results`
is `false` -- results are never published to the public `api.scorecard.dev`
dataset or badge. The workflow's top-level permission is `contents: read`;
since 2026-09-22 the `analysis` job alone also holds `security-events: write`,
which it uses only to upload the SARIF report to code scanning with
`github/codeql-action/upload-sarif` v4.38.1 (free for this public repository,
no GitHub Advanced Security purchase). The SARIF report is also retained as a
workflow artifact (`scorecard-results-<run_id>`, 5-day retention).

**`harden-runner` (step-security).** `step-security/harden-runner`, pinned to
the full commit SHA of its latest release `v2.21.1`
(`e14015d583714f6e62063499dc959a02595150a1`, from
`gh api repos/step-security/harden-runner/releases/latest`), runs as the
*first* step, before checkout, with `egress-policy: audit` (never `block`),
on 21 of 25 `ubuntu-24.04` jobs (measured 2026-09-23 at HEAD: every job across
`.github/workflows/*.yml` whose `runs-on` is a literal `ubuntu-` label, using
`tests/test_workflow_hardening.py`'s own job/first-step parser -- 25 such jobs
total, 4 in the hash-frozen exemptions below, and all 21 remaining jobs start
with `harden-runner` in audit mode, per
`test_every_ubuntu_job_starts_with_harden_runner_in_audit_mode`). The four exempt jobs are those whose
workflows are byte-pinned by retained evidence: `source` and `destination`
(`native-offhost-app-state.yml`, pinned in
`blueprints/convergence-practice/offhost-app-state/plan.json`'s
`frozen_sources`), `synthetic-restore` (`native-offhost-restore.yml`, pinned
in `blueprints/convergence-practice/offhost-restore/hosted-plan.json`) and
`native-token-tools` (`native-token-e2e.yml`, recorded in four dated execution
receipts). Adding a step to one of those needs the evidence re-run and
re-pinned. `bootstrap-macos` runs on `macos-15`, which `harden-runner` does not
support. `tests/test_workflow_hardening.py` classifies every job: an unhardened
`ubuntu` job outside the named exemptions fails, an unrecognized runner label
fails, and each exemption fails as soon as its workflow drifts from the pinned
hash. The exemptions and their overturn condition are recorded in the
"Integration follow-up" of
[`docs/decisions/2026-09-22-actions-hardening-fix-round.md`](decisions/2026-09-22-actions-hardening-fix-round.md).
Audit mode only logs
observed egress; it cannot fail a job or block a network call, so it changes
no existing pass/fail behavior.

**`dependency-review.yml` (actions/dependency-review-action).** Pinned to
the full commit SHA of its latest release `v5.0.0`
(`a1d282b36b6f3519aa1f3fc636f609c47dddb294`, from
`gh api repos/actions/dependency-review-action/releases/latest`), runs on
`pull_request` only with `contents: read`. The warn-only phase ended
2026-09-22: it now uses `fail-on-severity: high` and is a required check in
the target `main-ruleset.json`. This repository is
public (`gh api repos/seathatflowsinourveins/native-agent-stack --jq
.visibility` returns `public`) and needs no GitHub Advanced Security, but
its dependency graph was not on automatically: the first hosted run failed
until the graph was enabled through `PUT .../vulnerability-alerts` (which also
enables Dependabot alerts), after which the re-run passed. The correction and
its rollback are recorded in the decision record.

## From report-only to a reviewable evidence PR, 2026-09-23

`catalog-freshness.yml` gained a second job, `propose`, so a detected drift
can turn into a normal, human-reviewable pull request instead of only a
30-day workflow artifact. `freshness` itself is unchanged in spirit -- it
still writes nothing to the repository -- except that it now diffs against
the **newest** `catalogs/sota-convergence/manifest-*.json` by name instead of
a hard-coded dated filename, and exposes a `drift` job output (`'true'`/
`'false'`) that `propose` reads. See
[`docs/decisions/2026-09-23-bot-pr-dispatch.md`](decisions/2026-09-23-bot-pr-dispatch.md)
for the evidence, the alternatives considered and the overturn condition.

**Off by default, two ways to turn it on for one run or on a schedule.**
`propose` only runs when `github.ref == 'refs/heads/main'` and
`needs.freshness.outputs.drift == 'true'`, and even then only when *either*:

- a manual `workflow_dispatch` sets the new `open_pr` boolean input to `true`
  (default `false`), or
- the run is the weekly `schedule` trigger **and** the repository variable
  `CATALOG_FRESHNESS_PROPOSE` is set to the literal string `'true'`.

Leaving `CATALOG_FRESHNESS_PROPOSE` unset (or anything other than `'true'`)
keeps every scheduled run report-only exactly as before; opening a PR from a
schedule is an explicit opt-in, not a side effect of adding the job. `propose`
also refuses to run at all when this run's own freshness fetch was bounded
(`inputs.max_repos` nonzero), recorded any full fetch error
(`needs.freshness.outputs.upstream_errors != '0'`), or recorded any partial
error -- a releases/tags/commit sub-fetch for one repository that failed and
fell back to another source, for example a `503` on the releases endpoint
papered over by a successful tags-endpoint fetch
(`needs.freshness.outputs.partial_errors != '0'`): a partial or
partially-degraded fetch must not be turned into evidence that reads as a
complete one.

Set the variable with `gh variable set CATALOG_FRESHNESS_PROPOSE --body true`
(not `gh api --method PATCH .../actions/variables/CATALOG_FRESHNESS_PROPOSE`:
`PATCH` only updates a variable that already exists, so it fails the first
time this variable is set; `gh variable set` creates or updates it in one
call) or the repository Settings -> Secrets and variables -> Actions ->
Variables UI -- this is separate from a repository *secret* and separate from
the ordinary Dependabot/ruleset settings already documented above.

**One-time repository setting.** By default, GitHub Actions workflows using
the automatic `GITHUB_TOKEN` cannot open pull requests at all; the repository
setting **"Allow GitHub Actions to create and approve pull requests"**
(Settings -> Actions -> General -> Workflow permissions) must be enabled once
before `propose`'s `gh pr create` step can succeed, matching
[GitHub's own documentation for this restriction](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#preventing-github-actions-from-creating-or-approving-pull-requests).
This is a coordinator-only, one-time action, the same way the ruleset
application above is.

**What the bot PR actually contains.** `propose` downloads `freshness`'s own
artifact (`catalog-freshness-${{ github.run_id }}`, same run), force-creates
`automation/catalog-freshness` from `main` (`git checkout -B`, which resets
this branch to `main`'s current tip on every run regardless of what was on
it before -- **any commit a human pushes directly to
`automation/catalog-freshness` is discarded the next time this job runs**;
treat it as a bot-owned branch, not a place to accumulate manual edits), and
runs [`scripts/freshness_propose.py`](../scripts/freshness_propose.py) to:

1. copy `drift.md` and the rebuilt `manifest-*.json` into
   `evidence/artifacts/catalog-freshness-<YYYYMMDD>/`;
2. write `evidence/receipts/catalog-freshness-<YYYYMMDD>.json`, an
   `upstream_provenance`-kind receipt satisfying `scripts/validate.py`'s
   generic receipt rules (`kind`, nonempty `claim`/`limitations`, and
   `component_ids` that are real `manifests/stack.json` components -- the
   run's own drifted ids narrowed to known stack components). If **none** of
   the drifted ids match a known stack component, the job raises and stops:
   there is deliberately no fallback to an unrelated fixed component set,
   because a receipt whose `component_ids` do not describe what actually
   drifted would be misleading. The drift table's pin column is always
   compared, whether or not either side's `upstream.latest` is known --
   `scripts/freshness_propose.py`'s `compute_drift()` puts each component
   into exactly one of three buckets: **drifted** (the pin, the upstream
   `latest`, or `pin_behind_upstream` actually changed), **unfetched**
   (`upstream.pushed_at` is `None`, meaning `github_freshness.py` never
   reliably fetched that repository this run, or its raw record shows a
   fetch problem -- for example a `503` on the releases endpoint papered
   over by a tags-endpoint fallback), or **no-release** (fetched
   successfully, but the repository genuinely has no GitHub release or tag
   at all -- for example `tavily-cli`, `skills-ref` or `poppler` in the
   2026-09-22 manifest; not drift, and not "unfetched" either, since it was
   reliably observed). Only the first bucket counts toward drift or appears
   in `component_ids`. Its claim states plainly that the drift is
   report-only, that no `catalogs/sota-convergence/*`,
   `catalogs/landscape/*.json`, `manifests/stack.json`, or `layer-verdicts*`
   file was selected or changed, and that a pin bump needs its own
   separately qualified receipt under `evidence/artifacts/*/` from the
   existing SOTA-convergence lane review -- this job never runs that review
   itself;
3. register all three new files' hashes in `manifests/evidence.json`
   `files[]` (via `scripts/host_receipts.py`'s `register_file`, imported
   directly rather than reimplemented) and upsert the receipt's manifest
   entry into `receipts[]`, both matched by `path`/`id` rather than list
   position, since neither list's order is assumed stable; and
4. only when `git ls-files` still tracks `docs/ecosystem/index.html`,
   **rewrite** it from the updated evidence (`scripts/build_ecosystem.py
   --write` -- this regenerates the file's actual content, not only its
   registered hash), rehash it, and loop until `--check` passes. As of
   ["Stop committing the generated explorer"](decisions/2026-09-23-generated-explorer-sorted-manifest.md)
   the file is already `.gitignore`d on `main`, so this branch is currently
   dead code in normal operation; it is kept (and still covered by its own
   test, `TrackedExplorerSubprocessTests`) only so a future change that
   tracks the explorer again does not silently reintroduce the stdout-
   pollution bug ("H1" in
   [the decision record](decisions/2026-09-23-bot-pr-dispatch.md)) this step
   guards against.

`propose`'s remaining steps then re-run `scripts/validate.py` and
`scripts/host_receipts.py validate` on the result (its checkout uses
`fetch-depth: 0`, matching `validate.yml`'s own full-history checkout,
because `host_receipts.py validate` resolves every existing receipt's
pinned `catalog_revision` commit and a shallow clone would make historical
commits unresolvable), commit (`evidence/artifacts/`, `evidence/receipts/`,
`manifests/evidence.json`, and `docs/ecosystem/index.html` only if tracked)
as `github-actions[bot]`, and push with the job's own `GITHUB_TOKEN`
supplied through `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0`
(`http.https://github.com/.extraheader`, a Basic-auth header built at
runtime and masked with `::add-mask::` before use) rather than a persisted
credential helper -- `actions/checkout` still runs with
`persist-credentials: false`, matching every other job in this repository.
The push uses `--force-with-lease=automation/catalog-freshness:<observed-sha>`
(the remote branch's tip as `git ls-remote` observed it moments earlier, or
empty if the branch does not exist yet), not a plain `--force`, so a
concurrent run's push in between is rejected instead of silently
overwritten. This is the actual data-safety guard against a race; `propose`
also carries a job-scoped `concurrency:` group
(`${{ github.workflow }}-propose-<manual|scheduled>`, `cancel-in-progress:
false`) so that, most of the time, a run just queues behind an in-progress
one instead of overlapping at all -- keyed on whether the run is a manual
`open_pr: true` dispatch or a scheduled activation, not just
`${{ github.workflow }}`, specifically so a plain scheduled run can never
silently replace a pending manual request in the same queue slot (GitHub's
default concurrency queue holds one pending run per group, and a newly
queued run cancels/replaces it; the `queue: max` property that allows up to
100 queued runs instead is rejected by this repository's pinned actionlint
1.7.12, which does not yet recognize that key -- see
[the decision record](decisions/2026-09-23-bot-pr-dispatch.md)). Two runs
*within* the same category can still replace each other's pending slot
(an accepted, lower-stakes loss: the later same-category request already
supersedes the earlier one), and a manual and a scheduled run can therefore
still execute this job concurrently in the rare case both are triggered
close together -- `--force-with-lease` above is what keeps that safe, not
this concurrency group.
`gh pr create` opens `automation/catalog-freshness` against `main` (or
`gh pr edit` updates the existing one, keyed on `gh pr list --head
automation/catalog-freshness`), with a body that includes the run's
`drift.md` table (each cell rendered as escaped inline code by
`scripts/freshness_propose.py`'s `md_cell()`, so an upstream release tag
fetched from an external API can never break the Markdown table or smuggle
formatting) and states plainly: "no selection or pin changed; pin bumps
require a qualified receipt under evidence/artifacts/*/".

**No workflow is dispatched from this job, and that is deliberate.** An
earlier version of this design called `gh workflow run validate.yml
--ref automation/catalog-freshness` (and the same for `token-report.yml`)
on the theory that a `workflow_dispatch` run would supply the review
evidence a `pull_request` trigger normally would. [GitHub's own
troubleshooting documentation](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
refutes that: "For checks created by workflow jobs to be evaluated for a
pull request, the workflow run must be triggered by one of these events:
`push`, `pull_request`, `pull_request_review`, `pull_request_target`,
`deployment`, `deployment_status`" -- `workflow_dispatch` is not on that
list, so a dispatched run's checks never satisfy a required status check on
this PR at all, regardless of whether they pass. Dispatching would have
produced a green-looking run that the branch ruleset simply ignores. This
is recorded as a corrected claim, not silently dropped, in
[the decision record](decisions/2026-09-23-bot-pr-dispatch.md).

Instead, the job relies on the PR's own `pull_request`-triggered runs, and
tells the reader they need one extra step: because this PR is opened with
the workflow's own `GITHUB_TOKEN`, [GitHub's `GITHUB_TOKEN` reference](https://docs.github.com/en/actions/concepts/security/github_token)
states that "events triggered by the `GITHUB_TOKEN` will not create a new
workflow run, with the following exceptions" -- one of which is: "`pull_request`
events with the `opened`, `synchronize`, or `reopened` activity types: when a
workflow using `GITHUB_TOKEN` creates or updates a pull request, the
resulting `pull_request` event creates workflow runs in an
**approval-required** state." The job's last step prints the PR's URL and an
approval instruction to the job summary. To actually approve, a repository
collaborator with write access opens the PR itself and uses the banner the
GITHUB_TOKEN documentation describes in the PR's merge box, selecting
**"Approve workflows to run"** (the fork-approval page describes the same
action through an **"Awaiting approval"** button that opens the merge status
panel) -- after that, `validate`,
`token-report` and `secret-scan` run and report as ordinary `pull_request`
checks the ruleset actually requires. [GitHub's documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)
also states that "workflow runs that have been awaiting approval for more
than 30 days are automatically deleted" -- an evidence PR left unapproved
that long needs a fresh `propose` run (or a manual `git push --force` /
re-dispatch) before its checks can run at all. The REST API also documents
`POST /repos/{owner}/{repo}/actions/runs/{run_id}/approve`, but its own
description scopes it to "a pull request from a public fork of a first time
contributor" -- this repository's evidence PR is not a fork PR, so whether
that same endpoint accepts a GITHUB_TOKEN-created same-repo PR's pending run
is **not established by the documentation**. The live test on 2026-09-23
answered it: for bot PR #109, `gh api -X POST .../actions/runs/<id>/approve`
returned success on all three pending runs, and they then ran. The UI banner
and this API call both work, so a coordinator session can approve without a
browser. The job itself still does not call it, because approval stays a
reviewer's act. See "Live test, 2026-09-23" in the decision record.

`propose` is the one job in this workflow with write permissions
(`contents: write`, `pull-requests: write`, scoped to the job, not the
workflow -- the top-level `permissions:` block stays `contents: read`),
because it is the one job that opens a PR; it needs no `actions: write`
since it no longer dispatches other workflows. It is still never a required
check and it never merges anything by itself.
**Auto-merge stays off.** The evidence PR is meant to be read, not
rubber-stamped: a human (or a review lane) reads `drift.md`, decides whether
a real SOTA-convergence lane review is warranted, and merges or closes it
like any other PR. Enabling auto-merge would turn a report-only freshness
signal into an unreviewed write path into `main`, which is exactly what this
job is designed not to be.

**A peer WSL or macOS host contributes evidence the same way it always
has.** This job does not change the contribution flow in
[`docs/contributing-evidence.md`](contributing-evidence.md) at all -- it is
a separate, CI-only, scheduled/manually-dispatched producer of one specific
kind of receipt (`upstream_provenance`, pin/upstream drift only). A host
recording `native_proven`/`local_integration` host-acceptance receipts,
opening its own PR, and requesting independent review remains the primary
way this catalog gains evidence; read that chapter for the full flow.


## Verdict review gate, 2026-09-23

The repository has one maintainer and the main ruleset requires 0 approvals,
so a PR that changes a layer verdict could merge with no review at all.
`validate.yml`'s `verdict-review-gate` job is the control instead. It runs
[`scripts/verdict_review_gate.py`](../scripts/verdict_review_gate.py) on every
pull request (no path filter, so it can be required) and on each push to
`main`. The job has `contents: read`, starts with harden-runner in audit mode,
and checks out full history without persisted credentials. The event values
reach the script only through `env`. On a pull request the job first asserts
that the checked-out HEAD is the PR merge commit: it has exactly two parents
and the second is the payload's `pull_request.head.sha`, or the job fails
(otherwise `HEAD^1` could be the PR's own previous commit and the gate would
judge only the last commit). The base is then the merge commit's first parent
(`git rev-parse HEAD^1`), and the payload's `pull_request.base.sha` must be
its ancestor; if neither is available the job fails. On a push to `main` the base is
`github.event.before`, and the job fails on an empty or all-zero value (a
branch-creating push has no base). A manual dispatch compares with the
parent. The job runs the base commit's copy of
the script (from a detached worktree of the base) against the PR checkout, so a
PR is judged by the rules it started from, not by rules it edits. Only the PR
that adds the gate runs its own copy.

The script compares the ledger rows at the PR's merge base with the head,
keyed by `(catalog, layer_id, run_id)`. It always reads the ledgers the wave
documents are published from (`build_verdicts.LEDGER_FILES`), and it fails if
the head's `catalogs/landscape/manifest.json` names any other files. It then
checks each row that is added or changed in `winners`, `platform_status`,
`lanes`, `verdict_status`, `alternatives`, `verdict_overturn_when`,
`overturn_protocol` or `open_gaps` and does not belong to the grandfathered
20260922 wave. Such a row passes only
when all of these hold at the head:

- its wave document is registered in `layer-verdict-waves.json`;
- its `run-manifest.json` is registered in `manifests/evidence.json`, lists
  the row and has the sha256 the row stores in `lanes.run_manifest_sha256`;
- each sealed lane return exists, matches the row's `sealed_sha256` and is
  registered with that sha256, and the two lanes come from distinct model
  families;
- the agreement recomputed from the two sealed returns equals the recorded
  one;
- the row's winners equal the chosen lane's `winner_keys`, resolved through
  the wave's sealed packet, and each winner apart from `platform_status` is
  exactly what `record_verdicts.build_winners` writes: the packet candidate's
  repository and recipe reference, that lane's evidence class,
  `why_selected` and `winner_evidence_refs` (normalized against the head),
  the packet pin (else the row's v1 candidate pin, else `unpinned`), and no
  other key.
  The packet is the one the row's run-manifest entry names by
  `packet_sha256`, found through the manifest's `retained_packets` under
  `<sealed_base>/packets/`. `packets/SHA256SUMS` must list it and equal the
  manifest's `packets_sha256sums`. At no depth may the packet carry a withheld
  key: `stars`, `forks`, `watchers`, any key ending in `_at` (except the
  packet's own top-level `checked_at`), `latest`, `prerelease`,
  `pin_behind_upstream`, `newcomer` and the other keys in the policy of the
  tooling PR #124. Without a sealed packet, the row fails closed;
- the published `alternatives` (on the fields the wave document publishes),
  `verdict_overturn_when` and `overturn_protocol` are the ones
  `record_verdicts.py` derives from the sealed returns. `open_gaps` is
  re-checked with the row but its text is not re-derived. The derivation
  reads the canonical repository index the head's landscape manifest names
  (`sources.repository_index`), so it must give the same alternatives with the
  base's index: an index change that alters a changed row lands first;
- a recorded `disagree` row has an adjudication in which judges from both
  lane families agree in both presentation orders with no refuting vote. Its
  sha256 is stored in `lanes.adjudication_sha256` and in the run-manifest
  entry's `adjudication` `{outcome: sealed, sha256}`;
- a recorded `codex_absent` row names a `docs/decisions/` record that carries
  `single-lane-authorization: <catalog>/<layer_id>`, and stores that record's
  sha256 in `lanes.single_lane_decision_sha256`. The record must already be
  at the base with the same bytes, so an authorization lands (and is seen) in
  its own earlier PR; one added or edited in the PR that adds the row fails;
- the row's `verdict_status` is the one `record_verdicts.py` writes for that
  evidence: `recorded` for agreeing lanes, for a disagreement whose sealed
  adjudication chooses a lane and for a `codex_absent` row whose named decision
  record authorizes it, unless no indexed alternative remains; `pending_lanes`
  otherwise. A new-wave row is never `no_selection`. A recorded verdict
  therefore cannot be withdrawn by relabelling its row and clearing its
  winners.

If any of these `lanes` hashes is absent, the row fails.

Every `(catalog, layer_id)` row at the base must still exist at the head, and
there is one row per layer. The head row's run id may not be older than the
base row's (run ids are dates, and the grandfathered 20260922 wave is the
oldest). A row may not move from a new wave back to grandfathered content. A
row may change its run id only to the newest registered wave, and it then
needs all the new-wave evidence above.

Rows, wave documents and the wave registry are compared by their parsed
values, not their bytes. A pure formatting change of a generated wave
document or ledger therefore passes, as long as `build_verdicts.py --check`
passes and no row field value changes. A reformatted frozen wave document
also needs its registry sha256 updated to the new bytes. Such a change is not
a verdict change for the trust-base rule, so a generator format change can
land together with its regenerated documents. Sealed artifacts count by their
bytes.

Any change of a row field value in a non-grandfathered wave needs a new
recorded wave. The gate re-derives `verdict_status`, `winners` (apart from
`platform_status`), `alternatives`, `verdict_overturn_when`,
`overturn_protocol` and `lanes.agreement` from the wave's sealed returns,
packet, adjudication and run manifest, so a changed value of those fields
that those files do not derive fails. A `platform_status` value is checked
against the registered receipts instead. The remaining fields are free-form
within the newest wave and are not checked: `open_gaps` text (a change still
counts as a row change and triggers the checks above, but its text is not
re-derived), and the wave document's `title`, `group`, `overturn_when` (the
handbook fallback) and `checked_at`, which are layer metadata outside
`VERDICT_FIELDS`. A frozen wave's document is compared whole, so these fields
cannot change there. Each row's published `sota_components` come from the
SOTA manifest the wave's registry entry names. The manifest every base
registry entry names, the newest included, must keep its pointer and parsed
value, but a wave registered for the first time brings its manifest with it
unbound. The gate does not stop a PR from rewriting the newest wave's sealed
files together with their registrations, so a new recorded wave remains a
rule for the author rather than a byte-level block. The sealed files are
self-attested: the gate shows that a row is consistent with the lane returns
its wave registers and that their declared families differ, not that a
cross-family review ran (the decision record's accepted residual).

Rows, wave documents, the registry and sealed files are parsed without
duplicate object keys: a duplicate is not equivalent to anything and fails a
frozen document comparison, and a ledger, landscape manifest or registry with
one exits 2. A git command that fails while listing changed paths, reading a
base tree or finding the merge base also exits 2 instead of counting as "no
changed paths" (the merge base falls back to the given base only when git
reports no common history).

Every changed `platform_status` value must be the one
`scripts/platform_status.py` derives for the winner's sealed pin and
evidence refs, not for the head winner's own values: the chosen lane's
`winner_evidence_refs`, and the packet pin, else a pin the base's row
candidates already carry, else `unpinned` (which binds no receipt). A PR can
therefore neither cite an unrelated registered file nor introduce a pin that
matches some receipt to raise a status. A changed value may also rank no
higher than the same derivation from only the cited evidence files and host
receipts that are already at the base with the same bytes and registered
there with that sha256. Evidence or a receipt that raises a status therefore
lands in its own earlier PR, as a single-lane authorization does; a lower
value is not held to the base. A change to `platform_status` alone
needs nothing else; its row is still resolved against the sealed evidence for
that pin and those refs. The newest registered
wave is the only one that may change, and only while the PR registers no newer
wave: a PR that registers a newer wave must leave the base's newest wave's
registry entry (its sha256 included) and document byte for byte as they are,
because once that wave is no longer current `build_verdicts.py --check` checks
only its own rows and sha256 while its document holds every row. For the same
reason a PR registers at most one new wave, and it must be the head's newest
and newer than every base wave, so the only new wave is always the current one
that `build_verdicts.py --check` regenerates. Frozen values
compare type-strictly (`1`, `1.0` and `true` differ), and changed paths are
listed NUL-separated, so a path with a space, newline or non-ASCII byte is not
lost to git's quoting. A PR that changes a verdict row, a wave
or a sealed verdict artifact fails if it also changes the gate's trust base
(`TRUST_PATHS`), so a rules change lands on its own first. The trust base is
the gate script, every repository module the gate and its validators import
(transitively, which brings in `scripts/validate.py` through
`scripts/host_receipts.py`), the rule inputs they read (the lane-provenance
registry `tools/sota-convergence/lane-provenance.json`, the host-receipt and
lane-return schemas) and `validate.yml`. A rule input held inside a data file
counts too: `adoption/manifest.json#/platform_profiles` (which host
os/architecture a receipt's platform binds) changed together with verdict
data fails the same way (`RULE_INPUT_FIELDS`). The tests derive the list
rather than restate it: one walks the modules' imports with `ast`, and one
records every file opened (a `sys.addaudithook`, in a subprocess) while the
gate judges a fixture that reaches every row path and while the validators
check this checkout. Every head-side file the gate reads must be a
`TRUST_PATHS` file or verdict data the gate binds (`HEAD_DATA_BINDINGS`
names what binds each class), and every code, schema or tool-registry file
the validators read must be a `TRUST_PATHS` file. The validators' catalog
reads are data: they can only add failures to the gate's own verdict. A base
file that exists but cannot be read or parsed, and a base tree that cannot be
listed, exit 2 instead of counting as absent.
Whenever a row, a wave or a file under
the sealed verdict artifacts, `catalogs/landscape/` or
`catalogs/sota-convergence/` changes, the job also runs `scripts/landscape.py`
and `build_verdicts.py --check`. Run it locally with:

```sh
python3 scripts/verdict_review_gate.py --base origin/main
```

The workflow's `pull_request` trigger adds the `edited` type to the default
three, so a PR whose base branch changes runs again, and the job fails closed
on any `pull_request` event whose base branch (`GITHUB_BASE_REF`, passed
through the step's environment) is not `main`. A PR first judged against
another branch and then retargeted to `main` therefore cannot merge on its
earlier green run. The merge commit's first parent, which the gate compares
with, must also be a commit on `origin/main`, so a merge commit still built on
a branch that merely contains `main`'s tip fails closed.

After a retarget, the `edited` run checks out the merge commit still built on
the old base. This was measured on 2026-09-23 with throwaway PR #143, and the
decision record has the run IDs. The gate therefore fails once, and re-running
the job cannot help, because a re-run keeps the same commit. Close and reopen
the pull request, or push a commit, to rebuild the merge commit on `main`; the
next run judges it.

The job runs the head's own copy of the gate only when the
base has none and this change adds `scripts/verdict_review_gate.py` (the
bootstrap PR); a base without the gate otherwise fails closed.

One residual is accepted. A pull request runs the job definition from its
own `validate.yml`, so a PR that rewrites this job's step can disable the
check for itself. The tests that pin the job's shape
(`tests/test_workflow_hardening.py`) and the gate's rules
(`tests/test_verdict_review_gate.py`) are the head's copies too, so such a PR
can edit them in the same change. No `pull_request_target` or `workflow_run` job is added,
because the strict zizmor gate rejects those triggers, and ruleset-required
workflows exist only for organizations. The decision record lists the
mitigations and the overturn.

`.github/main-ruleset.json` adds `verdict-review-gate` to the required checks.
The coordinator applies it with the ruleset PUT above after this change
merges. The decision record is "verdict-review-gate (2026-09-23)" in
[`docs/decisions/2026-09-22-github-automation-closure.md`](decisions/2026-09-22-github-automation-closure.md).


## Automation closure, 2026-09-22

The closure record
[`docs/decisions/2026-09-22-github-automation-closure.md`](decisions/2026-09-22-github-automation-closure.md)
holds the evidence, alternatives and overturn comparison for each item.

- **Repository settings (applied by the coordinator, before/after GETs in the
  record).** CodeQL default setup configured (a fresh
  `gh api repos/seathatflowsinourveins/native-agent-stack/code-scanning/default-setup`
  GET at 2026-09-23T04:47:34Z returned `state: configured`, languages
  `actions`, `csharp`, `go`, `javascript`, `javascript-typescript`, `python`,
  `rust`, `typescript`, `query_suite: default`, `schedule: weekly`,
  `updated_at` 2026-09-23T04:40:46Z; first run 35815088202; the
  first-analysis alerts were resolved in #104,
  [`docs/decisions/2026-09-22-codeql-first-analysis.md`](decisions/2026-09-22-codeql-first-analysis.md)); Dependabot security
  updates on; Actions `sha_pinning_required: true`; squash-only merges with
  auto-merge allowed and branches deleted on merge; immutable releases on;
  private vulnerability reporting on.
- **`security-scan.yml`.** The `osv-scanner` job (OSV-Scanner 2.6.0,
  checksum-verified) scans every lockfile and manifest listed in
  `.github/osv-scanner-lockfiles.json` with `--no-resolve` and fails on any
  vulnerability not ignored in `.github/osv-scanner.toml`; it runs on every PR
  (a required check in branch ruleset 23739774). Off PRs it keeps its SARIF as
  an artifact that the tool-free `osv-sarif-upload` job uploads (category
  `osv-scanner`). `tests/test_osv_lockfile_coverage.py` fails when a
  tracked lockfile is missing from the list. Its `excluded` list may name only
  a deliberately vulnerable test fixture, with a reason and an evidence path;
  today it lists three gap-wave-2 DVC-lock evidence fixtures under
  `evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance/raw/`
  (captured dependency lists from an isolated probe environment, not a shipped
  dependency). It no longer lists the grype positive control for gap
  ci-supply-chain[13] (urllib3 1.26.4, `tests/test_grype_known_cve_fixture.py`):
  that fixture is retained as
  `blueprints/gap-wave2-20260923/grype-known-cve-fixture/requirements.txt.fixture`
  -- a name no manifest/lockfile scanner recognizes, so it needs no exclusion
  (the test copies it into a fresh temp dir as `requirements.txt` immediately
  before invoking grype, never into the repository tree). The `zizmor-online` job
  (push/schedule/dispatch) reuses the hash-locked zizmor with its online
  audits in a `contents: read` job; the tool-free `zizmor-sarif-upload` job
  uploads its SARIF (category `zizmor`); findings do not fail it. The
  offline zizmor PR gate in `validate.yml` is unchanged.
- **Gates.** `dependency-review.yml` fails on high advisories;
  `supply-chain.yml`'s grype scan fails at `--fail-on high` with the reviewed
  `.grype.yaml`; Scorecard SARIF goes to code scanning.
- **Target main ruleset.** `.github/main-ruleset.json` adds `dependency-review`
  and `osv-scanner`, keeps `strict_required_status_checks_policy: false`, a
  `code_scanning` rule for CodeQL (`security_alerts_threshold:
  high_or_higher`, `alerts_threshold: errors`) and `allowed_merge_methods:
  ["squash"]`. The coordinator applies it with the PUT above after this change
  merges. `required_signatures` is left out (keep-but-compare): on agent-lab
  (2026-09-23) it blocked PRs #19 and #20, whose branch commits were unsigned,
  although GitHub signs the squash merge; removing only that rule unblocked
  them. Add it after every writer signs commits and one signed PR merges
  under it. Strict up-to-date checks stay off: with auto-merge and no merge
  queue (unavailable for this personal repository), strict mode stalls every
  open PR on a manual branch update whenever `main` moves, this host runs many
  concurrent PR sessions, and no `main` failure has been traced to merge skew.
  Overturn: a `main` failure traced to two PRs merging close together.
  `can_approve_pull_request_reviews` is owned by another session's #95 and is
  not part of this target.
- **Releases.** `publish-catalog.yml`'s tag-only `release` job (see
  "Publication on tags") creates an immutable release with the attested
  archive and SBOM attached at creation.
- **Kept as is.** harden-runner stays in audit mode; Renovate stays deferred;
  gitleaks stays the required secret gate because non-provider patterns and
  validity checks are not free here; the Socket Security app's PR checks are
  advisory and not required; no paid or SaaS service is needed.
