#!/usr/bin/env python3
"""Offline EdgarTools extraction and DuckDB Parquet/as-of acceptance bridge."""
import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
STRICT_PATH = HERE.parent / "catalyst-provenance/catalyst.py"
SPEC = importlib.util.spec_from_file_location("strict_catalyst", STRICT_PATH)
strict = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(strict)
_PATH_SAFETY_SPEC = importlib.util.spec_from_file_location("path_safety", HERE.parents[2] / "scripts/path_safety.py")
_path_safety = importlib.util.module_from_spec(_PATH_SAFETY_SPEC)
_PATH_SAFETY_SPEC.loader.exec_module(_path_safety)
MAX_JSON = 20 * 1024 * 1024
EDGAR_VERSION = "5.58.0"
DUCKDB_VERSION = "1.5.5"
LIMITATIONS = [
    "Offline metadata conversion of retained sources; no new SEC acquisition.",
    "No historical point-in-time dataset: first observation is in this acquisition run.",
    "Deterministic acquisition subset is not a representative or trading universe.",
    "Header item declarations are not catalyst, incentive, sentiment or price labels.",
    "Unfetched headers, amendment parent accessions and ticker mappings remain unknown.",
    "Hash anchors establish local integrity, not a signed SEC attestation.",
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(path):
    # See scripts/path_safety.py: a symlink is tolerated only when it is a
    # trusted OS-level boundary link (root-owned, not group/world-writable,
    # e.g. macOS's /tmp -> /private/tmp); $TMPDIR grants no exemption.
    return _path_safety.refuse_untrusted_symlinks(path, "symlink_or_parent_traversal_refused")


def read_bytes(path, cap=MAX_JSON):
    path = safe_path(path)
    if not path.is_file() or path.stat().st_size > cap:
        raise ValueError("invalid_or_oversized_file")
    with path.open("rb") as stream:
        raw = stream.read(cap + 1)
    if len(raw) > cap:
        raise ValueError("invalid_or_oversized_file")
    return raw


def unique_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def digest_entry(name, raw):
    return {"path": name, "bytes": len(raw), "sha256": sha(raw)}


def verify_blob(root, entry):
    name = entry["path"]
    if name != Path(name).name or name in {".", ".."}:
        raise ValueError("unsafe_artifact_name")
    raw = read_bytes(root / name)
    if len(raw) != entry["bytes"] or sha(raw) != entry["sha256"]:
        raise ValueError("artifact_hash_mismatch")
    return raw


def bridge_identity():
    return [digest_entry("dataset.py", read_bytes(Path(__file__))),
            digest_entry("../catalyst-provenance/catalyst.py", read_bytes(STRICT_PATH))]


def native_parser_identity():
    from edgar.sgml import FilingHeader, FilingSGML
    from edgar.company_reports.current_report import EightK
    import edgar.sgml.sgml_parser as sgml_parser
    version = importlib.metadata.version("edgartools")
    if version != EDGAR_VERSION:
        raise ValueError("edgartools_version_mismatch")
    paths = sorted({Path(inspect.getfile(x)) for x in [FilingHeader, FilingSGML, EightK, sgml_parser]})
    return {"version": version, "source_files": [digest_entry("edgar/" + str(p).split("/edgar/", 1)[1], read_bytes(p)) for p in paths]}


def native_view(raw):
    """Only local from_text paths: neither native API can fetch a URL here."""
    from edgar.sgml import FilingHeader, FilingSGML
    from edgar.company_reports.current_report import EightK
    text = raw.decode("utf-8")
    tagged = FilingHeader.parse_from_sgml_text(text)
    normalized = FilingSGML.from_text(text).header
    accepted = tagged.acceptance_datetime
    if accepted is None or accepted.tzinfo is not None:
        raise ValueError("native_acceptance_unavailable_or_unexpected_timezone")
    declared = tagged.filing_metadata.get("ITEMS")
    codes = [] if declared is None else [x.strip() for x in declared.split(",")]
    if len(codes) > 40 or any(not re.fullmatch(r"[1-9]\.[0-9]{2}", x) for x in codes) or len(set(codes)) != len(codes):
        raise ValueError("invalid_or_duplicate_native_item")
    items = []
    for code in codes:
        taxonomy = EightK.structure.get_item("ITEM " + code)
        items.append({"code": code, "title": taxonomy.get("Title") if taxonomy else None})
    filers = sorted(int(f.company_information.cik) for f in normalized.filers if f.company_information is not None)
    if len(filers) != len(set(filers)):
        raise ValueError("duplicate_native_filer")
    return {"form": normalized.form, "accession": normalized.accession_number,
            "filed_date": str(normalized.filing_date), "acceptance_raw": accepted.strftime("%Y%m%d%H%M%S"),
            "filer_ciks": filers, "items": items,
            "items_status": "declared" if declared is not None else "not_declared"}


def summary(data):
    accessions = Counter(row["accession"] for row in data["members"])
    return {"members": len(data["members"]), "unique_accessions": len(accessions),
            "cofiling_groups": sum(count > 1 for count in accessions.values()),
            "headers": len(data["headers"]), "qualified_headers": sum(h["status"] == "qualified" for h in data["headers"]),
            "not_fetched": sum(m["fetch_status"] == "not_fetched" for m in data["members"]), "items": len(data["items"])}


def identity(row):
    return row["cik"], row["accession"]


def validate_data(data):
    if data["schema_version"] != 1 or data["native_version"] != EDGAR_VERSION or data["historical_point_in_time"] is not False:
        raise ValueError("unsupported_extraction_schema")
    members, headers, items = data["members"], data["headers"], data["items"]
    if not 1 <= len(members) <= 100000 or len(headers) > 5 or len(items) > 200:
        raise ValueError("dataset_bounds_exceeded")
    def keyed(rows, key):
        result = {}
        for row in rows:
            value = key(row)
            if value in result:
                raise ValueError("duplicate_dataset_identity")
            result[value] = row
        return result
    member_map, header_map = keyed(members, identity), keyed(headers, identity)
    keyed(items, lambda r: (*identity(r), r["source_sha256"], r["ordinal"]))
    code_keys = set()
    for m in members:
        if type(m["cik"]) is not int or m["cik"] < 1 or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", m["accession"]):
            raise ValueError("invalid_member_identity")
        if m["form"] not in strict.FORMS or m["filed_date"] != data["day"] or m["is_amendment"] != (m["form"] == "8-K/A"):
            raise ValueError("invalid_member_form_or_day")
        if m["ticker"] is not None or m["amends_accession"] is not None:
            raise ValueError("unsupported_inferred_mapping")
        strict.timestamp(m["index_observed_at"])
        if m["index_sha256"] != data["index"]["sha256"] or m["index_observed_at"] != data["index"]["first_observed_at"]:
            raise ValueError("index_lineage_mismatch")
        if m["fetch_status"] == "not_fetched":
            if identity(m) in header_map or m["header_sha256"] is not None:
                raise ValueError("unfetched_has_header")
        elif m["fetch_status"] != "fetched" or identity(m) not in header_map:
            raise ValueError("missing_header")
    for h in headers:
        m = member_map.get(identity(h))
        if m is None or m["fetch_status"] != "fetched" or m["header_sha256"] != h["source_sha256"]:
            raise ValueError("header_member_lineage_mismatch")
        if h["form"] != m["form"] or h["filed_date"] != m["filed_date"] or h["index_observed_at"] != m["index_observed_at"]:
            raise ValueError("header_member_identity_mismatch")
        observed = max(strict.timestamp(h["header_observed_at"]), strict.timestamp(h["index_observed_at"]))
        if strict.timestamp(h["first_observed_at"]) != observed:
            raise ValueError("first_observation_mismatch")
        if h["status"] == "qualified":
            if h["available_at"] is None or h["accepted_at"] is None or h["acceptance_raw"] is None:
                raise ValueError("qualified_availability_required")
            accepted = strict.acceptance_time(h["acceptance_raw"])
            if accepted != strict.timestamp(h["accepted_at"]) or strict.timestamp(h["available_at"]) != max(accepted, observed):
                raise ValueError("availability_mismatch")
            if h["cik"] not in h["native_filer_ciks"] or h["items_status"] not in {"declared", "not_declared"}:
                raise ValueError("native_header_identity_missing")
        elif h["status"] != "quarantined" or h["available_at"] is not None or h["item_count"] is not None:
            raise ValueError("quarantine_availability_mismatch")
    by_header = Counter()
    for item in items:
        h = header_map.get(identity(item))
        if h is None or h["status"] != "qualified" or item["source_sha256"] != h["source_sha256"] or item["available_at"] != h["available_at"]:
            raise ValueError("item_header_lineage_mismatch")
        if not re.fullmatch(r"[1-9]\.[0-9]{2}", item["code"]) or type(item["ordinal"]) is not int or item["ordinal"] < 1:
            raise ValueError("invalid_item")
        code_key = (*identity(item), item["code"])
        if code_key in code_keys:
            raise ValueError("duplicate_item_code")
        code_keys.add(code_key)
        by_header[identity(item)] += 1
    for h in headers:
        if h["status"] == "qualified":
            expected = by_header[identity(h)] if h["items_status"] == "declared" else None
            if h["item_count"] != expected:
                raise ValueError("item_count_mismatch")
            ordinals = sorted(x["ordinal"] for x in items if identity(x) == identity(h))
            if ordinals != list(range(1, len(ordinals) + 1)):
                raise ValueError("item_ordinal_gap")
    if data["summary"] != summary(data):
        raise ValueError("dataset_summary_mismatch")


def extract(run, out, expected_receipt_hash):
    run, out = safe_path(run), safe_path(out)
    if out.exists():
        raise FileExistsError(out)
    receipt_raw = read_bytes(run / "receipt.json")
    if sha(receipt_raw) != expected_receipt_hash:
        raise ValueError("receipt_hash_mismatch")
    receipt = unique_json(receipt_raw)
    if receipt["status"] != "complete" or not 1 <= receipt["member_limit"] <= 5 or not 2 <= len(receipt["files"]) <= 6:
        raise ValueError("unsupported_acquisition_bounds")
    entries, blobs = {}, {}
    for entry in receipt["files"]:
        if entry["path"] in entries:
            raise ValueError("duplicate_source")
        strict.timestamp(entry["first_observed_at"])
        entries[entry["path"]] = entry
        blobs[entry["path"]] = verify_blob(run, entry)
    cohort = strict.parse_index(blobs["index.idx"], receipt["day"])
    cutoff = strict.iso(max(strict.timestamp(x["first_observed_at"]) for x in entries.values()))
    # Existing gate verifies the full index, every raw header and cohort membership.
    gate = strict.packet(run, cutoff)
    if read_bytes(run / "receipt.json") != receipt_raw or any(verify_blob(run, e) != blobs[n] for n, e in entries.items()):
        raise ValueError("source_changed_during_verification")
    parser = native_parser_identity()
    members, headers, items = [], [], []
    used = {"index.idx"}
    index = entries["index.idx"]
    selected = cohort[:receipt["member_limit"]]
    for n, member in enumerate(cohort):
        row = {**member, "index_sha256": index["sha256"], "index_observed_at": index["first_observed_at"],
               "fetch_status": "not_fetched", "header_sha256": None, "is_amendment": member["form"] == "8-K/A",
               "amends_accession": None, "ticker": None}
        members.append(row)
        if n >= receipt["member_limit"]:
            continue
        name = f"{member['cik']}-{member['accession']}.hdr.sgml"
        if name not in blobs:
            if sum(x["accession"] == member["accession"] for x in selected) != 1:
                raise ValueError("ambiguous_legacy_header")
            name = member["accession"] + ".hdr.sgml"
        used.add(name)
        entry = entries[name]
        observed = strict.iso(max(strict.timestamp(entry["first_observed_at"]), strict.timestamp(index["first_observed_at"])))
        event = strict.parse_header(blobs[name], member, observed)
        h = {key: event.get(key) for key in ["cik", "accession", "form", "filed_date", "first_observed_at", "accepted_at",
                                             "available_at", "status", "acceptance_raw", "exclusion_reason"]}
        h.update(source_path=name, source_sha256=entry["sha256"], source_bytes=entry["bytes"],
                 header_observed_at=entry["first_observed_at"], index_observed_at=index["first_observed_at"],
                 native_filer_ciks=None, item_count=None, items_status="quarantined")
        if event["status"] == "qualified":
            native = native_view(blobs[name])
            if any(native[k] != event[k] for k in ["form", "accession", "filed_date", "acceptance_raw"]) or member["cik"] not in native["filer_ciks"]:
                raise ValueError("native_header_disagreement")
            h.update(native_filer_ciks=native["filer_ciks"], items_status=native["items_status"],
                     item_count=len(native["items"]) if native["items_status"] == "declared" else None)
            for ordinal, item in enumerate(native["items"], 1):
                items.append({"cik": member["cik"], "accession": member["accession"], "source_sha256": entry["sha256"],
                              "ordinal": ordinal, **item, "available_at": event["available_at"], "taxonomy_version": EDGAR_VERSION})
        row.update(fetch_status="fetched", header_sha256=entry["sha256"])
        headers.append(h)
    if used != set(entries):
        raise ValueError("unexpected_source_set")
    if {identity(h) for h in headers if strict.eligible_at(h, cutoff)} != {identity(e) for e in gate["events"]}:
        raise ValueError("strict_packet_disagreement")
    data = {"schema_version": 1, "day": receipt["day"], "native_version": EDGAR_VERSION, "historical_point_in_time": False,
            "index": index, "observation_cutoff": cutoff, "members": members, "headers": headers, "items": items}
    data["summary"] = summary(data)
    validate_data(data)
    payload = strict.json_bytes(data)
    manifest = {"schema_version": 1, "stage": "extraction", "source_receipt": digest_entry("receipt.json", receipt_raw),
                "source_files": [entries[name] for name in sorted(entries)], "source_day": receipt["day"],
                "index_url": receipt["index_url"], "parsers": {"bridge": bridge_identity(), "edgartools": parser},
                "files": [digest_entry("extraction.json", payload)], "summary": data["summary"],
                "gate": {k: gate[k] for k in ["as_of", "eligible_count", "exclusions"]}, "limitations": LIMITATIONS}
    out.mkdir(mode=0o700)
    strict.write_new(out / "extraction.json", payload)
    strict.write_new(out / "manifest.json", strict.json_bytes(manifest))
    return manifest


def load_extraction(root, expected_manifest_hash):
    root = safe_path(root)
    raw = read_bytes(root / "manifest.json")
    if sha(raw) != expected_manifest_hash:
        raise ValueError("manifest_hash_mismatch")
    manifest = unique_json(raw)
    if manifest["schema_version"] != 1 or manifest["stage"] != "extraction" or [x["path"] for x in manifest["files"]] != ["extraction.json"]:
        raise ValueError("unsupported_manifest")
    if {p.name for p in root.iterdir()} != {"manifest.json", "extraction.json"}:
        raise ValueError("unexpected_payload_set")
    data = unique_json(verify_blob(root, manifest["files"][0]))
    validate_data(data)
    sources = {x["path"]: x for x in manifest["source_files"]}
    if len(sources) != len(manifest["source_files"]) or sources.get("index.idx") != data["index"] or manifest["summary"] != data["summary"]:
        raise ValueError("manifest_lineage_mismatch")
    for h in data["headers"]:
        entry = sources.get(h["source_path"])
        if entry is None or (h["source_sha256"], h["source_bytes"], h["header_observed_at"]) != (entry["sha256"], entry["bytes"], entry["first_observed_at"]):
            raise ValueError("header_source_lineage_mismatch")
    if set(sources) != {"index.idx", *(h["source_path"] for h in data["headers"])}:
        raise ValueError("unexpected_source_set")
    return data, manifest


TABLES = {
    "members": [("cik", "BIGINT"), ("accession", "VARCHAR"), ("company", "VARCHAR"), ("form", "VARCHAR"),
                ("filed_date", "DATE"), ("header_url", "VARCHAR"), ("index_sha256", "VARCHAR"),
                ("index_observed_at", "TIMESTAMPTZ"), ("fetch_status", "VARCHAR"), ("header_sha256", "VARCHAR"),
                ("is_amendment", "BOOLEAN"), ("amends_accession", "VARCHAR"), ("ticker", "VARCHAR")],
    "headers": [("cik", "BIGINT"), ("accession", "VARCHAR"), ("form", "VARCHAR"), ("filed_date", "DATE"),
                ("first_observed_at", "TIMESTAMPTZ"), ("accepted_at", "TIMESTAMPTZ"), ("available_at", "TIMESTAMPTZ"),
                ("status", "VARCHAR"), ("acceptance_raw", "VARCHAR"), ("exclusion_reason", "VARCHAR"),
                ("source_path", "VARCHAR"), ("source_sha256", "VARCHAR"), ("source_bytes", "BIGINT"),
                ("header_observed_at", "TIMESTAMPTZ"), ("index_observed_at", "TIMESTAMPTZ"),
                ("native_filer_ciks", "BIGINT[]"), ("item_count", "INTEGER"), ("items_status", "VARCHAR")],
    "items": [("cik", "BIGINT"), ("accession", "VARCHAR"), ("source_sha256", "VARCHAR"), ("ordinal", "INTEGER"),
              ("code", "VARCHAR"), ("title", "VARCHAR"), ("available_at", "TIMESTAMPTZ"), ("taxonomy_version", "VARCHAR")],
}
AS_OF_SQL = """SELECT m.cik, m.accession, m.form, h.accepted_at, h.first_observed_at,
       h.available_at, h.item_count
FROM members m JOIN headers h USING (cik, accession)
WHERE h.status = 'qualified' AND h.available_at IS NOT NULL
  AND h.available_at <= CAST(? AS TIMESTAMPTZ)
ORDER BY m.cik, m.accession"""
ITEM_AS_OF_SQL = """SELECT i.cik, i.accession, i.source_sha256, i.ordinal, i.code,
       i.title, i.available_at
FROM items i JOIN headers h USING (cik, accession, source_sha256)
WHERE h.status = 'qualified' AND h.available_at IS NOT NULL
  AND i.available_at = h.available_at AND i.available_at <= CAST(? AS TIMESTAMPTZ)
ORDER BY i.cik, i.accession, i.ordinal"""


def duckdb_connection():
    import duckdb
    if importlib.metadata.version("duckdb") != DUCKDB_VERSION:
        raise ValueError("duckdb_version_mismatch")
    con = duckdb.connect(":memory:", config={"threads": "1"})
    con.execute("SET TimeZone='UTC'")
    return con


def rows_json(cursor):
    names = [x[0] for x in cursor.description]
    return [{k: (strict.iso(v) if isinstance(v, datetime) else v.isoformat() if isinstance(v, date) else v)
             for k, v in zip(names, row)} for row in cursor.fetchall()]


def materialize(root, out, expected_manifest_hash):
    out = safe_path(out)
    if out.exists():
        raise FileExistsError(out)
    data, source_manifest = load_extraction(root, expected_manifest_hash)
    con = duckdb_connection()
    out.mkdir(mode=0o700)
    try:
        outputs = []
        for name, fields in TABLES.items():
            con.execute(f"CREATE TABLE {name} (" + ",".join(f"{k} {t}" for k, t in fields) + ")")
            if data[name]:
                con.executemany(f"INSERT INTO {name} VALUES (" + ",".join("?" for _ in fields) + ")",
                                [[row[k] for k, _ in fields] for row in data[name]])
            order = "cik, accession, ordinal" if name == "items" else "cik, accession"
            output = out / f"{name}.parquet"
            con.execute(f"COPY (SELECT * FROM {name} ORDER BY {order}) TO ? (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 2048)", [str(output)])
            output.chmod(0o600)
            outputs.append(digest_entry(output.name, read_bytes(output)))
        results = {}
        for label, cutoff in [("historical", "2020-03-03T00:00:00Z"), ("observation", data["observation_cutoff"])]:
            events = rows_json(con.execute(AS_OF_SQL, [cutoff]))
            item_rows = rows_json(con.execute(ITEM_AS_OF_SQL, [cutoff]))
            results[label] = {"as_of": cutoff, "eligible_headers": len(events), "eligible_items": len(item_rows), "headers": events, "items": item_rows}
        counts = con.execute("SELECT count(*), count(DISTINCT accession), count(*) FILTER (WHERE fetch_status='not_fetched') FROM members").fetchone()
        if counts != (data["summary"]["members"], data["summary"]["unique_accessions"], data["summary"]["not_fetched"]):
            raise ValueError("native_materialization_count_mismatch")
        for name, raw in [("as-of.sql", (AS_OF_SQL + ";\n\n" + ITEM_AS_OF_SQL + ";\n").encode()),
                          ("queries.json", strict.json_bytes(results))]:
            strict.write_new(out / name, raw)
            outputs.append(digest_entry(name, raw))
        manifest = {"schema_version": 1, "stage": "parquet", "extraction_manifest_sha256": expected_manifest_hash,
                    "source_receipt": source_manifest["source_receipt"], "source_files": source_manifest["source_files"],
                    "parsers": source_manifest["parsers"], "materializer": {"duckdb_version": DUCKDB_VERSION, "bridge": bridge_identity()},
                    "files": outputs, "summary": data["summary"], "schema": TABLES,
                    "query_counts": {k: {f: v[f] for f in ["as_of", "eligible_headers", "eligible_items"]} for k, v in results.items()},
                    "historical_point_in_time": False, "limitations": LIMITATIONS}
        strict.write_new(out / "manifest.json", strict.json_bytes(manifest))
        return manifest
    finally:
        con.close()


def query(root, as_of, expected_manifest_hash=None):
    root = safe_path(root)
    strict.timestamp(as_of)
    raw = read_bytes(root / "manifest.json")
    if expected_manifest_hash is None or sha(raw) != expected_manifest_hash:
        raise ValueError("manifest_hash_mismatch")
    manifest = unique_json(raw)
    expected = {"members.parquet", "headers.parquet", "items.parquet", "as-of.sql", "queries.json"}
    if manifest["stage"] != "parquet" or len(manifest["files"]) != len(expected) or {x["path"] for x in manifest["files"]} != expected or {p.name for p in root.iterdir()} != expected | {"manifest.json"}:
        raise ValueError("unexpected_payload_set")
    for entry in manifest["files"]:
        verify_blob(root, entry)
    con = duckdb_connection()
    try:
        for name in TABLES:
            # Filename parameterized; identifiers are from the constant schema only.
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet(?)", [str(root / f"{name}.parquet")])
        return rows_json(con.execute(AS_OF_SQL, [as_of]))
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    a = commands.add_parser("extract")
    a.add_argument("--run", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--receipt-sha256", required=True)
    b = commands.add_parser("materialize")
    b.add_argument("--extraction", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--manifest-sha256", required=True)
    c = commands.add_parser("query")
    c.add_argument("--dataset", type=Path, required=True)
    c.add_argument("--as-of", required=True)
    c.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    if args.command == "extract":
        result = extract(args.run, args.out, args.receipt_sha256)
    elif args.command == "materialize":
        result = materialize(args.extraction, args.out, args.manifest_sha256)
    else:
        rows = query(args.dataset, args.as_of, args.manifest_sha256)
        print(json.dumps({"as_of": args.as_of, "eligible_count": len(rows), "headers": rows}, sort_keys=True))
        return
    print(json.dumps({"stage": result["stage"], "summary": result["summary"],
                      "manifest_sha256": sha(read_bytes(args.out / "manifest.json"))}, sort_keys=True))


if __name__ == "__main__":
    main()
