"""Local cross-module tests: native engine, controller, ledger, synthetic port."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
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
    from runner import (Controller, reconcile, run_native, load_config, public_preflight,
                        validate_preflight, _honest_overnight_hold, trial_phase_and_exit_code)
    from safety import Ledger, Quote, RiskLimits, SafetyError
    from strategies import PolicyConfig
    from simulation import SimulatedPort
    NATIVE = True
except ImportError:
    NATIVE = False

# runner.py itself (and safety.py) import cleanly without nautilus_trader/alpaca
# (those are only imported lazily inside run_native/recovery paths), so the
# promotion-gate and credential-permission tests below run unconditionally.
import runner as runner_module
from runner import credentials, validate_preflight as validate_preflight_always
from safety import SafetyError as SafetyErrorAlways


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class IntegratedRunner(unittest.TestCase):
    def test_default_config_is_bounded(self):
        config, risk, policy = load_config(SOURCE / "config.json")
        self.assertEqual(risk.max_submits_per_minute, 180)
        self.assertEqual(policy.max_leverage, 1)
        self.assertEqual(len(policy.symbols), 24)

    def test_public_preflight_identifies_the_selected_feed(self):
        observation = {"account": {"status": "ACTIVE", "cash": "10000"},
                       "clock": {"is_open": True}, "assets": [], "positions": [],
                       "orders": [], "quotes": [], "quote_errors": {}}
        for name, expected in (("config.json", "iex"), ("config-sip.json", "sip")):
            with self.subTest(config=name):
                config, _, _ = load_config(SOURCE / name)
                summary = public_preflight(observation, config)
                self.assertEqual(summary["feed"], expected)
                self.assertEqual(summary["endpoint"], "https://paper-api.alpaca.markets")

    def test_frozen_sip_config_matches_the_iex_lane_except_the_feed(self):
        base, base_risk, base_policy = load_config(SOURCE / "config.json")
        sip, sip_risk, sip_policy = load_config(SOURCE / "config-sip.json")
        self.assertEqual(base["feed"], "iex")
        self.assertEqual(sip["feed"], "sip")
        self.assertEqual({k: v for k, v in base.items() if k != "feed"},
                         {k: v for k, v in sip.items() if k != "feed"})
        self.assertEqual(base_risk, sip_risk)
        self.assertEqual(base_policy, sip_policy)

    def test_unqualified_feed_is_refused_at_config_load(self):
        for value in ("otc", "delayed_sip", "IEX", "", None, 1):
            with self.subTest(feed=value), tempfile.TemporaryDirectory() as root:
                path = Path(root) / "config.json"
                data = json.loads((SOURCE / "config.json").read_text())
                data["feed"] = value
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError) as caught:
                    load_config(path)
                self.assertEqual(str(caught.exception), "unqualified_data_feed")

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

    def test_default_policy_run_native_never_calls_session_at_and_survives_2028(self):
        """S3 regression: last_session_kind used to be computed
        unconditionally, before the try block, on every paper run --
        including the default policy (extended_hours False, overnight_holds
        False), which never actually consults it (it is only read inside
        the `if session_policy["overnight_holds"]` boundary-receipt branch).
        session_at's calendar table only covers 2026 and exchange_calendars
        is not installed in this deployment, so any wall-clock year outside
        that table used to crash a default run immediately. Patch
        runner.time.time to a 2028 timestamp (see fixed_now below) and
        runner.session_at to raise if the default path ever calls it; the
        run must both complete without raising and never touch session_at."""
        import runner as runner_module

        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=1, cleanup_seconds=1, order_timeout_seconds=1)
        self.assertFalse(config.get("sessions", {}).get("extended_hours", False))
        with tempfile.TemporaryDirectory() as root:
            limits = RiskLimits(trial_seconds=1, cleanup_seconds=1)
            ledger = Ledger(Path(root) / "journal.db", limits)
            fixed_now = 1832677200.0  # 2028-01-28 13:00 UTC -- outside the 2026 calendar table
            ledger.start_trial(fixed_now)
            controller = Controller(ledger, fixed_now + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"), max_positions=6,
                                  warmup_samples=4, warmup_seconds=.06, sample_seconds=.02,
                                  rebalance_seconds=.02, min_hold_seconds=.05, max_hold_seconds=.4,
                                  cooldown_seconds=.05)
            port = SimulatedPort(controller, policy.symbols)
            controller.port = port

            def refuse_session_at(*args, **kwargs):
                raise AssertionError("default policy must never call session_at")

            with patch.object(runner_module.time, "time", return_value=fixed_now), \
                 patch.object(runner_module, "session_at", side_effect=refuse_session_at):
                result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                                "fixture", config, "100000"))
            self.assertIn(result["status"], ("passed", "completed_no_signals"))
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

    def test_native_strategy_operational_status_reflects_real_stop_file_ledger_halt_and_transport_health(self):
        """Gap-closing wiring: native_strategy.AdaptiveStrategy._operational_status
        must be built from the real STOP file, the real Ledger's halted_reason,
        and the real transport's health -- not fabricated. Uses a fake transport
        object exposing the same `.health` shape AlpacaPaperTransport does,
        since a real transport needs live sockets."""
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy, RegimeSelector, SelectorConfig
        now = time.time()

        class V1Spec:
            id = "adaptive_policy_v1"
            receipt_sha256 = "0" * 64
            sessions = ("regular",)
            regime_affinity = ()

            def propose(self, decision_inputs):
                return {}

        class FakeTransport:
            def __init__(self):
                self.health = {"frozen": False}

        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            _, _, policy_config = load_config(SOURCE / "config.json")
            selector = RegimeSelector(SelectorConfig())
            policy = AdaptivePolicy(policy_config, strategy_pool=(V1Spec(),), selector=selector)
            transport = FakeTransport()
            stop_file = Path(root) / "STOP"
            strategy = AdaptiveStrategy(policy, ledger, "fixture", transport=transport, stop_file=stop_file)

            status = strategy._operational_status(now)
            self.assertFalse(status.kill_switch)
            self.assertFalse(status.risk_halted)
            self.assertTrue(status.reconciled)
            self.assertFalse(status.transport_frozen)

            stop_file.write_text("stop")
            self.assertTrue(strategy._operational_status(now).kill_switch)

            ledger.freeze("fixture_risk_halt")
            after_halt = strategy._operational_status(now)
            self.assertTrue(after_halt.risk_halted)
            self.assertTrue(after_halt.reconciled)  # a real halt reason != "recovery_only"

            transport.health = {"frozen": True}
            self.assertTrue(strategy._operational_status(now).transport_frozen)
            ledger.close()

    def test_native_strategy_operational_status_recovery_only_is_reconciled_false_not_a_risk_halt(self):
        """D7/D8: the recovery_only branch of _operational_status was
        untested -- begin_recovery() sets halted_reason == "recovery_only",
        which must flip reconciled False without being reported as a
        risk_halted (that reason means "needs reconciliation", not a halt)."""
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy, RegimeSelector, SelectorConfig
        now = time.time()

        class V1Spec:
            id = "adaptive_policy_v1"
            receipt_sha256 = "0" * 64
            sessions = ("regular",)
            regime_affinity = ()

            def propose(self, decision_inputs):
                return {}

        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            ledger.begin_recovery(now)
            _, _, policy_config = load_config(SOURCE / "config.json")
            policy = AdaptivePolicy(policy_config, strategy_pool=(V1Spec(),),
                                    selector=RegimeSelector(SelectorConfig()))
            strategy = AdaptiveStrategy(policy, ledger, "fixture")
            status = strategy._operational_status(now)
            self.assertFalse(status.reconciled)
            self.assertFalse(status.risk_halted)
            ledger.close()

    def test_selector_liquidation_cancels_resting_entry_and_tags_the_exit_rotation_flatten(self):
        """D3: a liquidating selector decision must propagate into
        rebalance()'s own force_exit so a resting entry order is cancelled
        (cancel_expired(..., all_entries=True)), not merely block new
        entries. D4: the exit reason/order tag is the distinct
        "rotation_flatten", not the generic "trial_end". order_factory is a
        read-only Cython property on the real Strategy base and cannot be
        monkeypatched on the instance, so a thin subclass overrides it with a
        recording fake; submit_order/cancel_order are plain overridable
        instance attributes on real nautilus Strategy objects."""
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy, SelectorConfig
        from selector import ACTIVE, FLATTEN_BEFORE_SWITCH, OperationalStatus, SelectionDecision

        class V1Spec:
            id = "adaptive_policy_v1"
            receipt_sha256 = "0" * 64
            sessions = ("regular",)
            regime_affinity = ()

            def propose(self, decision_inputs):
                return {}

        class FakeSelector:
            def __init__(self, decision):
                self.decision = decision
                self.config = SelectorConfig(portfolio_transition_policy=FLATTEN_BEFORE_SWITCH)

            def decide(self, decision_inputs):
                return self.decision

        class FakeOrderFactory:
            def __init__(self):
                self.calls = []

            def limit(self, instrument_id, side, quantity, price, *, time_in_force, client_order_id, tags):
                self.calls.append({"instrument_id": str(instrument_id), "side": side,
                                   "tags": list(tags), "client_order_id": str(client_order_id)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            quote = Quote("AAPL", "100", "100.01", now)
            ledger.reserve_intent("buy-1", "AAPL", "buy", "1", "100.01", quote=quote, now=now,
                                  market_open=True, session_close=now + 3600)
            ledger.record_order("buy-1", "broker-buy-1", "filled", "1", "100", timestamp=now)

            _, _, policy_config = load_config(SOURCE / "config.json")
            decision = SelectionDecision(timestamp=now, prior_state=ACTIVE, new_state=ACTIVE,
                                         regime="trend", confidence=1.0, advantage_bps=50.0,
                                         incumbent_id="adaptive_policy_v1", candidate_id="adaptive_policy_v1",
                                         reason_codes=("switched",), blocked_by=(), liquidate=True)
            policy = AdaptivePolicy(policy_config, strategy_pool=(V1Spec(),), selector=FakeSelector(decision))
            strategy = FakeStrategy(policy, ledger, "fixture")
            strategy._fake_order_factory = FakeOrderFactory()
            submitted = []
            strategy.submit_order = submitted.append
            cancelled = []
            strategy.cancel_order = cancelled.append
            strategy.started = True
            strategy.enabled = True

            policy.observe("AAPL", 100.995, 101.005, now)
            resting_id = "adp-fixture-0000099"
            strategy.pending[resting_id] = {"symbol": "MSFT", "side": "buy", "created": now}

            strategy.rebalance(now + .01, force_exit=False)

            # D3: the resting buy was cancelled (propagated liquidate -> force_exit
            # -> cancel_expired(..., all_entries=True)), not left pending.
            self.assertEqual([str(c) for c in cancelled], [resting_id])
            self.assertTrue(strategy.pending[resting_id]["cancel_requested"])

            # D4: the held AAPL position was exited with the distinct
            # "rotation_flatten" reason, carried into the order tags.
            self.assertEqual(len(strategy._fake_order_factory.calls), 1)
            call = strategy._fake_order_factory.calls[0]
            self.assertEqual(call["side"].name if hasattr(call["side"], "name") else call["side"], "SELL")
            self.assertIn("strategy=rotation_flatten", call["tags"])
            self.assertIn("reason=rotation_flatten", call["tags"])
            self.assertEqual(len(submitted), 1)
            ledger.close()

    def test_selector_liquidation_cancels_only_resting_entries_not_resting_sells(self):
        """R1 regression: rebalance()'s liquidating branch used to call
        cancel_expired(now, 0, all_entries=True); with timeout=0 the
        cancel_expired timeout clause (`now - created >= timeout`) is true
        for every resting order regardless of side, so a resting SELL
        (e.g. an exit already working before the flatten) was cancelled too.
        Only resting entry (buy) orders may be cancelled here; a resting
        sell must survive untouched."""
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy, SelectorConfig
        from selector import FLATTEN_BEFORE_SWITCH, SelectionDecision, ACTIVE

        class V1Spec:
            id = "adaptive_policy_v1"
            receipt_sha256 = "0" * 64
            sessions = ("regular",)
            regime_affinity = ()

            def propose(self, decision_inputs):
                return {}

        class FakeSelector:
            def __init__(self, decision):
                self.decision = decision
                self.config = SelectorConfig(portfolio_transition_policy=FLATTEN_BEFORE_SWITCH)

            def decide(self, decision_inputs):
                return self.decision

        class FakeOrderFactory:
            def __init__(self):
                self.calls = []

            def limit(self, instrument_id, side, quantity, price, *, time_in_force, client_order_id, tags):
                self.calls.append({"instrument_id": str(instrument_id), "side": side,
                                   "tags": list(tags), "client_order_id": str(client_order_id)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            _, _, policy_config = load_config(SOURCE / "config.json")
            decision = SelectionDecision(timestamp=now, prior_state=ACTIVE, new_state=ACTIVE,
                                         regime="trend", confidence=1.0, advantage_bps=50.0,
                                         incumbent_id="adaptive_policy_v1", candidate_id="adaptive_policy_v1",
                                         reason_codes=("switched",), blocked_by=(), liquidate=True)
            policy = AdaptivePolicy(policy_config, strategy_pool=(V1Spec(),), selector=FakeSelector(decision))
            strategy = FakeStrategy(policy, ledger, "fixture")
            strategy._fake_order_factory = FakeOrderFactory()
            strategy.submit_order = lambda order: None
            cancelled = []
            strategy.cancel_order = cancelled.append
            strategy.started = True
            strategy.enabled = True

            resting_buy_id = "adp-fixture-0000001"
            resting_sell_id = "adp-fixture-0000002"
            strategy.pending[resting_buy_id] = {"symbol": "MSFT", "side": "buy", "created": now}
            strategy.pending[resting_sell_id] = {"symbol": "IBM", "side": "sell", "created": now}

            strategy.rebalance(now + .01, force_exit=False)

            cancelled_ids = {str(c) for c in cancelled}
            self.assertEqual(cancelled_ids, {resting_buy_id})
            self.assertTrue(strategy.pending[resting_buy_id]["cancel_requested"])
            self.assertNotIn("cancel_requested", strategy.pending[resting_sell_id])
            ledger.close()

    def test_operational_status_against_simulated_port_health_never_keyerrors(self):
        """R2 regression: _operational_status used to read
        self.transport.health["frozen"] unconditionally, which KeyErrors
        against SimulatedPort's health dict (only ready/simulation/reason,
        no "frozen" key). Verify the defensive read across the port's
        actual lifecycle: not-yet-started (ready False -> frozen True),
        started (ready True, no reason -> frozen False), and frozen via
        freeze_health (reason set -> frozen True) -- and that rotation
        (selector configured) can call it through run_native-like wiring
        without raising."""
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy, RegimeSelector, SelectorConfig
        from simulation import SimulatedPort

        class V1Spec:
            id = "adaptive_policy_v1"
            receipt_sha256 = "0" * 64
            sessions = ("regular",)
            regime_affinity = ()

            def propose(self, decision_inputs):
                return {}

        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True, clock=lambda: now)
            port = SimulatedPort(controller, ("SPY",))
            controller.port = port
            _, _, policy_config = load_config(SOURCE / "config.json")
            policy = AdaptivePolicy(policy_config, strategy_pool=(V1Spec(),),
                                    selector=RegimeSelector(SelectorConfig()))
            strategy = AdaptiveStrategy(policy, ledger, "fixture", transport=port)

            # Not started yet: health == {"ready": False, "simulation": True}.
            status = strategy._operational_status(now)
            self.assertTrue(status.transport_frozen)

            async def exercise():
                await port.start(lambda q: None, lambda o: None)
                started_status = strategy._operational_status(now)
                port.freeze_health("fixture_reason")
                frozen_status = strategy._operational_status(now)
                if port.task:
                    port.task.cancel()
                    await asyncio.gather(port.task, return_exceptions=True)
                return started_status, frozen_status
            started_status, frozen_status = asyncio.run(exercise())
            self.assertFalse(started_status.transport_frozen)
            self.assertTrue(frozen_status.transport_frozen)
            ledger.close()

    def test_run_native_uses_the_load_config_validated_registry_not_the_default(self):
        """R5 regression: run_native used to reload SOURCE/registry.json
        unconditionally instead of using the registry load_config already
        validated (and a registry_path override may point elsewhere).
        Build a registry_path override whose only entry is disabled; the
        default (shipped) registry.json entry is enabled, so if run_native
        fell back to it, strategy_pool_and_selector would build a non-empty
        pool and no error would occur. Verify run_native instead raises for
        the *overridden* registry's empty eligible pool -- proof it used
        the threaded, already-validated entries, not the default file."""
        import hashlib
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            module_bytes = b"x = 1\n"
            (root / "mod.py").write_bytes(module_bytes)
            (root / "source-hashes.json").write_text(
                json.dumps({"mod.py": hashlib.sha256(module_bytes).hexdigest()}))
            receipt_bytes = b"{}"
            (root / "receipt.json").write_bytes(receipt_bytes)
            entry = {"id": "override_disabled", "module": "mod", "receipt_path": "receipt.json",
                     "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                     "evidence_class": "SYN", "sessions": ["regular"], "enabled": False}
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps({"schema_version": 1, "strategies": [entry]}))

            config, _, policy_config = load_config(SOURCE / "config.json", registry_path=registry_path)
            self.assertEqual(config["_registry_path"], str(registry_path))
            self.assertEqual([e["id"] for e in config["_registry_entries"]], ["override_disabled"])
            config["rotation"] = {"enabled": True, "allow_synthetic": True}

            with self.assertRaises(ValueError) as caught:
                asyncio.run(run_native(object(), policy_config, [], "fixture", config, "100000"))
            self.assertEqual(str(caught.exception), "rotation_enabled_with_no_eligible_strategy")

    def test_honest_overnight_hold_true_only_for_a_genuine_reconciled_boundary_end(self):
        """S1: a non-flat end under overnight_holds must only be treated as
        a legitimate, resumable hold when the run actually ended at a real
        session boundary (POST/CLOSED), reconciliation succeeded, and there
        were no adapter errors or risk halt -- not merely because
        overnight_holds is enabled and the ledger happens to be non-flat."""
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        post_ts = datetime(2026, 3, 10, 18, 0, tzinfo=ny).astimezone(timezone.utc).timestamp()
        rth_ts = datetime(2026, 3, 10, 12, 0, tzinfo=ny).astimezone(timezone.utc).timestamp()
        session_policy = {"overnight_holds": True, "extended_hours": True}

        clean_outcome = {"reconciliation": {"positions": 1, "open_orders": 0},
                         "adapter_errors": [], "accounting": {"halted_reason": None}}
        self.assertTrue(_honest_overnight_hold(clean_outcome, session_policy, post_ts))

    def test_honest_overnight_hold_false_for_mid_rth_unreconciled_error_or_halt(self):
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        post_ts = datetime(2026, 3, 10, 18, 0, tzinfo=ny).astimezone(timezone.utc).timestamp()
        rth_ts = datetime(2026, 3, 10, 12, 0, tzinfo=ny).astimezone(timezone.utc).timestamp()
        session_policy = {"overnight_holds": True, "extended_hours": True}
        clean_outcome = {"reconciliation": {"positions": 1, "open_orders": 0},
                         "adapter_errors": [], "accounting": {"halted_reason": None}}

        # Still mid-RTH (duration_seconds elapsed early with positions
        # still open) -- no real session boundary was reached.
        self.assertFalse(_honest_overnight_hold(clean_outcome, session_policy, rth_ts))
        # At a real boundary, but reconciliation never completed.
        unreconciled = {**clean_outcome, "reconciliation": None}
        self.assertFalse(_honest_overnight_hold(unreconciled, session_policy, post_ts))
        # At a real boundary and reconciled, but an adapter error occurred.
        errored = {**clean_outcome, "adapter_errors": ["some_error"]}
        self.assertFalse(_honest_overnight_hold(errored, session_policy, post_ts))
        # At a real boundary and reconciled, but the ledger is halted.
        halted = {**clean_outcome, "accounting": {"halted_reason": "gross_loss_cap_reached"}}
        self.assertFalse(_honest_overnight_hold(halted, session_policy, post_ts))
        # overnight_holds itself disabled: never a hold regardless of the rest.
        self.assertFalse(_honest_overnight_hold(clean_outcome, {"overnight_holds": False}, post_ts))

    def test_run_native_status_mid_rth_non_flat_end_is_needs_attention_not_held_overnight(self):
        """D1: run_native's own status computation used to set
        "held_overnight" purely from `overnight_holds and reconciled and
        non-flat`, with no boundary test -- so an end _honest_overnight_hold
        would reject (e.g. mid-RTH, not an actual POST/CLOSED boundary)
        could still be recorded as "held_overnight" (exit 0, resumable
        phase). run_native's status decision is factored into
        _run_native_status precisely so this real production code path
        (the exact function run_native calls, not a re-implementation) is
        directly testable without driving a full native node -- SimulatedPort
        fills every submitted order synchronously and immediately, so there
        is no way to leave a position "genuinely stuck open" mid-run through
        the full native pipeline to exercise this branch. Confirm a
        reconciled, error/halt-free, non-flat outcome at a real RTH instant
        (not POST/CLOSED) is "needs_attention", not "held_overnight" -- and
        that trial_phase_and_exit_code, the same single authority main()
        uses, turns that into phase "needs_attention" and exit code 3."""
        from datetime import datetime, timezone as _tz
        from zoneinfo import ZoneInfo
        import runner as runner_module
        rth_ts = datetime(2026, 3, 10, 12, 0, tzinfo=ZoneInfo("America/New_York")) \
            .astimezone(_tz.utc).timestamp()  # a real RTH instant, not a POST/CLOSED boundary
        session_policy = {"extended_hours": True, "overnight_holds": True}
        reconciliation = {"positions_match": True, "cash_match": True, "cash_delta_usd": "0",
                          "open_orders": 0, "positions": 1}  # non-flat: one reconciled position
        outcome = {"reconciliation": reconciliation, "adapter_errors": [],
                  "accounting": {"halted_reason": None}}

        status = runner_module._run_native_status(reconciliation, [], 0, outcome, session_policy, rth_ts)
        self.assertEqual(status, "needs_attention")

        # Sanity: the identical inputs, but at a real POST-session instant,
        # correctly ARE a genuine hold -- proving the RTH case above is
        # refused specifically for the boundary reason, not some other
        # field in `outcome`/`reconciliation`.
        post_ts = datetime(2026, 3, 10, 18, 0, tzinfo=ZoneInfo("America/New_York")) \
            .astimezone(_tz.utc).timestamp()
        held_status = runner_module._run_native_status(reconciliation, [], 0, outcome, session_policy, post_ts)
        self.assertEqual(held_status, "held_overnight")

        outcome["status"] = status
        outcome["flat"] = False
        phase, exit_code = trial_phase_and_exit_code(outcome)
        self.assertEqual(phase, "needs_attention")
        self.assertEqual(exit_code, 3)

        outcome["status"] = held_status
        phase2, exit_code2 = trial_phase_and_exit_code(outcome)
        self.assertEqual(phase2, "held_overnight")
        self.assertEqual(exit_code2, 0)

    def test_forced_recovery_that_fails_to_flatten_cannot_report_held_overnight_or_exit_0(self):
        """D4 (round 6): main()'s forced-recovery branch used to set
        outcome["flat"] = recovery["flat"] but never touch
        outcome["status"] -- a forced liquidation that failed to actually
        flatten the account (recovery["flat"]=False) left whatever status
        run_native's OWN, now-stale, pre-recovery snapshot had (here:
        "held_overnight", the exact case the review flagged) still exposed
        to trial_phase_and_exit_code, reporting exit 0/resumable phase for
        a genuinely non-flat account. _apply_forced_recovery_outcome is
        the exact function main() now calls for this merge."""
        import runner as runner_module

        stale_outcome = {"status": "held_overnight", "flat": False, "native_fill_events": 0}
        failed_recovery = {"status": "needs_attention", "flat": False, "errors": ["stuck_order"],
                           "positions": [{"symbol": "AAPL", "qty": "1"}], "unresolved_orders": []}

        merged = runner_module._apply_forced_recovery_outcome(stale_outcome, failed_recovery)
        self.assertEqual(merged["status"], "needs_attention")  # not the stale "held_overnight"
        self.assertFalse(merged["flat"])
        self.assertIs(merged["recovery"], failed_recovery)

        phase, exit_code = trial_phase_and_exit_code(merged)
        self.assertEqual(phase, "needs_attention")
        self.assertEqual(exit_code, 3)  # not 0 -- the account is genuinely non-flat

    def test_forced_recovery_that_succeeds_from_an_equally_good_pre_status_reports_passed_and_exit_0(self):
        """A forced liquidation that DOES actually flatten the account,
        starting from a pre-recovery status no worse than "passed"
        (severity-tied here), correctly reports "passed"/flat/exit 0."""
        import runner as runner_module

        pre_status_outcome = {"status": "passed", "flat": False, "native_fill_events": 2}
        successful_recovery = {"status": "passed", "flat": True, "errors": [],
                               "positions": [], "unresolved_orders": []}

        merged = runner_module._apply_forced_recovery_outcome(pre_status_outcome, successful_recovery)
        self.assertEqual(merged["status"], "passed")
        self.assertTrue(merged["flat"])
        self.assertEqual(merged["status_before_recovery"], "passed")

        phase, exit_code = trial_phase_and_exit_code(merged)
        self.assertEqual(phase, "finished")
        self.assertEqual(exit_code, 0)

    # -- D1 (round 7): monotone composition -- never upgrade a genuinely
    #    failed pre-recovery status just because recovery then succeeds --

    def test_successful_recovery_does_not_upgrade_a_genuinely_failed_pre_status(self):
        """The exact bug D1 fixes: round 6's unconditional overwrite let a
        forced liquidation that happens to SUCCEED (recovery status
        "passed") silently upgrade a pre-recovery status of
        "needs_attention" (a REAL mid-RTH error/halt/reconciliation
        mismatch run_native itself already detected) to "passed"/exit 0 --
        masking the original failure entirely. The composed status must
        stay the worse of the two: "needs_attention"."""
        import runner as runner_module

        failed_outcome = {"status": "needs_attention", "flat": False, "native_fill_events": 0,
                          "adapter_errors": ["some_adapter_error"]}
        successful_recovery = {"status": "passed", "flat": True, "errors": [],
                               "positions": [], "unresolved_orders": []}

        merged = runner_module._apply_forced_recovery_outcome(failed_outcome, successful_recovery)
        self.assertEqual(merged["status"], "needs_attention")  # NOT upgraded to "passed"
        self.assertTrue(merged["flat"])  # flat is still taken from the real recovery outcome
        self.assertEqual(merged["status_before_recovery"], "needs_attention")
        self.assertIs(merged["recovery"], successful_recovery)

        phase, exit_code = trial_phase_and_exit_code(merged)
        # D5 (round 8): phase is derived from status FIRST, not flat
        # first -- flat=True does NOT yield phase "finished" here, since
        # the composed status is the sticky "needs_attention". This is
        # the exact flattened-failed case D5 fixes: a failed session that
        # got tidied up by the forced liquidation must still surface as
        # needs_attention (and exit 3), not silently as "finished".
        self.assertEqual(phase, "needs_attention")
        self.assertEqual(exit_code, 3)

        # D5 (round 8): reproduce main()'s own resume guard condition
        # (see runner.py, around the `resumable_hold`/SafetyError check
        # just after metadata_path is loaded) against this exact
        # persisted phase, for a next invocation NOT using --command
        # recover. Before this round's fix, phase would have been
        # "finished" here (flat-first), so `previous_metadata.get("phase")
        # != "finished"` would be False and the guard would silently NOT
        # fire for a session that was, underneath, a genuine failure --
        # letting the next invocation start a fresh trial over an account
        # state main() itself still considers unresolved. With phase now
        # "needs_attention", the guard correctly fires (would raise
        # SafetyError("existing_trial_requires_explicit_recovery")).
        previous_metadata = {"phase": phase}
        session_policy_overnight = {"overnight_holds": True}
        resumable_hold = (previous_metadata.get("phase") == "held_overnight"
                          and session_policy_overnight["overnight_holds"])
        guard_fires = (previous_metadata.get("phase") != "finished" and not resumable_hold)
        self.assertTrue(guard_fires)

    def test_failed_recovery_downgrades_an_optimistic_pre_status(self):
        """The mirror (already covered in round 6, re-asserted under the
        new monotone composition): a forced liquidation that FAILS to
        flatten the account must downgrade an optimistic pre-recovery
        status (here: "held_overnight") to "needs_attention"."""
        import runner as runner_module

        held_outcome = {"status": "held_overnight", "flat": False, "native_fill_events": 0}
        failed_recovery = {"status": "needs_attention", "flat": False, "errors": ["stuck_order"],
                           "positions": [{"symbol": "AAPL", "qty": "1"}], "unresolved_orders": []}

        merged = runner_module._apply_forced_recovery_outcome(held_outcome, failed_recovery)
        self.assertEqual(merged["status"], "needs_attention")
        self.assertFalse(merged["flat"])

        phase, exit_code = trial_phase_and_exit_code(merged)
        self.assertEqual(phase, "needs_attention")
        self.assertEqual(exit_code, 3)

    def test_non_sticky_pre_status_always_defers_to_recoverys_own_status(self):
        """D6 (round 8): the single severity table (round 7) is replaced
        by an explicit two-tier rule -- there is no longer a "tie" concept
        at all for a non-failed pre-status. A pre-recovery status of
        "completed_no_signals" (not sticky) is fully replaced by
        recovery's own "passed", not "kept" because the two used to rank
        at the same severity tier under the old table."""
        import runner as runner_module

        pre_outcome = {"status": "completed_no_signals", "flat": False, "native_fill_events": 0}
        recovery = {"status": "passed", "flat": True, "errors": [], "positions": [], "unresolved_orders": []}

        merged = runner_module._apply_forced_recovery_outcome(pre_outcome, recovery)
        self.assertEqual(merged["status"], "passed")  # not "completed_no_signals"
        self.assertEqual(merged["status_before_recovery"], "completed_no_signals")

        phase, exit_code = trial_phase_and_exit_code(merged)
        self.assertEqual(phase, "finished")
        self.assertEqual(exit_code, 0)

    def test_held_overnight_pre_status_does_not_survive_a_successful_flatten(self):
        """D6 (round 8): the exact bug in round 7's severity table --
        "held_overnight" (2) ranked ABOVE "passed"/"completed_no_signals"
        (1), so a successful forced liquidation (recovery status "passed")
        following a "held_overnight" pre-status kept reporting
        "held_overnight" with flat=True, instead of recovery's own
        "passed". Forcing a flatten at all already means this run is no
        longer an overnight hold; "held_overnight" is not sticky and must
        always defer to recovery's own status."""
        import runner as runner_module

        held_outcome = {"status": "held_overnight", "flat": False, "native_fill_events": 0}
        successful_recovery = {"status": "passed", "flat": True, "errors": [],
                               "positions": [], "unresolved_orders": []}

        merged = runner_module._apply_forced_recovery_outcome(held_outcome, successful_recovery)
        self.assertEqual(merged["status"], "passed")  # not "held_overnight"
        self.assertTrue(merged["flat"])
        self.assertEqual(merged["status_before_recovery"], "held_overnight")

        phase, exit_code = trial_phase_and_exit_code(merged)
        self.assertEqual(phase, "finished")
        self.assertEqual(exit_code, 0)

    def test_failed_pre_status_stays_sticky_even_when_recovery_also_fails(self):
        """D6 (round 8): both tiers of the sticky rule are exercised by a
        single case -- a "failed" (not just "needs_attention") pre-status
        must also stay sticky."""
        import runner as runner_module

        failed_outcome = {"status": "failed", "flat": False, "native_fill_events": 0}
        failed_recovery = {"status": "needs_attention", "flat": False, "errors": ["stuck_order"],
                           "positions": [{"symbol": "AAPL", "qty": "1"}], "unresolved_orders": []}

        merged = runner_module._apply_forced_recovery_outcome(failed_outcome, failed_recovery)
        self.assertEqual(merged["status"], "failed")
        self.assertFalse(merged["flat"])

        phase, exit_code = trial_phase_and_exit_code(merged)
        self.assertEqual(phase, "needs_attention")
        self.assertEqual(exit_code, 3)


def _paper_ready_observation(now_ns, symbols=("SPY",)):
    return {"account": {"status": "ACTIVE", "currency": "USD", "cash": "10000", "equity": "30000",
                        "trading_blocked": False, "account_blocked": False, "trade_suspended_by_user": False},
            "clock": {"timestamp_ns": now_ns, "received_at_ns": now_ns, "next_close_ns": now_ns + 3600_000_000_000,
                      "is_open": True},
            "positions": [], "orders": [],
            "assets": [{"symbol": s, "status": "active", "tradable": True} for s in symbols],
            "quotes": [{"symbol": s, "ts_ns": now_ns} for s in symbols]}


def _paper_ready_config(symbols=("SPY",)):
    # The session-policy keys mirror the shipped config.json defaults: main()
    # validates the session policy of the config load_config returned, and
    # the gate-wiring tests patch load_config with this fixture.
    return {"capital_usd": "10000", "duration_seconds": 60, "cleanup_seconds": 10,
            "symbols": list(symbols), "benchmarks": list(symbols), "quote_max_age_seconds": 5,
            "feed": "iex", "regular_session_only": True, "extended_hours_enabled": False,
            "sessions": {"extended_hours": False, "overnight_holds": False, "overnight_gross_multiple": "1.0"}}


def _full_gate_result(*, status="pass", row_count=1, checks_status="pass", input_sha256=None):
    """A gate-result.json body with the full contract `_check_promotion_gate`
    now requires (status, input_sha256, row_count, checks, versions,
    checked_at) -- shaped like a real `promotion_gate.py` output, not the
    bare {status, input_sha256} pairs the pre-fix runtime accepted."""
    return {
        "status": status,
        "input_sha256": input_sha256,
        "row_count": row_count,
        "checks": [{"name": name, "status": checks_status, "detail": "ok"}
                   for name in sorted(runner_module._GATE_CHECK_NAMES)],
        "versions": {"pandera": "0.33.1"},
        "checked_at": "2026-09-22T00:00:00+00:00",
    }


class PromotionGatePreflight(unittest.TestCase):
    """`mode="paper"` requires a complete, fully-passing, hash-matched
    promotion-gate result; `mode=None` (every pre-existing call) is
    unaffected. Does not require the pinned nautilus_trader/alpaca runtime:
    runner.py imports those lazily."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.snapshot = self.root / "snapshot.csv"
        self.snapshot.write_text("symbol\nSPY\n")
        self.snapshot_hash = hashlib.sha256(self.snapshot.read_bytes()).hexdigest()
        self.now_ns = time.time_ns()
        self.observation = _paper_ready_observation(self.now_ns)
        self.config = _paper_ready_config()

    def tearDown(self):
        self.tmp.cleanup()

    def _call(self, **gate_kwargs):
        return validate_preflight_always(self.observation, self.config, require_open=True,
                                          mode="paper", **gate_kwargs)

    def _write_gate(self, **fields):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(**fields)))
        return gate_path

    def _write_raw_gate(self, body):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(body))
        return gate_path

    def test_complete_gate_result_is_accepted(self):
        gate_path = self._write_gate(input_sha256=self.snapshot_hash)
        self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_gate_result_without_the_named_checks_is_incomplete(self):
        # The blind review's reproduction: an unnamed passing check, null versions and
        # checked_at, matching hash of a header-only CSV.
        body = {"status": "pass", "input_sha256": self.snapshot_hash, "row_count": 1,
                "checks": [{"status": "pass"}], "versions": None, "checked_at": None}
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
            self._call(gate_result_path=self._write_raw_gate(body), snapshot_path=self.snapshot)

    def test_gate_result_missing_one_named_check_is_incomplete(self):
        body = _full_gate_result(input_sha256=self.snapshot_hash)
        body["checks"] = [c for c in body["checks"] if c["name"] != "volume_integral_non_negative"]
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
            self._call(gate_result_path=self._write_raw_gate(body), snapshot_path=self.snapshot)

    def test_gate_result_with_duplicate_or_unknown_check_is_incomplete(self):
        for extra in ({"name": "rows_present", "status": "pass"}, {"name": "made_up_check", "status": "pass"}):
            body = _full_gate_result(input_sha256=self.snapshot_hash)
            body["checks"].append(extra)
            with self.subTest(extra=extra["name"]):
                with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
                    self._call(gate_result_path=self._write_raw_gate(body), snapshot_path=self.snapshot)

    def test_non_string_check_name_is_refused_cleanly(self):
        body = _full_gate_result(input_sha256=self.snapshot_hash)
        body["checks"][0] = {"name": ["rows_present"], "status": "pass"}
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
            self._call(gate_result_path=self._write_raw_gate(body), snapshot_path=self.snapshot)

    def test_naive_or_date_only_checked_at_and_empty_versions_are_incomplete(self):
        for field, value in (("checked_at", "2026-09-22"), ("checked_at", "20260922"),
                             ("checked_at", "2026-09-22T10:00:00"), ("versions", {"pandera": None}),
                             ("versions", {"pandera": ""})):
            body = _full_gate_result(input_sha256=self.snapshot_hash)
            body[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
                    self._call(gate_result_path=self._write_raw_gate(body), snapshot_path=self.snapshot)

    def test_csv_row_count_must_match_the_snapshot_rows(self):
        gate_path = self._write_gate(input_sha256=self.snapshot_hash, row_count=4)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_mismatch"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_unmapped_failures_entry_is_reported_as_such(self):
        body = _full_gate_result(input_sha256=self.snapshot_hash, status="fail")
        body["checks"].append({"name": "unmapped_failures", "status": "fail",
                               "detail": "unrecognized pandera check identifiers ['not_nullable']"})
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_unmapped_failures"):
            self._call(gate_result_path=self._write_raw_gate(body), snapshot_path=self.snapshot)

    def test_null_or_empty_versions_and_checked_at_are_incomplete(self):
        for field, value in (("versions", None), ("versions", {}), ("checked_at", None),
                             ("checked_at", ""), ("checked_at", "not-a-time")):
            body = _full_gate_result(input_sha256=self.snapshot_hash)
            body[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
                    self._call(gate_result_path=self._write_raw_gate(body), snapshot_path=self.snapshot)

    def test_runner_check_names_match_the_gate_module(self):
        import ast
        source = (Path(runner_module.__file__).resolve().parents[1] / "data" / "promotion_gate.py").read_text()
        names = None
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "CHECK_NAMES" for t in node.targets):
                names = ast.literal_eval(node.value)
        self.assertIsNotNone(names, "promotion_gate.CHECK_NAMES not found")
        self.assertEqual(frozenset(names), runner_module._GATE_CHECK_NAMES)

    def test_mode_none_is_unaffected_by_missing_gate_arguments(self):
        # Every pre-existing preflight/recover call site omits mode/gate args.
        validate_preflight_always(self.observation, self.config, require_open=True)

    def test_missing_gate_result_path_raises_promotion_gate_missing(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(snapshot_path=self.snapshot)

    def test_missing_snapshot_path_raises_promotion_gate_missing(self):
        gate_path = self._write_gate(input_sha256=self.snapshot_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=gate_path)

    def test_nonexistent_gate_result_file_raises_promotion_gate_missing(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=self.root / "does-not-exist.json", snapshot_path=self.snapshot)

    def test_unparseable_gate_result_file_raises_promotion_gate_missing(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text("not json")
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_failing_gate_status_raises_promotion_gate_failed(self):
        gate_path = self._write_gate(status="fail", input_sha256=self.snapshot_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_failed$"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_mismatched_hash_raises_promotion_gate_mismatch(self):
        gate_path = self._write_gate(input_sha256="0" * 64)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_mismatch"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_passing_matched_gate_allows_preflight_to_proceed(self):
        gate_path = self._write_gate(input_sha256=self.snapshot_hash)
        close = self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)
        self.assertEqual(close, (self.now_ns + 3600_000_000_000) / 1e9)

    def test_passing_gate_still_enforces_ordinary_account_checks(self):
        gate_path = self._write_gate(input_sha256=self.snapshot_hash)
        self.observation["account"]["trading_blocked"] = True
        with self.assertRaisesRegex(SafetyErrorAlways, "account_not_ready"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    # --- Regression (finding 3): the pre-fix _check_promotion_gate only ever
    # read gate["status"] and gate["input_sha256"], so a gate result declaring
    # row_count=0 or carrying a failed check but a "pass" top-level status
    # (and a matching hash) was wrongly accepted. ---

    def test_gate_result_missing_required_keys_raises_promotion_gate_incomplete(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps({"status": "pass", "input_sha256": self.snapshot_hash}))
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_gate_result_with_empty_checks_list_raises_promotion_gate_incomplete(self):
        gate_path = self.root / "gate-result.json"
        body = _full_gate_result(input_sha256=self.snapshot_hash)
        body["checks"] = []
        gate_path.write_text(json.dumps(body))
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_incomplete"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_gate_result_with_zero_row_count_raises_promotion_gate_empty(self):
        """The exact review-finding scenario: top-level status "pass", hash
        matches, but row_count is 0."""
        gate_path = self._write_gate(row_count=0, input_sha256=self.snapshot_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_empty"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_gate_result_with_a_failed_check_raises_promotion_gate_failed_check(self):
        """The other review-finding scenario: top-level status "pass", hash
        matches, but one of the named checks reports status "fail"."""
        gate_path = self._write_gate(checks_status="fail", input_sha256=self.snapshot_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_failed_check"):
            self._call(gate_result_path=gate_path, snapshot_path=self.snapshot)

    def test_snapshot_with_unaccepted_extension_raises_promotion_gate_missing(self):
        """`--snapshot` must reference a file the gate itself could accept
        (`.csv`/`.parquet`); a `.json` config file (or any other extension)
        can never legitimately be the gated snapshot."""
        bogus_snapshot = self.root / "config.json"
        bogus_snapshot.write_text('{"symbols": ["SPY"]}')
        bogus_hash = hashlib.sha256(bogus_snapshot.read_bytes()).hexdigest()
        gate_path = self._write_gate(input_sha256=bogus_hash)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=gate_path, snapshot_path=bogus_snapshot)

    def test_snapshot_path_that_is_a_directory_raises_promotion_gate_missing(self):
        directory_snapshot = self.root / "snapshot-dir.csv"
        directory_snapshot.mkdir()
        gate_path = self._write_gate(input_sha256="0" * 64)
        with self.assertRaisesRegex(SafetyErrorAlways, "promotion_gate_missing"):
            self._call(gate_result_path=gate_path, snapshot_path=directory_snapshot)


class MainCommandGateWiring(unittest.TestCase):
    """Regression: review found `python3 runner.py paper ...` bypassed the
    promotion gate entirely -- `main()` registered no `--gate-result`/
    `--snapshot` arguments and its `paper`/`recover` call site omitted the
    new `mode`/`gate_result_path`/`snapshot_path` kwargs, so `validate_preflight`
    always ran with `mode=None`. These tests drive `runner.main()` itself
    (mocking only the network-touching `preflight` call and the
    native-runtime entry past the gate check) to prove the CLI wiring, not
    just the already-covered `validate_preflight` unit behavior."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env_file = self.root / "paper.env"
        self.env_file.write_text("APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")
        os.chmod(self.env_file, 0o600)
        self.config_file = self.root / "config.json"
        self.config_file.write_text("{}")
        self.output = self.root / "output.json"
        self.snapshot = self.root / "universe.csv"
        self.snapshot.write_text("symbol\nSPY\n")
        self.snapshot_hash = hashlib.sha256(self.snapshot.read_bytes()).hexdigest()
        self.now_ns = time.time_ns()
        self.observation = _paper_ready_observation(self.now_ns)
        self.observation["account_identity_sha256"] = "fixture-account"
        self.config = _paper_ready_config()

    def tearDown(self):
        self.tmp.cleanup()

    def _argv(self, command, extra):
        return ["runner.py", command, "--env-file", str(self.env_file), "--config", str(self.config_file),
                "--output", str(self.output), "--state-root", str(self.root / "state"), *extra]

    def _run_main(self, command, extra=()):
        """Patches every dependency `main()` reaches before/at the gate check
        (config loading, credential parsing, the network preflight call) and
        makes `account_lock_fingerprint` -- the first thing `main()` touches
        immediately *after* a passing gate check -- raise a sentinel so the
        test can tell "gate check passed and execution continued" apart from
        "gate check raised/returned" without needing the pinned native
        runtime or an SQLite ledger. Returns `(sentinel, code, raised)`:
        `code` is `main()`'s return value (`None` if it raised instead), and
        `raised` is the exception instance if one propagated out of `main()`."""
        sentinel = RuntimeError("reached_post_gate_execution")
        with patch.object(sys, "argv", self._argv(command, extra)), \
             patch.object(runner_module, "load_config", return_value=(self.config, None, None)), \
             patch.object(runner_module, "credentials", return_value=("fixture-key", "fixture-secret")), \
             patch.object(runner_module, "preflight", return_value=self.observation), \
             patch.object(runner_module, "account_lock_fingerprint", side_effect=sentinel):
            try:
                code = runner_module.main()
                return sentinel, code, None
            except Exception as exc:  # noqa: BLE001 -- deliberately catches the sentinel too
                return sentinel, None, exc

    def test_paper_without_gate_arguments_is_blocked_before_execution_continues(self):
        sentinel, code, raised = self._run_main("paper")
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "not_started")
        self.assertEqual(result["reason"], "promotion_gate_missing")

    def test_paper_with_failing_gate_result_is_blocked_before_execution_continues(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(status="fail", input_sha256=self.snapshot_hash)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "not_started")
        self.assertEqual(result["reason"], "promotion_gate_failed")

    def test_paper_with_mismatched_snapshot_hash_is_blocked(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(input_sha256="0" * 64)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["reason"], "promotion_gate_mismatch")

    def test_paper_with_zero_row_count_gate_result_is_blocked(self):
        """Regression (finding 3): a gate result with top-level status "pass"
        and a matching hash, but row_count=0, must not reach execution."""
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(row_count=0, input_sha256=self.snapshot_hash)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["reason"], "promotion_gate_empty")

    def test_paper_with_a_failed_check_in_gate_result_is_blocked(self):
        """Regression (finding 3): a gate result with top-level status
        "pass" and a matching hash, but a failed named check, must not
        reach execution."""
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(checks_status="fail", input_sha256=self.snapshot_hash)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["reason"], "promotion_gate_failed_check")

    def test_paper_with_passing_matched_gate_reaches_post_gate_execution(self):
        gate_path = self.root / "gate-result.json"
        gate_path.write_text(json.dumps(_full_gate_result(input_sha256=self.snapshot_hash)))
        sentinel, code, raised = self._run_main("paper", ["--gate-result", str(gate_path), "--snapshot", str(self.snapshot)])
        self.assertIsNone(code)
        self.assertIs(raised, sentinel)

    def test_recover_command_is_unaffected_by_missing_gate_arguments(self):
        """`recover` resumes a trial already admitted by an earlier `paper`
        run; it must not additionally require --gate-result/--snapshot."""
        self.observation["positions"] = [{"symbol": "SPY", "qty": "1"}]
        sentinel, code, raised = self._run_main("recover")
        self.assertIsNone(code)
        self.assertIs(raised, sentinel)

    def test_preflight_command_is_unaffected_by_missing_gate_arguments(self):
        sentinel, code, raised = self._run_main("preflight")
        self.assertIsNone(raised)
        self.assertEqual(code, 0)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "ready")


class OvernightHoldPreflightScope(unittest.TestCase):
    """Rebase review D1/D2 (PR #69): overnight_holds may relax the flat-account
    gate only to resume a trial this engine left held_overnight, and main()
    reuses run_native's own hold decision instead of re-reading the clock."""

    # 2026-09-22 15:00 UTC = 11:00 ET, a regular session inside the frozen calendar.
    RTH_NS = 1790089200 * 1_000_000_000

    def setUp(self):
        MainCommandGateWiring.setUp(self)
        self.observation["clock"].update(timestamp_ns=self.RTH_NS, received_at_ns=self.RTH_NS,
                                         next_close_ns=self.RTH_NS + 3600 * 1_000_000_000)
        # Benchmark-quote freshness is checked against real time, so quotes keep a current stamp.
        self.observation["quotes"] = [{"symbol": s, "ts_ns": time.time_ns()} for s in self.config["symbols"]]
        self.observation["positions"] = [{"symbol": "SPY", "qty": "1"}]
        self.config.update(regular_session_only=False, extended_hours_enabled=True,
                           sessions={"extended_hours": True, "overnight_holds": True,
                                     "overnight_gross_multiple": "1.0"})
        self.gate_path = self.root / "gate-result.json"
        self.gate_path.write_text(json.dumps(_full_gate_result(input_sha256=self.snapshot_hash)))

    def tearDown(self):
        MainCommandGateWiring.tearDown(self)

    _argv = MainCommandGateWiring._argv
    _run_main = MainCommandGateWiring._run_main

    def _paper(self):
        return self._run_main("paper", ["--gate-result", str(self.gate_path), "--snapshot", str(self.snapshot)])

    def test_first_trial_with_foreign_position_is_refused_even_under_overnight_holds(self):
        sentinel, code, raised = self._paper()
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(self.output.read_text())["reason"], "clean_native_start_requires_flat_account")

    def test_prior_held_overnight_phase_allows_the_non_flat_resume(self):
        trial = self.root / "state" / "fixture-account" / "adaptive" / "trial.json"
        trial.parent.mkdir(parents=True)
        trial.write_text(json.dumps({"phase": "held_overnight"}))
        sentinel, code, raised = self._paper()
        self.assertIs(raised, sentinel)

    def test_other_prior_phase_does_not_relax_the_flat_gate(self):
        trial = self.root / "state" / "fixture-account" / "adaptive" / "trial.json"
        trial.parent.mkdir(parents=True)
        trial.write_text(json.dumps({"phase": "needs_attention"}))
        sentinel, code, raised = self._paper()
        self.assertIsNone(raised)
        self.assertEqual(code, 2)

    def test_non_object_state_file_keeps_the_flat_gate(self):
        trial = self.root / "state" / "fixture-account" / "adaptive" / "trial.json"
        trial.parent.mkdir(parents=True)
        trial.write_text("[]")
        sentinel, code, raised = self._paper()
        self.assertIsNone(raised)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(self.output.read_text())["reason"], "clean_native_start_requires_flat_account")

    def _paper_with_lock_hook(self, on_lock):
        """Runs main() with a real (no-op) account lock whose entry calls
        ``on_lock`` -- another process changing trial.json between the
        pre-lock phase read and the locked re-read."""
        from contextlib import contextmanager

        @contextmanager
        def lock(_fingerprint):
            on_lock()
            yield

        extra = ["--gate-result", str(self.gate_path), "--snapshot", str(self.snapshot)]
        with patch.object(sys, "argv", self._argv("paper", extra)), \
             patch.object(runner_module, "load_config", return_value=(self.config, None, None)), \
             patch.object(runner_module, "credentials", return_value=("fixture-key", "fixture-secret")), \
             patch.object(runner_module, "preflight", return_value=self.observation), \
             patch.object(runner_module, "account_lock_fingerprint", lock):
            return runner_module.main()

    def test_hold_appearing_between_preflight_and_lock_is_refused(self):
        self.observation["positions"] = []
        trial = self.root / "state" / "fixture-account" / "adaptive" / "trial.json"

        def write_hold():
            trial.parent.mkdir(parents=True, exist_ok=True)
            trial.write_text(json.dumps({"phase": "held_overnight"}))

        with self.assertRaisesRegex(SafetyErrorAlways, "trial_state_changed_during_preflight"):
            self._paper_with_lock_hook(write_hold)

    def test_hold_disappearing_between_preflight_and_lock_is_refused(self):
        trial = self.root / "state" / "fixture-account" / "adaptive" / "trial.json"
        trial.parent.mkdir(parents=True)
        trial.write_text(json.dumps({"phase": "held_overnight"}))
        with self.assertRaisesRegex(SafetyErrorAlways, "trial_state_changed_during_preflight"):
            self._paper_with_lock_hook(lambda: trial.write_text(json.dumps({"phase": "finished"})))

    def _held_ledger(self, positions=(), orders=()):
        from safety import Ledger as LedgerAlways, RiskLimits as RiskLimitsAlways
        ledger = LedgerAlways(self.root / "held-ledger.sqlite3", RiskLimitsAlways())
        self.addCleanup(ledger.close)
        ledger.adopt_broker_snapshot({"positions": list(positions), "orders": list(orders)}, time.time())
        return ledger

    def test_held_resume_accepts_exactly_the_ledger_holdings(self):
        own_order = {"client_order_id": "trial-exit-1", "id": "b-7", "symbol": "SPY", "side": "sell",
                     "qty": "1", "limit_price": "501", "filled_qty": "0", "status": "new"}
        ledger = self._held_ledger([{"symbol": "SPY", "qty": "1", "avg_entry_price": "500"},
                                    {"symbol": "AAPL", "qty": "0.5", "avg_entry_price": "200"}], [own_order])
        # Decimal value equality ("1" == "1.0", "0.5" == "0.50"), zero-quantity rows ignored,
        # and an open order the ledger itself owns is accepted.
        runner_module.held_resume_matches_ledger(ledger, {
            "positions": [{"symbol": "SPY", "qty": "1.0"}, {"symbol": "AAPL", "qty": "0.50"},
                          {"symbol": "MSFT", "qty": "0"}],
            "orders": [own_order]})

    def test_held_resume_refuses_a_foreign_or_changed_position(self):
        ledger = self._held_ledger([{"symbol": "SPY", "qty": "1", "avg_entry_price": "500"}])
        for positions in ([{"symbol": "SPY", "qty": "1"}, {"symbol": "AMD", "qty": "3"}],
                          [{"symbol": "SPY", "qty": "2"}],
                          [{"symbol": "SPY", "qty": "1"}, {"symbol": "META", "qty": "-1"}],
                          []):
            with self.subTest(positions=positions):
                with self.assertRaisesRegex(SafetyErrorAlways, "held_resume_position_mismatch"):
                    runner_module.held_resume_matches_ledger(ledger, {"positions": positions, "orders": []})

    def test_held_resume_refuses_an_order_the_ledger_does_not_own(self):
        ledger = self._held_ledger([{"symbol": "SPY", "qty": "1", "avg_entry_price": "500"}])
        foreign = {"client_order_id": "manual-1", "id": "b-1", "symbol": "SPY", "side": "sell", "qty": "1"}
        with self.assertRaisesRegex(SafetyErrorAlways, "held_resume_external_order"):
            runner_module.held_resume_matches_ledger(
                ledger, {"positions": [{"symbol": "SPY", "qty": "1"}], "orders": [foreign]})

    def test_main_refuses_held_resume_when_broker_holds_what_the_ledger_does_not(self):
        """Wiring: the persisted held trial's ledger is empty while the broker
        shows SPY, so main() refuses before resuming, keeps the held phase for
        explicit recovery, and never builds a broker transport."""
        from safety import RiskLimits as RiskLimitsAlways
        trial = self.root / "state" / "fixture-account" / "adaptive" / "trial.json"
        trial.parent.mkdir(parents=True)
        held = {"phase": "held_overnight", "config_sha256": hashlib.sha256(self.config_file.read_bytes()).hexdigest(),
                "started_at": 0, "baseline_cash": "100000"}
        trial.write_text(json.dumps(held))
        transport_sentinel = RuntimeError("broker_transport_constructed")
        frozen = datetime.fromtimestamp(self.RTH_NS / 1e9, timezone.utc)
        real_session_at, real_extended_close = runner_module.session_at, runner_module.extended_session_close
        extra = ["--gate-result", str(self.gate_path), "--snapshot", str(self.snapshot)]
        from contextlib import nullcontext
        with patch.object(sys, "argv", self._argv("paper", extra)), \
             patch.object(runner_module, "load_config", return_value=(self.config, RiskLimitsAlways(), None)), \
             patch.object(runner_module, "credentials", return_value=("fixture-key", "fixture-secret")), \
             patch.object(runner_module, "preflight", return_value=self.observation), \
             patch.object(runner_module, "account_lock_fingerprint", lambda _f: nullcontext()), \
             patch.object(runner_module, "AlpacaPaperTransport", side_effect=transport_sentinel), \
             patch.object(runner_module, "session_at", lambda _ts: real_session_at(frozen)), \
             patch.object(runner_module, "extended_session_close", lambda _ts: real_extended_close(frozen)):
            # The session clock is pinned to the frozen RTH instant, so the controller's
            # wall-clock session lookup does not depend on the built-in 2026 calendar.
            with self.assertRaisesRegex(SafetyErrorAlways, "held_resume_position_mismatch"):
                runner_module.main()
        self.assertEqual(json.loads(trial.read_text()), held)

    def test_main_reuses_run_native_hold_decision(self):
        self.assertFalse(runner_module._final_boundary_from_run_status({"status": "held_overnight"}))
        for status in ("needs_attention", "failed", "passed", "completed_no_signals"):
            self.assertTrue(runner_module._final_boundary_from_run_status({"status": status}))


class CredentialFilePermissions(unittest.TestCase):
    """runner.credentials() fails closed on env-file mode, ownership, and
    Git-worktree location before any line of the file is parsed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_env(self, directory, name="paper.env", mode=0o600):
        path = directory / name
        path.write_text("APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")
        os.chmod(path, mode)
        return path

    def test_wrong_mode_is_rejected(self):
        path = self._write_env(self.root, mode=0o644)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(path)

    def test_group_or_other_readable_mode_is_rejected(self):
        path = self._write_env(self.root, mode=0o640)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(path)

    def test_wrong_owner_is_rejected(self):
        path = self._write_env(self.root)
        with patch.object(runner_module.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
                credentials(path)

    def test_inside_git_worktree_is_rejected(self):
        repo_root = Path(__file__).resolve().parents[1]
        self.assertTrue((repo_root / ".git").exists(), "test assumes this checkout is a Git worktree")
        with tempfile.TemporaryDirectory(dir=repo_root) as inside:
            path = self._write_env(Path(inside))
            with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
                credentials(path)

    def test_missing_file_is_rejected(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(self.root / "does-not-exist.env")

    def test_passing_case_outside_worktree_mode_0600_own_uid_returns_credentials(self):
        path = self._write_env(self.root)
        self.assertEqual(credentials(path), ("fixture-key", "fixture-secret"))

    def test_error_never_includes_file_contents(self):
        path = self._write_env(self.root, mode=0o644)
        with self.assertRaises(SafetyErrorAlways) as ctx:
            credentials(path)
        self.assertNotIn("fixture-key", str(ctx.exception))
        self.assertNotIn("fixture-secret", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
