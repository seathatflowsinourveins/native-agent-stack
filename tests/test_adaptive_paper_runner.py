"""Local cross-module tests: native engine, controller, ledger, synthetic port."""
import asyncio
import contextlib
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


class _DeadlineExceeded(Exception):
    """Raised by a SIGALRM handler; never a real timeout the OS enforces."""


@contextlib.contextmanager
def _deadline(seconds):
    """Hard wall-clock bound for one call, via signal.alarm: a blocking
    syscall (e.g. open() on a FIFO without O_NONBLOCK) is interrupted with
    EINTR and, since the handler raises rather than returning, Python does
    not auto-retry it (PEP 475) -- so a real hang fails this test fast
    instead of freezing the suite."""
    def _on_alarm(signum, frame):
        raise _DeadlineExceeded(f"exceeded {seconds}s deadline")
    previous = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)

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
    # EH-3/N1-0 (2026-09-22 leverage fix round 2): module references (not just
    # the names run_native/Ledger already pull in) needed to pin every
    # session_at() lookup the achieved-leverage integration tests exercise --
    # native_strategy._leverage_inputs and safety.Ledger._leverage_envelope
    # each hold their own `session_at`/`_session_at` binding, imported
    # separately from the sessions module, so patching runner_module alone
    # does not reach them. native_strategy imports nautilus_trader at module
    # scope, so it is only importable inside this NATIVE-gated block.
    import native_strategy as native_strategy_module
    NATIVE = True
except ImportError:
    NATIVE = False

# runner.py itself (and safety.py) import cleanly without nautilus_trader/alpaca
# (those are only imported lazily inside run_native/recovery paths), so the
# promotion-gate and credential-permission tests below run unconditionally.
import runner as runner_module
import safety as safety_module
from runner import credentials, validate_preflight as validate_preflight_always
from safety import SafetyError as SafetyErrorAlways

try:  # package mode (python -m unittest tests.x) or discover -s tests (top-level modules)
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    extra = (native_strategy_module,) if NATIVE else ()
    _HERMETIC_TOKEN = patch_default_stop(*extra)


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class IntegratedRunner(unittest.TestCase):
    def test_default_config_is_bounded(self):
        config, risk, policy = runner_module.load_config(SOURCE / "config.json")
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
            # E2's native assertions ride the outcome (a receipt field, not only counters).
            self.assertEqual(result["native_assertions"], {"fill_events_carry_execution_fields": True,
                                                           "no_fill_gap_open_at_stop": True, "overturn_signals": []})
            self.assertTrue(any(e["type"] == "intent" for e in controller.events))
            self.assertEqual(len(ledger.unresolved()), 0)
            self.assertEqual(port.started, 1)
            self.assertEqual(port.stopped, 1)
            ledger.close()

    def test_run_output_records_dropped_quote_counts_from_the_transport(self):
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=1, cleanup_seconds=2, order_timeout_seconds=1)
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=1, cleanup_seconds=2))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
            port = SimulatedPort(controller, policy.symbols, price=lambda symbol, tick: Decimal("100"))
            port.health.update(dropped_quotes={"crossed": 2, "one_sided": 1}, dropped_quotes_by_symbol={"SPY": 3})
            controller.port = port
            result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                            "fixture", config, "100000"))
            self.assertEqual(result["dropped_quotes"], {"by_reason": {"crossed": 2, "one_sided": 1},
                                                        "by_symbol": {"SPY": 3}})
            ledger.close()

    def test_gap_arising_during_the_periodic_snapshot_stops_instead_of_thawing(self):
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=3, cleanup_seconds=2, order_timeout_seconds=1)

        class GapDuringSnapshot(SimulatedPort):
            marks = snapshots = 0

            async def snapshot(self):
                snap = await super().snapshot()
                GapDuringSnapshot.snapshots += 1
                if GapDuringSnapshot.snapshots == 2:  # the first periodic one; the first is the startup snapshot
                    self.health["reasons"] = ["orders_disconnected"]  # arrives while the snapshot awaits
                return snap

            def mark_reconciled(self):
                GapDuringSnapshot.marks += 1

        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=3, cleanup_seconds=2))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
            port = GapDuringSnapshot(controller, policy.symbols, price=lambda symbol, tick: Decimal("100"))
            port.health.update(fresh_quotes=True, reasons=[])
            controller.port = port
            with patch.object(runner_module, "RECONCILE_EVERY_SECONDS", 0.2):
                asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                       "fixture", config, "100000"))
            self.assertGreaterEqual(GapDuringSnapshot.snapshots, 2)  # the periodic branch ran
            self.assertEqual(GapDuringSnapshot.marks, 0)
            self.assertTrue(controller.stop)
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

    def test_cancel_requests_name_their_order_without_touching_the_durable_budget(self):
        # Exact sim-to-paper cancel pairing reads the in-memory log (paper-output
        # requests[]). The durable row stays unbound for a cancel: requests.client_id is a
        # foreign key to intents, so an unknown id must not be able to fail the reservation.
        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True, clock=lambda: now)
            asyncio.run(controller.before_request("cancel", client_id="not-a-durable-intent"))
            asyncio.run(controller.before_request("read"))
            controller.port = type("Port", (), {"ready": True})()
            controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01", "ts_ns": int(now * 1e9)})
            controller.before_submit({"client_order_id": "named-submit", "symbol": "SPY", "side": "buy",
                                      "qty": "1", "limit_price": "100.03"})
            asyncio.run(controller.before_request("submit", client_id="named-submit"))
            self.assertEqual(controller.requests, [
                {"timestamp": now, "kind": "cancel", "client_id": "not-a-durable-intent"},
                {"timestamp": now, "kind": "read"},
                {"timestamp": now, "kind": "submit", "client_id": "named-submit"}])
            rows = ledger.db.execute("SELECT kind, client_id FROM requests ORDER BY id").fetchall()
            self.assertEqual([tuple(row) for row in rows],
                             [("cancel", None), ("read", None), ("submit", "named-submit")])
            ledger.close()

    def test_simulated_ports_name_the_cancelled_order(self):
        from mover_simulation import MoverSimulatedPort
        from simulation import SimulatedPort
        calls = []

        class Recorder:
            async def before_request(self, kind, client_id=None):
                calls.append((kind, client_id))
        asyncio.run(SimulatedPort(Recorder(), ["SPY"]).cancel("sim-1"))
        mover = MoverSimulatedPort(Recorder(), ["SPY"], path=lambda symbol, elapsed: None)
        mover._intents["mover-1"] = {"client_order_id": "mover-1"}
        asyncio.run(mover.cancel("mover-1"))
        self.assertEqual(calls, [("cancel", "sim-1"), ("cancel", "mover-1")])

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

    def test_documented_sub_penny_refusal_is_recorded_through_the_controller(self):
        from transport import RejectedSubmission, SUB_PENNY_REFUSAL
        import safety

        class Exempt(Ledger):  # native-faults/harness.py FaultLedger shape
            def _check_price_increment(self, client_id, price):
                if client_id != "c04-test":
                    super()._check_price_increment(client_id, price)
        now = time.time()
        with tempfile.TemporaryDirectory() as root:
            ledger = Exempt(Path(root) / "journal.db")
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True)

            class RefusingPort:
                ready = True
                async def submit(self, payload):
                    controller.before_submit(payload)
                    await controller.before_request("submit", payload["client_order_id"])
                    raise RejectedSubmission(422, SUB_PENNY_REFUSAL)
            controller.port = controller.bind(RefusingPort())
            controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01", "ts_ns": time.time_ns()})
            payload = {"client_order_id": "c04-test", "symbol": "SPY", "side": "buy", "qty": "1",
                       "limit_price": "40.0001"}
            with self.assertRaises(RejectedSubmission) as caught:
                asyncio.run(controller.port.submit(payload))
            self.assertEqual(caught.exception.refusal, safety.SUB_PENNY_REFUSAL)
            intent = ledger.intents()[0]
            self.assertEqual((intent.status, intent.limit_price), ("broker_refused", Decimal("40.0001")))
            self.assertTrue(controller.stop)
            proof = reconcile(ledger, {"complete": True, "orders": [], "positions": [], "account": {"cash": "100000"}}, "100000")
            self.assertEqual((proof["open_orders"], proof["positions"]), (0, 0))
            ledger.close()

    def test_order_contract_refusal_is_local_not_sent_and_never_reaches_the_fake_broker(self):
        """Controller.bind over the real AlpacaPaperTransport: a symbol the ledger and
        the transport accept but the order contract does not (BRK-B, not BRK.B)
        is refused before any HTTP request and recorded as local not_sent."""
        from unittest.mock import Mock
        import transport as engine_transport
        now = time.time()

        async def scenario(ledger, controller):
            port = engine_transport.AlpacaPaperTransport(
                "fixture-key", "fixture-secret", ["SPY", "BRK-B"], before_request=controller.before_request,
                before_submit=controller.before_submit, sink_observation=controller.observe)
            port._loop = asyncio.get_running_loop()
            port._started = True
            for channel in ("quotes", "orders"):
                port._authorized(channel)
                port._ack(channel, True)
            for symbol in ("SPY", "BRK-B"):
                port._quote_seen[symbol] = time.monotonic()
                port._quote_values[symbol] = {"ts_ns": time.time_ns()}
                controller.quote({"symbol": symbol, "bid": "100", "ask": "100.01", "ts_ns": time.time_ns()})
            controller.port = controller.bind(port)
            broker = Mock()
            payload = {"client_order_id": "contract-test", "symbol": "BRK-B", "side": "buy", "qty": "1",
                       "limit_price": "100.03", "type": "limit", "time_in_force": "day", "extended_hours": False}
            try:
                with patch.object(port._client._session._session, "request", broker):
                    with self.assertRaises(engine_transport.OrderContractRefused) as caught:
                        await controller.port.submit(payload)
            finally:
                await port.stop()
            broker.assert_not_called()
            return caught.exception

        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            controller = Controller(ledger, now + 3600, market_open=True)
            error = asyncio.run(scenario(ledger, controller))
            self.assertNotIsInstance(error, engine_transport.RejectedSubmission)
            intent = ledger.intents()[0]
            self.assertEqual((intent.client_id, intent.status, intent.submit_attempted),
                             ("contract-test", "not_sent", False))
            reason = ledger.db.execute("SELECT payload FROM events WHERE kind='intent_not_sent' AND client_id=?",
                                       ("contract-test",)).fetchone()[0]
            self.assertEqual(json.loads(reason), {"reason": "order_contract_refused"})
            self.assertFalse(ledger.db.execute("SELECT 1 FROM events WHERE kind='broker_refused'").fetchone())
            self.assertFalse(controller.stop)  # a local refusal is not a broker refusal stop
            proof = reconcile(ledger, {"complete": True, "orders": [], "positions": [],
                                       "account": {"cash": "100000"}}, "100000")
            self.assertEqual((proof["open_orders"], proof["positions"]), (0, 0))
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

    def test_a_halted_symbol_gets_no_order_and_its_resting_exit_is_not_repriced(self):
        """E4: while halted (runner.Controller.is_halted), a symbol gets no entry and no exit
        order, and its resting exit is neither cancelled for a timeout nor replaced; the same
        tick after the resume sends the exit."""
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy, SelectorConfig
        from selector import ACTIVE, FLATTEN_BEFORE_SWITCH, SelectionDecision

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
                self.calls.append({"instrument_id": str(instrument_id), "tags": list(tags)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        now = time.time()
        halted = {"AAPL", "IBM"}
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            ledger.reserve_intent("buy-1", "AAPL", "buy", "1", "100.01", quote=Quote("AAPL", "100", "100.01", now),
                                  now=now, market_open=True, session_close=now + 3600)
            ledger.record_order("buy-1", "broker-buy-1", "filled", "1", "100", timestamp=now)
            _, _, policy_config = load_config(SOURCE / "config.json")
            decision = SelectionDecision(timestamp=now, prior_state=ACTIVE, new_state=ACTIVE, regime="trend",
                                         confidence=1.0, advantage_bps=50.0, incumbent_id="adaptive_policy_v1",
                                         candidate_id="adaptive_policy_v1", reason_codes=("switched",),
                                         blocked_by=(), liquidate=True)
            policy = AdaptivePolicy(policy_config, strategy_pool=(V1Spec(),), selector=FakeSelector(decision))
            strategy = FakeStrategy(policy, ledger, "fixture", halted=lambda symbol: symbol in halted)
            strategy._fake_order_factory = FakeOrderFactory()
            submitted, cancelled = [], []
            strategy.submit_order = submitted.append
            strategy.cancel_order = cancelled.append
            strategy.started = strategy.enabled = True
            policy.observe("AAPL", 100.995, 101.005, now)
            strategy.pending["adp-fixture-0000098"] = {"symbol": "IBM", "side": "sell", "created": now - 60}
            strategy.pending["adp-fixture-0000099"] = {"symbol": "IBM", "side": "buy", "created": now - 60}

            strategy.rebalance(now + .01)
            strategy.cancel_expired(now + .02, 10)
            self.assertEqual(submitted, [])                                   # the AAPL flatten waits
            self.assertEqual([str(c) for c in cancelled], ["adp-fixture-0000099"])   # entries still cancel
            self.assertNotIn("cancel_requested", strategy.pending["adp-fixture-0000098"])

            halted.clear()                                                    # both resume
            policy.observe("AAPL", 100.995, 101.005, now + .03)
            policy.last_decision = 0                                          # the next decision tick
            strategy.rebalance(now + .03)
            strategy.cancel_expired(now + .04, 10)
            self.assertEqual(len(submitted), 1)
            self.assertIn("reason=rotation_flatten", strategy._fake_order_factory.calls[0]["tags"])
            self.assertIn("adp-fixture-0000098", [str(c) for c in cancelled])  # re-pricing resumes
            ledger.close()

    def test_a_stale_seed_on_a_held_symbol_blocks_its_exit_only_until_the_seed_expires(self):
        """A3 and B6 through the adaptive strategy and a real Controller: the startup seed says
        AAPL and IBM are in a LULD pause that in fact resumed before the engine subscribed (no
        status message follows), and their quotes carry the best-effort condition flag. While
        the seed counts, AAPL's flatten waits and IBM's resting exit is not cancelled for
        re-pricing; at the seed's 12-minute expiry both go ahead, and the quote flag, still
        set, holds neither exit back."""
        from native_strategy import AdaptiveStrategy
        from strategies import AdaptivePolicy, SelectorConfig
        from selector import ACTIVE, FLATTEN_BEFORE_SWITCH, SelectionDecision

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
                self.calls.append({"instrument_id": str(instrument_id), "tags": list(tags)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        now = time.time()
        clock = [now]
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db")
            ledger.start_trial(now)
            ledger.reserve_intent("buy-1", "AAPL", "buy", "1", "100.01", quote=Quote("AAPL", "100", "100.01", now),
                                  now=now, market_open=True, session_close=now + 3600)
            ledger.record_order("buy-1", "broker-buy-1", "filled", "1", "100", timestamp=now)
            controller = Controller(ledger, now + 3600, market_open=True, clock=lambda: clock[0])
            halted_at = int((now - 12 * 60 + .02) * 1e9)          # the seed expires at now + 0.02 s
            pause = {"halted_at_ns": halted_at, "resumption_trade_ns": None, "reason_code": "LUDP", "market": "NASDAQ"}
            controller.apply_halt_seed({"source": "nasdaq_trade_halts_rss", "fetched_at_ns": int(now * 1e9),
                                        "sha256": "0" * 64, "bytes": 1, "items": 2,
                                        "halts": {"AAPL": dict(pause), "IBM": dict(pause)}})
            for symbol in ("AAPL", "IBM"):
                controller.quote({"symbol": symbol, "bid": "100.99", "ask": "101.01", "ts_ns": int(now * 1e9),
                                  "halted": True})
            _, _, policy_config = load_config(SOURCE / "config.json")
            decision = SelectionDecision(timestamp=now, prior_state=ACTIVE, new_state=ACTIVE, regime="trend",
                                         confidence=1.0, advantage_bps=50.0, incumbent_id="adaptive_policy_v1",
                                         candidate_id="adaptive_policy_v1", reason_codes=("switched",),
                                         blocked_by=(), liquidate=True)
            policy = AdaptivePolicy(policy_config, strategy_pool=(V1Spec(),), selector=FakeSelector(decision))
            strategy = FakeStrategy(policy, ledger, "fixture", halted=controller.is_halted)
            strategy._fake_order_factory = FakeOrderFactory()
            submitted, cancelled = [], []
            strategy.submit_order = submitted.append
            strategy.cancel_order = cancelled.append
            strategy.started = strategy.enabled = True
            policy.observe("AAPL", 100.995, 101.005, now)
            strategy.pending["adp-fixture-0000098"] = {"symbol": "IBM", "side": "sell", "created": now - 60}

            clock[0] = now + .01
            strategy.rebalance(now + .01)
            strategy.cancel_expired(now + .01, 10)
            self.assertEqual((submitted, cancelled), ([], []))                  # the seed still counts
            self.assertEqual(controller.halt_summary()["halted_now"], ["AAPL", "IBM"])

            clock[0] = now + .03                                                # past the seed's expiry
            policy.observe("AAPL", 100.995, 101.005, now + .03)
            policy.last_decision = 0
            strategy.rebalance(now + .03)
            strategy.cancel_expired(now + .03, 10)
            self.assertEqual(len(submitted), 1)
            self.assertIn("reason=rotation_flatten", strategy._fake_order_factory.calls[0]["tags"])
            self.assertEqual([str(c) for c in cancelled], ["adp-fixture-0000098"])   # re-pricing resumes
            self.assertTrue(controller.quotes["AAPL"].halted)                   # the flag alone: entries only
            self.assertEqual(controller.halt_summary()["halted_now"], [])
            self.assertEqual(sorted(e["symbol"] for e in controller.events if e.get("effect") == "seed_expired"),
                             ["AAPL", "IBM"])
            ledger.close()

    def test_an_order_callback_exception_ends_the_run_needs_attention_and_routes_to_recovery(self):
        """E3 through run_native: an exception raised beneath the guard of on_order_filled
        freezes the ledger with its named reason, stops the session (the adapter records the
        fault and denies every later submit), and the run ends needs_attention and non-flat,
        which main() hands to recovery.recover (must_end_flat)."""
        import native_strategy
        from runner import _final_boundary_from_run_status
        from sessions import DEFAULT_SESSION_POLICY, must_end_flat
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=3, cleanup_seconds=2, order_timeout_seconds=1)
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=3, cleanup_seconds=2))
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
            submits_at_fault = []

            def fault(self, client_id, terminal=None):
                submits_at_fault.append(len(port.submitted_at))
                raise RuntimeError("injected bookkeeping fault")

            with patch.object(native_strategy.AdaptiveStrategy, "_release_staged_replacement", fault):
                result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                                "fixture", config, "100000"))
            reason = "strategy_callback_exception_on_order_filled"
            self.assertEqual(result["status"], "needs_attention", result.get("adapter_errors"))
            self.assertTrue(result["adapter_errors"])
            self.assertEqual(set(result["adapter_errors"]), {reason + ":RuntimeError"})
            self.assertEqual(ledger.halted_reason(), reason)
            self.assertEqual(result["callback_faults"][0]["callback"], "on_order_filled")
            self.assertEqual(len(port.submitted_at), submits_at_fault[0])   # no submit after the fault
            self.assertFalse(result["flat"])
            self.assertTrue(must_end_flat(DEFAULT_SESSION_POLICY,
                                          is_final_boundary=_final_boundary_from_run_status(result)))
            self.assertEqual(trial_phase_and_exit_code(result), ("needs_attention", 3))
            self.assertTrue(any(e.get("type") == "strategy_callback_exception" for e in controller.events))
            ledger.close()

    def test_a_seeded_halt_keeps_its_symbol_out_of_run_native_entries(self):
        """E4 startup state through run_native: the halt seed (a halts-feed result in the
        shape transport.nasdaq_halt_seed returns) marks AAPL halted while the node connects;
        with no streamed resume it gets no order while MSFT, on the same price path, trades.
        The outcome records the seed."""
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=3, cleanup_seconds=2, order_timeout_seconds=1)
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=3, cleanup_seconds=2))
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
            reads = []

            def seed(symbols):
                reads.append(symbols)
                return {"source": "nasdaq_trade_halts_rss", "fetched_at_ns": time.time_ns(), "sha256": "0" * 64,
                        "bytes": 1, "items": 1,
                        "halts": {"AAPL": {"halted_at_ns": time.time_ns() - 10 ** 9, "resumption_trade_ns": None,
                                           "reason_code": "T12", "market": "NASDAQ"}}}
            controller.halt_seed_fetch = seed
            result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                            "fixture", config, "100000"))
            bought = {i.symbol for i in ledger.intents() if i.side == "buy"}
            self.assertEqual(result["adapter_errors"], [])
            self.assertEqual(reads, [sorted(policy.symbols)])
            self.assertNotIn("AAPL", bought)
            self.assertIn("MSFT", bought)
            self.assertEqual((result["halts"]["seed"]["status"], result["halts"]["halted_now"]), ("seeded", ["AAPL"]))
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

    def test_honest_overnight_hold_false_when_corporate_action_guard_still_pending(self):
        """MEDIUM finding 5 (2026-09-24 fix round): a held symbol still
        flagged must_flatten by the corporate-action guard at the run's own
        boundary must make the run needs_attention (take the recovery path)
        rather than a legitimate held_overnight -- a confirmed in-range
        corporate action that never actually got flattened (order never
        filled/was rejected/run ended too soon) is a genuine failure, not
        an intentional hold."""
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        post_ts = datetime(2026, 3, 10, 18, 0, tzinfo=ny).astimezone(timezone.utc).timestamp()
        session_policy = {"overnight_holds": True, "extended_hours": True}
        clean_outcome = {"reconciliation": {"positions": 1, "open_orders": 0},
                         "adapter_errors": [], "accounting": {"halted_reason": None},
                         "corporate_action_guard": {"enabled": True, "ever_flagged_symbols": ["AAPL"],
                                                    "pending_must_flatten": ["AAPL"]}}
        self.assertFalse(_honest_overnight_hold(clean_outcome, session_policy, post_ts))
        # Same outcome but the guard's pending_must_flatten has cleared (the
        # flatten actually completed): a genuine hold is allowed again.
        cleared = {**clean_outcome, "corporate_action_guard": {"enabled": True, "ever_flagged_symbols": ["AAPL"],
                                                                "pending_must_flatten": []}}
        self.assertTrue(_honest_overnight_hold(cleared, session_policy, post_ts))
        # No guard summary at all (guard disabled/never wired): unaffected,
        # same as before this finding's fix.
        no_guard = {k: v for k, v in clean_outcome.items() if k != "corporate_action_guard"}
        self.assertTrue(_honest_overnight_hold(no_guard, session_policy, post_ts))

    def test_honest_overnight_hold_false_when_a_held_symbol_was_never_verified_clear(self):
        """MEDIUM finding 4 (fix round 3): a held symbol whose
        corporate-action lookup failed/was ambiguous/went stale for the
        whole run (needs_attention, but never a confirmed must_flatten --
        the guard never even learned enough to know whether to flatten)
        must ALSO refuse a "held_overnight" success. The documented policy
        is block-and-flag: not flattening an unverified holding is correct,
        but declaring the run a clean success while the attention flag is
        still live is not."""
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        post_ts = datetime(2026, 3, 10, 18, 0, tzinfo=ny).astimezone(timezone.utc).timestamp()
        session_policy = {"overnight_holds": True, "extended_hours": True}
        clean_outcome = {"reconciliation": {"positions": 1, "open_orders": 0},
                         "adapter_errors": [], "accounting": {"halted_reason": None},
                         "corporate_action_guard": {"enabled": True, "ever_flagged_symbols": ["AAPL"],
                                                    "pending_must_flatten": [],
                                                    "pending_needs_attention_held": ["AAPL"]}}
        self.assertFalse(_honest_overnight_hold(clean_outcome, session_policy, post_ts))
        # Once positively verified clear (empty), a genuine hold is allowed.
        cleared = {**clean_outcome, "corporate_action_guard": {
            "enabled": True, "ever_flagged_symbols": ["AAPL"],
            "pending_must_flatten": [], "pending_needs_attention_held": []}}
        self.assertTrue(_honest_overnight_hold(cleared, session_policy, post_ts))

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


class OrderContractPreflight(unittest.TestCase):
    """The runner refuses to start unless the transport's pre-submission
    order-contract boundary is active. Local; no pinned runtime or network."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env_file = self.root / "paper.env"
        self.env_file.write_text("APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")
        os.chmod(self.env_file, 0o600)
        self.config_file = self.root / "config.json"
        self.config_file.write_text("{}")
        self.output = self.root / "output.json"
        self.observation = _paper_ready_observation(time.time_ns())
        self.observation["account_identity_sha256"] = "fixture-account"
        self.config = _paper_ready_config()

    def tearDown(self):
        self.tmp.cleanup()

    def _main(self, command, status_error=None):
        from unittest.mock import Mock
        network, creds = Mock(return_value=self.observation), Mock(return_value=("fixture-key", "fixture-secret"))
        argv = ["runner.py", command, "--env-file", str(self.env_file), "--config", str(self.config_file),
                "--output", str(self.output), "--state-root", str(self.root / "state")]
        patches = [patch.object(sys, "argv", argv),
                   patch.object(runner_module, "load_config", return_value=(self.config, None, None)),
                   patch.object(runner_module, "credentials", creds),
                   patch.object(runner_module, "preflight", network)]
        if status_error is not None:
            patches.append(patch.object(runner_module, "order_contract_status", side_effect=status_error))
        with contextlib.ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            code = runner_module.main()
        return code, json.loads(self.output.read_text()), network, creds

    def test_active_boundary_is_checked_and_recorded_in_the_preflight_summary(self):
        status = runner_module.check_order_contract_boundary(["SPY", "BRK.B"])
        self.assertTrue(status["active"])
        self.assertEqual(status["symbols_checked"], 2)
        code, summary, network, _ = self._main("preflight")
        self.assertEqual((code, summary["status"]), (0, "ready"))
        self.assertTrue(summary["order_contract"]["active"])
        self.assertEqual(summary["order_contract"]["symbols_checked"], 1)
        network.assert_called_once()

    def test_inactive_boundary_refuses_before_credentials_or_any_request(self):
        error = runner_module.TransportError("order_contract_boundary_inactive:invalid_sentinel_accepted")
        for command in ("preflight", "paper", "recover"):
            with self.subTest(command=command):
                code, result, network, creds = self._main(command, status_error=error)
                self.assertEqual(code, 2)
                self.assertEqual(result, {"status": "not_started", "stage": "order_contract", "orders_submitted": 0,
                                          "reason": "order_contract_boundary_inactive:invalid_sentinel_accepted"})
                network.assert_not_called()
                creds.assert_not_called()

    def test_validate_preflight_requires_the_boundary_and_admissible_symbols(self):
        validate_preflight_always(self.observation, self.config, require_open=True)
        with self.assertRaisesRegex(SafetyErrorAlways, "^order_contract_boundary_inactive:configured_symbol"):
            validate_preflight_always(self.observation, _paper_ready_config(("SPY", "BRK-B")), require_open=True)
        error = runner_module.TransportError("order_contract_boundary_inactive:contract_module_not_loaded")
        with patch.object(runner_module, "order_contract_status", side_effect=error):
            with self.assertRaisesRegex(SafetyErrorAlways, "contract_module_not_loaded"):
                validate_preflight_always(self.observation, self.config, require_open=True, allow_existing=True)


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

    def test_symlink_to_a_valid_target_is_resolved_and_accepted(self):
        # runner.credentials() keeps its prior symlink-tolerant behavior (unlike
        # market_research.credentials(), which refuses a symlink outright): the
        # shared guard resolves the path first when follow_symlinks=True, then
        # applies every rule to the resolved target.
        target = self._write_env(self.root, name="real.env")
        link = self.root / "linked.env"
        link.symlink_to(target)
        self.assertEqual(credentials(link), ("fixture-key", "fixture-secret"))

    def test_fifo_is_rejected_and_does_not_hang(self):
        fifo = self.root / "fifo.env"
        os.mkfifo(fifo, mode=0o600)
        try:
            with _deadline(10):
                with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
                    credentials(fifo)
        except _DeadlineExceeded:
            # A genuine assertion failure (self.fail), not an uncaught
            # exception: unittest -- and the real mutation driver in
            # tests/_credential_mutation_driver.py, which only counts a
            # "FAIL", never an "ERROR", as a kill -- must see this as the
            # test actively catching the regression, not merely erroring.
            self.fail("credentials(fifo) hung past the 10s deadline instead of raising")

    def test_hard_link_is_rejected(self):
        # G-fix-round item 2: a second name for the same inode (e.g. one outside a
        # worktree, one inside) must not pass because the checked name alone looks
        # compliant -- credential_guard checks st_nlink on the opened fd.
        target = self._write_env(self.root, name="real.env")
        other_name = self.root / "second-name.env"
        os.link(target, other_name)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(target)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(other_name)

    def test_group_writable_parent_directory_is_rejected(self):
        path = self._write_env(self.root, mode=0o600)
        os.chmod(self.root, 0o770)
        try:
            with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
                credentials(path)
        finally:
            os.chmod(self.root, 0o700)

    def test_world_writable_parent_directory_is_rejected(self):
        path = self._write_env(self.root, mode=0o600)
        os.chmod(self.root, 0o707)
        try:
            with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
                credentials(path)
        finally:
            os.chmod(self.root, 0o700)

    def test_0700_and_0755_owned_parent_directories_still_pass(self):
        # Coordinator requirement: runner's accepted configurations are unchanged.
        for mode in (0o700, 0o755):
            with self.subTest(mode=oct(mode)):
                directory = self.root / oct(mode)
                directory.mkdir(mode=mode)
                os.chmod(directory, mode)  # mkdir's mode is subject to umask; force the exact bits
                path = self._write_env(directory)
                self.assertEqual(credentials(path), ("fixture-key", "fixture-secret"))

    def test_passing_case_outside_worktree_mode_0600_own_uid_returns_credentials(self):
        path = self._write_env(self.root)
        self.assertEqual(credentials(path), ("fixture-key", "fixture-secret"))

    def test_error_never_includes_file_contents(self):
        path = self._write_env(self.root, mode=0o644)
        with self.assertRaises(SafetyErrorAlways) as ctx:
            credentials(path)
        self.assertNotIn("fixture-key", str(ctx.exception))
        self.assertNotIn("fixture-secret", str(ctx.exception))

    def test_error_never_includes_path_or_basename(self):
        path = self._write_env(self.root, name="tell-tale-name.env", mode=0o644)
        with self.assertRaises(SafetyErrorAlways) as ctx:
            credentials(path)
        self.assertNotIn("tell-tale-name", str(ctx.exception))
        self.assertNotIn(str(self.root), str(ctx.exception))

    def test_non_ascii_content_is_rejected(self):
        path = self.root / "paper.env"
        path.write_bytes("APCA_API_KEY_ID=fixturé-key\nAPCA_API_SECRET_KEY=fixture-secret\n".encode("utf-8"))
        os.chmod(path, 0o600)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions:encoding") as ctx:
            credentials(path)
        # G-round-4 item 1: `raw.isascii()` is checked before any `.decode()`
        # call, so no UnicodeDecodeError (whose `.object` attribute holds the
        # *entire* input, secret included) is ever constructed at all --
        # confirmed here on the exception itself, not only on its message.
        error = ctx.exception
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for attr in ("object", "args"):
            value = repr(getattr(error, attr, None))
            self.assertNotIn("fixtur", value)
            self.assertNotIn("fixture-secret", value)

    def test_oversized_file_is_rejected_not_silently_truncated_and_accepted(self):
        # G-round-4 item 4: proves the size check itself is what rejects an
        # over-cap file, not merely that some other check happens to reject
        # it too. Both real KEY/SECRET lines sit well inside the first
        # MAX_CREDENTIAL_BYTES + 1 bytes, followed by a huge trailing
        # comment line that pushes the file itself past the cap; a
        # truncated *comment* still starts with "#" and parses as a no-op,
        # so if the size check were ever removed, the bounded read alone
        # would silently hand back a "valid"-looking (but truncated-file)
        # credential pair instead of raising -- that specific failure mode
        # (a clean pass, not merely a different exception) is what this
        # test's assertRaisesRegex would then correctly flag as a FAIL.
        path = self.root / "paper.env"
        filler = "k" * 70000  # far past runner_module.MAX_CREDENTIAL_BYTES (64 KiB)
        path.write_text(f"APCA_API_KEY_ID=shortkey\nAPCA_API_SECRET_KEY=shortsecret\n# {filler}\n")
        os.chmod(path, 0o600)
        self.assertGreater(len(path.read_bytes()), runner_module.MAX_CREDENTIAL_BYTES)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions:size"):
            credentials(path)


class SharedCredentialGuardParity(unittest.TestCase):
    """runner.credentials() and market_research.credentials() cannot silently
    drift: both import the same credential_guard.open_verified(), and a
    permission violation that fails one fails the other the same way."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        import importlib.util
        spec = importlib.util.spec_from_file_location("market_research_parity", SOURCE / "market_research.py")
        self.market_research = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.market_research)

    def tearDown(self):
        self.tmp.cleanup()

    def test_both_loaders_share_the_same_guard_function(self):
        import credential_guard
        self.assertIs(runner_module.open_verified, credential_guard.open_verified)
        self.assertIs(self.market_research.open_verified, credential_guard.open_verified)

    def test_wrong_mode_rejected_by_both_loaders(self):
        path = self.root / "paper.env"
        path.write_text("APCA_API_KEY_ID=fixture-key\nAPCA_API_SECRET_KEY=fixture-secret\n")
        os.chmod(path, 0o644)
        with self.assertRaisesRegex(SafetyErrorAlways, "credential_file_permissions"):
            credentials(path)
        with self.assertRaisesRegex(self.market_research.ResearchError, "credential_file_permissions"):
            self.market_research.credentials(path)


def _scratch_registry(root):
    """A minimal, self-contained registry.json + source-hashes.json whose
    single (disabled) entry references a trivial scratch module -- avoids
    depending on the real strategies_v1.py's pinned hash (a separate,
    coordinator-owned repin step; see leverage.py's module docstring and
    this task's own file-editing scope), the same pattern already used by
    test_run_native_uses_the_load_config_validated_registry_not_the_default
    above. load_config only needs *a* validly hash-pinned, syntactically
    valid registry to pass strategy_pool_and_selector's fail-fast check;
    it does not need the shipped strategies_v1.py module specifically."""
    root = Path(root)
    module_bytes = b"x = 1\n"
    (root / "mod.py").write_bytes(module_bytes)
    (root / "source-hashes.json").write_text(
        json.dumps({"mod.py": hashlib.sha256(module_bytes).hexdigest()}))
    receipt_bytes = b"{}"
    (root / "receipt.json").write_bytes(receipt_bytes)
    entry = {"id": "scratch", "module": "mod", "receipt_path": "receipt.json",
             "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
             "evidence_class": "SYN", "sessions": ["regular"], "enabled": False}
    registry_path = root / "registry.json"
    registry_path.write_text(json.dumps({"schema_version": 1, "strategies": [entry]}))
    return registry_path


class LeverageLoadConfigTests(unittest.TestCase):
    """G-e: load_config's opt-in leverage_policy gate (runner.py E1)."""

    def test_default_configs_unaffected(self):
        with tempfile.TemporaryDirectory() as root:
            registry_path = _scratch_registry(root)
            for name in ("config.json", "config-sip.json"):
                config, risk, policy = runner_module.load_config(SOURCE / name, registry_path=registry_path)
                self.assertIsNone(risk.leverage)
                self.assertIsNone(policy.leverage_policy_id)
                self.assertNotIn("_leverage_policy", config)

    def test_max_leverage_2_without_block_still_refused(self):
        with tempfile.TemporaryDirectory() as root:
            registry_path = _scratch_registry(root)
            raw = json.loads((SOURCE / "config.json").read_text())
            raw["max_leverage"] = "2"
            path = Path(root) / "config.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "unqualified_lane_configuration"):
                runner_module.load_config(path, registry_path=registry_path)

    def test_valid_2x_and_4x_blocks_load(self):
        with tempfile.TemporaryDirectory() as root:
            registry_path = _scratch_registry(root)
            for name, lev in (("config-leverage-2x.json", "2"), ("config-leverage-4x.json", "4")):
                config, risk, policy = runner_module.load_config(SOURCE / name, registry_path=registry_path)
                self.assertEqual(str(risk.leverage.max_leverage), lev)
                self.assertEqual(policy.leverage_policy_id, risk.leverage.version)
                self.assertIs(config["_leverage_policy"], risk.leverage)

    def test_invalid_block_raises_specific_leverage_policy_error_code(self):
        import leverage as lev
        with tempfile.TemporaryDirectory() as root:
            registry_path = _scratch_registry(root)
            raw = json.loads((SOURCE / "config-leverage-2x.json").read_text())
            raw["leverage_policy"]["version"] = "wrong"
            path = Path(root) / "config.json"
            path.write_text(json.dumps(raw))
            with self.assertRaises(lev.LeveragePolicyError) as ctx:
                runner_module.load_config(path, registry_path=registry_path)
            self.assertEqual(str(ctx.exception), "leverage_policy_version_mismatch")


class LeverageRungConfigConsistencyTests(unittest.TestCase):
    """G-e Sec.5: rung configs differ from config-sip.json only in the
    documented keys, share one identical canonical leverage_policy block,
    and every widened numeric key satisfies its documented relationship."""

    # F2 (round 2): max_gross_loss_usd/max_drawdown_usd now scale with each
    # rung's leverage multiple (see config-leverage-*.json's notes), so they
    # join the other per-rung-widened keys here.
    ALLOWED_DIFF_KEYS = {"max_leverage", "max_gross_exposure_usd", "max_order_notional_usd",
                         "max_order_quantity", "max_order_qty_mode", "leverage_policy", "notes",
                         "max_gross_loss_usd", "max_drawdown_usd"}

    def test_rungs_differ_only_in_allowed_keys(self):
        import leverage as lev
        base = json.loads((SOURCE / "config-sip.json").read_text())
        for name in ("config-leverage-1x.json", "config-leverage-2x.json", "config-leverage-4x.json"):
            c = json.loads((SOURCE / name).read_text())
            diff = {k for k in set(base) | set(c) if base.get(k) != c.get(k)}
            self.assertLessEqual(diff, self.ALLOWED_DIFF_KEYS, name)
            self.assertEqual(c["leverage_policy"], lev.CANONICAL_V1_BLOCK, name)

    def test_leverage_policy_blocks_identical_across_rungs(self):
        blocks = [json.loads((SOURCE / n).read_text())["leverage_policy"]
                 for n in ("config-leverage-1x.json", "config-leverage-2x.json", "config-leverage-4x.json")]
        self.assertEqual(blocks[0], blocks[1])
        self.assertEqual(blocks[1], blocks[2])

    def test_rung_numeric_relationships(self):
        base = json.loads((SOURCE / "config-sip.json").read_text())
        for name, multiple in (("config-leverage-1x.json", 1), ("config-leverage-2x.json", 2),
                               ("config-leverage-4x.json", 4)):
            c = json.loads((SOURCE / name).read_text())
            capital = Decimal(c["capital_usd"])
            self.assertEqual(Decimal(c["max_gross_exposure_usd"]), capital * multiple)
            self.assertEqual(Decimal(c["max_order_notional_usd"]),
                             Decimal(c["max_gross_exposure_usd"]) / c["max_held_symbols"])
            # F2 (round 2): max_gross_loss_usd/max_drawdown_usd scale with
            # the rung's leverage multiple (base config-sip.json's $25 x
            # multiple) so the fraction of the cap a given entry-spread
            # mark-to-market loss consumes -- and thus the drawdown
            # ladder's runway before the hard halt -- is the same at every
            # rung; see config-leverage-*.json's notes.
            self.assertEqual(Decimal(c["max_gross_loss_usd"]), Decimal(base["max_gross_loss_usd"]) * multiple)
            self.assertEqual(Decimal(c["max_drawdown_usd"]), Decimal(base["max_drawdown_usd"]) * multiple)
            self.assertEqual(c["max_order_qty_mode"], "notional")

    def test_rung_loss_cap_absorbs_full_gross_spread_cost_with_ladder_room(self):
        """F2 (round 2): the scaled max_drawdown_usd must leave the
        drawdown ladder room to step down (not an immediate hard halt) when
        the rung's full gross exposure is marked at the worst allowed entry
        spread -- the exact scenario the round-1 finding named (entry
        spread on ~$40k gross could trip the $25 hard halt before 4x
        exposure was ever shown)."""
        for name, multiple in (("config-leverage-1x.json", 1), ("config-leverage-2x.json", 2),
                               ("config-leverage-4x.json", 4)):
            c = json.loads((SOURCE / name).read_text())
            gross = Decimal(c["max_gross_exposure_usd"])
            spread_cost = gross * Decimal(c["max_spread_bps"]) / Decimal("10000")
            max_drawdown = Decimal(c["max_drawdown_usd"])
            self.assertLess(spread_cost, max_drawdown, name)
            drawdown_fraction = spread_cost / max_drawdown
            # Still inside the ladder (below the 75% -> 0x step, and well
            # below the 100% hard halt), so de-leveraging, not an immediate
            # halt, is what the worst-case entry spread alone can trigger.
            self.assertLess(drawdown_fraction, Decimal("0.75"), name)

    def test_rung_max_order_quantity_matches_engine_share_ceiling(self):
        """F2: max_order_quantity must not undercut max_order_qty_mode
        ='notional' below its own designed ceiling -- PolicyConfig.max_shares
        (strategies_v1.py) and RiskLimits.max_order_qty (safety.py) both cap
        an order at 100 shares; a rung's max_order_quantity of 10 silently
        capped effective_max_order_qty's min(max_order_qty, notional/price,
        100) at 10 for any symbol priced above max_order_notional_usd/10,
        making the schedule's notional ceiling unreachable for most of the
        symbol universe (see config-leverage-4x.json's notes)."""
        for name in ("config-leverage-1x.json", "config-leverage-2x.json", "config-leverage-4x.json"):
            c = json.loads((SOURCE / name).read_text())
            self.assertEqual(c["max_order_quantity"], 100, name)
            # A $50 stock at this rung's max_order_notional_usd should be
            # sizeable to (near) the full notional, not truncated to 10
            # shares ($500) the way max_order_quantity=10 would have forced.
            notional = Decimal(c["max_order_notional_usd"])
            implied_shares_at_50 = int(notional / Decimal("50"))
            self.assertGreater(min(c["max_order_quantity"], implied_shares_at_50, 100), 10, name)

    def test_rung_policy_config_max_order_notional_matches_configured_value(self):
        """CX-P2 (2026-09-22 leverage fix round 1): PolicyConfig.max_order_notional
        (strategies_v1.py's own entry-allocation clamp) used to silently keep
        its 1000 default regardless of each rung's larger configured
        max_order_notional_usd (RiskLimits already received it) -- entries
        could then never size up to what the ledger-side cap would allow.
        load_config's returned PolicyConfig must carry the exact configured
        value for every shipped config, not just the default-1000 ones."""
        with tempfile.TemporaryDirectory() as root:
            registry_path = _scratch_registry(root)
            for name in ("config.json", "config-sip.json", "config-leverage-1x.json",
                        "config-leverage-2x.json", "config-leverage-4x.json"):
                config, _, policy = runner_module.load_config(SOURCE / name, registry_path=registry_path)
                self.assertEqual(policy.max_order_notional, float(config["max_order_notional_usd"]), name)

    def test_policy_config_accepts_the_widened_100_share_ceiling_under_leverage_policy(self):
        """F2: strategies_v1.PolicyConfig must allow max_shares up to 100
        (matching safety.RiskLimits.max_order_qty's own <=100 bound and
        effective_max_order_qty's hard 100-share ceiling), not the old
        (undocumented, tighter) 10-share validation ceiling -- but only
        under the opt-in canonical leverage policy (N1-0, round 2): the
        widened ceiling must not loosen the default (no leverage_policy_id)
        path, which keeps the original 10-share bound below."""
        import strategies_v1
        symbols = ("SPY", "QQQ", "IWM", "DIA")
        config = strategies_v1.PolicyConfig(symbols=symbols, max_positions=len(symbols), max_shares=100,
                                            leverage_policy_id=strategies_v1.LEVERAGE_POLICY_VERSION)
        self.assertEqual(config.max_shares, 100)
        with self.assertRaises(ValueError):
            strategies_v1.PolicyConfig(symbols=symbols, max_positions=len(symbols), max_shares=101,
                                       leverage_policy_id=strategies_v1.LEVERAGE_POLICY_VERSION)

    def test_policy_config_keeps_the_10_share_bound_without_leverage_policy(self):
        """N1-0 (round 2): a config with no leverage_policy block (the
        default, no leverage_policy_id) must keep the original 10-share
        max_shares ceiling -- F2 (round 1) widened this to 100
        unconditionally, which silently accepted a no-policy
        max_order_quantity in [11, 100] that the pre-F2 validation refused
        with invalid_policy_bounds (runner.py's load_config passes
        max_order_quantity straight through as max_shares)."""
        import strategies_v1
        symbols = ("SPY", "QQQ", "IWM", "DIA")
        config = strategies_v1.PolicyConfig(symbols=symbols, max_positions=len(symbols), max_shares=10)
        self.assertEqual(config.max_shares, 10)
        with self.assertRaises(ValueError):
            strategies_v1.PolicyConfig(symbols=symbols, max_positions=len(symbols), max_shares=11)


class AchievedLeverageReceiptStepTests(unittest.TestCase):
    """F2 (2026-09-22 residual review, reachability): pure unit tests for
    runner._leverage_achievement_step, the per-tick state update behind
    outcome["leverage"]'s peak_achieved_leverage/ceiling_at_peak_achieved_leverage/
    seconds_above_next_lower_rung_ceiling fields. `strategies_v1._decide_core`'s
    budget/inverse-volatility allocation means a rung's higher max_leverage
    does not by construction force higher achieved exposure, so a "4x"
    receipt could previously pass (needs_attention == 0) without ever
    showing exposure above the 2x rung's own ceiling; this step function is
    what now records whether it actually did."""

    def _initial(self):
        return dict(runner_module._INITIAL_LEVERAGE_ACHIEVEMENT_STATE)

    def test_first_tick_records_peak_and_ceiling_with_no_time_above_yet(self):
        # dt_seconds=0 on the very first tick this run observed -- there is
        # no preceding tick to measure an elapsed interval against, so
        # nothing is attributed to seconds_above even though 3.5 already
        # exceeds the next-lower (2x) rung's ceiling.
        state = runner_module._leverage_achievement_step(
            self._initial(), dt_seconds=0.0, achieved_leverage=Decimal("3.5"),
            ceiling=Decimal("4"), next_lower_ceiling=Decimal("2"))
        self.assertEqual(state["peak_achieved_leverage"], Decimal("3.5"))
        self.assertEqual(state["ceiling_at_peak"], Decimal("4"))
        self.assertEqual(state["seconds_above_next_lower_rung_ceiling"], 0.0)

    def test_time_accumulates_only_while_above_next_lower_ceiling(self):
        state = self._initial()
        state = runner_module._leverage_achievement_step(
            state, dt_seconds=1.0, achieved_leverage=Decimal("1.5"),
            ceiling=Decimal("4"), next_lower_ceiling=Decimal("2"))
        self.assertEqual(state["seconds_above_next_lower_rung_ceiling"], 0.0)
        state = runner_module._leverage_achievement_step(
            state, dt_seconds=1.0, achieved_leverage=Decimal("2.5"),
            ceiling=Decimal("4"), next_lower_ceiling=Decimal("2"))
        self.assertEqual(state["seconds_above_next_lower_rung_ceiling"], 1.0)
        state = runner_module._leverage_achievement_step(
            state, dt_seconds=0.5, achieved_leverage=Decimal("3.0"),
            ceiling=Decimal("4"), next_lower_ceiling=Decimal("2"))
        self.assertEqual(state["seconds_above_next_lower_rung_ceiling"], 1.5)
        # Dropping back below the threshold stops further accumulation but
        # does not erase what was already recorded.
        state = runner_module._leverage_achievement_step(
            state, dt_seconds=2.0, achieved_leverage=Decimal("1.0"),
            ceiling=Decimal("4"), next_lower_ceiling=Decimal("2"))
        self.assertEqual(state["seconds_above_next_lower_rung_ceiling"], 1.5)

    def test_exactly_at_next_lower_ceiling_does_not_count_as_above(self):
        state = runner_module._leverage_achievement_step(
            self._initial(), dt_seconds=1.0, achieved_leverage=Decimal("2"),
            ceiling=Decimal("4"), next_lower_ceiling=Decimal("2"))
        self.assertEqual(state["seconds_above_next_lower_rung_ceiling"], 0.0)

    def test_no_next_lower_ceiling_never_accumulates(self):
        """A None threshold (leverage.next_lower_rung_ceiling for a value
        below the lowest rung; since audit gap #5 the 1x rung itself is
        compared against leverage.ONE_X_MINIMUM_EXPOSURE, 0.5) never
        accumulates, whatever dt/achieved leverage is observed."""
        state = self._initial()
        for _ in range(5):
            state = runner_module._leverage_achievement_step(
                state, dt_seconds=1.0, achieved_leverage=Decimal("1.0"),
                ceiling=Decimal("1"), next_lower_ceiling=None)
        self.assertEqual(state["seconds_above_next_lower_rung_ceiling"], 0.0)

    def test_peak_and_its_ceiling_snapshot_never_move_backward(self):
        state = runner_module._leverage_achievement_step(
            self._initial(), dt_seconds=0.0, achieved_leverage=Decimal("2.0"),
            ceiling=Decimal("2"), next_lower_ceiling=Decimal("1"))
        self.assertEqual(state["peak_achieved_leverage"], Decimal("2.0"))
        self.assertEqual(state["ceiling_at_peak"], Decimal("2"))
        # A later, lower-achieved tick (even under a higher ceiling) must
        # not move the recorded peak or the ceiling snapshot taken with it.
        state = runner_module._leverage_achievement_step(
            state, dt_seconds=1.0, achieved_leverage=Decimal("1.0"),
            ceiling=Decimal("4"), next_lower_ceiling=Decimal("1"))
        self.assertEqual(state["peak_achieved_leverage"], Decimal("2.0"))
        self.assertEqual(state["ceiling_at_peak"], Decimal("2"))

    def test_nonpositive_dt_never_accumulates(self):
        state = runner_module._leverage_achievement_step(
            self._initial(), dt_seconds=1.0, achieved_leverage=Decimal("3"),
            ceiling=Decimal("4"), next_lower_ceiling=Decimal("2"))
        before = state["seconds_above_next_lower_rung_ceiling"]
        self.assertGreater(before, 0.0)
        for bad_dt in (0.0, -0.3):
            state = runner_module._leverage_achievement_step(
                state, dt_seconds=bad_dt, achieved_leverage=Decimal("3"),
                ceiling=Decimal("4"), next_lower_ceiling=Decimal("2"))
            self.assertEqual(state["seconds_above_next_lower_rung_ceiling"], before)


class AchievedLeverageGateTraceTests(unittest.TestCase):
    """Audit gap #5 (2026-09-24): per-tick achieved-leverage traces folded
    through runner._leverage_achievement_step with each rung's
    leverage.next_lower_rung_ceiling threshold, serialized the way
    run_native's outcome["leverage"] block writes them, and judged by the
    repository's leverage-ladder gate rows through scripts/trading_gates.py.
    Pure and offline: no paper trial, no broker."""

    @classmethod
    def setUpClass(cls):
        scripts = str(SOURCE.parents[2] / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import trading_gates
        cls.gates = trading_gates
        document = trading_gates.load_json(SOURCE.parents[2] / trading_gates.GATES)
        cls.gates_by_id = {gate["id"]: gate for gate in document["gates"]}

    def _receipt(self, rung, trace, tick_seconds=0.1):
        import leverage
        max_leverage = Decimal(rung)
        threshold = leverage.next_lower_rung_ceiling(max_leverage)
        state = dict(runner_module._INITIAL_LEVERAGE_ACHIEVEMENT_STATE)
        for index, achieved in enumerate(trace):
            state = runner_module._leverage_achievement_step(
                state, dt_seconds=0.0 if index == 0 else tick_seconds, achieved_leverage=Decimal(achieved),
                ceiling=max_leverage, next_lower_ceiling=threshold)
        # Mirrors run_native's outcome["leverage"] serialization of these fields.
        block = {"config_max_leverage": str(max_leverage),
                 "next_lower_rung_ceiling": str(threshold) if threshold is not None else None,
                 "peak_achieved_leverage": str(state["peak_achieved_leverage"]),
                 "ceiling_at_peak_achieved_leverage": str(state["ceiling_at_peak"]),
                 "seconds_above_next_lower_rung_ceiling": state["seconds_above_next_lower_rung_ceiling"]}
        # A synthetic stand-in for the certified run's committed paper-output.json,
        # which the gate's source_matches member binds the receipt to by sha256.
        source = (json.dumps({"status": "passed", "leverage": block}, indent=2, sort_keys=True) + "\n").encode("utf-8")
        digest = hashlib.sha256(source).hexdigest()
        path = f"blueprints/us-equities/adaptive-paper/ladder/{rung}x/trace-{digest[:12]}/paper-output.json"
        self._sources[path] = source
        return {"schema_version": 1, "kind": "leverage_ladder_rung_receipt", "rung": f"{rung}x", "needs_attention": 0,
                "source": {"paper_output_path": path, "paper_output_sha256": digest, "certified_run_status": "passed"},
                "leverage": json.loads(json.dumps(block))}

    def setUp(self):
        self._sources = {}

    def _holds(self, rung, receipt):
        gate = {**self.gates_by_id[f"leverage-ladder-{rung}x"], "status": "not_established", "evidence_class": "none"}
        with tempfile.TemporaryDirectory() as root:
            for relative, data in self._sources.items():
                (Path(root) / relative).parent.mkdir(parents=True, exist_ok=True)
                (Path(root) / relative).write_bytes(data)
            path = Path(root) / gate["receipt_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(receipt), encoding="utf-8")
            return self.gates.condition_holds(Path(root), gate)

    def test_trial_that_never_exceeds_the_lower_cap_does_not_satisfy_the_rung(self):
        # Clean (needs_attention 0) trials whose exposure rises to, but never
        # past, the next-lower cap: 0.5x for 1x, 1x for 2x, 2x for 4x.
        traces = {"1": ["0", "0.2", "0.45", "0.5", "0.5", "0.3"],
                  "2": ["0", "0.6", "1", "1", "0.9"],
                  "4": ["0", "1.5", "2", "2", "1.8"]}
        for rung, trace in traces.items():
            with self.subTest(rung=rung):
                receipt = self._receipt(rung, trace)
                self.assertEqual(receipt["leverage"]["seconds_above_next_lower_rung_ceiling"], 0.0)
                holds, detail = self._holds(rung, receipt)
                self.assertFalse(holds, detail)
                # Only the achievement members fail; the receipt is otherwise well formed and bound.
                self.assertIn("2 of 10 failed", detail)
                self.assertNotIn("source_matches", detail)

    def test_trial_that_exceeds_the_lower_cap_satisfies_the_rung(self):
        traces = {"1": ["0", "0.4", "0.62", "0.7", "0.4"],
                  "2": ["0", "1.2", "1.6", "0.8"],
                  "4": ["0", "2.5", "3.4", "1.9"]}
        for rung, trace in traces.items():
            with self.subTest(rung=rung):
                receipt = self._receipt(rung, trace)
                self.assertGreater(receipt["leverage"]["seconds_above_next_lower_rung_ceiling"], 0.0)
                holds, detail = self._holds(rung, receipt)
                self.assertTrue(holds, detail)

    def test_a_single_first_tick_above_the_cap_records_no_time_and_does_not_satisfy(self):
        # The first tick has no preceding interval (dt 0), so a peak observed
        # only there accrues no seconds_above; the peak alone is not enough.
        receipt = self._receipt("2", ["1.5", "0.5"])
        self.assertEqual(receipt["leverage"]["peak_achieved_leverage"], "1.5")
        self.assertEqual(receipt["leverage"]["seconds_above_next_lower_rung_ceiling"], 0.0)
        holds, detail = self._holds("2", receipt)
        self.assertFalse(holds, detail)


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class AchievedLeverageReceiptIntegrationTests(unittest.TestCase):
    """F2 (2026-09-22 residual review, reachability): outcome["leverage"]'s
    achieved-leverage fields, driven through run_native end-to-end (not
    just the pure step function above) against the shipped rung configs."""

    def _pinned_rth_session(self):
        """EH-3/N1-0 (2026-09-22 leverage fix round 2): these achieved-
        leverage assertions only hold while the run actually executes
        during a session the canonical schedule (leverage.py's
        CANONICAL_V1_BLOCK) gives a >1x trend ceiling to -- RTH. Nothing
        upstream pinned the wall clock for this class (the only session_at
        pins in this file were _held_ledger-adjacent, near lines 140 and
        1285), so left unpinned this class only passed while it happened to
        run during a 2026 RTH session on the real clock, and failed closed
        to a <=1x ceiling (PRE/POST) or 0x (CLOSED, or any date outside the
        2026 calendar) the rest of the time: native_strategy._leverage_
        inputs and safety.Ledger._leverage_envelope both classify
        time.time() through their own session_at/_session_at import, and
        leverage.py's ceiling()/envelope() fail closed to 0 on
        session=None.

        Mirrors the pinning pattern used near line 1285
        (test_main_refuses_held_resume_when_broker_holds_what_the_ledger_
        does_not): the `ts` argument is ignored entirely and every
        session_at() lookup this run's three call sites can make --
        runner.py's own loop, native_strategy._leverage_inputs and
        safety.Ledger._leverage_envelope, each importing session_at
        separately -- resolves against one fixed real RTH instant
        regardless of when this test actually runs. Real elapsed time
        (time.monotonic() loop control, the time.time()-based dt the
        achieved-leverage accumulator uses) is left untouched, since only
        the session classification is intercepted here, not the clock
        itself.
        """
        from contextlib import ExitStack
        from datetime import datetime as _dt, timezone as _tz
        from zoneinfo import ZoneInfo
        frozen = _dt(2026, 3, 10, 11, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(_tz.utc)
        real_session_at = runner_module.session_at
        stack = ExitStack()
        stack.enter_context(patch.object(runner_module, "session_at", lambda _ts: real_session_at(frozen)))
        stack.enter_context(patch.object(native_strategy_module, "session_at",
                                         lambda _ts: real_session_at(frozen)))
        stack.enter_context(patch.object(safety_module, "_session_at", lambda _ts: real_session_at(frozen)))
        # Deterministic regime: this class covers the achieved-leverage receipt, not regime
        # classification. With 0.02 s sampling on the real clock the benchmark momentum and
        # feature completeness depend on machine load (observed: only range/unavailable,
        # so a 2x rung capped at 1x). Any complete, non-risk_off sample is treated as trend.
        import statistics
        import strategies_v1 as strategies_v1_module
        original = strategies_v1_module.AdaptivePolicy._regime_and_signals

        def trend_when_complete(policy_self, now):
            features, complete, risk_off, regime, signals = original(policy_self, now)
            if complete and not risk_off and regime != "trend":
                benchmarks = [features[s] for s in policy_self.config.benchmarks if s in features]
                benchmark_return = statistics.mean(f["return"] for f in benchmarks) if benchmarks else 0
                regime = "trend"
                signals = policy_self._signals(features, regime, benchmark_return)
            return features, complete, risk_off, regime, signals

        stack.enter_context(patch.object(strategies_v1_module.AdaptivePolicy, "_regime_and_signals",
                                         trend_when_complete))
        return stack

    def _fast_leveraged_policy(self, name, root):
        registry_path = _scratch_registry(root)
        config, risk, policy = runner_module.load_config(SOURCE / name, registry_path=registry_path)
        config.update(duration_seconds=2, cleanup_seconds=2, order_timeout_seconds=1)
        # EH-3 (2026-09-22 leverage fix round 1): use load_config's own
        # `risk` (it carries the rung's actual RiskLimits.leverage, gross
        # cap and notional-mode order sizing) instead of a bare
        # `RiskLimits(trial_seconds=2, cleanup_seconds=2)`, which kept every
        # other field at its class default -- leverage=None (so
        # safety.Ledger._leverage_envelope was never even consulted),
        # max_gross_exposure_usd=$5000 and max_order_qty=1 share fixed --
        # under which every rung's ledger behaved identically to the
        # unleveraged default and could never show achieved exposure above
        # about 0.5x of capital, so this test could not have caught a
        # regression in the achieved-leverage tracking it exists to cover.
        risk = replace(risk, trial_seconds=2, cleanup_seconds=2)
        policy = replace(policy, warmup_samples=4, warmup_seconds=.06, sample_seconds=.02,
                         rebalance_seconds=.02, min_hold_seconds=.05, max_hold_seconds=.4,
                         cooldown_seconds=.05)
        return config, risk, policy

    def test_leveraged_run_records_the_achieved_leverage_receipt_fields(self):
        with self._pinned_rth_session(), tempfile.TemporaryDirectory() as root:
            config, limits, policy = self._fast_leveraged_policy("config-leverage-1x.json", root)
            ledger = Ledger(Path(root) / "journal.db", limits)
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            def price(symbol, tick):
                slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
                return Decimal("100") + min(tick, 70) * slope
            port = SimulatedPort(controller, policy.symbols, price=price)
            controller.port = port
            result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                            "fixture", config, "100000"))
            self.assertIn("leverage", result, result)
            lev = result["leverage"]
            # Every field this task adds is present alongside the
            # already-shipped ones.
            for key in ("next_lower_rung_ceiling", "peak_achieved_leverage",
                       "ceiling_at_peak_achieved_leverage", "seconds_above_next_lower_rung_ceiling"):
                self.assertIn(key, lev, lev)
            # The 1x rung has no lower rung; since audit gap #5 (2026-09-24)
            # its threshold is the documented 0.5x minimum exposure
            # (leverage.ONE_X_MINIMUM_EXPOSURE), which the leverage-ladder-1x
            # gate's flip condition requires peak_achieved_leverage and
            # seconds_above_next_lower_rung_ceiling to exceed.
            self.assertEqual(lev["next_lower_rung_ceiling"], "0.5")
            self.assertGreaterEqual(lev["seconds_above_next_lower_rung_ceiling"], 0.0)
            peak_achieved = Decimal(lev["peak_achieved_leverage"])
            ceiling_at_peak = Decimal(lev["ceiling_at_peak_achieved_leverage"])
            self.assertTrue(peak_achieved.is_finite())
            self.assertGreaterEqual(peak_achieved, Decimal("0"))
            # The 1x rung's policy-layer ceiling never exceeds 1.
            self.assertLessEqual(ceiling_at_peak, Decimal("1"))
            ledger.close()

    def test_2x_rung_next_lower_ceiling_is_the_1x_rung(self):
        with self._pinned_rth_session(), tempfile.TemporaryDirectory() as root:
            config, limits, policy = self._fast_leveraged_policy("config-leverage-2x.json", root)
            ledger = Ledger(Path(root) / "journal.db", limits)
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            def price(symbol, tick):
                slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
                return Decimal("100") + min(tick, 70) * slope
            port = SimulatedPort(controller, policy.symbols, price=price)
            controller.port = port
            result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                            "fixture", config, "100000"))
            lev = result["leverage"]
            self.assertEqual(lev["next_lower_rung_ceiling"], "1")
            self.assertGreaterEqual(lev["seconds_above_next_lower_rung_ceiling"], 0.0)
            # EH-3: with the ledger actually wired to this rung's leverage
            # policy (see _fast_leveraged_policy), SimulatedPort's immediate
            # fills let the strategy build filled positions past 1x of
            # capital inside this short trial -- exercising the real
            # achieved-leverage path this receipt exists to evidence,
            # instead of a ledger whose $5000 default gross cap could never
            # let achieved exposure clear about 0.5x. N1-0/EH-3 (round 2):
            # _pinned_rth_session above pins this at a real RTH instant so
            # the schedule's RTH/trend ceiling (4) -- not PRE/POST/CLOSED's
            # <=1x -- is actually in force, independent of when this test
            # happens to run.
            peak_achieved = Decimal(lev["peak_achieved_leverage"])
            self.assertGreater(peak_achieved, Decimal("1"), lev)
            self.assertGreater(lev["seconds_above_next_lower_rung_ceiling"], 0.0, lev)
            ledger.close()

    def test_resting_unfilled_buy_orders_do_not_count_as_achieved_leverage(self):
        """EH-3 (round 2, second half): the guarantee runner.py's EH-1 fix
        establishes -- filled_gross_exposure_usd excludes every not-yet-
        filled buy intent's notional (runner.py's `filled_gross_exposure_
        usd = acct_now.gross_exposure_usd - acct_now.pending_buy_notional_
        usd`) -- was previously untested at the run_native level: nothing
        in this file ever reads peak_pending_buy_notional_usd, and
        SimulatedPort.submit fills every order synchronously and
        immediately, so no existing test could tell this apart from the
        pre-EH-1 code (reverting to the raw gross_exposure_usd, which
        folds a resting buy's notional straight into achieved exposure,
        passed every other integration test here).

        This test replaces SimulatedPort.submit with a variant that walks
        the exact same admissions/observation path as the real submit()
        (Controller.before_submit -> ledger.reserve_intent,
        Controller.observe -> ledger.record_order, and the port's own
        on_order callback -> native_adapter's nautilus-event generation --
        so this is a broker acknowledgment, not a dropped/unmodeled
        submission) except the order is acknowledged at broker status
        "new" with filled_qty "0" and self.cash/self.positions are never
        updated. The intent's ledger status advances reserved -> new
        (still not in safety.TERMINAL, per safety.RANK/record_order) and
        stays there for the run's whole duration: a genuinely resting,
        unfilled buy order, not a synchronously-filled one.
        """
        from simulation import invoke as _invoke
        with self._pinned_rth_session(), tempfile.TemporaryDirectory() as root:
            config, limits, policy = self._fast_leveraged_policy("config-leverage-2x.json", root)
            ledger = Ledger(Path(root) / "journal.db", limits)
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            def price(symbol, tick):
                slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
                return Decimal("100") + min(tick, 70) * slope
            port = SimulatedPort(controller, policy.symbols, price=price)

            async def submit_resting(payload):
                """Mirrors SimulatedPort.submit exactly except it
                acknowledges (status "new", filled_qty "0") instead of
                filling, and never touches self.cash/self.positions."""
                port.controller.before_submit(payload)
                await port.controller.before_request("submit", client_id=payload["client_order_id"])
                port.submitted_at.append(time.time())
                order = dict(payload, id=f"sim-{len(port.orders) + 1}", status="new",
                            filled_qty="0", filled_avg_price=None, updated_at_ns=time.time_ns())
                port.orders[payload["client_order_id"]] = order
                port.controller.observe(order)
                await _invoke(port.on_order, dict(order))
                return dict(order)

            port.submit = submit_resting
            controller.port = port
            result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                            "fixture", config, "100000"))
            self.assertIn("leverage", result, result)
            lev = result["leverage"]
            # A buy was actually attempted and reserved (otherwise this
            # test proves nothing): some resting notional was seen.
            self.assertGreater(Decimal(lev["peak_pending_buy_notional_usd"]), Decimal("0"), lev)
            # None of it ever filled, so achieved leverage/exposure must
            # stay at exactly zero -- this is the assertion that catches a
            # revert of runner.py's EH-1 fix back to the raw (fill-blind)
            # gross_exposure_usd.
            self.assertEqual(lev["peak_gross_exposure_usd"], "0")
            self.assertEqual(Decimal(lev["peak_achieved_leverage"]), Decimal("0"), lev)
            ledger.close()

    def test_default_path_outcome_has_no_leverage_key(self):
        """The absence half of this task's acceptance: a run with no
        leverage_policy (both shipped default configs) must not gain this
        section at all -- outcome/receipt shape is otherwise unchanged
        (D1/F2 default-path-byte-identical requirement)."""
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
            port = SimulatedPort(controller, policy.symbols)
            controller.port = port
            result = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                            "fixture", config, "100000"))
            self.assertNotIn("leverage", result, result)
            ledger.close()


class LeverageMarginEntitlementTests(unittest.TestCase):
    """G-e E8: runner._check_margin_entitlement (pure, no network)."""

    def leverage_policy(self, max_leverage="4"):
        import leverage as lev
        config = {"max_leverage": max_leverage, "capital_usd": "10000",
                  "max_gross_exposure_usd": str(10000 * int(max_leverage)),
                  "leverage_policy": lev.CANONICAL_V1_BLOCK}
        session_policy = {"overnight_holds": False, "overnight_gross_multiple": Decimal("1.0")}
        return lev.validate_leverage_policy(config, session_policy)

    def config(self, max_leverage="4"):
        return {"max_gross_exposure_usd": str(10000 * int(max_leverage)), "capital_usd": "10000"}

    def account(self, **overrides):
        account = {"multiplier": "4", "daytrading_buying_power": "40000",
                  "regt_buying_power": "20000", "equity": "10000", "pattern_day_trader": False}
        account.update(overrides)
        return account

    def test_missing_margin_fields_refused(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "account_margin_fields_missing"):
            runner_module._check_margin_entitlement({"equity": "10000"}, self.config(),
                                                     self.leverage_policy(), {"overnight_holds": False})

    def test_multiplier_below_requested_refused(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "account_multiplier_below_requested_leverage"):
            runner_module._check_margin_entitlement(self.account(multiplier="2"), self.config(),
                                                     self.leverage_policy("4"), {"overnight_holds": False})

    def test_daytrading_buying_power_insufficient_refused(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "account_daytrading_buying_power_insufficient"):
            runner_module._check_margin_entitlement(self.account(daytrading_buying_power="100"), self.config(),
                                                     self.leverage_policy("4"), {"overnight_holds": False})

    def test_regt_buying_power_insufficient_refused_when_overnight_holds(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "account_regt_buying_power_insufficient"):
            runner_module._check_margin_entitlement(self.account(regt_buying_power="100"), self.config(),
                                                     self.leverage_policy("2"), {"overnight_holds": True})

    def test_pdt_with_low_equity_refused(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "account_restricted"):
            runner_module._check_margin_entitlement(
                self.account(pattern_day_trader=True, equity="10000"), self.config(),
                self.leverage_policy("4"), {"overnight_holds": False})

    def current_schema_account(self, **overrides):
        # Alpaca's GetAccount schema after FINRA's intraday margin rule: no
        # daytrading_buying_power, pattern_day_trader or daytrade_count.
        account = {"multiplier": "4", "buying_power": "40000", "regt_buying_power": "20000", "equity": "10000",
                   "maintenance_margin": "0"}
        account.update(overrides)
        return account

    def test_current_alpaca_schema_uses_buying_power(self):
        mult = runner_module._check_margin_entitlement(self.current_schema_account(), self.config(),
                                                        self.leverage_policy("4"), {"overnight_holds": False})
        self.assertEqual(mult, Decimal("4"))
        self.assertEqual(runner_module.intraday_buying_power(self.current_schema_account()), ("40000", "buying_power"))
        self.assertEqual(runner_module.intraday_buying_power(self.account()), ("40000", "daytrading_buying_power"))

    def test_current_alpaca_schema_insufficient_buying_power_refused(self):
        with self.assertRaisesRegex(SafetyErrorAlways, "account_daytrading_buying_power_insufficient"):
            runner_module._check_margin_entitlement(self.current_schema_account(buying_power="100"), self.config(),
                                                     self.leverage_policy("4"), {"overnight_holds": False})

    def test_buying_power_is_bounded_by_current_equity(self):
        # A stale or prior-close buying_power can never admit more than current equity supports.
        account = self.current_schema_account(buying_power="40000", equity="10000", maintenance_margin="5000")
        self.assertEqual(runner_module.intraday_buying_power(account),
                         ("20000", "multiplier*(equity-maintenance_margin)"))
        with self.assertRaisesRegex(SafetyErrorAlways, "account_daytrading_buying_power_insufficient"):
            runner_module._check_margin_entitlement(account, self.config(), self.leverage_policy("4"),
                                                     {"overnight_holds": False})
        consistent = self.current_schema_account(buying_power="40000", equity="10000", maintenance_margin="0")
        self.assertEqual(runner_module.intraday_buying_power(consistent), ("40000", "buying_power"))

    def test_bound_is_required_and_applies_to_the_legacy_field_too(self):
        no_margin = self.current_schema_account()
        del no_margin["maintenance_margin"]
        self.assertIsNone(runner_module.intraday_buying_power(no_margin))
        with self.assertRaisesRegex(SafetyErrorAlways, "account_margin_fields_missing"):
            runner_module._check_margin_entitlement(no_margin, self.config(), self.leverage_policy("4"),
                                                     {"overnight_holds": False})
        stale_legacy = self.account(daytrading_buying_power="80000", equity="10000")
        self.assertEqual(runner_module.intraday_buying_power(stale_legacy),
                         ("40000", "multiplier*(equity-maintenance_margin)"))

    def test_no_intraday_buying_power_field_is_missing(self):
        account = self.current_schema_account()
        del account["buying_power"]
        with self.assertRaisesRegex(SafetyErrorAlways, "account_margin_fields_missing"):
            runner_module._check_margin_entitlement(account, self.config(), self.leverage_policy("4"),
                                                     {"overnight_holds": False})

    def test_sufficient_account_returns_multiplier(self):
        mult = runner_module._check_margin_entitlement(self.account(), self.config(),
                                                        self.leverage_policy("4"), {"overnight_holds": False})
        self.assertEqual(mult, Decimal("4"))


class LeveragePreflightIntegrationTests(unittest.TestCase):
    """G-e: validate_preflight's margin-entitlement gate is opt-in on
    config["_leverage_policy"] and mutates config with "_account_multiplier"
    only then; the default path (no policy) is unaffected even when the
    observed account lacks every margin field."""

    def observation(self, account_overrides=None):
        account = {"status": "ACTIVE", "currency": "USD", "trading_blocked": False,
                  "account_blocked": False, "trade_suspended_by_user": False,
                  "cash": "10000", "equity": "30000"}
        if account_overrides:
            account.update(account_overrides)
        now_ns = int(time.time() * 1e9)
        return {"account": account,
                "clock": {"is_open": True, "timestamp_ns": now_ns, "received_at_ns": now_ns,
                         "next_close_ns": now_ns + 3600 * 10**9},
                "positions": [], "orders": [],
                "assets": [{"symbol": s, "status": "active", "tradable": True}
                          for s in ("SPY", "QQQ", "IWM", "DIA")],
                "quotes": [{"symbol": s, "ts_ns": now_ns} for s in ("SPY", "QQQ", "IWM", "DIA")]}

    def test_default_config_with_margin_less_account_still_ready(self):
        config = {"capital_usd": "10000", "duration_seconds": 10, "cleanup_seconds": 5,
                  "symbols": ["SPY", "QQQ", "IWM", "DIA"], "benchmarks": ["SPY", "QQQ", "IWM", "DIA"],
                  "quote_max_age_seconds": 5}  # no "_leverage_policy" key
        validate_preflight_always(self.observation(), config, require_open=True)
        self.assertNotIn("_account_multiplier", config)

    def test_under_policy_missing_margin_fields_refused_before_other_config_state(self):
        import leverage as lev
        block = lev.CANONICAL_V1_BLOCK
        leverage_config = {"max_leverage": "4", "capital_usd": "10000",
                           "max_gross_exposure_usd": "40000", "leverage_policy": block}
        policy = lev.validate_leverage_policy(leverage_config, {"overnight_holds": False,
                                                                "overnight_gross_multiple": Decimal("1.0")})
        config = {"capital_usd": "10000", "duration_seconds": 10, "cleanup_seconds": 5,
                  "symbols": ["SPY", "QQQ", "IWM", "DIA"], "benchmarks": ["SPY", "QQQ", "IWM", "DIA"],
                  "quote_max_age_seconds": 5, "max_gross_exposure_usd": "40000", "_leverage_policy": policy}
        with self.assertRaisesRegex(SafetyErrorAlways, "account_margin_fields_missing"):
            validate_preflight_always(self.observation(), config, require_open=True)
        self.assertNotIn("_account_multiplier", config)

    def test_under_policy_sufficient_account_sets_account_multiplier(self):
        import leverage as lev
        block = lev.CANONICAL_V1_BLOCK
        leverage_config = {"max_leverage": "4", "capital_usd": "10000",
                           "max_gross_exposure_usd": "40000", "leverage_policy": block}
        policy = lev.validate_leverage_policy(leverage_config, {"overnight_holds": False,
                                                                "overnight_gross_multiple": Decimal("1.0")})
        config = {"capital_usd": "10000", "duration_seconds": 10, "cleanup_seconds": 5,
                  "symbols": ["SPY", "QQQ", "IWM", "DIA"], "benchmarks": ["SPY", "QQQ", "IWM", "DIA"],
                  "quote_max_age_seconds": 5, "max_gross_exposure_usd": "40000", "_leverage_policy": policy}
        account_overrides = {"multiplier": "4", "daytrading_buying_power": "40000",
                             "regt_buying_power": "20000", "equity": "50000"}
        validate_preflight_always(self.observation(account_overrides), config, require_open=True)
        self.assertEqual(config["_account_multiplier"], Decimal("4"))

    def test_allow_existing_recovery_skips_margin_entitlement_even_when_missing(self):
        """LEV-RI-1: --command recover only ever submits sells
        (recovery.recover, recovery.py:168, "buy_submissions": 0), so a
        broker that reports insufficient multiplier/DTBP/regT or a missing
        margin field must not block sell-only recovery from flattening an
        over-leveraged position (README-safety.md: sells/exits are never
        refused by the leverage ceiling)."""
        import leverage as lev
        block = lev.CANONICAL_V1_BLOCK
        leverage_config = {"max_leverage": "4", "capital_usd": "10000",
                           "max_gross_exposure_usd": "40000", "leverage_policy": block}
        policy = lev.validate_leverage_policy(leverage_config, {"overnight_holds": False,
                                                                "overnight_gross_multiple": Decimal("1.0")})
        config = {"capital_usd": "10000", "duration_seconds": 10, "cleanup_seconds": 5,
                  "symbols": ["SPY", "QQQ", "IWM", "DIA"], "benchmarks": ["SPY", "QQQ", "IWM", "DIA"],
                  "quote_max_age_seconds": 5, "max_gross_exposure_usd": "40000", "_leverage_policy": policy}
        observation = self.observation()
        observation["positions"] = [{"symbol": "SPY"}]
        validate_preflight_always(observation, config, require_open=True, allow_existing=True)
        self.assertNotIn("_account_multiplier", config)

    def test_allow_existing_recovery_still_enforces_pdt_equity_floor_removal(self):
        """The ordinary account-restriction check (status/blocked flags,
        cash/equity floor) above the leverage gate already drops the equity
        floor under allow_existing (runner.py ~497-498); confirm a
        margin-restricted PDT account with low equity is not refused solely
        by _check_margin_entitlement's own (now skipped) pattern_day_trader
        branch during recovery."""
        import leverage as lev
        block = lev.CANONICAL_V1_BLOCK
        leverage_config = {"max_leverage": "4", "capital_usd": "10000",
                           "max_gross_exposure_usd": "40000", "leverage_policy": block}
        policy = lev.validate_leverage_policy(leverage_config, {"overnight_holds": False,
                                                                "overnight_gross_multiple": Decimal("1.0")})
        config = {"capital_usd": "10000", "duration_seconds": 10, "cleanup_seconds": 5,
                  "symbols": ["SPY", "QQQ", "IWM", "DIA"], "benchmarks": ["SPY", "QQQ", "IWM", "DIA"],
                  "quote_max_age_seconds": 5, "max_gross_exposure_usd": "40000", "_leverage_policy": policy}
        account_overrides = {"pattern_day_trader": True, "equity": "10000", "cash": "500"}
        observation = self.observation(account_overrides)
        observation["positions"] = [{"symbol": "SPY"}]
        validate_preflight_always(observation, config, require_open=True, allow_existing=True)
        self.assertNotIn("_account_multiplier", config)


class CorporateActionGuardRunnerWiringTests(unittest.TestCase):
    """Runner-level tests (per the fix-round brief) of the corporate-action
    guard's fetch-window sizing (finding 1), its wiring decision (finding
    8), and its bounded/threaded refresh scheduling (finding 2) -- the
    pure/async seams runner.py factors these into specifically so they are
    testable without driving a full native tick loop."""

    def test_fetch_window_is_wide_not_narrow(self):
        """CRITICAL finding 1: the fetch window sent to the source must be
        padded well past the today..next_session horizon in both
        directions (Alpaca filters corporate actions by process date,
        which for a dividend is 1-3 weeks after the governing ex_date this
        guard actually reasons about -- a narrow window misses it; the
        native check in corporate-actions-native-check-20260924.json
        confirms this for a real AAPL dividend)."""
        from datetime import date, timedelta
        import runner as runner_module
        session_date = date(2026, 9, 24)
        next_session, start, end = runner_module._corporate_action_fetch_window(session_date)
        self.assertEqual(next_session, date(2026, 9, 25))
        self.assertEqual(start, session_date - timedelta(days=7))
        self.assertEqual(end, next_session + timedelta(days=90))
        self.assertLess(start, session_date)
        self.assertGreater(end, next_session + timedelta(days=14))  # comfortably past a 1-3 week dividend lag

    def test_guard_wired_only_when_overnight_holds_enabled(self):
        """MEDIUM finding 8: the guard is only ever handed to the strategy
        when overnight_holds is actually enabled -- a regular-session-only
        run (no shipped config currently enables overnight_holds) never
        gets it wired in, regardless of whether config["_corporate_action_
        guard"] is present."""
        import runner as runner_module
        sentinel = object()
        config = {"_corporate_action_guard": sentinel}
        self.assertIs(
            runner_module._corporate_action_guard_for_strategy(config, {"overnight_holds": True}), sentinel)
        self.assertIsNone(
            runner_module._corporate_action_guard_for_strategy(config, {"overnight_holds": False}))
        self.assertIsNone(
            runner_module._corporate_action_guard_for_strategy({}, {"overnight_holds": True}))

    def test_scheduled_refresh_runs_off_the_event_loop_and_clears_in_flight(self):
        """HIGH finding 2: the fetch runs in a worker thread (never blocks
        the event loop), and the in-flight flag is set immediately and
        cleared once the background task completes.

        fix round 3: the concurrency proof now measures ticks that occur
        STRICTLY BEFORE the fetch itself finishes (`guard.finished`, set
        only inside refresh() after its blocking sleep returns) rather than
        ticks counted after awaiting to completion -- a prior version's
        `tick_counter()` looped until its OWN exit condition (ticks >= 3)
        was satisfied, which is trivially true regardless of whether the
        event loop was actually free to run concurrently or was fully
        blocked by a synchronous (non-threaded) refresh() call for the
        whole 0.2s; that version did not actually distinguish threaded from
        synchronous execution (F2a in the review's mutation table)."""
        import asyncio
        import time as time_module
        from datetime import date
        import runner as runner_module

        class SlowGuard:
            def __init__(self):
                self.calls = []
                self.finished = False

            def refresh(self, symbols, *, start, end, now):
                self.calls.append((tuple(sorted(symbols)), start, end, now))
                time_module.sleep(0.2)  # a blocking call, run inside asyncio.to_thread
                self.finished = True

        async def scenario():
            guard = SlowGuard()
            state = {"in_flight": False}
            ticks_before_finished = {"count": 0}

            async def tick_counter():
                while not guard.finished:
                    ticks_before_finished["count"] += 1
                    await asyncio.sleep(0.02)

            task = await runner_module._schedule_corporate_action_refresh(
                guard, {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), 1000.0, state)
            self.assertTrue(state["in_flight"], "in_flight must be set immediately, before the thread finishes")
            await tick_counter()
            await task
            self.assertFalse(state["in_flight"], "in_flight must clear once the background refresh completes")
            self.assertEqual(len(guard.calls), 1)
            self.assertEqual(guard.calls[0], (("AAPL",), date(2026, 9, 17), date(2026, 12, 24), 1000.0))
            self.assertGreaterEqual(ticks_before_finished["count"], 3,
                                    "the event loop must keep ticking WHILE the fetch is still running -- "
                                    "a synchronous (non-threaded) refresh() would block the loop entirely "
                                    "until it finished, so this counter would stay at 0 or 1")

        asyncio.run(scenario())

    def test_scheduled_refresh_no_op_when_already_in_flight(self):
        """HIGH finding 2 (mutation F2c: the tick-loop in_flight check
        removed). This tests the CALLER-SIDE contract callers rely on: the
        tick loop only calls `_schedule_corporate_action_refresh` when
        `not state["in_flight"]`. Verify that contract directly against the
        real tick-loop condition by simulating two consecutive tick-loop
        iterations exactly as run_native's own `if strategy.corporate_
        action_guard is not None and not ca_refresh_state["in_flight"]:`
        guards it -- the second iteration must be skipped while the first
        refresh is still running, so only ONE refresh() call happens even
        though two ticks elapsed."""
        import asyncio
        import time as time_module
        from datetime import date
        import runner as runner_module

        class SlowGuard:
            def __init__(self):
                self.calls = []

            def refresh(self, symbols, *, start, end, now):
                self.calls.append(now)
                time_module.sleep(0.15)

        async def scenario():
            guard = SlowGuard()
            state = {"in_flight": False}
            for tick_now in (1.0, 2.0, 3.0):
                # The exact condition run_native's tick loop uses.
                if guard is not None and not state["in_flight"]:
                    await runner_module._schedule_corporate_action_refresh(
                        guard, {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), tick_now, state)
                await asyncio.sleep(0.02)
            # Drain until the (single) in-flight refresh finishes.
            for _ in range(50):
                if not state["in_flight"]:
                    break
                await asyncio.sleep(0.02)
            self.assertEqual(len(guard.calls), 1, "only the first tick's refresh must actually run "
                                                   "while it is still in flight")

        asyncio.run(scenario())

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_run_native_actually_schedules_a_refresh_when_overnight_holds_is_enabled(self):
        """Runner-level test of BOTH the wiring (finding 8) and the refresh
        call site (finding 2/M13): drives run_native's real tick loop (via
        SimulatedPort, the same lightweight harness IntegratedRunner uses
        elsewhere in this file) with overnight_holds enabled and a fake
        corporate-action guard installed on config -- confirms the guard is
        actually wired into the strategy AND that its refresh() is actually
        invoked at least once during the run, not merely constructed and
        left untouched."""
        from simulation import SimulatedPort
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=2, cleanup_seconds=2, order_timeout_seconds=1)
        config["sessions"] = {"extended_hours": True, "overnight_holds": True,
                              "overnight_gross_multiple": "1.0"}
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True

        class FakeGuard:
            def __init__(self):
                self.refresh_calls = []

            def refresh(self, symbols, *, start, end, now):
                self.refresh_calls.append((tuple(sorted(symbols)), start, end, now))

            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                return {}

        guard = FakeGuard()
        config["_corporate_action_guard"] = guard
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=2, cleanup_seconds=2))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
            port = SimulatedPort(controller, policy.symbols, price=lambda symbol, tick: Decimal("100"))
            controller.port = port
            asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                   "fixture", config, "100000"))
            ledger.close()
        self.assertGreater(len(guard.refresh_calls), 0,
                           "the guard's refresh() must actually be invoked during a run with overnight_holds on")
        symbols, start, end, _ = guard.refresh_calls[0]
        self.assertIn("SPY", symbols)
        self.assertLess(start, end)
        # fix round 3 (mutation F1a): the tick-loop call site must use the
        # WIDE fetch window, not a narrow today..next_session one -- a
        # narrow window would also satisfy `start < end` but span only 1-2
        # days, not the ~97-day wide window this guard actually needs.
        self.assertGreaterEqual((end - start).days, 90,
                                "the tick-loop refresh window must be wide, not the narrow today..next_session span")

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_tick_loop_never_overlaps_refresh_calls(self):
        """HIGH finding 2 (fix round 3, mutation F2c: the tick-loop
        in_flight check removed). Drives run_native's REAL tick loop (not
        a simulated caller-side condition) with a guard whose refresh()
        takes longer than one tick (~0.1s) and records the maximum number
        of CONCURRENT refresh() invocations -- must never exceed 1, proving
        the tick loop's own `not ca_refresh_state["in_flight"]` check is
        actually in effect at the real call site, not just replicated in a
        test's own mimicked condition."""
        import threading
        from simulation import SimulatedPort
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=2, cleanup_seconds=1, order_timeout_seconds=1)
        config["sessions"] = {"extended_hours": True, "overnight_holds": True,
                              "overnight_gross_multiple": "1.0"}
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True

        class SlowGuard:
            def __init__(self):
                self.lock = threading.Lock()
                self.live = 0
                self.max_live = 0
                self.calls = 0

            def refresh(self, symbols, *, start, end, now):
                import time as time_module
                with self.lock:
                    self.live += 1
                    self.max_live = max(self.max_live, self.live)
                    self.calls += 1
                time_module.sleep(0.3)  # well past one 0.1s tick
                with self.lock:
                    self.live -= 1

            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                return {}

        guard = SlowGuard()
        config["_corporate_action_guard"] = guard
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=2, cleanup_seconds=1))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
            port = SimulatedPort(controller, policy.symbols, price=lambda symbol, tick: Decimal("100"))
            controller.port = port
            asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                   "fixture", config, "100000"))
            ledger.close()
        self.assertGreaterEqual(guard.calls, 2, "the run must have been long enough for more than one tick "
                                                "to attempt a refresh")
        self.assertEqual(guard.max_live, 1, "the tick loop must never launch a second refresh while one "
                                            "is still in flight")

    def test_preflight_corporate_action_refresh_uses_the_wide_window(self):
        """HIGH finding 2 (fix round 3, mutation F1b: 'preflight call site
        fetches a one-day window'). Directly exercises the extracted
        `_preflight_corporate_action_refresh` seam (no need to drive all of
        main())."""
        import asyncio
        from datetime import date, timedelta
        import runner as runner_module

        class FakeGuard:
            def __init__(self):
                self.calls = []

            def refresh(self, symbols, *, start, end, now):
                self.calls.append((tuple(sorted(symbols)), start, end, now))

        class FakeLedger:
            def positions(self):
                return {}

        guard = FakeGuard()
        config = {"symbols": ["SPY", "QQQ"], "_corporate_action_guard": guard}
        session_policy = {"overnight_holds": True, "extended_hours": True}
        state = {"in_flight": False}
        asyncio.run(runner_module._preflight_corporate_action_refresh(
            config, session_policy, FakeLedger(), state))
        self.assertEqual(len(guard.calls), 1)
        symbols, start, end, now = guard.calls[0]
        self.assertIn("SPY", symbols)
        self.assertGreaterEqual((end - start).days, 90,
                                "the preflight refresh window must be wide, not a narrow one-day span")

    def test_preflight_corporate_action_refresh_is_a_noop_when_guard_not_wired(self):
        """finding 8: the preflight fetch must never even attempt a call
        when the guard is not wired in (overnight_holds disabled)."""
        import asyncio
        import runner as runner_module

        class FakeGuard:
            def refresh(self, symbols, *, start, end, now):
                raise AssertionError("must not be called when overnight_holds is disabled")

        class FakeLedger:
            def positions(self):
                return {}

        config = {"symbols": ["SPY"], "_corporate_action_guard": FakeGuard()}
        state = {"in_flight": False}
        asyncio.run(runner_module._preflight_corporate_action_refresh(
            config, {"overnight_holds": False}, FakeLedger(), state))
        self.assertFalse(state["in_flight"])

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_outcome_pending_must_flatten_reflects_the_guards_final_state(self):
        """fix round 3 (mutations F5a/F5b), fix round 4 (finding 3): the
        outcome's corporate_action_guard summary is now RECOMPUTED fresh
        (_final_corporate_action_guard_summary) against the guard's own
        evaluate() and the truly final held positions, right before the
        outcome is built -- not a stale per-tick snapshot. A guard that
        reports must_flatten=True for a symbol genuinely still held at run
        end must make run_native's own returned outcome carry it in
        outcome["corporate_action_guard"]["pending_must_flatten"]."""
        import corporate_actions as CA
        from simulation import SimulatedPort
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=2, cleanup_seconds=2, order_timeout_seconds=1)
        config["sessions"] = {"extended_hours": True, "overnight_holds": True,
                              "overnight_gross_multiple": "1.0"}
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True

        class FlattenOnceHeldGuard:
            """Real evaluate_guard-style semantics: must_flatten only once
            AAPL is genuinely held, so it is bought normally first, then
            flagged -- unlike an unconditional guard, this cannot be
            satisfied by a symbol that was never actually held."""
            def refresh(self, symbols, *, start, end, now):
                pass

            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                if "AAPL" not in held_symbols:
                    return {}
                return {"AAPL": CA.GuardDecision(symbol="AAPL", block_entry=True, must_flatten=True,
                                                 needs_attention=False, reason="corporate_action_cash_dividend",
                                                 action_type="cash_dividend", action_date=today)}

        config["_corporate_action_guard"] = FlattenOnceHeldGuard()
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=2, cleanup_seconds=2))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            # AAPL is not one of PolicyConfig's own default benchmarks
            # (SPY/QQQ/IWM/DIA) -- it needs a real positive EDGE over them
            # to ever be selected, which the price() slope below provides
            # (benchmarks are all equal to each other, so a universe of
            # only benchmarks never generates a signal).
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL"), max_positions=5, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
            # A port whose sells never actually execute keeps AAPL held
            # through to the outcome, so the forced flatten this guard
            # requests stays genuinely pending -- proving the recomputed
            # summary reflects reality, not merely an echoed guard opinion.
            # Price drift (not a flat constant) is needed for the policy to
            # actually generate a real buy signal.
            def price(symbol, tick):
                slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
                return Decimal("100") + min(tick, 70) * slope

            port = SimulatedPort(controller, policy.symbols, price=price)
            original_submit = port.submit

            async def submit_buys_only(payload):
                if payload.get("side") == "sell":
                    # Accept the forced-flatten sell as a resting (never
                    # filled) order so SPY stays genuinely held all the way
                    # through to the outcome -- proving the recomputed
                    # summary reflects an ACTUALLY still-pending flatten,
                    # not merely an echoed guard opinion about a symbol
                    # that was already sold.
                    import inspect as inspect_module
                    import time as time_module
                    controller.before_submit(payload)
                    await controller.before_request("submit", client_id=payload["client_order_id"])
                    order = dict(payload, id=f"sim-resting-{payload['client_order_id']}", status="new",
                                filled_qty="0", filled_avg_price="0", updated_at_ns=time_module.time_ns())
                    port.orders[payload["client_order_id"]] = order
                    controller.observe(order)
                    result = port.on_order(dict(order))
                    if inspect_module.isawaitable(result):
                        await result
                    return dict(order)
                return await original_submit(payload)

            port.submit = submit_buys_only
            controller.port = port
            outcome = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                             "fixture", config, "100000"))
            ledger.close()
        self.assertIn("AAPL", outcome["corporate_action_guard"]["pending_must_flatten"])

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_run_native_shutdown_cleanup_hook_fires_before_return(self):
        """MEDIUM finding (fix round 5, Codex 4a): the shutdown test above
        (and the pre-existing G6 test) only asserted the END STATE after
        `asyncio.run()` already returned -- which `asyncio.run()`'s own
        `Runner.close()` guarantees regardless of run_native's OWN explicit
        cleanup call (it cancels every outstanding Task itself). This
        proves run_native's `finally` block ACTUALLY calls
        `_shutdown_corporate_action_tasks` itself, by patching that exact
        module-level function with a recording wrapper and confirming it
        was invoked -- `asyncio.run()`'s own internal `_cancel_all_tasks()`
        never calls this named Python function at all, so only run_native's
        own explicit call site can make this hook fire."""
        import runner as runner_module
        from simulation import SimulatedPort
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=1, cleanup_seconds=1, order_timeout_seconds=1)
        config["sessions"] = {"extended_hours": True, "overnight_holds": True,
                              "overnight_gross_multiple": "1.0"}
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True

        class QuickGuard:
            def refresh(self, symbols, *, start, end, now):
                pass

            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                return {}

        config["_corporate_action_guard"] = QuickGuard()
        calls = []
        original = runner_module._shutdown_corporate_action_tasks

        async def recording_shutdown(ca_refresh_state):
            calls.append(1)
            return await original(ca_refresh_state)

        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=1, cleanup_seconds=1))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
            port = SimulatedPort(controller, policy.symbols, price=lambda symbol, tick: Decimal("100"))
            controller.port = port
            with patch.object(runner_module, "_shutdown_corporate_action_tasks", recording_shutdown):
                asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                       "fixture", config, "100000"))
            ledger.close()
        self.assertGreaterEqual(len(calls), 1,
                                "run_native's own finally block must call _shutdown_corporate_action_tasks "
                                "directly, not merely rely on asyncio.run()'s own task cancellation")

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_run_native_refuses_the_hold_when_a_refresh_degrades_after_the_final_rebalance(self):
        """HIGH finding (fix round 5, Codex 4b): the existing hold/summary
        tests pass even when run_native's summary is (in memory) reverted
        to the strategy's own stale per-tick snapshot, because they either
        call `_final_corporate_action_guard_summary` directly (a unit test
        of the seam, not of run_native's actual wiring) or use a guard whose
        `evaluate()` answer never actually changes after the last tick.
        This drives the REAL `run_native` tick loop with a guard whose
        `evaluate()` answer flips from clear to `needs_attention` at a wall-
        clock threshold set to land AFTER the trial's own rebalancing has
        stopped (during cleanup/shutdown) -- reproducing "a refresh that
        completes/fails after the final rebalance tick" -- and asserts the
        REAL returned `outcome` both reports the held symbol under
        `pending_needs_attention_held` and REFUSES to report
        `held_overnight`."""
        import corporate_actions as CA
        from simulation import SimulatedPort
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=1, cleanup_seconds=2, order_timeout_seconds=1)
        config["sessions"] = {"extended_hours": True, "overnight_holds": True,
                              "overnight_gross_multiple": "1.0"}
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True

        class LateDegradingGuard:
            """Clear for every evaluate() call up through the end of the
            configured trial duration; any call after that (i.e., during
            cleanup/shutdown, or the outcome's own final recompute) reports
            needs_attention for AAPL instead -- simulating a background
            refresh that only degrades the cached result AFTER the last
            rebalance tick already ran."""
            def __init__(self, start_time, duration_seconds):
                self.start_time = start_time
                self.duration_seconds = duration_seconds

            def refresh(self, symbols, *, start, end, now):
                pass

            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                if "AAPL" not in held_symbols:
                    return {}
                import time as time_module
                if time_module.time() < self.start_time + self.duration_seconds:
                    return {"AAPL": CA.GuardDecision(symbol="AAPL", block_entry=False, must_flatten=False,
                                                     needs_attention=False, reason=None)}
                return {"AAPL": CA.GuardDecision(symbol="AAPL", block_entry=True, must_flatten=False,
                                                 needs_attention=True,
                                                 reason="corporate_action_lookup_failed")}

        started_at = time.time()
        config["_corporate_action_guard"] = LateDegradingGuard(started_at, config["duration_seconds"])
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=1, cleanup_seconds=2))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL"), max_positions=5, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)

            def price(symbol, tick):
                slope = Decimal(".03") if symbol in policy.benchmarks else Decimal(".10")
                return Decimal("100") + min(tick, 70) * slope

            port = SimulatedPort(controller, policy.symbols, price=price)
            original_submit = port.submit

            async def submit_buys_only(payload):
                # Keep AAPL genuinely held through to the outcome (a sell
                # here rests, never fills) -- an ordinary rebalance-driven
                # sell (min_hold/max_hold/cooldown are all short) would
                # otherwise flatten AAPL well before the trial ends,
                # regardless of this guard, so held_symbols_now at outcome
                # time would already be empty for reasons unrelated to what
                # this test is proving.
                if payload.get("side") == "sell":
                    import inspect as inspect_module
                    import time as time_module
                    controller.before_submit(payload)
                    await controller.before_request("submit", client_id=payload["client_order_id"])
                    order = dict(payload, id=f"sim-resting-{payload['client_order_id']}", status="new",
                                filled_qty="0", filled_avg_price="0", updated_at_ns=time_module.time_ns())
                    port.orders[payload["client_order_id"]] = order
                    controller.observe(order)
                    result = port.on_order(dict(order))
                    if inspect_module.isawaitable(result):
                        await result
                    return dict(order)
                return await original_submit(payload)

            port.submit = submit_buys_only
            controller.port = port
            outcome = asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                             "fixture", config, "100000"))
            ledger.close()
        self.assertIn("AAPL", outcome["corporate_action_guard"]["pending_needs_attention_held"],
                      "the REAL outcome must reflect the guard's post-rebalance degraded state")
        self.assertNotEqual(outcome["status"], "held_overnight",
                            "a run with a pending needs_attention symbol must never report held_overnight")

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_final_summary_uses_the_guards_current_state_not_a_stale_strategy_snapshot(self):
        """MEDIUM finding 3 (fix round 4): reproduces the independent
        review's own probe scenario directly against
        `_final_corporate_action_guard_summary` -- the exact function
        run_native's outcome construction calls. Even when the
        strategy's own last-tick bookkeeping (`_ca_ever_flagged`) is
        stale/empty (as it would be if a refresh only failed/completed
        AFTER the last rebalance() tick ran), the summary must reflect the
        guard's CURRENT evaluate() answer for the CURRENT held positions --
        not silently report a clear state just because the strategy's own
        tick-level snapshot never saw the change."""
        import corporate_actions as CA
        import runner as runner_module

        class StaleSnapshotStrategy:
            """Stands in for a real AdaptiveStrategy whose own per-tick
            bookkeeping is stale -- _ca_ever_flagged deliberately empty,
            simulating a strategy that never got another rebalance() tick
            after the guard's state changed."""
            def __init__(self, guard):
                self.corporate_action_guard = guard
                self._ca_ever_flagged = set()

        class LateGuard:
            """The monitor's CURRENT state, as of right now -- reflecting
            a refresh that failed/was cancelled after the last tick."""
            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                return {"AAPL": CA.GuardDecision(symbol="AAPL", block_entry=True, must_flatten=False,
                                                 needs_attention=True, reason="corporate_action_lookup_failed")}

        strategy = StaleSnapshotStrategy(LateGuard())
        # 2026-09-24 09:30:00 America/New_York (RTH open) -- resolves
        # without a ValueError under the frozen calendar.
        summary = runner_module._final_corporate_action_guard_summary(strategy, {"AAPL"}, 1790256600.0)
        self.assertIn("AAPL", summary["pending_needs_attention_held"],
                      "the recomputed summary must reflect the guard's CURRENT state, not the "
                      "strategy's stale (empty) _ca_ever_flagged snapshot")
        self.assertIn("AAPL", summary["ever_flagged_symbols"])

    def test_final_summary_fails_closed_when_the_calendar_itself_cannot_classify_now(self):
        """finding 6 (round 3)/H11 (fix round 5): when `session_at(now)`
        itself raises ValueError (the instant falls outside the frozen
        session calendar), the final summary must fail CLOSED -- every held
        symbol reported under `pending_needs_attention_held` -- never
        silently "clear" just because the calendar failed to classify this
        instant. A calendar failure is itself a reason for attention, not
        evidence of safety."""
        import runner as runner_module

        class UnusedGuard:
            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                raise AssertionError("evaluate() must never be reached once the calendar itself fails")

        class Strategy:
            def __init__(self, guard):
                self.corporate_action_guard = guard
                self._ca_ever_flagged = set()

        # Far outside the frozen session calendar's supported year range.
        out_of_range_now = datetime(2099, 1, 1, tzinfo=timezone.utc).timestamp()
        summary = runner_module._final_corporate_action_guard_summary(
            Strategy(UnusedGuard()), {"AAPL"}, out_of_range_now)
        self.assertEqual(summary["pending_needs_attention_held"], ["AAPL"],
                         "a calendar failure must fail closed for every held symbol, not report clear")
        self.assertEqual(summary["pending_must_flatten"], [])

    def test_final_summary_is_clear_when_the_guard_is_actually_clear(self):
        """The mirror case: a guard reporting a genuinely clear state for
        every held symbol must not be reported as pending."""
        import corporate_actions as CA
        import runner as runner_module

        class ClearGuard:
            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                return {"AAPL": CA.GuardDecision(symbol="AAPL", block_entry=False, must_flatten=False,
                                                 needs_attention=False, reason=None)}

        class Strategy:
            def __init__(self, guard):
                self.corporate_action_guard = guard
                self._ca_ever_flagged = set()

        summary = runner_module._final_corporate_action_guard_summary(Strategy(ClearGuard()), {"AAPL"}, 1790256600.0)
        self.assertEqual(summary["pending_must_flatten"], [])
        self.assertEqual(summary["pending_needs_attention_held"], [])

    def test_scheduled_refresh_times_out_and_still_clears_in_flight(self):
        """HIGH finding 1/2 (fix round 3): a refresh() call that runs
        longer than CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS is abandoned
        (wait_for gives up) but the in-flight flag is still cleared, so a
        later tick is not permanently locked out from ever refreshing
        again -- AND the guard's own `refresh_timed_out()` is called (if it
        exposes one), treating the timeout as an immediate failure rather
        than silently leaving the cache in whatever state it was in until
        the abandoned thread happens to resolve on its own."""
        import asyncio
        import time as time_module
        from datetime import date
        import runner as runner_module

        class HangingGuard:
            def __init__(self):
                self.timed_out_calls = []

            def refresh(self, symbols, *, start, end, now):
                time_module.sleep(runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS + 5)

            def refresh_timed_out(self, symbols):
                self.timed_out_calls.append(tuple(sorted(symbols)))

        async def scenario():
            state = {"in_flight": False}
            guard = HangingGuard()
            original_timeout = runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS
            runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS = 0.05
            try:
                await runner_module._schedule_corporate_action_refresh(
                    guard, {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), 1000.0, state)
                self.assertTrue(state["in_flight"])
                for _ in range(50):
                    if not state["in_flight"]:
                        break
                    await asyncio.sleep(0.02)
                self.assertFalse(state["in_flight"], "a timed-out refresh must still clear in_flight")
                self.assertEqual(guard.timed_out_calls, [("AAPL",)],
                                 "a timeout must be reported to the guard as a failure")
            finally:
                runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS = original_timeout

        asyncio.run(scenario())

    def test_scheduled_refresh_timeout_flags_the_symbol_and_retries_after_60s_not_900s(self):
        """LOW finding (fix round 6, test gap): mutation G4 (drop the
        scheduler's call to `guard.refresh_timed_out(generation, watch)`
        for a two-phase guard) survived every existing short-timeout test,
        because they all drive a LEGACY guard exposing only the single-arg
        `refresh_timed_out(symbols)` convention -- never the REAL
        `CorporateActionMonitor`'s own generation-aware two-phase timeout
        path. Drives the real monitor through `_schedule_corporate_action_
        refresh` with an artificially short timeout, and asserts (a) the
        symbol is actually flagged needs_attention right after the
        timeout, and (b) the next attempt is retried on the SHORT
        `retry_seconds` (60s) interval, not the ordinary long
        `refresh_seconds` (900s) one -- proving `refresh_timed_out` (not
        merely `invalidate_attempt`, which does not set `_last_attempt_
        failed`) is what actually ran."""
        import asyncio
        import threading
        import time as time_module
        from datetime import date
        import corporate_actions as CA
        import runner as runner_module

        release = threading.Event()

        class HangingSrc:
            def fetch(self, symbols, start, end):
                release.wait(5)
                return ({s: [] for s in symbols}, set())

        monitor = CA.CorporateActionMonitor(HangingSrc(), refresh_seconds=900, retry_seconds=60,
                                            clock=lambda: time_module.time())

        async def scenario():
            state = {"in_flight": False}
            original_timeout = runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS
            runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS = 0.05
            now0 = time_module.time()
            try:
                await runner_module._schedule_corporate_action_refresh(
                    monitor, {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), now0, state)
                for _ in range(50):
                    if not state["in_flight"]:
                        break
                    await asyncio.sleep(0.02)
                self.assertFalse(state["in_flight"])
            finally:
                runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS = original_timeout
            decision = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                        held_symbols={"AAPL"}, candidate_symbols=set(), now=now0 + 1)["AAPL"]
            self.assertTrue(decision.needs_attention, "the real monitor's generation-aware refresh_timed_out "
                                                      "must actually run and flag the symbol")
            # Still inside the SHORT retry_seconds=60 window -- a second
            # attempt must still be throttled.
            gen_throttled = monitor.begin_attempt({"AAPL"}, start=date(2026, 9, 17), end=date(2026, 12, 24),
                                                  now=now0 + 30)
            self.assertIsNone(gen_throttled, "must not yet retry within the short retry_seconds window")
            # Past retry_seconds=60 -- a fresh attempt must now be allowed,
            # proving the SHORT interval applied (not the ordinary long
            # refresh_seconds=900).
            gen_ready = monitor.begin_attempt({"AAPL"}, start=date(2026, 9, 17), end=date(2026, 12, 24),
                                              now=now0 + 61)
            self.assertIsNotNone(gen_ready, "must retry on the short retry_seconds=60 interval after a "
                                            "timeout, not the ordinary long refresh_seconds=900 one")
            release.set()

        asyncio.run(scenario())

    def test_hung_refresh_does_not_delay_process_exit(self):
        """LOW finding 6 (fix round 4): `asyncio.run()`'s own cleanup joins
        every outstanding `asyncio.to_thread`/default-executor thread
        before returning, regardless of any Task cancellation -- a single
        still-hanging refresh used to delay the whole process's own exit
        (and, in runner.py's real main(), the result-save and account-lock
        release) by the hang's full duration. `_schedule_corporate_action_
        refresh` now bridges the worker to a DAEMON thread via
        `loop.call_soon_threadsafe` instead, which `asyncio.run()` never
        waits for. Measured: `asyncio.run(scenario())` itself must return
        in well under the hang's own duration (here 3s), not ~3s."""
        import asyncio
        import time as time_module
        from datetime import date
        import runner as runner_module

        class HangingGuard:
            def refresh(self, symbols, *, start, end, now):
                time_module.sleep(3.0)  # a long hang, well past the timeout below

        async def scenario():
            state = {"in_flight": False}
            original_timeout = runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS
            runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS = 0.05
            try:
                await runner_module._schedule_corporate_action_refresh(
                    HangingGuard(), {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), 1000.0, state)
                await asyncio.sleep(0.1)  # let the timeout actually fire
            finally:
                runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS = original_timeout

        started = time_module.monotonic()
        asyncio.run(scenario())
        elapsed = time_module.monotonic() - started
        self.assertLess(elapsed, 1.5, f"asyncio.run() must not be delayed by the hanging worker "
                                      f"(daemon-thread bridge, not asyncio.to_thread); took {elapsed:.2f}s")

    def test_real_monitor_generation_drops_a_superseded_late_write(self):
        """HIGH finding 1 (fix round 3): reproduces the reviewer's own
        finding against the REAL CorporateActionMonitor (not a fake) --
        an older, slower refresh() attempt that finishes AFTER a newer one
        has already written a confirmed action must not overwrite it.
        Simulated directly at the monitor level (two threads racing
        CorporateActionMonitor.refresh with a real threading.Lock/gate),
        exactly as the independent review's own P2 probe did."""
        import threading
        from datetime import date
        import corporate_actions as CA

        gate = threading.Event()

        class Src:
            def fetch(self, symbols, start, end):
                if threading.current_thread().name == "A-slow":
                    gate.wait(5)
                    return {s: [] for s in symbols}  # stale: server state before the action existed
                return {s: [CA.ActionRecord(symbol=s, action_type="forward_split",
                                            action_date=date(2026, 9, 25))] for s in symbols}

        monitor = CA.CorporateActionMonitor(Src(), refresh_seconds=900, retry_seconds=60, max_age_seconds=3600)
        window = dict(start=date(2026, 9, 17), end=date(2026, 12, 24))
        # A starts first (slow, blocked on `gate`) with an OLDER `now` --
        # but the generation counter, not the `now` timestamp, is what
        # determines supersession: A started its attempt (bumped the
        # generation) before B did, so B's later-generation write must win
        # regardless of which `now` value either call carried.
        a = threading.Thread(target=monitor.refresh, args=({"NVDA"},), kwargs=dict(**window, now=1000.0), name="A-slow")
        a.start()
        # Ensure A has actually entered refresh() (bumped the generation
        # and is now blocked inside Src.fetch on `gate`) before B starts.
        import time as time_module
        time_module.sleep(0.05)
        b = threading.Thread(target=monitor.refresh, args=({"NVDA"},), kwargs=dict(**window, now=1030.0), name="B-fast")
        b.start()
        b.join(5)
        decisions = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                     held_symbols={"NVDA"}, candidate_symbols=set(), now=1030.0)
        self.assertTrue(decisions["NVDA"].must_flatten, "B's confirmed action must be visible before A resolves")
        gate.set()  # release A
        a.join(5)
        decisions_after_a = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                             held_symbols={"NVDA"}, candidate_symbols=set(), now=1030.0)
        self.assertTrue(decisions_after_a["NVDA"].must_flatten,
                        "A's late, superseded write must NOT cancel B's already-applied confirmed action")

    def test_scheduler_calls_begin_attempt_before_launching_the_worker_thread(self):
        """HIGH finding (fix round 5): `_schedule_corporate_action_refresh`
        itself -- not merely the monitor's own primitives -- must call
        `guard.begin_attempt(...)` on the calling coroutine BEFORE
        `threading.Thread(...).start()` is ever reached, for any guard that
        exposes the two-phase API. Proven directly by recording the ORDER
        `begin_attempt` and the worker's own `run_attempt` are invoked in a
        shared list from a fake two-phase guard -- `begin_attempt` must
        appear first, and (since it happens on the calling coroutine, not
        the worker thread) it must have already run by the time this
        function RETURNS the created task, before that task's own worker
        thread has necessarily done any work at all."""
        import asyncio
        from datetime import date
        import runner as runner_module

        order = []

        class TwoPhaseGuard:
            def begin_attempt(self, symbols, *, start, end, now):
                order.append("begin_attempt")
                return 1

            def run_attempt(self, symbols, generation, *, start, end, now):
                order.append("run_attempt")

            def refresh_timed_out(self, generation, symbols):
                order.append("refresh_timed_out")

            def invalidate_attempt(self, generation):
                order.append("invalidate_attempt")

        async def scenario():
            state = {"in_flight": False}
            task = await runner_module._schedule_corporate_action_refresh(
                TwoPhaseGuard(), {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), 1000.0, state)
            # begin_attempt must ALREADY have happened -- it runs
            # synchronously on this calling coroutine before the task
            # (whose own worker thread does the rest) is even created.
            self.assertEqual(order, ["begin_attempt"],
                             "begin_attempt must run before the worker thread is launched, "
                             "not lazily inside the worker itself")
            await task
            self.assertEqual(order, ["begin_attempt", "run_attempt"])

        asyncio.run(scenario())

    def test_begin_attempt_generation_survives_a_shutdown_before_the_worker_even_runs(self):
        """HIGH finding (fix round 5): reproduces an independent review's
        own probe (R1's synchronized scenario) directly against the
        two-phase API -- the generation for an attempt must be allocated
        (via begin_attempt) and invalidated (via invalidate_attempt) BEFORE
        the actual fetch ever runs, and that invalidation must still work
        even though the fetch itself never observed it (Python cannot
        forcibly kill a thread). Simulates a worker thread launched, then
        delayed by the OS before it starts running -- a shutdown-time
        cancellation fires and invalidates the pre-allocated generation --
        and only THEN does the delayed worker finally run and try to write
        a confirmed action; that write must be dropped as superseded."""
        from datetime import date
        import corporate_actions as CA

        class Src:
            def fetch(self, symbols, start, end):
                return {s: [CA.ActionRecord(symbol=s, action_type="forward_split",
                                            action_date=date(2026, 9, 25))] for s in symbols}

        monitor = CA.CorporateActionMonitor(Src(), clock=lambda: 1000.0)
        generation = monitor.begin_attempt({"NVDA"}, start=date(2026, 9, 17), end=date(2026, 12, 24), now=1000.0)
        self.assertIsNotNone(generation)
        # Shutdown fires HERE -- before the worker thread (which has not
        # even started running `fetch()` yet, simulating an OS-scheduling
        # delay after Thread.start() was already called) has done any work.
        monitor.invalidate_attempt(generation)
        # The delayed worker now finally runs and tries to commit its
        # (stale, since-invalidated) result.
        monitor.run_attempt({"NVDA"}, generation, start=date(2026, 9, 17), end=date(2026, 12, 24), now=1000.5)
        decisions = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                     held_symbols={"NVDA"}, candidate_symbols=set(), now=1000.5)
        self.assertFalse(decisions["NVDA"].must_flatten,
                         "an attempt invalidated before it ever ran must never commit its late write")

    def test_cancellation_of_a_routine_refresh_does_not_degrade_a_clean_cached_result(self):
        """LOW finding (fix round 5, Claude's review): cancellation (an
        ordinary shutdown interrupting an otherwise routine, still-in-
        flight refresh) must NOT force the cached result to needs_attention
        -- only a genuine timeout should. A perfectly clean, still-fresh
        cached result must stand after a cancellation, unlike after a
        `refresh_timed_out`."""
        from datetime import date
        import corporate_actions as CA

        class Src:
            def fetch(self, symbols, start, end):
                return {s: [] for s in symbols}

        monitor = CA.CorporateActionMonitor(Src(), clock=lambda: 1000.0)
        # A clean, confirmed-clear, fresh result is already cached.
        monitor.refresh({"SPY"}, start=date(2026, 9, 17), end=date(2026, 12, 24), now=1000.0)
        clean = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                 held_symbols={"SPY"}, candidate_symbols=set(), now=1000.0)
        self.assertFalse(clean["SPY"].needs_attention)
        # A routine periodic refresh is now in flight (generation
        # allocated) when shutdown cancels it.
        generation = monitor.begin_attempt({"SPY"}, start=date(2026, 9, 17), end=date(2026, 12, 24), now=1900.0)
        monitor.invalidate_attempt(generation)
        after_cancel = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                        held_symbols={"SPY"}, candidate_symbols=set(), now=1900.0)
        self.assertFalse(after_cancel["SPY"].needs_attention,
                         "cancelling a routine in-flight refresh must not degrade an already-clean result")
        # Contrast: a genuine TIMEOUT for the same kind of attempt DOES degrade.
        generation2 = monitor.begin_attempt({"SPY"}, start=date(2026, 9, 17), end=date(2026, 12, 24), now=2800.0)
        monitor.refresh_timed_out(generation2, {"SPY"})
        after_timeout = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                         held_symbols={"SPY"}, candidate_symbols=set(), now=2800.0)
        self.assertTrue(after_timeout["SPY"].needs_attention,
                        "a genuine timeout, unlike a cancellation, must degrade")

    def test_scheduled_refresh_cancellation_invalidates_not_degrades_with_the_real_monitor(self):
        """HIGH/LOW finding (fix round 5): end-to-end through
        `_schedule_corporate_action_refresh` and `_shutdown_corporate_
        action_tasks` with the REAL `CorporateActionMonitor` -- a routine
        refresh still in flight when shutdown cancels it must leave an
        already-clean cached result clean (not needs_attention), while a
        delayed worker's late write (released only after shutdown) must
        still be dropped as superseded."""
        import asyncio
        import threading
        from datetime import date
        import corporate_actions as CA
        import runner as runner_module

        release = threading.Event()

        class Src:
            def __init__(self):
                self.calls = 0

            def fetch(self, symbols, start, end):
                self.calls += 1
                if self.calls > 1:
                    release.wait(3)  # the routine periodic refresh is still in flight at shutdown
                return {s: [] for s in symbols}

        async def scenario():
            monitor = CA.CorporateActionMonitor(Src(), clock=lambda: 1000.0)
            monitor.refresh({"SPY"}, start=date(2026, 9, 17), end=date(2026, 12, 24), now=1000.0)
            state = {"in_flight": False}
            await runner_module._schedule_corporate_action_refresh(
                monitor, {"SPY"}, date(2026, 9, 17), date(2026, 12, 24), 1900.0, state)
            await asyncio.sleep(0.1)  # let the worker actually enter fetch() and block on `release`
            with monitor._lock:
                generation_before_cancel = monitor._generation
            await runner_module._shutdown_corporate_action_tasks(state)
            # LOW finding (fix round 6, G5 mutation gap): checking only the
            # END STATE (needs_attention stays False) cannot distinguish a
            # real invalidate_attempt call from a no-op cancellation that
            # happens to leave the same clean state anyway, because the
            # delayed fetch itself also returns a clean result -- assert
            # the generation counter was ACTUALLY bumped past the
            # cancelled attempt, proving invalidate_attempt really ran.
            with monitor._lock:
                generation_after_cancel = monitor._generation
            self.assertGreater(generation_after_cancel, generation_before_cancel,
                               "cancellation must actually invalidate (bump past) the in-flight attempt's "
                               "own generation, not silently do nothing")
            decisions = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                         held_symbols={"SPY"}, candidate_symbols=set(), now=1900.0)
            self.assertFalse(decisions["SPY"].needs_attention,
                             "cancelling a routine in-flight refresh at shutdown must not force needs_attention")
            release.set()  # let the delayed worker finally finish, after shutdown

        asyncio.run(scenario())

    def test_in_flight_is_reset_even_if_starting_the_worker_thread_itself_raises(self):
        """LOW finding (fix round 5): `Thread.start()` must sit INSIDE the
        try/finally that resets `state["in_flight"]` -- if starting the
        thread itself ever raised (e.g. a resource-exhaustion OSError), the
        old placement (outside the try) would leave `in_flight` stuck True
        forever, permanently locking out every future refresh attempt."""
        import asyncio
        import threading
        from datetime import date
        import runner as runner_module

        class ExplodingThread:
            def __init__(self, *args, **kwargs):
                pass

            def start(self):
                raise RuntimeError("simulated resource exhaustion starting the worker thread")

        class QuickGuard:
            def refresh(self, symbols, *, start, end, now):
                pass

        async def scenario():
            state = {"in_flight": False}
            with patch.object(threading, "Thread", ExplodingThread):
                task = await runner_module._schedule_corporate_action_refresh(
                    QuickGuard(), {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), 1000.0, state)
                # The patch must still be active when the created task
                # actually RUNS -- asyncio.create_task only SCHEDULES the
                # coroutine; it does not execute until the next loop
                # iteration.
                await asyncio.sleep(0)
            with self.assertRaises(RuntimeError):
                await task
            self.assertFalse(state["in_flight"], "in_flight must be reset even when Thread.start() itself raises")

        asyncio.run(scenario())

    def test_thread_start_failure_still_resolves_the_real_monitors_attempt(self):
        """LOW finding (fix round 6): reproduces an independent review's
        own probe (S3) against the REAL `CorporateActionMonitor` -- when
        `Thread.start()` itself raises, the pre-allocated generation must
        not be left permanently unresolved (never committed, never failed,
        never invalidated). Without `fail_attempt` being called on this
        path, `_last_attempt_failed` stays False and the symbol is never
        marked degraded, so a genuinely failed launch would be silently
        retried on the ordinary long `refresh_seconds` (900s) interval
        with nothing ever flagged, instead of the short `retry_seconds`
        (60s) one."""
        import asyncio
        import threading
        import time as time_module
        from datetime import date
        import corporate_actions as CA
        import runner as runner_module

        class Src:
            calls = 0

            def fetch(self, symbols, start, end):
                Src.calls += 1
                return ({s: [] for s in symbols}, set())

        monitor = CA.CorporateActionMonitor(Src(), refresh_seconds=900, retry_seconds=60,
                                            clock=lambda: time_module.time())
        t0 = time_module.time()
        monitor.refresh({"SPY"}, start=date(2026, 9, 17), end=date(2026, 12, 24), now=t0 - 1000)  # earlier clean success

        real_start = threading.Thread.start

        def boom(self):
            if self.name == "ca-refresh":
                raise RuntimeError("can't start new thread")
            return real_start(self)

        async def scenario():
            state = {"in_flight": False}
            threading.Thread.start = boom
            try:
                task = await runner_module._schedule_corporate_action_refresh(
                    monitor, {"SPY"}, date(2026, 9, 17), date(2026, 12, 24), t0, state)
                await asyncio.gather(task, return_exceptions=True)
            finally:
                threading.Thread.start = real_start
            self.assertFalse(state["in_flight"], "in_flight must still be reset")
            with monitor._lock:
                generation, committed, failed = (monitor._generation, monitor._committed_generation,
                                                 monitor._last_attempt_failed)
            self.assertEqual(generation, committed,
                             "the failed launch's generation must be resolved (committed as a failure), "
                             "not left dangling ahead of _committed_generation forever")
            self.assertTrue(failed, "a failed launch must be recorded as a failure, enabling the short "
                                    "retry_seconds interval")
            decision = monitor.evaluate(today=date(2026, 9, 24), next_session_date=date(2026, 9, 25),
                                        held_symbols={"SPY"}, candidate_symbols=set(), now=t0)["SPY"]
            self.assertTrue(decision.needs_attention,
                            "the failed launch must have flagged SPY degraded right away")
            # 30s later: still inside the SHORT retry_seconds=60 window --
            # a fresh attempt must still be throttled.
            still_throttled = monitor.begin_attempt({"SPY"}, start=date(2026, 9, 17), end=date(2026, 12, 24),
                                                     now=t0 + 30)
            self.assertIsNone(still_throttled, "must not yet retry within the short retry_seconds window")
            # 60s later: past retry_seconds=60 -- a fresh attempt must now
            # be allowed, proving the SHORT interval applied (the failure
            # was actually recorded), not the ordinary long
            # refresh_seconds=900 one.
            next_task = await runner_module._schedule_corporate_action_refresh(
                monitor, {"SPY"}, date(2026, 9, 17), date(2026, 12, 24), t0 + 61, state)
            self.assertIsNotNone(next_task, "must retry on the short retry_seconds interval, not be "
                                            "throttled for the ordinary long refresh_seconds=900")
            if next_task is not None:
                await next_task

        asyncio.run(scenario())

    def test_second_preflight_on_an_already_warmed_monitor_does_not_raise(self):
        """NIT (fix round 6): reproduces an independent review's own probe
        (S4) -- `_schedule_corporate_action_refresh` returns `None`, not a
        task, when the two-phase `begin_attempt` itself reports a
        throttled no-op (an equivalent fresh result already cached for
        this exact symbol set/window). `_preflight_corporate_action_
        refresh` used to unconditionally `await` that return value --
        `await None` raises TypeError -- so a SECOND preflight call while
        the monitor is already warm (e.g. a resumed/retried startup path)
        would crash instead of being the harmless no-op it should be."""
        import asyncio
        import corporate_actions as CA
        import runner as runner_module

        class Src:
            def fetch(self, symbols, start, end):
                return ({x: [] for x in symbols}, set())

        class FakeLedger:
            def positions(self):
                return {}

        monitor = CA.CorporateActionMonitor(Src())
        config = {"_corporate_action_guard": monitor, "symbols": ["SPY"]}
        state = {"in_flight": False}

        async def scenario():
            await runner_module._preflight_corporate_action_refresh(
                config, {"overnight_holds": True}, FakeLedger(), state)
            # The second call, within the same throttle interval, must be a
            # harmless no-op -- not raise TypeError from `await None`.
            await runner_module._preflight_corporate_action_refresh(
                config, {"overnight_holds": True}, FakeLedger(), state)

        asyncio.run(scenario())

    def test_worker_thread_is_a_daemon(self):
        """LOW finding (fix round 5): the worker thread that runs the
        blocking fetch must be a DAEMON thread -- not provable by the
        exit-timing test alone (a slow-but-not-infinite hang could still
        happen to let the process exit in time even on a non-daemon
        thread, or vice versa be flaky under load) -- capture the actual
        `threading.Thread` object via a patched constructor and assert
        `daemon=True` was passed directly."""
        import asyncio
        import threading
        from datetime import date
        import runner as runner_module

        captured = {}
        original_thread = threading.Thread

        def capturing_thread(*args, **kwargs):
            t = original_thread(*args, **kwargs)
            captured["daemon"] = kwargs.get("daemon")
            return t

        class QuickGuard:
            def refresh(self, symbols, *, start, end, now):
                pass

        async def scenario():
            state = {"in_flight": False}
            with patch.object(threading, "Thread", capturing_thread):
                task = await runner_module._schedule_corporate_action_refresh(
                    QuickGuard(), {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), 1000.0, state)
                await task

        asyncio.run(scenario())
        self.assertTrue(captured.get("daemon"), "the refresh worker thread must be created with daemon=True")

    def test_shutdown_cancels_and_joins_pending_corporate_action_tasks(self):
        """HIGH finding 1 (fix round 3, 'keep the task and join or cancel it
        at shutdown'): directly exercises the extracted
        `_shutdown_corporate_action_tasks` seam -- a still-pending task
        (here, a plain asyncio.sleep()-based fake standing in for a
        background refresh task, so this test itself completes quickly
        rather than needing to wait out a real hanging OS thread) must be
        cancelled and joined, not left running past the call."""
        import asyncio
        import runner as runner_module

        async def scenario():
            long_sleep_task = asyncio.create_task(asyncio.sleep(600))
            already_done_task = asyncio.create_task(asyncio.sleep(0))
            await already_done_task
            state = {"in_flight": False, "tasks": [long_sleep_task, already_done_task]}
            await runner_module._shutdown_corporate_action_tasks(state)
            self.assertTrue(long_sleep_task.done(), "a still-pending task must be cancelled, not left running")
            self.assertTrue(long_sleep_task.cancelled())
            self.assertTrue(already_done_task.done())

        asyncio.run(scenario())

    def test_shutdown_is_a_noop_with_no_tasks(self):
        import asyncio
        import runner as runner_module

        async def scenario():
            await runner_module._shutdown_corporate_action_tasks({"in_flight": False})
            await runner_module._shutdown_corporate_action_tasks({"in_flight": False, "tasks": []})

        asyncio.run(scenario())

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_shutdown_cleanup_still_runs_when_port_stop_raises(self):
        """LOW finding 7 (fix round 4)/H13 (fix round 5): `_shutdown_
        corporate_action_tasks` must still run, and actually cancel a
        still-hanging refresh task, even when `port.stop()` itself raises
        -- the nested `finally` around it, not merely the outer one, is
        what guarantees this. Patches `port.stop` to raise after
        construction, so run_native's own exception path (not a happy
        path) is what this test drives."""
        from simulation import SimulatedPort
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=1, cleanup_seconds=1, order_timeout_seconds=1)
        config["sessions"] = {"extended_hours": True, "overnight_holds": True,
                              "overnight_gross_multiple": "1.0"}
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True

        class HangingGuard:
            def refresh(self, symbols, *, start, end, now):
                import time as time_module
                time_module.sleep(30)  # outlives the trial + cleanup + shutdown entirely

            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                return {}

        config["_corporate_action_guard"] = HangingGuard()
        ca_refresh_state = {"in_flight": False}
        # MEDIUM finding (fix round 5): asyncio.run()'s own Runner.close()
        # cancels every outstanding Task regardless of run_native's OWN
        # explicit cleanup call (the same redundancy documented for G6) --
        # so merely checking the end state of ca_refresh_state["tasks"]
        # after asyncio.run() returns cannot distinguish "run_native's own
        # nested finally called _shutdown_corporate_action_tasks despite
        # port.stop() raising" from "asyncio.run()'s unrelated auto-cancel
        # produced the same end state anyway". A recording wrapper around
        # the exact named function proves the EXPLICIT call site fired.
        calls = []
        original_shutdown = runner_module._shutdown_corporate_action_tasks

        async def recording_shutdown(state):
            calls.append(1)
            return await original_shutdown(state)

        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=1, cleanup_seconds=1))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
            port = SimulatedPort(controller, policy.symbols, price=lambda symbol, tick: Decimal("100"))

            async def raising_stop():
                raise RuntimeError("port.stop() itself fails")

            port.stop = raising_stop
            controller.port = port
            with patch.object(runner_module, "_shutdown_corporate_action_tasks", recording_shutdown):
                with self.assertRaises(RuntimeError):
                    asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                           "fixture", config, "100000", ca_refresh_state=ca_refresh_state))
            ledger.close()
        self.assertGreaterEqual(len(calls), 1,
                                "the nested finally must call _shutdown_corporate_action_tasks directly "
                                "even when port.stop() itself raises, not rely on asyncio.run()'s own "
                                "unrelated task-cancellation cleanup")
        pending = [t for t in ca_refresh_state.get("tasks", []) if not t.done()]
        self.assertEqual(pending, [], "the refresh task must still be cancelled even though port.stop() raised")
        self.assertTrue(any(t.cancelled() for t in ca_refresh_state.get("tasks", [])),
                        "at least one task must have been genuinely cancelled despite the port.stop() error")

    def test_resolve_does_not_crash_when_the_future_is_already_cancelled(self):
        """H14 (fix round 5): `asyncio.wait_for` cancels the future it is
        waiting on when its OWN caller is cancelled (here, shutdown
        cancelling the task while the worker thread is still blocked in
        `fetch()`) -- the worker's own late `_resolve()` callback (run via
        `loop.call_soon_threadsafe` once `fetch()` finally returns, well
        after that cancellation) must check `fut.done()` before calling
        `set_result` on it, or it raises `InvalidStateError` inside that
        scheduled callback, which the loop's own exception handler would
        otherwise have to swallow."""
        import threading
        from datetime import date
        import corporate_actions as CA
        import runner as runner_module

        release = threading.Event()
        loop_exceptions = []

        class Src:
            def fetch(self, symbols, start, end):
                release.wait(3)  # still running when shutdown cancels the waiting task
                return {s: [] for s in symbols}

        async def scenario():
            loop = asyncio.get_running_loop()
            loop.set_exception_handler(lambda loop, context: loop_exceptions.append(context))
            monitor = CA.CorporateActionMonitor(Src(), clock=lambda: 1000.0)
            state = {"in_flight": False}
            await runner_module._schedule_corporate_action_refresh(
                monitor, {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), 1000.0, state)
            await asyncio.sleep(0.05)  # let the worker actually start and block on `release`
            await runner_module._shutdown_corporate_action_tasks(state)  # cancels the still-waiting task
            release.set()  # let the worker's fetch() finally return, well after cancellation
            await asyncio.sleep(0.2)  # give _resolve()'s call_soon_threadsafe callback a chance to run

        asyncio.run(scenario())
        self.assertEqual(loop_exceptions, [], "the worker's late _resolve() must not raise on an "
                                              "already-cancelled future")

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_worker_swallows_runtimeerror_when_the_loop_is_already_closed(self):
        """LOW finding 5 (fix round 4)/H15 (fix round 5): once asyncio.run()
        closes the loop, a still-running worker thread's own `loop.
        call_soon_threadsafe` back to that now-closed loop raises
        RuntimeError -- the worker must swallow exactly that (the late
        result is simply dropped), never crash its own daemon thread with
        an unhandled exception."""
        import threading
        import time as time_module
        from datetime import date

        release = threading.Event()
        excepthook_calls = []
        original_hook = threading.excepthook

        def recording_hook(args):
            excepthook_calls.append(args)

        class HangingGuard:
            def refresh(self, symbols, *, start, end, now):
                release.wait(5)  # still running well after asyncio.run() itself returns

        async def scenario():
            state = {"in_flight": False}
            original_timeout = runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS
            runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS = 0.05
            try:
                await runner_module._schedule_corporate_action_refresh(
                    HangingGuard(), {"AAPL"}, date(2026, 9, 17), date(2026, 12, 24), 1000.0, state)
                await asyncio.sleep(0.1)  # let the timeout fire; the worker itself is still running
            finally:
                runner_module.CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS = original_timeout

        threading.excepthook = recording_hook
        try:
            asyncio.run(scenario())  # returns/closes its own loop while the worker is still hanging
            release.set()  # let the worker finish now that the loop is already closed
            time_module.sleep(0.3)  # give the worker's own finally a moment to run against the closed loop
        finally:
            threading.excepthook = original_hook
        self.assertEqual(excepthook_calls, [], "the worker must swallow RuntimeError from a closed loop, "
                                              "not crash its own daemon thread")

    @unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
    def test_run_native_actually_cancels_a_hanging_refresh_at_its_own_shutdown(self):
        """G6 (fix round 4): run_native's OWN finally block must actually
        CALL _shutdown_corporate_action_tasks (not merely that the
        function works when called directly, tested above) -- a guard
        whose refresh() hangs well past the trial's own duration must be
        genuinely cancelled by the time run_native returns. G5: the
        cancellation path (not just an ordinary timeout) must also
        invalidate the attempt via refresh_timed_out(), proven here by the
        guard recording that call. The daemon-thread bridge (finding 6)
        keeps this test itself fast regardless of the hang's length."""
        from simulation import SimulatedPort
        config, _, _ = load_config(SOURCE / "config.json")
        config.update(duration_seconds=1, cleanup_seconds=1, order_timeout_seconds=1)
        config["sessions"] = {"extended_hours": True, "overnight_holds": True,
                              "overnight_gross_multiple": "1.0"}
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True

        class HangingGuard:
            def __init__(self):
                self.timed_out_calls = []

            def refresh(self, symbols, *, start, end, now):
                import time as time_module
                time_module.sleep(30)  # outlives the trial + cleanup + shutdown entirely

            def refresh_timed_out(self, symbols):
                self.timed_out_calls.append(tuple(sorted(symbols)))

            def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
                return {}

        guard = HangingGuard()
        config["_corporate_action_guard"] = guard
        ca_refresh_state = {"in_flight": False}
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "journal.db", RiskLimits(trial_seconds=1, cleanup_seconds=1))
            ledger.start_trial(time.time())
            controller = Controller(ledger, time.time() + 3600, market_open=True)
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4, warmup_samples=4,
                                  warmup_seconds=.06, sample_seconds=.02, rebalance_seconds=.02,
                                  min_hold_seconds=.05, max_hold_seconds=.4, cooldown_seconds=.05)
            port = SimulatedPort(controller, policy.symbols, price=lambda symbol, tick: Decimal("100"))
            controller.port = port
            started = time.monotonic()
            asyncio.run(run_native(controller, policy, [{"symbol": s} for s in policy.symbols],
                                   "fixture", config, "100000", ca_refresh_state=ca_refresh_state))
            elapsed = time.monotonic() - started
            ledger.close()
        self.assertLess(elapsed, 15, "run_native must not be delayed by the hanging refresh thread")
        pending = [t for t in ca_refresh_state.get("tasks", []) if not t.done()]
        self.assertEqual(pending, [], "run_native's own shutdown must actually cancel the hanging task")
        self.assertTrue(any(t.cancelled() for t in ca_refresh_state.get("tasks", [])),
                        "at least one task must have been genuinely cancelled, not merely completed")
        self.assertGreater(len(guard.timed_out_calls), 0,
                           "cancellation must invalidate the attempt via refresh_timed_out()")


if __name__ == "__main__":
    unittest.main()
