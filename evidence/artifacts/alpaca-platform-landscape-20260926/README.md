# Alpaca platform landscape (2026-09-26)

**Question (user, 2026-09-26):** "Are NautilusTrader and LEAN the only options? What do other Alpaca users run for SOTA practice, with historical data end to end?"

**Answer.** No. Alpaca users run several other platforms. Nothing reviewed beats the current pairing on merit for this north star, and the remaining end-to-end gap is data, not the engine. The current pairing is:
- NautilusTrader 2.0.0rc5 as destination;
- LEAN as the frozen oracle;
- alpaca-py plus the in-repo adapter for paper.

## What Alpaca users run

| Platform | Alpaca route | Notes |
| --- | --- | --- |
| **QuantConnect LEAN** with the official `Lean.Brokerages.Alpaca` plugin | Alpaca's own partner | The CLI's local Alpaca path needs a paid QuantConnect organization. Initialization uploads host identity. Default Alpaca fills are optimistic. |
| **Lumibot 4.6.1** | One strategy class from backtest to Alpaca paper | GPL-3.0. Adjusted-price defaults conflict with this repository's raw-bars-plus-actions policy. |
| **ml4t** (`backtest` / `live` / `data`) | Paper and live via its own `live` package | MIT. Newest and most rigorous pure-Python stack: volume-participation partial fills, market impact, a LEAN-parity preset. Pre-1.0. |
| **QuantRocket** (commercial, self-hosted Docker) | Multiple paper and live Alpaca accounts | Vendor claims survivorship-free 1-minute US data from 2007. Its paper route requires validating a live account first, which the paper-only policy forbids. |
| **vectorbt** / **PyBroker** | Alpaca as a data source only | No paper path. Apache-2.0 plus Commons Clause. |
| **Alpaca official agent layer**: `alpaca-mcp-server` (MIT), `alpaca-skills`, `alpaca` CLI | Research and agent access | Not a backtester. |
| **Hosted and no-code partners**: Composer, TradingView, Blueshift, Wealth-Lab, AlgoBulls, Tradetron | Varies | Hosted, closed or Windows-only; no reproducible local pipeline. |

Dormant or legacy: backtrader's Alpaca bridge, pylivetrader, Zipline Trader, LiuAlgoTrader, Blankly.

NautilusTrader has **no upstream Alpaca code**. RFC nautechsystems/nautilus_trader#3374 is still open, and PR #3375 was closed unmerged the same day. That is why this repository keeps its own adapter.

## Recommended next steps

These belong to the trading lane, which owns the rows.

1. Run the frozen `alpaca-history-fixture-v1-20260925` once paper keys are stored.
2. Two free targeted trials on the frozen SPY `one_zero` parity case, scored by `blueprints/us-equities/engine-nautilus/spy-parity/compare.py`:
   - first, ml4t-backtest's `lean` preset;
   - then, Lumibot 4.6.1.

   Only after a PASS does either get one SPY paper round trip on the alpaca-paper-smoke contract, with one owned writer.
3. The data gap (survivorship-free universe, delistings, dated identity) is closed only by licensed datasets: QuantRocket usstock, QuantConnect US Equity Security Master (AlgoSeek), Sharadar or Databento. Score them on the frozen fixture rows before buying anything.

## Catalog gaps found

All are in trading-owned rows.

- QuantRocket was never evaluated as an Alpaca platform.
- ml4t has not been evaluated.
- Lumibot's evidence is stale: the record says "MIT vs GPL", but it is GPL-3.0 throughout at 4.6.1.
- The LEAN Alpaca `conditional` row omits the paid-tier and host-identity gates.
- hftbacktest is still `out_of_scope`, although it is the accepted sim cross-check.
- Alpaca's integration partners have no dated dispositions.
- Community Nautilus Alpaca adapters have not been compared with the in-repo adapter.

## Files

- `landscape.json`
  - `evaluation`: 30 ranked platforms, each with a verdict, a comparison with the current pairing and the trial it would need.
  - `catalog_gaps`.
  - `facts_check`: an independent refuter's corrections.
  - `returns`: the three raw research returns, two from Claude Opus and one from GPT-6-Astra.
- `tavily-research-pro.json`: the Tavily Research (`--model pro`) report, with 32 sources, request id and timing. This is the first use of the Research endpoint in this repository. The key was held only in the kernel keyring (see `docs/secret-storage.md`).

## Evidence class

Source and documentation review. Nothing was installed or run. The verdicts are proposals for the trading lane's rows and for the next verdict wave; they are not selections.
