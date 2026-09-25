"""Statistics, items, Holm and verdicts for the ORB replication (protocol.json). Stdlib only.

  python evaluate.py power                              # pre-freeze: MDE and minimum sample from counts only
  python evaluate.py run --protocol-sha256 SHA          # post-freeze: items, portfolio, descriptives

``run`` refuses (exit != 0, nothing read) unless protocol.json has status frozen_before_outcomes,
frozen_before_outcomes true, and a sha256 equal to --protocol-sha256. ``power`` reads only signal-firing
counts (triggers.csv), never a price after a decision time.
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
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist

import orb_common as C  # noqa: E402
import orb_signal as S  # noqa: E402

LEGS = ("combined", "long", "short")


# ------------------------------------------------------------------ power (pre-freeze)

def mde(n: int, sd: float, deff: float, alpha: float, power: float = 0.8) -> float:
    z = NormalDist().inv_cdf(1 - alpha) + NormalDist().inv_cdf(power)
    return z * sd * math.sqrt(deff / n)


def n_required(effect: float, sd: float, deff: float, alpha: float, power: float = 0.8) -> int:
    z = NormalDist().inv_cdf(1 - alpha) + NormalDist().inv_cdf(power)
    return math.ceil((z * sd / effect) ** 2 * deff)


def power_table(per_session_fired: dict, per_session_long: dict, sessions: int, alpha: float, effect: float,
                sds=(1.5, 2.0, 3.0), rhos=(0.0, 0.02, 0.05)):
    out = {}
    for leg, counts in (("combined", per_session_fired), ("long", per_session_long)):
        n = sum(counts.values())
        k = sum(1 for v in counts.values() if v > 0)
        m_bar = n / k if k else 0.0
        rows = []
        for sd in sds:
            for rho in rhos:
                deff = 1 + (m_bar - 1) * rho
                rows.append({"sd_R": sd, "rho": rho, "deff": round(deff, 4), "mde_R": round(mde(n, sd, deff, alpha), 4),
                             "n_required_for_effect": n_required(effect, sd, deff, alpha)})
        out[leg] = {"trades": n, "sessions_with_trades": k, "m_bar": round(m_bar, 3), "table": rows}
    z = NormalDist().inv_cdf(1 - alpha) + NormalDist().inv_cdf(0.8)
    out["portfolio"] = {"sessions": sessions, "mde_annualised_sharpe": round(z / math.sqrt(sessions) * math.sqrt(252), 4)}
    return out


def cmd_power(a) -> int:
    proto = C.load_json(C.PROTOCOL_PATH)
    alpha = proto["multiplicity"]["family_alpha"] / proto["multiplicity"]["m"]
    lo, hi = proto["segments"]["post_publication"]["dates"]
    sessions = sum(1 for s, _ in C.calendar() if lo <= s <= hi)
    fired, longs = defaultdict(int), defaultdict(int)
    with open(C.PRIVATE / "triggers.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["segment"] != "post_publication" or r["trigger_minute"] == "":
                continue
            fired[r["d"]] += 1
            longs[r["d"]] += int(r["dirn"] == "1")
    res = power_table(fired, longs, sessions, alpha, a.effect)
    res["alpha_one_sided_worst_holm"] = alpha
    res["target_effect_R"] = a.effect
    central = [row for row in res["combined"]["table"] if row["sd_R"] == 2.0 and row["rho"] == 0.02][0]
    res["n_min_trades"] = central["n_required_for_effect"]
    res["n_min_basis"] = "sd 2.0 R, rho 0.02, effect +0.08 R, one-sided alpha 0.05/3, power 0.8"
    res["inputs"] = {"triggers_sha256": C.sha256_file(C.PRIVATE / "triggers.csv"), "label": "HIST counts only"}
    print(json.dumps(res, indent=1, sort_keys=True))
    C.write_private_json(C.PRIVATE / "power.json", res)
    return 0


# ------------------------------------------------------------------ statistics

def cluster_sums(rows, key_session, value):
    sums, counts = defaultdict(float), defaultdict(int)
    for r in rows:
        s = key_session(r)
        sums[s] += value(r)
        counts[s] += 1
    keys = sorted(sums)
    return [sums[k] for k in keys], [counts[k] for k in keys]


def bootstrap_mean(sums, counts, B: int, seed: int):
    """Session-clustered bootstrap of a ratio mean sum(x)/n. Returns (mean, p_one_sided_gt0, lo, hi)."""
    if not counts or sum(counts) == 0:
        return None, None, None, None
    mean = math.fsum(sums) / sum(counts)
    rng = random.Random(seed)
    k = len(sums)
    idx = range(k)
    reps = []
    for _ in range(B):
        pick = rng.choices(idx, k=k)
        n = sum(counts[i] for i in pick)
        reps.append(math.fsum(sums[i] for i in pick) / n if n else 0.0)
    exceed = sum(1 for m in reps if m - mean >= mean)
    reps.sort()
    return mean, (1 + exceed) / (B + 1), reps[int(0.025 * (B - 1))], reps[int(math.ceil(0.975 * (B - 1)))]


def bootstrap_ratio(num, den, B: int, seed: int):
    """Clustered bootstrap of sum(num)/sum(den) (per-session sums). Returns (ratio, lo, hi)."""
    if not den or math.fsum(den) == 0:
        return None, None, None
    ratio = math.fsum(num) / math.fsum(den)
    rng = random.Random(seed)
    k = len(num)
    reps = []
    for _ in range(B):
        pick = rng.choices(range(k), k=k)
        d = math.fsum(den[i] for i in pick)
        reps.append(math.fsum(num[i] for i in pick) / d if d else 0.0)
    reps.sort()
    return ratio, reps[int(0.025 * (B - 1))], reps[int(math.ceil(0.975 * (B - 1)))]


def holm(pvals: dict, alpha: float) -> dict:
    """Holm step-down: {id: (adjusted_p, rejected)}."""
    order = sorted(pvals, key=lambda k: pvals[k])
    m = len(order)
    out, running, stop = {}, 0.0, False
    for j, k in enumerate(order):
        adj = min(1.0, (m - j) * pvals[k])
        running = max(running, adj)
        rejected = (not stop) and pvals[k] <= alpha / (m - j)
        if not rejected:
            stop = True
        out[k] = (running, rejected)
    return out


def portfolio(trades, sessions, fees, model, sizing, start=25000.0):
    """Daily compounded book over `sessions` (all sessions of the period, no-trade days included)."""
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["d"]].append(t)
    eq, peak, mdd, rets, wins, n = start, start, 0.0, [], 0, 0
    for d in sessions:
        pnl = 0.0
        for t in by_day.get(d, []):
            ef, xf, atr, dirn, slots = t["entry_fill"], t["exit_fill"], t["atr14"], t["dirn"], t["slots"]
            sh = S.paper_shares(eq, ef, atr, slots) if sizing == "paper" else S.unlevered_shares(eq, ef, slots)
            p = S.net_pnl(dirn, sh, ef, xf, S.trade_costs(model, fees, d, dirn, sh, ef, xf))
            pnl += p
            wins += p > 0
            n += 1
        r = pnl / eq
        rets.append(r)
        eq += pnl
        peak = max(peak, eq)
        mdd = max(mdd, 1 - eq / peak)
    N = len(rets)
    mu = math.fsum(rets) / N if N else 0.0
    sd = math.sqrt(math.fsum((x - mu) ** 2 for x in rets) / (N - 1)) if N > 1 else 0.0
    return {"sessions": N, "trades": n, "end_equity": eq, "total_return": eq / start - 1,
            "cagr": (eq / start) ** (252 / N) - 1 if N and eq > 0 else None, "vol_annual": sd * math.sqrt(252),
            "sharpe": mu / sd * math.sqrt(252) if sd > 0 else None, "max_drawdown": mdd,
            "worst_day": min(rets) if rets else None, "positive_day_share": sum(1 for x in rets if x > 0) / N if N else None,
            "trade_win_rate": wins / n if n else None, "mean_daily": mu}, rets


def read_trades(population):
    path = C.PRIVATE / f"trades-{population}.csv.gz"
    ints = {"dirn", "rank", "slots", "entry_minute", "exit_minute", "gap_entry"}
    strs = {"d", "segment", "symbol", "model", "exit_reason", "ssr_flag"}
    with gzip.open(path, "rt", newline="") as f:
        for r in csv.DictReader(f):
            yield {k: (v if k in strs else int(v) if k in ints else float(v)) for k, v in r.items()}


def leg_filter(leg):
    return {"combined": lambda t: True, "long": lambda t: t["dirn"] > 0, "short": lambda t: t["dirn"] < 0}[leg]


def cmd_run(a) -> int:
    proto = C.require_frozen(C.PROTOCOL_PATH, a.protocol_sha256)
    B, seed = proto["statistics"]["bootstrap"]["B"], proto["statistics"]["bootstrap"]["seed"]
    fees = C.load_json(C.FEES_PATH)
    cal = [s for s, _ in C.calendar()]
    periods = {"post_publication": tuple(proto["segments"]["post_publication"]["dates"]),
               "reproduction": tuple(proto["segments"]["reproduction"]["dates"])}
    periods.update({f"reproduction_{k}": tuple(v) for k, v in proto["segments"]["reproduction"]["report_subperiods"].items()})
    trades = list(read_trades("selected"))
    res = {"protocol_id": proto["id"], "protocol_sha256": a.protocol_sha256, "label": "HIST", "per_trade": {},
           "portfolio": {}, "break_even": {}, "items": {}, "descriptive": {}}
    for pname, (lo, hi) in periods.items():
        sess = [s for s in cal if lo <= s <= hi]
        for model in ("F0", "F1", "F2"):
            tm = [t for t in trades if t["model"] == model and lo <= t["d"] <= hi]
            for leg in LEGS:
                tl = [t for t in tm if leg_filter(leg)(t)]
                sums, counts = cluster_sums(tl, lambda t: t["d"], lambda t: t["net_R"])
                b = B if pname == "post_publication" else max(1000, B // 10)
                mean, p, ci_lo, ci_hi = bootstrap_mean(sums, counts, b, seed)
                res["per_trade"][f"{pname}|{model}|{leg}"] = {
                    "n": len(tl), "sessions": len(sums), "mean_net_R": mean, "p_one_sided": p, "ci95": [ci_lo, ci_hi],
                    "bootstrap_B": b, "win_rate": sum(1 for t in tl if t["net_R"] > 0) / len(tl) if tl else None,
                    "stop_share": sum(1 for t in tl if t["exit_reason"] != "eod") / len(tl) if tl else None}
            for sizing in ("paper", "1x"):
                stats, rets = portfolio(tm, sess, fees, model, sizing)
                res["portfolio"][f"{pname}|{model}|{sizing}"] = stats
                if pname == "post_publication" and model == "F1" and sizing == "paper":
                    mean, p, ci_lo, ci_hi = bootstrap_mean(rets, [1] * len(rets), B, seed)
                    res["items"]["ORB-3"] = {"mean_daily": mean, "p_one_sided": p, "ci95": [ci_lo, ci_hi]}
        # break-even per-side cost vs measured, F1 bases
        tf = [t for t in trades if t["model"] == "F1" and lo <= t["d"] <= hi]
        if tf:
            num, _ = cluster_sums(tf, lambda t: t["d"], lambda t: t["gross_R"])
            den, _ = cluster_sums(tf, lambda t: t["d"], lambda t: (t["entry_base"] + t["exit_base"]) / S.r_per_share(t["atr14"]))
            c, c_lo, c_hi = bootstrap_ratio(num, den, max(1000, B // 10), seed)
            meas = [(abs(t["entry_fill"] - t["entry_base"]) / t["entry_base"] + abs(t["exit_fill"] - t["exit_base"]) / t["exit_base"]
                     + (S.trade_costs("F1", fees, t["d"], t["dirn"], 1.0, t["entry_fill"], t["exit_fill"])
                        / (t["exit_fill"] if t["dirn"] > 0 else t["entry_fill"]))) for t in tf]
            res["break_even"][pname] = {"per_side_fraction": c, "round_trip_bps": 2e4 * c if c is not None else None,
                                        "round_trip_bps_ci95": [2e4 * c_lo, 2e4 * c_hi] if c_lo is not None else None,
                                        "measured_round_trip_bps_mean": 1e4 * math.fsum(meas) / len(meas)}
    post = res["per_trade"]
    res["items"]["ORB-1"] = {k: post["post_publication|F1|combined"][k] for k in ("n", "mean_net_R", "p_one_sided", "ci95")}
    res["items"]["ORB-2"] = {k: post["post_publication|F1|long"][k] for k in ("n", "mean_net_R", "p_one_sided", "ci95")}
    alpha = proto["multiplicity"]["family_alpha"]
    h = holm({k: v["p_one_sided"] if v["p_one_sided"] is not None else 1.0 for k, v in res["items"].items()}, alpha)
    for k, (adj, rej) in h.items():
        res["items"][k].update({"holm_adjusted_p": adj, "rejected": rej})
    n_min = proto["sample_size"]["n_min_trades"]
    n_post = post["post_publication|F1|combined"]["n"]
    enough = n_min is not None and n_post >= n_min
    f2 = post["post_publication|F2|combined"]["mean_net_R"]
    f2l = post["post_publication|F2|long"]["mean_net_R"]
    f2s = res["portfolio"]["post_publication|F2|paper"]["sharpe"]
    res["verdicts"] = {
        "sample_gate": {"n_post_F1": n_post, "n_min": n_min, "met": enough},
        "combined": "inconclusive" if not enough else ("supported" if res["items"]["ORB-1"]["rejected"] and f2 is not None and f2 > 0 else "not_supported"),
        "long_only": "inconclusive" if not enough else ("supported" if res["items"]["ORB-2"]["rejected"] and f2l is not None and f2l > 0 else "not_supported"),
        "portfolio": "inconclusive" if not enough else ("supported" if res["items"]["ORB-3"]["rejected"] and f2s is not None and f2s > 0 else "not_supported")}
    # descriptive: Rule 201 sensitivity for the short leg (post-publication, F1)
    tf = [t for t in trades if t["model"] == "F1" and t["segment"] == "post_publication"]
    ex = [t for t in tf if not (t["dirn"] < 0 and t["ssr_flag"] == "1")]
    res["descriptive"]["ssr_excluded_post_F1_combined_mean_R"] = math.fsum(t["net_R"] for t in ex) / len(ex) if ex else None
    res["descriptive"]["ssr_flagged_shorts_post"] = sum(1 for t in tf if t["dirn"] < 0 and t["ssr_flag"] == "1")
    base_path = C.PRIVATE / "trades-base.csv.gz"
    if base_path.exists():
        base = list(read_trades("base"))
        for pname, (lo, hi) in periods.items():
            tb = [t for t in base if lo <= t["d"] <= hi]
            buckets = {"relvol_lt_1": lambda t: t["relvol"] < 1, "relvol_ge_1": lambda t: t["relvol"] >= 1,
                       "relvol_ge_30": lambda t: t["relvol"] >= 30}
            res["descriptive"][f"fig4|{pname}|F0"] = {
                k: {"n": len(x), "mean_net_R": math.fsum(t["net_R"] for t in x) / len(x) if x else None}
                for k, f in buckets.items() for x in [[t for t in tb if f(t)]]}
            sess = [s for s in cal if lo <= s <= hi]
            res["descriptive"][f"table1|{pname}|F0|paper"] = portfolio(tb, sess, fees, "F0", "paper")[0]
    out = C.PRIVATE / "results.json"
    sha = C.write_private_json(out, res)
    print(json.dumps({"items": res["items"], "verdicts": res["verdicts"], "sha256": sha}, indent=1, sort_keys=True))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("power")
    p.add_argument("--effect", type=float, default=0.08)
    r = sub.add_parser("run")
    r.add_argument("--protocol-sha256", default=None)
    a = ap.parse_args(argv)
    return {"power": cmd_power, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
