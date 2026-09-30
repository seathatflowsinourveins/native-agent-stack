"""Recompute attempt 2's tally from the published files, with the same rule as tally_attempt2.py.

usage: python3 attempt2/retally.py   (run from the x9-round2 directory)
tally_attempt2.py read the coordinator's working layout (x9-round2/returns2/<fam>-<order>.json,
attempt2-mapping.json, audit-attempt2.json). The published layout holds the same data as attempt2/mapping.json,
attempt2/audit.json and the "return" object of attempt2/<fam>.<order>.json. The rule: a judgment counts only when
the audit found no voiding hit, it is not a leak refusal, and it has one X9 entry with choice A, B or neither; the
text is applied only when all four counted judgments choose the same lane text; four `neither` keep the current
line; anything else is a split. Exits 1 when the result differs from attempt2/tally.json.
"""
import json
import sys
from pathlib import Path

A = Path("attempt2")
mapping = json.loads((A / "mapping.json").read_text())
audit = json.loads((A / "audit.json").read_text())["judgments"]
votes, void = {}, {}
for fam in ("gpt6", "claude"):
    for order in ("AB", "BA"):
        key = f"{fam}-{order}"
        ret = json.loads((A / f"{fam}.{order}.json").read_text())["return"]
        items = ret.get("items") or []
        if audit[key]["void"]:
            void[key] = "audit"
        elif ret.get("leak"):
            void[key] = "leak refusal"
        elif len(items) != 1 or items[0].get("id") != "X9" or items[0].get("choice") not in ("A", "B", "neither"):
            void[key] = "malformed return"
        if items and items[0].get("choice") in ("A", "B", "neither"):
            choice = items[0]["choice"]
            votes[key] = "neither" if choice == "neither" else mapping[order][choice]
counted = {k: x for k, x in votes.items() if k not in void}
distinct = sorted(set(counted.values()))
if void or len(counted) != 4:
    outcome = "split: no edit (a judgment is void or missing)"
elif distinct == ["neither"]:
    outcome = "keep the current line (unanimous neither)"
elif len(distinct) == 1:
    outcome = "apply " + distinct[0]
else:
    outcome = "split: no edit"
recorded = json.loads((A / "tally.json").read_text())
same = recorded["votes"] == votes and recorded["void"] == void and recorded["outcome"] == outcome
print(json.dumps({"votes": votes, "void": void, "outcome": outcome, "matches_tally_json": same}))
sys.exit(0 if same else 1)
