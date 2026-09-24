"""Evaluate protocol-v2.json (mover-followup-v2-20260924): families E, F and P; deterministic.

  python evaluate_v2.py dev_val --trades-dev F --trades-val F --cost-table evidence/cost-table-run-v1.json \
      --daily DAILY --audit AUDIT --out RESULTS.json
  python evaluate_v2.py holdout --dev-val RESULTS.json --trades-holdout F --cost-table ... --daily ... --audit ... --out HOLDOUT.json

E and F trades come from features_v2.py; P is computed here from the daily dataset. Statistics,
costs, fees and the portfolio follow v1 (evaluate.py) with the v2 seed and clarifications V1-V20.
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
CAPS = {"E": 4.0, "F": 4.0, "P": 2.0}
MAX_GAP_SESSIONS = 5  # V17


def rule_ids():
    return {"E": sorted(f"{FV2.e_rule_id(w, g, v, n)}|{x}" for w in FV2.WINDOWS for g in FV2.E_GAINS for v in FV2.E_VOLUMES
                        for n in FV2.E_NEWS for x in R.EXITS),
            "F": sorted(f"F|{s}|{y}" for s in FV2.F_SETUPS for y in FV2.Y_EXITS),
            "P": sorted(f"P|{s}|{z}" for s in P_SCORES for z in Z_EXITS)}


class Trades:
    """Column arrays for one family's trades across its rule-exits."""

    def __init__(self, cal):
        self.cal = cal
        self.cidx = {s: i for i, s in enumerate(cal)}
        self.cols = defaultdict(list)

    def add(self, rid, day, symbol, entry, exit_px, c_in, c_out, decision_price, decision_dv, bar_dv, order_key,
            supplement=False, basis_uncertain=False, flag=None, exit_day=None, forced_return=None):
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
        c["basis_uncertain"].append(bool(basis_uncertain))
        c["flag"].append(flag or "")
        c["forced"].append(np.nan if forced_return is None else forced_return)

    def finish(self):
        c = self.cols
        self.n = len(c["rid"])
        self.rid = np.array(c["rid"], dtype=object)
        self.symbol, self.day, self.flag = c["symbol"], c["day"], np.array(c["flag"], dtype=object)
        self.sess = np.array(c["sess"], dtype=int)
        for k in ("entry", "exit", "cin", "cout", "price", "dv", "bar_dv", "order", "forced"):
            setattr(self, k, np.array(c[k], dtype=float))
        self.supplement = np.array(c["supplement"], dtype=bool)
        self.basis_uncertain = np.array(c["basis_uncertain"], dtype=bool)
        fees = [R.fee_rates(d) for d in self.day]
        self.sec = np.array([f[0] for f in fees]) if fees else np.zeros(0)
        self.taf = np.array([f[1] for f in fees]) if fees else np.zeros(0)
        self.capv = np.array([f[2] for f in fees]) if fees else np.zeros(0)
        self.net = {}
        for name, broker, mult in V1.VARIANTS:
            net = R.net_return_np(self.entry, self.exit, self.cin, self.cout, self.sec, self.taf, self.capv, REF, broker, mult) \
                if self.n else np.zeros(0)
            self.net[name] = np.where(np.isnan(self.forced), net, self.forced)  # V17: a forced -100% loss
        syms = {s: i for i, s in enumerate(sorted(set(self.symbol)))}
        self.sym = np.array([syms[s] for s in self.symbol], dtype=int)
        self.years = sorted({d[:4] for d in self.day})
        self.year = np.array([self.years.index(d[:4]) for d in self.day], dtype=int)
        self.ptier = np.searchsorted(R.PRICE_TIERS, self.price, side="right") if self.n else np.zeros(0, dtype=int)
        self.vtier = np.minimum(np.searchsorted(R.DV_TIERS, self.dv, side="right"), 2) if self.n else np.zeros(0, dtype=int)
        return self

    def break_even(self, idx):
        """v1 C8 on this family's trades."""
        if not len(idx) or np.isnan(self.forced[idx]).sum() != len(idx):
            return None  # forced losses have no cost to scale

        def mean_at(k):
            return float(R.net_return_np(self.entry[idx], self.exit[idx], self.cin[idx], self.cout[idx], self.sec[idx], self.taf[idx],
                                         self.capv[idx], REF, "alpaca", k).mean())
        if mean_at(0.0) <= 0:
            return None
        lo, hi = 0.0, 1000.0
        if mean_at(hi) > 0:
            return hi
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if mean_at(mid) > 0 else (lo, mid)
        return lo


def simulate(T: Trades, idx, regime, rung, cap_leverage, start_equity=100_000.0, lag_booking=False):
    """V11/V13/V19: 5 slots per session in decision order, notional from the session's starting equity, v1's
    caps, drawdown factor, cooldown and ruin. lag_booking (P) books a session's P&L after the next session's
    sizing, because a next-close exit is only known after the auction the next entries trade in."""
    by_s = defaultdict(list)
    for i in sorted(idx.tolist(), key=lambda i: (T.sess[i], T.order[i], T.symbol[i])):
        if len(by_s[T.sess[i]]) < 5:
            by_s[T.sess[i]].append(i)
    equity = peak = start_equity
    pending = 0.0
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
        pnl = 0.0
        if cooldown > 0:
            cooldown -= 1
        else:
            lev = min(cap_leverage, rung * regime[s] * (1.0 if dd <= 0.10 else 0.5))
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
                if not math.isnan(T.forced[i]):
                    net = float(T.forced[i])
                else:
                    net = R.net_return(float(T.entry[i]), float(T.exit[i]), float(T.cin[i]), float(T.cout[i]), T.day[i], notional)
                pnl += net * notional * (1 + float(T.cin[i]))
                taken_s.append(si)
                taken_n.append(net)
        start = equity
        if lag_booking:
            equity += pending
            pending = pnl
        else:
            equity += pnl
        rets.append((equity - start) / start if start else 0.0)
        if equity <= 0:
            equity, ruined = 0.0, True
        peak = max(peak, equity)
        path.append(equity)
    if lag_booking and not ruined:
        equity += pending
        path[-1] = equity
    n = len(T.cal)
    eq = np.array(path)
    run_peak = np.maximum.accumulate(np.concatenate(([start_equity], eq)))[1:]
    return ({"final_equity": V1.rnd(equity, 2), "cagr": V1.rnd((equity / start_equity) ** (252 / n) - 1 if (n and equity > 0) else -1.0),
             "max_drawdown": V1.rnd(float(((run_peak - eq) / run_peak).max()) if n else 0.0), "worst_session": V1.rnd(min(rets)) if rets else None,
             "share_sessions_loss_over_5pct": V1.rnd(np.mean(np.array(rets) < -0.05)) if rets else None,
             "trades_taken": len(taken_n), "taken_mean_net": V1.rnd(float(np.mean(taken_n))) if taken_n else None,
             "fill_ratio": V1.rnd(filled_t / desired_t) if desired_t else None, "ruined": ruined},
            np.array(taken_s, dtype=int), V1.quantise(taken_n))


def evaluate_family(T: Trades, rids, regime, cap_leverage, lag_booking=False):
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
                 "by_v_tier": (V1.V_LABELS, T.vtier[idx]),
                 "by_concurrency": (V1.CONC_LABELS, np.searchsorted([1, 5, 20], conc_n, side="left") if len(idx) else conc_n)}
        m = V1.summarise(nets["primary"], T.exit[idx] / T.entry[idx] - 1 if len(idx) else np.zeros(0), T.sess[idx], S, codes)
        if len(idx):
            m["mean_stress"] = V1.rnd(float(nets["stress"].sum()) / len(idx) / Q)
            m["mean_ibkr"] = V1.rnd(float(nets["ibkr"].sum()) / len(idx) / Q)
            for name, mask in (("without_premarket_supplement_rows", ~T.supplement[idx]), ("without_basis_uncertain_rows", ~T.basis_uncertain[idx]),
                               ("without_flagged_rows", T.flag[idx] == "")):
                m[name] = [int(mask.sum()), V1.rnd(float(nets["primary"][mask].sum()) / int(mask.sum()) / Q) if mask.any() else None]
            m["flags"] = {f: int((T.flag[idx] == f).sum()) for f in sorted(set(T.flag[idx])) if f}
            m["p_two_way_cluster"] = V1.rnd(V1.two_way_p(nets["primary"] / Q, T.sess[idx], T.sym[idx]), 10)
            m["break_even_cost_multiple"] = V1.rnd(T.break_even(idx), 4)
        out[rid] = m
        for name, _, _ in V1.VARIANTS:
            cols.append(np.bincount(T.sess[idx], weights=nets[name], minlength=S))
            cnts.append(np.bincount(T.sess[idx], minlength=S).astype(float))
            keys.append((rid, name))
        out[rid]["portfolio"] = {}
        for rung in V1.RUNGS:
            stats, ts, tn = simulate(T, idx, regime, rung, cap_leverage, lag_booking=lag_booking)
            out[rid]["portfolio"][str(rung)] = stats
            cols.append(np.bincount(ts, weights=tn, minlength=S))
            cnts.append(np.bincount(ts, minlength=S).astype(float))
            keys.append((rid, f"portfolio_{rung}"))
        out[rid]["portfolio"]["capacity_rung1"] = {str(int(eq)): simulate(T, idx, regime, 1, cap_leverage, eq, lag_booking)[0]
                                                   for eq in (10_000.0, 100_000.0, 1_000_000.0)}
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
    lo, hi = V1.SPLITS[V1.SPLIT_OF[split]]
    if any(not (lo <= r["session"] <= hi) for r in rows):
        raise SystemExit(f"{path} has a session outside {split}")
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
                      e["entry_ts"], r["supplement"], r["basis_uncertain"], "close_fallback" if fb else ("halt" if e["halt"] else None))
        for name, e in sorted(r["F"].items()):
            for y in FV2.Y_EXITS:
                px, ts, fb, cum = e["exits"][y]
                c_in = 1.25 * costs.half_spread(day, e["entry_ts"], e["entry"], e["entry_cum_dv"])
                c_out = 1.25 * costs.half_spread(day, ts, px, cum)
                flag = "degenerate_stop" if e["degenerate"] else ("close_fallback" if fb else ("halt" if e["halt"] else None))
                F.add(f"F|{name}|{y}", day, r["symbol"], e["entry"], px, c_in, c_out, e["decision_price"], e["decision_dv"], e["entry_bar_dv"],
                      e["entry_ts"], r["supplement"], r["basis_uncertain"], flag)
    return E.finish(), F.finish()


def ef_capture(rows):
    """Degree-tier capture for E and F (v1 capture's quantities): recall of each tier's candidate days, median
    decision gain, and median gross return from entry to the close and to the session high."""
    days = [r for r in rows if r.get("eventual_gain") is not None]
    tiers = np.array([R.degree_tier_index(r["eventual_gain"]) for r in days], dtype=int)
    labels = [R.tier_label(i) for i in range(len(R.DEGREE_TIERS))]
    rids = sorted({k for r in days for k in r["E"]} | {f"F|{k}" for r in days for k in r["F"]})
    out = {}
    for rid in rids:
        fam, key = ("F", rid[2:]) if rid.startswith("F|") else ("E", rid)
        cells = {}
        for ti, lab in enumerate(labels):
            sel = [r for r, t in zip(days, tiers) if t == ti]
            fired = [r[fam][key] for r in sel if key in r[fam]]
            cells[lab] = {"symbol_days": len(sel), "fired": len(fired), "recall": V1.rnd(len(fired) / len(sel)) if sel else None,
                          "median_gain_at_decision": V1.rnd(np.median([e.get("decision_gain", e["decision_price"] / r0["ref"] - 1)
                                                                       for e, r0 in zip(fired, [r for r in sel if key in r[fam]])])) if fired else None,
                          "median_gross_to_close": V1.rnd(np.median([e["exits"]["X1" if fam == "E" else "Y1"][0] / e["entry"] - 1 for e in fired])) if fired else None,
                          "median_gross_to_session_high": V1.rnd(np.median([e["high"] / e["entry"] - 1 for e in fired])) if fired else None}
        out[rid] = cells
    return out


def ef_counts(rows):
    return {"candidate_days": len(rows), "eventual_gain_missing": sum(1 for r in rows if r.get("eventual_gain") is None),
            "basis_uncertain_days": sum(1 for r in rows if r.get("basis_uncertain")),
            "f_candidates_without_official_open": sum(1 for r in rows if r.get("f_candidate_no_official_open")),
            "f_degenerate_stops": {s: sum(1 for r in rows if s in r["F"] and r["F"][s]["degenerate"]) for s in FV2.F_SETUPS},
            "e_days_with_any_fire": sum(1 for r in rows if r["E"]), "f_days_with_any_setup": sum(1 for r in rows if r["F"])}


def p_trades(daily: Path, costs: V1.Costs, cal_all, split_cal, lo: str, hi: str):
    """V7-V10, V15-V20 from the daily dataset."""
    import duckdb
    cpos = {d: i for i, d in enumerate(cal_all)}
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    rows = con.execute(f"""
    WITH b AS (
      SELECT symbol, session_date AS d, raw_c, raw_o, raw_vw * raw_v AS dv, all_o, all_h, all_l, all_c, all_v,
        lag(session_date) OVER w AS d_prev, lag(all_c) OVER w AS c_prev,
        lead(session_date) OVER w AS d_next, lead(all_o) OVER w AS o_next, lead(all_c) OVER w AS c_next,
        lead(raw_o) OVER w AS raw_o_next, lead(raw_c) OVER w AS raw_c_next,
        median(all_v) OVER (w ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS v_med20,
        count(*) OVER (w ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS n20,
        max(all_h) OVER (w ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS h_max20,
        min(all_h - all_l) OVER (w ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS r_min6
      FROM read_parquet('{daily}') WHERE in_all AND session_date <= DATE '{hi}'
      WINDOW w AS (PARTITION BY symbol ORDER BY session_date))
    SELECT symbol, CAST(d AS VARCHAR), CAST(d_prev AS VARCHAR), CAST(d_next AS VARCHAR), raw_c, raw_o_next, raw_c_next, dv,
           all_o, all_h, all_l, all_c, all_v, c_prev, o_next, c_next, v_med20, n20, h_max20, r_min6
    FROM b WHERE d >= DATE '{lo}' AND raw_c >= 1 AND dv >= 1000000 AND NOT {DERIV} ORDER BY 2, 1""").fetchall()
    T = Trades(split_cal)
    skips = defaultdict(int)
    universe = defaultdict(list)
    qualifying = defaultdict(list)  # (score, d) -> [(dv, symbol, payload)]
    for (sym, d, dp, dn, raw_c, raw_on, raw_cn, dv, o, h, l, c, v, c_prev, o_next, c_next, v_med20, n20, h_max20, r_min6) in rows:
        if d not in T.cidx:
            continue
        i = cpos[d]
        if dp is None or cpos.get(dp) != i - 1 or not c_prev:
            skips["previous_row_not_the_previous_session"] += 1
            continue
        if not c or c <= 0:
            skips["no_adjusted_close"] += 1
            continue
        gap = (cpos[dn] - i) if dn in cpos else None  # rows are read only up to hi, so dn <= hi
        if gap is None or gap > MAX_GAP_SESSIONS:
            if i + MAX_GAP_SESSIONS >= len(cal_all) or cal_all[min(i + MAX_GAP_SESSIONS, len(cal_all) - 1)] > hi:
                skips["exit_window_beyond_split"] += 1
                continue
            exit_kind, exit_day = "no_row_within_5_sessions", cal_all[i + 1]
        elif gap == 1:
            if not (o_next and c_next and raw_on and raw_cn):
                skips["next_row_missing_prices"] += 1
                continue
            exit_kind, exit_day = None, dn
        else:
            if not (o_next and c_next and raw_on and raw_cn):
                skips["next_row_missing_prices"] += 1
                continue
            exit_kind, exit_day = "held_through_gap", dn
        if cal_all[i + 1] <= hi:
            universe[d].append((sym, (c_next / c - 1) if (exit_kind != "no_row_within_5_sessions" and gap == 1) else None))
        scores = {"S1_day2_runner": c / c_prev - 1 >= 0.30 - R.GAIN_EPS and c >= 0.90 * h,
                  "S2_volume_breakout": n20 == 20 and bool(v_med20) and v >= 5 * v_med20 and h_max20 is not None and c >= h_max20
                  and c / c_prev - 1 >= 0.10 - R.GAIN_EPS,
                  "S3_compression_expansion": n20 == 20 and r_min6 is not None and (h - l) < r_min6 and bool(v_med20) and v >= 3 * v_med20,
                  "S4_gap_and_hold": o >= 1.20 * c_prev * (1 - 1e-12) and c >= o}
        for sc, ok in scores.items():
            if ok:
                qualifying[(sc, d)].append((dv, sym, (raw_c, raw_on, raw_cn, dv, c, o_next, c_next, exit_kind, exit_day)))
    selected = defaultdict(set)
    for (sc, d), items in sorted(qualifying.items()):
        for dv, sym, (raw_c, raw_on, raw_cn, dv_, c, o_next, c_next, exit_kind, exit_day) in sorted(items, key=lambda x: (-x[0], x[1]))[:5]:  # V18
            selected[(sc, d)].add(sym)
            hs_in = costs.cells[f"3|{R.price_tier(raw_c)}|{R.dv_tier(dv)}"]["half_spread"]
            for z in Z_EXITS:
                if exit_kind == "no_row_within_5_sessions":
                    T.add(f"P|{sc}|{z}", d, sym, raw_c, 0.0, 0.5 * hs_in, 0.0, raw_c, dv, None, -dv, flag=exit_kind,
                          exit_day=exit_day, forced_return=-1.0)
                    continue
                use_open = z == "Z1" or (z == "Z3" and o_next < 0.95 * c)
                exit_raw = raw_c * (o_next if use_open else c_next) / c
                hs_out = costs.cells[f"{2 if use_open else 3}|{R.price_tier(raw_on if use_open else raw_cn)}|{R.dv_tier(dv)}"]["half_spread"]
                T.add(f"P|{sc}|{z}", d, sym, raw_c, exit_raw, 0.5 * hs_in, 0.5 * hs_out, raw_c, dv, None, -dv, flag=exit_kind, exit_day=exit_day)
    cap = p_capture(universe, qualifying, selected)
    return T.finish(), cap, dict(skips)


def p_capture(universe, qualifying, selected):
    """V10: recall of day-d+1 degree-tier movers by each score's qualifying set and top-5 set, beside the base rate."""
    tier_counts = defaultdict(int)
    q_hits, t_hits = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    total = 0
    qsets = {k: {s for _, s, _ in v} for k, v in qualifying.items()}
    for d, rows in universe.items():
        for sym, g in rows:
            if g is None:
                continue
            ti = R.degree_tier(g)
            tier_counts[ti] += 1
            total += 1
            for sc in P_SCORES:
                if sym in qsets.get((sc, d), ()):
                    q_hits[sc][ti] += 1
                if sym in selected.get((sc, d), ()):
                    t_hits[sc][ti] += 1
    return {sc: {ti: {"in_tier": n, "base_rate": V1.rnd(n / total) if total else None,
                      "recall_qualifying": V1.rnd(q_hits[sc][ti] / n) if n else None, "recall_top5": V1.rnd(t_hits[sc][ti] / n) if n else None}
                 for ti, n in sorted(tier_counts.items())} for sc in P_SCORES}


def family_selection(fam, dev, val, rids):
    dmin, vmin, _, hsize = PASS[fam]
    robust = ("winsorised_mean", "mean_without_top5_sessions", "mean_of_session_means")
    dev_pass = [r for r in rids if dev[r]["trades"] >= dmin and dev[r].get("p") is not None and dev[r]["p"] <= 0.05]
    vp = [val[r]["p"] if val[r]["trades"] else 1.0 for r in dev_pass]
    confirm, validated = {}, []
    for r, pa, pb in zip(dev_pass, V1.bh(vp), V1.by(vp)):
        v = val[r]
        ok = bool(v["trades"] >= vmin and pa <= 0.10 and all((v.get(k) or 0) > 0 for k in robust))
        confirm[r] = {"validation_trades": v["trades"], "validation_p": v.get("p"), "bh_adjusted": V1.rnd(pa, 10),
                      "by_adjusted_sensitivity": V1.rnd(pb, 10), "confirmed": ok}
        if ok:
            validated.append(r)
    lbk = lambda r: val[r]["lower_bound"] if val[r].get("lower_bound") is not None else -1e18  # noqa: E731
    most = sorted(rids, key=lambda r: (-dev[r]["trades"], dev[r].get("p") or 1.0, r))[0]
    cand = ({"rule_exit": sorted(validated, key=lambda r: (-lbk(r), r))[0], "basis": "highest validation lower bound", "mechanics_only": False}
            if validated else {"rule_exit": most, "basis": "most-traded development rule-exit (C20); nothing validated", "mechanics_only": True})
    return {"development_passes": dev_pass, "validation": confirm, "validated": validated,
            "holdout_candidates": sorted(validated, key=lambda r: (val[r]["p"], -lbk(r), r))[:hsize], "paper_candidate": cand}


def inputs_for(a):
    inputs, table, _ = V1.check_inputs(a)
    if inputs["cost_table_sha256"] != FV2.V1_COST_TABLE_SHA256:
        raise SystemExit("protocol v2 uses v1's committed cost table only")
    inputs["bootstrap"] = {"B": V1.B, "block": V1.BLOCK, "seed": SEED}
    inputs["clarifications_v2_sha256"] = V1.sha256_bytes((HERE / "clarifications-v2.json").read_bytes())
    return inputs, table


def dev_val(a) -> int:
    inputs, table = inputs_for(a)
    costs = V1.Costs(table)
    lo, hi = V1.SPLITS["development"][0], V1.SPLITS["validation"][1]
    spy = V1.Spy(a.daily, hi)
    dev_cal, val_cal = spy.calendar("development"), spy.calendar("validation")
    regime = spy.regime(dev_cal + val_cal)
    dev_rows, dev_meta = read_trades(a.trades_dev, "dev", inputs["cost_table_sha256"])
    val_rows, val_meta = read_trades(a.trades_val, "val", inputs["cost_table_sha256"])
    E_dev, F_dev = ef_trades(dev_rows, costs, dev_cal)
    E_val, F_val = ef_trades(val_rows, costs, val_cal)
    P_dev, cap_dev, skip_dev = p_trades(a.daily, costs, spy.days, dev_cal, *V1.SPLITS["development"])
    P_val, cap_val, skip_val = p_trades(a.daily, costs, spy.days, val_cal, *V1.SPLITS["validation"])
    rids = rule_ids()
    res = {}
    for fam, (Td, Tv) in (("E", (E_dev, E_val)), ("F", (F_dev, F_val)), ("P", (P_dev, P_val))):
        dev = evaluate_family(Td, rids[fam], regime, CAPS[fam], lag_booking=fam == "P")
        val = evaluate_family(Tv, rids[fam], regime, CAPS[fam], lag_booking=fam == "P")
        res[fam] = {"development": dev, "validation": val, "selection": family_selection(fam, dev, val, rids[fam]),
                    "trades": {"development": Td.n, "validation": Tv.n}}
    results = {"schema_version": 1, "protocol": PROTOCOL["id"], "stage": "dev_val", "protocol_sha256": V1.sha256_bytes(PROTOCOL_BYTES),
               "inputs": dict(inputs, trades_dev_content_sha256=dev_meta["content_sha256"], trades_val_content_sha256=val_meta["content_sha256"]),
               "families": res,
               "counts": {"development": ef_counts(dev_rows), "validation": ef_counts(val_rows), "p_skips": {"development": skip_dev, "validation": skip_val}},
               "ef_capture_dev_and_val": ef_capture(dev_rows + val_rows),
               "ef_capture_dev_and_val_without_basis_uncertain": ef_capture([r for r in dev_rows + val_rows if not r.get("basis_uncertain")]),
               "p_capture": {"development": cap_dev, "validation": cap_val}}
    body = (json.dumps(results, indent=1, sort_keys=True) + "\n").encode()
    a.out.write_bytes(body)
    os.chmod(a.out, 0o600)
    print(json.dumps({"out": a.out.name, "sha256": V1.sha256_bytes(body),
                      "passes": {f: len(res[f]["selection"]["development_passes"]) for f in res},
                      "validated": {f: res[f]["selection"]["validated"] for f in res},
                      "paper_candidates": {f: res[f]["selection"]["paper_candidate"] for f in res}}))
    return 0


def holdout(a) -> int:
    prior_bytes = a.dev_val.read_bytes()
    prior = json.loads(prior_bytes)
    if prior.get("stage") != "dev_val" or prior.get("protocol") != PROTOCOL["id"]:
        raise SystemExit("holdout needs v2 dev_val results")
    inputs, table = inputs_for(a)
    if inputs["cost_table_sha256"] != prior["inputs"]["cost_table_sha256"]:
        raise SystemExit("the cost table changed after dev_val")
    todo = {f: prior["families"][f]["selection"]["holdout_candidates"] for f in prior["families"]}
    lo, hi = V1.SPLITS["holdout"]
    spy = V1.Spy(a.daily, hi)
    cal = spy.calendar("holdout")
    regime = spy.regime(cal)
    out = {}
    need_ef = todo.get("E") or todo.get("F")
    if need_ef:
        rows, meta = read_trades(a.trades_holdout, "holdout", inputs["cost_table_sha256"])
        if meta.get("dev_val_sha256") != V1.sha256_bytes(prior_bytes):
            raise SystemExit("holdout trades were not gated on these dev_val results")
        E, F = ef_trades(rows, V1.Costs(table), cal)
    for fam in ("E", "F", "P"):
        if not todo.get(fam):
            continue
        T = {"E": E, "F": F}[fam] if fam in ("E", "F") else p_trades(a.daily, V1.Costs(table), spy.days, cal, lo, hi)[0]
        stats = evaluate_family(T, todo[fam], regime, CAPS[fam], lag_booking=fam == "P")
        _, _, hmin, _ = PASS[fam]
        ps = [stats[r]["p"] if stats[r]["trades"] >= hmin else 1.0 for r in todo[fam]]
        passes = {r: {"trades": stats[r]["trades"], "p": stats[r].get("p"), "holm_adjusted": V1.rnd(pa, 10), "lower_bound": stats[r].get("lower_bound"),
                      "passed": bool(stats[r]["trades"] >= hmin and pa <= 0.05)} for r, pa in zip(todo[fam], V1.holm(ps))}
        best = sorted(todo[fam], key=lambda r: (-(stats[r]["lower_bound"] if stats[r].get("lower_bound") is not None else -1e18), r))[0]
        out[fam] = {"evaluated": todo[fam], "holdout": stats, "passes": passes,
                    "paper_candidate": {"rule_exit": best, "basis": "highest holdout lower bound", "mechanics_only": not passes[best]["passed"]}}
    results = {"schema_version": 1, "protocol": PROTOCOL["id"], "stage": "holdout", "dev_val_sha256": V1.sha256_bytes(prior_bytes),
               "inputs": inputs, "families": out}
    body = (json.dumps(results, indent=1, sort_keys=True) + "\n").encode()
    a.out.write_bytes(body)
    os.chmod(a.out, 0o600)
    print(json.dumps({"out": a.out.name, "sha256": V1.sha256_bytes(body), "families": {f: out[f]["passes"] for f in out}}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="stage", required=True)
    for name in ("dev_val", "holdout"):
        s = sub.add_parser(name)
        s.add_argument("--cost-table", type=Path, required=True)
        s.add_argument("--daily", type=Path, required=True)
        s.add_argument("--audit", type=Path, required=True)
        s.add_argument("--state", type=Path, default=Path.home() / ".local/state/native-agent-stack/research/mover-early-entry")
        s.add_argument("--out", type=Path, required=True)
        if name == "dev_val":
            s.add_argument("--trades-dev", type=Path, required=True)
            s.add_argument("--trades-val", type=Path, required=True)
        else:
            s.add_argument("--dev-val", type=Path, required=True)
            s.add_argument("--trades-holdout", type=Path)
    a = ap.parse_args(argv)
    return dev_val(a) if a.stage == "dev_val" else holdout(a)


if __name__ == "__main__":
    raise SystemExit(main())
