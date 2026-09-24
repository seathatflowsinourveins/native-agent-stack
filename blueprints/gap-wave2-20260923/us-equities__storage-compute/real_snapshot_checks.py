#!/usr/bin/env python3
"""Gap 0 / gap 4 helper: run the pinned promotion gate, immutable Parquet and
DuckDB bars queries over real daily-bar snapshots, and write a price-free
summary.

Inputs are read-only: the #84 Alpaca SIP snapshots (copied into a private run
directory first) and LEAN's bundled AlgoSeek daily zips. No row, price or
price-derived value is written to the summary; only counts, dates, hashes and
gate check statuses.

Usage: real_snapshot_checks.py --run-dir DIR --gate-python PY --gate FILE
       --snapshot NAME=CSV:RECEIPT [...] --lean-daily DIR --out SUMMARY.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb

LEAN_FIVE = ("aapl", "spy", "ibm", "bac", "aig")
# LEAN commit 985ef30 committer date; used as the local observation stamp for
# bundled data whose original availability time is unknown.
LEAN_OBSERVED_AT = "2026-09-18T14:03:24+00:00"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_gate(py: str, gate: str, inp: Path, out: Path) -> dict:
    proc = subprocess.run([py, gate, "--input", str(inp), "--out", str(out), "--calendar", "XNYS"],
                          capture_output=True, text=True, timeout=600)
    res = json.loads(out.read_text())
    return {"exit": proc.returncode, "status": res["status"], "row_count": res["row_count"],
            "input_sha256": res["input_sha256"], "input_sha256_matches_file": res["input_sha256"] == sha256(inp),
            "failed_checks": [c["name"] for c in res["checks"] if c["status"] != "pass"],
            "checks_total": len(res["checks"]), "versions": res["versions"],
            "gate_result_file": out.name, "gate_result_sha256": sha256(out)}


def lean_rows(daily: Path, tickers, last_n=None):
    rows = []
    for t in tickers:
        with zipfile.ZipFile(daily / f"{t}.zip") as z:
            text = z.read(f"{t}.csv").decode()
        recs = [r for r in csv.reader(io.StringIO(text)) if r]
        if last_n:
            recs = recs[-last_n:]
        for r in recs:
            d = r[0].split()[0]
            px = [f"{int(v) / 10000:.4f}" for v in r[1:5]]
            rows.append([t.upper(), f"{d[:4]}-{d[4:6]}-{d[6:]}", *px, str(int(r[5])), LEAN_OBSERVED_AT])
    return rows


def write_csv(path: Path, rows):
    with open(path, "x", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["symbol", "session", "open", "high", "low", "close", "volume", "observed_at"])
        w.writerows(rows)


def parquet_and_duckdb(csv_path: Path, parquet: Path) -> dict:
    con = duckdb.connect()
    # Exact decimal text -> DECIMAL(18,4); volume BIGINT; immutable output.
    src = (f"read_csv('{csv_path}', header=true, columns={{'symbol':'VARCHAR','session':'DATE',"
           "'open':'DECIMAL(18,4)','high':'DECIMAL(18,4)','low':'DECIMAL(18,4)','close':'DECIMAL(18,4)',"
           "'volume':'BIGINT','observed_at':'TIMESTAMPTZ'})")
    if parquet.exists():
        raise FileExistsError(parquet)
    con.execute(f"COPY (SELECT * FROM {src} ORDER BY symbol, session) TO '{parquet}' "
                "(FORMAT parquet, COMPRESSION zstd)")
    os.chmod(parquet, 0o444)
    writable = os.access(parquet, os.W_OK)
    txt = (f"read_csv('{csv_path}', header=true, all_varchar=true)")
    # Precision check: exact decimal text vs the DECIMAL(18,4) value written to Parquet.
    precision_loss = con.execute(
        f"SELECT count(*) FROM {txt} WHERE " + " OR ".join(
            f"CAST({c} AS DECIMAL(38,12)) <> CAST(CAST({c} AS DECIMAL(18,4)) AS DECIMAL(38,12))"
            for c in ("open", "high", "low", "close"))).fetchone()[0]
    max_scale = con.execute(
        f"SELECT max(greatest(" + ", ".join(
            f"CASE WHEN strpos({c}, '.') > 0 THEN length({c}) - strpos({c}, '.') ELSE 0 END" for c in ("open", "high", "low", "close"))
        + f")) FROM {txt}").fetchone()[0]
    probe = con.execute("SELECT CAST('1.23456' AS DECIMAL(38,12)) <> CAST(CAST('1.23456' AS DECIMAL(18,4)) AS DECIMAL(38,12))").fetchone()[0]
    diff_a = con.execute(f"SELECT count(*) FROM (SELECT * FROM {src} EXCEPT ALL SELECT * FROM read_parquet('{parquet}'))").fetchone()[0]
    diff_b = con.execute(f"SELECT count(*) FROM (SELECT * FROM read_parquet('{parquet}') EXCEPT ALL SELECT * FROM {src})").fetchone()[0]
    p = f"read_parquet('{parquet}')"
    q = {}
    q["rows"], q["symbols"], q["first_session"], q["last_session"] = con.execute(
        f"SELECT count(*), count(DISTINCT symbol), min(session)::VARCHAR, max(session)::VARCHAR FROM {p}").fetchone()
    per = con.execute(f"SELECT symbol, count(*) n, min(session)::VARCHAR, max(session)::VARCHAR FROM {p} GROUP BY 1 ORDER BY 1").fetchall()
    q["sessions_per_symbol_min"] = min(r[1] for r in per)
    q["sessions_per_symbol_max"] = max(r[1] for r in per)
    q["symbols_with_full_range"] = sum(1 for r in per if r[2] == q["first_session"] and r[3] == q["last_session"])
    q["null_cells"] = con.execute(f"SELECT count(*) FROM {p} WHERE symbol IS NULL OR session IS NULL OR open IS NULL "
                                  "OR high IS NULL OR low IS NULL OR close IS NULL OR volume IS NULL").fetchone()[0]
    q["ohlc_inconsistent_rows"] = con.execute(f"SELECT count(*) FROM {p} WHERE high < greatest(open, close) "
                                              "OR low > least(open, close) OR low <= 0").fetchone()[0]
    # Per-symbol close-to-close return aggregate: computed, then only hashed.
    agg = con.execute(f"SELECT symbol, count(r), round(sum(r), 10) FROM (SELECT symbol, close / lag(close) OVER "
                      f"(PARTITION BY symbol ORDER BY session) - 1 AS r FROM {p}) WHERE r IS NOT NULL GROUP BY 1 ORDER BY 1").fetchall()
    q["return_aggregate_rows"] = len(agg)
    q["return_aggregate_sha256"] = hashlib.sha256(json.dumps([[a, b, str(c)] for a, b, c in agg]).encode()).hexdigest()
    return {"duckdb": duckdb.__version__, "parquet_sha256": sha256(parquet), "parquet_bytes": parquet.stat().st_size,
            "parquet_mode": oct(parquet.stat().st_mode & 0o777), "parquet_writable_after_chmod": writable,
            "precision_loss_rows": precision_loss, "max_price_decimal_places_in_text": max_scale,
            "precision_probe_1_23456_detected": probe,
            "csv_minus_parquet_rows": diff_a, "parquet_minus_csv_rows": diff_b, "queries": q}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--gate-python", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--snapshot", action="append", default=[])
    ap.add_argument("--lean-daily", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run = Path(a.run_dir)
    run.mkdir(mode=0o700, parents=True, exist_ok=False)
    summary = {"started_at": datetime.now(timezone.utc).isoformat(), "alpaca_snapshots": {}, "lean": {}}
    for spec in a.snapshot:
        name, rest = spec.split("=", 1)
        src, receipt = rest.split(":", 1)
        rec = json.loads(Path(receipt).read_text())
        dst = run / f"{name}.csv"
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o444)
        # The ingest receipt holds counts, dates and hashes only; it is retained whole.
        entry = {"receipt": rec, "receipt_sha256": sha256(Path(receipt)),
                 "copy_sha256": sha256(dst)}
        entry["copy_matches_receipt"] = entry["copy_sha256"] == rec["snapshot_sha256"]
        entry["gate"] = run_gate(a.gate_python, a.gate, dst, run / f"{name}-gate-result.json")
        entry["parquet_duckdb"] = parquet_and_duckdb(dst, run / f"{name}.parquet")
        # Detection control: one row's high below its close, one duplicated (symbol, session).
        rows = list(csv.reader(open(dst)))
        hdr, body = rows[0], rows[1:]
        mut = [list(r) for r in body]
        mut[0][3] = f"{float(mut[0][5]) - 0.01:.2f}"
        mut.append(list(body[1]))
        ctl = run / f"{name}-control.csv"
        with open(ctl, "x", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(hdr)
            w.writerows(mut)
        entry["detection_control"] = {"mutations": ["row 1 high set to close - 0.01", "row 2 duplicated"],
                                      "gate": run_gate(a.gate_python, a.gate, ctl, run / f"{name}-control-gate-result.json")}
        summary["alpaca_snapshots"][name] = entry
    daily = Path(a.lean_daily)
    arms = {"lean-five-252": (LEAN_FIVE, 252),
            "lean-all-full": (sorted(p.stem for p in daily.glob("*.zip") if p.stat().st_size > 1024), None)}
    for name, (tickers, last_n) in arms.items():
        path = run / f"{name}.csv"
        write_csv(path, lean_rows(daily, tickers, last_n))
        summary["lean"][name] = {"tickers": [t.upper() for t in tickers], "last_n_sessions": last_n,
                                 "csv_sha256": sha256(path),
                                 "gate": run_gate(a.gate_python, a.gate, path, run / f"{name}-gate-result.json"),
                                 "parquet_duckdb": parquet_and_duckdb(path, run / f"{name}.parquet")}
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    Path(a.out).write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps({k: (v["gate"]["status"], v["gate"]["failed_checks"]) for k, v in summary["lean"].items()}))
    for k, v in summary["alpaca_snapshots"].items():
        print(k, v["copy_matches_receipt"], v["gate"]["status"], v["gate"]["failed_checks"],
              "control:", v["detection_control"]["gate"]["status"], v["detection_control"]["gate"]["failed_checks"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
