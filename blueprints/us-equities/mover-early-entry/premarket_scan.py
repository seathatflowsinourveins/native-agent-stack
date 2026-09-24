"""Scan every symbol's pre-market high to complete the mover candidates for pre-market rules (D3).

The broad-universe daily bars are regular-session bars (their high and low exclude extended-hours
trades; deviations.json D3 measures this), so ``candidates.py``'s daily-high superset is complete
only for prices reached between 09:30 and 16:00. A pre-market rule can fire on a pre-market price
above the regular-session high. For each session this requests fully adjusted SIP 30-minute bars
04:00-09:29 ET for every symbol with a daily row that session and the previous one (asof
2026-09-21, the candidate list's naming date), and keeps symbol-days whose pre-market high reached
``--touch`` (1.20) x the previous session's fully adjusted low. A rule that fires before the first
regular-session bar has price_t <= the pre-market high, and ref >= the previous low, so the union of
this list and the daily-high list holds every firing symbol-day.

GET only. Every page is kept (gzip) and hashed into a ledger; the run resumes by session. Output is
selection fields only (symbol, session_date, prev_date) for symbol-days not already candidates.

  python premarket_scan.py --env-file ENV --daily DAILY --exclude candidates-provable.csv --out DIR
  python premarket_scan.py --daily DAILY --exclude candidates-provable.csv --out DIR --finalize CSV
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect  # noqa: E402

ASOF = "2026-09-21"
BATCH = 400
DERIV = "((length(symbol) = 5 AND regexp_matches(symbol, '[A-Z]{4}[WUR]$')) OR regexp_matches(symbol, '\\.(WS|U|R|W)'))"


class Limiter:
    def __init__(self, per_second):
        self.gap, self.next, self.lock = 1.0 / per_second, time.monotonic(), threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            slot = max(self.next, now)
            self.next = slot + self.gap
        if slot > now:
            time.sleep(slot - now)


def universe(daily: Path, start: str):
    """{session: [(symbol, prev_date, prev_all_l)]} for every symbol-day with a previous daily row."""
    import duckdb
    con = duckdb.connect()
    rows = con.execute(f"""SELECT CAST(session_date AS VARCHAR), symbol, CAST(prev_d AS VARCHAR), prev_l FROM (
        SELECT symbol, session_date, lag(all_l) OVER w AS prev_l, lag(session_date) OVER w AS prev_d
        FROM read_parquet('{daily}') WHERE in_all WINDOW w AS (PARTITION BY symbol ORDER BY session_date))
        WHERE prev_l > 0 AND session_date >= DATE '{start}' AND session_date <= DATE '2026-09-18' AND NOT {DERIV}
        ORDER BY 1, 2""").fetchall()
    out = {}
    for day, sym, prev, low in rows:
        out.setdefault(day, []).append((sym, prev, low))
    return out


def fetch_session(headers, limiter, out: Path, day: str, syms: list):
    sdir = out / "sessions" / day
    sdir.mkdir(parents=True, exist_ok=True)
    recs, ok = [], True
    d = date.fromisoformat(day)
    for bi in range(0, len(syms), BATCH):
        params = {"symbols": ",".join(syms[bi:bi + BATCH]), "timeframe": "30Min", "start": collect.et_iso(d, 4),
                  "end": collect.et_iso(d, 9, 29), "feed": "sip", "adjustment": "all", "asof": ASOF, "limit": 10000}
        token, page = None, 0
        while True:
            q = dict(params, **({"page_token": token} if token else {}))
            url = collect.DATA + "/v2/stocks/bars?" + urllib.parse.urlencode(q)
            for attempt in range(6):
                limiter.wait()
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                        raw, status = r.read(), r.status
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                        time.sleep(2 ** attempt)
                        continue
                    raw, status = exc.read() or b"{}", exc.code
                    break
                except (urllib.error.URLError, TimeoutError):
                    if attempt < 5:
                        time.sleep(2 ** attempt)
                        continue
                    raw, status = b"{}", 0
                    break
            name = f"pm-{bi // BATCH:04d}-{page:04d}.json.gz"
            with gzip.open(sdir / name, "wb", compresslevel=6) as f:
                f.write(raw)
            recs.append({"event": "page", "session": day, "file": name, "status": status,
                         "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
            if status != 200:
                ok = False
                break
            token = json.loads(raw).get("next_page_token")
            page += 1
            if not token:
                break
    recs.append({"event": "session_complete" if ok else "session_incomplete", "session": day, "symbols": len(syms)})
    return recs


def ledger_state(path: Path):
    pages, done = {}, set()
    if path.exists():
        for line in path.read_text().splitlines():
            rec = json.loads(line)
            if rec["event"] == "page":
                pages.setdefault(rec["session"], {})[rec["file"]] = rec
            elif rec["event"] == "session_complete":
                done.add(rec["session"])
            elif rec["event"] == "session_incomplete":
                done.discard(rec["session"])
    return pages, done


def finalize(a, uni):
    pages, done = ledger_state(a.out / "ledger.jsonl")
    missing = sorted(set(uni) - done)
    if missing:
        raise SystemExit(f"{len(missing)} sessions not scanned (first {missing[:3]})")
    exclude = {(r["symbol"], r["session_date"]) for r in csv.DictReader(a.exclude.open(newline=""))}
    hits, touched_existing, scanned = [], 0, 0
    for day in sorted(uni):
        low = {s: (p, l) for s, p, l in uni[day]}
        high = {}
        for name, rec in sorted(pages[day].items()):
            raw = gzip.decompress((a.out / "sessions" / day / name).read_bytes())
            if hashlib.sha256(raw).hexdigest() != rec["sha256"]:
                raise SystemExit(f"page hash mismatch {day}/{name}")
            for sym, bars in (json.loads(raw).get("bars") or {}).items():
                for b in bars:
                    high[sym] = max(high.get(sym, 0.0), b["h"])
        scanned += len(low)
        for sym, h in sorted(high.items()):
            if sym in low and h >= a.touch * low[sym][1]:
                if (sym, day) in exclude:
                    touched_existing += 1
                else:
                    hits.append((sym, day, low[sym][0]))
    with a.finalize.open("w") as f:
        f.write("symbol,session_date,prev_date\n")
        for sym, day, prev in hits:
            f.write(f"{sym},{day},{prev}\n")
    os.chmod(a.finalize, 0o600)
    meta = {"sessions": len(uni), "symbol_days_scanned": scanned, "touch": a.touch, "new_candidates": len(hits),
            "premarket_touches_already_candidates": touched_existing, "asof": ASOF,
            "exclude_sha256": hashlib.sha256(a.exclude.read_bytes()).hexdigest(),
            "candidates_sha256": hashlib.sha256(a.finalize.read_bytes()).hexdigest()}
    Path(str(a.finalize) + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path)
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--exclude", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start", default="2021-01-04")
    ap.add_argument("--touch", type=float, default=1.20)
    ap.add_argument("--per-second", type=float, default=60.0)
    ap.add_argument("--threads", type=int, default=24)
    ap.add_argument("--finalize", type=Path)
    a = ap.parse_args(argv)
    uni = universe(a.daily, a.start)
    if a.finalize:
        return finalize(a, uni)
    a.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    lpath = a.out / "ledger.jsonl"
    _, done = ledger_state(lpath)
    todo = [d for d in sorted(uni) if d not in done]
    key, secret = collect.credentials(a.env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    limiter, lock = Limiter(a.per_second), threading.Lock()
    with lpath.open("a") as ledger:
        ledger.write(json.dumps({"event": "run_start", "at": datetime.now(timezone.utc).isoformat(), "sessions_todo": len(todo),
                                 "asof": ASOF, "batch": BATCH}) + "\n")
        ledger.flush()

        def work(day):
            recs = fetch_session(headers, limiter, a.out, day, [s for s, _, _ in uni[day]])
            with lock:
                for r in recs:
                    ledger.write(json.dumps(r) + "\n")
                ledger.flush()
            return recs[-1]["event"]

        n = 0
        with ThreadPoolExecutor(max_workers=a.threads) as pool:
            for ev in pool.map(work, todo):
                n += 1
                if n % 50 == 0:
                    print(json.dumps({"sessions_done": n, "of": len(todo), "last": ev}), flush=True)
    print(json.dumps({"sessions_done": len(todo)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
