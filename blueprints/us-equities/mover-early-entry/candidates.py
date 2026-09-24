"""Build the mover candidate superset from the broad-universe daily dataset (selection fields only).

A symbol-day is a candidate when its fully adjusted daily-bar high reached at least ``--touch``
(default 1.20) times the PREVIOUS session's fully adjusted daily-bar LOW. Both bars include
extended-hours trades. This superset is provably complete for every entry rule with a threshold of
at least +20% over the previous official close:
- the official close lies within the previous day's full-session range, so it is at least that
  day's low;
- any price at time t is at most the day's high;
- so a rule that fires has high >= price_t >= 1.20 x official prev close >= 1.20 x prev low.
Days after a gap of more than 7 calendar days (halt resumptions, relistings) are kept and flagged.
Likely warrants, units and rights (a five-letter symbol ending W/U/R, or a .WS/.U/.R/.W suffix) are
excluded and counted.

The output carries only symbol, session_date and prev_date. No outcome (close, gain, forward
return) is written, so selection cannot leak an outcome into evaluation.

  python candidates.py --daily PATH/daily.parquet --start 2021-01-01 --out candidates.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--touch", type=float, default=1.20)
    ap.add_argument("--exclude", type=Path, default=None, help="an earlier candidates CSV; write only symbol-days not in it (a collection delta)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    import duckdb
    con = duckdb.connect()
    con.execute("PRAGMA threads=8")
    con.execute(f"""CREATE TEMP TABLE d AS SELECT symbol, session_date, all_h, all_l,
        lag(all_l) OVER (PARTITION BY symbol ORDER BY session_date) AS prev_l,
        lag(session_date) OVER (PARTITION BY symbol ORDER BY session_date) AS prev_d
        FROM read_parquet('{a.daily}') WHERE in_all""")
    base = f"""FROM d WHERE prev_l > 0 AND session_date >= DATE '{a.start}' AND all_h >= {a.touch} * prev_l"""
    if a.exclude:
        con.execute(f"CREATE TEMP TABLE ex AS SELECT symbol, CAST(session_date AS DATE) AS session_date FROM read_csv_auto('{a.exclude}')")
        base += " AND NOT EXISTS (SELECT 1 FROM ex WHERE ex.symbol = d.symbol AND ex.session_date = d.session_date)"
    deriv = "((length(symbol) = 5 AND regexp_matches(symbol, '[A-Z]{4}[WUR]$')) OR regexp_matches(symbol, '\\.(WS|U|R|W)'))"
    rows = con.execute(f"SELECT symbol, session_date, prev_d {base} AND NOT {deriv} ORDER BY session_date, symbol").fetchall()
    gap_days = con.execute(f"SELECT count(*) {base} AND NOT {deriv} AND session_date - prev_d > 7").fetchone()[0]
    excluded = con.execute(f"SELECT count(*) {base} AND {deriv}").fetchone()[0]
    with a.out.open("w") as f:
        f.write("symbol,session_date,prev_date\n")
        for sym, day, prev in rows:
            f.write(f"{sym},{day.isoformat()},{prev.isoformat()}\n")
    meta = {"daily_sha256": None, "daily_bytes": a.daily.stat().st_size, "start": a.start, "touch": a.touch,
            "candidates": len(rows), "sessions": len({r[1] for r in rows}), "excluded_likely_derivatives": excluded,
            "days_after_gap_over_7": gap_days, "exclude": str(a.exclude.name) if a.exclude else None,
            "candidates_sha256": hashlib.sha256(a.out.read_bytes()).hexdigest()}
    Path(str(a.out) + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
