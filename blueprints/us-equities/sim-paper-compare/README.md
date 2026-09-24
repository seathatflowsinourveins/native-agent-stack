# Simulated vs. paper fill comparison (trading-lane audit gap #7)

Simulated fills and paper fills had never been compared. `mover-early-entry/paper_compare.py`
exists but has never produced a retained output for this comparison, and the
`adaptive-paper` trials had no replay diff. [`replay_compare.py`](replay_compare.py)
closes that gap for one retained broker-order trial: it replays the trial's exact
order decisions (symbol, side, qty, order type, limit price, timestamps) through
NautilusTrader **2.0.0rc5**'s `BacktestEngine`, fed with historical Alpaca SIP
quotes for the trial window, and compares the replay's fills against the trial's
real paper fills.

## Scope: what this can and cannot show

This is **one retained trial with five order decisions** (four filled, one
canceled) -- [`adaptive-paper/trials/20260923g-main-passed`](../adaptive-paper/trials/20260923g-main-passed/README.md).
It measures how often, and by how much, a deterministic quote-driven replay
agrees with what the paper broker actually did in that one 5-minute window. It
is **an agreement measurement, not a fill-rate or slippage calibration**: five
orders on two symbols in one session say nothing about another trial, another
symbol, another session or another market regime, and no statistical
significance is claimed for the aggregates below.

[The retained receipt](receipts/20260923g-main-passed.json) is the record of the
one run performed for this gap; its inputs, data provenance, engine
configuration and results are described here. It was not re-run against a
second data pull, so it does not itself demonstrate reproducibility across
requests -- only the frozen SHA256 page ledger it cites does that (replay from
the same pages via `--replay` is deterministic, since matching only reads
already-validated market data).

## Results (from the retained receipt)

| Order | Symbol | Side | Paper | Sim | Agree | Price delta (bps) | Time delta (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `…0000001` | INTC | BUY | filled @120.57 | filled @120.57 | yes | 0.00 | -0.67 |
| `…0000002` | INTC | SELL | filled @120.55 | filled @120.54 | yes | -0.83 | -0.82 |
| `…0000003` | GOOGL | BUY | filled @338.61 | filled @338.62 | yes | +0.30 | -0.84 |
| `…0000004` | GOOGL | SELL | **canceled** | filled @338.44 | **no** | n/a | n/a |
| `…0000005` | GOOGL | SELL | filled @338.35 | **no fill** | **no** | n/a | n/a |

Aggregates: 5 orders, **3/5 fill agreement (60%)**, 3 orders filled in both;
mean absolute fill-price delta **0.375 bps** (median 0.295, max 0.83 bps); mean
absolute fill-time delta **0.78 s** (median 0.82, max 0.84 s; the replay fills
consistently *before* the paper broker in this sample, since it matches the
instant real SIP quotes cross the limit, with no broker/network latency
modeled).

Both disagreements come from the same cancel/replace pair and share one cause,
documented below: the replay does not know the paper trial's actual cancel
timestamp for order `…0000004`, so it holds that order open longer than the
paper trial did. Real SIP quotes crossed its limit (338.42) at 16:51:06.696Z,
before the declared cancel point, so the replay filled it -- consuming the
simulated GOOGL position -- and then correctly rejected the oversell on order
`…0000005` as a `CASH`-account short, while the paper broker (which had
genuinely canceled `…0000004`) filled `…0000005` normally. This is a real,
explainable effect of the cancel-timing gap in the input data, not a defect in
the matching logic: the three orders with unambiguous paper timestamps for
every recorded event (submit and fill) all agree, at sub-bp price differences
and sub-second time differences.

## Reuse and methodology

- **Fee/fill model**: the replay uses the exact baseline configuration accepted
  in [`engine-nautilus/equity-replay`](../engine-nautilus/equity-replay/README.md)
  ("zero fees and the native default fill model"): `FixedFeeModel(Money(0, "USD"))`
  (Alpaca equities are commission-free) and the native, unconfigured
  `nautilus_trader.execution.FillModel()` -- no synthetic slippage or partial-fill
  draw is injected. `book_type=L1_MBP` lets the engine's native matcher fill
  limit orders directly against the fed top-of-book quotes, which is the
  documented mechanism (see [equity-replay's fee/fill model source review](../engine-nautilus/equity-replay/README.md#source-choice-and-review))
  rather than a second, custom order matcher.
- **Cost sensitivity**: [`execution-realism`](../execution-realism/README.md)'s
  LEAN fee/slippage sensitivity receipt is the other existing fill-model
  evidence in the repo; it is a different engine (LEAN, not Nautilus) exercising
  market orders on a five-day SPY schedule, so it is cited here for its
  documented execution-boundary language (no partial fills, no queue position,
  no latency/impact model), which applies equally to this replay and is
  restated below, not reused as configuration.
- **Data fetch**: GET-only against the existing Alpaca historical data path
  (`/v2/stocks/quotes`, `feed=sip`), using `adaptive-paper/runner.py`'s
  `credentials()` loader (fails closed on env-file permissions/location) and a
  page-retention/replay fetcher adapted from `mover-early-entry/mover_scan.py`'s
  `Fetcher` (reimplemented locally as `PageFetcher` to avoid pulling that
  module's numpy/rules/sessions_io dependency chain into the pinned
  Nautilus-only runtime; behavior is identical: every response kept gzip'd with
  a sha256 ledger under `--pages`, and `--replay` re-derives the run from those
  pages with no network access).
- **Order replay**: `broker-orders.json`'s read-only order readback (symbol,
  side, qty, `limit` type, limit price, `submitted_at`/`filled_at`) is replayed
  as `Strategy.submit_order`/`cancel_order` calls at the exact recorded
  timestamps, with the paper trial's own `client_order_id`s preserved end to end
  so every simulated report row maps back to a specific paper order.

## Known gaps and declared limitations

- **Cancel timestamp**: `broker-orders.json` records a canceled order's
  `submitted_at` but not when Alpaca actually canceled it. `build_decisions()`
  cancels the simulated order 1 ns before the next same-symbol/same-side
  order's submit timestamp -- the latest point by which the trial is known to
  have superseded it -- and this single approximation accounts for both
  disagreements in this run (see above).
- **Unlimited liquidity, no latency/impact**: matching against L1 top-of-book
  quotes assumes full depth at the quoted price/size and no network or
  exchange latency; this is the same boundary `execution-realism` and
  `equity-replay` declare for their fill models, and it applies here too. No
  partial fills, queue position, spread dynamics beyond L1, halts or auction
  behavior are modeled.
- **Five orders, one trial**: this run cannot estimate a fill rate, size a
  slippage distribution or detect regime dependence. A calibration would need
  many trials across sessions, symbols and regimes with independently recorded
  cancel timestamps.
- **This receipt used a single fetch**: it was not independently re-pulled to
  check for revision; the SHA256 page ledger is the retained evidence of what
  was returned, not a claim that the SIP vendor never revises historical
  quotes.

## Reproduce

Requires the pinned runtime (`nautilus-trader==2.0.0rc5`, `alpaca-py==0.44.0`)
and a private paper-credential env file (`docs/secret-storage.md`):

```sh
python3 blueprints/us-equities/sim-paper-compare/replay_compare.py \
  --trial blueprints/us-equities/adaptive-paper/trials/20260923g-main-passed \
  --env-file "$PAPER_ENV_FILE" \
  --pages "$PRIVATE_CACHE_DIR/pages" \
  --out "$PRIVATE_CACHE_DIR/run" \
  --receipt blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json
```

Add `--replay` to re-derive the same run from already-retained pages with no
network request (used to reproduce [the retained receipt](receipts/20260923g-main-passed.json)
above). `--pages` and `--out` must be private paths outside the repository
(e.g. under `~/.local/state/native-agent-stack/sim-paper/`); only the receipt's
hashes and results are committed, never the fetched SIP quote pages or engine
report CSVs.

```sh
python3 -m unittest tests.test_sim_paper_compare -v
```

Seventeen focused offline tests exercise timestamp parsing, paper-order
normalization, decision building (including the cancel-timing approximation),
the fetch window, quote-row filtering and the comparison/aggregation logic,
all against synthetic fixtures and the retained trial's real
`broker-orders.json`. They do not exercise `run_replay` (which requires the
pinned Nautilus runtime and real market data) or the CLI's `main`; those paths
were exercised manually against a synthetic-quote smoke fixture and then
against the real retained receipt above, and are local integration checks, not
unchanged upstream tests.
