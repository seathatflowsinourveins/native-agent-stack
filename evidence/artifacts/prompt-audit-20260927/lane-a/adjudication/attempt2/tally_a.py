"""Tally lane A's X5a/X5c adjudication under the packet's convergence rule (lane-a/packet.md, "Convergence rule, fixed
before either lane runs"): a text is applied only when all four adjudications choose it.

usage: tally_a.py [DIR]
DIR (default: this directory) holds one attempt's returns/ and audit-a.json and receives tally-a.json.
Reads returns/{gpt6,claude}-{AB,BA}.json (each {"items": [one entry per item]}; a Claude return may instead carry
"leak": true), ../adjudication-mapping-a.json and audit-a.json, and writes tally-a.json.
A judgment counts only when the audit found no voiding hit, it is not a leak refusal, and it has exactly one X5a and
one X5c entry with choice A, B or neither. Per item: four counted judgments choosing the same lane whose effective
resolution is an edit apply that resolution; anything else (a split, `neither`, the keep return, or a void, refused
or malformed judgment) keeps the current text, with every position recorded.
"""
import json
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
LANE = X.parent
D = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else X
UNITS = ("X5a", "X5c")
mapping = json.loads((LANE / "adjudication-mapping-a.json").read_text())
audit = json.loads((D / "audit-a.json").read_text())["judgments"]
lanes = {k: {i["id"]: i for i in json.loads((LANE / f"{f}.json").read_text())["items"]}
         for k, f in (("g", "gpt6"), ("c", "claude"))}
votes, void = {u: {} for u in UNITS}, {}
for fam in ("gpt6", "claude"):
    for order in ("AB", "BA"):
        key = f"{fam}-{order}"
        ret = json.loads((D / "returns" / f"{key}.json").read_text())
        items = {i.get("id"): i for i in ret.get("items") or []}
        if audit[key]["void"]:
            void[key] = "audit: " + "; ".join(sorted({f"{h['pattern']} in {h['scope']}" for h in audit[key]["hits"]}))
        elif ret.get("leak"):
            void[key] = "leak refusal: " + str(ret.get("leak_text"))[:200]
        elif (len(ret.get("items") or []) != len(UNITS) or set(items) != set(UNITS)
              or any(items[u].get("choice") not in ("A", "B", "neither") for u in UNITS)):
            void[key] = "malformed return"
        for u in UNITS:
            c = (items.get(u) or {}).get("choice")
            if c in ("A", "B", "neither"):
                votes[u][key] = {"choice_label": c, "lane": "neither" if c == "neither" else mapping[order][u][c],
                                 "confidence": items[u].get("confidence")}
out = {}
for u in UNITS:
    counted = {k: v["lane"] for k, v in votes[u].items() if k not in void}
    distinct = sorted(set(counted.values()))
    edit = {k: lanes[k][u]["verdict"] in ("agree", "amend") for k in ("g", "c")}
    if not void and len(counted) == 4 and len(distinct) == 1 and distinct[0] != "neither" and edit[distinct[0]]:
        chosen = lanes[distinct[0]][u]
        outcome = {"applied": True, "lane": distinct[0], "verdict": chosen["verdict"],
                   "text": chosen["resolution_text"] or "the packet's proposed text"}
    else:
        why = ("a judgment is void, refused or malformed" if void else
               "unanimous for keeping the current text" if len(distinct) == 1 else "the adjudications split")
        outcome = {"applied": False, "reason": why}
    out[u] = {"votes": votes[u], "counted": sorted(counted), "outcome": outcome}
tally = {"rule": "a text is applied only when all four adjudications choose it", "void": void, "items": out}
(D / "tally-a.json").write_text(json.dumps(tally, indent=1) + "\n")
print(json.dumps(tally))
