# hftbacktest cross-check engine (Phase-B prep)

This blueprint brings in [hftbacktest](https://github.com/nkaz001/hftbacktest)
(MIT) as an independent cross-check engine for the simulation lane, alongside
(not instead of) the NautilusTrader sim-capacity work in
`blueprints/us-equities/sim-capacity/` (owned by a parallel builder; this task
does not read or modify that directory).

Overturn condition this addresses (`catalogs/sota-convergence/manifest-20260922.json`
around L6317): "An intraday fixture ... where queue-position and latency
modelling changes the cost-adjusted result versus the Nautilus fee/slippage
scenarios already receipted." The simulation lane now needs intraday
execution realism at 180-900 fills/minute; hftbacktest's queue-position and
latency models are the concrete mechanism to test that against.

## Pinned install

- Upstream: `hftbacktest` Python 2.4.4 / Rust 0.9.4, tags `py-v2.4.4` /
  `rust-v0.9.4`, commit `a244a14250b42d97fc305569c93c4117cd5e1dff`, MIT
  license, Python >=3.11 (cp312 wheels used here).
- Isolated venv: `~/.local/share/native-agent-stack/hftbacktest-2.4.4`
  (`uv venv --python 3.12`), kept outside the repository per
  `docs/secret-storage.md`-style host-state hygiene (nothing sensitive here,
  just a large binary-wheel venv that does not belong in git).
- `requirements.lock` in this directory is a `uv pip compile --generate-hashes`
  lock for `hftbacktest==2.4.4` and its full dependency closure (42 packages:
  numpy 2.2.6, numba 0.67.0, polars 1.44.2, matplotlib/holoviews/panel/bokeh
  transitive stack for hftbacktest's built-in plotting). Installed with
  `uv pip sync --require-hashes requirements.lock`.
- Installed wheel: `hftbacktest-2.4.4-cp312-cp312-manylinux_2_28_x86_64.whl`,
  sha256 `7df29f3f600e74cde4b7223dbc65d64caed7ae16c67dd4a85d33a5bf4e2e36b5`
  (matches the digest PyPI's JSON API reports for that file).
- Supply-chain scan: `osv-scanner` CLI binary was not found on this host (only
  a GitHub Action config exists in this repo's own `.github/`); ran
  `pip-audit 2.10.1` against `requirements.lock` instead and recorded that
  substitution explicitly. Result: **0 known vulnerabilities across the 42
  scanned dependencies**.

See `receipt.json` for exact commands, exit codes, hashes and the evidence
class of each item (per `docs/acceptance-evidence-policy.md`).

## Upstream's own tests, at the pinned tag

- **Python**: `py-hftbacktest/tests/test_hftbacktest.py` is upstream's only
  Python test file. It requires a private/undistributed fixture
  (`tmp_20240501.npz`) that is not present in the tagged source tree and is
  not fetched by any script or CI workflow at this tag. Running it with the
  pinned venv's interpreter gives `FileNotFoundError: 'tmp_20240501.npz'`,
  exit code 1. Separately, the repository's `.github/workflows/` at this tag
  (`release-python.yml`, `codeql.yml`, `stale.yml`) contains no job that runs
  a Python test suite at all -- only `maturin build` steps. That is: upstream
  currently ships one untestable-without-private-data unittest and no
  CI-executed Python test suite for this release, which we recorded rather
  than substituting an easier check for it.
- **Rust**: the `hftbacktest` crate has `#[test]` functions in 8 files,
  including `hftbacktest/src/backtest/models/queue.rs` and the four
  `hftbacktest/src/depth/*.rs` market-depth implementations this cross-check
  relies on. A Rust toolchain was installed with the supported user-level
  method (`rustup-init.sh -y --profile minimal --no-modify-path`, into
  `~/.rustup`/`~/.cargo`, shell profile untouched) -- `rustc 1.98.1`,
  `cargo 1.98.1`, `rustup 1.29.1`, satisfying the crate's pinned
  `rust-version = "1.91.1"`.
  - `cargo test -p hftbacktest` (default features `backtest`+`live`) fails to
    **build**: the `live` feature (live-trading IPC, unrelated to
    backtesting) pulls in `iceoryx2-pal-posix`, whose build script needs
    `bindgen`/`libclang` plus reachable C standard headers; neither was
    available on this host and there is no passwordless sudo to install
    `libclang-dev`. Recorded as an environment gap for the `live` feature
    specifically, not swept aside.
  - `cargo test -p hftbacktest --no-default-features --features backtest --lib`
    **passes: 22 passed, 0 failed, 0 ignored**, wall time 0.145s. This is the
    crate's actual unit-test suite (`--lib`, excluding `examples/`, several of
    which reference the `live` feature's API without an upstream
    `required-features = ["live"]` guard and so fail to *compile* -- not
    fail as tests -- without that feature; an upstream packaging gap, not
    something introduced here). No workflow in `.github/workflows/` at this
    tag runs `cargo test` at all, so there was no CI command to mirror; this
    is the crate's own unmodified `#[test]` functions run directly.
  - The recorded gap "upstream Rust tests never run" is now closed for the
    crate's unit-test suite; the `live`-feature build gap remains open (see
    `receipt.json`'s `unverified` list).

## L1 (top-of-book) feasibility

Alpaca's consolidated SIP feed gives best-bid/best-ask quotes and trade
prints with **no depth beyond the touch and no trade aggressor side**. This
is a materially thinner feed than hftbacktest's usual crypto L2/L3 or
Databento L3 inputs, so feasibility had to be checked, not assumed.

**Representation used** (see `l1_feasibility.py`'s module docstring for the
full reasoning, with source citations):

- Each top-of-book quote update is a pair of `DEPTH_EVENT` events: one that
  sets `qty=0` at the *old* best price on that side (hftbacktest's own format,
  `docs/data.rst`, documents `qty==0` as "remove this price level"), and one
  that sets a positive `qty` at the *new* best price. This is exact
  single-level replacement because at most one level per side is ever live.
- Each trade print is a bare `TRADE_EVENT` with **no** `BUY_EVENT`/`SELL_EVENT`
  bit, because the SIP tape carries no aggressor side.

**Verdict: feasible-with-limits.** Checked under both exchange models
hftbacktest exposes -- `no_partial_fill_exchange` and `partial_fill_exchange`
-- with an identical result on this fixture (see below).

Feasible (verified against hand-computed expectations, `l1_feasibility.py`,
run via `tests/test_sim_crosscheck_hftbacktest.py`, under both exchange models):

- Marketable IOC/limit fills and IOC/FOK expiry are decided in `ack_new`
  (`nopartialfillexchange.rs` and `partialfillexchange.rs`) purely from
  best-bid/best-ask depth at order-arrival time. Scenario A (order crosses
  the touch, ask unchanged) fills at the prevailing ask; Scenario B (ask
  re-quotes away during the order's 70ms entry latency) expires. Both
  matched hand computation exactly under both exchange models.
- Constant (and, separately, interpolated-from-recorded-data) latency models
  are independent of depth granularity and work unmodified on L1 data.
- Fee/cost accounting (`FlatPerTradeFeeModel`/`TradingValueFeeModel`) applies
  to realized fills regardless of feed depth.

Not feasible, or meaningless, on L1-only data (also verified empirically, not
just asserted -- Scenario C, under both exchange models):

- Probabilistic queue-position models (RiskAdverse/Power/Log) deplete a
  resting order's queue position from trade prints via
  `EXCH_BUY_TRADE_EVENT`/`EXCH_SELL_TRADE_EVENT` -- i.e. only when the trade
  event itself carries an aggressor side. A bare `TRADE_EVENT` (our L1/SIP
  reality) matches neither branch in either exchange model's source and is
  silently dropped: `queue_model.trade()` is never called. Scenario C ran the
  identical resting order and identical trade volume with and without a side
  bit, under both `no_partial_fill_exchange` and `partial_fill_exchange`:
  `with_side` filled from queue depletion in both; `without_side` stayed
  `NEW` in both for the entire run. Depth-quantity-change events
  (`on_bid_qty_chg`) still drive the queue model's `depth()` callback either
  way, but that is a materially different (coarser, level-quantity-only)
  signal than trade-driven queue consumption.
- The L3 FIFO queue model needs per-order add/cancel/execute events
  (`order_id`-level); categorically unavailable from L1 or even standard L2
  SIP quotes.
- Any multi-level queue heuristic that reads levels beyond the touch: our L1
  feed only ever has one live level per side.

**Does the verdict change under `PartialFillExchange`? No, not on this
fixture.** All three scenarios produced byte-identical results
(`order_status`/`exec_qty`/`leaves_qty`) under `no_partial_fill_exchange` and
`partial_fill_exchange`. This is expected here: every scenario's single L1
level has enough quantity (100) to fully satisfy the order (10 or 5), so
`PartialFillExchange`'s distinguishing behavior (partial fills when the
touch's quoted size is smaller than the order) never activates. A fixture
where order size exceeds the touch's quoted size would be needed to actually
exercise the divergence between the two models; that remains an open gap
(see `receipt.json`'s `unverified` list), not claimed to be covered here.

**Restoring trade-driven queue depletion from L1 data (proposed data
preparation, not an hftbacktest feature).** `run_scenario_c_lee_ready` infers
each trade's aggressor side with the Lee-Ready quote rule (trade price >=
ask -> buy; <= bid -> sell; otherwise the tick test against the previous
trade) before applying a `BUY_EVENT`/`SELL_EVENT` bit. In this fixture every
trade prints at the bid (10.00 <= bid 10.00), so Lee-Ready classifies all 5
as sell aggressors -- exactly matching Scenario C's `with_side=True` case,
and restoring the `FILLED` result versus the side-less `NEW`. This is a
classic market-microstructure heuristic (Lee & Ready, 1991), presented here
as a proposed conversion step for real SIP data, not validated against real
Alpaca SIP data's actual (unobserved) aggressor side -- that accuracy is
unverified (see `receipt.json`).

Run it yourself:

```
source ~/.local/share/native-agent-stack/hftbacktest-2.4.4/bin/activate
python3 blueprints/us-equities/sim-crosscheck-hftbacktest/l1_feasibility.py
```

## Cross-check plan against the NautilusTrader sim-capacity run

Not yet run (`blueprints/us-equities/sim-capacity/` did not exist as
committed work in this worktree at the time of this task, and is explicitly
out of scope here). The plan, once it lands on `main`:

1. Reuse a bounded, already-retained private-SIP sample (5 minutes, 2
   symbols) rather than acquiring new market data.
2. Convert its Alpaca SIP best-bid/ask and trade stream to hftbacktest's
   L1 representation above.
3. Run hftbacktest with `no_partial_fill_exchange`, `constant_order_latency`
   seeded at 69.2ms (the measured flip in
   `blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json`),
   and the queue model this feasibility check found usable at L1.
4. Compare against the sim-capacity run's own output on: **fill rate**,
   **median time-to-fill**, **fill share at the touch**, and **cost** (fees +
   realized slippage vs. decision price).

## Files

- `requirements.lock` -- pinned, hashed dependency closure (`uv pip compile
  --generate-hashes`).
- `l1_feasibility.py` -- the synthetic L1 feasibility fixture (Scenarios A/B/C).
- `receipt.json` -- compact evidence-class-tagged receipt: commands, exit
  codes, versions, hashes, stdout hashes.
- `tests/test_sim_crosscheck_hftbacktest.py` -- hermetic tests; skip cleanly
  when `hftbacktest` is not importable on the running interpreter (it lives in
  the isolated venv above, not the repository's own CI Python).

## Unverified / open risks

- `cargo test -p hftbacktest` with **default** features (`backtest`+`live`):
  blocked by a missing libclang/C-header toolchain for the `live` feature's
  `iceoryx2` dependency, with no passwordless sudo available to install it.
  The crate's own unit tests (`--features backtest --lib`) were run instead
  (22 passed, 0 failed) and are the ones this cross-check's conclusions
  depend on; the `live` feature itself is irrelevant to backtesting.
- `osv-scanner` CLI scan (binary absent on this host; `pip-audit` substituted
  and recorded as such, not silently swapped in).
- The actual numeric cross-check against sim-capacity's output (that run does
  not exist yet in this worktree).
- Whether `PartialFillExchange` diverges from `NoPartialFillExchange` on a
  fixture where order size exceeds the touch's quoted size (not constructed
  here -- this fixture's orders never exceeded the touch's quoted quantity,
  so the two exchange models could not diverge on it).
- Real-world accuracy of the Lee-Ready aggressor-side inference on actual
  Alpaca SIP data (only shown to work on this hand-constructed fixture, where
  every trade prints exactly at the bid).
