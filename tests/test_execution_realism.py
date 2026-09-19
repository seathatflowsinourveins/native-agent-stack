import copy
import importlib.util
import json
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("execution_analysis", ROOT / "blueprints/us-equities/execution-realism/analyze.py")
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class ExecutionAccountingTests(unittest.TestCase):
    def fixture(self):
        summary = {"state": {"Status": "Completed", "RuntimeError": ""},
                   "statistics": {"Total Orders": "2", "End Equity": "100198.00", "Total Fees": "$2.00"}}
        events = [{"status": "filled", "orderId": 1, "time": 1,
                   "symbolValue": "SPY", "fillPriceCurrency": "USD",
                   "fillPrice": 100, "fillQuantity": 100,
                   "orderFeeAmount": 1, "orderFeeCurrency": "USD"},
                  {"status": "filled", "orderId": 2, "time": 2,
                   "symbolValue": "SPY", "fillPriceCurrency": "USD",
                   "fillPrice": 102, "fillQuantity": -100,
                   "orderFeeAmount": 1, "orderFeeCurrency": "USD"}]
        return summary, events

    def test_exact_cash_reconciliation(self):
        result = analysis.summarize(*self.fixture())
        self.assertEqual(result["cash_pnl_usd"], "198")
        self.assertEqual(result["net_quantity"], "0")

    def test_native_runtime_error_rejected_even_if_completed(self):
        summary, events = self.fixture()
        summary["state"]["RuntimeError"] = "engine failed"
        with self.assertRaises(ValueError):
            analysis.summarize(summary, events)

    def test_unbalanced_or_duplicate_fill_rejected(self):
        summary, events = self.fixture()
        for modified in [events[:1], events + [copy.deepcopy(events[1])]]:
            with self.assertRaises(ValueError):
                analysis.summarize(summary, modified)

    def test_cash_discrepancy_rejected(self):
        summary, events = self.fixture()
        summary["statistics"]["End Equity"] = "100199"
        with self.assertRaises(ValueError):
            analysis.summarize(summary, events)

    def test_fee_currency_rejected(self):
        summary, events = self.fixture()
        events[0]["orderFeeCurrency"] = "EUR"
        with self.assertRaises(ValueError):
            analysis.summarize(summary, events)

    def test_serialized_decimal_precision_is_preserved(self):
        summary, events = self.fixture()
        events[0]["fillPrice"] = json.loads("100.0000000000000001", parse_float=Decimal)
        result = analysis.summarize(summary, events)
        self.assertEqual(Decimal(result["cash_pnl_usd"]), Decimal("197.9999999999999900"))

    def test_installation_outputs_rejected_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lean, sdk = root / "lean", root / "sdk"
            lean.mkdir()
            sdk.mkdir()
            link = root / "linked-lean"
            link.symlink_to(lean, target_is_directory=True)
            for output in [lean / "new", sdk / "new", link / "new"]:
                result = subprocess.run([sys.executable, str(ROOT / "blueprints/us-equities/execution-realism/run.py"),
                                         "--lean-source", str(lean), "--dotnet", str(sdk / "dotnet"),
                                         "--out", str(output)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("outside accepted engine", result.stderr)
                self.assertFalse(output.exists())
