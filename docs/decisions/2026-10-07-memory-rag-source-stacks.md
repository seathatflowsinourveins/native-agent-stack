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

Component selection follows the [October 6 upstream-evidence rule](2026-10-06-upstream-evidence-over-local-evaluation.md),
integrated in canonical commit `79619936926576576e5d011eec19e3790e55f457`.
That rule supersedes the older foundation-selection exceptions and local
comparison gates. Published upstream quality determines these recommendations;
installation, client wiring smoke checks and organic-use evidence establish
their separate deployment status. Historical trial artifacts retain their
original results and scope. This review does not change installed selections,
consume sealed evidence, queue an experiment, claim blind cross-family
convergence or finalize the separately owned catalog synthesis.

The completeness critic identified these remaining specifications and evidence limits:

1. Embedding, sparse-retrieval, reranking and generation model selections and
   exact revisions.
2. Compatible package locks, deployment configuration and immutable image
   digests.
3. Representative ingest/retrieve/rerank/generate/cite/evaluate/remember
   lifecycle, permission propagation, recovery, latency and complete cost.
4. The reviewed vendor benchmarks use different data, configurations and
   metrics; no matched complete-application comparison was performed. This is
   an evidence limit, not a prerequisite for these component recommendations.

Those are next-sweep inputs, not tasks or installations authorized by this
catalog entry. No local upstream suite or model benchmark was run for this
review; complete whole-task usage and net token savings are unknown.

**Revisit a recommendation** when a cited upstream regression, license or
compatibility gap, independent matched result, or simpler architecture meeting
the same requirements changes the evidence. Preserve this dated record when
superseding it. Recommendations, observed upstream quality and runtime
qualification remain separate fields.


## Amendment (2026-10-07): proposed status and source provenance

**Status:** proposed source-review recommendation record; not an accepted host
memory-owner decision.

The current title and interpretation are **Memory and RAG: proposed source-review
architecture recommendations**. The preceding decided text and original
[review observations](../../evidence/artifacts/memory-rag-stacks-20261007/review.json)
are preserved. This dated amendment qualifies how their recommendation wording,
including "final," "use," and "wins," is consumed; it does not turn the recorded
observations into new runtime results.

**Recommendation:** consider the five architectures as proposed stacks for their
named workloads. These are proposed architectures from a completed bounded
source review. Their source-review rationale and hypothetical component roles
are captured in the [current catalog](../../catalogs/foundation/memory-rag-stacks-20261007.json),
with `recommendation_status = proposed_source_review`. This record supplies
inputs to MEMORY-SCREEN. It preselects no memory-h2h winner, replaces no
independently owned measurement, and selects no memory owner for this host.

The [October 6 upstream-evidence rule](2026-10-06-upstream-evidence-over-local-evaluation.md)
at `79619936926576576e5d011eec19e3790e55f457` remains the original review's
accurate policy citation. The later, separately directed memory screen and
head-to-head consume this source-review input; this amendment does not assert
that the superseded general selection gates are current. It queues or resumes
no experiment and changes no installed selection. The five proposed workload
profiles and all 18 repository identities, conditional dispositions and inspected
pins remain. A separately owned memory-h2h result is an explicit possible
reason to overturn a proposal, alongside the original upstream regression,
compatibility, independent matched-result and simpler-architecture conditions.
That comparison and any host-owner decision belong to their own records.

### Review-scoped execution states and test actor

The [new qualification record](../../evidence/artifacts/memory-rag-stacks-20261007-followup/source-qualification.json)
separately records `installation = not_performed_in_this_review`,
`client_smoke = not_performed_in_this_review`, and
`organic_use = not_observed_in_this_review`. These describe this bounded source
review, not whether a component was exercised in another unit.

The original references to tested stores, SDK checks and "directly tested"
evaluation integrations refer to the upstream CI observed by the original
review at its named revisions. In particular, Opik is proposed for traces,
datasets and upstream-tested evaluation integrations; none was executed in this
review. Its recorded failing integrations remain limitations. Installation,
native-client smoke, organic observation and complete-stack execution remain
unperformed here. A schema, reference or hash check is structural validation,
not runtime acceptance; whole-task provider usage and net token savings remain
unknown.

### Newly dated PageIndex benchmark source check

The earlier separate benchmark revision remains unrecovered in the explicitly
checked retained materials. Its historical mutable locator and recorded
observations are unchanged; no revision is backfilled into the old review.
A new primary check on 2026-10-07 read
[VectifyAI/PageIndex-OSS-Benchmark@ad4c0b92970a6f4801f09ff2e647389e8f5874fa:README.md](https://github.com/VectifyAI/PageIndex-OSS-Benchmark/blob/ad4c0b92970a6f4801f09ff2e647389e8f5874fa/README.md#L6-L15)
at 2026-10-07T12:10:27Z. The checked README is 4,448 bytes, sha256
`2e8ec68a46b5b5f44e12d8cc1b214e888a71c9fc134c3483902fcb15c755d187`.
The maintainer describes 62 questions over 34 PDFs, scoped to running-text facts,
excluding charts, tables, figures, counting and arithmetic, and excluding
documents the local indexing path refuses. These are newly inspected vendor
scope and ingest-selection claims, not independently validated dataset contents,
a new run or a ranking. The pinned README's inventory also
[lists the question and PDF counts](https://github.com/VectifyAI/PageIndex-OSS-Benchmark/blob/ad4c0b92970a6f4801f09ff2e647389e8f5874fa/README.md#L22-L23).

This source observation does not establish what the original review inspected.
A release tag for the benchmark was not checked, and compatibility with the
separately pinned PageIndex implementation at
`6d23caf416858f2ca136840305d1f479a86f6ef7` remains unverified. No comparative
superiority, current-model performance, installation or native-client capture
claim follows from this check.

### Direct inspected component pins

These immutable file locators make the original 18 component pins directly
available from the decision record. They are source-review pins, not accepted
deployment locks or a claim that the listed workflows passed at those revisions.
The original review retains its release-versus-branch distinction, observed CI
failures and methodological limits.

| Repository | Original inspected commit | Immutable source locator |
| --- | --- | --- |
| vectorize-io/hindsight | `9269b88417ed263e5a8350f2e416ca2b322756b1` | [.github/workflows/test.yml](https://github.com/vectorize-io/hindsight/blob/9269b88417ed263e5a8350f2e416ca2b322756b1/.github/workflows/test.yml) |
| docling-project/docling | `4d4f6f7d123d221195fb64775c796c4de1f81c3b` | [.github/workflows/checks.yml](https://github.com/docling-project/docling/blob/4d4f6f7d123d221195fb64775c796c4de1f81c3b/.github/workflows/checks.yml) |
| deepset-ai/haystack | `234fc68f9c7bb7c156a5495f89b72d7aa27a907e` | [.github/workflows/tests.yml](https://github.com/deepset-ai/haystack/blob/234fc68f9c7bb7c156a5495f89b72d7aa27a907e/.github/workflows/tests.yml) |
| qdrant/qdrant | `016542aa5deb6c66380bb137badf73d54f742bde` | [.github/workflows/integration-tests.yml](https://github.com/qdrant/qdrant/blob/016542aa5deb6c66380bb137badf73d54f742bde/.github/workflows/integration-tests.yml) |
| comet-ml/opik | `f217a863ea3cbfcef7f9ab8217c543049bdff095` | [.github/workflows/lib-haystack-tests.yml](https://github.com/comet-ml/opik/blob/f217a863ea3cbfcef7f9ab8217c543049bdff095/.github/workflows/lib-haystack-tests.yml) |
| akitaonrails/ai-memory | `89bd8ded3c1ab8b769cf99417d038ed0364403c8` | [docs/ARCHITECTURE.md](https://github.com/akitaonrails/ai-memory/blob/89bd8ded3c1ab8b769cf99417d038ed0364403c8/docs/ARCHITECTURE.md) |
| DeusData/codebase-memory-mcp | `e71f23ecf40e473a3e0a49cff1ffebcccead384d` | [.github/workflows/_test.yml](https://github.com/DeusData/codebase-memory-mcp/blob/e71f23ecf40e473a3e0a49cff1ffebcccead384d/.github/workflows/_test.yml) |
| giancarloerra/SocratiCode | `1e829bf7ddf1e34c4cc6713227f00422cee791cc` | [.github/workflows/ci.yml](https://github.com/giancarloerra/SocratiCode/blob/1e829bf7ddf1e34c4cc6713227f00422cee791cc/.github/workflows/ci.yml) |
| mem0ai/mem0 | `c93420c49a6b14c3d446bdb156d96811908fd90a` | [README.md](https://github.com/mem0ai/mem0/blob/c93420c49a6b14c3d446bdb156d96811908fd90a/README.md) |
| infiniflow/ragflow | `cc72ecb0af18ade5d58f84d107af7cd59a88c39f` | [.github/workflows/sep-tests.yml](https://github.com/infiniflow/ragflow/blob/cc72ecb0af18ade5d58f84d107af7cd59a88c39f/.github/workflows/sep-tests.yml) |
| onyx-dot-app/onyx | `68dd959648704e0000b7bb070a699355bac11733` | [README.md](https://github.com/onyx-dot-app/onyx/blob/68dd959648704e0000b7bb070a699355bac11733/README.md) |
| VectifyAI/PageIndex | `6d23caf416858f2ca136840305d1f479a86f6ef7` | [.github/workflows/tests.yml](https://github.com/VectifyAI/PageIndex/blob/6d23caf416858f2ca136840305d1f479a86f6ef7/.github/workflows/tests.yml) |
| HKUDS/RAG-Anything | `8664e8b318a3ed651fe62dfcfddfb1f1d633d5be` | [.github/workflows/test.yaml](https://github.com/HKUDS/RAG-Anything/blob/8664e8b318a3ed651fe62dfcfddfb1f1d633d5be/.github/workflows/test.yaml) |
| volcengine/OpenViking | `87de989c5a18dc1f9fe2710cd60dbc48f1324527` | [README.md](https://github.com/volcengine/OpenViking/blob/87de989c5a18dc1f9fe2710cd60dbc48f1324527/README.md) |
| topoteretes/cognee | `b32d8afc59e1064d9291b9828a8a147be9cc8bab` | [README.md](https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/README.md) |
| rohitg00/agentmemory | `007a1a7fe8646a03d8652eb0712400cc6f0fcca3` | [benchmark/LONGMEMEVAL.md](https://github.com/rohitg00/agentmemory/blob/007a1a7fe8646a03d8652eb0712400cc6f0fcca3/benchmark/LONGMEMEVAL.md) |
| MemPalace/mempalace | `d439d1e6d01e2680d79fe3f5de5a336722cec779` | [benchmarks/BENCHMARKS.md](https://github.com/MemPalace/mempalace/blob/d439d1e6d01e2680d79fe3f5de5a336722cec779/benchmarks/BENCHMARKS.md) |
| supermemoryai/supermemory | `3535ff700da85134d1867e5eac1b649e8735e3af` | [apps/mcp/src/server/client/index.ts](https://github.com/supermemoryai/supermemory/blob/3535ff700da85134d1867e5eac1b649e8735e3af/apps/mcp/src/server/client/index.ts) |
