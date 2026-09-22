# Grand catalog handbook: foundation, runtimes and the north star

This is the portable selection and adoption handbook for the September 21, 2026
review baseline. Source checks and execution can cross into September 22 UTC;
their records retain exact timestamps. Start from a reviewed Git revision and
the [landscape manifest](../catalogs/landscape/manifest.json). A selection answers
the stated requirement with the available evidence. It is not a claim that a
repository wins every benchmark or that another PC is already configured.

Use the [offline explorer](ecosystem/index.html) for all current candidates,
alternatives, per-layer notes and evidence. Its counts are derived from the
canonical identity index; candidate-layer rows are not distinct repositories.
Public stars and awesome lists contribute discovery, not installation commands
or proof of quality. The complete list of every child link in every awesome list
has not been independently evaluated.

The current combined discovery index contains **843 repository identities**.
The selected manifest remains **68 versioned components**; shared skill selections
and SDK environments have their own linked practice records and locks. The
[independent Claude adjudication](claude-blind-adjudication-20260921.md) retains
the wider search, corrections and screening limits; the
[20-layer findings](blind-catalog-layer-findings-20260921.md) compare both sealed
source reports. The final Claude coverage critique and 159-row repair are now
[adjudicated with original decisions preserved](claude-blind-adjudication-20260921.md).
This closes the dated catalog review; matched quality and destination-host gates
remain explicit. Source-only candidates remain separate from qualified defaults.

The live Claude owner's [September 22 reconciliation](catalog-reconciliation-20260922.md)
identified nine ambiguous summary labels. All 20 displayed dispositions now
mirror the canonical layer decisions, with an automated consistency check.
No candidate disposition or selected version changed; historical reviewer
claims and their qualifications remain linked.

The [September 22 comparison progress](comparison-progress-20260922.md) records
the subsequent worker, retrieval, memory and parity results, including failed
judgments and the repaired publication check. The comparisons remain unresolved
or blocked; no selection changed. Joint setup readiness is still pending, and
the destination WSL host must supply its own acceptance after connection.

## What qualifies a selection

Evaluate repository quality against the task before investing in installation:

1. **Capability:** read the relevant implementation, documented interfaces and
   limitations at a source pin. Separate an advertised feature from our use of it.
2. **Evidence:** prefer relevant upstream tests/examples and actual returned
   behavior; distinguish those from our fixtures, integration tests and reviews.
3. **Maintenance and provenance:** inspect source/release history, dependency
   declarations and version compatibility. Recent activity and star counts do
   not establish maintainability or superiority by themselves.
4. **License and deployment fit:** record the declared license, required services,
   provider/account boundaries and platform assumptions. A license label is not
   a legal or complete dependency audit.
5. **Lifecycle and portability:** establish installation scope, useful operation,
   state ownership, restart, export/restore and rollback as required by the task.
6. **Quality and cost:** compare useful answers/results, omissions and failure
   handling on the same frozen workload; count ingestion, indexing, query,
   maintenance and failed attempts. Mark unmeasured cost or quality unknown.

The [candidate quality review](candidate-quality-review-20260921.md) records the
current focused source checks. It does not assign invented aggregate scores.
Native reviewer agreement is advisory: the coordinator checks each finding
against original sources and actual results. See the
[runtime review record](../blueprints/catalog-runtime-review/README.md) and the
[acceptance evidence policy](acceptance-evidence-policy.md).

Use these dispositions consistently:

| Disposition | Meaning |
| --- | --- |
| Selected | Supported choice for the named requirement and evidence scope |
| Conditional | Credible candidate when its stated requirement is present |
| Unqualified | Required local behavior or comparison has not been established |
| Overlap / out of scope | Does not close the current gap; no failure implied |
| Measured tradeoff | Retained observations include advantages and disadvantages |
| Observed failure | A named operation actually failed on recorded inputs/runtime |

## Foundation selection by layer

The [current foundation comparisons](../catalogs/landscape/foundation.json)
contain the exact alternatives, sources, limits and conditions for replacing
each choice. The manifest owns versions and installation recipes; this table
does not create a second package lock.

| Layer | Selected direction | Next meaningful acceptance |
| --- | --- | --- |
| Native clients | Codex and Claude Code; MCPorter for selected native tool access | Native sign-in, discovery, useful task and continuation per client |
| Skills | Selected ECC, Agent Skills reference, TypeSafe and OpenAI skills | Relevant task use with source pins and explicit worker context |
| Workers | Native workers and Worktrunk | Owned writing worktrees, integration and independent evidence review |
| Isolation | Worktrees for ownership; sandbox-runtime for selected access restrictions | Exercise the required restriction; worktrees do not enforce it |
| Code navigation | Serena, ast-grep, codebase-memory-mcp, jCodeMunch | Exact source retrieval and original-code confirmation |
| Documents | QMD, Context Hub, MarkItDown, Poppler | Corpus/format-specific retrieval and conversion checks |
| Semantic code search | SocratiCode, Qdrant, vLLM, Hugging Face Hub | Hardware-compatible embeddings, scoped indexing and real watcher/retrieval |
| Durable memory | ai-memory | Scoped cross-client recall, capture and restore; quality comparison remains open |
| Web research | agent-browser, Playwright CLI, Tavily CLI, OpenResearch | Actual source acquisition, attribution and task-specific completeness |
| Context and usage | RTK, Context Mode, Repomix, ccusage | Recoverable originals and matching usage categories; no blanket savings claim |
| Evaluation | Playwright, Promptfoo, ShellCheck, Difftastic, MCP Inspector | Meaningful behavior checks; source validation is not model-quality evidence |
| CI and provenance | actionlint, zizmor, Gitleaks, Syft, Dependabot, attestations | Actual scoped runs; inventory is not a vulnerability verdict |
| Scheduling | Dagu and systemd | Required failure/cancellation/restart behavior and effect ownership |
| Application services | Next.js, React, FastAPI, PostgreSQL | Reproduce the scoped application; production hosting is separate |
| Portability | uv, Restic and native backup/resume | Empty-target install/restore, logical checks and native consumer use |
| Observation | OTel, Prometheus, Loki, Grafana, Alertmanager, ntfy and selected agent viewers | Actual task/event delivery and recovery on the destination host |

Optional container platforms, cloud providers, inference gateways and alternative
orchestrators are not a universal startup bundle. Select them through the
[hosting comparison](hosting-container-practice.md) and their per-layer decisions.
This handbook does not start services, create schedules or select paid hosting.

## Runtime workers and research applications

The exercised programmatic research worker uses the **Codex Python SDK**
(`openai-codex`), explicitly selecting the native Codex binary. This is distinct
from **OpenAI Agents SDK** and **Claude Agent SDK**, which remain application
runtime candidates. The locked environment includes `openai-codex`, `openai`,
`alpaca-py`, `duckdb` and `exchange-calendars` with 36 transitive distributions.
Use the [SDK lock and native uv recipe](../adoption/sdk/README.md).

Native Claude workers/workflows and a retained Codex-analysis to Claude-review
pair complement that worker. The pair has completed; an earlier allowance-blocked
receipt is historical. Neither agreement nor a completed model response proves
the underlying source claim. The observed pair also shared a cutoff
overgeneralization that coordinator review corrected.

**DeerFlow is already exercised within a narrow boundary.** One unmodified,
pinned embedded `invoke_acp_agent` call used Codex ACP to review two existing
receipts. This did not qualify its full planner, web-research pipeline, UI,
persistent service, integrated RAG or recovery. The tested adapter's `read-only`
label mapped to `workspaceWrite/on-request`; observed read behavior does not
establish enforced read-only access. See the
[DeerFlow receipt](../blueprints/us-equities/deerflow/research-receipt.json).

| Requirement | Candidate escalation | Comparison needed before promotion |
| --- | --- | --- |
| Application-owned long-running agent state | Deep Agents / LangGraph | Same research task, source quality, checkpoint/interruption behavior and total usage |
| Native agent control across remote environments | OpenHands SDK / Agent Canvas | Actual ownership, isolation, cancellation and artifact recovery |
| Programmatic application integration | OpenAI Agents SDK / Claude Agent SDK / Microsoft Agent Framework | Required API/tools/events and lifecycle against the native baseline |
| Multi-host durable effects and long waits | Temporal / Restate | Host loss, retries, duplicate external effects and recovery |
| Python research flows or data assets | Prefect / Dagster | Real pipeline scheduling, lineage, backfills and operating burden |
| Specialized financial research assistant | Dexter and other domain research candidates | Source-grounded answers and point-in-time data boundaries; no execution inference |

Use one coordinator and bounded independent workers. Writers own separate
worktrees; the coordinator integrates. Supply each worker its requirement,
revision, paths, relevant skill context, output contract and stop condition.
Preserve requested and returned model/effort separately; record unavailable
metadata as unknown. Preserve native sign-ins, and never copy authentication
stores. A filesystem sandbox alone does not remove inherited remote-tool access.

## Memory selection and the strongest relevant challengers

ai-memory remains the shared project-memory choice because scoped native
Codex/Claude use, bounded outcome capture, native Codex task consolidation and
isolated restoration have actual evidence. ai-memory's own internal LLM
consolidation was disabled in that test. The 52 restored pages comprised **one ordinary decision
and 51 System pages**, so that test does not represent a large project corpus.
Captured excerpts are bounded observations, not complete native transcripts.

The priority comparison is ai-memory versus **Hindsight and Basic Memory** on
representative project decisions, superseded facts, failed approaches, exact
citations, no-answer cases and cross-project isolation. Use the same downstream
model/context budget, independent frozen answers, repeated runs and complete
ingestion/query/maintenance usage. Include deletion and empty-target restoration.
There is no completed matched quality/cost comparison yet.

A later [tiny lexical lifecycle comparison](../blueprints/memory-lifecycle-probe/README.md)
passed 28 content checks for ai-memory and Basic Memory: writes, reads, updates
and current-search deletion, plus ai-memory restart/backup and Basic Memory
text-index rebuild. Its first ai-memory attempt failed a no-model-download
constraint; the corrected run explicitly disabled embeddings. Unequal recovery
checks and this three-note fixture do not settle semantic recall or justify a
memory-store migration. The failed attempt and public provenance are retained.

Graphiti, Cognee and OpenViking are credible for temporal/relationship or broader
research-context requirements. Mem0 and Supermemory may fit application memory;
Letta Code changes the worker/runtime architecture. Claude-mem is an alternative
capture/retrieval stack. Current local or multi-client support must be reviewed
before using an old cloud-only or Claude-only exclusion. Compare stores in
isolated test scopes; do not silently add competing authoritative capture paths.

## Clean adoption on a new WSL PC

Follow [adoption/README.md](../adoption/README.md) and
[adoption/lifecycle.md](../adoption/lifecycle.md). The initial target is
Linux/WSL2 x86_64. Before selecting GPU or platform-specific tools, inspect the
destination's CPU, RAM, GPU, storage, Windows/WSL and Linux versions.

| Order | Profile / action | Destination acceptance |
| --- | --- | --- |
| 1 | Reviewed checkout and portable validators | Exact revision, intact source references/hashes and explicit installation paths |
| 2 | `foundation-cpu` | Native Codex/Claude sign-in, selected plugin/tool discovery, useful QMD/context call and scoped memory retrieval |
| 3 | Shared skills and workers | One bounded source/build/review task, owned changes and useful returned results |
| 4 | `research-runtime` | Recreate the SDK lock in a new prefix, dependency/import checks and retained research fixture |
| 5 | `observability` and `recovery` when selected | Real task/event delivery and isolated logical restore, then consumer verification |
| 6 | `semantic-rag` when hardware fits | Actual inference, scoped index/watch queries and recovered state |
| 7 | `trading-nautilus` | Engine replay and comparison; each broker's operation remains separately qualified |

The prerequisite report only detects executables/platform requirements. A clean
prefix on the existing host proves that prefix's reproducibility, not a fresh
WSL distribution, second physical PC, GPU stack, credentials or all services.
The recreated SDK environment does not install `context-mode`, `ai-memory` or
`mcporter`, or qualify the other `foundation-cpu` components.
Use the [clean-install review](../blueprints/catalog-clean-install/README.md) for
the actual checks and remaining destination requirements.

Do not synchronize a lock into the system/shared environment: native exact sync
can remove packages outside that lock. Use reviewed native upstream installers
and explicit package/source pins. Resolve template placeholders and register
selected tools through each client's supported interface. Keep Desktop,
native Linux Codex and native Linux Claude account/configuration scopes separate.

## Foundation to the north star

The four domain layers reuse this foundation: memory/retrieval, research workers
and operations, market data/filings, then simulation/execution. Current choices
are in the [domain comparisons](../catalogs/landscape/us-equities.json).

| Domain layer | Selected direction | Remaining decision or acceptance |
| --- | --- | --- |
| Research memory and retrieval | ai-memory; QMD; Serena; SocratiCode/Qdrant; task-selected Context Mode/RTK | Representative financial/source recall comparison and project isolation |
| Research workers and operations | Native Codex/Claude; Dagu/systemd; OTel with Prometheus/Loki/Grafana; scoped sandboxing and Restic | Destination worker ownership, event delivery, cancellation and recovery |
| Market data and filings | Official alpaca-py; EdgarTools; DuckDB/Parquet; exchange_calendars | Required universe, rights, corporate actions and information-availability evidence; Databento remains conditional |
| Simulation and broker execution | NautilusTrader destination; LEAN historical comparison; native IBKR and separate alpaca-py paper path | Engine parity and independent broker-specific reconciliation/risk/reconnect acceptance |

NautilusTrader 2.0.0rc5 remains the selected destination; LEAN retains useful
comparison evidence. The historical SDK/LEAN adoption profile does not override
that destination. A bounded engine replay or paper roundtrip does not establish
point-in-time universe quality, complete broker recovery or a winning strategy.
Use [runtime-target.json](../catalogs/us-equities/runtime-target.json) and the
latest linked evidence; older contracts' unimplemented lists can be historical.

## How future sessions continue

Use the [independent discovery and cooperation practice](blind-catalog-convergence-20260921.md)
when reopening a selection. Preserve reports before exposing incumbent rankings,
adjudicate differences with original sources and record unresolved comparisons.
The [live Claude repository report](claude-repository-evidence.md) and
[portable workflow practice](ultracode-token-routing-20260921.md) carry their
own command, host, model and qualification limits into this handbook.

Read this handbook, the [research queue](../catalogs/landscape/research-state.json)
and only the selected layer's evidence. Record the checkout revision, host,
requirement, current result, failed attempts and next decision-changing check.
Reopen on a demonstrated gap, changed requirements, relevant upstream behavior
or a challenger result. New releases and reviewer votes alone do not promote a
candidate. Preserve historical records with their dates and superseding links.

The catalog can be a complete handbook for its declared review set while
comparative quality remains open. New-host acceptance is recorded on that host;
neither a cloned receipt nor this HTML page certifies it.

<!-- verdicts:begin -->
## Per-layer verdicts (generated)

Joins the landscape ledger's layer-verdict schema v2 rows with the dated SOTA-convergence manifest's per-layer components/entries and adoption/manifest.json's recipe_map. Every row currently pending_lanes was carried over unchanged; this generator does not itself run a lane, select a winner or claim an execution result.

### foundation

| Layer | Group | Verdict status | Winner(s) + pin | Evidence class | Alternatives | Overturn when | Recipe anchor | Platform status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agent-sdks | - | pending | - | - | 0 | A concrete application needs durable multi-host state/replay (Temporal), explicit graph checkpoints (LangGraph), a remo… | - | - |
| ci-supply-chain | - | pending | - | - | 0 | A specific dependency/update or vulnerability gap is demonstrated and one alternative covers it with pinned database/pr… | - | - |
| code-navigation | - | pending | - | - | 0 | A sealed task set in the target languages shows a challenger returning more correct source/references at an acceptable … | - | - |
| document-retrieval | - | pending | - | - | 0 | A sealed representative corpus/query set shows useful quality gains with acceptable repeated end-to-end latency, or lay… | - | - |
| durable-memory | - | pending | - | - | 0 | An isolated representative corpus and question set shows better source-grounded recall/usefulness and acceptable comple… | - | - |
| git-github-automation | - | pending | - | - | 0 | A concrete cross-repository or multi-host Git/GitHub workflow needs capabilities beyond gh/worktrunk/difftastic, and a … | - | - |
| hosting-services | - | pending | - | - | 0 | A defined production, remote-team or GPU deployment requirement exceeds the local fixture, and one alternative passes i… | - | - |
| instructions-skills | - | pending | - | - | 0 | A specific task exposes a missing procedure, and a pinned candidate works in native discovery and task execution with l… | - | - |
| isolation | - | pending | - | - | 0 | Untrusted code or a deployment target requires a stronger VM/OCI boundary, and the selected alternative passes workload… | - | - |
| mcp-surfaces | - | pending | - | - | 0 | A concrete MCP surface gap needs a new server, and a reviewed registry entry passes the same bridge/inspection acceptan… | - | - |
| native-clients | - | pending | - | - | 0 | A required structured-event, custom-tool or application state capability is unavailable through the native path and a s… | - | - |
| observation-inference | - | pending | - | - | 0 | A required trace, evaluation or supported model/hardware workload is unanswerable by the current path, and one alternat… | - | - |
| quality-evaluation | - | pending | - | - | 0 | A defined tool-use/extraction or experiment-tracking requirement cannot be expressed adequately in the current test lan… | - | - |
| recovery-portability | - | pending | - | - | 0 | A real multi-language/system dependency or state-loss case exceeds the selected recipes, and the proposed environment/b… | - | - |
| scheduling-supervision | - | pending | - | - | 0 | Real jobs require host-loss survival, days-long waits or durable cross-host effects, and one challenger passes the decl… | - | - |
| secrets-credentials | - | pending | - | - | 0 | A concrete multi-host or multi-operator secret-sharing need appears, and openbao (or a comparable secret manager) passe… | - | - |
| semantic-rag | - | pending | - | - | 0 | A sealed project/domain retrieval set shows improved source-grounded quality and acceptable latency, memory and lifecyc… | - | - |
| token-efficiency | - | pending | - | - | 0 | A frozen task/artifact and repeated controlled comparison improves answer correctness or retrieval completeness while r… | - | - |
| web-research | - | pending | - | - | 0 | A defined source-coverage or ingestion task exceeds the current commands and a candidate improves attributable retrieva… | - | - |
| workers | - | pending | - | - | 0 | A real task needs durable multi-host state, approval waits or effect recovery beyond native workers, and one challenger… | - | - |

### foundation (per-layer narrative)

- **Agent SDKs and runtime workers** (agent-sdks): pending — no lane has run

- **CI and supply chain** (ci-supply-chain): pending — no lane has run

- **Code navigation** (code-navigation): pending — no lane has run

- **Documents and ingestion** (document-retrieval): pending — no lane has run

- **Durable memory** (durable-memory): pending — no lane has run

- **Git practice and GitHub automation** (git-github-automation): pending — no lane has run

- **Application and service hosting** (hosting-services): pending — no lane has run

- **Instructions and skills** (instructions-skills): pending — no lane has run

- **Isolation** (isolation): pending — no lane has run

- **MCP servers and client surfaces** (mcp-surfaces): pending — no lane has run

- **Native clients** (native-clients): pending — no lane has run

- **Observation and optional inference** (observation-inference): pending — no lane has run

- **Quality and evaluation** (quality-evaluation): pending — no lane has run

- **Recovery and portability** (recovery-portability): pending — no lane has run

- **Scheduling and supervision** (scheduling-supervision): pending — no lane has run

- **Secrets and credentials** (secrets-credentials): pending — no lane has run

- **Semantic code retrieval** (semantic-rag): pending — no lane has run

- **Context and usage efficiency** (token-efficiency): pending — no lane has run

- **Web research** (web-research): pending — no lane has run

- **Workers and task ownership** (workers): pending — no lane has run


### us-equities

| Layer | Group | Verdict status | Winner(s) + pin | Evidence class | Alternatives | Overturn when | Recipe anchor | Platform status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agents-models-workers | foundation-memory | pending | - | - | 0 | Run a preregistered, representative held-out financial/document and code retrieval set at the same context budget; repl… | - | - |
| backtesting-engine | engines-strategies | pending | - | - | 0 | Reopen the implementation choice if Nautilus cannot preserve a required cash/order semantic, fails a preregistered SPY/… | - | - |
| data-quality-orchestration | agents-operations | pending | - | - | 0 | Escalate to another scheduler, graph or host only when a specified long-running workflow, host-loss recovery, asset/bac… | - | - |
| evaluation-experiments | agents-operations | pending | - | - | 0 | Escalate to another scheduler, graph or host only when a specified long-running workflow, host-loss recovery, asset/bac… | - | - |
| execution-broker | engines-strategies | pending | - | - | 0 | Reopen the implementation choice if Nautilus cannot preserve a required cash/order semantic, fails a preregistered SPY/… | - | - |
| identity-provenance | data-research | pending | - | - | 0 | Freeze required universe/history/latency, rights, correction and availability semantics; compare selected providers on … | - | - |
| market-data-reference | data-research | pending | - | - | 0 | Freeze required universe/history/latency, rights, correction and availability semantics; compare selected providers on … | - | - |
| observability-hosting | agents-operations | pending | - | - | 0 | Escalate to another scheduler, graph or host only when a specified long-running workflow, host-loss recovery, asset/bac… | - | - |
| portfolio-risk | engines-strategies | pending | - | - | 0 | Reopen the implementation choice if Nautilus cannot preserve a required cash/order semantic, fails a preregistered SPY/… | - | - |
| research-factors-ml | engines-strategies | pending | - | - | 0 | Reopen the implementation choice if Nautilus cannot preserve a required cash/order semantic, fails a preregistered SPY/… | - | - |
| security-supply-chain | agents-operations | pending | - | - | 0 | Escalate to another scheduler, graph or host only when a specified long-running workflow, host-loss recovery, asset/bac… | - | - |
| storage-compute | data-research | pending | - | - | 0 | Freeze required universe/history/latency, rights, correction and availability semantics; compare selected providers on … | - | - |

### us-equities (per-layer narrative)

- **Agents, models and workers** (agents-models-workers): pending — no lane has run

- **Backtesting engine** (backtesting-engine): pending — no lane has run

- **Data quality and orchestration** (data-quality-orchestration): pending — no lane has run

- **Evaluation and experiments** (evaluation-experiments): pending — no lane has run

- **Execution and broker adapters** (execution-broker): pending — no lane has run

- **Identity, provenance and lineage** (identity-provenance): pending — no lane has run

- **Market data and reference** (market-data-reference): pending — no lane has run

- **Observability and hosting** (observability-hosting): pending — no lane has run

- **Portfolio and risk** (portfolio-risk): pending — no lane has run

- **Research, factors and ML** (research-factors-ml): pending — no lane has run

- **Security and supply chain** (security-supply-chain): pending — no lane has run

- **Storage and compute** (storage-compute): pending — no lane has run
<!-- verdicts:end -->
