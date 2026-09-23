#!/usr/bin/env python3
"""Fix round 2: write Promptfoo configs for one frozen case set.

Usage: gen_fixround2_configs.py CASES_JSON OUT_DIR
Writes typed.yaml (Nemotron, model-card input types), untyped.yaml (Nemotron,
round-1 single request), bge.yaml (bge-small-en-v1.5) and control.yaml
(constant pred=0), plus labels.json. The assertion text is identical to
gen_heldout_promptfoo.py's: it compares the printed prediction with
context.vars.label.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heldout_common import load_cases  # noqa: E402

ASSERT = (
    "const m = String(output).trim().match(/^pred=(\\d+)$/);\n"
    "if (!m) { return {pass: false, score: 0, reason: 'unparseable output: ' + output}; }\n"
    "const pred = Number(m[1]); const label = Number(context.vars.label);\n"
    "return {pass: pred === label, score: pred === label ? 1 : 0, reason: 'pred=' + pred + ' vars.label=' + label};\n"
)


def write(path, provider, label, rows):
    lines = ["description: Held-out retrieval eval (fix round 2); label read from test vars, not provider output",
             "prompts:", "  - '{{payload}}'", "providers:", f"  - id: file://{provider}", f"    label: {label}", "tests:"]
    for i, (payload, lab) in enumerate(rows):
        lines += [f"  - description: case-{i:02d}", "    vars:", f"      payload: {json.dumps(payload)}", f"      label: {lab}",
                  "    assert:", "      - type: javascript", f"        value: {json.dumps(ASSERT)}"]
    open(path, "w").write("\n".join(lines) + "\n")


cases, out = sys.argv[1], sys.argv[2]
rows = load_cases(cases)
write(os.path.join(out, "typed.yaml"), "pf_provider_typed.py", "Nemotron-3-Embed-1B, model-card input_type query/document", rows)
write(os.path.join(out, "untyped.yaml"), "pf_provider.py", "Nemotron-3-Embed-1B, single request without input_type (round-1 call)", rows)
write(os.path.join(out, "bge.yaml"), "pf_provider_bge.py", "BAAI/bge-small-en-v1.5 via fastembed 0.8.1", rows)
write(os.path.join(out, "control.yaml"), "pf_control_provider.py", "constant pred=0 control", rows)
json.dump([{"case": i, "label": lab} for i, (_, lab) in enumerate(rows)], open(os.path.join(out, "labels.json"), "w"), indent=0)
print(len(rows), "cases; label==0 count:", sum(1 for _, lab in rows if lab == 0))
