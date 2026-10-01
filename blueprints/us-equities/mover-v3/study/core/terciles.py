"""tercile_rule: trailing MAX21 breakpoints known at the decision, assignment and the 60-event minimum."""
from __future__ import annotations

import bisect

import numpy as np

from core.params import TERC


def trailing_window(pool: list, s: str) -> list:
    """The 252 most recent pool sessions strictly before s (pool is sorted, kept sessions only)."""
    i = bisect.bisect_left(pool, s)
    return pool[max(0, i - TERC["window_sessions"]): i]


def breakpoints(pool: list, max21_by_session: dict, s: str):
    """(q1, q2) = numpy 'linear' 1/3 and 2/3 quantiles of the defined MAX21 of every D event decided in the
    trailing window; None if fewer than 60 such events (the event is unassigned)."""
    vals = [m for d in trailing_window(pool, s) for m in max21_by_session.get(d, ()) if m is not None]
    if len(vals) < TERC["minimum_prior_events"]:
        return None
    q = np.quantile(np.asarray(vals, dtype=float), TERC["quantiles"], method="linear")
    return float(q[0]), float(q[1])


def assign(m, bps):
    """'low' if MAX21 <= q1, 'high' if MAX21 > q2, else 'middle'; None when MAX21 or the breakpoints are undefined."""
    if m is None or bps is None:
        return None
    q1, q2 = bps
    if m <= q1:
        return "low"
    if m > q2:
        return "high"
    return "middle"


def pool_development(cal, dropped_years=frozenset()) -> list:
    from core.calendar import year_of
    return [d for d in cal.range("2016-01-04", "2019-12-31") if year_of(d) not in dropped_years]


def pool_validation(cal, dropped_years=frozenset()) -> list:
    from core.calendar import year_of
    return [d for d in cal.range("2020-01-02", "2020-12-31") if year_of(d) not in dropped_years]


def pool_holdout(cal, n0: str, last: str) -> list:
    """Sessions before 2026-01-02 from the breakpoint screen (2024-11-01 .. 2025-12-31) plus holdout sessions;
    the gap 2026-01-02 .. N0 - 1 is never in the pool."""
    part_a = cal.range(TERC["holdout_breakpoint_screen_start"], TERC["holdout_breakpoint_screen_end"])
    return part_a + cal.range(n0, last)
