"""Synthetic tests for the Alpaca history fixture runner: a stubbed HTTP layer, made-up tickers, prices and keys.

No network, no credentials and no private package rows. The delisting fixture is built from the repository's
own EDGAR classification artifact, as the protocol pins it.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("alpaca_history_fixture", ROOT / "blueprints/us-equities/alpaca-history-fixture/fixture.py")
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)
PROTOCOL, PROTOCOL_SHA = F.load_protocol()
FAKE_KEY, FAKE_SECRET = "PKTESTKEYVALUE0000001", "testsecretvalue0000000000000000000000001"


def business_days(start, end):
    d, out = date.fromisoformat(start), []
    while d <= date.fromisoformat(end):
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


SESSIONS = business_days("2016-01-04", "2020-06-30")


def bar(day, close, volume=1000):
    return {"t": f"{day}T05:00:00Z", "o": close, "h": close, "l": close, "c": close, "v": volume}


class FakeMarket:
    """A stand-in for data.alpaca.markets with Alpaca's documented asof semantics.

    Each entity has bars by date and a list of (symbol, first, last) tenures. asof '-' answers by the literal
    symbol; asof D answers with the full history of the entity holding the symbol on D, or by the literal symbol
    when no entity holds it on D; no asof means the run date."""

    def __init__(self, run_date="2026-09-25"):
        self.entities, self.auctions, self.calls, self.run_date = {}, {}, [], run_date
        self.add("SPY-ENTITY", {d: bar(d, 100.0) for d in SESSIONS}, [("SPY", "2016-01-01", "2099-01-01")])

    def add(self, name, bars, tenures):
        self.entities[name] = {"bars": bars, "tenures": tenures}

    def holder(self, symbol, on):
        for name, entity in sorted(self.entities.items()):
            if any(s == symbol and first <= on <= last for s, first, last in entity["tenures"]):
                return name
        return None

    def literal(self, symbol):
        out = {}
        for entity in self.entities.values():
            for s, first, last in entity["tenures"]:
                if s == symbol:
                    out.update({d: b for d, b in entity["bars"].items() if first <= d <= last})
        return out

    def series(self, symbol, asof):
        if asof == "-":
            return self.literal(symbol)
        name = self.holder(symbol, asof or self.run_date)
        return dict(self.entities[name]["bars"]) if name else self.literal(symbol)

    def __call__(self, url, headers, timeout):
        parts = urlsplit(url)
        assert parts.scheme == "https" and parts.hostname == "data.alpaca.markets", url
        assert headers["APCA-API-KEY-ID"] == FAKE_KEY
        q = dict(parse_qsl(parts.query))
        self.calls.append((parts.path, q))
        symbol, start, end = q["symbols"], q["start"], q["end"]
        if parts.path == "/v2/stocks/bars":
            items = [b for d, b in sorted(self.series(symbol, q.get("asof")).items()) if start <= d <= end]
            body = {"bars": {symbol: items} if items else {}, "next_page_token": None}
        else:
            name = self.holder(symbol, q.get("asof") or self.run_date)
            days = self.auctions.get(name, {})
            items = [a for d, a in sorted(days.items()) if start <= d <= end]
            body = {"auctions": {symbol: items} if items else {}, "next_page_token": None}
        headers_out = {"X-RateLimit-Limit": "10000", "X-RateLimit-Remaining": "9990",
                       "X-RateLimit-Reset": str(int(time.time()) + 60)}
        return 200, headers_out, json.dumps(body).encode()


def live_source(market, protocol=PROTOCOL):
    client = F.DataClient(FAKE_KEY, FAKE_SECRET, protocol, transport=market, sleep=lambda s: None)
    return F.LiveSource(protocol, client), client


class FakeClock:
    def __init__(self):
        self.now, self.slept = 1000.0, []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(round(seconds, 3))
        self.now += seconds

    def wall(self):
        return 5000.0 + self.now


class ProtocolPins(unittest.TestCase):
    def test_frozen_gate_definitions_match_the_gates_file(self):
        F.check_gates(PROTOCOL)
        broken = copy.deepcopy(PROTOCOL)
        broken["gates"]["dated-security-identity"]["flip_condition"]["equals"] = 1
        with self.assertRaises(F.FixtureError):
            F.check_gates(broken)

    def test_repo_pins_hold(self):
        F.check_repo_pins(PROTOCOL)

    def test_rate_budget_is_at_or_below_the_verified_limit(self):
        budget = PROTOCOL["rate_budget"]
        self.assertEqual(budget["verified_plan_limit_per_minute"], 10000)
        self.assertLessEqual(budget["client_cap_per_minute"], budget["verified_plan_limit_per_minute"])
        self.assertEqual(budget["concurrency"], 1)

    def test_plan_facts_carry_dated_official_urls(self):
        for fact in PROTOCOL["plan_facts"]["verified"]:
            self.assertTrue(fact["url"].startswith("https://") and "alpaca.markets" in fact["url"], fact)
            self.assertIn("page_last_updated", fact)
        self.assertEqual(PROTOCOL["plan_facts"]["read_on"], "2026-09-25")

    def test_feed_and_adjustments(self):
        self.assertEqual(PROTOCOL["data_request"]["feed"], "sip")
        self.assertEqual(sorted(PROTOCOL["data_request"]["adjustments"]), ["raw", "split"])

    def test_delisting_fixture_reproduces_the_pinned_rows(self):
        rows = F.build_delistings(PROTOCOL)
        self.assertEqual(len(rows), 1236)
        self.assertEqual({y: sum(1 for r in rows if r["year"] == y) for y in F.YEARS},
                         {"2016": 378, "2017": 296, "2018": 268, "2019": 294})

    def test_a_changed_artifact_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_bytes(F.DELISTING_ARTIFACT.read_bytes() + b" ")
            with self.assertRaises(F.FixtureError):
                F.build_delistings(PROTOCOL, path)


class Boundary(unittest.TestCase):
    def test_only_the_two_data_paths_are_built(self):
        self.assertTrue(F.checked_url("/v2/stocks/bars", {"symbols": "ABC"}).startswith("https://data.alpaca.markets/v2/stocks/bars?"))
        for path in ("/v2/orders", "/v2/account", "/v2/positions", "/v2/assets", "/v1/corporate-actions", "/v2/stocks/ABC/bars"):
            with self.assertRaises(F.RefusedRequest):
                F.checked_url(path, {"symbols": "ABC"})

    def test_a_refused_path_never_reaches_the_transport(self):
        calls = []
        client = F.DataClient(FAKE_KEY, FAKE_SECRET, PROTOCOL, transport=lambda *a: calls.append(a), sleep=lambda s: None)
        with self.assertRaises(F.RefusedRequest):
            client.fetch("/v2/orders", {"symbols": "ABC"})
        self.assertEqual(calls, [])

    def test_default_transport_refuses_other_hosts_before_any_network(self):
        for url in ("https://paper-api.alpaca.markets/v2/orders", "https://api.alpaca.markets/v2/account",
                    "http://data.alpaca.markets/v2/stocks/bars"):
            with self.assertRaises(F.RefusedRequest):
                F.default_transport(url, {}, 1)

    def test_redirects_are_refused(self):
        with self.assertRaises(F.RefusedRequest):
            F._RefuseRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.com/")


class Credentials(unittest.TestCase):
    def test_keys_come_only_from_the_environment(self):
        with self.assertRaises(F.FixtureError) as ctx:
            F.keys_from_env({"APCA_API_KEY_ID": FAKE_KEY})
        self.assertNotIn(FAKE_KEY, str(ctx.exception))
        self.assertEqual(F.keys_from_env({"APCA_API_KEY_ID": FAKE_KEY, "APCA_API_SECRET_KEY": FAKE_SECRET}), (FAKE_KEY, FAKE_SECRET))

    def test_public_output_check(self):
        F.assert_public('{"a": "sha256 0d98909f091fb4d0", "path": "/v2/stocks/bars"}', (FAKE_KEY,))
        # Assembled at runtime so this file itself carries no UUID or home path for the publication scan.
        uuid_text = "-".join(("123e4567", "e89b", "12d3", "a456", "426614174000"))
        for text in (f'"{FAKE_SECRET}"', f'"{uuid_text}"', '"/' + 'Users/someone/x"',
                     '"/' + 'home/someone/x"', '"/private/var/folders/x"'):
            with self.assertRaises(F.FixtureError):
                F.assert_public(text, (FAKE_KEY, FAKE_SECRET))


def response(status, headers=None, body=None):
    return status, headers or {}, json.dumps(body if body is not None else {"bars": {}, "next_page_token": None}).encode()


class RateBudget(unittest.TestCase):
    def client(self, replies, protocol=PROTOCOL):
        clock = FakeClock()
        replies = list(replies)
        client = F.DataClient(FAKE_KEY, FAKE_SECRET, protocol, transport=lambda *a: replies.pop(0),
                              clock=clock.clock, sleep=clock.sleep, wall=clock.wall)
        return client, clock

    def test_header_lowers_the_cap_to_half_the_observed_limit(self):
        client, _ = self.client([response(200, {"X-RateLimit-Limit": "200", "X-RateLimit-Remaining": "199"})])
        self.assertEqual(client.fetch("/v2/stocks/bars", {"symbols": "ABC"})["status"], "ok")
        self.assertEqual((client.cap, client.rate_limit_header), (100, 200))

    def test_429_honours_retry_after_then_succeeds(self):
        client, clock = self.client([response(429, {"Retry-After": "3"}), response(200)])
        self.assertEqual(client.fetch("/v2/stocks/bars", {"symbols": "ABC"})["status"], "ok")
        self.assertEqual(client.retries, 1)
        self.assertIn(3.0, clock.slept)

    def test_server_errors_back_off_exponentially_and_give_up(self):
        client, clock = self.client([response(503)] * 6)
        self.assertEqual(client.fetch("/v2/stocks/bars", {"symbols": "ABC"}), {"status": "error", "http": 503})
        self.assertEqual(client.retries, 5)
        self.assertEqual([s for s in clock.slept if s >= 1], [1.0, 2.0, 4.0, 8.0, 16.0])

    def test_client_errors_are_not_retried(self):
        client, _ = self.client([response(422)])
        self.assertEqual(client.fetch("/v2/stocks/bars", {"symbols": "ABC"}), {"status": "error", "http": 422})
        self.assertEqual(client.retries, 0)

    def test_auth_refusal_stops_the_run(self):
        client, _ = self.client([response(403)])
        with self.assertRaises(F.AbortRun):
            client.fetch("/v2/stocks/bars", {"symbols": "ABC"})

    def test_headroom_waits_for_the_reset(self):
        clock = FakeClock()
        reset = str(int(clock.wall() + 30))
        replies = [response(200, {"X-RateLimit-Limit": "10000", "X-RateLimit-Remaining": "10", "X-RateLimit-Reset": reset})]
        client = F.DataClient(FAKE_KEY, FAKE_SECRET, PROTOCOL, transport=lambda *a: replies.pop(0),
                              clock=clock.clock, sleep=clock.sleep, wall=clock.wall)
        client.fetch("/v2/stocks/bars", {"symbols": "ABC"})
        self.assertTrue(any(25 <= s <= 30 for s in clock.slept), clock.slept)

    def test_sliding_window_enforces_the_cap(self):
        protocol = copy.deepcopy(PROTOCOL)
        protocol["rate_budget"]["client_cap_per_minute"] = 2
        client, clock = self.client([response(200)] * 3, protocol)
        for _ in range(3):
            client.fetch("/v2/stocks/bars", {"symbols": "ABC"})
        self.assertGreaterEqual(clock.now - 1000.0, 60.0)

    def test_request_ceiling_stops_the_run(self):
        protocol = copy.deepcopy(PROTOCOL)
        protocol["rate_budget"]["request_ceiling"] = 1
        client, _ = self.client([response(200)] * 2, protocol)
        client.fetch("/v2/stocks/bars", {"symbols": "ABC"})
        with self.assertRaises(F.AbortRun):
            client.fetch("/v2/stocks/bars", {"symbols": "ABC"})

    def test_pagination_merges_pages_and_refuses_a_repeated_token(self):
        pages = [response(200, body={"bars": {"ABC": [bar("2016-01-04", 1.0)]}, "next_page_token": "t1"}),
                 response(200, body={"bars": {"ABC": [bar("2016-01-05", 2.0)]}, "next_page_token": None})]
        client, _ = self.client(pages)
        got = client.fetch("/v2/stocks/bars", {"symbols": "ABC"})
        self.assertEqual((got["status"], len(got["items"]), got["pages"]), ("ok", 2, 2))
        loop = [response(200, body={"bars": {"ABC": []}, "next_page_token": "same"})] * 3
        client, _ = self.client(loop)
        self.assertEqual(client.fetch("/v2/stocks/bars", {"symbols": "ABC"}), {"status": "error", "http": "pagination"})


def ok(bars_by_date):
    return {"status": "ok", "items": [bars_by_date[d] for d in sorted(bars_by_date)]}


class DelistingRule(unittest.TestCase):
    filed = "2018-06-15"

    def days(self, first, last):
        return {d: bar(d, 10.0) for d in SESSIONS if first <= d <= last}

    def verdict(self, bars_by_date, filed=None):
        return F.classify_delisting(filed or self.filed, ok(bars_by_date), SESSIONS)

    def test_covered_when_history_runs_to_the_event_and_stops(self):
        got = self.verdict(self.days("2017-01-02", "2018-06-20"))
        self.assertEqual(got["verdict"], "covered")
        self.assertFalse(got["clipped"])

    def test_bars_after_the_event_mean_another_issuer_or_no_delisting(self):
        self.assertEqual(self.verdict(self.days("2017-01-02", "2018-07-31"))["verdict"], "bars_continue_after_event")

    def test_history_that_ended_long_before_the_filing(self):
        self.assertEqual(self.verdict(self.days("2017-01-02", "2018-03-01"))["verdict"], "no_recent_bars")

    def test_thin_and_incomplete_windows(self):
        self.assertEqual(self.verdict(self.days("2018-06-01", "2018-06-14"))["verdict"], "thin_window")
        gappy = {d: b for i, (d, b) in enumerate(sorted(self.days("2017-06-01", "2018-06-15").items())) if i % 3}
        self.assertEqual(self.verdict(gappy)["verdict"], "incomplete_window")

    def test_windows_before_the_history_floor_are_clipped_not_failed(self):
        got = self.verdict(self.days("2016-01-04", "2016-01-20"), filed="2016-01-11")
        self.assertEqual(got["verdict"], "covered")
        self.assertTrue(got["clipped"])

    def test_no_bars_and_fetch_errors(self):
        self.assertEqual(self.verdict({})["verdict"], "no_bars")
        self.assertEqual(F.classify_delisting(self.filed, {"status": "error", "http": 500}, SESSIONS)["verdict"], "fetch_error")


def delisting_row(year, verdict, pit=True, symbol="ABC"):
    return {"year": year, "symbol": symbol, "pit": pit, "raw": {"verdict": verdict}, "split": {"verdict": verdict}}


class DelistingGate(unittest.TestCase):
    def rows(self, covered_share=1.0, pit=True):
        out = []
        for year in F.YEARS:
            for i in range(100):
                out.append(delisting_row(year, "covered" if i < covered_share * 100 else "no_bars", pit))
        return out

    def test_confirmed_only_when_every_year_reaches_95_percent_with_pit_symbols(self):
        self.assertEqual(F.summarize_delistings(PROTOCOL, self.rows(0.95))[1]["outcome"], "confirmed")
        self.assertEqual(F.summarize_delistings(PROTOCOL, self.rows(0.94))[1]["outcome"], "not_confirmed")
        self.assertEqual(F.summarize_delistings(PROTOCOL, self.rows(1.0, pit=False))[1]["outcome"], "not_confirmed")

    def test_fetch_errors_or_a_missing_map_are_not_evaluable(self):
        rows = self.rows(1.0)
        rows[0] = delisting_row("2016", "fetch_error")
        self.assertEqual(F.summarize_delistings(PROTOCOL, rows)[1]["outcome"], "not_evaluable")
        none = [{"year": y, "symbol": None, "pit": False, "raw": {"verdict": "no_symbol"}, "split": {"verdict": "no_symbol"}}
                for y in F.YEARS]
        per_year, gate = F.summarize_delistings(PROTOCOL, none)
        self.assertEqual(gate["outcome"], "not_evaluable")
        self.assertEqual(gate["proposed_receipt"]["years_covered"], [])


class TickerMap(unittest.TestCase):
    rows = [{"accession": "0000000000-16-000001"}, {"accession": "0000000000-16-000002"}]

    def load(self, entries):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            path.write_text(json.dumps({"schema": "alpaca-history-fixture/delisting-tickers/1", "rows": entries}))
            return F.load_ticker_map(PROTOCOL, path, self.rows)

    def test_pit_comes_from_the_provenance_class(self):
        got, digest = self.load({"0000000000-16-000001": {"symbol": "ABC", "provenance": "edgar_dei_trading_symbol", "source_ref": "x"},
                                 "0000000000-16-000002": {"symbol": "XYZ", "provenance": "name_candidate", "source_ref": "y"}})
        self.assertTrue(got["0000000000-16-000001"]["pit"])
        self.assertFalse(got["0000000000-16-000002"]["pit"])
        self.assertEqual(len(digest), 64)

    def test_invalid_rows_refuse_the_whole_map(self):
        good = {"symbol": "ABC", "provenance": "edgar_dei_trading_symbol", "source_ref": "x"}
        for entries in ({"9999999999-16-000009": good},
                        {"0000000000-16-000001": {**good, "provenance": "alpaca_bars"}},
                        {"0000000000-16-000001": {**good, "symbol": "abc$"}},
                        {"0000000000-16-000001": {**good, "source_ref": ""}}):
            with self.assertRaises(F.FixtureError):
                self.load(entries)


def identities_doc(collisions_extra=None):
    """15,418 synthetic symbols of which 235 collide, matching the protocol's pinned counts."""
    identities, collisions = {}, {}
    for i in range(15418):
        n, name = i, ""
        for _ in range(4):
            name = chr(ord("A") + n % 26) + name
            n //= 26
        entries = [{"id": f"id{i}a", "status": "active", "exchange": "NASDAQ"}]
        if i < 235:
            entries.append({"id": f"id{i}b", "status": "inactive", "exchange": "NYSE"})
            collisions[name] = entries
        identities[name] = entries
    return {"identities": identities, "collisions": collisions}


class Collisions(unittest.TestCase):
    def market(self):
        m = FakeMarket()
        old = {d: bar(d, 5.0 + i * 0.01) for i, d in enumerate(business_days("2016-01-04", "2017-06-30"))}
        new = {d: bar(d, 40.0 + i * 0.01) for i, d in enumerate(business_days("2018-01-02", "2019-12-31"))}
        m.add("OLD", old, [("ABC", "2016-01-01", "2017-06-30")])
        m.add("NEW", new, [("NEWP", "2018-01-01", "2018-12-31"), ("ABC", "2019-01-01", "2099-01-01")])
        return m

    def measure(self, market, symbol="ABC", asset_ids=2):
        source, _ = live_source(market)
        return F.measure_collision(PROTOCOL, symbol, {"asset_ids": asset_ids, "status_pattern": "active+inactive"}, SESSIONS, source)

    def test_two_issuers_are_dated_but_the_type_requirement_keeps_it_unresolved(self):
        got = self.measure(self.market())
        self.assertEqual((got["segments"], got["entities"], got["dated_resolved"]), (2, 2, True))
        self.assertEqual(got["reason"], "security_type_unavailable")
        self.assertFalse(got["resolved_frozen"])
        self.assertEqual(got["tenures"], [["2016-01-04", "2017-06-30"], ["2019-01-01", "2019-12-31"]])

    def test_a_long_halt_is_one_entity(self):
        m = FakeMarket()
        bars = {d: bar(d, 7.0) for d in business_days("2016-01-04", "2019-12-31") if not "2017-03-01" <= d <= "2017-05-01"}
        m.add("ONE", bars, [("HLT", "2016-01-01", "2099-01-01")])
        got = self.measure(m, "HLT")
        self.assertEqual((got["segments"], got["entities"], got["reason"]), (2, 1, "entity_count_mismatch"))

    def test_interleaved_tenures_overlap(self):
        m = FakeMarket()
        a = {d: bar(d, 3.0) for d in business_days("2016-01-04", "2019-12-31")}
        b = {d: bar(d, 9.0) for d in business_days("2016-01-04", "2019-12-31")}
        m.add("A", a, [("SWP", "2016-01-01", "2016-06-30"), ("SWP", "2018-01-01", "2019-12-31")])
        m.add("B", b, [("SWP", "2017-01-02", "2017-06-30")])
        self.assertEqual(self.measure(m, "SWP")["reason"], "overlapping_tenures")

    def test_a_probe_that_disagrees_with_the_literal_series_is_unattributed(self):
        m = self.market()
        # A one-day print under the literal symbol from a third party the mapping never returns.
        m.add("GHOST", {"2019-06-03": bar("2019-06-03", 99.0)}, [("ABC", "2019-06-03", "2019-06-03")])
        self.assertEqual(self.measure(m)["reason"], "unattributed_segment")

    def test_no_bars_and_gate_outcomes(self):
        self.assertEqual(self.measure(FakeMarket(), "NONE")["reason"], "no_bars")
        rows = [{"resolved_frozen": False, "dated_resolved": True, "reason": "security_type_unavailable"}] * 3
        summary, gate = F.summarize_collisions(PROTOCOL, rows, {"verdict": "pass"})
        self.assertEqual((gate["outcome"], gate["proposed_receipt"]["unresolved_collisions"], summary["undated_collisions"]),
                         ("fail", 3, 0))
        _, gate = F.summarize_collisions(PROTOCOL, [{"resolved_frozen": True, "dated_resolved": True, "reason": "x"}], {"verdict": "fail"})
        self.assertEqual(gate["outcome"], "fail")
        _, gate = F.summarize_collisions(PROTOCOL, [{"resolved_frozen": True, "dated_resolved": True, "reason": "x"}], {"verdict": "pass"})
        self.assertEqual(gate["outcome"], "pass")
        _, gate = F.summarize_collisions(PROTOCOL, [{"resolved_frozen": True, "dated_resolved": True, "reason": "x"}], None)
        self.assertEqual(gate["outcome"], "not_evaluable")
        _, gate = F.summarize_collisions(PROTOCOL, [{"resolved_frozen": False, "dated_resolved": False, "reason": "fetch_error"}], None)
        self.assertEqual(gate["outcome"], "not_evaluable")

    def test_collision_fixture_counts_are_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ids.json"
            path.write_text(json.dumps(identities_doc()))
            fixture, meta = F.build_collisions(PROTOCOL, identities_file=path)
            self.assertEqual((len(fixture), meta["count"]), (235, 235))
            self.assertNotIn("id0a", json.dumps(meta))
            doc = identities_doc()
            doc["collisions"].popitem()
            path.write_text(json.dumps(doc))
            with self.assertRaises(F.FixtureError):
                F.build_collisions(PROTOCOL, identities_file=path)


class ReusedTicker(unittest.TestCase):
    event_day = "2022-02-23"

    def market(self, swap=False):
        m = FakeMarket()
        old = {"2022-02-18": bar("2022-02-18", 10.0), "2022-02-22": bar("2022-02-22", 10.0), "2022-02-23": bar("2022-02-23", 19.389)}
        new = {"2022-02-22": bar("2022-02-22", 7.50), "2022-02-23": bar("2022-02-23", 7.48)}
        m.add("OLDCO", old, [("TEN", "2016-01-01", "2022-11-30")])
        m.add("NEWCO", new, [("TNP", "2016-01-01", "2024-01-01"), ("TEN", "2024-01-02", "2099-01-01")])
        m.auctions["OLDCO"] = {
            "2022-02-22": {"d": "2022-02-22", "o": [{"c": "O", "p": 10.0, "x": "N"}], "c": [{"c": "6", "p": 10.0, "x": "N", "s": 900}]},
            "2022-02-23": {"d": "2022-02-23", "o": [{"c": "O", "p": 15.0, "x": "N"}],
                           "c": [{"c": "6", "p": 19.40, "x": "P", "s": 5}, {"c": "6", "p": 19.389, "x": "N", "s": 5000}]}}
        if swap:
            m.entities["OLDCO"]["tenures"], m.entities["NEWCO"]["tenures"] = [], [("TEN", "2016-01-01", "2099-01-01")]
        return m

    def event(self):
        return {"ticker": "TEN", "date": self.event_day, "symbols": ["TEN"], "dataset_gain": 93.89, "computed_gain": -0.27}

    def test_asof_event_date_resolves_the_issuer_trading_then(self):
        source, _ = live_source(self.market())
        got = F.measure_reused(self.event(), source)
        self.assertEqual(got["verdict"], "pass")
        self.assertTrue(got["matches_catalogued"] and not got["matches_wrong_issuer"] and got["control_differs"])
        self.assertEqual(got["event_close_source"], "closing_print_listing_exchange")

    def test_the_later_holder_fails(self):
        source, _ = live_source(self.market(swap=True))
        self.assertEqual(F.measure_reused(self.event(), source)["verdict"], "fail")


class OwedRows(unittest.TestCase):
    def market(self):
        m = FakeMarket()
        m.add("X", {"2023-03-01": bar("2023-03-01", 1.00), "2023-03-02": bar("2023-03-02", 3.10)},
              [("XYZ", "2016-01-01", "2099-01-01")])
        return m

    def item(self, audit_gain, package_gain):
        return {"id": "2023-03-02:XYZ:0", "date": "2023-03-02", "ticker": "XYZ", "symbol": "XYZ",
                "audit_verdict": "mismatch", "audit_gain": audit_gain, "package_gain": package_gain}

    def test_reproduction_and_package_agreement_are_separate(self):
        source, _ = live_source(self.market())
        got = F.measure_owed(self.item(210.0, 180.0), source)
        self.assertEqual((got["verdict"], got["gain_pct"]), ("measured", 210.0))
        self.assertTrue(got["reproduces_audit"])
        self.assertFalse(got["agrees_package_official"])
        # The band is on the gain: 1.05 pp at +210%, so a 1.2 pp difference disagrees.
        self.assertFalse(F.measure_owed(self.item(211.2, 180.0), source)["reproduces_audit"])
        self.assertTrue(F.measure_owed(self.item(211.0, 180.0), source)["reproduces_audit"])

    def test_fixture_verdict_thresholds(self):
        rows = [{"verdict": "measured", "audit_verdict": "mismatch", "reproduces_audit": i < 124, "agrees_package_official": False,
                 "agrees_package_raw_bar": False, "agrees_package_split_bar": False} for i in range(130)]
        self.assertEqual(F.summarize_owed(rows)["verdict"], "reproduced")
        rows[123]["reproduces_audit"] = False
        self.assertEqual(F.summarize_owed(rows)["verdict"], "drifted")
        rows[0] = {"verdict": "fetch_error", "audit_verdict": "mismatch"}
        self.assertEqual(F.summarize_owed(rows)["verdict"], "not_evaluable")

    def test_owed_selection_is_pinned_by_hash_and_counts(self):
        summary_b = json.loads(F.AUDIT_SUMMARY_B.read_text())
        events, results = [], []
        plan = {"mismatch": 84, "recovered_mismatch": 45, "package_uncomputed_mismatch": 1, "match": 3}
        i = 0
        for verdict, n in plan.items():
            for _ in range(n):
                ev_id = f"2023-01-02:T{i}:{i}"
                events.append({"id": ev_id, "date": "2023-01-02", "ticker": f"T{i}"})
                results.append({"id": ev_id, "verdict": verdict, "symbol_used": f"T{i}", "alpaca_gain_pct": 100.0, "package_gain_pct": 50.0})
                i += 1
        doc = {"plan_sha256": PROTOCOL["fixtures"]["audit_owed_rows"]["audit_plan_sha256"], "rules": "v2",
               "summary": {"verdicts": summary_b["summary"]["verdicts"]}, "events": results}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.json"
            path.write_text(json.dumps(doc))
            with self.assertRaises(F.FixtureError):
                F.build_owed(PROTOCOL, events, path)  # the real pin is a different file
            protocol = copy.deepcopy(PROTOCOL)
            protocol["fixtures"]["audit_owed_rows"]["results_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            items, _ = F.build_owed(protocol, events, path)
            self.assertEqual(len(items), 130)
            results.pop(0)
            path.write_text(json.dumps(doc))
            protocol["fixtures"]["audit_owed_rows"]["results_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(F.FixtureError):
                F.build_owed(protocol, events, path)


def quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return F.main(argv)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        rows = F.build_delistings(PROTOCOL)
        self.early = next(r for r in rows if r["date_filed"] == "2016-01-04")
        self.mid = next(r for r in rows if r["date_filed"] >= "2018-06-01")
        self.market = FakeMarket()
        self.market.add("EARLY", {d: bar(d, 20.0) for d in business_days("2016-01-04", self.early["date_filed"])},
                        [("ERLY", "2016-01-01", "2016-01-20")])
        self.market.add("MID", {d: bar(d, 30.0) for d in business_days("2017-01-02", self.mid["date_filed"])},
                        [("MIDX", "2016-01-01", "2018-12-31")])
        self.market.add("OLD", {d: bar(d, 5.0) for d in business_days("2016-01-04", "2017-06-30")}, [("AAAA", "2016-01-01", "2017-06-30")])
        self.market.add("NEW", {d: bar(d, 40.0) for d in business_days("2018-01-02", "2019-12-31")}, [("AAAA", "2018-01-01", "2099-01-01")])
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.tickers = base / "tickers.json"
        self.tickers.write_text(json.dumps({"schema": "alpaca-history-fixture/delisting-tickers/1", "rows": {
            self.early["accession"]: {"symbol": "ERLY", "provenance": "exchange_delisting_notice", "source_ref": "notice"},
            self.mid["accession"]: {"symbol": "MIDX", "provenance": "current_submissions_ticker", "source_ref": "submissions"}}}))
        self.identities = base / "ids.json"
        self.identities.write_text(json.dumps(identities_doc()))
        self.base = base

    def tearDown(self):
        self.tmp.cleanup()

    def argv(self, command, out, receipt, *extra):
        return [command, "--delisting-tickers", str(self.tickers), "--symbol-identities", str(self.identities),
                "--out-dir", str(out), "--receipt", str(receipt), *extra]

    def test_run_then_evaluate_is_byte_identical_and_carries_no_secrets(self):
        env = {"APCA_API_KEY_ID": FAKE_KEY, "APCA_API_SECRET_KEY": FAKE_SECRET}
        with mock.patch.dict(os.environ, env), mock.patch.object(F, "default_transport", self.market), \
                mock.patch.object(F.time, "sleep", lambda s: None):
            self.assertEqual(quiet_main(self.argv("run", self.base / "run", self.base / "receipt-a.json")), 0)
        self.assertTrue(self.market.calls)
        self.assertTrue(all(path in F.ALLOWED_PATHS for path, _ in self.market.calls))
        self.assertTrue(all(q["feed"] == "sip" for _, q in self.market.calls))
        self.assertEqual(quiet_main(self.argv("evaluate", self.base / "eval", self.base / "receipt-b.json",
                                          "--snapshot", str(self.base / "run" / "snapshot.json"))), 0)
        a, b = (self.base / "receipt-a.json").read_bytes(), (self.base / "receipt-b.json").read_bytes()
        self.assertEqual(a, b)
        for path in (self.base / "receipt-a.json", self.base / "run" / "snapshot.json", self.base / "run" / "details.json"):
            text = path.read_text()
            self.assertNotIn(FAKE_KEY, text)
            self.assertNotIn(FAKE_SECRET, text)
        self.assertEqual(os.stat(self.base / "run" / "snapshot.json").st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.base / "run").st_mode & 0o777, 0o700)
        receipt = json.loads(a)
        F.assert_public(a.decode())
        self.assertEqual(receipt["fetch"]["rate_limit_header"], 10000)
        self.assertEqual(receipt["fetch"]["plan_check"], "rate_limit_header_matches_algo_trader_plus")
        years = receipt["fixtures"]["delistings"]["by_year"]
        self.assertEqual((years["2016"]["gate_covered"], years["2016"]["clipped_rows"]), (1, 1))
        self.assertEqual((years["2018"]["covered_raw"], years["2018"]["gate_covered"]), (1, 0))  # non-PIT symbol
        self.assertEqual(receipt["gates"]["pre-2020-delisting"]["outcome"], "not_confirmed")
        collisions = receipt["fixtures"]["collisions"]
        self.assertEqual((collisions["total"], collisions["unresolved_collisions"]), (235, 235))
        self.assertEqual(collisions["reasons"], {"no_bars": 234, "security_type_unavailable": 1})
        self.assertEqual(receipt["gates"]["dated-security-identity"]["outcome"], "fail")  # 235 unresolved, package or not

    def test_refusals(self):
        env = {"APCA_API_KEY_ID": FAKE_KEY, "APCA_API_SECRET_KEY": FAKE_SECRET}
        with mock.patch.dict(os.environ, env), mock.patch.object(F, "default_transport", self.market):
            self.assertEqual(quiet_main(self.argv("run", ROOT / "tmp-private-out", self.base / "r.json")), 2)
            self.assertFalse((ROOT / "tmp-private-out").exists())
            (self.base / "exists.json").write_text("{}")
            self.assertEqual(quiet_main(self.argv("run", self.base / "o", self.base / "exists.json")), 2)
        with mock.patch.dict(os.environ, {"APCA_API_KEY_ID": "", "APCA_API_SECRET_KEY": ""}):
            self.assertEqual(quiet_main(self.argv("run", self.base / "o2", self.base / "r2.json")), 2)
        self.assertEqual(self.market.calls, [])


if __name__ == "__main__":
    unittest.main()
