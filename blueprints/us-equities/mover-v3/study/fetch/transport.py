"""Fetch transport only: HTTP client, authentication, pagination and retry (review round 8, R8-1).

This module receives one planned request (endpoint path and query parameters, built by core.plan from sealed
inputs) and returns the raw pages. It derives no symbol, asof, stamp or window, parses no row and filters
nothing: it reads only the envelope's next_page_token to paginate. A transport deviation
(run_discipline.transport_deviations) may change only this directory.

Retry (populations.fetch_failures): every page request is retried up to 3 times, waiting 1 s, 4 s and 16 s.
A page that still fails with an HTTP error, a URLError or a timeout ends the request as incomplete; the run
continues and nothing is raised.

Rate (review round 11, C2): every page request, the first and each retry, waits for its slot at the pinned
per-minute rate (exposure_registry.pre_freeze_access_path.rate_limit), one pacer shared by the data and trading
hosts. An HTTP 429 waits at least one full rate window (60 s) before its retry, so a rate-limit refusal is not
retried inside the window that refused it.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

HOST = "https://data.alpaca.markets"
TRADING_HOST = "https://paper-api.alpaca.markets"   # the asset master (GET /v2/assets) is a trading-API endpoint
RETRY_WAITS_S = (1, 4, 16)
RATE_WINDOW_S = 60
TIMEOUT_S = 60
MAX_PAGES = 100_000


def env_headers() -> dict:
    """Authentication headers from the environment (never logged, never written to a record)."""
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set for a live fetch")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def urllib_opener(url: str, headers: dict, timeout: float):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return r.status, r.read()


class Pacer:
    """Evenly spaced request slots at per_minute requests per minute (none: unpaced), shared across hosts."""

    def __init__(self, per_minute=None, sleep=time.sleep, monotonic=time.monotonic):
        self.gap = (60.0 / per_minute) if per_minute else 0.0
        self.sleep, self.monotonic, self.next_slot = sleep, monotonic, 0.0

    def wait(self):
        if self.gap:
            now = self.monotonic()
            slot = max(self.next_slot, now)
            self.next_slot = slot + self.gap
            if slot > now:
                self.sleep(slot - now)


class Transport:
    def __init__(self, opener=urllib_opener, headers=None, sleep=time.sleep, host=HOST, pacer=None):
        self.opener, self.headers, self.sleep, self.host = opener, headers, sleep, host
        self.pacer = pacer or Pacer(None, sleep)

    def _headers(self) -> dict:
        if self.headers is None:
            self.headers = env_headers()
        return self.headers

    def _throttle(self):
        self.pacer.wait()

    def _page(self, url: str):
        """(status, raw, error) for one page after at most len(RETRY_WAITS_S) retries."""
        error = None
        for attempt in range(len(RETRY_WAITS_S) + 1):
            self._throttle()
            code = None
            try:
                status, raw = self.opener(url, self._headers(), TIMEOUT_S)
                if status == 200:
                    return status, raw, None
                code, error = status, f"HTTP {status}"
            except urllib.error.HTTPError as exc:
                code, error = exc.code, f"HTTP {exc.code}"
            except urllib.error.URLError as exc:
                error = f"URLError {type(exc.reason).__name__}"
            except (TimeoutError, socket.timeout):
                error = "timeout"
            if attempt < len(RETRY_WAITS_S):
                wait = RETRY_WAITS_S[attempt]
                self.sleep(max(wait, RATE_WINDOW_S) if code == 429 else wait)
        return None, b"", error

    def get(self, endpoint: str, params: dict) -> dict:
        """Every page of one request: {"pages": [raw bytes, ...], "complete": bool, "error": str | None}."""
        pages, token = [], None
        for _ in range(MAX_PAGES):
            q = dict(params, **({"page_token": token} if token else {}))
            url = self.host + endpoint + "?" + urllib.parse.urlencode(sorted(q.items()))
            status, raw, error = self._page(url)
            if status != 200:
                return {"pages": pages, "complete": False, "error": error}
            pages.append(raw)
            try:
                body = json.loads(raw) if raw else {}
            except ValueError:
                return {"pages": pages, "complete": False, "error": "unparsable envelope"}
            token = body.get("next_page_token") if isinstance(body, dict) else None
            if not token:
                return {"pages": pages, "complete": True, "error": None}
        return {"pages": pages, "complete": False, "error": "page limit"}
