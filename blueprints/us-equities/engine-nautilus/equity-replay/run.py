#!/usr/bin/env python3
"""Local integration of retained Alpaca bars and native Nautilus equity execution."""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import socket
from zoneinfo import ZoneInfo

SOURCE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def select_rows(stages, plan):
    """Require a complete verified source and narrow away known action dates."""
    if any(stages[k]["status"] != "complete" for k in ("bars", "actions")):
        raise ValueError("incomplete_source")
    rows = [r for r in stages["bars"]["rows"] if plan["start"] <= r["session_date"] <= plan["end"]]
    expected = [date.fromordinal(i).isoformat() for i in range(date.fromisoformat(plan["start"]).toordinal(),
                date.fromisoformat(plan["end"]).toordinal() + 1) if date.fromordinal(i).weekday() < 5]
    if len(rows) != plan["expected_sessions"] or [r["session_date"] for r in rows] != expected:
        raise ValueError("session_coverage_or_order")
    for action in stages["actions"]["rows"]:
        if not action.get("ex_date"):
            raise ValueError("unknown_action_date")
        if plan["start"] <= action["ex_date"] <= plan["end"]:
            raise ValueError("corporate_action_in_replay")
    for row in rows:
        if row["symbol"] != plan["symbol"]:
            raise ValueError("wrong_symbol")
        numbers = {k: Decimal(row[k]) for k in ("o", "h", "l", "c", "v")}
        if any(not n.is_finite() or n <= 0 for n in numbers.values()):
            raise ValueError("invalid_bar_number")
        if any(n != n.quantize(Decimal("0.0001")) for k, n in numbers.items() if k != "v"):
            raise ValueError("unsupported_price_precision")
        if numbers["l"] > min(numbers["o"], numbers["c"]) or numbers["h"] < max(numbers["o"], numbers["c"], numbers["l"]):
            raise ValueError("invalid_ohlc")
        if numbers["v"] != numbers["v"].to_integral_value():
            raise ValueError("nonintegral_volume")
        if Decimal(plan["quantity"]) > numbers["v"] * Decimal(plan["maximum_daily_volume_fraction"]):
            raise ValueError("daily_participation_limit")
    return rows


def load_rows(run, plan):
    collector_path = SOURCE.parents[1] / "alpaca-historical" / "collect.py"
    spec = importlib.util.spec_from_file_location("retained_alpaca_collector", collector_path)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    return select_rows(collector.verify(run, plan["alpaca_receipt_sha256"]), plan)


def number(value):
    """Parse native report numeric values, including currency suffixes."""
    return Decimal(str(value).split()[0].replace(",", "").replace("_", ""))


def audit_reports(rows, plan, case, fills, positions, accounts):
    """Independently match every native fill and cash transition to the fixed schedule."""
    schedule = sorted([(i, "BUY") for i in plan["entry_indices"]] + [(i, "SELL") for i in plan["exit_indices"]])
    if len(fills) != len(schedule) or len(accounts) != len(fills) + 1 or len(positions) != len(plan["exit_indices"]):
        raise ValueError("report_counts")
    if len({f["venue_order_id"] for f in fills}) != len(fills):
        raise ValueError("duplicate_order_identity")
    cash, fees, position = Decimal(plan["capital_usd"]), Decimal(0), Decimal(0)
    if number(accounts[0]["total"]) != cash:
        raise ValueError("initial_cash")
    for index, (fill, (bar_index, side)) in enumerate(zip(fills, schedule)):
        row = rows[bar_index]
        close_time = datetime.combine(date.fromisoformat(row["session_date"]), time(16), ZoneInfo("America/New_York"))
        expected_ms = int(close_time.timestamp()) * 1000
        qty = Decimal(plan["quantity"])
        price = Decimal(row["c"]) + ((Decimal("0.01") if side == "BUY" else Decimal("-0.01")) if case["one_tick_slippage"] else 0)
        if (fill["instrument_id"] != "AAPL.SIM" or fill["status"] != "FILLED" or fill["side"] != side
                or number(fill["quantity"]) != qty or number(fill["filled_qty"]) != qty
                or fill["ts_init"] != expected_ms or fill["ts_last"] != expected_ms
                or number(fill["avg_px"]) != price):
            raise ValueError("fill_schedule_or_price")
        commission = sum(number(f) for f in fill["commissions"])
        if any(not f.endswith(" USD") for f in fill["commissions"]) or commission != Decimal(case["commission_per_order_usd"]):
            raise ValueError("commission_mismatch")
        cash += (-qty * price if side == "BUY" else qty * price) - commission
        position += qty if side == "BUY" else -qty
        fees += commission
        account = accounts[index + 1]
        if account["currency"] != "USD" or number(account["total"]) != cash:
            raise ValueError("cash_transition")
        if position < 0 or position > qty:
            raise ValueError("position_limit")
    if position != 0 or any(p["side"] != "FLAT" or number(p["quantity"]) != 0 or p["ts_closed"] is None for p in positions):
        raise ValueError("position_not_flat")
    if any(not p["realized_pnl"].endswith(" USD") for p in positions):
        raise ValueError("pnl_currency")
    realized = sum(number(p["realized_pnl"]) for p in positions)
    if realized != cash - Decimal(plan["capital_usd"]):
        raise ValueError("realized_pnl")
    return {"fees_usd": str(fees), "ending_cash_usd": str(cash), "realized_pnl_usd": str(realized),
            "cash_ledger_reconciled": True, "cash_transitions_verified": len(fills),
            "realized_pnl_reconciled": True, "scheduled_fill_prices_verified": len(fills)}


def run_case(rows, plan, case, out):
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import FixedFeeModel, OneTickSlippageFillModel
    from nautilus_trader.model import AccountType, Bar, BarType, Currency, Equity, InstrumentId
    from nautilus_trader.model import Money, OmsType, OrderSide, Price, Quantity, Symbol, Venue
    from nautilus_trader.trading import Strategy

    usd, venue = Currency.from_str("USD"), Venue("SIM")
    equity = Equity(InstrumentId.from_str("AAPL.SIM"), Symbol("AAPL"), usd, 4,
                    Price.from_str("0.0100"), 0, 0, lot_size=Quantity.from_int(1))
    bar_type = BarType.from_str("AAPL.SIM-1-DAY-LAST-EXTERNAL")
    bars = []
    for row in rows:
        # Alpaca labels daily bars at exchange midnight. Publish our retrospective
        # complete bar at 16:00 New York; this is a declared diagnostic convention.
        close_time = datetime.combine(date.fromisoformat(row["session_date"]), time(16), ZoneInfo("America/New_York"))
        stamp = int(close_time.timestamp()) * 10**9
        bars.append(Bar(bar_type, *[Price.from_str(format(Decimal(row[k]), ".4f")) for k in ("o", "h", "l", "c")],
                        Quantity.from_int(int(Decimal(row["v"]))), stamp, stamp))

    class ScheduledRoundtrips(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.index = -1
            self.decisions = []

        def on_start(self):
            self.subscribe_bars(bar_type)

        def on_bar(self, bar):
            self.index += 1
            side = (OrderSide.BUY if self.index in plan["entry_indices"] else
                    OrderSide.SELL if self.index in plan["exit_indices"] else None)
            if side is not None:
                self.decisions.append({"bar_index": self.index, "ts_event": bar.ts_event, "side": str(side)})
                self.submit_order(self.order_factory.market(equity.id, side, Quantity.from_int(plan["quantity"])))

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    try:
        kwargs = {"fill_model": OneTickSlippageFillModel(1.0, 0.0, 42)} if case["one_tick_slippage"] else {}
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal(plan["capital_usd"]), usd)],
                         base_currency=usd, fee_model=FixedFeeModel(Money(Decimal(case["commission_per_order_usd"]), usd)),
                         liquidity_consumption=case["liquidity_consumption"], **kwargs)
        engine.add_instrument(equity)
        engine.add_data(bars)
        strategy = ScheduledRoundtrips()
        engine.add_strategy(strategy)
        engine.run()
        result = engine.get_result()
        reports = {"account": engine.generate_account_report(venue=venue),
                   "positions": engine.generate_positions_report(),
                   "fills": engine.generate_order_fills_report()}
        for name, report in reports.items():
            report.to_csv(out / (name + ".csv"))
        save(out / "decisions.json", strategy.decisions)
        fill_rows = json.loads(reports["fills"].to_json(orient="records"))
        position_rows = json.loads(reports["positions"].to_json(orient="records"))
        account_rows = json.loads(reports["account"].to_json(orient="records"))
        save(out / "reports.json", {"fills": fill_rows, "positions": position_rows, "account": account_rows})
        accounting = audit_reports(rows, plan, case, fill_rows, position_rows, account_rows)
        summary = {"id": case["id"], "processed_bars": result.iterations, "filled_orders": len(fill_rows),
                   "closed_positions": len(position_rows), **accounting,
                   "open_positions": len(engine.cache.positions_open()), "open_orders": len(engine.cache.orders_open()),
                   "reports": {name: {"rows": len(report), "sha256": digest(out / (name + ".csv"))} for name, report in reports.items()}}
        save(out / "summary.json", summary)
        if not (summary["processed_bars"] == len(rows) and summary["filled_orders"] == 10
                and summary["closed_positions"] == 5 and not summary["open_positions"] and not summary["open_orders"]
                and summary["cash_ledger_reconciled"] and summary["realized_pnl_reconciled"]
                and Decimal(summary["fees_usd"]) == Decimal(case["commission_per_order_usd"]) * 10):
            raise ValueError("native_acceptance_failed")
        return summary
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="Retained authenticated Alpaca acquisition")
    parser.add_argument("--out", type=Path, required=True, help="Fresh private directory")
    args = parser.parse_args()
    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("native_version_mismatch")
    os.umask(0o077)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    plan = json.loads((SOURCE / "plan.json").read_text())
    save(args.out / "plan.json", plan)
    rows = load_rows(args.run, plan)
    save(args.out / "input.private.json", rows)
    results = []
    for case in plan["cases"]:
        case_out = args.out / case["id"]
        case_out.mkdir()
        results.append(run_case(rows, plan, case, case_out))
    summary = {"classification": "local integration with retained historical market data", "results": results,
               "engine_version": importlib.metadata.version("nautilus_trader"),
               "input_receipt_sha256": plan["alpaca_receipt_sha256"], "plan_sha256": digest(SOURCE / "plan.json"),
               "runner_sha256": digest(__file__), "retained_rows_sha256": digest(args.out / "input.private.json"),
               "network_interfaces": socket.if_nameindex(), "environment_names": sorted(os.environ),
               "completed_utc": datetime.now(timezone.utc).isoformat()}
    save(args.out / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
