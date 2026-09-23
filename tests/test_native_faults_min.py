"""Offline tests for the minimal native-fault harness; fake transport, no network.

Evidence class: local synthetic fixture. The fake mimics AlpacaPaperTransport's
engine seams (before_submit -> before_request -> sink_observation) around the
real runner.Controller and safety.Ledger; it establishes no broker behaviour.
"""
import asyncio
from decimal import Decimal
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
from transport import TERMINAL, TransportError  # noqa: E402

KEY, SECRET = "PKFAKEKEYVALUE0001", "fakesecretvalue0002"
ACCOUNT_ID = "acct-identity-should-never-appear"


class NotSent(TransportError):
    not_sent = True


class FakeClient:
    def get_clock(self):
        close = datetime.now(timezone.utc) + timedelta(hours=2)
        return {"is_open": True, "next_close": close.strftime("%Y-%m-%dT%H:%M:%SZ")}

    def get_account(self):
        return {"id": ACCOUNT_ID}


class FakePort:
    """Engine-seam fake: every broker call reports a response to the observer."""
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
        if Decimal(order["limit_price"]) != Decimal(order["limit_price"]).quantize(Decimal("0.01")):
            self.observer({"kind": "submit", "status": 422})
            raise TransportError("submission unresolved; no automatic retry")
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
        await self._http("read", 200)
        order = self.orders[cid]
        if order["status"] in TERMINAL:
            if self.scenario.get("delete_when_terminal"):
                await self._http("cancel", 422)
                self.deletes.append(cid)
            return dict(order)
        await self._http("cancel", 204)
        self.deletes.append(cid)
        order.update(status="canceled", updated_at_ns=time.time_ns())
        if self.scenario.get("leak_position_on_cancel"):
            self.positions = [{"symbol": "SPY", "qty": "1", "avg_entry_price": "300"}]
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

    def markers(self, name="CLEANUP_REQUIRED"):
        return list(self.root.glob("*/" + name))

    def test_full_sequence_records_engine_state_and_honest_c04(self):
        code, receipt, port = self.run_harness(run_root=self.root)
        cases = {c["id"]: c for c in receipt["cases"]}
        self.assertEqual([c["id"] for c in receipt["cases"]], ["C01", "C02", "C05", "C04"])
        # Write-ahead marker existed before the first POST and was removed after flat proof.
        self.assertEqual(port.in_flight_at_first_post, [
            {"run_id": receipt["client_id_prefix"].rstrip("-"), "client_id_prefix": receipt["client_id_prefix"],
             "at": port.in_flight_at_first_post[0]["at"]}])
        self.assertEqual(self.markers("IN_FLIGHT"), [])
        self.assertFalse(receipt["in_flight_marker_present"])
        self.assertEqual(cases["C01"]["outcome"], "passed")
        self.assertEqual(cases["C01"]["detail"]["ledger"]["status"], "new")
        self.assertEqual(cases["C01"]["detail"]["limit_price"], "300.00")
        self.assertEqual(cases["C02"]["outcome"], "passed")
        self.assertEqual(cases["C02"]["detail"]["ledger"]["status"], "canceled")
        self.assertEqual(cases["C05"]["outcome"], "passed")
        self.assertFalse(cases["C05"]["detail"]["delete_sent"])
        self.assertFalse(cases["C05"]["detail"]["broker_refusal_observed"])
        # The engine Ledger refuses a sub-penny >= $1 price before any POST.
        self.assertEqual(cases["C04"]["outcome"], "unobserved")
        self.assertEqual(cases["C04"]["evidence_class"], "none")
        self.assertEqual(cases["C04"]["requests"], [])
        self.assertEqual(cases["C04"]["detail"]["unobserved_reason"],
                         "engine_refused_before_send: invalid_price_increment")
        self.assertEqual(port.posts, 1)
        self.assertEqual(port.deletes, [receipt["client_id_prefix"] + "c01"])
        self.assertEqual(receipt["status"], "native_faults_incomplete")
        self.assertTrue(receipt["cleanup"]["flat"])
        self.assertEqual(code, 1)
        self.assertEqual(self.markers(), [])
        for case in ("C01", "C02"):
            self.assertEqual(cases[case]["evidence_class"], "native_paper")
        # C05's GET-by-client-id reached the broker but no DELETE was sent.
        self.assertEqual(cases["C05"]["evidence_class"], "engine_short_circuit")
        self.assertEqual([r["kind"] for r in cases["C05"]["requests"]], ["read"])
        plan_sha = __import__("hashlib").sha256((HARNESS.parent / "plan.json").read_bytes()).hexdigest()
        self.assertEqual(receipt["plan_sha256"], plan_sha)

    def test_c05_delete_sent_is_native_paper(self):
        code, receipt, port = self.run_harness(delete_when_terminal=True)
        c05 = {c["id"]: c for c in receipt["cases"]}["C05"]
        self.assertEqual((c05["outcome"], c05["evidence_class"]), ("passed", "native_paper"))
        self.assertTrue(c05["detail"]["delete_sent"])
        self.assertTrue(c05["detail"]["broker_refusal_observed"])
        # C04 is still refused before send, so the run cannot pass.
        self.assertEqual((receipt["status"], code), ("native_faults_incomplete", 1))

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

    def test_c01_c02_judges_use_ledger_state(self):
        state = {"status": "new", "filled_qty": "0", "submit_attempted": True, "broker_id_recorded": True}
        self.assertEqual(h.judge_c01("new", state), "passed")
        self.assertEqual(h.judge_c01("new", dict(state, status="reserved")), "failed")
        self.assertEqual(h.judge_c01("new", None), "failed")
        self.assertEqual(h.judge_c02(dict(state, status="canceled"), "canceled"), "passed")
        self.assertEqual(h.judge_c02(dict(state, status="pending_cancel"), "canceled"), "failed")


if __name__ == "__main__":
    unittest.main()
