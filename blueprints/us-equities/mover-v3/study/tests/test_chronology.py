"""chronology: segments with a dropped middle year, the embargo, censoring boundaries and none at N0."""
import unittest

from core import chronology as CH
from core import plan
from tests import synth


class Chronology(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()

    def test_dropped_middle_year_splits_development(self):
        segs = CH.stage_segments(self.cal, "development", frozenset({2018}))
        self.assertEqual(segs, [("2017-01-03", "2017-12-29"), ("2019-01-02", "2019-12-31")])
        kept = CH.kept_sessions(self.cal, "2017-01-03", "2019-12-31", frozenset({2018}))
        self.assertNotIn("2018-06-01", kept)
        self.assertEqual(kept[kept.index("2017-12-29") + 1], "2019-01-02")  # the bootstrap wraps over kept sessions

    def test_dropped_middle_year_breakpoints_and_bootstrap_wrap(self):
        """coverage_rule.dropped_year_consequences (a) and (c), review round 9, M-7: a dropped year's events never
        enter a trailing window, and the circular block bootstrap wraps over the kept sessions in date order."""
        import numpy as np
        from core import stats as ST
        from core import terciles as TC
        dy = frozenset({2018})
        pool = TC.pool_development(self.cal, dy)
        by = {d: [1.0 + (i % 3)] for i, d in enumerate(self.cal.range("2017-01-03", "2017-12-29"))}
        by.update({d: [500.0] for d in self.cal.range("2018-01-02", "2018-12-31")})
        s = "2019-01-15"
        bps = TC.breakpoints(pool, by, s)
        self.assertLess(bps[1], 500.0)                                   # no 2018 event in the window
        self.assertEqual(TC.trailing_window(pool, s)[-1], "2019-01-14")
        self.assertIn("2017-12-29", TC.trailing_window(pool, s))
        self.assertGreaterEqual(TC.breakpoints(TC.pool_development(self.cal), by, s)[1], 500.0)   # kept: it enters
        kept = CH.kept_sessions(self.cal, "2017-01-03", "2019-12-31", dy)
        n, L = len(kept), 10

        class Starts:                                                    # fixed block starts for the draw
            def integers(self, lo, hi, size):
                return np.array([[kept.index("2017-12-22")] + [n - 3] * (size[1] - 1)] * size[0])
        idx = ST._draw_indices(Starts(), n, L, 1)[0]
        first = [kept[i] for i in idx[:L]]
        self.assertEqual(first[:6], ["2017-12-22", "2017-12-26", "2017-12-27", "2017-12-28", "2017-12-29",
                                     "2019-01-02"])
        wrap = [kept[i] for i in idx[L: 2 * L]]
        self.assertEqual(wrap[:4], ["2019-12-27", "2019-12-30", "2019-12-31", "2017-01-03"])
        with self.assertRaises(ValueError):                              # a 2018 trade is in no kept session
            ST.session_arrays(kept, [{"session": "2018-06-01", "value": 1.0}])

    def test_embargo_after_a_dropped_year_and_at_validation_start(self):
        dy = frozenset({2018})
        segs = CH.stage_segments(self.cal, "development", dy)
        after = self.cal.range("2019-01-02", "2019-01-15")
        self.assertTrue(all(CH.embargoed(self.cal, "development", segs, d, dy) for d in after[:6]))
        self.assertFalse(CH.embargoed(self.cal, "development", segs, after[6], dy))
        self.assertFalse(CH.embargoed(self.cal, "development", segs, "2017-01-03", dy))  # after the warm-up: none
        vsegs = CH.stage_segments(self.cal, "validation")
        v = self.cal.range("2020-01-02", "2020-01-15")
        self.assertTrue(CH.embargoed(self.cal, "validation", vsegs, v[5], frozenset()))
        self.assertFalse(CH.embargoed(self.cal, "validation", vsegs, v[6], frozenset()))

    def test_no_embargo_at_n0_and_a_trade_entered_on_n0_is_kept(self):
        cal = synth.calendar("2026-06-01", "2028-06-30")
        n0 = "2026-11-23"
        seg = CH.holdout_segment(cal, n0)
        self.assertFalse(CH.embargoed(cal, "holdout", [seg], n0))
        t = cal.offset(n0, -1)
        e, x, censored = plan.planned_exit(cal, t, "b_lane", seg[1])
        self.assertFalse(censored)
        self.assertEqual(e, cal.offset(n0, 4))
        self.assertEqual(CH.segment_of([seg], cal.offset(t, 1)), 0)

    def test_decision_with_entry_in_no_segment_and_censoring(self):
        segs = CH.stage_segments(self.cal, "validation")
        self.assertIsNone(CH.segment_of(segs, self.cal.offset("2020-12-31", 1)))
        e, x, censored = plan.planned_exit(self.cal, "2020-12-28", "b_lane", segs[0][1])
        self.assertTrue(censored)
        self.assertEqual(e, "2020-12-31")
        self.assertEqual(x, self.cal.stamp_1555("2020-12-31"))

    def test_holdout_blocks(self):
        cal = synth.calendar("2026-06-01", "2028-12-29")
        n0 = "2026-11-23"
        for b, n in ((0, 252), (1, 315), (2, 378)):
            seg = CH.holdout_segment(cal, n0, b)
            self.assertEqual(len(cal.range(*seg)), n)
        with self.assertRaises(ValueError):
            CH.holdout_segment(cal, n0, 3)


if __name__ == "__main__":
    unittest.main()
