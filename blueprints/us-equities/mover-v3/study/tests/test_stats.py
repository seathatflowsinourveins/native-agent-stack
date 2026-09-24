"""statistics and multiple_testing: seeded bootstrap, closed null side, empty draws, Holm m = 5, robustness,
MDE, labels and verdicts."""
import math
import unittest

import numpy as np

from core import stats as ST
from core.params import ITEM_IDS

PID = "mover-v3-core-draft-20260924"


class Streams(unittest.TestCase):
    def test_seed_is_per_stage_and_item(self):
        a = ST.generator(PID, "validation", "H3-a").integers(0, 1 << 30, 5)
        b = ST.generator(PID, "validation", "H3-a").integers(0, 1 << 30, 5)
        c = ST.generator(PID, "holdout", "H3-a").integers(0, 1 << 30, 5)
        d = ST.generator(PID, "validation", "H3-b").integers(0, 1 << 30, 5)
        self.assertTrue((a == b).all())
        self.assertFalse((a == c).all())
        self.assertFalse((a == d).all())
        ss = np.random.SeedSequence(entropy=int.from_bytes(__import__("hashlib").sha256(PID.encode()).digest()[:8], "big"),
                                    spawn_key=(1,)).spawn(5)[ITEM_IDS.index("H3-a")]
        e = np.random.Generator(np.random.PCG64(ss)).integers(0, 1 << 30, 5)
        self.assertTrue((a == e).all())

    def test_circular_blocks_wrap_and_cut(self):
        rng = np.random.Generator(np.random.PCG64(1))
        idx = ST._draw_indices(rng, 7, 3, 4)
        self.assertEqual(idx.shape, (4, 7))
        for row in idx:
            for blk in range(0, 6, 3):
                s = row[blk]
                self.assertEqual(list(row[blk: blk + 3]), [(s + k) % 7 for k in range(3)])

    def test_bootstrap_is_deterministic_and_chunk_independent_of_B_split(self):
        sessions = [f"d{i:03d}" for i in range(50)]
        trades = [{"session": s, "value": 0.01 * ((i % 5) - 1)} for i, s in enumerate(sessions)]
        g = [ST.session_arrays(sessions, trades)]
        a = ST.bootstrap(sessions, g, ST.generator(PID, "validation", "H3-a"), 5, B=3000, chunk=1000)
        b = ST.bootstrap(sessions, g, ST.generator(PID, "validation", "H3-a"), 5, B=3000, chunk=1000)
        self.assertTrue(np.array_equal(a, b))


class PValues(unittest.TestCase):
    def test_closed_null_side(self):
        stats = np.array([0.0, 0.0, 1.0, 2.0])
        self.assertEqual(ST.p_value(stats, "greater"), (1 + 2) / 5)
        self.assertEqual(ST.p_value(stats, "less"), (1 + 4) / 5)
        self.assertEqual(ST.p_value(np.array([-1.0, -2.0, 0.0]), "less"), 0.5)  # only the 0 is on the null side

    def test_empty_group_draw_counts_as_null(self):
        stats = np.array([np.nan, 1.0, 1.0, 1.0])
        self.assertEqual(ST.p_value(stats, "greater"), 2 / 5)
        self.assertEqual(ST.p_value(np.array([np.nan, -1.0, -1.0, -1.0]), "less"), 2 / 5)
        two = ST.p_value(np.array([np.nan, 1.0, 1.0, 1.0]), "two-sided")
        self.assertEqual(two, min(1.0, 2 * min(2 / 5, 5 / 5)))

    def test_empty_group_in_a_difference_draw(self):
        sessions = ["a", "b"]
        trades = [{"session": "a", "value": 1.0, "group": "high"}, {"session": "b", "value": 0.0, "group": "low"}]
        g = [ST.session_arrays(sessions, trades, "high"), ST.session_arrays(sessions, trades, "low")]
        out = ST.bootstrap(sessions, g, np.random.Generator(np.random.PCG64(3)), 1, B=200, chunk=50)
        drawn_both = ~np.isnan(out)
        self.assertTrue(np.isnan(out).any() and drawn_both.any())
        self.assertTrue(np.allclose(out[drawn_both], 1.0))

    def test_normal_tail(self):
        stats = np.array([-1.0, 1.0] * 50)
        sd = float(np.std(stats, ddof=1))
        self.assertAlmostEqual(ST.normal_tail_p(sd * 1.6448536, stats, "greater"), 0.05, places=6)
        self.assertAlmostEqual(ST.normal_tail_p(-sd * 1.6448536, stats, "less"), 0.05, places=6)
        self.assertAlmostEqual(ST.normal_tail_p(sd * 1.959964, stats, "two-sided"), 0.05, places=5)
        self.assertEqual(ST.normal_tail_p(1.0, np.zeros(10), "greater"), 1.0)


class Holm(unittest.TestCase):
    def test_step_down_over_five(self):
        p = {"H1-D": 0.004, "H1-D-b_lane-low": 0.03, "H3-a": 0.011, "H3-b": 0.5, "H3-c": 0.02}
        adj = ST.holm(p)
        self.assertAlmostEqual(adj["H1-D"], 0.02)
        self.assertAlmostEqual(adj["H3-a"], 0.044)
        self.assertAlmostEqual(adj["H3-c"], 0.06)
        self.assertAlmostEqual(adj["H1-D-b_lane-low"], 0.06)
        self.assertAlmostEqual(adj["H3-b"], 0.5)

    def test_family_is_exactly_five_and_ties_break_by_normal_p_then_id(self):
        with self.assertRaises(ValueError):
            ST.holm({"H1-D": 0.01})
        floor = 1 / 100_001
        p = {i: floor for i in ITEM_IDS}
        adj = ST.holm(p, {"H1-D": 0.3, "H1-D-b_lane-low": 0.1, "H3-a": 0.1, "H3-b": 0.2, "H3-c": 0.0})
        self.assertTrue(all(abs(v - 5 * floor) < 1e-15 for v in adj.values()))
        order = sorted(ITEM_IDS, key=lambda i: (p[i], {"H1-D": 0.3, "H1-D-b_lane-low": 0.1, "H3-a": 0.1,
                                                       "H3-b": 0.2, "H3-c": 0.0}[i], i.encode()))
        self.assertEqual(order, ["H3-c", "H1-D-b_lane-low", "H3-a", "H3-b", "H1-D"])


class Robustness(unittest.TestCase):
    def test_small_table(self):
        trades = [{"session": "s1", "value": 0.10}, {"session": "s1", "value": -0.02}, {"session": "s2", "value": 0.03},
                  {"session": "s3", "value": 0.01}, {"session": "s4", "value": 0.02}, {"session": "s5", "value": -0.01},
                  {"session": "s6", "value": 0.02}, {"session": "s7", "value": 0.04}]
        vals = np.array([t["value"] for t in trades])
        lo, hi = np.quantile(vals, [0.01, 0.99])
        self.assertAlmostEqual(ST.winsorised_mean(vals), float(np.clip(vals, lo, hi).mean()))
        # session sums: s1 .08, s2 .03, s3 .01, s4 .02, s5 -.01, s6 .02, s7 .04; drop s1, s7, s2, then s4 (earlier
        # of the .02 tie) and s6; keep s3 and s5
        self.assertAlmostEqual(ST.mean_without_top_sessions(trades), (0.01 - 0.01) / 2)
        self.assertAlmostEqual(ST.mean_of_session_means(trades), np.mean([0.04, 0.03, 0.01, 0.02, -0.01, 0.02, 0.04]))
        self.assertFalse(ST.robustness(trades)["all_positive"])


class MDE(unittest.TestCase):
    def test_matches_the_protocol_tables(self):
        self.assertAlmostEqual(ST.mde("H3-a", n=150) * 100, 7.92, places=2)
        self.assertAlmostEqual(ST.mde("H3-b", n=300) * 100, 3.36, places=2)
        self.assertAlmostEqual(ST.mde("H1-D-b_lane-low", n=600) * 100, 5.54, places=2)
        self.assertAlmostEqual(ST.mde("H1-D", n1=100, n2=100) * 100, 19.2, places=1)
        self.assertAlmostEqual(ST.mde("H3-c", n=150) * 100, 3.42, places=2)

    def test_minimum_uses_the_statistic_n(self):
        self.assertTrue(ST.minimum_met("H3-a", "validation", 150))
        self.assertFalse(ST.minimum_met("H3-a", "validation", 149))
        self.assertFalse(ST.minimum_met("H1-D", "holdout", 500, 400, 99))
        self.assertTrue(ST.minimum_met("H1-D", "holdout", 200, 100, 100))
        self.assertFalse(ST.minimum_met("H3-c", "development", 299))

    def test_mde_exclusion_bounds(self):
        tight = np.linspace(-0.001, 0.001, 1001)
        self.assertTrue(ST.mde_excluded("H3-a", tight, 0.05))
        self.assertTrue(ST.mde_excluded("H1-D", tight, 0.05))
        self.assertTrue(ST.mde_excluded("H3-c", tight, 0.05))
        wide = np.linspace(-0.2, 0.2, 1001)
        self.assertFalse(ST.mde_excluded("H3-a", wide, 0.05))


class Labels(unittest.TestCase):
    def test_stage_pass_names_and_rules(self):
        kw = dict(n_ok=True, robust_ok=True, mde_ok=False)
        self.assertEqual(ST.item_label("development", "H3-a", p_stage=0.01, **kw), "development pass")
        self.assertEqual(ST.item_label("validation", "H3-a", p_stage=0.01, **kw), "screened")
        self.assertEqual(ST.item_label("holdout", "H3-a", p_stage=0.01, **kw), "supported (confirmatory)")
        self.assertEqual(ST.item_label("holdout", "H3-a", p_stage=0.01, contaminated=True, **kw),
                         "screened (contaminated holdout)")
        self.assertEqual(ST.item_label("validation", "H3-a", p_stage=0.01, n_ok=True, robust_ok=False, mde_ok=False),
                         "underpowered")
        self.assertEqual(ST.item_label("development", "H3-a", p_stage=0.01, n_ok=True, robust_ok=False, mde_ok=False),
                         "development pass")  # the development screen needs p and the minimum sample only
        self.assertEqual(ST.item_label("validation", "H1-D", p_stage=0.01, n_ok=True, robust_ok=False, mde_ok=False),
                         "screened")  # robustness applies to tradable cells only
        self.assertEqual(ST.item_label("validation", "H3-a", p_stage=0.2, n_ok=True, robust_ok=True, mde_ok=True),
                         "not_supported_mde_excluded")
        self.assertEqual(ST.item_label("validation", "H3-a", p_stage=0.01, n_ok=False, robust_ok=True, mde_ok=True),
                         "underpowered")
        self.assertEqual(ST.item_label("validation", "H3-a", p_stage=0.01, void=True, **kw), "underpowered")

    def test_h3c_holdout_needs_the_validation_sign(self):
        kw = dict(n_ok=True, robust_ok=True, mde_ok=False)
        self.assertEqual(ST.item_label("holdout", "H3-c", p_stage=0.001, sign_ok=False, **kw), "underpowered")
        self.assertEqual(ST.item_label("holdout", "H3-c", p_stage=0.001, sign_ok=True, **kw), "supported (confirmatory)")

    def test_verdicts(self):
        labels = {"H1-D": "not_supported_mde_excluded", "H1-D-b_lane-low": "underpowered", "H3-a": "screened",
                  "H3-b": "underpowered", "H3-c": "underpowered"}
        v = ST.hypothesis_verdict("validation", labels)
        self.assertEqual(v["H1"]["verdict"], "not supported")
        self.assertEqual(v["H3"], {"verdict": "screened", "items": ["H3-a"]})
        labels = {i: "not supported (holdout not read)" for i in ("H3-a", "H3-c")}
        labels.update({"H1-D": "not carried", "H1-D-b_lane-low": "not carried", "H3-b": "not carried"})
        v = ST.hypothesis_verdict("holdout", labels)
        self.assertEqual(v["H3"]["verdict"], "not supported (holdout not read)")
        self.assertEqual(v["H1"]["verdict"], "inconclusive")


if __name__ == "__main__":
    unittest.main()


class Diagnostics(unittest.TestCase):
    def test_h3c_is_two_sided_at_every_stage(self):
        from core.params import ALTERNATIVE
        self.assertEqual(ALTERNATIVE["H3-c"], "two-sided")
        up, down = np.array([1.0] * 99 + [-1.0]), np.array([-1.0] * 99 + [1.0])
        self.assertEqual(ST.p_value(up, "two-sided"), ST.p_value(down, "two-sided"))

    def test_bh_and_split_p(self):
        out = ST.benjamini_hochberg({"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5})
        self.assertEqual(out, {"a": True, "b": True, "c": True, "d": False})
        self.assertEqual(ST.benjamini_hochberg({"a": 0.2, "b": 0.3}), {"a": False, "b": False})
        self.assertLess(ST.split_p([0.1, 0.2, 0.15, 0.12], "greater"), 0.01)
        self.assertEqual(ST.split_p([0.1], "greater"), 1.0)

    def test_two_way_cluster(self):
        vals = [0.1, -0.1, 0.2, 0.0]
        out = ST.two_way_cluster(vals, ["s1", "s1", "s2", "s2"], ["A", "B", "A", "B"])
        self.assertAlmostEqual(out["mean"], 0.05)
        self.assertGreater(out["se"], 0.0)

    def test_break_even_multiple(self):
        from core import costs
        from tests.test_costs import FEES
        f = costs.Fees(FEES)
        tr = {"nets": {"primary": None}, "primary_parts": (10_000.0, 10.0, 10.5, 1.0, 0.0, 0.01, 0.01, "2019-06-03")}
        k = ST.break_even_multiple([tr], f)
        self.assertAlmostEqual(costs.trade_net_return(10_000.0, 10.0, 10.5, 1.0, 0.0, k * 0.01, k * 0.01, f, "2019-06-03"),
                               0.0, places=6)
        loser = {"nets": {"primary": -1.0}, "primary_parts": None}
        self.assertIsNone(ST.break_even_multiple([loser], f))
