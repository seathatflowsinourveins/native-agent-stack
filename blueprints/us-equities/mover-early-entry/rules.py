"""Pure per-symbol-day rules for protocol.json (mover-early-entry-v1-20260924).

Everything here is deterministic and takes plain arrays, so each definition can be tested without
the private data. Times are epoch seconds (UTC); a session's ET clock times come from ``et_epoch``.
Interpretations that the protocol text leaves open are recorded in clarifications.json and cited
here by id (C1, C2, ...).
"""
from __future__ import annotations

import json
from datetime import date, datetime, time as dtime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
TIMES = ("07:00", "08:00", "09:00", "09:25", "09:30", "09:35", "09:45", "10:00")
PLACEBO = {"07:00": "07:30", "08:00": "08:30", "09:00": "09:30", "09:25": "09:55", "09:30": "10:00",
           "09:35": "10:05", "09:45": "10:15", "10:00": "10:30"}
GAINS = (0.20, 0.30, 0.50, 1.00)
VOLUMES = (250_000, 1_000_000, 5_000_000)
NEWS = ("any", "news_before_t")
MIN_PRICE = 1.00
EXITS = ("X1", "X2", "X3", "X4")
DEGREE_TIERS = ((None, 0.30), (0.30, 0.50), (0.50, 1.00), (1.00, 3.00), (3.00, 10.00), (10.00, None))
SPLIT_TOLERANCE = 1e-2
# Cost buckets (protocol costs.table). C3: 09:25-09:30 belongs to the second bucket, which the
# protocol writes as 08:00-09:25, so the 09:25 rule's entries have a bucket; 16:00 is in the last.
TIME_BUCKETS = (("04:00", "08:00"), ("08:00", "09:30"), ("09:30", "10:00"), ("10:00", "16:01"))
PRICE_TIERS = (2.0, 5.0, 20.0)
DV_TIERS = (1_000_000.0, 5_000_000.0)
FEES = json.loads((Path(__file__).with_name("fees.json")).read_text())
# C26: NYSE scheduled 13:00 ET early closes, 2021-2026, from exchange_calendars 4.13.2 (XNYS schedule).
# The protocol's "16:00" (exit window, X1, halt flag, close fallback) is the session's close.
EARLY_CLOSES = frozenset({"2021-11-26", "2022-11-25", "2023-07-03", "2023-11-24", "2024-07-03", "2024-11-29",
                          "2024-12-24", "2025-07-03", "2025-11-28", "2025-12-24", "2026-11-27", "2026-12-24"})
GAIN_EPS = 1e-9  # C25: gain = price / ref - 1 is compared with G - 1e-9 so an exact +G price fires


def close_hhmm(day: str) -> str:
    return "13:00" if day in EARLY_CLOSES else "16:00"


@lru_cache(maxsize=None)
def et_epoch(day: str, hhmm: str) -> float:
    h, m = map(int, hhmm.split(":"))
    return datetime.combine(date.fromisoformat(day), dtime(h, m), ET).timestamp()


def split_factor(prev_raw_c, prev_all_c, raw_c, all_c):
    """f = (raw/adjusted close) on prev_date / the same on the session; ref = prev official close / f."""
    if not (prev_raw_c and prev_all_c and raw_c and all_c):
        return 1.0, False
    f = (prev_raw_c / prev_all_c) / (raw_c / all_c)
    return (f, True) if abs(f - 1) > SPLIT_TOLERANCE else (1.0, False)


def degree_tier_index(eventual_gain) -> int:
    for i, (lo, hi) in enumerate(DEGREE_TIERS):
        if (lo is None or eventual_gain >= lo) and (hi is None or eventual_gain < hi):
            return i
    raise ValueError(eventual_gain)


def tier_label(i: int) -> str:
    lo, hi = DEGREE_TIERS[i]
    return f"{'' if lo is None else f'{lo:.2f}'}-{'' if hi is None else f'{hi:.2f}'}"


def degree_tier(eventual_gain) -> str:
    return tier_label(degree_tier_index(eventual_gain))


class Bars:
    """One symbol-day's 1-minute bars as arrays (sorted, one bar per start time, from 04:00)."""

    def __init__(self, t, o, h, l, c, v, vw, day_start: float):
        keep = np.asarray(t, dtype=float) >= day_start
        self.t = np.asarray(t, dtype=float)[keep]
        self.o = np.asarray(o, dtype=float)[keep]
        self.h = np.asarray(h, dtype=float)[keep]
        self.l = np.asarray(l, dtype=float)[keep]
        self.c = np.asarray(c, dtype=float)[keep]
        self.dv = np.asarray(vw, dtype=float)[keep] * np.asarray(v, dtype=float)[keep]
        self.cumdv = np.cumsum(self.dv)

    @classmethod
    def from_rows(cls, rows, day_start):
        cols = list(zip(*[(b["t"], b["o"], b["h"], b["l"], b["c"], b["v"], b.get("vw") or b["c"]) for b in rows])) or [()] * 7
        return cls(*cols, day_start=day_start)

    def __len__(self):
        return len(self.t)

    def index(self, ts: float) -> int:
        """Number of bars starting before ts."""
        return int(np.searchsorted(self.t, ts, side="left"))

    def state(self, ts: float):
        """(price_at_ts, dollar_volume_at_ts): last close and summed vwap x volume of bars starting before ts."""
        i = self.index(ts)
        return (float(self.c[i - 1]), float(self.cumdv[i - 1])) if i else (None, 0.0)

    def cum_dv(self, ts: float) -> float:
        i = self.index(ts)
        return float(self.cumdv[i - 1]) if i else 0.0


def news_before(news: list, t: float, lag: float, since: float) -> bool:
    return any(since <= n <= t - lag for n in news)


def signal_cutoff(day: str, hhmm: str) -> float:
    return et_epoch(day, "09:28") if hhmm == "09:30" else et_epoch(day, hhmm)


def entry_for(day: str, hhmm: str, bars: Bars, official_open):
    """(entry_price, entry_ts, source, entry_bar_index) under entry_rules.entry_price.

    C1: "within 5 minutes of t" means a bar starting before t + 5 min."""
    t = et_epoch(day, hhmm)
    open_ts = et_epoch(day, "09:30")
    if hhmm == "09:30":
        if official_open is None:
            return None, None, "no_official_open", None
        return float(official_open), open_ts, "opening_auction", None
    limit = min(t + 300, open_ts) if t < open_ts else t + 300
    i = bars.index(t)
    if i < len(bars) and bars.t[i] < limit:
        return float(bars.o[i]), float(bars.t[i]), "bar_open", i
    return None, None, "no_bar_within_5m", None


def exits_for(entry: float, entry_ts: float, bars: Bars, day: str, official_close, daily_close=None):
    """{X: (exit_price, exit_ts, used_close_fallback)}, session_high_after_entry, halt flag, close source.

    The window is the entry bar through the last bar starting before the session close (C26). The close
    is the official close, else the daily bar close (C22; the audit's v2 fallback), else the session's
    last bar close before the close, else the entry price (each flagged)."""
    close_ts = et_epoch(day, close_hhmm(day))
    i0, i1 = bars.index(entry_ts), bars.index(close_ts)
    if official_close is not None:
        close, close_src = float(official_close), "official"
    elif daily_close:
        close, close_src = float(daily_close), "daily_close"
    elif i1 > 0:
        close, close_src = float(bars.c[i1 - 1]), "bar_close"
    else:
        close, close_src = float(entry), "entry_no_bars"
    t, o, h, l = bars.t[i0:i1], bars.o[i0:i1], bars.h[i0:i1], bars.l[i0:i1]
    out = {"X1": (close, close_ts, False)}
    # X2: the open of the first bar at or after entry + 60 min, before 16:00.
    k = int(np.searchsorted(t, entry_ts + 3600, side="left"))
    out["X2"] = (float(o[k]), float(t[k]), False) if k < len(t) else (close, close_ts, True)
    # X3: level for bar k is 0.85 x the running high through bar k-1 (starting at the entry price).
    running = np.maximum.accumulate(np.concatenate(([entry], h)))[:-1]
    level = 0.85 * running
    hit = np.flatnonzero(l <= level)
    if hit.size:
        k = int(hit[0])
        out["X3"] = (float(min(level[k], o[k])), float(t[k]), False)
    else:
        out["X3"] = (close, close_ts, True)
    # X4: bracket; an open at or beyond a level exits at the open, the stop is assumed first.
    stop, tp = 0.85 * entry, 1.50 * entry
    o_hit = (o <= stop) | (o >= tp)
    l_hit, h_hit = l <= stop, h >= tp
    hit = np.flatnonzero(o_hit | l_hit | h_hit)
    if hit.size:
        k = int(hit[0])
        px = o[k] if o_hit[k] else (stop if l_hit[k] else tp)
        out["X4"] = (float(px), float(t[k]), False)
    else:
        out["X4"] = (close, close_ts, True)
    high = float(max(entry, h.max())) if len(h) else float(entry)
    return out, high, halt_flag(bars, entry_ts, day), close_src


def halt_flag(bars: Bars, entry_ts: float, day: str) -> bool:
    """5+ consecutive minutes without a bar during 09:30-16:00 after entry (C2: the edges count)."""
    start = max(entry_ts, et_epoch(day, "09:30"))
    end = et_epoch(day, close_hhmm(day))
    n = int((end - start) // 60)
    if n < 5:
        return False
    t = bars.t[(bars.t >= start) & (bars.t < end)]
    if not len(t):
        return True
    m = np.unique(((t - start) // 60).astype(int))
    gaps = np.diff(np.concatenate(([-1], m, [n]))) - 1
    return bool((gaps >= 5).any())


def fires(price, dv, gain, news, g, v, variant) -> bool:
    return (gain is not None and gain >= g - GAIN_EPS and dv >= v and price is not None and price >= MIN_PRICE
            and (variant == "any" or bool(news)))


def time_bucket(day: str, ts: float):
    for i, (a, b) in enumerate(TIME_BUCKETS):
        if et_epoch(day, a) <= ts < et_epoch(day, b):
            return i
    return None


def price_tier(p: float) -> int:
    return int(np.searchsorted(PRICE_TIERS, p, side="right"))


def dv_tier(dv: float) -> int:
    return int(np.searchsorted(DV_TIERS, dv, side="right"))


def _row(table, day):
    for r in table:
        if r["from"] <= day <= r["to"]:
            return r
    raise KeyError(f"no fee row for {day}")


@lru_cache(maxsize=None)
def fee_rates(day: str):
    """(SEC USD per million of sales, FINRA TAF USD per share, TAF cap per trade) in force on day."""
    taf = _row(FEES["finra_taf_covered_equity_sales"], day)
    return _row(FEES["sec_section31_usd_per_million_of_sales"], day)["rate"], taf["usd_per_share"], taf["max_per_trade"]


def sell_fees(day: str, shares: float, sell_value: float) -> float:
    """SEC Section 31 fee plus FINRA TAF on a sale, in USD (fees.json; not rounded to the cent)."""
    sec, taf, cap = fee_rates(day)
    return sec * sell_value / 1e6 + min(taf * shares, cap)


def ibkr_commission(shares: float, value: float) -> float:
    c = FEES["ibkr_pro_tiered_us_stocks"]
    return min(max(c["min_per_order"], c["usd_per_share"] * shares), c["max_fraction_of_trade_value"] * value)


def net_return(entry, exit_, c_in, c_out, day, notional, broker="alpaca", mult=1.0):
    """Net long return for one round trip at a notional (C6).

    c_in and c_out are per-side spread+slippage fractions; mult scales them (stress = 2), not fees."""
    shares = notional / entry
    basis = shares * entry * (1 + mult * c_in)
    gross_sell = shares * exit_
    proceeds = gross_sell * (1 - mult * c_out) - sell_fees(day, shares, gross_sell)
    if broker == "ibkr":
        basis += ibkr_commission(shares, shares * entry)
        proceeds -= ibkr_commission(shares, gross_sell)
    return proceeds / basis - 1


def net_return_np(entry, exit_, c_in, c_out, sec, taf, cap, notional, broker="alpaca", mult=1.0):
    """net_return over arrays, with the same operations in the same order (bitwise equal)."""
    shares = notional / entry
    basis = shares * entry * (1 + mult * c_in)
    gross_sell = shares * exit_
    proceeds = gross_sell * (1 - mult * c_out) - (sec * gross_sell / 1e6 + np.minimum(taf * shares, cap))
    if broker == "ibkr":
        c = FEES["ibkr_pro_tiered_us_stocks"]
        per = c["usd_per_share"] * shares
        basis = basis + np.minimum(np.maximum(c["min_per_order"], per), c["max_fraction_of_trade_value"] * (shares * entry))
        proceeds = proceeds - np.minimum(np.maximum(c["min_per_order"], per), c["max_fraction_of_trade_value"] * gross_sell)
    return proceeds / basis - 1
