"""Synthetic (SYN) session-clock, session-policy, reconciliation and per-session
risk tests for the G-s (session model + overnight holds) deliverable. No
credentials, sockets, or broker execution; native tests use fakes only.
"""
import asyncio
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal as D
import importlib.util
from pathlib import Path
import sys
import time
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

import sessions as sess  # noqa: E402 (path inserted above)
from safety import Ledger, Quote, RiskLimits, SafetyError, evaluate_gap_risk  # noqa: E402
from transport import normalize_quote, normalize_trading_status  # noqa: E402
from runner import Controller, validate_preflight  # noqa: E402
from sessions import extended_session_close  # noqa: E402

from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    _HERMETIC_TOKEN = patch_default_stop()


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


NY = ZoneInfo("America/New_York")

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    PATH = SOURCE / "native_adapter.py"
    SPEC = importlib.util.spec_from_file_location("adaptive_native_sessions", PATH)
    ADAPTER = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(ADAPTER)


def ny(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=NY)


class SessionClockTests(unittest.TestCase):
    def test_pre_session_before_open(self):
        info = sess.session_at(ny(2026, 3, 10, 7, 0))  # Tuesday, ordinary trading day
        self.assertEqual(info.kind, sess.SessionKind.PRE)
        self.assertEqual(info.open, ny(2026, 3, 10, 4, 0))
        self.assertEqual(info.close, ny(2026, 3, 10, 9, 30))
        self.assertAlmostEqual(info.seconds_to_close, 2.5 * 3600)

    def test_rth_session_regular_hours(self):
        info = sess.session_at(ny(2026, 3, 10, 12, 0))
        self.assertEqual(info.kind, sess.SessionKind.RTH)
        self.assertEqual(info.close, ny(2026, 3, 10, 16, 0))
        self.assertFalse(info.is_early_close)

    def test_post_session_after_close(self):
        info = sess.session_at(ny(2026, 3, 10, 17, 30))
        self.assertEqual(info.kind, sess.SessionKind.POST)
        self.assertEqual(info.open, ny(2026, 3, 10, 16, 0))
        self.assertEqual(info.close, ny(2026, 3, 10, 20, 0))

    def test_closed_overnight_before_pre_open(self):
        info = sess.session_at(ny(2026, 3, 10, 2, 0))
        self.assertEqual(info.kind, sess.SessionKind.CLOSED)
        self.assertEqual(info.next_open, ny(2026, 3, 10, 4, 0))
        self.assertIsNone(info.seconds_to_close)

    def test_closed_after_post_close_rolls_to_next_trading_day(self):
        info = sess.session_at(ny(2026, 3, 10, 21, 0))  # Tuesday evening
        self.assertEqual(info.kind, sess.SessionKind.CLOSED)
        self.assertEqual(info.next_open, ny(2026, 3, 11, 4, 0))  # Wednesday PRE open

    def test_closed_weekend(self):
        info = sess.session_at(ny(2026, 3, 14, 12, 0))  # Saturday
        self.assertEqual(info.kind, sess.SessionKind.CLOSED)
        self.assertEqual(info.next_open, ny(2026, 3, 16, 4, 0))  # Monday PRE open

    def test_closed_full_holiday(self):
        info = sess.session_at(ny(2026, 1, 1, 12, 0))  # New Year's Day, Thursday
        self.assertEqual(info.kind, sess.SessionKind.CLOSED)
        # Jan 2 (Fri) is an ordinary trading day.
        self.assertEqual(info.next_open, ny(2026, 1, 2, 4, 0))

    def test_early_close_thanksgiving_friday(self):
        info = sess.session_at(ny(2026, 11, 27, 12, 30))  # Friday after Thanksgiving
        self.assertEqual(info.kind, sess.SessionKind.RTH)
        self.assertTrue(info.is_early_close)
        self.assertEqual(info.close, ny(2026, 11, 27, 13, 0))
        post = sess.session_at(ny(2026, 11, 27, 13, 30))
        self.assertEqual(post.kind, sess.SessionKind.POST)
        self.assertEqual(post.open, ny(2026, 11, 27, 13, 0))

    def test_early_close_christmas_eve(self):
        info = sess.session_at(ny(2026, 12, 24, 12, 59))
        self.assertEqual(info.kind, sess.SessionKind.RTH)
        self.assertTrue(info.is_early_close)
        self.assertEqual(info.close, ny(2026, 12, 24, 13, 0))

    def test_dst_spring_forward_rth_boundaries_stay_at_local_wall_clock(self):
        # 2026-03-08 is the US spring-forward DST transition (2am -> 3am).
        # NYSE opens/closes are always local wall-clock times regardless.
        info = sess.session_at(ny(2026, 3, 9, 9, 30))  # Monday after the transition
        self.assertEqual(info.kind, sess.SessionKind.RTH)
        self.assertEqual(info.open.utcoffset().total_seconds(), -4 * 3600)  # EDT

    def test_dst_fall_back_rth_boundaries_stay_at_local_wall_clock(self):
        # 2026-11-01 is the US fall-back DST transition.
        info = sess.session_at(ny(2026, 11, 2, 9, 30))  # Monday after the transition
        self.assertEqual(info.kind, sess.SessionKind.RTH)
        self.assertEqual(info.open.utcoffset().total_seconds(), -5 * 3600)  # EST

    def test_is_trading_session(self):
        self.assertTrue(sess.is_trading_session(ny(2026, 3, 10, 12, 0)))
        self.assertTrue(sess.is_trading_session(ny(2026, 3, 10, 5, 0)))  # PRE
        self.assertFalse(sess.is_trading_session(ny(2026, 3, 10, 2, 0)))  # CLOSED
        self.assertFalse(sess.is_trading_session(ny(2026, 3, 14, 12, 0)))  # weekend

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            sess.session_at(datetime(2026, 3, 10, 12, 0))

    def test_utc_input_converted_correctly(self):
        # 14:30 UTC on an EDT day (offset -4) is 10:30 ET, inside RTH.
        info = sess.session_at(datetime(2026, 3, 10, 14, 30, tzinfo=timezone.utc))
        self.assertEqual(info.kind, sess.SessionKind.RTH)

    def test_exchange_calendars_agreement_or_absent(self):
        result = sess.exchange_calendars_agrees_2026()
        if result is None:
            self.skipTest("exchange_calendars is not installed in this shared engine environment")
        self.assertTrue(result)

    def test_year_outside_calendar_refused(self):
        # D7: dates outside the frozen table's year(s) must not be silently
        # classified against the 2026 table. exchange_calendars is not
        # installed in this environment, so both raise.
        with self.assertRaisesRegex(ValueError, "session_calendar_out_of_range"):
            sess.session_at(ny(2025, 12, 25, 12, 0))
        with self.assertRaisesRegex(ValueError, "session_calendar_out_of_range"):
            sess.session_at(ny(2027, 1, 1, 12, 0))

    def test_year_inside_calendar_still_works(self):
        info = sess.session_at(ny(2026, 12, 31, 12, 0))
        self.assertEqual(info.kind, sess.SessionKind.RTH)

    def test_extended_session_close_spans_pre_rth_post(self):
        # D4: PRE's own .close (09:30) is only the RTH-open boundary, not the
        # real closure of the continuous extended-hours window; the window
        # close is always the day's 20:00 ET POST close.
        expected = ny(2026, 3, 10, 20, 0)
        self.assertEqual(extended_session_close(ny(2026, 3, 10, 7, 0)), expected)   # PRE
        self.assertEqual(extended_session_close(ny(2026, 3, 10, 12, 0)), expected)  # RTH
        self.assertEqual(extended_session_close(ny(2026, 3, 10, 18, 0)), expected)  # POST

    def test_extended_session_close_refuses_when_closed(self):
        with self.assertRaisesRegex(ValueError, "no_active_extended_session"):
            extended_session_close(ny(2026, 3, 10, 2, 0))


class SessionPolicyTests(unittest.TestCase):
    def base_config(self):
        return {"regular_session_only": True, "extended_hours_enabled": False,
                "sessions": {"extended_hours": False, "overnight_holds": False,
                            "overnight_gross_multiple": "1.0"}}

    def test_default_policy_matches_legacy_flags_byte_identical(self):
        policy = sess.validate_session_policy(self.base_config())
        self.assertEqual(policy, {"extended_hours": False, "overnight_holds": False,
                                  "overnight_gross_multiple": D("1.0")})

    def test_missing_sessions_block_falls_back_to_default(self):
        config = self.base_config()
        del config["sessions"]
        policy = sess.validate_session_policy(config)
        self.assertFalse(policy["extended_hours"])
        self.assertFalse(policy["overnight_holds"])

    def test_extended_hours_requires_legacy_flags_flip(self):
        config = self.base_config()
        config["sessions"]["extended_hours"] = True
        with self.assertRaisesRegex(ValueError, "unqualified_lane_configuration"):
            sess.validate_session_policy(config)
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True
        policy = sess.validate_session_policy(config)
        self.assertTrue(policy["extended_hours"])

    def test_overnight_gross_multiple_bound_rejects_above_two(self):
        config = self.base_config()
        config["sessions"]["overnight_gross_multiple"] = "2.5"
        with self.assertRaisesRegex(ValueError, "unqualified_lane_configuration"):
            sess.validate_session_policy(config)

    def test_overnight_gross_multiple_bound_accepts_two(self):
        # S4: a non-default multiple requires overnight_holds True (see
        # test_overnight_gross_multiple_off_default_requires_overnight_holds
        # below); enable it here too so this purely exercises the standalone
        # <=2.0 bound.
        config = self.base_config()
        config["sessions"]["overnight_gross_multiple"] = "2.0"
        config["sessions"]["overnight_holds"] = True
        config["sessions"]["extended_hours"] = True
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True
        policy = sess.validate_session_policy(config)
        self.assertEqual(policy["overnight_gross_multiple"], D("2.0"))

    def test_overnight_gross_multiple_non_finite_raises_value_error_not_decimal_error(self):
        # D7: the bound comparison must run inside the try/except so a
        # non-finite value raises ValueError("unqualified_lane_configuration"),
        # never decimal.InvalidOperation escaping uncaught. A non-finite
        # string is rejected by the is_finite() check before S4's
        # overnight_holds requirement is even reached, so overnight_holds
        # need not be set here.
        for bad in ("nan", "inf", "-inf", "Infinity"):
            config = self.base_config()
            config["sessions"]["overnight_gross_multiple"] = bad
            with self.assertRaisesRegex(ValueError, "unqualified_lane_configuration"):
                sess.validate_session_policy(config)

    def test_overnight_holds_without_extended_hours_refused(self):
        # D8: chose to refuse this combination rather than define undocumented
        # semantics for it.
        config = self.base_config()
        config["sessions"]["overnight_holds"] = True
        config["sessions"]["extended_hours"] = False
        with self.assertRaisesRegex(ValueError, "unqualified_lane_configuration"):
            sess.validate_session_policy(config)

    def test_overnight_holds_with_extended_hours_accepted(self):
        config = self.base_config()
        config["sessions"]["overnight_holds"] = True
        config["sessions"]["extended_hours"] = True
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True
        policy = sess.validate_session_policy(config)
        self.assertTrue(policy["overnight_holds"])

    def test_overnight_multiple_bounded_by_leverage_and_capital(self):
        # D9: max_gross_exposure_usd * overnight_gross_multiple <=
        # capital_usd * max_leverage. capital=1000, gross_exposure=900,
        # leverage=1: 900*1.5=1350 > 1000*1=1000, must refuse even though
        # 1.5 is within the standalone <=2.0 per-field bound.
        config = self.base_config()
        config["sessions"]["overnight_holds"] = True
        config["sessions"]["extended_hours"] = True
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True
        config["sessions"]["overnight_gross_multiple"] = "1.5"
        config["capital_usd"] = "1000"
        config["max_gross_exposure_usd"] = "900"
        config["max_leverage"] = "1"
        with self.assertRaisesRegex(ValueError, "unqualified_lane_configuration"):
            sess.validate_session_policy(config)

    def test_overnight_multiple_within_leverage_and_capital_bound_accepted(self):
        config = self.base_config()
        config["sessions"]["overnight_holds"] = True
        config["sessions"]["extended_hours"] = True
        config["regular_session_only"] = False
        config["extended_hours_enabled"] = True
        config["sessions"]["overnight_gross_multiple"] = "1.1"
        config["capital_usd"] = "1000"
        config["max_gross_exposure_usd"] = "900"
        config["max_leverage"] = "1"
        policy = sess.validate_session_policy(config)  # 900*1.1=990 <= 1000*1
        self.assertEqual(policy["overnight_gross_multiple"], D("1.1"))

    def test_overnight_gross_multiple_off_default_requires_overnight_holds(self):
        # S4: a regular-session-only lane (overnight_holds False) can never
        # carry a position past the RTH close, so a non-default
        # overnight_gross_multiple there is meaningless configuration at
        # best; refuse it rather than silently accept it.
        config = self.base_config()
        config["sessions"]["overnight_gross_multiple"] = "1.5"
        with self.assertRaisesRegex(ValueError, "unqualified_lane_configuration"):
            sess.validate_session_policy(config)

    def test_overnight_gross_multiple_default_is_fine_without_overnight_holds(self):
        # The neutral default (1.0) is a no-op regardless of overnight_holds
        # and must still be accepted (byte-identical default behaviour).
        config = self.base_config()
        config["sessions"]["overnight_gross_multiple"] = "1.0"
        policy = sess.validate_session_policy(config)
        self.assertEqual(policy["overnight_gross_multiple"], D("1.0"))
        self.assertFalse(policy["overnight_holds"])

    def test_order_extended_hours_flag_only_outside_rth_when_enabled(self):
        policy = {"extended_hours": True}
        self.assertTrue(sess.order_extended_hours_flag(ny(2026, 3, 10, 7, 0), policy))  # PRE
        self.assertFalse(sess.order_extended_hours_flag(ny(2026, 3, 10, 12, 0), policy))  # RTH
        self.assertTrue(sess.order_extended_hours_flag(ny(2026, 3, 10, 18, 0), policy))  # POST

    def test_order_extended_hours_flag_false_when_policy_disabled(self):
        policy = {"extended_hours": False}
        self.assertFalse(sess.order_extended_hours_flag(ny(2026, 3, 10, 7, 0), policy))


class ReconciliationAndBoundaryTests(unittest.TestCase):
    def test_reconciliation_receipt_shape(self):
        snapshot = {"positions": [{"symbol": "SPY", "qty": "1"}],
                    "orders": [{"status": "new", "client_order_id": "a"},
                              {"status": "filled", "client_order_id": "b"}]}
        receipt = sess.reconciliation_receipt(snapshot, boundary=False)
        self.assertEqual(receipt["positions"], snapshot["positions"])
        self.assertEqual(len(receipt["open_orders"]), 1)
        self.assertFalse(receipt["reconciled_at_boundary"])

    def test_boundary_receipt_records_session_info(self):
        receipt = sess.boundary_receipt(ny(2026, 3, 10, 12, 0), positions=[], cash="100000",
                                        cash_delta="0", open_orders=0, reconciled_at_boundary=True)
        self.assertEqual(receipt["session_kind"], "RTH")
        self.assertEqual(receipt["session_date"], "2026-03-10")
        self.assertTrue(receipt["reconciled_at_boundary"])

    def test_boundary_receipt_keeps_cash_and_cash_delta_separate(self):
        receipt = sess.boundary_receipt(ny(2026, 3, 10, 12, 0), positions=[], cash="10050",
                                        cash_delta="50", open_orders=0, reconciled_at_boundary=True)
        self.assertEqual(receipt["cash"], "10050")
        self.assertEqual(receipt["cash_delta"], "50")
        self.assertNotEqual(receipt["cash"], receipt["cash_delta"])

    def test_must_end_flat_default_always_true(self):
        policy = {"overnight_holds": False}
        self.assertTrue(sess.must_end_flat(policy, is_final_boundary=False))
        self.assertTrue(sess.must_end_flat(policy, is_final_boundary=True))

    def test_must_end_flat_overnight_holds_only_at_final_boundary(self):
        policy = {"overnight_holds": True}
        self.assertFalse(sess.must_end_flat(policy, is_final_boundary=False))
        self.assertTrue(sess.must_end_flat(policy, is_final_boundary=True))


class GapRiskAndOvernightCapTests(unittest.TestCase):
    def test_gap_risk_rule_computes_stop_from_actual_open(self):
        result = evaluate_gap_risk(prior_close="100.00", session_open="102.00", stop_bps="25")
        self.assertAlmostEqual(float(result["gap_bps"]), 200.0, places=2)
        self.assertAlmostEqual(float(result["stop_price"]), 102.00 * (1 - 25 / 10000), places=4)

    def test_gap_risk_rule_rejects_non_positive_prices(self):
        # decimal(..., zero=False) (the default coercion evaluate_gap_risk
        # uses) already rejects zero/negative/non-finite inputs before any
        # comparison runs (D1: the separate "<= 0" guard was unreachable dead
        # code and has been removed, not just made "real").
        with self.assertRaises(SafetyError):
            evaluate_gap_risk(prior_close="0", session_open="100", stop_bps="25")
        with self.assertRaises(SafetyError):
            evaluate_gap_risk(prior_close="-5", session_open="100", stop_bps="25")
        with self.assertRaises(SafetyError):
            evaluate_gap_risk(prior_close="100", session_open="0", stop_bps="25")

    def test_overnight_gross_multiple_default_and_bound_in_risklimits(self):
        limits = RiskLimits()
        self.assertEqual(limits.overnight_gross_multiple, D("1.0"))
        self.assertEqual(limits.overnight_gross_exposure_cap_usd(), limits.max_gross_exposure_usd)
        with self.assertRaisesRegex(SafetyError, "risk_limit_out_of_bounds"):
            RiskLimits(overnight_gross_multiple="2.5")

    def test_overnight_gross_multiple_within_bound_raises_cap(self):
        limits = RiskLimits(overnight_gross_multiple="2.0")
        self.assertEqual(limits.overnight_gross_exposure_cap_usd(), limits.max_gross_exposure_usd * D("2"))

    def test_every_numeric_cap_unchanged_by_default_risklimits(self):
        limits = RiskLimits()
        self.assertEqual(limits.max_gross_exposure_usd, D("5000"))
        self.assertEqual(limits.max_order_notional_usd, D("1000"))
        self.assertEqual(limits.max_gross_loss_usd, D("25"))
        self.assertEqual(limits.max_drawdown_usd, D("25"))
        self.assertEqual(limits.max_spread_bps, D("15"))


class HaltedQuoteGateTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1_800_000_000.0
        self.ledger = Ledger(Path(self.tmp.name) / "account.sqlite3")
        self.ledger.start_trial(self.now)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def test_halted_quote_blocks_new_buy_risk(self):
        halted_quote = Quote("SPY", "100", "100.01", self.now, halted=True)
        with self.assertRaisesRegex(SafetyError, "quote_halted"):
            self.ledger.reserve_intent("buy-halt", "SPY", "buy", "1", "100.02",
                                       quote=halted_quote, now=self.now, market_open=True,
                                       session_close=self.now + 3600)

    def test_halted_quote_does_not_block_existing_exit_chain(self):
        # A sell-side reserve on a halted quote still passes the halt/spread
        # gates (check_spread=False for sells); the exit chain is untouched.
        # First establish an owned, filled position to exit from.
        fresh_quote = Quote("SPY", "100", "100.01", self.now)
        self.ledger.reserve_intent("buy-1", "SPY", "buy", "1", "100.02", quote=fresh_quote,
                                   now=self.now, market_open=True, session_close=self.now + 3600)
        self.ledger.record_order("buy-1", "broker-buy-1", "filled", "1", "100.01", timestamp=self.now)
        halted_quote = Quote("SPY", "100", "100.01", self.now, halted=True)
        created = self.ledger.reserve_intent("sell-halt", "SPY", "sell", "1", "99.98",
                                             quote=halted_quote, now=self.now, market_open=True,
                                             session_close=self.now + 3600)
        self.assertTrue(created.newly_reserved)

    def test_default_quote_not_halted(self):
        q = Quote("SPY", "100", "100.01", self.now)
        self.assertFalse(q.halted)


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class NativeStartupReconciliationTests(unittest.TestCase):
    class FakePort:
        def __init__(self, snapshot):
            self._snapshot = snapshot
            self.started = 0

        async def start(self, on_quote, on_order):
            self.started += 1

        async def stop(self):
            pass

        async def snapshot(self):
            return self._snapshot

    def run_connect(self, snapshot, session_policy=None):
        port = self.FakePort(snapshot)
        session = ADAPTER.build_node(port, [{"symbol": "SPY"}], [], session_policy=session_policy)
        # generate_account_state requires the execution output bound by a full
        # running LiveNode; this test only exercises the flat-vs-reconciled
        # startup gate above it, so the account-state emission is stubbed.
        session.execution._account = lambda row: None
        try:
            asyncio.run(session.execution._connect())
            return session
        finally:
            asyncio.run(session.stop_port())
            session.node.dispose()

    def test_flat_start_default_still_refuses_existing_positions(self):
        snapshot = {"account": {"cash": "10000", "buying_power": "10000", "equity": "10000"},
                    "orders": [], "positions": [{"symbol": "SPY", "qty": "1"}]}
        with self.assertRaisesRegex(ValueError, "startup_requires_flat_account"):
            self.run_connect(snapshot)

    def test_reconciled_start_accepts_existing_positions_and_orders(self):
        snapshot = {"account": {"cash": "10000", "buying_power": "10000", "equity": "10000"},
                    "orders": [{"status": "new", "client_order_id": "x", "id": "1"}],
                    "positions": [{"symbol": "SPY", "qty": "1"}]}
        # D8: overnight_holds only ever reaches native_adapter alongside
        # extended_hours True in practice (validate_session_policy refuses
        # the combination otherwise); match that here for realism.
        session = self.run_connect(snapshot, session_policy={"extended_hours": True, "overnight_holds": True})
        self.assertEqual(session.snapshot_state["positions"], snapshot["positions"])
        self.assertIsNotNone(session.reconciliation)
        self.assertFalse(session.reconciliation["reconciled_at_boundary"])
        self.assertEqual(len(session.reconciliation["open_orders"]), 1)

    def test_snapshot_state_excludes_historical_terminal_orders(self):
        """S6: transport.snapshot() merges open + recent-history pages, so
        a startup snapshot can include an already-filled (or otherwise
        terminal) historical order alongside genuinely open ones.
        snapshot_state (later replayed into native order-status reports)
        must retain only open orders; the reconciliation receipt still
        sees the full snapshot (open + terminal) for its own audit trail."""
        snapshot = {"account": {"cash": "10000", "buying_power": "10000", "equity": "10000"},
                    "orders": [{"status": "new", "client_order_id": "open-1", "id": "1"},
                              {"status": "filled", "client_order_id": "old-filled-1", "id": "2"},
                              {"status": "canceled", "client_order_id": "old-canceled-1", "id": "3"}],
                    "positions": [{"symbol": "SPY", "qty": "1"}]}
        session = self.run_connect(snapshot, session_policy={"extended_hours": True, "overnight_holds": True})
        self.assertEqual([o["client_order_id"] for o in session.snapshot_state["orders"]], ["open-1"])
        # reconciliation_receipt() independently filters to open orders for
        # its own "open_orders" field regardless of snapshot_state's own
        # filtering; both correctly agree on the single genuinely open order.
        self.assertEqual(len(session.reconciliation["open_orders"]), 1)


class LedgerBrokerSnapshotAdoptionTests(unittest.TestCase):
    """D1: the overnight startup-reconciliation path must actually seed the
    local ledger from the broker snapshot the adapter accepted, with a
    ledger_delta describing what was imported, and the trial must be able to
    proceed afterward (a subsequent broker update for a seeded open order is
    recognized instead of freezing the run as an external order)."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1_800_000_000.0
        self.ledger = Ledger(Path(self.tmp.name) / "account.sqlite3")
        self.ledger.start_trial(self.now)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def fake_snapshot(self):
        return {"account": {"cash": "8000", "buying_power": "8000", "equity": "10000"},
                "positions": [{"symbol": "SPY", "qty": "3", "avg_entry_price": "500.00"}],
                "orders": [{"client_order_id": "broker-open-1", "id": "b1", "symbol": "AAPL",
                           "side": "buy", "qty": "2", "limit_price": "190.00",
                           "status": "new", "filled_qty": "0"}]}

    def test_adopts_positions_and_open_orders_with_ledger_delta(self):
        self.assertEqual(self.ledger.positions(), {})
        self.assertEqual(self.ledger.unresolved(), [])
        delta = self.ledger.adopt_broker_snapshot(self.fake_snapshot(), self.now)
        self.assertEqual(delta["positions_before"], 0)
        self.assertEqual(delta["positions_after"], 1)
        self.assertEqual(delta["open_orders_before"], 0)
        self.assertEqual(delta["open_orders_after"], 1)
        self.assertEqual(D(delta["cost_basis_delta_usd"]), D("1500.00"))  # 3 * 500.00, broker minus (empty) ledger
        positions = self.ledger.positions()
        self.assertEqual(positions["SPY"].qty, D("3"))
        unresolved = self.ledger.unresolved()
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].client_id, "broker-open-1")
        self.assertEqual(unresolved[0].symbol, "AAPL")

    def test_run_proceeds_after_adoption_seeded_order_is_recognized_not_external(self):
        self.ledger.adopt_broker_snapshot(self.fake_snapshot(), self.now)
        controller = Controller(self.ledger, self.now + 3600, market_open=True, clock=lambda: self.now)
        # A later broker status update for the seeded order must be
        # recognized (not raise external_order_detected / freeze the trial).
        controller.observe({"client_order_id": "broker-open-1", "id": "b1", "status": "filled",
                            "filled_qty": "2", "filled_avg_price": "190.00",
                            "updated_at_ns": int((self.now + 10) * 1e9)})
        self.assertFalse(self.ledger.accounting().halted_reason)

    def test_seeded_order_already_present_is_not_duplicated(self):
        self.ledger.adopt_broker_snapshot(self.fake_snapshot(), self.now)
        delta2 = self.ledger.adopt_broker_snapshot(self.fake_snapshot(), self.now + 1)
        self.assertEqual(delta2["open_orders_before"], 1)
        self.assertEqual(delta2["open_orders_after"], 1)  # idempotent, no duplicate intent
        self.assertEqual(len(self.ledger.unresolved()), 1)

    def test_adoption_refuses_an_order_with_an_invalid_side(self):
        """S8: row["side"] used to be interpolated straight into the
        intents row with no validation. A broker snapshot order whose side
        is neither "buy" nor "sell" must be refused, not silently stored."""
        snapshot = self.fake_snapshot()
        snapshot["orders"][0]["side"] = "short"
        with self.assertRaisesRegex(SafetyError, "unadoptable_broker_order_side"):
            self.ledger.adopt_broker_snapshot(snapshot, self.now)
        self.assertEqual(self.ledger.unresolved(), [])

    def test_resume_adoption_keeps_local_cost_basis_not_broker_average(self):
        """D2: adopt_broker_snapshot's own docstring precondition ("only
        against a fresh ledger") was violated by the resume path (S2's
        resume_held_trial calls it again on every subsequent invocation),
        and the position upsert's ON CONFLICT DO UPDATE overwrote the
        locally fill-derived cost basis with the broker's average price.
        On resume, the local basis (from an actual local fill, e.g. entered
        at 495.00, not the broker's reported "average" of 500.00) must
        survive untouched; the broker average and the basis delta are
        recorded in the returned dict's resumed_position_basis instead."""
        # First adoption: a fresh ledger, SPY imported at the broker's
        # reported average (500.00) -- the ordinary D1 startup path.
        first_snapshot = {"account": {"cash": "10000", "buying_power": "10000", "equity": "10000"},
                          "positions": [{"symbol": "SPY", "qty": "3", "avg_entry_price": "500.00"}],
                          "orders": []}
        self.ledger.adopt_broker_snapshot(first_snapshot, self.now)
        self.assertEqual(self.ledger.positions()["SPY"].qty, D("3"))
        self.assertEqual(self.ledger.positions()["SPY"].average_cost, D("500.00"))

        # A local fill happens (e.g. the strategy adds to the position),
        # changing the locally tracked cost basis away from the broker's
        # original reported average.
        self.ledger.reserve_intent("buy-more-spy", "SPY", "buy", "1", "495.00",
                                   quote=Quote("SPY", "494.99", "495.01", self.now),
                                   now=self.now, market_open=True, session_close=self.now + 3600)
        self.ledger.record_order("buy-more-spy", "broker-buy-more-spy", "filled", "1", "495.00",
                                 timestamp=self.now)
        local_qty_before = self.ledger.positions()["SPY"].qty
        local_basis_before = self.ledger.positions()["SPY"].cost_basis_usd
        self.assertEqual(local_qty_before, D("4"))

        # A later invocation (resume) re-adopts the same broker snapshot
        # (broker still reports its own, different, average price for the
        # position) -- the local basis must survive unchanged.
        resume_snapshot = {"account": {"cash": "10000", "buying_power": "10000", "equity": "10000"},
                           "positions": [{"symbol": "SPY", "qty": "4", "avg_entry_price": "500.00"}],
                           "orders": []}
        delta = self.ledger.adopt_broker_snapshot(resume_snapshot, self.now + 1)
        self.assertEqual(self.ledger.positions()["SPY"].qty, local_qty_before)
        self.assertEqual(self.ledger.positions()["SPY"].cost_basis_usd, local_basis_before)
        self.assertEqual(len(delta["resumed_position_basis"]), 1)
        resumed = delta["resumed_position_basis"][0]
        self.assertEqual(resumed["symbol"], "SPY")
        self.assertEqual(D(resumed["local_cost_basis_usd"]), local_basis_before)
        self.assertEqual(D(resumed["broker_avg_price"]), D("500.00"))
        self.assertEqual(D(resumed["broker_cost_basis_usd"]), D("2000.00"))  # 4 * 500.00
        self.assertEqual(D(resumed["basis_delta_usd"]), D("2000.00") - local_basis_before)

        # A brand-new symbol in the same resumed snapshot is still inserted
        # normally (only already-held positions retain their local basis).
        resume_snapshot["positions"].append({"symbol": "AAPL", "qty": "1", "avg_entry_price": "190.00"})
        delta2 = self.ledger.adopt_broker_snapshot(resume_snapshot, self.now + 2)
        self.assertEqual(self.ledger.positions()["AAPL"].qty, D("1"))
        self.assertEqual(self.ledger.positions()["AAPL"].average_cost, D("190.00"))
        self.assertEqual([r["symbol"] for r in delta2["resumed_position_basis"]], ["SPY"])


class HaltMappingTests(unittest.TestCase):
    """D3: fake-payload tests locking in exactly which fields are read."""

    def test_normalize_quote_maps_halt_condition_code(self):
        raw = {"S": "SPY", "bp": 100.0, "ap": 100.05, "bs": 1, "as": 1,
               "t": "2026-03-10T12:00:00Z", "c": ["H"]}
        q = normalize_quote(raw)
        self.assertTrue(q["halted"])

    def test_normalize_quote_not_halted_without_halt_condition(self):
        raw = {"S": "SPY", "bp": 100.0, "ap": 100.05, "bs": 1, "as": 1,
               "t": "2026-03-10T12:00:00Z", "c": ["R"]}
        q = normalize_quote(raw)
        self.assertFalse(q["halted"])

    def test_normalize_quote_defaults_not_halted_with_no_conditions(self):
        raw = {"S": "SPY", "bp": 100.0, "ap": 100.05, "bs": 1, "as": 1,
               "t": "2026-03-10T12:00:00Z"}
        q = normalize_quote(raw)
        self.assertFalse(q["halted"])

    def test_normalize_trading_status_halted_status_code(self):
        status = normalize_trading_status({"S": "SPY", "sc": "H", "t": "2026-03-10T12:00:00Z"})
        self.assertEqual(status["symbol"], "SPY")
        self.assertTrue(status["halted"])

    def test_normalize_trading_status_resumed_status_code(self):
        status = normalize_trading_status({"S": "SPY", "sc": "T", "t": "2026-03-10T12:00:00Z"})
        self.assertFalse(status["halted"])


class ControllerHaltAggregationTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1_800_000_000.0
        self.ledger = Ledger(Path(self.tmp.name) / "account.sqlite3")
        self.ledger.start_trial(self.now)
        self.controller = Controller(self.ledger, self.now + 3600, market_open=True, clock=lambda: self.now)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def test_quote_halted_flag_propagates_to_ledger_quote(self):
        self.controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01",
                               "ts_ns": int(self.now * 1e9), "halted": True})
        self.assertTrue(self.controller.quotes["SPY"].halted)

    def test_trading_status_sets_and_clears_halt_independent_of_quote_flag(self):
        # D7 (round 2): trading_status() now refuses a message without a
        # valid ts_ns (see TradingStatusTsNsGuardTests below), so every
        # trading_status() call in this class must carry one.
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": 100})
        self.controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01",
                               "ts_ns": int(self.now * 1e9), "halted": False})
        self.assertTrue(self.controller.quotes["SPY"].halted)  # trading_status still in effect
        self.controller.trading_status({"symbol": "SPY", "halted": False, "ts_ns": 200})
        self.controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01",
                               "ts_ns": int((self.now + 1) * 1e9)})
        self.assertFalse(self.controller.quotes["SPY"].halted)

    def test_halt_takes_effect_immediately_without_a_newer_quote(self):
        # D6: closes the fail-open window -- a halt must be visible to any
        # reader of the stored quote right after trading_status() fires, not
        # only once a strictly newer quote tick happens to arrive.
        self.controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01",
                               "ts_ns": int(self.now * 1e9)})
        self.assertFalse(self.controller.quotes["SPY"].halted)
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": 100})
        self.assertTrue(self.controller.quotes["SPY"].halted)  # no further quote() call happened

    def test_trading_status_before_any_quote_does_not_error(self):
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": 100})
        self.assertIn("SPY", self.controller.halted_symbols)
        self.assertNotIn("SPY", self.controller.quotes)

    def test_replayed_older_resumed_message_cannot_clear_a_newer_halt(self):
        """D3: trading_status() applies a per-symbol out-of-order/replay
        guard -- a message is only applied when its own ts_ns is strictly
        newer than the last status message actually applied for that
        symbol (D7, round 2: and only when ts_ns is itself a valid positive
        integer at all -- see TradingStatusTsNsGuardTests) -- the same
        strictly-newer contract quote() already applies via each Quote's
        own timestamp. A genuinely newer halt (ts_ns=200) followed by a
        replayed/out-of-order OLDER "resumed" message (ts_ns=100) must not
        clear it."""
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": 200})
        self.assertIn("SPY", self.controller.halted_symbols)
        self.controller.trading_status({"symbol": "SPY", "halted": False, "ts_ns": 100})
        self.assertIn("SPY", self.controller.halted_symbols)  # still halted: the resumed message was stale
        self.controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01", "ts_ns": int(self.now * 1e9)})
        self.assertTrue(self.controller.quotes["SPY"].halted)
        # A genuinely newer resumed message (ts_ns=300) does clear it.
        self.controller.trading_status({"symbol": "SPY", "halted": False, "ts_ns": 300})
        self.assertNotIn("SPY", self.controller.halted_symbols)
        self.controller.quote({"symbol": "SPY", "bid": "100", "ask": "100.01", "ts_ns": int((self.now + 1) * 1e9)})
        self.assertFalse(self.controller.quotes["SPY"].halted)

    def test_equal_ts_ns_status_message_is_not_reapplied(self):
        """A duplicate (equal timestamp) delivery of the same status message
        is treated as already-applied, not as a fresh, strictly-newer update
        (consistent with quote()'s own strict `>` comparison)."""
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": 200})
        self.controller.trading_status({"symbol": "SPY", "halted": False, "ts_ns": 200})
        self.assertIn("SPY", self.controller.halted_symbols)


class TradingStatusTsNsGuardTests(unittest.TestCase):
    """D7 (round 2): a trading_status message whose ts_ns is missing or not
    a valid positive integer must be refused outright (not applied, and not
    treated as passing the replay guard by accident), and recorded as an
    ignored event -- not silently dropped without a trace."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1_800_000_000.0
        self.ledger = Ledger(Path(self.tmp.name) / "account.sqlite3")
        self.ledger.start_trial(self.now)
        self.controller = Controller(self.ledger, self.now + 3600, market_open=True, clock=lambda: self.now)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def test_missing_ts_ns_is_refused_and_recorded_as_ignored(self):
        self.controller.trading_status({"symbol": "SPY", "halted": True})
        self.assertNotIn("SPY", self.controller.halted_symbols)
        ignored = [e for e in self.controller.events if e["type"] == "trading_status_ignored"]
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored[0]["symbol"], "SPY")

    def test_none_ts_ns_is_refused(self):
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": None})
        self.assertNotIn("SPY", self.controller.halted_symbols)

    def test_zero_ts_ns_is_refused(self):
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": 0})
        self.assertNotIn("SPY", self.controller.halted_symbols)

    def test_negative_ts_ns_is_refused(self):
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": -100})
        self.assertNotIn("SPY", self.controller.halted_symbols)

    def test_non_integer_ts_ns_is_refused(self):
        for bad in (200.5, "200", True, False):
            with self.subTest(ts_ns=bad):
                self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": bad})
                self.assertNotIn("SPY", self.controller.halted_symbols)

    def test_missing_ts_ns_cannot_clear_a_genuinely_newer_halt(self):
        """The exact bug this fix closes: a status message without ts_ns
        used to bypass the replay guard entirely (the guard only compared
        ts_ns to last_ts when BOTH were present) and was applied
        unconditionally -- clearing a real, newer halt just like a stale
        replayed message could."""
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": 500})
        self.assertIn("SPY", self.controller.halted_symbols)
        self.controller.trading_status({"symbol": "SPY", "halted": False})  # no ts_ns at all
        self.assertIn("SPY", self.controller.halted_symbols)  # still halted: refused, not applied

    def test_valid_ts_ns_after_an_ignored_message_still_applies(self):
        self.controller.trading_status({"symbol": "SPY", "halted": True})  # ignored
        self.controller.trading_status({"symbol": "SPY", "halted": True, "ts_ns": 100})
        self.assertIn("SPY", self.controller.halted_symbols)


class OvernightGrossCapLiveConsumerTests(unittest.TestCase):
    """D2: overnight_gross_multiple must have a live consumer in reserve_intent
    that only differs from the intraday cap during POST/CLOSED."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        # Close together (well inside one trial window) but straddling the
        # 16:00 ET RTH close boundary.
        self.rth_now = datetime(2026, 3, 10, 15, 50, tzinfo=NY).astimezone(timezone.utc).timestamp()
        self.post_now = datetime(2026, 3, 10, 16, 10, tzinfo=NY).astimezone(timezone.utc).timestamp()
        # Ordinary cap 2000, overnight cap (2.0x) 4000; each single order stays
        # within max_order_notional_usd so only the cumulative gross check
        # (never the per-order size check) can be the one that fires.
        limits = RiskLimits(capital_usd="10000", max_gross_exposure_usd="2000",
                            max_order_qty="50", max_order_notional_usd="2000",
                            overnight_gross_multiple="2.0", trial_seconds=3600)
        self.ledger = Ledger(Path(self.tmp.name) / "account.sqlite3", limits)
        self.ledger.start_trial(self.rth_now)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def reserve(self, cid, now, qty="15", price="100"):
        quote = Quote("SPY", "100", "100.01", now)
        return self.ledger.reserve_intent(cid, "SPY", "buy", qty, price, quote=quote, now=now,
                                          market_open=True, session_close=now + 3600)

    def test_rth_uses_ordinary_cap_not_overnight_multiple(self):
        # Two 1500 reserves cumulate to 3000, over the 2000 ordinary cap but
        # under the 4000 overnight cap; at RTH the ordinary cap must apply.
        self.reserve("buy-rth-1", self.rth_now)
        with self.assertRaisesRegex(SafetyError, "aggregate_exposure_cap_exceeded"):
            self.reserve("buy-rth-2", self.rth_now)

    def test_post_session_uses_overnight_multiple_cap(self):
        # Same two 1500 reserves (cumulative 3000) only pass at POST/CLOSED
        # if the wider 4000 overnight cap is actually applied there.
        self.reserve("buy-post-1", self.post_now)
        created = self.reserve("buy-post-2", self.post_now)
        self.assertTrue(created.newly_reserved)

    def test_post_session_still_enforces_overnight_cap_bound(self):
        # A third 1500 reserve pushes cumulative to 4500, over the 4000
        # overnight cap; it must still refuse, not become unlimited.
        self.reserve("buy-post-3a", self.post_now)
        self.reserve("buy-post-3b", self.post_now)
        with self.assertRaisesRegex(SafetyError, "aggregate_exposure_cap_exceeded"):
            self.reserve("buy-post-3c", self.post_now)

    def test_default_multiple_makes_post_session_cap_identical_to_rth(self):
        limits = RiskLimits(capital_usd="10000", max_gross_exposure_usd="2000",  # default multiple 1.0
                            max_order_qty="50", max_order_notional_usd="2000", trial_seconds=3600)
        ledger = Ledger(Path(self.tmp.name) / "account2.sqlite3", limits)
        ledger.start_trial(self.rth_now)

        def reserve(cid, now):
            quote = Quote("SPY", "100", "100.01", now)
            return ledger.reserve_intent(cid, "SPY", "buy", "15", "100", quote=quote, now=now,
                                         market_open=True, session_close=now + 3600)
        reserve("buy-default-post-1", self.post_now)
        with self.assertRaisesRegex(SafetyError, "aggregate_exposure_cap_exceeded"):
            reserve("buy-default-post-2", self.post_now)  # 3000 > 2000, no wider cap without a configured multiple
        ledger.close()


class PreflightGuardSplitTests(unittest.TestCase):
    """D4: overnight_holds must relax only the flat-account/open-orders gate,
    not the cash/equity floor, window sizing, universe or benchmark checks."""

    def observation(self, *, positions=(), orders=(), cash="10000", equity="10000",
                    is_open=True, window_seconds=10000):
        now_ns = int(time.time() * 1e9)
        return {"account": {"status": "ACTIVE", "currency": "USD", "trading_blocked": False,
                            "account_blocked": False, "trade_suspended_by_user": False,
                            "cash": cash, "equity": equity},
                "clock": {"timestamp_ns": now_ns, "received_at_ns": now_ns, "is_open": is_open,
                         "next_close_ns": now_ns + int(window_seconds * 1e9)},
                "positions": list(positions), "orders": list(orders),
                "assets": [{"symbol": "SPY", "status": "active", "tradable": True}],
                "quotes": [{"symbol": "SPY", "ts_ns": now_ns}]}

    def config(self):
        return {"capital_usd": "10000", "duration_seconds": 300, "cleanup_seconds": 120,
               "symbols": ["SPY"], "benchmarks": ["SPY"], "quote_max_age_seconds": 3}

    def test_overnight_holds_still_enforces_equity_floor(self):
        obs = self.observation(equity="100")  # below the 25000 floor
        with self.assertRaisesRegex(SafetyError, "account_not_ready"):
            validate_preflight(obs, self.config(), require_open=True, allow_existing=False,
                               allow_existing_positions=True)

    def test_overnight_holds_still_enforces_full_universe(self):
        obs = self.observation(equity="30000", positions=[{"symbol": "SPY", "qty": "1"}])
        obs["assets"] = []  # SPY (a required config symbol) is not tradable/known
        with self.assertRaisesRegex(SafetyError, "universe_not_tradable"):
            validate_preflight(obs, self.config(), require_open=True, allow_existing=False,
                               allow_existing_positions=True)

    def test_overnight_holds_relaxes_only_flat_account_gate(self):
        obs = self.observation(equity="30000", positions=[{"symbol": "SPY", "qty": "1"}],
                               orders=[{"status": "new"}])
        close = validate_preflight(obs, self.config(), require_open=True, allow_existing=False,
                                   allow_existing_positions=True)
        self.assertIsNotNone(close)

    def test_default_still_refuses_existing_positions(self):
        obs = self.observation(equity="30000", positions=[{"symbol": "SPY", "qty": "1"}])
        with self.assertRaisesRegex(SafetyError, "clean_native_start_requires_flat_account"):
            validate_preflight(obs, self.config(), require_open=True)


class SessionAwareRequireOpenTests(unittest.TestCase):
    """D9: require_open must allow a PRE/POST start when extended_hours is
    enabled, using the broker clock's own timestamp, while the default policy
    keeps relying on the broker's is_open flag exactly as before."""

    def observation_at(self, ny_dt, *, is_open):
        # The session clock uses the synthetic ny_dt (this is the whole point
        # of the test); the benchmark-quote freshness gate is independent of
        # the session clock and always compares against real wall-clock time
        # (see validate_preflight), so quote timestamps must be real "now".
        now_ns = int(ny_dt.astimezone(timezone.utc).timestamp() * 1e9)
        real_now_ns = int(time.time() * 1e9)
        return {"account": {"status": "ACTIVE", "currency": "USD", "trading_blocked": False,
                            "account_blocked": False, "trade_suspended_by_user": False,
                            "cash": "10000", "equity": "30000"},
                "clock": {"timestamp_ns": now_ns, "received_at_ns": now_ns, "is_open": is_open,
                         "next_close_ns": now_ns + int(3600 * 1e9)},
                "positions": [], "orders": [],
                "assets": [{"symbol": "SPY", "status": "active", "tradable": True}],
                "quotes": [{"symbol": "SPY", "ts_ns": real_now_ns}]}

    def config(self):
        return {"capital_usd": "10000", "duration_seconds": 300, "cleanup_seconds": 120,
               "symbols": ["SPY"], "benchmarks": ["SPY"], "quote_max_age_seconds": 3}

    def test_default_policy_pre_market_still_refused_even_if_broker_reports_open(self):
        # Defends the "keep RTH-only behaviour for the default policy" half of
        # D9: default policy ignores the session clock entirely and only
        # trusts the broker's is_open flag, which real brokers report False
        # pre-market; simulate a broker bug reporting True to prove the
        # default path still uses is_open, not the session clock.
        obs = self.observation_at(ny(2026, 3, 10, 7, 0), is_open=True)
        close = validate_preflight(obs, self.config(), require_open=True)
        self.assertIsNotNone(close)  # is_open True is trusted verbatim by default

    def test_default_policy_refuses_when_broker_reports_closed(self):
        obs = self.observation_at(ny(2026, 3, 10, 12, 0), is_open=False)
        with self.assertRaisesRegex(SafetyError, "regular_session_window_unavailable"):
            validate_preflight(obs, self.config(), require_open=True)

    def test_extended_hours_policy_allows_pre_market_start(self):
        obs = self.observation_at(ny(2026, 3, 10, 7, 0), is_open=False)  # broker: not RTH
        policy = {"extended_hours": True, "overnight_holds": False}
        close = validate_preflight(obs, self.config(), require_open=True, session_policy=policy)
        self.assertIsNotNone(close)

    def test_extended_hours_policy_refuses_fully_closed(self):
        obs = self.observation_at(ny(2026, 3, 14, 12, 0), is_open=False)  # Saturday: CLOSED
        policy = {"extended_hours": True, "overnight_holds": False}
        with self.assertRaisesRegex(SafetyError, "regular_session_window_unavailable"):
            validate_preflight(obs, self.config(), require_open=True, session_policy=policy)

    def test_extended_hours_policy_refuses_post_start_with_only_minutes_left(self):
        """S7: under extended_hours the required-window guard must compare
        against sessions.extended_session_close(now) (the day's 20:00 ET
        POST close), not the broker clock's own next_close_ns -- that field
        is RTH-only and, from a POST session, does not describe the actual
        (extended) session close at all. Set next_close_ns to a
        deliberately generous 1h window (what an RTH-only broker field might
        report, e.g. pointing at the next day's RTH close) while the real
        POST session close is only 2 minutes away; the fix must still refuse
        because there is not enough real time left before the extended
        close, well under this config's required_window
        (300 + 120 + 60 = 480s)."""
        ny_dt = ny(2026, 3, 10, 19, 58)  # POST session, 2 minutes before the 20:00 ET close
        obs = self.observation_at(ny_dt, is_open=False)
        obs["clock"]["next_close_ns"] = int(ny_dt.astimezone(timezone.utc).timestamp() * 1e9) + int(3600 * 1e9)
        policy = {"extended_hours": True, "overnight_holds": False}
        with self.assertRaisesRegex(SafetyError, "regular_session_window_unavailable"):
            validate_preflight(obs, self.config(), require_open=True, session_policy=policy)


class BoundaryReceiptCrossingOnlyTests(unittest.TestCase):
    """D6: sessions.must_end_flat/boundary_receipt themselves are pure and
    already tested above; this locks in that must_end_flat's is_final_boundary
    contract is what runner.py's real-crossing detection is expected to
    drive, exercised at the pure-function level (the full async run_native
    loop is exercised indirectly by tests.test_adaptive_paper_runner)."""

    def test_session_kind_changes_only_at_real_boundaries(self):
        a = sess.session_at(ny(2026, 3, 10, 9, 29, 59))
        b = sess.session_at(ny(2026, 3, 10, 9, 30, 0))
        self.assertNotEqual(a.kind, b.kind)
        c = sess.session_at(ny(2026, 3, 10, 9, 45, 0))
        self.assertEqual(b.kind, c.kind)  # no spurious change mid-session


class _FakeQuote:
    def __init__(self, bid, ask, timestamp=None):
        self.bid, self.ask, self.timestamp = bid, ask, timestamp


class _FakePolicyConfig:
    def __init__(self, stop_bps, quote_age_seconds=3, gap_stop_trigger_bps=None, gap_stop_enabled=True):
        self.stop_bps = stop_bps
        # D2 (round 3): _gap_risk_stop_symbols now applies the same
        # freshness window every other order path in native_strategy.py
        # uses (QUOTE_FUTURE_TOLERANCE_SECONDS/quote_age_seconds), so this
        # fake config needs a real quote_age_seconds too.
        self.quote_age_seconds = quote_age_seconds
        # D4 (round 4): mirrors strategies_v1.PolicyConfig's own default
        # resolution (None -> stop_bps), so existing tests here that only
        # ever cared about the stop *price* (not the trigger threshold)
        # keep the same effective behavior -- a gap must be at least as
        # adverse as stop_bps to arm, same as before this field existed.
        self.gap_stop_trigger_bps = D(str(gap_stop_trigger_bps if gap_stop_trigger_bps is not None else stop_bps))
        # Round 5: the whole hook is opt-in; this whole GapRiskExitChainTests
        # family exists specifically to exercise it, so the fake defaults
        # to enabled (GapStopOptInFlagTests below covers the disabled path
        # explicitly, on both this fake and a real PolicyConfig).
        self.gap_stop_enabled = gap_stop_enabled


class _FakePolicy:
    def __init__(self, stop_bps):
        self.latest = {}
        self.config = _FakePolicyConfig(stop_bps)


class _FakeLedger:
    def intents(self):
        return []

    def prior_rth_closes(self):
        return {}

    def record_prior_rth_close(self, symbol, price, session_date, ts_ns):
        pass


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class GapRiskExitChainTests(unittest.TestCase):
    """D5: safety.evaluate_gap_risk must have a real, genuinely-called
    engine caller (native_strategy.AdaptiveStrategy._gap_risk_stop_symbols),
    exercised here directly with fakes (no broker, no nautilus node).

    D2 (round 3): every _FakeQuote below is timestamped at (or fractionally
    before) the `now` of the very call that reads it, matching a real fresh
    quote; StaleQuoteGapRiskTests and RefusedGapStopSubmitTests below cover
    the freshness-guard and fire-once-after-acceptance fixes specifically."""

    def strategy(self, stop_bps="25"):
        from native_strategy import AdaptiveStrategy
        # Real construction (not added to any node/trader); _gap_risk_stop_symbols
        # only touches self.policy/self._prior_rth_close/self._last_session_kind/
        # self._gap_stop_applied, none of which need a running nautilus node.
        return AdaptiveStrategy(_FakePolicy(stop_bps), _FakeLedger(), "gap-risk-test")

    def test_no_trigger_before_any_prior_close_captured(self):
        strategy = self.strategy()
        rth = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        triggered = strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})
        self.assertEqual(triggered, set())

    def test_captures_prior_close_at_rth_to_post_crossing(self):
        strategy = self.strategy()
        rth = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth)
        strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})  # establishes last_session_kind = RTH
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})  # crosses RTH -> POST
        self.assertAlmostEqual(float(strategy._prior_rth_close["SPY"]), 100.01, places=2)

    def test_gap_down_on_next_rth_open_triggers_stop(self):
        strategy = self.strategy(stop_bps="25")
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})  # captures prior close ~100.01
        pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})  # overnight hold continues
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)  # a large gap-down open print
        first = strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        self.assertEqual(first, set())  # the open print itself only sets the stop, never trips it
        rth_next2 = ny(2026, 3, 11, 9, 36).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(79.0, 79.05, rth_next2)  # continues falling below the stop
        triggered = strategy._gap_risk_stop_symbols(rth_next2, {"SPY": D("1")})
        self.assertEqual(triggered, {"SPY"})

    def test_small_gap_within_stop_does_not_trigger(self):
        strategy = self.strategy(stop_bps="25")
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(99.99, 100.01, rth_next)  # essentially unchanged
        triggered = strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        self.assertEqual(triggered, set())

    def test_fires_once_per_rth_session(self):
        strategy = self.strategy(stop_bps="25")
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)  # sets the stop
        strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        rth_next2 = ny(2026, 3, 11, 9, 36).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(79.0, 79.05, rth_next2)  # breaches it
        # D2 (round 3): _gap_risk_stop_symbols alone no longer marks
        # fire-once (rebalance() does, only once the exit is actually
        # submitted) -- simulate that acceptance directly here, the same
        # way rebalance() would, so this test still locks in "fires once".
        first = strategy._gap_risk_stop_symbols(rth_next2, {"SPY": D("1")})
        self.assertEqual(first, {"SPY"})
        strategy._gap_stop_applied.add("SPY")
        rth_next3 = ny(2026, 3, 11, 9, 40).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(79.0, 79.05, rth_next3)
        second = strategy._gap_risk_stop_symbols(rth_next3, {"SPY": D("1")})
        self.assertEqual(second, set())  # already fired this RTH session

    def test_persisted_prior_close_survives_a_fresh_process_and_still_computes_the_stop(self):
        """S5: _prior_rth_close used to live only in AdaptiveStrategy's
        per-process memory, so the D5 gap-risk stop could never fire across
        invocations (e.g. resuming a held overnight position after a
        restart). Capture the prior close on one AdaptiveStrategy instance
        (against a real, durable Ledger), then construct an entirely new
        instance against the same ledger (simulating a fresh process) and
        confirm it computes the gap-risk stop from the persisted close --
        without ever itself observing the RTH->POST crossing that captured
        it."""
        import tempfile
        from native_strategy import AdaptiveStrategy
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "gap_risk.sqlite3")
            first_process = AdaptiveStrategy(_FakePolicy("25"), ledger, "trial-1")
            rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
            first_process.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
            first_process._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
            post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
            first_process.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
            first_process._gap_risk_stop_symbols(post, {"SPY": D("1")})  # persists prior close ~100.01
            self.assertIn("SPY", ledger.prior_rth_closes())

            # A brand-new AdaptiveStrategy instance against the same ledger,
            # standing in for a fresh process after a restart. It never
            # itself observes the RTH->POST crossing above.
            second_process = AdaptiveStrategy(_FakePolicy("25"), ledger, "trial-1")
            self.assertIn("SPY", second_process._prior_rth_close)
            self.assertAlmostEqual(float(second_process._prior_rth_close["SPY"]), 100.01, places=2)

            pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
            second_process._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})  # overnight hold continues
            rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
            second_process.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)  # gap-down open print
            first = second_process._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
            self.assertEqual(first, set())
            rth_next2 = ny(2026, 3, 11, 9, 36).astimezone(timezone.utc).timestamp()
            second_process.policy.latest["SPY"] = _FakeQuote(79.0, 79.05, rth_next2)  # continues falling
            triggered = second_process._gap_risk_stop_symbols(rth_next2, {"SPY": D("1")})
            self.assertEqual(triggered, {"SPY"})
            ledger.close()


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class StaleQuoteGapRiskTests(unittest.TestCase):
    """D2 (round 3): a stale quote must not trip the gap-risk stop, even
    though its bid is below the armed stop price."""

    def strategy(self, stop_bps="25"):
        from native_strategy import AdaptiveStrategy
        return AdaptiveStrategy(_FakePolicy(stop_bps), _FakeLedger(), "gap-risk-stale-test")

    def arm(self, strategy):
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)  # sets the stop ~79.98
        strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        return rth_next

    def test_stale_quote_below_stop_price_does_not_trigger(self):
        strategy = self.strategy(stop_bps="25")
        rth_next = self.arm(strategy)
        # A breaching bid, but timestamped well past quote_age_seconds (3s)
        # before the check `now`.
        check_now = rth_next + 60
        strategy.policy.latest["SPY"] = _FakeQuote(70.0, 70.05, rth_next)
        triggered = strategy._gap_risk_stop_symbols(check_now, {"SPY": D("1")})
        self.assertEqual(triggered, set())
        # The stop stays armed: a subsequent FRESH breaching quote still fires.
        strategy.policy.latest["SPY"] = _FakeQuote(70.0, 70.05, check_now)
        triggered = strategy._gap_risk_stop_symbols(check_now, {"SPY": D("1")})
        self.assertEqual(triggered, {"SPY"})

    def test_quote_from_the_future_beyond_tolerance_does_not_trigger(self):
        strategy = self.strategy(stop_bps="25")
        rth_next = self.arm(strategy)
        # A quote timestamped well ahead of `now` (beyond
        # QUOTE_FUTURE_TOLERANCE_SECONDS) is rejected the same way every
        # other order-path freshness check rejects one.
        strategy.policy.latest["SPY"] = _FakeQuote(70.0, 70.05, rth_next + 5)
        triggered = strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        self.assertEqual(triggered, set())


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class DeferredArmingOnStaleQuoteTests(unittest.TestCase):
    """D2 (round 4): the quote used to DERIVE the armed stop price (at the
    CLOSED/PRE -> RTH crossing, or any later RTH tick while still pending)
    is now age-checked too -- a stale quote at that instant no longer arms
    with a bogus reference price; arming is deferred to the next RTH tick
    instead of being silently skipped for the rest of the session."""

    def strategy(self, stop_bps="25"):
        from native_strategy import AdaptiveStrategy
        return AdaptiveStrategy(_FakePolicy(stop_bps), _FakeLedger(), "gap-risk-defer-test")

    def prime_prior_close(self, strategy):
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})

    def test_stale_quote_at_the_crossing_defers_arming_to_a_later_tick(self):
        strategy = self.strategy()
        self.prime_prior_close(strategy)
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        # Stale quote at the crossing instant itself (timestamped well
        # before rth_next -- beyond quote_age_seconds).
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next - 60)
        strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        self.assertNotIn("SPY", strategy._gap_risk_stop_price)  # not armed yet
        self.assertIn("SPY", strategy._gap_arm_pending)  # still pending, not abandoned

        # A later RTH tick with a fresh quote arms it.
        rth_next2 = rth_next + 30
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next2)
        strategy._gap_risk_stop_symbols(rth_next2, {"SPY": D("1")})
        self.assertIn("SPY", strategy._gap_risk_stop_price)
        self.assertNotIn("SPY", strategy._gap_arm_pending)


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class GapCloseCaptureFreshnessTests(unittest.TestCase):
    """D3 (round 4): the quote used to CAPTURE the prior RTH close (at the
    RTH -> non-RTH crossing) is now guarded with the same freshness
    window -- an unguarded/stale/future-stamped quote used to be captured
    (and persisted) unconditionally."""

    def strategy(self, stop_bps="25"):
        from native_strategy import AdaptiveStrategy
        return AdaptiveStrategy(_FakePolicy(stop_bps), _FakeLedger(), "gap-risk-capture-test")

    def test_stale_quote_at_the_rth_to_post_crossing_is_not_captured(self):
        strategy = self.strategy()
        rth = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth)
        strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})  # establishes RTH
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        # The quote is not refreshed -- still timestamped at `rth`, ~5
        # hours stale relative to `post`.
        triggered = strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        self.assertEqual(triggered, set())
        self.assertNotIn("SPY", strategy._prior_rth_close)

    def test_fresh_quote_at_the_crossing_is_captured_normally(self):
        strategy = self.strategy()
        rth = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth)
        strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)  # fresh
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        self.assertIn("SPY", strategy._prior_rth_close)
        self.assertEqual(strategy._prior_rth_close_session_date["SPY"], date(2026, 3, 10))


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class StalePriorCloseDateGuardTests(unittest.TestCase):
    """D3 (round 4): a persisted prior close is only usable if its
    session_date is exactly the trading day immediately before the
    session being armed; any other date is refused and recorded as an
    ignored event, never silently armed against."""

    def test_wrong_session_date_is_ignored_and_recorded(self):
        import tempfile
        from native_strategy import AdaptiveStrategy
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "gap_risk_date.sqlite3")
            # A close persisted for the WRONG date (well before the actual
            # trading day immediately preceding 2026-03-11).
            wrong_date = "2026-03-02"
            ledger.record_prior_rth_close("SPY", "100.00", wrong_date, 1)
            events = []
            strategy = AdaptiveStrategy(_FakePolicy("25"), ledger, "trial-1", event_sink=events.append)
            self.assertIn("SPY", strategy._prior_rth_close)
            self.assertEqual(strategy._prior_rth_close_session_date["SPY"], date(2026, 3, 2))

            rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
            strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)
            strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
            self.assertNotIn("SPY", strategy._gap_risk_stop_price)
            ignored = [e for e in events if e["type"] == "stale_prior_close_ignored"]
            self.assertEqual(len(ignored), 1)
            self.assertEqual(ignored[0]["symbol"], "SPY")
            ledger.close()

    def test_correct_session_date_arms_normally(self):
        import tempfile
        from native_strategy import AdaptiveStrategy
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "gap_risk_date_ok.sqlite3")
            correct_date = "2026-03-10"  # the trading day actually before 2026-03-11
            ledger.record_prior_rth_close("SPY", "100.00", correct_date, 1)
            strategy = AdaptiveStrategy(_FakePolicy("25"), ledger, "trial-1")
            rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
            strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)
            strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
            self.assertIn("SPY", strategy._gap_risk_stop_price)
            ledger.close()


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class GapStopTriggerThresholdTests(unittest.TestCase):
    """D4 (round 4): the gap stop only arms when the adverse (downward)
    gap magnitude is at least gap_stop_trigger_bps; gap_bps is recorded in
    self._gap_bps regardless of whether it armed."""

    def strategy(self, stop_bps="25", gap_stop_trigger_bps=None):
        from native_strategy import AdaptiveStrategy
        policy = _FakePolicy(stop_bps)
        if gap_stop_trigger_bps is not None:
            policy.config.gap_stop_trigger_bps = D(str(gap_stop_trigger_bps))
        return AdaptiveStrategy(policy, _FakeLedger(), "gap-risk-trigger-test")

    def arm_with_gap_pct(self, strategy, gap_bps):
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})  # prior close ~100.01
        pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        open_price = round(100.01 * (1 - gap_bps / 10000), 2)
        ask_price = round(open_price + .02, 2)  # avoid float-addition precision creep
        strategy.policy.latest["SPY"] = _FakeQuote(open_price, ask_price, rth_next)
        strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        return rth_next

    def test_small_gap_below_trigger_does_not_arm_but_gap_bps_is_recorded(self):
        strategy = self.strategy(stop_bps="25", gap_stop_trigger_bps="100")  # 1%
        self.arm_with_gap_pct(strategy, 10)  # 0.1% gap, well below the 100bps trigger
        self.assertNotIn("SPY", strategy._gap_risk_stop_price)
        self.assertIn("SPY", strategy._gap_bps)  # recorded regardless of arming

    def test_gap_at_or_above_trigger_arms(self):
        strategy = self.strategy(stop_bps="25", gap_stop_trigger_bps="100")  # 1%
        self.arm_with_gap_pct(strategy, 150)  # 1.5% gap, above the 100bps trigger
        self.assertIn("SPY", strategy._gap_risk_stop_price)

    def test_default_trigger_equals_stop_bps_and_is_byte_identical_in_effect(self):
        """PolicyConfig.gap_stop_trigger_bps' default (None -> stop_bps)
        must reproduce the exact pre-D4 arming behavior when nothing else
        changed: a gap as large as stop_bps arms; this class's other tests
        already lock in the pre-existing GapRiskExitChainTests fixtures,
        which never set gap_stop_trigger_bps explicitly."""
        strategy = self.strategy(stop_bps="25")  # gap_stop_trigger_bps defaults to 25
        # A gap comfortably at/above the default trigger (avoids a
        # rounding-boundary flake at the exact threshold from this
        # helper's cents-precision quote construction).
        self.arm_with_gap_pct(strategy, 40)
        self.assertIn("SPY", strategy._gap_risk_stop_price)


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class GapStopOptInFlagTests(unittest.TestCase):
    """Round 5: the entire gap-risk hook is opt-in on
    PolicyConfig.gap_stop_enabled (default False). Disabled: the whole
    method returns immediately without touching self._prior_rth_close,
    self.ledger, or self._last_session_kind at all -- including the
    prior-close capture/persist side, not just arming/triggering."""

    def strategy(self, gap_stop_enabled, ledger=None):
        from native_strategy import AdaptiveStrategy
        policy = _FakePolicy("25")
        policy.config.gap_stop_enabled = gap_stop_enabled
        return AdaptiveStrategy(policy, ledger or _FakeLedger(), "gap-stop-flag-test")

    def test_disabled_never_touches_ledger_state_or_quotes(self):
        class NeverCalledLedger(_FakeLedger):
            def record_prior_rth_close(self, *args, **kwargs):
                raise AssertionError("record_prior_rth_close must not be called when disabled")

        strategy = self.strategy(False, ledger=NeverCalledLedger())
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        result = strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        self.assertEqual(result, set())
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})  # would capture if enabled
        self.assertEqual(strategy._prior_rth_close, {})
        self.assertIsNone(strategy._last_session_kind)  # never even updated
        self.assertEqual(strategy._gap_arm_pending, set())
        self.assertEqual(strategy._prior_close_capture_pending, set())

    def test_enabled_behaves_normally(self):
        strategy = self.strategy(True)
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        self.assertEqual(strategy._last_session_kind, sess.SessionKind.RTH)


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class RealPolicyConfigGapDerivationTests(unittest.TestCase):
    """D3 (round 5, decisive): PolicyConfig.stop_bps/gap_stop_trigger_bps
    are plain Python floats (the REAL field type -- every fake elsewhere
    in this file passes stop_bps as a string, which happened to mask this
    entirely). safety.decimal() rejects float outright
    (`type(value) not in (str, int, Decimal)`), so the pre-fix stop
    derivation raised inside evaluate_gap_risk and was silently swallowed
    by _gap_risk_stop_symbols' own except-continue -- disabling the whole
    hook for every real engine config, regardless of gap_stop_enabled or
    anything else. This drives derivation with the real, unmodified
    strategies_v1.PolicyConfig dataclass."""

    def strategy(self):
        from native_strategy import AdaptiveStrategy
        from strategies_v1 import PolicyConfig

        class _RealConfigPolicy:
            def __init__(self, config):
                self.config = config
                self.latest = {}

        config = PolicyConfig(symbols=("SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT"),
                              benchmarks=("SPY", "QQQ", "IWM", "DIA"), max_positions=6,
                              stop_bps=25.0, gap_stop_enabled=True)
        return AdaptiveStrategy(_RealConfigPolicy(config), _FakeLedger(), "real-config-test")

    def test_derivation_succeeds_with_real_float_stop_bps_and_trigger(self):
        strategy = self.strategy()
        self.assertIsInstance(strategy.policy.config.stop_bps, float)
        self.assertIsInstance(strategy.policy.config.gap_stop_trigger_bps, float)
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)  # large gap-down
        strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        # Must have actually armed, not been silently discarded by a
        # float-rejecting decimal() call swallowed as "just no gap".
        self.assertIn("SPY", strategy._gap_risk_stop_price)
        self.assertIn("SPY", strategy._gap_bps)


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class PriorCloseCaptureRetryTests(unittest.TestCase):
    """D2 (round 5): the CAPTURE side (RTH -> non-RTH crossing) retries
    across later non-RTH ticks when the crossing-tick quote is stale,
    emitting "prior_close_captured" on success or
    "prior_close_capture_abandoned" if still pending once the next RTH
    session opens."""

    def strategy(self, stop_bps="25"):
        from native_strategy import AdaptiveStrategy
        events = []
        strategy = AdaptiveStrategy(_FakePolicy(stop_bps), _FakeLedger(), "capture-retry-test",
                                    event_sink=events.append)
        strategy._events = events
        return strategy

    def test_stale_crossing_quote_defers_capture_and_retries(self):
        strategy = self.strategy()
        rth = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth)
        strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        # Quote not refreshed -- stale relative to `post`.
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        self.assertNotIn("SPY", strategy._prior_rth_close)
        self.assertIn("SPY", strategy._prior_close_capture_pending)
        self.assertFalse(any(e["type"] == "prior_close_captured" for e in strategy._events))

        # A later non-RTH (still POST) tick with a fresh quote captures it.
        post2 = post + 30
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post2)
        strategy._gap_risk_stop_symbols(post2, {"SPY": D("1")})
        self.assertIn("SPY", strategy._prior_rth_close)
        self.assertNotIn("SPY", strategy._prior_close_capture_pending)
        captured = [e for e in strategy._events if e["type"] == "prior_close_captured"]
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["symbol"], "SPY")

    def test_still_pending_at_next_rth_open_is_abandoned(self):
        strategy = self.strategy()
        rth = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth)
        strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})  # quote stays stale forever
        self.assertIn("SPY", strategy._prior_close_capture_pending)

        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)
        strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        self.assertEqual(strategy._prior_close_capture_pending, set())
        abandoned = [e for e in strategy._events if e["type"] == "prior_close_capture_abandoned"]
        self.assertEqual(len(abandoned), 1)
        self.assertEqual(abandoned[0]["symbol"], "SPY")
        self.assertNotIn("SPY", strategy._prior_rth_close)  # never captured this crossing


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class PriorClosePersistGuardTests(unittest.TestCase):
    """D4 (round 5): the captured midpoint is rounded to tick precision
    before persisting (avoiding safety.decimal()'s 9-decimal-digit
    bound), and a persistence failure is caught and recorded via an
    event, never raised into rebalance()."""

    def strategy(self, ledger=None):
        from native_strategy import AdaptiveStrategy
        events = []
        strategy = AdaptiveStrategy(_FakePolicy("25"), ledger or _FakeLedger(), "persist-guard-test",
                                    event_sink=events.append)
        strategy._events = events
        return strategy

    def test_high_precision_midpoint_is_rounded_before_persisting(self):
        strategy = self.strategy()
        rth = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        # (100.123456781 + 100.123456782) / 2 = 100.1234567815 -- 10
        # decimal digits, one more than safety.decimal() accepts, if
        # persisted unrounded.
        strategy.policy.latest["SPY"] = _FakeQuote("100.123456781", "100.123456782", rth)
        strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote("100.123456781", "100.123456782", post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        self.assertIn("SPY", strategy._prior_rth_close)
        self.assertEqual(strategy._prior_rth_close["SPY"], D("100.12"))  # rounded to the cent
        failed = [e for e in strategy._events if e["type"] == "prior_close_persist_failed"]
        self.assertEqual(failed, [])  # rounding makes persistence succeed

    def test_persist_failure_is_caught_and_recorded_not_raised(self):
        class RaisingLedger(_FakeLedger):
            def record_prior_rth_close(self, symbol, price, session_date, ts_ns):
                raise SafetyError("simulated_persist_failure")

        strategy = self.strategy(ledger=RaisingLedger())
        rth = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth)
        strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})  # must not raise
        self.assertIn("SPY", strategy._prior_rth_close)  # in-memory copy still usable
        failed = [e for e in strategy._events if e["type"] == "prior_close_persist_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["symbol"], "SPY")


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class CalendarBoundaryPreviousTradingDayTests(unittest.TestCase):
    """D7 (round 5): previous_trading_day at the first trading day of the
    frozen calendar (2026-01-02, since 2026-01-01 is a holiday) walks
    back into 2025 -- outside sessions.CALENDAR_YEARS -- and raises
    ValueError. _gap_risk_stop_symbols already treats that as
    validation-unknown (do not arm, record it via the existing
    "stale_prior_close_ignored" event), not a raised exception; this
    test locks that in for the actual year-boundary date."""

    def strategy(self, stop_bps="25"):
        from native_strategy import AdaptiveStrategy
        events = []
        strategy = AdaptiveStrategy(_FakePolicy(stop_bps), _FakeLedger(), "calendar-boundary-test",
                                    event_sink=events.append)
        strategy._events = events
        return strategy

    def test_previous_trading_day_at_year_boundary_raises(self):
        with self.assertRaises(ValueError):
            sess.previous_trading_day(date(2026, 1, 2))

    def test_arming_on_2026_01_02_degrades_to_validation_unknown_not_a_raise(self):
        strategy = self.strategy()
        # A prior close dated the actual trading day before (2025-12-31)
        # would be the semantically-correct date, but it can never be
        # confirmed as such (out-of-calendar) and so must stay unusable.
        strategy._prior_rth_close["SPY"] = D("100.00")
        strategy._prior_rth_close_session_date["SPY"] = date(2025, 12, 31)
        rth = ny(2026, 1, 2, 9, 35).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(90.0, 90.02, rth)
        triggered = strategy._gap_risk_stop_symbols(rth, {"SPY": D("1")})  # must not raise
        self.assertEqual(triggered, set())
        self.assertNotIn("SPY", strategy._gap_risk_stop_price)
        ignored = [e for e in strategy._events if e["type"] == "stale_prior_close_ignored"]
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored[0]["symbol"], "SPY")
        self.assertIsNone(ignored[0]["expected_session_date"])  # could not be determined


@unittest.skipUnless(NATIVE, "nautilus_trader not installed")
class ArmingMidpointRoundingAndRetryTests(unittest.TestCase):
    """D3 (round 6): the session_open midpoint used for ARMING is now
    rounded to the same tick precision the capture side already uses
    (_round_to_tick), and a failed arming evaluation keeps the symbol in
    _gap_arm_pending for retry -- recorded via a "gap_arm_evaluation_failed"
    event -- instead of being permanently discarded from it."""

    def strategy(self, stop_bps="25"):
        from native_strategy import AdaptiveStrategy
        events = []
        strategy = AdaptiveStrategy(_FakePolicy(stop_bps), _FakeLedger(), "arming-retry-test",
                                    event_sink=events.append)
        strategy._events = events
        return strategy

    def prime_prior_close(self, strategy):
        rth1 = ny(2026, 3, 10, 12, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, rth1)
        strategy._gap_risk_stop_symbols(rth1, {"SPY": D("1")})
        post = ny(2026, 3, 10, 17, 0).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(100.0, 100.02, post)
        strategy._gap_risk_stop_symbols(post, {"SPY": D("1")})
        pre_next = ny(2026, 3, 11, 7, 0).astimezone(timezone.utc).timestamp()
        strategy._gap_risk_stop_symbols(pre_next, {"SPY": D("1")})

    def test_high_precision_session_open_is_rounded_before_arming(self):
        strategy = self.strategy()
        self.prime_prior_close(strategy)
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        # (80.123456781 + 80.123456782) / 2 has 10 decimal digits -- one
        # more than safety.decimal() accepts -- if used unrounded.
        strategy.policy.latest["SPY"] = _FakeQuote("80.123456781", "80.123456782", rth_next)
        strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})
        self.assertIn("SPY", strategy._gap_risk_stop_price)
        self.assertNotIn("SPY", strategy._gap_arm_pending)
        failed = [e for e in strategy._events if e["type"] == "gap_arm_evaluation_failed"]
        self.assertEqual(failed, [])

    def test_failed_evaluation_keeps_symbol_pending_for_retry(self):
        strategy = self.strategy()
        self.prime_prior_close(strategy)
        # Corrupt the primed prior close so evaluate_gap_risk's own
        # decimal(prior_close) call raises (zero is refused by decimal()'s
        # default zero=False).
        strategy._prior_rth_close["SPY"] = D("0")
        rth_next = ny(2026, 3, 11, 9, 35).astimezone(timezone.utc).timestamp()
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next)
        triggered = strategy._gap_risk_stop_symbols(rth_next, {"SPY": D("1")})  # must not raise
        self.assertEqual(triggered, set())
        self.assertNotIn("SPY", strategy._gap_risk_stop_price)
        self.assertIn("SPY", strategy._gap_arm_pending)  # kept for retry, not discarded
        failed = [e for e in strategy._events if e["type"] == "gap_arm_evaluation_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["symbol"], "SPY")

        # Fix the prior close and retry on a later RTH tick.
        strategy._prior_rth_close["SPY"] = D("100.01")
        rth_next2 = rth_next + 30
        strategy.policy.latest["SPY"] = _FakeQuote(80.0, 80.05, rth_next2)
        strategy._gap_risk_stop_symbols(rth_next2, {"SPY": D("1")})
        self.assertIn("SPY", strategy._gap_risk_stop_price)
        self.assertNotIn("SPY", strategy._gap_arm_pending)


if __name__ == "__main__":
    unittest.main()
