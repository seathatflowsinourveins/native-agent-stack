"""Synthetic fixtures for blueprints/us-equities/data-lake/backfill.py (evidence class: synthetic fixture; no network).

Every opener here is a local fake: the news fake serves day pages, the bars fake serves /v2/stocks/bars pages gzip-
encoded as the real host does when asked. The redirect tests patch urllib's HTTPS and HTTP handlers at class level, so
even the production opener never opens a socket. Nothing reaches data.alpaca.markets. The host-wide lease and the disk
floor are patched for the whole module: no test touches ~/.local/state or depends on this host's free disk.
"""
from __future__ import annotations

import contextlib
import errno
import fcntl
import gc
import gzip
import hashlib
import http.client
import importlib.util
import io
import itertools
import json
import math
import os
import shutil
import string
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
import weakref
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

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
URL = "https://data.alpaca.markets/v2/stocks/bars"


def setUpModule():
    lease_dir = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(lease_dir.cleanup)
    for name, value in (("HOST_LEASE", Path(lease_dir.name) / "state/backfill.lock"), ("DISK_FLOOR", 0)):
        patcher = mock.patch.object(B, name, value, create=True)
        patcher.start()
        unittest.addModuleCleanup(patcher.stop)


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
    `per_page` bars a page (None: the request's limit) with an opaque next_page_token, gzip-encoded when the request
    accepts it, except the pages keyed in `plain` by (first symbol, page_token), which are served identity-encoded.
    `transient` maps (first symbol, page_token) to HTTP codes answered, in order, before that page is served."""

    def __init__(self, bars, per_page=2, plain=(), fail=None, on_call=None, price=1.5, transient=None):
        self.bars, self.per_page, self.plain, self.fail, self.on_call = bars, per_page, set(plain), fail, on_call
        self.price, self.transient = price, {key: list(codes) for key, codes in (transient or {}).items()}
        self.calls, self.sent = [], {}

    def __call__(self, request, timeout):
        url = urllib.parse.urlsplit(request.full_url)
        query = dict(urllib.parse.parse_qsl(url.query))
        self.calls.append({"host": url.netloc, "path": url.path, "query": query,
                           "accept": request.get_header("Accept-encoding")})
        if self.on_call:
            self.on_call(len(self.calls))
        if self.fail and self.fail(query):
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, None)
        pending = self.transient.get((query["symbols"].split(",")[0], query.get("page_token")))
        if pending:
            code = pending.pop(0)
            raise urllib.error.HTTPError(request.full_url, code, "transient", {"X-Ratelimit-Reset": "0"}, None)
        per_page = self.per_page or int(query["limit"])
        low, high = ts(query["start"]), ts(query["end"])
        rows = [(s, t) for s in sorted(query["symbols"].split(",")) for t in sorted(self.bars.get(s, ()))
                if low <= ts(t) <= high]
        offset = int(query.get("page_token", "tok0")[3:])
        more = offset + per_page < len(rows)
        series = {}
        for symbol, t in rows[offset:offset + per_page]:
            p = self.price
            series.setdefault(symbol, []).append({"t": t, "o": p, "h": p, "l": p, "c": p, "v": 100, "n": 1, "vw": p})
        body = json.dumps({"bars": series, "next_page_token": f"tok{offset + per_page}" if more else None}).encode()
        gz = (request.get_header("Accept-encoding") == "gzip"
              and (query["symbols"].split(",")[0], query.get("page_token")) not in self.plain)
        wire = gzip.compress(body, mtime=0) if gz else body
        self.sent[(query["symbols"], query["start"], query.get("page_token"))] = wire
        return Response(wire, {"Content-Encoding": "gzip", "X-Ratelimit-Remaining": "9000"} if gz
                        else {"X-Ratelimit-Remaining": "8999"})


def make_universe(months, last_session="2026-03-31", naming=NAMING):
    rows = [(month, symbol, sessions) for month, members in months.items() for symbol, sessions in members.items()]
    return B.build_universe(rows, naming, {"last_session": last_session, "collection": "synthetic"})


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def news_page(records=(), token=None):
    return Response(json.dumps({"news": list(records), "next_page_token": token}).encode())


def synthetic_env(directory: Path) -> Path:
    env = directory / "paper.env"
    env.write_text("APCA_API_KEY_ID=SYNTHETIC\nAPCA_API_SECRET_KEY=SYNTHETIC\n")
    env.chmod(0o600)
    return env


def redirecting_handlers(test):
    """Patch urllib's HTTPS and HTTP handlers (class level, so any opener built from the defaults uses them): every
    https request is answered 302 to plain http on another host; an http request, the follow-up a redirect would send,
    is recorded with its headers and served an empty bars page. No socket is opened."""
    seen = {"https": [], "http": []}

    def respond(req, code, reason, body, headers):
        message = http.client.HTTPMessage()
        for key, value in headers.items():
            message[key] = value
        response = urllib.response.addinfourl(io.BytesIO(body), message, req.full_url, code)
        response.msg = reason
        return response

    def https_open(handler, req):
        seen["https"].append({"url": req.full_url, "host": req.host, "headers": dict(req.header_items())})
        return respond(req, 302, "Found", b"", {"Location": "http://collector.invalid/v2/stocks/bars"})

    def http_open(handler, req):
        seen["http"].append({"url": req.full_url, "headers": dict(req.header_items())})
        return respond(req, 200, "OK", json.dumps({"bars": {}, "next_page_token": None}).encode(),
                       {"Content-Type": "application/json"})

    test.enterContext(mock.patch.object(urllib.request.HTTPSHandler, "https_open", https_open))
    test.enterContext(mock.patch.object(urllib.request.HTTPHandler, "http_open", http_open))
    return seen


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


class ClientTests(unittest.TestCase):
    def client(self, opener=None, **kwargs):
        self.clock = FakeClock()
        return B.Client({"APCA-API-KEY-ID": "SYNTHETIC-ID", "APCA-API-SECRET-KEY": "SYNTHETIC-SECRET"},
                        B.Bucket(60000, clock=self.clock, sleep=self.clock.sleep), sleep=self.clock.sleep,
                        **({"opener": opener} if opener else {}), **kwargs)  # no opener: the production one

    def test_redirects_are_refused_before_a_follow_up_request(self):
        """urllib's default redirect handler resends every header but the content ones to the Location host."""
        seen = redirecting_handlers(self)
        client = self.client()  # the production opener
        with self.assertRaises(urllib.error.HTTPError) as caught:
            client.fetch("/v2/stocks/bars", {"symbols": "AAA"}, accept_gzip=True)
        self.assertEqual(caught.exception.code, 302)
        self.assertEqual(len(seen["https"]), 1)  # not retried: a redirect is not a transient failure
        self.assertEqual(seen["http"], [])  # the key pair never went to the Location host
        universe = make_universe({"2026-03": MAR})
        with tempfile.TemporaryDirectory() as tmp:  # a whole run: the task fails on its first request
            out = B.run(client, "stock_bars_1min", date(2026, 3, 1), date(2026, 3, 31), Path(tmp), 1,
                        universe=universe, pilot=1, disk_free=lambda path: 10 ** 12, peak_rss=lambda: 0, rate=6000)
            self.assertFalse((Path(tmp) / "stock_bars_1min/manifest.jsonl").read_text())
        self.assertEqual([f["task"] for f in out["failed"]], ["2026-03-b0000"])
        self.assertIn("HTTPError", out["failed"][0]["error"])
        self.assertIn("302", out["failed"][0]["error"])
        self.assertEqual((len(seen["https"]), seen["http"]), (2, []))

    def test_default_opener_refuses_redirects_and_ignores_proxies(self):
        seen = redirecting_handlers(self)
        proxies = {"https_proxy": "http://proxy.invalid:3128", "HTTPS_PROXY": "http://proxy.invalid:3128",
                   "http_proxy": "http://proxy.invalid:3128", "HTTP_PROXY": "http://proxy.invalid:3128"}
        with mock.patch.dict(os.environ, proxies):
            client = self.client()
            control = urllib.request.build_opener()  # the stdlib default reads the environment's proxies
        director = client.opener.__self__
        self.assertIsInstance(director, urllib.request.OpenerDirector)
        self.assertEqual([type(h) for h in director.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)],
                         [B.RedirectRefused])
        self.assertEqual([h for h in director.handlers if isinstance(h, urllib.request.ProxyHandler)], [])
        with self.assertRaises(urllib.error.HTTPError):
            client.fetch("/v2/stocks/bars", {"symbols": "AAA"})
        control.open(urllib.request.Request(URL), timeout=5).close()
        # the client connects to the data host itself; the default opener would have gone through the proxy
        self.assertEqual([call["host"] for call in seen["https"]], ["data.alpaca.markets", "proxy.invalid:3128"])
        request = urllib.request.Request(URL, headers={"APCA-API-SECRET-KEY": "SYNTHETIC-SECRET"})
        with mock.patch.object(urllib.request, "Request", side_effect=AssertionError("a follow-up request was built")):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                B.RedirectRefused().redirect_request(request, io.BytesIO(b""), 307, "Temporary Redirect", {},
                                                     "http://collector.invalid/v2/stocks/bars")
        self.assertEqual(caught.exception.code, 307)

    def test_transient_failures_are_retried_and_others_are_not(self):
        body = json.dumps({"news": [], "next_page_token": None}).encode()
        for label, failure in [("HTTP 503", urllib.error.HTTPError(URL, 503, "Unavailable", {}, None)),
                               ("URLError", urllib.error.URLError("connection refused")),
                               ("HTTPException", http.client.RemoteDisconnected("closed")),
                               ("TimeoutError", TimeoutError("read timed out")),
                               ("ConnectionError", ConnectionResetError("reset"))]:
            with self.subTest(label):
                calls = []

                def opener(request, timeout, failure=failure):
                    calls.append(request.full_url)
                    if len(calls) == 1:
                        raise failure
                    return Response(body)
                client = self.client(opener)
                self.assertEqual(client.get("/v1beta1/news", {}), {"news": [], "next_page_token": None})
                self.assertEqual((len(calls), client.requests), (2, 2))
                self.assertGreaterEqual(self.clock.t, 1.0)  # backed off before the retry
        calls = []

        def bad_request(request, timeout):
            calls.append(1)
            raise urllib.error.HTTPError(URL, 400, "Bad Request", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            self.client(bad_request).get("/v1beta1/news", {})
        self.assertEqual(len(calls), 1)
        calls = []

        def always_503(request, timeout):
            calls.append(1)
            raise urllib.error.HTTPError(URL, 503, "Unavailable", {}, None)
        with self.assertRaises(RuntimeError) as caught:
            self.client(always_503).get("/v1beta1/news", {})
        self.assertIn("gave up after retries", str(caught.exception))
        self.assertEqual(len(calls), 8)

    def test_unexpected_content_encoding_is_refused(self):
        client = self.client(lambda request, timeout: Response(b"\x1b\x00", {"Content-Encoding": "br"}))
        with self.assertRaises(RuntimeError) as caught:
            client.fetch("/v2/stocks/bars", {}, accept_gzip=True)
        self.assertIn("unexpected Content-Encoding 'br'", str(caught.exception))

    def test_low_ratelimit_remaining_pauses_the_bucket_until_the_reset(self):
        """Critique B10 and the budget table: at least 3,500 of the account's 10,000/min stay for the other pools."""
        headers = iter([{"X-Ratelimit-Remaining": "3499", "X-Ratelimit-Reset": "1030"},
                        {"X-Ratelimit-Remaining": "3500", "X-Ratelimit-Reset": "1060"},
                        {"X-Ratelimit-Remaining": "9000"}])
        client = self.client(lambda request, timeout: Response(b"{}", next(headers)), wall=lambda: 1000.0 + self.clock.t)
        client.get("/v2/stocks/bars", {})  # 3,499 left: the bucket pauses until the reset, 30 s away
        self.assertEqual(client.ratelimit_floor_pauses, 1)
        client.get("/v2/stocks/bars", {})
        self.assertAlmostEqual(self.clock.t, 30.0, places=6)
        client.get("/v2/stocks/bars", {})  # 3,500 left: no pause
        self.assertAlmostEqual(self.clock.t, 30.001, places=6)
        self.assertEqual((client.ratelimit_floor_pauses, client.ratelimit_remaining_min), (1, 3499))

    def test_halted_client_sends_nothing(self):
        client = self.client(forbidden)
        client.halt.set()
        with self.assertRaises(B.Halted):
            client.fetch("/v2/stocks/bars", {})
        self.assertEqual(client.requests, 0)


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
            return news_page(rows, token)
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
                "planned": {"tasks": 2, "task_ids_sha256": canonical_sha(["2026-09-01", "2026-09-02"])},
                "task": {"unit": "calendar day (UTC)", "window_utc": ["00:00:00", "23:59:59.999999999"]},
                "capture": "records"})
            self.assertEqual(header["fingerprint"], canonical_sha(header["scope"]))
            before = calls["n"]
            with self.assertRaises(B.Refused) as caught:  # widening the span is a different scope
                B.run(client, "news", date(2026, 9, 1), date(2026, 9, 3), root, workers=1)
            self.assertIn("span: recorded=", str(caught.exception))
            self.assertIn("'2026-09-03'", str(caught.exception))
            with self.assertRaises(B.Refused):  # so is another code version
                B.run(client, "news", date(2026, 9, 1), date(2026, 9, 2), root, workers=1, code="0" * 64)
            self.assertEqual(calls["n"], before)

    def test_a_record_stamped_at_midnight_lands_in_one_day_file(self):
        """Both bounds are inclusive (the /v1beta1/news reference): the archive's D+1T00:00:00Z end stored ids
        5922230 and 17421821 (created at exactly 00:00:00Z) in two day files each."""
        stamps = {1: "2026-09-01T00:00:00Z", 2: "2026-09-01T23:59:59Z", 3: "2026-09-02T00:00:00Z",
                  4: "2026-09-02T12:00:00Z", 5: "2026-09-03T00:00:00Z"}
        queries = []

        def opener(request, timeout):  # serves every record whose created_at lies in [start, end], both inclusive
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(request.full_url).query))
            queries.append((q["start"], q["end"]))
            low, high = ts(q["start"]), ts(q["end"])
            return news_page([{"id": i, "created_at": t} for i, t in stamps.items() if low <= ts(t) <= high])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = B.run(self.client(opener), "news", date(2026, 9, 1), date(2026, 9, 2), root, workers=1)
            self.assertEqual(sorted(queries), [("2026-09-01T00:00:00Z", "2026-09-01T23:59:59.999999999Z"),
                                               ("2026-09-02T00:00:00Z", "2026-09-02T23:59:59.999999999Z")])
            ids = {day: [json.loads(line)["id"] for line in
                         gzip.decompress((root / "news" / B.day_file(day)).read_bytes()).decode().splitlines()]
                   for day in ("2026-09-01", "2026-09-02")}
            self.assertEqual(ids, {"2026-09-01": [1, 2], "2026-09-02": [3, 4]})
            self.assertEqual(out["records"], 4)  # the record at 2026-09-03T00:00:00Z belongs to the next day

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

    def test_host_lease_refuses_a_second_backfill_of_any_dataset_or_out(self):
        """The backfill pool is one job at a time: a news incremental (3,000/min) beside a bars run (6,000/min) would
        break the 3,500/min headroom, and a new scope always goes to a new --out."""
        lease = B.HOST_LEASE
        lease.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lease, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(fd, 0)
            os.write(fd, b'{"pid": 1, "dataset": "stock_bars_1min"}')
            with tempfile.TemporaryDirectory() as tmp:
                for dataset, options in (("news", {}),
                                         ("stock_bars_1min", {"universe": make_universe({"2026-03": MAR}), "pilot": 1})):
                    out = Path(tmp) / f"another-{dataset}"
                    with self.subTest(dataset), self.assertRaises(B.Refused) as caught:
                        B.run(self.client(forbidden), dataset, date(2026, 3, 1), date(2026, 3, 1), out, workers=1, **options)
                    self.assertIn("another backfill run holds", str(caught.exception))
                    self.assertIn('"dataset": "stock_bars_1min"', str(caught.exception))  # names the holder
                    self.assertFalse(out.exists())  # refused before anything is written
        finally:
            os.close(fd)
        held = []

        def probe(request, timeout):  # the run holds the lease while it fetches, and releases it afterwards
            other = os.open(lease, os.O_RDWR)
            try:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held.append(False)
            except BlockingIOError:
                held.append(True)
            finally:
                os.close(other)
            return news_page()
        with tempfile.TemporaryDirectory() as tmp:
            out = B.run(self.client(probe), "news", date(2026, 9, 1), date(2026, 9, 2), Path(tmp), workers=1)
            self.assertEqual((out["days"], held), (2, [True, True]))
            self.assertIn(str(tmp), lease.read_text())
            B.run(self.client(forbidden), "news", date(2026, 9, 1), date(2026, 9, 2), Path(tmp), workers=1)  # released

    def test_stop_file_present_at_start_is_refused(self):
        """A STOP left behind must not make every later run exit at once as if it were done."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "STOP").write_text("")
            with self.assertRaises(B.Refused) as caught:
                B.run(self.client(forbidden), "news", date(2026, 9, 1), date(2026, 9, 3), root, workers=1,
                      stop_file=root / "STOP")
            self.assertIn("STOP exists", str(caught.exception))
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["STOP"])
            env = synthetic_env(root)
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                code = B.main(["news", "--env-file", str(env), "--out", str(root), "--start", "2026-09-01",
                               "--end", "2026-09-03"], opener=forbidden)
            self.assertEqual(code, 2)
            self.assertIn("STOP exists", stderr.getvalue())

    def test_stop_file_drains_the_pool_and_exits_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = synthetic_env(root)
            calls = []

            def opener(request, timeout):  # the operator touches STOP while the first day is being fetched
                calls.append(request.full_url)
                (root / "STOP").touch()
                return news_page([{"id": 1}])
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = B.main(["news", "--env-file", str(env), "--out", str(root), "--start", "2026-09-01",
                               "--end", "2026-09-03", "--workers", "1"], opener=opener)
            result = json.loads(stdout.getvalue())
            self.assertEqual(code, 3)  # a partial run is not "done"
            self.assertEqual((result["days"], result["stopped"], result["failed"], len(calls)), (1, 2, [], 1))
            self.assertIn("STOP exists", result["stop_reason"])

    def test_torn_manifest_line_refetches_that_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = Path(tmp)
            (ds / "2026/09").mkdir(parents=True)
            (ds / "2026/09/01.jsonl.gz").write_bytes(b"x" * 7)
            m = ds / "manifest.jsonl"
            m.write_text('{"day": "2026-09-01", "bytes": 7}\n[]\n{"day": "2026-09-0')
            self.assertEqual(B.done_days(ds), {"2026-09-01"})  # the malformed row and the torn line are skipped
            B.repair_manifest_tail(m)  # the next row starts on its own line
            self.assertTrue(m.read_text().endswith('{"day": "2026-09-0\n'))

    def test_day_whose_file_is_missing_or_resized_is_fetched_again(self):
        """A crash can keep a news row whose day file never reached the disk: that day must not count as done."""
        records = {"2026-09-01": [{"id": 1}, {"id": 2}, {"id": 3}], "2026-09-02": [{"id": 4}], "2026-09-03": [{"id": 5}]}
        opener, calls = self.pages(records)
        client = self.client(opener)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            B.run(client, "news", date(2026, 9, 1), date(2026, 9, 3), root, workers=1)
            (root / "news/2026/09/01.jsonl.gz").unlink()
            (root / "news/2026/09/03.jsonl.gz").write_bytes(b"")  # ext4 delayed allocation: a zero-length file
            records["2026-09-01"].append({"id": 6})  # the provider's answer changed: the superseded row no longer hashes
            before = calls["n"]
            again = B.run(client, "news", date(2026, 9, 1), date(2026, 9, 3), root, workers=1)
            self.assertEqual((again["days"], again["skipped_already_done"], again["records"]), (2, 1, 5))
            self.assertEqual(calls["n"] - before, 3)  # day 1's two pages and day 3's one
            check = B.verify_dataset(root, "news")  # a day's last row decides
            self.assertEqual((check["ok"], check["rows"], check["superseded_rows"], check["files"]), (True, 5, 2, 3))
            self.assertEqual((check["planned_tasks"], check["missing_tasks"], check["complete"]), (3, 0, True))

    def test_day_files_directories_header_and_manifest_are_fsynced(self):
        synced, real = set(), os.fsync

        def spy(fd):
            synced.add(os.fstat(fd).st_ino)
            return real(fd)
        opener, _ = self.pages({"2026-09-01": [{"id": 1}]})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(os, "fsync", spy):
                B.run(self.client(opener), "news", date(2026, 9, 1), date(2026, 9, 1), root, workers=1)
            for path in ("news/2026/09/01.jsonl.gz", "news/2026/09", "news/manifest.jsonl", "news/scope.json", "news"):
                self.assertIn((root / path).stat().st_ino, synced, path)  # "news": the header's rename into place

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

    def test_interrupt_halts_the_pool(self):
        """Ctrl-C in a direct run: queued work is cancelled instead of being fetched without a manifest row."""
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            raise KeyboardInterrupt
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(KeyboardInterrupt):
                B.run(self.client(opener), "news", date(2026, 9, 1), date(2026, 9, 10), Path(tmp), workers=1)
        self.assertEqual(len(calls), 1)

    def test_interrupt_halts_a_task_in_flight(self):
        """A second worker mid-way through a five-page day sends no further page once the run halts."""
        calls, client, second_in_flight = [], None, threading.Event()

        def opener(request, timeout):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(request.full_url).query))
            calls.append((q["start"][:10], q.get("page_token")))
            if q["start"].startswith("2026-09-01"):
                second_in_flight.wait(5)  # interrupt only once the second day is mid-chain
                raise KeyboardInterrupt
            second_in_flight.set()
            client.halt.wait(5)  # answer the second day's page once the main thread has handled the interrupt
            offset = int(q.get("page_token", "0"))
            return news_page([{"id": offset}], str(offset + 1) if offset < 4 else None)
        client = self.client(opener)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(KeyboardInterrupt):
                B.run(client, "news", date(2026, 9, 1), date(2026, 9, 3), Path(tmp), workers=2)
        self.assertEqual(calls.count(("2026-09-01", None)), 1)
        self.assertLessEqual(len([c for c in calls if c[0] == "2026-09-02"]), 1)  # not its other four pages
        self.assertNotIn("2026-09-03", {c[0] for c in calls})  # never submitted

    def test_out_inside_a_git_work_tree_is_refused(self):
        """Licensed provider data never lands in a checkout, where `git add -A` would stage it."""
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            work.mkdir()
            (work / ".git").write_text("gitdir: /elsewhere/.git/worktrees/work\n")  # a linked worktree's .git file
            link = Path(tmp) / "link"
            link.symlink_to(work, target_is_directory=True)
            repo = Path(tmp) / "repo"
            (repo / ".git").mkdir(parents=True)  # a main checkout's .git directory
            before = sorted(Path(tmp).rglob("*"))
            for out in (work / "lake", work / "deep/er/lake", link / "lake", repo / "lake", repo):
                with self.subTest(str(out)), self.assertRaises(B.Refused) as caught:
                    B.run(self.client(forbidden), "news", date(2026, 9, 1), date(2026, 9, 1), out, workers=1)
                self.assertIn("inside the git work tree", str(caught.exception))
            self.assertEqual(sorted(Path(tmp).rglob("*")), before)  # nothing was written
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                code = B.main(["universe", "--daily-dataset", "/nonexistent", "--out", str(work / "universe.json")])
            self.assertEqual(code, 2)
            self.assertIn("inside the git work tree", stderr.getvalue())
            self.assertFalse((work / "universe.json").exists())
        inside = ROOT / ".local" / "data-lake-guard-test"  # this checkout (a git work tree); .local/ is gitignored
        self.addCleanup(shutil.rmtree, inside, True)
        with contextlib.redirect_stderr(io.StringIO()) as stderr:  # refused before the credential file is read
            code = B.main(["news", "--env-file", "/nonexistent/paper.env", "--out", str(inside), "--start", "2026-09-01",
                           "--end", "2026-09-01"], opener=forbidden)
        self.assertEqual(code, 2)
        self.assertIn("inside the git work tree", stderr.getvalue())
        self.assertFalse(inside.exists())


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


@unittest.skipUnless(importlib.util.find_spec("duckdb"),
                     "SKIPPED: DuckDB is not installed in this interpreter; read_daily_collection's query runs under a "
                     "runtime with DuckDB (the pinned engine venv has 1.5.5)")
class DailyCollectionTests(unittest.TestCase):
    def test_read_daily_collection_on_a_tiny_parquet(self):
        import duckdb
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            con = duckdb.connect()
            con.execute("CREATE TABLE daily (symbol VARCHAR, session_date DATE, in_raw BOOLEAN, in_all BOOLEAN, c DOUBLE)")
            con.executemany("INSERT INTO daily VALUES (?, ?, ?, ?, ?)", [
                ("AAPL", "2016-01-04", True, True, 1.0), ("AAPL", "2016-01-05", True, False, 1.0),
                ("DLST", "2016-01-05", False, True, 1.0),                                    # delists in January
                ("AAPL", "2016-02-01", True, True, 1.0),
                ("NEWL", "2016-02-02", False, False, 1.0),                                   # in neither: excluded
                ("NEWL", "2016-03-01", True, True, 1.0), ("ZOLD", "2015-12-31", True, True, 1.0)])
            con.execute(f"COPY daily TO '{d / 'daily.parquet'}' (FORMAT PARQUET)")
            con.close()
            (d / "plan.json").write_text(json.dumps({"asof": B.PROVIDER_DEFAULT_ASOF}))
            (d / "ledger.jsonl").write_text(json.dumps({"recorded_at": "2026-09-21T21:56:23+00:00"}) + "\n\n"
                                            + json.dumps({"recorded_at": "2026-09-21T22:57:36+00:00"}) + "\n")
            (d / "identity-dedup.json").write_text("{}")
            rows, naming, source = B.read_daily_collection(d)
            self.assertEqual(rows, [("2015-12", "ZOLD", 1), ("2016-01", "AAPL", 2), ("2016-01", "DLST", 1),
                                    ("2016-02", "AAPL", 1), ("2016-03", "NEWL", 1)])
            self.assertEqual(naming, "2026-09-21")
            self.assertEqual((source["first_session"], source["last_session"], source["symbols_by_last_bar_year"]),
                             ("2015-12-31", "2016-03-01", {"2015": 1, "2016": 3}))
            self.assertEqual(source["requests_recorded"], ["2026-09-21T21:56:23+00:00", "2026-09-21T22:57:36+00:00"])
            self.assertEqual(source["daily_parquet_sha256"], hashlib.sha256((d / "daily.parquet").read_bytes()).hexdigest())
            self.assertEqual(B.build_universe(rows, naming, source)["summary"]["symbol_sessions"], 6)
            (d / "identity-dedup.json").unlink()
            with self.assertRaises(ValueError) as caught:  # only a deduplicated dataset builds a universe
                B.read_daily_collection(d)
            self.assertIn("identity-dedup.json", str(caught.exception))


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

    def cli(self, *args, opener=forbidden):
        """main() with a synthetic 0600 key file and the universe file: (exit code, stdout, stderr)."""
        env, universe = synthetic_env(self.root), self.root / "universe.json"
        universe.write_bytes(B.canonical(self.universe) + b"\n")
        with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = B.main(["stock_bars_1min", "--env-file", str(env), "--out", str(self.root), "--universe",
                           str(universe), "--rate", "6000", "--workers", "1", *args], opener=opener)
        return code, stdout.getvalue(), stderr.getvalue()


class PageCaptureTests(BarsCase):
    def test_pages_are_stored_as_received_with_params_hashes_and_quarantine(self):
        fake = FakeBars(BARS, plain={(SYMBOLS[100], "tok2")})
        out = self.run_bars(fake, pilot=3)  # a pilot over every planned task
        self.assertEqual((out["tasks"], out["pages"], out["bars"], out["quarantined"], out["failed"]), (3, 8, 13, 2, []))
        self.assertEqual(out["ratelimit_remaining_min"], 8999)
        # pages of 2 bars where 10,000 fit: D2's premise fails, so the pilot says "overturn"
        self.assertEqual((out["pilot"]["verdict"], out["pilot"]["flags"]),
                         ("overturn", {"pages_under_95pct_full": True, "calls_over_1_3x_d2_estimate": False}))
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
        self.assertEqual({t: r["bars_by_symbol"] for t, r in rows.items()},
                         {"2026-02-b0000": {"AAA": 5}, "2026-02-b0001": {"DLST": 2, "META": 3},
                          "2026-03-b0000": {"AAA": 1, "META": 1, "NEWL": 1}})
        self.assertEqual({t: r["symbols_without_bars"] for t, r in rows.items()},
                         {"2026-02-b0000": feb[1:100], "2026-02-b0001": feb[100:148], "2026-03-b0000": []})
        encodings = []
        for task, row in rows.items():
            self.assertEqual(row["symbols_sha256"], hashlib.sha256(row["params"]["symbols"].encode()).hexdigest())
            self.assertEqual([p["page_token"] for p in row["pages"]], [None] + [f"tok{2 * i}" for i in range(1, len(row["pages"]))])
            # the actual next token, so verify can check each stored body against it
            self.assertEqual([p["next_page_token"] for p in row["pages"]], [p["page_token"] for p in row["pages"][1:]] + [None])
            for page in row["pages"]:
                path = self.ds / page["file"]
                stored = path.read_bytes()
                sent = fake.sent[(row["params"]["symbols"], row["params"]["start"], page["page_token"])]
                encodings.append(page["content_encoding"])
                # a gzip page is kept byte for byte as the wire delivered it; an identity page is gzip-wrapped
                self.assertEqual(stored if page["content_encoding"] == "gzip" else gzip.decompress(stored), sent)
                self.assertEqual((len(stored), hashlib.sha256(stored).hexdigest()), (page["bytes"], page["sha256"]))
                self.assertEqual(page["wire_bytes"], len(sent))
                decoded = gzip.decompress(stored)
                self.assertEqual((len(decoded), hashlib.sha256(decoded).hexdigest()), (page["json_bytes"], page["json_sha256"]))
                self.assertEqual(sum(map(len, json.loads(decoded)["bars"].values())), page["bars"])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(encodings), ["gzip"] * 7 + ["identity"])
        self.assertEqual(rows["2026-02-b0000"]["quarantine"], [{"page": 1, "symbol": "AAA", "t": "2026-02-03T01:00:00Z"},
                                                               {"page": 2, "symbol": "AAA", "t": "2026-02-03T08:59:00Z"}])
        self.assertEqual([r["unexpected_symbols"] for r in rows.values()], [[], [], []])
        self.assertEqual(list(self.ds.rglob("*.part")), [])
        metrics = out["pilot"]["metrics"]
        self.assertEqual((metrics["symbol_months_requested"], metrics["symbol_months_without_bars"],
                          metrics["quarantined_bars_per_task_max"]), (153, 147, 2))
        check = B.verify_dataset(self.root, "stock_bars_1min")
        self.assertEqual((check["ok"], check["rows"], check["files"], check["problems"], check["superseded_rows"]),
                         (True, 3, 8, 0, 0))
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
        self.assertEqual((again["tasks"], again["skipped_already_done"], again["pilot"]["verdict"]), (1, 2, "overturn"))
        self.assertEqual({c["query"]["symbols"].split(",")[0] for c in healthy.calls}, {SYMBOLS[100]})
        self.assertEqual(list(self.ds.rglob("*.part")), [])
        self.assertTrue(B.verify_dataset(self.root, "stock_bars_1min")["ok"])

    def looping(self, token):
        """An opener whose every page names a next token: token(n) for the n-th call."""
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            body = {"bars": {"AAA": [{"t": "2026-03-10T14:00:00Z"}]}, "next_page_token": token(len(calls))}
            return Response(gzip.compress(json.dumps(body).encode(), mtime=0), {"Content-Encoding": "gzip"})
        return opener, calls

    def test_repeated_page_token_fails_the_task_and_writes_no_row(self):
        opener, calls = self.looping(lambda n: "again")
        out = self.run_bars(opener, pilot=1, start=date(2026, 3, 1))
        self.assertEqual([f["task"] for f in out["failed"]], ["2026-03-b0000"])
        self.assertIn("RuntimeError", out["failed"][0]["error"])
        self.assertIn("does not terminate", out["failed"][0]["error"])
        self.assertEqual((len(calls), (self.ds / "manifest.jsonl").read_text()), (2, ""))

    def test_page_cap_fails_the_task(self):
        opener, calls = self.looping(lambda n: f"fresh{n}")  # never repeats, never ends
        with mock.patch.object(B, "MAX_PAGES_PER_TASK", 3):
            out = self.run_bars(opener, pilot=1, start=date(2026, 3, 1))
        self.assertIn("does not terminate (3 pages)", out["failed"][0]["error"])
        self.assertEqual((len(calls), (self.ds / "manifest.jsonl").read_text()), (3, ""))

    def test_throttled_and_failing_pages_are_retried_in_place(self):
        """An HTTP 429 waits for the limit's reset and a 503 backs off; the page is then fetched and stored once."""
        healthy, flaky = FakeBars(BARS), FakeBars(BARS, transient={("AAA", "tok2"): [429, 503]})
        self.run_bars(healthy, pilot=1, start=date(2026, 3, 1))
        clean = self.rows()["2026-03-b0000"]
        shutil.rmtree(self.ds)
        out = self.run_bars(flaky, pilot=1, start=date(2026, 3, 1))
        row = self.rows()["2026-03-b0000"]
        self.assertEqual((out["tasks"], out["failed"], out["throttled"], out["requests"]), (1, [], 1, len(healthy.calls) + 2))
        self.assertEqual([c["query"].get("page_token") for c in flaky.calls], [None, "tok2", "tok2", "tok2"])
        self.assertEqual([(p["page_token"], p["sha256"], p["bars"]) for p in row["pages"]],
                         [(p["page_token"], p["sha256"], p["bars"]) for p in clean["pages"]])
        self.assertEqual(sorted(p.name for p in (self.ds / "2026/03/b0000").iterdir()), ["p00000.json.gz", "p00001.json.gz"])
        self.assertGreaterEqual(self.clock.t, 3.0)  # paused until the reset (at least 1 s), then backed off 2 s
        self.assertTrue(B.verify_dataset(self.root, "stock_bars_1min")["ok"])

    def test_quarantine_list_is_capped_and_counted(self):
        """Overnight prints inside the month are returned by a month window; a row stays bounded however many."""
        night = [f"2026-03-03T{1 + m // 60:02d}:{m % 60:02d}:00Z" for m in range(150)]  # 20:00-22:29 EST on 03-02
        out = self.run_bars(FakeBars({"AAA": night + ["2026-03-03T15:00:00Z"]}, per_page=None), pilot=1,
                            start=date(2026, 3, 1))
        row = self.rows()["2026-03-b0000"]
        self.assertEqual((row["bars"], row["quarantined"], len(row["quarantine"])), (151, 150, B.QUARANTINE_EXAMPLES))
        self.assertEqual(row["quarantine"][0], {"page": 0, "symbol": "AAA", "t": "2026-03-03T01:00:00Z"})
        self.assertEqual(out["quarantined"], 150)
        metrics = out["pilot"]["metrics"]
        self.assertEqual((metrics["quarantined_bars"], metrics["quarantined_bars_per_task_max"]), (150, 150))

    def test_requested_symbols_without_bars_are_listed(self):
        """Critique U11: a renamed or reused ticker may return nothing under asof=2026-09-21."""
        bars = {"AAA": ["2026-03-10T14:00:00Z", "2026-03-11T14:00:00Z"], "META": ["2026-03-10T14:00:00Z"]}
        out = self.run_bars(FakeBars(bars), pilot=1, start=date(2026, 3, 1))  # NEWL returns no bar
        row = self.rows()["2026-03-b0000"]
        self.assertEqual((row["bars_by_symbol"], row["symbols_without_bars"]), ({"AAA": 2, "META": 1}, ["NEWL"]))
        metrics = out["pilot"]["metrics"]
        self.assertEqual((metrics["symbol_months_requested"], metrics["symbol_months_without_bars"],
                          metrics["share_without_bars"], metrics["without_bars_examples"]), (3, 1, 0.333, ["2026-03 NEWL"]))
        self.assertTrue(B.verify_dataset(self.root, "stock_bars_1min")["ok"])

    def test_task_with_a_missing_page_file_is_fetched_again(self):
        """A crash can keep a row whose page never reached the disk: the task must not count as done."""
        fake = FakeBars(BARS)
        self.run_bars(fake, pilot=3)
        rows = self.rows()
        (self.ds / rows["2026-03-b0000"]["pages"][1]["file"]).unlink()
        truncated = self.ds / rows["2026-02-b0001"]["pages"][0]["file"]
        truncated.write_bytes(b"")  # ext4 delayed allocation: a zero-length page
        refetch = FakeBars(BARS, price=2.5)  # the provider's answer changed: the superseded rows no longer match
        again = self.run_bars(refetch, pilot=3)
        self.assertEqual((again["tasks"], again["skipped_already_done"]), (2, 1))
        self.assertEqual({c["query"]["symbols"] for c in refetch.calls},
                         {"AAA,META,NEWL", rows["2026-02-b0001"]["params"]["symbols"]})
        check = B.verify_dataset(self.root, "stock_bars_1min")  # a task's last row decides
        self.assertEqual((check["ok"], check["rows"], check["superseded_rows"]), (True, 5, 2))

    def test_pilot_with_a_broken_row_whose_refetch_fails_is_incomplete(self):
        self.run_bars(FakeBars(BARS), pilot=3)
        rows = self.rows()
        (self.ds / rows["2026-03-b0000"]["pages"][0]["file"]).unlink()
        out = self.run_bars(FakeBars(BARS, fail=lambda q: q["symbols"] == "AAA,META,NEWL"), pilot=3)
        self.assertEqual([f["task"] for f in out["failed"]], ["2026-03-b0000"])
        self.assertEqual(out["pilot"]["verdict"], "incomplete")  # the broken row is not measured as if complete
        self.assertIn("2026-03-b0000", out["pilot"]["reason"])

    def test_pages_directories_and_manifest_are_fsynced(self):
        synced, real = set(), os.fsync

        def spy(fd):
            synced.add(os.fstat(fd).st_ino)
            return real(fd)
        with mock.patch.object(os, "fsync", spy):
            self.run_bars(FakeBars(BARS), pilot=3)
        for row in self.rows().values():
            task_dir = (self.ds / row["pages"][0]["file"]).parent
            for page in row["pages"]:
                self.assertIn((self.ds / page["file"]).stat().st_ino, synced)
            self.assertIn(task_dir.stat().st_ino, synced)  # the task directory's entries
            self.assertIn(task_dir.parent.stat().st_ino, synced)  # its rename into place
        for name in ("manifest.jsonl", "scope.json", "pilot.json", "."):  # ".": the header's and report's renames
            self.assertIn((self.ds / name).stat().st_ino, synced, name)

    def test_failed_manifest_append_stops_all_requests(self):
        """ENOSPC on the manifest: nothing more is fetched that could not be recorded."""
        fake = FakeBars(BARS)
        with mock.patch.object(B, "append_row", side_effect=OSError(errno.ENOSPC, "No space left on device"), create=True):
            with self.assertRaises(OSError):
                self.run_bars(fake, pilot=3)
        self.assertEqual({c["query"]["symbols"] for c in fake.calls}, {fake.calls[0]["query"]["symbols"]})

    def test_stop_and_lock_on_the_page_dataset(self):
        self.ds.mkdir(parents=True)
        fd = os.open(self.ds / ".lock", os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(B.Refused) as caught:
                self.run_bars(forbidden, pilot=3)
            self.assertIn("another backfill run holds", str(caught.exception))
        finally:
            os.close(fd)
        stop = self.root / "STOP"
        fake = FakeBars(BARS, on_call=lambda n: stop.touch())  # touched during the first task
        out = self.run_bars(fake, pilot=3, stop_file=stop)
        self.assertEqual((out["tasks"], out["stopped"], out["failed"]), (1, 2, []))
        self.assertEqual({c["query"]["symbols"] for c in fake.calls}, {fake.calls[0]["query"]["symbols"]})
        with self.assertRaises(B.Refused):  # still there: the next run refuses until the operator removes it
            self.run_bars(fake, pilot=3, stop_file=stop)


class VerifyTests(BarsCase):
    def edit(self, change):
        manifest = self.ds / "manifest.jsonl"
        rows = [json.loads(line) for line in self.pristine.splitlines()]
        for row in rows:
            if row["task"] == "2026-02-b0000":
                change(row)
        manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        return B.verify_dataset(self.root, "stock_bars_1min")

    def test_verify_decodes_pages_for_the_chain_and_the_bar_totals(self):
        self.run_bars(FakeBars(BARS), pilot=3)
        self.pristine = (self.ds / "manifest.jsonl").read_text()
        self.assertTrue(self.edit(lambda row: None)["ok"])

        def truncate(row):  # cut after its second page and made self-consistent: its files still hash
            row["pages"] = row["pages"][:2]
            row["pages"][-1]["next_page_token"] = None
            row["bars"] = sum(page["bars"] for page in row["pages"])
            row["bars_by_symbol"] = {"AAA": row["bars"]}
        check = self.edit(truncate)
        self.assertFalse(check["ok"])
        self.assertIn({"task": "2026-02-b0000", "page": 1,
                       "problem": "last page body carries a next_page_token: the chain was cut short"}, check["examples"])

        def retoken(row):
            row["pages"][0]["next_page_token"] = "tok9"
        self.assertEqual(self.edit(retoken)["examples"], [
            {"task": "2026-02-b0000", "page": 0, "problem": "recorded next_page_token does not name the next page"}])

        def recount(row):  # page and task totals edited together
            row["pages"][0]["bars"] += 1
            row["bars"] += 1
        check = self.edit(recount)
        self.assertEqual(check["examples"][0], {"task": "2026-02-b0000", "page": 0,
                                                "problem": "recorded page bars differ from the page body"})

        def resymbol(row):
            row["bars_by_symbol"] = {"AAA": 4, "AAB": 1}
        self.assertEqual(self.edit(resymbol)["examples"], [
            {"task": "2026-02-b0000", "problem": "bars by symbol differ from the page bodies"}])

        def total(row):
            row["bars"] += 1
        self.assertEqual(self.edit(total)["examples"], [
            {"task": "2026-02-b0000", "problem": "page bars do not sum to the task total"}])

    def test_verify_compares_recorded_tasks_with_the_plan(self):
        """A drained or pilot-only lake is not complete, whatever its rows' integrity (exit 1, not ok)."""
        self.run_bars(FakeBars(BARS), pilot=2)  # tasks 2026-02-b0000 and 2026-03-b0000 of three
        check = B.verify_dataset(self.root, "stock_bars_1min")
        self.assertEqual((check["problems"], check["planned_tasks"], check["missing_tasks"], check["missing_examples"],
                          check["complete"], check["ok"]), (0, 3, 1, ["2026-02-b0001"], False, False))
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(B.main(["verify", "stock_bars_1min", "--out", str(self.root)]), 1)
        self.assertEqual(json.loads(stdout.getvalue())["missing_tasks"], 1)
        self.run_bars(FakeBars(BARS), pilot=3)
        check = B.verify_dataset(self.root, "stock_bars_1min")
        self.assertEqual((check["missing_tasks"], check["complete"], check["ok"]), (0, True, True))
        manifest = self.ds / "manifest.jsonl"
        rows = [json.loads(line) for line in manifest.read_text().splitlines()]
        manifest.write_text(manifest.read_text() + json.dumps({**rows[0], "task": "2026-04-b0000"}) + "\n")
        self.assertIn({"task": "2026-04-b0000", "problem": "not a planned task of the scope"},
                      B.verify_dataset(self.root, "stock_bars_1min")["examples"])
        header_path = self.ds / "scope.json"
        header = json.loads(header_path.read_text())
        header["provenance"]["planned_task_ids"].pop()  # the provenance is not fingerprinted; the planned digest is
        header_path.write_text(json.dumps(header))
        check = B.verify_dataset(self.root, "stock_bars_1min")
        self.assertIn({"file": "scope.json", "problem": "planned task list missing or does not match the scope"},
                      check["examples"])
        self.assertEqual((check["planned_tasks"], check["complete"], check["ok"]), (None, None, False))

    def test_verify_reports_a_missing_manifest_and_malformed_rows(self):
        self.run_bars(FakeBars(BARS), pilot=3)
        manifest = self.ds / "manifest.jsonl"
        pristine = manifest.read_text()
        manifest.unlink()
        check = B.verify_dataset(self.root, "stock_bars_1min")
        self.assertEqual((check["ok"], check["rows"], check["complete"]), (False, 0, False))
        self.assertIn({"file": "manifest.jsonl", "problem": "missing"}, check["examples"])
        rows = [json.loads(line) for line in pristine.splitlines()]
        pages_not_a_list = {**rows[0], "pages": "not-a-list"}
        page_without_file = {**rows[1], "pages": [{k: v for k, v in rows[1]["pages"][0].items() if k != "file"}]}
        broken = [pages_not_a_list, page_without_file, [], 5, {"task": 7}, rows[2]]
        manifest.write_text("".join(json.dumps(row) + "\n" for row in broken))
        check = B.verify_dataset(self.root, "stock_bars_1min")  # reported, not raised
        self.assertEqual((check["ok"], check["rows"], check["malformed_rows"]), (False, 6, 5))
        self.assertEqual([e for e in check["examples"] if "line" in e], [
            {"line": 3, "problem": "malformed manifest row"}, {"line": 4, "problem": "malformed manifest row"},
            {"line": 5, "problem": "malformed manifest row"},
            {"line": 1, "problem": "malformed row or page for 2026-02-b0000 (AttributeError)"},
            {"line": 2, "problem": "malformed row or page for 2026-02-b0001 (KeyError)"}])
        news = self.root / "news"  # a record-capture manifest: rows without a day or a sha256
        news.mkdir()
        (news / "manifest.jsonl").write_text('{"day": "2026-09-01"}\n{"sha256": "0"}\n{"day": 5, "sha256": "0"}\n')
        check = B.verify_dataset(self.root, "news")
        self.assertEqual((check["ok"], check["rows"], check["malformed_rows"], check["complete"]), (False, 3, 3, None))
        (news / "manifest.jsonl").unlink()
        self.assertEqual(B.verify_dataset(self.root, "news")["examples"], [{"file": "manifest.jsonl", "problem": "missing"}])


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
            "planned": {"tasks": 3, "task_ids_sha256": canonical_sha(["2026-02-b0000", "2026-02-b0001", "2026-03-b0000"])},
            "task": {"unit": "symbols x calendar month", "batch_size": 100, "window_et": ["04:00", "19:59:59.999999999"]},
            "capture": "pages"})
        self.assertEqual(header["fingerprint"], canonical_sha(header["scope"]))
        self.assertEqual(header["provenance"]["universe"]["naming_asof"], NAMING)
        self.assertEqual(header["provenance"]["planned_task_ids"], ["2026-02-b0000", "2026-02-b0001", "2026-03-b0000"])
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

    def test_refused_full_run_writes_no_header(self):
        """A full run before any pilot (say with a mistyped --end) is refused without pinning its scope, so the
        corrected pilot is not then refused as a different scope."""
        code, _, stderr = self.cli("--start", "2026-02-01", "--end", "2026-03-31")
        self.assertEqual(code, 2)
        self.assertIn("has no pilot", stderr)
        self.assertFalse((self.ds / "scope.json").exists())
        code, stdout, _ = self.cli("--start", "2026-02-01", "--end", "2026-03-30", "--pilot", "2",
                                   opener=FakeBars(BARS, per_page=None))
        self.assertEqual((code, json.loads(stdout)["pilot"]["verdict"]), (0, "pass"))
        self.assertEqual(json.loads((self.ds / "scope.json").read_text())["scope"]["span"]["end"], "2026-03-30")
        code, _, stderr = self.cli("--start", "2026-02-01", "--end", "2026-03-31", "--pilot", "2")
        self.assertEqual(code, 2)
        self.assertIn("different scope", stderr)


class PilotTests(BarsCase):
    """Pages of the request's limit (patched to 40), so the synthetic pilot meets D2's premise unless a test breaks it."""

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.dict(B.DATASETS["stock_bars_1min"]["params"], {"limit": 40}))
        members = SYMBOLS[:300]
        self.universe = make_universe({"2026-02": dict.fromkeys(members, 19), "2026-03": dict.fromkeys(members, 22)})
        self.bars = {s: [f"2026-02-{10 + k:02d}T15:00:00Z" for k in range(1 + i % 3)]
                     + [f"2026-03-{10 + k:02d}T14:00:00Z" for k in range(1 + i % 2)] for i, s in enumerate(members)}

    def stored(self):
        return sum(page["bytes"] for row in self.rows().values() for page in row["pages"])

    def test_pilot_fetches_spread_tasks_reports_and_projects_disk(self):
        fake = FakeBars(self.bars, per_page=None)
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
        stored = sum(p["bytes"] for p in pages)
        disk = (sum(max(os.stat(self.ds / p["file"]).st_size, os.stat(self.ds / p["file"]).st_blocks * 512) for p in pages)
                + sum(len(json.dumps(r, sort_keys=True)) + 1 for r in rows.values()))
        m = report["metrics"]
        self.assertEqual((m["tasks"], m["pages"], m["bars"], m["stored_bytes"], m["disk_bytes"]),
                         (2, len(pages), bars, stored, disk))
        self.assertEqual((m["pages_by_encoding"], m["wire_bytes"]), ({"gzip": len(pages)}, stored))  # gzip: as received
        self.assertEqual((m["wire_bytes_per_page"], m["wire_bytes_per_bar"], m["disk_bytes_per_bar"]),
                         (round(stored / len(pages), 3), round(stored / bars, 3), round(disk / bars, 3)))
        self.assertEqual((m["peak_rss_bytes"], m["peak_rss_mib"]), (64 * 2 ** 20, 64.0))
        self.assertEqual((m["symbol_months_without_bars"], m["quarantined_bars_per_task_max"]), (0, 0))
        p = report["projection"]
        sessions_pilot, sessions_total = 100 * 19 + 100 * 22, 300 * 19 + 300 * 22
        projected_bars = bars / sessions_pilot * sessions_total
        projected = math.ceil(max(projected_bars * disk / bars, disk / 2 * 6))
        self.assertEqual((p["planned_tasks"], p["symbol_sessions_pilot"], p["symbol_sessions_total"]),
                         (6, sessions_pilot, sessions_total))
        self.assertEqual((p["projected_disk_bytes"], p["stored_bytes"], p["remaining_disk_bytes"]),
                         (projected, stored, projected - stored))
        self.assertEqual((p["free_disk_bytes"], p["threshold_bytes"]), (10 ** 12, int(0.4 * 10 ** 12)))
        self.assertEqual(p["projected_calls_upper"], math.ceil(projected_bars / 40) + 6)
        self.assertEqual(p["projected_calls"], math.ceil(max(len(pages) / sessions_pilot * sessions_total, len(pages) * 3)))
        self.assertEqual(p["d2_estimate_calls"], math.ceil(B.D2_BARS_PER_SYMBOL_SESSION * sessions_total / 40) + 6)
        self.assertEqual(report["flags"], {"pages_under_95pct_full": False, "calls_over_1_3x_d2_estimate": False})
        self.assertEqual(report["verdict"], "pass")

    def test_pilot_refuses_above_40_percent_of_free_disk_and_gates_the_full_run(self):
        fake = FakeBars(self.bars, per_page=None)
        with self.assertRaises(B.Refused) as caught:  # no pilot yet
            self.run_bars(fake)
        self.assertIn("has no pilot", str(caught.exception))
        remaining = self.run_bars(fake, pilot=2)["pilot"]["projection"]["remaining_disk_bytes"]
        tight, ample = math.floor(remaining / 0.4) - 1, math.ceil(remaining / 0.4) + 1
        refused = self.run_bars(fake, pilot=2, free=tight)
        self.assertEqual((refused["pilot"]["verdict"], refused["pilot"]["metrics"]["fetched_in_this_run"]), ("refused", 0))
        self.assertIn("exceed 40% of free disk", refused["pilot"]["reason"])
        with self.assertRaises(B.Refused) as caught:
            self.run_bars(fake, free=10 ** 12)
        self.assertIn("verdict is 'refused'", str(caught.exception))
        with self.assertRaises(B.Refused) as caught:  # a disk refusal is never acknowledged away
            self.run_bars(fake, free=10 ** 12, accept_flags="synthetic acknowledgement")
        self.assertIn("verdict is 'refused'", str(caught.exception))
        self.assertEqual(self.run_bars(fake, pilot=2, free=ample)["pilot"]["verdict"], "pass")
        with self.assertRaises(B.Refused) as caught:  # free space shrank since the pilot
            self.run_bars(fake, free=tight)
        self.assertIn("bytes free now", str(caught.exception))
        before = len(fake.calls)
        full = self.run_bars(fake, free=10 ** 12)
        self.assertEqual((full["tasks"], full["skipped_already_done"], full["failed"], full["stopped"]), (4, 2, [], 0))
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
        self.run_bars(FakeBars(self.bars, per_page=None), pilot=2)
        (self.ds / "pilot.json").write_text("{")
        with self.assertRaises(B.Refused) as caught:
            self.run_bars(forbidden)
        self.assertIn("unreadable", str(caught.exception))

    def test_pilot_without_bars_refuses(self):
        out = self.run_bars(FakeBars({}, per_page=None), pilot=2)
        self.assertEqual(out["pilot"]["verdict"], "refused")
        self.assertIn("no bars", out["pilot"]["reason"])

    def test_pilot_reports_identity_pages_and_wire_bytes(self):
        """Gzip on /v2/stocks/bars is unmeasured: an identity answer must show, not pass as compressed wire bytes."""
        out = self.run_bars(FakeBars(self.bars, per_page=None, plain={(SYMBOLS[100], None)}), pilot=2)
        pages = [p for r in self.rows().values() for p in r["pages"]]
        identity = [p for p in pages if p["content_encoding"] == "identity"]
        m = out["pilot"]["metrics"]
        self.assertEqual(len(identity), 2)  # the first page of each pilot task
        self.assertEqual(m["pages_by_encoding"], {"gzip": len(pages) - 2, "identity": 2})
        self.assertEqual(m["wire_bytes"], sum(p["json_bytes"] if p["content_encoding"] == "identity" else p["bytes"]
                                              for p in pages))
        self.assertEqual(m["stored_bytes"], sum(p["bytes"] for p in pages))
        self.assertNotEqual(m["wire_bytes"], m["stored_bytes"])

    def test_d2_overturn_flag_needs_an_acknowledged_full_run(self):
        fake = FakeBars(self.bars, per_page=10)  # continuation pages 25% full
        code, stdout, _ = self.cli("--start", "2026-02-01", "--end", "2026-03-31", "--pilot", "2", opener=fake)
        report = json.loads(stdout)["pilot"]
        self.assertEqual((code, report["verdict"]), (4, "overturn"))
        self.assertEqual(report["flags"], {"pages_under_95pct_full": True, "calls_over_1_3x_d2_estimate": False})
        with self.assertRaises(B.Refused) as caught:
            self.run_bars(fake)
        self.assertIn("--accept-pilot-flags", str(caught.exception))
        with self.assertRaises(SystemExit):  # an acknowledgement needs a reason and belongs to a full run
            self.cli("--start", "2026-02-01", "--end", "2026-03-31", "--pilot", "2", "--accept-pilot-flags", "why")
        with self.assertRaises(SystemExit):
            self.cli("--start", "2026-02-01", "--end", "2026-03-31", "--accept-pilot-flags", " ")
        full = self.run_bars(fake, accept_flags="synthetic: month tasks kept for comparison")
        self.assertEqual((full["tasks"], full["pilot_flags_accepted"]), (4, "synthetic: month tasks kept for comparison"))
        acknowledged = json.loads((self.ds / "pilot.json").read_text())["acknowledged"]
        self.assertEqual((acknowledged["reason"], acknowledged["flags"]),
                         ("synthetic: month tasks kept for comparison", ["pages_under_95pct_full"]))

    def test_calls_above_d2_estimate_raise_the_overturn_flag(self):
        """Full pages but far more bars per symbol-session than D2's model: calls exceed 1.3x its estimate."""
        task = {"task": "2026-02-b0000", "month": "2026-02", "symbols": ["AAA"], "symbol_sessions": 1}
        self.ds.mkdir(parents=True)
        pages = []
        for index in range(10):  # 400 bars in one symbol-session, against D2's 172.4
            (self.ds / f"p{index}.json.gz").write_bytes(b"x")
            pages.append({"file": f"p{index}.json.gz", "bytes": 1, "wire_bytes": 1, "json_bytes": 1,
                          "content_encoding": "gzip", "bars": 40, "next_page_token": f"t{index + 1}" if index < 9 else None})
        row = {"task": task["task"], "month": "2026-02", "symbols": 1, "bars": 400, "pages": pages, "quarantine": [],
               "quarantined": 0, "symbols_without_bars": []}
        report = B.pilot_report(self.ds, "stock_bars_1min", "f" * 64, [task], [task], {task["task"]: row},
                                free_bytes=10 ** 12, stored_bytes=10, disk_floor=0, rss_bytes=0, seconds=1.0,
                                requests=10, fetched_now=1, rate=6000)
        self.assertEqual((report["projection"]["projected_calls"], report["projection"]["d2_estimate_calls"]),
                         (10, math.ceil(B.D2_BARS_PER_SYMBOL_SESSION / 40) + 1))
        self.assertEqual(report["flags"], {"pages_under_95pct_full": False, "calls_over_1_3x_d2_estimate": True})
        self.assertEqual(report["verdict"], "overturn")

    def test_pilot_rerun_after_a_partial_full_run_keeps_passing(self):
        """The verdict weighs what the span still needs, not the whole projection against today's free disk."""
        fake = FakeBars(self.bars, per_page=None)
        projected = self.run_bars(fake, pilot=2)["pilot"]["projection"]["projected_disk_bytes"]
        stop = self.root / "STOP"
        partial = self.run_bars(FakeBars(self.bars, per_page=None, on_call=lambda n: stop.touch()), stop_file=stop)
        self.assertEqual((partial["tasks"], partial["stopped"]), (1, 3))
        stop.unlink()
        free = math.ceil((projected - self.stored()) / 0.4) + 1
        self.assertLess(0.4 * free, projected)  # the whole projection would no longer fit
        again = self.run_bars(fake, pilot=2, free=free)["pilot"]
        self.assertEqual(again["verdict"], "pass")
        self.assertEqual(again["projection"]["remaining_disk_bytes"], projected - self.stored())
        resumed = self.run_bars(fake, free=free)
        self.assertEqual((resumed["tasks"], resumed["skipped_already_done"], resumed["stopped"]), (3, 3, 0))

    def test_free_disk_is_rechecked_before_each_task(self):
        self.run_bars(FakeBars(self.bars, per_page=None), pilot=2)
        fake = FakeBars(self.bars, per_page=None)
        free = lambda path: 10 ** 12 if not fake.calls else 1000  # something else fills the disk once the run starts
        out = self.run_bars(fake, free=None, disk_free=free)
        self.assertEqual((out["tasks"], out["stopped"], out["failed"]), (1, 3, []))
        self.assertIn("remaining projected", out["stop_reason"])
        self.assertEqual({c["query"]["symbols"] for c in fake.calls}, {fake.calls[0]["query"]["symbols"]})

    def test_stored_bytes_beyond_1_5x_the_projection_drain_the_run(self):
        self.run_bars(FakeBars(self.bars, per_page=None), pilot=2)
        path = self.ds / "pilot.json"
        report = json.loads(path.read_text())
        report["projection"]["projected_disk_bytes"] = math.ceil(self.stored() / 1.5) + 1  # an under-sampled pilot
        path.write_text(json.dumps(report))
        fake = FakeBars(self.bars, per_page=None)
        out = self.run_bars(fake)
        self.assertEqual((out["tasks"], out["stopped"]), (1, 3))
        self.assertIn("exceed 1.5x the pilot's projection", out["stop_reason"])

    def test_disk_floor_refuses_and_drains(self):
        with mock.patch.object(B, "DISK_FLOOR", 10 ** 9):
            fake = FakeBars(self.bars, per_page=None)
            low = self.run_bars(fake, pilot=2, free=10 ** 9 + 1000)["pilot"]
            self.assertEqual(low["verdict"], "refused")
            self.assertIn("-byte floor", low["reason"])
            self.assertEqual(self.run_bars(fake, pilot=2, free=10 ** 10)["pilot"]["verdict"], "pass")
            full = FakeBars(self.bars, per_page=None)
            out = self.run_bars(full, free=None, disk_free=lambda path: 10 ** 10 if not full.calls else 10 ** 9 - 1)
        self.assertEqual((out["tasks"], out["stopped"]), (1, 3))
        self.assertIn("-byte floor", out["stop_reason"])

    def test_normalized_layer_reserve_is_kept_free(self):
        """X4: the raw layer must leave room for D1's normalized layer (16.8 bytes/bar measured) beyond the floor."""
        fake = FakeBars(self.bars, per_page=None)
        report = self.run_bars(fake, pilot=2)["pilot"]
        projected_bars = report["metrics"]["bars"] / (100 * 19 + 100 * 22) * (300 * 19 + 300 * 22)
        self.assertEqual(report["projection"]["normalized_reserve_bytes"], math.ceil(projected_bars * 16.8))
        with mock.patch.object(B, "NORMALIZED_BYTES_PER_BAR", 10 ** 6):  # a reserve far above the raw projection
            reserve = math.ceil(projected_bars * 10 ** 6)
            refused = self.run_bars(fake, pilot=2, free=reserve)["pilot"]
            self.assertEqual(refused["verdict"], "refused")  # within 40% of free disk, but not above the reserve
            self.assertIn("normalized-layer reserve", refused["reason"])
            self.assertEqual(self.run_bars(fake, pilot=2, free=10 ** 12)["pilot"]["verdict"], "pass")
            with self.assertRaises(B.Refused) as caught:  # the full-run gate keeps it too
                self.run_bars(fake, free=reserve)
            self.assertIn("normalized-layer reserve", str(caught.exception))
            full = FakeBars(self.bars, per_page=None)
            out = self.run_bars(full, free=None, disk_free=lambda path: 10 ** 12 if not full.calls else reserve)
        self.assertEqual((out["tasks"], out["stopped"]), (1, 3))  # and so does the re-check before each task
        self.assertIn("normalized-layer reserve", out["stop_reason"])

    def test_exit_codes_tell_done_from_failed_refused_and_stopped(self):
        span = ("--start", "2026-02-01", "--end", "2026-03-31")
        self.assertEqual(self.cli(*span)[0], 2)  # refused: no pilot yet
        march_pilot_fails = FakeBars(self.bars, per_page=None, fail=lambda q: q["symbols"].startswith(SYMBOLS[100] + ",")
                                     and q["start"].startswith("2026-03"))
        self.assertEqual(self.cli(*span, "--pilot", "2", opener=march_pilot_fails)[0], 1)  # an incomplete pilot
        self.assertEqual(self.cli(*span, "--pilot", "2", opener=FakeBars(self.bars, per_page=None))[0], 0)
        stop = self.root / "STOP"
        code, stdout, _ = self.cli(*span, opener=FakeBars(self.bars, per_page=None, on_call=lambda n: stop.touch()))
        self.assertEqual((code, json.loads(stdout)["tasks"], json.loads(stdout)["stopped"]), (3, 1, 3))  # drained
        self.assertEqual(self.cli(*span)[0], 2)  # refused while STOP is still there
        stop.unlink()
        third_batch_fails = FakeBars(self.bars, per_page=None, fail=lambda q: q["symbols"].startswith(SYMBOLS[200] + ","))
        code, stdout, _ = self.cli(*span, opener=third_batch_fails)
        self.assertEqual((code, [f["task"] for f in json.loads(stdout)["failed"]]), (1, ["2026-02-b0002", "2026-03-b0002"]))
        code, stdout, _ = self.cli(*span, opener=FakeBars(self.bars, per_page=None))
        self.assertEqual((code, json.loads(stdout)["tasks"]), (0, 2))  # done
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(B.main(["verify", "stock_bars_1min", "--out", str(self.root)]), 0)

    def test_a_pilot_drains_below_the_floor(self):
        """A pilot has no projection yet, so the floor is its only disk re-check."""
        with mock.patch.object(B, "DISK_FLOOR", 10 ** 9):
            fake = FakeBars(self.bars, per_page=None)
            out = self.run_bars(fake, pilot=2, free=None, disk_free=lambda path: 10 ** 10 if not fake.calls else 10 ** 9 - 1)
        self.assertEqual((out["tasks"], out["stopped"], out["pilot"]["verdict"]), (1, 1, "incomplete"))
        self.assertEqual(out["stop_reason"], f"free disk fell to {10 ** 9 - 1} bytes, under the {10 ** 9}-byte floor")
        self.assertEqual({c["query"]["start"][:7] for c in fake.calls}, {"2026-02"})  # the March pilot task never started

    def test_completed_rows_are_released(self):
        """At most --workers tasks are in flight and a row is dropped once written, so memory does not grow with the
        11,620 completed tasks of the full run."""
        class Row(dict):
            pass
        refs, alive, original = [], [], B.page_task

        def tracked(*args):
            row = Row(original(*args))
            refs.append(weakref.ref(row))
            return row
        fake = FakeBars(self.bars, per_page=None)

        def opener(request, timeout):
            gc.collect()
            alive.append(sum(ref() is not None for ref in refs))
            return fake(request, timeout)
        with mock.patch.object(B, "page_task", tracked):
            out = self.run_bars(opener, pilot=6)
        self.assertEqual(out["tasks"], 6)
        self.assertLessEqual(max(alive), 1)  # one worker: at most the row just written


if __name__ == "__main__":
    unittest.main()
