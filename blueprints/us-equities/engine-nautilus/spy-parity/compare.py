#!/usr/bin/env python3
"""Independent Decimal comparator: SPY parity receipt against the LEAN oracle.

Reads the replay receipt and the dated LEAN receipt, compares every reviewed
economic key for the receipt's own case with ``Decimal`` arithmetic only, prints
one PASS/FAIL line per check and a machine-readable verdict, and exits nonzero on
any deviation outside the tolerance sheet. Pure standard library: it reproduces
the comparison from retained outputs without any engine or model call.

Attribution is measured, never taken on the receipt's word. A fill-price
deviation may be labelled ``market_on_open_proxy`` only when the converted bars
show that the native fill equals that session's first-bar close while the oracle
fill equals that same bar's open. A cash deviation may be labelled only for the
part the attributed fill-price deltas (and, for the native balance, the
unposted distribution total) explain exactly. Any residue outside tolerance stays
an unattributed FAIL, and a named mapping must carry status ``unsupported`` in
the manifest the receipt was bound to or the attribution is rejected.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parent
REQUIRED_LIMITS = ("event_seconds_abs", "fill_quantity_abs", "fill_price_usd_abs", "fees_usd_abs",
                   "dividend_usd_abs", "cash_usd_abs", "end_cash_usd_abs", "final_quantity_abs")
MARKET_ON_OPEN = "market_on_open_proxy"
DISTRIBUTIONS = "distributions_and_cash"


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _decimal(value) -> Decimal:
    return Decimal(str(value).split()[0].replace(",", "").replace("_", ""))


def _int(value, code: str) -> int:
    """Strict integer projection: a fractional value is refused, not truncated."""
    found = _decimal(value)
    if found != found.to_integral_value():
        raise ValueError(code + ":" + str(value))
    return int(found)


def oracle_case(oracle: dict, case_id: str) -> dict:
    """Project the dated LEAN receipt onto the reviewed economic keys.

    The LEAN receipt stores fill instants and quantities as decimal strings such
    as ``"1577977200.0"`` and ``"304.0"``; both are projected strictly.
    """
    cases = [c for c in oracle.get("cases", []) if c.get("id") == case_id]
    if len(cases) != 1:
        raise ValueError("oracle_case_not_found:" + case_id)
    case = cases[0]
    intents = [{"utc_seconds": _int(i["utc_seconds"], "non_integral_intent_time"),
                "quantity": _int(i["quantity"], "non_integral_intent_quantity"),
                "reason": i.get("reason")} for i in case["intents"]]
    fills = [{"utc_seconds": _int(f["time"], "non_integral_fill_time"),
              "quantity": _int(f["fillQuantity"], "non_integral_fill_quantity"),
              "price": _decimal(f["fillPrice"]), "fee": _decimal(f["orderFeeAmount"])}
             for f in case["fills"]]
    projected = {
        "id": case_id, "intents": intents, "fills": fills,
        "fees_usd": _decimal(case["fees_usd"]),
        "dividends_usd": _decimal(case["dividends_usd"]),
        "end_cash_usd": _decimal(case["end_cash_usd"]),
        "final_quantity": _int(case["final_quantity"], "non_integral_final_quantity"),
        "fill_count": _int(case["fill_count"], "non_integral_fill_count"),
    }
    if len(fills) != projected["fill_count"]:
        raise ValueError("oracle_fill_count_inconsistent:" + case_id)
    return projected


def receipt_case(receipt: dict) -> dict:
    return {
        "case": receipt["case"],
        "initial_cash_usd": _decimal(receipt["case_configuration"]["initial_cash_usd"]),
        "intents": [{"utc_seconds": int(i["utc_seconds"]), "quantity": int(i["quantity"]),
                     "reason": i.get("reason")} for i in receipt["intents"]],
        "fills": [{"utc_seconds": int(f["utc_seconds"]), "quantity": int(f["quantity"]),
                   "price": _decimal(f["price"]), "fee": _decimal(f["fee"])}
                  for f in receipt["fills"]],
        "fees_usd": _decimal(receipt["fees_usd"]),
        "dividends_usd": _decimal(receipt["dividend_cash_usd"]),
        "end_cash_usd": _decimal(receipt["reconciled_end_cash_usd"]),
        "native_end_cash_usd": _decimal(receipt["native_end_cash_usd"]),
        "final_quantity": int(_decimal(receipt["final_quantity"])),
        "cash_ledger": receipt.get("cash_ledger", []),
        "distribution_ledger": receipt.get("distribution_ledger", []),
        "two_run_records_equal": bool(receipt.get("two_run_records_equal", False)),
    }


def first_bars_by_instant(rows) -> dict:
    """Map each session's first converted bar to the UTC second it completes."""
    first = {}
    for row in rows:
        first.setdefault(row["session_date"], row)
    return {row["ts_event_ns"] // 10 ** 9: row for row in first.values()}


def serialize_rows(rows) -> str:
    """Reproduce run.py's own serialization so the digest is comparable."""
    return json.dumps(rows, indent=2, sort_keys=True, default=str) + "\n"


def _convert_module():
    spec = importlib.util.spec_from_file_location("spy_parity_convert", SOURCE / "convert.py")
    convert = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(convert)
    return convert


def load_bars(bars_path, lean_data, receipt: dict, manifest: dict):
    """Converted rows, either retained from the run or re-derived from the data.

    Either way the rows are hash-bound to the digest the receipt recorded, and a
    re-derivation first verifies the five frozen LEAN input hashes. Declared
    short sessions come from the hash-bound manifest, never from the receipt.
    """
    expected = receipt["attribution_evidence"]["converted_rows_sha256"]
    if bars_path is not None:
        blob = Path(bars_path).read_bytes()
        if hashlib.sha256(blob).hexdigest() != expected:
            raise ValueError("converted_rows_sha256_mismatch")
        return json.loads(blob.decode("utf-8"))
    if lean_data is None:
        return None
    convert = _convert_module()
    observed = convert.verify_inputs(lean_data)
    if observed != receipt["inputs"]["sha256"]:
        raise ValueError("lean_input_sha256_mismatch")
    window = receipt["case_configuration"]["window"]
    short = known_short_sessions(manifest)
    rows = convert.convert(lean_data, window["symbol"], window["start"], window["end"], short)["rows"]
    if hashlib.sha256(serialize_rows(rows).encode("utf-8")).hexdigest() != expected:
        raise ValueError("rederived_rows_sha256_mismatch")
    return rows


def known_short_sessions(manifest: dict) -> dict:
    row = next(r for r in manifest["mappings"] if r["id"] == "sessions_and_time")
    return row["known_short_sessions"]


def check_local_sources(receipt: dict, source_dir=None) -> None:
    """Every harness file the receipt hashed must still be that file on disk."""
    base = Path(source_dir or SOURCE)
    for name, recorded in sorted(receipt.get("local_source_sha256", {}).items()):
        path = base / name
        if not path.is_file():
            raise ValueError("local_source_missing:" + name)
        if digest(path) != recorded:
            raise ValueError("local_source_sha256_mismatch:" + name)


def check_case_configuration(receipt: dict, manifest: dict, plan: dict) -> None:
    """Bind the run's configuration to the pinned plan and the preregistered manifest.

    Numbers the frozen plan owns are compared against the plan; choices the plan
    does not express (seed, account type, identity generation, window) are
    compared against the manifest's preregistered ``case_configuration``.
    """
    configuration = receipt["case_configuration"]
    declared = manifest["case_configuration"]
    if receipt["case"] != declared["case"]:
        raise ValueError("case_disagrees_with_manifest:" + receipt["case"])
    if receipt["frozen_plan"]["sha256"] != manifest["oracle"]["plan_sha256"]:
        raise ValueError("receipt_plan_sha256_disagrees_with_manifest")
    spec = [c for c in plan["cases"] if c["id"] == receipt["case"]]
    if len(spec) != 1:
        raise ValueError("plan_case_not_found:" + receipt["case"])
    spec = spec[0]
    for field, wanted in (("initial_cash_usd", plan["initial_cash_usd"]),
                          ("sizing_buffer", plan["requested_target_sizing_multiplier"]),
                          ("target", spec["target"]), ("fee_usd", spec["fee_usd"]),
                          ("slippage", spec["slippage"])):
        if _decimal(configuration[field]) != _decimal(wanted):
            raise ValueError("case_configuration_disagrees_with_plan:" + field)
    for field in ("seed", "account_type", "use_random_ids", "fill_model", "fee_model", "window"):
        if configuration.get(field) != declared[field]:
            raise ValueError("case_configuration_disagrees_with_manifest:" + field)


def bind(receipt: dict, tolerances_path: Path, manifest_path: Path, oracle_path=None,
         plan_path=None, source_dir=None) -> tuple:
    """Refuse a comparison whose inputs or configuration are not the run's."""
    tolerances = json.loads(Path(tolerances_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    if digest(tolerances_path) != receipt["tolerances"]["sha256"]:
        raise ValueError("tolerances_sha256_mismatch")
    if digest(manifest_path) != receipt["mapping_manifest"]["sha256"]:
        raise ValueError("mapping_manifest_sha256_mismatch")
    if oracle_path is not None and digest(oracle_path) != manifest["oracle"]["receipt_sha256"]:
        raise ValueError("oracle_receipt_sha256_mismatch")
    limits = tolerances["limits"]
    if set(limits) != set(REQUIRED_LIMITS):
        raise ValueError("tolerance_sheet_keys:" + ",".join(sorted(set(limits) ^ set(REQUIRED_LIMITS))))
    if receipt["unsupported_mappings"] != sorted(_unsupported_ids(manifest)):
        raise ValueError("receipt_unsupported_mappings_disagree_with_manifest")
    if receipt["engine"]["version"] != manifest["engine"]["version"]:
        raise ValueError("engine_version_disagrees_with_manifest:" + receipt["engine"]["version"])
    if receipt["evidence_class"] != manifest["evidence_class"]:
        raise ValueError("evidence_class_disagrees_with_manifest:" + receipt["evidence_class"])
    check_local_sources(receipt, source_dir)
    if plan_path is not None:
        if digest(plan_path) != manifest["oracle"]["plan_sha256"]:
            raise ValueError("plan_sha256_mismatch")
        check_case_configuration(receipt, manifest, json.loads(Path(plan_path).read_text()))
    return limits, manifest


def _record(checks, entry):
    """Every check carries a unique key so a failure can never be ambiguous."""
    entry["ordinal"] = len(checks) + 1
    entry["key"] = entry["id"] + "." + entry["field"] + "#" + str(entry["ordinal"])
    checks.append(entry)
    return entry


def _check(checks, key, field, expected, observed, limit, blocked_by=None):
    expected_d, observed_d = Decimal(expected), Decimal(observed)
    delta = observed_d - expected_d
    status = "PASS" if abs(delta) <= Decimal(limit) else "FAIL"
    return _record(checks, {"id": key, "field": field, "expected": str(expected_d),
                            "observed": str(observed_d), "delta": str(delta),
                            "tolerance": str(Decimal(limit)), "status": status,
                            "blocked_by": blocked_by if status == "FAIL" else None})


def _event_name(kind: str, index: int, reason) -> str:
    return (str(reason) + "_" + kind) if reason else (kind + "_" + str(index + 1))


def _unsupported_ids(manifest) -> set:
    if not manifest:
        return set()
    return {row["id"] for row in manifest.get("mappings", []) if row.get("status") == "unsupported"}


def _attribution(mappings, declared: set):
    """A mapping may only be named if the bound manifest declares it unsupported."""
    named = sorted({m for m in mappings if m})
    if not named or any(m not in declared for m in named):
        return None, sorted(m for m in named if m not in declared)
    return ",".join(named), []


def recompute_cash_ledger(initial: Decimal, fills, distributions) -> list:
    """Independent reconstruction of the cash path from fills and distributions."""
    events = [{"kind": "fill", "utc_seconds": f["utc_seconds"],
               "delta": -Decimal(f["quantity"]) * Decimal(f["price"]) - Decimal(f["fee"])}
              for f in fills]
    events += [{"kind": "distribution", "utc_seconds": int(d["utc_seconds"]),
                "delta": Decimal(str(d["amount"]))} for d in distributions]
    events.sort(key=lambda e: (e["utc_seconds"], 0 if e["kind"] == "distribution" else 1))
    cash, ledger = Decimal(initial), []
    for event in events:
        cash += event["delta"]
        ledger.append({"kind": event["kind"], "utc_seconds": event["utc_seconds"], "cash": cash})
    return ledger


def compare(receipt: dict, oracle: dict, limits: dict, manifest=None, bars=None) -> dict:
    """Compare reviewed economic keys. Returns a machine-readable verdict."""
    observed, expected = receipt_case(receipt), oracle
    if observed["case"] != expected["id"]:
        raise ValueError("case_mismatch:" + observed["case"] + "!=" + expected["id"])
    declared = _unsupported_ids(manifest)
    # An empty bar list is evidence that cannot attribute anything, exactly like
    # no bar list at all; both take the SKIPPED path rather than silently
    # behaving as if attribution had been attempted.
    evidence_available = bars is not None and len(bars) > 0
    first_bars = first_bars_by_instant(bars) if evidence_available else None
    checks: list[dict] = []
    rejected: list[str] = []

    _check(checks, "intent_count", "count", len(expected["intents"]), len(observed["intents"]), "0")
    _check(checks, "fill_count", "count", expected["fill_count"], len(observed["fills"]), "0")
    _check(checks, "extra_fills", "fills_beyond_oracle", 0,
           max(0, len(observed["fills"]) - expected["fill_count"]), "0")
    _check(checks, "missing_fills", "oracle_fills_absent", 0,
           max(0, expected["fill_count"] - len(observed["fills"])), "0")

    for index in range(min(len(expected["intents"]), len(observed["intents"]))):
        want, got = expected["intents"][index], observed["intents"][index]
        name = _event_name("intent", index, want.get("reason"))
        _check(checks, name, "utc_seconds", want["utc_seconds"], got["utc_seconds"],
               limits["event_seconds_abs"])
        _check(checks, name, "signed_quantity", want["quantity"], got["quantity"],
               limits["fill_quantity_abs"])

    explained_fill = Decimal(0)
    unexplained_fill = Decimal(0)
    fill_attributions = set()
    for index in range(min(len(expected["fills"]), len(observed["fills"]))):
        want, got = expected["fills"][index], observed["fills"][index]
        reason = expected["intents"][index].get("reason") if index < len(expected["intents"]) else None
        name = _event_name("fill", index, reason)
        _check(checks, name, "utc_seconds", want["utc_seconds"], got["utc_seconds"],
               limits["event_seconds_abs"])
        quantity_ok = _check(checks, name, "signed_quantity", want["quantity"], got["quantity"],
                             limits["fill_quantity_abs"])["status"] == "PASS"
        fee_ok = _check(checks, name, "fee_usd", want["fee"], got["fee"],
                        limits["fees_usd_abs"])["status"] == "PASS"

        # Measured attribution: the native fill must be this session's first-bar
        # close and the oracle fill that same bar's open. Nothing else qualifies.
        measured = None
        bar = first_bars.get(got["utc_seconds"]) if first_bars else None
        if bar is not None and got["price"] == Decimal(bar["c"]) and want["price"] == Decimal(bar["o"]):
            measured = MARKET_ON_OPEN
        label, bad = _attribution([measured], declared)
        rejected += bad
        price_check = _check(checks, name, "fill_price_usd", want["price"], got["price"],
                             limits["fill_price_usd_abs"], blocked_by=label)
        if price_check["blocked_by"]:
            price_check["evidence"] = {"session_date": bar["session_date"],
                                       "first_bar_open": bar["o"], "first_bar_close": bar["c"]}
        contribution = (-Decimal(got["quantity"]) * got["price"] - got["fee"]) - \
                       (-Decimal(want["quantity"]) * want["price"] - want["fee"])
        if price_check["blocked_by"] and quantity_ok and fee_ok:
            explained_fill += contribution
            fill_attributions.add(MARKET_ON_OPEN)
        else:
            unexplained_fill += contribution

    _check(checks, "fees_total", "fees_usd", expected["fees_usd"], observed["fees_usd"],
           limits["fees_usd_abs"])
    _check(checks, "distributions_total", "dividend_cash_usd", expected["dividends_usd"],
           observed["dividends_usd"], limits["dividend_usd_abs"])

    # Independent reconstruction of the cash path from the receipt's own fills
    # and distributions. Every headline balance is reconciled against it before
    # it is allowed to stand in for the run against the oracle.
    rebuilt = recompute_cash_ledger(observed["initial_cash_usd"], observed["fills"],
                                    observed["distribution_ledger"])
    rebuilt_end = rebuilt[-1]["cash"] if rebuilt else observed["initial_cash_usd"]
    ledger = observed["distribution_ledger"]
    ledger_sum = sum((Decimal(str(d["amount"])) for d in ledger), Decimal(0))
    unposted_sum = sum((Decimal(str(d["amount"])) for d in ledger
                        if d.get("engine_posted") is False), Decimal(0))
    _check(checks, "end_cash_internal", "reconciled_vs_rebuilt_ledger", rebuilt_end,
           observed["end_cash_usd"], limits["cash_usd_abs"])
    # The native balance is the reconciled path minus whatever the engine did
    # not post. This identity holds for an empty, fully unposted or mixed ledger.
    _check(checks, "native_end_cash_internal", "native_vs_rebuilt_ledger",
           rebuilt_end - unposted_sum, observed["native_end_cash_usd"], limits["cash_usd_abs"])

    # Reconciled cash: only the attributed fill-price deltas may explain it.
    end_tolerance = Decimal(limits["end_cash_usd_abs"])
    delta_end = observed["end_cash_usd"] - expected["end_cash_usd"]
    residue_end = delta_end - explained_fill
    label_end, bad = _attribution(sorted(fill_attributions) if abs(residue_end) <= end_tolerance
                                  else [], declared)
    rejected += bad
    end_check = _check(checks, "end_cash", "reconciled_end_cash_usd", expected["end_cash_usd"],
                       observed["end_cash_usd"], limits["end_cash_usd_abs"], blocked_by=label_end)
    end_check["explained_by_fill_prices"] = str(explained_fill)
    end_check["unexplained_residue"] = str(residue_end)

    # Native balance: distributions_and_cash may claim the unposted total only
    # when the ledger says every entry is unposted and its sum matches exactly.
    all_unposted = bool(ledger) and all(d.get("engine_posted") is False for d in ledger)
    unposted_total = ledger_sum if all_unposted and ledger_sum == observed["dividends_usd"] \
        else Decimal(0)
    delta_native = observed["native_end_cash_usd"] - expected["end_cash_usd"]
    residue_native = delta_native - explained_fill + unposted_total
    native_parts = sorted(fill_attributions)
    if unposted_total != 0:
        native_parts = native_parts + [DISTRIBUTIONS]
    label_native, bad = _attribution(native_parts if abs(residue_native) <= end_tolerance else [],
                                     declared)
    rejected += bad
    native_check = _check(checks, "native_end_cash", "native_end_cash_usd", expected["end_cash_usd"],
                          observed["native_end_cash_usd"], limits["end_cash_usd_abs"],
                          blocked_by=label_native)
    native_check["explained_by_fill_prices"] = str(explained_fill)
    native_check["explained_by_unposted_distributions"] = str(-unposted_total)
    native_check["distribution_ledger_all_unposted"] = all_unposted
    native_check["distribution_ledger_sum_matches"] = ledger_sum == observed["dividends_usd"]
    native_check["unexplained_residue"] = str(residue_native)

    _check(checks, "final_quantity", "shares", expected["final_quantity"], observed["final_quantity"],
           limits["final_quantity_abs"])

    _check(checks, "cash_ledger_events", "count", len(rebuilt), len(observed["cash_ledger"]), "0")
    for index in range(min(len(rebuilt), len(observed["cash_ledger"]))):
        entry = observed["cash_ledger"][index]
        _check(checks, "cash_ledger[" + str(index) + "]", rebuilt[index]["kind"] + "@" +
               str(rebuilt[index]["utc_seconds"]), rebuilt[index]["cash"], _decimal(entry["cash"]),
               limits["cash_usd_abs"])
        if int(entry["utc_seconds"]) != rebuilt[index]["utc_seconds"] or \
                entry["kind"] != rebuilt[index]["kind"]:
            _record(checks, {"id": "cash_ledger[" + str(index) + "]", "field": "event_identity",
                             "expected": rebuilt[index]["kind"] + "@" + str(rebuilt[index]["utc_seconds"]),
                             "observed": str(entry["kind"]) + "@" + str(entry["utc_seconds"]),
                             "delta": "-", "tolerance": "exact", "status": "FAIL",
                             "blocked_by": None})

    _record(checks, {"id": "two_run_determinism", "field": "normalized_economic_sha256",
                     "expected": "equal",
                     "observed": "equal" if observed["two_run_records_equal"] else "differs",
                     "delta": "-", "tolerance": "exact",
                     "status": "PASS" if observed["two_run_records_equal"] else "FAIL",
                     "blocked_by": None})
    if not evidence_available:
        # Not a PASS: the check could not be performed, and saying otherwise
        # would read as evidence that attribution had been verified.
        _record(checks, {"id": "attribution_evidence", "field": "converted_bars",
                         "expected": "available",
                         "observed": "absent" if bars is None else "empty", "delta": "-",
                         "tolerance": "exact", "status": "SKIPPED", "blocked_by": None,
                         "reason": ("No converted bars supplied" if bars is None else
                                    "Converted bar list is empty") +
                                   ", so no deviation could be attributed; every deviation is "
                                   "an unattributed FAIL."})

    failures = [c for c in checks if c["status"] == "FAIL"]
    skipped = [c["key"] for c in checks if c["status"] == "SKIPPED"]
    blocked = sorted({m for c in failures if c["blocked_by"] for m in c["blocked_by"].split(",")})
    unattributed = [c["key"] for c in failures if not c["blocked_by"]]
    # A skipped check or a rejected attribution means the comparison was not
    # completed, so it can never reach PASS however few checks failed.
    if failures and (unattributed or rejected):
        outcome = "FAIL"
    elif failures:
        outcome = "BLOCKED-INCOMPLETE" if skipped else "BLOCKED"
    elif skipped or rejected:
        outcome = "BLOCKED-INCOMPLETE"
    else:
        outcome = "PASS"
    return {"case": expected["id"], "checks": checks, "failed": len(failures),
            "skipped": skipped, "verdict": outcome, "complete": not (skipped or rejected),
            "blocking_mappings": blocked, "unattributed_failures": unattributed,
            "rejected_attributions": sorted(set(rejected)),
            "manifest_unsupported_mappings": sorted(declared),
            "attribution_evidence": "converted bars" if evidence_available else "none",
            "native_end_cash_usd": str(observed["native_end_cash_usd"]),
            "note": "A failure is BLOCKED only when a measured deviation matches a mapping the bound "
                    "manifest declares unsupported. Any residue stays an unattributed FAIL, and a "
                    "skipped check or rejected attribution leaves the comparison incomplete."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True, help="Replay receipt.json from run.py")
    parser.add_argument("--oracle", type=Path,
                        default=SOURCE.parent.parent / "historical-simulation/receipt.json")
    parser.add_argument("--tolerances", type=Path, default=SOURCE / "tolerances.json")
    parser.add_argument("--manifest", type=Path, default=SOURCE / "mapping-manifest.json")
    parser.add_argument("--plan", type=Path,
                        default=SOURCE.parent.parent / "historical-simulation/plan.json")
    parser.add_argument("--bars", type=Path,
                        help="converted-rows.private.json from the run, for measured attribution")
    parser.add_argument("--lean-data", type=Path,
                        help="Retained LEAN Data root; re-derives the bars instead of --bars")
    parser.add_argument("--case", help="Optional: must equal the receipt's own case")
    parser.add_argument("--verdict", type=Path, help="Optional path for the machine-readable verdict")
    args = parser.parse_args()

    receipt = json.loads(args.receipt.read_text())
    if args.case and args.case != receipt["case"]:
        raise ValueError("requested_case_is_not_the_receipt_case:" + args.case)
    limits, manifest = bind(receipt, args.tolerances, args.manifest, args.oracle, args.plan)
    oracle = oracle_case(json.loads(args.oracle.read_text()), receipt["case"])
    bars = load_bars(args.bars, args.lean_data, receipt, manifest)
    verdict = compare(receipt, oracle, limits, manifest, bars)

    for check in verdict["checks"]:
        suffix = "" if not check["blocked_by"] else "  blocked_by=" + check["blocked_by"]
        if check["status"] == "SKIPPED":
            suffix = "  reason=" + check.get("reason", "")
        print("{status:<7} {id:<20} {field:<26} expected={expected:<14} observed={observed:<14} "
              "delta={delta:<12} tol={tolerance}{suffix}".format(suffix=suffix, **check))
    print("VERDICT " + json.dumps({k: v for k, v in verdict.items() if k != "checks"}, sort_keys=True))
    if args.verdict:
        args.verdict.write_text(json.dumps(verdict, indent=2, sort_keys=True, default=str) + "\n")
    # Only a complete comparison with no failing check exits zero.
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
