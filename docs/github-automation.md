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
The weekly time and a nonempty minor/patch group remain unobserved. This does not enable repository-level security-update
settings or auto-merge, and it does not update every version in the grand catalog.

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

As of this writing, the active [main ruleset](https://github.com/seathatflowsinourveins/native-agent-stack/rules/23739774)
requires the always-running `validate` and `token-report` jobs from GitHub Actions
(app ID 15368). It adds no human approval count, strict up-to-date requirement or
bypass actor. Native path-filtered and manually dispatched checks are not global
requirements. Require native acceptance separately when its capability changes.
No merge queue is enabled; add `merge_group` support before adopting one.

The committed [main-ruleset.json](../.github/main-ruleset.json) no longer
describes this applied state: it has been edited ahead of application to add
`secret-scan` and the other rules described in "Ruleset upgrade, 2026-09-22"
below. Until the coordinator applies it, treat `main-ruleset.json` as the
*reviewed, not-yet-applied* configuration, and the "active ruleset" GET below
as the ground truth for what GitHub currently enforces.

The prior state had no rulesets and returned `Branch not protected` for main.
After applying the configuration, a separate `GET /repos/OWNER/REPO/rules/branches/main`
confirmed both required contexts and their expected app. This verifies settings,
not an experimentally attempted blocked merge. GitHub's [rules REST interface](https://docs.github.com/en/rest/repos/rules)
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
CI lock and ruleset; Dependabot owns only GitHub Actions references.

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

Three lanes run on a schedule and never gate a merge: `catalog-freshness.yml`
(Mondays 06:17 UTC, plus manual dispatch with a `max_repos` bound), the
`sbom-vuln` job in `supply-chain.yml` (weekly, plus push/PR when its own paths
change) and `adoption-bootstrap.yml` (weekly Monday 06:47 UTC, plus push/PR
when `adoption/**` or `blueprints/convergence-practice/wsl-native-tools/pins.json`
change; described in full further below). None of these three appear in
`main-ruleset.json`'s required status checks; a required check must run on
every PR, and a report-only scheduled lane does not.

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
findings by severity). It never passes `--fail-on`; nothing blocks a merge on
a vulnerability finding, and no threshold has been decided yet (see below).

## Secret and supply-chain scanning, 2026-09-22

`validate.yml`'s `secret-scan` job runs gitleaks 8.30.1 (SHA-256 verified
against `blueprints/convergence-practice/wsl-native-tools/pins.json`,
`components[name=gitleaks].archive.sha256`,
`551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`) in `git`
mode (full history, `fetch-depth: 0`) and `dir` mode (working tree), both
`--redact`. The redacted JSON report is uploaded with `if: always()` so a
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
below), so nothing about grype's report-only vulnerability-scanning role
exempts its own version pin from freshness tracking.

Receipts land as workflow artifacts only: `secret-scan-<run_id>` (30-day
retention) and `supply-chain-<run_id>` (90-day retention, matching the SBOM's
longer useful life). Neither report is committed to the repository.
`sbom-vuln` is report-only by design -- it never passes `--fail-on`, so a
grype finding of any severity never fails that job, and the threshold
decision (whether one ever should) is explicitly **pending**; a human reads
the artifact. `secret-scan` already fails its own job on any detection (see
above); "report-only" describes `sbom-vuln`'s vulnerability findings, not
`secret-scan`'s.

`native-foundation-e2e.yml`'s package set has no dedicated lock file (its
pins live inline in the workflow's `packages=(...)` array); the task that
requested a "SDK lock file" for `supply-chain.yml`'s path filter found none,
so the filter instead watches the workflow file itself.

## Repository policy files

[`.github/CODEOWNERS`](../.github/CODEOWNERS) names the automation maintainer
as the default owner and again for `.github/` and `adoption/` (the built
adoption-bootstrap lane's own directory).
[`SECURITY.md`](../SECURITY.md) documents scope (a catalog, not a deployed
service), the private-vulnerability-reporting path (falling back to a public
issue without secret detail while private reporting is not yet enabled),
supported refs (`main` and the latest `v*` tag) and `gh attestation verify`
for released artifacts. [`.github/pull_request_template.md`](../.github/pull_request_template.md)
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

## Recorded decisions, 2026-09-22

**Dependabot's `pip` ecosystem is NOT activated.** Dependabot's `pip`
ecosystem discovers ordinary requirements/lock files by name; the checksum
lock actually used here is `.github/requirements-ci.lock`, a name Dependabot
does not recognize as a Python dependency file, and four of the five pinned
CI binaries (actionlint, gitleaks, syft, grype) are curl-downloaded release
tarballs with no manifest Dependabot understands at all. The new
`catalog-freshness.yml` drift table covers all five (actionlint, gitleaks,
syft, zizmor, grype) plus `nautilus_trader` against each tool's latest
upstream release (see "Secret and supply-chain scanning" above for why
grype's own pin is fixed like the others despite `sbom-vuln`'s scanning role
being report-only), so the gap is covered by a different, already-built lane
rather than by Dependabot.
Precondition to revisit: rename `.github/requirements-ci.lock` to a
Dependabot-discoverable name (e.g. `requirements-ci.txt` with a
`--require-hashes` format Dependabot's pip ecosystem parses) and re-evaluate.

**CodeQL is NOT activated.** GitHub's default CodeQL setup needs
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
`nautilus_trader`) and repository rulesets. Dependabot owns only GitHub
Actions references (`.github/dependabot.yml`, unchanged by this batch) --
it does not, and per the decision above still does not, own any Python or
binary pin.

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
action: the ruleset above protects `main`, and only a maintainer with push
access to tag refs can trigger this path — a fork or an unprivileged
contributor cannot cause a publication run by opening a pull request. Treat a
tag push the same as the manual dispatch it extends: it still requires
`github.repository == 'seathatflowsinourveins/native-agent-stack'` and the
job's `contents: read`, `id-token: write`, `attestations: write` permissions
are unchanged.

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

### Secret-scan coverage boundary (2026-09-22)

The first hosted run of the `secret-scan` job was cancelled by its own timeout while
scanning history: every commit re-diffs the 11 MB generated explorer
`docs/ecosystem/index.html`. The job now passes `--config .gitleaks.toml` and
`--max-target-megabytes 2`. The size skip means the generated explorer HTML is
**not** scanned in either `git` or working-tree mode; this is recorded as
incomplete coverage, mitigated because the explorer is built only from repository
sources that are scanned and is rebuilt by `scripts/build_ecosystem.py`.

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
resolution before merge, not something this unit can fix. Local scans on this
host go through the guarded `gitleaks` launcher (memory-capped, one scan per
user); do not raise its limits to retry a failed scan.

## Report-only Actions hardening, 2026-09-22

Three GitHub Actions security lanes were adopted, each report-only (none is a
required check) and recorded in
[`docs/decisions/2026-09-22-actions-hardening.md`](decisions/2026-09-22-actions-hardening.md)
with the exact evidence, alternatives and overturn condition.

**`scorecard.yml` (OpenSSF Scorecard).** Runs `ossf/scorecard-action` pinned
to the full commit SHA of `v2.4.4`
(`2d1146689b8cda280b9bc96326124645441f03bc`, verified by dereferencing the
annotated tag with `gh api repos/ossf/scorecard-action/git/tags/<sha>`) on a
weekly schedule, `workflow_dispatch`, and push to `main`. `publish_results`
is `false` -- results are never published to the public `api.scorecard.dev`
dataset or badge -- and the job requests only `contents: read`; it does not
use GitHub Advanced Security or `security-events: write`. The SARIF report is
retained only as a workflow artifact (`scorecard-results-<run_id>`, 5-day
retention), never uploaded to the Security tab.

**`harden-runner` (step-security).** `step-security/harden-runner`, pinned to
the full commit SHA of its latest release `v2.21.1`
(`e14015d583714f6e62063499dc959a02595150a1`, from
`gh api repos/step-security/harden-runner/releases/latest`), runs as the
*first* step, before checkout, with `egress-policy: audit` (never `block`),
on 14 of the 18 `ubuntu-24.04` jobs. The four exempt jobs are those whose
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
`pull_request` only with `warn-only: true` and `contents: read`; it is not
in `required_status_checks` and never blocks a PR. This repository is
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
(`inputs.max_repos` nonzero) or recorded any `github-freshness.json` fetch
error (`needs.freshness.outputs.upstream_errors != '0'`): a partial fetch must
not be turned into evidence that reads as a complete one.

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
`automation/catalog-freshness` from `main`, and runs
[`scripts/freshness_propose.py`](../scripts/freshness_propose.py) to:

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
   drifted would be misleading. A rebuilt row whose `upstream.latest` came
   back `None` this run (an unfetched or errored repository, not an
   observed change) is excluded from the drift count and reported
   separately as "unfetched" instead of counted as drift. Its claim states
   plainly that the drift is report-only, that no
   `catalogs/sota-convergence/*`, `catalogs/landscape/*.json`,
   `manifests/stack.json`, or `layer-verdicts*` file was selected or
   changed, and that a pin bump needs its own separately qualified receipt
   under `evidence/artifacts/*/` from the existing SOTA-convergence lane
   review -- this job never runs that review itself;
3. register all three new files' hashes in `manifests/evidence.json`
   `files[]` (via `scripts/host_receipts.py`'s `register_file`, imported
   directly rather than reimplemented) and upsert the receipt's manifest
   entry into `receipts[]`, both matched by `path`/`id` rather than list
   position, since neither list's order is assumed stable; and
4. only when `git ls-files` still tracks `docs/ecosystem/index.html`,
   **rewrite** it from the updated evidence (`scripts/build_ecosystem.py
   --write` -- this regenerates the file's actual content, not only its
   registered hash), rehash it, and loop until `--check` passes -- if a
   later change makes the explorer an untracked build artifact instead,
   this whole step is skipped rather than failing.

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
overwritten -- a second, independent guard alongside the single
`${{ github.workflow }}` concurrency group (`cancel-in-progress: false`)
that already serializes every run of this workflow regardless of trigger.
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
states that "the resulting `pull_request` event creates workflow runs in an
**approval-required** state ... a user with write access to the repository
can start the runs by selecting **Approve workflows to run**." The job's
last step prints the PR's URL and this instruction to the job summary. A
repository collaborator with write access opens the PR (or the repository's
Actions tab), finds the pending run, and selects "Approve and run workflow"
-- after that, `validate`, `token-report` and `secret-scan` run and report
as ordinary `pull_request` checks the ruleset actually requires. The REST
API also documents `POST /repos/{owner}/{repo}/actions/runs/{run_id}/approve`,
but its own description scopes it to "a pull request from a public fork of
a first time contributor" -- this repository's evidence PR is not a fork
PR, so whether that same endpoint accepts a GITHUB_TOKEN-created same-repo
PR's pending run is **not established by the documentation** and is left as
a manual UI step here rather than assumed and automated; see the decision
record's overturn condition for what would change this.

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

