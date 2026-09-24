#!/usr/bin/env python3
"""Validate Codex/Claude outputs against the schema and compute agreement.

Usage: score_reviews.py PACKET_DIR CODEX_LAST_MESSAGE CLAUDE_RESULT OUT_JSON
TypeSafe verdicts and prior source-review labels for C1-C8 come from the
retained blueprints/native-skill-practice files.
"""
import json
import os
import sys

import jsonschema

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "native-skill-practice"))
pk, codex_path, claude_path, out = sys.argv[1:5]
schema = json.load(open(f"{pk}/schema.json"))
labels = {k: v["label"] for k, v in json.load(open(f"{pk}/labels-frozen.json")).items()}
outputs = {"codex": json.load(open(codex_path)), "claude": json.load(open(claude_path))["structured_output"]}
report = {"schema_validation": {}, "per_case": {}, "agreement": {}}
verdicts = {}
for who, data in outputs.items():
    try:
        jsonschema.validate(data, schema)
        ids = [c["case_id"] for c in data["cases"]]
        ok = len(ids) == len(set(ids)) == len(labels)
        report["schema_validation"][who] = "valid" if ok else "valid schema but duplicate/missing case_id"
    except jsonschema.ValidationError as exc:
        report["schema_validation"][who] = f"invalid: {exc.message}"
    verdicts[who] = {c["case_id"]: c["verdict"] for c in data["cases"]}
ts = {r["case_id"]: r["verdict"] for r in json.load(open(f"{ROOT}/typesafe-result.json"))["providers"]["typesafe-jev-1.13.0-evidence-v1"]["rows"]}
prior = {}
for a in json.load(open(f"{ROOT}/native-receipt.json"))["attempts"]:
    rr = a.get("returned_report")
    if isinstance(rr, dict):
        prior[a["client"]] = {c["case_id"]: c["verdict"].split(" ")[0] for c in rr.get("result", rr).get("cases", [])}
for cid in labels:
    report["per_case"][cid] = {"frozen_label": labels[cid], "codex_blind": verdicts["codex"].get(cid), "claude_blind": verdicts["claude"].get(cid),
                               "typesafe_2026_09_21": ts.get(cid), "prior_codex_review": prior.get("codex", {}).get(cid), "prior_claude_review": prior.get("claude", {}).get(cid)}
orig = [f"C{i}" for i in range(1, 9)]
new = [f"C{i}" for i in range(9, 21)]


def agree(a, b, ids):
    return sum(1 for c in ids if report["per_case"][c][a] == report["per_case"][c][b])


for who in ("codex_blind", "claude_blind"):
    report["agreement"][who] = {
        "vs_frozen_label_C1_C8": f"{agree(who, 'frozen_label', orig)}/8",
        "vs_typesafe_C1_C8": f"{agree(who, 'typesafe_2026_09_21', orig)}/8",
        "vs_frozen_label_C9_C20": f"{agree(who, 'frozen_label', new)}/12",
        "vs_frozen_label_all_20": f"{agree(who, 'frozen_label', orig + new)}/20",
    }
report["agreement"]["codex_blind_vs_claude_blind_all_20"] = f"{agree('codex_blind', 'claude_blind', orig + new)}/20"
report["agreement"]["typesafe_vs_frozen_label_C1_C8"] = f"{agree('typesafe_2026_09_21', 'frozen_label', orig)}/8"
report["C4"] = report["per_case"]["C4"]
json.dump(report, open(out, "w"), indent=1)
print(json.dumps({k: report[k] for k in ("schema_validation", "agreement", "C4")}, indent=1))
print("disagreements with frozen label:", {c: v for c, v in report["per_case"].items() if v["codex_blind"] != v["frozen_label"] or v["claude_blind"] != v["frozen_label"]})
