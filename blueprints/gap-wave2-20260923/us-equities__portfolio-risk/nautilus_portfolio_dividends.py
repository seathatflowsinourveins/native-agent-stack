#!/usr/bin/env python3
"""Gap 4 dividend-inclusive arm: the gap 4/10 fold-weight run with native cash distributions credited.

Identical schedule, bars, weights, sizing and FixedFeeModel as nautilus_portfolio.py, plus one
DistributionModule (vendored unchanged from origin/main 51d66001, the peer sota-workflow-resolution's
accepted dividend simulation module) per instrument, so ex-date cash reaches the native account and is
included in later rebalancing equity. The independent Decimal ledger credits shares-held x per-share at
each ex-date instant (00:00 New York) and must match every native account transition.
"""
import argparse
import csv
import datetime as dt
from decimal import ROUND_FLOOR, Decimal
import importlib.metadata
import importlib.util
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
from nautilus_portfolio import CAPITAL, FEE, INVEST, load_bars, number  # noqa: E402

NY = ZoneInfo("America/New_York")
VENDORED = HERE / "vendored/distribution_module.py"
VENDORED_SHA256 = "eefee070b0dbe6ad3a1e68755ca959b5fff081fad61af8b84902a438996b126b"


def load_distribution():
    if common.digest(VENDORED) != VENDORED_SHA256:
        raise SystemExit("vendored distribution module changed")
    spec = importlib.util.spec_from_file_location("peer_distribution_module", VENDORED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def distribution_events(dist, root, asset, start, end):
    rows = [{"date": dt.datetime.strptime(r[0], "%Y%m%d").date().isoformat(), "price_factor": r[1],
             "split_factor": r[2], "reference_price": r[3]}
            for r in csv.reader(io.StringIO((root / f"Data/equity/usa/factor_files/{asset.lower()}.csv").read_text()))]
    with zipfile.ZipFile(root / f"Data/equity/usa/daily/{asset.lower()}.zip") as z:
        sessions = [dt.datetime.strptime(r[0], "%Y%m%d %H:%M").date().isoformat()
                    for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode()))]
    return dist.derive_events(rows, sessions, start, end)


def ledger(schedule, bars, assets, weight_key, final_close, events, fee=FEE):
    """Independent ledger with dividends: chronological ex-date credits and 16:00 rebalances."""
    close = {a: {b["date"]: b["close"] for b in bars[a]} for a in assets}
    stamp = lambda day: int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(16), NY).timestamp()) * 10**9
    # Same-instant distributions are applied in the venue's module order (the asset list order).
    timeline = [(e["ex_instant_ns"], assets.index(a), "dividend", a, e) for a in assets for e in events[a]]
    timeline += [(stamp(s["rebalance_close"]), len(assets), "rebalance", s["rebalance_close"], s["weights"][weight_key]) for s in schedule]
    timeline.append((stamp(final_close), len(assets), "rebalance", final_close, None))
    cash, shares, transitions, snapshots, credits = CAPITAL, {a: 0 for a in assets}, [], [], []
    for ts, _, kind, key, payload in sorted(timeline, key=lambda x: (x[0], x[1])):
        if kind == "dividend":
            amount = Decimal(shares[key]) * Decimal(payload["per_share"])
            cash += amount
            credits.append({"asset": key, "ex_date": payload["ex_date"], "qty": shares[key],
                            "per_share": payload["per_share"], "amount": str(amount)})
            transitions.append({"kind": "dividend", "asset": key, "ex_date": payload["ex_date"], "cash_after": cash})
            continue
        day, weights = key, payload
        equity = cash + sum(shares[a] * close[a][day] for a in assets)
        target = ({a: 0 for a in assets} if weights is None else
                  {a: int((equity * INVEST * Decimal(repr(weights[a])) / close[a][day]).to_integral_value(ROUND_FLOOR)) for a in assets})
        delta = {a: target[a] - shares[a] for a in assets}
        for side, pick in (("SELL", lambda q: q < 0), ("BUY", lambda q: q > 0)):
            for a in assets:
                if pick(delta[a]):
                    qty, px = abs(delta[a]), close[a][day]
                    cash += (qty * px if side == "SELL" else -qty * px) - fee
                    shares[a] += qty if side == "BUY" else -qty
                    transitions.append({"kind": "fill", "date": day, "asset": a, "side": side, "qty": qty,
                                        "price": px, "cash_after": cash})
        snapshots.append({"date": day, "equity_before": equity, "target": target})
    return transitions, snapshots, credits, cash, shares


def check(parsed, decisions, module_log, transitions, snapshots, credits, fee):
    """Every comparison between the native reports and the independent ledger; raises ValueError on any mismatch."""
    if any(d.get("denied") for d in decisions):
        raise ValueError("unexpected denial")
    if any(m["errors"] for m in module_log):
        raise ValueError("distribution module errors: " + json.dumps([m["errors"] for m in module_log])[:120])
    fills = [t for t in transitions if t["kind"] == "fill"]
    native_fills = sorted((dt.datetime.fromtimestamp(f["ts_last"] / 1e3, NY).strftime("%Y-%m-%d %H:%M:%S.%f"), f["instrument_id"].split(".")[0],
                           f["side"], number(f["filled_qty"]), number(f["avg_px"]), sum(number(c) for c in f["commissions"]))
                          for f in parsed["fills"])
    if native_fills != sorted((t["date"] + " 16:00:00.000000", t["asset"], t["side"], Decimal(t["qty"]), t["price"], fee) for t in fills):
        raise ValueError("fill mismatch")
    emitted = [(e["ex_date"], m["instrument"].split(".")[0], e["eligible_quantity"], Decimal(e["amount"]))
               for m in module_log for e in m["emissions"]]
    expected = [(c["ex_date"], c["asset"], c["qty"], Decimal(c["amount"])) for c in credits]
    if sorted(emitted) != sorted(expected):
        raise ValueError("distribution emissions differ from ledger credits")
    native_cash = [number(a["total"]) for a in parsed["account"]]
    ledger_cash = [t["cash_after"] for t in transitions]
    if native_cash[0] != CAPITAL or native_cash[1:] != ledger_cash:
        raise ValueError(f"account transitions differ: native {len(native_cash) - 1} rows, ledger {len(ledger_cash)}")
    targets = [d for d in decisions if "target" in d]
    if [(d["date"], Decimal(d["native_equity"]), d["target"]) for d in targets] != [(s["date"], s["equity_before"], s["target"]) for s in snapshots]:
        raise ValueError("decision mismatch")
    return {"fills": len(fills), "transitions": len(ledger_cash), "ending_cash": native_cash[-1]}


def mutation_self_tests(check_fn, parsed, decisions, module_log, transitions):
    """Mutate copies of the native reports, decisions and module log; `check_fn` must reject each one."""
    import copy
    div_row = next(i for i, t in enumerate(transitions)
                   if t["kind"] == "dividend" and t["cash_after"] != (transitions[i - 1]["cash_after"] if i else CAPITAL)) + 1
    first_emit = next((i, j) for i, m in enumerate(module_log) for j, e in enumerate(m["emissions"]) if Decimal(e["amount"]))

    def bump(row, delta):
        row["total"] = str(Decimal(str(row["total"]).split()[0]) + Decimal(delta))

    def emission(m):
        return m[first_emit[0]]["emissions"][first_emit[1]]
    mutations = {
        "wrong_instrument_first_fill": lambda p, d, m: p["fills"][0].__setitem__("instrument_id", "WRONG.SIM"),
        "fill_time_1900": lambda p, d, m: p["fills"][0].__setitem__("ts_last", -2208988800000),
        "fill_time_shifted_one_hour": lambda p, d, m: p["fills"][0].__setitem__("ts_last", p["fills"][0]["ts_last"] + 3600000),
        "cash_corrupted_first_transition": lambda p, d, m: bump(p["account"][1], "12345.67"),
        "dividend_account_transition_off_by_one_cent": lambda p, d, m: bump(p["account"][div_row], "0.01"),
        "dividend_account_row_removed": lambda p, d, m: p["account"].pop(div_row),
        "emission_amount_off_by_one_cent": lambda p, d, m: emission(m).__setitem__("amount", str(Decimal(emission(m)["amount"]) + Decimal("0.01"))),
        "emission_removed": lambda p, d, m: m[first_emit[0]]["emissions"].pop(first_emit[1]),
        "emission_ex_date_shifted_one_day": lambda p, d, m: emission(m).__setitem__(
            "ex_date", (dt.date.fromisoformat(emission(m)["ex_date"]) + dt.timedelta(days=1)).isoformat()),
        "module_error_injected": lambda p, d, m: m[0]["errors"].append("injected"),
        "decision_equity_off_by_one_cent": lambda p, d, m: next(x for x in d if "target" in x).__setitem__(
            "native_equity", str(Decimal(next(x for x in d if "target" in x)["native_equity"]) + Decimal("0.01"))),
        "all_decisions_removed": lambda p, d, m: d.clear(),
    }
    results = {}
    for name, mutate in mutations.items():
        p, d, m = copy.deepcopy(parsed), copy.deepcopy(decisions), copy.deepcopy(module_log)
        mutate(p, d, m)
        try:
            check_fn(p, d, m)
            results[name] = False
        except (ValueError, KeyError, IndexError) as exc:
            results[name] = str(exc)[:160]
    if not all(results.values()):
        raise SystemExit(f"reconciliation failed to detect a mutation: {results}")
    return results


def run_engine(schedule, bars, assets, weight_key, final_close, out, modules, alerts):
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import FixedFeeModel
    from nautilus_trader.model import AccountType, Bar, BarType, Currency, Equity, InstrumentId
    from nautilus_trader.model import Money, OmsType, OrderSide, Price, Quantity, Symbol, Venue
    from nautilus_trader.trading import Strategy

    usd, venue = Currency.from_str("USD"), Venue("SIM")
    instruments = {a: Equity(InstrumentId.from_str(f"{a}.SIM"), Symbol(a), usd, 4, Price.from_str("0.0001"), 0, 0,
                             lot_size=Quantity.from_int(1)) for a in assets}
    bar_types = {a: BarType.from_str(f"{a}.SIM-1-DAY-LAST-EXTERNAL") for a in assets}
    data = []
    for a in assets:
        for b in bars[a]:
            stamp = int(dt.datetime.combine(dt.date.fromisoformat(b["date"]), dt.time(16), NY).timestamp()) * 10**9
            data.append(Bar(bar_types[a], *[Price.from_str(format(b[k], ".4f")) for k in ("open", "high", "low", "close")],
                            Quantity.from_int(b["volume"]), stamp, stamp))
    plan = {e["rebalance_close"]: e["weights"][weight_key] for e in schedule}
    plan[final_close] = None
    by_id = {str(instruments[a].id): a for a in assets}

    class FoldRebalancer(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.seen, self.decisions, self.pending_sells, self.pending_buys = {}, [], 0, None

        def on_start(self):
            for bt in bar_types.values():
                self.subscribe_bars(bt)
            # No-op alerts at each ex-date instant give the engine a timestamp at which venue modules run
            # (the same mechanism as the peer's accepted parity fixture).
            self.alerts_fired = []
            for instant in alerts:
                self.clock.set_time_alert_ns(f"ex_{instant}", instant, self.on_ex_alert, allow_past=False)

        def on_ex_alert(self, event):
            self.alerts_fired.append(int(event.ts_event))

        def net_qty(self, a):
            return sum(int(number(p.signed_qty)) for p in self.cache.positions_open(instrument_id=instruments[a].id))

        def on_bar(self, bar):
            day = dt.datetime.fromtimestamp(bar.ts_event / 1e9, NY).date().isoformat()
            closes = self.seen.setdefault(day, {})
            closes[by_id[str(bar.bar_type.instrument_id)]] = number(bar.close)
            if len(closes) < len(assets) or day not in plan:
                return
            weights = plan[day]
            cash = number(self.cache.account_for_venue(venue).balance_total(usd))
            held = {a: self.net_qty(a) for a in assets}
            equity = cash + sum(held[a] * closes[a] for a in assets)
            if weights is None:
                target = {a: 0 for a in assets}
            else:
                target = {a: int((equity * INVEST * Decimal(repr(weights[a])) / closes[a]).to_integral_value(ROUND_FLOOR))
                          for a in assets}
            delta = {a: target[a] - held[a] for a in assets}
            self.decisions.append({"date": day, "native_cash": str(cash), "native_held": held,
                                   "native_equity": str(equity), "target": target})
            sells = [a for a in assets if delta[a] < 0]
            self.pending_buys = [(a, delta[a]) for a in assets if delta[a] > 0]
            self.pending_sells = len(sells)
            for a in sells:
                self.submit_order(self.order_factory.market(instruments[a].id, OrderSide.SELL, Quantity.from_int(-delta[a])))
            if self.pending_sells == 0:
                self.submit_buys()

        def submit_buys(self):
            buys, self.pending_buys = self.pending_buys or [], None
            for a, q in buys:
                self.submit_order(self.order_factory.market(instruments[a].id, OrderSide.BUY, Quantity.from_int(q)))

        def on_order_filled(self, event):
            if event.order_side == OrderSide.SELL and self.pending_sells > 0:
                self.pending_sells -= 1
                if self.pending_sells == 0:
                    self.submit_buys()

        def on_order_denied(self, event):
            self.decisions.append({"denied": str(event.client_order_id), "reason": event.reason})

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(CAPITAL, usd)], base_currency=usd,
                         fee_model=FixedFeeModel(Money(FEE, usd)), modules=modules)
        for inst in instruments.values():
            engine.add_instrument(inst)
        engine.add_data(data)
        strategy = FoldRebalancer()
        engine.add_strategy(strategy)
        engine.run()
        reports = {"account": engine.generate_account_report(venue=venue),
                   "positions": engine.generate_positions_report(),
                   "fills": engine.generate_order_fills_report()}
        for name, report in reports.items():
            report.to_csv(out / f"{name}.csv")
        parsed = {n: json.loads(r.reset_index().to_json(orient="records")) for n, r in reports.items()}
        common.dump(out / "decisions.json", strategy.decisions)
        return parsed, strategy.decisions, {
            "open_positions": len(engine.cache.positions_open()), "open_orders": len(engine.cache.orders_open()),
            "report_sha256": {n: common.digest(out / f"{n}.csv") for n in reports}}
    finally:
        engine.dispose()




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise SystemExit("native version mismatch")
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False)
    dist = load_distribution()
    frozen = common.frozen_panel()
    export = json.loads(args.weights.read_text())
    assets, schedule, final_close = export["assets"], export["schedule"], export["final_close"]
    start = schedule[0]["rebalance_close"]
    bars = load_bars(frozen["root"], assets, start, final_close)
    events = {a: distribution_events(dist, frozen["root"], a, start, final_close) for a in assets}
    summary = {"engine": importlib.metadata.version("nautilus_trader"), "weights_sha256": common.digest(args.weights),
               "runner_sha256": common.digest(__file__), "vendored_distribution_module": {
                   "path": str(VENDORED.relative_to(common.ROOT)), "sha256": VENDORED_SHA256,
                   "source": "origin/main 51d66001205dfe7722555d69b0a3f29d09a2164e blueprints/us-equities/engine-nautilus/spy-parity/distribution_module.py"},
               "distribution_events": {a: len(v) for a, v in events.items()},
               "capital_usd": str(CAPITAL), "invest_fraction": str(INVEST), "fee_per_order_usd": str(FEE), "optimizers": {}}
    for key in ("meanrisk_min_variance", "hrp_variance"):
        sub = args.out / key
        sub.mkdir()
        modules = [dist.build_module(events[a], f"{a}.SIM", "USD") for a in assets]
        alerts = sorted({e["ex_instant_ns"] for a in assets for e in events[a]})
        parsed, decisions, state = run_engine(schedule, bars, assets, key, final_close, sub, modules, alerts)
        module_log = [{"instrument": f"{a}.SIM", "emissions": m.emissions, "acknowledgements": m.acknowledgements,
                       "errors": m.errors, "process_calls": m.process_calls} for a, m in zip(assets, modules)]
        common.dump(sub / "modules.json", module_log)
        if any(m["errors"] for m in module_log):
            raise ValueError("distribution module errors: " + json.dumps([m["errors"] for m in module_log]))
        transitions, snapshots, credits, final_cash, final_shares = ledger(schedule, bars, assets, key, final_close, events)
        if state["open_positions"] or state["open_orders"] or any(final_shares.values()):
            raise ValueError(f"not flat at the end: {state} {final_shares}")
        rec = check(parsed, decisions, module_log, transitions, snapshots, credits, FEE)
        if rec["ending_cash"] != final_cash:
            raise ValueError("ending cash differs from the ledger")
        fills, ledger_cash = [t for t in transitions if t["kind"] == "fill"], [t["cash_after"] for t in transitions]
        native_cash = [number(a["total"]) for a in parsed["account"]]
        # Fee perturbation: a ledger charging 0.01 USD more per order must fail the same check.
        p_trans, p_snaps, p_credits, _, _ = ledger(schedule, bars, assets, key, final_close, events, FEE + Decimal("0.01"))
        try:
            check(parsed, decisions, module_log, p_trans, p_snaps, p_credits, FEE + Decimal("0.01"))
            detected = False
        except ValueError as exc:
            detected = str(exc)[:160]
        if not detected:
            raise SystemExit("fee perturbation not detected")
        summary.setdefault("self_test", {})[key] = {"perturbation": "ledger fee +0.01 USD", "detected": detected}
        summary.setdefault("mutation_self_tests", {})[key] = mutation_self_tests(
            lambda p, d, m: check(p, d, m, transitions, snapshots, credits, FEE), parsed, decisions, module_log, transitions)
        dividend_cash = sum(Decimal(c["amount"]) for c in credits)
        summary["optimizers"][key] = {
            **state, "fills_matched": len(fills), "account_transitions_matched": len(ledger_cash),
            "distribution_credits": len(credits), "nonzero_distribution_credits": sum(1 for c in credits if Decimal(c["amount"])),
            "dividend_cash_usd": str(dividend_cash), "fees_usd": str(FEE * len(fills)),
            "ending_cash_native": str(native_cash[-1]), "ending_cash_ledger": str(final_cash),
            "total_pnl_usd": str(final_cash - CAPITAL), "native_total_return": str((final_cash - CAPITAL) / CAPITAL),
            "final_shares": final_shares, "decisions_matched": len(snapshots)}
    summary["inputs_unchanged"] = common.inputs_unchanged(frozen)
    common.dump(args.out / "summary.json", summary)
    print(json.dumps({k: {x: v[x] for x in ("fills_matched", "account_transitions_matched", "nonzero_distribution_credits",
                                             "dividend_cash_usd", "ending_cash_native", "native_total_return")}
                      for k, v in summary["optimizers"].items()}, indent=1))


if __name__ == "__main__":
    main()
