"""Synthetic T15 overnight session/feed/status checks; no broker acceptance."""
from datetime import date, datetime
import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from unittest import mock
from zoneinfo import ZoneInfo

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

import sessions  # noqa: E402
import feeds  # noqa: E402
from transport import data_feed, data_stream_url  # noqa: E402
import transport  # noqa: E402
import runner  # noqa: E402
from runner import Controller  # noqa: E402
from safety import Quote, SafetyError  # noqa: E402
from tests.adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    from native_adapter import NativeOrderRejected  # noqa: E402

NY = ZoneInfo("America/New_York")
_STOP_TOKEN = None


def setUpModule():
    global _STOP_TOKEN
    _STOP_TOKEN = patch_default_stop()


def tearDownModule():
    restore_default_stop(_STOP_TOKEN)


class OvernightSessionTests(unittest.TestCase):
    def test_post_hands_off_at_2000_to_next_trade_date(self):
        # Alpaca 24/5: the Monday evening session belongs to Tuesday's trade date.
        before = sessions.session_at(datetime(2026, 3, 9, 19, 59, 59, tzinfo=NY))
        opened = sessions.session_at(datetime(2026, 3, 9, 20, 0, tzinfo=NY))
        self.assertEqual(before.kind, sessions.SessionKind.POST)
        self.assertEqual(opened.kind, sessions.SessionKind.OVERNIGHT)
        self.assertEqual(opened.session_date, date(2026, 3, 10))
        self.assertEqual(opened.open, datetime(2026, 3, 9, 20, 0, tzinfo=NY))
        self.assertEqual(opened.close, datetime(2026, 3, 10, 4, 0, tzinfo=NY))
        self.assertEqual(opened.seconds_to_close, 8 * 3600)

    def test_overnight_hands_off_to_pre_at_0400(self):
        last = sessions.session_at(datetime(2026, 3, 10, 3, 59, 59, tzinfo=NY))
        pre = sessions.session_at(datetime(2026, 3, 10, 4, 0, tzinfo=NY))
        self.assertEqual(last.kind, sessions.SessionKind.OVERNIGHT)
        self.assertEqual(last.seconds_to_close, 1)
        self.assertEqual(pre.kind, sessions.SessionKind.PRE)
        self.assertEqual(last.session_date, pre.session_date)
        self.assertEqual(last.close, pre.open)

    def test_sunday_start_and_friday_end(self):
        for stamp, kind in (
            ((2026, 3, 8, 19, 59), sessions.SessionKind.CLOSED),
            ((2026, 3, 8, 20, 0), sessions.SessionKind.OVERNIGHT),
            ((2026, 3, 13, 2, 0), sessions.SessionKind.OVERNIGHT),
            ((2026, 3, 13, 20, 0), sessions.SessionKind.CLOSED),
            ((2026, 3, 14, 2, 0), sessions.SessionKind.CLOSED),
        ):
            with self.subTest(stamp=stamp):
                self.assertEqual(sessions.session_at(datetime(*stamp, tzinfo=NY)).kind, kind)

    def test_upcoming_trade_date_controls_holidays_and_half_days(self):
        # The vendor's Thanksgiving example: no Wed-night session into the holiday,
        # but Thu-night trading into the Friday half-day lasts the full eight hours.
        self.assertEqual(sessions.session_at(datetime(2026, 11, 25, 20, 0, tzinfo=NY)).kind,
                         sessions.SessionKind.CLOSED)
        self.assertEqual(sessions.session_at(datetime(2026, 11, 26, 2, 0, tzinfo=NY)).kind,
                         sessions.SessionKind.CLOSED)
        opened = sessions.session_at(datetime(2026, 11, 26, 20, 0, tzinfo=NY))
        self.assertEqual(opened.kind, sessions.SessionKind.OVERNIGHT)
        self.assertEqual(opened.session_date, date(2026, 11, 27))
        self.assertTrue(opened.is_early_close)
        self.assertEqual(opened.seconds_to_close, 8 * 3600)

    def test_closed_next_open_names_sunday_overnight_not_monday_pre(self):
        closed = sessions.session_at(datetime(2026, 3, 13, 20, 0, tzinfo=NY))
        self.assertEqual(closed.next_open, datetime(2026, 3, 15, 20, 0, tzinfo=NY))

    def test_order_flag_and_window_cover_overnight(self):
        now = datetime(2026, 3, 9, 21, 0, tzinfo=NY)
        self.assertTrue(sessions.order_extended_hours_flag(now, {"extended_hours": True}))
        self.assertFalse(sessions.order_extended_hours_flag(now, {"extended_hours": False}))
        self.assertEqual(sessions.extended_session_close(now), datetime(2026, 3, 10, 20, 0, tzinfo=NY))


class OvernightFeedTests(unittest.TestCase):
    def test_boats_is_the_explicit_feed_and_uses_the_vendor_beta_endpoint(self):
        self.assertTrue(feeds.is_qualified_feed("boats"))
        self.assertEqual(data_feed("boats"), "boats")
        self.assertEqual(data_stream_url("boats"), "wss://stream.data.alpaca.markets/v1beta1/boats")
        self.assertFalse(feeds.is_qualified_feed("overnight"))  # vendor's derived/delayed feed

    def test_unqualified_sdk_boats_stream_refuses_before_any_client_construction(self):
        with mock.patch.object(transport, "_sdk_client") as client:
            with self.assertRaisesRegex(transport.UnsupportedDataFeed, "boats_stream_unqualified_sdk"):
                transport.AlpacaPaperTransport(None, None, ["AAPL"], feed="boats",
                    before_request=None, before_submit=None, sink_observation=None)
        client.assert_not_called()


class OvernightStatusCarrierTests(unittest.TestCase):
    def test_status_comes_from_asset_attributes_not_quote_conditions_or_top_level_flags(self):
        stamp = int(datetime(2026, 3, 9, 21, 0, tzinfo=NY).timestamp() * 1_000_000_000)
        status = transport.normalize_overnight_status(
            {"symbol": "AAPL", "attributes": ["overnight_tradable"], "c": ["H"]}, stamp)
        self.assertIs(status["overnight_tradable"], True)
        self.assertIs(status["overnight_halted"], False)
        self.assertEqual(status["source"], "alpaca_assets")
        missing = transport.normalize_overnight_status(
            {"symbol": "AAPL", "overnight_tradable": True, "overnight_halted": False}, stamp)
        self.assertIsNone(missing["overnight_tradable"])
        self.assertIsNone(missing["overnight_halted"])

    def test_tradable_and_halted_remain_independent_status_checks(self):
        stamp = int(datetime(2026, 3, 9, 21, 0, tzinfo=NY).timestamp() * 1_000_000_000)
        halted = transport.normalize_overnight_status(
            {"symbol": "AAPL", "attributes": ["overnight_tradable", "overnight_halted"]}, stamp)
        self.assertIs(halted["overnight_tradable"], True)
        self.assertIs(halted["overnight_halted"], True)
        ineligible = transport.normalize_overnight_status({"symbol": "AAPL", "attributes": []}, stamp)
        self.assertIs(ineligible["overnight_tradable"], False)
        self.assertIs(ineligible["overnight_halted"], False)

    def test_malformed_attribute_lists_carry_unknown_instead_of_a_resume(self):
        for attributes in ("overnight_tradable", {}, [1], ["overnight_tradable", None]):
            with self.subTest(attributes=attributes):
                status = transport.normalize_overnight_status({"symbol": "AAPL", "attributes": attributes}, 1)
                self.assertIsNone(status["overnight_tradable"])
                self.assertIsNone(status["overnight_halted"])


@unittest.skipUnless(NATIVE, "requires reviewed isolated Nautilus runtime")
class OvernightAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 3, 9, 21, 0, tzinfo=NY).timestamp()
        self.ledger = Mock()
        self.ledger.reserve_intent.return_value = SimpleNamespace(
            newly_reserved=True, client_id="overnight-1", symbol="AAPL", side="sell")
        self.controller = Controller(self.ledger, self.now + 3600, market_open=True, clock=lambda: self.now)
        self.controller.port = SimpleNamespace(ready=True, extended_hours_allowed=True, quote_timeout=5)
        self.controller.quotes["AAPL"] = Quote("AAPL", "99", "101", self.now)
        self.order = {"client_order_id": "overnight-1", "symbol": "AAPL", "side": "sell",
                      "qty": "1", "limit_price": "99", "extended_hours": True}

    def status(self, attributes, *, delta=0):
        status = transport.normalize_overnight_status(
            {"symbol": "AAPL", "attributes": attributes}, int((self.now + delta) * 1_000_000_000))
        self.controller.trading_status(status)

    def test_halted_unknown_and_ineligible_status_refuse_both_order_sides_before_reservation(self):
        for attributes, reason in ((None, "overnight_status_unknown"),
                                   ([], "overnight_not_tradable"),
                                   (["overnight_tradable", "overnight_halted"], "overnight_halted")):
            for side in ("buy", "sell"):
                with self.subTest(attributes=attributes, side=side):
                    self.now += 1
                    self.status(attributes)
                    self.order["side"] = side
                    with self.assertRaisesRegex(NativeOrderRejected, reason):
                        self.controller.before_submit(self.order)
        self.ledger.reserve_intent.assert_not_called()

    def test_missing_status_cannot_be_cleared_by_a_fresh_manual_quote(self):
        self.controller.quote(transport.normalize_quote({"S": "AAPL", "bp": "99", "ap": "101",
            "bs": 1, "as": 1, "c": ["H"], "t": datetime.fromtimestamp(self.now, NY)}))
        with self.assertRaisesRegex(NativeOrderRejected, "overnight_status_unknown"):
            self.controller.before_submit(self.order)
        self.ledger.reserve_intent.assert_not_called()

    def test_explicit_eligible_unhalted_carrier_allows_the_existing_guard_to_run(self):
        self.status(["overnight_tradable"])
        self.controller.before_submit(self.order)
        self.ledger.reserve_intent.assert_called_once()

    def test_status_is_rechecked_after_reservation_before_http_submit_for_both_sides(self):
        import asyncio
        for attributes, reason in ((["overnight_tradable", "overnight_halted"], "overnight_halted"),
                                   ([], "overnight_not_tradable")):
            for side in ("buy", "sell"):
                with self.subTest(side=side, attributes=attributes):
                    self.now += 1
                    self.status(["overnight_tradable"])
                    self.order["side"] = side
                    self.controller.before_submit(self.order)
                    self.ledger.intents.return_value = [SimpleNamespace(
                        client_id="overnight-1", symbol="AAPL", side=side)]
                    self.status(attributes)
                    with self.assertRaisesRegex(SafetyError, reason):
                        asyncio.run(self.controller.before_request("submit", "overnight-1"))
        self.ledger.validate_pending.assert_not_called()
        self.ledger.request_budget.assert_not_called()

    def test_stale_and_future_status_refuse_and_stale_resumes_do_not_clear_halts(self):
        self.status(["overnight_tradable"], delta=-6)
        with self.assertRaisesRegex(NativeOrderRejected, "overnight_status_stale"):
            self.controller.before_submit(self.order)
        self.status(["overnight_tradable"], delta=1)
        with self.assertRaisesRegex(NativeOrderRejected, "overnight_status_stale"):
            self.controller.before_submit(self.order)
        self.now += 2
        self.status(["overnight_tradable", "overnight_halted"])
        self.status(["overnight_tradable"], delta=-1)
        with self.assertRaisesRegex(NativeOrderRejected, "overnight_halted"):
            self.controller.before_submit(self.order)

    def test_restrictive_eligibility_and_halt_state_win_timestamp_ties(self):
        for attributes, reason in (([], "overnight_not_tradable"),
                                   (None, "overnight_status_unknown"),
                                   (["overnight_tradable", "overnight_halted"], "overnight_halted")):
            with self.subTest(attributes=attributes):
                self.now += 1
                self.status(attributes)
                self.status(["overnight_tradable"])
                with self.assertRaisesRegex(NativeOrderRejected, reason):
                    self.controller.before_submit(self.order)
                self.now += 1
                self.status(["overnight_tradable"])
                self.status(attributes)
                with self.assertRaisesRegex(NativeOrderRejected, reason):
                    self.controller.before_submit(self.order)

    def test_invalid_carrier_timestamp_cannot_leave_a_prior_clear_state(self):
        self.status(["overnight_tradable"])
        status = transport.normalize_overnight_status({"symbol": "AAPL", "attributes": []}, 1)
        status["ts_ns"] = None
        self.controller.trading_status(status)
        with self.assertRaisesRegex(NativeOrderRejected, "overnight_status_unknown"):
            self.controller.before_submit(self.order)


class OvernightCallerTests(unittest.TestCase):
    def test_extended_policy_does_not_admit_the_new_market_session(self):
        from mover_runner import _controller_session
        now = datetime(2026, 3, 9, 21, 0, tzinfo=NY).timestamp()
        close, allowed = _controller_session(now + 3600, now, {"extended_hours": True})
        self.assertFalse(allowed)
        self.assertEqual(close, now + 3600)

    def test_held_book_financing_keeps_the_completed_rth_date_across_overnight(self):
        from decimal import Decimal
        ledger = SimpleNamespace(positions=lambda: {
            "AAPL": SimpleNamespace(qty=1, cost_basis_usd=Decimal("12000"))})
        projections = [runner._modeled_financing_block({}, ledger, "10000", stamp.timestamp())
                       for stamp in (datetime(2026, 3, 12, 19, 59, tzinfo=NY),
                                     datetime(2026, 3, 12, 20, 0, tzinfo=NY),
                                     datetime(2026, 3, 13, 0, 1, tzinfo=NY))]
        self.assertEqual(projections[0], projections[1])
        self.assertEqual(projections[0], projections[2])
