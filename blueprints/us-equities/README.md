# US-equities research, replay and broker acceptance

**Current selection, September 20, 2026:** native research and reproducible
simulation, followed by independently accepted **IBKR and Alpaca paper** paths.
The selected engine is **NautilusTrader 2.0.0rc5**; LEAN remains the accepted
historical comparison. Nautilus supplies the native IBKR integration; Alpaca
requires a separate deterministic adapter. The [runtime target](../../catalogs/us-equities/runtime-target.json)
records those boundaries, and the [acceptance plan](engine-nautilus/acceptance-plan.md)
defines the next equity replay, offline fault cases and separate paper gates.

The [foundation catalog](../../catalogs/foundation/README.md) supplies native
Codex/Claude, context, memory, retrieval and operations. The September 19 native
results below remain dated evidence. This is a research and simulation foundation;
a complete trading service and validated strategy remain open.

```mermaid
flowchart LR
  D[Versioned data and documents] --> Q[DuckDB and Parquet]
  D --> R[Scoped QMD / SocratiCode / memory]
  Q --> W[Native Astra research workers]
  R --> W
  W --> P[Source-linked research proposals]
  F[Optional DeerFlow research orchestration] --> W
  G[Optional OmniRoute routes] --> F
  P --> V[Reviewed versioned strategy]
  V --> N[Nautilus replay]
  L[Retained LEAN baseline] --> N
  N --> C[Offline risk and reconciliation acceptance]
  C -. separate acceptance .-> I[IBKR paper via native adapter]
  C -. separate acceptance .-> A[Alpaca paper via separate adapter]
```

The broker side must own numeric validation, order state and reconciliation.
Models produce research and proposed code; they do not own broker credentials
or an unrestricted order-submission tool.

Read the [north-star architecture and acceptance boundaries](north-star.md),
[grand repository catalog](../../catalogs/us-equities/README.md), and
[machine-readable harness contract](harness-contract.json) for the integrated path.

The latest [roles and architecture convergence](architecture/README.md) adds
current source reviews, explicit data/simulation/paper promotion gates, official
Alpaca constraints and a native two-model critique. It separates platform support
from actual host acceptance and records the observed advanced-order SDK gap.

## Current engine and broker scope

The [local native receipt](../../evidence/receipts/native-nautilus-v2-20260920.json)
and [fresh hosted receipt](../../evidence/receipts/native-nautilus-ci-20260920.json)
accept only the unchanged synthetic EUR/USD quickstart and economic repeatability.
The retained SPY equity replay has not yet run in Nautilus. Alpaca has dated
[authenticated read-only data evidence](authenticated-data/README.md) and
[identity observations](identity-readiness/README.md); neither establishes current
Elite entitlements or order execution. IBKR native sign-in, paper account/data
access and broker operations remain unestablished.

## September 19 stack and native acceptance snapshot

| Layer | Upstream selection | Status and evidence |
| --- | --- | --- |
| Native agents | [OpenAI Codex](https://github.com/openai/codex), [Claude Code](https://github.com/anthropics/claude-code) | Existing native ecosystem; this extension ran one native Astra SDK research task. It did not rerun Claude. |
| Worker SDK | [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk), `openai-codex 0.154.0`, native Codex `0.155.1` | Installed; sign-in, model/allowance discovery and real task completed; [commands and usage](workers/README.md). |
| Research harness | [DeerFlow](https://github.com/bytedance/deer-flow), pinned `42334f2` | Backend `2.1.0-rc0` installed; 23 skills, healthy native HTTP backend. Distinct from stable `2.0.0`; no model configured in its own SDK. [Proof](deerflow/README.md). |
| Native agent protocol | [Codex ACP](https://github.com/agentclientprotocol/codex-acp) `1.12.0` | Installed; discovery and one DeerFlow→ACP→Astra research task passed. ACP read-only mode actually grants workspaceWrite; [exact limits](deerflow/research-receipt.json). |
| Optional routers | [OmniRoute](https://github.com/diegosouzapw/OmniRoute) `3.8.50`, [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) `0.11.0` | Existing installations healthy; explicit historical Qwen/Opus routes. Astra text Responses accepted; full native tool/hook parity remains unproved. [Native settings and limits](routing/README.md). |
| Large outputs and local retrieval | [Context Mode](https://github.com/mksglu/context-mode), [RTK](https://github.com/rtk-ai/rtk), scoped QMD, Serena, SocratiCode | Existing stack; real Astra worker used Context Mode in this run. One file-scope failure retained. See [full baseline manifest](../../manifests/stack.json) for repository identities and pins. |
| Shared memory and local RAG | [ai-memory](https://github.com/akitaonrails/ai-memory), SocratiCode, Qdrant, vLLM/Nemotron embeddings | Existing agent-lab scope and automatic refresh evidence retained; publication/new projects require deliberate adoption. No duplicate DeerFlow memory store enabled. |
| Data computation | [DuckDB](https://github.com/duckdb/duckdb) `1.5.5`, [exchange_calendars](https://github.com/gerrymanoim/exchange_calendars) `4.13.2` | Installed; LEAN event JSON→Parquet→SQL counts/calendar completed. [Commands](data/README.md). |
| Historical backtest engine | [QuantConnect LEAN](https://github.com/QuantConnect/Lean), pinned `985ef30`, .NET `10.0.401` | Native source build and unchanged bundled sample passed: 3,943 data points, three simulated orders. [Receipt and replay](engine/README.md). |
| Then-selected paper adapter | [LEAN Alpaca adapter](https://github.com/QuantConnect/Lean.Brokerages.Alpaca), reviewed `1973f61`; [alpaca-py](https://github.com/alpacahq/alpaca-py) `0.44.0` | SDK installed; official adapter and patched source-integration variant built. That LEAN adapter requires separate QuantConnect entitlement plus Alpaca paper access. Its compilation did not initialize a brokerage or submit orders. |
| Direct model API alternative | [OpenAI Python](https://github.com/openai/openai-python) `3.16.2` | Installed, no API key or paid API request. Native subscription access is not API authorization. |
| Hosting and observability | Native manual workflows plus authenticated Dagu local history service | [Hosting guide](hosting.md); private native receipts, elapsed time, usage, warnings and hashes retained. No public endpoint or standing trading service deployed. |

These are complementary layers. They are not all stacked on every request.
DeerFlow already uses LangGraph; another orchestration framework is not needed
for this proof. Temporal is a possible later durable workflow layer, not an
installed dependency. The earlier Nautilus comparison decision is superseded by
the selected 2.0.0rc5 target above; the absence of an official Nautilus Alpaca
adapter remains a separate integration constraint. vectorbt is optional analysis
software with a Commons Clause license addition; it is not adopted as the engine.
See [the dated manifest](manifest.json) and [coverage limits](../../docs/convergence-audit.md).

## September 19 results and remaining scope

- **Ran:** native SDK inference with Context Mode; native DeerFlow health and
  ACP discovery and actual embedded research; patched LEAN build/backtest; Dagu workflow and history restart; deterministic Parquet/SQL/calendar
  processing; fresh router health checks. The manifest links the exact receipts.
- **Measured:** the successful research turn used 133,839 input tokens, of which
  119,424 were cached, plus 1,472 output tokens. Including two unsuccessful
  file-tool follow-ups, the totals are 202,164 input / 176,000 cached / 1,927
  output. This is 87.06% aggregate cache reuse, not a net-savings benchmark.
- **Not complete:** DeerFlow's full application/planner hosting, full native gateway parity,
  broker execution acceptance, current live-data/Elite entitlements, actual
  strategy validation, order-risk/reconciliation implementation and unattended
  hosting/recovery. Installed libraries or a healthy port do not prove those.
  A Context Mode file-tool workspace override also remains pending normal native
  MCP approval in that run; trusted execution-tool extraction worked. Later
  read-only Alpaca authentication and historical data receipts are linked above;
  this historical limitation must not be read as a current absence of credentials.
- **Historical dependency issue:** the original LEAN restore reported seven advisory/package pairs,
  including critical severity. The subsequent patched launcher and source-integrated
  adapter audits reported zero vulnerable packages in their checked graphs.
  Original warnings and remaining compiler diagnostics are retained.

Alpaca's free paper-only data access is IEX, not consolidated US-market coverage,
and simulated fills omit important real execution effects. Use separately scoped
paper credentials and `TradingClient(..., paper=True)` for initial read-only
account/clock validation. The account SDK must not become a second order writer
alongside the engine. [Alpaca paper documentation](https://docs.alpaca.markets/us/docs/paper-trading)

The next execution implementation needs a versioned strategy, intended holding
period/universe, data entitlement and explicit numeric risk limits. It must
persist client order IDs, reconcile after ambiguous timeouts, check stale data,
market sessions, buying power and exposure, and make the kill switch independent
of model availability. None of those controls are claimed implemented by a policy
file. No live-trading authority or profitability claim is implied.

[Gap-resolution ledger](gap-resolution.md) records the later fixes, direct upstream command results and remaining external requirements. [LEAN resolution](engine/resolution.md) preserves the original warning evidence alongside the locally patched build.
