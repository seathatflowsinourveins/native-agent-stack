"""Offline tests for the IBKR read-only acceptance probes.

Synthetic boundary fixtures only: nothing here connects to TWS or IB Gateway,
and neither ibapi nor NautilusTrader is required. They do not establish the
ibkr-local-acceptance gate.
"""
import ast
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/engine-nautilus/ibkr-acceptance"
ORDER_CALLS = {"placeOrder", "cancelOrder", "reqGlobalCancel", "exerciseOptions", "submit_order",
               "cancel_order", "modify_order", "cancel_all_orders"}
RAW_ACCOUNT = re.compile(r"\b[D]?U\d{5,}\b")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IBAPI = _load("ibkr_ibapi_probe", SOURCE / "ibapi_probe.py")
NAUTILUS = _load("ibkr_nautilus_probe", SOURCE / "nautilus_probe.py")


class Bar:
    def __init__(self, date):
        self.date = date


class AccountScope(unittest.TestCase):
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
        state.position("DU1234567", None, 0, 0.0)
        dumped = json.dumps(state.r)
        self.assertNotIn("1234567", dumped)
        self.assertNotIn("1000123.45", dumped)
        self.assertEqual(state.r["summary_tags"], ["NetLiquidation", "AccountType"])
        self.assertEqual((state.r["account_count"], state.r["paper_accounts"]), (1, True))
        self.assertEqual(state.r["positions"], 0)


class ErrorRoutingAndVerdict(unittest.TestCase):
    def test_farm_notices_are_info_and_data_refusals_are_errors(self):
        state = IBAPI.ProbeState()
        for code in (2104, 2106, 2158, 10167):
            state.error(-1, 0, code, "notice")
        for code in (2188, 162, 10197):
            state.error(9004, 0, code, "refusal")
        self.assertEqual([e["code"] for e in state.r["info"]], [2104, 2106, 2158, 10167])
        self.assertEqual([e["code"] for e in state.r["errors"]], [2188, 162, 10197])

    def test_passed_needs_contract_bars_and_server_time(self):
        state = IBAPI.ProbeState()
        self.assertEqual(IBAPI.verdict(state.r), "incomplete")
        state.currentTime(1790169413)
        state.r["spy_contract"] = {"conId": 756733}
        self.assertEqual(IBAPI.verdict(state.r), "incomplete")
        state.historicalData(9004, Bar("1789997400"))
        state.historicalDataEnd(9004, "", "")
        self.assertEqual(IBAPI.verdict(state.r), "passed")
        self.assertTrue(state.completed()["history"])
        self.assertFalse(state.completed()["summary"])

    def test_delayed_quote_ticks_are_named(self):
        state = IBAPI.ProbeState()
        state.marketDataType(9003, 3)
        state.tickPrice(9003, 66, 772.64, None)
        state.tickPrice(9003, 67, -1.0, None)
        self.assertEqual(state.r["market_data_type"], "DELAYED")
        self.assertEqual(state.r["spy_quote"]["delayed_bid"], 772.64)
        self.assertNotIn("delayed_ask", state.r["spy_quote"])


class Refusals(unittest.TestCase):
    def test_ibapi_probe_refuses_a_live_port_before_connecting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            self.assertEqual(IBAPI.main(["--port", "7496", "--receipt", str(path)]), 3)
            receipt = json.loads(path.read_text())
        self.assertEqual(receipt["status"], "refused_not_paper_port")
        self.assertNotIn("observed", receipt)

    def test_nautilus_precondition(self):
        good = {"status": "passed", "host": "127.0.0.1", "port": 4002, "observed": {"paper_accounts": True}}
        pre = NAUTILUS.paper_precondition
        self.assertIsNone(pre(good, "127.0.0.1", 4002))
        self.assertEqual(pre(good, "127.0.0.1", 4001), "refused_not_paper_port")
        self.assertEqual(pre({**good, "status": "incomplete"}, "127.0.0.1", 4002),
                         "refused_no_passed_paper_ibapi_receipt")
        self.assertEqual(pre({**good, "observed": {"paper_accounts": False}}, "127.0.0.1", 4002),
                         "refused_no_passed_paper_ibapi_receipt")
        self.assertEqual(pre(good, "127.0.0.1", 7497), "refused_ibapi_receipt_for_other_endpoint")
        self.assertEqual(pre(good, "10.0.0.2", 4002), "refused_ibapi_receipt_for_other_endpoint")

    def test_nautilus_probe_refuses_without_a_passed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            ib = Path(tmp) / "ibapi.json"
            ib.write_text(json.dumps({"status": "incomplete", "host": "127.0.0.1", "port": 4002,
                                      "observed": {"paper_accounts": True}}))
            out = Path(tmp) / "n.json"
            self.assertEqual(NAUTILUS.main(["--ibapi-receipt", str(ib), "--receipt", str(out)]), 3)
            self.assertEqual(json.loads(out.read_text())["status"], "refused_no_passed_paper_ibapi_receipt")

    def test_bar_window_ends_on_the_previous_day(self):
        now = datetime(2026, 9, 23, 13, 0, tzinfo=timezone.utc)
        self.assertEqual(NAUTILUS.default_end(now), datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc))


class ReadOnlySource(unittest.TestCase):
    def test_no_probe_calls_an_order_method(self):
        for name in ("ibapi_probe.py", "nautilus_probe.py"):
            tree = ast.parse((SOURCE / name).read_text())
            called = {node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                      for node in ast.walk(tree) if isinstance(node, ast.Call)}
            self.assertFalse(called & ORDER_CALLS, name)

    def test_retained_receipts_hold_no_account_id_or_home_path(self):
        for path in sorted((SOURCE / "evidence").glob("*.json")) if (SOURCE / "evidence").is_dir() else []:
            text = path.read_text()
            self.assertIsNone(RAW_ACCOUNT.search(text), path.name)
            self.assertNotIn("/home/", text, path.name)


if __name__ == "__main__":
    unittest.main()
