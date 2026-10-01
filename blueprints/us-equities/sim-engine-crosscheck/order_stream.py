"""Deterministic, precomputed order stream for the engine-vs-engine
cross-check (Phase C).

Reuses sim-capacity's own `schedule.RoundRobin` / `clamp_sell_quantity` /
`tick_interval_ns` (blueprints/us-equities/sim-capacity/schedule.py) directly
-- imported, not reimplemented -- so this stream's inventory-aware side
alternation is bit-for-bit the same logic `CapacityExerciser` itself uses
(exerciser.py's module docstring: never propose a SELL from a flat or short
position; alternate BUY/SELL otherwise; force a SELL at the position cap).

Why precompute once instead of letting each engine decide sides live: the
real exerciser's side selection reads ITS OWN live position, itself a
function of realized fills -- and realized fills differ between
NautilusTrader and hftbacktest by construction (different liquidity-
consumption and queue-position semantics; see README.md's difference table).
Replaying two independently-fed-back streams would compare two different
order sequences, not the same orders under two engines. This module instead
walks the retained quotes ONCE, offline, with an ASSUMED-full-fill running
position per symbol used ONLY to pick sides/quantities deterministically --
not a claim that every order actually fills. A real engine's actual fills
can differ (an IOC can expire or partially fill); when that happens, a later
SELL sized against the assumed inventory can ask to sell more than a real
engine's own book of record actually holds at that moment. This is accepted,
not hidden: each engine handles it as a normal order outcome (a real
short-sale reject on Nautilus's CASH venue; a plain fill with no such
restriction on hftbacktest, which models no account-level short-sale rule at
all) and it is counted like any other outcome, not treated as fatal. See
README.md's "Order stream" section for the measured rate this occurs at on
the committed sample.

Cadence: 3 submits/sec, deliberately DIFFERENT from either real sim-capacity
profile's own attempted submit cadence (paper-parity attempts 5.0/sec, 300/min
against a 180/min budget, specifically so its limiter binds and denies;
elite-tier attempts ~16.67/sec against a 900/min budget) -- see
PAPER_PARITY_SUBMITS_PER_SEC below for why 3.0 is still the principled choice,
not an arbitrary third number.
"""
from __future__ import annotations

import bisect
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_SIM_CAPACITY = Path(__file__).resolve().parents[1] / "sim-capacity"
if str(_SIM_CAPACITY) not in sys.path:
    sys.path.insert(0, str(_SIM_CAPACITY))

from schedule import RoundRobin, clamp_sell_quantity, tick_interval_ns  # noqa: E402

# sim-capacity's paper-parity RiskEngineConfig budget is
# "180/00:01:00" (runner.PROFILES["paper-parity"]["max_order_submit_rate"]),
# i.e. 180/min = 3.0/sec exactly -- and 3.0 is independently also
# CapacityExerciserParams' own submits_per_sec dataclass default
# (exerciser.py). Submitting the deterministic stream AT this budget rate
# (not at paper-parity's own 5.0/sec attempted cadence, which is
# deliberately set ABOVE the budget to force rate-limit denials as that
# lane's own test target) keeps the stream inside the Nautilus risk
# engine's budget, so no order in this cross-check is expected to be denied
# for rate-limiting -- a Nautilus-only artifact with no counterpart at all on
# the hftbacktest side (hftbacktest has no per-account submit-rate limiter
# concept). A stream that deliberately exceeded a limiter would confound the
# fill-rate comparison with that artifact instead of measuring the two
# engines' execution/queue models, which is what this cross-check is for.
PAPER_PARITY_SUBMITS_PER_SEC = 3.0
COLLAR = Decimal("0.01")
QTY_MIN = 1
QTY_MAX = 5  # matches sim-capacity's runner.run_one CapacityExerciserParams(qty_max=5), not exerciser.py's own dataclass default of 3
POSITION_CAP = 300  # matches sim-capacity's runner.POSITION_CAP


@dataclass(frozen=True)
class OrderIntent:
    order_id: int
    ts_ns: int
    symbol: str
    side: str  # "BUY" or "SELL"
    qty: int
    limit_price: str  # decimal string, e.g. "123.45"
    touch_price: str  # ask (BUY) or bid (SELL) at generation time
    mid_price: str


def _quote_at_or_before(rows: list[dict], ts_list: list[int], ts_ns: int) -> dict | None:
    i = bisect.bisect_right(ts_list, ts_ns) - 1
    return rows[i] if i >= 0 else None


def generate_order_stream(quotes_by_symbol: dict[str, list[dict]], *, symbols: list[str] | None = None,
                           submits_per_sec: float = PAPER_PARITY_SUBMITS_PER_SEC, qty_min: int = QTY_MIN,
                           qty_max: int = QTY_MAX, position_cap: int = POSITION_CAP, collar: Decimal = COLLAR,
                           start_ns: int | None = None, end_ns: int | None = None) -> list[OrderIntent]:
    """Deterministic order stream: one entry per scheduled submit tick that
    has a quote and a positive clamped quantity, using ONLY the retained
    quote rows (see module docstring for why this is precomputed once, with
    no engine feedback). Mirrors `exerciser.CapacityExerciser._on_tick`'s
    per-tick logic exactly: round-robin symbol (`RoundRobin.next_symbol`,
    always advanced), inventory-aware side (`RoundRobin.next_side`, against
    an ASSUMED-full-fill running position, only when a quote exists),
    quantity clamped to displayed top-of-book size and, for a SELL, to the
    assumed sellable position (`clamp_sell_quantity`) -- each quote row's
    schema matches sim-capacity/fetcher.py's normalized output
    (`bid`/`ask`/`bid_size`/`ask_size`/`ts_ns`)."""
    symbols = sorted(quotes_by_symbol) if symbols is None else list(symbols)
    if not symbols:
        raise ValueError("symbols must be non-empty")
    for s in symbols:
        if not quotes_by_symbol.get(s):
            raise ValueError(f"no quotes for symbol {s!r}")

    rr = RoundRobin(symbols, position_cap)
    interval_ns = tick_interval_ns(submits_per_sec)
    all_start = min(row["ts_ns"] for s in symbols for row in quotes_by_symbol[s])
    all_end = max(row["ts_ns"] for s in symbols for row in quotes_by_symbol[s])
    lo = all_start if start_ns is None else max(start_ns, all_start)
    hi = all_end if end_ns is None else min(end_ns, all_end)
    if hi <= lo:
        raise ValueError("empty window after bounding to available quotes")

    ts_lists = {s: [row["ts_ns"] for row in quotes_by_symbol[s]] for s in symbols}
    assumed_position: dict[str, int] = {s: 0 for s in symbols}
    stream: list[OrderIntent] = []
    order_id = 0
    ts = lo + interval_ns
    while ts <= hi:
        symbol = rr.next_symbol()  # always advanced, even on a skip -- matches _on_tick
        quote = _quote_at_or_before(quotes_by_symbol[symbol], ts_lists[symbol], ts)
        if quote is not None:
            side = rr.next_side(symbol, assumed_position[symbol])
            bid, ask = Decimal(quote["bid"]), Decimal(quote["ask"])
            mid = (bid + ask) / 2
            if side == "BUY":
                limit_price, available, touch = ask + collar, quote["ask_size"], ask
            else:
                limit_price, available, touch = max(bid - collar, Decimal("0.01")), quote["bid_size"], bid
            qty = max(qty_min, min(qty_max, available))
            if side == "SELL":
                qty = clamp_sell_quantity(qty, assumed_position[symbol])
            if qty > 0:
                order_id += 1
                stream.append(OrderIntent(order_id=order_id, ts_ns=ts, symbol=symbol, side=side, qty=qty,
                                           limit_price=str(limit_price), touch_price=str(touch),
                                           mid_price=str(mid)))
                assumed_position[symbol] += qty if side == "BUY" else -qty
        ts += interval_ns
    return stream
