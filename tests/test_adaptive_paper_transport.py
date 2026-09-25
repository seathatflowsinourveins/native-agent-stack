"""Local synthetic transport failure tests; no credentials or broker requests."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch, Mock, AsyncMock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
SPEC = importlib.util.spec_from_file_location("adaptive_paper_transport", SOURCE / "transport.py")
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)
try:
    import alpaca
    import requests
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

ID = str(__import__("uuid").UUID(int=1))


def intent(**changes):
    value = {"client_order_id": "trial-1", "symbol": "SPY", "side": "buy",
             "qty": "1", "limit_price": "100.01"}
    value.update(changes)
    return value


def wire(**changes):
    """A POST body shaped as alpaca-py 0.44.0 serializes intent() (floats for decimals)."""
    value = {"symbol": "SPY", "qty": 1.0, "side": "buy", "type": "limit", "time_in_force": "day",
             "extended_hours": False, "client_order_id": "trial-1", "limit_price": 100.01}
    value.update(changes)
    return value


def allow_sub_penny(port):
    """Test mirror of native-faults FaultTransport: a sub-penny limit price passes the
    order-contract boundary (on-cent validation, exact wire price) so these tests can
    reach the transport's own 422 classification. Every other rule still applies."""
    original = port._validated_request

    def validated(intent):
        price = t.Decimal(intent["limit_price"])
        if not t.violates_minimum_price_variance(price):
            return original(intent)
        on_cent = dict(intent, limit_price=str(price.quantize(t.Decimal("0.01"), "ROUND_DOWN")))
        envelope = t.order_envelope(on_cent, extended_hours_allowed=port.extended_hours_allowed)
        envelope["intent"]["limit_price"] = intent["limit_price"]
        return envelope, t.limit_order_request(envelope)
    port._validated_request = validated


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
        self._handlers = {"quotes": {}, "statuses": {}, "lulds": {}}

    def subscribe_trade_updates(self, handler):
        self.handler = handler

    def subscribe_quotes(self, handler, *symbols):
        self.handler = handler
        self._subscribe(handler, symbols, self._handlers["quotes"])

    def subscribe_trading_statuses(self, handler, *symbols):
        self._subscribe(handler, symbols, self._handlers["statuses"])

    def _subscribe(self, handler, symbols, handlers):
        for symbol in symbols:
            handlers[symbol] = handler

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

    def test_wire_decimals_are_exact_fixed_point_for_risk_parser(self):
        self.assertEqual(t.decimal_string("1E-9"), "0.000000001")
        self.assertEqual(t.decimal_string("0.000000000"), "0")
        self.assertEqual(t.decimal_string("100.010000000"), "100.01")
        with self.assertRaises(t.TransportError):
            t.decimal_string("1E1000000")

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

    def test_crossed_and_one_sided_quotes_are_untradable_not_corrupt(self):
        base = {"S": "SPY", "bp": "100.01", "ap": "100.02", "bs": 1, "as": 1, "t": "2026-09-23T15:00:00.000000001Z"}
        self.assertEqual(t.normalize_quote(base)["bid"], "100.01")
        self.assertEqual(t.normalize_quote({**base, "bp": "100.02"})["ask"], "100.02")  # locked is tradable
        for changes, reason in (({"bp": "336.23", "ap": "336.21"}, "crossed"), ({"bp": 0}, "one_sided"),
                                ({"ap": "0.00"}, "one_sided")):
            with self.subTest(changes=changes), self.assertRaises(t.InvalidQuote) as caught:
                t.normalize_quote({**base, **changes})
            self.assertEqual(caught.exception.reason, reason)
        # Malformed data, or an untradable quote that is also malformed or halt-flagged, fails closed.
        for changes in ({"bp": "-1"}, {"t": None}, {"bs": -1}, {"ap": "NaN"}, {"bp": 0, "t": None},
                        {"bp": 0, "bs": -1}, {"bp": "101", "c": ["H"]}, {"ap": 0, "halted": True},
                        {"S": None}):
            with self.subTest(changes=changes), self.assertRaises(t.TransportError) as caught:
                t.normalize_quote({**base, **changes})
            self.assertNotIsInstance(caught.exception, t.InvalidQuote)

    def test_cumulative_fill_cannot_exceed_order(self):
        with self.assertRaises(t.TransportError):
            t.normalize_order(order(filled_qty="2"))


class OrderContractBoundary(unittest.TestCase):
    """SDK-free checks of the pre-submission order-contract boundary."""

    def test_envelope_validates_the_sdk_bound_projection_only(self):
        normalized = t.normalize_intent(intent(tags=["a"], strategy="s", reason="r"), ["SPY"])
        envelope = t.order_envelope(normalized)
        self.assertEqual((envelope["mode"], envelope["submission_enabled"]), ("offline", False))
        self.assertEqual(envelope["intent"], {"symbol": "SPY", "qty": "1", "side": "buy", "type": "limit",
                                              "time_in_force": "day", "client_order_id": "trial-1",
                                              "order_class": "simple", "extended_hours": False,
                                              "limit_price": "100.01"})

    def test_engine_semantics_kept_fractional_sell_and_allowed_extended_hours(self):
        exit_ = t.normalize_intent(intent(side="sell", qty="0.123456789"), ["SPY"])
        self.assertEqual(t.order_envelope(exit_)["intent"]["qty"], "0.123456789")
        extended = t.normalize_intent(intent(extended_hours=True), ["SPY"], allow_extended_hours=True)
        self.assertIs(t.order_envelope(extended, extended_hours_allowed=True)["intent"]["extended_hours"], True)
        with self.assertRaises(t.OrderContractRefused):
            t.order_envelope(extended)

    def test_contract_refusals_are_local_not_broker_refusals(self):
        # Each passes normalize_intent (and, except the price, the ledger) but not the contract.
        for changes, symbols in (({"client_order_id": "_leading"}, ["SPY"]),
                                 ({"client_order_id": "-leading"}, ["SPY"]),
                                 ({"symbol": "BRK-B"}, ["BRK-B"]),
                                 ({"limit_price": "100.001"}, ["SPY"]),
                                 ({"limit_price": "0.12345"}, ["SPY"])):
            with self.subTest(changes=changes):
                normalized = t.normalize_intent(intent(**changes), symbols)
                with self.assertRaises(t.OrderContractRefused) as caught:
                    t.order_envelope(normalized)
                error = caught.exception
                self.assertIsInstance(error, t.SubmissionNotSent)
                self.assertNotIsInstance(error, t.RejectedSubmission)
                self.assertTrue(error.not_sent and error.definitive_rejection)
                self.assertEqual((error.local_refusal, error.not_sent_reason),
                                 ("order_contract", "order_contract_refused"))
                self.assertFalse(hasattr(error, "status_code"))

    def test_wire_gate_requires_the_exact_validated_body(self):
        envelope = t.order_envelope(t.normalize_intent(intent(), ["SPY"]))
        envelopes = {"trial-1": envelope}
        self.assertIs(t.check_wire_submission(envelopes, wire()), envelope)
        self.assertIs(t.check_wire_submission(envelopes, wire(order_class="simple")), envelope)
        for label, found, body in (
                ("unregistered", {}, wire()),
                ("other-id", envelopes, wire(client_order_id="trial-2")),
                ("dropped-field", envelopes, {k: v for k, v in wire().items() if k != "extended_hours"}),
                ("added-field", envelopes, wire(advanced_instructions={"algorithm": "TWAP"})),
                ("changed-price", envelopes, wire(limit_price=100.0)),
                ("changed-qty", envelopes, wire(qty=2.0)),
                ("changed-side", envelopes, wire(side="sell")),
                ("bool-qty", envelopes, wire(qty=True)),
                ("non-dict", envelopes, None)):
            with self.subTest(label=label), self.assertRaises(t.OrderContractRefused):
                t.check_wire_submission(found, body)

    def test_float_that_loses_the_exact_decimal_is_refused(self):
        exit_ = t.normalize_intent(intent(side="sell", qty="12345678.123456789"), ["SPY"])
        envelope = t.order_envelope(exit_)
        self.assertFalse(t.wire_matches_envelope(wire(side="sell", qty=float("12345678.123456789")), envelope))

    def test_boundary_status_is_active_and_fails_closed(self):
        status = t.order_contract_status(["SPY", "BRK.B"])
        self.assertTrue(status["active"])
        self.assertEqual(status["symbols_checked"], 2)
        self.assertEqual(status["contract_sha256"],
                         __import__("hashlib").sha256(t.ORDER_CONTRACT_PATH.read_bytes()).hexdigest())
        with self.assertRaisesRegex(t.TransportError, "configured_symbol_outside_contract"):
            t.order_contract_status(["SPY", "BRK-B"])

        class Permissive:  # a contract that accepts anything is not an active boundary
            __file__ = str(t.ORDER_CONTRACT_PATH)
            ContractError = ValueError

            @staticmethod
            def build_envelope(value, **_):
                return {"intent": dict(value)}
        with patch.object(t, "order_contract", Permissive):
            with self.assertRaisesRegex(t.TransportError, "order_contract_boundary_inactive:invalid_sentinel"):
                t.order_contract_status()
        with patch.object(t, "order_contract", type("Missing", (), {"__file__": "/elsewhere.py"})):
            with self.assertRaisesRegex(t.TransportError, "contract_module_not_loaded"):
                t.order_contract_status()


@unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")
class HTTPBoundary(unittest.TestCase):
    def setUp(self):
        self.budget = Mock(return_value=None)
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
        self.session.expect_submission(t.order_envelope(intent()))
        with patch.object(self.session._session, "request", return_value=raw) as request:
            self.session.request("POST", t.PAPER_URL + "/v2/orders", json=wire())
            self.session.request("DELETE", t.PAPER_URL + "/v2/orders/" + ID)
            self.session.request("GET", t.PAPER_URL + "/v2/account")
        self.assertEqual(self.budget.call_args_list[0].kwargs, {"client_id": "trial-1"})
        self.assertEqual([c.args[0] for c in self.budget.call_args_list], ["submit", "cancel", "read"])
        self.assertFalse(self.session._session.trust_env)
        for call in request.call_args_list:
            self.assertEqual(call.kwargs["timeout"], (5, 5))
            self.assertFalse(call.kwargs["allow_redirects"])
        self.assertEqual(self.observer.call_args.args[0]["headers"], {"x-ratelimit-limit": "200"})

    def test_cancel_budget_names_only_the_announced_order(self):
        other = str(__import__("uuid").UUID(int=2))
        with patch.object(self.session._session, "request", return_value=response(None, 204)):
            self.session.request("DELETE", t.PAPER_URL + "/v2/orders/" + ID)
            self.session.cancel_expectation = (ID, "trial-1")
            self.session.request("DELETE", t.PAPER_URL + "/v2/orders/" + other)
            self.session.request("DELETE", t.PAPER_URL + "/v2/orders/" + ID.upper())
            self.session.request("GET", t.PAPER_URL + "/v2/orders/" + ID)
        self.assertEqual([(c.args, c.kwargs) for c in self.budget.call_args_list],
                         [(("cancel",), {}), (("cancel",), {}), (("cancel",), {"client_id": "trial-1"}),
                          (("read",), {})])

    def test_fill_activities_read_is_allowed_only_filtered_by_one_order(self):
        url = t.PAPER_URL + t.ACTIVITY_FILL_PATH
        token = "20260924150021320::" + str(__import__("uuid").uuid4())
        allowed = [{"order_id": ID}, {"order_id": ID, "direction": "asc", "page_size": 100},
                   {"order_id": ID, "direction": "asc", "page_size": 100, "page_token": token}]
        with patch.object(self.session._session, "request", return_value=response([])) as request:
            for params in allowed:
                self.session.request("GET", url, params=params)
        self.assertEqual(request.call_count, 3)
        self.assertEqual([c.args[0] for c in self.budget.call_args_list], ["read"] * 3)
        refused = [("GET", url, None), ("GET", url, {}), ("GET", url, {"order_id": "not-a-uuid"}),
                   ("GET", url, {"order_id": ID, "direction": "desc"}),
                   ("GET", url, {"order_id": ID, "page_size": 101}), ("GET", url, {"order_id": ID, "page_size": "100"}),
                   ("GET", url, {"order_id": ID, "page_token": "not::a-token"}),
                   ("GET", url, {"order_id": ID, "date": "2026-09-24"}),
                   ("GET", t.PAPER_URL + "/v2/account/activities", {"order_id": ID}),
                   ("GET", t.PAPER_URL + "/v2/account/activities/FEE", {"order_id": ID}),
                   ("POST", url, {"order_id": ID}), ("DELETE", url, {"order_id": ID})]
        self.budget.reset_mock()
        for method, target, params in refused:
            with self.subTest(method=method, url=target, params=params), self.assertRaises(t.TransportError):
                self.session.request(method, target, params=params)
        self.budget.assert_not_called()

    def test_sdk_zero_retry_applied_after_constructor(self):
        client = t._sdk_client("fixture-key", "fixture-secret", self.budget)
        self.addCleanup(client._session.close)
        self.assertEqual(client._retry, 0)
        with patch.object(client._session._session, "request", return_value=response({"code": 429, "message": "limited"}, 429)) as request:
            with self.assertRaises(Exception):
                client.get_account()
        self.assertEqual(request.call_count, 1)

    def test_positive_submission_delay_is_deferred_without_sending(self):
        self.budget.return_value = 60
        self.session.expect_submission(t.order_envelope(intent()))
        with patch.object(self.session._session, "request") as request:
            with self.assertRaises(t.SubmissionNotSent) as caught:
                self.session.request("POST", t.PAPER_URL + "/v2/orders", json=wire())
        self.assertNotIsInstance(caught.exception, t.OrderContractRefused)
        self.budget.assert_called_once()
        request.assert_not_called()

    def test_unvalidated_order_body_is_refused_before_budget_and_http(self):
        with patch.object(self.session._session, "request") as request:
            with self.assertRaises(t.OrderContractRefused):
                self.session.request("POST", t.PAPER_URL + "/v2/orders", json=wire())
            self.session.expect_submission(t.order_envelope(intent()))
            with self.assertRaises(t.OrderContractRefused):  # SDK-side field loss
                self.session.request("POST", t.PAPER_URL + "/v2/orders",
                                     json={k: v for k, v in wire().items() if k != "limit_price"})
            self.session.withdraw_submission("trial-1")
            with self.assertRaises(t.OrderContractRefused):  # admitted only for its own call
                self.session.request("POST", t.PAPER_URL + "/v2/orders", json=wire())
        self.budget.assert_not_called()
        self.observer.assert_not_called()
        request.assert_not_called()

    def test_sdk_serialization_of_an_envelope_passes_the_wire_gate(self):
        for changes in ({}, {"side": "sell", "qty": "0.123456789"}, {"limit_price": "0.1234"},
                        {"qty": "250", "limit_price": "999.99"}):
            with self.subTest(changes=changes):
                envelope = t.order_envelope(t.normalize_intent(intent(**changes), ["SPY"]))
                body = t.limit_order_request(envelope).to_request_fields()
                self.assertTrue(t.wire_matches_envelope(body, envelope))

    def test_preflight_is_read_only_and_hashes_identity(self):
        payloads = {"/v2/account": {"id": "fixture-account-id", "cash": "1000", "equity": "1000", "buying_power": "1000"},
                    "/v2/clock": {"is_open": True, "timestamp": "2026-09-21T15:00:00Z", "next_close": "2026-09-21T20:00:00Z", "next_open": "2026-09-22T13:30:00Z"},
                    "/v2/positions": [], "/v2/orders": [],
                    "/v2/assets/SPY": {"symbol": "SPY", "tradable": True, "fractionable": True},
                    "/v2/stocks/quotes/latest": {"quotes": {"SPY": {"bp": 100, "ap": 100.01, "bs": 1, "as": 1, "t": "2026-09-21T15:00:00Z"}}}}
        def request(method, url, **kwargs):
            self.assertEqual(method, "GET")
            return response(payloads[t.urlsplit(url).path])
        received_at_ns = t.timestamp_ns("2026-09-21T15:00:00.123456789Z")
        with patch("requests.Session.request", side_effect=request), patch.object(t.time, "time_ns", return_value=received_at_ns):
            result = t.preflight("fixture-key", "fixture-secret", ["SPY"], before_request=self.budget)
        self.assertEqual(len(result["account_identity_sha256"]), 64)
        self.assertNotIn("fixture-account-id", json.dumps(result))
        self.assertTrue(result["open_orders_complete"])
        self.assertEqual(result["orders"], [])
        self.assertEqual(result["clock"]["received_at_ns"], received_at_ns)
        self.assertEqual([c.args[0] for c in self.budget.call_args_list], ["read"] * 5 + ["data_read"])

    def _preflight_clients(self):
        trading, data = Mock(), Mock()
        trading.get_account.return_value = {"id": "fixture-account", "cash": "1000",
                                            "equity": "1000", "buying_power": "1000"}
        trading.get_clock.return_value = {"is_open": True, "timestamp": "2026-09-21T15:00:00Z",
                                          "next_close": "2026-09-21T20:00:00Z",
                                          "next_open": "2026-09-22T13:30:00Z"}
        trading.get_all_positions.return_value = []
        trading.get.return_value = []
        trading.get_asset.side_effect = lambda symbol: {"symbol": symbol, "tradable": True}
        data.get_stock_latest_quote.return_value = {}
        return trading, data

    def test_preflight_sends_the_configured_feed_on_the_quote_request(self):
        from alpaca.data.enums import DataFeed
        for keywords, expected in (({"feed": "sip"}, DataFeed.SIP), ({"feed": "iex"}, DataFeed.IEX),
                                   ({}, DataFeed.IEX)):
            with self.subTest(**keywords):
                trading, data = self._preflight_clients()
                with patch.object(t, "_sdk_client", side_effect=[trading, data]):
                    t.preflight("fixture-key", "fixture-secret", ["SPY"],
                                before_request=self.budget, **keywords)
                request = data.get_stock_latest_quote.call_args.args[0]
                self.assertEqual(request.feed, expected)
                self.assertEqual(request.feed.value, keywords.get("feed", "iex"))

    def test_preflight_refuses_an_unqualified_feed_before_any_request(self):
        for value in ("otc", "delayed_sip", "IEX", "", None):
            with self.subTest(feed=value):
                with patch.object(t, "_sdk_client") as client:
                    with self.assertRaises(t.UnsupportedDataFeed) as caught:
                        t.preflight("fixture-key", "fixture-secret", ["SPY"], feed=value,
                                    before_request=self.budget)
                self.assertEqual(str(caught.exception), "unqualified_data_feed")
                client.assert_not_called()
                self.budget.assert_not_called()

    def test_closed_preflight_preserves_clock_with_invalid_and_missing_quotes(self):
        trading, data = Mock(), Mock()
        trading.get_account.return_value = {"id": "fixture-account", "cash": "1000", "equity": "1000", "buying_power": "1000"}
        trading.get_clock.return_value = {"is_open": False, "timestamp": "2026-09-21T21:00:00Z",
                                         "next_close": "2026-09-22T20:00:00Z", "next_open": "2026-09-22T13:30:00Z"}
        trading.get_all_positions.return_value = []
        trading.get.return_value = []
        trading.get_asset.side_effect = lambda symbol: {"symbol": symbol, "tradable": True}
        data.get_stock_latest_quote.return_value = {"SPY": {"bp": 0, "ap": 0, "t": "2026-09-21T21:00:00Z"}}
        with patch.object(t, "_sdk_client", side_effect=[trading, data]):
            result = t.preflight("fixture-key", "fixture-secret", ["SPY", "QQQ"], before_request=self.budget)
        self.assertFalse(result["clock"]["is_open"])
        self.assertEqual(result["quotes"], [])
        self.assertEqual(result["quote_errors"], {"QQQ": "missing_quote", "SPY": "invalid_quote"})
        self.assertEqual(result["positions"], [])
        self.assertEqual(len(result["assets"]), 2)


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

    async def test_wire_future_quote_tolerance_matches_risk_layer(self):
        now = time.time_ns()
        with patch.object(t.time, "time_ns", return_value=now):
            self.port._quote_values["SPY"]["ts_ns"] = now + 250_000_000
            self.port._wire_guard(intent())
            self.port._quote_values["SPY"]["ts_ns"] = now + 251_000_000
            with self.assertRaises(t.SubmissionNotSent):
                self.port._wire_guard(intent())

    async def test_sleeping_submit_budget_cannot_starve_owned_cancel(self):
        blocked = asyncio.Event()
        canceled_hook = asyncio.Event()
        calls = []
        async def budget(kind, client_id=None):
            if kind == "submit":
                try:
                    await blocked.wait()
                finally:
                    canceled_hook.set()
            else:
                calls.append(kind)
        self.port.before_request = budget
        self.port.adopt_intents([intent(client_order_id="owned-prior")])
        initial = order(client_order_id="owned-prior")
        final = order(client_order_id="owned-prior", status="canceled")
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[response(initial), response(None, 204), response(final)]) as request:
            results = await asyncio.wait_for(asyncio.gather(
                self.port.submit(intent()), self.port.cancel("owned-prior"), return_exceptions=True), 2)
        self.assertIsInstance(results[0], t.SubmissionNotSent)
        self.assertEqual(results[1]["status"], "canceled")
        self.assertFalse(blocked.is_set())
        self.assertTrue(canceled_hook.is_set())
        self.assertEqual(calls, ["read", "cancel", "read"])
        self.assertEqual([c.args[0] for c in request.call_args_list], ["GET", "DELETE", "GET"])

    async def test_a_named_cancel_keeps_the_waiting_budget_path(self):
        # Naming the order must not move a cancel onto the submission path's 0.25 s,
        # never-wait deadline: a cancel whose budget waits still goes out.
        async def budget(kind, client_id=None):
            if kind == "cancel":
                await asyncio.sleep(0.4)
        self.port.before_request = budget
        self.port.adopt_intents([intent()])
        await self.port._observe(t.normalize_order(order()))
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[response(None, 204), response(order(status="canceled"))]) as request:
            result = await self.port.cancel("trial-1")
        self.assertEqual(result["status"], "canceled")
        self.assertEqual([c.args[0] for c in request.call_args_list], ["DELETE", "GET"])
        self.assertEqual(self.port.health["reasons"], [])

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
        # Only the DELETE's budget call names the owned order; the expectation does not outlive it.
        self.assertEqual([c[:2] for c in self.budgets], [("read", None), ("cancel", "trial-1"), ("read", None)])
        self.assertIsNone(self.port._client._session.cancel_expectation)

    async def test_known_partial_then_invisible_order_still_cancels_known_id(self):
        self.port.adopt_intents([intent()])
        await self.port._observe(t.normalize_order(order(filled_qty="0.25", status="partially_filled")))
        missing = response({"code": 404, "message": "not found"}, 404)
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[response(None, 204), missing]) as request:
            result = await self.port.cancel("trial-1")
        self.assertIsNone(result)
        # The known broker id is cancelled directly; no pre-DELETE lookup decides for the caller.
        self.assertEqual([c.args[0] for c in request.call_args_list], ["DELETE", "GET"])
        self.assertTrue(request.call_args_list[0].args[1].endswith("/v2/orders/" + ID))
        self.assertIn("cancel_finality_unobserved", self.port.health["reasons"])

    async def test_cancel_again_sends_delete_and_takes_422_as_data(self):
        # C05: the order is already canceled; the second cancel still reaches the
        # broker, whose documented 422 "not cancelable" is data, not a freeze.
        self.port.adopt_intents([intent()])
        canceled = order(status="canceled", updated_at="2026-09-21T15:00:01Z")
        await self.port._observe(t.normalize_order(canceled))
        observed = len(self.observations)
        with patch.object(self.port._client._session._session, "request", side_effect=[
                response({"code": 42210000, "message": "order is already in \"canceled\" state"}, 422),
                response(canceled)]) as request:
            result = await self.port.cancel("trial-1")
        self.assertEqual(result["status"], "canceled")
        self.assertEqual([c.args[0] for c in request.call_args_list], ["DELETE", "GET"])
        self.assertEqual([b[0] for b in self.budgets], ["cancel", "read"])
        self.assertEqual(self.port.health["reasons"], [])
        # The follow-up observation repeats the known terminal state exactly.
        self.assertTrue(all(o["status"] == "canceled" and o["filled_qty"] == "0"
                            for o in self.observations[observed:]))

    async def test_cancel_404_with_terminal_final_is_data(self):
        self.port.adopt_intents([intent()])
        await self.port._observe(t.normalize_order(order()))
        with patch.object(self.port._client._session._session, "request", side_effect=[
                response({"code": 40410000, "message": "order not found"}, 404),
                response(order(status="canceled", updated_at="2026-09-21T15:00:01Z"))]):
            result = await self.port.cancel("trial-1")
        self.assertEqual(result["status"], "canceled")
        self.assertEqual(self.port.health["reasons"], [])

    async def test_cancel_refusal_for_still_working_order_freezes(self):
        self.port.adopt_intents([intent()])
        await self.port._observe(t.normalize_order(order()))
        with patch.object(self.port._client._session._session, "request", side_effect=[
                response({"code": 42210000, "message": "not cancelable"}, 422),
                response(order(status="pending_cancel", updated_at="2026-09-21T15:00:01Z"))]):
            result = await self.port.cancel("trial-1")
        self.assertEqual(result["status"], "pending_cancel")
        self.assertIn("cancellation_unresolved", self.port.health["reasons"])

    async def test_cancel_server_error_stays_unresolved(self):
        self.port.adopt_intents([intent()])
        await self.port._observe(t.normalize_order(order()))
        with patch.object(self.port._client._session._session, "request", side_effect=[
                response({"code": 50010000, "message": "internal"}, 500),
                response(order(status="canceled", updated_at="2026-09-21T15:00:01Z"))]):
            await self.port.cancel("trial-1")
        self.assertIn("cancellation_unresolved", self.port.health["reasons"])
        self.assertIsNone(self.port._client._session.cancel_expectation)

    async def test_documented_sub_penny_422_is_definitive_once_absent(self):
        # C04: Alpaca documents this body for a price beyond the minimum price variance.
        body = {"code": 42210000,
                "message": "invalid limit_price 100.0101. sub-penny increment does not fulfill minimum pricing criteria"}
        missing = response({"code": 40410000, "message": "not found"}, 404)
        allow_sub_penny(self.port)
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[response(body, 422), missing]) as request:
            with self.assertRaises(t.RejectedSubmission) as caught:
                await self.port.submit(intent(limit_price="100.0101"))
            with self.assertRaises(t.RejectedSubmission) as replay:
                await self.port.submit(intent(limit_price="100.0101"))
        self.assertEqual((caught.exception.status_code, caught.exception.refusal), (422, t.SUB_PENNY_REFUSAL))
        self.assertEqual((replay.exception.status_code, replay.exception.refusal), (422, t.SUB_PENNY_REFUSAL))
        self.assertTrue(caught.exception.definitive_rejection)
        self.assertEqual([c.args[0] for c in request.call_args_list], ["POST", "GET"])  # no retry, no replay POST
        self.assertEqual(self.port.health["reasons"], [])
        self.assertNotIn("invalid limit_price", str(caught.exception))  # provider text never raised

    async def test_other_422_stays_ambiguous(self):
        missing = response({"code": 40410000, "message": "not found"}, 404)
        cases = [
            # The documented sub-penny body for a price that is on the increment contradicts itself.
            ("valid-price", "100.01", {"code": 42210000, "message":
                                       "sub-penny increment does not fulfill minimum pricing criteria"}),
            # A duplicate client id proves that an order exists.
            ("duplicate", "100.0101", {"code": 40010001, "message": "client_order_id must be unique"}),
            ("other-code", "100.0101", {"code": 40010001, "message":
                                        "sub-penny increment does not fulfill minimum pricing criteria"}),
            ("no-json", "100.0101", None),
        ]
        allow_sub_penny(self.port)
        for index, (label, price, body) in enumerate(cases):
            with self.subTest(label=label):
                self.port._reasons.clear()
                with patch.object(self.port._client._session._session, "request",
                                  side_effect=[response(body, 422), missing]):
                    with self.assertRaises(t.AmbiguousSubmission):
                        await self.port.submit(intent(client_order_id="amb-%d" % index, limit_price=price))
                self.assertIn("submission_ambiguous", self.port.health["reasons"])

    async def test_sub_penny_422_with_visible_order_is_not_a_refusal(self):
        body = {"code": 42210000, "message": "sub-penny increment does not fulfill minimum pricing criteria"}
        allow_sub_penny(self.port)
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[response(body, 422), response(order(limit_price="100.0101"))]):
            found = await self.port.submit(intent(limit_price="100.0101"))
        self.assertEqual(found["id"], ID)
        self.assertIn("submission_ambiguous", self.port.health["reasons"])

    def test_minimum_price_variance_matches_the_ledger(self):
        import safety
        self.assertEqual(t.SUB_PENNY_REFUSAL, safety.SUB_PENNY_REFUSAL)
        for price in ("1", "1.01", "0.9999", "0.5", "100.0101", "1.001", "0.99991", "307.6601"):
            self.assertEqual(t.violates_minimum_price_variance(price),
                             not safety.price_increment_valid(__import__("decimal").Decimal(price)), price)

    async def test_invalid_envelope_never_reaches_the_fake_broker(self):
        self.port.symbols = ("SPY", "BRK-B")  # both pass the transport's own symbol syntax
        self.port._quote_values["BRK-B"] = {"ts_ns": time.time_ns()}
        cases = [intent(client_order_id="_leading"), intent(client_order_id="bad-symbol", symbol="BRK-B"),
                 intent(client_order_id="sub-penny", limit_price="100.001")]
        with patch.object(self.port._client, "submit_order") as sdk_submit, \
                patch.object(self.port._client._session._session, "request") as broker:
            for payload in cases:
                with self.subTest(client_order_id=payload["client_order_id"]):
                    with self.assertRaises(t.OrderContractRefused) as caught:
                        await self.port.submit(payload)
                    self.assertNotIsInstance(caught.exception, t.RejectedSubmission)
                    self.assertIn(payload["client_order_id"], self.port._not_sent)
                    self.assertNotIn(payload["client_order_id"], self.port._rejected)
                    # A replay stays a local refusal and never looks the order up.
                    with self.assertRaises(t.SubmissionNotSent):
                        await self.port.submit(payload)
        sdk_submit.assert_not_called()
        broker.assert_not_called()
        self.assertEqual(self.budgets, [])  # no request budget was ever reserved
        self.assertEqual(self.port.health["reasons"], [])
        self.assertEqual([i["client_order_id"] for i in self.intents],
                         ["_leading", "bad-symbol", "sub-penny"])  # risk ran; the contract refused after it

    async def test_valid_submit_posts_exactly_its_envelope(self):
        calls = []
        def request(method, url, **kwargs):
            calls.append((method, kwargs))
            return response(order(side="sell", qty="0.123456789", client_order_id="exit-1"))
        payload = intent(client_order_id="exit-1", side="sell", qty="0.123456789")
        with patch.object(self.port._client._session._session, "request", side_effect=request):
            result = await self.port.submit(payload)
        self.assertEqual(result["client_order_id"], "exit-1")
        self.assertEqual([m for m, _ in calls], ["POST"])
        envelope = t.order_envelope(t.normalize_intent(payload, ["SPY"]))
        self.assertTrue(t.wire_matches_envelope(calls[0][1]["json"], envelope))
        self.assertEqual(self.port._client._session._envelopes, {})  # withdrawn after the call

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

    async def test_stream_execution_is_forwarded_after_a_rest_read_advanced_past_it(self):
        # REST cancel read first (2 of 3 filled, canceled); the stream's older partial_fill for those 2
        # shares must still reach the sink and the adapter with its own qty, price and execution id.
        self.port.adopt_intents([intent(qty="3")])
        seen = []
        self.port._on_order = seen.append
        rest = order(qty="3", filled_qty="2", filled_avg_price="100.01", status="canceled",
                     updated_at="2026-09-21T15:00:02Z")
        await self.port._observe(t.normalize_order(rest))
        execution_id = str(__import__("uuid").uuid4())
        stream = {"event": "partial_fill", "execution_id": execution_id, "qty": "2", "price": "100.01",
                  "order": order(qty="3", filled_qty="2", filled_avg_price="100.01", status="partially_filled",
                                 updated_at="2026-09-21T15:00:01Z")}
        self.port._enqueue("order", stream)
        self.port._enqueue("order", dict(stream))   # delivered twice
        await self._drain()
        forwarded = [o for o in self.observations if o.get("execution_id")]
        self.assertEqual(len(forwarded), 1)
        self.assertEqual((forwarded[0]["event_qty"], forwarded[0]["event_price"], forwarded[0]["filled_qty"],
                          forwarded[0]["event"]), ("2", "100.01", "2", "partial_fill"))
        self.assertEqual([o.get("execution_id") for o in seen], [execution_id, None])
        self.assertEqual(self.port._observed["trial-1"]["status"], "canceled")   # stored state never moves back
        self.assertNotIn("execution_id", self.port._observed["trial-1"])
        self.assertEqual(self.port.health["reasons"], [])

    def fill_activity(self, cum, qty, price="5.61", *, index=0, order_id=ID, **changes):
        row = {"activity_type": "FILL", "id": "20260924150021%03d::%s" % (index, __import__("uuid").uuid4()),
               "cum_qty": str(cum), "leaves_qty": "0", "order_id": order_id, "order_status": "partially_filled",
               "price": price, "qty": str(qty), "side": "sell", "symbol": "SPY",
               "transaction_time": "2026-09-24T15:00:21.320056Z", "type": "partial_fill"}
        row.update(changes)
        return row

    async def test_fill_activities_page_through_the_guarded_session_and_tile_one_order(self):
        first = [self.fill_activity(i + 1, 1, index=i) for i in range(100)]
        second = [self.fill_activity(101, 1, index=100, type="fill", order_status="filled")]
        with patch.object(self.port._client._session._session, "request",
                          side_effect=[response(first), response(second)]) as request:
            executions = await self.port.fill_activities(ID)
        self.assertEqual(len(executions), 101)
        self.assertEqual([c.args[0] for c in request.call_args_list], ["GET", "GET"])
        self.assertTrue(all(c.args[1] == t.PAPER_URL + t.ACTIVITY_FILL_PATH for c in request.call_args_list))
        self.assertEqual(request.call_args_list[0].kwargs["params"], {"order_id": ID, "direction": "asc", "page_size": 100})
        self.assertEqual(request.call_args_list[1].kwargs["params"]["page_token"], first[-1]["id"])
        self.assertEqual([b[0] for b in self.budgets], ["read", "read"])
        e = executions[0]
        self.assertEqual((e["qty"], e["price"], e["cum_qty"], e["side"], e["symbol"], e["type"]),
                         ("1", "5.61", "1", "sell", "SPY", "partial_fill"))
        self.assertEqual(e["trade_id"], first[0]["id"].split("::")[1])
        self.assertEqual(len(e["trade_id"]), 36)
        self.assertEqual(e["transaction_time_ns"], t.timestamp_ns("2026-09-24T15:00:21.320056Z"))

    async def test_fill_activities_that_do_not_describe_one_complete_order_are_refused(self):
        other = str(__import__("uuid").UUID(int=2))
        cases = {"gap": [self.fill_activity(1, 1), self.fill_activity(3, 1, index=1)],
                 "other_order": [self.fill_activity(1, 1, order_id=other)],
                 "not_fill": [self.fill_activity(1, 1, activity_type="FEE")],
                 "zero_qty": [self.fill_activity(1, 0)],
                 "qty_above_cum": [self.fill_activity(1, 2)],
                 "bad_id": [self.fill_activity(1, 1, id="20260924::not-a-uuid")],
                 "mixed_side": [self.fill_activity(1, 1), self.fill_activity(2, 1, index=1, side="buy")],
                 "not_a_list": {"activities": []}}
        for label, payload in cases.items():
            with self.subTest(label=label):
                with patch.object(self.port._client._session._session, "request", return_value=response(payload)):
                    with self.assertRaises(t.TransportError):
                        await self.port.fill_activities(ID)
        with patch.object(self.port._client._session._session, "request") as request:
            with self.assertRaises(t.TransportError):
                await self.port.fill_activities("not-an-order-id")
        request.assert_not_called()

    async def test_trading_status_messages_reach_the_status_sink_and_are_counted(self):
        statuses = []
        self.port.sink_status = statuses.append
        # The 2026-09-24 SIP capture's ATGL pause and resumption, in the documented schema, for SPY.
        self.port._enqueue("status", {"T": "s", "S": "SPY", "sc": "P", "sm": "Volatility Trading Pause",
                                      "rc": "LUDP", "rm": "Volatility Trading Pause",
                                      "t": "2026-09-24T15:40:40.219046565Z", "z": "C"})
        self.port._enqueue("status", {"T": "s", "S": "SPY", "sc": "T", "sm": "Trading Resumption", "rc": "C11",
                                      "rm": "Trade Halt Concluded By Other Regulatory Auth,; Quotes/Trades Resume",
                                      "t": "2026-09-24T15:45:40.219163054Z", "z": "C"})
        await self._drain()
        self.assertEqual([(s["symbol"], s["state"], s["halted"], s["reason_code"]) for s in statuses],
                         [("SPY", "volatility_pause", True, "LUDP"), ("SPY", "trading", False, "C11")])
        self.assertEqual(statuses[0]["ts_ns"], t.timestamp_ns("2026-09-24T15:40:40.219046565Z"))
        self.assertEqual(self.port.health["trading_status_messages"], {"volatility_pause": 1, "trading": 1})
        self.assertEqual(self.port.health["reasons"], [])
        self.port._enqueue("status", {"T": "s", "S": "TSLA", "sc": "H", "t": "2026-09-24T15:40:40Z", "z": "C"})
        await self._drain()
        self.assertIn("callback_failure", self.port.health["reasons"])   # a symbol this transport never subscribed

    async def test_luld_bands_are_kept_for_receipts_and_never_freeze(self):
        self.port._enqueue("luld", {"T": "l", "S": "SPY", "u": 3.24, "d": 2.65, "i": "B",
                                    "t": "2026-09-24T15:40:40Z", "z": "C"})
        self.port._enqueue("luld", {"T": "l", "S": "SPY", "u": 3.30, "d": 2.70, "i": "A",
                                    "t": "2026-09-24T15:40:39Z", "z": "C"})   # older: ignored
        self.port._enqueue("luld", {"T": "l", "S": "SPY", "u": "bad", "d": 1, "t": "2026-09-24T15:40:41Z"})
        self.port._enqueue("luld", {"T": "l", "S": "TSLA", "u": 1, "d": 1, "t": "2026-09-24T15:40:41Z"})
        await self._drain()
        band = self.port.health["luld_bands"]["SPY"]
        self.assertEqual((band["limit_up"], band["limit_down"], band["indicator"], band["tape"]),
                         ("3.24", "2.65", "B", "C"))
        self.assertEqual(self.port.health["luld_invalid"], 2)
        self.assertEqual(self.port.health["reasons"], [])

    def sip_port(self, symbols=("SPY",), **changes):
        port = t.AlpacaPaperTransport("fixture-key", "fixture-secret", list(symbols),
                                      before_request=lambda *a, **k: None, before_submit=lambda x: None,
                                      sink_observation=lambda x: None, feed="sip", **changes)
        port._loop = asyncio.get_running_loop()
        port._authorized("quotes")
        return port

    async def test_quote_subscription_ack_requires_statuses_and_lulds_for_every_symbol_on_sip(self):
        port = self.sip_port()
        self.addAsyncCleanup(port.stop)
        self.assertTrue(port.halt_statuses)
        await port._quotes_stream._dispatch({"T": "subscription", "quotes": ["SPY"], "statuses": ["SPY"],
                                             "lulds": ["SPY"]})
        self.assertTrue(port._acks["quotes"])
        await port._quotes_stream._dispatch({"T": "subscription", "quotes": ["SPY"], "statuses": [],
                                             "lulds": ["SPY"]})
        self.assertFalse(port._acks["quotes"])
        self.assertIn("halt_status_subscription_rejected", port.health["reasons"])

    async def test_an_iex_quote_ack_needs_no_halt_channels(self):
        # E4 scopes statuses and LULD bands to the SIP connection; on iex neither is
        # subscribed, so a quote-only acknowledgement is complete.
        self.assertFalse(self.port.halt_statuses)
        self.assertEqual(self.port.health["halt_status_channels"], [])
        self.port._acks["quotes"] = False
        await self.port._quotes_stream._dispatch({"T": "subscription", "quotes": ["SPY"]})
        self.assertTrue(self.port._acks["quotes"])
        self.assertEqual(self.port.health["reasons"], [])

    async def test_start_subscribes_statuses_and_lulds_on_the_sip_quote_connection(self):
        await self.port.stop()
        with patch.object(t, "_stream_classes", return_value=(FakeStream, FakeStream)):
            self.port = t.AlpacaPaperTransport("fixture-key", "fixture-secret", ["SPY", "QQQ"],
                    before_request=lambda *a, **k: None, before_submit=lambda x: None,
                    sink_observation=lambda x: None, start_timeout=1, required_quote_symbols=["SPY"], feed="sip")
        await self.port.start(lambda quote: None, lambda order: None)
        handlers = self.port._quotes_stream._handlers
        self.assertEqual({channel: set(handlers[channel]) for channel in ("quotes", "statuses", "lulds")},
                         {channel: {"QQQ", "SPY"} for channel in ("quotes", "statuses", "lulds")})
        self.assertEqual(handlers["statuses"]["SPY"], self.port._status_callback)
        self.assertEqual(handlers["lulds"]["SPY"], self.port._luld_callback)
        self.assertEqual(self.port.health["halt_status_channels"], ["statuses", "lulds"])

    async def test_start_on_iex_subscribes_quotes_only(self):
        await self.port.stop()
        with patch.object(t, "_stream_classes", return_value=(FakeStream, FakeStream)):
            self.port = t.AlpacaPaperTransport("fixture-key", "fixture-secret", ["SPY", "QQQ"],
                    before_request=lambda *a, **k: None, before_submit=lambda x: None,
                    sink_observation=lambda x: None, start_timeout=1, required_quote_symbols=["SPY"])
        await self.port.start(lambda quote: None, lambda order: None)
        handlers = self.port._quotes_stream._handlers
        self.assertEqual(set(handlers["quotes"]), {"QQQ", "SPY"})
        self.assertEqual((handlers["statuses"], handlers["lulds"]), ({}, {}))

    async def test_queued_statuses_and_lulds_do_not_block_reconciliation(self):
        self.port._enqueue("status", {"T": "s", "S": "SPY", "sc": "T", "t": "2026-09-24T15:40:40Z"})
        self.port._enqueue("luld", {"T": "l", "S": "SPY", "u": 1, "d": 1, "t": "2026-09-24T15:40:40Z"})
        self.port.mark_reconciled()

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

    def _stream_quote(self, **changes):
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".000000000Z"
        return {"S": "SPY", "bp": "100.01", "ap": "100.02", "bs": 1, "as": 1, "t": stamp, **changes}

    async def _drain(self):
        task = asyncio.create_task(self.port._consume_events())
        for _ in range(100):
            if self.port._events.empty():
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.02)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_crossed_streamed_quote_is_dropped_and_counted_not_fatal(self):
        seen = []
        self.port._on_quote = seen.append
        self.port._enqueue("quote", self._stream_quote(bp="100.03", ap="100.02"))
        self.port._enqueue("quote", self._stream_quote(bp=0))
        self.port._enqueue("quote", self._stream_quote())
        await self._drain()
        self.assertEqual(self.port.health["reasons"], [])
        self.assertEqual(self.port.health["dropped_quotes"], {"crossed": 1, "one_sided": 1})
        self.assertEqual([q["bid"] for q in seen], ["100.01"])
        self.assertTrue(self.port.ready)

    async def test_dropped_quote_keeps_the_last_valid_quote_and_its_age(self):
        self.port._on_quote = lambda quote: None
        self.port._enqueue("quote", self._stream_quote())
        await self._drain()
        seen_at = self.port._quote_seen["SPY"]
        self.port._enqueue("quote", self._stream_quote(bp="100.05", ap="100.04"))
        await self._drain()
        self.assertEqual(self.port._quote_values["SPY"]["bid"], "100.01")
        self.assertEqual(self.port._quote_seen["SPY"], seen_at)
        self.assertEqual(self.port.health["dropped_quotes_by_symbol"], {"SPY": 1})
        # Only crossed quotes after that: freshness still expires and the watchdog marks it stale.
        self.port._quote_seen["SPY"] = time.monotonic() - self.port.quote_timeout - 1
        self.port._ever_ready = True
        self.port._enqueue("quote", self._stream_quote(bp="100.05", ap="100.04"))
        await self._drain()
        task = asyncio.create_task(self.port._watchdog())
        await asyncio.sleep(0.02)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertIn("quote_stale", self.port.health["reasons"])
        self.assertFalse(self.port.ready)

    async def test_halted_or_unsubscribed_invalid_quote_fails_closed(self):
        for changes in ({"bp": "100.05", "ap": "100.04", "c": ["H"]}, {"S": "TSLA", "bp": "100.05", "ap": "100.04"}):
            with self.subTest(changes=changes):
                self.port._reasons.clear()
                self.port._on_quote = lambda quote: None
                self.port._enqueue("quote", self._stream_quote(**changes))
                await self._drain()
                self.assertIn("callback_failure", self.port.health["reasons"])

    async def test_routine_acknowledgement_keeps_pending_order_update_timers(self):
        self.port._pending_stream["trial-1"] = time.monotonic()
        self.port.freeze_health("quote_stale")
        self.port.mark_reconciled()
        self.assertIn("trial-1", self.port._pending_stream)
        self.assertEqual(self.port.health["reasons"], [])
        self.port.freeze_health("orders_disconnected")
        self.port.mark_reconciled()
        self.assertNotIn("trial-1", self.port._pending_stream)

    async def test_queued_quotes_do_not_block_reconciliation_but_order_events_do(self):
        self.port._enqueue("quote", self._stream_quote())
        self.port._enqueue("quote", self._stream_quote())
        self.port.mark_reconciled()
        self.port._enqueue("order", {"event": "new", "order": {}})
        with self.assertRaises(t.TransportError):
            self.port.mark_reconciled()

    async def test_malformed_streamed_quote_still_fails_the_transport(self):
        self.port._on_quote = lambda quote: None
        self.port._enqueue("quote", self._stream_quote(bs=-1))
        await self._drain()
        self.assertIn("callback_failure", self.port.health["reasons"])

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
        with patch.object(self.port._client, "get", side_effect=[page, [order(id=str(__import__("uuid").UUID(int=0x500)))]]) as get:
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


class DataFeedSelection(unittest.TestCase):
    """One configured feed derives the quote stream endpoint; nothing else does."""

    def test_configured_feed_selects_the_matching_quote_stream(self):
        self.assertEqual(t.DATA_FEEDS, ("iex", "sip"))
        self.assertEqual(t.data_stream_url("iex"), "wss://stream.data.alpaca.markets/v2/iex")
        self.assertEqual(t.data_stream_url("sip"), "wss://stream.data.alpaca.markets/v2/sip")

    def test_a_str_subclass_naming_a_feed_is_still_refused(self):
        class FeedLike(str):
            def __str__(self):
                return "DataFeed.IEX"
        with self.assertRaises(t.UnsupportedDataFeed):
            t.data_stream_url(FeedLike("iex"))

    def test_unqualified_feed_is_refused_before_any_endpoint_is_derived(self):
        for value in ("otc", "delayed_sip", "boats", "overnight", "IEX", "iex ", "", None, 1, ["iex"]):
            with self.subTest(feed=value):
                with self.assertRaises(t.UnsupportedDataFeed) as caught:
                    t.data_stream_url(value)
                self.assertEqual(str(caught.exception), "unqualified_data_feed")
                self.assertIsInstance(caught.exception, t.TransportError)

    @unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")
    def test_sdk_enum_members_are_refused_rather_than_formatted_into_the_url(self):
        from alpaca.data.enums import DataFeed
        for member in (DataFeed.IEX, DataFeed.SIP):
            with self.subTest(feed=member):
                self.assertIsInstance(member, str)
                self.assertIn(member, t.DATA_FEEDS)
                self.assertEqual("%s" % member, "DataFeed." + member.name)
                with self.assertRaises(t.UnsupportedDataFeed) as caught:
                    t.data_stream_url(member)
                self.assertEqual(str(caught.exception), "unqualified_data_feed")

    @unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")
    def test_quote_stream_connect_guard_follows_the_configured_feed(self):
        _, Quotes = t._stream_classes("wss://stream.data.alpaca.markets/v2/sip")
        stream = Quotes.__new__(Quotes)
        stream.owner = Mock()
        stream._endpoint = "wss://stream.data.alpaca.markets/v2/iex"
        with self.assertRaisesRegex(t.TransportError, "quote websocket endpoint rejected"):
            asyncio.run(stream._connect())


@unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")
class ConfiguredQuoteFeed(unittest.TestCase):
    """No broker request is made; only the constructed stream arguments are read."""

    def build(self, **kwargs):
        captured = []

        class Capturing(FakeStream):
            def __init__(self, *args, **stream_kwargs):
                captured.append(stream_kwargs)
                super().__init__(*args, **stream_kwargs)

        with patch.object(t, "_stream_classes", return_value=(Capturing, Capturing)) as classes:
            port = t.AlpacaPaperTransport("fixture-key", "fixture-secret", ["SPY"],
                                          before_request=lambda *a, **k: None,
                                          before_submit=lambda intent: None,
                                          sink_observation=lambda observation: None, **kwargs)
        quotes = [row for row in captured if "feed" in row]
        self.assertEqual(len(quotes), 1)
        return port, classes, quotes[0]

    def test_iex_feed_keeps_the_frozen_quote_stream(self):
        port, classes, quotes = self.build(feed="iex")
        self.assertEqual(port.feed, "iex")
        self.assertEqual(port.data_ws, "wss://stream.data.alpaca.markets/v2/iex")
        self.assertEqual(classes.call_args.args, (port.data_ws,))
        self.assertEqual(quotes["feed"], "iex")
        self.assertEqual(quotes["url_override"], port.data_ws)

    def test_sip_feed_selects_the_sip_quote_stream(self):
        port, classes, quotes = self.build(feed="sip")
        self.assertEqual(port.feed, "sip")
        self.assertEqual(port.data_ws, "wss://stream.data.alpaca.markets/v2/sip")
        self.assertEqual(classes.call_args.args, (port.data_ws,))
        self.assertEqual(quotes["feed"], "sip")
        self.assertEqual(quotes["url_override"], port.data_ws)

    def test_default_transport_feed_remains_the_frozen_iex_lane(self):
        port, _, quotes = self.build()
        self.assertEqual(port.feed, "iex")
        self.assertEqual(quotes["url_override"], "wss://stream.data.alpaca.markets/v2/iex")

    def test_unqualified_feed_refused_before_any_stream_is_constructed(self):
        with self.assertRaises(t.UnsupportedDataFeed):
            self.build(feed="otc")

    def test_sdk_enum_member_is_refused_by_the_transport_and_by_preflight(self):
        from alpaca.data.enums import DataFeed
        with self.assertRaises(t.UnsupportedDataFeed):
            self.build(feed=DataFeed.SIP)
        with patch.object(t, "_sdk_client") as client:
            with self.assertRaises(t.UnsupportedDataFeed):
                t.preflight("fixture-key", "fixture-secret", ["SPY"], feed=DataFeed.SIP,
                            before_request=lambda *a, **k: None)
        client.assert_not_called()


class TradingStatusParsing(unittest.TestCase):
    """E4: every trading status code Alpaca documents per tape
    (https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data.md, "Trading Status"),
    in the documented message schema. Synthetic fixtures; no stream connection."""

    def status(self, sc, rc="", z="C", ts="2026-09-24T15:40:40.219046565Z", symbol="SPY"):
        return {"T": "s", "S": symbol, "sc": sc, "sm": "", "rc": rc, "rm": "", "t": ts, "z": z}

    def test_every_documented_status_code_maps_to_one_effect(self):
        cta = {"2": True, "3": False, "5": True, "6": None, "7": None, "8": None, "9": None, "A": None,
               "C": None, "D": None, "E": None, "F": None}
        utp = {"H": True, "Q": True, "P": True, "T": False}
        for tape, table in (("A", cta), ("B", cta), ("C", utp), ("O", utp)):
            for code, halted in table.items():
                with self.subTest(tape=tape, code=code):
                    self.assertIs(t.normalize_trading_status(self.status(code, z=tape))["halted"], halted)
        self.assertEqual(set(t.CTA_STATUS_CODES), set(cta))
        self.assertEqual(set(t.UTP_STATUS_CODES), set(utp))

    def test_cta_halt_with_reason_m_is_a_luld_pause_and_e_or_f_never_changes_the_state(self):
        status = t.normalize_trading_status(self.status("2", "M", z="A"))
        self.assertEqual((status["state"], status["halted"], status["reason_code"]), ("luld_pause", True, "M"))
        for code, state in (("E", "short_sale_restriction"), ("F", "luld_limit_state")):
            status = t.normalize_trading_status(self.status(code, z="B"))
            self.assertEqual((status["state"], status["halted"]), (state, None))

    def test_cta_price_indication_halts_and_trading_range_indication_does_not(self):
        # CTS Pillar output specification v2.11b: a Price Indication is the reopening range
        # "when trading resumes after a Trading Halt"; a Trading Range Indication describes
        # "a security that is not Trading Halted", before or after the opening.
        price = t.normalize_trading_status(self.status("5", z="A"))
        self.assertEqual((price["state"], price["halted"]), ("price_indication", True))
        trading_range = t.normalize_trading_status(self.status("6", z="B"))
        self.assertEqual((trading_range["state"], trading_range["halted"]), ("trading_range_indication", None))

    def test_halt_statuses_ride_only_the_sip_feed(self):
        self.assertTrue(t.halt_statuses_supported("sip"))
        for feed in ("iex", "delayed_sip", "boats", "otc", "SIP", None):
            with self.subTest(feed=feed):
                self.assertFalse(t.halt_statuses_supported(feed))

    def test_market_wide_circuit_breakers_halt_and_mwcq_resumes(self):
        for code, reason, tape in (("2", "1", "A"), ("2", "3", "B"), ("H", "MWC1", "C"), ("H", "MWC0", "O")):
            with self.subTest(code=code, reason=reason):
                status = t.normalize_trading_status(self.status(code, reason, z=tape))
                self.assertEqual((status["state"], status["halted"]), ("market_wide_circuit_breaker", True))
        resume = t.normalize_trading_status(self.status("T", "MWCQ"))
        self.assertEqual((resume["state"], resume["halted"]), ("trading", False))

    def test_unknown_or_cross_tape_codes_fail_closed_and_malformed_messages_raise(self):
        for code, tape in (("X", "C"), ("H", "A"), ("2", "C"), ("Z", None), ("Z", "Q"), ("T", "A"), ("3", "C")):
            with self.subTest(code=code, tape=tape):
                status = t.normalize_trading_status(self.status(code, z=tape))
                self.assertEqual((status["state"], status["halted"]), ("unknown_status", True))
        # Without a tape the code alone decides (the two tables share no code).
        self.assertIs(t.normalize_trading_status(self.status("H", z=None))["halted"], True)
        for changes in ({"S": None}, {"S": "spy"}, {"sc": None}, {"sc": ""}, {"t": None},
                        {"t": "2026-09-24T15:40:40"}):
            with self.subTest(changes=changes), self.assertRaises(t.TransportError):
                t.normalize_trading_status({**self.status("H"), **changes})

    def test_an_unrecognized_tape_reads_both_tables_so_a_documented_resume_still_resumes(self):
        # B7: a tape outside A, B, C and O (for example an empty string) used to turn every code
        # into unknown_status, so the symbol could never resume in-session.
        for tape in ("", "Q", "X", 7, None):
            for code, state, halted in (("H", "halted", True), ("T", "trading", False), ("2", "halted", True),
                                        ("3", "trading", False), ("6", "trading_range_indication", None),
                                        ("P", "volatility_pause", True), ("X", "unknown_status", True)):
                with self.subTest(tape=tape, code=code):
                    status = t.normalize_trading_status(self.status(code, z=tape))
                    self.assertEqual((status["state"], status["halted"]), (state, halted))
        self.assertIsNone(t.normalize_trading_status(self.status("T", z=7))["tape"])

    def test_documented_luld_band_parses_and_malformed_bands_raise(self):
        band = t.normalize_luld({"T": "l", "S": "IONM", "u": 3.24, "d": 2.65, "i": "B",
                                 "t": "2023-04-06T13:34:45.565004401Z", "z": "C"})
        self.assertEqual((band["symbol"], band["limit_up"], band["limit_down"], band["indicator"], band["tape"]),
                         ("IONM", "3.24", "2.65", "B", "C"))
        for changes in ({"S": None}, {"u": -1}, {"d": "x"}, {"t": None}):
            with self.subTest(changes=changes), self.assertRaises(t.TransportError):
                t.normalize_luld({"T": "l", "S": "IONM", "u": 3.24, "d": 2.65, "t": "2023-04-06T13:34:45Z",
                                  **changes})


def halt_item(symbol, date, time_, reason="LUDP", market="NASDAQ", resume_date="", resume_trade=""):
    """One trade halts RSS item in the schema Nasdaq Trader publishes (ndaq: fields)."""
    return ("<item><title>%s</title><ndaq:HaltDate>%s</ndaq:HaltDate><ndaq:HaltTime>%s</ndaq:HaltTime>"
            "<ndaq:IssueSymbol>%s</ndaq:IssueSymbol><ndaq:IssueName>Fixture</ndaq:IssueName>"
            "<ndaq:Market>%s</ndaq:Market><ndaq:ReasonCode>%s</ndaq:ReasonCode><ndaq:PauseThresholdPrice />"
            "<ndaq:ResumptionDate>%s</ndaq:ResumptionDate><ndaq:ResumptionQuoteTime />"
            "<ndaq:ResumptionTradeTime>%s</ndaq:ResumptionTradeTime><description>table</description></item>"
            % (symbol, date, time_, symbol, market, reason, resume_date, resume_trade))


def halt_feed(*items):
    return ("﻿<?xml version=\"1.0\" encoding=\"utf-8\"?><rss version=\"2.0\" "
            "xmlns:ndaq=\"http://www.nasdaqtrader.com/\"><channel><title>NASDAQTrader.com</title><ttl>1</ttl>"
            + "".join(items) + "</channel></rss>").encode("utf-8")


class FakeFeedResponse:
    """A streamed requests.Response of the halts feed. Each socket read returns at most
    ``chunk`` bytes and advances the fake ``clock`` by ``per_read`` seconds. ``raw.read1``
    is one socket read (urllib3 HTTPResponse.read1); ``iter_content(size)`` keeps reading
    until it has ``size`` bytes, as urllib3's read(amt) does."""

    def __init__(self, status=200, body=b"", chunk=65536, headers=None, clock=None, per_read=0.0):
        self.status_code, self.body, self.chunk, self.closed = status, body, chunk, False
        self.headers = dict(headers or {})
        self.clock, self.per_read, self.offset, self.socket_reads = clock, per_read, 0, 0
        self.raw = self

    def _socket_read(self, size):
        self.socket_reads += 1
        if self.clock is not None:
            self.clock[0] += self.per_read
        data = self.body[self.offset:self.offset + min(size, self.chunk)]
        self.offset += len(data)
        return data

    def read1(self, amt, decode_content=None):
        return self._socket_read(amt)

    def iter_content(self, size):
        while self.offset < len(self.body):
            data = b""
            while len(data) < size and self.offset < len(self.body):
                data += self._socket_read(size - len(data))
            yield data

    def close(self):
        self.closed = True


class HaltFeedSeed(unittest.TestCase):
    """E4 startup state: halts already in force when the engine subscribes, from one trade
    halts RSS read (synthetic documents in the published item schema; no network)."""

    NOW = t.eastern_ns("09/24/2026", "11:42:00")
    FEED = halt_feed(
        halt_item("AAA", "09/24/2026", "11:40:40.220", resume_date="09/24/2026", resume_trade="11:45:40"),
        halt_item("BBB", "09/24/2026", "11:22:36.116", resume_date="09/24/2026", resume_trade="11:27:36"),
        halt_item("CCC", "09/23/2026", "15:10:02.004", reason="T12", market="NYSE"),
        halt_item("DDD", "09/24/2026", "10:01:00.000", resume_date="09/24/2026", resume_trade="10:06:00"),
        halt_item("DDD", "09/24/2026", "11:41:30.500", reason="M", market="NYSE"),
        halt_item("ZZZ", "not a date", "11:00:00"))

    def test_the_feed_parses_to_rows_of_the_documented_fields(self):
        rows = t.parse_nasdaq_halts(self.FEED)
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0], {"HaltDate": "09/24/2026", "HaltTime": "11:40:40.220", "IssueSymbol": "AAA",
                                   "Market": "NASDAQ", "ReasonCode": "LUDP", "ResumptionDate": "09/24/2026",
                                   "ResumptionQuoteTime": None, "ResumptionTradeTime": "11:45:40"})
        for payload in (b"not xml", b"<html><body/></html>", b"<rss version=\"2.0\"/>", None):
            with self.subTest(payload=payload), self.assertRaises(t.TransportError):
                t.parse_nasdaq_halts(payload)

    def test_active_halts_are_the_latest_unresumed_halt_of_each_wanted_symbol(self):
        rows = t.parse_nasdaq_halts(self.FEED)
        halts = t.active_halts(rows, ["AAA", "BBB", "CCC", "DDD", "SPY"], self.NOW)
        # AAA resumes at 11:45:40 (still ahead); BBB resumed at 11:27:36; CCC (T12, yesterday)
        # has no resumption; DDD's newer halt has none. ZZZ is not wanted, so its bad row is ignored.
        self.assertEqual(sorted(halts), ["AAA", "CCC", "DDD"])
        self.assertEqual(halts["AAA"], {"halted_at_ns": t.timestamp_ns("2026-09-24T15:40:40.220Z"),
                                        "resumption_trade_ns": t.timestamp_ns("2026-09-24T15:45:40Z"),
                                        "reason_code": "LUDP", "market": "NASDAQ"})
        self.assertEqual((halts["DDD"]["reason_code"], halts["DDD"]["resumption_trade_ns"]), ("M", None))
        self.assertEqual(t.active_halts(rows, ["AAA"], t.eastern_ns("09/24/2026", "11:45:41")), {})
        with self.assertRaises(t.TransportError):   # a malformed row of a wanted symbol is never guessed
            t.active_halts(rows, ["ZZZ"], self.NOW)

    def test_eastern_times_convert_across_daylight_saving(self):
        self.assertEqual(t.eastern_ns("09/24/2026", "11:40:40.220"), t.timestamp_ns("2026-09-24T15:40:40.220Z"))
        self.assertEqual(t.eastern_ns("01/05/2026", "09:30:00"), t.timestamp_ns("2026-01-05T14:30:00Z"))
        for date, time_ in (("2026-09-24", "11:40:40"), ("09/24/2026", "11:40"), ("13/01/2026", "10:00:00"), (None, None)):
            with self.subTest(date=date, time_=time_), self.assertRaises(t.TransportError):
                t.eastern_ns(date, time_)

    def test_one_bounded_get_of_the_one_url_without_redirects(self):
        calls, response = [], FakeFeedResponse(body=self.FEED, chunk=100)
        def get(url, **kwargs):
            calls.append((url, kwargs))
            return response
        self.assertEqual(t.fetch_nasdaq_halts(get=get), self.FEED)
        self.assertEqual(len(calls), 1)
        url, kwargs = calls[0]
        self.assertEqual(url, "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts")
        self.assertEqual((kwargs["allow_redirects"], kwargs["stream"]), (False, True))
        self.assertTrue(response.closed)
        refused = {"redirect": lambda url, **kw: FakeFeedResponse(status=302),
                   "server_error": lambda url, **kw: FakeFeedResponse(status=503),
                   "too_large": lambda url, **kw: FakeFeedResponse(body=b"x" * 2048, chunk=512),
                   "network": Mock(side_effect=OSError("connection reset"))}
        for label, fake in refused.items():
            with self.subTest(label=label), self.assertRaises(t.TransportError):
                t.fetch_nasdaq_halts(get=fake, max_bytes=1024)

    def test_a_dripping_server_cannot_hold_the_read_past_its_deadline(self):
        # A6: requests' timeout bounds each socket read, not the body. A server sending one
        # byte every 4 s (inside the 5 s read timeout) kept one 64 KB iter_content chunk open
        # for len(body) x 4 s before any deadline check; each read1 is one socket read and the
        # deadline is checked before every read.
        clock = [1000.0]
        response = FakeFeedResponse(body=self.FEED, chunk=1, clock=clock, per_read=4.0)
        with patch.object(t.time, "monotonic", lambda: clock[0]), self.assertRaises(t.TransportError):
            t.fetch_nasdaq_halts(get=lambda url, **kwargs: response, seconds=5.0)
        self.assertLessEqual(clock[0] - 1000.0, 5.0 + 4.0)          # at most one read past the deadline
        self.assertLessEqual(response.socket_reads, 3)
        self.assertTrue(response.closed)

    @unittest.skipUnless(importlib.util.find_spec("requests"), "requests is not installed")
    def test_a_dripping_loopback_server_is_cut_off_at_the_deadline_by_the_real_http_stack(self):
        # A6, local integration with the installed requests/urllib3 (loopback only): a server
        # that sends its 40-byte body one byte every 0.3 s stays inside the 1 s per-read
        # timeout, so reading the whole body takes 12 s; the fetch must end near its 1 s
        # deadline (one read past it at most) and never return a partial body.
        import http.server
        import requests

        class Drip(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/rss+xml")
                self.send_header("Content-Length", "40")
                self.end_headers()
                try:
                    for _ in range(40):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.3)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Drip)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:%d/" % server.server_address[1]
        try:
            started = time.monotonic()
            with self.assertRaises(t.TransportError):
                t.fetch_nasdaq_halts(get=lambda _, **kwargs: requests.get(url, **kwargs), seconds=1.0)
            self.assertLess(time.monotonic() - started, 3.0)
        finally:
            server.shutdown()
            server.server_close()

    def test_the_feed_is_requested_uncompressed_and_an_encoded_body_is_refused(self):
        calls = []
        def get(url, **kwargs):
            calls.append(kwargs)
            return FakeFeedResponse(body=self.FEED, headers={"Content-Encoding": "gzip"})
        with self.assertRaises(t.TransportError):
            t.fetch_nasdaq_halts(get=get)
        self.assertEqual(calls[0]["headers"]["Accept-Encoding"], "identity")
        plain = FakeFeedResponse(body=self.FEED, headers={"Content-Encoding": "identity"})
        self.assertEqual(t.fetch_nasdaq_halts(get=lambda url, **kwargs: plain), self.FEED)

    def test_the_seed_records_its_source_digest_and_active_halts(self):
        seed = t.nasdaq_halt_seed(["AAA", "BBB", "SPY"], now_ns=self.NOW, fetch=lambda: self.FEED)
        self.assertEqual((seed["source"], seed["items"], seed["bytes"], seed["fetched_at_ns"]),
                         ("nasdaq_trade_halts_rss", 6, len(self.FEED), self.NOW))
        self.assertRegex(seed["sha256"], r"\A[0-9a-f]{64}\Z")
        self.assertEqual(sorted(seed["halts"]), ["AAA"])


class LeverageNormalizeAccountTests(unittest.TestCase):
    """G-e E8: normalize_account's opt-in include_margin flag (pure, no SDK)."""

    def raw_account(self, **overrides):
        raw = {"cash": "10000", "equity": "30000", "buying_power": "10000",
              "status": "ACTIVE", "currency": "USD", "trading_blocked": False,
              "account_blocked": False, "trade_suspended_by_user": False,
              "shorting_enabled": True, "pattern_day_trader": False,
              "multiplier": "4", "daytrading_buying_power": "40000",
              "regt_buying_power": "20000", "daytrade_count": 0}
        raw.update(overrides)
        return raw

    def test_current_alpaca_schema_normalizes_without_legacy_fields(self):
        # Alpaca dropped daytrading_buying_power, pattern_day_trader and daytrade_count on 2026-07-06.
        raw = {"cash": "10000", "equity": "10000", "buying_power": "40000", "status": "ACTIVE", "currency": "USD",
               "trading_blocked": False, "account_blocked": False, "trade_suspended_by_user": False,
               "shorting_enabled": True, "multiplier": "4", "regt_buying_power": "20000",
               "maintenance_margin": "0", "initial_margin": "0"}
        result = t.normalize_account(raw, include_margin=True)
        for key in ("multiplier", "regt_buying_power", "maintenance_margin", "initial_margin", "buying_power"):
            self.assertIn(key, result)
        for key in ("daytrading_buying_power", "pattern_day_trader", "daytrade_count"):
            self.assertNotIn(key, result)
        self.assertNotIn("maintenance_margin", t.normalize_account(raw))

    def test_default_returns_exact_pre_change_key_set(self):
        result = t.normalize_account(self.raw_account())
        expected_keys = {"cash", "equity", "buying_power", "status", "currency", "trading_blocked",
                         "account_blocked", "trade_suspended_by_user", "shorting_enabled", "pattern_day_trader"}
        self.assertEqual(set(result), expected_keys)

    def test_include_margin_true_adds_margin_keys(self):
        result = t.normalize_account(self.raw_account(), include_margin=True)
        self.assertEqual(result["multiplier"], "4")
        self.assertEqual(result["daytrading_buying_power"], "40000")
        self.assertEqual(result["regt_buying_power"], "20000")
        self.assertEqual(result["daytrade_count"], 0)

    def test_include_margin_true_missing_fields_omitted_not_erroring(self):
        raw = self.raw_account()
        del raw["multiplier"]
        result = t.normalize_account(raw, include_margin=True)
        self.assertNotIn("multiplier", result)
        self.assertEqual(result["daytrading_buying_power"], "40000")


if __name__ == "__main__":
    unittest.main()
