"""Deterministic readers for the collected mover sessions (collect.py output; private data).

``load_session(dir)`` returns, for one session directory:

  bars      {symbol: [bar, ...]} 1-minute bars sorted by start time; each bar is
            {"t": epoch seconds (UTC start), "o", "h", "l", "c", "v", "vw"}
  auctions  {symbol: {"YYYY-MM-DD": {"o": [...], "c": [...]}}} official auction prints
  news      {symbol: [epoch seconds, ...]} headline creation times, sorted

``official_price(day_auction, side)`` selects the official open (side "o") or close (side "c") with
the price audit's v2 rule (extreme-gainer-audit/deviations.json D1), as protocol.json fixes it: the
listing exchange is the exchange of the largest-size condition-O opening print. For the close that is the largest-size
condition-6 print, else a condition-M print, else another exchange's condition-6 print. For the
open it is the condition-O print on the listing exchange. Returns (price, source) or (None, None).
"""
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def _pages(sdir: Path, kind: str):
    for f in sorted(sdir.glob(f"{kind}-*.json.gz")):
        body = json.loads(gzip.open(f).read())
        yield body


def load_session(sdir: Path) -> dict:
    bars = defaultdict(list)
    for body in _pages(sdir, "bars"):
        for sym, items in (body.get("bars") or {}).items():
            for b in items:
                bars[sym].append({"t": _epoch(b["t"]), "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b["v"],
                                  "vw": b.get("vw") or b["c"]})
    for sym in bars:
        bars[sym].sort(key=lambda b: b["t"])
        # A page boundary can repeat a bar; keep the first of each start time.
        dedup, last = [], None
        for b in bars[sym]:
            if b["t"] != last:
                dedup.append(b)
            last = b["t"]
        bars[sym] = dedup
    auctions = defaultdict(dict)
    for body in _pages(sdir, "auctions"):
        for sym, days in (body.get("auctions") or {}).items():
            for d in days or []:
                auctions[sym][d["d"]] = {"o": d.get("o") or [], "c": d.get("c") or []}
    news = defaultdict(list)
    for body in _pages(sdir, "news"):
        for item in body.get("news") or []:
            created = _epoch(item["created_at"])
            for sym in item.get("symbols") or []:
                news[sym].append(created)
    for sym in news:
        news[sym] = sorted(set(news[sym]))
    return {"bars": dict(bars), "auctions": dict(auctions), "news": dict(news)}


def official_price(day_auction: dict | None, side: str):
    if not day_auction:
        return None, None
    opens = day_auction.get("o") or []
    o_prints = [o for o in opens if o.get("c") == "O"]
    if not o_prints:
        listing = set()
    else:
        top = max(o_prints, key=lambda o: (o.get("s") or 0, o.get("x") or ""))
        listing = {top.get("x")}
    if side == "o":
        if o_prints:
            return float(top["p"]), "opening_print_listing_exchange"
        return None, None
    closes = day_auction.get("c") or []
    on_listing = [c for c in closes if c.get("c") == "6" and c.get("x") in listing]
    if on_listing:
        best = max(on_listing, key=lambda c: c.get("s") or 0)
        return float(best["p"]), "closing_print_listing_exchange"
    official = [c for c in closes if c.get("c") == "M" and c.get("x") in listing]
    if official:
        return float(official[0]["p"]), "official_close_listing_exchange"
    prints = [c for c in closes if c.get("c") == "6"]
    if prints:
        best = max(prints, key=lambda c: c.get("s") or 0)
        return float(best["p"]), "closing_print_other_exchange"
    return None, None
