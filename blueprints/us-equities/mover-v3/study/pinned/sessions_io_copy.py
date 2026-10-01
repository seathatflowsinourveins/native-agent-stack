"""Byte-for-byte copies of definitions from blueprints/us-equities/mover-early-entry/sessions_io.py at aa6fc79 (git blob 0f7791a87685c73635efe94c226031d9afe7bd7c).

Listed in study/pinned_copies.json and checked against that blob by tests/test_pinned_copies.py.
Nothing else from the source module is copied, so its module-level code never runs here.
"""
from __future__ import annotations


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
