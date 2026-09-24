"""Synthetic fixtures for blueprints/us-equities/data-lake/backfill.py (evidence class: synthetic fixture; no network).

Every opener here is a local fake: the news fake serves day pages, the bars fake serves /v2/stocks/bars pages gzip-
encoded as the real host does when asked. Nothing reaches data.alpaca.markets.
"""
from __future__ import annotations

import contextlib
import fcntl
import gzip
import hashlib
import io
import itertools
import json
import math
import os
import string
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blueprints/us-equities/data-lake"))
import backfill as B  # noqa: E402

NAMING = "2026-09-21"
SYMBOLS = ["".join(p) for p in itertools.product("ABC", string.ascii_uppercase, string.ascii_uppercase)]
FEB = {**{s: 19 for s in SYMBOLS[:148]}, "DLST": 7, "META": 19}  # 150 symbols: two tasks; DLST delists in February
MAR = {"AAA": 22, "META": 22, "NEWL": 10}  # NEWL lists in March
BARS = {
    "AAA": ["2026-02-01T08:59:00Z",   # 03:59 EST on the first day: before the request window
            "2026-02-02T09:00:00Z",   # 04:00 EST: the first in-window minute
            "2026-02-02T14:30:00Z",
            "2026-02-03T00:59:00Z",   # 19:59 EST
            "2026-02-03T01:00:00Z",   # 20:00 EST inside the month: returned, quarantined
            "2026-02-03T08:59:00Z",   # 03:59 EST inside the month: returned, quarantined
            "2026-03-01T01:00:00Z",   # 20:00 EST on Feb 28: after February's end, before March's start
            "2026-03-09T12:00:00Z"],  # 08:00 EDT, after the 2026-03-08 DST change
    "DLST": ["2026-02-04T15:00:00Z", "2026-02-05T15:00:00Z"],
    "META": ["2026-02-10T15:00:00Z", "2026-02-11T15:00:00Z", "2026-02-12T15:00:00Z", "2026-03-10T13:30:00Z"],
    "NEWL": ["2026-03-31T23:59:00Z",   # 19:59 EDT on the last day: in window
             "2026-04-01T00:00:00Z"],  # 20:00 EDT on the last day: after the end bound
}


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class Response(io.BytesIO):
    def __init__(self, body=b"", headers=None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def forbidden(request, timeout):
    raise AssertionError(f"no request may be sent: {request.full_url}")


def ts(text):
    """RFC-3339 UTC text (up to nanoseconds) as a datetime truncated to microseconds."""
    head, _, fraction = text.rstrip("Z").partition(".")
    return datetime.fromisoformat(head + "+00:00") + timedelta(microseconds=int((fraction + "000000")[:6]) if fraction else 0)


class FakeBars:
    """Local stand-in for GET /v2/stocks/bars: bars sorted by symbol then time within the inclusive start/end,
    `per_page` bars a page with an opaque next_page_token, gzip-encoded when the request accepts it, except the pages
    keyed in `plain` by (first symbol, page_token), which are served identity-encoded."""

    def __init__(self, bars, per_page=2, plain=(), fail=None):
        self.bars, self.per_page, self.plain, self.fail = bars, per_page, set(plain), fail
        self.calls, self.sent = [], {}

    def __call__(self, request, timeout):
        url = urllib.parse.urlsplit(request.full_url)
        query = dict(urllib.parse.parse_qsl(url.query))
        self.calls.append({"host": url.netloc, "path": url.path, "query": query,
                           "accept": request.get_header("Accept-encoding")})
        if self.fail and self.fail(query):
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, None)
        low, high = ts(query["start"]), ts(query["end"])
        rows = [(s, t) for s in sorted(query["symbols"].split(",")) for t in sorted(self.bars.get(s, ()))
                if low <= ts(t) <= high]
        offset = int(query.get("page_token", "tok0")[3:])
        more = offset + self.per_page < len(rows)
        series = {}
        for symbol, t in rows[offset:offset + self.per_page]:
            series.setdefault(symbol, []).append({"t": t, "o": 1.5, "h": 1.5, "l": 1.5, "c": 1.5, "v": 100, "n": 1, "vw": 1.5})
        body = json.dumps({"bars": series, "next_page_token": f"tok{offset + self.per_page}" if more else None}).encode()
        gz = (request.get_header("Accept-encoding") == "gzip"
              and (query["symbols"].split(",")[0], query.get("page_token")) not in self.plain)
        wire = gzip.compress(body) if gz else body
        self.sent[(query["symbols"], query["start"], query.get("page_token"))] = wire
        return Response(wire, {"Content-Encoding": "gzip", "X-Ratelimit-Remaining": "9000"} if gz
                        else {"X-Ratelimit-Remaining": "8999"})


def make_universe(months, last_session="2026-03-31", naming=NAMING):
    rows = [(month, symbol, sessions) for month, members in months.items() for symbol, sessions in members.items()]
    return B.build_universe(rows, naming, {"last_session": last_session, "collection": "synthetic"})


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
    """news: record capture, kept exactly as its 2015-2026 archive was collected, now under a scope header."""

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

    def client(self, opener):
        clock = FakeClock()
        return B.Client({}, B.Bucket(60000, clock=clock, sleep=clock.sleep), opener=opener, sleep=clock.sleep)

    def test_days_are_paged_written_and_resumed(self):
        records = {"2026-09-01": [{"id": i} for i in range(5)], "2026-09-02": [], "2026-09-03": [{"id": 9}]}
        opener, calls = self.pages(records)
        client = self.client(opener)
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
            check = B.verify_dataset(root, "news")
            self.assertEqual((check["ok"], check["rows"], check["files"], check["problems"]), (True, 3, 3, 0))
            (root / "news/scope.json").unlink()  # the 2015-2026 archive's shape: record capture without a header
            check = B.verify_dataset(root, "news")
            self.assertEqual((check["ok"], check["scope_header"], check["problems"]), (True, False, 0))
            day1.write_bytes(gzip.compress(b'{"id":0}\n', mtime=0))
            self.assertEqual(B.verify_dataset(root, "news")["examples"],
                             [{"file": "2026/09/01.jsonl.gz", "problem": "sha256 differs from the manifest"}])

    def test_news_scope_header_and_changed_span_refused(self):
        opener, calls = self.pages({"2026-09-01": [{"id": 1}]})
        client = self.client(opener)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            B.run(client, "news", date(2026, 9, 1), date(2026, 9, 2), root, workers=1)
            header_path = root / "news/scope.json"
            header = json.loads(header_path.read_text())
            self.assertEqual(header_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(header["scope"], {
                "dataset": "news", "code_sha256": hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest(),
                "endpoint": "https://data.alpaca.markets/v1beta1/news",
                "fixed_params": {"limit": 50, "sort": "asc", "include_content": "true", "exclude_contentless": "false"},
                "span": {"start": "2026-09-01", "end": "2026-09-02"}, "symbols_sha256": None,
                "task": {"unit": "calendar day (UTC)"}, "capture": "records"})
            self.assertEqual(header["fingerprint"], canonical_sha(header["scope"]))
            before = calls["n"]
            with self.assertRaises(B.Refused) as caught:  # widening the span is a different scope
                B.run(client, "news", date(2026, 9, 1), date(2026, 9, 3), root, workers=1)
            self.assertIn("span: recorded=", str(caught.exception))
            self.assertIn("'2026-09-03'", str(caught.exception))
            with self.assertRaises(B.Refused):  # so is another code version
                B.run(client, "news", date(2026, 9, 1), date(2026, 9, 2), root, workers=1, code="0" * 64)
            self.assertEqual(calls["n"], before)

    def test_manifest_without_header_is_not_resumed(self):
        """The 2015-2026 news archive was collected before scope headers: it is never appended to."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "news").mkdir()
            (root / "news/manifest.jsonl").write_text('{"day": "2026-09-01", "records": 1}\n')
            with self.assertRaises(B.Refused) as caught:
                B.run(self.client(forbidden), "news", date(2026, 9, 1), date(2026, 9, 2), root, workers=1)
            self.assertIn("no scope header", str(caught.exception))
            self.assertEqual(sorted(p.name for p in (root / "news").iterdir()), ["manifest.jsonl"])  # left untouched

    def test_edited_header_is_refused(self):
        opener, _ = self.pages({})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            B.run(self.client(opener), "news", date(2026, 9, 1), date(2026, 9, 1), root, workers=1)
            path = root / "news/scope.json"
            header = json.loads(path.read_text())
            header["scope"]["span"]["end"] = "2026-09-30"  # the fingerprint no longer matches
            path.write_text(json.dumps(header))
            with self.assertRaises(B.Refused) as caught:
                B.run(self.client(forbidden), "news", date(2026, 9, 1), date(2026, 9, 30), root, workers=1)
            self.assertIn("does not hash to its recorded fingerprint", str(caught.exception))
            # unreadable, not an object, or a scope that is not an object (fingerprint matching): refused, not a traceback
            for garbage in ("[", "[]", json.dumps({"scope": "news", "fingerprint": canonical_sha("news")})):
                path.write_text(garbage)
                with self.subTest(garbage), self.assertRaises(B.Refused) as caught:
                    B.run(self.client(forbidden), "news", date(2026, 9, 1), date(2026, 9, 1), root, workers=1)
                self.assertIn("unreadable", str(caught.exception))

    def test_second_concurrent_run_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "news").mkdir()
            fd = os.open(root / "news/.lock", os.O_WRONLY | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(B.Refused) as caught:
                    B.run(self.client(forbidden), "news", date(2026, 9, 1), date(2026, 9, 1), root, workers=1)
                self.assertIn("another backfill run holds", str(caught.exception))
            finally:
                os.close(fd)

    def test_stop_file_drains_the_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stop = root / "STOP"
            stop.write_text("")
            out = B.run(self.client(forbidden), "news", date(2026, 9, 1), date(2026, 9, 3), root, workers=1, stop_file=stop)
            self.assertEqual((out["days"], out["stopped"], out["failed"]), (0, 3, []))

    def test_torn_manifest_line_refetches_that_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = Path(tmp) / "manifest.jsonl"
            m.write_text('{"day": "2026-09-01"}\n{"day": "2026-09-0')
            self.assertEqual(B.done_days(m), {"2026-09-01"})
            B.repair_manifest_tail(m)  # the next row starts on its own line
            self.assertTrue(m.read_text().endswith('{"day": "2026-09-0\n'))

    def test_rate_cap_leaves_headroom(self):
        """The cap is what refuses: at 6,000/min the same command passes it and fails on the missing files."""
        for dataset in ("news", "stock_bars_1min"):
            args = [dataset, "--env-file", "/nonexistent", "--out", "/nonexistent/lake", "--universe", "/nonexistent",
                    "--start", "2026-01-01", "--end", "2026-01-02", "--rate"]
            with self.subTest(dataset), self.assertRaises(SystemExit) as caught:
                B.main(args + ["6001"])
            self.assertIn("at most 6000/min", str(caught.exception))
            with self.subTest(dataset), self.assertRaises(FileNotFoundError):
                B.main(args + ["6000"])


class UniverseTests(unittest.TestCase):
    """The asof-aware monthly universe (built from the identity-deduplicated broad-universe daily dataset)."""

    def test_months_follow_daily_bars_for_active_delisted_and_new_symbols(self):
        # The daily dataset is already identity-deduplicated (coverage.dedupe_identity): FB's 2016 rows duplicated
        # META's and were removed, so a 2016 month asks for META, which asof=2026-09-21 maps to Facebook's history.
        rows = [("2016-01", "AAPL", 19), ("2016-01", "DLST", 12), ("2016-01", "META", 19),
                ("2016-02", "AAPL", 20), ("2016-02", "META", 20),                         # DLST's last bar: January
                ("2016-03", "AAPL", 22), ("2016-03", "META", 22), ("2016-03", "NEWL", 5)]  # NEWL lists in March
        u = B.build_universe(reversed(rows), NAMING, {"last_session": "2016-03-31"})
        self.assertEqual(u["months"], {"2016-01": {"AAPL": 19, "DLST": 12, "META": 19},
                                       "2016-02": {"AAPL": 20, "META": 20},
                                       "2016-03": {"AAPL": 22, "META": 22, "NEWL": 5}})
        self.assertEqual((u["naming_asof"], u["covers_through"], u["first_month"], u["last_month"]),
                         (NAMING, "2016-03-31", "2016-01", "2016-03"))
        self.assertEqual(u["summary"], {"months": 3, "symbols": 4, "symbol_months": 8, "symbol_sessions": 139,
                                        "tasks_at_batch_100": 3})

    def test_malformed_rows_are_refused(self):
        for row in [("2016-01", "BRK B", 1), ("2016-01", "A,B", 1), ("2016-01", "aapl", 1), ("2016-13", "AAPL", 1),
                    ("2016-01", "AAPL", 0), ("2016-01", "AAPL", True)]:
            with self.subTest(row), self.assertRaises(ValueError):
                B.build_universe([row], NAMING, {"last_session": "2016-01-29"})
        with self.assertRaises(ValueError):
            B.build_universe([("2016-01", "AAPL", 1), ("2016-01", "AAPL", 2)], NAMING, {"last_session": "2016-01-29"})

    def test_naming_date_comes_from_the_collection(self):
        default = {"asof": B.PROVIDER_DEFAULT_ASOF}
        stamps = ["2026-09-21T21:56:23.322211+00:00", "2026-09-21T22:57:36.227571+00:00"]
        self.assertEqual(B.collection_naming_date([default, default], stamps), "2026-09-21")
        with self.assertRaises(ValueError):  # 03:30 UTC on 09-22 is 23:30 on 09-21 in New York: ambiguous
            B.collection_naming_date([default], stamps + ["2026-09-22T03:30:00+00:00"])
        self.assertEqual(B.collection_naming_date([{"asof": "2026-09-18"}], []), "2026-09-18")
        for plans in ([{"asof": "2026-09-18"}, default], [{}]):
            with self.subTest(plans), self.assertRaises(ValueError):
                B.collection_naming_date(plans, stamps)

    def test_universe_file_round_trip_and_malformed_file(self):
        u = make_universe({"2026-02": FEB, "2026-03": MAR})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "universe.json"
            payload = B.canonical(u) + b"\n"
            path.write_bytes(payload)
            loaded = B.load_universe(path)
            self.assertEqual((loaded["months"], loaded["file_sha256"]), (u["months"], hashlib.sha256(payload).hexdigest()))
            for broken in ({**u, "schema": "other"}, {**u, "months": {"2026-02": {"aaa": 1}}},
                           {**u, "naming_asof": "soon"}, [u]):
                with self.subTest(str(broken)[:40]), self.assertRaises(ValueError):
                    path.write_text(json.dumps(broken))
                    B.load_universe(path)

    def test_tasks_are_100_symbol_months_with_dst_aware_windows(self):
        u = make_universe({"2026-02": FEB, "2026-03": MAR})
        tasks = B.plan_month_tasks(u, date(2026, 2, 15), date(2026, 3, 31), 100)
        feb = sorted(FEB)
        self.assertEqual([t["task"] for t in tasks], ["2026-02-b0000", "2026-02-b0001", "2026-03-b0000"])
        self.assertEqual([t["symbols"] for t in tasks], [feb[:100], feb[100:], ["AAA", "META", "NEWL"]])
        self.assertEqual([t["symbol_sessions"] for t in tasks], [1900, 19 * 48 + 7 + 19, 54])
        # the span clips February's start; 04:00 EST = 09:00Z, 19:59:59.999999999 EST ends after UTC midnight
        self.assertEqual((tasks[0]["start"], tasks[0]["end"]), ("2026-02-15T09:00:00Z", "2026-03-01T00:59:59.999999999Z"))
        # March starts on EST and ends on EDT (DST began 2026-03-08)
        self.assertEqual((tasks[2]["start"], tasks[2]["end"]), ("2026-03-01T09:00:00Z", "2026-03-31T23:59:59.999999999Z"))

    def test_span_the_universe_does_not_cover_is_refused(self):
        u = make_universe({"2026-02": FEB, "2026-03": MAR})
        with self.assertRaises(B.Refused):  # a symbol listed after the universe's last session would be missed
            B.plan_month_tasks(u, date(2026, 3, 1), date(2026, 4, 1), 100)
        with self.assertRaises(B.Refused):
            B.plan_month_tasks(make_universe({"2026-03": MAR}), date(2026, 2, 1), date(2026, 3, 31), 100)

    def test_session_window_is_new_york_04_to_20(self):
        for t, outside in [("2026-02-03T00:59:00Z", False), ("2026-02-03T01:00:00Z", True),   # 19:59 / 20:00 EST
                           ("2026-02-03T08:59:00Z", True), ("2026-02-03T09:00:00Z", False),   # 03:59 / 04:00 EST
                           ("2026-07-01T07:59:00Z", True), ("2026-07-01T08:00:00Z", False),   # 03:59 / 04:00 EDT
                           ("2026-07-01T23:59:00Z", False), ("2026-07-02T00:00:00Z", True)]:  # 19:59 / 20:00 EDT
            with self.subTest(t):
                self.assertEqual(B.outside_session_window(t), outside)


class BarsCase(unittest.TestCase):
    START, END = date(2026, 2, 1), date(2026, 3, 31)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ds = self.root / "stock_bars_1min"
        self.clock = FakeClock()
        self.universe = make_universe({"2026-02": FEB, "2026-03": MAR})

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, opener):
        return B.Client({}, B.Bucket(60000, clock=self.clock, sleep=self.clock.sleep), opener=opener, sleep=self.clock.sleep)

    def run_bars(self, opener, pilot=0, free=10 ** 12, **kwargs):
        options = dict(universe=self.universe, pilot=pilot, disk_free=lambda path: free,
                       peak_rss=lambda: 64 * 2 ** 20, rate=6000)
        options.update(kwargs)
        start, end = options.pop("start", self.START), options.pop("end", self.END)
        return B.run(self.client(opener), "stock_bars_1min", start, end, self.root, 1, **options)

    def rows(self):
        return {row["task"]: row for row in map(json.loads, (self.ds / "manifest.jsonl").read_text().splitlines())}


class PageCaptureTests(BarsCase):
    def test_pages_are_stored_as_received_with_params_hashes_and_quarantine(self):
        fake = FakeBars(BARS, plain={(SYMBOLS[100], "tok2")})
        out = self.run_bars(fake, pilot=3)  # a pilot over every planned task
        self.assertEqual((out["tasks"], out["pages"], out["bars"], out["quarantined"], out["failed"]), (3, 8, 13, 2, []))
        self.assertEqual((out["pilot"]["verdict"], out["ratelimit_remaining_min"]), ("pass", 8999))
        for call in fake.calls:
            self.assertEqual((call["host"], call["path"], call["accept"]), ("data.alpaca.markets", "/v2/stocks/bars", "gzip"))
        rows = self.rows()
        feb = sorted(FEB)
        base = {"timeframe": "1Min", "feed": "sip", "adjustment": "raw", "limit": 10000, "sort": "asc", "asof": NAMING}
        self.assertEqual(rows["2026-02-b0000"]["params"], {**base, "symbols": ",".join(feb[:100]),
                         "start": "2026-02-01T09:00:00Z", "end": "2026-03-01T00:59:59.999999999Z"})
        self.assertEqual(rows["2026-03-b0000"]["params"], {**base, "symbols": "AAA,META,NEWL",
                         "start": "2026-03-01T09:00:00Z", "end": "2026-03-31T23:59:59.999999999Z"})
        self.assertEqual({t: (len(r["pages"]), r["bars"]) for t, r in rows.items()},
                         {"2026-02-b0000": (3, 5), "2026-02-b0001": (3, 5), "2026-03-b0000": (2, 3)})
        encodings = []
        for task, row in rows.items():
            self.assertEqual(row["symbols_sha256"], hashlib.sha256(row["params"]["symbols"].encode()).hexdigest())
            self.assertEqual([p["page_token"] for p in row["pages"]], [None] + [f"tok{2 * i}" for i in range(1, len(row["pages"]))])
            self.assertEqual([p["next_page_token"] for p in row["pages"]], [True] * (len(row["pages"]) - 1) + [False])
            for page in row["pages"]:
                path = self.ds / page["file"]
                stored = path.read_bytes()
                sent = fake.sent[(row["params"]["symbols"], row["params"]["start"], page["page_token"])]
                encodings.append(page["content_encoding"])
                # a gzip page is kept byte for byte as the wire delivered it; an identity page is gzip-wrapped
                self.assertEqual(stored if page["content_encoding"] == "gzip" else gzip.decompress(stored), sent)
                self.assertEqual((len(stored), hashlib.sha256(stored).hexdigest()), (page["bytes"], page["sha256"]))
                decoded = gzip.decompress(stored)
                self.assertEqual((len(decoded), hashlib.sha256(decoded).hexdigest()), (page["json_bytes"], page["json_sha256"]))
                self.assertEqual(sum(map(len, json.loads(decoded)["bars"].values())), page["bars"])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(encodings), ["gzip"] * 7 + ["identity"])
        self.assertEqual(rows["2026-02-b0000"]["quarantine"], [{"page": 1, "symbol": "AAA", "t": "2026-02-03T01:00:00Z"},
                                                               {"page": 2, "symbol": "AAA", "t": "2026-02-03T08:59:00Z"}])
        self.assertEqual([r["unexpected_symbols"] for r in rows.values()], [[], [], []])
        self.assertEqual(list(self.ds.rglob("*.part")), [])
        check = B.verify_dataset(self.root, "stock_bars_1min")
        self.assertEqual((check["ok"], check["rows"], check["files"], check["problems"]), (True, 3, 8, 0))
        victim = self.ds / rows["2026-03-b0000"]["pages"][1]["file"]
        victim.write_bytes(gzip.compress(b'{"bars":{},"next_page_token":null}'))
        self.assertEqual(B.verify_dataset(self.root, "stock_bars_1min")["examples"],
                         [{"file": "2026/03/b0000/p00001.json.gz", "problem": "sha256 differs from the manifest"}])

    def test_failed_task_is_not_recorded_and_is_fetched_again_cleanly(self):
        broken = FakeBars(BARS, fail=lambda q: q["symbols"].startswith(SYMBOLS[100] + ",") and q.get("page_token") == "tok2")
        out = self.run_bars(broken, pilot=3)
        self.assertEqual([f["task"] for f in out["failed"]], ["2026-02-b0001"])
        self.assertIn("HTTPError", out["failed"][0]["error"])
        self.assertEqual(out["pilot"]["verdict"], "incomplete")
        self.assertEqual(sorted(self.rows()), ["2026-02-b0000", "2026-03-b0000"])
        self.assertTrue((self.ds / "2026/02/b0001.part/p00000.json.gz").exists())  # the attempt's first page only
        healthy = FakeBars(BARS)
        again = self.run_bars(healthy, pilot=3)
        self.assertEqual((again["tasks"], again["skipped_already_done"], again["pilot"]["verdict"]), (1, 2, "pass"))
        self.assertEqual({c["query"]["symbols"].split(",")[0] for c in healthy.calls}, {SYMBOLS[100]})
        self.assertEqual(list(self.ds.rglob("*.part")), [])
        self.assertTrue(B.verify_dataset(self.root, "stock_bars_1min")["ok"])


class ScopeTests(BarsCase):
    def test_header_records_code_endpoint_params_symbols_and_span(self):
        self.run_bars(FakeBars(BARS), pilot=3)
        header = json.loads((self.ds / "scope.json").read_text())
        tasks = B.plan_month_tasks(self.universe, self.START, self.END, 100)
        self.assertEqual(header["scope"], {
            "dataset": "stock_bars_1min", "code_sha256": hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest(),
            "endpoint": "https://data.alpaca.markets/v2/stocks/bars",
            "fixed_params": {"timeframe": "1Min", "feed": "sip", "adjustment": "raw", "limit": 10000, "sort": "asc",
                             "asof": NAMING},
            "symbols_sha256": canonical_sha([[t["task"], t["symbols"]] for t in tasks]),
            "span": {"start": "2026-02-01", "end": "2026-03-31"},
            "task": {"unit": "symbols x calendar month", "batch_size": 100, "window_et": ["04:00", "19:59:59.999999999"]},
            "capture": "pages"})
        self.assertEqual(header["fingerprint"], canonical_sha(header["scope"]))
        self.assertEqual(header["provenance"]["universe"]["naming_asof"], NAMING)
        self.assertEqual({row["scope_fingerprint"] for row in self.rows().values()}, {header["fingerprint"]})
        self.assertEqual(B.verify_dataset(self.root, "stock_bars_1min")["scope_fingerprint"], header["fingerprint"])

    def test_rows_naming_another_scope_are_fetched_again_and_flagged(self):
        fake = FakeBars(BARS)
        self.run_bars(fake, pilot=3)
        manifest = self.ds / "manifest.jsonl"
        rows = [json.loads(line) for line in manifest.read_text().splitlines()]
        for row in rows:
            if row["task"] == "2026-03-b0000":
                row["scope_fingerprint"] = "0" * 64
        manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        check = B.verify_dataset(self.root, "stock_bars_1min")
        self.assertEqual((check["ok"], check["examples"]), (False, [
            {"task": "2026-03-b0000", "problem": "row names another scope fingerprint than the header"}]))
        sent = len(fake.calls)
        again = self.run_bars(fake, pilot=3)  # that row does not count as done under the header's scope
        self.assertEqual((again["tasks"], again["skipped_already_done"]), (1, 2))
        self.assertEqual({call["query"]["symbols"] for call in fake.calls[sent:]}, {"AAA,META,NEWL"})

    def test_verify_checks_the_scope_header(self):
        self.run_bars(FakeBars(BARS), pilot=3)
        path = self.ds / "scope.json"
        path.write_text(path.read_text().replace('"sip"', '"iex"'))  # edited: no longer hashes to its fingerprint
        self.assertEqual(B.verify_dataset(self.root, "stock_bars_1min")["examples"],
                         [{"file": "scope.json", "problem": "unreadable or does not hash to its recorded fingerprint"}])
        path.unlink()  # a page-capture dataset is always collected under a header
        check = B.verify_dataset(self.root, "stock_bars_1min")
        self.assertEqual((check["ok"], check["examples"]), (False, [{"file": "scope.json", "problem": "missing"}]))

    def test_changed_scope_refuses_to_resume(self):
        fake = FakeBars(BARS)
        self.run_bars(fake, pilot=3)
        sent = len(fake.calls)
        changes = {
            "span": dict(end=date(2026, 3, 30)),
            "code": dict(code="0" * 64),
            "universe symbols": dict(universe=make_universe({"2026-02": {**FEB, "ZZZ": 3}, "2026-03": MAR})),
            "universe naming date": dict(universe=make_universe({"2026-02": FEB, "2026-03": MAR}, naming="2026-09-22")),
        }
        for label, change in changes.items():
            with self.subTest(label), self.assertRaises(B.Refused) as caught:
                self.run_bars(fake, pilot=3, **change)
            self.assertIn("different scope", str(caught.exception))
        self.assertEqual(len(fake.calls), sent)  # nothing was requested for a refused scope
        again = self.run_bars(fake, pilot=3)  # the recorded scope still resumes
        self.assertEqual((again["tasks"], again["skipped_already_done"], len(fake.calls)), (0, 3, sent))

    def test_cli_refusals_exit_2_before_any_request(self):
        env = self.root / "paper.env"
        env.write_text("APCA_API_KEY_ID=SYNTHETIC\nAPCA_API_SECRET_KEY=SYNTHETIC\n")
        env.chmod(0o600)
        universe = self.root / "universe.json"
        universe.write_bytes(B.canonical(self.universe) + b"\n")
        common = ["--env-file", str(env), "--out", str(self.root), "--universe", str(universe)]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):  # a full run without a pilot
            code = B.main(["stock_bars_1min", *common, "--start", "2026-02-01", "--end", "2026-03-31"], opener=forbidden)
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", stderr.getvalue())
        self.assertIn("has no pilot", stderr.getvalue())
        with contextlib.redirect_stderr(io.StringIO()) as stderr:  # the header now holds March 31: a changed span
            code = B.main(["stock_bars_1min", *common, "--start", "2026-02-01", "--end", "2026-03-30", "--pilot", "2"],
                          opener=forbidden)
        self.assertEqual(code, 2)
        self.assertIn("different scope", stderr.getvalue())


class PilotTests(BarsCase):
    def setUp(self):
        super().setUp()
        members = SYMBOLS[:300]
        self.universe = make_universe({"2026-02": dict.fromkeys(members, 19), "2026-03": dict.fromkeys(members, 22)})
        self.bars = {s: [f"2026-02-{10 + k:02d}T15:00:00Z" for k in range(1 + i % 3)]
                     + [f"2026-03-{10 + k:02d}T14:00:00Z" for k in range(1 + i % 2)] for i, s in enumerate(members)}

    def test_pilot_fetches_spread_tasks_reports_and_projects_disk(self):
        fake = FakeBars(self.bars, per_page=40)
        out = self.run_bars(fake, pilot=2)
        report = json.loads((self.ds / "pilot.json").read_text())
        self.assertEqual(report, out["pilot"])
        self.assertEqual(report["pilot_tasks"], ["2026-02-b0001", "2026-03-b0001"])  # tasks 1 and 4 of 6
        self.assertEqual({(c["query"]["symbols"].split(",")[0], c["query"]["start"]) for c in fake.calls},
                         {(SYMBOLS[100], "2026-02-01T09:00:00Z"), (SYMBOLS[100], "2026-03-01T09:00:00Z")})
        rows = self.rows()
        self.assertEqual(sorted(rows), report["pilot_tasks"])
        pages = [p for r in rows.values() for p in r["pages"]]
        bars = sum(r["bars"] for r in rows.values())
        raw = sum(p["bytes"] for p in pages)
        disk = (sum(max(os.stat(self.ds / p["file"]).st_size, os.stat(self.ds / p["file"]).st_blocks * 512) for p in pages)
                + sum(len(json.dumps(r, sort_keys=True)) + 1 for r in rows.values()))
        m = report["metrics"]
        self.assertEqual((m["tasks"], m["pages"], m["bars"], m["raw_bytes"], m["disk_bytes"]), (2, len(pages), bars, raw, disk))
        self.assertEqual((m["raw_bytes_per_page"], m["raw_bytes_per_bar"], m["disk_bytes_per_bar"]),
                         (round(raw / len(pages), 3), round(raw / bars, 3), round(disk / bars, 3)))
        self.assertEqual((m["peak_rss_bytes"], m["peak_rss_mib"]), (64 * 2 ** 20, 64.0))
        p = report["projection"]
        sessions_pilot, sessions_total = 100 * 19 + 100 * 22, 300 * 19 + 300 * 22
        projected_bars = bars / sessions_pilot * sessions_total
        self.assertEqual((p["planned_tasks"], p["symbol_sessions_pilot"], p["symbol_sessions_total"]),
                         (6, sessions_pilot, sessions_total))
        self.assertEqual(p["projected_disk_bytes"], math.ceil(max(projected_bars * disk / bars, disk / 2 * 6)))
        self.assertEqual((p["free_disk_bytes"], p["threshold_bytes"]), (10 ** 12, int(0.4 * 10 ** 12)))
        self.assertEqual(p["projected_calls_upper"], math.ceil(projected_bars / 10000) + 6)
        self.assertEqual(report["verdict"], "pass")
        # the synthetic pages hold 40 of the 10,000 bars a page may carry: D2's per-day overturn flag is raised
        self.assertTrue(report["flags"]["pages_under_95pct_full"])

    def test_pilot_refuses_above_40_percent_of_free_disk_and_gates_the_full_run(self):
        fake = FakeBars(self.bars, per_page=40)
        with self.assertRaises(B.Refused) as caught:  # no pilot yet
            self.run_bars(fake)
        self.assertIn("has no pilot", str(caught.exception))
        projected = self.run_bars(fake, pilot=2)["pilot"]["projection"]["projected_disk_bytes"]
        tight = self.run_bars(fake, pilot=2, free=projected * 2)  # 40% of twice the projection is too little
        self.assertEqual((tight["pilot"]["verdict"], tight["pilot"]["metrics"]["fetched_in_this_run"]), ("refused", 0))
        self.assertIn("exceed 40% of free disk", tight["pilot"]["reason"])
        with self.assertRaises(B.Refused) as caught:
            self.run_bars(fake, free=10 ** 12)
        self.assertIn("verdict is 'refused'", str(caught.exception))
        self.run_bars(fake, pilot=2, free=projected * 3)  # 40% of three times the projection fits: pass
        with self.assertRaises(B.Refused) as caught:  # free space shrank since the pilot
            self.run_bars(fake, free=projected)
        self.assertIn("bytes free now", str(caught.exception))
        before = len(fake.calls)
        full = self.run_bars(fake, free=10 ** 12)
        self.assertEqual((full["tasks"], full["skipped_already_done"], full["failed"]), (4, 2, []))
        self.assertEqual(len(fake.calls) - before, full["pages"])  # one request per page of the four remaining tasks
        self.assertTrue(B.verify_dataset(self.root, "stock_bars_1min")["ok"])

    def test_pilot_is_a_bounded_sample(self):
        """A pilot runs before any disk gate, so an oversized one would fetch the whole span ungated."""
        with self.assertRaises(B.Refused) as caught:
            self.run_bars(forbidden, pilot=B.MAX_PILOT_TASKS + 1)
        self.assertIn(f"at most {B.MAX_PILOT_TASKS} tasks", str(caught.exception))
        self.assertFalse(self.ds.exists())  # refused before the header, the lock or any request
        with self.assertRaises(SystemExit) as caught:  # a missing universe file would raise FileNotFoundError instead
            B.main(["stock_bars_1min", "--env-file", "/nonexistent", "--out", str(self.root), "--universe",
                    "/nonexistent", "--start", "2026-02-01", "--end", "2026-03-31", "--pilot", str(B.MAX_PILOT_TASKS + 1)])
        self.assertIn(f"--pilot between 0 and {B.MAX_PILOT_TASKS}", str(caught.exception))

    def test_unreadable_pilot_report_refuses_the_full_run(self):
        self.run_bars(FakeBars(self.bars, per_page=40), pilot=2)
        (self.ds / "pilot.json").write_text("{")
        with self.assertRaises(B.Refused) as caught:
            self.run_bars(forbidden)
        self.assertIn("unreadable", str(caught.exception))

    def test_pilot_without_bars_refuses(self):
        out = self.run_bars(FakeBars({}), pilot=2)
        self.assertEqual(out["pilot"]["verdict"], "refused")
        self.assertIn("no bars", out["pilot"]["reason"])


if __name__ == "__main__":
    unittest.main()
