"""Pure rule functions for the Stocks-in-Play 5-minute ORB replication (protocol.json).

Stdlib only and free of I/O, so every rule can be exercised on synthetic fixtures by the system Python.
This file shadows the stdlib ``signal`` module by name, so callers load it by path under another module
name (``load_signal()`` in ``orb_common.py``). Each entry script imports the stdlib ``signal`` before it
puts this directory on ``sys.path``, so a later ``import signal`` anywhere still gets the stdlib module.

Conventions
- A minute bar is a tuple ``(minute, o, h, l, c, v)``; ``minute`` is minutes after midnight ET of the
  bar's start (570 = the 09:30-09:31 bar). Bars are sorted by minute and a minute without trades has no bar.
- ``direction`` is +1 (long, buy-stop at the opening-range high), -1 (short, sell-stop at the low) or
  0 (doji, no order).
- Prices are raw (unadjusted) on the decision session's basis. ``r_ps`` is the paper's R per share:
  10% of the 14-day ATR.
"""
from __future__ import annotations

import math

OPEN_MINUTE = 570          # 09:30 ET
OR_MINUTES = 5             # 5-minute opening range: bars 570..574
ENTRY_FROM = OPEN_MINUTE + OR_MINUTES  # stop orders are live from the 09:35 bar
WINDOW = 14                # paper: 14-day ATR, 14-day average volume, 14-day mean OR volume
MIN_OPEN = 5.0             # paper filter 1: open > $5
MIN_AVG_VOLUME = 1_000_000.0  # paper filter 2: average volume >= 1,000,000 shares
MIN_ATR = 0.50             # paper filter 3: ATR > $0.50
MIN_RELVOL = 1.0           # paper filter 4: relative volume >= 100%
TOP_N = 20                 # paper filter 5: top 20 by relative volume
STOP_ATR_FRACTION = 0.10   # stop 10% of ATR from the executed entry price
SPLIT_TOLERANCE = 1e-2     # a day-over-day adjustment-factor change above 1% is treated as a split
TICK = 0.01                # Reg NMS sub-penny rule: $0.01 increment for quotes >= $1 (F2 slippage)


# ---------------------------------------------------------------- opening range and direction

def opening_range(bars):
    """(open, high, low, close, volume, n_bars) over bars 570..574, or None when that window has no bar.

    open is the first bar's open and close the last bar's close inside the window (the 5-minute candle)."""
    rng = [b for b in bars if OPEN_MINUTE <= b[0] < ENTRY_FROM]
    if not rng:
        return None
    return (rng[0][1], max(b[2] for b in rng), min(b[3] for b in rng), rng[-1][4],
            math.fsum(b[5] for b in rng), len(rng))


def direction(or_open: float, or_close: float) -> int:
    """+1 when the 5-minute candle closes up, -1 when down, 0 for a doji (open == close, no order)."""
    if or_close > or_open:
        return 1
    if or_close < or_open:
        return -1
    return 0


# ---------------------------------------------------------------- 14-day windows (sessions strictly before t)

def split_between(prev_factor: float, today_factor: float) -> float:
    """Split ratio f between session t-1 and t from the share-adjustment factor all_v/raw_v.

    prev_factor = all_v/raw_v on t-1; today_factor = all_v/raw_v on t. The factor is the cumulative split
    multiplier after a session, so it changes only at a split (not at dividends or spin-offs, which move
    the price factor). Only the ratio of session t is read, never its volume or prices (deviation D8).
    f > 1 for a forward split (f new shares per old share); |f - 1| <= 1% returns 1.0."""
    if not (prev_factor and today_factor) or prev_factor <= 0 or today_factor <= 0:
        return 1.0
    f = prev_factor / today_factor
    return f if abs(f - 1.0) > SPLIT_TOLERANCE else 1.0


def atr14(prior, split: float = 1.0):
    """14-day ATR in raw price units of session t.

    prior: the WINDOW + 1 = 15 sessions t-15..t-1 (oldest first), each (all_h, all_l, all_c, raw_c); only
    sessions strictly before t. True range uses the adjusted series so a split inside the window does not
    create a false range; the mean is rescaled to t-1's raw basis by raw_c/all_c on t-1 and divided by the
    split ratio between t-1 and t. Simple mean of 14 true ranges (the paper's footnote 1 average)."""
    if len(prior) != WINDOW + 1:
        return None
    trs = []
    for i in range(1, WINDOW + 1):
        h, low, _, _ = prior[i]
        prev_c = prior[i - 1][2]
        trs.append(max(h, prev_c) - min(low, prev_c))
    last = prior[-1]
    if not last[2] or last[2] <= 0:
        return None
    return math.fsum(trs) / WINDOW * (last[3] / last[2]) / split


def avg_volume14(prior, split: float = 1.0):
    """14-day average share volume in session t's share units.

    prior: the 14 sessions t-14..t-1, each (all_v, raw_v). all_v is split-adjusted to the dataset's end;
    raw_v/all_v on t-1 rescales it to t-1's shares, and the split ratio to t's shares."""
    if len(prior) != WINDOW:
        return None
    all_v_last, raw_v_last = prior[-1]
    if not all_v_last or all_v_last <= 0 or raw_v_last is None or raw_v_last <= 0:
        return None
    return math.fsum(v for v, _ in prior) / WINDOW * (raw_v_last / all_v_last) * split


def relative_volume(or_volume_t: float, prior, split: float = 1.0):
    """Paper eq.: ORVolume_t / ((1/14) * sum_{i=1..14} ORVolume_{t-i}), all in session t's share units.

    prior: the 14 sessions t-14..t-1, each (or_volume_raw, all_v, raw_v). A session's raw OR volume is
    moved to t-1's shares by (all_v/raw_v on that session) / (all_v/raw_v on t-1), then to t's by the
    split ratio. Returns None when the window is incomplete or its mean is zero."""
    if len(prior) != WINDOW:
        return None
    k_last = _vol_factor(prior[-1][1], prior[-1][2])
    if k_last is None:
        return None
    total = 0.0
    for orv, all_v, raw_v in prior:
        k = _vol_factor(all_v, raw_v)
        if k is None or orv is None:
            return None
        total += orv * k / k_last
    mean = total / WINDOW * split
    if mean <= 0:
        return None
    return or_volume_t / mean


def _vol_factor(all_v, raw_v):
    if all_v is None or raw_v is None or all_v <= 0 or raw_v <= 0:
        return None
    return all_v / raw_v


def day_features(sessions, i: int, daily: dict, orr: dict, or_volume_t: float):
    """(atr14, avg_volume14, relvol, split, reason) for session sessions[i] of one symbol.

    sessions: the calendar's session dates (sorted). daily: date -> (raw_o, raw_c, raw_v, all_o, all_h,
    all_l, all_c, all_v). orr: date -> (or_open, or_high, or_low, or_close, or_vol, or_n, rth_bars).
    Reads daily rows of sessions i-15..i-1 and OR rows of i-14..i-1 only; from session i it reads just
    the share-adjustment ratio all_v/raw_v (D8). reason is "" when every window is complete."""
    if i < WINDOW + 1:
        return None, None, None, 1.0, "history"
    prev = sessions[i - WINDOW - 1: i]
    pd = [daily.get(p) for p in prev]
    today = daily.get(sessions[i])
    if any(x is None for x in pd):
        return None, None, None, 1.0, "daily_gap"
    if today is None or not today[2] or not today[7] or not pd[-1][2] or not pd[-1][7]:
        return None, None, None, 1.0, "daily_today_missing"
    split = split_between(pd[-1][7] / pd[-1][2], today[7] / today[2])
    atr = atr14([(x[4], x[5], x[6], x[1]) for x in pd], split)
    avgv = avg_volume14([(x[7], x[2]) for x in pd[1:]], split)
    prior_or = []
    for p, x in zip(prev[1:], pd[1:]):
        po = orr.get(p)
        # regular-hours bars but none in 09:30-09:34: OR volume 0; no bar at all: a corpus gap voids the window
        prior_or.append((po[4] if po is not None and po[6] > 0 else None, x[7], x[2]))
    rv = relative_volume(or_volume_t, prior_or, split)
    if atr is None or avgv is None:
        return atr, avgv, rv, split, "window_invalid"
    if rv is None:
        return atr, avgv, rv, split, "relvol_window_invalid"
    return atr, avgv, rv, split, ""


def eligible(open_price, avg_vol, atr) -> bool:
    """Paper filters 1-3 (Section 2.1): open > $5, 14-day average volume >= 1M, 14-day ATR > $0.50."""
    return (open_price is not None and avg_vol is not None and atr is not None
            and open_price > MIN_OPEN and avg_vol >= MIN_AVG_VOLUME and atr > MIN_ATR)


def select_top(candidates, n: int = TOP_N, min_relvol: float = MIN_RELVOL):
    """Filters 4-5: relative volume >= 1, then the n highest; ties break by symbol (ascending).

    candidates: iterable of (symbol, relvol) for one session, already passing filters 1-3.
    Doji names are ranked like any other and keep their slot (they place no order)."""
    kept = [(s, rv) for s, rv in candidates if rv is not None and rv >= min_relvol]
    kept.sort(key=lambda x: (-x[1], x[0]))
    return kept[:n]


# ---------------------------------------------------------------- entry, stop and exit (one symbol-day)

def find_trigger(bars, dirn: int, level: float, close_minute: int):
    """Index of the first bar at or after 09:35 and before the close that trades through the stop level.

    Long: bar high >= level. Short: bar low <= level. None when the order never triggers."""
    if dirn == 0:
        return None
    for i, b in enumerate(bars):
        m = b[0]
        if m < ENTRY_FROM:
            continue
        if m >= close_minute:
            break
        if (dirn > 0 and b[2] >= level) or (dirn < 0 and b[3] <= level):
            return i
    return None


def entry_base(model: str, dirn: int, level: float, bar_open: float) -> float:
    """Execution price before spread/slippage. F0 fills at the trigger; F1/F2 at the bar open when the
    bar opens beyond the trigger (gap-through), else at the trigger."""
    if model == "F0":
        return level
    if dirn > 0 and bar_open > level:
        return bar_open
    if dirn < 0 and bar_open < level:
        return bar_open
    return level


def adverse(model: str, side: int, base: float, half_spread: float) -> float:
    """Fill after costs for one execution. side +1 buys (pays up), -1 sells (receives less).

    F0: no spread. F1: the measured half-spread (fraction of price). F2: F1 plus one tick."""
    if model == "F0":
        return base
    px = base * (1.0 + side * half_spread)
    if model == "F2":
        px += side * TICK
    return px


def stop_price(dirn: int, fill: float, atr: float) -> float:
    """Stop level 10% of ATR from the executed entry price."""
    return fill - dirn * STOP_ATR_FRACTION * atr


def simulate_trade(bars, dirn: int, level: float, atr: float, close_minute: int, model: str, half_spread):
    """One symbol-day under fill model F0/F1/F2. Returns None when the order never triggers, else a dict.

    half_spread(minute, price) -> fraction for an execution in that bar at that base price (ignored by F0).
    Same-bar ambiguity: if the entry bar also reaches the stop, the trade is stopped in that bar (against
    the trade), at the stop without gap (the bar traded through the trigger before the stop).
    Later bars: long stops when low <= stop, at min(stop, open) (gap-through fills at the open); short
    symmetrically. Otherwise exit at the close of the last bar before the session close (16:00, or 13:00
    on early closes)."""
    i = find_trigger(bars, dirn, level, close_minute)
    if i is None:
        return None
    eb = bars[i]
    base_in = entry_base(model, dirn, level, eb[1])
    fill_in = adverse(model, dirn, base_in, half_spread(eb[0], base_in) if model != "F0" else 0.0)
    stop = stop_price(dirn, fill_in, atr)
    out = {"entry_minute": eb[0], "entry_base": base_in, "entry_fill": fill_in, "stop": stop,
           "gap_entry": base_in != level}
    if (dirn > 0 and eb[3] <= stop) or (dirn < 0 and eb[2] >= stop):
        base_out, m_out, reason = stop, eb[0], "stop_same_bar"
    else:
        base_out = m_out = reason = None
        last = None
        for b in bars[i + 1:]:
            if b[0] >= close_minute:
                break
            last = b
            if dirn > 0 and b[3] <= stop:
                base_out, m_out, reason = min(stop, b[1]) if model != "F0" else stop, b[0], "stop"
                break
            if dirn < 0 and b[2] >= stop:
                base_out, m_out, reason = max(stop, b[1]) if model != "F0" else stop, b[0], "stop"
                break
        if reason is None:
            last = last or eb
            base_out, m_out, reason = last[4], last[0], "eod"
    fill_out = adverse(model, -dirn, base_out, half_spread(m_out, base_out) if model != "F0" else 0.0)
    out.update({"exit_minute": m_out, "exit_base": base_out, "exit_fill": fill_out, "exit_reason": reason})
    return out


# ---------------------------------------------------------------- costs, R and sizing

def fee_row(rows, day: str, key_from="from", key_to="to"):
    for r in rows:
        if r[key_from] <= day and (r[key_to] is None or day <= r[key_to]):
            return r
    raise KeyError(f"no fee row for {day}")


def sell_fees(fees: dict, day: str, shares: float, value: float) -> float:
    """SEC Section 31 (USD per million of sales) plus FINRA TAF (per share, capped per trade) on one sale.

    Both charged on the trade date here (the SEC rate's settlement-date basis is a documented deviation)."""
    sec = fee_row(fees["sec_section31"]["rows"], day)["usd_per_million"]
    taf = fee_row(fees["finra_taf_covered_equity"]["rows"], day)
    return sec * value / 1e6 + min(taf["usd_per_share"] * shares, taf["max_usd_per_trade"])


F0_COMMISSION_PER_SHARE = 0.0035  # the paper's IBKR Pro Tiered entry-level rate, both sides, no minimum


def trade_costs(model: str, fees: dict, day: str, dirn: int, shares: float, entry_fill: float,
                exit_fill: float) -> float:
    """Explicit USD costs of one round trip (spread and slippage are already in the fills).

    F0: commission on both sides only (the paper's cost model). F1/F2: zero commission; SEC fee and FINRA
    TAF on the sale (the exit of a long, the entry of a short)."""
    if model == "F0":
        return 2 * F0_COMMISSION_PER_SHARE * shares
    sell_px = exit_fill if dirn > 0 else entry_fill
    return sell_fees(fees, day, shares, shares * sell_px)


def net_pnl(dirn: int, shares: float, entry_fill: float, exit_fill: float, costs: float) -> float:
    return dirn * shares * (exit_fill - entry_fill) - costs


def r_per_share(atr: float) -> float:
    return STOP_ATR_FRACTION * atr


def net_r(model: str, fees: dict, day: str, dirn: int, entry_fill: float, exit_fill: float, atr: float,
          shares: float = 1.0) -> float:
    """Per-trade net R: net P&L per share over the paper's R (10% of ATR). Fees at the given share count."""
    c = trade_costs(model, fees, day, dirn, shares, entry_fill, exit_fill)
    return net_pnl(dirn, shares, entry_fill, exit_fill, c) / shares / r_per_share(atr)


def paper_shares(equity: float, entry_price: float, atr: float, slots: int = TOP_N, risk: float = 0.01,
                 leverage: float = 4.0) -> float:
    """Deviation D4 (conservative reading of the paper's sizing): each of the `slots` positions is
    allocated equity/slots; a stop-out loses `risk` of that allocation; notional is capped at `leverage`
    times that allocation (so the book never exceeds `leverage` x equity). Fractional shares."""
    alloc = equity / slots
    return min(risk * alloc / r_per_share(atr), leverage * alloc / entry_price)


def unlevered_shares(equity: float, entry_price: float, slots: int = TOP_N) -> float:
    """The 1x book: equity/slots of notional per position."""
    return equity / slots / entry_price
