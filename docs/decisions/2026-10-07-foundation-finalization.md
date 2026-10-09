# Foundation finalization: memory and RAG owners, retrieval models, runtime pins, Mac host changes and readiness dispositions (2026-10-07)

Date: 2026-10-07; corrected 2026-10-09. Lane: foundation. PR base after the single rebase: `aba02ec3456d383bcc2fc72883db098f9be7918a`. Original October 7 selection-input base: `475127d43c1cce70dba5cd31238af4e078fa17eb`.
North-star action: finish the native foundation for US-equities research and
historical simulation, so the broker-specific paper lanes can follow under
`docs/paper-lane-policy.md`.

## Authority and rule

Selection follows the [2026-10-06 upstream-evidence rule](2026-10-06-upstream-evidence-over-local-evaluation.md):
maintainer organization, release discipline, CI at the release tag, documented
role fit, self-hosted deployability and client integration decide; same-model,
same-split benchmarks break ties; vendor numbers inform and never rank. License
is an information column ([harness defaults](../harness-defaults.md#build-on-upstream-as-foundation-platform-and-runtime-workers)).
This record turns the 2026-10-07 [memory and RAG proposals](2026-10-07-memory-rag-source-stacks.md)
(`proposed_source_review`) into selections for the rows below; the catalog
maintainer updates `catalogs/foundation/memory-rag-stacks-20261007.json` status
on landing. The Mac section retains its dated evidence. The October 8 inventory
below records read-only observations on NativeStack2604; those observations do
not rerun the Mac checks, change a runtime pin or qualify a new installation.

**Correction carried:** an earlier same-day relay disqualified OpenViking and
Cognee from the owner role on license. That was wrong under the rule above; the
re-ranked outcome is below and the correction is recorded in the shared memory
page `decisions/correction-license-not-a-gate-20261007.md`.

## Memory and RAG owners

| Role | Owner (pin) | Runner-up | Evidence | Overturn condition |
| --- | --- | --- | --- | --- |
| Cross-session project memory | [ai-memory](https://github.com/akitaonrails/ai-memory) v2.6.0, installed on NativeStack2604; the separate rules, session, code-graph and markdown jobs are assigned below | rohitg00/agentmemory v0.9.30 | Native version and scoped MCP status/query answered on October 8; v2.6.0 source includes the GHSA-7qj3-7wqw-m5w6 global-scope write authorization fix and wiki path confinement (CHANGELOG Security and Fixed sections) | a cited upstream regression or later clean-release review reopens the recommendation; this record does not authorize an upgrade |
| Research hypotheses and experiment memory | [Hindsight](https://github.com/vectorize-io/hindsight) v0.10.2, **WIRE** the research-consumer skill route; preserve accepted bank/service | [Cognee](https://github.com/topoteretes/cognee) v1.6.3 | [Canonical accepted job](../../manifests/landscape.json), `/research_memory_jobs/0`, and [research recipe](../../recipes/hindsight-research-memory.md): verbatim world/experience recall and strict experiment-tag isolation | a better-evidenced same-job replacement or documented host-install impossibility under the [landed retention rule](2026-10-07-clean-upstream-install-finalizes-a-candidate.md); call counts alone never remove it |
| Graph and temporal knowledge specialist | **Defer** [Graphiti](https://github.com/getzep/graphiti) v0.30.2 and MCP mcp-v1.1.0 for this host; no active job is assigned | Cognee v1.6.3 | The pinned library offers bi-temporal edges. [Recipe #839](https://github.com/seathatflowsinourveins/native-agent-stack/pull/839) at `4d8ecef02eb43e1be1266712fe76737b258006f0` records a Mac offline-import integration check and explicitly defers managed-stack installation. No Graphiti tool or named user unit was observed here | a concrete temporal-graph job, supported dependency set and native database/model acceptance reopen adoption; library and MCP versions require separate review |
| Document parsing (PDF exhibits, research PDFs) | [Docling](https://github.com/docling-project/docling) v2.135.0; [EdgarTools](https://github.com/dgunning/edgartools) stays the SEC HTML/iXBRL/XBRL owner | [MinerU](https://github.com/opendatalab/MinerU) mineru-4.0.10-released | Docling parent commit `0d604da` 50 pass / 0 fail; Mac OCR/MLX paths; docling-mcp v3.3.0 | the preregistered Docling-versus-MinerU table comparison (new-WSL architecture row `document-retrieval`, closure c3) favors MinerU |
| Retrieval orchestration | plain [qdrant-client](https://github.com/qdrant/qdrant-client) v1.19.1 | [Haystack](https://github.com/deepset-ai/haystack) v3.3.0 with qdrant-haystack 11.1.0 and docling-haystack 2.0.0 | only the plain client exposes as-of corpus statistics (`IdfCorpusParams`, models.py L1297) with filing-date filters, so BM25 statistics exclude future filings in historical research | a qdrant-haystack release exposing the corpus filter |
| Document store | [Qdrant](https://github.com/qdrant/qdrant) v1.19.2, its own instance and owner, separate from SocratiCode's | [LanceDB](https://github.com/lancedb/lancedb) v0.40.0 | 52 checks pass at the tag; local BM25; snapshots | the one-writer rule refuses a second Qdrant instance |
| RAG evaluation | promptfoo (existing owner) | [Phoenix](https://github.com/Arize-ai/phoenix) arize-phoenix-v20.19.0 | promptfoo already scores context faithfulness, recall and relevance and receives OTLP traces | the first need for persisted traces from runs that are not evaluations |

Specialists on demand: [PageIndex](https://github.com/VectifyAI/PageIndex) v0.2.21
(long text-heavy documents with page references) and
[RAG-Anything](https://github.com/HKUDS/RAG-Anything) v1.4.2 (images, tables,
equations).

Not chosen, with the deciding observation:

- OpenViking v0.4.23: at tag commit `df32bf6e`, "API Effect Tests" failed and "P0 Memory Tests" was cancelled; its README documents no entity or temporal memory.
- MemOS v2.0.34: the tag commit is `[skip ci]` with no checks, and PyPI `MemoryOS` stops at 2.0.33.
- Zep Community Edition: "no longer supported" (getzep/zep README); Letta now lives in letta-code as an agent harness, not a memory store.
- EverOS v1.4.1: strongest tag CI found, but no temporal search and only a third-party MCP.
- LightRAG v1.5.7 and GraphRAG v3.2.0: corpus-wide graphs and query APIs without date filters leak future filings into historical research.
- Opik 2.2.94: an integration job fails at the tag and the self-hosted deployment runs about 14 services.
- LlamaIndex v0.14.25: build and lint fail at the tag.

No independent study ran the released Hindsight, Cognee or Graphiti against each
other with the same model and split; MemoryAgentBench (arXiv 2507.05257) and EvalMem
(arXiv 2609.22231) cover other systems or earlier versions and inform only.

## NativeStack2604 memory roles and maintenance (2026-10-08)

The [sanitized observation record](2026-10-08-memory-roles-live-host.json)
retains returned metadata, commands, scope and failed probes. It covers seven
layers: six are available through native files or answering tools, and Graphiti
is deferred. Availability and a successful metadata read do not establish
retrieval quality, complete capture or restart acceptance.

| Job | Sole owner and observed version | What runs here today | Source |
| --- | --- | --- | --- |
| Durable rules and preferences for Claude Code | Claude Code native auto-memory, client 2.1.295 | Native repository memory directory contains `MEMORY.md` and 46 files; file metadata only was inspected. Claude maintains the index and topic files during native sessions | [Anthropic memory documentation](https://code.claude.com/docs/en/memory), read October 8; [client changelog at the observed source](https://github.com/anthropics/claude-code/blob/602df92bf481ed904533e95c09f740f40aab5aed/CHANGELOG.md), `2.1.295` |
| Cross-session, cross-client project memory | ai-memory 2.6.0 | `ai-memory.service` is active/enabled. Scoped MCP status/query answered; the native lifecycle hooks carry session capture and consolidation. Native consolidation log categories were observed, but this inventory does not certify completed jobs or effective scheduler settings | [v2.6.0 configuration and lifecycle source](https://github.com/akitaonrails/ai-memory/blob/89bd8ded3c1ab8b769cf99417d038ed0364403c8/crates/ai-memory-cli/src/config.rs); [native maintenance skill](https://github.com/akitaonrails/ai-memory/blob/89bd8ded3c1ab8b769cf99417d038ed0364403c8/crates/ai-memory-core/src/routing_skills/ai-memory-learning-maintenance/SKILL.md) |
| Research hypotheses and experiment records | Hindsight API/client 0.10.2; WIRE scoped vendor research routing | `hindsight-research.service` is active/enabled; the accepted `trading-research` bank retains the 15-tool allowlist. Three consolidation operations were recorded, newest completed October 8 at 09:26:34Z. Zero mental models do not negate the accepted research job | [Canonical job](../../manifests/landscape.json), `/research_memory_jobs/0`; [research recipe](../../recipes/hindsight-research-memory.md); [vendor skill](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md) |
| Session continuity through compaction/resume and captured-output retrieval | context-mode 1.0.169 | Answering tools observed. Claude installed-plugin metadata pins `9f3ecc8b0aafd25d3592ffc31e4b02b1767f6089`; its marketplace checkout is `a83c20165125850473e9344421cf7f374201f0fe`. The separately observed Codex plugin source checkout is `6f0cc6841c687e754059f36714a11233fda1a02b`. No checkout/registration check establishes running-bundle equivalence | [Release source](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/session/db.ts), with per-client metadata separated in the JSON |
| Structural code graph | codebase-memory-mcp 0.11.0 | Native `--version` and paged `list_projects` answered. The vendor's per-account daemon owns shared watchers and indexing while clients are connected; a listed project alone does not establish exact-path coverage | [v0.11.0 README, Auto-sync and Session Coordination Daemon](https://github.com/DeusData/codebase-memory-mcp/blob/8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798/README.md) |
| Markdown search | QMD 2.8.3 (`facd35e`) | MCP status answered: 425 documents, four collections, no vector index. `native-stack-qmd-shared.service` exists but is inactive/disabled. The shared HTTP service remains pending; this metadata call does not prove its transport has been adopted | [v2.8.3 README, MCP Server and Index Maintenance](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/README.md) |
| Optional application entity/fact graph with temporal invalidation | Graphiti v0.30.2; MCP mcp-v1.1.0 | **Defer.** No Graphiti namespace in this client's exposed tools and no Graphiti entry in the named user-unit root. A host-wide package absence is not claimed | [library source](https://github.com/getzep/graphiti/blob/eaa4128681bc53487138a4bbc22d58336ebe70d2/graphiti_core/graphiti.py); [MCP dependencies](https://github.com/getzep/graphiti/blob/11538f6d45561bcce9a4400b374fb2dc533dccb6/mcp_server/pyproject.toml) |

Current instruction files remain authoritative. Durable preference/rule
corrections use native Claude memory and the applicable instruction file;
existing ai-memory profile pages remain historical retrieval evidence. ai-memory
owns project/coding events and decisions. Hindsight owns the already accepted
research-hypothesis and experiment-record bank, with world/experience verbatim
recall and strict experiment-tag isolation. context-mode owns session captures,
codebase-memory the structural graph, and QMD markdown retrieval. These jobs
remain distinct; no existing store is migrated or deleted by this record.

Selection/retention follows the [landed October 7 rule](2026-10-07-clean-upstream-install-finalizes-a-candidate.md):
low use first prompts a vendor installation/routing check. Component removal
requires a better-evidenced same-job upstream replacement or evidence that its
official installation cannot work on this host. Invocation counters inform and
do not gate readiness. No such removal evidence is supplied for Hindsight or
Graphiti; Hindsight is WIRE and Graphiti DEFER.

### Invoke-rate evidence and default-routing dispositions

The disposition evidence is now bound to two [retained private-host-state producer snapshots](memory-adoption-835/README.md):
`5de97cf238b3d28aa9f7d5110a05857204a847b0c75cda8971de8e142e362e36`
(generated 2026-10-08T23:42:51Z) and
`8682d1d326f2979802efa32d156d9db14dba3ce04273328b6b48a0e227533ac7`
(generated 2026-10-09T00:31:25Z). Each is its own rolling 24-hour window.
The [JSON record](2026-10-08-memory-roles-live-host.json) binds every decision to
the exact source hash, snapshot bucket, calls, distinct identities and that
bucket's denominator. Its `adoption_evidence.reconciliation.changed_fields`
lists every changed counter for these seven namespaces across all source
buckets/producer layers and every changed role/client population.

The owning Codex identities are bound from the [pinned registry/history excerpt](memory-adoption-835/registry-role-identities.json): memory-h2h `voni/zimu/rumi/revi`, context owner codex-token-parity `novu/dove/zonu`, and code-intelligence owner overlap-token `vuru/luva/lise`. All observed aliases are recorded even when absent from a source window. `wsl-architecture-design` stays a named Claude consumer and `other Claude sessions` is context only. Exact alias/source bindings and separate bucket sums are below; raw thread/session ids and credential values are not added.

Cells below bind **separate source buckets** at 5de97cf2 → 8682d1d3. MCP counters classify invocation only. KEEP is proposed until stage 3 or 4 establishes organic use; WIRE and DEFER do not claim deployment. Exact complete owning-lane sums and per-alias source pointers are in the JSON and machine-checked successor table below.

| Layer | Proposed disposition | Complete owning-lane binding and limits |
| --- | --- | --- |
| Claude native auto-memory | **KEEP proposed** | No native-memory MCP counter; organic source-bound use remains OUTSTANDING |
| ai-memory | **WIRE** | Every memory-h2h alias, both source windows and all named/context Claude buckets bound. Shell routing/inverse/smoke in the vendor packet remains OUTSTANDING |
| Hindsight | **WIRE** | Every memory-h2h alias bound; accepted research job preserved. CC-applied CLI/client routes, inverse, per-client smoke and fresh retain/recall checks remain OUTSTANDING |
| context-mode | **KEEP proposed** | Every codex-token-parity alias bound; source sum 205/4/4 → 276/6/6. Memory-h2h consumers stay separate. Organic usefulness remains OUTSTANDING |
| codebase-memory | **KEEP proposed** | Every overlap-token alias bound; source sum 8/2/5 → 8/2/5. Memory-h2h consumer evidence separate. SocratiCode/Serena structural overlap explicitly flagged |
| QMD | **WIRE** | Every memory-h2h alias and uniform named/context Claude buckets bound; native skill/inverse/client smoke remains OUTSTANDING |
| Graphiti | **DEFER** | No reported Graphiti counter across owning-lane or named/context scopes; null does not mean zero |


Reconciliation keeps the producer populations separate: Codex 841 → 850 and
Claude 63 → 70. The exec-reader denominator changes 286 → 285; it is not mixed
with interactive lane buckets. Producer roll-ups reconcile ai-memory Codex
303/81 → 293/80, context-mode 32093/569 → 31789/579, and codebase-memory
1750/156 → 1769/160. Hindsight 25/16, QMD 41/28, and shared QMD 4/2 stay
unchanged for Codex. Claude's ai-memory 13/6, Hindsight 4/4, QMD 5/5, and
codebase-memory 4/4 stay unchanged; plugin context stays 2453/9. Those roll-ups
check producer consistency; they are not owning-role evidence. The older Markdown
exec context pair 3002/153 differs from the two pinned snapshot pairs 3029/24
and 2910/24. The later read also cites 2981/24 without an attached producer pin.
These figures are not blended, and the 153-to-24 identity discrepancy is not
explained away as a window shift merely because code-graph counts match.

Every changed scalar and its before/after presence is retained in the JSON.
Absent buckets/servers are not assigned measured zeros. In particular, Claude
`other Claude sessions` changes 55 → 66 and `review-replay (transient)` leaves
the snapshot; no causal reclassification is inferred. The fresh snapshot's
new orchestration section does not enter these memory decisions. A difference
between rolling snapshots is not a count of new activity, a performance result
or an organic-use improvement.

The older private-host-state [Markdown capture](memory-adoption-835/INVOKE-RATES-24H-20261008T2330Z.md)
retains its exact 2,438 bytes and SHA256
`86e8a4e0db11846eed1c4e99d5e89321b576cab087aa07676188705de593e541`
as **dated history only**, with its private host-state origin labelled. Its interactive/exec/Claude populations and earlier
query time do not support the disposition table above. No Loki query,
fresh-session model task or product comparison was rerun.

Hindsight's distinct job is already accepted in
`manifests/landscape.json#/research_memory_jobs/0`: retain and recall research
hypotheses and experiment records. The [research recipe](../../recipes/hindsight-research-memory.md)
requires recall types `world` and `experience` for verbatim text and
`tags_match: "all_strict"` for experiment isolation. Synthesized observations
are paraphrases. Recall has no hard time filter and supplies no backtest
point-in-time exclusion. No evidence shows ai-memory replacing that same job.

WIRE reuses the existing bank-specific native registrations at
`http://127.0.0.1:8888/mcp/trading-research/` and loads the unchanged
[first-party memory skill](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md)
only in the named research-consumer scope. The vendor
[Skills + MCP manual route](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-integrations/agent-plugin/README.md)
adds no automatic coding-capture hooks. The shipped portable `mcp.json` points
to Cloud; setting `HINDSIGHT_MCP_URL` alone does not redirect it. Preserve the
accepted self-hosted endpoint and server-side 15-tool allowlist, and verify
native client exposure before claiming the scoped skill is active.

The accepted job, `adoption/manifest.json#/recipe_map/hindsight`, research
recipe, native registrations, service/drop-in/allowlist templates and retained
bank remain dependents. No retirement step is authorized or performed. The inverse of this proposed wiring restores only reviewed client preimages or removes verified transaction-created skill/CLI additions, preserving all existing client registrations, pinned service/drop-in/allowlist and bank data. The precise CLI pin, per-client routes, inverse and smokes are in the [CC-reviewed wiring packet](memory-adoption-835/hindsight-wire.diff.md). Every host step remains OUTSTANDING. The service-retirement inverse is a separate recipe operation and is not used as this wiring inverse.

ai-memory's managed recall/maintenance skills were absent in the inspected
Claude/cross-agent roots. The selected WIRE proposal is project-scoped native
`install-instructions --target CLAUDE.md --compact --skills-agent claude-code`
and `--target AGENTS.md --compact --skills-agent agents`, with the live quoted
`$HOME` data/config parameters. The command writes matching managed skills;
global `install-skills` is an unselected reviewed alternative. No installation,
global-rule rewrite or new model route is applied.

QMD's 823-byte entrypoint is generated by
[`installedSkillStubContent`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/src/cli/qmd.ts#L3339),
not the full runtime skill. SHA256
`bb4664ad7d959f171c8aa5c9575394327d8fc1070b2529bcc5494a0843a7bc1b`
matches both installed entrypoints; native `showSkill` loads the separate runtime
payload. The unregistered first-party plugin route and native bootstrap use
remain installation/routing questions, not inferred absence of the skill.

### Role slots, overlaps and stage-2 memory cost

Stage 1 names one current source choice per distinct role slot. The JSON's
`adoption_stages.stage1.role_slots` binds the choice to its source/evidence,
explicit overlap disposition and using roles. It does not create parallel
defaults or publish the grand-catalog owner's later projection after G5 lands.

| Role slot | Current choice | Overlap disposition |
| --- | --- | --- |
| Native Claude durable preferences | Claude native auto-memory | ai-memory profile pages remain historical context; no competing preference authoring default |
| Cross-client project events/decisions | ai-memory | Hindsight generic coding capture is not enabled alongside it |
| Research hypotheses/experiment records | Hindsight | Research-scoped bank/skill, preserving the accepted job; project coding memory stays ai-memory |
| Session continuity/captured output | context-mode | Continuity/scratch retrieval is not another durable project decision store |
| Structural code graph | codebase-memory | SocratiCode impact/flow/dependency queries and Serena reference navigation overlap this slot. Proposed default is codebase-memory; SocratiCode semantic/context search and Serena source editing/refactoring remain distinct proposed scopes, pending role comparisons. Graphiti's application graph is separate |
| Checked-in markdown retrieval | QMD | Native event/memory stores are not another default markdown-corpus search engine |
| Application temporal fact graph | Graphiti, DEFER | Candidate source choice only; no active parallel default or retirement action |

Stage 2 requires **role/session-bound per-server or tool PSS from native
`smaps_rollup`** before ADOPT-NOW. These seven component figures are currently
**unmeasured**, so this record makes no ADOPT-NOW declaration. Existing accepted
jobs/installed services are preserved. Prefer a supported shared HTTP or
streamable-HTTP copy and load only in using roles; apply `alwaysLoad: false`
only where the installed client supports it. No new client setting is assumed
or written here. Shared backend PSS and per-session frontend PSS need separate
attribution rather than dividing whole-arm memory by a tool count.

The [retained role-MCP trial report](memory-adoption-835/ROLE-MCP-TRIAL-REPORT-20261009.md),
SHA256 `f0afc2c734b3ad1b70e68cd38d3c844c7f4b1338cc030c8fc40fc88db1e53989`,
is private host-state metadata. Its after-task owned-process PSS is A full-set
1,431,973 kB (23 processes), B scout 674,966 kB (12), B supplied-artifact
837,623 kB (16), and C token-parity 947,334 kB (14). Each arm ran once on a
different real task and includes alive subagents/tools. These are whole-arm
observations, not per-component figures or paired measured savings. They do
not fill the missing component PSS values. The report also marks its first
completion token data as lacking independent provider-first-response binding.

ai-memory and Hindsight already expose shared native HTTP services. QMD's
documented shared HTTP service remains pending activation. codebase-memory
shares its daemon/backend but retains per-session stdio frontends. A shared
MCP HTTP transport for context-mode or that code-graph frontend has not been
verified in this record. Native Claude memory has no independent MCP process;
Graphiti has no adopted host process. Those limits stay explicit in the JSON.

The catalog owner retains release/freshness tracking and reopen triggers for
each role slot; G5 publication/identity binding is still pending. No per-role
trial is rerun and no PSS number is inferred from invocation counts.

### Proposed fresh-session checks per client

Run these only after the corresponding routing decision, using a new native
session per client and an ordinary task stated without tool names. They are
future integration/use observations, not executed tests, quality benchmarks or
a restarted comparison. Record the new Claude `session_id` or Codex
`conversation_id`, then observe native Loki tool-result events for that identity.
A registration/status probe does not satisfy task use. Check the answer's cited
source and the vendor operation that did useful work; unsupported, unused and
unknown outcomes stay explicit.

| Layer | Fresh Claude task | Fresh Codex task | Required observation |
| --- | --- | --- | --- |
| Claude native memory | Apply an existing native-memory-only preference to a bounded review, without supplying its value | Apply the published repository rule through the Codex instruction owner | For Claude, record native loaded-memory/file-read metadata and actual application of the preference; a timestamp or the task text is not proof. No observation is attached: organic use unresolved. No Claude-only feature is claimed for Codex |
| ai-memory | Continue a real unresolved project decision from a prior completed session, citing its record | Same task in a new Codex conversation | Useful scoped retrieval and native MCP events; lifecycle capture remains a separate observation |
| context-mode | Research the two pinned source references and retain unresolved points through native compaction/resume | Same task with native Codex compaction/resume | Useful capture/retrieval and restoration; count each session's events once |
| codebase-memory | Trace callers of `scripts/catalog_decisions.py:identity` and explain affected source paths | Same scoped code question | Useful graph traversal, source citations and native events; a project list alone fails |
| QMD | Find the checked-in decision defining foundation evidence and cite exact text/lines | Same markdown question with native runtime skill activation | Actual search and source retrieval from the named collection, counted from Loki; no tool is named in the task |
| Hindsight | Recover the original stored hypothesis/outcome for one real experiment and exclude other experiments | Same research task in a new Codex session after scoped route repair | Useful bank-specific events and byte-equal `world`/`experience` source with `all_strict` tags. Preserve 15 tools; recall supplies no hard time filter. Proposed, not run |
| Graphiti | Continue a code/project-memory task with the assigned owners | Same task | DEFER with no current default exposure or retirement action. A future temporal-graph job needs its own fresh task, useful native events and database/provider results before adoption; none is run here |

### Native maintenance, current execution and proposed cadence

Read-only `systemctl --user list-timers --all` returned 23 loaded timers. The
named user-unit directory also contained 23 timer files and no names matching
these memory layers. That establishes **no observed systemd memory-maintenance
timer**, not absence of native process schedulers. The initial user-bus reads
failed because this lane lacked the bus environment; supplying the existing
runtime/bus address made the read-only commands succeed. No service changed.

| Layer | Vendor-native upkeep | Evidence of execution today | Draft cadence and runner |
| --- | --- | --- | --- |
| Claude native auto-memory | Native session writes, concise `MEMORY.md`, topic-file maintenance and `/memory` review. The client prompts for index shortening near its 200-line/25KB load limit | Memory file presence and installed client observed; no contents or settings read, and no cleanup execution claimed | Event driven by Claude. Weekly operator `/memory` review is proposed. No unattended CLI timer is invented for this interactive operation |
| ai-memory | `memory_lint` / CLI `lint`, `memory_consolidate`, `memory_forget_sweep` / CLI `forget-sweep`, curated feedback and auto-improvement. Its server has persisted maintenance cadence; v2.6.0 defaults enable daily lint/forget sweeps and hourly auto-improvement, while SessionEnd consolidation is opt-in | Active server and answering scoped MCP observed. Bounded journal metadata includes consolidation categories. Historical CLI probes omitted the live explicit `--config` and each timed out after 15 seconds; they do not diagnose the configured service. effective lint/sweep/learning intervals remain unknown. Defaults and old receipts are not current settings | Preserve SessionEnd/native scheduling as the primary runner where confirmed. Draft daily rule-only lint and weekly retention review run native CLI with the live `--config` and `--dry-run`; lint also uses `--no-llm`. Before activation, reconcile them with the server scheduler to prevent duplicate work. No consolidation timer replays completed sessions |
| Hindsight | On-demand `reflect`; observation consolidation; saved mental-model source-query refresh. Mental models support native `refresh_cron` or `refresh_after_consolidation`, with dirty-scope gating and bounded retries | Native consolidation operation completion observed. `list_mental_models`: total 0; refresh operations: total 0. This bank has no mental models to schedule. Reflect/model-refresh execution was not invoked by this task | Accepted research bank, optional maintenance drafts: weekly `memory reflect` uses `--budget low --max-tokens 512`; daily refresh requires a selected model ID and installed native CLI. Prefer either native model cron or the timer, never both. Refresh makes model calls and stores refreshed `reflect_response`; exit zero submits an operation and completion must be observed separately |
| context-mode | Session hooks capture/restore continuity; vendor `cleanupOldSessions` supports age-based session cleanup. `ctx_stats` and `ctx_doctor` inspect health; scoped `ctx_purge` is explicit deletion | Session tools answered; release source and installed source were inspected. No independent retention execution or effective retention age was measured | Session hooks remain the runner. Weekly operator health/continuity review; no automatic purge or invented timer. Destructive purge stays an explicit scoped request |
| codebase-memory | Native daemon watcher incrementally refreshes graphs. `detect_changes`, `index_status`, `check_index_coverage` and scoped `index_repository` support diagnosis/recovery | `list_projects` answered with 50 registered projects. Current watcher activity and exact-path freshness were not independently inspected | Preserve event-driven watcher updates. Draft weekly native `check_index_coverage` for the named project; repair only an observed stale/gapped index. No periodic whole-repository rebuild |
| QMD | `qmd update` refreshes collections; `qmd embed` is optional for a semantic index; `qmd cleanup --dry-run` previews orphan/cache cleanup | Lexical index status answered; no maintenance timer found. Current update history was not inspected. Shared HTTP unit remains inactive/disabled | Draft daily `update` and weekly `cleanup --dry-run` on the explicit lexical index. Review collection update hooks before activation because `update` may execute them. Embeddings remain a separately justified workload |
| Graphiti | `add_episode` performs edge resolution/invalidation; `build_indices_and_constraints`, `build_communities` and `remove_episode` manage graph state. Community updates are optional; these methods do not establish a scheduler | No adopted host job observed. #839's Mac import check is retained at its original scope | No maintenance unit while deferred. Reopen with a named graph job and database/provider acceptance |

The [draft units](../../adoption/drafts/memory-maintenance-20261008/README.md)
contain seven services and seven timers. They call supported native commands;
no scheduler or maintenance implementation is rebuilt. All are guarded by an
absent operator marker, use bounded time/resource settings, and remain files in
this PR. None was installed, enabled or run. Cadences are proposals, not vendor
defaults, measured optima or a new model-use authorization. ai-memory workspace
flags may create a workspace if the name drifts; confirm the exact existing
scope before any preview. Hindsight refresh makes model calls and stores a
new `reflect_response`; it is not read-only upkeep.

Hindsight's native mental-model triggers default to `false` / `null` and are
mutually exclusive. A failed refresh exhausts native retries and pauses further
automatic refresh until successful refresh. See [mental-model scheduling](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/api/mental-models.mdx#L117)
and [CLI refresh submission](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-cli/src/api.rs#L992).
The research agents keep the 15-tool allowlist; draft administrative CLI jobs do
not expand it.

### Graphiti disposition and currency boundary

Graphiti is retained as a specialist candidate because its temporal invalidation
fits an application fact graph. It is deferred because this host has no assigned
Graphiti job or observed managed installation, and #839 establishes an offline
import on another host. The MCP tag identifies a separate 1.1.0 package with
`graphiti-core>=0.30.1` and `openai>=2.41.0`; the root library at that tag is
0.30.1 ([root package at the MCP pin](https://github.com/getzep/graphiti/blob/11538f6d45561bcce9a4400b374fb2dc533dccb6/pyproject.toml#L4)). It does not establish a tested v0.30.2 library deployment. The old
image/dependency observations stay historical rather than being asserted as
today's image inventory. Adoption reopens only with a concrete specialist need,
the supported dependency set and separate native database/model checks.

Installed ai-memory remains 2.6.0. Live release metadata on October 8 reports
[v2.6.2](https://github.com/akitaonrails/ai-memory/releases/tag/v2.6.2), published
20:42:35Z. This discovery is a currency lead, not installation or permission to
change the held runtime. The existing stopped comparison and retained fixture
boundaries are not reopened.

### Completeness critic and acceptance boundary

The refresh checks native files/versions, answering MCP tools, the named user
unit root, loaded timers, bounded maintenance log metadata, operation metadata,
pinned maintainer source and the separate Graphiti recipe. It includes session,
project, research, structural-code, markdown and temporal-graph roles. Docling,
EdgarTools and qdrant-client retain their document-RAG jobs in the dated table;
this task supplies no new parser, vector-store or provider/GPU acceptance.

Unknowns remain explicit: effective ai-memory maintenance settings after the
timed-out CLI reads, complete lifecycle capture, code-graph watcher/freshness,
QMD update history/shared HTTP acceptance, running-bundle equivalence for
context-mode, and Graphiti database/provider behavior. No comparative benchmark
or maintenance/qualification provider call was requested. Native coordinator and
worker provider usage is outside this inventory and remains unknown. Current
role assignment and proposed cadence do not claim
the best retrieval quality or upgrade any catalog readiness state. Independent
designated reads remain part of the landing process.

### G5 catalog cross-reference boundary

Each disposition has its own `g5_binding` under
`adoption_evidence.per_decision_bindings` in the [JSON record](2026-10-08-memory-roles-live-host.json).
All bind [G5 #878](https://github.com/seathatflowsinourveins/native-agent-stack/pull/878)
at `ae6cc2286643822d3a0218136722c69d0127fcd4`, catalog
`catalogs/landscape/grand-catalog-20261008.json`. The exact
[118-row source bytes](memory-adoption-835/g5-grand-catalog-ae6cc228.json) are retained
at SHA256 `ff3b593c34b5f27caba29a915d3ed5443cb3a3d3ebb7e46937277529f0637dc9`.
The catalog owner is **g5-stars-gap (G5 #878)**. A binding resolves only after
that owner publishes the matching row and the published commit/pointer/identity
are bound; this draft is not main or current-host adoption acceptance.

| Decision identity | G5 pointer at ae6cc228 | Binding status and catalog-owner dependency |
| --- | --- | --- |
| Claude native memory — `anthropics/claude-code` | none | **PENDING — row absent at this G5 pin**; g5-stars-gap must publish the native-memory component row and confirm its identity |
| ai-memory — `akitaonrails/ai-memory` | `/rows/7` | **PENDING until G5 lands**; preserve the verified SOURCE-REVIEW/WATCH row, then bind the published commit/pointer |
| Hindsight — `vectorize-io/hindsight` | none | **PENDING — row absent at this G5 pin**; g5-stars-gap must publish the Hindsight row and confirm its identity |
| context-mode — `mksglu/context-mode` | none | **PENDING — row absent at this G5 pin**; g5-stars-gap must publish the session-context row and confirm its identity |
| codebase-memory — `DeusData/codebase-memory-mcp` | `/rows/32` | **PENDING until G5 lands**; preserve the verified SOURCE-REVIEW/WATCH row, then bind the published commit/pointer |
| QMD — `tobi/qmd` | none | **PENDING — row absent at this G5 pin**; g5-stars-gap must publish the markdown-search row and confirm its identity |
| Graphiti — `getzep/graphiti` | none | **PENDING — row absent at this G5 pin**; g5-stars-gap must publish the specialist-candidate row and confirm its identity |

The five null pointers are deliberate pending bindings, not invented row numbers
or global catalog-absence claims. The two present pointers establish source
traceability only. Publication and final identity binding remain independent of
this record's validation and the designated reads.

### Corrections retained in this record

The earlier default-retirement proposal for Hindsight was wrong: it omitted the
canonical accepted research job and did not meet the landed removal rule. The
current head corrects that record to WIRE, retaining all dependents.

| Anti-pattern | Correction and verification | Preventing check |
| --- | --- | --- |
| Treating a library import on another host as current deployment | The earlier Graphiti row used an installation verb; pinned #839 explicitly defers managed installation. The current role is DEFER; no default exposure or retirement action exists | Read the exact recipe head and current native tool/unit state before assigning an active owner; this record |
| Inferring no native maintenance from no systemd timer | ai-memory has native persisted cadence; Hindsight supports model triggers and has completed consolidation operations | Check pinned native schedulers and operation metadata separately from the timer inventory; this record |
| Handwriting observation times | Two future coordination headings were corrected with an append-only notice using the host UTC clock | Obtain heading/receipt times from the native clock or artifact timestamp; coordination correction retained, no timer acceptance inferred |

## Retrieval models

| Role | Selection | Runner-up |
| --- | --- | --- |
| Mac dense embedding (Ollama) | `qwen3-embedding:4b` (Qwen/Qwen3-Embedding-4B@5cf2132a), already serving ai-memory and SocratiCode on the Mac | google/embeddinggemma-2@914f7f89 (needs Ollama 0.40.0 or later) |
| GPU dense embedding (vLLM 0.31.0, RTX 4090) | nvidia/Nemotron-3-Embed-8B-BF16@d1f2f257, already serving NativeStack2604 | nvidia/Nemotron-3-Embed-1B-BF16@c0c9fea9 |
| GPU reranker | mixedbread-ai/mxbai-rerank-large-v2@ca7e1ee4 | Qwen/Qwen3-Reranker-4B@22e68366 (weights total 22.30 GiB with the 8B embedder) |
| Mac reranker (Python pipelines) | jinaai/jina-reranker-v3.5-mlx@3dd4ac90 (CC-BY-NC-4.0, eligible) | ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF@a02f48bb (qmd's existing pin) |
| Sparse retrieval | BM25 in Qdrant | BAAI/bge-m3@5617a9f6 lexical weights on vLLM |
| Visual documents (exclusive ingest job) | nvidia/nemotron-colembed-vl-4b-v2@0ed152d9 | TomoroAI/tomoro-colqwen3-embed-4b@13517a29 |

Each model choice flips on an observable condition: a submitted MTEB result for
embeddinggemma-2 above 93.08 private code and 66.80 private finance; less than
10 GiB free beside the 4090 embedder for the reranker; a frozen SEC-plus-code
query set where dense plus bge-m3 sparse beats dense plus BM25 on nDCG@10.
"Qwen3.8" has no embedding or reranker release (only the generative
Qwen3.8-27B); BAAI/AREX-2 is a generative image-text model; "Jina3.5 MLX" is
jina-reranker-v3.5-mlx above.

## Runtime and SDK pins

Every runtime pin waits for the 24-hour post-tag gate and records tag, digest and
CI at the tag; coupled pins move as one unit.

| Slot | Verdict | Gate clears |
| --- | --- | --- |
| Codex CLI, openai-codex, openai-codex-cli-bin, @openai/codex-sdk | pin-bump together to rust-v0.161.0 | 2026-10-08T15:59Z |
| Claude Agent SDK (Python) | pin-bump to v0.2.164 (bundles CLI 2.1.292) | 2026-10-07T23:53Z |
| OpenHands software-agent-sdk | pin-bump to v1.53.0 (skip 1.51.0) | gate cleared |
| hcom | pin-bump to v0.7.28 after the launch/close/migration rerun; stay on 0.7.27 if the Codex delivery stall (#151) persists | 2026-10-07T22:01Z |
| agentsview (kenn-io/agentsview) | pin-bump to v0.44.0 after a smoke check | gate cleared |
| Harbor | v0.24.0; regenerate install.sh and accept.sh | gate cleared |
| Inspect AI and Inspect Scout | 0.3.277 with 0.5.4, together | 2026-10-07T22:10Z |
| Claude Code | 2.1.293 runs on the Mac since its native self-update at 2026-10-07T18:18Z under `autoUpdatesChannel: "latest"`, the recorded policy (decisions 2026-09-23 item 2 and 2026-09-28 M51); the recorded pin moves after the gate | 2026-10-08T17:18Z |
| GPT Researcher, DeerFlow, DSPy | keep v3.7.0, v2.1.0, 3.4.0 (latest tags) | n/a |
| OmniRoute | keep the v3.8.51 + #15167 + affinity composition; #15167 is still open on untagged release/v3.8.52 | a tag containing `0585aba5` |

## Instruction practice adopted from current client sources

- Claude Code 2.1.277 adds `AGENTS.md` fallback only for a project without `CLAUDE.md` ([changelog](https://github.com/anthropics/claude-code/blob/602df92bf481ed904533e95c09f740f40aab5aed/CHANGELOG.md)). This repository has `CLAUDE.md` importing `@AGENTS.md`; preserve that import or the fallback does not apply.
- The Agent tool takes a per-call `effort` (2.1.292); frontmatter effort remains valid (2.1.267, 2.1.288).
- Claude runs a skill named exactly `verify` before commits (2.1.286); projects provide a `verify` skill that wraps their acceptance commands.
- `omitClaudeMd` (2.1.271) suits blind judges and reviewers.
- [Current official Codex skill documentation](https://developers.openai.com/codex/skills#where-codex-loads-local-skills) specifies `.agents/skills` for user/project skills. This session also discovers codebase-memory from the legacy `%h/.codex/skills/codebase-memory/SKILL.md`; the `.agents` counterpart is absent. Record this observed compatibility and unresolved vendor-led migration, not a claim that the legacy skill is no longer loaded.
- Always-loaded instructions stay a short map (Claude memory guidance: files over 200 lines reduce adherence); procedures go to skills, enforcement to hooks and settings.

## Mac coordinator host changes (2026-10-07; the evidence class is per row)

| Change | Evidence | Rollback |
| --- | --- | --- |
| Codex 0.160.0 → 0.160.1 from `codex-package-aarch64-apple-darwin.tar.gz` (SHA256 `f73527ee…c6314`) | `codex --version` 0.160.1; `codex mcp list` exit 0 | relink `~/.local/bin/codex` to the retained 0.160.0 directory |
| OTel Collector Contrib 0.162.0 (`otelcol-contrib_0.162.0_darwin_arm64.tar.gz`, SHA256 `d5e11974…5f97a`) as a launchd agent, using `observability/collector/collector.yaml` without the Loki exporter and the two workstation-only `http_check` targets | `otelcol-contrib validate` exit 0; health 200 on 14333; Claude and Codex tool, MCP, hook and API events reach `file/events`; Prometheus exporter on 18889 | unload the agent; both clients then drop telemetry as before |
| Chrome DevTools MCP 1.10.1 registered at user level in both clients with `--isolated` | one real `list_pages` call answered in Claude and in Codex (Codex reported 27,333 tokens); both calls appear in the collector with `mcp_server.name=chrome-devtools` | `claude mcp remove chrome-devtools --scope user`; `codex mcp remove chrome-devtools` |
| context-mode marketplace `source.ref` set to `v1.0.169`; Codex `codebase-memory` skill moved to `~/.agents/skills` | readback of `known_marketplaces.json` and the skill at its new location. The installed plugin commit at that tag is not corroborated (#384 audit, 2026-10-07T19:50Z), so this row is a pin request, not a native proof | restore the backed-up file and directory |
| `tools/token-report` refresh | RTK 4,406,580 tokens saved across retained projects (4,288,399 for one project); headroom 20,968 over 30 days; jCodeMunch 0 session calls and 0 saved | read-only |

These are each tool's own estimates, not net provider savings. jCodeMunch is
installed and was not called on the Mac. Under the
[clean-install decision](2026-10-07-clean-upstream-install-finalizes-a-candidate.md)
(#833, rule 4), zero use is an install gap first and never a reason for removal; its
state there is release owed (1.108.332). The ai-memory swap waits for its gate and runs in this order:
1. While 2.5.2 is still serving, take `ai-memory backup --to <dated tarball>`. The
   command is a thin HTTP client that needs the running server
   (`adoption/lifecycle.md` L282-283).
2. Verify the archive by restoring it into a new empty fixture directory.
3. Stop the agent.
4. Copy the 2.5.2 directory to a 2.6.0 directory and run
   `ai-memory upgrade --version v2.6.0` from the copy.
5. Repoint the launchd program and `~/.local/bin/ai-memory`, then start.
6. Run `ai-memory doctor` and an MCP status read from both clients.

Rollback restores the verified backup and the 2.5.2 path.
`claude-plugins-official` publishes no tags and stays unpinned.

## NativeStack2604 readiness dispositions (proposed for the readiness owner)

Amended after #833 (merged 2026-10-07T23:47Z, `36654a81`): READY is now the
source-backed selection, the vendor's installation, and the vendor's own check or
one named operation passing in each client the row applies to. Organic counters are
read and published but no longer a condition (the clean-install decision, rule 3).
The groups below were drawn under the earlier bar; the readiness owner re-reads them
under rule 3. A group-1 row whose only open item was its counters can be ruled final
on its existing install and check evidence.

The 2026-10-05 slot record holds 18 READY and 12 BY_DESIGN of 80 (historical #700
labels). The same day's correction excluded seven slots from READY (ccusage,
command-output, native-clients/codex, session-analytics, alerting, Serena, MinerU);
of those, only native-clients/codex carried a READY baseline label. Under the
2026-10-06 bar (selection, installation, an integration smoke check in each client
and organic counters), the 50 open slots plus native-clients/codex fall into three
groups:

1. **Re-adjudicate with existing evidence:** native-clients/codex (at the selected 0.160.1, then 0.161.0 after its gate), agent-sdks/codex-sdk-and-codex-exec-app-server, ci-supply-chain/syft, code-navigation/serena, code-navigation/structural-search, cross:credential-practice/credential-guard, document-retrieval/tobi-qmd, git-github-automation/git, instructions-skills/engineering-process-skills, instructions-skills/research-skill, instructions-skills/trail-of-bits-security-skills, observation-inference/local-generation-model, observation-inference/otel-collector-contrib, secrets-credentials/betterleaks, semantic-rag/embedding-model, the nine token-efficiency slots (api-docs, code-graph, code-index, command-output, context-supply, doc-conversion, output-compression, repo-packing, structured-data), workers/agent-messaging (2026-10-06 launch-and-close gate), web-research/playwright-cli (2026-10-06 Chrome DevTools fixture), quality-evaluation/harbor-containerized-agent-e2e-runner, observation-inference/alerting (user-accepted Telegram receiver), token-efficiency/statusline (user observation) and durable-memory/memory-owner (ai-memory 2.6.0 after its gate; the head-to-head no longer gates).
2. **BY_DESIGN:** secrets-credentials/credential-custody (private 0600-file practice), token-efficiency/token-lane-carriers (documented holdout), token-efficiency/trace-viewer (traces are off by the 2026-09-26 decision) and document-retrieval/mineru (Docling owns parsing; MinerU is the runner-up).
3. **Fix and smoke on the host:** observation-inference/session-analytics (agentsview v0.44.0), token-efficiency/ccusage, cross:gpt6-harnesses/gpt-gateway (smoke the running composition; the canary is superseded), cross:runtime-workers/agent-runtime-worker (OpenHands v1.53.0), cross:runtime-workers/research-harnesses, cross:wsl-distro/base-distribution (the binfmt unit), git-github-automation/cross-family-review (Claude turn limit), git-github-automation/difftastic and worktrunk (empty print prompt in the staged check), instructions-skills/skill-authoring (rerun after PyYAML provisioning), isolation/sandbox-runtime-srt, mcp-surfaces/mcp-inspector (libnspr4 for the web smoke), observation-inference/grafana (configuration drift), observation-inference/local-model-server, quality-evaluation/inspect-ai (non-relative example path), quality-evaluation/promptfoo, and semantic-rag/code-search. Code search is INTERIM in `evidence/artifacts/ns2604-requalification-20261005/slots.json`. Under #833's table semble is final there, while SocratiCode is install owed: release 1.16.0 with the vendor's plugin, then its own `codebase_health` check. The Mac's semble evidence below does not adjudicate this host's slot.

**Code search (settled by #833):** the two engines have one job each. SocratiCode
serves indexed projects on the local embedding model, and semble serves any other
local or remote repository. On the Mac, semble 0.6.2 is final by the vendor's route
(2026-10-07):
- the uv tool, wheel SHA256 `94110c12…` matching PyPI, with model
  `minishlab/potion-code-16M-v2@e9d2a44c` pinned;
- the vendor's `semble install --type subagent` agent on both clients;
- manual server entries with `SEMBLE_MODEL_NAME` and a per-client
  `SEMBLE_CACHE_LOCATION`, plus `enabled_tools` and `approve` on Codex;
- one named search passing in each client: Claude `mcp__semble__search` exit 0, and a
  Codex `mcp_tool_call` to semble/search with status `completed`.

The host receipt is `~/.local/state/native-agent-stack/evidence/semble-mac-20261007/receipt.json`.
SocratiCode stays installed beside it.

## Readiness verdict

Selections are complete. The foundation is not READY by the clean-install bar until
the fix-and-smoke group clears on NativeStack2604, which is its owner's host work. Offline North Star research was never blocked by these
slots. Paper E2E is pre-authorized and proceeds when its frozen trials pass their
own gates.

## Worker boundary failure

The starred-repository research worker wrote three helper JSON files under generic
names in the shared temporary directory, against its one-file brief, then deleted
them. Preventing check: worker briefs name the single writable path, and the
coordinator verifies that no other path changed (this log).

## Overturn

Each row carries its own overturn condition. A cited upstream regression, a failed
gate or an independent matched result reopens a row; the retained failure
observations above stay in the record when a later release fixes them.

## Combined delta correction — 2026-10-09

This successor correction carries the CC delta at
`c5ce6546da699ca08ecd8a3f83ec52fd2d5802232d8922b35abd5e8acd961e31`
and GPT delta at
`6041041dd85cb7854b9e3ca8cd9389de57cdfb1415acd96965947cda8c45ec0c`
for `7f2dc865cc1ead227621bb23fce8d0c771f22440`. No prior source capture,
whole-arm trial, G5 draft or historical host observation was replayed.

The [registry excerpt](memory-adoption-835/registry-role-identities.json) is
pinned at SHA256 `fc6f5dd30aa8dfa78932f1cb81b11abea311beca3d306927e21cb75f54ec765e`.
It covers memory-h2h `voni/zimu/rumi/revi`, context owner
codex-token-parity `novu/dove/zonu`, and code-intelligence owner overlap-token
`vuru/luva/lise`, including names absent from one or both source captures.
Voni is joined through its canonical thread-registry row and supported stopped
hcom metadata; raw thread identity is hashed. Current relaunch names do not
replace earlier buckets. Context-owner whole-lane sums reproduce
**205 calls / 4 bucket identities / 4 denominator → 276 / 6 / 6**.
Each alias stays separately inspectable; no event-level deduplication is claimed.
Named Claude architecture consumers and `other Claude sessions` context are
now present uniformly for all seven components. Context never proves ownership.

The [Hindsight wiring diff](memory-adoption-835/hindsight-wire.diff.md) records the pinned vendor CLI installer and unchanged project-scoped vendor skill route, with exact byte hashes bound in the JSON. The targets are us-equities-trading's two project roots through PR15 and native-agent-stack's blueprint-scoped roots through #835. User roots and the native repository root are rejected. CLI installation, pre-run binary digest check and two research-cwd get_bank smokes are CC host work; skill additions land through repository review. The full provider/scratch-bank harness is DEFERRED. Every unexecuted landing, smoke, organic retain/recall and +24h role follow-up stays OUTSTANDING. Reviewed repository revert and transaction-specific CLI inverses preserve the existing service/bank/registrations/allowlist and accepted research job.

The [ai-memory/QMD packet](memory-adoption-835/wire-inverses-smokes.md), SHA256
`509d4b65980a5012e4e3b80cab86ffcb8769e06ba3fc3107516e2b774ef6fbc8`,
records upstream inverses, preview/application commands and client checks.
Shell commands use `$HOME`; `%h` appears only in systemd directives. The two
ai-memory maintenance drafts now name the live optional
`EnvironmentFile=-%h/.config/ai-memory/env`. Only the unit property's path and
ignore-errors flag were inspected; no environment-file content was read.

The JSON now records stage 1 candidate/G5 status, stage 2 install/routing/pin/
inverse/PSS/load scope, stage 3 natural fresh tasks per owning lane and named
consumer, and stage 4 hourly capture/role comparisons from T0 to T0+24 h.
All seven candidates remain **PENDING until G5**. Native memory, context-mode
and codebase-memory are **KEEP proposed** because stage 3/4 organic observations
are unexecuted. Accepted KEEP requires a returned role/session/source-bound
organic-use observation in one of those stages. Smoke/inventory counts do not
supply it. This condition leaves the separate #833 READY rule and retention
rule intact; sparse counters do not authorize removal.

SocratiCode impact/flow/dependency queries and Serena references overlap the
structural-graph slot. The proposed default is codebase-memory, SocratiCode is
scoped to semantic/context search, and Serena to source editing/refactoring.
Capability sources are the installed [SocratiCode 1.16.0 vendor manifest/skill](https://github.com/giancarloerra/socraticode/tree/v1.16.0) (skill SHA256 `629aaed8c034787773095475b7086ae1ada99dcec75318ce356da9081c29b2ec`) and its impact/flow tool interfaces, plus the installed [Serena](https://github.com/oraios/serena) initial-instructions/reference interface. Serena's build pin is unverified; these are capability observations, not a paired quality comparison. That routing split is a proposal pending owner review and comparative role observations. No host change or parallel structural default is accepted here.

The canonical JSON `outstanding` array has **50** unique steps: 16 packet steps,
seven each for component PSS, natural-task observations, hourly follow-ups and
G5 bindings, plus Claude-owner binding, both micro reads, current CI, the required
pre-cue tool and explicit CC cue/owner decisions. All are unexecuted. The fix head
is record qualification; it is not host installation or upstream acceptance.

### Machine-checked lane summary

Bucket identities are summed across every registry-bound alias; these sums are
not deduplicated lane identities. Each source window stays separate. The null
native-memory/Graphiti calls do not represent zero use. Exact per-alias counters,
denominators, registry pointers and absent names remain in the JSON record.

| Component | Lane | Baseline calls / identities sum / denominator sum | Reconciled calls / identities sum / denominator sum |
| --- | --- | --- | --- |
| claude_native_memory | native Claude feature; no named native-memory counter | null / null / null | null / null / null |
| ai_memory | memory-h2h | 13 / 2 / 8 | 13 / 2 / 8 |
| hindsight | memory-h2h | 5 / 2 / 8 | 5 / 2 / 8 |
| context_mode | codex-token-parity | 205 / 4 / 4 | 276 / 6 / 6 |
| codebase_memory | overlap-token | 8 / 2 / 5 | 8 / 2 / 5 |
| qmd | memory-h2h | 1 / 1 / 8 | 1 / 1 / 8 |
| graphiti | memory-h2h | null / null / 8 | null / null / 8 |

## Project-scoped Hindsight and both micro corrections — 2026-10-09

The CC selected the unchanged vendor skill as repository content in two research
scopes: us-equities-trading's `.claude/skills/hindsight-memory/SKILL.md` and
`.agents/skills/hindsight-memory/SKILL.md`, and native-agent-stack's
`blueprints/us-equities/.claude/skills/hindsight-memory/SKILL.md` and
`blueprints/us-equities/.agents/skills/hindsight-memory/SKILL.md`.
Each skill is **2,758 bytes**, SHA256
`736dec06d414798f6b17dc078c5ef6204e8802f53cb3a5fb3c306ce08872f08e`,
from `vectorize-io/hindsight@5fc4ce20917b916240cef27c212c387a177f115b`,
`hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md`.
No user root or native repository-root Hindsight skill route is selected.

[us-equities-trading#15](https://github.com/seathatflowsinourveins/us-equities-trading/pull/15)
is draft at **650df14547daf7ac4e86d1f85f167787d94b4f24**. Its only changes are the
two unchanged skill files and a small `SOURCE.json` beside the Claude copy,
binding both copies to the full vendor pin/hash/byte count. SOURCE.json SHA256
`ada3ac1eb18414a22ce05f44ba778c7eda4e2ccc9f9ab924d8c07fce67a478d3`.
The tiny provenance follow-up addresses the CC's PASS-WITH-P3 read at d794e28f
(SHA256 `2ff57f6a7a7788265d3d7f0663f3509de50b49efda26a2c59c0b7ba7edcb2caa`).
Native repository verify passed at the final head: **62/63 tests, one skip**,
19 lane-path self-tests and three permitted paths. Draft review, exact-head
micro/CI and the explicit CC landing cue stay separate. The two nested copies
are included in #835's next head and are byte-identical to that same vendor source.

Claude nested discovery is documented by the pinned 2.1.295 changelog and
official skills documentation, including lazy loading while working on files
in that subtree. Codex's official skills page documents scanning from launch
cwd to the repository root; the CC/L1 source handoff cites `host_roots.rs:138-185`
at `rust-v0.161.0`. A direct source-path API probe hit HTTP403 rate limit;
no version-pinned loader execution is claimed. Actual fresh-session skill
discovery and use remain **OUTSTANDING** after the corresponding PR lands.
Research sessions start in the trading project or the native blueprint subtree.

The dedicated CLI remains a CC host action with no PATH/profile change.
The unchanged pinned installer is hashed before invocation; the downloaded
`hindsight-linux-amd64` binary must match the official v0.10.2 release digest
**be87c63714ff046ac8ed668465ca0c875f94e6ff0a89ed83da7eb387313197af**
**before its first execution**. Official release metadata observed at
2026-10-09T04:01:10Z matches the CC's digest. No binary was downloaded or run
by this lane. The two Hindsight maintenance drafts now call
`%h/.local/opt/hindsight-cli/0.10.2/bin/hindsight` directly, rather than relying
on a PATH addition. Draft installation and maintenance execution remain unperformed.

Both micro reads of **04c4bc278c25913cf7f3dff859dae7e91d8aab4e** are included:
GPT SHA256 `da4e41a4857c4a51d80293bcf4e6a0c9827e22ff29f2cb2d90cfd227b50985b4`
and CC SHA256 `3c886d2f427c58fe4445c8671408a72943bc03b65030724a05cac7f4a604fa61`.
The revised packet's Bash blocks are self-contained and start with
`set -euo pipefail`; failed download, checksum or pre-existing-destination
checks terminate before dependent installation/run or replacement. The reader's
saved offline reproduction and regression fixtures exercise actual command
order with harmless substitutions; they execute no vendor installer or provider.
Those fixtures establish shell control flow, not upstream acceptance.

The CC runs one `get_bank` smoke per client from a newly started research-project
session; Claude's headless form explicitly allows
`mcp__hindsight__get_bank`. The shipped `smoke-test.sh` is recorded once and
**DEFERRED** because it performs scratch-bank writes/deletion and provider/model
work; the CC accepted the two named `get_bank` smokes for rule A. All get_bank,
organic fresh-session retain/recall and hourly/+24 h checks remain **OUTSTANDING**.
The skill inverse is a reviewed repository revert PR; the CLI inverse touches
only its transaction-created dedicated addition. Existing bank/data, service,
MCP registrations and server-side allowlist are preserved.

ai-memory's selected project route uses reviewed `install-instructions` with
the same quoted `$HOME` data/config parameters as the live CLI configuration,
and writes the matching managed skills. Standalone global `install-skills`
is an explicitly unselected alternative, not a parallel default. AM-02/QMD-02
name the transaction inverses; AM-03/QMD-03 name fresh-client retrieval smokes.
The SocratiCode/Serena overlap is now in the stage-1 structural graph row.
The registry excerpt cites immutable `hcom-lanes.json.pre-ram-20261009`, verified
byte-identical to the previously pinned registry source hash
`7094935b8fe668a3004c774941679b1867c3ecc3f8f362f3099221f84f6e45bf`.
Counter snapshots, trial/G5 bytes and all per-alias source numbers remain unchanged.
