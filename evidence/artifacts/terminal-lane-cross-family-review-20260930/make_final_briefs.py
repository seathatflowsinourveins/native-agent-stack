#!/usr/bin/env python3
"""Write one private verification brief per verification unit of the final review pass: <out>/<unit>.brief.md holds the checkout path, the rules and every finding of the unit in full (id, severity, file:line,
claim, the reviewer's evidence, failure scenario, proposed fix, whether it ran a test), and, for a finding that another job reported too, the other report's claim and evidence as corroboration (the models are not
named beyond 'another job'). The unit table is a JSON file: {"<unit>": {"findings": ["F-..-1", ...], "also": {"F-..-1": ["F-..-9", ...]}}}.
usage: make_final_briefs.py <consolidated.json> <units.json> <out-dir> <checkout>"""
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
units = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
out, checkout = Path(sys.argv[3]), sys.argv[4]
out.mkdir(parents=True, exist_ok=True)
by_id = {f["id"]: f for f in data["findings"]}
for unit, spec in units.items():
    lines = [f"# Verification brief for review unit {unit}", "",
             f"Checkout (read-only, do not modify): {checkout}", "",
             "Definitions: high = wrong behavior, data loss, a security defect, or a false claim a reader would act on; medium = wrong edge behavior, a control that cannot fail, an overstated or unsupported claim; low = a minor inaccuracy or hygiene issue.", "",
             "Context: the checkout is the MERGED state of a repository on which two earlier review rounds were repaired. Verify each finding against that checkout as it is; do not look at any other tree.", ""]
    for finding_id in spec["findings"]:
        f = by_id[finding_id]
        lines += [f"## {f['id']}  (reviewer severity {f['severity']}, reviewer ran a test: {f['tested']})",
                  f"Location: {f['file']}:{f['line']}", f"Claim: {f['claim']}", f"Reviewer's evidence: {f['evidence']}",
                  f"Failure scenario: {f['failure_scenario']}", f"Reviewer's proposed fix: {f['fix']}", ""]
        for other_id in spec.get("also", {}).get(finding_id, []):
            o = by_id[other_id]
            lines += [f"### Independently reported by another job as {o['id']} ({o['severity']}, ran a test: {o['tested']}, {o['file']}:{o['line']})",
                      f"Its claim: {o['claim']}", f"Its evidence: {o['evidence']}", ""]
    (out / f"{unit}.brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(unit, len(spec["findings"]), "findings ->", f"{unit}.brief.md", (out / f"{unit}.brief.md").stat().st_size, "bytes")
