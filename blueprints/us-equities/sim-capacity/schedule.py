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


class RoundRobin:
    """Deterministic round-robin symbol/side picker with a per-symbol position
    cap. `next_order` never mutates state on a skip (cap reached and the
    opposite side is also capped, or no quote yet) -- it just returns None,
    leaving the caller's counters to record the skip."""

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

    def next_side(self, symbol: str, current_position: int) -> str | None:
        """Alternates BUY/SELL per symbol to keep inventory near flat, refusing
        a side that would push |position| past `position_cap`. Returns None if
        both sides are blocked (e.g. cap == 0, or a position exactly at +cap
        that the alternation would push further in the same direction twice in
        a row -- this cannot happen under normal alternation but is guarded
        defensively)."""
        preferred = "BUY" if self._last_side[symbol] == "SELL" else "SELL"
        other = "SELL" if preferred == "BUY" else "BUY"
        for side in (preferred, other):
            projected = current_position + (1 if side == "BUY" else -1)
            if abs(projected) <= self.position_cap:
                self._last_side[symbol] = side
                return side
        return None
