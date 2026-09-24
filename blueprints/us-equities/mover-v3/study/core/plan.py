"""The request plan (review round 8, R8-1): which symbols, asof values, sessions, stamps and quote windows are
requested. It lives in the frozen evaluation tree, never under study/fetch/, and is derived only from sealed inputs
(the calendar, the enumeration, corporate-action records, decision-time inputs and the timestamps and eligibility
of already sealed quotes). A transport deviation cannot change it, and the reproduction check regenerates it from a
sealed snapshot and requires byte equality with the sealed request records.

Request kinds and their shapes (universe_and_identity.request_shapes):
  assets, corporate_actions                   enumeration (no asof; the corporate-action end is the fetch date)
  screen_daily_{raw,split,all}, screen_auctions  sessions s-1 and s for a batch of symbols, asof = s
  event_daily_{raw,split,all}                 as-known symbol, asof = t, t-60 .. end session
  event_auctions                              asof = t, t-22 .. end session
  event_minute                                asof = t, 04:00 ET of t-19 .. scheduled close of the end session
  quote_entry, quote_exit, quote_backward, quote_rename  quote windows (below), asof = t (rename: asof = the
                                              rename session, a sensitivity only)
The end session of an event is E+5 for its latest planned exit E (b_lane's, censored at the segment end), or t
for a decision whose entry session lies in no segment.

Quote windows. Entry at stamp X: [X - 1 s, X + 300 s]. Exit at planned stamp X on session E: W0 = [X - 1 s,
min(X + 300 s, close(E))], W1 = [X + 300 s, close(E)] when X + 300 s is before the close, then one window per
session E+1 .. E+5, [open, close]. A window is requested only when every earlier window of the same exit is
complete and holds no fill. Backward (review round 8, R8-7): for a trade whose forward search found no eligible
quote, one window per session from E back to the entry session, [max(open, entry fill), min(close, X)], each
requested only when every later one is complete and holds no eligible quote after the entry fill.
"""
from __future__ import annotations

import math

from core.calendar import iso_utc
from core.canon import dumps, sha256_obj
from core.params import FETCH, T

DATA, TRADING = "data", "trading"
ADJ = ("raw", "split", "all")


def make(kind: str, api: str, endpoint: str, params: dict, asof_session: str | None, parser: str) -> dict:
    params = {k: v for k, v in params.items() if v is not None}
    core = {"api": api, "endpoint": endpoint, "params": params}
    return {"key": f"{kind}|{sha256_obj(core)[:32]}", "kind": kind, "api": api, "endpoint": endpoint,
            "params": params, "asof_session": asof_session, "parser": parser}


def record(req: dict) -> str:
    """The canonical request record (one JSON line) compared byte for byte by the reproduction check."""
    return dumps({k: req[k] for k in ("key", "kind", "api", "endpoint", "params", "asof_session", "parser")})


def t_floor(ts: float) -> str:
    return iso_utc(math.floor(ts))


def t_ceil(ts: float) -> str:
    return iso_utc(math.ceil(ts))


# ---------------------------------------------------------------- enumeration

def assets_requests() -> list:
    return [make("assets", TRADING, "/v2/assets", {"status": st, "asset_class": "us_equity"}, None, "assets")
            for st in ("active", "inactive")]


def corporate_actions_request(start: str, end: str) -> dict:
    return make("corporate_actions", DATA, "/v1/corporate-actions",
                {"start": start, "end": end, "limit": 1000}, None, "corporate_actions")


# ---------------------------------------------------------------- screen

def batches(symbols: list, size: int | None = None) -> list:
    size = size or FETCH["screen_symbols_per_request"]
    symbols = sorted(symbols)
    return [symbols[i: i + size] for i in range(0, len(symbols), size)]


def screen_requests(cal, s: str, symbols: list) -> list:
    prev = cal.offset(s, -1)
    out = []
    for batch in batches(symbols):
        syms = ",".join(batch)
        for adj in ADJ:
            out.append(make(f"screen_daily_{adj}", DATA, "/v2/stocks/bars",
                            {"symbols": syms, "timeframe": "1Day", "start": prev, "end": s, "adjustment": adj,
                             "asof": s, "feed": FETCH["feed"], "limit": FETCH["page_limit"]}, s, "daily_bars"))
        out.append(make("screen_auctions", DATA, "/v2/stocks/auctions",
                        {"symbols": syms, "start": prev, "end": s, "asof": s, "feed": FETCH["feed"],
                         "limit": FETCH["page_limit"]}, s, "auctions"))
    return out


# ---------------------------------------------------------------- per event

def event_requests(cal, symbol: str, t: str, end: str) -> list:
    d60, d22, d19 = cal.offset(t, -60), cal.offset(t, -22), cal.offset(t, -19)
    if d60 is None:
        raise ValueError(f"the calendar does not reach 60 sessions before {t}")
    out = [make(f"event_daily_{adj}", DATA, "/v2/stocks/bars",
                {"symbols": symbol, "timeframe": "1Day", "start": d60, "end": end, "adjustment": adj, "asof": t,
                 "feed": FETCH["feed"], "limit": FETCH["page_limit"]}, t, "daily_bars") for adj in ADJ]
    out.append(make("event_auctions", DATA, "/v2/stocks/auctions",
                    {"symbols": symbol, "start": d22, "end": end, "asof": t, "feed": FETCH["feed"],
                     "limit": FETCH["page_limit"]}, t, "auctions"))
    out.append(make("event_minute", DATA, "/v2/stocks/bars",
                    {"symbols": symbol, "timeframe": "1Min", "start": t_floor(cal.at(d19, T["premarket_start_hhmm"])),
                     "end": t_ceil(cal.close(end)), "adjustment": "raw", "asof": t, "feed": FETCH["feed"],
                     "limit": FETCH["page_limit"]}, t, "minute_bars"))
    return out


def quote_request(kind: str, symbol: str, asof: str, start: float, end: float) -> dict:
    return make(kind, DATA, "/v2/stocks/quotes",
                {"symbols": symbol, "start": t_floor(start), "end": t_ceil(end), "asof": asof, "feed": FETCH["feed"],
                 "limit": FETCH["page_limit"], "sort": "asc"}, asof, "quotes")


# ---------------------------------------------------------------- stamps and windows

def entry_stamp(cal, t: str, arm: str) -> float:
    d1 = cal.offset(t, 1)
    if arm == "b_overnight":
        return cal.stamp_1555(d1)
    decision = cal.at(t, T["decision_hhmm"])
    return max(cal.at(d1, T["entry_hhmm"]), decision + T["min_latency_s"])


def entry_deadline(x: float) -> float:
    return x + T["entry_timeout_s"]


def entry_window(cal, symbol: str, t: str, arm: str) -> dict:
    x = entry_stamp(cal, t, arm)
    return quote_request("quote_entry", symbol, t, x - T["prevailing_max_age_s"], entry_deadline(x))


def planned_exit(cal, t: str, arm: str, seg_last: str):
    """(E, X, censored): the planned exit session and stamp, censored at 15:55 ET of the segment's last session."""
    if arm == "b_lane":
        e = cal.offset(t, T["holding_sessions_b_lane"])
        x = cal.stamp_1555(e) if e else None
    elif arm == "a_intraday":
        e = cal.offset(t, 1)
        x = cal.stamp_1555(e)
    elif arm == "b_overnight":
        e = cal.offset(t, 2)
        x = cal.open(e) if e else None
    else:
        raise ValueError(arm)
    if e is None or e > seg_last:
        return seg_last, cal.stamp_1555(seg_last), True
    return e, x, False


def exit_windows(cal, e: str, x: float) -> list:
    """[(start, end)] of the forward search from stamp x on session e through the close of E+5."""
    close = cal.close(e)
    w = [(x - T["prevailing_max_age_s"], min(x + T["entry_timeout_s"], close))]
    if x + T["entry_timeout_s"] < close:
        w.append((x + T["entry_timeout_s"], close))
    for k in range(1, T["search_sessions"] + 1):
        d = cal.offset(e, k)
        if d is None:
            break
        w.append((cal.open(d), cal.close(d)))
    return w


def backward_windows(cal, entry_session: str, entry_fill: float, e: str, x: float) -> list:
    """[(start, end)] from session e back to the entry session, clipped to (entry fill, x]."""
    out = []
    d = e
    while d is not None and d >= entry_session:
        lo, hi = max(cal.open(d), entry_fill), min(cal.close(d), x)
        if lo <= hi:
            out.append((lo, hi))
        d = cal.offset(d, -1)
    return out


def event_end(cal, t: str, segs: list) -> str:
    """E+5 of the b_lane exit (censored at the segment end), or t if the entry session lies in no segment."""
    from core.chronology import segment_of
    d1 = cal.offset(t, 1)
    i = segment_of(segs, d1) if d1 else None
    if i is None:
        return t
    e, _, _ = planned_exit(cal, t, "b_lane", segs[i][1])
    end = cal.offset(e, T["search_sessions"])
    return end or cal.days[-1]


# ---------------------------------------------------------------- prospective collection (holdout_gate)

def collection_requests(cal, sessions: list, symbols: list, previous_renames: list, fetch_date: str,
                        actions_start: str = "2016-01-01") -> list:
    """One collection batch: the enumeration refresh (asset master and corporate actions to the fetch date), the
    screen of each collected session s (daily bars raw, split and all and auctions of s-1 and s, asof = s) for the
    whole enumerated list, and the logged rename-day re-fetch: for every name_change record effective (process_date)
    on a session s of the previous batch, the rows of s-1 and s under the new symbol with asof = s. No quote and no
    minute bar is collected, and nothing selects symbols by membership."""
    out = assets_requests() + [corporate_actions_request(actions_start, fetch_date)]
    for s in sessions:
        out.extend(screen_requests(cal, s, symbols))
    for rec in previous_renames:
        s = rec.get("date")
        if rec.get("type") == "name_change" and rec.get("new_symbol") and s and cal.is_session(s):
            for r in screen_requests(cal, s, [rec["new_symbol"]]):
                out.append({**r, "kind": "rename_refetch_" + r["kind"], "key": "rename_refetch_" + r["key"]})
    return out


def late_collected(cal, batches: list) -> list:
    """Sessions whose batch was not timely: a batch is timely if its accrual log became reachable from origin/main
    before 09:30 ET of the session after its last session. batches: [{"sessions": [...], "reachable": epoch s}]."""
    late = []
    for b in batches:
        nxt = cal.offset(b["sessions"][-1], 1)
        if b.get("reachable") is None or nxt is None or b["reachable"] >= cal.at(nxt, "09:30"):
            late.extend(b["sessions"])
    return sorted(late)
