"""Local cross-module tests: native engine, controller, ledger, synthetic port."""
import asyncio
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
try:
    import nautilus_trader
    import alpaca
    from runner import Controller, reconcile, run_native, load_config, validate_preflight
    from safety import Ledger, Quote, RiskLimits, SafetyError
    from strategies import PolicyConfig
    from simulation import SimulatedPort
    NATIVE = True
except ImportError:
    NATIVE = False


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class IntegratedRunner(unittest.TestCase):
    def test_default_config_is_bounded(self):
        config, risk, policy = load_config(SOURCE / "config.json")
        self.assertEqual(risk.max_submits_per_minute, 180)
        self.assertEqual(policy.max_leverage, 1)
        self.assertEqual(len(policy.symbols), 24)

    def test_native_adaptive_policy_reaches_ledger_and_flat_reconciliation(self):
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=2, cleanup_seconds=2, order_timeout_seconds=1)
        with tempfile.TemporaryDirectory() as root:
            limits = RiskLimits(trial_seconds=2, cleanup_seconds=2)
            ledger = Ledger(Path(root) / "journal.db", limits)
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                                  warmup_samples=4, warmup_seconds=.06, sample_seconds=.02,
                                  rebalance_seconds=.02, min_hold_seconds=.05, max_hold_seconds=.4,
                                  cooldown_seconds=.05)
            def price(symbol, tick):
                slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
                return Decimal("100") + min(tick, 70) * slope
            port = SimulatedPort(controller, policy.symbols, price=price)
            controller.port = port
            result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                            "fixture", config, "100000"))
            self.assertEqual(result["status"], "passed", result)
            self.assertTrue(result["flat"])
            self.assertGreater(result["native_fill_events"], 0, result)
            self.assertTrue(any(e["type"] == "intent" for e in controller.events))
            self.assertEqual(len(ledger.unresolved()), 0)
            self.assertEqual(port.started, 1)
            self.assertEqual(port.stopped, 1)
            ledger.close()

    def test_reconcile_rejects_external_position_and_cash_gap(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            snapshot = {"complete": True, "orders": [], "positions": [{"symbol": "SPY", "qty": "1"}],
                        "account": {"cash": "100000"}}
            with self.assertRaisesRegex(SafetyError, "position_mismatch"):
                reconcile(ledger, snapshot, "100000")
            snapshot["positions"] = []
            snapshot["account"]["cash"] = "99999"
            with self.assertRaisesRegex(SafetyError, "cash_mismatch"):
                reconcile(ledger, snapshot, "100000")
            ledger.close()

    def test_submission_rate_defers_without_waiting_or_selling_held_positions(self):
        from native_adapter import NativeOrderRejected
        from strategies import AdaptivePolicy
        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True, clock=lambda: now)
            controller.port = type("Port", (), {"ready": True})()
            controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01", "ts_ns": int(now * 1e9)})
            payload = {"client_order_id": "rate-test", "symbol": "SPY", "side": "buy", "qty": "1", "limit_price": "100.03"}
            controller.before_submit(payload)
            for _ in range(180):
                self.assertEqual(ledger.request_budget(now, "submit"), 0)
            started = time.monotonic()
            with self.assertRaisesRegex(SafetyError, "submission_rate_deferred"):
                asyncio.run(controller.before_request("submit", "rate-test"))
            self.assertLess(time.monotonic() - started, .1)
            self.assertGreater(controller.defer_until, now)
            self.assertEqual(ledger.request_budget(now, "cancel"), 0)
            self.assertFalse(ledger.intents()[0].submit_attempted)
            ledger.close()

    def test_restart_ids_use_highest_reserved_sequence_and_native_config(self):
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy
        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            for sequence in (1, 2, 4):
                cid = f"adp-fixture-{sequence:07d}"
                ledger.reserve_intent(cid, "SPY", "buy", "1", "100.03",
                    quote=Quote("SPY", "100", "100.01", now), now=now,
                    market_open=True, session_close=now + 3600)
                ledger.mark_not_sent(cid, "fixture_unsent")
            _, _, policy = load_config(SOURCE / "config.json")
            strategy = AdaptiveStrategy(AdaptivePolicy(policy), ledger, "fixture")
            self.assertEqual(strategy.sequence, 4)
            self.assertEqual(str(strategy.strategy_id), "ADAPTIVE-001-A")
            ledger.close()

    def test_proven_broker_refusal_is_retained_without_poisoning_flat_reconciliation(self):
        from transport import RejectedSubmission
        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True)
            class RefusingPort:
                ready = True
                async def submit(self, payload):
                    controller.before_submit(payload)
                    await controller.before_request("submit", payload["client_order_id"])
                    raise RejectedSubmission(403)
            controller.port = controller.bind(RefusingPort())
            controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01", "ts_ns": time.time_ns()})
            payload = {"client_order_id": "refused-test", "symbol": "SPY", "side": "buy", "qty": "1", "limit_price": "100.03"}
            with self.assertRaises(RejectedSubmission):
                asyncio.run(controller.port.submit(payload))
            intent = ledger.intents()[0]
            self.assertEqual(intent.status, "broker_refused")
            self.assertTrue(intent.submit_attempted)
            proof = reconcile(ledger, {"complete": True, "orders": [], "positions": [], "account": {"cash": "100000"}}, "100000")
            self.assertEqual(proof["open_orders"], 0)
            ledger.close()

    def test_recovery_preflight_does_not_require_entry_cash_or_unrelated_quotes(self):
        config, _, _ = load_config(SOURCE / "config.json")
        now = time.time_ns()
        observation = {"account": {"status": "ACTIVE", "currency": "USD", "cash": "500", "equity": "1000",
                        "trading_blocked": False, "account_blocked": False, "trade_suspended_by_user": False},
                       "clock": {"timestamp_ns": now, "received_at_ns": now, "next_close_ns": now + 60_000_000_000, "is_open": True},
                       "positions": [{"symbol": "SPY", "qty": "1"}], "orders": [],
                       "assets": [{"symbol": "SPY", "status": "active", "tradable": True}], "quotes": []}
        validate_preflight(observation, config, require_open=True, allow_existing=True)
        with self.assertRaisesRegex(SafetyError, "account_not_ready"):
            validate_preflight(observation, config, require_open=True)


if __name__ == "__main__":
    unittest.main()
