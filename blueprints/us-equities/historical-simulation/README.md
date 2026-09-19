# Native historical exposure and margin stress

Six frozen LEAN simulations completed on bundled SPY history from **December 2,
2019 through April 30, 2020**. They exercise requested leverage, automatic exposure
reduction, native margin liquidation and an over-limit rejection. These are
known-crash development scenarios, with no parameter changes after outcomes and
no strategy selection or performance promotion. The target catalyst/+200% mover
research still requires accepted candidate and event data.

## Direct results

Each run started with $100,000. The requested 1x/2x targets use a declared 2%
sizing buffer and integer shares; actual exposure changes with price and equity.
"Stress" means $1 per order plus 20 basis points of price slippage, with no
financing charges configured. These are illustrative assumptions.

| Scenario | Native end equity | Fees | Native dividends | Observed drawdown | Fills | Margin liquidations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1x, zero costs | $90,734.08 | $0 | $428.64 | 33.98% | 2 | 0 |
| 1x, stressed costs | $90,358.00 | $2 | $428.64 | 34.04% | 2 | 0 |
| 2x, zero costs | $76,310.34 | $0 | $613.35 | 58.52% | 5 | 3 |
| 2x, stressed costs | $75,607.75 | $5 | $610.53 | 58.65% | 5 | 3 |
| Adaptive 2x → 0.5x, stressed costs | $95,324.10 | $3 | $211.50 | 19.40% | 3 | 0 |
| Over-limit 4x request under 2x margin model | $100,000.00 | $0 | $0 | 0% | 0 | 0 |

All positions finished flat. The last case received **one native insufficient
buying-power rejection**, requesting 1,217 shares with initial margin $195,852.81
against $100,000 free margin. All seven native commands—one compilation and six
engine launches—returned zero. Stderr was **381 and 390 bytes** for the two
leveraged cases, recording three margin liquidations each, and **202 bytes** for
the expected rejection; the other four commands had empty stderr. There were
no failed local data requests. [Exact receipt and argument arrays](receipt.json).

The adaptive rule was fixed before execution: once completed-session equity is
5% below its previously observed hourly peak, request 0.5x gross at the next
session open, with a one-way latch. It fired on **January 27 at 16:00 New York**,
at 5.2977% observed drawdown; the reduction of 458 shares was recorded at 10:00
on January 28. The lower loss in this deliberately selected stress interval
does not establish a robust or profitable strategy.

Both 2x controls triggered default engine liquidations on February 28, March 12
and March 18. Their maximum callback-observed gross exposures exceeded 2x after
losses. A target or initial-margin check is therefore not a continuous exposure
cap. Margin warnings are repeated engine callbacks, not distinct trading days.
Stressed costs also changed forced-liquidation quantities, so the two leveraged
paths do not keep an identical fill schedule and quantity ledger.

## Data and causal timing

The installed sample contains SPY daily/hourly files spanning January 2, 1998 to
March 31, 2021. The selected window has **104 daily rows and 725 hourly rows**
across all **104 expected XNYS sessions**, with no missing/extra session dates.
This date check does not establish complete market observations or entitlement.
Each engine run processed 1,457 data points and recorded 725 hourly callbacks.
The request log lists hourly SPY, daily SPY and the engine's interest-rate
reference file; native raw-data dividend cash is included in reconciliation.

The entry decision is December 31 at 16:00, with the exit decision April 29 at
16:00. All discretionary orders use upstream `MarketOnOpenOrder` on a later
session. On this hourly feed, native fills are timestamped **10:00 New York**
using the next bar's open-price proxy. This does not accept an exact 09:30
opening-auction price, tick feed or real execution latency. Native
[`EquityFillModel.MarketOnOpenFill`](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Orders/Fills/EquityFillModel.cs#L482)
rejects stale/same-bar opens, then assumes full quantity fills.

The model is explicitly
[`SecurityMarginModel(2m)`](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Securities/SecurityMarginModel.cs#L54),
with constant illustrative initial/maintenance requirements. The native
[`DefaultMarginCallModel`](https://github.com/QuantConnect/Lean/blob/985ef30ad3ac774218c5ac516b4cb0aa2655730f/Common/Securities/DefaultMarginCallModel.cs#L73)
remains enabled. Its same-event market liquidations and trade-bar fallback
warnings are retained. This is not an Alpaca account, current broker margin
contract or calibrated liquidation model; the historical PDT model is unused.

Drawdown/exposure statistics use hourly callbacks after engine processing.
Intrabar and pre-liquidation risk may be worse; separate margin-call equity
and deficit observations are retained. No borrow/financing cost, depth,
participation cap, partial fill, impact or halt/resumption acceptance follows.
SPY data cannot validate small-cap catalysts, a survivor-safe universe or the
historical +200% mover cohort.

## Native replay and audit

Use the [accepted remediated LEAN installation](../engine/resolution.md), its
isolated .NET 10.0.401 SDK, Bubblewrap and Python 3.11+. No Python packages,
package restore, model inference, broker account or data download are needed
for the runs. [The frozen plan](plan.json) records all six scenarios. The local
algorithm is an integration around upstream APIs, not an unchanged example.

```sh
python3 blueprints/us-equities/historical-simulation/run.py \
  --lean-source "$LEAN_SOURCE" \
  --dotnet "$DOTNET_ROOT/dotnet" \
  --out "$NEW_PRIVATE_RESULT_DIR"
```

The actual native commands inside the inherited isolated sandbox are:

```sh
/dotnet/dotnet /dotnet/sdk/10.0.401/Roslyn/bincore/csc.dll @/run/build/compiler.rsp
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/one_zero/config.json
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/one_stress/config.json
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/two_zero/config.json
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/two_stress/config.json
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/adaptive_stress/config.json
/dotnet/dotnet /engine/QuantConnect.Lean.Launcher.dll --config /run/over_limit/config.json
```

Audit retained native results without rerunning the engine:

```sh
python3 blueprints/us-equities/historical-simulation/analysis.py --run "$PRIVATE_RUN"
python3 -m unittest tests.test_historical_simulation -q
```

The analyzer reconciles fills, fees and distributions to flat cash within one
cent of exported native values. It checks terminal results, native order type,
quantity and tags; each discretionary fill follows its decision, while every
engine margin fill matches its callback timestamp/count. It rejects missing
or failed data-request logs. Ten focused tests exercise malformed attribution,
causality, cash, positions, adaptive/rejection outcomes and nonfinite values.

Independent review identified the need to bind forced fills to actual native
order tags and callback counts. The strengthened analyzer passed over all six
retained results, with no engine rerun or parameter change. Original runner
and initial analyzer hashes are retained separately from current replay code.
All 1,476 mounted engine/data hashes stayed unchanged; inputs are mounted
read-only with no network/account stores. Hashes establish byte identity,
not third-party data authenticity or immutable off-host retention.

The next meaningful research gate is accepted as-known candidate/catalyst data
and a frozen all-candidate experiment ledger. Current simulation results do not
enable paper orders, automatic strategy promotion or live trading.
