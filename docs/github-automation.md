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
change) and a later `adoption-bootstrap` lane (not yet built). None of these
three appear in `main-ruleset.json`'s required status checks; a required check
must run on every PR, and a report-only scheduled lane does not.

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
a fixed-tool pin table (actionlint, gitleaks, syft, zizmor, `nautilus_trader`
vs each `gh api repos/<owner>/<repo>/releases/latest`) to
`$GITHUB_STEP_SUMMARY`, and uploads both as a 30-day artifact. It opens no
issue and writes nothing back to the repository; a maintainer reads the
summary/artifact and decides whether a real lane review is warranted.

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
secret to the job log. This job is not yet in `main-ruleset.json`'s required
checks by default merge policy -- it *is* listed in the required-status-checks
parameters below, pending the coordinator applying the updated ruleset (see
"Ruleset upgrade" below).

`supply-chain.yml`'s `sbom-vuln` job uses syft 1.52.0 (linux_amd64 tarball
SHA-256 `caeedb81fb0491615f1ebd1761e4145d41ee86dd2cc7bf80669f9f5ad9d6133d`,
read from `https://github.com/anchore/syft/releases/download/v1.52.0/syft_1.52.0_checksums.txt`)
and grype 0.119.0, the latest release as of 2026-09-22 (linux_amd64 tarball
SHA-256 `3fa2dc4b924621ab65404cf08d0b8438d896d80ab949c9d5a4ca283c36004c9b`,
read from `https://github.com/anchore/grype/releases/download/v0.119.0/grype_0.119.0_checksums.txt`).
Unlike the other pins on this page, grype tracks upstream's latest release
rather than a fixed version, because it ships its own vulnerability-matching
logic (not just a data feed) and this lane is report-only; the freshness
job's fixed-tool table does not include grype for that reason and the pin
should be re-checked whenever `sbom-vuln`'s own workflow path changes.

Receipts land as workflow artifacts only: `secret-scan-<run_id>` (30-day
retention) and `supply-chain-<run_id>` (90-day retention, matching the SBOM's
longer useful life). Neither report is committed to the repository. The
threshold decision -- whether a grype finding of a given severity should ever
fail a build -- is explicitly **pending**; today both scans are report-only
and a human reads the artifact.

`native-foundation-e2e.yml`'s package set has no dedicated lock file (its
pins live inline in the workflow's `packages=(...)` array); the task that
requested a "SDK lock file" for `supply-chain.yml`'s path filter found none,
so the filter instead watches the workflow file itself.

## Repository policy files

[`.github/CODEOWNERS`](../.github/CODEOWNERS) names the automation maintainer
as the default owner and again for `.github/` and a not-yet-created
`adoption/` directory (reserved for a future adoption-bootstrap lane).
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
published tags without adding a tag-level review requirement. **Neither
ruleset file is applied by this change**; both are coordinator-only, per the
task boundary that only the coordinator regenerates repository-wide settings
after all lane PRs land. Apply and verify with:

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
`catalog-freshness.yml` drift table already covers all five pins (including
`nautilus_trader`) against each tool's latest upstream release, so the gap is
covered by a different, already-built lane rather than by Dependabot.
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
