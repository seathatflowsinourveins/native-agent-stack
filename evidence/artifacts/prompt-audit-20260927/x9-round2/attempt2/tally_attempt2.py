"""Tally attempt 2 of X9's second adjudication round (the final attempt; attempt1-void.json, attempt_2_rules).

usage: tally_attempt2.py
Reads x9-round2/returns2/{gpt6,claude}-{AB,BA}.json (each {"items": [one X9 entry]}; a Claude return may instead
carry "leak": true), attempt2-mapping.json and audit-attempt2.json, and writes x9-round2/tally-attempt2.json.
A judgment counts only when the audit found no voiding hit, it is not a leak refusal, and it has one X9 entry with
choice A, B or neither. The text is applied only when all four counted judgments choose the same lane text; four
`neither` keeps the current line; anything else, including any void or refused judgment, is a split: no edit.
"""
import json
from pathlib import Path

X = Path(__file__).resolve().parent / "x9-round2"
mapping = json.loads((X / "attempt2-mapping.json").read_text())
audit = json.loads((X / "audit-attempt2.json").read_text())["judgments"]
votes, labels, void = {}, {}, {}
for fam in ("gpt6", "claude"):
    for order in ("AB", "BA"):
        key = f"{fam}-{order}"
        ret = json.loads((X / "returns2" / f"{key}.json").read_text())
        items = ret.get("items") or []
        if audit[key]["void"]:
            void[key] = "audit: " + "; ".join(sorted({f"{h['pattern']} in {h['scope']}" for h in audit[key]["hits"]}))
        elif ret.get("leak"):
            void[key] = "leak refusal: " + str(ret.get("leak_text"))[:200]
        elif len(items) != 1 or items[0].get("id") != "X9" or items[0].get("choice") not in ("A", "B", "neither"):
            void[key] = "malformed return"
        if items and items[0].get("choice") in ("A", "B", "neither"):
            choice = items[0]["choice"]
            votes[key] = "neither" if choice == "neither" else mapping[order][choice]
            labels[key] = {"choice_label": choice, "confidence": items[0].get("confidence")}
counted = {k: x for k, x in votes.items() if k not in void}
distinct = sorted({x for x in counted.values()})
if void or len(counted) != 4:
    outcome = "split: no edit (a judgment is void or missing)"
elif distinct == ["neither"]:
    outcome = "keep the current line (unanimous neither)"
elif len(distinct) == 1:
    outcome = "apply " + distinct[0]
else:
    outcome = "split: no edit"
tally = {"attempt": 2, "votes": votes, "labels": labels, "void": void, "counted": sorted(counted),
         "outcome": outcome}
(X / "tally-attempt2.json").write_text(json.dumps(tally, indent=1) + "\n")
print(json.dumps(tally))
