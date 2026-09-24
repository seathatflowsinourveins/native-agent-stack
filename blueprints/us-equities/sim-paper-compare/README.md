# Simulated vs. paper fill comparison

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
agrees with what the paper broker actually did in that one 5-minute window, at
a declared latency-sensitivity sweep (see below). It is **an agreement
measurement, not a fill-rate or slippage calibration**: five orders on two
symbols in one session say nothing about another trial, another symbol,
another session or another market regime, and no statistical significance is
claimed for the aggregates below.

[The retained receipt](receipts/20260923g-main-passed.json) is the record of the
one run performed for this gap; its inputs, data provenance, engine
configuration and results are described here. It was not re-run against a
second data pull, so it does not itself demonstrate reproducibility across
requests -- only the frozen SHA256 page ledger it cites does that (replay from
the same pages via `--replay` is deterministic byte-for-byte outside of
run-local metadata such as timestamps and argv; see "Reproduce" below for how
to check this without overwriting the committed receipt).

## Results (from the retained receipt, zero-latency default)

| Order | Symbol | Side | Paper | Sim | Agree | Price delta (bps) | Time delta (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `…0000001` | INTC | BUY | filled @120.57 | filled @120.57 | yes | 0.00 | -0.67 |
| `…0000002` | INTC | SELL | filled @120.55 | filled @120.54 | yes | -0.83 | -0.82 |
| `…0000003` | GOOGL | BUY | filled @338.61 | filled @338.62 | yes | +0.30 | -0.84 |
| `…0000004` | GOOGL | SELL | **canceled** | filled @338.44 | **no** | n/a | n/a |
| `…0000005` | GOOGL | SELL | filled @338.35 | **no fill (rejected)** | **no** | n/a | n/a |

Aggregates: 5 orders, **3/5 fill agreement (60%)**, 3 orders filled in both;
mean absolute fill-price delta **0.375 bps** (median 0.295, max 0.83 bps); mean
absolute fill-time delta **0.86 s** (median 0.82, max 1.09 s; the replay
consistently applies orders *before* the paper broker's own decision-to-fill
latency shows up -- see "What the time delta actually measures" below).

### Why orders 4 and 5 disagree: instant fills, not cancel timing

The earlier version of this receipt attributed the two disagreements to not
knowing paper order `…0000004`'s actual cancel time. That attribution was
**wrong** and is withdrawn. `paper-output.json`'s own request log records the
real cancel instant directly (`{"kind":"cancel","timestamp":1790182276.7766664}`,
2026-09-23T16:51:16.777Z -- `submit + 10.06s`, matching the trial's
`order_timeout_seconds: 10` config almost exactly), and `build_decisions()` now
uses that recorded time (see `resolve_cancel_timestamps()`), not an inferred
successor-order time. Using the real recorded cancel time **still produces
3/5 agreement** -- the cancel-timing gap was never the actual cause.

The real cause is that this replay's zero-latency default lets order 4's limit
(SELL GOOGL @338.42) become marketable the instant real SIP quotes cross it,
which happens at 16:51:06.696Z -- **about 69ms after its 16:51:06.688Z submit**,
well before its 16:51:16.777Z recorded cancel. The paper broker's own
order-to-fill latency (648-1094ms across this trial's four real fills) was
enough to let Alpaca cancel the order first; the zero-latency replay is not.
That one instant fill then consumes the simulated GOOGL position, so order 5
(a second SELL) is correctly rejected by the engine as a `CASH`-account short
("Short selling not permitted on a CASH account..." -- the sim order's actual
recorded reject reason, see the receipt), while the paper broker (which had
genuinely canceled order 4 first) filled order 5 normally.

### Latency-sensitivity sweep (not a calibration)

To characterize this, rather than assert it, the replay now runs a declared
sweep of `StaticLatencyModel(base_latency_nanos=...)` settings from the
receipt's committed `latency_sensitivity_sweep`:

| Latency | Fill agreement | Both filled | Disagreeing orders | mean |Δprice| (bps) | mean |Δtime| (s) |
| --- | --- | --- | --- | --- | --- |
| 0 ms (default) | 3/5 | 3 | `…0004`, `…0005` | 0.375 | 0.863 |
| 5 ms | 3/5 | 3 | `…0004`, `…0005` | 0.375 | 0.763 |
| 50 ms | 3/5 | 3 | `…0004`, `…0005` | 0.375 | 0.725 |
| 70 ms | 5/5 | 4 | none | 0.281 | 0.644 |
| 100 ms | 5/5 | 4 | none | 0.489 | 0.631 |
| 250 ms | 5/5 | 4 | none | 0.281 | 0.457 |
| 650 ms | 5/5 | 4 | none | 0.281 | 0.066 |
| 1000 ms | 5/5 | 4 | none | 0.281 | 0.284 |

The outcome flips between 50ms and 70ms of modeled broker/network latency,
consistent with order 4's ~69ms marketable window: below that, the sim fills
order 4 before its real-world cancel would have landed; at/above it, the sim's
order 4 is still open (or already canceled) when the window closes, matching
the paper trial, and order 5 then fills in the sim too -- at the paper's own
fill price (338.35) for the 70-250ms points in this run. **This is a
sensitivity check on one order's ~69ms marketable window, not a calibrated
latency estimate** -- it does not claim Alpaca's real latency is any specific
value in this range, only that the disagreement is latency-sensitive and
concentrated at that boundary.

### What the time delta actually measures

All of this replay's simulated fills happen at order application (submission is
now scheduled with `clock.set_time_alert_ns` at the paper trial's exact
recorded timestamp, not "whenever the next quote of any symbol arrives" -- see
"Known gaps" below for what that change fixed), and the fed SIP quotes were
already crossing the limit at that instant for every filled order in this
trial. So the `fill_time_delta_s` column mostly measures the **paper broker's
own decision-to-fill latency** (648ms-1.09s across this trial's real fills),
not a property of the replay.

## Reuse and methodology

- **Fee/fill model**: the replay uses the exact baseline configuration accepted
  in [`engine-nautilus/equity-replay`](../engine-nautilus/equity-replay/README.md)
  ("zero fees and the native default fill model"): `FixedFeeModel(Money(0, "USD"))`
  (Alpaca equities are commission-free) and the native, unconfigured
  `nautilus_trader.execution.FillModel()` at the zero-latency default -- no
  synthetic slippage or partial-fill draw is injected. `book_type=L1_MBP` lets
  the engine's native matcher fill limit orders directly against the fed
  top-of-book quotes, which is the documented mechanism (see
  [equity-replay's fee/fill model source review](../engine-nautilus/equity-replay/README.md#source-choice-and-review))
  rather than a second, custom order matcher. **equity-replay's own reuse
  boundary applies here too, and more directly**: equity-replay accepted
  *market* orders on *daily bars*; this replay matches *limit* orders against
  *quote-level* NBBO data, which is a materially different matching surface --
  the reused pieces are the fee model and the "no synthetic slippage" default,
  not a claim that equity-replay already exercised this matching path.
- **Latency model**: `nautilus_trader.execution.StaticLatencyModel` is used
  only for the declared sensitivity sweep above; the primary "results" section
  and receipt aggregates are the zero-latency default (`latency_model=None`),
  consistent with `engine-nautilus/equity-replay`'s baseline case.
- **Cost sensitivity**: [`execution-realism`](../execution-realism/README.md)'s
  LEAN fee/slippage sensitivity receipt is the other existing fill-model
  evidence in the repo; it is a different engine (LEAN, not Nautilus) exercising
  market orders on a five-day SPY schedule, so it is cited here for its
  documented execution-boundary language (no partial fills, no queue position,
  no latency/impact model beyond the declared sweep above), which applies
  equally to this replay's zero-latency default and is restated below, not
  reused as configuration.
- **Data fetch**: GET-only against the existing Alpaca historical data path
  (`/v2/stocks/quotes`, `feed=sip`), using `adaptive-paper/runner.py`'s
  `credentials()` loader (fails closed on env-file permissions/location, and is
  never invoked at all in `--replay` mode -- see "Known gaps") and a
  page-retention/replay fetcher adapted from `mover-early-entry/mover_scan.py`'s
  `Fetcher` (reimplemented locally as `PageFetcher` to avoid pulling that
  module's numpy/rules/sessions_io dependency chain into the pinned
  Nautilus-only runtime; behavior is identical for a fresh fetch: every
  response kept gzip'd with a sha256 ledger under `--pages`. `--replay`
  re-derives the run from those pages with no network access, and the receipt's
  `data_provenance.page_sources` now records, per page, whether it was served
  from the network or the cache in the run that produced it -- the retained
  receipt above shows all four pages served from cache, since it was produced
  with `--replay`).
- **Order replay**: `broker-orders.json`'s read-only order readback (symbol,
  side, qty, `limit` type, limit price, `submitted_at`/`filled_at`) is replayed
  as `Strategy.submit_order`/`cancel_order` calls scheduled at the exact
  recorded timestamps via `clock.set_time_alert_ns`, with the paper trial's own
  `client_order_id`s preserved end to end so every simulated report row maps
  back to a specific paper order.

## Known gaps and declared limitations

- **Cancel timestamp**: resolved from `paper-output.json`'s own `requests` log
  (`resolve_cancel_timestamps()`) when the number of recorded cancel requests
  matches the number of canceled orders (true for this trial: one of each);
  falls back to `submitted_at + order_timeout_seconds` (the runner's own
  cancel-on-timeout rule, with `order_timeout_seconds` read from the config
  file whose sha256 matches this trial's `ingest-receipt.json`) only when no
  recorded cancel request is available. Neither branch infers a cancel time
  from a successor order.
- **Unlimited liquidity, no queue position**: matching against L1 top-of-book
  quotes assumes full depth at the quoted price/size; `liquidity_consumption`
  and `queue_position` are both explicitly set to their engine defaults
  (`False`) and recorded in the receipt's `engine` section rather than only
  described in prose. This is the same boundary `execution-realism` and
  `equity-replay` declare for their fill models, and it applies here too. No
  partial fills, spread dynamics beyond L1, halts or auction behavior are
  modeled.
- **Latency**: the zero-latency default and the declared sensitivity sweep
  (above) are the only latency treatments; neither claims to know Alpaca's
  actual paper-broker latency distribution.
- **Five orders, one trial**: this run cannot estimate a fill rate, size a
  slippage distribution or detect regime dependence. A calibration would need
  many trials across sessions, symbols and regimes with independently recorded
  cancel timestamps.
- **This receipt used a single fetch**: it was not independently re-pulled to
  check for revision; the SHA256 page ledger is the retained evidence of what
  was returned, not a claim that the SIP vendor never revises historical
  quotes.
- **Crossed quotes**: any SIP quote row with `bid > ask` is dropped before
  matching (a crossed NBBO cannot be matched sanely and would let a limit fill
  through a data artifact) and counted per symbol in the receipt's
  `data_provenance.quote_drop_counts`. Locked quotes (`bid == ask`) are valid
  market data and are kept.

## Reproduce

Requires the pinned runtime (`nautilus-trader==2.0.0rc5`) and, for a fresh
network fetch, a private paper-credential env file (`docs/secret-storage.md`).
`--replay` never opens a credential file and never sends a network request --
it only reads the retained page cache -- so `--env-file`/`--env-file-from-file`
are not required in `--replay` mode:

```sh
python3 blueprints/us-equities/sim-paper-compare/replay_compare.py \
  --trial blueprints/us-equities/adaptive-paper/trials/20260923g-main-passed \
  --pages "$PRIVATE_CACHE_DIR/pages" \
  --out "$PRIVATE_CACHE_DIR/scratch-run" \
  --replay \
  --receipt "$PRIVATE_CACHE_DIR/scratch-receipt.json"
```

`--out` must be a fresh (nonexistent or empty) private directory outside the
repository, and the run refuses to write into one that already has files in
it. **Do not point `--receipt` at the committed path to "reproduce" it** --
that overwrites the evidence you're trying to check. Instead point `--receipt`
at a scratch path (as above) and diff it against the committed receipt,
ignoring only the run-local `started_utc`/`completed_utc`/`argv`/`stdout_sha256`
fields (which necessarily differ between runs/hosts):

```sh
python3 - <<'PY'
import json
a = json.load(open("blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json"))
b = json.load(open("$PRIVATE_CACHE_DIR/scratch-receipt.json"))
for k in ("started_utc", "completed_utc", "argv", "stdout_sha256"):
    a.pop(k, None); b.pop(k, None)
print("EQUAL" if a == b else "DIFFER")
PY
```

`--pages` and `--out` must be private paths outside the repository (e.g. under
`~/.local/state/native-agent-stack/sim-paper/`); only the receipt's hashes and
results are committed, never the fetched SIP quote pages or engine report
CSVs. The report hashes in the receipt (`engine.reports.*.sha256_excluding_init_id`)
are computed over the fills/orders rows with the random per-order `init_id`
field stripped first, since `init_id` is a fresh UUID on every run and would
otherwise make the hash non-reproducible for reasons that have nothing to do
with the run's actual results.

```sh
python3 -m unittest tests.test_sim_paper_compare -v
```

The offline suite exercises timestamp parsing, paper-order normalization
(including refusing a non-DAY time-in-force and a fractional quantity),
cancel-timestamp resolution (recorded request vs. timeout fallback), decision
building, the fetch window, quote-row filtering (including crossed and locked
quotes), `PageFetcher` (replay, hash-mismatch, pagination), the comparison/
aggregation logic (including partial fills), and a receipt-consistency check
that recomputes the retained receipt's aggregates and hashes -- all against
synthetic fixtures and the retained trial's real `broker-orders.json`/
`paper-output.json`. A separate, explicitly gated class runs `run_replay` and
the CLI's `--replay` path (with no credential file) against a tiny synthetic
fixture on the pinned Nautilus runtime; it is skipped automatically when that
runtime is not the active interpreter. These are local integration checks, not
unchanged upstream tests -- see `docs/acceptance-evidence-policy.md`.
