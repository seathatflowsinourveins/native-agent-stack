"""Boundary tests for actual native result reconciliation; no market simulator."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "blueprints/us-equities/historical-simulation/analysis.py"
SPEC = importlib.util.spec_from_file_location("historical_analysis", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HistoricalAnalysisTests(unittest.TestCase):
    def orders(self):
        return {str(i): {"quantity": q, "tag": reason, "type": 4}
                for i, q, reason in [(1, "1", "entry"), (2, "-1", "exit")]}

    def sample(self):
        summary = {"state": {"Status": "Completed", "RuntimeError": ""},
                   "statistics": {"End Equity": "100009.00", "Total Fees": "$2.00"}}
        events = [{"status": "filled", "orderId": i, "time": t, "symbolValue": "SPY",
                   "fillPriceCurrency": "USD", "orderFeeCurrency": "USD",
                   "fillQuantity": q, "fillPrice": p, "orderFeeAmount": "1"}
                  for i, t, q, p in [(1, 100, "1", "100"), (2, 200, "-1", "110")]]
        audit = [{"kind": "intent", "order_id": 1, "utc_seconds": 50, "reason": "entry"},
                 {"kind": "intent", "order_id": 2, "utc_seconds": 150, "reason": "exit"},
                 {"kind": "dividend", "amount": "1"},
                 {"kind": "mark", "equity": "100000", "gross": "0", "drawdown": "0", "margin_remaining": "100000"},
                 {"kind": "mark", "equity": "100009", "gross": "0", "drawdown": "0", "margin_remaining": "100009"},
                 {"kind": "final", "cash": "100009", "equity": "100009", "quantity": "0"}]
        return summary, events, audit

    def test_cash_includes_native_dividend(self):
        result = MODULE.summarize(*self.sample(), rejected=False, adaptive=False, orders=self.orders())
        self.assertEqual(result["dividends_usd"], "1")
        self.assertEqual(result["end_cash_usd"], "100009")

    def test_same_time_fill_rejected(self):
        summary, events, audit = self.sample()
        events[0]["time"] = 50
        with self.assertRaisesRegex(ValueError, "causal"):
            MODULE.summarize(summary, events, audit, rejected=False, adaptive=False, orders=self.orders())

    def test_unknown_order_status_rejected(self):
        summary, events, audit = self.sample()
        events[0]["status"] = "partiallyFilled"
        with self.assertRaisesRegex(ValueError, "status"):
            MODULE.summarize(summary, events, audit, rejected=False, adaptive=False, orders=self.orders())

    def test_bad_cash_and_nonflat_rejected(self):
        for field, value in [("cash", "999"), ("quantity", "1")]:
            with self.subTest(field=field):
                summary, events, audit = self.sample()
                audit[-1][field] = value
                with self.assertRaises(ValueError):
                    MODULE.summarize(summary, events, audit, rejected=False, adaptive=False, orders=self.orders())

    def test_rejection_must_be_actual_insufficient_buying_power(self):
        summary, events, audit = self.sample()
        with self.assertRaises(ValueError):
            MODULE.summarize(summary, events, audit, rejected=True, adaptive=False, orders=self.orders())

    def test_adaptive_requires_exactly_one_reduction(self):
        with self.assertRaisesRegex(ValueError, "reduction"):
            MODULE.summarize(*self.sample(), rejected=False, adaptive=True, orders=self.orders())

    def test_unattributed_fill_rejected(self):
        summary, events, audit = self.sample()
        audit = [a for a in audit if a.get("order_id") != 1]
        with self.assertRaisesRegex(ValueError, "unattributed"):
            MODULE.summarize(summary, events, audit, rejected=False, adaptive=False, orders=self.orders())

    def test_later_margin_call_does_not_excuse_missing_intent(self):
        summary, events, audit = self.sample()
        audit = [a for a in audit if a.get("order_id") != 1]
        audit.append({"kind": "margin_call", "utc_seconds": 150, "count": 1})
        orders = self.orders()
        orders["1"].update(tag="Margin Call", type=0)
        with self.assertRaisesRegex(ValueError, "unattributed"):
            MODULE.summarize(summary, events, audit, rejected=False, adaptive=False, orders=orders)

    def test_margin_order_count_must_match(self):
        summary, events, audit = self.sample()
        audit = [a for a in audit if a.get("order_id") != 1]
        audit.append({"kind": "margin_call", "utc_seconds": 100, "count": 2})
        orders = self.orders()
        orders["1"].update(tag="Margin Call", type=0)
        with self.assertRaisesRegex(ValueError, "quantity of orders"):
            MODULE.summarize(summary, events, audit, rejected=False, adaptive=False, orders=orders)

    def test_nonfinite_mark_rejected(self):
        summary, events, audit = self.sample()
        audit[-2]["gross"] = "NaN"
        with self.assertRaises(ValueError):
            MODULE.summarize(summary, events, audit, rejected=False, adaptive=False, orders=self.orders())


if __name__ == "__main__":
    unittest.main()
