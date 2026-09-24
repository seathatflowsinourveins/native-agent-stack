"""Continuous incentive monitor: records market-side and non-market-side catalyst signals and ranks a board.

  python monitor.py run  --env-file ENV --out DIR [--until-et 20:00] [--sweep-seconds 20]
  python monitor.py once --env-file ENV --out DIR     # one sweep of every polled source (no streams), then exit

Data only: it never places, changes or cancels an order. Sources (entitlements measured on 2026-09-24):

market side   Alpaca SIP snapshots for every active tradable US equity (REST, about 27 calls per sweep against
              a 10,000/min data limit); OPRA option trades for every contract (websocket "*", msgpack),
              aggregated per underlying root and minute with large prints kept whole; trading status, LULD
              bands and imbalances for every symbol on the IEX stock stream (v2/iex; the SIP stock stream v2/sip
              is left to the trading engine: a user may hold one connection per stream endpoint); the screener
              (most actives by volume and by trades, top movers); option chain snapshots (implied volatility,
              greeks) for the top board candidates, with open interest from the contracts endpoint once a day.
non-market    Alpaca/Benzinga news (websocket "*"); SEC EDGAR current filings (Atom, the declared contact in
              SEC_USER_AGENT, one request per form per sweep); Nasdaq Trader trade halts (RSS, at most once a
              minute), merged with the status stream into one halt state; the corporate-actions event stream
              (Server-Sent Events, every event archived); FINRA daily short sale volume files (once a day after
              publication).

Every source runs inside an explicit call budget that is written to monitor.jsonl; the data REST plan is refused
above 5% of the 10,000/min data limit. Every record carries the time the monitor received it, so the files form a
point-in-time dataset from the first day they are written. The boards are unvalidated detectors (no strategy has
been qualified on them): board.json keeps board version 1 (the frozen forward protocol's components and weights) and
board-v2.json adds the new sources' components. "early" marks names with incentive signals whose price has not yet
moved 10% from the reference close.
"""
from __future__ import annotations

import argparse
import asyncio
import errno
import fcntl
import gzip
import hashlib
import json
import math
import os
import re
import socket
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as XML
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dtime, timedelta, timezone
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
EDGAR_FUND_TICKERS = "https://www.sec.gov/files/company_tickers_mf.json"  # 1940 Act funds, incl. most ETFs
FUND_NAME = re.compile(r"\b(ETF|ETN|ETP|Fund|Trust)\b", re.IGNORECASE)
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

# ---------------------------------------------------------------- monitor v2 sources (docs read 2026-09-24)
# docs.alpaca.markets real-time stock data: statuses and lulds "can be accessed from any {source} depending on your
# subscription"; one connection per endpoint (406 "connection limit exceeded"). The engine owns v2/sip; this recorder
# holds v2/iex behind a host lease and backs off after a 406 (--no-iex-status on a day an iex engine config runs).
IEX_WS = "wss://stream.data.alpaca.markets/v2/iex"
# "Subscribe to Corporate Actions Events (SSE)": the operation's own server is the stream host (the data host is 404).
CA_EVENTS = "https://stream.data.alpaca.markets/v1beta1/events/corporate-actions"
SCREENER_ACTIVES, SCREENER_MOVERS = "/v1beta1/screener/stocks/most-actives", "/v1beta1/screener/stocks/movers"
OPTION_CHAIN, OPTION_CONTRACTS = "/v1beta1/options/snapshots/{symbol}", "/v2/options/contracts"
# FINRA posts the consolidated NMS file no later than 18:00 ET on the trade date (off-exchange TRF/ADF volume only).
FINRA_SHORT_VOLUME = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day}.txt"
FINRA_HEADER = ["Date", "Symbol", "ShortVolume", "ShortExemptVolume", "TotalVolume", "Market"]
FINRA_AFTER_ET = dtime(18, 5)
GENERIC_UA = {"User-Agent": "Mozilla/5.0 (compatible; incentive-monitor)"}  # the declared SEC contact goes to SEC only
DATA_LIMIT_PER_MIN, TRADING_LIMIT_PER_MIN = 10_000, 200  # X-Ratelimit-Limit of the data and paper trading APIs, measured
BUDGET_FRACTION = 0.05             # the monitor's REST plan may use at most 5% of either limit
RSS_MIN_SECONDS = 60.0             # Nasdaq Trader: at most one request per minute
CA_CONNECTS_PER_MIN = 2            # the events endpoint reports X-Ratelimit-Limit 20
CA_READ_TIMEOUT, CA_RESUME_MAX_DAYS = 120, 7
RATELIMIT_FLOOR = 3500             # optional data sources pause while the data API reports fewer calls left
BOARD_VERSION, BOARD_V2_VERSION = 1, 2
SOURCES = (("data.alpaca.markets/v2/stocks/snapshots", "snapshots"), ("data.alpaca.markets/v2/stocks/bars", "adv_bars"),
           ("data.alpaca.markets/v1beta1/screener/", "screener"), ("data.alpaca.markets/v1beta1/options/snapshots/", "option_chains"),
           ("alpaca.markets/v2/options/contracts", "option_contracts"), ("alpaca.markets/v2/assets", "assets"),
           ("www.sec.gov/cgi-bin/browse-edgar", "edgar"), ("www.sec.gov/files/", "sec_files"),
           ("nasdaqtrader.com/", "nasdaq_halts"), ("cdn.finra.org/", "finra"))
# Trading status codes (docs): UTP tapes C and O, CTA tapes A and B. CTA 5-9 and A-F are indications, imbalances,
# short-sale restrictions and LULD notices, which do not change the halt state (CTA F is not a halt).
UTP_STATUS = {"H": "halted", "P": "paused", "Q": "quotation_only", "T": "trading"}
CTA_STATUS = {"2": "halted", "3": "trading"}
CTA_NEWS_REASONS = {"P", "D", "A", "C"}   # news pending, news released, additional information requested, regulatory concern
CTA_VOLATILITY_REASONS = {"M"}            # LULD trading pause
RSS_VOLATILITY_EXTRA = {"M"}              # Nasdaq Trader code M: a volatility pause in an exchange-listed issue (v1 omits it)
STATE_KIND = {"halted": "halt", "paused": "halt", "quotation_only": "quote", "trading": "trade"}
# Corporate actions surfaced as board context: symbol fields and the date that places each action in time.
CA_TYPES = {"forward_split": (("symbol",), "ex_date"), "reverse_split": (("symbol", "new_symbol"), "ex_date"),
            "unit_split": (("old_symbol", "new_symbol", "alternate_symbol"), "effective_date"),
            "cash_merger": (("acquiree_symbol", "acquirer_symbol"), "effective_date"),
            "stock_merger": (("acquiree_symbol", "acquirer_symbol"), "effective_date"),
            "stock_and_cash_merger": (("acquiree_symbol", "acquirer_symbol"), "effective_date"),
            "spin_off": (("source_symbol", "new_symbol"), "ex_date"), "name_change": (("old_symbol", "new_symbol"), "process_date")}
CA_SUFFIX = "_corporateaction_event"
CA_WINDOW_DAYS = (-1, 10)          # the component: the action's date from yesterday to ten days ahead, or announced today
CA_CONTEXT_DAYS = (-5, 60)         # context only
EVENT_ID = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
# Board v2: fixed on 2026-09-24 without outcome data (unvalidated). Board v1 components and weights are unchanged.
V2_WEIGHTS = {"stream_news_halt": 2.0, "stream_volatility_halt": 1.0, "corporate_action": 0.5, "iv_runup": 1.0,
              "short_volume_high": 0.5}
V2_RULES = {
    "stream_news_halt": "the status stream showed a halt today with a news reason (UTP T1 T2 T3 T12 H10 H11, CTA P D A C) "
                        "and the Nasdaq RSS shows no news halt for the name today (never counted twice)",
    "stream_volatility_halt": "the status stream showed a volatility pause today (UTP LUDP LUDS T5 T7, CTA M), no news halt on "
                              "either source and no RSS halt of any kind (price-triggered, not a non-price incentive)",
    "corporate_action": "a split, merger, spin-off or name/symbol change whose ex, effective or process date is from yesterday "
                        "to 10 days ahead, or first inserted today",
    "iv_runup": "near-the-money implied volatility of the first expiry at least 7 days out is up at least 20% on its baseline "
                "(the previous session's last value for the same expiry, else the first value today from 09:45 ET), "
                "with the baseline at least 30 minutes old",
    "short_volume_high": "the latest FINRA consolidated short sale volume ratio is at least 0.80 on at least 200,000 shares "
                         "of reported off-exchange volume (volume-derived, not a non-price incentive)"}
IV_RUNUP_MIN, IV_BASELINE_MIN_AGE, IV_FIRST_ET = 0.20, 1800, dtime(9, 45)
SHORT_RATIO_HIGH, SHORT_MIN_TOTAL = 0.80, 200_000


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
                torn = path.exists() and path.stat().st_size > 0 and path.read_bytes()[-1:] != b"\n"  # a crash mid-line
                handle = self.files[path] = os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a", buffering=1)
                if torn:
                    handle.write("\n")
            handle.write(line)

    def close(self) -> None:
        with self.lock:
            for handle in self.files.values():
                handle.close()
            self.files.clear()

    def replace(self, name: str, payload: bytes, shared: bool = False) -> Path:
        """Owner-only atomic write under today's directory, or under the root for files that span days (shared)."""
        path = self.root / name if shared else self.path(name)
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

    def drain(self, drained_at: str) -> tuple[list, list]:
        """Rows of the trades received since the previous drain (one sweep interval), labelled with this drain's time."""
        by_root = defaultdict(dict)
        for (root, right, bucket), (volume, premium, trades) in self.cells.items():
            by_root[root][f"{right}|{bucket}"] = [volume, round(premium, 2), trades]
        rows = [{"drained_at": drained_at, "root": root, "cells": cells} for root, cells in sorted(by_root.items())]
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


# ---------------------------------------------------------------- monitor v2: parsing and rules (pure; covered by the tests)

def utc(text) -> datetime | None:
    """An RFC 3339 timestamp (nanoseconds and Z allowed) as an aware UTC datetime; None when absent or unreadable."""
    if not text:
        return None
    try:
        value = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return value.astimezone(timezone.utc) if value.tzinfo else None


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def et_clock(day_text: str | None, clock_text: str | None) -> datetime | None:
    """A Nasdaq RSS date (MM/DD/YYYY) and Eastern wall-clock time (HH:MM:SS[.fff]) as a UTC datetime."""
    if not day_text or not clock_text:
        return None
    try:
        day = datetime.strptime(day_text.strip(), "%m/%d/%Y").date()
        hours, minutes, *rest = clock_text.strip().split(":")
        local = datetime.combine(day, dtime(int(hours), int(minutes)), ET) + timedelta(seconds=float(rest[0]) if rest else 0.0)
    except ValueError:
        return None
    return local.astimezone(timezone.utc)


def halt_category(tape: str | None, reason: str | None) -> str:
    """news, volatility or other for a halt reason code of either plan (CTA on tapes A and B, UTP otherwise)."""
    if tape in ("A", "B"):
        return "news" if reason in CTA_NEWS_REASONS else ("volatility" if reason in CTA_VOLATILITY_REASONS else "other")
    return "news" if reason in NEWS_HALTS else ("volatility" if reason in VOLATILITY_HALTS else "other")


def status_state(msg: dict) -> str | None:
    """The trading state a status message sets (halted, paused, quotation_only, trading), or None for a notice."""
    return (CTA_STATUS if msg.get("z") in ("A", "B") else UTP_STATUS).get(msg.get("sc"))


class HaltBook:
    """One halt state per symbol, merged from the status stream and the Nasdaq RSS: the latest event by its own time wins.

    Events are halt (a halt or pause begins), quote (quotation resumes, trading not yet) and trade (trading resumes). The
    stream sends changes only, with no snapshot on subscribe, so a halt that began before the connection is known from the
    RSS; the RSS lags the stream by tens of seconds, so the stream usually knows first. LULD bands are kept per symbol."""

    SEVERITY = {"other": 1, "volatility": 2, "news": 3}

    def __init__(self):
        self.events, self.bands, self.lock = defaultdict(list), {}, threading.Lock()

    def _add(self, symbol: str, event: dict) -> bool:
        key = (event["source"], event["kind"], event["at"])
        with self.lock:
            if any((e["source"], e["kind"], e["at"]) == key for e in self.events[symbol]):
                return False
            self.events[symbol].append(event)
            return True

    def stream_status(self, msg: dict, received: str | None) -> bool:
        state, at, symbol = status_state(msg), utc(msg.get("t")), msg.get("S")
        if state is None or at is None or not symbol:
            return False
        kind = STATE_KIND[state]
        return self._add(symbol, {"source": "stream", "kind": kind, "state": state, "at": iso(at), "reason": msg.get("rc"),
                                  "category": halt_category(msg.get("z"), msg.get("rc")) if kind == "halt" else None,
                                  "tape": msg.get("z"), "received_at": received})

    def rss_row(self, row: dict) -> int:
        symbol, reason = row.get("IssueSymbol"), row.get("ReasonCode")
        if not symbol:
            return 0
        category, added = ("volatility" if reason in RSS_VOLATILITY_EXTRA else halt_category(None, reason)), 0
        for kind, day_key, clock_key in (("halt", "HaltDate", "HaltTime"), ("quote", "ResumptionDate", "ResumptionQuoteTime"),
                                         ("trade", "ResumptionDate", "ResumptionTradeTime")):
            at = et_clock(row.get(day_key), row.get(clock_key))
            if at is None:
                continue
            state = ("paused" if category == "volatility" else "halted") if kind == "halt" else ("quotation_only" if kind == "quote" else "trading")
            added += self._add(symbol, {"source": "rss", "kind": kind, "state": state, "at": iso(at), "reason": reason,
                                        "category": category if kind == "halt" else None, "tape": None, "received_at": row.get("received_at")})
        return added

    def set_band(self, msg: dict, received: str | None) -> None:
        if msg.get("S"):
            with self.lock:
                self.bands[msg["S"]] = {"u": msg.get("u"), "d": msg.get("d"), "i": msg.get("i"), "t": msg.get("t"), "z": msg.get("z"),
                                        "received_at": received}

    def band(self, symbol: str, price: float | None = None) -> dict | None:
        with self.lock:
            band = dict(self.bands[symbol]) if symbol in self.bands else None
        if band and price and band.get("u") and band.get("d"):
            band.update({"to_up_bps": round((band["u"] / price - 1) * 1e4, 1), "to_down_bps": round((1 - band["d"] / price) * 1e4, 1)})
        return band

    def state(self, symbol: str, now: datetime) -> dict | None:
        """The merged state at ``now``: a scheduled RSS resumption counts only once its time has come."""
        horizon = iso(now + timedelta(seconds=5))  # exchange time may run a little ahead of this host's clock
        with self.lock:
            events = sorted((e for e in self.events.get(symbol, ()) if e["at"] <= horizon), key=lambda e: (e["at"], e["source"]))
        if not events:
            return None
        last, halts = events[-1], [e for e in events if e["kind"] == "halt"]
        return {"state": last["state"], "since": last["at"], "source": last["source"], "reason": halts[-1]["reason"] if halts else None,
                "category": halts[-1]["category"] if halts else None,
                "halts": {source: sum(e["source"] == source for e in halts) for source in ("rss", "stream")}}

    def stream_category(self, symbol: str) -> str | None:
        """The most severe halt category the status stream showed for the symbol (news, then volatility, then other)."""
        with self.lock:
            found = [e["category"] for e in self.events.get(symbol, ()) if e["source"] == "stream" and e["kind"] == "halt"]
        return max(found, key=self.SEVERITY.__getitem__) if found else None

    def symbols(self, source: str | None = None) -> set:
        with self.lock:
            return {s for s, events in self.events.items() if any(source is None or e["source"] == source for e in events)}


def sse_events(lines):
    """Events of a text/event-stream (WHATWG rules): comments skipped, data lines joined by newlines, the last id carried.

    Yields {"id", "event", "data"}; an event is dispatched at a blank line, so a truncated final event is dropped."""
    data, event, last_id = [], "", None
    for raw in lines:
        line = (raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else raw).rstrip("\r\n")
        if not line:
            if data:
                yield {"id": last_id, "event": event or "message", "data": "\n".join(data)}
            data, event = [], ""
        elif not line.startswith(":"):
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "data":
                data.append(value)
            elif field == "event":
                event = value
            elif field == "id" and "\0" not in value:
                last_id = value


def ca_event_list(data: str) -> list[dict]:
    """The corporate-action events in one SSE data field (the documented payload is an array of events)."""
    payload = json.loads(data)
    return [e for e in (payload if isinstance(payload, list) else [payload]) if isinstance(e, dict)]


def ulid_time(event_id) -> datetime | None:
    """The emission time a ULID event id carries in its first ten characters (milliseconds since the epoch)."""
    if not isinstance(event_id, str) or not EVENT_ID.match(event_id):
        return None
    ms = 0
    for ch in event_id[:10]:
        ms = ms * 32 + CROCKFORD.index(ch)
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


class CorporateActions:
    """The latest version of every surfaced corporate action by id (splits, mergers, spin-offs, name and symbol changes).

    ULID event ids sort in emission order, so an older version of an action, or one replayed after its deletion, is ignored."""

    def __init__(self):
        self.actions, self.versions, self.lock = {}, {}, threading.Lock()

    def observe(self, event: dict) -> bool:
        kind, ca, eid = str(event.get("event_type") or "").removesuffix(CA_SUFFIX), event.get("ca") or {}, event.get("event_id")
        if kind not in CA_TYPES or not isinstance(ca, dict) or not ca.get("id") or not isinstance(eid, str):
            return False
        with self.lock:
            if self.versions.get(ca["id"], "") >= eid:
                return False
            self.versions[ca["id"]] = eid
            if event.get("action") == "delete":
                self.actions.pop(ca["id"], None)
            else:
                self.actions[ca["id"]] = {"type": kind, "action": event.get("action"), "at": event.get("at"), "event_id": eid, "ca": ca}
        return True

    def by_symbol(self, today: date) -> dict:
        """symbol -> actions dated inside the context window; ``in_window`` marks those that meet the board component rule."""
        out = defaultdict(list)
        with self.lock:
            items = list(self.actions.values())
        for item in items:
            fields, date_field = CA_TYPES[item["type"]]
            when = item["ca"].get(date_field)
            try:
                days = (date.fromisoformat(when) - today).days if when else None
            except (TypeError, ValueError):
                days = None
            emitted = utc(item["at"])
            fresh = item["action"] == "insert" and emitted is not None and emitted.astimezone(ET).date() == today
            in_window = fresh or (days is not None and CA_WINDOW_DAYS[0] <= days <= CA_WINDOW_DAYS[1])
            if not in_window and (days is None or not CA_CONTEXT_DAYS[0] <= days <= CA_CONTEXT_DAYS[1]):
                continue
            terms = {k: v for k, v in item["ca"].items() if k.endswith(("rate", "symbol"))}
            for field in fields:
                if item["ca"].get(field):
                    out[item["ca"][field]].append({"type": item["type"], "role": field, "date": when, "days": days, "in_window": in_window,
                                                   "action": item["action"], "at": item["at"], "terms": terms})
        return dict(out)


def screener_ranks(by_volume: dict, by_trades: dict, movers: dict) -> dict:
    """symbol -> ranks in the most-actives screens (by volume, by trades) and the movers screen (gainers, losers)."""
    ranks = defaultdict(dict)
    for key, body in (("volume_rank", by_volume), ("trades_rank", by_trades)):
        for i, row in enumerate((body or {}).get("most_actives") or []):
            if row.get("symbol"):
                ranks[row["symbol"]][key] = i + 1
    for key, side in (("gainer_rank", "gainers"), ("loser_rank", "losers")):
        for i, row in enumerate((movers or {}).get(side) or []):
            if row.get("symbol"):
                ranks[row["symbol"]].update({key: i + 1, "pct_change": row.get("percent_change")})
    return dict(ranks)


def valid_iv(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 < value < 20


def contract_row(symbol: str, snap: dict, oi: dict | None) -> dict:
    greeks, quote, bar = snap.get("greeks") or {}, snap.get("latestQuote") or {}, snap.get("dailyBar") or {}
    return {"symbol": symbol, "iv": snap.get("impliedVolatility"), "delta": greeks.get("delta"), "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"), "vega": greeks.get("vega"), "bid": quote.get("bp"), "ask": quote.get("ap"), "quote_t": quote.get("t"),
            "volume": bar.get("v"), "oi": (oi or {}).get(symbol)}


def chain_summary(underlying: str, snapshots: dict, price: float | None, today: date, oi: dict | None = None, near: int = 3) -> dict:
    """Near-the-money implied volatility of the chain's first expiry, the contracts around it and the day's volumes.

    The chain request starts at the minimum days to expiry, so its first expiry is the target. Standard contracts (root
    equal to the symbol without its class dot) are used when present; adjusted roots have other deliverables."""
    rows = []
    for symbol, snap in (snapshots or {}).items():
        parsed = occ_parse(symbol)
        if parsed is not None and isinstance(snap, dict):
            rows.append((parsed[1], parsed[3], parsed[2], symbol, snap, parsed[0]))
    standard = [r for r in rows if r[5] == underlying.replace(".", "")]
    rows = standard or rows
    out = {"contracts": len(rows), "expiry": None, "dte": None, "strike": None, "call_iv": None, "put_iv": None, "atm_iv": None,
           "call_volume": 0, "put_volume": 0, "near": []}
    for _, _, right, _, snap, _ in rows:
        bar = snap.get("dailyBar") or {}
        traded = utc(bar.get("t"))
        if traded is not None and traded.astimezone(ET).date() == today:
            out["call_volume" if right == "C" else "put_volume"] += int(bar.get("v") or 0)
    if not rows or not price:
        return out
    expiry = min(r[0] for r in rows)
    at_expiry = [r for r in rows if r[0] == expiry]
    ivs = {(r[1], r[2]): r[4].get("impliedVolatility") for r in at_expiry if valid_iv(r[4].get("impliedVolatility"))}
    strikes = sorted({r[1] for r in at_expiry}, key=lambda k: (abs(k - price), k))
    for strike in strikes:
        call, put = ivs.get((strike, "C")), ivs.get((strike, "P"))
        present = [v for v in (call, put) if v is not None]
        if present:
            out.update({"strike": strike, "call_iv": call, "put_iv": put, "atm_iv": round(sum(present) / len(present), 5)})
            break
    out.update({"expiry": expiry.isoformat(), "dte": (expiry - today).days,
                "near": [contract_row(r[3], r[4], oi) for r in sorted(at_expiry, key=lambda r: (r[1], r[2])) if r[1] in strikes[:near]]})
    return out


class IVTracker:
    """Per-symbol near-the-money implied volatility: the first value today from 09:45 ET, the latest, and the previous
    session's last value (from the previous day's file). The change is measured against the previous session when the
    expiry is the same, else against the first value today."""

    def __init__(self):
        self.first, self.last, self.prev = {}, {}, {}

    def observe(self, symbol: str, at: datetime, summary: dict) -> None:
        if not valid_iv(summary.get("atm_iv")):
            return
        rec = {"at": iso(at), "iv": summary["atm_iv"], "expiry": summary.get("expiry")}
        if symbol not in self.first and at.astimezone(ET).time() >= IV_FIRST_ET:
            self.first[symbol] = rec
        self.last[symbol] = rec

    def change(self, symbol: str, at: datetime) -> dict | None:
        cur = self.last.get(symbol)
        if cur is None:
            return None
        prev, first = self.prev.get(symbol), self.first.get(symbol)
        if prev and prev.get("expiry") == cur["expiry"] and valid_iv(prev.get("iv")) and utc(prev.get("at")) is not None:
            base, kind = prev, "previous_session"
        elif first:
            base, kind = first, "first_today"
        else:
            return None
        return {"iv": cur["iv"], "expiry": cur["expiry"], "baseline_iv": base["iv"], "baseline": kind,
                "baseline_age_s": round((at - utc(base["at"])).total_seconds()), "chg": round(cur["iv"] / base["iv"] - 1, 4)}

    def runup(self, symbol: str, at: datetime) -> dict | None:
        found = self.change(symbol, at)
        return found if found and found["chg"] >= IV_RUNUP_MIN and found["baseline_age_s"] >= IV_BASELINE_MIN_AGE else None


def oi_summary(contracts: list, truncated: bool) -> dict:
    """Open interest per contract from the contracts endpoint (decimal strings), with call and put totals."""
    by_contract, totals, dates = {}, {"call": 0, "put": 0}, set()
    for c in contracts or []:
        try:
            oi = int(float(c.get("open_interest")))
        except (TypeError, ValueError, OverflowError):
            continue
        by_contract[c.get("symbol")] = oi
        if c.get("type") in totals:
            totals[c["type"]] += oi
        if c.get("open_interest_date"):
            dates.add(c["open_interest_date"])
    return {"contracts": len(contracts or []), "with_oi": len(by_contract), "call_oi": totals["call"], "put_oi": totals["put"],
            "oi_date": max(dates) if dates else None, "truncated": truncated, "by_contract": by_contract}


def parse_finra(payload: bytes) -> tuple[str, dict]:
    """(trade date YYYYMMDD, symbol -> row) from a FINRA daily short sale volume file. The header must match, the trailer
    record count must equal the rows, and class-share symbols read with a dot (BF/B is BF.B)."""
    lines = payload.decode("utf-8-sig").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or lines[0].split("|") != FINRA_HEADER:
        raise ValueError("finra_header")
    body = lines[1:]
    if not body or not body[-1].strip().isdigit():
        raise ValueError("finra_trailer")
    count, body = int(body[-1].strip()), body[:-1]
    if count != len(body):
        raise ValueError("finra_count_mismatch")
    rows, day = {}, None
    for line in body:
        fields = line.split("|")
        if len(fields) != 6:
            raise ValueError("finra_row")
        trade_day, symbol, short, exempt, total, markets = fields
        if day is None:
            day = trade_day
        elif trade_day != day:
            raise ValueError("finra_mixed_dates")
        short_v, total_v = float(short), float(total)
        rows[symbol.replace("/", ".")] = {"short": short_v, "exempt": float(exempt), "total": total_v,
                                          "ratio": round(short_v / total_v, 4) if total_v > 0 else None, "markets": markets}
    if day is None or not re.fullmatch(r"\d{8}", day):
        raise ValueError("finra_date")
    return day, rows


def finra_due(now: datetime) -> date:
    """The latest trade date whose FINRA file is due: today from 18:05 ET on a weekday, else the previous weekday."""
    local = now.astimezone(ET)
    if local.weekday() < 5 and local.time() >= FINRA_AFTER_ET:
        return local.date()
    day = local.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def weekdays_back(day: date, n: int) -> list[date]:
    out = [day]
    while len(out) < n:
        day -= timedelta(days=1)
        if day.weekday() < 5:
            out.append(day)
    return out


def short_volume_high(row: dict | None) -> bool:
    return bool(row) and row.get("ratio") is not None and row["ratio"] >= SHORT_RATIO_HIGH and row.get("total", 0) >= SHORT_MIN_TOTAL


class BudgetExceeded(RuntimeError):
    """A call refused before any request was made, because its source reached its cap."""


class Budget:
    """Explicit call caps per source: per sweep for polled sources, per process for start-up loads. A source without a cap
    is refused (fail closed). The caps, the calls and the refusals are written to monitor.jsonl."""

    def __init__(self, per_sweep: dict | None = None, once: dict | None = None):
        self.per_sweep, self.once = dict(per_sweep or {}), dict(once or {})
        self.used, self.used_once, self.refused = defaultdict(int), defaultdict(int), defaultdict(int)
        self.lock = threading.Lock()

    def configure(self, per_sweep: dict, once: dict) -> None:
        with self.lock:
            self.per_sweep.update(per_sweep)
            self.once.update(once)

    def start_sweep(self) -> None:
        with self.lock:
            self.used.clear()

    def take(self, source: str) -> bool:
        with self.lock:
            used, cap = (self.used, self.per_sweep[source]) if source in self.per_sweep else (self.used_once, self.once.get(source, 0))
            if used[source] >= cap:
                self.refused[source] += 1
                return False
            used[source] += 1
            return True


def plan_budget(symbols: int, a) -> dict:
    """The per-source call plan for a universe of ``symbols`` names. ``refusals`` names every rule the plan breaks: data
    REST calls (steady rate plus the one-off daily-bar load in the first minute) above 5% of the 10,000/min data limit,
    trading REST calls above 5% of the 200/min trading limit, or the Nasdaq RSS polled more than once a minute."""
    refusals = []
    if (a.sweep_seconds <= 0 or a.edgar_seconds <= 0 or a.option_roots < 0 or a.option_pages < 1 or a.oi_per_sweep < 0
            or not 0 < a.option_strike_band < 1 or a.option_min_dte < 0 or a.option_window_days < 0 or a.iex_conflict_wait < 0
            or a.ca_context_days < 0):
        return {"symbols": symbols, "refusals": ["invalid_bounds"]}
    sweeps_per_min = 60.0 / a.sweep_seconds
    chunks, adv = math.ceil(symbols / 500), math.ceil(symbols / 200)
    per_sweep = {"snapshots": chunks, "screener": 3 if a.screener else 0,
                 "option_chains": a.option_roots * a.option_pages if a.option_chains else 0,
                 "option_contracts": a.oi_per_sweep if a.option_oi else 0,
                 "edgar": len(EDGAR_FORMS), "nasdaq_halts": 1, "finra": 1 if a.finra else 0}
    once = {"assets": 5, "sec_files": 5, "adv_bars": 4 * adv}   # start-up loads, retries included
    data_per_min = (per_sweep["snapshots"] + per_sweep["screener"] + per_sweep["option_chains"]) * sweeps_per_min
    trading_per_min = per_sweep["option_contracts"] * sweeps_per_min + 1   # plus the start-up assets load
    caps = {"data": DATA_LIMIT_PER_MIN * BUDGET_FRACTION, "trading": TRADING_LIMIT_PER_MIN * BUDGET_FRACTION}
    if data_per_min + adv > caps["data"]:
        refusals.append("data_calls_above_5pct_of_limit")
    if trading_per_min > caps["trading"]:
        refusals.append("trading_calls_above_5pct_of_limit")
    if a.rss_seconds < RSS_MIN_SECONDS:
        refusals.append("nasdaq_rss_more_than_once_per_minute")
    return {"symbols": symbols, "sweep_seconds": a.sweep_seconds, "sweeps_per_min": round(sweeps_per_min, 3), "per_sweep": per_sweep,
            "once": once, "data_per_min": round(data_per_min, 1), "data_first_min": round(data_per_min + adv, 1),
            "data_cap_per_min": caps["data"], "trading_per_min": round(trading_per_min, 1), "trading_cap_per_min": caps["trading"],
            "sec_per_min": round(len(EDGAR_FORMS) * min(sweeps_per_min, 60.0 / a.edgar_seconds), 1),
            "nasdaq_per_min": round(min(sweeps_per_min, 60.0 / a.rss_seconds), 2), "finra_per_sweep": per_sweep["finra"],
            "streams": {"news": {"connections": 1}, "opra": {"connections": 1},
                        "iex_status": {"connections": 1 if a.iex_status else 0, "conflict_wait_s": a.iex_conflict_wait},
                        "corporate_actions": {"connects_per_min": CA_CONNECTS_PER_MIN if a.corporate_actions else 0,
                                              "endpoint_limit_per_min": 20, "context_replays_per_start": 1 if a.corporate_actions else 0}},
            "refusals": refusals}


def acquire_lease(directory: Path, endpoint: str):
    """(descriptor, None) holding this host's exclusive lease on one stream endpoint, or (None, reason). A lease held by
    another process refuses the stream before it connects; a lease directory that cannot be used is reported, not fatal."""
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(directory / f"{endpoint}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        return None, f"lease_unavailable: {type(exc).__name__}"
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        return None, ("lease_held" if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES) else f"lease_unavailable: {type(exc).__name__}")
    try:
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())  # informational: the lock is the lease
    except OSError:
        pass
    return fd, None


def default_lease_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR") or Path.home() / ".cache") / "alpaca-stream-leases"


# ---------------------------------------------------------------- network

def source_of(url: str) -> str:
    """The budgeted source a request belongs to, from its host and path."""
    return next((name for key, name in SOURCES if key in url), "other")


class Http:
    """GET with per-kind and per-source call counts. With a budget, a call over its source's cap is refused before any
    request; the data and trading APIs' rate-limit headers are kept per host."""

    def __init__(self, alpaca_headers: dict, sec_ua: str | None, budget: Budget | None = None):
        self.alpaca, self.sec_ua, self.calls = alpaca_headers, sec_ua, defaultdict(int)
        self.budget, self.source_calls, self.ratelimit, self.lock = budget, defaultdict(int), {}, threading.Lock()

    def get(self, url: str, kind: str, headers: dict, timeout: float = 20) -> bytes:
        source = source_of(url)
        with self.lock:
            if self.budget is not None and not self.budget.take(source):
                raise BudgetExceeded(source)
            self.calls[kind] += 1
            self.source_calls[source] += 1
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            limit = r.headers.get("X-Ratelimit-Limit")
            if limit is not None:
                with self.lock:
                    self.ratelimit[urllib.parse.urlsplit(url).hostname] = {
                        "limit": limit, "remaining": r.headers.get("X-Ratelimit-Remaining"), "reset": r.headers.get("X-Ratelimit-Reset")}
            return r.read()

    def data_remaining(self) -> int | None:
        try:
            return int((self.ratelimit.get("data.alpaca.markets") or {}).get("remaining"))
        except (TypeError, ValueError):
            return None

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
        # monitor v2 sources
        self.haltbook, self.ca, self.iv = HaltBook(), CorporateActions(), IVTracker()
        self.screener, self.oi, self.short_volume = {}, {}, {}   # symbol -> ranks / open-interest summary / FINRA row
        self.short_volume_day, self.no_options, self.finra_missing = None, set(), {}
        self.iex_tapes = defaultdict(int)                          # message type and tape -> count, to measure tape coverage
        self.restored_v2 = {}


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
    for row in lines("halts"):
        if row.get("HaltDate") == state.today.strftime("%m/%d/%Y") and row.get("IssueSymbol"):
            key = (row["IssueSymbol"], row.get("HaltDate"), row.get("HaltTime"))
            if key not in state.halt_rows:
                state.halts[row["IssueSymbol"]].append(row)
            state.halt_rows[key] = {k: v for k, v in row.items() if k != "received_at"}
            counts["halts"] += 1
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


def jsonl(path: Path, counts: dict | None = None):
    if path.exists():
        with path.open() as f:
            for line in f:
                try:
                    yield json.loads(line)
                except ValueError:
                    if counts is not None:
                        counts[f"{path.stem}_unreadable"] += 1


def day_dirs(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("[0-9]" * 8) if p.is_dir())


def restore_v2(state: State, root: Path, day_dir: Path) -> dict:
    """Rebuild the v2 sources' session state after a restart: the merged halt state (stream and RSS), LULD bands, today's
    and the previous session's implied volatility, and today's open interest."""
    counts = defaultdict(int)
    for row in jsonl(day_dir / "status.jsonl", counts):
        counts["status"] += state.haltbook.stream_status(row, row.get("received_at"))
    for row in jsonl(day_dir / "halts.jsonl", counts):
        if row.get("HaltDate") == state.today.strftime("%m/%d/%Y"):
            counts["rss_events"] += state.haltbook.rss_row(row)
    for row in jsonl(day_dir / "luld.jsonl", counts):
        state.haltbook.set_band(row, row.get("received_at"))
        counts["luld"] += 1
    earlier = [d for d in day_dirs(root) if d.name < day_dir.name and (d / "options-iv.jsonl").exists()]
    for row in (jsonl(earlier[-1] / "options-iv.jsonl", counts) if earlier else ()):
        if row.get("symbol") and valid_iv(row.get("atm_iv")) and utc(row.get("received_at")) is not None:
            state.iv.prev[row["symbol"]] = {"at": row.get("received_at"), "iv": row["atm_iv"], "expiry": row.get("expiry")}
            counts["options_iv_previous"] += 1
    for row in jsonl(day_dir / "options-iv.jsonl", counts):
        at = utc(row.get("received_at"))
        if at is not None and row.get("symbol"):
            state.iv.observe(row["symbol"], at, row)
            counts["options_iv"] += 1
    for row in jsonl(day_dir / "options-oi.jsonl", counts):
        if row.get("symbol"):
            state.oi[row["symbol"]] = {k: v for k, v in row.items() if k not in ("symbol", "received_at")}
            counts["options_oi"] += 1
    return dict(counts)


def last_archived_event_id(root: Path) -> str | None:
    """The newest event id in the most recent corporate-actions archive (the stream's resume point)."""
    for folder in reversed(day_dirs(root)):
        ids = [r.get("event_id") for r in jsonl(folder / "corporate-actions.jsonl")]
        ids = [i for i in ids if isinstance(i, str) and EVENT_ID.match(i)]
        if ids:
            return max(ids)
    return None


def load_short_volume(root: Path, upto: date, prior: int = 5) -> tuple[str | None, dict]:
    """The newest stored FINRA file up to ``upto``, joined per symbol, with each symbol's mean ratio over up to ``prior``
    earlier stored files (context only; no request is made)."""
    stamp = upto.strftime("%Y%m%d")
    files = sorted(p for p in (root / "finra").glob("CNMSshvol*.txt") if p.stem[len("CNMSshvol"):] <= stamp)
    if not files:
        return None, {}
    day, rows = parse_finra(files[-1].read_bytes())
    history = defaultdict(list)
    for path in files[-1 - prior:-1]:
        try:
            _, older = parse_finra(path.read_bytes())
        except ValueError:
            continue
        for symbol, row in older.items():
            if row["ratio"] is not None:
                history[symbol].append(row["ratio"])
    for symbol, row in rows.items():
        row["date"] = day
        if history.get(symbol):
            row.update({"ratio_prior_mean": round(statistics.fmean(history[symbol]), 4), "prior_files": len(history[symbol])})
    return day, rows


def root_symbol(root: str, universe: set) -> str | None:
    """The equity for an option root: itself, an adjusted root less its digit (TSLA1), or a class root (BRKB -> BRK.B)."""
    if root in universe:
        return root
    stripped = root.rstrip("0123456789")
    if stripped != root and stripped in universe:
        return stripped
    dotted = f"{root[:-1]}.{root[-1]}" if len(root) > 1 else None
    return dotted if dotted in universe else None


def load_assets(http: Http) -> dict:
    """Active tradable US equities: symbol -> Alpaca asset name."""
    assets = http.alpaca_json(TRADING, "/v2/assets", {"status": "active", "asset_class": "us_equity"})
    return {a["symbol"]: a.get("name") or "" for a in assets if a.get("tradable") and "/" not in a["symbol"] and " " not in a["symbol"]}


def load_universe(http: Http) -> list[str]:
    return sorted(load_assets(http))


def load_fund_tickers(http: Http) -> set:
    body = json.loads(http.sec(EDGAR_FUND_TICKERS))
    column = body["fields"].index("symbol")
    return {str(row[column]).replace("-", ".") for row in body["data"]}


def operating_symbols(names: dict, company_tickers: set, fund_tickers: set) -> set:
    """Operating companies: an SEC company ticker, not a registered fund's, and no fund-like word in the asset name."""
    return {s for s, name in names.items() if s in company_tickers and s not in fund_tickers and not FUND_NAME.search(name)}


def retry(call, attempts: int = 5, first_wait: float = 2.0):
    for attempt in range(attempts):
        try:
            return call()
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(first_wait * 2 ** attempt)


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


def sweep_snapshots(http: Http, symbols: list[str], state: State, sink: Sink, at: datetime, workers: int = 1) -> list[dict]:
    """One SIP snapshot of every symbol (500 per call); ``workers`` > 1 fetches the chunks concurrently, same calls."""
    def fetch(chunk):
        body = http.alpaca_json(DATA, "/v2/stocks/snapshots", {"symbols": ",".join(chunk), "feed": "sip"})
        return body.get("snapshots", body)
    chunks = [symbols[i:i + 500] for i in range(0, len(symbols), 500)]
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            bodies = list(pool.map(fetch, chunks))
    else:
        bodies = map(fetch, chunks)
    rows = []
    for body in bodies:
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
    """Credit a filing to its issuer only: M&A forms to their Subject, other forms to their Filer; never "Filed by"."""
    role = row.get("role")
    if role == "Filed by" or (row.get("form") in MNA_FORMS and role != "Subject"):
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
        state.haltbook.rss_row(row)  # the merged halt state (board v2); the v1 halt rows below are unchanged
        key = (row["IssueSymbol"], row.get("HaltDate"), row.get("HaltTime"))
        body = {k: v for k, v in row.items() if k != "received_at"}
        if state.halt_rows.get(key) != body:
            state.halt_rows[key] = body
            sink.write("halts", row)
            if key not in {(h["IssueSymbol"], h.get("HaltDate"), h.get("HaltTime")) for h in state.halts[row["IssueSymbol"]]}:
                state.halts[row["IssueSymbol"]].append(row)
            changed += 1
    return changed


# Components that are not derived from the name's own price or volume (volatility halts are price-triggered).
NON_PRICE_PARTS = {"news", "mna_filing", "material_8k", "dilution_filing", "news_halt", "short_dated_calls", "large_option_prints"}


def score_candidates(state: State, at: datetime, extra=frozenset()) -> dict:
    """Board v1 rows (``score`` unchanged) for every v1 candidate and any ``extra`` symbols, keyed by symbol."""
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
    rows = {}
    for symbol in candidates | set(extra):
        feat = state.features.get(symbol)
        adv = state.adv.get(symbol)
        relvol = (feat["v"] / (adv * fraction)) if (feat and feat.get("v") and adv and fraction) else None
        articles = state.news.get(symbol) or {}
        for article in [a for a, received in articles.items() if received < horizon]:
            del articles[article]
        rows[symbol] = score(symbol, feat, relvol, len(articles), state.filings.get(symbol, []), state.halts.get(symbol, []), options.get(symbol))
    return rows


def build_board(state: State, at: datetime, top: int = 100, rows: dict | None = None) -> tuple[list[dict], list[str]]:
    """(board, incentive_symbols) of board version 1: rows scoring at least 2, and every symbol with any component other
    than relvol. ``rows`` may carry this sweep's score_candidates result."""
    rows = score_candidates(state, at) if rows is None else rows
    incentive = sorted(s for s, row in rows.items() if set(row["parts"]) & NON_PRICE_PARTS)
    board = sorted((row for row in rows.values() if row["score"] >= 2), key=lambda r: (-r["score"], r["symbol"]))
    return board[:top], incentive


# Board v2 non-price components: v1's plus a stream news halt, a corporate action and an implied-volatility run-up.
NON_PRICE_PARTS_V2 = NON_PRICE_PARTS | {"stream_news_halt", "corporate_action", "iv_runup"}


def v2_components(state: State, symbol: str, row: dict, at: datetime, actions: dict) -> tuple[dict, dict]:
    """(parts, context) that board v2 adds to a v1 row; the rules are V2_RULES and the weights V2_WEIGHTS."""
    parts, context, v1 = {}, {}, row["parts"]
    halt = state.haltbook.state(symbol, at)
    if halt:
        context["halt"] = halt
    band = state.haltbook.band(symbol, row.get("price"))
    if band:
        context["luld"] = band
    category = state.haltbook.stream_category(symbol)
    if category == "news" and "news_halt" not in v1:
        parts["stream_news_halt"] = V2_WEIGHTS["stream_news_halt"]
    elif category == "volatility" and not {"news_halt", "volatility_halt"} & set(v1):
        parts["stream_volatility_halt"] = V2_WEIGHTS["stream_volatility_halt"]
    items = actions.get(symbol)
    if items:
        context["corporate_actions"] = items
        if any(item["in_window"] for item in items):
            parts["corporate_action"] = V2_WEIGHTS["corporate_action"]
    iv, oi = state.iv.change(symbol, at), state.oi.get(symbol)
    if iv or oi:
        context["options"] = {**(iv or {}), **({k: oi.get(k) for k in ("call_oi", "put_oi", "oi_date", "truncated")} if oi else {})}
    if state.iv.runup(symbol, at):
        parts["iv_runup"] = V2_WEIGHTS["iv_runup"]
    sv = state.short_volume.get(symbol)
    if sv:
        context["short_volume"] = sv
        if short_volume_high(sv):
            parts["short_volume_high"] = V2_WEIGHTS["short_volume_high"]
    if state.screener.get(symbol):
        context["screener"] = state.screener[symbol]
    return parts, context


def v2_symbols(state: State, at: datetime, actions: dict) -> set:
    """Symbols that only the v2 sources make candidates (limited to the tradable universe once it is loaded)."""
    found = state.haltbook.symbols("stream") | {s for s, items in actions.items() if any(i["in_window"] for i in items)}
    found |= {s for s in list(state.iv.last) if state.iv.runup(s, at)}
    found |= {s for s, row in state.short_volume.items() if short_volume_high(row)}
    return found & state.universe if state.universe else found


def build_board_v2(state: State, at: datetime, top: int = 100) -> tuple[list[dict], list[str]]:
    """(board, incentive_symbols) of board version 2: every v1 part and weight unchanged (``score_v1`` keeps the v1 score),
    plus the v2 parts; the same threshold of 2. Unvalidated: a detector to be tested prospectively."""
    actions = state.ca.by_symbol(state.today)
    board, incentive = [], []
    for symbol, row in score_candidates(state, at, v2_symbols(state, at, actions)).items():
        parts, context = v2_components(state, symbol, row, at, actions)
        merged = {**row["parts"], **parts}
        out = {**row, "score": round(sum(merged.values()), 3), "score_v1": row["score"], "parts": merged}
        if context:
            out["context"] = context
        if set(merged) & NON_PRICE_PARTS_V2:
            incentive.append(symbol)
        if out["score"] >= 2:
            board.append(out)
    board.sort(key=lambda r: (-r["score"], r["symbol"]))
    return board[:top], sorted(incentive)


def board_payloads(at: datetime, board: list, incentive: list, board_v2: list, incentive_v2: list, monitor: dict) -> tuple[dict, dict]:
    """(board.json, board-v2.json): board version 1 (the frozen forward protocol's) and board version 2."""
    stamp = at.isoformat(timespec="seconds")
    return ({"at": stamp, "board_version": BOARD_VERSION, "evidence_class": "unvalidated_detector", "board": board,
             "incentive_symbols": incentive, "monitor": monitor},
            {"at": stamp, "board_version": BOARD_V2_VERSION, "evidence_class": "unvalidated_detector", "weights_v2": V2_WEIGHTS,
             "rules_v2": V2_RULES, "board": board_v2, "incentive_symbols": incentive_v2, "monitor": monitor})


def halt_snapshot(state: State, at: datetime) -> dict:
    return {"at": iso(at), "symbols": {s: found for s in sorted(state.haltbook.symbols()) if (found := state.haltbook.state(s, at))}}


# ---------------------------------------------------------------- v2 polled sources (each call inside the budget)

def poll_screener(http: Http, state: State, sink: Sink) -> int:
    """Most actives by volume and by trades (top 100 each) and the top movers (50 gainers, 50 losers): three calls."""
    by_volume = http.alpaca_json(DATA, SCREENER_ACTIVES, {"by": "volume", "top": 100})
    by_trades = http.alpaca_json(DATA, SCREENER_ACTIVES, {"by": "trades", "top": 100})
    movers = http.alpaca_json(DATA, SCREENER_MOVERS, {"top": 50})
    sink.write("screener", {"received_at": now_utc(), "most_actives_volume": by_volume, "most_actives_trades": by_trades, "movers": movers})
    state.screener = screener_ranks(by_volume, by_trades, movers)
    return len(state.screener)


def option_targets(rows: dict, state: State, n: int) -> list[str]:
    """The top ``n`` board candidates by v1 score (then relative volume, then symbol) not known to lack options."""
    ranked = sorted((r for r in rows.values() if r["score"] > 0 and r["symbol"] not in state.no_options),
                    key=lambda r: (-r["score"], -(r.get("relvol") or -1), r["symbol"]))
    return [r["symbol"] for r in ranked[:n]]


def chain_params(price: float | None, today: date, a) -> dict:
    first = today + timedelta(days=a.option_min_dte)
    params = {"expiration_date_gte": first.isoformat(), "expiration_date_lte": (first + timedelta(days=a.option_window_days)).isoformat()}
    if price:
        params.update({"strike_price_gte": round(price * (1 - a.option_strike_band), 2), "strike_price_lte": round(price * (1 + a.option_strike_band), 2)})
    return params


def fetch_chain(http: Http, symbol: str, price: float | None, today: date, a) -> tuple[dict, bool, int]:
    """(snapshots, truncated, pages): the chain from the first expiry at least option_min_dte days out, strikes within the
    band around the price, at most option_pages pages of 1,000 contracts."""
    params = {"feed": "opra", "limit": 1000, **chain_params(price, today, a)}
    snapshots, token, pages = {}, None, 0
    while pages < a.option_pages:
        if token:
            params["page_token"] = token
        body = http.alpaca_json(DATA, OPTION_CHAIN.format(symbol=urllib.parse.quote(symbol, safe="")), params)
        pages += 1
        snapshots.update(body.get("snapshots") or {})
        token = body.get("next_page_token")
        if not token:
            break
    return snapshots, bool(token), pages


def poll_option_chains(http: Http, state: State, sink: Sink, a, targets: list[str]) -> dict:
    """Chain snapshots for the targets (four at a time); each root's near-the-money summary goes to options-iv.jsonl."""
    stats = defaultdict(int)

    def one(symbol):
        snapshots, truncated, pages = fetch_chain(http, symbol, (state.features.get(symbol) or {}).get("p"), state.today, a)
        return snapshots, truncated, pages, now_utc()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [(symbol, pool.submit(one, symbol)) for symbol in targets]
        for symbol, future in futures:
            try:
                snapshots, truncated, pages, received = future.result()
            except BudgetExceeded:
                stats["budget_refused"] += 1
                continue
            except urllib.error.HTTPError as exc:
                stats[f"http_{exc.code}"] += 1
                if 400 <= exc.code < 500 and exc.code != 429:
                    state.no_options.add(symbol)
                continue
            except Exception:  # one root never stops the others
                stats["errors"] += 1
                continue
            if not snapshots:
                state.no_options.add(symbol)
                stats["empty"] += 1
                continue
            price = (state.features.get(symbol) or {}).get("p")
            summary = chain_summary(symbol, snapshots, price, state.today, (state.oi.get(symbol) or {}).get("by_contract"))
            state.iv.observe(symbol, utc(received), summary)
            sink.write("options-iv", {"received_at": received, "symbol": symbol, "price": price, "pages": pages, "truncated": truncated, **summary})
            stats["roots"] += 1
    return dict(stats)


def poll_option_oi(http: Http, state: State, sink: Sink, a, targets: list[str]) -> int:
    """Open interest (the contracts endpoint, trading API) for targets not yet fetched today, oi_per_sweep at most."""
    fetched = 0
    for symbol in [s for s in targets if s not in state.oi][:a.oi_per_sweep]:
        params = {"underlying_symbols": symbol, "status": "active", "limit": 10000,
                  **chain_params((state.features.get(symbol) or {}).get("p"), state.today, a)}
        try:
            body = http.alpaca_json(TRADING, OPTION_CONTRACTS, params)
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                state.oi[symbol] = {"error": f"http_{exc.code}"}  # a refused root is not asked again today
                continue
            raise
        summary = oi_summary(body.get("option_contracts") or [], bool(body.get("next_page_token")))
        state.oi[symbol] = summary
        sink.write("options-oi", {"received_at": now_utc(), "symbol": symbol, **summary})
        fetched += 1
    return fetched


def poll_finra(http: Http, state: State, sink: Sink, now: datetime) -> str | None:
    """At most one request per sweep: the newest due FINRA file not yet stored. A missing file (a holiday, or not posted
    yet) is retried after an hour while earlier weekdays are tried; stored files are never fetched again."""
    due = finra_due(now)
    for day in weekdays_back(due, 5):
        stamp = day.strftime("%Y%m%d")
        if (sink.root / "finra" / f"CNMSshvol{stamp}.txt").exists():
            if state.short_volume_day != stamp:
                state.short_volume_day, state.short_volume = load_short_volume(sink.root, due)
            return None
        if time.time() - state.finra_missing.get(stamp, -math.inf) < 3600:
            continue
        url = FINRA_SHORT_VOLUME.format(day=stamp)
        try:
            payload = http.get(url, "finra", GENERIC_UA)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):  # the file store answers a missing key with 403
                state.finra_missing[stamp] = time.time()
                return f"missing:{stamp}"
            raise
        received = now_utc()
        parsed_day, rows = parse_finra(payload)  # a malformed file raises and nothing is stored
        if parsed_day != stamp:
            raise ValueError("finra_date_mismatch")
        sink.replace(f"finra/CNMSshvol{stamp}.txt", payload, shared=True)
        sink.replace(f"finra/CNMSshvol{stamp}.json", json.dumps({"url": url, "date": stamp, "received_at": received, "rows": len(rows),
                                                                  "sha256": hashlib.sha256(payload).hexdigest()}).encode(), shared=True)
        state.short_volume_day, state.short_volume = load_short_volume(sink.root, due)
        return stamp
    return None


# ---------------------------------------------------------------- streams

class StreamError(ConnectionError):
    """An error message from a stream endpoint, with its code (406: connection limit exceeded)."""

    def __init__(self, name: str, code):
        super().__init__(f"{name}:{code}")
        self.code = code


async def stream(name: str, url: str, subscribe: dict, headers: dict, on_message, state: State, sink: Sink, stop: asyncio.Event, packed: bool,
                 conflict_wait: float | None = None):
    """Hold one stream with bounded reconnects. With ``conflict_wait``, a 406 (another holder of the endpoint) waits that
    long before the next attempt instead of contending for the connection."""
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
                            raise StreamError(name, msg.get("code"))
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
            conflict = conflict_wait is not None and getattr(exc, "code", None) == 406
            sink.write("monitor", {"event": "stream_conflict" if conflict else "stream_down", "stream": name,
                                   "error": f"{type(exc).__name__}: {str(exc)[:200]}", "attempt": attempt, "at": now_utc()})
            try:
                await asyncio.wait_for(stop.wait(), timeout=conflict_wait if conflict else min(60, 2 ** attempt))
            except asyncio.TimeoutError:
                pass


class EventStream:
    """The corporate-actions event stream (Server-Sent Events). Every event is archived to corporate-actions.jsonl with its
    receive time and fed to the corporate-action context; ids are deduplicated (a resume redelivers the last id); the stream
    resumes with Last-Event-Id, or starts at ``start`` when nothing is archived; connects stay within a per-minute budget."""

    def __init__(self, headers: dict, sink: Sink, state: State, start: datetime, last_id: str | None = None, opener=None,
                 connects_per_min: int = CA_CONNECTS_PER_MIN, timeout: float = CA_READ_TIMEOUT, backoff=None, url: str = CA_EVENTS):
        self.headers = {**headers, "Accept": "text/event-stream", "Cache-Control": "no-cache"}
        self.sink, self.state, self.start, self.last_id, self.url = sink, state, start, last_id, url
        self.opener = opener or urllib.request.urlopen
        self.connects_per_min, self.timeout = connects_per_min, timeout
        self.backoff = backoff or (lambda attempt: min(300.0, 5.0 * 2 ** min(attempt, 6)))
        self.stop_event, self.response, self.connects, self.counts = threading.Event(), None, deque(), defaultdict(int)

    def request(self, params: dict | None, last_id: str | None) -> urllib.request.Request:
        headers = {**self.headers, **({"Last-Event-Id": last_id} if last_id else {})}
        return urllib.request.Request(self.url + ("?" + urllib.parse.urlencode(params) if params else ""), headers=headers)

    def may_connect(self) -> bool:
        now = time.monotonic()
        while self.connects and now - self.connects[0] >= 60:
            self.connects.popleft()
        if len(self.connects) >= self.connects_per_min:
            return False
        self.connects.append(now)
        return True

    def consume(self, lines, archive: bool) -> int:
        events = 0
        for ev in sse_events(lines):
            received = now_utc()
            try:
                items = ca_event_list(ev["data"])
            except ValueError:
                self.counts["unparsed"] += 1
                if archive:
                    self.sink.write("corporate-actions", {"received_at": received, "sse_id": ev["id"], "unparsed": ev["data"][:2000]})
                continue
            for item in items:
                eid = item.get("event_id")
                valid = isinstance(eid, str) and EVENT_ID.match(eid) is not None
                if archive:
                    if valid and self.last_id is not None and eid <= self.last_id:
                        self.counts["duplicates"] += 1
                        continue
                    self.sink.write("corporate-actions", {**item, "received_at": received, "sse_id": ev["id"]})
                    self.counts["archived"] += 1
                    if valid:
                        self.last_id = eid
                else:
                    self.counts["context_events"] += 1
                self.counts["surfaced"] += self.state.ca.observe(item)
                events += 1
            if self.stop_event.is_set():
                break
        return events

    def replay_context(self, since: datetime, until: datetime) -> int:
        """One bounded replay of the surfaced types (the server closes after ``until``) to build the board context."""
        params = {"type": ",".join(t + CA_SUFFIX for t in CA_TYPES), "since": rfc3339(since), "until": rfc3339(until)}
        self.counts["context_replays"] += 1
        with self.opener(self.request(params, None), timeout=self.timeout) as resp:
            return self.consume(resp, archive=False)

    def run(self) -> None:
        attempt = 0
        while not self.stop_event.is_set():
            if not self.may_connect():
                self.counts["connect_budget_waits"] += 1
                self.stop_event.wait(5.0)
                continue
            self.counts["connects"] += 1
            try:
                params = None if self.last_id else {"since": rfc3339(self.start)}
                with self.opener(self.request(params, self.last_id), timeout=self.timeout) as resp:
                    self.response = resp
                    if "corporate_actions" in self.state.down_since:
                        self.state.down_seconds["corporate_actions"] += time.time() - self.state.down_since.pop("corporate_actions")
                    self.sink.write("monitor", {"event": "stream_connected", "stream": "corporate_actions", "resume_id": self.last_id,
                                                "since": None if params is None else params["since"], "at": now_utc()})
                    attempt = 0
                    self.consume(resp, archive=True)
                reason = "closed_by_server"
            except Exception as exc:  # reconnect with backoff inside the connect budget; every disconnect is recorded
                reason = f"{type(exc).__name__}: {str(exc)[:200]}"
            finally:
                self.response = None
            if self.stop_event.is_set():
                break
            attempt += 1
            self.state.down_since.setdefault("corporate_actions", time.time())
            self.sink.write("monitor", {"event": "stream_down", "stream": "corporate_actions", "error": reason, "attempt": attempt, "at": now_utc()})
            self.stop_event.wait(self.backoff(attempt))

    def close(self) -> None:
        """Stop the loop and unblock a pending read by shutting the socket down."""
        self.stop_event.set()
        resp = self.response
        sock = getattr(getattr(getattr(resp, "fp", None), "raw", None), "_sock", None)
        try:
            if sock is not None:
                sock.shutdown(socket.SHUT_RDWR)
            elif resp is not None:
                resp.close()
        except OSError:
            pass


async def run(args) -> int:
    key, secret = credentials(args.env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    budget = Budget(once={"assets": 5, "sec_files": 5})  # start-up loads before the plan exists; every other cap follows the plan
    http, sink, state, stop = Http(headers, sec_identity(), budget), Sink(args.out), State(), asyncio.Event()
    until = datetime.combine(state.today, datetime.strptime(args.until_et, "%H:%M").time(), ET)
    optional = (("iex_status_luld", args.iex_status), ("corporate_actions_sse", args.corporate_actions), ("screener", args.screener),
                ("option_chains", args.option_chains), ("option_oi", args.option_oi), ("finra_short_volume", args.finra))
    sink.write("monitor", {"event": "start", "at": now_utc(), "mode": args.mode, "until_et": args.until_et, "sweep_seconds": args.sweep_seconds,
                           "pid": os.getpid(), "sources": ["sip_snapshots", "opra_trades", "news", "edgar", "nasdaq_halts"] + [n for n, on in optional if on],
                           "board_versions": [BOARD_VERSION, BOARD_V2_VERSION]})
    symbols = await asyncio.to_thread(retry, lambda: load_universe(http))
    state.universe = set(symbols)
    plan = plan_budget(len(symbols), args)
    sink.write("monitor", {"event": "budget", "at": now_utc(), **plan})
    if plan["refusals"]:
        sink.write("monitor", {"event": "stop", "at": now_utc(), "refused": plan["refusals"]})
        sink.close()
        return 2
    budget.configure(plan["per_sweep"], plan["once"])
    state.cik_tickers = await asyncio.to_thread(retry, lambda: load_cik_tickers(http))
    code_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()  # the code this process loaded
    state.restored = restore(state, sink.path(""))
    state.restored_v2 = restore_v2(state, sink.root, sink.path(""))
    if args.finra:
        try:
            state.short_volume_day, state.short_volume = load_short_volume(sink.root, finra_due(datetime.now(timezone.utc)))
        except (OSError, ValueError) as exc:
            state.restored_v2["finra_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    sink.write("monitor", {"event": "restored", "at": now_utc(), "counts": state.restored, "counts_v2": state.restored_v2})
    adv_task = asyncio.create_task(asyncio.to_thread(load_adv, http, symbols, state.today))
    events = None
    if args.corporate_actions:
        last_id, start = last_archived_event_id(sink.root), datetime.combine(state.today, dtime(0, 0), ET)
        emitted = ulid_time(last_id)
        if last_id and (emitted is None or datetime.now(timezone.utc) - emitted > timedelta(days=CA_RESUME_MAX_DAYS)):
            sink.write("monitor", {"event": "ca_resume_gap", "at": now_utc(), "last_id": last_id, "since": rfc3339(start)})
            last_id = None
        events = EventStream(headers, sink, state, start, last_id=last_id)
        since = datetime.combine(state.today - timedelta(days=args.ca_context_days), dtime(0, 0), ET)
        try:
            replayed = await asyncio.to_thread(events.replay_context, since, datetime.now(timezone.utc) - timedelta(seconds=60))
            sink.write("monitor", {"event": "ca_context", "at": now_utc(), "since": rfc3339(since), "events": replayed, "actions": len(state.ca.actions)})
        except Exception as exc:  # the archive stream still runs; the context then builds from its events only
            sink.write("monitor", {"event": "ca_context_error", "at": now_utc(), "error": f"{type(exc).__name__}: {str(exc)[:160]}"})

    def on_news(msg):
        received = now_utc()
        sink.write("news", news_record(msg, received))
        for symbol in msg.get("symbols") or []:
            if msg.get("id") is not None:
                state.news[symbol].setdefault(msg["id"], time.time())

    def on_opra(msg):
        if msg.get("T") == "t":
            state.options.add(msg, state.today)

    def on_iex(msg):
        received, kind = now_utc(), msg.get("T")
        state.iex_tapes[f"{kind}:{msg.get('z')}"] += 1
        if kind == "s":
            sink.write("status", {**msg, "received_at": received})
            state.haltbook.stream_status(msg, received)
        elif kind == "l":
            sink.write("luld", {**msg, "received_at": received})
            state.haltbook.set_band(msg, received)
        elif kind == "i":
            sink.write("imbalance", {**msg, "received_at": received})

    tasks, threads, leases = [], [], []

    def leased(endpoint: str) -> bool:
        """Hold this host's lease on a stream endpoint; a lease held by another process refuses the stream before it connects."""
        fd, reason = acquire_lease(args.lease_dir, endpoint)
        if fd is not None:
            leases.append(fd)
            return True
        sink.write("monitor", {"event": "stream_refused" if reason == "lease_held" else "lease_unavailable", "endpoint": endpoint,
                               "reason": reason, "at": now_utc()})
        return reason != "lease_held"

    if args.mode == "run":
        if leased("v1beta1-news"):
            tasks.append(asyncio.create_task(stream("news", NEWS_WS, {"action": "subscribe", "news": ["*"]}, headers, on_news, state, sink, stop, False)))
        if leased("v1beta1-opra"):
            tasks.append(asyncio.create_task(stream("opra", OPRA_WS, {"action": "subscribe", "trades": ["*"]}, headers, on_opra, state, sink, stop, True)))
        if args.iex_status and leased("v2-iex"):
            tasks.append(asyncio.create_task(stream("iex_status", IEX_WS, {"action": "subscribe", "statuses": ["*"], "lulds": ["*"], "imbalances": ["*"]},
                                                    headers, on_iex, state, sink, stop, False, conflict_wait=args.iex_conflict_wait)))
        if events is not None and leased("v1beta1-events-corporate-actions"):
            threads.append(threading.Thread(target=events.run, name="corporate-actions", daemon=True))
            threads[-1].start()
    stop_file = args.out / "STOP"
    last_edgar = last_rss = -math.inf
    try:
        while True:
            started, at = time.monotonic(), datetime.now(timezone.utc)
            budget.start_sweep()
            before = dict(http.source_calls)
            stats = {"event": "sweep", "at": at.isoformat(timespec="seconds")}
            if adv_task.done() and not state.adv:
                try:
                    state.adv = adv_task.result()
                    if not state.adv:
                        raise ValueError("no daily bars returned")
                    sink.replace("adv20.json", json.dumps(state.adv, sort_keys=True).encode())
                except Exception as exc:  # retried next sweep; relvol stays empty meanwhile
                    stats["adv_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
                    adv_task = asyncio.create_task(asyncio.to_thread(load_adv, http, symbols, state.today))
            remaining = http.data_remaining()
            spare = remaining is None or remaining >= RATELIMIT_FLOOR  # optional data sources pause below the floor
            if not spare:
                stats["ratelimit_floor"] = remaining
            jobs = [("snapshots", lambda: len(sweep_snapshots(http, symbols, state, sink, at, workers=3)))]
            if started - last_edgar >= args.edgar_seconds:
                last_edgar = started
                jobs.append(("edgar_new", lambda: poll_edgar(http, state, sink)))
            if started - last_rss >= args.rss_seconds:
                last_rss = started
                jobs.append(("halt_changes", lambda: poll_halts(http, state, sink)))
            if args.screener and spare:
                jobs.append(("screener", lambda: poll_screener(http, state, sink)))
            if args.finra:
                jobs.append(("finra", lambda: poll_finra(http, state, sink, at)))
            results = await asyncio.gather(*(asyncio.to_thread(job) for _, job in jobs), return_exceptions=True)
            for (label, _), result in zip(jobs, results):  # one failing source never stops the others
                if isinstance(result, BaseException):
                    stats[f"{label}_error"] = f"{type(result).__name__}: {str(result)[:160]}"
                else:
                    stats[label] = result
            # Labelled with the drain time: a row holds trades received up to this moment.
            rows, large = state.options.drain(datetime.now(ET).isoformat(timespec="seconds"))
            for row in rows:
                sink.write("options-minute", row)
            for row in large:
                sink.write("options-large", row)
            if state.features:
                sink.write("regime", regime(list(state.features.values()), state.adv, at))
            v1_rows = score_candidates(state, at)
            board, incentive = build_board(state, at, rows=v1_rows)
            if args.option_chains and spare:  # the top candidates by the v1 score; the v1 board is already fixed
                targets = option_targets(v1_rows, state, args.option_roots)
                for label, job in (("option_chains", lambda: poll_option_chains(http, state, sink, args, targets)),
                                   ("option_oi", lambda: poll_option_oi(http, state, sink, args, targets) if args.option_oi else 0)):
                    try:
                        stats[label] = await asyncio.to_thread(job)
                    except Exception as exc:
                        stats[f"{label}_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            board_v2, incentive_v2 = build_board_v2(state, at)
            down = {name: round(state.down_seconds[name] + (time.time() - since if (since := state.down_since.get(name)) else 0), 1)
                    for name in ("news", "opra", "iex_status", "corporate_actions")}
            monitor = {"started_at": state.started_at, "code_sha256": code_sha256, "restored": state.restored, "restored_v2": state.restored_v2,
                       "stream_down_seconds": down, "adv_loaded": bool(state.adv), "sweep_errors": sorted(k for k in stats if k.endswith("_error"))}
            payload, payload_v2 = board_payloads(at, board, incentive, board_v2, incentive_v2, monitor)
            sink.replace("board.json", json.dumps(payload, indent=1).encode())
            sink.write("board", {"at": payload["at"], "board": board[:50]})
            sink.replace("board-v2.json", json.dumps(payload_v2, indent=1).encode())
            sink.write("board-v2", {"at": payload["at"], "board": board_v2[:50]})
            sink.replace("halt-state.json", json.dumps(halt_snapshot(state, at), separators=(",", ":")).encode())
            calls = {k: v - before.get(k, 0) for k, v in http.source_calls.items() if v - before.get(k, 0)}
            stats.update({"board": len(board), "early": sum(r["stage"] == "early" for r in board), "board_v2": len(board_v2),
                          "calls": dict(http.calls), "source_calls": calls, "budget_per_sweep": plan["per_sweep"], "budget_refused": dict(budget.refused),
                          "ratelimit": dict(http.ratelimit), "streams": dict(state.stream_counts), "iex_tapes": dict(state.iex_tapes),
                          "corporate_actions": dict(events.counts) if events else None, "options_unparsed": state.options.unparsed,
                          "seconds": round(time.monotonic() - started, 2)})
            sink.write("monitor", stats)
            if args.mode == "once" or stop_file.exists() or datetime.now(ET) >= until:
                break
            await asyncio.sleep(max(1.0, args.sweep_seconds - (time.monotonic() - started)))
    finally:
        stop.set()
        if events is not None:
            events.close()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for thread in threads:
            await asyncio.to_thread(thread.join, 10)
        if not adv_task.done():
            adv_task.cancel()
        for fd in leases:
            os.close(fd)
        sink.write("monitor", {"event": "stop", "at": now_utc(), "stop_file": stop_file.exists()})
        sink.close()
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("run", "once"))
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--until-et", default="20:00")
    ap.add_argument("--sweep-seconds", type=float, default=20.0, help="sweep cadence; the data plan is refused above 5%% of the data limit")
    ap.add_argument("--edgar-seconds", type=float, default=20.0, help="EDGAR current-filings cycle (7 requests, at most one cycle a sweep)")
    ap.add_argument("--rss-seconds", type=float, default=RSS_MIN_SECONDS, help="Nasdaq halts RSS interval (refused below 60)")
    ap.add_argument("--option-roots", type=int, default=25, help="option chains per sweep: the top board candidates")
    ap.add_argument("--option-pages", type=int, default=1, help="pages of 1,000 contracts per chain")
    ap.add_argument("--option-min-dte", type=int, default=7)
    ap.add_argument("--option-window-days", type=int, default=14)
    ap.add_argument("--option-strike-band", type=float, default=0.10)
    ap.add_argument("--oi-per-sweep", type=int, default=2, help="contracts-endpoint calls per sweep (trading API; once per root per day)")
    ap.add_argument("--ca-context-days", type=int, default=30, help="corporate-action context replayed at start")
    ap.add_argument("--iex-conflict-wait", type=float, default=900.0, help="seconds to wait after a 406 on the IEX endpoint")
    ap.add_argument("--lease-dir", type=Path, default=default_lease_dir(), help="host leases, one per stream endpoint")
    for name in ("iex-status", "corporate-actions", "screener", "option-chains", "option-oi", "finra"):
        ap.add_argument(f"--no-{name}", dest=name.replace("-", "_"), action="store_false", help=f"leave the {name} source off")
    return ap


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
