# Memory and RAG: final upstream architecture recommendations (2026-10-07)

**Decision:** use the five stacks below for their named workloads. The primary
modular recommendation is **Hindsight + Docling + Haystack + Qdrant, with Opik
for measurement**. These are final choices for this bounded source-review unit,
not a universal accuracy ranking or an installation plan.

The [machine-readable catalog](../../catalogs/foundation/memory-rag-stacks-20261007.json)
contains the component responsibilities and operating requirements. The
[review record](../../evidence/artifacts/memory-rag-stacks-20261007/review.json)
retains immutable inspected revisions, release metadata, source locators,
observed CI failures, benchmark limits and the completeness critique for all
18 repositories. It is the evidence behind the judgments below.

## Final stacks

| Workload | Architecture | Why this wins its role |
| --- | --- | --- |
| General agent memory and document RAG | [Hindsight](https://github.com/vectorize-io/hindsight) + [Docling](https://github.com/docling-project/docling) + [Haystack](https://github.com/deepset-ai/haystack) + [Qdrant](https://github.com/qdrant/qdrant) + [Opik](https://github.com/comet-ml/opik) | Advanced temporal/entity memory, structured ingestion, explicit retrieval pipelines, a substantially tested retrieval store, and inspectable measurement. |
| Codex/Claude coding continuity | [ai-memory](https://github.com/akitaonrails/ai-memory) + [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp); optional [SocratiCode](https://github.com/giancarloerra/SocratiCode) | Durable cross-client knowledge and handoffs have one owner; structural code context comes from source. Add semantic infrastructure only for a distinct conceptual-search requirement. |
| Personalized applications with document evidence | [Mem0](https://github.com/mem0ai/mem0) + Docling + Haystack + Qdrant + Opik | Mem0 provides the user/session memory API; the remaining components provide source evidence and measurement. Mem0 replaces Hindsight in this stack. |
| Packaged document RAG | [RAGFlow](https://github.com/infiniflow/ragflow) and its supported deployment services | Strong integrated OCR/layout/table processing, visible chunks and citations. Release-transition risk reduces confidence in an immediate deployment choice. |
| Connected workplace knowledge | [Onyx](https://github.com/onyx-dot-app/onyx) and its supported deployment services | Connectors, permission ingestion, indexing workers and the search/agent application form the strongest reviewed product for this requirement. |

The first and third stacks share a document-retrieval foundation; they are
alternatives for the memory owner. Packaged RAGFlow and Onyx are alternative
application stacks, not mandatory additions to the modular stack.

In the general architecture, Hindsight retains agent knowledge. Docling parses
source documents; Qdrant stores searchable document evidence; Haystack composes
retrieval, ranking and generation context; Opik records traces and directly
tested evaluation metrics. Hindsight's own supported database is separate from
the document store. The inspected [Docling integration](https://docs.haystack.deepset.ai/docs/doclingconverter),
[Qdrant hybrid retriever](https://docs.haystack.deepset.ai/docs/qdranthybridretriever)
and [Opik integration](https://www.comet.com/docs/opik/integrations/haystack)
document pairwise interfaces. No complete composition was executed here.

## Upstream-quality evaluation

The review considered architecture, actual test workflows, release discipline,
integration documentation, licensing, maintenance and the reproducibility of
published evaluations. Stars were discovery input only: the authenticated
inventory contained 366 repositories, and a metadata filter identified 56
memory/retrieval-related candidates. Fifteen reviewed repositories were in that
inventory; Docling, Haystack and Qdrant were explicit additions. The bounded
shortlist is not an exhaustive global landscape audit.

| Component or class | Evidence supporting the judgment | Material limitation retained |
| --- | --- | --- |
| Hindsight | Retain/recall/reflect, temporal and entity retrieval, public evaluation harness and API/SDK/deployment workflows. | Latest retrieved successful core CI was on an earlier revision. Current AMB jobs failed for missing Groq credentials, not an accuracy threshold. Mutable published-image scans failed; a stable image digest's status was not established. |
| Docling / Haystack / Qdrant | Parser regression fixtures and OCR/model lanes; successful Haystack unit/integration jobs on three OSes; successful Qdrant distributed/consensus/consistency/snapshot jobs. | Docling head had running checks. Haystack's inspected successful tests were on an earlier revision and its workflow can skip tests. Qdrant had a Dependabot failure and model testing in progress. These are not all-green release claims. |
| Opik | SDK E2E and library integration workflows, including successful inspected Python 3.10-3.14 jobs. | A Ragas adapter rejected `bypass_temperature` (1 failed, 57 passed, 12 skipped in the inspected job); another OpenAI integration failure was not classified. Do not assume all metric adapters work. |
| ai-memory | Portable wiki/index architecture, owned handoffs, backup/recovery engineering, official artifacts and substantial CI; 68 successful reviewed-head checks. | Upstream v2.6.0 availability does not upgrade a deployed pin or prove retrieval superiority. |
| codebase-memory / SocratiCode | Platform/sanitizer testing and official artifacts for the structural tool; real Qdrant/Ollama integration tests for semantic search. | codebase-memory had a failed publish check and an evaluation plan without executed scores. SocratiCode adds services, AGPL/commercial licensing and a floating Ollama CI image. |
| Mem0 | Successful current Python and TypeScript CI, application-oriented APIs, and public evaluation code. | Its strongest advertised hosted scores include proprietary optimizations absent from the OSS SDK. The latest GitHub release `ts-v3.3.1` names the TypeScript channel, not every package. |
| RAGFlow | Integrated document capabilities and real API tests against Infinity and Elasticsearch. | Latest `v1.0.0-rc1` is a substantial Go rewrite, despite GitHub's `prerelease=false` flag. Reviewed Go-era main failed both backend integrations; Infinity reported 7 failed, 223 passed and 200 skipped. These failures do not establish that older `v0.27.2` fails; that release's acceptance was not verified here. |
| Onyx | Connector/permission architecture and integration, database, browser and MIT/EE test paths. | Inspected current-head checks included failures/cancellations; an expanded EE build failed on Docker Hub token/network timeout. This is not a demonstrated retrieval defect. Lite cannot index documents; `ee` directories have a separate license. |

Observed hosted CI is source evidence about those named revisions. It is not a
new local test run, release-tag acceptance, a native-client lifecycle result or
proof of comparative answer quality. Later green checks may supersede a dated
observation but must not erase the recorded failed attempt.

## Specialists and alternatives

- **PageIndex:** select for long text-heavy documents requiring hierarchical
  reasoning and page references. Its local OSS lacks OCR/image understanding;
  the published OSS benchmark uses 62 text-lookup questions over 34 ingestible
  PDFs, excluding tables, charts, arithmetic and refused documents.
- **RAG-Anything:** select as a multimodal framework when image/table/equation
  retrieval is required. Parser/model integration remains application work;
  complete dataset provenance and reproduction were not audited.
- **OpenViking:** consider when one inspectable memory/knowledge/skills context
  system is itself the requirement. Its progressive context design is strong;
  AGPL terms and its lifecycle remain distinct from a matched quality win.
- **Cognee:** select for explicit ontology and graph-relationship requirements.
  Some production extraction/storage paths have separate licensing, and current
  cloud/image checks failed. Its BEAM report discloses tuning and orchestration
  limits that prevent a general SOTA claim.
- **agentmemory and MemPalace:** credible challengers with meaningful source
  engineering. Retrieval-only recall, tuned results and answer accuracy are
  different metrics; their numbers do not settle the memory comparison.
- **Supermemory:** a product/integration alternative. The inspected MCP client
  defaults to the hosted API; public-source-to-binary core parity was not
  established in this review.

## Scope, ownership and what remains unspecified

This entry supports research and engineering infrastructure, including the
foundation used for North Star work. It does not qualify a strategy, market-data
source, execution engine or broker. It adds source-review recommendations to
the catalog without changing deployment selections, `manifests/stack.json`,
host receipts, services, native authentication or model routes.

It does not settle or reopen independently owned memory/code-search trials,
consume sealed evidence, or claim the separate final-catalog synthesis is
complete. The dated [repository-quality rule](2026-10-04-repository-quality-rule.md)
and its scoped exceptions retain their own authority. This source-review unit
does not queue an experiment or claim blind cross-family convergence.

The completeness critic identified these remaining specification gaps:

1. Embedding, sparse-retrieval, reranking and generation model selections and
   exact revisions.
2. Compatible package locks, deployment configuration and immutable image
   digests.
3. Representative ingest/retrieve/rerank/generate/cite/evaluate/remember
   lifecycle, permission propagation, recovery, latency and complete cost.
4. Independent matched comparative evaluation; the reviewed vendor benchmarks
   use different data, configurations and metrics.

Those are next-sweep inputs, not tasks or installations authorized by this
catalog entry. No local upstream suite or model benchmark was run for this
review; complete whole-task usage and net token savings are unknown.

**Revisit a recommendation** when a cited upstream regression, license or
compatibility gap, independent matched result, or simpler architecture meeting
the same requirements changes the evidence. Preserve this dated record when
superseding it. Recommendations, observed upstream quality and runtime
qualification remain separate fields.
