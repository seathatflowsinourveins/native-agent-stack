# Alpaca paper and equity simulation practice — 2026-09-21

The selected path is the existing `alpaca-py==0.44.0` SDK with a bounded deterministic paper adapter, and NautilusTrader 2.0.0rc5 for native equity replay. This extends the prior read-only acceptance. The [runtime target](runtime-target.json) records completed evidence and outstanding work; a repository's presence in this catalog does not establish its execution quality.

## Current account and rate boundary

The authorized paper profile authenticated to the native paper endpoint on September 21. Six Trading GETs returned HTTP 200 with `X-Ratelimit-Limit: 200`; the account was active, unrestricted and flat with no open orders. Regular-session SPY IEX quotes were available. The initial lifecycle runner uses 120 requests/minute and at most USD 1,000 order/exposure.

Alpaca's [current Elite comparison](https://alpaca.markets/elite) describes 200 and 1,000 **Trading API calls** per minute for commission-free and Smart Router paths respectively. A completed roundtrip uses multiple calls and two fills. The product page does not override this paper account's returned 200 limit. Increasing throughput requires verified account entitlement and a separately frozen request/position budget; no paid upgrade or entitlement change was performed.

## Source-backed choices

| Repository / pinned source | Decision and comparison that would change it |
| --- | --- |
| [alpaca-py v0.44.0](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28) | Retain installed SDK and reuse selected upstream paper REST probes. Add the missing durable order lifecycle locally. Replace only if measured broker behavior or supported serialization shows a material gap. |
| [alpaca-skills](https://github.com/alpacahq/alpaca-skills/tree/39111abee6b60af7c11d40b5fc892dfc4fd791a4) | Source reference for SDK-neutral paper workflow and historical reporting. Existing canonical authorization and deterministic execution rules already cover this task; no additional runtime layer is required. |
| [Alpaca CLI](https://github.com/alpacahq/cli/tree/53606273aa230a40c64b783425dcb3f4423ede30) | Keep as a native alternative. Its order lifecycle tests are useful source examples, but its full integration suite can cancel existing orders, and its lifecycle test accepts `pending_cancel`. Adopt only for a demonstrated operator workflow that the SDK runner cannot provide. |
| [Alpaca MCP server](https://github.com/alpacahq/alpaca-mcp-server/tree/9b0c72beda5579de088413ce9c3720456cde8f5f) | Keep as comparison for a separately requested conversational brokerage surface. Full tests include account-wide cancellation/closure. It adds no needed capability to this deterministic account-writer lane. |
| [Legacy Python SDK](https://github.com/alpacahq/alpaca-trade-api-python) | Archived; retain historical reference, use `alpaca-py` for new work. Reconsider only with a supported maintenance path and a demonstrated compatibility need. |
| [Backtrader adapter](https://github.com/alpacahq/alpaca-backtrader-api/tree/475bb54b8b16506092eb97df5a7cb1d05f0b86be) | Keep as a dated alternative; the main implementation is from 2022. No measured advantage warrants replacing the selected Nautilus/LEAN simulation paths. |

The official [SDK live-test documentation](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/tests/live/README.md) supports paper REST/streaming probes. Selected read-only checks establish native connectivity and schema behavior; they do not establish submit/fill/cancel reconciliation. Retain both the upstream results and the separate operational lifecycle results.

## Simulation and paper evidence

Use native BacktestEngine execution on retained, hashed historical equity data with an explicitly fixed schedule, followed by cost/slippage stress. Freeze the date interval and avoid unsupported corporate-action transitions. A diagnostic schedule is not a selected profitable strategy; historical data observed locally today does not establish an as-known historical universe.

Alpaca's [paper specification](https://docs.alpaca.markets/us/docs/paper-trading) describes simplified liquidity and partial-fill behavior. Paper omits important real execution costs and queue/impact effects. Keep broker-observed fills, native historical simulation and synthetic failure tests separately labelled. Neither a fast simulator nor paper fill throughput proves attainable live execution capacity.

The initial lifecycle is a bounded operational smoke test. Broader catalyst research, the retained SPY/LEAN cash-and-dividend oracle, realistic latency/liquidity stress, IBKR paper execution and Elite advanced order types require their own evidence. Unresolved items remain visible rather than being described as a fully resolved foundation.
