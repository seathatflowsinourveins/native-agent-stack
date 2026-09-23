"""Offline tests for the IBKR paper order harness (ibkr-paper-orders/run.py).

Synthetic boundary fixtures only: nothing here connects to TWS or IB Gateway.
Everything except the NautilusBacktestFlow class runs on a plain python3 without
nautilus_trader or ibapi; that class runs the harness strategy inside a
NautilusTrader 1.231.0 BacktestEngine (a simulated venue, not IBKR) and is
skipped when nautilus_trader is not importable. None of this establishes the
ibkr-local-acceptance gate or IBKR paper behaviour.
"""
import ast
import copy
import importlib.util
import json
import os
import re
import signal
import tempfile
import time
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/engine-nautilus/ibkr-paper-orders"
RAW_ACCOUNT = re.compile(r"\b(?:D?[UF]|I)\d{5,}\b")
NY = ZoneInfo("America/New_York")
FAKE_ACCOUNT = "DU7654321"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = _load("ibkr_paper_orders_run", SOURCE / "run.py")
PLAN = RUN.load_plan()


def ny(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=NY).astimezone(timezone.utc)


WEDNESDAY_10AM = ny(2026, 9, 23, 10, 0)


class AfterHoursPlan(unittest.TestCase):
    def test_post_plan_is_the_regular_plan_with_only_the_session_changed(self):
        post, rth = RUN.load_plan(RUN.HERE / "plan-post.json"), RUN.load_plan(RUN.HERE / "plan.json")
        self.assertEqual(RUN.validate_plan(post), [])
        self.assertEqual((post["session"]["open"], post["session"]["close"], post["session"]["outside_rth"]),
                         ("16:00", "20:00", True))
        for key in set(rth) - {"session", "revision", "revision_note"}:
            self.assertEqual(post[key], rth[key], key)

    def test_session_and_outside_rth_must_agree(self):
        post, rth = RUN.load_plan(RUN.HERE / "plan-post.json"), RUN.load_plan(RUN.HERE / "plan.json")
        cases = [(post, {"outside_rth": False}), (rth, {"outside_rth": True}),
                 (post, {"contract_hours_field": "liquidHours"}), (rth, {"contract_hours_field": "tradingHours"}),
                 (post, {"use_contract_liquid_hours": False}), (post, {"open": "16:00", "close": "21:00"})]
        for plan, change in cases:
            with self.subTest(change=change):
                bad = copy.deepcopy(plan)
                bad["session"].update(change)
                self.assertNotEqual(RUN.validate_plan(bad), [])

    def test_only_predeclared_plans_are_selectable(self):
        with self.assertRaises(SystemExit):
            RUN.main(["run", "--receipt", "/dev/null", "--plan", "../plan.json"])

    def test_every_order_builder_passes_the_plan_order_tags(self):
        source = (RUN.HERE / "run.py").read_text()
        builders = re.findall(r"def _new_\w+_order\(self[^)]*\):\n(?:.*\n){1,4}?.*tags=self\._order_tags\(\)\)", source)
        self.assertEqual(len(builders), 3)
        self.assertEqual(source.count("order_factory.limit("), 3)


class PlanValidation(unittest.TestCase):
    def test_frozen_plan_is_valid(self):
        self.assertEqual(RUN.validate_plan(PLAN), [])
        self.assertEqual(PLAN["client_ids"], {**PLAN["client_ids"], "node": 91, "check": 92})
        self.assertEqual(PLAN["bounds"]["max_orders"], 6)
        self.assertEqual(PLAN["receipt"]["kind"], RUN.RECEIPT_KIND)

    def test_violations_are_reported(self):
        cases = [
            (("bounds", "max_orders"), 7, "max_orders"),
            (("bounds", "max_quantity_per_order"), 2, "max_quantity"),
            (("bounds", "max_notional_per_order_usd"), 5000, "notional"),
            (("bounds", "max_roundtrip_loss_usd"), 50, "max_roundtrip_loss"),
            (("client_ids", "node"), 73, "client ids"),
            (("timeouts", "overall_deadline_seconds"), 900, "overall_deadline"),
            (("session", "close_buffer_minutes"), 5, "close_buffer"),
            (("data", "quote_max_age_seconds"), 900, "quote_max_age"),
        ]
        for (section, key), value, needle in cases:
            plan = copy.deepcopy(PLAN)
            plan[section][key] = value
            errors = RUN.validate_plan(plan)
            self.assertTrue(any(needle in e for e in errors), (key, errors))
        plan = copy.deepcopy(PLAN)
        plan["paper_ports"] = [4001]
        self.assertTrue(RUN.validate_plan(plan))
        plan = copy.deepcopy(PLAN)
        plan["cases"] = list(reversed(plan["cases"]))
        self.assertTrue(any("C1..C4" in e for e in RUN.validate_plan(plan)))
        plan = copy.deepcopy(PLAN)
        del plan["bounds"]
        self.assertTrue(any("missing" in e for e in RUN.validate_plan(plan)))


class Prices(unittest.TestCase):
    def test_resting_price_floors_to_cent_with_minimum(self):
        self.assertEqual(RUN.resting_buy_price("650.37"), Decimal("325.18"))
        self.assertEqual(RUN.resting_buy_price("650.39"), Decimal("325.19"))
        self.assertEqual(RUN.resting_buy_price("1.50"), Decimal("1.00"))
        with self.assertRaises(ValueError):
            RUN.resting_buy_price(0)

    def test_marketable_buy_caps_by_notional(self):
        self.assertEqual(RUN.marketable_buy_price("650.00", 1, 1000, 0.05), Decimal("650.05"))
        self.assertEqual(RUN.marketable_buy_price("650.001", 1, 1000, 0.05), Decimal("650.06"))
        self.assertEqual(RUN.marketable_buy_price("999.97", 1, 1000, 0.05), Decimal("1000.00"))
        self.assertIsNone(RUN.marketable_buy_price("1000.01", 1, 1000, 0.05))

    def test_marketable_sell_and_worst_case_loss(self):
        self.assertEqual(RUN.marketable_sell_price("650.00", 0.05), Decimal("649.95"))
        self.assertEqual(RUN.marketable_sell_price("0.03", 0.05), Decimal("0.01"))
        loss = RUN.worst_case_roundtrip_loss(Decimal("650.07"), "650.00", 1, 0.05, 1.0)
        self.assertEqual(loss, Decimal("2.12"))

    def test_quote_freshness(self):
        self.assertTrue(RUN.quote_is_fresh(RUN.quote_age_seconds(100.0, 0.5, 95.0), 10, 2))
        self.assertFalse(RUN.quote_is_fresh(RUN.quote_age_seconds(100.0, 0.0, 89.0), 10, 2))
        self.assertFalse(RUN.quote_is_fresh(RUN.quote_age_seconds(100.0, 0.0, 103.0), 10, 2))
        self.assertTrue(RUN.quote_is_fresh(-1.5, 10, 2))
        self.assertFalse(RUN.quote_is_valid("650.02", "650.00"))
        self.assertTrue(RUN.quote_is_valid("650.00", "650.02"))


class SubmitSpacingAndCancels(unittest.TestCase):
    def test_rate_parts_and_spacing(self):
        self.assertEqual(RUN.submit_rate_parts("100/00:00:01"), (100, 1.0))
        self.assertEqual(RUN.submit_rate_parts("1/00:01:00"), (1, 60.0))
        with self.assertRaises(ValueError):
            RUN.submit_rate_parts("0/00:00:01")
        self.assertTrue(RUN.spacing_ok(10, None, 1.5))
        self.assertFalse(RUN.spacing_ok(int(2.4e9), int(1e9), 1.5))
        self.assertTrue(RUN.spacing_ok(int(2.5e9), int(1e9), 1.5))

    def test_plan_rejects_binding_throttle_and_short_inflight_horizon(self):
        for mutate, needle in [
            (lambda p: p["bounds"].update(max_order_submit_rate="1/00:00:01"), "max_order_submit_rate"),
            (lambda p: p["bounds"].update(min_submit_spacing_seconds=0.5), "min_submit_spacing"),
            (lambda p: p["exec_engine"].update(inflight_check_retries=5), "in-flight"),
            (lambda p: p["exec_engine"].update(inflight_check_interval_ms=0), "inflight_check_interval_ms"),
            (lambda p: p["timeouts"].update(flatten_retry_delay_seconds=0), "flatten_retry_delay"),
            (lambda p: p["bounds"].update(max_cancel_attempts_per_order=1), "max_cancel_attempts"),
            (lambda p: p["bounds"].update(max_order_submit_rate="garbage"), "malformed"),
        ]:
            plan = copy.deepcopy(PLAN)
            mutate(plan)
            errors = RUN.validate_plan(plan)
            self.assertTrue(any(needle in e for e in errors), (needle, errors))

    def test_cancel_decision_is_bounded_and_recancels(self):
        iv, mx = 5, 3
        d = RUN.cancel_decision
        self.assertEqual(d(False, 0, None, 0, iv, mx), "cancel")
        self.assertEqual(d(True, 0, None, 0, iv, mx), "cancel_all")
        # A cancel was sent 2 s ago: wait; after the interval re-send (cancel rejected -> order open again).
        self.assertEqual(d(False, 1, 0, int(2e9), iv, mx), "wait")
        self.assertEqual(d(False, 1, 0, int(5e9), iv, mx), "cancel")
        # Still PENDING_CANCEL after the interval (cancel dropped): re-send through cancel_all_orders.
        self.assertEqual(d(True, 1, 0, int(6e9), iv, mx), "cancel_all")
        self.assertEqual(d(True, 3, 0, int(60e9), iv, mx), "exhausted")
        # Finish and on_stop always send, whatever the count or interval.
        self.assertEqual(d(True, 3, 0, 1, iv, mx, force=True), "cancel_all")
        self.assertEqual(d(False, 1, 0, 1, iv, mx, force=True), "cancel")


class ContextEvents(unittest.TestCase):
    def test_c1_events_after_c2_passed_are_c2_evidence(self):
        ctx = RUN.RunContext(PLAN, "NTP-T")
        cid = ctx.client_order_id("C1")
        ctx.register_order(cid, "C1", "BUY", 1, "300.00", 1, 1)
        ctx.begin("C1", 1)
        ctx.pass_case("C1", 2)
        ctx.begin("C2", 2)
        ctx.record_event(cid, "OrderCanceled", 3)
        ctx.pass_case("C2", 3)
        ctx.begin("C3", 3)
        ctx.record_event(cid, "OrderCanceled", 4, duplicate_ignored=True)
        self.assertEqual([e["type"] for e in ctx.cases["C2"]["events"]], ["OrderCanceled", "OrderCanceled"])
        self.assertEqual(ctx.cases["C1"]["events"], [])
        self.assertIn("duplicate_events", ctx.summary())


class Budget(unittest.TestCase):
    def test_order_count_cap(self):
        b = RUN.OrderBudget(6, 1)
        for i in range(6):
            self.assertEqual(b.reserve("C1", 1), i + 1)
        with self.assertRaises(RUN.BudgetError):
            b.reserve("cleanup", 1)
        self.assertEqual(b.used, 6)
        self.assertEqual(b.remaining, 0)

    def test_quantity_cap(self):
        b = RUN.OrderBudget(6, 1)
        for qty in (0, 2, -1):
            with self.assertRaises(RUN.BudgetError):
                b.reserve("C3", qty)
        self.assertEqual(b.used, 0)


class SessionWindow(unittest.TestCase):
    def test_regular_hours_and_close_buffer(self):
        self.assertEqual(RUN.rth_check(WEDNESDAY_10AM, PLAN), (True, "inside_window"))
        self.assertEqual(RUN.rth_check(ny(2026, 9, 23, 9, 29), PLAN)[1], "before_open")
        # 16:00 - 10 min buffer - 420 s deadline = 15:43:00 latest start.
        self.assertTrue(RUN.rth_check(ny(2026, 9, 23, 15, 43, 0), PLAN)[0])
        self.assertEqual(RUN.rth_check(ny(2026, 9, 23, 15, 43, 1), PLAN)[1], "too_close_to_close")
        self.assertEqual(RUN.rth_check(ny(2026, 9, 23, 15, 55), PLAN, horizon_s=0)[1], "too_close_to_close")
        self.assertEqual(RUN.rth_check(ny(2026, 9, 26, 11, 0), PLAN)[1], "market_closed_today")  # Saturday

    def test_liquid_hours_early_close_and_holiday(self):
        early = "20261127:0930-20261127:1300;20261130:0930-20261130:1600"
        sessions = RUN.parse_liquid_hours(early, "US/Eastern", date(2026, 11, 27))
        self.assertEqual(len(sessions), 1)
        self.assertTrue(RUN.rth_check(ny(2026, 11, 27, 12, 0), PLAN, sessions)[0])
        self.assertEqual(RUN.rth_check(ny(2026, 11, 27, 12, 50), PLAN, sessions)[1], "too_close_to_close")
        closed = RUN.parse_liquid_hours("20261126:CLOSED;20261127:0930-20261127:1300", "US/Eastern", date(2026, 11, 26))
        self.assertEqual(closed, [])
        self.assertEqual(RUN.rth_check(ny(2026, 11, 26, 11, 0), PLAN, closed)[1], "market_closed_today")
        self.assertIsNone(RUN.parse_liquid_hours("garbage", "US/Eastern", date(2026, 11, 26)))
        self.assertEqual(RUN.resolve_zone("US/Eastern").key, "America/New_York")
        self.assertIsNone(RUN.parse_liquid_hours("20261127:0930-20261127:1300", "US/Eastern", date(2026, 11, 26)))


class CheckStateVerdict(unittest.TestCase):
    def _state(self, accounts="DU1234567"):
        s = RUN.CheckState()
        s.managedAccounts(accounts)
        for k in RUN.CHECK_REQUESTS:
            s.done[k].set()
        return s

    def test_paper_single_account_passes_and_account_stays_private(self):
        s = self._state()
        self.assertEqual(RUN.check_verdict(s.r, s.completed()), "passed")
        self.assertEqual(s.single_account(), "DU1234567")
        self.assertNotIn("DU1234567", json.dumps(s.r))

    def test_non_paper_account_is_latched(self):
        s = self._state("DU1234567,U7654321")
        self.assertEqual(RUN.check_verdict(s.r, s.completed()), "refused_not_paper_account")
        s.managedAccounts("DU1234567")
        self.assertEqual(RUN.check_verdict(s.r, s.completed()), "refused_not_paper_account")

    def test_multiple_accounts_and_existing_state(self):
        s = self._state("DU1234567,DU7654321")
        self.assertEqual(RUN.check_verdict(s.r, s.completed()), "refused_account_scope")
        s = self._state()
        s.position("DU1234567", SimpleNamespace(symbol="SPY"), 1, 650.0)
        self.assertEqual(RUN.check_verdict(s.r, s.completed()), "refused_existing_state")
        self.assertTrue(s.r["spy_position"])
        s = self._state()
        order, state = SimpleNamespace(permId=5), SimpleNamespace(status="Submitted")
        s.openOrder(1, None, order, state)
        s.openOrder(1, None, order, state)  # duplicate callback for the same order
        self.assertEqual(s.r["open_orders"], 1)
        self.assertEqual(RUN.check_verdict(s.r, s.completed()), "refused_existing_state")

    def test_error_text_is_redacted(self):
        s = RUN.CheckState()
        s.error(1, 0, 321, "account DU1234567 at 10.0.0.5:4002 /home/example/x.log")
        text = json.dumps(s.r)
        self.assertIsNone(RAW_ACCOUNT.search(text))
        self.assertNotIn("10.0.0.5", text)
        self.assertNotIn("/home/", text)


def _check_result(status, positions=0, open_orders=0):
    return {"client": "ibapi", "status": status, "observed": {
        "account_count": 1, "paper_accounts": status != "refused_not_paper_account", "positions": positions,
        "open_orders": open_orders, "server_minus_local_s": 0.2, "errors": [
            {"code": 1, "text": f"raw {FAKE_ACCOUNT}"}]}}


TODAY_HOURS = "20260923:0930-20260923:1600;20260924:0930-20260924:1600"


class FakeChecks:
    """Scripted run_check replacement: first call is the pre-run check, later calls the flat proof.
    A post entry that is an exception instance is raised instead of returning a result."""

    def __init__(self, pre, post=("passed",), liquid_hours=TODAY_HOURS, trading_hours=None):
        self.pre, self.post, self.calls, self.liquid_hours = pre, list(post), [], liquid_hours
        self.trading_hours = trading_hours

    def __call__(self, plan, port, *, with_session, deadline_s=None):
        self.calls.append(with_session)
        if with_session:
            status = self.pre
            result = _check_result(status)
            if self.liquid_hours is not None:
                result.update(liquid_hours=self.liquid_hours, time_zone_id="US/Eastern")
            if self.trading_hours is not None:
                result.update(trading_hours=self.trading_hours, time_zone_id="US/Eastern")
            return result, (FAKE_ACCOUNT if status == "passed" else None)
        status = self.post.pop(0) if self.post else "passed"
        if isinstance(status, BaseException):
            raise status
        positions = 1 if status == "refused_existing_state" else 0
        return _check_result(status, positions=positions), None


class RunRefusals(unittest.TestCase):
    def _run(self, port=4002, checks=None, now=WEDNESDAY_10AM, node_fn=None, receipt=None, plan="plan.json"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = receipt or str(Path(tmp.name) / "r.json")
        checks = checks or FakeChecks("passed")
        nodes = []

        def fake_node(plan, account, port_, ctx, **kw):
            nodes.append(account)
            if node_fn:
                node_fn(ctx)

        args = SimpleNamespace(port=port, receipt=path, log_level="WARNING", plan=plan)
        code = RUN.cmd_run(args, check_fn=checks, node_fn=fake_node, now_fn=lambda: now, sleep_fn=lambda s: None)
        text = Path(path).read_text() if Path(path).exists() else None
        return code, (json.loads(text) if text else None), text, checks, nodes

    def test_after_hours_plan_reads_trading_hours_and_enters_the_node(self):
        trading = "20260923:0400-20260923:2000;20260924:0400-20260924:2000"
        code, r, text, checks, nodes = self._run(now=ny(2026, 9, 23, 19, 0), plan="plan-post.json",
                                                 checks=FakeChecks("passed", trading_hours=trading))
        self.assertEqual(nodes, [FAKE_ACCOUNT])
        self.assertEqual(r["session_check"]["contract_hours_field"], "tradingHours")
        self.assertEqual(r["session_check"]["with_liquid_hours"], "inside_window")
        self.assertEqual(r["plan_sha256"], RUN.sha256_file(RUN.HERE / "plan-post.json"))
        self.assertNotIn("0400-20260923", text)  # contract hours are never written to the receipt

    def test_after_hours_plan_refused_without_todays_trading_hours(self):
        code, r, _, _, nodes = self._run(now=ny(2026, 9, 23, 19, 0), plan="plan-post.json",
                                         checks=FakeChecks("passed", trading_hours=""))
        self.assertEqual((code, r["status"], nodes), (3, "refused_liquid_hours_unavailable", []))

    def test_regular_plan_still_refused_after_hours_and_post_plan_before_16(self):
        code, r, _, checks, _ = self._run(now=ny(2026, 9, 23, 19, 0))
        self.assertEqual((code, r["status"], checks.calls), (3, "refused_outside_rth", []))
        code, r, _, checks, _ = self._run(now=WEDNESDAY_10AM, plan="plan-post.json")
        self.assertEqual((code, r["status"], checks.calls), (3, "refused_outside_rth", []))

    def test_non_paper_port_refused_before_connecting(self):
        code, r, _, checks, nodes = self._run(port=4001)
        self.assertEqual((code, r["status"]), (3, "refused_not_paper_port"))
        self.assertEqual((checks.calls, nodes), ([], []))

    def test_outside_rth_refused_before_connecting(self):
        code, r, _, checks, nodes = self._run(now=ny(2026, 9, 23, 8, 0))
        self.assertEqual((code, r["status"]), (3, "refused_outside_rth"))
        self.assertEqual(checks.calls, [])

    def test_gate_receipt_path_refused_and_untouched(self):
        before = RUN.GATE_RECEIPT.read_bytes() if RUN.GATE_RECEIPT.exists() else None
        code, r, _, checks, nodes = self._run(receipt=str(RUN.GATE_RECEIPT))
        self.assertEqual(code, 3)
        self.assertEqual(checks.calls, [])
        after = RUN.GATE_RECEIPT.read_bytes() if RUN.GATE_RECEIPT.exists() else None
        self.assertEqual(before, after)

    def test_non_du_account_refused(self):
        code, r, text, _, nodes = self._run(checks=FakeChecks("refused_not_paper_account"))
        self.assertEqual((code, r["status"], nodes), (3, "refused_not_paper_account", []))

    def test_existing_positions_or_orders_refused(self):
        code, r, _, _, nodes = self._run(checks=FakeChecks("refused_existing_state"))
        self.assertEqual((code, r["status"], nodes), (3, "refused_existing_state", []))

    def test_not_connected(self):
        code, r, _, _, nodes = self._run(checks=FakeChecks("not_connected"))
        self.assertEqual((code, r["status"], r["evidence_class"], nodes), (2, "not_connected", "not_connected", []))

    def test_incomplete_check_refused(self):
        code, r, _, _, nodes = self._run(checks=FakeChecks("incomplete"))
        self.assertEqual((code, r["status"], nodes), (3, "refused_check_not_passed", []))

    def test_passed_only_with_all_cases_and_flat_proof(self):
        def all_pass(ctx):
            for cid in RUN.CASE_IDS:
                ctx.begin(cid, 1)
                ctx.pass_case(cid, 2)
            ctx.compute_roundtrip()

        code, r, text, checks, nodes = self._run(node_fn=all_pass)
        self.assertEqual((code, r["status"]), (0, "passed"))
        self.assertEqual(nodes, [FAKE_ACCOUNT])  # the account reached the node in memory
        self.assertEqual(checks.calls, [True, False])
        self.assertNotIn(FAKE_ACCOUNT, text)
        self.assertIsNone(RAW_ACCOUNT.search(text))
        for key in ("schema_version", "kind", "nautilus_trader_version", "ibapi_version", "plan_sha256",
                    "harness_sha256", "flat_proof", "status", "exit_code"):
            self.assertIn(key, r)
        self.assertEqual(r["plan_sha256"], RUN.sha256_file(RUN.PLAN_PATH))
        self.assertEqual(r["kind"], RUN.RECEIPT_KIND)

    def test_not_flat_after_run_is_cleanup_required(self):
        code, r, _, checks, _ = self._run(checks=FakeChecks("passed", post=["refused_existing_state"] * 2))
        self.assertEqual((code, r["status"]), (3, "cleanup_required"))
        self.assertEqual(len(r["flat_proof"]["attempts"]), 2)

    def test_flat_on_retry_and_incomplete_cases(self):
        code, r, _, _, _ = self._run(checks=FakeChecks("passed", post=["refused_existing_state", "passed"]))
        self.assertEqual((code, r["status"]), (1, "incomplete"))

    def test_failed_case(self):
        def fail_c1(ctx):
            ctx.begin("C1", 1)
            ctx.start_cleanup("C1_OrderRejected: price DU1234567", "failed", 2)

        code, r, text, _, _ = self._run(node_fn=fail_c1)
        self.assertEqual((code, r["status"]), (1, "failed"))
        self.assertIsNone(RAW_ACCOUNT.search(text))


# Ten earlier days put today's segment past the old 200-character cut.
EARLIER_DAYS = ";".join(f"202609{d:02d}:0930-202609{d:02d}:1600" for d in range(9, 19)) + ";20260919:CLOSED"


class FakeIbapi(RUN.CheckState):
    """Offline stand-in for the ibapi client that run_check drives (no socket)."""

    def __init__(self, liquid_hours):
        super().__init__()
        self._hours, self._connected = liquid_hours, False

    def connect(self, host, port, client_id):
        self._connected = True
        self.managedAccounts(FAKE_ACCOUNT)

    def isConnected(self):
        return self._connected

    def run(self):
        pass

    def disconnect(self):
        self._connected = False

    def reqCurrentTime(self):
        self.currentTime(int(datetime.now(timezone.utc).timestamp()))

    def reqPositions(self):
        self.positionEnd()

    def cancelPositions(self):
        pass

    def reqAllOpenOrders(self):
        self.openOrderEnd()

    def reqContractDetails(self, req_id, contract):
        c = SimpleNamespace(secType="STK", currency="USD", exchange="SMART", primaryExchange="ARCA")
        self.contractDetails(req_id, SimpleNamespace(contract=c, liquidHours=self._hours, timeZoneId="US/Eastern",
                                                     minTick=0.01))
        self.contractDetailsEnd(req_id)


class LiquidHoursFailClosed(unittest.TestCase):
    """Finding 1: holiday/early-close protection must not fail open."""

    def test_run_check_keeps_the_whole_liquid_hours_string(self):
        hours = EARLIER_DAYS + ";20260923:0930-20260923:1300;20260924:0930-20260924:1600"
        self.assertGreater(hours.index("20260923:"), 200)
        result, account = RUN.run_check(PLAN, 4002, with_session=True, client_factory=lambda: FakeIbapi(hours),
                                        contract_factory=lambda: None)
        self.assertEqual((result["status"], account), ("passed", FAKE_ACCOUNT))
        sessions = RUN.parse_liquid_hours(result["liquid_hours"], result["time_zone_id"], date(2026, 9, 23))
        self.assertEqual([(a.hour, b.hour) for a, b in sessions], [(9, 13)])
        self.assertNotIn("liquid_hours", RUN._sanitized_check(result))

    def test_parse_skips_other_broken_days_but_not_a_broken_today(self):
        day = date(2026, 9, 23)
        good = "20260922:09x0-bad;garbage;20260923:0930-20260923:1300;20260924:0930"
        self.assertEqual(len(RUN.parse_liquid_hours(good, "US/Eastern", day)), 1)
        self.assertIsNone(RUN.parse_liquid_hours("20260922:0930-20260922:1600;20260923:09", "US/Eastern", day))
        self.assertIsNone(RUN.parse_liquid_hours("20260923:0930-20260923:16xx", "US/Eastern", day))
        self.assertIsNone(RUN.parse_liquid_hours("20260923:0930-20260923:16", "US/Eastern", day))  # not 01:06
        legacy = RUN.parse_liquid_hours("20260923:0930-1300;20260924:CLOSED", "US/Eastern", day)
        self.assertEqual([(a.hour, b.hour) for a, b in legacy], [(9, 13)])

    def _run(self, liquid_hours, now=WEDNESDAY_10AM):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "r.json"
        nodes = []
        checks = FakeChecks("passed", liquid_hours=liquid_hours)
        code = RUN.cmd_run(SimpleNamespace(port=4002, receipt=str(path), log_level="WARNING"), check_fn=checks,
                           node_fn=lambda *a, **k: nodes.append(1), now_fn=lambda: now, sleep_fn=lambda s: None)
        return code, json.loads(path.read_text()), nodes, checks

    def test_missing_or_broken_today_refuses_the_run(self):
        for hours in (None, "", "garbage", EARLIER_DAYS, "20260923:0930-20260923:16", "20260924:0930-20260924:1600"):
            code, r, nodes, checks = self._run(hours)
            self.assertEqual((code, r["status"], nodes), (3, "refused_liquid_hours_unavailable", []), hours)
            self.assertEqual(checks.calls, [True])  # no node, no flat proof: nothing was submitted
            self.assertFalse(r["session_check"]["liquid_hours_parsed"])

    def test_early_close_beyond_200_chars_refuses_the_run(self):
        hours = EARLIER_DAYS + ";20260923:0930-20260923:1000;20260924:0930-20260924:1600"
        code, r, nodes, _ = self._run(hours)
        self.assertEqual((code, r["status"], r["session_check"]["with_liquid_hours"], nodes),
                         (3, "refused_outside_rth", "too_close_to_close", []))
        code, r, nodes, _ = self._run(EARLIER_DAYS + ";20260923:CLOSED")
        self.assertEqual((r["status"], r["session_check"]["with_liquid_hours"], nodes),
                         ("refused_outside_rth", "market_closed_today", []))


class RunReceiptAndFlatProof(unittest.TestCase):
    """Findings 2 and 3: a cleanup_required receipt exists before the node connects, and the
    independent flat proof runs on every exit path once orders may exist."""

    def _run(self, node_fn=None, checks=None, receipt=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(receipt(tmp.name) if receipt else Path(tmp.name) / "r.json")
        checks = checks or FakeChecks("passed")
        seen = []

        def fake_node(plan, account, port, ctx, **kw):
            seen.append(json.loads(path.read_text()) if path.exists() else None)
            if node_fn:
                node_fn(ctx)

        code = RUN.cmd_run(SimpleNamespace(port=4002, receipt=str(path), log_level="WARNING"), check_fn=checks,
                           node_fn=fake_node, now_fn=lambda: WEDNESDAY_10AM, sleep_fn=lambda s: None)
        text = path.read_text() if path.exists() else None
        return code, (json.loads(text) if text else None), text, seen, checks

    def test_provisional_cleanup_required_receipt_exists_while_the_node_runs(self):
        code, r, text, seen, _ = self._run()
        (provisional,) = seen
        self.assertEqual((provisional["status"], provisional["evidence_class"], provisional["exit_code"]),
                         ("cleanup_required", "native_paper", 3))
        self.assertTrue(provisional["provisional"])
        self.assertIn("provisional", provisional["note"])
        self.assertTrue(provisional["run"]["run_prefix"].startswith("NTP-"))
        self.assertEqual(provisional["flat_proof"], {"status": "not_attempted"})
        # The final receipt replaced it.
        self.assertEqual(r["run"]["run_prefix"], provisional["run"]["run_prefix"])
        self.assertNotIn("provisional", r)
        self.assertIsNone(RAW_ACCOUNT.search(text))

    def test_unwritable_receipt_path_refuses_before_the_node(self):
        code, r, _, seen, checks = self._run(receipt=lambda d: Path(d) / "missing-dir" / "r.json")
        self.assertEqual((code, r, seen), (3, None, []))
        self.assertEqual(checks.calls, [True])  # read-only pre-check only; the node never connected

    def test_base_exception_from_the_node_still_runs_the_flat_proof(self):
        class Hangup(BaseException):
            pass

        for exc in (KeyboardInterrupt("signal 1"), Hangup("gone"), SystemExit(1)):
            def node(ctx, exc=exc):
                ctx.budget.reserve("C1", 1)
                raise exc

            code, r, _, _, checks = self._run(node_fn=node)
            self.assertEqual(checks.calls, [True, False], exc)
            self.assertEqual((r["flat_proof"]["status"], r["status"], code), ("passed", "incomplete", 1), exc)
            self.assertTrue(any(type(exc).__name__ in e for e in r["run"]["errors"]), r["run"]["errors"])
        self.assertTrue(r["interrupted"])

    def test_exception_from_the_node_is_never_a_pass(self):
        def node(ctx):
            ctx.budget.reserve("C1", 1)
            for cid in RUN.CASE_IDS:
                ctx.pass_case(cid, 1)
            raise RuntimeError("dispose failed after a forced stop")

        code, r, _, _, checks = self._run(node_fn=node)
        self.assertEqual(r["flat_proof"]["status"], "passed")
        self.assertEqual((r["status"], code), ("incomplete", 1))
        self.assertIn("RuntimeError", r["error"])

    def test_check_exception_in_the_post_loop_is_an_attempt(self):
        checks = FakeChecks("passed", post=[RuntimeError("socket DU1234567 closed"), "passed"])
        code, r, text, _, _ = self._run(checks=checks)
        self.assertEqual([a["status"] for a in r["flat_proof"]["attempts"]], ["error", "passed"])
        self.assertEqual(r["flat_proof"]["status"], "passed")
        self.assertIsNone(RAW_ACCOUNT.search(text))

    def test_interrupt_during_the_flat_proof_is_recorded(self):
        def node(ctx):
            ctx.budget.reserve("C1", 1)

        checks = FakeChecks("passed", post=[KeyboardInterrupt()])
        code, r, _, _, _ = self._run(node_fn=node, checks=checks)
        self.assertEqual((code, r["status"], r["flat_proof"]["status"]), (3, "cleanup_required", "interrupted"))


class _FakeNode:
    """TradingNode stand-in on a real asyncio loop whose graceful stop never finishes."""

    def __init__(self):
        import asyncio

        self.asyncio = asyncio
        self.loop = asyncio.new_event_loop()
        self.kernel = SimpleNamespace(cancel_all_tasks=self._cancel_all_tasks)
        self.stop_calls = 0
        self.cancelled = 0

    def stop(self):
        self.stop_calls += 1  # hangs: node.run() never returns on its own

    def _cancel_all_tasks(self):
        for task in self.asyncio.all_tasks(self.loop):
            self.cancelled += 1
            task.cancel()

    def run(self, actions, safety_s=3.0):
        async def engines():
            await self.asyncio.Event().wait()

        for delay, fn in actions:
            self.loop.call_later(delay, fn)
        self.loop.call_later(safety_s, self.loop.stop)  # without escalation the test ends here and fails
        start = time.monotonic()
        try:
            self.loop.run_until_complete(engines())
        except (RuntimeError, self.asyncio.CancelledError):
            pass  # "Event loop stopped before Future completed" is what TradingNode.run catches
        finally:
            elapsed = time.monotonic() - start
            self.loop.close()
        return elapsed


class NodeStopEscalation(unittest.TestCase):
    """Findings 4 and 5 on NodeStopControl (the run_node controller), offline."""

    def _control(self, allowance=15):
        plan = copy.deepcopy(PLAN)
        plan["timeouts"]["node_stop_allowance_seconds"] = allowance
        ctx = RUN.RunContext(plan, "NTP-T")
        node = _FakeNode()
        aborts = []
        control = RUN.NodeStopControl(ctx, plan, node=node, loop=node.loop, abort=aborts.append)
        return ctx, node, control, aborts

    def test_signal_before_start_marks_the_run_finished(self):
        for handler in ("on_signal", "on_hard_stop"):
            ctx, node, control, aborts = self._control()
            args = (signal.SIGTERM,) if handler == "on_signal" else ()
            getattr(control, handler)(*args)
            self.assertTrue(ctx.finished, handler)
            self.assertEqual(ctx.cleanup["kind"], "incomplete")
            self.assertEqual((node.stop_calls, aborts), (1, []))
            node.loop.close()

    def test_second_signal_forces_a_hung_stop(self):
        ctx, node, control, _ = self._control()
        sig = signal.SIGHUP if hasattr(signal, "SIGHUP") else signal.SIGTERM
        elapsed = node.run([(0.01, lambda: control.on_signal(sig)), (0.05, lambda: control.on_signal(sig))])
        self.assertLess(elapsed, 2.0)
        self.assertEqual(ctx.node["forced_stop_by"], f"signal_{sig.name}")
        self.assertGreaterEqual(node.cancelled, 1)
        self.assertEqual(node.stop_calls, 1)

    def test_stop_allowance_forces_a_hung_stop(self):
        ctx, node, control, _ = self._control(allowance=0.2)
        elapsed = node.run([(0.01, lambda: control.request_stop("strategy:cases_complete"))])
        self.assertLess(elapsed, 2.0)
        self.assertEqual(ctx.node["forced_stop_by"], "stop_allowance_exceeded")

    def test_hard_stop_keeps_a_graceful_stop_inside_its_allowance(self):
        now = [100.0]
        ctx, node, control, _ = self._control(allowance=15)
        control.monotonic = lambda: now[0]
        ctx.started = True
        ctx.finished = True  # the strategy's _finish marks the run finished, then requests the stop
        control.request_stop("strategy:cleanup_deadline")
        self.assertEqual(control.force_at, 115.0)
        now[0] = 101.0
        control.on_hard_stop()  # a stop already in progress is not cut short
        self.assertEqual((control.forced, control.force_at), (False, 115.0))
        control.on_signal(signal.SIGTERM)  # a first signal during a graceful stop waits too
        self.assertFalse(control.forced)
        control.on_signal(signal.SIGTERM)
        self.assertTrue(control.forced)
        node.loop.close()

    def test_first_signal_after_start_aborts_into_cleanup(self):
        ctx, node, control, aborts = self._control()
        ctx.started = True
        control.on_signal(signal.SIGTERM)
        self.assertEqual((aborts, node.stop_calls, ctx.finished), (["signal_SIGTERM"], 0, False))
        node.loop.close()


class Redaction(unittest.TestCase):
    def test_redact_and_scrub(self):
        text = "U1234567 DF123456 I987654 host 192.168.1.2:4002 at /home/example/nautilus/x.py"
        out = RUN.redact(text)
        self.assertIsNone(RAW_ACCOUNT.search(out))
        self.assertNotIn("192.168", out)
        self.assertNotIn("/home/", out)
        serialized = json.dumps({"a": "DU0000001", "b": "path /home/example/q", "c": "blueprints/us-equities/x.json",
                                 "d": "ACCTX"})
        scrubbed = RUN.scrub_serialized(serialized, ["ACCTX"])
        self.assertNotIn("DU0000001", scrubbed)
        self.assertNotIn("/home/", scrubbed)
        self.assertNotIn("ACCTX", scrubbed)
        self.assertIn("blueprints/us-equities/x.json", scrubbed)

    def test_ib_margin_rejection_amounts_are_removed(self):
        text = ("Order rejected - reason:YOUR ORDER IS NOT ACCEPTED. IN ORDER TO OBTAIN THE DESIRED POSITION YOUR "
                "EQUITY WITH LOAN VALUE [1234567.89 USD] MUST EXCEED THE INITIAL MARGIN [5,678.90 USD] "
                "account DU1234567")
        out = RUN.redact(text)
        for leak in ("1234567.89", "5,678.90", "DU1234567"):
            self.assertNotIn(leak, out)
        self.assertIn("EQUITY WITH LOAN VALUE", out)
        for text, leak in [("Available Funds: 98,765.43", "98,765.43"), ("Net Liquidation 250000", "250000"),
                           ("cash balance USD 12,000.50 remains", "12,000.50"),
                           ("precautionary: exceeds 5000.00 USD limit", "5000.00"),
                           ("Buying Power = 400000.00", "400000.00")]:
            self.assertNotIn(leak, RUN.redact(text), text)
        # Error codes and case names survive.
        self.assertEqual(RUN.redact("C3_OrderRejected: code 201"), "C3_OrderRejected: code 201")

    def test_rejection_amounts_are_redacted_in_receipt(self):
        ctx = RUN.RunContext(PLAN, "NTP-T")
        cid = ctx.client_order_id("C1")
        ctx.register_order(cid, "C1", "BUY", 1, "300.00", 1, 1)
        ctx.begin("C1", 1)
        ctx.record_event(cid, "OrderRejected", 2, reason="EQUITY WITH LOAN VALUE [1234567.89 USD]")
        ctx.start_cleanup("C1_OrderRejected: EQUITY WITH LOAN VALUE [1234567.89 USD]", "failed", 3)
        self.assertNotIn("1234567.89", json.dumps(ctx.summary()))
        s = RUN.CheckState()
        s.error(7, 0, 201, "Available Funds: 98,765.43")
        self.assertNotIn("98,765.43", json.dumps(s.r))

    def test_exit_codes(self):
        self.assertEqual([RUN.exit_code_for(s) for s in ("passed", "failed", "incomplete", "not_connected",
                                                         "cleanup_required", "refused_outside_rth")], [0, 1, 1, 2, 3, 3])


class SourceSafety(unittest.TestCase):
    """AST checks: the only order-creating calls are the case builders."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((SOURCE / "run.py").read_text())
        cls.parents = {}
        for node in ast.walk(cls.tree):
            for child in ast.iter_child_nodes(node):
                cls.parents[child] = node

    def _enclosing_function(self, node):
        while node in self.parents:
            node = self.parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return None

    def _calls(self, attr):
        return [(self._enclosing_function(n), n) for n in ast.walk(self.tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attr]

    def test_order_factory_calls_only_in_case_builders(self):
        factory_calls = [(self._enclosing_function(n), n.func.attr) for n in ast.walk(self.tree)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                         and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "order_factory"]
        # C2 is a cancel and creates no order; the cleanup flatten reuses the C4 builder.
        self.assertEqual(sorted(factory_calls), [("_new_c1_order", "limit"), ("_new_c3_order", "limit"),
                                                 ("_new_flatten_order", "limit")])

    def test_submit_and_cancel_call_sites(self):
        self.assertEqual([f for f, _ in self._calls("submit_order")], ["_submit"])
        self.assertEqual([f for f, _ in self._calls("cancel_order")], ["_send_cancel"])
        self.assertEqual([f for f, _ in self._calls("cancel_all_orders")], ["_sweep_cancels"])
        self.assertEqual(sorted(f for f, _ in self._calls("_send_cancel")), ["_cancel_c1", "_sweep_cancels"])
        self.assertEqual(sorted(f for f, _ in self._calls("_sweep_cancels")), ["_cleanup_step", "_finish", "on_stop"])
        builders = {f for f, _ in self._calls("_new_c1_order") + self._calls("_new_c3_order")
                    + self._calls("_new_flatten_order")}
        self.assertEqual(builders, {"_submit"})
        self.assertEqual({f for f, _ in self._calls("_submit")}, {"_try_step", "_cleanup_step"})

    def test_budget_reserved_before_factory_call(self):
        submit = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == "_submit")
        lines = {getattr(n.func, "attr", None): n.lineno for n in ast.walk(submit) if isinstance(n, ast.Call)}
        self.assertLess(lines["reserve"], lines["_new_c1_order"])
        self.assertLess(lines["_new_flatten_order"], lines["submit_order"])

    def test_forbidden_calls_absent(self):
        forbidden = {"close_position", "close_all_positions", "modify_order", "submit_order_list", "market",
                     "placeOrder", "cancelOrder", "reqGlobalCancel", "exerciseOptions", "place_order",
                     "cancel_all_orders_for", "market_to_limit", "stop_market", "stop_limit", "bracket"}
        found = {n.func.attr for n in ast.walk(self.tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in forbidden}
        self.assertEqual(found, set())

    def test_no_heavy_imports_at_module_level(self):
        for node in self.tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
                self.assertFalse(any(n.startswith(("nautilus_trader", "ibapi")) for n in names), names)


def _nautilus_available():
    try:
        import nautilus_trader  # noqa: F401

        return nautilus_trader.__version__ == "1.231.0"
    except Exception:
        return False


@unittest.skipUnless(_nautilus_available(), "needs nautilus_trader 1.231.0 (synthetic backtest venue)")
class NautilusBacktestFlow(unittest.TestCase):
    """Runs the harness strategy in a 1.231.0 BacktestEngine against a simulated ARCA venue.
    This checks the strategy's use of the Nautilus API and its cleanup logic; it is not IBKR."""

    def _engine(self, rate=None, seconds=120):
        from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
        from nautilus_trader.config import LoggingConfig, RiskEngineConfig
        from nautilus_trader.model.currencies import USD
        from nautilus_trader.model.data import QuoteTick
        from nautilus_trader.model.enums import AccountType, OmsType
        from nautilus_trader.model.identifiers import Venue
        from nautilus_trader.model.objects import Money, Price, Quantity
        from nautilus_trader.test_kit.providers import TestInstrumentProvider

        eng = BacktestEngine(BacktestEngineConfig(
            trader_id="BACKTESTER-001", logging=LoggingConfig(bypass_logging=True),
            risk_engine=RiskEngineConfig(max_order_submit_rate=rate or PLAN["bounds"]["max_order_submit_rate"])))
        eng.add_venue(venue=Venue("ARCA"), oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
                      base_currency=USD, starting_balances=[Money(100_000, USD)])
        inst = TestInstrumentProvider.equity(symbol="SPY", venue="ARCA")
        eng.add_instrument(inst)
        t0 = 1_790_000_000_000_000_000
        eng.add_data([QuoteTick(inst.id, Price(600.00, 2), Price(600.02, 2), Quantity.from_int(100),
                                Quantity.from_int(100), t0 + i * 500_000_000, t0 + i * 500_000_000)
                      for i in range(seconds * 2)])
        return eng

    def simulate(self, strategy_cls=None, seconds=120, plan=None):
        from nautilus_trader.config import StrategyConfig

        eng = self._engine(seconds=seconds)
        ctx = RUN.RunContext(plan or PLAN, "NTP-SIM")
        stops = []
        strategy = (strategy_cls or RUN.build_strategy_class())(StrategyConfig(order_id_tag="001"), ctx, stops.append)
        eng.add_strategy(strategy)
        try:
            eng.run()
            self.statuses = {o.client_order_id.value: o.status_string() for o in strategy.cache.orders()}
            self.order_tags = {o.client_order_id.value: o.tags for o in strategy.cache.orders()}
        finally:
            eng.dispose()
        return ctx, stops

    def test_after_hours_plan_tags_every_order_outside_rth(self):
        self.simulate(plan=RUN.load_plan(RUN.HERE / "plan-post.json"))
        self.assertTrue(self.order_tags)
        for cid, tags in self.order_tags.items():
            with self.subTest(cid=cid):
                self.assertEqual(len(tags), 1)
                self.assertTrue(tags[0].startswith("IBOrderTags:"))
                self.assertIs(json.loads(tags[0].removeprefix("IBOrderTags:"))["outsideRth"], True)
        self.simulate()
        self.assertTrue(self.order_tags)
        self.assertTrue(all(not tags for tags in self.order_tags.values()))

    def _submit_times(self, ctx):
        orders = [o for c in RUN.CASE_IDS for o in ctx.cases[c]["orders"]] + ctx.cleanup_orders
        return sorted(datetime.fromisoformat(o["created_at"]).timestamp() for o in orders)

    def test_submit_rate_throttle_denies_only_the_old_rate(self):
        """Two submits 0.5 s apart through the 1.231.0 RiskEngine: the reviewed '1/00:00:01' denies
        the second; the plan's rate does not."""
        from nautilus_trader.config import StrategyConfig
        from nautilus_trader.model.enums import OrderSide, TimeInForce
        from nautilus_trader.model.events import OrderDenied
        from nautilus_trader.model.identifiers import InstrumentId
        from nautilus_trader.model.objects import Price, Quantity
        from nautilus_trader.trading.strategy import Strategy

        class TwoSubmits(Strategy):
            def __init__(self):
                super().__init__(StrategyConfig(order_id_tag="002"))
                self.denied, self.sent = [], 0

            def on_start(self):
                self.subscribe_quote_ticks(InstrumentId.from_str("SPY.ARCA"))

            def on_quote_tick(self, tick):
                if self.sent < 2:
                    self.sent += 1
                    self.submit_order(self.order_factory.limit(
                        instrument_id=tick.instrument_id, order_side=OrderSide.BUY, quantity=Quantity.from_int(1),
                        price=Price(300.00, 2), time_in_force=TimeInForce.DAY))

            def on_order_event(self, event):
                if isinstance(event, OrderDenied):
                    self.denied.append(str(event.reason))

        results = {}
        for rate in ("1/00:00:01", PLAN["bounds"]["max_order_submit_rate"]):
            eng = self._engine(rate=rate, seconds=5)
            strategy = TwoSubmits()
            eng.add_strategy(strategy)
            try:
                eng.run()
            finally:
                eng.dispose()
            results[rate] = (strategy.sent, strategy.denied)
        self.assertEqual(results["1/00:00:01"], (2, ["Exceeded MAX_ORDER_SUBMIT_RATE"]))
        self.assertEqual(results[PLAN["bounds"]["max_order_submit_rate"]], (2, []))

    def test_happy_path(self):
        ctx, stops = self.simulate()
        self.assertEqual([ctx.cases[c]["outcome"] for c in RUN.CASE_IDS], ["passed"] * 4)
        self.assertEqual(stops, ["strategy:cases_complete"])
        self.assertEqual(ctx.budget.used, 3)
        self.assertEqual(ctx.net_qty, 0)
        self.assertEqual([f["side"] for f in ctx.fills], ["BUY", "SELL"])
        self.assertEqual(ctx.cases["C2"]["events"][-1]["type"], "OrderCanceled")
        self.assertTrue(ctx.cases["C1"]["venue_order_id_present"])
        self.assertIsNotNone(ctx.roundtrip["nautilus_realized_pnl"])
        self.assertEqual(RUN.final_status(ctx, {"status": "passed"}), "passed")
        times = self._submit_times(ctx)
        self.assertEqual(len(times), 3)
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(g >= PLAN["bounds"]["min_submit_spacing_seconds"] for g in gaps), gaps)
        self.assertEqual((ctx.duplicates, ctx.unconfirmed), ([], []))

    def test_duplicate_c1_cancel_is_ignored(self):
        from nautilus_trader.model.events import OrderCanceled

        base = RUN.build_strategy_class()

        class DoubleCancelReport(base):
            def on_order_event(self, event):
                super().on_order_event(event)
                if isinstance(event, OrderCanceled) and event.client_order_id.value.endswith("-C1"):
                    super().on_order_event(event)  # the second (error 202 / orderStatus) report

        ctx, stops = self.simulate(DoubleCancelReport)
        self.assertEqual([ctx.cases[c]["outcome"] for c in RUN.CASE_IDS], ["passed"] * 4)
        self.assertEqual(stops, ["strategy:cases_complete"])
        self.assertEqual([(d["type"], d["first"]) for d in ctx.duplicates], [("OrderCanceled", "OrderCanceled")])
        self.assertTrue(ctx.cases["C2"]["events"][-1]["duplicate_ignored"])

    def test_engine_generated_cancel_never_passes_c2(self):
        from nautilus_trader.core.uuid import UUID4
        from nautilus_trader.model.events import OrderCanceled

        base = RUN.build_strategy_class()

        class SynthesizedCancel(base):
            def _send_cancel(self, order, where, action="cancel"):
                if where != "C2":
                    return super()._send_cancel(order, where, action)
                # What _resolve_inflight_order publishes: reconciliation=True, no IB callback.
                self.on_order_event(OrderCanceled(
                    trader_id=order.trader_id, strategy_id=order.strategy_id, instrument_id=order.instrument_id,
                    client_order_id=order.client_order_id, venue_order_id=order.venue_order_id,
                    account_id=order.account_id, event_id=UUID4(), ts_event=self.clock.timestamp_ns(),
                    ts_init=self.clock.timestamp_ns(), reconciliation=True))

        ctx, stops = self.simulate(SynthesizedCancel)
        self.assertEqual(ctx.cases["C2"]["outcome"], "incomplete")
        self.assertEqual(ctx.cases["C2"]["reason"], "C1_unconfirmed_OrderCanceled")
        self.assertEqual(ctx.cases["C3"]["outcome"], "not_run")
        self.assertEqual(ctx.budget.used, 1)  # no C3 and no flatten order
        self.assertEqual(stops, ["strategy:cleanup_unconfirmed_order_state"])
        self.assertEqual(len(ctx.unconfirmed), 1)
        # The still-open C1 order was cancelled for real by cleanup.
        self.assertEqual(self.statuses[ctx.client_order_id("C1")], "CANCELED")
        self.assertNotEqual(RUN.final_status(ctx, {"status": "passed"}), "passed")

    def _deadline_with_resting_flatten(self, drop_finish_cancel):
        base = RUN.build_strategy_class()

        class AbortAtC4(base):
            dropped = []

            def _begin(self, cid):
                if cid == "C4":
                    self.abort("injected_signal", kind="incomplete")
                else:
                    super()._begin(cid)

            def cancel_order(self, order, client_id=None, params=None):
                # Simulates the adapter dropping a cancel (execution.py _cancel_order logs only when
                # the IB order id cannot be resolved): the order stays open at the venue.
                if drop_finish_cancel and order.client_order_id.value.endswith("-X1") and not self.dropped:
                    self.dropped.append(self.ctx.finished)
                    return
                super().cancel_order(order, client_id, params)

        plan = copy.deepcopy(PLAN)
        plan["timeouts"]["cleanup_seconds"] = 6  # shorter than flatten_fill_wait_seconds (10)
        original = RUN.marketable_sell_price
        RUN.marketable_sell_price = lambda bid, offset=0.05: RUN.ceil_cent(RUN._dec(bid) + 1)  # rests, never fills
        try:
            ctx, stops = self.simulate(AbortAtC4, plan=plan)
        finally:
            RUN.marketable_sell_price = original
        return ctx, stops, AbortAtC4.dropped

    def test_cleanup_deadline_cancels_open_flatten(self):
        ctx, stops, _ = self._deadline_with_resting_flatten(drop_finish_cancel=False)
        self.assertEqual(stops, ["strategy:cleanup_deadline"])
        self.assertEqual(ctx.cleanup["flatten_orders"], 1)
        x1 = ctx.client_order_id("X1")
        # The flatten was still inside its fill window at the deadline; finish cancels it anyway.
        self.assertEqual([r["where"] for r in ctx.cancel_requests if r["client_order_id"] == x1],
                         ["finish:cleanup_deadline"])
        self.assertEqual(self.statuses[x1], "CANCELED")
        self.assertEqual(ctx.net_qty, 1)  # left long; the independent check would report cleanup_required

    def test_on_stop_cancels_after_finish_when_a_cancel_was_dropped(self):
        ctx, stops, dropped = self._deadline_with_resting_flatten(drop_finish_cancel=True)
        x1 = ctx.client_order_id("X1")
        self.assertEqual(dropped, [True])  # the finish-time cancel was dropped after ctx.finished was set
        self.assertEqual([r["where"] for r in ctx.cancel_requests if r["client_order_id"] == x1],
                         ["finish:cleanup_deadline", "on_stop"])
        self.assertEqual(self.statuses[x1], "CANCELED")

    def test_cancel_rejected_is_resent_after_interval(self):
        from nautilus_trader.core.uuid import UUID4
        from nautilus_trader.model.events import OrderCancelRejected

        base = RUN.build_strategy_class()

        class FirstCancelRejected(base):
            rejected = 0

            def cancel_order(self, order, client_id=None, params=None):
                if order.client_order_id.value.endswith("-C3") and not self.rejected:
                    self.rejected += 1
                    self.on_order_event(OrderCancelRejected(
                        trader_id=order.trader_id, strategy_id=order.strategy_id, instrument_id=order.instrument_id,
                        client_order_id=order.client_order_id, venue_order_id=order.venue_order_id,
                        account_id=order.account_id, reason="simulated reject", event_id=UUID4(),
                        ts_event=self.clock.timestamp_ns(), ts_init=self.clock.timestamp_ns()))
                    return
                super().cancel_order(order, client_id, params)

        original = RUN.marketable_buy_price
        RUN.marketable_buy_price = lambda ask, qty, cap, off: RUN.floor_cent(RUN._dec(ask) - 1)
        try:
            ctx, stops = self.simulate(FirstCancelRejected)
        finally:
            RUN.marketable_buy_price = original
        c3 = [r for r in ctx.cancel_requests if r["client_order_id"] == ctx.client_order_id("C3")]
        self.assertEqual([r["attempt"] for r in c3], [1, 2])
        gap = datetime.fromisoformat(c3[1]["at"]).timestamp() - datetime.fromisoformat(c3[0]["at"]).timestamp()
        self.assertGreaterEqual(gap, PLAN["timeouts"]["recancel_interval_seconds"])
        self.assertEqual(stops, ["strategy:cleanup_flat"])
        self.assertEqual(self.statuses[ctx.client_order_id("C3")], "CANCELED")

    def test_denied_flatten_waits_before_retry(self):
        base = RUN.build_strategy_class()

        class DenyFirstFlatten(base):
            def _begin(self, cid):
                if cid == "C4":
                    self.abort("injected_signal", kind="incomplete")
                else:
                    super()._begin(cid)

            def submit_order(self, order, *args, **kwargs):
                if order.client_order_id.value.endswith("-X1"):
                    # A denial like the risk engine's: the order closes without reaching the venue.
                    from nautilus_trader.model.events import OrderDenied
                    from nautilus_trader.core.uuid import UUID4

                    self.cache.add_order(order)
                    denied = OrderDenied(trader_id=order.trader_id, strategy_id=order.strategy_id,
                                         instrument_id=order.instrument_id, client_order_id=order.client_order_id,
                                         reason="Exceeded MAX_ORDER_SUBMIT_RATE", event_id=UUID4(),
                                         ts_init=self.clock.timestamp_ns())
                    order.apply(denied)
                    self.cache.update_order(order)
                    self.on_order_event(denied)
                    return
                super().submit_order(order, *args, **kwargs)

        ctx, stops = self.simulate(DenyFirstFlatten)
        self.assertEqual(ctx.net_qty, 0)
        self.assertEqual(ctx.cleanup["flatten_orders"], 2)
        self.assertEqual(stops, ["strategy:cleanup_flat"])
        times = {o["client_order_id"].rsplit("-", 1)[1]: datetime.fromisoformat(o["created_at"]).timestamp()
                 for o in ctx.cleanup_orders}
        self.assertGreaterEqual(times["X2"] - times["X1"], PLAN["timeouts"]["flatten_retry_delay_seconds"])
        reasons = [e.get("reason") for e in ctx.cleanup_events if e["type"] == "OrderDenied"]
        self.assertEqual(reasons, ["Exceeded MAX_ORDER_SUBMIT_RATE"])

    def test_abort_after_fill_flattens_once(self):
        base = RUN.build_strategy_class()

        class AbortAtC4(base):
            def _begin(self, cid):
                if cid == "C4":
                    self.abort("injected_signal", kind="incomplete")
                else:
                    super()._begin(cid)

        ctx, stops = self.simulate(AbortAtC4)
        self.assertEqual(ctx.net_qty, 0)
        self.assertEqual(ctx.cleanup["flatten_orders"], 1)
        self.assertEqual([f["side"] for f in ctx.fills], ["BUY", "SELL"])
        self.assertEqual(stops, ["strategy:cleanup_flat"])
        self.assertEqual(RUN.final_status(ctx, {"status": "passed"}), "incomplete")

    def test_unfilled_buy_times_out_and_is_canceled(self):
        original = RUN.marketable_buy_price
        RUN.marketable_buy_price = lambda ask, qty, cap, off: RUN.floor_cent(RUN._dec(ask) - 1)
        try:
            ctx, stops = self.simulate()
        finally:
            RUN.marketable_buy_price = original
        self.assertEqual(ctx.cases["C3"]["outcome"], "incomplete")
        self.assertEqual(ctx.cases["C3"]["reason"], "C3_step_timeout")
        self.assertEqual(ctx.cleanup["cancels_requested"], 1)
        self.assertEqual((ctx.net_qty, ctx.fills), (0, []))
        self.assertEqual(stops, ["strategy:cleanup_flat"])

    def test_node_config_matches_plan(self):
        cfg = RUN.build_node_config(PLAN, FAKE_ACCOUNT, 4002)
        ex, da = cfg.exec_clients["INTERACTIVE_BROKERS"], cfg.data_clients["INTERACTIVE_BROKERS"]
        self.assertEqual((ex.ibg_host, ex.ibg_port, ex.ibg_client_id, ex.dockerized_gateway), ("127.0.0.1", 4002, 91, None))
        self.assertEqual((da.ibg_client_id, da.dockerized_gateway), (91, None))
        self.assertEqual(cfg.timeout_connection, 60.0)
        self.assertEqual(cfg.risk_engine.max_order_submit_rate, "100/00:00:01")
        x = cfg.exec_engine
        self.assertEqual((x.inflight_check_interval_ms, x.inflight_check_threshold_ms, x.inflight_check_retries),
                         (2000, 5000, 100))
        self.assertGreater(x.inflight_check_threshold_ms * x.inflight_check_retries / 1000,
                           PLAN["timeouts"]["overall_deadline_seconds"])
        self.assertEqual(cfg.timeout_post_stop, 5.0)



@unittest.skipUnless(_nautilus_available() and hasattr(signal, "SIGHUP"), "needs nautilus_trader 1.231.0 and SIGHUP")
class RunNodeSignalWiring(unittest.TestCase):
    """run_node with a stand-in TradingNode (patched into nautilus_trader.live.node; no IB client
    is built or connected): a real SIGHUP reaches the harness handler, marks the not-yet-started
    run finished, and a second SIGHUP forces the hung stop so run_node returns."""

    def setUp(self):
        saved = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        self.addCleanup(lambda: [signal.signal(s, h) for s, h in saved.items()])
        self.stray = []
        # Without the harness handler a SIGHUP lands here instead of ending the test process.
        signal.signal(signal.SIGHUP, lambda signum, frame: self.stray.append(signum))

    def test_sighup_twice_before_start(self):
        from unittest import mock

        import nautilus_trader.live.node as live_node

        class StandInNode(_FakeNode):
            def __init__(self, config):
                super().__init__()
                self.trader = SimpleNamespace(add_strategy=lambda s: None)

            def add_data_client_factory(self, *a):
                pass

            add_exec_client_factory = add_data_client_factory

            def build(self):
                pass

            def get_event_loop(self):
                return self.loop

            def run(self):
                self.elapsed = super().run([(0.05, lambda: os.kill(os.getpid(), signal.SIGHUP)),
                                            (0.3, lambda: os.kill(os.getpid(), signal.SIGHUP))])

            def dispose(self):
                pass

        ctx = RUN.RunContext(PLAN, "NTP-T")
        nodes = []
        with mock.patch.object(live_node, "TradingNode", lambda config: nodes.append(StandInNode(config)) or nodes[-1]):
            far = time.monotonic() + 3600
            RUN.run_node(PLAN, FAKE_ACCOUNT, 4002, ctx, abort_at=far, hard_stop_at=far, window_end=None)
        self.assertEqual(self.stray, [])
        self.assertEqual([n for n in ctx.notes if n.startswith("received")], ["received SIGHUP"] * 2)
        self.assertTrue(ctx.finished)
        self.assertFalse(ctx.started)
        self.assertEqual(ctx.node["forced_stop_by"], "signal_SIGHUP")
        self.assertLess(nodes[0].elapsed, 2.0)
        # After the node phase SIGHUP raises KeyboardInterrupt so the flat proof and receipt still run.
        self.assertIs(signal.getsignal(signal.SIGHUP), RUN._raise_interrupt)


if __name__ == "__main__":
    unittest.main()
