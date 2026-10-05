#!/usr/bin/env python3
"""Print the locked XNYS eligibility token for the Dagu step precondition.

Source: gerrymanoim/exchange_calendars@4.13.2:
exchange_calendars/exchange_calendar.py:1012-1016,1263-1279;
exchange_calendars/exchange_calendar_xnys.py:157-165.
ecal.py:118-149 renders calendars rather than a close/freshness eligibility token.
Lock evidence: adoption/sdk/requirements-linux-x86_64-py313.lock:241.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo


CALENDAR_VERSION = "4.13.2"
MARKET_ZONE = ZoneInfo("America/New_York")


def eligibility(calendar, now: datetime, events: Path | None = None) -> str:
    """Use today's New York date and actual session close, including early closes."""
    if now.utcoffset() is None:
        raise ValueError("an explicit time zone is required")
    day = now.astimezone(MARKET_ZONE).date().isoformat()
    if not calendar.is_session(day):
        return "non_session"
    close = calendar.session_close(day)
    if now < close:
        return "before_close"
    if events is not None:
        # Producer contract: finish this session's local simulation and atomically
        # publish LEAN_EVENTS after its close, by 16:25 New York. No data acquisition.
        if not events.is_file():
            return "missing_input"
        modified = events.stat().st_mtime
        if modified < close.timestamp():
            return "stale_input"
        if modified > now.timestamp():
            return "future_input"
    return "session"


def calendar_for(now: datetime):
    """Bracket holidays before the first/after the last session of the year.

    exchange_calendars@4.13.2:exchange_calendar.py:1257-1279 uses session
    boundaries for coverage. Genuine uncovered dates still raise DateOutOfBounds.
    """
    import exchange_calendars

    if now.utcoffset() is None:
        raise ValueError("an explicit time zone is required")
    year = now.astimezone(MARKET_ZONE).year
    return exchange_calendars.get_calendar(
        "XNYS", start=f"{year - 1}-12-01", end=f"{year + 1}-01-31"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", help="optional RFC 3339 instant for an operator drill")
    parser.add_argument("--events", type=Path, help="require a local input published after this session's close")
    args = parser.parse_args(argv)
    # This normal DAG step fails on missing packages, wrong versions or calendar errors.
    if version("exchange-calendars") != CALENDAR_VERSION:
        raise RuntimeError("use the trading runtime's locked exchange-calendars 4.13.2")
    now = datetime.fromisoformat(args.at) if args.at else datetime.now(MARKET_ZONE)
    if now.utcoffset() is None:
        raise ValueError("--at requires an explicit offset")
    token = eligibility(calendar_for(now), now, args.events)
    print(token)
    # Unavailable session input must be visible to Dagu's failed-run history/handlers.
    return 1 if token in {"missing_input", "stale_input", "future_input"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
