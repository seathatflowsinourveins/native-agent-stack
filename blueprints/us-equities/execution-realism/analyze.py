"""Reconcile native LEAN order events and rounded summary; no engine simulation."""
from decimal import Decimal


def number(value):
    result = Decimal(str(value).replace("$", "").replace(",", ""))
    if not result.is_finite():
        raise ValueError("nonfinite accounting value")
    return result


def summarize(summary, events):
    state, stats = summary["state"], summary["statistics"]
    if state.get("Status") != "Completed" or state.get("RuntimeError"):
        raise ValueError("native algorithm did not complete successfully")
    if any(e["status"] not in {"submitted", "filled"} for e in events):
        raise ValueError("unexpected order status")
    fills = [e for e in events if e["status"] == "filled"]
    if len(fills) != 2 or len({e["orderId"] for e in fills}) != 2:
        raise ValueError("expected exactly two distinct filled orders")
    if [number(e["fillQuantity"]) for e in fills] != [Decimal(100), Decimal(-100)]:
        raise ValueError("fixed round-trip quantities changed")
    if not fills[0]["time"] < fills[1]["time"]:
        raise ValueError("round-trip timing changed")
    if any(e["symbolValue"] != "SPY" or e["fillPriceCurrency"] != "USD"
           or e.get("orderFeeCurrency", "USD") != "USD" for e in fills):
        raise ValueError("unexpected instrument or accounting currency")
    fees = sum((number(e.get("orderFeeAmount", 0)) for e in fills), Decimal(0))
    cash = -sum((number(e["fillQuantity"]) * number(e["fillPrice"]) for e in fills), Decimal(0)) - fees
    expected = Decimal(100000) + cash
    if abs(number(stats["End Equity"]) - expected) > Decimal("0.005"):
        raise ValueError("native summary disagrees with exact fill cash ledger")
    if number(stats["Total Fees"]) != fees or int(stats["Total Orders"]) != 2:
        raise ValueError("native order/fee summary disagrees")
    return {"cash_pnl_usd": str(cash), "end_cash_usd": str(expected),
            "fees_usd": str(fees), "net_quantity": "0",
            "native_summary_end_equity_usd": stats["End Equity"],
            "fills": [{k: e.get(k, 0) for k in ("orderId", "time", "symbolValue",
                        "fillPrice", "fillQuantity", "orderFeeAmount")} for e in fills]}
