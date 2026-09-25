"""Trade outcomes for the ORB replication under fill models F0/F1/F2 (protocol.json). Post-freeze only.

  python simulate.py run --protocol-sha256 SHA [--population selected|base]

``selected`` simulates the top-20 orders (the items and the Table 2 analogue); ``base`` simulates every
filter-1-3 name under F0 (the Fig. 4 and Table 1 descriptive analogues). The command refuses unless
protocol.json is frozen and hashes to --protocol-sha256 (orb_common.require_frozen), because it reads prices
after the decision time. The per-trade logic is signal.simulate_trade, the function the synthetic tests
cover. Needs duckdb for reading the private minute corpus.
"""
from __future__ import annotations

# signal.py in this directory shadows the stdlib module by name: cache the stdlib one before this
# directory goes on sys.path, and load ours only by path (orb_common.load_signal).
import os as _os
import sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _sys.path and _os.path.abspath(_sys.path[0] or _os.curdir) == _HERE:
    _sys.path.pop(0)
import signal as _stdlib_signal  # noqa: E402,F401
_sys.path.insert(0, _HERE)

import argparse
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import orb_common as C  # noqa: E402
import collect_quotes as Q  # noqa: E402

S = C.load_signal()
MODELS = ("F0", "F1", "F2")
TRADE_COLS = ["d", "segment", "symbol", "dirn", "rank", "relvol", "atr14", "slots", "model", "entry_minute",
              "entry_base", "entry_fill", "stop", "gap_entry", "exit_minute", "exit_base", "exit_fill",
              "exit_reason", "gross_R", "net_R", "ssr_flag"]


def cost_function(table: dict, segment: str, liq_tier: int, close_minute: int):
    """half_spread(minute, price) for one symbol-day: the cell of the execution's time bucket (the bar's end,
    as the quote stamps), its base price tier and the symbol-day's liquidity tier."""
    cells = table["groups"][segment]["cells"]

    def hs(minute, price):
        tb = Q.time_bucket(minute + 1, close_minute)
        if tb is None:
            tb = 0 if minute + 1 < Q.TIME_BUCKETS[0][0] else len(Q.TIME_BUCKETS) - 1
        return cells[f"{tb}|{Q.tier(price, Q.PRICE_TIERS)}|{liq_tier}"]["half_spread"]
    return hs


def trade_record(model, fees, d, dirn, level, atr, bars, close_minute, hs):
    """One simulated trade as a flat dict, or None when the order never triggers."""
    t = S.simulate_trade(bars, dirn, level, atr, close_minute, model, hs)
    if t is None:
        return None
    r_ps = S.r_per_share(atr)
    gross = dirn * (t["exit_base"] - t["entry_base"]) / r_ps
    net = S.net_r(model, fees, d, dirn, t["entry_fill"], t["exit_fill"], atr, shares=1.0)
    return dict(t, gross_R=gross, net_R=net)


def ssr_flag(dirn, prev_low_adj, prev_prev_close_adj, prev_close_raw, split, bars, trigger_minute):
    """Rule 201 plausibly active for a short: the prior session fell 10% below its previous close, or a
    regular-hours bar before the trigger traded 10% below the prior close. Longs: 0."""
    if dirn >= 0:
        return 0
    if prev_low_adj is not None and prev_prev_close_adj and prev_low_adj <= 0.9 * prev_prev_close_adj:
        return 1
    ref = prev_close_raw / split if prev_close_raw else None
    if ref and any(b[3] <= 0.9 * ref for b in bars if b[0] < trigger_minute):
        return 1
    return 0


def load_orders(population: str):
    """[(d, segment, symbol, dirn, rank, relvol, level, atr, liq_tier, slots, split)] for the population."""
    import orb_prepare as P
    proto = C.load_json(C.PROTOCOL_PATH)
    split_of, eligible_by_day = {}, defaultdict(list)
    for c in P.read_candidates():
        if c["eligible"] == "1":
            split_of[(c["d"], c["symbol"])] = float(c["split"])
            eligible_by_day[c["d"]].append(c)
    out = []
    if population == "selected":
        for r in P.read_selected():
            if r["dirn"] == "0":
                continue
            adv = float(r["avgvol14"]) * float(r["or_open"])
            out.append((r["d"], r["segment"], r["symbol"], int(r["dirn"]), int(r["rank"]), float(r["relvol"]),
                        float(r["level"]), float(r["atr14"]), Q.tier(adv, Q.LIQ_TIERS), S.TOP_N,
                        split_of[(r["d"], r["symbol"])]))
    else:
        for d, cands in eligible_by_day.items():
            seg = P.segment_of(proto, d)
            if seg is None:
                continue
            for c in cands:
                dirn = S.direction(float(c["or_open"]), float(c["or_close"]))
                if dirn == 0:
                    continue
                adv = float(c["avgvol14"]) * float(c["or_open"])
                out.append((d, seg, c["symbol"], dirn, 0, float(c["relvol"]),
                            float(c["or_high"] if dirn > 0 else c["or_low"]), float(c["atr14"]),
                            Q.tier(adv, Q.LIQ_TIERS), len(cands), float(c["split"])))
    return out


def cmd_run(a) -> int:
    C.verify_pins(C.require_frozen(C.PROTOCOL_PATH, a.protocol_sha256))
    import orb_prepare as P
    fees = C.load_json(C.FEES_PATH)
    table = C.load_json(C.PRIVATE / "cost-table.json")
    close_of = dict(C.calendar())
    sessions = [s for s, _ in C.calendar()]
    prev_of = {s: (sessions[i - 1], sessions[i - 2]) for i, s in enumerate(sessions) if i >= 2}
    orders = load_orders(a.population)
    models = MODELS if a.population == "selected" else ("F0",)
    by_file = defaultdict(list)
    for o in orders:
        by_file[(o[2], int(o[0][:4]))].append(o)
    con = P.connect()
    daily = {}
    if a.population == "selected":
        con.execute("CREATE TEMP TABLE u(symbol VARCHAR)")
        con.executemany("INSERT INTO u VALUES (?)", [(s,) for s in sorted({o[2] for o in orders})])
        for sym, d, al, ac, rc in con.execute(f"""SELECT symbol, CAST(session_date AS VARCHAR), all_l, all_c, raw_c
                FROM read_parquet('{C.DAILY_PARQUET}') WHERE symbol IN (SELECT symbol FROM u)""").fetchall():
            daily[(sym, d)] = (al, ac, rc)
    out = C.PRIVATE / f"trades-{a.population}.csv.gz"
    n = defaultdict(int)
    with open(out, "wb") as raw_f, gzip.GzipFile(fileobj=raw_f, mode="wb", compresslevel=6, mtime=0) as gzb:
        import io
        txt = io.TextIOWrapper(gzb, encoding="utf-8", newline="")
        w = csv.writer(txt)
        w.writerow(TRADE_COLS)
        for (sym, year), rows in sorted(by_file.items()):
            path = C.MINUTE_ROOT / f"bars/symbol={sym}/year={year}/full.parquet"
            days = sorted({r[0] for r in rows})
            got = con.execute(f"""SELECT CAST(et_date AS VARCHAR), et_minute, o, h, l, c, v FROM read_parquet('{path}')
                WHERE et_minute BETWEEN 570 AND 959 AND CAST(et_date AS VARCHAR) IN ({",".join("?" * len(days))})
                ORDER BY 1, 2""", days).fetchall()
            per_day = defaultdict(list)
            for d, m, o, h, low, c, v in got:
                per_day[d].append((m, o, h, low, c, v))
            for (d, seg, _, dirn, rank, rv, level, atr, liq, slots, split) in rows:
                bars = per_day.get(d, [])
                cm = close_of[d]
                hs = cost_function(table, seg, liq, cm)
                ssr = ""
                for model in models:
                    t = trade_record(model, fees, d, dirn, level, atr, bars, cm, hs)
                    if t is None:
                        n["not_fired"] += 1
                        break
                    if ssr == "" and a.population == "selected":
                        p1, p2 = prev_of[d]
                        dp1, dp2 = daily.get((sym, p1)), daily.get((sym, p2))
                        ssr = ssr_flag(dirn, dp1[0] if dp1 else None, dp2[1] if dp2 else None,
                                       dp1[2] if dp1 else None, split, bars, t["entry_minute"])
                    n[f"trades:{model}"] += 1
                    w.writerow([d, seg, sym, dirn, rank, rv, atr, slots, model, t["entry_minute"], t["entry_base"],
                                t["entry_fill"], t["stop"], int(t["gap_entry"]), t["exit_minute"], t["exit_base"],
                                t["exit_fill"], t["exit_reason"], t["gross_R"], t["net_R"], ssr])
        txt.flush()
        txt.detach()
    res = dict(n, sha256=C.sha256_file(out))
    print(json.dumps(res, sort_keys=True))
    C.write_private_json(C.PRIVATE / f"trades-{a.population}.counts.json", res)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--protocol-sha256", default=None)
    r.add_argument("--population", choices=("selected", "base"), default="selected")
    a = ap.parse_args(argv)
    return {"run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
