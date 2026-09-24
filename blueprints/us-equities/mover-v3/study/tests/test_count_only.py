"""The pre-freeze count-only code: hashed samples, coverage stamps, rates, the year and item rules decided by code
from the hashed thresholds (R8-9), minute-bar coverage (E3), the identity diagnostic and probe, and an output with
no symbol, price or event row."""
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from core import count_only as CO
from core import coverage_rule, driver
from core.store import Store
from tests import synth
from tests.test_identity import fixed_clock, issuer_data, transports

PROTOCOL = json.loads((Path(__file__).resolve().parents[2] / "protocol-core-draft.json").read_text())


class Keys(unittest.TestCase):
    def test_sample_and_coverage_rates(self):
        pairs = [(f"S{i:04d}", "2019-05-01") for i in range(20000)]
        rate = sum(CO.sampled(s, d) for s, d in pairs) / len(pairs)
        self.assertAlmostEqual(rate, 1 / 20, delta=0.006)
        self.assertEqual(CO.sampled("AAPL", "2019-05-01"), CO.sampled("AAPL", "2019-05-01"))
        crate = sum(CO.coverage_selected(s, d) for s, d in pairs) / len(pairs)
        self.assertAlmostEqual(crate, 1 / 25, delta=0.006)

    def test_coverage_stamps_move_on_early_closes(self):
        cal = synth.calendar()
        self.assertEqual(CO.coverage_stamps(cal, "2019-12-24"), [cal.at("2019-12-24", "12:17"), cal.at("2019-12-24", "12:43")])
        self.assertEqual(CO.coverage_stamps(cal, "2019-12-23"), [cal.at("2019-12-23", "12:17"), cal.at("2019-12-23", "14:43")])

    def test_stamp_eligibility(self):
        cal = synth.calendar()
        st = cal.at("2019-12-23", "12:17")
        q = synth.quote
        self.assertTrue(CO.stamp_has_eligible(cal, [q(st - 0.5, 1, 1.1)], st))
        self.assertTrue(CO.stamp_has_eligible(cal, [q(st - 5, 1, 1.1), q(st + 59, 1, 1.1)], st))
        self.assertFalse(CO.stamp_has_eligible(cal, [q(st - 5, 1, 1.1), q(st + 61, 1, 1.1)], st))
        self.assertFalse(CO.stamp_has_eligible(cal, [q(st + 3, 1.1, 1.1)], st))

    def test_candidate_bound(self):
        self.assertEqual(CO.candidate_bound(0), 60)
        self.assertEqual(CO.candidate_bound(100), 20 * (100 + 30 + 3))


class Decisions(unittest.TestCase):
    def setUp(self):
        self.th = coverage_rule.checked_thresholds(PROTOCOL)

    def test_year_rule_from_hashed_thresholds(self):
        good = {"official_close_rate": 0.95, "eligible_quote_rate": 0.85, "identity_unreached_rate": 0.02,
                "minute_bar_rate": 0.97}
        self.assertTrue(coverage_rule.year_decision(good, self.th)["kept"])
        for key, bad in (("official_close_rate", 0.89), ("eligible_quote_rate", 0.79),
                         ("identity_unreached_rate", 0.11), ("minute_bar_rate", 0.89), ("minute_bar_rate", None)):
            self.assertFalse(coverage_rule.year_decision({**good, key: bad}, self.th)["kept"], key)

    def test_item_rule_depends_on_2020_only(self):
        kept = {"kept": True, "reasons": []}
        drop = {"kept": False, "reasons": ["x"]}
        r = coverage_rule.item_rule({2016: drop, 2017: drop, 2018: drop, 2019: drop, 2020: kept})
        self.assertTrue(r["items_tested"])
        self.assertFalse(r["development_computed"])
        r = coverage_rule.item_rule({2016: kept, 2017: kept, 2018: kept, 2019: kept, 2020: drop})
        self.assertFalse(r["items_tested"])
        self.assertEqual(r["H1"], "not tested, p = 1 at every stage, permanently")

    def test_changed_coverage_rule_is_refused(self):
        bad = json.loads(json.dumps(PROTOCOL))
        bad["coverage_rule"]["thresholds"]["identity_limited_validation_rate"] = 0.05
        with self.assertRaises(coverage_rule.CoverageRuleChanged):
            coverage_rule.checked_thresholds(bad)

    def test_probe_identity_limited_and_margin_decisions(self):
        ok = {"rename_probes": 40, "bars_match": 39, "auctions_match": 38, "quotes_match": 36, "reuse_cases": 0,
              "reuse_differ": 0}
        d = coverage_rule.probe_decision(ok, self.th)
        self.assertTrue(d["passes"])
        self.assertEqual(d["ticker_reuse"], "unverified for 2016-2020")
        self.assertFalse(coverage_rule.probe_decision({**ok, "quotes_match": 35}, self.th)["passes"])
        self.assertFalse(coverage_rule.probe_decision({**ok, "rename_probes": 19, "bars_match": 19, "auctions_match": 19,
                                                       "quotes_match": 19}, self.th)["passes"])
        self.assertTrue(coverage_rule.identity_limited(0.021, self.th))
        self.assertFalse(coverage_rule.identity_limited(0.02, self.th))
        self.assertTrue(coverage_rule.fetch_margin(1_728_000, self.th)["passes"])
        self.assertFalse(coverage_rule.fetch_margin(1_728_001, self.th)["passes"])


class Pipeline(unittest.TestCase):
    def test_counts_and_output_hold_no_symbol_or_price(self):
        cal = synth.calendar()
        sess = cal.range("2020-06-01", "2020-06-30")
        symbols = [f"S{i:03d}" for i in range(120)]
        m = synth.FakeMarket(cal)
        for i, sym in enumerate(symbols):
            daily, prints = issuer_data(cal, cal.offset(sess[0], -1), sess[-1],
                                        lambda d, i=i: 3.0 + i * 0.01 if d != "2020-06-15" else 5.0 + i * 0.01)
            if i % 10 == 0:
                prints = {d: synth.auction(b["o"], b["c"], close_cond="6") for d, b in daily["raw"].items()}
                prints = {d: {"o": [], "c": p["c"]} for d, p in prints.items()}  # no listing-exchange open
            quotes = []
            for d in sess:
                for st in CO.coverage_stamps(cal, d):
                    if i % 4:
                        quotes.append(synth.quote(st - 0.2, 3.0, 3.01))
            minute = [] if i % 7 == 0 else [b for d in sess for b in synth.minute_rows(cal, d, 3.0, 10, n=3)]
            names = [("2015-01-01", sym)] + ([("2020-07-01", "S001X")] if sym == "S001" else [])
            m.add(sym, names, daily=daily, auctions=prints, minute=minute, quotes=quotes)
        # S001 was renamed away after the window; the default asof serves another history under it
        m.aliases["S001"] = "S002"

        def planner(store):
            reqs = [r for s in sess for r in CO.part1_requests(cal, s, symbols)]
            if any(not store.has(r["key"]) for r in reqs):
                return reqs
            for s in sess:
                picked = [x for x in symbols if CO.sampled(x, s)]
                from core import plan
                for batch in plan.batches(picked):
                    raw = store.parsed(plan.screen_requests(cal, s, batch)[0]["key"])
                    reqs += CO.part1_phase2(cal, s, [x for x in batch if raw.get(x, {}).get(s)])
            return reqs

        store = Store()
        driver.stage_fetch(planner, transports(m), store, "2026-09-25", clock=fixed_clock)
        c = CO.part1_counts(store, cal, sess, symbols, [])
        CO.phase2_counts(store, cal, sess, symbols, c)
        cy = c[2020]
        expected = sum(CO.sampled(x, s) for x in symbols for s in sess)
        self.assertEqual(cy["sampled_pairs"], expected)
        self.assertEqual(cy["with_daily_bar"], expected)
        no_open = sum(CO.sampled(x, s) for i, x in enumerate(symbols) if i % 10 == 0 for s in sess)
        self.assertEqual(cy["accepted_official_close"], expected - no_open)
        self.assertEqual(cy["close_label:no_opening_print"], no_open)
        stamps = cy["coverage_stamps_with_eligible"] + cy["coverage_stamps_without_eligible"]
        self.assertGreater(stamps, 0)
        self.assertEqual(stamps % 2, 0)
        unreached = sum(CO.sampled("S001", s) for s in sess)
        self.assertEqual(cy["identity_unreached_pairs"], unreached)
        out = CO.outputs(PROTOCOL, c, {"rename_probes": 0, "bars_match": 0, "auctions_match": 0, "quotes_match": 0,
                                       "reuse_cases": 0, "reuse_differ": 0}, {"counts": {"union": 120}}, 1000.0)
        text = json.dumps(out)
        self.assertNotIn("S0", text)
        self.assertEqual(out["coverage_rule_sha256"], coverage_rule.rule_sha256(PROTOCOL))
        self.assertFalse(out["item_rule"]["items_tested"] and not out["years"]["2020"]["decision"]["kept"])
        self.assertEqual(out["years"]["2020"]["counts"]["distinct_unreached_symbols"], 1 if unreached else 0)


class Round9(unittest.TestCase):
    """Review round 9: the candidate count uses D's floor on the official close only (L-3), coverage_rule's hash is
    checked before any fetch (L-3), and the committed count-only command (M-2, F8)."""

    def test_candidate_with_raw_close_below_one_and_official_close_above(self):
        cal = synth.calendar()
        s = "2020-06-03"
        prev = cal.offset(s, -1)
        name = next(f"Q{i:03d}" for i in range(2000) if CO.sampled(f"Q{i:03d}", s))
        daily, prints = issuer_data(cal, cal.offset(s, -3), s, lambda d: 0.98 if d == s else 0.8)
        prints[prev] = synth.auction(1.0, 1.0)
        prints[s] = synth.auction(1.2, 1.25)
        m = synth.FakeMarket(cal)
        m.add("q", [("2015-01-01", name)], daily=daily, auctions=prints)
        store = Store()
        driver.stage_fetch(CO.part1_planner(cal, [s], [name]), transports(m), store, "2026-09-25", clock=fixed_clock)
        c = CO.part1_counts(store, cal, [s], [name], [])
        self.assertEqual(c[2020]["sampled_candidates"], 1)
        self.assertEqual(c[2020]["with_bar_close_ge_1"], 0)

    def test_changed_coverage_rule_is_refused_before_any_fetch(self):
        bad = json.loads(json.dumps(PROTOCOL))
        bad["coverage_rule"]["thresholds"]["minute_bar_rate_min"] = 0.5
        m = synth.FakeMarket(synth.calendar())
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(coverage_rule.CoverageRuleChanged):
                CO.run(bad, synth.calendar(), transports(m), tmp, "2026-09-25", 10_000, clock=fixed_clock)
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertEqual(m.calls, [])

    def test_count_only_command_runs_once_from_a_committed_tree(self):
        import run
        from core import logs, runner
        from core.canon import sha256_file
        from core.params import COUNT_ONLY_OUTPUT, RUN_LOG
        from fetch.transport import TRADING_HOST
        from tests import fixture_repo as FR
        self.assertEqual(run.transports()["trading"].host, TRADING_HOST)
        self.assertTrue(all(r["api"] == "trading" for r in CO.part0_requests("2026-09-25") if r["kind"] == "assets"))
        cal = synth.calendar()
        m = synth.FakeMarket(cal)
        syms = [f"S{chr(65 + i)}" for i in range(12)]
        for i, sym in enumerate(syms):
            daily, prints = issuer_data(cal, "2020-05-01", "2020-06-30", lambda d, i=i: 3.0 + i)
            m.add(sym, [("2015-01-01", sym)], daily=daily, auctions=prints)
        m.assets = [{"symbol": x, "status": "active", "class": "us_equity"} for x in syms]
        m.actions = [{"type": "cash_dividend", "symbol": "SB", "ex_date": "2020-06-02"}]
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp, frozen=False)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            argv = ["count-only", "--snapshot-root", root, "--rate-per-minute", "10000", "--rate-source", "synthetic"]
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda: transports(m)), \
                    mock.patch.object(run, "clock", fixed_clock), \
                    mock.patch.object(CO, "PART1_RANGE", ("2020-06-01", "2020-06-05")):
                (repo / COUNT_ONLY_OUTPUT).unlink()                # the fixture's placeholder output
                FR.commit_push(repo, "2026-09-25T12:00:00+00:00")
                logs.append_line(repo / RUN_LOG, {"stage": "pre_freeze", "purpose": "note"})
                with self.assertRaises(runner.guards.Refused):     # a run log that differs from HEAD
                    run.main(argv)
                FR.sh(repo, "checkout", "--", RUN_LOG)
                self.assertEqual(run.main(argv), 0)
                out = json.loads((repo / COUNT_ONLY_OUTPUT).read_text())
                line = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((line["purpose"], line["status"]), ("count_only", "complete"))
                self.assertEqual(line["results_sha256"], sha256_file(repo / COUNT_ONLY_OUTPUT))
                self.assertEqual(line["coverage_rule_sha256"], coverage_rule.rule_sha256(PROTOCOL))
                self.assertEqual((out["study_tree"], out["code_revision"]), (fx["tree"], FR.sh(repo, "rev-parse", "HEAD")))
                self.assertEqual(set(out["snapshots"]), {"part0", "part1", "part3"})
                self.assertEqual(out["part0"]["enumeration_sha256"], sha256_file(Path(root) / "enumeration.json"))
                self.assertEqual(out["fetch_estimate"]["screen_requests"], 5 * 4 * 1)
                self.assertEqual(out["part0"]["actions_by_year"], {"2020": {"cash_dividend": 1}})
                self.assertFalse(any(f'"{x}"' in json.dumps(out) for x in syms))
                self.assertIn(("/v2/assets", {"status": "active", "asset_class": "us_equity"}), m.calls)
                FR.commit_push(repo, "2026-09-25T13:00:00+00:00")
                with self.assertRaises(runner.RunRefused):            # it runs once
                    run.main(argv)


class Probe(unittest.TestCase):
    def test_probe_list_counts_and_reuse(self):
        cal = synth.calendar()
        d = "2019-06-12"
        actions = [{"type": "name_change", "old_symbol": "OLDA", "new_symbol": "NEWA", "date": d},
                   {"type": "name_change", "old_symbol": "RU", "new_symbol": "RUX", "date": "2017-03-01"},
                   {"type": "name_change", "old_symbol": "QQQZ", "new_symbol": "RU", "date": "2018-05-01"},
                   {"type": "name_change", "old_symbol": "LATE", "new_symbol": "L2", "date": "2021-03-01"}]
        probes = CO.probe_list(cal, actions)
        self.assertEqual(len(probes["renames"]), 3)
        self.assertEqual(probes["reuse"], [("RU", "2017-03-01", "2018-05-01")])
        daily, prints = issuer_data(cal, "2016-01-04", "2019-12-31", lambda x: 4.0)
        q = [synth.quote(cal.at(cal.offset(d, k), "12:16"), 4.0, 4.01) for k in (-1, 1)]
        m = synth.FakeMarket(cal)
        m.add("a", [("2015-01-01", "OLDA"), (d, "NEWA")], daily=daily, auctions=prints, quotes=q)
        ru_old, _ = issuer_data(cal, "2016-01-04", "2017-02-28", lambda x: 9.0)
        ru_new, _ = issuer_data(cal, "2016-01-04", "2019-12-31", lambda x: 1.0)
        m.add("ru_old", [("2015-01-01", "RU"), ("2017-03-01", "RUX")], daily=ru_old)
        m.add("ru_new", [("2015-01-01", "QQQZ"), ("2018-05-01", "RU")], daily=ru_new)
        only = {"renames": [r for r in probes["renames"] if r[0] == "OLDA"], "reuse": probes["reuse"]}
        store = Store()
        driver.stage_fetch(lambda st: CO.probe_requests(cal, only), transports(m), store, "2026-09-25", clock=fixed_clock)
        counts = CO.probe_counts(store, cal, only)
        self.assertEqual(counts, {"rename_probes": 1, "bars_match": 1, "auctions_match": 1, "quotes_match": 1,
                                  "reuse_cases": 1, "reuse_differ": 1})


if __name__ == "__main__":
    unittest.main()


class DryRun(unittest.TestCase):
    def test_dry_run_emits_counts_only(self):
        cal = synth.calendar("2022-06-01", "2023-12-29")
        s = "2023-03-01"
        daily, prints = issuer_data(cal, cal.offset(s, -60), cal.offset(s, 12), lambda d: 7.25)
        minute = [b for d in cal.range(cal.offset(s, -19), cal.offset(s, 12)) for b in synth.minute_rows(cal, d, 7.25, 5, n=30)]
        q = [synth.quote(cal.at(cal.offset(s, 1), "09:35"), 7.2, 7.3)]
        m = synth.FakeMarket(cal, page_size={"bars": 100, "auctions": 100, "quotes": 1})
        m.add("a", [("2015-01-01", "AAA")], daily=daily, auctions=prints, minute=minute, quotes=q)
        store = Store()
        driver.stage_fetch(lambda st: CO.dry_run_requests(cal, [s], ["AAA", "ZZZ"]), transports(m), store, "2026-09-25",
                           clock=fixed_clock)
        out = CO.dry_run_counts(store)
        self.assertEqual(out["event_minute"]["requests"], 2)
        self.assertGreater(out["event_minute"]["pages"], 2)          # pagination exercised
        self.assertEqual(out["event_minute"]["empty"], 1)            # ZZZ
        self.assertEqual(out["quote_entry"]["records"], 1)
        text = json.dumps(out)
        self.assertNotIn("7.2", text)
        self.assertNotIn("AAA", text)
