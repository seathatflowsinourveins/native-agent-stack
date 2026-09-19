# Daily and intraday catalyst research protocol

The user selected **both daily and intraday research**, focused on potential
large movers, pre-positioning and early entry, including historical **+200% and
larger moves**. “Incentive-driven” is provisionally interpreted as catalyst/event-driven.
The [structured protocol](research-protocol.json) records that direction while
leaving capital, risk, source entitlements, evaluation intervals and promotion
thresholds unset. This is a research design, with no accepted strategy or broker authority.

## Two timing hypotheses

| Track | Eligible decision information | Excluded hindsight |
| --- | --- | --- |
| Scheduled-event pre-positioning | Event schedules and features demonstrably known before entry | Future release content, surprise, schedule revisions or eventual mover ranking |
| Post-signal early entry | A received catalyst, trailing price/relative-volume features and eligible liquidity | Final daily volume/high, later corrections or fills before the signal existed |

Daily and intraday cohorts must be scored separately. A close-derived daily signal
cannot execute at that same close. Intraday entry follows actual information
receipt and declared processing/order latency at a tradable market state.
The fixed SPY experiment remains an accounting control, not the target strategy.

## Historical extreme-mover cohort

Create a discovery cohort for observed price increases of at least 200%:
return `>= 2.0`, equivalent to a price ratio `>= 3.0`. Freeze the anchor and
horizon before extraction. Prior regular close to intraday high, first executable
post-signal quote to exit, and multiday close-to-close are different measures;
never mix them in one claimed return. Exact horizons remain to be selected.

Keep split/reverse-split adjustments, cash distributions, symbol changes,
delistings, IPO/no-prior-close cases, bad ticks, feed, session, halt state and
liquidity explicit. Preserve raw and adjusted prices with source evidence.
A reported high or trough-to-peak change is not an attainable strategy return.
Record first threshold-crossing time separately from the final known high.

Use verified historical cases to generate hypotheses and inspect earlier
catalysts/features. Any inspected cases belong to development data. Test entry
skill against the **complete as-known candidate universe**, including nonmovers,
failed signals, untradable names and missed moves. A final top-gainers list cannot
define the evaluation universe. Freeze the direction, return horizon and target
before scoring; report event-only, price/volume-only, combined and no-signal controls.

## Data and timing requirements

Retain event ID, issuer/asset mapping, known event-schedule version, publication,
source-update, original receipt and local ingestion time, payload hash and
feature-completion time. A current historical article with a later update does
not establish its original text. Alpaca news has creation/update fields and
historical sorting by updated time; it does not document an immutable revision
archive. [Realtime schema](https://docs.alpaca.markets/us/docs/streaming-real-time-news),
[historical news](https://docs.alpaca.markets/us/reference/news-3).

Retain each initial/revised bar with its interval, received time, feed, adjustment,
session and pagination evidence. Alpaca historical bars sort by symbol, and
continuation can remain after a short page. Its `asof` option handles symbol
mapping rather than historical knowledge availability.
[Historical bars](https://docs.alpaca.markets/us/reference/stockbars).

Alpaca streams late bar revisions and nanosecond trade/quote timestamps. Final
bars cannot stand in for their initial observed values. The accepted synthetic
PIT contract safely rejects finer-than-microsecond timestamps; it is **not yet
a raw-tick adapter**. Preserve exact raw timestamps/sequences and require exact
finer-resolution handling or separately verified conservative normalization.
[Stock-stream semantics](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data).

Treat news dissemination, quote resumption and trade resumption as distinct
states. A catalyst or quote does not alone establish a possible fill.
[Nasdaq halt definitions](https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltCodes).
Regular-session mechanical acceptance comes first; extended/overnight sessions
need separate data, asset and order support. The current guard rejects those
instructions. [Alpaca order constraints](https://docs.alpaca.markets/us/docs/orders-at-alpaca).

## Evaluation and ledgers

The [factor/feed and regime design](factors-regimes.md) adds complementary data
sources and a versioned selector over validated strategies. Its confidence,
hysteresis, cooldown and portfolio-transition rules remain unset until evaluation;
no automatic strategy switching is enabled by this document.

Keep two linked records: an experiment ledger for every hypothesis, parameter,
model/prompt/code/data version, failure and inspected result; and a candidate
ledger for every asset/event at each cutoff, eligibility reason, contemporary
rank, source versions, decision time, fill outcome and subsequent label.

Freeze chronological training, validation and holdout intervals before scoring.
Keep related issuer events/revisions together across daily and intraday cohorts.
Purge overlapping label/holding intervals, fit transformations on training only
and derive embargo from timing/dependence. Once results guide selection, that
interval is development evidence. The upstream
[WalkForward interface](https://skfolio.org/generated/skfolio.model_selection.WalkForward.html)
provides primitives, not complete event-level leakage protection.

Report all signals, false positives, missed moves, unfilled/partial orders, halted
names, costs, capacity, drawdown, exposure and sample uncertainty. The
[LEAN sensitivity result](../execution-realism/README.md) verifies fixed-schedule
cost response; quantity, spread, latency and impact calibration remain open.

Next: accept versioned catalyst/candidate data and frozen numeric criteria, then
run offline strategy/control comparisons and order-state fault scenarios.
No historical vendor dataset or +200% case census was acquired in this wave.
Source rights and availability must be accepted before market-performance claims;
paper integration additionally needs account/risk choices and authorized broker progression.
