"""Byte-for-byte copies of definitions from blueprints/us-equities/broad-universe/collect_daily.py at aa6fc79 (git blob 8df7d3485b848847a372d264768945e3a6d8b9c1).

Listed in study/pinned_copies.json and checked against that blob by tests/test_pinned_copies.py.
Nothing else from the source module is copied, so its module-level code never runs here.
"""
import re


DATA_SYMBOL = re.compile(r"^[A-Z]+(\.[A-Z]+)?$")
