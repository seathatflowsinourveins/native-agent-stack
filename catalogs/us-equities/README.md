# US-equities grand catalog

**Dated decision catalog: September 19, 2026.** The north star is native, token-efficient research → reproducible backtesting → Alpaca paper automation. This is an examined selection across layers, not a universal final SOTA ranking or a claim that every listed framework runs together.

The catalog has **145 repository decision cards covering 140 unique GitHub repositories**, and **20 model entries**. It connects to the earlier 36-component foundation. The [combined repository index](repository-index.md) contains **447 repository identities**, including all 337 public stars and 110 beyond that snapshot, with overlap removed.

## Read the layer you need

| Layer | Cards | Guide / structured manifest |
| --- | ---: | --- |
| Token efficiency, memory, retrieval, document ingestion | 36 | [foundation-memory](foundation-memory.md) · [JSON](foundation-memory.json) |
| Agents, OmniRoute, SDKs, orchestration, hosting, security, telemetry | 35 | [agents-operations](agents-operations.md) · [JSON](agents-operations.json) |
| Market/reference/filing data, storage, quality, lineage | 36 | [data-research](data-research.md) · [JSON](data-research.json) |
| Engines, broker adapters, portfolios, statistics, strategy research | 38 | [engines-strategies](engines-strategies.md) · [JSON](engines-strategies.json) |
| Current model choices and older compatible baselines | 20 | [Models](models.md) · [JSON](models.json) |

Start with the [north-star architecture](../../blueprints/us-equities/north-star.md), [native commands and direct results](native-workflows.md), [harness contract](../../blueprints/us-equities/harness-contract.json), and [machine-readable catalog manifest](manifest.json).

## Recommended convergence

Use native **Codex SDK/Astra + Claude Opus**, **Context Mode/RTK**, **ai-memory**, scoped **QMD/Serena/SocratiCode**, and existing **Nemotron/vLLM/Qdrant**. Keep **DuckDB/Parquet + exchange calendars** for deterministic data work and **LEAN** as the accepted source-built backtest engine. The official **Alpaca adapter** is the paper target, with the SDK as a read-only observer and one future order writer. QuantStats is a proposed reporting layer; selected statistical/ML tools follow only after point-in-time data exists.

**OmniRoute** remains an optional route with explicit model fidelity and usage checks; **DeerFlow** remains a research orchestration candidate whose backend and ACP discovery ran but full inference chain did not. Add document RAG, a temporal graph, durable scheduling, remote sandboxes or managed hosting only for a concrete requirement. A healthy endpoint, installed SDK or paper simulator is not a complete automated trading runtime.

## What the evidence establishes

- Native Astra SDK research used Context Mode and returned useful results. All three turns, including failed file-scope checks, have usage receipts: 202,164 input / 176,000 cached input / 1,927 output. Cache reuse is 87.06%, not a net-savings comparison.
- Native LEAN source build and unchanged bundled backtest passed: 3,943 data points, 3 simulated orders, 13/13 local-data requests. Data transformed through DuckDB/Parquet successfully.
- New native QMD catalog retrieval produced 490 tokens versus 6,398 for the full model-guide output: 5,908 fewer, 92.34% less retrieved text. Both artifacts and upstream tokenizer replay are retained.
- Native HF discovery returned 17 model metadata records and 11 model cards. Only separately cited earlier/native runs establish inference; model-card retrieval does not.
- New catalog recipes are prospective unless their referenced receipt explicitly establishes execution. No Alpaca connection, strategy edge or deterministic risk service was accepted. A later manual research DAG and authenticated local Dagu history host were accepted; this is not unattended trading.

## Starred repositories and beyond

The fresh authenticated listing contained **337 public stars**. **41** have current catalog cards; **10** more have adopted baseline records; **286** have no current catalog/baseline card. All337 now also have individual dispositions in the [complete star audit](star-audit.md), with README/license overview separated from deeper source inspection. Absence of a full catalog card is no longer an unreviewed identity. **99** catalog repositories are beyond the starred snapshot. [All identities and joins](coverage.json).

Source review covered current official metadata, README/license text and relevant API/source documentation at the depth stated per record. It did not deeply benchmark all 337stars or every project beyond them. Repository freshness, stars, model launch dates and author benchmarks do not establish superiority. The catalog exposes missing acceptance work rather than turning a list into a deployment claim.

## Decision and evidence vocabulary

| Field | Meaning |
| --- | --- |
| default | Recommended responsibility in the selected path; actual installation/acceptance is stated separately |
| conditional | Add when the stated workload, entitlement or evaluation justifies it |
| alternative | Competing implementation; do not stack it by default |
| watch | Relevant research or integration lead with unresolved adoption issues |
| excluded | Not eligible for the selected path under current compatibility, lifecycle, license or user constraints |
| native_proven | Only the cited local receipt scope ran; may be a CLI/health/sample proof, not model or broker E2E |
| source_review | Primary-source examination and proposed commands; no new runtime acceptance |

Every card supplies role, selection reason, version/source, license, US-equity/Alpaca fit, requirements, limitations, source links and native workflow entry points. Commands without pins are moving upstream examples; lock the selected versions before deployment. Keep each candidate in its own compatible environment. Never concatenate the catalog into a global installer.

## Freshness findings that change decisions

- TimesFM 3.0 weights are non-commercial; Apache 2.5 remains the conditional forecasting baseline. Jina reranker 3.5 also has a non-commercial license.
- Letta V1 is retired; current work lives in letta-ai/letta-code. Daytona’s current SDK is distinct from its last public core, whose development moved private.
- SGLang 0.5.20 requires CUDA 13; the working local vLLM 0.25 service is retained after the recorded 0.29 WSL failure.
- Lumibot release license/setup metadata conflict; Fincept has additional commercial restrictions. Vectorbt’s Commons Clause and separate PRO product are explicit.
- GitHub latest-release tags can refer to SDKs/plugins rather than core packages. Mem0, LangGraph, OpenBB, Darts and forecasting models need artifact-specific version labels.

The underlying source citations and precise scopes appear in the layer guides. See [publication coverage history](../../docs/convergence-audit.md) for the earlier, smaller audit.

## Subsequent native gap resolution

See the [resolution ledger](../../blueprints/us-equities/gap-resolution.md) for real DeerFlow→native Astra inference, the patched LEAN/adaptor build, Dagu workflow hosting and the current gateway/account boundary. Historical receipts above retain their original scope and counts.
