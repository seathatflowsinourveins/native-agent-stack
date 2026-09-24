"""Live pre-market/early-session scanner for one mover rule (protocol mover-early-entry-v1-20260924).

  python mover_scan.py --env-file ENV --rule "08:00|G0.20|V250000|any" --out scan.json --pages DIR
  python mover_scan.py --replay DIR --rule ... --at 2026-09-24T08:00:05-04:00 --out scan.json

At or after the rule's time t it evaluates the rule exactly as the historical study does (rules.py):
price_at_t and dollar_volume_at_t from SIP 1-minute bars starting 04:00 and before t (09:28 for the
09:30 rule), ref = the previous session's official close (sessions_io.official_price on the auction
prints) divided by a split factor, gain_at_t = price_at_t / ref - 1, price >= $1, and headlines at
least 120 s before t for the news variant. The universe is every active, tradable Alpaca US equity on
NASDAQ/NYSE/ARCA/AMEX/BATS, less likely warrants, units and rights; a snapshot pass keeps symbols whose
latest trade is at least (1 + 0.9 G) x the previous daily close before bars are requested. Fired
symbols are ranked by dollar_volume_at_t descending, then symbol; the first five are the trial's
universe. The regime factor (C4) comes from SPY's adjusted daily closes.

GET only. Every response is kept (gzip) under --pages with a sha256 ledger, and --replay re-derives the
same scan from those pages without network access (the tests use this).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules as R  # noqa: E402
from sessions_io import official_price  # noqa: E402

DATA = "https://data.alpaca.markets"
TRADING = "https://paper-api.alpaca.markets"
EXCHANGES = {"NASDAQ", "NYSE", "ARCA", "AMEX", "BATS"}
DERIV = re.compile(r"^[A-Z]{4}[WUR]$|\.(WS|U|R|W)")
PREFILTER = 0.9  # latest trade >= (1 + 0.9 G) x previous daily close
TOP = 5


def parse_rule(rule: str):
    t, g, v, n = rule.split("|")
    if t not in R.TIMES or n not in R.NEWS:
        raise SystemExit(f"unknown rule {rule}")
    return t, float(g[1:]), float(v[1:]), n


def req_key(path: str, params: dict) -> str:
    return hashlib.sha256((path + "?" + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:32]


class Fetcher:
    """HTTP GET with page retention, or replay of retained pages by request key."""

    def __init__(self, pages: Path, headers=None, replay=False):
        self.pages, self.headers, self.replay = pages, headers, replay
        self.ledger = {}
        lpath = pages / "ledger.jsonl"
        if lpath.exists():
            for line in lpath.read_text().splitlines():
                rec = json.loads(line)
                self.ledger[rec["key"]] = rec
        if not replay:
            pages.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.lfile = lpath.open("a")

    def get(self, base: str, path: str, params: dict):
        """Yields parsed pages following next_page_token."""
        token = None
        while True:
            q = dict(params, **({"page_token": token} if token else {}))
            key = req_key(base + path, q)
            if self.replay:
                rec = self.ledger[key]
                raw = gzip.decompress((self.pages / rec["file"]).read_bytes())
                if hashlib.sha256(raw).hexdigest() != rec["sha256"]:
                    raise SystemExit(f"page hash mismatch {rec['file']}")
                status = rec["status"]
            else:
                url = base + path + "?" + urllib.parse.urlencode(q)
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=self.headers), timeout=30) as r:
                        raw, status = r.read(), r.status
                except urllib.error.HTTPError as exc:
                    raw, status = exc.read() or b"{}", exc.code
                name = f"{key}.json.gz"
                with gzip.open(self.pages / name, "wb", compresslevel=6) as f:
                    f.write(raw)
                self.lfile.write(json.dumps({"key": key, "file": name, "path": path, "status": status,
                                             "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}) + "\n")
                self.lfile.flush()
            if status != 200:
                raise SystemExit(f"GET {path} returned {status}")
            body = json.loads(raw)
            yield body
            token = body.get("next_page_token") if isinstance(body, dict) else None
            if not token:
                return


def et_iso(day: str, hhmm: str, second_offset: int = 0) -> str:
    return datetime.fromtimestamp(R.et_epoch(day, hhmm) + second_offset, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def universe(f: Fetcher):
    assets = []
    for body in f.get(TRADING, "/v2/assets", {"status": "active", "asset_class": "us_equity"}):
        assets.extend(body if isinstance(body, list) else [])
    return sorted(a["symbol"] for a in assets if a.get("tradable") and a.get("exchange") in EXCHANGES
                  and not DERIV.search(a["symbol"]) and "/" not in a["symbol"])


def regime_factor(f: Fetcher, day: str):
    """C4 on SPY's adjusted daily closes before the session."""
    start = (datetime.fromisoformat(day) - timedelta(days=500)).date().isoformat()
    closes = []
    for body in f.get(DATA, "/v2/stocks/bars", {"symbols": "SPY", "timeframe": "1Day", "start": start, "end": day,
                                                 "adjustment": "all", "feed": "sip", "limit": 10000}):
        closes.extend((b["t"][:10], b["c"]) for b in (body.get("bars") or {}).get("SPY", []))
    c = np.array([x for d, x in sorted(closes) if d < day], dtype=float)
    if len(c) < 273:
        raise SystemExit("SPY history too short for the regime factor")
    lr = np.diff(np.log(c))
    # vol at close p = sd of the 20 log returns ending at p (as evaluate.Spy); the last p is the previous session
    vol = np.array([np.std(lr[p - 20:p], ddof=1) for p in range(len(c) - 252, len(c))])
    up = c[-1] > c[-20:].mean()
    calm = vol[-1] < np.median(vol)
    return (1.0 if (up and calm) else 0.5), {"spy_prev_close": float(c[-1]), "mean20": float(c[-20:].mean()),
                                             "vol20": float(vol[-1]), "vol20_median252": float(np.median(vol[-252:]))}


def previous_session(f: Fetcher, day: str) -> str:
    """The trading session before day, from the broker calendar (C31/D5), refusing a non-trading day."""
    start = (datetime.fromisoformat(day) - timedelta(days=14)).date().isoformat()
    days = []
    for body in f.get(TRADING, "/v2/calendar", {"start": start, "end": day}):
        days.extend(x["date"] for x in (body if isinstance(body, list) else []))
    if day not in days:
        raise SystemExit(f"{day} is not a trading session")
    return max(d for d in days if d < day)


def scan(f: Fetcher, rule: str, now: datetime):
    t, g, v, n = parse_rule(rule)
    day = now.astimezone(R.ET).date().isoformat()
    cutoff = R.signal_cutoff(day, t)
    if now.timestamp() < cutoff:
        raise SystemExit(f"it is before the rule's signal cutoff ({t} ET rule)")
    prev_day = previous_session(f, day)
    syms = universe(f)
    snaps = {}
    for i in range(0, len(syms), 500):
        for body in f.get(DATA, "/v2/stocks/snapshots", {"symbols": ",".join(syms[i:i + 500]), "feed": "sip"}):
            snaps.update(body)
    def bar_day(b):
        return datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(R.ET).date().isoformat() if b.get("t") else None

    def prev_bar(sn):
        """The snapshot's daily bar dated the previous session: dailyBar before today's first regular-session
        trade, otherwise prevDailyBar; None when neither carries that date."""
        for key in ("dailyBar", "prevDailyBar"):
            b = (sn or {}).get(key) or {}
            if bar_day(b) == prev_day:
                return b
        return None

    # symbols with a split effective today always pass the prefilter; the exact rule below applies the split factor
    split_today = set()
    for body in f.get(DATA, "/v1/corporate-actions", {"types": "forward_split,reverse_split", "start": day, "end": day, "limit": 1000}):
        for items in (body.get("corporate_actions") or {}).values():
            split_today.update(x["symbol"] for x in items if x.get("symbol"))
    pre, undated = [], 0
    for s, sn in sorted(snaps.items()):
        lt, pb = (sn or {}).get("latestTrade") or {}, prev_bar(sn)
        if pb is None:
            undated += 1
            continue
        if lt.get("p") and pb.get("c") and lt["p"] >= R.MIN_PRICE and (s in split_today or lt["p"] >= (1 + PREFILTER * g) * pb["c"]):
            pre.append(s)
    rows = []
    for i in range(0, len(pre), 100):
        chunk = pre[i:i + 100]
        bars = {s: [] for s in chunk}
        for body in f.get(DATA, "/v2/stocks/bars", {"symbols": ",".join(chunk), "timeframe": "1Min", "start": et_iso(day, "04:00"),
                                                     "end": datetime.fromtimestamp(cutoff - 1, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                     "feed": "sip", "adjustment": "raw", "limit": 10000, "sort": "asc"}):
            for s, items in (body.get("bars") or {}).items():
                bars[s].extend(items)
        auctions = {}
        for body in f.get(DATA, "/v2/stocks/auctions", {"symbols": ",".join(chunk), "start": prev_day, "end": prev_day, "feed": "sip", "limit": 10000}):
            for s, days in (body.get("auctions") or {}).items():
                for d in days or []:
                    auctions.setdefault(s, {})[d["d"]] = {"o": d.get("o") or [], "c": d.get("c") or []}
        factors = {}
        for adj in ("raw", "split"):
            for body in f.get(DATA, "/v2/stocks/bars", {"symbols": ",".join(chunk), "timeframe": "1Day", "start": prev_day, "end": prev_day,
                                                         "feed": "sip", "adjustment": adj, "limit": 10000}):
                for s, items in (body.get("bars") or {}).items():
                    if items:
                        factors.setdefault(s, {})[adj] = items[-1]["c"]
        for s in chunk:
            b = R.Bars.from_rows([{"t": datetime.fromisoformat(x["t"].replace("Z", "+00:00")).timestamp(), **{k: x[k] for k in "ohlcv"},
                                   "vw": x.get("vw") or x["c"]} for x in bars[s]], R.et_epoch(day, "04:00"))
            prev_close, src = official_price(auctions.get(s, {}).get(prev_day), "c")
            if prev_close is None:
                pb = prev_bar(snaps.get(s))
                prev_close, src = (pb or {}).get("c"), "daily_bar_close"
            fr = factors.get(s, {})
            f_split, split = (fr["raw"] / fr["split"], True) if (fr.get("raw") and fr.get("split") and abs(fr["raw"] / fr["split"] - 1) > R.SPLIT_TOLERANCE) else (1.0, False)
            ref = prev_close / f_split if prev_close else None
            price, dv = b.state(cutoff)
            gain = price / ref - 1 if (price is not None and ref) else None
            rows.append({"symbol": s, "price_at_t": price, "dollar_volume_at_t": dv, "gain_at_t": gain, "ref": ref, "ref_source": src,
                         "split": split, "split_factor": f_split, "entry_bar_dollar_volume": None})
    fired = [r for r in rows if R.fires(r["price_at_t"], r["dollar_volume_at_t"], r["gain_at_t"], True, g, v, "any")]
    if n == "news_before_t" and fired:
        tt = R.et_epoch(day, t)
        since = R.et_epoch(prev_day, "16:00")
        news = {r["symbol"]: [] for r in fired}
        syms_f = sorted(news)
        for i in range(0, len(syms_f), 50):
            for body in f.get(DATA, "/v1beta1/news", {"symbols": ",".join(syms_f[i:i + 50]), "start": datetime.fromtimestamp(since, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                       "end": datetime.fromtimestamp(tt - 120, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                       "limit": 50, "include_content": "false", "sort": "asc"}):
                for item in body.get("news") or []:
                    for s in item.get("symbols") or []:
                        if s in news:
                            news[s].append(datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).timestamp())
        fired = [r for r in fired if R.news_before(news[r["symbol"]], tt, 120, since)]
    fired.sort(key=lambda r: (-r["dollar_volume_at_t"], r["symbol"]))
    for rank, r in enumerate(fired, 1):
        r["rank"] = rank
    rf, rdetail = regime_factor(f, day)
    return {"schema_version": 1, "protocol": "mover-early-entry-v1-20260924", "rule": rule, "session": day, "prev_session": prev_day,
            "rule_time_et": t, "scan_time_utc": now.astimezone(timezone.utc).isoformat(), "signal_cutoff_utc": datetime.fromtimestamp(cutoff, timezone.utc).isoformat(),
            "universe": len(syms), "snapshots": len(snaps), "snapshots_without_previous_session_bar": undated,
            "prefiltered": len(pre), "fired": len(fired),
            "regime_factor": rf, "regime_detail": rdetail, "candidates": fired[:TOP], "fired_beyond_top": [r["symbol"] for r in fired[TOP:]],
            "splits_effective_today": sorted(split_today),
            "limitations": ["the snapshot prefilter keeps latest trades >= (1 + 0.9 G) x the previous daily close (and every split effective today); a symbol that met the rule before t but traded below that by the scan is missed",
                            "the split factor uses split-only adjusted previous-day bars (dividends ignored), unlike the study's fully adjusted ratio with a 1e-2 tolerance",
                            "entry_bar_dollar_volume is unknown at scan time, so the 10% entry-bar capacity cap does not apply live"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", type=Path)
    ap.add_argument("--rule", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pages", type=Path, help="retain pages here (live mode)")
    ap.add_argument("--replay", type=Path, help="derive the scan from retained pages")
    ap.add_argument("--at", help="scan time (ISO); replay mode requires it")
    a = ap.parse_args(argv)
    if a.replay:
        if not a.at:
            raise SystemExit("--replay needs --at")
        f, now = Fetcher(a.replay, replay=True), datetime.fromisoformat(a.at)
    else:
        import collect
        key, secret = collect.credentials(a.env_file)
        f = Fetcher(a.pages, {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
        now = datetime.now(timezone.utc) if not a.at else datetime.fromisoformat(a.at)
    out = scan(f, a.rule, now)
    body = json.dumps(out, indent=1, sort_keys=True) + "\n"
    a.out.write_text(body)
    os.chmod(a.out, 0o600)
    print(json.dumps({"rule": out["rule"], "session": out["session"], "fired": out["fired"], "candidates": [c["symbol"] for c in out["candidates"]],
                      "regime_factor": out["regime_factor"], "sha256": hashlib.sha256(body.encode()).hexdigest()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
