import csv
import hashlib
import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ingest_snapshot", ROOT / "blueprints/us-equities/data/ingest_snapshot.py")
ingest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ingest)


def bar(day, close, volume=1000.0):
    # 04:00 UTC is midnight New York (EDT): the bar's session is that date.
    return {"timestamp": datetime(2026, 9, day, 4, 0, tzinfo=timezone.utc),
            "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": volume}


class IngestSnapshotRows(unittest.TestCase):
    def test_keeps_the_last_sessions_per_symbol_sorted(self):
        rows = ingest.rows_from_bars({"SPY": [bar(22, 3), bar(18, 1), bar(21, 2)], "AMD": [bar(22, 9)]},
                                     2, "2026-09-22T22:00:00Z")
        self.assertEqual([(r["symbol"], r["session"]) for r in rows],
                         [("AMD", "2026-09-22"), ("SPY", "2026-09-21"), ("SPY", "2026-09-22")])
        self.assertEqual(rows[0]["volume"], "1000")
        self.assertTrue(all(r["observed_at"] == "2026-09-22T22:00:00Z" for r in rows))

    def test_session_is_the_new_york_date(self):
        late = {"timestamp": datetime(2026, 9, 23, 3, 30, tzinfo=timezone.utc),
                "open": 1, "high": 2, "low": 1, "close": 2, "volume": 5}
        self.assertEqual(ingest.rows_from_bars({"SPY": [late]}, 5, "x")[0]["session"], "2026-09-22")

    def test_non_integral_volume_is_refused(self):
        with self.assertRaisesRegex(ValueError, "non_integral_volume:SPY"):
            ingest.rows_from_bars({"SPY": [bar(22, 1, volume=10.5)]}, 5, "x")

    def test_csv_matches_the_promotion_gate_columns_and_hash(self):
        rows = ingest.rows_from_bars({"SPY": [bar(22, 3)]}, 5, "2026-09-22T22:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.csv"
            sha, size = ingest.write_csv(rows, path)
            self.assertEqual(sha, hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(size, path.stat().st_size)
            with open(path, newline="") as handle:
                self.assertEqual(tuple(next(csv.reader(handle))), ingest.COLUMNS)
            fixture = ROOT / "blueprints/us-equities/data/fixtures/good.csv"
            self.assertEqual(fixture.read_text().splitlines()[0], ",".join(ingest.COLUMNS))


class IngestSnapshotCompleteness(unittest.TestCase):
    # 2026-09-22 is a Tuesday trading day; 2026-09-21 the prior session.
    def _bar(self, y, m, d):
        return {"timestamp": datetime(y, m, d, 4, 0, tzinfo=timezone.utc), "open": 1, "high": 2, "low": 1,
                "close": 2, "volume": 5}

    def test_todays_bar_is_completed_only_from_17_00_new_york(self):
        bars = {"SPY": [self._bar(2026, 9, 21), self._bar(2026, 9, 22)]}
        before = datetime(2026, 9, 22, 20, 59, tzinfo=timezone.utc)   # 16:59 EDT
        after = datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc)     # 17:00 EDT
        self.assertEqual(len(ingest.completed_bars(bars, before)["SPY"]), 1)
        self.assertEqual(len(ingest.completed_bars(bars, after)["SPY"]), 2)

    def test_expected_latest_session_uses_the_trading_calendar(self):
        trading = lambda d: d.weekday() < 5
        prev = lambda d: d - timedelta(days=3 if d.weekday() == 0 else 1)
        self.assertEqual(ingest.expected_latest_session(datetime(2026, 9, 23, 14, 5, tzinfo=timezone.utc), trading, prev),
                         date(2026, 9, 22))
        self.assertEqual(ingest.expected_latest_session(datetime(2026, 9, 22, 22, 0, tzinfo=timezone.utc), trading, prev),
                         date(2026, 9, 22))
        self.assertEqual(ingest.expected_latest_session(datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc), trading, prev),
                         date(2026, 9, 25))

    def test_stale_truncated_or_empty_symbols_are_reported(self):
        full = [self._bar(2026, 9, 21), self._bar(2026, 9, 22)]
        problems = ingest.coverage_problems({"SPY": full, "AMD": full[:1], "ASTS": [], "META": full},
                                            2, date(2026, 9, 22))
        self.assertEqual(problems, {"AMD": "latest_session_2026-09-21_expected_2026-09-22",
                                    "ASTS": "no_completed_bars"})
        self.assertEqual(ingest.coverage_problems({"SPY": full}, 3, date(2026, 9, 22)),
                         {"SPY": "only_2_of_3_sessions"})

    def test_expected_latest_session_with_the_engine_calendar_skips_holidays(self):
        import sys
        sys.path.insert(0, str(ROOT / "blueprints/us-equities/adaptive-paper"))
        from sessions import _is_trading_day, previous_trading_day
        # Friday 2026-11-27 09:00 ET: Thanksgiving (Thu 2026-11-26) is closed, so the
        # latest completed session is Wed 2026-11-25.
        now = datetime(2026, 11, 27, 14, 0, tzinfo=timezone.utc)
        self.assertEqual(ingest.expected_latest_session(now, _is_trading_day, previous_trading_day), date(2026, 11, 25))
        # Monday 2026-09-07 is Labor Day; Tuesday morning expects Friday 2026-09-04.
        now = datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc)
        self.assertEqual(ingest.expected_latest_session(now, _is_trading_day, previous_trading_day), date(2026, 9, 4))

    def test_non_positive_sessions_is_refused(self):
        with self.assertRaises(SystemExit):
            ingest.main(["--env-file", "x", "--out", "o.csv", "--receipt", "r.json", "--sessions", "0"])


if __name__ == "__main__":
    unittest.main()
