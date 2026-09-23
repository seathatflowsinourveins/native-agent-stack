"""Compute XNYS full closures and early (half-day) closes for 2016-2027
with two independently implemented calendar libraries and report every
disagreement between them.

Source A: exchange_calendars 4.13.2 (get_calendar("XNYS")).
Source B: pandas_market_calendars 5.4.0, own NYSEExchangeCalendar
implementation (pandas_market_calendars.calendars.nyse), not a delegate
to exchange_calendars even though the latter is an installed dependency
of the former in this environment (verified: NYSE class module is
pandas_market_calendars.calendars.nyse, not exchange_calendars).

Both are offline computations (holiday/session rules are hard-coded
calendar logic, not fetched over the network at call time).

Usage: run with a Python interpreter that has both packages importable.
"""
from __future__ import annotations

import json
import sys

import pandas as pd
import exchange_calendars as ec
import pandas_market_calendars as mcal

YEARS = range(2016, 2028)  # 2016-2027 inclusive


def compute_exchange_calendars() -> dict:
    # exchange_calendars defaults to a bound of roughly "today + 1 year";
    # an explicit end date is required to compute the full 2016-2027 range.
    # The calendar's own realized bounds (first/last session) must then be
    # used for range queries: passing the requested "2016-01-01" back into
    # sessions_in_range raises DateOutOfBounds because the realized first
    # session is 2016-01-04 (2016-01-01 is a non-trading New Year's Day).
    cal = ec.get_calendar("XNYS", start="2016-01-01", end="2027-12-31")
    bound_start, bound_end = cal.first_session, cal.last_session
    out = {"library": "exchange_calendars", "version": ec.__version__, "years": {}}
    for year in YEARS:
        start = max(pd.Timestamp(f"{year}-01-01"), bound_start)
        end = min(pd.Timestamp(f"{year}-12-31"), bound_end)
        sessions = cal.sessions_in_range(start, end)
        bdays = pd.bdate_range(start, end)
        holidays = sorted(str(d.date()) for d in (set(bdays) - set(sessions)))
        half_days = []
        for session in sessions:
            open_ = cal.session_open(session)
            close_ = cal.session_close(session)
            if (close_ - open_) < pd.Timedelta(hours=6):
                half_days.append(str(session.date()) if hasattr(session, "date") else str(session))
        out["years"][str(year)] = {
            "holiday_count": len(holidays),
            "holidays": holidays,
            "half_days": sorted(half_days),
        }
    return out


def compute_pandas_market_calendars() -> dict:
    cal = mcal.get_calendar("NYSE")
    out = {
        "library": "pandas_market_calendars",
        "version": mcal.__version__,
        "calendar_class": f"{type(cal).__module__}.{type(cal).__qualname__}",
        "years": {},
    }
    for year in YEARS:
        start, end = f"{year}-01-01", f"{year}-12-31"
        schedule = cal.schedule(start_date=start, end_date=end)
        sessions = set(str(d.date()) for d in schedule.index)
        bdays = pd.bdate_range(start, end)
        holidays = sorted(str(d.date()) for d in bdays if str(d.date()) not in sessions)
        half_days = []
        for idx, row in schedule.iterrows():
            open_ = row["market_open"]
            close_ = row["market_close"]
            if (close_ - open_) < pd.Timedelta(hours=6):
                half_days.append(str(idx.date()))
        out["years"][str(year)] = {
            "holiday_count": len(holidays),
            "holidays": holidays,
            "half_days": sorted(half_days),
        }
    return out


def diff(a: dict, b: dict) -> list[dict]:
    disagreements = []
    for year in a["years"]:
        ay, by = a["years"][year], b["years"].get(year, {})
        a_hol, b_hol = set(ay.get("holidays", [])), set(by.get("holidays", []))
        a_half, b_half = set(ay.get("half_days", [])), set(by.get("half_days", []))
        if a_hol != b_hol:
            disagreements.append({
                "year": year, "field": "holidays",
                "only_in_exchange_calendars": sorted(a_hol - b_hol),
                "only_in_pandas_market_calendars": sorted(b_hol - a_hol),
            })
        if a_half != b_half:
            disagreements.append({
                "year": year, "field": "half_days",
                "only_in_exchange_calendars": sorted(a_half - b_half),
                "only_in_pandas_market_calendars": sorted(b_half - a_half),
            })
    return disagreements


def main() -> None:
    a = compute_exchange_calendars()
    b = compute_pandas_market_calendars()
    disagreements = diff(a, b)
    result = {
        "years_checked": [str(y) for y in YEARS],
        "exchange_calendars": a,
        "pandas_market_calendars": b,
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }
    json.dump(result, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
