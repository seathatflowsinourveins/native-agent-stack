"""Synthetic fixtures for blueprints/us-equities/overnight-volume/watch.py (local integration; no network).

Every response below is written here, shaped after the BOATS and SIP payloads observed on 2026-09-29 01:14Z; none is a
recorded provider response, and no test makes a network request."""
from __future__ import annotations

import contextlib
import copy
import gzip
import hashlib
import io
import json
import stat
import sys
import tempfile
import unittest
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blueprints/us-equities/overnight-volume"))
import watch as W  # noqa: E402

M = W.M
TRADE_DATE = date(2026, 9, 29)
HOLIDAYS = {date(2026, 9, 7)}   # Labor Day
NOW = datetime(2026, 9, 29, 1, 30, tzinfo=timezone.utc)   # 21:30 ET on 2026-09-28, inside the overnight session


def sessions(first: date, last: date) -> list[date]:
    out, day = [], first
    while day <= last:
        if day.weekday() < 5 and day not in HOLIDAYS:
            out.append(day)
        day += timedelta(days=1)
    return out


SESSIONS = sessions(date(2026, 8, 17), date(2026, 9, 28))
DATES20 = SESSIONS[-20:]


def thresholds() -> dict:
    return W.load_thresholds(W.THRESHOLDS_PATH)


def sip_bar(day: date, c: float, v: int) -> dict:
    return {"t": f"{day.isoformat()}T04:00:00Z", "o": c, "h": c, "l": c, "c": c, "v": v, "n": 10, "vw": c}


def boats_bar(day: date, c: float, v: int) -> dict:
    return {"t": f"{day.isoformat()}T00:00:00Z", "o": c, "h": c, "l": c, "c": c, "v": v, "n": 5, "vw": c}


def snapshot(v: int, vw: float, c: float, bar_day: date = TRADE_DATE, prev_c: float | None = None,
             trade_at: str = "2026-09-29T01:29:30.123456789Z", bid: float | None = None, ask: float | None = None) -> dict:
    """A BOATS snapshot: dailyBar keyed at 00:00Z of its trade date, prevDailyBar the previous overnight session. The
    previous close defaults to twice the price, so a measure that read it would be visibly wrong."""
    bid = round(c - 0.01, 2) if bid is None else bid
    ask = round(c + 0.01, 2) if ask is None else ask
    prev_day = bar_day - timedelta(days=1)
    return {"dailyBar": {"t": f"{bar_day.isoformat()}T00:00:00Z", "o": c, "h": c, "l": c, "c": c, "v": v, "vw": vw, "n": 50},
            "prevDailyBar": {"t": f"{prev_day.isoformat()}T00:00:00Z", "o": c, "h": c, "l": c, "c": prev_c or c * 2, "v": v * 9, "vw": c, "n": 9},
            "minuteBar": {"t": "2026-09-29T01:29:00Z", "o": c, "h": c, "l": c, "c": c, "v": 100, "vw": c, "n": 1},
            "latestTrade": {"t": trade_at, "p": c, "s": 100, "x": "B", "c": ["@"], "i": 1, "z": "N"},
            "latestQuote": {"t": trade_at, "bp": bid, "ap": ask, "bs": 1, "as": 1, "bx": "B", "ax": "B", "c": [], "z": "N"}}


def row(symbol: str, dv: float | None, adv_fraction: float | None = None, change: float | None = None,
        relvol: float | None = None, prior: int = 20, fund: bool = False) -> dict:
    return {"s": symbol, "overnight_shares": 1000, "overnight_dollar_volume": dv, "adv20_shares": 1000.0,
            "adv_fraction": adv_fraction, "ref_close": 10.0, "close": 10.0, "change": change, "relvol_boats20": relvol,
            "prior_sessions": prior, "trades": 5, "last_trade_age_s": 1.0, "spread_bps": 10.0, "fund": fund}


class FakeResponse:
    def __init__(self, body: bytes, headers: dict | None = None):
        self.body, self.headers = body, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        return self.body


class Market:
    """A fake Alpaca: GET /v2/assets, /v2/stocks/bars (sip, boats) and /v2/stocks/snapshots, filtered like the API."""

    def __init__(self, drop_sip_day: date | None = None):
        self.assets, self.sip, self.boats, self.snaps, self.requests = [], {}, {}, {}, []
        self.remaining = "9990"
        self.add("SPY", "SPDR S&P 500 ETF Trust", adv=80_000_000, ref=765.61, boats={d: 60_000 for d in SESSIONS},
                 snap=snapshot(24_128, 765.100369, 764.46, prev_c=768.15))
        self.add("AAA", "Alpha Therapeutics Inc", adv=1_000_000, ref=10.0, boats={d: 2_000 for d in SESSIONS},
                 snap=snapshot(400_000, 11.0, 11.5))
        self.add("BBB", "Beta Corp", adv=5_000_000, ref=20.0, boats={d: 5_000 for d in DATES20[-12:]},
                 snap=snapshot(20_000, 20.5, 21.2))
        self.add("CCC", "Gamma Inc", adv=1_000_000, ref=5.0, boats={d: 1_000 for d in SESSIONS},
                 snap=snapshot(900_000, 6.0, 6.0, bar_day=date(2026, 9, 28)))   # no trade tonight: last session's bar
        self.add("DDD", "Delta 2x Leveraged ETF", adv=2_000_000, ref=50.0, boats={d: 10_000 for d in SESSIONS},
                 snap=snapshot(300_000, 45.0, 44.0))
        self.add("EEE", "Epsilon Ltd", adv=100_000, ref=1.5, boats={}, snap=snapshot(10_000, 2.0, 1.95))
        self.add("FFF", "Zeta Holdings", adv=50_000_000, ref=100.0, boats={d: 1_000 for d in DATES20[-5:]},
                 snap=snapshot(5_000, 100.2, 100.3))
        self.add("GGG", "Eta Inc", adv=300_000, ref=3.0, boats={}, snap=None)   # no snapshot returned
        self.add("HHH", "Theta Inc", attributes=("overnight_halted",))
        self.add("III", "Iota Inc", tradable=False)
        self.add("KKK", "Kappa Inc", attributes=())
        self.add("ABC/WS", "Warrant", tradable=True)
        for i in range(1200):
            self.add(f"F{i:04d}", f"Filler {i}")
        for bars in self.boats.values():   # the in-progress trade-date bar that a BOATS 1Day request can return
            if bars:
                bars.append(boats_bar(TRADE_DATE, bars[-1]["c"], 777))
        if drop_sip_day is not None:
            self.sip = {s: [b for b in bars if not b["t"].startswith(drop_sip_day.isoformat())] for s, bars in self.sip.items()}

    def add(self, symbol, name, adv=None, ref=None, boats=None, snap=None, attributes=("overnight_tradable",), tradable=True):
        self.assets.append({"symbol": symbol, "name": name, "status": "active", "class": "us_equity", "tradable": tradable,
                            "attributes": list(attributes)})
        if adv is not None:
            self.sip[symbol] = [sip_bar(d, ref, adv) for d in SESSIONS] + [sip_bar(TRADE_DATE, ref, adv)]
        if boats:
            self.boats[symbol] = [boats_bar(d, ref, v) for d, v in sorted(boats.items())]
        if snap is not None:
            self.snaps[symbol] = snap

    def urlopen(self, request, timeout=None):
        url, method = request.full_url, request.get_method()
        self.requests.append((method, url))
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parts.query)
        if method != "GET":
            raise AssertionError(f"unexpected {method}")
        if parts.path == "/v2/assets":
            body = self.assets
        elif parts.path == "/v2/stocks/bars":
            source = {"sip": self.sip, "boats": self.boats}[query["feed"][0]]
            start, end = query["start"][0], query["end"][0]
            bars = {s: [b for b in source.get(s, []) if start <= b["t"] <= end] for s in query["symbols"][0].split(",")}
            body = {"bars": {s: b for s, b in bars.items() if b}, "next_page_token": None}
        elif parts.path == "/v2/stocks/snapshots":
            if query["feed"][0] != "boats":
                raise AssertionError("snapshots must use feed=boats")
            body = {s: self.snaps[s] for s in query["symbols"][0].split(",") if s in self.snaps}
        else:
            raise AssertionError(f"unexpected path {parts.path}")
        return FakeResponse(json.dumps(body).encode(), {"X-Ratelimit-Limit": "10000", "X-Ratelimit-Remaining": self.remaining,
                                                        "X-Ratelimit-Reset": "1790000000"})


class FakeClock:
    """utcnow, monotonic and wait for Watch: waiting advances the clock; nothing sleeps."""

    def __init__(self, start: datetime):
        self.start, self.elapsed = start, 0.0

    def utcnow(self) -> datetime:
        return self.start + timedelta(seconds=self.elapsed)

    def monotonic(self) -> float:
        return self.elapsed

    def wait(self, seconds: float) -> bool:
        self.elapsed += seconds
        return False


def args(mode: str, out: Path, **extra) -> SimpleNamespace:
    values = {"mode": mode, "env_file": Path("unused.env"), "out": out, "thresholds": W.THRESHOLDS_PATH, "trade_date": None,
              "no_push": False, "symbols": None}
    values.update(extra)
    return SimpleNamespace(**values)


class SnapshotParsing(unittest.TestCase):
    def test_session_bar_uses_the_utc_date_of_the_boats_bar(self):
        snap = snapshot(24_128, 765.100369, 764.46)
        # 00:00Z on the trade date is 20:00 ET the evening before: an ET-day comparison (monitor.snapshot_features) would
        # place tonight's bar on 2026-09-28 and treat it as the previous session.
        self.assertEqual(M.et_day(snap["dailyBar"]["t"]), date(2026, 9, 28))
        self.assertIs(W.session_bar(snap, TRADE_DATE), snap["dailyBar"])
        self.assertIsNone(W.session_bar(snap, date(2026, 9, 28)))

    def test_session_bar_rejects_previous_sessions_and_sip_shaped_bars(self):
        self.assertIsNone(W.session_bar(snapshot(900_000, 6.0, 6.0, bar_day=date(2026, 9, 28)), TRADE_DATE))
        sip_shaped = {"dailyBar": {"t": "2026-09-28T04:00:00Z", "v": 1_000_000, "vw": 10.0, "c": 10.0}}
        self.assertIsNone(W.session_bar(sip_shaped, TRADE_DATE))
        self.assertIsNone(W.session_bar({}, TRADE_DATE))
        self.assertIsNone(W.session_bar(None, TRADE_DATE))
        self.assertIsNone(W.session_bar({"dailyBar": {"t": "2026-09-29T00:00:00Z", "c": 1.0}}, TRADE_DATE))   # no volume
        self.assertIsNone(W.session_bar({"dailyBar": {"t": "not a time", "v": 5}}, TRADE_DATE))

    def test_measures_use_the_sip_reference_never_prev_daily_bar(self):
        snap = snapshot(24_128, 765.100369, 764.46, prev_c=768.15, bid=764.51, ask=764.6)
        ctx = {"adv20": {"SPY": 80_000_000.0}, "ref_close": {"SPY": 765.61}, "base_sum": {"SPY": 1_200_000},
               "prior_sessions": {"SPY": 20}}
        got = W.measures("SPY", snap, TRADE_DATE, ctx, NOW, fund=True)
        self.assertEqual(got["s"], "SPY")
        self.assertEqual(got["overnight_shares"], 24_128)
        self.assertAlmostEqual(got["overnight_dollar_volume"], 24_128 * 765.100369, places=1)
        self.assertAlmostEqual(got["adv_fraction"], 24_128 / 80_000_000, places=6)
        self.assertAlmostEqual(got["change"], 764.46 / 765.61 - 1, places=6)   # not 764.46 / 768.15 - 1
        self.assertAlmostEqual(got["relvol_boats20"], 24_128 / 60_000, places=4)
        self.assertEqual(got["prior_sessions"], 20)
        self.assertEqual(got["ref_close"], 765.61)
        self.assertEqual(got["close"], 764.46)
        self.assertEqual(got["trades"], 50)
        self.assertAlmostEqual(got["last_trade_age_s"], 29.9, places=1)
        self.assertAlmostEqual(got["spread_bps"], round((764.6 - 764.51) / ((764.6 + 764.51) / 2) * 1e4, 1))
        self.assertTrue(got["fund"])

    def test_measures_without_reference_data(self):
        snap = snapshot(1_000, 5.0, 5.0)
        snap["latestQuote"] = {"bp": 0, "ap": 5.01}
        del snap["latestTrade"]
        got = W.measures("NEW", snap, TRADE_DATE, {"adv20": {}, "ref_close": {}, "base_sum": {}, "prior_sessions": {}}, NOW)
        self.assertEqual((got["overnight_shares"], got["overnight_dollar_volume"]), (1_000, 5_000.0))
        for key in ("adv20_shares", "adv_fraction", "ref_close", "change", "relvol_boats20", "last_trade_age_s", "spread_bps"):
            self.assertIsNone(got[key], key)
        self.assertEqual(got["prior_sessions"], 0)
        self.assertIsNone(W.measures("OLD", snapshot(9, 1.0, 1.0, bar_day=date(2026, 9, 28)), TRADE_DATE, {}, NOW))


class Universe(unittest.TestCase):
    def test_overnight_universe_reads_the_attributes_list(self):
        rules = thresholds()["universe"]
        assets = [
            {"symbol": "AAA", "name": "Alpha", "tradable": True, "status": "active", "class": "us_equity", "attributes": ["overnight_tradable", "has_options"]},
            {"symbol": "HLT", "name": "Halted", "tradable": True, "attributes": ["overnight_halted"]},
            {"symbol": "BTH", "name": "Both", "tradable": True, "attributes": ["overnight_tradable", "overnight_halted"]},
            {"symbol": "NOT", "name": "Untradable", "tradable": False, "attributes": ["overnight_tradable"]},
            {"symbol": "NON", "name": "No attribute", "tradable": True, "attributes": []},
            {"symbol": "TOP", "name": "Top-level flag only", "tradable": True, "overnight_tradable": True},
            {"symbol": "A/B", "name": "Slash", "tradable": True, "attributes": ["overnight_tradable"]},
            {"symbol": "A B", "name": "Space", "tradable": True, "attributes": ["overnight_tradable"]},
            {"symbol": "INA", "name": "Inactive", "tradable": True, "status": "inactive", "attributes": ["overnight_tradable"]},
            {"symbol": "CRY", "name": "Crypto", "tradable": True, "class": "crypto", "attributes": ["overnight_tradable"]},
            {"symbol": "NUL", "name": None, "tradable": True, "attributes": None},
        ]
        self.assertEqual(W.overnight_universe(assets, rules), {"AAA": "Alpha"})


class RelativeVolume(unittest.TestCase):
    def test_reference_takes_dates_adv20_and_the_prior_regular_close_from_sip_bars(self):
        sip = {"SPY": [sip_bar(d, 700.0 + i, 1_000 + i) for i, d in enumerate(SESSIONS)] + [sip_bar(TRADE_DATE, 1.0, 9)],
               "NEW": [sip_bar(d, 5.0, 100 * (i + 1)) for i, d in enumerate(SESSIONS[-5:])],
               "GAP": [sip_bar(d, 3.0, 50) for d in SESSIONS[:-1]]}   # no regular-session bar on 2026-09-28
        ref = W.reference(sip, TRADE_DATE)
        self.assertEqual(ref["dates20"], DATES20)
        self.assertEqual(ref["prior_session"], date(2026, 9, 28))
        spy_v = [1_000 + i for i in range(len(SESSIONS))]
        self.assertAlmostEqual(ref["adv20"]["SPY"], sum(spy_v[-20:]) / 20)          # the trade-date bar is excluded
        self.assertAlmostEqual(ref["adv20"]["NEW"], (100 + 200 + 300 + 400 + 500) / 5)   # monitor.AdvLoader: mean of <= 20
        self.assertEqual(ref["ref_close"]["SPY"], 700.0 + len(SESSIONS) - 1)
        self.assertEqual(ref["ref_close"]["NEW"], 5.0)
        self.assertNotIn("GAP", ref["ref_close"])
        self.assertAlmostEqual(ref["adv20"]["GAP"], 50.0)

    def test_adv20_matches_the_monitor_advloader_formula(self):
        volumes = [7 * i + 3 for i in range(len(SESSIONS))]
        sip = {"X": [sip_bar(d, 1.0, v) for d, v in zip(SESSIONS, volumes)]}
        loader = M.AdvLoader(["X"], TRADE_DATE)

        class OnePage:
            def alpaca_json(self, base, path, params):
                return {"bars": {"X": [{"v": v} for v in volumes]}, "next_page_token": None}

        self.assertAlmostEqual(W.reference(sip, TRADE_DATE)["adv20"]["X"], loader.run(OnePage())["X"])

    def test_baseline20_counts_only_the_twenty_dates_and_missing_dates_as_zero(self):
        boats = {"AAA": [boats_bar(d, 10.0, 2_000) for d in SESSIONS] + [boats_bar(TRADE_DATE, 10.0, 999_999)],
                 "BBB": [boats_bar(d, 20.0, 5_000) for d in DATES20[-12:]],
                 "OLD": [boats_bar(d, 1.0, 50_000) for d in SESSIONS[:-20]],   # only dates before the window
                 "DUP": [boats_bar(DATES20[0], 1.0, 300), boats_bar(DATES20[0], 1.0, 300)]}
        base = W.baseline20(boats, DATES20)
        self.assertEqual(base["base_sum"]["AAA"], 40_000)      # 20 x 2,000; the in-progress trade-date bar is not counted
        self.assertEqual(base["prior_sessions"]["AAA"], 20)
        self.assertEqual(base["base_sum"]["BBB"], 60_000)
        self.assertEqual(base["prior_sessions"]["BBB"], 12)
        self.assertNotIn("OLD", base["base_sum"])
        self.assertEqual((base["base_sum"]["DUP"], base["prior_sessions"]["DUP"]), (300, 1))
        ctx = {"adv20": {}, "ref_close": {}, **base}
        got = W.measures("BBB", snapshot(20_000, 20.5, 21.2), TRADE_DATE, ctx, NOW)
        self.assertAlmostEqual(got["relvol_boats20"], 20_000 / (60_000 / 20), places=4)   # 6.6667, divided by 20 not 12
        self.assertIsNone(W.measures("OLD", snapshot(5, 1.0, 1.0), TRADE_DATE, ctx, NOW)["relvol_boats20"])


class ThresholdSelection(unittest.TestCase):
    def test_committed_thresholds(self):
        th = thresholds()
        self.assertEqual(th["id"], "overnight-volume-watch-v1")
        self.assertEqual(th["session"]["trade_date"], "2026-09-29")
        self.assertEqual((th["sources"]["overnight_feed"], th["sources"]["reference_feed"]), ("boats", "sip"))
        self.assertEqual([t["by"] for t in th["top_n"]], ["relvol_boats20", "adv_fraction"])
        self.assertEqual(W.check_notify_url(th["alerts"]["ntfy_url"]), "http://127.0.0.1:18080/overnight-volume")

    def test_significant_tier_rules(self):
        tier = thresholds()["significant"]
        self.assertEqual(W.qualifies(row("A", 249_999, adv_fraction=0.9, change=0.9, relvol=99), tier), [])
        self.assertEqual(W.qualifies(row("A", None, adv_fraction=0.9), tier), [])
        self.assertEqual(W.qualifies(row("A", 250_000, adv_fraction=0.02), tier), ["adv_fraction"])
        self.assertEqual(W.qualifies(row("A", 250_000, adv_fraction=0.0199), tier), [])
        self.assertEqual(W.qualifies(row("A", 250_000, change=-0.05), tier), ["change"])
        self.assertEqual(W.qualifies(row("A", 250_000, change=0.0499), tier), [])
        self.assertEqual(W.qualifies(row("A", 250_000, relvol=5.0, prior=10), tier), ["relvol_boats20"])
        self.assertEqual(W.qualifies(row("A", 250_000, relvol=50.0, prior=9), tier), [])   # too few prior sessions
        self.assertEqual(W.qualifies(row("A", 300_000, adv_fraction=0.03, change=0.06, relvol=6.0), tier),
                         ["adv_fraction", "change", "relvol_boats20"])

    def test_notify_tier_is_stricter(self):
        th = thresholds()
        significant_only = row("S", 900_000, adv_fraction=0.04, change=0.08, relvol=8.0)
        self.assertTrue(W.qualifies(significant_only, th["significant"]))
        self.assertEqual(W.qualifies(significant_only, th["notify"]), [])
        self.assertEqual(W.qualifies(row("N", 1_000_000, change=0.10), th["notify"]), ["change"])
        self.assertEqual(W.qualifies(row("N", 1_000_000, relvol=10.0, prior=9), th["notify"]), [])

    def test_alerts_once_per_symbol_and_tier_with_push_caps(self):
        th = copy.deepcopy(thresholds())
        th["notify"]["max_per_session"] = 7
        alerts = W.Alerts(th)
        movers = [row(f"N{i}", 2_000_000 + i, change=0.2) for i in range(8)]
        fund = row("ETF1", 9_000_000, change=0.3, fund=True)
        first = alerts.cross(movers + [fund, row("S1", 300_000, change=0.06)], "t1")
        self.assertEqual(sum(r["tier"] == "significant" for r in first), 10)
        notify = [r for r in first if r["tier"] == "notify"]
        self.assertEqual(len(notify), 9)
        self.assertEqual(next(r for r in notify if r["s"] == "ETF1")["push"], "excluded_fund_name")
        self.assertTrue(all(r["push"] == "queued" for r in notify if r["s"] != "ETF1"))
        due1 = alerts.due()
        self.assertEqual(due1, ["N7", "N6", "N5", "N4", "N3"])   # at most five a sweep, largest dollar volume first
        for s in due1:
            alerts.record_push(s)
        self.assertEqual(alerts.cross(movers + [fund], "t2"), [])    # nothing alerts twice
        due2 = alerts.due()
        self.assertEqual(due2, ["N2", "N1"])                      # the session cap of 7 leaves two
        for s in due2:
            alerts.record_push(s)
        self.assertEqual(alerts.due(), [])
        upgraded = alerts.cross([row("S1", 1_500_000, change=0.12)], "t3")
        self.assertEqual([(r["tier"], r["s"]) for r in upgraded], [("notify", "S1")])
        self.assertEqual(alerts.due(), [])                         # queued, but the session cap is spent

    def test_dry_run_and_disabled_push_never_queue(self):
        alerts = W.Alerts(thresholds())
        records = alerts.cross([row("A", 2_000_000, change=0.2)], "t", dry_run=True)
        self.assertEqual({r["push"] for r in records if r["tier"] == "notify"}, {"dry_run"})
        self.assertTrue(all(r["dry_run"] for r in records))
        self.assertEqual(alerts.due(), [])
        disabled = W.Alerts(thresholds())
        records = disabled.cross([row("A", 2_000_000, change=0.2)], "t", push=False)
        self.assertEqual({r["push"] for r in records if r["tier"] == "notify"}, {"disabled"})
        self.assertEqual(disabled.due(), [])

    def test_restore_ignores_dry_run_records(self):
        records = [{"event": "alert", "tier": "significant", "s": "DRY", "dry_run": True},
                   {"event": "alert", "tier": "notify", "s": "DRY", "dry_run": True, "push": "dry_run"},
                   {"event": "alert", "tier": "significant", "s": "A", "dry_run": False},
                   {"event": "alert", "tier": "notify", "s": "A", "dry_run": False, "push": "queued"},
                   {"event": "alert", "tier": "notify", "s": "B", "dry_run": False, "push": "queued"},
                   {"event": "push", "s": "A", "status": "sent"}]
        alerts = W.Alerts(thresholds())
        self.assertEqual(alerts.restore(records), {"significant": 1, "notify": 2, "pushes": 1, "pending": 1})
        self.assertEqual(alerts.due(), ["B"])
        again = alerts.cross([row("DRY", 2_000_000, change=0.2), row("A", 2_000_000, change=0.2)], "t")
        self.assertEqual(sorted((r["tier"], r["s"]) for r in again), [("notify", "DRY"), ("significant", "DRY")])

    def test_top_n_filters_and_orders(self):
        spec = thresholds()["top_n"][0]
        rows = [row("B", 300_000, relvol=6.0), row("A", 300_000, relvol=6.0), row("C", 900_000, relvol=50.0),
                row("LOW", 249_999, relvol=99.0), row("FEW", 900_000, relvol=99.0, prior=9), row("NONE", 900_000)]
        self.assertEqual([r["s"] for r in W.top_n(rows, spec)], ["C", "A", "B"])
        many = [row(f"R{i:02d}", 300_000, relvol=float(i)) for i in range(40)]
        self.assertEqual(len(W.top_n(many, spec)), 25)
        second = thresholds()["top_n"][1]
        self.assertEqual([r["s"] for r in W.top_n([row("FEW", 900_000, adv_fraction=0.5, prior=0)], second)], ["FEW"])

    def test_notice_text(self):
        at = datetime(2026, 9, 29, 4, 42, tzinfo=timezone.utc)
        text = W.notice_text(row("XYZ", 3_200_000, adv_fraction=0.061, change=0.124, relvol=14.2), date(2026, 9, 28), at)
        self.assertEqual(text, "overnight XYZ $3.2M 6.1% ADV +12.4% vs 09-28 close relvol 14 00:42 ET")
        text = W.notice_text(row("NEW", 850_000, change=-0.2, relvol=30.0, prior=3), date(2026, 9, 28), at)
        self.assertEqual(text, "overnight NEW $850k -20.0% vs 09-28 close 00:42 ET")


class PlanAndSession(unittest.TestCase):
    def test_plan_for_the_observed_universe(self):
        plan = W.plan_calls(9_683, thresholds()["sources"])
        self.assertEqual(plan["per_sweep"], {"snapshots": 20})
        self.assertEqual(plan["once"], {"assets": 5})
        self.assertEqual(plan["per_minute"], {"adv_bars": 98})
        self.assertEqual(plan["startup_calls"], 99)
        self.assertEqual((plan["data_per_min"], plan["data_first_min"], plan["data_cap_per_min"]), (10.0, 108.0, 500.0))
        self.assertEqual(plan["refusals"], [])

    def test_plan_refuses_above_five_percent_of_the_data_limit(self):
        sources = thresholds()["sources"]
        self.assertEqual(W.plan_calls(9_683, sources, sweep_seconds=2)["refusals"], ["data_calls_above_5pct_of_limit"])
        self.assertEqual(W.plan_calls(9_683, sources, sweep_seconds=0)["refusals"], ["invalid_bounds"])
        self.assertEqual(W.plan_calls(0, sources)["refusals"], ["empty_universe"])

    def test_stop_times(self):
        stop_at, backstop = W.stop_times(TRADE_DATE, thresholds()["session"])
        self.assertEqual(stop_at, datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc))
        self.assertEqual(backstop, datetime(2026, 9, 29, 8, 5, tzinfo=timezone.utc))


class Network(unittest.TestCase):
    def test_allow_list_refuses_before_any_request_or_budget(self):
        for url in ("https://paper-api.alpaca.markets/v2/assets?status=active&asset_class=us_equity",
                    "https://data.alpaca.markets/v2/stocks/snapshots?symbols=SPY&feed=boats",
                    "https://data.alpaca.markets/v2/stocks/bars?symbols=SPY&feed=sip"):
            self.assertEqual(W.allowed_get(url), url)
        refused = ("https://paper-api.alpaca.markets/v2/orders", "https://paper-api.alpaca.markets/v2/positions",
                   "https://paper-api.alpaca.markets/v2/account", "https://api.alpaca.markets/v2/assets",
                   "http://data.alpaca.markets/v2/stocks/bars", "https://data.alpaca.markets/v2/stocks/trades",
                   "https://data.alpaca.markets/v1beta1/screener/stocks/movers",
                   "https://data.alpaca.markets/v2/stocks/snapshots/../../v2/orders",
                   "https://user:pw@data.alpaca.markets/v2/stocks/bars", "https://data.alpaca.markets.example/v2/stocks/bars")
        budget = M.Budget(per_sweep={"snapshots": 5}, once={"assets": 5}, per_minute={"adv_bars": 5})
        http = W.GuardedHttp({"APCA-API-KEY-ID": "k", "APCA-API-SECRET-KEY": "s"}, budget)
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("no request may be made")) as opened:
            for url in refused:
                with self.assertRaises(W.NotAllowed, msg=url):
                    http.get(url, "alpaca", http.alpaca)
            opened.assert_not_called()
        self.assertEqual((dict(budget.used), dict(budget.used_once), dict(http.source_calls)), ({}, {}, {}))

    def test_ratelimit_floor_honours_fresh_readings_only(self):
        clock = [100.0]
        http = W.GuardedHttp({}, None, clock=lambda: clock[0])
        self.assertEqual(W.data_floor(http), (True, None))
        low = FakeResponse(b"{}", {"X-Ratelimit-Limit": "10000", "X-Ratelimit-Remaining": "1200"})
        with mock.patch("urllib.request.urlopen", return_value=low):
            http.get("https://data.alpaca.markets/v2/stocks/snapshots?symbols=SPY&feed=boats", "alpaca", {})
        clock[0] += 30
        self.assertEqual(W.data_floor(http), (False, 1200))
        clock[0] += 31   # a reading more than 60 s old says nothing about the current window
        self.assertEqual(W.data_floor(http), (True, None))

    def test_daily_bars_pages_and_resumes_without_repeating_requests(self):
        symbols = [f"S{i:03d}" for i in range(450)]
        calls = []
        failed = []

        class Http:
            def alpaca_json(self, base, path, params):
                calls.append((params["symbols"].split(",")[0], params.get("page_token")))
                first = params["symbols"].split(",")[0]
                if first == "S200" and not failed:
                    failed.append(1)
                    raise OSError("transient")
                if first == "S000" and "page_token" not in params:
                    return {"bars": {"S000": [{"t": "2026-09-25T04:00:00Z", "c": 1.0, "v": 1}]}, "next_page_token": "p2"}
                return {"bars": {first: [{"t": "2026-09-28T04:00:00Z", "c": 2.0, "v": 2, "vw": 2.0}]}, "next_page_token": None}

        loader = W.DailyBars(symbols, "sip", "2026-08-20T00:00:00Z", "2026-09-29T00:00:00Z", adjustment="split", attempts=1)
        with self.assertRaises(OSError):
            loader.run(Http())
        bars = loader.run(Http())
        self.assertEqual(calls, [("S000", None), ("S000", "p2"), ("S200", None), ("S200", None), ("S400", None)])
        self.assertEqual(bars["S000"], [{"t": "2026-09-25T04:00:00Z", "c": 1.0, "v": 1}, {"t": "2026-09-28T04:00:00Z", "c": 2.0, "v": 2}])
        self.assertEqual(sorted(bars), ["S000", "S200", "S400"])
        self.assertEqual(loader.calls, 5)

    def test_load_bars_waits_for_the_per_minute_budget_then_resumes(self):
        now = [0.0]
        budget = M.Budget(per_minute={"adv_bars": 2}, clock=lambda: now[0])
        made = []

        class Http:
            def alpaca_json(self, base, path, params):
                if not budget.take("adv_bars"):
                    raise M.BudgetExceeded("adv_bars")
                made.append(params["symbols"].split(",")[0])
                return {"bars": {made[-1]: [{"t": "2026-09-28T04:00:00Z", "c": 1.0, "v": 5}]}, "next_page_token": None}

        def sleep(seconds):
            now[0] += seconds

        loader = W.DailyBars([f"S{i:03d}" for i in range(600)], "sip", "a", "b")
        bars = W.load_bars(loader, Http(), deadline=300.0, sleep=sleep, clock=lambda: now[0])
        self.assertEqual(made, ["S000", "S200", "S400"])
        self.assertEqual(len(bars), 3)
        self.assertGreaterEqual(now[0], 60.0)   # the third call waited for the rolling minute
        now[0] = 1_000.0
        budget.recent.clear()
        stuck = W.DailyBars([f"S{i:03d}" for i in range(600)], "sip", "a", "b")
        with self.assertRaises(M.BudgetExceeded):
            W.load_bars(stuck, Http(), deadline=1_010.0, sleep=sleep, clock=lambda: now[0])


class Notifier(unittest.TestCase):
    URLS = ("http://127.0.0.1:18080/overnight-volume", "http://localhost/overnight-volume", "https://127.0.0.1:18080/t",
            "http://example.com/t", "http://127.0.0.1:18080/a/b", "http://127.0.0.1:18080/t?x=1", "http://u:p@127.0.0.1/t",
            "http://127.0.0.1:18080/t#f", "http://127.0.0.1:99999/t", "http://127.0.0.1:18080/", "not a url")

    def test_check_notify_url_mirror_matches_host_requests(self):
        if str(ROOT) not in sys.path:
            sys.path.append(str(ROOT))
        from scripts import host_requests as hr

        def accepted(check, url):
            try:
                check(url)
                return True
            except (hr.UsageError, W.UsageError):
                return False

        for url in self.URLS:
            self.assertEqual(accepted(W.check_notify_url, url), accepted(hr.check_notify_url, url), url)
        self.assertTrue(accepted(W.check_notify_url, self.URLS[0]))

    def test_send_notice_posts_one_plain_line(self):
        sent = []

        class Opener:
            def open(self, request, timeout):
                sent.append((request.get_method(), request.full_url, request.data, request.get_header("Content-type"), timeout))
                return FakeResponse(b"{}")

        W.send_notice("http://127.0.0.1:18080/overnight-volume", "overnight XYZ $3.2M", opener=Opener())
        self.assertEqual(sent, [("POST", "http://127.0.0.1:18080/overnight-volume", b"overnight XYZ $3.2M",
                                 "text/plain; charset=utf-8", 5)])
        with self.assertRaises(W.UsageError):
            W.send_notice("http://example.com/t", "x", opener=Opener())


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "20260929"
        self.market = Market()
        self.patches = [mock.patch("urllib.request.urlopen", side_effect=lambda r, timeout=None: self.market.urlopen(r, timeout)),
                        mock.patch.object(M, "credentials", return_value=("test-key", "test-secret"))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def lines(self, name: str) -> list[dict]:
        return [json.loads(line) for line in (self.out / name).read_text().splitlines() if line.strip()]

    def test_once_is_a_dry_run_that_prints_counts_only(self):
        buffer = io.StringIO()
        with mock.patch.object(W, "utcnow", return_value=NOW), mock.patch.object(W, "send_notice") as send, \
                contextlib.redirect_stdout(buffer):
            code = W.main(["--once", "--env-file", "unused.env", "--out", str(self.out)])
        self.assertEqual(code, 0)
        send.assert_not_called()
        summary = json.loads(buffer.getvalue())
        self.assertEqual(summary["mode"], "once")
        self.assertEqual(summary["symbols_swept"], 1208)
        self.assertEqual(summary["calls"], {"assets": 1, "adv_bars": 14, "snapshots": 3})
        self.assertEqual(summary["calls_total"], 18)
        self.assertEqual((summary["chunks_ok"], summary["chunks_failed"], summary["chunks_skipped"]), (3, 0, 0))
        self.assertEqual(summary["with_overnight_volume"], 6)
        self.assertEqual((summary["significant"], summary["notify"], summary["notify_non_fund"]), (3, 2, 1))
        self.assertEqual(summary["prior_session"], "2026-09-28")
        for symbol in ("AAA", "BBB", "DDD", "SPY"):
            self.assertNotIn(symbol, buffer.getvalue())
        self.assertTrue(all(m == "GET" for m, _ in self.market.requests))
        self.assertTrue(all((urllib.parse.urlsplit(u).hostname, urllib.parse.urlsplit(u).path) in W.ALLOWED_GETS
                            for _, u in self.market.requests))

        alerts = self.lines("alerts.jsonl")
        self.assertTrue(alerts and all(r["dry_run"] for r in alerts))
        self.assertEqual(sorted((r["tier"], r["s"]) for r in alerts),
                         [("notify", "AAA"), ("notify", "DDD"), ("significant", "AAA"), ("significant", "BBB"), ("significant", "DDD")])
        aaa = next(r for r in alerts if r["s"] == "AAA" and r["tier"] == "notify")
        self.assertEqual((aaa["overnight_dollar_volume"], aaa["adv_fraction"], aaa["change"], aaa["relvol_boats20"]),
                         (4_400_000.0, 0.4, 0.15, 200.0))
        self.assertEqual(aaa["push"], "dry_run")
        self.assertEqual(next(r for r in alerts if r["s"] == "DDD" and r["tier"] == "notify")["push"], "excluded_fund_name")

        top = self.lines("top.jsonl")[-1]
        lists = {entry["by"]: [r["s"] for r in entry["rows"]] for entry in top["lists"]}
        self.assertEqual(lists, {"relvol_boats20": ["AAA", "DDD", "BBB", "SPY"], "adv_fraction": ["AAA", "DDD", "BBB", "SPY", "FFF"]})

        start = json.loads((self.out / "start.json").read_text())
        self.assertEqual(start["id"], "overnight-volume-watch-v1")
        self.assertEqual(start["reference"]["prior_session"], "2026-09-28")
        self.assertEqual(start["reference"]["dates20"], [DATES20[0].isoformat(), DATES20[-1].isoformat()])
        self.assertEqual(start["universe"]["watched"], 1208)
        self.assertEqual(start["sha256"]["watch.py"], hashlib.sha256(Path(W.__file__).read_bytes()).hexdigest())
        self.assertEqual(start["sha256"]["thresholds"], hashlib.sha256(W.THRESHOLDS_PATH.read_bytes()).hexdigest())
        self.assertEqual(start["sha256"]["monitor.py"], hashlib.sha256(Path(M.__file__).read_bytes()).hexdigest())
        self.assertFalse(start["push"]["enabled"])
        stop = json.loads((self.out / "stop.json").read_text())
        self.assertEqual((stop["reason"], stop["sweeps"]), ("once", 1))

        board = json.loads((self.out / "board.json").read_text())
        self.assertEqual([r["s"] for r in board["significant_now"]], ["DDD", "AAA", "BBB"])
        snaps = sorted((self.out / "snapshots").iterdir())
        self.assertEqual(len(snaps), 1)
        saved = json.loads(gzip.decompress(snaps[0].read_bytes()))
        self.assertEqual(sorted(saved["rows"]), ["AAA", "BBB", "DDD", "EEE", "FFF", "SPY"])
        self.assertEqual(stat.S_IMODE(self.out.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.out / "snapshots").stat().st_mode), 0o700)
        for path in [p for p in self.out.rglob("*") if p.is_file()]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path.name)
        self.assertFalse(any(p.is_dir() and p.name.isdigit() for p in self.out.iterdir()))   # no per-day subdirectory

    def run_watch(self, clock: FakeClock, send=None, **extra) -> tuple[int, W.Watch]:
        watch = W.Watch(args("run", self.out, **extra))
        watch.monotonic, watch.wait = clock.monotonic, clock.wait
        if send is not None:
            watch.send = send
        with mock.patch.object(W, "utcnow", side_effect=clock.utcnow), contextlib.redirect_stdout(io.StringIO()):
            return watch.execute(), watch

    def test_run_pushes_non_fund_notify_names_once_and_stops_at_four_et(self):
        sent = []
        clock = FakeClock(datetime(2026, 9, 29, 7, 57, tzinfo=timezone.utc))
        code, watch = self.run_watch(clock, send=lambda url, text: sent.append((url, text)))
        self.assertEqual(code, 0)
        self.assertEqual(sent, [("http://127.0.0.1:18080/overnight-volume",
                                 "overnight AAA $4.4M 40.0% ADV +15.0% vs 09-28 close relvol 200 03:57 ET")])
        stop = json.loads((self.out / "stop.json").read_text())
        self.assertEqual((stop["reason"], stop["sweeps"]), ("stop_time", 2))
        self.assertEqual(stop["pushes"], {"sent": 1, "failed": 0})
        records = self.lines("alerts.jsonl")
        self.assertEqual(sum(r["event"] == "alert" for r in records), 5)
        self.assertEqual([(r["s"], r["status"]) for r in records if r["event"] == "push"], [("AAA", "sent")])
        sweeps = [r for r in self.lines("sweeps.jsonl") if r["event"] == "sweep"]
        self.assertEqual([r["new_alerts"] for r in sweeps], [{"significant": 3, "notify": 2}, {"significant": 0, "notify": 0}])
        self.assertEqual(self.market.requests[-1][1].split("?")[0], "https://data.alpaca.markets/v2/stocks/snapshots")

        # A restart on the same directory restores what was alerted and pushed: nothing alerts or posts twice.
        self.market.requests.clear()
        again = []
        code, _ = self.run_watch(FakeClock(datetime(2026, 9, 29, 7, 59, 30, tzinfo=timezone.utc)), send=lambda u, t: again.append(t))
        self.assertEqual(code, 0)
        self.assertEqual(again, [])
        self.assertEqual(json.loads((self.out / "start.json").read_text())["restored"],
                         {"significant": 3, "notify": 2, "pushes": 1, "pending": 0})

    def test_failed_push_is_recorded_and_the_sweep_continues(self):
        def refuse(url, text):
            raise OSError("connection refused")

        code, _ = self.run_watch(FakeClock(datetime(2026, 9, 29, 7, 59, tzinfo=timezone.utc)), send=refuse)
        self.assertEqual(code, 0)
        pushes = [r for r in self.lines("alerts.jsonl") if r["event"] == "push"]
        self.assertEqual([(r["s"], r["status"]) for r in pushes], [("AAA", "failed")])
        self.assertIn("OSError", pushes[0]["error"])
        self.assertEqual(json.loads((self.out / "stop.json").read_text())["pushes"], {"sent": 0, "failed": 1})

    def test_no_push_flag_records_disabled(self):
        sent = []
        code, _ = self.run_watch(FakeClock(datetime(2026, 9, 29, 7, 59, tzinfo=timezone.utc)), send=lambda u, t: sent.append(t), no_push=True)
        self.assertEqual((code, sent), (0, []))
        notify = [r for r in self.lines("alerts.jsonl") if r.get("tier") == "notify"]
        self.assertEqual({r["push"] for r in notify}, {"disabled", "excluded_fund_name"})

    def test_run_refuses_after_the_session_and_makes_no_request(self):
        code, _ = self.run_watch(FakeClock(datetime(2026, 9, 29, 8, 0, 1, tzinfo=timezone.utc)))
        self.assertEqual(code, 2)
        self.assertEqual(self.market.requests, [])
        self.assertEqual(json.loads((self.out / "stop.json").read_text())["refused"], ["session_over"])

    def test_stop_file_and_sigterm_stop_before_the_first_sweep(self):
        self.out.mkdir(parents=True)
        (self.out / "STOP").touch()
        code, _ = self.run_watch(FakeClock(NOW))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((self.out / "stop.json").read_text())["reason"], "stop_file")
        (self.out / "STOP").unlink()
        watch = W.Watch(args("run", self.out))
        clock = FakeClock(NOW)
        watch.monotonic, watch.wait = clock.monotonic, clock.wait
        watch.request_stop("sigterm")
        with mock.patch.object(W, "utcnow", side_effect=clock.utcnow), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(watch.execute(), 0)
        stop = json.loads((self.out / "stop.json").read_text())
        self.assertEqual((stop["reason"], stop["sweeps"]), ("sigterm", 0))

    def test_startup_refuses_a_prior_session_other_than_the_thresholds(self):
        self.market = Market(drop_sip_day=date(2026, 9, 28))
        code, _ = self.run_watch(FakeClock(NOW))
        self.assertEqual(code, 2)
        stop = json.loads((self.out / "stop.json").read_text())
        self.assertEqual(stop["refused"], ["prior_session_mismatch"])
        self.assertFalse(any("/v2/stocks/snapshots" in u for _, u in self.market.requests))

    def test_trade_date_must_match_the_thresholds(self):
        with self.assertRaises(W.UsageError):
            W.Watch(args("run", self.out, trade_date="2026-09-30"))
        self.assertEqual(W.Watch(args("run", self.out, trade_date="2026-09-29")).trade_date, TRADE_DATE)

    def test_plan_mode_needs_no_network_or_credentials(self):
        buffer = io.StringIO()
        with mock.patch.object(M, "credentials", side_effect=AssertionError("plan reads no credentials")), \
                contextlib.redirect_stdout(buffer):
            self.assertEqual(W.main(["plan", "--symbols", "9683"]), 0)
        plan = json.loads(buffer.getvalue())
        self.assertEqual((plan["per_sweep"]["snapshots"], plan["startup_calls"]), (20, 99))
        self.assertEqual(self.market.requests, [])


if __name__ == "__main__":
    unittest.main()
