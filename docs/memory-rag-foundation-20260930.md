# Memory and RAG foundation review

Checked September 30, 2026 for native Claude Code and Codex.

**Recommendation: Hindsight for the new shared Claude/Codex memory target.** This is a fit-based choice supported by maintained native integrations, published conversational QA and coding comparisons, plus our scoped storage/lifecycle trial. A measured overall or token-efficiency winner remains unestablished. Keep ai-memory as the canonical operational reference while current-version capture, matched quality and complete-cost qualification continue. Hindsight server 0.10.2 and coding integration 0.8.0 remain current stable; capture remains disabled here.

The [current review manifest](../catalogs/foundation/memory-rag-20260930.json) records current upstream pins, candidate dispositions and promotion gates. The [native receipt](../evidence/receipts/memory-rag-20260930.json) retains both upstream test attempts and installation boundaries. These additions are a dated supplemental review; they do not replace the accepted component pins in `manifests/stack.json` or another host's memory decision.

The generated [HTML manifest](ecosystem/index.html#memory-review) presents the fit-based recommendation and open measured-winner verdict, all 25 candidate reasons, exact pins, primary sources and a five-finalist evidence matrix. Build it with the repository's existing `python3 scripts/build_ecosystem.py --write` command. The [backbone assurance record](../evidence/artifacts/memory-rag-20260930/backbone-assurance.json) retains checked published metrics, source hashes, failure/correction records, native stack alignment and the selection gate. The separate native resolution wave below does not supply a new matched model-quality or complete-cost benchmark.

## Fresh upstream check and directly relevant coding evidence

The [freshness record](../evidence/artifacts/memory-runtime-resolution-20260930/latestness.json)
records the fresh release/tag/registry and installed-version checks. Hindsight
remains server **0.10.2** with independently pinned integration **0.8.0**.
ai-memory **2.5.0** was released September 30 at 20:31:52 UTC, commit
`a8757a05a960f96a0ba510b6341bcd520cf80bb2`. It adds server routing,
repository identity and optional external lifecycle delivery. This is source
review, not an upgrade acceptance: the completed native fixture tested **2.4.2**.
The fresh CLI probe also reports 2.4.2; the canonical accepted pin is 2.4.1,
and a version probe does not qualify any running-service cutover.
[Current release](https://github.com/akitaonrails/ai-memory/releases/tag/v2.5.0),
[immutable changes](https://github.com/akitaonrails/ai-memory/blob/a8757a05a960f96a0ba510b6341bcd520cf80bb2/CHANGELOG.md).

The qualified Codex client remains 0.159.2. The final release recheck at
2026-10-01T00:22:46Z found [Codex 0.159.3](https://github.com/openai/codex/releases/tag/rust-v0.159.3)
(@01fc69f4026735edfdf6789820549727a4867b11); that release has not been installed
or qualified by this wave. Claude 2.1.286, QMD 2.8.3, RTK 0.50.0 and
MCPorter 0.14.1 match the retained stable-release checks. Context-mode 1.0.169
matches the recipe and retained metadata observation. Installed WSL is 2.7.13.0 while
upstream is 3.0.1; no OS upgrade or new distro ran. Release freshness alone
does not establish SOTA or complete lifecycle acceptance.

The [published coding evidence record](../evidence/artifacts/memory-runtime-resolution-20260930/published-coding-evidence.json)
retains independent aggregation of the publisher's 18-run SDE-bench manifest.
These are **61 constructed bug-fix tasks repeated three times per arm**,
principally boltons; 183 is a repeated-run denominator, not independent tasks.

| Native agent/model | Corrections per task: no memory → Hindsight | Solved repeated task runs | Reported coding-agent cost reduction |
| --- | --- | --- | --- |
| Claude Code / Claude Sonnet 5 | 0.847 → 0.361 | 181/183 → 183/183 | 24.04% |
| Codex / GPT-5.4-mini | 1.344 → 0.470 | 182/183 → 183/183 | 52.26% |
| opencode / Gemini 3.5 Flash | 1.197 → 0.798 | 183/183 → 182/183 | 12.81% |

This is a publisher-run **no-memory comparison**, not a comparison of our five
finalists. Cost includes the coding agents and excludes Hindsight extraction,
reflection, refresh, storage and hosting. Native clients in the Dockerfiles
are unpinned; the plugin directory is supplied externally. The current harness
fixes stale-bank and remote-authentication failures, which does not prove every
published run used those fixes. No new coding-agent run occurred here.
[Results manifest](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/results-manifest.json),
[cost calculation](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/sdebench/harness/run.py#L829),
[dataset](https://github.com/vectorize-io/sde-bench/blob/afcce15c1f608242e28e48832c301f39c5aed708/DATASET.md).

Astra/Max accepts Hindsight as the recommended shared-native target with this
stronger evidence. ai-memory 2.5.0 strengthens the competing source fit, while
the measured replacement and complete-cost gates remain open.

## Evidence for the clean runtime

The [WSL resolution manifest](../blueprints/convergence-practice/memory-runtime-resolution-20260930/manifest.json)
fixes the execution wave's list and records current native qualification. The
supported `foundation-cpu` bootstrap has completed in a new owned prefix on this
WSL host: exit 0, ten verified probes and zero failures. It retained the existing
Claude 2.1.285 launcher above the recipe's 2.1.284 minimum. Independent prerequisite
and pin checks returned exit 0 with `runtime_acceptance_verified: false`.
The isolated native qualification wave is complete, with results below;
Hindsight integration capture remains disabled. This is a fresh installation
prefix, not a new distro, second machine or fully accepted runtime.
The [foundation installation record](../evidence/artifacts/memory-runtime-resolution-20260930/foundation-prefix.json)
binds the frozen installer inputs, original private output hashes and actual
native version report. The fresh prefix shares the native Claude launcher and
npm cache; active client wiring was not applied. The execution uses current
reviewed checkout pins rather than the older published release's client pins.

| Current-host execution | Actual result | Boundary and retained failure |
| --- | --- | --- |
| [ai-memory 2.4.2](../evidence/artifacts/memory-runtime-resolution-20260930/ai-memory-native.json) | 101 lifecycle-fixture and 65 recovery-fixture checks pass; 42 unchanged upstream scope tests pass, native exit 0. Native backup and empty-target restore passed; six Markdown files match and four page rows match excluding read telemetry. | Synthetic integration is distinct from upstream tests and native capture. First restore hit the enabled global sibling-process guard and created logging scaffolding. A clean PID/network namespace retry passed. The broader store attempt timed out with no completed aggregate; it remains incomplete. |
| [Hindsight 0.10.2](../evidence/artifacts/memory-runtime-resolution-20260930/hindsight-chunk-native.json) | Supported no-LLM mode retained/recalled two documents, preserved them after daemon restart, exported/restored them with new IDs and passed source/target deletion controls. Owned API/database stopped natively. | Different banks in one new profile, not separate-instance restoration. Local embeddings/reranker; no observations, pages or reflection acceptance. Reflect correctly returned HTTP 400. Native coding-client capture and full quality/cost remain pending. |
| [agentmemory 0.9.29](../evidence/artifacts/memory-runtime-resolution-20260930/agentmemory-native.json) | Two unchanged upstream eval processes exited 0; adapter scored 0/15, while first grep control hit 15/15. Native HTTP independently confirmed 15 ingested records and six search results. | The score is not backend-quality evidence: the runtime supplies truthy synthetic `sessionId: memory`, which bypasses the adapter's fixture-ID fallback. Current keyless default resolves to BM25-only. No evaluator edits; leaked owned workers were explicitly stopped. |

Astra/Max accepted these scoped findings after the bounded Sol diagnosis and
original-source verification. An extra embedding run cannot repair the session
identity mismatch. A maintained correction or supported matched harness is needed
before interpreting new comparative scores. The operational reference stays
ai-memory; the new-backbone and token-efficiency verdict remain unresolved.

The new-distro proposal is prepared in the runtime manifest using installed WSL
help and Microsoft's supported install syntax. Ubuntu-24.04 is offered and matches
the retained userspace scope. Installed WSL is 2.7.13.0; upstream 3.0.1 is a
source-reviewed candidate, not an executed upgrade. No distribution, kernel or
default-distro change ran. A genuinely fresh distro must perform native sign-in,
configuration and lifecycle acceptance anew.

| Candidate | Strongest relevant evidence | What it establishes and what remains open |
| --- | --- | --- |
| ai-memory | Retained native operational receipts; a separate author benchmark at 0ac0dcf records hit@5 0.823 and fractional recall@5 0.680 on 470 questions with bounded capture. | Reference configuration, not a SOTA claim. Latest 2.5.0 is source-only; the scoped 2.4.2 fixture passed. Production reranker-on comparison remains pending. |
| Hindsight | Original publisher AMB artifacts: LongMemEval 473/500 = 94.6%; LoCoMo 1417/1540 = 92.013%. Same-harness hybrid controls score 74.0% and 79.091%. | Strong configuration-level QA gain. The publisher attributes runtime 0.4.19. Answerer/judge are Gemini 3.1 Pro Preview/2.5 Flash Lite. Mean answering context is 43,624.5 versus 23,221.7 tokens and 36,235.4 versus 22,156.5; complete lifecycle costs and current native acceptance remain unknown. |
| agentmemory | Retained historical Mac REST recall_all@5 0.821 versus ai-memory reranker-off 0.570, n=470; +0.251, 95% CI [+0.203,+0.299], Holm p=0.0001. | Strong descriptive retrieval improvement. Original report hash and sanitized transcription are retained, not a new independently reconstructed run. Native capture, production reranker and complete operating costs remain pending. |
| MemPalace | Original raw 500-row JSONL mean recall_any@5 0.966; author-labelled held-out hybrid 450-row mean 0.984444. | Any-session retrieval rather than all-session retrieval or answer accuracy. The inspected artifacts omit recall_all@5. Native capture, knowledge freshness and independent empty-target recovery remain pending. |
| Mem0 | Original committed managed top-200 artifacts: 467/500 = 93.4% LongMemEval and 1410/1540 = 91.558% LoCoMo; GPT-5 answering/judging. | Current documentation headlines 94.4%/92.5% conflict with these artifacts. Managed results and 6,787/6,956 documented query-context tokens do not qualify OSS 2.2.1 or complete local operating cost. |

Every row's immutable original-source links are in the assurance record and HTML matrix. These metrics use different protocols, models, capture boundaries and runtime revisions; they are not one leaderboard. Published context counts, local compute and complete provider/cache billing remain separate.

For the clean runtime, reuse the `foundation-cpu` native profile from `adoption/manifest.json`: native Codex/Claude, Context Mode, QMD, RTK, MCPorter and the ai-memory reference. Keep Serena/SocratiCode project-scoped and Dagu optional. Component pins come from `manifests/stack.json`. The nonmutating prerequisite command returned `prerequisites_present` and `runtime_acceptance_verified: false`; it does not accept a new prefix. Qualify the challengers in isolated configurations against the reference before selecting one memory of record.

Astra/Max adjudicated the consequential quality/cost conflict and accepted an **unresolved backbone verdict**, withdrawing the earlier unconditional Hindsight final-target label. The fresh coding-evidence review accepts a fit-based recommendation, while keeping the measured-winner fields null. The deciding comparison must use current pinned deployable profiles, the same tasks and correctness/freshness thresholds, native scope/deletion/restore checks, complete background and downstream model usage, separate cache billing and cold/warm latency. The original replacement rules remain binding.

## What the evidence selects

| Decision | Selection | Evidence and limit |
| --- | --- | --- |
| Accepted production memory | ai-memory | Existing scoped native capture, retrieval and recovery receipts. The earlier CLI observation was 2.4.1; the fresh probe is 2.4.2 and upstream is 2.5.0. Service cutover was not requalified by this probe. Existing operational acceptance does not establish a quality winner. |
| Quality and lifecycle qualification target | Hindsight | Official unified Claude and Codex hooks/MCP, shared project banks, reflective memory, derived pages and bank transfer. Current unchanged package tests passed here; live cross-client capture, recovery and complete-cost superiority remain unqualified. |
| Strongest recorded retrieval challenger | agentmemory | The existing Mac descriptive REST-path run scored 0.821 recall_all@5 against 0.570 for reranker-off ai-memory. Its shipped hook path and production reranker-on control remain outstanding. |
| Other shortlisted challenger | MemPalace | Current source ships both clients' hooks and direct Python transcript capture. Published retrieval results need the registered reproduction and lifecycle checks. |
| Document retrieval | QMD | Keep the selected scoped document index. It supplies retrieval rather than automatic session learning. |
| Code retrieval | Existing SocratiCode, Serena and static graph lanes | Preserve the selected project index and exact-source navigation. This review supplies no new language, GPU or code-corpus acceptance. |

The retrieval figures and their limitations come from the [existing September 25 comparison](../catalogs/foundation/memory-stack-20260925.json). They are different evidence from today's package tests. The existing [durable-memory verdict rule](../catalogs/landscape/foundation.json) and [replacement rule](../catalogs/foundation/memory-stack-20260925.json) still require the executed representative comparison and memory-lane acceptance.

## Current candidate comparison

This is a broad shortlist of credible maintained alternatives, including the existing research candidates. Each verdict below is a scoped source-review judgment unless a local evidence class is stated. It is not an exhaustive claim about every memory repository.

| Candidate and current upstream | Useful role | Decision for this ecosystem |
| --- | --- | --- |
| [Hindsight 0.10.2 and coding agents 0.8.0](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/README.md) | Shared coding-agent lifecycle, recall/reflect, observations and knowledge pages; native installers for both clients. | Quality/lifecycle challenger; overall winner unresolved. Native package staged here, capture disabled. Server and integration need separate pins. |
| [ai-memory 2.5.0](https://github.com/akitaonrails/ai-memory/releases/tag/v2.5.0) | Scoped Markdown decisions, native hooks, named server routing, repository identity, optional external lifecycle relay and backup/restore. | Retain canonical accepted control. New 2.5.0 is source-reviewed; 2.4.2 lifecycle results do not qualify its migrations or native capture. |
| [agentmemory 0.9.29](https://github.com/rohitg00/agentmemory/tree/v0.9.29) | Native client hooks, local retrieval, event/state APIs and snapshot/export paths. | Priority matched retrieval and hook-path trial. Retained Mac measurements support comparison, not production replacement. |
| [MemPalace 3.10.0](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/hooks_cli.py) | Local persistent project memory with direct transcript capture and both clients' hook manifests. | Priority local challenger. Prove short Codex-session capture, isolation, freshness and restore; default capture is not merely an agent prompt to save. |
| [Mem0 OSS 2.2.1 and plugins 0.3.3](https://github.com/mem0ai/mem0/blob/v2.2.1/integrations/claude-code-plugin/README.md) | Application identity memory and official Claude/Codex Platform plugins. | Strong managed-service alternative; the OSS SDK is a separate integration. A base-URL override does not demonstrate stock plugin parity with the bundled OSS server. |
| [Claude-mem 13.28.0](https://github.com/thedotmack/claude-mem/blob/v13.28.0/README.md) | Coding-session capture, compression, search and inspection, including current Codex support. | Direct lifecycle alternative. Compare scope, retention and recovery before replacing the current capture path. |
| [Basic Memory 0.23.2](https://github.com/basicmachines-co/basic-memory/tree/v0.23.2) | Human-editable Markdown knowledge and native Claude/Codex integrations. | Strong notes-first alternative; existing synthetic lexical evidence is narrower than semantic or whole-lifecycle quality. AGPL profile remains an explicit selection attribute. |
| [Supermemory server 0.0.8](https://github.com/supermemoryai/supermemory/releases/tag/server-v0.0.8) | Search/profile memory, Claude/Codex integrations and self-hosted endpoint choices. | Conditional alternative. Distinguish open integration sources from the distributed server engine and qualify export, scope and selected inference providers. |
| [Graphiti 0.30.2](https://github.com/getzep/graphiti/blob/v0.30.2/mcp_server/README.md) | Temporal entities, relationships, hybrid retrieval and group-scoped MCP. | Specialist graph layer or isolated challenger. Managed Zep results do not establish OSS Graphiti performance. Its upstream Docker recipe includes backup/restore. |
| [Letta Code 0.34.0](https://github.com/letta-ai/letta-code/releases/tag/v0.34.0) | Stateful coding runtime, memory files and dreaming; current Memory Palace feature uses Letta Cloud. | Consider for an explicitly selected worker runtime. It changes the harness architecture and is not the same adoption shape as shared native-client capture. |
| [Cognee 1.6.2](https://github.com/topoteretes/cognee/blob/v1.6.2/README.md) | Graph/context processing for documents, code and conversations; local GLiNER extraction without an LLM key. | Strong graph/context challenger when that workload is needed. Model downloads, selected integrations and representative quality remain separate gates. |
| [OpenViking 0.4.22](https://github.com/volcengine/OpenViking/blob/v0.4.22/README.md) | Hierarchical resources, memory and skills; native Claude/Codex hooks and MCP. | Conditional unified-context trial if fragmented retrieval becomes a demonstrated problem. Provider/model and AGPL profile require explicit selection. |
| [Honcho 3.2.1](https://github.com/plastic-labs/honcho/blob/v3.2.1/README.md) | Background reasoning about peers and sessions, native coding-agent integrations and local/self-hosted setup. | Prefer for peer/user modeling requirements; qualify the selected worker/database profile before a shared coding-memory trial. |
| [EverOS from EverMemOS 1.4.1](https://github.com/EverMind-AI/EverMemOS/blob/v1.4.1/README.md) | Local Markdown with SQLite/LanceDB indexes, memory ingestion/search and coding-agent tooling. | Current local challenger. Its latest architecture should be evaluated on its own source rather than an older mandatory multi-service description. |
| [MemOS 2.0.34](https://github.com/MemTensor/MemOS/blob/v2.0.34/README.md) | Memory APIs and multiple local/cloud agent-plugin profiles. | Conditional application/agent-memory layer. Select and test the intended profile; vendor QA scores are not native Claude/Codex acceptance. |
| [Attemory 0.1.3](https://github.com/AttemorySystem/attemory/tree/v0.1.3) | Local memory SDK with shipped Python MCP module and tests. | Defer foundation adoption until core source/distribution and lifecycle acceptance are established. The old “MCP only planned” exclusion is stale. |
| [GBrain 0.60.11.0](https://github.com/garrytan/gbrain/tree/v0.60.11.0) | Persistent knowledge search; current quickstart includes keyless keyword retrieval. | Optional local retrieval challenger. The old blanket hosted-only rationale is stale; no new matched result was run here. |
| [memento-mcp 2.3.0](https://github.com/lfrmonteiro99/memento-mcp/blob/v2.3.0/src/cli/install.ts) | Typed SQLite coding-agent memory and git synchronization. | Lightweight alternative. The installer supports Claude, Cursor and manual setup; Codex compatibility does not establish a one-shot Codex installer. |
| [Shane Farkas Memento 0.1.0](https://github.com/shane-farkas/memento-memory/blob/3dec57ae5e22a3ae2c2580b6f6ffcffba28b8a21/src/memento/mcp_server.py) | SQLite bitemporal graph and MCP operations. | Graph-memory trial. Forgetting soft-archives; its benchmark is QA rather than the registered retrieval metric, and its Codex YAML example is stale. |
| [Memento Vault 5.0.0](https://github.com/sandsower/memento-vault/blob/v5.0.0/README.md) | Markdown/git knowledge vault, Claude lifecycle and MCP. | Separate notes candidate; native Codex lifecycle remains unqualified. |

For document/application RAG, [LlamaIndex 0.14.25](https://github.com/run-llama/llama_index/blob/v0.14.25/README.md), [Haystack 3.2.0](https://github.com/deepset-ai/haystack/blob/v3.2.0/README.md), [LightRAG 1.5.7](https://github.com/HKUDS/LightRAG/blob/v1.5.7/README.md) and [RAGFlow 1.0.0-rc1](https://github.com/infiniflow/ragflow/releases/tag/v1.0.0-rc1) remain useful candidates for an application ingestion/retrieval pipeline. They do not establish an improved native-client memory lifecycle by installation alone. RAGFlow's new release is a preview and carries an irreversible upgrade warning; it belongs in an independent trial. QMD 2.8.3 remains the selected document-search component. [QMD source](https://github.com/tobi/qmd/tree/v2.8.3).

## Native installation completed

The official npm package's supported runtime staging operation completed:

```sh
rtk npx --yes @vectorize-io/hindsight-coding-agents@0.8.0 update
```

Independent inspection found the staged version, Claude/Codex entry points and companion skill. A new private Hindsight configuration pins the runtime/backend versions and sets capture disabled, automatic updates off, empty project opt-in, no historical seed/survey and manual page refresh. Existing Claude/Codex hook and MCP configuration was not wired by this operation. [Upstream staging implementation](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/src/installer.ts#L2350).

Initial staging installed `hindsight-embed==0.10.2` with uv and passed native `--help`; that earlier receipt covers the launcher only. The subsequent [chunk-only resolution trial](../evidence/artifacts/memory-runtime-resolution-20260930/hindsight-chunk-native.json) downloaded backend/local model dependencies, exercised an owned daemon and stopped it. No production import or full LLM/native-client capture acceptance followed. [Embedded CLI source](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-embed/README.md).

The package was built at npm's exact source revision with the unchanged lockfile. Its unchanged upstream test command first returned exit 1 with 1,267 passed, 12 failed and six skipped. One bounded rerun changed only `TMPDIR` to an owned directory outside the source checkout and returned exit 0 with **1,279 passed and six skipped**. All previously failed assertions passed. Both native JSON reports are retained with hashes in the receipt. Temporary-directory isolation resolved the test failures; the original transient filesystem cause was not directly observed. [Node temporary-directory contract](https://nodejs.org/download/release/v24.21.0/docs/api/os.html#ostmpdir).

The six skipped cases concern Trae workspace SQLite enable switches. The ordinary upstream command excludes E2E files, and the separate Docker harness marks fresh-container Claude Code E2E unsupported. This pass does not establish real Claude/Codex capture or recovery. [Upstream test command](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/package.json), [harness limitation](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/src/e2e/harnesses.ts#L84).

## Required promotion and lifecycle checks

Before any production replacement, qualify the following against one disposable project and the registered representative comparison:

1. **Native activation and capture:** official Claude and Codex installers, ordinary native hook trust, fresh-session observation, bidirectional capture/recall and a memory-disabled control. Successful file installation alone is insufficient.
2. **Identity and isolation:** explicit unique repository-to-bank mappings, worktree sharing, unrelated-project negatives and same-basename repository negatives. Default bank names derive from repository basename, so collisions must be addressed. [Bank resolver](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/src/core/bank.ts).
3. **Grounded usefulness:** held-out decisions, provenance, updated facts, abstention and freshness, against both registered ai-memory controls and the other shortlisted challengers. Count all selected extraction, embedding, reflection, consolidation and retry work; keep unavailable usage unknown.
4. **Interruption and replay:** unfinished ingestion, failed inference, offline recall behavior and resumed capture without lost or duplicated turns. Exercise the real daemon, not only fixture mocks.
5. **Deletion and recovery:** stop the relevant writers and historical seeding before deletion, test that memory stays deleted, use current bank `/transfer/export` and `/transfer/import` in default `restore` mode into a nonexistent target, and verify provenance and source/target independence. Import re-embeds facts and resolves entities without LLM re-extraction. Omit copied bank configuration or remove source-bound webhooks. The older document-transfer examples are superseded; bank transfer is semantic recovery rather than a byte-identical database copy. [Bank transfer API](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/api/memory-banks.mdx).
6. **Cutover and rollback:** preserve the incumbent and owned backups; switch one project's authoritative capture only after gates pass. Native uninstall removes its owned hook/MCP/skill entries, while bank erasure and state/runtime cleanup need separate checks. [Installer ownership](https://github.com/vectorize-io/hindsight/blob/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c/hindsight-integrations/coding-agents/src/installer.ts).

Local deployment can use Hindsight's documented local providers. Choose the provider explicitly: its Claude provider uses the Claude Agent SDK, while its Codex provider directly reads native authentication and calls the ChatGPT backend. This trial selected no inference provider and read/copied no authentication store. [Claude provider](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-api-slim/hindsight_api/engine/providers/claude_code_llm.py), [Codex provider](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-api-slim/hindsight_api/engine/providers/codex_llm.py).

## Corrections and evidence boundaries

This review records current source corrections without rewriting historical receipts:

- Server 0.10.2 bundles integration 0.7.0; the current npm integration is 0.8.0 at a different commit. The two pins must remain independent.
- Claude-mem, Basic Memory, OpenViking, Honcho and Mem0 have current cross-client integrations. A blanket “Claude-only” or “no Codex plugin” exclusion is insufficient.
- Mem0's supported Platform plugins use API routes that differ from its bundled OSS server. Self-hosted URL configuration alone does not establish compatibility. [Plugin core](https://github.com/mem0ai/mem0/blob/v2.2.1/integrations/agent-plugin-core/python/memory_core.py#L1995), [OSS routes](https://github.com/mem0ai/mem0/blob/v2.2.1/server/main.py#L367).
- MemPalace defaults to silent direct Python capture; its legacy blocking save prompt is a separate mode. Attemory ships MCP code, and GBrain offers keyless retrieval. These capabilities require qualification rather than stale blanket exclusions.
- Managed Zep/Mem0 QA results, Hindsight vendor results, retrieval recall, context-token estimates and this package test pass measure different things. They do not supply a universal SOTA ranking or complete lifecycle certification.

Astra/Max reviewed the consequential shared lifecycle architecture and accepted **isolated Hindsight qualification while retaining the incumbent**, with explicit scoping, deletion/reseed controls, separate integration pins and native acceptance gates. The bounded Sol diagnosis independently verified the corrected test report. No matched model-quality run or complete provider accounting was performed in this review.

Direct anonymous GitHub API calls eventually returned rate-limit errors; authenticated `gh api` recovered the release-tag verification. npm/PyPI metadata, installed help, pinned original source and existing acceptance records remain distinct sources. No unavailable channel was counted as a negative capability result.

The catalog structure and this review's scoped convergence record passed their repository checks. The earlier publication check returned exit 1 with **zero errors in this review's paths** and 33 errors elsewhere in the shared checkout. Those findings include concurrent hash changes and unregistered token-lifecycle artifacts. Their owning work was not changed, and this review was not committed. Structural validation checks consistency and source references, not model quality or live service behavior.

The [first HTML verification record](../evidence/artifacts/memory-rag-20260930/html-verification.json) retains the earlier presentation checks and output hash. The revised comparison-open page is checked separately. Presentation/integration checks remain separate from Hindsight's unchanged upstream tests and live lifecycle acceptance.
