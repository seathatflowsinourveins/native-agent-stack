"""universe_and_identity: FB/META through the pinned dedupe_identity (DuckDB), ticker reuse, a rename inside a hold,
a split and a rename inside one hold, empty responses, the asof refusal, enumeration and record date fields."""
import json
import unittest

from core import driver, events, identity, plan, records, screen
from core import formulas as FM
from core.store import Store
from fetch.transport import Transport
from tests import synth


def transports(market):
    return {"data": Transport(opener=market.opener, headers={}, sleep=lambda s: None),
            "trading": Transport(opener=market.opener, headers={}, sleep=lambda s: None)}


def fixed_clock():
    return "2026-12-01T00:00:00Z"


def issuer_data(cal, first, last, close_fn, split_at=None, jump=None):
    raw, split, allc = synth.series(cal, first, last, close_fn, split_at=split_at)
    return {"raw": raw, "split": split, "all": allc}, synth.prints_from(raw)


class FbMeta(unittest.TestCase):
    def test_renamed_away_ticker_served_under_both_symbols_gives_one_event(self):
        cal = synth.calendar()
        sess = cal.range("2020-05-01", "2020-06-30")
        jump = sess[35]
        daily, prints = issuer_data(cal, cal.offset(sess[0], -1), sess[-1],
                                    lambda d: 10.0 if d < jump else 12.5)
        m = synth.FakeMarket(cal)
        m.add("meta", [("2015-01-01", "META")], daily=daily, auctions=prints)
        m.aliases_any_asof["FB"] = "meta"
        store = Store()
        reqs = [r for s in sess for r in plan.screen_requests(cal, s, ["FB", "META"])]
        driver.to_fixpoint(lambda st: reqs, transports(m), store, "2026-12-01", clock=fixed_clock)
        renames = {("FB", "META")}
        cands, counts, report = screen.candidates(store, cal, sess, ["FB", "META"], renames)
        self.assertEqual([(c["symbol"], c["t"]) for c in cands], [("META", jump)])
        self.assertEqual(report["by_rule"], {"rename_record": 1})
        self.assertEqual(counts["dedupe_rows_removed"], len(sess))

    def test_dedupe_without_rename_record_and_same_session_guard(self):
        rows = []
        cal = synth.calendar()
        for i, s in enumerate(cal.range("2020-01-02", "2020-02-28")):
            for sym in ("AAA", "BBB"):
                rows.append({"symbol": sym, "session": s, "o": 1 + i, "h": 2 + i, "l": 0.5, "c": 1.5 + i, "v": 100})
        out = identity.dedupe_screen(rows, set(), frozenset({"BBB"}))
        self.assertEqual({s for s, _ in out["kept"]}, {"BBB"})
        self.assertEqual(out["report"]["by_rule"], {"active_status": 1})
        c = [{"symbol": "XX", "session": "2020-03-02", "ohlcv": (1, 2, 1, 2, 10), "ohlcv_prev": (1, 1, 1, 1, 5)},
             {"symbol": "YY", "session": "2020-03-02", "ohlcv": (1, 2, 1, 2, 10), "ohlcv_prev": (1, 1, 1, 1, 5)},
             {"symbol": "ZZ", "session": "2020-03-02", "ohlcv": (1, 2, 1, 2, 10), "ohlcv_prev": (1, 1, 1, 1, 6)}]
        kept, removed = identity.same_session_guard(c, {("XX", "YY")})
        self.assertEqual([k["symbol"] for k in kept], ["YY", "ZZ"])
        self.assertEqual([r["symbol"] for r in removed], ["XX"])


class AsofIdentity(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()

    def _fetch(self, m, reqs):
        store = Store()
        driver.to_fixpoint(lambda st: reqs, transports(m), store, "2026-12-01", clock=fixed_clock)
        return store

    def test_ticker_reuse_resolves_the_old_issuer_at_asof_t(self):
        cal = self.cal
        t = "2018-03-01"
        old, _ = issuer_data(cal, "2017-09-01", "2018-05-31", lambda d: 5.0)
        new, _ = issuer_data(cal, "2017-09-01", "2019-12-31", lambda d: 50.0)
        m = synth.FakeMarket(cal)
        m.add("old", [("2015-01-01", "ABC"), ("2018-06-01", "ABCQ")], daily=old)
        m.add("new", [("2019-03-01", "ABC")], daily=new)
        reqs = plan.event_requests(cal, "ABC", t, cal.offset(t, 10))
        store = self._fetch(m, reqs)
        raw = store.parsed(reqs[0]["key"])["ABC"]
        self.assertEqual(raw[t]["c"], 5.0)
        default = plan.make("count_default_asof_daily_raw", "data", "/v2/stocks/bars",
                            {"symbols": "ABC", "timeframe": "1Day", "start": t, "end": t, "adjustment": "raw"}, None,
                            "daily_bars")
        store2 = self._fetch(m, [default])
        self.assertEqual(store2.parsed(default["key"])["ABC"][t]["c"], 50.0)

    def test_rename_inside_a_hold_returns_the_whole_hold(self):
        cal = self.cal
        t = "2020-06-01"
        d3 = cal.offset(t, 3)
        daily, prints = issuer_data(cal, cal.offset(t, -60), cal.offset(t, 12), lambda d: 10.0)
        m = synth.FakeMarket(cal)
        m.add("x", [("2015-01-01", "OLDN"), (d3, "NEWN")], daily=daily, auctions=prints)
        end = cal.offset(t, 10)
        reqs = plan.event_requests(cal, "OLDN", t, end)
        store = self._fetch(m, reqs)
        data = events.event_data(store, cal, "OLDN", t, end)
        self.assertIn(cal.offset(t, 8), data["daily"]["raw"])
        self.assertIn(cal.offset(t, 8), data["prints"])
        self.assertEqual(data["incomplete"], [])

    def test_split_and_rename_inside_one_hold_use_per_event_responses(self):
        cal = self.cal
        t = "2020-06-01"
        d2, d3 = cal.offset(t, 2), cal.offset(t, 3)
        daily, prints = issuer_data(cal, cal.offset(t, -60), cal.offset(t, 12),
                                    lambda d: 20.0 if d < d3 else 10.0, split_at={d3: 2.0})
        m = synth.FakeMarket(cal)
        m.add("x", [("2015-01-01", "OLDN"), (d2, "NEWN")], daily=daily, auctions=prints)
        end = cal.offset(t, 10)
        reqs = plan.event_requests(cal, "OLDN", t, end)
        store = self._fetch(m, reqs)
        data = events.event_data(store, cal, "OLDN", t, end)
        F = FM.share_factor(data["daily"]["raw"], data["daily"]["split"], cal.offset(t, 1), cal.offset(t, 5))
        self.assertEqual(F, 2.0)
        # a screen request for a hold session under the old symbol with asof = s finds nothing: screen rows are
        # never joined into the per-event computation
        s5 = cal.offset(t, 5)
        sreq = plan.screen_requests(cal, s5, ["OLDN"])
        store2 = self._fetch(m, sreq)
        self.assertTrue(store2.empty(sreq[0]["key"], "OLDN"))

    def test_empty_response_is_counted_not_incomplete(self):
        cal = self.cal
        m = synth.FakeMarket(cal)
        reqs = plan.screen_requests(cal, "2020-06-01", ["NONE"])
        store = self._fetch(m, reqs)
        self.assertTrue(all(store.status(r["key"]) == "complete" for r in reqs))
        self.assertTrue(all(store.empty(r["key"], "NONE") for r in reqs))

    def test_request_with_the_fetch_date_as_asof_is_refused(self):
        cal = self.cal
        req = plan.event_requests(cal, "ABC", "2020-06-01", "2020-06-15")[0]
        identity.check_asof(req, "2026-12-01")
        bad = json.loads(json.dumps(req))
        bad["params"]["asof"] = "2026-12-01"
        with self.assertRaises(identity.AsofRefused):
            identity.check_asof(bad, "2026-12-01")
        nothing = json.loads(json.dumps(req))
        del nothing["params"]["asof"]
        with self.assertRaises(identity.AsofRefused):
            identity.check_asof(nothing, "2026-12-01")
        # the driver refuses before any request leaves
        m = synth.FakeMarket(cal)
        with self.assertRaises(identity.AsofRefused):
            driver.to_fixpoint(lambda st: [bad], transports(m), Store(), "2026-12-01", clock=fixed_clock)
        self.assertEqual(m.calls, [])


class Enumeration(unittest.TestCase):
    def test_union_of_asset_master_and_action_symbols(self):
        assets = [{"symbol": "AAPL", "status": "active", "class": "us_equity"},
                  {"symbol": "TWTRQ", "status": "inactive", "class": "us_equity"},
                  {"symbol": "12345X", "status": "inactive", "class": "us_equity"},
                  {"symbol": "BRK.B", "status": "active", "class": "us_equity"}]
        actions = [{"type": "name_change", "old_symbol": "FB", "new_symbol": "META", "date": "2022-06-09"},
                   {"type": "cash_merger", "acquiree_symbol": "TWTR", "acquirer_symbol": "X", "date": "2022-10-28"}]
        out = identity.enumerate_symbols(assets, actions)
        self.assertEqual(out["symbols"], ["AAPL", "BRK.B", "FB", "META", "TWTR", "TWTRQ", "X"])
        self.assertEqual(out["counts"]["asset_master_placeholders_removed"], 1)

    def test_corporate_action_date_fields(self):
        body = {"corporate_actions": {
            "name_changes": [{"old_symbol": "A", "new_symbol": "B", "process_date": "2020-01-10", "ex_date": "2020-01-09"}],
            "forward_split": [{"symbol": "C", "ex_date": "2020-02-03", "process_date": "2020-02-01", "payable_date": "2020-01-31"}],
            "reverse_splits": [{"symbol": "D", "ex_date": "2020-03-03", "process_date": "2020-03-01"}],
            "cash_merger": [{"acquiree_symbol": "E", "acquirer_symbol": "F", "effective_date": "2020-04-01",
                             "process_date": "2020-04-03"}]}}
        recs = {r["type"]: r["date"] for r in records.corporate_actions(body)}
        self.assertEqual(recs, {"name_change": "2020-01-10", "forward_split": "2020-02-03",
                                "reverse_split": "2020-03-03", "cash_merger": "2020-04-01"})


if __name__ == "__main__":
    unittest.main()
