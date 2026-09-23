#!/usr/bin/env python3
"""Generate results.json from the receipts (never by hand)."""
import glob
import json
import os

E = "evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/"
out = {}
for path in glob.glob(E + "[0-9]*-*.json"):
    r = json.load(open(path))
    out[str(r["gap_index"])] = {"outcome": r["outcome"], "receipt": os.path.basename(path)}
out = dict(sorted(out.items(), key=lambda kv: int(kv[0])))
open(E + "results.json", "w").write(json.dumps(out, indent=1) + "\n")
print(json.dumps(out))
