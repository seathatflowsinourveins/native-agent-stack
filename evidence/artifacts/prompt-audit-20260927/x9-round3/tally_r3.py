"""Tally X9's round 3 (prereg-r3.json, decision_rule): round 2's tally_attempt2.py with the round-3 rule.

usage: tally_r3.py
Reads returns/{gpt6,claude}-{AB,BA}.json (each {"items": [one X9 entry]}; a Claude return may instead carry
"leak": true), round3-mapping.json, audit-r3.json and analysis-r3.json, and writes tally-r3.json.
A judgment counts only when the audit found no voiding hit, it is not a leak refusal, and it has one X9 entry with
choice A, B or neither. Four counted judgments choosing the same lane text apply it; four `neither` keep the current
line. Anything else, including a void or refused judgment, goes to the preregistered metric order of K5-K6
(analysis-r3.json, metric_order), which picks the lane text it ranks first; an incomplete comparison or a tie on every
step decides nothing, and X9 stays pending.
"""
import json
from pathlib import Path

X = Path(__file__).resolve().parent
mapping = json.loads((X / "round3-mapping.json").read_text())
audit = json.loads((X / "audit-r3.json").read_text())["judgments"]
analysis = json.loads((X / "analysis-r3.json").read_text())
votes, labels, void = {}, {}, {}
for fam in ("gpt6", "claude"):
    for order in ("AB", "BA"):
        key = f"{fam}-{order}"
        ret = json.loads((X / "returns" / f"{key}.json").read_text())
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
distinct = sorted(set(counted.values()))
order = analysis.get("metric_order")
if not void and len(counted) == 4 and distinct == ["neither"]:
    outcome, step = "keep the current line (unanimous neither)", 1
elif not void and len(counted) == 4 and len(distinct) == 1:
    outcome, step = "apply " + distinct[0] + " (unanimous)", 1
elif analysis.get("complete") and order and order.get("winner"):
    outcome, step = f"apply {order['winner']} (metric order, decided by {order['decided_by']})", 2
else:
    outcome, step = "pending: no unanimous judgment and the comparison decides nothing", 4
tally = {"round": 3, "votes": votes, "labels": labels, "void": void, "counted": sorted(counted),
         "adjudication": "unanimous" if step == 1 else "split", "decision_rule_step": step, "outcome": outcome,
         "metric_order": order}
(X / "tally-r3.json").write_text(json.dumps(tally, indent=1) + "\n")
print(json.dumps(tally))
