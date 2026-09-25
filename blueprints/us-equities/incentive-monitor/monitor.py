"""Continuous incentive monitor: records market-side and non-market-side catalyst signals and ranks a board.

  python monitor.py run  --standalone --env-file ENV --out DIR [--until-et 20:00] [--sweep-seconds 20]
  python monitor.py run  --follow-v1 DIR1 --env-file ENV --out DIR2   # version 2 recorder beside a version 1 monitor
  python monitor.py once --standalone --env-file ENV --out DIR        # one sweep of every polled source (no streams)

Every run declares its role. --standalone: no version 1 monitor runs on this account, so this process holds the news
and OPRA streams, polls EDGAR and the Nasdaq RSS, and writes board.json and board-v2.json. --follow-v1 DIR1: a version 1
monitor (whose --out is DIR1) is running; Alpaca allows one connection per stream endpoint and Nasdaq one RSS request a
minute per host, so the follower holds no news or OPRA connection, polls neither EDGAR nor the RSS, reads those inputs
from version 1's files (appended lines only) and writes board-v2.json only. It never writes to DIR1.

Data only: it never places, changes or cancels an order. Sources (entitlements measured on 2026-09-24):

market side   Alpaca SIP snapshots for every active tradable US equity (REST, about 27 calls per sweep against
              a 10,000/min data limit); OPRA option trades for every contract (websocket "*", msgpack),
              aggregated per underlying root and minute with large prints kept whole; trading status, LULD
              bands and imbalances for every symbol on the IEX stock stream (v2/iex, only with --iex-status; the SIP
              stock stream v2/sip is left to the trading engine, and an engine config with feed iex needs v2/iex);
              the screener (most actives by volume and by trades, top movers); option chain snapshots (implied
              volatility, greeks) for the top board candidates from 09:45 to 16:00 ET; open interest from the trading
              API's contracts endpoint once per root and day, only with --option-oi (an account no engine trades).
non-market    Alpaca/Benzinga news (websocket "*"); SEC EDGAR current filings (Atom, the declared contact in
              SEC_USER_AGENT, one request per form per sweep); Nasdaq Trader trade halts (RSS, at most once a
              minute), merged with the status stream into one halt state; the corporate-actions event stream
              (Server-Sent Events, every event archived, from the earliest the server still replays when the archive
              is empty); FINRA daily short sale volume files (once a day after publication, fetched once more after the
              next publication for an update).

Every source runs inside an explicit call budget that is written to monitor.jsonl; the data REST plan is refused
above 5% of the 10,000/min data limit. Every record carries the time the monitor received it, so the files form a
point-in-time dataset from the first day they are written. The boards are unvalidated detectors (no strategy has
been qualified on them): board.json keeps board version 1 (the frozen forward protocol's components and weights) and
board-v2.json adds the new sources' components. "early" marks names with incentive signals whose price has not yet
moved 10% from the reference close. This code is not the forward study's frozen code: it refuses to run beside that
study's bridge, and its own bridge refuses protocol v1 decisions (a new protocol version is needed to use it).
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
import pwd
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
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
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
# holds v2/iex only when asked (--iex-status), behind a host lease, backs off after a 406, and refuses the endpoint while
# a declared scheduled engine config streams feed iex (--engine-config).
IEX_WS = "wss://stream.data.alpaca.markets/v2/iex"
# "Subscribe to Corporate Actions Events (SSE)": the operation's own server is the stream host (the data host is 404).
CA_EVENTS = "https://stream.data.alpaca.markets/v1beta1/events/corporate-actions"
# An empty archive starts here, before the earliest event the server still replays (2026-07-09T09:00:05Z when probed on
# 2026-09-24 with this since value), so the whole retained history is archived once; retention itself is undocumented.
# Probed volume: about 12,000-54,000 events a day (almost all cash-dividend updates). --ca-archive-since bounds it.
CA_ARCHIVE_SINCE = "2020-01-01T00:00:00Z"
SCREENER_ACTIVES, SCREENER_MOVERS = "/v1beta1/screener/stocks/most-actives", "/v1beta1/screener/stocks/movers"
OPTION_CHAIN, OPTION_CONTRACTS = "/v1beta1/options/snapshots/{symbol}", "/v2/options/contracts"
# FINRA posts the consolidated NMS file no later than 18:00 ET on the trade date (off-exchange TRF/ADF volume only), and
# "in rare instances" updates a file on a subsequent day.
FINRA_SHORT_VOLUME = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day}.txt"
FINRA_HEADER = ["Date", "Symbol", "ShortVolume", "ShortExemptVolume", "TotalVolume", "Market"]
FINRA_AFTER_ET = dtime(18, 5)
FINRA_RETRY_SECONDS = 3600         # a missing, failed or invalid file is asked for again after an hour, never sooner
GENERIC_UA = {"User-Agent": "Mozilla/5.0 (compatible; incentive-monitor)"}  # the declared SEC contact goes to SEC only
DATA_LIMIT_PER_MIN, TRADING_LIMIT_PER_MIN = 10_000, 200  # X-Ratelimit-Limit of the data and paper trading APIs, measured
BUDGET_FRACTION = 0.05             # the monitor's REST plan may use at most 5% of either limit
RSS_MIN_SECONDS = 60.0             # Nasdaq Trader: at most one request per minute
CA_CONNECTS_PER_MIN = 2            # the events endpoint reports X-Ratelimit-Limit 20
CA_READ_TIMEOUT = 120
CA_CONTEXT_DEADLINE, CA_CONTEXT_READ_TIMEOUT = 90.0, 30.0   # the start-up context replay: whole replay, one read
RATELIMIT_FLOOR = 3500             # optional data sources pause while the data API reports fewer calls left
TRADING_RATELIMIT_FLOOR = 100      # open-interest calls pause while the trading API reports fewer calls left (of 200)
DATA_HOST, TRADING_HOST = "data.alpaca.markets", "paper-api.alpaca.markets"
ADV_ATTEMPTS, ADV_RETRY_WAIT = 3, 2.0   # daily-bar requests: attempts per request inside one load, first wait (doubling)
# Option chains are sampled while options trade with settled quotes; before 09:45 and after 16:00 ET quotes are stale.
CHAIN_SESSION_ET = (dtime(9, 45), dtime(16, 0))
IV_FRESH_SWEEPS = 2                # a root's latest implied volatility counts while it is at most two sweeps old
SOURCE_TIMEOUTS = {"option_chains": 10.0, "option_contracts": 10.0}   # seconds per read; other sources 20
# A stream connection counts as established (its reconnect backoff resets) after a data message or this long connected;
# the welcome and subscription batches alone never reset it. These error codes do not heal by reconnecting.
STREAM_STABLE_SECONDS = 60.0
STREAM_FATAL_CODES = {402, 405, 409, 410}   # auth failed, symbol limit, insufficient subscription, invalid action
BOARD_VERSION, BOARD_V2_VERSION = 1, 2
# Protocol incentive-board-forward-v1-20260924 bound these files (05c28491) in its decisions; this monitor refuses to run
# beside that bridge, so it can never become the study's monitor by being copied into the study's directory, and this
# bridge refuses protocol v1 decisions because its own code is not the frozen code (a new protocol version is needed).
FROZEN_V1 = {"monitor.py": "4c8029e5f8b96e65aa630923e36fd5ddfa51a1adfa18533113d3e6ce7642eaef",
             "board_scan.py": "0912f48b108ee680d71258ab7c63f47516fdd5dc658cdb69418f17d25fd1ff03"}
# The files a version 1 monitor writes per day that a follower reads instead of holding their connections.
V1_INPUTS = ("edgar", "news", "halts", "options-minute", "options-large")
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
# Board v2: fixed on 2026-09-24 without outcome data (unvalidated) and amended the same day, before any study used it.
# Board v1 components and weights are unchanged; halts keep v1's precedence (one news halt, else one volatility halt).
V2_WEIGHTS = {"stream_news_halt": 2.0, "stream_volatility_halt": 1.0, "corporate_action": 0.5, "iv_runup": 1.0,
              "short_volume_high": 0.5}
V2_RULES = {
    "stream_news_halt": "the status stream showed a halt today with a news reason (UTP T1 T2 T3 T12 H10 H11, CTA P D A C) "
                        "and the Nasdaq RSS shows no news halt for the name today; it replaces v1's volatility_halt, as "
                        "v1 ranks a news halt over a volatility halt (one halt component per name, never counted twice)",
    "stream_volatility_halt": "the status stream showed a volatility pause today (UTP LUDP LUDS T5 T7, CTA M), no news halt on "
                              "either source and no RSS halt of any kind today (price-triggered, not a non-price incentive)",
    "corporate_action": "a US-region split, merger, spin-off or name/symbol change whose ex, effective or process date is from "
                        "yesterday to 10 days ahead, or whose first insert event is from today (later updates keep it)",
    "iv_runup": "near-the-money implied volatility of the first expiry 7 to 42 days out, sampled from 09:45 to 16:00 ET with "
                "the latest sample at most two sweeps old, is up at least 20% on its baseline for the same expiry (the "
                "previous session's last value sampled by 16:00 ET, else the first value today from 09:45 ET), with the "
                "baseline at least 30 minutes old",
    "short_volume_high": "the latest FINRA consolidated short sale volume ratio is at least 0.80 on at least 200,000 shares "
                         "of reported off-exchange volume (volume-derived, not a non-price incentive)"}
IV_RUNUP_MIN, IV_BASELINE_MIN_AGE = 0.20, 1800
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
        self.rss_rows = {}   # (symbol, HaltDate, HaltTime) -> the events that RSS row added

    def _add_locked(self, symbol: str, event: dict) -> bool:
        key = (event["source"], event["kind"], event["at"])
        if any((e["source"], e["kind"], e["at"]) == key for e in self.events[symbol]):
            return False
        self.events[symbol].append(event)
        return True

    def _add(self, symbol: str, event: dict) -> bool:
        with self.lock:
            return self._add_locked(symbol, event)

    def stream_status(self, msg: dict, received: str | None) -> bool:
        state, at, symbol = status_state(msg), utc(msg.get("t")), msg.get("S")
        if state is None or at is None or not symbol:
            return False
        kind = STATE_KIND[state]
        return self._add(symbol, {"source": "stream", "kind": kind, "state": state, "at": iso(at), "reason": msg.get("rc"),
                                  "category": halt_category(msg.get("z"), msg.get("rc")) if kind == "halt" else None,
                                  "tape": msg.get("z"), "received_at": received})

    def rss_row(self, row: dict) -> int:
        """Merge one RSS row: its halt and scheduled resumptions. A later version of the same row (symbol, halt date and
        time) replaces the events of the earlier one that it no longer states, so a resumption moved later (an extended
        halt) is not kept at its earlier time. Returns the number of events added."""
        symbol, reason = row.get("IssueSymbol"), row.get("ReasonCode")
        if not symbol:
            return 0
        category, events = ("volatility" if reason in RSS_VOLATILITY_EXTRA else halt_category(None, reason)), []
        for kind, day_key, clock_key in (("halt", "HaltDate", "HaltTime"), ("quote", "ResumptionDate", "ResumptionQuoteTime"),
                                         ("trade", "ResumptionDate", "ResumptionTradeTime")):
            at = et_clock(row.get(day_key), row.get(clock_key))
            if at is None:
                continue
            state = ("paused" if category == "volatility" else "halted") if kind == "halt" else ("quotation_only" if kind == "quote" else "trading")
            events.append({"source": "rss", "kind": kind, "state": state, "at": iso(at), "reason": reason,
                           "category": category if kind == "halt" else None, "tape": None, "received_at": row.get("received_at")})
        same = lambda e: (e["kind"], e["at"], e["state"], e["reason"], e["category"])
        added = 0
        with self.lock:
            mine = self.rss_rows.setdefault((symbol, row.get("HaltDate"), row.get("HaltTime")), [])
            stated = {same(e) for e in events}
            dropped = [e for e in mine if same(e) not in stated]
            if dropped:
                self.events[symbol] = [e for e in self.events[symbol] if not any(e is d for d in dropped)]
                mine[:] = [e for e in mine if not any(e is d for d in dropped)]
            for event in events:
                if not any(same(e) == same(event) for e in mine) and self._add_locked(symbol, event):
                    mine.append(event)
                    added += 1
        return added

    def rss_ongoing(self, row: dict, today: date) -> bool:
        """An RSS row dated before today that still matters: not yet resumed (no resumption, or one from today on), or a
        row this book already holds (so its resumption is recorded when it arrives)."""
        key = (row.get("IssueSymbol"), row.get("HaltDate"), row.get("HaltTime"))
        resume = et_clock(row.get("ResumptionDate"), row.get("ResumptionTradeTime"))
        with self.lock:
            held = key in self.rss_rows
        return held or resume is None or resume.astimezone(ET).date() >= today

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
    """The latest version of every surfaced US corporate action by id (splits, mergers, spin-offs, name and symbol changes).

    ULID event ids sort in emission order, so an older version of an action, or one replayed after its deletion, is ignored.
    The time of an action's first insert event is kept across its later updates. Events whose envelope region is not us
    are archived by the stream but never surfaced (a non-US symbol can equal a US ticker)."""

    def __init__(self):
        self.actions, self.versions, self.inserted, self.lock = {}, {}, {}, threading.Lock()

    def observe(self, event: dict) -> bool:
        kind, ca, eid = str(event.get("event_type") or "").removesuffix(CA_SUFFIX), event.get("ca") or {}, event.get("event_id")
        if kind not in CA_TYPES or not isinstance(ca, dict) or not isinstance(ca.get("id"), str) or not ca["id"] or not isinstance(eid, str):
            return False
        if str(event.get("region") or "").lower() != "us":
            return False
        with self.lock:
            if event.get("action") == "insert" and isinstance(event.get("at"), str):
                first = self.inserted.get(ca["id"])
                self.inserted[ca["id"]] = event["at"] if first is None else min(first, event["at"], key=lambda t: utc(t) or datetime.max.replace(tzinfo=timezone.utc))
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
            items, inserted = list(self.actions.items()), dict(self.inserted)
        for ca_id, item in items:
            fields, date_field = CA_TYPES[item["type"]]
            when = item["ca"].get(date_field)
            try:
                days = (date.fromisoformat(when) - today).days if when else None
            except (TypeError, ValueError):
                days = None
            first = utc(inserted.get(ca_id))
            fresh = first is not None and first.astimezone(ET).date() == today
            in_window = fresh or (days is not None and CA_WINDOW_DAYS[0] <= days <= CA_WINDOW_DAYS[1])
            if not in_window and (days is None or not CA_CONTEXT_DAYS[0] <= days <= CA_CONTEXT_DAYS[1]):
                continue
            terms = {k: v for k, v in item["ca"].items() if k.endswith(("rate", "symbol"))}
            for field in fields:
                value = item["ca"].get(field)
                if isinstance(value, str) and value:   # a malformed payload never breaks the board
                    out[value].append({"type": item["type"], "role": field, "date": when, "days": days, "in_window": in_window,
                                       "action": item["action"], "at": item["at"], "inserted_at": inserted.get(ca_id), "terms": terms})
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


def chain_session_open(at: datetime) -> bool:
    """Option chains are sampled, and implied volatility is kept, only from 09:45 to 16:00 ET, when the quotes behind the
    implied volatility are live and the SIP price that picks the near-the-money strike is the regular session's."""
    clock = at.astimezone(ET).time()
    return CHAIN_SESSION_ET[0] <= clock < CHAIN_SESSION_ET[1]


class IVTracker:
    """Per-symbol near-the-money implied volatility sampled from 09:45 to 16:00 ET: the first value today for the current
    expiry, the latest, and the previous session's last value (from the previous day's file). The change is measured on
    the same expiry only: against the previous session, else against the first value today. A latest sample older than
    ``max_age`` seconds (two sweeps) no longer counts, so a root that left the sampled set loses its change."""

    def __init__(self, max_age: float = IV_FRESH_SWEEPS * 20.0):
        self.first, self.last, self.prev, self.max_age = {}, {}, {}, max_age

    def observe(self, symbol: str, at: datetime, summary: dict) -> None:
        if not valid_iv(summary.get("atm_iv")) or not chain_session_open(at):
            return
        rec = {"at": iso(at), "iv": summary["atm_iv"], "expiry": summary.get("expiry")}
        first = self.first.get(symbol)
        if first is None or first.get("expiry") != rec["expiry"]:
            self.first[symbol] = rec   # the first value today, reset when the target expiry changes
        self.last[symbol] = rec

    def change(self, symbol: str, at: datetime) -> dict | None:
        cur = self.last.get(symbol)
        if cur is None or (at - utc(cur["at"])).total_seconds() > self.max_age:
            return None
        prev, first = self.prev.get(symbol), self.first.get(symbol)
        if prev and prev.get("expiry") == cur["expiry"] and valid_iv(prev.get("iv")) and utc(prev.get("at")) is not None:
            base, kind = prev, "previous_session"
        elif first and first.get("expiry") == cur["expiry"]:
            base, kind = first, "first_today"
        else:
            return None
        return {"iv": cur["iv"], "expiry": cur["expiry"], "last_at": cur["at"], "baseline_iv": base["iv"], "baseline": kind,
                "baseline_at": base["at"], "baseline_age_s": round((at - utc(base["at"])).total_seconds()),
                "chg": round(cur["iv"] / base["iv"] - 1, 4)}

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
    """Explicit call caps per source: per sweep for polled sources, per rolling minute for the daily-bar load (retries and
    resumed attempts included), per process for start-up loads. A source without a cap is refused (fail closed). The
    caps, the calls and the refusals are written to monitor.jsonl."""

    def __init__(self, per_sweep: dict | None = None, once: dict | None = None, per_minute: dict | None = None, clock=time.monotonic):
        self.per_sweep, self.once, self.per_minute = dict(per_sweep or {}), dict(once or {}), dict(per_minute or {})
        self.used, self.used_once, self.refused = defaultdict(int), defaultdict(int), defaultdict(int)
        self.recent, self.clock, self.lock = defaultdict(deque), clock, threading.Lock()

    def configure(self, per_sweep: dict, once: dict, per_minute: dict | None = None) -> None:
        with self.lock:
            self.per_sweep.update(per_sweep)
            self.once.update(once)
            self.per_minute.update(per_minute or {})

    def start_sweep(self) -> None:
        with self.lock:
            self.used.clear()

    def take(self, source: str) -> bool:
        with self.lock:
            if source in self.per_minute:
                now, recent = self.clock(), self.recent[source]
                while recent and now - recent[0] >= 60:
                    recent.popleft()
                if len(recent) >= self.per_minute[source]:
                    self.refused[source] += 1
                    return False
                recent.append(now)
                return True
            used, cap = (self.used, self.per_sweep[source]) if source in self.per_sweep else (self.used_once, self.once.get(source, 0))
            if used[source] >= cap:
                self.refused[source] += 1
                return False
            used[source] += 1
            return True


def plan_budget(symbols: int, a) -> dict:
    """The per-source call plan for a universe of ``symbols`` names. ``refusals`` names every rule the plan breaks: data
    REST calls above 5% of the 10,000/min data limit in any minute (the steady rate plus one full daily-bar pass, which
    the daily-bar load's per-minute cap enforces however often it is resumed), trading REST calls above 5% of the 200/min
    trading limit, or the Nasdaq RSS polled more than once a minute. A follower of a version 1 monitor (--follow-v1) has
    no EDGAR, Nasdaq RSS or SEC file budget and no news or OPRA connection: it reads those inputs from version 1's files."""
    refusals = []
    if (a.sweep_seconds <= 0 or a.edgar_seconds <= 0 or a.rss_seconds <= 0 or a.option_roots < 0 or a.option_pages < 1
            or a.option_retries < 0 or a.oi_per_sweep < 0 or not 0 < a.option_strike_band < 1 or a.option_min_dte < 0
            or a.option_window_days < 0 or a.iex_conflict_wait < 0 or a.ca_context_days < 0):
        return {"symbols": symbols, "refusals": ["invalid_bounds"]}
    follower = getattr(a, "follow_v1", None) is not None
    sweeps_per_min = 60.0 / a.sweep_seconds
    chunks, adv = math.ceil(symbols / 500), math.ceil(symbols / 200)
    per_sweep = {"snapshots": chunks, "screener": 3 if a.screener else 0,
                 "option_chains": (a.option_roots + a.option_retries) * a.option_pages if a.option_chains else 0,
                 "option_contracts": a.oi_per_sweep if a.option_oi else 0,
                 "edgar": 0 if follower else len(EDGAR_FORMS), "nasdaq_halts": 0 if follower else 1, "finra": 1 if a.finra else 0}
    once = {"assets": 5, "sec_files": 0 if follower else 5}   # start-up loads, retries included
    per_minute = {"adv_bars": adv}                              # one daily-bar pass in any minute, retries included
    data_per_min = (per_sweep["snapshots"] + per_sweep["screener"] + per_sweep["option_chains"]) * sweeps_per_min
    trading_per_min = per_sweep["option_contracts"] * sweeps_per_min + 1   # plus the start-up assets load
    caps = {"data": DATA_LIMIT_PER_MIN * BUDGET_FRACTION, "trading": TRADING_LIMIT_PER_MIN * BUDGET_FRACTION}
    if data_per_min + per_minute["adv_bars"] > caps["data"]:
        refusals.append("data_calls_above_5pct_of_limit")
    if trading_per_min > caps["trading"]:
        refusals.append("trading_calls_above_5pct_of_limit")
    if a.rss_seconds < RSS_MIN_SECONDS:
        refusals.append("nasdaq_rss_more_than_once_per_minute")
    return {"symbols": symbols, "sweep_seconds": a.sweep_seconds, "sweeps_per_min": round(sweeps_per_min, 3), "per_sweep": per_sweep,
            "once": once, "per_minute": per_minute, "data_per_min": round(data_per_min, 1),
            "data_first_min": round(data_per_min + per_minute["adv_bars"], 1),
            "data_cap_per_min": caps["data"], "trading_per_min": round(trading_per_min, 1), "trading_cap_per_min": caps["trading"],
            "sec_per_min": 0.0 if follower else round(len(EDGAR_FORMS) * min(sweeps_per_min, 60.0 / a.edgar_seconds), 1),
            "nasdaq_per_min": 0.0 if follower else round(min(sweeps_per_min, 60.0 / a.rss_seconds), 2), "finra_per_sweep": per_sweep["finra"],
            "follow_v1": str(a.follow_v1) if follower else None,
            "streams": {"news": {"connections": 0 if follower else 1}, "opra": {"connections": 0 if follower else 1},
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
    """One fixed directory per user, from the password database (not XDG_RUNTIME_DIR or HOME), so monitors started by cron,
    systemd or a shell all see the same leases."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".cache" / "alpaca-stream-leases"


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
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=SOURCE_TIMEOUTS.get(source, timeout)) as r:
            limit = r.headers.get("X-Ratelimit-Limit")
            if limit is not None:
                with self.lock:
                    self.ratelimit[urllib.parse.urlsplit(url).hostname] = {
                        "limit": limit, "remaining": r.headers.get("X-Ratelimit-Remaining"), "reset": r.headers.get("X-Ratelimit-Reset")}
            return r.read()

    def remaining(self, host: str) -> int | None:
        """The calls left in the host's rate-limit window, from its last response (None before any)."""
        with self.lock:
            value = (self.ratelimit.get(host) or {}).get("remaining")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def data_remaining(self) -> int | None:
        return self.remaining(DATA_HOST)

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
        self.short_volume_day, self.no_options, self.finra_failed = None, set(), {}
        self.chain_unbanded = set()                                # roots whose in-band chain was empty today
        self.iex_tapes = defaultdict(int)                          # message type and tape -> count, to measure tape coverage
        self.restored_v2 = {}


def apply_v1_row(state: State, name: str, row: dict, counts, haltbook: bool = False) -> None:
    """Apply one row of a version 1 input file (edgar, news, halts, options-minute, options-large) to the session state,
    as the monitor that wrote it did: filings once per accession, news once per article at its receive time, today's RSS
    halts (and, with ``haltbook``, the merged halt state), option totals and large prints."""
    if name == "edgar":
        key = (row.get("accession"), row.get("cik"))
        if key not in state.seen_accessions:
            state.seen_accessions.add(key)
            attach_filing(state, row)
            counts["edgar"] += 1
    elif name == "news":
        received = datetime.fromisoformat(row["received_at"]).timestamp() if row.get("received_at") else None
        for symbol in row.get("symbols") or []:
            if received is not None and row.get("id") is not None:
                state.news[symbol].setdefault(row["id"], received)
        counts["news"] += 1
    elif name == "halts":
        if row.get("HaltDate") == state.today.strftime("%m/%d/%Y") and row.get("IssueSymbol"):
            key = (row["IssueSymbol"], row.get("HaltDate"), row.get("HaltTime"))
            if key not in state.halt_rows:
                state.halts[row["IssueSymbol"]].append(row)
            state.halt_rows[key] = {k: v for k, v in row.items() if k != "received_at"}
            counts["halts"] += 1
            if haltbook:
                counts["rss_events"] += state.haltbook.rss_row(row)
    elif name == "options-minute":
        totals = state.options.day[row["root"]]
        for cell, (volume, premium, _trades) in row.get("cells", {}).items():
            right, bucket = cell.split("|")
            totals[f"{right}_volume"] += volume
            totals[f"{right}_premium"] += premium
            if bucket == "0-7":
                totals[f"{right}_premium_0_7"] += premium
        counts["options_minutes"] += 1
    elif name == "options-large":
        state.options.day[row["root"]]["large_prints"] += 1
        counts["options_large"] += 1


def restore(state: State, day_dir: Path) -> dict:
    """Rebuild this session's filings, news window and option totals from today's files after a restart."""
    counts = defaultdict(int)
    for name in V1_INPUTS:
        for row in jsonl(day_dir / f"{name}.jsonl", counts):
            apply_v1_row(state, name, row, counts)
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
    and the previous session's implied volatility, and today's open interest. The previous session's baseline is each
    root's last sample taken from 09:45 to 16:00 ET (an after-hours sample has stale option quotes)."""
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
        received = utc(row.get("received_at"))
        if not (row.get("symbol") and valid_iv(row.get("atm_iv")) and received is not None):
            continue
        if not chain_session_open(received):
            counts["options_iv_previous_outside_session"] += 1
            continue
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


def reverse_lines(path: Path, block: int = 1 << 16):
    """A file's non-empty lines from the last to the first (bytes, without line ends), read from the end in blocks."""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        pos, tail = f.tell(), b""
        while pos > 0:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            parts = (f.read(step) + tail).split(b"\n")
            tail = parts[0]
            for line in reversed(parts[1:]):
                if line.strip():
                    yield line
        if tail.strip():
            yield tail


def last_archived_event_id(root: Path) -> str | None:
    """The newest event id of the most recent corporate-actions archive (the stream's resume point). The archive appends an
    event id only when it is newer than the last archived one, so the last valid id is the newest; it is read from the
    end of the file, which can hold the whole retained history (millions of events)."""
    for folder in reversed(day_dirs(root)):
        path = folder / "corporate-actions.jsonl"
        if not path.exists():
            continue
        for line in reverse_lines(path):
            try:
                eid = json.loads(line).get("event_id")
            except (ValueError, AttributeError):
                continue
            if isinstance(eid, str) and EVENT_ID.match(eid):
                return eid
    return None


class FollowV1:
    """The follower's inputs from a running version 1 monitor (``root`` is its --out directory): each poll applies the
    complete lines appended to today's edgar, news, halts, options-minute and options-large files since the last poll,
    so the follower needs no news or OPRA connection and polls neither EDGAR nor the Nasdaq RSS. Nothing is written to
    version 1's directory."""

    def __init__(self, root: Path, today: date):
        self.root, self.day = root, today.strftime("%Y%m%d")
        self.offsets, self.counts = {}, defaultdict(int)

    def poll(self, state: State) -> dict:
        folder = self.root / self.day
        for name in V1_INPUTS:
            path = folder / f"{name}.jsonl"
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                continue
            offset = self.offsets.get(name, 0)
            if size < offset:   # version 1 appends only; a shorter file is another file, never read twice
                self.counts[f"{name}_shrunk"] += 1
                self.offsets[name] = size
                continue
            with path.open("rb") as f:
                f.seek(offset)
                for raw in f:
                    if not raw.endswith(b"\n"):
                        break   # a line still being written is read at the next poll
                    offset += len(raw)
                    try:
                        row = json.loads(raw)
                        apply_v1_row(state, name, row, self.counts, haltbook=True)
                    except (ValueError, KeyError, TypeError, AttributeError):
                        self.counts[f"{name}_unreadable"] += 1
            self.offsets[name] = offset
        return dict(self.counts)

    def heartbeat(self, now: datetime) -> dict:
        """The version 1 monitor's last monitor.jsonl record today: its event and age in seconds (None when absent)."""
        path = self.root / self.day / "monitor.jsonl"
        if path.exists():
            for line in reverse_lines(path):
                try:
                    row = json.loads(line)
                    at = utc(row.get("at"))
                except (ValueError, AttributeError):
                    continue
                if at is not None:
                    return {"event": row.get("event"), "age_s": round((now - at).total_seconds(), 1)}
        return {"event": None, "age_s": None}


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


class AdvLoader:
    """Twenty-session average daily volume from SIP daily bars, 200 symbols a request. Each request is tried up to
    ADV_ATTEMPTS times inside one attempt; a request that still fails ends the attempt where it stopped, and the next
    attempt resumes from that chunk and page, so finished requests are never repeated. Every call, retries included,
    stays inside the daily-bar source's per-minute cap (a refusal ends the attempt at once, without waiting)."""

    def __init__(self, symbols: list[str], today: date, attempts: int = ADV_ATTEMPTS, first_wait: float = ADV_RETRY_WAIT, sleep=time.sleep):
        self.symbols, self.today, self.attempts, self.first_wait, self.sleep = symbols, today, attempts, first_wait, sleep
        self.index, self.token, self.volumes, self.failures = 0, None, defaultdict(list), 0

    def run(self, http: Http) -> dict:
        while self.index < len(self.symbols):
            params = {"symbols": ",".join(self.symbols[self.index:self.index + 200]), "timeframe": "1Day",
                      "start": (self.today - timedelta(days=35)).isoformat(), "end": (self.today - timedelta(days=1)).isoformat(),
                      "feed": "sip", "adjustment": "split", "limit": 10000, **({"page_token": self.token} if self.token else {})}
            for attempt in range(self.attempts):
                try:
                    body = http.alpaca_json(DATA, "/v2/stocks/bars", params)
                    break
                except BudgetExceeded:
                    raise
                except Exception:
                    self.failures += 1
                    if attempt == self.attempts - 1:
                        raise
                    self.sleep(self.first_wait * 2 ** attempt)
            for symbol, bars in (body.get("bars") or {}).items():
                self.volumes[symbol].extend(b["v"] for b in bars)
            self.token = body.get("next_page_token")
            if not self.token:
                self.index += 200
        return {s: sum(v[-20:]) / len(v[-20:]) for s, v in self.volumes.items() if v}


def load_adv(http: Http, symbols: list[str], today: date) -> dict:
    return AdvLoader(symbols, today).run(http)


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
    """Today's RSS halt rows (v1: the halt list, halts.jsonl, the change count) and the merged halt state (v2), which also
    takes an earlier day's row while that halt is still in force, since the status stream sends no snapshot."""
    changed = 0
    # A generic agent here: the declared SEC contact is sent to SEC only.
    for row in parse_halts(http.get(HALTS_RSS, "nasdaq", {"User-Agent": "Mozilla/5.0 (compatible; incentive-monitor)"}), now_utc()):
        if row.get("HaltDate") != state.today.strftime("%m/%d/%Y"):
            if state.haltbook.rss_ongoing(row, state.today):
                state.haltbook.rss_row(row)   # a multi-day halt: merged state only; the v1 rows stay today's
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


def score_rows(state: State, at: datetime, extra=frozenset()) -> tuple[dict, set]:
    """(rows, v1_candidates): board v1 rows (``score`` unchanged) for every v1 candidate and any ``extra`` symbols, keyed
    by symbol, all scored in one pass over one state, and the set of v1 candidates among them."""
    fraction = session_fraction(at)
    horizon = at.timestamp() - 1800
    options = {}
    for root, totals in list(state.options.day.items()):
        symbol = root_symbol(root, state.universe) if state.universe else root
        if symbol:
            merged = options.setdefault(symbol, defaultdict(float))
            for key, value in list(totals.items()):
                merged[key] += value
    candidates = set(state.filings) | set(state.halts) | set(state.news) | set(options)
    candidates |= {s for s, f in state.features.items() if f["chg"] is not None and abs(f["chg"]) >= 0.05}
    rows = {}
    for symbol in candidates | set(extra):
        feat = state.features.get(symbol)
        adv = state.adv.get(symbol)
        relvol = (feat["v"] / (adv * fraction)) if (feat and feat.get("v") and adv and fraction) else None
        articles = state.news.get(symbol) or {}
        for article in [a for a, received in list(articles.items()) if received < horizon]:
            del articles[article]
        rows[symbol] = score(symbol, feat, relvol, len(articles), state.filings.get(symbol, []), state.halts.get(symbol, []), options.get(symbol))
    return rows, candidates


def score_candidates(state: State, at: datetime, extra=frozenset()) -> dict:
    """Board v1 rows (``score`` unchanged) for every v1 candidate and any ``extra`` symbols, keyed by symbol."""
    return score_rows(state, at, extra)[0]


def build_board(state: State, at: datetime, top: int = 100, rows: dict | None = None) -> tuple[list[dict], list[str]]:
    """(board, incentive_symbols) of board version 1: rows scoring at least 2, and every symbol with any component other
    than relvol. ``rows`` may carry this sweep's score_candidates result."""
    rows = score_candidates(state, at) if rows is None else rows
    incentive = sorted(s for s, row in rows.items() if set(row["parts"]) & NON_PRICE_PARTS)
    board = sorted((row for row in rows.values() if row["score"] >= 2), key=lambda r: (-r["score"], r["symbol"]))
    return board[:top], incentive


# Board v2 non-price components: v1's plus a stream news halt, a corporate action and an implied-volatility run-up.
NON_PRICE_PARTS_V2 = NON_PRICE_PARTS | {"stream_news_halt", "corporate_action", "iv_runup"}


def v2_components(state: State, symbol: str, row: dict, at: datetime, actions: dict) -> tuple[dict, dict, set]:
    """(parts, context, superseded) that board v2 adds to a v1 row; the rules are V2_RULES and the weights V2_WEIGHTS.
    ``superseded`` names the v1 parts that board v2 drops: v1's volatility_halt when the stream adds a news halt, since
    v1 counts one halt component per name (news over volatility)."""
    parts, context, superseded, v1 = {}, {}, set(), row["parts"]
    halt = state.haltbook.state(symbol, at)
    if halt:
        context["halt"] = halt
    band = state.haltbook.band(symbol, row.get("price"))
    if band:
        context["luld"] = band
    category = state.haltbook.stream_category(symbol)
    if category == "news" and "news_halt" not in v1:
        parts["stream_news_halt"] = V2_WEIGHTS["stream_news_halt"]
        superseded |= {"volatility_halt"} & set(v1)
    elif category == "volatility" and "news_halt" not in v1 and not state.halts.get(symbol):   # no RSS halt of any kind today
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
    if superseded:
        context["superseded_v1_parts"] = sorted(superseded)
    return parts, context, superseded


def v2_symbols(state: State, at: datetime, actions: dict) -> set:
    """Symbols that only the v2 sources make candidates (limited to the tradable universe once it is loaded)."""
    found = state.haltbook.symbols("stream") | {s for s, items in actions.items() if any(i["in_window"] for i in items)}
    found |= {s for s in list(state.iv.last) if state.iv.runup(s, at)}
    found |= {s for s, row in state.short_volume.items() if short_volume_high(row)}
    return found & state.universe if state.universe else found


def v2_scoring_extra(state: State, at: datetime, actions: dict) -> set:
    """The symbols to score with the v1 rows, besides the v1 candidates, so board v2 needs no second scoring pass: every
    current v2 candidate and every root with an implied-volatility sample (whose run-up this sweep's chains may reveal)."""
    extra = v2_symbols(state, at, actions) | set(state.iv.last)
    return extra & state.universe if state.universe else extra


def build_board_v2(state: State, at: datetime, top: int = 100, rows: dict | None = None, v1: set | None = None,
                   actions: dict | None = None) -> tuple[list[dict], list[str]]:
    """(board, incentive_symbols) of board version 2: every v1 part and weight unchanged (``score_v1`` keeps the v1 score),
    plus the v2 parts; the same threshold of 2. Unvalidated: a detector to be tested prospectively. ``rows`` and ``v1``
    are this sweep's single scoring pass (score_rows), so each row's v1 parts and score_v1 are exactly board.json's; a
    v2 candidate that pass did not score waits for the next sweep."""
    actions = state.ca.by_symbol(state.today) if actions is None else actions
    if rows is None:
        rows, v1 = score_rows(state, at, v2_symbols(state, at, actions))
    wanted = set(v1 if v1 is not None else rows) | (v2_symbols(state, at, actions) & set(rows))
    board, incentive = [], []
    for symbol in sorted(wanted):
        row = rows[symbol]
        parts, context, superseded = v2_components(state, symbol, row, at, actions)
        merged = {**{k: v for k, v in row["parts"].items() if k not in superseded}, **parts}
        out = {**row, "score": round(sum(merged.values()), 3), "score_v1": row["score"], "parts": merged}
        if context:
            out["context"] = context
        if set(merged) & NON_PRICE_PARTS_V2:
            incentive.append(symbol)
        if out["score"] >= 2:
            board.append(out)
    board.sort(key=lambda r: (-r["score"], r["symbol"]))
    return board[:top], sorted(incentive)


def board_v1_payload(at: datetime, board: list, incentive: list, monitor: dict) -> dict:
    """board.json: board version 1, the frozen forward protocol's."""
    return {"at": at.isoformat(timespec="seconds"), "board_version": BOARD_VERSION, "evidence_class": "unvalidated_detector",
            "board": board, "incentive_symbols": incentive, "monitor": monitor}


def board_v2_payload(at: datetime, board_v2: list, incentive_v2: list, monitor: dict) -> dict:
    """board-v2.json: board version 2 with its weights and rules."""
    return {"at": at.isoformat(timespec="seconds"), "board_version": BOARD_V2_VERSION, "evidence_class": "unvalidated_detector",
            "weights_v2": V2_WEIGHTS, "rules_v2": V2_RULES, "board": board_v2, "incentive_symbols": incentive_v2, "monitor": monitor}


def board_payloads(at: datetime, board: list, incentive: list, board_v2: list, incentive_v2: list, monitor: dict) -> tuple[dict, dict]:
    """(board.json, board-v2.json): board version 1 (the frozen forward protocol's) and board version 2."""
    return board_v1_payload(at, board, incentive, monitor), board_v2_payload(at, board_v2, incentive_v2, monitor)


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


def chain_params(price: float | None, today: date, a, banded: bool = True) -> dict:
    """The chain's expiry window, from option_min_dte days out for option_window_days more (35 by default, so the window
    always holds a standard monthly expiry: third Fridays are 28 or 35 days apart), and the strike band around the price
    unless ``banded`` is false."""
    first = today + timedelta(days=a.option_min_dte)
    params = {"expiration_date_gte": first.isoformat(), "expiration_date_lte": (first + timedelta(days=a.option_window_days)).isoformat()}
    if price and banded:
        params.update({"strike_price_gte": round(price * (1 - a.option_strike_band), 2), "strike_price_lte": round(price * (1 + a.option_strike_band), 2)})
    return params


def fetch_chain(http: Http, symbol: str, price: float | None, today: date, a, banded: bool = True) -> tuple[dict, bool, int]:
    """(snapshots, truncated, pages): the chain inside the expiry window (and the strike band when ``banded``), at most
    option_pages pages of 1,000 contracts. Pages are expected in contract-symbol order (root, expiry, right, strike), so a
    truncated first page still starts at the first expiry; ``truncated`` marks it."""
    params = {"feed": "opra", "limit": 1000, **chain_params(price, today, a, banded)}
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


def poll_option_chains(http: Http, state: State, sink: Sink, a, targets: list[str], deadline_s: float | None = None) -> dict:
    """Chain snapshots for the targets (four at a time); each root's near-the-money summary goes to options-iv.jsonl.

    An empty answer inside the strike band (a mover beyond its listed strikes, or wide strike spacing) is asked again
    once without the band, at most option_retries roots a sweep, and that root then goes without the band for the day.
    A root is marked as having no options only for a 4xx answer (not 429) or an empty answer without the band. Roots not
    answered within ``deadline_s`` seconds are left for the next sweep, so a stalled endpoint cannot hold the sweep."""
    stats, retries = defaultdict(int), [a.option_retries]
    lock = threading.Lock()

    def one(symbol):
        price = (state.features.get(symbol) or {}).get("p")
        banded = bool(price) and symbol not in state.chain_unbanded
        snapshots, truncated, pages = fetch_chain(http, symbol, price, state.today, a, banded)
        if not snapshots and banded:
            with lock:
                allowed = retries[0] > 0
                retries[0] -= allowed
            if not allowed:
                return None, False, pages, now_utc(), "retry_deferred"
            snapshots, truncated, more = fetch_chain(http, symbol, price, state.today, a, banded=False)
            pages += more
            if snapshots:
                state.chain_unbanded.add(symbol)
            return snapshots, truncated, pages, now_utc(), "unbanded_retry"
        return snapshots, truncated, pages, now_utc(), None
    pool = ThreadPoolExecutor(max_workers=4)
    try:
        futures = [(symbol, pool.submit(one, symbol)) for symbol in targets]
        done, _ = futures_wait([f for _, f in futures], timeout=deadline_s)
        for symbol, future in futures:
            if future not in done:
                stats["deadline"] += 1
                continue
            try:
                snapshots, truncated, pages, received, note = future.result()
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
            if note:
                stats[note] += 1
            if snapshots is None:
                continue   # the in-band answer was empty and this sweep's retries are used up: asked again next sweep
            if not snapshots:
                state.no_options.add(symbol)   # nothing listed in the expiry window, whatever the strike
                stats["empty"] += 1
                continue
            price = (state.features.get(symbol) or {}).get("p")
            summary = chain_summary(symbol, snapshots, price, state.today, (state.oi.get(symbol) or {}).get("by_contract"))
            state.iv.observe(symbol, utc(received), summary)
            sink.write("options-iv", {"received_at": received, "symbol": symbol, "price": price, "pages": pages, "truncated": truncated,
                                      "banded": symbol not in state.chain_unbanded, **summary})
            stats["roots"] += 1
    finally:
        pool.shutdown(wait=False, cancel_futures=True)   # roots past the deadline are not waited for
    return dict(stats)


def poll_option_oi(http: Http, state: State, sink: Sink, a, targets: list[str]) -> int:
    """Open interest (the contracts endpoint, trading API) for targets not yet fetched today, oi_per_sweep at most. The
    calls pause while the trading API reports fewer than TRADING_RATELIMIT_FLOOR calls left in its window, since an engine
    on the same account shares that limit."""
    fetched = 0
    for symbol in [s for s in targets if s not in state.oi][:a.oi_per_sweep]:
        remaining = http.remaining(TRADING_HOST)
        if remaining is not None and remaining < TRADING_RATELIMIT_FLOOR:
            break
        params = {"underlying_symbols": symbol, "status": "active", "limit": 10000,
                  **chain_params((state.features.get(symbol) or {}).get("p"), state.today, a, banded=symbol not in state.chain_unbanded)}
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


def finra_fetch(http: Http, state: State, stamp: str, clock) -> tuple[str, bytes, dict]:
    """(url, payload, rows) of one FINRA file, parsed and date-checked. Every failure except a budget refusal (a missing
    file, a server or network error, a malformed, partial or misdated file) marks the day for a retry no sooner than
    FINRA_RETRY_SECONDS later, and is raised."""
    url = FINRA_SHORT_VOLUME.format(day=stamp)
    try:
        payload = http.get(url, "finra", GENERIC_UA)
        parsed_day, rows = parse_finra(payload)   # a malformed or partial file raises and nothing is stored
        if parsed_day != stamp:
            raise ValueError("finra_date_mismatch")
    except BudgetExceeded:
        raise
    except Exception:
        state.finra_failed[stamp] = clock()
        raise
    return url, payload, rows


def store_finra(sink: Sink, stamp: str, url: str, payload: bytes, rows: dict, received: str, **extra) -> None:
    sink.replace(f"finra/CNMSshvol{stamp}.txt", payload, shared=True)
    sink.replace(f"finra/CNMSshvol{stamp}.json", json.dumps({"url": url, "date": stamp, "received_at": received, "rows": len(rows),
                                                              "sha256": hashlib.sha256(payload).hexdigest(), **extra}).encode(), shared=True)


def poll_finra(http: Http, state: State, sink: Sink, now: datetime, clock=time.time) -> str | None:
    """At most one request per sweep. First the newest due FINRA file not yet stored: a file that is missing (a holiday,
    or not posted yet) or that failed (server or network error, malformed or partial) is asked for again an hour later at
    the earliest, while earlier weekdays are tried. Then, once every due file is stored, each stored file is fetched once
    more after the first publication time that follows its receipt, since FINRA may update a file on a subsequent day; a
    changed file replaces the stored one, and the earlier version stays under finra/superseded/."""
    due = finra_due(now)
    days, folder = weekdays_back(due, 5), sink.root / "finra"
    waiting = lambda stamp: clock() - state.finra_failed.get(stamp, -math.inf) < FINRA_RETRY_SECONDS
    for day in days:
        stamp = day.strftime("%Y%m%d")
        if (folder / f"CNMSshvol{stamp}.txt").exists():
            if state.short_volume_day != stamp:
                state.short_volume_day, state.short_volume = load_short_volume(sink.root, due)
            break
        if waiting(stamp):
            continue
        try:
            url, payload, rows = finra_fetch(http, state, stamp, clock)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):  # the file store answers a missing key with 403
                return f"missing:{stamp}"
            raise
        store_finra(sink, stamp, url, payload, rows, now_utc())
        state.short_volume_day, state.short_volume = load_short_volume(sink.root, due)
        return stamp
    for day in days:   # the update check: one request per stored file, after the next publication following its receipt
        stamp = day.strftime("%Y%m%d")
        try:
            manifest = json.loads((folder / f"CNMSshvol{stamp}.json").read_text())
            received = utc(manifest.get("received_at"))
        except (OSError, ValueError, AttributeError):
            continue
        if manifest.get("rechecked_at") or received is None or due <= received.astimezone(ET).date() or waiting(stamp):
            continue
        try:
            url, payload, rows = finra_fetch(http, state, stamp, clock)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                sink.replace(f"finra/CNMSshvol{stamp}.json", json.dumps({**manifest, "rechecked_at": now_utc(), "recheck": "missing"}).encode(), shared=True)
                return f"recheck_missing:{stamp}"
            raise
        checked, digest = now_utc(), hashlib.sha256(payload).hexdigest()
        if digest == manifest.get("sha256"):
            sink.replace(f"finra/CNMSshvol{stamp}.json", json.dumps({**manifest, "rechecked_at": checked, "recheck": "unchanged"}).encode(), shared=True)
            return f"unchanged:{stamp}"
        old = str(manifest.get("sha256") or "unknown")[:12]
        sink.replace(f"finra/superseded/CNMSshvol{stamp}.{old}.txt", (folder / f"CNMSshvol{stamp}.txt").read_bytes(), shared=True)
        sink.replace(f"finra/superseded/CNMSshvol{stamp}.{old}.json", json.dumps(manifest).encode(), shared=True)
        store_finra(sink, stamp, url, payload, rows, checked, rechecked_at=checked, recheck="updated", supersedes=manifest.get("sha256"))
        state.short_volume_day, state.short_volume = load_short_volume(sink.root, due)
        return f"updated:{stamp}"
    return None


# ---------------------------------------------------------------- streams

class StreamError(ConnectionError):
    """An error message from a stream endpoint, with its code (406: connection limit exceeded)."""

    def __init__(self, name: str, code):
        super().__init__(f"{name}:{code}")
        self.code = code


async def stream(name: str, url: str, subscribe: dict, headers: dict, on_message, state: State, sink: Sink, stop: asyncio.Event, packed: bool,
                 conflict_wait: float | None = None, backoff=None, stable_seconds: float = STREAM_STABLE_SECONDS):
    """Hold one stream with bounded reconnects. The backoff grows with each failed attempt and resets only once the
    connection is established (a data message, or ``stable_seconds`` connected): the welcome and subscription batches
    that precede a 406 never reset it. With ``conflict_wait``, a 406 (another holder of the endpoint) waits that long
    before the next attempt instead of contending. An error that reconnecting cannot heal (STREAM_FATAL_CODES, e.g. 409
    insufficient subscription) stops the stream for the rest of the run."""
    import msgpack
    import websockets
    backoff = backoff or (lambda attempt: min(60, 2 ** attempt))
    attempt = 0
    while not stop.is_set():
        try:
            async with websockets.connect(url, additional_headers=({**headers, "Content-Type": "application/msgpack"} if packed else headers),
                                          max_size=None, ping_interval=20) as ws:
                await ws.send(msgpack.packb(subscribe) if packed else json.dumps(subscribe))
                if name in state.down_since:
                    state.down_seconds[name] += time.time() - state.down_since.pop(name)
                sink.write("monitor", {"event": "stream_connected", "stream": name, "at": now_utc()})
                connected = time.monotonic()
                while not stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        raw = None
                    delivered = False
                    for msg in ((msgpack.unpackb(raw, timestamp=3) if packed else json.loads(raw)) if raw is not None else ()):
                        kind = msg.get("T")
                        if kind == "error":
                            sink.write("monitor", {"event": "stream_error", "stream": name, "code": msg.get("code"), "msg": msg.get("msg"), "at": now_utc()})
                            raise StreamError(name, msg.get("code"))
                        if kind in ("success", "subscription"):
                            continue
                        state.stream_counts[f"{name}:{kind}"] += 1
                        on_message(msg)
                        delivered = True
                    if delivered or time.monotonic() - connected >= stable_seconds:
                        attempt = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # reconnect with bounded backoff; every disconnect is recorded
            attempt += 1
            state.down_since.setdefault(name, time.time())
            code = getattr(exc, "code", None)
            if code in STREAM_FATAL_CODES:
                sink.write("monitor", {"event": "stream_stopped", "stream": name, "code": code, "attempt": attempt, "at": now_utc()})
                return
            conflict = conflict_wait is not None and code == 406
            sink.write("monitor", {"event": "stream_conflict" if conflict else "stream_down", "stream": name,
                                   "error": f"{type(exc).__name__}: {str(exc)[:200]}", "attempt": attempt, "at": now_utc()})
            try:
                await asyncio.wait_for(stop.wait(), timeout=conflict_wait if conflict else backoff(attempt))
            except asyncio.TimeoutError:
                pass


class EventStream:
    """The corporate-actions event stream (Server-Sent Events). Every event (every type and region) is archived to
    corporate-actions.jsonl with its receive time and fed to the corporate-action context; ids are deduplicated (a resume
    redelivers the last id); the stream resumes with Last-Event-Id from the last archived id whatever its age, or starts
    at ``start`` when nothing is archived; connects, the context replay's included, stay within a per-minute budget.

    Last-Event-Id is inclusive, so a resume's first event is the resume id itself while the server still holds it; a
    first event newer than the resume id is recorded as ca_resume_gap (the events between may be lost)."""

    def __init__(self, headers: dict, sink: Sink, state: State, start: datetime, last_id: str | None = None, opener=None,
                 connects_per_min: int = CA_CONNECTS_PER_MIN, timeout: float = CA_READ_TIMEOUT, backoff=None, url: str = CA_EVENTS,
                 clock=time.monotonic):
        self.headers = {**headers, "Accept": "text/event-stream", "Cache-Control": "no-cache"}
        self.sink, self.state, self.start, self.last_id, self.url = sink, state, start, last_id, url
        self.opener = opener or urllib.request.urlopen
        self.connects_per_min, self.timeout, self.clock = connects_per_min, timeout, clock
        self.backoff = backoff or (lambda attempt: min(300.0, 5.0 * 2 ** min(attempt, 6)))
        self.stop_event, self.response, self.connects, self.counts = threading.Event(), None, deque(), defaultdict(int)
        self.resume_check, self.context = None, None   # context: (since, until) for a replay before the archive stream

    def request(self, params: dict | None, last_id: str | None) -> urllib.request.Request:
        headers = {**self.headers, **({"Last-Event-Id": last_id} if last_id else {})}
        return urllib.request.Request(self.url + ("?" + urllib.parse.urlencode(params) if params else ""), headers=headers)

    def may_connect(self) -> bool:
        now = self.clock()
        while self.connects and now - self.connects[0] >= 60:
            self.connects.popleft()
        if len(self.connects) >= self.connects_per_min:
            return False
        self.connects.append(now)
        return True

    def bounded(self, lines, deadline: float | None):
        """The response's lines, until ``deadline`` (a clock value) passes: then TimeoutError."""
        for line in lines:
            if deadline is not None and self.clock() > deadline:
                raise TimeoutError("ca_context_deadline")
            yield line

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
                    if valid and self.resume_check is not None:
                        if eid > self.resume_check:
                            self.counts["resume_gaps"] += 1
                            emitted = {"resume_emitted": ulid_time(self.resume_check), "first_emitted": ulid_time(eid)}
                            self.sink.write("monitor", {"event": "ca_resume_gap", "at": now_utc(), "resume_id": self.resume_check, "first_id": eid,
                                                        **{k: iso(v) if v else None for k, v in emitted.items()},
                                                        "note": "the resume id was not redelivered; events between may be missing"})
                        self.resume_check = None
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

    def replay_context(self, since: datetime, until: datetime, deadline_s: float = CA_CONTEXT_DEADLINE,
                       read_timeout: float = CA_CONTEXT_READ_TIMEOUT) -> int:
        """One bounded replay of the surfaced types in the US region (the server closes after ``until``) to build the board
        context; the whole replay ends after ``deadline_s`` seconds and each read after ``read_timeout``."""
        params = {"type": ",".join(t + CA_SUFFIX for t in CA_TYPES), "region": "us", "since": rfc3339(since), "until": rfc3339(until)}
        self.counts["context_replays"] += 1
        deadline = self.clock() + deadline_s
        with self.opener(self.request(params, None), timeout=read_timeout) as resp:
            self.response = resp
            try:
                return self.consume(self.bounded(resp, deadline), archive=False)
            finally:
                self.response = None

    def run_context(self) -> None:
        """The start-up context replay inside the connect budget, recorded as ca_context or ca_context_error."""
        since, until = self.context
        while not self.may_connect():
            self.counts["connect_budget_waits"] += 1
            if self.stop_event.wait(5.0):
                return
        try:
            replayed = self.replay_context(since, until)
            self.sink.write("monitor", {"event": "ca_context", "at": now_utc(), "since": rfc3339(since), "events": replayed,
                                        "actions": len(self.state.ca.actions)})
        except Exception as exc:  # the archive stream still runs; the context then builds from its events only
            self.sink.write("monitor", {"event": "ca_context_error", "at": now_utc(), "error": f"{type(exc).__name__}: {str(exc)[:160]}"})

    def run(self, archive: bool = True) -> None:
        """The context replay when one is set, then (with ``archive``) the archive stream with bounded reconnects."""
        if self.context is not None:
            self.run_context()
        attempt = 0
        while archive and not self.stop_event.is_set():
            if not self.may_connect():
                self.counts["connect_budget_waits"] += 1
                self.stop_event.wait(5.0)
                continue
            self.counts["connects"] += 1
            try:
                params = None if self.last_id else {"since": rfc3339(self.start)}
                self.resume_check = self.last_id
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


def iex_handler(state: State, sink: Sink):
    """The IEX stream's message handler: statuses go to status.jsonl and the merged halt state, LULD bands to luld.jsonl
    and the band book, imbalances to imbalance.jsonl, each with its receive time; every message is counted by type and
    tape (iex_tapes), which measures the tapes the IEX endpoint covers."""
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
    return on_iex


def engine_configs_using_iex(paths) -> tuple[list[str], list[str]]:
    """(configs that stream feed iex, configs that cannot be read) among the declared scheduled engine configs."""
    iex, unreadable = [], []
    for path in paths or ():
        try:
            config = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            unreadable.append(str(path))
            continue
        if not isinstance(config, dict):
            unreadable.append(str(path))
        elif str(config.get("feed") or "").lower() == "iex":
            iex.append(str(path))
    return iex, unreadable


def beside_frozen_bridge() -> bool:
    """True when the board_scan.py beside this file is protocol v1's frozen bridge, i.e. this file was copied into the
    forward study's deployed directory, where its board would pass that bridge's monitor-code check."""
    try:
        return hashlib.sha256((HERE / "board_scan.py").read_bytes()).hexdigest() == FROZEN_V1["board_scan.py"]
    except OSError:
        return False


def live_v1_monitors(proc: Path = Path("/proc")) -> list[int]:
    """PIDs of version 1 monitors running on this host, from /proc: a process running a file named monitor.py in run mode
    whose file is protocol v1's frozen monitor (FROZEN_V1), or whose arguments are version 1's (--env-file and --out, and
    neither --follow-v1 nor --standalone, one of which every version 2 run states). Unreadable processes are skipped."""
    found = []
    try:
        entries = [e for e in proc.iterdir() if e.name.isdigit() and int(e.name) != os.getpid()]
    except OSError:
        return found
    for entry in entries:
        try:
            args = [a.decode("utf-8", "replace") for a in (entry / "cmdline").read_bytes().split(b"\0") if a]
            cwd = os.readlink(entry / "cwd")
        except OSError:
            continue
        script = next((a for a in args if Path(a).name == "monitor.py"), None)
        if script is None or "run" not in args:
            continue
        try:
            frozen = hashlib.sha256((Path(cwd) / script).read_bytes()).hexdigest() == FROZEN_V1["monitor.py"]
        except OSError:
            frozen = False
        if frozen or ({"--env-file", "--out"} <= set(args) and not {"--follow-v1", "--standalone"} & set(args)):
            found.append(int(entry.name))
    return sorted(found)


def startup_refusal(args) -> str | None:
    """A reason to stop before credentials are read or any request is made, or None."""
    if beside_frozen_bridge():
        return "beside_frozen_v1_bridge"
    if args.follow_v1 is not None:
        if not args.follow_v1.is_dir():
            return "follow_v1_directory_missing"
        if args.follow_v1.resolve() == args.out.resolve():
            return "follow_v1_is_this_out_directory"
    elif live_v1_monitors():   # --standalone states that no version 1 monitor runs; one does on this host
        return "v1_monitor_running_use_follow_v1"
    return None


def ca_archive_start(value: str, today: date) -> datetime:
    """Where an empty corporate-actions archive starts: "retained" (everything the server still replays), "today" (00:00
    ET) or an RFC 3339 time. An archive that holds any event resumes from its last id instead, whatever its age."""
    if value == "retained":
        return utc(CA_ARCHIVE_SINCE)
    if value == "today":
        return datetime.combine(today, dtime(0, 0), ET)
    found = utc(value)
    if found is None:
        raise ValueError(f"ca_archive_since: {value!r}")
    return found


def data_spare(http: Http) -> tuple[bool, int | None]:
    """(optional data sources may run, calls left): they pause while the data API reports fewer than RATELIMIT_FLOOR."""
    remaining = http.data_remaining()
    return remaining is None or remaining >= RATELIMIT_FLOOR, remaining


async def run(args) -> int:
    follower = args.follow_v1 is not None
    sink, state, stop = Sink(args.out), State(), asyncio.Event()
    refused = startup_refusal(args)
    if refused:
        sink.write("monitor", {"event": "stop", "at": now_utc(), "refused": [refused]})
        sink.close()
        return 2
    key, secret = credentials(args.env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    # start-up loads before the plan exists; every other cap follows the plan (a follower makes no SEC request)
    budget = Budget(once={"assets": 5, "sec_files": 0 if follower else 5})
    http = Http(headers, None if follower else sec_identity(), budget)
    until = datetime.combine(state.today, datetime.strptime(args.until_et, "%H:%M").time(), ET)
    optional = (("iex_status_luld", args.iex_status), ("corporate_actions_sse", args.corporate_actions), ("screener", args.screener),
                ("option_chains", args.option_chains), ("option_oi", args.option_oi), ("finra_short_volume", args.finra))
    inherited = ["opra_trades", "news", "edgar", "nasdaq_halts"]
    sink.write("monitor", {"event": "start", "at": now_utc(), "mode": args.mode, "role": "follower" if follower else "standalone",
                           "follow_v1": str(args.follow_v1) if follower else None, "until_et": args.until_et,
                           "sweep_seconds": args.sweep_seconds, "pid": os.getpid(),
                           "sources": ["sip_snapshots"] + ([] if follower else inherited) + [n for n, on in optional if on],
                           "from_v1_files": inherited if follower else [], "board_versions": [BOARD_V2_VERSION] if follower else [BOARD_VERSION, BOARD_V2_VERSION]})
    symbols = await asyncio.to_thread(retry, lambda: load_universe(http))
    state.universe = set(symbols)
    plan = plan_budget(len(symbols), args)
    sink.write("monitor", {"event": "budget", "at": now_utc(), **plan})
    if plan["refusals"]:
        sink.write("monitor", {"event": "stop", "at": now_utc(), "refused": plan["refusals"]})
        sink.close()
        return 2
    budget.configure(plan["per_sweep"], plan["once"], plan["per_minute"])
    state.iv.max_age = IV_FRESH_SWEEPS * args.sweep_seconds
    if not follower:   # a follower takes each filing's tickers from version 1's rows
        state.cik_tickers = await asyncio.to_thread(retry, lambda: load_cik_tickers(http))
    code_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()  # the code this process loaded
    follow = FollowV1(args.follow_v1, state.today) if follower else None
    state.restored = await asyncio.to_thread(follow.poll, state) if follower else restore(state, sink.path(""))
    state.restored_v2 = restore_v2(state, sink.root, sink.path(""))
    if args.finra:
        try:
            state.short_volume_day, state.short_volume = load_short_volume(sink.root, finra_due(datetime.now(timezone.utc)))
        except (OSError, ValueError) as exc:
            state.restored_v2["finra_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    sink.write("monitor", {"event": "restored", "at": now_utc(), "counts": state.restored, "counts_v2": state.restored_v2,
                           "follow_v1_heartbeat": follow.heartbeat(datetime.now(timezone.utc)) if follower else None})
    adv = AdvLoader(symbols, state.today)
    adv_task = asyncio.create_task(asyncio.to_thread(adv.run, http))
    events = None
    if args.corporate_actions:
        events = EventStream(headers, sink, state, ca_archive_start(args.ca_archive_since, state.today), last_id=last_archived_event_id(sink.root))
        since = datetime.combine(state.today - timedelta(days=args.ca_context_days), dtime(0, 0), ET)
        events.context = (since, datetime.now(timezone.utc) - timedelta(seconds=60))
        if args.mode == "once":   # bounded; in run mode the replay runs first on the stream's own thread
            await asyncio.to_thread(events.run_context)
            events.context = None

    def on_news(msg):
        received = now_utc()
        sink.write("news", news_record(msg, received))
        for symbol in msg.get("symbols") or []:
            if msg.get("id") is not None:
                state.news[symbol].setdefault(msg["id"], time.time())

    def on_opra(msg):
        if msg.get("T") == "t":
            state.options.add(msg, state.today)

    tasks, threads, leases, running = [], [], [], []

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
        if not follower and leased("v1beta1-news"):
            running.append("news")
            tasks.append(asyncio.create_task(stream("news", NEWS_WS, {"action": "subscribe", "news": ["*"]}, headers, on_news, state, sink, stop, False)))
        if not follower and leased("v1beta1-opra"):
            running.append("opra")
            tasks.append(asyncio.create_task(stream("opra", OPRA_WS, {"action": "subscribe", "trades": ["*"]}, headers, on_opra, state, sink, stop, True)))
        if args.iex_status:
            iex_configs, unreadable = engine_configs_using_iex(args.engine_config)
            if iex_configs or unreadable:
                sink.write("monitor", {"event": "stream_refused", "endpoint": "v2-iex", "at": now_utc(),
                                       "reason": "engine_config_streams_iex" if iex_configs else "engine_config_unreadable",
                                       "configs": iex_configs or unreadable})
            elif leased("v2-iex"):
                running.append("iex_status")
                tasks.append(asyncio.create_task(stream("iex_status", IEX_WS, {"action": "subscribe", "statuses": ["*"], "lulds": ["*"], "imbalances": ["*"]},
                                                        headers, iex_handler(state, sink), state, sink, stop, False, conflict_wait=args.iex_conflict_wait)))
        if events is not None:
            archive = leased("v1beta1-events-corporate-actions")   # without the lease: the context replay only
            if archive:
                running.append("corporate_actions")
            threads.append(threading.Thread(target=events.run, kwargs={"archive": archive}, name="corporate-actions", daemon=True))
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
                except Exception as exc:  # the next attempt resumes where this one stopped; relvol stays empty meanwhile
                    stats["adv_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
                    if adv.index >= len(adv.symbols) and not adv.token:
                        adv = AdvLoader(symbols, state.today)   # a finished load without bars starts over
                    adv_task = asyncio.create_task(asyncio.to_thread(adv.run, http))
            spare, remaining = data_spare(http)
            if not spare:
                stats["ratelimit_floor"] = remaining
            jobs = [("snapshots", lambda: len(sweep_snapshots(http, symbols, state, sink, at, workers=3)))]
            if follower:
                jobs.append(("follow_v1", lambda: follow.poll(state)))
            else:
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
            # One scoring pass for both boards: board v2's rows carry exactly board.json's v1 parts and score.
            actions = state.ca.by_symbol(state.today)
            scored, v1_set = score_rows(state, at, v2_scoring_extra(state, at, actions))
            v1_rows = {s: scored[s] for s in v1_set}
            board, incentive = build_board(state, at, rows=v1_rows)
            down = {name: round(state.down_seconds[name] + (time.time() - since if (since := state.down_since.get(name)) else 0), 1)
                    for name in running}
            monitor = {"started_at": state.started_at, "code_sha256": code_sha256, "role": "follower" if follower else "standalone",
                       "restored": state.restored, "restored_v2": state.restored_v2, "stream_down_seconds": down, "adv_loaded": bool(state.adv),
                       "sweep_errors": sorted(k for k in stats if k.endswith("_error"))}
            if not follower:   # board version 1 is written before any version 2 work, which can neither delay nor stop it
                payload = board_v1_payload(at, board, incentive, monitor)
                sink.replace("board.json", json.dumps(payload, indent=1).encode())
                sink.write("board", {"at": payload["at"], "board": board[:50]})
            board_v2 = []
            try:
                if args.option_chains and chain_session_open(at):   # the top candidates by the v1 score
                    spare, remaining = data_spare(http)
                    if not spare:
                        stats["ratelimit_floor"] = remaining
                    else:
                        targets = option_targets(v1_rows, state, args.option_roots)
                        try:
                            stats["option_chains"] = await asyncio.to_thread(poll_option_chains, http, state, sink, args, targets, max(10.0, args.sweep_seconds))
                        except Exception as exc:
                            stats["option_chains_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
                        if args.option_oi:
                            left = http.remaining(TRADING_HOST)
                            if left is not None and left < TRADING_RATELIMIT_FLOOR:
                                stats["trading_ratelimit_floor"] = left
                            try:
                                stats["option_oi"] = await asyncio.to_thread(poll_option_oi, http, state, sink, args, targets)
                            except Exception as exc:
                                stats["option_oi_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
                if follower:
                    stats["follow_v1_heartbeat"] = follow.heartbeat(datetime.now(timezone.utc))
                board_v2, incentive_v2 = build_board_v2(state, at, rows=scored, v1=v1_set, actions=actions)
                payload_v2 = board_v2_payload(at, board_v2, incentive_v2, {**monitor, "sweep_errors": sorted(k for k in stats if k.endswith("_error"))})
                sink.replace("board-v2.json", json.dumps(payload_v2, indent=1).encode())
                sink.write("board-v2", {"at": payload_v2["at"], "board": board_v2[:50]})
                sink.replace("halt-state.json", json.dumps(halt_snapshot(state, at), separators=(",", ":")).encode())
            except Exception as exc:  # recorded; the next sweep tries again
                stats["board_v2_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            calls = {k: v - before.get(k, 0) for k, v in http.source_calls.items() if v - before.get(k, 0)}
            stats.update({"board": None if follower else len(board), "early": None if follower else sum(r["stage"] == "early" for r in board),
                          "board_v2": len(board_v2), "calls": dict(http.calls), "source_calls": calls, "budget_per_sweep": plan["per_sweep"],
                          "budget_refused": dict(budget.refused), "ratelimit": dict(http.ratelimit), "streams": dict(state.stream_counts),
                          "iex_tapes": dict(state.iex_tapes), "corporate_actions": dict(events.counts) if events else None,
                          "options_unparsed": state.options.unparsed, "follow_v1": dict(follow.counts) if follower else None,
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


def ca_since_arg(value: str) -> str:
    if value in ("retained", "today") or utc(value) is not None:
        return value
    raise argparse.ArgumentTypeError("retained, today or an RFC 3339 time with a zone")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("run", "once"))
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    role = ap.add_mutually_exclusive_group(required=True)
    role.add_argument("--follow-v1", type=Path, metavar="V1_OUT",
                      help="run beside a version 1 monitor whose --out is V1_OUT: read its news, OPRA, EDGAR and halt files instead of "
                           "holding news and OPRA and polling EDGAR and the Nasdaq RSS; write board-v2.json only")
    role.add_argument("--standalone", action="store_true",
                      help="no version 1 monitor runs on this account: hold news and OPRA, poll EDGAR and the Nasdaq RSS, write both boards")
    ap.add_argument("--until-et", default="20:00")
    ap.add_argument("--sweep-seconds", type=float, default=20.0, help="sweep cadence; the data plan is refused above 5%% of the data limit")
    ap.add_argument("--edgar-seconds", type=float, default=20.0, help="EDGAR current-filings cycle (7 requests, at most one cycle a sweep)")
    ap.add_argument("--rss-seconds", type=float, default=RSS_MIN_SECONDS, help="Nasdaq halts RSS interval (refused below 60)")
    ap.add_argument("--option-roots", type=int, default=25, help="option chains per sweep: the top board candidates")
    ap.add_argument("--option-pages", type=int, default=1, help="pages of 1,000 contracts per chain")
    ap.add_argument("--option-retries", type=int, default=5, help="roots per sweep asked again without the strike band after an empty in-band chain")
    ap.add_argument("--option-min-dte", type=int, default=7)
    ap.add_argument("--option-window-days", type=int, default=35, help="expiry window after the minimum days to expiry (35 holds a monthly expiry)")
    ap.add_argument("--option-strike-band", type=float, default=0.10)
    ap.add_argument("--oi-per-sweep", type=int, default=2, help="contracts-endpoint calls per sweep (trading API; once per root per day)")
    ap.add_argument("--ca-context-days", type=int, default=30, help="corporate-action context replayed at start")
    ap.add_argument("--ca-archive-since", type=ca_since_arg, default="retained",
                    help="where an empty corporate-action archive starts: retained (all the server replays), today, or an RFC 3339 time")
    ap.add_argument("--iex-conflict-wait", type=float, default=900.0, help="seconds to wait after a 406 on the IEX endpoint")
    ap.add_argument("--engine-config", type=Path, action="append", default=[],
                    help="a scheduled engine config (repeatable); the IEX stream is refused while any of them streams feed iex")
    ap.add_argument("--lease-dir", type=Path, default=default_lease_dir(), help="host leases, one per stream endpoint")
    ap.add_argument("--iex-status", action="store_true",
                    help="hold the IEX stock stream for statuses, LULD bands and imbalances (off by default: an engine with feed iex needs it)")
    ap.add_argument("--option-oi", action="store_true",
                    help="open interest from the trading API's contracts endpoint (off by default: only on an account no engine trades)")
    for name in ("corporate-actions", "screener", "option-chains", "finra"):
        ap.add_argument(f"--no-{name}", dest=name.replace("-", "_"), action="store_false", help=f"leave the {name} source off")
    return ap


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
