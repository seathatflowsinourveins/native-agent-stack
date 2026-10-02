# Final deployment verdict — 2026-10-02

**Decision: retain the existing native core; do not replace the shared memory
backend. This decision unit is closed. No further candidate experiment or canary
is queued by it.** The unexecuted comparison is closed as insufficient evidence
for replacement, not left running and not converted into a passed test.

This is a deployment decision for the existing Mac environment. It does not
declare a universal retrieval winner, full production readiness or acceptance
on a new WSL host. The north-star benefit is dependable project decisions and
source-grounded engineering context without adding another capture service.

## The architecture

| Responsibility | Selected component and boundary |
| --- | --- |
| Native work | Codex and Claude keep native authentication, compaction and caching. GPT-6.1 Sol is the primary worker; this user's requested native effort is Ultra. Astra is a bounded escalation for a consequential unresolved judgment. |
| Instructions and source truth | Git owns project code, concise AGENTS/CLAUDE instructions, versioned decisions and evidence. A retrieved assertion must resolve to its exact source/revision before it is used as current truth. |
| Shared durable memory | Retain official ai-memory 2.5.2 as the single existing memory owner for scoped decisions and handoffs. Markdown is the readable knowledge source; derived indexes support retrieval. Database-only queue state and external configuration must also be backed up. |
| Document retrieval | Use the configured QMD collections for selected documents and exact source reads; retain lexical/file lookup as the dependable fallback. Semantic retrieval and generated answers are not required for the accepted core. |
| Code retrieval | Start with identifiers and syntax search; use the configured structural index with revision/coverage checks and actual-source fallback. Static graph evidence does not establish semantic code-search quality. |
| Context transport | Native compaction/caching plus bounded Context Mode for large outputs. Tool-output indexes and raw histories do not become the canonical decision store. |
| SDK work | Use explicit provider/model requests through OmniRoute, as directed. Native CLI authentication stays native. A separate successful SDK route does not validate the gateway's legacy native-CLI adapters. |
| Evaluation and rollback | Keep pinned upstream Inspect tooling and its archived comparison contract, immutable failure records, matching snapshots and guarded GitHub PR integration. Evaluation is not an always-running service. |

Ollama 0.34.4 remains the existing Mac local-inference pin; this unit does not
upgrade it or make local generation, reranking or LLM consolidation a dependency
of the accepted core. Existing service configuration was not changed. Exact
scope, explicit reads and source verification are the accepted operating contract;
universal automatic capture/resume correctness is not promised.

## What the evidence establishes

- **Implementation:** 20 deterministic regression tests passed. The upstream
  Inspect CLI executed 12 authored development samples with no errors, all scores
  1.0 and zero model events. One scoped unchanged upstream solver test passed.
  These prove integration and fixture behavior, not model/backend superiority.
- **Recovery:** the actual isolated ai-memory backup restored a wiki page and a
  DB-only pending message into a separate volume; both survived restart.
  External configuration was recovered separately. The owned Colima profile is
  stopped; its rollback volumes are retained. See [the receipt](runtime/observed-20261002.json).
- **Native/gateway boundary:** native Codex and Claude authentication was
  observed. A separately owned, completed Sol SDK review through OmniRoute has
  27/27 protocol checks. It does not provide a blind cross-family memory verdict
  or qualify the legacy ACP adapters. The [source owner's handoff](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384#issuecomment-5947617075)
  and [closure record](closure.json) identify that evidence without publishing
  native histories or credentials.
- **Counterevidence is retained:** the canonical historical retrieval record
  favors agentmemory and plain BM25 over the tested ai-memory prerelease.
  With the same MiniLM embedder, session recall_all@5 was 0.821 versus 0.496;
  BM25 was 0.747. The 470-question descriptive runs did not match native capture,
  hooks or reranking and are not current-release production acceptance. They
  prevent a claim that ai-memory is the best retriever. See the [canonical
  qualification](../../../docs/decisions/2026-10-01-new-wsl-definitive-defaults.md#qualifications-of-the-blind-rounds-memory-pick).

The retained choice follows the existing shared-memory integration, recoverable
state and absence of a qualified replacement. It is not protected from contrary
evidence. Document/code retrieval remains a separate source-grounded lane rather
than relying on ai-memory to answer every knowledge question.

## Candidate dispositions

| Candidate | Final disposition for this deployment | Reason |
| --- | --- | --- |
| ai-memory 2.5.2 | **Retain existing shared memory** | Existing integration and scoped recovery evidence; no claim of best retrieval or complete native lifecycle acceptance. |
| Native files, lexical lookup and configured QMD | **Retain source retrieval** | Transparent versioned sources and exact-read fallback; semantic quality is not assumed from index availability. |
| Hindsight 0.10.2 / coding-agents 0.8.0 | **Not selected as the default** | Self-hosted upstream artifacts and private API evidence exist. No accepted matched native capture/lifecycle/quality result establishes a replacement. Repository quality is not rejected. Existing isolated staging is preserved. |
| agentmemory | **Not selected as shared capture** | Historical retrieval strength is real descriptive evidence; the required native hook/handoff comparison is absent. |
| Mem0, LangMem, Zep/Graphiti, basic-memory, mcp-memory-service, OpenViking, cognee, MemPalace, Hindsight alternatives and hosted memory APIs | **Not selected for this deployment** | No accepted same-host replacement result in this unit. Adding another default memory owner would duplicate responsibility. This disposition is not a claim that each repository failed a benchmark or was exhaustively runtime-tested. |
| New ACP bridge, new embeddings/reranker/consolidation stack | **Not adopted by this unit** | Source compatibility or partial probes do not establish the missing native operational contract. No installation or autonomous trial is queued. |

## Known limits are final dispositions, not running tests

The 60-case holdout, matched native lifecycle/latency comparison, blind
cross-family memory convergence and 20-session canary were **not executed by
this unit**. Full-stack readiness is **not established**. Whole-task usage and
net savings remain **unknown**. Historical failures remain unchanged.

At tag 2.5.2, the canonical source audit records next-session handoff claim
semantics, managed-Codex fixes absent from that release and cross-scope purge
caveats. Do not infer directed-session delivery from a pending handoff or apply
scope-local purge assumptions. Keep explicit scope/source reads; the documented
managed-Codex `--no-daemon` caveat is relevant until an appropriate official
release is separately adopted. This closure performs no purge or upgrade.

The [prospective protocol](PREREGISTRATION.md) is archived for reference. A future
replacement requires a **new explicitly scoped decision unit** with suitable
current-release, host, capture, lifecycle, quality and independent convergence
evidence. It is not unfinished work silently carried by this closed decision.

Official releases were refreshed at closure: [ai-memory v2.5.2](https://github.com/akitaonrails/ai-memory/releases/tag/v2.5.2)
and [Hindsight v0.10.2](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.2)
remain the latest reported releases. Canonical source: `b9dbe3c5a09cdefca435cd78c7f3dad46ca883a4`.
