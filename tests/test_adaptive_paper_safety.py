"""Synthetic durable-risk tests; no credentials, sockets, or broker execution."""
from dataclasses import replace
from decimal import Decimal as D
import hashlib
import importlib.util
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


if __name__ == "__main__":
    unittest.main()
