"""Evaluate protocol.json (mover-early-entry-v1-20260924) on features.py outcomes; deterministic.

  python evaluate.py dev_val --outcomes-dev F --outcomes-val F --cost-table cost-table.json \
      --daily DAILY --benchmarks DIR --audit AUDIT_RESULTS --out RESULTS.json [--summary SUMMARY.json]
  python evaluate.py holdout --dev-val RESULTS.json --outcomes-holdout F --cost-table cost-table.json \
      --daily DAILY --benchmarks DIR --audit AUDIT_RESULTS --out HOLDOUT.json

dev_val never reads a holdout session. Results hold aggregates only (no symbol or date rows).
Clarifications are cited by id (clarifications.json). Returns are quantised to 1e-6 (C11) so every
sum is exact and every run reproduces the files byte for byte.
"""
from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse  # noqa: E402
import csv  # noqa: E402
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
import rules as R  # noqa: E402
from sessions_io import official_price  # noqa: E402

PROTOCOL_BYTES = (HERE / "protocol.json").read_bytes()
PROTOCOL = json.loads(PROTOCOL_BYTES)
SPLITS = {k: tuple(v) for k, v in PROTOCOL["splits"].items()}
SPLIT_OF = {"dev": "development", "val": "validation", "holdout": "holdout"}
B, BLOCK = 20_000, 5
SEED = int.from_bytes(hashlib.sha256(PROTOCOL["id"].encode()).digest()[:8], "big")
Q = 1e6
REF_NOTIONAL = 20_000.0
VARIANTS = (("primary", "alpaca", 1.0), ("stress", "alpaca", 2.0), ("ibkr", "ibkr", 1.0))
RULES = [(t, g, v, n) for t in R.TIMES for g in R.GAINS for v in R.VOLUMES for n in R.NEWS]
RULE_EXITS = [(t, g, v, n, x) for (t, g, v, n) in RULES for x in R.EXITS]
RUNGS = (1, 2, 4)
PRICE_LABELS = ("<2", "2-5", "5-20", ">=20")
V_LABELS = ("250k-1M", "1-5M", ">=5M")
CONC_LABELS = ("1", "2-5", "6-20", ">20")


def rule_id(t, g, v, n, x=None):
    base = f"{t}|G{g:.2f}|V{int(v)}|{n}"
    return base if x is None else f"{base}|{x}"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rnd(x, nd=8):
    if x is None:
        return None
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def quantise(x):
    return np.round(np.asarray(x, dtype=float) * Q)


# ---------------------------------------------------------------- statistics


def replicate_counts(n_sessions: int, seed: int = SEED, b: int = B, block: int = BLOCK):
    """C11: circular block bootstrap session multiplicities, shape (b, n_sessions)."""
    rng = np.random.default_rng(seed)
    nblocks = -(-n_sessions // block)
    starts = rng.integers(0, n_sessions, size=(b, nblocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n_sessions
    idx = idx.reshape(b, nblocks * block)[:, :n_sessions]
    flat = (np.arange(b)[:, None] * n_sessions + idx).ravel()
    return np.bincount(flat, minlength=b * n_sessions).reshape(b, n_sessions).astype(float)


def bootstrap(C, sums, counts):
    """Per column: p = (1 + #{mean_b <= 0}) / (B + 1), and the 5th percentile of replicate means."""
    s = C @ sums
    n = C @ counts
    le = (n == 0) | (s <= 0)
    p = (1 + le.sum(axis=0)) / (C.shape[0] + 1)
    means = np.where(n > 0, s / np.where(n > 0, n, 1) / Q, -np.inf)
    means.sort(axis=0)
    return p, means[int(math.floor(0.05 * (C.shape[0] - 1)))]


def bh(pvals):
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    adj = np.empty(m)
    run = 1.0
    order = np.lexsort((np.arange(m), p))
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        run = min(run, p[i] * m / rank)
        adj[i] = run
    return adj


def by(pvals):
    m = len(pvals)
    return np.minimum(1.0, bh(pvals) * sum(1.0 / i for i in range(1, m + 1))) if m else np.asarray(pvals, dtype=float)


def holm(pvals):
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(np.lexsort((np.arange(m), p))):
        run = max(run, min(1.0, p[i] * (m - rank)))
        adj[i] = run
    return adj


def two_way_p(r, sess, sym):
    """C14: one-sided p for mean > 0 with session and symbol clustering (one trade per symbol-day)."""
    n = len(r)
    if n < 2:
        return None
    u = (r - r.mean()) / n
    vs = float(np.square(np.bincount(sess, weights=u)).sum())
    vy = float(np.square(np.bincount(sym, weights=u)).sum())
    var = vs + vy - float(np.square(u).sum())
    if var <= 0:
        var = max(vs, vy)
    if var <= 0:
        return None
    return 0.5 * math.erfc(float(r.mean()) / math.sqrt(var) / math.sqrt(2))


def spearman(x, y):
    def ranks(a):
        a = np.asarray(a, dtype=float)
        order = np.argsort(a, kind="mergesort")
        srt = a[order]
        rk = np.empty(len(a))
        i = 0
        while i < len(a):
            j = i
            while j + 1 < len(a) and srt[j + 1] == srt[i]:
                j += 1
            rk[order[i:j + 1]] = (i + j) / 2 + 1
            i = j + 1
        return rk
    if len(x) < 3:
        return None
    return float(np.corrcoef(ranks(x), ranks(y))[0, 1])


def summarise(net_q, gross, sess, n_sessions, codes):
    """C12/C13 metrics for one trade set (net_q quantised; sess are calendar indices)."""
    n = len(net_q)
    if not n:
        return {"trades": 0}
    r = net_q / Q
    total = float(net_q.sum())
    ssum = np.bincount(sess, weights=net_q, minlength=n_sessions)
    scnt = np.bincount(sess, minlength=n_sessions)
    active = np.flatnonzero(scnt)
    top5 = active[np.lexsort((active, -ssum[active]))][:5]
    keep = ~np.isin(sess, top5)
    lo, hi = np.percentile(r, [1, 99])
    k = max(1, math.ceil(0.01 * n))
    gains, losses = float(r[r > 0].sum()), float(-r[r < 0].sum())
    out = {"trades": n, "mean": rnd(total / n / Q), "median": rnd(np.median(r)),
           "winsorised_mean": rnd(np.clip(r, lo, hi).mean()),
           "mean_without_top5_sessions": rnd(float(net_q[keep].sum()) / int(keep.sum()) / Q) if keep.any() else None,
           "mean_of_session_means": rnd((ssum[active] / scnt[active]).mean() / Q), "sessions_with_trades": int(len(active)),
           "win_rate": rnd((r > 0).mean()), "p5": rnd(np.percentile(r, 5)), "p95": rnd(np.percentile(r, 95)),
           "profit_factor": rnd(gains / losses) if losses > 0 else None,
           "top1pct_share": rnd(float(np.sort(net_q)[-k:].sum()) / total) if total > 0 else None,
           "gross_mean": rnd(np.mean(gross))}
    for name, (labels, code) in codes.items():
        cnt = np.bincount(code, minlength=len(labels))
        sm = np.bincount(code, weights=net_q, minlength=len(labels))
        out[name] = {labels[i]: [int(cnt[i]), rnd(sm[i] / cnt[i] / Q)] for i in range(len(labels)) if cnt[i]}
    return out


# ---------------------------------------------------------------- inputs


def read_outcomes(path: Path, split: str):
    meta = json.loads(Path(str(path) + ".meta.json").read_text())
    if meta["mode"] != "outcomes" or meta["split"] != split or meta.get("max_sessions"):
        raise SystemExit(f"{path} is not a full outcomes file for {split}")
    h = hashlib.sha256()
    rows = []
    with gzip.open(path, "rb") as f:
        for line in f:
            h.update(line)
            rows.append(json.loads(line))
    if h.hexdigest() != meta["content_sha256"]:
        raise SystemExit(f"{path} content hash mismatch")
    lo, hi = SPLITS[SPLIT_OF[split]]
    if any(not (lo <= r["session"] <= hi) for r in rows):
        raise SystemExit(f"{path} has a session outside {split}")
    return rows, meta


class Spy:
    """D4: SPY adjusted closes from 2019-11-01 up to the stage's last session; the regime factor (C4) and the calendar."""

    def __init__(self, daily_path: Path, last: str):
        import duckdb
        rows = duckdb.connect().execute(
            f"""SELECT CAST(session_date AS VARCHAR), all_c FROM read_parquet('{daily_path}')
                WHERE symbol = 'SPY' AND session_date >= DATE '2019-11-01' AND session_date <= DATE '{last}'
                ORDER BY session_date""").fetchall()
        self.days = [d for d, _ in rows]
        self.pos = {d: i for i, d in enumerate(self.days)}
        self.closes = np.array([c for _, c in rows], dtype=float)
        lr = np.diff(np.log(self.closes))
        self.vol = np.full(len(self.closes), np.nan)
        for i in range(20, len(self.closes)):
            self.vol[i] = np.std(lr[i - 20:i], ddof=1)

    def calendar(self, split: str):
        lo, hi = SPLITS[split]
        return [d for d in self.days if lo <= d <= hi]

    def regime(self, sessions):
        out = {}
        for s in sessions:
            i = self.pos[s]
            if i < 272:
                raise SystemExit(f"SPY history too short for {s}")
            p = i - 1
            up = self.closes[p] > self.closes[p - 19:p + 1].mean()
            calm = self.vol[p] < np.median(self.vol[p - 251:p + 1])
            out[s] = 1.0 if (up and calm) else 0.5
        return out


def iwm_open_to_close(bench_dir: Path, cal):
    """IWM official open-to-close per calendar session; sessions without both prints are counted."""
    import benchmarks
    days = benchmarks.load(bench_dir)
    out, missing = {}, 0
    for d in cal:
        o, _ = official_price(days.get(d), "o")
        c, _ = official_price(days.get(d), "c")
        if o and c:
            out[d] = c / o - 1
        else:
            missing += 1
    return out, missing


class Costs:
    def __init__(self, table: dict):
        self.cells = table["cells"]

    def half_spread(self, day, ts, price, cum_dv):
        tb = R.time_bucket(day, ts)
        if tb is None:
            raise ValueError("timestamp outside the cost buckets")
        return self.cells[f"{tb}|{R.price_tier(price)}|{R.dv_tier(cum_dv)}"]["half_spread"]

    def sides(self, day, entry, entry_ts, source, entry_cum_dv, exit_px, exit_ts, exit_cum_dv):
        hs = self.half_spread(day, entry_ts, entry, entry_cum_dv)
        c_in = 0.5 * hs if source == "opening_auction" else 1.25 * hs
        return c_in, 1.25 * self.half_spread(day, exit_ts, exit_px, exit_cum_dv)


# ---------------------------------------------------------------- entries


class Entries:
    """Arrays over the (symbol-day, time) entries the loosest rule fires, with costs and net returns."""

    def __init__(self, rows, costs: Costs, iwm: dict, cal: list):
        self.cal = cal
        cidx = {s: i for i, s in enumerate(cal)}
        syms = sorted({r["symbol"] for r in rows})
        yidx = {y: i for i, y in enumerate(sorted({r["session"][:4] for r in rows}))}
        self.years = sorted(yidx, key=yidx.get)
        sidx = {s: i for i, s in enumerate(syms)}
        cols = defaultdict(list)
        fired = defaultdict(list)  # C24: every loosest-rule fire, filled or not
        for r in rows:
            for ti, t in enumerate(R.TIMES):
                row = r["t"][t]
                if not row.get("loosest"):
                    continue
                fired["time"].append(ti)
                fired["sess"].append(cidx[r["session"]])
                fired["symbol"].append(r["symbol"])
                fired["price"].append(row["price"])
                fired["dv"].append(row["dv"])
                fired["gain"].append(row["gain"])
                fired["news"].append(bool(row["news120"]))
                fired["news600"].append(bool(row["news600"]))
                fired["entry_index"].append(len(cols["time"]) if row.get("entry") is not None else -1)
                if row.get("entry") is None:
                    continue
                day, e = r["session"], row["entry"]
                cols["time"].append(ti)
                cols["sess"].append(cidx[day])
                cols["sym"].append(sidx[r["symbol"]])
                cols["symbol"].append(r["symbol"])
                cols["year"].append(yidx[day[:4]])
                cols["price"].append(row["price"])
                cols["dv"].append(row["dv"])
                cols["gain"].append(row["gain"] if row["gain"] is not None else np.nan)
                cols["news"].append(bool(row["news120"]))
                cols["news600"].append(bool(row["news600"]))
                cols["entry"].append(e)
                cols["bar_dv"].append(row["entry_bar_dv"] if row["entry_bar_dv"] is not None else np.nan)
                cols["halt"].append(bool(row["halt"]))
                cols["fallback_row"].append(r["ref_source"] == "daily_bar_close" or r.get("official_close") is None)
                cols["supplement"].append(bool(r.get("supplement")))
                oo, oc = r.get("official_open"), r.get("official_close")
                cols["open_to_close"].append(oc / oo - 1 if (oo and oc) else np.nan)
                cols["iwm"].append(iwm.get(day, np.nan))
                sec, taf, cap = R.fee_rates(day)
                cols["sec"].append(sec)
                cols["taf"].append(taf)
                cols["cap"].append(cap)
                cols["day"].append(day)
                for x in R.EXITS:
                    px, ts, fb, cum = row["exits"][x]
                    c_in, c_out = costs.sides(day, e, row["entry_ts"], row["entry_source"], row["entry_cum_dv"], px, ts, cum)
                    cols[f"{x}_px"].append(px)
                    cols[f"{x}_fb"].append(bool(fb))
                    cols[f"{x}_cin"].append(c_in)
                    cols[f"{x}_cout"].append(c_out)
                    p = row.get("placebo") or {}
                    if p.get("entry") is not None:
                        ppx, pts, _, pcum = p["exits"][x]
                        pci, pco = costs.sides(day, p["entry"], p["entry_ts"], p["entry_source"], p["entry_cum_dv"], ppx, pts, pcum)
                        cols[f"{x}_placebo"].append(R.net_return(p["entry"], ppx, pci, pco, day, REF_NOTIONAL))
                    else:
                        cols[f"{x}_placebo"].append(np.nan)
        self.n = len(cols["time"])
        self.symbol = cols.pop("symbol")
        self.day = cols.pop("day")
        for k, v in cols.items():
            dtype = int if k in ("time", "sess", "sym", "year") else (bool if k in ("news", "news600", "halt", "fallback_row", "supplement") or k.endswith("_fb") else float)
            setattr(self, k.replace("-", "_"), np.array(v, dtype=dtype) if v else np.zeros(0, dtype=dtype))
        self.f_symbol = fired.pop("symbol", [])
        for k, v in fired.items():
            dtype = int if k in ("time", "sess", "entry_index") else (bool if k in ("news", "news600") else float)
            setattr(self, "f_" + k, np.array(v, dtype=dtype) if v else np.zeros(0, dtype=dtype))
        self.n_fired = len(self.f_symbol)
        self.net = {}
        for x in R.EXITS:
            for name, broker, mult in VARIANTS:
                self.net[(x, name)] = R.net_return_np(self.entry, getattr(self, f"{x}_px"), getattr(self, f"{x}_cin"),
                                                      getattr(self, f"{x}_cout"), self.sec, self.taf, self.cap, REF_NOTIONAL, broker, mult)
        self.ptier = np.searchsorted(R.PRICE_TIERS, self.price, side="right") if self.n else np.zeros(0, dtype=int)
        self.vtier = np.searchsorted(R.DV_TIERS, self.dv, side="right") if self.n else np.zeros(0, dtype=int)

    def mask(self, t, g, v, n, fired=False):
        """Filled entries (or, with fired=True, every fire) of a rule; n may also be 'news600' (sensitivity)."""
        pre = "f_" if fired else ""
        m = ((getattr(self, pre + "time") == R.TIMES.index(t)) & (getattr(self, pre + "gain") >= g - R.GAIN_EPS)
             & (getattr(self, pre + "dv") >= v) & (getattr(self, pre + "price") >= R.MIN_PRICE))
        if n == "news_before_t":
            m &= getattr(self, pre + "news")
        elif n == "news600":
            m &= getattr(self, pre + "news600")
        return np.flatnonzero(m)

    def break_even(self, idx, x):
        """C8."""
        if not len(idx):
            return None
        args = (self.entry[idx], getattr(self, f"{x}_px")[idx], getattr(self, f"{x}_cin")[idx], getattr(self, f"{x}_cout")[idx],
                self.sec[idx], self.taf[idx], self.cap[idx], REF_NOTIONAL)

        def mean_at(k):
            return float(R.net_return_np(*args, "alpaca", k).mean())
        if mean_at(0.0) <= 0:
            return None
        lo, hi = 0.0, 1000.0
        if mean_at(hi) > 0:
            return hi
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if mean_at(mid) > 0 else (lo, mid)
        return lo


def top5_by_session(E: Entries, fidx):
    """C24: the five slots per session over every fire (dollar volume descending, then symbol), as entry
    indices; a fire without a fill keeps its slot as -1 (zero P&L, counted in the desired notional)."""
    order = sorted(fidx.tolist(), key=lambda i: (E.f_sess[i], -E.f_dv[i], E.f_symbol[i]))
    out = defaultdict(list)
    for i in order:
        s = int(E.f_sess[i])
        if len(out[s]) < 5:
            out[s].append((int(E.f_entry_index[i]), float(E.f_dv[i]), float(E.f_price[i])))
    return out


def simulate(E: Entries, top5, x, regime, rung, start_equity=100_000.0):
    """C15: the leveraged, capacity-capped 5-position portfolio for one rule-exit."""
    equity = peak = start_equity
    cooldown, served, ruin = 0, False, None
    path, rets, desired_total, filled_total = [], [], 0.0, 0.0
    taken_sess, taken_net = [], []
    px, cin, cout = getattr(E, f"{x}_px"), getattr(E, f"{x}_cin"), getattr(E, f"{x}_cout")
    for si, s in enumerate(E.cal):
        if ruin is not None:  # equity exhausted: no margin model, trading stops
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
        lev = min(4.0, rung * regime[s] * (1.0 if dd <= 0.10 else 0.5))
        pnl = 0.0
        for i, f_dv, f_price in top5.get(si, ()):
            li = min(lev, 1.0) if f_price < 5 else lev
            desired = equity * li / 5
            desired_total += desired
            if i < 0:  # C24: fired but not filled
                continue
            cap = 0.01 * E.dv[i]
            if not math.isnan(E.bar_dv[i]):
                cap = min(cap, 0.10 * E.bar_dv[i])
            notional = min(desired, cap)
            if notional <= 0:
                continue
            filled_total += notional
            net = R.net_return(float(E.entry[i]), float(px[i]), float(cin[i]), float(cout[i]), E.day[i], notional)
            pnl += net * notional * (1 + float(cin[i]))  # net is a return on the basis (C6)
            taken_sess.append(si)
            taken_net.append(net)
        rets.append(pnl / equity)
        equity += pnl
        if equity <= 0:
            equity, ruin = 0.0, s
        peak = max(peak, equity)
        path.append(equity)
    n = len(E.cal)
    eq = np.array(path)
    run_peak = np.maximum.accumulate(np.concatenate(([start_equity], eq)))[1:]
    mdd = float(((run_peak - eq) / run_peak).max()) if n else 0.0
    ruined = ruin is not None
    cagr = (equity / start_equity) ** (252 / n) - 1 if (n and equity > 0) else -1.0
    stats = {"final_equity": rnd(equity, 2), "cagr": rnd(cagr), "max_drawdown": rnd(mdd), "worst_session": rnd(min(rets)) if rets else None,
             "share_sessions_loss_over_5pct": rnd(np.mean(np.array(rets) < -0.05)) if rets else None,
             "trades_taken": len(taken_net), "fill_ratio": rnd(filled_total / desired_total) if desired_total else None,
             "ruined": ruined}
    return stats, np.array(taken_sess, dtype=int), quantise(taken_net)


# ---------------------------------------------------------------- per split


def evaluate_split(E: Entries, regime, portfolio: bool = True, only=None):
    """Per rule-exit metrics; `only` limits the rule-exits evaluated (the holdout's at most five)."""
    S = len(E.cal)
    C = replicate_counts(S)
    out, cols, cnts, keys = {}, [], [], []
    tops = {}
    for (t, g, v, n) in RULES:
        if only is not None and not any(rule_id(t, g, v, n, x) in only for x in R.EXITS):
            continue
        idx = E.mask(t, g, v, n)
        fidx = E.mask(t, g, v, n, fired=True)
        fires_per_session = np.bincount(E.f_sess[fidx], minlength=S)  # C13: fires, filled or not
        conc_n = fires_per_session[E.sess[idx]] if len(idx) else np.zeros(0, dtype=int)
        conc = np.searchsorted([1, 5, 20], conc_n, side="left") if len(idx) else conc_n
        codes = {"by_year": (E.years, E.year[idx]), "by_price_tier": (PRICE_LABELS, E.ptier[idx]),
                 "by_v_tier": (V_LABELS, E.vtier[idx]), "by_concurrency": (CONC_LABELS, conc)}
        top5 = top5_by_session(E, fidx) if portfolio else None
        tops[rule_id(t, g, v, n)] = top5
        for x in R.EXITS:
            rid = rule_id(t, g, v, n, x)
            if only is not None and rid not in only:
                continue
            nets = {name: quantise(E.net[(x, name)][idx]) for name, _, _ in VARIANTS}
            gross = getattr(E, f"{x}_px")[idx] / E.entry[idx] - 1
            m = summarise(nets["primary"], gross, E.sess[idx], S, codes)
            if len(idx):
                m["mean_stress"] = rnd(float(nets["stress"].sum()) / len(idx) / Q)
                m["mean_ibkr"] = rnd(float(nets["ibkr"].sum()) / len(idx) / Q)
                nf = ~E.fallback_row[idx]
                m["without_fallback_rows"] = [int(nf.sum()), rnd(float(nets["primary"][nf].sum()) / int(nf.sum()) / Q) if nf.any() else None]
                ns = ~E.supplement[idx]
                m["without_premarket_supplement_rows"] = [int(ns.sum()), rnd(float(nets["primary"][ns].sum()) / int(ns.sum()) / Q) if ns.any() else None]
                m["halt_flagged"] = int(E.halt[idx].sum())
                m["close_fallback_exits"] = int(getattr(E, f"{x}_fb")[idx].sum())
                iw = ~np.isnan(E.iwm[idx])
                m["excess_vs_iwm_open_to_close_proxy"] = rnd((nets["primary"][iw] / Q - E.iwm[idx][iw]).mean()) if iw.any() else None
                pl = getattr(E, f"{x}_placebo")[idx]
                pl = pl[~np.isnan(pl)]
                m["placebo_t_plus_30"] = [int(len(pl)), rnd(quantise(pl).sum() / len(pl) / Q) if len(pl) else None]
                oc = E.open_to_close[idx]
                oc = oc[~np.isnan(oc)]
                m["fired_set_official_open_to_close"] = [int(len(oc)), rnd(oc.mean()) if len(oc) else None]
                m["break_even_cost_multiple"] = rnd(E.break_even(idx, x), 4)
                m["p_two_way_cluster"] = rnd(two_way_p(nets["primary"] / Q, E.sess[idx], E.sym[idx]), 10)
            out[rid] = m
            for name, _, _ in VARIANTS:
                cols.append(np.bincount(E.sess[idx], weights=nets[name], minlength=S))
                cnts.append(np.bincount(E.sess[idx], minlength=S).astype(float))
                keys.append((rid, name))
            if n == "news_before_t":  # the preregistered 600 s news-lag sensitivity (not used for selection)
                i6 = E.mask(t, g, v, "news600")
                n6 = quantise(E.net[(x, "primary")][i6])
                out[rid]["news600_sensitivity"] = {"trades": int(len(i6)), "mean": rnd(float(n6.sum()) / len(i6) / Q) if len(i6) else None}
                cols.append(np.bincount(E.sess[i6], weights=n6, minlength=S))
                cnts.append(np.bincount(E.sess[i6], minlength=S).astype(float))
                keys.append((rid, "news600"))
            if portfolio:
                out[rid]["portfolio"] = {}
                for rung in RUNGS:
                    stats, ts, tn = simulate(E, top5, x, regime, rung)
                    out[rid]["portfolio"][str(rung)] = stats
                    cols.append(np.bincount(ts, weights=tn, minlength=S))
                    cnts.append(np.bincount(ts, minlength=S).astype(float))
                    keys.append((rid, f"portfolio_{rung}"))
                    stats["taken_mean_net"] = rnd(float(tn.sum()) / len(tn) / Q) if len(tn) else None
                out[rid]["portfolio"]["capacity_rung1"] = {str(int(eq)): simulate(E, top5, x, regime, 1, eq)[0]
                                                           for eq in (10_000.0, 100_000.0, 1_000_000.0)}
    Smat, Nmat = np.stack(cols, axis=1), np.stack(cnts, axis=1)
    for lo in range(0, Smat.shape[1], 256):
        p, lb = bootstrap(C, Smat[:, lo:lo + 256], Nmat[:, lo:lo + 256])
        for j, (rid, name) in enumerate(keys[lo:lo + 256]):
            if name.startswith("portfolio_"):
                out[rid]["portfolio"][name.split("_")[1]].update({"p": rnd(p[j], 10), "lower_bound": rnd(lb[j])})
            elif name == "news600":
                out[rid]["news600_sensitivity"].update({"p": rnd(p[j], 10), "lower_bound": rnd(lb[j])})
            else:
                suffix = "" if name == "primary" else f"_{name}"
                out[rid]["p" + suffix] = rnd(p[j], 10)
                out[rid]["lower_bound" + suffix] = rnd(lb[j])
    return out


# ---------------------------------------------------------------- capture, replication, gates


def basis_uncertain(r) -> bool:
    """D6: rows whose ref may be on the wrong price basis (the C23 daily-close fallback or a split day)."""
    return r["ref_source"] == "daily_bar_close" or bool(r["split"])


def capture(rows):
    rows = [r for r in rows if r.get("eventual_gain") is not None]
    tier = np.array([R.degree_tier_index(r["eventual_gain"]) for r in rows], dtype=int)
    labels = [R.tier_label(i) for i in range(len(R.DEGREE_TIERS))]
    out = {}
    for t in R.TIMES:
        price = np.array([r["t"][t]["price"] if r["t"][t]["price"] is not None else np.nan for r in rows], dtype=float)
        dv = np.array([r["t"][t]["dv"] for r in rows], dtype=float)
        gain = np.array([r["t"][t]["gain"] if r["t"][t]["gain"] is not None else np.nan for r in rows], dtype=float)
        news = np.array([bool(r["t"][t]["news120"]) for r in rows], dtype=bool)
        has = np.array([r["t"][t].get("entry") is not None and "exits" in r["t"][t] for r in rows], dtype=bool)
        to_close = np.array([r["t"][t]["exits"]["X1"][0] / r["t"][t]["entry"] - 1 if h else np.nan for r, h in zip(rows, has)])
        to_high = np.array([r["t"][t]["high"] / r["t"][t]["entry"] - 1 if h else np.nan for r, h in zip(rows, has)])
        for g in R.GAINS:
            for v in R.VOLUMES:
                elig = (price >= R.MIN_PRICE) & (dv >= v)
                base = elig & (gain >= g - R.GAIN_EPS)  # C25, as the trade-level rule
                for n in R.NEWS:
                    fired = base & news if n == "news_before_t" else base
                    cell = {}
                    for ti, lab in enumerate(labels):
                        tm = tier == ti
                        f, e = fired & tm, elig & tm
                        fe = f & has
                        cell[lab] = {"symbol_days": int(tm.sum()), "fired": int(f.sum()),
                                     "recall": rnd(f.sum() / tm.sum()) if tm.any() else None,
                                     "recall_among_price_volume_eligible": rnd(f.sum() / e.sum()) if e.any() else None,
                                     "median_gain_at_t": rnd(np.median(gain[f])) if f.any() else None,
                                     "median_gross_to_close": rnd(np.median(to_close[fe])) if fe.any() else None,
                                     "median_gross_to_session_high": rnd(np.median(to_high[fe])) if fe.any() else None}
                    out[rule_id(t, g, v, n)] = cell
    return out


def replication(rows):
    rows = [r for r in rows if r.get("eventual_gain") is not None and r["eventual_gain"] >= 1.0]
    g = [r["t"]["09:25"]["gain"] for r in rows]
    lead = sum(1 for x in g if x is not None and x >= 0.20 - R.GAIN_EPS)
    d = [(x, r["eventual_gain"]) for x, r in zip(g, rows) if x is not None]
    return {"tier_ge_1_symbol_days": len(rows), "share_gain_at_0925_ge_0_20": rnd(lead / len(rows)) if rows else None,
            "spearman_gain_at_0925_vs_eventual": rnd(spearman([a for a, _ in d], [b for _, b in d])) if d else None,
            "days_with_defined_gain_at_0925": len(d),
            "package_claim": "premarket leadership in 77% of >=100% gainers; premarket magnitude rho 0.04 (the package's definition, quoted beside this, not assumed identical)"}


def completeness(rows, meta):
    return {"sessions": meta["sessions"], "symbol_days": len(rows),
            "split_sessions_ever_incomplete_elsewhere": len(meta.get("split_sessions_ever_incomplete_elsewhere") or []),
            "zero_bar_symbol_days": sum(1 for r in rows if r["bars"] == 0),
            "ref_from_daily_bar_close": sum(1 for r in rows if r["ref_source"] == "daily_bar_close"),
            "ref_missing": sum(1 for r in rows if r["ref"] is None),
            "missing_official_open": sum(1 for r in rows if r["official_open"] is None),
            "missing_official_close": sum(1 for r in rows if not r["has_official_close"]),
            "eventual_gain_missing": sum(1 for r in rows if r.get("eventual_gain") is None),
            "split_days": sum(1 for r in rows if r["split"]), "days_after_gap_over_7": sum(1 for r in rows if r["gap_over_7"]),
            "daily_rows_missing": sum(1 for r in rows if r["daily_missing"]),
            "premarket_supplement_symbol_days": sum(1 for r in rows if r.get("supplement"))}


def coverage(audit_path: Path, candidate_paths, lo: str, hi: str):
    """C21, against the evaluated universe: the main list plus the D3 pre-market supplement."""
    cand = set()
    for path in candidate_paths:
        cand |= {(r["symbol"], r["session_date"]) for r in csv.DictReader(path.open(newline=""))}
    tiers = defaultdict(lambda: [0, 0])
    for e in json.loads(audit_path.read_text())["events"]:
        if e["verdict"] not in ("match", "recovered_match") or e.get("alpaca_gain_pct") is None:
            continue
        if e["alpaca_gain_pct"] < 20 or not (lo <= e["date"] <= hi):
            continue
        tier = R.degree_tier(e["alpaca_gain_pct"] / 100)
        tiers[tier][0] += 1
        tiers[tier][1] += int((e.get("symbol_used"), e["date"]) in cand or (e.get("ticker"), e["date"]) in cand)
    total, found = sum(v[0] for v in tiers.values()), sum(v[1] for v in tiers.values())
    return {"events": total, "present": found, "share": rnd(found / total) if total else None,
            "by_tier": {k: {"events": v[0], "present": v[1]} for k, v in sorted(tiers.items())},
            "survivorship_limited": bool(total and found / total < 0.95)}


# ---------------------------------------------------------------- stages


def check_inputs(a):
    """Frozen inputs and runtime (protocol inputs; C28 records what each check covers)."""
    import duckdb
    rt = PROTOCOL["inputs"]["runtime"]
    have = {"python": sys.version.split()[0], "duckdb": duckdb.__version__, "numpy": np.__version__}
    if have != rt:
        raise SystemExit(f"runtime {have} differs from the protocol's {rt}")
    daily_sha = hashlib.sha256(a.daily.read_bytes()).hexdigest()
    if daily_sha != PROTOCOL["inputs"]["daily_dataset"]["sha256"]:
        raise SystemExit("daily dataset does not match protocol.json")
    main_list = a.state / "candidates-provable-20260924.csv"
    supp = a.state / "candidates-premarket-20260924.csv"
    d3 = next(d for d in json.loads((HERE / "deviations.json").read_text())["deviations"] if d["id"] == "D3")
    if hashlib.sha256(main_list.read_bytes()).hexdigest() != PROTOCOL["inputs"]["candidates"]["sha256"]:
        raise SystemExit("candidate list does not match protocol.json")
    if hashlib.sha256(supp.read_bytes()).hexdigest() != d3["supplement_candidates_sha256"]:
        raise SystemExit("pre-market supplement does not match deviations.json D3")
    table_bytes = a.cost_table.read_bytes()
    return {"runtime": have, "daily_sha256": daily_sha, "cost_table_sha256": sha256_bytes(table_bytes),
            "fees_sha256": sha256_bytes((HERE / "fees.json").read_bytes()),
            "clarifications_sha256": sha256_bytes((HERE / "clarifications.json").read_bytes()),
            "deviations_sha256": sha256_bytes((HERE / "deviations.json").read_bytes()),
            "audit_sha256": sha256_bytes(a.audit.read_bytes()), "bootstrap": {"B": B, "block": BLOCK, "seed": SEED}}, \
        json.loads(table_bytes), [main_list, supp]


def gate_outcomes(meta, name, want_table_sha):
    if meta.get("cost_table_sha256") != want_table_sha:
        raise SystemExit(f"{name} outcomes were not computed against this cost table (costs.sample ordering)")


def dev_val(a) -> int:
    inputs, table, cand_paths = check_inputs(a)
    costs = Costs(table)
    dev_rows, dev_meta = read_outcomes(a.outcomes_dev, "dev")
    val_rows, val_meta = read_outcomes(a.outcomes_val, "val")
    gate_outcomes(dev_meta, "development", inputs["cost_table_sha256"])
    gate_outcomes(val_meta, "validation", inputs["cost_table_sha256"])
    lo, hi = SPLITS["development"][0], SPLITS["validation"][1]
    spy = Spy(a.daily, hi)
    dev_cal, val_cal = spy.calendar("development"), spy.calendar("validation")
    iwm, iwm_missing = iwm_open_to_close(a.benchmarks, dev_cal + val_cal)
    regime = spy.regime(dev_cal + val_cal)
    dev_E, val_E = Entries(dev_rows, costs, iwm, dev_cal), Entries(val_rows, costs, iwm, val_cal)
    dev = evaluate_split(dev_E, regime)
    val = evaluate_split(val_E, regime)
    rids = [rule_id(*re) for re in RULE_EXITS]
    robust = ("winsorised_mean", "mean_without_top5_sessions", "mean_of_session_means")
    dev_pass = [r for r in rids if dev[r]["trades"] >= 200 and dev[r].get("p") is not None and dev[r]["p"] <= 0.05]
    val_p = [val[r]["p"] if val[r]["trades"] else 1.0 for r in dev_pass]
    confirm, validated = {}, []
    for r, pa, pb in zip(dev_pass, bh(val_p), by(val_p)):
        v = val[r]
        ok = bool(v["trades"] >= 100 and pa <= 0.10 and all((v.get(k) or 0) > 0 for k in robust))
        confirm[r] = {"validation_trades": v["trades"], "validation_p": v.get("p"), "bh_adjusted": rnd(pa, 10),
                      "by_adjusted_sensitivity": rnd(pb, 10), "confirmed": ok}
        if ok:
            validated.append(r)
    # C29: BH across all 768 rule-exits, at each stage's own thresholds (sensitivities, not selection)
    dev_bh = dict(zip(rids, bh([dev[r]["p"] if dev[r]["trades"] else 1.0 for r in rids])))
    val_bh = dict(zip(rids, bh([val[r]["p"] if val[r]["trades"] else 1.0 for r in rids])))
    sens = {"development_bh768_passes": sorted(r for r in rids if dev[r]["trades"] >= 200 and dev_bh[r] <= 0.05),
            "validation_bh768_confirmations": sorted(r for r in rids if val[r]["trades"] >= 100 and val_bh[r] <= 0.10
                                                     and all((val[r].get(k) or 0) > 0 for k in robust))}

    def lb_key(stats, r):
        return stats[r]["lower_bound"] if stats[r].get("lower_bound") is not None else -1e18
    # C27: the holdout's five: lowest validation p, then higher validation lower bound, then rule id
    holdout_list = sorted(validated, key=lambda r: (val[r]["p"], -lb_key(val, r), r))[:5]
    paperable = [r for r in rids if not r.startswith("09:30|")]  # C31
    most_traded = sorted(paperable, key=lambda r: (-dev[r]["trades"], dev[r].get("p") or 1.0, r))[0]
    val_paper = [r for r in validated if not r.startswith("09:30|")]
    if val_paper:
        candidate = {"rule_exit": sorted(val_paper, key=lambda r: (-lb_key(val, r), r))[0],
                     "basis": "highest validation lower bound (holdout pending; 09:30 rules excluded, C31)", "mechanics_only": False}
    else:
        candidate = {"rule_exit": most_traded, "basis": "most-traded development rule-exit (C20); nothing validated", "mechanics_only": True}
    results = {
        "schema_version": 1, "protocol": PROTOCOL["id"], "stage": "dev_val", "protocol_sha256": sha256_bytes(PROTOCOL_BYTES),
        "inputs": dict(inputs, outcomes_dev_content_sha256=dev_meta["content_sha256"], outcomes_val_content_sha256=val_meta["content_sha256"],
                       iwm_calendar_sessions_without_official_open_and_close=iwm_missing),
        "regime_factor_share_1": {"development": rnd(np.mean([regime[d] == 1.0 for d in dev_cal])),
                                  "validation": rnd(np.mean([regime[d] == 1.0 for d in val_cal]))},
        "completeness": {"development": completeness(dev_rows, dev_meta), "validation": completeness(val_rows, val_meta)},
        "coverage": coverage(a.audit, cand_paths, lo, hi),
        "entries_fired_loosest": {"development": {"fires": dev_E.n_fired, "filled": dev_E.n},
                                  "validation": {"fires": val_E.n_fired, "filled": val_E.n}},
        "development": dev, "validation": val,
        "selection": {"development_passes": dev_pass, "validation": confirm, "validated": validated, "holdout_candidates": holdout_list,
                      "sensitivities": sens},
        "paper_candidate": candidate,
        "capture": {"development": capture(dev_rows), "validation": capture(val_rows), "development_and_validation": capture(dev_rows + val_rows),
                    "development_and_validation_without_basis_uncertain_rows": capture([r for r in dev_rows + val_rows if not basis_uncertain(r)])},
        "replication_wave_h": replication(dev_rows + val_rows),
        "replication_wave_h_without_basis_uncertain_rows": replication([r for r in dev_rows + val_rows if not basis_uncertain(r)]),
        "basis_uncertain_rows": {"development": sum(map(basis_uncertain, dev_rows)), "validation": sum(map(basis_uncertain, val_rows))},
    }
    body = (json.dumps(results, indent=1, sort_keys=True) + "\n").encode()
    a.out.write_bytes(body)
    os.chmod(a.out, 0o600)
    print(json.dumps({"out": a.out.name, "sha256": sha256_bytes(body), "development_passes": len(dev_pass),
                      "validated": validated, "holdout_candidates": holdout_list, "paper_candidate": candidate}))
    return 0


def holdout(a) -> int:
    prior_bytes = a.dev_val.read_bytes()
    prior = json.loads(prior_bytes)
    if prior["stage"] != "dev_val":
        raise SystemExit("holdout needs the dev_val results")
    inputs, table, cand_paths = check_inputs(a)
    if inputs["cost_table_sha256"] != prior["inputs"]["cost_table_sha256"]:
        raise SystemExit("the cost table changed after dev_val")
    todo = prior["selection"]["holdout_candidates"]
    rows, meta = read_outcomes(a.outcomes_holdout, "holdout")
    gate_outcomes(meta, "holdout", inputs["cost_table_sha256"])
    if meta.get("dev_val_sha256") != sha256_bytes(prior_bytes):
        raise SystemExit("holdout outcomes were not gated on these dev_val results")
    lo, hi = SPLITS["holdout"]
    spy = Spy(a.daily, hi)
    cal = spy.calendar("holdout")
    iwm, iwm_missing = iwm_open_to_close(a.benchmarks, cal)
    E = Entries(rows, Costs(table), iwm, cal)
    stats = evaluate_split(E, spy.regime(cal), only=set(todo)) if todo else {}
    ps = [stats[r]["p"] if stats[r]["trades"] >= 50 else 1.0 for r in todo]
    passes = {r: {"trades": stats[r]["trades"], "p": stats[r].get("p"), "holm_adjusted": rnd(pa, 10),
                  "lower_bound": stats[r].get("lower_bound"), "passed": bool(stats[r]["trades"] >= 50 and pa <= 0.05)}
              for r, pa in zip(todo, holm(ps) if todo else [])}
    if todo:
        # C30: paper_e2e's first clause: the evaluated rule-exit with the highest holdout lower bound;
        # it is labelled mechanics-only unless it passed the holdout.
        pool = [r for r in todo if not r.startswith("09:30|")]  # C31
        if pool:
            best = sorted(pool, key=lambda r: (-(stats[r]["lower_bound"] if stats[r].get("lower_bound") is not None else -1e18), r))[0]
            cand = {"rule_exit": best, "basis": "highest holdout lower bound among the evaluated non-09:30 rule-exits",
                    "mechanics_only": not passes[best]["passed"], "holdout_passed": passes[best]["passed"]}
        else:
            cand = dict(prior["paper_candidate"], note="every evaluated rule-exit is a 09:30 rule (C31)")
    else:
        cand = prior["paper_candidate"]
    results = {"schema_version": 1, "protocol": PROTOCOL["id"], "stage": "holdout", "dev_val_sha256": sha256_bytes(prior_bytes),
               "inputs": dict(inputs, outcomes_holdout_content_sha256=meta["content_sha256"],
                              iwm_calendar_sessions_without_official_open_and_close=iwm_missing),
               "evaluated": todo, "holdout": {r: stats[r] for r in todo}, "passes": passes,
               "completeness": completeness(rows, meta), "coverage": coverage(a.audit, cand_paths, lo, hi), "paper_candidate": cand}
    body = (json.dumps(results, indent=1, sort_keys=True) + "\n").encode()
    a.out.write_bytes(body)
    os.chmod(a.out, 0o600)
    print(json.dumps({"out": a.out.name, "sha256": sha256_bytes(body), "passes": passes, "paper_candidate": cand}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="stage", required=True)
    for name in ("dev_val", "holdout"):
        s = sub.add_parser(name)
        s.add_argument("--cost-table", type=Path, required=True)
        s.add_argument("--daily", type=Path, required=True)
        s.add_argument("--benchmarks", type=Path, required=True)
        s.add_argument("--audit", type=Path, required=True)
        s.add_argument("--state", type=Path, default=Path.home() / ".local/state/native-agent-stack/research/mover-early-entry")
        s.add_argument("--out", type=Path, required=True)
        if name == "dev_val":
            s.add_argument("--outcomes-dev", type=Path, required=True)
            s.add_argument("--outcomes-val", type=Path, required=True)
        else:
            s.add_argument("--dev-val", type=Path, required=True)
            s.add_argument("--outcomes-holdout", type=Path, required=True)
    a = ap.parse_args(argv)
    return dev_val(a) if a.stage == "dev_val" else holdout(a)


if __name__ == "__main__":
    raise SystemExit(main())
