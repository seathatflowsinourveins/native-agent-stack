"""Per-symbol-day features for protocol.json (mover-early-entry-v1-20260924); private data in and out.

  python features.py signals  --daily DAILY --split dev --out FILE   pre-entry fields only (quotes.py input)
  python features.py outcomes --daily DAILY --split dev --out FILE   pre-entry fields plus exits

``signals`` computes nothing after an entry except, for entries the loosest rule fires, the session's
summed dollar volume at the fixed cost-sample timestamps (entry + 15 min, entry + 60 min, 15:55).
``outcomes`` adds the official close, eventual gain, the four exits, session_high_after_entry, the
halt flag and the t + 30 min placebo entry with its exits. Exits are computed only for entries the
loosest rule fires (G 0.20, V $250k, any news): every other rule's fired set is a subset of it.

Each page is checked against its collection ledger's sha256 before use. The candidate list and the
daily dataset are checked against the hashes protocol.json froze. Output is gzip JSON lines, one
symbol-day per line, sorted by session then symbol, and byte-identical across runs.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules as R  # noqa: E402
from sessions_io import official_price  # noqa: E402

STATE = Path.home() / ".local/state/native-agent-stack/research/mover-early-entry"
# The asof 2026-09-21 collections (deviations.json D2), in session-range parts; each session is read
# from the first collection (by name) whose ledger marks it complete.
COLLECTION_GLOB = "collect-asof20260921*"
# The pre-market supplement (deviations.json D3): its own candidate list, sha-pinned in D3, collected
# into its own directories; each session reads the main and the supplement collection.
SUPPLEMENT = "candidates-premarket-20260924.csv"
SUPPLEMENT_GLOB = "supp-asof20260921*"
DEVIATIONS = json.loads((HERE / "deviations.json").read_text())
CANDIDATES = "candidates-provable-20260924.csv"
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
SPLITS = {k: tuple(v) for k, v in PROTOCOL["splits"].items()}
SPLIT_KEYS = {"dev": "development", "val": "validation", "holdout": "holdout"}
LOOSEST = (min(R.GAINS), min(R.VOLUMES), "any")
_BASE: dict = {}


def fast_epoch(ts: str) -> float:
    if len(ts) == 20 and ts[10] == "T" and ts[-1] == "Z":
        base = _BASE.get(ts[:10])
        if base is None:
            base = _BASE[ts[:10]] = datetime.fromisoformat(ts[:10] + "T00:00:00+00:00").timestamp()
        return base + int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + int(ts[17:19])
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


ASOF = "2026-09-21"  # deviations.json D2


def ledger(coll: Path):
    """(pages, complete sessions, incomplete sessions, symbols per complete session); refuses a collection
    any of whose runs used an asof other than the candidate list's naming date (D2)."""
    pages, complete, incomplete, symbols = {}, set(), set(), {}
    for line in (coll / "ledger.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if rec["event"] == "run_start" and rec.get("asof") != ASOF:
            raise SystemExit(f"{coll.name}: a run used asof {rec.get('asof')!r}, not {ASOF}")
        if rec["event"] == "page":
            pages[(rec["session"], rec["kind"], rec["batch"], rec["page"])] = (rec["sha256"], rec["status"])
        elif rec["event"] == "session_complete":
            complete.add(rec["session"])
            incomplete.discard(rec["session"])
            symbols[rec["session"]] = rec["symbols"]
        elif rec["event"] == "session_incomplete":
            incomplete.add(rec["session"])
    return pages, complete, incomplete, symbols


def read_pages(sdir: Path, session: str, kind: str, pages: dict):
    on_disk = sorted(sdir.glob(f"{kind}-*.json.gz"))
    names = {f.name for f in on_disk}
    for (sess, k, batch, page) in pages:
        if sess == session and k == kind and f"{kind}-{batch:04d}-{page:04d}.json.gz" not in names:
            raise SystemExit(f"ledger page without a file: {sdir}/{kind}-{batch:04d}-{page:04d}")
    for f in on_disk:
        _, batch, page = f.name.removesuffix(".json.gz").split("-")
        raw = gzip.decompress(f.read_bytes())
        want, status = pages[(session, kind, int(batch), int(page))]
        if hashlib.sha256(raw).hexdigest() != want:
            raise SystemExit(f"page hash mismatch: {f}")
        if status == 200:
            yield json.loads(raw)


def load_session(session: str, colls: list, ledgers: dict):
    """Bars as column lists per symbol (stable-sorted, first bar of each start time), auctions, news."""
    raw_bars = defaultdict(list)
    auctions = defaultdict(dict)
    news = defaultdict(set)
    for coll in colls:
        sdir = coll / "sessions" / session
        pages = ledgers[coll.name][0]
        for body in read_pages(sdir, session, "bars", pages):
            for sym, items in (body.get("bars") or {}).items():
                raw_bars[sym].extend((fast_epoch(b["t"]), b["o"], b["h"], b["l"], b["c"], b["v"], b.get("vw") or b["c"]) for b in items)
        for body in read_pages(sdir, session, "auctions", pages):
            for sym, days in (body.get("auctions") or {}).items():
                for d in days or []:
                    auctions[sym].setdefault(d["d"], {"o": d.get("o") or [], "c": d.get("c") or []})
        for body in read_pages(sdir, session, "news", pages):
            for item in body.get("news") or []:
                created = fast_epoch(item["created_at"])
                for sym in item.get("symbols") or []:
                    news[sym].add(created)
    bars = {}
    for sym, rows in raw_bars.items():
        rows.sort(key=lambda r: r[0])  # stable: the first page's copy of a repeated bar wins
        dedup, last = [], None
        for r in rows:
            if r[0] != last:
                dedup.append(r)
            last = r[0]
        bars[sym] = dedup
    return bars, auctions, {s: sorted(v) for s, v in news.items()}


def opening_dollar_volume(day_auction):
    o_prints = [o for o in (day_auction or {}).get("o", []) if o.get("c") == "O"]
    if not o_prints:
        return None
    top = max(o_prints, key=lambda o: (o.get("s") or 0, o.get("x") or ""))
    return float(top["p"]) * float(top.get("s") or 0)


def entry_fields(day, hhmm, bars, oo, open_dv):
    px, ts, src, i = R.entry_for(day, hhmm, bars, oo)
    if px is None:
        return {"entry": None, "entry_reason": src}
    bar_dv = float(bars.dv[i]) if i is not None else open_dv
    return {"entry": px, "entry_ts": ts, "entry_source": src, "entry_bar_dv": bar_dv, "entry_cum_dv": bars.cum_dv(ts)}


def exit_fields(entry, entry_ts, bars, day, oc, daily_close):
    out, high, halt, close_src = R.exits_for(entry, entry_ts, bars, day, oc, daily_close)
    return {"exits": {x: [p, ts, fb, bars.cum_dv(ts)] for x, (p, ts, fb) in out.items()},
            "high": high, "halt": halt, "close_source": close_src}


def symbol_day(session, sym, prev_date, gap, rows, auc, news_ts, daily, outcomes):
    bars = R.Bars(*(zip(*rows) if rows else [()] * 7), day_start=R.et_epoch(session, "04:00"))
    auc_today, auc_prev = auc.get(session), auc.get(prev_date)
    prev_close, prev_src = official_price(auc_prev, "c")
    if prev_close is None and daily.get("prev_raw_c"):
        prev_close, prev_src = float(daily["prev_raw_c"]), "daily_bar_close"
    f, split = R.split_factor(daily.get("prev_raw_c"), daily.get("prev_all_c"), daily.get("raw_c"), daily.get("all_c"))
    ref = prev_close / f if prev_close else None
    oo, oo_src = official_price(auc_today, "o")
    oc, oc_src = official_price(auc_today, "c")
    open_dv = opening_dollar_volume(auc_today)
    prev16 = R.et_epoch(prev_date, "16:00")
    rec = {"session": session, "symbol": sym, "prev_date": prev_date, "gap_over_7": gap, "bars": len(bars),
           "ref": ref, "ref_source": prev_src, "split": split, "split_factor": f, "official_open": oo,
           "open_source": oo_src, "open_dv": open_dv, "has_official_close": oc is not None,
           "daily_missing": not daily, "t": {}}
    if outcomes:
        rec["official_close"], rec["official_close_source"] = oc, oc_src
        close_ts = R.et_epoch(session, R.close_hhmm(session))
        i1 = bars.index(close_ts)
        rec["bar_close"] = float(bars.c[i1 - 1]) if i1 else None
        # C22 (amended): official close, else the daily bar close, else the last bar close before the close
        eod, src = ((oc, "official") if oc is not None else (daily.get("raw_c"), "daily_close") if daily.get("raw_c")
                    else (rec["bar_close"], "bar_close") if rec["bar_close"] else (None, None))
        rec["eventual_gain"] = eod / ref - 1 if (eod and ref) else None
        rec["eventual_source"] = src
    for hhmm in R.TIMES:
        price, dv = bars.state(R.signal_cutoff(session, hhmm))
        tt = R.et_epoch(session, hhmm)
        gain = price / ref - 1 if (price is not None and ref) else None
        row = {"price": price, "dv": dv, "gain": gain,
               "news120": R.news_before(news_ts, tt, 120, prev16), "news600": R.news_before(news_ts, tt, 600, prev16)}
        row.update(entry_fields(session, hhmm, bars, oo, open_dv))
        loosest = R.fires(price, dv, gain, row["news120"], *LOOSEST)
        row["loosest"] = loosest
        if loosest and row["entry"] is not None:
            e_ts = row["entry_ts"]
            row["sample_cum_dv"] = [bars.cum_dv(e_ts + 900), bars.cum_dv(e_ts + 3600),
                                    bars.cum_dv(R.et_epoch(session, R.close_hhmm(session)) - 300)]
            if outcomes:
                row.update(exit_fields(row["entry"], e_ts, bars, session, oc, daily.get("raw_c")))
                p = entry_fields(session, R.PLACEBO[hhmm], bars, oo, open_dv)
                if p["entry"] is not None:
                    p.update(exit_fields(p["entry"], p["entry_ts"], bars, session, oc, daily.get("raw_c")))
                row["placebo"] = p
        rec["t"][hhmm] = row
    return rec


_CTX: dict = {}


def _work(args):
    session, cands, daily, outcomes, colls = args
    bars, auctions, news = load_session(session, [_CTX["state"] / c for c in colls], _CTX["ledgers"])
    out = []
    for sym, prev_date, gap, supp in cands:
        rec = symbol_day(session, sym, prev_date, gap, bars.get(sym, []), auctions.get(sym, {}),
                         news.get(sym, []), daily.get(sym, {}), outcomes)
        rec["supplement"] = supp
        out.append(rec)
    return session, [json.dumps(r, sort_keys=True, separators=(",", ":")) for r in out]


def load_inputs(daily_path: Path, state: Path, split: str):
    cand_path = state / CANDIDATES
    if sha256_file(cand_path) != PROTOCOL["inputs"]["candidates"]["sha256"]:
        raise SystemExit("candidate list does not match protocol.json")
    if sha256_file(daily_path) != PROTOCOL["inputs"]["daily_dataset"]["sha256"]:
        raise SystemExit("daily dataset does not match protocol.json")
    supp_path = state / SUPPLEMENT
    d3 = next(d for d in DEVIATIONS["deviations"] if d["id"] == "D3")
    if sha256_file(supp_path) != d3["supplement_candidates_sha256"]:
        raise SystemExit("pre-market supplement does not match deviations.json D3")
    lo, hi = SPLITS[SPLIT_KEYS[split]]
    by_day = defaultdict(list)
    for path, supp in ((cand_path, False), (supp_path, True)):
        for r in csv.DictReader(path.open(newline="")):
            if lo <= r["session_date"] <= hi:
                gap = (datetime.fromisoformat(r["session_date"]) - datetime.fromisoformat(r["prev_date"])).days > 7
                by_day[r["session_date"]].append((r["symbol"], r["prev_date"], gap, supp))
    for d, rows in by_day.items():
        if len({r[0] for r in rows}) != len(rows):
            raise SystemExit(f"{d}: a symbol-day is in the candidate list twice or in both lists (D3 requires disjoint lists)")
    import duckdb
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("CREATE TEMP TABLE c (symbol VARCHAR, session_date DATE, prev_date DATE)")
    con.executemany("INSERT INTO c VALUES (?, ?, ?)", [(s, d, p) for d, rows in by_day.items() for s, p, _, _ in rows])
    q = f"""SELECT c.symbol, CAST(c.session_date AS VARCHAR), a.raw_c, a.all_c, b.raw_c, b.all_c FROM c
            LEFT JOIN read_parquet('{daily_path}') a ON a.symbol = c.symbol AND a.session_date = c.session_date
            LEFT JOIN read_parquet('{daily_path}') b ON b.symbol = c.symbol AND b.session_date = c.prev_date"""
    daily = defaultdict(dict)
    for sym, day, raw_c, all_c, prev_raw_c, prev_all_c in con.execute(q).fetchall():
        if raw_c is not None or prev_raw_c is not None:
            daily[day][sym] = {"raw_c": raw_c, "all_c": all_c, "prev_raw_c": prev_raw_c, "prev_all_c": prev_all_c}
    return {d: sorted(v) for d, v in by_day.items()}, daily


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("signals", "outcomes"))
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--split", choices=tuple(SPLIT_KEYS), required=True)
    ap.add_argument("--state", type=Path, default=STATE)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-sessions", type=int, default=0, help="trial runs only")
    ap.add_argument("--cost-table", type=Path, help="outcomes mode: the committed cost table (costs.sample ordering)")
    ap.add_argument("--dev-val", type=Path, help="holdout split: the dev_val results (selection.holdout ordering)")
    a = ap.parse_args(argv)
    gate = {}
    if a.mode == "outcomes":
        if not a.cost_table:
            raise SystemExit("outcomes mode needs --cost-table: no exit path is computed before the cost table is fixed")
        gate["cost_table_sha256"] = sha256_file(a.cost_table)
    if a.split == "holdout":
        if not a.dev_val or json.loads(a.dev_val.read_text()).get("stage") != "dev_val":
            raise SystemExit("the holdout split is read only after dev_val results exist (--dev-val)")
        gate["dev_val_sha256"] = sha256_file(a.dev_val)
    colls = sorted(p for p in a.state.glob(COLLECTION_GLOB) if (p / "ledger.jsonl").exists())
    supps = sorted(p for p in a.state.glob(SUPPLEMENT_GLOB) if (p / "ledger.jsonl").exists())
    ledgers = {c.name: ledger(c) for c in colls + supps}
    by_day, daily = load_inputs(a.daily, a.state, a.split)
    source = {}
    for d, cands in by_day.items():
        src = []
        for group, needed in ((colls, any(not c[3] for c in cands)), (supps, any(c[3] for c in cands))):
            if needed:
                c = next((c for c in group if d in ledgers[c.name][1]), None)
                if c is None:
                    raise SystemExit(f"session {d} is not complete in any {'supplement' if group is supps else 'main'} collection")
                want = sum(1 for x in cands if x[3] == (group is supps))
                if ledgers[c.name][3][d] != want:
                    raise SystemExit(f"{c.name} {d}: collected {ledgers[c.name][3][d]} symbols, the frozen list has {want}")
                src.append(c.name)
        source[d] = src
    # sessions of this split that some collection once marked incomplete (each was then completed where it is read)
    incomplete = sorted(d for d in by_day if any(d in ledgers[c.name][2] for c in colls + supps))
    jobs = [(d, by_day[d], daily.get(d, {}), a.mode == "outcomes", source[d]) for d in sorted(by_day)]
    if a.max_sessions:
        jobs = jobs[: a.max_sessions]
    _CTX.update(state=a.state, ledgers=ledgers)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".partial")
    h = hashlib.sha256()
    n = 0
    old = os.umask(0o077)
    try:
        with tmp.open("wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, compresslevel=6, mtime=0) as gz, \
                get_context("fork").Pool(a.workers) as pool:
            for session, lines in pool.imap(_work, jobs, chunksize=1):
                for line in lines:
                    data = (line + "\n").encode()
                    gz.write(data)
                    h.update(data)
                    n += 1
    finally:
        os.umask(old)
    tmp.replace(a.out)
    meta = {"mode": a.mode, "split": a.split, "sessions": len(jobs), "max_sessions": a.max_sessions, "symbol_days": n, "content_sha256": h.hexdigest(),
            "file_sha256": sha256_file(a.out), "split_sessions_ever_incomplete_elsewhere": incomplete, **gate,
            "collections": sorted({c for j in jobs for c in j[4]}),
            "supplement_symbol_days": sum(1 for j in jobs for c in j[1] if c[3]),
            "candidates_sha256": PROTOCOL["inputs"]["candidates"]["sha256"], "daily_sha256": PROTOCOL["inputs"]["daily_dataset"]["sha256"],
            "supplement_sha256": next(d for d in DEVIATIONS["deviations"] if d["id"] == "D3")["supplement_candidates_sha256"]}
    meta_path = Path(str(a.out) + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    os.chmod(meta_path, 0o600)
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
