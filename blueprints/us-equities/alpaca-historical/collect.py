#!/usr/bin/env python3
"""Pinned native Alpaca GET transport with a private page/provenance bridge.

No trading client. Raw bodies, precise numbers and page transitions are retained;
the public output is deliberately limited to counts, statuses and integrity hashes.
"""
import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import re
import time
from uuid import UUID
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
MAX_BODY = 8 * 1024 * 1024
UTC = timezone.utc


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("nonfinite_json_number")
    try:
        return json.loads(raw, parse_float=Decimal, parse_constant=nonfinite, object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("malformed_json") from None


def safe_path(path):
    path = Path(path).absolute()
    if ".." in path.parts or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("symlink_or_parent_traversal_refused")
    return path


def read(path):
    path = safe_path(path)
    if not path.is_file() or path.stat().st_size > MAX_BODY:
        raise ValueError("invalid_or_oversized_file")
    raw = path.read_bytes()
    if len(raw) > MAX_BODY:
        raise ValueError("invalid_or_oversized_file")
    return raw


def write_new(path, raw):
    path = safe_path(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def digest(name, raw):
    return {"path": name, "bytes": len(raw), "sha256": sha(raw)}


def timestamp_ns(value):
    """UTC RFC3339, no floating timestamp arithmetic or precision truncation."""
    if not isinstance(value, str):
        raise ValueError("invalid_timestamp")
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z", value)
    if not match:
        raise ValueError("invalid_timestamp")
    try:
        parsed = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        raise ValueError("invalid_timestamp") from None
    delta = parsed - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 10**9 + int((match[2] or "").ljust(9, "0"))


def now():
    seconds, ns = divmod(time.time_ns(), 10**9)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{ns:09d}Z"


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("invalid_date") from None


def number(value, *, integer=False, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError("invalid_numeric_field")
    value = Decimal(value)
    if not value.is_finite() or value < 0 or (positive and value == 0):
        raise ValueError("invalid_numeric_field")
    if integer and value != value.to_integral_value():
        raise ValueError("invalid_integer_field")
    return str(value)


def validate_plan(plan):
    start, end = timestamp_ns(plan["start_inclusive"]), timestamp_ns(plan["end_exclusive"])
    b, a = plan["bars"]["query"], plan["actions"]["query"]
    if start >= end or timestamp_ns(b["start"]) != start or timestamp_ns(b["end"]) != end - 1:
        raise ValueError("invalid_half_open_wire_bounds")
    if (b["symbols"], b["feed"], b["adjustment"], b["currency"], b["timeframe"], b["sort"]) != ("AAPL", "sip", "raw", "USD", "1Day", "asc"):
        raise ValueError("unsupported_bars_contract")
    if iso_date(b["asof"]) != date(2020, 9, 4):
        raise ValueError("unsupported_symbol_asof")
    if (a["symbols"], a["types"], a["region"], a["data_quality"], a["sort"]) != ("AAPL", "cash_dividend,forward_split", "us", "all", "asc"):
        raise ValueError("unsupported_actions_contract")
    if (a["start"], a["end"]) != ("2020-08-03", "2020-09-04"):
        raise ValueError("unsupported_actions_bounds")
    if (plan["max_pages_per_stage"], b["limit"], a["limit"], plan["http_attempts_per_page"], plan["max_body_bytes"]) != (10, 10, 1, 1, MAX_BODY):
        raise ValueError("unsupported_resource_bounds")
    if plan["timeout_seconds"] != {"connect": 10, "read": 30}:
        raise ValueError("unsupported_timeout")
    if plan["alpaca_py_version"] != "0.44.0":
        raise ValueError("unsupported_sdk_version")
    if len(plan["expected_session_dates"]) != 25 or sorted(set(plan["expected_session_dates"])) != plan["expected_session_dates"]:
        raise ValueError("invalid_expected_sessions")
    for kind, version, path in [("bars", "v2", "/stocks/bars"), ("actions", "v1", "/corporate-actions")]:
        if plan[kind]["path"] != path or plan[kind]["url"] != "https://data.alpaca.markets/" + version + path:
            raise ValueError("unsupported_endpoint")
    return plan


def source_anchor(page):
    return {"source_sha256": sha(page["body"]), "source_bytes": len(page["body"]),
            "first_observed_at": page["observed_at"]}


def bar_rows(body, page, plan):
    groups = body.get("bars")
    if not isinstance(groups, dict) or set(groups) - {"AAPL"}:
        raise ValueError("unexpected_bar_symbols")
    rows = groups.get("AAPL", [])
    if not isinstance(rows, list):
        raise ValueError("invalid_bar_array")
    result = []
    for row in rows:
        if not isinstance(row, dict) or not {"t", "o", "h", "l", "c", "v", "n", "vw"} <= row.keys():
            raise ValueError("malformed_bar_fields")
        ns = timestamp_ns(row["t"])
        if not timestamp_ns(plan["start_inclusive"]) <= ns < timestamp_ns(plan["end_exclusive"]):
            raise ValueError("bar_outside_window")
        seconds, fraction = divmod(ns, 10**9)
        local = datetime.fromtimestamp(seconds, UTC).astimezone(ZoneInfo("America/New_York"))
        if fraction or (local.hour, local.minute, local.second) != (0, 0, 0):
            raise ValueError("daily_bar_not_exchange_midnight")
        parsed = {k: number(row[k], integer=k == "n", positive=k in {"o", "h", "l", "c", "vw"}) for k in ["o", "h", "l", "c", "v", "n", "vw"]}
        if Decimal(parsed["l"]) > min(Decimal(parsed["o"]), Decimal(parsed["c"])) or Decimal(parsed["h"]) < max(Decimal(parsed["o"]), Decimal(parsed["c"]), Decimal(parsed["l"])):
            raise ValueError("invalid_ohlc_order")
        result.append(dict(parsed, symbol="AAPL", timestamp=row["t"], timestamp_ns=ns,
                           session_date=local.date().isoformat(), **source_anchor(page)))
    return result


def action_rows(body, page, plan):
    groups = body.get("corporate_actions")
    if not isinstance(groups, dict):
        raise ValueError("invalid_actions_object")
    result = []
    for group, rows in groups.items():
        if not isinstance(rows, list):
            raise ValueError("invalid_action_array")
        if group not in {"cash_dividends", "forward_splits"}:
            if rows:
                raise ValueError("unexpected_action_type")
            continue
        for row in rows:
            if not isinstance(row, dict) or row.get("symbol") != "AAPL":
                raise ValueError("invalid_action_identity")
            try:
                identity = str(UUID(row.get("id", "")))
            except (ValueError, AttributeError, TypeError):
                raise ValueError("invalid_action_identity") from None
            process = iso_date(row.get("process_date"))
            if not iso_date(plan["actions"]["query"]["start"]) <= process <= iso_date(plan["actions"]["query"]["end"]):
                raise ValueError("action_outside_process_window")
            output = {"id": identity, "symbol": "AAPL", "type": group[:-1],
                      "process_date": row["process_date"], **source_anchor(page)}
            missing = []
            for key in ["ex_date", "record_date", "payable_date", "due_bill_on_date", "due_bill_off_date", "due_bill_redemption_date"]:
                value = row.get(key)
                output[key] = iso_date(value).isoformat() if value is not None else None
            if output["ex_date"] is None:
                missing.append("ex_date")
            for key in (["rate"] if group == "cash_dividends" else ["old_rate", "new_rate"]):
                value = row.get(key)
                if value is None:
                    missing.append(key)
                    output[key] = None
                else:
                    output[key] = number(value, positive=group == "forward_splits")
            for key in ["cusip", "isin", "currency"]:
                value = row.get(key)
                if value is not None and (not isinstance(value, str) or not value):
                    raise ValueError("invalid_action_field")
                output[key] = value
            if not output["cusip"] and not output["isin"]:
                missing.append("security_identifier")
            if group == "cash_dividends":
                for key in ["special", "foreign"]:
                    value = row.get(key)
                    if value is not None and not isinstance(value, bool):
                        raise ValueError("invalid_action_boolean")
                    output[key] = value
                    if value is None:
                        missing.append(key)
            output.update(qualification="incomplete" if missing else "qualified", missing_fields=missing)
            result.append(output)
    return result


def validate_pages(kind, pages, plan, *, require_terminal=True):
    validate_plan(plan)
    if not pages or len(pages) > plan["max_pages_per_stage"]:
        raise ValueError("invalid_page_count")
    expected_token, tokens, seen, all_rows = None, set(), set(), []
    previous_order = None
    for index, page in enumerate(pages):
        expected_request = dict(plan[kind]["query"])
        if expected_token is not None:
            expected_request["page_token"] = expected_token
        if page["request"] != expected_request:
            raise ValueError("request_mismatch")
        start, observed = timestamp_ns(page["started_at"]), timestamp_ns(page["observed_at"])
        if observed < start or observed < timestamp_ns(plan["end_exclusive"]):
            raise ValueError("invalid_observation_interval")
        if page["transport_error"] is not None:
            raise ValueError("transport_error")
        actual = page.get("actual_request")
        if not isinstance(actual, dict) or actual.get("method") != "GET" or not isinstance(actual.get("url"), str):
            raise ValueError("wire_request_mismatch")
        url = urlsplit(actual["url"])
        if (url.scheme + "://" + url.netloc + url.path != plan[kind]["url"] or url.fragment
                or parse_qs(url.query, keep_blank_values=True) != {k: [str(v)] for k, v in expected_request.items()}):
            raise ValueError("wire_request_mismatch")
        if page.get("body_complete") is not True:
            raise ValueError("incomplete_response_body")
        if page["status"] != 200:
            if isinstance(page["status"], int) and 100 <= page["status"] <= 599:
                raise ValueError("http_" + str(page["status"]))
            raise ValueError("invalid_http_status")
        if not isinstance(page["body"], bytes) or len(page["body"]) > MAX_BODY:
            raise ValueError("invalid_or_oversized_body")
        body = strict_json(page["body"])
        if not isinstance(body, dict):
            raise ValueError("invalid_response_object")
        if "next_page_token" not in body:
            raise ValueError("missing_page_token")
        token = body["next_page_token"]
        if token is not None and (not isinstance(token, str) or not token or len(token) > 4096):
            raise ValueError("invalid_page_token")
        if token is not None and token in tokens:
            raise ValueError("page_token_cycle")
        if token is not None:
            tokens.add(token)
        if token is None and index != len(pages) - 1:
            raise ValueError("pages_after_terminal")
        rows = bar_rows(body, page, plan) if kind == "bars" else action_rows(body, page, plan)
        if len(rows) > plan[kind]["query"]["limit"]:
            raise ValueError("page_limit_exceeded")
        for row in rows:
            identity = row["timestamp_ns"] if kind == "bars" else row["id"]
            if identity in seen:
                raise ValueError("duplicate_bar" if kind == "bars" else "duplicate_action")
            seen.add(identity)
            order = row["timestamp_ns"] if kind == "bars" else row["process_date"]
            if previous_order is not None and order < previous_order:
                raise ValueError("unordered_response")
            previous_order = order
            all_rows.append(row)
        expected_token = token
    if require_terminal and expected_token is not None:
        raise ValueError("incomplete_page_chain")
    summary = {"pages": len(pages), "rows": len(all_rows), "terminal_page_observed": expected_token is None}
    if kind == "bars":
        days = [r["session_date"] for r in all_rows]
        if require_terminal and days != plan["expected_session_dates"]:
            raise ValueError("session_coverage_mismatch")
        summary["session_dates"] = days
    else:
        summary["qualified_rows"] = sum(r["qualification"] == "qualified" for r in all_rows)
        summary["comparison_targets_observed"] = [any(r["type"] == t["type"] and r["ex_date"] == t["ex_date"] and r["qualification"] == "qualified" for r in all_rows) for t in plan["action_comparison_targets"]]
        summary["historical_coverage_established"] = False
    return {"status": "complete", "summary": summary, "rows": all_rows}


def assess(kind, pages, plan):
    try:
        return validate_pages(kind, pages, plan)
    except (ValueError, KeyError, TypeError) as exc:
        # Our ValueError codes contain no provider body or account data.
        reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"[a-z_0-9]+", str(exc)) else "malformed_structure"
        return {"status": "failed", "reason": reason, "summary": {"pages": len(pages)}, "rows": []}


def native_identity():
    from alpaca.common.rest import RESTClient
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.historical.corporate_actions import CorporateActionsClient
    from alpaca.data.requests import StockBarsRequest, CorporateActionsRequest
    version = importlib.metadata.version("alpaca-py")
    if version != "0.44.0":
        raise ValueError("alpaca_sdk_version_mismatch")
    sources = sorted({Path(inspect.getfile(c)) for c in [RESTClient, StockHistoricalDataClient, CorporateActionsClient, StockBarsRequest, CorporateActionsRequest]})
    return {"alpaca_py_version": version, "requests_version": importlib.metadata.version("requests"),
            "sources": [digest("alpaca/" + str(p).split("/alpaca/", 1)[1], read(p)) for p in sources]}


class NativePages:
    """The only authenticated seam: pinned native SDK GET + Requests hook.

    Private SDK _session/_retry access is guarded and version-pinned. Zero passed
    to the native retry constructor is ignored in 0.44.0, hence explicit _retry.
    """
    def __init__(self, api_key, secret_key, plan):
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.historical.corporate_actions import CorporateActionsClient
        from requests import Session
        native_identity()
        validate_plan(plan)
        self.plan, self.clients, self.captured = plan, {}, None
        for kind, cls in [("bars", StockHistoricalDataClient), ("actions", CorporateActionsClient)]:
            client = cls(api_key=api_key, secret_key=secret_key, raw_data=True)
            if not isinstance(client._session, Session) or not hasattr(client, "_retry"):
                raise ValueError("unsupported_sdk_transport_seam")
            client._retry = 0
            client._session.trust_env = False
            original = client._session.request
            expected_url = plan[kind]["url"]
            def bounded(method, url, *, _request=original, _url=expected_url, **kwargs):
                if method != "GET" or url != _url or kwargs.get("allow_redirects") is not False:
                    raise ValueError("unsupported_transport_request")
                return _request(method, url, timeout=(10, 30), stream=True, **kwargs)
            client._session.request = bounded
            client._session.hooks["response"].append(self._capture)
            self.clients[kind] = client

    def _capture(self, response, *args, **kwargs):
        if self.captured is not None:
            raise ValueError("multiple_http_attempts_refused")
        chunks, count, complete = [], 0, False
        try:
            for chunk in response.iter_content(chunk_size=65536):
                room = MAX_BODY - count
                chunks.append(chunk[:room])
                count += min(len(chunk), room)
                if len(chunk) > room:
                    break
            else:
                complete = True
        finally:
            raw = b"".join(chunks)
            self.captured = {"body": raw, "body_complete": complete,
                             "status": response.status_code, "observed_at": now(),
                             "actual_request": {"method": response.request.method, "url": response.request.url}}
            # Requests' consumed-body cache lets the native SDK inspect text/JSON
            # after this bounded stream read. No bytes are parsed into floats here.
            # Close an incomplete stream before marking its prefix consumed;
            # Requests otherwise skips raw.close() and may leak the connection.
            response.close()
            response._content = raw
            response._content_consumed = True
        if not complete:
            raise ValueError("incomplete_response_body")

    def __call__(self, kind, request):
        started = now()
        self.captured = None
        error = None
        try:
            self.clients[kind].get(self.plan[kind]["path"], data=request)
        except Exception:
            # SDK exception messages can include provider bodies. Keep their raw
            # response privately; never copy the exception or HTTP headers.
            error = "native_request_failed"
        captured = self.captured or {"body": b"", "body_complete": False,
                                    "status": None, "observed_at": now(), "actual_request": None}
        # Status-bearing failures remain HTTP evidence; a 200 parse failure is
        # independently classified by strict raw parsing, never SDK floats.
        return dict(captured, started_at=started,
                    transport_error=error if captured["status"] is None else None)

    def close(self):
        for client in self.clients.values():
            client._session.close()


def collect(out, fetch=None):
    out = safe_path(out)
    if any((p / ".git").exists() for p in [out, *out.parents]):
        raise ValueError("private_output_must_be_outside_git")
    if out.exists():
        raise FileExistsError("output_directory_exists")
    plan_raw, bridge_raw = read(HERE / "plan.json"), read(Path(__file__))
    plan = validate_plan(strict_json(plan_raw))
    identity = native_identity()
    out.mkdir(mode=0o700, parents=True)
    write_new(out / "plan.json", plan_raw)
    write_new(out / "collector.py", bridge_raw)
    receipt = {"schema_version": 1, "plan": digest("plan.json", plan_raw),
               "collector": digest("collector.py", bridge_raw), "native": identity,
               "frozen_at": now(), "stages": {}}
    # Freeze before any client creation or authenticated request.
    write_new(out / "freeze.json", encode(receipt))
    receipt["freeze"] = digest("freeze.json", read(out / "freeze.json"))
    native = None
    if fetch is None:
        key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
        if not key or not secret:
            write_new(out / "preflight-failure.json", encode({"status": "failed", "reason": "missing_credentials"}))
            raise ValueError("missing_credentials")
        native = NativePages(key, secret, plan)
        fetch = native
    results = {}
    try:
        for kind in ["bars", "actions"]:
            pages, entries, token = [], [], None
            for index in range(plan["max_pages_per_stage"]):
                request = dict(plan[kind]["query"])
                if token is not None:
                    request["page_token"] = token
                response = fetch(kind, request)
                page = dict(response, request=request)
                name = f"{kind}-{index+1:03d}.json"
                write_new(out / name, page["body"])
                entry = {k: v for k, v in page.items() if k != "body"}
                entry["source"] = digest(name, page["body"])
                # Per-page metadata survives interruption before final receipt.
                write_new(out / (name + ".meta.json"), encode(entry))
                pages.append(page); entries.append(entry)
                try:
                    validate_pages(kind, pages, plan, require_terminal=False)
                    token = strict_json(page["body"])["next_page_token"]
                except (ValueError, KeyError, TypeError):
                    break
                if token is None:
                    break
            result = assess(kind, pages, plan)
            results[kind] = result
            receipt["stages"][kind] = {"pages": entries, "assessment": result}
    finally:
        if native is not None:
            native.close()
    write_new(out / "receipt.json", encode(receipt))
    return public_summary(results, sha(read(out / "receipt.json")))


def verify_blob(root, entry):
    name = entry["path"]
    if not isinstance(name, str) or name != Path(name).name or name in {".", ".."}:
        raise ValueError("unsafe_artifact_name")
    raw = read(root / name)
    if sha(raw) != entry["sha256"] or len(raw) != entry["bytes"]:
        raise ValueError("artifact_hash_mismatch")
    return raw


def verify(root, expected_receipt_sha256):
    root = safe_path(root)
    raw = read(root / "receipt.json")
    if sha(raw) != expected_receipt_sha256:
        raise ValueError("receipt_hash_mismatch")
    receipt = strict_json(raw)
    plan = validate_plan(strict_json(verify_blob(root, receipt["plan"])))
    verify_blob(root, receipt["collector"])
    freeze = strict_json(verify_blob(root, receipt["freeze"]))
    if freeze != {k: receipt[k] for k in ["schema_version", "plan", "collector", "native", "frozen_at"]} | {"stages": {}}:
        raise ValueError("freeze_mismatch")
    if set(receipt["stages"]) != {"bars", "actions"}:
        raise ValueError("unexpected_stage_set")
    names = {"receipt.json", "plan.json", "collector.py", "freeze.json"}
    results = {}
    for kind, stage in receipt["stages"].items():
        pages = []
        for index, entry in enumerate(stage["pages"]):
            name = f"{kind}-{index+1:03d}.json"
            if entry["source"]["path"] != name:
                raise ValueError("page_source_identity_mismatch")
            body = verify_blob(root, entry["source"])
            if strict_json(read(root / (name + ".meta.json"))) != entry:
                raise ValueError("page_metadata_mismatch")
            names.update([name, name + ".meta.json"])
            pages.append({k: v for k, v in entry.items() if k != "source"} | {"body": body})
        result = assess(kind, pages, plan)
        if result != stage["assessment"]:
            raise ValueError("assessment_mismatch")
        results[kind] = result
    if {p.name for p in root.iterdir()} != names:
        raise ValueError("unexpected_artifact")
    return results


def public_summary(results, receipt_hash):
    return {"receipt_sha256": receipt_hash,
            "stages": {kind: {k: v for k, v in result.items() if k != "rows"} for kind, result in results.items()},
            "scope": "Retrospective query only; historical availability and complete action coverage remain unestablished."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    acquire = sub.add_parser("collect")
    acquire.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--run", type=Path, required=True)
    check.add_argument("--receipt-sha256", required=True)
    args = parser.parse_args()
    if args.command == "collect":
        result = collect(args.out)
    else:
        result = public_summary(verify(args.run, args.receipt_sha256), args.receipt_sha256)
    print(json.dumps(result, sort_keys=True))
    # Refused/empty actions remain a separate result; valid bars are still useful.
    return 0 if result["stages"]["bars"]["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
