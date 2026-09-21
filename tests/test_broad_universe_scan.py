"""Local integration checks for the broad-market scan/watchlist (synthetic fixtures only).

Mocked HTTP session, fixed --now, no network, no credentials, no real dataset.
These are local integration checks against synthetic fixtures, never broker or
upstream acceptance evidence.
"""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "blueprints/us-equities/broad-universe/scan.py"
SPEC = importlib.util.spec_from_file_location("broad_universe_scan", PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


def http_response(payload, status=200, headers=None):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(payload).encode()
    result.headers.update(headers or {"X-Ratelimit-Limit": "200", "X-Ratelimit-Remaining": "199"})
    return result


def calendar_day(date, open_="09:30", close="16:00"):
    return {"date": date, "open": open_, "close": close}


CALENDAR_WEEK = [calendar_day("2026-09-14"), calendar_day("2026-09-15"), calendar_day("2026-09-16"),
                 calendar_day("2026-09-17"), calendar_day("2026-09-18"), calendar_day("2026-09-21")]


def clock_payload(is_open, next_open, next_close):
    return {"is_open": is_open, "next_open": next_open, "next_close": next_close,
            "timestamp": "2026-09-21T00:00:00Z"}


@unittest.skipUnless(HAS_REQUESTS, "requires requests")
class SessionAllowList(unittest.TestCase):
    def test_disallowed_path_is_refused(self):
        session = m.Session("k", "s")
        with self.assertRaises(m.ScanError):
            session.get(m.TRADING_HOST, "/v2/account")

    def test_disallowed_host_is_refused(self):
        session = m.Session("k", "s")
        with self.assertRaises(m.ScanError):
            session.get("https://evil.example.com", "/v2/clock")

    def test_redirect_is_rejected(self):
        session = m.Session("k", "s")
        with patch("requests.Session.request", return_value=http_response({}, 302)):
            with self.assertRaises(m.ScanError):
                session.get(m.TRADING_HOST, "/v2/clock")

    def test_request_cap_is_enforced(self):
        session = m.Session("k", "s", request_cap=1)
        with patch("requests.Session.request", return_value=http_response({"is_open": False})):
            session.get(m.TRADING_HOST, "/v2/clock")
            with self.assertRaises(m.ScanError):
                session.get(m.TRADING_HOST, "/v2/clock")

    def test_oversized_url_is_refused_before_any_get(self):
        session = m.Session("k", "s")
        huge = ",".join(f"SYM{i:06d}" for i in range(2000))
        with patch("requests.Session.request", return_value=http_response({})) as http:
            with self.assertRaises(m.ScanError):
                session.get(m.DATA_HOST, "/v2/stocks/snapshots", params={"symbols": huge, "feed": "sip"})
        http.assert_not_called()

    def test_rate_limit_headers_are_recorded(self):
        session = m.Session("k", "s")
        with patch("requests.Session.request",
                   return_value=http_response({"is_open": False}, headers={"X-Ratelimit-Remaining": "17"})):
            session.get(m.TRADING_HOST, "/v2/clock")
        self.assertEqual(session.log[-1]["rate_headers"]["x-ratelimit-remaining"], "17")


class SessionStateDetermination(unittest.TestCase):
    def test_pre_market(self):
        now = datetime(2026, 9, 21, 13, 0, tzinfo=timezone.utc)  # 09:00 ET
        clock = clock_payload(False, "2026-09-21T13:30:00Z", "2026-09-21T20:00:00Z")
        info = m.determine_session(now, clock, CALENDAR_WEEK)
        self.assertEqual(info["session_state"], "pre_market")
        self.assertEqual(info["current_or_last_regular_session"], "2026-09-18")
        self.assertEqual(info["previous_regular_session"], "2026-09-17")

    def test_regular_open(self):
        now = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)  # 11:00 ET
        clock = clock_payload(True, "2026-09-22T13:30:00Z", "2026-09-21T20:00:00Z")
        info = m.determine_session(now, clock, CALENDAR_WEEK)
        self.assertEqual(info["session_state"], "regular_open")
        self.assertEqual(info["current_or_last_regular_session"], "2026-09-21")
        self.assertEqual(info["previous_regular_session"], "2026-09-18")

    def test_after_hours(self):
        now = datetime(2026, 9, 21, 21, 0, tzinfo=timezone.utc)  # 17:00 ET
        clock = clock_payload(False, "2026-09-22T13:30:00Z", "2026-09-22T20:00:00Z")
        info = m.determine_session(now, clock, CALENDAR_WEEK)
        self.assertEqual(info["session_state"], "after_hours")
        self.assertEqual(info["current_or_last_regular_session"], "2026-09-21")
        self.assertEqual(info["previous_regular_session"], "2026-09-18")

    def test_weekend_is_closed(self):
        now = datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc)  # Saturday
        clock = clock_payload(False, "2026-09-21T13:30:00Z", "2026-09-21T20:00:00Z")
        info = m.determine_session(now, clock, CALENDAR_WEEK)
        self.assertEqual(info["session_state"], "closed")
        self.assertEqual(info["current_or_last_regular_session"], "2026-09-18")

    def test_holiday_is_closed(self):
        # 2026-09-20 (Sunday, also absent from calendar as a holiday stand-in) is closed.
        now = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)
        clock = clock_payload(False, "2026-09-21T13:30:00Z", "2026-09-21T20:00:00Z")
        info = m.determine_session(now, clock, CALENDAR_WEEK)
        self.assertEqual(info["session_state"], "closed")
        self.assertEqual(info["current_or_last_regular_session"], "2026-09-18")


class SymbolBatching(unittest.TestCase):
    def test_snapshot_batches_stay_under_url_budget_and_report_missing(self):
        symbols = [f"SYM{i:04d}" for i in range(1200)]
        batches = m.batch_symbols_for_url(symbols, m.DATA_HOST, "/v2/stocks/snapshots", {"feed": "sip"})
        self.assertGreater(len(batches), 1)
        for group in batches:
            self.assertLess(len(",".join(group)), m.MAX_URL_BYTES)
        self.assertEqual(sum(len(b) for b in batches), len(symbols))

    def test_missing_symbols_are_reported_not_dropped(self):
        session = m.Session("k", "s")
        calls = []

        def request(method, url, **kwargs):
            calls.append(kwargs["params"]["symbols"])
            return http_response({"AAA": {"dailyBar": {"t": "2026-09-21T04:00:00Z", "c": 10, "v": 100}}})

        with patch("requests.Session.request", side_effect=request):
            snapshots, missing = m.fetch_snapshots(session, ["AAA", "BBB"])
        self.assertIn("AAA", snapshots)
        self.assertEqual(missing, {"BBB"})

    def test_snapshot_wrapper_key_is_also_supported(self):
        session = m.Session("k", "s")

        def request(method, url, **kwargs):
            return http_response({"snapshots": {"AAA": {"dailyBar": {"t": "2026-09-21T04:00:00Z", "c": 10, "v": 100}}}})

        with patch("requests.Session.request", side_effect=request):
            snapshots, missing = m.fetch_snapshots(session, ["AAA"])
        self.assertIn("AAA", snapshots)


class ObservationClassification(unittest.TestCase):
    def test_today_session_and_percent_change(self):
        now = datetime(2026, 9, 21, 21, 0, tzinfo=timezone.utc)
        snapshot = {"dailyBar": {"t": "2026-09-21T04:00:00Z", "o": 10, "h": 11, "l": 9, "c": 11, "v": 1000},
                    "prevDailyBar": {"t": "2026-09-18T04:00:00Z", "c": 10, "v": 900},
                    "latestQuote": {"bp": 10.9, "ap": 11.0, "t": "2026-09-21T20:59:30Z"},
                    "latestTrade": {"p": 11.0, "t": "2026-09-21T20:59:50Z"}}
        row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-18", "regular_open", now)
        self.assertEqual(row["observation_class"], "today_session")
        self.assertAlmostEqual(row["pct_change"], 10.0)
        self.assertNotIn("prev_bar_mismatch", row)
        self.assertFalse(row["stale_quote"])

    def test_missing_symbol_is_flagged_missing(self):
        row = m.classify_observation("AAA", None, "2026-09-21", "2026-09-18", "regular_open",
                                      datetime(2026, 9, 21, tzinfo=timezone.utc))
        self.assertEqual(row["observation_class"], "missing")

    def test_previous_session_classification(self):
        now = datetime(2026, 9, 21, 13, 0, tzinfo=timezone.utc)
        snapshot = {"dailyBar": {"t": "2026-09-18T04:00:00Z", "o": 10, "h": 11, "l": 9, "c": 11, "v": 1000},
                    "prevDailyBar": {"t": "2026-09-17T04:00:00Z", "c": 10, "v": 900}}
        row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-17", "pre_market", now)
        self.assertEqual(row["observation_class"], "previous_session")

    def test_prev_bar_mismatch_when_prev_date_is_wrong(self):
        now = datetime(2026, 9, 21, 21, 0, tzinfo=timezone.utc)
        snapshot = {"dailyBar": {"t": "2026-09-21T04:00:00Z", "o": 10, "h": 11, "l": 9, "c": 11, "v": 1000},
                    "prevDailyBar": {"t": "2026-09-17T04:00:00Z", "c": 10, "v": 900}}
        row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-18", "regular_open", now)
        self.assertTrue(row["prev_bar_mismatch"])
        self.assertNotIn("pct_change", row)

    def test_stale_quote_flagged_only_during_regular_open(self):
        now = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)
        snapshot = {"dailyBar": {"t": "2026-09-21T04:00:00Z", "c": 11, "v": 1000},
                    "prevDailyBar": {"t": "2026-09-18T04:00:00Z", "c": 10, "v": 900},
                    "latestQuote": {"bp": 10.9, "ap": 11.0, "t": "2026-09-21T14:57:00Z"}}
        open_row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-18", "regular_open", now)
        closed_row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-18", "after_hours", now)
        self.assertTrue(open_row["stale_quote"])
        self.assertFalse(closed_row["stale_quote"])
        self.assertIn("quote_age_note", closed_row)

    def test_invalid_quote_bid_below_ask_violation(self):
        now = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)
        snapshot = {"dailyBar": {"t": "2026-09-21T04:00:00Z", "c": 11, "v": 1000},
                    "prevDailyBar": {"t": "2026-09-18T04:00:00Z", "c": 10, "v": 900},
                    "latestQuote": {"bp": 11.5, "ap": 11.0, "t": "2026-09-21T14:59:55Z"}}
        row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-18", "regular_open", now)
        self.assertTrue(row["quote_invalid"])

    def test_zero_bid_is_invalid(self):
        now = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)
        snapshot = {"dailyBar": {"t": "2026-09-21T04:00:00Z", "c": 11, "v": 1000},
                    "prevDailyBar": {"t": "2026-09-18T04:00:00Z", "c": 10, "v": 900},
                    "latestQuote": {"bp": 0, "ap": 11.0, "t": "2026-09-21T14:59:55Z"}}
        row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-18", "regular_open", now)
        self.assertTrue(row["quote_invalid"])


class UniverseBuilding(unittest.TestCase):
    def test_otc_and_placeholder_and_untradable_are_excluded_not_silently_merged(self):
        assets = [
            {"class": "us_equity", "exchange": "NASDAQ", "symbol": "AAA", "status": "active", "tradable": True, "name": "AAA Inc"},
            {"class": "us_equity", "exchange": "OTC", "symbol": "BBB", "status": "active", "tradable": True, "name": "BBB Inc"},
            {"class": "us_equity", "exchange": "NASDAQ", "symbol": "CC1W", "status": "active", "tradable": True, "name": "CC1W Warrant"},
            {"class": "us_equity", "exchange": "NASDAQ", "symbol": "DDD", "status": "inactive", "tradable": True, "name": "DDD Inc"},
            {"class": "us_equity", "exchange": "NASDAQ", "symbol": "EEE", "status": "active", "tradable": False, "name": "EEE Inc"},
        ]
        universe, skipped = m.build_universe(assets)
        self.assertEqual([a["symbol"] for a in universe], ["AAA"])
        self.assertIn("OTC", skipped)
        self.assertIn("placeholder_symbol", skipped)
        self.assertIn("not_active_tradable", skipped)


class ProviderScreens(unittest.TestCase):
    def test_screens_are_labelled_bounded_not_market_coverage(self):
        session = m.Session("k", "s")

        def request(method, url, **kwargs):
            if url.endswith("/movers"):
                return http_response({"gainers": [{"symbol": "AAA"}], "losers": [{"symbol": "BBB"}]})
            return http_response({"most_actives": [{"symbol": "CCC"}]})

        with patch("requests.Session.request", side_effect=request):
            raw, public = m.fetch_provider_screens(session)
        self.assertEqual(public["movers"]["gainers_symbols"], ["AAA"])
        self.assertEqual(public["most_actives"]["symbols"], ["CCC"])
        self.assertIn("bounded_top_n_provider_screen_includes_sub_5_names_not_market_coverage",
                      public["movers"]["label"])
        self.assertIn("gainers", raw["movers"])


class PinnedSymbols(unittest.TestCase):
    def test_pinned_present_even_when_ineligible_or_missing(self):
        rows = {"META": {"observation_class": "missing"}}
        eligibility = {"META": {"eligible": False}}
        lists = m.build_lists(rows, eligibility, ["META", "AMD"])
        self.assertIn("META", lists["pinned"])
        self.assertIn("AMD", lists["pinned"])
        self.assertFalse(lists["pinned"]["AMD"]["present_in_universe"])
        self.assertFalse(lists["pinned"]["META"]["eligible"])


@unittest.skipUnless(HAS_DUCKDB, "requires duckdb")
class HistoryEligibilityAndSignals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "daily.parquet")

    def _write_history(self, rows):
        con = duckdb.connect()
        con.execute("""
            CREATE TABLE daily (symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, raw_l DOUBLE,
                                 raw_c DOUBLE, raw_v DOUBLE, raw_n BIGINT, raw_vw DOUBLE,
                                 all_o DOUBLE, all_h DOUBLE, all_l DOUBLE, all_c DOUBLE, all_v DOUBLE,
                                 in_raw BOOLEAN, in_all BOOLEAN)
        """)
        con.executemany("INSERT INTO daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.execute(f"COPY daily TO '{self.path}' (FORMAT PARQUET)")
        con.close()

    def _flat_history(self, symbol, n, close=20.0, volume=2_000_000.0, high=None, low=None, start="2026-06-01"):
        base = datetime.fromisoformat(start)
        rows = []
        for i in range(n):
            d = (base + timedelta(days=i)).date().isoformat()
            h = high if high is not None else close + 0.5
            l = low if low is not None else close - 0.5
            rows.append((symbol, d, close, h, l, close, volume, 1000, close,
                         close, h, l, close, volume, True, True))
        return rows

    def test_eligible_requires_price_liquidity_and_history_length(self):
        rows = self._flat_history("AAA", 65, close=20.0, volume=2_000_000.0)  # dv ~ 40M
        self._write_history(rows)
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        self.assertFalse(status["history_not_adjacent"])
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.5, "raw_low": 20.4, "raw_volume": 2_000_000.0}
        elig = m.compute_eligibility("AAA", obs, {"name": "AAA Inc"}, hist["AAA"], status)
        self.assertTrue(elig["eligible"])
        self.assertEqual(elig["prior_bars"], 65)

    def test_ineligible_below_min_close(self):
        rows = self._flat_history("BBB", 65, close=20.0, volume=2_000_000.0)
        self._write_history(rows)
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        obs = {"raw_close": 2.0, "raw_open": 2.0, "raw_high": 2.1, "raw_low": 1.9, "raw_volume": 2_000_000.0}
        elig = m.compute_eligibility("BBB", obs, {"name": "BBB Inc"}, hist["BBB"], status)
        self.assertFalse(elig["eligible"])

    def test_ineligible_below_liquidity_floor(self):
        rows = self._flat_history("CCC", 65, close=20.0, volume=1000.0)  # dv ~ 20k, below 20M floor
        self._write_history(rows)
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        obs = {"raw_close": 20.0, "raw_open": 20.0, "raw_high": 20.5, "raw_low": 19.5, "raw_volume": 1000.0}
        elig = m.compute_eligibility("CCC", obs, {"name": "CCC Inc"}, hist["CCC"], status)
        self.assertFalse(elig["eligible"])

    def test_fund_like_name_excludes_primary_lane_but_reports_all_instruments(self):
        rows = self._flat_history("SPYX", 65, close=20.0, volume=2_000_000.0)
        self._write_history(rows)
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.5, "raw_low": 20.4, "raw_volume": 2_000_000.0}
        elig = m.compute_eligibility("SPYX", obs, {"name": "SPYX Index Trust ETF"}, hist["SPYX"], status)
        self.assertFalse(elig["eligible"])
        self.assertTrue(elig["eligible_all_instruments"])
        self.assertTrue(elig["instrument_lane_fund_like"])

    def test_history_not_adjacent_marks_unknown_and_skips_signals(self):
        rows = self._flat_history("DDD", 65, close=20.0, volume=2_000_000.0)
        self._write_history(rows)
        hist, status = m.compute_history_features(self.path, "2026-09-18")  # dataset ends earlier
        self.assertTrue(status["history_not_adjacent"])
        elig = m.compute_eligibility("DDD", {"raw_close": 21.0, "raw_volume": 1.0}, None, None, status)
        self.assertIsNone(elig["eligible"])
        self.assertEqual(elig["eligibility_status"], "unknown_history_not_adjacent")

    def test_no_history_marks_unknown(self):
        status = {"history_used": False}
        elig = m.compute_eligibility("EEE", {"raw_close": 21.0, "raw_volume": 1.0}, None, None, status)
        self.assertIsNone(elig["eligible"])
        self.assertEqual(elig["eligibility_status"], "unknown_no_history")

    def test_s1_momentum_breakout_hand_computed(self):
        # 64 flat prior sessions at close=20 (high=20.5) then evaluate a breakout scanned bar.
        rows = self._flat_history("MOM", 64, close=20.0, high=20.5, low=19.5, volume=2_000_000.0)
        self._write_history(rows)
        hist, status = m.compute_history_features(self.path, "2026-08-03")
        h = hist["MOM"]
        self.assertAlmostEqual(h["high60"], 20.5)
        self.assertAlmostEqual(h["med20"], 20.0 * 2_000_000.0)
        # dv = 25 * 8_000_000 = 200M >= 2*med20(40M); close 25 > high60 20.5; clv = (25-24)/(25-24)=1 >= 0.75
        obs = {"raw_close": 25.0, "raw_open": 24.0, "raw_high": 25.0, "raw_low": 24.0, "raw_volume": 8_000_000.0}
        signals = m.compute_signals(obs, h, 25.0 * 8_000_000.0)
        self.assertTrue(signals["flags"]["S1_momentum_breakout"])

    def test_s5_gap_and_hold_hand_computed(self):
        rows = self._flat_history("GAP", 64, close=20.0, high=20.5, low=19.5, volume=2_000_000.0)
        self._write_history(rows)
        hist, status = m.compute_history_features(self.path, "2026-08-03")
        h = hist["GAP"]
        # prev_close=20; gap = open/prev_close - 1 = 21/20-1 = 0.05 >= 0.04; close 21.5 >= open 21; dv large
        obs = {"raw_close": 21.5, "raw_open": 21.0, "raw_high": 21.5, "raw_low": 20.9, "raw_volume": 10_000_000.0}
        signals = m.compute_signals(obs, h, 21.5 * 10_000_000.0)
        self.assertTrue(signals["flags"]["S5_gap_and_hold"])

    def test_possible_corporate_action_flag_on_large_gap(self):
        rows = self._flat_history("COR", 64, close=20.0, high=20.5, low=19.5, volume=2_000_000.0)
        self._write_history(rows)
        hist, status = m.compute_history_features(self.path, "2026-08-03")
        obs = {"raw_close": 30.0, "raw_open": 30.0, "raw_high": 30.5, "raw_low": 29.5, "raw_volume": 2_000_000.0}
        signals = m.compute_signals(obs, hist["COR"], 30.0 * 2_000_000.0)
        self.assertTrue(signals["possible_corporate_action"])


class PublicOutputRedaction(unittest.TestCase):
    def test_public_symbol_row_has_no_price_or_quote_fields(self):
        rows = {"AAA": {"observation_class": "today_session", "observed_at": "2026-09-21T20:00:00Z",
                        "daily_bar_t": "2026-09-21T04:00:00Z", "pct_change": 12.345, "dollar_volume": 5_000_000_000,
                        "raw_close": 123.45, "quote_at": "2026-09-21T19:59:00Z", "bid": 1, "ask": 2}}
        eligibility = {"AAA": {"eligible": True, "signals": {"flags": {"S1_momentum_breakout": True}}}}
        lists = m.build_lists(rows, eligibility, [])
        public_row = m.public_symbol_row("AAA", rows, eligibility, lists)
        blob = json.dumps(public_row)
        self.assertNotIn("123.45", blob)
        self.assertNotIn("quote_at", public_row)
        self.assertNotIn("bid", public_row)
        self.assertEqual(public_row["percent_change"], 12.3)
        self.assertEqual(public_row["dollar_volume_bucket"], ">=1B")

    def test_assemble_public_has_no_headline_text(self):
        session_info = {"run_time_utc": "2026-09-21T20:00:00Z", "run_time_et": "2026-09-21T16:00:00-04:00",
                        "session_state": "regular_open", "current_or_last_regular_session": "2026-09-21",
                        "previous_regular_session": "2026-09-18", "next_open": None, "next_close": None}
        news_items = [{"symbols": ["META"], "created_at": "2026-09-21T19:00:00Z", "updated_at": "2026-09-21T19:05:00Z",
                       "observed_at": "2026-09-21T20:00:00Z", "source": "benzinga",
                       "url": "https://example.org/a", "headline_sha256": "a" * 64, "headline": "SECRET HEADLINE TEXT"}]
        lists = m.build_lists({}, {}, [])
        public = m.assemble_public(session_info, lists, {}, {}, {"scanned": 0}, {"history_used": False},
                                   news_items, False, {}, {"total_requests": 1})
        blob = json.dumps(public)
        self.assertNotIn("SECRET HEADLINE TEXT", blob)
        self.assertIn("headline_sha256", blob)


class NewsFetch(unittest.TestCase):
    def test_bounded_pages_and_capped_flag(self):
        session = m.Session("k", "s")
        calls = []

        def request(method, url, **kwargs):
            calls.append(kwargs["params"].get("page_token"))
            return http_response({"news": [], "next_page_token": "more"})

        with patch("requests.Session.request", side_effect=request):
            items, capped = m.fetch_news(session, {"META"}, datetime(2026, 9, 21, tzinfo=timezone.utc),
                                         lambda: datetime(2026, 9, 21, tzinfo=timezone.utc))
        self.assertEqual(len(calls), m.NEWS_MAX_PAGES)
        self.assertTrue(capped)

    def test_normalize_drops_articles_outside_requested_symbols(self):
        row = {"id": 1, "headline": "Example", "symbols": ["ZZZ"], "source": "x", "url": "https://example.org"}
        self.assertIsNone(m.normalize_news_row(row, datetime.now(timezone.utc), {"META"}))

    def test_normalize_hashes_headline_and_omits_body(self):
        row = {"id": 1, "headline": "Example headline", "symbols": ["META"], "source": "x",
               "url": "https://example.org", "content": "full body text should never appear"}
        result = m.normalize_news_row(row, datetime.now(timezone.utc), {"META"})
        self.assertNotIn("content", result)
        self.assertNotIn("full body", json.dumps(result))
        self.assertEqual(len(result["headline_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
