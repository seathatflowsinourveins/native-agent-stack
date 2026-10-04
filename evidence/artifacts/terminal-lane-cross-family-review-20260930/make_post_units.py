#!/usr/bin/env python3
"""Write units.json for the verifier briefs of the post-merge GPT read: the 38 findings grouped into 16 distinct issues (the representative is listed first, the duplicates are attached as corroboration), four units.
Asserts that every finding id of the consolidated file appears exactly once. usage: make_post_units.py <consolidated.json> <out units.json>"""
import json
import sys
from pathlib import Path

UNITS = {
    "V1": {"findings": ["F-sol-P1-1", "F-sol-P1-2", "F-sol-P1-3"],
           "also": {"F-sol-P1-1": ["F-sol-P3-3", "F-ultra-P1-1"], "F-sol-P1-2": ["F-ultra-P1-3"], "F-sol-P1-3": ["F-sol-P3-1", "F-ultra-P1-2", "F-ultra-P3-2"]}},
    "V2": {"findings": ["F-sol-P3-2", "F-sol-P1-4", "F-sol-P1-6"],
           "also": {"F-sol-P3-2": ["F-ultra-P1-4"], "F-sol-P1-4": ["F-ultra-P1-5", "F-sol-P3-4"]}},
    "V3": {"findings": ["F-sol-P2-1", "F-sol-P2-3", "F-ultra-P2-2", "F-sol-P2-5", "F-sol-P3-6", "F-sol-P1-5"],
           "also": {"F-sol-P2-1": ["F-ultra-P2-1"], "F-sol-P2-3": ["F-ultra-P2-3"], "F-ultra-P2-2": ["F-ultra-P3-1", "F-sol-P2-2"], "F-sol-P2-5": ["F-ultra-P2-5"],
                    "F-sol-P1-5": ["F-sol-P2-4", "F-sol-P3-5", "F-ultra-P1-6", "F-ultra-P2-4", "F-ultra-P3-3"]}},
    "V4": {"findings": ["F-sol-P2-6", "F-sol-P3-7", "F-sol-P3-8", "F-sol-P3-9"],
           "also": {"F-sol-P2-6": ["F-ultra-P3-5", "F-ultra-P2-6"], "F-sol-P3-8": ["F-ultra-P3-4"]}},
}
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
known = [f["id"] for f in data["findings"]]
used = [i for unit in UNITS.values() for i in unit["findings"]] + [i for unit in UNITS.values() for group in unit["also"].values() for i in group]
assert len(used) == len(frozenset(used)) == len(known) == len(frozenset(known)), (len(used), len(frozenset(used)), len(known))
assert frozenset(used) == frozenset(known), (sorted(frozenset(known) - frozenset(used)), sorted(frozenset(used) - frozenset(known)))
Path(sys.argv[2]).write_text(json.dumps(UNITS, indent=1), encoding="utf-8")
print("units ok:", {name: len(unit["findings"]) for name, unit in UNITS.items()}, "| representatives", sum(len(u["findings"]) for u in UNITS.values()), "| duplicates attached", sum(len(g) for u in UNITS.values() for g in u["also"].values()))
