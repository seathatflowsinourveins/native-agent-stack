#!/usr/bin/env python3
"""Point-in-time expected earnings-announcement dates from SEC 8-K Item 2.02 filings.

Pure functions (standard library only) plus one CLI that measures date-prediction accuracy
on real filing metadata. No price, return or outcome is read here; the CLI reads filing
metadata, the session calendar and (through signal.py) pre-decision lane membership only.

  python expected_dates.py accuracy --root ROOT --daily DAILY.parquet [--out RECEIPT.json]

Definitions (protocol.json#/announcements and #/expectation):
* An announcement is an original 8-K (form exactly "8-K") whose items include 2.02. Its
  effective session is the acceptance session when accepted before 16:00 ET on a session
  day, otherwise the next session. Filings whose effective sessions fall within
  MERGE_DAYS calendar days after a kept announcement are merged into it.
* Month t is decided at the close of D(t), the last session of month t-1. Only filings
  accepted before CUTOFF_HOUR ET on the session before D(t) are known.
* Monthly rule (Frazzini-Lamont restated): eligible when exactly 4 known announcements
  have effective months in t-12..t-1; expected when one of them is in month t-12.
* Event-time rule (secondary): each known announcement is assigned to the latest known
  10-Q/10-K period end within MAX_PERIOD_LAG days before it; the next fiscal period is the
  latest assigned period plus 3 months; the expected date is the session of the announcement
  assigned to that period minus 12 months (within PERIOD_TOL days) plus 364 days.
"""
from __future__ import annotations

import os
import sys

# signal.py in this directory would shadow the standard-library module: never import from
# the script directory; siblings are loaded under eap_* names by load_sibling().
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse
import bisect
import importlib.util
import calendar
import gzip
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")
CLOSE = time(16, 0)
CUTOFF_HOUR = time(16, 0)
MERGE_DAYS = 7
REQUIRED_COUNT = 4
MAX_PERIOD_LAG = 100
PERIOD_TOL = 10
EVENT_TIME_SHIFT = 364
PERIOD_FORMS = {"10-Q", "10-K", "10-KT"}
# NYSE full-day holidays in 2015; the daily dataset starts 2016-01-04, and 2015 filings
# need a calendar for their effective sessions (protocol deviation D8).
NYSE_HOLIDAYS_2015 = {date(2015, 1, 1), date(2015, 1, 19), date(2015, 2, 16), date(2015, 4, 3),
                      date(2015, 5, 25), date(2015, 7, 3), date(2015, 9, 7), date(2015, 11, 26),
                      date(2015, 12, 25)}

Month = tuple  # (year, month)


def load_sibling(name: str):
    """Import a module of this directory as ``eap_<name>`` without touching sys.path."""
    key = f"eap_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass(frozen=True, order=True)
class Event:
    session: date
    accepted: datetime
    accession: str
    cik: str

    @property
    def month(self) -> Month:
        return (self.session.year, self.session.month)


@dataclass(frozen=True)
class PeriodFiling:
    accepted: datetime
    period_end: date
    form: str


# ---------------------------------------------------------------- calendar and parsing

def sessions_2015() -> list[date]:
    d, out = date(2015, 1, 1), []
    while d.year == 2015:
        if d.weekday() < 5 and d not in NYSE_HOLIDAYS_2015:
            out.append(d)
        d += timedelta(days=1)
    return out


def parse_acceptance(value: str) -> datetime:
    """SEC submissions ``acceptanceDateTime`` (UTC, ``Z``) -> naive US/Eastern wall-clock datetime.

    collect_edgar.py tzcheck compared the field with each sampled filing's SGML
    <ACCEPTANCE-DATETIME> header (Eastern): the JSON value is UTC, 5 hours ahead in EST and
    4 in EDT (receipts/tzcheck-summary.json). A value without ``Z`` is refused.
    """
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z$", value)
    if not m:
        raise ValueError(f"unparseable or non-UTC acceptanceDateTime {value!r}")
    utc = datetime(*map(int, m.groups()), tzinfo=timezone.utc)
    return utc.astimezone(ET).replace(tzinfo=None)


def effective_session(accepted: datetime, sessions: list[date]) -> date | None:
    """Session whose trading can first react: same session before 16:00 ET, else the next."""
    d = accepted.date()
    i = bisect.bisect_left(sessions, d)
    if i < len(sessions) and sessions[i] == d and accepted.time() < CLOSE:
        return d
    j = bisect.bisect_right(sessions, d)
    return sessions[j] if j < len(sessions) else None


def add_months(ym: Month, k: int) -> Month:
    y, m = ym
    n = y * 12 + (m - 1) + k
    return (n // 12, n % 12 + 1)


def shift_date_months(d: date, k: int) -> date:
    y, m = add_months((d.year, d.month), k)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def month_sessions(sessions: list[date], ym: Month) -> list[date]:
    lo = bisect.bisect_left(sessions, date(ym[0], ym[1], 1))
    y, m = add_months(ym, 1)
    hi = bisect.bisect_left(sessions, date(y, m, 1))
    return sessions[lo:hi]


def decision_session(sessions: list[date], t: Month) -> date:
    """D(t): the last session of month t-1 (positions are entered at its close)."""
    prev = month_sessions(sessions, add_months(t, -1))
    if not prev:
        raise ValueError(f"no sessions in the month before {t}")
    return prev[-1]


def information_cutoff(sessions: list[date], t: Month) -> datetime:
    """Filings accepted strictly before this instant are known when month t is decided."""
    d = decision_session(sessions, t)
    i = bisect.bisect_left(sessions, d)
    if i == 0:
        raise ValueError("no session before the decision session")
    return datetime.combine(sessions[i - 1], CUTOFF_HOUR)


# ---------------------------------------------------------------- announcements

def is_item_202(row: dict) -> bool:
    return row.get("form") == "8-K" and "2.02" in [x.strip() for x in (row.get("items") or "").split(",")]


def announcement_events(rows: list[dict], sessions: list[date], merge_days: int = MERGE_DAYS) -> tuple[list[Event], Counter]:
    """Item 2.02 events of one CIK, merged within ``merge_days`` of the kept event."""
    tally = Counter()
    raw = []
    for r in rows:
        if r.get("form") == "8-K/A" and "2.02" in (r.get("items") or ""):
            tally["amendment_excluded"] += 1
        if not is_item_202(r):
            continue
        if not r.get("acceptance"):
            tally["missing_acceptance"] += 1
            continue
        acc = parse_acceptance(r["acceptance"])
        s = effective_session(acc, sessions)
        if s is None:
            tally["beyond_calendar"] += 1
            continue
        if acc.time() >= CLOSE or acc.date() != s:
            tally["rolled_to_next_session"] += 1
        raw.append(Event(s, acc, r["accession"], r["cik"]))
    raw.sort()
    kept: list[Event] = []
    for e in raw:
        if kept and (e.session - kept[-1].session).days <= merge_days:
            tally["merged_within_window"] += 1
            continue
        kept.append(e)
    tally["events"] += len(kept)
    return kept, tally


def known(events: list[Event], cutoff: datetime) -> list[Event]:
    return [e for e in events if e.accepted < cutoff]


def monthly_status(events: list[Event], t: Month, cutoff: datetime) -> dict:
    """Frazzini-Lamont monthly expectation for month t using only filings before ``cutoff``."""
    window = {add_months(t, -k) for k in range(1, 13)}
    k = [e for e in known(events, cutoff) if e.month in window]
    count = len(k)
    eligible = count == REQUIRED_COUNT
    expected = eligible and any(e.month == add_months(t, -12) for e in k)
    return {"count": count, "eligible": eligible, "expected": expected}


def announced_in(events: list[Event], t: Month) -> bool:
    """Actual announcement in month t (uses later filings: evaluation of predictions only)."""
    return any(e.month == t for e in events)


# ---------------------------------------------------------------- fiscal-quarter matching

def period_filings(rows: list[dict]) -> list[PeriodFiling]:
    out = []
    for r in rows:
        if r.get("form") in PERIOD_FORMS and r.get("report_date") and r.get("acceptance"):
            out.append(PeriodFiling(parse_acceptance(r["acceptance"]), date.fromisoformat(r["report_date"]), r["form"]))
    return sorted(out, key=lambda p: (p.accepted, p.period_end))


def assign_period(session: date, period_ends: list[date], max_lag: int = MAX_PERIOD_LAG) -> date | None:
    """Latest period end strictly before the announcement session, at most ``max_lag`` days earlier."""
    cands = [p for p in period_ends if p < session and (session - p).days <= max_lag]
    return max(cands) if cands else None


def near(a: date, b: date, tol: int = PERIOD_TOL) -> bool:
    return abs((a - b).days) <= tol


def event_time_expectation(events: list[Event], periods: list[PeriodFiling], cutoff: datetime) -> dict | None:
    """Expected date of the next announcement from the same fiscal quarter one year earlier."""
    ev = known(events, cutoff)
    ends = sorted({p.period_end for p in periods if p.accepted < cutoff})
    assigned = [(e, assign_period(e.session, ends)) for e in ev]
    assigned = [(e, p) for e, p in assigned if p is not None]
    if not assigned:
        return None
    last_period = max(p for _, p in assigned)
    target = shift_date_months(last_period, 3)
    ref_period = shift_date_months(target, -12)
    refs = [(e, p) for e, p in assigned if near(p, ref_period)]
    if not refs:
        return None
    ref_event, p = min(refs, key=lambda ep: (abs((ep[1] - ref_period).days), ep[0].session))
    return {"target_period": target, "ref_period": p, "ref_session": ref_event.session,
            "expected_date": ref_event.session + timedelta(days=EVENT_TIME_SHIFT)}


def match_actual(events: list[Event], periods: list[PeriodFiling], target_period: date, after: datetime) -> Event | None:
    """Actual announcement for ``target_period`` (uses later filings; evaluation only)."""
    ends = sorted({p.period_end for p in periods})
    for e in events:
        if e.accepted < after:
            continue
        p = assign_period(e.session, ends)
        if p is not None and near(p, target_period):
            return e
    return None


def event_time_trade(events: list[Event], expected_date: date, cutoff: datetime, sessions: list[date],
                     decision: date, month_last: date, k: int = 5, fallback_days: int = 30) -> tuple[date, date] | None:
    """(entry, exit) sessions of the descriptive event-time trade, or None when entry is outside month t.

    Entry: k sessions before the first session on or after ``expected_date``; it must lie in
    (decision, month_last]. No trade when an announcement accepted after ``cutoff`` has an
    effective session on or before entry (it is public before the entry close). Exit: the
    session after the first later announcement; else the first session on or after
    expected_date + fallback_days. Exit timing is observable when it happens.
    """
    i = bisect.bisect_left(sessions, expected_date)
    if i - k < 0 or i >= len(sessions):
        return None
    entry = sessions[i - k]
    if not decision < entry <= month_last:
        return None
    for e in sorted(events):
        if e.accepted < cutoff:
            continue
        if e.session <= entry:
            return None
        j = bisect.bisect_right(sessions, e.session)
        if e.session <= expected_date + timedelta(days=fallback_days) and j < len(sessions):
            return entry, sessions[j]
        break
    j = bisect.bisect_left(sessions, expected_date + timedelta(days=fallback_days))
    return (entry, sessions[j]) if j < len(sessions) else None


# ---------------------------------------------------------------- loading

def load_filings(root: Path) -> dict[str, list[dict]]:
    by_cik: dict[str, list[dict]] = defaultdict(list)
    for line in gzip.decompress((root / "derived" / "filings.jsonl.gz").read_bytes()).splitlines():
        r = json.loads(line)
        by_cik[r["cik"]].append(r)
    return by_cik


CALENDAR_MIN_SYMBOLS = 1000


def load_sessions(con, daily: Path, min_symbols: int | None = None) -> list[date]:
    min_symbols = CALENDAR_MIN_SYMBOLS if min_symbols is None else min_symbols
    rows = con.execute(
        f"SELECT session_date FROM read_parquet('{daily}') GROUP BY 1 HAVING count(*) >= {min_symbols} ORDER BY 1").fetchall()
    return sessions_2015() + [r[0] for r in rows]


def study_months(first: Month = (2017, 1), last: Month = (2026, 8)) -> list[Month]:
    out, m = [], first
    while m <= last:
        out.append(m)
        m = add_months(m, 1)
    return out


# ---------------------------------------------------------------- accuracy CLI (no returns)

def cmd_accuracy(a) -> None:
    S = load_sibling("signal")
    con = S.duck(a.root)
    sessions = load_sessions(con, a.daily)
    universe = json.loads((a.root / "universe.json").read_text())["ciks"]
    filings = load_filings(a.root)
    events, periods, tally = {}, {}, Counter()
    for cik in universe:
        ev, t = announcement_events(filings.get(cik, []), sessions)
        events[cik], periods[cik] = ev, period_filings(filings.get(cik, []))
        tally.update(t)
    tally["ciks_without_any_item_2_02"] = sum(1 for c in universe if not events[c])
    months = study_months()
    decisions = [decision_session(sessions, t) for t in months]
    symbols = {s for syms in universe.values() for s in syms}
    all_lanes = S.lanes_from_inputs(S.load_lane_inputs(con, a.daily, sessions, decisions, symbols))
    lane_counts = {f"{d}": dict(Counter(v for v in all_lanes[d].values() if v)) for d in decisions}
    acc = {lane: Counter() for lane in ("all_mapped", "main")}
    by_year = {lane: defaultdict(Counter) for lane in acc}
    et_err = []
    et_counts = Counter()
    for t in months:
        cutoff = information_cutoff(sessions, t)
        lanes = all_lanes[decision_session(sessions, t)]
        for cik, syms in universe.items():
            in_main = any(lanes.get(s) == "main" for s in syms)
            st = monthly_status(events[cik], t, cutoff)
            actual = announced_in(events[cik], t)
            for lane, member in (("all_mapped", True), ("main", in_main)):
                if not member:
                    continue
                c, cy = acc[lane], by_year[lane][t[0]]
                for cc in (c, cy):
                    cc["firm_months"] += 1
                    cc["eligible"] += st["eligible"]
                    if st["eligible"]:
                        cc["expected"] += st["expected"]
                        cc["actual"] += actual
                        cc["expected_and_actual"] += st["expected"] and actual
            if in_main and st["eligible"] and st["expected"]:
                et = event_time_expectation(events[cik], periods[cik], cutoff)
                if et is None:
                    et_counts["no_event_time_expectation"] += 1
                    continue
                m = match_actual(events[cik], periods[cik], et["target_period"], cutoff)
                if m is None:
                    et_counts["no_matched_actual"] += 1
                    continue
                et_counts["matched"] += 1
                et_err.append((m.session - et["expected_date"]).days)

    def ratios(c):
        return {**dict(c),
                "precision_expected_month_correct": round(c["expected_and_actual"] / c["expected"], 4) if c["expected"] else None,
                "recall_actual_in_expected_month": round(c["expected_and_actual"] / c["actual"], 4) if c["actual"] else None}

    et_err.sort()
    n = len(et_err)
    receipt = {
        "kind": "eap_date_prediction_accuracy", "label": "HIST", "outcomes_computed": False,
        "months": [f"{months[0][0]}-{months[0][1]:02d}", f"{months[-1][0]}-{months[-1][1]:02d}"],
        "event_tally": dict(tally), "lane_symbol_counts_by_decision_session": lane_counts,
        "monthly_rule": {lane: ratios(c) for lane, c in acc.items()},
        "monthly_rule_by_year": {lane: {y: ratios(c) for y, c in sorted(v.items())} for lane, v in by_year.items()},
        "event_time_rule_main": {**dict(et_counts), "n": n,
                                 "median_error_days": et_err[n // 2] if n else None,
                                 "share_abs_error_le_3d": round(sum(abs(x) <= 3 for x in et_err) / n, 4) if n else None,
                                 "share_abs_error_le_7d": round(sum(abs(x) <= 7 for x in et_err) / n, 4) if n else None,
                                 "share_early_gt_7d": round(sum(x < -7 for x in et_err) / n, 4) if n else None,
                                 "share_late_gt_7d": round(sum(x > 7 for x in et_err) / n, 4) if n else None}}
    out = a.out or (a.root / "receipts" / "accuracy.json")
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str))
    print(json.dumps({k: receipt[k] for k in ("event_tally", "monthly_rule", "event_time_rule_main")}, sort_keys=True, default=str))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("accuracy")
    s.add_argument("--root", type=Path, required=True)
    s.add_argument("--daily", type=Path, required=True)
    s.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    cmd_accuracy(a)


if __name__ == "__main__":
    main()
