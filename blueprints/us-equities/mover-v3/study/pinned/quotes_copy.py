"""Byte-for-byte copies of definitions from blueprints/us-equities/mover-early-entry/quotes.py at aa6fc79 (git blob caebf6f6a72fee6bb7ae637ebb698f8c5f6b3850).

Listed in study/pinned_copies.json and checked against that blob by tests/test_pinned_copies.py.
Nothing else from the source module is copied, so its module-level code never runs here.
"""
from __future__ import annotations


def valid_quote(quotes):
    """The newest quote (input newest first) that is not crossed, locked or zero-priced."""
    for q in quotes:
        bp, ap = q.get("bp") or 0, q.get("ap") or 0
        if bp > 0 and ap > 0 and ap > bp:
            return q
    return None
