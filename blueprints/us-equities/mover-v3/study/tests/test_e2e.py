"""A synthetic validation stage end to end: plan -> transport (fake client) -> sealed snapshot -> evaluation ->
atomic results, including the kill-before-write retry, plan regeneration from the sealed snapshot, and the
independence of validation from development-period data."""
import json
import tempfile
import unittest
from pathlib import Path

from core import costs, driver, runner, transport_check
from core import stage as ST
from core.store import Store
from tests import synth
from tests.test_costs import FEES
from tests.test_identity import fixed_clock, transports
from tests.test_trades import CELLS

PID = "mover-v3-core-draft-20260924"
B = 2000


def build_market(cal, extra_dev_event=False):
    first, last = "2019-08-01", "2021-01-29"
    events = {"MOVA": ["2020-03-02", "2020-06-15"], "MOVB": ["2020-06-15", "2020-09-14"], "MOVC": ["2020-12-28"],
              "DEAD": ["2020-05-01"], "EARLY": ["2020-01-03"], "FLAT": []}
    if extra_dev_event:
        events["FLAT"] = ["2018-04-02"]
    m = synth.FakeMarket(cal, page_size={"bars": 4000, "auctions": 4000, "quotes": 3})
    for k, (sym, ts) in enumerate(events.items()):
        def close_fn(d, ts=ts, k=k):  # a distinct level per symbol, so no two histories are identical
            return (10.0 + 0.37 * k) * (1.3 ** sum(1 for t in ts if d >= t))
        raw, split, allc = synth.series(cal, first, last, close_fn)
        prints = synth.prints_from(raw)
        minute, quotes = [], []
        for t in ts:
            for d in cal.range(cal.offset(t, -19), cal.offset(t, 12)):
                minute += synth.minute_rows(cal, d, close_fn(d), 1_000, start="04:00", n=16 * 60, step=60)
            d = [cal.offset(t, k) for k in range(0, 13)]
            live = d[1:3] if sym == "DEAD" else d[1:]
            for day in live:
                px = close_fn(day)
                for hhmm in ("09:30", "09:35", "12:00", "15:55"):
                    quotes.append(synth.quote(cal.at(day, hhmm) + (0.5 if hhmm == "09:30" else -0.2), px * 0.999, px * 1.001))
        m.add(sym, [("2015-01-01", sym)], daily={"raw": raw, "split": split, "all": allc}, auctions=prints,
              minute=sorted({b["t"]: b for b in minute}.values(), key=lambda b: b["t"]), quotes=quotes)
    return m, sorted(events)


def spec_for(cal, symbols):
    return ST.StageSpec(stage="validation", cal=cal, symbols=symbols, actions=[], fees=costs.Fees(FEES), cells=CELLS)


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = synth.calendar()
        cls.market, cls.symbols = build_market(cls.cal)
        cls.spec = spec_for(cls.cal, cls.symbols)
        store = Store()
        cls.fetch = driver.stage_fetch(ST.planner(cls.spec), transports(cls.market), store, "2026-12-01", clock=fixed_clock)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.sha = store.write(cls.tmp.name)
        cls.store = Store.read(cls.tmp.name, cls.sha)
        cls.results = ST.evaluate_stage(cls.spec, cls.store, PID, B=B)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_membership_and_trades(self):
        mem = self.results["counts"]["membership"]
        self.assertEqual(mem["d_events"], 7)
        by = self.results["counts"]["trades_by_arm_status"]
        self.assertEqual(by["b_lane:embargoed"], 1)                 # EARLY enters on 2020-01-06
        self.assertEqual(by["a_intraday:filled"], 7)                # H3-a has no embargo
        self.assertEqual(by["b_overnight:embargoed"], 1)
        items = self.results["items"]
        self.assertEqual(items["H3-a"]["n"], 7)
        self.assertEqual(items["H3-b"]["n"], 6)
        self.assertEqual(items["H3-a"]["exits"], {"normal": 7})
        self.assertIn("terminal_zero", self.results["items"]["H3-b"]["exits"] | {"terminal_zero": 0})
        self.assertEqual(self.results["counts"]["terciles"], {"None": 7})  # fewer than 60 prior validation events
        self.assertEqual(items["H1-D"]["n"], 0)
        self.assertEqual(items["H1-D"]["p"], 1.0)
        self.assertEqual(self.results["labels"]["H1-D"], "underpowered")
        self.assertEqual(self.results["counts"]["h3c_by_status"]["complete"], 5)

    def test_delisted_and_censored_b_lane_trades_stay_in_the_arm(self):
        ev_trades = self.results["counts"]["trades_by_arm_status"]
        self.assertEqual(ev_trades["b_lane:filled"], 6)
        self.assertEqual(self.results["counts"]["terminal_zero_without_merger_record"], 1)

    def test_plan_regenerates_byte_for_byte_from_the_sealed_snapshot(self):
        res = transport_check.check_plan(ST.planner(self.spec), self.store)
        self.assertTrue(res["passes"], res)
        self.assertTrue(transport_check.check_reparse(self.store)["passes"])

    def test_fetch_rate_by_kind(self):
        kinds = self.fetch["incomplete_by_kind"]
        for k in ("screen_daily_raw", "screen_auctions", "event_minute", "quote_entry", "quote_exit", "quote_backward"):
            self.assertIn(k, kinds)
        self.assertEqual(sum(v["incomplete"] for v in kinds.values()), 0)

    def test_evaluation_is_deterministic(self):
        again = ST.evaluate_stage(self.spec, Store.read(self.tmp.name, self.sha), PID, B=B)
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.results, sort_keys=True))

    def test_validation_ignores_development_period_data(self):
        m2, syms = build_market(self.cal, extra_dev_event=True)
        store = Store()
        driver.stage_fetch(ST.planner(spec_for(self.cal, syms)), transports(m2), store, "2026-12-01", clock=fixed_clock)
        res = ST.evaluate_stage(spec_for(self.cal, syms), store, PID, B=B)
        self.assertEqual({i: (r["n"], r["p"], r["estimate"]) for i, r in res["items"].items()},
                         {i: (r["n"], r["p"], r["estimate"]) for i, r in self.results["items"].items()})

    def test_kill_before_write_then_retry_reproduces_an_uninterrupted_run(self):
        ctx = {"protocol_sha256": "a" * 64, "tree": "t" * 40, "runtime_lock_sha256": "r" * 64,
               "run_log": [{"stage": "validation", "purpose": "fetch", "input_snapshot_sha256s": [self.sha],
                            "fetch_incomplete_rate": 0.0}]}
        compute = lambda: ST.evaluate_stage(self.spec, self.store, PID, B=B)  # noqa: E731
        with tempfile.TemporaryDirectory() as tmp:
            killed, clean = Path(tmp) / "killed.json", Path(tmp) / "clean.json"

            def kill():
                raise KeyboardInterrupt("killed before the results write")
            with self.assertRaises(KeyboardInterrupt):
                runner.evaluate_and_write(ctx, stage="validation", snapshot_sha256=self.sha,
                                          vintages=self.store.vintages(), freeze_utc="2026-11-01T00:00:00Z",
                                          compute=compute, results_path=killed, before_write=kill)
            self.assertFalse(killed.exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])
            a = runner.evaluate_and_write(ctx, stage="validation", snapshot_sha256=self.sha, vintages=self.store.vintages(),
                                          freeze_utc="2026-11-01T00:00:00Z", compute=compute, results_path=killed)
            b = runner.evaluate_and_write(ctx, stage="validation", snapshot_sha256=self.sha, vintages=self.store.vintages(),
                                          freeze_utc="2026-11-01T00:00:00Z", compute=compute, results_path=clean)
            self.assertEqual(a, b)
            self.assertEqual(killed.read_bytes(), clean.read_bytes())
            body = json.loads(killed.read_text())
            self.assertEqual(body["protocol_sha256"], "a" * 64)
            self.assertEqual(body["input_snapshot_sha256"], self.sha)

    def test_refusals_before_any_outcome(self):
        ctx = {"protocol_sha256": "a" * 64, "tree": "t" * 40, "runtime_lock_sha256": "r" * 64, "run_log": []}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.RunRefused):  # no committed fetch rate for this snapshot
                runner.evaluate_and_write(ctx, stage="validation", snapshot_sha256=self.sha, vintages=[],
                                          freeze_utc="2026-11-01T00:00:00Z", compute=lambda: {},
                                          results_path=Path(tmp) / "r.json")
            ctx["run_log"] = [{"stage": "validation", "purpose": "fetch", "input_snapshot_sha256s": [self.sha],
                               "fetch_incomplete_rate": 0.0}]
            with self.assertRaises(runner.guards.Refused):  # a page fetched before the freeze
                runner.evaluate_and_write(ctx, stage="validation", snapshot_sha256=self.sha,
                                          vintages=self.store.vintages(), freeze_utc="2027-01-01T00:00:00Z",
                                          compute=lambda: {}, results_path=Path(tmp) / "r.json")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_void_stage_scores_p_one_and_underpowered(self):
        res = ST.evaluate_stage(self.spec, self.store, PID, B=200, void={"void": True, "rate": 0.02})
        self.assertTrue(all(r["p_stage"] == 1.0 for r in res["items"].values()))
        self.assertTrue(all(v == "underpowered" for v in res["labels"].values()))
        untested = ST.evaluate_stage(self.spec, self.store, PID, B=200, tested=False)
        self.assertTrue(all(r["p_stage"] == 1.0 for r in untested["items"].values()))


if __name__ == "__main__":
    unittest.main()
