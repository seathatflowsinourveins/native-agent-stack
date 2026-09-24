"""Response parsing into normalized records (evaluation code; never under study/fetch/).

Review round 8, R8-1: parsing and row filtering decide which prices exist, so they live in the frozen evaluation
tree. study/fetch/ only moves bytes (HTTP client, auth, pagination, retry). A transport deviation therefore
cannot change a normalized record, and the reproduction check re-parses every sealed raw page with this module.

Empty responses (universe_and_identity.empty_responses): a 200 page set with no row for the requested symbol is
'empty', never fetch-incomplete.

Corporate-action dates (review round 8, E7): a record is effective on the session named by one field per type:
name_change process_date; forward_split, reverse_split, unit_split, stock_dividend and cash_dividend ex_date;
cash_merger, stock_merger and stock_and_cash_merger effective_date; any other type process_date.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

EFFECTIVE_DATE_FIELD = {
    "name_change": "process_date",
    "forward_split": "ex_date",
    "reverse_split": "ex_date",
    "unit_split": "ex_date",
    "stock_dividend": "ex_date",
    "cash_dividend": "ex_date",
    "cash_merger": "effective_date",
    "stock_merger": "effective_date",
    "stock_and_cash_merger": "effective_date",
}
MERGER_TYPES = ("cash_merger", "stock_merger", "stock_and_cash_merger")
SPLIT_TYPES = ("forward_split", "reverse_split")
SYMBOL_FIELDS = ("symbol", "old_symbol", "new_symbol", "acquirer_symbol", "acquiree_symbol", "target_symbol",
                 "source_symbol", "new_symbol_2")


def ts_epoch(text: str) -> float:
    """RFC 3339 with up to nanoseconds, e.g. 2020-01-02T14:34:59.965123456Z."""
    head, _, frac = text.rstrip("Z").partition(".")
    if "+" in head[10:]:
        head = head[: 10] + head[10:].split("+")[0]
    base = datetime.fromisoformat(head).replace(tzinfo=timezone.utc).timestamp()
    return base + (float("0." + frac) if frac else 0.0)


def ts_ns(text: str) -> int:
    """The same RFC 3339 stamp as exact integer nanoseconds since the epoch. A float epoch near 1.6e9 s resolves
    only about 240 ns, so two quote updates a few nanoseconds apart would compare equal (review round 12, Codex
    P2): quotes are ordered by this key, never by the float."""
    head, _, frac = text.rstrip("Z").partition(".")
    if "+" in head[10:]:
        head = head[: 10] + head[10:].split("+")[0]
    base = int(datetime.fromisoformat(head).replace(tzinfo=timezone.utc).timestamp())
    return base * 1_000_000_000 + int((frac + "000000000")[:9])


def et_date(ts: float) -> str:
    return datetime.fromtimestamp(ts, ET).strftime("%Y-%m-%d")


def singular(kind: str) -> str:
    return kind[:-1] if kind.endswith("s") and kind[:-1] in EFFECTIVE_DATE_FIELD else kind


def bars(body: dict) -> dict:
    """{symbol: {session: {o,h,l,c,v,vw,t}}} for daily bars; the session is the ET date of the bar start."""
    out = {}
    for sym, items in (body.get("bars") or {}).items():
        for b in items or []:
            t = ts_epoch(b["t"])
            out.setdefault(sym, {})[et_date(t)] = {"t": t, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
                                                    "v": b["v"], "vw": b.get("vw")}
    return out


def minute_bars(body: dict) -> dict:
    """{symbol: [bar, ...]} sorted by start, first of each start time kept (a page boundary can repeat a bar)."""
    out = {}
    for sym, items in (body.get("bars") or {}).items():
        for b in items or []:
            out.setdefault(sym, []).append({"t": ts_epoch(b["t"]), "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
                                            "v": b["v"], "vw": b.get("vw") or b["c"]})
    return out


def merge_minute(chunks: list[list[dict]]) -> list[dict]:
    rows = sorted((b for chunk in chunks for b in chunk), key=lambda b: b["t"])
    out, last = [], None
    for b in rows:
        if b["t"] != last:
            out.append(b)
        last = b["t"]
    return out


def auctions(body: dict) -> dict:
    """{symbol: {session: {"o": [...], "c": [...]}}} in sessions_io.load_session's shape."""
    out = {}
    for sym, days in (body.get("auctions") or {}).items():
        for d in days or []:
            out.setdefault(sym, {})[d["d"]] = {"o": d.get("o") or [], "c": d.get("c") or []}
    return out


def quotes(body: dict) -> dict:
    """{symbol: [quote, ...]} with epoch t; sorted ascending by the caller after merging pages."""
    out = {}
    for sym, items in (body.get("quotes") or {}).items():
        for q in items or []:
            out.setdefault(sym, []).append({"t": ts_epoch(q["t"]), "ns": ts_ns(q["t"]), "bp": q.get("bp"),
                                            "ap": q.get("ap"), "bs": q.get("bs"), "as": q.get("as")})
    return out


def _quote_key(q) -> tuple:
    return (q["ns"], q["bp"], q["ap"], q["bs"], q["as"])


def merge_quotes(chunks: list[list[dict]]) -> list[dict]:
    """Pages in order, stably sorted by the exact nanosecond stamp: updates keep the provider's sequence, and a
    price never decides which of two updates is later (review round 12, Codex P2). A repeat of one update across a
    page boundary (the next page's first update identical to the previous page's last) is kept once. Identical
    updates inside a page are all kept in the provider's order (review round 13, Codex P2: dropping every repeat of
    a stamp and quote turned [eligible A, locked B, eligible A] into [A, B], so the locked B prevailed)."""
    seq = []
    for chunk in chunks:
        chunk = list(chunk)
        if seq and chunk and _quote_key(chunk[0]) == _quote_key(seq[-1]):
            chunk = chunk[1:]
        seq.extend(chunk)
    return sorted(seq, key=lambda q: q["ns"])


def corporate_actions(body: dict) -> list[dict]:
    """Normalized records: {"type", "date" (per EFFECTIVE_DATE_FIELD), symbol fields, rates}."""
    out = []
    for kind, items in (body.get("corporate_actions") or {}).items():
        typ = singular(kind)
        field = EFFECTIVE_DATE_FIELD.get(typ, "process_date")
        for it in items or []:
            rec = {"type": typ, "date": it.get(field)}
            for f in SYMBOL_FIELDS + ("old_rate", "new_rate", "rate", "acquirer_rate", "acquiree_rate"):
                if it.get(f) is not None:
                    rec[f] = it[f]
            out.append(rec)
    out.sort(key=lambda r: json.dumps(r, sort_keys=True))
    return out


def assets(body) -> list[dict]:
    items = body if isinstance(body, list) else body.get("assets") or []
    return sorted(({"symbol": a.get("symbol"), "status": a.get("status"), "exchange": a.get("exchange"),
                    "class": a.get("class")} for a in items), key=lambda a: (a["symbol"] or "", a["status"] or ""))


PARSERS = {"daily_bars": bars, "minute_bars": minute_bars, "auctions": auctions, "quotes": quotes,
           "corporate_actions": corporate_actions, "assets": assets}


def normalize_page(parser: str, raw: bytes):
    """The normalized records of one raw 200 page, in canonical order (the reproduction check compares these)."""
    body = json.loads(raw) if raw else {}
    rec = PARSERS[parser](body)
    return rec


def is_empty(parser: str, pages_bodies: list, symbol: str | None = None) -> bool:
    """HTTP 200 with no row (for the symbol, when one is named)."""
    for body in pages_bodies:
        rec = PARSERS[parser](body)
        if parser in ("corporate_actions", "assets"):
            if rec:
                return False
        elif symbol is None:
            if any(rec.values()):
                return False
        elif rec.get(symbol):
            return False
    return True
