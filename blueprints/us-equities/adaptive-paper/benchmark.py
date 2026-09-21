"""Wall-clock native capacity fixture. Zero Alpaca connections or paper orders.

Forced alternating intents measure the engineering path only. They are not the
adaptive policy, market signals, a historical backtest, or a profitability test.
"""
from __future__ import annotations
import argparse
import asyncio
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
import tempfile
import time

from nautilus_trader.trading import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import ClientOrderId, InstrumentId, OrderSide, Price, Quantity, StrategyId, TimeInForce
from native_adapter import build_node
from runner import Controller, reconcile, save
from safety import Ledger, RiskLimits
from simulation import SimulatedPort


class CapacityProbe(Strategy):
    def __new__(cls, ledger, target):
        return super().__new__(cls, StrategyConfig(strategy_id=StrategyId("CAPACITY-001"),
                                order_id_tag="C", log_events=False, log_commands=False))

    def __init__(self, ledger, target):
        self.ledger, self.target = ledger, target
        self.pending = False
        self.submitted = self.fills = 0
        self.last_submit = 0
        self.errors = []
        self.native_flat = False

    def on_start(self):
        self.subscribe_quotes(InstrumentId.from_str("SPY.ALPACA"))

    def on_quote(self, quote):
        now = time.monotonic()
        if self.pending or self.submitted >= self.target or now - self.last_submit < 1 / 3:
            return
        held = self.ledger.positions().get("SPY")
        side = OrderSide.SELL if held and held.qty else OrderSide.BUY
        self.submitted += 1
        self.pending = True
        self.last_submit = now
        order = self.order_factory.limit(quote.instrument_id, side, Quantity.from_int(1),
                    Price.from_str("100.03" if side == OrderSide.BUY else "99.97"),
                    time_in_force=TimeInForce.DAY,
                    client_order_id=ClientOrderId(f"capacity-{self.submitted:06d}"),
                    tags=["reason=synthetic_capacity_fixture"])
        self.submit_order(order)

    def on_order_filled(self, event):
        self.fills += 1
        self.pending = False
        if self.fills == self.target:
            self.native_flat = self.portfolio.is_net_flat(event.instrument_id)
            self.shutdown_system("capacity fixture complete")

    def on_order_rejected(self, event):
        self.errors.append("native_rejection")
        self.shutdown_system("capacity fixture rejected")

    def on_order_denied(self, event):
        self.errors.append("native_denial")
        self.shutdown_system("capacity fixture denied")


async def benchmark(target=180):
    if target <= 0 or target > 180 or target % 2:
        raise ValueError("bounded_even_target_required")
    with tempfile.TemporaryDirectory() as root:
        ledger = Ledger(Path(root) / "ledger.sqlite3", RiskLimits(trial_seconds=70, cleanup_seconds=5))
        ledger.start_trial(time.time())
        controller = Controller(ledger, time.time() + 3600, market_open=True)
        port = SimulatedPort(controller, ["SPY"], interval=.005)
        controller.port = port
        strategy = CapacityProbe(ledger, target)
        session = build_node(port, [{"symbol": "SPY"}], [strategy], max_order_submit_rate="180/00:01:00")
        start = time.monotonic()
        try:
            await asyncio.wait_for(session.run_async(), 75)
            snapshot = await port.snapshot()
            verification = reconcile(ledger, snapshot, "100000")
            elapsed = time.monotonic() - start
            times = port.submitted_at
            peak = max((sum(t <= x < t + 60 for x in times) for t in times), default=0)
            result = {"kind": "local_native_synthetic_capacity", "broker_connections": 0, "paper_orders": 0,
                      "engine": "NautilusTrader LiveNode 2.0.0rc5", "target_submit_ceiling_per_minute": 180,
                      "synthetic_submissions": len(times), "native_fill_events": strategy.fills,
                      "completed_synthetic_roundtrips": strategy.fills // 2,
                      "elapsed_seconds": elapsed, "peak_submissions_in_60_seconds": peak,
                      "average_submissions_per_minute": len(times) / elapsed * 60,
                      "native_portfolio_flat": strategy.native_flat, "reconciliation": verification,
                      "accounting": asdict(ledger.accounting()), "adapter_errors": session.errors,
                      "strategy_errors": strategy.errors, "requests_reserved": len(controller.requests),
                      "limitations": ["Immediate synthetic fills; zero fees; no broker/network latency or liquidity effects.",
                                      "Forced alternating intents; not adaptive strategy performance or paper acceptance."]}
            result["status"] = "passed" if (strategy.fills == target and strategy.native_flat
                and not session.errors and not strategy.errors and verification["open_orders"] == 0
                and verification["positions"] == 0 and peak <= 180) else "failed"
            return result
        finally:
            session.stop()
            await port.stop()
            ledger.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=int, default=180)
    args = parser.parse_args()
    result = asyncio.run(benchmark(args.target))
    save(args.output, result)
    print({k: result[k] for k in ("status", "synthetic_submissions", "native_fill_events", "elapsed_seconds")})
    raise SystemExit(0 if result["status"] == "passed" else 1)
