#!/usr/bin/env python3
"""Re-fetch the primary sources of ../data/fees-v3.json and check every quote.

Each quote must be a verbatim substring of its source after markup is removed,
entities are unescaped and whitespace is collapsed. FINRA rulebook versions are
also checked against the version labels on the rulebook page. This makes network
requests to www.federalregister.gov, www.ecfr.gov and www.finra.org only (no
market-data or broker service), so it is run by hand and not by the unit tests.
sec.gov refuses scripted requests, so its sources are listed as not checked.

  python3 verify_fee_sources.py            # exit 1 if any quote or label fails
"""

from __future__ import annotations

import gzip
import html
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

FEES = Path(__file__).resolve().parent.parent / "data" / "fees-v3.json"
FINRA_PAGE = "https://www.finra.org/rules-guidance/rulebooks/corporate-organization/section-1-member-regulatory-fees"
USER_AGENT = "native-agent-stack-fee-source-check/1 (+https://github.com/seathatflowsinourveins/native-agent-stack)"
SCRIPTED = {"federalregister_text", "finra_revision_json", "ecfr_xml"}


LAST_REQUEST: dict[str, float] = {}
SPACING_SECONDS = 2.0  # between requests to one host


def fetch(url: str, attempts: int = 4) -> str:
    host = urllib.parse.urlsplit(url).hostname
    for attempt in range(1, attempts + 1):
        # Alternate compressed and identity transfers: on some network paths one of them arrives truncated.
        encoding = "gzip" if attempt % 2 else "identity"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": encoding})
        wait = LAST_REQUEST.get(host, 0.0) + SPACING_SECONDS - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        LAST_REQUEST[host] = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            return raw.decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == attempts:
                raise
            retry_after = error.headers.get("Retry-After", "")
            time.sleep(min(int(retry_after), 120) if retry_after.isdigit() else 30 * attempt)
        except (OSError, http.client.HTTPException):
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def normalize(markup: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


def text_of(source: dict, cache: dict) -> str:
    url = source["retrieved_from"]
    if url not in cache:
        raw = fetch(url)
        if source["retrieved_format"] == "finra_revision_json":
            raw = json.loads(raw)[0]["body"]
        cache[url] = normalize(raw)
    return cache[url]


def sources(fees: dict):
    yield "sec_section31.date_basis_source", fees["sec_section31"]["date_basis_source"]
    for table in ("sec_section31", "finra_taf_covered_equity"):
        for row in fees[table]["rows"]:
            for source in row["sources"]:
                yield f"{table} {row['from']}", source


def main() -> int:
    fees = json.loads(FEES.read_text(encoding="utf-8"))
    cache: dict[str, str] = {}
    checked, failures, not_checked = 0, [], []
    try:
        labels = dict(re.findall(r'<option value="(\d+)"[^>]*>([^<]+)</option>', fetch(FINRA_PAGE)))
    except (OSError, http.client.HTTPException) as error:
        labels = {}
        failures.append({"where": "FINRA rulebook version labels", "url": FINRA_PAGE, "error": repr(error)[:200]})
    for where, source in sources(fees):
        if source["retrieved_format"] not in SCRIPTED:
            not_checked.append({"where": where, "url": source["url"], "reason": source.get("verification_note", "")})
            continue
        try:
            text = text_of(source, cache)
        except (OSError, http.client.HTTPException, ValueError) as error:
            failures.append({"where": where, "url": source["retrieved_from"], "error": repr(error)[:200]})
            continue
        for quote in source["quotes"]:
            checked += 1
            if quote not in text:
                failures.append({"where": where, "url": source["url"], "quote": quote[:160]})
        if source["retrieved_format"] == "finra_revision_json":
            label = labels.get(source["version_id"], "").strip()
            if label != source["version_label"]:
                failures.append({"where": where, "version_id": source["version_id"],
                                 "expected_label": source["version_label"], "page_label": label})
    report = {"status": "passed" if not failures else "failed", "quotes_checked": checked,
              "documents_fetched": len(cache) + (1 if labels else 0), "failures": failures, "not_checked": not_checked}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
