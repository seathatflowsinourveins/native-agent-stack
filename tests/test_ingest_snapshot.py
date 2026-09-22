import csv
import hashlib
import importlib.util
from datetime import datetime, timezone
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


if __name__ == "__main__":
    unittest.main()
