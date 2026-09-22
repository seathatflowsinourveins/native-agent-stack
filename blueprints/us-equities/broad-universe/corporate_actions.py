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


SCOPE_FIELDS = ("start", "end", "types", "types_key", "page_limit")


def scope_conflicts(existing_plan, plan):
    """Scope fields on which a retained corporate-actions plan disagrees with this run."""
    return [{"field": key, "recorded": existing_plan.get(key), "requested": plan.get(key)}
            for key in SCOPE_FIELDS if existing_plan.get(key) != plan.get(key)]


def completed_years(ledger_path, types_key, windows=None):
    """Years already collected for these types. When `windows` maps year -> (start, end),
    a recorded year counts as done only if its recorded window matches exactly, so
    widening --end inside an already-collected year is re-collected rather than skipped.
    Legacy records carry no window; collect() refuses a changed plan scope before they
    are consulted, so an unchanged re-run still resumes."""
    done = set()
    if os.path.exists(ledger_path):
        with open(ledger_path, encoding="utf-8") as handle:
            for line in handle:
                rec = json.loads(line)
                if rec.get("event") != "year_complete" or rec.get("types_key") != types_key:
                    continue
                if windows is not None and rec.get("window_start") is not None:
                    wanted = windows.get(rec["year"])
                    if wanted != (rec.get("window_start"), rec.get("window_end")):
                        continue
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
        ledger.write(event="page", year=year, types_key=types_key, window_start=window_start,
                     window_end=window_end, page=page,
                     sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), items=sum(counts.values()),
                     by_type=dict(counts), next_page_token_present=bool(token), attempts=attempts,
                     elapsed_s=round(time.time() - started, 3), file=name)
        page += 1
        if not token:
            break
    ledger.write(event="year_complete", year=year, types_key=types_key, window_start=window_start,
                 window_end=window_end, pages=page, items=total_items, by_type=dict(total_by_type))
    return total_items


def collect(env_file, out_dir, start, end, include_cash_dividends):
    types = types_for(include_cash_dividends)
    types_key = hashlib.sha256(",".join(types).encode()).hexdigest()[:16]
    plan = {"schema": "broad-universe-corporate-actions-plan/1", "created_at": utc_now(), "host": HOST, "path": PATH,
            "types": list(types), "types_key": types_key, "start": start, "end": end, "page_limit": PAGE_LIMIT}
    # The scope refusal comes before credentials and the HTTP client: a run that must not
    # reuse this directory should stop before it touches either.
    plan_path = os.path.join(out_dir, "plan.json")
    if os.path.exists(plan_path):
        with open(plan_path, encoding="utf-8") as handle:
            existing = json.load(handle)
        conflicts = scope_conflicts(existing, plan)
        if conflicts:
            detail = "; ".join(f"{c['field']}: recorded={c['recorded']!r} requested={c['requested']!r}"
                               for c in conflicts)
            raise SystemExit(
                f"REFUSED: plan.json in {out_dir} was written for a different request scope ({detail}). "
                "Completed years of the recorded scope must not be reused for this one: "
                "collect the new scope into a new --out directory.")

    import requests
    collect_daily = _load_collect_daily()
    key, secret = collect_daily.read_credentials(env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    os.makedirs(out_dir, mode=0o700, exist_ok=True)
    ledger = collect_daily.Ledger(os.path.join(out_dir, "ledger.jsonl"))
    windows = {year: (window_start, window_end) for year, window_start, window_end in year_windows(start, end)}
    done = completed_years(os.path.join(out_dir, "ledger.jsonl"), types_key, windows)

    with open(plan_path, "w", encoding="utf-8") as handle:
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
    """Best-effort event date: the earliest value among any key ending in '_date'.
    Retained only as a secondary attribute: it can fall outside the window that
    returned the action, so it never decides which year an action is counted in."""
    dates = [v for k, v in item.items() if k.endswith("_date") and isinstance(v, str) and v]
    return min(dates) if dates else None


# One named date per action, most specific first. The field actually used is reported
# per type so a reader never has to guess which date a summary line refers to.
DATE_FIELD_PREFERENCE = ("ex_date", "effective_date", "process_date", "payable_date", "record_date",
                         "declaration_date", "due_bill_off_date", "expiration_date", "settlement_date")


def selected_date(item):
    """(field_name, value) for the single date this summary reports, or (None, None)."""
    for field in DATE_FIELD_PREFERENCE:
        value = item.get(field)
        if isinstance(value, str) and value:
            return field, value
    others = sorted(k for k, v in item.items() if k.endswith("_date") and isinstance(v, str) and v)
    if others:
        return others[0], item[others[0]]
    return None, None


def _window_year(year_dir):
    name = year_dir.name
    return name if len(name) == 4 and name.isdigit() else "unknown"


def summarize_dict(out_dir):
    """Counts bucketed by the REQUEST WINDOW year (the page directory the action was
    returned in), so every year count corresponds to a window that was actually queried."""
    per_type_year = defaultdict(Counter)
    fields_used = defaultdict(Counter)
    earliest, latest = {}, {}
    min_earliest, min_latest = {}, {}
    for year_dir in sorted(Path(out_dir, "pages").glob("*")):
        if not year_dir.is_dir():
            continue
        window_year = _window_year(year_dir)
        for page_file in sorted(year_dir.glob("*.json.gz")):
            with gzip.open(page_file, "rt", encoding="utf-8") as handle:
                body = json.load(handle)
            for action_type, items in (body.get("corporate_actions") or {}).items():
                for item in items:
                    per_type_year[action_type][window_year] += 1
                    field, date = selected_date(item)
                    if field:
                        fields_used[action_type][field] += 1
                    if date:
                        if action_type not in earliest or date < earliest[action_type]:
                            earliest[action_type] = date
                        if action_type not in latest or date > latest[action_type]:
                            latest[action_type] = date
                    min_date = _date_of(item)
                    if min_date:
                        if action_type not in min_earliest or min_date < min_earliest[action_type]:
                            min_earliest[action_type] = min_date
                        if action_type not in min_latest or min_date > min_latest[action_type]:
                            min_latest[action_type] = min_date
    return {
        "year_basis": "request window (the queried year directory the page was retained in)",
        "per_type_per_year_counts": {t: dict(sorted(c.items())) for t, c in sorted(per_type_year.items())},
        "date_field_by_type": {t: {"primary": c.most_common(1)[0][0], "counts": dict(sorted(c.items()))}
                               for t, c in sorted(fields_used.items())},
        "earliest_by_type": earliest,
        "latest_by_type": latest,
        "secondary_min_of_all_dates": {"note": "earliest key ending in _date on each action; "
                                               "may fall outside the queried window",
                                       "earliest_by_type": min_earliest, "latest_by_type": min_latest},
    }


def cmd_collect(args):
    return collect(args.env_file, args.out, args.start, args.end, args.include_cash_dividends)


def cmd_summarize(args):
    summary = summarize_dict(args.dir)
    print(f"year basis: {summary['year_basis']}")
    for action_type, by_year in summary["per_type_per_year_counts"].items():
        total = sum(by_year.values())
        field = (summary["date_field_by_type"].get(action_type) or {}).get("primary", "none")
        print(f"{action_type}: total={total} date_field={field} "
              f"earliest={summary['earliest_by_type'].get(action_type)} "
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
