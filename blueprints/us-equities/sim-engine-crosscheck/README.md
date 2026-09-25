# sim-engine-crosscheck: NautilusTrader vs hftbacktest, Phase C

**This is an engine-execution-semantics comparison, not strategy evidence.**
It replays one shared, deterministic, non-reactive order stream through two
independent simulation engines -- NautilusTrader 2.0.0rc5
(`blueprints/us-equities/sim-capacity/`) and hftbacktest 2.4.4
(`blueprints/us-equities/sim-crosscheck-hftbacktest/`) -- over the same
bounded, already-retained Alpaca SIP sample, and compares fill rate, timing,
touch share and cost. Tagged `evidence_class: sim_engine_crosscheck`.

## Repair round (2026-09-25): the first attempt's conclusion was wrong

**An independent adversarial review refuted the first attempt's conclusion
outright, and this task independently reproduced the refutation.** The
original `run_hftbacktest.py` had a use-after-free: a single loop-local
`data` variable was reassigned once per symbol while building each symbol's
`BacktestAsset`, but `BacktestAsset.add_data()` does not take ownership of
the numpy array or increment its reference count -- it stores a raw,
non-owning pointer into the array's own buffer. As soon as the second
symbol's array was built, the first symbol's (NVDA, built first) only
Python reference was gone, and CPython was free to reclaim that memory
while hftbacktest's Rust side kept reading through the dangling pointer for
the rest of the run. This corrupted every hftbacktest result the first
attempt reported and drove its entire "F1"/"F2" narrative, both now
**withdrawn**.

This task confirmed the bug directly, independent of the review's own
numbers: running the *unmodified* first-attempt driver twice on identical
input gave non-identical outcome hashes (determinism check fails); running
NVDA alone versus extracting NVDA's own outcomes from a two-symbol run also
gave non-identical hashes (isolation check fails). Both checks pass
(hash-identical) once the array-lifetime fix is applied. See
`receipts/20260925-crosscheck.json`'s `superseded_first_attempt` block for
the full account, every hash, and the fix. **The original, wrong receipt is
kept on record, unmodified, at `receipts/20260925-crosscheck-superseded.json`
-- not deleted.**

**Corrected conclusion: NautilusTrader and hftbacktest agree within
tolerance.** Fill rate diverges by 0.30-0.36% (not the ~27-29% the first
attempt reported) and median time-to-fill by 1.16-1.59x (1.0x on a
NautilusTrader exact-latency variant added this round) -- both comfortably
inside sim-capacity's own 20%/2x overturn thresholds. The NautilusTrader
destination is **not** overturned. See "Overturn evaluation" below.

## Prerequisites

Both merged to `main` before this task started: `sim-capacity/` (#235,
commit `1e11a894`) and `sim-crosscheck-hftbacktest/` (merged earlier, present
at the same commit).

## Sample and order stream

Unchanged from the first attempt (neither was implicated in the bug): an
8-minute slice (`2026-09-24T14:05:00Z`-`14:13:00Z`) of SPY and NVDA from
sim-capacity's already-retained private Alpaca SIP cache, and a deterministic,
precomputed 1439-order stream at 3 submits/sec (sim-capacity's paper-parity
rate-limit budget, `180/00:01:00` = 3.0/sec), generated once via
`order_stream.py` (reusing sim-capacity's own `schedule.py`) and regenerated
this round to a byte-identical file
(`sha256 0e095e88451da921c8858e3d8cd0cb87c9add865fd4a0f7ad7bc0aef9b673e60`).
See `sample.py` and `order_stream.py`'s own module docstrings for the full
rationale (window choice, cadence justification, precompute-vs-live-feedback
tradeoff). `sample.py` never touches the network or opens credentials.

3 of 1439 orders (0.21%) are REJECTED on NautilusTrader from the stream's own
assumed-vs-real fill divergence (order IDs 223, 295, 608 at 70ms latency;
60, 211, 299 at 250ms latency -- corrected this round from the first
attempt's receipt, which listed only the 70ms IDs and mislabeled them as
applying to both latencies). See `order_stream.py`'s module docstring for why
this is expected and accepted, not a defect.

## The fix

`run_hftbacktest.py`'s module docstring has the full citation trail
(`py-hftbacktest/hftbacktest/__init__.py:119-120`, `lib.rs:206-210`,
`backtest/data/mod.rs`'s own "not owned ... must remain valid" comment on the
pointer type). In short:

- **Use-after-free (the actual bug)**: every per-symbol event array is now
  appended to a list held alive for the whole `run_stream` call, through
  `hbt.close()`.
- **Exact submit times**: orders are now submitted at their exact scheduled
  time (the engine's clock is `elapse()`d directly to each order's own
  `ts_ns`, computed as a delta from `hbt.current_timestamp`) instead of the
  original 10ms polling grid.
- **Filled quantity**: now read as `qty - leaves_qty` (the order's own
  before/after bookkeeping), not `exec_qty`, which upstream holds only the
  LAST individual fill call's quantity -- irrelevant once fills are
  single-tick (the corrected, common case here), but was masking the
  corruption's true footprint in the original run.

Verified four independent ways (all in the committed receipt): a
determinism rerun (hash-identical), a two-symbol-vs-single-symbol isolation
check (hash-identical), a last-NBBO-crossing oracle agreeing with every
engine/symbol combination at >=99.58%, and zero fills better than the
displayed touch across all 8 runs (a new hard check that the first attempt
never ran against hftbacktest's own output at all -- it would have caught
the corruption directly: 354 of 384 NVDA fills in the broken run were better
than any displayed quote, by up to 87 cents).

## Oracle (new this round)

`oracle.py` is a small, independent, engine-free ground-truth check: given
only the retained quotes, it decides per order whether it should be
immediately fillable at `submit_ts + latency` -- the last NBBO at or before
that instant, the limit price crossing it, and the touch's displayed size
being at least the order's quantity. It exists specifically to catch a case
where both engine drivers agree with each other while both being wrong
(something comparing the two engines only to each other could never detect
-- exactly the blind spot the first attempt had). It is a sanity oracle, not
a third execution simulator: it ignores queue position, in-transit price
movement of the touch used for the crossing check, and cross-order
liquidity consumption.

## Engine configuration

| | NautilusTrader (`run_nautilus.py`) | hftbacktest (`run_hftbacktest.py`) |
|---|---|---|
| Book / feed | `BookType.L1_MBP`, QuoteTicks only | L1 `DEPTH_EVENT` pairs per side per quote tick |
| Venue flags | `trade_execution=True, liquidity_consumption=True, queue_position=True` | `power_prob_queue_model(2.0)`; exchange model swept |
| Latency | `StaticLatencyModel`, released at the next own-instrument quote or any due timer at or after submit+latency (default), or forced to exactly submit+latency via a no-op alert (`exact_latency=True`, new this round) | `constant_order_latency(latency_ns, latency_ns)` -- always exactly submit+latency |
| Account | `CASH`, 10,000,000 USD | No account/short-sale concept |
| Order | marketable `LIMIT`, `TimeInForce.IOC`, one-cent collar | `LIMIT`, `IOC`, same collar |

Fees are computed post-hoc, uniformly, by `metrics.py` using sim-capacity's
own `fee_model.commission_usd(commission_plan="none")` for both engines.

## Configuration matrix (8 runs)

Nautilus: 70ms and 250ms, each with and without `exact_latency` (4 runs).
hftbacktest: 70ms and 250ms, `partial_fill_exchange` and
`no_partial_fill_exchange` (4 runs). See `receipts/20260925-crosscheck.json`'s
`config_matrix`.

## Results

Read `receipts/20260925-crosscheck.json`'s `metrics_table` for the exact,
regeneratable numbers (this table is sourced from it, not retyped by hand):

| Config | Fill rate | Median time-to-fill | p90 | Touch share | Better-than-touch |
|---|---|---|---|---|---|
| Nautilus 70ms (primary) | 97.64% | 111.23ms | 287.40ms | 100.0% | 0 |
| Nautilus 70ms (exact_latency) | 97.71% | 70.00ms | 70.00ms | 100.0% | 0 |
| hftbacktest 70ms partial_fill | 97.98% | 70.00ms | 70.00ms | 100.0% | 0 |
| hftbacktest 70ms no_partial_fill | 97.98% | 70.00ms | 70.00ms | 100.0% | 0 |
| Nautilus 250ms (primary) | 94.23% | 290.60ms | 333.33ms | 100.0% | 0 |
| Nautilus 250ms (exact_latency) | 94.44% | 250.00ms | 250.00ms | 100.0% | 0 |
| hftbacktest 250ms partial_fill | 94.51% | 250.00ms | 250.00ms | 100.0% | 0 |
| hftbacktest 250ms no_partial_fill | 94.51% | 250.00ms | 250.00ms | 100.0% | 0 |

By symbol (fill rate), from `metrics_table_by_symbol_fill_rate_pct`:

| Symbol | Nautilus 70ms | Nautilus 70ms exact | hftbacktest 70ms | Nautilus 250ms | Nautilus 250ms exact | hftbacktest 250ms |
|---|---|---|---|---|---|---|
| SPY | 98.33% | 98.33% | 98.61% | 94.71% | 94.99% | 94.99% |
| NVDA | 96.94% | 97.08% | 97.36% | 93.75% | 93.89% | 94.03% |

**Both symbols now agree closely between engines** (NVDA within 0.43%
relative divergence at 70ms; SPY within 0.28%) -- a complete reversal of the
first attempt's reported ~82% NVDA divergence, which never reflected real
engine behavior.

**hftbacktest's two exchange models agree exactly**: `partial_fill_exchange`
and `no_partial_fill_exchange` produce byte-identical outcomes on all
1439 orders at both latencies (`hftbacktest_exchange_model_agreement` in the
receipt) -- the withdrawn F2 finding (a reported NVDA-only, 70ms-only
disagreement between them) was the same use-after-free, not a real
hftbacktest inconsistency.

### Oracle agreement table

From `receipts/20260925-crosscheck.json`'s `oracle_agreement`:

| Config | Overall | NVDA | SPY |
|---|---|---|---|
| Nautilus 70ms (primary) | 99.65% | 99.58% | 99.72% |
| Nautilus 70ms (exact_latency) | 99.72% | 99.72% | 99.72% |
| hftbacktest 70ms (either exchange model) | 100.0% | 100.0% | 100.0% |
| Nautilus 250ms (primary) | 99.72% | 99.72% | 99.72% |
| Nautilus 250ms (exact_latency) | 99.93% | 99.86% | 100.0% |
| hftbacktest 250ms (either exchange model) | 100.0% | 100.0% | 100.0% |

hftbacktest's constant-latency, last-NBBO-crossing model matches the
oracle's own definition almost by construction (100% in every
configuration) -- a strong sanity check that the fix is correct, not merely
a coincidence. Every cell exceeds the review's own 99% bar.

### A real, minor, separate NautilusTrader finding: release-timing slack

Distinct from the withdrawn findings and the hftbacktest fix: a deferred
NautilusTrader order is released only when some event (its own instrument's
next quote, or any due clock timer) is next processed at or after
submit + latency, not exactly at that instant. With this cross-check's
single, shared 3/sec submit-schedule timer as the only per-order timer, an
order can sit past its configured latency until the next actual trigger.
Measured on the primary 70ms run (`release_timing_finding` in the receipt):
extra delay median ~29ms (SPY) / ~58ms (NVDA), p90 ~136ms/263ms -- close to,
and corroborating, the review's own independently reported ~28ms/~53ms
median and ~135ms/263ms p90 (small differences consistent with a different
percentile-interpolation method).

**Tested fix, added this round**: `exact_latency=True` (one no-op
`set_time_alert_ns` per order at exactly `submit_ts + latency_ns`,
`run_nautilus.py`) makes every filled order resolve at EXACTLY
submit+latency (verified: min/max extra delay both exactly 0.0ms), bringing
NVDA to 699/720 (97.08%) at 70ms versus hftbacktest's 701/720 (97.36%) -- a
0.29% relative difference. Nautilus's actual fill prices stay within the
100% touch-share guarantee even with the default timing (this is a delay in
*when* an order resolves, not a stale- or better-than-touch price).

**This is not fixed here.** Recommendation: fix sim-capacity's own
`CapacityExerciser`/`runner.py` timing (e.g. an equivalent per-order release
alert, or documenting the behavior explicitly) in a **separate follow-up
PR**. This task does not modify sim-capacity code.

## Overturn evaluation

Quoting `sim-capacity/experiment.json`'s `next_decision_changing_test`
verbatim: *"overturn if it diverges from this record's NautilusTrader
results by more than 20% or 2x with no attributable Nautilus matching bug."*

- Fill-rate relative divergence (hftbacktest vs. Nautilus primary): 0.356%
  (70ms), 0.295% (250ms) -- **not** over 20%.
- Median time-to-fill ratio (Nautilus primary / hftbacktest): 1.589x (70ms),
  1.162x (250ms) -- **not** over 2x. (1.0x exactly against the
  exact-latency variant, at both latencies.)

**Neither threshold is met, so the "no attributable Nautilus matching bug"
clause is moot -- the condition does not trigger.** The sim-capacity
NautilusTrader 2.0.0rc5 destination is **not** overturned by this
cross-check. This corrects the first attempt's conclusion, which reported a
27-29% divergence caused entirely by the hftbacktest driver's own
use-after-free.

## Files

- `sample.py` -- bounded SPY+NVDA sample extraction (unchanged this round).
- `order_stream.py` -- deterministic order-stream generator (unchanged).
- `metrics.py` -- engine-agnostic metrics; adds `better_than_touch_violations`
  this round (a hard integrity check, not just a reported metric).
- `oracle.py` -- **new this round**: independent, engine-free ground-truth
  fillability prediction and confusion-table computation.
- `run_nautilus.py` -- NautilusTrader driver; adds the `exact_latency` option.
- `run_hftbacktest.py` -- hftbacktest driver; **fixes the use-after-free**,
  submits at exact times, and reads `qty - leaves_qty`.
- `crosscheck.py` -- CLI orchestrator; `report` now runs the oracle and the
  better-than-touch hard check (raises on failure) and writes an
  intermediate `report.json`, not the committed receipt directly; adds a
  `determinism-check` subcommand.
- `receipts/20260925-crosscheck.json` -- the corrected receipt.
- `receipts/20260925-crosscheck-superseded.json` -- the first attempt's
  exact, original, wrong receipt -- kept on record, unmodified, not deleted.

## Running it

NautilusTrader and hftbacktest live in two different, mutually incompatible
Python environments:

```
# 1. Bounded sample (system python)
python3 blueprints/us-equities/sim-engine-crosscheck/sample.py

# 2. Deterministic order stream (system python)
python3 blueprints/us-equities/sim-engine-crosscheck/crosscheck.py stream \
    --out PRIVATE/stream.json

# 3. NautilusTrader side (pinned runtime), primary and exact-latency variant
~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python \
    blueprints/us-equities/sim-engine-crosscheck/crosscheck.py run-nautilus \
    --stream PRIVATE/stream.json --latency-ms 70 --out PRIVATE/nt_70.json
# ... add --exact-latency for the timing-isolation variant

# 4. hftbacktest side (isolated venv -- see "Reproducing the hftbacktest venv"
#    in the previous section, unchanged), one call per (latency, exchange model)
~/.local/share/native-agent-stack/hftbacktest-2.4.4/bin/python3 \
    blueprints/us-equities/sim-engine-crosscheck/crosscheck.py run-hftbacktest \
    --stream PRIVATE/stream.json --latency-ms 70 --exchange partial_fill \
    --out PRIVATE/hft_70_partial.json

# 4b. Determinism check (same venv)
~/.local/share/native-agent-stack/hftbacktest-2.4.4/bin/python3 \
    blueprints/us-equities/sim-engine-crosscheck/crosscheck.py determinism-check \
    --stream PRIVATE/stream.json --latency-ms 70 --exchange partial_fill

# 5. Report (any python): build a {"label": "path.json", ...} manifest of the
#    eight outcome files, then:
python3 blueprints/us-equities/sim-engine-crosscheck/crosscheck.py report \
    --stream PRIVATE/stream.json --runs PRIVATE/runs.json \
    --commission-plan none --out PRIVATE/report.json
```

`report` raises (non-zero exit) if any fill beats the displayed touch, for
either engine -- treat that as a hard failure, not a metric to eyeball.

### Reproducing the hftbacktest venv

Exactly per `sim-crosscheck-hftbacktest/README.md`'s "Pinned install":

```
uv venv --python 3.12 ~/.local/share/native-agent-stack/hftbacktest-2.4.4
uv pip sync --python ~/.local/share/native-agent-stack/hftbacktest-2.4.4/bin/python3 \
    --require-hashes blueprints/us-equities/sim-crosscheck-hftbacktest/requirements.lock
```

This task rebuilt that venv (again, for this repair round) and **removed it
again** afterward, matching that blueprint's own established cleanup
convention -- see the receipt's `cleanup` block.

Tests: `python3 -m unittest -v tests.test_sim_engine_crosscheck`. Hermetic
and synthetic throughout. `oracle.py` and `metrics.better_than_touch_violations`
are checked on small, hand-constructed synthetic fixtures unconditionally;
receipt-level tests assert oracle agreement >=99% and zero
better-than-touch violations for every committed run. Runtime-gated tests
(skip cleanly without the corresponding interpreter) include the
two-symbol-vs-single-symbol isolation check and a determinism rerun --
their docstrings record that both were verified failing against the
original, unmodified (use-after-free) driver before the fix.

## Limitations

- Two latency points, two exchange models (plus one Nautilus timing
  variant), on one 8-minute, 2-symbol sample.
- The release-timing finding's mechanism is cited from the existing
  sim-crosscheck-hftbacktest/README.md and sim-paper-compare receipts'
  prior source citations, not re-derived from source a second time this
  round.
- The locked-quote depth-eviction behavior (314 locked NVDA rows, 610 locked
  SPY rows, independently recounted and matching the review exactly) was
  measured to affect exactly one order across the whole matrix; this task
  did not identify which specific order.
- EMO/Lee-Ready aggressor-side inference was not applied: both engines
  replay quotes only.
