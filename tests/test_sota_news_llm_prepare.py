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
    article(106, "2023-03-02T01:00:00Z", ["ACME"], "Acme wins big contract!"),            # 24 h duplicate of 100
    article(107, "2023-03-01T15:02:00Z", ["ZZZZ"], "Unknown Co Reports"),                 # not in asset master
    article(108, "2023-03-01T15:05:00Z", ["BETA"], "Beta Launches Product"),              # kept: RTH
    article(109, "2023-02-25T15:00:00Z", ["GAMMA"], "Gamma Raises Guidance"),            # guard B (id order)
    article(110, "2023-03-01T15:06:00Z", [], "Economic Calendar"),                        # no symbols
    article(111, "2023-03-01T15:07:00Z", ["AMB"], "Ambiguous Co Update"),                 # ambiguous symbol
    article(112, "2023-03-01T20:45:00Z", ["BETA"], "Beta Late Update"),                   # 15:45 EST, last 30 min
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
        self.assertEqual(funnel["drop_guard_id_order"], 1)
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
        (priv / "scores" / "progress.json").write_text(json.dumps(progress))
        (priv / "scores" / "scores-20201231.jsonl").write_text('{"label": "FAVORABLE"}\n{"label": "UNFAVORABLE"}\n')
        (priv / "auctions" / "auctions-summary.json").write_text(json.dumps({"rows": 1}))
        (priv / "auctions" / "ledger.jsonl").write_text('{"status": "ok"}\n')
        (models / "fetch-manifest-2020.json").write_text(json.dumps({"years": [2020], "finished_at": "t", "seconds": 1,
                                                                     "bytes_downloaded": 5, "bytes_verified": 5,
                                                                     "records": [{"year": 2020, "file": "f", "status": "downloaded", "bytes": 5}]}))
        rec.main(["--private-root", str(priv), "--models-root", str(models), "--out", str(out)])
        status = json.loads((out / "scoring-status.json").read_text())
        self.assertEqual(status["labels_in_files"], {"FAVORABLE": 1, "UNFAVORABLE": 1})
        self.assertEqual(status["runs"]["progress.json"]["batch1_agreement"], {"agree": 1, "checked": 1})
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
