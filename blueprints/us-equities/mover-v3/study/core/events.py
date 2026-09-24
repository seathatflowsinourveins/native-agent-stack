"""Per-event data and D membership: DV_reg (the last membership condition), exclusion 3, MAX21, med20, sigma_d.

Every per-event quantity is computed within the event's own asof = t responses; screen rows are never joined in
(universe_and_identity.request_shapes). Fetch failures (review round 8, R8-5 and E5): an incomplete per-event
minute-bar or raw daily-bar request makes the candidate membership-unknown (excluded, counted); an incomplete
split, all or auction request excludes the event from every item (counted per item by the caller).
"""
from __future__ import annotations

from collections import Counter

from core import formulas as FM
from core import plan
from core.params import M


class Unsealed(KeyError):
    pass


def event_data(store, cal, symbol: str, t: str, end: str, strict: bool = True, holdout: bool = False):
    reqs = {r["kind"]: r for r in plan.event_requests(cal, symbol, t, end, holdout=holdout)}
    status = {k: store.status(r["key"]) for k, r in reqs.items()}
    missing = [k for k, v in status.items() if v is None]
    if missing:
        if strict:
            raise Unsealed(f"{symbol} {t}: unsealed per-event requests {missing}")
        return {"needs": [reqs[k] for k in missing]}
    get = lambda k: store.parsed(reqs[k]["key"]) if status[k] == "complete" else None  # noqa: E731
    daily = {adj: (get(f"event_daily_{adj}") or {}).get(symbol, {}) for adj in plan.ADJ}
    return {"symbol": symbol, "t": t, "end": end, "daily": daily,
            "prints": (get("event_auctions") or {}).get(symbol, {}),
            "minute": (get("event_minute") or {}).get(symbol, []),
            "incomplete": sorted(k for k, v in status.items() if v != "complete"),
            "empty": sorted(k for k, r in reqs.items() if status[k] == "complete" and store.empty(r["key"], symbol))}


def build_event(cal, cand: dict, data: dict, counts: Counter, holdout: bool = False):
    """The D event for a screen candidate, or None (with the reason counted). A holdout event has no least-exposed
    flag: the slice is a validation sensitivity, and its t-60 lookback is not fetched at the holdout (L-5)."""
    sym, t = cand["symbol"], cand["t"]
    inc = set(data["incomplete"])
    for k in data["empty"]:
        counts[f"event_request_empty:{k}"] += 1
    if "event_minute" in inc or "event_daily_raw" in inc:
        counts["membership_unknown:event_fetch_incomplete"] += 1
        return None
    raw, split, allc = data["daily"]["raw"], data["daily"]["split"], data["daily"]["all"]
    minute, prints = data["minute"], data["prints"]
    dv = FM.dv_reg(cal, minute, t)
    if dv == 0.0 and (raw.get(t) or {}).get("v", 0) > 0:
        counts["candidate_volume_but_no_regular_minute_bar"] += 1
    if dv < M["min_dv_reg"]:
        counts["not_event:dv_reg_below_floor"] += 1
        return None
    if FM.exclusion3(cal, raw, t):
        counts["not_event:exclusion3_short_history"] += 1
        return None
    for d, screen_val in ((t, cand.get("close_t")), (cal.offset(t, -1), cand.get("prev_close"))):
        per_event = FM.official_close(prints.get(d))
        if per_event is not None and screen_val is not None and per_event != screen_val:
            counts["per_event_close_differs_from_screen"] += 1
    m21, reason = (None, "event_fetch_incomplete") if ({"event_daily_split", "event_auctions"} & inc) else \
        FM.max21(cal, prints, raw, split, t)
    if m21 is None:
        counts[f"max21_undefined:{reason}"] += 1
    w = FM.window_sessions(cal, t, M["sizing_window"])
    dvs = {d: FM.dv_reg(cal, minute, d) for d in w}
    med = FM.med20(dvs, w)
    sig = FM.sigma_d(cal, prints, raw, split, w) if not ({"event_daily_split", "event_auctions"} & inc) else None
    return {"symbol": sym, "t": t, "dv_reg": dv, "max21": m21, "med20": med, "sigma_d": sig,
            "least_exposed": None if holdout else FM.least_exposed(cal, raw, t), "incomplete": sorted(inc), "data": data,
            "raw": raw, "split": split, "all": allc, "prints": prints, "minute": minute}
