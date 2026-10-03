#!/usr/bin/env python3
"""Save the Claude family's decision-round returns from the workflow journal into one file.

Usage: save_claude_returns.py <journal.jsonl> <out.json> <run-id>
The journal has one line per agent start (key, label) and one per result (key, result). Nothing is rewritten.
"""
import hashlib
import json
import sys
from pathlib import Path

journal, out, run = sys.argv[1:4]
labels, results = {}, {}
for line in Path(journal).read_text(encoding="utf-8").splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("label"):
        labels[e["key"]] = e["label"]
    r = e.get("result") if "result" in e else e.get("value")
    if isinstance(r, dict) and e.get("key"):
        results[e["key"]] = r

slots = {}
for key, label in labels.items():
    kind, _, rest = label.partition(":")
    r = results.get(key)
    if kind == "decide":
        slot, _, order = rest.partition(":")
        slots.setdefault(slot, {"decisions": {}, "critique": None})["decisions"][order] = r
    elif kind == "critic":
        slots.setdefault(rest, {"decisions": {}, "critique": None})["critique"] = r

missing = [f"{s}:{o}" for s, v in slots.items() for o in ("order-1", "order-2") if not v["decisions"].get(o)]
missing += [f"{s}:critic" for s, v in slots.items() if not v["critique"]]
doc = {"schema_version": 1, "kind": "decision-round-returns", "family": "claude", "run": run,
       "dispatch": "stack-researcher, opus, effort max; two deciders per slot in seeded orders, one critic per slot",
       "missing": missing, "slots": slots}
text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
Path(out).write_text(text, encoding="utf-8")
print("slots", len(slots), "| missing", missing, "| bytes", len(text.encode("utf-8")), "| sha256", hashlib.sha256(text.encode("utf-8")).hexdigest())
