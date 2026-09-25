"""Offline tests for the IBKR local acceptance runner (ibkr-acceptance/local_acceptance.py).

Synthetic boundary fixtures only: nothing here connects to TWS or IB Gateway. Everything except
the NautilusBacktestFlow class runs on a plain python3 without nautilus_trader or ibapi; that
class runs the phase strategy inside a NautilusTrader 1.231.0 BacktestEngine (a simulated ARCA
venue, not IBKR) and is skipped when nautilus_trader 1.231.0 is not importable. None of this
establishes the ibkr-local-acceptance gate or IBKR paper behaviour.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
import pwd
import re
import signal
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/engine-nautilus/ibkr-acceptance"
RAW_ACCOUNT = re.compile(r"\b(?:D?[UF]|I)\d{5,}\b")
NY = ZoneInfo("America/New_York")
FAKE_ACCOUNT = "DU7654321"
PINNED = {"nautilus_trader": "1.231.0", "ibapi": "10.45.1"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LA = _load("ibkr_local_acceptance", SOURCE / "local_acceptance.py")
PLAN = LA.load_plan(SOURCE / "local-acceptance-plan.json")
POST = LA.load_plan(SOURCE / "local-acceptance-plan-post.json")
# The frozen per-account latch, audit and lock directory as imported, before any test redirects it.
IMPORTED_CONTROL_DIR = LA.CONTROL_DIR
_MODULE_PATCHES = []


def setUpModule():
    # No test may read or write the real per-account latch, lock or default state directory:
    # every test class below redirects them again to its own temporary directory.
    tmp = tempfile.TemporaryDirectory()
    _MODULE_PATCHES.append(tmp)
    for name in ("CONTROL_DIR", "DEFAULT_STATE_DIR"):
        patch = mock.patch.object(LA, name, Path(tmp.name) / name.lower())
        patch.start()
        _MODULE_PATCHES.append(patch)


def tearDownModule():
    while _MODULE_PATCHES:
        item = _MODULE_PATCHES.pop()
        (item.stop if hasattr(item, "stop") else item.cleanup)()


def isolate_control(case, root: Path) -> Path:
    """Give one test its own frozen control directory and default state directory."""
    control = Path(root) / "control"
    for name, value in (("CONTROL_DIR", control), ("DEFAULT_STATE_DIR", Path(root) / "default-state")):
        patch = mock.patch.object(LA, name, value)
        patch.start()
        case.addCleanup(patch.stop)
    return control


def ny(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=NY).astimezone(timezone.utc)


WEDNESDAY_10AM = ny(2026, 9, 23, 10, 0)
TODAY_HOURS = "20260923:0930-20260923:1600;20260924:0930-20260924:1600"
TODAY_TRADING = "20260923:0400-20260923:2000;20260924:0400-20260924:2000"


# --------------------------------------------------------------------------- plan


class PlanValidation(unittest.TestCase):
    def test_frozen_plans_are_valid(self):
        self.assertEqual(LA.validate_plan(PLAN), [])
        self.assertEqual(LA.validate_plan(POST), [])
        self.assertEqual((PLAN["client_ids"]["node"], PLAN["client_ids"]["check"]), (93, 98))
        self.assertEqual(PLAN["bounds"]["order_ids"], ["R1", "R2", "P1", "P2"])
        self.assertIs(PLAN["bounds"]["marketable_orders"], False)

    def test_post_plan_differs_only_in_the_session(self):
        self.assertEqual((POST["session"]["open"], POST["session"]["close"], POST["session"]["outside_rth"]),
                         ("16:00", "20:00", True))
        for key in set(PLAN) - {"session", "revision_note"}:
            self.assertEqual(POST[key], PLAN[key], key)

    def test_violations_are_reported(self):
        cases = [
            (("bounds", "max_orders"), 5, "max_orders"),
            (("bounds", "marketable_orders"), True, "marketable"),
            (("bounds", "resting_fraction_of_bid"), 0.6, "resting_fraction"),
            (("bounds", "max_quantity_per_order"), 2, "max_quantity"),
            (("bounds", "max_notional_per_order_usd"), 5000, "notional"),
            (("bounds", "order_side"), "SELL", "BUY LIMIT DAY"),
            (("client_ids", "node"), 91, "client ids"),
            (("client_ids", "check"), 95, "client ids"),
            (("engine", "version"), "2.0.0rc5", "engine"),
            (("session", "close_buffer_minutes"), 5, "close_buffer"),
            (("data", "quote_max_age_seconds"), 900, "quote_max_age"),
            (("timeouts", "overall_deadline_seconds"), 900, "overall_deadline"),
            (("exec_engine", "inflight_check_retries"), 5, "in-flight"),
        ]
        for (section, key), value, needle in cases:
            with self.subTest(key=key):
                plan = copy.deepcopy(PLAN)
                plan[section][key] = value
                errors = LA.validate_plan(plan)
                self.assertTrue(any(needle in e for e in errors), (key, errors))
        plan = copy.deepcopy(PLAN)
        plan["timeouts"]["phase_deadline_seconds"]["A"] = 300
        self.assertTrue(any("phase A" in e for e in LA.validate_plan(plan)))
        plan = copy.deepcopy(PLAN)
        plan["paper_ports"] = [4001, 4002]
        self.assertTrue(any("paper_ports" in e for e in LA.validate_plan(plan)))
        plan = copy.deepcopy(PLAN)
        plan["live_ports_refused"] = [4001]
        self.assertTrue(any("live_ports_refused" in e for e in LA.validate_plan(plan)))
        plan = copy.deepcopy(PLAN)
        plan["client_ids"]["reserved_elsewhere"].append(96)
        self.assertTrue(any("fallback band" in e for e in LA.validate_plan(plan)))
        plan = copy.deepcopy(PLAN)
        plan["cases"] = list(reversed(plan["cases"]))
        self.assertTrue(any("A1..A4" in e for e in LA.validate_plan(plan)))
        plan = copy.deepcopy(PLAN)
        plan["receipt"]["gate_receipt"]["schema"]["kind"] = "other"
        self.assertTrue(any("gate receipt schema" in e for e in LA.validate_plan(plan)))
        plan = copy.deepcopy(PLAN)
        del plan["bounds"]
        self.assertTrue(any("missing" in e for e in LA.validate_plan(plan)))

    def test_worst_case_covers_graces_cleanup_and_checkpoints(self):
        t = PLAN["timeouts"]
        floor = (sum(t["phase_deadline_seconds"].values())
                 + 3 * (LA.PHASE_GRACE_SECONDS + LA.TERMINATE_GRACE_SECONDS) + 3 * t["check_seconds"])
        self.assertGreater(LA.worst_case_seconds(PLAN), floor)
        self.assertLessEqual(LA.worst_case_seconds(PLAN), t["overall_deadline_seconds"])
        plan = copy.deepcopy(PLAN)
        plan["timeouts"]["overall_deadline_seconds"] = LA.worst_case_seconds(PLAN) - 1
        self.assertTrue(any("worst-case" in e for e in LA.validate_plan(plan)))

    def test_session_and_outside_rth_must_agree(self):
        for plan, change in [(POST, {"outside_rth": False}), (PLAN, {"outside_rth": True}),
                             (POST, {"contract_hours_field": "liquidHours"}), (PLAN, {"use_contract_liquid_hours": False})]:
            with self.subTest(change=change):
                bad = copy.deepcopy(plan)
                bad["session"].update(change)
                self.assertNotEqual(LA.validate_plan(bad), [])

    def test_ports(self):
        self.assertEqual(LA.port_refusal(PLAN, 4001), "refused_live_port")
        self.assertEqual(LA.port_refusal(PLAN, 7496), "refused_live_port")
        self.assertEqual(LA.port_refusal(PLAN, 4003), "refused_not_paper_port")
        self.assertIsNone(LA.port_refusal(PLAN, 4002))
        self.assertIsNone(LA.port_refusal(PLAN, 7497))

    def test_gate_prerequisites(self):
        ok, entries = LA.gate_prerequisites(PLAN)
        self.assertTrue(ok, entries)
        self.assertEqual(len(entries), 3)
        self.assertTrue(all(len(e["sha256"]) == 64 for e in entries))
        with tempfile.TemporaryDirectory() as d:
            ok, entries = LA.gate_prerequisites(PLAN, repo=Path(d))
            self.assertFalse(ok)
            self.assertFalse(any(e["ok"] for e in entries))
            # A prerequisite with another status is not enough.
            for p in PLAN["receipt"]["gate_receipt"]["prerequisites"]:
                target = Path(d) / p["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"status": "incomplete"}))
            record = Path(d) / PLAN["version_selection_record"]
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text("record")
            ok, entries = LA.gate_prerequisites(PLAN, repo=Path(d))
            self.assertFalse(ok)
            self.assertEqual([e["ok"] for e in entries], [False, False, True])

    def test_the_plan_preregisters_the_builders_corroboration_rule(self):
        for plan in (PLAN, POST):
            c = plan["receipt"]["gate_receipt"]["corroboration"]
            self.assertIs(c["required"], True)
            self.assertEqual(set(c["sources"]), {"gateway_api_message_log", "ibkr_activity_statement"})
            self.assertEqual(c["sources"]["gateway_api_message_log"]["corroborates"], list(LA.RUN_CLAIMS))
            # Revision 3 (second review of PR #280): the API message log is required and every run
            # claim must be corroborated; the activity statement is optional and additional.
            self.assertEqual((c["sources"]["gateway_api_message_log"]["required"],
                              c["sources"]["ibkr_activity_statement"]["required"]), (True, False))
            self.assertEqual(c["required_sources"], ["gateway_api_message_log"])
            self.assertEqual((c["run_claims"], c["every_run_claim_corroborated"]), (list(LA.RUN_CLAIMS), True))
            self.assertEqual(c["max_future_skew_seconds"], 300)
        # The required sources alone cover every run claim, so a gate receipt never leaves one
        # on the in-process observer.
        covered = {claim for s in LA.REQUIRED_CORROBORATION_SOURCES for claim in LA.CORROBORATION_SOURCES[s]["corroborates"]}
        self.assertEqual(covered, set(LA.RUN_CLAIMS))
        self.assertLess(set(LA.CORROBORATION_SOURCES["ibkr_activity_statement"]["corroborates"]), set(LA.RUN_CLAIMS))
        weakened = [
            ("required", lambda g: g.update(required=False)),
            ("kind", lambda g: g.update(record_kind="other")),
            ("check dropped", lambda g: g["sources"]["gateway_api_message_log"]["checks"].remove("p1_p2_never_sent")),
            ("claim added", lambda g: g["sources"]["ibkr_activity_statement"]["corroborates"].append("r1_r2_cancelled_at_ib")),
            ("source added", lambda g: g["sources"].update(runner_log={"required": False, "checks": [],
                                                                        "corroborates": ["no_fill"]})),
            ("sources not an object", lambda g: g.update(sources=[])),
            ("block removed", lambda g: g.clear()),
            ("api log made optional", lambda g: g["sources"]["gateway_api_message_log"].update(required=False)),
            ("statement made required", lambda g: g["sources"]["ibkr_activity_statement"].update(required=True)),
            ("statement named as the required source", lambda g: g.update(required_sources=["ibkr_activity_statement"])),
            ("required sources removed", lambda g: g.pop("required_sources")),
            ("claims may rest on the observer", lambda g: g.update(every_run_claim_corroborated=False)),
            ("claim dropped from run_claims", lambda g: g["run_claims"].remove("p1_p2_never_reached_ib")),
            ("future skew widened", lambda g: g.update(max_future_skew_seconds=86400)),
        ]
        for label, change in weakened:
            with self.subTest(label=label):
                plan = copy.deepcopy(PLAN)
                change(plan["receipt"]["gate_receipt"]["corroboration"])
                self.assertNotEqual(LA.validate_plan(plan), [])


# --------------------------------------------------------------------------- kill switch and lock


class KillSwitchLatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = isolate_control(self, Path(self.tmp.name))
        self.ks = LA.KillSwitch()

    def test_engage_is_private_durable_and_audited(self):
        self.assertFalse(self.ks.engaged())
        rec = self.ks.engage("NTA-X", "case B2")
        self.assertTrue(self.ks.engaged())
        self.assertEqual(self.ks.path, self.dir / "kill-switch.json")
        self.assertEqual(stat.S_IMODE(self.ks.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.dir.stat().st_mode), 0o700)
        self.assertEqual(json.loads(self.ks.path.read_text())["run_prefix"], "NTA-X")
        self.assertEqual(self.ks.status()["record"]["reason"], rec["reason"])
        self.assertEqual([json.loads(line)["event"] for line in self.ks.audit_path.read_text().splitlines()], ["engaged"])
        self.assertEqual(stat.S_IMODE(self.ks.audit_path.stat().st_mode), 0o600)

    def test_the_latch_path_is_frozen_per_account(self):
        # Regression (review of PR #280): the latch and the lock lived under --state-dir, so a
        # run with another state directory did not see an engaged latch. The directory now
        # comes from the password database, not from $HOME, XDG_STATE_HOME or any option.
        expected = (Path(pwd.getpwuid(os.getuid()).pw_dir) / ".local" / "state" / "native-agent-stack"
                    / "ibkr-local-acceptance")
        with mock.patch.dict(os.environ, {"HOME": str(self.dir / "fake-home"), "XDG_STATE_HOME": str(self.dir / "xdg")}):
            self.assertEqual(LA._frozen_control_dir(), expected)
        self.assertEqual(IMPORTED_CONTROL_DIR, expected)
        self.assertTrue(expected.is_absolute())
        # Every state directory resolves to the same latch.
        for other in (self.dir / "a", self.dir / "b", LA.DEFAULT_STATE_DIR):
            self.assertEqual(LA.KillSwitch(legacy_dirs=(other,)).path, self.ks.path)

    def test_a_latch_an_earlier_revision_wrote_under_a_state_dir_still_counts(self):
        legacy = Path(self.tmp.name) / "old-state"
        legacy.mkdir()
        (legacy / "kill-switch.json").write_text(json.dumps({"engaged": True, "run_prefix": "NTA-OLD"}))
        ks = LA.KillSwitch(legacy_dirs=(legacy,))
        self.assertFalse(self.ks.engaged())  # the frozen latch itself is not engaged
        self.assertEqual((ks.engaged(), ks.status()["location"], ks.status()["record"]["run_prefix"]),
                         (True, "legacy_state_dir", "NTA-OLD"))
        res = ks.clear(True, "reviewed run NTA-OLD")
        self.assertEqual((res["status"], res["legacy_latches_cleared"]), ("cleared", 1))
        self.assertFalse((legacy / "kill-switch.json").exists())
        self.assertFalse(ks.engaged())
        # The audit line sits at the frozen path even though only a legacy latch was engaged.
        self.assertEqual(json.loads(self.ks.audit_path.read_text().splitlines()[-1])["prior"]["run_prefix"], "NTA-OLD")

    def test_a_corrupt_latch_still_reads_as_engaged(self):
        self.dir.mkdir(parents=True)
        self.ks.path.write_text("{not json")
        self.assertTrue(self.ks.engaged())
        self.assertEqual(self.ks.status(), {"engaged": True, "location": "frozen", "readable": False})

    def test_clear_needs_confirm_and_reason_and_audits_first(self):
        self.ks.engage("NTA-X", "case B2")
        self.assertEqual(self.ks.clear(False, "x")["status"], "refused_not_confirmed")
        self.assertEqual(self.ks.clear(True, " ")["status"], "refused_reason_required")
        self.assertTrue(self.ks.engaged())
        res = self.ks.clear(True, "reviewed run NTA-X")
        self.assertEqual(res["status"], "cleared")
        self.assertFalse(self.ks.engaged())
        events = [json.loads(line) for line in self.ks.audit_path.read_text().splitlines()]
        self.assertEqual([e["event"] for e in events], ["engaged", "cleared"])
        self.assertEqual(events[1]["prior"]["run_prefix"], "NTA-X")
        self.assertEqual(self.ks.clear(True, "again")["status"], "not_engaged")

    def test_cli_status_and_clear(self):
        self.ks.engage("NTA-X", "case B2")
        other = str(Path(self.tmp.name) / "another-state-dir")
        with mock.patch("builtins.print") as out:
            self.assertEqual(LA.main(["kill-switch", "status"]), 0)
            self.assertIs(json.loads(out.call_args[0][0])["engaged"], True)
            # Another state directory sees the same latch.
            self.assertEqual(LA.main(["kill-switch", "status", "--state-dir", other]), 0)
            self.assertIs(json.loads(out.call_args[0][0])["engaged"], True)
            self.assertEqual(LA.main(["kill-switch", "clear", "--state-dir", other]), 3)
            self.assertTrue(self.ks.engaged())
            self.assertEqual(LA.main(["kill-switch", "clear", "--state-dir", other, "--confirm", "--reason", "reviewed"]), 0)
        self.assertFalse(self.ks.engaged())

    def test_lock_is_single_writer_and_private(self):
        first = LA.acquire_lock()
        self.assertIsNotNone(first)
        lock = self.dir / "run.lock"
        self.assertEqual((stat.S_IMODE(lock.stat().st_mode), stat.S_IMODE(self.dir.stat().st_mode)), (0o600, 0o700))
        self.assertIsNone(LA.acquire_lock())
        first.close()
        again = LA.acquire_lock()
        self.assertIsNotNone(again)
        again.close()


# --------------------------------------------------------------------------- observer


def _order(order_id, client_id, perm_id, ref, status="Submitted"):
    return SimpleNamespace(clientId=client_id, permId=perm_id, orderRef=ref, action="BUY", totalQuantity=Decimal(1),
                           lmtPrice=300.0, tif="DAY", orderId=order_id), SimpleNamespace(status=status, completedStatus="")


class FakeObserver(LA.ObserverState):
    """A fake official-ibapi client driving ObserverState's callbacks synchronously."""

    def __init__(self, accounts=FAKE_ACCOUNT, open_orders=(), positions=(), completed=(), executions=(),
                 refuse_326=False, connect_ok=True, answer_accounts=True):
        super().__init__()
        self.accounts, self._open, self._positions = accounts, list(open_orders), list(positions)
        self._completed, self._executions = list(completed), list(executions)
        self.refuse_326, self.connect_ok, self.answer_accounts = refuse_326, connect_ok, answer_accounts
        self.requests, self.cancelled, self.connected_as = [], [], None

    def connect(self, host, port, client_id):
        self.connected_as = client_id
        if not self.connect_ok:
            raise ConnectionRefusedError("refused")
        if self.refuse_326:
            self.error(-1, 0, 326, "Unable to connect as the client id is already in use.")
            return
        if self.answer_accounts:
            self.managedAccounts(self.accounts)
            self.nextValidId(1)

    def isConnected(self):
        return self.connect_ok and not self.refuse_326

    def run(self):
        pass

    def disconnect(self):
        self.requests.append("disconnect")

    def reqPositions(self):
        self.requests.append("positions")
        for sym, qty in self._positions:
            self.position(FAKE_ACCOUNT, SimpleNamespace(symbol=sym, secType="STK"), Decimal(qty), 1.0)
        self.positionEnd()

    def cancelPositions(self):
        pass

    def reqAllOpenOrders(self):
        self.requests.append("all_open")
        for oid, cid, perm, ref, status in self._open:
            order, state = _order(oid, cid, perm, ref, status)
            self.openOrder(oid, SimpleNamespace(symbol="SPY"), order, state)
        self.openOrderEnd()

    def reqOpenOrders(self):
        self.requests.append("own_open")
        self.reqAllOpenOrders()

    def reqCompletedOrders(self, api_only):
        self.requests.append("completed")
        for oid, cid, perm, ref, status in self._completed:
            order, state = _order(oid, cid, perm, ref, status)
            self.completedOrder(SimpleNamespace(symbol="SPY"), order, state)
        self.completedOrdersEnd()

    def reqExecutions(self, req_id, flt):
        self.requests.append(("executions", flt.clientId))
        for i, ref in enumerate(self._executions):
            self.execDetails(req_id, SimpleNamespace(symbol="SPY"),
                             SimpleNamespace(execId=f"e{i}", orderRef=ref, permId=1, clientId=93, side="BOT", shares=1))
        self.execDetailsEnd(req_id)

    def cancelOrder(self, order_id, order_cancel):
        self.cancelled.append(order_id)
        self.orderStatus(order_id, "Cancelled", 0, 1, 0.0, 0, 0, 0.0, 93, "", 0.0)


class FakeBroker:
    """Shared IB state behind fake official-ibapi clients: open orders as
    (order_id, client_id, perm_id, order_ref, status). A cancel removes the order only when sent
    by its own client id, as IB allows."""

    def __init__(self, orders, accounts=FAKE_ACCOUNT, own_listing_ok=True, all_listing_ok=True, failed_observations=0):
        self.orders, self.accounts = list(orders), accounts
        self.own_listing_ok, self.all_listing_ok = own_listing_ok, all_listing_ok
        self.failed_observations = failed_observations
        self.connections, self.cancels = [], []

    def client(self):
        return BrokerClient(self)


class BrokerClient(FakeObserver):
    def __init__(self, broker):
        super().__init__(accounts=broker.accounts)
        self.broker = broker

    def connect(self, host, port, client_id):
        self.broker.connections.append(client_id)
        if client_id == 98 and self.broker.failed_observations > 0:
            self.broker.failed_observations -= 1
            self.connect_ok = False
        super().connect(host, port, client_id)

    def _list(self, only_own):
        for oid, cid, perm, ref, status in self.broker.orders:
            if not only_own or cid == self.connected_as:
                order, state = _order(oid, cid, perm, ref, status)
                self.openOrder(oid, SimpleNamespace(symbol="SPY"), order, state)

    def reqAllOpenOrders(self):
        self.requests.append("all_open")
        self._list(False)
        if self.broker.all_listing_ok:
            self.openOrderEnd()

    def reqOpenOrders(self):
        self.requests.append("own_open")
        self._list(True)
        if self.broker.own_listing_ok:
            self.openOrderEnd()

    def cancelOrder(self, order_id, order_cancel):
        self.broker.cancels.append((self.connected_as, order_id))
        self.broker.orders = [o for o in self.broker.orders if not (o[0] == order_id and o[1] == self.connected_as)]
        self.orderStatus(order_id, "Cancelled", 0, 1, 0.0, 0, 0, 0.0, self.connected_as, "", 0.0)


class Observer(unittest.TestCase):
    def test_observe_reads_every_requested_list_on_the_check_id(self):
        fake = FakeObserver(open_orders=[(12, 93, 555, "NTA-X-R2:12", "Submitted")], positions=[("SPY", 0)],
                            completed=[(11, 93, 554, "NTA-X-R1:11", "Cancelled")], executions=["other:1"])
        with mock.patch.object(LA, "_exec_filter", lambda plan: SimpleNamespace(clientId=93)):
            snap = LA.observe(PLAN, 4002, include=("positions", "open_orders", "completed", "executions"),
                              client_factory=lambda: fake)
        self.assertEqual(snap["status"], "passed")
        self.assertEqual(fake.connected_as, 98)
        obs = snap["observed"]
        self.assertEqual(obs["positions"], [])  # a zero position is not a position
        self.assertEqual(obs["open_orders"][0]["perm_id"], 555)
        self.assertEqual(obs["completed_orders"][0]["status"], "Cancelled")
        self.assertEqual(len(obs["executions"]), 1)
        self.assertIn(("executions", 93), fake.requests)
        self.assertNotIn(FAKE_ACCOUNT, json.dumps(snap))

    def test_observe_refuses_ports_and_non_paper_accounts(self):
        for port in (4001, 7496, 4003):
            with self.subTest(port=port):
                self.assertTrue(LA.observe(PLAN, port, client_factory=lambda: self.fail("connected"))["status"]
                                .startswith("refused_"))
        fake = FakeObserver(accounts="U1234567")
        snap = LA.observe(PLAN, 4002, include=("positions", "open_orders"), client_factory=lambda: fake)
        self.assertEqual(snap["status"], "refused_not_paper_account")
        self.assertEqual(fake.requests, ["disconnect"])  # no request after a non-paper account
        fake = FakeObserver(accounts="DU1111111,DU2222222")
        self.assertEqual(LA.observe(PLAN, 4002, client_factory=lambda: fake)["status"], "refused_account_scope")
        self.assertEqual(LA.observe(PLAN, 4002, client_factory=lambda: FakeObserver(connect_ok=False),
                                    deadline_s=0.1)["status"], "not_connected")

    def test_non_paper_latch_survives_a_later_paper_callback(self):
        s = LA.ObserverState()
        s.managedAccounts("U1234567")
        s.managedAccounts("DU1234567")
        self.assertFalse(s.r["paper_accounts"])

    def test_contender_outcomes(self):
        self.assertEqual(LA.contender_probe(PLAN, 4002, client_factory=lambda: FakeObserver(refuse_326=True),
                                            wait_s=0.2)["outcome"], "refused_326")
        free = FakeObserver()
        res = LA.contender_probe(PLAN, 4002, client_factory=lambda: free, wait_s=0.2)
        self.assertEqual((res["outcome"], free.connected_as), ("connected", 93))
        self.assertEqual(free.requests, ["disconnect"])  # sends nothing
        self.assertEqual(LA.contender_probe(PLAN, 4002, client_factory=lambda: FakeObserver(accounts="U1"),
                                            wait_s=0.2)["outcome"], "refused_not_paper_account")
        self.assertEqual(LA.contender_probe(PLAN, 4002, client_factory=lambda: FakeObserver(connect_ok=False),
                                            wait_s=0.2)["outcome"], "not_connected")
        self.assertEqual(LA.contender_probe(PLAN, 7496)["outcome"], "refused_live_port")

    def _cleanup(self, broker):
        plan = copy.deepcopy(PLAN)
        plan["timeouts"]["check_seconds"] = 0.2  # an incomplete fake listing never answers
        with mock.patch.object(LA, "_order_cancel", lambda: object()), mock.patch.object(LA, "IBAPI_LISTING_SECONDS", 0.2):
            return LA.ibapi_cancel_run_orders(plan, 4002, "NTA-X", client_factory=broker.client, sleep_fn=lambda s: None)

    def test_ibapi_cleanup_cancels_only_this_runs_orders_on_their_own_client_id(self):
        broker = FakeBroker([(12, 93, 555, "NTA-X-R2:12", "Submitted"), (13, 93, 556, "NTA-OTHER-R2:13", "Submitted"),
                             (14, 5, 557, "manual:14", "Submitted")])
        res = self._cleanup(broker)
        self.assertEqual(res["status"], "cancelled")
        self.assertEqual(broker.cancels, [(93, 12)])
        self.assertEqual(broker.connections, [98, 93, 98])  # observe, cancel as the holder, observe again

    def test_ibapi_cleanup_follows_the_adapters_fallback_id(self):
        broker = FakeBroker([(20, 94, 600, "NTA-X-R1:20", "Submitted")])
        self.assertEqual(self._cleanup(broker)["status"], "cancelled")
        self.assertEqual(broker.cancels, [(94, 20)])

    def test_ibapi_cleanup_never_touches_ids_outside_the_band(self):
        broker = FakeBroker([(30, 5, 700, "NTA-X-R2:30", "Submitted")])
        res = self._cleanup(broker)
        self.assertEqual((res["status"], broker.cancels), ("cancel_unconfirmed", []))
        self.assertEqual(res["attempts"][0]["outside_band"], [5])

    def test_ibapi_cleanup_is_never_clean_on_an_incomplete_listing(self):
        broker = FakeBroker([(12, 93, 555, "NTA-X-R2:12", "Submitted")], own_listing_ok=False)
        res = self._cleanup(broker)
        self.assertEqual((res["status"], broker.cancels), ("cancel_unconfirmed", []))
        self.assertTrue(any("listing incomplete" in n for n in res["notes"]))
        broker = FakeBroker([(12, 93, 555, "NTA-X-R2:12", "Submitted")], all_listing_ok=False)
        res = self._cleanup(broker)
        self.assertEqual((res["status"], broker.cancels), ("cancel_unconfirmed", []))

    def test_a_failed_observation_does_not_use_up_a_cancel_round(self):
        broker = FakeBroker([(12, 93, 555, "NTA-X-R2:12", "Submitted")], failed_observations=2)
        res = self._cleanup(broker)
        self.assertEqual((res["status"], broker.cancels), ("cancelled", [(93, 12)]))
        self.assertEqual([a["status"] for a in res["attempts"]][:2], ["observer_not_connected"] * 2)

    def test_cleanup_takes_the_observer_by_keyword(self):
        seen = []

        def observe_fn(plan, port, *, include):
            seen.append(include)
            return {"status": "passed", "observed": {"open_orders": []}}

        res = LA.ibapi_cancel_run_orders(PLAN, 4002, "NTA-X", observe_fn=observe_fn, sleep_fn=lambda s: None)
        self.assertEqual((res["status"], seen), ("none_open", [("open_orders",)]))

    def test_ibapi_cleanup_none_open_and_refusals(self):
        broker = FakeBroker([(14, 5, 557, "manual:14", "Submitted")])
        self.assertEqual(self._cleanup(broker)["status"], "none_open")
        self.assertEqual(broker.connections, [98])
        self.assertEqual(self._cleanup(FakeBroker([], accounts="U1234567"))["status"], "refused_not_paper_account")
        self.assertEqual(LA.ibapi_cancel_run_orders(PLAN, 4001, "NTA-X")["status"], "refused_live_port")

    def test_error_text_is_redacted(self):
        s = LA.ObserverState()
        s.error(1, 0, 201, "Order rejected for DU1234567 at 10.0.0.2 [1234.56 USD]")
        text = json.dumps(s.r["errors"])
        self.assertNotIn("DU1234567", text)
        self.assertNotIn("10.0.0.2", text)
        self.assertNotIn("1234.56", text)


# --------------------------------------------------------------------------- verdicts


def _snap(open_orders=(), positions=(), completed=(), executions=(), status="passed"):
    def entry(oid, cid, perm, ref, st):
        return {"order_id": oid, "client_id": cid, "perm_id": perm, "order_ref": ref, "status": st}

    return {"status": status, "observed": {"open_orders": [entry(*o) for o in open_orders],
                                           "positions": [{"symbol": s, "quantity": q} for s, q in positions],
                                           "completed_orders": [entry(*o) for o in completed],
                                           "executions": [{"order_ref": r} for r in executions]}}


R1, R2, P1, P2 = "NTA-X-R1", "NTA-X-R2", "NTA-X-P1", "NTA-X-P2"
IDS = {"R1": R1, "R2": R2, "P1": P1, "P2": P2}
UP = {"present": True, "client_id": 93, "configured_client_id": 93, "fetch_all_open_orders": False}


class Verdicts(unittest.TestCase):
    def test_ownership(self):
        probe = {"contender": {"outcome": "refused_326"}, "observer": _snap([(11, 93, 554, R1 + ":11", "Submitted")])}
        node = {"adapter": UP, "r1_open": True, "r1_venue_order_id": "PERM-554"}
        self.assertEqual(LA.ownership_verdict(PLAN, probe, node, R1)["reasons"], [])
        self.assertTrue(LA.ownership_verdict(PLAN, probe, {**node, "r1_venue_order_id": "11"}, R1)["passed"])
        bad = [
            ({**probe, "contender": {"outcome": "connected"}}, node, "contender_connected"),
            ({**probe, "observer": _snap([(11, 7, 554, R1 + ":11", "Submitted")])}, node, "r1_client_id_mismatch"),
            ({**probe, "observer": _snap([(11, 93, 554, R1 + ":12", "Submitted")])}, node, "r1_order_ref_suffix_mismatch"),
            ({**probe, "observer": _snap([])}, node, "r1_not_listed_once"),
            (probe, {**node, "r1_venue_order_id": "PERM-999"}, "r1_venue_order_id_mismatch"),
            (probe, {**node, "adapter": {**UP, "client_id": 94}}, "adapter_client_id_changed"),
            (probe, {**node, "adapter": {**UP, "fetch_all_open_orders": True}}, "adapter_client_id_fallback"),
            (probe, {**node, "r1_open": False}, "r1_not_open_in_node"),
            ({"error": "boom"}, node, "probe_error"),
        ]
        for p, n, reason in bad:
            with self.subTest(reason=reason):
                v = LA.ownership_verdict(PLAN, p, n, R1)
                self.assertFalse(v["passed"])
                self.assertIn(reason, v["reasons"])

    def test_still_open_after_reconnect(self):
        snap = _snap([(11, 93, 554, R1 + ":11", "Submitted")])
        self.assertTrue(LA.still_open_verdict(PLAN, snap, R1, {"perm_id": 554, "order_id": 11})["passed"])
        self.assertIn("perm_id_changed", LA.still_open_verdict(PLAN, snap, R1, {"perm_id": 1, "order_id": 11})["reasons"])
        gone = _snap([], completed=[(11, 93, 554, R1 + ":11", "Cancelled")])
        self.assertIn("order_not_listed_once", LA.still_open_verdict(PLAN, gone, R1, {"perm_id": 554})["reasons"])

    def test_adoption_after_restart(self):
        expected = {"client_order_id": R2, "venue_order_id": "PERM-555", "price": "300.00", "quantity": "1"}
        view = {"client_order_id": R2, "strategy_id": "S-001", "status": "ACCEPTED", "venue_order_id": "PERM-555",
                "side": "BUY", "quantity": "1", "price": "300.00", "time_in_force": "DAY"}
        self.assertEqual(LA.adoption_verdict(expected, [view], "S-001")["reasons"], [])
        self.assertTrue(LA.adoption_verdict(expected, [{**view, "status": "SUBMITTED"}], "S-001")["passed"])
        # Accepted under the raw orderId before IB assigned a permId; the after-A observer supplies PERM-555.
        raw = {**expected, "venue_order_id": "12", "venue_order_ids": ["12", "PERM-555"]}
        self.assertTrue(LA.adoption_verdict(raw, [view], "S-001")["passed"])
        self.assertFalse(LA.adoption_verdict({**expected, "venue_order_id": "12"}, [view], "S-001")["passed"])
        for change, reason in [({"strategy_id": "EXTERNAL"}, "r2_not_claimed_by_strategy"),
                               ({"status": "CANCELED"}, "r2_not_working"),
                               ({"venue_order_id": "PERM-1"}, "r2_venue_order_id_changed"),
                               ({"price": "301.00"}, "r2_price_changed"),
                               ({"quantity": "2"}, "r2_quantity_changed"),
                               ({"side": "SELL"}, "r2_side_or_tif_changed")]:
            with self.subTest(reason=reason):
                self.assertIn(reason, LA.adoption_verdict(expected, [{**view, **change}], "S-001")["reasons"])
        self.assertIn("not_exactly_one_run_order",
                      LA.adoption_verdict(expected, [view, {**view, "client_order_id": P1}], "S-001")["reasons"])
        self.assertIn("r2_not_in_cache", LA.adoption_verdict(expected, [], "S-001")["reasons"])

    def test_checkpoints(self):
        carry = {"R2": {"client_order_id": R2, "venue_order_id": "PERM-555"}}
        ok_a = _snap([(12, 93, 555, R2 + ":12", "Submitted")])
        self.assertTrue(LA.after_a_verdict(PLAN, ok_a, "NTA-X", carry)["passed"])
        for snap, reason in [(_snap([(12, 93, 555, R2 + ":12", "Submitted"), (1, 0, 9, "manual", "Submitted")]),
                              "foreign_open_orders"),
                             (_snap([(12, 93, 555, R2 + ":12", "Submitted")], positions=[("SPY", "1")]), "positions_present"),
                             (_snap([]), "r2_not_the_only_open_order_of_the_run"),
                             (_snap([(12, 93, 999, R2 + ":12", "Submitted")]), "r2_venue_order_id_mismatch"),
                             (_snap(status="not_connected"), "observer_not_connected")]:
            with self.subTest(reason=reason):
                self.assertIn(reason, LA.after_a_verdict(PLAN, snap, "NTA-X", carry)["reasons"])
        done = [(11, 93, 554, R1 + ":11", "Cancelled"), (12, 93, 555, R2 + ":12", "Cancelled")]
        b = LA.after_b_verdict(PLAN, _snap(completed=done), "NTA-X", IDS)
        self.assertTrue(b["passed"] and b["r1_r2_listed_cancelled"])
        # An empty or partial completed-orders list proves nothing about P1: it fails.
        for completed in ([], done[:1]):
            with self.subTest(completed=len(completed)):
                v = LA.after_b_verdict(PLAN, _snap(completed=completed), "NTA-X", IDS)
                self.assertIn("completed_orders_do_not_show_r1_r2_cancelled", v["reasons"])
                self.assertIn("completed_orders_do_not_show_r1_r2_cancelled",
                              LA.final_verdict(PLAN, _snap(completed=completed), "NTA-X", IDS)["reasons"])
        self.assertIn("p1_reached_ib",
                      LA.after_b_verdict(PLAN, _snap(completed=done + [(13, 93, 556, P1 + ":13", "Cancelled")]),
                                         "NTA-X", IDS)["reasons"])
        final = LA.final_verdict(PLAN, _snap(completed=done), "NTA-X", IDS)
        self.assertTrue(final["passed"] and final["flat"])
        self.assertIn("executions_of_the_run",
                      LA.final_verdict(PLAN, _snap(completed=done, executions=[R1 + ":11"]), "NTA-X", IDS)["reasons"])
        # Before any probe was attempted (a run stopped in phase A) nothing depends on the list.
        early = LA.final_verdict(PLAN, _snap(completed=done[:1]), "NTA-X", IDS, probes=())
        self.assertTrue(early["passed"] and early["flat"])
        not_flat = LA.final_verdict(PLAN, _snap([(12, 93, 555, R2 + ":12", "Submitted")]), "NTA-X", IDS)
        self.assertFalse(not_flat["flat"])
        self.assertFalse(LA.final_verdict(PLAN, _snap(status="not_connected"), "NTA-X", IDS)["flat"])

    def test_run_and_phase_status(self):
        passed = [{"result": {"status": "passed"}}] * 3
        cps = {"after_A": {"passed": True}, "after_B": {"passed": True}}
        final = {"passed": True, "flat": True}
        self.assertEqual(LA.run_status(passed, cps, final), "passed")
        self.assertEqual(LA.run_status(passed, cps, {"passed": False, "flat": False}), "cleanup_required")
        self.assertEqual(LA.run_status(passed[:1], {"after_A": {"passed": False}}, final), "failed")
        self.assertEqual(LA.run_status([{"result": None}], {}, final), "incomplete")
        self.assertEqual(LA.run_status(passed, {"after_A": {"passed": True}}, final), "incomplete")
        ctx = LA.PhaseContext(PLAN, "NTA-X", "C")
        self.assertEqual(LA.phase_status(ctx), "incomplete")
        ctx.cases["C1"]["outcome"] = "passed"
        self.assertEqual(LA.phase_status(ctx), "incomplete")  # needs the phase_complete finish
        ctx.node["finish_reason"] = "phase_complete"
        self.assertEqual(LA.phase_status(ctx), "passed")
        self.assertEqual(LA.phase_status(ctx, error=True), "incomplete")
        ctx.fills.append({"order": "R1"})
        self.assertEqual(LA.phase_status(ctx), "cleanup_required")

    def test_ref_and_venue_helpers(self):
        self.assertEqual(LA.order_ref_client_id("NTA-X-R1:123"), "NTA-X-R1")
        self.assertEqual(LA.order_ref_suffix("NTA-X-R1:123"), "123")
        self.assertEqual(LA.perm_from_venue("PERM-42"), 42)
        self.assertIsNone(LA.perm_from_venue("42"))
        self.assertEqual(LA.venue_ids_for({"perm_id": 42, "order_id": 7}), {"PERM-42", "7"})
        self.assertTrue(LA.is_run_order({"order_ref": "NTA-X-R1:1"}, "NTA-X"))
        self.assertFalse(LA.is_run_order({"order_ref": "NTA-XY-R1:1"}, "NTA-X"))


class PhaseContextAndStopControl(unittest.TestCase):
    def test_budget_spans_phases_and_carry_keep(self):
        ctx = LA.PhaseContext(PLAN, "NTA-X", "B", orders_created=2)
        self.assertEqual(ctx.budget.remaining, 2)
        ctx.budget.reserve("P1", 1, Decimal("300"))
        ctx.budget.reserve("x", 1, Decimal("300"))
        with self.assertRaises(LA.BudgetError):
            ctx.budget.reserve("y", 1, Decimal("300"))
        a = LA.PhaseContext(PLAN, "NTA-X", "A")
        self.assertEqual(a.carry_keep(), set())
        a.carry_out = {"R2": {}}
        self.assertEqual(a.carry_keep(), {"NTA-X-R2"})
        self.assertEqual(ctx.suffix_for("NTA-X-P1"), "P1")
        self.assertIsNone(ctx.suffix_for("NTA-X-P9"))

    def test_shared_stop_control_marks_an_unstarted_phase_finished(self):
        class Node:
            stopped = 0

            def stop(self):
                Node.stopped += 1

        ctx = LA.PhaseContext(PLAN, "NTA-X", "A")
        control = LA.PO.NodeStopControl(ctx, PLAN, node=Node(), loop=None)
        control.on_signal(signal.SIGTERM)
        self.assertTrue(ctx.finished)
        self.assertEqual(ctx.cases["A1"]["outcome"], "incomplete")
        self.assertEqual(Node.stopped, 1)


# --------------------------------------------------------------------------- run: refusals


def _check_result(status, positions=0, open_orders=0, liquid=TODAY_HOURS, trading=TODAY_TRADING):
    return {"client": "ibapi", "client_id": 98, "port": 4002, "status": status,
            "observed": {"account_count": 1, "paper_accounts": status != "refused_not_paper_account",
                         "server_time_epoch": 1, "positions": positions, "open_orders": open_orders,
                         "server_minus_local_s": 0.2, "errors": [], "info": []},
            "liquid_hours": liquid, "trading_hours": trading, "time_zone_id": "US/Eastern"}


class Scenario:
    """Fakes for check/contender/observer/phase/cancel that behave like a clean paper account."""

    def __init__(self, tmp, check="passed", contender="connected", phase_status=None, after_a=None, final_open=(),
                 interrupt_in=None, liquid=TODAY_HOURS, completed=("R1", "R2")):
        self.tmp, self.check, self.contender, self.liquid = tmp, check, contender, liquid
        self.completed = completed
        self.phase_status = phase_status or {}
        self.after_a, self.final_open, self.interrupt_in = after_a, final_open, interrupt_in
        self.calls, self.manifests, self.envs, self.prefix, self.cancels = [], [], [], None, []
        self.receipt_during_phase = {}

    def check_fn(self, plan, port, *, with_session, deadline_s=None):
        self.calls.append("check")
        return _check_result(self.check, liquid=self.liquid), (FAKE_ACCOUNT if self.check == "passed" else None)

    def contender_fn(self, plan, port):
        self.calls.append("contender")
        return {"client_id": 93, "outcome": self.contender}

    def phase_fn(self, phase, manifest_path, env, deadline_s, signals):
        m = json.loads(Path(manifest_path).read_text())
        self.calls.append(f"phase-{phase}")
        self.manifests.append(m)
        self.envs.append(env)
        self.prefix = m["run_prefix"]
        self.receipt_during_phase[phase] = json.loads(Path(self.receipt_path).read_text())
        if self.interrupt_in == phase:
            signals.received.append("SIGINT")
        status = self.phase_status.get(phase, "passed")
        if status is None:  # the phase process died before writing a result
            return {"exit_code": -9, "terminated": True, "killed": True}
        carry = {}
        if phase == "A":
            carry = {"R1": {"client_order_id": f"{self.prefix}-R1", "venue_order_id": "PERM-554", "perm_id": 554},
                     "R2": {"client_order_id": f"{self.prefix}-R2", "venue_order_id": "PERM-555", "perm_id": 555,
                            "price": "300.00", "quantity": "1", "side": "BUY", "time_in_force": "DAY"}}
        created = {"A": 2, "B": 3, "C": 4}[phase]
        cases = [{"id": c, "outcome": "passed" if status == "passed" else "failed"} for c in LA.PHASE_CASES[phase]]
        result = {"schema_version": 1, "kind": LA.PHASE_KIND, "phase": phase, "run_prefix": self.prefix,
                  "status": status, "provisional": False,
                  "summary": {"cases": cases, "orders_created": created, "carry_out": carry or None}}
        Path(m["result_path"]).write_text(json.dumps(result))
        return {"exit_code": 0 if status == "passed" else 1, "terminated": False, "killed": False}

    def observe_fn(self, plan, port, include):
        self.calls.append("observe:" + ",".join(include))
        p = self.prefix
        done = [(11 + i, 93, 554 + i, f"{p}-{s}:{11 + i}", "Cancelled") for i, s in enumerate(self.completed)]
        if include == ("positions", "open_orders"):
            return self.after_a or _snap([(12, 93, 555, f"{p}-R2:12", "Submitted")])
        return _snap(list(self.final_open), completed=done)

    def cancel_fn(self, plan, port, prefix):
        self.cancels.append(prefix)
        return {"status": "none_open"}


class QuietSignals(LA.ParentSignals):
    def install(self):
        pass


class _RunHarness(unittest.TestCase):
    """A temporary repository root, the frozen control directory redirected into it, and 'run'
    driven through the Scenario fakes. No test methods of its own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.receipt = self.d / "steps.json"
        self.gate = self.d / "gate.json"
        self.state = self.d / "state"
        self.control = isolate_control(self, self.d)
        # The temporary directory stands in for the repository root: the prerequisites are read
        # from it, and a steps receipt inside it counts as in the repository.
        for rel in [p["path"] for p in PLAN["receipt"]["gate_receipt"]["prerequisites"]] + [PLAN["version_selection_record"]]:
            target = self.d / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / rel).read_bytes())

    def run_cli(self, sc=None, extra=(), enable=True, port=4002, now=WEDNESDAY_10AM, versions=PINNED, plan=None,
                signals=None, repo_root="tmp", state=None):
        sc = sc or Scenario(self.d)
        sc.receipt_path = self.receipt
        argv = ["run", "--port", str(port), "--receipt", str(self.receipt), "--state-dir", str(state or self.state)]
        argv += ["--enable-paper-orders"] if enable else []
        argv += ["--plan", plan] if plan else []
        argv += list(extra)
        with mock.patch("builtins.print"):
            code = LA.main(argv, check_fn=sc.check_fn, contender_fn=sc.contender_fn, observe_fn=sc.observe_fn,
                           cancel_fn=sc.cancel_fn, phase_fn=sc.phase_fn, now_fn=lambda: now,
                           versions_fn=lambda: dict(versions), sleep_fn=lambda s: None,
                           signals=signals or QuietSignals(), gate_path=str(self.gate),
                           repo_root=self.d if repo_root == "tmp" else repo_root)
        receipt = json.loads(self.receipt.read_text()) if self.receipt.exists() else None
        return code, receipt, sc


class RunCommand(_RunHarness):
    def test_refuses_without_enable_flag_and_connects_nothing(self):
        code, r, sc = self.run_cli(enable=False)
        self.assertEqual((code, r["status"]), (3, "refused_orders_not_enabled"))
        self.assertEqual(sc.calls, [])

    def test_live_and_other_ports_refused_before_connecting(self):
        for port, status in ((4001, "refused_live_port"), (7496, "refused_live_port"), (4003, "refused_not_paper_port")):
            with self.subTest(port=port):
                code, r, sc = self.run_cli(port=port)
                self.assertEqual((code, r["status"], sc.calls), (3, status, []))

    def test_gate_receipt_path_is_refused(self):
        with mock.patch("builtins.print"):
            code = LA.main(["run", "--enable-paper-orders", "--receipt", str(LA.GATE_RECEIPT), "--state-dir", str(self.state)])
        self.assertEqual(code, 3)
        self.assertFalse(LA.GATE_RECEIPT.exists())

    def test_static_and_state_refusals(self):
        code, r, _ = self.run_cli(versions={"nautilus_trader": "2.0.0rc5", "ibapi": None})
        self.assertEqual(r["status"], "refused_unpinned_runtime")
        LA.KillSwitch().engage("NTA-OLD", "left engaged")
        code, r, sc = self.run_cli()
        self.assertEqual((r["status"], sc.calls), ("refused_kill_switch_engaged", []))
        LA.KillSwitch().clear(True, "test")
        lock = LA.acquire_lock()
        try:
            code, r, sc = self.run_cli()
            self.assertEqual((r["status"], sc.calls), ("refused_concurrent_run", []))
        finally:
            lock.close()
        missing = [{"path": "blueprints/x.json", "ok": False, "reason": "unreadable: FileNotFoundError"}]
        with mock.patch.object(LA, "gate_prerequisites", lambda plan, repo=None: (False, missing)):
            code, r, sc = self.run_cli()
        self.assertEqual((r["status"], sc.calls, r["prerequisites"]), ("refused_gate_prerequisites_missing", [], missing))

    def test_account_state_and_session_refusals(self):
        cases = [(Scenario(self.d, check="refused_not_paper_account"), WEDNESDAY_10AM, "refused_not_paper_account"),
                 (Scenario(self.d, check="refused_account_scope"), WEDNESDAY_10AM, "refused_account_scope"),
                 (Scenario(self.d, check="refused_existing_state"), WEDNESDAY_10AM, "refused_existing_state"),
                 (Scenario(self.d, check="not_connected"), WEDNESDAY_10AM, "not_connected"),
                 (Scenario(self.d, contender="refused_326"), WEDNESDAY_10AM, "refused_client_id_in_use"),
                 (Scenario(self.d, contender="refused_not_paper_account"), WEDNESDAY_10AM, "refused_not_paper_account"),
                 (Scenario(self.d, liquid="20260924:0930-20260924:1600"), WEDNESDAY_10AM, "refused_liquid_hours_unavailable"),
                 (Scenario(self.d), ny(2026, 9, 23, 15, 40), "refused_outside_rth"),
                 (Scenario(self.d), ny(2026, 9, 26, 10, 0), "refused_outside_rth")]
        for sc, now, status in cases:
            with self.subTest(status=status, now=now):
                code, r, sc = self.run_cli(sc=sc, now=now)
                self.assertEqual(r["status"], status)
                self.assertFalse(any(c.startswith("phase-") for c in sc.calls))
                self.assertNotIn(FAKE_ACCOUNT, self.receipt.read_text())

    def test_an_engaged_latch_refuses_a_run_with_any_state_dir(self):
        # Regression (review of PR #280): B2 of a run with one state directory engages the latch;
        # a later run or preflight with another state directory must still refuse.
        LA.KillSwitch(legacy_dirs=(self.state,)).engage("NTA-EARLIER", "acceptance case B2")
        for other in (self.state, self.d / "another-state", self.d / "third-state"):
            with self.subTest(state=other.name):
                code, r, sc = self.run_cli(state=other)
                self.assertEqual((code, r["status"], sc.calls), (3, "refused_kill_switch_engaged", []))
                self.assertEqual(r["kill_switch"]["record"]["run_prefix"], "NTA-EARLIER")
        def no_connection(*args, **kwargs):
            raise AssertionError("preflight connected despite an engaged latch")

        with mock.patch("builtins.print") as out:
            code = LA.main(["preflight", "--state-dir", str(self.d / "fourth-state")], versions_fn=lambda: dict(PINNED),
                           check_fn=no_connection, contender_fn=no_connection)
        self.assertEqual((code, json.loads(out.call_args[0][0])["status"]), (3, "refused_kill_switch_engaged"))
        self.assertFalse(self.gate.exists())

    def test_a_held_lock_refuses_a_run_with_another_state_dir(self):
        lock = LA.acquire_lock()
        try:
            code, r, sc = self.run_cli(state=self.d / "another-state")
            self.assertEqual((code, r["status"], sc.calls), (3, "refused_concurrent_run", []))
        finally:
            lock.close()

    def test_a_latch_engaged_while_the_lock_was_taken_is_seen(self):
        real = LA.acquire_lock

        def lock_after_a_run_ended():
            # A run that ends in this instant leaves its latch engaged and releases the lock.
            LA.KillSwitch().engage("NTA-JUST-ENDED", "acceptance case B2")
            return real()

        with mock.patch.object(LA, "acquire_lock", lock_after_a_run_ended):
            code, r, sc = self.run_cli()
        self.assertEqual((code, r["status"], sc.calls), (3, "refused_kill_switch_engaged", []))
        again = LA.acquire_lock()  # the refusal released the lock
        self.assertIsNotNone(again)
        again.close()

    def test_a_legacy_latch_under_the_state_dir_refuses(self):
        self.state.mkdir(parents=True)
        (self.state / "kill-switch.json").write_text("{}")  # where an earlier revision kept it
        code, r, sc = self.run_cli()
        self.assertEqual((r["status"], r["kill_switch"]["location"], sc.calls),
                         ("refused_kill_switch_engaged", "legacy_state_dir", []))

    def test_a_passed_run_writes_no_gate_receipt_and_awaits_corroboration(self):
        # Regression (review of PR #280): the run's own result and its in-process observer are
        # not independent confirmation, so the run never writes the gate receipt.
        code, r, sc = self.run_cli()
        self.assertEqual((code, r["status"]), (0, "passed"), r)
        self.assertEqual([c for c in sc.calls if c.startswith("phase-")], ["phase-A", "phase-B", "phase-C"])
        self.assertEqual(sc.cancels, [])  # nothing of the run was left working
        self.assertTrue(r["checkpoints"]["after_A"]["passed"] and r["checkpoints"]["after_B"]["passed"])
        self.assertTrue(r["final"]["passed"])
        self.assertEqual(r["gate_receipt"], {"eligible": True, "written": False, "awaiting": "independent_corroboration",
                                             "path": "gate.json", "builder": "local_acceptance.py gate-receipt"})
        self.assertFalse(self.gate.exists())
        self.assertLessEqual(datetime.fromisoformat(r["generated_at"]), datetime.fromisoformat(r["finished_at"]))
        text = self.receipt.read_text()
        self.assertIsNone(RAW_ACCOUNT.search(text))
        self.assertNotIn(str(Path.home()), text)

    def test_phase_manifests_carry_the_handshake_and_state(self):
        _, r, sc = self.run_cli()
        a, b, c = sc.manifests
        token = sc.envs[0][LA.TOKEN_ENV]
        self.assertEqual({m["token_sha256"] for m in sc.manifests}, {LA.sha256_text(token)})
        self.assertEqual(sc.envs[0][LA.ACCOUNT_ENV], FAKE_ACCOUNT)
        self.assertEqual((a["carry"], a["orders_created"]), ({}, 0))
        self.assertEqual((b["carry"]["R2"]["venue_order_id"], b["orders_created"]), ("PERM-555", 2))
        self.assertEqual(b["carry"]["R2"]["venue_order_ids"], ["12", "PERM-555"])  # IB's forms from the after-A observer
        self.assertEqual((c["carry"]["R2"]["price"], c["orders_created"]), ("300.00", 3))
        self.assertEqual({m["plan_sha256"] for m in sc.manifests}, {LA.PO.sha256_file(SOURCE / "local-acceptance-plan.json")})
        for m in sc.manifests:
            self.assertNotIn(FAKE_ACCOUNT, json.dumps(m))
        # A cleanup_required receipt stands while every phase runs.
        for phase, rec in sc.receipt_during_phase.items():
            self.assertEqual((rec["status"], rec["provisional"]), ("cleanup_required", True), phase)

    def test_failed_phase_a_stops_and_cleans_up_the_runs_own_orders(self):
        code, r, sc = self.run_cli(sc=Scenario(self.d, phase_status={"A": "failed"}))
        self.assertEqual([c for c in sc.calls if c.startswith("phase-")], ["phase-A"])
        self.assertEqual(sc.cancels, [sc.prefix])
        self.assertEqual((code, r["status"]), (1, "failed"))
        self.assertFalse(self.gate.exists())

    def test_after_a_checkpoint_failure_stops_before_the_restart(self):
        code, r, sc = self.run_cli(sc=Scenario(self.d, after_a=_snap([])))
        self.assertEqual([c for c in sc.calls if c.startswith("phase-")], ["phase-A"])
        self.assertIn("r2_not_the_only_open_order_of_the_run", r["checkpoints"]["after_A"]["reasons"])
        self.assertEqual((r["status"], len(sc.cancels)), ("failed", 1))
        self.assertFalse(self.gate.exists())

    def test_dead_phase_process_is_incomplete_and_cleaned_up(self):
        code, r, sc = self.run_cli(sc=Scenario(self.d, phase_status={"B": None}))
        self.assertEqual((r["status"], len(sc.cancels)), ("incomplete", 1))
        self.assertTrue(r["phases"][1]["process"]["killed"])

    def test_not_flat_at_the_end_is_cleanup_required(self):
        sc = Scenario(self.d, phase_status={"C": "failed"}, final_open=[(12, 93, 555, "X-R2:12", "Submitted")])
        code, r, sc = self.run_cli(sc=sc)
        self.assertEqual((code, r["status"]), (3, "cleanup_required"))
        self.assertFalse(self.gate.exists())

    def test_signal_during_a_phase_stops_further_phases(self):
        signals = QuietSignals()
        code, r, sc = self.run_cli(sc=Scenario(self.d, interrupt_in="A"), signals=signals)
        self.assertEqual([c for c in sc.calls if c.startswith("phase-")], ["phase-A"])
        self.assertEqual(r["status"], "incomplete")
        self.assertEqual(sc.cancels, [sc.prefix])
        self.assertEqual(r["interrupted"], ["SIGINT"])

    def test_prerequisites_changing_during_the_run_withhold_the_gate_receipt(self):
        real = LA.gate_prerequisites
        calls = []

        def flaky(plan, repo=None):
            calls.append(1)
            ok, entries = real(plan, repo)
            return (ok if len(calls) == 1 else False), entries

        with mock.patch.object(LA, "gate_prerequisites", flaky):
            code, r, _ = self.run_cli()
        self.assertEqual(r["status"], "passed")
        self.assertFalse(r["gate_receipt"]["eligible"])
        self.assertFalse(self.gate.exists())

    def test_a_steps_receipt_outside_the_repository_is_refused_before_connecting(self):
        code, r, sc = self.run_cli(repo_root=None)  # the temporary receipt is outside the real repository
        self.assertEqual((code, r["status"], sc.calls), (3, "refused_receipt_outside_repository", []))
        self.assertFalse(self.gate.exists())

    def test_a_run_stopped_before_any_probe_is_incomplete_not_failed(self):
        code, r, sc = self.run_cli(sc=Scenario(self.d, phase_status={"A": "incomplete"}, completed=("R1",)))
        self.assertEqual((code, r["status"]), (1, "incomplete"))
        self.assertEqual(r["final"]["probes_checked"], [])
        self.assertTrue(r["final"]["passed"])

    def test_a_plan_edited_during_the_run_stops_before_the_next_phase(self):
        real = LA.PO.sha256_file
        changed = {"now": False}

        def sha(path):
            if changed["now"] and Path(path).name == "local-acceptance-plan.json":
                return "0" * 64
            return real(path)

        sc = Scenario(self.d)
        original = sc.phase_fn

        def phase_fn(phase, *args):
            out = original(phase, *args)
            changed["now"] = True
            return out

        sc.phase_fn = phase_fn
        with mock.patch.object(LA.PO, "sha256_file", sha):
            code, r, sc = self.run_cli(sc=sc)
        self.assertEqual([c for c in sc.calls if c.startswith("phase-")], ["phase-A"])
        self.assertTrue(r["plan_changed_during_run"])
        self.assertEqual((r["status"], sc.cancels), ("incomplete", [sc.prefix]))

    def test_a_plan_unreadable_during_the_run_still_cleans_up(self):
        real = LA.PO.sha256_file
        gone = {"now": False}

        def sha(path):
            if gone["now"] and Path(path).name == "local-acceptance-plan.json":
                raise FileNotFoundError(path)
            return real(path)

        sc = Scenario(self.d)
        original = sc.phase_fn

        def phase_fn(phase, *args):
            out = original(phase, *args)
            gone["now"] = True
            return out

        sc.phase_fn = phase_fn
        with mock.patch.object(LA.PO, "sha256_file", sha):
            code, r, sc = self.run_cli(sc=sc)
        self.assertTrue(r["plan_changed_during_run"])
        self.assertEqual((r["status"], sc.cancels), ("incomplete", [sc.prefix]))

    def test_after_hours_plan_runs_after_16(self):
        code, r, sc = self.run_cli(plan="local-acceptance-plan-post.json", now=ny(2026, 9, 23, 17, 0))
        self.assertEqual(r["status"], "passed", r)
        code, r, sc = self.run_cli(plan="local-acceptance-plan-post.json", now=WEDNESDAY_10AM)
        self.assertEqual(r["status"], "refused_outside_rth")

    def test_preflight_is_read_only(self):
        sc = Scenario(self.d)
        with mock.patch("builtins.print") as out:
            code = LA.main(["preflight", "--state-dir", str(self.state)], check_fn=sc.check_fn,
                           contender_fn=sc.contender_fn, now_fn=lambda: WEDNESDAY_10AM, versions_fn=lambda: dict(PINNED))
        printed = json.loads(out.call_args[0][0])
        self.assertEqual((code, printed["status"]), (0, "ready"))
        self.assertEqual(sc.calls, ["check", "contender"])
        self.assertNotIn(FAKE_ACCOUNT, out.call_args[0][0])
        again = LA.acquire_lock()  # preflight released the run lock on its way out
        self.assertIsNotNone(again)
        again.close()
        with mock.patch("builtins.print") as out:
            code = LA.main(["preflight", "--port", "4001", "--state-dir", str(self.state)], versions_fn=lambda: dict(PINNED))
        self.assertEqual((code, json.loads(out.call_args[0][0])["status"]), (3, "refused_live_port"))

    def _preflight(self, state, check_fn, contender_fn):
        with mock.patch("builtins.print") as out:
            code = LA.main(["preflight", "--state-dir", str(state)], check_fn=check_fn, contender_fn=contender_fn,
                           now_fn=lambda: WEDNESDAY_10AM, versions_fn=lambda: dict(PINNED))
        return code, json.loads(out.call_args[0][0])

    def test_preflight_and_a_run_never_overlap(self):
        # Regression (second review of PR #280): preflight did not look at the run lock, so a
        # preflight during a run connected client 98 and a contender on 93, the run's own ids.
        def no_connection(*args, **kwargs):
            raise AssertionError("preflight connected while a run held the lock")

        lock = LA.acquire_lock()  # a run in progress, with any state directory
        try:
            code, out = self._preflight(self.d / "another-state", no_connection, no_connection)
            self.assertEqual((code, out["status"]), (3, "refused_concurrent_run"))
        finally:
            lock.close()
        # Discriminating control: the same preflight with the lock free connects and is ready,
        # and while it connects it holds the lock, so a run started then is refused.
        sc = Scenario(self.d)
        seen = []

        def check_fn(plan, port, *, with_session, deadline_s=None):
            probe = LA.acquire_lock()
            seen.append(probe is None)
            if probe is not None:
                probe.close()
            return sc.check_fn(plan, port, with_session=with_session, deadline_s=deadline_s)

        code, out = self._preflight(self.d / "another-state", check_fn, sc.contender_fn)
        self.assertEqual((code, out["status"], seen, sc.calls), (0, "ready", [True], ["check", "contender"]))
        code, r, run_sc = self.run_cli()  # the lock is free again once preflight returned
        self.assertEqual((code, r["status"]), (0, "passed"))

    def test_preflight_rereads_the_latch_under_the_lock(self):
        real = LA.acquire_lock

        def lock_after_a_run_ended():
            LA.KillSwitch().engage("NTA-JUST-ENDED", "acceptance case B2")
            return real()

        def no_connection(*args, **kwargs):
            raise AssertionError("preflight connected despite an engaged latch")

        with mock.patch.object(LA, "acquire_lock", lock_after_a_run_ended):
            code, out = self._preflight(self.state, no_connection, no_connection)
        self.assertEqual((code, out["status"]), (3, "refused_kill_switch_engaged"))
        again = LA.acquire_lock()  # the refusal released the lock
        self.assertIsNotNone(again)
        again.close()


# --------------------------------------------------------------------------- gate-receipt (the builder)


class GateReceiptBuilder(_RunHarness):
    """The builder writes the gate receipt only from a passed steps receipt plus a checked
    corroboration record from IB's own records (review of PR #280). Synthetic records only."""

    def setUp(self):
        super().setUp()
        code, self.steps, _ = self.run_cli()
        self.assertEqual((code, self.steps["status"]), (0, "passed"))
        self.steps_sha = hashlib.sha256(self.receipt.read_bytes()).hexdigest()

    def record(self, kind="gateway_api_message_log", **over) -> dict:
        finished = datetime.fromisoformat(self.steps["finished_at"])
        retrieved = finished + (timedelta(minutes=5) if kind == "gateway_api_message_log" else timedelta(days=1))
        rec = {"schema_version": 1, "kind": LA.CORROBORATION_KIND, "run_prefix": self.steps["run_prefix"],
               "steps_receipt": {"path": "steps.json", "sha256": self.steps_sha},
               "source": {"kind": kind, "raw_sha256": ["ab" * 32], "retrieved_at": retrieved.isoformat()},
               "observer": {"separate_session": True, "started_the_run": False,
                            "method": "read the private raw file for the run prefix; no ibapi, no local_acceptance.py",
                            "observed_at": (retrieved + timedelta(minutes=5)).isoformat()},
               "checks": dict.fromkeys(LA.CORROBORATION_SOURCES.get(kind, {}).get("checks", ()), True)}
        if kind == "gateway_api_message_log":
            rec["source"]["client_ids"] = [93, 98]
        else:
            rec["source"]["statement_date"] = LA.run_trade_date(PLAN, self.steps)
        for dotted, value in over.items():
            *parents, leaf = dotted.split("__")
            node = rec
            for key in parents:
                node = node[key]
            if value is DELETE:
                node.pop(leaf, None)
            else:
                node[leaf] = value
        return rec

    def write(self, rec, name="corroboration.json") -> Path:
        path = self.d / name
        path.write_text(json.dumps(rec, indent=2) + "\n")
        return path

    def build(self, *corroborations, steps=None, repo_root="tmp", now=None):
        """now is the builder's clock; by default two days after the run finished, later than
        every time a default record reports."""
        now = now or datetime.fromisoformat(self.steps["finished_at"]) + timedelta(days=2)
        argv = ["gate-receipt", "--steps-receipt", str(steps or self.receipt)]
        for path in corroborations:
            argv += ["--corroboration", str(path)]
        with mock.patch("builtins.print") as out:
            code = LA.main(argv, gate_path=str(self.gate), repo_root=self.d if repo_root == "tmp" else repo_root,
                           now_fn=lambda: now)
        return code, json.loads(out.call_args[0][0])

    def test_only_a_passing_corroboration_record_writes_the_gate_receipt(self):
        # Discriminating control first: the same record with one check false writes nothing.
        failing = self.write(self.record(checks__p1_p2_never_sent=False))
        code, out = self.build(failing)
        self.assertEqual((code, out["status"]), (3, "refused_corroboration_invalid"))
        self.assertIn("checks.p1_p2_never_sent must be true", out["reasons"])
        self.assertFalse(self.gate.exists())
        path = self.write(self.record())
        code, out = self.build(path)
        self.assertEqual((code, out["status"]), (0, "passed"), out)
        gate = json.loads(self.gate.read_text())
        for key, value in {"schema_version": 1, "kind": "native_ibkr_local_acceptance", "status": "passed",
                           "broker": "ibkr"}.items():
            self.assertEqual(gate[key], value)
        self.assertEqual(gate["steps_receipt"], {"path": "steps.json", "sha256": self.steps_sha})
        record = gate["corroboration"]["records"][0]
        self.assertEqual((record["path"], record["sha256"], record["source_kind"]),
                         ("corroboration.json", hashlib.sha256(path.read_bytes()).hexdigest(), "gateway_api_message_log"))
        self.assertEqual(gate["corroboration"]["claims_corroborated"], list(LA.RUN_CLAIMS))
        self.assertEqual(gate["corroboration"]["claims_on_the_in_process_observer_only"], [])
        self.assertEqual(len(gate["prerequisites"]), 3)
        self.assertEqual((gate["run_prefix"], gate["run_finished_at"]), (self.steps["run_prefix"], self.steps["finished_at"]))
        text = self.gate.read_text()
        self.assertIsNone(RAW_ACCOUNT.search(text))
        self.assertNotIn(str(Path.home()), text)
        # A standing gate receipt is never replaced by the builder.
        code, out = self.build(path)
        self.assertEqual((code, out["status"]), (3, "refused_gate_receipt_exists"))

    def test_an_activity_statement_alone_is_refused_as_uncorroborated(self):
        # Regression (second review of PR #280): a statement-only record wrote status passed,
        # although no fill and a flat account are expected from orders resting at half the bid
        # whether or not the kill switch worked. It now writes nothing.
        statement = self.write(self.record("ibkr_activity_statement"), "statement.json")
        code, out = self.build(statement)
        self.assertEqual((code, out["status"]), (3, "refused_claims_uncorroborated"), out)
        self.assertEqual(out["missing_sources"], ["gateway_api_message_log"])
        self.assertEqual(out["claims_on_the_in_process_observer_only"],
                         ["no_duplicate_submission", "r1_r2_cancelled_at_ib", "p1_p2_never_reached_ib"])
        self.assertFalse(self.gate.exists())
        # Discriminating control: the same statement with the API message log record passes.
        code, out = self.build(self.write(self.record(), "api.json"), statement)
        self.assertEqual((code, out["status"], out["claims_on_the_in_process_observer_only"]), (0, "passed", []), out)

    def test_both_sources_together_and_one_record_per_source(self):
        api = self.write(self.record(), "api.json")
        statement = self.write(self.record("ibkr_activity_statement"), "statement.json")
        code, out = self.build(api, self.write(self.record(), "api-again.json"))
        self.assertEqual((code, out["status"]), (3, "refused_one_record_per_source"))
        self.assertFalse(self.gate.exists())
        code, out = self.build(api, statement)
        self.assertEqual((code, out["status"]), (0, "passed"), out)
        gate = json.loads(self.gate.read_text())
        self.assertEqual([r["source_kind"] for r in gate["corroboration"]["records"]],
                         ["gateway_api_message_log", "ibkr_activity_statement"])
        self.assertEqual((gate["corroboration"]["claims_corroborated"],
                          gate["corroboration"]["claims_on_the_in_process_observer_only"]), (list(LA.RUN_CLAIMS), []))

    def test_record_times_later_than_the_builders_clock_are_refused(self):
        # Regression (second review of PR #280): retrieved_at and observed_at had no upper bound,
        # so a record dated 30 days after the run, or a statement "retrieved tomorrow" on the run's
        # own date, built a gate receipt.
        finished = datetime.fromisoformat(self.steps["finished_at"])
        month = self.write(self.record(source__retrieved_at=(finished + timedelta(days=30)).isoformat(),
                                       observer__observed_at=(finished + timedelta(days=30, minutes=5)).isoformat()),
                           "api-month.json")
        code, out = self.build(month, now=finished + timedelta(days=2))
        self.assertEqual((code, out["status"]), (3, "refused_corroboration_invalid"))
        self.assertTrue(any("source.retrieved_at must not be later than the builder's clock" in r for r in out["reasons"]))
        self.assertTrue(any("observer.observed_at must not be later than the builder's clock" in r for r in out["reasons"]))
        self.assertFalse(self.gate.exists())
        observed_ahead = self.write(self.record(observer__observed_at=(finished + timedelta(hours=3)).isoformat()),
                                    "api-observed-ahead.json")
        code, out = self.build(observed_ahead, now=finished + timedelta(hours=1))
        self.assertEqual(out["reasons"], ["observer.observed_at must not be later than the builder's clock plus 300 s"])
        # A same-day statement dated tomorrow: the builder runs on the run's own date.
        api = self.write(self.record(), "api.json")  # retrieved 5 min and observed 10 min after the run
        tomorrow = self.write(self.record("ibkr_activity_statement"), "statement-tomorrow.json")
        code, out = self.build(api, tomorrow, now=finished + timedelta(hours=1))
        self.assertEqual((code, out["status"], out["path"]), (3, "refused_corroboration_invalid", "statement-tomorrow.json"))
        self.assertTrue(any("source.retrieved_at must not be later than the builder's clock" in r for r in out["reasons"]))
        self.assertFalse(self.gate.exists())
        # Within the skew still counts: clocks of two sessions may differ a little.
        code, out = self.build(api, now=finished + timedelta(minutes=10) - timedelta(seconds=LA.MAX_FUTURE_SKEW_SECONDS))
        self.assertEqual((code, out["status"]), (0, "passed"), out)
        self.gate.unlink()
        # Discriminating control: the same records pass once the builder's clock is past them.
        code, out = self.build(month, now=finished + timedelta(days=31))
        self.assertEqual((code, out["status"]), (0, "passed"), out)
        self.gate.unlink()
        code, out = self.build(api, tomorrow, now=finished + timedelta(days=2))
        self.assertEqual((code, out["status"]), (0, "passed"), out)

    def test_invalid_records_are_refused(self):
        finished = datetime.fromisoformat(self.steps["finished_at"])
        cases = [
            ({"run_prefix": "NTA-0101-000000-abcdef"}, "run_prefix"),
            ({"kind": "other"}, "kind must be"),
            ({"steps_receipt__sha256": "0" * 64}, "steps_receipt must name"),
            ({"steps_receipt__path": "other.json"}, "steps_receipt must name"),
            ({"source__kind": "runner_log"}, "source.kind must be one of"),
            ({"source__raw_sha256": []}, "source.raw_sha256"),
            ({"source__raw_sha256": ["not-a-hash"]}, "source.raw_sha256"),
            ({"source__retrieved_at": (finished - timedelta(seconds=1)).isoformat()}, "after the run finished"),
            ({"source__retrieved_at": finished.replace(tzinfo=None).isoformat()}, "UTC offset"),
            ({"observer__observed_at": finished.isoformat()}, "after source.retrieved_at"),
            ({"observer__separate_session": False}, "separate_session"),
            ({"observer__started_the_run": True}, "started_the_run"),
            ({"observer__started_the_run": DELETE}, "started_the_run"),
            ({"observer__method": " "}, "observer.method"),
            ({"source__client_ids": [93]}, "client_ids"),
            ({"source__client_ids": [93, 98, {"id": 1}]}, "client_ids"),
            ({"source": "not an object"}, "source.kind must be one of"),
            ({"checks__flat_at_end": "true"}, "checks.flat_at_end must be true"),
            ({"checks__r1_r2_each_sent_once": DELETE}, "checks.r1_r2_each_sent_once must be true"),
        ]
        for over, needle in cases:
            with self.subTest(over=over):
                code, out = self.build(self.write(self.record(**over)))
                self.assertEqual((code, out["status"]), (3, "refused_corroboration_invalid"))
                self.assertTrue(any(needle in reason for reason in out["reasons"]), out["reasons"])
                self.assertFalse(self.gate.exists())

    def test_an_activity_statement_must_be_the_next_day_statement_of_the_run_date(self):
        finished = datetime.fromisoformat(self.steps["finished_at"])
        same_day = self.record("ibkr_activity_statement", source__retrieved_at=(finished + timedelta(seconds=1)).isoformat(),
                               observer__observed_at=(finished + timedelta(seconds=2)).isoformat())
        trade_date = LA.run_trade_date(PLAN, self.steps)
        ny_same_day = datetime.fromisoformat(same_day["source"]["retrieved_at"]).astimezone(NY).date().isoformat()
        if ny_same_day == trade_date:  # a run finishing just before New York midnight has no same-day case
            code, out = self.build(self.write(same_day))
            self.assertEqual(out["status"], "refused_corroboration_invalid")
            self.assertTrue(any("later New York date" in r for r in out["reasons"]), out["reasons"])
        wrong_date = self.record("ibkr_activity_statement", source__statement_date="2026-01-02")
        code, out = self.build(self.write(wrong_date))
        self.assertTrue(any("statement_date" in r for r in out["reasons"]), out)
        self.assertFalse(self.gate.exists())

    def test_private_content_in_a_record_is_refused(self):
        for text in (FAKE_ACCOUNT, "/home/example/private/api.93.Fri.log"):
            with self.subTest(text=text):
                code, out = self.build(self.write(self.record(notes=f"read {text}")))
                self.assertEqual((code, out["status"]), (3, "refused_corroboration_private_content"))
                self.assertNotIn(text, json.dumps(out))
        self.assertFalse(self.gate.exists())

    def test_steps_receipts_that_cannot_back_the_gate_are_refused(self):
        path = self.write(self.record())
        tampered = dict(self.steps, final={**self.steps["final"], "flat": False})  # status still says passed
        self.receipt.write_text(json.dumps(tampered))
        code, out = self.build(path)
        self.assertEqual((code, out["status"]), (3, "refused_steps_receipt_not_passed"))
        self.assertIn("run_not_passed", out["reasons"])
        for change, reason in (({"status": "failed"}, "status_failed"), ({"provisional": True}, "status_passed"),
                               ({"gate_receipt": {"eligible": False}}, "gate_receipt_not_eligible"),
                               ({"finished_at": None}, "finished_at_missing"), ({"plan": "plan.json"}, "plan"),
                               ({"kind": "other"}, "not_a_steps_receipt")):
            with self.subTest(change=change):
                self.receipt.write_text(json.dumps({**self.steps, **change}))
                code, out = self.build(path)
                self.assertEqual(out["status"], "refused_steps_receipt_not_passed")
                self.assertIn(reason, out["reasons"])
        self.assertFalse(self.gate.exists())

    def test_path_plan_and_prerequisite_refusals(self):
        path = self.write(self.record())
        self.assertEqual(self.build(path, steps=path)[1]["status"], "refused_same_file_twice")
        self.assertEqual(self.build(self.gate)[1]["status"], "refused_gate_receipt_path")
        self.assertEqual(self.build(LA.GATE_RECEIPT)[1]["status"], "refused_gate_receipt_path")
        self.assertEqual(self.build(self.d / "missing.json")[1]["status"], "refused_corroboration_unreadable")
        # Outside the repository: the temporary files are outside the real repository root.
        self.assertEqual(self.build(path, repo_root=None)[1]["status"], "refused_outside_repository")
        with mock.patch("builtins.print"), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            LA.main(["gate-receipt", "--steps-receipt", str(self.receipt)])  # no corroboration named
        real = LA.PO.sha256_file

        def sha(p):
            return "0" * 64 if Path(p).name == "local-acceptance-plan.json" else real(p)

        with mock.patch.object(LA.PO, "sha256_file", sha):
            self.assertEqual(self.build(path)[1]["status"], "refused_plan_changed_since_run")
        (self.d / PLAN["receipt"]["gate_receipt"]["prerequisites"][0]["path"]).unlink()
        self.assertEqual(self.build(path)[1]["status"], "refused_gate_prerequisites_missing")
        self.assertFalse(self.gate.exists())

    def test_a_failed_write_is_reported_and_leaves_no_receipt(self):
        with mock.patch.object(LA, "write_json", side_effect=OSError("disk full")):
            code, out = self.build(self.write(self.record()))
        self.assertEqual((code, out["status"]), (3, "gate_receipt_write_failed"))
        self.assertFalse(self.gate.exists())

    def test_the_receipt_function_itself_needs_a_corroboration(self):
        with self.assertRaises(ValueError):
            LA.gate_receipt(PLAN, self.steps, self.receipt, [], [], self.d)
        statement_only = [{"source_kind": "ibkr_activity_statement", "corroborates": ["no_fill", "flat_at_end"]}]
        with self.assertRaises(ValueError):
            LA.gate_receipt(PLAN, self.steps, self.receipt, [], statement_only, self.d)
        self.assertEqual(LA.uncorroborated(statement_only),
                         (["gateway_api_message_log"], ["no_duplicate_submission", "r1_r2_cancelled_at_ib",
                                                        "p1_p2_never_reached_ib"]))
        api = [{"source_kind": "gateway_api_message_log", "corroborates": list(LA.RUN_CLAIMS)}]
        self.assertEqual(LA.uncorroborated(api), ([], []))
        self.assertEqual(LA.gate_receipt(PLAN, self.steps, self.receipt, [], api, self.d)["corroboration"]
                         ["claims_on_the_in_process_observer_only"], [])


DELETE = object()


# --------------------------------------------------------------------------- phase command (child)


class PhaseCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.token = "t" * 32
        self.state = self.d / "state"
        self.state.mkdir()
        isolate_control(self, self.d)

    def manifest(self, phase="A", **over):
        m = {"schema_version": 1, "run_prefix": "NTA-X", "phase": phase, "token_sha256": LA.sha256_text(self.token),
             "plan": "local-acceptance-plan.json", "plan_sha256": LA.PO.sha256_file(SOURCE / "local-acceptance-plan.json"),
             "port": 4002, "state_dir": str(self.state), "result_path": str(self.d / f"phase-{phase}.json"),
             "carry": {"R2": {"price": "300.00"}}, "orders_created": 0, "deadline_seconds": 360, "window_end": None,
             "server_minus_local_s": 0.0, "log_level": "WARNING"}
        m.update(over)
        path = self.d / f"manifest-{phase}.json"
        path.write_text(json.dumps(m))
        return path

    def run_phase(self, phase="A", env=None, node_fn=None, versions=PINNED, **over):
        env = {LA.TOKEN_ENV: self.token, LA.ACCOUNT_ENV: FAKE_ACCOUNT} if env is None else env
        path = self.manifest(phase, **over)
        with mock.patch.dict(os.environ, env, clear=False), mock.patch("builtins.print"):
            if env == {}:
                os.environ.pop(LA.TOKEN_ENV, None)
            code = LA.main(["phase", phase, "--manifest", str(path)], node_fn=node_fn or self.passing_node,
                           versions_fn=lambda: dict(versions))
        result_path = self.d / f"phase-{phase}.json"
        return code, (json.loads(result_path.read_text()) if result_path.exists() else None)

    def passing_node(self, plan, account, port, ctx, kill, *, abort_at, hard_stop_at, window_end, log_level):
        self.seen = {"account": account, "provisional": json.loads((self.d / f"phase-{ctx.phase}.json").read_text())}
        for c in ctx.cases.values():
            c["outcome"] = "passed"
        ctx.node["finish_reason"] = "phase_complete"

    def test_refused_unless_started_by_run(self):
        self.assertEqual(self.run_phase(env={})[0], 3)
        self.assertEqual(self.run_phase(env={LA.TOKEN_ENV: "wrong", LA.ACCOUNT_ENV: FAKE_ACCOUNT})[0], 3)
        path = self.manifest("A")
        with mock.patch.dict(os.environ, {LA.TOKEN_ENV: self.token}), mock.patch("builtins.print"):
            self.assertEqual(LA.main(["phase", "B", "--manifest", str(path)], node_fn=self.passing_node), 3)
        self.assertEqual(self.run_phase(plan_sha256="0" * 64)[0], 3)
        self.assertEqual(self.run_phase(port=4001)[0], 3)
        self.assertEqual(self.run_phase(versions={"nautilus_trader": "2.0.0rc5", "ibapi": None})[0], 3)
        self.assertEqual(self.run_phase(env={LA.TOKEN_ENV: self.token, LA.ACCOUNT_ENV: "U1234567"})[0], 3)
        self.assertFalse((self.d / "phase-A.json").exists())

    def test_kill_switch_state_must_match_the_phase(self):
        self.assertEqual(self.run_phase("C")[0], 3)  # C needs the latch engaged
        LA.KillSwitch().engage("NTA-X", "B2")  # the frozen latch, whatever the manifest's state_dir
        self.assertEqual(self.run_phase("A")[0], 3)  # A and B refuse an engaged latch
        self.assertEqual(self.run_phase("B")[0], 3)
        code, result = self.run_phase("C")
        self.assertEqual((code, result["status"]), (0, "passed"))
        code, result = self.run_phase("C", state_dir=str(self.d / "another-state"))
        self.assertEqual((code, result["status"]), (0, "passed"))

    def test_passed_phase_writes_a_private_result_after_a_provisional_one(self):
        code, result = self.run_phase("A")
        self.assertEqual((code, result["status"], result["provisional"]), (0, "passed", False))
        self.assertEqual(self.seen["account"], FAKE_ACCOUNT)
        self.assertEqual((self.seen["provisional"]["status"], self.seen["provisional"]["provisional"]),
                         ("cleanup_required", True))
        path = self.d / "phase-A.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertIsNone(RAW_ACCOUNT.search(path.read_text()))

    def test_node_exceptions_are_never_a_pass(self):
        def boom(*args, **kwargs):
            raise RuntimeError(f"node failed for {FAKE_ACCOUNT}")

        code, result = self.run_phase("A", node_fn=boom)
        self.assertEqual((code, result["status"]), (1, "incomplete"))
        self.assertIsNone(RAW_ACCOUNT.search(json.dumps(result)))

        def interrupted(plan, account, port, ctx, kill, **kwargs):
            for c in ctx.cases.values():
                c["outcome"] = "passed"
            ctx.node["finish_reason"] = "phase_complete"
            raise KeyboardInterrupt

        self.assertEqual(self.run_phase("A", node_fn=interrupted)[1]["status"], "incomplete")


# --------------------------------------------------------------------------- source safety


class SourceSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (SOURCE / "local_acceptance.py").read_text()
        cls.tree = ast.parse(cls.source)
        cls.parents = {}
        for node in ast.walk(cls.tree):
            for child in ast.iter_child_nodes(node):
                cls.parents[child] = node

    def _enclosing(self, node):
        while node in self.parents:
            node = self.parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return None

    def _calls(self, attr):
        return [n for n in ast.walk(self.tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attr]

    def test_single_resting_buy_builder(self):
        calls = [c for c in self._calls("limit") if isinstance(c.func.value, ast.Attribute)
                 and c.func.value.attr == "order_factory"]
        self.assertEqual([self._enclosing(c) for c in calls], ["_new_resting_order"])
        kwargs = {k.arg: ast.unparse(k.value) for k in calls[0].keywords}
        self.assertEqual((kwargs["order_side"], kwargs["time_in_force"]), ("OrderSide.BUY", "TimeInForce.DAY"))

    def test_order_affecting_call_sites(self):
        self.assertEqual([self._enclosing(c) for c in self._calls("submit_order")], ["_submit"])
        self.assertEqual([self._enclosing(c) for c in self._calls("cancel_order")], ["_send_cancel"])
        self.assertEqual([self._enclosing(c) for c in self._calls("cancelOrder")], ["_cancel_as"])
        callers = [self._enclosing(n) for n in ast.walk(self.tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_cancel_as"]
        self.assertEqual(callers, ["ibapi_cancel_run_orders"])
        halts = self._calls("set_trading_state")
        self.assertEqual(sorted(self._enclosing(c) for c in halts), ["engage_kill_switch", "run_phase_node"])
        self.assertTrue(all(ast.unparse(c.args[0]) == "TradingState.HALTED" for c in halts))

    def test_budget_reserved_before_the_order_exists(self):
        body = ast.unparse(next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == "_submit"))
        self.assertLess(body.index("kill_switch_engaged"), body.index("budget.reserve"))
        self.assertLess(body.index("budget.reserve"), body.index("_new_resting_order"))
        self.assertLess(body.index("_new_resting_order"), body.index("submit_order"))

    def test_forbidden_calls_absent(self):
        for attr in ("market", "close_position", "close_all_positions", "cancel_all_orders", "placeOrder",
                     "reqGlobalCancel", "modify_order", "reqAutoOpenOrders"):
            with self.subTest(attr=attr):
                self.assertEqual(self._calls(attr), [])
        self.assertNotIn("OrderSide.SELL", self.source)
        self.assertNotIn("TradingState.ACTIVE", self.source)

    def _named_calls(self, name):
        return [c for c in ast.walk(self.tree) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                and c.func.id == name]

    def test_only_the_builder_writes_the_gate_receipt(self):
        # Regression (review of PR #280): the run wrote the gate receipt from its own result.
        # Now one write site builds it, in the builder, after the corroboration checks.
        builds = self._named_calls("gate_receipt")
        self.assertEqual([self._enclosing(c) for c in builds], ["cmd_gate_receipt"])
        writes = [c for c in self._named_calls("write_json") if c.args and ast.unparse(c.args[0]) in ("gate", "gate_path")]
        self.assertEqual([(self._enclosing(c), ast.unparse(c.args[0])) for c in writes], [("cmd_gate_receipt", "gate")])
        body = ast.unparse(next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)
                                and n.name == "cmd_gate_receipt"))
        self.assertLess(body.index("corroboration_errors"), body.index("gate_receipt(plan"))
        self.assertLess(body.index("steps_receipt_errors"), body.index("gate_receipt(plan"))
        # Second review of PR #280: the claim-coverage refusal precedes the build.
        self.assertLess(body.index("refused_claims_uncorroborated"), body.index("gate_receipt(plan"))

    def test_the_builder_connects_to_nothing(self):
        node = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == "cmd_gate_receipt")
        called = {c.func.id if isinstance(c.func, ast.Name) else c.func.attr
                  for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, (ast.Name, ast.Attribute))}
        for name in ("observe", "observe_with_retry", "contender_probe", "_connect", "ibapi_cancel_run_orders",
                     "spawn_phase", "run_phase_node", "run_check", "cmd_run", "_run_phases", "engage"):
            self.assertNotIn(name, called)

    def test_the_latch_and_lock_ignore_the_state_dir(self):
        # Every KillSwitch the CLI builds takes its latch from CONTROL_DIR; state directories
        # enter only as legacy_dirs, and the lock takes no state directory at all.
        for call in self._named_calls("KillSwitch"):
            self.assertEqual([k.arg for k in call.keywords], ["legacy_dirs"], ast.unparse(call))
            self.assertEqual(call.args, [])
        # run and (second review of PR #280) preflight take the same frozen lock.
        self.assertEqual(sorted((self._enclosing(c), ast.unparse(c)) for c in self._named_calls("acquire_lock")),
                         [("cmd_preflight", "acquire_lock()"), ("cmd_run", "acquire_lock()")])
        preflight = ast.unparse(next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)
                                     and n.name == "cmd_preflight"))
        self.assertLess(preflight.index("acquire_lock()"), preflight.index("_checks_before_orders"))

    def test_no_heavy_imports_at_module_level(self):
        for node in self.tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
                self.assertFalse(any(n.startswith(("nautilus_trader", "ibapi")) for n in names), names)


# --------------------------------------------------------------------------- 1.231.0 backtest venue


def _nautilus_available():
    try:
        import nautilus_trader

        return nautilus_trader.__version__ == "1.231.0"
    except Exception:
        return False


class DoneProbe:
    def __init__(self, result):
        self._result = result

    def done(self):
        return True

    def result(self):
        return self._result


class FakeHooks:
    """Stand-ins for the IB adapter, the ibapi probes and the stop request. The kill switch
    uses the real latch and the backtest engine's real RiskEngine."""

    def __init__(self, engine, state_dir, down_polls=1, halt=True, records_disconnection=True):
        self.engine, self.kill = engine, LA.KillSwitch(control=state_dir)
        self.down_polls, self.halt, self.records = down_polls, halt, records_disconnection
        self.stops, self.injected, self.probes = [], 0, []

    def adapter_state(self):
        state = {"present": True, "client_id": 93, "configured_client_id": 93, "ready": True, "ib_connected": True,
                 "socket_connected": True, "fetch_all_open_orders": False, "client_id_collisions": 0,
                 "last_disconnection_ns": None}
        if self.injected and self.records:
            state["last_disconnection_ns"] = 2 ** 62  # after any backtest fault time
        if self.injected and self.down_polls > 0:
            self.down_polls -= 1
            state.update(ready=False, ib_connected=False, socket_connected=False)
        return state

    def inject_disconnect(self):
        self.injected += 1
        return {"kind": "fake"}

    def start_probe(self, kind, client_order_id):
        self.probes.append(kind)
        return DoneProbe({"kind": kind})

    def engage_kill_switch(self, reason):
        from nautilus_trader.model.enums import TradingState

        record = self.kill.engage("NTA-SIM", reason)
        if self.halt:
            self.engine.kernel.risk_engine.set_trading_state(TradingState.HALTED)
        return record

    def trading_state(self):
        from nautilus_trader.model.enums import trading_state_to_str

        return trading_state_to_str(self.engine.kernel.risk_engine.trading_state)

    def kill_switch_engaged(self):
        return self.kill.engaged()

    def request_stop(self, by):
        self.stops.append(by)


PASS = {"passed": True, "reasons": [], "perm_id": 1, "order_id": 1}


@unittest.skipUnless(_nautilus_available(), "needs nautilus_trader 1.231.0 (synthetic backtest venue)")
class NautilusBacktestFlow(unittest.TestCase):
    """Runs the phase strategy in a 1.231.0 BacktestEngine against a simulated ARCA venue. It checks
    the strategy's use of the Nautilus API, its case sequence and cleanup, and the real 1.231.0
    RiskEngine's HALTED denial; it is not IBKR (no reconnect, restart or reconciliation happens)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"

    def tearDown(self):
        self.tmp.cleanup()

    def _engine(self, quotes):
        from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
        from nautilus_trader.backtest.models import FixedFeeModel
        from nautilus_trader.config import LoggingConfig, RiskEngineConfig
        from nautilus_trader.model.currencies import USD
        from nautilus_trader.model.data import QuoteTick
        from nautilus_trader.model.enums import AccountType, OmsType
        from nautilus_trader.model.identifiers import Venue
        from nautilus_trader.model.objects import Money, Price, Quantity
        from nautilus_trader.test_kit.providers import TestInstrumentProvider

        eng = BacktestEngine(BacktestEngineConfig(
            trader_id="BACKTESTER-001", logging=LoggingConfig(bypass_logging=True),
            risk_engine=RiskEngineConfig(max_order_submit_rate=PLAN["bounds"]["max_order_submit_rate"])))
        eng.add_venue(venue=Venue("ARCA"), oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
                      base_currency=USD, starting_balances=[Money(100_000, USD)], fee_model=FixedFeeModel(Money(1, USD)))
        inst = TestInstrumentProvider.equity(symbol="SPY", venue="ARCA")
        eng.add_instrument(inst)
        t0 = 1_790_000_000_000_000_000
        eng.add_data([QuoteTick(inst.id, Price(bid, 2), Price(ask, 2), Quantity.from_int(100), Quantity.from_int(100),
                                t0 + i * 500_000_000, t0 + i * 500_000_000) for i, (bid, ask) in enumerate(quotes)])
        return eng

    def simulate(self, phase, *, quotes=None, carry=None, orders_created=0, strategy_cls=None, halted_before=False,
                 latch=False, hooks_kwargs=None):
        from nautilus_trader.config import StrategyConfig
        from nautilus_trader.model.enums import TradingState

        eng = self._engine(quotes or [(600.00, 600.02)] * 240)
        ctx = LA.PhaseContext(PLAN, "NTA-SIM", phase, carry=carry, orders_created=orders_created)
        hooks = FakeHooks(eng, self.state, **(hooks_kwargs or {}))
        if latch:
            hooks.kill.engage("NTA-SIM", "engaged in phase B")
        if halted_before:
            eng.kernel.risk_engine.set_trading_state(TradingState.HALTED)
        strategy = (strategy_cls or LA.build_strategy_class())(StrategyConfig(order_id_tag="001"), ctx, hooks)
        eng.add_strategy(strategy)
        try:
            eng.run()
            statuses = {o.client_order_id.value: o.status_string() for o in strategy.cache.orders()}
            reasons = {}
            for e in ctx.events:
                if e["type"] == "OrderDenied":
                    reasons[e["order"]] = e.get("reason")
        finally:
            eng.dispose()
        return ctx, hooks, statuses, reasons

    def test_phase_a_leaves_only_r2_working(self):
        with mock.patch.object(LA, "ownership_verdict", lambda *a: dict(PASS)), \
                mock.patch.object(LA, "still_open_verdict", lambda *a: dict(PASS)):
            ctx, hooks, statuses, _ = self.simulate("A")
        self.assertEqual({c: ctx.cases[c]["outcome"] for c in ctx.cases}, dict.fromkeys(("A1", "A2", "A3", "A4"), "passed"))
        self.assertEqual(hooks.stops, ["strategy:phase_complete"])
        self.assertEqual((hooks.injected, hooks.probes), (1, ["ownership", "still_open"]))
        self.assertEqual(statuses, {"NTA-SIM-R1": "CANCELED", "NTA-SIM-R2": "ACCEPTED"})
        self.assertEqual([r["order"] for r in ctx.cancel_requests], ["R1"])  # finish and on_stop keep R2
        self.assertEqual(ctx.budget.used, 2)
        r2 = ctx.carry_out["R2"]
        self.assertEqual((r2["client_order_id"], r2["price"], r2["quantity"]), ("NTA-SIM-R2", "300.00", "1"))
        self.assertEqual(ctx.orders["R1"]["limit_price"], "300.00")  # half the 600.00 bid
        self.assertEqual(LA.phase_status(ctx), "passed")

    def test_phase_a_ownership_failure_cancels_everything(self):
        with mock.patch.object(LA, "ownership_verdict", lambda *a: {"passed": False, "reasons": ["contender_connected"]}):
            ctx, hooks, statuses, _ = self.simulate("A")
        self.assertEqual(ctx.cases["A2"]["outcome"], "failed")
        self.assertEqual(statuses, {"NTA-SIM-R1": "CANCELED"})
        self.assertIsNone(ctx.carry_out)
        self.assertEqual(hooks.stops, ["strategy:cleanup_flat"])
        self.assertEqual(LA.phase_status(ctx), "failed")

    def test_reconnect_timeout_is_incomplete_and_cleans_up(self):
        with mock.patch.object(LA, "ownership_verdict", lambda *a: dict(PASS)):
            ctx, hooks, statuses, _ = self.simulate("A", hooks_kwargs={"down_polls": 10_000})
        self.assertEqual(ctx.cases["A3"]["outcome"], "incomplete")
        self.assertIn("A3_reconnect_timeout", ctx.cases["A3"]["reason"])
        self.assertEqual(statuses, {"NTA-SIM-R1": "CANCELED"})

    def test_a_reconnect_the_adapter_never_recorded_is_not_a_pass(self):
        with mock.patch.object(LA, "ownership_verdict", lambda *a: dict(PASS)), \
                mock.patch.object(LA, "still_open_verdict", lambda *a: dict(PASS)):
            ctx, hooks, statuses, _ = self.simulate("A", hooks_kwargs={"records_disconnection": False})
        self.assertEqual(ctx.cases["A3"]["outcome"], "incomplete")
        self.assertIn("A3_disconnect_not_recorded", ctx.cases["A3"]["reason"])
        self.assertEqual(statuses, {"NTA-SIM-R1": "CANCELED"})

    def test_an_unexpected_fill_is_cleanup_required_and_never_flattened(self):
        quotes = [(600.00, 600.02)] * 6 + [(290.00, 290.02)] * 200
        with mock.patch.object(LA, "ownership_verdict", lambda *a: dict(PASS)), \
                mock.patch.object(LA, "still_open_verdict", lambda *a: dict(PASS)):
            ctx, hooks, statuses, _ = self.simulate("A", quotes=quotes)
        self.assertEqual(statuses["NTA-SIM-R1"], "FILLED")
        self.assertTrue(ctx.fills)
        self.assertTrue(all(o["side"] == "BUY" for o in ctx.orders.values()))
        self.assertEqual(LA.phase_status(ctx), "cleanup_required")
        self.assertEqual(hooks.stops, ["strategy:cleanup_position_left"])

    def _phase_b_class(self):
        base = LA.build_strategy_class()

        class BWithSetup(base):
            """Test only: a backtest has no restart reconciliation, so R2 is placed here; B1's own
            adoption check then runs on the real cache order, and B2 runs unchanged."""

            def _start_B1(self):
                self._setup = True
                self._submit("R2", Decimal("300.00"))

            def _on_case_event(self, suffix, event, unconfirmed, reason):
                if getattr(self, "_setup", False) and suffix == "R2" and type(event).__name__ == "OrderAccepted":
                    self._setup = False
                    self._last_submit_ns = None  # a restarted node has submitted nothing yet
                    self.ctx.carry["R2"]["venue_order_id"] = event.venue_order_id.value
                    base._start_B1(self)
                    return
                super()._on_case_event(suffix, event, unconfirmed, reason)

        return BWithSetup

    def test_phase_b_kill_switch_denies_p1_through_the_risk_engine_and_cancels_r2(self):
        carry = {"R2": {"client_order_id": "NTA-SIM-R2", "venue_order_id": None, "price": "300.00", "quantity": "1"}}
        ctx, hooks, statuses, reasons = self.simulate("B", carry=carry, orders_created=1, strategy_cls=self._phase_b_class())
        self.assertEqual({c: ctx.cases[c]["outcome"] for c in ctx.cases}, {"B1": "passed", "B2": "passed"})
        self.assertEqual(ctx.cases["B1"]["adoption"]["reasons"], [])
        self.assertEqual(statuses, {"NTA-SIM-R2": "CANCELED", "NTA-SIM-P1": "DENIED"})
        self.assertIn(LA.HALTED_DENIAL, reasons["P1"])
        self.assertEqual(ctx.kill_switch["trading_state_after_engage"], "HALTED")
        self.assertTrue(hooks.kill.engaged())
        self.assertEqual(hooks.stops, ["strategy:phase_complete"])
        self.assertEqual(ctx.budget.used, 3)

    def test_phase_b_without_a_halted_risk_engine_sends_no_probe(self):
        carry = {"R2": {"client_order_id": "NTA-SIM-R2", "venue_order_id": None, "price": "300.00", "quantity": "1"}}
        ctx, hooks, statuses, _ = self.simulate("B", carry=carry, orders_created=1, strategy_cls=self._phase_b_class(),
                                                hooks_kwargs={"halt": False})
        self.assertEqual(ctx.cases["B2"]["outcome"], "failed")
        self.assertIn("B2_risk_engine_not_halted", ctx.cases["B2"]["reason"])
        self.assertEqual(statuses, {"NTA-SIM-R2": "CANCELED"})

    def test_phase_c_restart_keeps_the_halt(self):
        carry = {"R2": {"client_order_id": "NTA-SIM-R2", "price": "300.00"}}
        ctx, hooks, statuses, reasons = self.simulate("C", carry=carry, orders_created=3, halted_before=True, latch=True)
        self.assertEqual(ctx.cases["C1"]["outcome"], "passed")
        self.assertEqual(statuses, {"NTA-SIM-P2": "DENIED"})
        self.assertIn(LA.HALTED_DENIAL, reasons["P2"])
        self.assertEqual(ctx.kill_switch["trading_state_at_start"], "HALTED")
        self.assertEqual(LA.phase_status(ctx), "passed")
        # Regression: the case begins on the first timer tick. Begun inside on_start, the synchronous
        # OrderDenied was dropped (Strategy.handle_event delivers nothing before RUNNING).
        started = datetime.fromisoformat(ctx.node["strategy_started_at"])
        self.assertGreaterEqual((datetime.fromisoformat(ctx.cases["C1"]["started_at"]) - started).total_seconds(), 1.0)

    def test_phase_c_without_the_halt_fails_without_an_order(self):
        carry = {"R2": {"client_order_id": "NTA-SIM-R2", "price": "300.00"}}
        ctx, hooks, statuses, _ = self.simulate("C", carry=carry, orders_created=3, halted_before=False, latch=True)
        self.assertEqual(ctx.cases["C1"]["outcome"], "failed")
        self.assertEqual(statuses, {})
        self.assertEqual(ctx.budget.used, 3)


if __name__ == "__main__":
    unittest.main()
