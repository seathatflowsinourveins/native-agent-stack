#!/usr/bin/env python3
"""Turn one slot's discovery result into two judge packets with the candidates in different seeded orders.

Keys (C01, C02, ...) are assigned once, by sorted repository URL, so both orders use the same key for the same candidate.
Usage: make_packets.py <gap-slots.json> <output folder> <layer_id>
"""
import hashlib
import json
import pathlib
import random
import sys

spec = json.loads(pathlib.Path(sys.argv[1]).read_text())
out, lid = pathlib.Path(sys.argv[2]), sys.argv[3]
slot = next(s for s in spec["slots"] if s["layer_id"] == lid)
found = json.loads((out / "discover" / lid / "last.json").read_text())["candidates"]
seen, cands = set(), []
for c in sorted(found, key=lambda c: (c["repository"].lower().rstrip("/"), c["name"].lower())):
    ident = c["repository"].lower().rstrip("/") or c["name"].lower()
    if ident in seen:
        continue
    seen.add(ident)
    cands.append({"key": f"C{len(cands) + 1:02d}", "name": c["name"], "repository": c["repository"]})
if len(cands) < 2:
    sys.exit(f"{lid}: fewer than two candidates")
for n, order in enumerate(("order-1", "order-2"), start=1):
    seed = int(hashlib.sha256(f"{lid}:{order}:20261002".encode()).hexdigest()[:8], 16)
    shuffled = cands[:]
    random.Random(seed).shuffle(shuffled)
    packet = {"layer_id": lid, "title": slot["title"], "requirement": slot["requirement"],
              "a_deciding_comparison_would_measure": slot["a_deciding_comparison_would_measure"], "candidates": shuffled,
              "comparisons_on_record_where_every_named_arm_ran": [], "target_hosts": spec["target_hosts"]}
    p = out / order / lid / "packet.json"
    p.write_text(json.dumps(packet, ensure_ascii=False))
print(json.dumps({"unit_id": lid, "stage": "packets", "candidates": len(cands)}))
