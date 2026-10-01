"""Tally M5's four adjudications: map each choice to the lane whose text it names, apply the audit's voids, and state
the rule's outcome. A text is applied only when all four judgments are valid and choose it.

usage: tally_m45.py
Reads adjudication/{gpt6,claude}.{AB,BA}.json, adjudication/m45-mapping.json and adjudication/audit-m45.json in this
work directory; writes adjudication/tally-m45.json.
"""
import json
from pathlib import Path

W = Path(__file__).resolve().parent
A = W / "adjudication"
mapping = json.loads((A / "m45-mapping.json").read_text())
audit = json.loads((A / "audit-m45.json").read_text())["judgments"]
rows = {}
for fam in ("gpt6", "claude"):
    for order in ("AB", "BA"):
        ret = json.loads((A / f"{fam}.{order}.json").read_text())
        void = audit[f"{fam}-{order}"]["void"]
        leak = bool(ret.get("leak"))
        choice = None if leak else ret["items"][0]["choice"]
        lane = mapping[order].get(choice) if choice in ("A", "B") else choice
        rows[f"{fam}-{order}"] = {"choice": choice, "text_of": lane, "void": void, "leak": leak,
                                  "confidence": None if leak else ret["items"][0].get("confidence")}
valid = [r for r in rows.values() if not r["void"] and not r["leak"]]
picks = {r["text_of"] for r in valid}
if len(valid) == 4 and len(picks) == 1 and picks != {"neither"}:
    outcome = {"decision": "apply", "text_of": picks.pop()}
elif len(valid) == 4 and picks == {"neither"}:
    outcome = {"decision": "keep", "text_of": None}
else:
    outcome = {"decision": "split: lines 15-18 unchanged, both texts recorded", "text_of": None}
result = {"rule": "apply a text only when all four valid judgments choose it", "judgments": rows,
          "valid_judgments": len(valid), "outcome": outcome}
(A / "tally-m45.json").write_text(json.dumps(result, indent=1) + "\n")
print(json.dumps(result))
