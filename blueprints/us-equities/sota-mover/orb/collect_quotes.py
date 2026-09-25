"""SIP quote spreads at ORB signal times, for the F1/F2 cost table (protocol.json cost_table).

  python collect_quotes.py sample                       # preregistered sha-keyed sample of fired orders
  python collect_quotes.py fetch --env-file ENV         # GET data.alpaca.markets/v2/stocks/quotes only
  python collect_quotes.py table                        # half-spread cells per segment group

Follows the mover v1 method (mover-early-entry/quotes.py): four fixed, exit-agnostic stamps per sampled
order (end of the trigger minute, +15 min, +60 min, close - 5 min), the newest valid quote in the 60 s
ending at each stamp, 5%-trimmed cell means with time x price and table-p90 fallbacks. Measures cost at
signal times only; it never reads a fill, stop, exit or return. Every page is gzip-kept and hashed in a
ledger; the fetch is resumable and GET-only. Stdlib only.
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
import hashlib
import json
import math
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import orb_common as C  # noqa: E402

ET = ZoneInfo("America/New_York")
HOST = "https://data.alpaca.markets"
PATH = "/v2/stocks/quotes"
ASOF = "2026-09-22"  # the minute corpus's collection date (current-ticker identities)
SAMPLE_RATE = {"reproduction": 10, "post_publication": 5}  # 1-in-N by sha256 key, fixed before fetching
MIN_CELL = 30
TIME_BUCKETS = ((575, 600), (600, 660), (660, 930), (930, 961))  # [09:35,10:00) [10:00,11:00) [11:00,15:30) [15:30,close]
PRICE_TIERS = (20.0, 50.0, 200.0)       # [5,20) [20,50) [50,200) [200,inf)
LIQ_TIERS = (100e6, 500e6)              # 14-day average dollar volume [0,100M) [100M,500M) [500M,inf)
STAMP_KINDS = ("trigger", "trigger+15m", "trigger+60m", "close-5m")
MAX_PER_MINUTE = 2000
MAX_PER_MINUTE_AFTER_0330 = 500


def et_epoch(day: str, minute: float) -> float:
    return datetime.combine(date.fromisoformat(day), dtime(0, 0), ET).timestamp() + minute * 60


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sample_key(symbol: str, day: str, dirn: int, n: int) -> bool:
    return int.from_bytes(hashlib.sha256(f"{symbol}|{day}|{dirn}".encode()).digest()[:8], "big") % n == 0


def stamps_for(day: str, trigger_minute: int, close_minute: int):
    """[(epoch, minute_of_stamp, kind)]: end of the trigger minute, +15, +60, close-5; later stamps that
    reach close-5 are dropped (close-5 itself is kept)."""
    c5 = close_minute - 5
    out = [(trigger_minute + 1, "trigger")]
    for add, kind in ((15, "trigger+15m"), (60, "trigger+60m")):
        if trigger_minute + 1 + add < c5:
            out.append((trigger_minute + 1 + add, kind))
    out.append((c5, "close-5m"))
    return [(et_epoch(day, m), m, k) for m, k in out]


def time_bucket(minute: float, close_minute: int):
    """Bucket of a stamp at `minute` (the stamp is the end of its measured window)."""
    for i, (a, b) in enumerate(TIME_BUCKETS):
        hi = close_minute + 1 if i == len(TIME_BUCKETS) - 1 else b
        if a <= minute < hi:
            return i
    return None


def tier(x: float, bounds) -> int:
    return sum(1 for b in bounds if x >= b)


# ------------------------------------------------------------------ sample

def cmd_sample(a) -> int:
    close_of = dict(C.calendar())
    sel = {}
    with open(C.PRIVATE / "selected.csv", newline="") as f:
        for r in csv.DictReader(f):
            sel[(r["d"], r["symbol"])] = r
    picked, fired = [], Counter()
    with open(C.PRIVATE / "triggers.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["trigger_minute"] == "":
                continue
            seg, d, sym, dirn = r["segment"], r["d"], r["symbol"], int(r["dirn"])
            fired[seg] += 1
            if not sample_key(sym, d, dirn, SAMPLE_RATE[seg]):
                continue
            s = sel[(d, sym)]
            adv = float(s["avgvol14"]) * float(s["or_open"])
            picked.append({"d": d, "segment": seg, "symbol": sym, "dirn": dirn, "liq_tier": tier(adv, LIQ_TIERS),
                           "close_minute": close_of[d],
                           "stamps": stamps_for(d, int(r["trigger_minute"]), close_of[d])})
    out = {"kind": "orb_cost_sample", "sample_rate": SAMPLE_RATE, "asof": ASOF, "fired": dict(fired),
           "sampled": dict(Counter(p["segment"] for p in picked)), "stamps": sum(len(p["stamps"]) for p in picked),
           "triggers_sha256": C.sha256_file(C.PRIVATE / "triggers.csv"),
           "selected_sha256": C.sha256_file(C.PRIVATE / "selected.csv"), "sample": picked}
    qdir = C.private_dir("quotes")
    sha = C.write_private_json(qdir / "sample.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "sample"} | {"sha256": sha}))
    return 0


# ------------------------------------------------------------------ fetch

def credentials(env_file: Path):
    """Read only the paper data-key pair from a guarded env file, inside this process."""
    sys.path.insert(1, str(C.REPO / "blueprints/us-equities/adaptive-paper"))
    from credential_guard import open_verified  # noqa: E402
    with open_verified(env_file, follow_symlinks=False) as h:
        raw = h.read(4097)
    if len(raw) > 4096:
        raise SystemExit("credential file too large")
    found = {}
    for line in raw.decode("ascii").splitlines():
        line = line.strip().removeprefix("export ")
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
                found[k.strip()] = v.strip().strip("'\"")
    if len(found) != 2:
        raise SystemExit("credential file lacks the key pair")
    return {"APCA-API-KEY-ID": found["APCA_API_KEY_ID"], "APCA-API-SECRET-KEY": found["APCA_API_SECRET_KEY"]}


def allowed_per_minute(now: datetime | None = None) -> int:
    """2,000/min, or 500/min from 03:30 ET until 20:00 ET (live monitors share the budget)."""
    now = (now or datetime.now(timezone.utc)).astimezone(ET)
    minute = now.hour * 60 + now.minute
    return MAX_PER_MINUTE_AFTER_0330 if 210 <= minute < 1200 else MAX_PER_MINUTE


class Limiter:
    def __init__(self, per_minute: int):
        self.requested = per_minute
        self.next, self.lock, self.count = time.monotonic(), threading.Lock(), 0

    def wait(self):
        per_min = min(self.requested, allowed_per_minute())
        gap = 60.0 / per_min
        with self.lock:
            now = time.monotonic()
            slot = max(self.next, now)
            self.next = slot + gap
            self.count += 1
        if slot > now:
            time.sleep(slot - now)


def valid_quote(quotes):
    """The newest quote (input newest first) with bid > 0 and ask > bid."""
    for q in quotes:
        bp, ap = q.get("bp") or 0, q.get("ap") or 0
        if bp > 0 and ap > 0 and ap > bp:
            return q
    return None


def fetch_stamp(headers, limiter, symbol, ts, max_pages=10):
    params = {"symbols": symbol, "start": iso(ts - 60), "end": iso(ts), "feed": "sip", "limit": 1000,
              "sort": "desc", "asof": ASOF}
    pages, token = [], None
    for _ in range(max_pages):
        q = dict(params, **({"page_token": token} if token else {}))
        url = HOST + PATH + "?" + urllib.parse.urlencode(q)
        assert url.startswith(HOST + PATH + "?")
        for attempt in range(5):
            limiter.wait()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method="GET"),
                                            timeout=60) as r:
                    raw, status = r.read(), r.status
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 4:
                    pages.append((exc.code, b""))
                    time.sleep(2 ** attempt)
                    continue
                raw, status = exc.read() or b"{}", exc.code
                break
            except (urllib.error.URLError, TimeoutError):
                if attempt < 4:
                    time.sleep(2 ** attempt)
                    continue
                raise
        pages.append((status, raw))
        if status != 200:
            break
        body = json.loads(raw)
        if valid_quote((body.get("quotes") or {}).get(symbol) or []) is not None:
            break
        token = body.get("next_page_token")
        if not token:
            break
    return pages


def stamp_key(p, kind):
    return f"{p['symbol']}|{p['d']}|{p['dirn']}|{kind}"


def cmd_fetch(a) -> int:
    qdir = C.PRIVATE / "quotes"
    sample_bytes = (qdir / "sample.json").read_bytes()
    sample = json.loads(sample_bytes)
    headers = credentials(a.env_file)
    ledger_path = qdir / "ledger.jsonl"
    done = set()
    if ledger_path.exists():
        for line in ledger_path.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("event") == "stamp_complete":
                done.add(rec["key"])
            elif rec.get("event") == "stamp_incomplete":
                done.discard(rec["key"])
    todo = [(stamp_key(p, kind), p["symbol"], ts) for p in sample["sample"] for ts, _, kind in p["stamps"]
            if stamp_key(p, kind) not in done]
    limiter, lock = Limiter(a.per_minute), threading.Lock()
    pages_dir = C.private_dir("quotes", "pages")
    with ledger_path.open("a") as ledger:
        ledger.write(json.dumps({"event": "run_start", "at": datetime.now(timezone.utc).isoformat(), "todo": len(todo),
                                 "per_minute": a.per_minute,
                                 "sample_sha256": hashlib.sha256(sample_bytes).hexdigest()}) + "\n")

        def work(item):
            k, sym, ts = item
            pages = fetch_stamp(headers, limiter, sym, ts)
            name = hashlib.sha256(k.encode()).hexdigest()[:24]
            recs = []
            for i, (status, raw) in enumerate(pages):
                rec = {"event": "page", "key": k, "status": status, "sha256": hashlib.sha256(raw).hexdigest(),
                       "bytes": len(raw)}
                if status == 200:
                    fn = f"{name}-{i:02d}.json.gz"
                    with gzip.open(pages_dir / fn, "wb", compresslevel=6) as f:
                        f.write(raw)
                    rec["file"] = fn
                recs.append(rec)
            final = [r for r in recs if r["status"] == 200 or r is recs[-1]]
            ok = bool(recs) and recs[-1]["status"] == 200
            recs.append({"event": "stamp_complete" if ok else "stamp_incomplete", "key": k, "ts": ts,
                         "pages": len(final)})
            with lock:
                for r in recs:
                    ledger.write(json.dumps(r) + "\n")
                ledger.flush()

        n = 0
        with ThreadPoolExecutor(max_workers=a.threads) as pool:
            for _ in pool.map(work, todo):
                n += 1
                if n % 2000 == 0:
                    print(json.dumps({"stamps_done": n, "of": len(todo), "requests": limiter.count}), flush=True)
    print(json.dumps({"stamps_done": len(todo), "requests": limiter.count}))
    return 0


# ------------------------------------------------------------------ table

def trimmed_mean(xs, cut=0.05):
    xs = sorted(xs)
    k = int(math.floor(cut * len(xs)))
    kept = xs[k: len(xs) - k] if k else xs
    return math.fsum(kept) / len(kept)


def percentile(xs, q):
    xs = sorted(xs)
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def build_cells(obs):
    """obs: [(time_bucket, price_tier, liq_tier, half_spread)] -> {"t|p|l": cell}, table p90."""
    nt, npr, nl = len(TIME_BUCKETS), len(PRICE_TIERS) + 1, len(LIQ_TIERS) + 1
    by_cell, by_tp = {}, {}
    for t, p, liq, hs in obs:
        by_cell.setdefault((t, p, liq), []).append(hs)
        by_tp.setdefault((t, p), []).append(hs)
    measured = []
    for t in range(nt):
        for p in range(npr):
            for liq in range(nl):
                xs, tp = by_cell.get((t, p, liq), []), by_tp.get((t, p), [])
                if len(xs) >= MIN_CELL:
                    measured.append(trimmed_mean(xs))
                elif len(tp) >= MIN_CELL:
                    measured.append(trimmed_mean(tp))
    pooled = [o[3] for o in obs]
    p90 = percentile(measured, 0.90) if measured else (percentile(pooled, 0.90) if pooled else None)
    cells = {}
    for t in range(nt):
        for p in range(npr):
            for liq in range(nl):
                xs, tp = by_cell.get((t, p, liq), []), by_tp.get((t, p), [])
                if len(xs) >= MIN_CELL:
                    cells[f"{t}|{p}|{liq}"] = {"half_spread": trimmed_mean(xs), "n": len(xs), "source": "cell"}
                elif len(tp) >= MIN_CELL:
                    cells[f"{t}|{p}|{liq}"] = {"half_spread": trimmed_mean(tp), "n": len(xs), "n_fallback": len(tp),
                                               "source": "time_x_price"}
                else:
                    cells[f"{t}|{p}|{liq}"] = {"half_spread": p90, "n": len(xs), "n_fallback": len(tp),
                                               "source": "table_p90"}
    return cells, p90


def quote_epoch(ts: str) -> float:
    head, _, frac = ts.rstrip("Z").partition(".")
    return datetime.fromisoformat(head).replace(tzinfo=timezone.utc).timestamp() + (float("0." + frac) if frac else 0.0)


def cmd_table(a) -> int:
    qdir = C.PRIVATE / "quotes"
    sample_bytes = (qdir / "sample.json").read_bytes()
    sample = json.loads(sample_bytes)
    attempt, status, closed = {}, {}, {}
    http = Counter()
    requests = 0
    for line in (qdir / "ledger.jsonl").read_text().splitlines():
        rec = json.loads(line)
        k = rec.get("key")
        if rec.get("event") == "page":
            requests += 1
            http[str(rec["status"])] += 1
            if closed.get(k, True):
                attempt[k], closed[k] = [], False
            attempt[k].append(rec)
        elif rec.get("event") in ("stamp_complete", "stamp_incomplete"):
            if closed.get(k, True):
                attempt[k] = []
            status[k], closed[k] = rec["event"], True
    obs = {"reproduction": [], "post_publication": []}
    tally = Counter()
    for p in sample["sample"]:
        for ts, minute, kind in p["stamps"]:
            k = stamp_key(p, kind)
            if status.get(k) != "stamp_complete":
                tally["stamps_incomplete"] += 1
                continue
            quotes = []
            for pg in attempt[k]:
                if pg["status"] != 200:
                    continue
                raw = gzip.decompress((qdir / "pages" / pg["file"]).read_bytes())
                if hashlib.sha256(raw).hexdigest() != pg["sha256"]:
                    raise SystemExit(f"quote page hash mismatch: {pg['file']}")
                quotes.extend((json.loads(raw).get("quotes") or {}).get(p["symbol"]) or [])
            if not all(ts - 60 - 1e-6 <= quote_epoch(q["t"]) <= ts + 1e-6 for q in quotes):
                raise SystemExit(f"stamp {k}: quotes outside [ts - 60 s, ts]")
            q = valid_quote(quotes)
            if q is None:
                tally["stamps_without_valid_quote"] += 1
                continue
            mid = (q["ap"] + q["bp"]) / 2
            hs = (q["ap"] - q["bp"]) / (q["ap"] + q["bp"])
            tb = time_bucket(minute, p["close_minute"])
            obs[p["segment"]].append((tb, tier(mid, PRICE_TIERS), p["liq_tier"], hs, kind))
            tally[f"obs:{p['segment']}:{kind}"] += 1
    out = {"schema_version": 1, "kind": "orb_quote_cost_table", "label": "HIST", "protocol": C.load_json(C.PROTOCOL_PATH)["id"],
           "sample_sha256": hashlib.sha256(sample_bytes).hexdigest(), "sample_rate": sample["sample_rate"],
           "fired": sample["fired"], "sampled": sample["sampled"], "stamps": sample["stamps"],
           "requests": requests, "http_status": dict(http), "tally": dict(tally), "min_cell": MIN_CELL,
           "time_buckets_et_minutes": [list(b) for b in TIME_BUCKETS], "price_tier_bounds": list(PRICE_TIERS),
           "liq_tier_bounds_usd": list(LIQ_TIERS), "cell_key": "time_bucket|price_tier|liq_tier", "groups": {}}
    for g, xs in obs.items():
        cells, p90 = build_cells([o[:4] for o in xs])
        hs = [o[3] for o in xs]
        entry = [o[3] for o in xs if o[4] == "trigger"]
        out["groups"][g] = {"observations": len(xs), "table_p90_half_spread": p90,
                            "median_half_spread": percentile(hs, 0.5) if hs else None,
                            "median_half_spread_at_trigger": percentile(entry, 0.5) if entry else None,
                            "cells": cells}
    path = C.PRIVATE / "cost-table.json"
    sha = C.write_private_json(path, out)
    print(json.dumps({k: v for k, v in out.items() if k != "groups"} | {
        "groups": {g: {kk: vv for kk, vv in v.items() if kk != "cells"} for g, v in out["groups"].items()},
        "sha256": sha}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sample")
    f = sub.add_parser("fetch")
    f.add_argument("--env-file", type=Path, required=True)
    f.add_argument("--per-minute", type=int, default=1500)
    f.add_argument("--threads", type=int, default=12)
    sub.add_parser("table")
    a = ap.parse_args(argv)
    if a.cmd == "fetch" and not (0 < a.per_minute <= MAX_PER_MINUTE):
        raise SystemExit("per-minute must be in 1..2000")
    return {"sample": cmd_sample, "fetch": cmd_fetch, "table": cmd_table}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
