#!/usr/bin/env python3
"""Anchored quality derivation and explicit bounded continuation; old probe is unchanged."""
import argparse
from datetime import datetime
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("quality_original_probe", HERE / "probe.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
B = P.B
POLICY = {"id": "reported-activity-quality-v1", "zero_activity": "Numeric v=n=vw=0 is reported zero activity; local price-observation quarantine, origin/market activity/tradability unknown.",
          "documentation_discrepancy": "The stock FAQ requires nonzero emitted volume. Reported zero volume conflicts with that rule; crypto midpoint semantics are not applied.",
          "other_zero_activity_fields": "Any other zero in v/n/vw is also quarantined.",
          "resume_case": "meta_unmapped", "max_total_pages_for_case": 3, "max_additional_pages": 2,
          "max_total_http_attempts": 13, "no_retries_or_refetch": True}


def normalized_bar(row, case, page, plan, phase):
    """Explicit nonnegative VWAP adaptation; source bytes are never substituted."""
    if not isinstance(row, dict) or not {"t", *P.FIELDS} <= row.keys():
        raise ValueError("malformed_bar_fields")
    event = P.ns(row["t"])
    if not P.ns(plan["start_inclusive"]) <= event < P.ns(plan["end_exclusive"]):
        raise ValueError("bar_outside_window")
    seconds, remainder = divmod(event, 10**9)
    local = datetime.fromtimestamp(seconds, B.UTC).astimezone(ZoneInfo("America/New_York"))
    if remainder or (local.hour, local.minute, local.second) != (0, 0, 0):
        raise ValueError("daily_bar_not_exchange_midnight")
    values = {f: B.number(row[f], integer=f == "n", positive=f in {"o", "h", "l", "c"}) for f in P.FIELDS}
    if Decimal(values["l"]) > min(Decimal(values["o"]), Decimal(values["c"])) or Decimal(values["h"]) < max(Decimal(values["o"]), Decimal(values["c"]), Decimal(values["l"])):
        raise ValueError("invalid_ohlc_order")
    zero = all(Decimal(values[f]) == 0 for f in ["v", "n", "vw"])
    qualified = all(Decimal(values[f]) > 0 for f in ["v", "n", "vw"])
    quality = "qualified_observation" if qualified else "quarantined_reported_zero_activity" if zero else "quarantined_inconsistent_activity"
    return {**values, "case_id": case["case_id"], "requested_symbol": case["symbol"], "returned_symbol": case["symbol"], "request_asof": case["asof"],
            "event_at": row["t"], "event_ns": event, "session_date": local.date().isoformat(),
            "observed_ns": P.ns(page["observed_at"]), "available_ns": P.ns(page["observed_at"]),
            "valid_from": None, "valid_to": None, "original_publication_at": None, "provider_revision_at": None,
            "permanent_security_id": None, "quality": quality, "reported_zero_activity": zero,
            "price_observation_qualified": qualified, "source_phase": phase, **B.source_anchor(page)}


def parse_case(case_id, pages, plan, original_status):
    case = next(c for c in plan["cases"] if c["case_id"] == case_id)
    token, tokens, identities, rows, previous = None, set(), set(), [], None
    if not pages or len(pages) > 3:
        raise ValueError("invalid_page_count")
    for index, page in enumerate(pages):
        body = P.envelope(page, P.query(plan, case_id, token), plan["bars_url"])
        if previous is not None and P.ns(page["started_at"]) < previous:
            raise ValueError("nonsequential_observation_interval")
        previous = P.ns(page["observed_at"])
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
        raw_rows = groups.get(case["symbol"], [])
        if not isinstance(raw_rows, list) or len(raw_rows) > 2:
            raise ValueError("invalid_page_rows")
        for raw in raw_rows:
            row = normalized_bar(raw, case, page, plan, page["source_phase"])
            if row["event_ns"] in identities:
                raise ValueError("duplicate_bar")
            if rows and row["event_ns"] < rows[-1]["event_ns"]:
                raise ValueError("unordered_bars")
            identities.add(row["event_ns"]); rows.append(row)
    complete = token is None
    return {"status": "complete" if complete else "partial", "source_status": original_status,
            "normalization_status": "passed", "summary": {"pages": len(pages), "rows": len(rows),
            "qualified_rows": sum(r["price_observation_qualified"] for r in rows), "quarantined_rows": sum(not r["price_observation_qualified"] for r in rows),
            "documentation_discrepancy_rows": sum(Decimal(r["v"]) == 0 for r in rows),
            "query_complete": complete, "session_dates": [r["session_date"] for r in rows]}, "rows": rows}


def assess(case_id, pages, plan, original_status):
    try:
        return parse_case(case_id, pages, plan, original_status)
    except (ValueError, KeyError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"[a-z_0-9]+", str(exc)) else "malformed_structure"
        # Preserve the validated prefix when a new page fails; its original
        # observations do not disappear because a continuation was refused.
        rows = []
        for length in range(len(pages)-1, 0, -1):
            try:
                rows = parse_case(case_id, pages[:length], plan, original_status)["rows"]
                break
            except (ValueError, KeyError, TypeError):
                continue
        return {"status": "failed", "source_status": original_status, "reason": reason,
                "normalization_status": "failed", "summary": {"pages": len(pages), "rows": len(rows),
                "qualified_rows": sum(r["price_observation_qualified"] for r in rows),
                "quarantined_rows": sum(not r["price_observation_qualified"] for r in rows), "query_complete": False}, "rows": rows}


def original_pages(source, receipt):
    return {case_id: [{k: v for k, v in entry.items() if k != "source"} |
                     {"body": B.verify_blob(source, entry["source"]), "source_phase": "original_capture"}
                     for entry in receipt["stages"][case_id]["pages"]] for case_id, _, _ in P.CASES}


def assemble(original, pages, plan, anchor, runtime):
    cases = {case_id: assess(case_id, pages[case_id], plan, original["cases"][case_id]["status"]) for case_id, _, _ in P.CASES}
    comparison = P.comparisons(cases)
    reference = {r["session_date"]: r for r in cases["meta_mapped"]["rows"]}
    unmapped = [r for name in ["meta_unmapped", "fb_unmapped"] for r in cases[name]["rows"]]
    pairs = [(r, reference[r["session_date"]]) for r in unmapped if r["session_date"] in reference]
    groups = {}
    for row in unmapped:
        groups.setdefault(row["session_date"], []).append(row)
    comparison["unmapped_observations_vs_meta_mapped"] = {
        "compared_observations": len(pairs), "missing_reference_observations": len(unmapped)-len(pairs),
        "equal_observations": sum(all(Decimal(a[f]) == Decimal(b[f]) for f in P.FIELDS) for a, b in pairs),
        "field_mismatches": {f: sum(Decimal(a[f]) != Decimal(b[f]) for a, b in pairs) for f in P.FIELDS},
        "overlap_date_count": sum(len(g) > 1 for g in groups.values()),
        "ambiguous_date_count": sum(len(g) > 1 and any(any(Decimal(r[f]) != Decimal(g[0][f]) for f in P.FIELDS) for r in g[1:]) for g in groups.values()),
        "basis": "Each unmapped query observation compared separately; conflicting values on an overlapping date remain distinct, including quarantined rows."}
    return {"original_receipt_sha256": anchor, "original_probe_exit": 0 if all(v["status"] == "complete" for v in original["cases"].values()) else 1,
            "continuation_runtime": runtime,
            "original_case_statuses": {k: {f: v[f] for f in ["status", "reason"] if f in v} for k, v in original["cases"].items()},
            "cases": cases, "asset": original["asset"], "comparison": comparison}


def derive(source, expected_receipt_sha256, out, *, resume=False, fetch=None):
    source, out = B.safe_path(source), B.safe_path(out)
    if out.exists():
        raise FileExistsError("output_directory_exists")
    P.verify(source, expected_receipt_sha256)
    out = P.new_directory(out)
    copied = out / "original"
    copied.mkdir(mode=0o700)
    for path in sorted(source.iterdir()):
        B.write_new(copied / path.name, B.read(path))
    original = P.verify(copied, expected_receipt_sha256)
    receipt = B.strict_json(B.read(copied / "receipt.json"))
    plan = P.validate_plan(B.strict_json(B.read(copied / "plan.json")))
    pages = original_pages(copied, receipt)
    count = sum(len(s["pages"]) for s in receipt["stages"].values())
    if count > 13:
        raise ValueError("original_attempt_bound_exceeded")
    for name, raw in [("quality.py", B.read(Path(__file__))), ("probe.py", B.read(HERE / "probe.py")), ("base-collector.py", B.read(P.BASE_PATH)), ("policy.json", B.encode(POLICY))]:
        B.write_new(out / name, raw)
    token, remaining = None, 0
    if resume:
        parse_case("meta_unmapped", pages["meta_unmapped"], plan, original["cases"]["meta_unmapped"]["status"])
        token = B.strict_json(pages["meta_unmapped"][-1]["body"])["next_page_token"]
        remaining = min(2, 3-len(pages["meta_unmapped"]), 13-count)
    runtime = {"transport_kind": "not_requested" if not resume else "no_request_needed"}
    if token is not None and remaining > 0:
        runtime = ({"transport_kind": "injected_test"} if fetch is not None else
                   {"transport_kind": "native", "identity": P.native_identity()})
    frozen = [B.digest(str(p.relative_to(out)), B.read(p)) for p in sorted(out.rglob("*")) if p.is_file()]
    B.write_new(out / "freeze.json", B.encode({"original_receipt_sha256": expected_receipt_sha256, "files": frozen, "resume_requested": resume, "continuation_runtime": runtime, "frozen_at": B.now()}))
    entries, native = [], None
    if resume:
        case_id = "meta_unmapped"
        if token is not None and remaining > 0:
            if fetch is None:
                key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
                if not key or not secret:
                    raise ValueError("missing_credentials")
                native = P.NativeIdentityPages(key, secret, plan)
                fetch = native
            try:
                for index in range(remaining):
                    request = P.query(plan, case_id, token)
                    page = dict(fetch(case_id, request), request=request, source_phase="continuation")
                    name = f"continuation-{index+1:03d}.json"
                    B.write_new(out / name, page["body"])
                    entry = {k: v for k, v in page.items() if k != "body"} | {"source": B.digest(name, page["body"])}
                    B.write_new(out / (name + ".meta.json"), B.encode(entry))
                    entries.append(entry); pages[case_id].append(page)
                    try:
                        parse_case(case_id, pages[case_id], plan, original["cases"][case_id]["status"])
                        token = B.strict_json(page["body"])["next_page_token"]
                    except (ValueError, KeyError, TypeError):
                        break
                    if token is None:
                        break
            finally:
                if native:
                    native.close()
    result = assemble(original, pages, plan, expected_receipt_sha256, runtime)
    files = [B.digest(str(p.relative_to(out)), B.read(p)) for p in sorted(out.rglob("*")) if p.is_file()]
    derived = {"schema_version": 1, "contract": POLICY["id"], "original_receipt_sha256": expected_receipt_sha256,
               "continuation_pages": entries, "files": files, "assessment": result}
    B.write_new(out / "receipt.json", B.encode(derived))
    return public_summary(result, B.sha(B.read(out / "receipt.json")), len(entries))


def verified_files(root, entries):
    files = {}
    for entry in entries:
        name = entry["path"]
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts or name in files:
            raise ValueError("unsafe_or_duplicate_artifact")
        raw = B.read(root / name)
        if len(raw) != entry["bytes"] or B.sha(raw) != entry["sha256"]:
            raise ValueError("artifact_hash_mismatch")
        files[name] = raw
    return files


def verify(root, expected_receipt_sha256):
    root = B.safe_path(root)
    raw = B.read(root / "receipt.json")
    if B.sha(raw) != expected_receipt_sha256:
        raise ValueError("receipt_hash_mismatch")
    receipt = B.strict_json(raw)
    if receipt["contract"] != POLICY["id"]:
        raise ValueError("unsupported_quality_contract")
    files = verified_files(root, receipt["files"])
    if {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} != {"receipt.json", *files}:
        raise ValueError("unexpected_quality_artifact")
    if any(p.is_symlink() or (p.is_dir() and p != root / "original") for p in root.rglob("*")):
        raise ValueError("unexpected_quality_directory")
    original = P.verify(root / "original", receipt["original_receipt_sha256"])
    source = B.strict_json(files["original/receipt.json"])
    plan = P.validate_plan(B.strict_json(files["original/plan.json"]))
    pages = original_pages(root / "original", source)
    freeze = B.strict_json(files["freeze.json"])
    runtime = freeze["continuation_runtime"]
    kind = runtime["transport_kind"]
    if kind not in {"native", "injected_test", "not_requested", "no_request_needed"}:
        raise ValueError("unsupported_continuation_transport")
    if kind == "native":
        identity = runtime["identity"]
        if identity["alpaca_py_version"] != "0.44.0" or not isinstance(identity["requests_version"], str) or not identity["sources"]:
            raise ValueError("invalid_retained_native_identity")
        for entry in identity["sources"]:
            if not isinstance(entry["path"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) or type(entry["bytes"]) is not int or entry["bytes"] <= 0:
                raise ValueError("invalid_retained_native_identity")
    elif set(runtime) != {"transport_kind"}:
        raise ValueError("unexpected_non_native_identity")
    frozen = verified_files(root, freeze["files"])
    if freeze["original_receipt_sha256"] != receipt["original_receipt_sha256"] or frozen["policy.json"] != B.encode(POLICY):
        raise ValueError("quality_freeze_mismatch")
    for name, path in [("quality.py", Path(__file__)), ("probe.py", HERE / "probe.py"), ("base-collector.py", P.BASE_PATH)]:
        if files[name] != B.read(path):
            raise ValueError("quality_bridge_version_mismatch")
    entries = receipt["continuation_pages"]
    if entries and kind not in {"native", "injected_test"}:
        raise ValueError("continuation_runtime_missing")
    if (entries and freeze["resume_requested"] is not True) or len(entries) > 2 or len(pages["meta_unmapped"])+len(entries) > 3 or sum(len(s["pages"]) for s in source["stages"].values())+len(entries) > 13:
        raise ValueError("continuation_bound_exceeded")
    expected = {*frozen, "freeze.json"}
    for index, entry in enumerate(entries):
        name = f"continuation-{index+1:03d}.json"
        if entry["source"]["path"] != name or entry["source_phase"] != "continuation" or B.strict_json(files[name+".meta.json"]) != entry:
            raise ValueError("continuation_metadata_mismatch")
        body = B.verify_blob(root, entry["source"])
        pages["meta_unmapped"].append({k: v for k, v in entry.items() if k != "source"} | {"body": body})
        expected.update([name, name+".meta.json"])
    if expected != set(files):
        raise ValueError("unexpected_quality_payload_set")
    result = assemble(original, pages, plan, receipt["original_receipt_sha256"], runtime)
    if result != receipt["assessment"]:
        raise ValueError("quality_assessment_mismatch")
    return result


def public_summary(result, anchor, additional_pages):
    summary = P.public_summary(result, anchor)
    return dict(summary, original_receipt_sha256=result["original_receipt_sha256"], original_probe_exit=result["original_probe_exit"],
                original_case_statuses=result["original_case_statuses"], additional_http_attempts=additional_pages,
                continuation_transport_kind=result["continuation_runtime"]["transport_kind"],
                policy=POLICY["id"], zero_activity_origin_known=False, trade_fill_eligibility_established=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["derive", "resume"]:
        p = sub.add_parser(command); p.add_argument("--source", type=Path, required=True); p.add_argument("--receipt-sha256", required=True); p.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("verify"); check.add_argument("--run", type=Path, required=True); check.add_argument("--receipt-sha256", required=True)
    args = parser.parse_args()
    if args.command == "verify":
        result = verify(args.run, args.receipt_sha256)
        count = len(B.strict_json(B.read(args.run / "receipt.json"))["continuation_pages"])
        result = public_summary(result, args.receipt_sha256, count)
    else:
        result = derive(args.source, args.receipt_sha256, args.out, resume=args.command == "resume")
    print(json.dumps(result, sort_keys=True))
    return 0 if all(c["status"] == "complete" for c in result["cases"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
