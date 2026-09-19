# Token, memory and retrieval foundations

Checked September 19, 2026. Keep one primary memory store, one retrieval lane per artifact and the existing compatible local embedding service. The catalog reviews alternatives without installing competing capture systems or importing private conversation archives.

The active path is **ai-memory + Context Mode/RTK + scoped QMD + Serena/SocratiCode + Qdrant**. Use Repomix for selected handoffs and Docling only when financial document layout requires it. All commands below are upstream entry points or existing native recipes; a command listing is not an execution receipt.

| Repository | Decision | Reviewed version | Role | Evidence |
| --- | --- | --- | --- | --- |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | default | v2.3.1 | Cross-harness project memory and handoffs | native_proven |
| [context-mode](https://github.com/mksglu/context-mode) | default | v1.0.169 | Execute large outputs locally and retrieve bounded relevant results | native_proven |
| [rtk](https://github.com/rtk-ai/rtk) | default | v0.49.0 | Compact supported CLI output | native_proven |
| [qmd](https://github.com/tobi/qmd) | default | v2.8.3 | Scoped Markdown BM25 retrieval | native_proven |
| [SocratiCode](https://github.com/giancarloerra/SocratiCode) | default | v1.14.0 | Automatic semantic code indexing and graph context | native_proven |
| [serena](https://github.com/oraios/serena) | default | v1.7.0 | Language-server symbol and reference retrieval | native_proven |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | conditional | v0.11.0 | Static code graph fallback | native_proven |
| [repomix](https://github.com/yamadashy/repomix) | conditional | v1.18.0 | Selected-file handoff bundles | native_proven |
| [headroom](https://github.com/headroomlabs-ai/headroom) | alternative | v0.37.0 | Context compression SDK/proxy | source_review |
| [toon](https://github.com/toon-format/toon) | conditional | v4.1.1 | Compact structured serialization | native_proven |
| [mem0](https://github.com/mem0ai/mem0) | alternative | core source a39a802bbc93e85b820078cd3c4dbaf53af25dbe | Model-extracted user/agent memory | source_review |
| [hindsight](https://github.com/vectorize-io/hindsight) | alternative | v0.10.0 | Retain/recall/reflect memory service | source_review |
| [OpenViking](https://github.com/volcengine/OpenViking) | alternative | v0.4.20 | Hierarchical context filesystem | source_review |
| [cognee](https://github.com/topoteretes/cognee) | alternative | v1.6.0 | Graph memory extraction and retrieval | source_review |
| [mempalace](https://github.com/MemPalace/mempalace) | alternative | v3.10.0 | Searchable local conversation archive | source_review |
| [EverOS](https://github.com/EverMind-AI/EverOS) | watch | v1.3.1 | Structured episodic memory platform | source_review |
| [claude-mem](https://github.com/thedotmack/claude-mem) | alternative | v13.24.23 | Claude lifecycle capture and compressed retrieval | source_review |
| [graphiti](https://github.com/getzep/graphiti) | conditional | v0.30.2 | Temporal knowledge graph for sourced relationships | source_review |
| [LightRAG](https://github.com/HKUDS/LightRAG) | alternative | v1.5.7 | Graph-assisted document retrieval | source_review |
| [ragflow](https://github.com/infiniflow/ragflow) | alternative | v0.27.2 | Document RAG platform | source_review |
| [WeKnora](https://github.com/Tencent/WeKnora) | alternative | v0.8.0 | Enterprise knowledge ingestion, search and access control | source_review |
| [PageIndex](https://github.com/VectifyAI/PageIndex) | conditional | v0.2.18 | Document-tree reasoning retrieval | source_review |
| [letta](https://github.com/letta-ai/letta) | excluded | 0.16.8 | Historical Letta V1 server repository | source_review |
| [letta-code](https://github.com/letta-ai/letta-code) | alternative | v0.32.13 | Stateful agent harness and App Server | source_review |
| [haystack](https://github.com/deepset-ai/haystack) | conditional | v3.1.1 | Composable document/retrieval pipelines | source_review |
| [llama_index](https://github.com/run-llama/llama_index) | alternative | v0.14.24 | Document loaders and RAG integrations | source_review |
| [qdrant](https://github.com/qdrant/qdrant) | default | v1.19.1 | Local dense/sparse vector index | native_proven |
| [pgvector](https://github.com/pgvector/pgvector) | conditional | v0.8.6 documented tag; reviewed HEAD efa08fda9ec485d80292d0487a77939c087 | Vector search inside PostgreSQL | source_review |
| [lancedb](https://github.com/lancedb/lancedb) | alternative | v0.39.0 | Embedded multimodal vector tables | source_review |
| [docling](https://github.com/docling-project/docling) | conditional | v2.129.0 | Financial PDF/table/OCR ingestion | source_review |
| [markitdown](https://github.com/microsoft/markitdown) | default | v0.1.7 | Selected document-to-Markdown conversion | native_proven |
| [mteb](https://github.com/embeddings-benchmark/mteb) | conditional | 2.21.0 | Embedding/retrieval evaluation tooling | source_review |
| [sentence-transformers](https://github.com/huggingface/sentence-transformers) | conditional | v6.1.0 | Embedding and reranking model SDK | source_review |
| [agent-retrieval-bench](https://github.com/eyuansu62/agent-retrieval-bench) | conditional | v0.2.1 | File-level agent retrieval evaluation | source_review |
| [engram-benchmark](https://github.com/Ubundi/engram-benchmark) | watch | ef432e3323eea4a298c6d53ff645d3fd322361a2 | Cross-session memory evaluation harness | source_review |
| [supermemory](https://github.com/supermemoryai/supermemory) | alternative | server-v0.0.8 | Local/cloud memory SDK | source_review |

## ai-memory

Retain one scoped memory of record shared by Codex and Claude; lexical retrieval avoids an extraction-model dependency.

License: **MIT**. Reviewed source: [`bbc96c4a93f5`](https://github.com/akitaonrails/ai-memory/blob/bbc96c4a93f5dc0473a993a2dab2ab1ac1c33025/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
ai-memory --version
ai-memory install-mcp --client codex --apply
ai-memory install-mcp --client claude-code --apply
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Native client hooks/instructions and explicit project identity; existing local installation.

- Lifecycle capture is bounded sanitized observations, not complete transcripts. Durable writes require explicit intent; recalled prose cannot authorize actions.

Evidence: [native-memory.json](../../evidence/receipts/native-memory.json), [desktop-direct-rag.json](../../evidence/receipts/desktop-direct-rag.json), [component-history.json](../../evidence/receipts/component-history.json).

## context-mode

Reduce tool-output context while preserving raw artifacts; use the existing native plugin and project-scoped bridge.

License: **Elastic-2.0**. Reviewed source: [`6f0cc6841c68`](https://github.com/mksglu/context-mode/blob/6f0cc6841c687e754059f36714a11233fda1a02b/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
mcporter --config "${MCPORTER_CONFIG}" call context-mode.ctx_doctor --args '{}' --output text --no-oauth
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Supported runtime, native hooks and trusted MCP registration.

- Counters estimate context reduction, not provider billing savings.
- Restart acceptance proves 11 direct Desktop Context Mode tools and correlated parent logs. The historical ephemeral SDK ctx_execute_file scope/new-registration approval caveat remains separate. See [restart receipt](../../observability/restart-receipt.json).

Evidence: [native-context-memory.json](../../evidence/receipts/native-context-memory.json), [artifact-reductions.json](../../evidence/receipts/artifact-reductions.json), [component-history.json](../../evidence/receipts/component-history.json), [receipt.json](../../blueprints/us-equities/workers/receipt.json).

## rtk

Use one output-filtering lane per artifact; preserve errors and raw-output recovery.

License: **Apache-2.0**. Reviewed source: [`0924356b4cab`](https://github.com/rtk-ai/rtk/blob/0924356b4caba4989607227b7c8824d3d8098719/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
rtk git status
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Existing native CLI and hook selection.

- RTK estimated token counters are not native provider usage or an independent quality benchmark.

Evidence: [native-context-memory.json](../../evidence/receipts/native-context-memory.json), [artifact-reductions.json](../../evidence/receipts/artifact-reductions.json), [component-history.json](../../evidence/receipts/component-history.json).

## qmd

Keep the proven local lexical lane for docs; use search then get instead of loading whole archives.

License: **MIT**. Reviewed source: [`04e4dbd8245c`](https://github.com/tobi/qmd/blob/04e4dbd8245c527a88f1a8f0bda547aef9ca81fb/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
qmd --index "${QMD_INDEX}" search "automatic local code RAG Nemotron" -c "${QMD_COLLECTION}" -n 2 --json
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Explicit per-project index/collection.

- Current profile is BM25 only. Semantic query/reranking models are not downloaded. New HF models are not automatically compatible with QMD GGUF/pooling contracts.

Evidence: [native-cli-gaps.json](../../evidence/receipts/native-cli-gaps.json), [component-history.json](../../evidence/receipts/component-history.json), [desktop-cli-workflows.json](../../evidence/receipts/desktop-cli-workflows.json).

## SocratiCode

Retain the proven watcher, local Nemotron embedding endpoint and Qdrant collection for conceptual code search.

License: **AGPL-3.0-only; commercial alternative**. Reviewed source: [`b67f1328ff52`](https://github.com/giancarloerra/SocratiCode/blob/b67f1328ff52ca869f642bb6b068bb0d3f2c3646/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
mcporter --config "${MCPORTER_CONFIG}" call socraticode.codebase_health --args '{}' --output text --no-oauth
mcporter --config "${MCPORTER_CONFIG}" call socraticode.codebase_search --args "${SEARCH_ARGS}" --output text --no-oauth
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Configured per-project scope, local embedding service and Qdrant.

- AGPL obligations or commercial license apply to relevant deployments. The lmstudio setting in this profile targets local vLLM; it does not require LM Studio.
- Embedding dimension/model changes require deliberate reindexing; no automatic linked-project expansion.

Evidence: [native-rag.json](../../evidence/receipts/native-rag.json), [desktop-direct-rag.json](../../evidence/receipts/desktop-direct-rag.json), [artifact-reductions.json](../../evidence/receipts/artifact-reductions.json), [component-history.json](../../evidence/receipts/component-history.json), [vllm-compatibility.json](../../evidence/receipts/vllm-compatibility.json).

## serena

Prefer exact symbol bodies/references for edits; complements conceptual retrieval without dumping the codebase.

License: **GPL-3.0-or-later application; MIT SolidLSP**. Reviewed source: [`c6fbd1c5932d`](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
{"tool": "find_symbol", "arguments": {"name_path_pattern": "greeting", "relative_path": "fixtures/after.py", "include_body": true}}
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Supported language server and selected workspace.

- Installed development snapshot differs from latest stable v1.7.0. Static correctness still requires original source inspection.

Evidence: [native-context-memory.json](../../evidence/receipts/native-context-memory.json), [component-history.json](../../evidence/receipts/component-history.json).

## codebase-memory-mcp

Use the installed graph service where language-server coverage is insufficient; avoid redundant full indexes.

License: **MIT**. Reviewed source: [`59a05eb1bf9e`](https://github.com/DeusData/codebase-memory-mcp/blob/59a05eb1bf9e11deb060d782cd7d3a29f2ae2866/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
mcporter --config "${MCPORTER_CONFIG}" call codebase-memory.search_graph --args "${GRAPH_QUERY_ARGS}" --output json --no-oauth
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Native MCP bridge and explicit graph scope.

- A static call graph cannot resolve every dynamic runtime dependency.

Evidence: [native-cli-gaps.json](../../evidence/receipts/native-cli-gaps.json), [component-history.json](../../evidence/receipts/component-history.json), [desktop-cli-workflows.json](../../evidence/receipts/desktop-cli-workflows.json).

## repomix

Pack explicit files for a bounded worker handoff; compressed structure is an index to original implementation.

License: **MIT**. Reviewed source: [`6c5ead0d2b83`](https://github.com/yamadashy/repomix/blob/6c5ead0d2b83911d4284be9f3424e7381ae44763/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
repomix --include fixtures/records.json,fixtures/example.sh --output "${OUTPUT_DIR}/repomix.xml"
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Native CLI and explicit include paths.

- Compression omits implementation detail and is not adequate evidence for correctness.

Evidence: [component-history.json](../../evidence/receipts/component-history.json), [portable-cli-artifacts.json](../../evidence/receipts/portable-cli-artifacts.json).

## headroom

Consider a measured API-worker experiment only after native retrieval/caching; do not insert a second compressor into every turn.

License: **Apache-2.0**. Reviewed source: [`bc21c9370793`](https://github.com/headroomlabs-ai/headroom/blob/bc21c9370793f7e4aa94ac4c5d9a67a8d2dd0df9/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
uv tool install --python 3.13 "headroom-ai[all]"
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Supported Python/wheels; explicit provider/proxy configuration.

- Canonical repository moved to headroomlabs-ai/headroom. Compression can discard trading evidence or disturb tool-call structure/cache prefixes.
- Existing offline Headroom artifact handling remains a separate baseline receipt; this proxy/SDK path is unexecuted. Upstream claimed savings do not measure this stack; native Codex subscription and Astra gateway behavior are unproved.

Evidence: [README.md](https://github.com/headroomlabs-ai/headroom/blob/bc21c9370793f7e4aa94ac4c5d9a67a8d2dd0df9/README.md), [v0.37.0](https://github.com/headroomlabs-ai/headroom/releases/tag/v0.37.0).

## toon

Use for homogeneous tabular research handoffs only after a same-data tokenizer comparison; retain canonical JSON/Parquet.

License: **MIT**. Reviewed source: [`f151a5d830d0`](https://github.com/toon-format/toon/blob/f151a5d830d001bc244395b891183cba37e0d935/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
toon fixtures/records.json --stats -o "${OUTPUT_DIR}/records.toon"
toon "${OUTPUT_DIR}/records.toon" --decode --strict -o "${OUTPUT_DIR}/recovered.json"
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: SDK-compatible consumers and lossless round-trip validation.

- Native proof is one encode/decode fixture roundtrip, not generalized token savings. Not universally smaller than JSON, especially nested or irregular records. Not an order-message protocol replacement.

Evidence: [component-history.json](../../evidence/receipts/component-history.json), [portable-cli-artifacts.json](../../evidence/receipts/portable-cli-artifacts.json).

## mem0

Useful when application-level personalized memory becomes a requirement; avoids duplicating the current coding memory store.

License: **Apache-2.0**. Reviewed source: [`a39a802bbc93`](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install mem0ai
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Configured extraction LLM and embeddings; self-hosted authentication configuration.

- Latest GitHub tag openclaw-v1.2.0 belongs to a plugin, not the Python core version.
- Extraction adds model calls and retention decisions; no local financial-memory quality or savings evaluation.

Evidence: [README.md](https://github.com/mem0ai/mem0/blob/a39a802bbc93e85b820078cd3c4dbaf53af25dbe/README.md), [openclaw-v1.2.0](https://github.com/mem0ai/mem0/releases/tag/openclaw-v1.2.0).

## hindsight

Evaluate when time-aware belief/observation consolidation is needed beyond the existing scoped wiki.

License: **MIT**. Reviewed source: [`79a2fb152f17`](https://github.com/vectorize-io/hindsight/blob/79a2fb152f17ad03e94882e9cb6b8b25049f38c0/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install hindsight-api hindsight-client
hindsight-api
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: PostgreSQL or packaged local database path; extraction/reflection model configuration.

- Normal retention/reflection needs a model; managed-service claims do not establish local availability or latency.

Evidence: [README.md](https://github.com/vectorize-io/hindsight/blob/79a2fb152f17ad03e94882e9cb6b8b25049f38c0/README.md), [v0.10.0](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.0).

## OpenViking

Consider when resources, memories and skills need a unified hierarchical retrieval service.

License: **AGPL-3.0 server; Apache-2.0 CLI/examples**. Reviewed source: [`535f0e003444`](https://github.com/volcengine/OpenViking/blob/535f0e003444fb2869d2cbeca95c65b027420780/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install --upgrade openviking
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Python 3.10+; embedding and VLM configuration; storage planning.

- Server moved to AGPL from v0.3; CLI/examples have separate Apache licensing. Commercial BYOC is distinct.
- No migration from ai-memory or measured token improvement performed.

Evidence: [README.md](https://github.com/volcengine/OpenViking/blob/535f0e003444fb2869d2cbeca95c65b027420780/README.md), [v0.4.20](https://github.com/volcengine/OpenViking/releases/tag/v0.4.20).

## cognee

Optional graph-first research when entity relations improve a measured retrieval task.

License: **Apache-2.0**. Reviewed source: [`4294605f2032`](https://github.com/topoteretes/cognee/blob/4294605f20324b250fd0edf8893cb69dc4215369/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
uv pip install cognee
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Python 3.10–3.14 and configured extraction/embedding providers.

- Default provider examples invoke OpenAI; local extraction options require configuration.
- Upstream describes the OSS PostgreSQL graph store as demo; production PostgreSQL graph support has separate licensing.

Evidence: [README.md](https://github.com/topoteretes/cognee/blob/4294605f20324b250fd0edf8893cb69dc4215369/README.md), [v1.6.0](https://github.com/topoteretes/cognee/releases/tag/v1.6.0).

## mempalace

Use only for an explicitly selected archive with retention boundaries; preserve ai-memory as shared durable knowledge.

License: **MIT**. Reviewed source: [`36ec72f95e2e`](https://github.com/MemPalace/mempalace/blob/36ec72f95e2e9f2bd6112891752edff457229f93/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
uv tool install mempalace
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Local embedding download and archive permissions; separate skill/MCP registration.

- Verbatim archive import is broader than bounded lifecycle capture. Publisher recall figures are not independent local results.

Evidence: [README.md](https://github.com/MemPalace/mempalace/blob/36ec72f95e2e9f2bd6112891752edff457229f93/README.md), [v3.10.0](https://github.com/MemPalace/mempalace/releases/tag/v3.10.0).

## EverOS

Track model-backed memory research; run the no-key demo before committing a service migration.

License: **Apache-2.0**. Reviewed source: [`5076683ab88d`](https://github.com/EverMind-AI/EverOS/blob/5076683ab88d714390573d8f88ff3c470e51129a/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
uv pip install everos
uv run everos demo --plain
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Python environment; real extraction/embedding/reranking configuration beyond demo.

- Demo behavior is not a production hybrid-memory evaluation. Office ingestion may require LibreOffice.

Evidence: [README.md](https://github.com/EverMind-AI/EverOS/blob/5076683ab88d714390573d8f88ff3c470e51129a/README.md), [v1.3.1](https://github.com/EverMind-AI/EverOS/releases/tag/v1.3.1).

## claude-mem

Useful in Claude-centric environments, but overlaps existing cross-harness ai-memory capture.

License: **Apache-2.0**. Reviewed source: [`adce0fdfaf1c`](https://github.com/thedotmack/claude-mem/blob/adce0fdfaf1cd46646bbd0b22ae74cbd460ed787/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
CLAUDE_MEM_ONLINE_OPTIN=false npx claude-mem install
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Native installer, background worker, storage and compression provider. Normal installer can request browser sign-in/observer provisioning; opt-out shown avoids new online enrollment.

- Global npm SDK installation alone does not register hooks and worker. Additional capture/consolidation has retention and model-cost consequences.
- Online observer flow documents a 30-day trial and potential Anthropic-plan fallback; it is not free permanent hosted memory.

Evidence: [README.md](https://github.com/thedotmack/claude-mem/blob/adce0fdfaf1cd46646bbd0b22ae74cbd460ed787/README.md), [v13.24.23](https://github.com/thedotmack/claude-mem/releases/tag/v13.24.23).

## graphiti

Candidate for issuer/entity relationships with valid-time provenance; separate it from trading/order state.

License: **Apache-2.0**. Reviewed source: [`de8eb5b896c0`](https://github.com/getzep/graphiti/blob/de8eb5b896c05ed1b5b329d4cb52015446d65e21/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install graphiti-core
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Supported Neo4j/FalkorDB or Neptune/OpenSearch backend; configured LLM and embeddings.

- Canonical repository is getzep/graphiti. Temporal graph assertions still require source timestamps and correction history.
- Default examples use model API credentials; no graph deployment or extraction accuracy proof here.

Evidence: [README.md](https://github.com/getzep/graphiti/blob/de8eb5b896c05ed1b5b329d4cb52015446d65e21/README.md), [v0.30.2](https://github.com/getzep/graphiti/releases/tag/v0.30.2).

## LightRAG

Compare only when cross-document relationships outperform simpler hybrid retrieval on selected filings.

License: **MIT**. Reviewed source: [`e4e261c2b156`](https://github.com/HKUDS/LightRAG/blob/e4e261c2b1566dba67e9a62cb84b9cb122581ae7/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
uv tool install "lightrag-hku[api]"
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Configured generation/embedding model; selected storage backend.

- Entity extraction consumes tokens; graph retrieval is not automatically more accurate or cheaper than lexical+dense search.

Evidence: [README.md](https://github.com/HKUDS/LightRAG/blob/e4e261c2b1566dba67e9a62cb84b9cb122581ae7/README.md), [v1.5.7](https://github.com/HKUDS/LightRAG/releases/tag/v1.5.7).

## ragflow

A full ingestion/UI platform option if enterprise document operations justify the additional services.

License: **Apache-2.0**. Reviewed source: [`302ada2cdbdd`](https://github.com/infiniflow/ragflow/blob/302ada2cdbdd72a5db4bd8e046478e52011fe4f0/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
git clone https://github.com/infiniflow/ragflow.git
git -C ragflow checkout v0.27.2
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Container infrastructure, document storage, model configuration and resource capacity.

- Repository checkout is only preparation; follow pinned compose/model instructions for deployment. No service was installed in this review.
- Do not apply upstream destructive volume-removal examples to retained data.

Evidence: [README.md](https://github.com/infiniflow/ragflow/blob/302ada2cdbdd72a5db4bd8e046478e52011fe4f0/README.md), [v0.27.2](https://github.com/infiniflow/ragflow/releases/tag/v0.27.2).

## WeKnora

Consider for governed multi-user collections and connectors, not as a duplicate personal coding index.

License: **MIT core; third-party notices apply**. Reviewed source: [`2a6a9c251734`](https://github.com/Tencent/WeKnora/blob/2a6a9c251734d12bf65bf17d8f3412689ebed4e1/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
git clone https://github.com/Tencent/WeKnora.git
git -C WeKnora checkout v0.8.0
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Deployment dependencies, chosen model/vector providers and connector permissions.

- Core MIT is subject to third-party notices. Connected sources require explicit scope and authorization.

Evidence: [README.md](https://github.com/Tencent/WeKnora/blob/2a6a9c251734d12bf65bf17d8f3412689ebed4e1/README.md), [v0.8.0](https://github.com/Tencent/WeKnora/releases/tag/v0.8.0).

## PageIndex

Compare on long financial reports where section/table structure is valuable and citations can be checked.

License: **MIT**. Reviewed source: [`9a8dd6658278`](https://github.com/VectifyAI/PageIndex/blob/9a8dd6658278fec90347e8ac3388a205305667a3/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install -U pageindex
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Configured supported LLM; local SDK mode and document-tree generation.

- Vectorless does not mean zero model tokens; tree construction and reasoning have cost. Publisher benchmark is not this system’s finance evaluation.

Evidence: [README.md](https://github.com/VectifyAI/PageIndex/blob/9a8dd6658278fec90347e8ac3388a205305667a3/README.md), [v0.2.18](https://github.com/VectifyAI/PageIndex/releases/tag/v0.2.18).

## letta

Current upstream explicitly retires V1 and points to letta-ai/letta-code; retain this card to prevent stale installation guidance.

License: **Apache-2.0**. Reviewed source: [`5bcdd177d70f`](https://github.com/letta-ai/letta/blob/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
git ls-remote https://github.com/letta-ai/letta.git HEAD
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Historical reproduction only.

- Old v0.16.8 release is not the current active harness. Do not deploy the retired server as the latest stack.

Evidence: [README.md](https://github.com/letta-ai/letta/blob/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a/README.md), [0.16.8](https://github.com/letta-ai/letta/releases/tag/0.16.8).

## letta-code

Active successor with memory blocks, MemFS, hooks and native provider connections; evaluate as a separate harness.

License: **Apache-2.0**. Reviewed source: [`8994497c7f5b`](https://github.com/letta-ai/letta-code/blob/8994497c7f5bc29da97fdad8703e4531152ca631/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
npm install -g @letta-ai/letta-code
letta
letta server
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Node runtime and native /connect login/provider setup; managed remote features may require Letta account.

- Not a transparent memory plugin for Codex/Claude. Autonomous context/skill rewriting must not redefine deterministic trading controls.
- AgentFile import/export was removed; do not reuse old V1 recipes.

Evidence: [README.md](https://github.com/letta-ai/letta-code/blob/8994497c7f5bc29da97fdad8703e4531152ca631/README.md), [v0.32.13](https://github.com/letta-ai/letta-code/releases/tag/v0.32.13).

## haystack

Preferred explicit RAG pipeline candidate when financial document evaluation requires a maintained application framework.

License: **Apache-2.0**. Reviewed source: [`b717d00654af`](https://github.com/deepset-ai/haystack/blob/b717d00654af0dc405e5cec35546d734c832042f/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install haystack-ai
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Selected retriever, document store and model integrations.

- No financial corpus pipeline or performance proof yet; enterprise platform is separate.

Evidence: [README.md](https://github.com/deepset-ai/haystack/blob/b717d00654af0dc405e5cec35546d734c832042f/README.md), [v3.1.1](https://github.com/deepset-ai/haystack/releases/tag/v3.1.1).

## llama_index

Useful targeted connectors; select core plus needed integrations instead of broad dependency bundles.

License: **MIT**. Reviewed source: [`f475afd8a9bb`](https://github.com/run-llama/llama_index/blob/f475afd8a9bbda84f252567e045d89d07b5701b3/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install llama-index-core
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Explicit provider integration packages and document permissions.

- Current README prioritizes LlamaParse/liteparse/benchmarks; reassess active integration maintenance. Managed parsing can have separate cost/data transfer.

Evidence: [README.md](https://github.com/run-llama/llama_index/blob/f475afd8a9bbda84f252567e045d89d07b5701b3/README.md), [v0.14.24](https://github.com/run-llama/llama_index/releases/tag/v0.14.24).

## qdrant

Keep the existing native service already accepted with SocratiCode and Nemotron.

License: **Apache-2.0**. Reviewed source: [`6ab21cac18eb`](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
qdrant --config-path "${QDRANT_CONFIG}" --disable-telemetry
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Existing configured native binary/service and per-project collection.

- Installed code search does not imply a financial-doc corpus exists. Enforce as-of/source/tenant metadata in future corpora.

Evidence: [native-rag.json](../../evidence/receipts/native-rag.json).

## pgvector

Prefer when a future service already uses PostgreSQL and benefits from transactionally joined metadata.

License: **PostgreSQL**. Reviewed source: [`efa08fda9ec4`](https://github.com/pgvector/pgvector/blob/efa08fda9ec485d80292d0487a77939c087dedcc/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
git clone --branch v0.8.6 https://github.com/pgvector/pgvector.git
make -C pgvector
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: PostgreSQL 13+, build dependencies and explicit database installation.

- No GitHub release object; v0.8.6 is the documented tag. Build is not database extension activation.
- Adds no benefit to current Qdrant code index unless a specific SQL integration need is established.

Evidence: [README.md](https://github.com/pgvector/pgvector/blob/efa08fda9ec485d80292d0487a77939c087dedcc/README.md).

## lancedb

Consider local research corpora co-located with columnar artifacts without another service.

License: **Apache-2.0**. Reviewed source: [`df5709efd841`](https://github.com/lancedb/lancedb/blob/df5709efd8411b66095e29f708290a3e2c80f0fe/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install lancedb
python -c "import lancedb; db = lancedb.connect('./research-vectors'); print(db.table_names())"
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Compatible CPU wheel; standard x86 wheel requires AVX2/FMA/F16C, older CPUs need lancedb-compat instead.

- Cloud/enterprise API differs from local embedded mode. Generated vectors and filters must still be validated.

Evidence: [README.md](https://github.com/lancedb/lancedb/blob/df5709efd8411b66095e29f708290a3e2c80f0fe/README.md), [v0.39.0](https://github.com/lancedb/lancedb/releases/tag/v0.39.0), [quickstart](https://docs.lancedb.com/quickstart).

## docling

Preferred document-layout candidate before evaluating complex filing RAG.

License: **MIT**. Reviewed source: [`890dd42d0174`](https://github.com/docling-project/docling/blob/890dd42d017497c955a56a1d2cfc3f0af5bc2aa9/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install docling
docling --help
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Document-specific pipeline/model downloads and sufficient CPU/GPU resources.

- MIT applies to code; downloaded OCR/layout/model weights retain separate licenses. Table/unit extraction quality is unmeasured.

Evidence: [README.md](https://github.com/docling-project/docling/blob/890dd42d017497c955a56a1d2cfc3f0af5bc2aa9/README.md), [v2.129.0](https://github.com/docling-project/docling/releases/tag/v2.129.0).

## markitdown

Use the installed lightweight converter for supported inputs before adding an OCR platform.

License: **MIT**. Reviewed source: [`945314a45ddb`](https://github.com/microsoft/markitdown/blob/945314a45ddbe02935f2fd287b797dc0ba4a01e4/README.md). Only the referenced receipt scope ran; commands may be prospective replays with operator-selected paths.

```text
markitdown fixtures/greeting.html
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Existing base package.

- Current proof is local HTML conversion only; PDF/Office extras are not installed or proven.

Evidence: [component-history.json](../../evidence/receipts/component-history.json), [portable-cli-artifacts.json](../../evidence/receipts/portable-cli-artifacts.json).

## mteb

Use reproducible benchmark tasks plus a domain-specific financial retrieval set to compare upgrades.

License: **Apache-2.0**. Reviewed source: [`8ecdd976aad5`](https://github.com/embeddings-benchmark/mteb/blob/8ecdd976aad52ee9d5718772065438ec60ed388a/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install mteb
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Task datasets, model runtime and reproducible evaluation configuration.

- Public leaderboard is not independent proof for code retrieval, point-in-time filings or net trading performance.

Evidence: [README.md](https://github.com/embeddings-benchmark/mteb/blob/8ecdd976aad52ee9d5718772065438ec60ed388a/README.md), [2.21.0](https://github.com/embeddings-benchmark/mteb/releases/tag/2.21.0).

## sentence-transformers

Use supported publisher recipes for model-specific pooling/prefixes; canonical project moved to Hugging Face.

License: **Apache-2.0**. Reviewed source: [`f3864a53cfaf`](https://github.com/huggingface/sentence-transformers/blob/f3864a53cfafb40a6f03f029ce96da70591e9931/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
pip install -U sentence-transformers
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Compatible PyTorch/Transformers and model-specific license/runtime.

- A generic feature-extraction pipeline is not a substitute for documented model wrappers. Newest package does not establish compatibility with the current vLLM service.

Evidence: [README.md](https://github.com/huggingface/sentence-transformers/blob/f3864a53cfafb40a6f03f029ce96da70591e9931/README.md), [v6.1.0](https://github.com/huggingface/sentence-transformers/releases/tag/v6.1.0).

## agent-retrieval-bench

Useful acceptance framework for code-context quality per fixed context budget and abstention.

License: **MIT**. Reviewed source: [`07014c986f3d`](https://github.com/eyuansu62/agent-retrieval-bench/blob/07014c986f3deadb1548c62b32c0ffbe6a81465d/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
git clone https://github.com/eyuansu62/agent-retrieval-bench.git
pip install -e ./agent-retrieval-bench
arb releases
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Python 3.10+, chosen corpus snapshots and evaluator.

- 427 examples across 25 repositories are not a financial-document benchmark. Large-project concentration and no-gold cases affect interpretation.
- No benchmark download/evaluation performed; freezing source and budgets is required.

Evidence: [README.md](https://github.com/eyuansu62/agent-retrieval-bench/blob/07014c986f3deadb1548c62b32c0ffbe6a81465d/README.md), [v0.2.1](https://github.com/eyuansu62/agent-retrieval-bench/releases/tag/v0.2.1).

## engram-benchmark

Track memory retention/usefulness separately from compression size.

License: **MIT**. Reviewed source: [`ef432e3323ee`](https://github.com/Ubundi/engram-benchmark/blob/ef432e3323eea4a298c6d53ff645d3fd322361a2/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
git clone https://github.com/Ubundi/engram-benchmark.git
uv sync --project engram-benchmark --dev
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Configured agent adapter, seeded tasks and optional judge model.

- Current practical adapters center on OpenClaw; Codex/Claude support is unproved. No benchmark execution or universal memory ranking claimed.

Evidence: [README.md](https://github.com/Ubundi/engram-benchmark/blob/ef432e3323eea4a298c6d53ff645d3fd322361a2/README.md).

## supermemory

Consider for a separate application memory service if its ownership/API model is preferable to existing stores.

License: **MIT**. Reviewed source: [`57b430b5b6a1`](https://github.com/supermemoryai/supermemory/blob/57b430b5b6a19106a989651f4cde853c05147682/README.md). Pinned upstream source review; commands are prospective and were not executed for this candidate.

```text
npx supermemory local
```

Workflow pins: Native receipt replays have their own pinned environments. Commands without explicit versions are moving upstream entry points, not reproducible installs of this reviewed snapshot; select and lock the named version/commit before deployment.

Requirements: Local embedding download/storage; service authentication; selected generation/extraction provider or local Ollama model. API costs or model downloads are separate; cloud option separately configured.

- Native local startup can print a generated API key: keep its output private. Publisher benchmark leadership is not a local result.
- Not installed or integrated; avoid duplicate automatic capture.

Evidence: [README.md](https://github.com/supermemoryai/supermemory/blob/57b430b5b6a19106a989651f4cde853c05147682/README.md), [server-v0.0.8](https://github.com/supermemoryai/supermemory/releases/tag/server-v0.0.8).
