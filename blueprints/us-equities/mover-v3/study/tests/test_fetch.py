"""populations.fetch_failures for every request kind, the single re-fetch, the 1% void rule, and review round 8,
R8-1: the transport derives nothing, and the reproduction check regenerates the plan and re-parses every page."""
import ast
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from core import driver, events, plan, screen, transport_check
from core.evaluate import void_rate
from core.store import Store
from fetch.transport import RETRY_WAITS_S, Transport
from tests import synth
from tests.test_identity import fixed_clock, issuer_data, transports

FETCH_DIR = Path(__file__).resolve().parents[1] / "fetch"


class TransportRetry(unittest.TestCase):
    def _t(self, m, slept):
        return Transport(opener=m.opener, headers={}, sleep=slept.append)

    def test_exhausted_urlerror_and_timeout_are_incomplete_and_do_not_raise(self):
        cal = synth.calendar()
        for mode in ("urlerror", "timeout", "http"):
            m = synth.FakeMarket(cal)
            m.fail.append((lambda path, p: True, mode, 99))
            slept = []
            res = self._t(m, slept).get("/v2/stocks/bars", {"symbols": "A", "timeframe": "1Day", "start": "2020-01-02",
                                                             "end": "2020-01-02", "adjustment": "raw", "asof": "2020-01-02"})
            self.assertFalse(res["complete"])
            self.assertEqual(slept, list(RETRY_WAITS_S))
            self.assertEqual(len(m.calls), 4)

    def test_success_on_the_third_retry(self):
        cal = synth.calendar()
        m = synth.FakeMarket(cal)
        m.fail.append((lambda path, p: True, "urlerror", 3))
        slept = []
        res = self._t(m, slept).get("/v2/stocks/auctions", {"symbols": "A", "start": "2020-01-02", "end": "2020-01-02",
                                                             "asof": "2020-01-02"})
        self.assertTrue(res["complete"])
        self.assertEqual(slept, [1, 4, 16])

    def test_pagination_follows_the_token(self):
        cal = synth.calendar()
        m = synth.FakeMarket(cal, page_size={"bars": 2, "auctions": 2, "quotes": 2})
        daily, prints = issuer_data(cal, "2020-01-02", "2020-01-31", lambda d: 3.0)
        m.add("a", [("2015-01-01", "A")], daily=daily)
        res = Transport(opener=m.opener, headers={}, sleep=lambda s: None).get(
            "/v2/stocks/bars", {"symbols": "A", "timeframe": "1Day", "start": "2020-01-02", "end": "2020-01-31",
                                "adjustment": "raw", "asof": "2020-01-31"})
        self.assertTrue(res["complete"])
        self.assertEqual(len(res["pages"]), 11)


class TransportIsTransportOnly(unittest.TestCase):
    def test_fetch_directory_imports_no_evaluation_code_and_derives_nothing(self):
        for path in FETCH_DIR.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split(".")[0], ("core", "pinned"), path.name)
                if isinstance(node, ast.Import):
                    for a in node.names:
                        self.assertNotIn(a.name.split(".")[0], ("core", "pinned"), path.name)
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    for word in ("asof", "adjustment", "timeframe", "quotes", "bars", "auctions"):
                        self.assertNotEqual(node.value, word, f"{path.name} names request field {word}")


def _universe(cal, sess):
    m = synth.FakeMarket(cal)
    for sym, px in (("AAA", 5.0), ("BBB", 7.0)):
        daily, prints = issuer_data(cal, cal.offset(sess[0], -1), sess[-1], lambda d, px=px: px)
        m.add(sym, [("2015-01-01", sym)], daily=daily, auctions=prints)
    return m


class Driver(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        self.sess = self.cal.range("2020-06-01", "2020-06-05")

    def _reqs(self):
        return [r for s in self.sess for r in plan.screen_requests(self.cal, s, ["AAA", "BBB"])]

    def test_failed_screen_batch_is_membership_unknown_and_counted(self):
        m = _universe(self.cal, self.sess)
        bad_s = self.sess[2]
        m.fail.append((lambda path, p: p.get("asof") == bad_s and p.get("adjustment") == "split", "urlerror", 99))
        store = Store()
        res = driver.stage_fetch(lambda st: self._reqs(), transports(m), store, "2026-12-01", clock=fixed_clock)
        self.assertEqual(res["refetched"], 1)
        rate = void_rate(res["incomplete_by_kind"])
        self.assertEqual(rate["incomplete"], 1)
        self.assertEqual(rate["requests"], 20)
        self.assertTrue(rate["void"])  # 1 of 20 > 1%
        self.assertEqual(rate["by_kind"]["screen_daily_split"], {"requests": 5, "incomplete": 1})
        rows, counts, unknown = screen.screen_rows(store, self.cal, self.sess, ["AAA", "BBB"])
        self.assertEqual(counts["membership_unknown_symbol_sessions"], 2)
        self.assertEqual(unknown, {("AAA", bad_s), ("BBB", bad_s)})
        self.assertEqual(counts["screen_incomplete:screen_daily_split"], 1)
        # the ledger keeps both attempts with stamp_incomplete records and the pool run completed
        with tempfile.TemporaryDirectory() as tmp:
            store.write(tmp)
            lines = [json.loads(x) for x in (Path(tmp) / "ledger.jsonl").read_text().splitlines()]
            inc = [x for x in lines if x["event"] == "stamp_incomplete"]
            self.assertEqual([x["attempt"] for x in inc], [0, 1])
            self.assertTrue(all(x["asof"] == bad_s and x["vintage"] == "2026-12-01T00:00:00Z" for x in inc))

    def test_single_refetch_recovers_a_transient_failure(self):
        m = _universe(self.cal, self.sess)
        m.fail.append((lambda path, p: p.get("asof") == self.sess[1], "timeout", 4 * 4))
        store = Store()
        res = driver.stage_fetch(lambda st: self._reqs(), transports(m), store, "2026-12-01", clock=fixed_clock)
        self.assertEqual(res["refetched"], 4)
        self.assertEqual(void_rate(res["incomplete_by_kind"])["incomplete"], 0)
        self.assertEqual(driver.refetch_once(transports(m), store, clock=fixed_clock), 0)

    def test_void_rule_threshold(self):
        ok = void_rate({"quote_exit": {"requests": 1000, "incomplete": 10}})
        self.assertFalse(ok["void"])
        bad = void_rate({"quote_exit": {"requests": 1000, "incomplete": 10}, "event_minute": {"requests": 1, "incomplete": 1}})
        self.assertTrue(bad["void"])

    def test_failed_per_event_minute_request_makes_the_candidate_membership_unknown(self):
        cal = self.cal
        t = "2020-06-01"
        daily, prints = issuer_data(cal, cal.offset(t, -60), cal.offset(t, 12), lambda d: 10.0)
        m = synth.FakeMarket(cal)
        m.add("x", [("2015-01-01", "XX")], daily=daily, auctions=prints)
        m.fail.append((lambda path, p: p.get("timeframe") == "1Min", "urlerror", 99))
        end = cal.offset(t, 10)
        store = Store()
        driver.stage_fetch(lambda st: plan.event_requests(cal, "XX", t, end), transports(m), store, "2026-12-01",
                           clock=fixed_clock)
        data = events.event_data(store, cal, "XX", t, end)
        self.assertEqual(data["incomplete"], ["event_minute"])
        counts = Counter()
        self.assertIsNone(events.build_event(cal, {"symbol": "XX", "t": t}, data, counts))
        self.assertEqual(counts["membership_unknown:event_fetch_incomplete"], 1)

    def test_empty_minute_response_is_a_zero_dv_non_event_and_reported(self):
        cal = self.cal
        t = "2020-06-01"
        daily, prints = issuer_data(cal, cal.offset(t, -60), cal.offset(t, 12), lambda d: 10.0)
        m = synth.FakeMarket(cal)
        m.add("x", [("2015-01-01", "XX")], daily=daily, auctions=prints)
        end = cal.offset(t, 10)
        store = Store()
        driver.stage_fetch(lambda st: plan.event_requests(cal, "XX", t, end), transports(m), store, "2026-12-01",
                           clock=fixed_clock)
        data = events.event_data(store, cal, "XX", t, end)
        self.assertEqual(data["incomplete"], [])
        self.assertIn("event_minute", data["empty"])
        counts = Counter()
        self.assertIsNone(events.build_event(cal, {"symbol": "XX", "t": t}, data, counts))
        self.assertEqual(counts["candidate_volume_but_no_regular_minute_bar"], 1)
        self.assertEqual(counts["event_request_empty:event_minute"], 1)


class ReproductionCheck(unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar()
        self.sess = self.cal.range("2020-06-01", "2020-06-05")
        self.m = _universe(self.cal, self.sess)
        self.planner = lambda st: [r for s in self.sess for r in plan.screen_requests(self.cal, s, ["AAA", "BBB"])]
        self.store = Store()
        driver.stage_fetch(self.planner, transports(self.m), self.store, "2026-12-01", clock=fixed_clock)
        self.tmp = tempfile.TemporaryDirectory()
        sha = self.store.write(self.tmp.name)
        self.sealed = Store.read(self.tmp.name, sha)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fetch_only_change_passes_all_three_checks(self):
        other = synth.FakeMarket(self.cal, page_size={"bars": 1, "auctions": 1, "quotes": 1})
        other.issuers = self.m.issuers
        res = transport_check.reproduction_check(self.planner, self.sealed, transports(other),
                                                 ["blueprints/us-equities/mover-v3/study/fetch/transport.py"],
                                                 "blueprints/us-equities/mover-v3/study/fetch")
        self.assertTrue(res["passes"], res)
        self.assertEqual(res["reparse"]["pages"], 20)

    def test_a_plan_change_or_a_change_outside_fetch_fails(self):
        changed = lambda st: self.planner(st)[:-1]  # noqa: E731 - a tree whose plan drops one request
        self.assertFalse(transport_check.check_plan(changed, self.sealed)["passes"])
        res = transport_check.reproduction_check(self.planner, self.sealed, transports(self.m),
                                                 ["blueprints/us-equities/mover-v3/study/core/plan.py"],
                                                 "blueprints/us-equities/mover-v3/study/fetch")
        self.assertFalse(res["passes"])

    def test_reparse_detects_a_parser_change(self):
        key = next(iter(self.sealed.page_norm))
        self.sealed.page_norm[key] = ["0" * 64]
        self.assertFalse(transport_check.check_reparse(self.sealed)["passes"])

    def test_live_sample_detects_different_rows(self):
        other = synth.FakeMarket(self.cal)
        daily, prints = issuer_data(self.cal, self.cal.offset(self.sess[0], -1), self.sess[-1], lambda d: 5.01)
        other.issuers = dict(self.m.issuers)
        other.add("AAA", [("2015-01-01", "AAA")], daily=daily, auctions=prints)
        self.assertFalse(transport_check.check_live(self.sealed, transports(other))["passes"])


if __name__ == "__main__":
    unittest.main()
