#!/usr/bin/env python3
"""Execute a bounded native EdgarTools metadata request or explicit offline fixture."""
import argparse
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import re
import sys

from catalyst import DAY, json_bytes, now, sha, write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    os.environ["EDGAR_RATE_LIMIT_PER_SEC"] = "2"
    os.environ["EDGAR_HTTP_TIMEOUT"] = "15"
    # The native HTTP manager rejects an empty proxy URL; retain real proxy settings.
    omitted_empty_proxies = []
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if key in os.environ and not os.environ[key].strip():
            omitted_empty_proxies.append(key)
            del os.environ[key]
    import stamina
    stamina.set_active(False)  # Documented public switch; this isolated process performs no retries.
    import edgar
    import edgar._filings as native_filings
    from edgar.httpclient import configure_http
    configure_http(timeout=15, http2=False)
    # Native set_identity logs its argument; keep declared contact out of receipts.
    logging.getLogger("edgar").setLevel(logging.ERROR)
    http_observations = []
    class HttpObserver(logging.Handler):
        def emit(self, record):
            match = re.search(r'HTTP Request: ([A-Z]+) (https://(?:www\.)?sec\.gov/[^ ]+) "HTTP/[^ ]+ ([0-9]{3})', record.getMessage())
            if match:
                http_observations.append({"method": match[1], "url": match[2], "status": int(match[3])})
    http_logger = logging.getLogger("httpx")
    http_logger.setLevel(logging.INFO)
    http_logger.addHandler(HttpObserver())
    receipt = {"schema_version": 1, "started_at": now(), "edgartools": importlib.metadata.version("edgartools"),
               "mode": "offline_fixture" if args.fixture else "native_network",
               "day": DAY, "forms": ["8-K", "8-K/A"], "automatic_retries": 0,
               "omitted_empty_proxy_variables": omitted_empty_proxies,
               "status": "failed", "historical_point_in_time": False,
               "method": "read_pipe_delimited_index / Filings.filter" if args.fixture else "get_filings(2020, 1, form='8-K', amendments=True, filing_date='2020-03-02')"}
    try:
        if args.fixture:
            raw = args.fixture.read_bytes()
            receipt["fixture_sha256"] = sha(raw)
            filings = edgar.Filings(native_filings.read_pipe_delimited_index(raw.decode())).filter(form="8-K", amendments=True, filing_date=DAY)
        else:
            identity = os.environ.get("EDGAR_IDENTITY") or os.environ.get("SEC_USER_AGENT", "")
            if not identity:
                raise ValueError("declared_contact_missing")
            # Upstream accepts arbitrary identity text; this does not establish SEC acceptance.
            edgar.set_identity(identity)
            receipt["identity_sha256"] = sha(identity.encode())
            filings = edgar.get_filings(2020, 1, form="8-K", amendments=True, filing_date=DAY)
        receipt["first_observed_at"] = now()
        receipt["cohort_count"] = len(filings)
        table = filings.to_pandas().sort_values(["cik", "accession_number"]).head(5)
        receipt["selected"] = json.loads(table.to_json(orient="records", date_format="iso"))
        # Native summary over five metadata rows; no filing body/extra network request.
        context = edgar.Filings(filings.data.take(__import__("pyarrow").array(table.index.tolist(), type=__import__("pyarrow").int64()))).to_context(detail="minimal") if len(table) else "No filings"
        receipt["native_context"] = context[:8000]
        receipt["native_context_truncated"] = len(context) > 8000
        receipt["status"] = "complete"
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        response = getattr(exc, "response", None)
        receipt["http_status"] = getattr(response, "status_code", None)
        receipt["error_code"] = "http_" + str(receipt["http_status"]) if receipt["http_status"] else "native_call_failed"
        if isinstance(exc, ValueError) and "Unknown scheme for proxy URL" in str(exc):
            receipt["error_code"] = "empty_proxy_configuration"
    receipt["http_observations"] = http_observations
    receipt["finished_at"] = now()
    write_new(args.out, json_bytes(receipt))
    print(json.dumps({key: receipt.get(key) for key in ["mode", "status", "edgartools", "cohort_count", "http_status", "error_type"]}))
    return 0 if receipt["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
