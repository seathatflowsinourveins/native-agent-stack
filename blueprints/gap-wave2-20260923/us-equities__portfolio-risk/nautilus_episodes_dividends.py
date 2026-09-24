#!/usr/bin/env python3
"""Gap 11 fix round 4: the fixed-fee episode replay with native cash dividends credited.

Same episodes, synthetic 09:30 open-print bars, integer legs and FixedFeeModel (1 USD per order) as the fixed case
of nautilus_episodes.py, plus one DistributionModule per instrument (vendored unchanged from origin/main 51d66001, the
peer sota-workflow-resolution's accepted module, sha256-checked) so ex-date cash reaches the native CASH account at
00:00 New York on each ex-date. An independent Decimal ledger merges dividend credits and fills chronologically,
attributes each credit to the episodes holding the asset at that instant, and must match every native account
transition, module emission and fill. Financing stays explicit zero; fills stay at the raw open with unlimited depth.
"""
import argparse
import copy
import datetime as dt
from decimal import ROUND_HALF_EVEN, Decimal
import gzip
import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
from nautilus_episodes import CAPITAL, LEDGER_SHA256, NOTIONAL, episodes_for  # noqa: E402
from nautilus_portfolio import load_bars, number  # noqa: E402
from nautilus_portfolio_dividends import VENDORED, VENDORED_SHA256, distribution_events, load_distribution  # noqa: E402

NY = ZoneInfo("America/New_York")
FEE = Decimal("1")


def midnight_ns(day):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(0), NY).timestamp()) * 10**9


def account_ts_ns(row):
    """Account report row timestamp (reset index, pandas epoch milliseconds) as integer nanoseconds."""
    for key in ("index", "ts_event", "ts_init"):
        if key in row:
            return int(row[key]) * 10**6
    raise KeyError("account row has no timestamp column")


def at_open_ns(day):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(9, 30), NY).timestamp()) * 10**9


def run_engine(eps, bars, assets, out, modules, alerts):
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import FixedFeeModel
    from nautilus_trader.model import AccountType, Bar, BarType, Currency, Equity, InstrumentId
    from nautilus_trader.model import Money, OmsType, OrderSide, Price, Quantity, Symbol, Venue
    from nautilus_trader.trading import Strategy

    usd, venue = Currency.from_str("USD"), Venue("SIM")
    inst = {a: Equity(InstrumentId.from_str(f"{a}.SIM"), Symbol(a), usd, 4, Price.from_str("0.0001"), 0, 0,
                      lot_size=Quantity.from_int(1)) for a in assets}
    btypes = {a: BarType.from_str(f"{a}.SIM-1-DAY-LAST-EXTERNAL") for a in assets}
    data = []
    for a in assets:
        for b in bars[a]:
            px = Price.from_str(format(b["open"], ".4f"))
            data.append(Bar(btypes[a], px, px, px, px, Quantity.from_int(b["volume"]), at_open_ns(b["date"]), at_open_ns(b["date"])))
    actions = {}
    for i, e in enumerate(eps):
        for a, q in e["legs"].items():
            actions.setdefault(e["exit"], {"SELL": [], "BUY": []})["SELL"].append((i, a, q))
            actions.setdefault(e["entry"], {"SELL": [], "BUY": []})["BUY"].append((i, a, q))
    by_id = {str(inst[a].id): a for a in assets}

    class EpisodeReplay(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.seen, self.orders_log, self.denied, self.alerts_fired = {}, [], [], []

        def on_start(self):
            for bt in btypes.values():
                self.subscribe_bars(bt)
            # No-op alerts at each ex-date instant give the engine a timestamp at which venue modules run.
            for instant in alerts:
                self.clock.set_time_alert_ns(f"ex_{instant}", instant, self.on_ex_alert, allow_past=False)

        def on_ex_alert(self, event):
            self.alerts_fired.append(int(event.ts_event))

        def on_bar(self, bar):
            day = dt.datetime.fromtimestamp(bar.ts_event / 1e9, NY).date().isoformat()
            seen = self.seen.setdefault(day, set())
            seen.add(by_id[str(bar.bar_type.instrument_id)])
            if len(seen) < len(assets) or day not in actions:
                return
            for side in ("SELL", "BUY"):
                for i, a, q in actions[day][side]:
                    order = self.order_factory.market(inst[a].id, OrderSide.SELL if side == "SELL" else OrderSide.BUY,
                                                      Quantity.from_int(q))
                    self.orders_log.append({"client_order_id": str(order.client_order_id), "episode": i, "date": day,
                                            "asset": a, "side": side, "qty": q})
                    self.submit_order(order)

        def on_order_denied(self, event):
            self.denied.append({"client_order_id": str(event.client_order_id), "reason": event.reason})

        def on_order_rejected(self, event):
            self.denied.append({"client_order_id": str(event.client_order_id), "reason": "REJECTED " + event.reason})

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(CAPITAL, usd)], base_currency=usd,
                         fee_model=FixedFeeModel(Money(FEE, usd)), modules=modules)
        for i in inst.values():
            engine.add_instrument(i)
        engine.add_data(data)
        s = EpisodeReplay()
        engine.add_strategy(s)
        engine.run()
        reports = {"account": engine.generate_account_report(venue=venue), "fills": engine.generate_order_fills_report()}
        for n, r in reports.items():
            r.to_csv(out / f"{n}.csv")
        parsed = {n: json.loads(r.reset_index().to_json(orient="records")) for n, r in reports.items()}
        common.dump(out / "orders.json", s.orders_log)
        return parsed, s.orders_log, s.denied, {"open_positions": len(engine.cache.positions_open()),
                                                 "open_orders": len(engine.cache.orders_open()),
                                                 "alerts_fired": len(s.alerts_fired),
                                                 "report_sha256": {n: common.digest(out / f"{n}.csv") for n in reports}}
    finally:
        engine.dispose()


def ledger(eps, log, events, assets, opens):
    """Independent chronological ledger: dividend credits at ex instants (module order) and fills in submission order."""
    timeline = [(e["ex_instant_ns"], 0, assets.index(a), "dividend", a, e) for a in assets for e in events[a]]
    timeline += [(at_open_ns(o["date"]), 1, i, "fill", o["asset"], o) for i, o in enumerate(log)]
    cash, shares, open_legs = CAPITAL, {a: 0 for a in assets}, {}
    transitions, credits, pnl = [], [], [Decimal(0)] * len(eps)
    for ts, _, _, kind, asset, item in sorted(timeline, key=lambda x: x[:3]):
        if kind == "dividend":
            amount = Decimal(shares[asset]) * Decimal(item["per_share"])
            holders = {i: legs[asset] for i, legs in open_legs.items() if asset in legs}
            if sum(holders.values()) != shares[asset]:
                raise ValueError("episode attribution does not cover the held shares")
            for i, q in holders.items():
                pnl[i] += Decimal(q) * Decimal(item["per_share"])
            cash += amount
            credits.append({"asset": asset, "ex_date": item["ex_date"], "qty": shares[asset], "amount": amount,
                            "instant_ns": midnight_ns(item["ex_date"])})
            transitions.append({"kind": "dividend", "asset": asset, "ex_date": item["ex_date"], "cash_after": cash,
                                "ts_ns": midnight_ns(item["ex_date"])})
            continue
        o = item
        px = opens[o["asset"]][o["date"]]
        signed = (o["qty"] * px).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) * (1 if o["side"] == "SELL" else -1)
        cash += signed - FEE
        pnl[o["episode"]] += signed - FEE
        shares[o["asset"]] += o["qty"] if o["side"] == "BUY" else -o["qty"]
        legs = open_legs.setdefault(o["episode"], {})
        if o["side"] == "BUY":
            legs[o["asset"]] = o["qty"]
        else:
            legs.pop(o["asset"])
            if not legs:
                open_legs.pop(o["episode"])
        transitions.append({"kind": "fill", "order": o, "price": px, "cash_after": cash, "ts_ns": at_open_ns(o["date"])})
    return transitions, credits, pnl, cash, shares


def check(parsed, log, denied, state, module_log, transitions, credits):
    if denied:
        raise ValueError(f"denied or rejected orders: {denied[:3]}")
    if any(m["errors"] for m in module_log):
        raise ValueError("distribution module errors: " + json.dumps([m["errors"] for m in module_log])[:120])
    fills = {f["client_order_id"]: f for f in parsed["fills"]}
    if set(fills) != {o["client_order_id"] for o in log}:
        raise ValueError("filled set differs from submitted set")
    for t in (t for t in transitions if t["kind"] == "fill"):
        o, f = t["order"], fills[t["order"]["client_order_id"]]
        when = dt.datetime.fromtimestamp(f["ts_last"] / 1e3, NY).strftime("%Y-%m-%d %H:%M:%S.%f")
        if (f["status"] != "FILLED" or f["side"] != o["side"] or number(f["filled_qty"]) != o["qty"]
                or f["instrument_id"] != f"{o['asset']}.SIM" or when != o["date"] + " 09:30:00.000000"
                or number(f["avg_px"]) != t["price"] or sum(number(c) for c in f["commissions"]) != FEE):
            raise ValueError(f"fill mismatch {o}")
    # Emissions: amount, quantity and ex-date, plus the actual emission instant and the armed ex-date instant,
    # both of which must be 00:00 New York on the ex-date (computed here, not taken from the module).
    emitted = sorted((e["ex_date"], m["instrument"].split(".")[0], e["eligible_quantity"], Decimal(e["amount"]),
                      int(e["ts_now_ns"]), int(e["ex_instant_ns"])) for m in module_log for e in m["emissions"])
    if emitted != sorted((c["ex_date"], c["asset"], c["qty"], c["amount"], c["instant_ns"], c["instant_ns"]) for c in credits):
        raise ValueError("distribution emissions differ from ledger credits")
    # Account rows: (timestamp, balance) for every transition, dividends at 00:00 and fills at 09:30 New York.
    native = [(account_ts_ns(a), number(a["total"])) for a in parsed["account"]]
    if native[0][1] != CAPITAL or native[1:] != [(t["ts_ns"], t["cash_after"]) for t in transitions]:
        raise ValueError(f"account transitions differ: native {len(native) - 1} rows, ledger {len(transitions)}")
    if state["open_positions"] or state["open_orders"]:
        raise ValueError("not flat")
    return len(native)


def mutation_self_tests(check_fn, parsed, module_log, transitions):
    div_row = next(i for i, t in enumerate(transitions)
                   if t["kind"] == "dividend" and t["cash_after"] != (transitions[i - 1]["cash_after"] if i else CAPITAL)) + 1
    first_emit = next((i, j) for i, m in enumerate(module_log) for j, e in enumerate(m["emissions"]) if Decimal(e["amount"]))

    def bump(row, delta):
        row["total"] = str(Decimal(str(row["total"]).split()[0]) + Decimal(delta))

    def emission(m):
        return m[first_emit[0]]["emissions"][first_emit[1]]

    def shift_row(row, ms):
        key = next(k for k in ("index", "ts_event", "ts_init") if k in row)
        row[key] = int(row[key]) + ms
    mutations = {
        "fill_time_shifted_one_hour": lambda p, m: p["fills"][0].__setitem__("ts_last", p["fills"][0]["ts_last"] + 3600000),
        "cash_corrupted_first_transition": lambda p, m: bump(p["account"][1], "12345.67"),
        "dividend_account_transition_off_by_one_cent": lambda p, m: bump(p["account"][div_row], "0.01"),
        "dividend_account_row_removed": lambda p, m: p["account"].pop(div_row),
        "emission_amount_off_by_one_cent": lambda p, m: emission(m).__setitem__("amount", str(Decimal(emission(m)["amount"]) + Decimal("0.01"))),
        "emission_removed": lambda p, m: m[first_emit[0]]["emissions"].pop(first_emit[1]),
        "dividend_account_row_shifted_to_0100": lambda p, m: shift_row(p["account"][div_row], 3600000),
        "emission_instant_shifted_one_hour": lambda p, m: emission(m).__setitem__("ts_now_ns", int(emission(m)["ts_now_ns"]) + 3600 * 10**9),
    }
    results = {}
    for name, mutate in mutations.items():
        p, m = copy.deepcopy(parsed), copy.deepcopy(module_log)
        mutate(p, m)
        try:
            check_fn(p, m)
            results[name] = False
        except (ValueError, KeyError, IndexError) as exc:
            results[name] = str(exc)[:160]
    if not all(results.values()):
        raise SystemExit(f"reconciliation failed to detect a mutation: {results}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True, help="regenerated candidate ledger (.json or .json.gz)")
    parser.add_argument("--no-dividend-summary", type=Path, required=True, help="fix-round-2 episodes summary.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise SystemExit("native version mismatch")
    raw = args.ledger.read_bytes()
    raw = gzip.decompress(raw) if args.ledger.suffix == ".gz" else raw
    if hashlib.sha256(raw).hexdigest() != LEDGER_SHA256:
        raise SystemExit("ledger is not the retained candidate ledger")
    ledger_rows = json.loads(raw)
    previous = json.loads(args.no_dividend_summary.read_text())
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False)
    dist = load_distribution()
    frozen = common.frozen_panel()
    assets = frozen["plan"]["assets"]
    observed = [r for r in ledger_rows if r["phase"] == "evaluation" and r["status"] == "observed"]
    first, last = min(r["entry"] for r in observed), max(r["exit"] for r in observed)
    bars = load_bars(frozen["root"], assets, first, last)
    opens = {a: {b["date"]: b["open"] for b in bars[a]} for a in assets}
    events = {a: distribution_events(dist, frozen["root"], a, first, last) for a in assets}
    alerts = sorted({e["ex_instant_ns"] for a in assets for e in events[a]})
    summary = {"engine": importlib.metadata.version("nautilus_trader"), "runner_sha256": common.digest(__file__),
               "ledger_sha256": LEDGER_SHA256, "first_entry": first, "last_exit": last, "notional_usd": str(NOTIONAL),
               "case": "fixed (FixedFeeModel 1 USD per order) with DistributionModule per instrument",
               "vendored_distribution_module": {"path": str(VENDORED.relative_to(common.ROOT)), "sha256": VENDORED_SHA256},
               "distribution_events": {a: len(v) for a, v in events.items()},
               "no_dividend_summary_sha256": common.digest(args.no_dividend_summary), "candidates": {}}
    for cand in frozen["plan"]["candidates"]:
        eps = episodes_for(ledger_rows, cand, opens)
        if not any(e["legs"] for e in eps):
            summary["candidates"][cand] = {"episodes": len(eps), "orders": 0, "note": "no invested episode; engine not needed"}
            continue
        sub = args.out / cand
        sub.mkdir(parents=True)
        modules = [dist.build_module(events[a], f"{a}.SIM", "USD") for a in assets]
        parsed, log, denied, state = run_engine(eps, bars, assets, sub, modules, alerts)
        module_log = [{"instrument": f"{a}.SIM", "emissions": m.emissions, "acknowledgements": m.acknowledgements,
                       "errors": m.errors, "process_calls": m.process_calls} for a, m in zip(assets, modules)]
        common.dump(sub / "modules.json", module_log)
        transitions, credits, pnl, cash, shares = ledger(eps, log, events, assets, opens)
        if any(shares.values()):
            raise ValueError("ledger not flat")
        rows = check(parsed, log, denied, state, module_log, transitions, credits)
        mutations = mutation_self_tests(lambda p, m: check(p, log, denied, state, m, transitions, credits),
                                        parsed, module_log, transitions)
        dividend_cash = sum((c["amount"] for c in credits), Decimal(0))
        if sum(pnl) != cash - CAPITAL:
            raise ValueError("episode attribution does not sum to the account P&L")
        n = Decimal(len(eps))
        mean_with = sum(p / NOTIONAL for p in pnl) / n
        before = previous["candidates"][cand]
        mean_without = Decimal(before["cases"]["fixed"]["mean_native_net_return_per_episode"])
        summary["candidates"][cand] = {
            "episodes": len(eps), "orders": len(log), "fills_reconciled": len(log), "account_rows": rows,
            "distribution_credits": len(credits), "nonzero_distribution_credits": sum(1 for c in credits if c["amount"]),
            "credited_dividend_cash_usd": str(dividend_cash),
            "previously_reported_unmodelled_dividend_cash_usd": before["unmodelled_dividend_cash_usd"],
            "credited_minus_unmodelled_usd": str(dividend_cash - Decimal(before["unmodelled_dividend_cash_usd"])),
            "ending_cash_native_equals_ledger": str(cash), "total_pnl_usd": str(cash - CAPITAL),
            "fixed_case_total_pnl_without_dividends_usd": before["cases"]["fixed"]["total_pnl_usd"],
            "mean_native_net_return_per_episode_with_dividends": str(mean_with),
            "mean_native_net_return_per_episode_without_dividends": str(mean_without),
            "dividend_contribution_per_episode": str(mean_with - mean_without),
            "mean_gross_price_label": before["mean_gross_price_label"],
            "mean_net_cost_proxy_label_20bp": before["mean_net_cost_proxy_label"],
            "alerts_fired": state["alerts_fired"], "report_sha256": state["report_sha256"], "mutation_self_tests": mutations}
    summary["inputs_unchanged"] = common.inputs_unchanged(frozen)
    common.dump(args.out / "summary.json", summary)
    print(json.dumps({c: {k: v.get(k) for k in ("episodes", "credited_dividend_cash_usd", "credited_minus_unmodelled_usd",
                                                "mean_native_net_return_per_episode_with_dividends",
                                                "dividend_contribution_per_episode")}
                      for c, v in summary["candidates"].items()}, indent=1))


if __name__ == "__main__":
    main()
