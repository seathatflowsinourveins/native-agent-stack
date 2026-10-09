"""Offline seams for upstream builtins and additive diagnostic STOP handling.

All latches, ledger state and ports are fixtures; no broker or host STOP is read.
"""
import asyncio
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import runner
import safety

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    import native_adapter
    import native_strategy
    from nautilus_trader.model import InstrumentId, Quantity, TimeInForce
    from nautilus_trader.testkit import ExecTesterConfig


@unittest.skipUnless(NATIVE, "requires pinned Nautilus runtime")
class BuiltinRegistration(unittest.TestCase):
    def test_builtin_keeps_config_identity_and_existing_python_registration(self):
        builtin = ExecTesterConfig(
            instrument_id=InstrumentId.from_str("SPY.ALPACA"),
            order_qty=Quantity.from_int(1), limit_time_in_force=TimeInForce.DAY,
            dry_run=True, log_data=False,
        )
        python_strategy = object()
        node = Mock(spec=["handle", "add_strategy", "add_builtin_strategy"])
        native_node = Mock()
        native_node.build.return_value = node
        with patch.object(native_adapter, "LiveNode", native_node):
            session = native_adapter.build_node(
                object(), [{"symbol": "SPY"}], [python_strategy],
                builtin_strategies=[("ExecTester", builtin)],
            )
        self.assertIs(session.node, node)
        node.add_strategy.assert_called_once_with(python_strategy)
        node.add_builtin_strategy.assert_called_once_with("ExecTester", builtin)
        self.assertIs(node.add_builtin_strategy.call_args.args[1], builtin)
        config = native_node.build.call_args.args[1]
        self.assertFalse(config.risk_engine.bypass)
        self.assertTrue(config.exec_engine.reconciliation)

    def test_default_path_does_not_register_a_builtin(self):
        python_strategy = object()
        node = Mock(spec=["handle", "add_strategy", "add_builtin_strategy"])
        native_node = Mock()
        native_node.build.return_value = node
        with patch.object(native_adapter, "LiveNode", native_node):
            native_adapter.build_node(object(), [{"symbol": "SPY"}], [python_strategy])
        node.add_strategy.assert_called_once_with(python_strategy)
        node.add_builtin_strategy.assert_not_called()

    def test_installed_native_registry_accepts_dry_run_builtin_without_start(self):
        builtin = ExecTesterConfig(
            instrument_id=InstrumentId.from_str("SPY.ALPACA"),
            order_qty=Quantity.from_int(1), limit_time_in_force=TimeInForce.DAY,
            dry_run=True, log_data=False,
        )
        # Building and registering are offline. The port has no broker methods
        # and the node is never started, so registration cannot place an order.
        native_adapter.build_node(
            object(), [{"symbol": "SPY"}], [],
            builtin_strategies=[("ExecTester", builtin)],
        )

    def test_non_dry_run_builtin_is_refused_before_node_construction(self):
        builtin = ExecTesterConfig(
            instrument_id=InstrumentId.from_str("SPY.ALPACA"),
            order_qty=Quantity.from_int(1), limit_time_in_force=TimeInForce.DAY,
            dry_run=False, log_data=False,
        )
        with patch.object(native_adapter, "LiveNode") as native_node:
            with self.assertRaisesRegex(ValueError, "builtin_strategy_requires_dry_run"):
                native_adapter.build_node(
                    object(), [{"symbol": "SPY"}], [],
                    builtin_strategies=[("ExecTester", builtin)],
                )
        native_node.build.assert_not_called()

    def test_missing_dry_run_in_mixed_builtins_refuses_all_registration(self):
        valid = ExecTesterConfig(
            instrument_id=InstrumentId.from_str("SPY.ALPACA"),
            order_qty=Quantity.from_int(1), dry_run=True, log_data=False,
        )
        with patch.object(native_adapter, "LiveNode") as native_node:
            with self.assertRaisesRegex(ValueError, "builtin_strategy_requires_dry_run"):
                native_adapter.build_node(
                    object(), [{"symbol": "SPY"}], [object()],
                    builtin_strategies=[("ExecTester", valid), ("MissingFlag", object())],
                )
        native_node.build.assert_not_called()

    def test_truthy_dry_run_value_does_not_authorize_builtin_registration(self):
        for value in (1, "true", None):
            with self.subTest(value=value):
                with patch.object(native_adapter, "LiveNode") as native_node:
                    with self.assertRaisesRegex(ValueError, "builtin_strategy_requires_dry_run"):
                        native_adapter.build_node(
                            object(), [{"symbol": "SPY"}], [],
                            builtin_strategies=[("InvalidFlag", SimpleNamespace(dry_run=value))],
                        )
                native_node.build.assert_not_called()


@unittest.skipUnless(NATIVE, "requires pinned Nautilus runtime for NativeOrderRejected")
class ControllerStopBoundaries(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="diagnostic-seam-fixture-")
        self.root = Path(self.directory.name)
        self.global_stop, self.local_stop = self.root / "global-STOP", self.root / "run-STOP"
        self.patches = [patch.object(module, "DEFAULT_STOP", self.global_stop)
                        for module in (runner, safety, native_strategy)]
        for item in self.patches:
            item.start()
        self.now = 1_800_000_000.0
        self.ledger = safety.Ledger(self.root / "ledger.sqlite3")
        self.ledger.start_trial(self.now)

    def tearDown(self):
        self.ledger.close()
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def controller(self, *, explicit=False):
        controller = runner.Controller(
            self.ledger, self.now + 3600, market_open=True, clock=lambda: self.now,
            **({"stop_file": self.local_stop} if explicit else {}),
        )
        controller.port = SimpleNamespace(ready=True)
        controller.quotes["SPY"] = safety.Quote(
            "SPY", Decimal("100.00"), Decimal("100.01"), self.now,
        )
        return controller

    @staticmethod
    def order(client_id="diagnostic-fixture-1"):
        return {"client_order_id": client_id, "symbol": "SPY", "side": "buy",
                "qty": "1", "limit_price": "100.01"}

    def test_default_keeps_ledger_stop_arguments_unchanged(self):
        controller = self.controller()
        with patch.object(self.ledger, "reserve_intent", wraps=self.ledger.reserve_intent) as reserve:
            controller.before_submit(self.order())
        self.assertNotIn("stop_file", reserve.call_args.kwargs)
        with patch.object(self.ledger, "validate_pending", wraps=self.ledger.validate_pending) as validate:
            asyncio.run(controller.before_request("submit", "diagnostic-fixture-1"))
        self.assertNotIn("stop_file", validate.call_args.kwargs)

    def test_explicit_latch_reaches_reservation_and_final_pending_check(self):
        controller = self.controller(explicit=True)
        with patch.object(self.ledger, "reserve_intent", wraps=self.ledger.reserve_intent) as reserve:
            controller.before_submit(self.order())
        self.assertEqual(reserve.call_args.kwargs["stop_file"], self.local_stop)
        with patch.object(self.ledger, "validate_pending", wraps=self.ledger.validate_pending) as validate:
            asyncio.run(controller.before_request("submit", "diagnostic-fixture-1"))
        self.assertEqual(validate.call_args.kwargs["stop_file"], self.local_stop)

    def test_explicit_latch_blocks_entry_before_an_intent_is_reserved(self):
        self.local_stop.touch()
        controller = self.controller(explicit=True)
        with self.assertRaisesRegex(native_adapter.NativeOrderRejected, "admissions_not_ready"):
            controller.before_submit(self.order())
        self.assertEqual(self.ledger.intents(), [])

    def test_default_global_latch_keeps_the_existing_entry_refusal(self):
        self.global_stop.touch()
        controller = self.controller()
        with self.assertRaisesRegex(native_adapter.NativeOrderRejected, "stop_blocks_entry"):
            controller.before_submit(self.order())
        self.assertEqual(self.ledger.intents(), [])

    def test_explicit_latch_cannot_bypass_the_global_abort(self):
        self.global_stop.touch()
        controller = self.controller(explicit=True)
        with self.assertRaisesRegex(native_adapter.NativeOrderRejected, "admissions_not_ready"):
            controller.before_submit(self.order())
        self.assertEqual(self.ledger.intents(), [])

    def test_either_latch_created_after_reservation_refuses_the_first_post(self):
        controller = self.controller(explicit=True)
        controller.before_submit(self.order())
        for stop in (self.local_stop, self.global_stop):
            with self.subTest(latch=stop.name):
                stop.touch()
                with self.assertRaisesRegex(safety.SafetyError, "stop_blocks_entry"):
                    asyncio.run(controller.before_request("submit", "diagnostic-fixture-1"))
                self.assertEqual(controller.requests, [])
                attempted = self.ledger.db.execute(
                    "SELECT submit_attempted FROM intents WHERE client_id=?",
                    ("diagnostic-fixture-1",),
                ).fetchone()[0]
                self.assertEqual(attempted, 0)
                stop.unlink()

    def test_readiness_loss_during_pending_validation_refuses_request_reservation(self):
        for boundary in ("global_stop", "port_not_ready", "controller_abort"):
            with self.subTest(boundary=boundary):
                controller = self.controller(explicit=True)
                client_id = "diagnostic-fixture-" + boundary
                controller.before_submit(self.order(client_id))
                validate_pending = self.ledger.validate_pending

                def refuse_after_validation(*args, **kwargs):
                    self.assertEqual(kwargs["stop_file"], self.local_stop)
                    intent = validate_pending(*args, **kwargs)
                    if boundary == "global_stop":
                        self.global_stop.touch()
                    elif boundary == "port_not_ready":
                        controller.port.ready = False
                    else:
                        controller.stop = True
                    return intent

                with patch.object(self.ledger, "validate_pending", side_effect=refuse_after_validation):
                    with self.assertRaisesRegex(safety.SafetyError, "admissions_not_ready"):
                        asyncio.run(controller.before_request("submit", client_id))
                self.assertEqual(controller.requests, [])
                attempted = self.ledger.db.execute(
                    "SELECT submit_attempted FROM intents WHERE client_id=?", (client_id,),
                ).fetchone()[0]
                self.assertEqual(attempted, 0)
                self.global_stop.unlink(missing_ok=True)

    def test_lifecycle_stop_request_includes_both_latches_and_controller_abort(self):
        controller = self.controller(explicit=True)
        self.assertFalse(controller.stop_requested())
        for stop in (self.local_stop, self.global_stop):
            stop.touch()
            self.assertTrue(controller.stop_requested())
            stop.unlink()
        controller.stop = True
        self.assertTrue(controller.stop_requested())

    def test_active_abort_preserves_owned_position_sell_and_cancel(self):
        controller = self.controller(explicit=True)
        controller.before_submit(self.order("diagnostic-fixture-filled-buy"))
        self.ledger.record_order(
            "diagnostic-fixture-filled-buy", "broker-fixture-buy", "filled",
            "1", "100.01", timestamp=self.now,
        )
        self.global_stop.touch()
        self.local_stop.touch()
        controller.stop = True
        controller.port.ready = False
        reducing = self.order("diagnostic-fixture-reducing-sell")
        reducing.update(side="sell", limit_price="100.00")
        controller.before_submit(reducing)
        asyncio.run(controller.before_request("submit", reducing["client_order_id"]))
        asyncio.run(controller.before_request("cancel", reducing["client_order_id"]))
        self.assertEqual(len(controller.requests), 2)
        reserved = self.ledger.db.execute(
            "SELECT side FROM intents WHERE client_id=?", (reducing["client_order_id"],),
        ).fetchone()[0]
        self.assertEqual(reserved, "sell")

    def test_local_latch_reaches_native_lifecycle_before_duration_cleanup(self):
        from runner import PolicyConfig, load_config, run_native
        from simulation import SimulatedPort

        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=30, cleanup_seconds=1, order_timeout_seconds=1)
        policy = PolicyConfig(
            symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
            warmup_samples=4, warmup_seconds=.06,
            sample_seconds=.02, rebalance_seconds=.02, min_hold_seconds=.05,
            max_hold_seconds=.4, cooldown_seconds=.05,
        )
        controller = self.controller(explicit=True)
        controller.port = SimulatedPort(controller, policy.symbols)
        self.local_stop.touch()

        async def exercise():
            # Without the local STOP lifecycle hook this would run for 30s.
            return await asyncio.wait_for(
                run_native(controller, policy, [{"symbol": symbol} for symbol in policy.symbols],
                           "diagnostic-lifecycle-fixture", config, "100000"),
                timeout=3,
            )

        result = asyncio.run(exercise())
        self.assertTrue(controller.stop)
        self.assertEqual(self.ledger.intents(), [])
        self.assertIn(result["status"], ("passed", "completed_no_signals"))


if __name__ == "__main__":
    unittest.main()
