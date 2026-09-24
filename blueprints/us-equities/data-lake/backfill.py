"""Governed, resumable Alpaca historical backfill into the data lake's raw source layer.

  python backfill.py news --env-file ENV --out DIR --start 2015-01-01 --end 2026-09-23 [--rate 3000] [--workers 8]
  python backfill.py universe --daily-dataset DAILY_DIR --out UNIVERSE_JSON        (research runtime with DuckDB)
  python backfill.py stock_bars_1min --env-file ENV --out DIR --universe UNIVERSE_JSON \
      --start 2016-01-01 --end 2026-08-31 [--rate 6000] [--workers 16] --pilot 2   (then the same without --pilot)
  python backfill.py verify DATASET --out DIR

Scope: DIR/<dataset>/scope.json records the sha256 of this file, the endpoint, the fixed request parameters, the
sha256 of the symbol task list and the span. The first run writes it. A run whose scope differs in any field, a header
that no longer hashes to its fingerprint, or a manifest without a header is refused (exit 2) before any request, so
completed work is never reused for another scope (the rule broad-universe/collect_daily.py applies). A lock file
admits one run per dataset at a time.

news keeps the record capture its 2015-2026 archive was collected with: one task per UTC calendar day, the day's
records re-serialized (sorted keys) into DIR/news/<YYYY>/<MM>/<DD>.jsonl.gz, one manifest row per day.

stock_bars_1min (convergence record 2026-09-24, D1-D2): SIP 1-minute bars, raw prices, extended hours, for every
symbol of the asof-aware monthly universe (`universe`: each month's symbols with a daily SIP bar in the deduplicated
broad-universe daily dataset, active and delisted alike, named as of that collection's request date, which becomes
the request `asof`). A task is 100 symbols x one calendar month, from 04:00 ET on the first day to
19:59:59.999999999 ET on the last. Each page is requested with Accept-Encoding: gzip, stored exactly as received and
written as it arrives. The task's manifest row records every page's request parameters (the task parameters plus
its page_token), sha256 and sizes, and lists bars outside 04:00-20:00 ET as quarantined instead of failing the task.
A full run requires a passing pilot for the same scope: --pilot N fetches N evenly spread tasks, reports raw bytes
per page, bytes per bar and peak RSS, and projects the disk the full span needs, refusing above 40% of free disk.

A shared token bucket keeps the whole run under --rate requests per minute (at most 6,000 of the account's
10,000/min data limit measured on 2026-09-24, which every other data client shares), and an HTTP 429 waits for the
limit's reset before retrying. GET only. Normalized Parquet is a separate, later layer.
"""
from __future__ import annotations

import argparse
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DATA = "https://data.alpaca.markets"
ET = ZoneInfo("America/New_York")
MAX_RATE = 6000
FREE_DISK_SHARE = 0.40  # a pilot refuses when the projected full-span disk use exceeds this share of free space
MAX_PAGES_PER_TASK = 2000  # 100 symbols x 23 sessions x 960 minutes fill at most 221 pages of 10,000 bars
SYMBOL = re.compile(r"^[A-Z]+(\.[A-Z]+)?$")  # broad-universe/collect_daily.py DATA_SYMBOL: what the bars API accepts
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
PROVIDER_DEFAULT_ASOF = "provider default (request date)"  # broad-universe plan.json wording
SCOPE_SCHEMA = "data-lake-scope/1"
UNIVERSE_SCHEMA = "data-lake-monthly-universe/1"
PILOT_SCHEMA = "data-lake-pilot/1"
DATASETS = {
    "news": {"path": "/v1beta1/news", "key": "news", "capture": "records", "task": "calendar day (UTC)",
             "params": {"limit": 50, "sort": "asc", "include_content": "true", "exclude_contentless": "false"}},
    "stock_bars_1min": {"path": "/v2/stocks/bars", "key": "bars", "capture": "pages", "task": "symbols x calendar month",
                        "batch_size": 100, "window_et": ["04:00", "19:59:59.999999999"],
                        "params": {"timeframe": "1Min", "feed": "sip", "adjustment": "raw", "limit": 10000,
                                   "sort": "asc"}},
}


class Refused(Exception):
    """A governed refusal, raised before any request for the refused scope."""


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
        wait = start - self.clock()
        if wait > 0:
            self.sleep(wait)

    def pause(self, seconds: float) -> None:
        with self.lock:
            self.paused_until = max(self.paused_until, self.clock() + seconds)


class Client:
    def __init__(self, headers: dict, bucket: Bucket, opener=urllib.request.urlopen, sleep=time.sleep):
        self.headers, self.bucket, self.opener, self.sleep = headers, bucket, opener, sleep
        self.requests = self.throttled = 0
        self.ratelimit_remaining_min = None
        self.lock = threading.Lock()

    def fetch(self, path: str, params: dict, accept_gzip: bool = False) -> tuple[bytes, str]:
        """One GET with bounded retries: (the body exactly as received, its Content-Encoding)."""
        url = f"{DATA}{path}?{urllib.parse.urlencode(params)}"
        headers = {**self.headers, "Accept-Encoding": "gzip"} if accept_gzip else self.headers
        for attempt in range(8):
            self.bucket.acquire()
            with self.lock:
                self.requests += 1
            try:
                with self.opener(urllib.request.Request(url, headers=headers), timeout=60) as r:
                    body, meta = r.read(), getattr(r, "headers", None)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    reset = exc.headers.get("X-Ratelimit-Reset") if exc.headers else None
                    wait = max(1.0, float(reset) - time.time()) if reset and reset.isdigit() else 2.0 ** attempt
                    with self.lock:
                        self.throttled += 1
                    self.bucket.pause(min(wait, 60.0))
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
                with self.lock:
                    low = self.ratelimit_remaining_min
                    self.ratelimit_remaining_min = int(remaining) if low is None else min(low, int(remaining))
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


def write_private(target: Path, payload: bytes) -> None:
    """Atomic owner-only write: a reader sees the previous file or the new one, never a torn one."""
    tmp = target.with_name(target.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
    os.replace(tmp, target)


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
def dataset_lock(ds_dir: Path):
    import fcntl
    fd = os.open(ds_dir / ".lock", os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused(f"another backfill run holds {ds_dir / '.lock'}") from None
        yield
    finally:
        os.close(fd)  # closing the descriptor releases the lock


def unless_stopped(stop_file: Path | None, task, *args):
    """Run one task unless the STOP file exists; checked when the task starts, so STOP drains a running pool."""
    if stop_file is not None and stop_file.exists():
        return None
    return task(*args)


# --------------------------------------------------------------------------- scope header


def dataset_scope(dataset: str, start: date, end: date, tasks: list | None = None, asof: str | None = None,
                  code: str | None = None) -> dict:
    """Every field that changes WHICH records a completed task holds."""
    spec = DATASETS[dataset]
    params = {**spec["params"], **({"asof": asof} if asof else {})}
    task = {"unit": spec["task"], **{k: spec[k] for k in ("batch_size", "window_et") if k in spec}}
    return {"dataset": dataset, "code_sha256": code or code_sha256(), "endpoint": DATA + spec["path"],
            "fixed_params": params, "span": {"start": start.isoformat(), "end": end.isoformat()},
            "symbols_sha256": None if tasks is None else sha256_hex(canonical([[t["task"], t["symbols"]] for t in tasks])),
            "task": task, "capture": spec["capture"]}


def scope_fingerprint(scope: dict) -> str:
    return sha256_hex(canonical(scope))


def refuse_headerless(ds_dir: Path) -> None:
    manifest = ds_dir / "manifest.jsonl"
    if not (ds_dir / "scope.json").exists() and manifest.is_file() and manifest.stat().st_size:
        raise Refused(f"{manifest} has no scope header (collected before scope headers existed), so its scope "
                      "cannot be verified and it is not resumed: collect into a new --out directory.")


def check_scope(ds_dir: Path, scope: dict, provenance: dict) -> dict:
    """Write the dataset's scope header on first use; refuse any later run whose scope differs from it."""
    header_path = ds_dir / "scope.json"
    fingerprint = scope_fingerprint(scope)
    if header_path.exists():
        try:
            recorded = json.loads(header_path.read_text())
            recorded_scope = recorded.get("scope") or {}
            intact = recorded.get("fingerprint") == scope_fingerprint(recorded_scope)
        except (ValueError, AttributeError, TypeError):
            intact = False
        if not intact:
            raise Refused(f"{header_path} is unreadable or does not hash to its recorded fingerprint (edited or corrupt)")
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


def page_task(client: Client, dataset: str, task: dict, root: Path, asof: str) -> dict:
    """Page one task to its terminal page, writing each wire page (gzip) as it arrives; returns its manifest row."""
    spec = DATASETS[dataset]
    rel = task_dir(task)
    final = root / dataset / rel
    part = final.with_name(final.name + ".part")
    if part.exists():
        shutil.rmtree(part)  # an interrupted attempt's pages were never recorded: fetch them again
    part.mkdir(parents=True, mode=0o700)
    params = {"symbols": ",".join(task["symbols"]), **spec["params"], "asof": asof,
              "start": task["start"], "end": task["end"]}
    wanted, unexpected, seen = set(task["symbols"]), set(), set()
    pages, quarantine, bars, token, started = [], [], 0, None, time.monotonic()
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
                if outside_session_window(bar["t"]):
                    quarantine.append({"page": len(pages), "symbol": symbol, "t": bar["t"]})
        name = f"p{len(pages):05d}.json.gz"
        write_private(part / name, stored)
        next_token = body.get("next_page_token")
        pages.append({"page": len(pages), "page_token": token, "file": f"{rel}/{name}", "content_encoding": encoding,
                      "bytes": len(stored), "sha256": sha256_hex(stored), "json_bytes": len(body_bytes),
                      "json_sha256": sha256_hex(body_bytes), "bars": count, "next_page_token": bool(next_token),
                      "fetched_at": fetched_at})
        bars += count
        if not next_token:
            break
        if next_token in seen or len(pages) >= MAX_PAGES_PER_TASK:
            raise RuntimeError(f"{task['task']}: the page chain does not terminate ({len(pages)} pages)")
        seen.add(next_token)
        token = next_token
    if final.exists():
        shutil.rmtree(final)  # a completed attempt whose manifest row a crash lost
    os.replace(part, final)
    return {"task": task["task"], "month": task["month"], "symbols": len(task["symbols"]),
            "symbols_sha256": symbols_digest(task["symbols"]), "params": params, "pages": pages, "bars": bars,
            "quarantine": quarantine, "unexpected_symbols": sorted(unexpected), "fetched_at": utc_now(),
            "seconds": round(time.monotonic() - started, 3)}


def done_tasks(manifest: Path) -> dict:
    """{task: (symbols_sha256, stored page bytes)}; a torn line is skipped, so that task is fetched again."""
    done = {}
    if manifest.exists():
        with open(manifest, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    done[row["task"]] = (row["symbols_sha256"], sum(page["bytes"] for page in row["pages"]))
                except (ValueError, KeyError, TypeError):
                    continue
    return done


def task_rows(manifest: Path, wanted: set) -> dict:
    rows = {}
    if manifest.exists():
        with open(manifest, encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if row["task"] in wanted:
                        rows[row["task"]] = row
                except (ValueError, KeyError, TypeError):
                    continue
    return rows


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


def pilot_report(ds_dir: Path, dataset: str, fingerprint: str, tasks: list, selected: list, rows: dict, *,
                 free_bytes: int, rss_bytes: int, seconds: float, requests: int, fetched_now: int,
                 rate: float | None) -> dict:
    """Measured pilot figures and the full-span disk projection. The projection takes the larger of two scalings of
    the pilot's disk use (page files plus manifest rows): per planned task, and per bar with bars scaled by the
    universe's symbol-sessions (the pilot's bars per symbol-session times the span's symbol-sessions)."""
    limit = DATASETS[dataset]["params"]["limit"]
    fetched = [rows[t["task"]] for t in selected if t["task"] in rows]
    pages = [page for row in fetched for page in row["pages"]]
    bars = sum(row["bars"] for row in fetched)
    raw = sum(page["bytes"] for page in pages)
    decoded = sum(page["json_bytes"] for page in pages)
    disk = (sum(disk_bytes(ds_dir / page["file"]) for page in pages)
            + sum(len(json.dumps(row, sort_keys=True)) + 1 for row in fetched))
    full = [page["bars"] / limit for page in pages if page["next_page_token"]]
    ideal = sum(max(1, math.ceil(row["bars"] / limit)) for row in fetched)

    def ratio(a, b):
        return round(a / b, 3) if b else None

    report = {"schema": PILOT_SCHEMA, "dataset": dataset, "fingerprint": fingerprint, "created_at": utc_now(),
              "pilot_tasks": [t["task"] for t in selected], "free_disk_share": FREE_DISK_SHARE, "projection": None,
              "metrics": {"tasks": len(fetched), "fetched_in_this_run": fetched_now, "pages": len(pages),
                          "bars": bars, "raw_bytes": raw, "json_bytes": decoded, "disk_bytes": disk,
                          "raw_bytes_per_page": ratio(raw, len(pages)), "json_bytes_per_page": ratio(decoded, len(pages)),
                          "raw_bytes_per_bar": ratio(raw, bars), "disk_bytes_per_bar": ratio(disk, bars),
                          "bars_per_page": ratio(bars, len(pages)),
                          "quarantined_bars": sum(len(row["quarantine"]) for row in fetched),
                          "full_page_share_nonterminal": round(sum(full) / len(full), 4) if full else None,
                          "calls_over_ideal": ratio(len(pages), ideal),
                          "peak_rss_bytes": rss_bytes, "peak_rss_mib": round(rss_bytes / 2 ** 20, 1),
                          "requests": requests, "seconds": round(seconds, 3),
                          "calls_per_minute": ratio(requests * 60, seconds)},
              # D2 overturn conditions, reported for the operator: under 95% full pages or more than 1.3x the ideal
              # call count means per-day tasks should replace month tasks.
              "flags": {"pages_under_95pct_full": (sum(full) / len(full) < 0.95) if full else None,
                        "calls_over_1_3x_ideal": (len(pages) > 1.3 * ideal) if ideal else None}}
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
    threshold = int(FREE_DISK_SHARE * free_bytes)
    calls = math.ceil(projected_bars / limit) + len(tasks)
    report["projection"] = {"planned_tasks": len(tasks), "symbol_sessions_total": total_sessions,
                            "symbol_sessions_pilot": pilot_sessions,
                            "bars_per_symbol_session": round(bars / pilot_sessions, 3),
                            "projected_bars": round(projected_bars),
                            "projected_disk_bytes_by_sessions": math.ceil(by_sessions),
                            "projected_disk_bytes_by_tasks": math.ceil(by_tasks),
                            "projected_disk_bytes": projected, "projected_disk_gib": round(projected / 2 ** 30, 2),
                            "free_disk_bytes": free_bytes, "threshold_bytes": threshold,
                            "projected_calls_upper": calls,
                            "projected_minutes_at_rate": round(calls / rate, 1) if rate else None}
    within = projected <= threshold
    return {**report, "verdict": "pass" if within else "refused",
            "reason": f"projected {projected} bytes {'are within' if within else 'exceed'} "
                      f"{FREE_DISK_SHARE:.0%} of free disk ({threshold} of {free_bytes} bytes)"}


def require_pilot(ds_dir: Path, fingerprint: str, stored_bytes: int, free_bytes: int) -> None:
    """A full run needs a passing pilot of the same scope, and its remaining projection must still fit free disk."""
    path = ds_dir / "pilot.json"
    if not path.exists():
        raise Refused(f"{ds_dir.name} has no pilot: run the same command with --pilot 2 first")
    try:
        report = json.loads(path.read_text())
        same_scope, verdict, reason = report.get("fingerprint") == fingerprint, report.get("verdict"), report.get("reason")
        projected = int(report["projection"]["projected_disk_bytes"]) if verdict == "pass" else None
    except (ValueError, AttributeError, KeyError, TypeError):
        raise Refused(f"{path} is unreadable: run --pilot again") from None
    if not same_scope:
        raise Refused(f"{path} was measured under a different scope: run --pilot again")
    if verdict != "pass":
        raise Refused(f"the pilot's verdict is {verdict!r}: {reason}")
    remaining = projected - stored_bytes
    if remaining > FREE_DISK_SHARE * free_bytes:
        raise Refused(f"the remaining projected {remaining} bytes exceed {FREE_DISK_SHARE:.0%} of the {free_bytes} "
                      "bytes free now")


# --------------------------------------------------------------------------- runs


def day_task(client: Client, dataset: str, day: date, root: Path) -> dict:
    spec = DATASETS[dataset]
    params = {**spec["params"], "start": f"{day.isoformat()}T00:00:00Z",
              "end": f"{(day + timedelta(days=1)).isoformat()}T00:00:00Z"}
    records, pages, token = [], 0, None
    while True:
        body = client.get(spec["path"], {**params, **({"page_token": token} if token else {})})
        records.extend(body.get(spec["key"]) or [])
        pages += 1
        token = body.get("next_page_token")
        if not token:
            break
    payload = gzip.compress("".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in records).encode(), mtime=0)
    target = root / dataset / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}.jsonl.gz"
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = target.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(payload)
    os.replace(tmp, target)
    return {"day": day.isoformat(), "records": len(records), "pages": pages, "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload), "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def done_days(manifest: Path) -> set:
    if not manifest.exists():
        return set()
    days = set()
    for line in manifest.read_text().splitlines():
        try:
            days.add(json.loads(line)["day"])
        except (ValueError, KeyError):
            continue  # a torn last line: that day is fetched again
    return days


def run(client: Client, dataset: str, start: date, end: date, root: Path, workers: int, stop_file: Path | None = None,
        *, universe: dict | None = None, pilot: int = 0, code: str | None = None, disk_free=None, peak_rss=None,
        rate: float | None = None) -> dict:
    spec = DATASETS[dataset]
    if end < start:
        raise Refused(f"--end {end} precedes --start {start}")
    ds_dir = root / dataset
    refuse_headerless(ds_dir)  # before the lock file: a refused legacy directory is left untouched
    ds_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with dataset_lock(ds_dir):
        if spec["capture"] == "records":
            if universe is not None or pilot:
                raise Refused(f"{dataset} is not symbol-scoped: it takes no --universe or --pilot")
            check_scope(ds_dir, dataset_scope(dataset, start, end, code=code), {"created_at": utc_now()})
            return run_days(client, dataset, start, end, root, workers, stop_file)
        if universe is None:
            raise Refused(f"{dataset} needs --universe (built by `backfill.py universe`)")
        tasks = plan_month_tasks(universe, start, end, spec["batch_size"])
        scope = dataset_scope(dataset, start, end, tasks=tasks, asof=universe["naming_asof"], code=code)
        provenance = {"created_at": utc_now(), "universe": {key: universe.get(key) for key in
                      ("file_sha256", "naming_asof", "covers_through", "rule", "source", "summary")}}
        header = check_scope(ds_dir, scope, provenance)
        return run_pages(client, dataset, tasks, root, workers, stop_file, header["fingerprint"],
                         universe["naming_asof"], pilot, disk_free or (lambda path: shutil.disk_usage(path).free),
                         peak_rss or peak_rss_bytes, rate)


def run_days(client: Client, dataset: str, start: date, end: date, root: Path, workers: int,
             stop_file: Path | None = None) -> dict:
    manifest = root / dataset / "manifest.jsonl"
    repair_manifest_tail(manifest)
    skip = done_days(manifest)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    todo = [d for d in days if d.isoformat() not in skip]
    lock, totals = threading.Lock(), {"days": 0, "records": 0, "failed": [], "stopped": 0}
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", buffering=1) as log, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(unless_stopped, stop_file, day_task, client, dataset, d, root): d for d in todo}
        for future in as_completed(futures):
            d = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # recorded and retried on the next run
                totals["failed"].append({"day": d.isoformat(), "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
                continue
            if row is None:
                totals["stopped"] += 1
                continue
            with lock:
                log.write(json.dumps(row, sort_keys=True) + "\n")
                totals["days"] += 1
                totals["records"] += row["records"]
    return {**totals, "skipped_already_done": len(days) - len(todo), "requests": client.requests, "throttled": client.throttled}


def run_pages(client: Client, dataset: str, tasks: list, root: Path, workers: int, stop_file: Path | None,
              fingerprint: str, asof: str, pilot: int, disk_free, peak_rss, rate: float | None) -> dict:
    ds_dir = root / dataset
    manifest = ds_dir / "manifest.jsonl"
    repair_manifest_tail(manifest)
    done = done_tasks(manifest)
    selected = pilot_tasks(tasks, pilot) if pilot else tasks
    if not pilot:
        require_pilot(ds_dir, fingerprint, sum(size for _, size in done.values()), disk_free(ds_dir))
    todo = [t for t in selected if done.get(t["task"], (None,))[0] != symbols_digest(t["symbols"])]
    totals = {"tasks": 0, "pages": 0, "bars": 0, "quarantined": 0, "failed": [], "stopped": 0}
    started, requests_before = time.monotonic(), client.requests
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", buffering=1) as log, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(unless_stopped, stop_file, page_task, client, dataset, t, root, asof): t for t in todo}
        for future in as_completed(futures):  # only this thread writes the manifest
            task = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # recorded and retried on the next run
                totals["failed"].append({"task": task["task"], "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
                continue
            if row is None:
                totals["stopped"] += 1
                continue
            log.write(json.dumps(row, sort_keys=True) + "\n")
            totals["tasks"] += 1
            totals["pages"] += len(row["pages"])
            totals["bars"] += row["bars"]
            totals["quarantined"] += len(row["quarantine"])
    result = {**totals, "planned_tasks": len(tasks), "selected_tasks": len(selected),
              "skipped_already_done": len(selected) - len(todo), "requests": client.requests,
              "throttled": client.throttled, "ratelimit_remaining_min": client.ratelimit_remaining_min}
    if pilot:
        report = pilot_report(ds_dir, dataset, fingerprint, tasks, selected,
                              task_rows(manifest, {t["task"] for t in selected}), free_bytes=disk_free(ds_dir),
                              rss_bytes=peak_rss(), seconds=time.monotonic() - started,
                              requests=client.requests - requests_before, fetched_now=totals["tasks"], rate=rate)
        write_private(ds_dir / "pilot.json", (json.dumps(report, indent=1, sort_keys=True) + "\n").encode())
        result["pilot"] = report
    return result


# --------------------------------------------------------------------------- verification


def verify_dataset(root: Path, dataset: str, examples: int = 20) -> dict:
    """Re-hash every recorded file against the manifest; for page capture also check each page chain and bar total."""
    spec, ds_dir = DATASETS[dataset], root / dataset
    result = {"dataset": dataset, "scope_header": (ds_dir / "scope.json").exists(), "rows": 0, "torn_lines": 0,
              "files": 0, "problems": 0, "examples": []}

    def problem(detail: dict) -> None:
        result["problems"] += 1
        if len(result["examples"]) < examples:
            result["examples"].append(detail)

    with open(ds_dir / "manifest.jsonl", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                result["torn_lines"] += 1
                continue
            result["rows"] += 1
            if spec["capture"] == "records":
                day = row["day"]
                checks = [(f"{day[:4]}/{day[5:7]}/{day[8:10]}.jsonl.gz", row["sha256"], None)]
            else:
                pages = row["pages"]
                chained = (bool(pages) and pages[0]["page_token"] is None and not pages[-1]["next_page_token"]
                           and all(page["next_page_token"] for page in pages[:-1])
                           and all(page["page_token"] for page in pages[1:]))
                if not chained:
                    problem({"task": row["task"], "problem": "page chain does not run from no token to a null next token"})
                if sum(page["bars"] for page in pages) != row["bars"]:
                    problem({"task": row["task"], "problem": "page bars do not sum to the task total"})
                checks = [(page["file"], page["sha256"], page["json_sha256"]) for page in pages]
            for name, digest, json_digest in checks:
                path = ds_dir / name
                if not path.is_file():
                    problem({"file": name, "problem": "missing"})
                    continue
                stored = path.read_bytes()
                result["files"] += 1
                if sha256_hex(stored) != digest:
                    problem({"file": name, "problem": "sha256 differs from the manifest"})
                elif json_digest and sha256_hex(gzip.decompress(stored)) != json_digest:
                    problem({"file": name, "problem": "decoded page sha256 differs from the manifest"})
    result["ok"] = result["rows"] > 0 and result["problems"] == 0
    return result


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
                    help="fetch N evenly spread tasks of the span, report bytes, bytes per bar and peak RSS, project "
                         "the span's disk use and record the verdict a full run requires")
    a = ap.parse_args(argv)
    if not 1 <= a.rate <= MAX_RATE:
        raise SystemExit("--rate must leave headroom for the live monitor, scans and the engine (at most 6000/min)")
    if a.workers < 1 or a.pilot < 0:
        raise SystemExit("--workers must be at least 1 and --pilot at least 0")
    if DATASETS[a.dataset]["capture"] == "pages" and a.universe is None:
        raise SystemExit(f"{a.dataset} needs --universe (built by `backfill.py universe`)")
    try:
        universe = load_universe(a.universe) if a.universe else None
    except ValueError as exc:
        raise SystemExit(str(exc))
    key, secret = load_credentials(a.env_file)
    client = Client({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, Bucket(a.rate),
                    **({"opener": opener} if opener else {}))
    started = time.time()
    try:
        result = run(client, a.dataset, a.start, a.end, a.out, a.workers, a.out / "STOP", universe=universe,
                     pilot=a.pilot, rate=a.rate)
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    result["seconds"] = round(time.time() - started, 1)
    print(json.dumps(result))
    if result["failed"]:
        return 1
    if a.pilot:
        return {"pass": 0, "incomplete": 1}.get(result["pilot"]["verdict"], 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
