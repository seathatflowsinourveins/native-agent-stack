"""populations.formulas, official_prints, suspected_unadjusted_split and exclusions."""
import math
import unittest

import numpy as np

from core import formulas as FM
from tests import synth


class Prints(unittest.TestCase):
    def test_each_source_label(self):
        listing = synth.auction(10.0, 11.0, exchange="Q")
        self.assertEqual(FM.close_label(listing), "closing_print_listing_exchange")
        self.assertEqual(FM.official_close(listing), 11.0)
        self.assertEqual(FM.official_open(listing), 10.0)
        official = synth.auction(10.0, 11.5, exchange="Q", close_cond="M")
        self.assertEqual(FM.close_label(official), "official_close_listing_exchange")
        self.assertEqual(FM.official_close(official), 11.5)
        other = {"o": [{"c": "O", "p": 10.0, "s": 100, "x": "Q"}], "c": [{"c": "6", "p": 11.9, "s": 100, "x": "Z"}]}
        self.assertEqual(FM.close_label(other), "closing_print_other_exchange")
        self.assertIsNone(FM.official_close(other))  # the rejected label counts as no official close
        no_open = synth.auction(None, 11.0, no_open=True)
        self.assertEqual(FM.close_label(no_open), "no_opening_print")
        self.assertIsNone(FM.official_close(no_open))
        self.assertIsNone(FM.official_open(no_open))
        self.assertIsNone(FM.listing_exchange(no_open))
        self.assertEqual(FM.close_label(None), "no_print")

    def test_listing_exchange_is_largest_opening_print(self):
        day = {"o": [{"c": "O", "p": 10, "s": 50, "x": "P"}, {"c": "O", "p": 10.1, "s": 500, "x": "N"}],
               "c": [{"c": "6", "p": 12, "s": 10, "x": "P"}, {"c": "6", "p": 12.2, "s": 900, "x": "N"}]}
        self.assertEqual(FM.listing_exchange(day), "N")
        self.assertEqual(FM.official_close(day), 12.2)


class SplitFactors(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        s = self.cal.range("2020-03-02", "2020-03-31")
        self.s = s
        # 2:1 forward split effective on s[10]: raw halves
        self.raw, self.split, self.all = synth.series(self.cal, s[0], s[-1],
                                                      lambda d: 20.0 if d < s[10] else 10.0, split_at={s[10]: 2.0})

    def test_share_factor_split_day(self):
        self.assertEqual(FM.f_step(self.cal, self.raw, self.split, self.s[10]), 2.0)
        self.assertEqual(FM.f_step(self.cal, self.raw, self.split, self.s[11]), 1.0)
        self.assertEqual(FM.share_factor(self.raw, self.split, self.s[5], self.s[15]), 2.0)

    def test_tolerance_sets_small_factor_to_one(self):
        raw = {"a": {"c": 10.0}, "b": {"c": 10.0}}
        split = {"a": {"c": 10.0}, "b": {"c": 10.05}}
        self.assertEqual(FM.share_factor(raw, split, "a", "b"), 1.0)

    def test_missing_bar_makes_factor_undefined_not_one(self):
        raw = dict(self.raw)
        del raw[self.s[9]]
        self.assertIsNone(FM.f_step(self.cal, raw, self.split, self.s[10]))

    def test_split_on_a_session_without_bar_is_carried_by_F(self):
        s = self.s
        raw = {k: v for k, v in self.raw.items() if k != s[10]}
        split = {k: v for k, v in self.split.items() if k != s[10]}
        self.assertEqual(FM.share_factor(raw, split, s[9], s[11]), 2.0)

    def test_ref_and_gain_with_split_day(self):
        s = self.s
        prints = {d: synth.auction(b["c"], b["c"]) for d, b in self.raw.items()}
        prints[s[10]] = synth.auction(12.0, 12.5)  # +25% on the split-consistent basis: 12.5 vs 20 / 2
        ref = FM.ref_close(self.cal, prints, self.raw, self.split, s[10])
        self.assertAlmostEqual(ref, 10.0)
        self.assertTrue(FM.gain_passes(12.5, ref))
        self.assertTrue(FM.gain_passes(12.0, ref))  # exactly +20%: G - 1e-9
        self.assertFalse(FM.gain_passes(11.99, ref))

    def test_missing_previous_close_makes_ref_undefined(self):
        s = self.s
        prints = {d: synth.auction(b["c"], b["c"]) for d, b in self.raw.items()}
        prints[s[4]] = synth.auction(None, None, no_open=True)
        self.assertIsNone(FM.ref_close(self.cal, prints, self.raw, self.split, s[5]))


class Max21(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        s = self.cal.range("2019-12-02", "2020-02-28")
        self.s = s
        self.t = s[40]
        self.closes = {d: 10.0 + 0.1 * (i % 3) for i, d in enumerate(s)}
        self.raw, self.split, self.all = synth.series(self.cal, s[0], s[-1], lambda d: self.closes[d])
        self.prints = synth.prints_from(self.raw)

    def test_max_of_21_returns_before_t(self):
        m, why = FM.max21(self.cal, self.prints, self.raw, self.split, self.t)
        rs = [self.closes[self.cal.offset(self.t, -k)] / self.closes[self.cal.offset(self.t, -k - 1)] - 1
              for k in range(1, 22)]
        self.assertIsNone(why)
        self.assertAlmostEqual(m, max(rs))

    def test_event_session_not_in_window(self):
        prints = dict(self.prints)
        prints[self.t] = synth.auction(50.0, 50.0)
        m1, _ = FM.max21(self.cal, prints, self.raw, self.split, self.t)
        m0, _ = FM.max21(self.cal, self.prints, self.raw, self.split, self.t)
        self.assertEqual(m0, m1)

    def test_missing_close_in_window(self):
        prints = dict(self.prints)
        prints[self.cal.offset(self.t, -22)] = {"o": [], "c": []}
        self.assertEqual(FM.max21(self.cal, prints, self.raw, self.split, self.t), (None, "missing_close_or_factor"))

    def test_suspected_split_in_window(self):
        d = self.cal.offset(self.t, -7)
        raw = {k: dict(v) for k, v in self.raw.items()}
        split = {k: dict(v) for k, v in self.split.items()}
        prev = self.cal.offset(d, -1)
        raw[d]["c"] = raw[prev]["c"] * 3.0
        split[d]["c"] = raw[d]["c"]  # adjusted bars do not carry it: f = 1
        self.assertTrue(FM.suspected_at(self.cal, raw, split, d))
        self.assertEqual(FM.max21(self.cal, self.prints, raw, split, self.t), (None, "suspected_split_in_window"))

    def test_reverse_split_on_a_session_without_bar_inside_lookback(self):
        s = self.s
        k = s.index(self.t) - 10
        raw, split, _ = synth.series(self.cal, s[0], s[-1], lambda d: 10.0 if d < s[k] else 100.0,
                                     split_at={s[k]: 0.1}, missing=(s[k],))
        prints = {d: synth.auction(b["c"], b["c"]) for d, b in raw.items()}
        m, why = FM.max21(self.cal, prints, raw, split, self.t)
        self.assertIsNone(m)
        # inside a hold the same split is carried by F between the surrounding bars
        self.assertAlmostEqual(FM.share_factor(raw, split, s[k - 1], s[k + 1]), 0.1)


class SuspectedSplit(unittest.TestCase):
    def test_integer_ratio_with_f_one(self):
        self.assertTrue(FM.suspected_unadjusted_split(20.0, 10.0, 1.0))      # +100% (preregistered loss)
        self.assertTrue(FM.suspected_unadjusted_split(3.33, 10.0, 1.0))      # 1:3 reverse, within 1%
        self.assertFalse(FM.suspected_unadjusted_split(12.5, 10.0, 1.0))
        self.assertFalse(FM.suspected_unadjusted_split(20.0, 10.0, 2.0))     # carried by the adjusted bars
        self.assertFalse(FM.suspected_unadjusted_split(9.5, 10.0, 1.0))      # a 5% special dividend is not flagged
        self.assertTrue(FM.suspected_unadjusted_split(1000.0, 10.0, 1.0))    # n = 100
        self.assertFalse(FM.suspected_unadjusted_split(1500.0, 10.0, 1.0))   # n = 150 is outside 2..100


class MinuteQuantities(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        self.d = "2020-03-10"

    def test_dv_reg_counts_regular_session_only(self):
        pre = synth.minute_rows(self.cal, self.d, 10.0, 1000, start="08:00", n=90)
        reg = synth.minute_rows(self.cal, self.d, 10.0, 1000, start="09:30")
        post = [{"t": self.cal.close(self.d) + 60, "o": 10, "h": 10, "l": 10, "c": 10, "v": 1e6, "vw": 10}]
        self.assertAlmostEqual(FM.dv_reg(self.cal, pre + reg + post, self.d), 10.0 * 1000 * 390)
        self.assertEqual(FM.dv_reg(self.cal, pre, self.d), 0.0)

    def test_dv_reg_early_close(self):
        d = "2019-12-24"
        reg = synth.minute_rows(self.cal, d, 5.0, 100)
        self.assertEqual(len(reg), 210)
        self.assertAlmostEqual(FM.dv_reg(self.cal, reg, d), 5.0 * 100 * 210)

    def test_entry_bar_complete_before_decision(self):
        rows = synth.minute_rows(self.cal, self.d, 10.0, 1000, start="04:00", n=400)
        x = self.cal.at(self.d, "09:35")
        rows[-1]["v"] = 7
        dv = FM.entry_bar_dv(self.cal, rows, self.d, x)
        self.assertEqual(dv, 10.0 * 1000)
        late = [b for b in rows if b["t"] > x - 60]
        self.assertIsNone(FM.entry_bar_dv(self.cal, late, self.d, x))  # no completed bar: cap 0, a no-fill

    def test_med20_and_sigma(self):
        cal = self.cal
        t = "2020-03-10"
        w = FM.window_sessions(cal, t, 20)
        self.assertEqual(len(w), 20)
        self.assertEqual(w[-1], t)
        dv = {d: float(i + 1) for i, d in enumerate(w)}
        self.assertEqual(FM.med20(dv, w), 10.5)
        dv[w[3]] = None
        self.assertIsNone(FM.med20(dv, w))
        closes = {d: 10.0 * (1.01 ** i) for i, d in enumerate(cal.range("2020-01-02", "2020-03-31"))}
        raw, split, _ = synth.series(cal, "2020-01-02", "2020-03-31", lambda d: closes[d])
        prints = synth.prints_from(raw)
        self.assertAlmostEqual(FM.sigma_d(cal, prints, raw, split, w), 0.0, places=12)


class Exclusions(unittest.TestCase):
    def test_rule2_regex_and_slash(self):
        for sym in ("ABCDW", "ABCDU", "ABCDR", "XYZ.WS", "XYZ.U", "XYZ.W", "BRK/A"):
            self.assertTrue(FM.exclusion2(sym), sym)
        for sym in ("ABCD", "ABCW", "AAPL", "BRK.B", "ABCDEF"):
            self.assertFalse(FM.exclusion2(sym), sym)

    def test_rule3_counts_bars_in_t22_to_t1(self):
        cal = synth.calendar()
        t = "2020-03-10"
        prior = [cal.offset(t, -k) for k in range(1, 23)]
        raw = {d: {"c": 1.0} for d in prior}
        self.assertFalse(FM.exclusion3(cal, raw, t))
        del raw[prior[3]]
        self.assertFalse(FM.exclusion3(cal, raw, t))        # 21 of 22
        del raw[prior[9]]
        self.assertTrue(FM.exclusion3(cal, raw, t))         # 20 of 22 (E8: the per-event window)

    def test_rule1_counted_before_the_accepted_close(self):
        """Review round 9, M-7: a session with a close print but no listing-exchange opening print is exclusion 1,
        counted as such (before the accepted-close check, which it would otherwise always fail first)."""
        from collections import Counter
        from core import driver, plan, screen
        from core.store import Store
        from tests.test_identity import fixed_clock, issuer_data, transports
        cal = synth.calendar()
        sess = cal.range("2020-06-01", "2020-06-05")
        m = synth.FakeMarket(cal)
        for sym, no_open in (("LIST", False), ("OTCX", True)):
            daily, prints = issuer_data(cal, cal.offset(sess[0], -1), sess[-1],
                                        lambda d: 5.0 if d < "2020-06-03" else 7.0)
            if no_open:
                prints = {d: synth.auction(b["o"], b["c"], no_open=True) for d, b in daily["raw"].items()}
            m.add(sym, [("2015-01-01", sym)], daily=daily, auctions=prints)
        store = Store()
        reqs = [r for s in sess for r in plan.screen_requests(cal, s, ["LIST", "OTCX"])]
        driver.stage_fetch(lambda st: reqs, transports(m), store, "2026-12-01", clock=fixed_clock)
        cands, counts, _ = screen.candidates(store, cal, sess, ["LIST", "OTCX"], set())
        self.assertEqual([(c["symbol"], c["t"]) for c in cands], [("LIST", "2020-06-03")])
        self.assertEqual(counts["not_event:exclusion1_not_listed"], len(sess))
        self.assertNotIn("not_event:no_accepted_official_close", Counter(counts))


class LeastExposed(unittest.TestCase):
    """exposure_registry.consequence's slice, restated from broad-universe at aa6fc79 (review round 9, L-7)."""

    def setUp(self):
        self.cal = synth.calendar()
        self.t = "2020-06-01"
        self.prior = [self.cal.offset(self.t, -k) for k in range(0, 61)]

    def raw(self, close=5.0, volume=1_000_000):
        return {d: {"c": close, "v": volume} for d in self.prior}

    def test_a_lane_decision_is_not_least_exposed(self):
        self.assertFalse(FM.least_exposed(self.cal, self.raw(), self.t))           # med20 = $5M, 60 bars, >= $1

    def test_each_condition(self):
        cal, t = self.cal, self.t
        self.assertTrue(FM.least_exposed(cal, self.raw(volume=390_000), t))        # med20 $1.95M < $2M
        self.assertFalse(FM.least_exposed(cal, self.raw(volume=400_000), t))       # med20 exactly $2M
        low = self.raw()
        low[t] = {"c": 0.95, "v": 1_000_000}
        self.assertTrue(FM.least_exposed(cal, low, t))                             # raw close < $1 on t
        gap = self.raw()
        del gap[cal.offset(t, -45)]
        self.assertTrue(FM.least_exposed(cal, gap, t))                             # has_gap inside 60 sessions
        short = {d: v for d, v in self.raw().items() if d >= cal.offset(t, -59)}
        self.assertTrue(FM.least_exposed(cal, short, t))                           # 59 prior bars
        nobar = self.raw()
        del nobar[t]
        self.assertTrue(FM.least_exposed(cal, nobar, t))                           # no bar on t


if __name__ == "__main__":
    unittest.main()
