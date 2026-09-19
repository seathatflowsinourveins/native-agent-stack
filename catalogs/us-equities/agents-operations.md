# Agents and operations for the US-equities research stack

Checked **2026-09-19**. This is a curated architecture decision record covering **35 upstream repositories**, not a claim that installing them creates an automated trading system. The [machine-readable catalog](agents-operations.json) contains release dates, license scope, requirements, primary sources and proposed native commands for every entry. The repository's [US-equities blueprint](../../blueprints/us-equities/README.md) records what actually ran.

The useful baseline is the existing native Codex worker, deterministic data/backtest code, an explicit artifact contract, and the existing command sandbox and secret scanner. Add a scheduler when work must recur or resume, dependency evidence before publishing runtime artifacts, and telemetry when services become persistent. Choose an alternative when it solves a concrete problem; running several agent frameworks, gateways, schedulers or trace databases together is not a completeness criterion.

## Evidence and version conventions

`default` means the preferred design or adoption lane; it does **not** mean installed. `conditional` requires the stated trigger, `alternative` replaces an overlapping choice, and `watch` lacks a reason or readiness level for adoption now. `native_proven` means only the bounded behavior in the cited local receipt. It can mean a health request or protocol discovery; it never upgrades itself into an inference, trading or production-availability claim. Other entries are source reviews, not local acceptance results.

Commands in the JSON were initially prospective; the linked gap-resolution receipts now establish the specific executed DeerFlow and Dagu workflows. Release inspection, imports and `--help` are deliberately labeled discovery/smoke checks. Application paths such as `$REVIEWED_RESEARCH_DAG` and `$SERVE_APP_IMPORT_PATH` require separately reviewed application code; this catalog supplies neither hidden jobs nor an all-tools installer. Select a dedicated environment or installation prefix, verify the chosen release asset's published digest/signature, retain its license, and then perform one useful scoped acceptance before promoting it. The initial source research did not perform runtime acceptance; subsequent native acceptance is recorded separately below.

The release field identifies a dated upstream release or package, not a leaderboard rank. GitHub “latest” can refer to a monorepo SDK rather than its core package. Package uploads, release dates, development commits and locally working versions remain distinct:

- Codex CLI **0.155.1** and Python SDK **0.154.0** are separate. The SDK normally selects its packaged runtime; the existing worker deliberately selects the native executable. [Official SDK documentation](https://developers.openai.com/codex/sdk)
- Codex ACP is **agentclientprotocol/codex-acp 1.12.0**. The old Zed repository directs new installations there. [Upstream migration notice](https://github.com/zed-industries/codex-acp)
- DeerFlow stable is **v2.0.0**; local discovery used commit **42334f26d7025d905678f9075b079fc65f9beaf9**, whose backend reports **2.1.0-rc0**. Newer development integration examples must not be attributed to the stable release. [Discovery receipt](../../blueprints/us-equities/deerflow/native-receipt.json)
- LangGraph core **1.2.11** differs from the repository's latest **sdk==0.4.4** release. [Core package](https://pypi.org/project/langgraph/1.2.11/)
- vLLM upstream **0.29.0** installed successfully but failed GPU startup with `UVA is not available` on the recorded WSL host. **0.25.0** was restored and retrieval passed. It is the working compatibility pin, not the newest release. [Compatibility receipt](../../evidence/receipts/vllm-compatibility.json)
- SGLang **0.5.20** documents CUDA 13 for the current NVIDIA lane; **0.5.19** was the last CUDA 12 release. A version bump alone is insufficient hardware validation. [Installation contract](https://docs.sglang.io/docs/get-started/install)
- Daytona's public core stopped receiving updates after development moved private in June 2026. Public server **0.190.0** and current Python SDK **0.214.0** are different artifacts. The former is AGPL-3.0, the latter Apache-2.0; do not describe the old public server as a freshly maintained self-host default. [Current notice](https://github.com/daytonaio/daytona/blob/ec4c21b2d597091ac09ecc278f3bcc172575a987/README.md)

## The worker boundary comes before an orchestrator

A research job should carry an immutable input manifest: symbols, source identifiers, as-of time, filing/data revision, timezone/calendar, units, code revision, model identity, result schema, owner and deadline. The worker returns a source-linked artifact plus uncertainty, terminal status and available usage. Deterministic code validates arithmetic and data consistency. Retrieved filings, web text and stored agent memories are evidence, not permission to execute tools.

The existing [native SDK receipt](../../blueprints/us-equities/workers/receipt.json) establishes a completed Astra research task and actual tool use after normal native login. It also retains failed Context Mode file-extraction and approval attempts. The native plugin's workspace attribution remains a real limitation for ephemeral SDK file tools; successful project-independent tool calls do not prove that all native plugins work in an SDK session. Keep account readiness, tool discovery, permission policy, workspace scope and actual task behavior as separate checks.

Use native Codex for the current worker. Add ACP only for a host that speaks ACP. DeerFlow now has one completed native ACP research task; it remains an optional embedded research lane, without an accepted durable application service. LangGraph is useful for explicit branching/checkpoints when a simple task becomes insufficient. OpenAI Agents SDK and Claude Agent SDK are alternatives for application-owned loops, each with its own authentication, tool and tracing semantics. They are not interchangeable paths to the user's native subscription. Claude's current documentation specifically limits offering third-party products using claude.ai login/rate limits without prior approval. [Claude SDK authentication scope](https://code.claude.com/docs/en/agent-sdk/overview)

The future broker execution service needs a separate identity, durable intent ledger, deterministic preflight, deduplication, reconciliation and explicit activation policy. These are **requirements, not implemented capabilities in this catalog**. Research workers receive neither broker secrets nor order-capable MCP tools. A filesystem sandbox, a model's refusal instruction, or a scheduler's retry setting is insufficient to establish that boundary. None of the 35 operations components is itself a complete Alpaca execution adapter.

## Choose one scheduling path

| Trigger | Preferred candidate | Why it earns its operational cost |
| --- | --- | --- |
| Single host, existing shell/Python jobs, simple schedules | Dagu | One native binary can run reviewed DAGs around existing commands. No new model layer is required. |
| Python flows and operational task visibility dominate | Prefect instead of Dagu | Native Python task/flow lifecycle and deployment controls. |
| Dataset partitions, lineage and historical backfills dominate | Dagster instead of a generic job scheduler | Assets and partitions describe research data dependencies directly. |
| Jobs span days, wait for approval, or must recover across host failure | Temporal | Durable history and replay, with explicit activity boundaries and a production persistence obligation. |
| Within-task agent branching or review/resume | LangGraph, only if needed | Persistent graph checkpoints complement a scheduler; they do not replace job or broker ledgers. |

Temporal activities retry by default, with potentially unlimited attempts. Bound retries and classify authentication/quota failures as nonretryable until external state changes. Network/LLM effects belong in activities, while workflow code must remain replayable. Exactly-once application outcomes still require effect-specific idempotency and reconciliation. [Temporal retry semantics](https://docs.temporal.io/encyclopedia/retry-policies)

Likewise, LangGraph's in-memory checkpointer loses state on restart. Persisted checkpoints preserve graph state but do not make a broker write safe to repeat. [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

Do not schedule the native account simply because a previous allowance check passed. Check at dispatch, stop repeated unchanged quota failures, and record all failed attempts. A local concurrency limit controls processes; it does not enforce an account-wide token allowance. A process deadline does not prove upstream cancellation or cap already-incurred inference usage.

## Routing fidelity and cost accounting

OmniRoute **3.8.50** remains the latest verified release; its default development branch is different. It documents native `/v1/responses`, explicit thinking passthrough and optional `sessionAffinityTtlMs`. Treat those as individual protocol features, not complete native Codex equivalence. The [routing recipe](../../blueprints/us-equities/routing/README.md) distinguishes historical exact Opus/local Qwen calls, fresh anonymous health checks and the **unverified gateway Astra route**. FreeLLMAPI **0.11.0** is an alternative local routing profile; Claude-looking aliases may resolve to local Qwen. Neither an advertised model list nor HTTP 200 establishes exact-model account entitlement.

Keep response caching, lossy compression and injected gateway memory/skills off for the initial fidelity baseline. Preserve model identity, tool-call IDs, opaque reasoning items, source dates, numerical precision and provider usage. Do not stack both gateways in series. Native clients retain their own accounts and normal trust flow; the catalog does not copy OAuth stores or turn subscription access into a generic API credential.

Provider prefix caching, complete-response caching, retained artifact reduction and local context estimates are different measurements. Current official GPT-5.6-and-later caching uses `prompt_cache_options.ttl: "30m"` and charges cache writes. A gateway must be shown to preserve the specific fields; older `prompt_cache_retention` behavior is not equivalent. [Official caching contract](https://developers.openai.com/api/docs/guides/prompt-caching)

The OmniRoute Codex executor removes `max_output_tokens`, so that client field is not a spending ceiling on that backend. [Pinned executor source](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/open-sse/executors/codex.ts) Count actual input, cached reads, cache writes, output and reasoning according to each provider's schema: subset counters must not be added twice. Keep cumulative snapshots separate from per-attempt totals. Missing failure usage stays unknown or partial, never zero. A cache-hit share or artifact-size reduction is not paired net provider savings, and API-equivalent cost is not a subscription invoice.

## Hosting and isolation without a framework pile

Keep local services on loopback for the existing research setup. A dedicated Linux host with persistent storage and a process supervisor is a simpler next hosting step than an agent platform plus several orchestrators. Build evidence first: restore a stopped service, reject a stale input, cancel an owned job, and recover a durable job without duplicating effects. No production high-availability claim is established here.

Use the working vLLM deployment until a concrete model/hardware requirement favors SGLang. Ray Serve becomes useful for distributed capacity and composing separately scalable services; BentoML is an alternative packaging/deployment layer. Neither is necessary solely to expose one working model endpoint. Modal is conditional elastic cloud compute, with a separate account, bill and data-egress decision. E2B provides managed isolated code environments; its self-host path is a separate cloud-infrastructure project. OpenSandbox is a self-hosted Docker/Kubernetes control plane that requires deliberate operations. Daytona remains a watch item under the public-core maintenance limitation.

Reuse the current native sandbox for small scoped commands. Existing filesystem tests cover allowed writes, denied reads and a separately denied write; they do not certify network denial, VM isolation or every host secret. [Runtime evidence](../../evidence/receipts/runtime-tools.json) Give generated code only the selected input artifact, an owned output directory and necessary network access. Read-only local files do not disable remote mutations or remove inherited credentials.

## Observability, evaluations and release evidence

Start with typed job receipts, then an OpenTelemetry collector plus Prometheus when long-running services need monitoring. Add Grafana only when there is operational data to display. Record data age, job state, retry count, queue duration, actual provider usage availability and service health using bounded labels. Prompt text, raw tool payloads, account identifiers and credentials should not be default metric labels or exported trace fields. Redact before export and set retention. [OpenTelemetry data handling](https://opentelemetry.io/docs/security/handling-sensitive-data/)

Choose one initial trace/evaluation UI: Phoenix for local trace investigation, Langfuse for shared prompt/dataset operations, or MLflow where experiment/model artifacts are the main need. They have different licenses and infrastructure costs. Phoenix is Elastic-2.0; Langfuse has MIT core and separately licensed enterprise directories; Grafana is AGPL-3.0-only with component exceptions. Open-source clients do not imply free hosted services or unrestricted managed redistribution. Phoenix’s provider visibility setting hides UI/catalog choices; it does not itself deny backend inference. Keep the inspection environment free of provider credentials and apply access controls.

Use one small Inspect AI suite or Promptfoo configuration for frozen extraction/tool-policy regressions. Exact dates, units, citations, schema conformance and recovery behavior should have deterministic assertions before adding a judge model. Provider/LLM-judge evaluation requires a separate bounded run; none ran for this catalog. Trading outcomes require their own research protocol and execution validation, not an LLM quality score. OpenAI Agents SDK tracing and Promptfoo telemetry default to enabled upstream; the JSON proposes documented per-process opt-outs for initial local checks. [Agents tracing](https://openai.github.io/openai-agents-python/tracing/), [Promptfoo telemetry](https://www.promptfoo.dev/docs/configuration/telemetry/)

The most immediate publication gap is dependency evidence. Keep Gitleaks for redacted secret scans; add Syft for an artifact-scoped SBOM and Grype for a dated vulnerability result. Trivy is an alternative when IaC/container coverage is needed, not a mandatory duplicate scan. Cosign adds signature/producer verification where upstream publishes suitable material; pin both digest and expected identity. OpenBao becomes useful when several unattended services require scoped, rotated credentials. None of these tools independently proves a strategy safe, a package uncompromised, or a service authorized to trade.

## Catalog index

The following decisions refer to architecture selection, not installation status. Full commands and evidence limits are in the JSON.

| Component | Decision | Evidence | Purpose |
| --- | --- | --- | --- |
| [codex-native-sdk](https://github.com/openai/codex) | default | bounded native receipt | Native Codex CLI and Python app-server SDK |
| [codex-acp](https://github.com/agentclientprotocol/codex-acp) | conditional | bounded native receipt | ACP adapter to native Codex app-server |
| [omniroute](https://github.com/diegosouzapw/OmniRoute) | conditional | bounded native receipt | Optional explicit provider gateway |
| [freellmapi](https://github.com/tashfeenahmed/freellmapi) | alternative | bounded native receipt | Alternative local-provider and free-tier router |
| [deerflow](https://github.com/bytedance/deer-flow) | watch | bounded native receipt | Optional research application and subagent host |
| [langgraph](https://github.com/langchain-ai/langgraph) | conditional | source review | Explicit agent-state graph and checkpoints |
| [dagu](https://github.com/dagucloud/dagu) | conditional | bounded native receipt | Single-binary scheduler for existing native commands |
| [temporal](https://github.com/temporalio/temporal) | conditional | source review | Durable workflow history, activities and cancellation |
| [prefect](https://github.com/PrefectHQ/prefect) | alternative | source review | Python flow scheduling and operations |
| [dagster](https://github.com/dagster-io/dagster) | alternative | source review | Partitioned data assets, lineage and backfills |
| [vllm](https://github.com/vllm-project/vllm) | default | bounded native receipt | Existing local GPU serving runtime |
| [sglang](https://github.com/sgl-project/sglang) | alternative | source review | Alternative GPU serving engine with prefix caching |
| [ray-serve](https://github.com/ray-project/ray) | conditional | source review | Distributed compute and model-service composition |
| [bentoml](https://github.com/bentoml/BentoML) | alternative | source review | Model service packaging and deployment |
| [modal](https://github.com/modal-labs/modal-client) | conditional | source review | Managed elastic Python/GPU jobs and sandboxes |
| [e2b](https://github.com/e2b-dev/E2B) | conditional | source review | Managed isolated code execution environments |
| [daytona](https://github.com/daytonaio/daytona) | watch | source review | Managed development sandbox alternative |
| [opensandbox](https://github.com/opensandbox-group/OpenSandbox) | conditional | source review | Self-hostable sandbox control API and SDKs |
| [sandbox-runtime](https://github.com/anthropics/sandbox-runtime) | default | bounded native receipt | Native filesystem/network restriction for selected commands |
| [opentelemetry-collector](https://github.com/open-telemetry/opentelemetry-collector) | conditional | source review | Vendor-neutral telemetry collection and export |
| [prometheus](https://github.com/prometheus/prometheus) | conditional | source review | Metrics scraping, time-series retention and alert rules |
| [grafana](https://github.com/grafana/grafana) | conditional | source review | Operations dashboards and visualization |
| [langfuse](https://github.com/langfuse/langfuse) | alternative | source review | Shared LLM trace, prompt and evaluation platform |
| [phoenix](https://github.com/Arize-ai/phoenix) | conditional | source review | Local trace inspection and evaluation workspace |
| [inspect-ai](https://github.com/UKGovernmentBEIS/inspect_ai) | default | source review | Programmable task/solver/scorer evaluations |
| [promptfoo](https://github.com/promptfoo/promptfoo) | alternative | source review | Declarative prompt regression and adversarial testing |
| [gitleaks](https://github.com/gitleaks/gitleaks) | default | bounded native receipt | Redacted secret scanning of code and history |
| [syft](https://github.com/anchore/syft) | default | source review | Native artifact dependency inventory |
| [grype](https://github.com/anchore/grype) | default | source review | Scan a recorded SBOM against vulnerability data |
| [trivy](https://github.com/aquasecurity/trivy) | alternative | source review | Alternative integrated vulnerability/IaC/secret scanner |
| [cosign](https://github.com/sigstore/cosign) | conditional | source review | Artifact signature and identity verification |
| [openbao](https://github.com/openbao/openbao) | conditional | source review | Separate service identity and secret lifecycle |
| [openai-agents-sdk](https://github.com/openai/openai-agents-python) | alternative | source review | API-backed agent loops and explicit function tools |
| [claude-agent-sdk](https://github.com/anthropics/claude-agent-sdk-python) | alternative | source review | Programmatic Claude Code agent loop |
| [mlflow](https://github.com/mlflow/mlflow) | conditional | source review | Versioned experiment artifacts, model lineage and optional traces |

## Recommended next adoption sequence

1. Preserve the native worker and existing evidence; resolve native plugin workspace attribution upstream before claiming SDK file-tool parity.
2. Add artifact-scoped SBOM and vulnerability reporting to the publication pipeline, with version, database timestamp and reviewable findings.
3. Select one scheduler only when a concrete recurring research job is defined; prove cancellation and failure recovery using public fixtures before any broker integration.
4. Add bounded metrics and one trace destination for persistent jobs; avoid exporting raw sessions by default.
5. Treat managed hosting, distributed inference and the broker execution service as separate deployments with their own identity, operating costs and acceptance.

## Accepted follow-up integrations

[DeerFlow/ACP](../../blueprints/us-equities/deerflow/research-receipt.json) completed one native Astra task: 41,737 input (24,320 cached) and608 output tokens. ACP's `read-only` mode actually maps to workspaceWrite with approvals; strict read-only workers should use the native SDK. [Dagu](../../blueprints/us-equities/hosting/README.md) now has a completed three-step local research DAG, authenticated loopback status service, failure/cancellation evidence and persistent completed history after restart. Neither result establishes autonomous trading or net provider savings.
