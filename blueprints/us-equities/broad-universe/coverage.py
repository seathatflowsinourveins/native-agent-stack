#!/usr/bin/env python3
"""Offline, deterministic DuckDB-based coverage builder for the broad-universe
daily-bar dataset produced by collect_daily.py.

Three subcommands:
  materialize  build daily.parquet from bars/{raw,all}/*.csv.gz, refusing to run
               unless the ledger proves the collection run is complete.
  build        assemble a measured, offline coverage-manifest.json from
               daily.parquet, the ledger, the asset master and identity files.
  probe        a bounded (<=40 GET), read-only, data-host-only live probe of a
               few entitlement edges (IEX/1Min bar range, one OTC symbol on
               two feeds), recorded verbatim with statuses and rate limits.

No network happens in materialize or build. Only probe touches the network,
and only GET requests to the market-data host, never an account/trading path.
"""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb

HOST = "https://data.alpaca.markets"
MAX_RETRIES = 5
CSV_COLUMN_TYPES = {"symbol": "VARCHAR", "t": "VARCHAR", "o": "DOUBLE", "h": "DOUBLE",
                     "l": "DOUBLE", "c": "DOUBLE", "v": "DOUBLE", "n": "BIGINT", "vw": "DOUBLE"}
FUND_NAME_PATTERN = re.compile(r"ETF|ETN|Fund|Trust|Shares|ProShares|Direxion|iShares|SPDR|Index|Portfolio", re.I)


def _load_collect_daily():
    path = Path(__file__).resolve().with_name("collect_daily.py")
    spec = importlib.util.spec_from_file_location("collect_daily", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_ledger_events(dataset_dir):
    events = []
    path = os.path.join(dataset_dir, "ledger.jsonl")
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def read_plan(dataset_dir):
    return read_json(os.path.join(dataset_dir, "plan.json"))


# --------------------------------------------------------------------------- materialize


def check_ledger_complete(plan, events):
    """True/reasons: every planned batch is complete for every adjustment and the
    latest run_complete event reports zero failures."""
    reasons = []
    complete = {(e["adjustment"], e["batch"]) for e in events if e.get("event") == "batch_complete"}
    for adjustment in plan["adjustments"]:
        for index in range(plan["batches"]):
            if (adjustment, index) not in complete:
                reasons.append(f"missing batch_complete adjustment={adjustment} batch={index}")
    runs = [e for e in events if e.get("event") == "run_complete"]
    if not runs:
        reasons.append("no run_complete event in ledger")
    elif runs[-1].get("failed", 1) != 0:
        reasons.append(f"latest run_complete reports failed={runs[-1].get('failed')}")
    return not reasons, reasons


def detect_duplicate_rows(con, table):
    rows = con.execute(
        f"SELECT symbol, session_date, count(*) AS n FROM {table} GROUP BY 1, 2 HAVING count(*) > 1"
    ).fetchall()
    return [{"symbol": r[0], "session_date": str(r[1]), "count": r[2]} for r in rows]


def load_bars_view(con, dataset_dir, adjustment, view_name, prefix):
    glob_path = os.path.join(dataset_dir, "bars", adjustment, "*.csv.gz")
    columns = json.dumps(CSV_COLUMN_TYPES)
    con.execute(f"""
        CREATE OR REPLACE TABLE {view_name} AS
        SELECT symbol,
               CAST(substr(t, 1, 10) AS DATE) AS session_date,
               o AS {prefix}_o, h AS {prefix}_h, l AS {prefix}_l, c AS {prefix}_c,
               v AS {prefix}_v, n AS {prefix}_n, vw AS {prefix}_vw
        FROM read_csv('{glob_path}', columns={columns}, header=true, filename=false)
    """)


def materialize(dataset_dir):
    """Build daily.parquet. Returns (ok, detail-dict)."""
    out_path = os.path.join(dataset_dir, "daily.parquet")
    if os.path.exists(out_path):
        return False, {"reason": "daily.parquet already exists; remove it before rematerializing"}
    con = duckdb.connect()
    load_bars_view(con, dataset_dir, "raw", "raw_bars", "raw")
    load_bars_view(con, dataset_dir, "all", "all_bars", "all")
    dup_raw = detect_duplicate_rows(con, "raw_bars")
    dup_all = detect_duplicate_rows(con, "all_bars")
    if dup_raw or dup_all:
        return False, {"reason": "duplicate (symbol, session_date) rows detected",
                        "raw_duplicates": len(dup_raw), "all_duplicates": len(dup_all),
                        "raw_examples": dup_raw[:20], "all_examples": dup_all[:20]}
    con.execute(f"""
        COPY (
            SELECT
                coalesce(r.symbol, a.symbol) AS symbol,
                coalesce(r.session_date, a.session_date) AS session_date,
                r.raw_o, r.raw_h, r.raw_l, r.raw_c, r.raw_v, r.raw_n, r.raw_vw,
                a.all_o, a.all_h, a.all_l, a.all_c, a.all_v,
                (r.symbol IS NOT NULL) AS in_raw,
                (a.symbol IS NOT NULL) AS in_all
            FROM raw_bars r
            FULL OUTER JOIN all_bars a
              ON r.symbol = a.symbol AND r.session_date = a.session_date
        ) TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]
    return True, {"rows": rows, "path": out_path}


def cmd_materialize(args):
    plan = read_plan(args.dataset)
    events = read_ledger_events(args.dataset)
    ok, reasons = check_ledger_complete(plan, events)
    if not ok:
        print("REFUSED: ledger incomplete", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 1
    ok, detail = materialize(args.dataset)
    if not ok:
        print(f"REFUSED: {detail['reason']}", file=sys.stderr)
        print(json.dumps(detail, indent=1, default=str), file=sys.stderr)
        return 1
    print(json.dumps(detail, indent=1))
    return 0


# --------------------------------------------------------------------------- build: collection


def pagination_proof(page_events):
    """Group page ledger events by (adjustment, batch label); every group's pages
    must be contiguous from 0 and only the last may have next_page_token_present
    false."""
    groups = defaultdict(list)
    for event in page_events:
        groups[(event["adjustment"], event["batch"])].append(event)
    violations = []
    for key, items in groups.items():
        items = sorted(items, key=lambda e: e["page"])
        pages = [item["page"] for item in items]
        contiguous = pages == list(range(len(items)))
        terminal_ok = bool(items) and not items[-1]["next_page_token_present"] and \
            all(item["next_page_token_present"] for item in items[:-1])
        if not (contiguous and terminal_ok):
            violations.append({"adjustment": key[0], "batch": key[1], "pages": pages,
                                "next_page_token_present": [i["next_page_token_present"] for i in items]})
    return {"symbol_groups_checked": len(groups), "violations": violations}


def verify_page_sha256(dataset_dir, page_events, sample_fraction=1.0):
    sample_fraction = min(1.0, max(0.0, sample_fraction))
    if sample_fraction >= 1.0 or not page_events:
        sample = page_events
    else:
        step = max(1, int(round(1.0 / sample_fraction)))
        sample = page_events[::step]
    verified = 0
    mismatches = []
    for event in sample:
        path = os.path.join(dataset_dir, "pages", event["adjustment"], event["file"])
        try:
            with gzip.open(path, "rb") as handle:
                raw = handle.read()
        except (FileNotFoundError, OSError):
            mismatches.append({"file": event["file"], "adjustment": event["adjustment"], "reason": "missing"})
            continue
        actual = hashlib.sha256(raw).hexdigest()
        if actual != event["sha256"]:
            mismatches.append({"file": event["file"], "adjustment": event["adjustment"], "reason": "sha_mismatch",
                                "expected": event["sha256"], "actual": actual})
        else:
            verified += 1
    return {"pages_total": len(page_events), "pages_checked": len(sample),
            "sampled_fraction": len(sample) / len(page_events) if page_events else 1.0,
            "verified": verified, "mismatches": mismatches}


def build_collection_section(con, dataset_dir, plan, events, page_sample):
    pages = [e for e in events if e.get("event") == "page"]
    batch_complete = [e for e in events if e.get("event") == "batch_complete"]
    batch_failed = [e for e in events if e.get("event") == "batch_failed"]
    rejected = [e for e in events if e.get("event") == "rejected_symbol"]

    per_adjustment_pages = defaultdict(lambda: {"pages": 0, "bytes": 0, "bars": 0})
    for event in pages:
        entry = per_adjustment_pages[event["adjustment"]]
        entry["pages"] += 1
        entry["bytes"] += event["bytes"]
        entry["bars"] += event["bars"]
    per_adjustment_batches = defaultdict(lambda: {"complete": 0, "failed": 0, "bars": 0})
    for event in batch_complete:
        entry = per_adjustment_batches[event["adjustment"]]
        entry["complete"] += 1
        entry["bars"] += event["bars"]
    for event in batch_failed:
        per_adjustment_batches[event["adjustment"]]["failed"] += 1

    csv_totals = {}
    for adjustment in plan["adjustments"]:
        glob_path = os.path.join(dataset_dir, "bars", adjustment, "*.csv.gz")
        columns = json.dumps(CSV_COLUMN_TYPES)
        csv_totals[adjustment] = con.execute(
            f"SELECT count(*) FROM read_csv('{glob_path}', columns={columns}, header=true)"
        ).fetchone()[0]
    ledger_totals = {a: per_adjustment_batches[a]["bars"] for a in plan["adjustments"]}

    with open(os.path.join(dataset_dir, "ledger.jsonl"), "rb") as handle:
        ledger_sha = hashlib.sha256(handle.read()).hexdigest()

    return {
        "plan": plan,
        "per_adjustment_pages": dict(per_adjustment_pages),
        "per_adjustment_batches": dict(per_adjustment_batches),
        "rejected_symbols": rejected,
        "pagination_proof": pagination_proof(pages),
        "page_sha256_reverification": verify_page_sha256(dataset_dir, pages, page_sample),
        "row_totals": {"csv_totals": csv_totals, "ledger_totals": ledger_totals,
                       "match": all(csv_totals[a] == ledger_totals[a] for a in plan["adjustments"])},
        "ledger_sha256": ledger_sha,
    }


# --------------------------------------------------------------------------- build: universe/calendar


def compute_gap_by_symbol(con):
    """Sessions in the SPY calendar strictly between a symbol's first and last
    bar for which the symbol has no bar."""
    rows = con.execute("""
        WITH cal AS (SELECT DISTINCT session_date FROM daily WHERE symbol = 'SPY'),
        bars AS (
            SELECT DISTINCT symbol, session_date FROM daily
            WHERE (in_raw OR in_all) AND session_date IN (SELECT session_date FROM cal)
        ),
        rng AS (SELECT symbol, min(session_date) AS fst, max(session_date) AS lst FROM bars GROUP BY symbol),
        expected AS (
            SELECT r.symbol, count(*) AS exp
            FROM rng r JOIN cal c ON c.session_date BETWEEN r.fst AND r.lst
            GROUP BY r.symbol
        ),
        actual AS (SELECT symbol, count(*) AS act FROM bars GROUP BY symbol)
        SELECT e.symbol, e.exp - a.act AS gap FROM expected e JOIN actual a USING (symbol)
    """).fetchall()
    return {symbol: gap for symbol, gap in rows}


def percentile(sorted_values, p):
    if not sorted_values:
        return None
    idx = min(len(sorted_values) - 1, int(round(p * (len(sorted_values) - 1))))
    return sorted_values[idx]


def build_calendar_section(con, gap_by_symbol):
    sessions = [r[0] for r in con.execute(
        "SELECT DISTINCT session_date FROM daily WHERE symbol = 'SPY' ORDER BY 1").fetchall()]
    per_session = con.execute("""
        SELECT session_date, count(DISTINCT symbol) FROM daily WHERE in_raw OR in_all GROUP BY 1
    """).fetchall()
    by_year = defaultdict(list)
    for session_date, count in per_session:
        by_year[session_date.year].append(count)
    per_year_stats = {str(year): {"min": min(v), "median": statistics.median(v), "max": max(v)}
                       for year, v in sorted(by_year.items())}
    gaps_sorted = sorted(gap_by_symbol.values())
    return {
        "sessions": len(sessions),
        "first_session": str(sessions[0]) if sessions else None,
        "last_session": str(sessions[-1]) if sessions else None,
        "per_year_symbols_per_session": per_year_stats,
        "gap_summary": {
            "symbols_with_any_bar": len(gap_by_symbol),
            "symbols_with_gap": sum(1 for g in gaps_sorted if g > 0),
            "p50": percentile(gaps_sorted, 0.50),
            "p95": percentile(gaps_sorted, 0.95),
            "max": gaps_sorted[-1] if gaps_sorted else None,
        },
    }, sessions


def build_universe_section(con, identities, sessions):
    have_bars = {r[0] for r in con.execute(
        "SELECT DISTINCT symbol FROM daily WHERE in_raw OR in_all").fetchall()}
    zero_bar = [s for s in identities if s not in have_bars]
    zero_bar_by_status_exchange = Counter()
    for symbol in zero_bar:
        for ident in identities[symbol]:
            zero_bar_by_status_exchange[f"{ident['status']}/{ident['exchange']}"] += 1

    first_last = con.execute("""
        SELECT symbol, min(session_date), max(session_date) FROM daily
        WHERE in_raw OR in_all GROUP BY symbol
    """).fetchall()
    first_hist, last_hist, per_year_symbols = Counter(), Counter(), defaultdict(set)
    for symbol, fst, lst in first_last:
        first_hist[fst.year] += 1
        last_hist[lst.year] += 1
    for year, count in con.execute("""
        SELECT extract(year FROM session_date)::INT, count(DISTINCT symbol) FROM daily
        WHERE in_raw OR in_all GROUP BY 1 ORDER BY 1
    """).fetchall():
        per_year_symbols[year] = count

    inactive_symbols = {s for s, v in identities.items() if any(i["status"] == "inactive" for i in v)}
    active_symbols = {s for s, v in identities.items() if any(i["status"] == "active" for i in v)}
    inactive_last_year_hist = Counter()
    session_index = {d: i for i, d in enumerate(sessions)}
    end_idx = len(sessions) - 1
    stale_active = []
    for symbol, fst, lst in first_last:
        if symbol in inactive_symbols:
            inactive_last_year_hist[lst.year] += 1
        if symbol in active_symbols and lst in session_index and (end_idx - session_index[lst]) > 5:
            stale_active.append({"symbol": symbol, "last_session": str(lst), "sessions_before_end": end_idx - session_index[lst]})

    return {
        "requested_symbols": len(identities),
        "symbols_with_raw_bar": con.execute("SELECT count(DISTINCT symbol) FROM daily WHERE in_raw").fetchone()[0],
        "symbols_with_all_bar": con.execute("SELECT count(DISTINCT symbol) FROM daily WHERE in_all").fetchone()[0],
        "zero_bar_symbols": len(zero_bar),
        "zero_bar_symbols_by_status_exchange": dict(zero_bar_by_status_exchange),
        "first_session_year_histogram": {str(y): c for y, c in sorted(first_hist.items())},
        "last_session_year_histogram": {str(y): c for y, c in sorted(last_hist.items())},
        "symbols_with_bars_per_year": {str(y): c for y, c in sorted(per_year_symbols.items())},
        "inactive_last_bar_year_histogram": {str(y): c for y, c in sorted(inactive_last_year_hist.items())},
        "active_symbols_stale_gt_5_sessions": {"count": len(stale_active), "examples": stale_active[:50]},
    }


def build_quality_section(con):
    row = con.execute("""
        SELECT
          sum(CASE WHEN in_raw AND (raw_o <= 0 OR raw_h <= 0 OR raw_l <= 0 OR raw_c <= 0) THEN 1 ELSE 0 END),
          sum(CASE WHEN in_all AND (all_o <= 0 OR all_h <= 0 OR all_l <= 0 OR all_c <= 0) THEN 1 ELSE 0 END),
          sum(CASE WHEN in_raw AND raw_h < raw_l THEN 1 ELSE 0 END),
          sum(CASE WHEN in_all AND all_h < all_l THEN 1 ELSE 0 END),
          sum(CASE WHEN in_raw AND (raw_o < raw_l OR raw_o > raw_h OR raw_c < raw_l OR raw_c > raw_h) THEN 1 ELSE 0 END),
          sum(CASE WHEN in_all AND (all_o < all_l OR all_o > all_h OR all_c < all_l OR all_c > all_h) THEN 1 ELSE 0 END),
          sum(CASE WHEN in_raw AND raw_v = 0 THEN 1 ELSE 0 END),
          sum(CASE WHEN in_all AND all_v = 0 THEN 1 ELSE 0 END),
          sum(CASE WHEN in_raw AND raw_v <> floor(raw_v) THEN 1 ELSE 0 END),
          sum(CASE WHEN in_all AND all_v <> floor(all_v) THEN 1 ELSE 0 END),
          sum(CASE WHEN in_raw <> in_all THEN 1 ELSE 0 END),
          count(*)
        FROM daily
    """).fetchone()
    keys = ["raw_non_positive_price", "all_non_positive_price", "raw_high_lt_low", "all_high_lt_low",
            "raw_open_close_outside_range", "all_open_close_outside_range", "raw_zero_volume", "all_zero_volume",
            "raw_fractional_volume", "all_fractional_volume", "raw_all_presence_mismatch", "total_rows"]
    return {k: (v or 0) for k, v in zip(keys, row)}


def build_identity_section(identities_doc, plan, probe_doc, reproduced):
    collisions = identities_doc.get("collisions", {})
    pattern_counts = Counter()
    for entries in collisions.values():
        pattern_counts["+".join(sorted(e["status"] for e in entries))] += 1
    named = {}
    for request in probe_doc.get("requests", []):
        if request["path"] in ("/v2/assets/FB", "/v2/assets/META", "/v2/assets/TWTR"):
            named[request["path"].rsplit("/", 1)[-1]] = request.get("result")
    return {
        "collisions_total": len(collisions),
        "collisions_by_status_pattern": dict(pattern_counts),
        "excluded_exchange_assets": plan.get("excluded_exchange_assets", {}),
        "symbol_collisions_in_plan": plan.get("symbol_collisions"),
        "fb_meta_twtr": named,
        "assets_reproduced_match": reproduced,
    }


def build_requested_names_section(con, gap_by_symbol, names=("META", "AMD")):
    out = {}
    for name in names:
        row = con.execute(
            "SELECT min(session_date), max(session_date), count(*) FROM daily "
            "WHERE symbol = ? AND (in_raw OR in_all)", [name]).fetchone()
        present = row[0] is not None
        out[name] = {
            "present": present,
            "first_session": str(row[0]) if present else None,
            "last_session": str(row[1]) if present else None,
            "bar_count": row[2] if present else 0,
            "gap_count": gap_by_symbol.get(name) if present else None,
        }
    return out


def build_eligible_universe_section(con):
    con.execute("""
        CREATE OR REPLACE TEMP VIEW elig_sessions AS
        WITH r AS (
            SELECT symbol, session_date, raw_c, raw_c * raw_v AS dv
            FROM daily WHERE in_raw AND raw_c IS NOT NULL AND raw_v IS NOT NULL
        ),
        w AS (
            SELECT symbol, session_date, raw_c,
                   median(dv) OVER (PARTITION BY symbol ORDER BY session_date
                                     ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS med20,
                   count(*) OVER (PARTITION BY symbol ORDER BY session_date
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_bars
            FROM r
        )
        SELECT session_date, count(*) AS n
        FROM w
        WHERE raw_c >= 5 AND med20 >= 20000000 AND prior_bars >= 60
        GROUP BY session_date
    """)
    rows = con.execute("""
        SELECT extract(year FROM session_date)::INT, min(n), median(n), max(n)
        FROM elig_sessions GROUP BY 1 ORDER BY 1
    """).fetchall()
    return {str(y): {"min": mn, "median": med, "max": mx} for y, mn, med, mx in rows}


def _parse_iso(value):
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age_seconds(mark, observed):
    a, b = _parse_iso(mark), _parse_iso(observed)
    if a is None or b is None:
        return None
    return (b - a).total_seconds()


def build_entitlements_section(probe_doc, live_probe_doc):
    feeds = defaultdict(dict)
    history_probes = []
    for request in probe_doc.get("requests", []):
        path, params, observed = request["path"], request.get("params") or {}, request.get("observed_at")
        if path in ("/v2/stocks/quotes/latest", "/v2/stocks/bars/latest"):
            feed = params.get("feed", "unknown")
            ages = {}
            for symbol, quote in (request.get("result") or {}).items():
                mark = quote.get("t")
                if mark:
                    ages[symbol] = _age_seconds(mark, observed)
            feeds[feed]["quote_age_seconds" if path.endswith("quotes/latest") else "bar_age_seconds"] = ages
        elif path == "/v2/stocks/bars" and (params.get("start") or "").startswith("2000"):
            history_probes.append({"feed": params.get("feed"), "timeframe": params.get("timeframe"),
                                    "symbols": params.get("symbols"), "result": request.get("result")})
    news = []
    for r in probe_doc.get("requests", []):
        if r["path"] != "/v1beta1/news":
            continue
        result = r.get("result") or {}
        # Counts and timestamps only: never a headline or article body.
        news.append({"params": r.get("params"), "status": r.get("status"), "observed_at": r.get("observed_at"),
                     "count": result.get("n"), "first_created": result.get("first_created")})
    screens = {}
    for r in probe_doc.get("requests", []):
        if "screener" not in r["path"]:
            continue
        result = r.get("result") or {}
        counts = {k: len(v) for k, v in result.items() if isinstance(v, list)}
        screens[r["path"]] = {"params": r.get("params"), "status": r.get("status"), "counts": counts}
    corporate_actions_available = any(r["path"] == "/v1/corporate-actions" for r in probe_doc.get("requests", []))
    out = {
        "generated_at": probe_doc.get("generated_at"),
        "feeds": dict(feeds),
        "history_start_probes": history_probes,
        "news_probes": news,
        "screens_bounded_top_n": screens,
        "corporate_actions_available": corporate_actions_available,
    }
    if live_probe_doc:
        out["live_probe"] = live_probe_doc
    return out


LIMITATIONS = [
    "no listing/delisting dates: the provider asset master exposes no historical listing or delisting timestamps",
    "no historical security type: instrument-lane classification uses the CURRENT asset name only",
    "ticker reuse: a symbol reused after delisting resolves to the current holder; collisions are counted, not resolved",
    "names the provider never carried are absent from the universe; this survivorship exposure is only measured indirectly",
    "unknown bar revisions: bars downloaded on the collection date are not proven to equal what was published at each historical close",
    "OTC symbols are excluded from the daily-bar collection entirely",
    "minute bars are not collected market-wide; only a bounded probe sample exists",
]


def cmd_build(args):
    plan = read_plan(args.dataset)
    events = read_ledger_events(args.dataset)
    identities_doc = read_json(os.path.join(args.dataset, "symbol-identities.json"))
    identities = identities_doc["identities"]
    probe_doc = read_json(args.probe)
    live_probe_doc = read_json(args.probes) if args.probes else None

    collect_daily = _load_collect_daily()
    symbols, reproduced_identities, collisions, skipped = collect_daily.select_symbols(args.assets)
    reproduced = {
        "symbol_count_match": len(symbols) == plan["symbols"],
        "symbols_sha256_match": collect_daily.symbols_digest(symbols) == plan["symbols_sha256"],
        "collision_count_match": len(collisions) == plan.get("symbol_collisions"),
        "excluded_exchange_assets_match": skipped == plan.get("excluded_exchange_assets"),
    }

    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE VIEW daily AS SELECT * FROM read_parquet('{os.path.join(args.dataset, 'daily.parquet')}')")

    calendar_section, sessions = build_calendar_section(con, compute_gap_by_symbol(con))
    gap_by_symbol = compute_gap_by_symbol(con)
    manifest = {
        "schema": "broad-universe-coverage-manifest/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collection": build_collection_section(con, args.dataset, plan, events, args.page_sample),
        "universe": build_universe_section(con, identities, sessions),
        "calendar": calendar_section,
        "quality_flags": build_quality_section(con),
        "identity": build_identity_section(identities_doc, plan, probe_doc, reproduced),
        "requested_names": build_requested_names_section(con, gap_by_symbol),
        "eligible_universe": build_eligible_universe_section(con),
        "entitlements": build_entitlements_section(probe_doc, live_probe_doc),
        "limitations": LIMITATIONS,
    }
    if args.corporate_actions:
        ca_module = _load_corporate_actions()
        manifest["corporate_actions"] = ca_module.summarize_dict(args.corporate_actions)

    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1, default=str)
    print(f"wrote {args.out}")
    return 0


def _load_corporate_actions():
    path = Path(__file__).resolve().with_name("corporate_actions.py")
    spec = importlib.util.spec_from_file_location("corporate_actions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- probe (bounded live)


def _probe_get(session, headers, path, params):
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(HOST + path, headers=headers, params=params, timeout=(5, 30),
                                    allow_redirects=False)
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"network failure after {attempt} attempts: {type(exc).__name__}") from exc
            time.sleep(delay)
            delay *= 2
            continue
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == MAX_RETRIES:
                break
            time.sleep(delay)
            delay *= 2
            continue
        break
    observed = datetime.now(timezone.utc).isoformat()
    try:
        body = response.json()
    except ValueError:
        body = response.text[:500]
    ratelimit = {k: v for k, v in response.headers.items() if k.lower().startswith("x-ratelimit")}
    return {"path": path, "params": params, "status": response.status_code, "observed_at": observed,
            "ratelimit": ratelimit, "result": body}


def cmd_probe(args):
    import requests
    collect_daily = _load_collect_daily()
    key, secret = collect_daily.read_credentials(args.env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    session = requests.Session()
    session.trust_env = False
    requests_log = []

    def get(path, params):
        record = _probe_get(session, headers, path, params)
        requests_log.append(record)
        return record

    try:
        base_daily = {"symbols": "AMD,META", "timeframe": "1Day", "start": "2016-01-01", "feed": "iex", "limit": 1}
        get("/v2/stocks/bars", {**base_daily, "sort": "asc"})
        get("/v2/stocks/bars", {**base_daily, "sort": "desc"})

        otc_symbol = args.otc_symbol
        if not otc_symbol and args.assets:
            for asset in read_json(args.assets):
                if asset.get("exchange") == "OTC" and asset.get("status") == "active":
                    otc_symbol = asset["symbol"]
                    break

        minute_symbols = ["META", "AMD", "SPY", "TWTR"]
        if args.other_inactive_symbol:
            minute_symbols.append(args.other_inactive_symbol)
        base_minute = {"symbols": ",".join(minute_symbols), "timeframe": "1Min", "start": "2016-01-01",
                       "feed": "sip", "limit": 1}
        get("/v2/stocks/bars", {**base_minute, "sort": "asc"})
        get("/v2/stocks/bars", {**base_minute, "sort": "desc"})

        if otc_symbol:
            get("/v2/stocks/bars", {"symbols": otc_symbol, "timeframe": "1Day", "limit": 1, "feed": "sip"})
            get("/v2/stocks/bars", {"symbols": otc_symbol, "timeframe": "1Day", "limit": 1, "feed": "otc"})
    finally:
        session.close()

    assert len(requests_log) <= 40
    doc = {"schema": "broad-universe-coverage-probe/1", "generated_at": datetime.now(timezone.utc).isoformat(),
           "otc_symbol": otc_symbol, "requests": requests_log}
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, default=str)
    print(f"wrote {args.out} ({len(requests_log)} requests)")
    return 0


# --------------------------------------------------------------------------- CLI


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_materialize = sub.add_parser("materialize")
    p_materialize.add_argument("--dataset", required=True)
    p_materialize.set_defaults(func=cmd_materialize)

    p_build = sub.add_parser("build")
    p_build.add_argument("--dataset", required=True)
    p_build.add_argument("--assets", nargs=2, required=True, metavar=("ACTIVE", "INACTIVE"))
    p_build.add_argument("--probe", required=True)
    p_build.add_argument("--corporate-actions", default=None)
    p_build.add_argument("--probes", default=None)
    p_build.add_argument("--out", required=True)
    p_build.add_argument("--page-sample", type=float, default=1.0,
                          help="fraction of ledger pages to re-verify by sha256 (default: all)")
    p_build.set_defaults(func=cmd_build)

    p_probe = sub.add_parser("probe")
    p_probe.add_argument("--env-file", required=True)
    p_probe.add_argument("--out", required=True)
    p_probe.add_argument("--assets", default=None, help="active asset-master JSON, to pick one OTC symbol")
    p_probe.add_argument("--otc-symbol", default=None, help="explicit active OTC symbol override")
    p_probe.add_argument("--other-inactive-symbol", default=None)
    p_probe.set_defaults(func=cmd_probe)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
