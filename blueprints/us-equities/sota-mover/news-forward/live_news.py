"""Read-only Alpaca market-data client and the 15-second news poller.

Only GET requests to an explicit allow-list are possible: market data on
https://data.alpaca.markets (news, daily bars, latest quotes, snapshots, auctions) and the
asset master (GET /v2/assets) on https://paper-api.alpaca.markets. No order, position or
account path is reachable through this client. Requests are spaced to at most
300 per minute in total (one shared limiter).
"""

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import timedelta

import common

DATA_HOST = "https://data.alpaca.markets"
PAPER_HOST = "https://paper-api.alpaca.markets"
NEWS_PATH = "/v1beta1/news"
BARS_PATH = "/v2/stocks/bars"
LATEST_QUOTES_PATH = "/v2/stocks/quotes/latest"
SNAPSHOTS_PATH = "/v2/stocks/snapshots"
AUCTIONS_PATH = "/v2/stocks/auctions"  # official opening/closing auction prints (the study's exit price source)
ASSETS_PATH = "/v2/assets"
ALLOWED = {
    (DATA_HOST, NEWS_PATH),
    (DATA_HOST, BARS_PATH),
    (DATA_HOST, LATEST_QUOTES_PATH),
    (DATA_HOST, SNAPSHOTS_PATH),
    (DATA_HOST, AUCTIONS_PATH),
    (PAPER_HOST, ASSETS_PATH),
}
ASSET_ONE = re.compile(r"^/v2/assets/[A-Z]{1,5}(?:\.[A-Z])?$")
MAX_RATE_PER_MIN = 300
MAX_RETRIES = 5
POLL_SECONDS = 15
_CRED = re.compile(r"^\s*(?:export\s+)?(APCA_API_KEY_ID|APCA_API_SECRET_KEY)=(['\"]?)([A-Za-z0-9]+)\2\s*$")


class CredentialError(RuntimeError):
    """Credential file refused; the message never carries a path or a secret."""


def read_credentials(path):
    """Guarded literal parse of the two APCA variables (credential_guard.open_verified)."""
    guard = common.credential_guard()
    try:
        with guard.open_verified(path, follow_symlinks=False) as handle:
            raw = handle.read(64 * 1024 + 1)
    except guard.CredentialGuardError as error:
        raise CredentialError(str(error)) from None
    if len(raw) > 64 * 1024:
        raise CredentialError("credential_file:size")
    found = {}
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        raise CredentialError("credential_file:encoding") from None
    for line in text.splitlines():
        m = _CRED.match(line)
        if m:
            found[m.group(1)] = m.group(3)
    if set(found) != {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"}:
        raise CredentialError("credential_file:missing_apca_variables")
    return found["APCA_API_KEY_ID"], found["APCA_API_SECRET_KEY"]


class RateLimiter:
    def __init__(self, per_min=MAX_RATE_PER_MIN, clock=time.monotonic, sleep=time.sleep):
        if not 1 <= per_min <= MAX_RATE_PER_MIN:
            raise ValueError("rate outside 1..300 per minute")
        self.interval = 60.0 / per_min
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.next_at = clock()

    def wait(self):
        with self.lock:
            now = self.clock()
            start = max(now, self.next_at)
            self.next_at = start + self.interval
        delay = start - self.clock()
        if delay > 0:
            self.sleep(delay)


def urllib_transport(url, headers, timeout=30):
    request = urllib.request.Request(url, headers={**headers, "User-Agent": "news-forward/1"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as error:
        return error.code, error.read()[:300], {k.lower(): v for k, v in (error.headers or {}).items()}


class DataClient:
    def __init__(self, key_id, secret, limiter=None, transport=urllib_transport, sleep=time.sleep):
        self._headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}
        self.limiter = limiter or RateLimiter()
        self.transport = transport
        self.sleep = sleep
        self.tally = Counter()
        self.lock = threading.Lock()

    def get(self, host, path, params=None):
        if (host, path) not in ALLOWED and not (host == PAPER_HOST and ASSET_ONE.match(path)):
            raise ValueError("endpoint not in the read-only allow-list")
        url = host + path + ("?" + urllib.parse.urlencode(params) if params else "")
        for attempt in range(MAX_RETRIES):
            self.limiter.wait()
            try:
                status, body, headers = self.transport(url, self._headers)
            except OSError as error:
                with self.lock:
                    self.tally[f"error:{type(error).__name__}"] += 1
                self.sleep(min(30, 2 ** attempt))
                continue
            with self.lock:
                self.tally[f"http_{status}"] += 1
                self.tally["requests"] += 1
            if status == 200:
                return json.loads(body)
            if status == 429 or status >= 500:
                self.sleep(min(30, 2 ** attempt))
                continue
            raise RuntimeError(f"HTTP {status} for {path}")
        raise RuntimeError(f"retries exhausted for {path}")

    # -- endpoints ---------------------------------------------------------------------

    def news_since(self, start_utc, end_utc=None, max_pages=200):
        """All articles with created_at >= start (ascending), following page tokens."""
        params = {"start": common.iso(start_utc), "sort": "asc", "limit": 50, "include_content": "false"}
        if end_utc is not None:
            params["end"] = common.iso(end_utc)
        out, token = [], None
        for _ in range(max_pages):
            query = dict(params)
            if token:
                query["page_token"] = token
            payload = self.get(DATA_HOST, NEWS_PATH, query)
            out.extend(payload.get("news") or [])
            token = payload.get("next_page_token")
            if not token:
                break
        return out

    def daily_bars(self, symbols, start_day, end_day, adjustment="raw"):
        """SIP daily bars per symbol for [start_day, end_day] (dates, New York); raw by default,
        "split" for the split-adjusted bars the study's Rule 201 carry-over uses."""
        if adjustment not in ("raw", "split"):
            raise ValueError("adjustment must be raw or split")
        out = {s: [] for s in symbols}
        for i in range(0, len(symbols), 100):
            chunk = symbols[i:i + 100]
            token = None
            while True:
                params = {"symbols": ",".join(chunk), "timeframe": "1Day", "start": start_day.isoformat(),
                          "end": end_day.isoformat(), "adjustment": adjustment, "feed": "sip", "limit": 10000}
                if token:
                    params["page_token"] = token
                payload = self.get(DATA_HOST, BARS_PATH, params)
                for sym, bars in (payload.get("bars") or {}).items():
                    out.setdefault(sym, []).extend(bars)
                token = payload.get("next_page_token")
                if not token:
                    break
        return out

    def latest_quotes(self, symbols):
        out = {}
        for i in range(0, len(symbols), 100):
            payload = self.get(DATA_HOST, LATEST_QUOTES_PATH, {"symbols": ",".join(symbols[i:i + 100]), "feed": "sip"})
            out.update(payload.get("quotes") or {})
        return out

    def snapshots(self, symbols):
        out = {}
        for i in range(0, len(symbols), 100):
            payload = self.get(DATA_HOST, SNAPSHOTS_PATH, {"symbols": ",".join(symbols[i:i + 100]), "feed": "sip"})
            out.update(payload if isinstance(payload, dict) else {})
        return out

    def auctions(self, symbols, day):
        """{symbol: {"o": [...], "c": [...]}} of one session's SIP auction entries (as the study's
        collect_auctions.fetch_auctions requests them), merged across pages; only entries dated `day`."""
        out = {}
        for i in range(0, len(symbols), 100):
            token = None
            while True:
                params = {"symbols": ",".join(symbols[i:i + 100]), "start": f"{day.isoformat()}T00:00:00Z",
                          "end": f"{day.isoformat()}T23:59:59Z", "limit": 10000, "feed": "sip", "sort": "asc"}
                if token:
                    params["page_token"] = token
                payload = self.get(DATA_HOST, AUCTIONS_PATH, params)
                for sym, days in (payload.get("auctions") or {}).items():
                    for d in days or []:
                        if d.get("d") != day.isoformat():
                            continue
                        slot = out.setdefault(sym, {"o": [], "c": []})
                        slot["o"].extend(d.get("o") or [])
                        slot["c"].extend(d.get("c") or [])
                token = payload.get("next_page_token")
                if not token:
                    break
        return out

    def assets(self):
        payload = self.get(PAPER_HOST, ASSETS_PATH, {"status": "active", "asset_class": "us_equity"})
        return {a["symbol"].upper(): a for a in payload}

    def asset(self, symbol):
        return self.get(PAPER_HOST, f"{ASSETS_PATH}/{symbol}")


class NewsPoller:
    """Ascending-watermark news polling; every article gets our own received_at.

    The watermark is the newest created_at seen; each poll re-reads from watermark - 10
    minutes (late-indexed stories) and keeps only unseen ids, in (created_at, id) order.
    received_at is the first time this runner received the id: `first_received` (news id ->
    ISO time, e.g. rebuilt from today's journal after a restart) keeps the original receipt
    time, so a restart does not make an article look late to guard B.
    """

    OVERLAP = timedelta(minutes=10)

    def __init__(self, client, start_utc, clock=common.utc_now, first_received=None):
        self.client = client
        self.watermark = start_utc
        self.clock = clock
        self.seen = set()
        self.first_received = dict(first_received or {})

    def poll(self):
        articles = self.client.news_since(self.watermark - self.OVERLAP)
        received = self.clock()  # stamped on the response (all pages in hand), never before the request
        fresh = []
        for a in articles:
            aid = str(a.get("id"))
            if aid in self.seen:
                continue
            self.seen.add(aid)
            a = dict(a)
            a["received_at"] = self.first_received.setdefault(aid, common.iso(received))
            fresh.append(a)
            try:
                created = common.news_signal().as_utc(a["created_at"])
                if created > self.watermark:
                    self.watermark = created
            except (KeyError, ValueError, TypeError):
                pass
        fresh.sort(key=lambda a: (a.get("created_at", ""), int(a["id"]) if str(a.get("id")).isdigit() else 0))
        return fresh
