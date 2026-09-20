# GitHub automation for the native research foundation

Use GitHub to maintain reproducible recipes and qualify selected changes. The
useful result is a working research task, current instructions or a recoverable
artifact. A green PR alone establishes only the checks that actually ran.

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
other runs use a unique run ID. Only the two short, read-only validation workflows
cancel superseded PR runs. Native trials retain their existing completion and
artifact/cleanup behavior. PR validation and validation after integration are
different revision checks; branch-push duplication is removed.

This uses GitHub's [branch/path filters](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
and [native concurrency controls](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
The configuration expresses intended scheduling. Confirm actual run counts on
the first PR/update/merge; local static analysis is not hosted scheduling evidence.

## Upstream updates with limited noise

[Dependabot configuration](../.github/dependabot.yml) checks GitHub Actions weekly
on Monday at 09:00 UTC, groups minor/patch updates and limits simultaneous version
update PRs to two. Major versions remain separate. This config takes effect after
it reaches the default branch. It does not enable repository-level security-update
settings or auto-merge, and it does not update every version in the grand catalog.

Retain full commit-SHA action pins and their release comments. Dependabot supports
updating these references. Review release/source changes, run the affected upstream
or native checks, and update the reviewed hashes in `manifests/evidence.json`.
An initial bot PR may correctly fail those hash checks until the changed source is
reviewed and registered. Do not remove integrity checks or add a privileged
untrusted-PR writer merely to make the bot's first check green.

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
Assign this maintenance responsibility either to the existing Codex task or the
GitHub workflow before scheduling it; avoid duplicate catalog maintenance.

Keep deterministic checks in supported Actions and native commands. Agent-written
summaries do not substitute for returned test output or separate observation.
Cloud engine authentication and billing are distinct from local Desktop sign-in;
do not transfer a native client's credential store.

## Publication and practical acceptance

A future repository ruleset can require the always-running `validate` and
`token-report` jobs. Do not require a workflow that path filtering can prevent
from starting. Require native acceptance when its capability changes. Configure
review requirements to match the actual maintainers; this guide changes no remote
rules, approval counts or branch permissions.

[Artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
can later identify the producing workflow and revision for a published catalog or
evidence bundle. They prove provenance, not the truth or adequacy of its claims.

For ecosystem usefulness, exercise a representative native Codex/Claude research
task and inspect its result, retrieval sources, continuity and complete available
usage. Preserve its baseline and quality criteria. GitHub fixture results do not
establish current-session activation or causal token savings. Apply the
[acceptance evidence policy](acceptance-evidence-policy.md) throughout.
