#!/usr/bin/env python3
"""Gap 6: skfolio target weights through a native NautilusTrader 2.0.0rc5 RiskEngine with numeric limits.

Two arms on the same raw LEAN SPY/QQQ/IWM daily bars (2021-01-04..2021-01-08), 1,000,000 USD CASH account,
FixedFeeModel 1 USD per order:
  limits:  RiskEngineConfig(max_notional_per_order=45000 USD per instrument, max_order_submit_rate=4/00:00:01)
  control: RiskEngineConfig() defaults (no notional limit; native default submit rate)
Schedule (identical in both arms):
  2021-01-04 close: buy integer shares of the skfolio reserved HRP weights x 100,000 USD (all under 45,000 USD)
  2021-01-05 close: one deliberately oversized SPY buy of floor(60,000 / close) shares
  2021-01-06 close: a burst of six 1-share QQQ buys submitted at the same timestamp
  2021-01-08 close: liquidate every open position
Every native fill, fee and cash transition is reconciled to an independent ledger built from the strategy's
own submission log, the bars, and the set of orders the engine denied.
"""
import argparse
import datetime as dt
from decimal import ROUND_FLOOR, Decimal
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from nautilus_portfolio import load_bars, number  # noqa: E402

CAPITAL, BASE, FEE = Decimal("1000000"), Decimal("100000"), Decimal("1")
LIMIT, OVERSIZED, RATE = "45000", Decimal("60000"), "4/00:00:01"
NY = ZoneInfo("America/New_York")
DAYS = {"target": "2021-01-04", "oversized": "2021-01-05", "burst": "2021-01-06", "liquidate": "2021-01-08"}


def run_arm(arm, weights, bars, assets, out):
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, RiskEngineConfig, StrategyConfig
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
            stamp = int(dt.datetime.combine(dt.date.fromisoformat(b["date"]), dt.time(16), NY).timestamp()) * 10**9
            data.append(Bar(btypes[a], *[Price.from_str(format(b[k], ".4f")) for k in ("open", "high", "low", "close")],
                            Quantity.from_int(b["volume"]), stamp, stamp))
    by_id = {str(inst[a].id): a for a in assets}

    class LimitProbe(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.closes, self.submitted, self.denied, self.rejected = {}, [], [], []

        def on_start(self):
            for bt in btypes.values():
                self.subscribe_bars(bt)

        def send(self, day, tag, a, side, qty):
            order = self.order_factory.market(inst[a].id, side, Quantity.from_int(qty))
            self.submitted.append({"client_order_id": str(order.client_order_id), "date": day, "tag": tag,
                                   "asset": a, "side": str(side).split(".")[-1], "qty": qty,
                                   "notional": str(qty * self.closes[day][a])})
            self.submit_order(order)

        def on_bar(self, bar):
            day = dt.datetime.fromtimestamp(bar.ts_event / 1e9, NY).date().isoformat()
            c = self.closes.setdefault(day, {})
            c[by_id[str(bar.bar_type.instrument_id)]] = number(bar.close)
            if len(c) < len(assets):
                return
            if day == DAYS["target"]:
                for a in assets:
                    q = int((BASE * Decimal(repr(weights[a])) / c[a]).to_integral_value(ROUND_FLOOR))
                    self.send(day, "target", a, OrderSide.BUY, q)
            elif day == DAYS["oversized"]:
                self.send(day, "oversized", "SPY", OrderSide.BUY, int((OVERSIZED / c["SPY"]).to_integral_value(ROUND_FLOOR)))
            elif day == DAYS["burst"]:
                for _ in range(6):
                    self.send(day, "burst", "QQQ", OrderSide.BUY, 1)
            elif day == DAYS["liquidate"]:
                for a in assets:
                    q = sum(int(number(p.signed_qty)) for p in self.cache.positions_open(instrument_id=inst[a].id))
                    if q > 0:
                        self.send(day, "liquidate", a, OrderSide.SELL, q)

        def on_order_denied(self, event):
            self.denied.append({"client_order_id": str(event.client_order_id), "reason": event.reason})

        def on_order_rejected(self, event):
            self.rejected.append({"client_order_id": str(event.client_order_id), "reason": event.reason})

    risk = (RiskEngineConfig(max_notional_per_order={f"{a}.SIM": LIMIT for a in assets}, max_order_submit_rate=RATE)
            if arm == "limits" else RiskEngineConfig())
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR), risk_engine=risk))
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(CAPITAL, usd)], base_currency=usd,
                         fee_model=FixedFeeModel(Money(FEE, usd)))
        for i in inst.values():
            engine.add_instrument(i)
        engine.add_data(data)
        s = LimitProbe()
        engine.add_strategy(s)
        engine.run()
        reports = {"account": engine.generate_account_report(venue=venue), "fills": engine.generate_order_fills_report(),
                   "positions": engine.generate_positions_report()}
        for n, r in reports.items():
            r.to_csv(out / f"{n}.csv")
        parsed = {n: json.loads(r.reset_index().to_json(orient="records")) for n, r in reports.items()}
        log = {"submitted": s.submitted, "denied": s.denied, "rejected": s.rejected,
               "open_positions": len(engine.cache.positions_open()), "open_orders": len(engine.cache.orders_open())}
        common.dump(out / "strategy-log.json", log)
        return parsed, log, {n: common.digest(out / f"{n}.csv") for n in reports}
    finally:
        engine.dispose()


def reconcile(parsed, log, bars, assets):
    close = {a: {b["date"]: b["close"] for b in bars[a]} for a in assets}
    if log["rejected"]:
        raise ValueError(f"venue rejections are not expected in this probe: {log['rejected']}")
    denied = {d["client_order_id"] for d in log["denied"]}
    expected = [o for o in log["submitted"] if o["client_order_id"] not in denied]
    fills = {f["client_order_id"]: f for f in parsed["fills"]}
    if set(fills) != {o["client_order_id"] for o in expected}:
        raise ValueError(f"filled set {sorted(fills)} != expected {[o['client_order_id'] for o in expected]}")
    cash, shares, sequence = CAPITAL, {a: 0 for a in assets}, []
    for o in expected:
        f = fills[o["client_order_id"]]
        px = close[o["asset"]][o["date"]]
        fill_day = dt.datetime.fromtimestamp(f["ts_last"] / 1e3, NY).strftime("%Y-%m-%d %H:%M:%S.%f")
        if (number(f["filled_qty"]) != o["qty"] or number(f["avg_px"]) != px or f["side"] != o["side"]
                or f["instrument_id"] != f"{o['asset']}.SIM" or fill_day != o["date"] + " 16:00:00.000000"
                or sum(number(c) for c in f["commissions"]) != FEE or f["status"] != "FILLED"):
            raise ValueError(f"fill mismatch {o['client_order_id']}")
        cash += (o["qty"] * px if o["side"] == "SELL" else -o["qty"] * px) - FEE
        sequence.append(cash)
        shares[o["asset"]] += o["qty"] if o["side"] == "BUY" else -o["qty"]
    native_cash = [number(a["total"]) for a in parsed["account"]]
    if native_cash[0] != CAPITAL or native_cash[1:] != sequence:
        raise ValueError(f"cash transitions differ: native {len(native_cash) - 1} rows, ledger {len(sequence)}")
    if any(shares.values()) or log["open_positions"] or log["open_orders"]:
        raise ValueError("not flat after liquidation")
    return {"expected_fills": len(expected), "native_fills": len(fills), "cash_transitions_matched": len(sequence),
            "ending_cash_native": str(native_cash[-1]), "ending_cash_ledger": str(cash),
            "fees_usd": str(FEE * len(expected)), "final_shares": shares, "account_rows": len(native_cash)}


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise SystemExit("native version mismatch")
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False)
    frozen = common.frozen_panel()
    export = json.loads(args.weights.read_text())
    assets = export["assets"]
    weights = next(e for e in export["schedule"] if e["id"] == "reserved-2021q1")["weights"]["hrp_variance"]
    bars = load_bars(frozen["root"], assets, DAYS["target"], DAYS["liquidate"])
    summary = {"engine": importlib.metadata.version("nautilus_trader"), "weights_sha256": common.digest(args.weights),
               "runner_sha256": common.digest(__file__), "hrp_reserved_weights": weights,
               "limits": {"max_notional_per_order_usd": LIMIT, "max_order_submit_rate": RATE}, "arms": {}}
    for arm in ("limits", "control"):
        sub = args.out / arm
        sub.mkdir()
        parsed, log, hashes = run_arm(arm, weights, bars, assets, sub)
        by_tag = {}
        for o in log["submitted"]:
            by_tag.setdefault(o["tag"], []).append(o["client_order_id"])
        denied = {d["client_order_id"]: d["reason"] for d in log["denied"]}
        summary["arms"][arm] = {
            "reconciliation": reconcile(parsed, log, bars, assets), "report_sha256": hashes,
            "mutation_self_tests": mutation_self_tests(
                lambda p, e: reconcile(p, e.get("log", log), bars, assets), parsed,
                {"venue_rejection_injected": lambda p, e: e.__setitem__("log", dict(log, rejected=[{"client_order_id": "X", "reason": "injected"}]))}),
            "submitted": len(log["submitted"]), "denied": log["denied"], "rejected": log["rejected"],
            "target_orders_denied": [i for i in by_tag["target"] if i in denied],
            "target_order_notionals": [o["notional"] for o in log["submitted"] if o["tag"] == "target"],
            "oversized_order": next(o for o in log["submitted"] if o["tag"] == "oversized"),
            "oversized_denied_reason": denied.get(by_tag["oversized"][0]),
            "burst_denied": [denied[i] for i in by_tag["burst"] if i in denied],
            "burst_filled": sum(1 for f in parsed["fills"] if f["client_order_id"] in by_tag["burst"]),
            "target_orders_filled": sum(1 for i in by_tag["target"] if i in {f["client_order_id"] for f in parsed["fills"]}),
            "target_orders_submitted": len(by_tag["target"]),
            "oversized_filled": by_tag["oversized"][0] in {f["client_order_id"] for f in parsed["fills"]},
        }
    lim, ctl = summary["arms"]["limits"], summary["arms"]["control"]
    summary["criteria"] = {
        "a_target_orders_filled_under_limits": lim["target_orders_filled"] == lim["target_orders_submitted"] == 3,
        "b_oversized_denied_with_notional_reason": (bool(lim["oversized_denied_reason"])
                                                    and "NOTIONAL" in lim["oversized_denied_reason"].upper()
                                                    and not lim["oversized_filled"]),
        "c_control_fills_oversized": ctl["oversized_filled"] and ctl["oversized_denied_reason"] is None,
        "d_burst_order_denied_by_rate": any("RATE" in r.upper() or "THROTTL" in r.upper() for r in lim["burst_denied"])
                                        and ctl["burst_filled"] == 6,
        "e_positions_and_cash_reconciled_both_arms": all(v["reconciliation"]["cash_transitions_matched"] == v["reconciliation"]["expected_fills"]
                                                         for v in summary["arms"].values()),
    }
    summary["inputs_unchanged"] = common.inputs_unchanged(frozen)
    common.dump(args.out / "summary.json", summary)
    print(json.dumps({"criteria": summary["criteria"], "limits_denied": lim["denied"], "control_denied": ctl["denied"],
                      "limits_burst_filled": lim["burst_filled"], "control_burst_filled": ctl["burst_filled"]}, indent=1))


if __name__ == "__main__":
    main()
