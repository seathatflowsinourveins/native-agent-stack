#!/usr/bin/env python3
"""L1 (top-of-book) feasibility check for hftbacktest 2.4.4.

This is OUR synthetic integration check, not an upstream test. It answers a
narrow, concrete question: can hftbacktest's exchange-simulation logic (order
acceptance, marketable-IOC fill, and non-marketable expiry) be driven
correctly from single-level ("L1") top-of-book quotes -- i.e. data shaped
like Alpaca's consolidated SIP best-bid/best-ask feed, which carries no
depth beyond the touch and no trade aggressor side -- and, separately, where
that data is NOT sufficient (queue-position depletion from trade prints).

Data representation used here (documented, not just asserted):
  * Each L1 quote update (`best_bid` or `best_ask` changing) is represented
    as a pair of `DEPTH_EVENT` events: one that zeroes the quantity at the
    OLD best price on that side (removing the level) and one that sets the
    quantity at the NEW best price on that side. hftbacktest's own data
    format (docs/data.rst in the pinned source, py-v2.4.4) documents
    `qty == 0` at a price as "remove this price level" for `DEPTH_EVENT`,
    which is exactly single-level replacement when only one level per side
    is ever present.
  * Each trade print is represented as a bare `TRADE_EVENT` with NEITHER
    `BUY_EVENT` nor `SELL_EVENT` set, because Alpaca's consolidated SIP tape
    does not carry an aggressor/taker side. hftbacktest's exchange models
    (`hftbacktest/src/backtest/proc/nopartialfillexchange.rs`,
    `partialfillexchange.rs`) only act on trades when the event matches
    `EXCH_BUY_TRADE_EVENT` or `EXCH_SELL_TRADE_EVENT` (TRADE_EVENT + a side
    bit). A side-less TRADE_EVENT matches neither arm, so it is silently
    ignored by both exchange models -- confirmed empirically in Scenario C
    below.

Scenarios:
  A. Marketable IOC buy limit crosses the touch (collar = ask + $0.01) and
     is filled at the prevailing best ask, purely from L1 depth. This is the
     `ack_new` "price_tick >= best_ask_tick" branch in nopartialfillexchange.rs
     -- decided entirely from best-ask depth, no trade data needed.
  B. Same order type, but the ask has already moved away (jumped from $10.02
     to $10.06) before the order's entry latency elapses, so it arrives
     non-marketable and IOC forces immediate expiry ("ack_new" else-branch,
     IOC/FOK -> Status.Expired). Again decided purely from L1 depth.
  C. A resting (GTC) buy order sits at the best bid. Trade prints occur at
     that exact price. With side-tagged trades, `queue_model.trade()` is
     invoked and the probabilistic queue model can register the order as
     filled from consumed queue volume. With side-less trades (our L1
     reality), `queue_model.trade()` is never called -- the branch requires
     `EXCH_BUY_TRADE_EVENT`/`EXCH_SELL_TRADE_EVENT` -- so the identical
     resting order does NOT get a trade-driven fill; it can only still be
     filled if the *quoted depth* at that price is driven to zero (a
     `on_bid_qty_chg` depth event), which is a materially different (and in
     practice slower/less realistic) fill signal than trade-driven queue
     consumption. This is the concrete "breaks / is meaningless" case for
     L1-only data: probabilistic and L3 queue models that key off trade
     prints cannot be driven correctly without an aggressor side.

Latency: constant_order_latency(70ms, 70ms), matching the 69.2ms flip
recorded in blueprints/us-equities/sim-paper-compare/receipts/20260923g-main-passed.json.
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

TICK = 0.01
LOT = 1.0
NS = 1_000_000_000
MS = 1_000_000
ENTRY_LATENCY = 70 * MS
RESP_LATENCY = 70 * MS


def build_scenario_a():
    """Static book (bid 10.00 / ask 10.02) for 10s. Order submitted mid-way
    should fill against the resting ask via a marketable IOC crossing."""
    import hftbacktest as h

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


def run_ioc_scenario(data_builder, submit_at_ns, collar=0.01, order_qty=10.0):
    import hftbacktest as h
    from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
    from numba import njit

    data = data_builder()

    asset = (
        BacktestAsset()
        .add_data(data)
        .linear_asset(1.0)
        .constant_order_latency(ENTRY_LATENCY, RESP_LATENCY)
        .power_prob_queue_model(2.0)
        .no_partial_fill_exchange()
        .trading_value_fee_model(0.0, 0.0)
        .tick_size(TICK)
        .lot_size(LOT)
    )
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
                hbt.submit_buy_order(asset_no, order_id, price, order_qty, 3, 0, False)
                submitted = True
                # 1 == reached end of data before a response arrived; 0 covers
                # both "response received" and "timeout", disambiguated below
                # by inspecting the order's final status.
                if hbt.wait_order_response(asset_no, order_id, 2_000_000_000) == 1:
                    return -1
        return 0

    rc = _run(hbt, submit_at_ns, collar, order_qty)
    order = hbt.orders(0).get(1)
    result = {
        "run_rc": int(rc),
        "order_status": int(order.status) if order is not None else None,
        "exec_price": float(order.exec_price_tick * TICK) if order is not None else None,
        "exec_qty": float(order.exec_qty) if order is not None else None,
        "leaves_qty": float(order.leaves_qty) if order is not None else None,
    }
    hbt.close()
    return result


def run_scenario_c():
    """Resting GTC buy at the touch; compare trade-driven queue depletion
    with vs without an aggressor side on otherwise-identical trade prints."""
    import hftbacktest as h
    from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
    from numba import njit

    def build(with_side: bool):
        exch_local = h.EXCH_EVENT | h.LOCAL_EVENT
        # A trade that hits the resting BID is a SELL-side aggressor print
        # (EXCH_SELL_TRADE_EVENT consumes resting Side::Buy orders in
        # nopartialfillexchange.rs). Our L1/SIP data has no aggressor side,
        # so `without_side` uses a bare TRADE_EVENT (side_bit=0).
        side_bit = h.SELL_EVENT if with_side else 0
        rows = [
            (h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 0, 0, 10.00, 20.0, 0, 0, 0.0),
            (h.DEPTH_EVENT | h.SELL_EVENT | exch_local, 0, 0, 10.02, 100.0, 0, 0, 0.0),
        ]
        # 5 trade prints of qty 10 at the bid touch (10.00), well after order
        # is resting (order submitted at 100ms). With side, these should be
        # visible to queue_model.trade(); without side, they are dropped by
        # the exchange model's TRADE_EVENT branch entirely.
        t = 500 * MS
        for _ in range(5):
            rows.append((h.TRADE_EVENT | side_bit | exch_local, t, t, 10.00, 10.0, 0, 0, 0.0))
            t += 50 * MS
        rows.append((h.DEPTH_EVENT | h.BUY_EVENT | exch_local, 5 * NS, 5 * NS, 10.00, 20.0, 0, 0, 0.0))
        return np.array(rows, dtype=h.event_dtype)

    def run(with_side: bool):
        asset = (
            BacktestAsset()
            .add_data(build(with_side))
            .linear_asset(1.0)
            .constant_order_latency(ENTRY_LATENCY, RESP_LATENCY)
            .power_prob_queue_model(2.0)
            .no_partial_fill_exchange()
            .trading_value_fee_model(0.0, 0.0)
            .tick_size(TICK)
            .lot_size(LOT)
        )
        hbt = HashMapMarketDepthBacktest([asset])

        @njit
        def _run(hbt):
            asset_no = 0
            order_id = 1
            submitted = False
            while hbt.elapse(10_000_000) == 0:
                if not submitted and hbt.current_timestamp >= 100 * 1_000_000:
                    hbt.submit_buy_order(asset_no, order_id, 10.00, 5.0, 0, 0, False)
                    submitted = True
                    if hbt.wait_order_response(asset_no, order_id, 2_000_000_000) == 1:
                        return -1
            return 0

        rc = _run(hbt)
        order = hbt.orders(0).get(1)
        result = {
            "run_rc": int(rc),
            "order_status": int(order.status) if order is not None else None,
            "exec_qty": float(order.exec_qty) if order is not None else None,
        }
        hbt.close()
        return result

    return {"with_side": run(True), "without_side": run(False)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="write JSON result to this path")
    args = parser.parse_args()

    result_a = run_ioc_scenario(build_scenario_a, submit_at_ns=1 * NS)
    result_b = run_ioc_scenario(build_scenario_b, submit_at_ns=50 * MS)
    result_c = run_scenario_c()

    # order.status constants (hftbacktest.order): NEW=0? check via import
    import hftbacktest as h
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
        r = dict(r)
        r["order_status_name"] = status_names.get(r["order_status"], "UNKNOWN")
        return r

    out = {
        "scenario_a_marketable_ioc_fill_from_l1_depth": label(result_a),
        "scenario_b_ioc_expiry_from_l1_depth": label(result_b),
        "scenario_c_queue_trade_depletion_needs_side": {
            "with_side": label(result_c["with_side"]),
            "without_side": label(result_c["without_side"]),
        },
        "expectations": {
            "scenario_a": "FILLED at ask=10.02 (marketable IOC crosses touch; decided purely from L1 best-ask depth)",
            "scenario_b": "EXPIRED (ask moved to 10.06 before order arrival; IOC does not rest)",
            "scenario_c": "with_side: order should reflect queue-model trade-driven state differently than "
                          "without_side, because hftbacktest's EXCH_BUY_TRADE_EVENT/EXCH_SELL_TRADE_EVENT "
                          "branches require a side bit; a bare TRADE_EVENT (our L1/SIP reality) is dropped "
                          "by nopartialfillexchange.rs entirely and never reaches queue_model.trade().",
        },
    }

    text = json.dumps(out, indent=2, sort_keys=True)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
