#!/usr/bin/env python3
"""Bounded SEC provenance acceptance; no historical strategy or broker execution."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

DAY = "2020-03-02"
INDEX_URL = "https://www.sec.gov/Archives/edgar/daily-index/2020/QTR1/master.20200302.idx"
FORMS = {"8-K", "8-K/A"}
MAX_INDEX = 5 * 1024 * 1024
MAX_HEADER = 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone_required")
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, raw):
    # Exclusive creation also preserves an interrupted run for inspection.
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def parse_index(raw, day):
    day = date.fromisoformat(day).isoformat()
    lines = raw.decode("utf-8").splitlines()
    headers = {"CIK|Company Name|Form Type|Date Filed|Filename",
               "CIK|Company Name|Form Type|Date Filed|File Name"}
    header_index = next((i for i, line in enumerate(lines) if line in headers), None)
    if header_index is None:
        raise ValueError("missing_master_index_header")
    rows, seen = [], set()
    for line in lines[header_index + 1:]:
        if not line.strip() or set(line.strip()) == {"-"}:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            raise ValueError("malformed_master_index_row")
        cik, company, form, filed, path = parts
        if re.fullmatch(r"[0-9]{8}", filed):
            filed = f"{filed[:4]}-{filed[4:6]}-{filed[6:]}"
        elif not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", filed):
            raise ValueError("invalid_index_date")
        date.fromisoformat(filed)
        match = re.fullmatch(r"edgar/data/([0-9]+)/([0-9]{10}-[0-9]{2}-[0-9]{6})\.txt", path)
        if not cik.isdigit() or not match or int(cik) != int(match[1]):
            raise ValueError("index_identity_or_day_mismatch")
        # Other forms can be older correspondence or repeated ownership entries.
        # Day and duplicate membership checks apply to the declared catalyst cohort.
        if form not in FORMS:
            continue
        if filed != day:
            raise ValueError("index_identity_or_day_mismatch")
        accession = match[2]
        identity = (int(cik), accession)
        if identity in seen:
            raise ValueError("duplicate_accession")
        seen.add(identity)
        rows.append({"cik": int(cik), "company": company, "form": form,
                     "filed_date": filed, "accession": accession,
                     "header_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}.hdr.sgml"})
    return sorted(rows, key=lambda row: (row["cik"], row["accession"]))


def acceptance_time(value):
    if not re.fullmatch(r"[0-9]{14}", value):
        raise ValueError("invalid_acceptance_time")
    naive = datetime.strptime(value, "%Y%m%d%H%M%S")
    eastern = ZoneInfo("America/New_York")
    first, second = naive.replace(tzinfo=eastern, fold=0), naive.replace(tzinfo=eastern, fold=1)
    if first.utcoffset() != second.utcoffset() or first.astimezone(timezone.utc).astimezone(eastern).replace(tzinfo=None) != naive:
        raise ValueError("ambiguous_or_nonexistent_acceptance_time")
    return first.astimezone(timezone.utc)


def parse_header(raw, member, observed):
    result = {**member, "first_observed_at": observed, "accepted_at": None,
              "available_at": None, "status": "quarantined", "acceptance_raw": None}
    try:
        text = raw.decode("utf-8")
        def field(pattern):
            matches = re.findall(pattern, text, flags=re.MULTILINE)
            if len(matches) != 1:
                raise ValueError("missing_or_duplicate_header_field")
            return matches[0].strip()
        accession = field(r"^(?:ACCESSION NUMBER:\s*|<ACCESSION-NUMBER>)([^\r\n<]+)")
        form = field(r"^(?:CONFORMED SUBMISSION TYPE:\s*|<CONFORMED-SUBMISSION-TYPE>)([^\r\n<]+)")
        filed = field(r"^(?:FILED AS OF DATE:\s*|<FILING-DATE>)([0-9]{8})")
        value = field(r"^<ACCEPTANCE-DATETIME>([^\r\n<]+)")
        result["acceptance_raw"] = value
        if accession != member["accession"] or form != member["form"] or filed != member["filed_date"].replace("-", ""):
            raise ValueError("header_identity_mismatch")
        accepted = acceptance_time(value)
        result.update(accepted_at=iso(accepted), available_at=iso(max(accepted, timestamp(observed))), status="qualified")
    except (ValueError, UnicodeError) as exc:
        result["exclusion_reason"] = str(exc) if isinstance(exc, ValueError) else "header_decode_failed"
    return result


def eligible_at(event, as_of):
    return event.get("status") == "qualified" and event.get("available_at") is not None and timestamp(event["available_at"]) <= timestamp(as_of)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise ValueError("redirect_refused")


def fetch(url, identity, limit):
    if url != INDEX_URL and not re.fullmatch(r"https://www\.sec\.gov/Archives/edgar/data/[0-9]+/[0-9]{18}/[0-9]{10}-[0-9]{2}-[0-9]{6}\.hdr\.sgml", url):
        raise ValueError("source_url_not_allowlisted")
    if not 10 <= len(identity) <= 300 or any(ord(c) < 32 or ord(c) > 126 for c in identity) or not ("@" in identity or "https://" in identity):
        raise ValueError("truthful_declared_contact_required")
    request = urllib.request.Request(url, headers={"User-Agent": identity, "Accept-Encoding": "identity"})
    start = time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            if response.status != 200 or response.geturl() != url or response.headers.get("Content-Encoding", "identity") != "identity":
                raise ValueError("unexpected_http_response")
            chunks, size = [], 0
            while True:
                if time.monotonic() - start > 20:
                    raise ValueError("response_deadline")
                part = response.read(min(65536, limit + 1 - size))
                if not part:
                    break
                chunks.append(part)
                size += len(part)
                if size > limit:
                    raise ValueError("response_too_large")
            raw = b"".join(chunks)
            if response.headers.get("Content-Length") and int(response.headers["Content-Length"]) != len(raw):
                raise ValueError("incomplete_response")
            return raw
    except urllib.error.HTTPError as exc:
        raise ValueError(f"http_{exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError("network_error") from None


def acquire(root, run_id, identity, member_limit=5):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", run_id) or not 1 <= member_limit <= 5:
        raise ValueError("invalid_acquisition_bounds")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    run = root / run_id
    run.mkdir(mode=0o700)
    receipt = {"schema_version": 1, "status": "failed", "started_at": now(), "day": DAY,
               "index_url": INDEX_URL, "member_limit": member_limit, "request_count": 0,
               "automatic_retries": 0, "files": [], "selected": [], "cohort_count": None,
               "identity_sha256": sha(identity.encode()), "historical_point_in_time": False}
    current = None
    try:
        receipt["request_count"] += 1
        raw = fetch(INDEX_URL, identity, MAX_INDEX)
        observed = now()
        write_new(run / "index.idx", raw)
        receipt["files"].append({"path": "index.idx", "sha256": sha(raw), "bytes": len(raw), "first_observed_at": observed})
        cohort = parse_index(raw, DAY)
        receipt["cohort_count"] = len(cohort)
        receipt["selected"] = [{**row, "acquisition_status": "not_requested"} for row in cohort[:member_limit]]
        for current in receipt["selected"]:
            time.sleep(0.5)
            receipt["request_count"] += 1
            raw = fetch(current["header_url"], identity, MAX_HEADER)
            observed = now()
            name = f"{current['cik']}-{current['accession']}.hdr.sgml"
            write_new(run / name, raw)
            receipt["files"].append({"path": name, "sha256": sha(raw), "bytes": len(raw), "first_observed_at": observed})
            current.update(acquisition_status="complete", event=parse_header(raw, current, observed))
        receipt["status"] = "complete"
    except (ValueError, OSError) as exc:
        receipt["error_code"] = str(exc) if isinstance(exc, ValueError) else "local_io_error"
        if current is not None:
            current.update(acquisition_status="failed", error_code=receipt["error_code"])
    receipt["finished_at"] = now()
    write_new(run / "receipt.json", json_bytes(receipt))
    return receipt


def packet(run, as_of):
    cutoff = timestamp(as_of)
    receipt = json.loads((run / "receipt.json").read_bytes())
    if receipt["status"] != "complete":
        raise ValueError("incomplete_acquisition")
    blobs = {}
    for entry in receipt["files"]:
        name = entry["path"]
        if name != Path(name).name or name in blobs:
            raise ValueError("unsafe_or_duplicate_artifact")
        path = run / name
        if path.is_symlink():
            raise ValueError("symlink_artifact")
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or sha(raw) != entry["sha256"]:
            raise ValueError("artifact_hash_mismatch")
        blobs[name] = (raw, entry["first_observed_at"])
    cohort = parse_index(blobs["index.idx"][0], receipt["day"])
    selected = cohort[:receipt["member_limit"]]
    if len(cohort) != receipt["cohort_count"] or [(x["cik"], x["accession"]) for x in selected] != [(x["cik"], x["accession"]) for x in receipt["selected"]]:
        raise ValueError("cohort_receipt_mismatch")
    events, exclusions = [], {}
    for member in selected:
        name = f"{member['cik']}-{member['accession']}.hdr.sgml"
        if name not in blobs:
            # Existing successful runs used accession-only filenames and unique accessions.
            if sum(row["accession"] == member["accession"] for row in selected) != 1:
                raise ValueError("ambiguous_legacy_header")
            name = member["accession"] + ".hdr.sgml"
        raw, observed = blobs[name]
        # Index and document are both required to reconstruct this cohort member.
        observed = iso(max(timestamp(observed), timestamp(blobs["index.idx"][1])))
        event = parse_header(raw, member, observed)
        reason = event.get("exclusion_reason")
        if event["status"] == "qualified" and timestamp(event["available_at"]) > cutoff:
            reason = "before_first_availability"
        if reason:
            exclusions[reason] = exclusions.get(reason, 0) + 1
        else:
            events.append(event)
    return {"schema_version": 1, "as_of": iso(cutoff), "cohort_count": len(cohort),
            "selected_count": len(selected), "eligible_count": len(events), "events": events,
            "exclusions": exclusions, "historical_point_in_time": False,
            "selection_role": "deterministic acquisition sample, not a trading universe"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch_parser = sub.add_parser("acquire")
    fetch_parser.add_argument("--root", type=Path, required=True)
    fetch_parser.add_argument("--run-id", required=True)
    fetch_parser.add_argument("--member-limit", type=int, default=5)
    packet_parser = sub.add_parser("packet")
    packet_parser.add_argument("--run", type=Path, required=True)
    packet_parser.add_argument("--as-of", required=True)
    packet_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "acquire":
        identity = os.environ.get("SEC_USER_AGENT", "")
        if not identity:
            parser.error("SEC_USER_AGENT must contain an honest declared contact")
        result = acquire(args.root, args.run_id, identity, args.member_limit)
        print(json.dumps({key: result.get(key) for key in ["status", "request_count", "cohort_count", "error_code"]}))
        return 0 if result["status"] == "complete" else 1
    result = packet(args.run, args.as_of)
    write_new(args.out, json_bytes(result))
    print(json.dumps({key: result[key] for key in ["cohort_count", "selected_count", "eligible_count", "exclusions"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
