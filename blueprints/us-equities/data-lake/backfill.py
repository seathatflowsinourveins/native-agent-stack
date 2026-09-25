"""Governed, resumable Alpaca historical backfill into the data lake's raw source layer.

  python backfill.py news --env-file ENV --out DIR --start 2015-01-01 --end 2026-09-23 [--rate 3000] [--workers 8]
  python backfill.py universe --daily-dataset DAILY_DIR --out UNIVERSE_JSON        (research runtime with DuckDB)
  python backfill.py stock_bars_1min --env-file ENV --out DIR --universe UNIVERSE_JSON \
      --start 2016-01-01 --end 2026-08-31 [--rate 6000] [--workers 16] --pilot 2   (then the same without --pilot)
  python backfill.py verify DATASET --out DIR

Exit codes: 0 done; 1 task failures or an incomplete pilot; 2 refused (before any request, or a pilot whose disk
projection does not fit); 3 stopped early (the STOP file or the disk re-check drained the run: resume with the same
command); 4 the pilot raised a D2 overturn flag (a full run then needs --accept-pilot-flags REASON).

Scope: DIR/<dataset>/scope.json records the sha256 of this file, the endpoint, the fixed request parameters, the
sha256 of the symbol task list, the span and the planned task count with the sha256 of the task ids. The first run
writes it. A run whose scope differs in any field, a header that no longer hashes to its fingerprint, or a manifest
without a header is refused (exit 2) before any request, so completed work is never reused for another scope (the rule
broad-universe/collect_daily.py applies). Each page-capture manifest row also carries that fingerprint, and a row
naming another one never counts as done. `verify` compares the recorded tasks with the planned ones and reports
complete: false (exit 1) while any planned task has no row.

Also refused with exit 2 before any request: an --out inside a git work tree (licensed provider data never lands in
a checkout); a STOP file present at start; a second backfill on this host, whatever its dataset or --out (a host-wide
lease, ~/.local/state/native-agent-stack/data-lake/backfill.lock, keeps the backfill pool one job at a time within
the account's shared data limit); a second run on the same dataset (DIR/<dataset>/.lock).

news keeps the record capture its 2015-2026 archive was collected with: one task per UTC calendar day, the day's
records re-serialized (sorted keys) into DIR/news/<YYYY>/<MM>/<DD>.jsonl.gz, one manifest row per day. A day is now
requested from 00:00:00Z to 23:59:59.999999999Z (both bounds are inclusive); the archive's D+1T00:00:00Z end put two
records stamped exactly at midnight into two day files, so its consumers dedupe by id.

stock_bars_1min (convergence record 2026-09-24, D1-D2): SIP 1-minute bars, raw prices, extended hours, for every
symbol of the asof-aware monthly universe (`universe`: each month's symbols with a daily SIP bar in the deduplicated
broad-universe daily dataset, active and delisted alike, named as of that collection's request date, which becomes
the request `asof`). A task is 100 symbols x one calendar month, from 04:00 ET on the first day to
19:59:59.999999999 ET on the last. Each page is requested with Accept-Encoding: gzip, stored exactly as received and
written (fsynced) as it arrives. The task's manifest row records every page's request parameters (the task parameters
plus its page_token), sha256, sizes and next page token, the bars per symbol and the requested symbols that returned
none, and counts bars outside 04:00-20:00 ET as quarantined (listing the first 100) instead of failing the task. A
task counts as done only while every recorded page file exists at its recorded size; a news day, likewise its file.

A full run requires a pilot of the same scope: --pilot N fetches N (at most 20) evenly spread tasks, reports wire and
stored bytes per page and per bar, pages by Content-Encoding, peak RSS and the symbol-months without bars, and projects
the raw disk the span still needs. It refuses when that exceeds 40% of free disk or would leave less than a 20 GiB
floor plus a reserve for the normalized layer (16.8 bytes per projected bar), and it gives verdict "overturn" when one
of D2's overturn conditions holds (continuation pages under 95% full, or projected calls above 1.3x D2's estimate).
While a run is going, free disk is re-read before each task starts: the run drains like STOP below the floor, and a
full run also when storing the remaining projection would break that floor and reserve, or once it has stored more
than 1.5x the projection.

A shared token bucket keeps the whole run under --rate requests per minute (at most 6,000 of the account's
10,000/min data limit measured on 2026-09-24, which every other data client shares). An HTTP 429 waits for the limit's
reset before retrying, and a response whose X-Ratelimit-Remaining is under 3,500 (the headroom the monitor, scans and
engine always keep) pauses the bucket until the limit resets. Requests go to the fixed endpoint only: redirects are
refused before any follow-up request (urllib would resend the key pair to the Location host, over plain http too) and
environment proxies are ignored. GET only. Normalized Parquet is a separate, later layer.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import functools
import gzip
import hashlib
import http.client
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DATA = "https://data.alpaca.markets"
ET = ZoneInfo("America/New_York")
MAX_RATE = 6000
RATELIMIT_FLOOR = 3500  # X-Ratelimit-Remaining the monitor, scans and engine always keep (critique B10, budget table)
FREE_DISK_SHARE = 0.40  # a pilot refuses when the projected remaining disk use exceeds this share of free space
DISK_FLOOR = 20 * 2 ** 30  # free bytes a page-capture run never takes the lake's filesystem below (shared with ~/.local/state)
DISK_OVERRUN = 1.5  # a running full run drains once its stored bytes exceed this multiple of the pilot's projection
# D1's normalized layer (DuckDB Zstd Parquet, DECIMAL(18,6)) measured 16.8 bytes/bar in the D2 proposal (DL-2: about
# 70 GB for the span's 4.17e9 bars, X4's arithmetic). Both disk gates keep this much free beyond the floor, scaled by
# the pilot's projected bars, so a raw backfill never leaves too little room to normalize it.
NORMALIZED_BYTES_PER_BAR = 16.8
QUARANTINE_EXAMPLES = 100  # a row lists at most this many quarantined bars (their count is exact; the pages keep them)
HOST_LEASE = Path.home() / ".local/state/native-agent-stack/data-lake/backfill.lock"  # one backfill per host
MAX_PILOT_TASKS = 20  # a pilot runs before any disk gate, so it stays a bounded sample and can never be the full run
MAX_PAGES_PER_TASK = 2000  # 100 symbols x 23 sessions x 960 minutes fill at most 221 pages of 10,000 bars
# D2's bar model: 4.171e9 bars for 2016-01-04..2026-09 (local fit on retained mover pages, held-out -3.2%/+5.0%), over
# the retained universe's 24,195,741 symbol-sessions for 2016-01..2026-09: about 172.4 bars per symbol-session.
D2_BARS_PER_SYMBOL_SESSION = 4.171e9 / 24_195_741
D2_MIN_FULL = 0.95  # D2 overturn: continuation pages under 95% full ...
D2_MAX_CALLS = 1.3  # ... or projected calls above 1.3x D2's estimate: per-day tasks replace month tasks
EXIT_FAILED, EXIT_REFUSED, EXIT_STOPPED, EXIT_OVERTURN = 1, 2, 3, 4
SYMBOL = re.compile(r"^[A-Z]+(\.[A-Z]+)?$")  # broad-universe/collect_daily.py DATA_SYMBOL: what the bars API accepts
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
PROVIDER_DEFAULT_ASOF = "provider default (request date)"  # broad-universe plan.json wording
SCOPE_SCHEMA = "data-lake-scope/1"
UNIVERSE_SCHEMA = "data-lake-monthly-universe/1"
PILOT_SCHEMA = "data-lake-pilot/2"
DATASETS = {
    # start and end are both inclusive (the /v1beta1/news reference), so a day ends at 23:59:59.999999999Z: the
    # retained archive's D+1T00:00:00Z end stored two records stamped exactly at midnight in two day files.
    "news": {"path": "/v1beta1/news", "key": "news", "capture": "records", "task": "calendar day (UTC)",
             "window_utc": ["00:00:00", "23:59:59.999999999"],
             "params": {"limit": 50, "sort": "asc", "include_content": "true", "exclude_contentless": "false"}},
    "stock_bars_1min": {"path": "/v2/stocks/bars", "key": "bars", "capture": "pages", "task": "symbols x calendar month",
                        "batch_size": 100, "window_et": ["04:00", "19:59:59.999999999"],
                        "params": {"timeframe": "1Min", "feed": "sip", "adjustment": "raw", "limit": 10000,
                                   "sort": "asc"}},
}


class Refused(Exception):
    """A governed refusal, raised before any request for the refused scope."""


class Halted(Exception):
    """The run is stopping after an exception in its main thread: no further request is sent."""


class Bucket:
    """Thread-safe token bucket: at most `rate` acquisitions per 60 s, smoothly."""

    def __init__(self, rate_per_minute: float, clock=time.monotonic, sleep=time.sleep):
        self.interval, self.clock, self.sleep = 60.0 / rate_per_minute, clock, sleep
        self.next, self.lock = clock(), threading.Lock()
        self.paused_until = 0.0

    def acquire(self) -> None:
        with self.lock:
            now = self.clock()
            start = max(now, self.next, self.paused_until)
            self.next = start + self.interval
        wait_for = start - self.clock()
        if wait_for > 0:
            self.sleep(wait_for)

    def pause(self, seconds: float) -> None:
        with self.lock:
            self.paused_until = max(self.paused_until, self.clock() + seconds)


class RedirectRefused(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect before a follow-up request is built. The stdlib handler copies every header except
    Content-Length and Content-Type into the redirected request, so a 3xx would resend the key pair to the Location
    host, over plain http too (financial-data/sec_data.py NoRedirect; D12's fixed-endpoint redirect guard). The 3xx
    becomes a non-retryable HTTPError that fails its task."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise urllib.error.HTTPError(req.full_url, code, f"redirect refused ({msg})", headers, None)


def guarded_opener() -> urllib.request.OpenerDirector:
    """The data client's opener: redirects refused, environment proxies ignored (the fixed endpoint only)."""
    return urllib.request.build_opener(RedirectRefused(), urllib.request.ProxyHandler({}))


class Client:
    def __init__(self, headers: dict, bucket: Bucket, opener=None, sleep=time.sleep, wall=time.time):
        self.headers, self.bucket, self.sleep, self.wall = headers, bucket, sleep, wall
        self.opener = opener or guarded_opener().open
        self.requests = self.throttled = self.ratelimit_floor_pauses = 0
        self.ratelimit_remaining_min = None
        self.halt = threading.Event()
        self.lock = threading.Lock()

    def until_reset(self, headers, fallback: float) -> float:
        """Seconds until X-Ratelimit-Reset (a Unix time), at least 1; `fallback` without a usable header."""
        reset = headers.get("X-Ratelimit-Reset") if headers is not None else None
        return max(1.0, float(reset) - self.wall()) if reset and str(reset).isdigit() else fallback

    def fetch(self, path: str, params: dict, accept_gzip: bool = False) -> tuple[bytes, str]:
        """One GET with bounded retries: (the body exactly as received, its Content-Encoding)."""
        url = f"{DATA}{path}?{urllib.parse.urlencode(params)}"
        headers = {**self.headers, "Accept-Encoding": "gzip"} if accept_gzip else self.headers
        for attempt in range(8):
            self.bucket.acquire()
            if self.halt.is_set():
                raise Halted(f"the run is halting: {path} not requested")
            with self.lock:
                self.requests += 1
            try:
                with self.opener(urllib.request.Request(url, headers=headers), timeout=60) as r:
                    body, meta = r.read(), getattr(r, "headers", None)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    with self.lock:
                        self.throttled += 1
                    self.bucket.pause(min(self.until_reset(exc.headers, 2.0 ** attempt), 60.0))
                    continue
                if exc.code >= 500:
                    self.sleep(min(30.0, 2.0 ** attempt))
                    continue
                raise
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError):
                self.sleep(min(30.0, 2.0 ** attempt))
                continue
            encoding = ((meta.get("Content-Encoding") if meta is not None else None) or "identity").strip().lower()
            if encoding not in ("identity", "gzip"):
                raise RuntimeError(f"unexpected Content-Encoding {encoding!r}: {path}")
            remaining = meta.get("X-Ratelimit-Remaining") if meta is not None else None
            if remaining is not None and str(remaining).isdigit():
                remaining = int(remaining)
                with self.lock:
                    low = self.ratelimit_remaining_min
                    self.ratelimit_remaining_min = remaining if low is None else min(low, remaining)
                if remaining < RATELIMIT_FLOOR:  # leave the account's headroom to the other pools until the reset
                    with self.lock:
                        self.ratelimit_floor_pauses += 1
                    self.bucket.pause(min(self.until_reset(meta, 1.0), 60.0))
            return body, encoding
        raise RuntimeError(f"gave up after retries: {path}")

    def get(self, path: str, params: dict) -> dict:
        body, encoding = self.fetch(path, params)
        return json.loads(gzip.decompress(body) if encoding == "gzip" else body)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_sha256() -> str:
    return file_sha256(Path(__file__).resolve())


def symbols_digest(symbols) -> str:
    return sha256_hex(",".join(symbols).encode())


def write_private(target: Path, payload: bytes, sync_dir: bool = True) -> None:
    """Atomic, durable owner-only write: the bytes are fsynced before the rename, so a reader or a crash sees the
    previous file or the complete new one, never a torn or empty one; then the directory is fsynced, so the rename
    itself survives a crash (scope.json must, before any manifest row names it). A caller writing many files into one
    directory passes sync_dir=False and fsyncs that directory once."""
    tmp = target.with_name(target.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    if sync_dir:
        fsync_dir(target.parent)


def fsync_dir(path: Path) -> None:
    """Make a directory's entries (new files, a rename into it) durable."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def append_row(handle, row: dict) -> None:
    """Append one manifest row and make it durable before the next is recorded."""
    handle.write(json.dumps(row, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def repair_manifest_tail(manifest: Path) -> None:
    """End a torn last line (a crash mid-write) so the next row starts on its own line and stays readable."""
    if manifest.exists() and manifest.stat().st_size:
        with open(manifest, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            torn = handle.read(1) != b"\n"
        if torn:
            fd = os.open(manifest, os.O_WRONLY | os.O_APPEND)
            with os.fdopen(fd, "wb") as handle:
                handle.write(b"\n")


@contextlib.contextmanager
def exclusive_lock(path: Path, note: str = ""):
    """Hold a non-blocking flock on `path` for the block. A held lock is refused, never waited for; `note` (who holds
    the lock) is written into the file so a refused run can name the holder."""
    import fcntl
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            holder = os.pread(fd, 512, 0).decode("utf-8", "replace").strip()
            raise Refused(f"another backfill run holds {path}" + (f": {holder}" if holder else "")) from None
        if note:
            os.ftruncate(fd, 0)
            os.pwrite(fd, note.encode(), 0)
        yield
    finally:
        os.close(fd)  # closing the descriptor releases the lock


def git_work_tree(path: Path) -> Path | None:
    """The nearest directory at or above `path` (symlinks resolved) that holds a .git entry, or None."""
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if os.path.lexists(candidate / ".git"):
            return candidate
    return None


def refuse_inside_git_work_tree(out: Path) -> None:
    """Licensed provider data never lands in a git work tree: a routine `git add -A` would stage it, and this checkout
    publishes to a public repository."""
    tree = git_work_tree(out)
    if tree is not None:
        raise Refused(f"--out {out} lies inside the git work tree {tree}: keep licensed provider data outside any "
                      "checkout (for example under ~/.local/state/native-agent-stack/research/data-lake)")


# --------------------------------------------------------------------------- scope header


def span_days(start: date, end: date) -> list:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def day_file(day: str) -> str:
    return f"{day[:4]}/{day[5:7]}/{day[8:10]}.jsonl.gz"


def dataset_scope(dataset: str, start: date, end: date, tasks: list | None = None, asof: str | None = None,
                  code: str | None = None) -> dict:
    """Every field that changes WHICH records a completed task holds, and the planned task list (its count and the
    sha256 of its ids), so verify can tell a complete dataset from one missing tasks."""
    spec = DATASETS[dataset]
    params = {**spec["params"], **({"asof": asof} if asof else {})}
    task = {"unit": spec["task"], **{k: spec[k] for k in ("batch_size", "window_et", "window_utc") if k in spec}}
    ids = [t["task"] for t in tasks] if tasks is not None else [d.isoformat() for d in span_days(start, end)]
    return {"dataset": dataset, "code_sha256": code or code_sha256(), "endpoint": DATA + spec["path"],
            "fixed_params": params, "span": {"start": start.isoformat(), "end": end.isoformat()},
            "symbols_sha256": None if tasks is None else sha256_hex(canonical([[t["task"], t["symbols"]] for t in tasks])),
            "planned": {"tasks": len(ids), "task_ids_sha256": sha256_hex(canonical(ids))},
            "task": task, "capture": spec["capture"]}


def scope_fingerprint(scope: dict) -> str:
    return sha256_hex(canonical(scope))


def refuse_headerless(ds_dir: Path) -> None:
    manifest = ds_dir / "manifest.jsonl"
    if not (ds_dir / "scope.json").exists() and manifest.is_file() and manifest.stat().st_size:
        raise Refused(f"{manifest} has no scope header (collected before scope headers existed), so its scope "
                      "cannot be verified and it is not resumed: collect into a new --out directory.")


def read_header(ds_dir: Path) -> dict | None:
    """The dataset's scope header, None when it has none; refused when it is unreadable or no longer hashes to its
    recorded fingerprint."""
    header_path = ds_dir / "scope.json"
    if not header_path.exists():
        return None
    try:
        recorded = json.loads(header_path.read_text())
        intact = (isinstance(recorded.get("scope"), dict)
                  and recorded.get("fingerprint") == scope_fingerprint(recorded["scope"]))
    except (ValueError, AttributeError, TypeError):
        intact = False
    if not intact:
        raise Refused(f"{header_path} is unreadable or does not hash to its recorded fingerprint (edited or corrupt)")
    return recorded


def check_scope(ds_dir: Path, scope: dict, provenance: dict) -> dict:
    """Write the dataset's scope header on first use; refuse any later run whose scope differs from it."""
    header_path = ds_dir / "scope.json"
    fingerprint = scope_fingerprint(scope)
    recorded = read_header(ds_dir)
    if recorded is not None:
        recorded_scope = recorded["scope"]
        if recorded["fingerprint"] != fingerprint:
            changed = "; ".join(f"{key}: recorded={recorded_scope.get(key)!r} requested={scope.get(key)!r}"
                                for key in sorted(set(recorded_scope) | set(scope))
                                if recorded_scope.get(key) != scope.get(key))
            raise Refused(f"{ds_dir} was collected under a different scope ({changed}). Its completed tasks must "
                          "not be reused for this scope: collect it into a new --out directory.")
        return recorded
    refuse_headerless(ds_dir)
    header = {"schema": SCOPE_SCHEMA, "fingerprint": fingerprint, "scope": scope, "provenance": provenance}
    write_private(header_path, (json.dumps(header, indent=1, sort_keys=True) + "\n").encode())
    return header


# --------------------------------------------------------------------------- asof-aware monthly universe


def collection_naming_date(plans: list, stamps: list) -> str:
    """The date the daily collection's symbols are named at. Its collector sent no asof, so the provider named every
    symbol as of the request date: every request must fall on one date, in UTC and in New York, or it is ambiguous."""
    values = [plan.get("asof") for plan in plans]
    if any(not isinstance(value, str) for value in values):
        raise ValueError("a daily collection plan records no asof")
    explicit = set(values) - {PROVIDER_DEFAULT_ASOF}
    if explicit:
        if len(set(values)) != 1:
            raise ValueError(f"the daily collection's plans disagree on asof: {sorted(map(str, set(values)))}")
        return date.fromisoformat(values[0]).isoformat()
    if not plans or not stamps:
        raise ValueError("no plan or ledger timestamps date the daily collection's symbol naming")
    days = set()
    for stamp in stamps:
        moment = datetime.fromisoformat(stamp)
        if moment.tzinfo is None:
            raise ValueError(f"ledger timestamp without a timezone: {stamp!r}")
        days |= {moment.astimezone(timezone.utc).date(), moment.astimezone(ET).date()}
    if len(days) != 1:
        raise ValueError(f"the daily collection's requests span {sorted(d.isoformat() for d in days)}, so its "
                         "provider-default symbol naming date is ambiguous")
    return days.pop().isoformat()


def build_universe(rows, naming_asof: str, source: dict) -> dict:
    """rows: (YYYY-MM, symbol, sessions with a daily bar that month), from a deduplicated daily dataset."""
    naming_asof = date.fromisoformat(naming_asof).isoformat()
    covers_through = date.fromisoformat(source["last_session"]).isoformat()
    months: dict = {}
    for month, symbol, sessions in rows:
        if not (isinstance(month, str) and MONTH.match(month) and isinstance(symbol, str) and SYMBOL.match(symbol)
                and isinstance(sessions, int) and not isinstance(sessions, bool) and sessions > 0):
            raise ValueError(f"malformed universe row {(month, symbol, sessions)!r}")
        members = months.setdefault(month, {})
        if symbol in members:
            raise ValueError(f"duplicate universe row {month} {symbol}")
        members[symbol] = sessions
    if not months:
        raise ValueError("empty universe")
    ordered = {month: dict(sorted(months[month].items())) for month in sorted(months)}
    return {"schema": UNIVERSE_SCHEMA, "naming_asof": naming_asof, "covers_through": covers_through,
            "rule": "symbols with at least one daily SIP bar in the month in the broad-universe daily dataset after "
                    "coverage.dedupe_identity (asset master active and inactive plus the corporate-action supplement), "
                    "named as of the collection's request date; each value is the symbol's daily-bar sessions that month",
            "source": source, "first_month": min(ordered), "last_month": max(ordered),
            "summary": {"months": len(ordered), "symbols": len(set().union(*ordered.values())),
                        "symbol_months": sum(map(len, ordered.values())),
                        "symbol_sessions": sum(sum(members.values()) for members in ordered.values()),
                        "tasks_at_batch_100": sum(math.ceil(len(members) / 100) for members in ordered.values())},
            "months": ordered}


def load_universe(path: Path) -> dict:
    payload = path.read_bytes()
    universe = json.loads(payload)
    try:
        ok = universe.get("schema") == UNIVERSE_SCHEMA and bool(universe["months"])
        date.fromisoformat(universe["naming_asof"])
        date.fromisoformat(universe["covers_through"])
        ok = ok and all(MONTH.match(month) and members and all(
            SYMBOL.match(symbol) and isinstance(n, int) and not isinstance(n, bool) and n > 0
            for symbol, n in members.items()) for month, members in universe["months"].items())
    except (AttributeError, KeyError, TypeError, ValueError):
        ok = False
    if not ok:
        raise ValueError(f"{path} is not a well-formed {UNIVERSE_SCHEMA} file")
    universe["file_sha256"] = sha256_hex(payload)
    return universe


def read_daily_collection(dataset_dir: Path):
    """(rows, naming date, source) from a materialized broad-universe daily dataset (coverage.py materialize)."""
    import duckdb  # the research runtime has DuckDB 1.5.5 (broad-universe README); the backfill itself is stdlib-only
    required = ("daily.parquet", "plan.json", "ledger.jsonl", "identity-dedup.json")
    missing = [name for name in required if not (dataset_dir / name).is_file()]
    if missing:
        raise ValueError(f"{dataset_dir} lacks {missing}: build the universe from a materialized, "
                         "identity-deduplicated daily dataset")
    plan_names = [name for name in ("plan.json", "plan-supplement.json") if (dataset_dir / name).is_file()]
    plans = [json.loads((dataset_dir / name).read_text()) for name in plan_names]
    stamps = []
    with open(dataset_dir / "ledger.jsonl", encoding="utf-8") as handle:
        for line in handle:
            stamp = json.loads(line).get("recorded_at") if line.strip() else None
            if stamp:
                stamps.append(stamp)
    naming = collection_naming_date(plans, stamps)
    parquet = str(dataset_dir / "daily.parquet").replace("'", "''")
    daily = f"(SELECT symbol, session_date FROM read_parquet('{parquet}') WHERE in_raw OR in_all)"
    con = duckdb.connect()
    rows = con.execute(f"SELECT strftime(session_date, '%Y-%m'), symbol, count(*)::INTEGER FROM {daily} "
                       "GROUP BY ALL ORDER BY 1, 2").fetchall()
    first, last = con.execute(f"SELECT min(session_date), max(session_date) FROM {daily}").fetchone()
    by_year = con.execute(f"SELECT year(last_bar)::INTEGER, count(*)::INTEGER FROM (SELECT symbol, "
                          f"max(session_date) AS last_bar FROM {daily} GROUP BY symbol) GROUP BY ALL ORDER BY 1").fetchall()
    con.close()
    source = {"collection": "broad-universe daily dataset (coverage.py materialize)",
              "daily_parquet_sha256": file_sha256(dataset_dir / "daily.parquet"),
              "identity_dedup_sha256": file_sha256(dataset_dir / "identity-dedup.json"),
              "ledger_sha256": file_sha256(dataset_dir / "ledger.jsonl"),
              "plans_sha256": {name: file_sha256(dataset_dir / name) for name in plan_names},
              "plans_asof": sorted({str(plan.get("asof")) for plan in plans}),
              "requests_recorded": [min(stamps), max(stamps)],
              "first_session": first.isoformat(), "last_session": last.isoformat(),
              "symbols_by_last_bar_year": {str(year): count for year, count in by_year}}
    return rows, naming, source


# --------------------------------------------------------------------------- stock_bars_1min tasks and page capture


def months_between(start: date, end: date) -> list:
    months, year, month = [], start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def et_utc(day: date, clock: dtime, fraction: str = "") -> str:
    """New York wall-clock time as the RFC-3339 UTC text the bars API takes (the offset follows DST)."""
    moment = datetime.combine(day, clock, ET).astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S") + (f".{fraction}" if fraction else "") + "Z"


def plan_month_tasks(universe: dict, start: date, end: date, batch_size: int) -> list:
    """Tasks of `batch_size` symbols x one month, each month's symbols in sorted order, window clipped to the span."""
    covers = date.fromisoformat(universe["covers_through"])
    if end > covers:
        raise Refused(f"the universe covers sessions through {covers}; --end {end} would miss symbols first listed "
                      "after that: build a newer universe or end the span there")
    tasks = []
    for month in months_between(start, end):
        members = universe["months"].get(month)
        if not members:
            raise Refused(f"the universe has no symbols for {month}")
        year, number = int(month[:4]), int(month[5:])
        first = max(date(year, number, 1), start)
        last = min(date(year + number // 12, number % 12 + 1, 1) - timedelta(days=1), end)
        window = {"start": et_utc(first, dtime(4, 0)), "end": et_utc(last, dtime(19, 59, 59), "999999999")}
        symbols = sorted(members)
        for index in range(0, len(symbols), batch_size):
            chunk = symbols[index:index + batch_size]
            tasks.append({"task": f"{month}-b{index // batch_size:04d}", "month": month, "symbols": chunk,
                          "symbol_sessions": sum(members[symbol] for symbol in chunk), **window})
    return tasks


@functools.lru_cache(maxsize=None)
def _new_york_hour(utc_hour: str) -> int:
    return datetime.fromisoformat(f"{utc_hour}:00:00+00:00").astimezone(ET).hour


def outside_session_window(t: str) -> bool:
    """True for a bar whose start (UTC, as Alpaca stamps it) falls outside 04:00-20:00 New York time."""
    return not 4 <= _new_york_hour(t[:13]) < 20


def task_dir(task: dict) -> str:
    month, batch = task["task"].rsplit("-", 1)
    return f"{month[:4]}/{month[5:]}/{batch}"


def page_task(client: Client, dataset: str, task: dict, root: Path, asof: str, fingerprint: str) -> dict:
    """Page one task to its terminal page, writing each wire page (gzip, fsynced) as it arrives; returns its manifest
    row, which carries the dataset's scope fingerprint so every task row names the scope it was collected under."""
    spec = DATASETS[dataset]
    rel = task_dir(task)
    final = root / dataset / rel
    part = final.with_name(final.name + ".part")
    if part.exists():
        shutil.rmtree(part)  # an interrupted attempt's pages were never recorded: fetch them again
    part.mkdir(parents=True, mode=0o700)
    params = {"symbols": ",".join(task["symbols"]), **spec["params"], "asof": asof,
              "start": task["start"], "end": task["end"]}
    wanted, unexpected, seen, by_symbol = set(task["symbols"]), set(), set(), collections.Counter()
    pages, quarantine, quarantined, bars, token, started = [], [], 0, 0, None, time.monotonic()
    while True:
        wire, encoding = client.fetch(spec["path"], {**params, **({"page_token": token} if token else {})},
                                      accept_gzip=True)
        fetched_at = utc_now()
        body_bytes = gzip.decompress(wire) if encoding == "gzip" else wire
        stored = wire if encoding == "gzip" else gzip.compress(wire, mtime=0)
        body = json.loads(body_bytes)
        series = body.get(spec["key"]) or {}
        if not isinstance(series, dict):
            raise ValueError(f"{task['task']}: '{spec['key']}' is not an object keyed by symbol")
        count = 0
        for symbol, items in series.items():
            if symbol not in wanted:
                unexpected.add(symbol)
            for bar in items:
                count += 1
                by_symbol[symbol] += 1
                if outside_session_window(bar["t"]):
                    quarantined += 1  # a row stays bounded however many the provider returns (overnight prints)
                    if len(quarantine) < QUARANTINE_EXAMPLES:
                        quarantine.append({"page": len(pages), "symbol": symbol, "t": bar["t"]})
        name = f"p{len(pages):05d}.json.gz"
        write_private(part / name, stored, sync_dir=False)  # the task directory is fsynced once, below
        next_token = body.get("next_page_token") or None
        pages.append({"page": len(pages), "page_token": token, "file": f"{rel}/{name}", "content_encoding": encoding,
                      "wire_bytes": len(wire), "bytes": len(stored), "sha256": sha256_hex(stored),
                      "json_bytes": len(body_bytes), "json_sha256": sha256_hex(body_bytes), "bars": count,
                      "next_page_token": next_token, "fetched_at": fetched_at})
        bars += count
        if next_token is None:
            break
        if next_token in seen or len(pages) >= MAX_PAGES_PER_TASK:
            raise RuntimeError(f"{task['task']}: the page chain does not terminate ({len(pages)} pages)")
        seen.add(next_token)
        token = next_token
    fsync_dir(part)
    if final.exists():
        shutil.rmtree(final)  # a completed attempt whose manifest row a crash lost
    os.replace(part, final)
    fsync_dir(final.parent)
    return {"task": task["task"], "month": task["month"], "symbols": len(task["symbols"]),
            "symbols_sha256": symbols_digest(task["symbols"]), "scope_fingerprint": fingerprint, "params": params,
            "pages": pages, "bars": bars, "bars_by_symbol": dict(sorted(by_symbol.items())),
            "symbols_without_bars": sorted(wanted - set(by_symbol)), "quarantined": quarantined,
            "quarantine": quarantine, "unexpected_symbols": sorted(unexpected), "fetched_at": utc_now(),
            "seconds": round(time.monotonic() - started, 3)}


def scope_rows(manifest: Path, fingerprint: str):
    """Manifest rows collected under `fingerprint`. A torn line, or a row naming another scope, is skipped, so its
    task counts as not done and is fetched again."""
    if manifest.exists():
        with open(manifest, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("scope_fingerprint") == fingerprint:
                    yield row


def row_intact(ds_dir: Path, row: dict) -> bool:
    """Every page file the row records exists at its recorded size (a crash can leave a row whose pages never reached
    the disk; verify re-hashes the content)."""
    try:
        return bool(row["pages"]) and all((ds_dir / page["file"]).stat().st_size == page["bytes"]
                                          for page in row["pages"])
    except (KeyError, TypeError, OSError):
        return False


def done_tasks(ds_dir: Path, fingerprint: str) -> dict:
    """{task: (symbols_sha256, stored page bytes)} for the tasks completed under this scope. A task's last row
    decides, and it counts only while its page files are intact."""
    done = {}
    for row in scope_rows(ds_dir / "manifest.jsonl", fingerprint):
        task = row.get("task")
        try:
            entry = (row["symbols_sha256"], sum(page["bytes"] for page in row["pages"]))
        except (KeyError, TypeError):
            entry = None
        if entry is not None and row_intact(ds_dir, row):
            done[task] = entry
        else:
            done.pop(task, None)
    return done


def task_rows(manifest: Path, wanted: set, fingerprint: str) -> dict:
    return {row["task"]: row for row in scope_rows(manifest, fingerprint) if row.get("task") in wanted}


# --------------------------------------------------------------------------- pilot and disk gate


def pilot_tasks(tasks: list, count: int) -> list:
    """`count` tasks spread evenly over the planned order (month, then batch), so a pilot samples the whole span."""
    if count >= len(tasks):
        return list(tasks)
    return [tasks[int((k + 0.5) * len(tasks) / count)] for k in range(count)]


def peak_rss_bytes() -> int:
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)  # getrusage(2): kilobytes on Linux


def disk_bytes(path: Path) -> int:
    info = path.stat()
    return max(info.st_size, getattr(info, "st_blocks", 0) * 512)


def disk_problem(remaining: int, free: int, floor: int, normalized: int = 0) -> str | None:
    """Why storing `remaining` more raw bytes does not fit `free` bytes, or None when it does: the remainder must stay
    within FREE_DISK_SHARE of free disk and leave the floor plus the normalized layer's reserve free."""
    if remaining > FREE_DISK_SHARE * free:
        return (f"the remaining projected {remaining} bytes exceed {FREE_DISK_SHARE:.0%} of free disk "
                f"({int(FREE_DISK_SHARE * free)} of {free} bytes free now)")
    if free - remaining < floor + normalized:
        return (f"storing the remaining projected {remaining} bytes would leave {free - remaining} of {free} bytes "
                f"free, under the {floor}-byte floor plus the {normalized}-byte normalized-layer reserve")
    return None


def pilot_report(ds_dir: Path, dataset: str, fingerprint: str, tasks: list, selected: list, rows: dict, *,
                 free_bytes: int, stored_bytes: int, disk_floor: int, rss_bytes: int, seconds: float, requests: int,
                 fetched_now: int, rate: float | None) -> dict:
    """Measured pilot figures and the full-span projection. Disk: the larger of two scalings of the pilot's disk use
    (page files plus manifest rows), per planned task and per bar with bars scaled by the universe's symbol-sessions;
    the verdict weighs what the span still needs (the projection less the `stored_bytes` already stored under this
    scope) against free disk. Calls: the pilot's pages scaled the same two ways, against D2's estimate."""
    limit = DATASETS[dataset]["params"]["limit"]
    fetched = [rows[t["task"]] for t in selected if t["task"] in rows]
    pages = [page for row in fetched for page in row["pages"]]
    bars = sum(row["bars"] for row in fetched)
    wire = sum(page["wire_bytes"] for page in pages)  # as received: gzip bytes, or the identity JSON body
    stored = sum(page["bytes"] for page in pages)  # as written: identity pages are gzip-wrapped locally
    decoded = sum(page["json_bytes"] for page in pages)
    disk = (sum(disk_bytes(ds_dir / page["file"]) for page in pages)
            + sum(len(json.dumps(row, sort_keys=True)) + 1 for row in fetched))
    full = [page["bars"] / limit for page in pages if page["next_page_token"]]
    ideal = sum(max(1, math.ceil(row["bars"] / limit)) for row in fetched)
    requested = sum(row["symbols"] for row in fetched)
    silent = [f"{row['month']} {symbol}" for row in fetched for symbol in row["symbols_without_bars"]]
    quarantined = [row["quarantined"] for row in fetched]

    def ratio(a, b):
        return round(a / b, 3) if b else None

    report = {"schema": PILOT_SCHEMA, "dataset": dataset, "fingerprint": fingerprint, "created_at": utc_now(),
              "pilot_tasks": [t["task"] for t in selected], "free_disk_share": FREE_DISK_SHARE,
              "disk_floor_bytes": disk_floor, "projection": None,
              "metrics": {"tasks": len(fetched), "fetched_in_this_run": fetched_now, "pages": len(pages),
                          "pages_by_encoding": dict(sorted(collections.Counter(
                              page["content_encoding"] for page in pages).items())),
                          "bars": bars, "wire_bytes": wire, "stored_bytes": stored, "json_bytes": decoded,
                          "disk_bytes": disk, "wire_bytes_per_page": ratio(wire, len(pages)),
                          "stored_bytes_per_page": ratio(stored, len(pages)),
                          "json_bytes_per_page": ratio(decoded, len(pages)), "wire_bytes_per_bar": ratio(wire, bars),
                          "stored_bytes_per_bar": ratio(stored, bars), "disk_bytes_per_bar": ratio(disk, bars),
                          "bars_per_page": ratio(bars, len(pages)), "quarantined_bars": sum(quarantined),
                          "quarantined_bars_per_task_max": max(quarantined, default=0),
                          "full_page_share_nonterminal": round(sum(full) / len(full), 4) if full else None,
                          "calls_over_ideal": ratio(len(pages), ideal),
                          "symbol_months_requested": requested, "symbol_months_without_bars": len(silent),
                          "share_without_bars": ratio(len(silent), requested), "without_bars_examples": silent[:20],
                          "peak_rss_bytes": rss_bytes, "peak_rss_mib": round(rss_bytes / 2 ** 20, 1),
                          "requests": requests, "seconds": round(seconds, 3),
                          "calls_per_minute": ratio(requests * 60, seconds)},
              # D2's overturn conditions: either one switches the design to per-day tasks (verdict "overturn")
              "flags": {"pages_under_95pct_full": (sum(full) / len(full) < D2_MIN_FULL) if full else None,
                        "calls_over_1_3x_d2_estimate": None}}
    missing = [t["task"] for t in selected if t["task"] not in rows]
    pilot_sessions = sum(t["symbol_sessions"] for t in selected)
    if missing:
        return {**report, "verdict": "incomplete", "reason": f"{len(missing)} pilot task(s) not completed: {missing[:5]}"}
    if not bars or not pilot_sessions:
        return {**report, "verdict": "refused", "reason": "the pilot tasks returned no bars, so nothing projects the span"}
    total_sessions = sum(t["symbol_sessions"] for t in tasks)
    projected_bars = bars / pilot_sessions * total_sessions
    by_sessions, by_tasks = projected_bars * disk / bars, disk / len(fetched) * len(tasks)
    projected = math.ceil(max(by_sessions, by_tasks))
    calls = math.ceil(max(len(pages) / pilot_sessions * total_sessions, len(pages) / len(fetched) * len(tasks)))
    calls_upper = math.ceil(projected_bars / limit) + len(tasks)
    d2_calls = math.ceil(D2_BARS_PER_SYMBOL_SESSION * total_sessions / limit) + len(tasks)
    remaining = max(0, projected - stored_bytes)
    normalized = math.ceil(projected_bars * NORMALIZED_BYTES_PER_BAR)
    report["flags"]["calls_over_1_3x_d2_estimate"] = calls > D2_MAX_CALLS * d2_calls
    report["projection"] = {"planned_tasks": len(tasks), "symbol_sessions_total": total_sessions,
                            "symbol_sessions_pilot": pilot_sessions,
                            "bars_per_symbol_session": round(bars / pilot_sessions, 3),
                            "projected_bars": round(projected_bars),
                            "projected_disk_bytes_by_sessions": math.ceil(by_sessions),
                            "projected_disk_bytes_by_tasks": math.ceil(by_tasks),
                            "projected_disk_bytes": projected, "projected_disk_gib": round(projected / 2 ** 30, 2),
                            "stored_bytes": stored_bytes, "remaining_disk_bytes": remaining,
                            "normalized_bytes_per_bar": NORMALIZED_BYTES_PER_BAR,
                            "normalized_reserve_bytes": normalized,
                            "free_disk_bytes": free_bytes, "threshold_bytes": int(FREE_DISK_SHARE * free_bytes),
                            "projected_calls": calls, "projected_calls_upper": calls_upper,
                            "d2_estimate_calls": d2_calls,
                            "projected_minutes_at_rate": round(max(calls, calls_upper) / rate, 1) if rate else None}
    problem = disk_problem(remaining, free_bytes, disk_floor, normalized)
    if problem:
        return {**report, "verdict": "refused", "reason": problem}
    raised = sorted(name for name, value in report["flags"].items() if value)
    if raised:
        return {**report, "verdict": "overturn",
                "reason": f"D2 overturn condition(s) {raised}: D2 switches to per-day tasks. A month-task full run "
                          "needs --accept-pilot-flags REASON"}
    return {**report, "verdict": "pass", "reason": f"the remaining projected {remaining} bytes fit "
                                                   f"{FREE_DISK_SHARE:.0%} of the {free_bytes} bytes free and leave the "
                                                   f"{disk_floor}-byte floor plus the {normalized}-byte normalized-layer "
                                                   "reserve"}


def require_pilot(ds_dir: Path, fingerprint: str, stored_bytes: int, free_bytes: int, disk_floor: int,
                  accept_flags: str | None = None) -> tuple[int, int, dict]:
    """A full run needs a pilot of the same scope whose verdict is "pass" (or "overturn" with --accept-pilot-flags),
    and the remaining projection must still fit free disk. Returns (projected raw disk bytes, the normalized-layer
    reserve, the pilot report)."""
    path = ds_dir / "pilot.json"
    if not path.exists():
        raise Refused(f"{ds_dir.name} has no pilot: run the same command with --pilot 2 first")
    try:
        report = json.loads(path.read_text())
        same_scope, verdict, reason = report.get("fingerprint") == fingerprint, report.get("verdict"), report.get("reason")
        projected = normalized = None
        if verdict in ("pass", "overturn"):
            projected = int(report["projection"]["projected_disk_bytes"])
            normalized = int(report["projection"]["normalized_reserve_bytes"])
        raised = sorted(name for name, value in report["flags"].items() if value)
    except (ValueError, AttributeError, KeyError, TypeError):
        raise Refused(f"{path} is unreadable: run --pilot again") from None
    if not same_scope:
        raise Refused(f"{path} was measured under a different scope: run --pilot again")
    if verdict == "overturn" and not accept_flags:
        raise Refused(f"the pilot's verdict is 'overturn': {raised} hold, so D2 switches to per-day tasks. Run month "
                      "tasks anyway only with --accept-pilot-flags REASON")
    if verdict not in ("pass", "overturn"):
        raise Refused(f"the pilot's verdict is {verdict!r}: {reason}")
    problem = disk_problem(max(0, projected - stored_bytes), free_bytes, disk_floor, normalized)
    if problem:
        raise Refused(problem)
    return projected, normalized, report


# --------------------------------------------------------------------------- runs


def drain_pool(client: Client, workers: int, items: list, work, record, fail, stop_reason, totals: dict) -> None:
    """Run work(item) for each item with at most `workers` in flight, so at most `workers` rows are held at once (a
    row is dropped once recorded) and a stop leaves at most `workers` tasks to finish. stop_reason() is asked before
    each submission: a reason stops submission and the items not submitted are counted as stopped. Only this thread
    calls record(row) (the manifest append) and fail(item, exc). Any exception here, such as a failed manifest append
    or Ctrl-C, halts the client and cancels queued work before it propagates, so nothing is fetched that could not be
    recorded."""
    pending, position = {}, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        try:
            while True:
                while position < len(items) and len(pending) < workers:
                    reason = stop_reason()
                    if reason:
                        totals["stopped"] += len(items) - position
                        totals["stop_reason"] = reason
                        position = len(items)
                        break
                    pending[pool.submit(work, items[position])] = items[position]
                    position += 1
                if not pending:
                    return
                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    item = pending.pop(future)
                    try:
                        row = future.result()
                    except Exception as exc:  # recorded and retried on the next run
                        fail(item, exc)
                        continue
                    record(row)
        except BaseException:
            client.halt.set()
            pool.shutdown(wait=True, cancel_futures=True)
            raise


def day_task(client: Client, dataset: str, day: date, root: Path) -> dict:
    spec = DATASETS[dataset]
    first, last = spec["window_utc"]
    params = {**spec["params"], "start": f"{day.isoformat()}T{first}Z", "end": f"{day.isoformat()}T{last}Z"}
    records, pages, token = [], 0, None
    while True:
        body = client.get(spec["path"], {**params, **({"page_token": token} if token else {})})
        records.extend(body.get(spec["key"]) or [])
        pages += 1
        token = body.get("next_page_token")
        if not token:
            break
    payload = gzip.compress("".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in records).encode(), mtime=0)
    target = root / dataset / day_file(day.isoformat())
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_private(target, payload)  # fsynced with its directory before the row that names it is appended
    return {"day": day.isoformat(), "records": len(records), "pages": pages, "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload), "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def done_days(ds_dir: Path) -> set:
    """Days whose last manifest row names a day file that exists at its recorded size. A torn line or a malformed row
    is skipped; a row whose file is missing or has another size (a crash kept the row but not the file) leaves its day
    to be fetched again."""
    manifest, days = ds_dir / "manifest.jsonl", set()
    if not manifest.exists():
        return days
    with open(manifest, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                row = json.loads(line)
                day, size = row["day"], row["bytes"]
                path = ds_dir / day_file(day)
            except (ValueError, KeyError, TypeError):
                continue  # a torn last line or a malformed row: its day is fetched again unless another row holds it
            try:
                intact = path.stat().st_size == size
            except OSError:
                intact = False
            if intact:
                days.add(day)
            else:
                days.discard(day)
    return days


def run(client: Client, dataset: str, start: date, end: date, root: Path, workers: int, stop_file: Path | None = None,
        *, universe: dict | None = None, pilot: int = 0, code: str | None = None, disk_free=None, peak_rss=None,
        rate: float | None = None, accept_flags: str | None = None) -> dict:
    spec = DATASETS[dataset]
    if end < start:
        raise Refused(f"--end {end} precedes --start {start}")
    if not 0 <= pilot <= MAX_PILOT_TASKS:
        raise Refused(f"--pilot {pilot}: a pilot samples at most {MAX_PILOT_TASKS} tasks, because it runs before the "
                      "disk gate")
    if spec["capture"] == "records" and (universe is not None or pilot or accept_flags is not None):
        raise Refused(f"{dataset} is not symbol-scoped: it takes no --universe, --pilot or --accept-pilot-flags")
    if spec["capture"] == "pages" and universe is None:
        raise Refused(f"{dataset} needs --universe (built by `backfill.py universe`)")
    if pilot and accept_flags is not None:
        raise Refused("--accept-pilot-flags applies to a full run, not a pilot")
    refuse_inside_git_work_tree(root)
    if stop_file is not None and stop_file.exists():
        raise Refused(f"{stop_file} exists: remove it to start a run (touching it drains a running one)")
    lease = HOST_LEASE  # read at call time: one backfill per host, whatever the dataset or --out
    lease.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    holder = json.dumps({"pid": os.getpid(), "dataset": dataset, "out": str(root), "started_at": utc_now()})
    ds_dir = root / dataset
    with exclusive_lock(lease, holder):
        refuse_headerless(ds_dir)  # before the lock file: a refused legacy directory is left untouched
        ds_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with exclusive_lock(ds_dir / ".lock"):
            if spec["capture"] == "records":
                check_scope(ds_dir, dataset_scope(dataset, start, end, code=code), {"created_at": utc_now()})
                return run_days(client, dataset, start, end, root, workers, stop_file)
            tasks = plan_month_tasks(universe, start, end, spec["batch_size"])
            scope = dataset_scope(dataset, start, end, tasks=tasks, asof=universe["naming_asof"], code=code)
            # the ids hash to scope.planned, so verify can list planned tasks with no row (a news span lists its days)
            provenance = {"created_at": utc_now(), "universe": {key: universe.get(key) for key in
                          ("file_sha256", "naming_asof", "covers_through", "rule", "source", "summary")},
                          "planned_task_ids": [t["task"] for t in tasks]}
            if not pilot and read_header(ds_dir) is None:
                # without a header there is no pilot of any scope: refuse before a header pins this (maybe mistyped) scope
                raise Refused(f"{dataset} has no pilot: run the same command with --pilot 2 first")
            header = check_scope(ds_dir, scope, provenance)
            return run_pages(client, dataset, tasks, root, workers, stop_file, header["fingerprint"],
                             universe["naming_asof"], pilot, disk_free or (lambda path: shutil.disk_usage(path).free),
                             peak_rss or peak_rss_bytes, rate, accept_flags)


def run_days(client: Client, dataset: str, start: date, end: date, root: Path, workers: int,
             stop_file: Path | None = None) -> dict:
    manifest = root / dataset / "manifest.jsonl"
    repair_manifest_tail(manifest)
    skip = done_days(root / dataset)
    days = span_days(start, end)
    todo = [d for d in days if d.isoformat() not in skip]
    totals = {"days": 0, "records": 0, "failed": [], "stopped": 0, "stop_reason": None}

    def stop_reason():
        return f"{stop_file} exists" if stop_file is not None and stop_file.exists() else None

    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", buffering=1) as log:
        def record(row):
            append_row(log, row)
            totals["days"] += 1
            totals["records"] += row["records"]

        def fail(day, exc):
            totals["failed"].append({"day": day.isoformat(), "error": f"{type(exc).__name__}: {str(exc)[:120]}"})

        drain_pool(client, workers, todo, lambda day: day_task(client, dataset, day, root), record, fail, stop_reason,
                   totals)
    return {**totals, "skipped_already_done": len(days) - len(todo), "requests": client.requests,
            "throttled": client.throttled, "ratelimit_floor_pauses": client.ratelimit_floor_pauses}


def run_pages(client: Client, dataset: str, tasks: list, root: Path, workers: int, stop_file: Path | None,
              fingerprint: str, asof: str, pilot: int, disk_free, peak_rss, rate: float | None,
              accept_flags: str | None) -> dict:
    ds_dir = root / dataset
    manifest = ds_dir / "manifest.jsonl"
    floor = DISK_FLOOR  # read at call time
    repair_manifest_tail(manifest)
    done = done_tasks(ds_dir, fingerprint)
    state = {"stored": sum(size for _, size in done.values())}
    selected = pilot_tasks(tasks, pilot) if pilot else tasks
    projected, normalized, accepted = None, 0, None
    if not pilot:
        projected, normalized, report = require_pilot(ds_dir, fingerprint, state["stored"], disk_free(ds_dir), floor,
                                                      accept_flags)
        if report["verdict"] == "overturn":
            accepted = accept_flags
            if (report.get("acknowledged") or {}).get("reason") != accept_flags:
                report["acknowledged"] = {"reason": accept_flags, "at": utc_now(),
                                          "flags": sorted(name for name, value in report["flags"].items() if value)}
                write_private(ds_dir / "pilot.json", (json.dumps(report, indent=1, sort_keys=True) + "\n").encode())
    todo = [t for t in selected if done.get(t["task"], (None,))[0] != symbols_digest(t["symbols"])]
    totals = {"tasks": 0, "pages": 0, "bars": 0, "quarantined": 0, "failed": [], "stopped": 0, "stop_reason": None}
    started, requests_before = time.monotonic(), client.requests

    def stop_reason():
        """Checked before each task starts: STOP, then the disk (re-read every time, since the projection comes from
        a few pilot tasks and the filesystem is shared with the engine's state)."""
        if stop_file is not None and stop_file.exists():
            return f"{stop_file} exists"
        free = disk_free(ds_dir)
        if free < floor:
            return f"free disk fell to {free} bytes, under the {floor}-byte floor"
        if projected is not None:
            remaining = max(0, projected - state["stored"])
            if free - remaining < floor + normalized:
                return (f"free disk fell to {free} bytes: the remaining projected {remaining} bytes would leave less "
                        f"than the {floor}-byte floor plus the {normalized}-byte normalized-layer reserve")
            if state["stored"] > DISK_OVERRUN * projected:
                return (f"the {state['stored']} bytes stored exceed {DISK_OVERRUN}x the pilot's projection "
                        f"({projected} bytes): the pilot under-sampled the span")
        return None

    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", buffering=1) as log:
        def record(row):
            append_row(log, row)
            totals["tasks"] += 1
            totals["pages"] += len(row["pages"])
            totals["bars"] += row["bars"]
            totals["quarantined"] += row["quarantined"]
            state["stored"] += sum(page["bytes"] for page in row["pages"])

        def fail(task, exc):
            totals["failed"].append({"task": task["task"], "error": f"{type(exc).__name__}: {str(exc)[:160]}"})

        drain_pool(client, workers, todo, lambda task: page_task(client, dataset, task, root, asof, fingerprint),
                   record, fail, stop_reason, totals)
    result = {**totals, "planned_tasks": len(tasks), "selected_tasks": len(selected),
              "skipped_already_done": len(selected) - len(todo), "requests": client.requests,
              "throttled": client.throttled, "ratelimit_remaining_min": client.ratelimit_remaining_min,
              "ratelimit_floor_pauses": client.ratelimit_floor_pauses, "pilot_flags_accepted": accepted}
    if pilot:
        rows = {task: row for task, row in task_rows(manifest, {t["task"] for t in selected}, fingerprint).items()
                if row_intact(ds_dir, row)}
        report = pilot_report(ds_dir, dataset, fingerprint, tasks, selected, rows, free_bytes=disk_free(ds_dir),
                              stored_bytes=state["stored"], disk_floor=floor, rss_bytes=peak_rss(),
                              seconds=time.monotonic() - started, requests=client.requests - requests_before,
                              fetched_now=totals["tasks"], rate=rate)
        write_private(ds_dir / "pilot.json", (json.dumps(report, indent=1, sort_keys=True) + "\n").encode())
        result["pilot"] = report
    return result


# --------------------------------------------------------------------------- verification


def planned_task_ids(header: dict, capture: str) -> list:
    """The planned task ids of a header: a page dataset's provenance list, a record dataset's span days. ValueError
    when they do not match the scope's planned count and sha256 (the provenance is not fingerprinted; the scope is)."""
    scope = header["scope"]
    if capture == "pages":
        ids = header["provenance"]["planned_task_ids"]
    else:
        span = scope["span"]
        ids = [d.isoformat() for d in span_days(date.fromisoformat(span["start"]), date.fromisoformat(span["end"]))]
    planned = scope["planned"]
    if not isinstance(ids, list) or len(ids) != planned["tasks"] or sha256_hex(canonical(ids)) != planned["task_ids_sha256"]:
        raise ValueError("the planned task ids do not match the scope's planned count and sha256")
    return ids


def verify_dataset(root: Path, dataset: str, examples: int = 20) -> dict:
    """Re-hash every recorded file against the manifest. For page capture, also check the scope header and that each
    task's row names its fingerprint, and decode every page: each body's next_page_token must name the next recorded
    page's token (null on the last page), each body must hold the bars the row records for it, and the bodies must sum
    to the row's total and its bars by symbol. A task's (or day's) last row decides; earlier rows for it (a refetch)
    are counted as superseded. Under a header, the recorded tasks are also compared with the scope's planned tasks:
    `complete` is false, and so is `ok`, while any planned task has no row (after a pilot, most of them). A missing
    manifest or a malformed row is reported as a problem. A record-capture dataset may lack a header: the news archive
    predates headers, so its plan is unknown (`complete` null)."""
    spec, ds_dir = DATASETS[dataset], root / dataset
    result = {"dataset": dataset, "scope_header": (ds_dir / "scope.json").exists(), "scope_fingerprint": None,
              "rows": 0, "torn_lines": 0, "malformed_rows": 0, "superseded_rows": 0, "files": 0, "problems": 0,
              "examples": [], "planned_tasks": None, "missing_tasks": None, "missing_examples": [], "complete": None}

    def problem(detail: dict) -> None:
        result["problems"] += 1
        if len(result["examples"]) < examples:
            result["examples"].append(detail)

    def malformed(number: int, detail: str = "malformed manifest row") -> None:
        result["malformed_rows"] += 1
        problem({"line": number, "problem": detail})

    try:
        header = read_header(ds_dir)
    except Refused:
        header = None
        problem({"file": "scope.json", "problem": "unreadable or does not hash to its recorded fingerprint"})
    else:
        if header is None and spec["capture"] == "pages":
            problem({"file": "scope.json", "problem": "missing"})
    fingerprint = result["scope_fingerprint"] = header["fingerprint"] if header else None
    planned = None
    if header is not None:
        try:
            planned = planned_task_ids(header, spec["capture"])
        except (KeyError, TypeError, ValueError, AttributeError):
            problem({"file": "scope.json", "problem": "planned task list missing or does not match the scope"})

    def intact_file(name: str, digest: str) -> bytes | None:
        path = ds_dir / name
        if not path.is_file():
            problem({"file": name, "problem": "missing"})
            return None
        stored = path.read_bytes()
        result["files"] += 1
        if sha256_hex(stored) != digest:
            problem({"file": name, "problem": "sha256 differs from the manifest"})
            return None
        return stored

    manifest = ds_dir / "manifest.jsonl"
    latest = {}  # task or day -> its last row (pages: the line number; one pass to index, one to verify: bounded memory)
    if not manifest.is_file():
        problem({"file": "manifest.jsonl", "problem": "missing"})
    else:
        with open(manifest, "rb") as handle:
            for number, line in enumerate(handle, 1):
                try:
                    row = json.loads(line)
                except ValueError:
                    result["torn_lines"] += 1
                    continue
                result["rows"] += 1
                if spec["capture"] == "records":
                    try:
                        digest, day = row["sha256"], date.fromisoformat(row["day"]).isoformat()
                    except (KeyError, TypeError, ValueError):
                        malformed(number)
                    else:
                        latest[day] = digest
                elif isinstance(row, dict) and isinstance(row.get("task"), str):
                    latest[row["task"]] = number
                else:
                    malformed(number)
        result["superseded_rows"] = result["rows"] - result["malformed_rows"] - len(latest)
        if spec["capture"] == "records":
            for day, digest in latest.items():
                intact_file(day_file(day), digest)
        else:
            wanted = set(latest.values())
            with open(manifest, "rb") as handle:
                for number, line in enumerate(handle, 1):
                    if number in wanted:
                        row = json.loads(line)
                        try:
                            verify_task_row(ds_dir, spec, row, fingerprint, intact_file, problem)
                        except (KeyError, TypeError, AttributeError, ValueError, OSError, EOFError, zlib.error) as exc:
                            malformed(number, f"malformed row or page for {row['task']} ({type(exc).__name__})")
    if planned is not None:
        planned_set = set(planned)
        missing = [task for task in planned if task not in latest]
        for task in sorted(set(latest) - planned_set):
            problem({"task": task, "problem": "not a planned task of the scope"})
        result.update({"planned_tasks": len(planned), "missing_tasks": len(missing),
                       "missing_examples": missing[:examples], "complete": not missing})
    result["ok"] = result["rows"] > 0 and result["problems"] == 0 and result["complete"] is not False
    return result


def verify_task_row(ds_dir: Path, spec: dict, row: dict, fingerprint: str | None, intact_file, problem) -> None:
    task = row.get("task")
    if fingerprint is not None and row.get("scope_fingerprint") != fingerprint:
        problem({"task": task, "problem": "row names another scope fingerprint than the header"})
    pages = row.get("pages") or []
    if not pages or pages[0].get("page_token") is not None:
        problem({"task": task, "problem": "page chain does not start without a page token"})
    decoded_all, counts = True, collections.Counter()
    for index, page in enumerate(pages):
        following = pages[index + 1].get("page_token") if index + 1 < len(pages) else None
        if page.get("next_page_token") != following:
            problem({"task": task, "page": index, "problem": "recorded next_page_token does not name the next page"})
        stored = intact_file(page["file"], page["sha256"])
        if stored is None:
            decoded_all = False
            continue
        body_bytes = gzip.decompress(stored)
        if sha256_hex(body_bytes) != page["json_sha256"]:
            problem({"file": page["file"], "problem": "decoded page sha256 differs from the manifest"})
            decoded_all = False
            continue
        body = json.loads(body_bytes)
        if (body.get("next_page_token") or None) != following:
            problem({"task": task, "page": index,
                     "problem": "page body's next_page_token does not chain to the next recorded page" if following
                     else "last page body carries a next_page_token: the chain was cut short"})
        series = body.get(spec["key"]) or {}
        in_body = 0
        for symbol, items in series.items():
            counts[symbol] += len(items)
            in_body += len(items)
        if in_body != page["bars"]:
            problem({"task": task, "page": index, "problem": "recorded page bars differ from the page body"})
    if sum(page["bars"] for page in pages) != row.get("bars"):
        problem({"task": task, "problem": "page bars do not sum to the task total"})
    if decoded_all and pages:
        if "bars_by_symbol" in row and {s: n for s, n in counts.items() if n} != row["bars_by_symbol"]:
            problem({"task": task, "problem": "bars by symbol differ from the page bodies"})
        requested = set(str(row.get("params", {}).get("symbols", "")).split(","))
        if "symbols_without_bars" in row and sorted(requested - {s for s, n in counts.items() if n}) != row["symbols_without_bars"]:
            problem({"task": task, "problem": "symbols without bars differ from the page bodies"})


# --------------------------------------------------------------------------- command line


def load_credentials(env_file: Path):
    """The mover-early-entry reader: an owner-only 0600 file holding the paper key pair only."""
    path = HERE.parent / "mover-early-entry" / "collect.py"
    spec = importlib.util.spec_from_file_location("mover_early_entry_collect", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.credentials(env_file)


def universe_main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="backfill.py universe",
                                 description="Build the asof-aware monthly universe from a broad-universe daily dataset "
                                             "(needs DuckDB; no network).")
    ap.add_argument("--daily-dataset", type=Path, required=True,
                    help="directory holding daily.parquet, plan.json, ledger.jsonl and identity-dedup.json")
    ap.add_argument("--out", type=Path, required=True, help="universe JSON to create; an existing file is never replaced")
    a = ap.parse_args(argv)
    try:
        refuse_inside_git_work_tree(a.out)  # it is derived from licensed daily bars
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    if a.out.exists():
        raise SystemExit(f"{a.out} exists; a universe file is never replaced")
    rows, naming, source = read_daily_collection(a.daily_dataset)
    universe = build_universe(rows, naming, source)
    payload = canonical(universe) + b"\n"
    write_private(a.out, payload)
    print(json.dumps({"out": str(a.out), "sha256": sha256_hex(payload), "naming_asof": naming,
                      "covers_through": universe["covers_through"], "first_month": universe["first_month"],
                      **universe["summary"], "symbols_by_last_bar_year": source["symbols_by_last_bar_year"]}))
    return 0


def verify_main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="backfill.py verify", description="Re-hash a dataset against its manifest (no network).")
    ap.add_argument("dataset", choices=sorted(DATASETS))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    result = verify_dataset(a.out, a.dataset)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


def main(argv=None, opener=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["universe"]:
        return universe_main(argv[1:])
    if argv[:1] == ["verify"]:
        return verify_main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dataset", choices=sorted(DATASETS))
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start", type=date.fromisoformat, required=True)
    ap.add_argument("--end", type=date.fromisoformat, required=True)
    ap.add_argument("--rate", type=float, default=3000.0, help="requests per minute for this run (the account limit is shared)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--universe", type=Path, help="asof-aware monthly universe (stock_bars_1min), built by `backfill.py universe`")
    ap.add_argument("--pilot", type=int, default=0, metavar="N",
                    help=f"fetch N (at most {MAX_PILOT_TASKS}) evenly spread tasks of the span, report bytes, bytes per "
                         "bar and peak RSS, project the span's disk use and record the verdict a full run requires")
    ap.add_argument("--accept-pilot-flags", metavar="REASON",
                    help="run month tasks although the pilot's verdict is 'overturn' (D2's per-day switch); the reason "
                         "is recorded in pilot.json. Never overrides a disk refusal")
    a = ap.parse_args(argv)
    if not 1 <= a.rate <= MAX_RATE:
        raise SystemExit("--rate must leave headroom for the live monitor, scans and the engine (at most 6000/min)")
    if a.workers < 1 or not 0 <= a.pilot <= MAX_PILOT_TASKS:
        raise SystemExit(f"--workers must be at least 1 and --pilot between 0 and {MAX_PILOT_TASKS}")
    if DATASETS[a.dataset]["capture"] == "pages" and a.universe is None:
        raise SystemExit(f"{a.dataset} needs --universe (built by `backfill.py universe`)")
    if a.accept_pilot_flags is not None and (a.pilot or DATASETS[a.dataset]["capture"] != "pages"
                                             or not a.accept_pilot_flags.strip()):
        raise SystemExit("--accept-pilot-flags REASON takes a non-empty reason and applies to a full page-capture run")
    try:
        refuse_inside_git_work_tree(a.out)  # before the universe or the credentials are read
        try:
            universe = load_universe(a.universe) if a.universe else None
        except ValueError as exc:
            raise SystemExit(str(exc))
        key, secret = load_credentials(a.env_file)
        client = Client({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, Bucket(a.rate),
                        **({"opener": opener} if opener else {}))
        started = time.time()
        result = run(client, a.dataset, a.start, a.end, a.out, a.workers, a.out / "STOP", universe=universe,
                     pilot=a.pilot, rate=a.rate, accept_flags=a.accept_pilot_flags)
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    result["seconds"] = round(time.time() - started, 1)
    print(json.dumps(result))
    if result["failed"]:
        return EXIT_FAILED
    if result["stopped"]:
        return EXIT_STOPPED
    if a.pilot:
        return {"pass": 0, "incomplete": EXIT_FAILED, "overturn": EXIT_OVERTURN}.get(result["pilot"]["verdict"], EXIT_REFUSED)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
