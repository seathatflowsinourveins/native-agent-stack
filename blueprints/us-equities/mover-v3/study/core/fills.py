"""populations.fill_quote, fill_price and terminal_exits.search_window: which quote fills, and when.

Quotes are dicts {"t" (epoch s), "bp", "ap", ...} sorted by t. Eligible = quotes.py valid_quote applied as a
predicate to ONE quote (bid > 0, ask > bid) and a regular-session timestamp (at or after 09:30 ET and before the
scheduled close of its session). The windows these functions search are derived in core.plan.
"""
from __future__ import annotations

import bisect

from pinned.quotes_copy import valid_quote
from core.params import T
from core.records import et_date


def eligible(cal, q) -> bool:
    if valid_quote([q]) is None:
        return False
    d = et_date(q["t"])
    return cal.is_session(d) and cal.in_regular(d, q["t"])


def mid(q) -> float:
    return (float(q["bp"]) + float(q["ap"])) / 2.0


def half_spread(q) -> float:
    """h_fill = (ask - bid) / (ask + bid), the realized half-spread as a fraction of the mid."""
    return (float(q["ap"]) - float(q["bp"])) / (float(q["ap"]) + float(q["bp"]))


def fill_at(cal, quotes: list, x: float, deadline: float):
    """(fill_time, quote, how) for a fill at or after x: the NBBO prevailing at x if eligible and at most 1000 ms
    old, else the first eligible update stamped after x and at or before deadline; None if there is none."""
    ts = [q["t"] for q in quotes]
    i = bisect.bisect_right(ts, x)
    if i:
        prev = quotes[i - 1]
        if eligible(cal, prev) and x - prev["t"] <= T["prevailing_max_age_s"]:
            return x, prev, "prevailing"
    for q in quotes[i:]:
        if q["t"] > deadline:
            break
        if eligible(cal, q):
            return q["t"], q, "next"
    return None


def last_eligible_bid(cal, quotes: list, after: float, at_or_before: float):
    """The bid of the latest eligible quote stamped after `after` and at or before `at_or_before` (terminal-merger
    booking and the terminal-zero sensitivity), with its time; None if there is none."""
    for q in reversed(quotes):
        if q["t"] > at_or_before:
            continue
        if q["t"] <= after:
            break
        if eligible(cal, q):
            return float(q["bp"]), q["t"]
    return None


def search_end(cal, planned_exit_session: str):
    """The scheduled close of E+5 (terminal_exits.search_window); None if the calendar ends before it."""
    last = cal.offset(planned_exit_session, T["search_sessions"])
    return None if last is None else cal.close(last)
