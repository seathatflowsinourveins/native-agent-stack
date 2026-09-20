"""Failure boundaries in the compact native corporate-action result verifier."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1]/"blueprints/us-equities/corporate-action-readiness/verify.py"


class CorporateActionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PATH.exists(), "native result verifier is required")
        spec = importlib.util.spec_from_file_location("corporate_action_verify", PATH)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_nonzero_raw_factor_sentinel_rejected(self):
        with self.assertRaisesRegex(ValueError, "raw sentinel"):
            self.m.check_row({"raw_factor_sentinel": "1"})

    def test_basis_at_wrong_date_rejected(self):
        with self.assertRaisesRegex(ValueError, "basis"):
            self.m.check_row({"raw_factor_sentinel": "0", "date": "2020-08-28", "mapped_symbol": "AAPL",
                "raw_close": "100", "split_factor": "0.25", "split_adjusted_close": "25",
                "adjusted_factor": "0.24", "adjusted_close": "24", "total_return_factor": "0.25",
                "end_basis": "2020-08-28", "end_basis_scaled_close": "25", "end_basis_scale": "0.25"})

    def test_mapping_change_rejected(self):
        with self.assertRaisesRegex(ValueError, "mapping"):
            self.m.check_row({"raw_factor_sentinel": "0", "date": "2020-08-28", "mapped_symbol": "OTHER"})

    def test_split_price_scaling_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "split scaling"):
            self.m.check_row({"raw_factor_sentinel": "0", "date": "2020-08-28", "mapped_symbol": "AAPL",
                "raw_close": "100", "split_factor": "0.25", "split_adjusted_close": "100"})

    def test_missing_extra_false_and_nonboolean_guards_rejected(self):
        good = {"implicit_scaled_raw_basis_rejected": True, "future_bar_for_decision_rejected": True}
        for guards in [{}, {**good, "extra": True}, {**good, "future_bar_for_decision_rejected": False},
                       {**good, "future_bar_for_decision_rejected": "true"}]:
            with self.subTest(guards=guards), self.assertRaisesRegex(ValueError, "guard"):
                self.m.check_scope({"guards": guards, "orders_submitted": False,
                                    "total_return_series_computed": False})

    def test_falsey_nonboolean_scope_rejected(self):
        good = {"implicit_scaled_raw_basis_rejected": True, "future_bar_for_decision_rejected": True}
        for value in [0, "", None]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "scope"):
                self.m.check_scope({"guards": good, "orders_submitted": value,
                                    "total_return_series_computed": False})

    def test_missing_empty_and_failed_upstream_tests_rejected(self):
        for result in [{}, {"counters": {"total": "0", "executed": "0"}, "cases": []},
                       {"counters": {"total": "1", "executed": "1", "failed": "1"},
                        "cases": [{"outcome": "Failed"}]}]:
            with self.subTest(result=result), self.assertRaises(ValueError):
                self.m.check_upstream_tests(result)

    def test_native_decimal_rounding_bound(self):
        self.assertTrue(self.m.product_matches("108.74143640795507009412832133", "435.75", "0.2495500548662193232223254649"))
        self.assertFalse(self.m.product_matches("108.7414364079550700941284", "435.75", "0.2495500548662193232223254649"))

    def test_corrupt_input_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            altered = base/"lean/Data/equity/usa/daily/aapl.zip"
            altered.parent.mkdir(parents=True)
            altered.write_bytes(b"corrupt-input-fixture")
            output = base/"must-not-exist"
            result = subprocess.run([sys.executable, str(PATH.with_name("run.py")),
                "--lean-source", str(base/"lean"), "--dotnet", str(base/"sdk/dotnet"),
                "--out", str(output)], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("frozen input hash mismatch", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
