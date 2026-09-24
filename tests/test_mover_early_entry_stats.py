"""Synthetic tests for the mover early-entry evaluator's statistics, costs and portfolio (no private data)."""
import importlib.util
import math
import sys
import unittest
from pathlib import Path

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HERE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/mover-early-entry"


def load(name):
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location(f"mover_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (protocol inputs.runtime)")
class Statistics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.E = load("evaluate")
        cls.R = load("rules")

    def test_replicates_are_deterministic_and_keep_the_session_count(self):
        a = self.E.replicate_counts(23, seed=7, b=50)
        b = self.E.replicate_counts(23, seed=7, b=50)
        self.assertTrue((a == b).all())
        self.assertTrue((a.sum(axis=1) == 23).all())
        self.assertNotEqual(self.E.replicate_counts(23, seed=8, b=50).tobytes(), a.tobytes())

    def test_bootstrap_p_counts_non_positive_and_empty_replicates(self):
        np = self.np
        C = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0], [1.0, 1.0]])
        sums = np.array([[5.0], [-1.0]])
        cnts = np.array([[1.0], [1.0]])
        p, lb = self.E.bootstrap(C, sums, cnts)
        # replicates: +5, -1, empty, +4 -> non-positive or empty = 2 -> p = 3/5
        self.assertAlmostEqual(p[0], 3 / 5)
        self.assertEqual(lb[0], -np.inf)

    def test_multiple_testing_adjustments(self):
        p = [0.01, 0.04, 0.03, 0.20]
        bh = self.E.bh(p)
        self.assertEqual([round(x, 6) for x in bh], [0.04, 0.053333, 0.053333, 0.2])
        holm = self.E.holm(p)
        self.assertEqual([round(x, 6) for x in holm], [0.04, 0.09, 0.09, 0.2])
        self.assertTrue(all(b >= a for a, b in zip(bh, self.E.by(p))))

    def test_spearman_and_two_way_cluster(self):
        self.assertAlmostEqual(self.E.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(self.E.spearman([1, 2, 2, 4], [4, 3, 3, 1]), -1.0)
        np = self.np
        r = np.array([0.02, 0.01, 0.03, -0.01, 0.02, 0.04])
        p = self.E.two_way_p(r, np.array([0, 0, 1, 1, 2, 2]), np.array([0, 1, 2, 3, 4, 5]))
        self.assertTrue(0 < p < 0.5)

    def test_summarise_drops_top_sessions_and_reports_breakdowns(self):
        np = self.np
        net = self.E.quantise([0.5, -0.1, 0.1, 0.1, -0.2, 0.3, 0.0])
        sess = np.array([0, 0, 1, 2, 3, 4, 5])
        codes = {"by_year": (["2021", "2022"], np.array([0, 0, 0, 1, 1, 1, 1]))}
        m = self.E.summarise(net, net / 1e6, sess, 6, codes)
        self.assertEqual(m["trades"], 7)
        self.assertAlmostEqual(m["mean"], 0.7 / 7)
        # session sums: 0.4, 0.1, 0.1, -0.2, 0.3, 0.0 -> top five exclude only session 3 (-0.2)
        self.assertAlmostEqual(m["mean_without_top5_sessions"], -0.2)
        self.assertEqual(m["by_year"]["2021"][0], 3)
        self.assertAlmostEqual(m["profit_factor"], 1.0 / 0.3)

    def test_vectorised_net_return_is_bitwise_equal_to_the_scalar_model(self):
        np = self.np
        rng = np.random.default_rng(3)
        n = 400
        entry = rng.uniform(1, 50, n)
        exit_ = entry * rng.uniform(0.5, 2.5, n)
        cin, cout = rng.uniform(0, 0.03, n), rng.uniform(0, 0.03, n)
        days = rng.choice(["2021-03-01", "2022-06-01", "2024-06-03", "2025-06-02", "2026-05-01"], n)
        fees = [self.R.fee_rates(d) for d in days]
        sec, taf, cap = (np.array([f[i] for f in fees]) for i in range(3))
        for broker, mult in (("alpaca", 1.0), ("alpaca", 2.0), ("ibkr", 1.0)):
            vec = self.R.net_return_np(entry, exit_, cin, cout, sec, taf, cap, 20_000.0, broker, mult)
            scal = np.array([self.R.net_return(e, x, a, b, d, 20_000.0, broker, mult) for e, x, a, b, d in zip(entry, exit_, cin, cout, days)])
            self.assertEqual(vec.tobytes(), scal.tobytes(), broker)


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (protocol inputs.runtime)")
class Portfolio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.E = load("evaluate")

    def entries(self, nets, prices=None, dv=1e9):
        np = self.np
        E = self.E.Entries.__new__(self.E.Entries)
        n = len(nets)
        E.cal = [f"2023-01-{i + 2:02d}" for i in range(n)]
        E.sess = np.arange(n)
        E.symbol = [f"S{i}" for i in range(n)]
        E.day = E.cal
        E.dv = np.full(n, dv)
        E.bar_dv = np.full(n, np.nan)
        E.price = np.array(prices if prices else [10.0] * n)
        E.entry = np.full(n, 10.0)
        E.X1_px = 10.0 * (1 + np.array(nets))
        E.X1_cin = np.zeros(n)
        E.X1_cout = np.zeros(n)
        return E

    def test_leverage_regime_and_sub5_cap(self):
        E = self.entries([0.10])
        top5 = self.E.top5_by_session(E, self.np.arange(1))
        stats, _, _ = self.E.simulate(E, top5, "X1", {E.cal[0]: 1.0}, 4)
        # 4x gross over 5 slots -> one position is 80% of equity; +10% -> +8% (less sell fees)
        self.assertAlmostEqual(stats["final_equity"], 108000, delta=5)
        stats, _, _ = self.E.simulate(E, top5, "X1", {E.cal[0]: 0.5}, 4)
        self.assertAlmostEqual(stats["final_equity"], 104000, delta=5)
        cheap = self.entries([0.10], prices=[3.0])
        stats, _, _ = self.E.simulate(cheap, self.E.top5_by_session(cheap, self.np.arange(1)), "X1", {cheap.cal[0]: 1.0}, 4)
        self.assertAlmostEqual(stats["final_equity"], 102000, delta=5)

    def test_capacity_cap_and_drawdown_cooldown(self):
        E = self.entries([0.10], dv=100_000.0)
        stats, _, _ = self.E.simulate(E, self.E.top5_by_session(E, self.np.arange(1)), "X1", {E.cal[0]: 1.0}, 1)
        self.assertAlmostEqual(stats["fill_ratio"], 1000 / 20000)
        # A -100% session at 4x (80% of equity in one name) is a >20% drawdown: the next 10 sessions trade nothing.
        nets = [-1.0] + [0.10] * 12
        E = self.entries(nets)
        stats, taken_sess, _ = self.E.simulate(E, self.E.top5_by_session(E, self.np.arange(len(nets))), "X1", {d: 1.0 for d in E.cal}, 4)
        self.assertEqual(taken_sess.tolist(), [0, 11, 12])


if __name__ == "__main__":
    unittest.main()
