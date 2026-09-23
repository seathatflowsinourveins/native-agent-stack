"""Local fake-transport fault checks with the real durable Ledger; no network."""
import asyncio
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
from safety import Ledger, Quote, RiskLimits, SafetyError
from recovery import recover

from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    _HERMETIC_TOKEN = patch_default_stop()


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


def proof(ledger, snapshot, baseline):
    """Independent fake-broker oracle; the integration default is runner.reconcile."""
    if not snapshot.get("complete"):
        raise SafetyError("incomplete_snapshot")
    known = {i.client_id: i for i in ledger.intents()}
    actual = {r["client_order_id"] for r in snapshot["orders"]}
    if actual - known.keys():
        raise SafetyError("external_order_detected")
    if any(i.submit_attempted and i.status not in {"not_sent", "broker_refused"}
           and i.client_id not in actual for i in known.values()):
        raise SafetyError("submitted_intent_absent")
    if {p["symbol"]: Decimal(p["qty"]) for p in snapshot["positions"]} != {s: p.qty for s, p in ledger.positions().items()}:
        raise SafetyError("position_mismatch")
    if Decimal(snapshot["account"]["cash"]) - Decimal(baseline) != ledger.accounting().cash_delta_usd:
        raise SafetyError("cash_mismatch")
    return {"positions": len(snapshot["positions"]), "open_orders": len(ledger.unresolved()),
            "cash_match": True, "positions_match": True}


class Controller:
    def __init__(self, ledger):
        self.ledger, self.clock = ledger, time.time
        self.close, self.market_open = self.clock() + 10000, True
        self.quotes, self.stop = {}, False

    def quote(self, row):
        self.quotes[row["symbol"]] = Quote(row["symbol"], row["bid"], row["ask"], row["ts_ns"] / 1e9)

    def observe(self, row):
        if row["client_order_id"] not in {i.client_id for i in self.ledger.intents()}:
            raise SafetyError("external_order_detected")
        self.ledger.record_order(row["client_order_id"], row["id"], row["status"], row["filled_qty"],
                                 row["filled_avg_price"], timestamp=row["updated_at_ns"] / 1e9)


class FakePort:
    def __init__(self, controller, mode="fill"):
        self.c, self.mode, self.ready = controller, mode, False
        self.rows, self.adopted, self.submissions, self.cancelled = {}, {}, [], []
        self.cash, self.qty = Decimal("10000"), Decimal(0)
        self.snapshots, self.stopped = 0, 0
        self.external_position = False
        self.health = {"reasons": []}

    def adopt_intents(self, intents):
        self.adopted.update({i["client_order_id"]: i for i in intents})

    async def start(self, on_quote, on_order):
        self.on_quote, self.on_order = on_quote, on_order
        self.ready = True
        self.publish_quote()

    def publish_quote(self):
        self.on_quote({"symbol": "SPY", "bid": "100.00", "ask": "100.01",
                       "ts_ns": int((self.c.clock() - (30 if self.mode == "stale" else 0)) * 1e9)})

    async def snapshot(self):
        self.snapshots += 1
        if self.mode == "slow_snapshot":
            await asyncio.sleep(5)
        for row in self.rows.values():
            self.c.observe(row)
        return {"complete": True, "account": {"cash": str(self.cash)}, "orders": list(self.rows.values()),
                "positions": ([{"symbol": "SPY", "qty": str(self.qty)}] if self.qty else []) +
                             ([{"symbol": "QQQ", "qty": "1"}] if self.external_position else [])}

    async def cancel(self, client_id):
        assert client_id in self.adopted, "never cancel an unowned order"
        self.cancelled.append(client_id)
        row = self.rows[client_id]
        if self.mode == "cancel_pending":
            row = dict(row, status="pending_cancel")
        else:
            row = dict(row, status="canceled")
        self.rows[client_id] = row
        self.c.observe(row)
        self.on_order(row)
        return row

    async def submit(self, payload):
        assert payload["side"] == "sell", "recovery must never buy"
        assert all(i.terminal for i in self.c.ledger.intents()), "cancel confirmation must precede sell"
        self.publish_quote()
        now = self.c.clock()
        intent = self.c.ledger.reserve_intent(payload["client_order_id"], "SPY", "sell", payload["qty"],
                    payload["limit_price"], quote=self.c.quotes["SPY"], now=now,
                    market_open=self.c.market_open, session_close=self.c.close)
        if self.c.ledger.request_budget(now, "submit", client_id=intent.client_id):
            raise SafetyError("fake_budget_exhausted")
        self.submissions.append(payload)
        self.adopted[intent.client_id] = payload
        if self.mode == "local_not_sent":
            class LocalRefusal(RuntimeError):
                definitive_rejection = True
                not_sent = True
            raise LocalRefusal("prevented before HTTP")
        if self.mode == "http_definitive_refusal":
            class BrokerRefusal(RuntimeError):
                definitive_rejection = True
            raise BrokerRefusal("HTTP response received; order absent")
        if self.mode == "ambiguous_submit":
            raise TimeoutError("provider secret must not escape")
        qty, price = Decimal(payload["qty"]), Decimal(payload["limit_price"])
        if self.mode == "exit_unfilled":
            filled, status, average = Decimal(0), "new", None
        else:
            filled, status, average = qty, "filled", str(price)
            self.qty -= qty
            self.cash += qty * price
        row = {**payload, "id": "broker-" + intent.client_id, "filled_qty": str(filled),
               "filled_avg_price": average, "status": status, "updated_at_ns": time.time_ns()}
        self.rows[intent.client_id] = row
        self.c.observe(row)
        self.on_order(row)
        return row

    async def stop(self):
        self.stopped += 1
        self.ready = False


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # Time budgets sized for slow CI runners: the fake port publishes one quote at start,
        # and snapshot/ledger writes before the exit can exceed a 50 ms freshness window on
        # slow disks (observed CI flakes: needs_attention instead of passed). A genuinely stale
        # quote (mode "stale", 30 s old) still fails; the deadline test keeps its own 1 s budget.
        self.ledger = Ledger(Path(self.temp.name) / "ledger.sqlite", RiskLimits(cleanup_seconds=3))
        self.controller = Controller(self.ledger)
        self.port = self.controller.port = FakePort(self.controller)
        self.config = {"cleanup_seconds": 3, "quote_max_age_seconds": 1.0, "order_timeout_seconds": .05,
                      "regular_session_only": True, "extended_hours_enabled": False,
                      "sessions": {"extended_hours": False, "overnight_holds": False,
                                  "overnight_gross_multiple": "1.0"}}
        self.meta = {"trial_id": "fault-test", "baseline_cash": "10000"}
        self.start = time.time() - 1000
        self.ledger.start_trial(self.start)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def original_buy(self, filled="1", status="filled", *, attempted=True, observed=False, cid="entry-1"):
        quote = Quote("SPY", "100", "100.01", self.start)
        intent = self.ledger.reserve_intent(cid, "SPY", "buy", "1", "100.01", quote=quote,
                    now=self.start, market_open=True, session_close=self.controller.close)
        if attempted:
            self.assertEqual(self.ledger.request_budget(self.start, "submit", client_id=cid), 0)
        qty = Decimal(filled)
        row = {"client_order_id": cid, "id": "broker-" + cid, "symbol": "SPY", "side": "buy",
               "qty": "1", "limit_price": "100.01", "filled_qty": filled,
               "filled_avg_price": "100.01" if qty else None, "status": status, "updated_at_ns": time.time_ns()}
        if attempted:
            self.port.rows[cid] = row
            self.port.qty += qty
            self.port.cash -= qty * Decimal("100.01")
            if observed:
                self.controller.observe(row)
        return intent

    def recover(self):
        result = asyncio.run(recover(self.controller, self.meta, self.config, reconcile_fn=proof))
        self.assertEqual(self.port.stopped, 1)
        self.assertTrue(self.controller.stop)
        self.assertEqual(result["buy_submissions"], 0)
        return result

    def test_crash_after_post_reconciles_original_id_without_resubmitting(self):
        self.original_buy(observed=False)
        result = self.recover()
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["flat"])
        self.assertEqual(len(self.port.submissions), 1)
        self.assertNotEqual(self.port.submissions[0]["client_order_id"], "entry-1")
        self.assertEqual(self.port.snapshots, 2)

    def test_partial_buy_cancel_then_exact_nine_decimal_exit_after_expired_trial(self):
        self.original_buy("0.123456789", "partially_filled")
        result = self.recover()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(self.port.cancelled, ["entry-1"])
        self.assertEqual(self.port.submissions[0]["qty"], "0.123456789")
        self.assertEqual(self.port.snapshots, 3)
        self.assertEqual(self.ledger.accounting().halted_reason, "recovery_only")

    def test_pending_cancel_cannot_authorize_sell(self):
        self.original_buy("0.5", "partially_filled")
        self.port.mode = "cancel_pending"
        result = self.recover()
        self.assertEqual(result["status"], "needs_attention")
        self.assertIn("cancellation_not_confirmed", result["errors"])
        self.assertEqual(self.port.submissions, [])
        self.assertEqual(result["positions"], [{"symbol": "SPY", "qty": "0.5"}])

    def test_missing_attempted_order_never_becomes_not_sent(self):
        self.original_buy("0", "new")
        self.port.rows.clear()
        result = self.recover()
        self.assertIn("submitted_intent_absent", result["errors"])
        self.assertEqual(self.ledger.intents()[0].status, "reserved")
        self.assertTrue(self.ledger.intents()[0].submit_attempted)
        self.assertEqual(self.port.submissions, [])

    def test_proven_unsent_reservation_is_retired_without_lookup_or_submit(self):
        self.original_buy("0", "new", attempted=False)
        result = self.recover()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(self.ledger.intents()[0].status, "not_sent")
        self.assertEqual(self.port.adopted, {})

    def test_retained_broker_refusal_does_not_block_owned_residual_exit(self):
        self.original_buy(observed=True)
        self.original_buy("0", "new", cid="http-refused")
        del self.port.rows["http-refused"]
        self.ledger.mark_broker_refused("http-refused", 403)
        original_snapshot = self.port.snapshot
        async def checked_snapshot():
            self.assertNotIn("http-refused", self.port.adopted,
                             "a local terminal refusal must never trigger missing-ID broker lookup")
            return await original_snapshot()
        self.port.snapshot = checked_snapshot
        result = self.recover()
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["flat"])
        self.assertEqual(len(self.port.submissions), 1)
        self.assertEqual(self.port.submissions[0]["side"], "sell")
        self.assertEqual(self.ledger.intents()[1].status, "broker_refused")

    def test_external_position_stops_without_liquidating_owned_or_external(self):
        self.original_buy()
        self.port.external_position = True
        result = self.recover()
        self.assertIn("position_mismatch", result["errors"])
        self.assertEqual(self.port.submissions, [])
        self.assertEqual(len(result["broker_positions_last_observed"]), 2)

    def test_external_order_stops_before_cancel(self):
        self.original_buy("0", "new")
        self.port.rows["alien"] = dict(self.port.rows["entry-1"], client_order_id="alien", id="alien")
        result = self.recover()
        self.assertIn("external_order_detected", result["errors"])
        self.assertEqual(self.port.cancelled, [])

    def test_stream_observation_failure_prevents_residual_exit(self):
        self.original_buy()
        self.port.health["reasons"] = ["callback_failure"]
        result = self.recover()
        self.assertIn("recovery_observation_integrity_lost", result["errors"])
        self.assertEqual(self.port.submissions, [])

    def test_admission_freeze_does_not_block_confirmed_owned_exit(self):
        self.original_buy()
        self.port.health["reasons"] = ["quotes_disconnected"]
        result = self.recover()
        self.assertEqual(result["status"], "passed")

    def test_ambiguous_exit_is_retained_never_retried_or_rejected(self):
        self.original_buy()
        self.port.mode = "ambiguous_submit"
        result = self.recover()
        self.assertEqual(result["errors"], ["TimeoutError"])
        self.assertEqual(len(self.port.submissions), 1)
        self.assertEqual(result["unresolved_orders"][0]["status"], "reserved")
        self.assertTrue(result["unresolved_orders"][0]["submit_attempted"])
        self.assertNotIn("secret", str(result))

    def test_explicit_pre_wire_refusal_can_release_pending_intent(self):
        self.original_buy()
        self.port.mode = "local_not_sent"
        result = self.recover()
        self.assertEqual(result["errors"], ["LocalRefusal"])
        self.assertEqual(self.ledger.intents()[-1].status, "not_sent")
        self.assertTrue(self.ledger.intents()[-1].submit_attempted)
        self.assertEqual(result["unresolved_orders"], [])
        self.assertFalse(result["flat"])

    def test_http_definitive_refusal_is_not_mislabeled_as_never_sent(self):
        self.original_buy()
        self.port.mode = "http_definitive_refusal"
        result = self.recover()
        self.assertEqual(result["errors"], ["BrokerRefusal"])
        self.assertEqual(self.ledger.intents()[-1].status, "reserved")
        self.assertTrue(self.ledger.intents()[-1].submit_attempted)
        self.assertEqual(len(result["unresolved_orders"]), 1)
        self.assertFalse(result["flat"])

    def test_unfilled_exit_is_canceled_and_not_blindly_repriced(self):
        self.original_buy()
        self.port.mode = "exit_unfilled"
        result = self.recover()
        self.assertIn("exit_unfilled_no_blind_retry", result["errors"])
        self.assertEqual(len(self.port.submissions), 1)
        self.assertEqual(result["unresolved_orders"], [])
        self.assertFalse(result["flat"])

    def test_stale_quote_does_not_send_exit(self):
        self.original_buy()
        self.port.mode = "stale"
        result = self.recover()
        self.assertIn("recovery_quote_not_fresh", result["errors"])
        self.assertEqual(self.port.submissions, [])

    def test_closed_market_does_not_send_exit(self):
        self.original_buy()
        self.controller.market_open = False
        result = self.recover()
        self.assertIn("outside_allowed_session", result["errors"])
        self.assertEqual(self.port.submissions, [])

    def test_cleanup_client_id_advances_past_prior_durable_cleanup(self):
        self.original_buy(observed=True)
        cid = "rec-fault-test-0000042"
        stamp = self.start + 1
        self.ledger.reserve_intent(cid, "SPY", "sell", "1", "99.98",
            quote=Quote("SPY", "100", "100.01", stamp), now=stamp,
            market_open=True, session_close=self.controller.close)
        self.ledger.request_budget(stamp, "submit", client_id=cid)
        self.port.rows[cid] = {"client_order_id": cid, "id": "old-cleanup", "symbol": "SPY", "side": "sell",
                              "qty": "1", "limit_price": "99.98", "filled_qty": "0", "filled_avg_price": None,
                              "status": "canceled", "updated_at_ns": time.time_ns()}
        result = self.recover()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(self.port.submissions[0]["client_order_id"], "rec-fault-test-0000043")

    def test_shared_request_budget_prevents_unbudgeted_exit(self):
        self.original_buy()
        now = self.controller.clock()
        for _ in range(self.ledger.limits.max_rest_per_minute):
            self.assertEqual(self.ledger.request_budget(now, "read"), 0)
        result = self.recover()
        self.assertIn("fake_budget_exhausted", result["errors"])
        self.assertEqual(self.port.submissions, [])
        self.assertFalse(result["flat"])
        self.assertEqual(self.ledger.positions()["SPY"].qty, Decimal(1))

    def test_task_cancellation_stops_transport_and_retains_ambiguity(self):
        self.original_buy()
        self.port.mode = "slow_snapshot"
        async def exercise():
            task = asyncio.create_task(recover(self.controller, self.meta, self.config, reconcile_fn=proof))
            await asyncio.sleep(.02)
            task.cancel()
            return await task
        result = asyncio.run(exercise())
        self.assertEqual(result["errors"], ["recovery_cancelled"])
        self.assertEqual(self.port.stopped, 1)
        self.assertFalse(result["flat"])

    def test_deadline_stops_without_claiming_snapshot_or_flatness(self):
        self.config["cleanup_seconds"] = 1  # the deadline under test: min(1, ledger's 3) = 1 s
        self.original_buy()
        self.port.mode = "slow_snapshot"
        began = time.monotonic()
        result = self.recover()
        self.assertLess(time.monotonic() - began, 1.5)
        self.assertIn("recovery_deadline_reached", result["errors"])
        self.assertEqual(result["order_deadline_seconds"], 1)
        self.assertFalse(result["flat"])
        self.assertIsNone(result["reconciliation"])

    def test_existing_stop_request_still_allows_owned_exit(self):
        self.original_buy()
        self.controller.stop = True
        result = self.recover()
        self.assertEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
