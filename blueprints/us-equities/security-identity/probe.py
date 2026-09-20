#!/usr/bin/env python3
"""Four retrospective symbol-query observations and one current asset observation."""
import argparse
from datetime import datetime
from decimal import Decimal
import importlib.metadata
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "alpaca-historical/collect.py"
SPEC = importlib.util.spec_from_file_location("identity_acquisition_primitives", BASE_PATH)
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)
CASES = [("meta_mapped", "META", "2022-06-10"), ("fb_mapped", "FB", "2022-06-08"),
         ("meta_unmapped", "META", "-"), ("fb_unmapped", "FB", "-")]
FIELDS = ["o", "h", "l", "c", "v", "n", "vw"]


def ns(text):
    value = B.timestamp_ns(text)
    if not -(2**63) < value <= 2**63 - 1:
        raise ValueError("nanosecond_out_of_int64_range")
    return value


def validate_plan(plan):
    if [(c["case_id"], c["symbol"], c["asof"]) for c in plan["cases"]] != CASES:
        raise ValueError("unsupported_query_cases")
    expected = {"start": "2022-06-08T00:00:00Z", "end": "2022-06-10T23:59:59.999999999Z", "timeframe": "1Day", "feed": "sip", "adjustment": "raw", "currency": "USD", "sort": "asc", "limit": 2}
    if plan["bars_query"] != expected or plan["bars_url"] != "https://data.alpaca.markets/v2/stocks/bars":
        raise ValueError("unsupported_bars_contract")
    if plan["start_inclusive"] != expected["start"] or plan["end_exclusive"] != "2022-06-11T00:00:00Z" or ns(expected["end"]) != ns(plan["end_exclusive"]) - 1:
        raise ValueError("unsupported_half_open_bounds")
    if plan["asset"] != {"case_id": "meta_current", "symbol": "META", "url": "https://paper-api.alpaca.markets/v2/assets/META"}:
        raise ValueError("unsupported_asset_contract")
    if (plan["max_pages_per_case"], plan["max_asset_requests"], plan["max_total_http_attempts"], plan["max_body_bytes"], plan["http_attempts_per_page"], plan["connect_timeout_seconds"], plan["read_timeout_seconds"]) != (3, 1, 13, B.MAX_BODY, 1, 10, 30):
        raise ValueError("unsupported_resource_bounds")
    if plan["alpaca_py_version"] != "0.44.0" or plan["duckdb_version"] != "1.5.5" or plan["historical_cutoff"] != plan["end_exclusive"]:
        raise ValueError("unsupported_runtime_or_cutoff")
    if plan["session_dates"] != ["2022-06-08", "2022-06-09", "2022-06-10"]:
        raise ValueError("unsupported_session_dates")
    return plan


def query(plan, case_id, token=None):
    if case_id == "meta_current":
        if token is not None:
            raise ValueError("asset_pagination_forbidden")
        return {}
    case = next(c for c in plan["cases"] if c["case_id"] == case_id)
    result = dict(plan["bars_query"], symbols=case["symbol"], asof=case["asof"])
    if token is not None:
        result["page_token"] = token
    return result


def native_identity():
    from alpaca.trading.client import TradingClient
    result = B.native_identity()
    path = Path(inspect.getfile(TradingClient))
    result["sources"].append(B.digest("alpaca/trading/client.py", B.read(path)))
    return result


class NativeIdentityPages(B.NativePages):
    """Reuse the accepted bounded response hook and native GET dispatch unchanged.

    Only initialization differs: fixed query-case paths and a paper asset GET.
    No account, order, position, historical announcement or asset-list methods.
    """
    def __init__(self, key, secret, plan):
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.trading.client import TradingClient
        from requests import Session
        native_identity()
        validate_plan(plan)
        self.clients, self.plan, self.captured = {}, {}, None
        for case_id in [c[0] for c in CASES] + ["meta_current"]:
            asset = case_id == "meta_current"
            client = (TradingClient(api_key=key, secret_key=secret, paper=True, raw_data=True) if asset
                      else StockHistoricalDataClient(api_key=key, secret_key=secret, raw_data=True))
            if not isinstance(client._session, Session) or not hasattr(client, "_retry"):
                raise ValueError("unsupported_sdk_transport_seam")
            client._retry = 0
            client._session.trust_env = False
            original = client._session.request
            allowed = plan["asset"]["url"] if asset else plan["bars_url"]
            def bounded(method, url, *, _request=original, _url=allowed, **kwargs):
                if method != "GET" or url != _url or kwargs.get("allow_redirects") is not False:
                    raise ValueError("unsupported_transport_request")
                return _request(method, url, timeout=(10, 30), stream=True, **kwargs)
            client._session.request = bounded
            client._session.hooks["response"].append(self._capture)
            self.clients[case_id] = client
            self.plan[case_id] = {"path": "/assets/META" if asset else "/stocks/bars"}


def envelope(page, expected, endpoint):
    if page["request"] != expected:
        raise ValueError("request_mismatch")
    started, observed = ns(page["started_at"]), ns(page["observed_at"])
    if observed < started or observed < ns("2022-06-11T00:00:00Z"):
        raise ValueError("invalid_observation_interval")
    if page["transport_error"] is not None:
        raise ValueError("transport_error")
    actual = page.get("actual_request")
    if not isinstance(actual, dict) or actual.get("method") != "GET":
        raise ValueError("wire_request_mismatch")
    url = urlsplit(actual.get("url", ""))
    if url.scheme + "://" + url.netloc + url.path != endpoint or url.fragment or parse_qs(url.query, keep_blank_values=True) != {k: [str(v)] for k, v in expected.items()}:
        raise ValueError("wire_request_mismatch")
    if page["body_complete"] is not True:
        raise ValueError("incomplete_response_body")
    if type(page["status"]) is not int or not 100 <= page["status"] <= 599:
        raise ValueError("invalid_http_status")
    if page["status"] != 200:
        raise ValueError("http_" + str(page["status"]))
    if not isinstance(page["body"], bytes) or len(page["body"]) > B.MAX_BODY:
        raise ValueError("invalid_or_oversized_body")
    value = B.strict_json(page["body"])
    if not isinstance(value, dict):
        raise ValueError("invalid_response_object")
    return value


def normalized_bar(row, case, page, plan):
    if not isinstance(row, dict) or not {"t", *FIELDS} <= row.keys():
        raise ValueError("malformed_bar_fields")
    event = ns(row["t"])
    if not ns(plan["start_inclusive"]) <= event < ns(plan["end_exclusive"]):
        raise ValueError("bar_outside_window")
    seconds, remainder = divmod(event, 10**9)
    local = datetime.fromtimestamp(seconds, B.UTC).astimezone(ZoneInfo("America/New_York"))
    if remainder or (local.hour, local.minute, local.second) != (0, 0, 0):
        raise ValueError("daily_bar_not_exchange_midnight")
    values = {f: B.number(row[f], integer=f == "n", positive=f in {"o", "h", "l", "c", "vw"}) for f in FIELDS}
    if Decimal(values["l"]) > min(Decimal(values["o"]), Decimal(values["c"])) or Decimal(values["h"]) < max(Decimal(values["o"]), Decimal(values["c"]), Decimal(values["l"])):
        raise ValueError("invalid_ohlc_order")
    return {**values, "case_id": case["case_id"], "requested_symbol": case["symbol"],
            "returned_symbol": case["symbol"], "request_asof": case["asof"],
            "event_at": row["t"], "event_ns": event, "session_date": local.date().isoformat(),
            "observed_ns": ns(page["observed_at"]), "available_ns": ns(page["observed_at"]),
            "valid_from": None, "valid_to": None, "original_publication_at": None,
            "provider_revision_at": None, "permanent_security_id": None, **B.source_anchor(page)}


def validate_pages(case_id, pages, plan, terminal=True):
    validate_plan(plan)
    asset = case_id == "meta_current"
    if not pages or len(pages) > (1 if asset else 3):
        raise ValueError("invalid_page_count")
    if asset:
        body = envelope(pages[0], {}, plan["asset"]["url"])
        try:
            identity = str(UUID(body["id"]))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ValueError("invalid_asset_identity") from None
        if body.get("symbol") != "META" or body.get("status") not in {"active", "inactive"} or not isinstance(body.get("exchange"), str) or not body["exchange"] or body.get("class") != "us_equity" or type(body.get("tradable")) is not bool:
            raise ValueError("invalid_current_asset_fields")
        row = {"provider_asset_id": identity, "symbol": "META", "status": body["status"],
               "exchange": body["exchange"], "asset_class": body["class"], "tradable": body["tradable"],
               "valid_from": None, "valid_to": None, "original_publication_at": None,
               "provider_revision_at": None, "historical_universe_eligible": False,
               "observed_ns": ns(pages[0]["observed_at"]), **B.source_anchor(pages[0])}
        return {"status": "complete", "summary": {"pages": 1, "rows": 1}, "rows": [row]}
    case = next(c for c in plan["cases"] if c["case_id"] == case_id)
    token, tokens, identities, rows, previous_observation = None, set(), set(), [], None
    for index, page in enumerate(pages):
        body = envelope(page, query(plan, case_id, token), plan["bars_url"])
        if previous_observation is not None and ns(page["started_at"]) < previous_observation:
            raise ValueError("nonsequential_observation_interval")
        previous_observation = ns(page["observed_at"])
        if "next_page_token" not in body:
            raise ValueError("missing_page_token")
        token = body["next_page_token"]
        if token is not None and (not isinstance(token, str) or not token or len(token) > 4096):
            raise ValueError("invalid_page_token")
        if token is not None and token in tokens:
            raise ValueError("page_token_cycle")
        if token is not None:
            tokens.add(token)
        elif index != len(pages) - 1:
            raise ValueError("pages_after_terminal")
        groups = body.get("bars")
        if not isinstance(groups, dict) or set(groups) - {case["symbol"]}:
            raise ValueError("unexpected_returned_symbols")
        source_rows = groups.get(case["symbol"], [])
        if not isinstance(source_rows, list) or len(source_rows) > 2:
            raise ValueError("invalid_page_rows")
        for raw in source_rows:
            row = normalized_bar(raw, case, page, plan)
            if row["event_ns"] in identities:
                raise ValueError("duplicate_bar")
            if rows and row["event_ns"] < rows[-1]["event_ns"]:
                raise ValueError("unordered_bars")
            identities.add(row["event_ns"]); rows.append(row)
    if terminal and token is not None:
        raise ValueError("incomplete_page_chain")
    return {"status": "complete", "summary": {"pages": len(pages), "rows": len(rows),
            "session_dates": [r["session_date"] for r in rows], "terminal_page_observed": token is None}, "rows": rows}


def assess(case_id, pages, plan):
    try:
        return validate_pages(case_id, pages, plan)
    except (ValueError, KeyError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"[a-z_0-9]+", str(exc)) else "malformed_structure"
        return {"status": "failed", "reason": reason, "summary": {"pages": len(pages)}, "rows": []}


def comparisons(cases):
    def mapping(name):
        return {r["session_date"]: r for r in cases[name]["rows"]}
    meta, fb = mapping("meta_mapped"), mapping("fb_mapped")
    common = sorted(meta.keys() & fb.keys())
    mismatches = {f: sum(Decimal(meta[d][f]) != Decimal(fb[d][f]) for d in common) for f in FIELDS}
    left, right = mapping("meta_unmapped"), mapping("fb_unmapped")
    return {"mapped_alias": {"both_queries_complete": all(cases[c]["status"] == "complete" for c in ["meta_mapped", "fb_mapped"]),
            "shared_sessions": len(common), "equal_rows": sum(all(Decimal(meta[d][f]) == Decimal(fb[d][f]) for f in FIELDS) for d in common),
            "only_meta_sessions": len(meta.keys() - fb.keys()), "only_fb_sessions": len(fb.keys() - meta.keys()), "field_mismatches": mismatches},
            "unmapped_partition": {"both_queries_complete": all(cases[c]["status"] == "complete" for c in ["meta_unmapped", "fb_unmapped"]),
            "overlap_sessions": len(left.keys() & right.keys()), "union_sessions": len(left.keys() | right.keys()),
            "union_equals_meta_mapped_dates": left.keys() | right.keys() == meta.keys()},
            "permanent_identity_established": False, "historical_delisting_established": False,
            "provider_revision_availability_established": False}


def new_directory(out):
    out = B.safe_path(out)
    if any((p / ".git").exists() for p in [out, *out.parents]):
        raise ValueError("private_output_must_be_outside_git")
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    return out


def collect(out, fetch=None):
    if B.safe_path(out).exists():
        raise FileExistsError("output_directory_exists")
    plan_raw = B.read(HERE / "plan.json")
    plan = validate_plan(B.strict_json(plan_raw))
    identity = native_identity()
    out = new_directory(out)
    files = []
    for name, raw in [("plan.json", plan_raw), ("probe.py", B.read(Path(__file__))), ("base-collector.py", B.read(BASE_PATH))]:
        B.write_new(out / name, raw); files.append(B.digest(name, raw))
    freeze = {"schema_version": 1, "files": files, "native": identity, "frozen_at": B.now()}
    B.write_new(out / "freeze.json", B.encode(freeze))
    receipt = {"schema_version": 1, "files": files, "freeze": B.digest("freeze.json", B.read(out / "freeze.json")), "stages": {}}
    native = None
    if fetch is None:
        key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
        if not key or not secret:
            B.write_new(out / "preflight-failure.json", B.encode({"reason": "missing_credentials"}))
            raise ValueError("missing_credentials")
        native = NativeIdentityPages(key, secret, plan)
        fetch = native
    results = {}
    try:
        for case_id in [c[0] for c in CASES] + ["meta_current"]:
            pages, entries, token = [], [], None
            for index in range(1 if case_id == "meta_current" else 3):
                request = query(plan, case_id, token)
                page = dict(fetch(case_id, request), request=request)
                name = f"{case_id}-{index+1:03d}.json"
                B.write_new(out / name, page["body"])
                entry = {k: v for k, v in page.items() if k != "body"} | {"source": B.digest(name, page["body"])}
                B.write_new(out / (name + ".meta.json"), B.encode(entry))
                pages.append(page); entries.append(entry)
                try:
                    validate_pages(case_id, pages, plan, terminal=False)
                    token = None if case_id == "meta_current" else B.strict_json(page["body"])["next_page_token"]
                except (ValueError, KeyError, TypeError):
                    break
                if token is None:
                    break
            results[case_id] = assess(case_id, pages, plan)
            receipt["stages"][case_id] = {"pages": entries, "assessment": results[case_id]}
    finally:
        if native:
            native.close()
    B.write_new(out / "receipt.json", B.encode(receipt))
    result = assemble(results)
    return public_summary(result, B.sha(B.read(out / "receipt.json")))


def assemble(results):
    cases = {key: results[key] for key, _, _ in CASES}
    return {"cases": cases, "asset": results["meta_current"], "comparison": comparisons(cases)}


def verify(root, expected_receipt_sha256):
    root = B.safe_path(root)
    raw = B.read(root / "receipt.json")
    if B.sha(raw) != expected_receipt_sha256:
        raise ValueError("receipt_hash_mismatch")
    receipt = B.strict_json(raw)
    files = receipt["files"]
    if [f["path"] for f in files] != ["plan.json", "probe.py", "base-collector.py"]:
        raise ValueError("unexpected_source_file_set")
    sources = {f["path"]: B.verify_blob(root, f) for f in files}
    plan = validate_plan(B.strict_json(sources["plan.json"]))
    freeze = B.strict_json(B.verify_blob(root, receipt["freeze"]))
    if freeze["files"] != files:
        raise ValueError("freeze_mismatch")
    expected_stages = [c[0] for c in CASES] + ["meta_current"]
    if set(receipt["stages"]) != set(expected_stages):
        raise ValueError("unexpected_stage_set")
    names = {"receipt.json", "freeze.json", *sources}
    results = {}
    for case_id in expected_stages:
        stage = receipt["stages"][case_id]
        pages = []
        for index, entry in enumerate(stage["pages"]):
            name = f"{case_id}-{index+1:03d}.json"
            if entry["source"]["path"] != name:
                raise ValueError("page_source_identity_mismatch")
            body = B.verify_blob(root, entry["source"])
            if B.strict_json(B.read(root / (name + ".meta.json"))) != entry:
                raise ValueError("page_metadata_mismatch")
            names.update([name, name + ".meta.json"])
            pages.append({k: v for k, v in entry.items() if k != "source"} | {"body": body})
        result = assess(case_id, pages, plan)
        if result != stage["assessment"]:
            raise ValueError("assessment_mismatch")
        results[case_id] = result
    if {p.name for p in root.iterdir()} != names:
        raise ValueError("unexpected_artifact")
    return assemble(results)


def public_summary(result, anchor):
    return {"receipt_sha256": anchor, "cases": {key: {k: v for k, v in item.items() if k != "rows"} for key, item in result["cases"].items()},
            "asset": {k: v for k, v in result["asset"].items() if k != "rows"}, "comparison": result["comparison"],
            "scope": "Retrospective alias-query observations and one current asset snapshot; no historical universe or permanent identity resolution."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("collect"); run.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("verify"); check.add_argument("--run", type=Path, required=True); check.add_argument("--receipt-sha256", required=True)
    args = parser.parse_args()
    result = collect(args.out) if args.command == "collect" else public_summary(verify(args.run, args.receipt_sha256), args.receipt_sha256)
    print(json.dumps(result, sort_keys=True))
    return 0 if all(v["status"] == "complete" for v in result["cases"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
