"""Check native factor/event results without inferring a strategy or cash account."""
from decimal import Decimal, localcontext


def num(value):
    n = Decimal(value)
    if not n.is_finite():
        raise ValueError("nonfinite decimal")
    return n


def product_matches(actual, price, factor):
    # C# decimal has a 96-bit coefficient and <=28 fractional digits; Python
    # must not use its default 28-significant-digit context to compare products.
    with localcontext() as ctx:
        ctx.prec = 70
        return abs(num(actual) - num(price) * num(factor)) <= Decimal("1e-25")


def check_scope(result):
    expected = {"implicit_scaled_raw_basis_rejected", "future_bar_for_decision_rejected"}
    if set(result["guards"]) != expected or any(v is not True for v in result["guards"].values()):
        raise ValueError("guard schema or rejection mismatch")
    if result["orders_submitted"] is not False or result["total_return_series_computed"] is not False:
        raise ValueError("scope violation")


def check_upstream_tests(tests):
    counts = tests.get("counters", {})
    cases = tests.get("cases", [])
    total = int(counts.get("total", 0))
    executed = int(counts.get("executed", 0))
    if total <= 0 or executed != total or len(cases) != total:
        raise ValueError("missing or inconsistent upstream test evidence")
    if any(int(counts.get(k, 0)) for k in ["failed", "error", "notRunnable", "timeout", "aborted"]) or any(c["outcome"] != "Passed" for c in cases):
        raise ValueError("upstream tests did not all pass")


def check_row(r):
    if num(r["raw_factor_sentinel"]) != 0:
        raise ValueError("unexpected upstream raw sentinel")
    if r["mapped_symbol"] != "AAPL":
        raise ValueError("unexpected mapping")
    raw, split = num(r["raw_close"]), num(r["split_factor"])
    if raw <= 0 or not product_matches(r["split_adjusted_close"], raw, split):
        raise ValueError("split scaling mismatch")
    if not product_matches(r["adjusted_close"], raw, r["adjusted_factor"]):
        raise ValueError("adjusted scaling mismatch")
    if num(r["total_return_factor"]) != split:
        raise ValueError("unexpected total return factor")
    if r["date"] > r["end_basis"] or not product_matches(r["end_basis_scaled_close"], raw, r["end_basis_scale"]):
        raise ValueError("end basis mismatch")
    if r["date"] == r["end_basis"] and num(r["end_basis_scale"]) != 1:
        raise ValueError("same-date basis must retain raw price")
    if "pre_basis" in r:
        if r["date"] > r["pre_basis"] or not product_matches(r["pre_basis_scaled_close"], raw, r["pre_basis_scale"]):
            raise ValueError("pre basis mismatch")
        if r["date"] == r["pre_basis"] and num(r["pre_basis_scale"]) != 1:
            raise ValueError("same-date pre basis must retain raw price")


def verify(result):
    rows = result["observations"]
    if len(rows) != 25 or len({r["date"] for r in rows}) != 25:
        raise ValueError("session coverage mismatch")
    if [r["date"] for r in rows] != sorted(r["date"] for r in rows):
        raise ValueError("session order mismatch")
    for row in rows:
        check_row(row)
    events = result["events"]
    dividends = [e for e in events if e["kind"] == "dividend"]
    splits = [e for e in events if e["kind"] == "split"]
    if len(dividends) != 1 or dividends[0]["date"] != "2020-08-07" or num(dividends[0]["distribution"]) != Decimal("0.82"):
        raise ValueError("unexpected dividend event/units")
    if len(splits) != 1 or splits[0]["date"] != "2020-08-31" or num(splits[0]["factor"]) != Decimal("0.25"):
        raise ValueError("unexpected split event")
    check_scope(result)
    indexed = {r["date"]: r for r in rows}
    pre, post = indexed["2020-08-28"], indexed["2020-08-31"]
    if num(pre["pre_basis_scale"]) != 1 or num(pre["end_basis_scale"]) != Decimal("0.25") or num(post["end_basis_scale"]) != 1:
        raise ValueError("split/basis boundary mismatch")
    return {"sessions": len(rows), "native_dividend_events": len(dividends), "native_split_events": len(splits),
            "expected_guard_rejections": 2, "dividend": dividends[0], "split": splits[0],
            "basis_comparison": {"observation": pre["date"], "raw_close": pre["raw_close"],
                "pre_basis": pre["pre_basis"], "pre_basis_close": pre["pre_basis_scaled_close"],
                "post_basis": pre["end_basis"], "post_basis_close": pre["end_basis_scaled_close"]},
            "scope": "retrospective factor/map/event mechanics; no orders, cash P&L or original availability proof"}
