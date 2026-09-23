#!/usr/bin/env python3
"""Verify the foundation/mcp-surfaces receipts (fix round 3, round-4 review finding 2).

Checks, per receipt:
- required fields are present (id, gap_index, gap_text_sha256, preregistration{written_at, expectation, criteria},
  commands, results, outcome, evidence_class, limits, checked_at);
- gap_text_sha256 equals sha256(UTF-8 text) of that gap in the unit list (g2-units.json, layer_id "mcp-surfaces"),
  recomputed here, and the receipt's gap_text equals the unit text;
- outcome and evidence_class are in the allowed sets;
- every cited raw/helper file exists and its sha256 matches the receipt;
- preregistration written_at precedes checked_at (and each addendum's written_at too);
- every unit gap has exactly one receipt;
- results.json equals {gap_index: {outcome, receipt}} derived from the receipts.

Usage (repository root): verify_receipts.py PATH/TO/g2-units.json [OUT_TXT]
Exit status 1 on any failure; each failure is printed.
"""
import hashlib
import json
import pathlib
import sys

L = pathlib.Path("evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces")
OUTCOMES = {"settled", "advanced", "not_settled", "deferred", "covered_elsewhere"}
CLASSES = {"native_proven", "local_integration", "synthetic", "source_review"}
REQ = ("id", "gap_index", "gap_text_sha256", "preregistration", "commands", "results", "outcome", "evidence_class",
       "limits", "checked_at")

units = json.loads(pathlib.Path(sys.argv[1]).read_text())
unit = next(u for u in units if u["layer_id"] == "mcp-surfaces")
gaps = {g["index"]: g for g in unit["gaps"]}
fail, lines = [], []
receipts = {}
for p in sorted(L.glob("[0-9]*-*.json"), key=lambda q: int(q.name.split("-")[0])):
    d = json.loads(p.read_text())
    i = d.get("gap_index")
    if i in receipts:
        fail.append(f"{p.name}: second receipt for gap {i}")
    receipts[i] = (p, d)
    miss = [k for k in REQ if k not in d] + [f"preregistration.{k}" for k in ("written_at", "expectation", "criteria")
                                             if k not in d.get("preregistration", {})]
    if miss:
        fail.append(f"{p.name}: missing {miss}")
    g = gaps.get(i)
    if g is None:
        fail.append(f"{p.name}: gap_index {i} not in the unit list")
        continue
    h = hashlib.sha256(g["text"].encode()).hexdigest()
    ok_h = h == d.get("gap_text_sha256")
    ok_t = d.get("gap_text", g["text"]) == g["text"]
    if not ok_h:
        fail.append(f"{p.name}: gap_text_sha256 {d.get('gap_text_sha256')} != recomputed {h}")
    if not ok_t:
        fail.append(f"{p.name}: gap_text differs from the unit list")
    if d.get("outcome") not in OUTCOMES:
        fail.append(f"{p.name}: outcome {d.get('outcome')!r}")
    if d.get("evidence_class") not in CLASSES:
        fail.append(f"{p.name}: evidence_class {d.get('evidence_class')!r}")
    pre = d.get("preregistration", {})
    stamps = [pre.get("written_at")] + [a.get("written_at") for a in pre.get("addenda", [])]
    for s in stamps:
        if s is not None and not s < d.get("checked_at", ""):
            fail.append(f"{p.name}: preregistration stamp {s} not before checked_at {d.get('checked_at')}")
    nref = 0
    for ref in d.get("raw_evidence", []) + d.get("helper_scripts", []):
        f = pathlib.Path(ref["file"])
        nref += 1
        if not f.is_file():
            fail.append(f"{p.name}: cited file missing {f}")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != ref["sha256"]:
            fail.append(f"{p.name}: sha256 mismatch for {f}")
    lines.append(f"gap {i}: {p.name} outcome={d.get('outcome')} class={d.get('evidence_class')} "
                 f"gap_text_sha256_recomputed_match={ok_h} gap_text_match={ok_t} cited_files_checked={nref}")
for i in gaps:
    if i not in receipts:
        fail.append(f"gap {i}: no receipt")
res = json.loads((L / "results.json").read_text())["results"]
want = {str(i): {"outcome": d["outcome"], "receipt": str(p)} for i, (p, d) in receipts.items()}
if res != want:
    fail.append(f"results.json differs from receipts: {res} != {want}")
else:
    lines.append(f"results.json equals the {len(want)} receipt outcomes")
lines += [f"FAIL {x}" for x in fail] or ["all checks passed"]
text = "\n".join(lines) + "\n"
print(text, end="")
if len(sys.argv) > 2:
    pathlib.Path(sys.argv[2]).write_text(text)
sys.exit(1 if fail else 0)
