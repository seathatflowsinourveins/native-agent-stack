"""Synthetic fixtures for blueprints/us-equities/data-lake/backfill.py (local integration; no network)."""
from __future__ import annotations

import gzip
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blueprints/us-equities/data-lake"))
import backfill as B  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class BucketTests(unittest.TestCase):
    def test_rate_is_spread_and_pauses_hold(self):
        clock = FakeClock()
        bucket = B.Bucket(600, clock=clock, sleep=clock.sleep)  # one per 0.1 s
        for _ in range(10):
            bucket.acquire()
        self.assertAlmostEqual(clock.t, 0.9)
        bucket.pause(5)
        bucket.acquire()
        self.assertAlmostEqual(clock.t, 5.9)


class BackfillTests(unittest.TestCase):
    def pages(self, day_records):
        """A fake opener serving `day_records[start_day]` in pages of two, with one 429 first."""
        calls = {"n": 0, "throttled": False}

        def opener(request, timeout):
            calls["n"] += 1
            if not calls["throttled"]:
                calls["throttled"] = True
                raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {"X-Ratelimit-Reset": "0"}, None)
            q = dict(p.split("=", 1) for p in request.full_url.split("?", 1)[1].split("&"))
            day = q["start"][:10]
            offset = int(q.get("page_token", "0"))
            rows = day_records.get(day, [])[offset:offset + 2]
            token = str(offset + 2) if offset + 2 < len(day_records.get(day, [])) else None
            return Response(json.dumps({"news": rows, "next_page_token": token}).encode())
        return opener, calls

    def test_days_are_paged_written_and_resumed(self):
        records = {"2026-09-01": [{"id": i} for i in range(5)], "2026-09-02": [], "2026-09-03": [{"id": 9}]}
        opener, calls = self.pages(records)
        clock = FakeClock()
        client = B.Client({}, B.Bucket(60000, clock=clock, sleep=clock.sleep), opener=opener, sleep=clock.sleep)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = B.run(client, "news", date(2026, 9, 1), date(2026, 9, 3), root, workers=1)
            self.assertEqual((out["days"], out["records"], out["failed"], out["throttled"]), (3, 6, [], 1))
            day1 = root / "news/2026/09/01.jsonl.gz"
            self.assertEqual([json.loads(l)["id"] for l in gzip.decompress(day1.read_bytes()).decode().splitlines()], [0, 1, 2, 3, 4])
            self.assertEqual(day1.stat().st_mode & 0o777, 0o600)
            manifest = [json.loads(l) for l in (root / "news/manifest.jsonl").read_text().splitlines()]
            self.assertEqual(sorted((m["day"], m["records"], m["pages"]) for m in manifest),
                             [("2026-09-01", 5, 3), ("2026-09-02", 0, 1), ("2026-09-03", 1, 1)])
            before = calls["n"]
            again = B.run(client, "news", date(2026, 9, 1), date(2026, 9, 3), root, workers=1)
            self.assertEqual((again["days"], again["skipped_already_done"], calls["n"]), (0, 3, before))

    def test_torn_manifest_line_refetches_that_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Path(tmp) / "manifest.jsonl"
            m.write_text('{"day": "2026-09-01"}\n{"day": "2026-09-0')
            self.assertEqual(B.done_days(m), {"2026-09-01"})

    def test_rate_cap_leaves_headroom(self):
        with self.assertRaises(SystemExit):
            B.main(["news", "--env-file", "/nonexistent", "--out", "/tmp/x", "--start", "2026-01-01", "--end", "2026-01-02", "--rate", "9000"])


if __name__ == "__main__":
    unittest.main()
