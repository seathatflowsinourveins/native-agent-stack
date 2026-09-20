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
