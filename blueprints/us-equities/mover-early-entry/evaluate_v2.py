"""Evaluate protocol-v2.json (mover-followup-v2-20260924): families E, F and P; deterministic.

  python evaluate_v2.py dev_val --trades-dev F --trades-val F --cost-table evidence/cost-table-run-v1.json \
      --daily DAILY --out RESULTS.json

E and F trades come from features_v2.py; P is computed here from the daily dataset. Statistics,
costs, fees and the portfolio follow v1 (evaluate.py) with the v2 seed and clarifications V1-V14.
dev_val reads no holdout session; aggregates only.
"""
from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
from collections import defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as V1  # noqa: E402
import features_v2 as FV2  # noqa: E402
import rules as R  # noqa: E402

PROTOCOL_BYTES = (HERE / "protocol-v2.json").read_bytes()
PROTOCOL = json.loads(PROTOCOL_BYTES)
SEED = int.from_bytes(hashlib.sha256(PROTOCOL["id"].encode()).digest()[:8], "big")
Q, REF = V1.Q, V1.REF_NOTIONAL
DERIV = "((length(symbol) = 5 AND regexp_matches(symbol, '[A-Z]{4}[WUR]$')) OR regexp_matches(symbol, '\\.(WS|U|R|W)'))"
P_SCORES = ("S1_day2_runner", "S2_volume_breakout", "S3_compression_expansion", "S4_gap_and_hold")
Z_EXITS = ("Z1", "Z2", "Z3")
PASS = {"E": (200, 100, 50, 3), "F": (200, 100, 50, 3), "P": (100, 50, 30, 3)}  # dev, val, holdout trades; holdout size


class Trades:
    """Column arrays for one family's trades across its rule-exits."""

    def __init__(self, cal):
        self.cal = cal
        self.cidx = {s: i for i, s in enumerate(cal)}
        self.cols = defaultdict(list)

    def add(self, rid, day, symbol, entry, exit_px, c_in, c_out, decision_price, decision_dv, bar_dv, order_key, supplement, exit_day=None):
        c = self.cols
        c["rid"].append(rid)
        c["sess"].append(self.cidx[day])
        c["day"].append(exit_day or day)
        c["symbol"].append(symbol)
        c["entry"].append(entry)
        c["exit"].append(exit_px)
        c["cin"].append(c_in)
        c["cout"].append(c_out)
        c["price"].append(decision_price)
        c["dv"].append(decision_dv)
        c["bar_dv"].append(np.nan if bar_dv is None else bar_dv)
        c["order"].append(order_key)
        c["supplement"].append(bool(supplement))

    def finish(self):
        c = self.cols
        self.n = len(c["rid"])
        self.rid = np.array(c["rid"], dtype=object)
        self.symbol = c["symbol"]
        self.day = c["day"]
        for k in ("sess",):
            setattr(self, k, np.array(c[k], dtype=int))
        for k in ("entry", "exit", "cin", "cout", "price", "dv", "bar_dv", "order"):
            setattr(self, k, np.array(c[k], dtype=float))
        self.supplement = np.array(c["supplement"], dtype=bool)
        fees = [R.fee_rates(d) for d in self.day]
        self.sec = np.array([f[0] for f in fees]) if fees else np.zeros(0)
        self.taf = np.array([f[1] for f in fees]) if fees else np.zeros(0)
        self.capv = np.array([f[2] for f in fees]) if fees else np.zeros(0)
        self.net = {name: R.net_return_np(self.entry, self.exit, self.cin, self.cout, self.sec, self.taf, self.capv, REF, broker, mult)
                    for name, broker, mult in V1.VARIANTS} if self.n else {name: np.zeros(0) for name, _, _ in V1.VARIANTS}
        syms = {s: i for i, s in enumerate(sorted(set(self.symbol)))}
        self.sym = np.array([syms[s] for s in self.symbol], dtype=int)
        years = sorted({d[:4] for d in self.day})
        self.years = years
        self.year = np.array([years.index(d[:4]) for d in self.day], dtype=int)
        self.ptier = np.searchsorted(R.PRICE_TIERS, self.price, side="right") if self.n else np.zeros(0, dtype=int)
        self.vtier = np.searchsorted(R.DV_TIERS, self.dv, side="right") if self.n else np.zeros(0, dtype=int)
        return self


def simulate(T: Trades, idx, regime, rung, cap_leverage, start_equity=100_000.0):
    """V11/V13: 5 slots per session in decision order (entry time for E/F; dollar volume for P), notional
    from the session's starting equity, v1's caps, drawdown factor, cooldown and ruin."""
    by_s = defaultdict(list)
    for i in sorted(idx.tolist(), key=lambda i: (T.sess[i], T.order[i], T.symbol[i])):
        if len(by_s[T.sess[i]]) < 5:
            by_s[T.sess[i]].append(i)
    equity = peak = start_equity
    cooldown, served, ruined = 0, False, False
    path, rets, taken_s, taken_n, desired_t, filled_t = [], [], [], [], 0.0, 0.0
    for si, s in enumerate(T.cal):
        if ruined:
            path.append(0.0)
            rets.append(0.0)
            continue
        dd = 1 - equity / peak
        if dd <= 0.20:
            served = False
        if cooldown == 0 and dd > 0.20 and not served:
            cooldown, served = 10, True
        if cooldown > 0:
            cooldown -= 1
            path.append(equity)
            rets.append(0.0)
            continue
        lev = min(cap_leverage, rung * regime[s] * (1.0 if dd <= 0.10 else 0.5))
        pnl = 0.0
        for i in by_s.get(si, ()):
            li = min(lev, 1.0) if T.price[i] < 5 else lev
            desired = equity * li / 5
            cap = 0.01 * T.dv[i]
            if not math.isnan(T.bar_dv[i]):
                cap = min(cap, 0.10 * T.bar_dv[i])
            notional = min(desired, cap)
            desired_t += desired
            if notional <= 0:
                continue
            filled_t += notional
            net = R.net_return(float(T.entry[i]), float(T.exit[i]), float(T.cin[i]), float(T.cout[i]), T.day[i], notional)
            pnl += net * notional * (1 + float(T.cin[i]))
            taken_s.append(si)
            taken_n.append(net)
        rets.append(pnl / equity)
        equity += pnl
        if equity <= 0:
            equity, ruined = 0.0, True
        peak = max(peak, equity)
        path.append(equity)
    n = len(T.cal)
    eq = np.array(path)
    run_peak = np.maximum.accumulate(np.concatenate(([start_equity], eq)))[1:]
    return ({"final_equity": V1.rnd(equity, 2), "cagr": V1.rnd((equity / start_equity) ** (252 / n) - 1 if (n and equity > 0) else -1.0),
             "max_drawdown": V1.rnd(float(((run_peak - eq) / run_peak).max()) if n else 0.0), "worst_session": V1.rnd(min(rets)) if rets else None,
             "trades_taken": len(taken_n), "fill_ratio": V1.rnd(filled_t / desired_t) if desired_t else None, "ruined": ruined},
            np.array(taken_s, dtype=int), V1.quantise(taken_n))


def evaluate_family(T: Trades, rids, regime, cap_leverage):
    S = len(T.cal)
    C = V1.replicate_counts(S, seed=SEED)
    out, cols, cnts, keys = {}, [], [], []
    by_rid = defaultdict(list)
    for i, r in enumerate(T.rid):
        by_rid[r].append(i)
    for rid in rids:
        idx = np.array(by_rid.get(rid, []), dtype=int)
        nets = {name: V1.quantise(T.net[name][idx]) for name, _, _ in V1.VARIANTS}
        conc_n = np.bincount(T.sess[idx], minlength=S)[T.sess[idx]] if len(idx) else np.zeros(0, dtype=int)
        codes = {"by_year": (T.years, T.year[idx]), "by_price_tier": (V1.PRICE_LABELS, T.ptier[idx]),
                 "by_v_tier": (V1.V_LABELS, np.minimum(T.vtier[idx], 2)),
                 "by_concurrency": (V1.CONC_LABELS, np.searchsorted([1, 5, 20], conc_n, side="left") if len(idx) else conc_n)}
        m = V1.summarise(nets["primary"], T.exit[idx] / T.entry[idx] - 1 if len(idx) else np.zeros(0), T.sess[idx], S, codes)
        if len(idx):
            m["mean_stress"] = V1.rnd(float(nets["stress"].sum()) / len(idx) / Q)
            m["mean_ibkr"] = V1.rnd(float(nets["ibkr"].sum()) / len(idx) / Q)
            ns = ~T.supplement[idx]
            m["without_premarket_supplement_rows"] = [int(ns.sum()), V1.rnd(float(nets["primary"][ns].sum()) / int(ns.sum()) / Q) if ns.any() else None]
            m["p_two_way_cluster"] = V1.rnd(V1.two_way_p(nets["primary"] / Q, T.sess[idx], T.sym[idx]), 10)
        out[rid] = m
        for name, _, _ in V1.VARIANTS:
            cols.append(np.bincount(T.sess[idx], weights=nets[name], minlength=S))
            cnts.append(np.bincount(T.sess[idx], minlength=S).astype(float))
            keys.append((rid, name))
        out[rid]["portfolio"] = {}
        for rung in V1.RUNGS:
            stats, ts, tn = simulate(T, idx, regime, rung, cap_leverage)
            out[rid]["portfolio"][str(rung)] = stats
            cols.append(np.bincount(ts, weights=tn, minlength=S))
            cnts.append(np.bincount(ts, minlength=S).astype(float))
            keys.append((rid, f"portfolio_{rung}"))
    if cols:
        Smat, Nmat = np.stack(cols, axis=1), np.stack(cnts, axis=1)
        for lo in range(0, Smat.shape[1], 256):
            p, lb = V1.bootstrap(C, Smat[:, lo:lo + 256], Nmat[:, lo:lo + 256])
            for j, (rid, name) in enumerate(keys[lo:lo + 256]):
                if name.startswith("portfolio_"):
                    out[rid]["portfolio"][name.split("_")[1]].update({"p": V1.rnd(p[j], 10), "lower_bound": V1.rnd(lb[j])})
                else:
                    sfx = "" if name == "primary" else f"_{name}"
                    out[rid]["p" + sfx] = V1.rnd(p[j], 10)
                    out[rid]["lower_bound" + sfx] = V1.rnd(lb[j])
    return out


def read_trades(path: Path, split: str, table_sha: str):
    meta = json.loads(Path(str(path) + ".meta.json").read_text())
    if meta.get("mode") != "v2_trades" or meta["split"] != split or meta.get("cost_table_sha256") != table_sha:
        raise SystemExit(f"{path} is not a v2 trades file for {split} gated on this cost table")
    h, rows = hashlib.sha256(), []
    with gzip.open(path, "rb") as f:
        for line in f:
            h.update(line)
            rows.append(json.loads(line))
    if h.hexdigest() != meta["content_sha256"]:
        raise SystemExit(f"{path} content hash mismatch")
    return rows, meta


def ef_trades(rows, costs: V1.Costs, cal):
    E, F = Trades(cal), Trades(cal)
    for r in rows:
        day = r["session"]
        for rid, e in sorted(r["E"].items()):
            for x in R.EXITS:
                px, ts, fb, cum = e["exits"][x]
                c_in = 1.25 * costs.half_spread(day, e["entry_ts"], e["entry"], e["entry_cum_dv"])
                c_out = 1.25 * costs.half_spread(day, ts, px, cum)
                E.add(f"{rid}|{x}", day, r["symbol"], e["entry"], px, c_in, c_out, e["decision_price"], e["decision_dv"], e["entry_bar_dv"],
                      e["entry_ts"], r["supplement"])
        for name, e in sorted(r["F"].items()):
            for y in FV2.Y_EXITS:
                px, ts, fb, cum = e["exits"][y]
                c_in = 1.25 * costs.half_spread(day, e["entry_ts"], e["entry"], e["entry_cum_dv"])
                c_out = 1.25 * costs.half_spread(day, ts, px, cum)
                F.add(f"F|{name}|{y}", day, r["symbol"], e["entry"], px, c_in, c_out, e["decision_price"], e["decision_dv"], e["entry_bar_dv"],
                      e["entry_ts"], r["supplement"])
    return E.finish(), F.finish()


def p_trades(daily: Path, costs: V1.Costs, cal, lo: str, hi: str):
    """V7-V10 from the daily dataset; both d and d+1 inside the split (V13)."""
    import duckdb
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    q = f"""
    WITH b AS (
      SELECT symbol, session_date AS d, raw_c, raw_o, raw_vw * raw_v AS dv, all_o, all_h, all_l, all_c, all_v,
        lag(all_c) OVER w AS c_prev, lead(all_o) OVER w AS o_next, lead(all_c) OVER w AS c_next, lead(raw_o) OVER w AS raw_o_next,
        lead(raw_c) OVER w AS raw_c_next, lead(session_date) OVER w AS d_next,
        median(all_v) OVER (w ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS v_med20,
        count(*) OVER (w ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS n20,
        max(all_h) OVER (w ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS h_max20,
        min(all_h - all_l) OVER (w ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS r_min6
      FROM read_parquet('{daily}') WHERE in_all AND session_date <= DATE '{hi}'
      WINDOW w AS (PARTITION BY symbol ORDER BY session_date))
    SELECT symbol, CAST(d AS VARCHAR), CAST(d_next AS VARCHAR), raw_c, raw_o_next, raw_c_next, dv, all_o, all_h, all_l, all_c, all_v,
           c_prev, o_next, c_next, v_med20, n20, h_max20, r_min6
    FROM b WHERE d >= DATE '{lo}' AND d_next IS NOT NULL AND d_next <= DATE '{hi}' AND raw_c >= 1 AND dv >= 1000000 AND NOT {DERIV}
      AND c_prev > 0 AND o_next > 0 AND c_next > 0 ORDER BY 2, 1"""
    rows = con.execute(q).fetchall()
    T = Trades(cal)
    universe = defaultdict(list)
    for (sym, d, dn, raw_c, raw_on, raw_cn, dv, o, h, l, c, v, c_prev, o_next, c_next, v_med20, n20, h_max20, r_min6) in rows:
        if d not in T.cidx:
            continue
        scores = {"S1_day2_runner": c / c_prev - 1 >= 0.30 and c >= 0.90 * h,
                  "S2_volume_breakout": n20 == 20 and v_med20 and v >= 5 * v_med20 and h_max20 is not None and c >= h_max20 and c / c_prev - 1 >= 0.10,
                  "S3_compression_expansion": n20 == 20 and r_min6 is not None and (h - l) < r_min6 and v_med20 and v >= 3 * v_med20,
                  "S4_gap_and_hold": o >= 1.20 * c_prev and c >= o}
        universe[d].append((sym, c_next / c - 1, [k for k, ok in scores.items() if ok]))
        for sc, ok in scores.items():
            if not ok:
                continue
            hs_in = costs.cells[f"3|{R.price_tier(raw_c)}|{R.dv_tier(dv)}"]["half_spread"]
            for z in Z_EXITS:
                use_open = z == "Z1" or (z == "Z3" and o_next < 0.95 * c)
                ratio = (o_next if use_open else c_next) / c
                exit_raw = raw_c * ratio
                tb = 2 if use_open else 3
                hs_out = costs.cells[f"{tb}|{R.price_tier(raw_on if use_open else raw_cn)}|{R.dv_tier(dv)}"]["half_spread"]
                T.add(f"P|{sc}|{z}", d, sym, raw_c, exit_raw, 0.5 * hs_in, 0.5 * hs_out, raw_c, dv, None, -dv, False, exit_day=dn)
    return T.finish(), universe


def p_capture(universe):
    """V10: recall of day-d+1 degree-tier movers by each score's qualifying set, beside the base rate."""
    out = {}
    tier_counts = defaultdict(int)
    sel = defaultdict(lambda: defaultdict(int))
    total = 0
    for d, rows in universe.items():
        for sym, g, scs in rows:
            ti = R.degree_tier(g)
            tier_counts[ti] += 1
            total += 1
            for sc in scs:
                sel[sc][ti] += 1
    for sc in P_SCORES:
        out[sc] = {ti: {"in_tier": n, "selected": sel[sc][ti], "recall": V1.rnd(sel[sc][ti] / n) if n else None,
                        "base_rate": V1.rnd(n / total) if total else None} for ti, n in sorted(tier_counts.items())}
    return out


def family_selection(fam, dev, val, rids):
    dmin, vmin, _, hsize = PASS[fam]
    robust = ("winsorised_mean", "mean_without_top5_sessions", "mean_of_session_means")
    dev_pass = [r for r in rids if dev[r]["trades"] >= dmin and dev[r].get("p") is not None and dev[r]["p"] <= 0.05]
    vp = [val[r]["p"] if val[r]["trades"] else 1.0 for r in dev_pass]
    confirm, validated = {}, []
    for r, pa in zip(dev_pass, V1.bh(vp)):
        v = val[r]
        ok = bool(v["trades"] >= vmin and pa <= 0.10 and all((v.get(k) or 0) > 0 for k in robust))
        confirm[r] = {"validation_trades": v["trades"], "validation_p": v.get("p"), "bh_adjusted": V1.rnd(pa, 10), "confirmed": ok}
        if ok:
            validated.append(r)
    lbk = lambda r: val[r]["lower_bound"] if val[r].get("lower_bound") is not None else -1e18  # noqa: E731
    return {"development_passes": dev_pass, "validation": confirm, "validated": validated,
            "holdout_candidates": sorted(validated, key=lambda r: (val[r]["p"], -lbk(r), r))[:hsize]}


def dev_val(a) -> int:
    inputs, table, _ = V1.check_inputs(a)
    costs = V1.Costs(table)
    lo, hi = V1.SPLITS["development"][0], V1.SPLITS["validation"][1]
    spy = V1.Spy(a.daily, hi)
    dev_cal, val_cal = spy.calendar("development"), spy.calendar("validation")
    regime = spy.regime(dev_cal + val_cal)
    dev_rows, dev_meta = read_trades(a.trades_dev, "dev", inputs["cost_table_sha256"])
    val_rows, val_meta = read_trades(a.trades_val, "val", inputs["cost_table_sha256"])
    E_dev, F_dev = ef_trades(dev_rows, costs, dev_cal)
    E_val, F_val = ef_trades(val_rows, costs, val_cal)
    P_dev, U_dev = p_trades(a.daily, costs, dev_cal, *V1.SPLITS["development"])
    P_val, U_val = p_trades(a.daily, costs, val_cal, *V1.SPLITS["validation"])
    rids = {"E": sorted(f"{FV2.e_rule_id(w, g, v, n)}|{x}" for w in FV2.WINDOWS for g in FV2.E_GAINS for v in FV2.E_VOLUMES
                        for n in FV2.E_NEWS for x in R.EXITS),
            "F": sorted(f"F|{s}|{y}" for s in FV2.F_SETUPS for y in FV2.Y_EXITS),
            "P": sorted(f"P|{s}|{z}" for s in P_SCORES for z in Z_EXITS)}
    res = {}
    for fam, (Td, Tv, cap) in (("E", (E_dev, E_val, 4.0)), ("F", (F_dev, F_val, 4.0)), ("P", (P_dev, P_val, 2.0))):
        dev = evaluate_family(Td, rids[fam], regime, cap)
        val = evaluate_family(Tv, rids[fam], regime, cap)
        res[fam] = {"development": dev, "validation": val, "selection": family_selection(fam, dev, val, rids[fam]),
                    "trades": {"development": Td.n, "validation": Tv.n}}
    results = {"schema_version": 1, "protocol": PROTOCOL["id"], "stage": "dev_val", "protocol_sha256": V1.sha256_bytes(PROTOCOL_BYTES),
               "inputs": dict(inputs, seed=SEED, trades_dev_content_sha256=dev_meta["content_sha256"], trades_val_content_sha256=val_meta["content_sha256"],
                              clarifications_v2_sha256=V1.sha256_bytes((HERE / "clarifications-v2.json").read_bytes())),
               "families": res, "p_capture": {"development": p_capture(U_dev), "validation": p_capture(U_val)}}
    body = (json.dumps(results, indent=1, sort_keys=True) + "\n").encode()
    a.out.write_bytes(body)
    os.chmod(a.out, 0o600)
    print(json.dumps({"out": a.out.name, "sha256": V1.sha256_bytes(body),
                      "passes": {f: len(res[f]["selection"]["development_passes"]) for f in res},
                      "validated": {f: res[f]["selection"]["validated"] for f in res}}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="stage", required=True)
    s = sub.add_parser("dev_val")
    s.add_argument("--trades-dev", type=Path, required=True)
    s.add_argument("--trades-val", type=Path, required=True)
    s.add_argument("--cost-table", type=Path, required=True)
    s.add_argument("--daily", type=Path, required=True)
    s.add_argument("--audit", type=Path, required=True)
    s.add_argument("--state", type=Path, default=Path.home() / ".local/state/native-agent-stack/research/mover-early-entry")
    s.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    return dev_val(a)


if __name__ == "__main__":
    raise SystemExit(main())
