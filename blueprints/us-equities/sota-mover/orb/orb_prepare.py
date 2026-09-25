"""Pre-outcome data work for the ORB replication: opening ranges, 14-day features, selection, trigger times.

Runs on real data before the freeze. It reads bars up to 09:35 ET for features and, for the selected
names only, finds the first minute the stop order would trigger (a signal-firing timestamp). It never
reads or writes a fill price, stop, exit, return or any price after the trigger (protocol.json
freeze_discipline). Needs duckdb (the adaptive-paper tools Python).

  python orb_prepare.py or-table            # opening-range table from the minute corpus (bounded run)
  python orb_prepare.py membership        # point-in-time top-500 liquidity membership per session (D1)
  python orb_prepare.py candidates          # 14-day ATR / volume / RelVol per member symbol-day (pure Python)
  python orb_prepare.py select              # top-20 per session, directions, dojis, thin-session counts
  python orb_prepare.py triggers            # first trigger minute of each selected order (no prices kept)
  python orb_prepare.py verify-or --n 300   # re-derive a sample of opening ranges from raw bars with orb_signal.py
  python orb_prepare.py receipt             # counts and sha256 of every private artifact
"""
from __future__ import annotations

import os as _os
import sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)

import argparse
import csv
import gzip
import hashlib
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

import orb_common as C  # noqa: E402
import orb_signal as S  # noqa: E402

BARS_GLOB = str(C.MINUTE_ROOT / "bars/symbol=*/year=*/full.parquet")


def connect():
    import duckdb
    tmp = C.private_dir("tmp")
    con = duckdb.connect()
    con.execute(f"SET memory_limit='2.5GB'; SET threads=4; SET temp_directory='{tmp}'; "
                "SET preserve_insertion_order=false")
    return con


def protocol():
    return C.load_json(C.PROTOCOL_PATH)


TOP_LIQUID = 500  # the same N as universe A's construction
EXCLUDED_SUFFIX = r"\.(WS|W|U|R|RT)$"  # the stage-1 plan's warrant/unit/right exclusion


def membership():
    """({session: set(in-corpus members)}, union) from the point-in-time membership (D1, fix 1)."""
    plan = C.load_json(C.MINUTE_PLAN)
    con = connect()
    by_day = defaultdict(set)
    for d, sym in con.execute(f"SELECT d, symbol FROM '{C.PRIVATE / 'membership.parquet'}' WHERE in_corpus").fetchall():
        by_day[d].add(sym)
    return by_day, plan["universe_a"]["union"]


def cmd_membership(a) -> int:
    """Point-in-time top-500 liquidity membership for each session t, from sessions strictly before t.

    Mirrors the stage-1 universe-A construction (minute-plan selection_sql) but ranks each session on its
    own: med20 = median raw dollar volume over the 20 sessions t-20..t-1 (the window excludes t),
    20 and 60 calendar-contiguous prior sessions with bars, raw close of t-1 >= $5, med20 >= $20M, no
    warrant/unit/right suffix; the 500 highest med20 (ties by symbol). From session t it reads only the
    existence of its daily bar (the symbol trades that day), never a price or volume of t."""
    proto = protocol()
    start, end = proto["segments"]["reproduction"]["dates"][0], proto["segments"]["post_publication"]["dates"][1]
    union = C.load_json(C.MINUTE_PLAN)["universe_a"]["union"]
    con = connect()
    con.execute("CREATE TEMP TABLE u(symbol VARCHAR)")
    con.executemany("INSERT INTO u VALUES (?)", [(s,) for s in union])
    out = C.private_dir() / "membership.parquet"
    con.execute(f"""
    COPY (
      WITH cal AS (
        SELECT session_date, row_number() OVER (ORDER BY session_date) AS si
        FROM (SELECT DISTINCT session_date FROM read_parquet('{C.DAILY_PARQUET}') WHERE symbol = 'SPY' AND in_raw)
      ),
      d AS (
        SELECT b.symbol, b.session_date, c.si, b.raw_c, b.raw_c * b.raw_v AS dv
        FROM read_parquet('{C.DAILY_PARQUET}') b JOIN cal c USING (session_date)
        WHERE b.in_raw AND b.raw_c IS NOT NULL AND b.raw_v IS NOT NULL AND b.session_date <= DATE '{end}'
          AND NOT regexp_matches(b.symbol, '{EXCLUDED_SUFFIX}')
      ),
      w AS (
        SELECT symbol, session_date, si,
               median(dv) OVER (PARTITION BY symbol ORDER BY si ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS med20,
               lag(raw_c) OVER (PARTITION BY symbol ORDER BY si) AS prev_c,
               si - lag(si, 20) OVER (PARTITION BY symbol ORDER BY si) AS d_lookback,
               si - lag(si, 60) OVER (PARTITION BY symbol ORDER BY si) AS d_history
        FROM d
      ),
      e AS (
        SELECT symbol, CAST(session_date AS VARCHAR) AS d, med20,
               row_number() OVER (PARTITION BY session_date ORDER BY med20 DESC, symbol) AS rank
        FROM w
        WHERE d_lookback = 20 AND d_history = 60 AND prev_c >= 5.0 AND med20 >= 20000000.0
          AND session_date BETWEEN DATE '{start}' AND DATE '{end}'
      )
      SELECT e.d, e.symbol, e.rank, e.med20, e.symbol IN (SELECT symbol FROM u) AS in_corpus
      FROM e WHERE rank <= {TOP_LIQUID} ORDER BY d, rank
    ) TO '{out}' (FORMAT parquet, COMPRESSION zstd)""")
    res = {"top_n": TOP_LIQUID, "segments": {}, "years": {}}
    for name, (lo, hi) in ((k, v["dates"]) for k, v in proto["segments"].items()):
        r = con.execute(f"""SELECT count(DISTINCT d), count(*), count(*) FILTER (WHERE in_corpus),
            count(*) FILTER (WHERE NOT in_corpus), count(DISTINCT symbol) FILTER (WHERE NOT in_corpus),
            min(n), max(n) FROM (SELECT *, count(*) OVER (PARTITION BY d) AS n FROM '{out}')
            WHERE d BETWEEN '{lo}' AND '{hi}'""").fetchone()
        res["segments"][name] = dict(zip(("sessions", "member_days", "in_corpus_days", "missing_days",
                                          "missing_symbols", "min_members_per_session", "max_members_per_session"), r))
    for y, n, inc, miss, msym in con.execute(f"""SELECT substr(d, 1, 4), count(*), count(*) FILTER (WHERE in_corpus),
            count(*) FILTER (WHERE NOT in_corpus), count(DISTINCT symbol) FILTER (WHERE NOT in_corpus)
            FROM '{out}' GROUP BY 1 ORDER BY 1""").fetchall():
        res["years"][y] = {"member_days": n, "in_corpus_days": inc, "missing_days": miss, "missing_symbols": msym}
    res["sha256"] = C.sha256_file(out)
    print(json.dumps(res, sort_keys=True))
    C.write_private_json(C.PRIVATE / "membership.counts.json", res)
    return 0


# ------------------------------------------------------------------ or-table

def cmd_or_table(a) -> int:
    out = C.private_dir() / "or5.parquet"
    con = connect()
    con.execute(f"""
    COPY (
      SELECT symbol, et_date AS d,
        arg_min(o, et_minute) FILTER (WHERE et_minute BETWEEN 570 AND 574) AS or_open,
        max(h) FILTER (WHERE et_minute BETWEEN 570 AND 574) AS or_high,
        min(l) FILTER (WHERE et_minute BETWEEN 570 AND 574) AS or_low,
        arg_max(c, et_minute) FILTER (WHERE et_minute BETWEEN 570 AND 574) AS or_close,
        coalesce(sum(v) FILTER (WHERE et_minute BETWEEN 570 AND 574), 0) AS or_vol,
        count(*) FILTER (WHERE et_minute BETWEEN 570 AND 574) AS or_n,
        count(*) FILTER (WHERE et_minute BETWEEN 570 AND 959) AS rth_bars
      FROM read_parquet('{BARS_GLOB}', hive_partitioning=false)
      WHERE et_minute BETWEEN 570 AND 959
      GROUP BY 1, 2
      ORDER BY 1, 2
    ) TO '{out}' (FORMAT parquet, COMPRESSION zstd)""")
    n, syms = con.execute(f"SELECT count(*), count(DISTINCT symbol) FROM '{out}'").fetchone()
    print(json.dumps({"or5_rows": n, "symbols": syms, "sha256": C.sha256_file(out)}))
    return 0


# ------------------------------------------------------------------ candidates

CAND_COLS = ["symbol", "d", "pit_member", "or_open", "or_high", "or_low", "or_close", "or_vol", "or_n",
             "atr14", "avgvol14", "relvol", "split", "eligible", "reason"]


def cmd_candidates(a) -> int:
    proto = protocol()
    start, end = proto["segments"]["reproduction"]["dates"][0], proto["segments"]["post_publication"]["dates"][1]
    members, union = membership()
    cal = [(s, cm) for s, cm in C.calendar() if "2016-01-01" <= s <= end]
    idx = {s: i for i, (s, _) in enumerate(cal)}
    sessions = [s for s, _ in cal]
    con = connect()
    or_path = C.PRIVATE / "or5.parquet"
    con.execute("CREATE TEMP TABLE u(symbol VARCHAR)")
    con.executemany("INSERT INTO u VALUES (?)", [(s,) for s in union])
    con.execute(f"""CREATE TEMP TABLE dly AS SELECT symbol, CAST(session_date AS VARCHAR) AS d,
        raw_o, raw_c, raw_v, all_o, all_h, all_l, all_c, all_v
        FROM read_parquet('{C.DAILY_PARQUET}') WHERE symbol IN (SELECT symbol FROM u)
        AND session_date <= DATE '{end}' AND in_raw AND in_all""")
    con.execute(f"""CREATE TEMP TABLE orx AS SELECT symbol, CAST(d AS VARCHAR) AS d, or_open, or_high, or_low,
        or_close, or_vol, or_n, rth_bars FROM '{or_path}'""")
    out_path = C.private_dir() / "candidates.csv.gz"
    counts = defaultdict(int)
    # mtime=0 keeps the gzip bytes (and the recorded sha256) identical across runs
    with open(out_path, "wb") as raw_f, gzip.GzipFile(fileobj=raw_f, mode="wb", compresslevel=6, mtime=0) as gzb, \
            io.TextIOWrapper(gzb, encoding="utf-8", newline="") as gz:
        w = csv.writer(gz)
        w.writerow(CAND_COLS)
        for sym in sorted(union):
            daily = {r[0]: r[1:] for r in con.execute(
                "SELECT d, raw_o, raw_c, raw_v, all_o, all_h, all_l, all_c, all_v FROM dly WHERE symbol=?",
                [sym]).fetchall()}
            orr = {r[0]: r[1:] for r in con.execute(
                "SELECT d, or_open, or_high, or_low, or_close, or_vol, or_n, rth_bars FROM orx WHERE symbol=?",
                [sym]).fetchall()}
            for d, o in sorted(orr.items()):
                if not (start <= d <= end) or d not in idx:
                    continue
                or_open, or_high, or_low, or_close, or_vol, or_n, _ = o
                if or_n == 0:
                    continue  # no opening-range bar: not a candidate that day
                member = sym in members.get(d, ())
                counts["or_symbol_days"] += 1
                if not member:
                    counts["not_member_pit"] += 1
                    continue
                i = idx[d]
                row = [sym, d, 1, or_open, or_high, or_low, or_close, or_vol, or_n]
                atr, avgv, rv, split, reason = S.day_features(sessions, i, daily, orr, or_vol)
                if reason == "" and not S.eligible(or_open, avgv, atr):
                    reason = "filters_1_3"
                el = int(reason == "")
                counts["member_symbol_days"] += 1
                counts["eligible_1_3"] += el
                counts[f"reason:{reason or 'eligible'}"] += 1
                counts["split_adjusted_windows"] += int(split != 1.0)
                w.writerow(row + [atr, avgv, rv, split, el, reason])
    sha = C.sha256_file(out_path)
    counts = dict(counts, sha256=sha)
    print(json.dumps(counts, sort_keys=True))
    C.write_private_json(C.PRIVATE / "candidates.counts.json", counts)
    return 0


# ------------------------------------------------------------------ select

def read_candidates():
    with gzip.open(C.PRIVATE / "candidates.csv.gz", "rt", newline="") as f:
        r = csv.reader(f)
        head = next(r)
        for row in r:
            yield dict(zip(head, row))


def segment_of(proto, d):
    for name, seg in proto["segments"].items():
        lo, hi = seg["dates"]
        if lo <= d <= hi:
            return name
    return None


def cmd_select(a) -> int:
    proto = protocol()
    by_day = defaultdict(list)
    for c in read_candidates():
        if c["eligible"] == "1":
            by_day[c["d"]].append(c)
    cal = [s for s, _ in C.calendar()]
    out = C.private_dir() / "selected.csv"
    stats = defaultdict(lambda: defaultdict(int))
    thin = defaultdict(list)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["d", "segment", "rank", "symbol", "relvol", "dirn", "level", "atr14", "avgvol14", "or_open",
                    "or_close"])
        for d in cal:
            seg = segment_of(proto, d)
            if seg is None:
                continue
            cands = by_day.get(d, [])
            rows = {c["symbol"]: c for c in cands}
            top = S.select_top([(c["symbol"], float(c["relvol"])) for c in cands])
            st = stats[seg]
            st["sessions"] += 1
            st["eligible_1_3"] += len(cands)
            n_rv = sum(1 for c in cands if float(c["relvol"]) >= S.MIN_RELVOL)
            st["eligible_relvol_ge_1"] += n_rv
            if n_rv < S.TOP_N:
                st["sessions_lt20_selectable"] += 1
                thin[seg].append(n_rv)
            if n_rv == 0:
                st["sessions_zero_selectable"] += 1
            for rank, (sym, rv) in enumerate(top, 1):
                c = rows[sym]
                dirn = S.direction(float(c["or_open"]), float(c["or_close"]))
                level = c["or_high"] if dirn > 0 else c["or_low"] if dirn < 0 else ""
                st["selected"] += 1
                st["long" if dirn > 0 else "short" if dirn < 0 else "doji"] += 1
                st["relvol_ge_30"] += int(rv >= 30)
                w.writerow([d, seg, rank, sym, rv, dirn, level, c["atr14"], c["avgvol14"], c["or_open"],
                            c["or_close"]])
    res = {seg: dict(v) for seg, v in stats.items()}
    for seg, xs in thin.items():
        xs.sort()
        res[seg]["selectable_on_thin_sessions_median"] = xs[len(xs) // 2]
    res["sha256"] = C.sha256_file(out)
    print(json.dumps(res, sort_keys=True))
    C.write_private_json(C.PRIVATE / "selected.counts.json", res)
    return 0


# ------------------------------------------------------------------ triggers

def read_selected():
    with open(C.PRIVATE / "selected.csv", newline="") as f:
        yield from csv.DictReader(f)


def cmd_triggers(a) -> int:
    close_of = dict(C.calendar())
    want = defaultdict(list)
    for r in read_selected():
        if r["dirn"] != "0":
            want[(r["symbol"], int(r["d"][:4]))].append(r)
    con = connect()
    out = C.private_dir() / "triggers.csv"
    counts = defaultdict(lambda: defaultdict(int))
    minutes = defaultdict(list)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["d", "segment", "symbol", "dirn", "trigger_minute"])
        for (sym, year), rows in sorted(want.items()):
            path = C.MINUTE_ROOT / f"bars/symbol={sym}/year={year}/full.parquet"
            days = sorted({r["d"] for r in rows})
            # only minutes 09:35..close-1 and only h/l: the trigger test; no open/close/volume after 09:35
            got = con.execute(f"""SELECT CAST(et_date AS VARCHAR), et_minute, h, l FROM read_parquet('{path}')
                WHERE et_minute BETWEEN 575 AND 959 AND CAST(et_date AS VARCHAR) IN ({",".join("?" * len(days))})
                ORDER BY 1, 2""", days).fetchall()
            per_day = defaultdict(list)
            for d, m, h, low in got:
                per_day[d].append((m, None, h, low, None, None))
            for r in rows:
                d, dirn, level = r["d"], int(r["dirn"]), float(r["level"])
                i = S.find_trigger(per_day.get(d, []), dirn, level, close_of[d])
                tm = per_day[d][i][0] if i is not None else ""
                seg = r["segment"]
                counts[seg]["orders"] += 1
                if tm == "":
                    counts[seg]["not_fired"] += 1
                else:
                    counts[seg]["fired"] += 1
                    counts[seg]["fired_long" if dirn > 0 else "fired_short"] += 1
                    minutes[seg].append(tm)
                w.writerow([d, seg, sym, dirn, tm])
    res = {}
    for seg, c in counts.items():
        c = dict(c)
        ms = sorted(minutes[seg])
        if ms:
            c["trigger_minute_p10_p50_p90"] = [ms[int(q * (len(ms) - 1))] for q in (0.1, 0.5, 0.9)]
            c["fired_by_1000"] = sum(1 for m in ms if m < 600)
            c["fired_by_1030"] = sum(1 for m in ms if m < 630)
        res[seg] = c
    res["sha256"] = C.sha256_file(out)
    print(json.dumps(res, sort_keys=True))
    C.write_private_json(C.PRIVATE / "triggers.counts.json", res)
    return 0


# ------------------------------------------------------------------ verify-or

def cmd_verify_or(a) -> int:
    """Re-derive opening ranges for a sha256-keyed sample of candidate rows from raw bars with orb_signal.py."""
    rows = [c for c in read_candidates()
            if int.from_bytes(hashlib.sha256(f"{c['symbol']}|{c['d']}".encode()).digest()[:8], "big") % 5000 == 0]
    rows = rows[: a.n]
    con = connect()
    bad = 0
    for c in rows:
        path = C.MINUTE_ROOT / f"bars/symbol={c['symbol']}/year={c['d'][:4]}/full.parquet"
        bars = con.execute(f"""SELECT et_minute, o, h, l, c, v FROM read_parquet('{path}')
            WHERE CAST(et_date AS VARCHAR)=? AND et_minute BETWEEN 570 AND 574 ORDER BY 1""", [c["d"]]).fetchall()
        o = S.opening_range(bars)
        want = (float(c["or_open"]), float(c["or_high"]), float(c["or_low"]), float(c["or_close"]),
                float(c["or_vol"]), int(c["or_n"]))
        if o is None or any(abs(x - y) > 1e-9 for x, y in zip(o, want)):
            bad += 1
    res = {"checked": len(rows), "mismatched": bad}
    print(json.dumps(res))
    C.write_private_json(C.PRIVATE / "verify-or.json", res)
    return 0 if bad == 0 else 1


# ------------------------------------------------------------------ compare-membership

def cmd_compare_membership(a) -> int:
    """Selected orders under the point-in-time membership versus the superseded per-year membership."""
    def orders(path):
        with open(path, newline="") as f:
            return {(r["segment"], r["d"], r["symbol"], r["dirn"]) for r in csv.DictReader(f)}
    new, old = orders(C.PRIVATE / "selected.csv"), orders(C.PRIVATE / "v1-membership/selected.csv")
    res = {}
    for seg in ("reproduction", "post_publication"):
        n = {o for o in new if o[0] == seg}
        o = {x for x in old if x[0] == seg}
        nd, od = {x for x in n if x[3] != "0"}, {x for x in o if x[3] != "0"}
        res[seg] = {"selected_new": len(n), "selected_old": len(o), "only_new": len(n - o), "only_old": len(o - n),
                    "orders_new": len(nd), "orders_old": len(od), "orders_only_new": len(nd - od),
                    "orders_only_old": len(od - nd), "sessions_changed": len({x[1] for x in (n ^ o)})}
    print(json.dumps(res, sort_keys=True))
    C.write_private_json(C.PRIVATE / "membership-change.json", res)
    return 0


# ------------------------------------------------------------------ receipt

def cmd_receipt(a) -> int:
    files = ["or5.parquet", "candidates.csv.gz", "selected.csv", "triggers.csv", "candidates.counts.json",
             "selected.counts.json", "triggers.counts.json", "verify-or.json", "power.json", "cost-table.json",
             "quotes/sample.json", "quotes/ledger.jsonl", "membership.parquet", "membership.counts.json",
             "membership-change.json", "split-check.json", "splits/ledger.jsonl"]
    out = {"kind": "orb_pre_outcome_receipt", "label": "HIST", "outcomes_computed": False,
           "protocol_id": protocol()["id"],
           "inputs": {"minute_plan_file_sha256": C.sha256_file(C.MINUTE_PLAN),
                      "daily_parquet_sha256": C.load_json(C.MINUTE_PLAN)["universe_inputs"]["daily_parquet_sha256"],
                      "fees_sha256": C.sha256_file(C.FEES_PATH), "calendar_sha256": C.sha256_file(C.CALENDAR_PATH)},
           "artifacts_sha256": {}, "counts": {}}
    for name in files:
        p = C.PRIVATE / name
        if not p.exists():
            continue
        out["artifacts_sha256"][name] = C.sha256_file(p)
        if name == "cost-table.json":  # summary only; the measured cells stay private
            t = C.load_json(p)
            out["counts"][name] = {k: v for k, v in t.items() if k != "groups"} | {"groups": {
                g: {k: v for k, v in x.items() if k != "cells"} | {
                    "cell_sources": {s: sum(1 for c in x["cells"].values() if c["source"] == s)
                                     for s in ("cell", "time_x_price", "table_p90")}}
                for g, x in t["groups"].items()}}
        elif name == "power.json":
            t = C.load_json(p)
            out["counts"][name] = {k: t[k] for k in ("n_min_trades", "n_min_basis", "n_min_trades_sd3_rho005", "n_min_long_sd3_rho005", "alpha_one_sided_per_step",
                                                     "target_effect_R", "portfolio")} | {
                leg: {k: v for k, v in t[leg].items() if k != "table"} for leg in ("combined", "long")}
        elif name == "split-check.json":
            t = C.load_json(p)
            out["counts"][name] = {k: (len(v) if isinstance(v, list) else v) for k, v in t.items()}
        elif name == "quotes/sample.json":
            t = C.load_json(p)
            out["counts"][name] = {k: v for k, v in t.items() if k != "sample"}
        elif name.endswith(".json"):
            out["counts"][name] = C.load_json(p)
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("or-table", "membership", "candidates", "select", "triggers", "receipt", "compare-membership"):
        sub.add_parser(name)
    v = sub.add_parser("verify-or")
    v.add_argument("--n", type=int, default=300)
    a = ap.parse_args(argv)
    return {"or-table": cmd_or_table, "membership": cmd_membership, "candidates": cmd_candidates, "select": cmd_select,
            "triggers": cmd_triggers, "verify-or": cmd_verify_or, "receipt": cmd_receipt, "compare-membership": cmd_compare_membership}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
