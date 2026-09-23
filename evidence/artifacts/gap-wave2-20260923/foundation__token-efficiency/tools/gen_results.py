"""Regenerate results.json from the per-gap receipts (never edited by hand)."""
import glob, json, os
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rel = "evidence/artifacts/gap-wave2-20260923/foundation__token-efficiency/"
out = {}
for p in sorted(glob.glob(os.path.join(D, "[0-9]*-*.json"))):
    r = json.load(open(p)); out[str(r["gap_index"])] = {"outcome": r["outcome"], "receipt": rel + os.path.basename(p)}
out = dict(sorted(out.items(), key=lambda kv: int(kv[0])))
open(os.path.join(D, "results.json"), "w").write(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: v["outcome"] for k, v in out.items()}))
