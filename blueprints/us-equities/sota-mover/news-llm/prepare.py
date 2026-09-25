#!/usr/bin/env python3
"""Build the preregistered news event list (no prices after the trade decision are read).

Reads the Alpaca/Benzinga news archive, the XNYS session calendar, the asset-master
snapshot and daily bars of sessions *before* each trade session, and writes:

  <out>/events.jsonl.gz      one line per selected event (the scoring input)
  <out>/prepare-receipt.json funnel counts, timestamp diagnostics, input hashes

Only membership, coverage, timestamp and liquidity-filter facts are computed. No
return, price change after a decision, or anything derived from one is computed here.

Runs in a Python with duckdb (the adaptive-paper runtime); the rules themselves live
in news_signal.py and are shared with every other script.
"""
import argparse
import bisect
import gzip
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from array import array
from collections import Counter, defaultdict, deque
from datetime import date, datetime, timezone


_HERE = os.path.dirname(os.path.abspath(__file__))


def load_news_signal():
    spec = importlib.util.spec_from_file_location("news_signal", os.path.join(_HERE, "news_signal.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["news_signal"] = module
    spec.loader.exec_module(module)
    return module


sig = load_news_signal()

REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
CALENDAR = os.path.join(REPO, "blueprints/us-equities/mover-v3/data/session-calendar.json")
NEWS_ROOT = os.path.expanduser("~/.local/state/native-agent-stack/research/data-lake/news")
ASSET_FILES = [
    os.path.expanduser("~/codex-ecosystem/state/broad-market-20260921/entitlement-probe-assets-active.json"),
    os.path.expanduser("~/codex-ecosystem/state/broad-market-20260921/entitlement-probe-assets-inactive.json"),
]
DAILY = os.path.expanduser("~/codex-ecosystem/state/broad-market-20260921/dataset/daily.parquet")
PRIVATE_ROOT = os.path.expanduser("~/.local/state/native-agent-stack/research/sota-mover/news-llm")

STUDY_FIRST_SESSION = date(2016, 1, 4)
STUDY_LAST_SESSION = date(2026, 9, 18)


class DeterministicGzipText:
    """Text writer for a .gz whose bytes depend only on the content (mtime 0, no name)."""

    def __init__(self, path):
        self._raw = open(path, "wb")  # noqa: SIM115 - closed in __exit__
        self._text = io.TextIOWrapper(gzip.GzipFile(filename="", mode="wb", fileobj=self._raw, mtime=0), encoding="utf-8")

    def __enter__(self):
        return self._text

    def __exit__(self, *exc):
        self._text.close()  # flushes and closes the GzipFile (writes the trailer)
        self._raw.close()
        return False


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def load_assets(paths):
    """symbol -> asset. Active beats inactive; two assets of equal status are ambiguous."""
    by_symbol = defaultdict(list)
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        items = payload if isinstance(payload, list) else next(v for v in payload.values() if isinstance(v, list))
        for asset in items:
            by_symbol[asset["symbol"].upper()].append(asset)
    resolved, ambiguous = {}, set()
    for symbol, assets in by_symbol.items():
        active = [a for a in assets if a.get("status") == "active"]
        pool = active or assets
        if len(pool) == 1:
            resolved[symbol] = pool[0]
        else:
            ambiguous.add(symbol)
    return resolved, ambiguous


def iter_news_files(root):
    for year in sorted(d for d in os.listdir(root) if d.isdigit()):
        for month in sorted(os.listdir(os.path.join(root, year))):
            for name in sorted(os.listdir(os.path.join(root, year, month))):
                if name.endswith(".jsonl.gz"):
                    yield os.path.join(root, year, month, name), f"{year}-{month}-{name[:2]}"


def quantiles(values, qs=(0.5, 0.9, 0.95, 0.99, 0.999)):
    if not values:
        return {}
    ordered = sorted(values)
    n = len(ordered)
    return {f"p{round(q * 100, 1)}": ordered[min(n - 1, int(q * n))] for q in qs}


def scan_news(calendar, assets, ambiguous, args):
    funnel = Counter()
    by_window = Counter()
    guard = Counter()
    gaps = array("d")
    gap_counts = Counter()
    id_times = array("q")
    ids = array("q")
    file_date_mismatch = 0
    seen_ids = set()
    tracker = sig.DuplicateTracker()
    candidates = []
    by_year_single = Counter()
    by_year_missing = Counter()
    last_prune_day = None
    for path, file_day in iter_news_files(args.news_root):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        parsed = []
        for row in rows:
            funnel["articles"] += 1
            try:
                created = sig.as_utc(row["created_at"])
            except (KeyError, ValueError, TypeError):
                funnel["drop_bad_created_at"] += 1
                continue
            nid = str(row.get("id", ""))
            if nid in seen_ids:
                funnel["drop_repeated_id"] += 1
                continue
            seen_ids.add(nid)
            if created.date().isoformat() != file_day:
                file_date_mismatch += 1
            parsed.append((created, int(nid) if nid.isdigit() else 0, nid, row))
        parsed.sort(key=lambda r: (r[0], r[1]))
        for created, nid_int, nid, row in parsed:
            if nid_int:
                ids.append(nid_int)
                id_times.append(int(created.timestamp()))
            symbols = sig.parse_symbols(row.get("symbols"))
            norm = sig.normalize_headline(row.get("headline"))
            if symbols is None:
                funnel["drop_unparseable_symbols"] += 1
                continue
            duplicate = False
            if len(symbols) == 1:
                duplicate = tracker.seen_recently(symbols[0], created, norm)
            tracker.record(symbols, created, norm)
            day = created.date()
            if day != last_prune_day:
                tracker.prune_all(created)
                last_prune_day = day
            if len(symbols) != 1:
                funnel["drop_symbol_count_not_1" if symbols else "drop_no_symbols"] += 1
                continue
            funnel["single_symbol"] += 1
            symbol = symbols[0]
            ny_year = created.astimezone(sig.NY).year
            by_year_single[ny_year] += 1
            updated = None
            try:
                updated = sig.as_utc(row["updated_at"]) if row.get("updated_at") else None
            except ValueError:
                updated = None
            if updated is not None:
                gap = (updated - created).total_seconds()
                gaps.append(gap)
                gap_counts["negative" if gap < 0 else "zero" if gap == 0 else "le_60s" if gap <= 60
                           else "le_15min" if gap <= 900 else "le_1h" if gap <= 3600 else "le_1d" if gap <= 86400 else "gt_1d"] += 1
            if symbol in ambiguous:
                funnel["drop_symbol_ambiguous_in_asset_master"] += 1
                continue
            asset = assets.get(symbol)
            if asset is None:
                funnel["drop_symbol_not_in_asset_master"] += 1
                by_year_missing[ny_year] += 1
                continue
            if not sig.is_primary_operating_company(symbol, asset.get("name"), asset.get("exchange")):
                funnel["drop_not_primary_operating_company"] += 1
                continue
            window = calendar.classify(created)
            by_window[window.kind] += 1
            if window.kind not in (sig.OVERNIGHT, sig.RTH):
                funnel[f"drop_window_{window.kind}"] += 1
                continue
            if not (STUDY_FIRST_SESSION <= window.session <= STUDY_LAST_SESSION):
                funnel["drop_session_outside_study"] += 1
                continue
            ok, reason = sig.timestamp_guard(window, updated)
            guard[f"{window.kind}:{reason}"] += 1
            if not ok:
                funnel[f"drop_guard_{reason}"] += 1
                continue
            headline = sig.clean_headline(row.get("headline"))
            if not headline:
                funnel["drop_empty_headline"] += 1
                continue
            if sig.is_movement_headline(headline):
                funnel["drop_movement_headline"] += 1
                continue
            if duplicate:
                funnel["drop_duplicate_24h"] += 1
                continue
            try:
                ckpt = sig.checkpoint_year(created)
            except ValueError:
                funnel["drop_headline_year_before_2016"] += 1
                continue
            funnel["pre_eligibility_candidates"] += 1
            candidates.append({
                "news_id": nid,
                "symbol": symbol,
                "company": sig.clean_company_name(asset.get("name")),
                "asset_name": asset.get("name"),
                "exchange": asset.get("exchange"),
                "headline": headline,
                "created_at": created.isoformat().replace("+00:00", "Z"),
                "updated_at": updated.isoformat().replace("+00:00", "Z") if updated else None,
                "window": window.kind,
                "sub": window.sub,
                "session": window.session.isoformat(),
                "entry_utc": window.entry_utc.isoformat().replace("+00:00", "Z"),
                "exit_utc": window.exit_utc.isoformat().replace("+00:00", "Z"),
                "decision_cutoff_utc": window.decision_cutoff_utc.isoformat().replace("+00:00", "Z"),
                "checkpoint_year": ckpt,
                "_window": window,
                "_created_ts": int(created.timestamp()),
            })
    ingestion, lag_counts = estimate_ingestion(ids, id_times)
    diagnostics = {
        "updated_minus_created_seconds": {
            "n": len(gaps),
            "buckets": dict(gap_counts),
            "quantiles": quantiles(list(gaps)),
        },
        "estimated_ingestion_minus_created": {"n_with_numeric_id": len(ids), "rule": "max(created, p90 of 100 lower ids)",
                                              "buckets": dict(lag_counts)},
        "file_day_differs_from_created_at_utc_date": file_date_mismatch,
        "windows_after_instrument_filter": dict(by_window),
        "guard": dict(guard),
        "survivorship_single_symbol_not_in_asset_master_by_ny_year": {
            str(y): {"single_symbol": by_year_single[y], "not_in_asset_master": by_year_missing[y],
                     "share": round(by_year_missing[y] / by_year_single[y], 4) if by_year_single[y] else None}
            for y in sorted(by_year_single)
        },
    }
    kept = []
    for c in candidates:
        window = c.pop("_window")
        created_ts = c.pop("_created_ts")
        nid = int(c["news_id"]) if c["news_id"].isdigit() else None
        est = ingestion.get(nid, created_ts)
        ok, reason = sig.ingestion_guard(window, est)
        if not ok:
            funnel[f"drop_guard_{reason}"] += 1
            funnel["pre_eligibility_candidates"] -= 1
            continue
        kept.append(c)
    return kept, funnel, diagnostics


def estimate_ingestion(ids, id_times):
    """Guard B input: news id -> estimated ingestion time (epoch s), only where it exceeds
    created_at (news_signal.estimated_ingestion over the 100 next-lower ids)."""
    order = sorted(range(len(ids)), key=lambda i: ids[i])
    window_sorted, recent = [], deque()
    out = {}
    lags = Counter()
    for i in order:
        t = id_times[i]
        if window_sorted:
            est = sig.estimated_ingestion(window_sorted, t)
            if est > t:
                out[ids[i]] = est
                lag = est - t
                lags["gt_1d" if lag > 86400 else "1h_1d" if lag > 3600 else "1min_1h" if lag > 60 else "le_1min"] += 1
        bisect.insort(window_sorted, t)
        recent.append(t)
        if len(recent) > sig.INGESTION_PREDECESSORS:
            old = recent.popleft()
            del window_sorted[bisect.bisect_left(window_sorted, old)]
    return out, lags


# Bars of the pair symbols on XNYS sessions (daily rows on non-calendar dates are ignored).
DAILY_SQL = """
CREATE TABLE d AS
SELECT b.symbol, c.si, b.raw_c, b.raw_c * b.raw_v AS dv, b.all_l, b.all_c
FROM read_parquet(?) b JOIN cal c ON c.session = b.session_date
WHERE b.in_raw AND b.raw_c IS NOT NULL AND b.raw_v IS NOT NULL
  AND b.symbol IN (SELECT DISTINCT symbol FROM pairs)
"""

# For trade session index i the statistics come from the bar of session i-1 and its 19
# predecessors; `span = 19` proves those 20 bars sit on 20 consecutive XNYS sessions.
ELIGIBILITY_SQL = """
WITH w AS (
  SELECT symbol, si, raw_c, all_l,
         median(dv) OVER (PARTITION BY symbol ORDER BY si ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS med20,
         si - lag(si, 19) OVER (PARTITION BY symbol ORDER BY si) AS span,
         lag(all_c) OVER (PARTITION BY symbol ORDER BY si) AS prev_all_c,
         si - lag(si) OVER (PARTITION BY symbol ORDER BY si) AS gap1
  FROM d
)
SELECT p.symbol, p.session, w.raw_c AS prior_close, w.med20, coalesce(w.span = 19, false) AS complete,
       w.all_l AS prior_low_adj, CASE WHEN w.gap1 = 1 THEN w.prev_all_c END AS prior2_close_adj
FROM pairs p LEFT JOIN w ON w.symbol = p.symbol AND w.si = p.si - 1
"""


def eligibility(candidates, calendar, args):
    import duckdb  # noqa: PLC0415 - only the data runtime has it

    tmp = os.path.join(args.out, "duckdb-tmp")
    os.makedirs(tmp, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{args.memory_limit}'")
    con.execute(f"SET threads={args.threads}")
    con.execute(f"SET temp_directory='{tmp}'")
    con.execute("CREATE TABLE cal (session DATE, si INTEGER)")
    con.executemany("INSERT INTO cal VALUES (?, ?)", [(s.session, i) for i, s in enumerate(calendar.sessions)])
    pairs = sorted({(c["symbol"], c["session"]) for c in candidates})
    con.execute("CREATE TABLE pairs (symbol VARCHAR, session DATE, si INTEGER)")
    con.executemany(
        "INSERT INTO pairs VALUES (?, ?, ?)",
        [(sym, s, calendar.index_of(date.fromisoformat(s))) for sym, s in pairs],
    )
    con.execute(DAILY_SQL, [args.daily])
    in_daily = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM d").fetchall()}
    rows = con.execute(ELIGIBILITY_SQL).fetchall()
    stats = {}
    for symbol, session, prior_close, med20, complete, low_adj, prior2_adj in rows:
        stats[(symbol, session.isoformat())] = (prior_close, med20, bool(complete), symbol in in_daily, low_adj, prior2_adj)
    con.close()
    return stats


def git_provenance():
    """HEAD and whether the study directory is clean; events must come from committed code."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=_HERE, capture_output=True, text=True)
    head = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--", ".")
    return {"head": head.stdout.strip() if head.returncode == 0 else None,
            "study_dir_clean": status.returncode == 0 and not status.stdout.strip()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--news-root", default=NEWS_ROOT)
    parser.add_argument("--daily", default=DAILY)
    parser.add_argument("--out", default=PRIVATE_ROOT)
    parser.add_argument("--memory-limit", default="2.5GB")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--allow-dirty", action="store_true", help="tests only: build from uncommitted code")
    args = parser.parse_args(argv)
    provenance = git_provenance()
    if not provenance["study_dir_clean"] and not args.allow_dirty:
        raise SystemExit("refusing: the study directory has uncommitted changes; events must be built from committed code")
    os.makedirs(args.out, exist_ok=True)
    started = datetime.now(timezone.utc)
    with open(CALENDAR, encoding="utf-8") as handle:
        calendar = sig.Calendar.from_calendar_json(json.load(handle))
    assets, ambiguous = load_assets(ASSET_FILES)
    candidates, funnel, diagnostics = scan_news(calendar, assets, ambiguous, args)
    stats = eligibility(candidates, calendar, args)
    eligible = []
    lane_counts = Counter()
    for c in candidates:
        prior_close, med20, complete, in_daily, low_adj, prior2_adj = stats.get(
            (c["symbol"], c["session"]), (None, None, False, False, None, None))
        if not in_daily:
            funnel["drop_symbol_not_in_daily_dataset"] += 1
            continue
        lane = sig.lane_for(prior_close, med20, complete)
        if lane is None:
            funnel["drop_not_eligible_lane"] += 1
            continue
        if c["window"] == sig.RTH and lane != sig.LIQUID:
            funnel["drop_rth_not_liquid"] += 1
            continue
        c["lane"] = lane
        c["prior_close"] = prior_close
        c["prior_median_dollar_volume_20"] = med20
        c["ssr_carryover"] = sig.ssr_carryover(low_adj, prior2_adj)
        eligible.append(c)
        lane_counts[f"{c['window']}:{lane}"] += 1
    funnel["eligible_before_first_per_window"] = len(eligible)
    selected = sig.first_per_window(eligible)
    funnel["drop_not_first_in_window"] = len(eligible) - len(selected)
    funnel["selected_events"] = len(selected)
    per_year = Counter()
    per_ckpt = Counter()
    selected_lanes = Counter()
    sessions = defaultdict(set)
    events_path = os.path.join(args.out, "events.jsonl.gz")
    with DeterministicGzipText(events_path + ".tmp") as out:
        for ev in selected:
            ev["event_id"] = f"{ev['news_id']}:{ev['symbol']}"
            out.write(json.dumps(ev, sort_keys=True) + "\n")
            key = f"{ev['window']}:{ev['lane']}"
            per_year[f"{ev['session'][:4]}:{key}"] += 1
            per_ckpt[ev["checkpoint_year"]] += 1
            selected_lanes[key] += 1
            sessions[key].add(ev["session"])
    os.replace(events_path + ".tmp", events_path)  # readers never see a partial file
    receipt = {
        "schema": "sota-news-llm-prepare/1",
        "evidence_label": "HIST",
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": provenance,
        "inputs": {
            "news_manifest_sha256": sha256_file(os.path.join(args.news_root, "manifest.jsonl")),
            "news_run_header_sha256": sha256_file(os.path.join(args.news_root, "run-header.json")),
            "calendar_sha256": sha256_file(CALENDAR),
            "asset_files_sha256": {os.path.basename(p): sha256_file(p) for p in ASSET_FILES},
            "daily_parquet_sha256": sha256_file(args.daily),
            "news_signal_py_sha256": sha256_file(os.path.join(_HERE, "news_signal.py")),
            "prepare_py_sha256": sha256_file(os.path.abspath(__file__)),
        },
        "asset_master": {"symbols_resolved": len(assets), "symbols_ambiguous": len(ambiguous)},
        "funnel": dict(funnel),
        "eligible_by_window_lane": dict(lane_counts),
        "selected_by_window_lane": dict(selected_lanes),
        "selected_sessions_by_window_lane": {k: len(v) for k, v in sessions.items()},
        "selected_by_session_year": dict(sorted(per_year.items())),
        "selected_by_checkpoint": {str(k): v for k, v in sorted(per_ckpt.items())},
        "diagnostics": diagnostics,
        "events_file": {"path": "events.jsonl.gz", "sha256": sha256_file(events_path), "rows": len(selected)},
        "no_outcome_statement": "No price after any decision time was read; only daily bars of sessions before each trade session (liquidity lanes, Rule 201 carry-over) were used.",
    }
    with open(os.path.join(args.out, "prepare-receipt.json"), "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=1, sort_keys=True)
    print(json.dumps({"selected": len(selected), "funnel": dict(funnel)}, sort_keys=True))


if __name__ == "__main__":
    main()
