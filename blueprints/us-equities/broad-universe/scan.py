#!/usr/bin/env python3
"""Dated broad-market scan / watchlist.

Read-only, allow-listed GETs against the paper trading host (reference data
only: clock, calendar, assets) and the market-data host (SIP snapshots,
provider screeners, news). Session state comes from the provider clock plus
calendar, never the local clock alone. Eligibility and the five protocol
signal flags (see ``protocol.json``) are computed from PRIOR sessions in the
materialized ``daily.parquet`` history plus today's snapshot bar; without
``--history`` eligibility is reported unknown rather than guessed.

Credentials are read the same way as the collector
(``collect_daily.read_credentials``); news collection is bounded and
implemented here rather than reusing ``market_research.collect`` because that
helper hard-bounds itself to 3 total requests and 30 symbols (a shadow
watchlist contract), which cannot cover a universe-wide scan's snapshot
batching plus screener and news requests.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("broad_universe_collect_daily", _HERE / "collect_daily.py")
collect_daily = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect_daily)

TRADING_HOST = "https://paper-api.alpaca.markets"
DATA_HOST = "https://data.alpaca.markets"
NY = ZoneInfo("America/New_York")

ALLOWED_GETS = {
    (TRADING_HOST, "/v2/clock"),
    (TRADING_HOST, "/v2/calendar"),
    (TRADING_HOST, "/v2/assets"),
    (DATA_HOST, "/v2/stocks/snapshots"),
    (DATA_HOST, "/v1beta1/screener/stocks/movers"),
    (DATA_HOST, "/v1beta1/screener/stocks/most-actives"),
    (DATA_HOST, "/v1beta1/news"),
}
MAX_URL_BYTES = 4000
STALE_QUOTE_SECONDS = 60
NEWS_LOOKBACK_HOURS = 24
NEWS_MAX_PAGES = 3
NEWS_PAGE_LIMIT = 50
NEWS_TOP_ABS_MOVERS = 20
TOP_N = 50
MAX_RETRIES = 3
FUND_NAME_RE = re.compile(r"(ETF|ETN|Fund|Trust|Shares|ProShares|Direxion|iShares|SPDR|Index|Portfolio)", re.IGNORECASE)
EXCLUSION_SUFFIX_RE = re.compile(r"\.(WS|W|U|R|RT)$")
# Mirrors evaluate.py's AMBIGUOUS_TAIL: five-letter tickers with no dotted suffix ending in
# W/R/U are flagged (not excluded) per protocol.json eligibility.symbol_exclusion_pattern.
AMBIGUOUS_TAIL = ("W", "R", "U")
ELIGIBILITY_LOOKBACK_BARS = 60
S4_LOOKBACK_BARS = 130
RANGE10_BARS = 10
RANGE10_P20_OBS = 120
POSSIBLE_CORPORATE_ACTION_THRESHOLD = 0.40


class ScanError(RuntimeError):
    """Only bounded reason codes ever leave this module."""


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    if isinstance(value, str):
        value = parse_iso(value)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def to_number(value):
    """JSON-safe conversion for Decimal/None values encountered while assembling output."""
    if isinstance(value, Decimal):
        return float(value)
    return value


class Session:
    """Allow-listed, GET-only, request-capped HTTP boundary for the scan."""

    def __init__(self, key, secret, request_cap=2000, clock=utc_now):
        import requests
        self._session = requests.Session()
        self._session.trust_env = False
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.request_cap = request_cap
        self.log = []
        self._clock = clock

    def get(self, host, path, params=None):
        import requests
        if (host, path) not in ALLOWED_GETS:
            raise ScanError(f"path_not_allowlisted:{path}")
        prepared = requests.PreparedRequest()
        prepared.prepare_url(host + path, params or {})
        if len(prepared.url.encode("utf-8")) >= MAX_URL_BYTES:
            raise ScanError("url_too_large")
        delay = 0.05
        for attempt in range(1, MAX_RETRIES + 1):
            # Checked before every attempt (including retries), not only once before the loop,
            # so a request that starts within budget cannot spend extra retry attempts past it.
            if len(self.log) >= self.request_cap:
                raise ScanError("request_cap_exceeded")
            response = self._session.request("GET", host + path, params=params, headers=self._headers,
                                               timeout=(5, 20), allow_redirects=False)
            entry = {"path": path, "attempt": attempt, "status": response.status_code,
                     "observed_at": iso(self._clock()),
                     "rate_headers": {k.lower(): v for k, v in response.headers.items()
                                      if k.lower().startswith("x-ratelimit")}}
            self.log.append(entry)
            if 300 <= response.status_code < 400:
                raise ScanError("redirect_rejected")
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_RETRIES:
                    raise ScanError(f"http_{response.status_code}_after_retries")
                time.sleep(delay)
                delay *= 2
                continue
            raise ScanError(f"http_{response.status_code}")
        raise ScanError("unreachable")

    def close(self):
        self._session.close()


# --------------------------------------------------------------------------- session determination


def fetch_clock(session):
    return session.get(TRADING_HOST, "/v2/clock")


def fetch_calendar(session, start_date, end_date):
    return session.get(TRADING_HOST, "/v2/calendar", params={"start": start_date, "end": end_date})


def _localize(date_str, hhmm):
    year, month, day = (int(part) for part in date_str.split("-"))
    hour, minute = (int(part) for part in hhmm.split(":"))
    return datetime(year, month, day, hour, minute, tzinfo=NY)


def determine_session(now_utc, clock, calendar_days):
    """Session state from the provider clock and calendar plus the run timestamp.

    Never falls back to comparing the local clock against hardcoded market hours.
    """
    sessions = sorted(
        ({"date": day["date"], "open": _localize(day["date"], day["open"]),
          "close": _localize(day["date"], day["close"])} for day in calendar_days),
        key=lambda s: s["date"])

    is_open = bool(clock.get("is_open"))
    next_open = clock.get("next_open")
    next_close = clock.get("next_close")

    now_ny_date = now_utc.astimezone(NY).date().isoformat()
    today_session = next((s for s in sessions if s["date"] == now_ny_date), None)
    completed = sorted((s for s in sessions if s["close"] <= now_utc), key=lambda s: s["date"])

    if is_open:
        session_state = "regular_open"
        current_or_last = today_session["date"] if today_session else now_ny_date
    elif today_session is not None and now_utc < today_session["open"]:
        session_state = "pre_market"
        current_or_last = completed[-1]["date"] if completed else None
    elif today_session is not None and now_utc >= today_session["close"]:
        session_state = "after_hours"
        current_or_last = today_session["date"]
    else:
        session_state = "closed"
        current_or_last = completed[-1]["date"] if completed else None

    idx = next((i for i, s in enumerate(sessions) if s["date"] == current_or_last), None)
    previous = sessions[idx - 1]["date"] if idx is not None and idx > 0 else None

    return {
        "run_time_utc": iso(now_utc),
        "run_time_et": now_utc.astimezone(NY).isoformat(),
        "session_state": session_state,
        "is_open_per_clock": is_open,
        "current_or_last_regular_session": current_or_last,
        "previous_regular_session": previous,
        "next_open": iso(parse_iso(next_open)) if next_open else None,
        "next_close": iso(parse_iso(next_close)) if next_close else None,
    }


# --------------------------------------------------------------------------- universe


def fetch_active_tradable_assets(session):
    return session.get(TRADING_HOST, "/v2/assets", params={"status": "active", "asset_class": "us_equity"})


def build_universe(assets):
    universe = []
    skipped = {}
    for asset in assets:
        if asset.get("class") != "us_equity" or asset.get("status") != "active" or not asset.get("tradable"):
            skipped["not_active_tradable"] = skipped.get("not_active_tradable", 0) + 1
            continue
        if asset.get("exchange") == "OTC":
            skipped["OTC"] = skipped.get("OTC", 0) + 1
            continue
        symbol = asset.get("symbol") or ""
        if not collect_daily.DATA_SYMBOL.match(symbol):
            skipped["placeholder_symbol"] = skipped.get("placeholder_symbol", 0) + 1
            continue
        universe.append(asset)
    universe.sort(key=lambda a: a["symbol"])
    return universe, skipped


def batch_symbols_for_url(symbols, host, path, params_extra, max_url_bytes=MAX_URL_BYTES):
    import requests
    batches, current = [], []
    for symbol in symbols:
        trial = current + [symbol]
        prepared = requests.PreparedRequest()
        params = dict(params_extra)
        params["symbols"] = ",".join(trial)
        prepared.prepare_url(host + path, params)
        if len(prepared.url.encode("utf-8")) >= max_url_bytes:
            if not current:
                raise ScanError("single_symbol_exceeds_url_budget")
            batches.append(current)
            current = [symbol]
        else:
            current = trial
    if current:
        batches.append(current)
    return batches


def fetch_snapshots(session, symbols, clock=utc_now):
    """Fetch snapshots batch by batch, stamping each batch with its OWN fetch-time clock() call.

    Returns (snapshots, missing, observed_at) where observed_at maps every requested symbol to
    the timestamp its batch was actually fetched at, so age arithmetic against a symbol's quote
    never uses a run-start timestamp captured before that batch's request was made.
    """
    snapshots, missing, observed_at = {}, set(symbols), {}
    for group in batch_symbols_for_url(symbols, DATA_HOST, "/v2/stocks/snapshots", {"feed": "sip"}):
        payload = session.get(DATA_HOST, "/v2/stocks/snapshots", params={"symbols": ",".join(group), "feed": "sip"})
        batch_observed_at = clock()
        # The multi-symbol snapshot endpoint returns a flat {symbol: snapshot} map (no wrapper key),
        # unlike the single-symbol endpoint. Support a "snapshots" wrapper too in case of a future change.
        data = payload.get("snapshots", payload) if isinstance(payload, dict) else {}
        for symbol in group:
            observed_at[symbol] = batch_observed_at
            snap = data.get(symbol)
            if snap:
                snapshots[symbol] = snap
                missing.discard(symbol)
    return snapshots, missing, observed_at


# --------------------------------------------------------------------------- per-symbol observation


def classify_observation(symbol, snapshot, current_or_last_session, previous_session, session_state, observed_at):
    result = {"symbol": symbol, "observed_at": iso(observed_at),
              "daily_bar_revision_note": "daily_bar_may_still_be_revised_by_late_prints_after_close"}
    if not snapshot:
        result["observation_class"] = "missing"
        return result

    daily = snapshot.get("dailyBar") or {}
    prev_daily = snapshot.get("prevDailyBar") or {}
    quote = snapshot.get("latestQuote") or {}
    trade = snapshot.get("latestTrade") or {}

    daily_date = (daily.get("t") or "")[:10] or None
    result["daily_bar_t"] = daily.get("t")
    result["daily_bar_date"] = daily_date
    if daily_date == current_or_last_session:
        result["observation_class"] = "today_session"
    elif daily_date and daily_date == previous_session:
        result["observation_class"] = "previous_session"
    elif daily_date:
        result["observation_class"] = "stale_bar"
    else:
        result["observation_class"] = "missing"

    quote_t = quote.get("t")
    bid, ask = quote.get("bp"), quote.get("ap")
    if quote_t is not None:
        try:
            quote_at = parse_iso(quote_t)
            age = (observed_at - quote_at).total_seconds()
            result.update(quote_at=iso(quote_at), quote_age_seconds=age)
            if bid is not None and ask is not None:
                result["quote_invalid"] = bool(bid <= 0 or ask < bid)
            if age < 0:
                # The batch-fetch clock ran before the quote timestamp: the two clocks disagree
                # (provider skew, or clock() called ahead of the quote's own timestamp source).
                # Never silently treat this as "fresh" - flag it and leave staleness unknown.
                result["clock_skew"] = True
                result["stale_quote"] = None
            elif session_state == "regular_open":
                result["stale_quote"] = age > STALE_QUOTE_SECONDS
            else:
                result["stale_quote"] = False
                result["quote_age_note"] = "age_reported_not_flagged_stale_outside_regular_hours"
        except (ValueError, TypeError):
            result["quote_parse_error"] = True

    trade_t = trade.get("t")
    if trade_t is not None:
        try:
            trade_at = parse_iso(trade_t)
            trade_age = (observed_at - trade_at).total_seconds()
            result.update(trade_at=iso(trade_at), trade_age_seconds=trade_age)
            if trade_age < 0:
                result["trade_clock_skew"] = True
        except (ValueError, TypeError):
            result["trade_parse_error"] = True

    close, prev_close = daily.get("c"), prev_daily.get("c")
    prev_date = (prev_daily.get("t") or "")[:10] or None
    result["prev_daily_bar_date"] = prev_date
    if prev_date == previous_session and close is not None and prev_close:
        try:
            result["pct_change"] = float((Decimal(str(close)) / Decimal(str(prev_close)) - 1) * 100)
        except (InvalidOperation, ZeroDivisionError):
            result["prev_bar_mismatch"] = True
    else:
        result["prev_bar_mismatch"] = True

    result.update(raw_open=daily.get("o"), raw_high=daily.get("h"), raw_low=daily.get("l"),
                  raw_close=close, raw_volume=daily.get("v"))
    if close is not None and daily.get("v") is not None:
        result["dollar_volume"] = close * daily["v"]
    return result


# --------------------------------------------------------------------------- history-based eligibility and signals


def compute_history_features(path, previous_regular_session):
    """Per-symbol features as of the symbol's own last history row (t-1, feeding today's t decision).

    Mirrors evaluate.py's frozen contiguity rules so scan and evaluator signal definitions cannot
    diverge: a session calendar is built from SPY's own raw bars in the SAME history file (as
    evaluate.py's build_calendar does), and every window feature is gated on calendar-index
    contiguity (span60/span130) and, for range10_p20, on having exactly RANGE10_P20_OBS complete
    range10 observations - never on however many rows happen to exist.
    """
    import duckdb
    import pandas as pd
    con = duckdb.connect()
    try:
        global_last = con.execute("SELECT MAX(session_date) FROM read_parquet(?)", [path]).fetchone()[0]
        global_last_str = global_last.isoformat() if global_last is not None else None
        status = {"history_used": True, "history_path": os.path.basename(path),
                  "history_last_session": global_last_str,
                  "previous_regular_session": previous_regular_session,
                  "history_not_adjacent": global_last_str != previous_regular_session}
        if status["history_not_adjacent"] or global_last_str is None:
            return {}, status
        query = f"""
        WITH calendar AS (
            SELECT session_date, (row_number() OVER (ORDER BY session_date) - 1)::BIGINT AS cal_idx
            FROM (SELECT DISTINCT session_date FROM read_parquet(?) WHERE symbol = 'SPY' AND in_raw)
        ),
        base AS (
            -- SPY itself is NOT excluded here (evaluate.py's bars table does not exclude it either):
            -- it is used to build the calendar above AND still gets its own features/eligibility
            -- computed like any other symbol, so scan and evaluator never diverge on this point.
            SELECT b.symbol, b.session_date, c.cal_idx, b.raw_c, b.raw_v,
                   b.all_o, b.all_h, b.all_l, b.all_c, b.raw_c * b.raw_v AS dv
            FROM read_parquet(?) b
            JOIN calendar c USING (session_date)
            WHERE b.raw_c IS NOT NULL AND b.all_c IS NOT NULL
              AND b.all_h IS NOT NULL AND b.all_l IS NOT NULL AND b.all_o IS NOT NULL
        ),
        windowed AS (
            SELECT *,
                CASE WHEN COUNT(*) OVER w10 = {RANGE10_BARS}
                     THEN (MAX(all_h) OVER w10 - MIN(all_l) OVER w10) / NULLIF(all_c, 0) END AS range10_row,
                -- These rows are session t-1 (the last history bar); the scanned bar is t. The
                -- protocol window of k prior bars is therefore rows r-(k-1)..r, and it is
                -- contiguous when their calendar span plus one equals k. Lagging by k here
                -- would demand k+1 history bars and reject a symbol with exactly k.
                cal_idx - LAG(cal_idx, {ELIGIBILITY_LOOKBACK_BARS - 1}) OVER w + 1 AS span60,
                cal_idx - LAG(cal_idx, {S4_LOOKBACK_BARS - 1}) OVER w + 1 AS span130
            FROM base
            WINDOW w   AS (PARTITION BY symbol ORDER BY session_date),
                   w10 AS (PARTITION BY symbol ORDER BY session_date ROWS BETWEEN {RANGE10_BARS - 1} PRECEDING AND CURRENT ROW)
        ),
        finalized AS (
            SELECT *,
                COUNT(*) OVER (PARTITION BY symbol) AS prior_bars,
                MEDIAN(dv) OVER w20 AS med20,
                MAX(all_h) OVER w60 AS high60,
                MAX(all_h) OVER w20 AS high20,
                LAG(all_c, 4) OVER w AS prev5_close,
                CASE WHEN COUNT(range10_row) OVER wp = {RANGE10_P20_OBS}
                     THEN QUANTILE_CONT(range10_row, 0.2) OVER wp END AS range10_p20,
                MAX(session_date) OVER (PARTITION BY symbol) AS symbol_last_date
            FROM windowed
            WINDOW w   AS (PARTITION BY symbol ORDER BY session_date),
                   w20 AS (PARTITION BY symbol ORDER BY session_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
                   w60 AS (PARTITION BY symbol ORDER BY session_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW),
                   -- Protocol: range10 over u in [t-121, t-2]. Anchored at row r = t-1 that is
                   -- rows r-120..r-1, not the evaluator's t-anchored 121..2 PRECEDING frame.
                   wp  AS (PARTITION BY symbol ORDER BY session_date
                           ROWS BETWEEN {RANGE10_P20_OBS} PRECEDING AND 1 PRECEDING)
        )
        SELECT symbol, session_date, all_c AS prev_close, prior_bars, med20, high60, high20, prev5_close,
               range10_row, range10_p20, span60, span130
        FROM finalized
        WHERE session_date = symbol_last_date
        """
        df = con.execute(query, [path, path]).df()

        def num(value, cast):
            # DuckDB's nullable BIGINT (span60/span130, from a LAG that can be NULL) round-trips
            # through pandas as a pandas.NA scalar, not None or float('nan'); pd.isna() is the one
            # check that is correct for all three (None, NaN and pandas.NA).
            return None if pd.isna(value) else cast(value)

        features = {}
        for row in df.itertuples(index=False):
            features[row.symbol] = {
                "last_session_date": num(row.session_date, lambda v: v.date().isoformat()),
                "prior_bars": num(row.prior_bars, int),
                "med20": num(row.med20, float),
                "high60": num(row.high60, float),
                "high20": num(row.high20, float),
                "prev_close": num(row.prev_close, float),
                "prev5_close": num(row.prev5_close, float),
                "range10": num(row.range10_row, float),
                "range10_p20": num(row.range10_p20, float),
                "span60": num(row.span60, int),
                "span130": num(row.span130, int),
            }
        return features, status
    finally:
        con.close()


def compute_signals(obs_row, hist, dv_scanned):
    raw_close, raw_open = obs_row.get("raw_close"), obs_row.get("raw_open")
    raw_high, raw_low = obs_row.get("raw_high"), obs_row.get("raw_low")
    med20, high60, high20 = hist.get("med20"), hist.get("high60"), hist.get("high20")
    prev_close, prev5_close = hist.get("prev_close"), hist.get("prev5_close")
    range10, range10_p20 = hist.get("range10"), hist.get("range10_p20")
    # S4 additionally needs a fully contiguous 130-bar window (evaluate.py's has_gap_s4); the
    # 120-observation range10_p20 gate alone is not sufficient because a symbol can have exactly
    # 120 valid range10 observations spread across a non-contiguous (gapped) 130-session span.
    s4_history_ok = hist.get("span130") == S4_LOOKBACK_BARS

    clv = None
    if raw_high is not None and raw_low is not None and raw_close is not None:
        clv = 0.5 if raw_high == raw_low else (raw_close - raw_low) / (raw_high - raw_low)
    r1 = (raw_close / prev_close - 1) if raw_close is not None and prev_close else None
    r5 = (raw_close / prev5_close - 1) if raw_close is not None and prev5_close else None
    gap = (raw_open / prev_close - 1) if raw_open is not None and prev_close else None
    # obs_row["pct_change"] is a raw-to-raw same-feed ratio (in percentage points) independent of
    # the history file's adjustment basis; checking it alongside gap/r1 catches an adjustment-basis
    # mismatch (e.g. a split that post-dates the collected history) even when r1/gap themselves look
    # unremarkable because both their inputs were rebased by the same stale factor.
    pct_change = obs_row.get("pct_change")

    possible_corporate_action = bool(
        (gap is not None and abs(gap) >= POSSIBLE_CORPORATE_ACTION_THRESHOLD) or
        (r1 is not None and abs(r1) >= POSSIBLE_CORPORATE_ACTION_THRESHOLD) or
        (pct_change is not None and abs(pct_change) >= POSSIBLE_CORPORATE_ACTION_THRESHOLD * 100))

    flags = {}
    flags_null_reason = None
    if possible_corporate_action:
        # The snapshot's raw price and the history file's adjustment basis cannot be verified as
        # consistent (see the module docstring / protocol raw_vs_adjusted); every signal depends on
        # comparing today's raw/adjusted bar against history built on a possibly different basis, so
        # all five are withheld rather than publishing a signal derived from mismatched share units.
        flags_null_reason = "adjustment_basis_unverified"
    else:
        if None not in (raw_close, high60, dv_scanned, med20, clv):
            flags["S1_momentum_breakout"] = bool(raw_close > high60 and dv_scanned >= 2 * med20 and clv >= 0.75)
        if None not in (r1, dv_scanned, med20, clv):
            flags["S2_volume_shock_continuation"] = bool(r1 >= 0.05 and dv_scanned >= 3 * med20 and clv >= 0.5)
        if None not in (r5, raw_close, raw_open, dv_scanned, med20):
            flags["S3_oversold_reversal"] = bool(r5 <= -0.15 and raw_close > raw_open and dv_scanned >= med20)
        if s4_history_ok and None not in (range10, range10_p20, raw_close, high20):
            flags["S4_contraction_breakout"] = bool(range10 <= range10_p20 and raw_close > high20)
        if None not in (gap, raw_close, raw_open, dv_scanned, med20):
            flags["S5_gap_and_hold"] = bool(gap >= 0.04 and raw_close >= raw_open and dv_scanned >= 2 * med20)

    result = {"flags": {k: v for k, v in flags.items() if v}, "flags_evaluated": sorted(flags),
              "r1": r1, "r5": r5, "gap": gap, "clv": clv,
              "possible_corporate_action": possible_corporate_action,
              "research_flag_not_prediction": True}
    if flags_null_reason:
        result["flags_null_reason"] = flags_null_reason
    return result


def compute_eligibility(symbol, obs_row, asset, hist, history_status):
    # Mirrors evaluate.py's AMBIGUOUS_TAIL rule exactly: flagged, never excluded, and reported
    # regardless of any other eligibility outcome so scan and evaluator never silently disagree.
    ambiguous_suffix_flag = bool(len(symbol) == 5 and "." not in symbol and symbol[-1] in AMBIGUOUS_TAIL)
    result = {"symbol": symbol, "ambiguous_suffix_flag": ambiguous_suffix_flag}
    if not history_status.get("history_used"):
        return {**result, "eligible": None, "eligibility_status": "unknown_no_history"}
    if history_status.get("history_not_adjacent"):
        return {**result, "eligible": None, "eligibility_status": "unknown_history_not_adjacent"}
    if hist is None:
        return {**result, "eligible": False, "eligibility_status": "no_prior_history_for_symbol"}

    # Per-symbol freshness/contiguity gate (protocol execution_assumptions.window_contiguity):
    # a symbol's own last history row must BE the previous regular session (otherwise its series is
    # stale even though some other symbol - or the dataset max - is current), and its trailing 60
    # bars must be calendar-contiguous against the SPY calendar in the same history file. Either
    # failure makes eligibility/signals unusable: eligible is None (unknown), never False, because
    # "not eligible" and "cannot be evaluated" are different facts.
    previous_regular_session = history_status.get("previous_regular_session")
    if hist.get("last_session_date") != previous_regular_session:
        return {**result, "eligible": None, "eligibility_status": "history_stale",
                "prior_bars": hist.get("prior_bars")}
    if hist.get("span60") != ELIGIBILITY_LOOKBACK_BARS:
        return {**result, "eligible": None, "eligibility_status": "has_gap",
                "prior_bars": hist.get("prior_bars")}

    # protocol.json eligibility.bar_required_on_decision_session: a previous-session or older
    # snapshot bar cannot stand in for today's decision-session bar.
    observation_class = obs_row.get("observation_class")
    if observation_class != "today_session":
        return {**result, "eligible": False, "eligibility_status": "stale_snapshot_bar",
                "observation_class": observation_class}

    raw_close_scanned, daily_v = obs_row.get("raw_close"), obs_row.get("raw_volume")
    if raw_close_scanned is None or daily_v is None:
        return {**result, "eligible": False, "eligibility_status": "missing_scanned_bar"}

    dv_scanned = raw_close_scanned * daily_v
    prior_bars, med20 = hist.get("prior_bars"), hist.get("med20")
    name = (asset or {}).get("name") or ""
    fund_like = bool(FUND_NAME_RE.search(name))
    excluded_suffix = bool(EXCLUSION_SUFFIX_RE.search(symbol))
    meets_price = raw_close_scanned >= 5
    meets_liquidity = med20 is not None and med20 >= 20_000_000
    eligible_all_instruments = bool(meets_price and meets_liquidity and not excluded_suffix)
    eligible = eligible_all_instruments and not fund_like
    result.update(eligible=eligible, eligible_all_instruments=eligible_all_instruments,
                  eligibility_status="computed", instrument_lane_fund_like=fund_like,
                  exclusion_pattern_matched=excluded_suffix, raw_close_scanned=raw_close_scanned,
                  dollar_volume_scanned=dv_scanned, med20_dollar_volume=med20, prior_bars=prior_bars)
    if eligible:
        result["signals"] = compute_signals(obs_row, hist, dv_scanned)
    return result


# --------------------------------------------------------------------------- news (bounded, own contract)


def normalize_news_row(raw, observed_at, requested_symbols):
    headline = raw.get("headline") or ""
    symbols = [s for s in (raw.get("symbols") or []) if s in requested_symbols]
    article_id = raw.get("id")
    if not headline or not symbols or article_id is None:
        return None
    url = raw.get("url")
    # Provider news URLs commonly carry the headline as a slug (e.g. .../48372910/meta-jumps).
    # The full url is kept only in the private artifact; only its host and a hash of the whole
    # url are ever eligible for publication (see assemble_public).
    url_host = urlsplit(url).netloc if url else None
    url_sha256 = hashlib.sha256(url.encode("utf-8")).hexdigest() if url else None
    return {
        "article_id": str(article_id),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "observed_at": iso(observed_at),
        "symbols": symbols,
        "source": raw.get("source"),
        "url": url,
        "url_host": url_host,
        "url_sha256": url_sha256,
        "headline_sha256": hashlib.sha256(headline.encode("utf-8")).hexdigest(),
    }


def fetch_news(session, symbols, as_of, observed_now):
    """At most NEWS_MAX_PAGES bounded GETs against /v1beta1/news for an explicit symbol set."""
    if not symbols:
        return [], False
    since = as_of - timedelta(hours=NEWS_LOOKBACK_HOURS)
    articles, token, capped = {}, None, False
    for page in range(NEWS_MAX_PAGES):
        params = {"symbols": ",".join(sorted(symbols)), "start": iso(since), "end": iso(as_of),
                  "limit": NEWS_PAGE_LIMIT, "sort": "desc", "include_content": "false",
                  "exclude_contentless": "true"}
        if token:
            params["page_token"] = token
        payload = session.get(DATA_HOST, "/v1beta1/news", params=params)
        observed_at = observed_now()
        for raw in payload.get("news", []) or []:
            normalized = normalize_news_row(raw, observed_at, symbols)
            if normalized:
                articles[normalized["article_id"]] = normalized
        token = payload.get("next_page_token")
        if not token:
            break
    else:
        capped = bool(token)
    return list(articles.values()), capped


# --------------------------------------------------------------------------- provider screens


def fetch_provider_screens(session):
    movers = session.get(DATA_HOST, "/v1beta1/screener/stocks/movers")
    actives = session.get(DATA_HOST, "/v1beta1/screener/stocks/most-actives")
    label = "bounded_top_n_provider_screen_includes_sub_5_names_not_market_coverage"
    public = {
        "movers": {"label": label,
                   "gainers_symbols": [row.get("symbol") for row in movers.get("gainers", []) if row.get("symbol")],
                   "losers_symbols": [row.get("symbol") for row in movers.get("losers", []) if row.get("symbol")]},
        "most_actives": {"label": label,
                          "symbols": [row.get("symbol") for row in actives.get("most_actives", []) if row.get("symbol")]},
    }
    return {"movers": movers, "most_actives": actives}, public


# --------------------------------------------------------------------------- lists


def build_lists(rows, eligibility, pinned):
    eligible_symbols = [s for s, e in eligibility.items() if e.get("eligible")]

    def pct(symbol):
        return rows.get(symbol, {}).get("pct_change")

    def dv(symbol):
        return rows.get(symbol, {}).get("dollar_volume")

    valid_pct = [s for s in eligible_symbols if pct(s) is not None]
    gainers = sorted(valid_pct, key=lambda s: -pct(s))
    losers = sorted(valid_pct, key=lambda s: pct(s))
    valid_dv = [s for s in eligible_symbols if dv(s) is not None]
    by_dv = sorted(valid_dv, key=lambda s: -dv(s))
    signal_flagged = sorted(s for s in eligible_symbols if (eligibility[s].get("signals") or {}).get("flags"))

    gainer_rank = {s: i + 1 for i, s in enumerate(gainers)}
    dv_rank = {s: i + 1 for i, s in enumerate(by_dv)}

    pinned_info = {}
    for symbol in pinned:
        pinned_info[symbol] = {
            "symbol": symbol,
            "present_in_universe": symbol in rows,
            "observation_class": rows.get(symbol, {}).get("observation_class", "missing"),
            "eligible": eligibility.get(symbol, {}).get("eligible"),
            "pct_change_rank_among_eligible": gainer_rank.get(symbol),
            "dollar_volume_rank_among_eligible": dv_rank.get(symbol),
        }

    abs_candidates = valid_pct if valid_pct else [s for s, r in rows.items() if r.get("pct_change") is not None]
    news_candidates = sorted(abs_candidates, key=lambda s: -abs(rows[s]["pct_change"]))[:NEWS_TOP_ABS_MOVERS]

    return {
        "eligible_count": len(eligible_symbols),
        "top_gainers": gainers[:TOP_N], "top_losers": losers[:TOP_N], "top_dollar_volume": by_dv[:TOP_N],
        "signal_flagged": signal_flagged, "pinned": pinned_info, "news_candidates": news_candidates,
        "gainer_rank": gainer_rank, "dv_rank": dv_rank,
    }


# --------------------------------------------------------------------------- output assembly


def round_pct(value):
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN))


def dollar_volume_bucket(value):
    if value is None:
        return None
    if value >= 1_000_000_000:
        return ">=1B"
    if value >= 100_000_000:
        return ">=100M"
    if value >= 20_000_000:
        return ">=20M"
    return "<20M"


def public_symbol_row(symbol, rows, eligibility, lists):
    row, elig = rows.get(symbol, {}), eligibility.get(symbol, {})
    membership = []
    if symbol in lists["top_gainers"]:
        membership.append("top_50_gainers")
    if symbol in lists["top_losers"]:
        membership.append("top_50_losers")
    if symbol in lists["top_dollar_volume"]:
        membership.append("top_50_dollar_volume")
    if symbol in lists["signal_flagged"]:
        membership.append("signal_flagged")
    if symbol in lists["pinned"]:
        membership.append("pinned")
    signals = elig.get("signals") or {}
    signal_flags = sorted(signals.get("flags", {}))
    return {
        "symbol": symbol, "list_membership": membership,
        "pct_change_rank_among_eligible": lists["gainer_rank"].get(symbol),
        "dollar_volume_rank_among_eligible": lists["dv_rank"].get(symbol),
        "percent_change": round_pct(row.get("pct_change")),
        "dollar_volume_bucket": dollar_volume_bucket(row.get("dollar_volume")),
        "signal_flags": signal_flags, "research_flag_not_prediction": True,
        "possible_corporate_action": signals.get("possible_corporate_action"),
        "ambiguous_suffix_flag": elig.get("ambiguous_suffix_flag"),
        "observation_class": row.get("observation_class"),
        "observed_at": row.get("observed_at"), "daily_bar_t": row.get("daily_bar_t"),
        "stale_quote": row.get("stale_quote"), "prev_bar_mismatch": row.get("prev_bar_mismatch", False),
    }


def assemble_public(session_info, lists, rows, eligibility, counts, history_status, news_items,
                     news_capped, screens_public, request_meta):
    symbols_to_publish = sorted(set(lists["top_gainers"]) | set(lists["top_losers"])
                                 | set(lists["top_dollar_volume"]) | set(lists["signal_flagged"])
                                 | set(lists["pinned"]))
    return {
        "schema_version": 1,
        "run": {"run_time_utc": session_info["run_time_utc"], "run_time_et": session_info["run_time_et"],
                "session_state": session_info["session_state"],
                "current_or_last_regular_session": session_info["current_or_last_regular_session"],
                "previous_regular_session": session_info["previous_regular_session"],
                "next_open": session_info["next_open"], "next_close": session_info["next_close"]},
        "history": history_status, "counts": counts,
        "limitations": [
            "Signal flags are research_flag_not_prediction, never a prediction of return.",
            "Provider screens are bounded_top_n_provider_screen_includes_sub_5_names_not_market_coverage.",
            "Daily bars may still be revised by late prints after the close.",
            "This artifact carries no quotes, prices, headline text or full news URLs"
            " (only url host and a sha256 of the full url); see the private artifact for full rows.",
        ],
        "pinned": lists["pinned"],
        "lists": {"top_50_gainers": lists["top_gainers"], "top_50_losers": lists["top_losers"],
                  "top_50_dollar_volume": lists["top_dollar_volume"], "signal_flagged": lists["signal_flagged"]},
        "symbols": [public_symbol_row(s, rows, eligibility, lists) for s in symbols_to_publish],
        "provider_screens": screens_public,
        "news": [{"symbols": n["symbols"], "created_at": n["created_at"], "updated_at": n["updated_at"],
                  "observed_at": n["observed_at"], "source": n["source"],
                  "url_host": n.get("url_host"), "url_sha256": n.get("url_sha256"),
                  "headline_sha256": n["headline_sha256"]} for n in news_items],
        "news_window_status": "capped_more_available" if news_capped else "returned_provider_window",
        "requests": request_meta,
    }


def assemble_private(session_info, lists, rows, eligibility, counts, history_status, screens_raw,
                      news_items, news_capped, request_log, universe_skipped, pinned):
    return {
        "schema_version": 1, "session": session_info, "history": history_status, "counts": counts,
        "universe_excluded": universe_skipped, "pinned_symbols": pinned,
        "lists": {k: v for k, v in lists.items() if k not in ("gainer_rank", "dv_rank")},
        "rows": rows, "eligibility": eligibility, "provider_screens_raw": screens_raw,
        "news": news_items, "news_window_status": "capped_more_available" if news_capped else "returned_provider_window",
        "requests": request_log,
    }


def build_counts(symbols, rows, eligibility, lists, history_status):
    """History is only usable at all when it was supplied AND the dataset-level freshness check
    passed; a null (not zero) counts.eligible then distinguishes "not computed" from "computed and
    nothing qualified". Per-symbol has_gap/history_stale/unknown_* outcomes are folded into
    eligibility_unknown so the reconciliation (scanned = eligible + ineligible + unknown) holds.
    """
    history_used_effectively = bool(history_status.get("history_used")) and not history_status.get("history_not_adjacent")
    eligibility_unknown = sum(1 for e in eligibility.values() if e.get("eligible") is None)
    return {
        "scanned": len(symbols),
        "eligible": lists["eligible_count"] if history_used_effectively else None,
        "eligibility_unknown": eligibility_unknown,
        "missing": sum(1 for r in rows.values() if r["observation_class"] == "missing"),
        "previous_session": sum(1 for r in rows.values() if r["observation_class"] == "previous_session"),
        "stale_bar": sum(1 for r in rows.values() if r["observation_class"] == "stale_bar"),
        "today_session": sum(1 for r in rows.values() if r["observation_class"] == "today_session"),
    }


def write_json_file(path, data, mode):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, default=to_number)
        handle.write("\n")


# --------------------------------------------------------------------------- run


def run(args, clock=None):
    clock = clock or utc_now
    now = parse_iso(args.now) if args.now else clock()
    key, secret = collect_daily.read_credentials(args.env_file)
    session = Session(key, secret, clock=clock)
    private_dir = os.path.dirname(os.path.abspath(args.out_private))
    # Create the private output directory BEFORE the ledger is opened: Ledger.write() appends via
    # plain open(path, "a"), which raises FileNotFoundError on a fresh destination directory, and
    # that happens before any output helper (write_json_file creates its own directory, but too late).
    os.makedirs(private_dir, exist_ok=True)
    ledger = collect_daily.Ledger(os.path.join(private_dir, "scan-ledger.jsonl"))
    try:
        clock_payload = fetch_clock(session)
        cal_start = (now - timedelta(days=10)).date().isoformat()
        cal_end = (now + timedelta(days=10)).date().isoformat()
        calendar_days = fetch_calendar(session, cal_start, cal_end)
        session_info = determine_session(now, clock_payload, calendar_days)
        ledger.write(event="session_determined", **session_info)

        assets = fetch_active_tradable_assets(session)
        write_json_file(args.assets_out, assets, 0o600)
        universe, skipped = build_universe(assets)
        asset_by_symbol = {a["symbol"]: a for a in universe}
        symbols = [a["symbol"] for a in universe]
        ledger.write(event="universe_built", total_assets=len(assets), universe=len(universe), skipped=skipped)

        snapshots, missing, snapshot_observed_at = fetch_snapshots(session, symbols, clock)
        ledger.write(event="snapshots_fetched", requested=len(symbols), returned=len(snapshots), missing=len(missing))

        rows = {symbol: classify_observation(symbol, snapshots.get(symbol),
                                              session_info["current_or_last_regular_session"],
                                              session_info["previous_regular_session"],
                                              session_info["session_state"],
                                              snapshot_observed_at.get(symbol, now))
                for symbol in symbols}

        if args.history:
            hist_features, history_status = compute_history_features(args.history,
                                                                       session_info["previous_regular_session"])
        else:
            hist_features, history_status = {}, {"history_used": False}

        eligibility = {symbol: compute_eligibility(symbol, rows[symbol], asset_by_symbol.get(symbol),
                                                    hist_features.get(symbol), history_status)
                       for symbol in symbols}

        screens_raw, screens_public = fetch_provider_screens(session)

        pinned = sorted({p.strip().upper() for p in args.pinned.split(",") if p.strip()})
        lists = build_lists(rows, eligibility, pinned)

        news_symbols = sorted(set(pinned) | set(lists["news_candidates"]))
        news_items, news_capped = fetch_news(session, news_symbols, now, clock)

        counts = build_counts(symbols, rows, eligibility, lists, history_status)
        request_meta = {"total_requests": len(session.log), "request_cap": session.request_cap,
                         "rate_headers_last": session.log[-1]["rate_headers"] if session.log else {}}

        public = assemble_public(session_info, lists, rows, eligibility, counts, history_status,
                                  news_items, news_capped, screens_public, request_meta)
        private = assemble_private(session_info, lists, rows, eligibility, counts, history_status,
                                    screens_raw, news_items, news_capped, session.log, skipped, pinned)

        write_json_file(args.out_private, private, 0o600)
        write_json_file(args.out_public, public, 0o644)
        ledger.write(event="run_complete", requests=len(session.log), counts=counts)
        return private, public
    finally:
        session.close()


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("run", help="run the dated broad-market scan")
    scan.add_argument("--env-file", required=True)
    scan.add_argument("--assets-out", required=True, help="private asset-master snapshot output path")
    scan.add_argument("--history", default=None, help="materialized daily.parquet contract path")
    scan.add_argument("--pinned", required=True, help="comma-separated symbols always reported, e.g. META,AMD")
    scan.add_argument("--out-private", required=True)
    scan.add_argument("--out-public", required=True)
    scan.add_argument("--now", default=None, help="UTC ISO timestamp override for tests")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    if args.command == "run":
        _, public = run(args)
        print(json.dumps({"status": "complete", "session_state": public["run"]["session_state"],
                          "scanned": public["counts"]["scanned"], "eligible": public["counts"]["eligible"],
                          "requests": public["requests"]["total_requests"]}))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
