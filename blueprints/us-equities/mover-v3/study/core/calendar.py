"""The XNYS session calendar (populations.session_calendar, session_times).

data/session-calendar.json is generated once from exchange_calendars 4.13.2 by build_calendar and pinned by
sha256 at the freeze. Removals of unscheduled closures come only from data/session-calendar-amendments.jsonl
(append-only; core.logs checks the prefix rule and the commit-time rule). Every time is epoch seconds (UTC).
"""
from __future__ import annotations

import bisect
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pinned.rules_copy import et_epoch
from core.params import T

CALENDAR_SOURCE = "exchange_calendars 4.13.2 XNYS"


def iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def build_calendar(first: str, last: str) -> dict:
    """The data file's content, from the pinned exchange_calendars version (refuses any other)."""
    import exchange_calendars as xcals

    if xcals.__version__ != "4.13.2":
        raise RuntimeError(f"exchange_calendars {xcals.__version__} is not the pinned 4.13.2")
    cal = xcals.get_calendar("XNYS", start=first, end=last)
    sessions = []
    for s in cal.sessions_in_range(first, last):
        sessions.append({"d": s.strftime("%Y-%m-%d"),
                         "open": iso_utc(cal.session_open(s).timestamp()),
                         "close": iso_utc(cal.session_close(s).timestamp())})
    return {"schema_version": 1, "source": CALENDAR_SOURCE, "first": first, "last": last, "sessions": sessions}


class Calendar:
    def __init__(self, sessions: list[dict], removed: tuple[str, ...] = ()):
        removed = set(removed)
        rows = [r for r in sessions if r["d"] not in removed]
        self.days = [r["d"] for r in rows]
        if self.days != sorted(self.days) or len(set(self.days)) != len(self.days):
            raise ValueError("calendar sessions must be unique and sorted")
        self._open = {r["d"]: parse_utc(r["open"]) for r in rows}
        self._close = {r["d"]: parse_utc(r["close"]) for r in rows}
        self._idx = {d: i for i, d in enumerate(self.days)}
        self.removed = tuple(sorted(removed))

    @classmethod
    def from_files(cls, calendar_path, amendments_path=None):
        body = json.loads(Path(calendar_path).read_text(encoding="utf-8"))
        removed = []
        if amendments_path and Path(amendments_path).exists():
            for line in Path(amendments_path).read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    if rec.get("kind") != "remove_session":
                        raise ValueError(f"unknown calendar amendment kind {rec.get('kind')!r}")
                    removed.append(rec["session"])
        return cls(body["sessions"], tuple(removed))

    def is_session(self, d: str) -> bool:
        return d in self._idx

    def index(self, d: str) -> int:
        return self._idx[d]

    def offset(self, d: str, k: int) -> str | None:
        i = self._idx[d] + k
        return self.days[i] if 0 <= i < len(self.days) else None

    def next_on_or_after(self, d: str) -> str | None:
        i = bisect.bisect_left(self.days, d)
        return self.days[i] if i < len(self.days) else None

    def range(self, first: str, last: str) -> list[str]:
        return self.days[bisect.bisect_left(self.days, first): bisect.bisect_right(self.days, last)]

    def open(self, d: str) -> float:
        return self._open[d]

    def close(self, d: str) -> float:
        return self._close[d]

    def is_early_close(self, d: str) -> bool:
        return self._close[d] < et_epoch(d, "16:00")

    def stamp_1555(self, d: str) -> float:
        """'15:55 ET' = the scheduled close minus 5 minutes (12:55 on a 13:00 early close)."""
        return self._close[d] - T["stamp_before_close_s"]

    def at(self, d: str, hhmm: str) -> float:
        return et_epoch(d, hhmm)

    def session_of_time(self, ts: float) -> str | None:
        """The first session whose scheduled open is at or after ts (chronology.holdout.window)."""
        start = (datetime.fromtimestamp(ts, timezone.utc).date() - timedelta(days=1)).isoformat()
        for d in self.days[bisect.bisect_left(self.days, start):]:
            if self._open[d] >= ts:
                return d
        return None

    def in_regular(self, d: str, ts: float) -> bool:
        return self._open[d] <= ts < self._close[d]


def session_of_time(cal: Calendar, ts: float) -> str | None:
    return cal.session_of_time(ts)


def year_of(d: str) -> int:
    return date.fromisoformat(d).year
