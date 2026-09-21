#!/usr/bin/env python3
"""Bulk corporate-actions collector for the broad-universe research dataset.

Read-only: exactly one HTTPS GET path (`/v1/corporate-actions`) on the
Alpaca market-data host, requested market-wide (no `symbols` filter), paged
explicitly to a terminal page with `page_token`, in calendar-year windows so a
single run stays resumable. Every page is retained (gzip) with its sha256 and
a ledger line, mirroring collect_daily.py's evidence pattern.

Contract verified against https://docs.alpaca.markets/reference/corporateactions-1
on 2026-09-21: `limit` (default 100, max 1000), `page_token` pagination, and a
response envelope `{"corporate_actions": {<type>: [...]}, "next_page_token": ...}`.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HOST = "https://data.alpaca.markets"
PATH = "/v1/corporate-actions"
PAGE_LIMIT = 1000
MAX_RETRIES = 5

# Every non-cash-dividend type named in the task, plus cash_dividend gated by --include-cash-dividends.
DEFAULT_TYPES = ("forward_split", "reverse_split", "unit_split", "stock_dividend", "spin_off", "cash_merger",
                  "stock_merger", "stock_and_cash_merger", "redemption", "name_change", "worthless_removal",
                  "rights_distribution")


def _load_collect_daily():
    path = Path(__file__).resolve().with_name("collect_daily.py")
    spec = importlib.util.spec_from_file_location("collect_daily", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def types_for(include_cash_dividends):
    types = list(DEFAULT_TYPES)
    if include_cash_dividends:
        types.append("cash_dividend")
    return tuple(sorted(types))


def year_windows(start, end):
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    for year in range(start_date.year, end_date.year + 1):
        window_start = max(start_date, start_date.replace(year=year, month=1, day=1))
        window_end = min(end_date, end_date.replace(year=year, month=12, day=31))
        yield year, window_start.isoformat(), window_end.isoformat()


class BadRequest(Exception):
    pass


def fetch_page(session, headers, params):
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(HOST + PATH, headers=headers, params=params, timeout=(5, 60),
                                    allow_redirects=False)
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"network failure after {attempt} attempts: {type(exc).__name__}") from exc
            time.sleep(delay)
            delay *= 2
            continue
        if response.status_code == 200:
            return response.content, attempt
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


def count_by_type(body):
    counts = {}
    for action_type, items in (body.get("corporate_actions") or {}).items():
        counts[action_type] = len(items)
    return counts


def completed_years(ledger_path, types_key):
    done = set()
    if os.path.exists(ledger_path):
        with open(ledger_path, encoding="utf-8") as handle:
            for line in handle:
                rec = json.loads(line)
                if rec.get("event") == "year_complete" and rec.get("types_key") == types_key:
                    done.add(rec["year"])
    return done


def collect_year(session, headers, year, window_start, window_end, types, out_dir, ledger, types_key):
    params = {"start": window_start, "end": window_end, "types": ",".join(types), "limit": PAGE_LIMIT}
    page = 0
    token = None
    year_dir = os.path.join(out_dir, "pages", str(year))
    os.makedirs(year_dir, exist_ok=True)
    total_items = 0
    total_by_type = Counter()
    while True:
        if token:
            params["page_token"] = token
        else:
            params.pop("page_token", None)
        started = time.time()
        raw, attempts = fetch_page(session, headers, params)
        body = json.loads(raw)
        counts = count_by_type(body)
        total_items += sum(counts.values())
        total_by_type.update(counts)
        token = body.get("next_page_token")
        name = f"p{page:04d}.json.gz"
        with gzip.open(os.path.join(year_dir, name), "wb", compresslevel=6) as handle:
            handle.write(raw)
        ledger.write(event="page", year=year, types_key=types_key, page=page,
                     sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), items=sum(counts.values()),
                     by_type=dict(counts), next_page_token_present=bool(token), attempts=attempts,
                     elapsed_s=round(time.time() - started, 3), file=name)
        page += 1
        if not token:
            break
    ledger.write(event="year_complete", year=year, types_key=types_key, pages=page, items=total_items,
                 by_type=dict(total_by_type))
    return total_items


def collect(env_file, out_dir, start, end, include_cash_dividends):
    import requests
    collect_daily = _load_collect_daily()
    key, secret = collect_daily.read_credentials(env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    types = types_for(include_cash_dividends)
    types_key = hashlib.sha256(",".join(types).encode()).hexdigest()[:16]

    os.makedirs(out_dir, mode=0o700, exist_ok=True)
    ledger = collect_daily.Ledger(os.path.join(out_dir, "ledger.jsonl"))
    done = completed_years(os.path.join(out_dir, "ledger.jsonl"), types_key)

    plan = {"schema": "broad-universe-corporate-actions-plan/1", "created_at": utc_now(), "host": HOST, "path": PATH,
            "types": list(types), "types_key": types_key, "start": start, "end": end, "page_limit": PAGE_LIMIT}
    with open(os.path.join(out_dir, "plan.json"), "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=1)

    session = requests.Session()
    session.trust_env = False
    failed = 0
    total = 0
    try:
        for year, window_start, window_end in year_windows(start, end):
            if year in done:
                continue
            try:
                total += collect_year(session, headers, year, window_start, window_end, types, out_dir, ledger,
                                       types_key)
            except Exception as exc:
                failed += 1
                ledger.write(event="year_failed", year=year, types_key=types_key, error=str(exc)[:300])
    finally:
        session.close()
    ledger.write(event="run_complete", types_key=types_key, failed=failed, items=total)
    return 1 if failed else 0


def _date_of(item):
    """Best-effort event date: the earliest value among any key ending in '_date'."""
    dates = [v for k, v in item.items() if k.endswith("_date") and isinstance(v, str) and v]
    return min(dates) if dates else None


def summarize_dict(out_dir):
    per_type_year = defaultdict(Counter)
    earliest = {}
    latest = {}
    for year_dir in sorted(Path(out_dir, "pages").glob("*")):
        if not year_dir.is_dir():
            continue
        for page_file in sorted(year_dir.glob("*.json.gz")):
            with gzip.open(page_file, "rt", encoding="utf-8") as handle:
                body = json.load(handle)
            for action_type, items in (body.get("corporate_actions") or {}).items():
                for item in items:
                    date = _date_of(item)
                    year = date[:4] if date else "unknown"
                    per_type_year[action_type][year] += 1
                    if date:
                        if action_type not in earliest or date < earliest[action_type]:
                            earliest[action_type] = date
                        if action_type not in latest or date > latest[action_type]:
                            latest[action_type] = date
    return {
        "per_type_per_year_counts": {t: dict(sorted(c.items())) for t, c in sorted(per_type_year.items())},
        "earliest_by_type": earliest,
        "latest_by_type": latest,
    }


def cmd_collect(args):
    return collect(args.env_file, args.out, args.start, args.end, args.include_cash_dividends)


def cmd_summarize(args):
    summary = summarize_dict(args.dir)
    for action_type, by_year in summary["per_type_per_year_counts"].items():
        total = sum(by_year.values())
        print(f"{action_type}: total={total} earliest={summary['earliest_by_type'].get(action_type)} "
              f"latest={summary['latest_by_type'].get(action_type)}")
        for year, count in by_year.items():
            print(f"  {year}: {count}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect")
    p_collect.add_argument("--env-file", required=True)
    p_collect.add_argument("--out", required=True)
    p_collect.add_argument("--start", default="2016-01-01")
    p_collect.add_argument("--end", default="2026-09-21")
    p_collect.add_argument("--include-cash-dividends", action="store_true")
    p_collect.set_defaults(func=cmd_collect)

    p_summarize = sub.add_parser("summarize")
    p_summarize.add_argument("--dir", required=True)
    p_summarize.set_defaults(func=cmd_summarize)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
