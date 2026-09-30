#!/usr/bin/env python3
"""Write one private verification brief per review job that has findings: <out>/<job>.brief.md holds the checkout path, the rules and every finding of that job in full
(id, severity, file:line, claim, the reviewer's evidence, failure scenario, proposed fix, whether it ran a test). The reviewer's identity is not named beyond 'another model family'.
usage: make_verify_briefs.py <consolidated.json> <out-dir> <checkout> <job>[:<id>,<id>...] [...]"""
import json, sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out, checkout, jobs = Path(sys.argv[2]), sys.argv[3], sys.argv[4:]
out.mkdir(parents=True, exist_ok=True)
for spec in jobs:
    job, _, only = spec.partition(":")
    wanted = only.split(",") if only else None
    findings = [f for f in data["findings"] if f["job"] == job and (wanted is None or f["id"] in wanted)]
    if not findings:
        print(job, "no findings")
        continue
    lines = [f"# Verification brief for review unit {job}", "",
             f"Checkout (read-only, do not modify): {checkout}", "",
             "Definitions: high = wrong behavior, data loss, a security defect, or a false claim a reader would act on; medium = wrong edge behavior, a control that cannot fail, an overstated or unsupported claim; low = a minor inaccuracy or hygiene issue.", ""]
    for f in findings:
        lines += [f"## {f['id']}  (reviewer severity {f['severity']}, reviewer ran a test: {f['tested']})",
                  f"Location: {f['file']}:{f['line']}", f"Claim: {f['claim']}", f"Reviewer's evidence: {f['evidence']}",
                  f"Failure scenario: {f['failure_scenario']}", f"Reviewer's proposed fix: {f['fix']}", ""]
    (out / f"{job}.brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(job, len(findings), "findings ->", f"{job}.brief.md", (out / f"{job}.brief.md").stat().st_size, "bytes")
