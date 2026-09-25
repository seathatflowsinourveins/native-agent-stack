"""SYN: synthetic tests for the Stocks-in-Play ORB rules (blueprints/us-equities/sota-mover/orb/orb_signal.py).

Made-up bars and daily rows only; no private data. Stdlib only (system python3).
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ORB = Path(__file__).resolve().parents[1] / "blueprints/us-equities/sota-mover/orb"
spec = importlib.util.spec_from_file_location("orb_signal_under_test", ORB / "orb_signal.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
FEES = json.loads((ORB.parents[1] / "mover-v3/data/fees-v3.json").read_text())

CLOSE = 960


def b(m, o, h, l, c, v=1000.0):  # noqa: E741
    return (m, o, h, l, c, v)


def flat(m, px):
    return b(m, px, px, px, px)


def no_spread(minute, price):
    return 0.0


def const(hs):
    return lambda minute, price: hs


class OpeningRangeAndDirection(unittest.TestCase):
    def test_opening_range_uses_0930_to_0934_only(self):
        bars = [b(569, 9, 99, 1, 9), b(570, 10, 11, 9.5, 10.5, 100), b(572, 10.5, 12, 10, 11, 200),
                b(574, 11, 11.5, 10.8, 11.2, 300), b(575, 11.2, 50, 1, 11, 999)]
        self.assertEqual(S.opening_range(bars), (10, 12, 9.5, 11.2, 600.0, 3))
        self.assertIsNone(S.opening_range([b(569, 1, 1, 1, 1), b(575, 1, 1, 1, 1)]))

    def test_direction_and_doji(self):
        self.assertEqual(S.direction(10.0, 10.5), 1)
        self.assertEqual(S.direction(10.0, 9.5), -1)
        self.assertEqual(S.direction(10.0, 10.0), 0)

    def test_doji_places_no_order(self):
        bars = [flat(575, 10), b(576, 10, 20, 1, 10)]
        self.assertIsNone(S.find_trigger(bars, 0, 10.0, CLOSE))
        self.assertIsNone(S.simulate_trade(bars, 0, 10.0, 1.0, CLOSE, "F1", const(0.001)))


class RelVolRanking(unittest.TestCase):
    def test_filters_order_and_ties(self):
        cands = [("ZZZ", 5.0), ("AAA", 5.0), ("BBB", 0.99), ("CCC", 1.0), ("DDD", None), ("EEE", 30.0)]
        self.assertEqual(S.select_top(cands, n=3), [("EEE", 30.0), ("AAA", 5.0), ("ZZZ", 5.0)])
        self.assertEqual([s for s, _ in S.select_top(cands)], ["EEE", "AAA", "ZZZ", "CCC"])

    def test_top_20_cap_and_doji_keeps_slot(self):
        cands = [(f"S{i:02d}", 100.0 - i) for i in range(25)]
        top = S.select_top(cands)
        self.assertEqual(len(top), 20)
        self.assertEqual(top[-1][0], "S19")  # a doji among the 20 is not replaced by S20

    def test_eligibility_thresholds(self):
        self.assertTrue(S.eligible(5.01, 1_000_000, 0.51))
        self.assertFalse(S.eligible(5.0, 1_000_000, 0.51))      # open must be above $5
        self.assertFalse(S.eligible(6.0, 999_999, 0.51))        # volume at least 1M
        self.assertFalse(S.eligible(6.0, 1_000_000, 0.50))      # ATR more than $0.50


def make_history(n=30, h=11.0, low=9.0, c=10.0, v=2e6, orv=1000.0):
    sessions = [f"2024-01-{i + 1:02d}" if i < 31 else f"2024-02-{i - 30:02d}" for i in range(n)]
    daily = {s: (c, c, v, c, h, low, c, v) for s in sessions}
    orr = {s: (c, h, low, c, orv, 5, 390) for s in sessions}
    return sessions, daily, orr


class FourteenDayWindows(unittest.TestCase):
    def test_values(self):
        sessions, daily, orr = make_history()
        atr, avgv, rv, split, reason = S.day_features(sessions, 20, daily, orr, 3000.0)
        self.assertEqual(reason, "")
        self.assertAlmostEqual(atr, 2.0)
        self.assertAlmostEqual(avgv, 2e6)
        self.assertAlmostEqual(rv, 3.0)
        self.assertEqual(split, 1.0)

    def test_no_look_ahead(self):
        sessions, daily, orr = make_history()
        i = 20
        base = S.day_features(sessions, i, daily, orr, 3000.0)
        for j in range(i, len(sessions)):  # session t and later: everything but t's share-adjustment ratio
            d = sessions[j]
            daily[d] = (99.0, 99.0, 9e9, 99.0, 999.0, 0.01, 99.0, 9e9)  # all_v/raw_v still 1
            orr[d] = (99.0, 999.0, 0.01, 99.0, 9e9, 5, 390)
        self.assertEqual(S.day_features(sessions, i, daily, orr, 3000.0), base)

    def test_window_edges(self):
        sessions, daily, orr = make_history()
        i = 20
        base = S.day_features(sessions, i, daily, orr, 3000.0)
        d16 = sessions[i - 16]  # outside every window
        daily[d16] = (1.0, 1.0, 1.0, 1.0, 500.0, 0.1, 1.0, 1.0)
        orr[d16] = (1.0, 1.0, 1.0, 1.0, 9e9, 5, 390)
        self.assertEqual(S.day_features(sessions, i, daily, orr, 3000.0), base)
        d15 = sessions[i - 15]  # the ATR's previous-close row only; OR window starts at t-14
        orr[d15] = (1.0, 1.0, 1.0, 1.0, 9e9, 5, 390)
        self.assertEqual(S.day_features(sessions, i, daily, orr, 3000.0), base)
        daily[d15] = (10.0, 10.0, 2e6, 10.0, 11.0, 9.0, 5.0, 2e6)  # previous close 5 widens t-14's true range
        self.assertGreater(S.day_features(sessions, i, daily, orr, 3000.0)[0], base[0])
        d14 = sessions[i - 14]
        orr[d14] = (10.0, 11.0, 9.0, 10.0, 15000.0, 5, 390)
        self.assertAlmostEqual(S.day_features(sessions, i, daily, orr, 3000.0)[2], 3000.0 / 2000.0)

    def test_zero_or_volume_versus_corpus_gap(self):
        sessions, daily, orr = make_history()
        i = 20
        orr[sessions[i - 3]] = (None, None, None, None, 0.0, 0, 390)  # traded, but not in 09:30-09:34
        self.assertAlmostEqual(S.day_features(sessions, i, daily, orr, 3000.0)[2], 3000.0 / (13000.0 / 14))
        del orr[sessions[i - 3]]  # no bar at all that day: the window is void
        self.assertEqual(S.day_features(sessions, i, daily, orr, 3000.0)[4], "relvol_window_invalid")
        del daily[sessions[i - 2]]
        self.assertEqual(S.day_features(sessions, i, daily, orr, 3000.0)[4], "daily_gap")

    def test_split_between_t_minus_1_and_t(self):
        sessions, daily, orr = make_history()
        i = 20
        for s in sessions[:i]:  # 2-for-1 on session i: earlier rows carry adjusted volume 2x raw, price / 2
            daily[s] = (10.0, 10.0, 1e6, 5.0, 5.5, 4.5, 5.0, 2e6)
        daily[sessions[i]] = (5.0, 5.0, 2e6, 5.0, 5.5, 4.5, 5.0, 2e6)
        atr, avgv, rv, split, reason = S.day_features(sessions, i, daily, orr, 2000.0)
        self.assertEqual((split, reason), (2.0, ""))
        self.assertAlmostEqual(atr, 1.0)       # $2 pre-split range is $1 in post-split dollars
        self.assertAlmostEqual(avgv, 2e6)      # 1M pre-split shares are 2M post-split shares
        self.assertAlmostEqual(rv, 1.0)        # 2000 post-split shares vs 1000 pre-split shares
        self.assertEqual(S.split_between(1.0, 1.0), 1.0)
        self.assertEqual(S.split_between(1.005, 1.0), 1.0)


class EntryStopExit(unittest.TestCase):
    ATR = 2.0  # stop distance 0.20

    def test_stop_entry_long_and_short(self):
        bars = [b(572, 10, 12, 9, 11), b(575, 11, 11.9, 10.9, 11.5), b(576, 11.5, 12.0, 11.4, 11.9),
                b(577, 11.9, 12.5, 11.85, 12.4)]
        self.assertEqual(S.find_trigger(bars, 1, 12.0, CLOSE), 2)   # the 572 bar is before 09:35
        t = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F0", no_spread)
        self.assertEqual((t["entry_minute"], t["entry_fill"], t["gap_entry"]), (576, 12.0, False))
        short = [b(575, 10, 10.2, 9.9, 10), b(576, 10, 10.1, 9.5, 9.6)]
        self.assertEqual(S.find_trigger(short, -1, 9.5, CLOSE), 1)
        self.assertIsNone(S.find_trigger(short, -1, 9.49, CLOSE))

    def test_no_trigger_at_or_after_close(self):
        bars = [flat(575, 10), b(960, 10, 20, 10, 20)]
        self.assertIsNone(S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F1", const(0.001)))

    def test_gap_through_entry(self):
        bars = [b(575, 12.5, 12.8, 12.4, 12.7), flat(959, 13.0)]
        f0 = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F0", no_spread)
        f1 = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F1", const(0.001))
        self.assertEqual(f0["entry_fill"], 12.0)
        self.assertEqual(f1["entry_base"], 12.5)
        self.assertAlmostEqual(f1["entry_fill"], 12.5 * 1.001)
        self.assertTrue(f1["gap_entry"])
        s1 = S.simulate_trade([b(575, 9.0, 9.1, 8.9, 9.0)], -1, 9.5, self.ATR, CLOSE, "F1", const(0.002))
        self.assertAlmostEqual(s1["entry_fill"], 9.0 * 0.998)

    def test_gap_through_stop_exit(self):
        bars = [b(575, 12.0, 12.1, 11.95, 12.05), b(600, 11.0, 11.1, 10.9, 11.0)]
        f0 = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F0", no_spread)
        f1 = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F1", const(0.001))
        self.assertAlmostEqual(f0["exit_fill"], 11.8)           # paper-exact: at the stop
        self.assertEqual(f1["exit_base"], 11.0)                  # gap-through: the bar open
        self.assertAlmostEqual(f1["exit_fill"], 11.0 * 0.999)
        self.assertEqual(f1["exit_reason"], "stop")

    def test_same_bar_resolves_against_the_trade(self):
        bars = [b(575, 11.9, 12.1, 11.7, 12.05), flat(959, 15.0)]
        for model in ("F0", "F1", "F2"):
            t = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, model, const(0.0))
            self.assertEqual(t["exit_reason"], "stop_same_bar", model)
            self.assertEqual(t["exit_minute"], 575)
            self.assertAlmostEqual(t["exit_base"], t["stop"])
        short = [b(575, 10.0, 10.3, 9.5, 10.2)]
        t = S.simulate_trade(short, -1, 9.9, self.ATR, CLOSE, "F0", no_spread)
        self.assertEqual((t["exit_reason"], t["exit_base"]), ("stop_same_bar", 9.9 + 0.2))

    def test_atr_stop_from_executed_fill(self):
        bars = [b(575, 12.0, 12.05, 11.95, 12.0), b(580, 12.0, 12.0, 11.80, 11.9), flat(959, 13)]
        t = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F0", no_spread)
        self.assertAlmostEqual(t["stop"], 11.8)
        self.assertEqual((t["exit_reason"], t["exit_minute"]), ("stop", 580))
        f1 = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F1", const(0.01))
        self.assertAlmostEqual(f1["stop"], 12.0 * 1.01 - 0.2)    # C4: from the fill after the half-spread
        self.assertEqual(f1["exit_minute"], 580)
        self.assertAlmostEqual(S.stop_price(-1, 10.0, 3.0), 10.3)

    def test_eod_exit_at_last_bar_before_close(self):
        bars = [b(575, 12.0, 12.1, 11.95, 12.05), flat(700, 12.5), flat(959, 13.25), flat(960, 20.0)]
        t = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F0", no_spread)
        self.assertEqual((t["exit_reason"], t["exit_minute"], t["exit_base"]), ("eod", 959, 13.25))
        early = S.simulate_trade(bars[:2] + [flat(779, 12.75), flat(780, 30)], 1, 12.0, self.ATR, 780, "F0",
                                 no_spread)
        self.assertEqual((early["exit_minute"], early["exit_base"]), (779, 12.75))
        only = S.simulate_trade([b(958, 11.9, 12.1, 11.95, 12.05)], 1, 12.0, self.ATR, CLOSE, "F0", no_spread)
        self.assertEqual((only["exit_reason"], only["exit_base"]), ("eod", 12.05))

    def test_f2_adds_two_bps(self):
        self.assertEqual(S.F2_EXTRA, 0.0002)
        self.assertAlmostEqual(S.adverse("F2", 1, 100.0, 0.001), 100.0 * 1.0012)
        self.assertAlmostEqual(S.adverse("F2", -1, 100.0, 0.001), 100.0 * 0.9988)
        self.assertAlmostEqual(S.adverse("F1", 1, 100.0, 0.001), 100.1)
        self.assertEqual(S.adverse("F0", 1, 10.0, 0.5), 10.0)

    def test_same_bar_favour_variant(self):
        bars = [b(575, 11.9, 12.1, 11.7, 12.05), b(576, 12.05, 12.3, 12.0, 12.2), flat(959, 15.0)]
        against = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F0", no_spread)
        favour = S.simulate_trade(bars, 1, 12.0, self.ATR, CLOSE, "F0", no_spread, same_bar="favour")
        self.assertTrue(against["same_bar"] and favour["same_bar"])
        self.assertEqual(against["exit_reason"], "stop_same_bar")
        self.assertEqual((favour["exit_reason"], favour["exit_base"]), ("eod", 15.0))
        clean = S.simulate_trade([b(575, 12.0, 12.1, 11.95, 12.05)], 1, 12.0, self.ATR, CLOSE, "F0", no_spread)
        self.assertFalse(clean["same_bar"])


class FeesRAndSizing(unittest.TestCase):
    def test_sell_fees_dated(self):
        # 2024-06-03: SEC $27.80 per million; TAF $0.000166/share capped at $8.30
        self.assertAlmostEqual(S.sell_fees(FEES, "2024-06-03", 100_000, 5_000_000), 139.0 + 8.3)
        self.assertAlmostEqual(S.sell_fees(FEES, "2024-06-03", 100, 5_000), 27.8 * 5_000 / 1e6 + 0.0166)
        # 2025-06-02: SEC rate 0 (FY2025); TAF still charged
        self.assertAlmostEqual(S.sell_fees(FEES, "2025-06-02", 100, 5_000), 0.0166)
        # 2017-03-01: SEC $21.80 per million; TAF $0.000119
        self.assertAlmostEqual(S.sell_fees(FEES, "2017-03-01", 1000, 10_000), 0.218 + 0.119)

    def test_trade_costs_side(self):
        self.assertAlmostEqual(S.trade_costs("F0", FEES, "2024-06-03", 1, 100, 10, 11), 0.7)
        long_ = S.trade_costs("F1", FEES, "2024-06-03", 1, 100, 10.0, 11.0)
        short = S.trade_costs("F1", FEES, "2024-06-03", -1, 100, 10.0, 11.0)
        self.assertAlmostEqual(long_, 27.8 * 1100 / 1e6 + 0.0166)   # the long sells at the exit
        self.assertAlmostEqual(short, 27.8 * 1000 / 1e6 + 0.0166)   # the short sells at the entry

    def test_net_r(self):
        r = S.net_r("F0", FEES, "2024-06-03", 1, 12.0, 12.4, 2.0)
        self.assertAlmostEqual(r, (0.4 - 0.007) / 0.2)
        r = S.net_r("F1", FEES, "2024-06-03", -1, 12.0, 11.8, 2.0)
        self.assertAlmostEqual(r, (0.2 - (27.8 * 12.0 / 1e6 + 0.000166)) / 0.2)

    def test_paper_sizing(self):
        # allocation 25000/20 = 1250; risk 12.5 / R 0.2 = 62.5 shares; cap 4 x 1250 / 10 = 500 shares
        self.assertAlmostEqual(S.paper_shares(25000, 10.0, 2.0), 62.5)
        # a small ATR hits the leverage cap: 12.5 / 0.01 = 1250 > 500
        self.assertAlmostEqual(S.paper_shares(25000, 10.0, 0.1), 500.0)
        self.assertAlmostEqual(S.unlevered_shares(25000, 10.0), 125.0)


if __name__ == "__main__":
    unittest.main()
