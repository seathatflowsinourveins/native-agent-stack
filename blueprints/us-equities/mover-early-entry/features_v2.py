"""Per-symbol-day trades for protocol-v2.json families E (first-cross) and F (follow-up setups).

  python features_v2.py --daily DAILY --split dev --cost-table evidence/cost-table-run-v1.json --out FILE

Reads the same collections as features.py (asof 2026-09-21 main parts plus the D3 supplement, pages
checked against their ledgers) and writes one gzip JSON line per symbol-day that has any E or F trade:
for each rule the entry (price, time, decision-time dollar volume, entry-bar dollar volume, cumulative
dollar volume at entry) and each exit's price, time, close-fallback flag and cumulative dollar volume.
Clarifications V1-V6 (clarifications-v2.json) apply; the holdout split needs --dev-val like v1.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from multiprocessing import get_context
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import features as F  # noqa: E402
import rules as R  # noqa: E402
from sessions_io import official_price  # noqa: E402

PROTOCOL_V2 = json.loads((HERE / "protocol-v2.json").read_text())
EF = PROTOCOL_V2["families"]["E_first_cross"]
WINDOWS = [tuple(w) for w in EF["windows_et"]]
E_GAINS, E_VOLUMES, E_NEWS = EF["gain_thresholds"], EF["min_dollar_volume"], EF["news_variants"]
F_SETUPS = ("F1_orb5", "F2_orb15", "F3_premarket_high_break", "F4_vwap_reclaim")
# protocol-v2 inputs.cost_table: v1's committed table (evidence/cost-table-run-v1.json)
V1_COST_TABLE_SHA256 = "be50cbdfd75c5c4b0a66286bf9edb40c9ce49add719b6b5e1b0cdf93064eaa13"
Y_EXITS = ("Y1", "Y2", "Y3", "Y4")


def e_rule_id(w, g, v, n):
    return f"E|{w[0]}-{w[1]}|G{g:.2f}|V{int(v)}|{n}"


def first_cross(bars: R.Bars, day, ref, news, prev16):
    """{E rule id: bar index k} for the first qualifying bar per rule (V1)."""
    out = {}
    if not len(bars) or not ref:
        return out
    t = bars.t
    price_before = np.concatenate(([np.nan], bars.c[:-1]))
    dv_before = np.concatenate(([0.0], bars.cumdv[:-1]))
    gain_before = price_before / ref - 1
    base = (~np.isnan(price_before)) & (price_before >= R.MIN_PRICE)
    later = [x for x in news if x >= prev16]
    news_ok = t >= (min(later) + 120) if later else np.zeros(len(t), dtype=bool)
    open_ts = R.et_epoch(day, "09:30")
    for w in WINDOWS:
        lo, hi = R.et_epoch(day, w[0]), R.et_epoch(day, w[1])
        in_w = (t >= lo) & (t < hi)
        if w[1] == "09:30":
            in_w &= t < open_ts
        for g in E_GAINS:
            for v in E_VOLUMES:
                q = base & in_w & (gain_before >= g - R.GAIN_EPS) & (dv_before >= v)
                for n in E_NEWS:
                    qq = q & news_ok if n == "news_before_t" else q
                    hit = np.flatnonzero(qq)
                    if hit.size:
                        out[e_rule_id(w, g, v, n)] = int(hit[0])
    return out


def y_exits(bars: R.Bars, day, kb, entry, stop, start_after_entry, close, close_ts):
    """V2/V5/V6: Y1-Y4 as {Y: (price, ts, used_close)} from bar kb (+1 for breakout entries)."""
    i1 = bars.index(close_ts)
    j0 = kb + 1 if start_after_entry else kb
    o, h, l, t = bars.o[j0:i1], bars.h[j0:i1], bars.l[j0:i1], bars.t[j0:i1]
    out = {"Y1": (close, close_ts, False)}
    if stop >= entry:  # V6 (amended V15): a stop at or above the entry exits every stop-based rule at the next bar's open
        nxt = (float(bars.o[kb + 1]), float(bars.t[kb + 1]), False) if kb + 1 < i1 else (close, close_ts, True)
        return dict(out, Y2=nxt, Y3=nxt, Y4=nxt), True
    # Y2: the initial stop
    y2 = None
    for j in range(len(o)):
        if o[j] <= stop:
            y2 = (float(o[j]), float(t[j]), False)
            break
        if l[j] <= stop:
            y2 = (float(stop), float(t[j]), False)
            break
    out["Y2"] = y2 or (close, close_ts, True)
    # Y3: stop, then a 10% trail once the running high (through the previous bar) reaches 1.10 x entry
    running = max(entry, float(bars.h[kb])) if start_after_entry else entry
    y3 = None
    for j in range(len(o)):
        level = stop if running < 1.10 * entry else max(stop, 0.90 * running)
        if l[j] <= level:
            y3 = (float(min(level, o[j])), float(t[j]), False)
            break
        running = max(running, float(h[j]))
    out["Y3"] = y3 or (close, close_ts, True)
    # Y4: stop or a 2R target, stop assumed first
    target = entry + 2 * (entry - stop)
    y4 = None
    for j in range(len(o)):
        if o[j] <= stop or o[j] >= target:
            y4 = (float(o[j]), float(t[j]), False)
            break
        if l[j] <= stop:
            y4 = (float(stop), float(t[j]), False)
            break
        if h[j] >= target:
            y4 = (float(target), float(t[j]), False)
            break
    out["Y4"] = y4 or (close, close_ts, True)
    return out, False


def setups(bars: R.Bars, day):
    """{setup: (entry bar index, entry price, stop, breakout)} for F1-F4 (V2-V4); official open checked by the caller."""
    out = {}
    t, o, h, l, c = bars.t, bars.o, bars.h, bars.l, bars.c
    e = lambda hhmm: R.et_epoch(day, hhmm)  # noqa: E731
    close_ts = e(R.close_hhmm(day))
    for name, r_end, entries_from in (("F1_orb5", "09:35", "09:35"), ("F2_orb15", "09:45", "09:45")):
        rng = np.flatnonzero((t >= e("09:30")) & (t < e(r_end)))
        if rng.size:
            hi, lo = float(h[rng].max()), float(l[rng].min())
            cand = np.flatnonzero((t >= e(entries_from)) & (t < e("11:00")) & (t < close_ts) & (h > hi))
            if cand.size:
                k = int(cand[0])
                out[name] = (k, float(max(o[k], hi)), lo, True)
    pm = np.flatnonzero((t >= e("04:00")) & (t < e("09:30")))
    if pm.size:
        pmh = float(h[pm].max())
        # V16: the breakout bar must start after the opening print's 09:30 bar (the official open sets the stop)
        cand = np.flatnonzero((t >= e("09:31")) & (t < e("11:00")) & (t < close_ts) & (h > pmh))
        if cand.size:
            k = int(cand[0])
            out["F3_premarket_high_break"] = (k, float(max(o[k], pmh)), None, True)  # stop = official open x 0.90
    return out


def vwap_reclaim(bars: R.Bars, day, volume):
    e = lambda hhmm: R.et_epoch(day, hhmm)  # noqa: E731
    t, o, l, c = bars.t, bars.o, bars.l, bars.c
    cv = np.cumsum(volume)
    vwap = np.cumsum(bars.dv) / np.where(cv > 0, cv, np.nan)
    dips = np.flatnonzero((t >= e("09:35")) & (t < e(R.close_hhmm(day))) & (c < vwap))
    if not dips.size:
        return None
    k1 = int(dips[0])
    rec = np.flatnonzero((np.arange(len(t)) > k1) & (c > vwap))
    if not rec.size:
        return None
    k2 = int(rec[0])
    k = k2 + 1
    if k >= len(t) or t[k] >= e("11:00") or t[k] >= e(R.close_hhmm(day)):
        return None
    since = np.flatnonzero((t >= e("09:30")) & (np.arange(len(t)) <= k2))
    return k, float(o[k]), float(l[since].min()), False


def symbol_day_v2(session, sym, prev_date, gap, supp, rows, auc, news_ts, daily):
    cols = list(zip(*rows)) if rows else [()] * 7
    bars = R.Bars(*cols, day_start=R.et_epoch(session, "04:00"))
    volume = np.asarray(cols[5], dtype=float)[np.asarray(cols[0], dtype=float) >= R.et_epoch(session, "04:00")] if rows else np.zeros(0)
    prev_close, prev_src = official_price(auc.get(prev_date), "c")
    if prev_close is None and daily.get("prev_raw_c"):
        prev_close, prev_src = float(daily["prev_raw_c"]), "daily_bar_close"
    f, split = R.split_factor(daily.get("prev_raw_c"), daily.get("prev_all_c"), daily.get("raw_c"), daily.get("all_c"))
    ref = prev_close / f if prev_close else None
    oo, _ = official_price(auc.get(session), "o")
    oc, _ = official_price(auc.get(session), "c")
    close_ts = R.et_epoch(session, R.close_hhmm(session))
    i1 = bars.index(close_ts)
    close, close_src = ((oc, "official") if oc is not None else (daily.get("raw_c"), "daily_close") if daily.get("raw_c")
                        else (float(bars.c[i1 - 1]), "bar_close") if i1 else (None, None))
    eventual = close / ref - 1 if (ref and close) else None
    rec = {"session": session, "symbol": sym, "supplement": supp, "gap_over_7": gap, "ref": ref, "ref_source": prev_src,
           "split": split, "close_source": close_src, "eventual_gain": eventual,
           "basis_uncertain": prev_src == "daily_bar_close" or bool(split), "f_candidate_no_official_open": False, "E": {}, "F": {}}
    if not ref or close is None:
        return rec
    prev16 = R.et_epoch(prev_date, "16:00")
    # family E
    ks = first_cross(bars, session, ref, news_ts, prev16)
    cache = {}
    for rid, k in sorted(ks.items()):
        if k not in cache:
            entry, ets = float(bars.o[k]), float(bars.t[k])
            ex, high, halt, src = R.exits_for(entry, ets, bars, session, oc, daily.get("raw_c"))
            cache[k] = {"entry": entry, "entry_ts": ets, "decision_dv": float(bars.cumdv[k - 1]), "decision_price": float(bars.c[k - 1]),
                        "decision_gain": float(bars.c[k - 1]) / ref - 1, "high": high,
                        "entry_bar_dv": float(bars.dv[k]), "entry_cum_dv": float(bars.cumdv[k - 1]), "halt": halt,
                        "exits": {x: [p, ts, fb, bars.cum_dv(ts)] for x, (p, ts, fb) in ex.items()}}
        rec["E"][rid] = cache[k]
    # family F (V3 universe)
    pre = bars.index(R.et_epoch(session, "09:30"))
    pre_price = float(bars.c[pre - 1]) if pre else None
    pre_dv = float(bars.cumdv[pre - 1]) if pre else 0.0
    if oo is None and pre_price is not None and pre_price >= 1.20 * ref * (1 - 1e-12) and pre_price >= R.MIN_PRICE and pre_dv >= 250_000:
        rec["f_candidate_no_official_open"] = True  # V3: outside the universe, counted
    if oo is not None and oo >= 1.20 * ref * (1 - 1e-12) and pre_price is not None and pre_price >= R.MIN_PRICE and pre_dv >= 250_000:
        found = setups(bars, session)
        vr = vwap_reclaim(bars, session, volume)
        if vr:
            found["F4_vwap_reclaim"] = vr
        for name, (k, entry, stop, breakout) in sorted(found.items()):
            if stop is None:
                stop = 0.90 * oo
            ex, degenerate = y_exits(bars, session, k, entry, stop, breakout, float(close), close_ts)
            i1c = bars.index(close_ts)
            high = float(max(entry, bars.h[k:i1c].max())) if i1c > k else entry
            rec["F"][name] = {"entry": entry, "entry_ts": float(bars.t[k]), "stop": stop, "breakout": breakout, "degenerate": degenerate,
                              "high": high, "halt": R.halt_flag(bars, float(bars.t[k]), session),
                              "decision_dv": float(bars.cumdv[k - 1]) if k else 0.0, "decision_price": float(bars.c[k - 1]) if k else entry,
                              "entry_bar_dv": float(bars.dv[k]), "entry_cum_dv": float(bars.cumdv[k - 1]) if k else 0.0,
                              "exits": {y: [p, ts, fb, bars.cum_dv(ts)] for y, (p, ts, fb) in ex.items()}}
    return rec


def _work(args):
    session, cands, daily, colls = args
    bars, auctions, news = F.load_session(session, [F._CTX["state"] / c for c in colls], F._CTX["ledgers"])
    out = []
    for sym, prev_date, gap, supp in cands:
        rec = symbol_day_v2(session, sym, prev_date, gap, supp, bars.get(sym, []), auctions.get(sym, {}), news.get(sym, []), daily.get(sym, {}))
        out.append(json.dumps(rec, sort_keys=True, separators=(",", ":")))  # every candidate day, for degree-tier capture
    return session, out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--split", choices=tuple(F.SPLIT_KEYS), required=True)
    ap.add_argument("--state", type=Path, default=F.STATE)
    ap.add_argument("--cost-table", type=Path, required=True)
    ap.add_argument("--dev-val", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args(argv)
    gate = {"cost_table_sha256": F.sha256_file(a.cost_table)}
    if gate["cost_table_sha256"] != V1_COST_TABLE_SHA256:
        raise SystemExit("protocol v2 uses v1's committed cost table only")
    if a.split == "holdout":
        prior = json.loads(a.dev_val.read_text()) if a.dev_val else {}
        if prior.get("stage") != "dev_val" or prior.get("protocol") != PROTOCOL_V2["id"] \
                or prior.get("inputs", {}).get("cost_table_sha256") != gate["cost_table_sha256"]:
            raise SystemExit("the v2 holdout split is read only after v2 dev_val results on this cost table exist (--dev-val)")
        gate["dev_val_sha256"] = F.sha256_file(a.dev_val)
    colls = sorted(p for p in a.state.glob(F.COLLECTION_GLOB) if (p / "ledger.jsonl").exists())
    supps = sorted(p for p in a.state.glob(F.SUPPLEMENT_GLOB) if (p / "ledger.jsonl").exists())
    ledgers = {c.name: F.ledger(c) for c in colls + supps}
    by_day, daily = F.load_inputs(a.daily, a.state, a.split)
    jobs = []
    for d in sorted(by_day):
        src = []
        for group, needed in ((colls, any(not c[3] for c in by_day[d])), (supps, any(c[3] for c in by_day[d]))):
            if needed:
                c = next((c for c in group if d in ledgers[c.name][1]), None)
                if c is None:
                    raise SystemExit(f"session {d} is not complete in any collection")
                want = sum(1 for x in by_day[d] if x[3] == (group is supps))
                if ledgers[c.name][3][d] != want:
                    raise SystemExit(f"{c.name} {d}: symbol count mismatch")
                src.append(c.name)
        jobs.append((d, by_day[d], daily.get(d, {}), src))
    F._CTX.update(state=a.state, ledgers=ledgers)
    tmp = a.out.with_suffix(".partial")
    h, n = hashlib.sha256(), 0
    old = os.umask(0o077)
    try:
        with tmp.open("wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, compresslevel=6, mtime=0) as gz, \
                get_context("fork").Pool(a.workers) as pool:
            for _, lines in pool.imap(_work, jobs, chunksize=1):
                for line in lines:
                    data = (line + "\n").encode()
                    gz.write(data)
                    h.update(data)
                    n += 1
    finally:
        os.umask(old)
    tmp.replace(a.out)
    meta = {"protocol": PROTOCOL_V2["id"], "mode": "v2_trades", "split": a.split, "sessions": len(jobs), "symbol_days": n,
            "content_sha256": h.hexdigest(), **gate}
    mp = Path(str(a.out) + ".meta.json")
    mp.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    os.chmod(mp, 0o600)
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
