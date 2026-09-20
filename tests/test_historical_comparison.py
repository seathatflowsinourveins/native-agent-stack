import copy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "blueprints/us-equities/authenticated-data/compare.py"
SPEC = importlib.util.spec_from_file_location("historical_comparison", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HistoricalComparisonTests(unittest.TestCase):
    def setUp(self):
        self.lean = {"symbol": "AAPL", "observations": [{"date": f"2020-08-{i:02d}", "mapped_symbol": "AAPL", "raw_close": "100.000000000000000001"} for i in range(1, 26)],
                     "events": [{"kind": "dividend", "date": "2020-08-07", "distribution": "0.82"}, {"kind": "split", "date": "2020-08-31", "factor": "0.25"}]}
        self.stages = {"bars": {"status": "complete", "rows": [{"session_date": r["date"], "symbol": "AAPL", "c": r["raw_close"]} for r in self.lean["observations"]]},
                       "actions": {"status": "complete", "rows": [{"symbol": "AAPL", "qualification": "qualified", "type": "cash_dividend", "ex_date": "2020-08-07", "rate": "0.82", "currency": "USD"},
                         {"symbol": "AAPL", "qualification": "qualified", "type": "forward_split", "ex_date": "2020-08-31", "old_rate": "1", "new_rate": "4"}]}}

    def test_equal_bases_and_units(self):
        result = MODULE.compare(self.lean, self.stages)
        self.assertEqual(result["bars"]["equal"], 25)
        self.assertEqual(result["actions"]["equal"], 2)

    def test_exact_decimal_difference_survives(self):
        self.stages["bars"]["rows"][0]["c"] = "100.000000000000000002"
        result = MODULE.compare(self.lean, self.stages)["bars"]
        self.assertEqual(result["different"], 1)
        self.assertEqual(result["maximum_absolute_close_difference"], "1E-18")

    def test_missing_is_not_equality(self):
        self.stages["bars"]["rows"].pop()
        self.stages["actions"]["rows"] = []
        result = MODULE.compare(self.lean, self.stages)
        self.assertEqual(result["bars"]["missing"], 1)
        self.assertEqual(result["actions"]["compared"], 0)
        self.assertEqual(result["actions"]["missing"], 2)

    def test_duplicate_bars_rejected(self):
        self.stages["bars"]["rows"].append(copy.deepcopy(self.stages["bars"]["rows"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            MODULE.compare(self.lean, self.stages)

    def test_revisions_are_ambiguous(self):
        self.stages["actions"]["rows"].append(copy.deepcopy(self.stages["actions"]["rows"][0]))
        self.assertEqual(MODULE.compare(self.lean, self.stages)["actions"]["ambiguous"], 1)

    def test_wrong_currency_or_split_basis_differs(self):
        self.stages["actions"]["rows"][0]["currency"] = "EUR"
        self.stages["actions"]["rows"][1]["old_rate"] = "4"
        self.assertEqual(MODULE.compare(self.lean, self.stages)["actions"]["different"], 2)

    def test_failed_stage_does_not_compare(self):
        self.stages["bars"] = {"status": "failed", "reason": "http_403", "rows": []}
        self.assertEqual(MODULE.compare(self.lean, self.stages)["bars"]["compared"], 0)

    def test_zero_cash_distribution_is_a_difference(self):
        self.stages["actions"]["rows"][0]["rate"] = "0"
        self.assertEqual(MODULE.compare(self.lean, self.stages)["actions"]["different"], 1)

    def test_missing_currency_is_unknown_not_a_value_mismatch(self):
        self.stages["actions"]["rows"][0]["currency"] = None
        result = MODULE.compare(self.lean, self.stages)["actions"]
        self.assertEqual(result["different"], 0)
        self.assertEqual(result["unknown_currency"], 1)
        self.assertEqual(result["numeric_values_equal"], 2)

    def test_nonfinite_and_float_rejected(self):
        for value in ["NaN", "Infinity", "0", "-1", 0.82, "1e900"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.numeric(value)


if __name__ == "__main__":
    unittest.main()
