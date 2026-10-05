#!/usr/bin/env python3
"""Print the locked XNYS eligibility token for the Dagu step precondition.

Source: gerrymanoim/exchange_calendars@4.13.2:
exchange_calendars/exchange_calendar.py:1012-1016,1263-1279;
exchange_calendars/exchange_calendar_xnys.py:157-165.
Lock evidence: runtime-2604/trading-2604-runtime/pyproject.toml:11 (PR-1),
also manifests/stack.json's exchange-calendars 4.13.2 entry at the PR-4 base.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from importlib.metadata import version
from zoneinfo import ZoneInfo


CALENDAR_VERSION = "4.13.2"
MARKET_ZONE = ZoneInfo("America/New_York")


def eligibility(calendar, now: datetime) -> str:
    """Use today's New York date and actual session close, including early closes."""
    if now.utcoffset() is None:
        raise ValueError("an explicit time zone is required")
    day = now.astimezone(MARKET_ZONE).date().isoformat()
    if not calendar.is_session(day):
        return "non_session"
    return "session" if now >= calendar.session_close(day) else "before_close"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", help="optional RFC 3339 instant for an operator drill")
    args = parser.parse_args(argv)
    # This normal DAG step fails on missing packages, wrong versions or calendar errors.
    if version("exchange-calendars") != CALENDAR_VERSION:
        raise RuntimeError("use the trading runtime's locked exchange-calendars 4.13.2")
    import exchange_calendars

    now = datetime.fromisoformat(args.at) if args.at else datetime.now(MARKET_ZONE)
    if now.utcoffset() is None:
        raise ValueError("--at requires an explicit offset")
    year = now.astimezone(MARKET_ZONE).year
    calendar = exchange_calendars.get_calendar(
        "XNYS", start=f"{year}-01-01", end=f"{year}-12-31"
    )
    print(eligibility(calendar, now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
