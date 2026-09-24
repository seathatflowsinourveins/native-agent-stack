#!/usr/bin/env python3
"""Gap 14 LEAN arm: diff native LEAN outputs against the committed native Nautilus reports (stdlib, Decimal).

Compared per optimizer: fills as a multiset of (16:00 New York time, asset, side, quantity, price, fee) read from
LEAN's native order-events JSON; rebalance decisions (date, equity before, integer targets); the ordered cash
sequence (after every fill, and after every ex-date instant's dividend credits, because LEAN exposes cash to the
algorithm only after all same-instant dividends are applied); dividend credits (ex-date, asset, quantity, amount)
against the Nautilus DistributionModule emissions; total fees; ending cash; final positions. Any difference raises.
Mutation self-tests on copies of the LEAN data must each be detected; the control_fee2 case must be detected natively.
"""
import argparse
import ast
import copy
import csv
import datetime as dt
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
KEYS = ("meanrisk_min_variance", "hrp_variance")
PAIRS = {"no_dividends": "base", "dividends": "dividends", "control_fee2": "base"}


def ny(stamp):
    return stamp.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S")


def utc(text):
    text = text.replace("Z", "+00:00")
    if "." in text:  # .NET round-trip format carries 7 fractional digits
        head, tail = text.split(".", 1)
        frac, zone = tail[:tail.index("+")], tail[tail.index("+"):]
        text = f"{head}.{frac[:6]}{zone}"
    return dt.datetime.fromisoformat(text)


def load_lean(case_dir):
    summary = json.loads((case_dir / "WeightScheduleParityAlgorithm-summary.json").read_text(), parse_float=Decimal)
    events = json.loads((case_dir / "WeightScheduleParityAlgorithm-order-events.json").read_text(), parse_float=Decimal)
    rows = list(csv.reader((case_dir / "parity-ledger.csv").read_text().splitlines()))[1:]
    fills = [(ny(dt.datetime.fromtimestamp(float(e["time"]), dt.timezone.utc)), e["symbolValue"],
              "BUY" if Decimal(e["fillQuantity"]) > 0 else "SELL", abs(Decimal(e["fillQuantity"])),
              Decimal(e["fillPrice"]), Decimal(e.get("orderFeeAmount", 0)))
             for e in events if e["status"] == "filled"]
    return {"state": summary["state"], "end_equity": summary["statistics"]["End Equity"],
            "total_fees": summary["statistics"]["Total Fees"], "statuses": sorted({e["status"] for e in events}),
            "fills": fills, "rows": rows}


def lean_views(lean):
    rows = lean["rows"]
    ledger_fills = [(ny(utc(r[1])), r[2], "BUY" if Decimal(r[3]) > 0 else "SELL", abs(Decimal(r[3])), Decimal(r[4]),
                     Decimal(r[5])) for r in rows if r[0] == "fill"]
    decisions = [(r[2], Decimal(r[3]), {"SPY": int(r[4]), "QQQ": int(r[5]), "IWM": int(r[6])}) for r in rows if r[0] == "decision"]
    credits = [(ny(utc(r[1]))[:10], r[2], int(Decimal(r[4])), Decimal(r[3]) * Decimal(r[4])) for r in rows if r[0] == "dividend"]
    cash = []
    for r in rows:
        if r[0] == "fill":
            cash.append((ny(utc(r[1])), "fill", Decimal(r[6])))
        elif r[0] == "dividend":
            item = (ny(utc(r[1])), "dividend", Decimal(r[5]))
            if cash and cash[-1][:2] == item[:2]:
                if cash[-1] != item:
                    raise ValueError("inconsistent same-instant dividend cash in LEAN ledger")
                continue
            cash.append(item)
    final = [r for r in rows if r[0] == "final"]
    if len(final) != 1:
        raise ValueError("LEAN ledger has no single final row")
    return {"ledger_fills": ledger_fills, "decisions": decisions, "credits": credits, "cash": cash,
            "final_cash": Decimal(final[0][2]), "final_shares": [Decimal(x) for x in final[0][3:6]]}


def load_nautilus(key_dir, summary, with_modules):
    fills = []
    with (key_dir / "fills.csv").open() as f:
        for r in csv.DictReader(f):
            fees = sum(Decimal(c.split()[0]) for c in ast.literal_eval(r["commissions"]))
            fills.append((ny(dt.datetime.fromisoformat(r["ts_last"])), r["instrument_id"].split(".")[0], r["side"],
                          Decimal(r["filled_qty"]), Decimal(r["avg_px"]), fees))
    with (key_dir / "account.csv").open() as f:
        rows = [(dt.datetime.fromisoformat(r[""]), Decimal(r["total"])) for r in csv.DictReader(f)]
    cash = []
    for stamp, total in rows[1:]:
        when = ny(stamp)
        kind = "fill" if when.endswith("16:00:00") else "dividend" if when.endswith("00:00:00") else "other"
        if kind == "dividend" and cash and cash[-1][:2] == (when, kind):
            cash[-1] = (when, kind, total)
        else:
            cash.append((when, kind, total))
    decisions = [(d["date"], Decimal(d["native_equity"]), d["target"])
                 for d in json.loads((key_dir / "decisions.json").read_text()) if "target" in d]
    credits = []
    if with_modules:
        for m in json.loads((key_dir / "modules.json").read_text()):
            credits += [(e["ex_date"], m["instrument"].split(".")[0], e["eligible_quantity"], Decimal(e["amount"]))
                        for e in m["emissions"]]
    return {"fills": fills, "cash": cash, "decisions": decisions, "credits": credits,
            "initial_cash": rows[0][1], "ending_cash": Decimal(summary["ending_cash_native"]),
            "final_shares": summary["final_shares"], "open_positions": summary["open_positions"],
            "fees": Decimal(summary["fees_usd"])}


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return {"index": i, "lean": str(x), "nautilus": str(y)}
    return {"index": min(len(a), len(b)), "lean_len": len(a), "nautilus_len": len(b)}


class InternalError(Exception):
    """A LEAN-internal check failed (run incomplete or inconsistent); never counts as a cross-engine detection."""


def internal(lean):
    """LEAN-internal checks only: completion, order statuses, ledger well formed, ledger fills equal native events."""
    if lean["state"].get("Status") != "Completed" or lean["state"].get("RuntimeError"):
        raise InternalError("LEAN run did not complete")
    if not set(lean["statuses"]) <= {"submitted", "filled"}:
        raise InternalError(f"unexpected LEAN order statuses {lean['statuses']}")
    try:
        view = lean_views(lean)
    except (ValueError, IndexError, ArithmeticError) as exc:
        raise InternalError(f"LEAN ledger malformed: {exc}") from exc
    if sorted(view["ledger_fills"]) != sorted(lean["fills"]):
        raise InternalError("LEAN algorithm ledger fills differ from LEAN native order events")
    return view


def check(lean, nt):
    """Internal checks, then every cross-engine comparison; a cross-engine difference raises ValueError."""
    view = internal(lean)
    if sorted(lean["fills"]) != sorted(nt["fills"]):
        raise ValueError(f"fill mismatch: {first_diff(sorted(lean['fills']), sorted(nt['fills']))}")
    if view["decisions"] != nt["decisions"]:
        raise ValueError(f"decision mismatch: {first_diff(view['decisions'], nt['decisions'])}")
    if sorted(view["credits"]) != sorted(nt["credits"]):
        raise ValueError(f"dividend credit mismatch: {first_diff(sorted(view['credits']), sorted(nt['credits']))}")
    if view["cash"] != nt["cash"]:
        raise ValueError(f"cash sequence mismatch: {first_diff(view['cash'], nt['cash'])}")
    fees = sum((f[5] for f in lean["fills"]), Decimal(0))
    if fees != nt["fees"]:
        raise ValueError(f"total fee mismatch: LEAN {fees} Nautilus {nt['fees']}")
    if view["final_cash"] != nt["ending_cash"] or Decimal(str(lean["end_equity"]).replace(",", "")) != nt["ending_cash"]:
        raise ValueError(f"ending cash mismatch: LEAN {view['final_cash']} / {lean['end_equity']} Nautilus {nt['ending_cash']}")
    if any(view["final_shares"]) or any(nt["final_shares"].values()) or nt["open_positions"]:
        raise ValueError("not flat at the end")
    return {"fills_matched": len(lean["fills"]), "decisions_matched": len(view["decisions"]),
            "cash_points_matched": len(view["cash"]), "dividend_credits_matched": len(view["credits"]),
            "nonzero_dividend_credits": sum(1 for c in view["credits"] if c[3]),
            "dividend_cash_usd": str(sum((c[3] for c in view["credits"]), Decimal(0))),
            "fees_usd": str(fees), "ending_cash_usd": str(view["final_cash"]),
            "lean_summary_end_equity": str(lean["end_equity"]), "lean_summary_total_fees": str(lean["total_fees"])}


def control_detected(lean, nt):
    """A negative control counts only if LEAN-internal checks pass and a cross-engine comparison raises."""
    try:
        internal(lean)
    except InternalError:
        return False
    try:
        check(lean, nt)
    except InternalError:
        return False
    except ValueError:
        return True
    return False


def edit_row(kind, col, change):
    def mutate(lean):
        row = next(r for r in lean["rows"] if r[0] == kind)
        row[col] = change(row[col])
    return mutate


def mutations(with_dividends):
    """Fill mutations change the native order event and the algorithm ledger row together, so only the
    cross-engine comparison can detect them (the LEAN-internal consistency check still passes)."""
    def both(event_change, row_change, which=0):
        def mutate(lean):
            lean["fills"][which] = event_change(lean["fills"][which])
            rows = [r for r in lean["rows"] if r[0] == "fill"]
            row_change(rows[which])
        return mutate

    def set_col(col, change):
        def apply(row):
            row[col] = change(row[col])
        return apply

    plus_hour = lambda f: ((dt.datetime.fromisoformat(f[0]) + dt.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),) + f[1:]
    row_hour = lambda v: (utc(v) + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")

    def drop_last_fill(lean):
        lean["fills"].pop()
        index = max(i for i, r in enumerate(lean["rows"]) if r[0] == "fill")
        lean["rows"].pop(index)

    out = {
        "fill_price_plus_0.0001": both(lambda f: f[:4] + (f[4] + Decimal("0.0001"),) + f[5:],
                                       set_col(4, lambda v: str(Decimal(v) + Decimal("0.0001")))),
        "fill_time_plus_one_hour": both(plus_hour, set_col(1, row_hour)),
        "fill_fee_plus_0.01": both(lambda f: f[:5] + (f[5] + Decimal("0.01"),),
                                   set_col(5, lambda v: str(Decimal(v) + Decimal("0.01")))),
        "last_fill_removed": drop_last_fill,
        "first_cash_transition_plus_0.01": edit_row("fill", 6, lambda v: str(Decimal(v) + Decimal("0.01"))),
        "decision_equity_plus_0.01": edit_row("decision", 3, lambda v: str(Decimal(v) + Decimal("0.01"))),
    }
    if with_dividends:
        def drop_credit(lean):
            index = next(i for i, r in enumerate(lean["rows"]) if r[0] == "dividend" and Decimal(r[4]))
            lean["rows"].pop(index)
        out["one_nonzero_dividend_credit_removed"] = drop_credit
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lean-out", type=Path, required=True)
    parser.add_argument("--nautilus-base", type=Path, required=True)
    parser.add_argument("--nautilus-dividends", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    roots = {"base": args.nautilus_base, "dividends": args.nautilus_dividends}
    summaries = {k: json.loads((v / "summary.json").read_text()) for k, v in roots.items()}
    report = {"compare_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "lean_run": json.loads((args.lean_out / "run.json").read_text()), "cases": {}}
    ok = True
    for case, ref in PAIRS.items():
        for key in KEYS:
            lean = load_lean(args.lean_out / case / key)
            nt = load_nautilus(roots[ref] / key, summaries[ref]["optimizers"][key], ref == "dividends")
            entry = {"compared_with": str(roots[ref] / key)}
            try:
                internal(lean)
                entry["internal_checks_passed"] = True
            except InternalError as exc:
                entry["internal_checks_passed"], entry["internal_error"] = False, str(exc)
                ok = False
            try:
                entry["result"] = check(lean, nt)
                entry["match"] = True
            except InternalError as exc:
                entry["match"], entry["difference"] = False, "internal: " + str(exc)
            except ValueError as exc:
                entry["match"], entry["difference"] = False, str(exc)
            if case == "control_fee2":
                entry["expected"] = "cross-engine mismatch (negative control) with LEAN-internal checks passing"
                entry["detected"] = control_detected(lean, nt)
                ok &= entry["detected"]
                # The acceptance rule must reject a broken control: each of these copies must NOT count as detected.
                broken = {"runtime_error_injected": lambda l: l["state"].__setitem__("RuntimeError", "injected"),
                          "native_fill_inconsistent_with_ledger": lambda l: l["fills"].__setitem__(
                              0, l["fills"][0][:4] + (l["fills"][0][4] + Decimal("1"),) + l["fills"][0][5:])}
                entry["broken_control_self_tests"] = {}
                for name, mutate in broken.items():
                    copy_ = copy.deepcopy(lean)
                    mutate(copy_)
                    entry["broken_control_self_tests"][name] = {"counted_as_detected": control_detected(copy_, nt)}
                    ok &= not entry["broken_control_self_tests"][name]["counted_as_detected"]
            else:
                ok &= entry["match"]
                tests = {}
                for name, mutate in mutations(ref == "dividends").items():
                    copy_ = copy.deepcopy(lean)
                    mutate(copy_)
                    try:
                        internal(copy_)
                    except InternalError as exc:
                        tests[name] = False  # only a cross-engine detection counts
                        continue
                    try:
                        check(copy_, nt)
                        tests[name] = False
                    except ValueError as exc:
                        tests[name] = "cross-engine: " + str(exc)[:200]
                entry["mutation_self_tests"] = tests
                ok &= all(tests.values())
            report["cases"].setdefault(case, {})[key] = entry
    report["all_criteria_met"] = ok
    args.out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({c: {k: (v["match"], v.get("detected"), v.get("difference", "")[:120]) for k, v in d.items()}
                      for c, d in report["cases"].items()}, indent=1))
    print("all_criteria_met", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
