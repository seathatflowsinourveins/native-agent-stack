#!/usr/bin/env python3
"""Offline native document parsing and DuckDB proof for six fixed lifecycle sources."""
import argparse
import importlib.metadata
import importlib.util
import inspect
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "alpaca-historical/collect.py"
SPEC = importlib.util.spec_from_file_location("lifecycle_bytes", BASE)
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)
CONTRACT = "bounded-lifecycle-source-v1"
PLAN_SHA = "1324845825796e32b46d502884bf036e6b9211ca9976b7e9684dfda5b9b7f72b"
POLICY = {
    "meta_release": ("meta_rename", "Meta Platforms Class A common stock", "symbol_change", "FB", "META", "2022-06-09", "prior_to_market_open", "May 31, 2022", ["Class A common stock", "June 9, 2022", "May 31, 2022", "CUSIP number will remain unchanged", "'FB'", "'META'", "prior to market open"]),
    "roundhill_release": ("roundhill_rename", "Roundhill Ball Metaverse ETF shares", "symbol_change", "META", "METV", "2022-01-31", "start_of_trading", "Jan 14, 2022, 16:30 ET", ["Roundhill Ball Metaverse ETF", '"META" to "METV"', "January 31, 2022", "Jan 14, 2022, 16:30 ET", "start of trading"]),
    "twtr_8k_sgml": ("twitter_suspension", "Twitter common stock on NYSE", "exchange_trading_suspension", "TWTR", None, "2022-10-28", "prior_to_exchange_open", None, ["Twitter", "NYSE", "suspended prior to the opening", "October 28, 2022"]),
}


def plan():
    raw = B.read(HERE / "plan.json")
    if B.sha(raw) != PLAN_SHA:
        raise ValueError("frozen_plan_changed")
    return B.strict_json(raw)


def normalize(text):
    return " ".join(text.replace("\u201c", '"').replace("\u201d", '"').split())


def claim(source_id, text, observed_ns, source_sha256):
    case, scope, kind, before, after, day, timing, publication, markers = POLICY[source_id]
    supported = all(normalize(x).casefold() in normalize(text).casefold() for x in markers)
    return {"case_id": case, "documentary_security_scope": scope, "event_kind": kind,
            "symbol_before": before, "symbol_after": after, "effective_date": day if supported else None,
            "effective_timing": timing if supported else None, "publisher_claimed_publication": publication if supported else None,
            "sec_acceptance_raw": None, "sec_acceptance_zone": None, "sec_filing_date_raw": None,
            "status": "supported_documentary_claim" if supported else "unresolved_missing_document_witness",
            "source_id": source_id, "source_sha256": source_sha256, "observed_ns": observed_ns,
            "available_ns": observed_ns, "original_publication_ns": None, "permanent_security_id": None,
            "valid_from_ns": None, "valid_to_ns": None, "provider_revision_ns": None,
            "legal_delisting_effective_ns": None, "historical_universe_eligible": False}


def verify_entry(root, entry):
    name = entry["path"]
    if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("unsafe_artifact_path")
    raw = B.read(root / name)
    if B.digest(name, raw) != entry:
        raise ValueError("artifact_hash_mismatch")
    return raw


def exact_files(root, expected):
    actual = set()
    for path in root.rglob("*"):
        B.safe_path(path)
        if path.is_file():
            actual.add(str(path.relative_to(root)))
        elif path.is_dir() and not any(name.startswith(str(path.relative_to(root)) + "/") for name in expected):
            raise ValueError("unexpected_directory")
    if actual != set(expected):
        raise ValueError("unexpected_artifact_set")


def capture(root, anchor):
    root = B.safe_path(root)
    raw = B.read(root / "manifest.json")
    if B.sha(raw) != anchor:
        raise ValueError("capture_anchor_mismatch")
    data = B.strict_json(raw)
    if data.get("schema_version") != 1 or data.get("kind") != "lifecycle-source-capture-v1" or type(data.get("synthetic")) is not bool:
        raise ValueError("unsupported_capture")
    if verify_entry(root, data["plan"]) != B.read(HERE / "plan.json"):
        raise ValueError("capture_plan_mismatch")
    specs = plan()["sources"]
    if [s["source_id"] for s in data["sources"]] != [s["source_id"] for s in specs]:
        raise ValueError("source_scope_mismatch")
    freeze = B.strict_json(verify_entry(root, data["freeze"]))
    if data["freeze"]["path"] != "freeze.json" or freeze["plan_sha256"] != PLAN_SHA or freeze["transport"] != data["transport"]:
        raise ValueError("capture_freeze_mismatch")
    transport = data["transport"]
    if transport.get("library") != "requests" or transport.get("version") != "2.34.2" or transport.get("automatic_retries") != 0 or transport.get("environment_proxy_and_netrc") is not False:
        raise ValueError("unsupported_capture_transport")
    for digest in [*transport["sources"], transport["capture_code"], transport["shared_helper"]]:
        if not re.fullmatch("[a-f0-9]{64}", digest.get("sha256", "")) or type(digest.get("bytes")) is not int or digest["bytes"] < 1:
            raise ValueError("invalid_transport_identity")
    if len(transport["sources"]) != 3 or transport["shared_helper"]["sha256"] != B.sha(B.read(BASE)):
        raise ValueError("capture_helper_mismatch")
    files = {"manifest.json", "plan.json", "freeze.json"}
    refused = set()
    previous = B.timestamp_ns(freeze["frozen_at"])
    attempts = 0
    for source, spec in zip(data["sources"], specs):
        if source["url"] != spec["url"] or source["body"]["path"] != source["source_id"] + ".body":
            raise ValueError("source_url_or_body_mismatch")
        body = verify_entry(root, source["body"])
        files.add(source["body"]["path"])
        meta = source["meta"]
        if meta["path"] != source["source_id"] + ".meta.json" or B.strict_json(verify_entry(root, meta)) != {k: v for k, v in source.items() if k != "meta"}:
            raise ValueError("source_metadata_mismatch")
        files.add(meta["path"])
        start, observed = B.timestamp_ns(source["started_at"]), B.timestamp_ns(source["observed_at"])
        if start > observed or (previous is not None and start < previous):
            raise ValueError("invalid_observation_order")
        previous = observed
        if type(source["body_complete"]) is not bool or (source["status"] is not None and (type(source["status"]) is not int or not 100 <= source["status"] <= 599)):
            raise ValueError("invalid_response_metadata")
        origin = urlsplit(spec["url"]).netloc
        skipped = source["transport_error"] == "skipped_origin_access_refusal"
        if skipped != (origin in refused):
            raise ValueError("origin_refusal_policy_mismatch")
        if skipped:
            if body or source["status"] is not None or source["actual_request"] is not None or source["body_complete"]:
                raise ValueError("invalid_skipped_source")
        else:
            attempts += 1
            if source["actual_request"] != {"method": "GET", "url": spec["url"]}:
                if source["actual_request"] is not None or source["status"] is not None or source["body_complete"] or not source["transport_error"]:
                    raise ValueError("wire_request_mismatch")
        if source["status"] in {401, 403, 429}:
            refused.add(origin)
    if type(data["http_attempts"]) is not int or data["http_attempts"] != attempts or attempts > 6:
        raise ValueError("attempt_count_mismatch")
    exact_files(root, files)
    return data


def native_identity():
    if importlib.metadata.version("edgartools") != "5.58.0":
        raise ValueError("edgartools_version_mismatch")
    from edgar.documents import HTMLParser
    from edgar.sgml import FilingSGML, FilingHeader
    from edgar.sgml import sgml_parser
    paths = sorted({Path(inspect.getfile(x)) for x in [HTMLParser, FilingSGML, FilingHeader, sgml_parser]})
    return {"kind": "native", "edgartools": "5.58.0", "sources": [B.digest("edgar/" + str(p).split("/edgar/", 1)[1], B.read(p)) for p in paths]}


def native_parse(source_id, raw):
    from edgar.documents import HTMLParser
    from edgar.sgml import FilingSGML
    metadata = {"acceptance_raw": None, "acceptance_zone": None, "acceptance_utc_ns": None,
                "filing_date_raw": None, "form": None, "accession": None}
    if source_id.endswith("_sgml"):
        submission = FilingSGML.from_text(raw.decode("utf-8"))
        expected = {"twtr_8k_sgml": ("8-K", "0001193125-22-272772"), "twtr_25_sgml": ("25-NSE", "0000876661-22-000890")}[source_id]
        if (submission.form, submission.accession_number) != expected:
            raise ValueError("unexpected_submission_identity")
        accepted = submission.header.acceptance_datetime
        metadata.update(form=submission.form, accession=submission.accession_number,
                        filing_date_raw=submission.filing_date,
                        acceptance_raw=accepted.isoformat(sep=" ") if accepted is not None else None)
        primary = submission.get_document_by_sequence("1")
        if primary is None:
            raise ValueError("missing_primary_document")
        raw = primary.content.encode("utf-8")
    text = HTMLParser().parse(raw).to_markdown()
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty_native_text")
    return {"text": text, "metadata": metadata}


def source_assessment(source, parsed):
    if source["status"] != 200 or not source["body_complete"] or source["transport_error"]:
        return "source_unavailable"
    return "parsed" if parsed.get("text") is not None else "native_parse_failed"


def make_claims(sources, parsed):
    rows = []
    for source in sources:
        name = source["source_id"]
        if name in POLICY:
            text = parsed[name].get("text", "") if source_assessment(source, parsed[name]) == "parsed" else ""
            row = claim(name, text, B.timestamp_ns(source["observed_at"]), source["body"]["sha256"])
            metadata = parsed[name].get("metadata", {})
            row.update(sec_acceptance_raw=metadata.get("acceptance_raw"), sec_acceptance_zone=metadata.get("acceptance_zone"),
                       sec_filing_date_raw=metadata.get("filing_date_raw"))
            if row["sec_acceptance_zone"] is not None or metadata.get("acceptance_utc_ns") is not None:
                raise ValueError("unsupported_acceptance_timezone_inference")
            rows.append(row)
    return rows


def relationships(rows):
    supported = {r["case_id"] for r in rows if r["status"] == "supported_documentary_claim"}
    reuse = {"meta_rename", "roundhill_rename"} <= supported
    return {"distinct_documentary_scopes": len({r["documentary_security_scope"] for r in rows}),
            "documented_meta_ticker_reuse": reuse,
            "reconstructed_order": "Roundhill META-to-METV claim precedes Meta FB-to-META claim" if reuse else None,
            "continuous_symbol_ownership_intervals_established": False,
            "permanent_identity_crosswalk_established": False,
            "quarantined_bar_origin_established": False}


def new_dir(out):
    out = B.safe_path(out)
    if out.exists():
        raise FileExistsError("output_directory_exists")
    if any((p / ".git").exists() for p in [out, *out.parents]):
        raise ValueError("private_output_must_be_outside_git")
    out.mkdir(mode=0o700, parents=True)
    return out


def copy_tree(source, out):
    for p in sorted(source.rglob("*")):
        B.safe_path(p)
        target = out / p.relative_to(source)
        if p.is_dir():
            target.mkdir(mode=0o700)
        else:
            B.write_new(target, B.read(p))


def code_files():
    return {"sample.py": Path(__file__), "base-collector.py": BASE, "select.sql": HERE / "select.sql", "plan.json": HERE / "plan.json"}


def finish(out, data):
    data["files"] = [B.digest(str(p.relative_to(out)), B.read(p)) for p in sorted(out.rglob("*")) if p.is_file()]
    B.write_new(out / "receipt.json", B.encode(data))
    return B.sha(B.read(out / "receipt.json"))


def qualify(source, anchor, out, parser=None):
    source = B.safe_path(source)
    data = capture(source, anchor)
    if parser is not None and not data["synthetic"]:
        raise ValueError("injected_parser_requires_synthetic_capture")
    identity = {"kind": "injected_test"} if parser is not None else native_identity()
    parser = parser or native_parse
    out = new_dir(out)
    (out / "capture").mkdir(mode=0o700)
    copy_tree(source, out / "capture")
    data = capture(out / "capture", anchor)
    for name, path in code_files().items():
        B.write_new(out / name, B.read(path))
    B.write_new(out / "freeze.json", B.encode({"parser": identity, "capture_sha256": anchor, "plan_sha256": PLAN_SHA}))
    parsed = {}
    for s in data["sources"]:
        name = s["source_id"]
        result = {"error": "source_unavailable"}
        if s["status"] == 200 and s["body_complete"] and not s["transport_error"]:
            try:
                result = parser(name, B.read(out / "capture" / s["body"]["path"]))
            except Exception:
                result = {"error": "native_parse_failed"}
        parsed[name] = result
    B.write_new(out / "parsed.json", B.encode(parsed))
    rows = make_claims(data["sources"], parsed)
    B.write_new(out / "claims.json", B.encode(rows))
    result = {"kind": "lifecycle-qualified-v1", "synthetic": data["synthetic"], "capture_sha256": anchor,
              "parser": identity, "source_statuses": {s["source_id"]: source_assessment(s, parsed[s["source_id"]]) for s in data["sources"]},
              "claim_count": len(rows), "supported_claims": sum(r["status"] == "supported_documentary_claim" for r in rows),
              "relationships": relationships(rows),
              "historical_universe_eligible": False, "provider_revision_availability_established": False}
    return {"receipt_sha256": finish(out, result), **result}


def verify_receipt(root, anchor, kind):
    root = B.safe_path(root)
    raw = B.read(root / "receipt.json")
    if B.sha(raw) != anchor:
        raise ValueError("receipt_anchor_mismatch")
    data = B.strict_json(raw)
    if data["kind"] != kind:
        raise ValueError("receipt_kind_mismatch")
    files = {}
    for entry in data["files"]:
        if entry["path"] in files:
            raise ValueError("duplicate_artifact")
        files[entry["path"]] = verify_entry(root, entry)
    exact_files(root, {"receipt.json", *files})
    for name, path in code_files().items():
        if files.get(name) != B.read(path):
            raise ValueError("bridge_or_sql_version_mismatch")
    return data, files


def verify(root, anchor, reparse=False):
    root = B.safe_path(root)
    result, files = verify_receipt(root, anchor, "lifecycle-qualified-v1")
    expected = {*code_files(), "freeze.json", "parsed.json", "claims.json"}
    if {n for n in files if not n.startswith("capture/")} != expected:
        raise ValueError("unexpected_qualified_payload")
    data = capture(root / "capture", result["capture_sha256"])
    freeze = B.strict_json(files["freeze.json"])
    if freeze != {"parser": result["parser"], "capture_sha256": result["capture_sha256"], "plan_sha256": PLAN_SHA} or data["synthetic"] != result["synthetic"]:
        raise ValueError("freeze_mismatch")
    identity = result["parser"]
    if identity.get("kind") == "injected_test":
        if not result["synthetic"]:
            raise ValueError("native_identity_missing")
    elif identity.get("kind") != "native" or identity.get("edgartools") != "5.58.0" or len(identity.get("sources", [])) != 4:
        raise ValueError("invalid_parser_identity")
    parsed = B.strict_json(files["parsed.json"])
    if set(parsed) != {s["source_id"] for s in data["sources"]}:
        raise ValueError("parsed_source_scope_mismatch")
    if reparse:
        if identity != native_identity():
            raise ValueError("parser_runtime_changed")
        for source in data["sources"]:
            if source_assessment(source, parsed[source["source_id"]]) == "source_unavailable":
                continue
            try:
                observed = native_parse(source["source_id"], B.read(root / "capture" / source["body"]["path"]))
            except Exception:
                observed = {"error": "native_parse_failed"}
            if observed != parsed[source["source_id"]]:
                raise ValueError("native_reparse_mismatch")
    rows = make_claims(data["sources"], parsed)
    statuses = {s["source_id"]: source_assessment(s, parsed[s["source_id"]]) for s in data["sources"]}
    if B.strict_json(files["claims.json"]) != rows or result["source_statuses"] != statuses or result["claim_count"] != len(rows) or result["supported_claims"] != sum(r["status"] == "supported_documentary_claim" for r in rows) or result["relationships"] != relationships(rows):
        raise ValueError("claim_derivation_mismatch")
    if result["historical_universe_eligible"] is not False or result["provider_revision_availability_established"] is not False:
        raise ValueError("unsupported_eligibility_claim")
    return result, rows


def connection():
    if importlib.metadata.version("duckdb") != "1.5.5":
        raise ValueError("duckdb_version_mismatch")
    import duckdb
    return duckdb.connect(":memory:", config={"threads": "1"})


def selection(con, sql, cutoff):
    if type(cutoff) is not int or not -(2**63) < cutoff < 2**63:
        raise ValueError("invalid_nanosecond_cutoff")
    result = con.execute(sql, [cutoff]).fetchall()
    return {"cutoff_ns": str(cutoff), "eligible_documentary_claims": len(result),
            "selection_sha256": B.sha(B.encode(result)), "historical_universe_eligible": False}


def proofs(con, sql, rows):
    times = [r["observed_ns"] for r in rows]
    cutoffs = [("historical", B.timestamp_ns("2022-12-31T23:59:59.999999999Z")),
               ("before_first_observation", min(times)-1), ("at_first_observation", min(times)),
               ("at_last_observation", max(times)), ("historical_replay", B.timestamp_ns("2022-12-31T23:59:59.999999999Z"))]
    return {name: selection(con, sql, cutoff) for name, cutoff in cutoffs}


def materialize(source, anchor, out):
    source = B.safe_path(source)
    verify(source, anchor)
    out = new_dir(out)
    (out / "qualified").mkdir(mode=0o700)
    copy_tree(source, out / "qualified")
    result, rows = verify(out / "qualified", anchor)
    for name, path in code_files().items():
        B.write_new(out / name, B.read(path))
    sql = B.read(HERE / "select.sql").decode()
    with connection() as con:
        columns = list(rows[0])
        schema = ",".join(k + (" BIGINT" if k.endswith("_ns") else " BOOLEAN" if k == "historical_universe_eligible" else " VARCHAR") for k in columns)
        con.execute("CREATE TABLE claims (" + schema + ")")
        con.executemany("INSERT INTO claims VALUES (" + ",".join("?" for _ in columns) + ")", [[r[k] for k in columns] for r in rows])
        con.execute("COPY (SELECT * FROM claims ORDER BY case_id) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(out / "claims.parquet")])
        (out / "claims.parquet").chmod(0o600)
        proof = proofs(con, sql, rows)
    receipt = {"kind": "lifecycle-ledger-v1", "qualified_receipt_sha256": anchor,
               "duckdb": "1.5.5", "synthetic": result["synthetic"], "proof": proof,
               "source_statuses": result["source_statuses"], "supported_claims": result["supported_claims"],
               "historical_universe_eligible": False}
    return {"receipt_sha256": finish(out, receipt), **receipt}


def verify_ledger(root, anchor):
    root = B.safe_path(root)
    data, files = verify_receipt(root, anchor, "lifecycle-ledger-v1")
    if {n for n in files if not n.startswith("qualified/")} != {*code_files(), "claims.parquet"}:
        raise ValueError("unexpected_ledger_payload")
    # Stage verified bytes before native SQL, avoiding a mutable input path.
    with tempfile.TemporaryDirectory(prefix="lifecycle-verified-") as temp:
        staged = Path(temp)
        for name, raw in files.items():
            (staged / name).parent.mkdir(parents=True, exist_ok=True)
            B.write_new(staged / name, raw)
        qualified, rows = verify(staged / "qualified", data["qualified_receipt_sha256"])
        with connection() as con:
            con.read_parquet(str(staged / "claims.parquet")).create_view("claims")
            cursor = con.execute("SELECT * FROM claims ORDER BY case_id")
            names = [d[0] for d in cursor.description]
            actual = [dict(zip(names, row)) for row in cursor.fetchall()]
            if sorted(B.encode(r) for r in actual) != sorted(B.encode(r) for r in rows):
                raise ValueError("materialized_source_mismatch")
            proof = proofs(con, files["select.sql"].decode(), rows)
    if data["proof"] != proof or data["source_statuses"] != qualified["source_statuses"] or data["supported_claims"] != qualified["supported_claims"] or data["synthetic"] != qualified["synthetic"] or data["duckdb"] != "1.5.5" or data["historical_universe_eligible"] is not False:
        raise ValueError("ledger_summary_mismatch")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["qualify", "verify", "materialize", "verify-ledger"])
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--reparse", action="store_true")
    args = parser.parse_args()
    if args.command in {"qualify", "materialize"}:
        if args.out is None:
            parser.error("new output directory required")
        result = globals()[args.command](args.source, args.receipt_sha256, args.out)
    elif args.command == "verify":
        result = verify(args.source, args.receipt_sha256, args.reparse)[0]
    else:
        result = verify_ledger(args.source, args.receipt_sha256)
    print(json.dumps({k: v for k, v in result.items() if k not in {"files", "parser"}}, sort_keys=True))


if __name__ == "__main__":
    main()
