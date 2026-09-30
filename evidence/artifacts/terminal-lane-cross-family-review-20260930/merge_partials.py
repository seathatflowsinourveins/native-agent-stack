#!/usr/bin/env python3
"""Merge several collect_reviews.py outputs ({"records": [...], "findings": [...]}) into one file, keeping the order given. usage: merge_partials.py <out.json> <in.json> [<in.json> ...]"""
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
merged = {"records": [], "findings": []}
for name in sys.argv[2:]:
    data = json.loads(Path(name).read_text(encoding="utf-8"))
    merged["records"] += data["records"]
    merged["findings"] += data["findings"]
ids = [f["id"] for f in merged["findings"]]
assert len(ids) == len(frozenset(ids)), "duplicate finding ids"
out.write_text(json.dumps(merged, indent=1), encoding="utf-8")
print(f"merged {len(merged['records'])} jobs and {len(ids)} findings into {out.name}")
