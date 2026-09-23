#!/usr/bin/env python3
"""Write the held-out Promptfoo configs from the frozen cases.json.

Usage: gen_heldout_promptfoo.py CASES_JSON OUT_DIR
Writes promptfooconfig.yaml (model provider) and control.yaml (constant
provider). The label lives in each test's vars; the assertion compares the
provider's printed prediction with context.vars.label.
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
    lines = [
        "description: Held-out 30-case retrieval eval; label read from test vars, not provider output",
        "prompts:",
        "  - '{{payload}}'",
        "providers:",
        f"  - id: file://{provider}",
        f"    label: {label}",
        "tests:",
    ]
    for i, (payload, lab) in enumerate(rows):
        lines += [
            f"  - description: case-{i:02d}",
            "    vars:",
            f"      payload: {json.dumps(payload)}",
            f"      label: {lab}",
            "    assert:",
            "      - type: javascript",
            f"        value: {json.dumps(ASSERT)}",
        ]
    open(path, "w").write("\n".join(lines) + "\n")


cases, out = sys.argv[1], sys.argv[2]
rows = load_cases(cases)
write(os.path.join(out, "promptfooconfig.yaml"), "pf_provider.py", "vLLM Nemotron-3-Embed-1B cosine argmax", rows)
write(os.path.join(out, "control.yaml"), "pf_control_provider.py", "constant pred=0 control", rows)
json.dump([{"case": i, "label": lab} for i, (_, lab) in enumerate(rows)], open(os.path.join(out, "labels.json"), "w"), indent=0)
print(len(rows), "cases; label==0 count:", sum(1 for _, lab in rows if lab == 0))
