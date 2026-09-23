"""Crossed-quote qualification using local queues/native engine; no broker calls."""
import asyncio
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import transport as t
import runner
from safety import Ledger, Quote, RiskLimits, SafetyError
from strategies import AdaptivePolicy, PolicyConfig
from native_adapter import NativeSession, NativeOrderRejected, quote_components
from native_strategy import AdaptiveStrategy


class Stamp:
    def __init__(self, ns):
        self.ns = ns

    def to_unix_nano(self):
        return self.ns


def raw(ns, symbol="AAPL", **changes):
    row = {"S": symbol, "bp": "100", "ap": "100.01", "bs": "100", "as": "100", "t": Stamp(ns)}
    row.update(changes)
    return row


class Quarantine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        stop_patch = patch("safety.DEFAULT_STOP", Path(self.tmp.name) / "STOP")
        stop_patch.start()
        self.addCleanup(stop_patch.stop)
        self.ledger = Ledger(Path(self.tmp.name) / "ledger.sqlite3", RiskLimits())
        self.ledger.start_trial(time.time())
        self.controller = runner.Controller(self.ledger, time.time() + 3600, market_open=True)
        self.port = t.AlpacaPaperTransport("fixture-key", "fixture-secret", ["SPY", "AAPL"],
            before_request=self.controller.before_request, before_submit=self.controller.before_submit,
            sink_observation=self.controller.observe, required_quote_symbols=["SPY"], quote_timeout=3)
        self.controller.port = self.controller.bind(self.port)
        self.port._loop = asyncio.get_running_loop()
        self.port._started = True
        self.port._auth = self.port._acks = {"orders": True, "quotes": True}
        self.policy = AdaptivePolicy(PolicyConfig(symbols=("SPY", "AAPL"), benchmarks=("SPY",), max_positions=2))
        self.strategy = AdaptiveStrategy(self.policy, self.ledger, "quarantine", transport=self.port)
        self.session = NativeSession(self.port, [{"symbol": s} for s in ("SPY", "AAPL")])
        self.ticks = []
        self.session.data = SimpleNamespace(clock=SimpleNamespace(timestamp_ns=time.time_ns),
            subscriptions={"SPY", "AAPL"}, _handle_data=self.ticks.append)
        # The production owner-loop wiring is deliberately used in this fixture.
        if hasattr(runner, "install_quote_quarantine"):
            runner.install_quote_quarantine(self.controller, self.strategy, self.session)
        def quote_sink(q):
            self.controller.quote(q)
            self.session.on_quote(q)
            if self.ticks:
                self.strategy.on_quote(self.ticks[-1])
        self.port._on_quote = quote_sink
        self.port._on_order = lambda _: None
        self.consumer = asyncio.create_task(self.port._consume_events())
        self.ns = time.time_ns() - 100_000_000
        await self.push(raw(self.ns, "SPY"))
        await self.push(raw(self.ns))

    async def asyncTearDown(self):
        self.consumer.cancel()
        await asyncio.gather(self.consumer, return_exceptions=True)
        await self.port.stop()
        self.ledger.close()
        self.tmp.cleanup()

    async def push(self, row):
        self.port._enqueue("quote", row)
        for _ in range(100):
            if self.port._events.empty():
                break
            await asyncio.sleep(.001)

    async def test_unexposed_cross_invalidates_all_execution_caches_then_strictly_newer_recovers(self):
        history = list(self.policy.history["AAPL"])
        await self.push(raw(self.ns + 1, bp="101"))
        self.assertFalse(self.port.health["frozen"])
        for cache in (self.port._quote_values, self.controller.quotes, self.session.quotes, self.policy.latest):
            self.assertNotIn("AAPL", cache)
        self.assertEqual(list(self.policy.history["AAPL"]), history)
        self.assertTrue(self.port.ready)  # nonbenchmark only
        await self.push(raw(self.ns + 1))
        self.assertNotIn("AAPL", self.policy.latest)
        await self.push(raw(self.ns + 2))
        for cache in (self.port._quote_values, self.controller.quotes, self.session.quotes, self.policy.latest):
            self.assertIn("AAPL", cache)
        self.assertFalse(self.port.health["frozen"])
        self.assertEqual(self.port.health["quote_quarantine"]["released"], 1)

    async def test_older_cross_cannot_invalidate_newer_accepted_quote(self):
        await self.push(raw(self.ns - 1, bp="101"))
        self.assertFalse(self.port.health["frozen"])
        self.assertIn("AAPL", self.controller.quotes)
        self.assertEqual(self.port._quote_values["AAPL"]["ts_ns"], self.ns)

    async def test_equal_time_cross_conflict_invalidates_and_equal_valid_cannot_release(self):
        await self.push(raw(self.ns, bp="101"))
        self.assertFalse(self.port.health["frozen"])
        await self.push(raw(self.ns))
        self.assertNotIn("AAPL", self.controller.quotes)

    async def test_benchmark_blocks_all_entries_but_recovers_before_existing_deadline(self):
        self.port._ever_ready = True
        watchdog = asyncio.create_task(self.port._watchdog())
        try:
            await self.push(raw(self.ns + 1, "SPY", bp="101"))
            self.assertFalse(self.port.ready)
            await asyncio.sleep(.12)
            self.assertFalse(self.port.health["frozen"])
            self.assertIsNone(self.policy._features("SPY", time.time()))
            await self.push(raw(self.ns + 2, "SPY"))
            self.assertTrue(self.port.ready)
            self.assertNotIn("quote_stale", self.port.health["reasons"])
        finally:
            watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)

    async def test_held_symbol_escalates_without_erasing_valuation_or_owned_orders(self):
        q = self.controller.quotes["AAPL"]
        self.ledger.reserve_intent("owned", "AAPL", "buy", "1", "100.01", quote=q,
            now=time.time(), market_open=True, session_close=time.time() + 3600)
        self.ledger.record_order("owned", "broker-owned", "filled", "1", "100.01")
        self.ledger.mark_to_market([q], time.time())
        before = self.ledger.accounting()
        await self.push(raw(self.ns + 1, bp="101"))
        self.assertTrue(self.controller.stop)
        self.assertIn("quarantined_exposure", self.port.health["reasons"])
        self.assertEqual(self.ledger.accounting().unrealized_pnl_usd, before.unrealized_pnl_usd)
        self.assertEqual(self.ledger.positions()["AAPL"].qty, Decimal(1))
        await self.push(raw(self.ns + 2))
        self.assertTrue(self.port.health["frozen"])

    async def test_native_pending_escalates_and_old_queued_tick_cannot_revive_policy(self):
        queued = self.ticks[-1]
        self.strategy.pending["native-not-yet-reserved"] = {"symbol": "AAPL", "side": "buy"}
        await self.push(raw(self.ns + 1, bp="101"))
        self.strategy.on_quote(queued)
        self.assertNotIn("AAPL", self.policy.latest)
        self.assertTrue(self.controller.stop)
        self.assertIn("native-not-yet-reserved", self.strategy.pending)

    async def test_crossed_target_refused_before_submit_without_reserving_or_http(self):
        await self.push(raw(self.ns + 1, bp="101"))
        with patch.object(self.port._client._session._session, "request") as wire:
            with self.assertRaises(NativeOrderRejected):
                await self.port.submit({"client_order_id": "blocked", "symbol": "AAPL", "side": "buy",
                                        "qty": "1", "limit_price": "100.01"})
        wire.assert_not_called()
        self.assertEqual(self.ledger.intents(), [])

    async def test_reserved_then_crossed_refused_before_request_without_budget_or_http(self):
        order = {"client_order_id": "reserved", "symbol": "AAPL", "side": "buy", "qty": "1", "limit_price": "100.01"}
        self.controller.before_submit(order)
        await self.push(raw(self.ns + 1, bp="101"))
        with self.assertRaisesRegex(SafetyError, "no_current_quote"):
            await self.controller.before_request("submit", client_id="reserved")
        self.assertFalse(self.ledger.intents()[0].submit_attempted)
        self.assertEqual(len(self.ledger.unresolved()), 1)

    async def test_crossing_after_budget_before_wire_is_proven_not_sent_and_counts_attempt(self):
        async def budget(kind, client_id=None):
            await self.controller.before_request(kind, client_id)
            if kind == "submit":
                await self.push(raw(self.ns + 1, bp="101"))
        self.port.before_request = budget
        with patch.object(self.port._client._session._session, "request") as wire:
            with self.assertRaises(t.SubmissionNotSent):
                await self.port.submit({"client_order_id": "wire-blocked", "symbol": "AAPL", "side": "buy",
                                        "qty": "1", "limit_price": "100.01"})
        wire.assert_not_called()
        row = self.ledger.intents()[0]
        self.assertEqual(row.status, "not_sent")
        self.assertTrue(row.submit_attempted)
        self.assertTrue(self.controller.stop)

    async def test_benchmark_recovery_cannot_revive_already_invalidated_unsent_intent(self):
        from test_adaptive_paper_transport import response, order
        async def budget(kind, client_id=None):
            await self.controller.before_request(kind, client_id)
            if kind == "submit":
                await self.push(raw(self.ns + 1, "SPY", bp="101"))
                await self.push(raw(self.ns + 2, "SPY"))
                self.assertTrue(self.port.ready)
        self.port.before_request = budget
        payload = order(client_order_id="generation", symbol="AAPL")
        with patch.object(self.port._client._session._session, "request", return_value=response(payload)) as wire:
            with self.assertRaises(t.SubmissionNotSent):
                await self.port.submit({"client_order_id": "generation", "symbol": "AAPL", "side": "buy",
                                        "qty": "1", "limit_price": "100.01"})
        wire.assert_not_called()
        self.assertEqual(self.ledger.intents()[0].status, "not_sent")

    async def test_crossing_after_http_started_retains_ambiguous_reservation(self):
        await self.assert_http_started_retains_ambiguous_reservation(raw(self.ns + 1, bp="101"))

    async def test_equal_timestamp_conflict_after_http_started_retains_ambiguous_reservation(self):
        await self.assert_http_started_retains_ambiguous_reservation(raw(self.ns, bs="101"))

    async def assert_http_started_retains_ambiguous_reservation(self, invalidation):
        wired, release = threading.Event(), threading.Event()
        def request(*args, **kwargs):
            wired.set()
            if not release.wait(2):
                raise AssertionError("test did not release HTTP boundary")
            raise TimeoutError("synthetic lost response")
        class NotFound(Exception):
            status_code = 404
        with patch.object(self.port._client._session._session, "request", side_effect=request), \
                patch.object(self.port._client, "get_order_by_client_id", side_effect=NotFound):
            submit = asyncio.create_task(self.port.submit({"client_order_id": "possibly-sent", "symbol": "AAPL",
                                "side": "buy", "qty": "1", "limit_price": "100.01"}))
            try:
                for _ in range(100):
                    if wired.is_set():
                        break
                    await asyncio.sleep(.005)
                self.assertTrue(wired.is_set())
                await self.push(invalidation)
            finally:
                release.set()
            with self.assertRaises(t.AmbiguousSubmission):
                await submit
        row = self.ledger.intents()[0]
        self.assertEqual(row.status, "reserved")
        self.assertTrue(row.submit_attempted)
        self.assertEqual(len(self.ledger.unresolved()), 1)
        self.assertNotIn("possibly-sent", self.port._not_sent)
        self.assertIn("quarantined_exposure", self.port.health["reasons"])

    async def test_no_recovery_by_existing_quote_deadline_is_sticky(self):
        self.port.quote_timeout = .05
        await self.push(raw(time.time_ns(), bp="101"))
        watchdog = asyncio.create_task(self.port._watchdog())
        try:
            await asyncio.sleep(.03)
            await self.push(raw(time.time_ns(), bp="101"))
            await asyncio.sleep(.05)
            self.assertIn("quote_quarantine_expired", self.port.health["reasons"])
            await self.push(raw(time.time_ns()))
            self.assertTrue(self.port.health["frozen"])
            with self.assertRaises(t.TransportError):
                self.port.mark_reconciled()
        finally:
            watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)

    async def test_halted_or_stale_recovery_cannot_release_quarantine(self):
        await self.push(raw(self.ns + 1, bp="101"))
        await self.push(raw(time.time_ns() - 4_000_000_000))
        self.assertNotIn("AAPL", self.port._quote_values)
        await self.push(raw(self.ns + 2, halted=True))
        self.assertNotIn("AAPL", self.port._quote_values)
        self.assertTrue(self.port.health["frozen"])

    async def test_identical_halted_quote_duplicate_keeps_baseline_without_bypassing_validation(self):
        halted = raw(self.ns + 1, halted=True)
        await self.push(halted)
        self.assertTrue(self.port._quote_values["AAPL"]["halted"])
        self.assertFalse(self.port.health["frozen"])
        tick_count = len(self.ticks)
        with patch.object(self.port, "_quarantine_validator", wraps=quote_components) as validate:
            self.assertIsNone(self.port._stream_quote(halted))
            await self.push(halted)
        self.assertEqual(validate.call_count, 2)
        self.assertEqual(len(self.ticks), tick_count)
        self.assertFalse(self.port.health["frozen"])
        self.assertEqual(self.port.health["quote_quarantine"]["invalidated"], 0)

    async def test_equal_timestamp_valid_conflict_quarantines_until_strictly_newer(self):
        history = list(self.policy.history["AAPL"])
        await self.push(raw(self.ns, bp="100.001"))
        self.assertFalse(self.port.health["frozen"])
        for cache in (self.port._quote_values, self.controller.quotes, self.session.quotes, self.policy.latest):
            self.assertNotIn("AAPL", cache)
        self.assertEqual(list(self.policy.history["AAPL"]), history)
        await self.push(raw(self.ns))
        self.assertNotIn("AAPL", self.policy.latest)
        await self.push(raw(self.ns - 1))
        self.assertNotIn("AAPL", self.policy.latest)
        await self.push(raw(self.ns + 1))
        self.assertIn("AAPL", self.policy.latest)
        self.assertEqual(self.policy.quote_ns["AAPL"], self.ns + 1)
        self.assertFalse(self.port.health["frozen"])
        counts = self.port.health["quote_quarantine"]
        self.assertEqual(counts["timestamp_conflict_invalidations"], 1)
        self.assertEqual(counts["crossed_invalidations"], 0)

    async def test_equal_timestamp_conflict_without_timely_recovery_expires(self):
        self.port.quote_timeout = .05
        ns = time.time_ns()
        await self.push(raw(ns))
        await self.push(raw(ns, bs="101"))
        self.assertFalse(self.port.health["frozen"])
        watchdog = asyncio.create_task(self.port._watchdog())
        try:
            await asyncio.sleep(.08)
            self.assertIn("quote_quarantine_expired", self.port.health["reasons"])
            await self.push(raw(time.time_ns()))
            self.assertTrue(self.port.health["frozen"])
        finally:
            watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)

    async def test_equal_timestamp_conflict_held_escalates_and_preserves_valuation(self):
        quote = self.controller.quotes["AAPL"]
        self.ledger.reserve_intent("held-conflict", "AAPL", "buy", "1", "100.01", quote=quote,
            now=time.time(), market_open=True, session_close=time.time() + 3600)
        self.ledger.record_order("held-conflict", "broker-held", "filled", "1", "100.01")
        self.ledger.mark_to_market([quote], time.time())
        before = self.ledger.accounting()
        await self.push(raw(self.ns, bs="101"))
        self.assertIn("quarantined_exposure", self.port.health["reasons"])
        self.assertTrue(self.controller.stop)
        self.assertEqual(self.ledger.accounting().unrealized_pnl_usd, before.unrealized_pnl_usd)
        self.assertEqual(self.ledger.positions()["AAPL"].qty, Decimal(1))
        await self.push(raw(self.ns + 1))
        self.assertTrue(self.port.health["frozen"])

    async def test_equal_timestamp_conflict_native_pending_retains_ownership_and_blocks_queued_tick(self):
        queued = self.ticks[-1]
        self.strategy.pending["pending-conflict"] = {"symbol": "AAPL", "side": "buy"}
        await self.push(raw(self.ns, bs="101"))
        self.strategy.on_quote(queued)
        self.assertNotIn("AAPL", self.policy.latest)
        self.assertIn("pending-conflict", self.strategy.pending)
        self.assertIn("quarantined_exposure", self.port.health["reasons"])
        self.assertTrue(self.controller.stop)

    async def test_equal_timestamp_conflict_reserved_refuses_request_without_budget(self):
        self.controller.before_submit({"client_order_id": "reserved-conflict", "symbol": "AAPL",
            "side": "buy", "qty": "1", "limit_price": "100.01"})
        await self.push(raw(self.ns, bs="101"))
        with self.assertRaisesRegex(SafetyError, "no_current_quote"):
            await self.controller.before_request("submit", client_id="reserved-conflict")
        self.assertIn("quarantined_exposure", self.port.health["reasons"])
        self.assertFalse(self.ledger.intents()[0].submit_attempted)
        self.assertEqual(len(self.ledger.unresolved()), 1)

    async def test_equal_timestamp_conflict_before_submit_has_no_reservation_or_http(self):
        await self.push(raw(self.ns, bs="101"))
        with patch.object(self.port._client._session._session, "request") as wire:
            with self.assertRaises(NativeOrderRejected):
                await self.port.submit({"client_order_id": "conflict-blocked", "symbol": "AAPL", "side": "buy",
                                        "qty": "1", "limit_price": "100.01"})
        wire.assert_not_called()
        self.assertEqual(self.ledger.intents(), [])

    async def test_equal_timestamp_conflict_after_budget_before_post_never_wires(self):
        async def budget(kind, client_id=None):
            await self.controller.before_request(kind, client_id)
            if kind == "submit":
                await self.push(raw(self.ns, bs="101"))
        self.port.before_request = budget
        with patch.object(self.port._client._session._session, "request") as wire:
            with self.assertRaises(t.SubmissionNotSent):
                await self.port.submit({"client_order_id": "conflict-wire", "symbol": "AAPL", "side": "buy",
                                        "qty": "1", "limit_price": "100.01"})
        wire.assert_not_called()
        self.assertEqual(self.ledger.intents()[0].status, "not_sent")
        self.assertTrue(self.ledger.intents()[0].submit_attempted)
        self.assertIn("quarantined_exposure", self.port.health["reasons"])

    async def test_benchmark_equal_conflict_recovery_cannot_revive_authorized_intent(self):
        async def budget(kind, client_id=None):
            await self.controller.before_request(kind, client_id)
            if kind == "submit":
                await self.push(raw(self.ns, "SPY", bs="101"))
                self.assertFalse(self.port.ready)
                self.assertNotIn("SPY", self.policy.latest)
                await self.push(raw(self.ns + 1, "SPY"))
                self.assertTrue(self.port.ready)
        self.port.before_request = budget
        with patch.object(self.port._client._session._session, "request") as wire:
            with self.assertRaises(t.SubmissionNotSent):
                await self.port.submit({"client_order_id": "conflict-generation", "symbol": "AAPL",
                                        "side": "buy", "qty": "1", "limit_price": "100.01"})
        wire.assert_not_called()
        self.assertEqual(self.ledger.intents()[0].status, "not_sent")

    async def test_benchmark_conflict_after_post_preserves_owned_order_and_blocks_dependent_entries(self):
        from test_adaptive_paper_transport import response, order
        intent = {"client_order_id": "benchmark-after-wire", "symbol": "AAPL", "side": "buy",
                  "qty": "1", "limit_price": "100.01"}
        accepted = order(client_order_id=intent["client_order_id"], symbol="AAPL", limit_price="100.01")
        wired, release = threading.Event(), threading.Event()
        def request(*args, **kwargs):
            wired.set()
            if not release.wait(2):
                raise AssertionError("test did not release HTTP boundary")
            return response(accepted)
        with patch.object(self.port._client._session._session, "request", side_effect=request) as wire:
            submit = asyncio.create_task(self.port.submit(intent))
            try:
                for _ in range(100):
                    if wired.is_set():
                        break
                    await asyncio.sleep(.005)
                self.assertTrue(wired.is_set())
                await self.push(raw(self.ns, "SPY", bs="101"))
                self.assertFalse(self.port.ready)
                self.assertFalse(self.port.health["frozen"])
                self.assertFalse(self.controller.stop)
                self.assertTrue(self.ledger.intents()[0].submit_attempted)
                with self.assertRaisesRegex(NativeOrderRejected, "admissions_not_ready"):
                    self.controller.before_submit(dict(intent, client_order_id="dependent-blocked"))
            finally:
                release.set()
            result = await submit
            self.assertEqual(result["status"], "new")
            self.assertEqual(len(self.ledger.unresolved()), 1)
            filled = dict(accepted, status="filled", filled_qty="1", filled_avg_price="100.01")
            with patch.object(self.port._client, "get_order_by_client_id", return_value=filled):
                reconciled = await self.port.submit(intent)  # existing ID is lookup-only
            self.assertEqual(reconciled["status"], "filled")
            self.assertEqual(wire.call_count, 1)
        self.assertEqual(self.ledger.positions()["AAPL"].qty, Decimal(1))
        self.assertEqual(self.ledger.unresolved(), [])
        self.assertFalse(self.port.ready)
        await self.push(raw(self.ns + 1, "SPY"))
        self.assertTrue(self.port.ready)
        self.assertFalse(self.port.health["frozen"])

    async def test_equal_timestamp_compound_invalidity_remains_fatal_even_after_tombstone(self):
        for active in (False, True):
            for changes in ({"bs": "0.5"}, {"bs": "-1"}, {"bp": "100.00000000000000001"},
                            {"bs": "1000000000000000000"}, {"halted": True}, {"t": None}, {"S": "PRIVATE"}):
                with self.subTest(active=active, changes=list(changes)):
                    # Reset this isolated fixture's executable state with a strictly newer valid quote.
                    self.port._reasons.clear()
                    self.port._callback_failure = None
                    self.ns += 10
                    await self.push(raw(self.ns))
                    if active:
                        await self.push(raw(self.ns, bs="101"))
                        self.port._reasons.clear()
                    await self.push(raw(self.ns, **changes))
                    self.assertIn("callback_failure", self.port.health["reasons"])

    async def test_reason_counters_count_invalidation_events_separately_from_episodes(self):
        await self.push(raw(self.ns, bs="101"))
        await self.push(raw(self.ns, bp="101"))
        await self.push(raw(self.ns + 1))
        await self.push(raw(self.ns + 1))  # exact duplicate is not a conflict
        counts = self.port.health["quote_quarantine"]
        self.assertEqual(counts["invalidated"], 1)
        self.assertEqual(counts["released"], 1)
        self.assertEqual(counts["crossed_invalidations"], 1)
        self.assertEqual(counts["timestamp_conflict_invalidations"], 1)
        diagnostic = runner._decision_transport_health(self.port)
        self.assertEqual(diagnostic["quote_quarantine"]["crossed_invalidations"], 1)
        self.assertEqual(diagnostic["quote_quarantine"]["timestamp_conflict_invalidations"], 1)

    async def test_no_handler_keeps_recovery_port_fail_closed(self):
        self.port._quarantine_handler = None
        await self.push(raw(self.ns + 1, bp="101"))
        self.assertTrue(self.port.health["frozen"])

    async def test_recovery_port_same_timestamp_size_update_preserves_confirmed_owned_exit(self):
        from test_adaptive_paper_transport import response, order
        self.port._quarantine_handler = None  # production recovery retains its original quote path
        quote = self.controller.quotes["AAPL"]
        self.ledger.reserve_intent("owned-before-recovery", "AAPL", "buy", "1", "100.01", quote=quote,
            now=time.time(), market_open=True, session_close=time.time() + 3600)
        self.ledger.record_order("owned-before-recovery", "owned-broker", "filled", "1", "100.01")
        await self.push(raw(self.ns, bs="101"))
        self.assertFalse(self.port.health["frozen"])
        self.assertEqual(self.port._quote_values["AAPL"]["bid_size"], "101")
        payload = order(client_order_id="owned-recovery-exit", symbol="AAPL", side="sell", limit_price="100",
                        status="filled", filled_qty="1", filled_avg_price="100")
        with patch.object(self.port._client._session._session, "request", return_value=response(payload)) as wire:
            result = await self.port.submit({"client_order_id": "owned-recovery-exit", "symbol": "AAPL",
                                "side": "sell", "qty": "1", "limit_price": "100"})
        self.assertEqual(wire.call_count, 1)
        self.assertEqual(wire.call_args.args[0], "POST")
        self.assertEqual(result["status"], "filled")
        self.assertEqual(self.ledger.positions(), {})
        self.assertEqual(self.ledger.unresolved(), [])
        self.assertFalse(self.port.health["frozen"])

    async def test_callback_failure_remains_fatal_after_transport_tombstone(self):
        def failed(symbol, ts):
            raise RuntimeError("private fixture message")
        self.port.set_quote_quarantine_handler(failed, validate=quote_components)
        await self.push(raw(self.ns + 1, bp="101"))
        self.assertNotIn("AAPL", self.port._quote_values)
        self.assertIn("callback_failure", self.port.health["reasons"])

    async def test_compound_invalid_cross_remains_fatal(self):
        for changes in ({"bs": "-1"}, {"bs": "0.5"}, {"bp": "101.00000000000000001"},
                        {"bp": "1000000000000000000"}, {"bs": "1000000000000000000"},
                        {"t": None}, {"S": "PRIVATE"}, {"halted": True},
                        {"t": Stamp(time.time_ns() - 4_000_000_000)},
                        {"t": Stamp(time.time_ns() + 1_000_000_000)}):
            with self.subTest(changes=list(changes)):
                self.port._reasons.clear()
                self.port._callback_failure = None
                await self.push(raw(self.ns + 1, **dict({"bp": "101"}, **changes)))
                self.assertTrue(self.port.health["frozen"])
                self.assertIn("callback_failure", self.port.health["reasons"])


class NativeQueuedQuotes(unittest.TestCase):
    def test_direct_adapter_malformed_timestamp_fails_before_tombstone_filter(self):
        for stamp in (0, -1, False, True, None, "100"):
            for tombstone in (None, 100):
                with self.subTest(timestamp=stamp, tombstone=tombstone):
                    session = NativeSession(None, [{"symbol": "SPY"}])
                    ticks = []
                    session.data = SimpleNamespace(clock=SimpleNamespace(timestamp_ns=time.time_ns),
                        subscriptions={"SPY"}, _handle_data=ticks.append)
                    if tombstone is not None:
                        session.invalidate_quote("SPY", tombstone)
                    session.on_quote({"symbol": "SPY", "bid": "100", "ask": "100.01",
                                      "bid_size": "100", "ask_size": "100", "ts_ns": stamp})
                    self.assertEqual(session.errors, ["quote_invalid_quote"])
                    self.assertEqual(session.quotes, {})
                    self.assertEqual(ticks, [])

    def test_actual_live_node_queued_old_and_equal_ticks_cannot_restore_policy(self):
        from test_adaptive_paper_native import FakePort
        from native_adapter import build_node
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "ledger.sqlite3", RiskLimits())
            self.addCleanup(ledger.close)
            ledger.start_trial(time.time())
            controller = runner.Controller(ledger, time.time() + 3600, market_open=True)
            policy = AdaptivePolicy(PolicyConfig(symbols=("SPY",), benchmarks=("SPY",), max_positions=1))
            strategy = AdaptiveStrategy(policy, ledger, "queued", stop_file=Path(directory) / "STOP")
            class Port(FakePort):
                def set_quote_quarantine_handler(self, handler, *, validate):
                    self.invalidate = handler
            port = Port()
            controller.port = port
            session = build_node(port, [{"symbol": "SPY"}], [strategy])
            runner.install_quote_quarantine(controller, strategy, session)

            async def exercise():
                task = asyncio.create_task(session.run_async())
                try:
                    for _ in range(200):
                        if strategy.started and "SPY" in policy.latest:
                            break
                        await asyncio.sleep(.005)
                    self.assertTrue(strategy.started)
                    self.assertIn("SPY", policy.latest)
                    old = session.quotes["SPY"]
                    ns = time.time_ns()
                    row = {"symbol": "SPY", "bid": "100", "ask": "100.01", "bid_size": "100", "ask_size": "100", "ts_ns": ns}
                    controller.quote(row)
                    session.on_quote(row)  # enqueues a REAL native-engine tick
                    session.data._handle_data(old)  # an older in-flight tick
                    before = strategy.received_quotes
                    self.assertFalse(port.invalidate("SPY", ns))  # equal to queued tick
                    await asyncio.sleep(.05)  # native engine consumes both queued ticks
                    self.assertNotIn("SPY", policy.latest)
                    self.assertEqual(strategy.received_quotes, before)
                    row["ts_ns"] = ns + 1  # float seconds may be identical
                    controller.quote(row)
                    session.on_quote(row)
                    await asyncio.sleep(.05)
                    self.assertIn("SPY", policy.latest)
                    self.assertEqual(policy.quote_ns["SPY"], ns + 1)
                    self.assertEqual(strategy.received_quotes, before + 1)
                    self.assertEqual(port.submissions, [])
                    self.assertEqual(session.errors, [])
                finally:
                    session.stop()
                    await asyncio.wait_for(task, 3)
            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
