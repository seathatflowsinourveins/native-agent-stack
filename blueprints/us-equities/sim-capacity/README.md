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
- `blueprints/us-equities/adaptive-paper/README.md` L40: "No strategy
  manufactures trades to hit a throughput target."
- `blueprints/us-equities/mover-v3/README.md` (~L294-374) and
  `catalogs/us-equities/mover-v3-sweep-20260924.json` (~L255): throughput is
  capacity, not a trading target, and high rates are cost-bound; "a high-rate
  capacity replay is an infrastructure test, never strategy evidence."

## What this measures

A NautilusTrader 2.0.0rc5 `BacktestEngine` fed with real Alpaca SIP quotes and
trades for SPY, QQQ, IWM, AAPL, MSFT, NVDA, AMD and TSLA over
`2026-09-24T14:00:00Z`-`14:30:00Z` (30 minutes of the regular session,
avoiding the open), under two venue/risk profiles that both keep
`trade_execution`, `liquidity_consumption` and `queue_position` on, a
`StaticLatencyModel` calibrated from the retained sim-to-paper receipt
(`blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json`:
the order-4 flip is at ~69.2ms, and paper submit-to-fill intervals were
0.65-1.09s -- the 70ms primary latency sits inside that observed flip/fill
range), and a cited US-equity sell-side fee model (`fee_model.py`).

- **paper-parity**: `RiskEngineConfig(max_order_submit_rate="180/00:01:00")`,
  mirroring Alpaca's 200 req/min x 0.9. Fills cannot exceed 180/min here by
  construction of the limiter; that is the expected, reported result, not a
  failure.
- **elite-tier**: `max_order_submit_rate="900/00:01:00")`, the Alpaca Elite /
  non-retail rate (1000 req/min x 0.9). This is the profile that must sustain
  >=180 fills/min in every full simulated minute, and does (see Results).

Exerciser cadence is set per profile so the native limiter is actually
exercised: 5 submits/sec (300/min attempted) for paper-parity against its
180/min budget, and 15 submits/sec (900/min attempted) for elite-tier against
its 900/min budget.

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
eating into the 30 reported minutes' own submit schedule. Every reported
number (`window`, per-minute stats) still covers only the original 30 minutes.

Pages are cached under `~/.local/state/native-agent-stack/sim-capacity/pages`
(0700), never committed. `--replay` reuses only retained pages: no network
request, and the credential loader is never even imported (see
`tests.test_sim_capacity.ReplayNeverOpensCredentialsTests`).

Alpaca's historical trade record carries **no aggressor-side field**. Every
`TradeTick` built from it is tagged `AggressorSide.NO_AGGRESSOR`
(`fetcher.normalize_trades`). Consequence: a queue-depletion model that relies
on aggressor side to remove resting liquidity from a known side of the book
never actually does so from this trade data, which makes any queue-position-
based fill estimate derived from these trade ticks **optimistic**.

Crossed quotes (`bid > ask`) are dropped and counted per symbol
(`fetcher.normalize_quotes`); locked quotes (`bid == ask`) are kept. A
NautilusTrader `ParquetDataCatalog` is written under the private catalog dir
(`fetcher.build_catalog`); the runner also keeps normalized quote/trade rows
privately for the engine run, never committed.

## Exerciser mechanics

- Buy orders: limit = ask + $0.01; sell orders: limit = bid - $0.01 (both IOC),
  quantity 1-5 shares, capped by displayed top-of-book size.
- Sides alternate per symbol (`schedule.RoundRobin`) so inventory stays near
  flat, under a hard per-symbol position cap (300 shares -- a tighter 20-share
  cap was tried and measured to throttle the exerciser on its own inventory
  bookkeeping rather than on the rate limiter or the market data, which would
  misattribute a scheduling artifact as the venue's throughput ceiling; see
  `runner.py`'s `POSITION_CAP` comment).
- At the end of the analysis window the exerciser flattens every open
  position with several spaced retry attempts (a single flatten attempt can
  transiently fail per-instrument -- measured directly as an `OrderRejected`
  "No market for `<symbol>`" when a close order is processed at an instant
  with no fresh book update yet for that instrument -- with no automatic
  retry otherwise).
- Counts submits, fills (`OrderFilled` events), IOC expiries (auto-canceled/
  expired unfilled IOC remainder), rejects and RATE_LIMIT denials
  (`OrderDenied`, the RiskEngine's pre-trade rate-limit refusal, distinct from
  a venue-side `OrderRejected`).

## Fee model

`fee_model.py`: Alpaca commission $0 (documented, no commission schedule),
plus on **sells only**:

- SEC Section 31: $20.60 per $1,000,000 of proceeds, effective 2026-04-04,
  open-ended at retrieval (SEC Release No. 34-104909, corrected by
  34-104909A; SEC Fee Rate Advisory for FY2026, 2026-02-27).
- FINRA TAF: $0.000195/share sold, capped at $9.79/trade, in force
  2026-01-01 through 2026-09-30 (covers the 2026-09-24 session date).

Both rates are cited from the pinned, dated, primary-sourced
`blueprints/us-equities/mover-v3/data/fees-v3.json` (retrieved_at
2026-09-24), not re-derived. **UNVERIFIED**: whether the FINRA TAF cap applies
per order or per execution/fill; this model applies it per fill (documented
in `fee_model.py`'s module docstring as the conservative choice for a
high-fill-rate run).

## Independent recount and naive L1 check

`runner.summarize_run` recounts fills per minute from NautilusTrader's own
`generate_fills_report()`, separately from the strategy's own counters, and
`cmd_run` asserts they are equal for every run (`recount.agrees` in every
receipt is `true`). Extracting timestamps required a fix documented in
`runner.dataframe_to_rows`'s docstring: `DataFrame.to_json(date_format=
'epoch')` on a tz-aware `datetime64[ns, UTC]` column does **not** round-trip
to the true nanosecond epoch (verified directly: a `ts_event` of
1,800,000,500,000,000 ns serializes to `1800000500`, three orders of
magnitude off) -- exactly the trap `sim-paper-compare/replay_compare.py`'s
module docstring already warns about; `dataframe_to_rows` converts via
`.astype('int64')` on the raw dtype instead, and this is unit-tested directly
(`tests.test_sim_capacity.RunnerPureLogicTests.
test_dataframe_to_rows_recovers_true_ns_epoch`).

`runner.naive_l1_marketability_sample` independently re-derives, for a sample
of up to 200 fills, whether the order's actual submitted limit price was
marketable against the quote in force at its modelled arrival time (submit +
latency), using only the retained normalized quote rows -- never the engine's
internal book state. A small disagreement rate (1-2% in the observed runs) is
expected and not a bug: the market can move between submit and the modelled
arrival instant, and (per `sim-paper-compare/replay_compare.py`'s module
docstring) the engine's actual settlement instant is not guaranteed to equal
submit + latency exactly.

## Results (2026-09-24 fetch, real Alpaca SIP data)

| Profile | min/min | median/min | max/min | full minutes >=180 | sim cost/min (USD) | wall-clock | recount |
|---|---|---|---|---|---|---|---|
| paper-parity (70ms) | 133 | 153.0 | 170 | 0/30 (by design: capped by the 180/min limiter) | ~12.32 | ~5.2s | agrees |
| elite-tier (70ms, primary) | 614 | 702.5 | 812 | **30/30** | ~57.67 | ~6.5s | agrees |

Latency sensitivity (elite-tier, full 30-min run at each latency):

| latency (ms) | min/min | median/min | max/min | full minutes >=180 |
|---|---|---|---|---|
| 0 | 622 | 741.5 | 845 | 30/30 |
| 70 (primary) | 614 | 702.5 | 812 | 30/30 |
| 250 | 572 | 676.5 | 772 | 30/30 |
| 1000 | 560 | 628.0 | 694 | 30/30 |

Both profiles flatten fully at the end (`flat_at_end: true`), and net P&L is
negative in both (paper-parity ~-$431.56, elite-tier ~-$2083.23) -- expected,
since the exerciser pays the spread (collar) on every round trip plus fees
with no offsetting signal. See `receipts/20260924-paper-parity.json` and
`receipts/20260924-elite-tier.json` for full per-minute breakdowns, page
hashes, engine/runtime versions and the redacted argv.

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

# Both profiles, latency sweep and recount:
python3 blueprints/us-equities/sim-capacity/runner.py run \
    --catalog ~/.local/state/native-agent-stack/sim-capacity/catalog \
    --receipt blueprints/us-equities/sim-capacity/receipts/20260924-paper-parity.json \
    --profile paper-parity
python3 blueprints/us-equities/sim-capacity/runner.py run \
    --catalog ~/.local/state/native-agent-stack/sim-capacity/catalog \
    --receipt blueprints/us-equities/sim-capacity/receipts/20260924-elite-tier.json \
    --profile elite-tier

# Replay from retained pages only (no network, no credential file opened):
python3 blueprints/us-equities/sim-capacity/runner.py fetch --replay \
    --pages ~/.local/state/native-agent-stack/sim-capacity/pages \
    --catalog ~/.local/state/native-agent-stack/sim-capacity/catalog
```

Tests: `python3 -m unittest -v tests.test_sim_capacity`. Nautilus-requiring
tests (`PinnedRuntimeEngineTests`) and the pandas-requiring datetime-recovery
test skip cleanly on system Python and run on the pinned runtime
(`~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python`).
