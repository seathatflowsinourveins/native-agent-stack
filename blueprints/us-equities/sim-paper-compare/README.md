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
configuration and results are described here. **A checksum ledger identifies
retained inputs and supports deterministic replay from those same retained
pages -- it does not, by itself, demonstrate that an independent, fresh
request against the live Alpaca endpoint would return byte-identical data**;
this receipt was not independently re-pulled to check for historical-quote
revision (see "Known gaps" below). Replay from the same retained pages via
`--replay` is deterministic byte-for-byte outside of run-local metadata such
as timestamps and argv; see "Reproduce" below for how to check this without
overwriting the committed receipt.

## Results (from the retained receipt, zero-latency default)

This table is generated from [the retained receipt](receipts/20260923g-main-passed.json)'s
`results.rows` (see `tests/test_sim_paper_compare.py`'s `ReadmeReceiptConsistencyTests`,
which fails if this table stops matching the receipt):

| Order | Symbol | Side | Paper | Sim | Agree | Price delta (bps) | Time delta (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `…0000001` | INTC | BUY | filled @120.57 | filled @120.57 | yes | +0.00 | -0.68 |
| `…0000002` | INTC | SELL | filled @120.55 | filled @120.54 | yes | -0.83 | -0.82 |
| `…0000003` | GOOGL | BUY | filled @338.61 | filled @338.62 | yes | +0.30 | -1.09 |
| `…0000004` | GOOGL | SELL | **canceled** | filled @338.44 | **no** | n/a | n/a |
| `…0000005` | GOOGL | SELL | filled @338.35 | **no fill (rejected)** | **no** | n/a | n/a |

Aggregates: 5 orders, **3/5 fill agreement (60%)**, 3 orders filled in both;
mean absolute fill-price delta **0.375 bps** (median 0.295, max 0.83 bps); mean
absolute fill-time delta **0.86 s** (median 0.82, max 1.09 s -- order 3's row
above; **range across the four filled orders: 0.65-1.09s**, order 5 at
0.648s is the low end, not order 1's 0.68s -- see "What the time delta
actually measures" below for what this column is and is not evidence of).

### Why orders 4 and 5 disagree

**H1 correction (this is the second correction to this explanation; both are
recorded here rather than silently replaced).** The first receipt attributed
the disagreement to not knowing order `…0000004`'s actual cancel time. That
was wrong and was withdrawn: `paper-output.json`'s own request log records the
real cancel instant directly (`{"kind":"cancel","timestamp":1790182276.7766664}`,
2026-09-23T16:51:16.777Z -- `submit + 10.09s`, close to the trial's
`order_timeout_seconds: 10` config), `build_decisions()` uses that recorded
time (see `resolve_cancel_timestamps()`), and using it still produces 3/5
agreement -- the cancel-timing gap was never the cause.

The **second** version of this explanation (also since corrected) additionally
got the marketability direction backwards, citing "the quote crosses the limit
at submit + 69ms" as if the order only became fillable partway through its
life. It did not: order 4 (SELL GOOGL @338.42) was **already marketable at
submit** -- the NBBO bid was 338.44 (>= the limit) as far back as
16:46:37, well before the 16:51:06.688616Z submit. What changes at
submit + ~69ms is the *opposite* of what was previously written: **the order
stops being marketable.** The bid steps down through 338.43 (16:51:06.740Z),
338.42 (16:51:06.755Z) and finally to 338.41 (16:51:06.757889Z) -- the first
quote at which the order is no longer marketable, `submit + 69.273ms` by the
raw SIP quote timestamps. (`16:51:06.696Z`, cited in an earlier version of this
README as "when the quote crosses," is only `submit + 7.8ms` and was an
artifact of the previous quote-polling implementation, not a crossing point --
see "Known gaps" for the fix.)

At zero latency, the sim's order-4 submit is processed essentially immediately
(the receipt's own sim fill is at `.688616`, i.e. at submit), while that
marketable window is still open, so it fills. Enough modeled broker/network
latency delays that processing until *after* the window has closed at
`submit + ~69.2ms`, so the sim order is not filled by the time it's
canceled -- matching paper. The exact bisected boundary (see the sweep table
below) is **69.216918ms (still fills -> disagrees with paper) to 69.217529ms
(does not fill -> agrees with paper)**, close to but not identical to the raw
69.273ms quote-window boundary; the difference is a consequence of how the
pinned engine's latency model actually schedules processing (see "Latency
model semantics" below), and the bisected value, not the quote-derived one, is
the number that should be cited for "where the outcome changes."

That fill then consumes the simulated GOOGL position, so order 5 (a second
SELL) is correctly rejected by the engine as a `CASH`-account short ("Short
selling not permitted on a CASH account..." -- the sim order's actual recorded
reject reason, see the receipt), while the paper broker (which had genuinely
canceled order 4 first) filled order 5 normally. **Order 5 is not an
independent second flip** -- with order 4 removed from the replay entirely,
order 5 agrees with paper at every latency in the declared sweep (verified,
not assumed: the receipt's `latency_sensitivity_sweep.flip_bisections` entry
for order 5 carries `independent_flip: false`,
`depends_on_client_order_ids: ["...0000004"]`, and a `counterfactual_sweep`
recording order 5's own agreement, with order 4 removed, at *every* declared
sweep latency -- not just the original bracket's two endpoints, since probing
only those could misread a flip that merely *shifted* elsewhere in the sweep
as one that disappeared). There is exactly one flip in this trial (order 4);
order 5's apparent flip is a downstream consequence of it.

**This causal chain is a hypothesis consistent with the retained data, not a
demonstrated broker-side mechanism.** The paper broker's own broker
submission-to-fill interval on the four *filled* orders in this trial
(0.65-1.09s, see the results table) does not by itself show that Alpaca
processed order 4's cancel before a fill would otherwise have happened --
**no fill-vs-cancel race for order 4 was directly measured**; the recorded
cancel came 10.09s after order 4's submit, an order of magnitude longer than
any of the four measured submission-to-fill intervals, so "consistent with"
is as far as this evidence goes. Clock provenance matters here too (see
"Clock sources and provenance" below): the cancel-request timestamp itself is
host-clock, not broker-clock, so any claim about order 4's specific timing
carries that uncertainty, even though this particular receipt's outcome does
not depend on it (see below).

### Latency model semantics (read before citing exact-latency numbers)

The pinned engine (nautilus_trader==2.0.0rc5) does **not** guarantee that a
`StaticLatencyModel`-delayed command is processed at exactly `submit +
latency`. There are exactly **two** kinds of eligible settlement event -- not
just any event on another instrument: **(a)** the next event on that order's
*own instrument* (its own next quote -- what a sparse-quote symbol falls back
to), or **(b)** *any* due clock timer the engine processes, from *any*
source, including one with no order effect at all. Per the engine's own
source (`crates/backtest/src/engine.rs` L1559-1585 for timer collection
across the whole engine and L1716-1747 for command processing at that point,
commit
[1b0a49d2792a9432a3aca3fcb617ce7a630d905e](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/backtest/src/engine.rs#L1559-L1747)),
`advance_time_impl` collects every due timer at each processed event and
settles *all* instruments' outstanding deferred commands together at that
point -- not only that timer's own instrument, and not only timers tied to an
order command. **A plain market-data quote for a *different* instrument,
alone, does not do this** -- it is neither trigger (a) nor (b). Concretely
(all verified on the pinned runtime, see
`tests.test_sim_paper_compare.PinnedRuntimeTests`): order A (quotes at
0ms/100ms) submitted at 10ms with 20ms latency (modeled arrival 30ms) fills
at **100ms** (its own next quote, trigger (a)) if order B (a *different*
instrument) merely *has a quote* at 50ms with no order of its own -- a
foreign quote alone does not settle A. It instead fills at **50ms** if order
B is *submitted* at 50ms (B's own decision timer, trigger (b)) -- and fills
at **50ms** even with *no order B at all*, given only a bare no-op clock
timer scheduled at 50ms with no order effect whatsoever, confirming trigger
(b) is genuinely "any due timer," not specifically an order-command one.
Matching happens at the first settlement event *at or after* submit +
latency for that order, whichever trigger reaches it first, and always
against the book as of that settlement instant, not a book frozen at exactly
`submit + latency`.

When quotes for a symbol are sparse and no timer intervenes first, the actual
processing instant can land well after the modeled arrival instant purely
from that symbol's own quotes (trigger (a)): in this receipt, order 3
(GOOGL) fills **266.9ms** after its modeled 5ms arrival, and **466.4ms**
after its modeled 650ms arrival, because no earlier timer happened to
intervene and no GOOGL quote arrived any sooner. At the 100ms sweep point,
order 2 (INTC) fills at 120.54, while the book *at exactly submit + 100ms*
(16:47:43.244353Z) was still bid 120.55/ask 120.57 (the same book as at the
neighboring 70ms and 250ms sweep points, where order 2 fills at 120.55) --
the book had moved to bid 120.54 by the time the next actual settlement event
let the engine process the order, later than submit + 100ms. Order 1 is
unchanged across the 50-650ms sweep points (120.58 throughout); order 2's
move specifically *at* the 100ms point, relative to its own value at the
neighboring 70ms/250ms points, accounts for the 100ms row's 0.489bps mean
price delta (the outlier in the sweep table below) -- order 1's own nonzero
delta at 100ms (+0.829bps) is present at every one of the 50-650ms points and
so is not what makes 100ms distinct from its neighbors.

**Consequence: the sweep's time/price columns are not a pure function of the
configured latency alone**, and a quote-derived "marketable window" boundary
(like order 4's raw-quote 69.273ms above) is corroborating evidence, not the
authoritative flip point. The receipt's `latency_sensitivity_sweep.flip_bisections`
re-runs the replay at bisected latencies (to 1us resolution) to find the actual
fill/no-fill boundary for each order whose agreement changes across the
declared sweep, recording each endpoint's *actual measured* agreement
explicitly (`lo`/`hi`, each `{"latency_ns": ..., "agrees": bool}`) rather than
assuming a direction -- for this trial, agreement is **False at the lower
latency endpoint and True at the higher one** (a lower-latency sim fills an
order paper did not), the opposite of "agrees below, disagrees above." That
bisected value (69.216918ms disagrees / 69.217529ms agrees, for orders 4 and 5
in this receipt) is what's cited above. This behavior is disclosed here rather
than worked around with synthetic arrival-time wakeups, which would need their
own validation against sparse-quote symbols and multi-instrument settlement
interaction before being trusted.

### Latency-sensitivity sweep (not a calibration)

| Latency | Fill agreement | Both filled | Disagreeing orders | mean \|Δprice\| (bps) | mean \|Δtime\| (s) |
| --- | --- | --- | --- | --- | --- |
| 0 ms (default) | 3/5 | 3 | `…0000004`, `…0000005` | 0.375 | 0.863 |
| 5 ms | 3/5 | 3 | `…0000004`, `…0000005` | 0.375 | 0.763 |
| 50 ms | 3/5 | 3 | `…0000004`, `…0000005` | 0.375 | 0.725 |
| 70 ms | 5/5 | 4 | none | 0.281 | 0.644 |
| 100 ms | 5/5 | 4 | none | 0.489 | 0.631 |
| 250 ms | 5/5 | 4 | none | 0.281 | 0.457 |
| 650 ms | 5/5 | 4 | none | 0.281 | 0.066 |
| 1000 ms | 5/5 | 4 | none | 0.281 | 0.284 |

Every cell above is stored per-order (not only as this table's aggregates) in
the receipt's `latency_sensitivity_sweep.points[*].rows`, so any of these
figures can be traced back to a specific order's comparison row at that
latency, not just recomputed from an aggregate.

Bisected flip (`latency_sensitivity_sweep.flip_bisections` in the receipt, not
the raw quote-window boundary -- see above): both orders 4 and 5 flip **from
disagreeing at 69.216918ms to agreeing at 69.217529ms**, a 1us-resolution
bisection between the 50ms and 70ms sweep points. Order 4's flip is
independent (`independent_flip: true`); order 5's is not
(`independent_flip: false`, `depends_on_client_order_ids` names order 4) --
see "Why orders 4 and 5 disagree" above. **This is a sensitivity check on one
order's marketable-window boundary, not a calibrated latency estimate** -- it
does not claim Alpaca's real latency is any specific value in this range, only
that the disagreement is latency-sensitive and concentrated at that boundary,
subject to the "Latency model semantics" caveat above.

### What the time delta actually measures

Submission is scheduled with `clock.set_time_alert_ns` at the paper trial's
exact recorded broker timestamp (not "whenever the next quote of any symbol
arrives" -- see "Known gaps" for what that change fixed), and at the
zero-latency default the fed SIP quotes were already crossing the limit at
that instant for every filled order in this trial. So the `fill_time_delta_s`
column at zero latency mostly measures the **paper broker's own broker
submission-to-fill interval** (0.65-1.09s across this trial's four real
fills, per the results table) -- not a property of the replay, and not a
measure of "how long the paper strategy took to decide": both the
submission timestamp and the fill timestamp it is measured against are
broker-reported, so this interval reflects Alpaca's own processing/matching
time, not any client-side decision delay. This is subject to the same "next
eligible settlement event, not exact instant" caveat above once latency is
added to the sweep.

### Clock sources and provenance

Three different clocks are in play, and their mutual agreement is **not
established** by this replay:

- **Submit timestamps** use the broker's own reported clock (Alpaca order
  `submitted_at`).
- **Cancel timestamps** (`resolve_cancel_timestamps()`) use the adaptive-paper
  runner's **host clock**, captured just before the cancel request is sent
  (`adaptive-paper/runner.py`'s `before_request()`). Runs since 2026-09-25
  also record the cancelled order's `client_id` on each cancel request, which
  pairs cancels exactly. Older ledgers record only `{"timestamp": ..., "kind":
  ...}` -- no `client_order_id`, which is why their cancel-request-to-order
  matching is validated rather than trusted blindly; see below.
- **SIP quote timestamps** are a third, Alpaca-feed clock.

Measured for this trial: the host clock read **at least +27.994 to +40.769ms
ahead** of the broker's own submit timestamps
(`clock_provenance.host_minus_broker_submit_offset_ms` in the receipt). This
is a **lower bound**, not an upper one: the host timestamp is captured
*before* the request is sent over the network, while the broker timestamp is
captured *after* Alpaca receives it, so the true clock-source offset is at
least this measured gap and could be larger by however much
network/processing time separates those two capture points
(`clock_provenance.host_minus_broker_submit_offset_is_lower_bound: true` in
the receipt). Since the host clock leads the broker clock, the broker-clock
instant corresponding to the recorded (host-clock) cancel request is
*earlier* than the raw number used here, not later. **This receipt's outcome
is not sensitive to that uncertainty**: there is no marketable order-4 quote
in the interval from submit+80ms to the recorded cancel time + 1.1s, so
shifting the cancel instant earlier within the plausible clock-offset range
does not change which side of the marketable-window boundary it falls on. A
future trial with a marketable quote near a cancel boundary could flip on
this offset, and SIP-vs-broker clock agreement specifically is not
established at all -- treat per-trial clock provenance as something to
check, not assume. `clock_provenance`'s own submit-timestamp pairing reports
`null` offsets with an explicit `host_minus_broker_submit_offset_unavailable_reason`
whenever its own count check (`counts_match`) fails, rather than reporting
offsets computed from a truncated, misaligned pairing (a dropped entry on
either side would shift every later pairing by one position and produce
numbers that look like measurements but pair unrelated events -- as large as
~195 seconds in a constructed test case).

**Exact pairing (runs since 2026-09-25).** When cancel requests carry
`client_id`, each canceled order resolves to its first named request
(`source: recorded_cancel_request_client_id`, with `named_request_count`; a
retried cancel counts more than once). A canceled order with no named request
falls back to submit + `order_timeout_seconds`
(`submit_plus_order_timeout_seconds_no_named_cancel_request`), and
`clock_provenance.named_cancel_requests` reports the named requests, the orders
they name and any unnamed cancel requests that were ignored. Submit entries
also carry `client_id` and are never read as cancels. The rule below is not
used for such runs.

**Older ledgers: cancel-request matching is by open-order uniqueness across
the whole trial, not positional and not limited to canceled orders.** There
`requests[]` has no `client_order_id` and no symbol, so a cancel request
cannot be attributed to a specific order directly. `resolve_cancel_timestamps()` uses this rule
instead of a chronological-order heuristic: a cancel request at time T is
attributed to order O only if O is the *unique* order that is open (submitted
by T, and not yet terminal -- a filled order is terminal at its reported
`filled_at_ns`; a canceled order is never treated as terminal here, since its
true cancel instant is exactly what this function is solving for) across the
*entire trial* at T, and O is one of the trial's canceled orders. This
correctly accepts an unambiguous cross-symbol case (a canceled order's own
symbol has no other open order at cancel time, even though an unrelated,
already-resolved order of a *different* symbol was submitted in between --
the earlier heuristic's "most-recently-submitted order overall" check
wrongly refused this) and correctly refuses a genuinely ambiguous one (more
than one order, of any symbol, still open at the cancel instant -- including
the tied-input-order case, where two same-symbol orders are both open at T
and the correct answer, "ambiguous," must not depend on which one happens to
sort first; the previous rule's positional tie-break did). Any failed
validation falls back to `submit + order_timeout_seconds` for *all* canceled
orders in the trial, rather than guessing. `clock_provenance()`'s
submit-timestamp pairing is similarly count-checked (`counts_match` in the
receipt) before any offsets are reported.

**This rule is not unconditionally correct -- it is sound only under three
assumptions**, none of which is checked by the code: (1) each canceled order
has *exactly one* cancel-request log entry (not zero, not more than one); (2)
no order is canceled broker-side *without* a corresponding logged request
(e.g. a risk halt, a session close, or any other non-request-driven
cancellation the runner doesn't log as a `"cancel"` request); and (3) the
host and broker clocks are aligned within whatever tolerance separates two
genuinely-open orders' windows -- see "Clock sources and provenance" above
for this trial's measured (lower-bound) offset. Two constructed
counterexamples show why each assumption matters, not just in the abstract:

- **(a) A repeated DELETE, paired with the wrong order.** Order X is
  submitted, a cancel is requested for it at 10s, and (for whatever reason --
  a retry, a stale UI action) a *second* cancel request for X is logged at
  12s. Meanwhile order W, submitted at 11s, is canceled broker-side with *no*
  logged request at all (assumption (2) violated). At the 12s request, W is
  the *only* order that looks open (X, per this algorithm, was already
  resolved by the 10s request and is now terminal) -- so the 12s DELETE gets
  paired with W, not with its actual (second) request for X. This is a
  repeated-DELETE case (assumption (1) violated) compounding a broker-side,
  unlogged cancellation (assumption (2)).
- **(b) A DELETE that loses the race to a fill, inside the clock-offset
  window.** The host clock leads the broker's by at least ~41ms (above), so
  a cancel request sent at broker time 10.000s is logged at about 10.050s.
  If the targeted order fills at broker time 10.020s, after the request was
  sent but before the broker acted on it, the logged request appears to come
  *after* the fill. The algorithm then treats the targeted order as already
  terminal at the request time and excludes it, so the request can be
  attributed to a different, genuinely canceled order that is still open.
  If the offset ran the other way, the filled order would stay open at the
  request time and the pairing would be refused as ambiguous instead.

Both failure modes trace back to the same root cause in older ledgers:
`requests[]` recorded neither `client_order_id` nor symbol. Since 2026-09-25
`AlpacaPaperTransport.cancel()` announces its DELETE on the guarded session,
the budget hook receives the cancelled order's `client_id`, and new runs are
paired exactly (above), with no assumptions needed. **This retained
receipt is unaffected by either counterexample**: order 4 is the *only* open
order at its cancel-request time in this trial (verified, not assumed --
there is no other order, of any symbol, open at that instant), so neither a
repeated-DELETE nor a race-lost-fill scenario is even reachable here. A
future trial with overlapping open orders near a cancel boundary could hit
either one, and should not assume this rule's soundness without checking.

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
  only for the declared sensitivity sweep above, with the semantics caveat
  above; the primary "results" section and receipt aggregates are the
  zero-latency default (`latency_model=None`), consistent with
  `engine-nautilus/equity-replay`'s baseline case.
- **Cost sensitivity**: [`execution-realism`](../execution-realism/README.md)'s
  LEAN fee/slippage sensitivity receipt is the other existing fill-model
  evidence in the repo; it is a different engine (LEAN, not Nautilus) exercising
  market orders on a five-day SPY schedule, so it is cited here for its
  documented execution-boundary language (no partial fills, no queue position,
  no latency/impact model beyond the declared sweep above), which applies
  equally to this replay's zero-latency default and is restated below, not
  reused as configuration.
- **Data fetch**: GET-only against the existing Alpaca historical data path
  (`/v2/stocks/quotes`, `feed=sip`), using `urllib.request` directly (not
  `alpaca-py`; see "Known gaps" for why the receipt's `alpaca_py_installed_version`
  is environment metadata, not data provenance), `adaptive-paper/runner.py`'s
  `credentials()` loader (fails closed on env-file permissions/location, and is
  never imported or invoked at all in `--replay` mode) and a
  page-retention/replay fetcher adapted from `mover-early-entry/mover_scan.py`'s
  `Fetcher` (reimplemented locally as `PageFetcher` to avoid pulling that
  module's numpy/rules/sessions_io dependency chain into the pinned
  Nautilus-only runtime; behavior is identical for a fresh fetch: every
  response kept gzip'd with a sha256 ledger under `--pages`. `--replay`
  re-derives the run from those pages with no network access, and the receipt's
  `data_provenance.page_sources` records, per page, whether it was served from
  the network or the cache in the run that produced it -- the retained receipt
  above shows all four pages served from cache, since it was produced with
  `--replay`).
- **Order replay**: `broker-orders.json`'s read-only order readback (symbol,
  side, qty, `limit` type, limit price, `submitted_at`/`filled_at`) is replayed
  as `Strategy.submit_order`/`cancel_order` calls scheduled at the exact
  recorded timestamps via `clock.set_time_alert_ns`, with the paper trial's own
  `client_order_id`s preserved end to end so every simulated report row maps
  back to a specific paper order.

## Known gaps and declared limitations

- **Cancel timestamp**: resolved from `paper-output.json`'s own `requests` log
  (`resolve_cancel_timestamps()`) when the number of recorded cancel requests
  matches the number of canceled orders *and* every request maps to a unique
  open order across the whole trial that is a canceled order (see "Clock
  sources and provenance" above -- including the three assumptions this rule
  depends on and is not checked against, and the two constructed
  counterexamples that show why); falls back to `submitted_at + order_timeout_seconds`
  (the runner's own cancel-on-timeout rule, with `order_timeout_seconds` read
  from the config file whose sha256 matches this trial's `ingest-receipt.json`)
  whenever that doesn't hold. Neither branch infers a cancel time from a
  successor order.
- **Unlimited liquidity, no queue position**: matching against L1 top-of-book
  quotes assumes full depth at the quoted price/size; `liquidity_consumption`
  and `queue_position` are both explicitly set to their engine defaults
  (`False`) and recorded in the receipt's `engine` section rather than only
  described in prose. This is the same boundary `execution-realism` and
  `equity-replay` declare for their fill models, and it applies here too. No
  partial fills, spread dynamics beyond L1, halts or auction behavior are
  modeled. Concretely: with `liquidity_consumption=False`, quoted size is
  ignored entirely, so a marketable order always fills in full at the first
  eligible settlement event regardless of quoted size (verified, not assumed
  -- see `tests.test_sim_paper_compare.PinnedRuntimeTests.test_current_no_partial_fill_configuration_ignores_quoted_size`).
  This engine configuration therefore cannot natively produce a partial-fill-
  then-cancel case; the `fill_ts_ns` extraction logic that matters for that
  case (see below) is instead tested directly against constructed events in
  `tests.test_sim_paper_compare.SummarizeSimOrderTests`.
- **Latency**: the zero-latency default and the declared sensitivity sweep
  (above) are the only latency treatments; neither claims to know Alpaca's
  actual paper-broker latency distribution, and the "Latency model semantics"
  caveat above (including cross-instrument settlement) applies to every
  sweep point.
- **Five orders, one trial**: this run cannot estimate a fill rate, size a
  slippage distribution or detect regime dependence. A calibration would need
  many trials across sessions, symbols and regimes with independently recorded
  cancel timestamps.
- **This receipt used a single fetch**: it was not independently re-pulled to
  check for revision; the SHA256 page ledger identifies the retained inputs
  and supports same-page replay, not a claim that the SIP vendor never revises
  historical quotes or that an independent fresh request would match.
- **Crossed quotes**: any SIP quote row with `bid > ask` is dropped before
  matching (a crossed NBBO cannot be matched sanely and would let a limit fill
  through a data artifact) and counted per symbol in the receipt's
  `data_provenance.quote_drop_counts`. Locked quotes (`bid == ask`) are valid
  market data and are kept.
- **Partial-fill timestamps**: a partial fill's reported `sim_fill_ts` comes
  from `summarize_sim_order()`'s extraction of the actual `OrderFilled`
  event(s), not `order.ts_last` (which reflects the order's *last event of
  any kind* -- so a partial fill followed by a later cancel would otherwise
  report the cancel's timestamp as the fill time). As noted above, this is
  tested directly against constructed events (`SummarizeSimOrderTests`),
  since the current engine configuration cannot natively exercise the case.
- **`alpaca_py_installed_version`** in the receipt's `runtime_environment` is
  environment metadata, not data provenance: this script fetches with
  `urllib.request` directly, and `--replay` makes no request at all.

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
ignoring only the run-local `started_utc`/`completed_utc`/`argv`/`stdout_sha256`/
`stdout_sha256_basis` fields (which necessarily differ between runs/hosts --
`stdout_sha256` differs because the receipt path itself is part of the hashed
summary, and `stdout_sha256_basis` depends on the invoking process's own stdout,
not on this script). Pass the scratch receipt's path as an argument, rather
than interpolating an environment variable inside a quoted heredoc (which a
shell will not expand and Python will not read automatically -- either read it
from the environment inside Python, or pass it as `argv`, as below):

```sh
python3 - "$PRIVATE_CACHE_DIR/scratch-receipt.json" <<'PY'
import json
import sys
a = json.load(open("blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json"))
b = json.load(open(sys.argv[1]))
for k in ("started_utc", "completed_utc", "argv", "stdout_sha256", "stdout_sha256_basis"):
    a.pop(k, None); b.pop(k, None)
print("EQUAL" if a == b else "DIFFER")
PY
```

`--pages` and `--out` must be private paths outside the repository (e.g. under
`~/.local/state/native-agent-stack/sim-paper/`); only the receipt's hashes and
results are committed, never the fetched SIP quote pages or engine report
CSVs. `--trial`/`--receipt` are trimmed in the committed `argv` to a
repo-relative path (or basename if given outside the repo) rather than
recorded verbatim, since an absolute path for either would still carry the
invoking user's home directory. The report hashes in the receipt
(`engine.reports.*.sha256_excluding_init_id`) are computed over the
fills/orders rows with the random per-order `init_id` field stripped first,
since `init_id` is a fresh UUID on every run and would otherwise make the
hash non-reproducible for reasons that have nothing to do with the run's
actual results.

```sh
python3 -m unittest tests.test_sim_paper_compare -v
```

The offline suite exercises timestamp parsing, paper-order normalization
(including refusing a non-DAY time-in-force and a fractional quantity),
cancel-timestamp resolution (recorded request vs. timeout fallback vs. refused
ambiguous match, validated against every order in the trial), clock
provenance (including the count check and lower-bound framing), decision
building, the fetch window, quote-row filtering (including crossed and locked
quotes), `PageFetcher` (replay, hash-mismatch, pagination), the
comparison/aggregation logic (including partial fills and BUY/SELL slippage
sign on both the paper and sim sides), `summarize_sim_order`'s event
extraction against constructed order/event objects (the authoritative
fill_ts_ns-vs-ts_last test, independent of whether the current engine
configuration can produce a native partial-fill-then-cancel case), argv
redaction (including that an abbreviated flag is now rejected outright, not
silently accepted and leaked, and that `--trial`/`--receipt` are trimmed), and
receipt/README consistency checks (aggregates, `inputs_sha256`,
`runner_sha256`, the results table, the per-order sweep rows, and the
bisection direction/dependence fields) -- all against synthetic fixtures and
the retained trial's real `broker-orders.json`/`paper-output.json`. A
separate, explicitly gated class runs `run_replay` and the CLI's `--replay`
path against tiny synthetic fixtures on the pinned Nautilus runtime --
including a cancel-boundary case (a canceled order must not fill on a later
marketable quote), an off-quote-timed submit (catching decision timing that
silently falls back to "next quote of any symbol" instead of the exact
scheduled instant), a cross-instrument settlement-timer case (reproducing the
"Latency model semantics" A/B example above), a latency-magnitude lower-bound
case, confirmation that report hashes reproduce across independent reruns
from the same retained pages, that stdout is written correctly even when
`sys.stdout` has no `.buffer` attribute (as under `python -m unittest -b`),
and that a distinctly-valued umask set immediately before the call is
restored exactly (not compared against whatever the ambient process umask
happened to be, which would pass even without a restore if an earlier test's
`main()` call had already left it changed) -- plus a check that the
credential loader (`runner.credentials`) is never imported or called in
`--replay` mode. It is skipped automatically when the pinned runtime is not
the active interpreter. These are local integration checks, not unchanged
upstream tests -- see `docs/acceptance-evidence-policy.md`.
