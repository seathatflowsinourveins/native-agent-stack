# Native workflow routing and recorded skill lifecycle (2026-10-06)

Status: implementation for draft review. No host application or readiness claim.

The round-2 decision separates routing from pins. A task selects existing skills,
roles and native harnesses through `adoption/workflow/manifest.json`; the four
referenced stores continue to own their identities. The manifest does not copy
commits, trees or skill hashes. A deterministic renderer produces native agent
frontmatter, foundation path rules and a readable routing table. Saved workflow
scripts remain unchanged. Their selected-row argument and Skill-packet consumer
has not been demonstrated; packet-dependent routes remain inert previews.

The north-star action is sourced research and complex-system implementation for
the US-equities research and historical-simulation foundation. Numeric, risk and
order state remains deterministic. Broker capabilities remain with their owners.

## Sources and demonstrated gap

- [Claude native subagents and preloaded skills](https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents):
  YAML frontmatter supplies startup skills; missing or disabled skills can be
  skipped. A role with neither a preload nor Skill cannot deliver a skill route.
- [Claude dynamic workflows](https://code.claude.com/docs/en/workflows): the
  coordinating script has no direct filesystem access. It receives supplied
  arguments rather than reading this manifest itself. The round-2 installed
  2.1.291 interface has no per-call skills argument, so role variants bridge the
  demonstrated preload gap using the supported frontmatter format.
- [Claude path-scoped memory](https://code.claude.com/docs/en/memory#path-specific-rules):
  native `paths` frontmatter triggers on matching Read, Write and Edit operations.
- [Claude 2.1.291 changelog](https://github.com/anthropics/claude-code/blob/v2.1.291/CHANGELOG.md):
  client-version claims are scoped to the observed client; SDK-bundled versions
  remain separate qualification targets.
- `native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:adoption/agents/claude`,
  `tests/test_install_claude_profile.py:1289-1346`, and
  `tests/test_token_e2e_preregistration.py`: preserve the five pinned base roles;
  variants inherit their base's held/evidence-sentence classification.
- `native-agent-stack@ecfa1127:docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md`
  and `adoption/hooks/claude/README.md:12-26`: context-injecting hooks stay held
  until the upstream-harness comparison passes. The relaxed recording lifecycle
  does not reverse that evidence-quality order.
- `openai/codex@a956835d020762cb2b570053af06f643a11c0ecc:codex-rs/hooks/schema/generated`
  and [Codex hooks](https://developers.openai.com/codex/hooks): native event output
  formats and trust apply independently. A hook that never ran cannot be a scored
  no-gain arm. Host trust/application is outside these foundation changes.
- `native-agent-stack@ecfa1127:tools/adoption/install_skills.py:137,210-214` and
  `blueprints/runtime-workers/skills/README.md:88-94`: reused entries inherit
  codex_enabled/claude_listing metadata and held/pruned installation state;
  implicit policy remains upstream metadata, and runtime enforcement is distinct.
- The existing role tests use [PyYAML.safe_load](https://pyyaml.org/wiki/PyYAMLDocumentation#loading-yaml).
  Routing verification reuses that maintained reader rather than a new YAML
  parser. CI provisions checksum-locked official wheels; this is integration
  support, not new upstream test acceptance.
  Freshness and catalog-publisher workflows are owned by open PR642 at9bcbc77f;
  their three dependency steps are a prepared owner handoff and landing gate,
  rather than edits to another owner's files. Main Linux/macOS prerequisite
  changes and the shared checksum lock are in this foundation draft.

## Current routes and pending dependencies

Only references that resolve against the current stores enter executable rows.
Unregistered trials retain names and reasons as pending dependencies. Their
channels are inert until the store entry and Tier B record exist. The validator
rejects a pending or skill-less route presented as deliverable. Pending role and
path-rule previews are kept outside the active native registries.

The pending set includes native-stack-research until its lifecycle registration
lands, hf-cli until its vendor-generated source is recorded, and the dagu, gh,
EdgarTools and Alpaca trials. Existing incumbent routes can remain usable in
other lanes; a pending SDK consumer does not silently certify native arguments.
S11's runtime owner performs that integration and acceptance.

The S1 routing draft does not introduce executable worker copies, unregistered
first-party skill copies or duplicate evaluation recipes from historical plan
evidence. Their original pinned evidence remains unchanged. Native-stack-research
waits on its lifecycle owner/#719, and the runtime consumer belongs to S11. The
SDK channels remain inert until that owner qualifies actual argument delivery.

The routing hook's production channels remain description plus existing native
discovery; a root AGENTS.md pointer requires its shared-lane review. The proposed
hook is a passive PR artifact until B13 and the command-center ACK. No foundation
change installs a hook, changes host permissions or updates global client state.

## Preload variants and held tool-grant inputs

Each variant preserves its pinned base body byte for byte. Its name, task-specific
description, preload and explicitly authorized tools identify the routed task.
Evidence sentences follow the base role's classification. Security review also
preloads variant-analysis. A skill-grant role carries Skill and an imperative
packet naming the required skill in its proposed routing definition. Its role
stays outside active registries until an accepted native caller forwards that
packet; validation of text is not evidence of delivery. Roles depending on preloads run as unnamed
children; the preload-dependent builder is not presented as a teammate route.

The newer HOLD-TOKEN-CLIENT and SERENA-HOLD directions defer P0-1 tool grants
to the command center's ordered clean-install plan. This PR preserves each
base's tool grants byte for byte; only the passive packet-skill proposal adds
Skill. Pure token-tool variants are withdrawn and the existing pinned researcher,
evidence reviewer and verifier remain the route sources. Security's task-specific
variant changes its preload, with its base tool grants unchanged. Prior grant
proposals remain private plan inputs in exact durable stash
91c481b8d6aaa1c6bea3507c6eda1b9d50a1e05f; they are not approved or deployed here.
Per-role organic before/after tool-use counts are a separate native measurement,
not an inference from frontmatter or a global count assigned to each role.
The supplied census does not contain per-role counts or eligible-child denominators;
the [before/after tables](../../adoption/workflow/role-tool-measurements.md) therefore
keep before values unknown and after values pending. This is a measurement gap,
not a completed S7 usage gate. The token-tool grant gate remains held; this PR
continues the supported preload, routing and foundation path-rule work.

The first post-hold local suite exposed three historical assumptions: preload
eligibility came from a dated table instead of the lifecycle store, the active
dispatch table named a passive role, and a mutant assumed an optional fixture
container existed. The checks now read current kept/trial listing metadata,
the passive role is absent from the active table, and the mutant initializes its
container before injecting the same invalid nested value. No runtime gate was
relaxed. The context-mode security check also receives its existing installed
module explicitly; the first missing-module skip is retained separately.

The six later source/candidate rows below belong to this dated decision, with
a back-reference to the [September25 decision](2026-09-25-skills-trial-and-usage.md).
Its entire current-main table remains byte-for-byte unchanged (A17); the current
find-skills listing/implicit policy is retained. Candidates are leads, not adoption.

| Skill | Source | State | Use and unresolved gate |
| --- | --- | --- | --- |
| variant-analysis | trailofbits/skills@0cc1c73 | existing trial | Security preload for variants of a confirmed finding; organic usage remains measured separately. |
| writing-for-agents | mattpocock/skills@c55ee46 | existing trial | Preload in the bounded agent-docs builder. |
| dagu | [dagucloud/dagu@5ca5c59f](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/skills/dagu/SKILL.md#L2) | pending | Native hosting name; lifecycle registration and per-host availability remain gates. |
| EdgarTools | [dgunning/edgartools@1e7a61b3](https://github.com/dgunning/edgartools/blob/1e7a61b3a142dbf5d19bc82444f85239c1786348/edgar/ai/skills/core/SKILL.md#L2) | pending | Native case-sensitive SEC-filing name; lifecycle registration and per-host availability remain gates. |
| alpaca-broker-money-precision | [alpacahq/alpaca-skills@39111abe](https://github.com/alpacahq/alpaca-skills/blob/39111abee6b60af7c11d40b5fc892dfc4fd791a4/skills/broker-api/money-precision/SKILL.md#L2) | pending | Exact monetary arithmetic; deny-set ruling and lifecycle registration required. |
| alpaca-broker-rate-limits-resilience | [alpacahq/alpaca-skills@39111abe](https://github.com/alpacahq/alpaca-skills/blob/39111abee6b60af7c11d40b5fc892dfc4fd791a4/skills/broker-api/rate-limits-resilience/SKILL.md#L2) | pending | Bounded retries/rate limits; deny-set ruling and lifecycle registration required. |

Source review found that checking only expected artifacts missed stale active
roles after a pending/retired transition. The renderer now compares finite owned
filenames across active and passive directories and refuses stale files. A reviewed
lifecycle change removes only those identified files; shared variants are retained
when another row still requires them. Output publication stages complete bytes and
uses Python's native os.replace per file. It is not atomic across the batch: a later
failure leaves complete old/new files, is detected by --check, and is recovered by
rerendering. Unknown native files are never classified as owned or deleted.

Stage-required and coordinator-only skills explicitly partition canonical skill
references. Native plugin aliases name their existing component source. Active
lanes enforce held/retired state and client eligibility; Anthropic's Claude-only
skill-creator cannot silently become Codex's different built-in source. Unknown
nested routing fields are rejected rather than used as a second pin store.
Foundation rules use explicit owned roots; broad AGENTS.md/SKILL.md globs that also
match trading files are excluded.

## Lifecycle and budget boundaries

Tier A recording is fail-open, state-based, deduplicated under a lock and audit
only. It inspects public skill identities and safe metadata, not authentication
stores. Async proposals and an unchanged-state fast path keep it off the hot
path. Metadata status runs only after a detected change and cannot start a fresh
model session. Bytecode caches are excluded from skill-state comparisons.

Tier B reconciliation records upstream installs in the existing skill manifest.
The vendor-generated Hugging Face skill records its generator and installed
bytes separately from the one-newline-different mirror; no Git tree is fabricated.
Tool-coupled source moves follow their binary release, with drift reported and a
reviewed native reconciliation path. Permission-deny retirement is a separate
owner/user action, not implied by this record.

Live catalog checks use actual client evidence. Claude's character budget is
floor(window × the client's bytesPerToken × its listing fraction), and native
truncation signals take precedence over a guessed conversion. Codex's rendered
catalog uses its native charging rule; raw skills/list alone lacks implicit-policy
and truncation fields and cannot certify the effective catalog. Unknown source
or freshness stays unknown. Declared manifest sums are descriptive metadata.

## Preregistered readiness and comparison criteria

A fresh run starts after the relevant skill/plugin change. Compaction-carried
catalogs are stale. Blind roles and agents unable to load their routed skill are
excluded from rate denominators and separately counted as inert/propagation gaps.
Organic means the typed user prompt and user-authored launch prompt name no tool,
skill, agent or harness. Native preload, hook, packet and SDK channels are reported
separately from user text.

For each deployed row and lane, the native batch has at least five matched
outcome-only prompts and five adjacent negatives. Deterministic delivery is N of N,
including every preload in at least five children. Probabilistic and measured-miss
loads must reach at least 80% of applicable tasks; false hints must stay at or below
10%. The read-only summarize-failed-runs class and Skill-less agents are excluded
from the measured CI-miss denominator. At least 80% of workflow stages use their
routed agentType, and at least 80% of Codex spawns carry agent_type. There is no
task-pass regression and no native catalog truncation. Budget arithmetic follows
the client, including 200K child windows rather than only 1M coordinators.

A READY lane row then enters a seven-day real-work window: every triggered row
must retain at least 80% organic loads. A failing row returns to NOT READY with its
cause recorded. Native artifacts, not the Stats tab alone, decide readiness.

Contested skills use the unchanged upstream skill-creator paired benchmark and
the authorized native Codex/SDK harness. The baseline catalog excludes the skill
under test; both arms authenticate compliantly and record equal effort. Correctness
must match or exceed the incumbent at no more than 1.10× tokens; ties favor the
maintained source. Hook B13 additionally needs positive controls that the hook
ran, a positive load-rate gain, false hints at most 10%, and no pass regression.
No live hook precedes that A/B. Complete native usage and actual failures remain
retained; metadata or fixture tests are not provider/GPU acceptance.

## Retained source and host corrections

Dated 2026-10-02 evidence stays unchanged. Canonical first-party skill, worker and
evaluation homes belong outside evidence; new outputs receive new registered
receipts. Source snapshots and installed/accepted revisions remain distinct.

Native Dagu and MinerU operations run from an owned non-Git working directory with
absolute state/store locations. Use the native service environment rather than
stripping quotes from an EnvironmentFile value. A quoted path must not turn into
a relative directory in a checkout. MinerU's relative document storage needs a
fixed native server working directory or a verified supported storage setting.
The installed Dagu --help and pinned v2.18.2 configuration source were inspected,
without starting a runtime. `dagucloud/dagu@5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4:
internal/cmn/config/path.go:70-75` calls filepath.Abs on the environment value:
a relative value is resolved against cwd. Supply a known absolute DAGU_HOME through
the supported environment; never derive it by manually stripping one quote type
from a service EnvironmentFile. The timing-based explanation for the historical
stray tree remains an inference, not an observed recreation. MinerU 4.0.10 help and
version returned successfully; an official v4.0.10 tag/release lookup returned404.
No storage flag or source/release qualification is inferred from that lookup.
The command center owns private stray-state cleanup and host deployment after ACK;
this lane never reads, copies or deletes a credential/key file.

| Handoff anti-pattern | Correction and verification rule | Source |
| --- | --- | --- |
| Handing off three pip steps without their referenced unpublished requirements file | The recipient lacked .github/requirements-validation.txt. The owner adds the CC-approved PyYAML lock. Every future patch is checked and applied at the exact recipient head in a throwaway worktree; all referenced inputs are checked and each safe changed step is run, with commands/exit codes retained beside the patch hash. A clean application does not establish runnable jobs. | [Git apply --check](https://git-scm.com/docs/git-apply#Documentation/git-apply.txt---check); native-agent-stack@ecfa1127:docs/lanes.md:94 and docs/acceptance-evidence-policy.md. |

The official current dagu v2.18.2 tag resolved to
`5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4`, while the decision's historical short
pin was different. This is a retained source distinction, not an inferred tag-move
cause or a lifecycle re-pin by the role renderer.

## Vendor candidates and alternatives

Retain vendor-organization candidates instead of deciding by omission:
OpenAI's public-equity-investing/investment-banking plugins, Anthropic's financial
services, Hugging Face's curated plugin and NVIDIA skill-finder. Systematic public
research, connector requirements, engineering quality and comparisons against the
EdgarTools/native-Hub owners need dated per-skill dispositions. Discretionary deck
work is not silently treated as the systematic-research owner.

`alpacahq/alpaca-skills` and the official
[Alpaca MCP server](https://github.com/alpacahq/alpaca-mcp-server) remain read-only
trading-fit candidates. Money precision, resilience and market-data guidance must
be checked against the selected research/paper scope and native broker APIs.
Nothing is installed or enabled before the deny-set ruling. Trading path rules
and broker operation stay with the trading owner.

Read-only primary-source checks on2026-10-06 found the skills repository at
`39111abee6b60af7c11d40b5fc892dfc4fd791a4` (Apache-2.0, last commit2026-08-31,
not archived) and the server at `a82ad1ccb740609abc99e10376e42d8e9c1037a1`
(MIT, last commit2026-09-25, not archived). The server's
[explicit toolsets](https://github.com/alpacahq/alpaca-mcp-server/blob/a82ad1ccb740609abc99e10376e42d8e9c1037a1/src/alpaca_mcp_server/toolsets.py#L52)
include asset queries relevant to read-only fit; its account, trading and watchlist
groups also expose mutations. A general server selection is therefore not a
read-only grant. The pinned tree includes CI and integrity, HTTP-security,
prompt-injection, trust-boundary and paper-integration tests; these were source
observations, not executed acceptance. The trading owner and deny-set ruling
settle any future exposure.

Alternatives were a monolithic router with duplicate pins, uncontrolled blanket
skill preloads, unchanged Skill-less roles, and enabling hints before measurement.
They respectively introduce drift, spend unnecessary context, create inert routes,
or reverse the user's hold-out order. Native formats plus strict references retain
the existing clients and let each future change show its own evidence.

Overturn a route on a broken reference, absent preload, stale catalog, failed
runtime delivery, poorer task outcome, budget/truncation failure or a better
maintained compared owner. Roll back generated routing changes through Git;
recorded history and failed attempts remain retained. The command center controls
ready/landing and all shared-host application.
