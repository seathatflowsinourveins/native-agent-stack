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
