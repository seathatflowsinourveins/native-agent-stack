# hftbacktest cross-check engine (Phase-B prep)

This blueprint brings in [hftbacktest](https://github.com/nkaz001/hftbacktest)
(MIT) as an independent cross-check engine for the simulation lane, alongside
(not instead of) the NautilusTrader sim-capacity work in
`blueprints/us-equities/sim-capacity/` (owned by a parallel builder; this task
does not read or modify that directory -- the reads below are `git show`
against its remote branch, from outside this worktree's tree, for citation
accuracy only).

Overturn condition this addresses (`catalogs/sota-convergence/manifest-20260922.json`
around L6317): "An intraday fixture ... where queue-position and latency
modelling changes the cost-adjusted result versus the Nautilus fee/slippage
scenarios already receipted." The simulation lane now needs intraday
execution realism at **180-900 submissions/minute** (the sim-capacity submit budgets; fills per minute are measured per run) -- verified, not just relayed:
`blueprints/us-equities/sim-capacity/experiment.json` on branch
`claude/sim-capacity-20260925` (commit `0e0740e7`, "merging soon" per the
coordinator) defines a paper-parity profile with a "180/min submit budget"
and an elite-tier profile with a "900/min submit budget", with passing
receipts for both (`receipts/20260924-paper-parity.json`,
`receipts/20260924-elite-tier.json`). hftbacktest's queue-position and
latency models are the concrete mechanism to test that against.

**Maintenance precondition -- this is DORMANCY, recorded as a risk, not a
pass.** As of 2026-09-25 (GitHub REST API, `GET /repos/nkaz001/hftbacktest`):
default branch `master` is still at `5f3ec40b2afb`, last pushed
**2025-12-23** -- about **9 months** with no push as of this check -- with
**17 open issues**, and `py-v2.4.4` remains the latest tag. This is the same
commit already reviewed in `catalogs/us-equities/architecture/trading.json`;
nothing has moved. **Overturn condition for this specific risk: if upstream
has made no commits by 2026-12-23** (a full 12 months of inactivity from the
last push), the maintenance posture should be re-scored as abandoned rather
than dormant before any further investment in this cross-check depends on
upstream fixes or releases.

## Pinned install

- Upstream: `hftbacktest` Python 2.4.4 / Rust 0.9.4, tags `py-v2.4.4` /
  `rust-v0.9.4`, commit `a244a14250b42d97fc305569c93c4117cd5e1dff`, MIT
  license, Python >=3.11 (cp312 wheels used here).
- Isolated venv: `~/.local/share/native-agent-stack/hftbacktest-2.4.4`
  (`uv venv --python 3.12`), kept outside the repository. **This venv is
  host-local and was deleted after this task's verification finished (see
  Cleanup below).** To rebuild it and reproduce anything in this README:
  ```
  uv venv --python 3.12 ~/.local/share/native-agent-stack/hftbacktest-2.4.4
  uv pip sync --python ~/.local/share/native-agent-stack/hftbacktest-2.4.4/bin/python3 \
      --require-hashes blueprints/us-equities/sim-crosscheck-hftbacktest/requirements.lock
  ```
- `requirements.lock` in this directory is a `uv pip compile --generate-hashes`
  lock for `hftbacktest==2.4.4` plus 42 further packages in its dependency
  closure (**43 packages total**: numpy 2.2.6, numba 0.67.0, polars 1.44.2,
  matplotlib/holoviews/panel/bokeh transitive stack for hftbacktest's
  built-in plotting).
- Installed wheel: `hftbacktest-2.4.4-cp312-cp312-manylinux_2_28_x86_64.whl`,
  sha256 `7df29f3f600e74cde4b7223dbc65d64caed7ae16c67dd4a85d33a5bf4e2e36b5`.
  This matches the digest PyPI's JSON API reports for that exact filename --
  a consistency check between the downloaded artifact and PyPI's own served
  record, **not independent third-party provenance**: PyPI provides no build
  attestations for this project's wheels. Upstream publishes via
  `PyO3/maturin-action@v1`'s `command: upload` step
  (`.github/workflows/release-python.yml` at the pinned tag), i.e.
  `maturin upload --non-interactive --skip-existing` authenticated with a
  maintainer-held `MATURIN_PYPI_TOKEN` GitHub Actions secret -- not `twine`,
  which an earlier version of this README said. Either way, this check would
  not catch a compromised token or account serving a tampered wheel with a
  self-consistent record.
- Supply-chain scan: `osv-scanner` CLI binary was not found on this host (only
  a GitHub Action config exists in this repo's own `.github/`); ran
  `pip-audit 2.10.1` via `uv tool run pip-audit -r requirements.lock
  --disable-pip --no-deps --format json` instead. **Result: 0 known
  vulnerabilities across all 43 pinned packages.** An earlier version of this
  README ran plain `pip-audit -r requirements.lock` (without those flags),
  which only enumerated 42 of the 43 packages -- it silently skipped
  `packaging`. `--disable-pip --no-deps` makes pip-audit resolve directly
  from the lock file's own pins instead of re-resolving via pip, which is
  what brings `packaging` into scope; this is the actually-run, corrected
  result, not merely a relayed claim.

See `receipt.json` for exact commands, exit codes, hashes, working
directories and the evidence class of each item (per
`docs/acceptance-evidence-policy.md`).

## Upstream's own tests, at the pinned tag

- **Python**: `py-hftbacktest/tests/test_hftbacktest.py` is upstream's only
  Python test file. It requires a private/undistributed fixture
  (`tmp_20240501.npz`) not present in the tagged source tree and not fetched
  by any script or CI workflow at this tag. Running it gives
  `FileNotFoundError: 'tmp_20240501.npz'`, exit code 1. The repository's own
  CI at this tag (`release-python.yml`, `codeql.yml`, `stale.yml`) never runs
  a Python test suite -- only `maturin build`/`upload` steps.
- **Rust toolchain**: installed with the supported user-level method
  (`rustup-init.sh -y --profile minimal --no-modify-path`) -- `rustc 1.98.1`,
  `cargo 1.98.1`, `rustup 1.29.1`, satisfying the crate's pinned
  `rust-version = "1.91.1"`. No `rust-toolchain.toml`/`rust-toolchain` file
  exists anywhere in the tagged tree, and no Cargo.lock is committed either
  (`.gitignore` has `**/Cargo.lock`; confirmed with `git ls-files Cargo.lock`
  returning nothing before any build). The Cargo.lock generated by this
  task's own build (sha256 `908990e1951581638307122bbaa8555314a125ee07c51462ed7662ae2023b6f4`,
  4663 lines) is a host-local artifact, not committed here; `cargo tree -p
  hftbacktest --no-default-features --features backtest` resolves 144 lines
  of transitive dependencies, with direct deps anyhow 1.0.104, bincode 2.0.1,
  dyn-clone 1.0.20, hftbacktest-derive 0.2.0, nom 8.0.0, thiserror 2.0.21,
  tracing 0.1.44, uuid 1.26.1, zip 6.0.0. **This toolchain was also deleted
  after verification** (`rustup self uninstall -y`; see Cleanup).
- **`cargo test -p hftbacktest`, default features (`backtest`+`live`): fails
  to build.** The `live` feature (live-trading IPC) pulls in
  `iceoryx2-pal-posix`, whose build script needs `bindgen`/`libclang` plus
  reachable C headers; neither was available on this host and there is no
  passwordless sudo to install `libclang-dev`.
- **`cargo test -p hftbacktest --no-default-features --features backtest`
  (still without `--lib`): ALSO fails to build -- on SIX examples, not four,
  and installing libclang alone would not fix it.** `gridtrading_live`,
  `logging_order_latency`, `gridtrading_live_bybit`, and
  `live_order_error_handling` all reference the `live` feature's API without
  an upstream `required-features = ["live"]` guard, so they are attempted
  even with `backtest` alone and fail without `live`. `custom_evhandling`
  calls `process_recv_order2`, a method that does not exist on the current
  `Local` struct (`E0599`) -- genuine upstream API drift, unrelated to
  `live`/libclang. `algo.rs` fails with `E0601` (no `main` function), but
  this is **a packaging issue, not API drift**: `algo.rs` defines
  `pub fn gridtrading(...)`, a shared helper with no `main` at all, and six
  other examples (`gridtrading_live.rs`, `gridtrading_backtest_args.rs`,
  `logging_order_latency.rs`, `gridtrading_backtest.rs`,
  `live_order_error_handling.rs`, `gridtrading_live_bybit.rs`) include it via
  `mod algo;`. Cargo's `examples/` directory auto-discovery *also*
  independently treats `algo.rs` itself as its own example target (every
  top-level `.rs` file directly under `examples/` becomes an example binary
  by default), which is what fails to compile -- upstream never gave it a
  `main`, nor excluded it from auto-discovery (e.g. by moving it to
  `examples/common/` or marking it `required-features` with something
  impossible). Two of six failures (`algo`, `custom_evhandling`) are thus
  unrelated to the `live` feature or to libclang either way.
- **`cargo test -p hftbacktest --no-default-features --features backtest
  --lib`: passes, 22 passed, 0 failed, 0 ignored.** `--lib` isolates the
  crate's actual unit-test suite from the example-build breakage above.
  Source files: **7, not 8** -- an earlier version of this README miscounted
  by including `connector/src/utils.rs`'s 5 `#[test]` functions, which live
  in the separate `connector` crate, excluded by `-p hftbacktest`. The 7
  files actually run: `hftbacktest/src/types.rs`, `backtest/mod.rs`,
  `backtest/models/queue.rs`,
  `depth/{btreemarketdepth,hashmapmarketdepth,roivectormarketdepth,fuse}.rs`.
  No workflow in `.github/workflows/` at this tag runs `cargo test` at all.
  - **What these 22 tests do NOT cover**: hftbacktest's exchange fill logic
    (`NoPartialFillExchange`/`PartialFillExchange`, `ack_new`,
    `check_if_buy_filled`/`check_if_sell_filled`,
    `on_best_bid_update`/`on_best_ask_update` -- `backtest/proc/*.rs` has
    zero `#[test]` functions of its own); IOC/FOK/GTX time-in-force
    handling; `ProbQueueModel` or `RiskAdverseQueueModel` (only the
    unrelated `L3FIFOQueueModel`'s `l3_tests` module has unit tests); or the
    **L2 depth-update path this fixture's `qty=0`-removes-a-level
    representation actually depends on**
    (`HashMapMarketDepth::update_bid_depth`/`update_ask_depth`,
    `hashmapmarketdepth.rs` ~lines 86/141 -- untested; only a *different*
    struct, `Fuse`, has `update_bid_depth`/`update_ask_depth` unit tests, in
    `fuse.rs`). All of that coverage in this cross-check comes from **our
    own synthetic fixture** below.
  - `--lib` also excludes 2 doctests (`types.rs` ~line 461; `latency.rs`
    ~line 89) that `cargo test --doc` would run.
  - Wall time: 0.145s (bash `time`), but this was an **incremental** build
    (dependencies already compiled by the immediately preceding failed
    attempts), not a from-clean-checkout timing.
  - The recorded gap "upstream Rust tests never run" is closed for the
    crate's unit-test suite specifically; the `live`-feature,
    `custom_evhandling`, and `algo` build gaps remain open.

## L1 (top-of-book) feasibility

Alpaca's consolidated SIP feed gives best-bid/best-ask quotes and trade
prints with **no depth beyond the touch and no trade aggressor side**.

**Representation used** (see `l1_feasibility.py`'s module docstring for the
full reasoning, with source citations):

- Each top-of-book quote update is a pair of `DEPTH_EVENT` events: one that
  sets `qty=0` at the *old* best price on that side, one that sets a
  positive `qty` at the *new* best price. This is exact single-level
  replacement for the best bid/offer **PRICE and SIZE**. It is **NOT**
  exact for queue **POSITION** (Scenario E) or for cross-order liquidity
  **DEPLETION** (Scenario I).
- Each trade print is a bare `TRADE_EVENT` with **no** `BUY_EVENT`/`SELL_EVENT`
  bit.

**What a side-less `TRADE_EVENT` actually loses**: hftbacktest's exchange
models reach `check_if_buy_filled`/`check_if_sell_filled` -- which cover
BOTH (a) an unconditional "trade-through" fill when a trade price crosses
clean through a resting order's price, AND (b) trade-driven queue-position
depletion when a trade prints exactly at the order's price -- only via the
side-tagged `EXCH_BUY_TRADE_EVENT`/`EXCH_SELL_TRADE_EVENT` dispatch arms. A
bare `TRADE_EVENT` reaches **neither** path. Depth-quantity events
(`on_bid_qty_chg`/`on_ask_qty_chg`) still update the queue model's internal
position estimate, but **nothing in that call path ever invokes
`is_filled()`** -- depth changes alone never fill a resting order (Scenario
D2). On raw L1 data, a passive order can be filled **only** by the opposite
quote *reaching or crossing* its price (Scenario D3 -- the condition is
`order.price_tick >= new_best_tick` for a resting buy, so the quote landing
exactly on the order's price is enough; it does not need to cross past it,
correcting an earlier version of this README that said "crossing through").

**Verdict: feasible-with-limits.** Checked under both exchange models --
with genuinely **different** results once order size exceeds the touch's
quoted size (Scenario F, Scenario G2) or across sequential orders at a
constant quoted size (Scenario I); they only coincide on Scenarios A-D and
G1/G3/G4 -- **not "A-D and G"** (an earlier version of this README and
receipt said that; G2, the oversized FOK, genuinely diverges and the
fixture's own `scenario_g2_fok_insufficient_diverges_between_exchange_models`
flag is `true`).

### Feasible (run, not just claimed -- see `receipt.json` for exact commands and output)

- **Scenario A/B**: marketable IOC crossing fills at the touch; IOC expires
  when the touch moves away before arrival. Decided purely from depth.
- **Scenario D3**: a resting order fills when the *opposite* quote reaches
  or crosses its price -- purely depth-driven, no trade data at all.
- **Scenario G1/G3/G4**: IOC/FOK/GTX time-in-force, actually run: crossing
  IOC/FOK fill fully under `NoPartialFillExchange` regardless of size
  (G1, sufficient depth); a crossing GTX order is **Expired**, never a
  distinct "Rejected" status, in either exchange model (G3); a non-crossing
  GTX rests exactly like GTC (G4).
- **Scenario H**: `TradingValueFeeModel` with a **nonzero** taker fee
  (0.1%) produces `state_values(...).fee == exec_price * exec_qty *
  taker_fee` exactly.
- Constant order latency, independent of depth granularity.

### Not feasible, or meaningless, on L1-only data (run, not just claimed)

- **Scenario C / D1**: any trade-driven fill path requires an aggressor
  side. A bare `TRADE_EVENT` matches neither `EXCH_BUY_TRADE_EVENT` nor
  `EXCH_SELL_TRADE_EVENT` and is dropped before either path is reached, in
  **both** exchange models.
- **Scenario D2**: depth driven to zero at a resting order's own price, with
  no trade at all, does **not** fill it -- `NEW` in every run.
- **Scenario E (HAND-VERIFIED)**: a buy resting away from the touch, at a
  price L1 has never quoted, is accepted with **zero** quantity ahead of it.
  `ProbQueueModel.depth()` has an early-return path for a quantity increase
  that never touches its probability formula at all, so this is exactly
  hand-computable, not merely observed: `front_q_qty` starts at 0 (nothing
  was ever quoted at that price), stays 0 when the bid re-quotes there
  showing 50 shares (the early-return path: `min(0, 50) = 0`), and a single
  5-share sell-aggressor print then fully fills the order
  (`is_filled() = round(5/1) = 5 > 0`). Once the market reaches that price, a
  tiny print can fill an order "queued" behind a much larger display. This
  will skew fill rate, time-to-fill and touch-share comparisons for any
  order that spends time resting away from the touch.
- **Scenario F**: `NoPartialFillExchange` fills a 150-share IOC in full
  against a 100-share touch; `PartialFillExchange` executes only the 100
  available and marks the order `Expired` -- but `exec_qty` is still 100,
  not 0, because the partial fill already applied to state before the
  terminal status was set to `Expired`. This "status understates the fill"
  caveat is **IOC-specific**: Scenario G2's FOK-with-insufficient-depth case
  correctly expires with `exec_qty` exactly 0 under `PartialFillExchange`
  (all-or-none by construction, computed and checked BEFORE any execution),
  so `status` does not understate anything there.
- **Scenario I (PartialFillExchange's no-depletion bias, new this round)**:
  three back-to-back 100-share IOCs against a touch that **always shows
  exactly 100 shares** (never re-quoted) all **FILL IN FULL** under
  `partial_fill_exchange`, for a cumulative position of **300**. Upstream's
  own doc comment says this explicitly: "Liquidity-taking orders will be
  executed based on the quantity of the order book, **even though the best
  price and quantity do not change due to your execution**. Be aware that
  this may cause unrealistic fill simulations if you attempt to execute a
  large quantity" (`partialfillexchange.rs` ~lines 66-69). `PartialFillExchange`
  caps a *single* order's fill at the touch's displayed size, but never
  actually depletes that display for the *next* order -- so calling it
  "realistic" (an earlier version of this README implied this by contrasting
  it favorably with `NoPartialFillExchange`) overstates what it does at a
  high submission rate. This is a **different** bias from Scenario E (which
  is about queue POSITION on a fresh price); this one is about the exchange
  model never depleting quoted SIZE across orders, at any price.
- The L3 FIFO queue model (needs per-order `order_id`-level events) and any
  multi-level queue heuristic: categorically unavailable from L1 data.

### Not exercised (moved here explicitly, not left implied as covered)

- `IntpOrderLatency` (interpolated/recorded-data latency) and per-symbol
  latency variation.
- `FlatPerTradeFeeModel` / `TradingQtyFeeModel`.
- `L3FIFOQueueModel` and `RiskAdverseQueueModel` (a **conservative**
  queue-position estimator, per upstream's own naming) -- only
  `ProbQueueModel` (`power_prob_queue_model`) was exercised. Scenario E's
  bias almost certainly generalizes to `RiskAdverseQueueModel` too (its
  `new_order()` has the identical zero-queue-ahead-on-a-fresh-price
  behavior, `queue.rs` ~lines 67-74), but this was not separately measured.

## Aggressor-side inference: EMO and Lee-Ready, offered separately

An earlier version of this fixture implemented the rule "trade at/above ask
-> buy; at/below bid -> sell; else tick test" and called it **Lee-Ready**.
That was wrong on two counts, both now fixed:

1. **Rule identity.** This is the **Ellis-Michaely-O'Hara (EMO) "at-quote"
   rule** (Ellis, Michaely & O'Hara, 2000, *Journal of Financial and
   Quantitative Analysis*, "The Accuracy of Trade Classification Rules:
   Evidence from Nasdaq"), which compares to the raw bid/ask. The actual
   **Lee-Ready** rule (Lee & Ready, 1991, *Journal of Finance*, "Inferring
   Trade Direction from Intraday Data") compares to the bid-ask **midpoint**
   instead. Both are implemented and offered separately here
   (`infer_side_emo`, `infer_side_lee_ready`).
2. **Citation and rule scope.** An earlier version cited "NBER Working Paper
   No. 14158 (Diether, Lee & Werner)" and called it a literature review.
   Verified directly against the paper's own NBER page metadata: it is
   **Asquith, Oman & Safaya, 2008**, "Short Sales and Trade Classification
   Algorithms" -- a study of how often these classification rules
   misclassify *short sales* specifically, not a general literature review
   (it does apply and compare EMO, Lee-Ready and the tick test as part of
   that study, which is why it's still the right citation for "these rules
   exist and get compared to each other"). Also, EMO's own at-quote
   condition is **equality**, not `>=`/`<=`: an earlier version applied the
   quote rule to any print at-or-beyond a quote; it now applies ONLY to
   prints EXACTLY at the bid or ask, and sends everything else -- including
   prints strictly inside the spread AND prints outside the quotes
   entirely (above the ask or below the bid, which can happen with
   stale/late quotes or off-exchange prints) -- to the tick test.
   `run_emo_boundary_demo()` exercises this directly: a print at the ask is
   `buy` (direct); one strictly above the ask falls to the tick test
   (happens to also resolve `buy` here, but via the fallback, not the
   at-quote condition); one strictly below the bid likewise falls to the
   tick test.

Both rules share a corrected tick-test fallback (`_tick_test`): a "zero
tick" (price unchanged from the immediately preceding trade) reuses the
**last known direction** across any number of consecutive flat prints,
rather than losing its classification. `run_tick_test_coverage_demo()` runs
a 6-print tape designed so both rules' tick-test fallback genuinely
executes, a flat-tick run demonstrates direction reuse, and -- concretely --
**EMO and Lee-Ready disagree** on one print (strictly inside the spread,
above the midpoint, arriving as a downtick): EMO's tick-test fallback says
`sell`; Lee-Ready's direct midpoint rule says `buy`. This tape's outcomes
are unaffected by the exact-quote fix (its only at-quote prints were
already exactly at the bid/ask).

**Does inference actually restore fills? Run, not assumed.** Applied to
Scenario C's original trade tape (all prints exactly at the bid), both rules
classify every trade as a sell aggressor, restoring the `FILLED` result from
`with_side=True`. An earlier version of this receipt separately claimed
inference "restores trade-through fills" on the D1 tape **without ever
running it**. This is now actually run
(`run_scenario_d1_with_inferred_side()`): the D1 print (9.99) is *outside*
the quotes (below the bid, not at it), so a bare, history-less tape would
give EMO nothing to classify it from (tick test needs a prior price); adding
one unambiguous seed trade at the ask first gives the tick test a genuine
prior price, and the 9.99 print is then correctly classified `sell` (a
downtick) -- which does restore the trade-through fill (`FILLED`,
`exec_qty=5.0`). This is shown only on hand-constructed synthetic tapes, not
validated against real Alpaca SIP data.

Run it yourself (after rebuilding the venv per "Pinned install" above):

```
source ~/.local/share/native-agent-stack/hftbacktest-2.4.4/bin/activate
python3 blueprints/us-equities/sim-crosscheck-hftbacktest/l1_feasibility.py
```

## Cross-check plan against the NautilusTrader sim-capacity run

Not yet run (`blueprints/us-equities/sim-capacity/` is not merged to `main`
at the time of this task; not read into or modified in this worktree, only
inspected via `git show` against its remote branch for citation accuracy).
**Verified configuration on that branch** (`claude/sim-capacity-20260925`,
commit `0e0740e7`, `runner.py`): `book_type=BookType.L1_MBP,
trade_execution=True, liquidity_consumption=True, queue_position=True`, and
it replays both `QuoteTick` and `TradeTick` (each `TradeTick` tagged
`AggressorSide.NO_AGGRESSOR` -- the same real-world SIP limitation this
blueprint's own hftbacktest side documents; "quotes-only replay" was
mentioned by the coordinator but not confirmed at the commit inspected
here). The older `sim-paper-compare` lane used
`liquidity_consumption=False, queue_position=False`
(`blueprints/us-equities/sim-paper-compare/replay_compare.py`).

**Update (coordinator, 2026-09-25): the sim-capacity configuration changed
after `0e0740e7`.** From `f47160b7` onward its runner feeds the matching
engine **quotes only**. Trades are still fetched and written to its private
catalog, but they are not added to the engine. The reason: in rc5 a trade
tick on an L1 book overwrites both sides with the print's price and size, and
a `NO_AGGRESSOR` trade leaves that locked book in place until the next quote.
With trades in the feed, 41% of the exerciser's IOC fills beat the NBBO
touch; with quotes only, none do. For its IOC-taker exerciser,
`queue_position` and `trade_execution` had no measured effect. The
cross-check below must use the sim-capacity commit that merges to `main`,
and compare against its quotes-only engine feed.

**A comparison that leaves these settings unmatched measures configuration,
not engines.** hftbacktest has no single setting equivalent to Nautilus's
`liquidity_consumption` -- neither exchange model actually depletes quoted
depth across sequential orders (Scenario I shows `PartialFillExchange`
doesn't; `NoPartialFillExchange` doesn't either, by design). The plan is an
explicit per-engine difference table, not a claim that either engine can be
configured to match the other exactly:

| Dimension | NautilusTrader (sim-capacity, verified) | hftbacktest (this cross-check) |
| --- | --- | --- |
| Liquidity consumption across orders | `liquidity_consumption=True`. The book itself is not decremented: `apply_liquidity_consumption` (rc5 `matching_engine/mod.rs:330-392`) keeps a separate consumed-size tally per price level, and that tally resets whenever the displayed size at the level changes | Neither exchange model decrements `self.depth` from a fill (Scenario I); closest available choice is `PartialFillExchange`, which at least caps a single order at the displayed size |
| Queue position for takers | Not applied at all for taker fills: `crates/execution/src/matching_engine/mod.rs` (`v2.0.0rc5`, ~lines 3555-3583) sets `LiquiditySide::Taker` and fills immediately WITHOUT calling `snapshot_queue_position`; that call only happens in the passive/maker branch | `ProbQueueModel` is consulted for RESTING orders only; a fresh L1 price starts at zero queue-ahead (Scenario E) -- also taker-irrelevant, but for a different reason (no notion of "ahead" for an immediate fill at all, vs. hftbacktest's zero-history assumption for passive orders) |
| Queue position for resting orders | `queue_position=True` on sim-capacity's branch (the older sim-paper-compare lane had it `False`) | `power_prob_queue_model` always on in this fixture; Scenario E's bias applies |
| Aggressor side on trade prints | `AggressorSide.NO_AGGRESSOR` (verified in sim-capacity's `runner.py`) | Bare `TRADE_EVENT`, no side bit -- same underlying SIP limitation, same absence, independently confirmed on both engines |

Given this, the plan:

1. Reuse a bounded, already-retained private-SIP sample (5 minutes, 2
   symbols) rather than acquiring new market data.
2. Convert its Alpaca SIP best-bid/ask and trade stream to hftbacktest's
   L1 representation above, optionally with an EMO/Lee-Ready-inferred side.
3. Run hftbacktest with `partial_fill_exchange` -- the configuration
   **closest to** Nautilus's consumption semantics available in hftbacktest,
   not equivalent to it (see the difference table); a **latency sweep** (not
   a single point -- the 69.2ms figure in `sim-paper-compare`'s receipt is
   explicitly labeled "Sensitivity check, not a calibration"); and
   `power_prob_queue_model`, with Scenario E's bias flagged as a known,
   uncorrected skew for orders resting away from the touch, and Scenario I's
   no-depletion bias flagged as a known, uncorrected skew at high submission
   rates against a constant-size touch.
4. Compare against the sim-capacity run's own output on: **fill rate**,
   **median time-to-fill**, **fill share at the touch**, and **cost** (fees +
   realized slippage vs. decision price) -- reading the difference table
   above alongside any gap, since some of it will be attributable to
   configuration asymmetry the two engines cannot fully eliminate, not to
   the underlying market data or strategy.

## Files

- `requirements.lock` -- pinned, hashed dependency closure (43 packages).
- `l1_feasibility.py` -- the synthetic L1 feasibility fixture (Scenarios A-I).
- `receipt.json` -- compact evidence-class-tagged receipt: commands, exit
  codes, working directories, versions, hashes, stdout hashes.
- `tests/test_sim_crosscheck_hftbacktest.py` (repository root, not inside this
  directory) -- hermetic tests, at the repository's top-level `tests/`
  directory. An earlier version of this file lived in a blueprint-local
  `tests/` subdirectory and never actually ran in CI; the verified cause
  (reproduced with a minimal example) is that `blueprints/` has no
  `__init__.py` anywhere under it, so `python3 -m unittest`'s bare,
  package-based discovery from the repo root never descends into that path
  at all -- not a dotted-name collision with the top-level `tests` package,
  which an earlier version of this README and the test file's own docstring
  incorrectly claimed. Skips cleanly when `hftbacktest` is not importable on
  the running interpreter; its structure-only and pure-Python classification
  tests run unconditionally and do not require the engine.

## Cleanup (host state this task created, per docs/harness-defaults.md)

**Executed** (dates below; the commands are in
`receipt.json`'s `cleanup` block, without exit codes (none were recorded), which an earlier version of this receipt
left saying "not yet run" after the removal had actually already happened --
that was a stale record, now corrected):

- `rm -rf ~/.local/share/native-agent-stack/hftbacktest-2.4.4` -- run
  2026-09-25 after the second fix round's verification, then the venv was
  **rebuilt** for this (third) fix round's own re-verification (pip-audit
  re-run, new scenarios I/D1-inferred-side, moved-test re-run), and **removed
  again** after this round's verification completed, same command, same day.
- `rm -rf /tmp/libclang-venv` -- run 2026-09-25 (not rebuilt this round; not
  needed, since no Rust work was done in this fix round).
- `$HOME/.cargo/bin/rustup self uninstall -y` -- run 2026-09-25, removing
  `~/.rustup` and `~/.cargo` entirely (not reinstalled this round).
- The scratch clone of `hftbacktest-src` and its `CARGO_TARGET_DIR`, both
  under a session scratchpad (already outside the repository; not this
  task's responsibility to manage further).

None of the above is referenced by anything committed to this repository.

## Unverified / open risks

- `cargo test -p hftbacktest` with **default** features, or even
  `--no-default-features --features backtest` **without** `--lib`: blocked
  by both the `live` feature's libclang/C-header gap AND two examples
  (`algo` -- a packaging issue, not API drift -- and `custom_evhandling`,
  genuine API drift) broken independent of any feature flag.
- `cargo test --doc` (2 doctests, excluded by `--lib`).
- `osv-scanner` CLI scan itself (binary absent on this host; `pip-audit`
  with `--disable-pip --no-deps` substituted, now covering all 43 packages).
- The actual numeric cross-check against sim-capacity's output (that lane is
  not merged to `main` yet).
- `IntpOrderLatency`/per-symbol latency, `FlatPerTradeFeeModel`/
  `TradingQtyFeeModel`, `L3FIFOQueueModel`/`RiskAdverseQueueModel` -- moved
  to "not exercised" rather than claimed covered.
- Real-world accuracy of the EMO/Lee-Ready aggressor-side inference on
  actual Alpaca SIP data (only demonstrated on hand-constructed synthetic
  tapes here).
- Whether upstream is dormant-but-maintained or effectively abandoned: the
  2026-12-23 no-further-commits checkpoint above is the concrete re-check
  point, not yet reached.
