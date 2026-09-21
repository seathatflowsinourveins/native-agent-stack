"""Local synthetic transport failure tests; no credentials or broker requests."""
import asyncio
import importlib.util
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch, Mock, AsyncMock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "adaptive_paper_transport", ROOT / "blueprints/us-equities/adaptive-paper/transport.py")
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)
try:
    import alpaca
    import requests
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

ID = "00000000-0000-0000-0000-000000000001"


def intent(**changes):
    value = {"client_order_id": "trial-1", "symbol": "SPY", "side": "buy",
             "qty": "1", "limit_price": "100.01"}
    value.update(changes)
    return value


def order(**changes):
    value = dict(intent(), id=ID, filled_qty="0", filled_avg_price=None,
                 status="new", updated_at="2026-09-21T15:00:00.000000001Z")
    value.update(changes)
    return value


def response(payload=None, status=200, headers=None):
    value = requests.Response()
    value.status_code = status
    value._content = json.dumps(payload).encode() if payload is not None else b""
    value.headers.update(headers or {})
    return value


class FakeStream:
    def __init__(self, *args, **kwargs):
        self._loop = None
        self._should_run = True
        self.channel = "orders" if "paper" in kwargs else "quotes"

    def subscribe_trade_updates(self, handler):
        self.handler = handler

    def subscribe_quotes(self, handler, *symbols):
        self.handler = handler

    def run(self):
        async def main():
            self._loop = asyncio.get_running_loop()
            self.owner._authorized(self.channel)
            self.owner._ack(self.channel, True)
            while self._should_run:
                if self.channel == "quotes":
                    await self.handler({"S": "SPY", "bp": 100, "ap": 100.01, "bs": 100,
                                        "as": 100, "t": t.datetime.now(t.timezone.utc)})
                await asyncio.sleep(0.02)
        asyncio.run(main())

    async def stop_ws(self):
        self._should_run = False

    async def close(self):
        self.owner._connection(self.channel, False)


class Normalization(unittest.TestCase):
    def test_fractional_exit_is_preserved_but_entry_rejected(self):
        self.assertEqual(t.normalize_intent(intent(side="sell", qty="0.123456789"), ["SPY"])["qty"], "0.123456789")
        with self.assertRaises(t.TransportError):
            t.normalize_intent(intent(qty="0.1"), ["SPY"])

    def test_nonfinite_and_advanced_orders_rejected(self):
        for changes in ({"qty": "NaN"}, {"limit_price": "Infinity"}, {"qty": "0"},
                        {"extended_hours": True}, {"advanced_instructions": {"algorithm": "TWAP"}},
                        {"time_in_force": "gtc"}, {"type": "market"}):
            with self.subTest(changes=changes), self.assertRaises(t.TransportError):
                t.normalize_intent(intent(**changes), ["SPY"])

    def test_timestamp_preserves_nanoseconds(self):
        ns = t.timestamp_ns("2026-09-21T15:00:00.123456789Z")
        self.assertEqual(ns % 1_000_000_000, 123456789)
        with self.assertRaises(t.TransportError):
            t.timestamp_ns("2026-09-21T15:00:00")

    def test_cumulative_fill_cannot_exceed_order(self):
        with self.assertRaises(t.TransportError):
            t.normalize_order(order(filled_qty="2"))


@unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")
class HTTPBoundary(unittest.TestCase):
    def setUp(self):
        self.budget = Mock()
        self.observer = Mock()
        self.session = t.GuardedSession(origin=t.PAPER_URL, before_request=self.budget, observer=self.observer)
        self.addCleanup(self.session.close)

    def test_restricts_origin_method_path_and_redirects(self):
        for method, url in [("POST", "https://api.alpaca.markets/v2/orders"),
                            ("DELETE", t.PAPER_URL + "/v2/orders"),
                            ("DELETE", t.PAPER_URL + "/v2/positions/SPY"),
                            ("PATCH", t.PAPER_URL + "/v2/orders/" + ID),
                            ("GET", t.PAPER_URL + "/v2/account?x=1"),
                            ("GET", t.PAPER_URL + "/v2/assets/../account")]:
            with self.subTest(method=method, url=url), self.assertRaises(t.TransportError):
                self.session.request(method, url)
        self.budget.assert_not_called()
        with patch.object(self.session._session, "request", return_value=response({}, 302)):
            with self.assertRaisesRegex(t.TransportError, "redirect"):
                self.session.request("GET", t.PAPER_URL + "/v2/account")

    def test_every_attempt_budgeted_timeouts_and_headers_sanitized(self):
        raw = response({}, headers={"X-Ratelimit-Limit": "200", "Authorization": "fixture-secret"})
        with patch.object(self.session._session, "request", return_value=raw) as request:
            self.session.request("POST", t.PAPER_URL + "/v2/orders", json=intent())
            self.session.request("DELETE", t.PAPER_URL + "/v2/orders/" + ID)
            self.session.request("GET", t.PAPER_URL + "/v2/account")
        self.assertEqual(self.budget.call_args_list[0].kwargs, {"client_id": "trial-1"})
        self.assertEqual([c.args[0] for c in self.budget.call_args_list], ["submit", "cancel", "read"])
        self.assertFalse(self.session._session.trust_env)
        for call in request.call_args_list:
            self.assertEqual(call.kwargs["timeout"], (5, 5))
            self.assertFalse(call.kwargs["allow_redirects"])
        self.assertEqual(self.observer.call_args.args[0]["headers"], {"x-ratelimit-limit": "200"})

    def test_sdk_zero_retry_applied_after_constructor(self):
        client = t._sdk_client("fixture-key", "fixture-secret", self.budget)
        self.addCleanup(client._session.close)
        self.assertEqual(client._retry, 0)
        with patch.object(client._session._session, "request", return_value=response({"code": 429, "message": "limited"}, 429)) as request:
            with self.assertRaises(Exception):
                client.get_account()
        self.assertEqual(request.call_count, 1)

    def test_preflight_is_read_only_and_hashes_identity(self):
        payloads = {"/v2/account": {"id": "fixture-account-id", "cash": "1000", "equity": "1000", "buying_power": "1000"},
                    "/v2/clock": {"is_open": True, "timestamp": "2026-09-21T15:00:00Z", "next_close": "2026-09-21T20:00:00Z", "next_open": "2026-09-22T13:30:00Z"},
                    "/v2/positions": [], "/v2/orders": [],
                    "/v2/assets/SPY": {"symbol": "SPY", "tradable": True, "fractionable": True},
                    "/v2/stocks/quotes/latest": {"quotes": {"SPY": {"bp": 100, "ap": 100.01, "bs": 1, "as": 1, "t": "2026-09-21T15:00:00Z"}}}}
        def request(method, url, **kwargs):
            self.assertEqual(method, "GET")
            return response(payloads[t.urlsplit(url).path])
        with patch("requests.Session.request", side_effect=request):
            result = t.preflight("fixture-key", "fixture-secret", ["SPY"], before_request=self.budget)
        self.assertEqual(len(result["account_identity_sha256"]), 64)
        self.assertNotIn("fixture-account-id", json.dumps(result))
        self.assertTrue(result["open_orders_complete"])
        self.assertEqual(result["orders"], [])
        self.assertEqual([c.args[0] for c in self.budget.call_args_list], ["read"] * 5 + ["data_read"])


@unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")
class AsyncTransport(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.budgets, self.observations, self.intents = [], [], []
        def budget(kind, client_id=None):
            self.budgets.append((kind, client_id, threading.get_ident()))
        self.port = t.AlpacaPaperTransport("fixture-key", "fixture-secret", ["SPY"],
                    before_request=budget, before_submit=self.intents.append,
                    sink_observation=self.observations.append)
        self.port._loop = asyncio.get_running_loop()
        self.port._started = True
        for channel in ("quotes", "orders"):
            self.port._authorized(channel)
            self.port._ack(channel, True)
        self.port._quote_seen["SPY"] = time.monotonic()
        self.port._quote_values["SPY"] = {"ts_ns": time.time_ns()}

    async def asyncTearDown(self):
        await self.port.stop()

    async def test_metadata_journaled_not_sent_and_replay_has_one_post(self):
        calls = []
        def request(method, url, **kwargs):
            calls.append((method, kwargs))
            return response(order())
        payload = intent(tags=["strategy=fixture"], strategy="fixture", reason="entry", extended_hours=False)
        with patch.object(self.port._client._session._session, "request", side_effect=request):
            await self.port.submit(payload)
            await self.port.submit(payload)
        self.assertEqual([m for m, _ in calls], ["POST", "GET"])
        self.assertEqual(self.intents[0]["strategy"], "fixture")
        self.assertNotIn("tags", calls[0][1]["json"])
        self.assertNotIn("strategy", calls[0][1]["json"])
        self.assertEqual(self.budgets[0][:2], ("submit", "trial-1"))
        self.assertTrue(all(row[2] == threading.get_ident() for row in self.budgets))

    async def test_ambiguous_post_resolves_by_id_without_retry_and_stays_frozen(self):
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[requests.Timeout(), response(order())]) as request:
            result = await self.port.submit(intent())
        self.assertEqual(result["client_order_id"], "trial-1")
        self.assertEqual([c.args[0] for c in request.call_args_list], ["POST", "GET"])
        self.assertIn("submission_ambiguous", self.port.health["reasons"])

    async def test_ambiguous_post_then_404_does_not_resubmit(self):
        missing = response({"code": 404, "message": "not found"}, 404)
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[requests.Timeout(), missing, missing]) as request:
            with self.assertRaises(t.AmbiguousSubmission):
                await self.port.submit(intent())
            with self.assertRaises(t.AmbiguousSubmission):
                await self.port.submit(intent())
        self.assertEqual([c.args[0] for c in request.call_args_list], ["POST", "GET", "GET"])

    async def test_403_rejection_requires_absence_lookup_and_never_retries(self):
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[response({"code": 403, "message": "rejected"}, 403),
                                       response({"code": 404, "message": "not found"}, 404)]) as request:
            with self.assertRaises(t.RejectedSubmission) as caught:
                await self.port.submit(intent())
        self.assertTrue(caught.exception.definitive_rejection)
        self.assertEqual([c.args[0] for c in request.call_args_list], ["POST", "GET"])

    async def test_422_duplicate_resolves_existing_order_or_stays_ambiguous(self):
        with patch.object(self.port._client._session._session, "request", side_effect=[
                response({"code": 42210000, "message": "duplicate client ID"}, 422), response(order())]) as request:
            found = await self.port.submit(intent())
        self.assertEqual(found["id"], ID)
        self.assertEqual([c.args[0] for c in request.call_args_list], ["POST", "GET"])
        self.port._reasons.clear()
        with patch.object(self.port._client._session._session, "request", side_effect=[
                response({"code": 42210000, "message": "duplicate client ID"}, 422),
                response({"code": 404, "message": "not found"}, 404)]):
            with self.assertRaises(t.AmbiguousSubmission):
                await self.port.submit(intent(client_order_id="trial-2"))
        self.assertTrue(self.port.health["frozen"])

    async def test_delayed_budget_rechecks_quote_before_wire(self):
        def budget(kind, client_id=None):
            self.port._quote_values["SPY"]["ts_ns"] = time.time_ns() - 60_000_000_000
        self.port.before_request = budget
        with patch.object(self.port._client._session._session, "request") as request:
            with self.assertRaises(t.SubmissionNotSent):
                await self.port.submit(intent())
        request.assert_not_called()

    async def test_replayed_id_cannot_change_intent(self):
        self.port.adopt_intents([intent()])
        with patch.object(self.port._client._session._session, "request") as request:
            with self.assertRaisesRegex(t.TransportError, "changed"):
                await self.port.submit(intent(qty="2"))
        request.assert_not_called()

    async def test_cancel_ack_is_not_terminal_and_every_attempt_counted(self):
        self.port.adopt_intents([intent()])
        partial = order(filled_qty="0.25", filled_avg_price="100.01", status="partially_filled")
        final = order(filled_qty="1", filled_avg_price="100.01", status="filled")
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[response(partial), response(None, 204), response(final)]) as request:
            result = await self.port.cancel("trial-1")
        self.assertEqual(result["status"], "filled")
        self.assertEqual([c.args[0] for c in request.call_args_list], ["GET", "DELETE", "GET"])
        self.assertEqual([c[0] for c in self.budgets], ["read", "cancel", "read"])

    async def test_known_partial_then_invisible_order_still_cancels_known_id(self):
        self.port.adopt_intents([intent()])
        await self.port._observe(t.normalize_order(order(filled_qty="0.25", status="partially_filled")))
        missing = response({"code": 404, "message": "not found"}, 404)
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[missing, response(None, 204), missing]) as request:
            result = await self.port.cancel("trial-1")
        self.assertIsNone(result)
        self.assertEqual([c.args[0] for c in request.call_args_list], ["GET", "DELETE", "GET"])
        self.assertIn("cancel_finality_unobserved", self.port.health["reasons"])

    async def test_proven_not_sent_intent_does_not_break_flat_snapshot(self):
        self.port.adopt_intents([intent()])
        self.port._not_sent.add("trial-1")
        values = [response({"cash": "1000", "equity": "1000", "buying_power": "1000"}),
                  response([]), response([]), response([])]
        with patch.object(self.port._client._session._session, "request", side_effect=values) as request:
            snapshot = await self.port.snapshot()
        self.assertTrue(snapshot["complete"])
        self.assertEqual(snapshot["positions"], [])
        self.assertEqual(request.call_count, 4)

    async def test_late_event_cannot_undo_cumulative_fill(self):
        final = t.normalize_order(order(filled_qty="1", filled_avg_price="100", status="filled"))
        await self.port._observe(final)
        observed = await self.port._observe(t.normalize_order(order(filled_qty="0.25", status="partially_filled")))
        self.assertEqual(observed["filled_qty"], "1")
        self.assertEqual(len(self.observations), 1)

    async def test_disconnect_requires_explicit_reconciliation(self):
        self.assertTrue(self.port.ready)
        self.port._connection("orders", False)
        self.port._authorized("orders")
        self.port._ack("orders", True)
        self.assertFalse(self.port.ready)
        self.port.mark_reconciled()
        self.assertTrue(self.port.ready)

    async def test_subscription_ack_not_running_flag_controls_ready(self):
        self.port._acks["orders"] = False
        self.port._orders_stream._running = True
        self.assertFalse(self.port.ready)
        self.port._ack("orders", True)
        self.assertTrue(self.port.ready)

    async def test_queue_overflow_cannot_be_silently_thawed(self):
        self.port._events = t.queue.Queue(maxsize=1)
        self.port._enqueue("quote", {})
        self.port._enqueue("quote", {})
        self.port._events.get_nowait()
        self.assertIn("queue_overflow", self.port.health["reasons"])
        with self.assertRaises(t.TransportError):
            self.port.mark_reconciled()

    async def test_missing_order_update_freezes(self):
        self.port._pending_stream["trial-1"] = time.monotonic() - 20
        task = asyncio.create_task(self.port._watchdog())
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertIn("order_update_missing", self.port.health["reasons"])

    async def test_startup_staggered_quotes_do_not_freeze_before_first_ready(self):
        self.port.symbols = ("SPY", "QQQ")
        self.port.required_quote_symbols = self.port.symbols
        self.port._ever_ready = False
        task = asyncio.create_task(self.port._watchdog())
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertNotIn("quote_stale", self.port.health["reasons"])

    async def test_quiet_unrequired_symbol_does_not_halt_benchmark_readiness(self):
        self.port.symbols = ("SPY", "QQQ")
        self.port.required_quote_symbols = ("SPY",)
        self.port._quote_seen["QQQ"] = time.monotonic() - 60
        self.port._ever_ready = True
        task = asyncio.create_task(self.port._watchdog())
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertTrue(self.port.ready)
        self.assertNotIn("quote_stale", self.port.health["reasons"])

    async def test_required_benchmark_stale_blocks_entry(self):
        self.port.required_quote_symbols = ("SPY",)
        self.port._quote_seen["SPY"] = time.monotonic() - 60
        self.assertFalse(self.port.ready)
        with patch.object(self.port._client._session._session, "request") as request:
            with self.assertRaisesRegex(t.TransportError, "not ready"):
                await self.port.submit(intent())
        request.assert_not_called()

    async def test_snapshot_paginates_and_rejects_nonadvancing_page(self):
        page = [order(id=f"00000000-0000-0000-0000-{i:012d}", client_order_id=f"fixture-{i}") for i in range(500)]
        with patch.object(self.port._client, "get", side_effect=[page, [order(id="00000000-0000-0000-0000-000000000500")]]) as get:
            result = self.port._pages("all", after=self.port.history_start)
        self.assertEqual(len(result), 501)
        self.assertEqual(get.call_count, 2)
        with patch.object(self.port._client, "get", side_effect=[page, page]):
            with self.assertRaisesRegex(t.TransportError, "advance"):
                self.port._pages("open")

    async def test_snapshot_bound_is_failure_not_partial_success(self):
        self.port.max_snapshot_pages = 1
        page = [order(id=str(i), client_order_id=f"fixture-{i}") for i in range(500)]
        with patch.object(self.port._client, "get", return_value=page):
            with self.assertRaisesRegex(t.TransportError, "completeness"):
                self.port._pages("open")

    async def test_native_stream_threads_start_and_join(self):
        await self.port.stop()
        with patch.object(t, "_stream_classes", return_value=(FakeStream, FakeStream)):
            self.port = t.AlpacaPaperTransport("fixture-key", "fixture-secret", ["SPY"],
                    before_request=lambda *a, **k: None, before_submit=lambda x: None,
                    sink_observation=lambda x: None, start_timeout=1)
        quotes = []
        await self.port.start(quotes.append, lambda order: None)
        self.assertTrue(self.port.ready)
        self.assertTrue(quotes)
        await self.port.stop()
        self.assertTrue(all(not thread.is_alive() for thread in self.port._threads))
        self.assertTrue(all(not thread.daemon for thread in self.port._threads))

    async def test_reviewed_native_dispatch_observes_control_ack(self):
        self.port._acks["orders"] = False
        await self.port._orders_stream._dispatch({"stream": "listening", "data": {"streams": ["trade_updates"]}})
        self.assertTrue(self.port._acks["orders"])
        await self.port._quotes_stream._dispatch({"T": "subscription", "quotes": []})
        self.assertIn("quotes_subscription_rejected", self.port.health["reasons"])

    async def test_websocket_redirect_rejected_before_sdk_authentication(self):
        from websockets.legacy.client import WebSocketClientProtocol
        from websockets.exceptions import RedirectHandshake
        from websockets.uri import parse_uri
        protocol = t._protocol_factory(t.PAPER_WS)()
        with patch.object(WebSocketClientProtocol, "handshake", new=AsyncMock(side_effect=RedirectHandshake("wss://example.org/stream"))):
            with self.assertRaisesRegex(t.TransportError, "redirect rejected"):
                await protocol.handshake(parse_uri(t.PAPER_WS))
        with patch.object(WebSocketClientProtocol, "handshake", new=AsyncMock()) as upstream:
            with self.assertRaisesRegex(t.TransportError, "endpoint rejected"):
                await protocol.handshake(parse_uri("wss://example.org/stream"))
            upstream.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
