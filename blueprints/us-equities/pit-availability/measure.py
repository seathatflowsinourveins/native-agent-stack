#!/usr/bin/env python3
"""Point-in-time news/filing availability and as-published vintage prices.

Measures gate `pit-news-filings` (catalogs/us-equities/gates-20260922.json):
what can be known point-in-time from open or already-entitled sources, on the
frozen sample in plan.json. Three parts:

(a) Filings: data.sec.gov submissions JSON per CIK. Fraction of 8-K/10-Q/10-K
    filings 2016-2026 carrying `acceptanceDateTime`; relation of acceptance
    time to `filingDate`; after-hours acceptance share.
(b) News: Alpaca news API (Benzinga) via alpaca-py 0.44.0. One sampled week
    per year 2016-2026: item counts, `created_at` presence, share with
    `updated_at` later than `created_at`, earliest date.
(c) Vintage prices: Alpaca daily bars adjustment=raw vs adjustment=all around
    corporate-action dates (feed=sip), and the corporate-actions endpoint's
    dated records.

Pure parsing/classification functions (importable without network, used by
tests/test_pit_availability.py) are defined first; network I/O lives in the
`fetch_*` and `run_*` functions invoked only from `main()`. Credentials are
loaded from the env files named in plan.json into this process only and are
never printed or written to the receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent
EASTERN = ZoneInfo("America/New_York")
SEC_RATE_LIMIT_PER_SEC = 5
SEC_MIN_INTERVAL = 1.0 / SEC_RATE_LIMIT_PER_SEC


# --------------------------------------------------------------------------
# Env loading (never logs values)
# --------------------------------------------------------------------------

def load_env_file(path: str) -> dict:
    """Parse `export KEY=VALUE` lines from a shell env file. No network, no printing."""
    env = {}
    text = Path(path).read_text()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r'export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)', line)
        if not match:
            continue
        key, val = match.groups()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        env[key] = val
    return env


# --------------------------------------------------------------------------
# Part (a): SEC filings acceptance-time parsing
# --------------------------------------------------------------------------

def parse_sec_datetime(raw: str) -> datetime:
    """Parse an EDGAR `acceptanceDateTime` string (e.g. '2023-06-01T16:30:24.000Z') as aware UTC."""
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def classify_acceptance_session(eastern_time) -> str:
    """Classify an Eastern local `time` into one of three windows:
    - 'regular': 06:00-16:00, the exchange-close-based cutoff (the look-ahead
      risk boundary: a strategy that reacts to a filing intraday cannot see
      anything accepted after the 16:00 close it is trading against).
    - 'post_close': 16:00-17:30, after the close but still same-business-day
      by EDGAR convention.
    - 'after_hours': everything else (>=17:30 or <06:00 Eastern).
    """
    hm = (eastern_time.hour, eastern_time.minute)
    if (6, 0) <= hm < (16, 0):
        return "regular"
    if (16, 0) <= hm < (17, 30):
        return "post_close"
    return "after_hours"


def classify_filing_row(row: dict) -> dict:
    """Classify one submissions-JSON filing row's acceptance-time relation to filingDate.

    Returns has_acceptance, and when present: eastern acceptance date/time,
    whether the Eastern acceptance date differs from filingDate, the acceptance
    session (see classify_acceptance_session) and is_after_hours (kept for
    backward compatibility: True for both 'post_close' and 'after_hours', i.e.
    outside the 06:00-17:30 conventional EDGAR same-business-day window).
    """
    filing_date = row.get("filingDate")
    raw_acceptance = row.get("acceptanceDateTime")
    result = {
        "accessionNumber": row.get("accessionNumber"),
        "form": row.get("form"),
        "filingDate": filing_date,
        "has_acceptance": bool(raw_acceptance),
    }
    if not raw_acceptance:
        return result
    acceptance_utc = parse_sec_datetime(raw_acceptance)
    acceptance_eastern = acceptance_utc.astimezone(EASTERN)
    eastern_date = acceptance_eastern.date().isoformat()
    eastern_time = acceptance_eastern.time()
    session = classify_acceptance_session(eastern_time)
    result.update({
        "acceptance_utc": acceptance_utc.isoformat(),
        "acceptance_eastern_date": eastern_date,
        "acceptance_eastern_time": eastern_time.isoformat(timespec="seconds"),
        "filing_date_matches_eastern_date": (filing_date == eastern_date) if filing_date else None,
        "acceptance_session": session,
        "is_after_hours": session != "regular",
    })
    return result


def filter_forms_daterange(recent: dict, forms: set, start: str, end: str) -> list:
    """Given a submissions JSON `filings.recent` (or an appended older-file) block
    with parallel arrays, return the row dicts matching `forms` and filingDate
    in [start, end] inclusive."""
    n = len(recent.get("form", []))
    keys = list(recent.keys())
    out = []
    for i in range(n):
        row = {k: recent[k][i] for k in keys if i < len(recent[k])}
        if row.get("form") not in forms:
            continue
        fd = row.get("filingDate")
        if not fd or not (start <= fd <= end):
            continue
        out.append(row)
    return out


def check_10k_completeness(by_form: dict, expected: int, tolerance: int) -> dict:
    """Flag a symbol whose 10-K count (original + 10-K/A counted separately, per
    plan.json filings_forms) falls short of the expected roughly-one-per-year
    count over the sample window. A shortfall is real evidence of either a gap
    in what data.sec.gov's submissions JSON returns, or -- as found for XOM --
    a ticker-to-CIK identity discontinuity (the current ticker no longer maps
    to the CIK that filed the historical 10-Ks); it is reported, not silently
    resolved."""
    actual = by_form.get("10-K", {}).get("total", 0)
    shortfall = actual < (expected - tolerance)
    return {
        "actual_10k_count": actual,
        "expected_10k_count": expected,
        "tolerance": tolerance,
        "shortfall": shortfall,
    }


def summarize_filings(classified_rows: list) -> dict:
    total = len(classified_rows)
    with_acceptance = [r for r in classified_rows if r["has_acceptance"]]
    n_with = len(with_acceptance)
    post_close = [r for r in with_acceptance if r.get("acceptance_session") == "post_close"]
    after_hours = [r for r in with_acceptance if r.get("acceptance_session") == "after_hours"]
    mismatched = [r for r in with_acceptance if r.get("filing_date_matches_eastern_date") is False]
    by_form = {}
    for r in classified_rows:
        entry = by_form.setdefault(r["form"], {
            "total": 0, "with_acceptance": 0,
            "regular_count": 0, "post_close_count": 0, "after_hours_count": 0,
        })
        entry["total"] += 1
        if r["has_acceptance"]:
            entry["with_acceptance"] += 1
            session = r.get("acceptance_session")
            if session in ("regular", "post_close", "after_hours"):
                entry[f"{session}_count"] += 1
    for entry in by_form.values():
        n = entry["with_acceptance"]
        entry["post_close_share_of_accepted"] = (entry["post_close_count"] / n) if n else None
        entry["after_hours_share_of_accepted"] = (entry["after_hours_count"] / n) if n else None
    return {
        "total_filings": total,
        "with_acceptance_datetime": n_with,
        "acceptance_datetime_fraction": (n_with / total) if total else None,
        # 16:00 ET is the close-based look-ahead-risk cutoff: 'post_close' (16:00-17:30 ET)
        # and 'after_hours' (>=17:30 or <06:00 ET) are reported separately per that cutoff.
        "post_close_count": len(post_close),
        "post_close_share_of_accepted": (len(post_close) / n_with) if n_with else None,
        "after_hours_count": len(after_hours),
        "after_hours_share_of_accepted": (len(after_hours) / n_with) if n_with else None,
        "filing_date_mismatch_count": len(mismatched),
        "filing_date_mismatch_share_of_accepted": (len(mismatched) / n_with) if n_with else None,
        "by_form": by_form,
    }


# --------------------------------------------------------------------------
# Part (b): News revision detection
# --------------------------------------------------------------------------

def parse_news_datetime(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def updated_after_created(item: dict) -> bool:
    """True when `updated_at` is strictly later than `created_at`. This is a
    measured timestamp comparison only -- 'provider updated_at later than
    created_at' -- not a claim about what content actually changed; the API
    exposes no diff or revision history, so 'content revision' would overstate
    what is measured here."""
    created = item.get("created_at")
    updated = item.get("updated_at")
    if not created or not updated:
        return False
    try:
        return parse_news_datetime(updated) > parse_news_datetime(created)
    except ValueError:
        return False


def filter_items_created_in_window(items: list, window_start_iso: str, window_end_iso: str) -> dict:
    """Split `items` by whether `created_at` falls in [window_start, window_end).
    The endpoint's own start/end query params were observed to admit items
    whose created_at is outside the requested window (its date filter can
    match on updated_at instead); this keeps only items whose created_at is
    actually inside the sampled week, and counts how many were dropped as
    direct evidence of that updated_at-based filtering."""
    window_start = parse_news_datetime(window_start_iso)
    window_end = parse_news_datetime(window_end_iso)
    in_window, outside_window = [], []
    for item in items:
        created = item.get("created_at")
        if not created:
            outside_window.append(item)
            continue
        try:
            created_dt = parse_news_datetime(created)
        except ValueError:
            outside_window.append(item)
            continue
        if window_start <= created_dt < window_end:
            in_window.append(item)
        else:
            outside_window.append(item)
    return {"in_window": in_window, "outside_window": outside_window}


def summarize_news_items(items: list) -> dict:
    total = len(items)
    with_created = [i for i in items if i.get("created_at")]
    updated_later = [i for i in items if updated_after_created(i)]
    dates = []
    for i in with_created:
        try:
            dates.append(parse_news_datetime(i["created_at"]))
        except ValueError:
            continue
    return {
        "item_count": total,
        "with_created_at": len(with_created),
        "created_at_fraction": (len(with_created) / total) if total else None,
        "updated_after_created_count": len(updated_later),
        "updated_after_created_share": (len(updated_later) / total) if total else None,
        "earliest_created_at": min(dates).isoformat() if dates else None,
        "latest_created_at": max(dates).isoformat() if dates else None,
    }


# --------------------------------------------------------------------------
# Part (c): raw vs adjusted vintage-price ratio
# --------------------------------------------------------------------------

def raw_vs_adjusted_ratio(raw_bars: list, adj_bars: list) -> list:
    """Pair raw and fully-adjusted daily close bars by date (ISO date string key)
    and return per-date {date, raw_close, adjusted_close, ratio}. ratio is
    raw_close / adjusted_close; a step in this ratio across a corporate-action
    date is the discontinuity the raw series carries and the adjusted series
    removes."""
    raw_by_date = {b["date"]: b["close"] for b in raw_bars}
    adj_by_date = {b["date"]: b["close"] for b in adj_bars}
    out = []
    for date in sorted(set(raw_by_date) & set(adj_by_date)):
        raw_close = raw_by_date[date]
        adj_close = adj_by_date[date]
        ratio = (raw_close / adj_close) if adj_close else None
        out.append({"date": date, "raw_close": raw_close, "adjusted_close": adj_close, "ratio": ratio})
    return out


LOG_STEP_THRESHOLD = 0.05  # |ln(ratio_t) - ln(ratio_t-1)| > 5% relative change: SPLITS ONLY, see below


def detect_ratio_step(paired: list, log_threshold: float = LOG_STEP_THRESHOLD) -> dict:
    """Find day-over-day changes in the raw/adjusted ratio using a *relative*
    (log-space) step rather than a fixed absolute tolerance. A fixed absolute
    tolerance (e.g. 0.005) is comparable to ordinary rounding/precision noise
    when the ratio itself is near 1.0 and comparable to real multi-way splits
    when the ratio is 15-20+, so it produces false positives on names with no
    dividend/split-driven adjustment at all (observed: a 0.005 absolute
    tolerance found 155 'steps' in TSLA's raw/adjusted ratio series even
    though the ratio only genuinely steps twice, at its two splits). The log
    step `|ln(ratio_t) - ln(ratio_t-1)|` is scale-invariant: a 5% relative
    change (log_threshold=0.05) is well above normal same-day rounding noise
    and well below a real split's adjustment factor.

    This function detects SPLITS ONLY. An ordinary ex-dividend adjustment
    factor is typically ~0.1-1% (a cash dividend divided by the prior close),
    which is well below the 5% threshold by design -- this check does not, and
    is not intended to, catch dividend-driven ratio changes. See
    detect_dividend_adjustment() for a separate, dividend-scaled check.

    Returns every date whose log step exceeds the threshold (not just the
    max), so each can be matched against dated corporate-action records."""
    if len(paired) < 2:
        return {"max_step": None, "max_step_date": None, "steps_found": 0, "step_dates": []}
    max_step = 0.0
    max_step_date = None
    step_dates = []
    prev_ratio = paired[0]["ratio"]
    for row in paired[1:]:
        ratio = row["ratio"]
        if ratio is None or prev_ratio is None or ratio <= 0 or prev_ratio <= 0:
            prev_ratio = ratio
            continue
        log_step = abs(math.log(ratio) - math.log(prev_ratio))
        if log_step > log_threshold:
            step_dates.append({"date": row["date"], "log_step": log_step,
                                "ratio_before": prev_ratio, "ratio_after": ratio})
        if log_step > max_step:
            max_step = log_step
            max_step_date = row["date"]
        prev_ratio = ratio
    return {
        "max_step": max_step, "max_step_date": max_step_date,
        "steps_found": len(step_dates), "step_dates": step_dates,
        "log_threshold": log_threshold,
    }


def compute_log_steps(paired: list) -> dict:
    """Day-over-day log(ratio) step for every date in `paired` (vs the
    immediately preceding paired date, not filtered by any threshold) --
    unlike detect_ratio_step's step_dates, this includes small (sub-5%) steps
    such as ordinary ex-dividend adjustments."""
    steps = {}
    prev_ratio = None
    for row in paired:
        ratio = row["ratio"]
        if ratio is not None and prev_ratio is not None and ratio > 0 and prev_ratio > 0:
            steps[row["date"]] = abs(math.log(ratio) - math.log(prev_ratio))
        prev_ratio = ratio
    return steps


DIVIDEND_STEP_TOLERANCE_RATIO = 0.5  # actual log-step must be within +-50% of the expected magnitude


def detect_dividend_adjustment(paired: list, cash_dividends: list,
                                tolerance_ratio: float = DIVIDEND_STEP_TOLERANCE_RATIO) -> dict:
    """Separate, dividend-scaled check: for each cash_dividends record
    (ex_date, rate), compares the observed raw/adjusted log-step on that
    ex_date against the expected magnitude |ln(close) - ln(close - rate)|
    using the raw close on the nearest prior trading date. This is
    independent of detect_ratio_step's 5%-threshold split detector, which by
    design does not catch dividend-scale (~0.1-1%) adjustments."""
    log_steps = compute_log_steps(paired)
    raw_by_date = {p["date"]: p["raw_close"] for p in paired}
    records = []
    for div in cash_dividends:
        ex_date = div.get("ex_date")
        rate = div.get("rate")
        if not ex_date or rate is None:
            continue
        prior_dates = sorted(d for d in raw_by_date if d < ex_date)
        if not prior_dates:
            continue
        prior_close = raw_by_date[prior_dates[-1]]
        if not prior_close or prior_close <= rate:
            continue
        expected_log_step = abs(math.log(prior_close) - math.log(prior_close - rate))
        actual_log_step = log_steps.get(ex_date)
        matched = (
            actual_log_step is not None and expected_log_step > 0 and
            (1 - tolerance_ratio) * expected_log_step <= actual_log_step <= (1 + tolerance_ratio) * expected_log_step
        )
        records.append({
            "ex_date": ex_date, "rate": rate,
            "expected_log_step": expected_log_step, "actual_log_step": actual_log_step,
            "matched": matched,
        })
    matched_count = sum(1 for r in records if r["matched"])
    return {
        "records_checked": len(records),
        "matched_count": matched_count,
        "unmatched_count": len(records) - matched_count,
        "tolerance_ratio": tolerance_ratio,
        "records": records,
    }


def match_steps_to_corporate_actions(step_dates: list, action_dates: list, window_days: int) -> dict:
    """Match each detected ratio-step date to the nearest corporate-action date
    (any of ex_date/process_date/payable_date/record_date, already flattened
    into `action_dates` as ISO date strings) within `window_days`. Reports
    matched vs unmatched steps -- an unmatched step is either detector noise
    or a real adjustment whose corporate-action record this sample didn't
    carry a matching date for."""
    from datetime import date as _date

    def to_date(s):
        return _date.fromisoformat(s)

    action_ds = [to_date(d) for d in action_dates if d]
    matched, unmatched = [], []
    for step in step_dates:
        step_date = to_date(step["date"])
        nearest = None
        nearest_gap = None
        for action_date in action_ds:
            gap = abs((step_date - action_date).days)
            if nearest_gap is None or gap < nearest_gap:
                nearest_gap = gap
                nearest = action_date
        if nearest is not None and nearest_gap <= window_days:
            matched.append({**step, "matched_action_date": nearest.isoformat(), "gap_days": nearest_gap})
        else:
            unmatched.append(step)
    return {"matched": matched, "unmatched": unmatched,
            "matched_count": len(matched), "unmatched_count": len(unmatched)}


# --------------------------------------------------------------------------
# Receipt assembly
# --------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_mtime_utc(path: Path) -> str:
    """The file's actual last-modified time (os.stat, UTC), not a hand-written
    value -- a hand-written timestamp could be wrong or postdate the run it
    claims to precede, which is not acceptable for a 'written before the run'
    claim."""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(timespec="seconds")


def build_receipt(plan_path: Path, plan: dict, parts: dict, limitations: list, sources: list) -> dict:
    return {
        "id": "pit-availability-20260922",
        "kind": "artifact_measurement",
        "evidence_class": "open_and_entitled_sources_measured",
        "claim": (
            "On the sample in plan.json (all 20 filings/news symbols and 5 vintage-price "
            "symbols are currently-listed survivors as of the plan's write time, and two of "
            "the 20 have a ticker-to-CIK identity break handled separately; see limitations), "
            "measures what point-in-time filing acceptance metadata, news "
            "updated_at-vs-created_at behaviour and raw-vs-adjusted price divergence "
            "establish from open (SEC data.sec.gov) and already-entitled (Alpaca paper/SIP, "
            "Benzinga news) sources. Does not establish a complete historical point-in-time "
            "reconstruction system."
        ),
        "plan_path": "blueprints/us-equities/pit-availability/plan.json",
        "plan_sha256": sha256_file(plan_path),
        "plan_written_utc": file_mtime_utc(plan_path),
        "preregistered": plan.get("preregistered", False),
        "plan_history": plan.get("history"),
        "sources": sources,
        "parts": parts,
        "limitations": limitations,
        "observed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------
# Network: SEC filings
# --------------------------------------------------------------------------

def sec_request(url: str, user_agent: str, min_interval: float = SEC_MIN_INTERVAL) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    elapsed = time.monotonic() - start
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    return data


def fetch_cik_map(user_agent: str) -> dict:
    data = sec_request("https://www.sec.gov/files/company_tickers.json", user_agent)
    return {row["ticker"].upper(): f'{row["cik_str"]:010d}' for row in data.values()}


def fetch_submissions(cik10: str, user_agent: str) -> dict:
    return sec_request(f"https://data.sec.gov/submissions/CIK{cik10}.json", user_agent)


def fetch_all_filing_rows(cik10: str, user_agent: str, forms: set, start: str, end: str) -> dict:
    """Fetch a CIK's filings.recent plus every filings.files[] entry (data.sec.gov
    keeps only the most recent filings inline in filings.recent; older filings,
    if any, live in the paginated filings.files[] entries), filtered to
    `forms`/[start, end]. Returns rows, the fetched older-file names, and the
    raw submissions payload (for name/tickers)."""
    subs = fetch_submissions(cik10, user_agent)
    recent = subs["filings"]["recent"]
    rows = filter_forms_daterange(recent, forms, start, end)
    older_files = subs["filings"].get("files", [])
    older_files_fetched = []
    for entry in older_files:
        older = sec_request(f"https://data.sec.gov/submissions/{entry['name']}", user_agent)
        older_files_fetched.append(entry["name"])
        if isinstance(older, dict) and "form" in older:
            rows += filter_forms_daterange(older, forms, start, end)
    return {"rows": rows, "older_files_fetched": older_files_fetched, "subs": subs}


def run_filings(plan: dict, sec_env: dict) -> dict:
    user_agent = sec_env.get("SEC_USER_AGENT") or sec_env.get("EDGAR_IDENTITY")
    if not user_agent:
        raise RuntimeError("sec.env has neither SEC_USER_AGENT nor EDGAR_IDENTITY")
    forms = set(plan["filings_forms"])
    start, end = plan["filings_date_range"]
    expected_10k = plan.get("filings_expected_10k_per_symbol", 10)
    tolerance = plan.get("filings_completeness_tolerance", 2)
    identity_breaks = {k: v for k, v in plan.get("filings_identity_breaks", {}).items() if k != "note"}
    cik_map = fetch_cik_map(user_agent)
    per_symbol = {}
    all_classified = []
    missing = []
    excluded_from_overall = []
    for symbol in plan["symbols_filings_news"]:
        cik10 = cik_map.get(symbol.upper())
        if not cik10:
            missing.append(symbol)
            continue
        fetched = fetch_all_filing_rows(cik10, user_agent, forms, start, end)
        rows, older_files_fetched, subs = fetched["rows"], fetched["older_files_fetched"], fetched["subs"]
        classified = [classify_filing_row(r) for r in rows]
        summary = summarize_filings(classified)
        summary["sec_cik"] = cik10
        summary["sec_entity_name"] = subs.get("name")
        summary["sec_current_tickers"] = subs.get("tickers", [])
        summary["older_files_fetched"] = older_files_fetched
        summary["completeness"] = check_10k_completeness(summary["by_form"], expected_10k, tolerance)

        break_info = identity_breaks.get(symbol)
        if break_info:
            # A ticker-to-CIK identity break: the current-map CIK's own filings
            # are not representative 2016-2026 coverage, so they are excluded
            # from `overall` (not silently counted as if complete), and the
            # historical CIK is probed explicitly and separately instead.
            summary["identity_break"] = {
                "current_cik": break_info["current_cik"],
                "historical_cik": break_info["historical_cik"],
            }
            summary["excluded_from_overall"] = True
            summary["excluded_reason"] = (
                f"current-map CIK {break_info['current_cik']} filings are not representative "
                f"2016-2026 coverage for {symbol}; see historical_cik_probe."
            )
            historical = fetch_all_filing_rows(break_info["historical_cik"], user_agent, forms, start, end)
            hist_classified = [classify_filing_row(r) for r in historical["rows"]]
            hist_summary = summarize_filings(hist_classified)
            hist_summary["sec_cik"] = break_info["historical_cik"]
            hist_summary["sec_entity_name"] = historical["subs"].get("name")
            hist_summary["sec_current_tickers"] = historical["subs"].get("tickers", [])
            hist_summary["older_files_fetched"] = historical["older_files_fetched"]
            hist_summary["completeness"] = check_10k_completeness(hist_summary["by_form"], expected_10k, tolerance)
            summary["historical_cik_probe"] = hist_summary
            excluded_from_overall.append(symbol)
        else:
            all_classified.extend(classified)
        per_symbol[symbol] = summary
    overall = summarize_filings(all_classified)
    shortfall_symbols = [
        s for s, v in per_symbol.items()
        if not v.get("excluded_from_overall") and v["completeness"]["shortfall"]
    ]
    return {
        "symbols_missing_cik": missing,
        "symbols_10k_shortfall": shortfall_symbols,
        "symbols_excluded_from_overall": excluded_from_overall,
        "overall": overall,
        "per_symbol": per_symbol,
    }


# --------------------------------------------------------------------------
# Network: Alpaca news and vintage prices
# --------------------------------------------------------------------------

def _alpaca_credentials(alpaca_env: dict) -> tuple:
    key = alpaca_env.get("APCA_API_KEY_ID") or alpaca_env.get("ALPACA_API_KEY")
    secret = alpaca_env.get("APCA_API_SECRET_KEY") or alpaca_env.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("alpaca env file has no usable API key/secret pair")
    return key, secret


def run_news(plan: dict, alpaca_env: dict) -> dict:
    """Uses direct REST against /v1beta1/news (same host/auth alpaca-py 0.44.0's
    NewsClient targets). alpaca-py 0.44.0 DOES paginate correctly:
    BaseRestClient._get_marketdata (alpaca/common/rest.py) loops sending
    page_token until the response's next_page_token is None, exactly as
    requests.py's NewsRequest.page_token docstring says ("pagination is
    handled automatically by the SDK"). The real mismatch is only in what
    `limit` means: NewsRequest.limit is documented as "Limit of news items to
    be returned for given page", but _get_marketdata treats it as a TOTAL cap
    across every page (`actual_limit = min(int(limit) - total_items,
    page_limit)`, loop stops once that reaches zero) -- so passing limit=50
    with the SDK, as an earlier version of this script did, legitimately
    capped the run at 50 items total, not one page. Direct REST is kept here
    (simpler than tracking the SDK's total-vs-per-page distinction across 11
    yearly requests) with an explicit per-request page size and its own
    next_page_token loop, so no SDK-internal total cap applies; see README.md."""
    import requests

    key, secret = _alpaca_credentials(alpaca_env)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    symbols = plan["symbols_filings_news"]
    per_year = {}
    for year, window in plan["news_weeks_sampled"].items():
        if year == "note":
            continue
        start, end = window
        start_iso = f"{start}T00:00:00Z"
        end_iso = f"{(datetime.fromisoformat(end) + timedelta(days=1)).date().isoformat()}T00:00:00Z"
        items = []
        page_token = None
        for _ in range(50):
            params = {"symbols": ",".join(symbols), "start": start_iso, "end": end_iso, "limit": 50}
            if page_token:
                params["page_token"] = page_token
            resp = requests.get("https://data.alpaca.markets/v1beta1/news", headers=headers,
                                 params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            items.extend(payload.get("news", []))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        split = filter_items_created_in_window(items, start_iso, end_iso)
        per_year[year] = {
            "raw_returned": summarize_news_items(items),
            "created_at_outside_window_count": len(split["outside_window"]),
            "created_at_outside_window_share": (
                len(split["outside_window"]) / len(items) if items else None
            ),
            "created_at_filtered": summarize_news_items(split["in_window"]),
        }
    return {"window_days": 7, "symbols": symbols, "per_year": per_year}


def run_vintage_prices(plan: dict, alpaca_env: dict) -> dict:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.historical.corporate_actions import CorporateActionsClient
    from alpaca.data.requests import CorporateActionsRequest, StockBarsRequest
    from alpaca.data.enums import Adjustment
    from alpaca.data.timeframe import TimeFrame

    key, secret = _alpaca_credentials(alpaca_env)
    bars_client = StockHistoricalDataClient(key, secret, raw_data=True)
    ca_client = CorporateActionsClient(key, secret, raw_data=True)
    start = plan["filings_date_range"][0]
    end = plan["filings_date_range"][1]
    window = plan["vintage_prices_window_days_around_action"]
    results = {}
    for symbol in plan["symbols_vintage_prices"]:
        raw_req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day,
                                    start=datetime.fromisoformat(start), end=datetime.fromisoformat(end),
                                    adjustment=Adjustment.RAW, feed="sip")
        all_req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day,
                                    start=datetime.fromisoformat(start), end=datetime.fromisoformat(end),
                                    adjustment=Adjustment.ALL, feed="sip")
        raw_payload = bars_client.get_stock_bars(raw_req)
        all_payload = bars_client.get_stock_bars(all_req)
        raw_bars = _extract_bars(raw_payload, symbol)
        adj_bars = _extract_bars(all_payload, symbol)
        paired = raw_vs_adjusted_ratio(raw_bars, adj_bars)
        step = detect_ratio_step(paired)

        ca_req = CorporateActionsRequest(symbols=[symbol], start=datetime.fromisoformat(start),
                                          end=datetime.fromisoformat(end))
        ca_payload = ca_client.get_corporate_actions(ca_req)
        ca_types = _corporate_action_type_counts(ca_payload)
        action_dates = _corporate_action_dates(ca_payload)
        match = match_steps_to_corporate_actions(step["step_dates"], action_dates, window)

        ca_dict = ca_payload.get("corporate_actions", ca_payload) if isinstance(ca_payload, dict) else {}
        cash_dividends = ca_dict.get("cash_dividends", []) if isinstance(ca_dict, dict) else []
        dividend_check = detect_dividend_adjustment(paired, cash_dividends)

        results[symbol] = {
            "raw_bar_count": len(raw_bars),
            "adjusted_bar_count": len(adj_bars),
            "ratio_step_detection": step,
            "corporate_action_type_counts": ca_types,
            "steps_matched_to_corporate_action": match["matched_count"],
            "steps_unmatched": match["unmatched_count"],
            "matched_steps": match["matched"],
            "unmatched_steps": match["unmatched"],
            "dividend_adjustment_check": dividend_check,
        }
    return {"window_days_around_action": window, "per_symbol": results}


def _extract_bars(payload, symbol: str) -> list:
    if isinstance(payload, dict):
        rows = payload.get("bars", {}).get(symbol, []) if "bars" in payload else payload.get(symbol, [])
    else:
        rows = list(payload.get(symbol, []))
    out = []
    for row in rows:
        if isinstance(row, dict):
            date = str(row.get("t", ""))[:10]
            close = row.get("c")
        else:
            date = str(getattr(row, "timestamp", ""))[:10]
            close = getattr(row, "close", None)
        if date and close is not None:
            out.append({"date": date, "close": close})
    return out


def _corporate_action_type_counts(payload) -> dict:
    # CorporateActionsClient(raw_data=True).get_corporate_actions() returns the
    # type-keyed dict directly (e.g. {"cash_dividends": [...], "forward_splits": [...]}),
    # not wrapped under a "corporate_actions" key.
    if not isinstance(payload, dict):
        return {}
    if "corporate_actions" in payload:
        payload = payload["corporate_actions"]
    return {k: len(v) for k, v in payload.items() if isinstance(v, list)}


def _corporate_action_dates(payload) -> list:
    """Flatten every ex_date/process_date/payable_date/record_date across all
    corporate-action records into one list of ISO date strings, for matching
    against detected ratio steps."""
    if not isinstance(payload, dict):
        return []
    if "corporate_actions" in payload:
        payload = payload["corporate_actions"]
    dates = []
    date_keys = ("ex_date", "process_date", "payable_date", "record_date")
    for records in payload.values():
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in date_keys:
                if record.get(key):
                    dates.append(record[key])
    return dates


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=str(HERE / "plan.json"))
    parser.add_argument("--out", default=str(REPO_ROOT / "evidence/receipts/pit-availability.json"))
    parser.add_argument("--parts", default="filings,news,prices",
                         help="comma-separated subset of: filings,news,prices")
    args = parser.parse_args(argv)

    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text())
    requested = set(args.parts.split(","))

    parts = {}
    sources = []
    limitations = [
        "Filing acceptanceDateTime establishes when data.sec.gov accepted the submission, "
        "not when any specific downstream consumer or feed first received or displayed it.",
        "After-hours classification uses a fixed 06:00-17:30 America/New_York window as a proxy "
        "for the EDGAR same-business-day acceptance convention; it is not the codified EDGAR rule text.",
        "'updated_at later than created_at' only measures a timestamp comparison the provider "
        "supplies; the API exposes no diff or content-revision history, so it is not a claim about "
        "what content actually changed, and a same-instant correction or a provider that does not "
        "bump updated_at is invisible to this measure.",
        "The sampled news weeks are one 7-day window per year; they are not a full-year or "
        "full-history news availability measurement.",
        "The news endpoint's start/end query parameters were found (see parts.news.per_year.*."
        "created_at_outside_window_count/share, measured per sampled week, not asserted here) to "
        "admit items whose created_at falls outside the requested window -- i.e. its date filter can "
        "match on updated_at rather than original publication time. created_at_filtered in each year's "
        "output keeps only items whose created_at is actually inside the sampled week; the endpoint's "
        "own date filter is not a point-in-time boundary on its own.",
        "Vintage-price comparison establishes that raw bars carry an unadjusted step at a corporate "
        "action while 'all'-adjusted bars do not; it does NOT establish a versioned historical record "
        "of later trade corrections, busted trades, or same-day price revisions -- Alpaca's raw daily "
        "bars are as-currently-served, not an audit trail of what was originally printed intraday.",
        "All three parts measure what is available from data.sec.gov and Alpaca's paper/SIP + Benzinga "
        "news entitlement today (2026-09-22); they do not establish availability from other vendors or "
        "at other historical dates than today's request time.",
        "The 20 filings/news symbols and 5 vintage-price symbols in plan.json are all currently listed "
        "(survivors as of 2026-09-22, not a delisted/renamed name in either list); nothing measured here "
        "establishes filing, news or price availability for a symbol that was delisted or renamed before "
        "today, and the coverage numbers should not be read as representative of the full historical "
        "universe.",
    ]

    if "filings" in requested:
        sec_env = load_env_file(os.path.expandvars(plan["env_files"]["sec"]))
        parts["filings"] = run_filings(plan, sec_env)
        sources.append({
            "part": "filings",
            "endpoint": "https://data.sec.gov/submissions/CIK{cik}.json",
            "ticker_map": "https://www.sec.gov/files/company_tickers.json",
            "rate_limit_per_sec": plan["filings_rate_limit_per_sec"],
        })

    if "news" in requested:
        alpaca_env = load_env_file(os.path.expandvars(plan["env_files"]["alpaca"]))
        parts["news"] = run_news(plan, alpaca_env)
        sources.append({
            "part": "news",
            "endpoint": "https://data.alpaca.markets/v1beta1/news (Benzinga content)",
            "note": (
                "alpaca-py 0.44.0's NewsClient.get_news() does paginate automatically "
                "(BaseRestClient._get_marketdata loops on next_page_token, matching "
                "NewsRequest.page_token's docstring). Its NewsRequest.limit, however, is "
                "documented as a per-page limit but is implemented as a TOTAL cap across all "
                "pages in alpaca/common/rest.py; passing limit=50 legitimately stopped the SDK "
                "at 50 items total, not one page. Direct REST is used here instead (same host, "
                "params and APCA-API-KEY-ID/APCA-API-SECRET-KEY headers the SDK itself uses) "
                "with its own next_page_token loop and no total-item cap, which is simpler than "
                "tracking the SDK's documented-per-page-vs-implemented-as-total distinction "
                "across 11 yearly requests."
            ),
        })

    if "prices" in requested:
        alpaca_env = load_env_file(os.path.expandvars(plan["env_files"]["alpaca"]))
        parts["prices"] = run_vintage_prices(plan, alpaca_env)
        sources.append({
            "part": "prices",
            "endpoint": "alpaca-py StockHistoricalDataClient bars (feed=sip) and CorporateActionsClient",
        })

    receipt = build_receipt(plan_path, plan, parts, limitations, sources)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
