"""Synthetic fixtures for blueprints/us-equities/incentive-monitor/monitor.py (local integration; no network)."""
from __future__ import annotations

import asyncio
import contextlib
import gzip
import hashlib
import io
import json
import os
import pwd
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

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
        self.assertEqual(rows, [{"drained_at": "2026-09-24T10:30", "root": "ABC", "cells": {"C|0-7": [310, 152000.0, 2], "P|31+": [5, 500.0, 1]}}])
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
        board, incentive = M.build_board(state, datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc))
        self.assertEqual([r["symbol"] for r in board], ["A"])  # B has no incentive, C scores 1.5 < 2
        self.assertEqual(incentive, ["A", "C"])  # every non-price incentive, whatever its score

    def test_news_counts_articles_once_inside_30_minutes(self):
        state = M.State()
        at = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)
        state.news["N"] = {1: at.timestamp() - 60, 2: at.timestamp() - 3600}
        state.halts["N"].append({"IssueSymbol": "N", "ReasonCode": "T1"})
        board, _ = M.build_board(state, at)
        self.assertEqual(board[0]["parts"]["news"], 1.0)
        self.assertEqual(list(state.news["N"]), [1])  # the expired article is pruned

    def test_option_roots_map_to_equities(self):
        universe = {"TSLA", "BRK.B", "SPY"}
        self.assertEqual([M.root_symbol(r, universe) for r in ("TSLA", "TSLA1", "BRKB", "SPXW", "X")], ["TSLA", "TSLA", "BRK.B", None, None])
        state = M.State()
        state.universe = universe
        state.options.day["TSLA1"].update({"C_premium": 900_000, "P_premium": 1, "C_premium_0_7": 300_000, "large_prints": 3})
        board, incentive = M.build_board(state, datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(([r["symbol"] for r in board], incentive), (["TSLA"], ["TSLA"]))

    def test_filings_credit_the_issuer_not_the_filer(self):
        state = M.State()
        M.attach_filing(state, {"form": "SC TO-T", "role": "Filed by", "tickers": ["BIDDER"]})
        M.attach_filing(state, {"form": "SC TO-T", "role": "Subject", "tickers": ["TARGET"]})
        M.attach_filing(state, {"form": "8-K", "role": "Filer", "tickers": ["ISSUER"]})
        M.attach_filing(state, {"form": "425", "role": "Filer", "tickers": ["ACQUIRER"]})   # an M&A form without a Subject role
        M.attach_filing(state, {"form": "425", "role": "Subject", "tickers": ["TARGETB"]})
        self.assertEqual(sorted(state.filings), ["ISSUER", "TARGET", "TARGETB"])

    def test_volatility_halt_is_not_a_non_price_incentive(self):
        state = M.State()
        state.halts["V"].append({"IssueSymbol": "V", "ReasonCode": "LUDP"})
        state.features = {"V": {"s": "V", "chg": 0.02, "p": 1, "v": None, "spr_bps": None}}
        _, incentive = M.build_board(state, datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(incentive, [])

    def test_torn_last_line_is_terminated_before_appending(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            path = sink.path("news.jsonl")
            path.parent.mkdir(parents=True)
            path.write_text('{"a":1}\n{"b":')
            sink.write("news", {"c": 3})
            sink.close()
            self.assertEqual(path.read_text(), '{"a":1}\n{"b":\n{"c":3}\n')


class Restart(unittest.TestCase):
    def test_restore_rebuilds_session_state_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = Path(tmp)
            rows = {"edgar": [{"accession": "a1", "cik": 1, "role": "Subject", "form": "SC TO-T", "tickers": ["T"]},
                              {"accession": "a1", "cik": 1, "role": "Subject", "form": "SC TO-T", "tickers": ["T"]}],
                    "news": [{"id": 7, "received_at": "2026-09-24T14:00:00+00:00", "symbols": ["N"]}],
                    "options-minute": [{"root": "R", "cells": {"C|0-7": [10, 1000.0, 2], "P|31+": [1, 50.0, 1]}}],
                    "options-large": [{"root": "R"}]}
            for name, items in rows.items():
                (day / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in items) + "not json\n")
            state = M.State()
            counts = M.restore(state, day)
            self.assertEqual((counts["edgar"], counts["news"], counts["options_minutes"], counts["options_large"], counts.get("halts", 0)), (1, 1, 1, 1, 0))
            self.assertEqual(counts["news_unreadable"], 1)
            self.assertEqual(len(state.filings["T"]), 1)
            self.assertEqual(state.news["N"], {7: datetime(2026, 9, 24, 14, tzinfo=timezone.utc).timestamp()})
            self.assertEqual(dict(state.options.day["R"]), {"C_volume": 10, "C_premium": 1000.0, "C_premium_0_7": 1000.0, "P_volume": 1, "P_premium": 50.0, "large_prints": 1})


class HaltRestore(unittest.TestCase):
    def test_todays_halts_are_restored_once_and_earlier_days_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            day = Path(tmp)
            state = M.State()
            state.today = date(2026, 9, 24)
            rows = [{"IssueSymbol": "PMAX", "HaltDate": "09/24/2026", "HaltTime": "10:08:56.356", "ReasonCode": "T1", "received_at": "a"},
                    {"IssueSymbol": "PMAX", "HaltDate": "09/24/2026", "HaltTime": "10:08:56.356", "ReasonCode": "T1", "ResumptionTradeTime": "10:20:00", "received_at": "b"},
                    {"IssueSymbol": "OLD", "HaltDate": "09/23/2026", "HaltTime": "15:00:00", "ReasonCode": "T1", "received_at": "c"}]
            (day / "halts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            counts = M.restore(state, day)
            self.assertEqual((counts["halts"], len(state.halts["PMAX"]), "OLD" in state.halts), (2, 1, False))
            self.assertEqual(state.halt_rows[("PMAX", "09/24/2026", "10:08:56.356")]["ResumptionTradeTime"], "10:20:00")


class Halts(unittest.TestCase):
    def test_only_today_and_changes_are_kept(self):
        class FakeHttp:
            def __init__(self, payload):
                self.payload = payload

            def get(self, url, kind, headers, timeout=20):
                assert "sec.gov" not in url and "@" not in headers["User-Agent"]
                return self.payload
        state = M.State()
        state.today = date(2026, 9, 24)
        old = HALTS.replace(b"<ndaq:HaltDate>09/24/2026", b"<ndaq:HaltDate>09/23/2026")
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            self.assertEqual(M.poll_halts(FakeHttp(old), state, sink), 0)
            self.assertEqual(M.poll_halts(FakeHttp(HALTS), state, sink), 1)
            self.assertEqual(M.poll_halts(FakeHttp(HALTS), state, sink), 0)
            resumed = HALTS.replace(b"<ndaq:ResumptionTradeTime />", b"<ndaq:ResumptionTradeTime>10:20:00</ndaq:ResumptionTradeTime>")
            self.assertEqual(M.poll_halts(FakeHttp(resumed), state, sink), 1)
            self.assertEqual(len(state.halts["PMAX"]), 1)
            sink.close()


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

    def test_shared_files_are_owner_only_outside_the_day_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = M.Sink(Path(tmp)).replace("finra/CNMSshvol20260923.txt", b"x", shared=True)
            self.assertEqual(path, Path(tmp) / "finra" / "CNMSshvol20260923.txt")
            self.assertEqual((path.stat().st_mode & 0o777, path.parent.stat().st_mode & 0o777), (0o600, 0o700))


# ---------------------------------------------------------------- monitor v2 (synthetic fixtures; no network)

def ulid(ms: int, tail: str = "0" * 16) -> str:
    """A synthetic ULID carrying ``ms`` milliseconds (Crockford base32)."""
    head = ""
    for _ in range(10):
        head = M.CROCKFORD[ms % 32] + head
        ms //= 32
    return head + tail


def ca_event(eid, kind, action="insert", at="2026-09-24T12:00:00.000000Z", **ca):
    return {"event_id": eid, "at": at, "action": action, "region": "us", "event_type": f"{kind}_corporateaction_event",
            "ca": {"id": ca.pop("id", "ca-1"), "process_date": ca.pop("process_date", "2026-09-30"), **ca}}


def opt(iv, delta=0.5, v=10, bar_t="2026-09-24T04:00:00Z"):
    return {"impliedVolatility": iv, "greeks": {"delta": delta, "gamma": 0.1, "theta": -0.05, "vega": 0.02, "rho": 0.01},
            "latestQuote": {"bp": 1.0, "ap": 1.1, "t": "2026-09-24T15:00:00Z"}, "dailyBar": {"t": bar_t, "v": v}}


FINRA = ("Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\r\n"
         "20260923|AAA|850000.5|10|1000000.5|B,Q,N\r\n"
         "20260923|BF/B|1000|0|4000|B,Q,N\r\n"
         "20260923|ZERO|0|0|0|Q\r\n"
         "3\r\n").encode()


class Response:
    """A urlopen-style response over fixed lines (no network)."""

    def __init__(self, lines=(), body=b"{}", headers=None):
        self.lines, self.body, self.headers = [line.encode() for line in lines], body, headers or {}

    def __iter__(self):
        return iter(self.lines)

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def records(tmp, name):
    return [json.loads(line) for line in next(Path(tmp).glob(f"*/{name}.jsonl")).read_text().splitlines()]


class HaltMerge(unittest.TestCase):
    def test_status_codes_by_plan(self):
        cases = [({"sc": "H", "z": "C"}, "halted"), ({"sc": "P", "z": "C"}, "paused"), ({"sc": "Q", "z": "O"}, "quotation_only"),
                 ({"sc": "T", "z": "C"}, "trading"), ({"sc": "2", "z": "A"}, "halted"), ({"sc": "3", "z": "B"}, "trading")]
        self.assertEqual([M.status_state(m) for m, _ in cases], [s for _, s in cases])
        for notice in ("5", "6", "7", "A", "E", "F"):  # CTA indications, imbalances, SSR and LULD notices are not halts
            self.assertIsNone(M.status_state({"sc": notice, "z": "B"}))
        self.assertIsNone(M.status_state({"sc": "H", "z": "A"}))  # a UTP code on a CTA tape
        self.assertEqual([M.halt_category("C", r) for r in ("T1", "T12", "LUDP", "H4", None)], ["news", "news", "volatility", "other", "other"])
        self.assertEqual([M.halt_category("A", r) for r in ("P", "D", "A", "C", "M", "X", "T1")],
                         ["news", "news", "news", "news", "volatility", "other", "other"])

    def test_stream_and_rss_merge_on_event_time(self):
        book = M.HaltBook()
        row = {"IssueSymbol": "PMAX", "HaltDate": "09/24/2026", "HaltTime": "10:08:56.356", "ReasonCode": "T1", "received_at": "r1"}
        self.assertEqual((book.rss_row(row), book.rss_row(row)), (1, 0))  # a re-polled row adds nothing
        state = book.state("PMAX", datetime(2026, 9, 24, 14, 10, tzinfo=timezone.utc))
        self.assertEqual((state["state"], state["source"], state["category"], state["since"]),
                         ("halted", "rss", "news", "2026-09-24T14:08:56.356000+00:00"))
        book.stream_status({"T": "s", "S": "PMAX", "sc": "Q", "rc": "T3", "t": "2026-09-24T14:19:00.000000001Z", "z": "C"}, "s1")
        self.assertEqual(book.state("PMAX", datetime(2026, 9, 24, 14, 19, 30, tzinfo=timezone.utc))["state"], "quotation_only")
        book.stream_status({"T": "s", "S": "PMAX", "sc": "T", "rc": "C11", "t": "2026-09-24T14:20:00.5Z", "z": "C"}, "s2")
        book.rss_row({**row, "ResumptionDate": "09/24/2026", "ResumptionQuoteTime": "10:19:00", "ResumptionTradeTime": "10:20:00"})
        state = book.state("PMAX", datetime(2026, 9, 24, 14, 21, tzinfo=timezone.utc))
        self.assertEqual((state["state"], state["source"], state["reason"], state["halts"]), ("trading", "stream", "T1", {"rss": 1, "stream": 0}))
        self.assertIsNone(book.stream_category("PMAX"))  # the stream saw only the resumptions

    def test_a_scheduled_rss_resumption_counts_only_once_due(self):
        book = M.HaltBook()
        book.rss_row({"IssueSymbol": "X", "HaltDate": "09/24/2026", "HaltTime": "11:00:00", "ReasonCode": "T1",
                      "ResumptionDate": "09/24/2026", "ResumptionTradeTime": "12:00:00"})
        self.assertEqual(book.state("X", datetime(2026, 9, 24, 15, 30, tzinfo=timezone.utc))["state"], "halted")  # 11:30 ET
        self.assertEqual(book.state("X", datetime(2026, 9, 24, 16, 0, 6, tzinfo=timezone.utc))["state"], "trading")
        self.assertIsNone(book.state("X", datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc)))  # before the halt

    def test_stream_category_ignores_notices_and_ranks_news_first(self):
        book = M.HaltBook()
        self.assertFalse(book.stream_status({"S": "N", "sc": "F", "rc": "", "t": "2026-09-24T14:00:00Z", "z": "A"}, "r"))
        self.assertFalse(book.stream_status({"S": "N", "sc": "2", "rc": "M", "t": "not a time", "z": "A"}, "r"))
        book.stream_status({"S": "N", "sc": "2", "rc": "M", "t": "2026-09-24T14:00:00Z", "z": "A"}, "r")
        self.assertEqual(book.stream_category("N"), "volatility")
        book.stream_status({"S": "N", "sc": "2", "rc": "P", "t": "2026-09-24T15:00:00Z", "z": "A"}, "r")
        self.assertEqual((book.stream_category("N"), book.symbols("stream"), book.symbols("rss")), ("news", {"N"}, set()))

    def test_rss_code_m_is_a_volatility_pause_in_the_merged_state(self):
        book = M.HaltBook()  # Nasdaq Trader code M: a volatility pause in an exchange-listed issue
        book.rss_row({"IssueSymbol": "NYSEX", "HaltDate": "09/24/2026", "HaltTime": "10:00:00", "ReasonCode": "M"})
        state = book.state("NYSEX", datetime(2026, 9, 24, 14, 1, tzinfo=timezone.utc))
        self.assertEqual((state["state"], state["category"]), ("paused", "volatility"))
        self.assertIsNone(M.score("NYSEX", None, None, 0, [], [{"ReasonCode": "M"}], None)["parts"].get("volatility_halt"))  # v1 unchanged

    def test_luld_band_distance_from_the_price(self):
        book = M.HaltBook()
        book.set_band({"T": "l", "S": "IONM", "u": 3.24, "d": 2.65, "i": "B", "t": "2023-04-06T13:34:45.565004401Z", "z": "C"}, "r")
        band = book.band("IONM", 3.0)
        self.assertEqual((band["to_up_bps"], band["to_down_bps"], band["received_at"]), (800.0, 1166.7, "r"))
        self.assertIsNone(book.band("OTHER"))

    def test_rss_halts_feed_the_merged_state(self):
        class FakeHttp:
            def get(self, url, kind, headers, timeout=20):
                return HALTS
        state = M.State()
        state.today = date(2026, 9, 24)
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            M.poll_halts(FakeHttp(), state, sink)
            sink.close()
        self.assertEqual(state.haltbook.state("PMAX", datetime(2026, 9, 24, 14, 10, tzinfo=timezone.utc))["category"], "news")
        self.assertEqual(len(state.halts["PMAX"]), 1)  # the v1 halt rows are unchanged


class StreamConflict(unittest.TestCase):
    def test_a_406_on_the_iex_endpoint_waits_instead_of_contending(self):
        connects, holder = [], {}

        class WS:
            async def send(self, data):
                holder["subscribe"] = json.loads(data)

            async def recv(self):
                return json.dumps([{"T": "error", "code": 406, "msg": "connection limit exceeded"}])

        class Connect:
            def __init__(self, url, **kwargs):
                connects.append(url)
                if len(connects) >= 2:
                    holder["stop"].set()

            async def __aenter__(self):
                return WS()

            async def __aexit__(self, *exc):
                return False

        fakes = {"websockets": types.SimpleNamespace(connect=Connect), "msgpack": types.SimpleNamespace(packb=None, unpackb=None)}
        with tempfile.TemporaryDirectory() as tmp:
            sink, state = M.Sink(Path(tmp)), M.State()

            async def main():
                holder["stop"] = asyncio.Event()
                await M.stream("iex_status", M.IEX_WS, {"action": "subscribe", "statuses": ["*"], "lulds": ["*"]}, {}, lambda m: None,
                               state, sink, holder["stop"], False, conflict_wait=0.05)
            started = time.monotonic()
            with mock.patch.dict(sys.modules, fakes):
                asyncio.run(main())
            sink.close()
            events = [r["event"] for r in records(tmp, "monitor")]
        self.assertLess(time.monotonic() - started, 1.5)  # the ordinary backoff would have waited 2 s
        self.assertEqual(connects, [M.IEX_WS, M.IEX_WS])
        self.assertEqual(events, ["stream_connected", "stream_error", "stream_conflict", "stream_connected"])
        self.assertEqual(holder["subscribe"]["statuses"], ["*"])


class EventsSSE(unittest.TestCase):
    today = date(2026, 9, 24)

    def test_event_stream_framing(self):
        lines = [": keep-alive\r\n", "id: 01A\r\n", "event: message\r\n", 'data: [{"a": 1},\r\n', 'data: {"a": 2}]\r\n', "\r\n",
                 b"retry: 3000\n", b'data:{"b":1}\n', b"\n", "\n", 'data: {"c": 1}']  # the last event is never terminated
        events = list(M.sse_events(lines))
        self.assertEqual(events, [{"id": "01A", "event": "message", "data": '[{"a": 1},\n{"a": 2}]'},
                                  {"id": "01A", "event": "message", "data": '{"b":1}'}])
        self.assertEqual((M.ca_event_list(events[0]["data"]), M.ca_event_list(events[1]["data"])), ([{"a": 1}, {"a": 2}], [{"b": 1}]))

    def test_ulid_time(self):
        found = M.ulid_time(ulid(1_790_263_944_995))
        self.assertLess(abs((found - datetime.fromtimestamp(1_790_263_944.995, timezone.utc)).total_seconds()), 0.002)
        self.assertIsNone(M.ulid_time("not-a-ulid"))

    def test_surfaced_actions_windows_and_versions(self):
        cas, e = M.CorporateActions(), lambda n: ulid(1_790_000_000_000 + n)
        self.assertTrue(cas.observe(ca_event(e(1), "reverse_split", id="rs", symbol="RSX", new_symbol="RSXD", old_rate="10", new_rate="1",
                                             ex_date="2026-09-28", at="2026-09-20T12:00:00Z")))
        self.assertTrue(cas.observe(ca_event(e(2), "cash_merger", id="cm", acquiree_symbol="TGT", acquirer_symbol="BUY", rate="42.50",
                                             effective_date="2026-10-20", at="2026-09-20T12:00:00Z")))
        self.assertTrue(cas.observe(ca_event(e(3), "name_change", id="nc", old_symbol="OLD", new_symbol="NEW", at="2026-09-20T12:00:00Z")))
        self.assertTrue(cas.observe(ca_event(e(4), "spin_off", id="so", source_symbol="PAR", new_symbol="KID", source_rate="1",
                                             new_rate="0.5", ex_date="2026-12-15", at="2026-09-24T13:00:00Z")))  # announced today
        self.assertTrue(cas.observe(ca_event(e(5), "forward_split", id="fs", symbol="FWD", ex_date="2026-09-23", at="2026-09-01T12:00:00Z")))
        self.assertTrue(cas.observe(ca_event(e(6), "spin_off", id="far", source_symbol="FAR", new_symbol="FAR2", ex_date="2027-03-01",
                                             at="2026-09-01T12:00:00Z")))  # beyond the context window
        self.assertFalse(cas.observe(ca_event(e(7), "cash_dividend", id="dv", symbol="DIV", rate="0.24", ex_date="2026-09-25")))
        context = cas.by_symbol(self.today)
        self.assertEqual({s for s, items in context.items() if any(i["in_window"] for i in items)}, {"RSX", "RSXD", "OLD", "NEW", "PAR", "KID", "FWD"})
        self.assertEqual({s for s, items in context.items() if not any(i["in_window"] for i in items)}, {"TGT", "BUY"})
        self.assertEqual((context["TGT"][0]["role"], context["TGT"][0]["days"], context["TGT"][0]["terms"]["rate"]), ("acquiree_symbol", 26, "42.50"))
        self.assertFalse(cas.observe(ca_event(e(0), "reverse_split", action="update", id="rs", symbol="RSX", ex_date="2026-10-30")))  # older
        self.assertTrue(cas.observe(ca_event(e(9), "reverse_split", action="delete", id="rs", symbol="RSX")))
        self.assertFalse(cas.observe(ca_event(e(8), "reverse_split", id="rs", symbol="RSX", ex_date="2026-09-28")))  # replayed after the delete
        self.assertNotIn("RSX", cas.by_symbol(self.today))

    def test_archive_every_event_deduplicate_and_resume_with_last_event_id(self):
        a, b, c = ulid(1_790_000_000_001), ulid(1_790_000_000_002), ulid(1_790_000_000_003)
        dividend = ca_event(a, "cash_dividend", id="d1", symbol="DIV", rate="0.24", ex_date="2026-09-25")
        split = ca_event(b, "reverse_split", id="r1", symbol="RSX", ex_date="2026-09-25")
        rename = ca_event(c, "name_change", id="n1", old_symbol="OLD", new_symbol="NEW")
        first = [f"id: {a}\n", f"data: {json.dumps([dividend])}\n", "\n", f"id: {b}\n", f"data: {json.dumps([split])}\n", "\n"]
        second = [f"id: {b}\n", f"data: {json.dumps([split])}\n", "\n", "data: not json\n", "\n", f"id: {c}\n", f"data: {json.dumps([rename])}\n", "\n"]
        responses, requests = [Response(first), Response(second)], []
        with tempfile.TemporaryDirectory() as tmp:
            sink, state = M.Sink(Path(tmp)), M.State()
            state.today = self.today
            events = M.EventStream({"APCA-API-KEY-ID": "k", "APCA-API-SECRET-KEY": "s"}, sink, state, datetime(2026, 9, 24, 4, tzinfo=timezone.utc),
                                   connects_per_min=10, backoff=lambda attempt: 0)

            def opener(request, timeout):
                requests.append(request)
                if not responses:
                    events.stop_event.set()
                    raise OSError("synthetic end")
                return responses.pop(0)
            events.opener = opener
            events.run()
            sink.close()
            archived = records(tmp, "corporate-actions")
            monitor = [r["event"] for r in records(tmp, "monitor")]
        self.assertEqual([r.get("event_id") for r in archived], [a, b, None, c])  # every event, the dividend included, once
        self.assertTrue(all(r["received_at"] for r in archived))
        self.assertEqual((archived[2]["unparsed"], archived[1]["sse_id"]), ("not json", b))
        self.assertEqual((events.counts["duplicates"], events.counts["connects"], events.last_id), (1, 3, c))
        self.assertIn("since=2026-09-24T04%3A00%3A00Z", requests[0].full_url)
        self.assertIsNone(requests[0].get_header("Last-event-id"))
        self.assertEqual((requests[1].full_url, requests[1].get_header("Last-event-id")), (M.CA_EVENTS, b))
        self.assertEqual(requests[0].get_header("Accept"), "text/event-stream")
        self.assertEqual(set(state.ca.by_symbol(self.today)), {"RSX", "OLD", "NEW"})
        self.assertEqual(monitor, ["stream_connected", "stream_down", "stream_connected", "stream_down"])

    def test_context_replay_is_bounded_and_not_archived(self):
        split = ca_event(ulid(1_790_000_000_001), "reverse_split", id="r1", symbol="RSX", ex_date="2026-09-25")
        requests = []
        with tempfile.TemporaryDirectory() as tmp:
            sink, state = M.Sink(Path(tmp)), M.State()
            events = M.EventStream({}, sink, state, datetime(2026, 9, 24, 4, tzinfo=timezone.utc),
                                   opener=lambda request, timeout: requests.append(request) or Response([f"data: {json.dumps([split])}\n", "\n"]))
            n = events.replay_context(datetime(2026, 8, 25, 4, tzinfo=timezone.utc), datetime(2026, 9, 24, 14, 59, tzinfo=timezone.utc))
            sink.close()
            self.assertFalse(list(Path(tmp).glob("*/corporate-actions.jsonl")))
        self.assertEqual((n, events.counts["context_events"]), (1, 1))
        self.assertIn("RSX", state.ca.by_symbol(date(2026, 9, 24)))
        url = requests[0].full_url
        self.assertIn("until=2026-09-24T14%3A59%3A00Z", url)
        self.assertIn("reverse_split_corporateaction_event", url)
        self.assertNotIn("cash_dividend", url)

    def test_resume_point_is_the_last_valid_id_of_the_newest_archive(self):
        with tempfile.TemporaryDirectory() as tmp:  # the archive appends only ids newer than its last, so the last is the newest
            root = Path(tmp)
            for name, ids in (("20260922", [ulid(5)]), ("20260923", [ulid(1), ulid(2), ulid(3)])):
                (root / name).mkdir()
                (root / name / "corporate-actions.jsonl").write_text("".join(json.dumps({"event_id": i}) + "\n" for i in ids)
                                                                     + '{"unparsed": "x"}\n{"event_id": "not-a-ulid"}\n{"torn')
            (root / "20260924").mkdir()   # a newer day without an archive
            self.assertEqual(M.last_archived_event_id(root), ulid(3))
            self.assertIsNone(M.last_archived_event_id(root / "empty"))
            big = root / "20260925"   # read from the end in blocks: a trailing line longer than one block is skipped whole
            big.mkdir()
            rows = [json.dumps({"event_id": ulid(10 + i), "pad": "x" * 200}) for i in range(2000)]
            (big / "corporate-actions.jsonl").write_text("\n".join(rows) + "\n" + json.dumps({"unparsed": "y" * 70_000}) + "\n")
            self.assertEqual(M.last_archived_event_id(root), ulid(2009))


class Screener(unittest.TestCase):
    def test_ranks_from_the_three_screens(self):
        ranks = M.screener_ranks({"most_actives": [{"symbol": "A", "volume": 9, "trade_count": 1}, {"symbol": "B", "volume": 5, "trade_count": 7}]},
                                 {"most_actives": [{"symbol": "B"}, {"symbol": "A"}]},
                                 {"gainers": [{"symbol": "G", "percent_change": 145.56}], "losers": [{"symbol": "B", "percent_change": -30.0}]})
        self.assertEqual(ranks["A"], {"volume_rank": 1, "trades_rank": 2})
        self.assertEqual(ranks["B"], {"volume_rank": 2, "trades_rank": 1, "loser_rank": 1, "pct_change": -30.0})
        self.assertEqual(ranks["G"], {"gainer_rank": 1, "pct_change": 145.56})

    def test_poll_makes_three_calls_and_records_the_receipt(self):
        class FakeHttp:
            def __init__(self):
                self.calls = []

            def alpaca_json(self, base, path, params):
                self.calls.append((path, params))
                return {"most_actives": [{"symbol": "A"}]} if "most-actives" in path else {"gainers": [], "losers": [{"symbol": "L"}]}
        http, state = FakeHttp(), M.State()
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            self.assertEqual(M.poll_screener(http, state, sink), 2)
            sink.close()
            (row,) = records(tmp, "screener")
        self.assertEqual(http.calls, [(M.SCREENER_ACTIVES, {"by": "volume", "top": 100}), (M.SCREENER_ACTIVES, {"by": "trades", "top": 100}),
                                      (M.SCREENER_MOVERS, {"top": 50})])
        self.assertIn("received_at", row)
        self.assertEqual(state.screener["L"], {"loser_rank": 1, "pct_change": None})


class OptionChains(unittest.TestCase):
    today = date(2026, 9, 24)

    def test_near_the_money_iv_of_the_first_expiry(self):
        snaps = {"ABC261002C00010000": opt(0.50), "ABC261002P00010000": opt(0.70, delta=-0.5, v=5), "ABC261002C00011000": opt(0.45),
                 "ABC261002P00009000": opt(None), "ABC261002C00010500": opt(0), "ABC261009C00010000": opt(0.30),
                 "ABC1261002C00010000": opt(0.99), "ABC261002C00012000": opt(0.4, bar_t="2026-09-23T04:00:00Z")}
        s = M.chain_summary("ABC", snaps, 10.2, self.today)
        self.assertEqual((s["expiry"], s["dte"], s["strike"], s["call_iv"], s["put_iv"], s["atm_iv"]), ("2026-10-02", 8, 10.0, 0.5, 0.7, 0.6))
        self.assertEqual((s["contracts"], s["call_volume"], s["put_volume"]), (7, 40, 15))  # the adjusted root is left out; yesterday's bar too
        self.assertEqual([r["symbol"] for r in s["near"]], ["ABC261002C00010000", "ABC261002P00010000", "ABC261002C00010500", "ABC261002C00011000"])
        self.assertEqual((s["near"][1]["delta"], s["near"][1]["bid"]), (-0.5, 1.0))
        no_price = M.chain_summary("ABC", snaps, None, self.today)
        self.assertEqual((no_price["atm_iv"], no_price["call_volume"]), (None, 40))
        self.assertEqual(M.chain_summary("ABC", {}, 10.0, self.today)["contracts"], 0)

    def test_iv_change_baselines_and_runup(self):
        iv, at = M.IVTracker(), (lambda h, m: datetime(2026, 9, 24, h, m, tzinfo=M.ET))
        iv.observe("ABC", at(9, 40), {"atm_iv": 0.40, "expiry": "2026-10-02"})  # before 09:45: not a baseline
        self.assertIsNone(iv.change("ABC", at(9, 40)))
        iv.observe("ABC", at(9, 50), {"atm_iv": 0.50, "expiry": "2026-10-02"})
        iv.observe("ABC", at(10, 10), {"atm_iv": 0.65, "expiry": "2026-10-02"})
        self.assertIsNone(iv.runup("ABC", at(10, 10)))  # +30% on a baseline only 20 minutes old
        iv.observe("ABC", at(10, 30), {"atm_iv": 0.61, "expiry": "2026-10-02"})
        found = iv.runup("ABC", at(10, 30))
        self.assertEqual((found["baseline"], found["chg"], found["baseline_age_s"]), ("first_today", 0.22, 2400))
        iv.prev["ABC"] = {"at": "2026-09-23T19:55:00+00:00", "iv": 0.60, "expiry": "2026-10-02"}
        self.assertEqual(iv.change("ABC", at(10, 30))["baseline"], "previous_session")  # same expiry: the previous session wins
        self.assertIsNone(iv.runup("ABC", at(10, 30)))
        iv.prev["ABC"]["expiry"] = "2026-09-25"
        self.assertEqual(iv.change("ABC", at(10, 30))["baseline"], "first_today")  # another expiry is not comparable
        iv.observe("ABC", at(10, 31), {"atm_iv": None})
        self.assertEqual(iv.last["ABC"]["iv"], 0.61)
        iv.prev["ABC"] = {"at": None, "iv": 0.30, "expiry": "2026-10-02"}  # a restored row without a receive time is never a baseline
        self.assertEqual(iv.change("ABC", at(10, 30))["baseline"], "first_today")

    def test_open_interest_summary(self):
        contracts = [{"symbol": "ABC261002C00010000", "type": "call", "open_interest": "237", "open_interest_date": "2026-09-23"},
                     {"symbol": "ABC261002P00010000", "type": "put", "open_interest": "40", "open_interest_date": "2026-09-23"},
                     {"symbol": "ABC261009C00010000", "type": "call", "open_interest": None},
                     {"symbol": "ABC261009P00010000", "type": "put", "open_interest": "inf"}]
        s = M.oi_summary(contracts[:3], True)
        self.assertEqual(M.oi_summary(contracts, True)["put_oi"], 40)  # an unreadable value is skipped
        self.assertEqual((s["call_oi"], s["put_oi"], s["with_oi"], s["contracts"], s["oi_date"], s["truncated"]), (237, 40, 2, 3, "2026-09-23", True))
        self.assertEqual(s["by_contract"]["ABC261002C00010000"], 237)

    def test_polls_stay_inside_their_bounds(self):
        class FakeHttp:
            def __init__(self):
                self.calls = []

            def alpaca_json(self, base, path, params):
                self.calls.append((base, path, dict(params)))
                if path.endswith("/NONE"):
                    return {"snapshots": {}, "next_page_token": None}
                if path == M.OPTION_CONTRACTS:
                    return {"option_contracts": [{"symbol": "ABC261002C00010000", "type": "call", "open_interest": "5"}], "next_page_token": None}
                return {"snapshots": {"ABC261002C00010000": opt(0.5), "ABC261002P00010000": opt(0.7)}, "next_page_token": "more"}

            def remaining(self, host):
                return None
        args = M.parser().parse_args(["run", "--standalone", "--env-file", "e", "--out", "o", "--oi-per-sweep", "1"])
        http, state = FakeHttp(), M.State()
        state.today, state.features = self.today, {"ABC": {"p": 10.2}}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(M, "chain_session_open", lambda at: True):   # inside 09:45-16:00 ET
            sink = M.Sink(Path(tmp))
            self.assertEqual(M.poll_option_chains(http, state, sink, args, ["ABC", "NONE"]), {"roots": 1, "empty": 1})
            self.assertEqual(M.poll_option_oi(http, state, sink, args, ["ABC", "XYZ"]), 1)  # oi_per_sweep
            self.assertEqual(M.poll_option_oi(http, state, sink, args, ["ABC"]), 0)  # once a day per root
            sink.close()
            (row,) = records(tmp, "options-iv")
            (oi,) = records(tmp, "options-oi")
        self.assertEqual(state.no_options, {"NONE"})
        base, path, params = next(c for c in http.calls if c[1].endswith("/ABC"))
        self.assertEqual((base, params["feed"], params["limit"], params["expiration_date_gte"], params["expiration_date_lte"],
                          params["strike_price_gte"], params["strike_price_lte"]), (M.DATA, "opra", 1000, "2026-10-01", "2026-11-05", 9.18, 11.22))
        self.assertEqual(sum(1 for c in http.calls if c[1].endswith("/ABC")), 1)  # one page although more exist
        self.assertEqual((row["symbol"], row["atm_iv"], row["truncated"], row["pages"]), ("ABC", 0.6, True, 1))
        self.assertEqual((oi["symbol"], oi["call_oi"], state.oi["ABC"]["call_oi"]), ("ABC", 5, 5))
        self.assertTrue(row["received_at"] and oi["received_at"])
        self.assertEqual(state.iv.last["ABC"]["iv"], 0.6)
        self.assertEqual(next(c for c in http.calls if c[1] == M.OPTION_CONTRACTS)[0], M.TRADING)

    def test_a_refused_root_is_not_asked_again_today(self):
        class FakeHttp:
            def __init__(self):
                self.symbols = []

            def alpaca_json(self, base, path, params):
                self.symbols.append(params["underlying_symbols"])
                if params["underlying_symbols"] == "BAD":
                    raise urllib.error.HTTPError(path, 422, "unprocessable", {}, None)
                return {"option_contracts": [], "next_page_token": None}

            def remaining(self, host):
                return None
        args = M.parser().parse_args(["run", "--standalone", "--env-file", "e", "--out", "o"])
        http, state = FakeHttp(), M.State()
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            self.assertEqual(M.poll_option_oi(http, state, sink, args, ["BAD", "OK"]), 1)
            self.assertEqual(M.poll_option_oi(http, state, sink, args, ["BAD", "OK"]), 0)
            sink.close()
        self.assertEqual((http.symbols, state.oi["BAD"]), (["BAD", "OK"], {"error": "http_422"}))

    def test_targets_are_the_top_candidates_with_options(self):
        rows = {s: {"symbol": s, "score": sc, "relvol": rv} for s, sc, rv in (("A", 3.0, None), ("B", 3.0, 5.0), ("C", 5.0, None), ("Z", 0, None), ("N", 4.0, None))}
        state = M.State()
        state.no_options = {"N"}
        self.assertEqual(M.option_targets(rows, state, 2), ["C", "B"])
        self.assertEqual(M.option_targets(rows, state, 10), ["C", "B", "A"])


class FinraShortVolume(unittest.TestCase):
    def test_parse_header_trailer_and_class_symbols(self):
        day, rows = M.parse_finra(FINRA)
        self.assertEqual((day, sorted(rows)), ("20260923", ["AAA", "BF.B", "ZERO"]))
        self.assertEqual((rows["AAA"]["ratio"], rows["BF.B"]["ratio"], rows["ZERO"]["ratio"]), (0.85, 0.25, None))
        self.assertEqual((M.short_volume_high(rows["AAA"]), M.short_volume_high(rows["BF.B"]), M.short_volume_high(rows["ZERO"])), (True, False, False))
        for broken, reason in ((FINRA.replace(b"3\r\n", b"4\r\n"), "finra_count_mismatch"), (FINRA.replace(b"3\r\n", b""), "finra_trailer"),
                               (FINRA.replace(b"Date|", b"Day|"), "finra_header"), (FINRA.replace(b"20260923|ZERO", b"20260922|ZERO"), "finra_mixed_dates"),
                               (FINRA.replace(b"|Q\r\n", b"\r\n"), "finra_row")):
            with self.assertRaisesRegex(ValueError, reason):
                M.parse_finra(broken)

    def test_due_dates(self):
        et = lambda *a: datetime(*a, tzinfo=M.ET)
        self.assertEqual(M.finra_due(et(2026, 9, 24, 17, 0)), date(2026, 9, 23))  # Thursday before publication
        self.assertEqual(M.finra_due(et(2026, 9, 24, 18, 5)), date(2026, 9, 24))
        self.assertEqual(M.finra_due(et(2026, 9, 28, 9, 0)), date(2026, 9, 25))  # Monday morning: Friday
        self.assertEqual(M.finra_due(et(2026, 9, 26, 20, 0)), date(2026, 9, 25))  # Saturday
        self.assertEqual(M.weekdays_back(date(2026, 9, 28), 3), [date(2026, 9, 28), date(2026, 9, 25), date(2026, 9, 24)])

    def test_one_request_per_sweep_missing_days_retried_later_and_files_owner_only(self):
        class FakeHttp:
            def __init__(self):
                self.urls = []

            def get(self, url, kind, headers, timeout=20):
                self.urls.append(url)
                assert "@" not in headers["User-Agent"]  # the declared SEC contact is sent to SEC only
                if url.endswith("20260924.txt"):
                    raise urllib.error.HTTPError(url, 403, "AccessDenied", {}, None)
                return FINRA
        http, state = FakeHttp(), M.State()
        now = datetime(2026, 9, 24, 18, 30, tzinfo=M.ET)
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            self.assertEqual(M.poll_finra(http, state, sink, now), "missing:20260924")
            self.assertEqual(M.poll_finra(http, state, sink, now), "20260923")  # the next sweep tries the previous weekday
            self.assertIsNone(M.poll_finra(http, state, sink, now))  # stored: no request
            stored = Path(tmp) / "finra" / "CNMSshvol20260923.txt"
            manifest = json.loads((Path(tmp) / "finra" / "CNMSshvol20260923.json").read_text())
            self.assertEqual((stored.stat().st_mode & 0o777, manifest["sha256"], manifest["rows"]), (0o600, hashlib.sha256(FINRA).hexdigest(), 3))
            self.assertTrue(manifest["received_at"])
        self.assertEqual([u.rsplit("/", 1)[1] for u in http.urls], ["CNMSshvol20260924.txt", "CNMSshvol20260923.txt"])
        self.assertEqual((state.short_volume_day, state.short_volume["BF.B"]["date"]), ("20260923", "20260923"))

    def test_join_with_the_prior_mean_from_stored_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "finra").mkdir()
            (root / "finra" / "CNMSshvol20260922.txt").write_bytes(FINRA.replace(b"20260923", b"20260922").replace(b"850000.5", b"500000.25"))
            (root / "finra" / "CNMSshvol20260923.txt").write_bytes(FINRA)
            (root / "finra" / "CNMSshvol20260924.txt").write_bytes(FINRA.replace(b"20260923", b"20260924"))  # after the due date
            day, rows = M.load_short_volume(root, date(2026, 9, 23))
        self.assertEqual((day, rows["AAA"]["ratio"], rows["AAA"]["ratio_prior_mean"], rows["AAA"]["prior_files"]), ("20260923", 0.85, 0.5, 1))


class Budgets(unittest.TestCase):
    def args(self, *extra):
        return M.parser().parse_args(["run", "--standalone", "--env-file", "e", "--out", "o", *extra])

    def test_default_plan_is_inside_five_percent_of_the_data_limit(self):
        plan = M.plan_budget(13_500, self.args())
        self.assertEqual(plan["refusals"], [])
        self.assertEqual(plan["sweep_seconds"], 20.0)
        self.assertEqual(plan["per_sweep"], {"snapshots": 27, "screener": 3, "option_chains": 30, "option_contracts": 0, "edgar": 7,
                                             "nasdaq_halts": 1, "finra": 1})   # open interest is opt-in (--option-oi)
        self.assertEqual((plan["per_minute"], plan["once"]), ({"adv_bars": 68}, {"assets": 5, "sec_files": 5}))
        self.assertEqual((plan["data_per_min"], plan["data_first_min"], plan["data_cap_per_min"]), (180.0, 248.0, 500.0))
        self.assertEqual((plan["trading_per_min"], plan["trading_cap_per_min"], plan["nasdaq_per_min"]), (1.0, 10.0, 1.0))
        self.assertEqual(M.plan_budget(13_500, self.args("--option-oi"))["trading_per_min"], 7.0)
        self.assertEqual(plan["streams"]["corporate_actions"]["connects_per_min"], 2)

    def test_plans_above_the_caps_are_refused(self):
        refused = lambda *extra: M.plan_budget(13_500, self.args(*extra))["refusals"]
        self.assertEqual(refused("--sweep-seconds", "5", "--option-oi"), ["data_calls_above_5pct_of_limit", "trading_calls_above_5pct_of_limit"])  # 60 + 2 every 5 s
        self.assertEqual(refused("--option-roots", "150"), ["data_calls_above_5pct_of_limit"])
        self.assertEqual(refused("--oi-per-sweep", "4", "--option-oi"), ["trading_calls_above_5pct_of_limit"])
        self.assertEqual(refused("--oi-per-sweep", "4"), [])   # open interest off: no trading calls planned
        self.assertEqual(refused("--rss-seconds", "20"), ["nasdaq_rss_more_than_once_per_minute"])
        self.assertEqual(refused("--option-pages", "0"), ["invalid_bounds"])
        self.assertEqual(refused("--sweep-seconds", "5", "--no-option-chains", "--no-screener"), [])  # 324/min + 68 a minute

    def test_sources_by_url(self):
        urls = {"https://data.alpaca.markets/v2/stocks/snapshots?x": "snapshots", "https://data.alpaca.markets/v2/stocks/bars?x": "adv_bars",
                "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=50": "screener",
                "https://data.alpaca.markets/v1beta1/options/snapshots/ABC?feed=opra": "option_chains",
                "https://paper-api.alpaca.markets/v2/options/contracts?x": "option_contracts", "https://paper-api.alpaca.markets/v2/assets?x": "assets",
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent": "edgar", "https://www.sec.gov/files/company_tickers.json": "sec_files",
                "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts": "nasdaq_halts", M.FINRA_SHORT_VOLUME.format(day="20260923"): "finra",
                "https://example.invalid/x": "other"}
        self.assertEqual({u: M.source_of(u) for u in urls}, urls)

    def test_calls_over_a_cap_are_refused_before_any_request(self):
        opened = []

        def fake_urlopen(request, timeout):
            opened.append(request.full_url)
            return Response(body=b"{}", headers={"X-Ratelimit-Limit": "10000", "X-Ratelimit-Remaining": "9990", "X-Ratelimit-Reset": "1"})
        budget = M.Budget({"screener": 1}, {})
        http = M.Http({}, None, budget)
        with mock.patch.object(M.urllib.request, "urlopen", fake_urlopen):
            http.alpaca_json(M.DATA, M.SCREENER_MOVERS, {"top": 50})
            with self.assertRaises(M.BudgetExceeded):
                http.alpaca_json(M.DATA, M.SCREENER_ACTIVES, {"by": "volume"})
            with self.assertRaises(M.BudgetExceeded):
                http.get("https://example.invalid/x", "other", {})  # a source without a cap is refused
            budget.start_sweep()
            http.alpaca_json(M.DATA, M.SCREENER_ACTIVES, {"by": "trades"})
        self.assertEqual((len(opened), dict(budget.refused), dict(http.source_calls)), (2, {"screener": 1, "other": 1}, {"screener": 2}))
        self.assertEqual((http.data_remaining(), dict(http.calls)), (9990, {"alpaca": 2}))

    def test_without_a_budget_http_is_unchanged(self):
        with mock.patch.object(M.urllib.request, "urlopen", lambda request, timeout: Response(body=b"[]")):
            http = M.Http({}, None)
            self.assertEqual([http.get("https://example.invalid/x", "other", {}) for _ in range(3)], [b"[]"] * 3)
        self.assertIsNone(http.data_remaining())

    def test_a_second_holder_of_an_endpoint_is_refused_before_connecting(self):
        with tempfile.TemporaryDirectory() as tmp:
            leases = Path(tmp) / "leases"
            first, reason = M.acquire_lease(leases, "v2-iex")
            self.assertIsNone(reason)
            self.assertEqual(M.acquire_lease(leases, "v2-iex"), (None, "lease_held"))
            other, _ = M.acquire_lease(leases, "v1beta1-news")
            self.assertIsNotNone(other)
            os.close(first)
            os.close(other)
            again, reason = M.acquire_lease(leases, "v2-iex")
            self.assertIsNone(reason)
            os.close(again)
            self.assertEqual((leases / "v2-iex.lock").stat().st_mode & 0o777, 0o600)


class BoardV2(unittest.TestCase):
    at = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)  # 11:00 ET

    def state(self):
        state = M.State()
        state.today = date(2026, 9, 24)
        state.features = {s: {"s": s, "chg": 0.02, "p": 10.0, "v": None, "spr_bps": 10.0} for s in "ABCDEF"}
        state.halts["A"].append({"IssueSymbol": "A", "ReasonCode": "T1"})  # a v1 news halt from the RSS
        state.haltbook.stream_status({"S": "A", "sc": "H", "rc": "T1", "t": "2026-09-24T14:00:00Z", "z": "C"}, "r")  # the same halt, streamed
        state.haltbook.stream_status({"S": "B", "sc": "2", "rc": "P", "t": "2026-09-24T14:00:00Z", "z": "A"}, "r")  # a news halt only the stream saw
        state.haltbook.stream_status({"S": "C", "sc": "P", "rc": "LUDP", "t": "2026-09-24T14:30:00Z", "z": "C"}, "r")  # a volatility pause
        state.ca.observe(ca_event(ulid(1), "reverse_split", id="rs", symbol="D", ex_date="2026-09-28"))
        state.iv.first["E"] = {"at": "2026-09-24T13:50:00+00:00", "iv": 0.5, "expiry": "2026-10-02"}
        state.iv.last["E"] = {"at": "2026-09-24T14:59:50+00:00", "iv": 0.7, "expiry": "2026-10-02"}
        state.short_volume = {"F": {"ratio": 0.9, "total": 500_000, "short": 450_000, "date": "20260923"}}
        state.screener = {"A": {"volume_rank": 3}}
        return state

    def test_v1_board_ignores_v2_sources_and_v2_adds_only_new_evidence(self):
        state = self.state()
        self.assertEqual(M.build_board(state, self.at), ([M.score("A", state.features["A"], None, 0, [], state.halts["A"], None)], ["A"]))
        board, incentive = M.build_board_v2(state, self.at)
        rows = {r["symbol"]: r for r in board}
        self.assertEqual(sorted(rows), ["A", "B"])  # C 1.0, D 0.5, E 1.0 and F 0.5 stay below the threshold of 2
        self.assertEqual((rows["A"]["parts"], rows["A"]["score"], rows["A"]["score_v1"]), ({"news_halt": 2.0}, 2.0, 2.0))  # never counted twice
        self.assertEqual((rows["B"]["parts"], rows["B"]["score_v1"]), ({"stream_news_halt": 2.0}, 0))
        self.assertEqual(rows["A"]["context"]["screener"], {"volume_rank": 3})
        self.assertEqual(incentive, ["A", "B", "D", "E"])  # C is price-triggered and F volume-derived
        parts = {s: M.v2_components(state, s, M.score(s, state.features[s], None, 0, [], [], None), self.at, state.ca.by_symbol(state.today))[0]
                 for s in "CDEF"}   # (parts, context, superseded v1 parts)
        self.assertEqual(parts, {"C": {"stream_volatility_halt": 1.0}, "D": {"corporate_action": 0.5}, "E": {"iv_runup": 1.0},
                                 "F": {"short_volume_high": 0.5}})

    def test_the_rss_volatility_pause_is_not_counted_again_from_the_stream(self):
        state = self.state()
        state.halts["C"].append({"IssueSymbol": "C", "ReasonCode": "LUDP"})
        rows = M.score_candidates(state, self.at)
        self.assertEqual(M.v2_components(state, "C", rows["C"], self.at, {})[0], {})

    def test_v1_components_and_weights_are_unchanged_in_v2(self):
        self.assertFalse(set(M.V2_WEIGHTS) & {"relvol", "news", "mna_filing", "material_8k", "dilution_filing", "news_halt", "volatility_halt",
                                               "short_dated_calls", "large_option_prints"})
        self.assertEqual(set(M.V2_WEIGHTS), set(M.V2_RULES))
        self.assertEqual(M.NON_PRICE_PARTS_V2 - M.NON_PRICE_PARTS, {"stream_news_halt", "corporate_action", "iv_runup"})

    def test_payloads_carry_their_board_version(self):
        v1, v2 = M.board_payloads(self.at, [], ["A"], [], ["A", "B"], {"code_sha256": "x"})
        self.assertEqual((v1["board_version"], v2["board_version"], M.BOARD_VERSION, M.BOARD_V2_VERSION), (1, 2, 1, 2))
        self.assertNotIn("weights_v2", v1)
        self.assertEqual((v2["weights_v2"], v1["incentive_symbols"], v1["monitor"]), (M.V2_WEIGHTS, ["A"], {"code_sha256": "x"}))


class Market:
    """A synthetic response router for whole-pipeline runs (local integration: urlopen is replaced, nothing leaves the host)."""

    def __init__(self, now=None, remaining="9000"):
        self.now = now or datetime.now(timezone.utc)
        self.today = self.now.astimezone(M.ET).date()
        self.expiry = (self.today + M.timedelta(days=8)).strftime("%y%m%d")
        self.remaining, self.opened, self.on_request = remaining, [], None
        self.halts = HALTS.replace(b"PMAX", b"AAA").replace(b"09/24/2026", self.today.strftime("%m/%d/%Y").encode()).replace(b"10:08:56.356", b"00:00:01.000")
        self.split = ca_event(ulid(1_790_000_000_001), "reverse_split", id="r1", symbol="BBB", ex_date=self.today.isoformat())
        self.bar = f"{self.today.isoformat()}T13:30:00Z"

    def snap(self, p):
        return {"latestTrade": {"p": p, "t": self.now.isoformat()}, "latestQuote": {"bp": p - 0.01, "ap": p + 0.01},
                "dailyBar": {"t": self.bar, "c": p, "v": 1000}, "prevDailyBar": {"c": 10.0}, "minuteBar": {"v": 5, "t": self.bar}}

    def route(self, url):
        if "/v2/assets" in url:
            return [{"symbol": "AAA", "name": "Aaa Inc", "tradable": True}, {"symbol": "BBB", "name": "Bbb Corp", "tradable": True}]
        if "company_tickers.json" in url:
            return {"0": {"cik_str": 1490906, "ticker": "AAA", "title": "Example Holdings"}}
        if "/v2/stocks/bars" in url:
            return {"bars": {"AAA": [{"v": 1000}] * 20, "BBB": [{"v": 1000}] * 20}, "next_page_token": None}
        if "/v2/stocks/snapshots" in url:
            return {"AAA": self.snap(11.0), "BBB": self.snap(10.0)}
        if "browse-edgar" in url:
            return EDGAR
        if "nasdaqtrader.com" in url:
            return self.halts
        if "most-actives" in url:
            return {"most_actives": [{"symbol": "AAA", "volume": 5, "trade_count": 2}], "last_updated": "x"}
        if "/movers" in url:
            return {"gainers": [{"symbol": "AAA", "percent_change": 10.0, "change": 1.0, "price": 11.0}], "losers": [], "market_type": "stocks"}
        if "/v1beta1/options/snapshots/AAA" in url:
            return {"snapshots": {f"AAA{self.expiry}C00011000": opt(0.5, bar_t=self.bar), f"AAA{self.expiry}P00011000": opt(0.7, bar_t=self.bar)},
                    "next_page_token": None}
        if "/v2/options/contracts" in url:
            return {"option_contracts": [{"symbol": f"AAA{self.expiry}C00011000", "type": "call", "open_interest": "12"}], "next_page_token": None}
        if url.startswith("https://cdn.finra.org/"):
            return FINRA.replace(b"20260923", url[-12:-4].encode())
        if url.startswith(M.CA_EVENTS):
            return [f"data: {json.dumps([self.split])}\n", "\n"]
        raise AssertionError(f"unexpected request {url}")

    def urlopen(self, request, timeout):
        self.opened.append(request.full_url)
        if self.on_request:
            self.on_request(request.full_url)
        body = self.route(request.full_url)
        if isinstance(body, list) and body and isinstance(body[0], str):
            return Response(lines=body)
        headers = {"X-Ratelimit-Limit": "10000", "X-Ratelimit-Remaining": self.remaining} if "alpaca.markets" in request.full_url else {}
        return Response(body=body if isinstance(body, bytes) else json.dumps(body).encode(), headers=headers)

    def run(self, argv, tmp: Path, *patches, session_open=True):
        """M.main(argv) with this router, fake credentials, the chain session clock fixed and no version 1 monitor on the
        host (the test host's own processes never decide a result); returns the exit code."""
        with contextlib.ExitStack() as stack:
            for patch in (mock.patch.object(M.urllib.request, "urlopen", self.urlopen), mock.patch.object(M, "credentials", lambda path: ("key", "secret")),
                          mock.patch.object(M, "sec_identity", lambda: "Example Research admin@example.com"),
                          mock.patch.object(M, "chain_session_open", lambda at: session_open),
                          mock.patch.object(M, "live_v1_monitors", lambda proc=None: []), *patches):
                stack.enter_context(patch)
            return M.main([*argv, "--env-file", str(tmp / "absent.env"), "--lease-dir", str(tmp / "leases")])


def day_files(out: Path) -> dict:
    """{name: parsed content} of the newest day directory: .jsonl as lists of records, .json as objects."""
    day = sorted(out.glob("[0-9]" * 8))[-1]
    found = {}
    for path in day.iterdir():
        if path.suffix == ".jsonl":
            found[path.name] = [json.loads(line) for line in path.read_text().splitlines()]
        elif path.suffix == ".json":
            found[path.name] = json.loads(path.read_text())
    return found


class FakeStreams:
    """Stand-ins for the websockets and msgpack modules: every connect is recorded and its socket stays silent."""

    def __init__(self):
        self.connects = []
        streams = self

        class WS:
            async def send(self, data):
                return None

            async def recv(self):
                await asyncio.sleep(3600)

        class Connect:
            def __init__(self, url, **kwargs):
                streams.connects.append(url)

            async def __aenter__(self):
                return WS()

            async def __aexit__(self, *exc):
                return False
        self.modules = {"websockets": types.SimpleNamespace(connect=Connect), "msgpack": types.SimpleNamespace(packb=lambda x: b"x", unpackb=None)}

    def patch(self):
        return mock.patch.dict(sys.modules, self.modules)


class OnceSweep(unittest.TestCase):
    """The whole `once` pipeline against synthetic responses (local integration: urlopen is replaced, nothing leaves the host)."""

    def sweep(self, *extra, patches=(), prepare=None, market=None, session_open=True):
        market = market or Market()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out = tmp / "out"
            if prepare:
                prepare(out, market)
            rc = market.run(["once", "--standalone", "--out", str(out), "--option-oi", *extra], tmp, *patches, session_open=session_open)
            files = day_files(out) if list(out.glob("[0-9]" * 8)) else {}
            modes = {p.name: p.stat().st_mode & 0o777 for p in out.rglob("*") if p.is_file()}
        return rc, files, modes, market

    def test_one_sweep_writes_both_boards_inside_the_budget(self):
        rc, files, modes, market = self.sweep()
        self.assertEqual(rc, 0)
        v1, v2, monitor = files["board.json"], files["board-v2.json"], files["monitor.jsonl"]
        events = [m.get("event") for m in monitor]
        self.assertEqual(events, ["start", "budget", "restored", "ca_context", "sweep", "stop"])
        budget, sweep = monitor[1], monitor[4]
        self.assertEqual((budget["refusals"], budget["per_sweep"]["snapshots"], budget["data_cap_per_min"]), ([], 1, 500.0))
        self.assertEqual([k for k in sweep if k.endswith("_error")], [])
        self.assertEqual(sweep["source_calls"], {"snapshots": 1, "edgar": 7, "nasdaq_halts": 1, "screener": 3, "finra": 1, "option_chains": 1,
                                                 "option_contracts": 1, **({"adv_bars": 1} if "adv_bars" in sweep["source_calls"] else {})})
        self.assertEqual((sweep["budget_refused"], sweep["ratelimit"]["data.alpaca.markets"]["remaining"]), ({}, "9000"))
        self.assertEqual((v1["board_version"], v2["board_version"], v1["monitor"]["code_sha256"], v2["monitor"]["code_sha256"]),
                         (1, 2, hashlib.sha256(Path(M.__file__).read_bytes()).hexdigest(), v1["monitor"]["code_sha256"]))
        self.assertEqual(([r["symbol"] for r in v1["board"]], v1["board"][0]["parts"]["news_halt"], v1["board"][0]["parts"]["material_8k"]), (["AAA"], 2.0, 1.0))
        aaa = v2["board"][0]
        self.assertEqual((aaa["symbol"], aaa["score_v1"], aaa["context"]["screener"]["volume_rank"], aaa["context"]["options"]["call_oi"]), ("AAA", v1["board"][0]["score"], 1, 12))
        self.assertEqual((aaa["context"]["halt"]["state"], aaa["context"]["short_volume"]["ratio"], aaa["parts"]["short_volume_high"]), ("halted", 0.85, 0.5))
        self.assertEqual(aaa["score"], round(aaa["score_v1"] + 0.5, 3))  # v1 parts unchanged plus the one v2 part
        self.assertEqual({k: v for k, v in aaa.items() if k not in ("score", "score_v1", "parts", "context")},
                         {k: v for k, v in v1["board"][0].items() if k not in ("score", "parts")})   # the same v1 row
        self.assertIn("BBB", v2["incentive_symbols"])  # the corporate-action context replay surfaced its reverse split
        self.assertNotIn("BBB", v1["incentive_symbols"])
        self.assertEqual(set(modes.values()), {0o600})
        self.assertTrue(all(u.startswith(("https://data.alpaca.markets/", "https://paper-api.alpaca.markets/", "https://www.sec.gov/",
                                          "https://www.nasdaqtrader.com/", "https://cdn.finra.org/", M.CA_EVENTS)) for u in market.opened))
        self.assertTrue(any("region=us" in u for u in market.opened if u.startswith(M.CA_EVENTS)))

    def test_no_chain_is_sampled_outside_the_option_session(self):
        rc, files, _, _ = self.sweep(session_open=False)
        sweep = next(m for m in files["monitor.jsonl"] if m.get("event") == "sweep")
        self.assertEqual(rc, 0)
        self.assertNotIn("option_chains", sweep["source_calls"])
        self.assertNotIn("option_contracts", sweep["source_calls"])
        self.assertNotIn("options-iv.jsonl", files)

    def test_optional_data_sources_pause_below_the_rate_limit_floor(self):
        rc, files, _, _ = self.sweep(patches=(mock.patch.object(M.Http, "data_remaining", lambda self: M.RATELIMIT_FLOOR - 500),))
        sweep = next(m for m in files["monitor.jsonl"] if m.get("event") == "sweep")
        self.assertEqual((rc, sweep["ratelimit_floor"]), (0, 3000))
        self.assertFalse({"screener", "option_chains", "option_contracts"} & set(sweep["source_calls"]))
        self.assertEqual(sweep["source_calls"]["snapshots"], 1)   # the required sources still run

    def test_a_board_v2_failure_never_stops_board_v1(self):
        def broken(*a, **k):
            raise TypeError("unhashable type: 'list'")
        rc, files, _, _ = self.sweep(patches=(mock.patch.object(M, "build_board_v2", broken),))
        sweep = next(m for m in files["monitor.jsonl"] if m.get("event") == "sweep")
        self.assertEqual(rc, 0)
        self.assertEqual(files["board.json"]["board"][0]["symbol"], "AAA")
        self.assertNotIn("board-v2.json", files)
        self.assertEqual(sweep["board_v2_error"], "TypeError: unhashable type: 'list'")

    def test_an_old_archive_resumes_from_its_last_id_and_an_empty_one_from_the_retained_history(self):
        captured = []
        real = M.EventStream

        class Capture(real):
            def __init__(self, *a, **k):
                captured.append((a[3], k.get("last_id")))
                super().__init__(*a, **k)
        old = ulid(int((datetime.now(timezone.utc) - M.timedelta(days=30)).timestamp() * 1000))

        def archive(out, market):
            folder = out / (market.today - M.timedelta(days=30)).strftime("%Y%m%d")
            folder.mkdir(parents=True)
            (folder / "corporate-actions.jsonl").write_text(json.dumps({"event_id": old}) + "\n")
        _, files, _, _ = self.sweep(patches=(mock.patch.object(M, "EventStream", Capture),), prepare=archive)
        self.assertEqual(captured[-1][1], old)   # a 30-day-old resume id is kept, not dropped
        self.assertNotIn("ca_resume_gap", [m.get("event") for m in files["monitor.jsonl"]])
        self.sweep(patches=(mock.patch.object(M, "EventStream", Capture),))
        self.assertEqual((captured[-1][0], captured[-1][1]), (datetime(2020, 1, 1, tzinfo=timezone.utc), None))

    def test_this_monitor_refuses_to_run_beside_the_frozen_v1_bridge(self):
        here = Path(M.__file__).resolve().parent
        pinned = {**M.FROZEN_V1, "board_scan.py": hashlib.sha256((here / "board_scan.py").read_bytes()).hexdigest()}
        called = []
        rc, files, _, market = self.sweep(patches=(mock.patch.dict(M.FROZEN_V1, pinned),
                                                   mock.patch.object(M, "credentials", lambda path: called.append("credentials") or ("k", "s")),
                                                   mock.patch.object(M, "sec_identity", lambda: called.append("sec") or "x")))
        self.assertEqual((rc, market.opened, called), (2, [], []))   # nothing read, nothing requested
        self.assertEqual(files["monitor.jsonl"][-1], {**files["monitor.jsonl"][-1], "event": "stop", "refused": ["beside_frozen_v1_bridge"]})


class RestoreV2(unittest.TestCase):
    def test_halts_bands_and_implied_volatility_are_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prev, day = root / "20260923", root / "20260924"
            prev.mkdir()
            day.mkdir()
            (prev / "options-iv.jsonl").write_text(json.dumps({"symbol": "E", "received_at": "2026-09-23T19:55:00+00:00", "atm_iv": 0.6, "expiry": "2026-10-02"}) + "\n")
            (day / "status.jsonl").write_text(json.dumps({"T": "s", "S": "B", "sc": "H", "rc": "T1", "t": "2026-09-24T14:00:00Z", "z": "C", "received_at": "r"}) + "\ntorn")
            (day / "halts.jsonl").write_text(json.dumps({"IssueSymbol": "Q", "HaltDate": "09/24/2026", "HaltTime": "10:00:00", "ReasonCode": "LUDP", "received_at": "r"}) + "\n"
                                             + json.dumps({"IssueSymbol": "OLD", "HaltDate": "09/23/2026", "HaltTime": "10:00:00", "ReasonCode": "T1"}) + "\n")
            (day / "luld.jsonl").write_text(json.dumps({"T": "l", "S": "B", "u": 11.0, "d": 9.0, "t": "x", "z": "C", "received_at": "r"}) + "\n")
            (day / "options-iv.jsonl").write_text(json.dumps({"symbol": "E", "received_at": "2026-09-24T13:50:00+00:00", "atm_iv": 0.5, "expiry": "2026-10-02"}) + "\n")
            (day / "options-oi.jsonl").write_text(json.dumps({"symbol": "E", "received_at": "r", "call_oi": 5, "put_oi": 1}) + "\n")
            state = M.State()
            state.today = date(2026, 9, 24)
            counts = M.restore_v2(state, root, day)
        self.assertEqual(counts, {"status": 1, "status_unreadable": 1, "rss_events": 1, "luld": 1, "options_iv_previous": 1, "options_iv": 1, "options_oi": 1})
        now = datetime(2026, 9, 24, 15, tzinfo=timezone.utc)
        self.assertEqual((state.haltbook.stream_category("B"), state.haltbook.state("Q", now)["state"], state.haltbook.band("B")["u"]), ("news", "paused", 11.0))
        fresh = datetime(2026, 9, 24, 13, 50, 20, tzinfo=timezone.utc)   # 20 s after the restored sample
        self.assertEqual((state.iv.change("E", fresh)["baseline"], state.oi["E"]["call_oi"]), ("previous_session", 5))
        self.assertIsNone(state.iv.change("E", now))   # the restored latest sample is over an hour old: no change until the next one
        self.assertNotIn("OLD", state.haltbook.symbols())


# ---------------------------------------------------------------- review fixes (synthetic fixtures; no network)

class Coexistence(unittest.TestCase):
    """Version 2 beside the running version 1 monitor: a follower holds no news or OPRA connection and makes no EDGAR or
    Nasdaq RSS request; it reads those inputs from version 1's files (local integration against synthetic responses)."""

    def v1_files(self, root: Path, market) -> Path:
        day = root / market.today.strftime("%Y%m%d")
        day.mkdir(parents=True)
        received = market.now.isoformat()
        rows = {"news": [{"id": 7, "received_at": received, "symbols": ["AAA"], "headline": "h"}],
                "halts": [{"IssueSymbol": "AAA", "HaltDate": market.today.strftime("%m/%d/%Y"), "HaltTime": "00:00:01.000", "ReasonCode": "T1",
                           "received_at": received}],
                "edgar": [{"accession": "a1", "cik": 1490906, "form": "8-K", "role": "Filer", "items": ["2.02"], "tickers": ["AAA"], "received_at": received}],
                "options-minute": [{"drained_at": "x", "root": "AAA", "cells": {"C|0-7": [100, 300000.0, 5]}}],
                "options-large": [{"root": "AAA"}] * 3,
                "monitor": [{"event": "sweep", "at": received}]}
        for name, items in rows.items():
            (day / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in items))
        return day

    def test_a_follower_holds_no_news_or_opra_connection_and_polls_neither_edgar_nor_the_rss(self):
        market, streams = Market(), FakeStreams()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v1, out = tmp / "v1", tmp / "out"
            v1_day = self.v1_files(v1, market)
            with streams.patch():
                rc = market.run(["run", "--follow-v1", str(v1), "--out", str(out), "--until-et", "00:00", "--no-corporate-actions"], tmp)
            files = day_files(out)
            v1_listing = sorted(p.name for p in v1_day.iterdir())
        self.assertEqual(rc, 0)
        self.assertEqual(streams.connects, [])   # no news, OPRA or IEX connection
        self.assertEqual([u for u in market.opened if "sec.gov" in u or "nasdaqtrader.com" in u], [])
        monitor = files["monitor.jsonl"]
        start, budget = monitor[0], next(m for m in monitor if m.get("event") == "budget")
        sweep = next(m for m in monitor if m.get("event") == "sweep")
        self.assertEqual((start["role"], start["from_v1_files"]), ("follower", ["opra_trades", "news", "edgar", "nasdaq_halts"]))
        self.assertEqual((budget["per_sweep"]["edgar"], budget["per_sweep"]["nasdaq_halts"], budget["once"]["sec_files"]), (0, 0, 0))
        self.assertEqual((budget["streams"]["news"]["connections"], budget["streams"]["opra"]["connections"], budget["nasdaq_per_min"]), (0, 0, 0.0))
        self.assertNotIn("board.json", files)   # version 1's board is version 1's own
        aaa = next(r for r in files["board-v2.json"]["board"] if r["symbol"] == "AAA")
        self.assertEqual({k: aaa["parts"][k] for k in ("news", "news_halt", "material_8k", "short_dated_calls", "large_option_prints")},
                         {"news": 1.0, "news_halt": 2.0, "material_8k": 1.0, "short_dated_calls": 1.5, "large_option_prints": 0.5})
        self.assertEqual(aaa["context"]["halt"]["source"], "rss")
        self.assertEqual((sweep["follow_v1_heartbeat"]["event"], sweep["follow_v1"]["news"], sweep["source_calls"].get("edgar")), ("sweep", 1, None))
        self.assertEqual(([k for k in sweep if k.endswith("_error")], sweep["budget_refused"]), ([], {}))   # not even a refused attempt
        self.assertEqual(v1_listing, ["edgar.jsonl", "halts.jsonl", "monitor.jsonl", "news.jsonl", "options-large.jsonl", "options-minute.jsonl"])

    def test_the_follower_applies_each_complete_line_once(self):
        state = M.State()
        state.today = date(2026, 9, 24)
        row = json.dumps({"root": "R", "cells": {"C|0-7": [10, 1000.0, 2]}})
        with tempfile.TemporaryDirectory() as tmp:
            day = Path(tmp) / "20260924"
            day.mkdir()
            minute = day / "options-minute.jsonl"
            minute.write_text(row + "\n" + row[:10])   # the second line is still being written
            follow = M.FollowV1(Path(tmp), state.today)
            follow.poll(state)
            follow.poll(state)
            self.assertEqual(state.options.day["R"]["C_volume"], 10)
            with minute.open("a") as f:
                f.write(row[10:] + "\n" + "not json\n")
            counts = follow.poll(state)
            follow.poll(state)
        self.assertEqual((state.options.day["R"]["C_volume"], counts["options_minutes"], counts["options-minute_unreadable"]), (20, 2, 1))
        self.assertEqual(M.FollowV1(Path(tmp), state.today).heartbeat(datetime.now(timezone.utc)), {"event": None, "age_s": None})

    def test_every_run_declares_its_role(self):
        base = ["run", "--env-file", "e", "--out", "o"]
        with mock.patch("sys.stderr", new=io.StringIO()):
            for argv in (base, base + ["--standalone", "--follow-v1", "d"], ["once", "--env-file", "e", "--out", "o"]):
                with self.assertRaises(SystemExit):
                    M.parser().parse_args(argv)
        self.assertTrue(M.parser().parse_args(base + ["--standalone"]).standalone)
        self.assertEqual(M.parser().parse_args(base + ["--follow-v1", "d"]).follow_v1, Path("d"))

    def test_a_follower_needs_an_existing_version_1_directory_other_than_its_own(self):
        market = Market()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rc = market.run(["run", "--follow-v1", str(tmp / "missing"), "--out", str(tmp / "out"), "--until-et", "00:00", "--no-corporate-actions"], tmp)
            refused = day_files(tmp / "out")["monitor.jsonl"][-1]["refused"]
            (tmp / "same").mkdir()
            rc2 = market.run(["run", "--follow-v1", str(tmp / "same"), "--out", str(tmp / "same"), "--until-et", "00:00", "--no-corporate-actions"], tmp)
            refused2 = day_files(tmp / "same")["monitor.jsonl"][-1]["refused"]
        self.assertEqual((rc, refused, rc2, refused2, market.opened), (2, ["follow_v1_directory_missing"], 2, ["follow_v1_is_this_out_directory"], []))

    def test_version_1_monitors_on_this_host_are_found_from_proc(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, deploy = Path(tmp) / "proc", Path(tmp) / "deploy"
            deploy.mkdir()
            (deploy / "monitor.py").write_text("# a version 1 copy\n")
            processes = {"4242": ["python3", "monitor.py", "run", "--env-file", "e", "--out", "o"],           # version 1 (relative path)
                         "4243": ["python3", str(deploy / "monitor.py"), "run", "--standalone", "--env-file", "e", "--out", "o"],
                         "4244": ["python3", str(deploy / "monitor.py"), "run", "--follow-v1", "v1", "--env-file", "e", "--out", "o"],
                         "4245": ["python3", str(deploy / "monitor.py"), "once", "--env-file", "e", "--out", "o"],
                         "4246": ["python3", "other.py", "run", "--env-file", "e", "--out", "o"], "self": ["x"]}
            for pid, argv in processes.items():
                (proc / pid).mkdir(parents=True)
                (proc / pid / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
                os.symlink(deploy, proc / pid / "cwd")
            self.assertEqual(M.live_v1_monitors(proc), [4242])
            frozen = hashlib.sha256((deploy / "monitor.py").read_bytes()).hexdigest()
            with mock.patch.dict(M.FROZEN_V1, {"monitor.py": frozen}):   # the frozen file, whatever its arguments
                self.assertEqual(M.live_v1_monitors(proc), [4242, 4243, 4244])
            self.assertEqual(M.live_v1_monitors(Path(tmp) / "absent"), [])

    def test_standalone_refuses_while_a_version_1_monitor_runs_here(self):
        market = Market()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "v1").mkdir()
            live = mock.patch.object(M, "live_v1_monitors", lambda proc=None: [4242])
            rc = market.run(["once", "--standalone", "--out", str(tmp / "out")], tmp, live)
            refused = day_files(tmp / "out")["monitor.jsonl"][-1]["refused"]
            opened = list(market.opened)
            rc2 = market.run(["once", "--follow-v1", str(tmp / "v1"), "--out", str(tmp / "out2"), "--no-corporate-actions"], tmp, live)
        self.assertEqual((rc, refused, opened), (2, ["v1_monitor_running_use_follow_v1"], []))
        self.assertEqual(rc2, 0)   # a follower runs beside it

    def test_the_lease_directory_does_not_depend_on_the_environment(self):
        found = set()
        for env in ({"XDG_RUNTIME_DIR": "/run/user/1000", "HOME": "/tmp/a"}, {"XDG_RUNTIME_DIR": "", "HOME": "/tmp/b"}):
            with mock.patch.dict(os.environ, env):
                found.add(M.default_lease_dir())
        self.assertEqual(found, {Path(pwd.getpwuid(os.getuid()).pw_dir) / ".cache" / "alpaca-stream-leases"})


class StreamBackoff(unittest.TestCase):
    def run_stream(self, batches, stop_after, **kwargs):
        connects, holder = [], {}

        class WS:
            def __init__(self, queue):
                self.queue = [json.dumps(b) for b in queue]

            async def send(self, data):
                return None

            async def recv(self):
                if self.queue:
                    return self.queue.pop(0)
                await asyncio.sleep(3600)

        class Connect:
            def __init__(self, url, **kw):
                connects.append(url)
                if len(connects) >= stop_after:
                    holder["stop"].set()
                self.ws = WS(batches[min(len(connects), len(batches)) - 1])

            async def __aenter__(self):
                return self.ws

            async def __aexit__(self, *exc):
                return False
        fakes = {"websockets": types.SimpleNamespace(connect=Connect), "msgpack": types.SimpleNamespace(packb=None, unpackb=None)}
        with tempfile.TemporaryDirectory() as tmp:
            sink, state = M.Sink(Path(tmp)), M.State()

            async def main():
                holder["stop"] = asyncio.Event()
                await M.stream("news", M.NEWS_WS, {"action": "subscribe", "news": ["*"]}, {}, lambda m: None, state, sink, holder["stop"], False,
                               backoff=lambda attempt: 0, **kwargs)
            with mock.patch.dict(sys.modules, fakes):
                asyncio.run(asyncio.wait_for(main(), 10))
            sink.close()
            return connects, records(tmp, "monitor")

    WELCOME, AUTHORIZED = [{"T": "success", "msg": "connected"}], [{"T": "success", "msg": "authenticated"}]
    LIMIT = [{"T": "error", "code": 406, "msg": "connection limit exceeded"}]

    def test_welcome_batches_before_a_406_never_reset_the_backoff(self):
        _, monitor = self.run_stream([[self.WELCOME, self.AUTHORIZED, self.LIMIT]], stop_after=4)
        self.assertEqual([m["attempt"] for m in monitor if m["event"] == "stream_down"], [1, 2, 3])

    def test_a_data_message_resets_the_backoff(self):
        data = [{"T": "n", "id": 1, "symbols": ["X"]}]
        _, monitor = self.run_stream([[self.WELCOME, self.LIMIT], [self.WELCOME, data, self.LIMIT], [self.WELCOME, self.LIMIT]], stop_after=4)
        self.assertEqual([m["attempt"] for m in monitor if m["event"] == "stream_down"], [1, 1, 2])

    def test_an_error_that_reconnecting_cannot_heal_stops_the_stream(self):
        connects, monitor = self.run_stream([[self.WELCOME, [{"T": "error", "code": 409, "msg": "insufficient subscription"}]]], stop_after=5)
        self.assertEqual((len(connects), [m["event"] for m in monitor]), (1, ["stream_connected", "stream_error", "stream_stopped"]))


class OptionSession(unittest.TestCase):
    et = staticmethod(lambda h, m, s=0: datetime(2026, 9, 24, h, m, s, tzinfo=M.ET))

    def test_the_option_session_is_0945_to_1600_et(self):
        self.assertEqual([M.chain_session_open(self.et(*t)) for t in ((9, 44, 59), (9, 45), (15, 59, 59), (16, 0), (19, 59))],
                         [False, True, True, False, False])

    def test_samples_outside_the_session_never_count(self):
        iv = M.IVTracker(max_age=60)
        iv.prev["X"] = {"at": "2026-09-23T19:55:00+00:00", "iv": 0.50, "expiry": "2026-10-16"}   # 15:55 ET yesterday
        iv.observe("X", self.et(9, 0), {"atm_iv": 0.80, "expiry": "2026-10-16"})   # pre-market: stale option quotes
        self.assertEqual((iv.last, iv.first, iv.runup("X", self.et(9, 0, 30))), ({}, {}, None))
        iv.observe("X", self.et(16, 30), {"atm_iv": 0.80, "expiry": "2026-10-16"})
        self.assertEqual(iv.last, {})
        iv.observe("X", self.et(10, 0), {"atm_iv": 0.62, "expiry": "2026-10-16"})
        self.assertEqual(iv.runup("X", self.et(10, 0, 30))["baseline"], "previous_session")

    def test_the_previous_session_baseline_is_its_last_sample_by_1600(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "20260923").mkdir()
            (root / "20260924").mkdir()
            rows = [{"symbol": "E", "received_at": "2026-09-23T19:55:00+00:00", "atm_iv": 0.5, "expiry": "2026-10-16"},   # 15:55 ET
                    {"symbol": "E", "received_at": "2026-09-23T23:59:00+00:00", "atm_iv": 0.8, "expiry": "2026-10-16"}]   # 19:59 ET
            (root / "20260923" / "options-iv.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            state = M.State()
            state.today = date(2026, 9, 24)
            counts = M.restore_v2(state, root, root / "20260924")
        self.assertEqual((state.iv.prev["E"]["iv"], counts["options_iv_previous"], counts["options_iv_previous_outside_session"]), (0.5, 1, 1))

    def test_the_first_value_today_is_the_baseline_only_for_its_own_expiry(self):
        iv = M.IVTracker(max_age=60)
        iv.observe("X", self.et(9, 50), {"atm_iv": 0.50, "expiry": "2026-10-02"})
        iv.observe("X", self.et(10, 30), {"atm_iv": 0.70, "expiry": "2026-10-09"})   # the target expiry moved
        self.assertIsNone(iv.runup("X", self.et(10, 30, 10)))   # +40% across two expiries is not a run-up
        self.assertEqual((iv.first["X"]["expiry"], iv.change("X", self.et(10, 30, 10))["baseline_age_s"]), ("2026-10-09", 10))
        iv.observe("X", self.et(11, 5), {"atm_iv": 0.85, "expiry": "2026-10-09"})
        self.assertEqual(iv.runup("X", self.et(11, 5, 10))["chg"], round(0.85 / 0.70 - 1, 4))
        iv.first["Y"] = {"at": M.iso(self.et(9, 50)), "iv": 0.5, "expiry": "2026-10-02"}   # e.g. a restored baseline of another expiry
        iv.last["Y"] = {"at": M.iso(self.et(11, 0)), "iv": 0.9, "expiry": "2026-10-09"}
        self.assertIsNone(iv.change("Y", self.et(11, 0, 10)))   # never compared across expiries

    def test_a_stale_latest_sample_no_longer_counts(self):
        iv = M.IVTracker(max_age=40)
        iv.observe("X", self.et(10, 0), {"atm_iv": 0.5, "expiry": "2026-10-02"})
        iv.observe("X", self.et(10, 40), {"atm_iv": 0.7, "expiry": "2026-10-02"})
        found = iv.runup("X", self.et(10, 40, 30))
        self.assertEqual((found["last_at"], found["baseline"]), (M.iso(self.et(10, 40)), "first_today"))
        self.assertIsNone(iv.change("X", self.et(10, 41)))   # the root left the sampled set a minute ago
        state = M.State()
        state.iv = iv
        self.assertEqual(("X" in M.v2_symbols(state, self.et(10, 40, 30), {}), "X" in M.v2_symbols(state, self.et(10, 41), {})), (True, False))


class ChainWindow(unittest.TestCase):
    today = date(2026, 9, 24)

    def args(self, *extra):
        return M.parser().parse_args(["run", "--standalone", "--env-file", "e", "--out", "o", *extra])

    def test_a_monthly_only_root_22_days_out_is_found(self):
        class FakeHttp:
            def alpaca_json(self, base, path, params):
                if params["expiration_date_gte"] <= "2026-10-16" <= params["expiration_date_lte"]:
                    return {"snapshots": {"MTH261016C00010000": opt(0.6), "MTH261016P00010000": opt(0.8)}, "next_page_token": None}
                return {"snapshots": {}, "next_page_token": None}
        state = M.State()
        state.today, state.features = self.today, {"MTH": {"p": 10.1}}
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            stats = M.poll_option_chains(FakeHttp(), state, sink, self.args(), ["MTH"])
            sink.close()
            (row,) = records(tmp, "options-iv")
        self.assertEqual((stats, state.no_options, row["expiry"], row["dte"], row["atm_iv"]), ({"roots": 1}, set(), "2026-10-16", 22, 0.7))
        for n in range(34):   # on any day the window holds the next standard monthly (third Friday) expiry
            day = date(2026, 1, 1) + M.timedelta(days=n * 11)
            first = date.fromisoformat(M.chain_params(None, day, self.args())["expiration_date_gte"])
            last = date.fromisoformat(M.chain_params(None, day, self.args())["expiration_date_lte"])
            self.assertTrue([d for d in (first + M.timedelta(days=i) for i in range((last - first).days + 1)) if d.weekday() == 4 and 15 <= d.day <= 21], day)

    def test_an_empty_in_band_chain_is_asked_again_without_the_band(self):
        class FakeHttp:
            def __init__(self):
                self.calls = []

            def alpaca_json(self, base, path, params):
                root = path.rsplit("/", 1)[1]
                self.calls.append((root, "strike_price_gte" in params))
                if root == "NONE" or "strike_price_gte" in params:
                    return {"snapshots": {}, "next_page_token": None}
                return {"snapshots": {f"{root}261002C00012500": opt(0.9), f"{root}261002P00012500": opt(1.1)}, "next_page_token": None}
        state, http = M.State(), FakeHttp()
        state.today, state.features = self.today, {"MOV": {"p": 20.0}, "NONE": {"p": 5.0}, "LATE": {"p": 7.0}}
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            polls = [M.poll_option_chains(http, state, sink, self.args("--option-retries", n), [root]) for root, n in (("MOV", "1"), ("MOV", "1"), ("NONE", "1"), ("LATE", "0"))]
            sink.close()
            rows = records(tmp, "options-iv")
        self.assertEqual(polls, [{"roots": 1, "unbanded_retry": 1}, {"roots": 1}, {"unbanded_retry": 1, "empty": 1}, {"retry_deferred": 1}])
        self.assertEqual(http.calls, [("MOV", True), ("MOV", False), ("MOV", False), ("NONE", True), ("NONE", False), ("LATE", True)])
        self.assertEqual((state.chain_unbanded, state.no_options), ({"MOV"}, {"NONE"}))   # LATE is asked again next sweep
        self.assertEqual([(r["symbol"], r["strike"], r["banded"]) for r in rows], [("MOV", 12.5, False), ("MOV", 12.5, False)])
        self.assertEqual(M.plan_budget(13_500, self.args())["per_sweep"]["option_chains"], 30)   # 25 roots and 5 retries a sweep

    def test_a_stalled_chain_endpoint_cannot_hold_the_sweep(self):
        release = threading.Event()

        class FakeHttp:
            def alpaca_json(self, base, path, params):
                if path.endswith("/SLOW"):
                    release.wait(5)
                return {"snapshots": {"FAST261002C00010000": opt(0.5)}, "next_page_token": None}
        state = M.State()
        state.today, state.features = self.today, {"FAST": {"p": 10.0}, "SLOW": {"p": 10.0}}
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            started = time.monotonic()
            stats = M.poll_option_chains(FakeHttp(), state, sink, self.args(), ["FAST", "SLOW"], deadline_s=0.3)
            elapsed = time.monotonic() - started
            release.set()
            sink.close()
        self.assertEqual(stats, {"roots": 1, "deadline": 1})
        self.assertLess(elapsed, 2.0)


class OpenInterest(unittest.TestCase):
    def test_open_interest_is_opt_in_and_pauses_near_the_trading_limit(self):
        base = ["run", "--standalone", "--env-file", "e", "--out", "o"]
        self.assertFalse(M.parser().parse_args(base).option_oi)
        args = M.parser().parse_args(base + ["--option-oi"])

        class FakeHttp:
            def __init__(self, left):
                self.left, self.calls = left, []

            def remaining(self, host):
                return self.left if host == M.TRADING_HOST else None

            def alpaca_json(self, base, path, params):
                self.calls.append(params["underlying_symbols"])
                return {"option_contracts": [], "next_page_token": None}
        state = M.State()
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            low, high = FakeHttp(M.TRADING_RATELIMIT_FLOOR - 1), FakeHttp(M.TRADING_RATELIMIT_FLOOR)
            self.assertEqual((M.poll_option_oi(low, state, sink, args, ["A", "B"]), low.calls), (0, []))
            self.assertEqual((M.poll_option_oi(high, state, sink, args, ["A", "B"]), high.calls), (2, ["A", "B"]))
            sink.close()
        http = M.Http({}, None)
        http.ratelimit[M.TRADING_HOST] = {"remaining": "42"}
        self.assertEqual((http.remaining(M.TRADING_HOST), http.data_remaining()), (42, None))


class FinraRetries(unittest.TestCase):
    now = datetime(2026, 9, 24, 17, 0, tzinfo=M.ET)   # before publication: the due file is the 23rd's

    def fake(self, failure):
        class FakeHttp:
            def __init__(self):
                self.urls, self.fail = [], True

            def get(self, url, kind, headers, timeout=20):
                self.urls.append(url.rsplit("/", 1)[1])
                if url.endswith("20260923.txt") and self.fail:
                    if isinstance(failure, bytes):
                        return failure
                    raise failure
                return FINRA.replace(b"20260923", url[-12:-4].encode())
        return FakeHttp()

    def test_every_failure_waits_an_hour_before_the_same_file_is_asked_again(self):
        failures = {"no_trailer": FINRA.replace(b"3\r\n", b""), "server_error": urllib.error.HTTPError("u", 503, "unavailable", {}, None),
                    "network_error": urllib.error.URLError("timed out"), "other_day": FINRA.replace(b"20260923", b"20260922")}
        for name, failure in failures.items():
            clock = [1000.0]
            tick = lambda: clock[0]
            http, state = self.fake(failure), M.State()
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                sink = M.Sink(Path(tmp))
                with self.assertRaises((ValueError, urllib.error.URLError)):
                    M.poll_finra(http, state, sink, self.now, clock=tick)
                self.assertEqual(M.poll_finra(http, state, sink, self.now, clock=tick), "20260922")   # the previous weekday meanwhile
                self.assertIsNone(M.poll_finra(http, state, sink, self.now, clock=tick))
                clock[0] += M.FINRA_RETRY_SECONDS
                http.fail = False
                self.assertEqual(M.poll_finra(http, state, sink, self.now, clock=tick), "20260923")
                self.assertEqual(http.urls, ["CNMSshvol20260923.txt", "CNMSshvol20260922.txt", "CNMSshvol20260923.txt"])
                self.assertTrue((Path(tmp) / "finra" / "CNMSshvol20260923.txt").exists())

    def test_a_stored_file_is_checked_once_more_after_the_next_publication(self):
        class FakeHttp:
            def __init__(self):
                self.urls = []

            def get(self, url, kind, headers, timeout=20):
                self.urls.append(url.rsplit("/", 1)[1])
                if url.endswith("20260923.txt"):
                    return FINRA.replace(b"850000.5", b"860000.5")   # FINRA updated the file on a later day
                return FINRA.replace(b"20260923", url[-12:-4].encode())
        http, state = FakeHttp(), M.State()
        now = datetime(2026, 9, 24, 18, 30, tzinfo=M.ET)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "finra").mkdir(mode=0o700)
            (root / "finra" / "CNMSshvol20260923.txt").write_bytes(FINRA)
            (root / "finra" / "CNMSshvol20260923.json").write_text(json.dumps({"date": "20260923", "received_at": "2026-09-23T22:10:00+00:00",
                                                                               "sha256": hashlib.sha256(FINRA).hexdigest(), "rows": 3}))
            sink = M.Sink(root)
            self.assertEqual(M.poll_finra(http, state, sink, now), "20260924")   # a new file first
            self.assertEqual(M.poll_finra(http, state, sink, now), "updated:20260923")
            self.assertIsNone(M.poll_finra(http, state, sink, now))   # once only
            manifest = json.loads((root / "finra" / "CNMSshvol20260923.json").read_text())
            (kept,) = (root / "finra" / "superseded").glob("CNMSshvol20260923.*.txt")
            self.assertEqual((manifest["recheck"], manifest["supersedes"], kept.read_bytes()), ("updated", hashlib.sha256(FINRA).hexdigest(), FINRA))
            self.assertEqual(M.load_short_volume(root, date(2026, 9, 23))[1]["AAA"]["short"], 860000.5)
        self.assertEqual(http.urls, ["CNMSshvol20260924.txt", "CNMSshvol20260923.txt"])


class HaltComponents(unittest.TestCase):
    at = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)

    def state(self):
        state = M.State()
        state.today = date(2026, 9, 24)
        state.features = {s: {"s": s, "chg": 0.02, "p": 10.0, "v": None, "spr_bps": 10.0} for s in ("M1", "P1")}
        return state

    def test_any_rss_halt_today_blocks_the_stream_volatility_part(self):
        state = self.state()
        state.halts["M1"].append({"IssueSymbol": "M1", "ReasonCode": "M"})   # an RSS code version 1 does not score
        state.haltbook.stream_status({"S": "M1", "sc": "2", "rc": "M", "t": "2026-09-24T14:00:00Z", "z": "A"}, "r")
        row = M.score_candidates(state, self.at)["M1"]
        self.assertEqual((row["parts"], M.v2_components(state, "M1", row, self.at, {})[0]), ({}, {}))

    def test_a_stream_news_halt_replaces_the_v1_volatility_halt(self):
        state = self.state()
        state.halts["P1"].append({"IssueSymbol": "P1", "ReasonCode": "LUDP"})   # the RSS lists a pause at 10:00
        state.haltbook.stream_status({"S": "P1", "sc": "H", "rc": "T1", "t": "2026-09-24T14:30:00Z", "z": "C"}, "r")   # the stream's news halt at 10:30
        board, incentive = M.build_board_v2(state, self.at)
        (p1,) = [r for r in board if r["symbol"] == "P1"]
        self.assertEqual((p1["parts"], p1["score"], p1["score_v1"], p1["context"]["superseded_v1_parts"]),
                         ({"stream_news_halt": 2.0}, 2.0, 1.0, ["volatility_halt"]))
        self.assertIn("P1", incentive)

    def test_an_ongoing_halt_from_an_earlier_day_enters_the_merged_state_only(self):
        rows = HALTS.replace(b"<ndaq:HaltDate>09/24/2026", b"<ndaq:HaltDate>09/22/2026")   # halted two days ago, not resumed

        class FakeHttp:
            def get(self, url, kind, headers, timeout=20):
                return rows
        state = M.State()
        state.today = date(2026, 9, 24)
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            self.assertEqual(M.poll_halts(FakeHttp(), state, sink), 0)
            sink.close()
            self.assertFalse(list(Path(tmp).glob("*/halts.jsonl")))   # version 1's halt rows stay today's
        self.assertEqual((state.haltbook.state("PMAX", self.at)["state"], "PMAX" in state.halts), ("halted", False))
        resumed = M.parse_halts(rows.replace(b"<ndaq:ResumptionDate>09/24/2026", b"<ndaq:ResumptionDate>09/22/2026").replace(
            b"<ndaq:ResumptionTradeTime />", b"<ndaq:ResumptionTradeTime>15:00:00</ndaq:ResumptionTradeTime>"), "r")[0]
        fresh = M.State()
        self.assertEqual((fresh.haltbook.rss_ongoing(resumed, state.today), state.haltbook.rss_ongoing(resumed, state.today)), (False, True))

    def test_a_resumption_moved_later_replaces_the_earlier_one(self):
        book = M.HaltBook()
        row = {"IssueSymbol": "X", "HaltDate": "09/24/2026", "HaltTime": "11:00:00", "ReasonCode": "T1", "ResumptionDate": "09/24/2026",
               "ResumptionQuoteTime": "11:55:00", "ResumptionTradeTime": "12:00:00"}
        extended = {**row, "ResumptionQuoteTime": "12:25:00", "ResumptionTradeTime": "12:30:00"}
        self.assertEqual((book.rss_row(row), book.rss_row(extended), book.rss_row(extended)), (3, 2, 0))
        at = lambda *t: datetime(2026, 9, 24, *t, tzinfo=M.ET)
        self.assertEqual([book.state("X", at(*t))["state"] for t in ((12, 10), (12, 25, 6), (12, 30, 6))], ["halted", "quotation_only", "trading"])
        self.assertEqual(len(book.events["X"]), 3)


class CorporateActionFixes(unittest.TestCase):
    today = date(2026, 9, 24)

    def test_an_action_inserted_today_stays_fresh_after_its_updates(self):
        cas, e = M.CorporateActions(), lambda n: ulid(1_790_000_000_000 + n)
        cas.observe(ca_event(e(1), "cash_merger", id="cm", acquiree_symbol="TGT", acquirer_symbol="BUY", effective_date="2026-12-20",
                             at="2026-09-24T13:00:00Z"))
        cas.observe(ca_event(e(2), "cash_merger", action="update", id="cm", acquiree_symbol="TGT", acquirer_symbol="BUY", rate="42.5",
                             effective_date="2026-12-20", at="2026-09-24T14:00:00Z"))
        (item,) = cas.by_symbol(self.today)["TGT"]
        self.assertEqual((item["in_window"], item["action"], item["inserted_at"], item["days"]), (True, "update", "2026-09-24T13:00:00Z", 87))
        self.assertNotIn("TGT", cas.by_symbol(date(2026, 9, 25)))   # fresh on its insert day only, and 86 days out is beyond the context

    def test_non_us_events_are_archived_but_never_surfaced(self):
        us, foreign = ulid(1_790_000_000_001), ulid(1_790_000_000_002)
        events = [ca_event(us, "reverse_split", id="u1", symbol="RSX", ex_date="2026-09-25"),
                  {**ca_event(foreign, "reverse_split", id="f1", symbol="SAME", ex_date="2026-09-25"), "region": "non_us"}]
        with tempfile.TemporaryDirectory() as tmp:
            sink, state = M.Sink(Path(tmp)), M.State()
            stream = M.EventStream({}, sink, state, datetime(2026, 9, 24, 4, tzinfo=timezone.utc))
            stream.consume([f"data: {json.dumps(events)}\n", "\n"], archive=True)
            sink.close()
            archived = [r["event_id"] for r in records(tmp, "corporate-actions")]
        self.assertEqual((archived, stream.counts["surfaced"], set(state.ca.by_symbol(self.today))), ([us, foreign], 1, {"RSX"}))

    def test_a_malformed_symbol_never_breaks_the_context(self):
        cas = M.CorporateActions()
        self.assertTrue(cas.observe(ca_event(ulid(5), "forward_split", id="bad", symbol=["LIST"], ex_date="2026-09-25")))
        self.assertEqual(cas.by_symbol(self.today), {})

    def test_a_resume_records_a_gap_only_when_the_resume_id_is_not_redelivered(self):
        old, kept, later = ulid(1_787_000_000_000), ulid(1_787_000_000_001), ulid(1_790_000_000_000)
        lines = lambda eid: [f"id: {eid}\n", f"data: {json.dumps([ca_event(eid, 'cash_dividend', id=eid)])}\n", "\n"]
        with tempfile.TemporaryDirectory() as tmp:
            sink, state = M.Sink(Path(tmp)), M.State()
            responses, resumes = [Response(lines(old) + lines(kept)), Response(lines(later))], []
            stream = M.EventStream({}, sink, state, datetime(2026, 9, 24, 4, tzinfo=timezone.utc), last_id=old, backoff=lambda a: 0, connects_per_min=10)

            def opener(request, timeout):
                resumes.append(request.get_header("Last-event-id"))
                if not responses:
                    stream.stop_event.set()
                    raise OSError("synthetic end")
                return responses.pop(0)
            stream.opener = opener
            stream.run()
            sink.close()
            gaps = [r for r in records(tmp, "monitor") if r["event"] == "ca_resume_gap"]
            archived = [r["event_id"] for r in records(tmp, "corporate-actions")]
        self.assertEqual(resumes, [old, kept, later])   # a month-old resume id is used as it is
        self.assertEqual(archived, [kept, later])
        self.assertEqual([(g["resume_id"], g["first_id"]) for g in gaps], [(kept, later)])   # only the second resume missed its id

    def test_at_most_two_connects_a_minute_the_context_replay_included(self):
        clock = [0.0]
        stream = M.EventStream({}, None, M.State(), datetime(2026, 9, 24, tzinfo=timezone.utc), clock=lambda: clock[0])
        allowed = []
        for t in (0.0, 1.0, 10.0, 59.9, 60.0, 61.5, 62.0):
            clock[0] = t
            allowed.append(stream.may_connect())
        self.assertEqual(allowed, [True, True, False, False, True, True, False])
        opened = []
        stream.opener = lambda request, timeout: opened.append(request) or Response([])
        stream.context = (datetime(2026, 8, 25, tzinfo=timezone.utc), datetime(2026, 9, 24, tzinfo=timezone.utc))
        stream.stop_event.set()   # the budget is spent: the replay waits (and here stops) instead of connecting
        stream.run_context()
        self.assertEqual((opened, stream.counts["connect_budget_waits"]), ([], 1))

    def test_the_context_replay_ends_at_its_deadline(self):
        clock, timeouts = [0.0], []

        def tick():
            clock[0] += 1.0
            return clock[0]
        with tempfile.TemporaryDirectory() as tmp:
            sink = M.Sink(Path(tmp))
            stream = M.EventStream({}, sink, M.State(), datetime(2026, 9, 24, tzinfo=timezone.utc), clock=tick,
                                   opener=lambda request, timeout: timeouts.append(timeout) or Response([": keep-alive\n"] * 1000))
            with self.assertRaises(TimeoutError):
                stream.replay_context(datetime(2026, 8, 25, tzinfo=timezone.utc), datetime(2026, 9, 24, 14, tzinfo=timezone.utc), deadline_s=30)
            stream.context = (datetime(2026, 8, 25, tzinfo=timezone.utc), datetime(2026, 9, 24, 14, tzinfo=timezone.utc))
            stream.run_context()
            sink.close()
            (error,) = [r for r in records(tmp, "monitor") if r["event"] == "ca_context_error"]
        self.assertEqual((timeouts, error["error"]), ([M.CA_CONTEXT_READ_TIMEOUT] * 2, "TimeoutError: ca_context_deadline"))

    def test_where_an_empty_archive_starts(self):
        today = date(2026, 9, 24)
        self.assertEqual(M.ca_archive_start("retained", today), datetime(2020, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(M.ca_archive_start("today", today), datetime(2026, 9, 24, 4, tzinfo=timezone.utc))
        self.assertEqual(M.ca_archive_start("2026-09-01T00:00:00Z", today), datetime(2026, 9, 1, tzinfo=timezone.utc))
        with mock.patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit):
            M.parser().parse_args(["run", "--standalone", "--env-file", "e", "--out", "o", "--ca-archive-since", "yesterday"])


class DailyBars(unittest.TestCase):
    symbols = [f"S{i:03d}" for i in range(450)]

    def test_a_failed_load_resumes_at_the_failed_request(self):
        class FakeHttp:
            def __init__(self):
                self.calls, self.failing = [], 3

            def alpaca_json(self, base, path, params):
                first = params["symbols"].split(",")[0]
                self.calls.append((first, params.get("page_token")))
                if first == "S200" and self.failing:
                    self.failing -= 1
                    raise urllib.error.HTTPError(path, 429, "too many requests", {}, None)
                if first == "S000" and not params.get("page_token"):
                    return {"bars": {"S000": [{"v": 10}] * 5}, "next_page_token": "p2"}
                return {"bars": {s: [{"v": 20}] * 5 for s in params["symbols"].split(",")}, "next_page_token": None}
        loader, http = M.AdvLoader(self.symbols, date(2026, 9, 24), sleep=lambda s: None), FakeHttp()
        with self.assertRaises(urllib.error.HTTPError):
            loader.run(http)
        adv = loader.run(http)
        self.assertEqual(http.calls, [("S000", None), ("S000", "p2"), ("S200", None), ("S200", None), ("S200", None), ("S200", None), ("S400", None)])
        self.assertEqual((len(adv), adv["S000"], adv["S449"], loader.failures), (450, 15.0, 20.0, 3))

    def test_a_budget_refusal_ends_the_attempt_at_once(self):
        class Refusing:
            calls = 0

            def alpaca_json(self, base, path, params):
                Refusing.calls += 1
                raise M.BudgetExceeded("adv_bars")
        slept = []
        loader = M.AdvLoader(self.symbols, date(2026, 9, 24), sleep=slept.append)
        with self.assertRaises(M.BudgetExceeded):
            loader.run(Refusing())
        self.assertEqual((Refusing.calls, slept, loader.index), (1, [], 0))

    def test_the_daily_bar_load_stays_inside_its_per_minute_cap(self):
        clock = [0.0]
        budget = M.Budget(per_minute={"adv_bars": 2}, clock=lambda: clock[0])
        taken = []
        for t in (0.0, 1.0, 2.0, 59.0, 60.5, 61.5):
            clock[0] = t
            taken.append(budget.take("adv_bars"))
        self.assertEqual((taken, budget.refused["adv_bars"]), ([True, True, False, False, True, True], 2))
        budget.start_sweep()   # a per-minute cap does not reset with the sweep
        clock[0] = 62.0
        self.assertFalse(budget.take("adv_bars"))

    def test_a_zero_rss_interval_is_refused_not_divided_by(self):
        args = M.parser().parse_args(["run", "--standalone", "--env-file", "e", "--out", "o", "--rss-seconds", "0"])
        self.assertEqual(M.plan_budget(13_500, args)["refusals"], ["invalid_bounds"])


class IexRecorder(unittest.TestCase):
    def test_status_luld_and_imbalance_messages_land_in_their_files_with_tape_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink, state = M.Sink(Path(tmp)), M.State()
            on_iex = M.iex_handler(state, sink)
            for msg in ({"T": "s", "S": "AAA", "sc": "H", "rc": "T1", "t": "2026-09-24T14:00:00Z", "z": "C"},
                        {"T": "l", "S": "BBB", "u": 11.0, "d": 9.0, "i": "B", "t": "2026-09-24T14:00:00Z", "z": "A"},
                        {"T": "i", "S": "CCC", "p": 5.5, "t": "2026-09-24T14:00:00Z", "z": "B"},
                        {"T": "s", "S": "DDD", "sc": "2", "rc": "M", "t": "2026-09-24T14:01:00Z", "z": "A"}):
                on_iex(msg)
            sink.close()
            files = {name: records(tmp, name) for name in ("status", "luld", "imbalance")}
        self.assertEqual({k: [r["S"] for r in v] for k, v in files.items()}, {"status": ["AAA", "DDD"], "luld": ["BBB"], "imbalance": ["CCC"]})
        self.assertTrue(all(r["received_at"] for v in files.values() for r in v))
        self.assertEqual(dict(state.iex_tapes), {"s:C": 1, "l:A": 1, "i:B": 1, "s:A": 1})
        self.assertEqual((state.haltbook.stream_category("AAA"), state.haltbook.stream_category("DDD"), state.haltbook.band("BBB")["u"]),
                         ("news", "volatility", 11.0))

    def test_the_iex_stream_is_opt_in_and_refused_while_a_declared_engine_config_streams_iex(self):
        self.assertFalse(M.parser().parse_args(["run", "--standalone", "--env-file", "e", "--out", "o"]).iex_status)
        market, streams = Market(), FakeStreams()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            engine = tmp / "engine.json"
            engine.write_text(json.dumps({"feed": "iex"}))
            with streams.patch():
                rc = market.run(["run", "--standalone", "--out", str(tmp / "out"), "--until-et", "00:00", "--no-corporate-actions",
                                 "--iex-status", "--engine-config", str(engine)], tmp)
            monitor = day_files(tmp / "out")["monitor.jsonl"]
        (refused,) = [m for m in monitor if m.get("event") == "stream_refused"]
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(streams.connects), sorted([M.NEWS_WS, M.OPRA_WS]))   # no IEX connection
        self.assertEqual((refused["endpoint"], refused["reason"], refused["configs"]), ("v2-iex", "engine_config_streams_iex", [str(engine)]))


class RunLoop(unittest.TestCase):
    def test_two_sweeps_inside_a_minute_make_one_rss_request_and_one_edgar_cycle(self):
        market, streams, snapshots = Market(), FakeStreams(), []
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out = tmp / "out"

            def on_request(url):
                if "/v2/stocks/snapshots" in url:
                    snapshots.append(url)
                    if len(snapshots) == 2:
                        (out / "STOP").touch()
            market.on_request = on_request
            with streams.patch():
                rc = market.run(["run", "--standalone", "--out", str(out), "--until-et", "23:59", "--sweep-seconds", "1", "--edgar-seconds", "30",
                                 "--no-corporate-actions", "--no-screener", "--no-option-chains", "--no-finra"], tmp)
            sweeps = [m for m in day_files(out)["monitor.jsonl"] if m.get("event") == "sweep"]
        self.assertEqual((rc, len(sweeps)), (0, 2))
        self.assertEqual((sum("nasdaqtrader.com" in u for u in market.opened), sum("browse-edgar" in u for u in market.opened)), (1, 7))
        self.assertEqual([("halt_changes" in s, "edgar_new" in s) for s in sweeps], [(True, True), (False, False)])
        self.assertEqual(sorted(streams.connects), sorted([M.NEWS_WS, M.OPRA_WS]))


class PairedBoards(unittest.TestCase):
    def test_board_v2_rows_carry_board_v1_scores_of_the_same_pass(self):
        at = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)
        state = M.State()
        state.today = date(2026, 9, 24)
        state.features = {s: {"s": s, "chg": 0.02, "p": 10.0, "v": None, "spr_bps": 10.0} for s in ("N", "Z")}
        state.news["N"] = {1: at.timestamp() - 60}
        state.halts["N"].append({"IssueSymbol": "N", "ReasonCode": "T1"})
        actions = state.ca.by_symbol(state.today)
        rows, v1 = M.score_rows(state, at, M.v2_scoring_extra(state, at, actions))
        board, _ = M.build_board(state, at, rows={s: rows[s] for s in v1})
        state.news["N"].update({2: at.timestamp() - 30, 3: at.timestamp() - 10})   # arrives while the chains are polled
        state.filings["Z"].append({"form": "SC TO-T", "items": [], "role": "Subject"})
        board_v2, incentive_v2 = M.build_board_v2(state, at, rows=rows, v1=v1, actions=actions)
        (n1,), (n2,) = [r for r in board if r["symbol"] == "N"], [r for r in board_v2 if r["symbol"] == "N"]
        self.assertEqual((n2["score_v1"], n2["parts"], n1["parts"]["news"]), (n1["score"], n1["parts"], 1.0))
        self.assertNotIn("Z", incentive_v2)   # scored at the next sweep, in both boards alike


if __name__ == "__main__":
    unittest.main()
