# Foundation finalization: memory and RAG owners, retrieval models, runtime pins, Mac host changes and readiness dispositions (2026-10-07)

Date: 2026-10-07. Lane: foundation. Base: `475127d43c1cce70dba5cd31238af4e078fa17eb`.
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
| Optional curated research-bank synthesis | [Hindsight](https://github.com/vectorize-io/hindsight) v0.10.2; **RETIRE proposed for the default coding-client toolset**, retaining the existing service/bank as optional | [Cognee](https://github.com/topoteretes/cognee) v1.6.3 | retain/recall/reflect and maintained mental models fit a dedicated curated research bank. Sparse invocation and zero mental models do not demonstrate that distinct workflow here; earlier release/test results remain historical | a named research execution scope needing curated-bank synthesis, supported scoped routing and fresh organic-use evidence reopen default inclusion |
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
| Optional research memory unit; proposed retirement from default exposure | Hindsight API/client 0.10.2 | `hindsight-research.service` is active/enabled. `get_bank` answered for the research bank. This client's 15 exposed tools match the research allowlist. Native operation metadata records three consolidation operations; the newest completed October 8 at 09:26:34Z. Runtime remains unchanged pending the separate exposure decision | [Hindsight v0.10.2](https://github.com/vectorize-io/hindsight/tree/5fc4ce20917b916240cef27c212c387a177f115b); [research recipe](../../recipes/hindsight-research-memory.md) |
| Session continuity through compaction/resume and retrieval of captured tool output | context-mode 1.0.169 | This session's context-mode tools answered. The installed package reports 1.0.169; its clean source checkout is `6f0cc6841c687e754059f36714a11233fda1a02b`, distinct from the release-tag source pin. No package-version check proves bundle equivalence | [v1.0.169 session database](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/session/db.ts); [observed source revision](https://github.com/mksglu/context-mode/tree/6f0cc6841c687e754059f36714a11233fda1a02b) |
| Structural code graph | codebase-memory-mcp 0.11.0 | Native `--version` and paged `list_projects` answered. The vendor's per-account daemon owns shared watchers and indexing while clients are connected; a listed project alone does not establish exact-path coverage | [v0.11.0 README, Auto-sync and Session Coordination Daemon](https://github.com/DeusData/codebase-memory-mcp/blob/8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798/README.md) |
| Markdown search | QMD 2.8.3 (`facd35e`) | MCP status answered: 425 documents, four collections, no vector index. `native-stack-qmd-shared.service` exists but is inactive/disabled. The shared HTTP service remains pending; this metadata call does not prove its transport has been adopted | [v2.8.3 README, MCP Server and Index Maintenance](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/README.md) |
| Optional application entity/fact graph with temporal invalidation | Graphiti v0.30.2; MCP mcp-v1.1.0 | **Defer.** No Graphiti namespace in this client's exposed tools and no Graphiti entry in the named user-unit root. A host-wide package absence is not claimed | [library source](https://github.com/getzep/graphiti/blob/eaa4128681bc53487138a4bbc22d58336ebe70d2/graphiti_core/graphiti.py); [MCP dependencies](https://github.com/getzep/graphiti/blob/11538f6d45561bcce9a4400b374fb2dc533dccb6/mcp_server/pyproject.toml) |

Current instruction files remain authoritative. New durable preference/rule
corrections use Claude's native memory and the applicable instruction file;
existing ai-memory profile pages remain historical retrieval evidence. Project
events, decisions and project research provenance use ai-memory; session captures
use context-mode, code structure uses the code graph, and checked-in markdown
uses QMD. A separately curated research bank could use Hindsight on demand;
that distinct workflow is not established by today's inventory. This assigns
default write and maintenance jobs without migrating or deleting existing
stores. SocratiCode and semble retain their separate code search jobs; they are
not additional durable-memory owners.

### Invoke-rate evidence and default-routing dispositions

The retained 24-hour counter artifact is
`research/token-efficiency-20261008/INVOKE-RATES-24H-20261008T2330Z.md`,
SHA256 `86e8a4e0db11846eed1c4e99d5e89321b576cab087aa07676188705de593e541`.
Its bytes/hash and every number used below were checked; the Loki count was not
rerun. It counts native MCP tool-result events and distinct conversations or
sessions, including subagents. Events are not outcomes; the artifact does not
separate every probe from organic work. Codex interactive conversations (555),
Codex exec readers (285) and Claude sessions with any event (105, including
headless runs without MCP) remain separate populations.

Each reviewed memory layer gets one default disposition. KEEP preserves the
native role with use evidence; WIRE proposes missing vendor-native routing;
RETIRE proposes removing default exposure while retaining optional stores and
historical evidence. These proposals do not change host configuration.

| Layer | Disposition | Evidence and native routing decision |
| --- | --- | --- |
| Claude native auto-memory | **KEEP** | Retention proposal pending the named native-session observation. The memory directory is present and updated within the observed day, but this built-in file workflow is outside the MCP metric. Freshness does not attribute the writer or prove loading and does not satisfy the organic-use criterion |
| ai-memory | **KEEP** | Codex: 303 calls in 84/555 conversations (15%); Claude: 13 calls in six sessions. Preserve vendor lifecycle capture and [managed recall/maintenance skills](https://github.com/akitaonrails/ai-memory/tree/89bd8ded3c1ab8b769cf99417d038ed0364403c8/crates/ai-memory-core/src/routing_skills); rare Claude use remains a test boundary |
| Hindsight | **RETIRE** | Codex: 20 calls in 14/555 conversations (2.5%); Claude: four calls in four sessions. No established unique default job is demonstrated. Retain the research service/bank as optional; do not install another generic coding-memory capture route |
| context-mode | **KEEP** | Codex: 29,102 calls in 545/555 conversations (98%); Claude: 2,433 calls in nine sessions. The retained artifact identifies organic use on both clients. Preserve vendor session hooks and runtime skill |
| codebase-memory | **KEEP** | Codex: 1,551 calls in 127/555 conversations (23%); Claude: four single calls in four sessions. Preserve the native daemon/watcher and vendor graph routing. Claude organic adoption is not established by single-call sessions |
| QMD | **WIRE** | Codex: 43 calls in 28/555 conversations (5%); Claude: five calls in five sessions. Both clients have the 823-byte bootstrap skill; native `claude plugin list --json` reports no QMD plugin entry. The unregistered first-party Claude plugin route is [qmd@qmd](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/.claude-plugin/marketplace.json), whose [runtime skill](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/skills/qmd/SKILL.md) triggers markdown retrieval. Effective bootstrap use is unverified. Propose that native plugin route for Claude and verify the existing runtime bootstrap in Codex; reconcile the named index/transport so activation adds no competing server |
| Graphiti | **RETIRE** | Keep it outside defaults while its installation disposition is **defer**. It is absent from the supplied invocation table; that is not a measured zero. No unique adopted job justifies default exposure |

Hindsight's potential unique job is source-grounded synthesis and maintained
mental models over a deliberately curated research bank. ai-memory owns project
session/decision memory, and context-mode owns session continuity. Zero mental
models and sparse invocation do not establish the separate curated research
workflow here. The vendor [portable memory skill](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md)
routes generic prior context, preferences and continuity, overlapping those
default jobs. The unified [coding-agent integration](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs-integrations/coding-agents.md#L495)
supports `optInOnly`/`optInPaths`, path-to-bank mapping, and suppression of
session retention, auto-seeding, bank management and injection. Those controls
can isolate a future dedicated research directory; they do not select a research
question within a mixed coding session. Reopen WIRE only with that named scope
and unique job. Keep the server's research 15-tool allowlist authoritative;
plugin configuration review is not client allowlist acceptance.

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
| Claude native memory | Apply a previously recorded citation preference to a bounded source review | Apply the same published repository rule to a bounded source review | Claude native memory load/read is a file/session observation, not an MCP count. Codex uses its instruction/memory owner; no Claude-only feature is claimed for Codex |
| ai-memory | Continue a real unresolved project decision from a prior completed session, citing its record | Same task in a new Codex conversation | Useful scoped retrieval and native MCP events; lifecycle capture remains a separate observation |
| context-mode | Research the two pinned source references and retain unresolved points through native compaction/resume | Same task with native Codex compaction/resume | Useful capture/retrieval and restoration; count each session's events once |
| codebase-memory | Trace callers of `scripts/catalog_decisions.py:identity` and explain affected source paths | Same scoped code question | Useful graph traversal, source citations and native events; a project list alone fails |
| QMD | Find the checked-in decision defining foundation evidence and cite exact text/lines | Same markdown question with native runtime skill activation | Actual search and source retrieval from the named collection, counted from Loki; no tool is named in the task |
| Hindsight | After proposed default retirement, continue the ordinary project decision above | Same task after proposed default retirement | No default Hindsight exposure/calls and successful use of the assigned project-memory owner. A later dedicated curated research scope needs ordinary bank-synthesis tasks and useful research-bank events in both clients; that optional test remains pending |
| Graphiti | Continue a code/project-memory task with the assigned owners | Same task | No Graphiti dependency in defaults. A future temporal-graph job needs its own fresh task, useful native events and database/provider results before adoption; none is run here |

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
| ai-memory | `memory_lint` / CLI `lint`, `memory_consolidate`, `memory_forget_sweep` / CLI `forget-sweep`, curated feedback and auto-improvement. Its server has persisted maintenance cadence; v2.6.0 defaults enable daily lint/forget sweeps and hourly auto-improvement, while SessionEnd consolidation is opt-in | Active server and answering scoped MCP observed. Bounded journal metadata includes consolidation categories. Direct CLI `status --json` and `auto-improve-report --json` each timed out after 15 seconds; effective lint/sweep/learning intervals remain unknown. Defaults and old receipts are not current settings | Preserve SessionEnd/native scheduling as the primary runner where confirmed. Draft daily rule-only lint and weekly retention review run native CLI with `--dry-run`; lint also uses `--no-llm`. Before activation, reconcile them with the server scheduler to prevent duplicate work. No consolidation timer replays completed sessions |
| Hindsight | On-demand `reflect`; observation consolidation; saved mental-model source-query refresh. Mental models support native `refresh_cron` or `refresh_after_consolidation`, with dirty-scope gating and bounded retries | Native consolidation operation completion observed. `list_mental_models`: total 0; refresh operations: total 0. This bank has no mental models to schedule. Reflect/model-refresh execution was not invoked by this task | Optional-bank drafts only: weekly `memory reflect` uses `--budget low --max-tokens 512`; daily refresh requires an adopted curated research job, selected model ID and installed native CLI. Prefer either native model cron or the timer, never both. Exit zero submits an operation; completion must be observed separately |
| context-mode | Session hooks capture/restore continuity; vendor `cleanupOldSessions` supports age-based session cleanup. `ctx_stats` and `ctx_doctor` inspect health; scoped `ctx_purge` is explicit deletion | Session tools answered; release source and installed source were inspected. No independent retention execution or effective retention age was measured | Session hooks remain the runner. Weekly operator health/continuity review; no automatic purge or invented timer. Destructive purge stays an explicit scoped request |
| codebase-memory | Native daemon watcher incrementally refreshes graphs. `detect_changes`, `index_status`, `check_index_coverage` and scoped `index_repository` support diagnosis/recovery | `list_projects` answered with 50 registered projects. Current watcher activity and exact-path freshness were not independently inspected | Preserve event-driven watcher updates. Draft weekly native `check_index_coverage` for the named project; repair only an observed stale/gapped index. No periodic whole-repository rebuild |
| QMD | `qmd update` refreshes collections; `qmd embed` is optional for a semantic index; `qmd cleanup --dry-run` previews orphan/cache cleanup | Lexical index status answered; no maintenance timer found. Current update history was not inspected. Shared HTTP unit remains inactive/disabled | Draft daily `update` and weekly `cleanup --dry-run` on the explicit lexical index. Review collection update hooks before activation because `update` may execute them. Embeddings remain a separately justified workload |
| Graphiti | `add_episode` performs edge resolution/invalidation; `build_indices_and_constraints`, `build_communities` and `remove_episode` manage graph state. Community updates are optional; these methods do not establish a scheduler | No adopted host job observed. #839's Mac import check is retained at its original scope | No maintenance unit while deferred. Reopen with a named graph job and database/provider acceptance |

The [draft units](../../adoption/drafts/memory-maintenance-20261008/README.md)
contain seven services and seven timers. They call supported native commands;
no scheduler or maintenance implementation is rebuilt. All are guarded by an
absent operator marker, use bounded time/resource settings, and remain files in
this PR. None was installed, enabled or run. Cadences are proposals, not vendor
defaults, measured optima or a new model-use authorization.

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

[G5 #878](https://github.com/seathatflowsinourveins/native-agent-stack/pull/878)
is still open at `ae6cc2286643822d3a0218136722c69d0127fcd4`. Its pinned
[compact catalog](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ae6cc2286643822d3a0218136722c69d0127fcd4/catalogs/landscape/grand-catalog-20261008.json)
maps ai-memory to JSON pointer `/rows/7` and codebase-memory to `/rows/32`.
Both are source-review/WATCH rows, not adoption or current-host acceptance.
The selected row lookup did not find the other five reviewed layers in that
draft manifest; it is not a global catalog-coverage claim. Their pinned vendor
and native evidence above remains the decision source. Map all seven decisions
to the published G5 rows once that publication lands; do not invent an absent
row or treat an open draft as main. This is a publication dependency for the
readers, separate from this branch's single rebase and structural validation.

### Corrections retained in this record

| Anti-pattern | Correction and verification | Preventing check |
| --- | --- | --- |
| Treating a library import on another host as current deployment | The earlier Graphiti row used an installation verb; pinned #839 explicitly defers managed installation. The current role is defer, with retirement from defaults proposed | Read the exact recipe head and current native tool/unit state before assigning an active owner; this record |
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

- Claude Code reads `AGENTS.md` natively (CHANGELOG 2.1.277); instruction files no longer prescribe an `@AGENTS.md` import.
- The Agent tool takes a per-call `effort` (2.1.292); frontmatter effort remains valid (2.1.267, 2.1.288).
- Claude runs a skill named exactly `verify` before commits (2.1.286); projects provide a `verify` skill that wraps their acceptance commands.
- `omitClaudeMd` (2.1.271) suits blind judges and reviewers.
- Codex user skills live under `$HOME/.agents/skills`; `$CODEX_HOME/skills` is the deprecated location (codex-rs `host_roots.rs` at rust-v0.160.0, L96-107).
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
