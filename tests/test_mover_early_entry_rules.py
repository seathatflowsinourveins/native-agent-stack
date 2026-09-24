"""Synthetic tests for the mover early-entry rules (made-up bars; no private data)."""
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/mover-early-entry"
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("mover_rules", HERE / "rules.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

DAY = "2023-03-15"


def bar(hhmm, o, h, l, c, v=1000, vw=None):
    return {"t": R.et_epoch(DAY, hhmm), "o": o, "h": h, "l": l, "c": c, "v": v, "vw": vw if vw is not None else c}


def bars(*rows):
    return R.Bars.from_rows(list(rows), R.et_epoch(DAY, "04:00"))


def ex(entry, hhmm, rows, close):
    return R.exits_for(entry, R.et_epoch(DAY, hhmm), bars(*rows), DAY, close)


class Basics(unittest.TestCase):
    def test_split_factor_converts_a_reverse_split_and_ignores_dividend_drift(self):
        f, split = R.split_factor(0.50, 5.00, 7.50, 7.50)  # 1:10 reverse split effective on the session
        self.assertTrue(split)
        self.assertAlmostEqual(0.50 / f, 5.00)  # ref on the session's raw basis
        self.assertEqual(R.split_factor(10.0, 9.99, 11.0, 11.0), (1.0, False))  # 0.1% dividend drift
        self.assertEqual(R.split_factor(None, 9.99, 11.0, 11.0), (1.0, False))

    def test_state_uses_bars_starting_before_t_from_04_00(self):
        b = bars(bar("03:59", 1, 1, 1, 1.0, 999), bar("04:00", 1, 1, 1, 1.1, 100, 1.05),
                 bar("07:59", 1.2, 1.3, 1.2, 1.25, 200, 1.25), bar("08:00", 2, 2, 2, 2.0))
        price, dv = b.state(R.et_epoch(DAY, "08:00"))
        self.assertEqual(price, 1.25)
        self.assertAlmostEqual(dv, 1.05 * 100 + 1.25 * 200)
        self.assertEqual(bars().state(R.et_epoch(DAY, "08:00")), (None, 0.0))

    def test_news_needs_the_two_minute_lag(self):
        t = R.et_epoch(DAY, "08:00")
        self.assertFalse(R.news_before([t - 60], t, 120, t - 86400))
        self.assertTrue(R.news_before([t - 121], t, 120, t - 86400))
        self.assertFalse(R.news_before([t - 400], t, 600, t - 86400))
        self.assertFalse(R.news_before([t - 90000], t, 120, t - 86400))  # before the previous 16:00

    def test_degree_tiers_and_cost_buckets(self):
        self.assertEqual([R.degree_tier(g) for g in (-0.1, 0.3, 0.99, 1.0, 5.0, 12.0)],
                         ["-0.30", "0.30-0.50", "0.50-1.00", "1.00-3.00", "3.00-10.00", "10.00-"])
        self.assertEqual([R.time_bucket(DAY, R.et_epoch(DAY, x)) for x in ("04:00", "07:59", "09:25", "09:29", "09:30", "10:00", "16:00", "16:01")],
                         [0, 0, 1, 1, 2, 3, 3, None])
        self.assertEqual([R.price_tier(p) for p in (1.5, 2.0, 4.99, 5.0, 19.9, 20.0)], [0, 1, 1, 2, 2, 3])
        self.assertEqual([R.dv_tier(d) for d in (999_999, 1_000_000, 5_000_000)], [0, 1, 2])

    def test_fees_follow_the_dated_schedules(self):
        # 2021-03-01: SEC $5.10/M, TAF $0.000119 capped at $5.95.
        self.assertAlmostEqual(R.sell_fees("2021-03-01", 10_000, 20_000), 5.10 * 0.02 + 1.19)
        self.assertAlmostEqual(R.sell_fees("2021-03-01", 100_000, 200_000), 5.10 * 0.2 + 5.95)
        self.assertAlmostEqual(R.sell_fees("2025-06-02", 1000, 20_000), 0.166)  # SEC $0.00 from 2025-05-14
        self.assertAlmostEqual(R.ibkr_commission(10, 25.0), 0.25)  # 1% cap below the $0.35 minimum
        self.assertAlmostEqual(R.ibkr_commission(50, 1000.0), 0.35)
        self.assertAlmostEqual(R.ibkr_commission(10_000, 20_000.0), 35.0)
        # A flat trade with 1% per side costs about 2% plus fees.
        net = R.net_return(10.0, 10.0, 0.01, 0.01, "2025-06-02", 20_000)
        self.assertAlmostEqual(net, (20_000 * 0.99 - 0.332) / (20_000 * 1.01) - 1)
        self.assertLess(R.net_return(10.0, 10.0, 0.01, 0.01, "2025-06-02", 20_000, "ibkr"), net)


class Entries(unittest.TestCase):
    def test_premarket_entry_uses_the_next_bar_within_5_minutes_and_before_09_30(self):
        b = bars(bar("09:24", 1, 1, 1, 1), bar("09:26", 1.4, 1.5, 1.4, 1.45), bar("09:31", 2, 2, 2, 2))
        self.assertEqual(R.entry_for(DAY, "09:25", b, 1.9)[:3], (1.4, R.et_epoch(DAY, "09:26"), "bar_open"))
        late = bars(bar("09:24", 1, 1, 1, 1), bar("09:31", 2, 2, 2, 2))
        self.assertIsNone(R.entry_for(DAY, "09:25", late, 1.9)[0])  # nothing before 09:30
        self.assertIsNone(R.entry_for(DAY, "07:00", bars(bar("07:05", 1, 1, 1, 1)), None)[0])  # 5 min is outside
        self.assertEqual(R.entry_for(DAY, "07:00", bars(bar("07:04", 1, 1, 1, 1)), None)[0], 1)

    def test_opening_auction_entry_and_its_signal_cutoff(self):
        self.assertEqual(R.entry_for(DAY, "09:30", bars(), 3.21)[:3], (3.21, R.et_epoch(DAY, "09:30"), "opening_auction"))
        self.assertIsNone(R.entry_for(DAY, "09:30", bars(), None)[0])
        self.assertEqual(R.signal_cutoff(DAY, "09:30"), R.et_epoch(DAY, "09:28"))
        self.assertEqual(R.signal_cutoff(DAY, "09:35"), R.et_epoch(DAY, "09:35"))

    def test_exact_threshold_fires_and_early_close_ends_the_window(self):
        self.assertTrue(R.fires(6.0, 1e6, 6.0 / 5.0 - 1, False, 0.20, 250_000, "any"))  # C25
        day = "2023-11-24"  # a 13:00 early close (C26)
        rows = [{"t": R.et_epoch(day, "12:30"), "o": 10, "h": 10, "l": 10, "c": 10, "v": 1, "vw": 10},
                {"t": R.et_epoch(day, "13:30"), "o": 20, "h": 20, "l": 1, "c": 20, "v": 1, "vw": 20}]
        b = R.Bars.from_rows(rows, R.et_epoch(day, "04:00"))
        out, high, halt, src = R.exits_for(10.0, R.et_epoch(day, "12:30"), b, day, None, 11.0)
        self.assertEqual(out["X1"][:2], (11.0, R.et_epoch(day, "13:00")))
        self.assertEqual(src, "daily_close")
        self.assertEqual(out["X4"][0], 11.0)  # the post-close 13:30 bar is outside the window
        self.assertEqual(high, 10)

    def test_fires(self):
        self.assertTrue(R.fires(2.5, 2_000_000, 0.35, False, 0.30, 1_000_000, "any"))
        self.assertFalse(R.fires(2.5, 2_000_000, 0.35, False, 0.50, 1_000_000, "any"))
        self.assertFalse(R.fires(2.5, 2_000_000, 0.35, False, 0.30, 5_000_000, "any"))
        self.assertFalse(R.fires(2.5, 2_000_000, 0.35, False, 0.30, 1_000_000, "news_before_t"))
        self.assertTrue(R.fires(2.5, 2_000_000, 0.35, True, 0.30, 1_000_000, "news_before_t"))
        self.assertFalse(R.fires(0.9, 2_000_000, 0.35, False, 0.20, 250_000, "any"))
        self.assertFalse(R.fires(None, 0.0, None, False, 0.20, 250_000, "any"))


class Exits(unittest.TestCase):
    def test_trailing_uses_the_previous_bars_high_and_gap_fills_at_the_open(self):
        rows = [bar("09:35", 10, 12, 10, 12), bar("09:36", 12, 13, 12.5, 13), bar("09:37", 10, 10.5, 9, 9.5)]
        out, high, halt, src = ex(10.0, "09:35", rows, 9.0)
        self.assertEqual(out["X3"][:2], (10.0, R.et_epoch(DAY, "09:37")))  # level 11.05; opens at 10 -> the open
        self.assertEqual(high, 13)
        # A bar's own high does not raise its own trail level.
        self.assertEqual(ex(10.0, "09:35", [bar("09:35", 10, 14, 10.1, 13)], 12.0)[0]["X3"], (12.0, R.et_epoch(DAY, "16:00"), True))
        # The entry bar can stop out at the level (0.85 x entry).
        self.assertEqual(ex(10.0, "09:35", [bar("09:35", 10, 10, 8, 8.5)], 12.0)[0]["X3"][0], 8.5)

    def test_bracket_stop_first_and_open_gaps(self):
        self.assertEqual(ex(10.0, "09:35", [bar("09:35", 10, 16, 8, 12)], 12.0)[0]["X4"][0], 8.5)
        gap_up = [bar("09:35", 10, 10, 10, 10), bar("09:36", 16, 17, 15.5, 16)]
        self.assertEqual(ex(10.0, "09:35", gap_up, 12.0)[0]["X4"][0], 16)
        gap_down = [bar("09:35", 10, 10, 10, 10), bar("09:36", 7, 7.5, 6.5, 7)]
        self.assertEqual(ex(10.0, "09:35", gap_down, 12.0)[0]["X4"][0], 7)
        self.assertEqual(ex(10.0, "09:35", [bar("09:35", 10, 15.2, 9.9, 15)], 12.0)[0]["X4"][0], 15.0)
        self.assertEqual(ex(10.0, "09:35", [bar("09:35", 10, 11, 9, 10)], 12.0)[0]["X4"], (12.0, R.et_epoch(DAY, "16:00"), True))

    def test_time_exit_halt_flag_and_close_fallback(self):
        rows = [bar("09:35", 10, 10, 10, 10), bar("10:34", 11, 11, 11, 11), bar("10:35", 12, 12, 12, 12), bar("10:50", 13, 13, 13, 13)]
        out, high, halt, src = ex(10.0, "09:35", rows, None)
        self.assertEqual(out["X2"][:2], (12, R.et_epoch(DAY, "10:35")))  # first bar at or after 10:35
        self.assertTrue(halt)
        self.assertEqual(src, "bar_close")
        self.assertEqual(out["X1"][0], 13)  # the last bar's close when there is no official close
        self.assertEqual(ex(10.0, "15:30", [bar("15:30", 10, 10, 10, 10)], 11.0)[0]["X2"], (11.0, R.et_epoch(DAY, "16:00"), True))

    def test_halt_flag_counts_edges_and_interior_runs(self):
        full = [bar(f"{h:02d}:{m:02d}", 1, 1, 1, 1) for h in range(9, 16) for m in range(60) if (h, m) >= (9, 30)]
        self.assertFalse(R.halt_flag(bars(*full), R.et_epoch(DAY, "09:30"), DAY))
        four = [b for b in full if not (R.et_epoch(DAY, "11:00") <= b["t"] < R.et_epoch(DAY, "11:04"))]
        self.assertFalse(R.halt_flag(bars(*four), R.et_epoch(DAY, "09:30"), DAY))
        five = [b for b in full if not (R.et_epoch(DAY, "11:00") <= b["t"] < R.et_epoch(DAY, "11:05"))]
        self.assertTrue(R.halt_flag(bars(*five), R.et_epoch(DAY, "09:30"), DAY))
        late_start = [b for b in full if b["t"] >= R.et_epoch(DAY, "09:35")]
        self.assertTrue(R.halt_flag(bars(*late_start), R.et_epoch(DAY, "07:00"), DAY))  # 09:30-09:34 missing
        early_end = [b for b in full if b["t"] < R.et_epoch(DAY, "15:55")]
        self.assertTrue(R.halt_flag(bars(*early_end), R.et_epoch(DAY, "09:30"), DAY))


if __name__ == "__main__":
    unittest.main()
