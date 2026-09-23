#!/usr/bin/env python3
"""Build the 20-case evidence-judgment packet (C1-C8 unchanged + C9-C20 new).

Usage: build_typesafe_extension.py OUT_DIR
Writes cases.json (case_id, source, claim, source_ref: sent to models),
labels-frozen.json (expected labels, never sent to models), schema.json and
prompt.txt. Sources for C9-C20 are verbatim line ranges of retained repository
documents, read at build time; labels were written by this agent before any
model call (not independently reviewed).
"""
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
out = sys.argv[1]
os.makedirs(out, exist_ok=True)


def lines(path, start, end):
    text = open(os.path.join(ROOT, path)).read().splitlines()
    return "\n".join(text[start - 1:end]) + "\n"


S = {
    "S1": ("docs/promptfoo-upstream-retrieval.md", 15, 22),
    "S2": ("docs/promptfoo-upstream-retrieval.md", 64, 68),
    "S3": ("docs/native-skill-practice-20260921.md", 116, 118),
    "S4": ("docs/native-skill-practice-20260921.md", 107, 109),
}
NEW = [
    ("C9", "S1", "The September 21 execution ranked all four paired documents first.", "supported"),
    ("C10", "S1", "The execution is evidence of general retrieval superiority.", "contradicted"),
    ("C11", "S1", "The execution had two failing Promptfoo cases.", "contradicted"),
    ("C12", "S2", "vLLM metric snapshots rose by 336 prompt tokens during the final evaluation window.", "supported"),
    ("C13", "S2", "The run cost less in US dollars than a hosted embedding API would have.", "insufficient"),
    ("C14", "S2", "The 336-token figure is exclusive per-evaluation billing.", "contradicted"),
    ("C15", "S3", "Both native reviews returned all eight judgments.", "supported"),
    ("C16", "S3", "The Claude review finished faster than the Codex review.", "insufficient"),
    ("C17", "S3", "The Codex review accepted a 'contradicted' label for C4.", "contradicted"),
    ("C18", "S4", "TypeSafe matched more frozen labels than the literal-containment baseline.", "supported"),
    ("C19", "S4", "The TypeSafe requests returned two service errors.", "contradicted"),
    ("C20", "S4", "TypeSafe's 7/8 result generalizes to a representative domain benchmark.", "insufficient"),
]

orig = json.load(open(os.path.join(ROOT, "blueprints/native-skill-practice/catalog-cases.json")))
cases, labels = [], {}
for c in orig:
    cid = c["metadata"]["case_id"]
    cases.append({"case_id": cid, "source_ref": c["metadata"]["source_ref"], "source": c["vars"]["source"], "claim": c["vars"]["claim"]})
    labels[cid] = {"label": c["vars"]["expected"], "label_origin": "frozen 2026-09-21 catalog-cases.json (independent reviewer before inference)"}
for cid, sid, claim, label in NEW:
    path, a, b = S[sid]
    cases.append({"case_id": cid, "source_ref": f"{path}#L{a}-L{b}", "source": lines(path, a, b), "claim": claim})
    labels[cid] = {"label": label, "label_origin": "authored by the gap-wave-2 agent before any model call; not independently reviewed"}

schema = {
    "type": "object", "additionalProperties": False, "required": ["cases"],
    "properties": {"cases": {"type": "array", "minItems": len(cases), "maxItems": len(cases), "items": {
        "type": "object", "additionalProperties": False, "required": ["case_id", "verdict", "rationale"],
        "properties": {"case_id": {"type": "string", "enum": [c["case_id"] for c in cases]},
                       "verdict": {"type": "string", "enum": ["supported", "contradicted", "insufficient"]},
                       "rationale": {"type": "string"}}}}},
}
prompt = (
    "You are an evidence reviewer. For each case below, judge the CLAIM only against its SOURCE excerpt.\n"
    "Do not use tools, files, the network or outside knowledge.\n"
    "verdict = supported if the source states or directly entails the claim; contradicted if the source states "
    "something incompatible with the claim; insufficient if the source neither entails nor contradicts it.\n"
    "Return one JSON object matching the provided schema, with exactly one entry per case_id, in order, and a "
    "one-sentence rationale each.\n\n"
    + "\n".join(f"=== {c['case_id']} (source_ref: {c['source_ref']})\nSOURCE:\n{c['source']}\nCLAIM: {c['claim']}\n" for c in cases)
)
for name, data in (("cases.json", cases), ("labels-frozen.json", labels), ("schema.json", schema)):
    open(os.path.join(out, name), "w").write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
open(os.path.join(out, "prompt.txt"), "w").write(prompt)
for name in ("cases.json", "labels-frozen.json", "schema.json", "prompt.txt"):
    print(hashlib.sha256(open(os.path.join(out, name), "rb").read()).hexdigest(), name)
