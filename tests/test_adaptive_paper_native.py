"""Local real-LiveNode integration with fake transport; never broker acceptance."""
import asyncio
import importlib.util
from pathlib import Path
import time
import unittest

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.model import InstrumentId, OrderSide, Quantity, TimeInForce
    from nautilus_trader.trading import Strategy
    PATH = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper/native_adapter.py"
    SPEC = importlib.util.spec_from_file_location("adaptive_native", PATH)
    ADAPTER = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(ADAPTER)


class FakePort:
    def __init__(self, mode="fills"):
        self.mode, self.started, self.stopped = mode, 0, 0
        self.submissions, self.events = [], []
        self.qty, self.cash = 0, 10000
        self.active = {}

    async def start(self, on_quote, on_order):
        self.started += 1
        self.on_quote, self.on_order = on_quote, on_order
        on_quote({"symbol": "SPY", "bid": "100.00", "ask": "100.01", "bid_size": "100",
                  "ask_size": "100", "ts_ns": time.time_ns()})

    async def stop(self):
        self.stopped += 1

    async def snapshot(self):
        return {"account": {"cash": str(self.cash), "buying_power": str(self.cash), "equity": "10000"},
                "orders": list(self.active.values()), "positions": [] if self.qty == 0 else
                [{"symbol": "SPY", "qty": str(self.qty), "avg_entry_price": "100.01"}]}

    async def submit(self, payload):
        self.submissions.append(payload)
        if self.mode == "unknown":
            raise TimeoutError("accepted may have happened")
        if self.mode == "denied":
            raise ADAPTER.NativeOrderRejected("risk_budget_exhausted")
        order = {**payload, "id": "paper-" + str(len(self.submissions)), "filled_qty": "0",
                 "filled_avg_price": None, "status": "new", "updated_at_ns": time.time_ns()}
        self.active[payload["client_order_id"]] = order
        self.on_order(dict(order))
        if self.mode == "fractional":
            order.update(filled_qty="0.5", filled_avg_price=payload["limit_price"],
                         status="partially_filled", updated_at_ns=time.time_ns())
            self.qty = 0.5
            self.on_order(dict(order))
            return dict(order)
        if self.mode == "cancel":
            return order
        qty = int(payload["qty"])
        for filled in range(1, qty + 1):
            order.update(filled_qty=str(filled), filled_avg_price=payload["limit_price"],
                         status="filled" if filled == qty else "partially_filled", updated_at_ns=time.time_ns())
            self.qty += 1 if payload["side"] == "buy" else -1
            self.cash += -float(payload["limit_price"]) if payload["side"] == "buy" else float(payload["limit_price"])
            self.on_order(dict(order))
            self.on_order(dict(order))  # repeated wire delivery must not duplicate native fills
        self.active.pop(payload["client_order_id"])
        return dict(order)  # REST confirmation repeats the last stream state

    async def cancel(self, cid):
        order = self.active.pop(cid)
        order = dict(order, status="canceled", updated_at_ns=time.time_ns())
        self.on_order(order)
        return order


if NATIVE:
    class Roundtrip(Strategy):
        def __init__(self, mode="fills"):
            super().__init__(StrategyConfig(log_events=False, log_commands=False))
            self.mode = mode
            self.order = None
            self.buy_qty = self.sell_qty = 0
            self.fill_events = 0
            self.accepted = self.canceled = self.rejected = 0
            self.flat_seen = False

        def on_start(self):
            self.subscribe_quotes(InstrumentId.from_str("SPY.ALPACA"))

        def on_quote(self, tick):
            if self.order is None:
                self.order = self.order_factory.limit(tick.instrument_id, OrderSide.BUY, Quantity.from_int(2),
                    tick.ask_price, time_in_force=TimeInForce.DAY, tags=["reason=test", "family=momentum"])
                self.submit_order(self.order)

        def on_order_accepted(self, event):
            self.accepted += 1
            if self.mode == "cancel":
                self.cancel_order(self.order.client_order_id)

        def on_order_filled(self, event):
            self.fill_events += 1
            if event.order_side == OrderSide.BUY:
                self.buy_qty += int(str(event.last_qty))
                if self.buy_qty == 2:
                    self.submit_order(self.order_factory.limit(event.instrument_id, OrderSide.SELL,
                        Quantity.from_int(2), event.last_px, time_in_force=TimeInForce.DAY))
            else:
                self.sell_qty += int(str(event.last_qty))
                if self.sell_qty == 2:
                    self.flat_seen = self.portfolio.is_net_flat(event.instrument_id)
                    self.shutdown_system("test roundtrip flat")

        def on_order_canceled(self, event):
            self.canceled += 1
            self.shutdown_system("test canceled")

        def on_order_rejected(self, event):
            self.rejected += 1
            self.shutdown_system("test rejected")


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class NativeIntegration(unittest.TestCase):
    def run_node(self, mode):
        port, strategy = FakePort(mode), Roundtrip(mode)
        session = ADAPTER.build_node(port, [{"symbol": "SPY", "currency": "USD"}], [strategy])
        async def exercise():
            await asyncio.wait_for(session.run_async(), timeout=8)
        asyncio.run(exercise())
        return port, strategy, session

    def test_real_native_roundtrip_partial_and_duplicate_events(self):
        port, strategy, session = self.run_node("fills")
        self.assertEqual(session.errors, [])
        self.assertEqual((port.started, port.stopped), (1, 1))
        self.assertEqual(len(port.submissions), 2)
        self.assertEqual((strategy.buy_qty, strategy.sell_qty, strategy.fill_events), (2, 2, 4))
        self.assertTrue(strategy.flat_seen)
        self.assertEqual(port.qty, 0)
        self.assertEqual(port.active, {})
        self.assertEqual(port.submissions[0]["reason"], "test")
        self.assertIn("family=momentum", port.submissions[0]["tags"])

    def test_real_native_cancel_confirmation_deduplicated(self):
        port, strategy, session = self.run_node("cancel")
        self.assertEqual(session.errors, [])
        self.assertEqual(strategy.canceled, 1)
        self.assertEqual(strategy.fill_events, 0)
        self.assertEqual(port.active, {})

    def test_definitive_risk_refusal_produces_native_rejection(self):
        port, strategy, session = self.run_node("denied")
        self.assertEqual(session.errors, [])
        self.assertEqual(strategy.rejected, 1)
        self.assertEqual(strategy.accepted, 0)
        self.assertEqual(strategy.fill_events, 0)

    def test_ambiguous_submit_stops_without_fake_rejection_or_retry(self):
        port, strategy, session = self.run_node("unknown")
        self.assertTrue(any(e.startswith("unknown_submit:") for e in session.errors))
        self.assertEqual(len(port.submissions), 1)
        self.assertEqual(strategy.rejected, 0)
        self.assertEqual(strategy.accepted, 0)
        self.assertEqual(strategy.fill_events, 0)
        self.assertEqual(port.stopped, 1)

    def test_fractional_broker_fill_freezes_and_retains_actual_residual(self):
        port, strategy, session = self.run_node("fractional")
        self.assertTrue(any("fractional_shares_unsupported" in e for e in session.errors))
        self.assertEqual(port.qty, 0.5)
        self.assertEqual(strategy.fill_events, 0)
        self.assertFalse(strategy.flat_seen)
        self.assertEqual(len(session.unresolved_orders), 1)
        self.assertEqual(next(iter(session.unresolved_orders.values()))["filled_qty"], "0.5")
        self.assertEqual(len(port.submissions), 1)

    def test_startup_refuses_preexisting_orders_or_positions(self):
        for snapshot in (
            {"positions": [{"symbol": "SPY", "qty": "0.5"}], "orders": []},
            {"positions": [], "orders": [{"status": "new"}]},
        ):
            port = FakePort()
            async def dirty_snapshot():
                return {**snapshot, "account": {"cash": "10000", "equity": "10000", "buying_power": "10000"}}
            port.snapshot = dirty_snapshot
            session = ADAPTER.build_node(port, [{"symbol": "SPY"}], [])
            try:
                with self.assertRaisesRegex(ValueError, "startup_requires"):
                    asyncio.run(session.execution._connect())
            finally:
                session.node.dispose()
            self.assertEqual(port.submissions, [])

    def test_native_equity_model_does_not_claim_fractional_precision(self):
        ins = ADAPTER.instrument({"symbol": "SPY", "lot_size": "1"})
        self.assertEqual(ins.size_precision, 0)
        with self.assertRaisesRegex(ValueError, "fractional_shares_unsupported"):
            ADAPTER.shares("0.5")


if __name__ == "__main__":
    unittest.main()
