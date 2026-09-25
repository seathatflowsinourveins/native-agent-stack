"""hftbacktest 2.4.4 side of the engine-vs-engine cross-check.

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
from schedule import tick_interval_ns  # noqa: E402

TICK_SIZE = Decimal("0.01")
LOT_SIZE = 1.0
# Keep-alive pad past the sample's last quote so hftbacktest's `elapse()` has
# data to advance through until every order submitted near the window's tail
# has had time to resolve -- comfortably above the largest configured latency
# in this cross-check's sweep (250ms) round-tripped (entry + response) with
# margin, mirroring l1_feasibility.py build_scenario_a's own "keep the feed
# alive" trailing event.
PAD_NS = 3_000_000_000
POLL_STEP_NS = 10_000_000  # 10ms -- matches l1_feasibility.py's own elapse() step
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
    exec_qty = int(round(float(order.exec_qty)))
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
    avg_px = str(Decimal(int(order.exec_price_tick)) * TICK_SIZE) if exec_qty > 0 else None
    resolved_ts = int(order.exch_timestamp) if status != "UNRESOLVED" else None
    return {**base, "status": status, "exec_qty": exec_qty, "avg_exec_price": avg_px, "resolved_ts_ns": resolved_ts}


def run_stream(quotes_by_symbol: dict, stream: list[OrderIntent], *, latency_ms: int,
                exchange: str = "partial_fill") -> list[dict]:
    """Run one (stream, latency, exchange model) combination. Returns a list
    of outcome dicts (metrics.py's schema), one per intent in `stream`, in
    intent order."""
    if latency_ms <= 0:
        raise ValueError("latency_ms must be positive for this driver")
    import hftbacktest as h  # noqa: F401  (imported for its side effect of validating the venv is active)
    from hftbacktest import BacktestAsset, HashMapMarketDepthBacktest
    from hftbacktest.order import IOC

    LIMIT = 0
    latency_ns = int(latency_ms * 1_000_000)
    symbols = sorted(quotes_by_symbol)
    asset_no_by_symbol = {s: i for i, s in enumerate(symbols)}

    assets = []
    for s in symbols:
        data = build_depth_events(quotes_by_symbol[s])
        asset = (BacktestAsset().add_data(data).linear_asset(1.0)
                 .constant_order_latency(latency_ns, latency_ns).power_prob_queue_model(2.0)
                 .trading_value_fee_model(0.0, 0.0).tick_size(float(TICK_SIZE)).lot_size(LOT_SIZE))
        asset = asset.partial_fill_exchange() if exchange == "partial_fill" else asset.no_partial_fill_exchange()
        assets.append(asset)
    hbt = HashMapMarketDepthBacktest(assets)

    max_quote_ts = max(row["ts_ns"] for rows in quotes_by_symbol.values() for row in rows)
    drain_until = max_quote_ts + PAD_NS - POLL_STEP_NS
    idx, n = 0, len(stream)
    try:
        while True:
            rc = hbt.elapse(POLL_STEP_NS)
            if rc != 0:
                break
            now = hbt.current_timestamp
            while idx < n and stream[idx].ts_ns <= now:
                intent = stream[idx]
                asset_no = asset_no_by_symbol[intent.symbol]
                price, qty = float(intent.limit_price), float(intent.qty)
                if intent.side == "BUY":
                    submit_rc = hbt.submit_buy_order(asset_no, intent.order_id, price, qty, IOC, LIMIT, False)
                else:
                    submit_rc = hbt.submit_sell_order(asset_no, intent.order_id, price, qty, IOC, LIMIT, False)
                if submit_rc != 0:
                    raise RuntimeError(f"hftbacktest submit failed rc={submit_rc} for order_id={intent.order_id}")
                idx += 1
            if idx >= n and now >= drain_until:
                break
        outcomes = []
        for intent in stream:
            asset_no = asset_no_by_symbol[intent.symbol]
            order = hbt.orders(asset_no).get(intent.order_id)
            outcomes.append(_outcome_row(intent, order))
        return outcomes
    finally:
        hbt.close()


# Re-exported for callers that want the exact same tick cadence hftbacktest's
# submit loop polls against without importing schedule.py directly.
TICK_INTERVAL_NS = tick_interval_ns
