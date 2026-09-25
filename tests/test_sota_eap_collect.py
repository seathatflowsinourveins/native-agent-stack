"""SYN: EAP SEC collector rate limit, retries, resumable manifest, extraction and identity drop-outs."""
import argparse
import contextlib
import gzip
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/sota-mover/eap"


sys.path.insert(0, str(BASE))
import collect_edgar as C  # noqa: E402



class FakeClock:
    def __init__(self):
        self.t = 100.0
        self.sleeps = []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class RateLimit(unittest.TestCase):
    def test_spacing_never_exceeds_rate(self):
        fc = FakeClock()
        rl = C.RateLimiter(8.0, clock=fc.clock, sleep=fc.sleep)
        starts = []
        for _ in range(20):
            rl.wait()
            starts.append(fc.t)
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        self.assertTrue(all(g >= 1 / 8 - 1e-12 for g in gaps))
        self.assertLessEqual((len(starts) - 1) / (starts[-1] - starts[0]), 8.0 + 1e-9)

    def test_rate_above_cap_refused(self):
        with self.assertRaises(ValueError):
            C.RateLimiter(8.5)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()), tempfile.TemporaryDirectory() as tmp:
            C.main(["fetch", "--rate", "9", "--root", tmp])


class Resp(io.BytesIO):
    def __init__(self, body, status=200, gz=False):
        super().__init__(gzip.compress(body) if gz else body)
        self.status = status
        self.headers = {"Content-Encoding": "gzip"} if gz else {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Retries(unittest.TestCase):
    def test_retry_then_success_and_tally(self):
        calls = []

        def opener(req):
            calls.append(req)
            if len(calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "slow", {}, None)
            return Resp(b'{"ok": 1}', gz=True)

        fc = FakeClock()
        http = C.Http("Tester test@example.invalid", C.RateLimiter(8.0, clock=fc.clock, sleep=fc.sleep), opener=opener, sleep=fc.sleep)
        status, body = http.get("https://data.sec.gov/x")
        self.assertEqual((status, json.loads(body)), (200, {"ok": 1}))
        self.assertEqual(dict(http.tally), {"429": 1, "200": 1})
        self.assertEqual(calls[0].get_header("User-agent"), "Tester test@example.invalid")

    def test_404_not_retried(self):
        def opener(req):
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        fc = FakeClock()
        http = C.Http("t", C.RateLimiter(8.0, clock=fc.clock, sleep=fc.sleep), opener=opener, sleep=fc.sleep)
        self.assertEqual(http.get("https://data.sec.gov/missing"), (404, b""))
        self.assertEqual(dict(http.tally), {"404": 1})


def submissions(cik, rows, files=()):
    keys = ["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items"]
    return {"cik": cik, "filings": {"recent": {k: [r[i] for r in rows] for i, k in enumerate(keys)}, "files": list(files)}}


class FakeHttp:
    def __init__(self, pages):
        self.pages = pages
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        name = url.rsplit("/", 1)[1]
        if name not in self.pages:
            return 404, b""
        return 200, json.dumps(self.pages[name]).encode()


class StoreAndExtract(unittest.TestCase):
    def pages(self):
        recent = [("0001-26-000001", "2026-02-01", "2025-12-31", "2026-02-01T16:30:00.000Z", "8-K", "2.02,9.01"),
                  ("0001-26-000002", "2026-02-20", "2025-12-31", "2026-02-20T17:00:00.000Z", "10-K", ""),
                  ("0001-26-000003", "2026-03-01", "", "2026-03-01T09:00:00.000Z", "4", "")]
        old = [("0001-15-000009", "2015-04-28", "2015-04-28", "2015-04-28T08:00:00.000Z", "8-K", "2.02"),
               ("0001-14-000009", "2014-10-28", "2014-10-28", "2014-10-28T08:00:00.000Z", "8-K", "2.02")]
        files = [{"name": "CIK0000000001-submissions-001.json", "filingFrom": "2014-01-01", "filingTo": "2015-12-31"},
                 {"name": "CIK0000000001-submissions-002.json", "filingFrom": "2005-01-01", "filingTo": "2013-12-31"}]
        cont = submissions("1", old)["filings"]["recent"]
        return {"CIK0000000001.json": submissions("1", recent, files),
                "CIK0000000001-submissions-001.json": cont}

    def test_only_needed_continuations(self):
        self.assertEqual(C.needed_continuations(self.pages()["CIK0000000001.json"]), ["CIK0000000001-submissions-001.json"])

    def test_resumable_fetch_manifest_and_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = C.Store(root)
            http = FakeHttp(self.pages())
            self.assertEqual(C.fetch_cik("0000000001", http, store), "ok")
            self.assertEqual(C.fetch_cik("0000000002", http, store), "not_found")
            self.assertEqual(store.done_ciks(), {"0000000001", "0000000002"})
            lines = store.lines()
            stored = [l for l in lines if l["kind"] in ("submissions", "continuation")]
            self.assertEqual(len(stored), 2)
            for l in stored:
                body = gzip.decompress((root / l["file"]).read_bytes())
                self.assertEqual(C.sha256_bytes(body), l["sha256"])
            with store.manifest.open("a") as f:
                f.write('{"kind": "cik_do')  # torn line from an interrupted run
            self.assertEqual(C.Store(root).done_ciks(), {"0000000001", "0000000002"})
            (root / "receipts").mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                C.cmd_extract(argparse.Namespace(root=root))
            rows = [json.loads(l) for l in gzip.decompress((root / "derived" / "filings.jsonl.gz").read_bytes()).splitlines()]
            self.assertEqual(sorted(r["accession"] for r in rows), ["0001-15-000009", "0001-26-000001", "0001-26-000002"])
            receipt = json.loads((root / "receipts" / "extract.json").read_text())
            self.assertEqual(receipt["by_form"]["8-K_item_2.02"], 2)
            self.assertEqual(receipt["not_found_ciks"], 1)
            self.assertEqual(receipt["manifest_sha256"], C.sha256_bytes(store.manifest.read_bytes()))


class Identity(unittest.TestCase):
    def test_current_map_drop_outs_are_counted(self):
        tickers = {"0": {"cik_str": 1, "ticker": "BRK-B", "title": "x"},
                   "1": {"cik_str": 1, "ticker": "BRK-A", "title": "x"},
                   "2": {"cik_str": 2, "ticker": "NEWCO", "title": "y"}}
        daily = {"BRK.B", "OLDCO", "GONE"}  # OLDCO and GONE: delisted issuers absent from the current map
        matched, counts = C.match_universe(tickers, daily)
        self.assertEqual(matched, {"0000000001": ["BRK.B"]})
        self.assertEqual(counts["daily_symbols_without_current_cik"], 2)
        self.assertEqual(counts["sec_ciks_without_daily_symbol"], 1)


if __name__ == "__main__":
    unittest.main()
