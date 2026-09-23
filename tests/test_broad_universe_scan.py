"""Local integration checks for the broad-market scan/watchlist (synthetic fixtures only).

Mocked HTTP session, fixed --now, no network, no credentials, no real dataset.
These are local integration checks against synthetic fixtures, never broker or
upstream acceptance evidence.
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
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

    def test_request_cap_is_checked_before_every_retry_attempt(self):
        # Reproduces the finding: with request_cap=2 and two 429s before a 200, the OLD code
        # checked the cap once before the loop and then issued all 3 attempts (exceeding the cap
        # by one). The fix must refuse the 3rd attempt instead of sending it.
        session = m.Session("k", "s", request_cap=2)
        responses = iter([http_response({}, 429), http_response({}, 429), http_response({"ok": True}, 200)])

        def request(method, url, **kwargs):
            return next(responses)

        with patch("requests.Session.request", side_effect=request), patch("time.sleep"):
            with self.assertRaises(m.ScanError) as ctx:
                session.get(m.TRADING_HOST, "/v2/clock")
        self.assertEqual(str(ctx.exception), "request_cap_exceeded")
        self.assertEqual(len(session.log), 2)


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


@unittest.skipUnless(HAS_REQUESTS, "requires requests")
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
            snapshots, missing, observed_at = m.fetch_snapshots(session, ["AAA", "BBB"])
        self.assertIn("AAA", snapshots)
        self.assertEqual(missing, {"BBB"})
        self.assertIn("AAA", observed_at)
        self.assertIn("BBB", observed_at)

    def test_snapshot_wrapper_key_is_also_supported(self):
        session = m.Session("k", "s")

        def request(method, url, **kwargs):
            return http_response({"snapshots": {"AAA": {"dailyBar": {"t": "2026-09-21T04:00:00Z", "c": 10, "v": 100}}}})

        with patch("requests.Session.request", side_effect=request):
            snapshots, missing, observed_at = m.fetch_snapshots(session, ["AAA"])
        self.assertIn("AAA", snapshots)

    def test_each_batch_is_stamped_with_its_own_fetch_time_clock_call(self):
        # Reproduces the run-start-timestamp defect: with two batches, each batch's observed_at
        # must come from a clock() call made AFTER that batch's request, not a single timestamp
        # captured once before any snapshot request was issued.
        session = m.Session("k", "s")
        symbols = [f"SYM{i:04d}" for i in range(1200)]  # forces multiple url-budget batches
        base = datetime(2026, 9, 21, 20, 0, 0, tzinfo=timezone.utc)
        counter = itertools.count()

        def request(method, url, **kwargs):
            return http_response({})

        with patch("requests.Session.request", side_effect=request):
            _, _, observed_at = m.fetch_snapshots(session, symbols,
                                                    clock=lambda: base + timedelta(seconds=30 * next(counter)))
        distinct_timestamps = set(observed_at.values())
        self.assertGreater(len(distinct_timestamps), 1)


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
        # The bar's own date ("2026-09-18") must equal previous_session exactly to be classified
        # "previous_session"; anything older is "stale_bar" (see the next test).
        row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-18", "pre_market", now)
        self.assertEqual(row["observation_class"], "previous_session")

    def test_stale_bar_classification_for_older_than_previous_session(self):
        # Reproduces the opus minor finding: a symbol whose last trade is weeks old must not be
        # silently reported as "previous_session" (which would let it compete in today's dollar
        # volume ranking using stale data undetected by prev_bar_mismatch).
        now = datetime(2026, 9, 21, 21, 0, tzinfo=timezone.utc)
        snapshot = {"dailyBar": {"t": "2026-06-05T04:00:00Z", "o": 10, "h": 11, "l": 9, "c": 13.5, "v": 1000},
                    "prevDailyBar": {"t": "2026-06-04T04:00:00Z", "c": 10, "v": 900}}
        row = m.classify_observation("STALE", snapshot, "2026-09-21", "2026-09-18", "regular_open", now)
        self.assertEqual(row["observation_class"], "stale_bar")

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

    def test_negative_quote_age_is_flagged_clock_skew_not_treated_as_fresh(self):
        # Reproduces the run-start-timestamp defect from the other side: if observed_at is EARLIER
        # than the quote's own timestamp (clocks disagree), the age must not be silently accepted
        # as "fresh" (stale_quote=False) - it must be flagged clock_skew with staleness left unknown.
        observed_at = datetime(2026, 9, 21, 15, 0, 0, tzinfo=timezone.utc)
        snapshot = {"dailyBar": {"t": "2026-09-21T04:00:00Z", "c": 11, "v": 1000},
                    "prevDailyBar": {"t": "2026-09-18T04:00:00Z", "c": 10, "v": 900},
                    "latestQuote": {"bp": 10.9, "ap": 11.0, "t": "2026-09-21T15:00:30Z"}}
        row = m.classify_observation("AAA", snapshot, "2026-09-21", "2026-09-18", "regular_open", observed_at)
        self.assertLess(row["quote_age_seconds"], 0)
        self.assertTrue(row["clock_skew"])
        self.assertIsNone(row["stale_quote"])


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


@unittest.skipUnless(HAS_REQUESTS, "requires requests")
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

    def _spy_calendar(self, n, start="2026-06-01"):
        """SPY reference bars compute_history_features needs to build its session calendar
        (cal_idx), mirroring evaluate.py's build_calendar. Contiguous by construction unless a
        test deliberately writes its own gapped SPY/symbol rows instead of using this helper."""
        return self._flat_history("SPY", n, close=400.0, high=400.5, low=399.5, volume=50_000_000.0, start=start)

    def test_eligible_requires_price_liquidity_and_history_length(self):
        rows = self._flat_history("AAA", 65, close=20.0, volume=2_000_000.0)  # dv ~ 40M
        self._write_history(rows + self._spy_calendar(65))
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        self.assertFalse(status["history_not_adjacent"])
        self.assertEqual(hist["AAA"]["span60"], 60)
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.5, "raw_low": 20.4, "raw_volume": 2_000_000.0,
               "observation_class": "today_session"}
        elig = m.compute_eligibility("AAA", obs, {"name": "AAA Inc"}, hist["AAA"], status)
        self.assertTrue(elig["eligible"])
        self.assertEqual(elig["prior_bars"], 65)
        self.assertEqual(elig["eligibility_status"], "computed")

    def test_ineligible_below_min_close(self):
        rows = self._flat_history("BBB", 65, close=20.0, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(65))
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        obs = {"raw_close": 2.0, "raw_open": 2.0, "raw_high": 2.1, "raw_low": 1.9, "raw_volume": 2_000_000.0,
               "observation_class": "today_session"}
        elig = m.compute_eligibility("BBB", obs, {"name": "BBB Inc"}, hist["BBB"], status)
        self.assertFalse(elig["eligible"])

    def test_ineligible_below_liquidity_floor(self):
        rows = self._flat_history("CCC", 65, close=20.0, volume=1000.0)  # dv ~ 20k, below 20M floor
        self._write_history(rows + self._spy_calendar(65))
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        obs = {"raw_close": 20.0, "raw_open": 20.0, "raw_high": 20.5, "raw_low": 19.5, "raw_volume": 1000.0,
               "observation_class": "today_session"}
        elig = m.compute_eligibility("CCC", obs, {"name": "CCC Inc"}, hist["CCC"], status)
        self.assertFalse(elig["eligible"])

    def test_fund_like_name_excludes_primary_lane_but_reports_all_instruments(self):
        rows = self._flat_history("SPYX", 65, close=20.0, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(65))
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.5, "raw_low": 20.4, "raw_volume": 2_000_000.0,
               "observation_class": "today_session"}
        elig = m.compute_eligibility("SPYX", obs, {"name": "SPYX Index Trust ETF"}, hist["SPYX"], status)
        self.assertFalse(elig["eligible"])
        self.assertTrue(elig["eligible_all_instruments"])
        self.assertTrue(elig["instrument_lane_fund_like"])

    def test_history_not_adjacent_marks_unknown_and_skips_signals(self):
        rows = self._flat_history("DDD", 65, close=20.0, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(65))
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

    def test_stale_symbol_history_is_unknown_not_silently_eligible(self):
        # Opus blocker reproduction: STALE's own last bar is months before previous_regular_session
        # even though the dataset (SPY/AAA) max session is current, so the OLD global-only check
        # (history_not_adjacent) passed and STALE was scored anyway. Per-symbol staleness must
        # make eligible None (unknown), never True/False, and must not compute signals.
        current_rows = self._flat_history("AAA", 65, close=20.0, volume=2_000_000.0)  # ends 2026-08-04
        stale_rows = self._flat_history("STALE", 65, close=10.0, volume=2_000_000.0, start="2026-03-01")  # ends 2026-05-04
        # SPY calendar must cover BOTH date ranges (STALE's older dates included) so the join in
        # compute_history_features can resolve cal_idx for STALE's rows at all.
        self._write_history(current_rows + stale_rows + self._spy_calendar(157, start="2026-03-01"))
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        self.assertFalse(status["history_not_adjacent"])
        self.assertNotEqual(hist["STALE"]["last_session_date"], "2026-08-04")
        obs = {"raw_close": 13.5, "raw_open": 13.0, "raw_high": 13.6, "raw_low": 12.9, "raw_volume": 20_000_000.0,
               "observation_class": "today_session"}
        elig = m.compute_eligibility("STALE", obs, {"name": "STALE Inc"}, hist["STALE"], status)
        self.assertIsNone(elig["eligible"])
        self.assertEqual(elig["eligibility_status"], "history_stale")
        self.assertNotIn("signals", elig)

    def test_mid_window_gap_in_last_60_bars_is_has_gap_not_silently_eligible(self):
        # Second angle on the same blocker: the symbol's last row DOES equal previous_regular_session
        # (so the naive "last row date" check alone would pass) but a session inside the trailing
        # 60-bar window is missing for this symbol only (SPY/the calendar still has it).
        base = datetime.fromisoformat("2026-01-01")
        all_dates = [(base + timedelta(days=i)).date().isoformat() for i in range(200)]
        spy_rows = [("SPY", d, 400.0, 400.5, 399.5, 400.0, 5e7, 1000, 400.0, 400.0, 400.5, 399.5, 400.0, 5e7, True, True)
                    for d in all_dates]
        gappy_dates = [d for i, d in enumerate(all_dates) if 135 <= i <= 199 and i != 160]
        gappy_rows = [("GAPPY", d, 20.0, 20.5, 19.5, 20.0, 2e6, 1000, 20.0, 20.0, 20.5, 19.5, 20.0, 2e6, True, True)
                      for d in gappy_dates]
        self._write_history(spy_rows + gappy_rows)
        hist, status = m.compute_history_features(self.path, all_dates[-1])
        self.assertFalse(status["history_not_adjacent"])
        self.assertEqual(hist["GAPPY"]["last_session_date"], all_dates[-1])
        self.assertNotEqual(hist["GAPPY"]["span60"], 60)
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.5, "raw_low": 20.4, "raw_volume": 2_000_000.0,
               "observation_class": "today_session"}
        elig = m.compute_eligibility("GAPPY", obs, {"name": "GAPPY Inc"}, hist["GAPPY"], status)
        self.assertIsNone(elig["eligible"])
        self.assertEqual(elig["eligibility_status"], "has_gap")
        self.assertNotIn("signals", elig)

    def test_stale_snapshot_bar_is_ineligible_even_with_perfect_history(self):
        # Codex "Exclude stale snapshot bars from current-session eligibility": history is perfect,
        # but today's snapshot bar itself is not the decision-session bar.
        rows = self._flat_history("OLDBAR", 65, close=20.0, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(65))
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.5, "raw_low": 20.4, "raw_volume": 2_000_000.0,
               "observation_class": "previous_session"}
        elig = m.compute_eligibility("OLDBAR", obs, {"name": "OLDBAR Inc"}, hist["OLDBAR"], status)
        self.assertFalse(elig["eligible"])
        self.assertEqual(elig["eligibility_status"], "stale_snapshot_bar")
        self.assertNotIn("signals", elig)

    def test_ambiguous_suffix_flag_matches_evaluator_convention(self):
        # Mirrors evaluate.py's AMBIGUOUS_TAIL exactly: 5-letter, no dot, tail in W/R/U -> flagged
        # (never excluded), reported regardless of eligibility outcome.
        status = {"history_used": False}
        flagged = m.compute_eligibility("ABCDW", {"raw_close": 1.0, "raw_volume": 1.0}, None, None, status)
        self.assertTrue(flagged["ambiguous_suffix_flag"])
        not_flagged_normal = m.compute_eligibility("META", {"raw_close": 1.0, "raw_volume": 1.0}, None, None, status)
        self.assertFalse(not_flagged_normal["ambiguous_suffix_flag"])
        not_flagged_dotted = m.compute_eligibility("ABCD.W", {"raw_close": 1.0, "raw_volume": 1.0}, None, None, status)
        self.assertFalse(not_flagged_dotted["ambiguous_suffix_flag"])

    def test_s1_momentum_breakout_hand_computed(self):
        # 64 flat prior sessions at close=20 (high=20.5) then evaluate a breakout scanned bar.
        rows = self._flat_history("MOM", 64, close=20.0, high=20.5, low=19.5, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(64))
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
        self._write_history(rows + self._spy_calendar(64))
        hist, status = m.compute_history_features(self.path, "2026-08-03")
        h = hist["GAP"]
        # prev_close=20; gap = open/prev_close - 1 = 21/20-1 = 0.05 >= 0.04; close 21.5 >= open 21; dv large
        obs = {"raw_close": 21.5, "raw_open": 21.0, "raw_high": 21.5, "raw_low": 20.9, "raw_volume": 10_000_000.0}
        signals = m.compute_signals(obs, h, 21.5 * 10_000_000.0)
        self.assertTrue(signals["flags"]["S5_gap_and_hold"])

    def test_possible_corporate_action_flag_on_large_gap(self):
        rows = self._flat_history("COR", 64, close=20.0, high=20.5, low=19.5, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(64))
        hist, status = m.compute_history_features(self.path, "2026-08-03")
        obs = {"raw_close": 30.0, "raw_open": 30.0, "raw_high": 30.5, "raw_low": 29.5, "raw_volume": 2_000_000.0}
        signals = m.compute_signals(obs, hist["COR"], 30.0 * 2_000_000.0)
        self.assertTrue(signals["possible_corporate_action"])

    def test_possible_corporate_action_nulls_all_signal_flags_with_reason(self):
        # Design decision (c) / codex "Align snapshot and history adjustment bases": once a
        # corporate action is possible, EVERY signal is withheld (null), not just left uncomputed
        # by accident, because every signal mixes today's raw bar with a history file whose
        # adjustment basis cannot be verified as consistent with it.
        rows = self._flat_history("SPLIT", 64, close=20.0, high=20.5, low=19.5, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(64))
        hist, status = m.compute_history_features(self.path, "2026-08-03")
        h = hist["SPLIT"]
        # Would otherwise satisfy S1 (close > high60, big dv, clv=1) if not suppressed.
        obs = {"raw_close": 30.0, "raw_open": 30.0, "raw_high": 30.0, "raw_low": 30.0, "raw_volume": 8_000_000.0}
        signals = m.compute_signals(obs, h, 30.0 * 8_000_000.0)
        self.assertTrue(signals["possible_corporate_action"])
        self.assertEqual(signals["flags"], {})
        self.assertEqual(signals["flags_null_reason"], "adjustment_basis_unverified")

    def test_possible_corporate_action_triggered_by_raw_pct_change_alone(self):
        # The gate must also catch a large SAME-FEED raw pct_change even when gap/r1 (which mix
        # today's raw bar with the history file's all-adjusted prev_close) look unremarkable.
        rows = self._flat_history("PCTGAP", 64, close=20.0, high=20.5, low=19.5, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(64))
        hist, status = m.compute_history_features(self.path, "2026-08-03")
        obs = {"raw_close": 20.5, "raw_open": 20.2, "raw_high": 20.6, "raw_low": 20.1, "raw_volume": 2_000_000.0,
               "pct_change": 45.0}
        signals = m.compute_signals(obs, hist["PCTGAP"], 20.5 * 2_000_000.0)
        self.assertTrue(signals["possible_corporate_action"])
        self.assertEqual(signals["flags"], {})

    def test_s4_requires_130_contiguous_bars_and_120_range10_observations(self):
        # Opus major #2 / codex "Require complete history before evaluating S4": with only 65
        # prior bars (far short of the 130 needed), range10_p20 must be null (not computed over a
        # partial window) and S4 must be absent (null), never true or false.
        rows = self._flat_history("SHORT", 65, close=20.0, high=20.5, low=19.5, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(65))
        hist, status = m.compute_history_features(self.path, "2026-08-04")
        h = hist["SHORT"]
        self.assertIsNone(h["range10_p20"])
        self.assertIsNone(h["span130"])
        # Contrived to satisfy the naive S4 condition (range10 <= range10_p20 and close > high20) if
        # a buggy implementation let range10_p20 be computed over a partial window anyway.
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.0, "raw_low": 20.9, "raw_volume": 2_000_000.0}
        signals = m.compute_signals(obs, h, 21.0 * 2_000_000.0)
        self.assertNotIn("S4_contraction_breakout", signals["flags"])
        self.assertNotIn("S4_contraction_breakout", signals["flags_evaluated"])

    def test_exactly_sixty_contiguous_prior_bars_are_eligible(self):
        # The history's last row is session t-1. Lagging by 60 there demanded 61 bars, so a
        # symbol meeting the frozen protocol with exactly 60 prior bars was rejected as has_gap.
        rows = self._flat_history("SIXTY", 60, close=20.0, volume=2_000_000.0)
        self._write_history(rows + self._spy_calendar(60))
        last = max(r[1] for r in rows)
        hist, status = m.compute_history_features(self.path, last)
        self.assertEqual(hist["SIXTY"]["prior_bars"], 60)
        self.assertEqual(hist["SIXTY"]["span60"], 60)
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.5, "raw_low": 20.4, "raw_volume": 2_000_000.0,
               "observation_class": "today_session"}
        elig = m.compute_eligibility("SIXTY", obs, {"name": "Sixty Inc"}, hist["SIXTY"], status)
        self.assertEqual(elig["eligibility_status"], "computed")
        self.assertTrue(elig["eligible"])

    def test_exactly_130_prior_bars_make_s4_evaluable(self):
        rows = self._flat_history("ONE30", 130, close=20.0, volume=2_000_000.0, start="2026-01-01")
        self._write_history(rows + self._spy_calendar(130, start="2026-01-01"))
        hist, _ = m.compute_history_features(self.path, max(r[1] for r in rows))
        self.assertEqual(hist["ONE30"]["span130"], 130)
        self.assertIsNotNone(hist["ONE30"]["range10_p20"])

    def test_range10_p20_window_is_t_minus_121_to_t_minus_2(self):
        # Hand computation from the protocol: with the last history row r = t-1, range10_p20 is
        # the 20th percentile (linear interpolation) of range10[u] for u in r-120..r-1, where
        # range10[u] = (max high - min low over u-9..u) / close[u]. A frame shifted by one row
        # (r-121..r-2) reads a different set because the amplitudes below rise strictly.
        n = 140
        base = datetime.fromisoformat("2026-01-01")
        dates = [(base + timedelta(days=i)).date().isoformat() for i in range(n)]
        amp = [1.0 + 0.01 * i for i in range(n)]  # strictly rising, so every window has its own p20
        rows = [("TRND", d, 100.0, 100.0 + a, 100.0 - a, 100.0, 2e6, 1000, 100.0,
                 100.0, 100.0 + a, 100.0 - a, 100.0, 2e6, True, True) for d, a in zip(dates, amp)]
        self._write_history(rows + self._spy_calendar(n, start="2026-01-01"))
        hist, _ = m.compute_history_features(self.path, dates[-1])

        def range10(u):
            window = amp[u - 9:u + 1]
            return (2 * max(window)) / 100.0

        def p20(values):
            ordered = sorted(values)
            pos = (len(ordered) - 1) * 0.2
            lo = int(pos)
            return ordered[lo] + (ordered[lo + 1] - ordered[lo]) * (pos - lo)

        r = n - 1
        expected = p20([range10(u) for u in range(r - 120, r)])
        shifted = p20([range10(u) for u in range(r - 121, r - 1)])
        self.assertNotAlmostEqual(expected, shifted, places=9)
        self.assertAlmostEqual(hist["TRND"]["range10_p20"], expected, places=12)
        self.assertAlmostEqual(hist["TRND"]["range10"], range10(r), places=12)

    def test_s4_fires_with_full_130_bar_contiguous_window(self):
        # Positive control: with a genuinely complete, contiguous 135-bar window (>=130 needed for
        # span130, >=121 for the 120-observation range10_p20 gate), S4 must be evaluable.
        base = datetime.fromisoformat("2026-01-01")
        all_dates = [(base + timedelta(days=i)).date().isoformat() for i in range(400)]
        spy_rows = self._flat_history("SPY", 400, close=400.0, high=400.5, low=399.5, volume=5e7, start="2026-01-01")
        full_dates = all_dates[-135:]
        full_rows = [("FULL", d, 20.0, 20.5, 19.5, 20.0, 2e6, 1000, 20.0, 20.0, 20.5, 19.5, 20.0, 2e6, True, True)
                     for d in full_dates]
        self._write_history(spy_rows + full_rows)
        hist, status = m.compute_history_features(self.path, full_dates[-1])
        h = hist["FULL"]
        self.assertEqual(h["span130"], 130)
        self.assertIsNotNone(h["range10_p20"])
        # range10 is flat at (20.5-19.5)/20 = 0.05 every day, so range10_p20 == 0.05 too; a close
        # above high20 (20.5) with range10 <= range10_p20 satisfies S4.
        obs = {"raw_close": 21.0, "raw_open": 20.5, "raw_high": 21.0, "raw_low": 20.9, "raw_volume": 2_000_000.0}
        signals = m.compute_signals(obs, h, 21.0 * 2_000_000.0)
        self.assertIn("S4_contraction_breakout", signals["flags_evaluated"])
        self.assertTrue(signals["flags"]["S4_contraction_breakout"])

    def test_s4_null_when_range10_p20_present_but_130_window_has_gap(self):
        # Unit-level isolation of the contiguity-specific half of the S4 gate: even when
        # range10/range10_p20 both happen to be non-null (satisfying the naive condition), S4 must
        # stay null if the 130-bar window itself is not contiguous (span130 != 130).
        hist = {"med20": 1.0, "high60": 10.0, "high20": 10.0, "prev_close": 10.0, "prev5_close": 10.0,
                "range10": 0.01, "range10_p20": 0.05, "span130": 131}  # gapped: not exactly 130
        obs = {"raw_close": 11.0, "raw_open": 10.5, "raw_high": 11.0, "raw_low": 10.9, "raw_volume": 1.0}
        signals = m.compute_signals(obs, hist, 1.0)
        self.assertNotIn("S4_contraction_breakout", signals["flags"])
        self.assertNotIn("S4_contraction_breakout", signals["flags_evaluated"])


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

    def test_public_symbol_row_publishes_possible_corporate_action_flag(self):
        # Opus major #5: possible_corporate_action was computed but never reached the public
        # artifact, so a split-driven fake mover could head top_50_losers/gainers unflagged.
        rows = {"AAA": {"observation_class": "today_session", "pct_change": -50.0, "dollar_volume": 1_000_000}}
        eligibility = {"AAA": {"eligible": True, "ambiguous_suffix_flag": False,
                               "signals": {"flags": {}, "possible_corporate_action": True,
                                           "flags_null_reason": "adjustment_basis_unverified"}}}
        lists = m.build_lists(rows, eligibility, [])
        public_row = m.public_symbol_row("AAA", rows, eligibility, lists)
        self.assertTrue(public_row["possible_corporate_action"])
        # The symbol is still kept in the lists (marked, not excluded) per the coordinator's design.
        self.assertIn("top_50_losers", public_row["list_membership"])

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

    def test_assemble_public_hides_full_news_url_even_when_it_slugs_the_headline(self):
        # Opus major #3 reproduction: the OLD code published n["url"] verbatim, which defeats the
        # headline hash whenever the provider url carries the headline as a slug (real providers
        # like Benzinga do this). Only the host and a sha256 of the FULL url may reach the public
        # artifact; the fixture's slug words must never appear in the public blob.
        headline = "Meta Platforms Shares Jump After AI Deal"
        url = "https://www.benzinga.com/news/26/09/48372910/meta-platforms-shares-jump-after-ai-deal"
        raw = {"id": 42, "headline": headline, "symbols": ["META"], "source": "benzinga", "url": url,
               "created_at": "2026-09-21T19:00:00Z", "updated_at": "2026-09-21T19:05:00Z"}
        normalized = m.normalize_news_row(raw, datetime(2026, 9, 21, 20, 0, tzinfo=timezone.utc), {"META"})
        # Private artifact retains the full url for operator use.
        self.assertEqual(normalized["url"], url)
        self.assertEqual(normalized["url_host"], "www.benzinga.com")
        self.assertEqual(len(normalized["url_sha256"]), 64)

        session_info = {"run_time_utc": "2026-09-21T20:00:00Z", "run_time_et": "2026-09-21T16:00:00-04:00",
                        "session_state": "regular_open", "current_or_last_regular_session": "2026-09-21",
                        "previous_regular_session": "2026-09-18", "next_open": None, "next_close": None}
        lists = m.build_lists({}, {}, [])
        public = m.assemble_public(session_info, lists, {}, {}, {"scanned": 0}, {"history_used": False},
                                   [normalized], False, {}, {"total_requests": 1})
        blob = json.dumps(public)
        self.assertNotIn("meta-platforms-shares-jump", blob)
        self.assertNotIn("48372910", blob)
        self.assertNotIn(url, blob)
        self.assertIn("www.benzinga.com", blob)
        self.assertIn(normalized["url_sha256"], blob)


class NewsFetch(unittest.TestCase):
    @unittest.skipUnless(HAS_REQUESTS, "requires requests")
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


class CountsReconciliation(unittest.TestCase):
    def test_eligible_is_null_with_eligibility_unknown_count_when_history_not_used(self):
        # Opus minor #9: without --history (or with a not-adjacent dataset), counts.eligible must
        # be null ("not computed"), never 0 ("computed, nothing qualified").
        symbols = ["AAA", "BBB"]
        rows = {"AAA": {"observation_class": "today_session"}, "BBB": {"observation_class": "today_session"}}
        eligibility = {"AAA": {"eligible": None, "eligibility_status": "unknown_no_history"},
                       "BBB": {"eligible": None, "eligibility_status": "unknown_no_history"}}
        lists = m.build_lists(rows, eligibility, [])
        counts = m.build_counts(symbols, rows, eligibility, lists, {"history_used": False})
        self.assertIsNone(counts["eligible"])
        self.assertEqual(counts["eligibility_unknown"], 2)
        self.assertEqual(counts["scanned"], 2)

    def test_eligible_is_a_real_count_when_history_is_used_even_with_some_per_symbol_unknowns(self):
        # A global history_used=True/history_not_adjacent=False run still reports a real eligible
        # count, with per-symbol has_gap/history_stale outcomes folded into eligibility_unknown
        # rather than forcing the whole count to null.
        symbols = ["AAA", "GAPPY"]
        rows = {"AAA": {"observation_class": "today_session"}, "GAPPY": {"observation_class": "today_session"}}
        eligibility = {"AAA": {"eligible": True}, "GAPPY": {"eligible": None, "eligibility_status": "has_gap"}}
        history_status = {"history_used": True, "history_not_adjacent": False}
        lists = m.build_lists(rows, eligibility, [])
        counts = m.build_counts(symbols, rows, eligibility, lists, history_status)
        self.assertEqual(counts["eligible"], 1)
        self.assertEqual(counts["eligibility_unknown"], 1)


ENV_FILE_CONTENTS = "APCA_API_KEY_ID=testkey123\nAPCA_API_SECRET_KEY=testsecret456\n"


@unittest.skipUnless(HAS_REQUESTS, "requires requests")
class PrivateDirectoryCreation(unittest.TestCase):
    def test_run_creates_a_fresh_out_private_directory_before_the_ledger_is_opened(self):
        # Codex: "Create the private output directory before writing its ledger". Ledger.write()
        # appends via plain open(path, "a"), which raises FileNotFoundError on a directory that
        # does not exist yet; that used to happen on the very first ledger.write() call in run(),
        # before any output helper (write_json_file creates its own directory, but too late).
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, "creds.env")
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write(ENV_FILE_CONTENTS)

            def request(method, url, **kwargs):
                if url.endswith("/v2/clock"):
                    return http_response(clock_payload(True, "2026-09-22T13:30:00Z", "2026-09-21T20:00:00Z"))
                if url.endswith("/v2/calendar"):
                    return http_response(CALENDAR_WEEK)
                if url.endswith("/v2/assets"):
                    return http_response([{"class": "us_equity", "exchange": "NASDAQ", "symbol": "AAA",
                                            "status": "active", "tradable": True, "name": "AAA Inc"}])
                if url.endswith("/v2/stocks/snapshots"):
                    return http_response({"AAA": {"dailyBar": {"t": "2026-09-21T04:00:00Z", "o": 10, "h": 11,
                                                                 "l": 9, "c": 11, "v": 1000},
                                                    "prevDailyBar": {"t": "2026-09-18T04:00:00Z", "c": 10, "v": 900}}})
                if url.endswith("/movers"):
                    return http_response({"gainers": [], "losers": []})
                if url.endswith("/most-actives"):
                    return http_response({"most_actives": []})
                if url.endswith("/v1beta1/news"):
                    return http_response({"news": [], "next_page_token": None})
                raise AssertionError(f"unexpected url in test dispatcher: {url}")

            # A brand-new, not-yet-created nested directory for the private artifact/ledger.
            out_private = os.path.join(tmp, "fresh", "nested", "private.json")
            args = argparse.Namespace(
                env_file=env_path, assets_out=os.path.join(tmp, "assets.json"), history=None,
                pinned="", out_private=out_private, out_public=os.path.join(tmp, "public.json"),
                now="2026-09-21T15:00:00Z")

            with patch("requests.Session.request", side_effect=request):
                private, public = m.run(args)

            self.assertTrue(os.path.exists(out_private))
            self.assertTrue(os.path.exists(os.path.join(tmp, "fresh", "nested", "scan-ledger.jsonl")))
            self.assertIsNone(public["counts"]["eligible"])  # no --history was passed


if __name__ == "__main__":
    unittest.main()
