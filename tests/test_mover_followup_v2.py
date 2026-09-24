"""Synthetic tests for protocol v2 families E (first-cross) and F (follow-up setups) (made-up bars)."""
import importlib.util
import sys
import unittest
from pathlib import Path

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HERE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/mover-early-entry"
DAY, PREV = "2023-03-15", "2023-03-14"


@unittest.skipUnless(HAS_NUMPY, "requires the pinned numpy runtime (protocol inputs.runtime)")
class FollowUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE))
        spec = importlib.util.spec_from_file_location("mover_fv2", HERE / "features_v2.py")
        cls.V = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.V)
        cls.R = cls.V.R

    def bar(self, hhmm, o, h, l, c, v=100_000):
        return (self.R.et_epoch(DAY, hhmm), o, h, l, c, v, c)

    def test_first_cross_takes_the_first_qualifying_bar(self):
        R = self.R
        rows = [self.bar("07:00", 10, 10, 10, 10), self.bar("07:10", 11, 11, 11, 11), self.bar("07:20", 12.1, 12.1, 12.1, 12.1),
                self.bar("07:30", 12.5, 12.5, 12.5, 12.5), self.bar("09:40", 13, 13, 13, 13)]
        b = R.Bars(*zip(*rows), day_start=R.et_epoch(DAY, "04:00"))
        ks = self.V.first_cross(b, DAY, 10.0, [], R.et_epoch(PREV, "16:00"))
        # bar 3 (07:30) is the first whose previous close (12.1) is >= +20%; dv before it = 3.31M
        self.assertEqual(ks["E|04:00-09:30|G0.20|V250000|any"], 3)
        self.assertEqual(ks["E|04:00-11:00|G0.20|V1000000|any"], 3)
        self.assertNotIn("E|04:00-11:00|G0.20|V5000000|any", ks)
        self.assertEqual(ks["E|09:30-11:00|G0.20|V250000|any"], 4)  # the regular-session window starts at 09:30
        self.assertNotIn("E|04:00-09:30|G0.20|V250000|news_before_t", ks)
        ks = self.V.first_cross(b, DAY, 10.0, [R.et_epoch(DAY, "07:28") + 30], R.et_epoch(PREV, "16:00"))
        self.assertEqual(ks["E|04:00-11:00|G0.20|V250000|news_before_t"], 4)  # 07:30 is < 120 s after the headline

    def test_orb_breakout_fill_and_exits_start_after_the_entry_bar(self):
        R = self.R
        rows = [self.bar("09:30", 12, 12.5, 11.8, 12.2), self.bar("09:34", 12.2, 12.6, 12.0, 12.4),
                self.bar("09:40", 12.5, 13.0, 11.5, 12.8),  # breaks 12.6; its low 11.5 is before or after the break: ignored (V2)
                self.bar("09:41", 12.8, 12.9, 11.9, 12.0),  # the range low 11.8 is not reached
                self.bar("09:42", 11.7, 11.7, 11.0, 11.2)]  # gap below the stop -> fill at the open
        b = R.Bars(*zip(*rows), day_start=R.et_epoch(DAY, "04:00"))
        found = self.V.setups(b, DAY)
        k, entry, stop, brk = found["F1_orb5"]
        self.assertEqual((k, entry, stop, brk), (2, 12.6, 11.8, True))
        ex, degen = self.V.y_exits(b, DAY, k, entry, stop, True, 12.0, R.et_epoch(DAY, "16:00"))
        self.assertEqual(ex["Y2"][0], 11.7)
        self.assertEqual(ex["Y4"][0], 11.7)
        self.assertFalse(degen)
        self.assertEqual(ex["Y1"][0], 12.0)

    def test_y3_trails_only_after_ten_percent(self):
        R = self.R
        rows = [self.bar("09:30", 10, 10, 10, 10), self.bar("09:31", 10, 11.2, 10, 11.1), self.bar("09:32", 11.0, 11.0, 10.0, 10.1)]
        b = R.Bars(*zip(*rows), day_start=R.et_epoch(DAY, "04:00"))
        ex, _ = self.V.y_exits(b, DAY, 0, 10.0, 9.0, False, 10.5, R.et_epoch(DAY, "16:00"))
        # running high 11.2 >= 11.0 -> level 0.9 x 11.2 = 10.08; bar 09:32 low 10.0 -> exit at min(10.08, 11.0)
        self.assertAlmostEqual(ex["Y3"][0], 10.08)


if __name__ == "__main__":
    unittest.main()
