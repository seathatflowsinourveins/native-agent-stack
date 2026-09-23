#!/usr/bin/env python3
"""Gaps 4 and 10: run skfolio fold weights through native NautilusTrader 2.0.0rc5 and reconcile the accounting.

Local integration with retained public LEAN sample bars (raw, unadjusted SPY/QQQ/IWM daily OHLCV).
Each fold's weights are applied at the close of the session before its first test return, as integer
shares of 99% of the strategy's native account equity (cash plus position value at that close).
Sells are submitted first; buys follow once every sell has filled. Everything is liquidated at the last
close. Fees: native FixedFeeModel, 1 USD per order. CASH account, long only, no financing or borrowing.
Dividends are NOT credited by this engine configuration; the unmodelled dividend cash is computed from
LEAN factor files and reported separately. An independent Decimal ledger recomputes every order,
fill price, fee and cash transition from the weights and bars alone.
"""
import argparse
import csv
import datetime as dt
from decimal import ROUND_FLOOR, Decimal
import importlib.metadata
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

CAPITAL = Decimal("1000000")
INVEST = Decimal("0.99")
FEE = Decimal("1")
NY = ZoneInfo("America/New_York")


def number(value):
    return Decimal(str(value).split()[0].replace(",", "").replace("_", ""))


def load_bars(root, assets, start, end):
    bars = {}
    for asset in assets:
        with zipfile.ZipFile(root / f"Data/equity/usa/daily/{asset.lower()}.zip") as z:
            rows = list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())))
        out = []
        for r in rows:
            day = dt.datetime.strptime(r[0], "%Y%m%d %H:%M").date().isoformat()
            if start <= day <= end:
                o, h, lo, c = [Decimal(x) / 10000 for x in r[1:5]]
                out.append({"date": day, "open": o, "high": h, "low": lo, "close": c, "volume": int(r[5])})
        bars[asset] = out
    calendars = {a: [b["date"] for b in v] for a, v in bars.items()}
    if len({tuple(c) for c in calendars.values()}) != 1:
        raise ValueError("calendar mismatch")
    return bars


def dividends(root, assets, start, end):
    """Per-share cash dividends implied by LEAN factor rows: a factor change after row date d applies from
    the next session (ex-date); amount = reference_close x (1 - factor_d / factor_next)."""
    result = []
    for asset in assets:
        rows = list(csv.reader(io.StringIO((root / f"Data/equity/usa/factor_files/{asset.lower()}.csv").read_text())))
        for a, b in zip(rows, rows[1:]):
            day = dt.datetime.strptime(a[0], "%Y%m%d").date().isoformat()
            if not start <= day < end:
                continue
            if a[2] != b[2]:
                raise ValueError("split in interval")
            if Decimal(a[1]) != Decimal(b[1]):
                amount = Decimal(a[3]) * (1 - Decimal(a[1]) / Decimal(b[1]))
                result.append({"asset": asset, "last_cum_date": day, "per_share": amount})
    return result


def plan_orders(schedule, bars, assets, weight_key, final_close):
    """Independent ledger: recompute every order from weights and closes, without the engine."""
    close = {a: {b["date"]: b["close"] for b in bars[a]} for a in assets}
    cash, shares = CAPITAL, {a: 0 for a in assets}
    orders, snapshots = [], []
    events = [(e["rebalance_close"], e["weights"][weight_key], e["id"]) for e in schedule] + [(final_close, None, "liquidate")]
    for day, weights, label in events:
        equity = cash + sum(shares[a] * close[a][day] for a in assets)
        if weights is None:
            target = {a: 0 for a in assets}
        else:
            target = {a: int((equity * INVEST * Decimal(repr(weights[a])) / close[a][day]).to_integral_value(ROUND_FLOOR))
                      for a in assets}
        delta = {a: target[a] - shares[a] for a in assets}
        for side, pick in (("SELL", lambda q: q < 0), ("BUY", lambda q: q > 0)):
            for a in assets:
                if pick(delta[a]):
                    qty, px = abs(delta[a]), close[a][day]
                    cash += (qty * px if side == "SELL" else -qty * px) - FEE
                    shares[a] += qty if side == "BUY" else -qty
                    orders.append({"date": day, "asset": a, "side": side, "qty": qty, "price": px, "cash_after": cash})
        snapshots.append({"date": day, "label": label, "equity_before": equity, "target": target, "cash_after": cash})
    return orders, snapshots, cash, shares


def frictionless_buy_and_hold(schedule, bars, assets, weight_key, final_close):
    """Fractional, fee-free buy-and-hold within each fold at the same rebalance closes (convention isolation)."""
    close = {a: {b["date"]: b["close"] for b in bars[a]} for a in assets}
    value = Decimal(1)
    points = [e["rebalance_close"] for e in schedule] + [final_close]
    for e, nxt in zip(schedule, points[1:]):
        w = e["weights"][weight_key]
        growth = sum(Decimal(repr(w[a])) * close[a][nxt] / close[a][e["rebalance_close"]] for a in assets)
        value *= growth / sum(Decimal(repr(w[a])) for a in assets)
    return value - 1


def run_engine(schedule, bars, assets, weight_key, final_close, out):
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
                         fee_model=FixedFeeModel(Money(FEE, usd)))
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
        parsed = {n: json.loads(r.to_json(orient="records")) for n, r in reports.items()}
        common.dump(out / "decisions.json", strategy.decisions)
        return parsed, strategy.decisions, {
            "open_positions": len(engine.cache.positions_open()), "open_orders": len(engine.cache.orders_open()),
            "report_sha256": {n: common.digest(out / f"{n}.csv") for n in reports}}
    finally:
        engine.dispose()


def reconcile(orders, final_cash, parsed, decisions, snapshots, assets):
    fills, accounts, positions = parsed["fills"], parsed["account"], parsed["positions"]
    if any(d.get("denied") for d in decisions):
        raise ValueError("unexpected denial: " + json.dumps([d for d in decisions if d.get("denied")]))
    if len(fills) != len(orders):
        raise ValueError(f"fill count {len(fills)} != ledger orders {len(orders)}")
    native = sorted(((dt.datetime.fromtimestamp(f["ts_last"] / 1e3, NY).strftime("%Y-%m-%d %H:%M:%S.%f"), f["instrument_id"].split(".")[0],
                      f["side"], number(f["filled_qty"]), number(f["avg_px"]), sum(number(c) for c in f["commissions"]))
                     for f in fills))
    ledger = sorted((o["date"] + " 16:00:00.000000", o["asset"], o["side"], Decimal(o["qty"]), o["price"], FEE) for o in orders)
    if native != ledger:
        diff = [(n, l) for n, l in zip(native, ledger) if n != l][:5]
        raise ValueError(f"fill mismatch: {diff}")
    if any(f["status"] != "FILLED" for f in fills):
        raise ValueError("non-filled order in fills report")
    if number(accounts[0]["total"]) != CAPITAL or len(accounts) != len(orders) + 1:
        raise ValueError(f"account rows {len(accounts)} vs orders {len(orders)}")
    native_cash = [number(a["total"]) for a in accounts[1:]]
    ledger_cash = [o["cash_after"] for o in orders]
    if native_cash != ledger_cash:
        # Allow only an ordering difference within a single timestamp; totals per date must still match.
        raise ValueError("cash transition mismatch")
    native_targets = [d for d in decisions if "target" in d]
    if len(native_targets) != len(snapshots):
        raise ValueError(f"decision count {len(native_targets)} != ledger {len(snapshots)}")
    for d, s in zip(native_targets, snapshots):
        if d["date"] != s["date"] or Decimal(d["native_equity"]) != s["equity_before"] or d["target"] != s["target"]:
            raise ValueError(f"decision mismatch at {s['date']}")
    realized = sum(number(p["realized_pnl"]) for p in positions)
    return {"orders": len(orders), "fills_matched": len(fills), "cash_transitions_matched": len(native_cash),
            "decisions_matched": len(snapshots), "fees_usd": str(FEE * len(orders)),
            "ending_cash_native": str(native_cash[-1]), "ending_cash_ledger": str(final_cash),
            "total_pnl_usd": str(final_cash - CAPITAL),
            "positions_report_rows": len(positions), "positions_realized_pnl_sum": str(realized),
            "positions_realized_equals_cash_pnl": realized == final_cash - CAPITAL}


def mutation_self_tests(check, parsed, extra=None):
    """Mutate copies of the native reports and require that `check` rejects each one."""
    import copy
    mutations = {
        "wrong_instrument_first_fill": lambda p, e: p["fills"][0].__setitem__("instrument_id", "WRONG.SIM"),
        "fill_time_1900": lambda p, e: p["fills"][0].__setitem__("ts_last", -2208988800000),
        "fill_time_shifted_one_hour": lambda p, e: p["fills"][0].__setitem__("ts_last", p["fills"][0]["ts_last"] + 3600000),
        "cash_corrupted_first_transition": lambda p, e: p["account"][1].__setitem__(
            "total", str(Decimal(str(p["account"][1]["total"]).split()[0]) + Decimal("12345.67"))),
    }
    mutations.update(extra or {})
    results = {}
    for name, mutate in mutations.items():
        p = copy.deepcopy(parsed)
        e = {}
        mutate(p, e)
        try:
            check(p, e)
            results[name] = False
        except (ValueError, KeyError, IndexError) as exc:
            results[name] = str(exc)[:160]
    if not all(results.values()):
        raise SystemExit(f"reconciliation failed to detect a mutation: {results}")
    return results


def main():
    global FEE
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--self-test-fee-perturbation", action="store_true",
                        help="Perturb the ledger fee by one cent to prove the reconciliation detects it")
    args = parser.parse_args()
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise SystemExit("native version mismatch")
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False)
    frozen = common.frozen_panel()
    export = json.loads(args.weights.read_text())
    assets, schedule, final_close = export["assets"], export["schedule"], export["final_close"]
    start = schedule[0]["rebalance_close"]
    bars = load_bars(frozen["root"], assets, start, final_close)
    divs = dividends(frozen["root"], assets, start, final_close)
    summary = {"engine": importlib.metadata.version("nautilus_trader"), "weights_sha256": common.digest(args.weights),
               "runner_sha256": common.digest(__file__), "plan_sha256": frozen["plan_sha256"],
               "bars_per_asset": len(bars[assets[0]]), "first_bar": bars[assets[0]][0]["date"], "last_bar": final_close,
               "capital_usd": str(CAPITAL), "invest_fraction": str(INVEST), "fee_per_order_usd": str(FEE),
               "account": "CASH, NETTING, long only, no financing or borrowing", "optimizers": {}}
    for key in ("meanrisk_min_variance", "hrp_variance"):
        sub = args.out / key
        sub.mkdir()
        orders, snapshots, final_cash, final_shares = plan_orders(schedule, bars, assets, key, final_close)
        parsed, decisions, state = run_engine(schedule, bars, assets, key, final_close, sub)
        if args.self_test_fee_perturbation:
            real, FEE = FEE, FEE + Decimal("0.01")
            try:
                orders_p, snaps_p, cash_p, _ = plan_orders(schedule, bars, assets, key, final_close)
                reconcile(orders_p, cash_p, parsed, decisions, snaps_p, assets)
                detected = False
            except ValueError as exc:
                detected = str(exc)
            finally:
                FEE = real
            summary.setdefault("self_test", {})[key] = {"perturbation": "ledger fee +0.01 USD", "detected": detected}
        rec = reconcile(orders, final_cash, parsed, decisions, snapshots, assets)
        summary.setdefault("mutation_self_tests", {})[key] = mutation_self_tests(
            lambda p, e: reconcile(orders, final_cash, p, e.get("decisions", decisions), snapshots, assets), parsed,
            {"all_decisions_removed": lambda p, e: e.__setitem__("decisions", [])})
        # Unmodelled dividends: shares held (ledger) at each ex-date's last cum-dividend close.
        held_by_day = {}
        shares = {a: 0 for a in assets}
        for day in sorted({b["date"] for b in bars[assets[0]]}):
            for o in [o for o in orders if o["date"] == day]:
                shares[o["asset"]] += o["qty"] if o["side"] == "BUY" else -o["qty"]
            held_by_day[day] = dict(shares)
        unmodelled = sum(Decimal(held_by_day[d["last_cum_date"]][d["asset"]]) * d["per_share"]
                         for d in divs if d["last_cum_date"] in held_by_day and d["last_cum_date"] < final_close)
        desc = Decimal(1)
        for e in schedule:
            desc *= 1 + Decimal(repr(e["descriptive"][key]["compounded"]))
        summary["optimizers"][key] = {
            **rec, **state, "final_shares": final_shares,
            "native_total_return": str((final_cash - CAPITAL) / CAPITAL),
            "skfolio_descriptive_total_return_daily_rebalanced_cost_free": str(desc - 1),
            "frictionless_fractional_buy_and_hold_total_return": str(frictionless_buy_and_hold(schedule, bars, assets, key, final_close)),
            "unmodelled_dividend_cash_usd": str(unmodelled.quantize(Decimal("0.01"))),
            "dividend_events_in_span": len(divs)}
    summary["inputs_unchanged"] = common.inputs_unchanged(frozen)
    common.dump(args.out / "summary.json", summary)
    print(json.dumps({k: {x: v[x] for x in ("orders", "ending_cash_native", "total_pnl_usd", "native_total_return",
                                             "skfolio_descriptive_total_return_daily_rebalanced_cost_free",
                                             "unmodelled_dividend_cash_usd")} for k, v in summary["optimizers"].items()}, indent=1))


if __name__ == "__main__":
    main()
