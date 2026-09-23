#!/usr/bin/env python3
"""score.py GOLD_JSON TASK(t1|t2) < final_message  -> exact-match per key"""
import json, re, sys
gold = json.load(open(sys.argv[1]))[sys.argv[2]]
txt = sys.stdin.read(); m = re.search(r"\{.*\}", txt, re.S)
try:
    obj = json.loads(m.group(0)) if m else None
except ValueError:
    obj = None
per = {k: isinstance(obj, dict) and obj.get(k) == v for k, v in gold.items()}
print(json.dumps({"correct": sum(per.values()), "total": len(per), "per_key": per}))
