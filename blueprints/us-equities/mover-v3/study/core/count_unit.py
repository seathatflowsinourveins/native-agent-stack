"""chronology.holdout.count_unit: integers only, for the extension decision (review round 8, R8-8: count_unit is
used only for the extension decision; every stage's minimum sample uses the n that enters the statistic).

The count path evaluates presence and exclusion flags, decision-time inputs (MAX21, med20, the entry bar),
corporate-action records, the cumulative split factors a(s) and entry-quote presence. It computes no mid, spread,
return or exit value: trades.trade runs with mode "count" and returns before any booking.
"""
from __future__ import annotations

from core.params import CHRONO, MIN_SAMPLE
from core.trades import h3c_event, trade

KEYS = ("H1-D:high", "H1-D:low", "H1-D-b_lane-low", "H3-a", "H3-b", "H3-c")


def count(events: list, ctx, store, terc: dict) -> dict:
    if ctx.mode != "count":
        raise ValueError("count_unit runs only in count mode")
    out = {k: 0 for k in KEYS}
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
                if tc == "low":
                    out["H1-D:low"] += 1
                    out["H1-D-b_lane-low"] += 1
            elif arm == "a_intraday":
                out["H3-a"] += 1
            else:
                out["H3-b"] += 1
        if h3c_event(ev, ctx)["status"] == "counted":
            out["H3-c"] += 1
    if needs:
        return {"needs": needs}
    return out


def below_minimum(counts: dict, carried: tuple) -> list:
    """Carried items whose smallest key is below the holdout minimum."""
    low = []
    for item in carried:
        if item == "H1-D":
            if min(counts["H1-D:high"], counts["H1-D:low"]) < MIN_SAMPLE["difference_test_per_group"]["holdout"]:
                low.append(item)
        elif counts[item] < MIN_SAMPLE["tradable_cell"]["holdout"]:
            low.append(item)
    return low


def extension_decision(counts: dict, carried: tuple, blocks_done: int) -> dict:
    low = below_minimum(counts, carried)
    if low and blocks_done < CHRONO["max_extension_blocks"]:
        return {"extend": True, "below_minimum": low, "next_block": blocks_done + 1}
    return {"extend": False, "below_minimum": low, "underpowered": low if low else []}
