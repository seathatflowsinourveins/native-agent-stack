# sim-capacity: simulation-lane throughput/capacity infrastructure test

**This is infrastructure evidence, not strategy evidence.** `CapacityExerciser`
(`exerciser.py`) carries no signal, forecast or edge -- it round-robins a fixed
symbol list on a clock-timer schedule and submits marketable LIMIT IOC orders
purely to load the venue/risk-engine pipeline. Every artifact here is tagged
`evidence_class: sim_capacity_infrastructure` and every receipt carries a
`claim_boundary` echoing the rules this lane must respect:

- `docs/harness-rules-convergence-20260922.md` NS-06 (~L221): a synthetic
  throughput figure is "fixture evidence only and must never be cited as
  broker throughput or strategy performance".
- `blueprints/us-equities/adaptive-paper/README.md` L41: "No strategy
  manufactures trades to hit a throughput target."
- `blueprints/us-equities/mover-v3/README.md` (~L294-374) and
  `catalogs/us-equities/mover-v3-sweep-20260924.json` (~L255): throughput is
  capacity, not a trading target, and high rates are cost-bound; "a high-rate
  capacity replay is an infrastructure test, never strategy evidence."

## H1 -- why the engine is fed quotes only (no trade ticks)

**An independent review found that 41.2% of elite-tier fills (8,923 of
21,652) beat the NBBO touch** when the engine's tick feed included trade
prints alongside quotes. Mechanism (verified against the pinned rc5 source,
commit `1b0a49d2792a9432a3aca3fcb617ce7a630d905e` of
[nautilus_trader](https://github.com/nautechsystems/nautilus_trader)):

- An L1 book (`book_type=L1_MBP`) overwrites **both** sides with a trade
  print's price and size (`crates/model/src/orderbook/book.rs:1255-1300`).
- For a `NoAggressor` trade, nothing restores the prior quote afterward
  (`matching_engine/mod.rs:2363-2367,2395-2408`); the book stays locked to the
  trade print until the next actual quote tick
  (`matching_engine/mod.rs:4254-4265`).
- This happens even with `trade_execution=False`, because the book update
  happens before that flag is ever consulted (`matching_engine/mod.rs:2272-2288`).
- 58.8% of the affected trades are sub-penny prints, rounded to the cent at
  fill-tick construction time, which is exactly what let an IOC order match a
  stale, better-than-NBBO price.

Alpaca's historical trade record also carries **no aggressor-side field**, so
every `TradeTick` `fetcher.py` builds is tagged `AggressorSide.NO_AGGRESSOR` --
which is precisely the condition under which rc5 never restores the quote
above. This is not a queue-realism bonus; it is a data artifact that
corrupts the touch. (A side-bearing trade tick was not attempted, since
verifying from source that it does not *also* corrupt the L1 book would be
its own separate investigation; quotes-only sidesteps the question entirely
for a taker-only exerciser.)

**Fix.** The exerciser is taker-only (marketable IOC only; it never rests a
passive order), so the realistic engine feed for this lane is QuoteTicks
only -- `run_one` does not build or add `TradeTick`s to the engine at all.
Trade ticks are still fetched, normalized and written to the private
`ParquetDataCatalog` (see fetcher.py) for future passive-order work, where
queue position against real trade prints would matter; they are simply never
replayed into *this* engine. Measured after the fix: **0 of 26,145** (elite)
and **0 of 5,255** (paper) exerciser fills beat the NBBO touch in force at
fill time (`fill_vs_nbbo_touch.violation_count`, asserted by `cmd_run`). The
builder additionally ran the independent reviewer's own harness (`analyze.py`)
against this code as a cross-check before commit; the reviewer separately
verifies independently. See "Quotes-only vs with-trades" below for the
side-by-side comparison.

**`queue_position` and `trade_execution` have no measured effect in this
setup.** With trade ticks excluded and every order an all-or-nothing IOC,
turning `queue_position` or `trade_execution` off independently was measured
to produce byte-identical results to leaving them on (the reviewer's
`analyze.py elite_no_queue_position` / `elite_no_trade_execution` variants
against `elite_base`). Both are still left on in `run_one`'s `add_venue` call
(a plain, harmless default), but they are not claimed as active realism
features of this lane -- only `liquidity_consumption` was measured to change
results (it governs whether a fill can actually deplete the available
displayed size within a tick).

## What this measures

A NautilusTrader 2.0.0rc5 `BacktestEngine` fed with real Alpaca SIP quotes
(and, separately, trades -- see H1) for SPY, QQQ, IWM, AAPL, MSFT, NVDA, AMD
and TSLA over `2026-09-24T14:00:00Z`-`14:30:00Z` (30 minutes of the regular
session, avoiding the open), under two venue/risk profiles, a
`StaticLatencyModel`, and a cited US-equity fee model (`fee_model.py`).

- **paper-parity**: `RiskEngineConfig(max_order_submit_rate="180/00:01:00")`,
  mirroring Alpaca's 200 req/min x 0.9. Fills cannot exceed 180/min here by
  construction of the limiter; that is the expected, reported result, not a
  failure. Cadence: 5 submits/sec (300/min attempted) against the 180/min
  budget, so the limiter binds and denials are counted.
- **elite-tier**: `max_order_submit_rate="900/00:01:00"`, the Alpaca Elite /
  non-retail rate (1000 req/min x 0.9). This is the profile that must sustain
  >=180 fills/min in every full simulated minute, and does. Cadence:
  1000/60 ~= 16.67 submits/sec (~1000/min attempted) against the 900/min
  budget -- **not** exactly 15/s (900/min): an earlier cadence of exactly
  900/min attempted never triggered a single denial, since it never actually
  exceeded the budget, which would let a non-binding limiter be misread as
  "sustained 900/min of real capacity" rather than "we never asked for more
  than the budget." Denials are now measured (2,995 in the current run).

## Data

`fetcher.py` fetches Alpaca SIP `/v2/stocks/quotes` and `/v2/stocks/trades`
(`feed=sip`, `limit=10000`, paginated via `next_page_token`) for the 8 symbols,
reusing `sim-paper-compare/replay_compare.py`'s `PageFetcher` (gzip pages plus
a sha256 `ledger.jsonl` under a private cache) and
`adaptive-paper/runner.py`'s `credentials()` loader. Credentials are resolved
in-process via `credential_status.expand_template` on the `alpaca-paper`
inventory entry's `store.path_template` (the same resolution
`tools/credentials/alpaca_rate_limit_probe.py.paper_store_file` uses) --
never read, printed or grepped from a shell.

The actual fetch window is padded 5 minutes past the reported/analysis window
(`14:30:00Z` -> `14:35:00Z`, `FETCH_END_ISO` in `fetcher.py`) purely so the
exerciser's end-of-window flatten has quotes to execute its close orders
against and the shared rate-limit budget has room to refill first, without
eating into the 30 reported minutes' own submit schedule. **The receipt's
`quote_counts`/`trade_counts` exclude this pad** (`_window_bounded_counts` in
runner.py) -- they describe only the 30-minute analysis window, not the
35-minute fetch.

Pages are cached under `~/.local/state/native-agent-stack/sim-capacity/pages`
(0700), never committed. `--replay` reuses only retained pages: no network
request, and the credential loader is never even imported (see
`tests.test_sim_capacity.ReplayNeverOpensCredentialsTests`). The receipt
records exactly this run's served pages (`this_run_page_hashes`, from
`PageFetcher.page_events`) and a digest of that list, separately from the
private cache directory's whole cumulative `ledger.jsonl` (which can carry
pages from earlier, unrelated fetches against the same cache directory --
201 pages served this run, out of 372 cumulative in the ledger at the time
of writing).

Crossed quotes (`bid > ask`) are dropped and counted per symbol
(`fetcher.normalize_quotes`); locked quotes (`bid == ask`) are kept. A
NautilusTrader `ParquetDataCatalog` is written under the private catalog dir
(`fetcher.build_catalog`) from the fetched quotes and trades. **This catalog
is not read back by the engine run** -- `run_one` reads quotes (and, for the
catalog only, trades) from the private normalized JSON directly, for exact
control over tick construction and the H1 quotes-only exclusion. A future
`BacktestNode`-based run could read from the catalog directly; this lane does
not currently do so, and does not claim to.

## Exerciser mechanics

- Buy orders: limit = ask + $0.01; sell orders: limit = bid - $0.01 (both IOC),
  quantity 1-5 shares, capped by displayed top-of-book size.
- **Side selection is inventory-aware** (`schedule.RoundRobin.next_side`): it
  never proposes a sell from a flat or short position (always BUY when
  `position <= 0`), and a sell's quantity is additionally clamped to the
  currently held long in `exerciser.py`. This exists because the exerciser
  trades a plain Alpaca **CASH account**, which rejects any short sale
  outright. Measured *before* this fix: 162 of 163 elite rejects and 112 of
  113 paper rejects in one run were exactly "Short selling not permitted on a
  CASH account" -- consuming rate-limit budget, understating true throughput,
  and driving spurious position-cap skips (a prior 20-share cap, and even the
  current 300-share cap under the old alternation logic, could still walk
  into a long-only drift with no way back down). Measured *after* the fix:
  zero short-sale rejects in either profile.
- A hard per-symbol position cap (300 shares; see `runner.POSITION_CAP`'s
  comment for why a tighter cap was tried and rejected) forces a SELL once
  reached, alongside the inventory-aware BUY-when-flat rule above -- together
  these keep the exerciser's own bookkeeping from ever being the bottleneck.
- At the end of the analysis window the exerciser flattens every open
  position with several spaced retry attempts (a single flatten attempt can
  transiently fail per-instrument -- measured directly as an `OrderRejected`
  "No market for `<symbol>`" when a close order is processed at an instant
  with no fresh book update yet for that instrument -- with no automatic
  retry otherwise).
- Counts submits, fills (`OrderFilled` events), IOC expiries (auto-canceled/
  expired with nothing filled) separately from partial-fill-then-canceled
  orders (`ioc_partial_then_canceled`, checked against the order's own
  `filled_qty` at cancel/expiry time), rejects and RATE_LIMIT denials
  (`OrderDenied`, the RiskEngine's pre-trade rate-limit refusal, distinct from
  a venue-side `OrderRejected`; the reason string is checked before counting a
  denial as rate-limit, in case a future added risk check ever fires here
  too).

## Fee model

`fee_model.py` charges, per fill:

- **FINRA CAT**: $0.000003 per executed-equivalent share, on **both buys and
  sells**.
- On **sells only**: SEC Section 31 ($20.60 per $1,000,000 of proceeds,
  effective 2026-04-04) and FINRA TAF ($0.000195/share, capped at $9.79/trade,
  in force through 2026-09-30 -- covers the session date).
- **Elite Smart Router commission** (elite-tier profile only, both sides):
  the `all_in` plan by default, a flat $0.0040/share at every monthly-volume
  tier (Alpaca's fee schedule lists one all-in rate across all five listed
  volume rows; only the `cost_plus` rate is actually tiered). The `cost_plus`
  plan ($0.0025/share at this lane's -- lowest -- volume tier) is also
  implemented but not the default, since it additionally passes through
  actual per-venue exchange fees/rebates that this model does not have data
  for (**partial**, not modeled). paper-parity always uses
  `commission_plan="none"` (retail routing: $0 commission, CAT/SEC/TAF only).

Sources:

- SEC Section 31 / FINRA TAF: pinned, dated
  `blueprints/us-equities/mover-v3/data/fees-v3.json` (retrieved_at
  2026-09-24; SEC Release No. 34-104909, corrected by 34-104909A; SEC Fee
  Rate Advisory for FY2026, 2026-02-27).
- FINRA CAT and the Elite Smart Router commission: Alpaca Securities LLC's
  own [Brokerage Fee Schedule PDF](https://alpaca.markets/disclosures)
  (`https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf`),
  "Revised on September 17, 2026", retrieved 2026-09-25, sha256
  `7bc75e3cd86f5c1950f8ce1292049965280340a3cebe727ca7aee4a7d2d71b12`.
- **TAF cap scope is settled for this exerciser**: per **execution**, not per
  order (FINRA TAF FAQ [A200.17](https://www.finra.org/rules-guidance/guidance/faqs/trading-activity-fee),
  verbatim: a member "may choose to calculate the Trading Activity Fee on
  either the individual street side executions or on the account level
  average price confirmation" -- its own example bills a 1,000,000-share
  order filled as ten 100,000-share executions as "ten sales at $5" under the
  street-side-execution method (vs. "one sale at $5" under the account-level
  method; A200.17 is specifically about average-price-allocated orders and
  requires the chosen method be applied consistently). This exerciser does
  no average-price allocation, so the street-side-execution method applies,
  and per-fill -- what this model already does -- is the settled, sourced
  behavior for this case, not a conservative guess.

**Partial**: the `cost_plus` commission plan excludes its exchange-fee/rebate
pass-through component (not modeled).

**Rounding.** Alpaca aggregates each fee type per day, per account, and
rounds the day's total **up** to the cent. This model instead rounds each
fill's total fee **half-up**. `runner.alpaca_rounding_delta` recomputes both
totals directly from a run's actual fills and reports the measured
difference in that run's receipt (`runs[].fee_rounding`) -- not a fixed
dollar claim here, since it depends on the run's actual fill counts/sizes.
Measured on the current committed receipts: elite-tier model total is
$4.19 lower than Alpaca's aggregate-then-round-up method; paper-parity is
$0.88 lower.

## Latency -- a primary reference point, not a calibration

`PRIMARY_LATENCY_MS = 70` is **not calibrated**. It is a primary-reference
point chosen near the retained sim-to-paper receipt's own latency-sensitivity
flip point (~69.2ms) -- it sits **far below** that receipt's observed paper
submit-to-fill range (0.65-1.09s), not inside it. Of this lane's own
0/70/250/1000ms sweep points, 1000ms is the closest to that observed range.
That receipt explicitly says of its own sweep, "Sensitivity check, not a
calibration" (`sim-paper-compare/receipts/20260923g-main-passed.json`). This
lane inherits that caveat rather than upgrading it to "calibrated."

**Exact-latency release (default since 2026-09-25).** On the pinned rc5
engine, a deferred (latency-delayed) order is released at the first of:
(a) the next quote tick on its own instrument, or (b) **any** due clock
timer processed by the engine, from any source (see
`sim-paper-compare/replay_compare.py`'s module docstring for the underlying
source citations) -- not exactly at submit + latency. The exerciser's own
submit-schedule timer fires frequently, so it is very often *itself* the
timer that releases a deferred fill, mixing the configured
`StaticLatencyModel` delay together with the exerciser's own tick cadence.
Measured directly (isolated in `sim-engine-crosscheck`, on a shared
deterministic order stream, so it is not itself confounded by this
exerciser's own tick cadence): extra delay of **median 28ms (SPY) / 53ms
(NVDA), p90 135ms/263ms** -- see
`sim-engine-crosscheck/README.md`'s "A real, minor, separate NautilusTrader
finding" and `run_nautilus.py`'s `exact_latency` docstring.

**The fix, applied here as the default**: `CapacityExerciserParams.
release_alert_latency_ns` (`exerciser.py`), wired from `runner.run_one`'s
`exact_release` parameter (default `True`) using the same nanosecond value
given to `StaticLatencyModel`. It registers one additional, otherwise-inert
`self.clock.set_time_alert_ns(...)` per order, at exactly
`submit_ts + release_alert_latency_ns`, with a no-op callback that touches
no order state -- this forces every latency-delayed order to resolve at
EXACTLY submit + latency. Measured on the committed 2026-09-25 receipts
(`submit_to_fill_latency_ms` in each run): min/p50/p90/max are all exactly
**70.0ms** for both profiles at the 70ms primary latency, and
`release_timing.check` (asserted by `cmd_run`, not just reported) shows zero
early violations and zero inexact violations across every profile and every
latency-sweep point. This is the same mechanism, and the same measured
effect, as `sim-engine-crosscheck/run_nautilus.py`'s `exact_latency=True`
variant (median time-to-fill exactly 70.00ms/250.00ms there too).

**Legacy mode is still available**, for comparison or reproduction of the
pre-fix numbers: `runner.py run --release-timing legacy` (or
`run_one(..., exact_release=False)`), which sets
`release_alert_latency_ns=0` and reproduces the release-on-next-event
behavior described above. On this lane's own real-data fills prior to the
fix (previous committed receipts, superseded 2026-09-25 -- see
`receipts/20260924-elite-tier-superseded.json` /
`receipts/20260924-paper-parity-superseded.json`): elite-tier fills
clustered at p50=120ms, p90=120ms (min 70.0ms, max 120ms) at a ~60ms tick
interval and 70ms configured latency -- consistent with "release at the
first tick at or after submit + latency," which lands most fills at the
*second* tick after submit; paper-parity (200ms tick interval) showed
p50=138.6ms, p90=200ms (min 70.0ms, max 200ms). Legacy mode's own
`tests.test_sim_capacity.ExactReleaseTimingTests.
test_legacy_release_resolves_some_fills_later_than_exact` reproduces this
behavior directly against a small, sparse, synthetic quote set (never before
submit + latency, but not always exactly at it either). The latency sweep
(0/70/250/1000ms) below uses the default exact-release mode, so it varies
configured latency alone; under legacy mode it would still vary configured
latency together with the timer-cadence effect above.

## Independent recount and the NBBO-touch check

`runner.summarize_run` recounts fills per minute from NautilusTrader's own
`generate_fills_report()`, separately from the strategy's own counters, and
**`cmd_run` asserts they are equal** for every profile and every latency-sweep
point (an unhandled `AssertionError` is the intended failure mode if this
ever regresses -- this is a real `assert`, not just a reported boolean).
Extracting timestamps required a fix documented in `runner.dataframe_to_rows`:
`DataFrame.to_json(date_format='epoch')` on a tz-aware `datetime64[ns, UTC]`
column is a plain units mismatch (it reports epoch **milliseconds**, not
nanoseconds -- verified directly: 1,800,000,500,000,000 ns serializes as
`1800000500`, which is exactly `true_ns // 1_000_000`). `dataframe_to_rows`
instead forces `datetime64[ns, ...]` precision before extracting the integer
(so a `datetime64[us, UTC]` source column, which a raw `.astype("int64")`
would report as microseconds, cannot silently slip through as ns either),
and this is unit-tested directly for both cases.

`runner.check_no_fill_beats_nbbo_touch` independently re-derives, for every
exerciser fill, the NBBO touch in force **at fill time** (not submit time,
not modeled-arrival time -- the engine's own actual matching instant), using
only the retained normalized quote rows, never the engine's internal book
state, and asserts no fill is strictly better than the touch. This is the H1
guard: 0 violations in both profiles after the fix (see above).

## Results (2026-09-25 rerun, real Alpaca SIP data cache, exact-release default)

Re-run 2026-09-25 from the same retained, cached Alpaca SIP pages (`--replay`,
no network fetch) after making exact-latency release the default; numbers
shifted slightly from the 2026-09-24 fetch because release timing now changes
which fills actually land inside vs. outside a given simulated minute and
which orders see liquidity already consumed by an earlier order -- not
because of new or different market data. The prior (legacy-timing) receipts
are kept, unmodified, as superseded evidence -- see "Superseded receipts"
below.

| Profile | min/min | median/min | max/min | full minutes >=180 | sim cost/min (USD) | wall-clock | recount |
|---|---|---|---|---|---|---|---|
| paper-parity (70ms) | 170 | 176.0 | 180 | 2/30 (by design: capped by the 180/min limiter) | ~46.10 | ~2.8s | agrees |
| elite-tier (70ms, primary) | 866 | 873.0 | 884 | **30/30** | ~245.76 | ~5.3s | agrees |

Latency sensitivity (elite-tier, full 30-min run at each latency, exact
release). **This table is sourced from `receipts/20260925-elite-tier.json`'s
`latency_sensitivity_elite_tier`** -- read the numbers from that file when
regenerating this table, rather than retyping them, so it cannot silently
drift from the committed receipt (a stale copy of this exact table was
caught by review once already); `tests.test_sim_capacity`'s
`test_readme_latency_sweep_table_matches_receipt` asserts the two agree:

| latency (ms) | min/min | median/min | max/min | full minutes >=180 |
|---|---|---|---|---|
| 0 | 889 | 898.5 | 900 | 30/30 |
| 70 (primary) | 866 | 873.0 | 884 | 30/30 |
| 250 | 807 | 830.0 | 854 | 30/30 |
| 1000 | 672 | 727.5 | 761 | 30/30 |

At every nonzero latency point, `release_timing.check` confirms zero early
violations (no fill before submit + latency) and zero inexact violations (no
fill after submit + latency either -- every fill is at exactly submit +
latency); the 0ms row has nothing to make exact (no `StaticLatencyModel` is
even attached) and is unaffected by the release-timing default.

### Superseded receipts (legacy release timing)

`receipts/20260924-elite-tier-superseded.json` and
`receipts/20260924-paper-parity-superseded.json` are the original 2026-09-24
receipts, kept unmodified (not deleted, matching
`sim-engine-crosscheck/receipts/20260925-crosscheck-superseded.json`'s
convention) -- they were produced before the exact-release fix existed, so
their `runs[].submit_to_fill_latency_ms` mixes configured latency with the
release-on-next-event timer-cadence effect described above. They remain
valid infrastructure evidence for the legacy release mode specifically, not
a data or engine-configuration error.

### Quotes-only vs with-trades (H1 evidence)

Measured with the independent reviewer's harness (`analyze.py`), same data,
same profiles, mirroring `run_one`'s configuration:

| variant | fills/min (min/median/max) | fills beating touch | cost/min (USD) |
|---|---|---|---|
| elite, with trades | 657 / 716.5 / 832 | 8,990 / 21,924 = 41.0% | 59.09 |
| elite, **quotes-only** (this lane) | 866 / 873.0 / 884 | **0 / 26,230 = 0.0%** | 225.97 |
| paper, with trades | 138 / 154.0 / 171 | 2,072 / 4,664 = 44.4% | 11.95 |
| paper, **quotes-only** (this lane) | 170 / 176.0 / 180 | **0 / 5,278 = 0.0%** | 45.33 |

(The harness's own cost/min differs slightly from this lane's committed
receipts because it uses `commission_plan="none"` for both profiles, i.e. no
elite commission; it is included here only as H1 comparison evidence, not as
this lane's cost claim. The "quotes-only (this lane)" fills/min and
touch-check columns are re-read from the 2026-09-25 exact-release receipts;
the independent reviewer's own with-trades harness run is unaffected by this
lane's release-timing default and is not re-run here.)

Both profiles flatten fully at the end (`flat_at_end: true`), and net P&L is
negative in both -- expected, since the exerciser pays the spread (collar) on
every round trip plus fees with no offsetting signal. See
`receipts/20260925-paper-parity.json` and `receipts/20260925-elite-tier.json`
for full per-minute breakdowns, page hashes, engine/runtime versions, the
redacted argv and the `release_timing`/`release_timing_mode` fields; see
"Superseded receipts" above for the prior legacy-timing versions.

## Limitations

**Undocumented rc5 liquidity-consumption behavior: a price level's consumed
tally is not reset by an identical repeated quote.** On the pinned engine, a
book level's consumed-quantity tally under `liquidity_consumption=True` is
reset only when that price's *displayed size actually changes*
(`matching_engine/mod.rs:371-375`); it is otherwise cleared only on an
explicit book reset or an instrument precision change
(`matching_engine/mod.rs:297-298,1338-1339`). Two SIP quotes for the same
symbol that happen to repeat the exact same (price, size) pair -- not
uncommon in real market data during a quiet moment -- therefore do **not**
replenish liquidity at that price between them, even though each is a fresh,
independent quote. A taker order that would otherwise be marketable can
expire unfilled purely because an earlier order already consumed that
price's displayed size at an earlier, identically-priced-and-sized quote.

Measured directly on the committed elite-tier@70ms receipt
(`runner.stale_tally`-style attribution, cross-checked with the independent
reviewer's `final_check.py`): of 855 IOC expiries, 66 (7.7% of expiries,
**~0.25% of the 26,155 total fills**) are marketable-at-cancel, have nonzero
displayed size at the quote in force, and were already consumed by an
earlier fill at that same (symbol, side, price) since that quote instance
first appeared -- i.e. exactly this stale-tally artifact. This makes the
lane's throughput and cost figures **pessimistic** (fewer fills, not more)
relative to a hypothetical engine that replenishes every fresh quote
regardless of whether its price/size repeats a prior one, so it does not
inflate the >=180 fills/min claim.

This also affects the test suite's own synthetic fixtures: an early,
naive fixture using an *identical*, unchanging (price, size) quote every
tick fell into this depletion lock almost immediately (4 fills, then 95-99%
of subsequent orders expired for the rest of the run) -- every
`RealVenueRunOneTests` behavioral assertion would otherwise have rested on
just those first 4 fills. The shared fixture now varies size tick-to-tick
(so no two consecutive quotes at a given price ever share the same
displayed size), which lets liquidity keep replenishing and gives each test
a meaningful, healthy fill count instead.

## Convergence record

`experiment.json` (validated with `python3 scripts/validate_convergence.py
blueprints/us-equities/sim-capacity/experiment.json`) records the selected
NautilusTrader 2.0.0rc5 destination against the alternatives the coordinator
researched (hftbacktest as a next-phase cross-check; Lean, vectorbt,
vectorbt.pro, ABIDES, mbt_gym, backtrader, zipline-reloaded, hummingbot,
freqtrade and MarS rejected, with reasons) and the overturn conditions that
would change that selection.

## Running it

```
# Real fetch (once; read-only, never touches order placement):
python3 blueprints/us-equities/sim-capacity/runner.py fetch \
    --pages ~/.local/state/native-agent-stack/sim-capacity/pages \
    --catalog ~/.local/state/native-agent-stack/sim-capacity/catalog

# Both profiles, latency sweep and recount (exact-release default):
python3 blueprints/us-equities/sim-capacity/runner.py run \
    --catalog ~/.local/state/native-agent-stack/sim-capacity/catalog \
    --receipt blueprints/us-equities/sim-capacity/receipts/20260925-paper-parity.json \
    --profile paper-parity
python3 blueprints/us-equities/sim-capacity/runner.py run \
    --catalog ~/.local/state/native-agent-stack/sim-capacity/catalog \
    --receipt blueprints/us-equities/sim-capacity/receipts/20260925-elite-tier.json \
    --profile elite-tier

# Same, but reproducing the pre-fix release-on-next-event timing (legacy;
# see the Latency section above):
python3 blueprints/us-equities/sim-capacity/runner.py run \
    --catalog ~/.local/state/native-agent-stack/sim-capacity/catalog \
    --receipt PRIVATE/legacy-elite-tier.json \
    --profile elite-tier --release-timing legacy

# Replay from retained pages only (no network, no credential file opened):
python3 blueprints/us-equities/sim-capacity/runner.py fetch --replay \
    --pages ~/.local/state/native-agent-stack/sim-capacity/pages \
    --catalog ~/.local/state/native-agent-stack/sim-capacity/catalog
```

Tests: `python3 -m unittest -v tests.test_sim_capacity`. Nautilus-requiring
tests (`PinnedRuntimeEngineTests`, `RealVenueRunOneTests`,
`ExactReleaseTimingTests`) and the pandas-requiring datetime-recovery tests
skip cleanly on system Python and run on the pinned runtime
(`~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python`).
`RealVenueRunOneTests` calls `runner.run_one` directly (the real production
function, with its real venue/risk/fee configuration) on a small synthetic
quote set, and asserts: fill qty never exceeds displayed size; fill timestamp
never precedes submit + latency; no fill beats the NBBO touch; fees land on
sells only at `commission_plan="none"`; the independent recount agrees; every
exerciser order's actual time-in-force is IOC; and the configured budget
values match. `ExactReleaseTimingTests` calls `runner.run_one` on its own
deliberately sparse synthetic quote set and asserts the release-timing fix
directly: with the (default) exact-release mode, every fill resolves at
EXACTLY submit + latency; with legacy mode on the same fixture, fills never
precede submit + latency but at least one resolves strictly later --
reproducing, at unit-test scale, the slack measured in `sim-engine-crosscheck`.
