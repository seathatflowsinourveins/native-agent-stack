#!/usr/bin/env python3
"""Bounded official SEC snapshots, conservative availability, and cited packets.

This is a small local research recipe, not a historical point-in-time vendor feed
or a trading signal. Network acquisition and packet reads are separate commands.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

COMPANIES = {"AAPL": "0000320193", "MSFT": "0000789019"}
CONCEPTS = ("Assets", "Liabilities", "StockholdersEquity", "NetIncomeLoss")
MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 250000
MAX_PACKET_BYTES = 8192
SCHEMA = {
    "row_id": "VARCHAR", "symbol": "VARCHAR", "cik": "VARCHAR",
    "taxonomy": "VARCHAR", "concept": "VARCHAR", "unit": "VARCHAR",
    "value_text": "VARCHAR", "value_decimal": "DECIMAL(38,12)",
    "period_start": "VARCHAR", "period_end": "VARCHAR", "accession": "VARCHAR",
    "fiscal_year": "VARCHAR", "fiscal_period": "VARCHAR", "frame": "VARCHAR",
    "form": "VARCHAR", "filed": "VARCHAR", "is_amendment": "BOOLEAN",
    "acceptance_at": "TIMESTAMPTZ", "first_observed_at": "TIMESTAMPTZ",
    "available_at": "TIMESTAMPTZ", "status": "VARCHAR", "exclusion_reason": "VARCHAR",
    "filing_url": "VARCHAR", "companyfacts_sha256": "VARCHAR",
    "submissions_sha256": "VARCHAR", "fact_pointer": "VARCHAR",
}


class AcquisitionError(ValueError):
    """A bounded, safe error code; raw response bodies are never error messages."""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("timestamp_needs_explicit_timezone")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp_needs_explicit_timezone")
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("nonfinite_json_number")
    return json.loads(raw, parse_float=Decimal, parse_constant=invalid, object_pairs_hook=pairs)


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path, content):
    """Publish only complete bytes, with exclusive creation and no replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    pending = path.parent / (".pending-" + uuid.uuid4().hex)
    try:
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.link(pending, path)
        fsync_dir(path.parent)
    finally:
        pending.unlink(missing_ok=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise AcquisitionError("redirect_refused")


def validate_source_url(url):
    if not re.fullmatch(
        r"https://data\.sec\.gov/(?:submissions|api/xbrl/companyfacts)/CIK[0-9]{10}\.json", url
    ):
        raise AcquisitionError("source_url_not_allowlisted")


def fetch_json(url, user_agent, *, max_bytes=MAX_BYTES, timeout=20, opener=None):
    """One request, bounded bytes and socket time, no redirects or automatic retries."""
    validate_source_url(url)
    if not 10 <= len(user_agent) <= 300 or any(ord(c) < 32 or ord(c) > 126 for c in user_agent):
        raise AcquisitionError("invalid_declared_user_agent")
    if not ("https://" in user_agent or "@" in user_agent):
        raise AcquisitionError("user_agent_needs_honest_project_contact")
    if not 1 <= max_bytes <= MAX_BYTES or not 0 < timeout <= 30:
        raise AcquisitionError("invalid_network_bound")
    request = urllib.request.Request(url, headers={
        "User-Agent": user_agent, "Accept": "application/json", "Accept-Encoding": "identity",
    })
    open_request = opener or urllib.request.build_opener(NoRedirect()).open
    started = time.monotonic()
    try:
        with open_request(request, timeout=timeout) as response:
            if response.status != 200 or response.geturl() != url:
                raise AcquisitionError("unexpected_http_response")
            if "json" not in response.headers.get("Content-Type", "").lower():
                raise AcquisitionError("unexpected_content_type")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise AcquisitionError("unexpected_content_encoding")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or int(length) > max_bytes):
                raise AcquisitionError("response_length_outside_bound")
            chunks, received = [], 0
            while True:
                if time.monotonic() - started > timeout:
                    raise AcquisitionError("response_deadline_exceeded")
                chunk = response.read(min(65536, max_bytes + 1 - received))
                if not chunk:
                    break
                received += len(chunk)
                if received > max_bytes:
                    raise AcquisitionError("response_too_large")
                chunks.append(chunk)
            if time.monotonic() - started > timeout:
                raise AcquisitionError("response_deadline_exceeded")
            if length is not None and received != int(length):
                raise AcquisitionError("partial_response")
            raw = b"".join(chunks)
            if not isinstance(parse_json(raw), dict):
                raise AcquisitionError("json_object_required")
            return raw
    except urllib.error.HTTPError as error:
        raise AcquisitionError("http_" + str(error.code)) from None
    except AcquisitionError:
        raise
    except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as error:
        raise AcquisitionError("download_" + type(error).__name__) from None


def store_snapshot(root, kind, cik, raw, url, observed_at):
    validate_source_url(url)
    timestamp(observed_at)
    if kind not in {"companyfacts", "submissions"} or not re.fullmatch(r"[0-9]{10}", cik):
        raise AcquisitionError("invalid_snapshot_identity")
    data = parse_json(raw)
    if str(data.get("cik", "")).zfill(10) != cik:
        raise AcquisitionError("source_cik_mismatch")
    if (kind == "companyfacts" and not isinstance(data.get("facts"), dict)) or (
        kind == "submissions" and not isinstance(data.get("filings"), dict)
    ):
        raise AcquisitionError("source_schema_mismatch")
    sha = digest(raw)
    relative = Path("raw") / kind / cik / sha
    target = Path(root) / relative
    def existing():
        try:
            metadata = json.loads((target / "metadata.json").read_bytes())
            if digest((target / "source.json").read_bytes()) != sha or any([
                metadata["sha256"] != sha, metadata["url"] != url,
                metadata["relative_path"] != (relative / "source.json").as_posix(),
            ]):
                raise ValueError("mismatch")
            timestamp(metadata["first_observed_at"])
            return metadata
        except (OSError, ValueError, KeyError):
            raise AcquisitionError("existing_snapshot_integrity_failure") from None
    if target.exists():
        return existing()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    pending = target.parent / (".pending-" + uuid.uuid4().hex)
    pending.mkdir(mode=0o700)
    metadata = {"kind": kind, "cik": cik, "url": url, "sha256": sha, "bytes": len(raw),
                "first_observed_at": observed_at, "fetched_at": observed_at,
                "relative_path": (relative / "source.json").as_posix()}
    try:
        atomic_write(pending / "source.json", raw)
        atomic_write(pending / "metadata.json", json_bytes(metadata))
        try:
            os.rename(pending, target)
        except OSError:
            if target.exists():
                return existing()
            raise
        fsync_dir(target.parent)
        return metadata
    finally:
        if pending.exists():
            shutil.rmtree(pending)


def submission_index(data):
    recent = data.get("filings", {}).get("recent", {})
    keys = ("accessionNumber", "acceptanceDateTime", "filingDate", "form", "primaryDocument")
    if any(not isinstance(recent.get(key), list) for key in keys):
        raise AcquisitionError("submissions_columns_missing")
    if len({len(recent[key]) for key in keys}) != 1:
        raise AcquisitionError("submissions_columns_misaligned")
    entries = defaultdict(list)
    for values in zip(*(recent[key] for key in keys)):
        item = dict(zip(keys, values))
        entries[item["accessionNumber"]].append(item)
    return entries


def normalize_facts(symbol, cik, data, submissions, fact_source, submission_source):
    if str(data.get("cik", "")).zfill(10) != cik or str(submissions.get("cik", "")).zfill(10) != cik:
        raise AcquisitionError("normalization_cik_mismatch")
    index = submission_index(submissions)
    observed = iso(max(timestamp(fact_source["first_observed_at"]),
                       timestamp(submission_source["first_observed_at"])))
    rows = []
    for concept in CONCEPTS:
        units = data.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {})
        for unit in sorted(units):
            for number, fact in enumerate(units[unit]):
                if len(rows) >= MAX_ROWS:
                    raise AcquisitionError("normalized_row_bound_exceeded")
                row = dict.fromkeys(SCHEMA)
                row.update(symbol=symbol, cik=cik, taxonomy="us-gaap", concept=concept, unit=unit,
                           value_text=str(fact.get("val")), period_start=fact.get("start"),
                           period_end=fact.get("end"), accession=fact.get("accn"),
                           fiscal_year=str(fact.get("fy")), fiscal_period=fact.get("fp"),
                           frame=fact.get("frame"), form=fact.get("form"), filed=fact.get("filed"),
                           is_amendment=str(fact.get("form", "")).endswith("/A"),
                           first_observed_at=observed, companyfacts_sha256=fact_source["sha256"],
                           submissions_sha256=submission_source["sha256"],
                           fact_pointer=f"/facts/us-gaap/{concept}/units/{unit}/{number}",
                           status="excluded", exclusion_reason=None)
                reason = None
                try:
                    value = Decimal(row["value_text"])
                    # Fixed decimal storage never rounds a value into acceptance.
                    if not value.is_finite() or abs(value) >= Decimal(10) ** 26 or value.as_tuple().exponent < -12:
                        raise ValueError("numeric_bound")
                    row["value_decimal"] = str(value)
                except (InvalidOperation, ValueError):
                    reason = "invalid_or_unrepresentable_numeric"
                try:
                    end = date.fromisoformat(row["period_end"])
                    if row["period_start"] and date.fromisoformat(row["period_start"]) > end:
                        raise ValueError("reversed_period")
                    date.fromisoformat(row["filed"])
                except (TypeError, ValueError):
                    reason = reason or "invalid_period_or_filing_date"
                matches = index.get(row["accession"], [])
                distinct = {json_bytes(item) for item in matches}
                if not distinct:
                    reason = reason or "accession_not_in_recent_submissions"
                elif len(distinct) != 1:
                    reason = reason or "ambiguous_submission"
                else:
                    submission = matches[0]
                    if submission["form"] != row["form"] or submission["filingDate"] != row["filed"]:
                        reason = reason or "submission_mismatch"
                    try:
                        accepted = timestamp(submission["acceptanceDateTime"])
                        row["acceptance_at"] = iso(accepted)
                    except (TypeError, ValueError):
                        reason = reason or "missing_or_ambiguous_acceptance"
                    accession = row["accession"]
                    document = submission["primaryDocument"]
                    if (not isinstance(accession, str) or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession)
                            or not isinstance(document, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", document)):
                        reason = reason or "invalid_filing_link"
                    else:
                        row["filing_url"] = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                                             f"{accession.replace('-', '')}/{document}")
                if not reason:
                    row["available_at"] = iso(max(timestamp(row["acceptance_at"]), timestamp(observed)))
                    row["status"] = "available"
                row["exclusion_reason"] = reason
                row["row_id"] = digest(json_bytes({key: value for key, value in row.items() if key != "row_id"}))
                rows.append(row)
    return rows


def select_facts(rows, as_of, limit=8):
    cutoff = timestamp(as_of)
    if not 1 <= limit <= 8:
        raise ValueError("packet_fact_limit_must_be_1_to_8")
    counts = Counter()
    groups = defaultdict(list)
    for row in rows:
        if row["status"] != "available" or not row["available_at"]:
            counts["unavailable"] += 1
        elif timestamp(row["available_at"]) > cutoff:
            counts["after_cutoff"] += 1
        elif row["unit"] != "USD":
            counts["unit_mismatch"] += 1
        else:
            groups[(row["symbol"], row["concept"], row["unit"], row["period_start"], row["period_end"])].append(row)
    latest = []
    for values in groups.values():
        accepted = max(timestamp(row["acceptance_at"]) for row in values)
        candidates = [row for row in values if timestamp(row["acceptance_at"]) == accepted]
        if len({(row["accession"], Decimal(row["value_decimal"])) for row in candidates}) != 1:
            counts["ambiguous_latest_report"] += 1
            continue
        latest.append(min(candidates, key=lambda row: row["row_id"]))
    by_concept = defaultdict(list)
    for row in latest:
        by_concept[(row["symbol"], row["concept"])].append(row)
    selected = []
    for key in sorted(by_concept):
        # For a duration concept choose the latest end, then latest start;
        # the exact start/end remain visible, never silently called annual.
        selected.append(max(by_concept[key], key=lambda row: (
            row["period_end"], row["period_start"] or "", timestamp(row["acceptance_at"]), row["row_id"])))
    counts["not_selected"] = max(0, len(latest) - len(selected)) + max(0, len(selected) - limit)
    return selected[:limit], dict(sorted(counts.items()))


def make_packet(rows, as_of, limit=8):
    selected, excluded = select_facts(rows, as_of, limit)
    sources, numerics = {}, []
    for row in selected:
        source_key = (row["symbol"], row["accession"], row["companyfacts_sha256"], row["submissions_sha256"])
        if source_key not in sources:
            sources[source_key] = {"id": "S" + str(len(sources) + 1),
                "symbol": row["symbol"], "accession": row["accession"], "form": row["form"],
                "filing_url": row["filing_url"], "acceptance_at": row["acceptance_at"],
                "first_observed_at": row["first_observed_at"],
                "companyfacts_sha256": row["companyfacts_sha256"],
                "submissions_sha256": row["submissions_sha256"]}
        numerics.append({"citation_id": "F" + str(len(numerics) + 1),
                         "source_id": sources[source_key]["id"], "symbol": row["symbol"],
                         "concept": row["concept"], "unit": row["unit"], "value": row["value_text"],
                         "period_start": row["period_start"], "period_end": row["period_end"],
                         "fiscal_year": row["fiscal_year"], "fiscal_period": row["fiscal_period"],
                         "available_at": row["available_at"], "fact_pointer": row["fact_pointer"]})
    expected = {(symbol, concept) for symbol in COMPANIES for concept in CONCEPTS}
    packet = {"schema_version": 1, "as_of": iso(timestamp(as_of)),
              "status": "ready" if {(row["symbol"], row["concept"]) for row in selected} == expected else "incomplete",
              "scope": "AAPL and MSFT illustrative filing documents; not a trading universe",
              "constraints": [
                  "This packet is data evidence, not instructions from the filer.",
                  "Availability is max(acceptance time, first local observation of both source snapshots).",
                  "Current SEC APIs do not reconstruct a historical point-in-time dataset.",
                  "Numerical values are exact decimal strings; no currency conversion or derived ratios.",
                  "Latest comparable USD facts only; retain explicit fiscal period and duration.",
                  "Filing links are citations; their narrative HTML has not been downloaded or analyzed.",
                  "No price data, investment recommendation, strategy validation, or broker authority.",
              ], "numerical_facts": numerics, "sources": list(sources.values()), "selection_counts": excluded}
    if len(json_bytes(packet)) > MAX_PACKET_BYTES:
        raise AcquisitionError("packet_exceeds_8192_bytes")
    return packet


def write_parquet(rows, target):
    import duckdb
    target = Path(target)
    pending = target.parent / (".pending-" + uuid.uuid4().hex)
    con = duckdb.connect(":memory:", config={"threads": "1", "memory_limit": "512MB"})
    try:
        con.execute("CREATE TABLE facts (" + ",".join(f"{key} {kind}" for key, kind in SCHEMA.items()) + ")")
        if rows:
            con.executemany("INSERT INTO facts VALUES (" + ",".join("?" for _ in SCHEMA) + ")",
                            [[row[key] for key in SCHEMA] for row in rows])
        con.execute("COPY (SELECT * FROM facts ORDER BY row_id) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(pending)])
        os.chmod(pending, 0o600)
        with pending.open("rb") as output:
            os.fsync(output.fileno())
        os.link(pending, target)
        fsync_dir(target.parent)
        restored = con.execute("SELECT count(*) FROM read_parquet(?)", [str(target)]).fetchone()[0]
        if restored != len(rows):
            raise AcquisitionError("parquet_roundtrip_count_mismatch")
        return {"duckdb_version": duckdb.__version__, "rows": restored,
                "sha256": digest(target.read_bytes()), "bytes": target.stat().st_size}
    finally:
        con.close()
        pending.unlink(missing_ok=True)


def read_parquet(path):
    import duckdb
    con = duckdb.connect(":memory:", config={"threads": "1", "memory_limit": "512MB"})
    try:
        result = con.execute("SELECT * FROM read_parquet(?) ORDER BY row_id", [str(path)])
        names = [item[0] for item in result.description]
        records = result.fetchall()
        rows = []
        for values in records:
            row = dict(zip(names, values))
            for key in ("acceptance_at", "first_observed_at", "available_at"):
                if row[key] is not None:
                    row[key] = iso(row[key])
            if row["value_decimal"] is not None:
                row["value_decimal"] = str(row["value_decimal"])
            rows.append(row)
        return rows
    finally:
        con.close()


def acquire(root, run_id, user_agent):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", run_id):
        raise AcquisitionError("invalid_run_id")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / ".acquire.lock").open("a") as lock:
        os.chmod(root / ".acquire.lock", 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        target = root / "acquisitions" / run_id
        target.mkdir(parents=True, exist_ok=False, mode=0o700)
        receipt = {"schema_version": 1, "kind": "official_sec_acquisition",
                   "started_at": utc_now(), "status": "failed", "requests": [],
                   "request_limit_per_second": 2, "response_limit_bytes": MAX_BYTES,
                   "per_request_timeout_seconds": 20, "automatic_retries": 0,
                   "user_agent_sha256": digest(user_agent.encode()),
                   "selection": {"illustrative_symbols": list(COMPANIES), "concepts": list(CONCEPTS)},
                   "availability_policy": "max(acceptance_at, first_observed_at of both source snapshots)",
                   "historical_point_in_time_reconstruction": False}
        rows, previous_start = [], 0.0
        try:
            for symbol, cik in COMPANIES.items():
                sources = {}
                for kind, prefix in (("submissions", "submissions"), ("companyfacts", "api/xbrl/companyfacts")):
                    time.sleep(max(0, 0.5 - (time.monotonic() - previous_start)))
                    previous_start = time.monotonic()
                    url = f"https://data.sec.gov/{prefix}/CIK{cik}.json"
                    request_record = {"symbol": symbol, "kind": kind, "url": url, "started_at": utc_now()}
                    receipt["requests"].append(request_record)
                    try:
                        raw = fetch_json(url, user_agent)
                        finished = utc_now()
                        metadata = store_snapshot(root, kind, cik, raw, url, finished)
                        request_record.update(status="completed", http_status=200, fetched_at=finished,
                                              first_observed_at=metadata["first_observed_at"],
                                              sha256=metadata["sha256"], bytes=len(raw))
                        sources[kind] = (parse_json(raw), metadata)
                    except AcquisitionError as error:
                        request_record.update(status="failed", error_code=str(error), finished_at=utc_now())
                        raise
                rows.extend(normalize_facts(symbol, cik, sources["companyfacts"][0], sources["submissions"][0],
                                            sources["companyfacts"][1], sources["submissions"][1]))
            artifact = write_parquet(rows, target / "facts.parquet")
            receipt.update(status="completed", artifact={"name": "facts.parquet", **artifact},
                           row_status_counts=dict(Counter(row["status"] for row in rows)),
                           exclusion_counts=dict(Counter(row["exclusion_reason"] for row in rows if row["exclusion_reason"])),
                           as_of=utc_now())
        except Exception as error:
            receipt["error_code"] = str(error) if isinstance(error, AcquisitionError) else type(error).__name__
        receipt["finished_at"] = utc_now()
        atomic_write(target / "receipt.json", json_bytes(receipt))
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("acquire", help="four official SEC requests; new immutable run directory")
    fetch.add_argument("--root", type=Path, required=True)
    fetch.add_argument("--run-id", required=True)
    fetch.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT"))
    packet = sub.add_parser("packet", help="offline exact-decimal cited packet, at most 8192 bytes")
    packet.add_argument("--run", type=Path, required=True)
    packet.add_argument("--as-of", required=True)
    packet.add_argument("--out", type=Path, required=True)
    packet.add_argument("--text-out", type=Path)
    packet.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    if args.command == "acquire":
        if not args.user_agent:
            parser.error("--user-agent or SEC_USER_AGENT must identify the real project and contact")
        receipt = acquire(args.root, args.run_id, args.user_agent)
        print(json.dumps(receipt, sort_keys=True))
        return 0 if receipt["status"] == "completed" else 1
    receipt = json.loads((args.run / "receipt.json").read_bytes())
    if receipt["status"] != "completed":
        raise AcquisitionError("acquisition_not_completed")
    artifact = args.run / "facts.parquet"
    if digest(artifact.read_bytes()) != receipt["artifact"]["sha256"]:
        raise AcquisitionError("parquet_integrity_failure")
    result = make_packet(read_parquet(artifact), args.as_of, args.limit)
    raw = json_bytes(result)
    text = ("# SEC research evidence packet\n\nReview the evidence below. Cite source IDs for claims; "
            "keep calculations in deterministic code. Describe provenance and temporal limitations, "
            "and identify missing evidence. Do not provide orders or a performance claim.\n\n```json\n" +
            raw.decode().rstrip() + "\n```\n").encode()
    if args.text_out and len(text) > MAX_PACKET_BYTES:
        raise AcquisitionError("text_packet_exceeds_8192_bytes")
    atomic_write(args.out, raw)
    if args.text_out:
        atomic_write(args.text_out, text)
    print(json.dumps({"status": result["status"], "as_of": result["as_of"],
                      "facts": len(result["numerical_facts"]), "sources": len(result["sources"]),
                      "packet_bytes": len(raw), "packet_sha256": digest(raw),
                      "text_bytes": len(text) if args.text_out else None}))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AcquisitionError, FileExistsError, BlockingIOError) as error:
        print(json.dumps({"status": "failed", "error_code": str(error) if isinstance(error, AcquisitionError)
                          else type(error).__name__}))
        raise SystemExit(1)
