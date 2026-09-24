"""Synthetic fixtures for the study tests: a real XNYS calendar, hand-built series and a fake market-data server
(a recorded fake client) that honours symbols, start, end, asof, adjustment and pagination. No network, no market
data: every number here is invented.
"""
from __future__ import annotations

import bisect
import json
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from core.calendar import Calendar, build_calendar
from core.records import et_date
from core.store import Store

ET = ZoneInfo("America/New_York")


@lru_cache(maxsize=None)
def calendar(first="2015-09-01", last="2021-06-30") -> Calendar:
    return Calendar(build_calendar(first, last)["sessions"])


def iso_us(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def day_iso(session: str) -> str:
    return datetime.fromisoformat(session).replace(tzinfo=ET).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bar(c, o=None, h=None, l=None, v=1_000_000, vw=None):
    o = c if o is None else o
    return {"o": o, "h": max(o, c) if h is None else h, "l": min(o, c) if l is None else l, "c": c, "v": v,
            "vw": c if vw is None else vw}


def auction(open_px, close_px, exchange="Q", close_cond="6", other_close=None, no_open=False):
    day = {"o": [] if no_open else [{"c": "O", "p": open_px, "s": 5000, "x": exchange}], "c": []}
    if close_px is not None:
        day["c"].append({"c": close_cond, "p": close_px, "s": 5000, "x": exchange})
    if other_close is not None:
        day["c"].append({"c": "6", "p": other_close, "s": 100, "x": "Z"})
    return day


def quote(ts, bp, ap):
    return {"t": ts, "bp": bp, "ap": ap, "bs": 1, "as": 1}


def series(cal, first: str, last: str, close_fn, split_at: dict | None = None, cash_at: dict | None = None,
           missing=(), volume=2_000_000):
    """raw, split and all daily series. split_at {session: ratio}: a forward split (ratio new shares per share)
    effective on that session, so raw prices from then on are about 1/ratio of the old ones; a(s) is the product of
    the ratios of splits effective after s. cash_at {session: cash per share}: an ex-dividend on that session,
    reflected in 'all' only (all = split-adjusted close x the product of (1 - cash / previous close) of later
    ex-dates)."""
    split_at, cash_at = split_at or {}, cash_at or {}
    sessions = cal.range(first, last)
    closes = {s: close_fn(s) for s in sessions}
    a, f = {}, 1.0
    for s in reversed(sessions):
        a[s] = f
        if s in split_at:
            f *= split_at[s]
    d, g = {}, 1.0
    for s in reversed(sessions):
        d[s] = g
        if s in cash_at:
            prev = cal.offset(s, -1)
            g *= 1.0 - cash_at[s] / (closes[prev] * a[s] / a[prev])
    raw, split, allc = {}, {}, {}
    for s in sessions:
        if s in missing:
            continue
        c = closes[s]
        raw[s] = bar(c, v=volume)
        split[s] = bar(c / a[s], v=volume * a[s])
        allc[s] = bar(c / a[s] * d[s], v=volume * a[s])
    return raw, split, allc


def prints_from(raw: dict, exchange="Q", opens: dict | None = None):
    opens = opens or {}
    return {s: auction(opens.get(s, b["o"]), b["c"], exchange) for s, b in raw.items()}


def minute_rows(cal, session: str, px: float, vol: float, start="09:30", n=390, step=60):
    t0 = cal.at(session, start)
    close = cal.close(session)
    out = []
    for i in range(n):
        t = t0 + i * step
        if t >= close:
            break
        out.append({"t": t, "o": px, "h": px, "l": px, "c": px, "v": vol, "vw": px})
    return out


# ---------------------------------------------------------------- in-memory store helpers

def put_quotes(store: Store, req: dict, symbol: str, quotes: list, complete=True):
    body = {"quotes": {symbol: [{**q, "t": iso_us(q["t"])} for q in quotes]} if quotes else {}, "next_page_token": None}
    store.put(req, complete, [json.dumps(body).encode()] if complete else [], "2026-12-01T00:00:00Z")


def put_json(store: Store, req: dict, body: dict, complete=True):
    store.put(req, complete, [json.dumps(body).encode()] if complete else [], "2026-12-01T00:00:00Z")


# ---------------------------------------------------------------- fake market

class Timeout(Exception):
    pass


class FakeMarket:
    """A recorded fake client for the transport: opener(url, headers, timeout) -> (status, bytes)."""

    def __init__(self, cal, page_size=None):
        self.cal = cal
        self.issuers = {}
        self.aliases = {}          # default-asof only: old ticker -> issuer (the FB/META behaviour)
        self.aliases_any_asof = {}  # the same, whatever the asof (a provider that ignores asof for a ticker)
        self.actions = []
        self.assets = []
        self.page_size = page_size or {"bars": 5000, "auctions": 5000, "quotes": 4}
        self.fail = []             # [(predicate(url, params), mode, times)]
        self.calls = []

    def add(self, iid, symbols, daily=None, auctions=None, minute=None, quotes=None):
        self.issuers[iid] = {"symbols": sorted(symbols), "daily": daily or {}, "auctions": auctions or {},
                             "minute": minute or [], "quotes": sorted(quotes or [], key=lambda q: q["t"])}

    def resolve(self, symbol, asof):
        if symbol in self.aliases_any_asof:
            return self.aliases_any_asof[symbol]
        if asof is None:
            for iid, iss in self.issuers.items():
                if iss["symbols"][-1][1] == symbol:
                    return iid
            return self.aliases.get(symbol)
        for iid, iss in self.issuers.items():
            known = [sym for start, sym in iss["symbols"] if start <= asof]
            if known and known[-1] == symbol:
                return iid
        return None

    def opener(self, url, headers, timeout):
        parsed = urllib.parse.urlparse(url)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        self.calls.append((parsed.path, params))
        for i, (pred, mode, times) in enumerate(self.fail):
            if times and pred(parsed.path, params):
                self.fail[i] = (pred, mode, times - 1)
                if mode == "urlerror":
                    raise urllib.error.URLError(OSError("synthetic"))
                if mode == "timeout":
                    raise TimeoutError("synthetic")
                return 503, b"{}"
        body = self.route(parsed.path, params)
        return 200, json.dumps(body).encode()

    def _page(self, rows, params, kind):
        off = int(params.get("page_token") or 0)
        size = self.page_size[kind]
        chunk = rows[off: off + size]
        nxt = str(off + size) if off + size < len(rows) else None
        return chunk, nxt

    def route(self, path, p):
        if path == "/v2/assets":
            return [a for a in self.assets if a.get("status") == p.get("status")]
        if path == "/v1/corporate-actions":
            out = {}
            for a in self.actions:
                out.setdefault(a["type"], []).append({k: v for k, v in a.items() if k != "type"})
            return {"corporate_actions": out, "next_page_token": None}
        syms = p["symbols"].split(",")
        asof = p.get("asof")
        if path == "/v2/stocks/bars" and p["timeframe"] == "1Day":
            rows = []
            for sym in syms:
                iid = self.resolve(sym, asof)
                if iid is None:
                    continue
                d = self.issuers[iid]["daily"].get(p["adjustment"], {})
                for s in _in_range(d, p["start"], p["end"]):
                    rows.append((sym, {**d[s], "t": day_iso(s), "n": 1}))
            chunk, nxt = self._page(rows, p, "bars")
            out = {}
            for sym, r in chunk:
                out.setdefault(sym, []).append(r)
            return {"bars": out, "next_page_token": nxt}
        if path == "/v2/stocks/bars":
            lo, hi = p["start"], p["end"]
            rows = []
            for sym in syms:
                iid = self.resolve(sym, asof)
                if iid is None:
                    continue
                for b in self.issuers[iid]["minute"]:
                    ts = iso_us(b["t"])[:19] + "Z"
                    if lo <= ts <= hi:
                        rows.append((sym, {**b, "t": ts, "n": 1}))
            chunk, nxt = self._page(rows, p, "bars")
            out = {}
            for sym, r in chunk:
                out.setdefault(sym, []).append(r)
            return {"bars": out, "next_page_token": nxt}
        if path == "/v2/stocks/auctions":
            rows = []
            for sym in syms:
                iid = self.resolve(sym, asof)
                if iid is None:
                    continue
                a = self.issuers[iid]["auctions"]
                for s in _in_range(a, p["start"], p["end"]):
                    rows.append((sym, {"d": s, **a[s]}))
            chunk, nxt = self._page(rows, p, "auctions")
            out = {}
            for sym, r in chunk:
                out.setdefault(sym, []).append(r)
            return {"auctions": out, "next_page_token": nxt}
        if path == "/v2/stocks/quotes":
            from core.records import ts_epoch
            lo, hi = ts_epoch(p["start"]), ts_epoch(p["end"])
            rows = []
            for sym in syms:
                iid = self.resolve(sym, asof)
                if iid is None:
                    continue
                for q in self.issuers[iid]["quotes"]:
                    if lo <= q["t"] <= hi:
                        rows.append((sym, {**q, "t": iso_us(q["t"])}))
            chunk, nxt = self._page(rows, p, "quotes")
            out = {}
            for sym, r in chunk:
                out.setdefault(sym, []).append(r)
            return {"quotes": out, "next_page_token": nxt}
        raise ValueError(path)


def _in_range(by_day: dict, first: str, last: str) -> list:
    days = sorted(by_day)
    return days[bisect.bisect_left(days, first): bisect.bisect_right(days, last)]


def session_of(ts):
    return et_date(ts)
