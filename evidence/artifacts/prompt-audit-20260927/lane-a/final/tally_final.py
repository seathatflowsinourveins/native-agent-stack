"""Tally lane A's final round on X5a and X5c under the packet's rule (k2/packets/packet.md, "Convergence rule, fixed
before either lane runs"), with the lane audit.

usage: tally_final.py
Reads returns/gpt6.json, returns/claude.json and audit-lanes.json; writes tally-final.json.
Per item: both lanes agree -> apply the proposed change; both amend with the same resolution_text -> apply it; both
reject -> keep the current text; anything else -> one blind adjudication in both orders by both families. A lane
whose audit has a voiding hit, or whose return lacks exactly one entry per item, counts for no item, and an item
without two counted verdicts keeps the current text (this is the final round).
"""
import json
from pathlib import Path

X = Path(__file__).resolve().parent
UNITS = ("X5a", "X5c")
audit = json.loads((X / "audit-lanes.json").read_text())["judgments"]
lanes, void = {}, {}
for lane in ("gpt6", "claude"):
    ret = json.loads((X / "returns" / f"{lane}.json").read_text())
    items = {i.get("id"): i for i in ret.get("items") or []}
    if audit[lane]["void"]:
        void[lane] = "audit: " + "; ".join(sorted({f"{h['pattern']} in {h['scope']}" for h in audit[lane]["hits"]}))
    elif len(ret.get("items") or []) != len(UNITS) or set(items) != set(UNITS) or any(
            items[u].get("verdict") not in ("agree", "amend", "reject") for u in UNITS):
        void[lane] = "malformed return"
    lanes[lane] = items
out = {}
for u in UNITS:
    v = {lane: {"verdict": lanes[lane][u]["verdict"], "confidence": lanes[lane][u].get("confidence"),
                "resolution_text": lanes[lane][u].get("resolution_text", "")} for lane in lanes if u in lanes[lane]}
    if void:
        outcome = "keep the current text: a lane is void or malformed (final round)"
    elif v["gpt6"]["verdict"] == v["claude"]["verdict"] == "agree":
        outcome = "apply the proposed change"
    elif v["gpt6"]["verdict"] == v["claude"]["verdict"] == "reject":
        outcome = "keep the current text"
    elif (v["gpt6"]["verdict"] == v["claude"]["verdict"] == "amend"
          and v["gpt6"]["resolution_text"].strip() == v["claude"]["resolution_text"].strip()):
        outcome = "apply the common amendment"
    else:
        outcome = "adjudicate (one blind round, both orders, both families; applied only when all four choose it)"
    out[u] = {"lanes": v, "outcome": outcome}
tally = {"rule": "both agree: apply; both reject: keep; same amendment: apply; otherwise adjudicate", "void": void,
         "items": out}
(X / "tally-final.json").write_text(json.dumps(tally, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({u: {"lanes": {k: (x["verdict"], x["confidence"]) for k, x in r["lanes"].items()},
                      "outcome": r["outcome"]} for u, r in out.items()}, ensure_ascii=False), "void:", void)
