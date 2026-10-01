"""Pure schedule/budget/round-robin math for the capacity exerciser, kept free
of any nautilus_trader import so it is unit-testable on system Python.
"""
from __future__ import annotations

NS_PER_SEC = 1_000_000_000
NS_PER_MIN = 60 * NS_PER_SEC


def tick_interval_ns(submits_per_sec: float) -> int:
    if submits_per_sec <= 0:
        raise ValueError("submits_per_sec must be positive")
    return round(NS_PER_SEC / submits_per_sec)


def expected_submits_per_min(submits_per_sec: float) -> float:
    return submits_per_sec * 60.0


def minute_bucket(ts_ns: int, start_ns: int) -> int:
    """0-based simulated-minute index containing `ts_ns`, relative to `start_ns`."""
    if ts_ns < start_ns:
        raise ValueError("ts_ns before start_ns")
    return (ts_ns - start_ns) // NS_PER_MIN


def full_minutes(window_ns: int) -> int:
    """Count of full (complete, non-partial) 60s buckets in a window of
    `window_ns` nanoseconds."""
    return window_ns // NS_PER_MIN


def clamp_sell_quantity(desired_qty: int, sellable_position: int) -> int:
    """Never ask to sell more than the currently unreserved long position
    (which may itself already be reduced below the raw filled position by
    other SELL orders for the same symbol still in flight -- see
    `exerciser.CapacityExerciser._on_tick`'s `sellable_position` computation).
    A standalone pure function specifically so this exact clamp arithmetic is
    unit-testable without a running engine or a registered Strategy (whose
    `cache`/`portfolio`/`clock` attributes are not writable outside one)."""
    return max(0, min(desired_qty, sellable_position))


class RoundRobin:
    """Deterministic round-robin symbol/side picker with a per-symbol position
    cap, inventory-aware so it never proposes a short sale.

    The exerciser trades a plain Alpaca CASH account, which rejects any sell
    that would take a position negative ("Short selling not permitted on a
    CASH account" -- measured directly: 162/163 elite rejects and 112/113
    paper rejects in an earlier run were exactly this, before this fix).
    `next_side` therefore never returns SELL when `current_position <= 0`; it
    always returns a legal side (never None), and the caller is responsible
    for additionally clamping a SELL's quantity to `min(qty, current_position)`
    so a sell can never ask for more shares than are actually held."""

    def __init__(self, symbols: list[str], position_cap: int):
        if not symbols:
            raise ValueError("symbols must be non-empty")
        if position_cap <= 0:
            raise ValueError("position_cap must be positive")
        self.symbols = list(symbols)
        self.position_cap = position_cap
        self._index = 0
        self._last_side = {s: "SELL" for s in symbols}  # so the first pick per symbol is BUY

    def next_symbol(self) -> str:
        symbol = self.symbols[self._index % len(self.symbols)]
        self._index += 1
        return symbol

    def next_side(self, symbol: str, current_position: int) -> str:
        """Flat or short (<=0): always BUY (a CASH account cannot cover a sell
        from a non-positive position). At or above the cap: always SELL (never
        grow the position further). Otherwise, alternate BUY/SELL per symbol
        to keep inventory oscillating near flat, exactly as before."""
        if current_position <= 0:
            side = "BUY"
        elif current_position >= self.position_cap:
            side = "SELL"
        else:
            side = "BUY" if self._last_side[symbol] == "SELL" else "SELL"
        self._last_side[symbol] = side
        return side
