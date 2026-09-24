"""Offline tests for the minimal native-fault harness; fake transport, no network.

Evidence class: local synthetic fixture. The fake mimics AlpacaPaperTransport's
engine seams (before_submit -> before_request -> sink_observation) around the
real runner.Controller and safety.Ledger; it establishes no broker behaviour.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "blueprints/us-equities/adaptive-paper"
HARNESS = ENGINE / "native-faults/harness.py"
sys.path.insert(0, str(ENGINE))
try:
    import native_adapter  # noqa: F401  (real module under the pinned native runtime)
except ImportError:
    # System python3 lacks nautilus_trader; Controller.before_submit only needs this class.
    stub = types.ModuleType("native_adapter")
    stub.NativeOrderRejected = type("NativeOrderRejected", (RuntimeError,), {})
    sys.modules["native_adapter"] = stub
SPEC = importlib.util.spec_from_file_location("native_faults_min_harness", HARNESS)
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)
import safety  # noqa: E402  (same module object the harness imported)
from transport import (TERMINAL, AmbiguousSubmission, RejectedSubmission, SUB_PENNY_REFUSAL,  # noqa: E402
                       TransportError, documented_refusal, violates_minimum_price_variance)

try:  # package mode (python -m unittest tests.x) or discover -s tests (top-level modules)
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    _HERMETIC_TOKEN = patch_default_stop(h)


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


KEY, SECRET = "PKFAKEKEYVALUE0001", "fakesecretvalue0002"
ACCOUNT_ID = "acct-identity-should-never-appear"


class NotSent(TransportError):
    not_sent = True


class FakeAPIError(Exception):
    """Shape of alpaca-py's APIError: code and message parsed from the response body."""

    def __init__(self, body):
        super().__init__("provider text that must not be recorded")
        self.code, self.message = body.get("code"), body.get("message")


DOCUMENTED_SUB_PENNY = {"code": 42210000, "message": "invalid limit_price 240.0001. sub-penny increment "
                                                     "does not fulfill minimum pricing criteria"}


class FakeClient:
    def get_clock(self):
        close = datetime.now(timezone.utc) + timedelta(hours=2)
        return {"is_open": True, "next_close": close.strftime("%Y-%m-%dT%H:%M:%SZ")}

    def get_account(self):
        return {"id": ACCOUNT_ID}


class FakePort:
    """Engine-seam fake: every broker call reports a response to the observer.

    Mirrors AlpacaPaperTransport's current semantics: a sub-penny POST is answered
    with a 422 (by default Alpaca's documented minimum-price-variance body), then a
    client-id lookup 404, and classified by the real transport.documented_refusal;
    a cancel sends the DELETE to a known order whatever its cached status and
    treats 404/422 as data once the follow-up read shows it terminal."""
    scenario = {}
    instances = []

    def __init__(self, key, secret, symbols, *, before_request, before_submit, sink_observation,
                 request_observer, history_start):
        self.before_request, self.before_submit = before_request, before_submit
        self.sink, self.observer = sink_observation, request_observer
        self.orders, self.positions, self.reasons = {}, list(self.scenario.get("positions", [])), set()
        self.posts, self.deletes, self.stopped, self.started, self.cancel_calls = 0, [], 0, False, 0
        self.in_flight_at_first_post = None
        self._client = FakeClient()
        FakePort.instances.append(self)

    @property
    def ready(self):
        return self.started and not self.stopped

    @property
    def health(self):
        return {"reasons": sorted(self.reasons)}

    def quote(self):
        self.on_quote({"symbol": "SPY", "bid": "600.00", "ask": "600.02", "ts_ns": time.time_ns(), "halted": False})

    async def start(self, on_quote, on_order):
        self.on_quote, self.started = on_quote, True
        self.quote()

    async def _http(self, kind, status):
        await self.before_request(kind)
        self.observer({"kind": kind, "status": status})

    async def submit(self, order):
        self.quote()
        self.before_submit(dict(order))
        try:
            await self.before_request("submit", client_id=order["client_order_id"])
        except Exception:
            raise NotSent("submission prevented before HTTP request") from None
        if self.posts == 0 and "run_root" in self.scenario:
            self.in_flight_at_first_post = [json.loads(m.read_text())
                                            for m in self.scenario["run_root"].glob("*/IN_FLIGHT")]
        self.posts += 1
        if violates_minimum_price_variance(order["limit_price"]):
            status = self.scenario.get("c04_status", 422)
            self.observer({"kind": "submit", "status": status})
            await self._http("read", 404)  # client-id absence lookup
            refusal = documented_refusal(FakeAPIError(self.scenario.get("c04_body", DOCUMENTED_SUB_PENNY)),
                                         status, order)
            if status in (401, 403, 404) or refusal is not None:
                raise RejectedSubmission(status, refusal)
            self.reasons.add("submission_ambiguous")
            raise AmbiguousSubmission("submission unresolved; no automatic retry")
        self.observer({"kind": "submit", "status": 200})
        record = {"client_order_id": order["client_order_id"], "id": "b-%d" % self.posts, "symbol": "SPY",
                  "side": "buy", "qty": "1", "filled_qty": "0", "filled_avg_price": None,
                  "limit_price": order["limit_price"], "status": "new", "updated_at_ns": time.time_ns()}
        self.orders[record["client_order_id"]] = record
        self.sink(dict(record))
        if self.scenario.get("signal_after_submit"):
            os.kill(os.getpid(), signal.SIGTERM)
        return dict(record)

    async def cancel(self, cid):
        self.cancel_calls += 1
        if cid not in self.orders:
            raise TransportError("cancellation requires an owned durable intent")
        if self.scenario.get("cancel_raises_first") and self.cancel_calls == 1:
            raise RuntimeError("provider text that must not be recorded")
        order = self.orders[cid]
        if self.scenario.get("legacy_short_circuit") and order["status"] in TERMINAL:
            await self._http("read", 200)  # the pre-2026-09-24 engine: lookup, then no DELETE
            return dict(order)
        answer = self.scenario.get("terminal_delete_answer", 422) if order["status"] in TERMINAL else 204
        await self._http("cancel", answer)
        self.deletes.append(cid)
        if answer == 204:
            order.update(status="canceled", updated_at_ns=time.time_ns())
            if self.scenario.get("leak_position_on_cancel"):
                self.positions = [{"symbol": "SPY", "qty": "1", "avg_entry_price": "300"}]
        elif answer not in (404, 422):
            self.reasons.add("cancellation_unresolved")
        await self._http("read", 200)
        self.sink(dict(order))
        return dict(order)

    async def snapshot(self):
        await self._http("read", 200)
        if self.scenario.get("external_open_order"):
            raise TransportError("snapshot incomplete; admissions remain frozen")
        for order in self.orders.values():
            self.sink(dict(order))
        return {"account": {"cash": "100000"}, "positions": list(self.positions),
                "orders": [dict(o) for o in self.orders.values()], "complete": True}

    async def stop(self):
        self.stopped += 1
        if self.scenario.get("stop_raises"):
            raise RuntimeError("stream thread still alive")


class HarnessRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.state_base = base / "state/native-agent-stack"
        env = base / "paper.env"
        env.write_text("APCA_API_KEY_ID=%s\nAPCA_API_SECRET_KEY=%s\n" % (KEY, SECRET))
        env.chmod(0o600)
        self.env, self.out = env, base / "out/receipt.json"
        self.root = self.state_base / "native-faults-test"
        self.patches = [patch.object(h, "STATE_BASE", self.state_base),
                        patch.object(h, "DEFAULT_ROOT", self.state_base / "alpaca-paper"),
                        patch.object(h, "LOCK_ROOT", base / "locks"),
                        patch.object(safety, "DEFAULT_STOP", base / "no-stop/STOP")]
        for p in self.patches:
            p.start()
        FakePort.instances, FakePort.scenario = [], {}
        self.handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_harness(self, **scenario):
        FakePort.scenario = scenario
        code = h.run(self.env, self.root, self.out, factory=FakePort)
        receipt = json.loads(self.out.read_text())
        self.assertEqual(len(FakePort.instances), 1)  # never a second transport
        port = FakePort.instances[0]
        self.assertEqual(port.stopped, 1)
        self.assertLessEqual(port.posts, 4)
        self.assertEqual({s: signal.getsignal(s) for s in self.handlers}, self.handlers)
        text = self.out.read_text()
        for secret in (KEY, SECRET, ACCOUNT_ID, "provider text"):
            self.assertNotIn(secret, text)
        return code, receipt, port

    @staticmethod
    def flagged(cleanup):
        async def wrapper(harness, port):
            harness.cleaning = True
            return await cleanup(harness, port)
        return wrapper

    def markers(self, name="CLEANUP_REQUIRED"):
        return list(self.root.glob("*/" + name))

    def test_full_sequence_reaches_native_faults_passed_offline(self):
        code, receipt, port = self.run_harness(run_root=self.root)
        cases = {c["id"]: c for c in receipt["cases"]}
        prefix = receipt["client_id_prefix"]
        self.assertEqual([c["id"] for c in receipt["cases"]], ["C01", "C02", "C05", "C04"])
        # Write-ahead marker existed before the first POST and was removed after flat proof.
        self.assertEqual(port.in_flight_at_first_post, [
            {"run_id": prefix.rstrip("-"), "client_id_prefix": prefix,
             "at": port.in_flight_at_first_post[0]["at"]}])
        self.assertEqual(self.markers("IN_FLIGHT"), [])
        self.assertFalse(receipt["in_flight_marker_present"])
        self.assertEqual(cases["C01"]["outcome"], "passed")
        self.assertEqual(cases["C01"]["detail"]["ledger"]["status"], "new")
        self.assertEqual(cases["C01"]["detail"]["limit_price"], "300.00")
        self.assertEqual(cases["C02"]["outcome"], "passed")
        self.assertEqual(cases["C02"]["detail"]["ledger"]["status"], "canceled")
        # C05: the second cancel sends the DELETE; the broker's 422 is data.
        c05 = cases["C05"]
        self.assertEqual((c05["outcome"], c05["evidence_class"]), ("passed", "native_paper"))
        self.assertEqual([r["kind"] for r in c05["requests"]], ["cancel", "read"])
        self.assertTrue(c05["detail"]["delete_sent"])
        self.assertEqual(c05["detail"]["cancel_http_statuses"], [422])
        self.assertTrue(c05["detail"]["broker_refusal_observed"])
        self.assertEqual(c05["detail"]["ledger_before"], c05["detail"]["ledger_after"])
        self.assertEqual(c05["detail"]["new_transport_freeze_reasons"], [])
        # C04: the sub-penny order reaches the broker and its documented 422 is definitive.
        c04 = cases["C04"]
        self.assertEqual((c04["outcome"], c04["evidence_class"]), ("passed", "native_paper"))
        self.assertEqual(c04["detail"]["limit_price"], "240.0001")
        self.assertEqual([(r["kind"], r["status"]) for r in c04["requests"]], [("submit", 422), ("read", 404)])
        self.assertEqual(c04["detail"]["ledger"]["status"], "broker_refused")
        self.assertEqual(c04["detail"]["ledger_refusal"], {"http_status": 422, "refusal": SUB_PENNY_REFUSAL})
        self.assertEqual(c04["detail"]["effect_before"], c04["detail"]["effect_after"])
        self.assertEqual(receipt["c04_pre_send_exemption"],
                         "FaultLedger exempts only client id %sc04 from invalid_price_increment" % prefix)
        self.assertEqual(port.posts, 2)
        self.assertEqual(port.deletes, [prefix + "c01", prefix + "c01"])
        self.assertEqual(receipt["cleanup"]["cancels"], [])
        self.assertTrue(receipt["cleanup"]["flat"])
        self.assertEqual((receipt["status"], code), ("native_faults_passed", 0))
        self.assertEqual(self.markers(), [])
        for case in ("C01", "C02"):
            self.assertEqual(cases[case]["evidence_class"], "native_paper")
        plan_sha = __import__("hashlib").sha256((HARNESS.parent / "plan.json").read_bytes()).hexdigest()
        self.assertEqual(receipt["plan_sha256"], plan_sha)

    def test_legacy_short_circuit_is_never_native_evidence(self):
        # The engine as run on 2026-09-23: a client-id GET found the order terminal, no DELETE.
        code, receipt, port = self.run_harness(legacy_short_circuit=True)
        c05 = {c["id"]: c for c in receipt["cases"]}["C05"]
        self.assertEqual((c05["outcome"], c05["evidence_class"]), ("passed", "engine_short_circuit"))
        self.assertFalse(c05["detail"]["delete_sent"])
        self.assertFalse(c05["detail"]["broker_refusal_observed"])
        self.assertEqual((receipt["status"], code), ("native_faults_incomplete", 1))

    def test_c05_unresolved_delete_answer_fails(self):
        code, receipt, port = self.run_harness(terminal_delete_answer=500)
        cases = {c["id"]: c for c in receipt["cases"]}
        self.assertEqual(cases["C05"]["outcome"], "failed")
        self.assertEqual(cases["C05"]["detail"]["new_transport_freeze_reasons"], ["cancellation_unresolved"])
        self.assertEqual(cases["C04"]["outcome"], "not_run")
        self.assertEqual(port.posts, 1)
        self.assertEqual((receipt["status"], code), ("native_faults_failed", 1))

    def test_c05_404_answer_is_data(self):
        code, receipt, port = self.run_harness(terminal_delete_answer=404)
        c05 = {c["id"]: c for c in receipt["cases"]}["C05"]
        self.assertEqual((c05["outcome"], c05["evidence_class"]), ("passed", "native_paper"))
        self.assertEqual(c05["detail"]["cancel_http_statuses"], [404])
        self.assertEqual((receipt["status"], code), ("native_faults_passed", 0))

    def test_c04_definitive_403_passes(self):
        code, receipt, port = self.run_harness(c04_status=403)
        c04 = {c["id"]: c for c in receipt["cases"]}["C04"]
        self.assertEqual(c04["outcome"], "passed")
        self.assertEqual(c04["detail"]["ledger_refusal"], {"http_status": 403, "refusal": None})
        self.assertEqual((receipt["status"], code), ("native_faults_passed", 0))

    def test_c04_undocumented_422_stays_ambiguous_and_fails(self):
        # "client_order_id must be unique" proves an order exists: never a definitive refusal.
        for label, body in (("duplicate", {"code": 40010001, "message": "client_order_id must be unique"}),
                            ("other_code", dict(DOCUMENTED_SUB_PENNY, code=40010001))):
            with self.subTest(label=label):
                FakePort.instances = []
                self.root = self.state_base / ("native-faults-" + label)
                code, receipt, port = self.run_harness(c04_body=body)
                c04 = {c["id"]: c for c in receipt["cases"]}["C04"]
                self.assertEqual(c04["outcome"], "failed")
                self.assertEqual(c04["detail"]["ledger"]["status"], "reserved")
                self.assertIsNone(c04["detail"]["ledger_refusal"])
                self.assertEqual(c04["detail"]["error"]["type"], "AmbiguousSubmission")
                # An ambiguous submission is never proven flat: the run is marked for manual recovery.
                self.assertFalse(receipt["cleanup"]["flat"])
                self.assertEqual((receipt["status"], code), ("cleanup_required", 3))

    def test_flat_start_refusal_makes_no_write(self):
        code, receipt, port = self.run_harness(positions=[{"symbol": "AAPL", "qty": "3", "avg_entry_price": "1"}])
        self.assertEqual((code, receipt["status"], port.posts), (2, "refused", 0))
        self.assertEqual(receipt["error"]["reason"], "account_not_flat_or_open_orders")
        self.assertEqual(receipt["cleanup"]["proof"], "not_required_no_broker_writes")
        self.assertTrue(all(c["outcome"] == "not_run" for c in receipt["cases"]))
        self.assertEqual(self.markers(), [])
        self.assertEqual(self.markers("IN_FLIGHT"), [])

    def test_external_open_order_refuses_start(self):
        code, receipt, port = self.run_harness(external_open_order=True)
        self.assertEqual((code, receipt["status"], port.posts), (2, "refused", 0))

    def test_exception_stops_cases_and_cleanup_cancels_on_same_transport(self):
        code, receipt, port = self.run_harness(cancel_raises_first=True)
        cases = {c["id"]: c for c in receipt["cases"]}
        self.assertEqual(cases["C02"]["outcome"], "error")
        self.assertEqual(cases["C02"]["detail"]["error"], {"type": "RuntimeError", "reason": None})
        self.assertEqual((cases["C05"]["outcome"], cases["C04"]["outcome"]), ("not_run", "not_run"))
        self.assertEqual(receipt["cleanup"]["cancels"][0]["result_status"], "canceled")
        self.assertTrue(receipt["cleanup"]["flat"])
        self.assertEqual((receipt["status"], code), ("native_faults_failed", 1))

    def test_signal_interrupts_then_cleans_up(self):
        code, receipt, port = self.run_harness(signal_after_submit=True)
        self.assertEqual(receipt["interrupted"], "SIGTERM")
        self.assertEqual([c["outcome"] for c in receipt["cases"]], ["passed", "not_run", "not_run", "not_run"])
        self.assertEqual(port.deletes, [receipt["client_id_prefix"] + "c01"])
        self.assertTrue(receipt["cleanup"]["flat"])
        self.assertEqual((receipt["status"], code), ("interrupted", 1))

    def test_unproven_cleanup_writes_marker_and_exits_nonzero(self):
        code, receipt, port = self.run_harness(leak_position_on_cancel=True)
        self.assertFalse(receipt["cleanup"]["flat"])
        self.assertEqual((receipt["status"], code), ("cleanup_required", 3))
        self.assertEqual(len(self.markers()), 1)
        in_flight = self.markers("IN_FLIGHT")
        self.assertEqual(len(in_flight), 1)
        self.assertEqual(json.loads(in_flight[0].read_text())["client_id_prefix"], receipt["client_id_prefix"])
        self.assertTrue(receipt["in_flight_marker_present"])

    def test_cleanup_exception_still_writes_the_marker_and_a_receipt(self):
        # C02's cancel raises, so C01's order is still open when cleanup runs and
        # cleanup's own settle call then raises.
        original = h.Harness.settle

        async def settle_then_break(harness, cid):
            if harness.cleaning:
                raise RuntimeError("settle failed")
            return await original(harness, cid)
        with patch.object(h.Harness, "settle", settle_then_break), \
                patch.object(h.Harness, "cleaning", False, create=True), \
                patch.object(h.Harness, "cleanup", self.flagged(h.Harness.cleanup)):
            code, receipt, port = self.run_harness(cancel_raises_first=True)
        self.assertEqual((receipt["cleanup"]["proof"], receipt["cleanup"]["flat"]), ("failed", False))
        self.assertEqual((receipt["status"], code), ("cleanup_required", 3))
        self.assertEqual(len(self.markers()), 1)
        self.assertEqual(len(self.markers("IN_FLIGHT")), 1)

    def test_prior_run_marker_refuses_before_any_transport(self):
        for name in ("IN_FLIGHT", "CLEANUP_REQUIRED"):
            with self.subTest(name=name):
                stale = self.root / ("nf-old-" + name.lower())
                stale.mkdir(parents=True)
                (stale / name).write_text("{}\n")
                FakePort.instances = []
                code = h.run(self.env, self.root, self.out, factory=FakePort)
                receipt = json.loads(self.out.read_text())
                self.assertEqual((code, receipt["status"]), (2, "not_started"))
                self.assertEqual(receipt["error"]["reason"], "prior_run_marker_present")
                self.assertEqual(FakePort.instances, [])
                (stale / name).unlink()

    def test_in_flight_marker_is_fsynced_before_the_first_post(self):
        with patch.object(h.os, "fsync", wraps=h.os.fsync) as fsync:
            code, receipt, port = self.run_harness(run_root=self.root)
        self.assertGreaterEqual(fsync.call_count, 2)  # the marker file and its directory
        self.assertEqual(len(port.in_flight_at_first_post), 1)

    def test_transport_stop_failure_is_never_a_pass(self):
        code, receipt, port = self.run_harness(stop_raises=True)
        self.assertEqual((receipt["status"], code), ("error", 1))
        self.assertEqual(receipt["stop_error"]["type"], "RuntimeError")

    def test_state_root_must_be_dedicated(self):
        for bad in (self.state_base, self.state_base / "alpaca-paper", self.state_base / "alpaca-paper/x",
                    Path(self.tmp.name) / "elsewhere"):
            with self.assertRaises(ValueError):
                h.dedicated_root(bad)
        self.assertEqual(h.dedicated_root(self.root), self.root.resolve())


class Units(unittest.TestCase):
    def test_post_ceiling_refuses_before_controller(self):
        plan, sha = h.load_plan()
        harness = object.__new__(h.Harness)
        harness.plan, harness.posts = plan, 0
        calls = []

        async def budget(kind, client_id=None):
            calls.append(kind)
        harness.controller = types.SimpleNamespace(before_request=budget)
        for _ in range(4):
            asyncio.run(harness.before_request("submit", client_id="x"))
        with self.assertRaises(safety.SafetyError):
            asyncio.run(harness.before_request("submit", client_id="x"))
        self.assertEqual((harness.posts, len(calls)), (4, 4))
        asyncio.run(harness.before_request("read"))
        self.assertEqual(harness.posts, 4)

    def test_plan_bounds(self):
        plan = json.loads((HARNESS.parent / "plan.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            for change in ({"max_posts": 5}, {"symbol": "QQQ"}, {"qty": "2"}, {"max_price_ratio": "0.6"},
                           {"extended_hours": True}, {"cases": plan["cases"][::-1]},
                           {"c04_sub_penny_increment": "0"}, {"c04_sub_penny_increment": "0.01"},
                           {"c04_sub_penny_increment": "-0.0001"}):
                path = Path(tmp) / "plan.json"
                path.write_text(json.dumps(dict(plan, **change)))
                with self.assertRaises(ValueError):
                    h.load_plan(path)

    def test_c04_judge_branches(self):
        effect = {"positions": {}, "cash_delta_usd": "0"}
        refused = {"status": "broker_refused", "filled_qty": "0", "submit_attempted": True, "broker_id_recorded": False}
        ambiguous = dict(refused, status="reserved")
        sub = [{"kind": "submit", "status": 401}]
        self.assertEqual(h.judge_c04(sub, refused, None, effect, effect)[0], "passed")
        for status in (400, 422, 429, 500):  # Ambiguous to the engine; never a definitive refusal.
            self.assertEqual(h.judge_c04([{"kind": "submit", "status": status}], refused, None, effect, effect)[0],
                             "failed")
        documented = {"http_status": 422, "refusal": SUB_PENNY_REFUSAL}
        sub422 = [{"kind": "submit", "status": 422}, {"kind": "read", "status": 404}]
        self.assertEqual(h.judge_c04(sub422, refused, None, effect, effect, documented)[0], "passed")
        # The ledger's own refusal record decides; a 422 without it, or on a live intent, fails.
        self.assertEqual(h.judge_c04(sub422, refused, None, effect, effect,
                                     {"http_status": 422, "refusal": None})[0], "failed")
        self.assertEqual(h.judge_c04(sub422, ambiguous, None, effect, effect, documented)[0], "failed")
        self.assertEqual(h.judge_c04([{"kind": "submit", "status": 500}], refused, None, effect, effect,
                                     documented)[0], "failed")
        self.assertEqual(h.judge_c04(sub, ambiguous, {"type": "AmbiguousSubmission"}, effect, effect)[0], "failed")
        moved = {"positions": {"SPY": "1"}, "cash_delta_usd": "-1"}
        self.assertEqual(h.judge_c04(sub, refused, None, effect, moved)[0], "failed")
        outcome, detail = h.judge_c04([], None, {"type": "NativeOrderRejected", "reason": "invalid_price_increment"},
                                      effect, effect)
        self.assertEqual(outcome, "unobserved")
        self.assertEqual(detail["unobserved_reason"], "engine_refused_before_send: invalid_price_increment")

    def test_c05_judge_records_refusal_and_freeze(self):
        state = {"status": "canceled", "filled_qty": "0", "submit_attempted": True, "broker_id_recorded": True}
        effect = {"positions": {}, "cash_delta_usd": "0"}
        refusal = [{"kind": "read", "status": 200}, {"kind": "cancel", "status": 422}]
        outcome, detail = h.judge_c05(state, state, None, set(), effect, effect, refusal)
        self.assertEqual(outcome, "passed")
        self.assertTrue(detail["broker_refusal_observed"])
        outcome, detail = h.judge_c05(state, state, None, {"cancellation_unresolved"}, effect, effect, refusal)
        self.assertEqual(outcome, "failed")
        self.assertEqual(h.judge_c05(state, state, {"type": "TransportError"}, set(), effect, effect, [])[0], "failed")
        unresolved = [{"kind": "cancel", "status": 503}, {"kind": "read", "status": 200}]
        self.assertEqual(h.judge_c05(state, state, None, set(), effect, effect, unresolved)[0], "failed")
        outcome, detail = h.judge_c05(state, state, None, set(), effect, effect, [{"kind": "read", "status": 200}])
        self.assertEqual((outcome, detail["delete_sent"]), ("passed", False))  # run_cases then marks it engine_short_circuit

    def test_fault_ledger_exempts_only_the_c04_client_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = h.FaultLedger(Path(tmp) / "ledger.sqlite3", sub_penny_client_id="nf-x-c04")
            now = time.time()
            ledger.start_trial(now)
            quote = safety.Quote("SPY", "600", "600.02", now)
            args = {"quote": quote, "now": now, "market_open": True, "session_close": now + 7200,
                    "stop_file": Path(tmp) / "STOP"}
            for cid in ("nf-x-c01", "nf-x-c040", "other"):
                with self.assertRaisesRegex(safety.SafetyError, "invalid_price_increment"):
                    ledger.reserve_intent(cid, "SPY", "buy", "1", "240.0001", **args)
            self.assertTrue(ledger.reserve_intent("nf-x-c04", "SPY", "buy", "1", "240.0001", **args).newly_reserved)
            self.assertTrue(ledger.reserve_intent("nf-x-c01", "SPY", "buy", "1", "240.00", **args).newly_reserved)
            ledger.close()

    def test_c01_c02_judges_use_ledger_state(self):
        state = {"status": "new", "filled_qty": "0", "submit_attempted": True, "broker_id_recorded": True}
        self.assertEqual(h.judge_c01("new", state), "passed")
        self.assertEqual(h.judge_c01("new", dict(state, status="reserved")), "failed")
        self.assertEqual(h.judge_c01("new", None), "failed")
        self.assertEqual(h.judge_c02(dict(state, status="canceled"), "canceled"), "passed")
        self.assertEqual(h.judge_c02(dict(state, status="pending_cancel"), "canceled"), "failed")


if __name__ == "__main__":
    unittest.main()
