"""Reconcile native exported values. No price-path simulation or performance selection."""
from decimal import Decimal
from collections import Counter


def number(value):
    result = Decimal(str(value).replace("$", "").replace(",", ""))
    if not result.is_finite():
        raise ValueError("nonfinite number")
    return result


def summarize(summary, events, audit, *, rejected, adaptive, orders):
    state, stats = summary["state"], summary["statistics"]
    if state.get("Status") != "Completed" or state.get("RuntimeError"):
        raise ValueError("native algorithm failed")
    if any(e["status"] not in {"submitted", "filled", "invalid"} for e in events):
        raise ValueError("unexpected order status")
    fills = [e for e in events if e["status"] == "filled"]
    invalid = [e for e in events if e["status"] == "invalid"]
    intents = {r["order_id"]: r for r in audit if r["kind"] == "intent"}
    margin_calls = [r for r in audit if r["kind"] == "margin_call"]
    reductions = [r for r in audit if r["kind"] == "reduction"]
    if len(intents) != sum(r["kind"] == "intent" for r in audit):
        raise ValueError("duplicate intent")
    if adaptive and len(reductions) != 1:
        raise ValueError("expected exactly one adaptive reduction")
    if not adaptive and reductions:
        raise ValueError("unexpected reduction")
    if rejected:
        if fills or len(invalid) != 1 or len(intents) != 1:
            raise ValueError("over-limit must yield one rejection and zero fills")
        messages = [str(e.get("message", "")) for e in invalid]
        messages += [str(r.get("message", "")) for r in audit if r["kind"] == "order"]
        if not any("buying power" in m.lower() for m in messages):
            raise ValueError("expected native insufficient buying power reason")
    elif invalid or len(fills) < 2:
        raise ValueError("unexpected native rejection or missing round trip")
    observed_ids = {e["orderId"] for e in fills + invalid}
    if set(intents) - observed_ids:
        raise ValueError("intent lacks a terminal native result")
    if len(observed_ids) != len(fills + invalid):
        raise ValueError("duplicate terminal native result")
    attributed_margin_fills = Counter()
    for fill in fills:
        if fill["symbolValue"] != "SPY" or fill["fillPriceCurrency"] != "USD" or fill.get("orderFeeCurrency", "USD") != "USD":
            raise ValueError("unexpected currency/instrument")
        intent = intents.get(fill["orderId"])
        order = orders.get(str(fill["orderId"]))
        if not order or number(order["quantity"]) != number(fill["fillQuantity"]):
            raise ValueError("native order quantity disagrees")
        if intent is not None:
            if number(fill["time"]) <= number(intent["utc_seconds"]):
                raise ValueError("causal discretionary fill violation")
            if order.get("tag") != intent["reason"] or order.get("type") != 4:
                raise ValueError("discretionary order is not declared native MOO")
        elif order.get("tag") != "Margin Call" or order.get("type") != 0 or not any(
                number(r["utc_seconds"]) == number(fill["time"]) for r in margin_calls):
            raise ValueError("unattributed native fill")
        else:
            attributed_margin_fills[number(fill["time"])] += 1
        # Engine-initiated margin orders have their own native event/tag; retained separately.
    expected_margin_fills = Counter()
    for call in margin_calls:
        expected_margin_fills[number(call["utc_seconds"])] += int(call["count"])
    if attributed_margin_fills != expected_margin_fills:
        raise ValueError("margin-call quantity of orders disagrees")
    final = [r for r in audit if r["kind"] == "final"]
    if len(final) != 1 or number(final[0]["quantity"]) != 0:
        raise ValueError("final position is not flat")
    if sum((number(e["fillQuantity"]) for e in fills), Decimal(0)) != 0:
        raise ValueError("fill ledger is not flat")
    dividends = sum((number(r["amount"]) for r in audit if r["kind"] == "dividend"), Decimal(0))
    fees = sum((number(e.get("orderFeeAmount", 0)) for e in fills), Decimal(0))
    cash = Decimal(100000) + dividends - fees - sum((number(e["fillQuantity"]) * number(e["fillPrice"]) for e in fills), Decimal(0))
    # Exported fill precision can differ from internal values; never fabricate omitted digits.
    if abs(number(stats["End Equity"]) - cash) > Decimal("0.01") or abs(number(final[0]["cash"]) - cash) > Decimal("0.01"):
        raise ValueError("native cash disagrees with fill/fee/distribution ledger")
    if number(final[0]["cash"]) != number(final[0]["equity"]):
        raise ValueError("final equity differs from cash")
    if abs(number(stats["Total Fees"]) - fees) > Decimal("0.005"):
        raise ValueError("native fees disagree")
    marks = [r for r in audit if r["kind"] == "mark"]
    if not marks:
        raise ValueError("no native marks")
    if any(number(r["equity"]) <= 0 or number(r["gross"]) < 0 for r in marks):
        raise ValueError("nonpositive equity or invalid exposure")
    return {"end_cash_usd": str(cash), "native_end_equity_usd": stats["End Equity"],
            "cash_pnl_usd": str(cash - Decimal(100000)), "fees_usd": str(fees),
            "dividends_usd": str(dividends), "fill_count": len(fills), "invalid_count": len(invalid),
            "mark_count": len(marks), "max_observed_gross": str(max(number(r["gross"]) for r in marks)),
            "max_observed_drawdown": str(max(number(r["drawdown"]) for r in marks)),
            "minimum_observed_margin_remaining": str(min(number(r["margin_remaining"]) for r in marks)),
            "margin_warning_count": sum(r["kind"] == "margin_warning" for r in audit),
            "margin_calls": margin_calls, "reductions": reductions, "intents": list(intents.values()),
            "fills": [{k: e.get(k, 0) for k in ["orderId", "time", "fillPrice", "fillQuantity", "orderFeeAmount", "message"]} for e in fills],
            "final_quantity": "0"}


def inspect_case(case_path, case_spec):
    """Read native result, order and callback ledgers; never launch a process."""
    import hashlib
    import json
    def read(path):
        return json.loads(path.read_text(), parse_float=Decimal)
    stem = case_path / "HistoricalSimulationAlgorithm"
    summary_path = stem.with_name(stem.name + "-summary.json")
    events_path = stem.with_name(stem.name + "-order-events.json")
    result_path = stem.with_suffix(".json")
    audit_path = case_path / "audit.jsonl"
    audit = [json.loads(s, parse_float=Decimal) for s in audit_path.read_text().splitlines()]
    result = summarize(read(summary_path), read(events_path), audit, rejected=case_spec["reject"],
                       adaptive=case_spec["adaptive"], orders=read(result_path)["orders"])
    failed = list(case_path.glob("failed-data-requests-*.txt"))
    succeeded = list(case_path.glob("succeeded-data-requests-*.txt"))
    if len(failed) != 1 or failed[0].stat().st_size or len(succeeded) != 1 or not succeeded[0].read_text().splitlines():
        raise ValueError("native data request logs missing or failed")
    result.update({"id": case_spec["id"], "specification": case_spec,
                   "failed_data_request_bytes": 0, "succeeded_data_requests": succeeded[0].read_text().splitlines()})
    for key, path in [("summary", summary_path), ("events", events_path), ("audit", audit_path), ("native_result", result_path)]:
        result[key + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Audit existing native results without rerunning LEAN")
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads((args.run / "plan.json").read_text())
    print(json.dumps({"cases": [inspect_case(args.run / c["id"], c) for c in plan["cases"]]}, indent=2, default=str))
