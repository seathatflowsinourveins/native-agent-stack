#!/usr/bin/env python3
"""Generate ../data/session-calendar.json from exchange_calendars 4.13.2 XNYS.

protocol-core-draft.json populations.session_calendar: every scheduled XNYS
session (early closes included) from 2016-01-01 through the end of the last
possible holdout extension, with each session's scheduled open and close. The
output is deterministic: it has no timestamp or host detail, the rows are in
session order, and the time zone database is the pinned tzdata package (the
host's zoneinfo directory is never read). Regenerate byte-identically with:

  uv venv --python 3.12 .venv
  uv pip sync --python .venv/bin/python --require-hashes requirements.lock
  .venv/bin/python generate_session_calendar.py            # rewrite the file
  .venv/bin/python generate_session_calendar.py --check    # exit 1 if it differs

The generator refuses to run unless every package pinned in requirements.in is
installed at exactly its pinned version.
"""

from __future__ import annotations

import zoneinfo

# Use only the pinned tzdata package, before exchange_calendars builds its
# ZoneInfo("America/New_York") at import time.
zoneinfo.reset_tzpath(to=[])

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
from datetime import datetime, time, timezone  # noqa: E402
from importlib import metadata  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent / "data" / "session-calendar.json"
REQUIREMENTS = HERE / "requirements.in"
CALENDAR = "XNYS"
EXCHANGE_CALENDARS_VERSION = "4.13.2"
START = "2016-01-01"
END = "2030-12-31"
ET = "America/New_York"
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)
COLUMNS = ["session", "open_et", "close_et", "open_utc", "close_utc", "early_close"]


def pinned_versions() -> dict[str, str]:
    pins = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", line)
        if not match:
            raise SystemExit(f"requirements.in: unsupported line {line!r}")
        pins[match.group(1)] = match.group(2)
    return pins


def check_runtime() -> None:
    wrong = []
    for name, version in pinned_versions().items():
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            installed = None
        if installed != version:
            wrong.append(f"{name}: pinned {version}, installed {installed}")
    if wrong:
        raise SystemExit("refusing to generate outside the locked runtime:\n  " + "\n  ".join(wrong))


def iso_utc(stamp) -> str:
    value = stamp.to_pydatetime().astimezone(timezone.utc)
    if value.second or value.microsecond:
        raise SystemExit(f"unexpected sub-minute session time {value!r}")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_local(stamp, tz) -> tuple[str, datetime]:
    value = stamp.to_pydatetime().astimezone(tz)
    return value.isoformat(timespec="seconds"), value


def build() -> str:
    check_runtime()
    import exchange_calendars
    import tzdata

    if exchange_calendars.__version__ != EXCHANGE_CALENDARS_VERSION:
        raise SystemExit(f"exchange_calendars {exchange_calendars.__version__} != {EXCHANGE_CALENDARS_VERSION}")
    tz = zoneinfo.ZoneInfo(ET)
    calendar = exchange_calendars.get_calendar(CALENDAR, start=START, end=END)
    if str(calendar.tz) != ET:
        raise SystemExit(f"{CALENDAR} time zone is {calendar.tz}, expected {ET}")
    schedule = calendar.schedule.loc[START:END]
    early = {stamp.strftime("%Y-%m-%d") for stamp in calendar.early_closes if START <= stamp.strftime("%Y-%m-%d") <= END}
    late = [stamp for stamp in calendar.late_opens if START <= stamp.strftime("%Y-%m-%d") <= END]
    if late:
        raise SystemExit(f"unexpected late opens in range: {late}")
    if schedule["break_start"].notna().any() or schedule["break_end"].notna().any():
        raise SystemExit("unexpected session breaks")

    rows = []
    for label, record in schedule.iterrows():
        session = label.strftime("%Y-%m-%d")
        open_et, open_local = iso_local(record["open"], tz)
        close_et, close_local = iso_local(record["close"], tz)
        if open_local.date().isoformat() != session or close_local.date().isoformat() != session:
            raise SystemExit(f"{session}: open or close is not on the session date in {ET}")
        if open_local.time() != REGULAR_OPEN:
            raise SystemExit(f"{session}: open {open_local.time()} is not {REGULAR_OPEN}")
        is_early = session in early
        expected_close = EARLY_CLOSE if is_early else REGULAR_CLOSE
        if close_local.time() != expected_close:
            raise SystemExit(f"{session}: close {close_local.time()} does not match early_close={is_early}")
        rows.append([session, open_et, close_et, iso_utc(record["open"]), iso_utc(record["close"]), is_early])
    if len({row[0] for row in rows}) != len(rows) or [row[0] for row in rows] != sorted(row[0] for row in rows):
        raise SystemExit("sessions are not unique and ascending")
    if len(early) != sum(row[5] for row in rows):
        raise SystemExit("early-close set does not match the session rows")

    document = {
        "schema_version": 1,
        "id": "mover-v3-session-calendar",
        "protocol_field": "blueprints/us-equities/mover-v3/protocol-core-draft.json#/populations/session_calendar",
        "calendar": CALENDAR,
        "source": {
            "package": "exchange_calendars",
            "version": EXCHANGE_CALENDARS_VERSION,
            "call": f"exchange_calendars.get_calendar({CALENDAR!r}, start={START!r}, end={END!r}).schedule",
        },
        "generator": "blueprints/us-equities/mover-v3/data-tools/generate_session_calendar.py",
        "lock": "blueprints/us-equities/mover-v3/data-tools/requirements.lock",
        "tz_database": {"package": "tzdata", "version": metadata.version("tzdata"), "iana_version": tzdata.IANA_VERSION},
        "timezone": ET,
        "requested_range": {"start": START, "end": END},
        "first_session": rows[0][0],
        "last_session": rows[-1][0],
        "session_count": len(rows),
        "early_close_count": len(early),
        "late_open_count": 0,
        "semantics": (
            "One row per scheduled XNYS session in the range, early closes included. open_et and close_et are the "
            "scheduled open and close in America/New_York with their UTC offset; open_utc and close_utc are the same "
            "instants in UTC. early_close is true when the session is in the calendar's early_closes (a 13:00 ET "
            "close). Unscheduled closures after generation are handled only by session-calendar-amendments.jsonl."
        ),
        "columns": COLUMNS,
        "sessions": "__SESSIONS__",
    }
    text = json.dumps(document, indent=2, ensure_ascii=True)
    body = ",\n".join("    " + json.dumps(row, ensure_ascii=True, separators=(", ", ": ")) for row in rows)
    return text.replace('"__SESSIONS__"', "[\n" + body + "\n  ]") + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="write here (default: ../data/session-calendar.json)")
    parser.add_argument("--check", action="store_true", help="compare with --output instead of writing it")
    args = parser.parse_args(argv)
    raw = build().encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    if args.check:
        current = args.output.read_bytes() if args.output.exists() else b""
        same = current == raw
        print(json.dumps({"status": "match" if same else "differs", "sha256": digest, "bytes": len(raw)}, sort_keys=True))
        return 0 if same else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    print(json.dumps({"status": "written", "sha256": digest, "bytes": len(raw)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
