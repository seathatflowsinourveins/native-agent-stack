"""statistics and multiple_testing: seeded bootstrap, closed null side, empty draws, Holm m = 5, robustness,
MDE, labels and verdicts."""
import math
import unittest
from unittest import mock

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

    def test_holm_order_is_the_tie_break_rule(self):
        """Review round 12, F5: the step-down order comes from holm_order itself (holm steps down in it); tied p are
        ordered by the normal-tail p, then by item id. The adjusted p of tied items cannot depend on their order."""
        floor = 1 / 100_001
        p = {i: floor for i in ITEM_IDS}
        normal = {"H1-D": 0.3, "H1-D-b_lane-low": 0.1, "H3-a": 0.1, "H3-b": 0.2, "H3-c": 0.0}
        self.assertEqual(ST.holm_order(p, normal), ["H3-c", "H1-D-b_lane-low", "H3-a", "H3-b", "H1-D"])
        self.assertEqual(ST.holm_order(p), list(ITEM_IDS))                       # no normal p: item id order
        self.assertEqual(ST.holm_order(dict(p, **{"H1-D": 0.5}), normal)[-1], "H1-D")   # p first
        with mock.patch.object(ST, "holm_order", wraps=ST.holm_order) as spy:
            ST.holm(p, normal)
        spy.assert_called_once_with(p, normal)


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

    def test_top_session_tie_straddling_rank_five(self):
        # review round 10, F12: session sums s1 .09, s2 .08, s3 .07, s4 .06, then s5 and s6 tie at .05 across ranks
        # 5 and 6. s5 holds one trade (.05) and s6 two (.10 and -.05), so the two tie-breaks give different means:
        # dropping the earlier session (s5) keeps s6 and s7 -> (.10 - .05 - .03) / 3; dropping s6 would give .01
        trades = [{"session": s, "value": v} for s, v in (("s1", 0.09), ("s2", 0.08), ("s3", 0.07), ("s4", 0.06),
                                                          ("s6", 0.10), ("s6", -0.05), ("s5", 0.05), ("s7", -0.03))]
        self.assertAlmostEqual(ST.mean_without_top_sessions(trades), (0.10 - 0.05 - 0.03) / 3)
        self.assertNotAlmostEqual(ST.mean_without_top_sessions(trades), (0.05 - 0.03) / 2)


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

    def test_mde_exclusion_uses_the_two_sided_level_for_h3c(self):
        """Review round 12, F4: H3-c's bounds are at a = 0.05 / 10 on both sides. 8 of 1000 draws at -2 x MDE put
        the 0.005 quantile outside -MDE and the 0.01 quantile inside, so only the protocol level keeps the size."""
        mde = 0.01
        stats = np.concatenate([np.full(8, -2 * mde), np.linspace(-0.5 * mde, 0.5 * mde, 992)])
        self.assertLess(ST.bound(stats, 0.005), -mde)
        self.assertGreater(ST.bound(stats, 0.01), -mde)
        self.assertFalse(ST.mde_excluded("H3-c", stats, mde))
        self.assertFalse(ST.mde_excluded("H3-c", -stats, mde))                  # the upper side too
        self.assertTrue(ST.mde_excluded("H3-c", stats[8:], mde))
        # a one-sided item uses a = 0.05 / 5 on its side: the same draws exclude the size for 'less'
        self.assertTrue(ST.mde_excluded("H1-D", stats, mde))


class ConcentratedSessions(unittest.TestCase):
    """Review round 15, F06: undefined and degenerate bootstrap draws control both support and exclusion. Review
    round 16, F06: a fixed floor of 20 occupied entry sessions, identical for every item and every H1-D group,
    controls them too, alongside that bootstrap-implied rule."""

    def _h1d(self, n_sessions, per_group=100, spread=0.0):
        """H1-D rows at validation: each group has per_group trades spread over n_sessions sessions (L = 10 apart),
        every value 0 (+/- spread), so the group means coincide."""
        from core import evaluate as EV
        sessions = [f"s{i:03d}" for i in range(252)]
        occupied = [sessions[(i * 20) % 252] for i in range(n_sessions)]
        rows = []
        for k, g in enumerate(("high", "low")):
            for j in range(per_group):
                v = spread * ((j * (k + 2)) % 5 - 2)                  # values in {-2, .., 2} x spread, mean 0
                nets = {m: v for m in ("primary", "c0.5", "c2.0", "table_only", "stress")}
                rows.append({"session": occupied[(j + k) % n_sessions], "value": v, "group": g,
                             "rec": {"symbol": f"S{j}", "exit": "normal", "nets": nets}})
        return EV.item_result("H1-D", "validation", rows, sessions, "mover-v3-test", B=4000)

    def test_one_occupied_session_supports_no_exclusion(self):
        """The review's case: both H1-D groups meet the 100-trade minimum inside one entry session and their means
        coincide. Draws holding that session have difference 0, the others none. At e7529b47 bound() dropped the
        undefined draws, the interval was [0, 0] and the item was labelled 'not_supported_mde_excluded'."""
        res = self._h1d(1)
        self.assertTrue(res["n_ok"])
        self.assertEqual(res["occupied_sessions"], {"high": 1, "low": 1})
        self.assertGreater(res["inference"]["undefined_fraction"], 0.2)
        self.assertFalse(res["inference"]["valid"])
        self.assertFalse(res["mde_excluded"])
        label = ST.item_label("validation", "H1-D", p_stage=1.0, n_ok=True, robust_ok=True, mde_ok=res["mde_excluded"],
                              inference_ok=res["inference"]["valid"])
        self.assertEqual(label, "underpowered")

    def test_spread_sessions_restore_valid_inference(self):
        # 30 sessions clears both the bootstrap-implied rule and the round-16 occupied-session floor of 20
        res = self._h1d(30, spread=0.001)
        self.assertLessEqual(res["inference"]["undefined_fraction"], ST.tail_level("H1-D"))
        self.assertFalse(res["inference"]["insufficient_occupied_sessions"])
        self.assertTrue(res["inference"]["valid"])
        self.assertTrue(res["mde_excluded"])

    def test_occupied_session_floor_excludes_a_group_one_below_it(self):
        """Review round 16, F06: 19 occupied sessions per group already clears the bootstrap-implied rule (row
        spread far beyond the ~5-6 sessions it needs), but not the fixed floor of 20; the item can neither pass nor
        be MDE-excluded. On the code before this round (no floor), this case is valid and mde_excluded."""
        res = self._h1d(19, spread=0.001)
        self.assertEqual(res["occupied_sessions"], {"high": 19, "low": 19})
        self.assertLessEqual(res["inference"]["undefined_fraction"], ST.tail_level("H1-D"))  # the old rule alone passes
        self.assertTrue(res["inference"]["insufficient_occupied_sessions"])
        self.assertFalse(res["inference"]["valid"])
        self.assertFalse(res["mde_excluded"])
        label = ST.item_label("validation", "H1-D", p_stage=1.0, n_ok=True, robust_ok=True, mde_ok=res["mde_excluded"],
                              inference_ok=res["inference"]["valid"])
        self.assertEqual(label, "underpowered")

    def test_occupied_session_floor_met_at_exactly_twenty(self):
        """The boundary case: 20 occupied sessions per group meets the fixed floor exactly, and the old
        bootstrap-implied rule too, so the item is valid and (with a coinciding-mean draw) MDE-excluded."""
        res = self._h1d(20, spread=0.001)
        self.assertEqual(res["occupied_sessions"], {"high": 20, "low": 20})
        self.assertFalse(res["inference"]["insufficient_occupied_sessions"])
        self.assertEqual(res["inference"]["min_occupied_sessions"], 20)
        self.assertTrue(res["inference"]["valid"])
        self.assertTrue(res["mde_excluded"])

    def test_occupied_session_floor_is_reported_on_inference_check_and_mde_excluded_directly(self):
        """The floor gate in isolation, apart from the bootstrap-spread mechanics above: occupied=None (no count
        given) never triggers it, an int below core.stats.MIN_OCCUPIED_SESSIONS does for a cell or H3-c item, and
        for H1-D either group's count below it is enough. On the code before this round, inference_check and
        mde_excluded take no `occupied` argument at all and this call fails outright."""
        stats = np.random.default_rng(11).normal(size=5001)                    # passes the bootstrap-implied rule
        self.assertTrue(ST.inference_check("H3-a", stats)["valid"])
        self.assertFalse(ST.inference_check("H3-a", stats, occupied=19)["valid"])
        self.assertTrue(ST.inference_check("H3-a", stats, occupied=19)["insufficient_occupied_sessions"])
        self.assertTrue(ST.inference_check("H3-a", stats, occupied=20)["valid"])
        self.assertTrue(ST.inference_check("H1-D", stats, occupied={"high": 25, "low": 19})["insufficient_occupied_sessions"])
        self.assertTrue(ST.inference_check("H1-D", stats, occupied={"high": 20, "low": 20})["valid"])
        tight = np.linspace(-0.001, 0.001, 1001)                # ALTERNATIVE["H3-a"] == "greater"; bounds exclude 0.05
        self.assertTrue(ST.mde_excluded("H3-a", tight, 0.05))
        self.assertFalse(ST.mde_excluded("H3-a", tight, 0.05, occupied=19))
        self.assertTrue(ST.mde_excluded("H3-a", tight, 0.05, occupied=20))

    def test_degenerate_draws_support_neither_a_pass_nor_an_exclusion(self):
        stats = np.full(1000, 0.02)                               # every draw the same positive mean
        chk = ST.inference_check("H3-a", stats)
        self.assertTrue(chk["degenerate"])
        self.assertFalse(chk["valid"])
        self.assertFalse(ST.mde_excluded("H3-a", np.zeros(1000), 0.05))
        self.assertEqual(ST.item_label("validation", "H3-a", p_stage=0.001, n_ok=True, robust_ok=True, mde_ok=False,
                                       inference_ok=False), "underpowered")

    def test_conservative_bounds(self):
        rng = np.random.default_rng(3)
        x = rng.normal(size=5001)
        for q in (0.005, 0.01, 0.5, 0.99, 0.995):              # equal to numpy's linear quantile with no undefined draw
            self.assertAlmostEqual(ST.conservative_bound(x, q, upper=q > 0.5), float(np.quantile(x, q)), places=12)
        y = x.copy()
        y[:60] = np.nan                                          # 1.2% undefined
        self.assertEqual(ST.conservative_bound(y, 0.99, upper=True), float("inf"))
        self.assertEqual(ST.conservative_bound(y, 0.01, upper=False), float("-inf"))
        self.assertTrue(np.isfinite(ST.conservative_bound(y, 0.95, upper=True)))
        self.assertFalse(ST.inference_check("H3-a", y)["valid"])
        self.assertTrue(ST.inference_check("H3-a", x)["valid"])
        self.assertEqual(ST.tail_level("H3-c"), 0.005)


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

    def test_an_estimate_opposite_a_one_sided_alternative_never_passes(self):
        """Review round 12, F9: enforced by rule, whatever p_stage."""
        kw = dict(n_ok=True, robust_ok=True, mde_ok=False)
        for stage, name in (("development", "development pass"), ("validation", "screened"),
                            ("holdout", "supported (confirmatory)")):
            self.assertEqual(ST.item_label(stage, "H3-a", p_stage=0.001, **kw), name)
            self.assertNotEqual(ST.item_label(stage, "H3-a", p_stage=0.001, opposite=True, **kw), name)
        self.assertEqual(ST.item_label("validation", "H3-a", p_stage=0.001, opposite=True, n_ok=True, robust_ok=True,
                                       mde_ok=True), "not_supported_mde_excluded")

    def test_h3c_holdout_needs_the_validation_sign(self):
        kw = dict(n_ok=True, robust_ok=True, mde_ok=False)
        self.assertEqual(ST.item_label("holdout", "H3-c", p_stage=0.001, sign_ok=False, **kw), "underpowered")
        self.assertEqual(ST.item_label("holdout", "H3-c", p_stage=0.001, sign_ok=True, **kw), "supported (confirmatory)")

    def test_not_carried_precedes_the_minimum_sample(self):
        # review round 9, M-1: a holdout item the gate did not open is 'not carried', whatever its sample
        self.assertEqual(ST.item_label("holdout", "H3-b", p_stage=1.0, n_ok=False, robust_ok=False, mde_ok=False,
                                       carried=False), "not carried")
        self.assertEqual(ST.item_label("holdout", "H3-b", p_stage=1.0, n_ok=False, robust_ok=False, mde_ok=False),
                         "underpowered")

    def test_lineage_and_qualifiers(self):
        level = 0.05 / (1012 + 60 + 5)
        self.assertTrue(ST.lineage_confirmed(level, level))
        self.assertFalse(ST.lineage_confirmed(level, level * 1.01))
        self.assertFalse(ST.lineage_confirmed(1e-6, 0.01))
        self.assertEqual(ST.qualifiers("holdout", "supported (confirmatory)", False), ["lineage-unconfirmed"])
        self.assertEqual(ST.qualifiers("holdout", "supported (confirmatory)", True), [])
        self.assertEqual(ST.qualifiers("validation", "screened", False, ("transport-deviation",)),
                         ["transport-deviation"])
        labels = {"H1-D": "underpowered", "H1-D-b_lane-low": "underpowered", "H3-a": "underpowered",
                  "H3-b": "underpowered", "H3-c": "supported (confirmatory)"}
        v = ST.hypothesis_verdict("holdout", labels, {"H3-c": ["lineage-unconfirmed", "transport-deviation"]})
        self.assertEqual(v["H3"]["qualifiers"], ["lineage-unconfirmed", "transport-deviation"])

    def test_verdicts_come_from_the_primary_contrasts_and_cells_are_reported_apart(self):
        """Review round 15, F07: at e7529b47 H3 was 'screened' on H3-a alone (and H1 on H1-D-b_lane-low alone); a
        verdict now comes from H1-D or H3-c only, and a passing tradable cell is reported under profitability."""
        labels = {"H1-D": "not_supported_mde_excluded", "H1-D-b_lane-low": "screened", "H3-a": "screened",
                  "H3-b": "underpowered", "H3-c": "underpowered"}
        v = ST.hypothesis_verdict("validation", labels)
        self.assertEqual(v["H1"], {"verdict": "not supported", "items": ["H1-D"]})
        self.assertEqual(v["H3"], {"verdict": "inconclusive", "items": ["H3-c"]})
        prof = ST.profitability("validation", labels, {"H3-a": ["transport-deviation"]})
        self.assertEqual(prof["H3-a"], {"hypothesis": "H3", "label": "screened", "passes": True,
                                        "qualifiers": ["transport-deviation"]})
        self.assertEqual((prof["H1-D-b_lane-low"]["passes"], prof["H3-b"]["passes"]), (True, False))
        labels["H3-c"] = "screened"
        self.assertEqual(ST.hypothesis_verdict("validation", labels)["H3"]["verdict"], "screened")

    def test_verdicts_at_the_holdout(self):
        labels = {i: "not supported (holdout not read)" for i in ("H3-a", "H3-c")}
        labels.update({"H1-D": "not carried", "H1-D-b_lane-low": "not carried", "H3-b": "not carried"})
        v = ST.hypothesis_verdict("holdout", labels)
        self.assertEqual(v["H3"]["verdict"], "not supported (holdout not read)")
        self.assertNotIn("H1", v)               # review round 10, F8: a primary contrast that was not carried
        self.assertEqual(sorted(ST.profitability("holdout", labels)), ["H3-a"])
        labels["H3-c"] = "not carried"         # H3-a alone carried: no H3 verdict, the cell is reported apart
        self.assertEqual(ST.hypothesis_verdict("holdout", labels), {})
        self.assertEqual(ST.profitability("holdout", labels)["H3-a"]["label"], "not supported (holdout not read)")

    def test_a_contaminated_pass_is_inconclusive(self):
        # review round 10, F1: 'screened (contaminated holdout)' met the pass rule but supports no claim
        contaminated = "screened (contaminated holdout)"
        labels = {"H1-D": contaminated, "H1-D-b_lane-low": "not carried", "H3-a": "not carried",
                  "H3-b": "not carried", "H3-c": "not_supported_mde_excluded"}
        v = ST.hypothesis_verdict("holdout", labels)
        self.assertEqual((v["H1"]["verdict"], v["H3"]["verdict"]), ("inconclusive", "not supported"))


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
        self.assertLess(ST.split_p([0.1, 0.2, 0.15, 0.12], ["a", "b", "c", "d"], "greater"), 0.01)
        self.assertEqual(ST.split_p([0.1], ["a"], "greater"), 1.0)

    def test_split_p_clusters_trades_by_session(self):
        """Review round 12, Codex P2: ten session returns [-.10, .12] x 5 give p = 0.39; repeating each session's
        return across 100 trades adds no independent information and must not make the split significant."""
        vals = [-0.10, 0.12] * 5
        sess = [f"s{i}" for i in range(10)]
        p1 = ST.split_p(vals, sess, "greater")
        self.assertAlmostEqual(p1, 0.3925, places=3)
        p100 = ST.split_p([v for v in vals for _ in range(100)], [s for s in sess for _ in range(100)], "greater")
        self.assertAlmostEqual(p100, p1, places=12)
        self.assertEqual(ST.benjamini_hochberg({"a": p100, "b": 0.5}), {"a": False, "b": False})
        self.assertEqual(ST.split_p([0.1, 0.2, 0.3], ["a", "a", "a"], "greater"), 1.0)  # one session

    def test_two_way_cluster(self):
        vals = [0.1, -0.1, 0.2, 0.0]
        out = ST.two_way_cluster(vals, ["s1", "s1", "s2", "s2"], ["A", "B", "A", "B"])
        self.assertAlmostEqual(out["mean"], 0.05)
        self.assertGreater(out["se"], 0.0)

    def test_break_even_multiple(self):
        from core import costs
        from tests import synth
        from tests.test_costs import FEES
        f = costs.Fees(FEES, cal=synth.calendar())
        tr = {"nets": {"primary": None}, "primary_parts": (10_000.0, 10.0, 10.5, 1.0, 0.0, 0.01, 0.01, "2019-06-03")}
        k = ST.break_even_multiple([tr], f)
        self.assertAlmostEqual(costs.trade_net_return(10_000.0, 10.0, 10.5, 1.0, 0.0, k * 0.01, k * 0.01, f, "2019-06-03"),
                               0.0, places=6)
        loser = {"nets": {"primary": -1.0}, "primary_parts": None}
        self.assertIsNone(ST.break_even_multiple([loser], f))


if __name__ == "__main__":
    unittest.main()
