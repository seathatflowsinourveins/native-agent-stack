#!/usr/bin/env python3
"""Score a backend's returned text against gold.json (exact value match per key).
Usage: score_facts.py GOLD_JSON < response_text ; prints JSON, exit 0 iff all facts correct."""
import json, re, sys
gold = json.load(open(sys.argv[1]))["gold"]
text = sys.stdin.read()
obj = None
for m in re.finditer(r"\{", text):
    depth = 0
    for i in range(m.start(), len(text)):
        depth += text[i] == "{"; depth -= text[i] == "}"
        if depth == 0:
            try:
                obj = json.loads(text[m.start():i + 1])
            except ValueError:
                obj = None
            break
    if isinstance(obj, dict):
        break
per = {k: (isinstance(obj, dict) and obj.get(k) == v) for k, v in gold.items()}
out = {"parsed": isinstance(obj, dict), "correct": sum(per.values()), "total": len(gold), "per_key": per}
print(json.dumps(out))
sys.exit(0 if out["correct"] == out["total"] else 1)
