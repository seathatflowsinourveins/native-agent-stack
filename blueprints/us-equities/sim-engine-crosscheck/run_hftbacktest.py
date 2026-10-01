"""hftbacktest 2.4.4 side of the engine-vs-engine cross-check.

**Repair round (2026-09-25): fixes a use-after-free in the original
version.** `BacktestAsset.add_data(data)` does not take ownership of the
numpy array or increment its reference count -- it stores a raw pointer into
the array's buffer (`py-hftbacktest/hftbacktest/__init__.py:119-120` passes
the buffer address; `lib.rs:206-210` wraps it with `DataPtr::from_ptr`;
`backtest/data/mod.rs`'s own comment on that pointer type says it is "not
owned ... must remain valid"). The original `run_stream` reassigned a single
loop-local `data` variable on every iteration of the per-symbol asset-build
loop, so as soon as the second symbol's array was built, the FIRST symbol's
array's only Python reference was gone and CPython was free to reclaim that
memory -- while hftbacktest's Rust side kept reading through the
now-dangling pointer for the rest of the run. An independent adversarial
review reproduced this directly (72,134 of 74,835 NVDA (asset 0, built
first) event bytes differed in memory after a short elapse; 0 of the
later-built SPY (asset 1) array's bytes did; reruns on identical input gave
385/380/385 fills; one run hung; a synthetic two-symbol run segfaulted) and
traced the original cross-check's entire "F1"/"F2" narrative to this
corruption, not to any real hftbacktest or NautilusTrader behavior -- see
`receipts/20260925-crosscheck.json`'s `superseded_first_attempt` block and
README.md for the full account, kept on record rather than deleted.

**Fix**: every per-symbol event array is appended to `_data_arrays`, a list
held alive for the entire `run_stream` call (through `hbt.close()`), so no
array's Python reference count can reach zero while hftbacktest still holds
a raw pointer into it.

Also fixed this round: orders are submitted at their EXACT scheduled time
(the engine's clock is `elapse()`d directly to each order's own `ts_ns`,
computed as a delta from `hbt.current_timestamp`) instead of the original
10ms polling grid; and filled quantity is read as `qty - leaves_qty` (the
order's own before/after bookkeeping) rather than `exec_qty`, which upstream
only ever holds the LAST individual fill call's quantity/price, not a
running total across a multi-tick partial-fill walk (irrelevant for a
single-tick fill, which is the common case once displayed size comfortably
exceeds order size, but was masking the corruption's true footprint in the
original, broken run).

Converts the same bounded Alpaca SIP quote sample used on the NautilusTrader
side into hftbacktest's L1 `DEPTH_EVENT` representation -- a paired
zero-old-level / set-new-level event per side per quote tick, exactly the
convention `sim-crosscheck-hftbacktest/l1_feasibility.py`'s module docstring
and `build_scenario_b` establish and cite to hftbacktest's own `docs/data.rst`
(`qty == 0` at a price removes that level; HashMapMarketDepth is keyed by
price, so a new price does not implicitly retire the old one) -- then replays
the SAME precomputed `order_stream.OrderIntent` list the NautilusTrader side
replays, at the same scheduled times, with the given exchange model
(`partial_fill_exchange` -- the closest available to Nautilus's
`liquidity_consumption` semantics without being equivalent to it, see
README.md's difference table -- or `no_partial_fill_exchange` as a bracket)
and a constant order latency covering both entry and response, matching
`constant_order_latency(latency_ns, latency_ns)` as used throughout
`l1_feasibility.py`.

One known, documented limitation of the exposed Python API: `exec_price_tick`
reflects only the price of the LAST individual fill call applied to an
order, not a quantity-weighted average across every fill call. For a
single-tick fill (displayed size >= order size, the case for every order in
this cross-check's sample after the use-after-free fix -- see the "Locked
quotes" note below for the one exception) this is exact, since there is only
one fill call; it would understate a genuine multi-tick partial fill's
average price, which this dataset does not otherwise exercise.

**Locked quotes** (bid == ask): `HashMapMarketDepth::update_bid_depth` and
`update_ask_depth` each independently enforce `best_bid < best_ask`
(`hashmapmarketdepth.rs` ~177-182 for the bid side; the mirrored check on the
ask side): whichever side's DEPTH_EVENT is applied SECOND at a locked price
wins, and the other side's touch is evicted from the book (not merely
crossed) until the next event restores it. This sample has 314 locked NVDA
quote rows and 610 locked SPY rows; measured to affect exactly one order's
outcome across the whole configuration matrix (see the receipt's
`locked_quote_note`). This is real, disclosed upstream depth-model behavior
on a locked L1 book, not a bug in this driver, and is unrelated to the
use-after-free above.

Fee model is left at (0.0, 0.0): cost is computed post-hoc, uniformly for
both engines, by metrics.py using sim-capacity's own fee_model.commission_usd
-- see metrics.py's module docstring.

Requires the pinned isolated venv
(~/.local/share/native-agent-stack/hftbacktest-2.4.4); imports hftbacktest
lazily inside `run_stream` so this module stays importable (for
signature/shape inspection) without it.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from order_stream import OrderIntent

_SIM_CAPACITY = Path(__file__).resolve().parents[1] / "sim-capacity"
import sys  # noqa: E402

if str(_SIM_CAPACITY) not in sys.path:
    sys.path.insert(0, str(_SIM_CAPACITY))
from schedule import tick_interval_ns  # noqa: E402,F401  (re-exported below)

TICK_SIZE = Decimal("0.01")
LOT_SIZE = 1.0
# Keep-alive pad past the sample's last quote so hftbacktest's `elapse()` has
# data to advance through until every order submitted near the window's tail
# has had time to resolve -- comfortably above the largest configured latency
# in this cross-check's sweep (250ms) round-tripped (entry + response) with
# margin, mirroring l1_feasibility.py build_scenario_a's own "keep the feed
# alive" trailing event.
PAD_NS = 3_000_000_000
# `current_timestamp` starts at hftbacktest's own i64::MAX "uninitialized"
# sentinel before the first elapse() call; a minimal 1ns elapse initializes
# it to the fed data's own first event timestamp so subsequent calls can
# compute an exact delta to any target simulated time.
_PRIME_NS = 1
STATUS_NAMES = {0: "NONE", 1: "NEW", 2: "EXPIRED", 3: "FILLED", 4: "CANCELED", 5: "PARTIALLY_FILLED", 6: "REJECTED"}


def build_depth_events(rows: list[dict], pad_ns: int = PAD_NS):
    """One paired (zero-old, set-new) DEPTH_EVENT per side per quote tick
    whose price changed since the previous tick for that side; a plain
    set event (no zero) when only size changed at the same price; a final
    keep-alive event repeating the last known book, `pad_ns` past the last
    real quote."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    events = []
    last_bid_str = last_ask_str = None
    for row in rows:
        ts = row["ts_ns"]
        bid_str, ask_str = row["bid"], row["ask"]
        bid_size, ask_size = float(row["bid_size"]), float(row["ask_size"])
        if last_bid_str is not None and last_bid_str != bid_str:
            events.append((h.DEPTH_EVENT | h.BUY_EVENT | exch_local, ts, ts, float(last_bid_str), 0.0, 0, 0, 0.0))
        events.append((h.DEPTH_EVENT | h.BUY_EVENT | exch_local, ts, ts, float(bid_str), bid_size, 0, 0, 0.0))
        if last_ask_str is not None and last_ask_str != ask_str:
            events.append((h.DEPTH_EVENT | h.SELL_EVENT | exch_local, ts, ts, float(last_ask_str), 0.0, 0, 0, 0.0))
        events.append((h.DEPTH_EVENT | h.SELL_EVENT | exch_local, ts, ts, float(ask_str), ask_size, 0, 0, 0.0))
        last_bid_str, last_ask_str = bid_str, ask_str
    pad_ts = rows[-1]["ts_ns"] + pad_ns
    events.append((h.DEPTH_EVENT | h.BUY_EVENT | exch_local, pad_ts, pad_ts, float(last_bid_str),
                    float(rows[-1]["bid_size"]), 0, 0, 0.0))
    events.append((h.DEPTH_EVENT | h.SELL_EVENT | exch_local, pad_ts, pad_ts, float(last_ask_str),
                    float(rows[-1]["ask_size"]), 0, 0, 0.0))
    return np.array(events, dtype=h.event_dtype)


def _outcome_row(intent: OrderIntent, order) -> dict:
    base = {"order_id": intent.order_id, "symbol": intent.symbol, "side": intent.side,
            "submit_ts_ns": intent.ts_ns, "submit_qty": intent.qty, "limit_price": intent.limit_price,
            "touch_price_at_submit": intent.touch_price, "mid_price_at_submit": intent.mid_price}
    if order is None:
        return {**base, "status": "UNRESOLVED", "exec_qty": 0, "avg_exec_price": None, "resolved_ts_ns": None}
    # qty - leaves_qty, NOT exec_qty: exec_qty upstream holds only the LAST
    # fill call's own quantity, not a running total (see module docstring).
    exec_qty = int(round(float(order.qty) - float(order.leaves_qty)))
    status_int = int(order.status)
    if status_int == 3:  # FILLED
        status = "FILLED" if exec_qty >= intent.qty else "PARTIAL"
    elif status_int in (2, 4):  # EXPIRED / CANCELED (IOC's own terminal outcome when not fully filled)
        status = "PARTIAL" if exec_qty > 0 else "NO_FILL"
    elif status_int == 6:
        status = "REJECTED"
    elif status_int in (1, 5):  # NEW / PARTIALLY_FILLED still outstanding at end of run
        status = "UNRESOLVED"
    else:
        status = "OTHER"
    # exec_price_tick: the last fill call's price (see module docstring's
    # "known limitation" note) -- exact for the single-tick-fill case this
    # dataset exercises.
    avg_px = str(Decimal(int(order.exec_price_tick)) * TICK_SIZE) if exec_qty > 0 else None
    resolved_ts = int(order.exch_timestamp) if status != "UNRESOLVED" else None
    return {**base, "status": status, "exec_qty": exec_qty, "avg_exec_price": avg_px, "resolved_ts_ns": resolved_ts}


def run_stream(quotes_by_symbol: dict, stream: list[OrderIntent], *, latency_ms: int,
                exchange: str = "partial_fill") -> list[dict]:
    """Run one (stream, latency, exchange model) combination. Returns a list
    of outcome dicts (metrics.py's schema), one per intent in `stream`, in
    intent order.

    Every order is submitted at its own EXACT `ts_ns` (the engine's clock is
    `elapse()`d directly to that instant, not polled on a fixed grid), and
    every per-symbol feed array is kept referenced in `_data_arrays` for the
    whole call -- see module docstring's use-after-free fix."""
    if latency_ms <= 0:
        raise ValueError("latency_ms must be positive for this driver")
    import hftbacktest as h  # noqa: F401  (imported for its side effect of validating the venv is active)
    from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
    from hftbacktest.order import IOC

    LIMIT = 0
    latency_ns = int(latency_ms * 1_000_000)
    symbols = sorted(quotes_by_symbol)
    asset_no_by_symbol = {s: i for i, s in enumerate(symbols)}

    _data_arrays = []  # kept alive for the whole function -- see the use-after-free fix note above
    assets = []
    for s in symbols:
        data = build_depth_events(quotes_by_symbol[s])
        _data_arrays.append(data)
        asset = (BacktestAsset().add_data(data).linear_asset(1.0)
                 .constant_order_latency(latency_ns, latency_ns).power_prob_queue_model(2.0)
                 .trading_value_fee_model(0.0, 0.0).tick_size(float(TICK_SIZE)).lot_size(LOT_SIZE))
        asset = asset.partial_fill_exchange() if exchange == "partial_fill" else asset.no_partial_fill_exchange()
        assets.append(asset)
    hbt = HashMapMarketDepthBacktest(assets)

    max_quote_ts = max(row["ts_ns"] for rows in quotes_by_symbol.values() for row in rows)
    drain_until = max_quote_ts + PAD_NS - _PRIME_NS
    try:
        rc = hbt.elapse(_PRIME_NS)
        if rc != 0:
            raise RuntimeError(f"hftbacktest end-of-data during clock priming, rc={rc}")
        for intent in stream:
            delta = intent.ts_ns - hbt.current_timestamp
            if delta > 0:
                rc = hbt.elapse(delta)
                if rc != 0:
                    raise RuntimeError(f"hftbacktest end-of-data before order_id={intent.order_id}'s "
                                        f"submit time, rc={rc}")
            asset_no = asset_no_by_symbol[intent.symbol]
            price, qty = float(intent.limit_price), float(intent.qty)
            if intent.side == "BUY":
                submit_rc = hbt.submit_buy_order(asset_no, intent.order_id, price, qty, IOC, LIMIT, False)
            else:
                submit_rc = hbt.submit_sell_order(asset_no, intent.order_id, price, qty, IOC, LIMIT, False)
            if submit_rc != 0:
                raise RuntimeError(f"hftbacktest submit failed rc={submit_rc} for order_id={intent.order_id}")
        delta = drain_until - hbt.current_timestamp
        if delta > 0:
            rc = hbt.elapse(delta)
            if rc not in (0, 1):  # 1 (end of data) is fine here -- we only needed to reach the drain point
                raise RuntimeError(f"hftbacktest drain elapse failed rc={rc}")

        outcomes = []
        for intent in stream:
            asset_no = asset_no_by_symbol[intent.symbol]
            order = hbt.orders(asset_no).get(intent.order_id)
            outcomes.append(_outcome_row(intent, order))
        return outcomes
    finally:
        hbt.close()
        del _data_arrays  # explicit: the arrays must outlive hbt.close(), not be dropped before it


# Re-exported for callers that want the exact same tick cadence the order
# stream was generated at, without importing schedule.py directly.
TICK_INTERVAL_NS = tick_interval_ns
