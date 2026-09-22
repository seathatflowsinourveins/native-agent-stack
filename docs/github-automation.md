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

The active [main ruleset](https://github.com/seathatflowsinourveins/native-agent-stack/rules/23739774)
requires the always-running `validate` and `token-report` jobs from GitHub Actions
(app ID 15368). Its reviewed configuration is [main-ruleset.json](../.github/main-ruleset.json).
It adds no human approval count, strict up-to-date requirement or bypass actor.
Native path-filtered and manually dispatched checks are not global requirements.
Require native acceptance separately when its capability changes. No merge queue
is enabled; add `merge_group` support before adopting one.

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
  --source-digest <sha>
```

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
