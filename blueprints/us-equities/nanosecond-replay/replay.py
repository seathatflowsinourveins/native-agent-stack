#!/usr/bin/env python3
"""Synthetic exact-nanosecond replay through pandas, DuckDB BIGINT and Parquet.

This is an offline representation acceptance, not a market-data or broker adapter.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("existing_temporal_contract", HERE.parent / "point-in-time/temporal_snapshot.py")
PIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PIT)
SEC = PIT.SEC
TEXT_FIELDS = {"row_id": "VARCHAR", "asset_id": "VARCHAR", "available_at": "VARCHAR",
               "source_sequence": "BIGINT"}
OBS = {**TEXT_FIELDS, "logical_event_id": "VARCHAR", "symbol": "VARCHAR", "feed": "VARCHAR",
       "event_at": "VARCHAR", "value_text": "VARCHAR"}
UNIVERSE = {**TEXT_FIELDS, "universe_id": "VARCHAR", "effective_at": "VARCHAR", "is_member": "BOOLEAN"}
FILES = ("source.json", "observations.parquet", "universe.parquet")
CONTRACT = "synthetic-exact-utc-ns-v1"


def utc_ns(value):
    import pandas as pd
    PIT.require(isinstance(value, str) and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,9})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value),
        "rfc3339_explicit_offset_at_most_nine_fractional_digits_required")
    try:
        result = pd.Timestamp(value).tz_convert("UTC").as_unit("ns", round_ok=False).value
    except (ValueError, OverflowError) as error:
        raise PIT.ContractError("invalid_or_out_of_range_utc_nanoseconds") from error
    PIT.require(-(2**63) < result <= 2**63 - 1, "invalid_or_out_of_range_utc_nanoseconds")
    return result


def validate(data):
    PIT.require(isinstance(data, dict) and type(data.get("schema_version")) is int
                and data["schema_version"] == 1 and data.get("synthetic") is True,
                "synthetic_schema_required")
    PIT.text(data.get("provenance"), "provenance")
    normalized, row_ids, versions, event_times = {}, set(), set(), {}
    for name, schema in (("observations", OBS), ("universe", UNIVERSE)):
        rows = data.get(name)
        PIT.require(isinstance(rows, list) and 0 < len(rows) <= PIT.MAX_ROWS, "invalid_row_count")
        normalized[name] = []
        for row in rows:
            PIT.require(isinstance(row, dict) and set(row) == set(schema), "row_schema_mismatch")
            for field, kind in schema.items():
                if kind == "VARCHAR":
                    PIT.text(row[field], field)
                elif kind == "BOOLEAN":
                    PIT.require(type(row[field]) is bool, "boolean_membership_required")
                else:
                    PIT.require(type(row[field]) is int and 0 <= row[field] <= 2**63 - 1,
                                "source_sequence_must_be_nonnegative_int64")
            PIT.require(row["row_id"] not in row_ids, "duplicate_row_id")
            row_ids.add(row["row_id"])
            extra = {"available_ns": utc_ns(row["available_at"])}
            if name == "observations":
                extra["event_ns"] = utc_ns(row["event_at"])
                PIT.require(extra["event_ns"] <= extra["available_ns"], "realized_event_after_availability")
                identity = (name, row["asset_id"], row["logical_event_id"], row["feed"])
                PIT.require(identity not in event_times or event_times[identity] == extra["event_ns"],
                            "revision_changed_event_identity_time")
                event_times[identity] = extra["event_ns"]
            else:
                extra["effective_ns"] = utc_ns(row["effective_at"])
                identity = (name, row["asset_id"], row["universe_id"], extra["effective_ns"])
            key = (*identity, extra["available_ns"], row["source_sequence"])
            PIT.require(key not in versions, "ambiguous_revision_sequence")
            versions.add(key)
            normalized[name].append({**row, **extra})
    return normalized


def materialize(source, output):
    import duckdb
    import pandas as pd
    raw = PIT.bounded_bytes(source)
    data = SEC.parse_json(raw)
    normalized = validate(data)
    output = Path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    SEC.atomic_write(output / "source.json", raw)
    with duckdb.connect() as connection:
        for name, base in (("observations", OBS), ("universe", UNIVERSE)):
            schema = {**base, "available_ns": "BIGINT", "event_ns" if name == "observations" else "effective_ns": "BIGINT"}
            connection.execute(f"CREATE TABLE {name} ({','.join(f'{key} {kind}' for key, kind in schema.items())})")
            connection.executemany(f"INSERT INTO {name} VALUES ({','.join('?' for _ in schema)})",
                                   [[row[key] for key in schema] for row in normalized[name]])
            connection.table(name).order("row_id").write_parquet(str(output / f"{name}.parquet"), compression="zstd")
    manifest = {"schema_version": 1, "contract": CONTRACT, "synthetic": True,
                "provenance": data["provenance"], "ingested_at": SEC.utc_now(),
                "pandas_version": pd.__version__, "duckdb_version": duckdb.__version__,
                "counts": {name: len(rows) for name, rows in normalized.items()},
                "files": {name: {"sha256": SEC.digest(PIT.bounded_bytes(output / name)),
                                 "bytes": (output / name).stat().st_size} for name in FILES}}
    encoded = SEC.json_bytes(manifest)
    SEC.atomic_write(output / "snapshot.json", encoded)
    for name in (*FILES, "snapshot.json"):
        os.chmod(output / name, 0o400)
    return {"snapshot_sha256": SEC.digest(encoded), "source_sha256": SEC.digest(raw),
            "counts": manifest["counts"], "synthetic": True,
            "pandas_version": pd.__version__, "duckdb_version": duckdb.__version__}


def verified(snapshot, expected):
    PIT.require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "trusted_manifest_hash_required")
    snapshot = Path(snapshot)
    raw = PIT.bounded_bytes(snapshot / "snapshot.json")
    PIT.require(SEC.digest(raw) == expected, "snapshot_manifest_hash_mismatch")
    manifest = SEC.parse_json(raw)
    PIT.require(isinstance(manifest, dict) and manifest.get("contract") == CONTRACT
                and manifest.get("synthetic") is True and manifest.get("schema_version") == 1,
                "invalid_snapshot_contract")
    PIT.require(isinstance(manifest.get("files"), dict) and set(manifest["files"]) == set(FILES),
                "invalid_snapshot_files")
    frozen = {}
    for name in FILES:
        PIT.require(not (snapshot / name).is_symlink(), "snapshot_symlink_refused")
        content = PIT.bounded_bytes(snapshot / name)
        entry = manifest["files"][name]
        PIT.require(isinstance(entry, dict) and entry.get("bytes") == len(content)
                    and entry.get("sha256") == SEC.digest(content), "snapshot_artifact_hash_mismatch")
        frozen[name] = content
    normalized = validate(SEC.parse_json(frozen["source.json"]))
    PIT.require(manifest.get("counts") == {name: len(rows) for name, rows in normalized.items()},
                "snapshot_count_mismatch")
    return manifest, frozen


def select(snapshot, expected, cutoff, universe_id, feed):
    import duckdb
    cutoff_ns = utc_ns(cutoff)
    PIT.text(universe_id, "universe_id")
    PIT.text(feed, "feed")
    manifest, frozen = verified(snapshot, expected)
    with tempfile.TemporaryDirectory(prefix="exact-ns-read-") as directory, duckdb.connect() as connection:
        for name in ("observations", "universe"):
            path = Path(directory) / f"{name}.parquet"
            SEC.atomic_write(path, frozen[path.name])
            connection.read_parquet(str(path)).create_view(name)
            PIT.require(connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0] == manifest["counts"][name],
                        "snapshot_count_mismatch")
        sql = (HERE / "select.sql").read_text()
        result = connection.execute(sql, [cutoff_ns, universe_id, feed])
        columns = [column[0] for column in result.description]
        records = [dict(zip(columns, row)) for row in result.fetchall()]
    # JSON number consumers may use IEEE-754 doubles. Keep the integer SQL path
    # exact and serialize nanoseconds as decimal strings at this boundary.
    for record in records:
        for key in record:
            if key.endswith("_ns") or key == "source_sequence":
                record[key] = str(record[key])
    return {"schema_version": 1, "contract": CONTRACT, "synthetic": True,
            "cutoff_text": cutoff, "cutoff_ns": str(cutoff_ns), "universe_id": universe_id, "feed": feed,
            "snapshot_sha256": expected, "source_sha256": manifest["files"]["source.json"]["sha256"],
            "selection_sql_sha256": SEC.digest(sql.encode()), "records": records,
            "market_data_adapter_accepted": False, "availability_evidence_authenticated": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("materialize")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    query = sub.add_parser("select")
    query.add_argument("--snapshot", type=Path, required=True)
    for name in ("snapshot-sha256", "cutoff", "universe-id", "feed"):
        query.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        result = materialize(args.source, args.output) if args.command == "materialize" else select(
            args.snapshot, args.snapshot_sha256, args.cutoff, args.universe_id, args.feed)
    except (PIT.ContractError, ValueError, OSError) as error:
        print(json.dumps({"status": "rejected", "reason": str(error) if isinstance(error, ValueError) else type(error).__name__}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
