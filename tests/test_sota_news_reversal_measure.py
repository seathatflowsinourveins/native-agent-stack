"""SYN: news-reversal/measure_s.py - the return-free planning measurement (S, leg statistics, sd scaling).

Synthetic events, labels and quotes only; the private study inputs are never opened here.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "blueprints/us-equities/sota-mover/news-reversal"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ms = load("news_reversal_measure_under_test", STUDY / "measure_s.py")


def ev(i, sym, session, minute=0, ssr=False, prior=100.0):
    return {"event_id": f"{i}:{sym}", "news_id": str(i), "symbol": sym, "session": session, "window": "rth",
            "lane": "liquid", "entry_utc": f"{session}T14:{minute:02d}:00Z", "prior_close": prior, "ssr_carryover": ssr,
            "exchange": "NYSE"}


def quote(bid, ask):
    return {"bid": bid, "ask": ask, "t": "x"}


class Spread(unittest.TestCase):
    def test_full_spread_in_bps_of_mid(self):
        self.assertAlmostEqual(ms.spread_bps(quote(99.95, 100.05)), 10.0)
        self.assertAlmostEqual(ms.spread_bps(quote(10.0, 10.02)), 0.02 / 10.01 * 1e4)


class News3Selection(unittest.TestCase):
    def world(self):
        d = "2024-03-01"
        events = [ev(1, "L1", d), ev(2, "L2", d, 1), ev(3, "S1", d, 2, prior=50.0), ev(4, "S2", d, 3, prior=50.0),
                  ev(5, "S3", d, 4, ssr=True, prior=50.0), ev(6, "NOC", d, 5), ev(7, "NOQ", d, 6), ev(8, "UNC", d, 7)]
        sides = {"1:L1": 1, "2:L2": 1, "3:S1": -1, "4:S2": -1, "5:S3": -1, "6:NOC": 1, "7:NOQ": 1, "8:UNC": 0}
        quotes = {"1:L1": quote(99.95, 100.05), "2:L2": quote(99.9, 100.1), "3:S1": quote(49.99, 50.01),
                  "4:S2": quote(49.95, 50.05), "5:S3": quote(49.95, 50.05), "6:NOC": quote(10, 10.01), "8:UNC": quote(1, 1.1)}
        has_close = {(e["symbol"], e["session"]): e["symbol"] != "NOC" for e in events}
        return events, sides, quotes, has_close

    def test_positions_days_and_s(self):
        positions = ms.news3_positions(*self.world())
        # S3 is a Rule 201-flagged short (carry-over), NOC has no official close, NOQ no entry quote, UNC no side
        self.assertEqual(sorted((p["side"], round(p["spread_bps"], 6)) for p in positions),
                         [(-1, 4.0), (-1, 20.0), (1, 10.0), (1, 20.0)])
        days = ms.long_short_days(positions)
        s, n = ms.spread_term(days)
        self.assertEqual(n, 1)
        self.assertAlmostEqual(s, (10.0 + 20.0) / 2 + (4.0 + 20.0) / 2)  # long leg mean + short leg mean
        inv, _ = ms.inverse_size_mean(days)
        self.assertAlmostEqual(inv, 1 / 2 + 1 / 2)

    def test_a_day_needs_two_names_in_each_leg(self):
        events, sides, quotes, has_close = self.world()
        sides["2:L2"] = 0
        self.assertEqual(ms.long_short_days(ms.news3_positions(events, sides, quotes, has_close)), {})

    def test_outside_the_segment_is_ignored(self):
        events, sides, quotes, has_close = self.world()
        for e in events:
            e["session"] = "2015-12-31"
        self.assertEqual(ms.news3_positions(events, sides, quotes, has_close), [])


class ReversalLegs(unittest.TestCase):
    def test_sides_flip_and_forward_filters(self):
        d = "2025-06-02"
        events = [ev(i, f"F{i}", d, i, prior=50.0) for i in range(14)] + [
            ev(100, "U1", d, 30, prior=50.0), ev(101, "U2", d, 31, prior=50.0), ev(102, "WIDE", d, 32, prior=50.0),
            ev(103, "SSR", d, 33, prior=60.0)]
        sides = {e["event_id"]: 1 for e in events[:14]}  # 14 FAVORABLE -> reversal shorts
        sides.update({"100:U1": -1, "101:U2": -1, "102:WIDE": -1, "103:SSR": 1})
        quotes = {e["event_id"]: quote(49.99, 50.01) for e in events}
        quotes["102:WIDE"] = quote(49.0, 50.0)  # 202 bps
        has_close = {}
        fwd = ms.reversal_legs(events, sides, quotes, has_close, ms.FORWARD_CHECKPOINT_SEGMENT, forward_like=True)
        self.assertEqual(len(fwd[d][-1]), 12)  # FAVORABLE shorts capped at 12 by entry time
        self.assertEqual(len(fwd[d][1]), 2)  # U1, U2 long; WIDE skipped above 50 bps
        # the 13th and 14th FAVORABLE names and SSR (bid 49.99 <= 90% of its 60.00 prior close) never enter
        self.assertEqual(len([p for p in fwd[d][-1] if p["side"] == -1]), 12)
        study = ms.reversal_legs(events, sides, quotes, has_close, ms.FORWARD_CHECKPOINT_SEGMENT, forward_like=False)
        self.assertEqual(dict(study), {})  # study-consistent needs an official close, none here
        stats = ms.leg_statistics(fwd, [d, "2025-06-03"])
        self.assertEqual((stats["sessions"], stats["both_legs_ge_2_sessions"], stats["both_legs_ge_2_rate"]), (2, 1, 0.5))
        self.assertEqual((stats["names_short"]["share_at_12"], stats["names_long"]["share_ge_2"]), (0.5, 0.5))

    def test_rule_201_on_the_reversal_short(self):
        d = "2025-06-02"
        events = [ev(1, "A", d, prior=50.0), ev(2, "B", d, 1, prior=60.0)]
        sides = {"1:A": 1, "2:B": 1}
        quotes = {"1:A": quote(49.99, 50.01), "2:B": quote(49.99, 50.01)}  # B: bid 49.99 <= 0.9 x 60
        legs = ms.reversal_legs(events, sides, quotes, {}, ms.FORWARD_CHECKPOINT_SEGMENT, forward_like=True)
        self.assertEqual(len(legs[d][-1]), 1)


class Label(unittest.TestCase):
    def test_confirmatory_only_from_five_bps(self):
        self.assertEqual(ms.planning_label(6.0)[1], "confirmatory")  # 11.0083 - 6.0 = 5.0083
        self.assertEqual(ms.planning_label(6.0083)[1], "confirmatory")
        self.assertEqual(ms.planning_label(6.01)[1], "exploratory")
        self.assertEqual(ms.planning_label(None), (None, None))
        effect, _ = ms.planning_label(2.0)
        self.assertAlmostEqual(effect, 9.0083)

    def test_the_protocol_states_the_same_rule(self):
        p = json.loads((STUDY / "forward-protocol.json").read_text())["planning_measurement"]
        self.assertIn("11.0083 - S >= 5.0", p["label_rule"])
        self.assertEqual((ms.IN_SAMPLE_GROSS_BPS, ms.CONFIRMATORY_MIN_EFFECT_BPS), (11.0083, 5.0))


class Inputs(unittest.TestCase):
    def test_refuses_missing_or_unpinned_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ms.Refusal):
                ms.verify_inputs(tmp)
            self.assertEqual(ms.main(["--data-root", tmp]), 2)


if __name__ == "__main__":
    unittest.main()
