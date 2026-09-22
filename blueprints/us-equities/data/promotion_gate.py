#!/usr/bin/env python3
"""Fail-closed data-snapshot promotion gate for the adaptive paper runtime.

Run this file in its OWN isolated environment (pandera/pandas/
exchange_calendars/pyarrow pinned separately from the paper runtime). It
writes a bounded `gate-result.json`; the runtime consumes only that result
file, never this process's dependencies or the input rows.

Usage:
    python3 promotion_gate.py --input snapshot.parquet --out gate-result.json \
        [--calendar XNYS]

`--input` accepts a `.parquet` file, a `.csv` file, or a `duckdb://<db-path>#<table>`
table spec (the `duckdb` package is optional and only imported for that path;
this venv's pinned install does not include it, so the duckdb path is source
code only until a caller adds that dependency).

Required columns: symbol, session, open, high, low, close, volume, observed_at.
`session` must be an ISO date (YYYY-MM-DD) that is a valid session on the
selected exchange calendar (default XNYS). Rows must be unique on
(symbol, session). The snapshot must contain at least one row (`rows_present`).
OHLC must be positive, high >= max(open, close), low <= min(open, close),
observed_at must not be in the future, and volume must be a finite,
integral, non-negative value -- checked against the RAW column before any
lossy numeric coercion (`volume_integral_non_negative`; a raw value like
`-0.5` would otherwise be silently truncated to `0` by `astype('int64')`
and pass a post-coercion `>= 0` check).

Any exception -- schema failure or otherwise -- produces `status: "fail"`.
This script never raises past its own `main()`; a fail-closed result file is
always written when the output path is writable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_COLUMNS = ("symbol", "session", "open", "high", "low", "close", "volume", "observed_at")
CHECK_NAMES = (
    "rows_present", "symbol_nonempty", "valid_trading_session", "open_positive", "high_positive",
    "low_positive", "close_positive", "volume_integral_non_negative", "observed_at_not_future",
    "high_ge_max_open_close", "low_le_min_open_close", "unique_symbol_session",
)
DUCKDB_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _versions() -> dict:
    import pandas
    import pandera
    import pyarrow
    import exchange_calendars

    return {"python": sys.version.split()[0], "pandas": pandas.__version__,
            "pandera": pandera.__version__, "pyarrow": pyarrow.__version__,
            "exchange_calendars": exchange_calendars.__version__}


def _snapshot_path(input_spec: str) -> Path:
    """The file whose bytes are hashed for `input_sha256`."""
    if input_spec.startswith("duckdb://"):
        remainder = input_spec[len("duckdb://"):]
        if "#" not in remainder:
            raise ValueError("duckdb_spec_requires_table: expected duckdb://<path>#<table>")
        db_path, _table = remainder.split("#", 1)
        return Path(db_path)
    return Path(input_spec)


def _load_frame(input_spec: str):
    import pandas as pd

    if input_spec.startswith("duckdb://"):
        remainder = input_spec[len("duckdb://"):]
        if "#" not in remainder:
            raise ValueError("duckdb_spec_requires_table: expected duckdb://<path>#<table>")
        db_path, table = remainder.split("#", 1)
        if not DUCKDB_TABLE_RE.match(table):
            raise ValueError("duckdb_table_name_rejected")
        import duckdb  # optional dependency; not part of this venv's pinned install
        connection = duckdb.connect(str(Path(db_path)), read_only=True)
        try:
            return connection.execute(f"SELECT * FROM {table}").fetch_df()  # noqa: S608 (table validated above)
        finally:
            connection.close()
    path = Path(input_spec)
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"unsupported_input_format: {suffix or '(none)'}")


def _raw_volume_failure_indices(raw_frame) -> list:
    """Row indices where the RAW (pre-coercion) `volume` value is non-finite,
    has a non-zero fractional part, or is negative.

    Must run on `raw_frame` before `_prepare()`'s `.astype('int64')`
    coercion: that cast silently truncates a fractional/negative value
    (e.g. `-0.5` -> `0`), which would otherwise pass a `>= 0` check computed
    on the already-coerced column. `pd.to_numeric(..., errors="coerce")`
    maps any unparseable raw value to NaN, which `np.isfinite` correctly
    rejects.
    """
    import numpy as np
    import pandas as pd

    numeric = pd.to_numeric(raw_frame["volume"], errors="coerce").to_numpy(dtype="float64")
    finite = np.isfinite(numeric)
    valid = finite & (numeric == np.trunc(numeric)) & (numeric >= 0)
    return [int(index) for index, ok in zip(raw_frame.index, valid) if not ok]


def _prepare(raw_frame):
    import numpy as np
    import pandas as pd

    missing = [column for column in REQUIRED_COLUMNS if column not in raw_frame.columns]
    if missing:
        raise ValueError(f"missing_columns: {','.join(missing)}")
    frame = raw_frame[list(REQUIRED_COLUMNS)].copy()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["session"] = frame["session"].astype(str)
    for column in ("open", "high", "low", "close"):
        frame[column] = frame[column].astype("float64")
    # Safe for downstream schema typing ONLY: pass/fail for volume is decided
    # exclusively by `_raw_volume_failure_indices()` run on `raw_frame` before
    # this function (see `evaluate()`). This substitution exists only so an
    # out-of-range/fractional/NaN raw value cannot raise a casting exception
    # past `_prepare` and collapse the per-check report into a single opaque
    # `gate_execution` failure.
    numeric_volume = pd.to_numeric(raw_frame["volume"], errors="coerce")
    safe_volume = numeric_volume.where(np.isfinite(numeric_volume), 0.0).round(0).clip(lower=0)
    frame["volume"] = safe_volume.astype("int64")
    observed = pd.to_datetime(frame["observed_at"], utc=True, errors="coerce")
    if observed.isna().any():
        raise ValueError("unparseable_observed_at_timestamp")
    frame["observed_at"] = observed.dt.as_unit("ns")
    return frame


def _schema(calendar, now):
    import pandera.pandas as pa

    # Built-in Check factories (.gt/.ge/.str_length) set their own default
    # `.error` string internally; `name=` alone does not change the identifier
    # pandera writes into `failure_cases.check`, so `error=` is passed too.
    return pa.DataFrameSchema(
        {
            "symbol": pa.Column(str, nullable=False,
                                 checks=pa.Check.str_length(min_value=1, name="symbol_nonempty",
                                                             error="symbol_nonempty")),
            "session": pa.Column(str, nullable=False, checks=pa.Check(
                lambda value: calendar.is_session(value), element_wise=True, name="valid_trading_session")),
            "open": pa.Column("float64", pa.Check.gt(0, name="open_positive", error="open_positive")),
            "high": pa.Column("float64", pa.Check.gt(0, name="high_positive", error="high_positive")),
            "low": pa.Column("float64", pa.Check.gt(0, name="low_positive", error="low_positive")),
            "close": pa.Column("float64", pa.Check.gt(0, name="close_positive", error="close_positive")),
            # No pandera-level check here: pass/fail for volume is decided by
            # `_raw_volume_failure_indices()` on the RAW column before `_prepare()`'s
            # coercion (see that function and `evaluate()`). This column's already-
            # sanitized int64 values would trivially pass any post-coercion check.
            "volume": pa.Column("int64"),
            "observed_at": pa.Column("datetime64[ns, UTC]", nullable=False, checks=pa.Check(
                lambda value: value <= now, element_wise=True, name="observed_at_not_future")),
        },
        checks=[
            pa.Check(lambda d: d["high"] >= d[["open", "close"]].max(axis=1), name="high_ge_max_open_close"),
            pa.Check(lambda d: d["low"] <= d[["open", "close"]].min(axis=1), name="low_le_min_open_close"),
        ],
        unique=["symbol", "session"],
        strict=False,
        coerce=False,
    )


def _summarize(failure_cases, row_count: int, extra_failures: dict | None = None) -> list:
    """Fail closed: any pandera failure identifier not in the fixed
    CHECK_NAMES set (e.g. pandera's own `not_nullable` for a null cell) is
    never silently dropped. It is reported under a synthetic
    `unmapped_failures` check with status "fail", so `evaluate()`'s
    any-check-failed status computation still yields "fail" for it.

    `extra_failures` (name -> failing row indices) carries checks computed
    OUTSIDE pandera on raw, pre-coercion data (currently only
    `volume_integral_non_negative`; see `_raw_volume_failure_indices`) and is
    merged into the same per-check report. `rows_present` is handled
    separately below: it is a snapshot-level check (row_count == 0), not a
    per-row one, so it is never driven by failure indices.
    """
    extra_failures = {name: list(indices) for name, indices in (extra_failures or {}).items() if indices}
    if failure_cases is None or len(failure_cases) == 0:
        failing_indices = dict(extra_failures)
    else:
        renamed = failure_cases.copy()
        renamed["check"] = renamed["check"].replace({"multiple_fields_uniqueness": "unique_symbol_session"})
        failing_indices = {}
        for name in sorted(renamed["check"].unique()):
            subset = renamed[renamed["check"] == name]
            failing_indices[name] = sorted({int(index) for index in subset["index"].dropna()})
        for name, indices in extra_failures.items():
            failing_indices[name] = sorted(set(failing_indices.get(name, [])) | set(indices))

    checks = []
    for name in CHECK_NAMES:
        if name == "rows_present":
            checks.append({"name": name, "status": "pass", "detail": "ok"} if row_count > 0 else
                          {"name": name, "status": "fail", "detail": f"snapshot contains {row_count} rows"})
            continue
        indices = failing_indices.get(name)
        if not indices:
            checks.append({"name": name, "status": "pass", "detail": "ok"})
            continue
        checks.append({"name": name, "status": "fail",
                        "detail": f"{len(indices)} of {row_count} rows failed; example row indices {indices[:5]}"})
    unmapped = sorted(set(failing_indices) - set(CHECK_NAMES))
    if unmapped:
        indices = sorted({index for name in unmapped for index in failing_indices[name]})
        checks.append({"name": "unmapped_failures", "status": "fail",
                        "detail": f"unrecognized pandera check identifiers {unmapped}; "
                                  f"{len(indices)} of {row_count} rows failed; "
                                  f"example row indices {indices[:5]}"})
    return checks


def evaluate(input_spec: str, calendar_code: str) -> dict:
    """Run the gate; always returns a result dict, never raises."""
    import pandas as pd
    import pandera.pandas as pa
    import exchange_calendars as xcal

    checked_at = datetime.now(timezone.utc).isoformat()
    input_sha256 = None
    row_count = None
    versions = {}
    try:
        versions = _versions()
        snapshot_path = _snapshot_path(input_spec)
        if not snapshot_path.exists():
            raise FileNotFoundError(f"input_not_found: {snapshot_path.name}")
        input_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
        raw_frame = _load_frame(input_spec)
        row_count = int(len(raw_frame))
        # Computed on raw_frame BEFORE _prepare()'s lossy volume coercion; see
        # _raw_volume_failure_indices and _prepare for why ordering matters.
        extra_failures = {}
        if "volume" in raw_frame.columns:
            extra_failures["volume_integral_non_negative"] = _raw_volume_failure_indices(raw_frame)
        frame = _prepare(raw_frame)
        calendar = xcal.get_calendar(calendar_code)
        now = pd.Timestamp.now(tz="UTC")
        schema = _schema(calendar, now)
        try:
            schema.validate(frame, lazy=True)
            failure_cases = None
        except pa.errors.SchemaErrors as exc:
            failure_cases = exc.failure_cases
        checks = _summarize(failure_cases, row_count, extra_failures=extra_failures)
        status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
        return {"status": status, "input_sha256": input_sha256, "row_count": row_count,
                "checks": checks, "versions": versions, "checked_at": checked_at}
    except Exception as exc:  # fail closed on any exception, including load/env errors
        return {"status": "fail", "input_sha256": input_sha256, "row_count": row_count,
                "checks": [{"name": "gate_execution", "status": "fail",
                            "detail": f"{type(exc).__name__}: {exc}"}],
                "versions": versions, "checked_at": checked_at,
                "exception_class": type(exc).__name__}


def write_result(result: dict, out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    tmp.replace(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="parquet/csv path or duckdb://<db>#<table>")
    parser.add_argument("--out", required=True, type=Path, help="gate-result.json output path")
    parser.add_argument("--calendar", default="XNYS")
    args = parser.parse_args()
    try:
        result = evaluate(args.input, args.calendar)
    except Exception as exc:  # defensive: evaluate() already catches, this guards argument/env errors
        result = {"status": "fail", "input_sha256": None, "row_count": None,
                  "checks": [{"name": "gate_execution", "status": "fail",
                              "detail": f"{type(exc).__name__}: {exc}"}],
                  "versions": {}, "checked_at": datetime.now(timezone.utc).isoformat(),
                  "exception_class": type(exc).__name__}
        traceback.print_exc(file=sys.stderr)
    write_result(result, args.out)
    print(json.dumps({"status": result["status"], "row_count": result["row_count"]}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
