"""Gap 5 check: run promotion_gate.py on duckdb:// inputs built from the
retained CSV fixtures and compare each result with the retained CSV gate
result (status, row_count and every named check's status).

Two loaders are exercised so a type-dependent difference cannot hide:
  pandas  - pandas.read_csv(fixture) registered and copied into DuckDB, so the
            gate sees the same column dtypes it sees for the CSV path;
  native  - DuckDB's own read_csv (auto-detected DATE/TIMESTAMP/BIGINT types).

Run with the gate venv's interpreter (it must import duckdb and pandas):
  python duckdb_gate_check.py --repo <repo> --work <empty dir> --out <json>

Exits 0 only when every case matches on both loaders; any DIFF exits 1.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

FIXTURES = ["good", "bad", "null-price-cell", "empty-snapshot", "fractional-negative-volume"]


def build(db_path: Path, csv_path: Path, loader: str) -> None:
    import duckdb
    import pandas as pd

    con = duckdb.connect(str(db_path))
    try:
        if loader == "pandas":
            frame = pd.read_csv(csv_path)
            con.register("frame_view", frame)
            con.execute("CREATE TABLE snapshot AS SELECT * FROM frame_view")
        else:
            con.execute("CREATE TABLE snapshot AS SELECT * FROM read_csv(?)", [str(csv_path)])
    finally:
        con.close()


def column_types(db_path: Path) -> dict:
    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='snapshot' ORDER BY ordinal_position"
        ).fetchall()
    finally:
        con.close()
    return {name: dtype for name, dtype in rows}


def summary(result: dict) -> dict:
    return {
        "status": result.get("status"),
        "row_count": result.get("row_count"),
        "checks": {c["name"]: c["status"] for c in result.get("checks", [])},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    repo = Path(args.repo)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=False)
    gate = repo / "blueprints/us-equities/data/promotion_gate.py"
    fixtures = repo / "blueprints/us-equities/data/fixtures"
    report = {"python": sys.version.split()[0], "cases": []}
    for loader in ("pandas", "native"):
        for name in FIXTURES:
            db = work / f"{name}-{loader}.duckdb"
            build(db, fixtures / f"{name}.csv", loader)
            out = work / f"{name}-{loader}-gate-result.json"
            proc = subprocess.run(
                [sys.executable, str(gate), "--input", f"duckdb://{db}#snapshot", "--out", str(out)],
                capture_output=True, text=True, timeout=120)
            got = json.loads(out.read_text())
            expected = json.loads((fixtures / f"{name}-gate-result.json").read_text())
            g, e = summary(got), summary(expected)
            diffs = {k: {"duckdb": g["checks"].get(k), "csv": e["checks"].get(k)}
                     for k in sorted(set(g["checks"]) | set(e["checks"]))
                     if g["checks"].get(k) != e["checks"].get(k)}
            report["cases"].append({
                "fixture": name, "loader": loader, "gate_exit": proc.returncode,
                "column_types": column_types(db),
                "duckdb": g, "csv_retained": e,
                "status_match": g["status"] == e["status"],
                "row_count_match": g["row_count"] == e["row_count"],
                "check_status_diffs": diffs,
                "match": g["status"] == e["status"] and g["row_count"] == e["row_count"] and not diffs,
                "failure_details": {c["name"]: c.get("detail") for c in got.get("checks", []) if c["status"] == "fail"},
            })
    report["all_pandas_match"] = all(c["match"] for c in report["cases"] if c["loader"] == "pandas")
    report["all_native_match"] = all(c["match"] for c in report["cases"] if c["loader"] == "native")
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("all_pandas_match", "all_native_match")}))
    for c in report["cases"]:
        print(c["loader"], c["fixture"], "match" if c["match"] else f"DIFF {c['check_status_diffs']} status {c['duckdb']['status']}/{c['csv_retained']['status']}")
    # Exit nonzero unless every case matched, so a DIFF cannot pass as success
    # (Codex review of PR #132; changed 2026-09-23, after the recorded runs).
    return 0 if report["all_pandas_match"] and report["all_native_match"] else 1


if __name__ == "__main__":
    sys.exit(main())
