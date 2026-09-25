#!/usr/bin/env python3
"""Measured closing half-spreads on decision sessions D(t) for the EAP cost model (pre-freeze).

  python spreads.py sample --root ROOT --daily DAILY.parquet
  python spreads.py fetch  --root ROOT [--limit N]
  python spreads.py table  --root ROOT --out data/cost-table-eap-v1.json

``sample`` stratifies main-lane (symbol, D(t)) pairs of the study universe by calendar year of
D(t) x dollar-volume tier x price tier, using only raw close/volume before D(t), and keeps the
first K per cell in sha256 order (deterministic random draw). ``fetch`` requests Alpaca SIP
quotes in the 5 minutes before the close of D(t) (15:55-16:00 ET; 12:55-13:00 ET on the
listed early closes), newest first, from https://data.alpaca.markets only, and stores every
page gzipped with a sha256 manifest (GET only; resumable; <= 25 req/s before 03:30 ET and
<= 8 req/s from 03:30 to 20:00 ET). ``table`` takes the newest quote that is not crossed,
locked or zero-priced and builds the 5%-trimmed-mean half-spread per dollar-volume x price
cell. No trade price, return or outcome is read or computed.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import stat
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import expected_dates as E  # noqa: E402

ET = ZoneInfo("America/New_York")
DV_BOUNDS = [1e6, 5e6, 5e7, 5e8]           # tiers: [1,5)M, [5,50)M, [50,500)M, >=500M
PRICE_BOUNDS = [5.0, 20.0, 100.0]          # tiers: [5,20), [20,100), >=100
PER_CELL = 25
MIN_CELL = 30
TRIM = 0.05
EARLY_CLOSE_DECISIONS = {date(2019, 11, 29), date(2024, 11, 29), date(2025, 11, 28)}
ENV = Path("~/.config/codex-ecosystem/secrets/alpaca-paper-2.env").expanduser()
HOST = "https://data.alpaca.markets"
SEED = "sota-mover-eap-v1-20260925/spreads"


def tier(x: float, bounds: list[float]) -> int | None:
    if x < bounds[0]:
        return None
    k = 0
    for i, b in enumerate(bounds):
        if x >= b:
            k = i
    return k


def draw_key(symbol: str, d: date) -> str:
    return hashlib.sha256(f"{SEED}|{symbol}|{d}".encode()).hexdigest()


def stratified_sample(pairs: list[tuple[str, date, float, float]], per_cell: int = PER_CELL) -> list[dict]:
    """pairs: (symbol, D, prior raw close, prior-20 median dollar volume) of main-lane names."""
    cells = defaultdict(list)
    for sym, d, px, dv in pairs:
        dt, pt = tier(dv, DV_BOUNDS), tier(px, PRICE_BOUNDS)
        if dt is None or pt is None:
            continue
        cells[(d.year, dt, pt)].append((draw_key(sym, d), sym, d, px, dv))
    out = []
    for (y, dt, pt), xs in sorted(cells.items()):
        for _, sym, d, px, dv in sorted(xs)[:per_cell]:
            out.append({"symbol": sym, "d": d.isoformat(), "year": y, "dv_tier": dt, "price_tier": pt,
                        "prior_raw_close": px, "median_dv": dv, "cell_population": len(xs)})
    return out


def window(d: date) -> tuple[str, str]:
    close = (13, 0) if d in EARLY_CLOSE_DECISIONS else (16, 0)
    end = datetime(d.year, d.month, d.day, *close, tzinfo=ET)
    start = end.replace(minute=55, hour=end.hour - 1)
    z = lambda t: t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return z(start), z(end)


def valid_quote(quotes: list[dict]) -> dict | None:
    for q in quotes:
        bp, ap = q.get("bp") or 0, q.get("ap") or 0
        if bp > 0 and ap > 0 and ap > bp:
            return q
    return None


def half_spread_of(q: dict) -> float:
    return (q["ap"] - q["bp"]) / (q["ap"] + q["bp"])


def trimmed_mean(xs: list[float], trim: float = TRIM) -> float:
    s = sorted(xs)
    k = int(len(s) * trim)
    s = s[k: len(s) - k] if len(s) - 2 * k > 0 else s
    return sum(s) / len(s)


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def build_table(samples: list[dict], spreads: dict[tuple[str, str], float]) -> dict:
    cells, tiers, years = defaultdict(list), defaultdict(list), defaultdict(list)
    for s in samples:
        v = spreads.get((s["symbol"], s["d"]))
        if v is None:
            continue
        cells[(s["dv_tier"], s["price_tier"])].append(v)
        tiers[s["dv_tier"]].append(v)
        years[(s["dv_tier"], s["year"])].append(v)
    rows = []
    for dt in range(len(DV_BOUNDS)):
        for pt in range(len(PRICE_BOUNDS)):
            xs = cells.get((dt, pt), [])
            pooled = tiers.get(dt, [])
            use_cell = len(xs) >= MIN_CELL
            src = xs if use_cell else pooled
            rows.append({"dv_tier": dt, "price_tier": pt,
                         "dv_min": DV_BOUNDS[dt], "dv_max": DV_BOUNDS[dt + 1] if dt + 1 < len(DV_BOUNDS) else 1e30,
                         "price_min": PRICE_BOUNDS[pt], "price_max": PRICE_BOUNDS[pt + 1] if pt + 1 < len(PRICE_BOUNDS) else 1e18,
                         "n": len(xs), "source": "cell" if use_cell else "dv_tier_pooled", "n_source": len(src),
                         "median": median(xs) if xs else None,
                         "half_spread": trimmed_mean(src) if src else None})
    return {"rows": rows,
            "dv_tier_median": {str(dt): median(v) for dt, v in sorted(tiers.items())},
            "dv_tier_n": {str(dt): len(v) for dt, v in sorted(tiers.items())},
            "dv_tier_year_median": {f"{dt}|{y}": median(v) for (dt, y), v in sorted(years.items())}}


# ---------------------------------------------------------------- CLI

def cmd_sample(a) -> None:
    import eap_signal as S
    con = S.duck(a.root)
    sessions = E.load_sessions(con, a.daily)
    universe = json.loads((a.root / "universe.json").read_text())["ciks"]
    symbols = {s for v in universe.values() for s in v}
    months = E.study_months()
    decisions = [E.decision_session(sessions, t) for t in months]
    inputs = S.load_lane_inputs(con, a.daily, sessions, decisions, symbols)
    pairs = [(sym, d, v[0], v[1]) for d in decisions for sym, v in inputs[d].items() if S.lane(sym, *v) == "main"]
    samples = stratified_sample(pairs)
    body = json.dumps({"seed": SEED, "per_cell": PER_CELL, "dv_bounds": DV_BOUNDS, "price_bounds": PRICE_BOUNDS,
                       "samples": samples}, sort_keys=True, indent=0).encode()
    out = a.root / "spreads"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sample.json").write_bytes(body)
    print(json.dumps({"main_lane_pairs": len(pairs), "samples": len(samples),
                      "cells": len({(s['year'], s['dv_tier'], s['price_tier']) for s in samples}),
                      "sample_sha256": hashlib.sha256(body).hexdigest()}))


def credentials(path: Path = ENV) -> tuple[str, str]:
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise SystemExit("credential file must be owned by this user with mode 0600")
    found = {}
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
                found[k.strip()] = v.strip().strip("'\"")
    if len(found) != 2:
        raise SystemExit("credential file lacks the paper key pair")
    return found["APCA_API_KEY_ID"], found["APCA_API_SECRET_KEY"]


def allowed_rate(now_et: datetime) -> float:
    """Requests/s: 25 (1,500/min) outside 03:30-20:00 ET, else 8 (480/min)."""
    hm = now_et.hour * 60 + now_et.minute
    return 8.0 if 3 * 60 + 30 <= hm < 20 * 60 else 25.0


class Limiter:
    def __init__(self):
        self.lock, self.next_at = threading.Lock(), 0.0

    def wait(self):
        with self.lock:
            interval = 1.0 / allowed_rate(datetime.now(ET))
            t = time.monotonic()
            if t < self.next_at:
                time.sleep(self.next_at - t)
                t = self.next_at
            self.next_at = t + interval


def fetch_sample(s: dict, headers: dict, limiter: Limiter, tally: Counter, lock: threading.Lock, max_pages: int = 3) -> list[tuple[int, bytes]]:
    start, end = window(date.fromisoformat(s["d"]))
    params = {"symbols": s["symbol"], "start": start, "end": end, "feed": "sip", "limit": 1000, "sort": "desc"}
    pages, token = [], None
    for _ in range(max_pages):
        q = dict(params, **({"page_token": token} if token else {}))
        url = f"{HOST}/v2/stocks/quotes?" + urllib.parse.urlencode(q)
        assert url.startswith(HOST + "/v2/stocks/quotes?")
        raw, status = b"", -1
        for attempt in range(5):
            limiter.wait()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                    raw, status = r.read(), r.status
            except urllib.error.HTTPError as exc:
                raw, status = exc.read() or b"{}", exc.code
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                raw, status = b"", type(exc).__name__
            with lock:
                tally[str(status)] += 1
            if status in (429, 500, 502, 503, 504) or isinstance(status, str):
                time.sleep(2 ** (attempt + 1))
                continue
            break
        pages.append((status, raw))
        if status != 200:
            break
        body = json.loads(raw)
        if valid_quote((body.get("quotes") or {}).get(s["symbol"]) or []) is not None:
            break
        token = body.get("next_page_token")
        if not token:
            break
    return pages


def cmd_fetch(a) -> None:
    out = a.root / "spreads"
    pages_dir = out / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.jsonl"
    done = set()
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("kind") == "sample_done":
                done.add((r["symbol"], r["d"]))
    samples = [s for s in json.loads((out / "sample.json").read_text())["samples"] if (s["symbol"], s["d"]) not in done]
    if a.limit:
        samples = samples[: a.limit]
    key, secret = credentials()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    limiter, lock, tally = Limiter(), threading.Lock(), Counter()
    t0 = time.monotonic()

    def one(s):
        pages = fetch_sample(s, headers, limiter, tally, lock)
        recs = []
        for i, (status, raw) in enumerate(pages):
            name = f"{s['symbol'].replace('/', '_')}_{s['d']}_{i}.json.gz"
            (pages_dir / name).write_bytes(gzip.compress(raw, mtime=0))
            recs.append({"kind": "page", "symbol": s["symbol"], "d": s["d"], "page": i, "status": status,
                         "file": f"spreads/pages/{name}", "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        ok = bool(pages) and all(p[0] == 200 for p in pages)
        recs.append({"kind": "sample_done" if ok else "sample_error", "symbol": s["symbol"], "d": s["d"], "pages": len(pages)})
        with lock, manifest.open("a") as f:
            for r in recs:
                f.write(json.dumps(r, sort_keys=True) + "\n")
        return ok

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, samples))
    el = time.monotonic() - t0
    req = sum(tally.values())
    rec = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "samples": len(samples),
           "ok": sum(results), "http": dict(tally), "requests": req, "elapsed_s": round(el, 1),
           "mean_per_min": round(60 * req / el, 1) if el else None}
    with (out / "fetch-runs.jsonl").open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    print(json.dumps(rec, sort_keys=True))


def cmd_table(a) -> None:
    out = a.root / "spreads"
    sample_bytes = (out / "sample.json").read_bytes()
    samples = json.loads(sample_bytes)["samples"]
    manifest_bytes = (out / "manifest.jsonl").read_bytes()
    pages = defaultdict(list)
    for line in manifest_bytes.decode().splitlines():
        r = json.loads(line)
        if r["kind"] == "page" and r["status"] == 200:
            pages[(r["symbol"], r["d"])].append(r)
    spreads, reasons = {}, Counter()
    for key, recs in pages.items():
        q = None
        for r in sorted(recs, key=lambda r: r["page"]):
            raw = gzip.decompress((a.root / r["file"]).read_bytes())
            if hashlib.sha256(raw).hexdigest() != r["sha256"]:
                raise SystemExit(f"page hash mismatch {r['file']}")
            q = valid_quote((json.loads(raw).get("quotes") or {}).get(key[0]) or [])
            if q:
                break
        if q:
            spreads[key] = half_spread_of(q)
        else:
            reasons["no_valid_quote_in_window"] += 1
    table = build_table(samples, spreads)
    runs = [json.loads(l) for l in (out / "fetch-runs.jsonl").read_text().splitlines() if l.strip()]
    http = Counter()
    for r in runs:
        http.update(r["http"])
    doc = {"schema_version": 1, "kind": "eap_measured_closing_half_spread_table", "label": "HIST",
           "outcomes_computed": False,
           "method": "Alpaca SIP /v2/stocks/quotes, newest valid (not crossed, locked or zero) quote in the 5 minutes before the D(t) close; half-spread = (ask-bid)/(ask+bid); cell value = 5%-trimmed mean; cells with n < 30 use their dollar-volume tier pooled",
           "strata": {"years": "calendar year of D(t), 2016-12..2026-07 decisions", "dv_bounds": DV_BOUNDS, "price_bounds": PRICE_BOUNDS, "per_cell": PER_CELL},
           "early_close_decisions": sorted(d.isoformat() for d in EARLY_CLOSE_DECISIONS),
           "samples": len(samples), "measured": len(spreads), "missing": dict(reasons),
           "requests": sum(r["requests"] for r in runs), "http": dict(http), "fetch_runs": runs,
           "sample_sha256": hashlib.sha256(sample_bytes).hexdigest(),
           "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
           "private_files": "~/.local/state/native-agent-stack/research/sota-mover/eap/spreads/", **table}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in ("samples", "measured", "missing", "requests", "http", "dv_tier_median", "dv_tier_n")}, sort_keys=True))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for n in ("sample", "fetch", "table"):
        s = sub.add_parser(n)
        s.add_argument("--root", type=Path, default=Path("~/.local/state/native-agent-stack/research/sota-mover/eap").expanduser())
    sub.choices["sample"].add_argument("--daily", type=Path, required=True)
    sub.choices["fetch"].add_argument("--limit", type=int, default=0)
    sub.choices["table"].add_argument("--out", type=Path, default=HERE / "data" / "cost-table-eap-v1.json")
    a = p.parse_args(argv)
    {"sample": cmd_sample, "fetch": cmd_fetch, "table": cmd_table}[a.cmd](a)


if __name__ == "__main__":
    main()
