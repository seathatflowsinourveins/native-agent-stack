#!/usr/bin/env python3
"""Regenerate results.json from the receipts in this directory (gap_index -> outcome, receipt)."""
import glob, json, os
here = os.path.dirname(os.path.abspath(__file__))
rel = "evidence/artifacts/gap-wave2-20260923/foundation__workers"
out = {}
for p in sorted(glob.glob(os.path.join(here, "[0-9]*-*.json"))):
    d = json.load(open(p))
    k = str(d["gap_index"])
    assert k not in out, f"duplicate receipt for gap {k}"
    assert d["id"] == os.path.basename(p)[:-5], f"id/filename mismatch in {p}"
    out[k] = {"outcome": d["outcome"], "receipt": f"{rel}/{os.path.basename(p)}"}
out = dict(sorted(out.items(), key=lambda kv: int(kv[0])))
with open(os.path.join(here, "results.json"), "w") as f:
    json.dump(out, f, indent=2); f.write("\n")
print(json.dumps({k: v["outcome"] for k, v in out.items()}))
