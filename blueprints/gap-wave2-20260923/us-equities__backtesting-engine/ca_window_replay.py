#!/usr/bin/env python3
"""Gap-wave-2 check (us-equities/backtesting-engine gaps 1 and 8).

Native NautilusTrader 2.0.0rc5 replay of the retained, hash-verified Alpaca AAPL
daily raw bars over the FULL acquisition window 2020-08-03..2020-09-04, which
contains the 2020-08-07 cash-dividend ex-date and the 2020-08-31 4:1 forward-split
ex-date. It reuses the existing equity-replay collector verification, instrument
and bar convention (completed daily bar published at 16:00 New York) and native
engine/report APIs. It adds no corporate-action handling of its own.

Schedule: BUY 10 shares at the first bar, hold through both ex-dates, SELL 10 at the
last bar. Every bar the strategy records the native position quantity and the
native account cash, so a native dividend credit or split quantity adjustment
would appear as a cash or quantity change on a bar with no fill (detection method).
An independent Decimal ledger (fills only) is reconciled against native cash, and
an economic reference (4:1 split on 2020-08-31, dividend on 2020-08-07 per the
retained action records) is computed for comparison only.

Run inside the equity-replay bwrap isolation: no network, cleared environment,
read-only runtime, repository and data. No new data request, credential or broker.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import socket
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[3]
RECEIPT_SHA256 = "a59c6ed74e839ca43ee704033e207865ed938a22e4738afce22ec197e91b6bcd"
QTY = 10
CAPITAL = Decimal("100000")
NY = ZoneInfo("America/New_York")


def save(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def number(value):
    return Decimal(str(value).split()[0].replace(",", "").replace("_", ""))


def close_ns(session_date):
    return int(datetime.combine(date.fromisoformat(session_date), time(16), NY).timestamp()) * 10**9


def epoch_ns(moment):
    """Exact integer nanoseconds since the epoch (report timestamps carry at most microsecond digits)."""
    return (moment - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(microseconds=1) * 1000


def load(run):
    spec = importlib.util.spec_from_file_location("retained_alpaca_collector",
                                                  REPO / "blueprints/us-equities/alpaca-historical/collect.py")
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    stages = collector.verify(run, RECEIPT_SHA256)
    if any(stages[k]["status"] != "complete" for k in ("bars", "actions")):
        raise ValueError("incomplete_source")
    rows = stages["bars"]["rows"]
    if len(rows) != 25 or rows[0]["session_date"] != "2020-08-03" or rows[-1]["session_date"] != "2020-09-04":
        raise ValueError("unexpected_window")
    actions = [{k: a.get(k) for k in ("type", "ex_date", "payable_date", "record_date", "rate", "old_rate", "new_rate",
                                     "qualification")} for a in stages["actions"]["rows"]]
    kinds = sorted(a["type"] for a in actions)
    if kinds != ["cash_dividend", "forward_split"] or any(a["qualification"] != "qualified" or not a["ex_date"]
                                                           or not rows[0]["session_date"] < a["ex_date"] <= rows[-1]["session_date"]
                                                           for a in actions):
        raise ValueError("expected_one_qualified_dividend_and_split_inside_window")
    for row in rows:
        if Decimal(QTY) > Decimal(row["v"]) * Decimal("0.0001"):
            raise ValueError("daily_participation_limit")
    return rows, actions


def run_case(rows, out):
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import FixedFeeModel
    from nautilus_trader.model import AccountType, Bar, BarType, Currency, Equity, InstrumentId
    from nautilus_trader.model import Money, OmsType, OrderSide, Price, Quantity, Symbol, Venue
    from nautilus_trader.trading import Strategy

    usd, venue = Currency.from_str("USD"), Venue("SIM")
    equity = Equity(InstrumentId.from_str("AAPL.SIM"), Symbol("AAPL"), usd, 4,
                    Price.from_str("0.0100"), 0, 0, lot_size=Quantity.from_int(1))
    bar_type = BarType.from_str("AAPL.SIM-1-DAY-LAST-EXTERNAL")
    bars = [Bar(bar_type, *[Price.from_str(format(Decimal(r[k]), ".4f")) for k in ("o", "h", "l", "c")],
                Quantity.from_int(int(Decimal(r["v"]))), close_ns(r["session_date"]), close_ns(r["session_date"]))
            for r in rows]
    last = len(rows) - 1

    class HoldThroughActions(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.index = -1
            self.marks = []

        def on_start(self):
            self.subscribe_bars(bar_type)

        def mark(self, bar, phase):
            account = self.portfolio.account(venue)
            self.marks.append({"bar_index": self.index, "session_date": rows[self.index]["session_date"], "phase": phase,
                               "close": str(bar.close), "net_position": str(self.portfolio.net_position(equity.id)),
                               "cash_total": str(account.balance_total(usd)) if account else None})

        def on_bar(self, bar):
            self.index += 1
            self.mark(bar, "before_order")
            side = OrderSide.BUY if self.index == 0 else OrderSide.SELL if self.index == last else None
            if side is not None:
                self.submit_order(self.order_factory.market(equity.id, side, Quantity.from_int(QTY)))

        def on_stop(self):
            account = self.portfolio.account(venue)
            self.marks.append({"phase": "on_stop", "net_position": str(self.portfolio.net_position(equity.id)),
                               "cash_total": str(account.balance_total(usd))})

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(CAPITAL, usd)], base_currency=usd,
                         fee_model=FixedFeeModel(Money(Decimal(0), usd)))
        engine.add_instrument(equity)
        engine.add_data(bars)
        strategy = HoldThroughActions()
        engine.add_strategy(strategy)
        engine.run()
        result = engine.get_result()
        reports = {"account": engine.generate_account_report(venue=venue),
                   "positions": engine.generate_positions_report(),
                   "fills": engine.generate_order_fills_report()}
        for name, report in reports.items():
            report.to_csv(out / (name + ".csv"))
        data = {name: json.loads(report.to_json(orient="records", date_format="iso")) for name, report in reports.items()}
        save(out / "reports.json", data)
        return {"iterations": result.iterations, "marks": strategy.marks, "reports": data,
                "open_positions": len(engine.cache.positions_open()), "open_orders": len(engine.cache.orders_open()),
                "report_sha256": {n: hashlib.sha256((out / (n + ".csv")).read_bytes()).hexdigest() for n in reports}}
    finally:
        engine.dispose()


def reconcile(rows, actions, native):
    fills = native["reports"]["fills"]
    accounts = native["reports"]["account"]
    expected = [(0, "BUY"), (len(rows) - 1, "SELL")]
    checks = {}
    checks["fill_count"] = len(fills) == 2
    ledger, cash = [], CAPITAL
    for fill, (i, side) in zip(fills, expected):
        px = number(fill["avg_px"])
        checks[f"fill_{side}_side_qty"] = fill["side"] == side and number(fill["filled_qty"]) == QTY
        checks[f"fill_{side}_at_raw_close"] = px == Decimal(rows[i]["c"])
        stamps = [datetime.fromisoformat(fill[k].replace("Z", "+00:00")) for k in ("ts_init", "ts_last")]
        checks[f"fill_{side}_at_bar_instant"] = all(epoch_ns(t) == close_ns(rows[i]["session_date"]) for t in stamps)
        cash += -QTY * px if side == "BUY" else QTY * px
        ledger.append({"session_date": rows[i]["session_date"], "side": side, "qty": QTY, "price": str(px),
                       "raw_close": rows[i]["c"], "cash_after": str(cash)})
    native_final_cash = number(accounts[-1]["total"])
    checks["native_final_cash_equals_fill_only_ledger"] = native_final_cash == cash
    checks["account_events_equal_fills_plus_initial"] = len(accounts) == len(fills) + 1
    marks = [m for m in native["marks"] if m.get("phase") == "before_order"]
    held = [m for m in marks if 1 <= m["bar_index"] <= len(rows) - 1]
    checks["one_mark_per_bar"] = [m["bar_index"] for m in marks] == list(range(len(rows))) and len(held) == len(rows) - 1
    stop = [m for m in native["marks"] if m.get("phase") == "on_stop"]
    checks["terminal_flat"] = (native["open_positions"] == 0 and native["open_orders"] == 0 and len(stop) == 1
                               and number(stop[0]["net_position"]) == 0 and number(stop[0]["cash_total"]) == cash)
    checks["position_quantity_constant_10_while_held"] = all(number(m["net_position"]) == QTY for m in held)
    buy_px = Decimal(rows[0]["c"])
    checks["cash_constant_while_held"] = all(number(m["cash_total"]) == CAPITAL - QTY * buy_px for m in held)
    div = next((a for a in actions if a["type"] == "cash_dividend"), None)
    split = next((a for a in actions if a["type"] == "forward_split"), None)
    ratio = Decimal(split["new_rate"]) / Decimal(split["old_rate"]) if split else Decimal(1)
    div_cash = QTY * Decimal(div["rate"]) if div else Decimal(0)
    sell_px = Decimal(rows[-1]["c"])
    economic = CAPITAL - QTY * buy_px + QTY * ratio * sell_px + div_cash
    split_idx = next(i for i, r in enumerate(rows) if r["session_date"] >= split["ex_date"])
    return {"checks": checks, "all_checks_pass": all(checks.values()), "fill_ledger": ledger,
            "native_final_cash_usd": str(native_final_cash), "native_realized_pnl_usd": str(native_final_cash - CAPITAL),
            "economic_reference": {"split_ratio": str(ratio), "dividend_per_share": div and div["rate"],
                                   "dividend_cash_usd": str(div_cash), "final_cash_usd": str(economic),
                                   "realized_pnl_usd": str(economic - CAPITAL),
                                   "native_minus_economic_usd": str(native_final_cash - economic),
                                   "missing_split_adjustment_usd": str(QTY * (ratio - 1) * sell_px),
                                   "unposted_dividend_usd": str(div_cash)},
            "split_ex_date_bar": {"pre_close": rows[split_idx - 1]["c"], "ex_close": rows[split_idx]["c"],
                                  "session_dates": [rows[split_idx - 1]["session_date"], rows[split_idx]["session_date"]]},
            "marks_around_actions": [m for m in marks if m["session_date"] in
                                     {"2020-08-06", "2020-08-07", "2020-08-13", "2020-08-28", "2020-08-31"}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("native_version_mismatch")
    os.umask(0o077)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    rows, actions = load(args.run)
    native = run_case(rows, args.out)
    recon = reconcile(rows, actions, native)
    summary = {"classification": "local integration with retained historical market data (Alpaca, authenticated 2026-09-20)",
               "engine_version": importlib.metadata.version("nautilus_trader"), "input_receipt_sha256": RECEIPT_SHA256,
               "sessions": len(rows), "window": [rows[0]["session_date"], rows[-1]["session_date"]],
               "actions_in_window": actions, "iterations": native["iterations"],
               "open_positions": native["open_positions"], "open_orders": native["open_orders"],
               "report_sha256": native["report_sha256"], "fills": native["reports"]["fills"],
               "positions": native["reports"]["positions"], "account": native["reports"]["account"],
               "reconciliation": recon, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "network_interfaces": socket.if_nameindex(), "environment_names": sorted(os.environ),
               "completed_utc": datetime.now(timezone.utc).isoformat()}
    save(args.out / "summary.json", summary)
    print(json.dumps({"checks": recon["checks"], "native_final_cash_usd": recon["native_final_cash_usd"],
                      "economic_reference": recon["economic_reference"], "iterations": native["iterations"]}, sort_keys=True))
    raise SystemExit(0 if recon["all_checks_pass"] else 1)


if __name__ == "__main__":
    main()
