"""populations.formulas, official_prints, suspected_unadjusted_split and exclusions, restated exactly.

Every function takes plain dicts: a daily series is {session: {"o","h","l","c","v",...}} per adjustment, a print
series is {session: {"o": [...], "c": [...]}} (sessions_io's auction shape) and minute bars are lists of
{"t","o","h","l","c","v","vw"} with epoch-second starts. Undefined values are None and are counted by callers.
"""
from __future__ import annotations

import math
import re

import numpy as np

from pinned.rules_copy import Bars
from pinned.sessions_io_copy import official_price
from core.params import M, T

ACCEPTED_OPEN = ("opening_print_listing_exchange",)
ACCEPTED_CLOSE = ("closing_print_listing_exchange", "official_close_listing_exchange")


# ---------------------------------------------------------------- official prints

def close_label(day_auction) -> str:
    """The sessions_io source label of the close, or 'no_print' / 'no_opening_print'."""
    price, label = official_price(day_auction, "c")
    if label is None:
        return "no_print"
    opens = (day_auction or {}).get("o") or []
    if not any(o.get("c") == "O" for o in opens):
        return "no_opening_print"
    return label


def official_close(day_auction):
    """The accepted official close, else None (a closing_print_other_exchange or no O print counts as none)."""
    price, label = official_price(day_auction, "c")
    return float(price) if label in ACCEPTED_CLOSE else None


def official_open(day_auction):
    price, label = official_price(day_auction, "o")
    return float(price) if label in ACCEPTED_OPEN else None


def listing_exchange(day_auction):
    """The exchange of the largest condition-O opening print, or None (exclusions rule 1)."""
    opens = [o for o in ((day_auction or {}).get("o") or []) if o.get("c") == "O"]
    if not opens:
        return None
    return max(opens, key=lambda o: (o.get("s") or 0, o.get("x") or "")).get("x")


# ---------------------------------------------------------------- split factors

def a_factor(raw: dict, split: dict, s: str):
    """a(s) = raw daily close(s) / split-adjusted daily close(s); None without both bars."""
    r, p = raw.get(s), split.get(s)
    if not r or not p or not r.get("c") or not p.get("c"):
        return None
    return float(r["c"]) / float(p["c"])


def share_factor(raw: dict, split: dict, u: str, v: str):
    """F(u, v) = a(u) / a(v), 1 when |F - 1| <= 1e-2, None if either a is undefined. F(u, u) = 1."""
    if u == v:
        return 1.0 if a_factor(raw, split, u) is not None else None
    au, av = a_factor(raw, split, u), a_factor(raw, split, v)
    if au is None or av is None:
        return None
    f = au / av
    return 1.0 if abs(f - 1.0) <= M["split_tolerance"] else f


def f_step(cal, raw, split, j: str):
    """f(j) = F(j-1, j) for consecutive XNYS sessions."""
    prev = cal.offset(j, -1)
    return None if prev is None else share_factor(raw, split, prev, j)


def ref_close(cal, prints, raw, split, t: str):
    """ref(t) = accepted official close of the previous session / f(t); None if either is undefined."""
    prev = cal.offset(t, -1)
    c_prev = official_close(prints.get(prev)) if prev else None
    f = f_step(cal, raw, split, t)
    if c_prev is None or f is None:
        return None
    return c_prev / f


def gain_passes(close_t, ref_t) -> bool:
    return close_t is not None and ref_t is not None and close_t / ref_t - 1.0 >= M["gain_G"] - M["gain_eps"]


def r_return(cal, prints, raw, split, j: str):
    """r(j) = C(j) x f(j) / C(j-1) - 1; None if either close is missing or f(j) is undefined."""
    prev = cal.offset(j, -1)
    c_j = official_close(prints.get(j))
    c_p = official_close(prints.get(prev)) if prev else None
    f = f_step(cal, raw, split, j)
    if c_j is None or c_p is None or f is None:
        return None
    return c_j * f / c_p - 1.0


def suspected_unadjusted_split(raw_c_t, raw_c_prev, f_t) -> bool:
    """f(t) = 1 and the raw close ratio lies within 1% of an integer n or 1/n, n in 2..100."""
    if f_t is None or f_t != 1.0 or not raw_c_t or not raw_c_prev:
        return False
    r = raw_c_t / raw_c_prev
    tol = M["suspected_split_rel_tol"]
    for n in range(M["suspected_split_n_min"], M["suspected_split_n_max"] + 1):
        if abs(r - n) <= tol * n or abs(r - 1.0 / n) <= tol / n:
            return True
    return False


def suspected_at(cal, raw, split, t: str) -> bool:
    prev = cal.offset(t, -1)
    rt, rp = raw.get(t), raw.get(prev) if prev else None
    return suspected_unadjusted_split(rt["c"] if rt else None, rp["c"] if rp else None, f_step(cal, raw, split, t))


def max21(cal, prints, raw, split, t: str):
    """MAX21(t) = max of r(t-k), k = 1..21 (closes of t-22 .. t-1); None if any close or f is missing or any
    session t-21 .. t-1 is a suspected unadjusted split. Returns (value, reason)."""
    rs = []
    for k in range(1, M["max21_returns"] + 1):
        j = cal.offset(t, -k)
        if j is None:
            return None, "lookback_before_calendar"
        if suspected_at(cal, raw, split, j):
            return None, "suspected_split_in_window"
        r = r_return(cal, prints, raw, split, j)
        if r is None:
            return None, "missing_close_or_factor"
        rs.append(r)
    return max(rs), None


# ---------------------------------------------------------------- minute-bar quantities

def dv_reg(cal, minute_rows: list, s: str):
    """Summed vwap x volume of 1-minute bars of s starting at or after 09:30 ET and before the scheduled close;
    0 for a session with no such bar (rules.Bars.cum_dv arithmetic)."""
    bars = Bars.from_rows(minute_rows_of(cal, minute_rows, s), day_start=cal.at(s, T["premarket_start_hhmm"]))
    return bars.cum_dv(cal.close(s)) - bars.cum_dv(cal.open(s))


def minute_rows_of(cal, minute_rows: list, s: str) -> list:
    lo, hi = cal.at(s, T["premarket_start_hhmm"]), cal.close(s) + 4 * 3600
    return [b for b in minute_rows if lo <= b["t"] < hi]


def cum_dv_at(cal, minute_rows: list, s: str, ts: float) -> float:
    """The cost cell's dollar volume at a fill at ts (cost_model.lookup.cell_key): the summed vwap x volume of the
    session's 1-minute bars from 04:00 ET that are complete by ts, i.e. that start at or before ts - 60 s. Review
    round 15, F02: rules.Bars.cum_dv(ts) counts every bar that starts before ts, so a fill at 09:35:30 counted the
    whole 09:35 bar, volume traded after the fill, which could move the fill into a more liquid, cheaper dv tier.
    The pinned Bars arithmetic is kept; only completed bars are passed to it."""
    done = [b for b in minute_rows_of(cal, minute_rows, s) if b["t"] + T["entry_bar_complete_s"] <= ts]
    return Bars.from_rows(done, day_start=cal.at(s, T["premarket_start_hhmm"])).cum_dv(float("inf"))


def entry_bar_dv(cal, minute_rows: list, s: str, x: float):
    """vwap x volume of the last 1-minute bar of s (from 04:00 ET) that starts at or before x - 60 s; None if none."""
    rows = [b for b in minute_rows_of(cal, minute_rows, s) if b["t"] <= x - T["entry_bar_complete_s"]]
    if not rows:
        return None
    b = rows[-1]
    return float(b.get("vw") or b["c"]) * float(b["v"])


def window_sessions(cal, t: str, n: int) -> list:
    out = [cal.offset(t, -k) for k in range(n - 1, -1, -1)]
    return out if all(out) else []


def med20(dv_by_session: dict, sessions: list):
    vals = [dv_by_session.get(s) for s in sessions]
    if len(vals) != M["sizing_window"] or any(v is None for v in vals):
        return None
    return float(np.median(np.asarray(vals, dtype=float)))


def sigma_d(cal, prints, raw, split, sessions: list):
    """ddof = 1 sample sd of log(1 + r(j)) over W(t); None if any r(j) is undefined."""
    rs = [r_return(cal, prints, raw, split, j) for j in sessions]
    if len(rs) != M["sizing_window"] or any(r is None or r <= -1.0 for r in rs):
        return None
    return float(np.std(np.log1p(np.asarray(rs, dtype=float)), ddof=1))


# ---------------------------------------------------------------- exclusions

_WARRANT_5 = re.compile(r"[A-Z]{4}[WUR]$")
_DERIV = re.compile(r"\.(WS|U|R|W)")


def exclusion2(symbol: str) -> bool:
    """Warrants, units and rights (candidates.py's rule at aa6fc79) plus a '/' in the symbol (v3 addition)."""
    return bool((len(symbol) == 5 and _WARRANT_5.search(symbol)) or _DERIV.search(symbol) or "/" in symbol)


def exclusion3(cal, raw: dict, t: str) -> bool:
    """True (excluded) if fewer than 21 of the 22 sessions t-22 .. t-1 have a raw daily bar (review round 8, E8)."""
    sessions = [cal.offset(t, -k) for k in range(1, M["exclusion3_window"] + 1)]
    have = sum(1 for s in sessions if s is not None and raw.get(s))
    return have < M["exclusion3_min_bar_sessions"]


def contiguous_prior_bars(cal, raw: dict, t: str, limit: int = 60) -> int:
    n = 0
    for k in range(1, limit + 1):
        s = cal.offset(t, -k)
        if s is None or not raw.get(s):
            break
        n += 1
    return n


LANE_MIN_RAW_CLOSE = 1.0          # broad-universe descriptive_microcap_lane.min_raw_close_usd (the widest lane)
LANE_MED20_MIN = 2_000_000.0      # broad-universe descriptive_microcap_lane.median_dollar_volume_min_usd
LANE_PRIOR_BARS = 60              # broad-universe eligibility.min_prior_sessions_with_bars and window_contiguity


def least_exposed(cal, raw: dict, t: str) -> bool:
    """exposure_registry.consequence's slice: True when (symbol, t) was not a broad-universe lane decision. Restated
    from broad-universe protocol.json and evaluate.py at aa6fc79 (review round 9, L-7): a lane decision of the widest
    lane (descriptive_microcap, which contains every primary decision) needs a raw daily bar on t with raw close
    >= $1; 60 prior bars that are calendar-contiguous (span60 = 60, so neither insufficient_history nor has_gap);
    and med20, the median of raw close x raw volume over the 20 sessions t-20 .. t-1, > 0 and >= $2,000,000.
    Broad-universe's suffix exclusion needs no restatement: every v3 event passes exclusion 2, whose pattern removes
    every suffix broad-universe excludes. Limitation: the bars are the event's asof = t response, not
    broad-universe's default-asof history."""
    b = raw.get(t)
    if not b or b["c"] < LANE_MIN_RAW_CLOSE:
        return True
    if contiguous_prior_bars(cal, raw, t, LANE_PRIOR_BARS) < LANE_PRIOR_BARS:
        return True
    prior = [cal.offset(t, -k) for k in range(1, M["sizing_window"] + 1)]
    med = float(np.median([raw[s]["c"] * raw[s]["v"] for s in prior]))
    return med <= 0.0 or med < LANE_MED20_MIN


def finite(x) -> bool:
    return x is not None and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))
