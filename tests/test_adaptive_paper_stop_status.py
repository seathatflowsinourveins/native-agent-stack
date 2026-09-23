"""Local interruption fixtures; no broker, credentials or production ledger."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import runner

try:
    import nautilus_trader
    import alpaca
    NATIVE = True
except ImportError:
    NATIVE = False


class StopClassification(unittest.TestCase):
    def outcome(self, reason, completed=False):
        reconciliation = {"positions": 0, "open_orders": 0}
        return {"reconciliation": reconciliation, "accounting": {"halted_reason": None},
                "adapter_errors": [], "decision_exit": {
                    "reason": reason, "duration_completed": completed}}

    def status(self, outcome, fills=0, overnight=False, now=0):
        return runner._run_native_status(outcome["reconciliation"], [], fills, outcome,
                                         {"overnight_holds": overnight}, now)

    def test_flat_interrupted_trial_never_claims_success_even_with_fills(self):
        for reason in ("transport_gap", "controller_stop", "stop_file", "risk_halt",
                       "mark_to_market_refused", "native_task_completed",
                       "native_task_cancelled", "native_task_failed", "adapter_error"):
            for fills in (0, 2):
                with self.subTest(reason=reason, fills=fills):
                    self.assertEqual(self.status(self.outcome(reason), fills), "needs_attention")

    def test_elapsed_duration_cannot_override_an_interruption(self):
        self.assertEqual(self.status(self.outcome("transport_gap", True)), "needs_attention")

    def test_duration_success_requires_explicit_completion(self):
        self.assertEqual(self.status(self.outcome("duration_completed")), "needs_attention")
        self.assertEqual(self.status(self.outcome("duration_completed", True)), "completed_no_signals")
        self.assertEqual(self.status(self.outcome("duration_completed", True), 2), "passed")

    def test_clean_deliberate_boundary_retains_flat_and_overnight_semantics(self):
        outcome = self.outcome("session_boundary")
        self.assertEqual(self.status(outcome), "completed_no_signals")
        outcome["reconciliation"]["positions"] = 1
        post = datetime(2026, 9, 23, 22, tzinfo=timezone.utc).timestamp()
        self.assertEqual(self.status(outcome, overnight=True, now=post), "held_overnight")
        outcome["decision_exit"]["reason"] = "controller_stop"
        self.assertEqual(self.status(outcome, overnight=True, now=post), "needs_attention")


@unittest.skipUnless(NATIVE, "requires pinned combined native runtime")
class StopLifecycle(unittest.TestCase):
    def run_fixture(self, mode):
        from safety import Ledger, RiskLimits, SafetyError
        from simulation import SimulatedPort
        from strategies import PolicyConfig
        import native_adapter

        config, _, _ = runner.load_config(SOURCE / "config.json")
        config.update(duration_seconds=1, cleanup_seconds=1, order_timeout_seconds=1)
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "ledger.sqlite3", RiskLimits(trial_seconds=1, cleanup_seconds=1))
            ledger.start_trial(time.time())
            self.addCleanup(ledger.close)
            controller = runner.Controller(ledger, time.time() + 3600, market_open=True)
            # Warmup exceeds the trial, so no signal or order is possible.
            policy = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA"), max_positions=4, warmup_seconds=32)

            class Port(SimulatedPort):
                async def start(self, on_quote, on_order):
                    await super().start(on_quote, on_order)
                    if mode == "transport_gap":
                        self.health.update(frozen=True, reasons=["callback_failure"],
                                           callback_failure={"stage": "on_quote", "exception_type": "ValueError"})
                    elif mode == "controller_stop":
                        controller.stop = True

                async def stop(self):
                    await super().stop()
                    self.health["reasons"] = ["shutdown_marker"]
                    if mode == "port_stop_failure":
                        raise RuntimeError("private transport shutdown details")

                async def snapshot(self):
                    snapshot = await super().snapshot()
                    if controller.stop:
                        if mode == "final_snapshot_failure":
                            raise RuntimeError("private broker response")
                        if mode == "final_reconcile_failure":
                            snapshot["account"]["cash"] = "99999"
                        if mode in ("late_transport_gap", "late_stale"):
                            self.health["reasons"] = ["callback_failure" if mode == "late_transport_gap" else "quote_stale"]
                    return snapshot

            port = Port(controller, policy.symbols)
            controller.port = port
            assets = [{"symbol": s} for s in policy.symbols]
            stopped = asyncio.Event()

            async def task_end():
                if mode.startswith(("final_", "late_")) or mode == "port_stop_failure":
                    await stopped.wait()
                    return
                if mode.startswith("shutdown_"):
                    await stopped.wait()
                    if mode == "shutdown_cancelled":
                        raise asyncio.CancelledError()
                    await asyncio.Event().wait()
                await asyncio.sleep(.02)
                if mode == "native_task_failed":
                    raise RuntimeError("private exception message must not enter the receipt")
                if mode == "native_task_cancelled":
                    raise asyncio.CancelledError()

            session = SimpleNamespace(run_async=task_end, stop=stopped.set,
                                      reconciliation=None, errors=[])
            with patch.object(runner, "DEFAULT_STOP", Path(root) / "STOP"):
                if mode.startswith(("final_", "late_")) or mode == "port_stop_failure":
                    with patch.object(native_adapter, "build_node", return_value=session):
                        return asyncio.run(runner.run_native(controller, policy, assets, "fixture", config, "100000"))
                if mode.startswith("shutdown_"):
                    original_wait = asyncio.wait_for
                    async def bounded_wait(task, timeout):
                        return await original_wait(task, min(timeout, .02))
                    with patch.object(native_adapter, "build_node", return_value=session), \
                         patch.object(runner.asyncio, "wait_for", side_effect=bounded_wait):
                        return asyncio.run(runner.run_native(controller, policy, assets, "fixture", config, "100000"))
                if mode.startswith("native_task_"):
                    with patch.object(native_adapter, "build_node", return_value=session):
                        return asyncio.run(runner.run_native(controller, policy, assets, "fixture", config, "100000"))
                if mode == "mark_to_market_refused":
                    with patch.object(ledger, "mark_to_market", side_effect=SafetyError("invalid_quote")):
                        return asyncio.run(runner.run_native(controller, policy, assets, "fixture", config, "100000"))
                return asyncio.run(runner.run_native(controller, policy, assets, "fixture", config, "100000"))

    def test_flat_gap_records_health_before_shutdown_and_refuses_success(self):
        outcome = self.run_fixture("transport_gap")
        self.assertEqual(outcome["status"], "needs_attention")
        decision = outcome["decision_exit"]
        self.assertEqual(decision["reason"], "transport_gap")
        self.assertFalse(decision["duration_completed"])
        self.assertEqual(decision["transport_health"]["reasons"], ["callback_failure"])
        self.assertEqual(decision["transport_health"]["callback_failure"],
                         {"stage": "on_quote", "exception_type": "ValueError"})
        self.assertTrue(outcome["flat"])

    def test_controller_stop_and_mark_refusal_keep_explicit_reasons(self):
        for mode in ("controller_stop", "mark_to_market_refused"):
            with self.subTest(mode=mode):
                outcome = self.run_fixture(mode)
                self.assertEqual(outcome["status"], "needs_attention")
                self.assertEqual(outcome["decision_exit"]["reason"], mode)

    def test_premature_node_completion_cancellation_and_error_are_distinct(self):
        for mode in ("native_task_completed", "native_task_cancelled", "native_task_failed"):
            with self.subTest(mode=mode):
                outcome = self.run_fixture(mode)
                self.assertEqual(outcome["status"], "needs_attention")
                self.assertEqual(outcome["decision_exit"]["reason"], mode)
                self.assertNotIn("private exception", str(outcome))

    def test_genuine_duration_no_signal_completion_stays_successful(self):
        outcome = self.run_fixture("duration_completed")
        self.assertEqual(outcome["status"], "completed_no_signals")
        self.assertTrue(outcome["decision_exit"]["duration_completed"])
        self.assertEqual(outcome["decision_exit"]["reason"], "duration_completed")
        self.assertEqual(outcome["native_fill_events"], 0)

    def test_shutdown_timeout_or_cancellation_cannot_claim_normal_duration_success(self):
        for mode, kind in (("shutdown_timeout", "TimeoutError"), ("shutdown_cancelled", "CancelledError")):
            with self.subTest(mode=mode):
                outcome = self.run_fixture(mode)
                self.assertEqual(outcome["status"], "needs_attention")
                self.assertEqual(outcome["decision_exit"]["reason"], "duration_completed")
                self.assertTrue(outcome["decision_exit"]["duration_completed"])
                self.assertEqual(outcome["shutdown_failure"],
                                 {"stage": "native_task_shutdown", "exception_type": kind})

    def test_final_snapshot_and_reconcile_failure_retain_the_decision(self):
        for mode, stage, kind in (("final_snapshot_failure", "final_snapshot", "RuntimeError"),
                                  ("final_reconcile_failure", "final_reconciliation", "SafetyError")):
            with self.subTest(mode=mode):
                outcome = self.run_fixture(mode)
                self.assertEqual(outcome["status"], "needs_attention")
                self.assertEqual(outcome["decision_exit"]["reason"], "duration_completed")
                self.assertTrue(outcome["decision_exit"]["duration_completed"])
                self.assertEqual(outcome["finalization_failure"]["stage"], stage)
                self.assertEqual(outcome["finalization_failure"]["exception_type"], kind)
                self.assertNotIn("private", str(outcome))
                self.assertIsNone(outcome["reconciliation"])

    def test_port_stop_failure_retains_pre_shutdown_health(self):
        outcome = self.run_fixture("port_stop_failure")
        self.assertEqual(outcome["status"], "needs_attention")
        self.assertEqual(outcome["decision_exit"]["reason"], "duration_completed")
        self.assertNotIn("shutdown_marker", str(outcome["pre_shutdown_health"]))
        self.assertEqual(outcome["shutdown_failure"],
                         {"stage": "transport_shutdown", "exception_type": "RuntimeError"})
        self.assertNotIn("private", str(outcome))

    def test_late_transport_gap_is_seen_before_intentional_shutdown(self):
        outcome = self.run_fixture("late_transport_gap")
        self.assertEqual(outcome["status"], "needs_attention")
        self.assertEqual(outcome["decision_exit"]["reason"], "duration_completed")
        self.assertEqual(outcome["finalization_failure"]["stage"], "final_transport_health")
        self.assertEqual(outcome["pre_shutdown_health"]["reasons"], ["callback_failure"])

    def test_late_stale_health_keeps_existing_exit_semantics(self):
        outcome = self.run_fixture("late_stale")
        self.assertEqual(outcome["status"], "completed_no_signals")
        self.assertEqual(outcome["pre_shutdown_health"]["reasons"], ["quote_stale"])
        self.assertIsNone(outcome["finalization_failure"])
