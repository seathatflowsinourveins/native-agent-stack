"""Section 4 behavioral integration cases; no broker imports or network.

Run directly with --evidence-dir PRIVATE_DIR --attempt NAME to retain every
case's actual sequences, calls, journal snapshots, outcomes and source hashes.
Normal unittest discovery needs no evidence options. Expected money/quantities
below are hand calculated; tests use real SQLite, reopen and subprocess flock.
"""

import argparse
import copy
from contextlib import closing
from dataclasses import asdict, replace
from decimal import Context, Decimal, ROUND_HALF_EVEN, ROUND_UP, getcontext, localcontext
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import traceback
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "blueprints/us-equities/engine-nautilus/ibkr-native-paper/state.py"
FREEZE_PATH = STATE_PATH.with_name("offline-FREEZE.md")
RECORDS = []
RUN_EVIDENCE_DIR = None
RUN_ATTEMPT = "normal"
NOW = 1_500_000_000_000
ACCOUNT = "ba8321e3eb5d7d550215e79e1070cd7b2e2324e6684e4704cfe5b808b12be468"
PIN = "1b0a49d2792a9432a3aca3fcb617ce7a630d905e"
SOURCE = "fb2491805ad2331d2c08d0d2f04ed79107195655dc0fce9b8c68cff64b5f92c0"
UNSET_DOUBLE = "1.7976931348623157e308"


def sanitized(value):
    if isinstance(value, dict):
        return {str(k): sanitized(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitized(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return "<injected-callback>" if callable(value) else "<injected-transport>"


def load_state():
    if not STATE_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("ibkr_native_state", STATE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


class FakeBroker:
    """Independent account observations from transport and injected events only.

    No journal reads, risk/reservation/budget logic or state helper arithmetic.
    Opening account is a literal USD10000 and no positions/orders/executions.
    Received execution/commission facts book cash and quantities; reports are
    generated from this separate namespace, not from the controller's outputs.
    """

    def __init__(self):
        self.cash = Decimal("10000.00")
        self.fees = Decimal("0.00")
        self.positions = {}
        self.orders = {}
        self.executions = {}
        self.commissions = {}

    def accepted(self, intent, payload, identity):
        self.orders[intent] = {"payload": copy.deepcopy(payload), "identity": copy.deepcopy(identity),
                               "filled": 0, "status": "accepted"}

    def identified(self, reference, identity):
        for order in self.orders.values():
            seen = order["identity"]
            ref = seen.get("order_ref", seen.get("client_order_id", "")).rsplit(":", 1)[0]
            if ref == reference:
                order["identity"].update(copy.deepcopy(identity))

    def pending_cancel(self, identity):
        for order in self.orders.values():
            if any(k in identity and order["identity"].get(k) == identity[k]
                   for k in ["order_id", "perm_id", "venue_order_id"]):
                order["status"] = "cancel_pending"

    def received(self, method, args):
        if method == "execution":
            intent, exec_id, quantity, fill_price, currency = args
            if intent not in self.orders or exec_id in self.executions or currency != "USD":
                return
            order = self.orders[intent]
            try:
                amount = (Decimal(str(fill_price))*quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            except (ArithmeticError, ValueError):
                return
            self.executions[exec_id] = (intent, quantity, fill_price, currency)
            symbol = order["payload"]["symbol"]
            signed = quantity if order["payload"]["side"] == "BUY" else -quantity
            self.cash += -amount if signed > 0 else amount
            self.positions[symbol] = self.positions.get(symbol, 0)+signed
            if not self.positions[symbol]:
                del self.positions[symbol]
            order["filled"] += quantity
            if order["filled"] == order["payload"]["quantity"]:
                order["status"] = "filled"
        elif method == "commission":
            exec_id, amount, currency, posting = args
            if exec_id not in self.executions or exec_id in self.commissions or currency != "USD" or posting != "final":
                return
            try:
                value = Decimal(str(amount))
                if value == -1:
                    return
                amount = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            except (ArithmeticError, ValueError):
                return
            self.commissions[exec_id] = amount
            self.cash -= amount
            self.fees += amount
        elif method == "status":
            intent, status, cumulative = args
            if intent in self.orders and status in ["cancelled", "rejected", "filled"]:
                self.orders[intent]["status"] = status

    def report(self):
        return {"complete": {k: True for k in ["orders", "executions", "commissions", "positions", "cash"]},
                "orders": [{"intent": intent, "identity": copy.deepcopy(order["identity"]),
                            "filled": order["filled"], "status": order["status"]}
                           for intent, order in sorted(self.orders.items())],
                "executions": sorted(self.executions), "commissions": sorted(self.commissions),
                "positions": dict(self.positions), "cash": str(self.cash), "fees": str(self.fees),
                "currency": "USD", "fee_posting": "final"}


class Transport:
    """Injected boundary only; SQLite independently observes commit before send."""

    def __init__(self, case):
        self.case = case
        self.calls = []
        self.submit_mode = "accept"
        self.lookup_mode = "found"
        self.cancel_mode = "pending"
        self.identities = {}
        self.broker_orders = set()
        self.current_intent = None

    def identity(self, ref):
        if ref not in self.identities:
            self.identities[ref] = {"order_ref": ref, "order_id": 71+len(self.identities),
                                    "perm_id": 9001+len(self.identities)}
        return self.identities[ref]

    def submit(self, ref, payload):
        with closing(sqlite3.connect(self.case.db_path.resolve().as_uri()+"?mode=ro", uri=True)) as db:
            row = db.execute("SELECT attempted, reserved_cents FROM orders WHERE order_ref=?", (ref,)).fetchone()
        if self.submit_mode == "before_send_crash":
            self.case.record["sequence"].append({"operation": "transport_crash_before_outbound_send",
                                                 "durable_pre_send": list(row), "actual_outbound_calls": 0})
            raise KeyboardInterrupt("before_send")
        self.calls.append({"kind": "submit", "ref": ref, "payload": payload,
                           "durable_pre_send": list(row) if row else None})
        if self.submit_mode != "reject":
            self.broker_orders.add(ref)
            self.calls[-1]["fake_broker_accepted_identity"] = self.identity(ref)
            self.case.broker.accepted(self.current_intent, payload, self.identity(ref))
        if self.submit_mode == "lost":
            raise TimeoutError("accepted_then_response_lost")
        if self.submit_mode == "crash":
            raise KeyboardInterrupt("after_send_before_ack")
        if self.submit_mode == "reject":
            return {"kind": "rejected", "reason": "definitive_fixture_rejection"}
        return {"kind": "accepted", "identity": self.identity(ref)}

    def lookup(self, ref):
        observed = self.identity(ref) if self.lookup_mode == "found" and ref in self.broker_orders else None
        self.calls.append({"kind": "lookup", "ref": ref, "observed_identity": observed})
        if observed is not None:
            self.case.broker.identified(ref, observed)
        return observed

    def cancel(self, identity):
        self.calls.append({"kind": "cancel", "identity": identity})
        if self.cancel_mode == "fail":
            raise TimeoutError("cancel_response_unknown")
        if self.cancel_mode == "pending":
            self.case.broker.pending_cancel(identity)
        return {"kind": self.cancel_mode}


class StateCases(unittest.TestCase):
    def setUp(self):
        self.record = {"case": self.id().split(".")[-1], "expected": self._testMethodDoc,
                       "sequence": [], "transport_calls": [], "before": None, "after": None}
        RECORDS.append(self.record)
        self.module = load_state()
        self.assertIsNotNone(self.module, "durable controller unavailable: no intent can be safely reserved or submitted")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "state.sqlite"
        self.clock = Clock()
        self.broker = FakeBroker()
        self.transport = Transport(self)
        self.binding = self.module.Binding(
            broker="IBKR", endpoint="127.0.0.1:4002", account_fingerprint=ACCOUNT,
            client_id=176, plan_sha256=hashlib.sha256(FREEZE_PATH.read_bytes()).hexdigest(),
            source_sha256=SOURCE, source_revision=PIN, source_version="2.0.0rc5", schema=1,
        )
        self.state = self.open_state()
        self.addCleanup(self.close_state)
        self.record["before"] = self.state.snapshot()

    def tearDown(self):
        if getattr(self, "state", None):
            self.record["after"] = self.state.snapshot()
        if getattr(self, "transport", None):
            self.record["transport_calls"] = self.transport.calls

    def open_state(self, binding=None, db_path=None, limits=None):
        return self.module.PaperState(db_path or self.db_path, binding or self.binding,
                                     lock_root=Path(self.tmp.name) / "locks", clock=self.clock,
                                     stop_path=Path(self.tmp.name) / "STOP", limits=limits)

    def close_state(self):
        if getattr(self, "state", None):
            self.state.close()
            self.state = None

    def restart(self):
        self.record["sequence"].append({"operation": "restart"})
        self.close_state()
        self.state = self.open_state()

    def action(self, method, *args, **kwargs):
        self.record["sequence"].append({"operation": method, "args": sanitized(args), "kwargs": sanitized(kwargs),
                                        "clock_ns": self.clock.now})
        # Keep the independent fake account's arithmetic stable while testing
        # the controller against a caller's hostile ambient decimal context.
        with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
            self.broker.received(method, args)
        try:
            result = getattr(self.state, method)(*args, **kwargs)
        except BaseException as exc:
            self.record["sequence"][-1]["result"] = type(exc).__name__ + ":" + str(exc)
            raise
        self.record["sequence"][-1]["result"] = result
        self.record["sequence"][-1]["journal_after"] = self.state.snapshot()
        return result

    def order(self, intent="buy", qty=10, price="100.00", side="BUY", **extra):
        self.transport.current_intent = intent
        payload = {"symbol": "SYNTH.TEST", "side": side, "quantity": qty,
                   "limit_price": price, "currency": extra.pop("currency", "USD")}
        return self.action("submit", intent, payload, self.transport,
                           quote_price=extra.pop("quote_price", price),
                           quote_time_ns=extra.pop("quote_time_ns", self.clock.now), **extra)

    def fill(self, exec_id="e1", quantity=3, price="100.00", intent="buy", **extra):
        return self.action("execution", intent, exec_id, quantity, price, "USD", **extra)

    def fee(self, exec_id="e1", amount="0.30", currency="USD", posting="final"):
        return self.action("commission", exec_id, amount, currency, posting)

    def economics(self, position, cash, fees, filled=None):
        snap = self.state.snapshot()
        self.assertEqual(snap["positions"], {} if position == 0 else {"SYNTH.TEST": position})
        self.assertEqual(snap["cash_cents"], cash)
        self.assertEqual(snap["fees_cents"], fees)
        if filled is not None:
            self.assertEqual(snap["orders"][0]["filled"], filled)

    def complete_snapshot(self):
        return self.broker.report()

    def test_duplicate_intent_has_one_durable_transport_attempt(self):
        """Exactly one submit, attempted=1, reserve=100000 cents; repeat survives restart."""
        self.assertEqual(self.order(), "accepted")
        self.assertEqual(self.order(), "accepted")
        self.restart()
        self.assertEqual(self.order(), "accepted")
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.calls[0]["durable_pre_send"], [1, 100000])
        self.economics(0, 1000000, 0, 0)

    def test_duplicate_intent_changed_payload_cannot_replace_reservation(self):
        """Changed intent payload leaves journal and transport unchanged."""
        self.order()
        before = self.state.snapshot()
        with self.assertRaisesRegex(self.module.Refused, "intent_payload_changed"):
            self.order(qty=9)
        self.assertEqual(self.state.snapshot(), before)
        self.assertEqual(len(self.transport.calls), 1)

    def test_lost_response_restart_adopts_original_without_resubmit(self):
        """Accepted/lost response: unknown then explicit lookup adopts original; one submit."""
        self.transport.submit_mode = "lost"
        self.assertEqual(self.order(), "unknown")
        self.restart()
        self.assertEqual(self.order(), "unknown")
        self.assertEqual(self.action("lookup", "buy", self.transport), "accepted")
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit", "lookup"])
        self.assertEqual(self.state.snapshot()["orders"][0]["identity"],
                         {"order_ref": self.transport.calls[0]["ref"], "order_id": 71, "perm_id": 9001})
        self.assertFalse(self.state.snapshot()["ready"])
        self.assertTrue(self.action("reconcile", self.complete_snapshot()))
        self.assertTrue(self.state.snapshot()["ready"])

    def test_unresolved_lookup_remains_blocked(self):
        """Unresolved durable reference refuses new intents; no automatic resend."""
        self.transport.submit_mode = "lost"
        self.order()
        self.restart()
        self.transport.lookup_mode = "missing"
        self.assertEqual(self.action("lookup", "buy", self.transport), "unknown")
        with self.assertRaisesRegex(self.module.Refused, "reconciliation_required"):
            self.order("other")
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit", "lookup"])

    def test_definitive_rejection_is_terminal_and_releases_risk(self):
        """Rejection retained, zero cash/position effect, one submit across restart."""
        self.transport.submit_mode = "reject"
        self.assertEqual(self.order(), "rejected")
        self.restart()
        self.assertEqual(self.order(), "rejected")
        self.economics(0, 1000000, 0, 0)
        self.assertEqual(self.state.snapshot()["orders"][0]["reserved_cents"], 0)
        self.assertEqual(self.state.snapshot()["orders"][0]["reason"], "definitive_fixture_rejection")
        self.assertEqual(len(self.transport.calls), 1)

    def test_partial_replayed_execution_and_old_cumulative_status(self):
        """3+2+replay3 means position5/cash949950/fees50/remaining5; old status2 has no economics."""
        self.order()
        self.fill()
        self.fee()
        self.fill("e2", 2)
        self.fee("e2", "0.20")
        self.fill()
        self.fee()
        self.action("status", "buy", "accepted", 2)
        self.economics(5, 949950, 50, 5)
        self.assertEqual(self.state.snapshot()["orders"][0]["remaining"], 5)
        self.assertEqual(len(self.state.snapshot()["executions"]), 2)

    def test_status_cannot_create_fill_economics(self):
        """Status filled10 without executions freezes; cash and position stay unchanged."""
        self.order()
        self.assertFalse(self.action("status", "buy", "filled", 10))
        self.economics(0, 1000000, 0, 0)
        self.assertFalse(self.state.snapshot()["ready"])

    def test_execution_identity_recovers_lost_ack_before_lookup(self):
        """Owned fill identity binds before lookup; partial fill and matching snapshot recover without resubmit."""
        self.transport.submit_mode = "lost"
        self.assertEqual(self.order(qty=5), "unknown")
        identity = copy.deepcopy(self.transport.calls[0]["fake_broker_accepted_identity"])
        self.assertTrue(self.fill(quantity=3, identity=identity))
        order = self.state.snapshot()["orders"][0]
        self.assertEqual((order["identity"], order["status"], order["reserved_cents"]),
                         (identity, "accepted", 20000))
        self.economics(3, 970000, 0, 3)
        self.fee(amount="0")
        self.assertTrue(self.action("reconcile", self.complete_snapshot()))
        self.assertTrue(self.state.snapshot()["ready"])
        self.restart()
        self.assertTrue(self.action("reconcile", self.complete_snapshot()))
        self.assertEqual(self.order(qty=5), "accepted")
        self.fill("e2", quantity=2)
        self.fee("e2", "0")
        self.economics(5, 950000, 0, 5)
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit"])

    def test_execution_identity_requires_owned_reference_and_native_id(self):
        """Invalid fill identity never binds or books; missing identity remains a permanent contradiction."""
        cases = [(None, "unknown_execution_order"),
                 ({"order_ref": "foreign"}, "unknown_order_reference"),
                 ({"order_id": 0}, "invalid_native_id"),
                 ({"order_id": None, "perm_id": None}, "native_id_unobserved")]
        for index, (changes, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                self.close_state()
                self.db_path = Path(self.tmp.name)/("fill-identity-"+str(index)+".sqlite")
                self.broker = FakeBroker()
                self.transport = Transport(self)
                self.state = self.open_state()
                self.transport.submit_mode = "lost"
                self.order(qty=3)
                identity = copy.deepcopy(self.transport.calls[0]["fake_broker_accepted_identity"])
                if changes is None:
                    identity = None
                else:
                    identity.update(changes)
                    identity = {k: v for k, v in identity.items() if v is not None}
                self.assertFalse(self.fill(quantity=3, identity=identity))
                snap = self.state.snapshot()
                self.assertIn(reason, snap["alerts"])
                self.assertIsNone(snap["orders"][0]["identity"])
                self.assertEqual(snap["executions"], [])
                self.economics(0, 1000000, 0, 0)
                self.assertFalse(snap["ready"])
                self.restart()
                self.assertFalse(self.state.snapshot()["ready"])
                self.assertEqual([c["kind"] for c in self.transport.calls], ["submit"])

    def test_changed_execution_replay_freezes_without_second_effect(self):
        """Same execution ID changed quantity: position3/cash970000 and retained alert."""
        self.order()
        self.fill()
        self.assertFalse(self.fill(quantity=4))
        self.economics(3, 970000, 0, 3)
        self.assertIn("execution_payload_changed", self.state.snapshot()["alerts"])

    def test_late_commission_pending_then_final_currency_rounding(self):
        """Pending sentinel has no fee; final0.305 half-even=30 cents once; fees gate reconciliation."""
        self.order()
        self.fill()
        self.assertFalse(self.action("reconcile", self.complete_snapshot()))
        self.fee(amount="-1", posting="pending")
        self.economics(3, 970000, 0, 3)
        self.fee(amount="0.305")
        self.fee(amount="0.305")
        self.economics(3, 969970, 30, 3)
        self.assertTrue(self.action("reconcile", self.complete_snapshot()))

    def test_final_rebate_is_not_pending_sentinel(self):
        """Explicit final -0.205 USD rebate posts -20 cents; pending -1 cannot finalize."""
        self.order()
        self.fill()
        self.fee(amount="-0.205")
        self.economics(3, 970020, -20, 3)

    def test_zero_fee_pending_is_distinct_from_observed_final_zero(self):
        """Numeric zero pending cannot reconcile; explicit final USD zero completes fees."""
        self.order()
        self.fill()
        self.fee(amount="0", posting="pending")
        self.assertFalse(self.action("reconcile", self.complete_snapshot()))
        self.economics(3, 970000, 0, 3)
        self.fee(amount="0", posting="final")
        self.assertTrue(self.action("reconcile", self.complete_snapshot()))
        self.economics(3, 970000, 0, 3)

    def test_changed_final_commission_freezes_without_reposting(self):
        """Changed same execution commission is contradiction; first30 cents retained."""
        self.order()
        self.fill()
        self.fee()
        self.assertFalse(self.fee(amount="0.40"))
        self.economics(3, 969970, 30, 3)
        self.assertFalse(self.state.snapshot()["ready"])

    def test_cancel_race_retains_late_fill_and_cancelled_remainder(self):
        """Cancel at5, late2, confirmed cancellation: position7/fees70/cash929930; cancelled3."""
        self.order()
        self.fill()
        self.fee()
        self.fill("e2", 2)
        self.fee("e2", "0.20")
        self.assertEqual(self.action("cancel", "buy", self.transport), "cancel_pending")
        self.assertEqual(self.state.snapshot()["orders"][0]["status"], "cancel_pending")
        self.fill("e3", 2)
        self.fee("e3", "0.20")
        self.action("status", "buy", "cancelled", 7)
        self.economics(7, 929930, 70, 7)
        order = self.state.snapshot()["orders"][0]
        self.assertEqual((order["cancelled"], order["remaining"], order["reserved_cents"]), (3, 0, 0))

    def test_crash_before_send_durable_marker_never_blindly_resends(self):
        """Pre-send crash retains attempt/reserve, zero submit, lookup missing blocks."""
        self.transport.submit_mode = "before_send_crash"
        with self.assertRaises(KeyboardInterrupt):
            self.order()
        self.restart()
        self.assertEqual(self.order(), "unknown")
        self.assertEqual(self.transport.calls, [])
        self.transport.lookup_mode = "missing"
        self.action("lookup", "buy", self.transport)
        self.assertFalse(self.state.snapshot()["ready"])
        self.assertEqual(self.state.snapshot()["orders"][0]["attempted"], 1)

    def test_crash_after_send_before_ack_keeps_single_submission(self):
        """Post-send crash: one submit, restart lookup adopts, no resubmit."""
        self.transport.submit_mode = "crash"
        with self.assertRaises(KeyboardInterrupt):
            self.order()
        self.restart()
        self.assertEqual(self.order(), "unknown")
        self.action("lookup", "buy", self.transport)
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit", "lookup"])

    def test_crash_after_fill_before_checkpoint_replay_is_idempotent(self):
        """Durably committed fill survives checkpoint crash: position3/fees30 once, reconcile required."""
        self.order()
        with self.assertRaises(KeyboardInterrupt):
            self.fill()
            self.record["sequence"].append({"operation": "crash_before_external_checkpoint",
                                            "journal_after_committed_fill": self.state.snapshot()})
            raise KeyboardInterrupt("checkpoint_crash")
        self.restart()
        self.fill()
        self.fee()
        self.economics(3, 969970, 30, 3)
        self.assertFalse(self.state.snapshot()["ready"])
        self.assertTrue(self.action("reconcile", self.complete_snapshot()))

    def test_freshness_exact_nanosecond_boundaries(self):
        """max-1 and max submit; max+1 and future refused with identical journal/zero calls."""
        for age, allowed in [(2_999_999_999, True), (3_000_000_000, True), (3_000_000_001, False), (-1, False)]:
            with self.subTest(age=age):
                before = self.state.snapshot()
                calls = len(self.transport.calls)
                if allowed:
                    self.order(str(age), qty=1, quote_time_ns=NOW-age)
                else:
                    with self.assertRaises(self.module.Refused):
                        self.order(str(age), qty=1, quote_time_ns=NOW-age)
                    self.assertEqual(self.state.snapshot(), before)
                    self.assertEqual(len(self.transport.calls), calls)

    def test_invalid_quote_quantity_money_and_currency_have_zero_writes(self):
        """NaN/Inf/zero/offtick/fractional shares/nonUSD/missing quote refuse unchanged."""
        cases = [{"quote_price": "NaN"}, {"quote_price": "Infinity"}, {"price": "NaN"},
                 {"price": "0"}, {"price": "100.001"}, {"qty": 1.5}, {"qty": True},
                 {"quote_price": None}, {"quote_time_ns": 1.5}, {"currency": "EUR"}]
        for i, kwargs in enumerate(cases):
            with self.subTest(case=kwargs):
                before = self.state.snapshot()
                with self.assertRaises(self.module.Refused):
                    self.order(str(i), **kwargs)
                self.assertEqual(self.state.snapshot(), before)
        self.assertEqual(self.transport.calls, [])

    def test_session_open_included_close_excluded(self):
        """Session open accepts; close and before-open refuse unchanged."""
        # A fresh independent fixture starts at open; do not regress a running clock.
        self.close_state()
        self.db_path = Path(self.tmp.name) / "session.sqlite"
        self.clock.now = 1_000_000_000_000
        self.state = self.open_state()
        self.order("open", qty=1)
        for now in [999_999_999_999, 2_000_000_000_000]:
            self.clock.now = now
            before = self.state.snapshot()
            with self.assertRaisesRegex(self.module.Refused, "session_closed"):
                self.order(str(now), qty=1)
            self.assertEqual(self.state.snapshot(), before)
        self.assertEqual(len(self.transport.calls), 1)

    def test_order_and_aggregate_exposure_limit_equal_allowed(self):
        """10 shares at200 reaches2000; next1 share refuses unchanged, qty11/notional2000.10 refuse."""
        for qty, price in [(11, "100.00"), (10, "200.01")]:
            before = self.state.snapshot()
            with self.assertRaises(self.module.Refused):
                self.order("bad", qty=qty, price=price)
            self.assertEqual(self.state.snapshot(), before)
        self.order(price="200.00")
        before = self.state.snapshot()
        with self.assertRaisesRegex(self.module.Refused, "exposure"):
            self.order("too_many", qty=1)
        self.assertEqual(self.state.snapshot(), before)

    def test_insufficient_cash_respects_fee_economics(self):
        """Observed final9000 fee reduces cash1000; buy2000 refused without new journal writes."""
        self.order(qty=1)
        self.fill(quantity=1)
        self.fee(amount="9000.00")
        self.economics(1, 90000, 900000, 1)
        before = self.state.snapshot()
        with self.assertRaisesRegex(self.module.Refused, "insufficient_cash"):
            self.order("cash", price="200.00")
        self.assertEqual(self.state.snapshot(), before)
        self.assertEqual(len(self.transport.calls), 1)

    def test_loss_and_drawdown_caps_persist_across_restart_and_new_intent(self):
        """101 USD loss latches numeric halt; restart/new identity cannot reset it."""
        self.order()
        self.fill(quantity=10)
        self.fee(amount="0")
        self.assertFalse(self.action("observe_risk", {"SYNTH.TEST": "89.90"}))
        self.restart()
        with self.assertRaisesRegex(self.module.Refused, "halted"):
            self.order("new")
        self.assertEqual(self.state.snapshot()["halt"], "drawdown_cap_exceeded")
        self.economics(10, 900000, 0, 10)

    def test_realized_gross_loss_cap_and_exact_boundary(self):
        """Sell realizes exactly100 allowed, next loss crosses100 and permanently halts."""
        self.order()
        self.fill(quantity=10)
        self.fee(amount="0")
        self.order("sell", qty=10, price="90.00", side="SELL")
        self.fill("s1", 10, "90.00", "sell")
        self.fee("s1", "0")
        self.assertEqual(self.state.snapshot()["gross_loss_cents"], 10000)
        self.assertIsNone(self.state.snapshot()["halt"])
        self.clock.now += 60_000_000_000
        self.order("buy2", qty=1)
        self.fill("b2", 1, intent="buy2")
        self.fee("b2", "0")
        # Current quote stays100; the later injected fill99.99 causes the loss.
        self.order("sell2", qty=1, price="99.99", quote_price="100.00", side="SELL")
        self.fill("s2", 1, "99.99", "sell2")
        self.fee("s2", "0")
        self.assertEqual(self.state.snapshot()["gross_loss_cents"], 10001)
        self.assertEqual(self.state.snapshot()["halt"], "gross_loss_cap_exceeded")
        self.economics(0, 989999, 0)

    def test_partial_average_cost_does_not_round_each_internal_loss(self):
        """Buy3 at100.01+2 at100; five sell1 at100 lose3 cents total, not5 rounded intermediate cents."""
        self.order(qty=5, price="100.01")
        self.fill(quantity=3, price="100.01")
        self.fee(amount="0")
        self.fill("e2", 2)
        self.fee("e2", "0")
        self.order("sell", qty=5, side="SELL")
        for i in range(5):
            self.fill("s"+str(i), 1, "100.00", "sell")
            self.fee("s"+str(i), "0")
        self.economics(0, 999997, 0)
        self.assertEqual(self.state.snapshot()["gross_loss_cents"], 3)

    def test_money_arithmetic_ignores_ambient_context_and_restores_it(self):
        """Average-cost thirds, half-cent fees and helper refusals agree under changed precision, rounding and traps."""
        normal = Context(prec=28, rounding=ROUND_HALF_EVEN)
        hostile = Context(prec=6, rounding=ROUND_UP, Emin=-9, Emax=9, capitals=0, clamp=1)
        for signal in hostile.traps:
            hostile.traps[signal] = True
        permissive = hostile.copy()
        for signal in permissive.traps:
            permissive.traps[signal] = False
        expected = None
        for index, context in enumerate([normal, hostile, permissive]):
            with self.subTest(context=index):
                self.close_state()
                self.db_path = Path(self.tmp.name)/("money-context-"+str(index)+".sqlite")
                self.broker = FakeBroker()
                self.transport = Transport(self)
                with localcontext(context):
                    ambient = repr(getcontext())
                    self.state = self.open_state()
                    self.assertEqual(self.module.cents("1234.565"), 123456)
                    self.assertEqual(self.module.price("100.01"), Decimal("100.01"))
                    for helper in [self.module.cents, self.module.price]:
                        for value in ["1e30", UNSET_DOUBLE]:
                            with self.assertRaises(self.module.Refused):
                                helper(value)
                    with self.assertRaisesRegex(self.module.Refused, "invalid_decimal"):
                        self.module.decimal("1e999999999999999999999999")
                    self.order(qty=3, price="100.01")
                    self.fill(quantity=1, price="100.01")
                    self.fee(amount="0.005")
                    self.fill("e2", quantity=2)
                    self.fee("e2", "0.015")
                    self.order("sell", qty=3, side="SELL")
                    for i in range(3):
                        self.fill("s"+str(i), 1, "100.00", "sell")
                        self.fee("s"+str(i), "0")
                    self.assertTrue(self.action("reconcile", self.complete_snapshot()))
                    self.economics(0, 999997, 2)
                    snap = self.state.snapshot()
                    self.assertEqual(snap["gross_loss_cents"], 1)
                    self.assertEqual(repr(getcontext()), ambient)
                if expected is None:
                    expected = snap
                else:
                    self.assertEqual(snap, expected)

    def test_unset_double_fill_blocks_without_economic_effect(self):
        """Unrepresentable fill latches invalid_execution_economics instead of escaping and leaving admission ready."""
        self.order(qty=3)
        self.assertFalse(self.fill(quantity=3, price=UNSET_DOUBLE))
        self.assertIn("invalid_execution_economics", self.state.snapshot()["alerts"])
        self.assertEqual(self.state.snapshot()["executions"], [])
        self.economics(0, 1000000, 0, 0)
        with self.assertRaisesRegex(self.module.Refused, "reconciliation_required"):
            self.order("new", qty=1)
        self.restart()
        self.assertFalse(self.state.snapshot()["ready"])

    def test_unset_double_mark_blocks_without_replacing_mark(self):
        """Unrepresentable mark latches invalid_position_mark and retains the last valid economics."""
        self.order(qty=3)
        self.fill(quantity=3)
        self.fee(amount="0")
        self.assertFalse(self.action("observe_risk", {"SYNTH.TEST": UNSET_DOUBLE}))
        self.assertIn("invalid_position_mark", self.state.snapshot()["alerts"])
        self.assertEqual(self.state.db.execute("SELECT mark FROM positions").fetchone()[0], "100.00")
        self.economics(3, 970000, 0, 3)
        with self.assertRaisesRegex(self.module.Refused, "reconciliation_required"):
            self.order("new", qty=1)
        self.restart()
        self.assertFalse(self.state.snapshot()["ready"])

    def test_unset_double_snapshot_cash_and_fee_retain_conflict(self):
        """Unrepresentable snapshot cash or fees become retained snapshot_malformed conflicts, never balancing entries."""
        for field in ["cash", "fees"]:
            with self.subTest(field=field):
                self.close_state()
                self.db_path = Path(self.tmp.name)/("snapshot-unset-"+field+".sqlite")
                self.state = self.open_state()
                snapshot = self.complete_snapshot()
                snapshot[field] = UNSET_DOUBLE
                self.assertFalse(self.action("reconcile", snapshot))
                snap = self.state.snapshot()
                self.assertIn("snapshot_malformed", snap["alerts"])
                self.assertEqual(snap["observation_conflicts"][0]["reason"], "snapshot_malformed")
                self.economics(0, 1000000, 0)
                self.assertFalse(self.action("reconcile", self.complete_snapshot()))
                with self.assertRaisesRegex(self.module.Refused, "reconciliation_required"):
                    self.order("new", qty=1)
                self.restart()
                self.assertFalse(self.state.snapshot()["ready"])

    def test_unset_double_final_commission_blocks_without_posting(self):
        """Unrepresentable final commission latches invalid_commission and leaves cash and fees unchanged."""
        self.order(qty=3)
        self.fill(quantity=3)
        self.assertFalse(self.fee(amount=UNSET_DOUBLE))
        self.assertIn("invalid_commission", self.state.snapshot()["alerts"])
        self.assertEqual(self.state.snapshot()["commissions"], [])
        self.economics(3, 970000, 0, 3)
        self.fee(amount="0")
        with self.assertRaisesRegex(self.module.Refused, "reconciliation_required"):
            self.order("new", qty=1)
        self.restart()
        self.assertFalse(self.action("reconcile", self.complete_snapshot()))
        self.assertIn("contradiction_requires_adjudication", self.state.snapshot()["alerts"])

    def test_no_short_or_overlapping_sell_reservation(self):
        """Sell larger than holdings or reserved twice produces no submit or changed journal."""
        with self.assertRaises(self.module.Refused):
            self.order("short", qty=1, side="SELL")
        self.order(qty=3)
        self.fill(quantity=3)
        self.fee(amount="0")
        self.order("sell", qty=2, side="SELL")
        before = self.state.snapshot()
        with self.assertRaises(self.module.Refused):
            self.order("sell_again", qty=2, side="SELL")
        self.assertEqual(self.state.snapshot(), before)

    def test_fresh_quote_marks_held_exposure_before_admission(self):
        """Fresh quote300 marks held5=1500; proposed buy1000 exceeds2000 and is refused unchanged."""
        self.order(qty=5)
        self.fill(quantity=5)
        self.fee(amount="0")
        before = self.state.snapshot()
        with self.assertRaisesRegex(self.module.Refused, "exposure"):
            self.order("new", qty=10, quote_price="300.00")
        self.assertEqual(self.state.snapshot(), before)
        self.assertEqual(len(self.transport.calls), 1)

    def test_numeric_exposure_halt_cancels_owned_remaining_order(self):
        """Mark501 makes held5+pending5 exceed exposure; halt persists and cancels only pending owned order."""
        self.order(qty=5)
        self.fill(quantity=5)
        self.fee(amount="0")
        self.order("pending", qty=5)
        self.assertFalse(self.action("observe_risk", {"SYNTH.TEST": "501.00"}, transport=self.transport))
        self.assertEqual(self.state.snapshot()["halt"], "aggregate_exposure_cap_exceeded")
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit", "submit", "cancel"])
        self.assertEqual(self.state.snapshot()["orders"][1]["status"], "cancel_pending")
        self.restart()
        self.assertFalse(self.state.snapshot()["ready"])

    def test_unresolved_cancel_blocks_new_intents_until_confirmation(self):
        """Pending cancellation retains reservation and blocks unrelated new submit."""
        self.order(qty=1)
        self.action("cancel", "buy", self.transport)
        before = self.state.snapshot()
        with self.assertRaisesRegex(self.module.Refused, "reconciliation_required"):
            self.order("new", qty=1)
        self.assertEqual(self.state.snapshot(), before)
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit", "cancel"])

    def test_request_budget_preserves_three_control_calls_and_bounded_backoff(self):
        """5 submits then pause; cancel+2 lookups fit reserve, ninth call refused; persisted backoff bounded."""
        for i in range(5):
            self.order(str(i), qty=1)
        for _ in range(6):
            with self.assertRaisesRegex(self.module.Refused, "request_budget"):
                self.order("overflow", qty=1)
        snap = self.state.snapshot()
        self.assertEqual(snap["budget"]["backoff_ns"], 8_000_000_000)
        self.assertGreaterEqual(snap["budget"]["blocked_until_ns"], NOW+60_000_000_000)
        self.action("cancel", "0", self.transport)
        self.action("lookup", "1", self.transport)
        self.action("lookup", "2", self.transport)
        with self.assertRaisesRegex(self.module.Refused, "request_budget"):
            self.action("lookup", "3", self.transport)
        self.assertEqual(len(self.transport.calls), 8)
        self.restart()
        with self.assertRaisesRegex(self.module.Refused, "reconciliation_required|request_budget"):
            self.order("after_restart", qty=1)
        self.assertEqual(self.state.snapshot()["budget"]["used"], 8)

    def test_request_control_reserve_refusal_restart_and_window_renewal(self):
        """Explicit snapshot requests consume the reserve, refuse exhaustion and renew without clearing submit backoff."""
        for i in range(5):
            self.order(str(i), qty=1)
        self.clock.now += 59_999_999_999
        with self.assertRaisesRegex(self.module.Refused, "^request_budget_exhausted$"):
            self.order("overflow", qty=1)
        for _ in range(3):
            self.assertIsNone(self.action("request_control"))
        self.assertEqual(self.state.snapshot()["budget"]["used"], 8)
        with self.assertRaisesRegex(self.module.Refused, "^request_budget_exhausted$"):
            self.action("request_control")
        deadline = self.state.snapshot()["budget"]["blocked_until_ns"]
        self.restart()
        self.assertEqual(self.state.snapshot()["budget"]["used"], 8)
        self.clock.now = NOW+60_000_000_000
        self.assertIsNone(self.action("request_control"))
        budget = self.state.snapshot()["budget"]
        self.assertEqual((budget["window_start_ns"], budget["used"], budget["blocked_until_ns"]),
                         (self.clock.now, 1, deadline))
        self.assertGreater(deadline, self.clock.now)
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit"]*5)

    def test_regressed_clock_refuses_submit_and_control_without_mutation(self):
        """Clock before the durable window start refuses before any request, intent or transport mutation."""
        self.clock.now = NOW-1
        before = self.state.snapshot()
        for operation in [lambda: self.action("request_control"), lambda: self.order(qty=1)]:
            with self.assertRaisesRegex(self.module.Refused, "^clock_regressed$"):
                operation()
            self.assertEqual(self.state.snapshot(), before)
        self.assertEqual(self.transport.calls, [])

    def test_disconnect_requires_all_snapshot_parts(self):
        """Disconnect blocks submits; incomplete snapshot stays blocked; complete agreeing snapshot restores ready."""
        self.order(qty=3)
        self.fill(quantity=3)
        self.fee(amount="0")
        self.action("disconnect", "fixture_stream_gap")
        with self.assertRaises(self.module.Refused):
            self.order("new")
        incomplete = self.complete_snapshot()
        incomplete["complete"]["cash"] = False
        self.assertFalse(self.action("reconcile", incomplete))
        self.assertFalse(self.state.snapshot()["ready"])
        self.assertEqual(self.state.snapshot()["observation_conflicts"], [])
        self.assertTrue(self.action("reconcile", self.complete_snapshot()))
        self.assertTrue(self.state.snapshot()["ready"])

    def test_backoff_survives_window_boundary_until_declared_deadline(self):
        """Exhaust near window end: next-window call still paused until bounded backoff deadline."""
        for i in range(5):
            self.order(str(i), qty=1)
        self.clock.now += 59_999_999_999
        with self.assertRaisesRegex(self.module.Refused, "request_budget"):
            self.order("overflow", qty=1)
        deadline = self.state.snapshot()["budget"]["blocked_until_ns"]
        self.clock.now = NOW+60_000_000_000
        with self.assertRaisesRegex(self.module.Refused, "request_budget"):
            self.order("still_paused", qty=1)
        self.assertEqual(len(self.transport.calls), 5)
        self.clock.now = deadline
        self.assertEqual(self.order("resumed", qty=1), "accepted")
        self.assertEqual(len(self.transport.calls), 6)

    def test_unknown_order_snapshot_blocks_without_adoption(self):
        """Unknown native order freezes without creating local order or economic reset."""
        snapshot = self.complete_snapshot()
        snapshot["orders"] = [{"intent": "foreign", "identity": {"order_ref": "foreign", "order_id": 99}, "filled": 0, "status": "accepted"}]
        self.assertFalse(self.action("reconcile", snapshot))
        self.assertEqual(self.state.snapshot()["orders"], [])
        self.economics(0, 1000000, 0)

    def test_position_cash_fee_currency_and_execution_snapshot_contradictions(self):
        """Unknown position/cash/fee/currency/missing execution each blocks; original economics never erased."""
        for index, (field, value) in enumerate([("positions", {}), ("cash", "10000.00"), ("fees", "0"),
                             ("currency", "EUR"), ("executions", []), ("commissions", []),
                             ("fee_posting", "pending"), ("positions", {"FOREIGN": 1}),
                             ("cash", None), ("fees", None), ("currency", None)]):
            with self.subTest(field=field):
                # Each fault gets an independent broker and SQLite fixture, so
                # an earlier permanent conflict cannot satisfy the later case.
                self.close_state()
                self.db_path = Path(self.tmp.name)/("snapshot-fault-"+str(index)+".sqlite")
                self.broker = FakeBroker()
                self.state = self.open_state()
                self.order(qty=3)
                self.fill(quantity=3)
                self.fee()
                snapshot = self.complete_snapshot()
                snapshot[field] = value
                self.assertFalse(self.action("reconcile", snapshot))
                self.economics(3, 969970, 30, 3)
                self.assertFalse(self.state.snapshot()["ready"])
                self.assertTrue(self.state.snapshot()["observation_conflicts"])

    def test_unknown_execution_and_commission_currency_freeze(self):
        """Unowned fill/fee and nonUSD fee block without inventing economics."""
        self.assertFalse(self.fill(intent="foreign"))
        self.assertFalse(self.fee(exec_id="foreign"))
        self.economics(0, 1000000, 0)

    def test_nonusd_or_missing_commission_currency_stays_pending(self):
        """Missing/nonUSD final currency never posts USD fee and prevents reconcile."""
        self.order()
        self.fill()
        for currency in [None, "EUR"]:
            self.assertFalse(self.fee(currency=currency))
        self.economics(3, 970000, 0, 3)
        self.assertFalse(self.action("reconcile", self.complete_snapshot()))

    def test_contradictory_native_ids_cannot_rebind_intent(self):
        """Changed native identity freezes and preserves first observed71/9001 binding."""
        self.order()
        self.transport.identity = lambda ref: {"order_ref": ref, "order_id": 72, "perm_id": 9001}
        self.assertEqual(self.action("lookup", "buy", self.transport), "blocked")
        self.assertEqual(self.state.snapshot()["orders"][0]["identity"]["order_id"], 71)
        self.assertFalse(self.state.snapshot()["ready"])

    def test_observed_venue_id_does_not_fabricate_raw_identity(self):
        """PERM report stores permId only; later observed orderId enriches immutable mapping."""
        self.transport.identity = lambda ref: {"client_order_id": ref, "venue_order_id": "PERM-9001"}
        self.order()
        identity = self.state.snapshot()["orders"][0]["identity"]
        self.assertEqual(identity, {"client_order_id": self.transport.calls[0]["ref"], "venue_order_id": "PERM-9001", "perm_id": 9001})
        self.transport.identity = lambda ref: {"order_ref": ref+":176", "order_id": 71, "perm_id": 9001}
        self.assertEqual(self.action("lookup", "buy", self.transport), "accepted")
        self.assertEqual(self.state.snapshot()["orders"][0]["identity"]["order_id"], 71)

    def test_stop_file_independent_cancel_owned_failure_and_restart(self):
        """Independent STOP latches before submit; cancel failure blocks persistently; no halt reset on reconcile."""
        self.order()
        (Path(self.tmp.name) / "STOP").touch()
        self.transport.cancel_mode = "fail"
        self.assertFalse(self.action("poll_stop", self.transport))
        self.assertEqual(self.state.snapshot()["halt"], "independent_STOP")
        self.assertEqual(self.state.snapshot()["orders"][0]["status"], "cancel_unknown")
        self.restart()
        (Path(self.tmp.name) / "STOP").unlink()
        with self.assertRaisesRegex(self.module.Refused, "halted"):
            self.order("new")
        self.assertFalse(self.action("reconcile", self.complete_snapshot()))
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit", "cancel"])

    def test_stop_cancels_only_owned_resolved_nonterminal_orders(self):
        """STOP requests cancel for known owned order only; cancellation confirmation releases reserve, halt persists."""
        self.order()
        self.action("stop", "operator_STOP", self.transport)
        self.action("status", "buy", "cancelled", 0)
        self.assertEqual(self.state.snapshot()["orders"][0]["reserved_cents"], 0)
        self.restart()
        self.assertEqual(self.state.snapshot()["halt"], "operator_STOP")
        self.assertFalse(self.state.snapshot()["ready"])
        self.economics(0, 1000000, 0)

    def test_stop_control_budget_uses_intent_order_under_reversed_query_plan(self):
        """Five pending orders and three control slots cancel a,b,c in intent order; d,z remain owned and halted."""
        for intent in ["z", "d", "a", "c", "b"]:
            self.order(intent, qty=1)
        self.state.db.execute("PRAGMA reverse_unordered_selects=ON")
        self.assertFalse(self.action("stop", "operator_STOP", self.transport))
        cancels = [c["identity"]["order_id"] for c in self.transport.calls if c["kind"] == "cancel"]
        self.assertEqual(cancels, [73, 75, 74])
        snap = self.state.snapshot()
        self.assertEqual([o["status"] for o in snap["orders"]],
                         ["cancel_pending"]*3+["accepted"]*2)
        self.assertEqual([o["reserved_cents"] for o in snap["orders"]], [10000]*5)
        self.assertIn("stop_cancel_refused:request_budget_exhausted", snap["alerts"])
        self.assertEqual(snap["halt"], "operator_STOP")
        self.assertFalse(snap["ready"])
        self.restart()
        self.assertEqual(self.state.snapshot()["halt"], "operator_STOP")

    def test_numeric_halt_without_transport_retains_owned_orders_and_alert(self):
        """After restart, risk halt with no transport retains reservation and halt_cancel_transport_unavailable."""
        self.order(qty=5)
        self.fill(quantity=5)
        self.fee(amount="0")
        self.order("pending", qty=5)
        self.restart()
        self.assertFalse(self.action("observe_risk", {"SYNTH.TEST": "501.00"}))
        snap = self.state.snapshot()
        self.assertEqual(snap["halt"], "aggregate_exposure_cap_exceeded")
        self.assertIn("halt_cancel_transport_unavailable", snap["alerts"])
        pending = next(o for o in snap["orders"] if o["intent"] == "pending")
        self.assertEqual((pending["status"], pending["reserved_cents"]), ("accepted", 50000))
        self.economics(5, 950000, 0)
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit"]*2)
        self.restart()
        self.assertIn("halt_cancel_transport_unavailable", self.state.snapshot()["alerts"])
        self.assertFalse(self.state.snapshot()["ready"])

    def test_fresh_journal_binding_and_limit_refusals_have_exact_reasons(self):
        """Fresh journal rejects every binding/limit guard before database creation, including live-port literals."""
        self.close_state()
        cases = [(change, {}, "unsupported_broker_endpoint_schema") for change in [
            {"broker": "ALPACA"}, {"endpoint": "127.0.0.1:4001"},
            {"endpoint": "127.0.0.1:7496"}, {"endpoint": "127.0.0.1:7497"}, {"schema": 2}]]
        cases += [({"client_id": value}, {}, "invalid_client_owner")
                  for value in [0, -1, True, 176.0, 1000]]
        cases += [({field: value}, {}, "full_digest_required")
                  for field in ["plan_sha256", "source_sha256"] for value in ["abc", "G"*64]]
        cases += [({"source_version": "2.0.0rc6"}, {}, "selected_rc5_source_required"),
                  ({"source_revision": "d"*40}, {}, "selected_rc5_source_required")]
        limits = self.module.Limits()
        cases += [({}, {field: 0}, "positive_integer_limits_required") for field in asdict(limits)]
        cases += [({}, {"order_shares": value}, "positive_integer_limits_required")
                  for value in [-1, True, 10.0]]
        cases += [({}, change, "contradictory_limits") for change in [
            {"control_reserve": limits.request_calls},
            {"session_close_ns": limits.session_open_ns},
            {"backoff_initial_ns": limits.backoff_max_ns+1}]]
        for index, (binding_change, limit_change, reason) in enumerate(cases):
            with self.subTest(binding=binding_change, limits=limit_change):
                path = Path(self.tmp.name)/("invalid-binding-"+str(index)+".sqlite")
                with self.assertRaises(self.module.Refused) as result:
                    self.open_state(replace(self.binding, **binding_change), path,
                                    replace(limits, **limit_change))
                self.assertEqual(str(result.exception), reason)
                self.assertFalse(path.exists())
                self.record["sequence"].append({"operation": "fresh_invalid_binding",
                                                "binding_change": binding_change, "limit_change": limit_change,
                                                "expected": reason, "actual": str(result.exception),
                                                "journal_created": path.exists()})
        self.state = self.open_state()

    def test_journal_symlink_refused_before_mutating_target(self):
        """Symlink journal refuses with journal_symlink_refused, preserving target bytes and account ownership recovery."""
        self.close_state()
        before = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        alias = Path(self.tmp.name)/"alias.sqlite"
        alias.symlink_to(self.db_path)
        with self.assertRaises(self.module.Refused) as result:
            self.open_state(db_path=alias)
        self.assertEqual(str(result.exception), "journal_symlink_refused")
        after = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        self.assertEqual(after, before)
        self.assertTrue(alias.is_symlink())
        self.record["sequence"].append({"operation": "open_symlink", "expected": "journal_symlink_refused",
                                        "actual": str(result.exception), "journal_sha256_before": before,
                                        "journal_sha256_after": after})
        self.state = self.open_state()

    def test_account_endpoint_client_plan_source_schema_reopen_before_mutation(self):
        """Changed immutable binding refuses opening before journal mutation; file digest unchanged."""
        self.order()
        self.close_state()
        before = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        changes = [{"broker": "ALPACA"}, {"endpoint": "127.0.0.1:4001"},
                   {"endpoint": "127.0.0.1:7496"}, {"endpoint": "127.0.0.1:7497"},
                   {"account_fingerprint": "a"*64}, {"client_id": 177},
                   {"plan_sha256": "b"*64}, {"source_sha256": "c"*64},
                   {"source_revision": "d"*40}, {"source_version": "2.0.0rc6"}, {"schema": 2}]
        for change in changes:
            with self.subTest(change=change):
                entry = {"operation": "reopen_changed_binding", "change": change,
                         "journal_sha256_before": before, "expected": "refused_without_mutation"}
                self.record["sequence"].append(entry)
                with self.assertRaises(self.module.Refused) as result:
                    self.open_state(replace(self.binding, **change))
                self.assertEqual(str(result.exception), "immutable_binding_mismatch")
                after = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
                entry.update({"actual": str(result.exception), "journal_sha256_after": after})
                self.assertEqual(after, before)
        self.state = self.open_state()
        self.assertEqual(len(self.state.snapshot()["orders"]), 1)

    def test_limit_binding_mismatch_leaves_journal_unchanged(self):
        """Changing frozen numeric limits refuses reopening without mutation."""
        self.order()
        self.close_state()
        before = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(self.module.Refused, "immutable_binding_mismatch") as result:
            self.module.PaperState(self.db_path, self.binding,
                                  limits=replace(self.module.Limits(), order_shares=9),
                                  lock_root=Path(self.tmp.name)/"locks", clock=self.clock,
                                  stop_path=Path(self.tmp.name)/"STOP")
        after = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        self.record["sequence"].append({"operation": "reopen_changed_limits", "expected": "refused_without_mutation",
                                        "actual": str(result.exception), "journal_sha256_before": before,
                                        "journal_sha256_after": after})
        self.assertEqual(after, before)
        self.state = self.open_state()

    def test_competing_process_same_account_different_journal_refused(self):
        """Separate process same account lock rejects before creating second database."""
        second = Path(self.tmp.name) / "second.sqlite"
        code = """import importlib.util,sys,json
from pathlib import Path
s=importlib.util.spec_from_file_location('ibkr_native_state',sys.argv[1]);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
try:
 m.PaperState(Path(sys.argv[2]),m.Binding(**json.loads(sys.argv[3])),lock_root=Path(sys.argv[4]),clock=lambda:1500000000000,stop_path=Path(sys.argv[5]))
except m.Refused as e:
 print(str(e));sys.exit(23)
sys.exit(0)
"""
        r = subprocess.run([sys.executable, "-c", code, str(STATE_PATH), str(second),
                            json.dumps(asdict(self.binding)), str(Path(self.tmp.name)/"locks"),
                            str(Path(self.tmp.name)/"STOP")], capture_output=True, text=True)
        self.record["sequence"].append({"operation": "competing_process", "exit": r.returncode, "stdout": r.stdout.strip(), "second_db_created": second.exists()})
        self.assertEqual(r.returncode, 23)
        self.assertIn("account_writer_already_running", r.stdout)
        self.assertFalse(second.exists())

    def test_fresh_admission_quote_latches_101_dollar_drawdown(self):
        """Fresh89.90 on held10 bought100 exposes101 loss: halt before next submit, survives restart."""
        self.order()
        self.fill(quantity=10)
        self.fee(amount="0")
        with self.assertRaisesRegex(self.module.Refused, "halted"):
            self.order("next", qty=1, price="89.90", quote_price="89.90")
        self.assertEqual(self.state.snapshot()["halt"], "drawdown_cap_exceeded")
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit"])
        self.economics(10, 900000, 0)
        self.restart()
        self.assertEqual(self.state.snapshot()["halt"], "drawdown_cap_exceeded")
        self.assertFalse(self.state.snapshot()["ready"])

    def test_late_cancelled_sell_revalidates_other_sell_reservation(self):
        """Late old sell3 leaves held7 against new sell10: numeric halt and cancellation of new order."""
        self.order()
        self.fill(quantity=10)
        self.fee(amount="0")
        self.order("old_sell", side="SELL")
        self.action("cancel", "old_sell", self.transport)
        self.action("status", "old_sell", "cancelled", 0)
        self.order("new_sell", side="SELL")
        self.fill("old-sell-exec", 3, "100.00", "old_sell")
        self.fee("old-sell-exec", "0")
        self.economics(7, 930000, 0)
        self.assertEqual(self.state.snapshot()["halt"], "aggregate_sell_reservation_exceeds_position")
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit", "submit", "cancel", "submit", "cancel"])
        self.assertEqual(self.transport.calls[-1]["identity"]["order_id"], 73)
        self.assertEqual(next(o for o in self.state.snapshot()["orders"] if o["intent"] == "new_sell")["status"], "cancel_pending")
        self.restart()
        self.assertEqual(self.state.snapshot()["halt"], "aggregate_sell_reservation_exceeds_position")

    def test_control_window_renewal_cannot_clear_submission_backoff(self):
        """Lookup renews control capacity at window boundary but submission deadline remains unchanged."""
        for i in range(5):
            self.order(str(i), qty=1)
        self.clock.now += 59_999_999_999
        with self.assertRaisesRegex(self.module.Refused, "request_budget"):
            self.order("overflow", qty=1)
        deadline = self.state.snapshot()["budget"]["blocked_until_ns"]
        self.clock.now = NOW+60_000_000_000
        self.action("lookup", "0", self.transport)
        self.assertEqual(self.state.snapshot()["budget"]["blocked_until_ns"], deadline)
        with self.assertRaisesRegex(self.module.Refused, "request_budget"):
            self.order("still_paused", qty=1)
        self.assertEqual([c["kind"] for c in self.transport.calls], ["submit"]*5+["lookup"])
        self.clock.now = deadline
        self.assertEqual(self.order("resumed", qty=1), "accepted")

    def test_definitive_rejection_reconciles_without_fabricated_native_ids(self):
        """Conclusive rejected intent with no IDs is terminal: independent empty broker snapshot clears restart gap."""
        self.transport.submit_mode = "reject"
        self.order()
        self.restart()
        observed = self.complete_snapshot()
        self.assertEqual(observed["orders"], [])
        self.assertEqual((observed["positions"], observed["cash"], observed["fees"]), ({}, "10000.00", "0.00"))
        self.assertTrue(self.action("reconcile", observed))
        order = self.state.snapshot()["orders"][0]
        self.assertEqual((order["identity"], order["filled"], order["reserved_cents"], order["status"]), (None, 0, 0, "rejected"))
        self.assertTrue(self.state.snapshot()["ready"])
        self.assertEqual(len(self.transport.calls), 1)

    def test_unexplained_snapshot_observation_cannot_disappear_on_next_match(self):
        """Unknown order, position and cash observations remain conflicts through later matching snapshot/restart."""
        for field, value in [
            ("orders", [{"intent": "foreign", "identity": {"order_ref": "foreign", "order_id": 999}, "filled": 0, "status": "accepted"}]),
            ("positions", {"FOREIGN": 1}), ("cash", "9999.00"),
        ]:
            with self.subTest(field=field):
                self.close_state()
                self.db_path = Path(self.tmp.name)/("conflict-"+field+".sqlite")
                self.broker = FakeBroker()
                self.state = self.open_state()
                conflict = self.complete_snapshot()
                conflict[field] = value
                self.assertFalse(self.action("reconcile", conflict))
                self.assertFalse(self.action("reconcile", self.complete_snapshot()))
                self.assertFalse(self.state.snapshot()["ready"])
                self.assertTrue(self.state.snapshot()["observation_conflicts"])
                self.restart()
                self.assertFalse(self.action("reconcile", self.complete_snapshot()))
                self.economics(0, 1000000, 0)

    def test_evidence_attributes_failed_subtest_to_parent_case(self):
        """Public failed-subtest result must retain parent failed status and subtest diagnostics."""
        class Probe(unittest.TestCase):
            def runTest(self):
                with self.subTest(label="fixture_quantity"):
                    self.assertEqual(3, 2)
        probe_record = {"case": "runTest", "expected": "failed_subtest", "sequence": [],
                        "transport_calls": [], "before": None, "after": None}
        RECORDS.append(probe_record)
        try:
            result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=EvidenceResult).run(unittest.TestSuite([Probe()]))
        finally:
            RECORDS.remove(probe_record)
        self.record["sequence"].append({"operation": "failed_subtest_evidence_probe", "failures": len(result.failures),
                                        "expected_parent": "failed", "actual_parent": copy.deepcopy(probe_record)})
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(probe_record["actual"], "failed")
        self.assertIn("fixture_quantity", probe_record["failure"])
        class SkipProbe(unittest.TestCase):
            def runTest(self):
                with self.subTest(label="required_field"):
                    self.skipTest("required_subcase_fault_fixture")
        skipped_parent = {"case": "runTest", "expected": "skipped_subtest", "sequence": [],
                          "transport_calls": [], "before": None, "after": None}
        offset = len(RECORDS)
        RECORDS.append(skipped_parent)
        try:
            result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=EvidenceResult).run(unittest.TestSuite([SkipProbe()]))
            probe_records = copy.deepcopy(RECORDS[offset:])
        finally:
            del RECORDS[offset:]
        self.record["sequence"].append({"operation": "skipped_subtest_evidence_probe", "skips": len(result.skipped),
                                        "expected_parent": "skipped", "actual_records": probe_records})
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(skipped_parent["actual"], "skipped")
        self.assertEqual(skipped_parent["subtests"][0]["actual"], "skipped")

    def test_acceptance_cli_rejects_required_skipped_case(self):
        """One required case deliberately skipped: CLI exits1, retains skipped outcome rather than acceptance."""
        evidence = RUN_EVIDENCE_DIR or Path(self.tmp.name)/"skip-evidence"
        attempt = RUN_ATTEMPT+"-required-skip"
        code = """import runpy,sys,unittest
target,evidence,attempt=sys.argv[1:]
def required_skip(self,cls):
 name='test_duplicate_intent_has_one_durable_transport_attempt'
 setattr(cls,name,unittest.skip('required_case_fault_fixture')(getattr(cls,name)))
 return unittest.TestSuite([cls(name)])
unittest.TestLoader.loadTestsFromTestCase=required_skip
sys.argv=[target,'--evidence-dir',evidence,'--attempt',attempt]
runpy.run_path(target,run_name='__main__')
"""
        result = subprocess.run([sys.executable, "-c", code, str(Path(__file__)), str(evidence), attempt],
                                capture_output=True, text=True)
        artifact = json.loads((evidence/(attempt+".json")).read_text())
        returned_output = re.sub(r"(?m)^(Ran \d+ tests? in )\d+\.\d+s$", r"\1<elapsed>s",
                                 (result.stdout+result.stderr).replace(str(evidence), "<private-evidence>").replace(str(ROOT), "<checkout>"))
        self.record["sequence"].append({"operation": "required_skip_cli_probe", "expected_exit": 1,
                                        "actual_exit": result.returncode, "artifact": artifact,
                                        "returned_output": returned_output})
        self.assertIn("Ran 1 test in <elapsed>s", returned_output)
        self.assertEqual(result.returncode, 1)
        self.assertEqual((artifact["tests"], artifact["skips"], artifact["exit_code"]), (1, 1, 1))
        self.assertEqual(artifact["cases"][0]["actual"], "skipped")


class EvidenceResult(unittest.TextTestResult):
    def startTest(self, test):
        self.current_case = test
        super().startTest(test)

    def case_record(self, test):
        name = test.id().split(".")[-1]
        case = next((r for r in reversed(RECORDS) if r["case"] == name), None)
        if case is None:
            case = {"case": name, "expected": test.shortDescription(), "sequence": [],
                    "transport_calls": [], "before": None, "after": None}
            RECORDS.append(case)
        return case

    def diagnostic(self, err):
        message = "".join(traceback.format_exception(*err)).replace(str(ROOT), "<checkout>")
        # Keep public traceback diagnostics and source basenames, without host paths.
        import re
        return re.sub(r'File "(/[^\"]+)"', lambda m: 'File "<source>/'+Path(m.group(1)).name+'"', message)

    def failed(self, test, message):
        case = self.case_record(test)
        case["actual"] = "failed"
        case["failure"] = (case.get("failure") or "")+message

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.failed(test, self.diagnostic(err))

    def addError(self, test, err):
        super().addError(test, err)
        self.failed(test, self.diagnostic(err))

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        case = self.case_record(test)
        message = self.diagnostic(err) if err is not None else None
        case.setdefault("subtests", []).append({"name": subtest.id(), "actual": "failed" if err else "passed", "failure": message})
        if err is not None:
            self.failed(test, subtest.id()+"\n"+message)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        parent = getattr(self, "current_case", None) or test
        case = self.case_record(parent)
        if case.get("actual") != "failed":
            case["actual"] = "skipped"
        case.setdefault("failure", None)
        case["skip_reason"] = reason
        if parent is not test:
            case.setdefault("subtests", []).append({"name": test.id(), "actual": "skipped", "skip_reason": reason})

    def stopTest(self, test):
        case = self.case_record(test)
        case.setdefault("actual", "passed")
        case.setdefault("failure", None)
        super().stopTest(test)
        self.current_case = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--attempt", default="local")
    args, rest = parser.parse_known_args()
    RUN_EVIDENCE_DIR, RUN_ATTEMPT = args.evidence_dir, args.attempt
    result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(StateCases))
    acceptance_exit = 0 if result.wasSuccessful() and not result.skipped else 1
    if args.evidence_dir:
        args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = args.evidence_dir / (args.attempt+".json")
        if target.exists():
            raise SystemExit("evidence_attempt_already_exists")
        artifact = {"scope": "offline_synthetic_integration", "attempt": args.attempt,
                    "broker_network_calls": 0, "tests": result.testsRun,
                    "failures": len(result.failures), "errors": len(result.errors),
                    "skips": len(result.skipped), "exit_code": acceptance_exit,
                    "acceptance_status": "blocked_required_skips" if result.skipped else ("passed" if acceptance_exit == 0 else "failed"),
                    "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in [STATE_PATH, FREEZE_PATH, Path(__file__)] if p.exists()},
                    "cases": RECORDS}
        target.write_text(json.dumps(artifact, sort_keys=True, indent=2)+"\n")
        target.chmod(0o600)
        print("evidence="+str(target)+" sha256="+hashlib.sha256(target.read_bytes()).hexdigest())
    if result.skipped:
        print("acceptance=blocked_required_skips")
    raise SystemExit(acceptance_exit)
