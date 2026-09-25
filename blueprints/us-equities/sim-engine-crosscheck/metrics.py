"""Pure, engine-agnostic metric computations for the engine-vs-engine
cross-check (Phase C).

Every function here consumes a list of per-order OUTCOME dicts in one common
schema (see README.md's "Outcome schema"), so the exact same code applies to
NautilusTrader-derived and hftbacktest-derived results -- no engine import,
no network, no filesystem access beyond the retained quote sample already in
memory. Hermetic and unit-testable on system Python.

Outcome schema (one dict per submitted order):
  order_id: int
  symbol: str
  side: "BUY" | "SELL"
  submit_ts_ns: int
  submit_qty: int
  limit_price: str (decimal)
  touch_price_at_submit: str (decimal) -- ask (BUY) or bid (SELL) when the order was generated
  mid_price_at_submit: str (decimal)
  status: "FILLED" | "PARTIAL" | "NO_FILL" | "REJECTED" | "DENIED" | "UNRESOLVED"
  exec_qty: int (0 if nothing executed)
  avg_exec_price: str (decimal) or None
  resolved_ts_ns: int or None -- time of the terminal event (fill/expiry/reject)

Fee cost reuses sim-capacity's own `fee_model.commission_usd` directly
(imported, not reimplemented), applied identically to both engines' outcomes
post-hoc -- neither engine's own native fee/commission model is used here
(NautilusTrader's `fee_model=None`; hftbacktest's `trading_value_fee_model`
left at (0.0, 0.0)), so "total simulated cost" means the same thing for both.
"""
from __future__ import annotations

import bisect
import sys
from decimal import Decimal
from pathlib import Path

_SIM_CAPACITY = Path(__file__).resolve().parents[1] / "sim-capacity"
if str(_SIM_CAPACITY) not in sys.path:
    sys.path.insert(0, str(_SIM_CAPACITY))

import fee_model as _fee_model  # noqa: E402

FILLED_STATUSES = ("FILLED", "PARTIAL")


def fill_rate(outcomes: list[dict]) -> float:
    """Any nonzero execution (full or partial) / submitted -- matches
    sim-capacity's own notion that a partial-then-canceled IOC still counts
    as a fill event (exerciser.py's on_order_filled fires on every partial
    execution, separately from ioc_partial_then_canceled bookkeeping)."""
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o["exec_qty"] > 0) / len(outcomes)


def full_fill_share(outcomes: list[dict]) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o["exec_qty"] == o["submit_qty"]) / len(outcomes)


def partial_fill_share(outcomes: list[dict]) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if 0 < o["exec_qty"] < o["submit_qty"]) / len(outcomes)


def _percentile(sorted_values: list[float], q: float) -> float:
    """Same nearest-rank method as sim-capacity's runner.submit_to_fill_latency_ms."""
    n = len(sorted_values)
    return sorted_values[min(n - 1, int(q * (n - 1)))]


def time_to_fill_ms_stats(outcomes: list[dict]) -> dict:
    deltas = sorted((o["resolved_ts_ns"] - o["submit_ts_ns"]) / 1e6
                     for o in outcomes if o["exec_qty"] > 0 and o.get("resolved_ts_ns") is not None)
    if not deltas:
        return {"n": 0, "median_ms": None, "p90_ms": None, "min_ms": None, "max_ms": None}
    return {"n": len(deltas), "median_ms": _percentile(deltas, 0.5), "p90_ms": _percentile(deltas, 0.9),
            "min_ms": deltas[0], "max_ms": deltas[-1]}


def _touch_at(quotes_by_symbol: dict, symbol: str, ts_ns: int, side: str) -> str | None:
    rows = quotes_by_symbol.get(symbol) or []
    if not rows:
        return None
    ts_list = [r["ts_ns"] for r in rows]
    i = bisect.bisect_right(ts_list, ts_ns) - 1
    if i < 0:
        return None
    row = rows[i]
    return row["ask"] if side == "BUY" else row["bid"]


def touch_share(outcomes: list[dict], quotes_by_symbol: dict) -> dict:
    """Share of executed orders whose average execution price equals the
    NBBO touch in force AT THE RESOLUTION TIME (fill/expiry instant) -- the
    same "touch in force at fill time, not submit time" convention as
    sim-capacity's runner.check_no_fill_beats_nbbo_touch, reused here for a
    consistent, engine-agnostic definition."""
    filled = [o for o in outcomes if o["exec_qty"] > 0 and o.get("avg_exec_price") is not None]
    if not filled:
        return {"n": 0, "at_touch": 0, "share": 0.0}
    at_touch = 0
    for o in filled:
        ts = o.get("resolved_ts_ns") if o.get("resolved_ts_ns") is not None else o["submit_ts_ns"]
        touch = _touch_at(quotes_by_symbol, o["symbol"], ts, o["side"])
        if touch is not None and Decimal(o["avg_exec_price"]) == Decimal(touch):
            at_touch += 1
    return {"n": len(filled), "at_touch": at_touch, "share": at_touch / len(filled)}


def better_than_touch_violations(outcomes: list[dict], quotes_by_symbol: dict) -> list[dict]:
    """Hard integrity check, added in the 2026-09-25 repair round: fills
    STRICTLY better than the NBBO touch in force at resolution time, for
    EITHER engine -- the same guard as sim-capacity's own
    `runner.check_no_fill_beats_nbbo_touch` (a BUY fill must never be
    strictly better than the ask in force; a SELL fill must never be
    strictly better than the bid in force), applied here identically to
    both NautilusTrader's and hftbacktest's outcomes. The first cross-check
    attempt never ran this check against hftbacktest's own output at all;
    it would have caught the use-after-free directly (354 of 384 NVDA fills
    in that broken run were better than any displayed quote, by up to 87
    cents -- see receipts/20260925-crosscheck.json's
    `superseded_first_attempt` block). Returns the list of violations
    (empty means the check passes); callers should treat any non-empty
    result as a hard failure, not a metric to merely report."""
    violations = []
    for o in outcomes:
        if o["exec_qty"] <= 0 or o.get("avg_exec_price") is None:
            continue
        ts = o.get("resolved_ts_ns") if o.get("resolved_ts_ns") is not None else o["submit_ts_ns"]
        touch = _touch_at(quotes_by_symbol, o["symbol"], ts, o["side"])
        if touch is None:
            continue
        px, touch_d = Decimal(o["avg_exec_price"]), Decimal(touch)
        beats = (px < touch_d) if o["side"] == "BUY" else (px > touch_d)
        if beats:
            violations.append({"order_id": o["order_id"], "symbol": o["symbol"], "side": o["side"],
                                "avg_exec_price": o["avg_exec_price"], "touch": touch, "resolved_ts_ns": ts})
    return violations


def cost_vs_mid_bps(outcomes: list[dict]) -> dict:
    """Signed execution cost vs. the mid price at submit time (same sign
    convention as sim-capacity's runner.summarize_run:
    (px - mid) * qty for a BUY, (mid - px) * qty for a SELL -- positive means
    worse than mid), reported both as a notional-weighted aggregate in bps
    and as a simple per-order average in bps."""
    filled = [o for o in outcomes if o["exec_qty"] > 0 and o.get("avg_exec_price") is not None]
    if not filled:
        return {"n": 0, "total_cost_usd": "0", "total_mid_notional_usd": "0", "bps": None, "avg_per_order_bps": None}
    total_cost = Decimal("0")
    total_notional = Decimal("0")
    per_order_bps = []
    for o in filled:
        px = Decimal(o["avg_exec_price"])
        mid = Decimal(o["mid_price_at_submit"])
        qty = Decimal(o["exec_qty"])
        signed = (px - mid) * qty if o["side"] == "BUY" else (mid - px) * qty
        total_cost += signed
        total_notional += mid * qty
        if mid > 0:
            per_order_bps.append(float(signed / (mid * qty) * 10000))
    bps = float(total_cost / total_notional * 10000) if total_notional > 0 else None
    avg_bps = sum(per_order_bps) / len(per_order_bps) if per_order_bps else None
    return {"n": len(filled), "total_cost_usd": str(total_cost), "total_mid_notional_usd": str(total_notional),
            "bps": bps, "avg_per_order_bps": avg_bps}


def total_fees_usd(outcomes: list[dict], commission_plan: str = "none") -> str:
    total = Decimal("0")
    for o in outcomes:
        if o["exec_qty"] <= 0 or o.get("avg_exec_price") is None:
            continue
        total += _fee_model.commission_usd(side=o["side"], quantity=o["exec_qty"], price=o["avg_exec_price"],
                                            commission_plan=commission_plan)
    return str(total)


def status_counts(outcomes: list[dict]) -> dict:
    out: dict[str, int] = {}
    for o in outcomes:
        out[o["status"]] = out.get(o["status"], 0) + 1
    return out


def summarize(outcomes: list[dict], quotes_by_symbol: dict, *, commission_plan: str = "none") -> dict:
    fees = total_fees_usd(outcomes, commission_plan=commission_plan)
    cost = cost_vs_mid_bps(outcomes)
    total_simulated_cost_usd = str(Decimal(fees) + Decimal(cost["total_cost_usd"]))
    return {
        "n_orders": len(outcomes),
        "status_counts": status_counts(outcomes),
        "fill_rate": fill_rate(outcomes),
        "full_fill_share": full_fill_share(outcomes),
        "partial_fill_share": partial_fill_share(outcomes),
        "time_to_fill_ms": time_to_fill_ms_stats(outcomes),
        "touch_share": touch_share(outcomes, quotes_by_symbol),
        "cost_vs_mid": cost,
        "fees_usd": fees,
        "total_simulated_cost_usd": total_simulated_cost_usd,
        "commission_plan": commission_plan,
    }


def summarize_by_symbol(outcomes: list[dict], quotes_by_symbol: dict, *, commission_plan: str = "none") -> dict:
    symbols = sorted({o["symbol"] for o in outcomes})
    return {s: summarize([o for o in outcomes if o["symbol"] == s], quotes_by_symbol, commission_plan=commission_plan)
            for s in symbols}
