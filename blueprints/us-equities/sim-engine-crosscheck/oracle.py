"""Independent, engine-free ground-truth oracle for the engine-vs-engine
cross-check (added in the 2026-09-25 repair round, per an independent
adversarial review).

Given ONLY the retained quotes -- no engine, no simulation, no dependency on
either `run_nautilus.py` or `run_hftbacktest.py` -- decides per order
whether it should be immediately fillable at `submit_ts + latency`: the
last NBBO at or before that instant, the order's limit price crossing it,
and the touch's own displayed size being at least the order's quantity.
This mirrors the same "quote in force at a given instant" lookup
`metrics.py`'s `touch_share`/`better_than_touch_violations` and
sim-capacity's own `runner.check_no_fill_beats_nbbo_touch` already use, but
is deliberately its own, independent implementation here: it exists
specifically to catch a case where BOTH engine drivers agree with each
other while both being wrong (e.g. both reading corrupted memory, as the
first attempt's hftbacktest driver did) -- something comparing the two
engines only to each other could never detect.

This is a simplification, not a full execution simulator: it ignores queue
position, latency-in-transit price movement between the order's own
generation-time touch and the arrival instant's touch (the order's limit
price is fixed at generation time; only the ARRIVAL touch used for the
crossing/size check moves), and any consumption of displayed size by
earlier orders. It is a sanity oracle, not a third engine.
"""
from __future__ import annotations

import bisect
from decimal import Decimal

from order_stream import OrderIntent


def predict(quotes_by_symbol: dict, intent: OrderIntent, latency_ms: int) -> dict:
    """Ground-truth prediction for one order. `fillable` is True iff the
    last quote at or before `submit_ts + latency_ms` shows the order's limit
    price crossing the relevant touch AND that touch's displayed size is at
    least the order's quantity."""
    arrival_ts_ns = intent.ts_ns + int(latency_ms * 1_000_000)
    rows = quotes_by_symbol.get(intent.symbol) or []
    if not rows:
        return {"order_id": intent.order_id, "fillable": False, "reason": "no_quotes_for_symbol",
                "arrival_ts_ns": arrival_ts_ns, "touch": None, "top_size": None, "quote_ts_ns": None}
    ts_list = [r["ts_ns"] for r in rows]
    i = bisect.bisect_right(ts_list, arrival_ts_ns) - 1
    if i < 0:
        return {"order_id": intent.order_id, "fillable": False, "reason": "no_quote_at_or_before_arrival",
                "arrival_ts_ns": arrival_ts_ns, "touch": None, "top_size": None, "quote_ts_ns": None}
    quote = rows[i]
    bid, ask = Decimal(quote["bid"]), Decimal(quote["ask"])
    limit = Decimal(intent.limit_price)
    if intent.side == "BUY":
        crosses, top_size, touch = limit >= ask, quote["ask_size"], ask
    else:
        crosses, top_size, touch = limit <= bid, quote["bid_size"], bid
    size_ok = top_size >= intent.qty
    fillable = crosses and size_ok
    reason = None if fillable else ("not_crossing" if not crosses else "insufficient_top_size")
    return {"order_id": intent.order_id, "fillable": fillable, "reason": reason, "arrival_ts_ns": arrival_ts_ns,
            "touch": str(touch), "top_size": top_size, "quote_ts_ns": quote["ts_ns"]}


def predict_stream(quotes_by_symbol: dict, stream: list[OrderIntent], latency_ms: int) -> list[dict]:
    """Predictions in the same order as `stream`, one per intent."""
    return [predict(quotes_by_symbol, intent, latency_ms) for intent in stream]


def confusion(predictions: list[dict], outcomes: list[dict]) -> dict:
    """Confusion counts between the oracle's `fillable` prediction and each
    outcome's actual `exec_qty > 0`, aligned by list position (both lists
    must already be in the same order)."""
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must be the same length and order")
    tp = fp = fn = tn = 0
    for p, o in zip(predictions, outcomes):
        predicted, actual = p["fillable"], o["exec_qty"] > 0
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fn += 1
        elif not predicted and actual:
            fp += 1
        else:
            tn += 1
    n = len(predictions)
    agreement = (tp + tn) / n if n else 0.0
    return {"n": n, "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
            "agreement": agreement}


def confusion_by_symbol(predictions: list[dict], outcomes: list[dict]) -> dict:
    """Same as `confusion`, split by each outcome's own `symbol` field."""
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must be the same length and order")
    by_symbol: dict[str, list] = {}
    for p, o in zip(predictions, outcomes):
        by_symbol.setdefault(o["symbol"], []).append((p, o))
    return {sym: confusion([p for p, _ in pairs], [o for _, o in pairs]) for sym, pairs in by_symbol.items()}
