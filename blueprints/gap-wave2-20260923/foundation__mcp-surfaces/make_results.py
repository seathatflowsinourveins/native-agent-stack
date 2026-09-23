#!/usr/bin/env python3
"""Generate results.json for foundation/mcp-surfaces from the receipts on disk (never by hand)."""
import json
import pathlib

L = pathlib.Path("evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces")
res = {}
for p in sorted(L.glob("*-*.json")):
    if not p.name[0].isdigit():
        continue
    d = json.loads(p.read_text())
    res[str(d["gap_index"])] = {"outcome": d["outcome"], "receipt": str(p)}
res = dict(sorted(res.items(), key=lambda kv: int(kv[0])))
out = {"layer": "foundation/mcp-surfaces", "generated_by": "blueprints/gap-wave2-20260923/foundation__mcp-surfaces/make_results.py",
       "results": res}
(L / "results.json").write_text(json.dumps(out, indent=2) + "\n")
print({k: v["outcome"] for k, v in res.items()})
