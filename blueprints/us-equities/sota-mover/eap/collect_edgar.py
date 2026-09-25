#!/usr/bin/env python3
"""Collect SEC submissions metadata (8-K Item 2.02 and 10-Q/10-K rows) for the EAP study.

  python collect_edgar.py universe --root ROOT --daily DAILY.parquet
  python collect_edgar.py fetch    --root ROOT [--rate 7.5] [--workers 4] [--limit N]
  python collect_edgar.py tzcheck  --root ROOT [--sample 24]
  python collect_edgar.py extract  --root ROOT

``universe`` downloads the current ``company_tickers.json`` and keeps the CIKs whose ticker
(SEC ``-`` normalised to ``.``) is a symbol of the daily dataset; it reads symbols only.
``fetch`` downloads ``data.sec.gov/submissions/CIK##########.json`` and every continuation
file (``filings.files``) whose ``filingTo`` is on or after 2015-01-01. Raw response bodies
are stored gzipped under ROOT/raw/ with one manifest line per stored file (sha256 of the
decompressed body); a CIK is complete when its ``cik_done`` line exists, so a rerun resumes.
``tzcheck`` compares ``acceptanceDateTime`` with the filing's own SGML header for a
deterministic sample of 8-K rows, to establish the clock of the JSON field.
``extract`` writes ROOT/derived/filings.jsonl.gz: 8-K, 8-K/A, 10-Q, 10-K and their
amendments with filingDate >= 2015-01-01.

The SEC contact is loaded inside this process from ~/.config/codex-ecosystem/sec.env
(SEC_USER_AGENT or EDGAR_IDENTITY) and never printed or written. Request rate is capped at
8/s by a process-wide limiter. No return, price change or outcome is read or computed here.
"""
from __future__ import annotations

import os
import sys

# signal.py in this directory would shadow the standard-library module.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse
import gzip
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

MAX_RATE = 8.0
COLLECT_FROM = "2015-01-01"
KEEP_FORMS = {"8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A", "10-KT", "10-KT/A"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/{name}"
SEC_ENV = Path("~/.config/codex-ecosystem/sec.env").expanduser()
DEFAULT_ROOT = Path("~/.local/state/native-agent-stack/research/sota-mover/eap").expanduser()
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_env_file(path: Path) -> dict:
    """Parse ``KEY=VALUE`` / ``export KEY=VALUE`` lines. No printing."""
    env = {}
    for line in path.read_text().splitlines():
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not m or line.lstrip().startswith("#"):
            continue
        val = m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        env[m.group(1)] = val
    return env


def sec_user_agent() -> str:
    env = load_env_file(SEC_ENV)
    ua = env.get("SEC_USER_AGENT") or env.get("EDGAR_IDENTITY")
    if not ua:
        raise SystemExit("sec.env has neither SEC_USER_AGENT nor EDGAR_IDENTITY")
    return ua


def normalize_ticker(t: str) -> str:
    return t.strip().upper().replace("-", ".")


def cik10(cik) -> str:
    return f"{int(cik):010d}"


class RateLimiter:
    """Process-wide minimum spacing between request starts (rate <= MAX_RATE)."""

    def __init__(self, rate: float, clock=time.monotonic, sleep=time.sleep):
        if not 0 < rate <= MAX_RATE:
            raise ValueError(f"rate must be in (0, {MAX_RATE}]")
        self.interval = 1.0 / rate
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            t = self.clock()
            if t < self.next_at:
                self.sleep(self.next_at - t)
                t = self.next_at
            self.next_at = t + self.interval


class Http:
    """GET with the SEC contact header, bounded retries and a status tally."""

    def __init__(self, user_agent: str, limiter: RateLimiter, opener=None, sleep=time.sleep):
        self.ua = user_agent
        self.limiter = limiter
        self.open = opener or (lambda req: urllib.request.urlopen(req, timeout=30))
        self.sleep = sleep
        self.tally = Counter()
        self.lock = threading.Lock()

    def _count(self, key) -> None:
        with self.lock:
            self.tally[str(key)] += 1

    def get(self, url: str) -> tuple[int, bytes]:
        for attempt in range(MAX_ATTEMPTS):
            self.limiter.wait()
            req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Encoding": "gzip"})
            try:
                with self.open(req) as resp:
                    body = resp.read()
                    if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
                        body = gzip.decompress(body)
                    status = getattr(resp, "status", 200)
                self._count(status)
                return status, body
            except urllib.error.HTTPError as e:
                self._count(e.code)
                if e.code not in RETRY_STATUSES:
                    return e.code, b""
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                self._count(type(e).__name__)
            self.sleep(min(60, 2 ** (attempt + 1)))
        return -1, b""


class Store:
    """Gzipped raw bodies plus an append-only JSONL manifest."""

    def __init__(self, root: Path):
        self.root = root
        self.raw = root / "raw" / "submissions"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.manifest = root / "raw" / "manifest.jsonl"
        self.lock = threading.Lock()

    def lines(self) -> list[dict]:
        if not self.manifest.exists():
            return []
        out = []
        for line in self.manifest.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # a torn final line from an interrupted run
        return out

    def done_ciks(self) -> set[str]:
        return {r["cik"] for r in self.lines() if r.get("kind") == "cik_done"}

    def append(self, rec: dict) -> None:
        with self.lock, self.manifest.open("a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    def put(self, name: str, body: bytes) -> dict:
        path = self.raw / (name + ".gz")
        tmp = path.with_suffix(".gz.partial")
        tmp.write_bytes(gzip.compress(body, mtime=0))
        tmp.replace(path)
        return {"file": f"raw/submissions/{name}.gz", "sha256": sha256_bytes(body), "bytes": len(body)}


def needed_continuations(sub: dict, collect_from: str = COLLECT_FROM) -> list[str]:
    files = (sub.get("filings") or {}).get("files") or []
    return [f["name"] for f in files if (f.get("filingTo") or "9999") >= collect_from]


def fetch_cik(cik: str, http: Http, store: Store) -> str:
    name = f"CIK{cik}.json"
    status, body = http.get(SUBMISSIONS_URL.format(name=name))
    if status != 200:
        store.append({"kind": "error", "cik": cik, "name": name, "status": status, "at": now_utc()})
        if status == 404:
            store.append({"kind": "cik_done", "cik": cik, "status": "not_found", "at": now_utc()})
            return "not_found"
        return "error"
    store.append({"kind": "submissions", "cik": cik, "name": name, "status": 200, "at": now_utc(), **store.put(name, body)})
    for cont in needed_continuations(json.loads(body)):
        st, b = http.get(SUBMISSIONS_URL.format(name=cont))
        if st != 200:
            store.append({"kind": "error", "cik": cik, "name": cont, "status": st, "at": now_utc()})
            return "error"
        store.append({"kind": "continuation", "cik": cik, "name": cont, "status": 200, "at": now_utc(), **store.put(cont, b)})
    store.append({"kind": "cik_done", "cik": cik, "status": "ok", "at": now_utc()})
    return "ok"


def match_universe(tickers: dict, symbols: set[str]) -> tuple[dict[str, list[str]], dict]:
    """CIK -> matched daily symbols from the current SEC map, plus drop-out counts.

    Issuers absent from the current map (delisted, acquired or renamed before retrieval)
    cannot be matched; their daily symbols are counted, not guessed (deviation D3).
    """
    by_cik: dict[str, list[str]] = {}
    for row in tickers.values():
        by_cik.setdefault(cik10(row["cik_str"]), []).append(normalize_ticker(row["ticker"]))
    matched = {c: sorted(set(t for t in ts if t in symbols)) for c, ts in by_cik.items()}
    matched = {c: ts for c, ts in matched.items() if ts}
    sec_symbols = {t for ts in by_cik.values() for t in ts}
    counts = {"sec_ticker_rows": len(tickers), "sec_unique_ciks": len(by_cik),
              "daily_symbols": len(symbols), "matched_ciks": len(matched),
              "matched_symbols": sum(len(v) for v in matched.values()),
              "daily_symbols_without_current_cik": len(symbols - sec_symbols),
              "sec_ciks_without_daily_symbol": len(by_cik) - len(matched)}
    return matched, counts


def cmd_universe(a) -> None:
    root = a.root
    (root / "raw").mkdir(parents=True, exist_ok=True)
    http = Http(sec_user_agent(), RateLimiter(a.rate))
    status, body = http.get(TICKERS_URL)
    if status != 200:
        raise SystemExit(f"company_tickers.json status {status}")
    (root / "raw" / "company_tickers.json").write_bytes(body)
    tickers = json.loads(body)
    import duckdb  # lazy: only the CLI needs it
    con = duckdb.connect()
    con.execute("SET memory_limit='2.5GB'")
    con.execute("SET threads=4")
    (root / "duckdb-tmp").mkdir(exist_ok=True)
    con.execute(f"SET temp_directory='{root / 'duckdb-tmp'}'")
    symbols = {r[0] for r in con.execute(f"SELECT DISTINCT symbol FROM read_parquet('{a.daily}')").fetchall()}
    matched, counts = match_universe(tickers, symbols)
    universe = {"schema_version": 1, "created_at": now_utc(),
                "company_tickers_sha256": sha256_bytes(body),
                "ciks": {c: matched[c] for c in sorted(matched)}}
    (root / "universe.json").write_text(json.dumps(universe, indent=1, sort_keys=True))
    receipt = {**counts, "company_tickers_sha256": universe["company_tickers_sha256"], "http": dict(http.tally)}
    (root / "receipts").mkdir(exist_ok=True)
    (root / "receipts" / "universe.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))
    print(json.dumps(receipt, sort_keys=True))


def cmd_fetch(a) -> None:
    store = Store(a.root)
    universe = json.loads((a.root / "universe.json").read_text())
    todo = [c for c in universe["ciks"] if c not in store.done_ciks()]
    if a.limit:
        todo = todo[: a.limit]
    http = Http(sec_user_agent(), RateLimiter(a.rate))
    started = time.monotonic()
    outcomes = Counter()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for i, res in enumerate(pool.map(lambda c: fetch_cik(c, http, store), todo), 1):
            outcomes[res] += 1
            if i % 500 == 0:
                print(f"{i}/{len(todo)} {dict(outcomes)} http={dict(http.tally)}", flush=True)
    elapsed = time.monotonic() - started
    requests = sum(http.tally.values())
    receipt = {"at": now_utc(), "ciks_attempted": len(todo), "outcomes": dict(outcomes),
               "http": dict(http.tally), "requests": requests, "elapsed_s": round(elapsed, 1),
               "mean_rate_per_s": round(requests / elapsed, 3) if elapsed else None, "rate_cap": a.rate}
    with (a.root / "receipts" / "fetch-runs.jsonl").open("a") as f:
        f.write(json.dumps(receipt, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


def iter_rows(block: dict):
    keys = list(block.keys())
    n = len(block.get("accessionNumber", []))
    for i in range(n):
        yield {k: block[k][i] for k in keys if isinstance(block[k], list) and len(block[k]) == n}


def rows_for_cik(root: Path, cik: str, names: list[str]):
    for name in names:
        doc = json.loads(gzip.decompress((root / "raw" / "submissions" / (name + ".gz")).read_bytes()))
        block = doc["filings"]["recent"] if "filings" in doc else doc
        for r in iter_rows(block):
            yield r


def cmd_extract(a) -> None:
    store = Store(a.root)
    lines = store.lines()
    done = {r["cik"] for r in lines if r.get("kind") == "cik_done" and r.get("status") == "ok"}
    files: dict[str, list[str]] = {}
    for r in lines:
        if r.get("kind") in ("submissions", "continuation") and r["cik"] in done:
            if r["name"] not in files.setdefault(r["cik"], []):
                files[r["cik"]].append(r["name"])
    out_dir = a.root / "derived"
    out_dir.mkdir(exist_ok=True)
    counts = Counter()
    seen = set()
    first, last = "9999", "0000"
    buf = []
    for cik in sorted(files):
        for r in rows_for_cik(a.root, cik, files[cik]):
            form = r.get("form")
            if form not in KEEP_FORMS or (r.get("filingDate") or "") < COLLECT_FROM:
                continue
            key = r["accessionNumber"]
            if key in seen:
                counts["duplicate_accession_rows"] += 1
                continue
            seen.add(key)
            rec = {"cik": cik, "accession": key, "form": form, "filing_date": r.get("filingDate"),
                   "report_date": r.get("reportDate") or None, "acceptance": r.get("acceptanceDateTime"),
                   "items": r.get("items") or ""}
            counts[form] += 1
            if form == "8-K" and "2.02" in [x.strip() for x in rec["items"].split(",")]:
                counts["8-K_item_2.02"] += 1
                first, last = min(first, rec["filing_date"]), max(last, rec["filing_date"])
            buf.append(json.dumps(rec, sort_keys=True))
    body = ("\n".join(buf) + "\n").encode()
    (out_dir / "filings.jsonl.gz").write_bytes(gzip.compress(body, mtime=0))
    manifest_bytes = store.manifest.read_bytes()
    item_ciks = set()
    for line in buf:
        rec = json.loads(line)
        if rec["form"] == "8-K" and "2.02" in [x.strip() for x in rec["items"].split(",")]:
            item_ciks.add(rec["cik"])
    receipt = {"at": now_utc(), "ciks_complete": len(done), "ciks_with_item_2_02": len(item_ciks),
               "rows": len(buf), "by_form": dict(sorted(counts.items())),
               "item_2_02_filing_date_range": [first, last],
               "filings_jsonl_sha256": sha256_bytes(body), "manifest_sha256": sha256_bytes(manifest_bytes),
               "manifest_lines": len(lines),
               "stored_files": sum(1 for r in lines if r.get("kind") in ("submissions", "continuation")),
               "not_found_ciks": sum(1 for r in lines if r.get("kind") == "cik_done" and r.get("status") == "not_found")}
    (a.root / "receipts" / "extract.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))
    print(json.dumps(receipt, sort_keys=True))


HEADER_RE = re.compile(rb"<ACCEPTANCE-DATETIME>\s*(\d{14})")


def parse_acceptance_et(value: str):
    from zoneinfo import ZoneInfo
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z$", value)
    if not m:
        raise ValueError(f"non-UTC acceptanceDateTime {value!r}")
    utc = datetime(*map(int, m.groups()), tzinfo=timezone.utc)
    return utc.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)


def cmd_tzcheck(a) -> None:
    """Compare the JSON acceptanceDateTime clock with the filing's SGML header (US/Eastern)."""
    rows = [json.loads(l) for l in gzip.decompress((a.root / "derived" / "filings.jsonl.gz").read_bytes()).splitlines()]
    rows = sorted((r for r in rows if r["form"] == "8-K" and r["acceptance"]),
                  key=lambda r: sha256_bytes(r["accession"].encode()))[: a.sample]
    http = Http(sec_user_agent(), RateLimiter(a.rate))
    results = []
    for r in rows:
        acc = r["accession"]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(r['cik'])}/{acc.replace('-', '')}/{acc}-index-headers.html"
        st, body = http.get(url)
        m = HEADER_RE.search(body) if st == 200 else None
        header = m.group(1).decode() if m else None
        json_digits = re.sub(r"\D", "", r["acceptance"])[:14]
        converted = parse_acceptance_et(r["acceptance"]).strftime("%Y%m%d%H%M%S")
        results.append({"filing_date": r["filing_date"], "json_utc": json_digits, "header_eastern": header,
                        "json_converted_to_eastern": converted,
                        "same_wallclock": header == json_digits if header else None,
                        "utc_to_eastern_matches": header == converted if header else None})
    same = sum(1 for x in results if x["same_wallclock"])
    conv = sum(1 for x in results if x["utc_to_eastern_matches"])
    receipt = {"at": now_utc(), "sample": len(results), "header_found": sum(1 for x in results if x["header_eastern"]),
               "json_equals_header_wallclock": same, "json_utc_converted_equals_header": conv, "http": dict(http.tally),
               "conclusion": ("acceptanceDateTime is UTC; converted to America/New_York it equals the SGML header"
                              if results and conv == len(results) else "inspect: conversion does not match every header"),
               "rows": results}
    (a.root / "receipts" / "tzcheck.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in receipt.items() if k != "rows"}, sort_keys=True))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("universe", "fetch", "tzcheck", "extract"):
        s = sub.add_parser(name)
        s.add_argument("--root", type=Path, default=DEFAULT_ROOT)
        s.add_argument("--rate", type=float, default=7.5)
    sub.choices["universe"].add_argument("--daily", type=Path, required=True)
    sub.choices["fetch"].add_argument("--workers", type=int, default=4)
    sub.choices["fetch"].add_argument("--limit", type=int, default=0)
    sub.choices["tzcheck"].add_argument("--sample", type=int, default=24)
    a = p.parse_args(argv)
    if a.rate > MAX_RATE:
        p.error(f"--rate above {MAX_RATE}/s is refused")
    a.root.mkdir(parents=True, exist_ok=True)
    (a.root / "receipts").mkdir(exist_ok=True)
    {"universe": cmd_universe, "fetch": cmd_fetch, "tzcheck": cmd_tzcheck, "extract": cmd_extract}[a.cmd](a)


if __name__ == "__main__":
    main()
