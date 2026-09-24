"""Synthetic fixtures for blueprints/us-equities/incentive-monitor/monitor.py (local integration; no network)."""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blueprints/us-equities/incentive-monitor"))
import monitor as M  # noqa: E402

EDGAR = b"""<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>8-K - Example Holdings, Inc. (0001490906) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/1490906/000149090626000032/0001490906-26-000032-index.htm"/>
<summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-09-24 &lt;b&gt;AccNo:&lt;/b&gt; 0001490906-26-000032
&lt;br&gt;Item 2.02: Results of Operations and Financial Condition
&lt;br&gt;Item 9.01: Financial Statements and Exhibits
</summary>
<updated>2026-09-24T09:54:29-04:00</updated>
<category scheme="https://www.sec.gov/" label="form type" term="8-K"/>
<id>urn:tag:sec.gov,2008:accession-number=0001490906-26-000032</id>
</entry>
</feed>"""

HALTS = """﻿<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:ndaq="http://www.nasdaqtrader.com/"><channel><item><title>PMAX</title>
<ndaq:HaltDate>09/24/2026</ndaq:HaltDate><ndaq:HaltTime>10:08:56.356</ndaq:HaltTime><ndaq:IssueSymbol>PMAX</ndaq:IssueSymbol>
<ndaq:IssueName>Example Ltd</ndaq:IssueName><ndaq:Market>NASDAQ</ndaq:Market><ndaq:ReasonCode>T1</ndaq:ReasonCode>
<ndaq:PauseThresholdPrice /><ndaq:ResumptionDate>09/24/2026</ndaq:ResumptionDate><ndaq:ResumptionQuoteTime />
<ndaq:ResumptionTradeTime /><description>ignored</description></item></channel></rss>""".encode("utf-8")


class Parsing(unittest.TestCase):
    def test_occ_symbol(self):
        self.assertEqual(M.occ_parse("AAPL240315C00172500"), ("AAPL", date(2024, 3, 15), "C", 172.5))
        self.assertEqual(M.occ_parse("SPXW240327P04925000")[2:], ("P", 4925.0))
        self.assertIsNone(M.occ_parse("AAPL"))

    def test_dte_buckets(self):
        self.assertEqual([M.dte_bucket(d) for d in (0, 7, 8, 30, 31)], ["0-7", "0-7", "8-30", "8-30", "31+"])

    def test_options_aggregation_and_large_prints(self):
        agg = M.OptionsAggregator(large_premium=100_000)
        today = date(2026, 9, 24)
        agg.add({"T": "t", "S": "ABC260925C00010000", "p": 2.0, "s": 10}, today)      # 2,000 premium, 1 day
        agg.add({"T": "t", "S": "ABC260925C00010000", "p": 5.0, "s": 300}, today)     # 150,000 premium: large
        agg.add({"T": "t", "S": "ABC261218P00008000", "p": 1.0, "s": 5}, today)       # 500 premium, 85 days
        agg.add({"T": "t", "S": "not-an-option", "p": 1.0, "s": 1}, today)
        self.assertEqual(agg.unparsed, 1)
        self.assertEqual(agg.day["ABC"]["C_premium_0_7"], 152_000.0)
        self.assertEqual(agg.day["ABC"]["large_prints"], 1)
        rows, large = agg.drain("2026-09-24T10:30")
        self.assertEqual(rows, [{"minute": "2026-09-24T10:30", "root": "ABC", "cells": {"C|0-7": [310, 152000.0, 2], "P|31+": [5, 500.0, 1]}}])
        self.assertEqual([x["premium"] for x in large], [150000.0])
        self.assertEqual(agg.drain("2026-09-24T10:31"), ([], []))
        self.assertEqual(agg.day["ABC"]["C_volume"], 310)  # session totals survive a drain

    def test_msgpack_style_timestamps_become_text(self):
        self.assertEqual(M.ts_text(datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc)), "2026-09-24T14:00:00+00:00")
        self.assertEqual(M.ts_text("2026-09-24T14:00:00Z"), "2026-09-24T14:00:00Z")
        self.assertIsNone(M.ts_text(None))

    def test_edgar_atom(self):
        (row,) = M.parse_edgar(EDGAR, "r")
        self.assertEqual((row["form"], row["cik"], row["role"], row["accession"]), ("8-K", 1490906, "Filer", "0001490906-26-000032"))
        self.assertEqual(row["items"], ["2.02", "9.01"])
        self.assertEqual(row["company"], "Example Holdings, Inc.")

    def test_halts_rss_with_bom(self):
        (row,) = M.parse_halts(HALTS, "r")
        self.assertEqual((row["IssueSymbol"], row["ReasonCode"], row["HaltTime"]), ("PMAX", "T1", "10:08:56.356"))
        self.assertIsNone(row["PauseThresholdPrice"])
        self.assertNotIn("description", row)

    def test_news_record_keeps_receive_time_and_bounds_summary(self):
        rec = M.news_record({"id": 1, "symbols": ["X"], "summary": "s" * 5000, "content": "<p>body</p>"}, "r")
        self.assertEqual((rec["received_at"], len(rec["summary"]), rec["symbols"]), ("r", 1000, ["X"]))
        self.assertNotIn("content", rec)


class Features(unittest.TestCase):
    today = date(2026, 9, 24)

    def snap(self, daily_t):
        return {"latestTrade": {"p": 11.0, "t": "2026-09-24T14:00:00Z"}, "latestQuote": {"bp": 10.99, "ap": 11.01},
                "dailyBar": {"t": daily_t, "c": 10.5, "v": 1000}, "prevDailyBar": {"c": 10.0}, "minuteBar": {"v": 50, "t": "x"}}

    def test_regular_session_uses_previous_close(self):
        f = M.snapshot_features("X", self.snap("2026-09-24T04:00:00Z"), self.today)
        self.assertEqual((f["ref"], f["v"]), (10.0, 1000))
        self.assertAlmostEqual(f["chg"], 0.10)
        self.assertAlmostEqual(f["spr_bps"], 18.2)

    def test_premarket_uses_last_session_close(self):
        f = M.snapshot_features("X", self.snap("2026-09-23T04:00:00Z"), self.today)
        self.assertEqual((f["ref"], f["v"]), (10.5, None))

    def test_no_trade_no_row(self):
        self.assertIsNone(M.snapshot_features("X", {}, self.today))

    def test_session_fraction(self):
        et = M.ET
        self.assertIsNone(M.session_fraction(datetime(2026, 9, 24, 8, 0, tzinfo=et)))
        self.assertEqual(M.session_fraction(datetime(2026, 9, 24, 9, 31, tzinfo=et)), 0.05)
        self.assertEqual(M.session_fraction(datetime(2026, 9, 24, 16, 30, tzinfo=et)), 1.0)

    def test_regime_liquid_filter_and_index(self):
        rows = [{"s": "SPY", "chg": 0.01, "ref": 600}, {"s": "A", "chg": 0.12, "ref": 10}, {"s": "B", "chg": -0.02, "ref": 10},
                {"s": "PENNY", "chg": 0.5, "ref": 1}]
        r = M.regime(rows, {"SPY": 1e6, "A": 1e6, "B": 1e6, "PENNY": 1e9}, datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc))
        self.assertEqual((r["liquid_names"], r["up_10pct"], r["all_up_20pct"], r["index"]), (3, 1, 1, {"SPY": 0.01}))
        self.assertEqual(r["breadth_up"], 0.6667)


class Scoring(unittest.TestCase):
    def test_components_and_stage(self):
        feat = {"chg": 0.03, "p": 5.0, "spr_bps": 20.0}
        row = M.score("X", feat, relvol=8.0, news=1, filings=[{"form": "8-K", "items": ["2.02"]}],
                      halts=[{"ReasonCode": "T1"}], options={"C_premium": 400_000, "P_premium": 50_000, "C_premium_0_7": 300_000, "large_prints": 3})
        self.assertEqual(row["stage"], "early")
        self.assertEqual(row["parts"], {"relvol": 3.0, "news": 1.0, "material_8k": 1.0, "news_halt": 2.0, "short_dated_calls": 1.5, "large_option_prints": 0.5})
        self.assertEqual(row["score"], 9.0)

    def test_dilution_is_negative_and_moving_stage(self):
        row = M.score("Y", {"chg": -0.2, "p": 2.0, "spr_bps": None}, None, 0, [{"form": "424B4", "items": []}], [{"ReasonCode": "LUDP"}], None)
        self.assertEqual((row["parts"], row["stage"], row["score"]), ({"dilution_filing": -1.0, "volatility_halt": 1.0}, "moving", 0.0))

    def test_board_threshold_and_order(self):
        state = M.State()
        state.features = {"A": {"s": "A", "chg": 0.02, "p": 1, "v": None, "spr_bps": None}, "B": {"s": "B", "chg": 0.06, "p": 1, "v": None, "spr_bps": None}}
        state.halts["A"].append({"IssueSymbol": "A", "ReasonCode": "T1"})
        state.filings["C"].append({"form": "SC TO-T", "items": []})
        board = M.build_board(state, datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc))
        self.assertEqual([r["symbol"] for r in board], ["A"])  # B has no incentive, C scores 1.5 < 2


class SinkFiles(unittest.TestCase):
    def test_owner_only_files_and_atomic_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            sink.write("news", {"a": 1})
            path = sink.replace("board.json", b"{}")
            sink.replace("snapshots/100000.json.gz", gzip.compress(json.dumps({"rows": []}).encode()))
            sink.close()
            news = next(Path(tmp).glob("*/news.jsonl"))
            self.assertEqual(news.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(news.read_text(), '{"a":1}\n')
            self.assertFalse(list(Path(tmp).glob("*/*.tmp")))


if __name__ == "__main__":
    unittest.main()
