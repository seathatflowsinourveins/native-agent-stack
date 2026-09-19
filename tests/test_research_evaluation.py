"""Causal and input-boundary failures for the chronological price-label study."""
import datetime as dt
from decimal import Decimal
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "blueprints/us-equities/research-evaluation/evaluate.py"


def module():
    spec = importlib.util.spec_from_file_location("chronological_evaluation", PATH)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ResearchEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = module() if PATH.exists() else None

    def setUp(self):
        self.assertIsNotNone(self.m, "chronological evaluation implementation is required")
        self.dates = [(dt.date(2018, 1, 1) + dt.timedelta(days=i)).isoformat() for i in range(200)]
        self.prices = {s: [{"date": d, "open": Decimal(100+i), "close": Decimal(101+i)}
                          for i, d in enumerate(self.dates)] for s in ["SPY", "QQQ", "IWM"]}

    def test_future_prices_cannot_change_earlier_decision(self):
        before = self.m.weights(self.prices, 130, "momentum120")
        self.prices["SPY"][131]["close"] = Decimal("1000000")
        self.assertEqual(before, self.m.weights(self.prices, 130, "momentum120"))
        self.assertEqual(before, {"IWM": Decimal(1)})

    def test_holdout_labels_cannot_enter_selection(self):
        rows = [{"candidate": "cash", "decision": "2020-12-01", "exit": "2021-01-04", "net_proxy": "1"}]
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.m.choose(rows, ["cash"], "2021-01-04")

    def test_validation_outcomes_cannot_enter_selection(self):
        train = [{"candidate": "cash", "decision": "2018-01-01", "exit": "2018-01-07", "net_proxy": "0"},
                 {"candidate": "momentum20", "decision": "2018-01-01", "exit": "2018-01-07", "net_proxy": "0.02"}]
        self.assertEqual(self.m.choose(train, ["momentum20", "cash"], "2018-02-01")["chosen"], "momentum20")
        train.append({"candidate": "cash", "decision": "2018-02-01", "exit": "2018-02-07", "net_proxy": "99"})
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.m.choose(train, ["momentum20", "cash"], "2018-02-01")

    def test_future_prices_cannot_change_training_selection(self):
        candidates = ["momentum20", "momentum60", "momentum120", "cash"]
        def selection():
            rows = [self.m.label(self.prices, i, c, Decimal("0.002"))
                    for i in [125, 130, 135] for c in candidates]
            return self.m.choose(rows, candidates, self.dates[150])
        before = selection()
        for rows in self.prices.values():
            for row in rows[150:]:
                row["open"] = Decimal("0.01")
                row["close"] = Decimal("999999")
        self.assertEqual(before, selection())

    def test_label_entry_is_next_open_and_exit_six_sessions_later(self):
        row = self.m.label(self.prices, 130, "momentum20", Decimal("0.002"))
        self.assertEqual(row["entry"], self.dates[131])
        self.assertEqual(row["exit"], self.dates[136])
        self.assertEqual(Decimal(row["gross_price_label"]), Decimal(236)/Decimal(231)-1)

    def test_cash_and_equalweight_costs_are_comparable(self):
        cash = self.m.label(self.prices, 130, "cash", Decimal("0.002"))
        equal = self.m.label(self.prices, 130, "equalweight", Decimal("0.002"))
        self.assertEqual(cash["cost_proxy"], "0.000")
        self.assertEqual(Decimal(equal["cost_proxy"]), Decimal("0.002"))

    def test_incomplete_horizon_retained_without_label(self):
        row = self.m.label(self.prices, 195, "momentum20", Decimal("0.002"))
        self.assertEqual(row["status"], "censored")
        self.assertNotIn("net_proxy", row)

    def test_misaligned_asset_calendar_rejected(self):
        self.prices["SPY"].pop(30)
        with self.assertRaisesRegex(ValueError, "calendar"):
            self.m.validate_panel(self.prices)

    def test_nan_negative_duplicate_input_rejected(self):
        for value in [Decimal("NaN"), Decimal("-1"), Decimal("Infinity")]:
            with self.subTest(value=value):
                self.prices["SPY"][0]["open"] = value
                with self.assertRaises(ValueError):
                    self.m.validate_panel(self.prices)
        self.prices["SPY"][0]["open"] = Decimal(100)
        self.prices["SPY"][1]["date"] = self.dates[0]
        with self.assertRaises(ValueError):
            self.m.validate_panel(self.prices)

    def test_split_transition_rejected(self):
        with self.assertRaisesRegex(ValueError, "split"):
            self.m.check_auxiliary("20160101,1,0.5,100\n20200101,1,1,100\n20501231,1,1,0\n", "20100101,spy,P\n20501231,spy,P\n", "2015-01-01", "2021-03-31", "SPY")

    def test_frozen_record_resists_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "selection.json"
            self.m.write_new(path, {"chosen": "cash"})
            with self.assertRaises(FileExistsError):
                self.m.write_new(path, {"chosen": "momentum20"})

    def test_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.txt"
            path.write_text("corrupt")
            with self.assertRaisesRegex(ValueError, "hash"):
                self.m.verify_inputs(Path(folder), {"data.txt": "0"*64})


if __name__ == "__main__":
    unittest.main()
