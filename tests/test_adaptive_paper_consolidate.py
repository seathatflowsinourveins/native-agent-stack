"""Synthetic tests for booking external same-account fills; no credentials, sockets or broker."""
from dataclasses import replace
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import consolidate_external as ce  # noqa: E402
import safety as s  # noqa: E402

FINGERPRINT = "f" * 64
NOW = 1_800_000_000.0


def fill(cid, side, qty, price, at, symbol="SPY"):
    return {"client_order_id": cid, "symbol": symbol, "side": side, "qty": qty, "price": price, "filled_at": at}


ROUNDTRIPS = [fill("ext-a-1", "buy", "2", "100", "t1"), fill("ext-a-2", "sell", "1", "99", "t2"),
              fill("ext-a-3", "sell", "1", "101.5", "t3"),
              fill("ext-b-1", "buy", "1", "50", "t4", "QQQ"), fill("ext-b-2", "sell", "1", "49.4", "t5", "QQQ")]


class RecordExternalFillsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "ledger.sqlite3"
        self.ledger = s.Ledger(self.db)
        self.ledger.start_trial(NOW)

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def test_books_cash_realized_and_loss_at_average_cost(self):
        result = self.ledger.record_external_fills(ROUNDTRIPS, NOW, "separate state roots")
        state = self.ledger.accounting()
        # SPY: -200 + 99 + 101.5 = +0.5, loss 1 on the first sell; QQQ: -0.6, loss 0.6.
        self.assertEqual(state.cash_delta_usd, D("-0.1"))
        self.assertEqual(state.realized_pnl_usd, D("-0.1"))
        self.assertEqual(state.cumulative_realized_loss_usd, D("1.6"))
        self.assertEqual((result["orders"], result["fills"]), (5, 5))
        self.assertIsNone(result["halted_reason"])
        self.assertEqual(self.ledger.positions(), {})
        rows = self.ledger.db.execute("SELECT payload FROM events WHERE kind='external_fills_consolidated'").fetchall()
        self.assertEqual(len(rows), 1)
        payload = json.loads(rows[0][0])
        self.assertEqual([f["client_order_id"] for f in payload["fills"]], [f["client_order_id"] for f in ROUNDTRIPS])
        self.assertEqual(payload["reference"], "separate state roots")

    def test_second_booking_of_the_same_fills_is_refused_and_survives_restart(self):
        self.ledger.record_external_fills(ROUNDTRIPS, NOW, "first")
        self.ledger.close()
        self.ledger = s.Ledger(self.db)
        with self.assertRaisesRegex(s.SafetyError, "external_fill_already_known"):
            self.ledger.record_external_fills(ROUNDTRIPS[3:], NOW, "again")
        self.assertEqual(self.ledger.accounting().cash_delta_usd, D("-0.1"))
        self.assertEqual(self.ledger.known_client_ids(), {f["client_order_id"] for f in ROUNDTRIPS})

    def test_loss_counts_against_the_frozen_limits(self):
        self.ledger.close()
        limits = replace(s.RiskLimits(), max_gross_loss_usd=D("1.5"))
        self.ledger = s.Ledger(Path(self.tmp.name) / "limits.sqlite3", limits)
        self.ledger.start_trial(NOW)
        result = self.ledger.record_external_fills(ROUNDTRIPS, NOW, "loss")
        self.assertEqual(result["halted_reason"], "gross_loss_cap_reached")
        self.assertEqual(self.ledger.accounting().halted_reason, "gross_loss_cap_reached")

    def test_refusals_leave_the_ledger_unchanged(self):
        cases = [
            ([], "external_fills_empty"),
            ([fill("x-1", "buy", "1", "10", "t1")], "external_fills_leave_open_position"),
            ([fill("x-1", "sell", "1", "10", "t1")], "external_fill_would_make_short_position"),
            ([fill("x-1", "buy", "0.5", "10", "t1"), fill("x-2", "sell", "0.5", "10", "t2")], "external_fill_invalid"),
            ([fill("x-1", "buy", "1", "0", "t1"), fill("x-2", "sell", "1", "10", "t2")], "external_fill_invalid"),
            ([fill("x-1", "buy", "-1", "10", "t1")], "external_fill_invalid"),
            ([fill("x-1", "short", "1", "10", "t1")], "external_fill_invalid"),
            ([fill("x-1", "buy", "1", "10", "t1"), fill("x-1", "sell", "1", "10", "t2")], "external_fill_already_known"),
        ]
        for fills, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(s.SafetyError, reason):
                self.ledger.record_external_fills(fills, NOW, "refusal")
        with self.assertRaisesRegex(s.SafetyError, "external_reference_required"):
            self.ledger.record_external_fills(ROUNDTRIPS, NOW, "")
        self.assertEqual(self.ledger.accounting().cash_delta_usd, 0)
        self.assertEqual(self.ledger.db.execute(
            "SELECT COUNT(*) FROM events WHERE kind='external_fills_consolidated'").fetchone()[0], 0)

    def test_unfilled_orders_are_booked_as_known_without_cash(self):
        rows = [fill("x-0", "buy", "0", None, "t0"), *ROUNDTRIPS[3:]]
        result = self.ledger.record_external_fills(rows, NOW, "with an unfilled order")
        self.assertEqual((result["orders"], result["fills"]), (3, 2))
        self.assertEqual(self.ledger.accounting().cash_delta_usd, D("-0.6"))
        self.assertIn("x-0", self.ledger.known_client_ids())

    def test_drawdown_peak_is_tracked_per_fill(self):
        # +3 then -2.5: the batch ends at +0.5 but peaked at +3, so drawdown 2.5 >= 2 halts,
        # exactly as replaying the same fills through record_order would.
        self.ledger.close()
        limits = replace(s.RiskLimits(), max_gross_loss_usd=D("10"), max_drawdown_usd=D("2"))
        self.ledger = s.Ledger(Path(self.tmp.name) / "drawdown.sqlite3", limits)
        self.ledger.start_trial(NOW)
        rows = [fill("d-1", "buy", "1", "100", "t1"), fill("d-2", "sell", "1", "103", "t2"),
                fill("d-3", "buy", "1", "100", "t3"), fill("d-4", "sell", "1", "97.5", "t4")]
        result = self.ledger.record_external_fills(list(reversed(rows)), NOW, "peak")
        state = self.ledger.accounting()
        self.assertEqual((state.peak_pnl_usd, state.realized_pnl_usd), (D("3"), D("0.5")))
        self.assertEqual(result["halted_reason"], "drawdown_cap_reached")

    def test_external_order_matches_only_the_booked_terminal_row(self):
        self.ledger.record_external_fills([fill("x-0", "sell", "0", None, "t0"), *ROUNDTRIPS[3:]], NOW, "match")
        booked = {"client_order_id": "ext-b-1", "symbol": "QQQ", "side": "buy", "status": "filled", "filled_qty": "1"}
        self.assertTrue(self.ledger.external_order_matches(booked))
        self.assertTrue(self.ledger.external_order_matches(
            {"client_order_id": "x-0", "symbol": "SPY", "side": "sell", "status": "canceled", "filled_qty": "0"}))
        for change in ({"filled_qty": "2"}, {"status": "partially_filled"}, {"side": "sell"}, {"symbol": "SPY"},
                       {"client_order_id": "never-booked"}):
            with self.subTest(change=change):
                self.assertFalse(self.ledger.external_order_matches({**booked, **change}))

    def test_refused_unless_the_ledger_is_flat_and_the_fill_is_unknown(self):
        quote = s.Quote("SPY", "100", "100.01", NOW)
        self.ledger.reserve_intent("own-1", "SPY", "buy", "1", "100.02", quote=quote, now=NOW, market_open=True,
                                   session_close=NOW + 3600, stop_file=Path(self.tmp.name) / "STOP")
        with self.assertRaisesRegex(s.SafetyError, "external_consolidation_requires_flat_ledger"):
            self.ledger.record_external_fills(ROUNDTRIPS, NOW, "open intent")
        self.ledger.record_order("own-1", "broker-own-1", "filled", "1", "100")
        with self.assertRaisesRegex(s.SafetyError, "external_consolidation_requires_flat_ledger"):
            self.ledger.record_external_fills(ROUNDTRIPS, NOW, "open position")
        self.ledger.reserve_intent("own-2", "SPY", "sell", "1", "99.99", quote=quote, now=NOW, market_open=True,
                                   session_close=NOW + 3600, stop_file=Path(self.tmp.name) / "STOP")
        self.ledger.record_order("own-2", "broker-own-2", "filled", "1", "100")
        with self.assertRaisesRegex(s.SafetyError, "external_fill_already_known"):
            self.ledger.record_external_fills([fill("own-1", "buy", "1", "1", "t1"),
                                               fill("x-2", "sell", "1", "1", "t2")], NOW, "own id")


def broker_order(cid, side, qty, price, status="filled", symbol="SPY", at="2026-09-23T14:00:00+00:00"):
    return {"client_order_id": cid, "symbol": symbol, "side": side, "status": status,
            "filled_qty": qty, "filled_avg_price": price, "filled_at": at if D(qty) else None,
            "updated_at": at}


class HelperTests(unittest.TestCase):
    def test_external_fills_skip_known_and_unfilled_orders(self):
        orders = [broker_order("own-1", "buy", "1", "10"), broker_order("ext-1", "buy", "1", "10"),
                  broker_order("ext-2", "sell", "0", None, status="canceled"),
                  broker_order("ext-3", "sell", "1", "9.5", status="canceled")]
        fills = ce.external_fills(orders, {"own-1"})
        self.assertEqual([f["client_order_id"] for f in fills], ["ext-1", "ext-2", "ext-3"])
        self.assertEqual((fills[1]["price"], fills[1]["filled_at"]), (None, "2026-09-23T14:00:00+00:00"))
        self.assertEqual(ce.fills_cash(fills), D("-0.5"))
        self.assertEqual(ce.prefix_counts(fills), {"ext-1": 1, "ext-2": 1, "ext-3": 1})
        with self.assertRaisesRegex(SystemExit, "not terminal"):
            ce.external_fills([broker_order("ext-4", "buy", "0", None, status="new")], set())

    def test_reconciles_within_one_cent_only(self):
        self.assertEqual(ce.reconciles("998.90", "1000", "0", "-1.10"), (D("-1.10"), True))
        self.assertTrue(ce.reconciles("998.90", "1000", "0", "-1.109")[1])
        self.assertFalse(ce.reconciles("998.90", "1000", "0", "-1.12")[1])
        self.assertFalse(ce.reconciles("998.90", "1000", "0", "0")[1])


class CommandTests(unittest.TestCase):
    """main() with the broker replaced by fixed snapshots; the ledger is real."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = self.root / "config.json"
        self.config.write_bytes((SOURCE / "config.json").read_bytes())
        self.state = self.root / "state"
        self.adaptive = self.state / FINGERPRINT / "adaptive"
        self.adaptive.mkdir(parents=True)
        import runner
        _, self.limits, _ = runner.load_config(self.config)
        ledger = s.Ledger(self.adaptive / "ledger.sqlite3", self.limits)
        ledger.start_trial(NOW)
        ledger.close()
        self.meta = {"trial_id": "t", "phase": "finished", "status": "passed", "started_at": NOW,
                     "current_trial_started_at": NOW, "baseline_cash": "1000.00",
                     "config_sha256": hashlib.sha256(self.config.read_bytes()).hexdigest()}
        self.write_meta()
        self.observation = {"account": {"cash": "998.90"}, "account_identity_sha256": FINGERPRINT,
                            "positions": [], "orders": [], "open_orders_complete": True}
        self.orders = [broker_order("ext-a-1", "buy", "1", "100"), broker_order("ext-a-2", "sell", "1", "98.90"),
                       broker_order("ext-a-3", "buy", "0", None, status="canceled")]
        self.stop = patch.object(s, "DEFAULT_STOP", self.root / "locks-root" / "STOP")
        self.stop.start()

    def tearDown(self):
        self.stop.stop()
        self.tmp.cleanup()

    def write_meta(self):
        (self.adaptive / "trial.json").write_text(json.dumps(self.meta))

    def run_main(self, *extra):
        receipt = self.root / "receipt.json"
        seen = {}

        def orders(key, secret, since):
            seen["since"] = since
            return self.orders

        with patch("runner.credentials", return_value=("k", "s")), \
                patch("transport.preflight", return_value=self.observation), \
                patch.object(ce, "_broker_orders", side_effect=orders):
            code = ce.main(["--env-file", str(self.root / "unused.env"), "--config", str(self.config),
                            "--state-root", str(self.state), "--reference", "test", "--receipt", str(receipt),
                            *extra])
        return code, json.loads(receipt.read_text()), seen

    def cash_delta(self):
        ledger = s.Ledger(self.adaptive / "ledger.sqlite3", self.limits)
        try:
            return ledger.accounting().cash_delta_usd
        finally:
            ledger.close()

    def test_dry_run_reports_without_writing(self):
        code, receipt, seen = self.run_main()
        self.assertEqual(code, 0)
        self.assertFalse(receipt["applied"])
        self.assertTrue(receipt["reconciles_with_external"])
        self.assertEqual((receipt["external_orders"], receipt["external_fills"], receipt["external_cash_usd"]),
                         (3, 2, "-1.10"))
        self.assertEqual(seen["since"].timestamp(), NOW)
        self.assertEqual(self.cash_delta(), 0)
        self.assertNotIn(FINGERPRINT, json.dumps(receipt))

    def test_apply_books_and_reconciles(self):
        code, receipt, _ = self.run_main("--apply")
        self.assertEqual(code, 0)
        self.assertTrue(receipt["applied"])
        self.assertTrue(receipt["reconciled_after"])
        self.assertEqual(D(receipt["cash_gap_after_usd"]), 0)
        self.assertEqual(self.cash_delta(), D("-1.10"))
        # A rerun sees the booked fills as known: nothing external remains and cash reconciles.
        code, receipt, _ = self.run_main("--apply")
        self.assertEqual((code, receipt["external_orders"], receipt["applied"], receipt["refused"]),
                         (0, 0, False, "nothing_to_apply"))
        self.assertEqual(self.cash_delta(), D("-1.10"))
        self.next_trial_accepts_the_booked_history()

    def next_trial_accepts_the_booked_history(self):
        """The runner's own reconcile() and Controller.observe see the same broker history
        (orders since started_at) and must skip exactly the booked rows, nothing else."""
        import runner
        ledger = s.Ledger(self.adaptive / "ledger.sqlite3", self.limits)
        try:
            history = [{**o, "id": "broker-" + o["client_order_id"], "qty": o["filled_qty"] or "1",
                        "updated_at_ns": int(NOW * 1e9)} for o in self.orders]
            snapshot = {"complete": True, "orders": history, "positions": [], "account": {"cash": "998.90"}}
            self.assertTrue(runner.reconcile(ledger, snapshot, "1000.00")["cash_match"])
            controller = runner.Controller(ledger, NOW + 3600, market_open=True, clock=lambda: NOW)
            for order in history:
                controller.observe(order)
            self.assertIsNone(ledger.accounting().halted_reason)
            changed = {**history[0], "filled_qty": "2"}
            with self.assertRaisesRegex(s.SafetyError, "external_order_detected"):
                runner.reconcile(ledger, {**snapshot, "orders": [changed]}, "1000.00")
            with self.assertRaisesRegex(s.SafetyError, "external_order_detected"):
                controller.observe({**history[0], "client_order_id": "never-booked"})
            self.assertEqual(ledger.accounting().halted_reason, "external_order_detected")
        finally:
            ledger.close()

    def test_apply_refused_on_gap_mismatch_or_open_broker_state(self):
        self.observation["account"]["cash"] = "998.80"
        code, receipt, _ = self.run_main("--apply")
        self.assertEqual((code, receipt["applied"], receipt["refused"]), (3, False, "broker_not_flat_or_gap_mismatch"))
        self.observation["account"]["cash"] = "998.90"
        self.observation["positions"] = [{"symbol": "SPY", "qty": "1", "avg_entry_price": "100"}]
        code, receipt, _ = self.run_main("--apply")
        self.assertEqual((code, receipt["broker_flat"], receipt["applied"]), (3, False, False))
        self.observation["positions"], self.observation["open_orders_complete"] = [], False
        code, receipt, _ = self.run_main("--apply")
        self.assertEqual((code, receipt["broker_flat"]), (3, False))
        self.assertEqual(self.cash_delta(), 0)

    def test_refused_for_another_config_or_an_unfinished_trial(self):
        self.meta["config_sha256"] = "0" * 64
        self.write_meta()
        with self.assertRaisesRegex(SystemExit, "frozen with"):
            self.run_main()
        self.meta.update(config_sha256=hashlib.sha256(self.config.read_bytes()).hexdigest(), phase="running")
        self.write_meta()
        with self.assertRaisesRegex(SystemExit, "not finished"):
            self.run_main()


if __name__ == "__main__":
    unittest.main()
