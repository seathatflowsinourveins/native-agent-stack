"""populations.fetch_failures for every request kind, the single re-fetch, the 1% void rule, and review round 8,
R8-1: the transport derives nothing, and the reproduction check regenerates the plan and re-parses every page."""
import ast
import json
import subprocess
import sys
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


RATED = {"exposure_registry": {"pre_freeze_access_path": {"rate_limit": {
    "per_minute": 200, "source": "synthetic", "trading_per_minute": 100, "trading_source": "synthetic"}}}}


class TransportPacing(unittest.TestCase):
    """Review round 11, C2: the child's transport paces every page request, retries included, at the pinned
    per-minute rate with one pacer for both hosts, and an HTTP 429 waits a full rate window before its retry."""

    def test_requests_are_paced_at_the_pinned_rate_across_hosts(self):
        from core import transport_proc
        from fetch.transport import Pacer
        clock, slept = {"t": 1000.0}, []

        def sleep(s):
            slept.append(round(s, 6))
            clock["t"] += s
        pacer = Pacer(120, sleep=sleep, monotonic=lambda: clock["t"])
        cal = synth.calendar()
        m = synth.FakeMarket(cal)
        a = Transport(opener=m.opener, headers={}, sleep=sleep, pacer=pacer)
        b = Transport(opener=m.opener, headers={}, sleep=sleep, host="https://trading.example", pacer=pacer)
        for t in (a, b, a, b):
            t.get("/v2/stocks/auctions", {"symbols": "A", "start": "2020-01-02", "end": "2020-01-02"})
        self.assertEqual(slept, [0.5, 0.5, 0.5])            # 120 per minute: one slot every 0.5 s, shared
        apis = transport_proc.worker_apis(90)
        self.assertIs(apis["data"].pacer, apis["trading"].pacer)
        self.assertAlmostEqual(apis["data"].pacer.gap, 60 / 90)
        self.assertEqual(transport_proc.worker_apis()["data"].pacer.gap, 0.0)
        self.assertEqual(transport_proc.per_minute_arg(["--per-minute", "200.0"]), 200.0)
        tr = transport_proc.transports(per_minute=200)
        self.assertEqual(tr["data"].proc.cmd[-2:], ["--per-minute", "200.0"])
        # review round 15, F12: with a pinned trading limit each host has its own pacer
        apis = transport_proc.worker_apis(9000, 150)
        self.assertIsNot(apis["data"].pacer, apis["trading"].pacer)
        self.assertAlmostEqual(apis["trading"].pacer.gap, 60 / 150)
        tr = transport_proc.transports(per_minute=9000, trading_per_minute=150)
        self.assertEqual(tr["data"].proc.cmd[-4:], ["--per-minute", "9000.0", "--trading-per-minute", "150.0"])
        self.assertEqual(transport_proc.per_minute_arg(tr["data"].proc.cmd, "--trading-per-minute"), 150.0)

    def test_http_429_waits_a_full_rate_window(self):
        from fetch.transport import RATE_WINDOW_S
        cal = synth.calendar()
        m = synth.FakeMarket(cal)
        calls = []

        def opener(url, headers, timeout):
            calls.append(url)
            return (429, b"{}") if len(calls) <= 2 else m.opener(url, headers, timeout)
        slept = []
        res = Transport(opener=opener, headers={}, sleep=slept.append).get(
            "/v2/stocks/auctions", {"symbols": "A", "start": "2020-01-02", "end": "2020-01-02"})
        self.assertTrue(res["complete"])
        self.assertEqual(slept, [RATE_WINDOW_S, RATE_WINDOW_S])

    def test_run_py_refuses_a_fetch_without_the_pinned_rate(self):
        import run
        with self.assertRaisesRegex(ValueError, "rate_limit"):
            run.transports({"exposure_registry": {"pre_freeze_access_path": {"rate_limit": {"per_minute": None}}}})


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


class TransportProcess(unittest.TestCase):
    """Review round 10, H1: the transport runs in a child process and only raw pages cross the boundary."""

    def _worker(self, tmp, body):
        path = Path(tmp) / "worker.py"
        path.write_text(f"import sys\nsys.path.insert(0, {str(FETCH_DIR.parent)!r})\n" + body)
        return [sys.executable, "-I", "-B", str(path)]

    def test_pages_round_trip_through_the_child_process(self):
        from core import transport_proc
        body = ("from core.transport_proc import serve\n"
                "class T:\n"
                "    def __init__(self, tag): self.tag = tag\n"
                "    def get(self, endpoint, params):\n"
                "        return {'pages': [self.tag.encode() + endpoint.encode(), bytes(range(256))], 'complete': True,"
                " 'error': None}\n"
                "serve({'data': T('d'), 'trading': T('t')}, sys.stdin, sys.stdout)\n")
        with tempfile.TemporaryDirectory() as tmp:
            tr = transport_proc.transports(self._worker(tmp, body))
            res = tr["trading"].get("/v2/assets", {"status": "active"})
            self.assertEqual(res, {"pages": [b"t/v2/assets", bytes(range(256))], "complete": True, "error": None})
            self.assertEqual(tr["data"].get("/x", {})["pages"][0], b"d/x")
            child = tr["data"].proc.proc
            tr["data"].proc.close()
            # review round 12, F10: close() leaves no pipe open (no ResourceWarning at teardown)
            self.assertTrue(child.stdin.closed and child.stdout.closed)
            self.assertIsNotNone(child.returncode)

    def test_a_malformed_reply_is_an_incomplete_request_and_a_dead_child_stops_the_run(self):
        from core import transport_proc as TP
        for bad in ("not json", '{"pages": [1], "complete": true, "error": null}',
                    '{"pages": [], "complete": "yes", "error": null}',
                    '{"pages": [], "complete": true, "error": null, "patch": "core.stats"}',
                    '{"pages": ["***"], "complete": true, "error": null}'):
            self.assertEqual(TP.decode(bad)["complete"], False, bad)
        with tempfile.TemporaryDirectory() as tmp:
            tr = TP.transports(self._worker(tmp, "raise SystemExit(0)\n"))
            with self.assertRaises(TP.TransportProcessEnded):
                tr["data"].get("/x", {})
            tr["data"].proc.close()

    def test_run_py_never_imports_the_fetch_directory(self):
        code = ("import sys; sys.dont_write_bytecode = True; sys.path.insert(0, %r); import run; t = run.transports(%r); "
                "import core.runner, core.holdout, core.stage; "
                "print(sorted(m for m in sys.modules if m == 'fetch' or m.startswith('fetch.')))" % (str(FETCH_DIR.parent), RATED))
        out = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "[]")


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

    def test_the_live_sample_is_sealed_and_the_check_recomputes_from_the_seals(self):
        """Review round 15, N02 (R14-open-2): run.py transport-check seals each live sample before computing the check,
        so the check can be recomputed from the seals (to adopt an output a hard kill left with no run-log line), and
        a sample already sealed under the live root is read, never drawn again."""
        changed = ["blueprints/us-equities/mover-v3/study/fetch/transport.py"]
        prefix = "blueprints/us-equities/mover-v3/study/fetch"
        with tempfile.TemporaryDirectory() as live_root:
            res = transport_check.reproduction_check(self.planner, self.sealed, transports(self.m), changed, prefix,
                                                     seed="s", live_root=live_root, clock=fixed_clock)
            self.assertTrue(res["passes"], res)
            self.assertEqual(sorted(res["live_snapshots"]), ["stage"])
            again = transport_check.reproduction_from_sealed(self.planner, self.sealed, changed, prefix, "s", (),
                                                             live_root, res["live_snapshots"])
            self.assertEqual(again, res)
            dead = {"data": None, "trading": None}           # no transport: a second draw would fail
            reused = transport_check.reproduction_check(self.planner, self.sealed, dead, changed, prefix, seed="s",
                                                        live_root=live_root, clock=fixed_clock)
            self.assertEqual(reused, res)

    def test_live_sample_detects_different_rows(self):
        other = synth.FakeMarket(self.cal)
        daily, prints = issuer_data(self.cal, self.cal.offset(self.sess[0], -1), self.sess[-1], lambda d: 5.01)
        other.issuers = dict(self.m.issuers)
        other.add("AAA", [("2015-01-01", "AAA")], daily=daily, auctions=prints)
        self.assertFalse(transport_check.check_live(self.sealed, transports(other))["passes"])


if __name__ == "__main__":
    unittest.main()
