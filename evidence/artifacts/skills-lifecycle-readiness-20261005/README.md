# Skills lifecycle readiness — 2026-10-05

This record prepares the existing skills layer for the command center's
13-task landscape sweep. It serves the north star by making research,
implementation and worker skill provisioning recoverable and reviewable.
It selects no new skill and claims no landscape winner.

[inventory.json](inventory.json) records each selected pin, SKILL.md hash,
declared license, lifecycle task, installation, invocation baseline and client
policy. Those source/license fields are existing manifest metadata, verified
against installed SKILL.md bytes; they are not new whole-tree or license reviews.
[checks.json](checks.json) retains returned check summaries and original log hashes.

## Installed coverage

The adoption manifest has 25 selections: five kept, 19 trial and one held.
All 24 active installed selections match their SKILL.md hashes: 23 shared
Claude/Codex copies and one Claude-only paired-evaluation creator. Codex's
bundled authoring creator is a separate implementation. The held browser skill
is absent from both clients.

| Sweep task | Selected skills | Boundary or gap |
| --- | --- | --- |
| skills-research | search-first, iterative-retrieval | Discovery and retrieval; primary-source artifact quality still needs the sweep's comparison. |
| skill-lifecycle | find-skills, Claude skill-creator; separate Codex bundled creator | Discovery and authoring/evaluation overlap; deployment, verification and recording remain repository lifecycle responsibilities. |
| design-intake | None | No general intake selection; frontend-design is scoped visual implementation. |
| architecture | codebase-design | Deep-module vocabulary; broader system architecture remains a comparison gap. |
| implement | modern-python, frontend-design | Python tooling and visual UI; no general implementation selection. |
| test | tdd, property-based-testing | Complementary test-first and whole-domain testing; upstream model/effort advice is not a measured improvement here. |
| debug | diagnosing-bugs | Diagnosis loop; zero Claude baseline does not establish disuse in Codex. |
| review | typesafe-ai, variant-analysis | Typed judgments and known-bug variants are narrower than general code review. |
| security | security-audit, security-best-practices, security-threat-model, codeql, supply-chain-risk-auditor, agentic-actions-auditor, sarif-parsing, fp-check | Overlap is scope-dependent; custom static-analysis rule creation remains a gap after the prior Semgrep skill retirement. |
| ci-pr | gh-fix-ci, gh-address-comments | CI diagnosis/review comments; rebasing and shared evidence registration remain repository workflows. |
| agent-docs | writing-for-agents | Agent documents; no general product documentation claim. |
| browser | agent-browser (held, absent) | No active selected browser skill. |
| mcp-build | mcp-builder | Direct coverage; end-to-end capability still requires a task-specific check. |

Zero invocations are a review signal, not removal evidence. The private T0
baseline has 19 zero-count Claude and 17 zero-count Codex names in the selected
subsets. Claude Skill calls and Codex reads/mentions use different counters;
slash usage is not scanned, and the new layer's exposure before T0 was short.
The existing trial review date is 2026-10-25. Host-only mineru and
native-stack-research are outside this adoption manifest and remain an ownership
gap; this record neither removes nor adopts them.

## Client visibility

Claude 2.1.289's historical native initialization lists 58 names; a successful
model response recalls 54, with an overlap of 44. All 24 active manifest names
occur in both. These are different observations. The earlier “44 of 58 offered”
interpretation is corrected: the comparison does not establish description
eviction. Post-budget descriptions were not captured. The selected installed
descriptions total 8,559 characters, plus 742 for the two extra shared skills.
The current 0.05 listing fraction is retained pending an actual description
diagnostic or native truncation report. Claude documents dynamic budgeting and
the diagnostic on [skill descriptions being cut short](https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short);
the checked client release is [v2.1.289](https://github.com/anthropics/claude-code/releases/tag/v2.1.289).

Codex 0.160.0's read-only `debug prompt-input` diagnostic renders 38 catalog
rows. All 38 descriptions match their current sources, including all 23 active
shared selections and its bundled creator. No selected name conflicts with the
110 disabled rules. Its 6,000-token skills budget exceeds the diagnostic's
expanded-path estimate of 4,181 by 1,819; these are renderer estimates, not model
usage. No model turn ran and no configuration changed. The native renderer and
diagnostic are
[render.rs at rust-v0.160.0](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/ext/skills/src/render.rs#L126)
and [prompt_debug.rs](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/core/src/prompt_debug.rs#L88).

Codex configuration enables/disables skills; it does not override an upstream
`allow_implicit_invocation: false`. That metadata and Claude's
`disable-model-invocation` must be checked for each survivor, independently of
catalog size. See
[skills_config.rs](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/config/src/skills_config.rs#L20),
[host filtering](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/ext/skills/src/provider/host.rs#L147)
and [official optional metadata](https://developers.openai.com/codex/skills#optional-metadata).
No such restrictive metadata was observed in the active selected copies.
Any future client setting adjustment is a proposal for review, not an applied change.

## Worker lifecycle

The worker manifest contains 134 trial rows from 13 sources, including 25
adoption reuse references. Those counts describe a trial catalog, not accepted
or installed capabilities. The shared resolver previously inherited listing
gates but omitted central held/pruned status. In particular, held agent-browser
resolved as a worker trial. The fix inherits central held/pruned status while
preserving a worker's own stricter hold. OpenHands now checks the same eligible
set and retains both manifest hashes: 133 trial rows, one held.

This uses the existing supported Vercel installation path, not a second
installer: [vercel-labs/skills at 7407f389](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md),
the repository's [lifecycle](../../../adoption/skills/lifecycle.md) and the
[Agent Skills discovery/loading contract](https://agentskills.io/client-implementation/adding-skills-support).
The source module is loaded with Python's
[documented importlib direct-file recipe](https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly).
The tests are integration fixtures; they do not qualify upstream skill quality
or a provider-backed worker.

| Consumer | Current evidence | Remaining acceptance |
| --- | --- | --- |
| Reference OpenHands container | Project installation and explicit `/workspace/.agents/skills` loading; shared held gate now tested. | Native worker execution after reviewed survivor installation. The reference installer requires a verified `skills` PATH or an explicit supported CLI path; the isolated Skills 1.7.0 executable exists but PATH lookup failed. |
| Installed OmniRoute runtime worker | User/project loading enabled; 25 direct host skill directories, 23 overlapping worker selections. Public provisioning template and installed script differ. | Install selected worker skills through the lifecycle and observe a fresh conversation; do not infer 134 active skills from the manifest. |
| DeerFlow | Installed v2.1.0 native category loader was inspected. | Category-directory bridge and model-side invocation need separate qualification. |
| GPT Researcher | Installed v3.7.0; upstream skill instructs a caller to use its MCP capability. | Caller skill is not evidence that the Python research runtime consumes the worker skills folder. |
| Inspect | Installed 0.3.273 supports explicit skill directories/tools. | Wiring was not found in the two scoped repository consumers listed below. |
| Harbor | Installed 0.23.0 supports job skill provisioning. | OpenHands SDK adapter's configured skill paths must match Harbor's uploaded directory; fresh model-side consumption remains pending. |

Primary native contracts:
[OpenHands v1.50.1 user loader](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-sdk/openhands/sdk/skills/skill.py#L943),
[DeerFlow v2.1.0 storage](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/skills/storage/local_skill_storage.py#L75),
[GPT Researcher pinned caller skill](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/skills/gpt-researcher/SKILL.md#L1),
[Inspect 0.3.273 example](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.273/examples/skills/task.py#L52),
[Harbor v0.23.0 job skills](https://github.com/harbor-framework/harbor/blob/v0.23.0/docs-mintlify/core-concepts/jobs/skills.mdx#L10)
and [OpenHands SDK adapter](https://github.com/harbor-framework/harbor/blob/v0.23.0/src/harbor/agents/installed/openhands_sdk.py#L61).

Exact local scope: `blueprints/gap-wave2-20260923/foundation__quality-evaluation/inspect_heldout_task.py`,
`blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/inspect-arm/catalog_task.py`,
their supporting directories, and `tools/research/gpt_researcher.sh` plus its
config. The bounded skill-wiring search returned exit 1, no matches; this is
not an ecosystem-wide absence claim. The public installed-worker recipe is
`evidence/artifacts/new-wsl-install-plan-20261002/config/openhands-worker.py:80`;
`install.sh:813` also directly provisions native-stack-worker outside the
skills manifest. That direct provision is an ownership gap, not a new adoption.

## Pending adoption and completeness

The command center owns the existing sweep; it is not duplicated here.
Its initial research discovery output is a lead, not a survivor decision:
candidate hashes and final reviews remain pending. No new adoption, replacement,
benchmark, model acceptance or host install is claimed.

The completeness critic feeds these classes into the next lifecycle-keyed
sweep: native OpenHands/extensions and GPT Researcher sources; Inspect/Harbor
consumer contracts; installed plugin/bundled skills; explicit user-only and
implicit-invocation restrictions; generic intake, broad architecture and general
review; host-only skills and direct launcher provisioning. Catalog statements
of zero browser gaps or an installed architecture pair need reconciliation
with this inventory before the next sweep's inputs are frozen.

Each survivor must receive a pinned full-source/license review, actual SKILL.md
hash and task mapping, then an upstream paired comparison. The maintained
[Claude skill-creator benchmark workflow](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md#L163)
uses paired native workers, upstream grading/aggregation and the native viewer.
Promptfoo is the alternative repository-authorized harness. No custom runner
is introduced. Following PR review, install only with the shared lifecycle,
then capture fresh Claude `-p`, Codex `exec --json --skip-git-repo-check`
from a non-git directory and each selected worker's native discovery/invocation.
