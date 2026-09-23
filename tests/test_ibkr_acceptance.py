"""Offline tests for the IBKR read-only acceptance probes.

Synthetic boundary fixtures only: nothing here connects to TWS or IB Gateway,
and neither ibapi nor NautilusTrader is required. They do not establish the
ibkr-local-acceptance gate.
"""
import ast
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/engine-nautilus/ibkr-acceptance"
ORDER_CALLS = {"placeOrder", "cancelOrder", "reqGlobalCancel", "exerciseOptions", "submit_order",
               "cancel_order", "modify_order", "cancel_all_orders"}
RAW_ACCOUNT = re.compile(r"\b(?:D?[UF]|I)\d{5,}\b")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IBAPI = _load("ibkr_ibapi_probe", SOURCE / "ibapi_probe.py")
NAUTILUS = _load("ibkr_nautilus_probe", SOURCE / "nautilus_probe.py")
ALL_DONE = {k: True for k in IBAPI.REQUESTS}


class Bar:
    def __init__(self, date):
        self.date = date


class Details:
    class contract:
        conId, secType, currency, exchange, primaryExchange = 756733, "STK", "USD", "SMART", "ARCA"
    longName, tradingHours = "SPY", "20260923:0930-20260923:1600"


class FakeProbe(IBAPI.ProbeState):
    """Drives ProbeState callbacks synchronously in place of the ibapi client."""

    def __init__(self, accounts="DU1234567", connected=True, positions=0, finish_positions=True, switch_to=None):
        super().__init__()
        self.switch_to = switch_to
        self.accounts, self.connected, self.n_positions = accounts, connected, positions
        self.finish_positions, self.calls, self.disconnected = finish_positions, [], False
        self.client_version = "fake"

    def connect(self, host, port, client_id):
        if self.connected == "raises":
            raise ConnectionRefusedError(111, "Connection refused to 127.0.0.1:4002")
        if self.connected:
            self.managedAccounts(self.accounts)

    def run(self):
        pass

    def isConnected(self):
        return self.connected is True

    def disconnect(self):
        self.disconnected = True

    def __getattr__(self, name):
        if not name.startswith(("req", "cancel")):
            raise AttributeError(name)

        def call(*args):
            self.calls.append(name)
            if name == "reqCurrentTime":
                self.currentTime(int(__import__("time").time()))
            elif name == "reqPositions":
                if self.switch_to:
                    self.managedAccounts(self.switch_to)
                for _ in range(self.n_positions):
                    self.position("DU1234567", None, 1, 1.0)
                if self.finish_positions:
                    self.positionEnd()
            elif name == "reqAllOpenOrders":
                self.openOrderEnd()
            elif name == "reqAccountSummary":
                self.accountSummary(9001, "DU1234567", "NetLiquidation", "1000123.45", "USD")
                self.accountSummaryEnd(9001)
            elif name == "reqContractDetails":
                self.contractDetails(9002, Details)
                self.contractDetailsEnd(9002)
            elif name == "reqMktData":
                self.marketDataType(9003, 1)
                self.tickPrice(9003, 1, 772.64, None)
                self.tickString(9003, 45, str(int(__import__("time").time()) - 5))
                self.tickSnapshotEnd(9003)
            elif name == "reqHistoricalData":
                self.historicalData(9004, Bar("1790083800"))
                self.historicalDataEnd(9004, "", "")
        return call


def run_main(probe, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "r.json"
        code = IBAPI.main(["--receipt", str(path), "--deadline-seconds", "0.5", *extra],
                          probe_factory=lambda: probe, contract_factory=lambda: None)
        return code, json.loads(path.read_text())


class AccountScopeAndPrivacy(unittest.TestCase):
    def test_only_all_paper_accounts_pass(self):
        self.assertEqual(IBAPI.account_scope("DU1234567,"), (1, True))
        self.assertEqual(IBAPI.account_scope("DU1234567,DU7654321"), (2, True))
        self.assertEqual(IBAPI.account_scope("DU1234567,U7654321"), (2, False))
        self.assertEqual(IBAPI.account_scope(""), (0, False))

    def test_callbacks_keep_no_account_id_or_balance(self):
        state = IBAPI.ProbeState()
        state.managedAccounts("DU1234567,")
        state.accountSummary(9001, "DU1234567", "NetLiquidation", "1000123.45", "USD")
        state.accountSummary(9001, "DU1234567", "AccountType", "INDIVIDUAL", "")
        state.error(9001, 0, 321, "Error validating request for account DU1234567 and F7654321")
        dumped = json.dumps(state.r)
        self.assertIsNone(RAW_ACCOUNT.search(dumped))
        self.assertNotIn("1000123.45", dumped)
        self.assertIn("<account-id>", state.r["errors"][0]["text"])
        self.assertEqual(state.r["summary_tags"], ["NetLiquidation", "AccountType"])


class ErrorRoutingAndVerdict(unittest.TestCase):
    def passing_state(self):
        state = IBAPI.ProbeState()
        state.managedAccounts("DU1234567")
        state.currentTime(1790169413)
        state.r.update(spy_contract={"conId": 756733}, quote_age_s=12.0)
        state.tickPrice(9003, 1, 772.64, None)
        state.historicalData(9004, Bar("1789997400"))
        return state

    def test_farm_notices_are_info_and_data_refusals_are_errors(self):
        state = IBAPI.ProbeState()
        for code in (2104, 2106, 2158, 10167):
            state.error(-1, 0, code, "notice")
        for code in (2188, 162, 10197):
            state.error(9004, 0, code, "refusal")
        self.assertEqual([e["code"] for e in state.r["info"]], [2104, 2106, 2158, 10167])
        self.assertEqual([e["code"] for e in state.r["errors"]], [2188, 162, 10197])

    def test_passed_needs_every_request_zero_state_and_a_fresh_quote(self):
        state = self.passing_state()
        self.assertEqual(IBAPI.verdict(state.r, ALL_DONE, 900), "passed")
        self.assertEqual(IBAPI.verdict(state.r, {**ALL_DONE, "positions": False}, 900), "incomplete")
        self.assertEqual(IBAPI.verdict(state.r, {**ALL_DONE, "orders": False}, 900), "incomplete")
        self.assertEqual(IBAPI.verdict({**state.r, "quote_age_s": 901.0}, ALL_DONE, 900), "incomplete")
        self.assertEqual(IBAPI.verdict({**state.r, "quote_age_s": None}, ALL_DONE, 900), "incomplete")
        self.assertEqual(IBAPI.verdict({**state.r, "quote_age_s": -0.4}, ALL_DONE, 900), "passed")
        self.assertEqual(IBAPI.verdict({**state.r, "quote_age_s": -2.5}, ALL_DONE, 900), "incomplete")
        self.assertEqual(IBAPI.verdict({**state.r, "positions": 1}, ALL_DONE, 900), "blocked_existing_state")
        self.assertEqual(IBAPI.verdict({**state.r, "open_orders": 2}, ALL_DONE, 900), "blocked_existing_state")
        self.assertEqual(IBAPI.verdict({**state.r, "paper_accounts": False}, ALL_DONE, 900), "refused_not_paper_account")

    def test_quote_age_uses_the_trade_timestamp_and_server_offset(self):
        state = IBAPI.ProbeState()
        self.assertIsNone(IBAPI.quote_age(state.r, 1000.0))
        state.tickString(9003, 45, "990")
        state.tickString(9003, 45, "not-a-number")
        state.r["server_minus_local_s"] = -0.5
        self.assertEqual(IBAPI.quote_age(state.r, 1000.0), 9.5)
        delayed = IBAPI.ProbeState()
        delayed.tickString(9003, 88, "100")
        self.assertEqual(IBAPI.quote_age(delayed.r, 1000.0), 900.0)

    def test_plan_declares_the_quote_age_limit(self):
        self.assertEqual(IBAPI.max_quote_age(), 900.0)


class IbapiMain(unittest.TestCase):
    def test_happy_path_passes_with_zero_existing_state(self):
        probe = FakeProbe()
        code, receipt = run_main(probe)
        self.assertEqual((code, receipt["status"]), (0, "passed"))
        self.assertEqual(receipt["existing_state"], {"positions": 0, "open_orders": 0})
        self.assertTrue(probe.disconnected)
        self.assertIsNone(RAW_ACCOUNT.search(json.dumps(receipt)))

    def test_non_paper_account_disconnects_before_any_read(self):
        probe = FakeProbe(accounts="U1234567")
        code, receipt = run_main(probe)
        self.assertEqual((code, receipt["status"]), (3, "refused_not_paper_account"))
        self.assertEqual(probe.calls, [])
        self.assertTrue(probe.disconnected)

    def test_a_later_non_paper_account_callback_stops_all_further_reads(self):
        probe = FakeProbe(switch_to="U7654321")
        code, receipt = run_main(probe)
        self.assertEqual((code, receipt["status"]), (3, "refused_not_paper_account"))
        self.assertEqual(probe.calls, ["reqCurrentTime", "reqPositions", "cancelPositions"])
        self.assertTrue(probe.disconnected)
        probe = FakeProbe(switch_to="DU7654321")
        self.assertEqual(run_main(probe)[0], 0)

    def test_not_connected(self):
        code, receipt = run_main(FakeProbe(connected=False))
        self.assertEqual((code, receipt["status"]), (2, "not_connected"))

    def test_socket_error_from_connect_is_not_connected(self):
        code, receipt = run_main(FakeProbe(connected="raises"))
        self.assertEqual((code, receipt["status"]), (2, "not_connected"))
        self.assertEqual(receipt["observed"]["errors"][0]["text"], "ConnectionRefusedError: [Errno 111] Connection refused to <ip>")

    def test_error_text_redacts_ids_endpoints_and_paths(self):
        self.assertEqual(IBAPI.redact("acct DU1234567 at 192.168.1.5:4002 log /opt/ibc/logs/x.log or C:\\Jts\\x.log"),
                         "acct <account-id> at <ip> log <path> or <path>")

    def test_existing_position_blocks(self):
        code, receipt = run_main(FakeProbe(positions=1))
        self.assertEqual((code, receipt["status"]), (4, "blocked_existing_state"))

    def test_unfinished_positions_snapshot_is_incomplete_not_zero(self):
        code, receipt = run_main(FakeProbe(finish_positions=False))
        self.assertEqual((code, receipt["status"]), (1, "incomplete"))
        self.assertIsNone(receipt["existing_state"]["positions"])

    def test_live_port_is_refused_before_connecting(self):
        probe = FakeProbe()
        code, receipt = run_main(probe, "--port", "7496")
        self.assertEqual((code, receipt["status"]), (3, "refused_not_paper_port"))
        self.assertNotIn("observed", receipt)
        self.assertFalse(probe.disconnected)


class GateReceiptPath(unittest.TestCase):
    def test_probes_refuse_to_write_the_gate_receipt(self):
        gate = str(SOURCE / "receipt.json")
        self.assertEqual(IBAPI.main(["--receipt", gate], probe_factory=FakeProbe), 3)
        self.assertEqual(NAUTILUS.main(["--ibapi-receipt", gate, "--receipt", gate]), 3)
        self.assertFalse((SOURCE / "receipt.json").exists())


class NautilusPrecondition(unittest.TestCase):
    now = datetime(2026, 9, 23, 14, 13, 30, tzinfo=timezone.utc)
    good = {"client": "ibapi (official IB API client)", "status": "passed", "exit_code": 0, "host": "127.0.0.1",
            "port": 4002, "generated_at": "2026-09-23T14:13:00+00:00", "observed": {"paper_accounts": True}}

    def pre(self, receipt, host="127.0.0.1", port=4002, now=None):
        return NAUTILUS.paper_precondition(receipt, host, port, now or self.now, 300)

    def test_fresh_passed_paper_receipt_for_the_same_endpoint(self):
        self.assertIsNone(self.pre(self.good))
        self.assertEqual(self.pre(self.good, port=4001), "refused_not_paper_port")
        self.assertEqual(self.pre(self.good, port=7497), "refused_ibapi_receipt_for_other_endpoint")
        self.assertEqual(self.pre(self.good, host="10.0.0.2"), "refused_ibapi_receipt_for_other_endpoint")
        for change in ({"status": "incomplete"}, {"exit_code": 1}, {"client": "other"},
                       {"observed": {"paper_accounts": False}}, {"generated_at": "not-a-time"}):
            self.assertEqual(self.pre({**self.good, **change}), "refused_no_passed_paper_ibapi_receipt", change)

    def test_stale_or_future_receipt_is_refused(self):
        self.assertEqual(self.pre(self.good, now=self.now + timedelta(minutes=6)), "refused_stale_ibapi_receipt")
        self.assertEqual(self.pre(self.good, now=self.now - timedelta(minutes=2)), "refused_stale_ibapi_receipt")

    def test_the_committed_ibapi_evidence_is_stale_now(self):
        for path in sorted((SOURCE / "evidence").glob("ibapi-readonly-*.json")):
            receipt = json.loads(path.read_text())
            later = datetime.fromisoformat(receipt["generated_at"]) + timedelta(hours=1)
            self.assertEqual(self.pre(receipt, now=later), "refused_stale_ibapi_receipt", path.name)

    def test_missing_or_malformed_receipt_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("[1, 2")
            for ib in (Path(tmp) / "missing.json", bad):
                out = Path(tmp) / "n.json"
                self.assertEqual(NAUTILUS.main(["--ibapi-receipt", str(ib), "--receipt", str(out)]), 3)
                self.assertEqual(json.loads(out.read_text())["status"], "refused_no_passed_paper_ibapi_receipt")

    def test_unreachable_gateway_is_not_connected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ib = Path(tmp) / "ibapi.json"
            ib.write_text(json.dumps({**self.good, "generated_at": datetime.now(timezone.utc).isoformat()}))
            out = Path(tmp) / "n.json"
            with mock.patch.object(NAUTILUS, "tcp_reachable", return_value=False):
                self.assertEqual(NAUTILUS.main(["--ibapi-receipt", str(ib), "--receipt", str(out)]), 2)
            self.assertEqual(json.loads(out.read_text())["status"], "not_connected")

    def test_bar_window_ends_on_the_previous_day(self):
        self.assertEqual(NAUTILUS.default_end(self.now), datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc))


class ReadOnlySource(unittest.TestCase):
    def test_no_probe_references_an_order_method(self):
        # Any reference counts, not only direct calls: the ibapi probe dispatches
        # requests through a table of bound methods.
        for name in ("ibapi_probe.py", "nautilus_probe.py"):
            tree = ast.parse((SOURCE / name).read_text())
            names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
            names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            self.assertFalse(names & ORDER_CALLS, name)

    def test_order_reference_check_catches_table_dispatch(self):
        tree = ast.parse('steps = (("orders", 10, p.reqGlobalCancel, None),)')
        self.assertIn("reqGlobalCancel", {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & ORDER_CALLS)

    def test_published_evidence_holds_no_account_id_or_home_path(self):
        paths = sorted((SOURCE / "evidence").rglob("*.json")) + sorted((ROOT / "evidence/receipts").glob("ibkr-*.json"))
        self.assertTrue(paths)
        for path in paths:
            text = path.read_text()
            self.assertIsNone(RAW_ACCOUNT.search(text), path.name)
            self.assertNotIn("/home/", text, path.name)


if __name__ == "__main__":
    unittest.main()
