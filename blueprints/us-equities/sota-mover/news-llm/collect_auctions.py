#!/usr/bin/env python3
"""Collect official auction prints and entry-time SIP quotes for the news events.

Subcommands
  auctions  GET /v2/stocks/auctions (feed=sip) for every event symbol-session, batched
            per session date (<= 100 symbols per request), all pages retained.
  spreads   GET /v2/stocks/quotes (feed=sip) for each RTH event: the first quotes in
            [entry, entry + 60 s], used only to measure the half-spread at entry.

Read-only market data: only https://data.alpaca.markets is contacted and only the two
paths above; no trading endpoint, no order. Symbols are requested by the ticker current
on the collection date (the provider's default `asof`), which matches the daily
dataset's current-ticker identities; a renamed or reused ticker can therefore map to a
different issuer than the headline's (limitation recorded in protocol.json).

Rate: at most --rate requests per minute (default 2000) until 03:30 America/New_York
after start, then at most 500 per minute. Credentials are read inside this process
only, through blueprints/us-equities/adaptive-paper/credential_guard.py, and are never
printed or written. Collected prices are stored raw; nothing here pairs an entry with
an exit or computes any return.
"""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


_HERE = os.path.dirname(os.path.abspath(__file__))

REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
HOST = "https://data.alpaca.markets"
AUCTIONS_PATH = "/v2/stocks/auctions"
QUOTES_PATH = "/v2/stocks/quotes"
ALLOWED_PATHS = (AUCTIONS_PATH, QUOTES_PATH)
DEFAULT_CREDENTIALS = os.path.expanduser("~/.config/codex-ecosystem/secrets/alpaca-paper-2.env")
PRIVATE_ROOT = os.path.expanduser("~/.local/state/native-agent-stack/research/sota-mover/news-llm")
NY = ZoneInfo("America/New_York")
SYMBOLS_PER_REQUEST = 100
QUOTE_WINDOW = timedelta(seconds=60)
QUOTE_LIMIT = 10
LATE_RATE = 500
LATE_BOUNDARY = (3, 30)
MAX_RETRIES = 6
_CRED = re.compile(r"^\s*(?:export\s+)?(APCA_API_KEY_ID|APCA_API_SECRET_KEY)=(['\"]?)([A-Za-z0-9]+)\2\s*$")


def _load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sig = _load_by_path("news_signal", os.path.join(_HERE, "news_signal.py"))


class DeterministicGzipText:
    """Text writer for a .gz whose bytes depend only on the content (mtime 0, no name)."""

    def __init__(self, path):
        self._raw = open(path, "wb")  # noqa: SIM115 - closed in __exit__
        self._text = io.TextIOWrapper(gzip.GzipFile(filename="", mode="wb", fileobj=self._raw, mtime=0), encoding="utf-8")

    def __enter__(self):
        return self._text

    def __exit__(self, *exc):
        self._text.close()
        self._raw.close()
        return False


def read_credentials(path):
    """Guarded, literal parse of the two APCA variables; values never leave this process."""
    guard = _load_by_path("credential_guard", os.path.join(REPO, "blueprints/us-equities/adaptive-paper/credential_guard.py"))
    try:
        with guard.open_verified(path, follow_symlinks=False) as handle:
            raw = handle.read(64 * 1024 + 1)
    except guard.CredentialGuardError as error:
        raise SystemExit(f"credential guard refused the file: {error}") from None
    if len(raw) > 64 * 1024:
        raise SystemExit("credential file too large")
    found = {}
    for line in raw.decode("ascii", errors="strict").splitlines():
        match = _CRED.match(line)
        if match:
            found[match.group(1)] = match.group(3)
    if set(found) != {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"}:
        raise SystemExit("credential file lacks the two literal APCA variables")
    return {"APCA-API-KEY-ID": found["APCA_API_KEY_ID"], "APCA-API-SECRET-KEY": found["APCA_API_SECRET_KEY"]}


def late_boundary_after(start_utc):
    """The first 03:30 America/New_York at or after start."""
    local = start_utc.astimezone(NY)
    boundary = local.replace(hour=LATE_BOUNDARY[0], minute=LATE_BOUNDARY[1], second=0, microsecond=0)
    if boundary < local:
        boundary += timedelta(days=1)
        boundary = boundary.replace(hour=LATE_BOUNDARY[0], minute=LATE_BOUNDARY[1])
    return boundary.astimezone(timezone.utc)


class RateLimiter:
    """Evenly spaced request starts: rate/min until the boundary, LATE_RATE/min after."""

    def __init__(self, rate, boundary_utc, clock=time.monotonic, wall=lambda: datetime.now(timezone.utc), sleep=time.sleep):
        self.rate = rate
        self.boundary = boundary_utc
        self.clock, self.wall, self.sleep = clock, wall, sleep
        self.lock = threading.Lock()
        self.next_at = clock()

    def current_rate(self):
        return self.rate if self.wall() < self.boundary else min(self.rate, LATE_RATE)

    def wait(self):
        with self.lock:
            interval = 60.0 / self.current_rate()
            now = self.clock()
            start = max(now, self.next_at)
            self.next_at = start + interval
        delay = start - self.clock()
        if delay > 0:
            self.sleep(delay)


def urllib_transport(url, headers, timeout=60):
    request = urllib.request.Request(url, headers={**headers, "User-Agent": "sota-news-llm-collect/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as error:
        return error.code, error.read()[:500], {k.lower(): v for k, v in (error.headers or {}).items()}


class Client:
    def __init__(self, headers, limiter, transport=urllib_transport, sleep=time.sleep):
        self.headers = headers
        self.limiter = limiter
        self.transport = transport
        self.sleep = sleep
        self.tally = Counter()
        self.lock = threading.Lock()
        self.rate_limit_header = None

    def get(self, path, params):
        if path not in ALLOWED_PATHS:
            raise ValueError(f"path not allowed: {path}")
        url = HOST + path + "?" + urllib.parse.urlencode(params)
        for attempt in range(MAX_RETRIES):
            self.limiter.wait()
            try:
                status, body, headers = self.transport(url, self.headers)
            except OSError as error:
                with self.lock:
                    self.tally[f"error:{type(error).__name__}"] += 1
                self.sleep(min(60, 2 ** attempt))
                continue
            with self.lock:
                self.tally[f"http_{status}"] += 1
                self.tally["requests"] += 1
                if headers.get("x-ratelimit-limit"):
                    self.rate_limit_header = headers.get("x-ratelimit-limit")
            if status == 200:
                return json.loads(body)
            if status == 429 or status >= 500:
                reset = headers.get("x-ratelimit-reset")
                wait = 2 ** attempt
                if reset and reset.isdigit():
                    wait = max(wait, int(reset) - int(time.time()))
                self.sleep(min(60, max(1, wait)))
                continue
            raise RuntimeError(f"HTTP {status} for {path}")
        raise RuntimeError(f"retries exhausted for {path}")

    def pages(self, path, params):
        token = None
        while True:
            query = dict(params)
            if token:
                query["page_token"] = token
            payload = self.get(path, query)
            yield payload
            token = payload.get("next_page_token")
            if not token:
                return


def read_events(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def auction_requests(events):
    """Deterministic (session, symbols-chunk) requests covering every event symbol-session."""
    by_day = defaultdict(set)
    for ev in events:
        by_day[ev["session"]].add(ev["symbol"])
    out = []
    for day in sorted(by_day):
        symbols = sorted(by_day[day])
        for i in range(0, len(symbols), SYMBOLS_PER_REQUEST):
            out.append((day, symbols[i:i + SYMBOLS_PER_REQUEST]))
    return out


def request_key(*parts):
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


class Ledger:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.done = set()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if rec.get("status") == "ok":
                        self.done.add(rec["key"])

    def write(self, rec):
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(rec, sort_keys=True) + "\n")
            if rec.get("status") == "ok":
                self.done.add(rec["key"])


def fetch_auctions(client, day, symbols):
    params = {
        "symbols": ",".join(symbols),
        "start": f"{day}T00:00:00Z",
        "end": f"{day}T23:59:59Z",
        "limit": 10000,
        "feed": "sip",
        "sort": "asc",
    }
    merged = {}
    pages = 0
    for payload in client.pages(AUCTIONS_PATH, params):
        pages += 1
        for symbol, days in (payload.get("auctions") or {}).items():
            merged.setdefault(symbol, []).extend(days)
    return merged, pages


def cmd_auctions(args, client):
    events = list(read_events(args.events))
    requests = auction_requests(events)
    out_dir = os.path.join(args.out, "auctions")
    pages_dir = os.path.join(out_dir, "pages")
    os.makedirs(pages_dir, exist_ok=True)
    ledger = Ledger(os.path.join(out_dir, "ledger.jsonl"))
    todo = [(d, s) for d, s in requests if request_key("auctions", d, *s) not in ledger.done]
    print(json.dumps({"requests_total": len(requests), "requests_todo": len(todo)}), flush=True)

    def work(item):
        day, symbols = item
        key = request_key("auctions", day, *symbols)
        try:
            merged, pages = fetch_auctions(client, day, symbols)
        except RuntimeError as error:
            ledger.write({"key": key, "day": day, "n_symbols": len(symbols), "status": "failed", "error": str(error)})
            return
        raw = json.dumps({"day": day, "symbols": symbols, "auctions": merged}, sort_keys=True).encode()
        path = os.path.join(pages_dir, f"{day}-{key}.json.gz")
        with open(path, "wb") as handle:
            handle.write(gzip.compress(raw, mtime=0))
        ledger.write({"key": key, "day": day, "n_symbols": len(symbols), "pages": pages, "status": "ok",
                      "symbols_returned": len(merged), "sha256": hashlib.sha256(raw).hexdigest()})

    run_pool(work, todo, args.workers, label="auctions")
    materialize_auctions(out_dir, events)


def materialize_auctions(out_dir, events):
    """One row per (session, symbol) with the raw o/c entries; coverage counts only.

    Streams the retained pages in (session, symbol) order so memory stays bounded.
    """
    primary = {(ev["symbol"], ev["session"]): ev.get("exchange") for ev in events}
    pages_dir = os.path.join(out_dir, "pages")
    by_day = defaultdict(list)
    for name in os.listdir(pages_dir):
        if name.endswith(".json.gz"):
            by_day[name[:10]].append(name)
    path = os.path.join(out_dir, "auctions.jsonl.gz")
    coverage = Counter()
    found = set()
    written = 0
    with DeterministicGzipText(path) as out:
        for day in sorted(by_day):
            rows = {}
            for name in by_day[day]:
                with gzip.open(os.path.join(pages_dir, name), "rt", encoding="utf-8") as handle:
                    page = json.load(handle)
                for symbol, days in page["auctions"].items():
                    for d in days:
                        key = (symbol, d.get("d"))
                        if key in primary:
                            rows[symbol] = {"symbol": symbol, "session": d.get("d"), "o": d.get("o") or [], "c": d.get("c") or []}
            for symbol in sorted(rows):
                row = rows[symbol]
                out.write(json.dumps(row, sort_keys=True) + "\n")
                written += 1
                found.add((symbol, row["session"]))
                count_coverage(coverage, row, primary[(symbol, row["session"])])
    coverage["symbol_sessions_wanted"] = len(primary)
    coverage["no_auction_record"] = len(primary) - len(found)

    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    summary = {"rows": written, "sha256": digest, "coverage": dict(coverage)}
    with open(os.path.join(out_dir, "auctions-summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, sort_keys=True)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return summary


def count_coverage(coverage, row, listing):
    """Coverage of official prices for one symbol-session (no prices are combined)."""
    codes = sig.LISTING_TAPE_CODES.get(listing, ())
    o = sig.select_auction_price(row["o"], "open", listing)
    c = sig.select_auction_price(row["c"], "close", listing)
    coverage["official_open_available"] += o is not None
    coverage["official_close_available"] += c is not None
    coverage["both_available"] += o is not None and c is not None
    for kind, sel in (("open", o), ("close", c)):
        if sel is not None:
            how = "listing_print" if (sel[2] in codes and sel[1] in ("O", "6")) else f"fallback_{sel[1]}"
            coverage[f"{kind}_via_{how}"] += 1


def cmd_spreads(args, client):
    events = [ev for ev in read_events(args.events) if ev["window"] == sig.RTH]
    events.sort(key=lambda ev: ev["event_id"])
    out_dir = os.path.join(args.out, "spreads")
    os.makedirs(out_dir, exist_ok=True)
    ledger = Ledger(os.path.join(out_dir, "ledger.jsonl"))
    rows_path = os.path.join(out_dir, "quotes.jsonl")
    lock = threading.Lock()
    todo = [ev for ev in events if request_key("quotes", ev["event_id"]) not in ledger.done]
    print(json.dumps({"rth_events": len(events), "todo": len(todo)}), flush=True)

    def work(ev):
        key = request_key("quotes", ev["event_id"])
        entry = sig.as_utc(ev["entry_utc"])
        params = {
            "symbols": ev["symbol"],
            "start": entry.isoformat().replace("+00:00", "Z"),
            "end": (entry + QUOTE_WINDOW).isoformat().replace("+00:00", "Z"),
            "limit": QUOTE_LIMIT,
            "feed": "sip",
            "sort": "asc",
        }
        try:
            payload = client.get(QUOTES_PATH, params)
        except RuntimeError as error:
            ledger.write({"key": key, "event_id": ev["event_id"], "status": "failed", "error": str(error)})
            return
        quotes = (payload.get("quotes") or {}).get(ev["symbol"], [])[:QUOTE_LIMIT]
        row = {"event_id": ev["event_id"], "symbol": ev["symbol"], "entry_utc": ev["entry_utc"], "quotes": quotes}
        with lock:
            with open(rows_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        ledger.write({"key": key, "event_id": ev["event_id"], "status": "ok", "n_quotes": len(quotes)})

    run_pool(work, todo, args.workers, label="spreads")
    summarize_spreads(out_dir, {ev["event_id"] for ev in events})


def first_valid_half_spread(quotes):
    for q in quotes:
        hs = sig.half_spread_fraction(q)
        if hs is not None:
            return hs, q.get("t")
    return None, None


def summarize_spreads(out_dir, event_ids=None):
    """Half-spread distribution over the current RTH events (rows of dropped events are ignored)."""
    rows_path = os.path.join(out_dir, "quotes.jsonl")
    values = []
    counts = Counter()
    seen = set()
    if os.path.exists(rows_path):
        with open(rows_path, encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if row["event_id"] in seen or (event_ids is not None and row["event_id"] not in event_ids):
                    continue
                seen.add(row["event_id"])
                counts["events"] += 1
                hs, _ = first_valid_half_spread(row["quotes"])
                if hs is None:
                    counts["no_valid_quote"] += 1
                else:
                    values.append(hs * 1e4)
    values.sort()

    def q(p):
        return round(values[min(len(values) - 1, int(p * len(values)))], 3) if values else None

    summary = {
        "counts": dict(counts),
        "half_spread_bps": {"p10": q(0.1), "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "p90": q(0.9), "p99": q(0.99)},
    }
    if os.path.exists(rows_path):
        with open(rows_path, "rb") as handle:
            summary["quotes_sha256"] = hashlib.sha256(handle.read()).hexdigest()
    with open(os.path.join(out_dir, "spreads-summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, sort_keys=True)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return summary


def run_pool(work, items, workers, label):
    started = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(work, items):
            done += 1
            if done % 500 == 0:
                rate = done / max(1e-9, time.time() - started) * 60
                print(json.dumps({"stage": label, "done": done, "of": len(items), "per_min": round(rate)}), flush=True)


def main(argv=None, transport=None, credentials=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("auctions", "spreads", "summarize"))
    parser.add_argument("--events", default=os.path.join(PRIVATE_ROOT, "events.jsonl.gz"))
    parser.add_argument("--out", default=PRIVATE_ROOT)
    parser.add_argument("--credentials", default=DEFAULT_CREDENTIALS)
    parser.add_argument("--rate", type=int, default=2000, help="requests per minute before 03:30 ET (max 2000)")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    if not 1 <= args.rate <= 2000:
        raise SystemExit("--rate must be between 1 and 2000")
    if args.command == "summarize":
        materialize_auctions(os.path.join(args.out, "auctions"), list(read_events(args.events)))
        summarize_spreads(os.path.join(args.out, "spreads"), {ev["event_id"] for ev in read_events(args.events) if ev["window"] == sig.RTH})
        return
    headers = credentials if credentials is not None else read_credentials(args.credentials)
    limiter = RateLimiter(args.rate, late_boundary_after(datetime.now(timezone.utc)))
    client = Client(headers, limiter, transport=transport or urllib_transport)
    started = time.time()
    if args.command == "auctions":
        cmd_auctions(args, client)
    else:
        cmd_spreads(args, client)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tally = {"command": args.command, "finished_at": stamp, "seconds": round(time.time() - started, 1),
             "http": dict(client.tally), "x_ratelimit_limit": client.rate_limit_header,
             "rate_per_min_before_0330_et": args.rate, "rate_per_min_after_0330_et": min(args.rate, LATE_RATE)}
    with open(os.path.join(args.out, f"http-tally-{args.command}-{stamp}.json"), "w", encoding="utf-8") as handle:
        json.dump(tally, handle, indent=1, sort_keys=True)
    print(json.dumps(tally, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
