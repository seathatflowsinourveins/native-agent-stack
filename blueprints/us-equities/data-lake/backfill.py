"""Governed, resumable Alpaca historical backfill into immutable raw day files (the data lake's source layer).

  python backfill.py news --env-file ENV --out DIR --start 2015-01-01 --end 2026-09-23 [--rate 3000] [--workers 8]

One task per calendar day. Each task pages through the endpoint for [day, day + 1) and writes every returned
record to DIR/<dataset>/<YYYY>/<MM>/<DD>.jsonl.gz, then appends one line to DIR/<dataset>/manifest.jsonl with the
record count, page count, file sha256 and fetch time; a day already in the manifest is skipped, so a run resumes
where it stopped. A shared token bucket keeps the whole run under --rate requests per minute (the data API limit
measured on 2026-09-24 is 10,000/min for the account, shared with every other data client), and an HTTP 429
waits for the limit's reset before retrying. GET only. Normalized Parquet is a separate, later layer.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = "https://data.alpaca.markets"
DATASETS = {
    # dataset: (path, fixed params, records key)
    "news": ("/v1beta1/news", {"limit": 50, "sort": "asc", "include_content": "true", "exclude_contentless": "false"}, "news"),
}


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
        self.lock = threading.Lock()

    def get(self, path: str, params: dict) -> dict:
        url = f"{DATA}{path}?{urllib.parse.urlencode(params)}"
        for attempt in range(8):
            self.bucket.acquire()
            with self.lock:
                self.requests += 1
            try:
                with self.opener(urllib.request.Request(url, headers=self.headers), timeout=60) as r:
                    return json.loads(r.read())
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
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                self.sleep(min(30.0, 2.0 ** attempt))
        raise RuntimeError(f"gave up after retries: {path}")


def day_task(client: Client, dataset: str, day: date, root: Path) -> dict:
    path, fixed, key = DATASETS[dataset]
    params = {**fixed, "start": f"{day.isoformat()}T00:00:00Z", "end": f"{(day + timedelta(days=1)).isoformat()}T00:00:00Z"}
    records, pages, token = [], 0, None
    while True:
        body = client.get(path, {**params, **({"page_token": token} if token else {})})
        records.extend(body.get(key) or [])
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


def run(client: Client, dataset: str, start: date, end: date, root: Path, workers: int, stop_file: Path | None = None) -> dict:
    manifest = root / dataset / "manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    skip = done_days(manifest)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    todo = [d for d in days if d.isoformat() not in skip]
    lock, totals = threading.Lock(), {"days": 0, "records": 0, "failed": []}
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", buffering=1) as log, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for d in todo:
            if stop_file and stop_file.exists():
                break
            futures[pool.submit(day_task, client, dataset, d, root)] = d
        for future in as_completed(futures):
            d = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # recorded and retried on the next run
                totals["failed"].append({"day": d.isoformat(), "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
                continue
            with lock:
                log.write(json.dumps(row, sort_keys=True) + "\n")
                totals["days"] += 1
                totals["records"] += row["records"]
    return {**totals, "skipped_already_done": len(days) - len(todo), "requests": client.requests, "throttled": client.throttled}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dataset", choices=sorted(DATASETS))
    ap.add_argument("--env-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start", type=date.fromisoformat, required=True)
    ap.add_argument("--end", type=date.fromisoformat, required=True)
    ap.add_argument("--rate", type=float, default=3000.0, help="requests per minute for this run (the account limit is shared)")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    if not 1 <= a.rate <= 6000:
        raise SystemExit("--rate must leave headroom for the live monitor, scans and the engine (at most 6000/min)")
    sys.path.insert(0, str(HERE.parent / "mover-early-entry"))
    import collect  # owner-only 0600 credential file, key pair only
    key, secret = collect.credentials(a.env_file)
    client = Client({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, Bucket(a.rate))
    started = time.time()
    result = run(client, a.dataset, a.start, a.end, a.out, a.workers, a.out / "STOP")
    result["seconds"] = round(time.time() - started, 1)
    print(json.dumps(result))
    return 0 if not result["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
