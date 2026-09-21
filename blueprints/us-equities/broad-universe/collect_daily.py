#!/usr/bin/env python3
"""Bulk daily-bar collector for the broad-universe research dataset.

Read-only: exactly one HTTPS GET path (`/v2/stocks/bars`) on the Alpaca market-data
host. Every response page is retained (gzip) with its hash and a ledger line, so
pagination completion is evidence rather than an assumption. Bars are requested by
*today's* symbol (provider default `asof`): renamed issuers are returned under
their current ticker, and a ticker reused after a delisting resolves to the
current holder. Those identity limits are measured downstream, not hidden here.

Credentials are parsed literally from an explicit private env file; no shell is
executed and nothing secret is written to the ledger or stdout.
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

HOST = "https://data.alpaca.markets"
PATH = "/v2/stocks/bars"
PAGE_LIMIT = 10000
MAX_RETRIES = 5
COLUMNS = ("symbol", "t", "o", "h", "l", "c", "v", "n", "vw")
ADJUSTMENTS = ("raw", "all")
DATA_SYMBOL = re.compile(r"^[A-Z]+(\.[A-Z]+)?$")
_CRED = re.compile(r"^\s*(?:export\s+)?(APCA_API_KEY_ID|APCA_API_SECRET_KEY)=(['\"]?)([A-Za-z0-9]+)\2\s*$")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_credentials(path):
    if os.path.islink(path):
        raise SystemExit("refusing symlink credential file")
    found = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = _CRED.match(line)
            if match:
                found[match.group(1)] = match.group(3)
    if set(found) != {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"}:
        raise SystemExit("credential file lacks the two literal APCA variables")
    return found["APCA_API_KEY_ID"], found["APCA_API_SECRET_KEY"]


def select_symbols(asset_files, exclude_exchanges=("OTC",)):
    """Deterministic symbol list plus the identity facts the asset master supports."""
    by_symbol = {}
    skipped = {}
    for path in asset_files:
        with open(path, encoding="utf-8") as handle:
            for asset in json.load(handle):
                if asset.get("class") != "us_equity":
                    continue
                if asset.get("exchange") in exclude_exchanges:
                    skipped[asset["exchange"]] = skipped.get(asset["exchange"], 0) + 1
                    continue
                if not DATA_SYMBOL.match(asset["symbol"]):
                    # CUSIP-style escrow/rights/CVR placeholders: the bars API answers 400 "invalid symbol".
                    skipped["placeholder_symbol"] = skipped.get("placeholder_symbol", 0) + 1
                    continue
                by_symbol.setdefault(asset["symbol"], []).append(
                    {"id": asset.get("id"), "status": asset.get("status"), "exchange": asset.get("exchange")})
    collisions = {s: v for s, v in by_symbol.items() if len(v) > 1}
    return sorted(by_symbol), by_symbol, collisions, skipped


def batches(symbols, size):
    return [symbols[i:i + size] for i in range(0, len(symbols), size)]


def symbols_digest(symbols):
    return hashlib.sha256(",".join(symbols).encode()).hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()

    def completed(self):
        done = {}
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as handle:
                for line in handle:
                    rec = json.loads(line)
                    if rec.get("event") == "batch_complete":
                        done[(rec["adjustment"], rec["batch"])] = rec["symbols_sha256"]
        return done

    def write(self, **rec):
        rec["recorded_at"] = utc_now()
        with self.lock, open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, sort_keys=True) + "\n")


class BadRequest(Exception):
    pass


def fetch_page(session, headers, params):
    """One GET with bounded retry. Returns (status, body_bytes, attempts)."""
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(HOST + PATH, headers=headers, params=params, timeout=(5, 60),
                                   allow_redirects=False)
        except Exception as exc:  # network failure: retry, never fabricate a page
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"network failure after {attempt} attempts: {type(exc).__name__}")
            time.sleep(delay)
            delay *= 2
            continue
        if response.status_code == 200:
            return 200, response.content, attempt
        if response.status_code in (400, 422):
            raise BadRequest(response.text[:200])
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"HTTP {response.status_code} after {attempt} attempts")
            reset = response.headers.get("X-RateLimit-Reset")
            wait = max(1.0, float(reset) - time.time()) if reset and reset.isdigit() else delay
            time.sleep(min(wait, 60))
            delay *= 2
            continue
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
    raise RuntimeError("unreachable")


def collect_symbols(session, headers, symbols, args, adjustment, label, out, ledger, rows):
    """Page one symbol group to its terminal page. Bisects on a provider 400."""
    params = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": args.start, "end": args.end,
              "limit": PAGE_LIMIT, "adjustment": adjustment, "feed": args.feed, "sort": "asc"}
    page = 0
    token = None
    while True:
        if token:
            params["page_token"] = token
        started = time.time()
        try:
            status, raw, attempts = fetch_page(session, headers, params)
        except BadRequest as exc:
            if page:
                raise RuntimeError(f"400 after first page: {exc}")
            if len(symbols) == 1:
                ledger.write(event="rejected_symbol", adjustment=adjustment, batch=label, symbol=symbols[0],
                             message=str(exc))
                return
            half = len(symbols) // 2
            collect_symbols(session, headers, symbols[:half], args, adjustment, label + "a", out, ledger, rows)
            collect_symbols(session, headers, symbols[half:], args, adjustment, label + "b", out, ledger, rows)
            return
        body = json.loads(raw)
        bars = body.get("bars") or {}
        count = 0
        for symbol, items in bars.items():
            for bar in items:
                rows.append((symbol, bar["t"], bar["o"], bar["h"], bar["l"], bar["c"], bar["v"],
                             bar.get("n"), bar.get("vw")))
                count += 1
        token = body.get("next_page_token")
        name = f"{label}-p{page:04d}.json.gz"
        with gzip.open(os.path.join(out, "pages", adjustment, name), "wb", compresslevel=6) as handle:
            handle.write(raw)
        ledger.write(event="page", adjustment=adjustment, batch=label, page=page, status=status,
                     sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), bars=count,
                     symbols_with_bars=len(bars), next_page_token_present=bool(token), attempts=attempts,
                     elapsed_s=round(time.time() - started, 3), file=name)
        page += 1
        if not token:
            return


def run_batch(index, symbols, adjustment, args, headers, out, ledger):
    import requests
    session = requests.Session()
    session.trust_env = False
    label = f"b{index:05d}"
    rows = []
    try:
        collect_symbols(session, headers, symbols, args, adjustment, label, out, ledger, rows)
    except Exception as exc:
        ledger.write(event="batch_failed", adjustment=adjustment, batch=index, error=str(exc)[:300])
        return index, adjustment, False, 0
    finally:
        session.close()
    target = os.path.join(out, "bars", adjustment, f"{label}.csv.gz")
    temporary = target + ".tmp"
    with gzip.open(temporary, "wt", encoding="utf-8", newline="", compresslevel=4) as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    os.replace(temporary, target)
    ledger.write(event="batch_complete", adjustment=adjustment, batch=index, symbols=len(symbols),
                 symbols_sha256=symbols_digest(symbols), bars=len(rows),
                 symbols_with_bars=len({r[0] for r in rows}))
    return index, adjustment, True, len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--assets", nargs="+", required=True, help="asset-master JSON files (active, inactive)")
    parser.add_argument("--out", required=True, help="private output directory outside the repository")
    parser.add_argument("--start", default="2016-01-01T00:00:00Z")
    parser.add_argument("--end", required=True, help="inclusive upper bound; use the last settled session")
    parser.add_argument("--feed", default="sip")
    parser.add_argument("--adjustments", default="raw,all")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-batches", type=int, default=0, help="bounded trial; 0 means every batch")
    args = parser.parse_args()

    adjustments = [a for a in args.adjustments.split(",") if a]
    if any(a not in ADJUSTMENTS for a in adjustments):
        raise SystemExit(f"adjustments must be within {ADJUSTMENTS}")
    key, secret = read_credentials(args.env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    symbols, identities, collisions, skipped = select_symbols(args.assets)
    groups = batches(symbols, args.batch_size)
    if args.max_batches:
        groups = groups[:args.max_batches]
    os.makedirs(args.out, mode=0o700, exist_ok=True)
    for adjustment in adjustments:
        os.makedirs(os.path.join(args.out, "pages", adjustment), exist_ok=True)
        os.makedirs(os.path.join(args.out, "bars", adjustment), exist_ok=True)
    ledger = Ledger(os.path.join(args.out, "ledger.jsonl"))
    done = ledger.completed()
    plan = {"schema": "broad-universe-collection-plan/1", "created_at": utc_now(), "host": HOST, "path": PATH,
            "timeframe": "1Day", "start": args.start, "end": args.end, "feed": args.feed,
            "adjustments": adjustments, "page_limit": PAGE_LIMIT, "batch_size": args.batch_size,
            "symbols": len(symbols), "batches": len(groups), "symbols_sha256": symbols_digest(symbols),
            "excluded_exchange_assets": skipped, "symbol_collisions": len(collisions),
            "asof": "provider default (request date)", "asset_files": [os.path.basename(p) for p in args.assets]}
    with open(os.path.join(args.out, "plan.json"), "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=1)
    with open(os.path.join(args.out, "symbol-identities.json"), "w", encoding="utf-8") as handle:
        json.dump({"identities": identities, "collisions": collisions}, handle)

    jobs = [(i, g, a) for a in adjustments for i, g in enumerate(groups)
            if done.get((a, i)) != symbols_digest(g)]
    print(f"symbols={len(symbols)} batches={len(groups)} jobs={len(jobs)} resumed={len(done)}", flush=True)
    failed = 0
    total = 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_batch, i, g, a, args, headers, args.out, ledger) for i, g, a in jobs]
        for n, future in enumerate(as_completed(futures), 1):
            _, _, ok, bars = future.result()
            failed += 0 if ok else 1
            total += bars
            if n % 20 == 0 or n == len(futures):
                print(f"jobs={n}/{len(futures)} bars={total} failed={failed} elapsed_s={int(time.time() - started)}",
                      flush=True)
    ledger.write(event="run_complete", jobs=len(jobs), failed=failed, bars=total)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
