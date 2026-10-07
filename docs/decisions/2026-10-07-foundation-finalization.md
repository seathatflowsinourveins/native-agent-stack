# Foundation finalization: memory and RAG owners, retrieval models, runtime pins, Mac host changes and readiness dispositions (2026-10-07)

Date: 2026-10-07. Lane: foundation. Base: `475127d43c1cce70dba5cd31238af4e078fa17eb`.
North-star action: finish the native foundation for US-equities research and
historical simulation, so the broker-specific paper lanes can follow under
`docs/paper-lane-policy.md`.

## Authority and rule

The owner's directions of 2026-10-07, quoted verbatim:

> STOP making the date plan, resolute here any now with full landscapes of sota aligned practice

> the license is never a gate for this priveate env

Selection follows the [2026-10-06 upstream-evidence rule](2026-10-06-upstream-evidence-over-local-evaluation.md):
maintainer organization, release discipline, CI at the release tag, documented
role fit, self-hosted deployability and client integration decide; same-model,
same-split benchmarks break ties; vendor numbers inform and never rank. License
is an information column ([harness defaults](../harness-defaults.md#build-on-upstream-as-foundation-platform-and-runtime-workers)).
This record turns the 2026-10-07 [memory and RAG proposals](2026-10-07-memory-rag-source-stacks.md)
(`proposed_source_review`) into selections for the rows below; the catalog
maintainer updates `catalogs/foundation/memory-rag-stacks-20261007.json` status
on landing. No row here records host acceptance unless the Mac section says so.

**Correction carried:** an earlier same-day relay disqualified OpenViking and
Cognee from the owner role on license. That was wrong under the rule above; the
re-ranked outcome is below and the correction is recorded in the shared memory
page `decisions/correction-license-not-a-gate-20261007.md`.

## Memory and RAG owners

| Role | Owner (pin) | Runner-up | Evidence | Overturn condition |
| --- | --- | --- | --- | --- |
| Codex/Claude coding continuity | [ai-memory](https://github.com/akitaonrails/ai-memory) v2.6.0 (published 2026-10-07T03:50:06Z; promote after the 24-hour gate, 2026-10-08T03:50Z) with [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) 0.11.0; [SocratiCode](https://github.com/giancarloerra/SocratiCode) 1.16.0 optional | rohitg00/agentmemory v0.9.30 | 400 commits since v2.5.2, including the GHSA-7qj3-7wqw-m5w6 global-scope write authorization fix (multi-user mode) and wiki path confinement (CHANGELOG `## [2.6.0]`, Security and Fixed sections) | a published regression at v2.6.0 holds v2.5.2 |
| General agent memory (research agents) | [Hindsight](https://github.com/vectorize-io/hindsight) v0.10.2 (2026-09-29) | [Cognee](https://github.com/topoteretes/cognee) v1.6.3 (2026-10-07) | retain/recall/reflect; semantic, BM25, graph and temporal retrieval with reranking; first-party MCP and Claude/Codex integrations; tag `5fc4ce20` release jobs 19/19 (tests run on pull requests; nearest test run PR #4428 head `8402a647`: 120 pass, 0 fail) | a failing unit or integration test at Hindsight's next stable tag while Cognee's tag is green |
| Graph and temporal knowledge specialist | [Graphiti](https://github.com/getzep/graphiti) v0.30.2 with MCP server mcp-v1.1.0 | Cognee v1.6.3 | bi-temporal edges with automatic fact invalidation (README at v0.30.2 L145); tag `eaa41286` 31/31 | a failing unit or database-integration test at Graphiti's next stable tag while Cognee's tag is fully green |
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
| Claude Code | keep 2.1.292 | 2026-10-07T18:59:30Z |
| GPT Researcher, DeerFlow, DSPy | keep v3.7.0, v2.1.0, 3.4.0 (latest tags) | n/a |
| OmniRoute | keep the v3.8.51 + #15167 + affinity composition; #15167 is still open on untagged release/v3.8.52 | a tag containing `0585aba5` |

## Instruction practice adopted from current client sources

- Claude Code reads `AGENTS.md` natively (CHANGELOG 2.1.277); instruction files no longer prescribe an `@AGENTS.md` import.
- The Agent tool takes a per-call `effort` (2.1.292); frontmatter effort remains valid (2.1.267, 2.1.288).
- Claude runs a skill named exactly `verify` before commits (2.1.286); projects provide a `verify` skill that wraps their acceptance commands.
- `omitClaudeMd` (2.1.271) suits blind judges and reviewers.
- Codex user skills live under `$HOME/.agents/skills`; `$CODEX_HOME/skills` is the deprecated location (codex-rs `host_roots.rs` at rust-v0.160.0, L96-107).
- Always-loaded instructions stay a short map (Claude memory guidance: files over 200 lines reduce adherence); procedures go to skills, enforcement to hooks and settings.

## Mac coordinator host changes (native_proven on the Mac, 2026-10-07)

| Change | Evidence | Rollback |
| --- | --- | --- |
| Codex 0.160.0 → 0.160.1 from `codex-package-aarch64-apple-darwin.tar.gz` (SHA256 `f73527ee…c6314`) | `codex --version` 0.160.1; `codex mcp list` exit 0 | relink `~/.local/bin/codex` to the retained 0.160.0 directory |
| OTel Collector Contrib 0.162.0 (`otelcol-contrib_0.162.0_darwin_arm64.tar.gz`, SHA256 `d5e11974…5f97a`) as a launchd agent, using `observability/collector/collector.yaml` without the Loki exporter and the two workstation-only `http_check` targets | `otelcol-contrib validate` exit 0; health 200 on 14333; Claude and Codex tool, MCP, hook and API events reach `file/events`; Prometheus exporter on 18889 | unload the agent; both clients then drop telemetry as before |
| Chrome DevTools MCP 1.10.1 registered at user level in both clients with `--isolated` | one real `list_pages` call answered in Claude and in Codex (Codex reported 27,333 tokens); both calls appear in the collector with `mcp_server.name=chrome-devtools` | `claude mcp remove chrome-devtools --scope user`; `codex mcp remove chrome-devtools` |
| context-mode marketplace pinned to `v1.0.169`; Codex `codebase-memory` skill moved to `~/.agents/skills` | readback of `known_marketplaces.json`; skill present at the new location | restore the backed-up file and directory |
| `tools/token-report` refresh | RTK 4,406,580 tokens saved across retained projects (4,288,399 for one project); headroom 20,968 over 30 days; jCodeMunch 0 session calls and 0 saved | read-only |

These are each tool's own estimates, not net provider savings. jCodeMunch is
installed and organically unused on the Mac; under the 2026-10-06 rule its missing
use stays explicit. The ai-memory swap waits for its gate and runs: stop the agent,
`ai-memory backup --to <dated tarball>`, copy the 2.5.2 directory to a 2.6.0
directory, run `ai-memory upgrade --version v2.6.0` from the copy, repoint the
launchd program and `~/.local/bin/ai-memory`, start, then `ai-memory doctor` and an
MCP status read from both clients. Rollback restores the backup and the 2.5.2 path.
`claude-plugins-official` publishes no tags and stays unpinned.

## NativeStack2604 readiness dispositions (proposed for the readiness owner)

The 2026-10-05 slot record holds 18 READY and 12 BY_DESIGN of 80 (historical #700
labels). The same day's correction excluded seven slots from READY (ccusage,
command-output, native-clients/codex, session-analytics, alerting, Serena, MinerU);
of those, only native-clients/codex carried a READY baseline label. Under the
2026-10-06 bar (selection, installation, an integration smoke check in each client
and organic counters), the 50 open slots plus native-clients/codex fall into three
groups:

1. **Re-adjudicate with existing evidence:** native-clients/codex (at the selected 0.160.1, then 0.161.0 after its gate), agent-sdks/codex-sdk-and-codex-exec-app-server, ci-supply-chain/syft, code-navigation/serena, code-navigation/structural-search, cross:credential-practice/credential-guard, document-retrieval/tobi-qmd, git-github-automation/git, instructions-skills/engineering-process-skills, instructions-skills/research-skill, instructions-skills/trail-of-bits-security-skills, observation-inference/local-generation-model, observation-inference/otel-collector-contrib, secrets-credentials/betterleaks, semantic-rag/embedding-model, the nine token-efficiency slots (api-docs, code-graph, code-index, command-output, context-supply, doc-conversion, output-compression, repo-packing, structured-data), workers/agent-messaging (2026-10-06 launch-and-close gate), web-research/playwright-cli (2026-10-06 Chrome DevTools fixture), quality-evaluation/harbor-containerized-agent-e2e-runner, observation-inference/alerting (user-accepted Telegram receiver), token-efficiency/statusline (user observation) and durable-memory/memory-owner (ai-memory 2.6.0 after its gate; the head-to-head no longer gates).
2. **BY_DESIGN:** secrets-credentials/credential-custody (private 0600-file practice), token-efficiency/token-lane-carriers (documented holdout), token-efficiency/trace-viewer (traces are off by the 2026-09-26 decision) and document-retrieval/mineru (Docling owns parsing; MinerU is the runner-up).
3. **Fix and smoke on the host:** observation-inference/session-analytics (agentsview v0.44.0), token-efficiency/ccusage, cross:gpt6-harnesses/gpt-gateway (smoke the running composition; the canary is superseded), cross:runtime-workers/agent-runtime-worker (OpenHands v1.53.0), cross:runtime-workers/research-harnesses, cross:wsl-distro/base-distribution (the binfmt unit), git-github-automation/cross-family-review (Claude turn limit), git-github-automation/difftastic and worktrunk (empty print prompt in the staged check), instructions-skills/skill-authoring (rerun after PyYAML provisioning), isolation/sandbox-runtime-srt, mcp-surfaces/mcp-inspector (libnspr4 for the web smoke), observation-inference/grafana (configuration drift), observation-inference/local-model-server, quality-evaluation/inspect-ai (non-relative example path), quality-evaluation/promptfoo.

**Still open:** the semantic-rag/code-search owner. The portable instructions name a
`semble` MCP server, the slot record supports Semble use, and SocratiCode is the Mac's
installed semantic code search; no source comparison in this record settles the owner.

## Readiness verdict

Selections are complete except the code-search owner. The foundation is not READY
by the 2026-10-06 bar until the fix-and-smoke group clears on NativeStack2604, which
is its owner's host work. Offline North Star research was never blocked by these
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
