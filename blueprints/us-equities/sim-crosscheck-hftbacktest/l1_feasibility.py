#!/usr/bin/env python3
"""L1 (top-of-book) feasibility check for hftbacktest 2.4.4.

This is OUR synthetic integration check, not an upstream test. It answers a
narrow, concrete question: can hftbacktest's exchange-simulation logic (order
acceptance, marketable-IOC/FOK/GTX handling, and passive-order fills) be
driven correctly from single-level ("L1") top-of-book quotes -- i.e. data
shaped like Alpaca's consolidated SIP best-bid/best-ask feed, which carries
no depth beyond the touch and no trade aggressor side -- and, separately,
where that data is NOT sufficient?

Data representation used here (documented, not just asserted):
  * Each L1 quote update (`best_bid` or `best_ask` changing) is represented
    as a pair of `DEPTH_EVENT` events: one that zeroes the quantity at the
    OLD best price on that side (removing the level) and one that sets the
    quantity at the NEW best price on that side. hftbacktest's own data
    format (docs/data.rst in the pinned source, py-v2.4.4) documents
    `qty == 0` at a price as "remove this price level" for `DEPTH_EVENT`.
    This is exact single-level replacement for the best bid/offer PRICE and
    SIZE -- it is NOT exact for queue POSITION: a resting order accepted at a
    price hftbacktest has never quoted starts with queue_model.new_order()
    initializing its "quantity ahead" from the CURRENT quoted size at that
    price tick (ProbQueueModel: queue.rs new_order(), lines ~165-173;
    RiskAdverseQueueModel: lines ~67-74), which on an L1 feed is whatever
    happens to be quoted there *now*, not the order's true historical FIFO
    position. See Scenario E below for a concrete, measured demonstration of
    the resulting optimistic bias.
  * Each trade print is represented as a bare `TRADE_EVENT` with NEITHER
    `BUY_EVENT` nor `SELL_EVENT` set, because Alpaca's consolidated SIP tape
    does not carry an aggressor/taker side.

What a side-less TRADE_EVENT actually loses (verified by reading
hftbacktest/src/backtest/proc/{nopartialfillexchange,partialfillexchange}.rs,
not just Scenario C's queue-depletion case): the exchange models only reach
`check_if_buy_filled`/`check_if_sell_filled` -- which cover BOTH (a) an
unconditional "trade-through" fill when the trade price crossed clean through
a resting order's price, AND (b) trade-driven queue-position depletion via
`queue_model.trade()`/`is_filled()` when the trade printed exactly at the
order's price -- from the `EXCH_BUY_TRADE_EVENT`/`EXCH_SELL_TRADE_EVENT`
dispatch arms, which require a side bit. A bare `TRADE_EVENT` matches
neither arm and is dropped before either path is reached. Depth-quantity
events (`on_bid_qty_chg`/`on_ask_qty_chg`) still update the queue model's
internal position estimate via `queue_model.depth()`, but that function only
adjusts book-keeping state; nothing in that call path invokes `is_filled()`
or otherwise changes `order.status`. So on raw L1 data, a passive (resting)
order can be filled ONLY by the opposite quote REACHING OR crossing its
price (`on_best_bid_update`/`on_best_ask_update` fire on `order.price_tick
>= new_best_tick` for a resting buy -- equality, a quote landing exactly on
the order's price, is enough; it does not need to cross past it. Scenario
D3) -- never by trade
prints or by its own side's depth going to zero (Scenario D1/D2 show the
side-bearing and side-less contrast directly; the withdrawn-liquidity-with-
no-trade case in D2 confirms depth alone never fills anything by itself).

Scenarios:
  A. Marketable IOC buy limit crosses the touch (collar = ask + $0.01) and
     is filled at the prevailing best ask, purely from L1 depth.
  B. Same order type, but the ask has already moved away (jumped from $10.02
     to $10.06) before the order's entry latency elapses, so it arrives
     non-marketable and IOC forces immediate expiry.
  C. A resting (GTC) buy order sits at the best bid. Trade prints occur at
     that exact price (queue-position depletion case, `Ordering::Equal` arm).
     With side-tagged trades, filled; with side-less trades (our L1 reality),
     stays NEW for the whole run.
  D. Three probes isolating exactly which fill paths raw L1 data supports:
     D1 trade-through (a trade printing BELOW a resting buy's price, the
        `Ordering::Greater` arm -- unconditional fill, still side-gated);
     D2 the order's own quoted depth driven to zero with NO trade at all
        (must NOT fill -- `on_bid_qty_chg` never checks `is_filled`);
     D3 the opposite quote (best ask) reaching or crossing down through the
        resting buy's price (`on_best_ask_update` -- fills with no trade
        data at all; the ask does not need to cross past the order's price,
        landing exactly on it is enough, since the condition is `>=`).
  E. Optimistic new-order queue-position bias: a buy resting away from the
     touch (at a price L1 has never quoted) starts with zero quantity ahead
     of it; once the market quotes that price, even a tiny trade can fill it
     immediately. HAND-VERIFIED (see run_scenario_e_optimistic_queue_bias's
     docstring for the full trace): ProbQueueModel.depth() has an early-
     return path for a quantity increase that never touches its probability
     formula at all, so this fixture's outcome is exactly hand-computable,
     not merely observed.
  F. NoPartialFillExchange vs PartialFillExchange genuinely diverge once
     order size exceeds the touch's quoted size (not true for Scenarios
     A-D, whose orders were always <= the touch's quoted size). For IOC,
     the PartialFillExchange side executes what it can (exec_qty > 0) and
     THEN sets status=Expired for the unfilled remainder -- reading
     `order.status` alone understates what happened; for FOK (Scenario G2)
     PartialFillExchange is genuinely all-or-none and expires with exec_qty
     exactly 0, so that "status understates" caveat does NOT apply to FOK.
  G. Time-in-force coverage beyond IOC/GTC: FOK (all-or-none; expires with
     ZERO execution under PartialFillExchange when depth is insufficient,
     unlike IOC's partial-then-expire) and GTX (Expired -- never a distinct
     "Rejected" status -- when it would cross; New/accepted like GTC
     otherwise). G2 (oversized FOK) is the one Scenario-G case that diverges
     between exchange models; G1/G3/G4 coincide, same as A-D.
  H. Nonzero fee accounting: `trading_value_fee_model` with a nonzero taker
     fee, confirming `state_values(...).fee` reflects the traded value, not
     merely that a zero-fee call didn't error.
  I. PartialFillExchange's own no-depletion bias: three back-to-back
     100-share IOCs against a touch that always shows exactly 100 shares
     (never re-quoted) all FILL IN FULL under PartialFillExchange, for a
     cumulative position of 300 -- because executing against `self.depth`
     does not mutate `self.depth` itself (only an explicit DEPTH_EVENT
     does; upstream's own doc comment on PartialFillExchange says this
     explicitly: fills happen "even though the best price and quantity do
     not change due to your execution"). This is a DIFFERENT bias from
     Scenario E's (which is about queue POSITION on a fresh price); this one
     is about the exchange model never depleting quoted SIZE across orders
     at all, at any price.

Latency: constant_order_latency(70ms, 70ms) is a SENSITIVITY point carried
over from blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json,
which itself labels its 69.2ms flip "Sensitivity check, not a calibration".
It is used here only to give the fixture a concrete, non-zero latency; a
cross-check against real sim-capacity output should sweep latency, not seed
a single assumed value from a different experiment's sensitivity point.

Scenarios A/B/C/D/F/G are run under BOTH exchange models hftbacktest exposes
(`no_partial_fill_exchange` and `partial_fill_exchange`); Scenario F is
specifically designed to show they do NOT always agree (they coincide on
A/B/C/D only because those fixtures keep order size <= touch size).
"""
from __future__ import annotations

import argparse
import json

# numpy is imported lazily, inside each function that builds an event array
# (alongside `import hftbacktest as h`), not at module import time: this
# module's pure-Python aggressor-side-inference functions (infer_side_emo,
# infer_side_lee_ready, classify_trade_tape, run_tick_test_coverage_demo) and
# the tests that exercise them must import and run cleanly even on an
# interpreter that has neither hftbacktest nor numpy installed.

TICK = 0.01
LOT = 1.0
NS = 1_000_000_000
MS = 1_000_000
ENTRY_LATENCY = 70 * MS
RESP_LATENCY = 70 * MS

try:
    # hftbacktest.order DOES export GTC/GTX/FOK/IOC as named constants (an
    # earlier version of this file said FOK/IOC "are not exported as names"
    # -- that was wrong; use the real module's values when it is installed).
    from hftbacktest.order import FOK, GTC, GTX, IOC
except ImportError:
    # hftbacktest is not installed on this interpreter (e.g. the system
    # Python running only the pure-Python EMO/Lee-Ready classification
    # tests, which need neither hftbacktest nor numpy). These are
    # hftbacktest::types::TimeInForce's stable integer values
    # (hftbacktest/src/types.rs) used only as a fallback when the package
    # itself is entirely absent.
    GTC, GTX, FOK, IOC = 0, 1, 2, 3
LIMIT = 0


def _base_asset(data, exchange="no_partial_fill", maker_fee=0.0, taker_fee=0.0):
    from hftbacktest import BacktestAsset

    asset = (
        BacktestAsset()
        .add_data(data)
        .linear_asset(1.0)
        .constant_order_latency(ENTRY_LATENCY, RESP_LATENCY)
        .power_prob_queue_model(2.0)
        .trading_value_fee_model(maker_fee, taker_fee)
        .tick_size(TICK)
        .lot_size(LOT)
    )
    return _apply_exchange_model(asset, exchange)


def _apply_exchange_model(asset, exchange: str):
    if exchange == "no_partial_fill":
        return asset.no_partial_fill_exchange()
    if exchange == "partial_fill":
        return asset.partial_fill_exchange()
    raise ValueError(exchange)


def _order_result(order):
    if order is None:
        return {"order_status": None, "exec_price": None, "exec_qty": None, "leaves_qty": None}
    return {
        "order_status": int(order.status),
        "exec_price": float(order.exec_price_tick * TICK),
        "exec_qty": float(order.exec_qty),
        "leaves_qty": float(order.leaves_qty),
    }


def build_scenario_a():
    """Static book (bid 10.00 / ask 10.02) for 10s. Order submitted mid-way
    should fill against the resting ask via a marketable IOC crossing."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        # side-less trade print (SIP has no aggressor side) -- documentation only
        (h.TRADE_EVENT | exch_local, 0, 0, 10.01, 5.0, 0, 0, 0.0),
        # keep the feed alive to 10s so hbt.elapse() has data to run through
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 10 * NS, 10 * NS, 10.00, 100.0, 0, 0, 0.0),
    ]
    return np.array(rows, dtype=h.event_dtype)


def build_scenario_b():
    """Book starts bid 10.00 / ask 10.02. The order is submitted at 50ms
    (pricing off the then-current ask of 10.02 -> limit 10.03), but the ask
    re-quotes away to 10.06 at 100ms -- before the order's 70ms entry
    latency lands it at the exchange at 120ms -- so the marketable-at-
    submission-time IOC finds no cross on arrival and must expire."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        # ask re-quotes away: remove old level, add new level
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 100 * MS, 100 * MS, 10.02, 0.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 100 * MS, 100 * MS, 10.06, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 10 * NS, 10 * NS, 10.00, 100.0, 0, 0, 0.0),
    ]
    return np.array(rows, dtype=h.event_dtype)


def run_ioc_scenario(data_builder, submit_at_ns, collar=0.01, order_qty=10.0, exchange="no_partial_fill"):
    from hftbacktest import HashMapMarketDepthBacktest
    from numba import njit

    data = data_builder()
    asset = _base_asset(data, exchange=exchange)
    hbt = HashMapMarketDepthBacktest([asset])

    @njit
    def _run(hbt, submit_at_ns, collar, order_qty):
        asset_no = 0
        order_id = 1
        submitted = False
        while hbt.elapse(10_000_000) == 0:
            if not submitted and hbt.current_timestamp >= submit_at_ns:
                depth = hbt.depth(asset_no)
                price = depth.best_ask + collar
                hbt.submit_buy_order(asset_no, order_id, price, order_qty, IOC, LIMIT, False)
                submitted = True
                # 1 == reached end of data before a response arrived; 0 covers
                # both "response received" and "timeout", disambiguated below
                # by inspecting the order's final status.
                if hbt.wait_order_response(asset_no, order_id, 2_000_000_000) == 1:
                    return -1
        return 0

    rc = _run(hbt, submit_at_ns, collar, order_qty)
    result = {"run_rc": int(rc), **_order_result(hbt.orders(0).get(1))}
    hbt.close()
    return result


def build_scenario_c_data(with_side: bool):
    """Resting GTC buy at the touch; five trade prints of qty 10 at the bid.

    with_side=True: trades carry an explicit SELL_EVENT aggressor bit (a
      sell-side print hitting the bid), which is what hftbacktest's own
      exchange models require to reach queue depletion at all.
    with_side=False: bare TRADE_EVENT, no side bit (our raw L1/SIP reality).
    """
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    side_bit = h.SELL_EVENT if with_side else 0
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 20.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
    ]
    t = 500 * MS
    for _ in range(5):
        rows.append((h.TRADE_EVENT | side_bit | exch_local, t, t, 10.00, 10.0, 0, 0, 0.0))
        t += 50 * MS
    rows.append((h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 5 * NS, 5 * NS, 10.00, 20.0, 0, 0, 0.0))
    return np.array(rows, dtype=h.event_dtype)


def _run_resting_buy(data, price, qty, exchange="no_partial_fill", tif=GTC, submit_at_ns=100 * MS,
                      maker_fee=0.0, taker_fee=0.0):
    from hftbacktest import HashMapMarketDepthBacktest
    from numba import njit

    asset = _base_asset(data, exchange=exchange, maker_fee=maker_fee, taker_fee=taker_fee)
    hbt = HashMapMarketDepthBacktest([asset])

    @njit
    def _run(hbt):
        asset_no = 0
        order_id = 1
        submitted = False
        while hbt.elapse(10_000_000) == 0:
            if not submitted and hbt.current_timestamp >= submit_at_ns:
                hbt.submit_buy_order(asset_no, order_id, price, qty, tif, LIMIT, False)
                submitted = True
                if hbt.wait_order_response(asset_no, order_id, 2_000_000_000) == 1:
                    return -1
        return 0

    rc = _run(hbt)
    order = hbt.orders(0).get(1)
    fee = float(hbt.state_values(0).fee)
    result = {"run_rc": int(rc), "fee": fee, **_order_result(order)}
    hbt.close()
    return result


def run_scenario_c(exchange="no_partial_fill"):
    """Compare trade-driven queue depletion with vs without an aggressor
    side on an otherwise-identical resting order and trade stream."""
    return {
        "with_side": _run_resting_buy(build_scenario_c_data(with_side=True), 10.00, 5.0, exchange=exchange),
        "without_side": _run_resting_buy(build_scenario_c_data(with_side=False), 10.00, 5.0, exchange=exchange),
    }


def build_scenario_d1_data(with_side: bool):
    """Resting buy at 10.00 (book stays bid=10.00/ask=10.02 throughout); a
    single trade prints BELOW the resting order's own price (9.99), i.e. a
    sell-aggressor sweep through the level -- the `Ordering::Greater` arm in
    check_if_buy_filled, an UNCONDITIONAL fill (no queue math at all), but
    still only reachable via the side-tagged EXCH_SELL_TRADE_EVENT."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    side_bit = h.SELL_EVENT if with_side else 0
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 20.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        (h.TRADE_EVENT | side_bit | exch_local, 500 * MS, 500 * MS, 9.99, 3.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 5 * NS, 5 * NS, 10.00, 20.0, 0, 0, 0.0),
    ]
    return np.array(rows, dtype=h.event_dtype)


def build_scenario_d2_data():
    """Resting buy at 10.00; the bid level at 10.00 is driven to qty=0 with
    NO trade print at all. Must NOT fill: on_bid_qty_chg only calls
    queue_model.depth(), which never invokes is_filled()."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 20.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 500 * MS, 500 * MS, 10.00, 0.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 5 * NS, 5 * NS, 10.00, 0.0, 0, 0, 0.0),
    ]
    return np.array(rows, dtype=h.event_dtype)


def build_scenario_d3_data():
    """Resting buy at 10.00 (accepted while ask=10.02, non-crossing); the ask
    later re-quotes DOWN to 9.99 (< order price), crossing through it via
    on_best_ask_update -- filled from depth alone, no trade needed."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 20.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 500 * MS, 500 * MS, 10.02, 0.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 500 * MS, 500 * MS, 9.99, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 5 * NS, 5 * NS, 10.00, 20.0, 0, 0, 0.0),
    ]
    return np.array(rows, dtype=h.event_dtype)


def run_scenario_d_passive_fill_paths(exchange="no_partial_fill"):
    return {
        "d1_trade_through_with_side": _run_resting_buy(build_scenario_d1_data(True), 10.00, 5.0, exchange=exchange),
        "d1_trade_through_without_side": _run_resting_buy(build_scenario_d1_data(False), 10.00, 5.0, exchange=exchange),
        "d2_depth_zeroed_no_trade": _run_resting_buy(build_scenario_d2_data(), 10.00, 5.0, exchange=exchange),
        "d3_ask_crosses_down": _run_resting_buy(build_scenario_d3_data(), 10.00, 5.0, exchange=exchange),
    }


def build_scenario_d1_emo_data():
    """Same book and trade-through price as build_scenario_d1_data, but the
    side bit is not hard-coded: an unambiguous seed trade at the ask (400ms,
    classified 'buy' directly by EMO's exact-quote rule) is added before the
    9.99 trade-through print (500ms), so the tick test has a genuine prior
    price to compare against. Without a seed, the 9.99 print would be the
    FIRST trade in the tape and EMO's tick-test fallback would return
    undetermined (no history) -- run_scenario_d1_with_inferred_side()
    reports whichever of these two outcomes this tape actually produces,
    rather than assuming inference "just works"."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    bid, ask = 10.00, 10.02
    tick_state = {}
    prices = [ask, 9.99]  # seed at the ask (unambiguous 'buy'), then the test print
    sides = [infer_side_emo(px, bid, ask, tick_state) for px in prices]
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, bid, 20.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, ask, 100.0, 0, 0, 0.0),
    ]
    for t_ms, px, side in zip((400, 500), prices, sides):
        bit = h.SELL_EVENT if side == "sell" else (h.BUY_EVENT if side == "buy" else 0)
        rows.append((h.TRADE_EVENT | bit | exch_local, t_ms * MS, t_ms * MS, px, 3.0, 0, 0, 0.0))
    rows.append((h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 5 * NS, 5 * NS, bid, 20.0, 0, 0, 0.0))
    return np.array(rows, dtype=h.event_dtype), sides


def run_scenario_d1_with_inferred_side(exchange="no_partial_fill"):
    """Actually runs EMO inference on the D1 trade-through tape (an earlier
    version of this fixture's receipt claimed inference "restores trade-
    through fills in this fixture" without ever running this -- that claim
    is now either substantiated or corrected by this function's actual
    output, not assumed)."""
    data, inferred_sides = build_scenario_d1_emo_data()
    result = _run_resting_buy(data, 10.00, 5.0, exchange=exchange)
    result["inferred_sides"] = inferred_sides
    return result


def build_scenario_e_data():
    """Book quotes only bid=10.00/ask=10.02 (never 9.99) until 500ms, when the
    bid re-quotes to 9.99 showing size 50; a single 5-share sell-aggressor
    print then hits it. The resting buy at 9.99 was accepted while nothing
    was quoted there (front_q_qty initialized to 0 -- queue.rs new_order()),
    so this measures whether hftbacktest's L1-fed queue estimate lets a tiny
    print fill an order "queued" behind a much larger (50-share) display."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 500 * MS, 500 * MS, 10.00, 0.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 500 * MS, 500 * MS, 9.99, 50.0, 0, 0, 0.0),
        (h.TRADE_EVENT | h.SELL_EVENT | exch_local, 600 * MS, 600 * MS, 9.99, 5.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 5 * NS, 5 * NS, 9.99, 50.0, 0, 0, 0.0),
    ]
    return np.array(rows, dtype=h.event_dtype)


def run_scenario_e_optimistic_queue_bias(exchange="no_partial_fill"):
    """HAND-VERIFIED (corrected from an earlier version of this function,
    which called this "measured, not hand-derived" -- that undersold it).
    ProbQueueModel.depth() (queue.rs) has an early-return path for a quantity
    INCREASE (`chg = prev_qty - new_qty`; `if chg < 0.0 { front_q_qty =
    front_q_qty.min(new_qty); return; }`) that never touches the probability
    formula at all. Tracing this fixture by hand:
      1. new_order() at acceptance: front_q_qty = bid_qty_at_tick(9.99) = 0
         (nothing was ever quoted at 9.99 yet).
      2. The bid re-quotes to 9.99/50: on_bid_qty_chg -> depth(prev_qty=0,
         new_qty=50) -> chg = 0-50 = -50 < 0 -> early return with
         front_q_qty = min(0, 50) = 0. Still 0, exactly.
      3. The 5-share sell-aggressor print at 9.99: trade() ->
         front_q_qty -= 5 = -5; is_filled() -> exec =
         round(-(-5)/1.0) = 5 > 0 -> returns 5.0 shares filled.
      4. NoPartialFillExchange/PartialFillExchange's fill() then executes the
         order's full remaining leaves_qty (5.0) at the order's own price
         (9.99), maker=True.
    This traces to FILLED, exec_qty=5.0, exec_price=9.99 -- exactly the
    observed result below, with no probabilistic/random step ever actually
    invoked (the `prob()` formula is only reached when chg >= 0, i.e. when
    displayed quantity DECREASES, not when it appears fresh)."""
    return _run_resting_buy(build_scenario_e_data(), 9.99, 5.0, exchange=exchange, submit_at_ns=50 * MS)


def build_scenario_f_data():
    """Static book, ask quoting only 100 shares at 10.02."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 10 * NS, 10 * NS, 10.00, 100.0, 0, 0, 0.0),
    ]
    return np.array(rows, dtype=h.event_dtype)


def run_scenario_f_exchange_model_divergence():
    """An IOC buy for 150 shares against a touch quoting only 100. This is
    the case Scenarios A-C never exercised (their orders were always <= the
    touch's quoted size), so it is the one that actually demonstrates
    NoPartialFillExchange and PartialFillExchange are NOT equivalent:
    NoPartialFillExchange::ack_new (lines ~330-341) fills the FULL requested
    quantity unconditionally on any cross, ignoring quoted size.
    PartialFillExchange::ack_new (IOC arm, ~437-452) walks quoted depth tick
    by tick and can only execute what is actually quoted, expiring the
    remainder -- and its own IOC arm sets order.status = Expired even when a
    partial fill already executed and updated state (exec_qty/leaves_qty
    reflect the partial fill; the terminal `status` field alone does not)."""
    order_qty = 150.0
    result = {}
    for exchange in ("no_partial_fill", "partial_fill"):
        result[exchange] = run_ioc_scenario(
            build_scenario_f_data, submit_at_ns=1 * NS, order_qty=order_qty, exchange=exchange
        )
    return result


def build_scenario_i_data():
    """Static book, bid=10.00/100, ask=10.02/100, NEVER re-quoted for the
    whole 10s run -- deliberately: PartialFillExchange's own execution
    against `self.depth` does not mutate the depth structure itself (only an
    explicit DEPTH_EVENT does), so the touch keeps reporting 100 shares
    available no matter how many prior orders already executed against it."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 10 * NS, 10 * NS, 10.00, 100.0, 0, 0, 0.0),
    ]
    return np.array(rows, dtype=h.event_dtype)


def run_scenario_i_no_depletion_bias(exchange="partial_fill"):
    """Reproduces the reviewer's probe: three back-to-back 100-share IOC
    buys against a touch that always shows exactly 100 shares. Upstream's
    own doc comment on PartialFillExchange says exactly this: 'Liquidity-
    taking orders will be executed based on the quantity of the order book,
    EVEN THOUGH THE BEST PRICE AND QUANTITY DO NOT CHANGE DUE TO YOUR
    EXECUTION. Be aware that this may cause unrealistic fill simulations if
    you attempt to execute a large quantity' (partialfillexchange.rs
    ~lines 66-69). PartialFillExchange caps EACH order at the touch's
    displayed size, but never actually depletes that displayed size for the
    NEXT order -- so at a high enough submission rate it over-fills exactly
    like NoPartialFillExchange does for a single oversized order (Scenario
    F), just spread across multiple orders instead of one."""
    from hftbacktest import HashMapMarketDepthBacktest
    from numba import njit

    data = build_scenario_i_data()
    asset = _base_asset(data, exchange=exchange)
    hbt = HashMapMarketDepthBacktest([asset])

    @njit
    def _run(hbt):
        asset_no = 0
        submit_times = (1_000_000_000, 2_000_000_000, 3_000_000_000)
        submitted = (False, False, False)
        idx = 0
        while hbt.elapse(10_000_000) == 0:
            if idx < 3 and hbt.current_timestamp >= submit_times[idx]:
                order_id = idx + 1
                depth = hbt.depth(asset_no)
                hbt.submit_buy_order(asset_no, order_id, depth.best_ask + 0.01, 100.0, IOC, LIMIT, False)
                if hbt.wait_order_response(asset_no, order_id, 2_000_000_000) == 1:
                    return -1
                idx += 1
        return 0

    rc = _run(hbt)
    orders = [_order_result(hbt.orders(0).get(i)) for i in (1, 2, 3)]
    position = float(hbt.state_values(0).position)
    hbt.close()
    return {"run_rc": int(rc), "orders": orders, "final_position": position}


def build_scenario_g_data():
    return build_scenario_f_data()  # same static book, reused for TIF probes


def run_scenario_g_time_in_force():
    """FOK and GTX coverage, run (not just claimed) under both exchange
    models. Touch quotes 100 shares at 10.02 (see build_scenario_g_data)."""
    out = {}
    for exchange in ("no_partial_fill", "partial_fill"):
        from hftbacktest import HashMapMarketDepthBacktest
        from numba import njit

        def submit_and_read(order_qty, tif, price=None):
            data = build_scenario_g_data()
            asset = _base_asset(data, exchange=exchange)
            hbt = HashMapMarketDepthBacktest([asset])

            @njit
            def _run(hbt, order_qty, tif, price):
                asset_no = 0
                order_id = 1
                submitted = False
                while hbt.elapse(10_000_000) == 0:
                    if not submitted and hbt.current_timestamp >= 1 * NS:
                        depth = hbt.depth(asset_no)
                        px = price if price > 0 else depth.best_ask + 0.01
                        hbt.submit_buy_order(asset_no, order_id, px, order_qty, tif, LIMIT, False)
                        submitted = True
                        if hbt.wait_order_response(asset_no, order_id, 2_000_000_000) == 1:
                            return -1
                return 0

            rc = _run(hbt, order_qty, tif, price if price is not None else -1.0)
            result = {"run_rc": int(rc), **_order_result(hbt.orders(0).get(1))}
            hbt.close()
            return result

        out[exchange] = {
            "g1_fok_sufficient_depth": submit_and_read(10.0, FOK),
            "g2_fok_insufficient_depth": submit_and_read(150.0, FOK),
            "g3_gtx_crossing": submit_and_read(10.0, GTX),
            "g4_gtx_resting": submit_and_read(1.0, GTX, price=10.00),
        }
    return out


def run_scenario_h_fee_accounting(exchange="no_partial_fill", taker_fee=0.001):
    """Nonzero taker fee on a marketable IOC fill; confirms
    state_values(...).fee reflects traded value (price * qty * taker_fee),
    not merely that a zero-fee call didn't error."""
    from hftbacktest import HashMapMarketDepthBacktest
    from numba import njit

    data = build_scenario_a()
    asset = _base_asset(data, exchange=exchange, maker_fee=0.0, taker_fee=taker_fee)
    hbt = HashMapMarketDepthBacktest([asset])

    @njit
    def _run(hbt):
        asset_no = 0
        order_id = 1
        submitted = False
        while hbt.elapse(10_000_000) == 0:
            if not submitted and hbt.current_timestamp >= 1 * NS:
                depth = hbt.depth(asset_no)
                hbt.submit_buy_order(asset_no, order_id, depth.best_ask + 0.01, 10.0, IOC, LIMIT, False)
                submitted = True
                if hbt.wait_order_response(asset_no, order_id, 2_000_000_000) == 1:
                    return -1
        return 0

    rc = _run(hbt)
    order = hbt.orders(0).get(1)
    fee = float(hbt.state_values(0).fee)
    expected_fee = float(order.exec_price_tick * TICK * order.exec_qty * taker_fee) if order else None
    result = {"run_rc": int(rc), "fee": fee, "expected_fee": expected_fee, **_order_result(order)}
    hbt.close()
    return result


# --- Aggressor-side inference: proposed DATA-PREPARATION steps, NOT hftbacktest features ---

def _tick_test(trade_px, tick_state):
    """Classic tick test, comparing to the last DIFFERING trade price. A
    'zero tick' (price unchanged from the immediately preceding trade) reuses
    the last known direction instead of returning undetermined -- this is
    the fix: the naive version that only compares to the immediately
    preceding trade would otherwise lose its classification on a run of flat
    prints. Mutates tick_state (keys 'last_price', 'last_direction') and
    must be called exactly once per trade, in trade-time order, regardless
    of whether the caller's own rule ends up using the result (an at-the-
    quote trade still needs to update history for the NEXT ambiguous trade
    to fall back on)."""
    prev_price = tick_state.get("last_price")
    direction = tick_state.get("last_direction")
    if prev_price is not None:
        if trade_px > prev_price:
            direction = "buy"
        elif trade_px < prev_price:
            direction = "sell"
        # else: zero tick -- `direction` already holds the last known value (possibly still None)
    tick_state["last_price"] = trade_px
    tick_state["last_direction"] = direction
    return direction


def infer_side_emo(trade_px, bid, ask, tick_state):
    """The Ellis-Michaely-O'Hara (EMO) "at-quote" rule (Ellis, Michaely &
    O'Hara, 2000, Journal of Financial and Quantitative Analysis, "The
    Accuracy of Trade Classification Rules: Evidence from Nasdaq"): a trade
    priced EXACTLY at the ask is a buy; EXACTLY at the bid is a sell;
    everything else -- including a print strictly inside the spread AND a
    print outside the quotes entirely (above the ask or below the bid, which
    can happen with stale/late quotes or off-exchange prints) -- falls back
    to the tick test. An earlier version of this function used `>=`/`<=`
    (at-or-through the quote), which is wrong: EMO's own at-quote condition
    is equality, not a threshold; a print beyond the quote is exactly the
    kind of ambiguous case the tick-test fallback exists for.

    EMO, Lee-Ready and the plain tick test are all applied (to classify
    short-sale trades specifically, not as a general method survey) in
    Asquith, Oman & Safaya, 2008, NBER Working Paper No. 14158, "Short Sales
    and Trade Classification Algorithms" -- an earlier version of this
    docstring cited this paper as "Diether, Lee & Werner" and described it as
    a literature review; both were wrong (verified against the paper's own
    NBER page metadata: authors Paul Asquith, Rebecca Oman, Christopher
    Safaya; it is a study of trade-classification accuracy specifically for
    short sales).

    NOTE: this is NOT the Lee-Ready (1991) rule below, which compares to the
    bid-ask MIDPOINT rather than the raw quotes -- an earlier version of this
    fixture mislabeled this exact at-quote rule as "Lee-Ready"; that was
    wrong and is corrected here by naming (and separately implementing) both.
    """
    tick_direction = _tick_test(trade_px, tick_state)
    if trade_px == ask:
        return "buy"
    if trade_px == bid:
        return "sell"
    return tick_direction


def infer_side_lee_ready(trade_px, bid, ask, tick_state):
    """Lee & Ready, 1991, Journal of Finance, "Inferring Trade Direction from
    Intraday Data": a trade above the bid-ask MIDPOINT is a buy; below the
    midpoint is a sell; AT the midpoint falls back to the tick test."""
    tick_direction = _tick_test(trade_px, tick_state)
    mid = (bid + ask) / 2.0
    if trade_px > mid:
        return "buy"
    if trade_px < mid:
        return "sell"
    return tick_direction


def classify_trade_tape(prices, bid, ask, rule):
    """Pure-Python classification demo, no hftbacktest engine involved --
    used to prove the tick-test fallback branch actually executes, and that
    a flat tick reuses the prior direction, for BOTH rules independently."""
    state = {}
    return [rule(px, bid, ask, state) for px in prices]


def build_scenario_c_emo_data():
    """Same resting-order setup as Scenario C, but the trade prints are
    priced EXACTLY at the bid (10.00) with bid=10.00/ask=10.02, so the EMO
    at-quote rule's direct `trade_px == bid` condition unambiguously
    classifies every one as a sell aggressor -- exactly the SELL_EVENT bit
    Scenario C's with_side=True applies directly. Demonstrates the inference
    step explicitly instead of hard-coding the side, then applies the
    inferred bit."""
    import hftbacktest as h
    import numpy as np

    exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
    bid, ask = 10.00, 10.02
    rows = [
        (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, bid, 20.0, 0, 0, 0.0),
        (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, ask, 100.0, 0, 0, 0.0),
    ]
    t = 500 * MS
    tick_state = {}
    inferred_sides = []
    for _ in range(5):
        trade_px = 10.00  # prints at the bid -- SIP gives us this price, nothing else
        side = infer_side_emo(trade_px, bid, ask, tick_state)
        inferred_sides.append(side)
        bit = h.SELL_EVENT if side == "sell" else (h.BUY_EVENT if side == "buy" else 0)
        rows.append((h.TRADE_EVENT | bit | exch_local, t, t, trade_px, 10.0, 0, 0, 0.0))
        t += 50 * MS
    rows.append((h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 5 * NS, 5 * NS, bid, 20.0, 0, 0, 0.0))
    return np.array(rows, dtype=h.event_dtype), inferred_sides


def run_scenario_c_emo():
    """Proposed data-prep step: infer the aggressor side with the EMO
    at-quote rule and show it restores trade-driven queue depletion,
    matching Scenario C's with_side result."""
    data, inferred_sides = build_scenario_c_emo_data()
    result = _run_resting_buy(data, 10.00, 5.0)
    result["inferred_sides"] = inferred_sides
    return result


TICK_TEST_TRIGGER_PRICES = [10.02, 10.015, 10.01, 10.01, 10.005, 10.00]
"""A mid-spread price tape (bid=10.00/ask=10.02, midpoint=10.01) built so that:
  index 0 (10.02, at the ask): both rules agree directly ('buy'), seeding history.
  index 1 (10.015): strictly inside the spread (not at either quote) AND above
    the midpoint. EMO falls back to the tick test (10.015 is a downtick from
    10.02 -> 'sell'); Lee-Ready classifies it directly from the midpoint
    ('buy', since 10.015 > 10.01). The two rules DISAGREE here -- this is the
    concrete case showing EMO and Lee-Ready are not interchangeable, not
    merely different code paths to the same answer.
  index 2 (10.01): exactly the midpoint -- ambiguous for Lee-Ready (falls to
    the tick test) and strictly inside the spread for EMO (also tick test);
    both use the tick test here and agree ('sell', a downtick from 10.015).
  index 3 (10.01 again): a flat tick against index 2 -- both rules must reuse
    the prior direction ('sell') rather than losing their classification.
  index 4 (10.005): strictly inside the spread and below the midpoint -- EMO
    via tick test, Lee-Ready directly from the midpoint; both agree ('sell').
  index 5 (10.00, at the bid): both rules agree directly ('sell').

This tape's outcomes are UNCHANGED by the EMO exact-quote fix (`==` instead
of `>=`/`<=`): indices 0 and 5 are exactly at the ask/bid either way, and
indices 1-4 already relied on the tick test (they were always strictly
inside the spread, never beyond a quote). The exact-quote fix only changes
behavior for prints ABOVE the ask or BELOW the bid, exercised separately by
EMO_BOUNDARY_TEST_PRICES below.
"""


def run_tick_test_coverage_demo():
    bid, ask = 10.00, 10.02
    return {
        "prices": TICK_TEST_TRIGGER_PRICES,
        "emo": classify_trade_tape(TICK_TEST_TRIGGER_PRICES, bid, ask, infer_side_emo),
        "lee_ready": classify_trade_tape(TICK_TEST_TRIGGER_PRICES, bid, ask, infer_side_lee_ready),
    }


EMO_BOUNDARY_TEST_PRICES = [10.00, 10.02, 10.03, 9.98]
"""Exercises EMO's exact-quote boundary specifically (bid=10.00/ask=10.02):
  index 0 (10.00, exactly at the bid): direct 'sell', no tick test needed.
  index 1 (10.02, exactly at the ask): direct 'buy', no tick test needed;
    also seeds tick history at 10.02 for the next two prints.
  index 2 (10.03, ABOVE the ask -- not equal to it): under the corrected
    `==`-only rule this is NOT a direct 'buy' -- it falls to the tick test
    (an uptick from 10.02 -> 'buy' here, but via the fallback, not the
    at-quote condition; an earlier `>=`-based version would have classified
    this directly as 'buy' without ever exercising the fallback).
  index 3 (9.98, BELOW the bid -- not equal to it): likewise falls to the
    tick test (a downtick from 10.03 -> 'sell'), not a direct classification.
"""


def run_emo_boundary_demo():
    bid, ask = 10.00, 10.02
    return {"prices": EMO_BOUNDARY_TEST_PRICES, "emo": classify_trade_tape(EMO_BOUNDARY_TEST_PRICES, bid, ask, infer_side_emo)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="write JSON result to this path")
    args = parser.parse_args()

    from hftbacktest import order as order_mod

    status_names = {
        order_mod.NONE: "NONE",
        order_mod.NEW: "NEW",
        order_mod.EXPIRED: "EXPIRED",
        order_mod.FILLED: "FILLED",
        order_mod.CANCELED: "CANCELED",
        order_mod.PARTIALLY_FILLED: "PARTIALLY_FILLED",
        order_mod.REJECTED: "REJECTED",
    }

    def label(r):
        if not isinstance(r, dict):
            return r
        r = dict(r)
        if "order_status" in r:
            r["order_status_name"] = status_names.get(r["order_status"], "UNKNOWN")
        for k, v in list(r.items()):
            if isinstance(v, dict):
                r[k] = label(v)
        return r

    by_exchange = {}
    for exchange in ("no_partial_fill", "partial_fill"):
        by_exchange[exchange] = {
            "scenario_a_marketable_ioc_fill_from_l1_depth": label(
                run_ioc_scenario(build_scenario_a, submit_at_ns=1 * NS, exchange=exchange)
            ),
            "scenario_b_ioc_expiry_from_l1_depth": label(
                run_ioc_scenario(build_scenario_b, submit_at_ns=50 * MS, exchange=exchange)
            ),
            "scenario_c_queue_trade_depletion_needs_side": label(run_scenario_c(exchange=exchange)),
            "scenario_d_passive_fill_paths": label(run_scenario_d_passive_fill_paths(exchange=exchange)),
            "scenario_g_time_in_force": label(run_scenario_g_time_in_force()[exchange]),
        }

    scenario_e = label(run_scenario_e_optimistic_queue_bias())
    scenario_f = label(run_scenario_f_exchange_model_divergence())
    scenario_h = label(run_scenario_h_fee_accounting())
    scenario_i = label(run_scenario_i_no_depletion_bias())
    emo_result = label(run_scenario_c_emo())
    d1_emo_result = label(run_scenario_d1_with_inferred_side())
    tick_test_demo = run_tick_test_coverage_demo()
    emo_boundary_demo = run_emo_boundary_demo()

    # A-D and G1/G3/G4 coincide between the two exchange models on THIS
    # fixture's order sizes; G2 (oversized FOK) is the scenario in this group
    # that actually diverges (see scenario_g2_diverges below) -- an earlier
    # version of this script's single combined flag, and the surrounding
    # prose, wrongly implied ALL of Scenario G coincided.
    def _without_g2(block):
        block = dict(block)
        g = dict(block["scenario_g_time_in_force"])
        g.pop("g2_fok_insufficient_depth", None)
        block["scenario_g_time_in_force"] = g
        return block

    identical_a_to_d_and_g1_g3_g4 = (
        _without_g2(by_exchange["no_partial_fill"]) == _without_g2(by_exchange["partial_fill"])
    )
    scenario_g2_diverges = (
        by_exchange["no_partial_fill"]["scenario_g_time_in_force"]["g2_fok_insufficient_depth"]
        != by_exchange["partial_fill"]["scenario_g_time_in_force"]["g2_fok_insufficient_depth"]
    )
    scenario_f_diverges = scenario_f["no_partial_fill"] != scenario_f["partial_fill"]

    out = {
        "by_exchange_model": by_exchange,
        "identical_under_both_exchange_models_for_scenarios_a_to_d_and_g1_g3_g4": identical_a_to_d_and_g1_g3_g4,
        "scenario_g2_fok_insufficient_diverges_between_exchange_models": scenario_g2_diverges,
        "scenario_e_optimistic_queue_bias_HAND_VERIFIED": scenario_e,
        "scenario_f_exchange_models_diverge_on_oversized_order": scenario_f,
        "scenario_f_models_actually_diverge": scenario_f_diverges,
        "scenario_h_fee_accounting": scenario_h,
        "scenario_i_partial_fill_no_depletion_bias": scenario_i,
        "emo_aggressor_side_inference": {
            "result": emo_result,
            "note": "Proposed DATA-PREPARATION step (not an hftbacktest feature): infer each trade's "
                    "aggressor side with the EMO at-quote rule (==ask -> buy, ==bid -> sell, else tick "
                    "test -- including prints strictly above the ask or below the bid) before emitting "
                    "TRADE_EVENT, then apply that side as a BUY_EVENT/SELL_EVENT bit. This rule is NOT "
                    "Lee-Ready (see infer_side_lee_ready, and tick_test_coverage_demo for a case where "
                    "the two rules disagree on a strictly-inside-the-spread print). All 5 trades in "
                    "this fixture print exactly at the bid (10.00 == bid 10.00), so both rules classify "
                    "every one as a sell aggressor here -- restoring trade-driven queue depletion "
                    "(FILLED) versus the side-less case (stays NEW).",
        },
        "d1_trade_through_with_inferred_side": {
            "result": d1_emo_result,
            "note": "Runs EMO inference on the D1 trade-through tape (an earlier version of this "
                    "fixture's receipt claimed inference restores trade-through fills here WITHOUT "
                    "ever running it -- this is that actual run). The 9.99 print is OUTSIDE the "
                    "quotes (below the bid, not at it), so EMO needs the tick test; a seed trade at "
                    "the ask is added first so the tick test has a genuine prior price, and "
                    "inferred_sides in the result shows what each of the two trades was classified as.",
        },
        "tick_test_coverage_demo": tick_test_demo,
        "emo_boundary_demo": emo_boundary_demo,
        "expectations": {
            "scenario_a": "FILLED at ask=10.02 (marketable IOC crosses touch; decided purely from L1 best-ask depth)",
            "scenario_b": "EXPIRED (ask moved to 10.06 before order arrival; IOC does not rest)",
            "scenario_c": "with_side FILLED, without_side stays NEW -- queue-trade depletion needs a side bit",
            "scenario_d1_trade_through": "with_side FILLED (unconditional trade-through fill), without_side stays NEW (event dropped before reaching the trade-through arm at all)",
            "scenario_d2_depth_zeroed_no_trade": "NEW (depth-only changes never invoke is_filled)",
            "scenario_d3_ask_crosses_down": "FILLED (opposite-quote crossing fills with no trade data at all)",
            "scenario_f": "no_partial_fill fills the full 150 regardless of the 100-share touch; partial_fill executes only 100 and marks the remainder Expired (with exec_qty=100 already applied to state) -- these should NOT be equal",
            "scenario_g1_fok_sufficient": "FILLED under both exchange models",
            "scenario_g2_fok_insufficient": "no_partial_fill: FILLED IN FULL regardless of quoted size (FOK is bundled with GTC/IOC in that model's single unconditional-fill arm); partial_fill: EXPIRED with ZERO exec_qty (all-or-none, unlike IOC's partial-then-expire in scenario F) -- G2 is the one Scenario-G case that diverges between exchange models",
            "scenario_g3_gtx_crossing": "EXPIRED under both exchange models (never a distinct Rejected status)",
            "scenario_g4_gtx_resting": "NEW/accepted under both exchange models, like GTC",
            "scenario_h": "fee should equal exec_price * exec_qty * taker_fee, not zero",
            "scenario_i": "all three 100-share IOCs FILLED in full under partial_fill_exchange, final_position=300.0, despite the touch never showing more than 100 shares at any point -- PartialFillExchange caps a single order's fill at the displayed size but never depletes that display for the next order",
        },
    }

    text = json.dumps(out, indent=2, sort_keys=True)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
