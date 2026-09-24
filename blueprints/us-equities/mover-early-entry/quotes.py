"""Build the quote-measured cost table from a development-only entry sample (protocol.json costs).

  python quotes.py sample --signals SIGNALS_DEV.jsonl.gz --out SAMPLE.json
  python quotes.py fetch  --sample SAMPLE.json --env-file ENV --out QUOTES_DIR
  python quotes.py table  --sample SAMPLE.json --quotes QUOTES_DIR --out cost-table.json

``sample`` reads features.py signals output for development sessions only and keeps the entries the
loosest rule fires that have a fill (C5), one in twenty by a sha256 key. Each sampled entry gets
four fixed, exit-agnostic timestamps: the entry, entry + 15 min, entry + 60 min and 15:55.
``fetch`` requests the SIP quotes in the 60 s ending at each timestamp (newest first) and keeps
every page, hashed into a ledger (GET only; resumable). ``table`` takes the last quote at or before
each timestamp that is not crossed, locked or zero-priced, and builds the 5%-trimmed mean half-spread
per time x price tier x dollar-volume bucket with the protocol's fallbacks (C3, C9, C10). No exit
path is read or computed here.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules as R  # noqa: E402

PROTOCOL = json.loads((HERE / "protocol.json").read_text())
DEV = tuple(PROTOCOL["splits"]["development"])
MIN_CELL = 30


def sample_key(symbol: str, session: str, hhmm: str) -> bool:
    return int.from_bytes(hashlib.sha256(f"{symbol}|{session}|{hhmm}".encode()).digest()[:8], "big") % 20 == 0


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_sample(a) -> int:
    meta = json.loads(Path(str(a.signals) + ".meta.json").read_text())
    if meta["mode"] != "signals" or meta["split"] != "dev" or meta.get("max_sessions"):
        raise SystemExit("the cost sample reads a full development signals file only")
    fired, picked = 0, []
    h = hashlib.sha256()
    with gzip.open(a.signals, "rb") as f:
        for raw_line in f:
            h.update(raw_line)
            rec = json.loads(raw_line)
            if not (DEV[0] <= rec["session"] <= DEV[1]):
                raise SystemExit("non-development session in the signals file")
            for hhmm, row in sorted(rec["t"].items()):
                if not (row["loosest"] and row["entry"] is not None):
                    continue
                fired += 1
                if not sample_key(rec["symbol"], rec["session"], hhmm):
                    continue
                e = row["entry_ts"]
                # C26: the protocol's 15:55 stamp is 5 minutes before the session's close (13:00 on early closes)
                stamps = [(e, row["entry_cum_dv"], "entry"), (e + 900, row["sample_cum_dv"][0], "entry+15m"),
                          (e + 3600, row["sample_cum_dv"][1], "entry+60m"),
                          (R.et_epoch(rec["session"], R.close_hhmm(rec["session"])) - 300, row["sample_cum_dv"][2], "close-5m")]
                picked.append({"session": rec["session"], "symbol": rec["symbol"], "time": hhmm,
                               "entry_source": row["entry_source"], "stamps": stamps})
    if h.hexdigest() != meta["content_sha256"]:
        raise SystemExit("signals content hash mismatch")
    out = {"signals_content_sha256": meta["content_sha256"], "fired_entries": fired, "sampled_entries": len(picked),
           "requests": 4 * len(picked), "sample": picked}
    body = json.dumps(out, sort_keys=True, separators=(",", ":")).encode()
    a.out.write_bytes(body)
    os.chmod(a.out, 0o600)
    print(json.dumps({k: v for k, v in out.items() if k != "sample"} | {"sha256": hashlib.sha256(body).hexdigest()}))
    return 0


class Limiter:
    def __init__(self, per_second: float):
        self.gap, self.next, self.lock = 1.0 / per_second, time.monotonic(), threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            slot = max(self.next, now)
            self.next = slot + self.gap
        if slot > now:
            time.sleep(slot - now)


def fetch_one(client_headers, limiter, symbol, session, ts, max_pages=10):
    """Pages of quotes in [ts - 60 s, ts], newest first, until one is valid or the window ends."""
    import urllib.error
    import urllib.parse
    import urllib.request
    params = {"symbols": symbol, "start": iso(ts - 60), "end": iso(ts), "feed": "sip", "limit": 1000,
              "sort": "desc", "asof": PROTOCOL_ASOF}
    pages, token = [], None
    for _ in range(max_pages):
        q = dict(params, **({"page_token": token} if token else {}))
        url = "https://data.alpaca.markets/v2/stocks/quotes?" + urllib.parse.urlencode(q)
        for attempt in range(5):
            limiter.wait()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=client_headers), timeout=60) as r:
                    raw, status = r.read(), r.status
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 4:
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


PROTOCOL_ASOF = "2026-09-21"  # the candidate list's naming date (deviations.json D2)


def valid_quote(quotes):
    """The newest quote (input newest first) that is not crossed, locked or zero-priced."""
    for q in quotes:
        bp, ap = q.get("bp") or 0, q.get("ap") or 0
        if bp > 0 and ap > 0 and ap > bp:
            return q
    return None


def cmd_fetch(a) -> int:
    import collect
    key, secret = collect.credentials(a.env_file)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    sample = json.loads(a.sample.read_bytes())
    a.out.mkdir(parents=True, exist_ok=True, mode=0o700)
    ledger_path = a.out / "ledger.jsonl"
    done = set()
    if ledger_path.exists():
        for line in ledger_path.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("event") == "stamp_complete":
                done.add(rec["key"])
    todo = []
    for s in sample["sample"]:
        for ts, _, kind in s["stamps"]:
            k = f"{s['symbol']}|{s['session']}|{s['time']}|{kind}"
            if k not in done:
                todo.append((k, s["symbol"], s["session"], ts))
    limiter, lock = Limiter(a.per_second), threading.Lock()
    with ledger_path.open("a") as ledger:
        ledger.write(json.dumps({"event": "run_start", "at": datetime.now(timezone.utc).isoformat(), "todo": len(todo),
                                 "sample_sha256": hashlib.sha256(a.sample.read_bytes()).hexdigest()}) + "\n")

        def work(item):
            k, sym, session, ts = item
            pages = fetch_one(headers, limiter, sym, session, ts)
            name = hashlib.sha256(k.encode()).hexdigest()[:24]
            recs = []
            for i, (status, raw) in enumerate(pages):
                with gzip.open(a.out / f"{name}-{i:02d}.json.gz", "wb", compresslevel=6) as f:
                    f.write(raw)
                recs.append({"event": "page", "key": k, "file": f"{name}-{i:02d}.json.gz", "status": status,
                             "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
            ok = all(r["status"] == 200 for r in recs)
            recs.append({"event": "stamp_complete" if ok else "stamp_incomplete", "key": k, "pages": len(pages)})
            with lock:
                for r in recs:
                    ledger.write(json.dumps(r) + "\n")
                ledger.flush()

        n = 0
        with ThreadPoolExecutor(max_workers=a.threads) as pool:
            for _ in pool.map(work, todo):
                n += 1
                if n % 1000 == 0:
                    print(json.dumps({"stamps_done": n, "of": len(todo)}), flush=True)
    print(json.dumps({"stamps_done": len(todo)}))
    return 0


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


def cmd_table(a) -> int:
    sample_bytes = a.sample.read_bytes()
    sample = json.loads(sample_bytes)
    # One attempt's page records and its completion record are written together, so a key's pages
    # since its previous completion record belong to its latest attempt.
    attempt, status, closed = {}, {}, {}
    for line in (a.quotes / "ledger.jsonl").read_text().splitlines():
        rec = json.loads(line)
        k = rec.get("key")
        if rec.get("event") == "page":
            if closed.get(k, True):
                attempt[k], closed[k] = [], False
            attempt[k].append(rec)
        elif rec.get("event") in ("stamp_complete", "stamp_incomplete"):
            if closed.get(k, True):
                attempt[k] = []
            status[k], closed[k] = rec["event"], True
    obs, missing, incomplete, dropped = [], 0, 0, 0
    for s in sample["sample"]:
        for ts, cum_dv, kind in s["stamps"]:
            k = f"{s['symbol']}|{s['session']}|{s['time']}|{kind}"
            if status.get(k) != "stamp_complete":
                incomplete += 1
                continue
            quotes = []
            for p in attempt[k]:
                raw = gzip.decompress((a.quotes / p["file"]).read_bytes())
                if hashlib.sha256(raw).hexdigest() != p["sha256"]:
                    raise SystemExit(f"quote page hash mismatch: {p['file']}")
                quotes.extend((json.loads(raw).get("quotes") or {}).get(s["symbol"]) or [])
            q = valid_quote(quotes)
            if q is None:
                missing += 1
                continue
            dropped += quotes.index(q)
            mid = (q["ap"] + q["bp"]) / 2
            hs = (q["ap"] - q["bp"]) / (q["ap"] + q["bp"])
            tb = R.time_bucket(s["session"], ts)
            if tb is None:
                missing += 1
                continue
            obs.append((tb, R.price_tier(mid), R.dv_tier(cum_dv), hs, kind))
    pooled = [o[3] for o in obs]
    pooled_p90 = percentile(pooled, 0.90) if pooled else None
    # C9 (amended): "the table's 90th percentile" is over the table's own values: the cells that have a
    # measured value (>= 30 samples) or a time x price fallback value.
    measured = []
    for tb in range(len(R.TIME_BUCKETS)):
        for pt in range(len(R.PRICE_TIERS) + 1):
            tp = [o[3] for o in obs if o[0] == tb and o[1] == pt]
            for dt in range(len(R.DV_TIERS) + 1):
                xs = [o[3] for o in obs if o[0] == tb and o[1] == pt and o[2] == dt]
                if len(xs) >= MIN_CELL:
                    measured.append(trimmed_mean(xs))
                elif len(tp) >= MIN_CELL:
                    measured.append(trimmed_mean(tp))
    p90 = percentile(measured, 0.90) if measured else pooled_p90
    cells = {}
    for tb in range(len(R.TIME_BUCKETS)):
        for pt in range(len(R.PRICE_TIERS) + 1):
            tp = [o[3] for o in obs if o[0] == tb and o[1] == pt]
            for dt in range(len(R.DV_TIERS) + 1):
                xs = [o[3] for o in obs if o[0] == tb and o[1] == pt and o[2] == dt]
                if len(xs) >= MIN_CELL:
                    cell = {"half_spread": trimmed_mean(xs), "n": len(xs), "source": "cell"}
                elif len(tp) >= MIN_CELL:
                    cell = {"half_spread": trimmed_mean(tp), "n": len(xs), "n_fallback": len(tp), "source": "time_x_price"}
                else:
                    cell = {"half_spread": p90, "n": len(xs), "n_fallback": len(tp), "source": "table_p90"}
                cells[f"{tb}|{pt}|{dt}"] = cell
    out = {"schema_version": 1, "protocol": PROTOCOL["id"], "kind": "quote_measured_cost_table",
           "sample_sha256": hashlib.sha256(sample_bytes).hexdigest(), "signals_content_sha256": sample["signals_content_sha256"],
           "fired_entries_development": sample["fired_entries"], "sampled_entries": sample["sampled_entries"],
           "stamps": 4 * sample["sampled_entries"], "observations": len(obs), "stamps_without_valid_quote": missing,
           "stamps_incomplete": incomplete, "invalid_quotes_skipped_before_a_valid_one": dropped,
           "table_p90_half_spread": p90, "pooled_sample_p90_half_spread": pooled_p90, "min_cell": MIN_CELL,
           "time_buckets_et": [list(b) for b in R.TIME_BUCKETS], "price_tier_bounds": list(R.PRICE_TIERS),
           "dv_tier_bounds": list(R.DV_TIERS), "cell_key": "time_bucket|price_tier|dv_tier", "cells": cells,
           "observations_by_stamp": {k: sum(1 for o in obs if o[4] == k) for k in ("entry", "entry+15m", "entry+60m", "close-5m")}}
    a.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "cells"}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--signals", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--sample", type=Path, required=True)
    f.add_argument("--env-file", type=Path, required=True)
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--per-second", type=float, default=30.0)
    f.add_argument("--threads", type=int, default=16)
    t = sub.add_parser("table")
    t.add_argument("--sample", type=Path, required=True)
    t.add_argument("--quotes", type=Path, required=True)
    t.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    return {"sample": cmd_sample, "fetch": cmd_fetch, "table": cmd_table}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
