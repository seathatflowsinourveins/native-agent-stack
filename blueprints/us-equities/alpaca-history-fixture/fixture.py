#!/usr/bin/env python3
"""Alpaca historical-data fixture runner for protocol.json (alpaca-history-fixture-v1-20260925).

  plan      Offline. Builds the fixtures from repository files and the private inputs, checks every
            pin and count, and prints a sanitized summary with the planned request count. No network,
            no keys.
  run       Reads APCA_API_KEY_ID and APCA_API_SECRET_KEY from the environment only (use
            `secret run APCA_API_KEY_ID APCA_API_SECRET_KEY -- ...`), sends HTTPS GET requests to
            data.alpaca.markets on /v2/stocks/bars and /v2/stocks/auctions only, writes the private
            snapshot and details, then the sanitized public receipt.
  evaluate  Recomputes details and receipt from a snapshot alone. The same snapshot and inputs give
            byte-identical output.

Standard library only. Every other host, path, method and every redirect is refused, so no trading,
order, account, position or asset endpoint can be reached.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL_PATH = HERE / "protocol.json"
GATES_PATH = ROOT / "catalogs/us-equities/gates-20260922.json"
DELISTING_ARTIFACT = ROOT / "evidence/artifacts/pre-2020-delisting/classifications-2016-2019.json"
AUDIT_SUMMARY_B = ROOT / "blueprints/us-equities/extreme-gainer-audit/evidence/summary-run-20260924b.json"
AUDIT_PLAN = ROOT / "blueprints/us-equities/extreme-gainer-audit/plan.json"

DATA_HOST = "data.alpaca.markets"
DATA_BASE = "https://" + DATA_HOST
ALLOWED_PATHS = frozenset({"/v2/stocks/bars", "/v2/stocks/auctions"})
KEY_NAMES = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")
YEARS = ("2016", "2017", "2018", "2019")
GATE_IDS = ("pre-2020-delisting", "dated-security-identity")
MAX_RETRIES = 5
MAX_PAGES = 1000
MAX_BODY = 32 * 1024 * 1024
TIMEOUT_S = 30
SOURCE_NAME = "alpaca-market-data-sip-daily"


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load("alpaca_fixture_gainer_audit", "blueprints/us-equities/extreme-gainer-audit/audit.py")
COLLECT = _load("alpaca_fixture_collect_daily", "blueprints/us-equities/broad-universe/collect_daily.py")
PATH_SAFETY = _load("alpaca_fixture_path_safety", "scripts/path_safety.py")


class FixtureError(Exception):
    """An input, pin or output check failed; nothing is fetched or written past this point."""


class RefusedRequest(FixtureError):
    """A request outside the data host, the two allowed paths or GET, or a redirect."""


class AbortRun(FixtureError):
    """The run stops: HTTP 401/403, the request ceiling, or a missing session calendar."""


# ----------------------------------------------------------------------------- small helpers

def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=1, ensure_ascii=True, allow_nan=False) + "\n").encode()


def safe_path(path) -> Path:
    try:
        return PATH_SAFETY.refuse_untrusted_symlinks(path, "symlink or parent traversal refused")
    except ValueError as exc:
        raise FixtureError(str(exc)) from None


def read_input(path) -> bytes:
    path = safe_path(path)
    if not path.is_file():
        raise FixtureError(f"input is not a file: {path.name}")
    return path.read_bytes()


def day(text: str) -> date:
    return date.fromisoformat(text)


def shift(text: str, days: int) -> str:
    return (day(text) + timedelta(days=days)).isoformat()


def load_protocol() -> tuple[dict, str]:
    raw = PROTOCOL_PATH.read_bytes()
    return json.loads(raw), sha256_bytes(raw)


def runner_sha256() -> str:
    return sha256_bytes(Path(__file__).resolve().read_bytes())


# ----------------------------------------------------------------------------- pins

def check_gates(protocol: dict, gates_path: Path = GATES_PATH) -> None:
    """The gates' frozen definitions must still read as the protocol copied them."""
    live = {g["id"]: g for g in json.loads(gates_path.read_text(encoding="utf-8"))["gates"]}
    for gate_id in GATE_IDS:
        frozen, current = protocol["gates"][gate_id], live.get(gate_id)
        if current is None:
            raise FixtureError(f"gate {gate_id} is missing from the gates file")
        for field in ("title", "receipt_path", "flip_condition"):
            if current.get(field) != frozen[field]:
                raise FixtureError(f"gate {gate_id}: {field} differs from the frozen protocol copy")


def check_repo_pins(protocol: dict) -> None:
    owed = protocol["fixtures"]["audit_owed_rows"]
    if sha256_bytes(AUDIT_PLAN.read_bytes()) != owed["audit_plan_sha256"]:
        raise FixtureError("extreme-gainer-audit/plan.json differs from the protocol pin")
    if sha256_bytes(AUDIT_SUMMARY_B.read_bytes()) != owed["summary_sha256"]:
        raise FixtureError("summary-run-20260924b.json differs from the protocol pin")
    check_gates(protocol)


# ----------------------------------------------------------------------------- fixtures

def build_delistings(protocol: dict, artifact: Path = DELISTING_ARTIFACT) -> list[dict]:
    spec = protocol["fixtures"]["delistings"]
    raw = artifact.read_bytes()
    if sha256_bytes(raw) != spec["source_sha256"]:
        raise FixtureError("delisting classification artifact differs from the protocol pin")
    rows = sorted(({"accession": d["accession"], "cik": d["cik"], "date_filed": d["date_filed"],
                    "year": d["date_filed"][:4]}
                   for d in json.loads(raw)["documents"]
                   if d.get("security_class") == "common_ordinary_equity" and d.get("date_filed", "")[:4] in YEARS),
                  key=lambda r: (r["date_filed"], r["accession"]))
    by_year = Counter(r["year"] for r in rows)
    if dict(sorted(by_year.items())) != spec["expected_rows_by_year"] or len(rows) != spec["expected_rows"]:
        raise FixtureError(f"delisting rows by year {dict(sorted(by_year.items()))} differ from the protocol")
    digest = sha256_bytes("\n".join(r["accession"] for r in rows).encode())
    if digest != spec["filing_ids_sha256"]:
        raise FixtureError("delisting accession list differs from the protocol pin")
    return rows


def load_ticker_map(protocol: dict, path, rows: list[dict]) -> tuple[dict, str]:
    spec = protocol["fixtures"]["delistings"]["ticker_map"]
    raw = read_input(path)
    try:
        doc = json.loads(raw)
    except ValueError:
        raise FixtureError("ticker map is not valid JSON") from None
    if not isinstance(doc, dict) or doc.get("schema") != spec["schema"] or not isinstance(doc.get("rows"), dict):
        raise FixtureError("ticker map schema differs from the protocol")
    accessions = {r["accession"] for r in rows}
    pit, non_pit = set(spec["pit_provenance"]), set(spec["non_pit_provenance"])
    out = {}
    for accession in sorted(doc["rows"]):
        entry = doc["rows"][accession]
        if accession not in accessions:
            raise FixtureError("ticker map names an accession outside the fixture")
        if not isinstance(entry, dict):
            raise FixtureError("ticker map row is not an object")
        symbol, provenance = entry.get("symbol"), entry.get("provenance")
        if not isinstance(symbol, str) or not COLLECT.DATA_SYMBOL.match(symbol):
            raise FixtureError("ticker map row has an invalid symbol")
        if provenance not in pit | non_pit:
            raise FixtureError("ticker map row has a provenance class the protocol does not accept")
        if not isinstance(entry.get("source_ref"), str) or not entry["source_ref"].strip():
            raise FixtureError("ticker map row lacks source_ref")
        out[accession] = {"symbol": symbol, "provenance": provenance, "pit": provenance in pit}
    return out, sha256_bytes(raw)


def build_collisions(protocol: dict, asset_files=None, identities_file=None) -> tuple[dict, dict]:
    expected = protocol["fixtures"]["collisions"]["expected"]
    if asset_files:
        paths = [str(safe_path(p)) for p in asset_files]
        symbols, _identities, collisions, skipped = COLLECT.select_symbols(paths)
        if len(symbols) != expected["symbols"] or len(collisions) != expected["collisions"] or skipped != expected["excluded"]:
            raise FixtureError(f"asset master gives {len(symbols)} symbols, {len(collisions)} collisions and "
                               f"exclusions {skipped}; the protocol requires {expected}")
        kind = "asset_master"
    elif identities_file:
        doc = json.loads(read_input(identities_file))
        identities, collisions = doc.get("identities") or {}, doc.get("collisions") or {}
        if len(identities) != expected["symbols"] or len(collisions) != expected["collisions"]:
            raise FixtureError(f"symbol identities give {len(identities)} symbols and {len(collisions)} collisions; "
                               f"the protocol requires {expected['symbols']} and {expected['collisions']}")
        if any(len(v) < 2 or identities.get(s) != v for s, v in collisions.items()):
            raise FixtureError("symbol identities: a collision disagrees with its identity entry")
        kind = "symbol_identities"
    else:
        raise FixtureError("no collision source supplied")
    canonical_set = {s: sorted(json.dumps(e, sort_keys=True) for e in v) for s, v in collisions.items()}
    fixture = {s: {"asset_ids": len(v), "status_pattern": "+".join(sorted(str(e.get("status")) for e in v))}
               for s, v in sorted(collisions.items())}
    meta = {"source_kind": kind, "count": len(fixture), "collision_set_sha256": sha256_bytes(canonical(canonical_set))}
    return fixture, meta


def package_events(package_dir) -> list[dict]:
    package_dir = safe_path(package_dir)
    try:
        AUDIT.check_inputs(package_dir)
    except SystemExit as exc:
        raise FixtureError(f"package inputs differ from extreme-gainer-audit/plan.json ({exc})") from None
    return AUDIT.load_events(package_dir)


def build_reused(protocol: dict, events: list[dict]) -> list[dict]:
    out = []
    for ticker in protocol["fixtures"]["reused_tickers"]["tickers"]:
        rows = [e for e in events if e["ticker"] == ticker]
        if len(rows) != 1 or rows[0]["computed_gain"] is None or rows[0]["dataset_gain"] is None:
            raise FixtureError(f"reused ticker {ticker}: expected exactly one row with both package gains")
        out.append(rows[0])
    return out


def build_owed(protocol: dict, events: list[dict], results_path) -> tuple[list[dict], str]:
    spec = protocol["fixtures"]["audit_owed_rows"]
    raw = read_input(results_path)
    digest = sha256_bytes(raw)
    if digest != spec["results_sha256"]:
        raise FixtureError("audit results file differs from the protocol pin (private_results_sha256 of run-20260924b)")
    doc = json.loads(raw)
    summary_b = json.loads(AUDIT_SUMMARY_B.read_text(encoding="utf-8"))
    if doc.get("plan_sha256") != spec["audit_plan_sha256"] or doc.get("rules") != "v2" \
            or (doc.get("summary") or {}).get("verdicts") != summary_b["summary"]["verdicts"]:
        raise FixtureError("audit results do not match the committed run-20260924b summary")
    wanted = {k: v for k, v in spec["expected"].items() if k != "total"}
    by_id = {e["id"]: e for e in events}
    items = []
    for row in doc.get("events") or []:
        if row.get("verdict") not in wanted:
            continue
        event = by_id.get(row.get("id"))
        if event is None or not row.get("symbol_used") or row.get("alpaca_gain_pct") is None \
                or row.get("package_gain_pct") is None:
            raise FixtureError("an owed audit row lacks its event, symbol or gains")
        items.append({"id": row["id"], "date": event["date"], "ticker": event["ticker"], "symbol": row["symbol_used"],
                      "audit_verdict": row["verdict"], "audit_gain": row["alpaca_gain_pct"],
                      "package_gain": row["package_gain_pct"]})
    counts = dict(Counter(i["audit_verdict"] for i in items))
    if counts != wanted or len(items) != spec["expected"]["total"]:
        raise FixtureError(f"owed audit rows {counts} differ from the protocol's {wanted}")
    return sorted(items, key=lambda i: (i["date"], i["id"])), digest


def build_fixtures(protocol: dict, args) -> tuple[dict, dict]:
    """Every fixture the supplied inputs allow, plus the sanitized input metadata."""
    rows = build_delistings(protocol)
    fixtures = {"delistings": rows, "ticker_map": {}, "collisions": None, "reused": None, "owed": None}
    meta = {"delisting_artifact_sha256": protocol["fixtures"]["delistings"]["source_sha256"],
            "ticker_map": {"supplied": False}, "collisions": {"supplied": False},
            "package": {"supplied": False}, "audit_results": {"supplied": False}}
    if args.delisting_tickers:
        tickers, digest = load_ticker_map(protocol, args.delisting_tickers, rows)
        fixtures["ticker_map"] = tickers
        meta["ticker_map"] = {"supplied": True, "sha256": digest, "rows": len(tickers),
                              "pit_rows": sum(1 for t in tickers.values() if t["pit"])}
    if args.asset_master or args.symbol_identities:
        if args.asset_master and args.symbol_identities:
            raise FixtureError("give --asset-master or --symbol-identities, not both")
        fixtures["collisions"], collision_meta = build_collisions(protocol, args.asset_master, args.symbol_identities)
        meta["collisions"] = {"supplied": True, **collision_meta}
    if args.audit_results and not args.package_dir:
        raise FixtureError("--audit-results needs --package-dir")
    if args.package_dir:
        events = package_events(args.package_dir)
        fixtures["reused"] = build_reused(protocol, events)
        meta["package"] = {"supplied": True, "forward_returns_csv_sha256": AUDIT.PLAN["inputs"]["forward_returns_csv"]["sha256"],
                           "alias_map_csv_sha256": AUDIT.PLAN["inputs"]["alias_map_csv"]["sha256"]}
        if args.audit_results:
            fixtures["owed"], digest = build_owed(protocol, events, args.audit_results)
            meta["audit_results"] = {"supplied": True, "sha256": digest, "rows": len(fixtures["owed"])}
    return fixtures, meta


# ----------------------------------------------------------------------------- requests

def bars_request(protocol: dict, symbol: str, start: str, end: str, adjustment: str, asof) -> tuple[str, dict]:
    req = protocol["data_request"]
    params = {"symbols": symbol, "timeframe": req["timeframe"], "adjustment": adjustment, "feed": req["feed"],
              "start": start, "end": end, "limit": str(req["page_limit"]), "sort": req["sort"]}
    if asof is not None:
        params["asof"] = asof
    return "/v2/stocks/bars", params


def auctions_request(protocol: dict, symbol: str, start: str, end: str, asof) -> tuple[str, dict]:
    req = protocol["data_request"]
    params = {"symbols": symbol, "feed": req["feed"], "start": start, "end": end,
              "limit": str(req["page_limit"]), "sort": req["sort"]}
    if asof is not None:
        params["asof"] = asof
    return "/v2/stocks/auctions", params


def request_key(path: str, params: dict) -> str:
    return path + "?" + urllib.parse.urlencode(sorted(params.items()))


def checked_url(path: str, params: dict) -> str:
    """The only way a URL is built: fixed https base, allowed path, no credentials or port."""
    if path not in ALLOWED_PATHS:
        raise RefusedRequest(f"path refused: {path}")
    url = DATA_BASE + request_key(path, params)
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != DATA_HOST or parts.port is not None
            or parts.username or parts.password or parts.path != path or parts.fragment):
        raise RefusedRequest("host or URL refused")
    return url


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - urllib hook
        raise RefusedRequest("redirect refused")


_OPENER = urllib.request.build_opener(_RefuseRedirect)


def default_transport(url: str, headers: dict, timeout: float):
    """(status, headers, body). Certificate checks use Python's default context."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != DATA_HOST:
        raise RefusedRequest("host refused")
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(65536)
        except OSError:
            body = b""
        return exc.code, dict((exc.headers or {}).items()), body


def keys_from_env(environ=None) -> tuple[str, str]:
    environ = os.environ if environ is None else environ
    key, secret = (environ.get(name, "") for name in KEY_NAMES)
    if not key.strip() or not secret.strip():
        raise FixtureError("APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set in the environment; run under "
                           "`secret run APCA_API_KEY_ID APCA_API_SECRET_KEY -- ...`")
    return key, secret


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DataClient:
    """Sequential GET client with the protocol's rate budget, headroom rule and backoff."""

    def __init__(self, key_id: str, secret: str, protocol: dict, transport=None, clock=None, sleep=None, wall=None):
        budget = protocol["rate_budget"]
        self._headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret, "Accept": "application/json"}
        self._transport = transport or default_transport
        self._clock, self._sleep, self._wall = clock or time.monotonic, sleep or time.sleep, wall or time.time
        self.cap = int(budget["client_cap_per_minute"])
        self.ceiling = int(budget["request_ceiling"])
        self._sent = deque()
        self.requests = 0
        self.retries = 0
        self.status_counts = Counter()
        self.rate_limit_header = None

    def _acquire(self) -> None:
        if self.requests >= self.ceiling:
            raise AbortRun("request ceiling reached")
        now = self._clock()
        while self._sent and now - self._sent[0] >= 60:
            self._sent.popleft()
        while len(self._sent) >= self.cap:
            self._sleep(max(0.001, 60 - (now - self._sent[0])))
            now = self._clock()
            while self._sent and now - self._sent[0] >= 60:
                self._sent.popleft()
        gap = 60.0 / self.cap
        if self._sent and now - self._sent[-1] < gap:
            self._sleep(gap - (now - self._sent[-1]))
            now = self._clock()
        self._sent.append(now)
        self.requests += 1

    def _observe(self, headers: dict) -> None:
        limit = _number(headers.get("x-ratelimit-limit"))
        if limit and limit > 0:
            limit = int(limit)
            self.rate_limit_header = limit if self.rate_limit_header is None else min(self.rate_limit_header, limit)
            self.cap = max(1, min(self.cap, limit // 2))
            remaining, reset = _number(headers.get("x-ratelimit-remaining")), _number(headers.get("x-ratelimit-reset"))
            if remaining is not None and reset is not None and remaining <= max(1, limit * 0.05):
                wait = min(60.0, reset - self._wall())
                if wait > 0:
                    self._sleep(wait)

    def _backoff(self, status, headers: dict, attempt: int) -> float:
        wait = None
        if status == 429:
            wait = _number(headers.get("retry-after"))
            if wait is None and _number(headers.get("x-ratelimit-reset")) is not None:
                wait = _number(headers.get("x-ratelimit-reset")) - self._wall()
        if wait is None:
            wait = 2.0 ** attempt
        return min(60.0, max(1.0, wait))

    def _send(self, url: str):
        for attempt in range(MAX_RETRIES + 1):
            self._acquire()
            try:
                status, headers, body = self._transport(url, self._headers, TIMEOUT_S)
            except RefusedRequest:
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                status, headers, body = None, {}, b""
            headers = {str(k).lower(): v for k, v in (headers or {}).items()}
            self.status_counts[str(status)] += 1
            self._observe(headers)
            if status == 200:
                if body is None or len(body) > MAX_BODY:
                    return "oversized", None
                return status, body
            if status in (401, 403):
                raise AbortRun(f"HTTP {status}: the data API refused the credentials or the entitlement")
            if status in (400, 404, 422):
                return status, None
            if (status is None or status == 429 or status >= 500) and attempt < MAX_RETRIES:
                self.retries += 1
                self._sleep(self._backoff(status, headers, attempt))
                continue
            return status, None
        return None, None

    def fetch(self, path: str, params: dict) -> dict:
        field = "auctions" if path.endswith("/auctions") else "bars"
        symbol = params["symbols"]
        items, token, seen, pages, other = [], None, set(), 0, 0
        while True:
            query = dict(params, **({"page_token": token} if token else {}))
            status, body = self._send(checked_url(path, query))
            if body is None:
                return {"status": "error", "http": status}
            try:
                doc = json.loads(body)
            except ValueError:
                return {"status": "error", "http": "malformed_json"}
            data = doc.get(field) if isinstance(doc, dict) else None
            if data is None:
                data = {}
            if not isinstance(data, dict):
                return {"status": "error", "http": "unexpected_shape"}
            items.extend(data.get(symbol) or [])
            other += sum(1 for k in data if k != symbol)
            pages += 1
            token = doc.get("next_page_token")
            if not token:
                out = {"status": "ok", "items": items, "pages": pages}
                if other:
                    out["other_symbol_keys"] = other
                return out
            if token in seen or pages >= MAX_PAGES:
                return {"status": "error", "http": "pagination"}
            seen.add(token)


class _Source:
    def __init__(self, protocol: dict):
        self.protocol = protocol

    def bars(self, symbol, start, end, adjustment, asof):
        return self.get(*bars_request(self.protocol, symbol, start, end, adjustment, asof))

    def auctions(self, symbol, start, end, asof):
        return self.get(*auctions_request(self.protocol, symbol, start, end, asof))


class LiveSource(_Source):
    def __init__(self, protocol: dict, client: DataClient):
        super().__init__(protocol)
        self.client = client
        self.responses = {}

    def get(self, path, params):
        key = request_key(path, params)
        if key not in self.responses:
            self.responses[key] = self.client.fetch(path, params)
        return self.responses[key]


class SnapshotSource(_Source):
    def __init__(self, protocol: dict, responses: dict):
        super().__init__(protocol)
        self.responses = responses

    def get(self, path, params):
        key = request_key(path, params)
        if key not in self.responses:
            raise FixtureError("the snapshot lacks a request this protocol needs")
        return self.responses[key]


# ----------------------------------------------------------------------------- measurements

def item_date(item: dict) -> str:
    return item.get("d") or str(item.get("t", ""))[:10]


def session_calendar(protocol: dict, source) -> list[str]:
    req = protocol["data_request"]
    resp = source.bars("SPY", req["history_floor"], req["window_end"], "raw", None)
    if resp["status"] != "ok" or not resp["items"]:
        raise AbortRun("the SPY session calendar is unavailable")
    return sorted({item_date(b) for b in resp["items"]})


def classify_delisting(filed: str, resp: dict, sessions: list[str]) -> dict:
    if resp["status"] != "ok":
        return {"verdict": "fetch_error"}
    dates = sorted({item_date(b) for b in resp["items"]})
    if not dates:
        return {"verdict": "no_bars"}
    s_f = bisect.bisect_left(sessions, filed)
    if s_f >= len(sessions):
        raise FixtureError("filing date lies beyond the session calendar")
    after = sessions[min(s_f + 10, len(sessions) - 1)]
    first = max(0, s_f - 251)
    window = sessions[first:s_f + 1]
    out = {"first_bar": dates[0], "last_bar": dates[-1], "clipped": s_f - 251 < 0}
    if dates[-1] > after:
        return {**out, "verdict": "bars_continue_after_event"}
    recent_floor = shift(filed, -60)
    if not any(recent_floor <= d <= filed for d in dates):
        return {**out, "verdict": "no_recent_bars"}
    in_window = set(window)
    bars_in_window = sum(1 for d in dates if d in in_window)
    out["bars_in_window"] = bars_in_window
    if bars_in_window < min(20, len(window)):
        return {**out, "verdict": "thin_window"}
    lo, hi = max(window[0], dates[0]), dates[-1]
    span = sessions[bisect.bisect_left(sessions, lo):bisect.bisect_right(sessions, hi)]
    have = set(dates)
    completeness = (sum(1 for s in span if s in have) / len(span)) if span else 0.0
    out["completeness"] = round(completeness, 4)
    if completeness < 0.90:
        return {**out, "verdict": "incomplete_window"}
    return {**out, "verdict": "covered"}


def measure_delistings(protocol: dict, rows: list[dict], tickers: dict, sessions: list[str], source) -> list[dict]:
    floor = protocol["data_request"]["history_floor"]
    out = []
    for row in rows:
        entry = tickers.get(row["accession"])
        record = {"accession": row["accession"], "year": row["year"], "date_filed": row["date_filed"],
                  "symbol": entry["symbol"] if entry else None, "provenance": entry["provenance"] if entry else None,
                  "pit": bool(entry and entry["pit"])}
        if entry is None:
            record["raw"] = record["split"] = {"verdict": "no_symbol"}
        else:
            filed = row["date_filed"]
            start, end = max(shift(filed, -400), floor), shift(filed, 45)
            for adjustment in ("raw", "split"):
                record[adjustment] = classify_delisting(
                    filed, source.bars(entry["symbol"], start, end, adjustment, filed), sessions)
        out.append(record)
    return out


def segment_dates(dates: list[str], sessions: list[str], gap: int = 10) -> list[list[str]]:
    if not dates:
        return []
    index = {s: i for i, s in enumerate(sessions)}

    def position(d):
        return index[d] if d in index else bisect.bisect_left(sessions, d)

    segments, current = [], [dates[0]]
    for previous, current_date in zip(dates, dates[1:]):
        if position(current_date) - position(previous) - 1 > gap:
            segments.append(current)
            current = [current_date]
        else:
            current.append(current_date)
    segments.append(current)
    return segments


def bar_values(bar: dict) -> tuple:
    return tuple(bar.get(k) for k in ("o", "h", "l", "c", "v"))


def measure_collision(protocol: dict, symbol: str, info: dict, sessions: list[str], source) -> dict:
    req = protocol["data_request"]
    floor, end = req["history_floor"], req["window_end"]
    out = {"symbol": symbol, "asset_ids": info["asset_ids"], "status_pattern": info["status_pattern"],
           "dated_resolved": False, "security_type_provided": False, "resolved_frozen": False}
    literal = {adj: source.bars(symbol, floor, end, adj, "-") for adj in ("raw", "split")}
    if any(r["status"] != "ok" for r in literal.values()):
        return {**out, "reason": "fetch_error"}
    raw_by_date = {item_date(b): b for b in literal["raw"]["items"]}
    dates = sorted(raw_by_date)
    if not dates:
        return {**out, "reason": "no_bars"}
    segments = segment_dates(dates, sessions)
    split_segments = segment_dates(sorted({item_date(b) for b in literal["split"]["items"]}), sessions)
    out["segments"] = len(segments)
    out["split_segments_match"] = [(s[0], s[-1]) for s in segments] == [(s[0], s[-1]) for s in split_segments]
    probes = []
    for segment in segments:
        resp = source.bars(symbol, floor, end, "raw", segment[-1])
        if resp["status"] != "ok":
            return {**out, "reason": "fetch_error"}
        probe = {item_date(b): b for b in resp["items"]}
        attributed = all(d in probe and bar_values(probe[d]) == bar_values(raw_by_date[d]) for d in segment)
        signature = sha256_bytes(json.dumps(sorted((d, list(bar_values(b))) for d, b in probe.items())).encode())
        probes.append((segment, attributed, signature))
    tenures = {}
    for segment, _attributed, signature in probes:
        first, last = tenures.get(signature, (segment[0], segment[-1]))
        tenures[signature] = (min(first, segment[0]), max(last, segment[-1]))
    ordered = sorted(tenures.values())
    out["entities"] = len(ordered)
    out["tenures"] = [list(t) for t in ordered]
    if not all(p[1] for p in probes):
        return {**out, "reason": "unattributed_segment"}
    if any(ordered[i][1] >= ordered[i + 1][0] for i in range(len(ordered) - 1)):
        return {**out, "reason": "overlapping_tenures"}
    if len(ordered) != info["asset_ids"]:
        return {**out, "reason": "entity_count_mismatch"}
    # The Market Data API returns no security-type field, so the frozen title's type requirement is unmet.
    return {**out, "dated_resolved": True, "reason": "security_type_unavailable"}


def bar_gain(event_day: str, bars_by_date: dict):
    if event_day not in bars_by_date:
        return None
    earlier = [d for d in sorted(bars_by_date) if d < event_day]
    if not earlier:
        return None
    previous = bars_by_date[earlier[-1]].get("c")
    current = bars_by_date[event_day].get("c")
    if not previous or current is None:
        return None
    return round((current / previous - 1) * 100, 4)


def gain_for(source, symbol: str, event_day: str, asof) -> dict:
    start = shift(event_day, -12)
    auctions = source.auctions(symbol, start, event_day, asof)
    raw = source.bars(symbol, start, event_day, "raw", asof)
    split = source.bars(symbol, start, event_day, "split", asof)
    if any(r["status"] != "ok" for r in (auctions, raw, split)):
        return {"status": "fetch_error"}
    auctions_by, raw_by, split_by = (AUDIT.by_date(r["items"]) for r in (auctions, raw, split))
    result = AUDIT.event_gain(event_day, auctions_by, raw_by, split_by, "v2")
    return {"status": "ok", "has_event_data": event_day in raw_by or event_day in auctions_by,
            "gain_pct": result.get("gain_pct"), "reason": result.get("reason"),
            "event_close_source": result.get("event_close_source"), "prev_close_source": result.get("prev_close_source"),
            "split_between": result.get("split_between"),
            "raw_bar_gain_pct": bar_gain(event_day, raw_by), "split_bar_gain_pct": bar_gain(event_day, split_by)}


def _agrees(value, reference) -> bool:
    return value is not None and reference is not None and AUDIT.agrees(value, reference, AUDIT.PLAN["tolerance"]["event_gain"])


def measure_reused(event: dict, source) -> dict:
    out = {"ticker": event["ticker"], "date": event["date"], "pass": False}
    chosen = None
    for symbol in event["symbols"]:
        result = gain_for(source, symbol, event["date"], event["date"])
        if result["status"] != "ok":
            return {**out, "verdict": "fetch_error"}
        if result["has_event_data"]:
            chosen = (symbol, result)
            break
    if chosen is None:
        return {**out, "verdict": "no_source_data"}
    symbol, result = chosen
    gain = result["gain_pct"]
    matches_catalogued = _agrees(gain, event["dataset_gain"])
    matches_wrong_issuer = _agrees(gain, event["computed_gain"])
    control = gain_for(source, symbol, event["date"], None)
    if control["status"] != "ok":
        control_differs = None
    else:
        control_differs = (not control["has_event_data"]) or control["gain_pct"] is None or not _agrees(control["gain_pct"], gain)
    passed = gain is not None and matches_catalogued and not matches_wrong_issuer
    return {**out, "symbol": symbol, "pass": passed, "verdict": "pass" if passed else "fail",
            "gain_pct": gain, "catalogued_gain_pct": event["dataset_gain"], "wrong_issuer_gain_pct": event["computed_gain"],
            "matches_catalogued": matches_catalogued, "matches_wrong_issuer": matches_wrong_issuer,
            "control_differs": control_differs, "event_close_source": result["event_close_source"]}


def measure_owed(item: dict, source) -> dict:
    result = gain_for(source, item["symbol"], item["date"], item["date"])
    out = {"id": item["id"], "symbol": item["symbol"], "audit_verdict": item["audit_verdict"],
           "audit_gain_pct": item["audit_gain"], "package_gain_pct": item["package_gain"]}
    if result["status"] != "ok":
        return {**out, "verdict": "fetch_error"}
    if result["gain_pct"] is None:
        return {**out, "verdict": result["reason"] or "no_source_data"}
    gain = result["gain_pct"]
    return {**out, "verdict": "measured", "gain_pct": gain,
            "raw_bar_gain_pct": result["raw_bar_gain_pct"], "split_bar_gain_pct": result["split_bar_gain_pct"],
            "reproduces_audit": _agrees(gain, item["audit_gain"]),
            "agrees_package_official": _agrees(gain, item["package_gain"]),
            "agrees_package_raw_bar": _agrees(result["raw_bar_gain_pct"], item["package_gain"]),
            "agrees_package_split_bar": _agrees(result["split_bar_gain_pct"], item["package_gain"]),
            "event_close_source": result["event_close_source"]}


def measure_all(protocol: dict, fixtures: dict, source) -> dict:
    sessions = session_calendar(protocol, source)
    details = {"sessions": {"count": len(sessions), "first": sessions[0], "last": sessions[-1]},
               "delistings": measure_delistings(protocol, fixtures["delistings"], fixtures["ticker_map"], sessions, source)}
    if fixtures["collisions"] is not None:
        details["collisions"] = [measure_collision(protocol, s, info, sessions, source)
                                 for s, info in sorted(fixtures["collisions"].items())]
    if fixtures["reused"] is not None:
        details["reused_tickers"] = [measure_reused(e, source) for e in fixtures["reused"]]
    if fixtures["owed"] is not None:
        details["audit_owed_rows"] = [measure_owed(i, source) for i in fixtures["owed"]]
    return details


# ----------------------------------------------------------------------------- summaries and gates

def summarize_delistings(protocol: dict, rows: list[dict]) -> tuple[dict, dict]:
    spec = protocol["gates"]["pre-2020-delisting"]
    per_year, rates = {}, {}
    for year in YEARS:
        subset = [r for r in rows if r["year"] == year]
        gate_covered = sum(1 for r in subset if r["pit"] and r["raw"]["verdict"] == "covered")
        rates[year] = gate_covered / len(subset) if subset else 0.0
        per_year[year] = {
            "rows": len(subset), "with_symbol": sum(1 for r in subset if r["symbol"]),
            "with_pit_symbol": sum(1 for r in subset if r["pit"]),
            "verdicts_raw": dict(sorted(Counter(r["raw"]["verdict"] for r in subset).items())),
            "verdicts_split": dict(sorted(Counter(r["split"]["verdict"] for r in subset).items())),
            "covered_raw": sum(1 for r in subset if r["raw"]["verdict"] == "covered"),
            "covered_split": sum(1 for r in subset if r["split"]["verdict"] == "covered"),
            "clipped_rows": sum(1 for r in subset if r["raw"].get("clipped")),
            "gate_covered": gate_covered, "gate_rate": round(rates[year], 4)}
    fetch_errors = sum(1 for r in rows for a in ("raw", "split") if r[a]["verdict"] == "fetch_error")
    requested = any(r["symbol"] for r in rows)
    if fetch_errors or not requested:
        outcome = "not_evaluable"
    elif all(rates[y] >= 0.95 for y in YEARS):
        outcome = "confirmed"
    else:
        outcome = "not_confirmed"
    gate = {"outcome": outcome, "fetch_error_rows": fetch_errors, "ticker_map_supplied_rows": sum(1 for r in rows if r["symbol"]),
            "proposed_receipt": {"schema_version": 1, "coverage_status": outcome,
                                 "years_covered": [int(y) for y in YEARS if requested and rates[y] >= 0.95],
                                 "source": {"name": SOURCE_NAME, "kind": "entitled"}},
            "rule": spec["pass"], "limits": spec["limits"]}
    return per_year, gate


def summarize_reused(rows) -> dict | None:
    if rows is None:
        return None
    public = [{k: r.get(k) for k in ("ticker", "verdict", "matches_catalogued", "matches_wrong_issuer", "control_differs",
                                      "event_close_source")} for r in rows]
    passed = sum(1 for r in rows if r["pass"])
    return {"rows": public, "passed": passed, "total": len(rows),
            "verdict": "not_evaluable" if any(r["verdict"] == "fetch_error" for r in rows)
            else ("pass" if passed == len(rows) else "fail")}


def summarize_collisions(protocol: dict, rows, reused: dict | None) -> tuple[dict | None, dict]:
    spec = protocol["gates"]["dated-security-identity"]
    if rows is None:
        return None, {"outcome": "not_evaluable", "reason": "no collision fixture supplied", "rule": spec["pass"]}
    unresolved = sum(1 for r in rows if not r["resolved_frozen"])
    undated = sum(1 for r in rows if not r["dated_resolved"])
    fetch_errors = sum(1 for r in rows if r["reason"] == "fetch_error")
    summary = {"total": len(rows), "dated_resolved": len(rows) - undated, "undated_collisions": undated,
               "unresolved_collisions": unresolved,
               "reasons": dict(sorted(Counter(r["reason"] for r in rows).items())),
               "split_segments_mismatch": sum(1 for r in rows if r.get("split_segments_match") is False),
               "per_symbol": [{k: r.get(k) for k in ("symbol", "asset_ids", "status_pattern", "segments", "entities",
                                                    "dated_resolved", "reason")} for r in rows]}
    reused_verdict = reused["verdict"] if reused else "not_evaluable"
    if fetch_errors:
        outcome = "not_evaluable"
    elif unresolved:
        outcome = "fail"
    elif reused_verdict == "not_evaluable":
        outcome = "not_evaluable"
    else:
        outcome = "pass" if reused_verdict == "pass" else "fail"
    gate = {"outcome": outcome, "fetch_error_collisions": fetch_errors, "reused_tickers_verdict": reused_verdict,
            "proposed_receipt": {"schema_version": 1, "collisions_total": len(rows),
                                 "unresolved_collisions": unresolved, "source": SOURCE_NAME},
            "rule": spec["pass"], "limits": spec["limits"]}
    return summary, gate


def summarize_owed(rows) -> dict | None:
    if rows is None:
        return None
    measured = [r for r in rows if r["verdict"] == "measured"]
    fetch_errors = sum(1 for r in rows if r["verdict"] == "fetch_error")
    reproduced = sum(1 for r in measured if r["reproduces_audit"])
    share = reproduced / len(rows) if rows else 0.0
    by_verdict = {}
    for verdict in sorted({r["audit_verdict"] for r in rows}):
        subset = [r for r in rows if r["audit_verdict"] == verdict]
        by_verdict[verdict] = {"rows": len(subset), "reproduces_audit": sum(1 for r in subset if r.get("reproduces_audit")),
                               "agrees_package_official": sum(1 for r in subset if r.get("agrees_package_official"))}
    return {"rows": len(rows), "measured": len(measured), "fetch_error": fetch_errors,
            "no_data": dict(sorted(Counter(r["verdict"] for r in rows if r["verdict"] not in ("measured", "fetch_error")).items())),
            "reproduces_audit": reproduced, "reproduction_share": round(share, 4),
            "agrees_package_official": sum(1 for r in measured if r["agrees_package_official"]),
            "agrees_package_raw_bar": sum(1 for r in measured if r["agrees_package_raw_bar"]),
            "agrees_package_split_bar": sum(1 for r in measured if r["agrees_package_split_bar"]),
            "by_audit_verdict": by_verdict,
            "verdict": "not_evaluable" if fetch_errors else ("reproduced" if share >= 0.95 else "drifted"),
            "independence": "Alpaca SIP is the audit's own second source; no owed row is adjudicated by this result."}


def build_receipt(protocol: dict, protocol_sha: str, meta: dict, details: dict, snapshot_meta: dict,
                  snapshot_sha: str, details_sha: str) -> dict:
    per_year, delisting_gate = summarize_delistings(protocol, details["delistings"])
    reused = summarize_reused(details.get("reused_tickers"))
    collisions, identity_gate = summarize_collisions(protocol, details.get("collisions"), reused)
    plan_check = ("rate_limit_header_matches_algo_trader_plus" if snapshot_meta.get("rate_limit_header") == 10000
                  else "rate_limit_header_differs_from_algo_trader_plus")
    return {
        "schema_version": 1,
        "kind": "alpaca_history_fixture_receipt",
        "protocol_id": protocol["id"],
        "protocol_sha256": protocol_sha,
        "runner_sha256": runner_sha256(),
        "fetch": {**snapshot_meta, "plan_check": plan_check, "host": DATA_HOST,
                  "feed": protocol["data_request"]["feed"], "snapshot_sha256": snapshot_sha, "details_sha256": details_sha},
        "inputs": meta,
        "session_calendar": details["sessions"],
        "fixtures": {
            "delistings": {"by_year": per_year},
            "collisions": collisions,
            "reused_tickers": reused,
            "audit_owed_rows": summarize_owed(details.get("audit_owed_rows")),
        },
        "gates": {"pre-2020-delisting": delisting_gate, "dated-security-identity": identity_gate},
        "boundary": "Gate proposals only. This receipt never flips a gate: a flip needs manual qualification and a dated commit.",
    }


# ----------------------------------------------------------------------------- outputs

UUID_RE = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
HOME_RE = re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+")
LOCAL_RE = re.compile(r"(?:^|[\s\"'=])/(?:private|tmp|var|Volumes|mnt)/")


def assert_public(text: str, secrets=()) -> None:
    """Refuse a public text that carries a credential value, a UUID (asset or account id) or a local path."""
    for value in secrets:
        if value and value in text:
            raise FixtureError("output would contain a credential value; refused")
    for label, pattern in (("a UUID", UUID_RE), ("a home path", HOME_RE), ("a local path", LOCAL_RE)):
        if pattern.search(text):
            raise FixtureError(f"public output would contain {label}; refused")


def assert_no_secret(raw: bytes, secrets=()) -> None:
    for value in secrets:
        if value and value.encode() in raw:
            raise FixtureError("private output would contain a credential value; refused")


def private_dir(path) -> Path:
    path = safe_path(Path(path).expanduser())
    probe = path
    while True:
        if (probe / ".git").exists():
            raise FixtureError("--out-dir is inside a git checkout; private market data must stay outside it")
        if probe.parent == probe:
            break
        probe = probe.parent
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise FixtureError("--out-dir must be a new or empty directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def write_new(path: Path, raw: bytes, mode: int) -> None:
    path = safe_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)


def emit(protocol: dict, protocol_sha: str, meta: dict, details: dict, snapshot_meta: dict, snapshot_raw: bytes,
         out_dir: Path, receipt_path, secrets=()) -> dict:
    details_raw = canonical(details)
    assert_no_secret(details_raw, secrets)
    receipt = build_receipt(protocol, protocol_sha, meta, details, snapshot_meta,
                            sha256_bytes(snapshot_raw), sha256_bytes(details_raw))
    receipt_raw = canonical(receipt)
    assert_public(receipt_raw.decode(), secrets)
    write_new(out_dir / "details.json", details_raw, 0o600)
    write_new(Path(receipt_path).expanduser(), receipt_raw, 0o644)
    return receipt


# ----------------------------------------------------------------------------- commands

def planned_requests(fixtures: dict) -> dict:
    symbols = sum(1 for r in fixtures["delistings"] if r["accession"] in fixtures["ticker_map"])
    collisions = len(fixtures["collisions"] or {})
    reused = len(fixtures["reused"] or [])
    owed = len(fixtures["owed"] or [])
    return {"calendar": 1, "delistings": 2 * symbols, "collisions_literal": 2 * collisions,
            "collision_probes": "one per segment, known after the literal series",
            "reused_tickers": 6 * reused, "audit_owed_rows": 3 * owed,
            "known_before_run": 1 + 2 * symbols + 2 * collisions + 6 * reused + 3 * owed}


def cmd_plan(args) -> int:
    protocol, protocol_sha = load_protocol()
    check_repo_pins(protocol)
    fixtures, meta = build_fixtures(protocol, args)
    summary = {"protocol_id": protocol["id"], "protocol_sha256": protocol_sha, "inputs": meta,
               "delisting_rows_by_year": dict(sorted(Counter(r["year"] for r in fixtures["delistings"]).items())),
               "reused_tickers": [e["ticker"] for e in fixtures["reused"] or []],
               "audit_owed_rows": dict(Counter(i["audit_verdict"] for i in fixtures["owed"] or [])),
               "planned_requests": planned_requests(fixtures)}
    text = json.dumps(summary, sort_keys=True, indent=1)
    assert_public(text)
    print(text)
    return 0


def cmd_run(args) -> int:
    protocol, protocol_sha = load_protocol()
    check_repo_pins(protocol)
    fixtures, meta = build_fixtures(protocol, args)
    if not (fixtures["ticker_map"] or fixtures["collisions"] is not None or fixtures["reused"] is not None):
        raise FixtureError("nothing to measure: supply --delisting-tickers, a collision source or --package-dir")
    key, secret = keys_from_env()
    receipt_path = Path(args.receipt).expanduser()
    if receipt_path.exists():
        raise FixtureError("--receipt already exists; choose a new path")
    out_dir = private_dir(args.out_dir)
    client = DataClient(key, secret, protocol)
    source = LiveSource(protocol, client)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    aborted = None
    try:
        measure_all(protocol, fixtures, source)
    except (AbortRun, RefusedRequest) as exc:
        aborted = str(exc)
    snapshot_meta = {"fetched_at_utc": started, "requests": client.requests, "retries": client.retries,
                     "status_counts": dict(sorted(client.status_counts.items())),
                     "rate_limit_header": client.rate_limit_header, "client_cap_per_minute_final": client.cap,
                     "fetch_runner_sha256": runner_sha256()}
    snapshot = {"protocol_id": protocol["id"], "protocol_sha256": protocol_sha, "meta": snapshot_meta,
                "aborted": aborted, "responses": source.responses}
    snapshot_raw = canonical(snapshot)
    assert_no_secret(snapshot_raw, (key, secret))
    write_new(out_dir / "snapshot.json", snapshot_raw, 0o600)
    if aborted:
        print(json.dumps({"aborted": aborted, "requests": client.requests,
                          "status_counts": snapshot_meta["status_counts"]}, sort_keys=True))
        return 2
    # Evaluate from the serialized snapshot, exactly as `evaluate` does, so both give the same bytes.
    details = measure_all(protocol, fixtures, SnapshotSource(protocol, json.loads(snapshot_raw)["responses"]))
    receipt = emit(protocol, protocol_sha, meta, details, snapshot_meta, snapshot_raw, out_dir, receipt_path, (key, secret))
    print(json.dumps({"gates": {g: receipt["gates"][g]["outcome"] for g in GATE_IDS},
                      "requests": client.requests, "snapshot_sha256": receipt["fetch"]["snapshot_sha256"]}, sort_keys=True))
    return 0


def cmd_evaluate(args) -> int:
    protocol, protocol_sha = load_protocol()
    check_repo_pins(protocol)
    fixtures, meta = build_fixtures(protocol, args)
    snapshot_raw = read_input(args.snapshot)
    snapshot = json.loads(snapshot_raw)
    if snapshot.get("protocol_sha256") != protocol_sha:
        raise FixtureError("the snapshot was fetched under a different protocol.json")
    if snapshot.get("aborted"):
        raise FixtureError("the snapshot is from an aborted run")
    receipt_path = Path(args.receipt).expanduser()
    if receipt_path.exists():
        raise FixtureError("--receipt already exists; choose a new path")
    out_dir = private_dir(args.out_dir)
    details = measure_all(protocol, fixtures, SnapshotSource(protocol, snapshot["responses"]))
    receipt = emit(protocol, protocol_sha, meta, details, snapshot["meta"], snapshot_raw, out_dir, receipt_path)
    print(json.dumps({"gates": {g: receipt["gates"][g]["outcome"] for g in GATE_IDS}}, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def inputs(p):
        p.add_argument("--delisting-tickers", type=Path, help="frozen point-in-time ticker map for the delisting rows")
        p.add_argument("--asset-master", type=Path, nargs="+", help="the broad-universe asset-master JSON files")
        p.add_argument("--symbol-identities", type=Path, help="the broad-universe run's symbol-identities.json")
        p.add_argument("--package-dir", type=Path, help="the extreme-gainer research package directory")
        p.add_argument("--audit-results", type=Path, help="the audit's private run-20260924b results JSON")

    inputs(sub.add_parser("plan", help="offline fixture and pin check"))
    run = sub.add_parser("run", help="fetch from data.alpaca.markets and write snapshot, details and receipt")
    inputs(run)
    run.add_argument("--out-dir", type=Path, required=True, help="new private directory outside any git checkout")
    run.add_argument("--receipt", type=Path, required=True, help="new public receipt path")
    ev = sub.add_parser("evaluate", help="recompute details and receipt from a snapshot")
    inputs(ev)
    ev.add_argument("--snapshot", type=Path, required=True)
    ev.add_argument("--out-dir", type=Path, required=True)
    ev.add_argument("--receipt", type=Path, required=True)
    return ap


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        return {"plan": cmd_plan, "run": cmd_run, "evaluate": cmd_evaluate}[args.cmd](args)
    except FixtureError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
