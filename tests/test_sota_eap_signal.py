"""SYN: EAP universe, portfolio, delisting, cost and statistics functions (synthetic fixtures only)."""
import importlib.util
import math
import sys
import unittest
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/sota-mover/eap"


def load(name):
    key = f"eap_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, BASE / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]


S = load("signal")


class Universe(unittest.TestCase):
    def test_lanes(self):
        self.assertEqual(S.lane("ABC", 12.0, 2e6, 20, True), "main")
        self.assertEqual(S.lane("ABC", 4.99, 2e6, 20, True), "small")
        self.assertEqual(S.lane("ABC", 12.0, 5e5, 20, True), "small")
        self.assertIsNone(S.lane("ABC", 0.9, 5e5, 20, True))
        self.assertIsNone(S.lane("ABC", 12.0, 9e4, 20, True))

    def test_requires_decision_bar_and_history(self):
        self.assertIsNone(S.lane("ABC", 12.0, 2e6, 20, False))
        self.assertIsNone(S.lane("ABC", 12.0, 2e6, 17, True))
        self.assertEqual(S.lane("ABC", 12.0, 2e6, 18, True), "main")

    def test_common_stock_heuristic(self):
        for sym in ("ABCDW", "ABCDU", "ABCDR", "XYZ.WS", "XYZ.U", "BAC.PB", "BAC.P", "ABC.RT"):
            self.assertFalse(S.is_common_like(sym), sym)
        for sym in ("AAPL", "BRK.B", "GOOGL", "ABCD", "WW", "UBER"):
            self.assertTrue(S.is_common_like(sym), sym)

    def test_median(self):
        self.assertEqual(S.median([3, 1, 2]), 2)
        self.assertEqual(S.median([4, 1, 3, 2]), 2.5)


class Delisting(unittest.TestCase):
    def test_complete_month(self):
        r, flag = S.holding_return(10.0, [(date(2020, 3, 31), 11.0)], date(2020, 3, 31))
        self.assertAlmostEqual(r, 0.1)
        self.assertEqual(flag, "complete")

    def test_bars_end_early_keep_return_to_last_bar_then_cash(self):
        r, flag = S.holding_return(10.0, [(date(2020, 3, 12), 6.0)], date(2020, 3, 31))
        self.assertAlmostEqual(r, -0.4)
        self.assertEqual(flag, "bars_end_early")

    def test_no_bar_after_decision(self):
        self.assertEqual(S.holding_return(10.0, [], date(2020, 3, 31)), (0.0, "no_bar_in_month"))

    def test_no_decision_close_is_excluded(self):
        self.assertEqual(S.holding_return(None, [(date(2020, 3, 31), 11.0)], date(2020, 3, 31)), (None, "no_decision_close"))
        long, short = S.split_portfolios({"A": {"lane": "main", "eligible": True, "expected": True, "weight": 1.0, "ret": None}})
        self.assertEqual((long, short), ({}, {}))


class Portfolios(unittest.TestCase):
    def rows(self):
        return {
            "A": {"lane": "main", "eligible": True, "expected": True, "weight": 3.0, "ret": 0.10},
            "B": {"lane": "main", "eligible": True, "expected": True, "weight": 1.0, "ret": -0.10},
            "C": {"lane": "main", "eligible": True, "expected": False, "weight": 2.0, "ret": 0.02},
            "D": {"lane": "main", "eligible": False, "expected": False, "weight": 9.0, "ret": 0.50},
            "E": {"lane": "small", "eligible": True, "expected": True, "weight": 1.0, "ret": 0.30},
        }

    def test_split_and_value_weight(self):
        long, short = S.split_portfolios(self.rows())
        self.assertEqual(set(long), {"A", "B"})
        self.assertEqual(set(short), {"C"})
        self.assertAlmostEqual(S.vw_return(long), (3 * 0.1 - 0.1) / 4)
        ew, _ = S.split_portfolios(self.rows(), equal_weight=True)
        self.assertAlmostEqual(S.vw_return(ew), 0.0)
        small, _ = S.split_portfolios(self.rows(), lane_name="small")
        self.assertEqual(set(small), {"E"})

    def test_extreme_proxy_and_tercile(self):
        self.assertAlmostEqual(S.extreme_proxy([0.1, -0.2, None, 0.3], 3), 0.2)
        self.assertIsNone(S.extreme_proxy([0.1, None, None, 0.3], 3))
        prox = {f"S{i}": i / 100 for i in range(9)}
        self.assertEqual(S.top_tercile(prox), {"S8", "S7", "S6"})


class Costs(unittest.TestCase):
    FEES = {"sec_section31": {"rows": [{"from": "2016-01-01", "to": None, "usd_per_million": 20.0}]},
            "finra_taf_covered_equity": {"rows": [{"from": "2016-01-01", "to": None, "usd_per_share": 0.0002}]}}

    def test_half_spread_table(self):
        self.assertEqual(S.half_spread(10.0, 2e6, "main"), 0.00745)
        self.assertEqual(S.half_spread(50.0, 2e6, "main"), 0.00745)
        self.assertEqual(S.half_spread(10.0, 6e6, "main"), 0.00227)
        self.assertEqual(S.half_spread(50.0, 6e6, "main"), 0.00177)
        self.assertEqual(S.half_spread(3.0, 2e5, "small"), 0.01)

    def test_fees_from_v3_file(self):
        fees = S.load_fees()
        d = date(2020, 6, 1)
        sec = next(r for r in fees["sec_section31"]["rows"] if r["from"] <= "2020-06-01" <= (r["to"] or "9999"))
        taf = next(r for r in fees["finra_taf_covered_equity"]["rows"] if r["from"] <= "2020-06-01" <= (r["to"] or "9999"))
        self.assertAlmostEqual(S.sell_fee_per_dollar(d, 25.0, fees), sec["usd_per_million"] / 1e6 + taf["usd_per_share"] / 25.0)

    def test_rebalance_cost_and_turnover(self):
        old = {"A": 0.5, "B": 0.5}
        new = {"B": 0.5, "C": 0.5}
        px, dv = {"A": 10.0, "B": 10.0, "C": 50.0}, {"A": 6e6, "B": 6e6, "C": 6e6}
        cost, turn = S.rebalance_cost(old, new, px, dv, {}, date(2020, 1, 31), self.FEES)
        self.assertAlmostEqual(turn, 1.0)
        expected = 0.5 * 0.00227 + 0.5 * (20e-6 + 0.0002 / 10) + 0.5 * 0.00177
        self.assertAlmostEqual(cost, expected)

    def test_drift(self):
        w = S.drift({"A": 0.5, "B": 0.5}, {"A": 1.0, "B": 0.0})
        self.assertAlmostEqual(w["A"], 2 / 3)


class Statistics(unittest.TestCase):
    def test_nw_zero_lags_is_iid_se(self):
        xs = [0.01, -0.02, 0.03, 0.00, 0.02, -0.01]
        m, se, t = S.nw_t(xs, 0)
        n = len(xs)
        var = sum((x - m) ** 2 for x in xs) / n
        self.assertAlmostEqual(se, math.sqrt(var / n))
        self.assertAlmostEqual(t, m / se)

    def test_nw_positive_autocorrelation_widens_se(self):
        xs = [0.01 * (1 if (i // 4) % 2 else -1) + 0.001 for i in range(48)]
        self.assertGreater(S.nw_t(xs, 3)[1], S.nw_t(xs, 0)[1])

    def test_t_distribution_tail(self):
        self.assertAlmostEqual(S.t_sf(2.228, 10), 0.025, places=3)
        self.assertAlmostEqual(S.t_sf(1.6449, 100000), 0.05, places=3)
        self.assertAlmostEqual(S.t_sf(0.0, 20), 0.5, places=9)
        self.assertAlmostEqual(S.t_sf(-2.228, 10), 0.975, places=3)

    def test_holm(self):
        self.assertEqual(S.holm({"a": 0.01, "b": 0.015, "c": 0.02, "d": 0.04}, 0.05),
                         {"a": True, "b": True, "c": True, "d": True})
        self.assertEqual(S.holm({"a": 0.01, "b": 0.02, "c": 0.001, "d": 0.002}, 0.05),
                         {"a": True, "b": True, "c": True, "d": True})
        self.assertEqual(S.holm({"a": 0.01, "b": 0.02, "c": 0.03, "d": 0.04}, 0.05),
                         {"a": True, "b": False, "c": False, "d": False})
        self.assertEqual(S.holm({"a": 0.0125, "b": 0.016, "c": 0.5, "d": 0.9}, 0.05),
                         {"a": True, "b": True, "c": False, "d": False})
        self.assertEqual(S.holm({"a": 0.02, "b": 0.001, "c": 0.5, "d": 0.9}, 0.05),
                         {"a": False, "b": True, "c": False, "d": False})
        self.assertEqual(S.holm({"a": 0.0126, "b": 0.001, "c": 0.002, "d": 0.003}, 0.05)["a"], True)
        self.assertEqual(S.holm({"a": 0.0126, "b": 0.2, "c": 0.3, "d": 0.4}, 0.05)["a"], False)


if __name__ == "__main__":
    unittest.main()
