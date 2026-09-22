#!/usr/bin/env python3
"""Decode retained LEAN SPY files into Nautilus bar inputs for the frozen one_zero replay.

Every input is hash-checked against the frozen acceptance-plan table before any
row is read. Missing sessions and malformed, duplicate, nonfinite, non-integer
or split-bearing records are refused; nothing is forward filled or substituted.
Prices are decoded from the pinned LEAN deci-cent integer encoding (raw
normalization); volumes stay integer shares. Nautilus is imported only inside
``to_bars`` so the admission checks stay importable without the engine.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
import hashlib
from pathlib import Path
import zipfile
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
# A full XNYS regular session is 09:30 to 16:00 New York. LEAN labels an hourly
# row by its local start, so a full session yields exactly seven rows: 09:00
# (covering the 09:30 open through 10:00), then 10:00, 11:00, 12:00, 13:00,
# 14:00 and 15:00, the last completing at the 16:00 close. Any other row count
# is refused unless the session is a half-day declared in the mapping manifest.
FULL_SESSION_ROWS = 7
PRICE_SCALE = Decimal(10) ** 4
PRICE_QUANTUM = Decimal("0.0001")
DIVIDEND_QUANTUM = Decimal("0.01")

# Frozen bytes from acceptance-plan.md section 1. Fail on mismatch; never
# substitute a fresh provider download.
FROZEN_INPUT_SHA256 = {
    "equity/usa/hour/spy.zip": "27af83adec03a3dff2bfda0d4edc077a5085f83a8b71f4ac156af3480e2e99d4",
    "equity/usa/daily/spy.zip": "aaa1febad0cb8f91011212c92ff7caac6d4d6415a3b7f73c4b98c438db4274ad",
    "equity/usa/map_files/spy.csv": "4765f330a156d4b0c521c094abf9747c4c7ccaf8e10c15ca50db16887d36d3cf",
    "equity/usa/factor_files/spy.csv": "ad53e292de2e7076ff36721e1dcffd1db0d04fe6813b59aeece8620fb0d4cec1",
    "alternative/interest-rate/usa/interest-rate.csv": "1d0e6f2ab20e61a4330e8a38735bc73cde4034e7293a45d23b5ebdc6467f7899",
}
# The engine's interest-rate reference file is hash-checked but unused: this
# fixture configures no financing, so it is never decoded into bars.
DECODED_INPUTS = ("equity/usa/hour/spy.zip", "equity/usa/daily/spy.zip",
                  "equity/usa/map_files/spy.csv", "equity/usa/factor_files/spy.csv")


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs(data_root: Path, expected: dict | None = None) -> dict:
    """Hash every frozen input. Missing file or mismatch refuses the conversion."""
    expected = FROZEN_INPUT_SHA256 if expected is None else expected
    observed = {}
    for relative, frozen in sorted(expected.items()):
        path = Path(data_root) / relative
        if not path.is_file():
            raise ValueError("missing_input:" + relative)
        found = digest(path)
        if found != frozen:
            raise ValueError("input_hash_mismatch:" + relative)
        observed[relative] = found
    return observed


def read_zip_member(path: Path, member: str) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if names != [member]:
            raise ValueError("unexpected_zip_schema:" + ",".join(names))
        return archive.read(member).decode("ascii").splitlines()


def decode_price(raw: str) -> Decimal:
    """Pinned LEAN raw equity encoding: integer deci-cents scaled by 10,000."""
    if not raw or not raw.lstrip("-").isdigit():
        raise ValueError("malformed_price_field:" + raw)
    value = (Decimal(raw) / PRICE_SCALE).quantize(PRICE_QUANTUM)
    if not value.is_finite() or value <= 0:
        raise ValueError("nonfinite_or_nonpositive_price:" + raw)
    return value


def _session_and_end(stamp: str) -> tuple[str, str, int]:
    """LEAN labels an hourly row by its local start; the bar ends one hour later."""
    if len(stamp) != 14 or stamp[8] != " " or stamp[11] != ":":
        raise ValueError("malformed_timestamp:" + stamp)
    day, clock = stamp.split(" ")
    session = date(int(day[0:4]), int(day[4:6]), int(day[6:8])).isoformat()
    start = time(int(clock[0:2]), int(clock[3:5]))
    end = datetime.combine(date.fromisoformat(session), start, NEW_YORK) + timedelta(hours=1)
    return session, clock, int(end.timestamp()) * 10 ** 9


def parse_hour_rows(lines, start: str, end: str) -> list[dict]:
    """Decode the selected window. Refuse duplicates, disorder and bad records.

    The duplicate and ordering checks run over the whole file before the window
    filter, so a corrupt record outside the selected interval still refuses the
    conversion instead of being skipped silently.
    """
    rows, seen, previous = [], set(), None
    for line in lines:
        if not line.strip():
            continue
        fields = line.split(",")
        if len(fields) != 6:
            raise ValueError("malformed_row_field_count:" + str(len(fields)))
        session, clock, ts_event = _session_and_end(fields[0])
        key = (session, clock)
        if key in seen:
            raise ValueError("duplicate_timestamp:" + session + " " + clock)
        seen.add(key)
        if previous is not None and ts_event <= previous:
            raise ValueError("non_monotonic_timestamp:" + session + " " + clock)
        previous = ts_event
        if not start <= session <= end:
            continue
        o, h, l, c = (decode_price(f) for f in fields[1:5])
        if not fields[5].isdigit():
            raise ValueError("nonintegral_volume:" + fields[5])
        volume = int(fields[5])
        if l > min(o, c) or h < max(o, c, l) or h < l:
            raise ValueError("invalid_ohlc:" + session + " " + clock)
        rows.append({"session_date": session, "local_start": clock, "ts_event_ns": ts_event,
                     "o": str(o), "h": str(h), "l": str(l), "c": str(c), "v": volume})
    if not rows:
        raise ValueError("empty_window")
    return rows


def parse_daily_sessions(lines, start: str, end: str) -> list[str]:
    """The retained daily file is the frozen session membership source."""
    sessions, seen = [], set()
    for line in lines:
        if not line.strip():
            continue
        fields = line.split(",")
        if len(fields) != 6:
            raise ValueError("malformed_daily_field_count:" + str(len(fields)))
        session, _, _ = _session_and_end(fields[0])
        if not start <= session <= end:
            continue
        if session in seen:
            raise ValueError("duplicate_session:" + session)
        seen.add(session)
        sessions.append(session)
    if sessions != sorted(sessions):
        raise ValueError("non_monotonic_sessions")
    return sessions


def check_sessions(rows, sessions, known_short_sessions=None) -> dict:
    """Exact session membership and row count. A gap is refused, never filled.

    ``known_short_sessions`` maps a session date to its expected row count and
    comes from the mapping manifest, so an undeclared short or long session is
    refused rather than merely reported.
    """
    known = {str(k): int(v) for k, v in (known_short_sessions or {}).items()}
    observed = []
    for row in rows:
        if not observed or observed[-1] != row["session_date"]:
            observed.append(row["session_date"])
    missing = [s for s in sessions if s not in set(observed)]
    extra = [s for s in observed if s not in set(sessions)]
    if missing:
        raise ValueError("missing_session:" + ",".join(missing))
    if extra:
        raise ValueError("extra_session:" + ",".join(extra))
    if observed != sessions:
        raise ValueError("session_order")
    counts = {}
    for row in rows:
        counts[row["session_date"]] = counts.get(row["session_date"], 0) + 1
    short = {}
    for session, count in counts.items():
        if count == FULL_SESSION_ROWS:
            continue
        if count > FULL_SESSION_ROWS:
            raise ValueError("unexpected_long_session:" + session)
        if known.get(session) != count:
            raise ValueError("unexpected_short_session:" + session)
        short[session] = count
    undeclared = sorted(set(known) - set(short))
    if undeclared:
        raise ValueError("declared_short_session_absent:" + ",".join(undeclared))
    return {"sessions": len(sessions), "hour_rows": len(rows),
            "full_session_rows": FULL_SESSION_ROWS,
            "partial_sessions": short, "declared_short_sessions": known,
            "missing_session_dates": [], "extra_session_dates": []}


def parse_factor_rows(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split(",")
        if len(fields) != 4:
            raise ValueError("malformed_factor_field_count:" + str(len(fields)))
        rows.append({"date": date(int(fields[0][0:4]), int(fields[0][4:6]), int(fields[0][6:8])).isoformat(),
                     "price_factor": Decimal(fields[1]), "split_factor": Decimal(fields[2]),
                     "reference_price": Decimal(fields[3])})
    if [r["date"] for r in rows] != sorted(r["date"] for r in rows):
        raise ValueError("non_monotonic_factor_rows")
    return rows


def check_no_splits(factor_rows, start: str, end: str) -> None:
    """An unexpected split blocks this fixture; it is never silently absorbed."""
    for index in range(1, len(factor_rows)):
        previous, current = factor_rows[index - 1], factor_rows[index]
        ex_date = (date.fromisoformat(previous["date"]) + timedelta(days=1)).isoformat()
        if start <= ex_date <= end and previous["split_factor"] != current["split_factor"]:
            raise ValueError("unexpected_split:" + ex_date)


def derive_distributions(factor_rows, start: str, end: str) -> list[dict]:
    """Derive each cash distribution from the frozen factor file.

    A LEAN corporate factor row is the last session its factor applies to, so the
    distribution lands on the following calendar date. The per-share amount is
    ``reference_price * (1 - price_factor / next_price_factor)`` rounded to cents
    with the .NET ``Math.Round`` default (half-to-even), matching the pinned
    ``Dividend.ComputeDistribution``. The cash event is stamped at local midnight
    New York on the ex-date.
    """
    distributions = []
    for index in range(1, len(factor_rows)):
        previous, current = factor_rows[index - 1], factor_rows[index]
        ex_date = (date.fromisoformat(previous["date"]) + timedelta(days=1)).isoformat()
        if not start <= ex_date <= end:
            continue
        if current["price_factor"] == 0:
            raise ValueError("zero_price_factor:" + current["date"])
        ratio = previous["price_factor"] / current["price_factor"]
        per_share = (previous["reference_price"] * (1 - ratio)).quantize(
            DIVIDEND_QUANTUM, rounding=ROUND_HALF_EVEN)
        if per_share <= 0:
            continue
        stamp = datetime.combine(date.fromisoformat(ex_date), time(0), NEW_YORK)
        distributions.append({"ex_date": ex_date, "utc_seconds": int(stamp.timestamp()),
                              "per_share": str(per_share)})
    return distributions


def check_map_file(text: str, symbol: str, start: str, end: str) -> list[dict]:
    """The frozen map file must resolve one unchanged ticker over the window."""
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split(",")
        if len(fields) < 2:
            raise ValueError("malformed_map_field_count:" + str(len(fields)))
        rows.append({"date": date(int(fields[0][0:4]), int(fields[0][4:6]), int(fields[0][6:8])).isoformat(),
                     "ticker": fields[1], "exchange": fields[2] if len(fields) > 2 else ""})
    covering = [r for r in rows if r["date"] <= start]
    if not covering or covering[-1]["ticker"].upper() != symbol.upper():
        raise ValueError("map_file_symbol")
    if any(start < r["date"] <= end and r["ticker"].upper() != symbol.upper() for r in rows):
        raise ValueError("map_file_rename_in_window")
    return rows


def convert(data_root: Path, symbol: str, start: str, end: str,
            known_short_sessions=None) -> dict:
    """Full admission path: hashes, decode, session membership, actions."""
    data_root = Path(data_root)
    input_hashes = verify_inputs(data_root)
    rows = parse_hour_rows(read_zip_member(data_root / "equity/usa/hour/spy.zip", "spy.csv"), start, end)
    sessions = parse_daily_sessions(read_zip_member(data_root / "equity/usa/daily/spy.zip", "spy.csv"), start, end)
    counts = check_sessions(rows, sessions, known_short_sessions)
    factor_rows = parse_factor_rows((data_root / "equity/usa/factor_files/spy.csv").read_text())
    check_no_splits(factor_rows, start, end)
    distributions = derive_distributions(factor_rows, start, end)
    map_rows = check_map_file((data_root / "equity/usa/map_files/spy.csv").read_text(), symbol, start, end)
    return {"rows": rows, "counts": counts, "distributions": distributions,
            "input_hashes": input_hashes, "map_rows": map_rows,
            "decoded_inputs": list(DECODED_INPUTS), "forward_filled_rows": 0,
            "price_encoding": "integer deci-cents / 10000, raw normalization",
            "volume_encoding": "integer shares",
            "session_source": "retained LEAN daily spy.zip rows in window"}


def to_bars(rows, bar_type_str: str, price_precision: int, size_precision: int):
    """Build native Nautilus bars. ts_event and ts_init are the bar end instant."""
    from nautilus_trader.model import Bar, BarType, Price, Quantity

    bar_type = BarType.from_str(bar_type_str)
    bars = []
    for row in rows:
        prices = [Price.from_str(format(Decimal(row[k]), "." + str(price_precision) + "f"))
                  for k in ("o", "h", "l", "c")]
        bars.append(Bar(bar_type, *prices, Quantity(row["v"], size_precision),
                        row["ts_event_ns"], row["ts_event_ns"]))
    return bars
