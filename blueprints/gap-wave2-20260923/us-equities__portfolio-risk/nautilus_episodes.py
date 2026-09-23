#!/usr/bin/env python3
"""Gap 11: execute every observed evaluation episode of the research-evaluation study in native Nautilus.

Episodes come from the regenerated candidate ledger (gap 3; byte-identical to the retained private ledger).
For each candidate (momentum20/60/120, cash, equalweight), one native NautilusTrader 2.0.0rc5 BacktestEngine
replays all of its observed development and reserved evaluation episodes: at the entry open, buy
floor(100,000 USD x weight / open) shares of each weighted asset; at the exit open, sell them. Opens are fed
as synthetic open-print daily bars (O=H=L=C=raw LEAN open) at 09:30 New York, a declared convention.
Cases: fixed (FixedFeeModel 1 USD per order) and per_share (PerContractFeeModel 0.01 USD per share).
Financing is explicitly zero: CASH account, long only, no borrowing; the rc5 backtest package exposes only
FXRolloverInterestModule and CfdSwapModule financing modules, neither applicable to cash equities.
Dividends are not credited (raw prices); unmodelled dividend cash inside each holding is reported.
"""
import argparse
import datetime as dt
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
import gzip
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from nautilus_portfolio import dividends, load_bars, number  # noqa: E402

NOTIONAL, CAPITAL = Decimal("100000"), Decimal("1000000")
NY = ZoneInfo("America/New_York")
CASES = {"fixed": {"kind": "FixedFeeModel", "usd": "1", "slippage_ticks": 0},
         "fixed_one_tick_slippage": {"kind": "FixedFeeModel", "usd": "1", "slippage_ticks": 1},
         "per_share": {"kind": "PerContractFeeModel", "usd": "0.01", "slippage_ticks": 0}}
TICK = Decimal("0.0001")
LEDGER_SHA256 = "08ea5309466045574ba4b9c8524608ed66c91edb22cb592a5bad84e1e2f42672"


def episodes_for(ledger, candidate, opens):
    out = []
    for r in ledger:
        if r["phase"] != "evaluation" or r["status"] != "observed" or r["candidate"] != candidate:
            continue
        legs = {a: int((NOTIONAL * Decimal(w) / opens[a][r["entry"]]).to_integral_value(ROUND_FLOOR))
                for a, w in r["weights"].items()}
        out.append({"fold": r["fold"], "decision": r["decision"], "entry": r["entry"], "exit": r["exit"],
                    "legs": {a: q for a, q in legs.items() if q > 0}, "weights": r["weights"],
                    "gross_price_label": Decimal(r["gross_price_label"]), "net_proxy": Decimal(r["net_proxy"])})
    return out


def commission(case, qty):
    return Decimal(CASES[case]["usd"]) * (qty if CASES[case]["kind"] == "PerContractFeeModel" else 1)


def run_engine(case, eps, bars, assets, out):
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import FixedFeeModel, OneTickSlippageFillModel, PerContractFeeModel
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
            stamp = int(dt.datetime.combine(dt.date.fromisoformat(b["date"]), dt.time(9, 30), NY).timestamp()) * 10**9
            px = Price.from_str(format(b["open"], ".4f"))
            data.append(Bar(btypes[a], px, px, px, px, Quantity.from_int(b["volume"]), stamp, stamp))
    actions = {}
    for i, e in enumerate(eps):
        for a, q in e["legs"].items():
            actions.setdefault(e["exit"], {"SELL": [], "BUY": []})["SELL"].append((i, a, q))
            actions.setdefault(e["entry"], {"SELL": [], "BUY": []})["BUY"].append((i, a, q))
    by_id = {str(inst[a].id): a for a in assets}

    class EpisodeReplay(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.seen, self.orders_log, self.denied = {}, [], []

        def on_start(self):
            for bt in btypes.values():
                self.subscribe_bars(bt)

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

    fee = (FixedFeeModel(Money(Decimal(CASES[case]["usd"]), usd)) if CASES[case]["kind"] == "FixedFeeModel"
           else PerContractFeeModel(Money(Decimal(CASES[case]["usd"]), usd)))
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        extra = {"fill_model": OneTickSlippageFillModel(1.0, 0.0, 42)} if CASES[case]["slippage_ticks"] else {}
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(CAPITAL, usd)], base_currency=usd, fee_model=fee,
                         **extra)
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
                                         "report_sha256": {n: common.digest(out / f"{n}.csv") for n in reports}}
    finally:
        engine.dispose()


def reconcile(case, eps, parsed, log, denied, state, opens):
    if denied:
        raise ValueError(f"denied or rejected orders: {denied[:3]}")
    fills = {f["client_order_id"]: f for f in parsed["fills"]}
    if set(fills) != {o["client_order_id"] for o in log}:
        raise ValueError("filled set differs from submitted set")
    cash, pnl = CAPITAL, [Decimal(0)] * len(eps)
    fees_total, sequence = Decimal(0), []
    for o in log:
        f = fills[o["client_order_id"]]
        px = opens[o["asset"]][o["date"]] + CASES[case]["slippage_ticks"] * TICK * (1 if o["side"] == "BUY" else -1)
        fee = commission(case, o["qty"])
        fill_day = dt.datetime.fromtimestamp(f["ts_last"] / 1e3, NY).strftime("%Y-%m-%d %H:%M:%S.%f")
        if (f["status"] != "FILLED" or f["side"] != o["side"] or number(f["filled_qty"]) != o["qty"]
                or f["instrument_id"] != f"{o['asset']}.SIM" or fill_day != o["date"] + " 09:30:00.000000"
                or number(f["avg_px"]) != px or sum(number(c) for c in f["commissions"]) != fee):
            raise ValueError(f"fill mismatch {o}")
        # Native USD Money carries two decimals: each fill's notional settles rounded to the cent.
        signed = (o["qty"] * px).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) * (1 if o["side"] == "SELL" else -1)
        cash += signed - fee
        sequence.append(cash)
        pnl[o["episode"]] += signed - fee
        fees_total += fee
    native = [number(a["total"]) for a in parsed["account"]]
    if native[0] != CAPITAL or native[1:] != sequence:
        raise ValueError(f"cash transitions differ: native rows {len(native)}, ledger {len(sequence)}, "
                         f"ending native {native[-1]} ledger {cash}")
    if state["open_positions"] or state["open_orders"]:
        raise ValueError("not flat")
    return cash, pnl, fees_total, len(native)


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
    parser.add_argument("--ledger", type=Path, required=True, help="regenerated candidate-ledger.json.gz")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise SystemExit("native version mismatch")
    raw = gzip.decompress(args.ledger.read_bytes())
    import hashlib
    if hashlib.sha256(raw).hexdigest() != LEDGER_SHA256:
        raise SystemExit("ledger is not the retained candidate ledger")
    ledger = json.loads(raw)
    os.umask(0o077)
    args.out.mkdir(parents=True, exist_ok=False)
    frozen = common.frozen_panel()
    assets = frozen["plan"]["assets"]
    first = min(r["entry"] for r in ledger if r["phase"] == "evaluation" and r["status"] == "observed")
    last = max(r["exit"] for r in ledger if r["phase"] == "evaluation" and r["status"] == "observed")
    bars = load_bars(frozen["root"], assets, first, last)
    opens = {a: {b["date"]: b["open"] for b in bars[a]} for a in assets}
    divs = dividends(frozen["root"], assets, first, last)
    dates = [b["date"] for b in bars[assets[0]]]
    summary = {"engine": importlib.metadata.version("nautilus_trader"), "runner_sha256": common.digest(__file__),
               "ledger_sha256": LEDGER_SHA256, "first_entry": first, "last_exit": last, "notional_usd": str(NOTIONAL),
               "cases": CASES, "financing": "explicit zero: CASH account, long only, no borrowing",
               "backtest_financing_modules_available": ["FXRolloverInterestModule", "CfdSwapModule"],
               "candidates": {}}
    for cand in frozen["plan"]["candidates"]:
        eps = episodes_for(ledger, cand, opens)
        # Unmodelled dividends: an ex-date (session after last_cum_date) in (entry, exit] while holding.
        unmodelled = Decimal(0)
        for d in divs:
            ex = dates[dates.index(d["last_cum_date"]) + 1] if d["last_cum_date"] in dates[:-1] else None
            for e in eps:
                if ex and e["entry"] < ex <= e["exit"] and d["asset"] in e["legs"]:
                    unmodelled += e["legs"][d["asset"]] * d["per_share"]
        n = Decimal(len(eps))
        entry = {"episodes": len(eps), "invested_episodes": sum(bool(e["legs"]) for e in eps),
                 "mean_gross_price_label": str(sum(e["gross_price_label"] for e in eps) / n),
                 "mean_net_cost_proxy_label": str(sum(e["net_proxy"] for e in eps) / n),
                 "unmodelled_dividend_cash_usd": str(unmodelled.quantize(Decimal("0.01"))), "cases": {}}
        for case in CASES:
            sub = args.out / cand / case
            sub.mkdir(parents=True)
            if not any(e["legs"] for e in eps):
                entry["cases"][case] = {"orders": 0, "note": "no invested episode; engine not needed"}
                continue
            parsed, log, denied, state = run_engine(case, eps, bars, assets, sub)
            cash, pnl, fees, rows = reconcile(case, eps, parsed, log, denied, state, opens)
            mutations = mutation_self_tests(lambda p, e: reconcile(case, eps, p, log, denied, state, opens), parsed)
            ret = [p / NOTIONAL for p in pnl]
            mean_native = sum(ret) / n
            entry["cases"][case] = {
                "orders": len(log), "fills_reconciled": len(log), "account_rows": rows,
                "ending_cash_native_equals_ledger": str(cash), "total_pnl_usd": str(cash - CAPITAL),
                "fees_usd": str(fees), "mean_native_net_return_per_episode": str(mean_native),
                "mean_effective_cost_vs_gross_label": str(Decimal(entry["mean_gross_price_label"]) - mean_native),
                "mean_native_minus_net_proxy": str(mean_native - Decimal(entry["mean_net_cost_proxy_label"])),
                "report_sha256": state["report_sha256"], "mutation_self_tests": mutations}
        summary["candidates"][cand] = entry
    summary["inputs_unchanged"] = common.inputs_unchanged(frozen)
    common.dump(args.out / "summary.json", summary)
    print(json.dumps({c: {"episodes": v["episodes"], "gross": v["mean_gross_price_label"][:10], "proxy": v["mean_net_cost_proxy_label"][:10],
                          **{k: x.get("mean_native_net_return_per_episode", "n/a")[:10] for k, x in v["cases"].items()}}
                      for c, v in summary["candidates"].items()}, indent=1))


if __name__ == "__main__":
    main()
