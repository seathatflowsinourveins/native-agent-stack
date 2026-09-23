#!/usr/bin/env python3
"""Generate results.json (gap_index -> outcome, receipt) from the layer's receipts."""
import glob, json, os
L = "evidence/artifacts/gap-wave2-20260923/us-equities__observability-hosting/"
out = {}
for p in sorted(glob.glob(L + "[0-9]*-*.json")):
    r = json.load(open(p))
    out[str(r["gap_index"])] = {"outcome": r["outcome"], "receipt": p}
open(L + "results.json", "w").write(json.dumps(out, indent=1, sort_keys=True) + "\n")
print(json.dumps(out))
