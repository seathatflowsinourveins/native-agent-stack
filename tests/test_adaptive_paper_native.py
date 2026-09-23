"""Local real-LiveNode integration with fake transport; never broker acceptance."""
import asyncio
from decimal import Decimal
import importlib.util
from pathlib import Path
import tempfile
import time
import uuid
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
        self.quote_bid, self.quote_ask = "100.00", "100.01"

    async def start(self, on_quote, on_order):
        self.started += 1
        self.on_quote, self.on_order = on_quote, on_order
        on_quote({"symbol": "SPY", "bid": self.quote_bid, "ask": self.quote_ask, "bid_size": "100",
                  "ask_size": "100", "ts_ns": time.time_ns()})

    async def stop(self):
        self.stopped += 1

    async def snapshot(self):
        if not self.started:
            raise RuntimeError("snapshot_requires_bound_owner_loop")
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
    class QuoteCapture(Strategy):
        def __init__(self):
            self.received = []

        def on_start(self):
            self.subscribe_quotes(InstrumentId.from_str("SPY.ALPACA"))

        def on_quote(self, tick):
            self.received.append(tick)
            self.shutdown_system("test quote preserved")

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
    def test_native_quote_precision_preserves_normalized_and_subpenny_values(self):
        for bid, ask, precision in (("650.1", "650.12", 2), ("650.10", "650.12", 2),
                                    ("650.1234", "650.13", 4), ("0.1234", "0.1235", 4),
                                    ("0.1234567890123456", "0.123456789012346", 16)):
            with self.subTest(bid=bid, ask=ask):
                port, strategy = FakePort(), QuoteCapture()
                port.quote_bid, port.quote_ask = bid, ask
                session = ADAPTER.build_node(port, [{"symbol": "SPY"}], [strategy])
                async def exercise():
                    await asyncio.wait_for(session.run_async(), timeout=3)
                asyncio.run(exercise())
                self.assertEqual(session.errors, [])
                self.assertEqual(len(strategy.received), 1)
                quote = strategy.received[0]
                self.assertEqual((quote.bid_price.precision, quote.ask_price.precision), (precision, precision))
                self.assertEqual(Decimal(str(quote.bid_price)), Decimal(bid))
                self.assertEqual(Decimal(str(quote.ask_price)), Decimal(ask))
                self.assertEqual(port.submissions, [])

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

    def test_uuid_broker_ids_fill_without_trade_id_overflow(self):
        # Real Alpaca order ids are 36-character UUIDs; the old "<id>:cum:<qty>" TradeId was 42.
        original = FakePort.submit
        async def uuid_submit(port, payload):
            port.submissions.append(payload)
            order = {**payload, "id": str(uuid.uuid4()), "filled_qty": "0", "filled_avg_price": None,
                     "status": "new", "updated_at_ns": time.time_ns()}
            port.active[payload["client_order_id"]] = order
            port.on_order(dict(order))
            order.update(filled_qty=payload["qty"], filled_avg_price=payload["limit_price"], status="filled",
                         updated_at_ns=time.time_ns())
            port.qty += int(payload["qty"]) if payload["side"] == "buy" else -int(payload["qty"])
            port.on_order(dict(order))
            port.active.pop(payload["client_order_id"])
            return dict(order)
        FakePort.submit = uuid_submit
        try:
            port, strategy, session = self.run_node("fills")
        finally:
            FakePort.submit = original
        self.assertEqual(session.errors, [])
        self.assertTrue(strategy.flat_seen)
        self.assertEqual(port.qty, 0)
        broker_id = str(uuid.uuid4())
        first = ADAPTER.fill_trade_id(broker_id, Decimal("1"))
        self.assertEqual(len(str(first)), 36)
        self.assertEqual(first, ADAPTER.fill_trade_id(broker_id, Decimal("1")))
        self.assertNotEqual(first, ADAPTER.fill_trade_id(broker_id, Decimal("2")))

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
                self.assertEqual(port.started, 1, "execution must bind the port before its first REST snapshot")
                return {**snapshot, "account": {"cash": "10000", "equity": "10000", "buying_power": "10000"}}
            port.snapshot = dirty_snapshot
            session = ADAPTER.build_node(port, [{"symbol": "SPY"}], [])
            try:
                with self.assertRaisesRegex(ValueError, "startup_requires"):
                    asyncio.run(session.execution._connect())
            finally:
                asyncio.run(session.stop_port())
                session.node.dispose()
            self.assertEqual(port.submissions, [])

    def test_native_equity_model_does_not_claim_fractional_precision(self):
        ins = ADAPTER.instrument({"symbol": "SPY", "lot_size": "1"})
        self.assertEqual(ins.size_precision, 0)
        with self.assertRaisesRegex(ValueError, "fractional_shares_unsupported"):
            ADAPTER.shares("0.5")


if NATIVE:
    ENGINE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
    import sys as _sys
    if str(ENGINE) not in _sys.path:
        _sys.path.insert(0, str(ENGINE))
    from native_strategy import AdaptiveStrategy
    from strategies import AdaptivePolicy, PolicyConfig
    from safety import Ledger, RiskLimits, Quote, DEFAULT_STOP
    import leverage as lev

    class _LeverageFixtureStrategy(AdaptiveStrategy):
        """positions() needs a live nautilus cache/trader wiring this test
        never sets up (no LiveNode is started); override with a plain dict
        so the rest of AdaptiveStrategy's own (non-nautilus) logic --
        _leverage_inputs, rebalance()'s decide()/event_sink wiring -- can be
        exercised directly and cheaply. Defined at module level (not nested
        inside LeverageStrategyTests) so this module still imports cleanly
        without nautilus_trader installed -- a class body referencing
        AdaptiveStrategy would otherwise raise NameError at import time,
        before @unittest.skipUnless ever gets a chance to skip anything."""
        def __init__(self, *a, held=None, **kw):
            super().__init__(*a, **kw)
            self._held = held or {}

        def positions(self):
            return self._held


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class LeverageStrategyTests(unittest.TestCase):
    """G-e E5: AdaptiveStrategy._leverage_inputs / rebalance() leverage-inputs
    wiring, and the decision event's opt-in "leverage_ceiling" key."""

    RTH_NOW = 1772550000.0  # 2026-03-03 15:00 UTC = 10:00 ET (RTH), 2026 calendar

    def leverage_policy(self, max_leverage="4"):
        config = {"max_leverage": max_leverage, "capital_usd": "10000",
                 "max_gross_exposure_usd": str(10000 * int(max_leverage)), "leverage_policy": lev.CANONICAL_V1_BLOCK}
        session_policy = {"overnight_holds": False, "overnight_gross_multiple": Decimal("1.0")}
        return lev.validate_leverage_policy(config, session_policy)

    def make_ledger(self, leverage_policy=None, tmp=None):
        limits = RiskLimits(capital_usd=Decimal("10000"),
                            max_gross_exposure_usd=Decimal("40000") if leverage_policy else Decimal("5000"),
                            leverage=leverage_policy)
        ledger = Ledger(Path(tmp) / "lev.sqlite3", limits)
        ledger.start_trial(self.RTH_NOW)
        return ledger

    def make_strategy(self, *, with_policy, tmp, held=None, account_multiplier=None):
        leverage_policy = self.leverage_policy() if with_policy else None
        ledger = self.make_ledger(leverage_policy, tmp)
        config = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                              capital=10000, gross_cap=40000 if with_policy else 5000,
                              max_leverage=4.0 if with_policy else 1.0,
                              leverage_policy_id=lev.LEVERAGE_POLICY_VERSION if with_policy else None)
        policy = AdaptivePolicy(config, leverage_policy=leverage_policy)
        events = []
        strategy = _LeverageFixtureStrategy(policy, ledger, "t1", event_sink=events.append,
                                            account_multiplier=account_multiplier, held=held,
                                            clock=lambda: self.RTH_NOW)
        strategy.started = True
        strategy.enabled = True
        return strategy, ledger, events

    def test_leverage_inputs_reports_rth_session_and_zero_drawdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            strategy, ledger, _ = self.make_strategy(with_policy=True, tmp=tmp)
            inputs = strategy._leverage_inputs(self.RTH_NOW)
            self.assertEqual(inputs.session, "RTH")
            self.assertEqual(inputs.drawdown_fraction, Decimal("0"))
            self.assertFalse(inputs.kill_switch)
            ledger.close()

    def test_leverage_inputs_kill_switch_from_stop_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            strategy, ledger, _ = self.make_strategy(with_policy=True, tmp=tmp)
            stop = Path(tmp) / "STOP"
            stop.write_text("halt")
            strategy.stop_file = stop
            self.assertTrue(strategy._leverage_inputs(self.RTH_NOW).kill_switch)
            ledger.close()

    def test_leverage_inputs_kill_switch_from_halted_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            strategy, ledger, _ = self.make_strategy(with_policy=True, tmp=tmp)
            ledger.freeze("manual_halt_for_test")
            self.assertTrue(strategy._leverage_inputs(self.RTH_NOW).kill_switch)
            ledger.close()

    def test_leverage_inputs_carries_account_multiplier(self):
        with tempfile.TemporaryDirectory() as tmp:
            strategy, ledger, _ = self.make_strategy(with_policy=True, tmp=tmp, account_multiplier=Decimal("2"))
            self.assertEqual(strategy._leverage_inputs(self.RTH_NOW).account_multiplier, Decimal("2"))
            ledger.close()

    def test_rebalance_decision_event_has_no_leverage_key_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            strategy, ledger, events = self.make_strategy(with_policy=False, tmp=tmp)
            strategy.rebalance(self.RTH_NOW)
            decision_events = [e for e in events if e.get("type") == "decision"]
            self.assertTrue(decision_events)
            self.assertNotIn("leverage_ceiling", decision_events[-1])
            ledger.close()

    def test_rebalance_decision_event_has_leverage_ceiling_under_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            strategy, ledger, events = self.make_strategy(with_policy=True, tmp=tmp)
            strategy.rebalance(self.RTH_NOW)
            decision_events = [e for e in events if e.get("type") == "decision"]
            self.assertTrue(decision_events)
            self.assertIn("leverage_ceiling", decision_events[-1])
            ledger.close()

    def test_stop_file_gives_decided_ceiling_of_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            strategy, ledger, events = self.make_strategy(with_policy=True, tmp=tmp)
            stop = Path(tmp) / "STOP"
            stop.write_text("halt")
            strategy.stop_file = stop
            strategy.rebalance(self.RTH_NOW)
            decision_events = [e for e in events if e.get("type") == "decision"]
            self.assertEqual(decision_events[-1]["leverage_ceiling"], 0.0)
            ledger.close()


if __name__ == "__main__":
    unittest.main()
