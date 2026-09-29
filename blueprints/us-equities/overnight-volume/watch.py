"""Overnight (BOATS) volume watch: records significant overnight-session volume for every overnight-tradable US equity.

  python watch.py plan --symbols N                            # the call plan for N names; no network, no credentials
  python watch.py once --env-file ENV --out DIR               # dry run (alias --once): start-up, one sweep, counts only
  python watch.py run  --env-file ENV --out DIR [--no-push]   # a sweep every 120 s until 04:00 ET, a STOP file or SIGTERM

Data only: it never places, changes or cancels an order and makes no trading-API write. Every request must pass a GET
allow-list (paper trading /v2/assets; data /v2/stocks/snapshots and /v2/stocks/bars) and a per-source call budget
(monitor.Budget) before it is made. ENV is the 0600 PAPER key file (monitor.credentials); no key is ever printed.

Sources (docs.alpaca.markets): the overnight session runs 20:00-04:00 ET on the evening before its trade date, on the
Blue Ocean ATS (BOATS); with Algo Trader Plus, feed=boats serves snapshots and historical bars. thresholds-v1.json,
committed before the first sweep, fixes the measures, tiers and lists (any change is a new id):

  overnight_shares  BOATS snapshot dailyBar.v when the UTC date of dailyBar.t is the trade date: BOATS keys a session's
                    bar at 00:00Z of its trade date (20:00 ET the evening before); prevDailyBar, the previous overnight
                    session, is never used
  adv_fraction      overnight_shares / SIP ADV20 (monitor.AdvLoader's formula, split-adjusted)
  change            BOATS dailyBar.c / SIP 1Day close of the prior regular session - 1
  relvol_boats20    overnight_shares / (BOATS 1Day volume summed over the 20 SIP sessions before the trade date / 20)

Output goes to one fixed --out directory, owner-only as monitor.Sink: start.json, sweeps.jsonl, alerts.jsonl (the first
crossing per symbol and tier, and every push), top.jsonl, board.json, snapshots/HHMMSS.json.gz and stop.json. The notify
tier is pushed, best effort, to a loopback ntfy topic. These are indicative data from one ATS, not consolidated volume,
and the tiers are unvalidated monitoring thresholds, not a trading rule.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "incentive-monitor"))
import monitor as M  # noqa: E402  (neutral helpers; this file is not named monitor.py, see monitor.live_v1_monitors)

THRESHOLDS_PATH = HERE / "thresholds-v1.json"
# The only requests this watch makes, as (host, path) of a GET; the trading host is the paper API.
ALLOWED_GETS = frozenset({(M.TRADING_HOST, "/v2/assets"), (M.DATA_HOST, "/v2/stocks/snapshots"), (M.DATA_HOST, "/v2/stocks/bars")})
BASELINE_SESSIONS = 20      # relvol_boats20 divides the 20-session BOATS sum by 20 (a missing date counts as 0)
SIP_WINDOW_DAYS = 40        # calendar days of SIP 1Day bars: at least 20 sessions around a holiday
READING_MAX_AGE = 60.0      # a rate-limit reading older than one window says nothing about the current one
BUDGET_WAIT = 5.0           # seconds between tries while the daily-bar source's per-minute cap is spent
LOAD_ATTEMPTS = 4           # resumed attempts of one daily-bar pass after a request failed ADV_ATTEMPTS times
STARTUP_SECONDS = 600.0     # the daily-bar passes give up after this long
SNAPSHOT_WORKERS = 3        # as monitor.run's snapshot sweep
WAIT_STEP = 5.0             # between sweeps the stop conditions are checked at least this often
ROLL_PROBE = "SPY"          # a change of its BOATS dailyBar.t is logged as session_bar_rolled
TIERS = ("significant", "notify")
# Mirrored from scripts/host_requests.py@351a1b0d (NOTIFY_TOPIC_RE and NOTIFY_HOSTS 116-117, check_notify_url 408-420,
# send_notice 596-607). That module also imports scripts/validate.py, and this overnight process should not load a
# foundation script at start-up; tests/test_overnight_volume.py checks the URL rule against the original.
NOTIFY_TOPIC_RE = re.compile(r"/[A-Za-z0-9_-]{1,64}")
NOTIFY_HOSTS = ("127.0.0.1", "localhost")


class NotAllowed(RuntimeError):
    """A request outside the GET allow-list, refused before it is made."""


class UsageError(ValueError):
    """An invalid argument, thresholds file or notify URL."""


class Refused(RuntimeError):
    """A start-up refusal (the plan or the reference data break a rule): nothing is swept."""

    def __init__(self, codes: list[str], detail: dict | None = None):
        super().__init__(", ".join(codes))
        self.codes, self.detail = list(codes), detail or {}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def zulu(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- network

def allowed_get(url: str) -> str:
    """The url when it is an allow-listed GET target (https, exact host and path, no credentials, port or fragment)."""
    parts = urllib.parse.urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        port = -1
    if (parts.scheme != "https" or parts.username is not None or parts.password is not None or port is not None
            or parts.fragment or (parts.hostname, parts.path) not in ALLOWED_GETS):
        raise NotAllowed(f"{parts.scheme}://{parts.hostname}{parts.path}")
    return url


class GuardedHttp(M.Http):
    """monitor.Http (per-source budget, call counts, rate-limit headers) behind the GET allow-list, keeping the time of
    each host's last reading."""

    def __init__(self, alpaca_headers: dict, budget: M.Budget | None, clock=time.monotonic):
        super().__init__(alpaca_headers, None, budget)
        self.clock, self.read_at = clock, {}

    def get(self, url: str, kind: str, headers: dict, timeout: float = 20) -> bytes:
        allowed_get(url)
        body = super().get(url, kind, headers, timeout)
        with self.lock:
            self.read_at[urllib.parse.urlsplit(url).hostname] = self.clock()
        return body

    def fresh_data_remaining(self, max_age: float = READING_MAX_AGE) -> int | None:
        with self.lock:
            at = self.read_at.get(M.DATA_HOST)
        if at is None or self.clock() - at > max_age:
            return None
        return self.data_remaining()


def data_floor(http: GuardedHttp) -> tuple[bool, int | None]:
    """(the sweep may continue, calls left) by monitor.data_spare's RATELIMIT_FLOOR, from a reading at most a minute old.
    data_spare reads the last response whatever its age; at a 120 s cadence that reading is always from the previous
    window, and a sweep skipped on a stale low reading would make no request that could refresh it."""
    remaining = http.fresh_data_remaining()
    return remaining is None or remaining >= M.RATELIMIT_FLOOR, remaining


def check_notify_url(url: str) -> str:
    """Accept only a loopback ntfy topic URL: http, host 127.0.0.1 or localhost, a single topic path segment, no
    credentials, query or fragment."""
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise UsageError(f"notify URL is not a valid URL: {error}") from None
    if (parts.scheme != "http" or parts.hostname not in NOTIFY_HOSTS or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or not NOTIFY_TOPIC_RE.fullmatch(parts.path) or (port is not None and not 0 < port < 65536)):
        raise UsageError("notify URL must be http://127.0.0.1[:PORT]/TOPIC or http://localhost[:PORT]/TOPIC")
    return url


def send_notice(url: str, message: str, opener=None) -> None:
    """POST one fixed-format line to a loopback ntfy topic: no proxy, no redirect."""

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(check_notify_url(url), data=message.encode("utf-8"), method="POST",
                                     headers={"Content-Type": "text/plain; charset=utf-8"})
    with opener.open(request, timeout=5) as response:
        response.read(1024)


# ---------------------------------------------------------------- plan, universe and reference data (pure)

def load_thresholds(path: Path) -> dict:
    thresholds = json.loads(Path(path).read_text())
    missing = [k for k in ("id", "session", "sources", "universe", "significant", "notify", "top_n", "alerts") if k not in thresholds]
    if missing:
        raise UsageError(f"thresholds file lacks {', '.join(missing)}")
    return thresholds


def overnight_universe(assets: list, rules: dict) -> dict:
    """symbol -> asset name: monitor.load_assets' rule (tradable, no excluded character) plus the overnight attributes,
    which v2/assets returns as strings inside ``attributes`` (load_assets drops that field)."""
    out = {}
    for asset in assets:
        symbol, attributes = asset.get("symbol") or "", asset.get("attributes") or []
        if (asset.get("tradable") is not rules["tradable"] or asset.get("status", rules["status"]) != rules["status"]
                or asset.get("class", rules["asset_class"]) != rules["asset_class"]
                or rules["attribute_required"] not in attributes or rules["attribute_excluded"] in attributes
                or not symbol or any(ch in symbol for ch in rules["symbol_excludes"])):
            continue
        out[symbol] = asset.get("name") or ""
    return out


def plan_calls(symbols: int, sources: dict, sweep_seconds: float | None = None) -> dict:
    """The call plan for ``symbols`` names, refused by monitor.plan_budget's rule: the sweep rate plus both daily-bar
    passes in one minute must stay within 5% of the 10,000/min data limit (and the asset load within 5% of 200/min)."""
    seconds = sources["sweep_seconds"] if sweep_seconds is None else sweep_seconds
    if seconds <= 0:
        return {"symbols": symbols, "refusals": ["invalid_bounds"]}
    if symbols <= 0:
        return {"symbols": symbols, "refusals": ["empty_universe"]}
    chunks = math.ceil(symbols / sources["snapshot_symbols_per_call"])
    passes = math.ceil(symbols / sources["bars_symbols_per_call"])
    sweeps_per_min = 60.0 / seconds
    data_per_min = chunks * sweeps_per_min
    data_cap = M.DATA_LIMIT_PER_MIN * min(M.BUDGET_FRACTION, sources["max_data_fraction_per_min"])
    trading_cap = M.TRADING_LIMIT_PER_MIN * M.BUDGET_FRACTION
    once = {"assets": 5}   # the start-up asset load, retries included (monitor.retry's five attempts)
    refusals = []
    if data_per_min + 2 * passes > data_cap:
        refusals.append("data_calls_above_5pct_of_limit")
    if once["assets"] > trading_cap:
        refusals.append("trading_calls_above_5pct_of_limit")
    return {"symbols": symbols, "sweep_seconds": seconds, "sweeps_per_min": round(sweeps_per_min, 3),
            "per_sweep": {"snapshots": chunks}, "once": once, "per_minute": {"adv_bars": 2 * passes},
            "startup_calls": 1 + 2 * passes, "data_per_min": round(data_per_min, 1),
            "data_first_min": round(data_per_min + 2 * passes, 1), "data_cap_per_min": data_cap,
            "trading_first_min": once["assets"], "trading_cap_per_min": trading_cap, "refusals": refusals}


def stop_times(trade_date: date, session: dict) -> tuple[datetime, datetime]:
    """(stop, backstop) as UTC datetimes: the session's stop_et and backstop_et on the trade date, in New York time."""
    def at(hhmm: str) -> datetime:
        return datetime.combine(trade_date, dtime.fromisoformat(hhmm), M.ET).astimezone(timezone.utc)
    return at(session["stop_et"]), at(session["backstop_et"])


class DailyBars:
    """1Day bars for many symbols from one feed, 200 symbols a request, modeled on monitor.AdvLoader: each request is
    tried up to ADV_ATTEMPTS times; a request that still fails ends the attempt where it stopped, and the next attempt
    resumes from that chunk and page, so finished requests are never repeated; a budget refusal ends the attempt at once.
    Unlike AdvLoader (volume only, feed sip) it keeps each bar's time, close and volume and takes the feed and window."""

    def __init__(self, symbols: list[str], feed: str, start: str, end: str, adjustment: str | None = None, per_call: int = 200,
                 attempts: int = M.ADV_ATTEMPTS, first_wait: float = M.ADV_RETRY_WAIT, sleep=time.sleep):
        self.symbols, self.feed, self.start, self.end, self.adjustment = list(symbols), feed, start, end, adjustment
        self.per_call, self.attempts, self.first_wait, self.sleep = per_call, attempts, first_wait, sleep
        self.index, self.token, self.bars, self.failures, self.calls = 0, None, defaultdict(list), 0, 0

    def run(self, http) -> dict:
        while self.index < len(self.symbols):
            params = {"symbols": ",".join(self.symbols[self.index:self.index + self.per_call]), "timeframe": "1Day",
                      "start": self.start, "end": self.end, "feed": self.feed, "limit": 10000,
                      **({"adjustment": self.adjustment} if self.adjustment else {}),
                      **({"page_token": self.token} if self.token else {})}
            for attempt in range(self.attempts):
                try:
                    body = http.alpaca_json(M.DATA, "/v2/stocks/bars", params)
                except (M.BudgetExceeded, NotAllowed):
                    raise
                except Exception:
                    self.calls += 1
                    self.failures += 1
                    if attempt == self.attempts - 1:
                        raise
                    self.sleep(self.first_wait * 2 ** attempt)
                else:
                    self.calls += 1
                    break
            for symbol, bars in (body.get("bars") or {}).items():
                self.bars[symbol].extend({"t": b.get("t"), "c": b.get("c"), "v": b.get("v")} for b in bars)
            self.token = body.get("next_page_token")
            if not self.token:
                self.index += self.per_call
        return dict(self.bars)


def load_bars(loader: DailyBars, http, deadline: float, sleep=time.sleep, clock=time.monotonic) -> dict:
    """Run one daily-bar pass to its end: wait while the per-minute cap is spent (the cap equals both passes exactly, so
    any retry or extra page waits for the rolling minute) and resume after a failed request, until ``deadline``."""
    failed = 0
    while True:
        try:
            return loader.run(http)
        except M.BudgetExceeded:
            if clock() >= deadline:
                raise
            sleep(BUDGET_WAIT)
        except NotAllowed:
            raise
        except Exception:
            failed += 1
            if failed >= LOAD_ATTEMPTS or clock() >= deadline:
                raise
            sleep(M.ADV_RETRY_WAIT * 2 ** failed)


def bar_day(t: str | None, utc_date: bool = False) -> date | None:
    """A bar's session date: SIP 1Day bars are keyed at 00:00 New York time (ET date), BOATS 1Day bars at 00:00Z of
    their trade date (UTC date)."""
    at = M.utc(t)
    if at is None:
        return None
    return at.date() if utc_date else at.astimezone(M.ET).date()


def reference(sip_bars: dict, trade_date: date) -> dict:
    """From SIP 1Day bars before the trade date: the last 20 session dates (the dates the bars span, so no calendar call is
    needed), the prior regular session, ADV20 by monitor.AdvLoader's formula (the mean of a symbol's last 20 bars, fewer
    for a new listing) and each symbol's close on the prior session (absent when it has no bar that day)."""
    kept, dates = {}, set()
    for symbol, bars in sip_bars.items():
        by_day = {}
        for bar in bars:
            day = bar_day(bar.get("t"))
            if day is not None and day < trade_date:
                by_day[day] = bar
        if by_day:
            kept[symbol] = [by_day[d] for d in sorted(by_day)]
            dates.update(by_day)
    ordered = sorted(dates)
    prior = ordered[-1] if ordered else None
    adv20, ref_close = {}, {}
    for symbol, bars in kept.items():
        volumes = [b["v"] for b in bars if isinstance(b.get("v"), (int, float))]
        if volumes:
            adv20[symbol] = sum(volumes[-20:]) / len(volumes[-20:])
        if bar_day(bars[-1].get("t")) == prior and bars[-1].get("c"):
            ref_close[symbol] = bars[-1]["c"]
    return {"dates20": ordered[-BASELINE_SESSIONS:], "prior_session": prior, "adv20": adv20, "ref_close": ref_close,
            "symbols": len(kept)}


def baseline20(boats_bars: dict, dates20: list[date]) -> dict:
    """Per symbol, the BOATS 1Day volume summed over the 20 SIP sessions (a date without a bar adds 0) and the number of
    those dates with a bar. The in-progress trade-date bar and older bars fall outside the dates."""
    window, base_sum, prior = set(dates20), {}, {}
    for symbol, bars in boats_bars.items():
        by_day = {}
        for bar in bars:
            day = bar_day(bar.get("t"), utc_date=True)
            if day in window and isinstance(bar.get("v"), (int, float)):
                by_day[day] = bar["v"]
        if by_day:
            base_sum[symbol], prior[symbol] = sum(by_day.values()), len(by_day)
    return {"base_sum": base_sum, "prior_sessions": prior, "symbols": len(base_sum)}


# ---------------------------------------------------------------- measures and selection (pure)

def session_bar(snap: dict | None, trade_date: date) -> dict | None:
    """The BOATS snapshot's dailyBar when it is the trade date's session bar: the UTC date of dailyBar.t is the trade
    date. An ET date puts 00:00Z on the evening before, which is why monitor.snapshot_features (ET days) is not used."""
    bar = (snap or {}).get("dailyBar") or {}
    at = M.utc(bar.get("t"))
    if at is None or at.date() != trade_date or not isinstance(bar.get("v"), (int, float)):
        return None
    return bar


def measures(symbol: str, snap: dict, trade_date: date, ctx: dict, now: datetime, fund: bool = False) -> dict | None:
    """The thresholds' measures for one name with a session bar, else None."""
    bar = session_bar(snap, trade_date)
    if bar is None:
        return None
    v, vw, close = bar["v"], bar.get("vw"), bar.get("c")
    adv, ref = ctx.get("adv20", {}).get(symbol), ctx.get("ref_close", {}).get(symbol)
    total = ctx.get("base_sum", {}).get(symbol, 0)
    trade, quote = snap.get("latestTrade") or {}, snap.get("latestQuote") or {}
    traded = M.utc(trade.get("t"))
    bid, ask = quote.get("bp") or 0, quote.get("ap") or 0
    return {"s": symbol, "overnight_shares": v,
            "overnight_dollar_volume": round(v * vw, 2) if vw else None,   # approximate: vw excludes odd lots
            "adv20_shares": round(adv, 1) if adv else None,
            "adv_fraction": round(v / adv, 6) if adv else None,
            "ref_close": ref, "close": close,
            "change": round(close / ref - 1, 6) if ref and close else None,
            "relvol_boats20": round(v / (total / BASELINE_SESSIONS), 4) if total > 0 else None,
            "prior_sessions": ctx.get("prior_sessions", {}).get(symbol, 0),
            "trades": bar.get("n"),
            "last_trade_age_s": round((now - traded).total_seconds(), 1) if traded else None,
            "spread_bps": round((ask - bid) / ((ask + bid) / 2) * 1e4, 1) if bid > 0 and ask >= bid else None,
            "fund": bool(fund)}


def qualifies(row: dict, tier: dict) -> list[str]:
    """The tier's criteria a row meets (empty when it does not qualify): the dollar-volume floor and any of the rules,
    relative volume counting only with enough prior BOATS sessions."""
    dv = row.get("overnight_dollar_volume")
    if dv is None or dv < tier["min_dollar_volume_usd"]:
        return []
    rules, reasons = tier["any_of"], []
    if row.get("adv_fraction") is not None and row["adv_fraction"] >= rules["min_adv_fraction"]:
        reasons.append("adv_fraction")
    if row.get("change") is not None and abs(row["change"]) >= rules["min_abs_change"]:
        reasons.append("change")
    if (row.get("relvol_boats20") is not None and row.get("prior_sessions", 0) >= tier["relvol_min_prior_sessions"]
            and row["relvol_boats20"] >= rules["min_relvol_boats20"]):
        reasons.append("relvol_boats20")
    return reasons


def by_dollar_volume(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (-(r.get("overnight_dollar_volume") or 0), r["s"]))


def top_n(rows: list[dict], spec: dict) -> list[dict]:
    key = spec["by"]
    eligible = [r for r in rows if r.get(key) is not None and (r.get("overnight_dollar_volume") or 0) >= spec["min_dollar_volume_usd"]
                and r.get("prior_sessions", 0) >= spec["min_prior_sessions"]]
    return sorted(eligible, key=lambda r: (-r[key], r["s"]))[:spec["n"]]


def money(value: float) -> str:
    if value >= 1e6:
        return f"${value / 1e6:.1f}M"
    if value >= 1e3:
        return f"${value / 1e3:.0f}k"
    return f"${value:.0f}"


def notice_text(row: dict, ref_session: date, at: datetime, min_prior: int = 10) -> str:
    """One line with no credential, e.g. "overnight XYZ $3.2M 6.1% ADV +12.4% vs 09-28 close relvol 14 00:42 ET"."""
    parts = ["overnight", row["s"]]
    if row.get("overnight_dollar_volume") is not None:
        parts.append(money(row["overnight_dollar_volume"]))
    if row.get("adv_fraction") is not None:
        parts.append(f"{row['adv_fraction'] * 100:.1f}% ADV")
    if row.get("change") is not None:
        parts.append(f"{row['change'] * 100:+.1f}% vs {ref_session:%m-%d} close")
    if row.get("relvol_boats20") is not None and row.get("prior_sessions", 0) >= min_prior:
        parts.append(f"relvol {row['relvol_boats20']:.0f}")
    parts.append(f"{at.astimezone(M.ET):%H:%M} ET")
    return " ".join(parts)


class Alerts:
    """The first crossing per symbol and tier, and the notify tier's push queue: non-fund names (exclude_fund_names), once
    per symbol, at most max_per_sweep a sweep and max_per_session a session, largest dollar volume first. Dry-run
    records (the once mode) are written but never restored."""

    def __init__(self, thresholds: dict):
        self.tiers = {tier: thresholds[tier] for tier in TIERS}
        self.alerted = {tier: set() for tier in TIERS}
        self.pending, self.pushed, self.attempts, self.rows = [], set(), 0, {}

    def restore(self, records) -> dict:
        queued = []
        for record in records:
            if record.get("dry_run") or not record.get("s"):
                continue
            if record.get("event") == "alert" and record.get("tier") in self.alerted:
                self.alerted[record["tier"]].add(record["s"])
                if record["tier"] == "notify" and record.get("push") == "queued":
                    queued.append(record["s"])
                    self.rows[record["s"]] = record
            elif record.get("event") == "push":
                self.pushed.add(record["s"])
                self.attempts += 1
        self.pending = [s for s in dict.fromkeys(queued) if s not in self.pushed]
        return {"significant": len(self.alerted["significant"]), "notify": len(self.alerted["notify"]),
                "pushes": self.attempts, "pending": len(self.pending)}

    def cross(self, rows: list[dict], at: str, dry_run: bool = False, push: bool = True) -> list[dict]:
        records = []
        for row in by_dollar_volume(rows):
            for tier in TIERS:
                if row["s"] in self.alerted[tier]:
                    continue
                reasons = qualifies(row, self.tiers[tier])
                if not reasons:
                    continue
                self.alerted[tier].add(row["s"])
                record = {"event": "alert", "tier": tier, "at": at, **row, "reasons": reasons, "dry_run": dry_run}
                if tier == "notify":
                    if self.tiers["notify"].get("exclude_fund_names") and row.get("fund"):
                        record["push"] = "excluded_fund_name"
                    elif dry_run:
                        record["push"] = "dry_run"
                    elif not push:
                        record["push"] = "disabled"
                    elif row["s"] in self.pushed:
                        record["push"] = "already_pushed"
                    else:
                        record["push"] = "queued"
                        self.pending.append(row["s"])
                        self.rows[row["s"]] = row
                records.append(record)
        return records

    def due(self) -> list[str]:
        notify = self.tiers["notify"]
        room = max(0, min(notify["max_per_sweep"], notify["max_per_session"] - self.attempts))
        due, self.pending = self.pending[:room], self.pending[room:]
        return due

    def record_push(self, symbol: str) -> None:
        self.pushed.add(symbol)
        self.attempts += 1


class FixedSink(M.Sink):
    """monitor.Sink's owner-only files (0600 in 0700 directories), torn-line repair and atomic replace, in one fixed
    directory: Sink.path takes a day directory from now(ET) on every write, which would split a session at midnight."""

    def path(self, name: str, day: str | None = None) -> Path:
        return self.root / name


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*argv: str) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(HERE), *argv], capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip()


# ---------------------------------------------------------------- the watch

class Watch:
    def __init__(self, args):
        self.args, self.mode = args, args.mode
        self.th = load_thresholds(args.thresholds)
        session = self.th["session"]
        bound = date.fromisoformat(session["trade_date"])
        if getattr(args, "trade_date", None) is not None and date.fromisoformat(str(args.trade_date)) != bound:
            raise UsageError(f"the thresholds file binds trade date {bound}; another trade date needs a new thresholds id")
        self.trade_date = bound
        self.stop_at, self.backstop_at = stop_times(bound, session)
        self.expected_prior = date.fromisoformat(session.get("ref_session") or session["overnight_start_et"][:10])
        self.dry_run = self.mode == "once"
        self.push_enabled = not self.dry_run and not getattr(args, "no_push", False)
        self.notify_url = check_notify_url(self.th["alerts"]["ntfy_url"])
        self.sink = FixedSink(Path(args.out))
        self.stop_event, self.stop_reason = threading.Event(), None
        self.monotonic, self.wait, self.send, self.sleep = time.monotonic, self.stop_event.wait, send_notice, time.sleep
        self.alerts = Alerts(self.th)
        self.http = self.budget = self.plan = self.ref_session = self.last = self.roll_t = None
        self.symbols, self.names, self.ctx = [], {}, {}
        self.sweeps, self.errors, self.pushes, self.t0 = 0, 0, {"sent": 0, "failed": 0}, time.monotonic()

    def request_stop(self, reason: str) -> None:
        self.stop_reason = self.stop_reason or reason
        self.stop_event.set()

    def should_stop(self, check_time: bool = True) -> str | None:
        if self.stop_event.is_set():
            return self.stop_reason or "signal"
        if (self.sink.root / "STOP").exists():
            return "stop_file"
        if check_time and self.mode == "run" and utcnow() >= self.stop_at:
            return "stop_time"
        return None

    def pause(self, until: float) -> str | None:
        while True:
            reason = self.should_stop()
            if reason:
                return reason
            left = until - self.monotonic()
            if left <= 0:
                return None
            self.wait(min(WAIT_STEP, left))

    def execute(self) -> int:
        self.t0 = time.monotonic()
        if self.mode == "run" and utcnow() >= self.stop_at:
            return self.finish("refused", code=2, refused=["session_over"])
        reason = self.should_stop(check_time=False)
        if reason:
            return self.finish(reason)
        try:
            self.startup()
        except Refused as exc:
            return self.finish("refused", code=2, refused=exc.codes, detail=exc.detail)
        except Exception as exc:   # credentials, network or budget: recorded, nothing swept
            return self.finish("error", code=1, error=f"{type(exc).__name__}: {str(exc)[:200]}")
        while True:
            reason = self.should_stop()
            if reason:
                break
            began = self.monotonic()
            try:
                self.sweep()
            except Exception as exc:   # recorded; the next sweep tries again
                self.errors += 1
                self.sink.write("sweeps", {"event": "sweep_error", "at": iso(utcnow()), "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                if self.mode == "once":
                    return self.finish("error", code=1, error=f"{type(exc).__name__}: {str(exc)[:200]}")
            if self.mode == "once":
                reason = "once"
                break
            reason = self.pause(began + self.plan["sweep_seconds"])
            if reason:
                break
        return self.finish(reason)

    def startup(self) -> None:
        key, secret = M.credentials(Path(self.args.env_file))
        self.budget = M.Budget(once={"assets": 5})
        self.http = GuardedHttp({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, self.budget, clock=self.monotonic)
        rules, sources = self.th["universe"], self.th["sources"]
        assets = M.retry(lambda: self.http.alpaca_json(M.TRADING, "/v2/assets", {"status": rules["status"], "asset_class": rules["asset_class"]}))
        self.names = overnight_universe(assets, rules)
        self.symbols = sorted(self.names)
        self.plan = plan_calls(len(self.symbols), sources)
        if self.plan["refusals"]:
            raise Refused(self.plan["refusals"], {"symbols": len(self.symbols)})
        self.budget.configure(self.plan["per_sweep"], self.plan["once"], self.plan["per_minute"])
        deadline = self.monotonic() + STARTUP_SECONDS
        end = datetime.combine(self.trade_date, dtime(0), timezone.utc)
        sip = load_bars(DailyBars(self.symbols, sources["reference_feed"], zulu(end - timedelta(days=SIP_WINDOW_DAYS)), zulu(end),
                                  adjustment="split", per_call=sources["bars_symbols_per_call"], sleep=self.sleep),
                        self.http, deadline, sleep=self.sleep, clock=self.monotonic)
        ref = reference(sip, self.trade_date)
        if ref["prior_session"] != self.expected_prior:
            raise Refused(["prior_session_mismatch"], {"prior_session": str(ref["prior_session"]), "expected": str(self.expected_prior)})
        if len(ref["dates20"]) < BASELINE_SESSIONS:
            raise Refused(["fewer_than_20_sip_sessions"], {"sessions": len(ref["dates20"])})
        # BOATS bars from the day before the first date (start inclusivity does not matter) to 1 s before 00:00Z of the
        # trade date; baseline20 still keeps only the 20 dates, since the in-progress trade-date bar can come back.
        boats = load_bars(DailyBars(self.symbols, sources["overnight_feed"], zulu(datetime.combine(ref["dates20"][0] - timedelta(days=1), dtime(0), timezone.utc)),
                                    zulu(end - timedelta(seconds=1)), per_call=sources["bars_symbols_per_call"], sleep=self.sleep),
                          self.http, deadline, sleep=self.sleep, clock=self.monotonic)
        base = baseline20(boats, ref["dates20"])
        self.ctx = {"adv20": ref["adv20"], "ref_close": ref["ref_close"], "base_sum": base["base_sum"], "prior_sessions": base["prior_sessions"]}
        self.ref_session = ref["prior_session"]
        restored = self.alerts.restore(self.read_alerts()) if self.mode == "run" else None
        listed = [a for a in assets if a.get("tradable") and "/" not in (a.get("symbol") or "/") and " " not in a["symbol"]]
        start = {"event": "start", "at": iso(utcnow()), "id": self.th["id"], "mode": self.mode, "trade_date": str(self.trade_date),
                 "overnight_start_et": self.th["session"]["overnight_start_et"], "stop_at": iso(self.stop_at), "backstop_at": iso(self.backstop_at),
                 "git_head": git("rev-parse", "HEAD"), "git_status": (git("status", "--porcelain", "--", ".", "../incentive-monitor/monitor.py") or "").splitlines(),
                 "sha256": {"watch.py": sha256(__file__), "monitor.py": sha256(M.__file__), "thresholds": sha256(self.args.thresholds)},
                 "python": sys.version.split()[0], "pid": os.getpid(), "plan": self.plan,
                 "universe": {"assets": len(assets), "tradable": len(listed),
                              "overnight_tradable": sum(rules["attribute_required"] in (a.get("attributes") or []) for a in listed),
                              "overnight_halted": sum(rules["attribute_excluded"] in (a.get("attributes") or []) for a in listed),
                              "watched": len(self.symbols)},
                 "reference": {"prior_session": str(self.ref_session), "dates20": [str(ref["dates20"][0]), str(ref["dates20"][-1])],
                               "sip_symbols": ref["symbols"], "adv20": len(ref["adv20"]), "ref_close": len(ref["ref_close"]),
                               "boats_symbols": base["symbols"], "boats_prior_sessions_ge_10": sum(k >= 10 for k in base["prior_sessions"].values()),
                               "boats_adjustment": "none (as calibrated)", "sip_adjustment": "split"},
                 "calls": dict(self.http.source_calls), "ratelimit": dict(self.http.ratelimit),
                 "push": {"enabled": self.push_enabled, "url": self.notify_url}, "restored": restored}
        self.sink.replace("start.json", json.dumps(start, indent=1).encode())
        self.sink.write("sweeps", {k: start[k] for k in ("event", "at", "id", "mode", "git_head", "sha256", "universe", "reference", "calls", "restored")})
        if self.mode == "run":
            print(json.dumps({"event": "start", "id": self.th["id"], "watched": len(self.symbols), "startup_calls": sum(self.http.source_calls.values()),
                              "per_sweep": self.plan["per_sweep"], "prior_session": str(self.ref_session), "restored": restored,
                              "push": self.push_enabled}, sort_keys=True), flush=True)

    def read_alerts(self) -> list[dict]:
        path, records = self.sink.root / "alerts.jsonl", []
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    records.append(json.loads(line))
                except ValueError:   # a line torn by a crash
                    continue
        return records

    def sweep(self) -> dict:
        at, started = utcnow(), time.monotonic()
        self.sweeps += 1
        self.budget.start_sweep()
        before = dict(self.http.source_calls)
        sources = self.th["sources"]
        per_call, feed = sources["snapshot_symbols_per_call"], sources["overnight_feed"]
        chunks = [self.symbols[i:i + per_call] for i in range(0, len(self.symbols), per_call)]
        results = [None] * len(chunks)

        def fetch(k: int) -> None:
            try:
                body = self.http.alpaca_json(M.DATA, "/v2/stocks/snapshots", {"symbols": ",".join(chunks[k]), "feed": feed})
                results[k] = ("ok", body.get("snapshots", body))
            except Exception as exc:   # recorded per chunk; the other chunks still run
                results[k] = ("error", f"{type(exc).__name__}: {str(exc)[:160]}")

        fetch(0)   # its response refreshes the rate-limit reading the floor needs
        spare, remaining = data_floor(self.http)
        if spare and len(chunks) > 1:
            with ThreadPoolExecutor(max_workers=SNAPSHOT_WORKERS) as pool:
                list(pool.map(fetch, range(1, len(chunks))))
        snaps, statuses = {}, []
        for k, chunk in enumerate(chunks):
            status, value = results[k] or ("skipped_ratelimit_floor", None)
            entry = {"i": k, "symbols": len(chunk), "status": status}
            if status == "ok":
                entry["returned"] = len(value)
                snaps.update(value)
            elif status == "error":
                entry["error"] = value
            statuses.append(entry)
        rows, session = [], {}
        for symbol, snap in snaps.items():
            row = measures(symbol, snap or {}, self.trade_date, self.ctx, at, fund=bool(M.FUND_NAME.search(self.names.get(symbol, ""))))
            if row is not None:
                rows.append(row)
                session[symbol] = snap
        significant = by_dollar_volume([r for r in rows if qualifies(r, self.th["significant"])])
        notify = [r for r in rows if qualifies(r, self.th["notify"])]
        records = self.alerts.cross(rows, iso(at), dry_run=self.dry_run, push=self.push_enabled)
        for record in records:
            self.sink.write("alerts", record)
        pushes = self.push(rows, at)
        lists = [{"by": spec["by"], "n": spec["n"], "rows": top_n(rows, spec)} for spec in self.th["top_n"]]
        self.sink.write("top", {"at": iso(at), "sweep": self.sweeps, "lists": lists})
        probe = ((snaps.get(ROLL_PROBE) or {}).get("dailyBar") or {}).get("t")
        if probe is not None:
            if self.roll_t is not None and probe != self.roll_t:
                self.sink.write("sweeps", {"event": "session_bar_rolled", "at": iso(at), "symbol": ROLL_PROBE, "from": self.roll_t, "to": probe})
            self.roll_t = probe
        self.sink.replace(f"snapshots/{at.astimezone(M.ET):%H%M%S}.json.gz",
                          gzip.compress(json.dumps({"at": iso(at), "trade_date": str(self.trade_date), "feed": feed, "rows": session},
                                                   separators=(",", ":")).encode()))
        counts = {"with_overnight_volume": len(rows), "significant": len(significant), "notify": len(notify),
                  "notify_non_fund": sum(not r["fund"] for r in notify)}
        self.sink.replace("board.json", json.dumps({
            "at": iso(at), "id": self.th["id"], "trade_date": str(self.trade_date), "sweep": self.sweeps, "ref_session": str(self.ref_session),
            "counts": counts, "significant_now": significant, "top": {entry["by"]: entry["rows"] for entry in lists},
            "alerted": {tier: len(self.alerts.alerted[tier]) for tier in TIERS}, "pushes": dict(self.pushes)}, indent=1).encode())
        record = {"event": "sweep", "sweep": self.sweeps, "at": iso(at), "symbols": len(self.symbols), "chunks": statuses,
                  "calls": {k: v - before.get(k, 0) for k, v in self.http.source_calls.items() if v - before.get(k, 0)},
                  "ratelimit_remaining": self.http.data_remaining(), "ratelimit_floor": None if spare else remaining, **counts,
                  "new_alerts": {tier: sum(r["tier"] == tier for r in records) for tier in TIERS}, "pushes": pushes,
                  "roll_probe": probe, "seconds": round(time.monotonic() - started, 2)}
        self.sink.write("sweeps", record)
        self.last = record
        return record

    def push(self, rows: list[dict], at: datetime) -> dict:
        """Post the due notify names (best effort): every attempt is recorded, and a failure never stops the sweep."""
        current, done = {r["s"]: r for r in rows}, {"sent": 0, "failed": 0}
        for symbol in self.alerts.due():
            row = current.get(symbol) or self.alerts.rows.get(symbol) or {"s": symbol}
            text = notice_text(row, self.ref_session, at, self.th["notify"]["relvol_min_prior_sessions"])
            self.alerts.record_push(symbol)
            record = {"event": "push", "at": iso(at), "s": symbol, "message": text}
            try:
                self.send(self.notify_url, text)
                record["status"] = "sent"
            except Exception as exc:
                record.update(status="failed", error=f"{type(exc).__name__}: {str(exc)[:160]}")
            done[record["status"]] += 1
            self.sink.write("alerts", record)
        for key, value in done.items():
            self.pushes[key] += value
        return done

    def finish(self, reason: str, code: int = 0, refused: list[str] | None = None, error: str | None = None,
               detail: dict | None = None) -> int:
        record = {"event": "stop", "at": iso(utcnow()), "reason": reason, "sweeps": self.sweeps,
                  "alerts": {tier: len(self.alerts.alerted[tier]) for tier in TIERS}, "pushes": dict(self.pushes),
                  "calls": dict(self.http.source_calls) if self.http else {}, "sweep_errors": self.errors,
                  "refused": refused, "detail": detail, "error": error}
        self.sink.replace("stop.json", json.dumps(record, indent=1).encode())
        self.sink.write("sweeps", record)
        self.sink.close()
        print(json.dumps(self.summary(record), sort_keys=True), flush=True)
        return code

    def summary(self, stop: dict) -> dict:
        """Counts only: no symbol, price or credential."""
        last = self.last or {}
        chunks = last.get("chunks") or []
        return {"mode": self.mode, "id": self.th["id"], "trade_date": str(self.trade_date), "reason": stop["reason"],
                "refused": stop["refused"], "error": stop["error"], "sweeps": self.sweeps, "symbols_swept": last.get("symbols", 0),
                "calls": stop["calls"], "calls_total": sum(stop["calls"].values()),
                "chunks_ok": sum(c["status"] == "ok" for c in chunks), "chunks_failed": sum(c["status"] == "error" for c in chunks),
                "chunks_skipped": sum(c["status"].startswith("skipped") for c in chunks),
                "with_overnight_volume": last.get("with_overnight_volume", 0), "significant": last.get("significant", 0),
                "notify": last.get("notify", 0), "notify_non_fund": last.get("notify_non_fund", 0),
                "alerted": stop["alerts"], "pushes": stop["pushes"],
                "prior_session": str(self.ref_session) if self.ref_session else None,
                "data_ratelimit_remaining": self.http.data_remaining() if self.http else None,
                "seconds": round(time.monotonic() - self.t0, 1), "python": sys.version.split()[0]}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("plan", "once", "run"),
                    help="plan: the call plan, no network; once: a dry run (alias --once); run: until 04:00 ET on the trade date")
    ap.add_argument("--env-file", type=Path, help='the 0600 PAPER key file (pass "$PAPER_ENV_FILE")')
    ap.add_argument("--out", type=Path, help="one fixed output directory for the trade date (owner-only)")
    ap.add_argument("--thresholds", type=Path, default=THRESHOLDS_PATH)
    ap.add_argument("--trade-date", help="must equal the thresholds file's trade date")
    ap.add_argument("--symbols", type=int, help="plan: the universe size")
    ap.add_argument("--no-push", action="store_true", help="run: record notify alerts without posting them")
    return ap


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--once" in argv:   # the dry-run alias
        argv.remove("--once")
        argv.insert(0, "once")
    ap = parser()
    args = ap.parse_args(argv)
    if args.mode == "plan":
        if args.symbols is None:
            ap.error("plan needs --symbols")
        plan = plan_calls(args.symbols, load_thresholds(args.thresholds)["sources"])
        print(json.dumps(plan, sort_keys=True))
        return 2 if plan["refusals"] else 0
    if args.env_file is None or args.out is None:
        ap.error(f"{args.mode} needs --env-file and --out")
    try:
        watch = Watch(args)
    except UsageError as exc:
        print(f"watch: {exc}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.out, 0o700)
    previous = {s: signal.signal(s, lambda signum, frame: watch.request_stop(signal.Signals(signum).name.lower()))
                for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        return watch.execute()
    finally:
        for s, handler in previous.items():
            signal.signal(s, handler)


if __name__ == "__main__":
    raise SystemExit(main())
