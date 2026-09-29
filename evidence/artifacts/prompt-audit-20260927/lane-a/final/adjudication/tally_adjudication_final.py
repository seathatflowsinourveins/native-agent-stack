"""Tally lane A's final X5c adjudication under the fixed rule: a resolution is applied only when all four judgments
(both presentation orders, both families) are valid and choose it; anything else keeps the current text.

usage: tally_adjudication_final.py
Reads returns/{gpt6,claude}-{AB,BA}.json, audit-final.json and adjudication-mapping-final.json; writes
tally-adjudication-final.json. A judgment is invalid when its audit is void, it reports a leak, or it lacks exactly
one X5c entry with a choice of A, B or neither.
"""
import json
from pathlib import Path

X = Path(__file__).resolve().parent
mapping = json.loads((X / "adjudication-mapping-final.json").read_text())["orders"]
audit = json.loads((X / "audit-final.json").read_text())["judgments"]
judgments, invalid = {}, {}
for fam in ("gpt6", "claude"):
    for order in ("AB", "BA"):
        name = f"{fam}-{order}"
        path = X / "returns" / f"{name}.json"
        if not path.exists():
            invalid[name] = "no return"
            continue
        ret = json.loads(path.read_text())
        items = ret.get("items") or []
        if audit.get(name, {}).get("void", True):
            invalid[name] = "audit: " + "; ".join(sorted({f"{h['pattern']} in {h['scope']}" for h in
                                                          audit.get(name, {}).get("hits", [])})) or "not audited"
        elif ret.get("leak"):
            invalid[name] = "leak: " + str(ret.get("leak_text"))[:200]
        elif len(items) != 1 or items[0].get("id") != "X5c" or items[0].get("choice") not in ("A", "B", "neither"):
            invalid[name] = "malformed return"
        if items and items[0].get("choice") in ("A", "B", "neither"):
            c = items[0]["choice"]
            judgments[name] = {"choice": c, "resolution": mapping[order]["X5c"].get(c, "neither"),
                               "confidence": items[0].get("confidence")}
chosen = {j["resolution"] for n, j in judgments.items() if n not in invalid}
if invalid or len(judgments) != 4:
    outcome = "keep the current text (a judgment is invalid or missing; final round)"
elif chosen == {"g"}:
    outcome = "apply the packet's proposal (g)"
elif chosen == {"c"}:
    outcome = "apply the amendment (c)"
else:
    outcome = "keep the current text (the four judgments do not all choose one resolution)"
out = {"rule": "applied only when all four valid judgments choose the same resolution", "judgments": judgments,
       "invalid": invalid, "outcome": outcome}
(X / "tally-adjudication-final.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out))
