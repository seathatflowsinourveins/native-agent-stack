# sim-engine-crosscheck: NautilusTrader vs hftbacktest, Phase C

**This is an engine-execution-semantics comparison, not strategy evidence.**
It replays one shared, deterministic, non-reactive order stream through two
independent simulation engines -- NautilusTrader 2.0.0rc5
(`blueprints/us-equities/sim-capacity/`) and hftbacktest 2.4.4
(`blueprints/us-equities/sim-crosscheck-hftbacktest/`) -- over the same
bounded, already-retained Alpaca SIP sample, and compares fill rate, timing,
touch share and cost. Tagged `evidence_class: sim_engine_crosscheck`. See
`receipts/20260925-crosscheck.json` for exact numbers, hashes and commands;
this README explains the setup and reads its headline table from that
receipt rather than retyping it, so the two cannot silently drift apart.

## Prerequisites

Both merged to `main` before this task started: `sim-capacity/` (#235,
commit `1e11a894`) and `sim-crosscheck-hftbacktest/` (merged earlier, present
at the same commit). This task's worktree HEAD was verified equal to
`origin/main` at that commit before any work began.

## Sample

An 8-minute slice (`2026-09-24T14:05:00Z`-`14:13:00Z`, inside sim-capacity's
own 14:00-14:30Z analysis window) of two symbols from sim-capacity's already-
retained, private Alpaca SIP cache (`~/.local/state/native-agent-stack/
sim-capacity/catalog/`): **SPY** (the stable index-ETF proxy already used
throughout sim-capacity) and **NVDA** (a high-volume single name from the
same 8-symbol universe, deliberately more volatile). `sample.py` filters this
down with no network request and no credential file opened (it never imports
`fetcher.load_credentials`), and writes a private, 0600 bounded sample
(`~/.local/state/native-agent-stack/sim-engine-crosscheck/sample.private.json`,
never committed) plus a manifest of counts and hashes
(`sample-manifest.json`). Trades are extracted alongside quotes for
completeness but not fed to either engine (see "Engine configuration" below).

Counts: SPY 61,926 quotes / 12,175 trades; NVDA 32,786 quotes / 47,027 trades
over the 8-minute window (`receipts/20260925-crosscheck.json`'s `sample`
block has the exact hashes).

## Order stream

`order_stream.py` generates the deterministic stream **once**, importing
sim-capacity's own `schedule.RoundRobin` / `clamp_sell_quantity` /
`tick_interval_ns` directly (not reimplemented), so the inventory-aware side
alternation is bit-for-bit the same logic `CapacityExerciser` itself uses.

**Cadence: 3 submits/sec.** This is sim-capacity's own paper-parity
`RiskEngineConfig` budget expressed per second (`"180/00:01:00"` = 180/60 =
3.0 exactly) -- and independently also `CapacityExerciserParams`' own
`submits_per_sec` dataclass default. It is deliberately **not** either real
sim-capacity profile's own *attempted* cadence (paper-parity attempts
5.0/sec = 300/min specifically to exceed its 180/min budget and force
rate-limiter denials as that lane's own test target; elite-tier attempts
~16.67/sec against 900/min). Staying inside the budget keeps Nautilus's rate
limiter from denying any order -- an artifact with no hftbacktest counterpart
at all (hftbacktest has no per-account submit-rate-limiter concept) -- so
this cross-check measures execution/queue semantics, not limiter behavior.

**Precomputed once, not fed back from either engine.** The real exerciser's
side selection reads its own *live* position, itself a function of realized
fills -- which differ by construction between the two engines. Replaying two
independently-fed-back streams would compare two different order sequences,
not the same orders under two engines. `order_stream.py` instead walks the
retained quotes once, offline, with an **assumed-full-fill** running
position per symbol used only to pick sides/quantities deterministically --
not a claim that every order actually fills. **Measured cost of this
simplification**: 3 of 1439 orders (0.21%), all on NautilusTrader, were
REJECTED as an attempted short sale on the CASH-account venue, because the
immediately preceding same-symbol BUY was assumed-filled for stream
generation but did not actually fill in the real run (confirmed directly by
order ID: 221, 293 and 606 all resolved `NO_FILL`, and their following SELLs,
223/295/608, were the 3 rejects). hftbacktest shows **zero** REJECTED
outcomes in any configuration, consistent with it modeling no account-level
short-sale rule at all -- an accepted, documented, and very small (0.21%)
side effect of precomputing, not a fatal flaw.

1439 orders total: 720 NVDA / 719 SPY, 720 BUY / 719 SELL, always qty=5
(`qty_max=5`, matching `sim-capacity/runner.run_one`'s actual
`CapacityExerciserParams(qty_max=5)`, not `exerciser.py`'s own dataclass
default of 3 -- displayed top-of-book size never fell below 5 shares for
either symbol in this sample, so the cap always bound). One-cent collar,
baked into each order's limit price at generation time so both engines
replay byte-identical prices.

## Engine configuration

Both engines replay the identical `order_stream` (same submit times,
symbols, sides, quantities, limit prices). Fees are computed **post-hoc,
uniformly**, by `metrics.py` using sim-capacity's own
`fee_model.commission_usd(commission_plan="none")` -- neither engine's own
native fee model is used (NautilusTrader `fee_model=None`; hftbacktest
`trading_value_fee_model(0.0, 0.0)`), so "total simulated cost" means the
same thing on both sides.

| | NautilusTrader (`run_nautilus.py`) | hftbacktest (`run_hftbacktest.py`) |
|---|---|---|
| Book / feed | `BookType.L1_MBP`, QuoteTicks only (no TradeTick added -- matches sim-capacity's own H1 fix) | L1 `DEPTH_EVENT` pairs per side per quote tick (zero-old-level + set-new-level on a price change; a plain set when only size changes) -- matches `l1_feasibility.py`'s established convention |
| Venue flags | `trade_execution=True, liquidity_consumption=True, queue_position=True` (mirrors sim-capacity's `run_one` exactly; `trade_execution` is moot with no trade ticks fed) | `power_prob_queue_model(2.0)`; exchange model swept (below) |
| Latency | `StaticLatencyModel(base_latency_nanos=latency_ms*1e6)` | `constant_order_latency(latency_ns, latency_ns)` -- one value for entry **and** response |
| Account | `CASH`, 10,000,000 USD | No account/short-sale concept |
| Order | marketable `LIMIT`, `TimeInForce.IOC`, one-cent collar | `LIMIT`, `IOC`, same collar |

**Difference table** (an explicit per-engine table, not a claim of
achievable parity -- hftbacktest has no setting equivalent to
`liquidity_consumption`):

| Dimension | NautilusTrader | hftbacktest |
|---|---|---|
| Liquidity consumption across orders | `liquidity_consumption=True`: a per-price-level consumed-size tally that resets only when the displayed size at that level changes (rc5 `matching_engine/mod.rs:330-392,371-375`) | Neither exchange model decrements `self.depth` from a fill; `PartialFillExchange` caps one order at the displayed size but never depletes it for the next (Scenario I); `NoPartialFillExchange` ignores displayed size entirely on any cross (`nopartialfillexchange.rs:330-339`) |
| Latency release semantics | Released at the first of: the next quote tick on its own instrument, **or** any due clock timer, from any source | `constant_order_latency`: evaluated against the book at exactly submit + entry_latency, no "wait for a fresh quote" allowance |
| Queue position for takers | Never applied to taker fills (`matching_engine/mod.rs ~3555-3583`: `LiquiditySide::Taker`, immediate fill, `snapshot_queue_position` only on the maker branch) | `ProbQueueModel` only applies to resting (GTC/GTX) orders; moot here (IOC-only stream) |
| Aggressor side on trade prints | Moot: no TradeTick fed | Moot: no `TRADE_EVENT` built |

## Configuration matrix run

Latency sweep 70ms and 250ms on both engines; hftbacktest additionally swept
across `partial_fill_exchange` (closest available to Nautilus's consumption
semantics, per `sim-crosscheck-hftbacktest/README.md`'s own cross-check plan)
and `no_partial_fill_exchange` as a bracket -- 2 Nautilus runs + 4 hftbacktest
runs = 6 total. See `receipts/20260925-crosscheck.json`'s `config_matrix`.

## Results

Read `receipts/20260925-crosscheck.json`'s `metrics_table` for the exact,
regeneratable numbers (this table is sourced from it, not retyped by hand):

| Config | Fill rate | Rejected | Median time-to-fill | p90 | Touch share | Fees | Total sim. cost |
|---|---|---|---|---|---|---|---|
| Nautilus, 70ms | 97.64% | 3 | 111.23ms | 287.40ms | 100.0% | $35.14 | $96.17 |
| hftbacktest, 70ms, partial_fill | 75.96% | 0 | 73.33ms | 76.67ms | 66.42% | $35.02 | -$432.16 |
| hftbacktest, 70ms, no_partial_fill | 75.68% | 0 | 73.33ms | 76.67ms | 66.30% | $35.10 | -$446.88 |
| Nautilus, 250ms | 94.23% | 3 | 290.60ms | 333.33ms | 100.0% | $33.70 | $85.35 |
| hftbacktest, 250ms, partial_fill | 74.08% | 0 | 253.33ms | 256.67ms | 65.57% | $33.66 | -$438.07 |
| hftbacktest, 250ms, no_partial_fill | 74.08% | 0 | 253.33ms | 256.67ms | 65.57% | $33.66 | -$438.07 |

By symbol (fill rate; `partial_fill` shown for hftbacktest):

| Symbol | Nautilus 70ms | hftbacktest 70ms | Nautilus 250ms | hftbacktest 250ms |
|---|---|---|---|---|
| SPY | 98.33% | 98.61% | 94.71% | 94.85% |
| NVDA | 96.94% | 53.33% | 93.75% | 53.33% |

**SPY converges closely between engines at both latencies** (hftbacktest is
even marginally higher). **The entire overall fill-rate gap is concentrated
in NVDA** (81.8% relative divergence at 70ms).

### F1 -- why NVDA diverges and SPY does not (dominant effect)

NVDA has far fewer quotes than SPY over the identical window (32,786 vs
61,926) and its touch drifts roughly $0.80 over the 8 minutes -- a much
larger relative move than SPY's. NautilusTrader releases a deferred order at
the first of its own instrument's next quote **or** any due clock timer; for
a sparsely-quoted name like NVDA, the exerciser's own shared 3/sec
submit-schedule timer very often becomes the release trigger with no fresh
NVDA quote in between, so the order is frequently re-evaluated against
essentially the same touch it saw at submission (which has had no chance to
move away) -- keeping it marketable. hftbacktest's `constant_order_latency`
has no such allowance: it evaluates the order against whatever the book
literally is at exactly submit + entry_latency, catching genuine price
movement on a name that moves more than a SPY-sized single tick more often.

Supporting evidence: hftbacktest's NVDA touch-share is only ~4.4% (it rarely
fills exactly at the touch the order was generated against) versus 100% for
SPY and 100% for NVDA on Nautilus -- consistent with hftbacktest's surviving
NVDA fills being a favorably-selected subsample (the order only survives
because price already moved past the limit before the fixed latency
elapsed). This also explains NVDA's large, sign-flipped `cost_vs_mid` on
hftbacktest (~-11.5 to -12.0 bps vs Nautilus NVDA's ~+0.45 to +0.50bps): the
reference mid is captured at submit time, and a favorably-selected surviving
fill is not a fair like-for-like execution-cost comparison for that name.

**Classification: a documented model-semantics difference, not a matching
bug in either engine.**

### F2 -- a separate, smaller hftbacktest-internal artifact (NVDA, 70ms only)

At 70ms only, hftbacktest's own two exchange models disagree on 344 of 1439
orders (all NVDA, none SPY): `PartialFillExchange` fills 384/720 NVDA orders,
`NoPartialFillExchange` fills 380/720. **At 250ms the two exchange models
agree exactly** (1066/1439 filled, byte-identical) -- this artifact is
latency- and instrument-specific.

Investigated directly against the pinned tag source (`py-v2.4.4`, commit
`a244a14250b42d97fc305569c93c4117cd5e1dff`, cloned read-only to a session
scratchpad for citation, not committed): the IOC crossing check
(`order.price_tick >= self.depth.best_ask_tick()`) is textually **identical**
in `partialfillexchange.rs:396` and `nopartialfillexchange.rs:323`.
`NoPartialFillExchange` fills directly at `best_ask_tick()` on any cross
(`nopartialfillexchange.rs:334-339`); `PartialFillExchange` walks
`best_ask_tick()..=order.price_tick` checking `ask_qty_at_tick(t)` per tick
(`partialfillexchange.rs:437-452`). Direct instrumentation (submitting a
known order against both exchange models on the identical multi-asset setup
and polling `hbt.depth(0)` at the moment of resolution) showed
`PartialFillExchange`'s depth reporting the sentinel "no ask"/"no bid" values
at the **same simulated timestamp** where `NoPartialFillExchange`'s depth,
fed the byte-identical event array, reported valid, correct best-bid/ask
ticks. The exact root cause was **not** pinned to a specific line beyond
this -- since the crossing-check code itself is identical, whatever causes
this must be in code shared with or upstream of `ack_new`, not read
conclusively here.

This artifact cannot explain F1: it produces only a net 4-order difference
between hftbacktest's own two exchange models at 70ms, far smaller than
NVDA's ~340-order gap versus Nautilus, and it does not occur at all at
250ms, where the NVDA-vs-Nautilus gap is just as large.

**Classification: a suspected hftbacktest-internal inconsistency between its
two exchange models -- documented here as a probable bug. Per task policy,
not filed externally.** Proposed next steps are in
`receipts/20260925-crosscheck.json`'s `mechanistic_findings[1]
.proposed_next_steps` (a minimal reproduction for an eventual upstream
issue; prefer `no_partial_fill_exchange` for sparsely-quoted/gappy
instruments at short latency until resolved; re-check at hftbacktest's own
2026-12-23 dormancy checkpoint).

## Overturn evaluation

`sim-capacity/experiment.json`'s `next_decision_changing_test` overturn
condition: diverge by more than 20% (fill rate) or 2x (median time-to-fill),
**caused by a matching bug**.

- Fill-rate divergence **is** over 20%: 28.55% (70ms) / 27.20% (250ms)
  overall, driven almost entirely by NVDA (81.77%) with SPY inside tolerance
  (-0.28%).
- Median time-to-fill divergence is **not** over 2x at either latency
  (1.517x at 70ms, 1.147x at 250ms, including the NVDA-only breakdown at
  1.75x).
- The dominant cause of the fill-rate divergence (F1) is a documented
  model-semantics difference, not a bug. A separate, smaller effect (F2) is
  a suspected hftbacktest-internal bug, but is far too small to itself
  explain the >20% breach.

**Conclusion: diverges (fill rate, both latencies) for a documented
model-semantics reason, which is not a bug** (F1) -- median time-to-fill
stays within tolerance. **F2 is a separate, smaller suspected hftbacktest
bug, documented alongside this conclusion and not conflated with it,** per
`sim-capacity/experiment.json`'s own updated convergence record (appended,
dated entry -- history not rewritten).

## Files

- `sample.py` -- bounded SPY+NVDA sample extraction from sim-capacity's
  already-retained private cache; no network, no credentials.
- `order_stream.py` -- deterministic order-stream generator (reuses
  sim-capacity's `schedule.py`).
- `metrics.py` -- pure, engine-agnostic metric computations (fill rate,
  partial-fill share, time-to-fill percentiles, touch share, cost vs mid,
  fees via sim-capacity's `fee_model.py`).
- `run_nautilus.py` -- NautilusTrader-side driver (pinned runtime only).
- `run_hftbacktest.py` -- hftbacktest-side driver (isolated venv only).
- `crosscheck.py` -- CLI orchestrator tying the above together across the
  two incompatible runtimes (see "Running it" below).
- `receipts/20260925-crosscheck.json` -- the full receipt: sample
  definition, hashes, engine versions, config table, metrics table,
  mechanistic findings, overturn evaluation, conclusion.

## Running it

NautilusTrader and hftbacktest live in two different, mutually incompatible
Python environments, so this is split into subcommands run under each
interpreter separately, plus a final `report` step under any interpreter
(`metrics.py`/`fee_model.py` have no special dependency):

```
# 1. Bounded sample (system python; reads sim-capacity's already-retained cache)
python3 blueprints/us-equities/sim-engine-crosscheck/sample.py

# 2. Deterministic order stream (system python)
python3 blueprints/us-equities/sim-engine-crosscheck/crosscheck.py stream \
    --out PRIVATE/stream.json

# 3. NautilusTrader side (pinned runtime), one call per latency
~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python \
    blueprints/us-equities/sim-engine-crosscheck/crosscheck.py run-nautilus \
    --stream PRIVATE/stream.json --latency-ms 70 --out PRIVATE/nt_70.json

# 4. hftbacktest side (isolated venv -- see "Reproducing the hftbacktest venv"),
#    one call per (latency, exchange model)
~/.local/share/native-agent-stack/hftbacktest-2.4.4/bin/python3 \
    blueprints/us-equities/sim-engine-crosscheck/crosscheck.py run-hftbacktest \
    --stream PRIVATE/stream.json --latency-ms 70 --exchange partial_fill \
    --out PRIVATE/hft_70_partial.json

# 5. Report (any python): build a {"label": "path.json", ...} manifest of the
#    six outcome files, then:
python3 blueprints/us-equities/sim-engine-crosscheck/crosscheck.py report \
    --runs PRIVATE/runs.json --commission-plan none --out PRIVATE/report.json
```

### Reproducing the hftbacktest venv

Exactly per `sim-crosscheck-hftbacktest/README.md`'s "Pinned install":

```
uv venv --python 3.12 ~/.local/share/native-agent-stack/hftbacktest-2.4.4
uv pip sync --python ~/.local/share/native-agent-stack/hftbacktest-2.4.4/bin/python3 \
    --require-hashes blueprints/us-equities/sim-crosscheck-hftbacktest/requirements.lock
```

This task rebuilt that venv, ran the six configurations above, and **removed
it again** afterward (`rm -rf ~/.local/share/native-agent-stack/
hftbacktest-2.4.4`), matching that blueprint's own established cleanup
convention -- see `receipts/20260925-crosscheck.json`'s `cleanup` block.

Tests: `python3 -m unittest -v tests.test_sim_engine_crosscheck`. Hermetic
and synthetic throughout; the order-stream generator and metric computations
are checked with small, hand-constructed fixtures (no engine, no network, no
private sample required) and run unconditionally. Any test that would need
NautilusTrader or hftbacktest installed skips cleanly when the corresponding
interpreter/package is unavailable.

## Limitations

- Two latency points and two exchange models, on one 8-minute, 2-symbol
  sample -- not coverage of the full sim-capacity 8-symbol/30-minute universe
  or its 0/70/250/1000ms sweep.
- The precomputed stream's assumed-full-fill inventory bookkeeping produced
  3 real Nautilus REJECTEDs (0.21% of orders) where assumed and real fills
  diverged; see "Order stream" above.
- F2's root cause is reported as directly observed and reproduced, not as a
  fully traced source-line-level explanation.
- EMO/Lee-Ready aggressor-side inference was not applied: both engines
  replay quotes only here (trades are side-less on this feed for either
  engine regardless).
