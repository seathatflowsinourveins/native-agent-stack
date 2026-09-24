"""Continuous incentive monitor: records market-side and non-market-side catalyst signals and ranks a board.

  python monitor.py run  --env-file ENV --out DIR [--until-et 20:00] [--sweep-seconds 60]
  python monitor.py once --env-file ENV --out DIR     # one sweep of every polled source (no streams), then exit

Data only: it never places, changes or cancels an order. Sources (each measured entitled on 2026-09-24):

market side   Alpaca SIP snapshots for every active tradable US equity (REST, about 24 calls per sweep against
              a 10,000/min data limit); OPRA option trades for every contract (websocket "*", msgpack),
              aggregated per underlying root and minute with large prints kept whole. The SIP stock stream is
              left to the trading engine: a user may hold one connection per stream endpoint.
non-market    Alpaca/Benzinga news (websocket "*"); SEC EDGAR current filings (Atom, the declared contact in
              SEC_USER_AGENT, one request per form per sweep); Nasdaq Trader trade halts (RSS).

Every record carries the time the monitor received it, so the files form a point-in-time dataset from the
first day they are written. The board is an unvalidated detector (no strategy has been qualified on it);
"early" marks names with incentive signals whose price has not yet moved 10% from the reference close.
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import math
import os
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as XML
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")
DATA = "https://data.alpaca.markets"
TRADING = "https://paper-api.alpaca.markets"
OPRA_WS = "wss://stream.data.alpaca.markets/v1beta1/opra"
NEWS_WS = "wss://stream.data.alpaca.markets/v1beta1/news"
EDGAR_CURRENT = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={form}&company=&dateb=&owner=include&start=0&count=100&output=atom"
EDGAR_TICKERS = "https://www.sec.gov/files/company_tickers.json"
HALTS_RSS = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
# EDGAR's type filter is a prefix match ("4" also returns 424B2), so rows are kept by exact form afterwards.
EDGAR_FORMS = {"8-K": ("8-K", "8-K/A"), "6-K": ("6-K", "6-K/A"), "SCHEDULE 13D": ("SCHEDULE 13D", "SCHEDULE 13D/A"),
               "SC TO-T": ("SC TO-T", "SC TO-T/A"), "425": ("425",), "S-1": ("S-1", "S-1/A"), "424B4": ("424B4",)}
ATOM = "{http://www.w3.org/2005/Atom}"
OCC = re.compile(r"^([A-Z0-9.]{1,6})(\d{6})([CP])(\d{8})$")
HALT_FIELDS = ("HaltDate", "HaltTime", "IssueSymbol", "IssueName", "Market", "ReasonCode", "PauseThresholdPrice",
               "ResumptionDate", "ResumptionQuoteTime", "ResumptionTradeTime")
NEWS_HALTS = {"T1", "T2", "T3", "T12", "H10", "H11"}
VOLATILITY_HALTS = {"LUDP", "LUDS", "T5", "T7"}
MNA_FORMS = {"SCHEDULE 13D", "SCHEDULE 13D/A", "SC TO-T", "SC TO-T/A", "425"}
DILUTION_FORMS = {"S-1", "S-1/A", "424B4"}
EIGHT_K_MATERIAL = {"1.01", "1.02", "2.01", "2.02", "3.02", "5.01", "7.01", "8.01"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def et_day(ts: str | None) -> date | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ET).date()


def ts_text(value) -> str | None:
    """Timestamps arrive as RFC 3339 text (JSON streams) or as datetimes/msgpack Timestamps (the option stream)."""
    if value is None or isinstance(value, str):
        return value
    if hasattr(value, "to_datetime"):
        value = value.to_datetime()
    return value.astimezone(timezone.utc).isoformat() if hasattr(value, "astimezone") else str(value)


def credentials(path: Path):
    sys.path.insert(0, str(HERE.parent / "mover-early-entry"))
    import collect  # the study's reader: owner-only 0600 file, key pair only
    return collect.credentials(path)


def sec_identity() -> str:
    identity = os.environ.get("SEC_USER_AGENT", "")
    if not 10 <= len(identity) <= 300 or any(ord(c) < 32 or ord(c) > 126 for c in identity) or not ("@" in identity or "https://" in identity):
        raise SystemExit("SEC_USER_AGENT must hold the truthful declared contact (see catalyst-provenance/access-resolution.md)")
    return identity


class Sink:
    """Append-only JSON lines per ET day and stream, owner-only files."""

    def __init__(self, root: Path):
        self.root, self.files, self.lock = root, {}, threading.Lock()  # written from the loop and from poll threads

    def path(self, name: str, day: str | None = None) -> Path:
        return self.root / (day or datetime.now(ET).strftime("%Y%m%d")) / name

    def write(self, name: str, record: dict) -> None:
        line = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
        with self.lock:
            path = self.path(f"{name}.jsonl")
            handle = self.files.get(path)
            if handle is None:
                for old in [p for p in self.files if p.parent != path.parent]:
                    self.files.pop(old).close()
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                handle = self.files[path] = os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a", buffering=1)
            handle.write(line)

    def close(self) -> None:
        with self.lock:
            for handle in self.files.values():
                handle.close()
            self.files.clear()

    def replace(self, name: str, payload: bytes) -> Path:
        path = self.path(name)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = path.with_suffix(path.suffix + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp, path)
        return path


# ---------------------------------------------------------------- parsing (pure; covered by the tests)

def occ_parse(symbol: str):
    m = OCC.match(symbol or "")
    if not m:
        return None
    root, ymd, right, strike = m.groups()
    return root, date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:])), right, int(strike) / 1000


def dte_bucket(days: int) -> str:
    return "0-7" if days <= 7 else ("8-30" if days <= 30 else "31+")


class OptionsAggregator:
    """Per-minute option trade totals by (root, right, days-to-expiry bucket); session totals per root."""

    def __init__(self, large_premium: float = 100_000.0):
        self.large_premium = large_premium
        self.cells = defaultdict(lambda: [0, 0.0, 0])
        self.day = defaultdict(lambda: defaultdict(float))
        self.large, self.unparsed, self.messages = [], 0, 0

    def add(self, msg: dict, today: date) -> None:
        self.messages += 1
        parsed = occ_parse(msg.get("S", ""))
        if parsed is None:
            self.unparsed += 1
            return
        root, expiry, right, strike = parsed
        size, price = int(msg.get("s") or 0), float(msg.get("p") or 0.0)
        premium, days = price * size * 100.0, (expiry - today).days
        bucket = dte_bucket(days)
        cell = self.cells[(root, right, bucket)]
        cell[0] += size
        cell[1] += premium
        cell[2] += 1
        totals = self.day[root]
        totals[f"{right}_volume"] += size
        totals[f"{right}_premium"] += premium
        if bucket == "0-7":
            totals[f"{right}_premium_0_7"] += premium
        if premium >= self.large_premium:
            totals["large_prints"] += 1
            self.large.append({"symbol": msg.get("S"), "root": root, "right": right, "strike": strike, "dte": days,
                               "price": price, "size": size, "premium": round(premium, 2), "trade_ts": ts_text(msg.get("t")),
                               "exchange": msg.get("x"), "condition": msg.get("c")})

    def drain(self, minute: str) -> tuple[list, list]:
        by_root = defaultdict(dict)
        for (root, right, bucket), (volume, premium, trades) in self.cells.items():
            by_root[root][f"{right}|{bucket}"] = [volume, round(premium, 2), trades]
        rows = [{"minute": minute, "root": root, "cells": cells} for root, cells in sorted(by_root.items())]
        large, self.large = self.large, []
        self.cells = defaultdict(lambda: [0, 0.0, 0])
        return rows, large


def news_record(msg: dict, received: str) -> dict:
    return {"id": msg.get("id"), "created_at": msg.get("created_at"), "updated_at": msg.get("updated_at"), "received_at": received,
            "symbols": msg.get("symbols") or [], "headline": msg.get("headline"), "summary": (msg.get("summary") or "")[:1000],
            "source": msg.get("source"), "author": msg.get("author"), "url": msg.get("url")}


def parse_edgar(payload: bytes, received: str) -> list[dict]:
    rows = []
    for entry in XML.fromstring(payload).findall(f"{ATOM}entry"):
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        m = re.match(r"^(.*?) - (.*) \((\d{10})\) \(([^()]+)\)$", title)
        category, link = entry.find(f"{ATOM}category"), entry.find(f"{ATOM}link")
        summary = entry.findtext(f"{ATOM}summary") or ""
        rows.append({"accession": (entry.findtext(f"{ATOM}id") or "").rsplit("=", 1)[-1],
                     "form": category.get("term") if category is not None else (m.group(1) if m else None),
                     "company": m.group(2) if m else title, "cik": int(m.group(3)) if m else None, "role": m.group(4) if m else None,
                     "items": sorted(set(re.findall(r"Item (\d+\.\d+)", summary))), "updated": entry.findtext(f"{ATOM}updated"),
                     "link": link.get("href") if link is not None else None, "received_at": received})
    return rows


def parse_halts(payload: bytes, received: str) -> list[dict]:
    rows = []
    for item in XML.fromstring(payload).iter("item"):
        row = {}
        for child in item:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag in HALT_FIELDS:
                row[tag] = (child.text or "").strip() or None
        if row.get("IssueSymbol"):
            row["received_at"] = received
            rows.append(row)
    return rows


def snapshot_features(symbol: str, snap: dict, today: date) -> dict | None:
    trade, quote = snap.get("latestTrade") or {}, snap.get("latestQuote") or {}
    daily, prev, minute = snap.get("dailyBar") or {}, snap.get("prevDailyBar") or {}, snap.get("minuteBar") or {}
    price = trade.get("p")
    if not price:
        return None
    if et_day(daily.get("t")) == today:
        ref, volume = prev.get("c"), daily.get("v")
    else:  # before the regular session the daily bar is still the last session's (daily bars are regular-session only)
        ref, volume = daily.get("c"), None
    bid, ask = quote.get("bp") or 0, quote.get("ap") or 0
    return {"s": symbol, "p": price, "ref": ref, "chg": (price / ref - 1) if ref else None, "v": volume,
            "mv": minute.get("v"), "mt": minute.get("t"), "tt": trade.get("t"),
            "spr_bps": round((ask - bid) / ((ask + bid) / 2) * 1e4, 1) if bid > 0 and ask >= bid else None}


def session_fraction(at: datetime) -> float | None:
    local = at.astimezone(ET)
    minutes = (local.hour * 60 + local.minute) - (9 * 60 + 30)
    return None if minutes <= 0 else min(1.0, max(0.05, minutes / 390))


def regime(rows: list[dict], adv: dict, at: datetime) -> dict:
    liquid = [r for r in rows if r["chg"] is not None and (r["ref"] or 0) >= 5 and (adv.get(r["s"], 0) * (r["ref"] or 0)) >= 5e6]
    changes = sorted(r["chg"] for r in liquid)
    q = (lambda f: changes[min(len(changes) - 1, int(f * len(changes)))]) if changes else (lambda f: None)
    index = {r["s"]: round(r["chg"], 5) for r in rows if r["s"] in ("SPY", "QQQ", "IWM", "DIA") and r["chg"] is not None}
    return {"at": at.isoformat(timespec="seconds"), "liquid_names": len(liquid),
            "breadth_up": round(sum(c > 0 for c in changes) / len(changes), 4) if changes else None,
            "median_chg": round(statistics.median(changes), 5) if changes else None,
            "iqr_chg": round(q(0.75) - q(0.25), 5) if changes else None,
            "up_10pct": sum(c >= 0.10 for c in changes), "down_10pct": sum(c <= -0.10 for c in changes),
            "all_up_20pct": sum(1 for r in rows if (r["chg"] or 0) >= 0.20), "index": index}


def score(symbol: str, feat: dict | None, relvol: float | None, news: int, filings: list, halts: list, options: dict | None) -> dict:
    """Heuristic incentive score (unvalidated detector; components are kept so any study can re-weight them)."""
    parts = {}
    if relvol and relvol >= 2:
        parts["relvol"] = round(min(3.0, math.log2(relvol)), 3)
    if news:
        parts["news"] = 1.0 if news < 3 else 1.5
    forms = {f["form"] for f in filings}
    items = {i for f in filings for i in f.get("items", [])}
    if forms & MNA_FORMS:
        parts["mna_filing"] = 1.5
    if items & EIGHT_K_MATERIAL:
        parts["material_8k"] = 1.0
    if forms & DILUTION_FORMS:
        parts["dilution_filing"] = -1.0
    codes = {h.get("ReasonCode") for h in halts}
    if codes & NEWS_HALTS:
        parts["news_halt"] = 2.0
    elif codes & VOLATILITY_HALTS:
        parts["volatility_halt"] = 1.0
    if options:
        calls, puts = options.get("C_premium", 0.0), options.get("P_premium", 0.0)
        if options.get("C_premium_0_7", 0.0) >= 250_000 and calls >= 3 * max(puts, 1.0):
            parts["short_dated_calls"] = 1.5
        if options.get("large_prints", 0) >= 3:
            parts["large_option_prints"] = 0.5
    chg = feat["chg"] if feat else None
    stage = "unknown" if chg is None else ("early" if abs(chg) < 0.10 else "moving")
    return {"symbol": symbol, "score": round(sum(parts.values()), 3), "stage": stage, "parts": parts,
            "chg": None if chg is None else round(chg, 5), "price": feat["p"] if feat else None, "relvol": None if relvol is None else round(relvol, 2),
            "spr_bps": feat["spr_bps"] if feat else None}


# ---------------------------------------------------------------- network

class Http:
    def __init__(self, alpaca_headers: dict, sec_ua: str | None):
        self.alpaca, self.sec_ua, self.calls = alpaca_headers, sec_ua, defaultdict(int)

    def get(self, url: str, kind: str, headers: dict, timeout: float = 20) -> bytes:
        self.calls[kind] += 1
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            return r.read()

    def alpaca_json(self, base: str, path: str, params: dict) -> dict:
        return json.loads(self.get(f"{base}{path}?{urllib.parse.urlencode(params)}", "alpaca", self.alpaca))

    def sec(self, url: str) -> bytes:
        return self.get(url, "sec", {"User-Agent": self.sec_ua, "Accept-Encoding": "identity"})


class State:
    def __init__(self):
        self.news = defaultdict(dict)       # symbol -> {article id: epoch received}; updates of one article count once
        self.filings = defaultdict(list)    # symbol -> filing rows (this session, issuer role only)
        self.halts = defaultdict(list)      # symbol -> halt rows (today's halt date only)
        self.seen_accessions, self.halt_rows = set(), {}
        self.features, self.adv, self.cik_tickers, self.universe = {}, {}, {}, set()
        self.options = OptionsAggregator()
        self.last_trade = {}
        self.today = datetime.now(ET).date()
        self.stream_counts = defaultdict(int)
        self.started_at = now_utc()
        self.down_since, self.down_seconds = {}, defaultdict(float)  # stream -> epoch it went down; total seconds down
        self.restored = {}


def restore(state: State, day_dir: Path) -> dict:
    """Rebuild this session's filings, news window and option totals from today's files after a restart."""
    counts = defaultdict(int)
    def lines(name):
        path = day_dir / f"{name}.jsonl"
        if path.exists():
            with path.open() as f:
                for line in f:
                    try:
                        yield json.loads(line)
                    except ValueError:
                        counts[f"{name}_unreadable"] += 1
    for row in lines("edgar"):
        key = (row.get("accession"), row.get("cik"))
        if key not in state.seen_accessions:
            state.seen_accessions.add(key)
            attach_filing(state, row)
            counts["edgar"] += 1
    for row in lines("news"):
        received = datetime.fromisoformat(row["received_at"]).timestamp() if row.get("received_at") else None
        for symbol in row.get("symbols") or []:
            if received is not None and row.get("id") is not None:
                state.news[symbol].setdefault(row["id"], received)
        counts["news"] += 1
    for row in lines("options-minute"):
        totals = state.options.day[row["root"]]
        for cell, (volume, premium, _trades) in row.get("cells", {}).items():
            right, bucket = cell.split("|")
            totals[f"{right}_volume"] += volume
            totals[f"{right}_premium"] += premium
            if bucket == "0-7":
                totals[f"{right}_premium_0_7"] += premium
        counts["options_minutes"] += 1
    for row in lines("options-large"):
        state.options.day[row["root"]]["large_prints"] += 1
        counts["options_large"] += 1
    return dict(counts)


def root_symbol(root: str, universe: set) -> str | None:
    """The equity for an option root: itself, an adjusted root less its digit (TSLA1), or a class root (BRKB -> BRK.B)."""
    if root in universe:
        return root
    stripped = root.rstrip("0123456789")
    if stripped != root and stripped in universe:
        return stripped
    dotted = f"{root[:-1]}.{root[-1]}" if len(root) > 1 else None
    return dotted if dotted in universe else None


def load_universe(http: Http) -> list[str]:
    assets = http.alpaca_json(TRADING, "/v2/assets", {"status": "active", "asset_class": "us_equity"})
    return sorted(a["symbol"] for a in assets if a.get("tradable") and "/" not in a["symbol"] and " " not in a["symbol"])


def load_adv(http: Http, symbols: list[str], today: date) -> dict:
    volumes = defaultdict(list)
    for i in range(0, len(symbols), 200):
        params = {"symbols": ",".join(symbols[i:i + 200]), "timeframe": "1Day", "start": (today - timedelta(days=35)).isoformat(),
                  "end": (today - timedelta(days=1)).isoformat(), "feed": "sip", "adjustment": "split", "limit": 10000}
        while True:
            body = http.alpaca_json(DATA, "/v2/stocks/bars", params)
            for symbol, bars in (body.get("bars") or {}).items():
                volumes[symbol].extend(b["v"] for b in bars)
            if not body.get("next_page_token"):
                break
            params["page_token"] = body["next_page_token"]
    return {s: sum(v[-20:]) / len(v[-20:]) for s, v in volumes.items() if v}


def load_cik_tickers(http: Http) -> dict:
    mapping = defaultdict(list)
    for row in json.loads(http.sec(EDGAR_TICKERS)).values():
        mapping[int(row["cik_str"])].append(row["ticker"].replace("-", "."))  # SEC BRK-B is Alpaca BRK.B
    return dict(mapping)


def sweep_snapshots(http: Http, symbols: list[str], state: State, sink: Sink, at: datetime) -> list[dict]:
    rows = []
    for i in range(0, len(symbols), 500):
        body = http.alpaca_json(DATA, "/v2/stocks/snapshots", {"symbols": ",".join(symbols[i:i + 500]), "feed": "sip"})
        body = body.get("snapshots", body)
        for symbol, snap in body.items():
            feat = snapshot_features(symbol, snap or {}, state.today)
            if feat:
                rows.append(feat)
    changed = [r for r in rows if state.last_trade.get(r["s"]) != r["tt"]]
    state.last_trade.update({r["s"]: r["tt"] for r in rows})
    state.features = {r["s"]: r for r in rows}
    sink.replace(f"snapshots/{at.astimezone(ET).strftime('%H%M%S')}.json.gz",
                 gzip.compress(json.dumps({"at": at.isoformat(), "rows": changed}, separators=(",", ":")).encode()))
    return rows


def attach_filing(state: "State", row: dict) -> None:
    """Credit a filing to its issuer only: a bidder or holder ("Filed by") is not the incentive's subject."""
    if row.get("role") == "Filed by":
        return
    for ticker in row.get("tickers") or []:
        state.filings[ticker].append(row)


def poll_edgar(http: Http, state: State, sink: Sink) -> int:
    new = 0
    for query, keep in EDGAR_FORMS.items():
        received = now_utc()
        for row in parse_edgar(http.sec(EDGAR_CURRENT.format(form=urllib.parse.quote(query))), received):
            key = (row["accession"], row["cik"])
            if row["form"] not in keep or key in state.seen_accessions:
                continue
            state.seen_accessions.add(key)
            row["tickers"] = state.cik_tickers.get(row["cik"], [])
            sink.write("edgar", row)
            attach_filing(state, row)
            new += 1
        time.sleep(0.15)  # SEC fair access: well under 10 requests per second
    return new


def poll_halts(http: Http, state: State, sink: Sink) -> int:
    changed = 0
    # A generic agent here: the declared SEC contact is sent to SEC only.
    for row in parse_halts(http.get(HALTS_RSS, "nasdaq", {"User-Agent": "Mozilla/5.0 (compatible; incentive-monitor)"}), now_utc()):
        if row.get("HaltDate") != state.today.strftime("%m/%d/%Y"):
            continue  # the feed can still list earlier days' halts
        key = (row["IssueSymbol"], row.get("HaltDate"), row.get("HaltTime"))
        body = {k: v for k, v in row.items() if k != "received_at"}
        if state.halt_rows.get(key) != body:
            state.halt_rows[key] = body
            sink.write("halts", row)
            if key not in {(h["IssueSymbol"], h.get("HaltDate"), h.get("HaltTime")) for h in state.halts[row["IssueSymbol"]]}:
                state.halts[row["IssueSymbol"]].append(row)
            changed += 1
    return changed


NON_PRICE_PARTS = {"news", "mna_filing", "material_8k", "dilution_filing", "news_halt", "volatility_halt", "short_dated_calls", "large_option_prints"}


def build_board(state: State, at: datetime, top: int = 100) -> tuple[list[dict], list[str]]:
    """(board, incentive_symbols): rows scoring at least 2, and every symbol with any component other than relvol."""
    fraction = session_fraction(at)
    horizon = at.timestamp() - 1800
    options = {}
    for root, totals in state.options.day.items():
        symbol = root_symbol(root, state.universe) if state.universe else root
        if symbol:
            merged = options.setdefault(symbol, defaultdict(float))
            for key, value in totals.items():
                merged[key] += value
    candidates = set(state.filings) | set(state.halts) | set(state.news) | set(options)
    candidates |= {s for s, f in state.features.items() if f["chg"] is not None and abs(f["chg"]) >= 0.05}
    board, incentive = [], []
    for symbol in candidates:
        feat = state.features.get(symbol)
        adv = state.adv.get(symbol)
        relvol = (feat["v"] / (adv * fraction)) if (feat and feat.get("v") and adv and fraction) else None
        articles = state.news.get(symbol) or {}
        for article in [a for a, received in articles.items() if received < horizon]:
            del articles[article]
        row = score(symbol, feat, relvol, len(articles), state.filings.get(symbol, []), state.halts.get(symbol, []), options.get(symbol))
        if set(row["parts"]) & NON_PRICE_PARTS:
            incentive.append(symbol)
        if row["score"] >= 2:
            board.append(row)
    board.sort(key=lambda r: (-r["score"], r["symbol"]))
    return board[:top], sorted(incentive)


# ---------------------------------------------------------------- streams

async def stream(name: str, url: str, subscribe: dict, headers: dict, on_message, state: State, sink: Sink, stop: asyncio.Event, packed: bool):
    import msgpack
    import websockets
    attempt = 0
    while not stop.is_set():
        try:
            async with websockets.connect(url, additional_headers=({**headers, "Content-Type": "application/msgpack"} if packed else headers),
                                          max_size=None, ping_interval=20) as ws:
                await ws.send(msgpack.packb(subscribe) if packed else json.dumps(subscribe))
                if name in state.down_since:
                    state.down_seconds[name] += time.time() - state.down_since.pop(name)
                sink.write("monitor", {"event": "stream_connected", "stream": name, "at": now_utc()})
                while not stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    for msg in (msgpack.unpackb(raw, timestamp=3) if packed else json.loads(raw)):
                        kind = msg.get("T")
                        if kind == "error":
                            sink.write("monitor", {"event": "stream_error", "stream": name, "code": msg.get("code"), "msg": msg.get("msg"), "at": now_utc()})
                            raise ConnectionError(f"{name}:{msg.get('code')}")
                        if kind in ("success", "subscription"):
                            continue
                        state.stream_counts[f"{name}:{kind}"] += 1
                        on_message(msg)
                    attempt = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # reconnect with bounded backoff; every disconnect is recorded
            attempt += 1
            state.down_since.setdefault(name, time.time())
            sink.write("monitor", {"event": "stream_down", "stream": name, "error": f"{type(exc).__name__}: {str(exc)[:200]}", "attempt": attempt, "at": now_utc()})
            try:
                await asyncio.wait_for(stop.wait(), timeout=min(60, 2 ** attempt))
            except asyncio.TimeoutError:
                pass


async def run(args) -> int:
    key, secret = credentials(args.env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    http, sink, state, stop = Http(headers, sec_identity()), Sink(args.out), State(), asyncio.Event()
    until = datetime.combine(state.today, datetime.strptime(args.until_et, "%H:%M").time(), ET)
    sink.write("monitor", {"event": "start", "at": now_utc(), "mode": args.mode, "until_et": args.until_et, "sweep_seconds": args.sweep_seconds,
                           "pid": os.getpid(), "sources": ["sip_snapshots", "opra_trades", "news", "edgar", "nasdaq_halts"]})
    symbols = await asyncio.to_thread(load_universe, http)
    state.universe = set(symbols)
    state.cik_tickers = await asyncio.to_thread(load_cik_tickers, http)
    state.restored = restore(state, sink.path(""))
    sink.write("monitor", {"event": "restored", "at": now_utc(), "counts": state.restored})
    adv_task = asyncio.create_task(asyncio.to_thread(load_adv, http, symbols, state.today))

    def on_news(msg):
        received = now_utc()
        sink.write("news", news_record(msg, received))
        for symbol in msg.get("symbols") or []:
            if msg.get("id") is not None:
                state.news[symbol].setdefault(msg["id"], time.time())

    def on_opra(msg):
        if msg.get("T") == "t":
            state.options.add(msg, state.today)

    tasks = []
    if args.mode == "run":
        tasks = [asyncio.create_task(stream("news", NEWS_WS, {"action": "subscribe", "news": ["*"]}, headers, on_news, state, sink, stop, False)),
                 asyncio.create_task(stream("opra", OPRA_WS, {"action": "subscribe", "trades": ["*"]}, headers, on_opra, state, sink, stop, True))]
    stop_file = args.out / "STOP"
    try:
        while True:
            started, at = time.monotonic(), datetime.now(timezone.utc)
            stats = {"event": "sweep", "at": at.isoformat(timespec="seconds")}
            if adv_task.done() and not state.adv:
                try:
                    state.adv = adv_task.result()
                    sink.replace("adv20.json", json.dumps(state.adv, sort_keys=True).encode())
                except Exception as exc:  # retried next sweep; relvol stays empty meanwhile
                    stats["adv_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
                    adv_task = asyncio.create_task(asyncio.to_thread(load_adv, http, symbols, state.today))
            for label, job in (("snapshots", lambda: len(sweep_snapshots(http, symbols, state, sink, at))),
                               ("edgar_new", lambda: poll_edgar(http, state, sink)), ("halt_changes", lambda: poll_halts(http, state, sink))):
                try:
                    stats[label] = await asyncio.to_thread(job)
                except Exception as exc:  # one failing source never stops the others
                    stats[f"{label}_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            # Labelled with the drain time: a row holds trades received up to this moment.
            rows, large = state.options.drain(datetime.now(ET).isoformat(timespec="seconds"))
            for row in rows:
                sink.write("options-minute", row)
            for row in large:
                sink.write("options-large", row)
            if state.features:
                sink.write("regime", regime(list(state.features.values()), state.adv, at))
            board, incentive = build_board(state, at)
            down = {name: round(state.down_seconds[name] + (time.time() - since if (since := state.down_since.get(name)) else 0), 1)
                    for name in ("news", "opra")}
            payload = {"at": at.isoformat(timespec="seconds"), "evidence_class": "unvalidated_detector", "board": board,
                       "incentive_symbols": incentive,
                       "monitor": {"started_at": state.started_at, "restored": state.restored, "stream_down_seconds": down,
                                   "adv_loaded": bool(state.adv), "sweep_errors": sorted(k for k in stats if k.endswith("_error"))}}
            sink.replace("board.json", json.dumps(payload, indent=1).encode())
            sink.write("board", {"at": payload["at"], "board": board[:50]})
            stats.update({"board": len(board), "early": sum(r["stage"] == "early" for r in board), "calls": dict(http.calls),
                          "streams": dict(state.stream_counts), "options_unparsed": state.options.unparsed, "seconds": round(time.monotonic() - started, 2)})
            sink.write("monitor", stats)
            if args.mode == "once" or stop_file.exists() or datetime.now(ET) >= until:
                break
            await asyncio.sleep(max(1.0, args.sweep_seconds - (time.monotonic() - started)))
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if not adv_task.done():
            adv_task.cancel()
        sink.write("monitor", {"event": "stop", "at": now_utc(), "stop_file": stop_file.exists()})
        sink.close()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("run", "once"))
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--until-et", default="20:00")
    ap.add_argument("--sweep-seconds", type=float, default=60.0)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
