"""chronology.holdout.count_unit: integers only, for the extension decision (review round 8, R8-8: count_unit is
used only for the extension decision; every stage's minimum sample uses the n that enters the statistic).

The count path evaluates presence and exclusion flags, decision-time inputs (MAX21, med20, the entry bar),
corporate-action records, the cumulative split factors a(s) and entry-quote presence. It computes no mid, spread,
return or exit value: trades.trade runs with mode "count" and returns before any booking.

Review round 16, F06: alongside each KEYS entry's trade count, the count also tracks that key's occupied entry
sessions (a set's size, so still an integer; entry_session is known at count time from trade()/h3c_event() without
any price or return value), reported under SESSION_KEYS. below_minimum reads both, so the extension decision also
sees the fixed occupied-session floor (core.params.MIN_SAMPLE["min_occupied_sessions"]), not only the trade-count
minimum: an item that already meets its sample minimum but not the floor still gets the chance an extension gives it,
the same as one short of the sample minimum.
"""
from __future__ import annotations

from core.params import CHRONO, MIN_SAMPLE
from core.trades import h3c_event, trade

KEYS = ("H1-D:high", "H1-D:low", "H1-D-b_lane-low", "H3-a", "H3-b", "H3-c")
SESSION_KEYS = tuple(f"{k}:sessions" for k in KEYS)
MIN_OCCUPIED_SESSIONS = MIN_SAMPLE["min_occupied_sessions"]


def count(events: list, ctx, store, terc: dict) -> dict:
    if ctx.mode != "count":
        raise ValueError("count_unit runs only in count mode")
    out = {k: 0 for k in KEYS}
    sessions = {k: set() for k in KEYS}
    needs = []
    for ev in events:
        tc = terc.get((ev["symbol"], ev["t"]))
        for arm in ("b_lane", "a_intraday", "b_overnight"):
            tr = trade(ev, arm, ctx, store)
            if "needs" in tr:
                needs.extend(tr["needs"])
                continue
            if tr["status"] != "counted":
                continue
            if arm == "b_lane":
                if tc == "high":
                    out["H1-D:high"] += 1
                    sessions["H1-D:high"].add(tr["entry_session"])
                if tc == "low":
                    out["H1-D:low"] += 1
                    out["H1-D-b_lane-low"] += 1
                    sessions["H1-D:low"].add(tr["entry_session"])
                    sessions["H1-D-b_lane-low"].add(tr["entry_session"])
            elif arm == "a_intraday":
                out["H3-a"] += 1
                sessions["H3-a"].add(tr["entry_session"])
            else:
                out["H3-b"] += 1
                sessions["H3-b"].add(tr["entry_session"])
        h3c = h3c_event(ev, ctx)
        if h3c["status"] == "counted":
            out["H3-c"] += 1
            sessions["H3-c"].add(h3c["entry_session"])
    if needs:
        return {"needs": needs}
    return {**out, **{f"{k}:sessions": len(sessions[k]) for k in KEYS}}


def below_minimum(counts: dict, carried: tuple) -> list:
    """Carried items whose smallest key is below the holdout minimum, or whose occupied entry sessions (the
    smallest key's :sessions companion) are below the fixed floor (review round 16, F06)."""
    low = []
    for item in carried:
        if item == "H1-D":
            if min(counts["H1-D:high"], counts["H1-D:low"]) < MIN_SAMPLE["difference_test_per_group"]["holdout"] \
                    or min(counts["H1-D:high:sessions"], counts["H1-D:low:sessions"]) < MIN_OCCUPIED_SESSIONS:
                low.append(item)
        elif counts[item] < MIN_SAMPLE["tradable_cell"]["holdout"] \
                or counts[f"{item}:sessions"] < MIN_OCCUPIED_SESSIONS:
            low.append(item)
    return low


def extension_decision(counts: dict, carried: tuple, blocks_done: int) -> dict:
    low = below_minimum(counts, carried)
    if low and blocks_done < CHRONO["max_extension_blocks"]:
        return {"extend": True, "below_minimum": low, "next_block": blocks_done + 1}
    return {"extend": False, "below_minimum": low, "underpowered": low if low else []}
