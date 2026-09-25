#!/usr/bin/env python3
"""Evaluate the frozen EAP protocol (EAP-1..EAP-4 with Holm) on the daily dataset.

  python evaluate.py --protocol-sha256 SHA --root ROOT --daily DAILY.parquet [--out RESULT.json]

Refuses (exit 2) before reading any price unless protocol.json has status
'frozen_pre_outcome', frozen_before_outcomes true and a sha256 equal to --protocol-sha256.
The pure core (month_rows -> series -> item tests) is exercised by synthetic fixtures; the
DuckDB loaders below are the only code that reads adjusted closes.
"""
from __future__ import annotations

import os
import sys

# signal.py in this directory would shadow the standard-library module.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / "protocol.json"
FROZEN_STATUS = "frozen_pre_outcome"


class Refusal(SystemExit):
    def __init__(self, reason: str):
        super().__init__(2)
        self.reason = reason


def guard(protocol_path: Path, expected_sha256: str | None) -> dict:
    """Return the parsed protocol only when it is frozen and its bytes match the given sha256."""
    raw = protocol_path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    p = json.loads(raw)
    if not expected_sha256 or expected_sha256.strip().lower() != actual:
        raise Refusal(f"protocol sha256 mismatch: expected {expected_sha256!r}, file has {actual}")
    if p.get("status") != FROZEN_STATUS or p.get("frozen_before_outcomes") is not True or not p.get("frozen_at"):
        raise Refusal(f"protocol is not frozen (status={p.get('status')!r}, frozen_before_outcomes={p.get('frozen_before_outcomes')!r})")
    return p


def _load(name: str):
    key = f"eap_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


S = _load("signal")
E = _load("expected_dates")
P = S.PROTOCOL
MIN = {"long": 10, "short": 10, "tercile_pool": 30}
MIN_MONTHS = P["statistics"]["minimum_samples"]["min_valid_months"]
ALPHA = P["statistics"]["multiplicity"]["family_alpha"]
LAGS = P["statistics"]["nw_lags"]


# ---------------------------------------------------------------- pure core

def month_series(rows: dict[str, dict]) -> dict:
    """Portfolio returns of one month. rows: symbol -> {lane, eligible, expected, weight, ret, proxy}."""
    long, short = S.split_portfolios(rows)
    out = {"n_long": len(long), "n_short": len(short)}
    L, Sh = S.vw_return(long), S.vw_return(short)
    M = S.vw_return({**long, **short})
    out.update(L=L, S=Sh, M=M)
    out["eap1"] = L - Sh if len(long) >= MIN["long"] and len(short) >= MIN["short"] else None
    out["eap2"] = L - M if len(long) >= MIN["long"] else None
    prox = {s: rows[s]["proxy"] for s in long if rows[s].get("proxy") is not None}
    out["n_proxy"] = len(prox)
    if len(prox) >= MIN["tercile_pool"]:
        top = S.top_tercile(prox)
        out["eap3"] = S.vw_return({s: long[s] for s in top}) - M
        out["n_top"] = len(top)
    else:
        out["eap3"] = None
    lew, sew = S.split_portfolios(rows, equal_weight=True)
    out["ew_eap1"] = (S.vw_return(lew) - S.vw_return(sew)) if len(lew) >= MIN["long"] and len(sew) >= MIN["short"] else None
    out["ew_eap2"] = (S.vw_return(lew) - S.vw_return({**lew, **sew})) if len(lew) >= MIN["long"] else None
    ls, ss = S.split_portfolios(rows, lane_name="small")
    out["small_eap1"] = (S.vw_return(ls) - S.vw_return(ss)) if len(ls) >= MIN["long"] and len(ss) >= MIN["short"] else None
    out["small_eap2"] = (S.vw_return(ls) - S.vw_return({**ls, **ss})) if len(ls) >= MIN["long"] else None
    return out


def cost_pass(months: list[dict], fees: dict) -> list[dict]:
    """Long-leg rebalancing costs month by month (months ordered; each has t, d, rows)."""
    prev_w, prev_r = {}, {}
    last_px, last_dv, last_lane = {}, {}, {}
    out = []
    for m in months:
        rows = m["rows"]
        for s, r in rows.items():
            if r.get("price") is not None:
                last_px[s], last_dv[s], last_lane[s] = r["price"], r["dv"], r["lane"] or "small"
        long, _ = S.split_portfolios(rows)
        new = S.normalized({s: w for s, (w, _) in long.items()}) if len(long) >= MIN["long"] else {}
        old = S.drift(prev_w, prev_r) if prev_w else {}
        cost, turnover = S.rebalance_cost(old, new, last_px, last_dv, last_lane, m["d"], fees)
        out.append({"cost": cost, "turnover": turnover})
        prev_w, prev_r = new, {s: rows[s]["ret"] for s in new}
    return out


def item_test(xs: list[float], min_months: int) -> dict:
    n = len(xs)
    if n < max(3, min_months):
        return {"n_valid_months": n, "status": "inconclusive_below_minimum", "p_one_sided": 1.0}
    mean, se, t = S.nw_t(xs, LAGS)
    return {"n_valid_months": n, "mean_monthly": mean, "nw_se": se, "t": t, "p_one_sided": S.t_sf(t, n - 1), "status": "tested"}


def evaluate_core(months: list[dict], fees: dict) -> dict:
    series = [dict(t=m["t"], **month_series(m["rows"])) for m in months]
    costs = cost_pass(months, fees)
    for s, c in zip(series, costs):
        s.update(c)
        s["eap4"] = s["eap2"] - c["cost"] if s["eap2"] is not None else None
    items = {}
    for name, key in (("EAP-1", "eap1"), ("EAP-2", "eap2"), ("EAP-3", "eap3"), ("EAP-4", "eap4")):
        items[name] = item_test([s[key] for s in series if s[key] is not None], MIN_MONTHS[name])
    reject = S.holm({k: v["p_one_sided"] for k, v in items.items()}, ALPHA)
    for k in items:
        items[k]["holm_reject"] = reject[k] and items[k]["status"] == "tested"
    valid = [s for s in series if s["eap2"] is not None]
    turn = sum(s["turnover"] for s in valid)
    by_year = defaultdict(lambda: defaultdict(list))
    for s in series:
        for key in ("eap1", "eap2", "eap3", "eap4"):
            if s[key] is not None:
                by_year[s["t"][0]][key].append(s[key])
    descriptive = {
        "break_even_cost_per_unit_turnover": (sum(s["eap2"] for s in valid) / turn) if turn else None,
        "measured_cost_per_unit_turnover": (sum(s["cost"] for s in valid) / turn) if turn else None,
        "mean_monthly_turnover": turn / len(valid) if valid else None,
        "by_year_mean": {y: {k: sum(v) / len(v) for k, v in d.items()} for y, d in sorted(by_year.items())},
    }
    for key in ("ew_eap1", "ew_eap2", "small_eap1", "small_eap2"):
        xs = [s[key] for s in series if s[key] is not None]
        descriptive[key] = item_test(xs, 3) if len(xs) >= 3 else {"n_valid_months": len(xs)}
    r = {k: items[k]["holm_reject"] for k in items}
    if r["EAP-2"] and r["EAP-4"]:
        decision = "adopt_for_pre_positioning_research"
    elif r["EAP-1"] or r["EAP-2"]:
        decision = "premium_exists_not_tradable"
    else:
        decision = "no_premium"
    return {"items": items, "decision": decision, "descriptive": descriptive,
            "months": [{k: v for k, v in s.items() if k != "t"} | {"t": f"{s['t'][0]}-{s['t'][1]:02d}"} for s in series]}


# ---------------------------------------------------------------- loaders (after the guard only)

def load_adjusted(con, daily: Path, symbols: set[str]) -> None:
    con.execute("CREATE OR REPLACE TEMP TABLE eap_syms(symbol VARCHAR)")
    con.executemany("INSERT INTO eap_syms VALUES (?)", [(s,) for s in sorted(symbols | {"SPY"})])
    con.execute(f"""CREATE OR REPLACE TEMP TABLE eap_bars AS
        SELECT symbol, session_date, all_c,
               lag(all_c) OVER (PARTITION BY symbol ORDER BY session_date) AS prev_c
        FROM read_parquet('{daily}') WHERE symbol IN (SELECT symbol FROM eap_syms) AND all_c > 0""")


def holding_inputs(con, windows: list[tuple[int, date, date]]) -> dict:
    con.execute("CREATE OR REPLACE TEMP TABLE eap_win(i INTEGER, d DATE, e DATE)")
    con.executemany("INSERT INTO eap_win VALUES (?, ?, ?)", windows)
    rows = con.execute("""
        SELECT w.i, b.symbol, max(b.all_c) FILTER (WHERE b.session_date = w.d),
               max(b.session_date) FILTER (WHERE b.session_date > w.d),
               arg_max(b.all_c, b.session_date) FILTER (WHERE b.session_date > w.d)
        FROM eap_bars b JOIN eap_win w ON b.session_date BETWEEN w.d AND w.e GROUP BY 1, 2""").fetchall()
    out = defaultdict(dict)
    for i, sym, dc, ls, lc in rows:
        out[i][sym] = (dc, [(ls, lc)] if ls is not None else [])
    return out


def event_day_returns(con, keys: set[tuple[str, date]]) -> dict:
    con.execute("CREATE OR REPLACE TEMP TABLE eap_ev(symbol VARCHAR, s DATE)")
    con.executemany("INSERT INTO eap_ev VALUES (?, ?)", sorted(keys))
    rows = con.execute("""SELECT b.symbol, b.session_date, b.all_c / b.prev_c - 1 FROM eap_bars b
        JOIN eap_ev e ON b.symbol = e.symbol AND b.session_date = e.s WHERE b.prev_c > 0""").fetchall()
    return {(s, d): r for s, d, r in rows}


def closes_at(con, keys: set[tuple[str, date]]) -> dict:
    con.execute("CREATE OR REPLACE TEMP TABLE eap_ck(symbol VARCHAR, s DATE)")
    con.executemany("INSERT INTO eap_ck VALUES (?, ?)", sorted(keys))
    rows = con.execute("""SELECT b.symbol, b.session_date, b.all_c FROM eap_bars b
        JOIN eap_ck k ON b.symbol = k.symbol AND b.session_date = k.s""").fetchall()
    return {(s, d): c for s, d, c in rows}


def run(a, protocol: dict) -> dict:
    con = S.duck(a.root)
    sessions = E.load_sessions(con, a.daily)
    universe = json.loads((a.root / "universe.json").read_text())["ciks"]
    filings = E.load_filings(a.root)
    events = {c: E.announcement_events(filings.get(c, []), sessions)[0] for c in universe}
    periods = {c: E.period_filings(filings.get(c, [])) for c in universe}
    months = E.study_months(tuple(map(int, protocol["segments"]["first_month"].split("-"))),
                            tuple(map(int, protocol["segments"]["last_month"].split("-"))))
    decisions = [E.decision_session(sessions, t) for t in months]
    symbols = {s for v in universe.values() for s in v}
    lane_in = S.load_lane_inputs(con, a.daily, sessions, decisions, symbols)
    load_adjusted(con, a.daily, symbols)
    windows = [(i, d, E.month_sessions(sessions, t)[-1]) for i, (t, d) in enumerate(zip(months, decisions))]
    hold = holding_inputs(con, windows)
    status = {}
    ev_keys = set()
    for i, t in enumerate(months):
        cutoff = E.information_cutoff(sessions, t)
        for cik in universe:
            st = E.monthly_status(events[cik], t, cutoff)
            prior = [e for e in E.known(events[cik], cutoff)][-4:] if st["expected"] else []
            status[(i, cik)] = (st, prior)
            for sym in universe[cik]:
                ev_keys.update((sym, e.session) for e in prior)
    edr = event_day_returns(con, ev_keys)
    flags = Counter()
    month_inputs = []
    for i, (t, d) in enumerate(zip(months, decisions)):
        rows = {}
        for cik, syms in universe.items():
            st, prior = status[(i, cik)]
            for sym in syms:
                li = lane_in[d].get(sym)
                if li is None:
                    continue
                ln = S.lane(sym, *li)
                if ln is None:
                    continue
                dc, bars = hold[i].get(sym, (None, []))
                ret, flag = S.holding_return(dc, bars, windows[i][2])
                flags[flag] += 1
                proxy = S.extreme_proxy([edr.get((sym, e.session)) for e in prior], 3) if prior else None
                rows[sym] = {"lane": ln, "eligible": st["eligible"], "expected": st["expected"], "weight": li[1],
                             "ret": ret, "proxy": proxy, "price": li[0], "dv": li[1]}
        month_inputs.append({"t": t, "d": d, "rows": rows})
    result = evaluate_core(month_inputs, S.load_fees())
    result["descriptive"]["flags"] = dict(flags)
    result["descriptive"]["event_time"] = event_time_descriptive(con, sessions, months, decisions, universe, events, periods, lane_in)
    return result


def event_time_descriptive(con, sessions, months, decisions, universe, events, periods, lane_in) -> dict:
    et = P["expectation"]["secondary_event_time_rule"]
    trades = []
    for t, d in zip(months, decisions):
        cutoff = E.information_cutoff(sessions, t)
        last = E.month_sessions(sessions, t)[-1]
        for cik, syms in universe.items():
            if not E.monthly_status(events[cik], t, cutoff)["eligible"]:
                continue
            x = E.event_time_expectation(events[cik], periods[cik], cutoff)
            if x is None:
                continue
            tr = E.event_time_trade(events[cik], x["expected_date"], cutoff, sessions, d, last, et["k_sessions"], et["fallback_exit_days"])
            if tr is None:
                continue
            for sym in syms:
                li = lane_in[d].get(sym)
                if li and S.lane(sym, *li) == "main":
                    trades.append((sym, *tr))
    keys = {(s, x) for s, a, b in trades for x in (a, b)} | {("SPY", x) for _, a, b in trades for x in (a, b)}
    c = closes_at(con, keys)
    rets, rel = [], []
    for s, a, b in trades:
        if (s, a) in c and (s, b) in c:
            r = c[(s, b)] / c[(s, a)] - 1
            rets.append(r)
            if ("SPY", a) in c and ("SPY", b) in c:
                rel.append(r - (c[("SPY", b)] / c[("SPY", a)] - 1))
    med = lambda xs: S.median(xs) if xs else None
    return {"trades": len(trades), "with_prices": len(rets), "mean": sum(rets) / len(rets) if rets else None,
            "median": med(rets), "mean_minus_spy": sum(rel) / len(rel) if rel else None, "median_minus_spy": med(rel)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--protocol-sha256", required=True)
    p.add_argument("--protocol", type=Path, default=PROTOCOL_PATH, help=argparse.SUPPRESS)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--daily", type=Path, required=True)
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    if a.protocol.resolve() != PROTOCOL_PATH.resolve():
        print("REFUSED: evaluation runs only against this directory's protocol.json", file=sys.stderr)
        return 2
    try:
        protocol = guard(a.protocol, a.protocol_sha256)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        return 2
    result = run(a, protocol)
    result.update(protocol_sha256=a.protocol_sha256, protocol_id=protocol["id"], label="HIST")
    out = a.out or (a.root / "receipts" / "evaluation.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True, default=str))
    print(json.dumps({"items": result["items"], "decision": result["decision"]}, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
