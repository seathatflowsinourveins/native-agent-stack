"""populations.fill_quote: prevailing, stale, locked, none inside the timeout, regular session; last eligible bid."""
import unittest

from core import fills
from tests import synth
from tests.synth import quote


class FillQuote(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        self.d = "2020-03-10"
        self.x = self.cal.at(self.d, "09:35")

    def test_fresh_prevailing_quote_fills_at_x(self):
        qs = [quote(self.x - 0.4, 10.0, 10.2), quote(self.x + 5, 11.0, 11.2)]
        ts, q, how = fills.fill_at(self.cal, qs, self.x, self.x + 300)
        self.assertEqual((ts, q["bp"], how), (self.x, 10.0, "prevailing"))
        ts, q, how = fills.fill_at(self.cal, [quote(self.x - 1.0, 10.0, 10.2)], self.x, self.x + 300)
        self.assertEqual(how, "prevailing")  # exactly 1000 ms old is allowed

    def test_stale_prevailing_quote_waits_for_next(self):
        qs = [quote(self.x - 1.5, 10.0, 10.2), quote(self.x + 7, 11.0, 11.2)]
        ts, q, how = fills.fill_at(self.cal, qs, self.x, self.x + 300)
        self.assertEqual((ts, q["bp"], how), (self.x + 7, 11.0, "next"))

    def test_locked_and_crossed_quotes_are_skipped_one_by_one(self):
        qs = [quote(self.x - 0.2, 10.0, 10.0), quote(self.x + 1, 10.5, 10.4), quote(self.x + 2, 0, 10.4),
              quote(self.x + 3, 10.1, 10.3)]
        ts, q, how = fills.fill_at(self.cal, qs, self.x, self.x + 300)
        self.assertEqual((ts, q["bp"]), (self.x + 3, 10.1))

    def test_no_quote_inside_timeout(self):
        qs = [quote(self.x + 301, 10.0, 10.2)]
        self.assertIsNone(fills.fill_at(self.cal, qs, self.x, self.x + 300))
        self.assertIsNone(fills.fill_at(self.cal, [], self.x, self.x + 300))

    def test_premarket_and_after_close_quotes_are_not_eligible(self):
        open_ = self.cal.open(self.d)
        self.assertFalse(fills.eligible(self.cal, quote(open_ - 0.5, 10, 10.2)))
        self.assertTrue(fills.eligible(self.cal, quote(open_, 10, 10.2)))
        self.assertFalse(fills.eligible(self.cal, quote(self.cal.close(self.d), 10, 10.2)))
        # an exit at 09:30 does not take a fresh pre-market quote as prevailing
        qs = [quote(open_ - 0.3, 10, 10.2), quote(open_ + 2, 9, 9.2)]
        ts, q, _ = fills.fill_at(self.cal, qs, open_, self.cal.close(self.d))
        self.assertEqual(q["bp"], 9)

    def test_mid_and_half_spread(self):
        q = quote(self.x, 9.9, 10.1)
        self.assertAlmostEqual(fills.mid(q), 10.0)
        self.assertAlmostEqual(fills.half_spread(q), 0.01)

    def test_last_eligible_bid(self):
        e = self.x
        stamp = self.cal.at("2020-03-16", "15:55")
        qs = [quote(e - 1, 5, 5.1), quote(e + 60, 10, 10.2), quote(self.cal.at("2020-03-12", "11:00"), 12, 12.1),
              quote(self.cal.at("2020-03-12", "11:01"), 13, 13.0), quote(stamp + 10, 14, 14.1)]
        self.assertEqual(fills.last_eligible_bid(self.cal, qs, e, stamp)[0], 12.0)
        self.assertIsNone(fills.last_eligible_bid(self.cal, qs[:1], e, stamp))



class NanosecondOrder(unittest.TestCase):
    def test_updates_nanoseconds_apart_keep_their_order(self):
        """Review round 12, Codex P2: stamps 9 ns apart collapsed to one float and were reordered by price, so an
        older 10/10.2 quote became the prevailing one after a newer locked 9/9 update and filled."""
        import json
        from core import records
        cal = synth.calendar()
        body = {"quotes": {"AAA": [{"t": "2020-03-10T13:35:00.000000001Z", "bp": 10.0, "ap": 10.2, "bs": 1, "as": 1},
                                   {"t": "2020-03-10T13:35:00.000000010Z", "bp": 9.0, "ap": 9.0, "bs": 1, "as": 1}]},
                "next_page_token": None}
        qs = records.merge_quotes([records.PARSERS["quotes"](json.loads(json.dumps(body)))["AAA"]])
        self.assertEqual([q["bp"] for q in qs], [10.0, 9.0])
        self.assertEqual(records.ts_ns("2020-03-10T13:35:00.000000010Z") - records.ts_ns("2020-03-10T13:35:00.000000001Z"), 9)
        x = cal.at("2020-03-10", "09:35") + 0.5
        self.assertIsNone(fills.fill_at(cal, qs, x, x + 300))  # the prevailing quote is the locked one: no entry
        # a repeat of one update across a page boundary is kept once
        self.assertEqual(len(records.merge_quotes([qs, qs[1:]])), 2)

    def test_identical_updates_inside_a_page_keep_the_provider_order(self):
        """Review round 13, Codex P2: [eligible A, locked B, eligible A] on one nanosecond stamp. The provider's
        last update (A) prevails; before the fix every repeat of (stamp, quote) was dropped, the locked B
        prevailed and the fill was lost."""
        import json
        from core import records
        cal = synth.calendar()
        a = {"t": "2020-03-10T13:35:00.000000005Z", "bp": 10.0, "ap": 10.2, "bs": 1, "as": 1}
        b = {"t": "2020-03-10T13:35:00.000000005Z", "bp": 9.0, "ap": 9.0, "bs": 1, "as": 1}
        page = records.PARSERS["quotes"](json.loads(json.dumps({"quotes": {"AAA": [a, b, a]}})))["AAA"]
        qs = records.merge_quotes([page])
        self.assertEqual([q["bp"] for q in qs], [10.0, 9.0, 10.0])
        x = cal.at("2020-03-10", "09:35") + 0.5
        got = fills.fill_at(cal, qs, x, x + 300)
        self.assertIsNotNone(got)
        self.assertEqual((got[2], got[1]["bp"]), ("prevailing", 10.0))
        # across a page boundary the repeated last update is still kept once, and the page's own order stands
        self.assertEqual([q["bp"] for q in records.merge_quotes([page, page[2:]])], [10.0, 9.0, 10.0])

if __name__ == "__main__":
    unittest.main()
