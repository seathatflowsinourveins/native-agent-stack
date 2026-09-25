"""SYN: prepare.scan_news on a synthetic news archive (no private data, no duckdb).

Each synthetic article exercises one funnel rule: single-symbol relevance, the asset
filter, timing windows, both timestamp guards, the movement filter and 24 h novelty.
"""

import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/sota-mover/news-llm"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prep = load("news_llm_prepare_under_test", "prepare.py")
sig = prep.sig
CALENDAR = sig.Calendar.from_calendar_json(json.loads((ROOT / "blueprints/us-equities/mover-v3/data/session-calendar.json").read_text()))

ASSETS = {
    "ACME": {"symbol": "ACME", "name": "Acme Corporation Common Stock", "exchange": "NYSE", "status": "active"},
    "BETA": {"symbol": "BETA", "name": "Beta Inc. Class A Common Stock", "exchange": "NASDAQ", "status": "active"},
    "GAMMA": {"symbol": "GAMMA", "name": "Gamma Holdings, Inc.", "exchange": "NASDAQ", "status": "active"},
    "FUND": {"symbol": "FUND", "name": "SPDR Something ETF Trust", "exchange": "ARCA", "status": "active"},
}


def article(nid, created, symbols, headline, updated=None):
    return {"id": str(nid), "created_at": created, "updated_at": updated or created, "symbols": repr(symbols),
            "headline": headline, "summary": "", "content": "", "source": "", "author": "", "url": ""}


ARTICLES = [
    article(100, "2023-03-01T12:00:00Z", ["ACME"], "Acme Wins Big Contract"),             # kept: overnight
    article(101, "2023-03-01T12:00:01Z", ["ACME", "BETA"], "Acme And Beta Partner"),      # two symbols
    article(102, "2023-03-01T12:00:02Z", ["FUND"], "Fund Rebalances"),                    # not an operating company
    article(103, "2023-03-01T14:10:00Z", ["ACME"], "Acme Names New CFO"),                 # 09:10 EST, excluded window
    article(104, "2023-03-01T15:00:00Z", ["BETA"], "Beta Signs Supplier", "2023-03-01T15:20:00Z"),  # guard A
    article(105, "2023-03-01T15:01:00Z", ["BETA"], "Beta Shares Are Trading Higher"),     # movement headline
    article(121, "2023-03-02T01:00:00Z", ["ACME"], "Acme wins big contract!"),            # 24 h duplicate of 100
    article(107, "2023-03-01T15:02:00Z", ["ZZZZ"], "Unknown Co Reports"),                 # not in asset master
    article(108, "2023-03-01T15:05:00Z", ["BETA"], "Beta Launches Product"),              # kept: RTH
    article(109, "2023-02-25T15:00:00Z", ["GAMMA"], "Gamma Raises Guidance"),            # guard B: ingested after its cutoff
    article(110, "2023-03-01T15:06:00Z", [], "Economic Calendar"),                        # no symbols
    article(111, "2023-03-01T15:07:00Z", ["AMB"], "Ambiguous Co Update"),                 # ambiguous symbol
    article(120, "2023-03-01T20:45:00Z", ["BETA"], "Beta Late Update"),                   # 15:45 EST, last 30 min
    article(113, "2023-03-01T15:08:00Z", ["ACME"], "Acme Opens Plant"),                   # kept: RTH (ACME)
    article(114, "2023-03-01T15:09:00Z", ["ACME"], "Acme Opens Second Plant"),            # later RTH, same window
]


class ScanNews(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        by_day = {}
        for a in ARTICLES:
            by_day.setdefault(a["created_at"][:10], []).append(a)
        for day, rows in by_day.items():
            y, m, d = day.split("-")
            (root / y / m).mkdir(parents=True, exist_ok=True)
            with gzip.open(root / y / m / f"{d}.jsonl.gz", "wt") as fh:
                for a in rows:
                    fh.write(json.dumps(a) + "\n")
        self.args = Namespace(news_root=str(root))

    def tearDown(self):
        self.tmp.cleanup()

    def test_funnel(self):
        candidates, funnel, diagnostics = prep.scan_news(CALENDAR, ASSETS, {"AMB"}, self.args)
        self.assertEqual(funnel["articles"], len(ARTICLES))
        self.assertEqual(funnel["drop_symbol_count_not_1"], 1)
        self.assertEqual(funnel["drop_no_symbols"], 1)
        self.assertEqual(funnel["drop_not_primary_operating_company"], 1)
        self.assertEqual(funnel["drop_symbol_not_in_asset_master"], 1)
        self.assertEqual(funnel["drop_symbol_ambiguous_in_asset_master"], 1)
        self.assertEqual(funnel["drop_window_excluded_0900_0930"], 1)
        self.assertEqual(funnel["drop_window_excluded_last_30min"], 1)
        self.assertEqual(funnel["drop_guard_updated_after_cutoff"], 1)
        self.assertEqual(funnel["drop_movement_headline"], 1)
        self.assertEqual(funnel["drop_duplicate_24h"], 1)
        self.assertEqual(funnel["drop_guard_ingested_after_cutoff"], 1)
        gb = diagnostics["guard_B_drops_by_window_and_session_year"]
        self.assertEqual(gb["overnight"]["2023"], {"evaluated": 2, "dropped": 1, "share": 0.5})  # 100 kept, 109 dropped
        self.assertEqual(gb["rth"]["2023"], {"evaluated": 3, "dropped": 0, "share": 0.0})
        self.assertEqual(gb["overnight"]["all"]["dropped"], 1)
        surv = diagnostics["survivorship_single_symbol_not_in_asset_master_by_ny_year"]["2023"]
        self.assertEqual(surv["not_in_asset_master"], 1)
        self.assertEqual(surv["share"], round(1 / surv["single_symbol"], 4))
        kept = {c["news_id"]: c for c in candidates}
        self.assertEqual(sorted(kept), ["100", "108", "113", "114"])  # first-per-window runs after eligibility
        acme = kept["100"]
        self.assertEqual((acme["window"], acme["session"], acme["sub"]), ("overnight", "2023-03-01", "pre_open"))
        self.assertEqual((acme["company"], acme["checkpoint_year"], acme["exchange"]), ("Acme Corporation", 2022, "NYSE"))
        self.assertEqual(acme["entry_utc"], "2023-03-01T14:30:00Z")
        beta = kept["108"]
        self.assertEqual((beta["window"], beta["entry_utc"], beta["exit_utc"]), ("rth", "2023-03-01T15:20:00Z", "2023-03-01T21:00:00Z"))
        self.assertEqual(beta["company"], "Beta Inc.")
        self.assertEqual(funnel["pre_eligibility_candidates"], 4)
        self.assertEqual(diagnostics["updated_minus_created_seconds"]["buckets"]["le_1h"], 1)
        self.assertEqual(sig.first_per_window([dict(c, window=c["window"]) for c in candidates if c["symbol"] == "ACME" and c["window"] == "rth"])[0]["news_id"], "113")


class Receipts(unittest.TestCase):
    def test_receipts_from_a_synthetic_private_root(self):
        rec = load("news_llm_receipts_under_test", "receipts.py")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        priv, models, out = (Path(tmp.name) / d for d in ("priv", "models", "out"))
        for d in (priv / "scores", priv / "probe" / "p1", priv / "auctions", priv / "spreads", models):
            d.mkdir(parents=True, exist_ok=True)
        prep = {k: {} for k in ("inputs", "asset_master", "funnel", "eligible_by_window_lane", "selected_by_window_lane",
                                "selected_sessions_by_window_lane", "selected_by_session_year", "selected_by_checkpoint",
                                "diagnostics", "events_file")}
        prep.update(started_at="t0", finished_at="t1")
        (priv / "prepare-receipt.json").write_text(json.dumps(prep))
        progress = {"scored_this_run": 2, "by_checkpoint": {"2020": {"labels": {"FAVORABLE": 2}, "stops": {"eos": 2}, "load_seconds": 1.0,
                                                                      "batch1_agreement": {"agree": 1, "checked": 1}}}}
        (priv / "probe" / "p1" / "progress.json").write_text(json.dumps(progress))
        (priv / "scores" / "progress-delta-liquid.json").write_text(json.dumps(progress))
        interrupted = {"scored_this_run": 3, "by_checkpoint": {  # a unit stopped mid-checkpoint
            "2020": {"labels": {"FAVORABLE": 2}, "stops": {"eos": 2}, "load_seconds": 1.0, "batch1_agreement": {"agree": 1, "checked": 1}},
            "2021": {"labels": {"FAVORABLE": 1}, "stops": {"eos": 1}, "load_seconds": 1.0, "batch1_agreement": None}}}
        (priv / "scores" / "progress-first-unit.json").write_text(json.dumps(interrupted))
        (priv / "scores" / "progress.json").write_text(json.dumps(progress))  # a copy, not reported twice
        rows = [{"event_id": "1:A", "checkpoint_year": 2020, "label": "FAVORABLE", "raw_output": "FAVORABLE", "stop": "eos"},
                {"event_id": "2:B", "checkpoint_year": 2020, "label": "PARSE_FAIL", "raw_output": "UNFLEXIBLE", "stop": "eos"},
                {"event_id": "9:Z", "checkpoint_year": 2020, "label": "UNFAVORABLE", "raw_output": "UNFAVORABLE", "stop": "eos"}]
        (priv / "scores" / "scores-20201231.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        with gzip.open(priv / "events.jsonl.gz", "wt") as fh:  # 9:Z is a stale row (event no longer selected)
            fh.write(json.dumps({"event_id": "1:A", "window": "overnight", "lane": "liquid"}) + "\n")
            fh.write(json.dumps({"event_id": "2:B", "window": "rth", "lane": "liquid"}) + "\n")
        (priv / "d5-audit-sample.json").write_text(json.dumps({
            "seed": 7, "population_single_symbol": 10, "dropped": 3, "sample": [["11", "Acme Shares Up 5%"], ["12", "Beta Halted"]],
            "labels": ["A", "C"], "label_key": {"A": "a", "C": "c"}, "labelled_by": "test"}))
        (priv / "auctions" / "auctions-summary.json").write_text(json.dumps({"rows": 1}))
        (priv / "auctions" / "ledger.jsonl").write_text('{"status": "ok"}\n')
        (models / "fetch-manifest-2020.json").write_text(json.dumps({"years": [2020], "finished_at": "t", "seconds": 1,
                                                                     "bytes_downloaded": 5, "bytes_verified": 5,
                                                                     "records": [{"year": 2020, "file": "f", "status": "downloaded", "bytes": 5}]}))
        rec.main(["--private-root", str(priv), "--models-root", str(models), "--out", str(out)])
        status = json.loads((out / "scoring-status.json").read_text())
        self.assertEqual(status["labels_in_files"], {"FAVORABLE": 1, "PARSE_FAIL": 1, "UNFAVORABLE": 1})
        self.assertEqual(set(status["runs"]), {"progress-delta-liquid.json", "progress-first-unit.json"})
        self.assertEqual(status["runs"]["progress-delta-liquid.json"]["batch1_agreement"], {"agree": 1, "checked": 1})
        self.assertEqual(status["runs"]["progress-first-unit.json"]["batch1_agreement"], {"agree": 1, "checked": 1})
        rules = status["label_rules_on_current_events"]
        ck = rules["by_checkpoint"]["2020"]
        self.assertEqual(ck["rows"], 2)  # the stale row is left out
        self.assertEqual((ck["strict:PARSE_FAIL"], ck["operative:UNFAVORABLE"]), (1, 1))
        self.assertEqual(ck["strict_parse_fail_recovered_as:UNFAVORABLE"], 1)
        self.assertEqual((ck["strict_parse_fail_share"], ck["operative_parse_fail_share"]), (0.5, 0.0))
        self.assertEqual(rules["by_window_lane"]["rth:liquid"]["operative:UNFAVORABLE"], 1)
        audit = json.loads((out / "d5-audit.json").read_text())
        self.assertEqual((audit["seed"], audit["sample_size"], audit["counts"]), (7, 2, {"A": 1, "C": 1}))
        self.assertEqual(audit["sample_ids_and_labels"], [{"news_id": "11", "label": "A"}, {"news_id": "12", "label": "C"}])
        self.assertNotIn("Acme Shares Up", (out / "d5-audit.json").read_text())  # no headline text is committed
        self.assertEqual(json.loads((out / "collection-summary.json").read_text())["auctions"]["ledger"], {"ok": 1})
        self.assertEqual(json.loads((out / "models-fetch.json").read_text())["bytes_downloaded_total"], 5)
        leaky = dict(prep, inputs={"path": str(Path.home() / "secret-place")})
        (priv / "prepare-receipt.json").write_text(json.dumps(leaky))
        with self.assertRaises(SystemExit):
            rec.main(["--private-root", str(priv), "--models-root", str(models), "--out", str(out)])


class Helpers(unittest.TestCase):
    def test_load_assets_prefers_active_and_flags_ambiguity(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        a = Path(tmp.name) / "active.json"
        i = Path(tmp.name) / "inactive.json"
        a.write_text(json.dumps([{"symbol": "X", "status": "active", "name": "X Inc."},
                                 {"symbol": "D", "status": "active", "name": "D1"}, {"symbol": "D", "status": "active", "name": "D2"}]))
        i.write_text(json.dumps([{"symbol": "X", "status": "inactive", "name": "Old X"}, {"symbol": "Y", "status": "inactive", "name": "Y"}]))
        resolved, ambiguous = prep.load_assets([str(a), str(i)])
        self.assertEqual(resolved["X"]["name"], "X Inc.")
        self.assertEqual(resolved["Y"]["name"], "Y")
        self.assertEqual(ambiguous, {"D"})

    def test_deterministic_gzip(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p1, p2 = Path(tmp.name) / "a.gz", Path(tmp.name) / "b.gz"
        for p in (p1, p2):
            with prep.DeterministicGzipText(str(p)) as out:
                out.write("same content\n")
        self.assertEqual(p1.read_bytes(), p2.read_bytes())
        self.assertEqual(gzip.open(p1, "rt").read(), "same content\n")


if __name__ == "__main__":
    unittest.main()
