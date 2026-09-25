"""SYN: collect_auctions.py against a fake transport (no network, no credentials).

Covers the endpoint allow-list, batching, pagination, retry on 429, the 03:30 ET rate
switch, auction materialization/coverage, spread sampling and the credential guard.
"""

import gzip
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/sota-mover/news-llm"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ca = load("news_llm_collect_under_test", "collect_auctions.py")
FAKE_HEADERS = {"APCA-API-KEY-ID": "fake-id", "APCA-API-SECRET-KEY": "fake-secret"}


class NoWaitLimiter:
    def wait(self):
        pass


class FakeTransport:
    def __init__(self, responder):
        self.calls = []
        self.responder = responder

    def __call__(self, url, headers, timeout=60):
        parsed = urllib.parse.urlparse(url)
        self.calls.append((parsed.scheme, parsed.netloc, parsed.path, dict(urllib.parse.parse_qsl(parsed.query)), dict(headers)))
        return self.responder(parsed.path, dict(urllib.parse.parse_qsl(parsed.query)), len(self.calls))


def auction_day(day, price=10.0, code="N"):
    return {"d": day, "o": [{"c": "O", "p": price, "t": f"{day}T13:30:00Z", "x": code}],
            "c": [{"c": "6", "p": price + 0.1, "t": f"{day}T20:00:00Z", "x": code}]}


class Client(unittest.TestCase):
    def test_only_data_host_and_two_paths(self):
        transport = FakeTransport(lambda path, q, n: (200, b'{"auctions": {}, "next_page_token": null}', {}))
        client = ca.Client(FAKE_HEADERS, NoWaitLimiter(), transport=transport, sleep=lambda s: None)
        client.get(ca.AUCTIONS_PATH, {"symbols": "A"})
        with self.assertRaises(ValueError):
            client.get("/v2/orders", {})
        with self.assertRaises(ValueError):
            client.get("/v2/account", {})
        scheme, host, path, _, headers = transport.calls[0]
        self.assertEqual((scheme, host, path), ("https", "data.alpaca.markets", "/v2/stocks/auctions"))
        self.assertEqual(headers, FAKE_HEADERS)
        self.assertEqual(len(transport.calls), 1)

    def test_retries_429_and_5xx_then_succeeds(self):
        answers = [(429, b"", {"x-ratelimit-reset": "0"}), (503, b"", {}), (200, b'{"quotes": {}, "next_page_token": null}', {"x-ratelimit-limit": "10000"})]
        transport = FakeTransport(lambda path, q, n: answers[n - 1])
        sleeps = []
        client = ca.Client(FAKE_HEADERS, NoWaitLimiter(), transport=transport, sleep=sleeps.append)
        self.assertEqual(client.get(ca.QUOTES_PATH, {})["quotes"], {})
        self.assertEqual(len(sleeps), 2)
        self.assertEqual(client.tally["http_429"], 1)
        self.assertEqual(client.rate_limit_header, "10000")

    def test_non_retryable_status_raises(self):
        transport = FakeTransport(lambda path, q, n: (403, b"forbidden", {}))
        client = ca.Client(FAKE_HEADERS, NoWaitLimiter(), transport=transport, sleep=lambda s: None)
        with self.assertRaises(RuntimeError):
            client.get(ca.AUCTIONS_PATH, {})

    def test_pagination(self):
        pages = [{"auctions": {"A": [auction_day("2023-03-01")]}, "next_page_token": "t1"},
                 {"auctions": {"A": [auction_day("2023-03-01", 11.0)]}, "next_page_token": None}]
        transport = FakeTransport(lambda path, q, n: (200, json.dumps(pages[n - 1]).encode(), {}))
        client = ca.Client(FAKE_HEADERS, NoWaitLimiter(), transport=transport, sleep=lambda s: None)
        merged, n_pages = ca.fetch_auctions(client, "2023-03-01", ["A"])
        self.assertEqual(n_pages, 2)
        self.assertEqual(len(merged["A"]), 2)
        self.assertEqual(transport.calls[1][3]["page_token"], "t1")
        q = transport.calls[0][3]
        self.assertEqual((q["feed"], q["start"], q["end"], q["limit"]), ("sip", "2023-03-01T00:00:00Z", "2023-03-01T23:59:59Z", "10000"))


class RateLimit(unittest.TestCase):
    def test_boundary_is_next_0330_new_york(self):
        start = datetime(2026, 9, 25, 3, 12, tzinfo=timezone.utc)  # 23:12 EDT on 09-24
        self.assertEqual(ca.late_boundary_after(start), datetime(2026, 9, 25, 7, 30, tzinfo=timezone.utc))
        start = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)  # 04:00 EDT
        self.assertEqual(ca.late_boundary_after(start), datetime(2026, 9, 26, 7, 30, tzinfo=timezone.utc))
        start = datetime(2026, 12, 1, 5, 0, tzinfo=timezone.utc)  # 00:00 EST
        self.assertEqual(ca.late_boundary_after(start), datetime(2026, 12, 1, 8, 30, tzinfo=timezone.utc))

    def test_limiter_spacing_switches_after_boundary(self):
        clock = [0.0]
        wall = [datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc)]
        sleeps = []

        def sleep(s):
            sleeps.append(s)
            clock[0] += s

        limiter = ca.RateLimiter(2000, datetime(2026, 9, 25, 7, 30, tzinfo=timezone.utc),
                                 clock=lambda: clock[0], wall=lambda: wall[0], sleep=sleep)
        for _ in range(3):
            limiter.wait()
        self.assertAlmostEqual(sum(sleeps), 2 * 60 / 2000)
        wall[0] = datetime(2026, 9, 25, 7, 31, tzinfo=timezone.utc)
        sleeps.clear()
        limiter.wait()
        limiter.wait()
        self.assertAlmostEqual(sum(sleeps), 60 / 2000 + 60 / 500)
        self.assertEqual(limiter.current_rate(), 500)


class Workflows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.events = [
            {"event_id": "1:A", "symbol": "A", "session": "2023-03-01", "window": "overnight", "exchange": "NYSE",
             "entry_utc": "2023-03-01T14:30:00Z"},
            {"event_id": "2:B", "symbol": "B", "session": "2023-03-01", "window": "rth", "exchange": "NASDAQ",
             "entry_utc": "2023-03-01T15:00:05Z"},
            {"event_id": "3:A", "symbol": "A", "session": "2023-03-02", "window": "overnight", "exchange": "NYSE",
             "entry_utc": "2023-03-02T14:30:00Z"},
            {"event_id": "4:C", "symbol": "C", "session": "2023-03-02", "window": "rth", "exchange": "NASDAQ",
             "entry_utc": "2023-03-02T16:00:00Z"},
        ]
        self.events_path = self.dir / "events.jsonl.gz"
        with gzip.open(self.events_path, "wt") as fh:
            for e in self.events:
                fh.write(json.dumps(e) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def responder(self, path, q, n):
        if path == ca.AUCTIONS_PATH:
            day = q["start"][:10]
            out = {}
            for sym in q["symbols"].split(","):
                if sym == "C":
                    continue  # no auction record for C
                out[sym] = [auction_day(day, code="Q" if sym != "A" else "N")]
            return 200, json.dumps({"auctions": out, "next_page_token": None}).encode(), {}
        if path == ca.QUOTES_PATH:
            sym = q["symbols"]
            quotes = [] if sym == "C" else [{"bp": 0, "ap": 10.0, "t": q["start"]}, {"bp": 9.99, "ap": 10.01, "t": q["start"]}]
            return 200, json.dumps({"quotes": {sym: quotes}, "next_page_token": None}).encode(), {}
        return 404, b"", {}

    def run_cmd(self, command, transport):
        with redirect_stdout(io.StringIO()):
            ca.main([command, "--events", str(self.events_path), "--out", str(self.dir), "--rate", "2000", "--workers", "2"],
                    transport=transport, credentials=FAKE_HEADERS)

    def test_auctions_collect_materialize_and_resume(self):
        transport = FakeTransport(self.responder)
        self.run_cmd("auctions", transport)
        self.assertEqual(len(transport.calls), 2)  # one request per session date
        summary = json.loads((self.dir / "auctions/auctions-summary.json").read_text())
        self.assertEqual(summary["coverage"]["symbol_sessions_wanted"], 4)
        self.assertEqual(summary["coverage"]["no_auction_record"], 1)
        self.assertEqual(summary["coverage"]["both_available"], 3)
        self.assertEqual(summary["rows"], 3)
        rows = [json.loads(l) for l in gzip.open(self.dir / "auctions/auctions.jsonl.gz", "rt")]
        self.assertEqual([(r["session"], r["symbol"]) for r in rows], [("2023-03-01", "A"), ("2023-03-01", "B"), ("2023-03-02", "A")])
        first = (self.dir / "auctions/auctions.jsonl.gz").read_bytes()
        self.run_cmd("auctions", transport)
        self.assertEqual(len(transport.calls), 2)  # ledger: nothing re-requested
        self.assertEqual((self.dir / "auctions/auctions.jsonl.gz").read_bytes(), first)  # deterministic bytes
        tallies = list(self.dir.glob("http-tally-auctions-*.json"))
        self.assertTrue(tallies)
        text = "".join(p.read_text() for p in tallies) + (self.dir / "auctions/ledger.jsonl").read_text()
        self.assertNotIn("fake-secret", text)
        self.assertNotIn("fake-id", text)

    def test_spreads_only_rth_events_first_valid_quote(self):
        transport = FakeTransport(self.responder)
        self.run_cmd("spreads", transport)
        self.assertEqual(len(transport.calls), 2)
        q = {c[3]["symbols"]: c[3] for c in transport.calls}
        self.assertEqual(q["B"]["start"], "2023-03-01T15:00:05Z")
        self.assertEqual(q["B"]["end"], "2023-03-01T15:01:05Z")
        self.assertEqual((q["B"]["feed"], q["B"]["limit"]), ("sip", "10"))
        summary = json.loads((self.dir / "spreads/spreads-summary.json").read_text())
        self.assertEqual(summary["counts"], {"events": 2, "no_valid_quote": 1})
        self.assertAlmostEqual(summary["half_spread_bps"]["median"], 10.0, places=2)


class Credentials(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(os.path.realpath(self.tmp.name))
        os.chmod(self.dir, 0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_literal_variables_from_a_private_file(self):
        path = self.dir / "paper.env"
        path.write_text("# comment\nexport APCA_API_KEY_ID=abc123\nAPCA_API_SECRET_KEY='def456'\nOTHER=$(rm -rf /)\n")
        os.chmod(path, 0o600)
        headers = ca.read_credentials(str(path))
        self.assertEqual(headers, {"APCA-API-KEY-ID": "abc123", "APCA-API-SECRET-KEY": "def456"})

    def test_refuses_group_readable_file_without_leaking_values(self):
        path = self.dir / "paper.env"
        path.write_text("APCA_API_KEY_ID=abc123\nAPCA_API_SECRET_KEY=def456\n")
        os.chmod(path, 0o644)
        with self.assertRaises(SystemExit) as ctx:
            ca.read_credentials(str(path))
        self.assertNotIn("abc123", str(ctx.exception))
        self.assertNotIn("def456", str(ctx.exception))
        self.assertNotIn(str(path), str(ctx.exception))

    def test_refuses_missing_variables(self):
        path = self.dir / "paper.env"
        path.write_text("APCA_API_KEY_ID=abc123\n")
        os.chmod(path, 0o600)
        with self.assertRaises(SystemExit):
            ca.read_credentials(str(path))


if __name__ == "__main__":
    unittest.main()
