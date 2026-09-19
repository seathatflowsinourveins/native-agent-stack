#!/usr/bin/env python3
"""Local normalized temporal snapshots; no acquisition, models, or broker access.

Reuses SEC's timestamp, strict JSON, hashing and exclusive-write primitives. It
does not parse SEC documents or authenticate availability/entitlement assertions.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("native_sec_primitives", HERE.parent / "financial-data/sec_data.py")
SEC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SEC)
MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 100000
COMMON = {"row_id": "VARCHAR", "asset_id": "VARCHAR", "available_at": "TIMESTAMPTZ",
          "first_observed_at": "TIMESTAMPTZ", "availability_basis": "VARCHAR",
          "availability_evidence": "VARCHAR"}
OBSERVATIONS = {**COMMON, "symbol": "VARCHAR", "event_at": "TIMESTAMPTZ", "field": "VARCHAR",
                "value_text": "VARCHAR", "unit": "VARCHAR", "feed": "VARCHAR",
                "adjustment": "VARCHAR", "adjustment_available_at": "TIMESTAMPTZ",
                "adjustment_reference": "VARCHAR"}
UNIVERSE = {**COMMON, "universe_id": "VARCHAR", "effective_at": "TIMESTAMPTZ", "is_member": "BOOLEAN"}
FILES = ("source.json", "observations.parquet", "universe.parquet")


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def text(value, field):
    require(isinstance(value, str) and 0 < len(value) <= 512
            and not any(ord(char) < 32 for char in value), f"invalid_{field}")
    return value


def timestamp(value):
    # DuckDB TIMESTAMPTZ and Python datetime represent microseconds. Reject
    # finer precision instead of truncating a post-cutoff event into eligibility.
    require(isinstance(value, str) and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value),
        "timestamp_requires_rfc3339_microsecond_precision")
    return SEC.timestamp(value)


def bounded_bytes(path):
    with Path(path).open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    require(len(content) <= MAX_BYTES, "file_exceeds_bound")
    return content


def validate_source(data):
    require(isinstance(data, dict) and type(data.get("schema_version")) is int
            and data["schema_version"] == 1, "unsupported_source_schema")
    require(type(data.get("synthetic")) is bool, "synthetic_scope_required")
    text(data.get("dataset_id"), "dataset_id")
    text(data.get("provenance"), "provenance")
    identifiers, semantic_versions = set(), set()
    for collection, schema in (("observations", OBSERVATIONS), ("universe", UNIVERSE)):
        rows = data.get(collection)
        require(isinstance(rows, list) and 0 < len(rows) <= MAX_ROWS, "invalid_row_count")
        for row in rows:
            require(isinstance(row, dict) and set(row) == set(schema), "row_schema_mismatch")
            for name, kind in schema.items():
                if kind == "TIMESTAMPTZ":
                    timestamp(row[name])
                elif kind == "BOOLEAN":
                    require(type(row[name]) is bool, "membership_must_be_boolean")
                else:
                    text(row[name], name)
            require(row["row_id"] not in identifiers, "duplicate_row_id")
            identifiers.add(row["row_id"])
            available = timestamp(row["available_at"])
            require(row["availability_basis"] in {"captured_observation", "source_publication"},
                    "unsupported_availability_basis")
            if row["availability_basis"] == "captured_observation":
                require(available >= timestamp(row["first_observed_at"]),
                        "availability_precedes_captured_observation")
            if collection == "observations":
                require(available >= timestamp(row["event_at"]), "realized_observation_precedes_event")
                require(available >= timestamp(row["adjustment_available_at"]),
                        "availability_precedes_adjustment_evidence")
                try:
                    value = Decimal(row["value_text"])
                except InvalidOperation as error:
                    raise ContractError("invalid_decimal") from error
                require(value.is_finite() and -12 <= value.as_tuple().exponent <= 25
                        and value.copy_abs() < Decimal("1e26"), "unrepresentable_decimal")
                key = (collection, row["asset_id"], row["field"], row["unit"],
                       SEC.iso(timestamp(row["event_at"])), SEC.iso(available),
                       row["feed"], row["adjustment"])
            else:
                key = (collection, row["universe_id"], row["asset_id"],
                       SEC.iso(timestamp(row["effective_at"])), SEC.iso(available))
            require(key not in semantic_versions, "ambiguous_temporal_revision")
            semantic_versions.add(key)
    return data


def write_snapshot(source: Path, output: Path):
    import duckdb
    raw = bounded_bytes(source)
    data = validate_source(SEC.parse_json(raw))
    # Reserve the new directory first. Partial attempts have no manifest and are
    # never accepted; reruns cannot overwrite either successful or failed output.
    output = Path(output)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    SEC.atomic_write(output / "source.json", raw)
    with duckdb.connect() as connection:
        for name, schema in (("observations", OBSERVATIONS), ("universe", UNIVERSE)):
            extra = ", value_decimal DECIMAL(38,12)" if name == "observations" else ""
            connection.execute(f"CREATE TABLE {name} ({', '.join(f'{field} {kind}' for field, kind in schema.items())}{extra})")
            values = [[row[field] for field in schema] + ([Decimal(row["value_text"])] if extra else [])
                      for row in data[name]]
            connection.executemany(f"INSERT INTO {name} VALUES ({','.join('?' for _ in values[0])})", values)
            connection.table(name).order("row_id").write_parquet(str(output / f"{name}.parquet"), compression="zstd")
    metadata = {"schema_version": 1, "contract": "realized-observations-and-universe-v1",
                "dataset_id": data["dataset_id"], "synthetic": data["synthetic"],
                "provenance": data["provenance"], "ingested_at": SEC.utc_now(),
                "duckdb_version": duckdb.__version__, "entitlement_verified": False,
                "counts": {name: len(data[name]) for name in ("observations", "universe")},
                "files": {name: {"sha256": SEC.digest(bounded_bytes(output / name)),
                                 "bytes": (output / name).stat().st_size} for name in FILES}}
    manifest = SEC.json_bytes(metadata)
    SEC.atomic_write(output / "snapshot.json", manifest)
    for name in (*FILES, "snapshot.json"):
        os.chmod(output / name, 0o400)
    return {"snapshot_sha256": SEC.digest(manifest), "source_sha256": metadata["files"]["source.json"]["sha256"],
            "counts": metadata["counts"], "synthetic": metadata["synthetic"],
            "duckdb_version": duckdb.__version__, "entitlement_verified": False}


def verified_snapshot(snapshot: Path, expected_sha256):
    require(isinstance(expected_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", expected_sha256), "expected_manifest_hash_required")
    snapshot = Path(snapshot)
    raw = bounded_bytes(snapshot / "snapshot.json")
    require(SEC.digest(raw) == expected_sha256, "snapshot_manifest_hash_mismatch")
    metadata = SEC.parse_json(raw)
    require(isinstance(metadata, dict) and metadata.get("schema_version") == 1
            and metadata.get("contract") == "realized-observations-and-universe-v1", "unsupported_snapshot_contract")
    require(isinstance(metadata.get("files"), dict) and set(metadata["files"]) == set(FILES), "snapshot_file_set_mismatch")
    frozen = {}
    for name in FILES:
        require(not (snapshot / name).is_symlink(), "snapshot_symlink_refused")
        content = bounded_bytes(snapshot / name)
        record = metadata["files"][name]
        require(isinstance(record, dict) and record.get("bytes") == len(content)
                and record.get("sha256") == SEC.digest(content), "snapshot_artifact_hash_mismatch")
        frozen[name] = content
    validate_source(SEC.parse_json(frozen["source.json"]))
    return metadata, frozen


def select(snapshot, expected_sha256, cutoff, universe_id, feed, adjustment, field, unit):
    import duckdb
    cutoff = SEC.iso(timestamp(cutoff))
    for name, value in (("universe_id", universe_id), ("feed", feed), ("adjustment", adjustment), ("field", field), ("unit", unit)):
        text(value, name)
    metadata, frozen = verified_snapshot(snapshot, expected_sha256)
    # Query the exact verified bytes from a private staging directory, avoiding
    # a later reopen of mutable source paths between verification and DuckDB.
    with tempfile.TemporaryDirectory(prefix="native-pit-read-") as directory, duckdb.connect() as connection:
        for name in ("observations", "universe"):
            path = Path(directory) / f"{name}.parquet"
            SEC.atomic_write(path, frozen[path.name])
            connection.read_parquet(str(path)).create_view(name)
            actual = connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            require(actual == metadata["counts"][name], "snapshot_row_count_mismatch")
        query = (HERE / "select.sql").read_text(encoding="utf-8")
        cursor = connection.execute(query, [cutoff, universe_id, feed, adjustment, field, unit])
        columns = [column[0] for column in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]
    for record in records:
        for key, value in record.items():
            if isinstance(value, datetime):
                record[key] = SEC.iso(value)
    return {"schema_version": 1, "scope": "realized_observations_and_effective_universe_state",
            "snapshot_sha256": expected_sha256, "source_sha256": metadata["files"]["source.json"]["sha256"],
            "selection_sql_sha256": SEC.digest(query.encode()), "cutoff": cutoff,
            "universe_id": universe_id, "feed": feed, "adjustment": adjustment, "field": field, "unit": unit,
            "synthetic": metadata["synthetic"], "entitlement_verified": False,
            "availability_evidence_authenticated": False, "records": records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("snapshot")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    query = commands.add_parser("select")
    query.add_argument("--snapshot", type=Path, required=True)
    query.add_argument("--snapshot-sha256", required=True)
    for option in ("cutoff", "universe-id", "feed", "adjustment", "field", "unit"):
        query.add_argument("--" + option, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            result = write_snapshot(args.source, args.output)
        else:
            result = select(args.snapshot, args.snapshot_sha256, args.cutoff, args.universe_id,
                            args.feed, args.adjustment, args.field, args.unit)
    except (ContractError, ValueError, OSError) as error:
        print(json.dumps({"status": "rejected", "reason": str(error) if isinstance(error, ValueError) else type(error).__name__}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
