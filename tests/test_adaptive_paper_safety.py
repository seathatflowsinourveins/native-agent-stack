"""Synthetic durable-risk tests; no credentials, sockets, or broker execution."""
from dataclasses import replace
from decimal import Decimal as D
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "blueprints/us-equities/adaptive-paper/safety.py"
SPEC = importlib.util.spec_from_file_location("adaptive_paper_safety", FILE)
s = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = s
SPEC.loader.exec_module(s)

try:  # package mode (python -m unittest tests.x) or discover -s tests (top-level modules)
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    _HERMETIC_TOKEN = patch_default_stop(s)


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = 1_800_000_000.0
        self.db = self.root / "account.sqlite3"
        self.ledger = s.Ledger(self.db)
        self.ledger.start_trial(self.now)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def quote(self, symbol="SPY", bid="100", ask="100.01", at=None):
        return s.Quote(symbol, bid, ask, self.now if at is None else at)

    def reserve(self, cid="buy-1", symbol="SPY", side="buy", qty="1", price="100.02", **kwargs):
        args = {"quote": self.quote(symbol), "now": self.now, "market_open": True,
                "session_close": self.now + 3600, "stop_file": self.root / "STOP"}
        args.update(kwargs)
        return self.ledger.reserve_intent(cid, symbol, side, qty, price, **args)

    def fill(self, cid="buy-1", qty="1", price="100", status="filled", broker_id=None, timestamp=None):
        return self.ledger.record_order(cid, broker_id or "broker-" + cid, status, qty, price, timestamp=timestamp)

    def reopen(self, limits=None):
        self.ledger.close()
        self.ledger = s.Ledger(self.db, limits)

    def test_intent_and_frozen_limits_survive_restart(self):
        created = self.reserve()
        self.assertTrue(created.newly_reserved)
        self.reopen()
        duplicate = self.reserve()
        self.assertFalse(duplicate.newly_reserved)
        self.assertEqual(duplicate.client_id, created.client_id)
        self.assertEqual(self.ledger.accounting().pending_buy_notional_usd, D("100.02"))
        with self.assertRaisesRegex(s.SafetyError, "conflicts"):
            self.reserve(price="101")
        with self.assertRaisesRegex(s.SafetyError, "persisted_risk_limits_differ"):
            s.Ledger(self.db, replace(s.RiskLimits(), max_order_qty=D(2)))

    def test_no_blind_resubmit_after_ambiguous_attempt(self):
        self.reserve()
        self.assertEqual(self.ledger.request_budget(self.now, "submit", "buy-1"), 0)
        self.reopen()
        self.assertTrue(self.ledger.intents()[0].submit_attempted)
        with self.assertRaisesRegex(s.SafetyError, "already_attempted"):
            self.ledger.request_budget(self.now, "submit", "buy-1")
        self.assertEqual(len(self.ledger.unresolved()), 1)

    def test_submit_attempt_requires_known_reserved_identity(self):
        with self.assertRaises(s.SafetyError):
            self.ledger.request_budget(self.now, "submit", "unknown")
        self.reserve()
        self.fill()
        with self.assertRaises(s.SafetyError):
            self.ledger.request_budget(self.now, "submit", "buy-1")

    def test_incremental_fill_notional_uses_cumulative_average(self):
        self.reserve(price="102")
        self.fill(qty="0.4", price="100", status="partially_filled")
        self.fill(qty="1", price="101")
        position = self.ledger.positions()["SPY"]
        self.assertEqual(position.qty, 1)
        self.assertEqual(position.cost_basis_usd, 101)
        self.assertEqual(self.ledger.accounting().cash_delta_usd, -101)
        self.reserve("sell-1", side="sell", qty="0.4", price="99.99")
        self.fill("sell-1", qty="0.2", price="101", status="partially_filled")
        self.fill("sell-1", qty="0.4", price="102")
        self.assertEqual(self.ledger.positions()["SPY"].cost_basis_usd, D("60.6"))
        self.assertEqual(self.ledger.accounting().realized_pnl_usd, D("0.4"))

    def test_stale_and_duplicate_fills_do_not_change_accounting(self):
        self.reserve()
        self.fill(qty="0.4", status="partially_filled")
        before = self.ledger.accounting()
        self.assertFalse(self.fill(qty="0.2", status="partially_filled"))
        self.assertFalse(self.fill(qty="0.4", status="partially_filled"))
        self.assertEqual(self.ledger.accounting(), before)
        self.fill()
        self.assertFalse(self.fill(status="accepted"))
        self.assertEqual(self.ledger.positions()["SPY"].qty, 1)

    def test_partial_terminal_releases_only_unfilled_reservation(self):
        self.reserve()
        self.fill(qty="0.4", status="partially_filled")
        self.fill(qty="0.6", status="canceled")
        self.assertEqual(self.ledger.accounting().pending_buy_notional_usd, 0)
        self.assertEqual(self.ledger.positions()["SPY"].qty, D("0.6"))
        self.assertEqual(self.ledger.unresolved(), [])
        with self.assertRaisesRegex(s.SafetyError, "sell_exceeds"):
            self.reserve("sell-1", side="sell", qty="1", price="99.99")
        self.reserve("sell-1", side="sell", qty="0.6", price="99.99")
        self.fill("sell-1", qty="0.6", price="100")
        self.assertEqual(self.ledger.positions(), {})
        self.assertEqual(self.ledger.accounting().cash_delta_usd, 0)

    def test_conflicting_snapshot_rolls_back_fill_and_position(self):
        self.reserve()
        self.fill(qty="0.4", status="partially_filled")
        before = self.ledger.accounting()
        for kwargs in [{"qty": "0.4", "price": "101", "status": "partially_filled"},
                       {"qty": "1.1", "price": "100"},
                       {"qty": "1", "price": "105"},
                       {"qty": "1", "broker_id": "different"}]:
            with self.assertRaises(s.SafetyError):
                self.fill(**kwargs)
            self.assertEqual(self.ledger.accounting(), before)

    def test_terminal_contradiction_fails_closed(self):
        self.reserve()
        self.fill(qty="0.4", status="canceled")
        with self.assertRaisesRegex(s.SafetyError, "terminal_order_contradiction"):
            self.fill(qty="0.6", status="canceled")
        self.assertEqual(self.ledger.positions()["SPY"].qty, D("0.4"))

    def test_broker_order_id_cannot_alias_two_intents(self):
        self.reserve("buy-1")
        self.reserve("buy-2")
        self.fill("buy-1", broker_id="same")
        with self.assertRaises(sqlite3.IntegrityError):
            self.fill("buy-2", broker_id="same")
        self.assertEqual(self.ledger.positions()["SPY"].qty, 1)

    def test_pending_and_held_exposure_share_one_cap(self):
        limits = replace(s.RiskLimits(), max_gross_exposure_usd=D("200"), max_order_notional_usd=D("200"))
        self.ledger.close()
        self.db = self.root / "limited.sqlite3"
        self.ledger = s.Ledger(self.db, limits)
        self.ledger.start_trial(self.now)
        self.reserve(price="100")
        self.fill(qty="0.4", status="partially_filled")
        with self.assertRaisesRegex(s.SafetyError, "aggregate_exposure"):
            self.reserve("buy-2", price="100.02")
        self.assertGreaterEqual(self.ledger.accounting().gross_exposure_usd, D(100))

    def test_outstanding_sell_reservation_prevents_oversell(self):
        self.reserve()
        self.fill()
        self.reserve("sell-1", side="sell", qty="0.6", price="99.99")
        with self.assertRaisesRegex(s.SafetyError, "sell_exceeds"):
            self.reserve("sell-2", side="sell", qty="0.5", price="99.99")
        self.reserve("sell-2", side="sell", qty="0.4", price="99.99")

    def test_cumulative_realized_loss_and_halt_survive_restart(self):
        limits = replace(s.RiskLimits(), max_gross_loss_usd=D("1"), max_drawdown_usd=D("5"))
        self.ledger.close()
        self.db = self.root / "loss.sqlite3"
        self.ledger = s.Ledger(self.db, limits)
        self.ledger.start_trial(self.now)
        self.reserve(price="100")
        self.fill()
        self.reserve("sell-1", side="sell", price="99", quote=self.quote(bid="99", ask="99.01"))
        self.fill("sell-1", price="99")
        self.reopen(limits)
        state = self.ledger.accounting()
        self.assertEqual(state.cash_delta_usd, -1)
        self.assertEqual(state.realized_pnl_usd, -1)
        self.assertEqual(state.cumulative_realized_loss_usd, 1)
        self.assertEqual(state.halted_reason, "gross_loss_cap_reached")
        with self.assertRaisesRegex(s.SafetyError, "gross_loss"):
            self.reserve("buy-2")

    def test_marked_drawdown_and_risk_reducing_exit(self):
        self.reserve(price="100")
        self.fill()
        high = self.ledger.mark_to_market([self.quote(bid="120", ask="120.01")], self.now)
        self.assertEqual(high.peak_pnl_usd, 20)
        low = self.ledger.mark_to_market([self.quote(bid="95", ask="95.01")], self.now)
        self.assertEqual(low.drawdown_usd, 25)
        self.assertEqual(low.halted_reason, "drawdown_cap_reached")
        with self.assertRaises(s.SafetyError):
            self.reserve("buy-2")
        self.reserve("sell-1", side="sell", price="94.99", quote=self.quote(bid="95", ask="95.01"))

    def test_stop_and_entry_deadline_preserve_cleanup_exit(self):
        self.reserve()
        self.fill()
        (self.root / "STOP").touch()
        with self.assertRaisesRegex(s.SafetyError, "stop_blocks"):
            self.reserve("buy-2")
        self.now += 301
        self.reserve("sell-1", side="sell", price="99.99")
        self.fill("sell-1")
        with self.assertRaisesRegex(s.SafetyError, "trial_window"):
            self.reserve("buy-3")
        self.assertEqual(self.ledger.start_trial(self.now), self.now - 301)

    def test_cleanup_deadline_is_not_reset_by_restart(self):
        self.reserve()
        self.fill()
        self.reopen()
        self.now += 421
        with self.assertRaisesRegex(s.SafetyError, "trial_window"):
            self.reserve("sell-1", side="sell", price="99.99")

    def test_quote_session_and_numeric_failures(self):
        for changes in [{"quote": self.quote(at=self.now - 3.01)},
                        {"quote": self.quote(at=self.now + 0.3)},
                        {"quote": self.quote(bid="100", ask="100.2")},
                        {"market_open": False}, {"session_close": self.now + 299},
                        {"quote": self.quote("AAPL")}]:
            with self.assertRaises(s.SafetyError):
                self.reserve(**changes)
        for value in [True, 1.0, "NaN", "Infinity", "-1", "1e2", "0", "0.0000000001"]:
            with self.assertRaises(s.SafetyError):
                self.reserve(qty=value)
        with self.assertRaises(s.SafetyError):
            self.reserve(qty="0.5")
        with self.assertRaises(s.SafetyError):
            self.reserve(price="100.001")
        self.assertEqual(self.ledger.intents(), [])

    def test_rate_budget_reserves_twenty_calls_and_persists(self):
        for _ in range(180):
            self.assertEqual(self.ledger.request_budget(self.now, "submit"), 0)
        self.assertEqual(self.ledger.request_budget(self.now, "submit"), 60)
        self.reopen()
        for _ in range(20):
            self.assertEqual(self.ledger.request_budget(self.now, "cancel"), 0)
        self.assertEqual(self.ledger.request_budget(self.now, "read"), 60)
        self.assertEqual(self.ledger.request_budget(self.now + 59.5, "submit"), 0.5)
        self.assertEqual(self.ledger.request_budget(self.now + 60, "submit"), 0)

    def test_budget_clock_backward_and_frozen_limits_rejected(self):
        self.ledger.request_budget(self.now, "data_read")
        with self.assertRaisesRegex(s.SafetyError, "backward"):
            self.ledger.request_budget(self.now - 1, "read")
        for change in [{"max_rest_per_minute": 1000}, {"max_submits_per_minute": 181},
                       {"max_rest_per_minute": 190}, {"max_outstanding_orders": True},
                       {"max_gross_exposure_usd": "10001"}]:
            with self.assertRaises(s.SafetyError):
                s.RiskLimits(**change)

    def test_two_connections_share_atomic_budget(self):
        other = s.Ledger(self.db)
        try:
            barrier = threading.Barrier(2)
            results = []
            def reserve_many(ledger):
                barrier.wait()
                results.extend(ledger.request_budget(self.now, "read") for _ in range(110))
            workers = [threading.Thread(target=reserve_many, args=(ledger,)) for ledger in (self.ledger, other)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            self.assertEqual(results.count(0), 200)
            self.assertEqual(results.count(60), 20)
        finally:
            other.close()

    def test_same_account_lock_matches_smoke_namespace(self):
        locks = self.root / "locks"
        fingerprint = hashlib.sha256(b"fixture-account").hexdigest()
        with s.account_lock("fixture-account", locks) as returned:
            self.assertEqual(returned, fingerprint)
            self.assertTrue((locks / (fingerprint + ".lock")).exists())
            with self.assertRaisesRegex(s.SafetyError, "writer_already"):
                with s.account_lock("fixture-account", locks):
                    self.fail("second writer entered")
            with self.assertRaisesRegex(s.SafetyError, "writer_already"):
                with s.account_lock_fingerprint(fingerprint, locks):
                    self.fail("fingerprint path bypassed raw-id lock")

    def test_invalid_account_fingerprint_rejected(self):
        for fingerprint in ["raw-account", "../" + "a" * 64, "A" * 64, "a" * 63, True]:
            with self.assertRaisesRegex(s.SafetyError, "invalid_account_fingerprint"):
                with s.account_lock_fingerprint(fingerprint, self.root / "locks"):
                    self.fail("invalid fingerprint locked")

    def test_symlink_database_rejected(self):
        link = self.root / "alias.sqlite3"
        link.symlink_to(self.db)
        with self.assertRaises(OSError):
            s.Ledger(link)

    def test_unknown_fill_and_persistent_freeze(self):
        with self.assertRaisesRegex(s.SafetyError, "unknown_client"):
            self.fill("external")
        self.ledger.freeze("stream_reconciliation_failed")
        self.reopen()
        with self.assertRaisesRegex(s.SafetyError, "stream_reconciliation_failed"):
            self.reserve()

    def test_held_mark_staleness_blocks_new_exposure(self):
        self.reserve()
        self.fill()
        self.now += 4
        with self.assertRaisesRegex(s.SafetyError, "held_position_mark_stale"):
            self.reserve("buy-2", symbol="AAPL")
        self.ledger.mark_to_market([self.quote()], self.now)
        self.reserve("buy-2", symbol="AAPL")

    def test_sqlite_full_durability_and_events_survive_reopen(self):
        self.reserve()
        self.assertEqual(self.ledger.db.execute("PRAGMA synchronous").fetchone()[0], 2)
        self.assertEqual(self.ledger.db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.reopen()
        kinds = [r[0] for r in self.ledger.db.execute("SELECT kind FROM events")]
        self.assertEqual(kinds, ["trial_start", "intent_reserved"])

    def test_out_of_order_partial_update_does_not_reverse_pending_cancel(self):
        self.reserve()
        self.fill(qty="0.2", status="pending_cancel")
        self.fill(qty="0.4", status="partially_filled")
        self.assertEqual(self.ledger.intents()[0].status, "pending_cancel")
        self.assertEqual(self.ledger.positions()["SPY"].qty, D("0.4"))
        self.fill(qty="0.6", status="canceled")
        self.assertEqual(self.ledger.unresolved(), [])

    def test_outstanding_order_cap_counts_ambiguous_intents(self):
        for index in range(20):
            self.reserve(f"buy-{index}")
        with self.assertRaisesRegex(s.SafetyError, "outstanding_order_cap"):
            self.reserve("buy-over-cap")
        self.assertEqual(len(self.ledger.unresolved()), 20)

    def test_symbol_cap_counts_pending_entries(self):
        for symbol in ["AAPL", "AMZN", "MSFT", "META", "GOOG", "QQQ", "SPY", "IWM", "DIA", "NVDA"]:
            self.reserve("buy-" + symbol, symbol=symbol)
        with self.assertRaisesRegex(s.SafetyError, "held_symbol_cap"):
            self.reserve("buy-TSLA", symbol="TSLA")

    def test_total_exposure_does_not_exceed_current_allocated_equity(self):
        limits = replace(s.RiskLimits(), capital_usd=D("200"), max_gross_exposure_usd=D("200"),
                         max_order_notional_usd=D("200"), max_gross_loss_usd=D("10"), max_drawdown_usd=D("10"))
        self.ledger.close()
        self.db = self.root / "unlevered.sqlite3"
        self.ledger = s.Ledger(self.db, limits)
        self.ledger.start_trial(self.now)
        self.reserve(price="100")
        self.fill()
        self.reserve("sell-1", side="sell", price="99", quote=self.quote(bid="99", ask="99.01"))
        self.fill("sell-1", price="99")
        self.reserve("buy-2", price="100")
        with self.assertRaisesRegex(s.SafetyError, "aggregate_exposure"):
            self.reserve("buy-3", price="100")

    def test_risk_refusal_retains_observed_loss_halt(self):
        self.reserve()
        self.fill()
        with self.assertRaisesRegex(s.SafetyError, "gross_loss_cap_reached"):
            self.reserve("buy-2", price="75", quote=self.quote(bid="75", ask="75.01"))
        self.reopen()
        self.assertEqual(self.ledger.accounting().gross_loss_usd, 25)
        self.assertEqual(self.ledger.accounting().halted_reason, "gross_loss_cap_reached")
        self.assertEqual(len(self.ledger.intents()), 1)
        with self.assertRaisesRegex(s.SafetyError, "gross_loss_cap_reached"):
            self.reserve("buy-2")

    def validate(self, cid="buy-1", **kwargs):
        args = {"quote": self.quote(), "now": self.now, "market_open": True,
                "session_close": self.now + 3600, "stop_file": self.root / "STOP"}
        args.update(kwargs)
        return self.ledger.validate_pending(cid, **args)

    def test_final_validation_does_not_double_reserve(self):
        self.reserve()
        before = self.ledger.accounting()
        self.validate()
        self.validate()
        self.assertEqual(self.ledger.accounting(), before)
        self.assertEqual(len(self.ledger.intents()), 1)

    def test_final_validation_after_budget_wait_rejects_stale_and_stop(self):
        self.reserve()
        quote = self.quote()
        for _ in range(180):
            self.ledger.request_budget(self.now, "submit")
        self.assertEqual(self.ledger.request_budget(self.now, "submit", "buy-1"), 60)
        self.now += 60
        with self.assertRaisesRegex(s.SafetyError, "quote_not_fresh"):
            self.validate(quote=quote)
        (self.root / "STOP").touch()
        with self.assertRaisesRegex(s.SafetyError, "stop_blocks_entry"):
            self.validate()

    def test_final_validation_rechecks_clock_window_and_halt(self):
        self.reserve()
        with self.assertRaisesRegex(s.SafetyError, "outside_allowed_session"):
            self.validate(market_open=False)
        self.ledger.freeze("stream_gap")
        with self.assertRaisesRegex(s.SafetyError, "stream_gap"):
            self.validate()
        self.now += 300
        with self.assertRaisesRegex(s.SafetyError, "trial_window_ended"):
            self.validate()

    def test_definitive_not_sent_releases_risk_without_budget_refund(self):
        self.reserve()
        self.ledger.request_budget(self.now, "submit", "buy-1")
        self.assertTrue(self.ledger.mark_not_sent("buy-1", "quote_not_fresh"))
        self.assertFalse(self.ledger.mark_not_sent("buy-1", "quote_not_fresh"))
        self.reopen()
        intent = self.ledger.intents()[0]
        self.assertEqual(intent.status, "not_sent")
        self.assertIsNone(intent.broker_id)
        self.assertTrue(intent.submit_attempted)
        self.assertEqual(self.ledger.unresolved(), [])
        self.assertEqual(self.ledger.accounting().pending_buy_notional_usd, 0)
        self.assertEqual(self.ledger.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)
        with self.assertRaises(s.SafetyError):
            self.ledger.request_budget(self.now, "submit", "buy-1")
        with self.assertRaisesRegex(s.SafetyError, "after_definitive_not_sent"):
            self.fill()

    def test_observed_or_filled_order_cannot_be_called_not_sent(self):
        self.reserve()
        self.fill(qty="0", price=None, status="accepted")
        with self.assertRaisesRegex(s.SafetyError, "cannot_mark_observed"):
            self.ledger.mark_not_sent("buy-1", "transport_refused")
        with self.assertRaisesRegex(s.SafetyError, "already_observed_or_terminal"):
            self.validate()

    def test_pending_exit_remains_allowed_after_halt_and_stop(self):
        self.reserve()
        self.fill()
        self.reserve("sell-1", side="sell", price="99.99")
        self.ledger.freeze("stream_gap")
        (self.root / "STOP").touch()
        self.now += 301
        self.validate("sell-1")
        self.fill("sell-1")
        self.assertEqual(self.ledger.positions(), {})

    def test_expired_trial_bounded_recovery_allows_owned_fractional_exit_only(self):
        self.reserve()
        self.ledger.request_budget(self.now, "submit", "buy-1")
        self.fill(qty="0.6", status="canceled")
        self.now += 421
        with self.assertRaisesRegex(s.SafetyError, "trial_window"):
            self.reserve("sell-1", side="sell", qty="0.6", price="99.99")
        original = self.ledger.accounting()
        self.ledger.begin_recovery(self.now)
        self.assertEqual(self.ledger.accounting().cash_delta_usd, original.cash_delta_usd)
        self.assertEqual(self.ledger.positions()["SPY"].qty, D("0.6"))
        self.assertEqual(self.ledger.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)
        with self.assertRaisesRegex(s.SafetyError, "recovery_only_blocks_entry"):
            self.reserve("buy-2")
        self.reserve("sell-1", side="sell", qty="0.6", price="99.99")
        self.validate("sell-1")
        self.fill("sell-1", qty="0.6")
        self.assertEqual(self.ledger.positions(), {})

    def test_recovery_preserves_loss_halt_and_does_not_renew_implicitly(self):
        self.reserve()
        self.fill()
        self.ledger.freeze("gross_loss_cap_reached")
        self.now += 421
        self.ledger.begin_recovery(self.now)
        self.assertEqual(self.ledger.accounting().halted_reason, "gross_loss_cap_reached")
        self.reopen()
        self.now += 121
        with self.assertRaisesRegex(s.SafetyError, "trial_window"):
            self.reserve("sell-1", side="sell", price="99.99")
        self.ledger.begin_recovery(self.now)
        self.reserve("sell-1", side="sell", price="99.99")
        with self.assertRaisesRegex(s.SafetyError, "outside_allowed_session"):
            self.validate("sell-1", market_open=False)
        with self.assertRaisesRegex(s.SafetyError, "quote_not_fresh"):
            self.validate("sell-1", quote=self.quote(at=self.now - 4))
        with self.assertRaisesRegex(s.SafetyError, "recovery_only_blocks_entry"):
            self.reserve("buy-2")

    def test_nine_decimal_partial_fill_can_recover_exact_residual(self):
        self.reserve()
        residual = D("0.123456789")
        self.fill(qty="0.123456789", status="canceled")
        self.now += 421
        self.ledger.begin_recovery(self.now)
        self.reserve("sell-1", side="sell", qty=residual, price="99.99")
        self.fill("sell-1", qty=residual, price="100")
        self.assertEqual(self.ledger.positions(), {})
        self.assertEqual(self.ledger.accounting().cash_delta_usd, 0)
        self.assertEqual(s.decimal(D("0.000000001")), D("0.000000001"))
        self.assertEqual(s.decimal(D("1.000000000000")), 1)
        for bad in [D("1E-10"), D("1E-1000000"), D("1E1000000"), D("NaN")]:
            with self.assertRaises(s.SafetyError):
                s.decimal(bad)

    def test_future_quote_tolerance_is_consistent_for_held_risk(self):
        allowed = self.quote(at=self.now + 0.2)
        self.reserve(quote=allowed)
        self.fill()
        self.ledger.mark_to_market([allowed], self.now)
        self.reserve("buy-2", quote=allowed)
        self.validate("buy-2", quote=allowed)
        rejected = self.quote(at=self.now + 0.251)
        for action in [lambda: self.ledger.mark_to_market([rejected], self.now),
                       lambda: self.reserve("buy-3", quote=rejected),
                       lambda: self.validate("buy-2", quote=rejected)]:
            with self.assertRaisesRegex(s.SafetyError, "quote_not_fresh"):
                action()

    def test_proven_broker_refusal_has_distinct_status_and_retains_request(self):
        self.reserve()
        with self.assertRaisesRegex(s.SafetyError, "cannot_mark_order_broker_refused"):
            self.ledger.mark_broker_refused("buy-1", 403)
        self.ledger.request_budget(self.now, "submit", "buy-1")
        for bad in [400, 422, 429, 500, True, "403"]:
            with self.assertRaisesRegex(s.SafetyError, "unsupported_broker_refusal"):
                self.ledger.mark_broker_refused("buy-1", bad)
        self.assertTrue(self.ledger.mark_broker_refused("buy-1", 403))
        self.assertFalse(self.ledger.mark_broker_refused("buy-1", 403))
        self.reopen()
        intent = self.ledger.intents()[0]
        self.assertEqual(intent.status, "broker_refused")
        self.assertTrue(intent.terminal)
        self.assertTrue(intent.submit_attempted)
        self.assertIsNone(intent.broker_id)
        self.assertEqual(self.ledger.unresolved(), [])
        self.assertEqual(self.ledger.accounting().pending_buy_notional_usd, 0)
        self.assertEqual(self.ledger.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)
        with self.assertRaisesRegex(s.SafetyError, "after_definitive_refusal"):
            self.fill()

    def test_price_outside_minimum_price_variance_is_refused_before_send(self):
        for cid, price in (("sub-1", "100.0201"), ("sub-2", "0.99991")):
            with self.assertRaisesRegex(s.SafetyError, "invalid_price_increment"):
                self.reserve(cid, price=price)
        self.assertEqual(self.ledger.intents(), [])
        self.reserve("ok-1", price="0.9999")  # four decimals below $1.00 are valid

    def test_documented_sub_penny_422_is_the_only_definitive_422(self):
        class Exempt(s.Ledger):  # the native-fault harness's FaultLedger shape
            def _check_price_increment(self, client_id, price):
                if client_id != "c04":
                    super()._check_price_increment(client_id, price)
        self.ledger.close()
        self.ledger = Exempt(self.db)
        with self.assertRaisesRegex(s.SafetyError, "invalid_price_increment"):
            self.reserve("other", price="100.0201")
        self.reserve("c04", price="100.0201")
        self.reserve("valid", price="100.02")
        for cid in ("c04", "valid"):
            self.ledger.request_budget(self.now, "submit", cid)
        for status, refusal in [(422, None), (422, "other"), (403, s.SUB_PENNY_REFUSAL), (400, s.SUB_PENNY_REFUSAL)]:
            with self.assertRaisesRegex(s.SafetyError, "unsupported_broker_refusal"):
                self.ledger.mark_broker_refused("c04", status, refusal)
        # The refusal must agree with the intent's own durable price.
        with self.assertRaisesRegex(s.SafetyError, "refusal_contradicts_intent_price"):
            self.ledger.mark_broker_refused("valid", 422, s.SUB_PENNY_REFUSAL)
        self.assertTrue(self.ledger.mark_broker_refused("c04", 422, s.SUB_PENNY_REFUSAL))
        self.assertFalse(self.ledger.mark_broker_refused("c04", 422, s.SUB_PENNY_REFUSAL))
        statuses = {i.client_id: i.status for i in self.ledger.intents()}
        self.assertEqual(statuses, {"c04": "broker_refused", "valid": "reserved"})
        payload = json.loads(self.ledger.db.execute(
            "SELECT payload FROM events WHERE kind='broker_refused' AND client_id='c04'").fetchone()[0])
        self.assertEqual((payload["http_status"], payload["refusal"]), (422, s.SUB_PENNY_REFUSAL))
        self.assertEqual(self.ledger.accounting().cash_delta_usd, 0)
        self.assertEqual(self.ledger.positions(), {})

    def test_wide_quote_values_held_loss_but_does_not_block_owned_exit(self):
        self.reserve()
        self.fill()
        wide = self.quote(bid="74", ask="100")
        state = self.ledger.mark_to_market([wide], self.now)
        self.assertEqual(state.unrealized_pnl_usd, -26)
        self.assertEqual(state.gross_loss_usd, 26)
        self.assertEqual(state.halted_reason, "gross_loss_cap_reached")
        self.reserve("sell-1", side="sell", price="73.99", quote=wide)
        self.validate("sell-1", quote=wide)

    def test_nonheld_wide_mark_does_not_halt_but_wide_entry_still_refused(self):
        wide = self.quote("QQQ", bid="90", ask="100")
        state = self.ledger.mark_to_market([wide], self.now)
        self.assertIsNone(state.halted_reason)
        with self.assertRaisesRegex(s.SafetyError, "quote_spread_exceeds_cap"):
            self.reserve("buy-QQQ", symbol="QQQ", quote=wide)
        self.reserve()
        with self.assertRaisesRegex(s.SafetyError, "quote_spread_exceeds_cap"):
            self.validate(quote=self.quote(bid="90", ask="100"))

    def test_next_trial_retains_loss_cash_and_request_budget(self):
        self.reserve()
        self.ledger.request_budget(self.now, "submit", "buy-1")
        self.fill()
        self.reserve("sell-1", side="sell", price="99", quote=self.quote(bid="99", ask="99.01"))
        self.ledger.request_budget(self.now, "submit", "sell-1")
        self.fill("sell-1", price="99")
        before = self.ledger.accounting()
        self.now += 1
        self.ledger.begin_next_trial(self.now, "next-day-2")
        self.reopen()
        after = self.ledger.accounting()
        self.assertEqual(after, before)
        self.assertEqual(self.ledger.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 2)
        self.assertEqual(self.ledger.start_trial(self.now + 1), self.now)
        with self.assertRaisesRegex(s.SafetyError, "trial_id_already_used"):
            self.ledger.begin_next_trial(self.now + 1, "next-day-2")
        for _ in range(178):
            self.assertEqual(self.ledger.request_budget(self.now, "submit"), 0)
        self.assertGreater(self.ledger.request_budget(self.now, "submit"), 0)

    def test_next_trial_refuses_unresolved_position_and_loss_halt(self):
        self.reserve()
        with self.assertRaisesRegex(s.SafetyError, "flat_and_terminal"):
            self.ledger.begin_next_trial(self.now, "next-1")
        self.fill()
        with self.assertRaisesRegex(s.SafetyError, "flat_and_terminal"):
            self.ledger.begin_next_trial(self.now, "next-1")
        self.reserve("sell-1", side="sell", price="99.99")
        self.fill("sell-1")
        self.ledger.freeze("gross_loss_cap_reached")
        with self.assertRaisesRegex(s.SafetyError, "cannot_clear_risk_halt"):
            self.ledger.begin_next_trial(self.now, "next-1")
        self.assertEqual(self.ledger.db.execute("SELECT COUNT(*) FROM trials").fetchone()[0], 0)

    def test_resume_held_trial_continues_a_non_flat_held_overnight_position(self):
        """S2: runner.py's resumable-hold path (a prior run's phase ==
        "held_overnight") deliberately bypasses its own flat/cash guards,
        but used to then fall through to begin_next_trial -- which always
        raises against non-flat state -- defeating the whole point of the
        bypass. resume_held_trial is the counterpart that continues a held
        (non-flat) trial instead of requiring flat."""
        self.reserve()
        self.fill()  # non-flat: one filled SPY position, no unresolved intents
        self.assertTrue(self.ledger.positions())
        self.now += 3600
        # begin_next_trial still correctly refuses non-flat state for the
        # ordinary (not a resumed hold) path.
        with self.assertRaisesRegex(s.SafetyError, "flat_and_terminal"):
            self.ledger.begin_next_trial(self.now, "run-2")
        # resume_held_trial continues it instead.
        self.ledger.resume_held_trial(self.now, "run-2")
        self.assertTrue(self.ledger.positions())  # the held position survives, adopted not reset
        self.assertEqual(self.ledger.db.execute(
            "SELECT COUNT(*) FROM trials WHERE trial_id='run-2'").fetchone()[0], 1)

    def test_resume_held_trial_still_enforces_risk_halt_and_clock_guards(self):
        """Every guard except the flat/terminal check stays enforced for a
        resumed hold: trial_id uniqueness, clock monotonicity and an actual
        (non recovery_only) risk halt."""
        self.reserve()
        self.fill()
        self.ledger.freeze("gross_loss_cap_reached")
        with self.assertRaisesRegex(s.SafetyError, "cannot_clear_risk_halt"):
            self.ledger.resume_held_trial(self.now + 1, "run-2")

    def test_two_invocation_sequence_run_one_holds_run_two_resumes_and_proceeds(self):
        """The exact scenario S2 describes: run 1 ends held_overnight (a
        broker snapshot with an open position gets adopted mid-run via
        Ledger.adopt_broker_snapshot -- D1's path); run 2 starts against the
        same durable ledger, adopts (idempotently) the still-open position
        from a fresh broker snapshot, and proceeds (begins its own trial
        window) without raising."""
        # Run 1: adopt a non-flat broker snapshot (the D1 startup-reconciliation
        # path used under overnight_holds) and end the run without ever
        # calling begin_next_trial again (this IS the first trial).
        snapshot = {"account": {"cash": "9500", "buying_power": "9500", "equity": "10000"},
                   "positions": [{"symbol": "SPY", "qty": "1", "avg_entry_price": "500.00"}],
                   "orders": []}
        self.ledger.adopt_broker_snapshot(snapshot, self.now)
        self.assertTrue(self.ledger.positions())
        self.assertEqual(self.ledger.unresolved(), [])

        # Run 2, a later invocation against the same durable ledger file
        # (simulated here in-process; the resumable-hold gate in runner.py
        # itself is exercised by the resumable_hold flag, not repeated
        # here). A fresh broker snapshot for the new invocation still shows
        # the same open SPY position -- adopt_broker_snapshot is idempotent
        # (test_seeded_order_already_present_is_not_duplicated already
        # covers the open-order side of that for adopted orders).
        run_two_now = self.now + 3600 * 12  # well past the run 1 window
        self.ledger.resume_held_trial(run_two_now, "run-2")
        self.ledger.adopt_broker_snapshot(snapshot, run_two_now)
        self.assertEqual(self.ledger.positions()["SPY"].qty, D("1"))
        self.ledger.mark_to_market([self.quote("SPY", bid="500", ask="500.01", at=run_two_now)], run_two_now)
        # The resumed trial proceeds normally: a fresh order can still be
        # reserved (the ledger is not stuck refusing admissions).
        reserved = self.ledger.reserve_intent(
            "buy-2", "AAPL", "buy", "1", "190.00",
            quote=self.quote("AAPL", bid="189.99", ask="190.01", at=run_two_now),
            now=run_two_now, market_open=True, session_close=run_two_now + 3600)
        self.assertTrue(reserved.newly_reserved)

    def test_next_trial_clears_only_completed_recovery_only_state(self):
        self.ledger.begin_recovery(self.now)
        self.assertEqual(self.ledger.accounting().halted_reason, "recovery_only")
        self.now += 1
        self.ledger.begin_next_trial(self.now, "next-1")
        self.assertIsNone(self.ledger.accounting().halted_reason)
        self.assertIsNone(self.ledger._get("recovery_start"))
        self.assertIsNone(self.ledger._get("recovery_only"))
        self.reserve()


class LeverageRiskLimitsTests(unittest.TestCase):
    """G-e: RiskLimits.leverage / frozen_json() byte-identity and bounds."""

    PINNED_DEFAULT_FROZEN_JSON = (
        '{"capital_usd": "10000", "cleanup_seconds": 120, "max_drawdown_usd": "25", '
        '"max_gross_exposure_usd": "5000", "max_gross_loss_usd": "25", "max_held_symbols": 10, '
        '"max_order_notional_usd": "1000", "max_order_qty": "1", "max_order_qty_mode": "fixed", '
        '"max_outstanding_orders": 20, "max_rest_per_minute": 200, "max_spread_bps": "15", '
        '"max_submits_per_minute": 180, "min_entry_close_seconds": 300, "overnight_gross_multiple": "1", '
        '"quote_max_age_seconds": 3, "trial_seconds": 300}')

    def leverage_policy(self, max_leverage="4", overnight_holds=False):
        import leverage as lev
        block = lev.CANONICAL_V1_BLOCK
        capital, gross_multiple = D("10000"), min(D(max_leverage), D("2")) if overnight_holds else D(max_leverage)
        config = {"max_leverage": max_leverage, "capital_usd": "10000",
                  "max_gross_exposure_usd": str(int(capital * gross_multiple)), "leverage_policy": block}
        session_policy = {"overnight_holds": overnight_holds, "overnight_gross_multiple": D("1.0")}
        return lev.validate_leverage_policy(config, session_policy)

    def test_default_frozen_json_matches_pinned_bdd04ca_literal(self):
        self.assertEqual(s.RiskLimits().frozen_json(), self.PINNED_DEFAULT_FROZEN_JSON)

    def test_ledger_opens_with_pre_change_meta_limits_bytes(self):
        db = Path(tempfile.mkdtemp()) / "pre.sqlite3"
        ledger = s.Ledger(db)  # writes the current (== pre-G-e for the default) frozen bytes
        ledger.close()
        reopened = s.Ledger(db)  # must not raise persisted_risk_limits_differ
        reopened.close()

    def test_risklimits_refuses_gross_above_capital_without_leverage_unchanged(self):
        with self.assertRaises(s.SafetyError):
            s.RiskLimits(max_gross_exposure_usd=D("10001"))  # capital_usd default is 10000

    def test_risklimits_with_2x_policy_accepts_exactly_2x_refuses_above(self):
        policy = self.leverage_policy("2")
        ok = s.RiskLimits(max_gross_exposure_usd=D("20000"), max_order_notional_usd=D("2000"),
                          leverage=policy)
        self.assertEqual(ok.max_gross_exposure_usd, D("20000"))
        with self.assertRaises(s.SafetyError):
            s.RiskLimits(max_gross_exposure_usd=D("20000.01"), max_order_notional_usd=D("2000"), leverage=policy)

    def test_risklimits_refuses_leverage_above_4(self):
        import leverage as lev
        bad = replace(self.leverage_policy("4"), max_leverage=D("4.5"))
        with self.assertRaises(s.SafetyError):
            s.RiskLimits(max_gross_exposure_usd=D("20000"), max_order_notional_usd=D("2000"), leverage=bad)


class LeverageLedgerTests(unittest.TestCase):
    """G-e: reserve_intent/validate_pending under a validated leverage policy.

    RTH timestamp 1772550000.0 = 2026-03-03 15:00 UTC (10:00 ET), a
    classified RTH tick in sessions.py's frozen 2026 calendar.
    """
    RTH_NOW = 1772550000.0

    def tearDown(self):
        tmp = getattr(self, "tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def leverage_policy(self, max_leverage="4"):
        import leverage as lev
        capital = D("10000")
        config = {"max_leverage": max_leverage, "capital_usd": "10000",
                  "max_gross_exposure_usd": str(int(capital * D(max_leverage))),
                  "leverage_policy": lev.CANONICAL_V1_BLOCK}
        session_policy = {"overnight_holds": False, "overnight_gross_multiple": D("1.0")}
        return lev.validate_leverage_policy(config, session_policy)

    def make_ledger(self, max_leverage="4", **overrides):
        policy = self.leverage_policy(max_leverage)
        capital = D("10000")
        kwargs = dict(capital_usd=capital, max_gross_exposure_usd=capital * D(max_leverage),
                     max_order_notional_usd=D("10000"), max_order_qty=D("100"),
                     max_drawdown_usd=D("100"), max_gross_loss_usd=D("100"), leverage=policy)
        kwargs.update(overrides)
        limits = s.RiskLimits(**kwargs)
        self.tmp = tempfile.TemporaryDirectory()
        ledger = s.Ledger(Path(self.tmp.name) / "lev.sqlite3", limits)
        ledger.start_trial(self.RTH_NOW)
        return ledger

    def quote(self, symbol="SPY", bid="50", ask="50.02", at=None):
        return s.Quote(symbol, bid, ask, self.RTH_NOW if at is None else at)

    def test_reserve_intent_under_2x_admits_to_equity_times_2_refuses_beyond(self):
        ledger = self.make_ledger("2")
        # equity == capital == 10000; envelope == 2 -> cap 20000.
        ledger.reserve_intent("b1", "SPY", "buy", "100", "50.02", quote=self.quote(),
                              now=self.RTH_NOW, market_open=True, session_close=self.RTH_NOW + 3600)
        ledger.reserve_intent("b2", "QQQ", "buy", "100", "50.02", quote=self.quote("QQQ"),
                              now=self.RTH_NOW, market_open=True, session_close=self.RTH_NOW + 3600)
        # 2 x 5002 = 10004; a third same-size order would push gross past 20000.
        ledger.reserve_intent("b3", "DIA", "buy", "100", "50.02", quote=self.quote("DIA"),
                              now=self.RTH_NOW, market_open=True, session_close=self.RTH_NOW + 3600)
        # 3 x 5002 = 15006, still under 20000; a 4th pushes to 20008 > 20000.
        with self.assertRaisesRegex(s.SafetyError, "aggregate_exposure_cap_exceeded"):
            ledger.reserve_intent("b4", "IWM", "buy", "100", "50.02", quote=self.quote("IWM"),
                                  now=self.RTH_NOW, market_open=True, session_close=self.RTH_NOW + 3600)
        ledger.close()

    def test_order_notional_cap_still_binds_tighter_than_envelope(self):
        ledger = self.make_ledger("4", max_order_notional_usd=D("500"))
        with self.assertRaisesRegex(s.SafetyError, "order_size_cap_exceeded"):
            ledger.reserve_intent("b1", "SPY", "buy", "100", "50.02", quote=self.quote(),
                                  now=self.RTH_NOW, market_open=True, session_close=self.RTH_NOW + 3600)
        ledger.close()

    def test_ladder_zero_blocks_buy_but_sells_and_no_risk_halt(self):
        ledger = self.make_ledger("4")
        ledger.reserve_intent("b1", "SPY", "buy", "2", "50.02", quote=self.quote(),
                              now=self.RTH_NOW, market_open=True, session_close=self.RTH_NOW + 3600)
        ledger.record_order("b1", "broker-b1", "filled", "2", "50.02")
        # Peak at bid=60 (unrealized ~+20), then mark down to bid=15
        # (unrealized ~-70) -> drawdown ~90 (fraction 0.9 of
        # max_drawdown_usd=100), inside the ladder's zero step
        # (>=0.75, canonical) but still below the hard 1.0 drawdown_cap_reached halt.
        ledger.mark_to_market([s.Quote("SPY", "60", "60.02", self.RTH_NOW + 1)], self.RTH_NOW + 1)
        low = ledger.mark_to_market([s.Quote("SPY", "15", "15.02", self.RTH_NOW + 2)], self.RTH_NOW + 2)
        self.assertGreaterEqual(low.drawdown_usd, D("75"))
        self.assertLess(low.drawdown_usd, D("100"))
        self.assertIsNone(low.halted_reason)  # below the hard drawdown_cap_reached halt
        with self.assertRaisesRegex(s.SafetyError, "leverage_ceiling_zero"):
            ledger.reserve_intent("b2", "QQQ", "buy", "1", "50.02", quote=self.quote("QQQ"),
                                  now=self.RTH_NOW + 2, market_open=True, session_close=self.RTH_NOW + 3600)
        # A sell of the held position is still admitted (never gated by leverage).
        sold = ledger.reserve_intent("s1", "SPY", "sell", "1", "15.00",
                                     quote=s.Quote("SPY", "15", "15.02", self.RTH_NOW + 2),
                                     now=self.RTH_NOW + 2, market_open=True, session_close=self.RTH_NOW + 3600)
        self.assertEqual(sold.side, "sell")
        self.assertIsNone(ledger.accounting().halted_reason)
        ledger.close()

    def test_validate_pending_refuses_after_ladder_stepdown(self):
        ledger = self.make_ledger("4")
        ledger.reserve_intent("b1", "SPY", "buy", "2", "50.02", quote=self.quote(),
                              now=self.RTH_NOW, market_open=True, session_close=self.RTH_NOW + 3600)
        ledger.record_order("b1", "broker-b1", "filled", "2", "50.02")
        # Reserve a second buy while the ladder is still fully open.
        ledger.reserve_intent("b2", "QQQ", "buy", "1", "50.02", quote=self.quote("QQQ"),
                              now=self.RTH_NOW + 1, market_open=True, session_close=self.RTH_NOW + 3600)
        # Drive drawdown to the ladder's zero step (>=0.75, <1.0) before validate_pending.
        ledger.mark_to_market([s.Quote("SPY", "60", "60.02", self.RTH_NOW + 2)], self.RTH_NOW + 2)
        ledger.mark_to_market([s.Quote("SPY", "15", "15.02", self.RTH_NOW + 3),
                               s.Quote("QQQ", "50", "50.02", self.RTH_NOW + 3)], self.RTH_NOW + 3)
        with self.assertRaisesRegex(s.SafetyError, "leverage_ceiling_zero"):
            ledger.validate_pending("b2", quote=self.quote("QQQ", at=self.RTH_NOW + 3), now=self.RTH_NOW + 3,
                                    market_open=True, session_close=self.RTH_NOW + 3600)
        ledger.close()

    def test_stop_file_and_halts_still_bind_under_policy(self):
        ledger = self.make_ledger("4")
        stop = Path(self.tmp.name) / "STOP"
        stop.write_text("halt")
        with self.assertRaisesRegex(s.SafetyError, "stop_blocks_entry"):
            ledger.reserve_intent("b1", "SPY", "buy", "1", "50.02", quote=self.quote(),
                                  now=self.RTH_NOW, market_open=True, session_close=self.RTH_NOW + 3600,
                                  stop_file=stop)
        stop.unlink()
        ledger.close()

    def test_timestamp_outside_calendar_fails_closed_under_policy_default_unaffected(self):
        ledger = self.make_ledger("4")
        outside = 1_800_000_000.0  # year 2027, outside the frozen 2026 calendar
        ledger2_root = Path(self.tmp.name) / "outside.sqlite3"
        outside_ledger = s.Ledger(ledger2_root, replace(s.RiskLimits(), leverage=self.leverage_policy("4"),
                                                        max_gross_exposure_usd=D("40000")))
        outside_ledger.start_trial(outside - 10)
        with self.assertRaisesRegex(s.SafetyError, "leverage_ceiling_zero"):
            outside_ledger.reserve_intent("b1", "SPY", "buy", "1", "50.02",
                                          quote=s.Quote("SPY", "50", "50.02", outside),
                                          now=outside, market_open=True, session_close=outside + 3600)
        outside_ledger.close()
        # The default (no leverage) path falls back to the ordinary cap and is unaffected.
        default_ledger = s.Ledger(Path(self.tmp.name) / "outside_default.sqlite3")
        default_ledger.start_trial(outside - 10)
        default_ledger.reserve_intent("b1", "SPY", "buy", "1", "50.02",
                                      quote=s.Quote("SPY", "50", "50.02", outside),
                                      now=outside, market_open=True, session_close=outside + 3600)
        default_ledger.close()
        ledger.close()


# The 2026-09-24 APUS sell: (qty, price, the cumulative average Alpaca reported after it).
APUS = (("26", "5.62", "5.62"), ("2", "5.61", "5.619286"), ("1", "5.61", "5.618966"))


class PerExecutionLedger(unittest.TestCase):
    """E2 in the ledger (synthetic fixtures): an execution's own qty and price book the
    fill; a cumulative average only books an advance no recorded execution explains."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = 1_800_000_000.0
        self.limits = replace(s.RiskLimits(), max_order_qty=D(100), max_order_notional_usd=D(1000),
                              max_spread_bps=D(100))
        self.db = self.root / "apus.sqlite3"
        self.ledger = s.Ledger(self.db, self.limits)
        self.ledger.start_trial(self.now)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def reserve(self, cid, side, qty, price):
        quote = s.Quote("APUS", "5.61", "5.62", self.now)
        return self.ledger.reserve_intent(cid, "APUS", side, qty, price, quote=quote, now=self.now, market_open=True,
                                          session_close=self.now + 3600, stop_file=self.root / "STOP")

    def hold_29(self):
        self.reserve("buy-1", "buy", "29", "5.64")
        self.ledger.record_order("buy-1", "b-buy", "filled", "29", "5.62",
                                 execution={"execution_id": "e-buy", "qty": "29", "price": "5.62"})
        self.reserve("sell-1", "sell", "29", "5.60")

    def execution_rows(self):
        cum, rows = 0, []
        for index, (qty, price, average) in enumerate(APUS):
            cum += int(qty)
            rows.append({"cum": str(cum), "average": average, "status": "filled" if cum == 29 else "partially_filled",
                         "execution": {"execution_id": "e-sell-%d" % index, "qty": qty, "price": price}})
        return rows

    def record(self, row, *, with_execution=True, status=None):
        return self.ledger.record_order("sell-1", "b-sell", status or row["status"], row["cum"], row["average"],
                                        timestamp=row.get("at"),
                                        execution=row["execution"] if with_execution else None)

    def events(self, kind):
        return [json.loads(r[0]) for r in self.ledger.db.execute(
            "SELECT payload FROM events WHERE kind=? ORDER BY id", (kind,))]

    def test_apus_replay_books_the_exact_executions_without_a_freeze(self):
        self.hold_29()
        for row in self.execution_rows():
            self.assertTrue(self.record(row))
        state = self.ledger.accounting()
        self.assertEqual(self.ledger.positions(), {})
        # Exact: 162.95 received for 162.98 paid, not 29 x 5.618966 = 162.950014.
        self.assertEqual((state.cash_delta_usd, state.realized_pnl_usd), (D("-0.03"), D("-0.03")))
        self.assertEqual([e["booking"] for e in self.events("order_observed")], ["executions"] * 4)
        self.assertEqual(self.ledger.intents()[1].average_price, D("5.618966"))   # the broker's own average is kept

    def test_apus_accounting_is_exact_across_delivery_sequences(self):
        sequences = {
            "stream_first": [(0, True), (1, True), (2, True), (2, False)],
            "rest_first": [(2, False), (0, True), (1, True), (2, True)],
            "duplicates": [(2, False), (2, True), (0, True), (0, True), (1, True), (2, True)],
            "restart": [(2, False), (2, True), "restart", (0, True), (1, True), "restart", (2, True)],
            "mixed": [(0, True), (1, False), (1, True), (2, True)],
            "mixed_gap": [(0, False), (1, True), (2, False), (0, True), (2, True)],
        }
        for name, sequence in sequences.items():
            with self.subTest(delivery=name):
                self.ledger.close()
                self.db = self.root / (name + ".sqlite3")
                self.ledger = s.Ledger(self.db, self.limits)
                self.ledger.start_trial(self.now)
                self.hold_29()
                rows = self.execution_rows()
                for observation in sequence:
                    if observation == "restart":
                        self.ledger.close()
                        self.ledger = s.Ledger(self.db, self.limits)
                    else:
                        index, exact = observation
                        self.record(rows[index], with_execution=exact)
                state = self.ledger.accounting()
                self.assertEqual((state.cash_delta_usd, state.realized_pnl_usd), (D("-0.03"), D("-0.03")))
                self.assertEqual(self.ledger.positions(), {})
                self.assertEqual(self.ledger.unresolved(), [])
                self.ledger.close()
                self.ledger = s.Ledger(self.db, self.limits)
                for row in rows + rows:
                    self.record(row)
                self.assertEqual(self.ledger.accounting(), state)

    def test_late_buy_executions_correct_basis_and_already_realized_pnl(self):
        for sold in (False, True):
            with self.subTest(sold=sold):
                self.ledger.close()
                self.db = self.root / ("late-buy-%s.sqlite3" % sold)
                self.ledger = s.Ledger(self.db, self.limits)
                self.ledger.start_trial(self.now)
                self.reserve("buy-1", "buy", "29", "5.64")
                self.ledger.record_order("buy-1", "b-buy", "filled", "29", "5.618966")
                if sold:
                    self.reserve("sell-1", "sell", "29", "5.60")
                    self.ledger.record_order("sell-1", "b-sell", "filled", "29", "5.62",
                        execution={"execution_id": "sale", "qty": "29", "price": "5.62"})
                self.ledger.close()
                self.ledger = s.Ledger(self.db, self.limits)
                for row in self.execution_rows():
                    self.ledger.record_order("buy-1", "b-buy", row["status"], row["cum"], row["average"],
                                             execution=row["execution"])
                state = self.ledger.accounting()
                expected = (D("0.03"), D("0.03")) if sold else (D("-162.95"), D(0))
                self.assertEqual((state.cash_delta_usd, state.realized_pnl_usd), expected)
                if sold:
                    self.assertEqual(self.ledger.positions(), {})
                else:
                    self.assertEqual(self.ledger.positions()["APUS"].cost_basis_usd, D("162.95"))

    def test_mixed_profit_gross_loss_is_exact_across_delivery_sequences(self):
        # Review oracle: two shares at $100, sold at $110 and $90, realize
        # zero net P&L but $10 gross loss. Gains must not refund the loss cap.
        # Reference: QuantConnect/Lean 985ef30, SecurityPortfolioModel.cs
        # (per-fill closing P&L) and TradeStatistics.cs (separate losing P&L).
        from live_manifest import read_ledger

        sequences = {
            "stream_first": [(0, True), (1, True), (1, False)],
            "rest_first": [(1, False), (0, True), (1, True)],
            "duplicates": [(1, False), (1, True), (0, True), (0, True), (1, True), (1, False)],
            "restart": [(1, False), (1, True), "restart", (0, True), "restart", (1, True)],
        }
        rows = [
            {"cum": "1", "average": "110.00", "status": "partially_filled",
             "execution": {"execution_id": "profit", "qty": "1", "price": "110.00"}},
            {"cum": "2", "average": "100.00", "status": "filled",
             "execution": {"execution_id": "loss", "qty": "1", "price": "90.00"}},
        ]
        limits = replace(self.limits, max_gross_loss_usd=D("5"), max_drawdown_usd=D("100"))
        quote = s.Quote("APUS", "100.00", "100.01", self.now)
        admission = dict(quote=quote, now=self.now, market_open=True,
                         session_close=self.now + 3600, stop_file=self.root / "STOP")
        for name, sequence in sequences.items():
            with self.subTest(delivery=name):
                self.ledger.close()
                self.db = self.root / ("mixed-profit-" + name + ".sqlite3")
                self.ledger = s.Ledger(self.db, limits)
                self.ledger.start_trial(self.now)
                self.ledger.reserve_intent("buy-1", "APUS", "buy", "2", "100.00", **admission)
                self.ledger.record_order("buy-1", "b-buy", "filled", "2", "100.00",
                                         execution={"execution_id": "basis", "qty": "2", "price": "100.00"})
                self.ledger.reserve_intent("sell-1", "APUS", "sell", "2", "90.00", **admission)
                self.ledger.reserve_intent("pending-buy", "APUS", "buy", "1", "100.00", **admission)
                for observation in sequence:
                    if observation == "restart":
                        self.ledger.close()
                        self.ledger = s.Ledger(self.db, limits)
                    else:
                        index, exact = observation
                        self.record(rows[index], with_execution=exact)
                state = self.ledger.accounting()
                amounts = (state.cash_delta_usd, state.realized_pnl_usd,
                           state.cumulative_realized_loss_usd, state.gross_loss_usd)
                self.assertTrue(all(isinstance(value, D) for value in amounts))
                self.assertEqual(amounts, (D("0.00"), D("0.00"), D("10.00"), D("10.00")))
                self.assertEqual(self.ledger.positions(), {})
                self.assertEqual(state.halted_reason, "gross_loss_cap_reached")
                # Reopening and redelivering either source cannot add another loss
                # or erase the corrected accounting/halt.
                self.ledger.close()
                self.ledger = s.Ledger(self.db, limits)
                for row in rows + rows:
                    self.assertFalse(self.record(row))
                self.assertFalse(self.record(rows[-1], with_execution=False))
                self.assertEqual(self.ledger.accounting(), state)
                self.assertEqual(self.ledger.mark_to_market([], self.now), state)
                self.assertEqual(self.ledger.halted_reason(), "gross_loss_cap_reached")
                report = read_ledger(self.db)
                self.assertEqual(D(report["realized_loss_usd"]), D("10.00"))
                self.assertEqual(report["halted_reason"], "gross_loss_cap_reached")
                with self.assertRaisesRegex(s.SafetyError, "^gross_loss_cap_reached$"):
                    self.ledger.reserve_intent("blocked-buy", "APUS", "buy", "1", "100.00", **admission)
                with self.assertRaisesRegex(s.SafetyError, "^gross_loss_cap_reached$"):
                    self.ledger.validate_pending("pending-buy", **admission)
                self.ledger.mark_not_sent("pending-buy", "test_finished")
                for begin in (self.ledger.begin_next_trial, self.ledger.resume_held_trial):
                    with self.assertRaisesRegex(s.SafetyError, "^next_trial_cannot_clear_risk_halt$"):
                        begin(self.now + 1, "next-trial")

    def test_mixed_profit_replay_preserves_basis_at_each_booking(self):
        self.ledger.adopt_broker_snapshot(
            {"positions": [{"symbol": "APUS", "qty": "3", "avg_entry_price": "100.00"}]}, self.now)
        admission = dict(quote=s.Quote("APUS", "100.00", "100.01", self.now), now=self.now,
                         market_open=True, session_close=self.now + 3600, stop_file=self.root / "STOP")
        self.ledger.reserve_intent("sell-1", "APUS", "sell", "3", "90.00", **admission)
        # The first two executions use the adopted $100 basis. A later buy
        # changes only the third execution's basis to $110.
        self.ledger.record_order("sell-1", "b-sell", "partially_filled", "2", "100.00")
        self.ledger.reserve_intent("buy-1", "APUS", "buy", "1", "120.00", **admission)
        self.ledger.record_order("buy-1", "b-buy", "filled", "1", "120.00",
                                 execution={"execution_id": "new-basis", "qty": "1", "price": "120.00"})
        self.ledger.record_order("sell-1", "b-sell", "filled", "3", "100.00")
        self.ledger.close()
        self.ledger = s.Ledger(self.db, self.limits)
        rows = [
            {"cum": "1", "average": "110.00", "status": "partially_filled",
             "execution": {"execution_id": "profit", "qty": "1", "price": "110.00"}},
            {"cum": "2", "average": "100.00", "status": "partially_filled",
             "execution": {"execution_id": "loss", "qty": "1", "price": "90.00"}},
            {"cum": "3", "average": "100.00", "status": "filled",
             "execution": {"execution_id": "later-loss", "qty": "1", "price": "100.00"}},
        ]
        for row in reversed(rows):
            self.record(row)
        state = self.ledger.accounting()
        # +$10, -$10, -$10, with one share still held at $110. Adopted
        # holdings predate the cash ledger: $300 sales less the $120 buy.
        self.assertEqual((state.cash_delta_usd, state.realized_pnl_usd, state.cumulative_realized_loss_usd),
                         (D("180.00"), D("-10.00"), D("20.00")))
        position = self.ledger.positions()["APUS"]
        self.assertEqual((position.qty, position.cost_basis_usd), (D("1"), D("110.00")))
        self.ledger.close()
        self.ledger = s.Ledger(self.db, self.limits)
        for row in rows:
            self.assertFalse(self.record(row))
        self.assertEqual(self.ledger.accounting(), state)

    def test_pre_fix_execution_accounting_marker_rederives_loss_once(self):
        self.ledger.adopt_broker_snapshot(
            {"positions": [{"symbol": "APUS", "qty": "2", "avg_entry_price": "100"}]}, self.now)
        self.ledger.reserve_intent("sell-1", "APUS", "sell", "2", "90",
                                   quote=s.Quote("APUS", "100", "100.01", self.now), now=self.now,
                                   market_open=True, session_close=self.now + 3600, stop_file=self.root / "STOP")
        rows = [
            {"cum": "1", "average": "110", "status": "partially_filled",
             "execution": {"execution_id": "profit", "qty": "1", "price": "110"}},
            {"cum": "2", "average": "100", "status": "filled",
             "execution": {"execution_id": "loss", "qty": "1", "price": "90"}},
        ]
        self.record(rows[-1], with_execution=False)
        for row in rows:
            self.record(row)
        # Persist the pre-fix checkpoint with the old netted-loss result.
        self.ledger.db.execute("DELETE FROM meta WHERE key LIKE 'execution_accounting:%'")
        self.ledger.db.execute("INSERT INTO meta VALUES ('execution_accounting:sell-1', '2')")
        self.ledger.db.execute("UPDATE meta SET value='0' WHERE key='realized_loss'")
        self.ledger.close()
        self.ledger = s.Ledger(self.db, self.limits)
        reconciliations = len(self.events("execution_accounting_reconciled"))
        self.record(rows[-1])
        state = self.ledger.accounting()
        self.assertEqual((state.cash_delta_usd, state.realized_pnl_usd, state.cumulative_realized_loss_usd),
                         (D("200"), D("0"), D("10")))
        self.assertEqual(self.ledger.positions(), {})
        self.assertEqual(len(self.events("execution_accounting_reconciled")), reconciliations + 1)
        self.ledger.close()
        self.ledger = s.Ledger(self.db, self.limits)
        before = tuple(self.ledger.db.iterdump())
        for row in rows + rows:
            self.assertFalse(self.record(row))
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        self.assertEqual(self.ledger.accounting(), state)


    def test_uncovered_rest_booking_survives_another_orders_execution_replay(self):
        self.ledger.close()
        limits = replace(self.limits, max_gross_loss_usd=D("100"), max_drawdown_usd=D("100"))
        self.db = self.root / "uncovered.sqlite3"
        self.ledger = s.Ledger(self.db, limits)
        self.ledger.start_trial(self.now)
        self.ledger.adopt_broker_snapshot(
            {"positions": [{"symbol": "APUS", "qty": "4", "avg_entry_price": "100"}]}, self.now)
        admission = dict(now=self.now, market_open=True, session_close=self.now + 3600,
                         stop_file=self.root / "STOP")
        self.ledger.reserve_intent("X", "APUS", "sell", "2", "80",
                                   quote=s.Quote("APUS", "130", "130.01", self.now), **admission)
        for cid, side, qty, price in (("sell-1", "sell", "2", "90"), ("B", "buy", "1", "130")):
            self.ledger.reserve_intent(cid, "APUS", side, qty, price,
                                       quote=s.Quote("APUS", "130", "130.01", self.now), **admission)
        # X is REST-only: a mixed +10/-20 pair is known only as 2 @ 95.
        # Its provisional -10 realized / 10 loss must survive Y's replay (#355 review F4).
        self.ledger.record_order("X", "b-X", "filled", "2", "95", timestamp=self.now + 10)
        x_state = self.ledger.accounting()
        self.assertEqual((x_state.cash_delta_usd, x_state.realized_pnl_usd, x_state.cumulative_realized_loss_usd),
                         (D("190"), D("-10"), D("10")))
        self.assertEqual(self.ledger.positions()["APUS"].qty, D("2"))
        x_intent = next(i for i in self.ledger.intents() if i.client_id == "X")
        x_bookings = [e for e in self.events("order_observed") if e["broker_id"] == "b-X"]
        self.ledger.record_order("B", "b-B", "filled", "1", "130", timestamp=self.now + 2,
                                 execution={"execution_id": "B", "qty": "1", "price": "130"})
        rows = [
            {"cum": "1", "average": "110", "status": "partially_filled", "at": self.now + 1,
             "execution": {"execution_id": "A", "qty": "1", "price": "110"}},
            {"cum": "2", "average": "100", "status": "filled", "at": self.now + 3,
             "execution": {"execution_id": "C", "qty": "1", "price": "90"}},
        ]
        self.record(rows[-1], with_execution=False)
        self.ledger.close()
        self.ledger = s.Ledger(self.db, limits)
        for row in reversed(rows):
            self.record(row)
        state = self.ledger.accounting()
        self.assertEqual(next(i for i in self.ledger.intents() if i.client_id == "X"), x_intent)
        self.assertEqual([e for e in self.events("order_observed") if e["broker_id"] == "b-X"], x_bookings)
        # Subtract Y's oracle under observation-order replay: B (observed first) raises the basis to
        # 330/3 = 110 before sell-1's A @ 110 (0) and C @ 90 (-20): 70 cash, -20 P&L, 20 loss, 1 @ 110.
        # Execution-order replay (A before B) is a recorded follow-up, not this PR.
        self.assertEqual((state.cash_delta_usd - D("70"), state.realized_pnl_usd + D("20"),
                          state.cumulative_realized_loss_usd - D("20")), (D("190"), D("-10"), D("10")))
        position = self.ledger.positions()["APUS"]
        self.assertEqual((position.qty, position.cost_basis_usd), (D("1"), D("110")))


    def test_accounting_replay_quantity_mismatch_rolls_back_late_execution(self):
        self.reserve("buy-1", "buy", "29", "5.64")
        self.ledger.record_order("buy-1", "b-buy", "filled", "29", "5.618966")
        # A damaged materialized position disagrees with the durable booking journal.
        self.ledger.db.execute("UPDATE positions SET qty='28' WHERE symbol='APUS'")
        before = tuple(self.ledger.db.iterdump())

        with self.assertRaisesRegex(s.SafetyError, "^accounting_replay_quantity_mismatch$"):
            self.ledger.record_order("buy-1", "b-buy", "filled", "29", "5.618966",
                                     execution={"execution_id": "late-buy", "qty": "29", "price": "5.61"})

        # The new execution, replay checkpoint, accounting and journal all roll back.
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        self.ledger.close()
        self.ledger = s.Ledger(self.db, self.limits)
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)

    def test_accounting_replay_short_position_rolls_back_late_execution(self):
        self.reserve("buy-1", "buy", "29", "5.64")
        self.ledger.record_order("buy-1", "b-buy", "filled", "29", "5.618966")
        self.reserve("sell-1", "sell", "29", "5.60")
        self.ledger.record_order("sell-1", "b-sell", "filled", "29", "5.62",
                                 execution={"execution_id": "sale", "qty": "29", "price": "5.62"})
        # Corrupt the journal order so the sale precedes its buy. Late execution
        # coverage must refuse a replay whose first booking would create a short.
        self.ledger.db.execute(
            "UPDATE events SET id=(SELECT MAX(id)+1 FROM events) "
            "WHERE kind='order_observed' AND client_id='buy-1'")
        before = tuple(self.ledger.db.iterdump())

        with self.assertRaisesRegex(s.SafetyError, "^accounting_replay_would_make_short_position$"):
            self.ledger.record_order("buy-1", "b-buy", "filled", "29", "5.618966",
                                     execution={"execution_id": "late-buy", "qty": "29", "price": "5.61"})

        self.assertEqual(tuple(self.ledger.db.iterdump()), before)
        self.ledger.close()
        self.ledger = s.Ledger(self.db, self.limits)
        self.assertEqual(tuple(self.ledger.db.iterdump()), before)

    def test_rounded_average_at_the_limit_does_not_freeze_either_path(self):
        # 26 @ 5.62 then 3 @ 5.60 against a 5.60 sell limit: Alpaca reports 5.617931 (162.92/29
        # rounded), and the old derivation priced the last 3 at 5.599999, below the limit.
        for with_execution in (True, False):
            with self.subTest(with_execution=with_execution):
                self.ledger.close()
                self.db = self.root / ("limit-%s.sqlite3" % with_execution)
                self.ledger = s.Ledger(self.db, self.limits)
                self.ledger.start_trial(self.now)
                self.hold_29()
                first = {"cum": "26", "average": "5.62", "status": "partially_filled",
                         "execution": {"execution_id": "x1", "qty": "26", "price": "5.62"}}
                last = {"cum": "29", "average": "5.617931", "status": "filled",
                        "execution": {"execution_id": "x2", "qty": "3", "price": "5.60"}}
                self.record(first, with_execution=with_execution)
                self.record(last, with_execution=with_execution)
                self.assertEqual(self.ledger.positions(), {})
                self.assertIsNone(self.ledger.halted_reason())
                expected = D("-0.06") if with_execution else D("-0.060001")   # derived: 29 x 5.617931 - 162.98
                self.assertEqual(self.ledger.accounting().cash_delta_usd, expected)

    def test_shuffled_duplicated_and_dropped_executions_never_double_book(self):
        self.hold_29()
        e1, e2, e3 = self.execution_rows()
        self.assertTrue(self.record(e3))     # E3 first: 29 booked from the averages (E1, E2 unknown yet)
        self.assertFalse(self.record(e1))    # an older cumulative quantity: recorded, never booked again
        self.assertFalse(self.record(e1))    # a duplicate delivery: no-op
        self.assertEqual(self.ledger.positions(), {})
        self.assertEqual(self.ledger.intents()[1].filled_qty, D(29))
        self.assertEqual([e["booking"] for e in self.events("order_observed")][-1], "cumulative_average")
        self.assertEqual(len(self.events("execution_recorded")), 3)   # buy, E3, E1; E2 was never delivered
        state = self.ledger.accounting()
        self.assertEqual(state.cash_delta_usd, D("29") * D("5.618966") - D("162.98"))

    def test_rest_read_ahead_of_the_stream_fill_is_consistent(self):
        self.reserve("buy-1", "buy", "3", "5.64")
        rest = self.ledger.record_order("buy-1", "b-1", "canceled", "2", "5.62")        # REST cancel read first
        stream = self.ledger.record_order("buy-1", "b-1", "partially_filled", "2", "5.62",
                                          execution={"execution_id": "e-1", "qty": "2", "price": "5.62"})
        self.assertTrue(rest)
        self.assertFalse(stream)     # the execution is recorded; no terminal contradiction
        self.assertEqual(self.ledger.intents()[0].status, "canceled")
        self.assertEqual(self.ledger.positions()["APUS"].qty, D(2))
        self.assertEqual(len(self.events("execution_recorded")), 1)
        with self.assertRaisesRegex(s.SafetyError, "terminal_order_contradiction"):   # a later fill still freezes
            self.ledger.record_order("buy-1", "b-1", "canceled", "3", "5.62")

    def test_conflicting_or_overlapping_executions_and_limit_violations_fail_closed(self):
        self.hold_29()
        e1 = self.execution_rows()[0]
        self.record(e1)
        cases = [({"execution_id": "e-sell-0", "qty": "26", "price": "5.63"}, "26", "execution_conflict"),
                 ({"execution_id": "other", "qty": "26", "price": "5.61"}, "26", "execution_conflict"),
                 ({"execution_id": "e-sell-0", "qty": "2", "price": "5.61"}, "28", "execution_conflict"),
                 ({"execution_id": "e-over", "qty": "3", "price": "5.61"}, "28", "execution_overlap"),
                 ({"execution_id": "e-low", "qty": "2", "price": "5.59"}, "28", "incremental_fill_violates_limit"),
                 ({"execution_id": "e-big", "qty": "30", "price": "5.61"}, "28", "execution_exceeds_cumulative"),
                 ({"execution_id": "bad id!", "qty": "2", "price": "5.61"}, "28", "invalid_execution_identity")]
        before = self.ledger.accounting()
        for execution, cum, reason in cases:
            with self.subTest(reason=reason, execution=execution):
                with self.assertRaisesRegex(s.SafetyError, reason):
                    self.ledger.record_order("sell-1", "b-sell", "partially_filled", cum,
                                             "5.62" if cum == "26" else "5.619286", execution=execution)
                self.assertEqual(self.ledger.accounting(), before)

    def test_recorded_executions_survive_a_restart(self):
        self.hold_29()
        e1, e2, e3 = self.execution_rows()
        self.record(e1)
        self.ledger.close()
        self.ledger = s.Ledger(self.db, self.limits)
        self.assertFalse(self.record(e1))    # replayed after the restart: a no-op
        self.record(e2)
        self.record(e3)
        self.assertEqual(self.ledger.accounting().cash_delta_usd, D("-0.03"))

    def test_execution_from_observation_reads_only_complete_stream_fills(self):
        row = {"event": "partial_fill", "execution_id": "e", "event_qty": "2", "event_price": "5.61"}
        self.assertEqual(s.execution_from_observation(row), {"execution_id": "e", "qty": "2", "price": "5.61"})
        for changes in ({"event": "canceled"}, {"event": None}, {"execution_id": None}, {"event_qty": ""},
                        {"event_price": None}):
            with self.subTest(changes=changes):
                self.assertIsNone(s.execution_from_observation({**row, **changes}))
        self.assertIsNone(s.execution_from_observation({"filled_qty": "2"}))


if __name__ == "__main__":
    unittest.main()
