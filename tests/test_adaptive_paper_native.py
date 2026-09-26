"""Local real-LiveNode integration with fake transport; never broker acceptance.

Evidence class: synthetic fixture (a scripted port in the documented trade_updates and
FILL-activity schemas) driving the real NautilusTrader 2.0.0rc5 LiveNode."""
import ast
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
    from nautilus_trader.model import ClientOrderId, InstrumentId, OrderSide, Price, Quantity, TimeInForce
    from nautilus_trader.trading import Strategy
    PATH = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper/native_adapter.py"
    SPEC = importlib.util.spec_from_file_location("adaptive_native", PATH)
    ADAPTER = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(ADAPTER)
    import transport as TRANSPORT  # the adapter module put the engine directory on sys.path

try:  # package mode (python -m unittest tests.x) or discover -s tests (top-level modules)
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    _HERMETIC_TOKEN = patch_default_stop()


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


def execution(order, qty, price):
    """A stream fill row as transport.py forwards a trade_updates fill or partial_fill:
    the order's cumulative state plus this one execution's id, qty and price."""
    status = order["status"]
    return dict(order, event="fill" if status == "filled" else "partial_fill", execution_id=str(uuid.uuid4()),
                event_qty=str(qty), event_price=str(price))


class FakePort:
    def __init__(self, mode="fills"):
        self.mode, self.started, self.stopped = mode, 0, 0
        self.submissions, self.events = [], []
        self.qty, self.cash = 0, 10000
        self.active = {}
        self.quote_bid, self.quote_ask = "100.00", "100.01"
        self.activity_reads = []

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
            fill = execution(order, 1, payload["limit_price"])
            self.on_order(dict(fill))
            self.on_order(dict(fill))  # repeated wire delivery must not duplicate native fills
        self.active.pop(payload["client_order_id"])
        return dict(order)  # REST confirmation repeats the last stream state

    async def cancel(self, cid):
        order = self.active.pop(cid)
        order = dict(order, status="canceled", updated_at_ns=time.time_ns())
        self.on_order(order)
        return order

    async def fill_activities(self, order_id):
        self.activity_reads.append(order_id)
        return []


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
            self.trade_ids = []
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
            self.trade_ids.append(str(event.trade_id))
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

    def test_activity_recovery_persists_through_transport_observation_hook(self):
        """Use AlpacaPaperTransport's callback shape, without SimulatedPort.controller."""
        from runner import Controller
        from safety import Ledger, RiskLimits

        class MissingStreamPort(FakePort):
            def __init__(self, *, before_submit, sink_quote, sink_observation):
                super().__init__()
                self.before_submit = before_submit
                self.sink_quote, self.sink_observation = sink_quote, sink_observation
                self.ready = True

            async def start(self, on_quote, on_order):
                def quote(row):
                    self.sink_quote(row)
                    on_quote(row)
                await super().start(quote, on_order)

            async def submit(self, payload):
                self.before_submit(payload)
                self.submissions.append(payload)
                stamp = time.time_ns()
                row = dict(payload, id="paper-buy", status="partially_filled", filled_qty="1",
                           filled_avg_price="100.01", updated_at_ns=stamp)
                self.sink_observation(row)
                self.activities = [
                    {"trade_id": str(uuid.uuid4()), "qty": "1", "price": price,
                     "cum_qty": str(cum), "symbol": "SPY", "side": "buy",
                     "transaction_time_ns": stamp + cum}
                    for cum, price in enumerate(("100.01", "100.01", "100.00"), 1)]
                return row

            async def fill_activities(self, order_id):
                self.activity_reads.append(order_id)
                return self.activities

        class RecoveryWatcher(Strategy):
            def __new__(cls, ledger):
                return super().__new__(cls, StrategyConfig(log_events=False, log_commands=False))

            def __init__(self, ledger):
                self.ledger, self.order = ledger, None
                self.filled = Decimal(0)
                self.durable_at_callback = []

            def on_start(self):
                self.subscribe_quotes(InstrumentId.from_str("SPY.ALPACA"))

            def on_quote(self, tick):
                if self.order is None:
                    self.order = self.order_factory.limit(tick.instrument_id, OrderSide.BUY,
                        Quantity.from_int(3), tick.ask_price, time_in_force=TimeInForce.DAY)
                    self.submit_order(self.order)

            def on_order_filled(self, event):
                self.filled += Decimal(str(event.last_qty))
                intent = self.ledger.intents()[0]
                self.durable_at_callback.append((intent.filled_qty, intent.status,
                    len(self.ledger.unresolved()), self.ledger.positions()["SPY"].cost_basis_usd))
                if self.filled == 3:
                    self.shutdown_system("activity recovery complete")

        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "ledger.db"
            limits = RiskLimits(max_order_qty=Decimal(3))
            ledger = Ledger(path, limits)
            self.addCleanup(ledger.close)
            now = time.time()
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True)
            port = MissingStreamPort(before_submit=controller.before_submit,
                                     sink_quote=controller.quote, sink_observation=controller.observe)
            controller.port = port
            self.assertFalse(hasattr(port, "controller"))
            watcher = RecoveryWatcher(ledger)
            session = ADAPTER.build_node(port, [{"symbol": "SPY"}], [watcher])
            session.fill_gap_grace_seconds = .01

            async def exercise():
                await asyncio.wait_for(session.run_async(), timeout=5)

            asyncio.run(exercise())
            self.assertEqual(session.errors, [])
            self.assertEqual(port.activity_reads, ["paper-buy"])
            self.assertEqual(watcher.filled, Decimal(3))
            self.assertEqual(ledger.intents()[0].filled_qty, watcher.filled)
            self.assertEqual(watcher.durable_at_callback,
                             [(Decimal(3), "filled", 0, Decimal("300.02"))] * 3)
            self.assertEqual(ledger.accounting().cash_delta_usd, Decimal("-300.02"))
            ledger.close()
            reopened = Ledger(path, limits)
            self.addCleanup(reopened.close)
            self.assertEqual(reopened.intents()[0].filled_qty, Decimal(3))
            self.assertEqual(reopened.positions()["SPY"].cost_basis_usd, Decimal("300.02"))
            self.assertEqual(reopened.accounting().cash_delta_usd, Decimal("-300.02"))
            self.assertEqual(reopened.unresolved(), [])

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
        # Real Alpaca order and execution ids are 36-character UUIDs, NautilusTrader's TradeId limit.
        original = FakePort.submit
        executions = []
        async def uuid_submit(port, payload):
            port.submissions.append(payload)
            order = {**payload, "id": str(uuid.uuid4()), "filled_qty": "0", "filled_avg_price": None,
                     "status": "new", "updated_at_ns": time.time_ns()}
            port.active[payload["client_order_id"]] = order
            port.on_order(dict(order))
            order.update(filled_qty=payload["qty"], filled_avg_price=payload["limit_price"], status="filled",
                         updated_at_ns=time.time_ns())
            port.qty += int(payload["qty"]) if payload["side"] == "buy" else -int(payload["qty"])
            fill = execution(order, payload["qty"], payload["limit_price"])
            executions.append(fill["execution_id"])
            port.on_order(fill)
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
        self.assertEqual(strategy.trade_ids, executions)       # TradeId is the execution id itself
        self.assertEqual(session.execution_stats["executions_booked"], 2)
        self.assertEqual(str(ADAPTER.execution_trade_id(executions[0])), executions[0])
        long_id = "x" * 80
        self.assertEqual(len(str(ADAPTER.execution_trade_id(long_id))), 36)
        self.assertEqual(ADAPTER.execution_trade_id(long_id), ADAPTER.execution_trade_id(long_id))
        self.assertNotEqual(ADAPTER.execution_trade_id(long_id), ADAPTER.execution_trade_id(long_id + "y"))

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


# The 2026-09-24 APUS sell as the native evidence records it: (qty, price, the
# cumulative average Alpaca reported after that execution). The old cumulative-average
# booking derived 5.610004 for the second execution and froze the adapter.
APUS_EXECUTIONS = (("26", "5.62", "5.62"), ("2", "5.61", "5.619286"), ("1", "5.61", "5.618966"))


def fill_activity(order_id, cum, qty, price, *, side="sell", symbol="APUS", total=29, index=0):
    """One TradeActivity row in the documented schema (activity_type FILL); its id is
    "<timestamp>::<uuid>" with a UUID unrelated to any stream execution_id."""
    leaves = total - int(cum)
    return {"activity_type": "FILL", "id": "20260924150021%03d::%s" % (index, uuid.uuid4()), "cum_qty": str(cum),
            "leaves_qty": str(leaves), "order_id": order_id, "order_status": "filled" if not leaves else "partially_filled",
            "price": price, "qty": str(qty), "side": side, "symbol": symbol,
            "transaction_time": "2026-09-24T15:00:21.%06dZ" % (320056 + index), "type": "fill" if not leaves else "partial_fill"}


def apus_activities(order_id):
    cum, rows = 0, []
    for index, (qty, price, _) in enumerate(APUS_EXECUTIONS):
        cum += int(qty)
        rows.append(fill_activity(order_id, cum, qty, price, index=index))
    return rows


def apus_stream_rows(order, *, execution_fields=True, averages=None):
    """The three APUS executions as trade_updates rows (order cumulative state after each)."""
    rows, cum = [], 0
    for index, (qty, price, average) in enumerate(APUS_EXECUTIONS):
        cum += int(qty)
        state = dict(order, filled_qty=str(cum), filled_avg_price=(averages or {}).get(index, average),
                     status="filled" if cum == 29 else "partially_filled", updated_at_ns=time.time_ns() + index)
        row = dict(state, event="fill" if cum == 29 else "partial_fill")
        if execution_fields:
            row.update(execution_id=str(uuid.uuid4()), event_qty=qty, event_price=price)
        rows.append(row)
    return rows


class ScriptedPort:
    """One symbol. The buy fills in one execution at the ask; the sell's stream rows, the
    cancel's REST answer and rows after it, and the FILL activities follow the test's
    script. Stream rows are delivered after the REST answer, as on the wire."""

    def __init__(self, *, symbol="APUS", bid="5.61", ask="5.62", sell_rows=None, cancel=None, activities=None,
                 snapshot_orders=(), snapshot_positions=(), after_sell_rows=None, activity_delay=0.0,
                 during_activity_read=()):
        self.symbol, self.bid, self.ask = symbol, bid, ask
        self.sell_rows, self.cancel_script, self.activities = sell_rows, cancel, activities
        self.snapshot_orders, self.snapshot_positions = list(snapshot_orders), list(snapshot_positions)
        self.orders, self.tasks, self.activity_reads, self.cancels = {}, [], [], []
        self.started = self.stopped = 0
        # Test hooks: called once the sell's scripted rows are delivered; an activities read
        # that takes activity_delay seconds and delivers during_activity_read(order) rows
        # (e.g. a REST row that got ahead) while it is in flight.
        self.after_sell_rows, self.activity_delay = after_sell_rows, activity_delay
        self.during_activity_read = during_activity_read

    async def start(self, on_quote, on_order):
        self.started += 1
        self.on_quote, self.on_order = on_quote, on_order
        on_quote({"symbol": self.symbol, "bid": self.bid, "ask": self.ask, "bid_size": "100", "ask_size": "100",
                  "ts_ns": time.time_ns()})

    async def stop(self):
        self.stopped += 1
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def snapshot(self):
        return {"account": {"cash": "10000", "buying_power": "10000", "equity": "10000"},
                "orders": list(self.snapshot_orders), "positions": list(self.snapshot_positions)}

    def deliver(self, rows, delay=0.0):
        """Deliver stream rows of an adopted order from inside the running node."""
        self.later(rows, delay)

    def later(self, rows, delay=0.0, then=None):
        """Deliver ``rows`` in order after ``delay``; a number among them is a pause (s)."""
        async def emit():
            await asyncio.sleep(delay)
            for row in rows:
                if isinstance(row, (int, float)):
                    await asyncio.sleep(row)
                    continue
                self.on_order(dict(row))
                await asyncio.sleep(0)
            if then is not None:
                then()
        self.tasks.append(asyncio.get_running_loop().create_task(emit()))

    async def submit(self, payload):
        order = {**payload, "id": str(uuid.uuid4()), "filled_qty": "0", "filled_avg_price": None, "status": "new",
                 "updated_at_ns": time.time_ns()}
        self.orders[payload["client_order_id"]] = order
        if payload["side"] == "buy":
            filled = dict(order, filled_qty=payload["qty"], filled_avg_price=self.ask, status="filled",
                          updated_at_ns=time.time_ns())
            self.later([dict(order), execution(filled, payload["qty"], self.ask)])
        else:
            self.later([dict(order)] + list(self.sell_rows(order) if self.sell_rows else []),
                       then=self.after_sell_rows)
        return dict(order)

    async def cancel(self, cid):
        self.cancels.append(cid)
        rest, later = self.cancel_script(self.orders[cid])
        self.later(later, delay=0.05)
        return rest

    async def fill_activities(self, order_id):
        self.activity_reads.append(order_id)
        rows = self.activities(order_id) if self.activities else []
        order = next((o for o in self.orders.values() if o["id"] == order_id), None)
        for row in (self.during_activity_read(order) if callable(self.during_activity_read) else ()):
            self.on_order(dict(row))
        if self.activity_delay:
            await asyncio.sleep(self.activity_delay)
        return TRANSPORT.tiled_executions([TRANSPORT.normalize_fill_activity(row, order_id) for row in rows])


def rest_row(row):
    """The order state of a trade_updates row as a REST read returns it (no event fields)."""
    return {key: value for key, value in row.items() if key not in ("event", "execution_id", "event_qty", "event_price")}


if NATIVE:
    class ExecutionScript(Strategy):
        """Buys ``qty`` at the ask, then sells it at ``sell_limit`` (optionally cancelling the
        sell once accepted); records every native fill as (side, qty, price, trade id)."""

        def __new__(cls, *args, **kwargs):
            return super().__new__(cls, StrategyConfig(log_events=False, log_commands=False))

        def __init__(self, qty=29, *, symbol="APUS", sell_limit="5.60", cancel_sell=False, stop_on_cancel=True):
            self.qty, self.symbol, self.sell_limit = qty, symbol, sell_limit
            self.cancel_sell, self.stop_on_cancel = cancel_sell, stop_on_cancel
            self.buy = self.sell = None
            self.fills, self.canceled = [], []

        def on_start(self):
            self.subscribe_quotes(InstrumentId.from_str(self.symbol + ".ALPACA"))

        def on_quote(self, tick):
            if self.buy is None:
                self.buy = self.order_factory.limit(tick.instrument_id, OrderSide.BUY, Quantity.from_int(self.qty),
                                                    tick.ask_price, time_in_force=TimeInForce.DAY)
                self.submit_order(self.buy)

        def on_order_accepted(self, event):
            if self.cancel_sell and self.sell is not None and event.client_order_id == self.sell.client_order_id:
                self.cancel_order(self.sell.client_order_id)

        def filled(self, side):
            return sum(int(q) for s, q, _, _ in self.fills if s == side)

        def on_order_filled(self, event):
            side = "buy" if event.order_side == OrderSide.BUY else "sell"
            self.fills.append((side, str(event.last_qty), str(event.last_px), str(event.trade_id)))
            if side == "buy" and self.filled("buy") == self.qty:
                self.sell = self.order_factory.limit(event.instrument_id, OrderSide.SELL, Quantity.from_int(self.qty),
                                                     Price.from_str(self.sell_limit), time_in_force=TimeInForce.DAY)
                self.submit_order(self.sell)
            elif side == "sell" and self.filled("sell") == self.qty:
                self.shutdown_system("script sell filled")

        def on_order_canceled(self, event):
            self.canceled.append(str(event.client_order_id))
            if self.stop_on_cancel:
                self.shutdown_system("script sell canceled")

    class AdoptedOrderWatcher(Strategy):
        """Claims the adopted APUS order (rc5 external_order_instrument_ids), records the
        native order and positions at start, has the port stream the next fills, and stops
        once the order is filled."""

        def __new__(cls, *args, **kwargs):
            return super().__new__(cls, StrategyConfig(
                log_events=False, log_commands=False,
                external_order_instrument_ids=[InstrumentId.from_str("APUS.ALPACA")]))

        def __init__(self, port, cid, stream_rows):
            self.port, self.cid, self.stream_rows = port, cid, stream_rows
            self.fills, self.start_state, self.end_state = [], None, None

        def order_state(self):
            order = self.cache.order(ClientOrderId(self.cid))
            return (str(order.filled_qty), str(order.status), [str(t) for t in order.trade_ids],
                    len(self.cache.orders()),
                    [(str(p.instrument_id), str(p.quantity)) for p in self.cache.positions_open()])

        def on_start(self):
            self.start_state = self.order_state()
            self.port.deliver(self.stream_rows, delay=0.05)

        def on_order_filled(self, event):
            self.fills.append((str(event.last_qty), str(event.last_px), str(event.trade_id)))
            if str(self.cache.order(event.client_order_id).filled_qty) == "29":
                self.end_state = self.order_state()
                self.shutdown_system("adopted order filled")


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class PerExecutionBooking(unittest.TestCase):
    """E2: each broker execution is one native fill with its own qty and price; a
    cumulative average never prices a fill."""

    def run_script(self, port, strategy, *, grace=0.05, timeout=8):
        session = ADAPTER.build_node(port, [{"symbol": "APUS"}], [strategy])
        session.fill_gap_grace_seconds = grace
        async def exercise():
            await asyncio.wait_for(session.run_async(), timeout=timeout)
        asyncio.run(exercise())
        return session

    def sells(self, strategy):
        return [(q, p, t) for s, q, p, t in strategy.fills if s == "sell"]

    def test_apus_replay_books_three_exact_executions_without_a_freeze(self):
        rows = {}
        def sell_rows(order):
            rows["sell"] = apus_stream_rows(order)
            return rows["sell"]
        port = ScriptedPort(sell_rows=sell_rows)
        strategy = ExecutionScript()
        session = self.run_script(port, strategy)
        self.assertEqual(session.errors, [])
        ids = [row["execution_id"] for row in rows["sell"]]
        self.assertEqual(self.sells(strategy), [("26", "5.62", ids[0]), ("2", "5.61", ids[1]), ("1", "5.61", ids[2])])
        notional = sum(Decimal(q) * Decimal(p) for q, p, _ in self.sells(strategy))
        self.assertEqual(notional, Decimal("162.95"))
        self.assertEqual(port.activity_reads, [])
        stats = session.execution_stats
        self.assertEqual((stats["executions_booked"], stats["duplicate_executions"],
                          stats["average_invariant_mismatches"], stats["fill_events_missing_execution_fields"]),
                         (4, 0, 0, 0))
        self.assertEqual(session.native_assertions(), {"fill_events_carry_execution_fields": True,
                                                       "no_fill_gap_open_at_stop": True, "overturn_signals": []})
        # The old derivation from Alpaca's rounded averages: 28 x 5.619286 - 26 x 5.62 = 11.220008 for 2
        # shares, 5.610004, off the cent grid (the 2026-09-24 freeze). Nothing here derives it.
        self.assertEqual((28 * Decimal("5.619286") - 26 * Decimal("5.62")) / 2, Decimal("5.610004"))

    def test_shuffled_duplicated_and_dropped_executions_close_from_activities_without_double_booking(self):
        rows = {}
        def sell_rows(order):
            e1, e2, e3 = rows["all"] = apus_stream_rows(order)
            return [e3, e1, dict(e1)]          # E3 first, E1 twice, E2 never delivered
        port = ScriptedPort(sell_rows=sell_rows, activities=apus_activities)
        strategy = ExecutionScript()
        session = self.run_script(port, strategy)
        self.assertEqual(session.errors, [])
        e1, e2, e3 = rows["all"]
        sells = self.sells(strategy)
        self.assertEqual(len(sells), 3)
        self.assertEqual(sells[0], ("1", "5.61", e3["execution_id"]))
        self.assertEqual(sells[1], ("26", "5.62", e1["execution_id"]))
        self.assertEqual(sells[2][:2], ("2", "5.61"))   # E2 from its FILL activity
        self.assertNotIn(sells[2][2], {e1["execution_id"], e2["execution_id"], e3["execution_id"]})
        self.assertEqual(sum(int(q) for q, _, _ in sells), 29)
        self.assertEqual(sum(Decimal(q) * Decimal(p) for q, p, _ in sells), Decimal("162.95"))
        sell_id = next(o["id"] for o in port.orders.values() if o["side"] == "sell")
        self.assertEqual(port.activity_reads, [sell_id])   # one read closes the gap
        stats = session.execution_stats
        self.assertEqual((stats["activity_fill_reconciliations"], stats["activity_executions_booked"]), (1, 1))
        self.assertEqual(stats["duplicate_executions"], 3)  # E1 again, then E1 and E3 from the activities

    def test_fill_events_without_execution_fields_are_booked_from_activities(self):
        # The E2 overturn path: a paper fill event lacking execution_id, qty or price is only a
        # cumulative report; the FILL activities price every execution.
        port = ScriptedPort(sell_rows=lambda order: apus_stream_rows(order, execution_fields=False),
                            activities=apus_activities)
        strategy = ExecutionScript()
        session = self.run_script(port, strategy)
        self.assertEqual(session.errors, [])
        self.assertEqual([(q, p) for q, p, _ in self.sells(strategy)], [("26", "5.62"), ("2", "5.61"), ("1", "5.61")])
        self.assertEqual(session.execution_stats["fill_events_missing_execution_fields"], 3)
        self.assertEqual(session.execution_stats["activity_executions_booked"], 3)
        self.assertEqual(len(port.activity_reads), 1)
        # E2's overturn condition is a named receipt assertion, not only a counter.
        self.assertEqual(session.native_assertions(),
                         {"fill_events_carry_execution_fields": False, "no_fill_gap_open_at_stop": True,
                          "overturn_signals": ["e2_fill_event_without_execution_fields"]})

    def test_rest_cancel_before_the_stream_fill_defers_the_cancel_until_the_fill(self):
        stream = {}
        def cancel(order):
            filled = dict(order, filled_qty="2", filled_avg_price="5.61", updated_at_ns=time.time_ns())
            rest = dict(filled, status="canceled")                  # the REST read after DELETE, ahead of the stream
            stream["fill"] = execution(dict(filled, status="partially_filled"), "2", "5.61")
            return rest, [stream["fill"], dict(rest, updated_at_ns=time.time_ns())]
        port = ScriptedPort(cancel=cancel)
        strategy = ExecutionScript(cancel_sell=True)
        session = self.run_script(port, strategy, grace=2.0)
        self.assertEqual(session.errors, [])
        self.assertEqual(self.sells(strategy), [("2", "5.61", stream["fill"]["execution_id"])])
        self.assertEqual(strategy.canceled, [str(strategy.sell.client_order_id)])
        self.assertEqual(port.activity_reads, [])   # the stream closed the gap inside the grace period

    def test_rest_cancel_whose_stream_fill_never_arrives_closes_from_the_activity(self):
        def cancel(order):
            rest = dict(order, filled_qty="2", filled_avg_price="5.61", status="canceled", updated_at_ns=time.time_ns())
            return rest, [dict(rest)]                              # the stream fill is lost
        activities = lambda order_id: [fill_activity(order_id, 2, 2, "5.61")]
        port = ScriptedPort(cancel=cancel, activities=activities)
        strategy = ExecutionScript(cancel_sell=True)
        session = self.run_script(port, strategy)
        self.assertEqual(session.errors, [])
        self.assertEqual([(q, p) for q, p, _ in self.sells(strategy)], [("2", "5.61")])
        self.assertEqual(len(strategy.canceled), 1)
        self.assertEqual(len(port.activity_reads), 1)

    def test_a_fill_after_the_native_terminal_event_still_freezes(self):
        def cancel(order):
            filled = dict(order, filled_qty="2", filled_avg_price="5.61", updated_at_ns=time.time_ns())
            rest = dict(filled, status="canceled")
            late = execution(dict(order, filled_qty="3", filled_avg_price="5.61", status="partially_filled",
                                  updated_at_ns=time.time_ns()), "1", "5.61")
            return rest, [execution(dict(filled, status="partially_filled"), "2", "5.61"), late]
        port = ScriptedPort(cancel=cancel)
        strategy = ExecutionScript(cancel_sell=True, stop_on_cancel=False)
        session = self.run_script(port, strategy, grace=2.0)
        self.assertEqual(session.errors, ["order_post_terminal_fill_requires_reconciliation"])
        self.assertEqual([(q, p) for q, p, _ in self.sells(strategy)], [("2", "5.61")])
        self.assertEqual(len(strategy.canceled), 1)

    def rest_cancel_at_two(self, order, later):
        """The REST read after DELETE reports the sell canceled with 2 filled before any of
        its fills is booked; ``later(filled)`` gives the rows that follow on the wire."""
        filled = dict(order, filled_qty="2", filled_avg_price="5.61", updated_at_ns=time.time_ns())
        return dict(filled, status="canceled"), later(filled)

    def test_a_stream_execution_above_a_rest_cancel_freezes_before_the_cancels_fills_are_booked(self):
        # The cancel waits for its fills, but it fixed the order's final quantity at 2: an
        # execution ending at 3 is post-terminal even though it arrives before the cum-2 fill.
        stream = {}
        def later(filled):
            stream["late"] = execution(dict(filled, filled_qty="3", filled_avg_price="5.61",
                                            status="partially_filled", updated_at_ns=time.time_ns()), "1", "5.61")
            return [stream["late"], execution(dict(filled, status="partially_filled"), "2", "5.61")]
        port = ScriptedPort(cancel=lambda order: self.rest_cancel_at_two(order, later))
        strategy = ExecutionScript(cancel_sell=True, stop_on_cancel=False)
        session = self.run_script(port, strategy, grace=2.0)
        self.assertEqual(session.errors[0], "order_post_terminal_fill_requires_reconciliation")
        # The cum-2 fill that follows may still be booked before the node stops (it is the
        # cancel's own fill); nothing ending above 2 ever is.
        self.assertLessEqual(set(session.errors), {"order_post_terminal_fill_requires_reconciliation",
                                                   "fill_gap_open_at_stop"})
        self.assertNotIn(stream["late"]["execution_id"], [t for _, _, t in self.sells(strategy)])
        self.assertLessEqual(sum(int(q) for q, _, _ in self.sells(strategy)), 2)
        state = session.execution.seen[str(strategy.sell.client_order_id)]
        self.assertTrue(all(cum <= 2 for cum in state["executions"]))
        self.assertEqual(port.activity_reads, [])

    def test_activities_above_a_rest_cancel_freeze(self):
        # The stream fill never arrives, and the FILL activities show an execution ending at 3
        # past the cancel's filled quantity 2: the gap read freezes instead of booking it.
        port = ScriptedPort(cancel=lambda order: self.rest_cancel_at_two(order, lambda filled: []),
                            activities=lambda order_id: [fill_activity(order_id, 2, 2, "5.61", index=0),
                                                         fill_activity(order_id, 3, 1, "5.61", index=1)])
        strategy = ExecutionScript(cancel_sell=True, stop_on_cancel=False)
        session = self.run_script(port, strategy)
        # The read failed closed and the gap it was closing is still open when the node stops.
        self.assertEqual(session.errors, ["fill_gap_post_terminal_fill_requires_reconciliation", "fill_gap_open_at_stop"])
        self.assertEqual(self.sells(strategy), [])
        self.assertEqual(strategy.canceled, [])
        self.assertEqual(len(port.activity_reads), 1)

    def gap_rows(self, order):
        """The first APUS execution arrives without its execution fields (a cumulative report
        only): a gap at 26 that only the activities can close."""
        rows = apus_stream_rows(order, execution_fields=False)
        return [rows[0]]

    def test_a_gap_the_activities_leave_open_freezes(self):
        port = ScriptedPort(sell_rows=self.gap_rows, activities=lambda order_id: [])
        session = self.run_script(port, ExecutionScript())
        self.assertEqual(session.errors, ["fill_gap_unresolved_after_activities", "fill_gap_open_at_stop"])
        self.assertEqual(len(port.activity_reads), 1)

    def test_incomplete_activity_tiling_is_refused_before_observation_or_native_booking(self):
        for keep, reason in (((0, 2), "fill_gap_fill_activity_ledger_incomplete"),
                             ((0, 1), "fill_gap_unresolved_after_activities")):
            with self.subTest(activities=keep):
                class IncompleteActivities(ScriptedPort):
                    async def fill_activities(self, order_id):
                        rows = await super().fill_activities(order_id)
                        return [rows[index] for index in keep]

                observations = []
                port = IncompleteActivities(
                    sell_rows=lambda order: [rest_row(apus_stream_rows(order)[-1])],
                    activities=apus_activities)
                port.sink_observation = observations.append
                strategy = ExecutionScript()
                session = self.run_script(port, strategy)
                self.assertEqual(session.errors, [reason, "fill_gap_open_at_stop"])
                self.assertEqual(observations, [])
                self.assertEqual(self.sells(strategy), [])
                self.assertEqual(session.execution_stats["activity_executions_booked"], 0)

    def test_a_failing_activities_read_freezes_with_its_error(self):
        class Failing(ScriptedPort):
            async def fill_activities(self, order_id):
                self.activity_reads.append(order_id)
                raise TRANSPORT.TransportError("fill activity lookup failed")
        port = Failing(sell_rows=self.gap_rows)
        session = self.run_script(port, ExecutionScript())
        self.assertEqual(session.errors, ["fill_gap_TransportError", "fill_gap_open_at_stop"])
        self.assertEqual(len(port.activity_reads), 1)

    def test_a_gap_on_a_port_without_activities_freezes(self):
        class NoActivities(ScriptedPort):
            fill_activities = None
        session = self.run_script(NoActivities(sell_rows=self.gap_rows), ExecutionScript())
        self.assertEqual(session.errors, ["fill_gap_unresolved_without_activities", "fill_gap_open_at_stop"])

    def test_a_gap_still_open_when_the_session_stops_is_a_named_adapter_error(self):
        # B3: the node stops inside the grace period (for example the run ended right after a
        # REST read revealed a fill); the native side never booked that execution.
        port = ScriptedPort(sell_rows=self.gap_rows, activities=apus_activities)
        session = ADAPTER.build_node(port, [{"symbol": "APUS"}], [ExecutionScript()])
        session.fill_gap_grace_seconds = 30.0
        port.after_sell_rows = session.stop
        async def exercise():
            await asyncio.wait_for(session.run_async(), timeout=8)
        asyncio.run(exercise())
        self.assertEqual(session.errors, ["fill_gap_open_at_stop"])
        self.assertEqual(session.execution_stats["open_fill_gaps_at_stop"], 1)
        self.assertEqual(port.activity_reads, [])
        self.assertEqual(session.native_assertions(),
                         {"fill_events_carry_execution_fields": False, "no_fill_gap_open_at_stop": False,
                          "overturn_signals": ["e2_fill_event_without_execution_fields",
                                               "e2_fill_gap_open_at_stop"]})

    def test_a_gap_opened_during_another_gaps_grace_gets_its_own_grace(self):
        # A2/B2: a gap at 26 opens at t=0; at 0.4 s a REST read reports 28 while the stream
        # fills for 28 and 29 are still behind (they land at 0.8 s). The one activities read
        # at 0.6 s closes 26 (the activity for 28 is not visible yet) and must not fail the
        # younger gap at 28, which the stream closes inside its own grace (until 1.0 s).
        def sell_rows(order):
            bare = apus_stream_rows(order, execution_fields=False)
            full = apus_stream_rows(order)
            return [bare[0], 0.4, rest_row(bare[1]), 0.4, full[1], full[2]]
        port = ScriptedPort(sell_rows=sell_rows, activities=lambda order_id: apus_activities(order_id)[:1])
        strategy = ExecutionScript()
        session = self.run_script(port, strategy, grace=0.6)
        self.assertEqual(session.errors, [])
        self.assertEqual([(q, p) for q, p, _ in self.sells(strategy)], [("26", "5.62"), ("2", "5.61"), ("1", "5.61")])
        self.assertEqual(len(port.activity_reads), 1)
        self.assertEqual(session.execution_stats["activity_executions_booked"], 1)
        self.assertEqual(session.native_assertions()["overturn_signals"], ["e2_fill_event_without_execution_fields"])

    def test_a_quantity_reported_during_the_activities_read_is_a_new_gap_not_a_failure(self):
        # A2: while the read for the gap at 26 is in flight (at 0.4 s), a REST read reports 29
        # (its stream fills are behind; they land at 0.6 s). The read books 26; 29 then has
        # its own grace (until 0.8 s) and the stream closes it.
        script = {}
        def sell_rows(order):
            bare = apus_stream_rows(order, execution_fields=False)
            full = apus_stream_rows(order)
            script["ahead"] = rest_row(bare[2])
            return [bare[0], 0.6, full[1], full[2]]
        port = ScriptedPort(sell_rows=sell_rows, activities=lambda order_id: apus_activities(order_id)[:1],
                            activity_delay=0.05, during_activity_read=lambda order: [script["ahead"]])
        strategy = ExecutionScript()
        session = self.run_script(port, strategy, grace=0.4)
        self.assertEqual(session.errors, [])
        self.assertEqual([(q, p) for q, p, _ in self.sells(strategy)], [("26", "5.62"), ("2", "5.61"), ("1", "5.61")])
        self.assertEqual(len(port.activity_reads), 1)

    def test_a_cumulative_average_that_disagrees_with_the_executions_is_recorded_not_frozen(self):
        port = ScriptedPort(sell_rows=lambda order: apus_stream_rows(order, averages={2: "5.62"}))
        strategy = ExecutionScript()
        session = self.run_script(port, strategy)
        self.assertEqual(session.errors, [])
        self.assertEqual(len(self.sells(strategy)), 3)
        self.assertEqual(session.execution_stats["average_invariant_mismatches"], 1)
        self.assertEqual(session.average_invariant_mismatches[0]["executions_notional"], "162.95")

    def test_same_quantity_with_a_changed_average_still_freezes(self):
        def sell_rows(order):
            rows = apus_stream_rows(order)
            corrected = {key: value for key, value in rows[0].items()
                         if key not in ("event", "execution_id", "event_qty", "event_price")}
            return [rows[0], dict(corrected, filled_avg_price="5.63")]   # a REST read of the same 26 at a new average
        port = ScriptedPort(sell_rows=sell_rows)
        strategy = ExecutionScript()
        session = self.run_script(port, strategy, timeout=3)
        self.assertEqual(session.errors, ["order_same_quantity_fill_correction_requires_reconciliation"])

    def test_every_documented_trade_updates_event_has_exactly_one_handling(self):
        # https://docs.alpaca.markets/us/docs/websocket-streaming.md lists these events; alpaca-py
        # 0.44.0's TradeEvent adds "restated". trade_correct and trade_bust are not trade_updates events.
        documented = {"new": "status", "fill": "execution", "partial_fill": "execution", "canceled": "status",
                      "expired": "status", "done_for_day": "unsupported_trade_event_requires_reconciliation",
                      "replaced": "replace_event_requires_reconciliation", "accepted": "status", "rejected": "status",
                      "pending_new": "status", "stopped": "unsupported_trade_event_requires_reconciliation",
                      "pending_cancel": "status", "pending_replace": "replace_event_requires_reconciliation",
                      "calculated": "unsupported_trade_event_requires_reconciliation",
                      "suspended": "unsupported_trade_event_requires_reconciliation",
                      "order_replace_rejected": "replace_event_requires_reconciliation",
                      "order_cancel_rejected": "status",
                      "restated": "unsupported_trade_event_requires_reconciliation"}
        for event, kind in documented.items():
            with self.subTest(event=event):
                self.assertEqual(ADAPTER.trade_event_kind(event), kind)
        for event in ("trade_correct", "trade_bust", "FILL", ""):
            with self.subTest(event=event):
                self.assertEqual(ADAPTER.trade_event_kind(event), "unknown_trade_event_requires_reconciliation")
        self.assertEqual(ADAPTER.trade_event_kind(None), "status")   # a REST read carries no event

    def test_an_undocumented_trade_event_freezes_the_adapter(self):
        def sell_rows(order):
            return [dict(apus_stream_rows(order)[0], event="trade_bust")]
        port = ScriptedPort(sell_rows=sell_rows)
        session = self.run_script(port, ExecutionScript(), timeout=3)
        self.assertEqual(session.errors, ["order_unknown_trade_event_requires_reconciliation"])

    def test_activity_trade_ids_are_the_36_character_uuid_of_the_activity_id(self):
        row = fill_activity(str(uuid.uuid4()), 26, 26, "5.62")
        trade_id = TRANSPORT.activity_trade_id(row["id"])
        self.assertEqual(len(trade_id), 36)
        self.assertEqual(trade_id, row["id"].split("::")[1])
        self.assertEqual(str(ADAPTER.execution_trade_id(trade_id)), trade_id)
        with self.assertRaises(ValueError):   # NautilusTrader refuses a 37-character TradeId
            ADAPTER.TradeId("x" * 37)


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class StartupFillReports(unittest.TestCase):
    """A restart that adopts an open, partly filled order (overnight holds) reports its
    fills from the FILL activities instead of raising or deriving them."""

    def open_order(self, filled="26", average="5.62"):
        return {"client_order_id": "adp-t1-0000009", "id": str(uuid.uuid4()), "symbol": "APUS", "side": "sell",
                "qty": "29", "filled_qty": filled, "filled_avg_price": average, "status": "partially_filled",
                "limit_price": "5.60", "updated_at_ns": time.time_ns()}

    def session(self, port):
        policy = {"extended_hours": True, "overnight_holds": True, "overnight_gross_multiple": Decimal("1.0")}
        return ADAPTER.build_node(port, [{"symbol": "APUS"}], [], session_policy=policy)

    def reports(self, port, row):
        session = self.session(port)
        session.snapshot_state = {"account": {}, "orders": [row], "positions": []}
        try:
            return session, asyncio.run(session.execution._generate_fill_reports(None))
        finally:
            session.node.dispose()

    def test_restart_with_fills_reports_each_execution_from_the_activities(self):
        row = self.open_order()
        # The activities also hold a later execution (28) the snapshot does not include yet.
        port = ScriptedPort(activities=lambda order_id: apus_activities(order_id)[:2])
        session, reports = self.reports(port, row)
        self.assertEqual(port.activity_reads, [row["id"]])
        self.assertEqual([(str(r.last_qty), str(r.last_px)) for r in reports], [("26", "5.62")])
        self.assertEqual(len(str(reports[0].trade_id)), 36)
        state = session.execution.seen[row["client_order_id"]]
        self.assertEqual((state["booked"], state["broker_filled"], state["accepted"]), (Decimal(26), Decimal(26), True))
        self.assertEqual(session.execution_stats["startup_fill_reports"], 1)

    def test_incomplete_or_missing_activities_refuse_the_restart(self):
        row = self.open_order(filled="28", average="5.619286")
        port = ScriptedPort(activities=lambda order_id: apus_activities(order_id)[:1])   # 26 of 28
        with self.assertRaisesRegex(ValueError, "historical_fill_ledger_incomplete"):
            self.reports(port, row)
        class NoActivities(ScriptedPort):
            fill_activities = None
        with self.assertRaisesRegex(ValueError, "historical_fill_ledger_not_supplied_by_port"):
            self.reports(NoActivities(), row)

    def test_an_adopted_partly_filled_order_books_one_native_fill_per_execution_through_rc5_startup(self):
        # A4, local integration: rc5's own startup reconciliation (not a direct call) of an
        # adopted buy at 26 of 29 (two executions), then the next two stream fills. rc5 applies
        # reconciliation events in timestamp order: with the acceptance stamped at the order's
        # last update (after its fills) it dropped the real fills as invalid transitions, left
        # the order ACCEPTED with nothing filled and synthesized a second order for the position.
        from types import SimpleNamespace
        order_id, cid = str(uuid.uuid4()), "adp-t1-0000009"
        row = {"client_order_id": cid, "id": order_id, "symbol": "APUS", "side": "buy", "qty": "29",
               "filled_qty": "26", "filled_avg_price": "5.62", "status": "partially_filled", "limit_price": "5.63",
               "updated_at_ns": time.time_ns()}
        activities = [fill_activity(order_id, 20, 20, "5.62", side="buy", index=0),
                      fill_activity(order_id, 26, 6, "5.62", side="buy", index=1)]
        stream = [execution(dict(row, filled_qty="28", filled_avg_price="5.619286", updated_at_ns=time.time_ns()),
                            "2", "5.61"),
                  execution(dict(row, filled_qty="29", filled_avg_price="5.618966", status="filled",
                                 updated_at_ns=time.time_ns() + 1), "1", "5.61")]
        port = ScriptedPort(activities=lambda oid: activities, snapshot_orders=[row],
                            snapshot_positions=[{"symbol": "APUS", "qty": "26", "avg_entry_price": "5.62"}])
        strategy = AdoptedOrderWatcher(port, cid, stream)
        policy = {"extended_hours": True, "overnight_holds": True, "overnight_gross_multiple": Decimal("1.0")}
        session = ADAPTER.build_node(port, [{"symbol": "APUS"}], [strategy], session_policy=policy)
        async def exercise():
            await asyncio.wait_for(session.run_async(), timeout=8)
        asyncio.run(exercise())
        startup = [activity["id"].split("::")[1] for activity in activities]
        streamed = [r["execution_id"] for r in stream]
        self.assertEqual(session.errors, [])
        self.assertEqual(port.activity_reads, [order_id])            # one read, at connect
        # The startup fills landed on the adopted order itself; no synthetic order was made.
        self.assertEqual(strategy.start_state, ("26", "PARTIALLY_FILLED", startup, 1, [("APUS.ALPACA", "26")]))
        self.assertEqual(strategy.fills, [("2", "5.61", streamed[0]), ("1", "5.61", streamed[1])])
        self.assertEqual(strategy.end_state, ("29", "FILLED", startup + streamed, 1, [("APUS.ALPACA", "29")]))
        self.assertEqual((session.execution_stats["startup_fill_reports"], session.execution_stats["executions_booked"]),
                         (2, 2))
        # A later fill-report request reports what is booked natively, never resets it or reads again,
        # and honours the command's filters.
        execution_client = session.execution
        everything = SimpleNamespace(venue_order_id=None, instrument_id=None)
        reports = asyncio.run(execution_client._generate_fill_reports(everything))
        self.assertEqual([str(r.trade_id) for r in reports], startup + streamed)
        self.assertEqual(execution_client.seen[cid]["booked"], Decimal(29))
        self.assertEqual(port.activity_reads, [order_id])
        other = SimpleNamespace(venue_order_id=ADAPTER.VenueOrderId(str(uuid.uuid4())), instrument_id=None)
        self.assertEqual(asyncio.run(execution_client._generate_fill_reports(other)), [])
        this = SimpleNamespace(venue_order_id=ADAPTER.VenueOrderId(order_id),
                               instrument_id=ADAPTER.InstrumentId.from_str("APUS.ALPACA"))
        self.assertEqual(len(asyncio.run(execution_client._generate_fill_reports(this))), 4)
        elsewhere = SimpleNamespace(venue_order_id=None, instrument_id=ADAPTER.InstrumentId.from_str("SPY.ALPACA"))
        self.assertEqual(asyncio.run(execution_client._generate_fill_reports(elsewhere)), [])


GUARDED_MODULES = ("native_strategy.py", "mover_strategy.py", "benchmark.py")


def strategy_handlers(source):
    """(class, handler, guarded) for every on_order_* / on_position_* method defined on a
    NautilusTrader Strategy subclass in ``source``."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and any(getattr(base, "id", getattr(base, "attr", None)) == "Strategy"
                                                  for base in node.bases):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                        item.name.startswith(("on_order_", "on_position_")):
                    names = {getattr(d, "id", getattr(d, "attr", None)) for d in item.decorator_list}
                    yield node.name, item.name, "guarded_callback" in names


class CallbackGuardCoverage(unittest.TestCase):
    """E3 (upstream nautilus_trader#5039: rc5's LiveNode discards an exception raised in an
    order or position callback). Every such handler in the engine's strategies is wrapped."""

    def test_every_order_and_position_handler_is_guarded(self):
        for module in GUARDED_MODULES:
            source = (Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper" / module).read_text()
            handlers = list(strategy_handlers(source))
            self.assertTrue(handlers, module)   # the scan found the handlers it checks
            for class_name, name, guarded in handlers:
                with self.subTest(module=module, handler=class_name + "." + name):
                    self.assertTrue(guarded, "unguarded order/position callback")
                    # The freeze reason the guard derives from the name passes Ledger.freeze's check.
                    self.assertRegex("strategy_callback_exception_" + name, r"\A[a-z][a-z0-9_]{0,79}\Z")

    def test_the_scan_reports_an_unguarded_handler(self):
        source = ("class S(Strategy):\n    @guarded_callback\n    def on_order_filled(self, e): pass\n"
                  "    def on_position_opened(self, e): pass\n    def on_quote(self, q): pass\n"
                  "class NotAStrategy:\n    def on_order_filled(self, e): pass\n")
        self.assertEqual(list(strategy_handlers(source)),
                         [("S", "on_order_filled", True), ("S", "on_position_opened", False)])


if NATIVE:
    class UnguardedRaiser(Roundtrip):
        """Roundtrip whose on_order_filled raises on the first fill, before its own
        bookkeeping, with no guard (the nautilus_trader#5039 characterization)."""

        def __init__(self):
            super().__init__("fills")
            self.raised = self.dispatched_after_raise = 0

        def on_order_filled(self, event):
            if not self.raised:
                self.raised = 1
                raise RuntimeError("characterization: unguarded exception in on_order_filled")
            self.dispatched_after_raise += 1
            super().on_order_filled(event)
            self.shutdown_system("characterization complete")


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class UpstreamCallbackLoss(unittest.TestCase):
    """Local integration (real 2.0.0rc5 LiveNode, synthetic port): why the E3 guard exists.
    rc5 discards an exception raised in a Strategy order callback (upstream #5039:
    strategy.rs dispatches with ``let _ =``): nothing reaches the adapter or the session,
    the node keeps dispatching and the raising call's own bookkeeping is lost. If a later
    release surfaces the exception or stops the node, this fails, which is E3's overturn
    condition (the guard can then shrink to record and freeze)."""

    def test_rc5_livenode_discards_an_unguarded_order_callback_exception(self):
        port, strategy = FakePort("fills"), UnguardedRaiser()
        session = ADAPTER.build_node(port, [{"symbol": "SPY", "currency": "USD"}], [strategy])

        async def exercise():
            await asyncio.wait_for(session.run_async(), timeout=8)
        asyncio.run(exercise())          # no exception propagates out of the node
        self.assertEqual((strategy.raised, strategy.dispatched_after_raise), (1, 1))
        self.assertEqual(session.errors, [])
        self.assertEqual(strategy.buy_qty, 1)   # the first fill's share was never counted
        self.assertEqual(port.qty, 2)           # while the broker side holds both


if NATIVE:
    class FaultyPending(dict):
        """Strategy order bookkeeping that raises: a fault beneath the guard, not a patched handler."""
        def get(self, *args):
            raise RuntimeError("injected pending fault")

        def pop(self, *args):
            raise RuntimeError("injected pending fault")


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class AdaptiveCallbackGuard(unittest.TestCase):
    NOW = 1772550000.0

    def make(self, tmp):
        ledger = Ledger(Path(tmp) / "guard.sqlite3", RiskLimits())
        ledger.start_trial(self.NOW)
        config = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4)
        events, sunk = [], []
        strategy = _LeverageFixtureStrategy(AdaptivePolicy(config), ledger, "t1", event_sink=events.append,
                                            clock=lambda: self.NOW)
        strategy.started = strategy.enabled = True
        strategy.fault_sink = sunk.append
        submitted = []
        strategy.submit_order = lambda *args, **kwargs: submitted.append(args)
        return strategy, ledger, events, sunk, submitted

    def test_an_exception_in_any_order_handler_freezes_stops_submits_and_stops_the_session(self):
        from types import SimpleNamespace
        event = SimpleNamespace(client_order_id="adp-t1-0000001", reason="broker says no")
        for name in ("on_order_filled", "on_order_canceled", "on_order_expired", "on_order_rejected",
                     "on_order_denied", "on_order_cancel_rejected"):
            with self.subTest(handler=name), tempfile.TemporaryDirectory() as tmp:
                strategy, ledger, events, sunk, submitted = self.make(tmp)
                strategy.pending = FaultyPending()
                with self.assertRaisesRegex(RuntimeError, "injected pending fault"):
                    getattr(strategy, name)(event)
                reason = "strategy_callback_exception_" + name
                self.assertEqual(ledger.halted_reason(), reason)
                self.assertTrue(strategy.faulted)
                self.assertFalse(strategy.enabled)
                self.assertEqual(sunk, [reason + ":RuntimeError"])
                fault = strategy.callback_faults[0]
                self.assertEqual((fault["callback"], fault["error_type"], fault["freeze_reason"]),
                                 (name, "RuntimeError", reason))
                self.assertRegex(fault["traceback_sha256"], r"\A[0-9a-f]{64}\Z")
                self.assertEqual(events[-1]["type"], "strategy_callback_exception")
                strategy.pending = {}
                self.assertIsNone(strategy.rebalance(self.NOW))   # no decision, no submit after the fault
                self.assertEqual(submitted, [])
                ledger.close()

    def test_a_failing_freeze_still_stops_the_session(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            strategy, ledger, events, sunk, submitted = self.make(tmp)
            strategy.pending = FaultyPending()
            ledger.close()   # the ledger itself is gone: freeze raises, the session still stops
            with self.assertRaises(RuntimeError):
                strategy.on_order_filled(SimpleNamespace(client_order_id="adp-t1-0000001"))
            self.assertEqual(sunk, ["strategy_callback_exception_on_order_filled:RuntimeError"])
            self.assertIn("freeze_error", strategy.callback_faults[0])


if __name__ == "__main__":
    unittest.main()
