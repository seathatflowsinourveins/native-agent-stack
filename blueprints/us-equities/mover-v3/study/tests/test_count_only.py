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
from core import coverage_rule, driver, plan
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
              "reuse_differ": 0, "reuse_failed": 0, "reuse_inconclusive": 0}
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
        # review round 11, C5: the identity-diagnostic, coverage-stamp and minute-bar counts are also split by
        # listing exchange, and each split sums to its per-year count
        for name in ("identity_unreached_pairs", "default_asof_pairs_close_ge_1", "coverage_stamps_with_eligible",
                     "coverage_stamps_without_eligible", "minute_pairs_with_regular_bar",
                     "minute_pairs_without_regular_bar", "with_daily_bar"):
            split = {k: v for k, v in cy.items() if k.startswith(name + ":")}
            self.assertEqual(sum(split.values()), cy[name], name)
            if cy[name]:
                self.assertTrue(split, name)
        out = CO.outputs(PROTOCOL, c, {k: 0 for k in CO.PROBE_KEYS}, {"counts": {"union": 120}}, 1000.0)
        text = json.dumps(out)
        self.assertNotIn("S0", text)
        self.assertEqual(out["coverage_rule_sha256"], coverage_rule.rule_sha256(PROTOCOL))
        self.assertFalse(out["item_rule"]["items_tested"] and not out["years"]["2020"]["decision"]["kept"])
        self.assertEqual(out["years"]["2020"]["counts"]["distinct_unreached_symbols"], 1 if unreached else 0)


class FetchBudget(unittest.TestCase):
    """Review round 15, F12: at e7529b47 the margin divided the request count by the rate ceiling. The estimate now
    prices pages at the slower of the pinned rate and the dry run's measured throughput, the trading API at its own
    limit, and adds the pinned retry and evaluation-and-merge allowances, all pinned before the count-only run."""

    def _budget(self, **allow):
        from tests import fixture_repo as FR
        a = json.loads(json.dumps(FR.ALLOWANCE))
        a.update(allow)
        return {"rate": dict(FR.RATE_LIMIT), "allowance": a}

    def test_pages_throughput_and_allowances_are_priced(self):
        cal = synth.calendar()
        k = {y: 100 for y in range(2016, 2021)}
        pages = {kk: 1 for kk in CO.PAGE_KINDS}
        pages["event_minute"] = 4
        cheap = CO.fetch_estimate(cal, 12_000, k, self._budget(seconds_per_page=0.001, pages_per_request=pages,
                                                               retry_seconds=0.0, evaluation_and_merge_seconds=0.0))
        # with one page per request, a fast measurement and no allowances this is e7529b47's request estimate plus
        # the extra minute-bar pages
        sessions = len(cal.range(*CO.PART1_RANGE))
        requests = sessions * 4 * 120 + 58 * sum(CO.candidate_bound(v) for v in k.values()) + 3
        self.assertEqual(cheap["requests"], requests)
        self.assertEqual(cheap["pages"], requests + 3 * 5 * CO.candidate_bound(100))
        slow = CO.fetch_estimate(cal, 12_000, k, self._budget(seconds_per_page=1.5, pages_per_request=pages,
                                                              retry_seconds=7_200.0,
                                                              evaluation_and_merge_seconds=86_400.0))
        self.assertAlmostEqual(slow["data_seconds_per_page"], 1.5)       # a measured 1.5 s per page, not 0.006 s
        self.assertGreater(slow["estimate_seconds"], cheap["estimate_seconds"] * 40)
        th = coverage_rule.checked_thresholds(PROTOCOL)
        old = requests / FR_RATE() * 60.0                          # e7529b47's estimate at the rate ceiling
        self.assertTrue(coverage_rule.fetch_margin(old, th)["passes"])
        self.assertFalse(coverage_rule.fetch_margin(slow["estimate_seconds"], th)["passes"])

    def test_unpinned_budgets_are_refused_before_the_run(self):
        bad = json.loads(json.dumps(PROTOCOL))
        with self.assertRaisesRegex(ValueError, "pipeline_allowance"):
            CO.pinned_pipeline_allowance(bad)                      # the draft pins none
        bad["exposure_registry"]["pre_freeze_access_path"]["rate_limit"].update({"per_minute": 10000, "source": "x"})
        with self.assertRaisesRegex(ValueError, "trading_per_minute"):
            CO.pinned_rate_limit(bad)
        from tests import fixture_repo as FR
        pa = bad["exposure_registry"]["pre_freeze_access_path"]["pipeline_allowance"]
        pa.update(json.loads(json.dumps(FR.ALLOWANCE)))
        self.assertEqual(CO.pinned_pipeline_allowance(bad)["seconds_per_page"], FR.ALLOWANCE["seconds_per_page"])
        del pa["pages_per_request"]["quote_backward"]
        with self.assertRaises(ValueError):                        # every priced kind needs its page bound
            CO.pinned_pipeline_allowance(bad)

    def test_the_dry_run_measures_pages_and_throughput_from_its_seal(self):
        cal = synth.calendar()
        store = Store()
        req = plan.screen_requests(cal, "2020-06-02", ["AAA"])[0]
        store.put(req, True, [b"{}", b"{}", b"{}"], "2026-09-25T10:00:00Z", elapsed_seconds=6.0)
        store.put(plan.quote_request("quote_exit", "AAA", "2020-06-01", 1.6e9, 1.6e9 + 60), True, [b"{}"],
                  "2026-09-25T10:00:06Z", elapsed_seconds=2.0)
        m = CO.dry_run_measured(store)
        self.assertEqual(m["pages_per_request_max"], {"quote_exit": 1, "screen_daily_raw": 3})
        self.assertEqual((m["pages"], m["elapsed_seconds"], m["seconds_per_page"]), (4, 8.0, 2.0))


def FR_RATE():
    from tests import fixture_repo as FR
    return FR.RATE_LIMIT["per_minute"]


class SelectiveFailures(unittest.TestCase):
    """Review round 15, N03: a failed endpoint no longer removes its batch from every rate. Four sessions, each with
    its own sampled pairs, every pair with a raw close >= $1, an accepted official close, quotes at both stamps and
    regular-session minute bars: s1 complete; s2 with its screen auctions failing; s3 with its asof = s raw daily
    request failing (one of its pairs coverage-selected); s4 with its default-asof raw request failing. At e7529b47
    s2 and s3 dropped out of every rate (official close 1.0, identity 0.0) and s4 out of the identity rate."""

    def test_each_rate_keeps_its_cohort_and_counts_unknowns_against_coverage(self):
        cal = synth.calendar()
        s1, s2, s3, s4 = "2020-06-02", "2020-06-03", "2020-06-04", "2020-06-05"
        sess = [s1, s2, s3, s4]
        names = [f"N{i:04d}" for i in range(3000)]
        chosen = {s: [x for x in names if CO.sampled(x, s)][:3] for s in sess}
        chosen[s3].append(next(x for x in names if CO.sampled(x, s3) and CO.coverage_selected(x, s3)))
        symbols = sorted({x for xs in chosen.values() for x in xs})
        m = synth.FakeMarket(cal)
        for sym in symbols:
            daily, prints = issuer_data(cal, cal.offset(s1, -2), s4, lambda d: 5.0)
            quotes = [synth.quote(st - 0.2, 4.99, 5.01) for d in sess for st in CO.coverage_stamps(cal, d)]
            minute = [b for d in sess for b in synth.minute_rows(cal, d, 5.0, 10, n=3)]
            m.add(sym, [("2015-01-01", sym)], daily=daily, auctions=prints, minute=minute, quotes=quotes)
        m.fail = [(lambda path, p: path == "/v2/stocks/auctions" and p.get("asof") == s2, "urlerror", 10_000),
                  (lambda path, p: path == "/v2/stocks/bars" and p.get("timeframe") == "1Day" and
                   p.get("adjustment") == "raw" and p.get("asof") == s3, "urlerror", 10_000),
                  (lambda path, p: path == "/v2/stocks/bars" and p.get("timeframe") == "1Day" and
                   p.get("adjustment") == "raw" and "asof" not in p and p.get("end") == s4, "urlerror", 10_000)]
        store = Store()
        driver.stage_fetch(CO.part1_planner(cal, sess, symbols), transports(m), store, "2026-09-25",
                           clock=fixed_clock)
        c = CO.part1_counts(store, cal, sess, symbols, [])
        CO.phase2_counts(store, cal, sess, symbols, c)
        cy = c[2020]
        n = {s: sum(CO.sampled(x, s) for x in symbols) for s in sess}
        cov3 = sum(CO.sampled(x, s3) and CO.coverage_selected(x, s3) for x in symbols)
        self.assertGreaterEqual(cov3, 1)
        self.assertEqual(cy["with_bar_close_ge_1"], n[s1] + n[s2] + n[s4])
        self.assertEqual(cy["official_close_fetch_incomplete"], n[s2])
        self.assertEqual(cy["raw_fetch_incomplete_pairs"], n[s3])
        self.assertEqual(cy["accepted_official_close"], n[s1] + n[s4])
        self.assertEqual(cy["default_asof_pairs_unknown"], n[s4])
        self.assertEqual(cy["identity_unreached_pairs_fetch_incomplete"], n[s3])
        self.assertEqual(cy["identity_unreached_pairs"], 0)
        r = CO.rates(cy)
        total = sum(n.values())
        self.assertAlmostEqual(r["official_close_rate"], (n[s1] + n[s4]) / total)
        self.assertAlmostEqual(r["identity_unreached_rate"], (n[s3] + n[s4]) / total)
        # the raw-incomplete batch's coverage-selected pairs count against the stamp and minute rates
        self.assertEqual(cy["coverage_pairs_raw_unknown"], cov3)
        self.assertGreaterEqual(cy["coverage_stamps_fetch_incomplete"], 2 * cov3)
        self.assertGreaterEqual(cy["minute_pairs_fetch_incomplete"], cov3)
        self.assertLess(r["eligible_quote_rate"], 1.0)
        self.assertLess(r["minute_bar_rate"], 1.0)
        # every pair whose candidacy is unknown (s2: prints; s3: raw) counts toward the fetch-estimate bound
        self.assertEqual(cy["sampled_candidates_unknown"], n[s2] + n[s3])
        self.assertEqual(CO.candidates_for_bound(cy), cy["sampled_candidates"] + n[s2] + n[s3])


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
        from core import transport_proc
        from core.params import PROTOCOL_PATH
        from fetch.transport import TRADING_HOST
        from tests import fixture_repo as FR
        self.assertEqual(transport_proc.worker_apis()["trading"].host, TRADING_HOST)
        self.assertEqual(sorted(run.transports({"exposure_registry": {"pre_freeze_access_path": {"rate_limit": {
            "per_minute": 200, "source": "synthetic", "trading_per_minute": 100, "trading_source": "synthetic"}}}})),
            ["data", "trading"])
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
            argv = ["count-only", "--snapshot-root", root]
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda *_: transports(m)), \
                    mock.patch.object(run, "clock", fixed_clock), \
                    mock.patch.object(CO, "PART1_RANGE", ("2020-06-01", "2020-06-05")):
                (repo / COUNT_ONLY_OUTPUT).unlink()                # the fixture's placeholder output
                FR.commit_push(repo, "2026-09-25T12:00:00+00:00")
                with self.assertRaisesRegex(ValueError, "rate_limit"):   # review round 10, L1: pinned before the run
                    run.main(argv)
                proto = json.loads((repo / PROTOCOL_PATH).read_text())
                proto["exposure_registry"]["pre_freeze_access_path"]["rate_limit"].update(FR.RATE_LIMIT)
                # review round 11, C4: a committed parameters mismatch stops the run before any fetch
                bad = json.loads(json.dumps(proto))
                bad["run_discipline"]["study_code"]["parameters"]["sampling"] = {"changed": True}
                FR.write(repo / PROTOCOL_PATH, json.dumps(bad, indent=1) + "\n")
                FR.commit_push(repo, "2026-09-25T12:05:00+00:00")
                calls = len(m.calls)
                with self.assertRaisesRegex(runner.guards.Refused, "parameters"):
                    run.main(argv)
                self.assertEqual(len(m.calls), calls)
                FR.write(repo / PROTOCOL_PATH, json.dumps(proto, indent=1) + "\n")
                FR.sh(repo, "commit", "-q", "-am", "pin the rate", when="2026-09-25T12:10:00+00:00")
                with self.assertRaises(runner.guards.Refused):     # committed, not on origin/main
                    run.main(argv)
                FR.push(repo)
                logs.append_line(repo / RUN_LOG, {"stage": "pre_freeze", "purpose": "note"})
                with self.assertRaises(runner.guards.Refused):     # a run log that differs from HEAD
                    run.main(argv)
                FR.sh(repo, "checkout", "--", RUN_LOG)
                # review round 11, F4: the first run appends its start line (with the coverage_rule sha256) only
                self.assertEqual(run.main(argv), 0)
                started = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((started["purpose"], started["coverage_rule_sha256"]),
                                 ("count_only_start", coverage_rule.rule_sha256(PROTOCOL)))
                self.assertFalse((repo / COUNT_ONLY_OUTPUT).exists())
                FR.commit_push(repo, "2026-09-25T12:20:00+00:00")
                # while that start has no end line, a changed protocol cannot start again
                FR.write(repo / PROTOCOL_PATH, json.dumps({**proto, "note": "changed after a discarded run"}, indent=1)
                         + "\n")
                FR.commit_push(repo, "2026-09-25T12:25:00+00:00")
                with self.assertRaisesRegex(runner.RunRefused, "has no end line"):
                    run.main(argv)
                FR.write(repo / PROTOCOL_PATH, json.dumps(proto, indent=1) + "\n")
                FR.commit_push(repo, "2026-09-25T12:30:00+00:00")
                self.assertEqual(run.main(argv), 0)
                out = json.loads((repo / COUNT_ONLY_OUTPUT).read_text())
                line = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((line["purpose"], line["status"]), ("count_only", "complete"))
                self.assertEqual(line["results_sha256"], sha256_file(repo / COUNT_ONLY_OUTPUT))
                self.assertEqual(logs.read_lines(repo / RUN_LOG)[line["start_index"]]["purpose"], "count_only_start")
                self.assertEqual(line["coverage_rule_sha256"], coverage_rule.rule_sha256(PROTOCOL))
                self.assertEqual(out["rate_limit"], FR.RATE_LIMIT)
                self.assertEqual((out["study_tree"], out["code_revision"]), (fx["tree"], FR.sh(repo, "rev-parse", "HEAD")))
                self.assertEqual(set(out["snapshots"]), {"part0", "part1", "part3"})
                self.assertEqual(out["part0"]["enumeration_sha256"], sha256_file(Path(root) / "enumeration.json"))
                self.assertEqual(out["fetch_estimate"]["requests_by_kind"]["screen_daily_raw"], 5 * 1)
                self.assertEqual(out["pipeline_allowance"], FR.ALLOWANCE)
                self.assertEqual(out["part0"]["actions_by_year"], {"2020": {"cash_dividend": 1}})
                self.assertFalse(any(f'"{x}"' in json.dumps(out) for x in syms))
                self.assertIn(("/v2/assets", {"status": "active", "asset_class": "us_equity"}), m.calls)
                FR.commit_push(repo, "2026-09-25T13:00:00+00:00")
                with self.assertRaises(runner.RunRefused):            # it runs once
                    run.main(argv)


class FailedRunRecord(unittest.TestCase):
    def test_a_failed_run_logs_every_sealed_part_and_keeps_its_rule(self):
        """Review round 12, F3 (second review): a count-only run that fails after sealing parts 0 and 1 names both
        sha256s on its failed end line, and a later run under another coverage_rule is refused."""
        import run
        from core import logs, runner
        from core.params import COUNT_ONLY_OUTPUT, PROTOCOL_PATH, RUN_LOG
        from tests import fixture_repo as FR
        cal = synth.calendar()
        m = synth.FakeMarket(cal)
        daily, prints = issuer_data(cal, "2020-05-01", "2020-06-30", lambda d: 3.0)
        m.add("sa", [("2015-01-01", "SA")], daily=daily, auctions=prints)
        m.assets = [{"symbol": "SA", "status": "active", "class": "us_equity"}]
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp, frozen=False)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            argv = ["count-only", "--snapshot-root", root]
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda *_: transports(m)), \
                    mock.patch.object(run, "clock", fixed_clock), \
                    mock.patch.object(CO, "PART1_RANGE", ("2020-06-01", "2020-06-03")):
                (repo / COUNT_ONLY_OUTPUT).unlink()
                proto = json.loads((repo / PROTOCOL_PATH).read_text())
                proto["exposure_registry"]["pre_freeze_access_path"]["rate_limit"].update(FR.RATE_LIMIT)
                FR.write(repo / PROTOCOL_PATH, json.dumps(proto, indent=1) + "\n")
                FR.commit_push(repo, "2026-09-25T12:00:00+00:00")
                self.assertEqual(run.main(argv), 0)                     # the start line
                FR.commit_push(repo, "2026-09-25T12:05:00+00:00")
                with mock.patch.object(CO, "probe_list", side_effect=RuntimeError("after part 1")), \
                        self.assertRaises(RuntimeError):
                    run.main(argv)
                end = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((end["purpose"], end["status"]), ("count_only", "failed"))
                self.assertEqual(end["sealed_parts"], ["part0", "part1"])
                self.assertEqual(len(end["input_snapshot_sha256s"]), 2)
                for part, sha in zip(("part0", "part1"), end["input_snapshot_sha256s"]):
                    Store.read(Path(root) / part, sha)                # each logged sha256 is the sealed part's
                other = dict(end, coverage_rule_sha256="0" * 64)
                logs.append_line(repo / RUN_LOG, other)
                FR.commit_push(repo, "2026-09-25T12:10:00+00:00")
                with self.assertRaisesRegex(runner.RunRefused, "sealed part 1 under another coverage_rule"):
                    run.main(argv)


def _kill_before_the_line(purpose):
    """A hard kill between an output's rename and its run-log line: the end line of `purpose` is never written
    (a SIGKILL runs no 'finally'; here the append itself dies)."""
    from core import logs
    real = logs.append_line

    def append(path, obj):
        if obj.get("purpose") == purpose:
            raise KeyboardInterrupt(f"killed before the {purpose} line")
        real(path, obj)
    return mock.patch.object(logs, "append_line", append)


class OrphanOutputs(unittest.TestCase):
    """Review round 15, N02 (R14-open-2): a count-only or dry-run output that a hard kill left with no run-log line is
    adopted under the open start line once it equals the output recomputed from its sealed inputs; nothing is fetched
    again, a tampered file is refused, and the adopted output governs. At e7529b47 both commands refused while the
    output existed, so the study could only continue by deleting a file no line cited."""

    def _setup(self, tmp, m):
        import run
        from core.params import COUNT_ONLY_OUTPUT, PROTOCOL_PATH
        from tests import fixture_repo as FR
        fx = FR.build(tmp, frozen=False)
        repo = fx["repo"]
        (repo / COUNT_ONLY_OUTPUT).unlink()
        proto = json.loads((repo / PROTOCOL_PATH).read_text())
        proto["exposure_registry"]["pre_freeze_access_path"]["rate_limit"].update(FR.RATE_LIMIT)
        FR.write(repo / PROTOCOL_PATH, json.dumps(proto, indent=1) + "\n")
        FR.commit_push(repo, "2026-09-25T12:00:00+00:00")
        return fx, repo, run

    def test_a_count_only_output_left_by_a_hard_kill_is_adopted_from_its_seals(self):
        from core import logs, runner
        from core.canon import sha256_file
        from core.params import COUNT_ONLY_OUTPUT, RUN_LOG
        from tests import fixture_repo as FR
        cal = synth.calendar()
        m = synth.FakeMarket(cal)
        for i, sym in enumerate(("SA", "SB", "SC")):
            daily, prints = issuer_data(cal, "2020-05-01", "2020-06-30", lambda d, i=i: 3.0 + i)
            m.add(sym.lower(), [("2015-01-01", sym)], daily=daily, auctions=prints)
        m.assets = [{"symbol": x, "status": "active", "class": "us_equity"} for x in ("SA", "SB", "SC")]
        with tempfile.TemporaryDirectory() as tmp:
            fx, repo, run = self._setup(tmp, m)
            root = str(Path(tmp) / "snap")
            argv = ["count-only", "--snapshot-root", root]
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda *_: transports(m)), \
                    mock.patch.object(run, "clock", fixed_clock), \
                    mock.patch.object(CO, "PART1_RANGE", ("2020-06-01", "2020-06-03")):
                self.assertEqual(run.main(argv), 0)                     # the start line
                FR.commit_push(repo, "2026-09-25T12:05:00+00:00")
                with _kill_before_the_line("count_only"), self.assertRaises(KeyboardInterrupt):
                    run.main(argv)
                out = repo / COUNT_ONLY_OUTPUT
                self.assertTrue(out.exists())
                self.assertEqual(logs.read_lines(repo / RUN_LOG)[-1]["purpose"], "count_only_start")
                body, calls = out.read_bytes(), len(m.calls)
                # a tampered orphan is not adopted
                bad = json.loads(body)
                bad["years"]["2020"]["counts"]["sampled_pairs"] = 10 ** 6
                out.write_text(json.dumps(bad))
                with self.assertRaisesRegex(runner.RunRefused, "not adopted"):
                    run.main(argv)
                out.write_bytes(body)
                self.assertEqual(run.main(argv), 0)                     # adopted, nothing fetched again
                self.assertEqual(len(m.calls), calls)
                line = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((line["purpose"], line["status"], line["results_sha256"], line["adopted_uncited_output"]),
                                 ("count_only", "complete", sha256_file(out), True))
                self.assertEqual(line["sealed_parts"], ["part0", "part1", "part3"])
                self.assertEqual(json.loads(body)["dependencies"]["study_tree"], fx["tree"])
                FR.commit_push(repo, "2026-09-25T12:10:00+00:00")
                with self.assertRaises(runner.RunRefused):                # it has run once
                    run.main(argv)

    def test_a_dry_run_output_left_by_a_hard_kill_is_adopted_from_its_seal(self):
        from core import logs
        from core.canon import sha256_file
        from core.params import DRY_RUN_OUTPUT, RUN_LOG
        from tests import fixture_repo as FR
        cal = synth.calendar("2022-06-01", "2023-12-29")
        s = "2023-05-15"
        m = synth.FakeMarket(cal)
        daily, prints = issuer_data(cal, cal.offset(s, -61), cal.offset(s, 12), lambda d: 3.0)
        m.add("xx", [("2015-01-01", "XX")], daily=daily, auctions=prints)
        with tempfile.TemporaryDirectory() as tmp:
            fx, repo, run = self._setup(tmp, m)
            root = str(Path(tmp) / "snap")
            argv = ["dry-run", "--sessions", s, "--symbols", "XX", "--snapshot-root", root]
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda *_: transports(m)), \
                    mock.patch.object(run, "clock", fixed_clock):
                self.assertEqual(run.main(argv), 0)
                FR.commit_push(repo, "2026-09-25T12:05:00+00:00")
                with _kill_before_the_line("dry_run"), self.assertRaises(KeyboardInterrupt):
                    run.main(argv)
                calls = len(m.calls)
                self.assertEqual(run.main(argv), 0)
                self.assertEqual(len(m.calls), calls)
                line = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((line["purpose"], line["status"], line["results_sha256"], line["adopted_uncited_output"]),
                                 ("dry_run", "complete", sha256_file(repo / DRY_RUN_OUTPUT), True))


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
                                  "reuse_cases": 1, "reuse_differ": 1, "reuse_failed": 0, "reuse_inconclusive": 0})

    def test_a_rename_probe_needs_the_same_sessions_across_the_rename_and_identical_quotes(self):
        """Review round 15, F09: at e7529b47 one common session made a bars (or auctions) match, and two non-empty
        quote responses made a quotes match, whatever their content. Here the new ticker's asof = d+3 response holds
        only the sessions from d on (the old ticker's history is not reached through it) and its quotes differ, so
        no endpoint matches; the old-ticker response is complete and the two histories agree where they overlap."""
        cal = synth.calendar()
        d = "2019-06-12"
        daily, prints = issuer_data(cal, "2016-01-04", "2019-12-31", lambda x: 4.0)
        tail_daily = {adj: {s: b for s, b in rows.items() if s >= d} for adj, rows in daily.items()}
        tail_prints = {s: v for s, v in prints.items() if s >= d}
        q_old = [synth.quote(cal.at(cal.offset(d, k), "12:16"), 4.0, 4.01) for k in (-1, 1)]
        q_new = [synth.quote(cal.at(cal.offset(d, k), "12:16") + 1, 4.0, 4.02) for k in (-1, 1)]
        m = synth.FakeMarket(cal)
        m.add("old", [("2015-01-01", "OLDA"), (d, "OLDA-GONE")], daily=daily, auctions=prints, quotes=q_old)
        m.add("new", [("2015-01-01", "NEWA-PRE"), (d, "NEWA")], daily=tail_daily, auctions=tail_prints, quotes=q_new)
        probes = {"renames": [("OLDA", "NEWA", d)], "reuse": []}
        store = Store()
        driver.stage_fetch(lambda st: CO.probe_requests(cal, probes), transports(m), store, "2026-09-25",
                           clock=fixed_clock)
        counts = CO.probe_counts(store, cal, probes)
        self.assertEqual((counts["bars_match"], counts["auctions_match"], counts["quotes_match"]), (0, 0, 0))

    def test_an_observed_ticker_reuse_failure_fails_the_gate(self):
        """Review round 15, N07: at e7529b47 'ticker_reuse: failed' was only reported and the gate passed on the
        rename rates. A provider that serves the old issuer's bars under RU whatever the asof is an observed failure;
        a case whose early response has no bar is inconclusive, never a failure."""
        cal = synth.calendar()
        th = coverage_rule.checked_thresholds(PROTOCOL)
        probes = {"renames": [], "reuse": [("RU", "2017-03-01", "2018-05-01")]}
        ru_old, _ = issuer_data(cal, "2016-01-04", "2017-02-28", lambda x: 9.0)
        m = synth.FakeMarket(cal)
        m.add("ru_old", [("2015-01-01", "RU"), ("2017-03-01", "RUX")], daily=ru_old)
        m.aliases_any_asof["RU"] = "ru_old"                      # asof is ignored for RU
        store = Store()
        driver.stage_fetch(lambda st: CO.probe_requests(cal, probes), transports(m), store, "2026-09-25",
                           clock=fixed_clock)
        counts = CO.probe_counts(store, cal, probes)
        self.assertEqual((counts["reuse_failed"], counts["reuse_differ"], counts["reuse_inconclusive"]), (1, 0, 0))
        renames_ok = {"rename_probes": 40, "bars_match": 40, "auctions_match": 40, "quotes_match": 40}
        d = coverage_rule.probe_decision({**counts, **renames_ok}, th)
        self.assertEqual(d["ticker_reuse"], "failed")
        self.assertFalse(d["passes"])
        empty = synth.FakeMarket(cal)                             # no bar of the old issuer at all
        store = Store()
        driver.stage_fetch(lambda st: CO.probe_requests(cal, probes), transports(empty), store, "2026-09-25",
                           clock=fixed_clock)
        counts = CO.probe_counts(store, cal, probes)
        self.assertEqual((counts["reuse_failed"], counts["reuse_inconclusive"]), (0, 1))
        d = coverage_rule.probe_decision({**counts, **renames_ok}, th)
        self.assertEqual((d["ticker_reuse"], d["passes"]), ("unverified for 2016-2020", True))



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
        # review round 10, F6: every forward exit window is planned: W0 with the prevailing lookback (15:55 + 300 s
        # reaches the close, so there is no W1) and the search windows E+1 .. E+5
        e, stamp, _ = plan.planned_exit(cal, s, "b_lane", cal.offset(s, 10))
        self.assertEqual(len(plan.exit_windows(cal, e, stamp)), 6)
        self.assertEqual(out["quote_exit"]["requests"], 2 * 6)

    def test_dry_run_bounds_every_request_reach_not_only_sessions(self):
        """Review round 11, C1: a session inside 2021-01-04 .. 2024-10-17 whose lookbacks (daily t-60, auctions t-22,
        minute bars 04:00 ET of t-19, screen s-1) reach 2020 is refused; the first session whose t-60 is 2021-01-04
        is accepted, and every planned request then starts on or after 2021-01-04."""
        cal = synth.calendar("2020-01-02", "2021-12-31")
        for s in ("2021-01-04", "2021-03-01", cal.offset("2021-01-04", 59)):
            with self.assertRaises(ValueError):
                CO.dry_run_requests(cal, [s], ["AAA"])
        first = cal.offset("2021-01-04", 60)
        reqs = CO.dry_run_requests(cal, [first], ["AAA"])
        self.assertEqual(min(r["params"]["start"][:10] for r in reqs), "2021-01-04")
        with self.assertRaises(ValueError):                          # a mixed list is refused as a whole
            CO.dry_run_requests(cal, [first, "2021-02-01"], ["AAA"])
        with self.assertRaises(ValueError):                          # dry_run refuses before any fetch
            CO.dry_run(cal, ["2021-01-04"], ["AAA"], None, "/nonexistent", "2026-09-25", clock=fixed_clock)

    def test_dry_run_command_writes_counts_once_from_an_exposed_window(self):
        import run
        from core import logs, runner
        from core.canon import sha256_file
        from core.params import DRY_RUN_OUTPUT, RUN_LOG
        from tests import fixture_repo as FR
        cal = synth.calendar("2022-06-01", "2023-12-29")
        s = "2023-03-01"
        daily, prints = issuer_data(cal, cal.offset(s, -60), cal.offset(s, 12), lambda d: 7.25)
        m = synth.FakeMarket(cal)
        m.add("a", [("2015-01-01", "AAA")], daily=daily, auctions=prints)
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp, frozen=False)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda *_: transports(m)), \
                    mock.patch.object(run, "clock", fixed_clock):
                with self.assertRaises(ValueError):                  # a v3 validation session
                    run.main(["dry-run", "--sessions", "2020-06-01", "--symbols", "AAA", "--snapshot-root", root])
                with self.assertRaises(ValueError):                  # its search windows reach 2024-11-01
                    run.main(["dry-run", "--sessions", "2024-10-25", "--symbols", "AAA", "--snapshot-root", root])
                for early in ("2021-01-04", "2021-03-01"):             # review round 11, C1: lookbacks reach 2020
                    with self.assertRaises(ValueError):
                        run.main(["dry-run", "--sessions", early, "--symbols", "AAA", "--snapshot-root", root])
                self.assertFalse((repo / RUN_LOG).exists() and logs.read_lines(repo / RUN_LOG))
                dry = ["dry-run", "--sessions", s, "--symbols", "AAA,ZZZ", "--snapshot-root", root]
                self.assertEqual(run.main(dry), 0)                     # review round 11, F4: the start line
                self.assertEqual(logs.read_lines(repo / RUN_LOG)[-1]["purpose"], "dry_run_start")
                FR.commit_push(repo, "2026-09-26T11:00:00+00:00")
                self.assertEqual(run.main(dry), 0)
                out = json.loads((repo / DRY_RUN_OUTPUT).read_text())
                line = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((line["purpose"], line["status"], line["results_sha256"]),
                                 ("dry_run", "complete", sha256_file(repo / DRY_RUN_OUTPUT)))
                self.assertEqual(out["counts"]["event_minute"]["empty"], 2)
                self.assertNotIn("AAA", json.dumps(out))
                FR.commit_push(repo, "2026-09-26T12:00:00+00:00")
                with self.assertRaises(runner.RunRefused):          # it runs once
                    run.main(["dry-run", "--sessions", s, "--symbols", "AAA", "--snapshot-root", root])


if __name__ == "__main__":
    unittest.main()
