#!/usr/bin/env python3
"""Re-fetch the frozen 2020-03-02 SEC 8-K cohort with EdgarTools; keep SEC bytes private.

Run with the catalyst-provenance SDK Python (EdgarTools 5.58.0). The SEC contact
comes from the pointer file given by --env-file (default: $SEC_CONTACT_ENV). It
stays in this process, is sent only as the EDGAR User-Agent, and is never printed
or stored. Stdout carries a sanitized summary: counts, hashes and item-code
tallies, never filing text.

The parsing functions below use only the standard library so the offline tests
can exercise them; EdgarTools is imported only by the network path.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html.parser
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PLAN = HERE / "plan.json"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalyst = _load("li26_catalyst", REPO / "blueprints/us-equities/catalyst-provenance/catalyst.py")
path_safety = _load("li26_path_safety", REPO / "scripts/path_safety.py")

EDGAR_VERSION = "5.58.0"
DAY = catalyst.DAY
INDEX_URL = catalyst.INDEX_URL
INDEX_SHA256 = "5865f91e3d68590389b08760ea256fbaa1693fbc1b0e1350142fc3634a9c3383"
INDEX_BYTES = 630238
EXPECTED_COHORT = {"rows": 371, "accessions": 360, "8-K": 362, "8-K/A": 9}
ARCHIVE = "https://www.sec.gov/Archives/"
REQUESTS_PER_SECOND = 5
MAX_INDEX_BYTES = 5 * 1024 * 1024
MAX_HEADER_BYTES = 1024 * 1024
MAX_SUBMISSION_BYTES = 64 * 1024 * 1024
MAX_ACQUISITION_FAILURES = 36
HEAD_CHARS = 12000
TAIL_CHARS = 4000
MARKER = "\n[...]\n"
EXCLUSIONS = ("acquisition_failure", "empty_primary_document", "zero_declared_items")
CODE = re.compile(r"[1-9]\.[0-9]{2}")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")
CONTACT_NAMES = ("EDGAR_IDENTITY", "SEC_USER_AGENT")
PROXY_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


class Refused(Exception):
    """SEC refused or throttled a request; the run stops without retrying."""


class EmptyPrimary(ValueError):
    """No usable primary document text."""


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_frozen(plan):
    """Every frozen script, prompt and shared helper must match its planned SHA-256."""
    for relative, expected in plan["frozen_inputs"].items():
        path = path_safety.refuse_untrusted_symlinks(REPO / relative, "frozen_input_symlink_refused")
        if sha(path.read_bytes()) != expected:
            raise ValueError(f"frozen_input_changed:{relative}")


def check_plan(plan):
    """Fail closed when the frozen plan and this script disagree."""
    task = plan["task"]
    expected = {
        ("cohort", "index_sha256"): INDEX_SHA256, ("cohort", "index_bytes"): INDEX_BYTES,
        ("cohort", "rows"): EXPECTED_COHORT["rows"], ("cohort", "accessions"): EXPECTED_COHORT["accessions"],
        ("input", "head_chars"): HEAD_CHARS, ("input", "tail_chars"): TAIL_CHARS, ("input", "marker"): MARKER,
        ("acquisition", "max_requests_per_second"): REQUESTS_PER_SECOND,
        ("acquisition", "max_acquisition_failures"): MAX_ACQUISITION_FAILURES,
        ("acquisition", "edgartools"): EDGAR_VERSION,
    }
    for (section, key), value in expected.items():
        if task[section][key] != value:
            raise ValueError(f"frozen_plan_mismatch:{section}.{key}")
    if [item["reason"] for item in task["exclusions"]] != list(EXCLUSIONS):
        raise ValueError("frozen_plan_mismatch:exclusions")


# --- contact pointer file -------------------------------------------------

def check_contact(identity):
    if (not isinstance(identity, str) or not 10 <= len(identity) <= 300
            or any(not 32 <= ord(character) <= 126 for character in identity)
            or not ("@" in identity or "https://" in identity)):
        raise ValueError("declared_contact_missing_or_malformed")
    return identity


def load_contact(path):
    """Return the declared contact from a private `export NAME=value` file; never echo it."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ValueError("contact_file_unreadable_or_symlink") from None
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("contact_file_must_be_owner_only_regular_file")
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise ValueError("contact_file_too_large")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("contact_file_not_ascii") from None
    values = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*?)\s*", line)
        if not match:
            continue
        value = match[2]
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[match[1]] = value
    for name in CONTACT_NAMES:
        if values.get(name):
            return check_contact(values[name])
    raise ValueError("declared_contact_missing_or_malformed")


# --- SGML submission to model input ---------------------------------------

def _field(block, tag):
    match = re.search(rf"^<{tag}>([^\r\n<]*)", block, re.MULTILINE)
    return match[1].strip() if match else None


def split_submission(text):
    """Split an EDGAR full submission into its SEC header and the documents after it."""
    start = text.find("<SEC-HEADER>")
    end = text.find("</SEC-HEADER>")
    if start < 0 or end < start or text.find("<SEC-HEADER>", start + 1) >= 0:
        raise ValueError("sec_header_missing_or_repeated")
    header = text[start + len("<SEC-HEADER>"):end]
    documents = []
    for block in re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", text[end + len("</SEC-HEADER>"):], re.DOTALL):
        body = re.search(r"<TEXT>(.*?)</TEXT>", block, re.DOTALL)
        documents.append({"type": _field(block, "TYPE"), "sequence": _field(block, "SEQUENCE"),
                          "filename": _field(block, "FILENAME"), "text": body[1] if body else ""})
    return header, documents


def submission_identity(header):
    """Accession and form declared by the text-format SEC header of a full submission."""
    accession = re.search(r"^ACCESSION NUMBER:\s*(\S+)", header, re.MULTILINE)
    form = re.search(r"^CONFORMED SUBMISSION TYPE:\s*(\S+)", header, re.MULTILINE)
    return (accession[1] if accession else None), (form[1] if form else None)


def primary_document(documents, form):
    for document in documents:
        if document["type"] == form:
            return document
    raise EmptyPrimary("primary_document_missing")


class _TextParser(html.parser.HTMLParser):
    SKIP = {"script", "style", "head", "title", "ix:header"}
    BREAK = {"br", "p", "div", "tr", "li", "table", "hr", "center", "pre", "blockquote",
             "ul", "ol", "dl", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6"}
    CELL = {"td", "th"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.open = Counter()

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.open["head"] = self.open["title"] = 0
        if tag in self.SKIP:
            self.open[tag] += 1
        elif tag in self.BREAK:
            self.parts.append("\n")
        elif tag in self.CELL:
            self.parts.append(" ")

    def handle_startendtag(self, tag, attrs):
        if tag in self.BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.open[tag] = max(0, self.open[tag] - 1)
        elif tag in self.BREAK:
            self.parts.append("\n")
        elif tag in self.CELL:
            self.parts.append(" ")

    def handle_data(self, data):
        if not any(self.open.values()):
            self.parts.append(data)


def looks_like_html(raw):
    return re.search(r"<(?:html|body|div|p|table|font|span|br)\b", raw, re.IGNORECASE) is not None


def html_text(raw):
    parser = _TextParser()
    parser.feed(raw)
    parser.close()
    return "".join(parser.parts)


def plain_text(raw):
    return "\n".join(line for line in raw.splitlines() if line.strip().upper() != "<PAGE>")


def normalize_whitespace(text):
    lines = (" ".join(line.split()) for line in text.translate(ZERO_WIDTH).splitlines())
    return "\n".join(line for line in lines if line)


def cap_text(text, head=HEAD_CHARS, tail=TAIL_CHARS, marker=MARKER):
    if len(text) <= head + tail:
        return text, False
    return text[:head] + marker + text[-tail:], True


def model_input(submission, form):
    """Primary document text without the SEC header, whitespace-normalized and capped."""
    _, documents = split_submission(submission)
    primary = primary_document(documents, form)
    raw = primary["text"]
    text = normalize_whitespace(html_text(raw) if looks_like_html(raw) else plain_text(raw))
    if not text:
        raise EmptyPrimary("empty_primary_document")
    capped, truncated = cap_text(text)
    return {"text": capped, "chars_original": len(text), "truncated": truncated,
            "primary_filename": primary["filename"], "primary_sequence": primary["sequence"]}


def item_codes(declared):
    """Codes from the native FilingHeader ITEMS metadata; None means none declared."""
    if declared is None:
        return []
    values = declared if isinstance(declared, (list, tuple)) else str(declared).split(",")
    codes = [str(value).strip() for value in values if str(value).strip()]
    if len(codes) > 40 or any(not CODE.fullmatch(code) for code in codes) or len(set(codes)) != len(codes):
        raise ValueError("invalid_or_duplicate_declared_item")
    return sorted(codes)


# --- network path (EdgarTools) --------------------------------------------

class Pacer:
    """Start at most `per_second` requests per second, on top of EdgarTools' own limiter."""

    def __init__(self, per_second, clock=time.monotonic, sleep=time.sleep):
        self.interval = 1.0 / per_second
        self.clock, self.sleep = clock, sleep
        self.next_start = None

    def wait(self):
        now = self.clock()
        if self.next_start is not None and now < self.next_start:
            self.sleep(self.next_start - now)
            now = self.next_start
        self.next_start = now + self.interval


def native_http(state_run):
    """Configure EdgarTools for this process only, then return its GET function."""
    os.environ["EDGAR_RATE_LIMIT_PER_SEC"] = str(REQUESTS_PER_SECOND)
    os.environ["EDGAR_HTTP_TIMEOUT"] = "30"
    os.environ["EDGAR_LOCAL_DATA_DIR"] = str(state_run / "edgar-data")
    for name in PROXY_NAMES:  # the native HTTP manager rejects an empty proxy URL
        if name in os.environ and not os.environ[name].strip():
            del os.environ[name]
    import importlib.metadata
    if importlib.metadata.version("edgartools") != EDGAR_VERSION:
        raise ValueError("edgartools_version_mismatch")
    import stamina
    stamina.set_active(False)  # no automatic retries; failures are retained
    from edgar.httprequests import get_with_retry
    return get_with_retry


def fetch(get, url, limit, pacer):
    pacer.wait()
    try:
        response = get(url)
    except Exception as error:  # noqa: BLE001 - classify without echoing request details
        if type(error).__name__ == "TooManyRequestsError":
            raise Refused("http_429") from None
        raise ValueError("network_error:" + type(error).__name__) from None
    if response.status_code in (403, 429):
        raise Refused(f"http_{response.status_code}")
    if response.status_code != 200 or str(response.url) != url:
        raise ValueError(f"http_{response.status_code}")
    declared = response.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise ValueError("response_too_large")
    raw = response.content
    if len(raw) > limit:
        raise ValueError("response_too_large")
    return raw


def native_labels(header_bytes):
    from edgar.sgml import FilingHeader
    try:
        tagged = FilingHeader.parse_from_sgml_text(header_bytes.decode("utf-8"))
        declared = tagged.filing_metadata.get("ITEMS")
    except Exception as error:  # noqa: BLE001 - any native parse failure is an acquisition failure
        raise ValueError("native_header_parse_failed:" + type(error).__name__) from None
    return item_codes(declared)


def native_primary_filename(submission):
    """Diagnostic only: EdgarTools' own choice of primary document."""
    try:
        from edgar.sgml import FilingSGML
        documents = FilingSGML.from_text(submission).primary_documents
        return documents[0].document if documents else None
    except Exception:  # noqa: BLE001 - a diagnostic never changes eligibility
        return None


def submission_url(cik, accession):
    """EdgarTools' own Filing.text_url form for the full submission text."""
    return f"{ARCHIVE}edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}.txt"


def cohort_groups(raw_index):
    cohort = catalyst.parse_index(raw_index, DAY)
    forms = Counter(row["form"] for row in cohort)
    groups = {}
    for row in cohort:
        group = groups.setdefault(row["accession"], {"accession": row["accession"], "form": row["form"],
                                                     "ciks": [], "member": row})
        if group["form"] != row["form"]:
            raise ValueError("cofiler_form_mismatch")
        group["ciks"].append(row["cik"])
    counts = {"rows": len(cohort), "accessions": len(groups), "8-K": forms["8-K"], "8-K/A": forms["8-K/A"]}
    if counts != EXPECTED_COHORT:
        raise ValueError("frozen_cohort_mismatch")
    return [groups[accession] for accession in sorted(groups)], counts


def record(run, relative, raw, observed):
    catalyst.write_new(run / relative, raw)
    return {"path": relative, "sha256": sha(raw), "bytes": len(raw), "first_observed_at": observed}


def build_inputs(run, filings, parse_labels=native_labels, native_primary=native_primary_filename):
    """Apply the predeclared exclusions in order and return eligible rows plus tallies."""
    rows, exclusions, agreement = [], Counter(), Counter()
    for entry in filings:
        reason = None
        if entry["status"] != "fetched":
            reason = "acquisition_failure"
        else:
            try:
                submission = (run / entry["submission"]["path"]).read_bytes().decode("utf-8", errors="replace")
                header, _ = split_submission(submission)
                if submission_identity(header) != (entry["accession"], entry["form"]):
                    raise ValueError("submission_identity_mismatch")
                header_bytes = (run / entry["header"]["path"]).read_bytes()
                labels = parse_labels(header_bytes)
                if catalyst.parse_header(header_bytes, entry["member"],
                                         entry["header"]["first_observed_at"])["status"] != "qualified":
                    raise ValueError("header_identity_or_acceptance_unqualified")
            except (ValueError, OSError) as error:
                entry["error"] = str(error).split(":")[0][:80]
                reason = "acquisition_failure"
            else:
                try:
                    source = model_input(submission, entry["form"])
                except EmptyPrimary:
                    reason = "empty_primary_document"
                except ValueError as error:
                    entry["error"] = str(error)[:80]
                    reason = "acquisition_failure"
                else:
                    if not labels:
                        reason = "zero_declared_items"
        entry["exclusion"] = reason
        if reason:
            exclusions[reason] += 1
            continue
        native = native_primary(submission)
        agreement["unavailable" if native is None else "agree" if native == source["primary_filename"] else "disagree"] += 1
        rows.append({"accession": entry["accession"], "ciks": entry["ciks"], "form": entry["form"],
                     "labels": labels, "input": source["text"], "input_sha256": sha(source["text"].encode()),
                     "chars_original": source["chars_original"], "truncated": source["truncated"],
                     "primary_filename": source["primary_filename"]})
    return rows, exclusions, agreement


def inputs_bytes(rows):
    return b"".join(json.dumps(row, sort_keys=True, ensure_ascii=True).encode() + b"\n" for row in rows)


def acquire(state, run_id, identity, get=None, pacer=None, now=catalyst.now,
            parse_labels=native_labels, native_primary=native_primary_filename):
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("invalid_run_id")
    check_contact(identity)
    state = path_safety.refuse_untrusted_symlinks(state, "state_dir_symlink_refused")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    (state / "sec").mkdir(exist_ok=True, mode=0o700)
    if any(stat.S_IMODE(path.stat().st_mode) & 0o077 for path in (state, state / "sec")):
        raise ValueError("state_dir_must_be_owner_only")
    run = state / "sec" / run_id
    run.mkdir(mode=0o700)
    for name in ("headers", "filings", "edgar-data"):
        (run / name).mkdir(mode=0o700)
    # The contact lives only in this process environment, where EdgarTools reads it.
    os.environ["EDGAR_IDENTITY"] = identity
    get = get or native_http(run)
    pacer = pacer or Pacer(REQUESTS_PER_SECOND)
    manifest = {"schema_version": 1, "kind": "local_inference_latest_acquisition", "status": "failed",
                "run_id": run_id, "started_at": now(), "day": DAY, "index_url": INDEX_URL,
                "edgartools": EDGAR_VERSION, "max_requests_per_second": REQUESTS_PER_SECOND,
                "automatic_retries": 0, "request_count": 0, "stopped": None, "index": None,
                "cohort": None, "filings": [], "historical_point_in_time": False}
    rows, exclusions, agreement = [], Counter(), Counter()
    try:
        manifest["request_count"] += 1
        raw = fetch(get, INDEX_URL, MAX_INDEX_BYTES, pacer)
        manifest["index"] = record(run, "index.idx", raw, now())
        if manifest["index"]["sha256"] != INDEX_SHA256 or manifest["index"]["bytes"] != INDEX_BYTES:
            raise ValueError("frozen_index_changed")
        groups, manifest["cohort"] = cohort_groups(raw)
        for group in groups:
            accession, cik = group["accession"], group["ciks"][0]
            entry = {"accession": accession, "form": group["form"], "ciks": group["ciks"],
                     "member": {key: group["member"][key] for key in ("cik", "accession", "form", "filed_date")},
                     "status": "not_attempted", "header": None, "submission": None, "error": None}
            manifest["filings"].append(entry)
            if manifest["stopped"]:
                continue
            try:
                manifest["request_count"] += 1
                raw = fetch(get, group["member"]["header_url"], MAX_HEADER_BYTES, pacer)
                entry["header"] = record(run, f"headers/{accession}.hdr.sgml", raw, now())
                manifest["request_count"] += 1
                raw = fetch(get, submission_url(cik, accession), MAX_SUBMISSION_BYTES, pacer)
                entry["submission"] = record(run, f"filings/{accession}.txt", raw, now())
                entry["status"] = "fetched"
            except Refused as refusal:
                entry.update(status="failed", error=str(refusal))
                manifest["stopped"] = str(refusal)
            except (ValueError, OSError) as error:
                entry.update(status="failed", error=str(error)[:80])
                failed = sum(item["status"] == "failed" for item in manifest["filings"])
                if failed > MAX_ACQUISITION_FAILURES:
                    # The run can no longer be complete; stop sending requests.
                    manifest["stopped"] = "failure_budget_exhausted"
        rows, exclusions, agreement = build_inputs(run, manifest["filings"], parse_labels, native_primary)
        payload = inputs_bytes(rows)
        manifest["inputs"] = record(run, "inputs.jsonl", payload, now())
        manifest["inputs"]["rows"] = len(rows)
        complete = (not manifest["stopped"] and rows
                    and exclusions["acquisition_failure"] <= MAX_ACQUISITION_FAILURES)
        manifest["status"] = "complete" if complete else "incomplete"
    except (ValueError, OSError, Refused) as error:
        manifest["error"] = str(error)[:120]
    manifest["exclusions"] = {reason: exclusions[reason] for reason in EXCLUSIONS}
    manifest["finished_at"] = now()
    catalyst.write_new(run / "manifest.json", catalyst.json_bytes(manifest))
    summary = public_summary(manifest, rows, agreement, sha((run / "manifest.json").read_bytes()))
    catalyst.write_new(run / "summary.json", catalyst.json_bytes(summary))
    return summary


def public_summary(manifest, rows, agreement, manifest_sha256):
    """Counts and hashes only: no contact, no filing text, no local paths."""
    labels = Counter(code for row in rows for code in row["labels"])
    chars = [row["chars_original"] for row in rows]
    return {"schema_version": 1, "kind": "local_inference_latest_acquisition_summary",
            "status": manifest["status"], "run_id": manifest["run_id"], "day": DAY,
            "edgartools": EDGAR_VERSION, "request_count": manifest["request_count"],
            "max_requests_per_second": REQUESTS_PER_SECOND, "automatic_retries": 0,
            "stopped": manifest["stopped"], "error": manifest.get("error"),
            "index_sha256": (manifest["index"] or {}).get("sha256"), "cohort": manifest["cohort"],
            "accessions_fetched": sum(entry["status"] == "fetched" for entry in manifest["filings"]),
            "exclusions": manifest["exclusions"], "eligible": len(rows),
            "truncated_inputs": sum(row["truncated"] for row in rows),
            "input_chars_median": statistics.median(chars) if chars else None,
            "input_chars_max": max(chars) if chars else None,
            "label_counts": dict(sorted(labels.items())),
            "native_primary_agreement": dict(sorted(agreement.items())),
            "inputs_sha256": (manifest.get("inputs") or {}).get("sha256"),
            "manifest_sha256": manifest_sha256,
            "started_at": manifest["started_at"], "finished_at": manifest["finished_at"],
            "historical_point_in_time": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=os.environ.get("SEC_CONTACT_ENV"),
                        help="pointer to the private contact file (default: $SEC_CONTACT_ENV)")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args()
    if not args.env_file:
        parser.error("pass --env-file \"$SEC_CONTACT_ENV\" (a pointer, never the value)")
    plan = json.loads(args.plan.read_text())
    check_plan(plan)
    verify_frozen(plan)
    try:
        identity = load_contact(args.env_file)
    except ValueError as error:
        parser.error(str(error))
    summary = acquire(args.state_dir, args.run_id, identity)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
