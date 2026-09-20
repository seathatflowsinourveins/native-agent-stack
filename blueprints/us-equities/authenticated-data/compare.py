#!/usr/bin/env python3
"""Compare verified private provider data to the frozen LEAN probe, in memory.

Only aggregate counts and integrity hashes leave this command. Neither matching
prices nor revisions establish original historical availability or data rights.
"""
import argparse
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import importlib.util
import json
from pathlib import Path


def load_collector():
    path = Path(__file__).resolve().parents[1] / "alpaca-historical" / "collect.py"
    spec = importlib.util.spec_from_file_location("historical_collector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def numeric(value, *, allow_zero=False):
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError("invalid_decimal_text")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid_decimal_text") from None
    if not number.is_finite() or number < 0 or (number == 0 and not allow_zero) or abs(number.adjusted()) > 30:
        raise ValueError("invalid_positive_decimal")
    return number


def keyed(rows, date_key, symbol_key):
    result = {}
    for row in rows:
        key = row[date_key]
        if row[symbol_key] != "AAPL" or key in result:
            raise ValueError("duplicate_date_or_wrong_symbol")
        result[key] = row
    return result


def compare(lean, stages):
    reference = keyed(lean["observations"], "date", "mapped_symbol")
    if lean["symbol"] != "AAPL" or len(reference) != 25:
        raise ValueError("unsupported_lean_reference")
    for row in reference.values():
        numeric(row["raw_close"])
    result = {"reference_sessions": len(reference), "basis": "raw daily close by New York session date",
              "original_historical_availability": "not_established", "strategy_or_return_computed": False}
    bars = stages["bars"]
    if bars["status"] != "complete":
        result["bars"] = {"status": "unavailable", "reason": bars.get("reason", "stage_failed"), "compared": 0}
    else:
        actual = keyed(bars["rows"], "session_date", "symbol")
        common = sorted(reference.keys() & actual.keys())
        with localcontext() as context:
            context.prec = 200
            deltas = [numeric(actual[d]["c"]) - numeric(reference[d]["raw_close"]) for d in common]
        missing, extra = len(reference.keys() - actual.keys()), len(actual.keys() - reference.keys())
        mismatches = sum(d != 0 for d in deltas)
        result["bars"] = {"status": "equal" if not (missing or extra or mismatches) else "differences",
                          "compared": len(common), "equal": len(common) - mismatches,
                          "different": mismatches, "missing": missing, "extra": extra,
                          "maximum_absolute_close_difference": str(max(d.copy_abs() for d in deltas)) if deltas else None}
    actions = stages["actions"]
    if actions["status"] != "complete":
        result["actions"] = {"status": "unavailable", "reason": actions.get("reason", "stage_failed"), "compared": 0}
    else:
        counts = {"equal": 0, "different": 0, "missing": 0, "ambiguous": 0, "unknown_currency": 0}
        numeric_matches = 0
        for event in lean["events"]:
            kind = {"dividend": "cash_dividend", "split": "forward_split"}[event["kind"]]
            candidates = [r for r in actions["rows"] if r["type"] == kind and r.get("ex_date") == event["date"]
                          and r.get("qualification") == "qualified" and r.get("symbol") == "AAPL"]
            if len(candidates) != 1:
                counts["ambiguous" if candidates else "missing"] += 1
                continue
            row = candidates[0]
            with localcontext() as context:
                context.prec = 200
                value_equal = (numeric(row["rate"], allow_zero=True) == numeric(event["distribution"], allow_zero=True)) if kind == "cash_dividend" else (
                    numeric(row["old_rate"]) == numeric(event["factor"]) * numeric(row["new_rate"]))
            numeric_matches += value_equal
            if kind == "cash_dividend" and row.get("currency") is None:
                counts["unknown_currency"] += 1
            else:
                equal = value_equal and (kind != "cash_dividend" or row["currency"] == "USD")
                counts["equal" if equal else "different"] += 1
        result["actions"] = {"status": "equal" if counts["equal"] == len(lean["events"]) else "reconciliation_incomplete",
                             "reference_events": len(lean["events"]), "provider_records": len(actions["rows"]),
                             "compared": counts["equal"] + counts["different"] + counts["unknown_currency"],
                             "numeric_values_equal": numeric_matches, **counts,
                             "scope": "qualified ex-date/type candidates; cash per raw share and old/new split ratio; process-date window may omit events"}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--lean-sha256", required=True)
    args = parser.parse_args()
    collector = load_collector()
    raw = collector.read(args.lean)
    if hashlib.sha256(raw).hexdigest() != args.lean_sha256:
        raise ValueError("lean_reference_hash_mismatch")
    stages = collector.verify(args.run, args.receipt_sha256)
    result = compare(collector.strict_json(raw), stages)
    result["input_hashes"] = {"alpaca_receipt": args.receipt_sha256, "lean_native_results": args.lean_sha256,
                              "comparison_code": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
