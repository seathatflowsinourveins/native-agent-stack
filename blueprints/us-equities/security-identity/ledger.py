#!/usr/bin/env python3
"""Immutable native DuckDB/Parquet ledger for verified query-scoped observations."""
import argparse
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("identity_probe", HERE / "probe.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
B = P.B
BAR_FIELDS = [*P.FIELDS, "case_id", "requested_symbol", "returned_symbol", "request_asof", "event_at", "event_ns", "session_date", "observed_ns", "available_ns", "valid_from", "valid_to", "original_publication_at", "provider_revision_at", "permanent_security_id", "source_sha256", "source_bytes", "first_observed_at", "acquisition_receipt_sha256"]
ASSET_FIELDS = ["provider_asset_id", "symbol", "status", "exchange", "asset_class", "tradable", "valid_from", "valid_to", "original_publication_at", "provider_revision_at", "historical_universe_eligible", "observed_ns", "source_sha256", "source_bytes", "first_observed_at", "acquisition_receipt_sha256"]
INTEGER = {"event_ns", "observed_ns", "available_ns", "source_bytes"}
BOOLEAN = {"tradable", "historical_universe_eligible"}
SCHEMAS = {"bars": BAR_FIELDS, "assets": ASSET_FIELDS}


def connection():
    if importlib.metadata.version("duckdb") != "1.5.5":
        raise ValueError("duckdb_version_mismatch")
    import duckdb
    return duckdb.connect(":memory:", config={"threads": "1"})


def bar_records(acquisition, anchor):
    return [dict(row, acquisition_receipt_sha256=anchor) for case in acquisition["cases"].values() for row in case["rows"]]


def source_statuses(acquisition):
    return {name: {k: v for k, v in result.items() if k != "rows"}
            for name, result in {**acquisition["cases"], "meta_current": acquisition["asset"]}.items()}


def validate_rows(rows):
    seen = set()
    for row in rows:
        if set(row) != set(BAR_FIELDS) or row["case_id"] not in {c[0] for c in P.CASES}:
            raise ValueError("invalid_ledger_row")
        if any(type(row[k]) is not int or not -(2**63) < row[k] <= 2**63 - 1 for k in ["event_ns", "observed_ns", "available_ns"]):
            raise ValueError("invalid_ledger_nanoseconds")
        if row["available_ns"] != row["observed_ns"] or row["event_ns"] > row["available_ns"]:
            raise ValueError("invalid_observation_availability")
        if any(row[k] is not None for k in ["valid_from", "valid_to", "original_publication_at", "provider_revision_at", "permanent_security_id"]):
            raise ValueError("unsupported_historical_identity_claim")
        key = (row["case_id"], row["event_ns"], row["observed_ns"])
        if key in seen:
            raise ValueError("ambiguous_semantic_revision")
        seen.add(key)


def table_rows(con, table):
    cursor = con.execute(f"SELECT * FROM {table} ORDER BY ALL")
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def selection(con, sql, cutoff_ns, case_id=None):
    if case_id is not None and case_id not in {c[0] for c in P.CASES}:
        raise ValueError("unsupported_query_case")
    if type(cutoff_ns) is not int or not -(2**63) < cutoff_ns <= 2**63 - 1:
        raise ValueError("invalid_cutoff_nanoseconds")
    cursor = con.execute(sql, [case_id, case_id, cutoff_ns, cutoff_ns, cutoff_ns])
    names = [c[0] for c in cursor.description]
    rows = [dict(zip(names, row)) for row in cursor.fetchall()]
    return {"case_id": case_id, "cutoff_ns": str(cutoff_ns), "count": len(rows),
            "selected_rows_sha256": B.sha(B.encode(rows)), "historical_universe_eligible": False}


def proof(con, sql, rows):
    historical = P.ns("2022-06-11T00:00:00Z")
    result = {"historical": selection(con, sql, historical)}
    if rows:
        first, last = min(r["observed_ns"] for r in rows), max(r["observed_ns"] for r in rows)
        for name, cutoff in [("before_first_observation", first-1), ("at_first_observation", first), ("at_last_observation", last)]:
            result[name] = selection(con, sql, cutoff)
    result["historical_replay"] = selection(con, sql, historical)
    return result


def materialize(source, expected_receipt_sha256, out):
    out = B.safe_path(out)
    if out.exists():
        raise FileExistsError("output_directory_exists")
    source = B.safe_path(source)
    P.verify(source, expected_receipt_sha256)
    out = P.new_directory(out)
    frozen_source = out / "source"
    frozen_source.mkdir(mode=0o700)
    for path in sorted(source.iterdir()):
        B.write_new(frozen_source / path.name, B.read(path))
    # Reparse exactly the copied bytes under the external anchor, not mutable paths.
    acquisition = P.verify(frozen_source, expected_receipt_sha256)
    rows = bar_records(acquisition, expected_receipt_sha256)
    validate_rows(rows)
    assets = [dict(row, acquisition_receipt_sha256=expected_receipt_sha256) for row in acquisition["asset"]["rows"]]
    sql_raw = B.read(HERE / "select.sql")
    for name, raw in [("select.sql", sql_raw), ("ledger.py", B.read(Path(__file__))), ("probe.py", B.read(HERE / "probe.py")), ("base-collector.py", B.read(P.BASE_PATH))]:
        B.write_new(out / name, raw)
    with connection() as con:
        for table, records in [("bars", rows), ("assets", assets)]:
            fields = SCHEMAS[table]
            schema = ",".join(f"{f} {'BIGINT' if f in INTEGER else 'BOOLEAN' if f in BOOLEAN else 'VARCHAR'}" for f in fields)
            con.execute(f"CREATE TABLE {table} ({schema})")
            if records:
                con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in fields)})", [[r[f] for f in fields] for r in records])
            con.execute(f"COPY (SELECT * FROM {table} ORDER BY ALL) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(out / (table + ".parquet"))])
            (out / (table + ".parquet")).chmod(0o600)
        eligibility = proof(con, sql_raw.decode(), rows)
    counts = {"bars": len(rows), "assets": len(assets)}
    B.write_new(out / "eligibility.json", B.encode(eligibility))
    files = [B.digest(str(p.relative_to(out)), B.read(p)) for p in sorted(out.rglob("*")) if p.is_file()]
    manifest = {"schema_version": 1, "contract": "query-scoped-identity-ledger-v1", "synthetic": False,
                "duckdb_version": "1.5.5", "acquisition_receipt_sha256": expected_receipt_sha256,
                "files": files, "counts": counts, "eligibility": eligibility,
                "source_statuses": source_statuses(acquisition),
                "provider_revision_availability_established": False, "historical_identity_established": False}
    B.write_new(out / "manifest.json", B.encode(manifest))
    return {"manifest_sha256": B.sha(B.read(out / "manifest.json")), "counts": counts, "eligibility": eligibility,
            "source_statuses": source_statuses(acquisition),
            "historical_identity_established": False, "provider_revision_availability_established": False}


def verified(root, expected_manifest_sha256):
    root = B.safe_path(root)
    raw = B.read(root / "manifest.json")
    if B.sha(raw) != expected_manifest_sha256:
        raise ValueError("manifest_hash_mismatch")
    manifest = B.strict_json(raw)
    if manifest["contract"] != "query-scoped-identity-ledger-v1" or manifest["synthetic"] is not False:
        raise ValueError("unsupported_ledger_contract")
    files = {}
    for entry in manifest["files"]:
        name = entry["path"]
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts or name in files:
            raise ValueError("unsafe_or_duplicate_artifact")
        content = B.read(root / name)
        if B.sha(content) != entry["sha256"] or len(content) != entry["bytes"]:
            raise ValueError("artifact_hash_mismatch")
        files[name] = content
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if any(p.is_symlink() or (p.is_dir() and p != root / "source") for p in root.rglob("*")):
        raise ValueError("unexpected_ledger_directory_or_symlink")
    if actual != {"manifest.json", *files}:
        raise ValueError("unexpected_ledger_artifact")
    required = {"bars.parquet", "assets.parquet", "select.sql", "ledger.py", "probe.py", "base-collector.py", "eligibility.json"}
    if {n for n in files if not n.startswith("source/")} != required:
        raise ValueError("unexpected_ledger_payload_set")
    if files["select.sql"] != B.read(HERE / "select.sql"):
        raise ValueError("selection_sql_version_mismatch")
    for name, path in [("ledger.py", Path(__file__)), ("probe.py", HERE / "probe.py"), ("base-collector.py", P.BASE_PATH)]:
        if files[name] != B.read(path):
            raise ValueError("ledger_bridge_version_mismatch")
    # All native queries operate only on the verified frozen bytes in this temp copy.
    with tempfile.TemporaryDirectory(prefix="identity-verified-") as temp:
        staged = Path(temp)
        (staged / "source").mkdir(mode=0o700)
        for name, content in files.items():
            B.write_new(staged / name, content)
        acquisition = P.verify(staged / "source", manifest["acquisition_receipt_sha256"])
        if manifest["source_statuses"] != source_statuses(acquisition):
            raise ValueError("source_status_mismatch")
        rows = bar_records(acquisition, manifest["acquisition_receipt_sha256"])
        validate_rows(rows)
        assets = [dict(row, acquisition_receipt_sha256=manifest["acquisition_receipt_sha256"]) for row in acquisition["asset"]["rows"]]
        with connection() as con:
            for table, expected in [("bars", rows), ("assets", assets)]:
                con.read_parquet(str(staged / (table + ".parquet"))).create_view(table)
                actual_rows = table_rows(con, table)
                if sorted(B.encode(r) for r in actual_rows) != sorted(B.encode(r) for r in expected):
                    raise ValueError("materialized_source_mismatch")
            eligibility = proof(con, files["select.sql"].decode(), rows)
        if manifest["counts"] != {"bars": len(rows), "assets": len(assets)} or manifest["eligibility"] != eligibility or B.strict_json(files["eligibility.json"]) != eligibility:
            raise ValueError("eligibility_or_count_mismatch")
    return manifest, files


def select(root, expected_manifest_sha256, cutoff, case_id):
    cutoff_ns = P.ns(cutoff)
    if case_id not in {c[0] for c in P.CASES}:
        raise ValueError("unsupported_query_case")
    _, files = verified(root, expected_manifest_sha256)
    with tempfile.TemporaryDirectory(prefix="identity-select-") as temp, connection() as con:
        path = Path(temp) / "bars.parquet"
        B.write_new(path, files["bars.parquet"])
        con.read_parquet(str(path)).create_view("bars")
        result = selection(con, files["select.sql"].decode(), cutoff_ns, case_id)
    return dict(result, manifest_sha256=expected_manifest_sha256, selection_sql_sha256=B.sha(files["select.sql"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("materialize")
    make.add_argument("--source", type=Path, required=True); make.add_argument("--receipt-sha256", required=True); make.add_argument("--out", type=Path, required=True)
    query = sub.add_parser("select")
    query.add_argument("--ledger", type=Path, required=True)
    for key in ["manifest-sha256", "cutoff", "case-id"]:
        query.add_argument("--" + key, required=True)
    args = parser.parse_args()
    result = materialize(args.source, args.receipt_sha256, args.out) if args.command == "materialize" else select(args.ledger, args.manifest_sha256, args.cutoff, args.case_id)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
