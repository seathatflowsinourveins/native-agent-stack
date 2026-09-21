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


def check_ledger_complete(plan, events, supplement_plan=None):
    """True/reasons: every planned batch of the main series ('b') and, when present,
    the supplement series ('s') is complete for every adjustment, and the latest
    run_complete of each series reports zero failures."""
    reasons = []
    complete = defaultdict(list)
    for event in events:
        if event.get("event") == "batch_complete":
            complete[(event.get("series", "b"), event["adjustment"], event["batch"])].append(event)
    plans = [("b", plan)] + ([("s", supplement_plan)] if supplement_plan else [])
    for series, item in plans:
        expected_fingerprint = item.get("request_sha256")
        for adjustment in item["adjustments"]:
            for index in range(item["batches"]):
                recorded = complete.get((series, adjustment, index))
                if not recorded:
                    reasons.append(f"missing batch_complete series={series} adjustment={adjustment} batch={index}")
                    continue
                # A completion recorded under a different request scope proves nothing about
                # the bars this plan asks for; a legacy record carries no fingerprint at all.
                if expected_fingerprint and all(
                        e.get("request_sha256") not in (None, expected_fingerprint) for e in recorded):
                    reasons.append(f"batch_complete series={series} adjustment={adjustment} batch={index} "
                                   "was recorded for a different request scope than plan.request_sha256")
        runs = [e for e in events if e.get("event") == "run_complete" and e.get("series", "b") == series]
        if not runs:
            reasons.append(f"no run_complete event for series={series}")
        elif runs[-1].get("failed", 1) != 0:
            reasons.append(f"latest run_complete series={series} reports failed={runs[-1].get('failed')}")
    return not reasons, reasons


def read_supplement_plan(dataset_dir):
    path = os.path.join(dataset_dir, "plan-supplement.json")
    return read_json(path) if os.path.exists(path) else None


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


DUPLICATE_SERIES_MIN_SESSIONS = 20
# The identical sessions must cover essentially the whole of the dropped candidate's
# history inside the shared span. 25 scattered coincidental matches inside 800 genuine
# sessions are evidence of nothing and must not delete rows from a live security.
DUPLICATE_SERIES_MIN_SPAN_COVERAGE = 0.98
CONTINUITY_RATIO = 1.5
# The corporate-actions API names its types in the singular; older retained envelopes
# were read with plural keys. Both spellings are accepted and counted separately so a
# key-name change can never silently produce zero rename evidence.
RENAME_KINDS = ("name_change", "name_changes", "unit_split", "unit_splits")


def load_rename_pairs(corporate_actions_dir, stats=None):
    """(old_symbol, new_symbol) pairs from retained name_change/unit_split pages.

    `stats`, when given, is filled with how much rename evidence was actually available:
    silence about an empty result is exactly what made the lexicographic fallback
    undiagnosable."""
    pairs = set()
    if stats is not None:
        stats.update({"rename_evidence": "absent", "rename_pairs_loaded": 0,
                      "rename_pairs_by_kind": {}, "rename_pages_read": 0,
                      "rename_kinds_recognized": list(RENAME_KINDS)})
    if not corporate_actions_dir:
        return pairs
    import glob as _glob
    kinds = Counter()
    unknown_kinds = Counter()
    pages = 0
    for path in sorted(_glob.glob(os.path.join(corporate_actions_dir, "pages", "*", "*.json.gz"))):
        with gzip.open(path, "rb") as handle:
            body = json.loads(handle.read())
        pages += 1
        actions = body.get("corporate_actions") or {}
        for kind, items in actions.items():
            if kind not in RENAME_KINDS:
                unknown_kinds[kind] += len(items or ())
                continue
            for item in items or ():
                old, new = item.get("old_symbol"), item.get("new_symbol")
                if old and new and old != new:
                    pairs.add((old, new))
                    kinds[kind] += 1
    if stats is not None:
        stats.update({"rename_evidence": "present", "rename_pairs_loaded": len(pairs),
                      "rename_pairs_by_kind": dict(sorted(kinds.items())), "rename_pages_read": pages,
                      "rename_kinds_recognized": list(RENAME_KINDS),
                      "other_action_kinds_seen": dict(sorted(unknown_kinds.items()))})
    return pairs


def check_corporate_actions_complete(corporate_actions_dir):
    """The same completeness gate the bars ledger gets: every planned year collected for
    the planned types, and a terminal run_complete with zero failures. Rename records are
    identity evidence, so a partial corporate-actions run must not be used as if complete."""
    reasons = []
    plan_path = os.path.join(corporate_actions_dir, "plan.json")
    ledger_path = os.path.join(corporate_actions_dir, "ledger.jsonl")
    if not os.path.exists(plan_path):
        return False, [f"missing {plan_path}"]
    if not os.path.exists(ledger_path):
        return False, [f"missing {ledger_path}"]
    plan = read_json(plan_path)
    events = []
    with open(ledger_path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    types_key = plan.get("types_key")
    done = {e["year"] for e in events
            if e.get("event") == "year_complete" and e.get("types_key") == types_key}
    try:
        first_year, last_year = int(str(plan["start"])[:4]), int(str(plan["end"])[:4])
    except (KeyError, ValueError):
        return False, ["corporate-actions plan.json lacks a parsable start/end window"]
    for year in range(first_year, last_year + 1):
        if year not in done:
            reasons.append(f"missing year_complete year={year} types_key={types_key}")
    runs = [e for e in events if e.get("event") == "run_complete" and e.get("types_key") == types_key]
    if not runs:
        reasons.append(f"no run_complete event for types_key={types_key}")
    elif runs[-1].get("failed", 1) != 0:
        reasons.append(f"latest run_complete reports failed={runs[-1].get('failed')}")
    return not reasons, reasons


def _rename_terminus(members, rename_pairs):
    """Follow retained old->new rename records inside one duplicate component to the
    terminal current ticker. A pair recorded in BOTH directions is no evidence and its
    edge is dropped. Returns the single terminus, or None when the records are absent,
    branching or cyclic."""
    member_set = set(members)
    edges = defaultdict(set)
    for old, new in rename_pairs:
        if old in member_set and new in member_set and (new, old) not in rename_pairs:
            edges[old].add(new)
    if not edges:
        return None
    termini = set()
    for member in members:
        seen = {member}
        current = member
        while True:
            following = edges.get(current)
            if not following:
                break
            if len(following) > 1:
                return None  # branching rename records: ambiguous
            current = next(iter(following))
            if current in seen:
                return None  # cycle: ambiguous
            seen.add(current)
        termini.add(current)
    return termini.pop() if len(termini) == 1 else None


def _components(pairs):
    """Connected components over duplicate pairs (rename chains A->B->C, three-way
    duplicates), so one survivor is chosen per group instead of pair by pair."""
    parent = {}

    def find(symbol):
        parent.setdefault(symbol, symbol)
        while parent[symbol] != symbol:
            parent[symbol] = parent[parent[symbol]]
            symbol = parent[symbol]
        return symbol

    for sym_a, sym_b in pairs:
        root_a, root_b = find(sym_a), find(sym_b)
        if root_a != root_b:
            parent[root_b] = root_a
    groups = defaultdict(set)
    for symbol in parent:
        groups[find(symbol)].add(symbol)
    return [sorted(members) for _, members in sorted(groups.items())]


def dedupe_identity(con, rename_pairs, active_symbols=frozenset(), rename_stats=None):
    """Remove bars served twice under two tickers (the provider answers an old ticker
    with its successor's history). Table `joined` is edited in place; returns a report.

    Everything is decided from an immutable snapshot taken before the first DELETE, so a
    symbol that a chain already dropped can never make a later lookup fail.

    A pair is a duplicate-series candidate when >= DUPLICATE_SERIES_MIN_SESSIONS sessions
    carry identical raw OHLCV (volume > 0) under both symbols AND those sessions cover at
    least DUPLICATE_SERIES_MIN_SPAN_COVERAGE of one side's rows inside the shared span.
    A pair that clears the session count but not the coverage is reported under
    partial_overlap_not_deduped and BOTH symbols are left untouched.

    Candidate pairs are grouped into connected components and ONE survivor is chosen per
    component, in order: retained rename records (chains followed to the terminal
    new_symbol); price continuity after the shared span; active asset-master status; then
    the lexicographic fallback, which is reported with identity_unresolved=true.

    For each non-survivor, its rows inside a shared span are removed - not only the
    byte-identical ones, so no sparse phantom series is left behind - but ONLY on sessions
    where a higher-ranked member it is paired with has a row. A survivor that lacks bars
    for an early part of a rename chain therefore never erases that history; it stays, once,
    under the latest-trading predecessor. Non-identical removed rows are reported as residue."""
    con.execute("""
        CREATE OR REPLACE TEMP TABLE dup_rows AS
        SELECT a.symbol AS sym_a, b.symbol AS sym_b, a.session_date
        FROM joined a JOIN joined b
          ON a.session_date = b.session_date AND a.symbol < b.symbol
         AND a.raw_o = b.raw_o AND a.raw_h = b.raw_h AND a.raw_l = b.raw_l
         AND a.raw_c = b.raw_c AND a.raw_v = b.raw_v
        WHERE a.raw_v > 0
    """)
    # Immutable snapshot: every decision below reads this, never the table being edited.
    con.execute("CREATE OR REPLACE TEMP TABLE identity_snapshot AS "
                "SELECT symbol, session_date, raw_c FROM joined")
    candidates = con.execute(f"""
        SELECT sym_a, sym_b, count(*) AS n, min(session_date), max(session_date)
        FROM dup_rows GROUP BY 1, 2 HAVING count(*) >= {DUPLICATE_SERIES_MIN_SESSIONS} ORDER BY 1, 2
    """).fetchall()

    def rows_in_span(symbol, first, last):
        return con.execute(
            "SELECT count(*) FROM identity_snapshot WHERE symbol = ? AND session_date BETWEEN ? AND ?",
            [symbol, first, last]).fetchone()[0]

    qualified = []
    partial = []
    for sym_a, sym_b, shared, first, last in candidates:
        rows_a, rows_b = rows_in_span(sym_a, first, last), rows_in_span(sym_b, first, last)
        ratio_a = shared / rows_a if rows_a else 0.0
        ratio_b = shared / rows_b if rows_b else 0.0
        entry = {"sym_a": sym_a, "sym_b": sym_b, "identical_sessions": shared,
                 "first": str(first), "last": str(last),
                 "span_coverage_sym_a": round(ratio_a, 6), "span_coverage_sym_b": round(ratio_b, 6),
                 "rows_in_span_sym_a": rows_a, "rows_in_span_sym_b": rows_b}
        if max(ratio_a, ratio_b) >= DUPLICATE_SERIES_MIN_SPAN_COVERAGE:
            qualified.append((sym_a, sym_b))
        else:
            entry["stage"] = "pair"
            entry["reason"] = ("identical sessions cover neither symbol's history inside the shared span; "
                               "coincidental matches are not identity evidence")
            partial.append(entry)

    # Only pairs that cleared BOTH tests are identity evidence; every query below reads
    # this restriction, so a disqualified coincidence can never widen a deletion span.
    con.execute("CREATE OR REPLACE TEMP TABLE qualified_pairs (sym_a VARCHAR, sym_b VARCHAR)")
    if qualified:
        con.executemany("INSERT INTO qualified_pairs VALUES (?, ?)", qualified)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE qualified_dup AS
        SELECT d.sym_a, d.sym_b, d.session_date FROM dup_rows d
        JOIN qualified_pairs q ON d.sym_a = q.sym_a AND d.sym_b = q.sym_b
    """)

    report = []
    unresolved = 0
    components = _components(qualified)
    for members in components:
        member_set = set(members)
        pair_rows = con.execute(f"""
            SELECT max(session_date) FROM qualified_dup
            WHERE sym_a IN ({','.join('?' * len(members))}) AND sym_b IN ({','.join('?' * len(members))})
        """, members + members).fetchone()
        last = pair_rows[0]
        close_row = con.execute(f"""
            SELECT max(raw_c) FROM identity_snapshot
            WHERE session_date = ? AND raw_c IS NOT NULL AND symbol IN ({','.join('?' * len(members))})
        """, [last] + members).fetchone()
        last_close = close_row[0] if close_row else None

        def continues(symbol):
            row = con.execute(
                "SELECT raw_c FROM identity_snapshot WHERE symbol = ? AND session_date > ? "
                "AND raw_c IS NOT NULL ORDER BY session_date LIMIT 1", [symbol, last]).fetchone()
            if not row or not last_close:
                return False
            ratio = row[0] / last_close
            return 1 / CONTINUITY_RATIO <= ratio <= CONTINUITY_RATIO

        keep = _rename_terminus(members, rename_pairs)
        rule = "rename_record" if keep else None
        if keep is None:
            continuing = [m for m in members if continues(m)]
            if len(continuing) == 1:
                keep, rule = continuing[0], "price_continuity"
        if keep is None:
            actives = [m for m in members if m in active_symbols]
            if len(actives) == 1:
                keep, rule = actives[0], "active_status"
        if keep is None:
            keep, rule = min(members), "lexicographic_fallback"

        # Preference order inside the component: the survivor, then the members that trade
        # latest. Winners are resolved PER SESSION through transitive qualified links: on a
        # session where A~B and B~C are both in force, A, B and C are one security and only
        # the highest-ranked stays, even if A and C never qualified as a direct pair. A
        # session the survivor has no bar for keeps exactly one copy under the best-ranked
        # member that does, so a staggered rename chain never loses history.
        marks = ",".join("?" * len(members))
        last_seen = dict(con.execute(
            f"SELECT symbol, max(session_date) FROM identity_snapshot WHERE symbol IN ({marks}) GROUP BY 1",
            members).fetchall())
        ranked = [keep] + sorted((m for m in members if m != keep),
                                 key=lambda m: (-(last_seen[m].toordinal() if last_seen.get(m) else 0), m))
        rank_of = {m: i for i, m in enumerate(ranked)}
        dup_sessions = con.execute(
            f"SELECT sym_a, sym_b, session_date FROM qualified_dup WHERE sym_a IN ({marks}) AND sym_b IN ({marks})",
            members + members).fetchall()
        pair_span, identical_rows = {}, set()
        for sym_a, sym_b, day in dup_sessions:
            first, last_day = pair_span.get((sym_a, sym_b), (day, day))
            pair_span[(sym_a, sym_b)] = (min(first, day), max(last_day, day))
            identical_rows.update({(sym_a, day), (sym_b, day)})
        span_first = min(v[0] for v in pair_span.values())
        span_last = max(v[1] for v in pair_span.values())
        present = defaultdict(set)
        for symbol, day in con.execute(
                f"SELECT symbol, session_date FROM identity_snapshot WHERE symbol IN ({marks}) "
                "AND session_date BETWEEN ? AND ?", members + [span_first, span_last]).fetchall():
            present[day].add(symbol)

        entries, protected = {}, set()
        for drop in ranked[1:]:
            mine = [(k, v) for k, v in pair_span.items() if drop in k]
            first_shared = min(v[0] for _, v in mine)
            last_shared = max(v[1] for _, v in mine)
            identical = len({day for symbol, day in identical_rows
                             if symbol == drop and first_shared <= day <= last_shared})
            span_rows = rows_in_span(drop, first_shared, last_shared)
            ratio = identical / span_rows if span_rows else 0.0
            entry = {"kept": keep, "dropped": drop, "rule": rule, "identical_sessions": identical,
                     "first": str(first_shared), "last": str(last_shared),
                     "span_coverage": round(ratio, 6), "rows_in_span": span_rows,
                     "component_size": len(members),
                     "identity_unresolved": rule == "lexicographic_fallback"}
            if ratio < DUPLICATE_SERIES_MIN_SPAN_COVERAGE:
                entry["stage"] = "component"
                entry["reason"] = ("shared sessions do not cover this symbol's history inside the span; "
                                   "left untouched")
                partial.append(entry)
                protected.add(drop)
                continue
            entries[drop] = entry

        doomed = defaultdict(list)
        for day, symbols in present.items():
            linked = {m: {m} for m in symbols}
            for (sym_a, sym_b), (first, last_day) in pair_span.items():
                if sym_a in linked and sym_b in linked and first <= day <= last_day:
                    merged = linked[sym_a] | linked[sym_b]
                    for member in merged:
                        linked[member] = merged
            for group in {frozenset(v) for v in linked.values() if len(v) > 1}:
                winner = min(group, key=lambda m: rank_of[m])
                for member in group:
                    if member != winner and member not in protected:
                        doomed[member].append(day)

        for drop, entry in entries.items():
            days = doomed.get(drop, [])
            if days:
                con.execute("CREATE OR REPLACE TEMP TABLE doomed_days (session_date DATE)")
                con.executemany("INSERT INTO doomed_days VALUES (?)", [(d,) for d in days])
                con.execute("DELETE FROM joined WHERE symbol = ? AND session_date IN "
                            "(SELECT session_date FROM doomed_days)", [drop])
            entry["rows_removed"] = len(days)
            # Zero-volume halts and all-series-only rows are never byte-identical; count them
            # among the rows ACTUALLY removed, not across the whole component span.
            entry["residue_rows_removed"] = sum(1 for d in days if (drop, d) not in identical_rows)
            entry["rows_retained_without_survivor_row"] = max(0, entry["rows_in_span"] - len(days))
            if entry["identity_unresolved"]:
                unresolved += 1
            report.append(entry)

    rules = defaultdict(int)
    for item in report:
        rules[item["rule"]] += 1
    out = {"min_identical_sessions": DUPLICATE_SERIES_MIN_SESSIONS,
           "min_span_coverage": DUPLICATE_SERIES_MIN_SPAN_COVERAGE,
           "candidate_pairs": len(candidates), "qualified_pairs": len(qualified),
           "components": len(components),
           "pairs": len(report),
           "rows_removed": sum(item.get("rows_removed") or 0 for item in report),
           "residue_rows_removed": sum(item.get("residue_rows_removed") or 0 for item in report),
           "identity_unresolved_pairs": unresolved,
           "partial_overlap_not_deduped": partial,
           "by_rule": dict(rules), "detail": report}
    out.update(rename_stats or {})
    return out


def materialize(dataset_dir, corporate_actions_dir=None, asset_files=()):
    """Build daily.parquet. Returns (ok, detail-dict)."""
    out_path = os.path.join(dataset_dir, "daily.parquet")
    if os.path.exists(out_path):
        return False, {"reason": "daily.parquet already exists; remove it before rematerializing"}
    rename_stats = {}
    rename_pairs = load_rename_pairs(corporate_actions_dir, rename_stats)
    if corporate_actions_dir:
        ca_ok, ca_reasons = check_corporate_actions_complete(corporate_actions_dir)
        if not ca_ok:
            return False, {"reason": "corporate-actions ledger incomplete; its rename records would be "
                                     "used as identity evidence", "corporate_actions_reasons": ca_reasons}
        if not rename_pairs:
            return False, {"reason": "--corporate-actions was given but no rename pair could be loaded from its "
                                     "retained pages; identity de-duplication would silently fall back to price "
                                     "continuity and a lexicographic coin-flip",
                           "rename_evidence": rename_stats}
    con = duckdb.connect()
    load_bars_view(con, dataset_dir, "raw", "raw_bars", "raw")
    load_bars_view(con, dataset_dir, "all", "all_bars", "all")
    dup_raw = detect_duplicate_rows(con, "raw_bars")
    dup_all = detect_duplicate_rows(con, "all_bars")
    if dup_raw or dup_all:
        return False, {"reason": "duplicate (symbol, session_date) rows detected",
                        "raw_duplicates": len(dup_raw), "all_duplicates": len(dup_all),
                        "raw_examples": dup_raw[:20], "all_examples": dup_all[:20]}
    con.execute("""
        CREATE TABLE joined AS
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
    """)
    rows_before = con.execute("SELECT count(*) FROM joined").fetchone()[0]
    active = set()
    for path in asset_files:
        active |= {a["symbol"] for a in read_json(path) if a.get("status") == "active"}
    dedup = dedupe_identity(con, rename_pairs, frozenset(active), rename_stats)
    con.execute(f"COPY (SELECT * FROM joined ORDER BY symbol, session_date) "
                f"TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]
    with open(os.path.join(dataset_dir, "identity-dedup.json"), "w", encoding="utf-8") as handle:
        json.dump(dedup, handle, indent=1)
    summary = {k: v for k, v in dedup.items() if k not in ("detail", "partial_overlap_not_deduped")}
    summary["partial_overlap_not_deduped"] = len(dedup["partial_overlap_not_deduped"])
    return True, {"rows": rows, "rows_before_identity_dedup": rows_before, "path": out_path,
                  "identity_dedup": summary}


def cmd_materialize(args):
    plan = read_plan(args.dataset)
    events = read_ledger_events(args.dataset)
    ok, reasons = check_ledger_complete(plan, events, read_supplement_plan(args.dataset))
    if not ok:
        print("REFUSED: ledger incomplete", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 1
    ok, detail = materialize(args.dataset, args.corporate_actions, args.assets or ())
    if not ok:
        print(f"REFUSED: {detail['reason']}", file=sys.stderr)
        print(json.dumps(detail, indent=1, default=str), file=sys.stderr)
        return 1
    print(json.dumps(detail, indent=1))
    return 0


# --------------------------------------------------------------------------- build: collection


def _batch_label(event):
    """The page-event batch label a batch event belongs to. Page events carry the label
    ('b00007', bisect children 'b00007a'); batch events carry the numeric index."""
    label = event.get("label")
    if label:
        return label
    batch = event.get("batch")
    if isinstance(batch, int):
        return f"{event.get('series', 'b')}{batch:05d}"
    return str(batch)


def partition_attempts(page_events, batch_events=()):
    """Split retained page events into the attempt that produced each batch_complete and
    the earlier attempts it superseded.

    A batch that failed part way and was re-run leaves both attempts in the append-only
    ledger. Those earlier pages are retained evidence, not a pagination violation, and
    their bars must not be counted twice. Events predating run ids form one legacy group
    and, when no batch_complete information is available, every group is checked as
    before."""
    groups = defaultdict(list)
    for event in page_events:
        groups[(event["adjustment"], event["batch"], event.get("run_id"))].append(event)
    # Ledger order is append order, so the last batch_complete per batch is the attempt
    # whose CSV is on disk; an earlier COMPLETED attempt is superseded just like a failed one.
    completing = {}
    for event in batch_events:
        if event.get("event") == "batch_complete":
            completing[(event["adjustment"], _batch_label(event))] = {event.get("run_id")}
    checked, superseded = {}, {}
    for key, items in groups.items():
        adjustment, label, run_id = key
        runs = {run for (adj, prefix), values in completing.items() if adj == adjustment
                and (label == prefix or label.startswith(prefix)) for run in values}
        if runs and run_id not in runs:
            superseded[key] = items
        else:
            checked[key] = items
    return checked, superseded


def pagination_proof(page_events, batch_events=()):
    """Group page ledger events by (adjustment, batch label, run id); every checked
    group's pages must be contiguous from 0 and only the last may have
    next_page_token_present false. Attempts superseded by a later, completing attempt are
    reported as such instead of counted as violations."""
    checked, superseded = partition_attempts(page_events, batch_events)
    violations = []
    for key, items in checked.items():
        items = sorted(items, key=lambda e: e["page"])
        pages = [item["page"] for item in items]
        contiguous = pages == list(range(len(items)))
        terminal_ok = bool(items) and not items[-1]["next_page_token_present"] and \
            all(item["next_page_token_present"] for item in items[:-1])
        if not (contiguous and terminal_ok):
            violations.append({"adjustment": key[0], "batch": key[1], "run_id": key[2], "pages": pages,
                                "next_page_token_present": [i["next_page_token_present"] for i in items]})
    return {"symbol_groups_checked": len(checked), "violations": violations,
            "superseded_attempts": [{"adjustment": k[0], "batch": k[1], "run_id": k[2],
                                     "pages": sorted(i["page"] for i in v)}
                                    for k, v in sorted(superseded.items(), key=lambda kv: str(kv[0]))]}


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

    # Page and bar totals come from the attempt that actually produced each
    # batch_complete; earlier attempts are retained evidence, reported separately.
    checked_pages, superseded_pages = partition_attempts(pages, batch_complete)
    effective_pages = [event for items in checked_pages.values() for event in items]
    per_adjustment_pages = defaultdict(lambda: {"pages": 0, "bytes": 0, "bars": 0, "superseded_pages": 0})
    for event in effective_pages:
        entry = per_adjustment_pages[event["adjustment"]]
        entry["pages"] += 1
        entry["bytes"] += event["bytes"]
        entry["bars"] += event["bars"]
    for items in superseded_pages.values():
        for event in items:
            per_adjustment_pages[event["adjustment"]]["superseded_pages"] += 1

    # One batch may hold several batch_complete records across attempts; the last one wins,
    # so a retried batch is never double-counted against the single CSV it wrote.
    latest_complete = {}
    for event in batch_complete:
        latest_complete[(event.get("series", "b"), event["adjustment"], event["batch"])] = event
    per_adjustment_batches = defaultdict(lambda: {"complete": 0, "failed": 0, "bars": 0, "superseded": 0})
    for event in latest_complete.values():
        entry = per_adjustment_batches[event["adjustment"]]
        entry["complete"] += 1
        entry["bars"] += event["bars"]
    for event in batch_complete:
        if latest_complete.get((event.get("series", "b"), event["adjustment"], event["batch"])) is not event:
            per_adjustment_batches[event["adjustment"]]["superseded"] += 1
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
        "pagination_proof": pagination_proof(pages, batch_complete),
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


def build_universe_section(con, identities, sessions, supplement_symbols=frozenset()):
    """Denominators are reported on one stated basis. `daily` holds the main asset-master
    list AND the supplement, so a reader is told which count is which, and the
    survivorship histogram names both classes of known-delisted ticker."""
    supplement_symbols = set(supplement_symbols) - set(identities)
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
    supplement_last_year_hist = Counter()
    session_index = {d: i for i, d in enumerate(sessions)}
    end_idx = len(sessions) - 1
    stale_active = []
    for symbol, fst, lst in first_last:
        if symbol in inactive_symbols:
            inactive_last_year_hist[lst.year] += 1
        if symbol in supplement_symbols:
            supplement_last_year_hist[lst.year] += 1
        if symbol in active_symbols and lst in session_index and (end_idx - session_index[lst]) > 5:
            stale_active.append({"symbol": symbol, "last_session": str(lst), "sessions_before_end": end_idx - session_index[lst]})
    combined_last_year_hist = Counter(inactive_last_year_hist)
    combined_last_year_hist.update(supplement_last_year_hist)

    return {
        "requested_symbols": len(identities),
        "denominator_basis": "requested_symbols counts the main asset-master list only; the bar counts and "
                             "histograms below are computed over daily.parquet, which also holds the "
                             "supplement series. Use the *_combined counts to compare the two.",
        "requested_symbols_main_list": len(identities),
        "requested_symbols_supplement": len(supplement_symbols),
        "requested_symbols_combined": len(set(identities) | supplement_symbols),
        "symbols_with_raw_bar": con.execute("SELECT count(DISTINCT symbol) FROM daily WHERE in_raw").fetchone()[0],
        "symbols_with_all_bar": con.execute("SELECT count(DISTINCT symbol) FROM daily WHERE in_all").fetchone()[0],
        "zero_bar_symbols": len(zero_bar),
        "zero_bar_symbols_by_status_exchange": dict(zero_bar_by_status_exchange),
        "first_session_year_histogram": {str(y): c for y, c in sorted(first_hist.items())},
        "last_session_year_histogram": {str(y): c for y, c in sorted(last_hist.items())},
        "symbols_with_bars_per_year": {str(y): c for y, c in sorted(per_year_symbols.items())},
        "inactive_last_bar_year_histogram": {str(y): c for y, c in sorted(inactive_last_year_hist.items())},
        "supplement_last_bar_year_histogram": {str(y): c for y, c in sorted(supplement_last_year_hist.items())},
        "known_inactive_or_supplement_last_bar_year_histogram":
            {str(y): c for y, c in sorted(combined_last_year_hist.items())},
        "survivorship_measure_basis": "known_inactive_or_supplement_last_bar_year_histogram is the survivorship "
                                      "measure: asset-master inactive names plus the supplement names the asset "
                                      "master omits entirely (the class the supplement exists to recover).",
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


def build_supplement_section(con, dataset_dir, supplement_plan, identities):
    """Symbols the asset-master list omitted but corporate actions referenced."""
    if not supplement_plan:
        return {"present": False}
    requested = read_json(os.path.join(dataset_dir, "supplement-symbols.json"))
    rows = con.execute("""
        SELECT symbol, min(session_date), max(session_date), count(*) FROM daily
        WHERE in_raw OR in_all GROUP BY symbol
    """).fetchall()
    in_supplement = set(requested) - set(identities)
    last_hist, bars = Counter(), 0
    with_bars = 0
    for symbol, _first, last, count in rows:
        if symbol in in_supplement:
            with_bars += 1
            bars += count
            last_hist[last.year] += 1
    return {"present": True, "source": "symbols referenced by retained corporate-action pages, minus renamed-away "
                                       "old tickers whose history is served under the successor",
            "requested_symbols": len(in_supplement), "symbols_with_bars": with_bars,
            "rows_after_identity_dedup": bars,
            "last_bar_year_histogram": {str(y): c for y, c in sorted(last_hist.items())},
            "plan": {k: supplement_plan.get(k) for k in ("created_at", "start", "end", "feed", "batches", "symbols_sha256")},
            "meaning": "The provider asset list under-enumerates delisted names (TWTR is served by the bars API but "
                       "absent from /v2/assets?status=inactive). Corporate-action coverage is thin before 2020, so "
                       "names delisted in 2016-2019 without a retained action remain undiscoverable."}


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

    supplement_plan = read_supplement_plan(args.dataset)
    supplement_path = os.path.join(args.dataset, "supplement-symbols.json")
    supplement_symbols = set()
    if supplement_plan and os.path.exists(supplement_path):
        supplement_symbols = set(read_json(supplement_path)) - set(identities)

    if args.corporate_actions:
        ca_ok, ca_reasons = check_corporate_actions_complete(args.corporate_actions)
        if not ca_ok:
            print("REFUSED: corporate-actions ledger incomplete", file=sys.stderr)
            for reason in ca_reasons:
                print(f"  - {reason}", file=sys.stderr)
            return 1

    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE VIEW daily AS SELECT * FROM read_parquet('{os.path.join(args.dataset, 'daily.parquet')}')")

    calendar_section, sessions = build_calendar_section(con, compute_gap_by_symbol(con))
    gap_by_symbol = compute_gap_by_symbol(con)
    manifest = {
        "schema": "broad-universe-coverage-manifest/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collection": build_collection_section(con, args.dataset, plan, events, args.page_sample),
        "universe": build_universe_section(con, identities, sessions, supplement_symbols),
        "calendar": calendar_section,
        "quality_flags": build_quality_section(con),
        "identity": build_identity_section(identities_doc, plan, probe_doc, reproduced),
        "identity_dedup": (read_json(os.path.join(args.dataset, "identity-dedup.json"))
                           if os.path.exists(os.path.join(args.dataset, "identity-dedup.json")) else None),
        "supplement": build_supplement_section(con, args.dataset, supplement_plan, identities),
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
    p_materialize.add_argument("--corporate-actions", default=None,
                               help="retained corporate-action directory; rename records decide duplicate series")
    p_materialize.add_argument("--assets", nargs="*", default=None, help="asset-master JSON files (active status tie-break)")
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
