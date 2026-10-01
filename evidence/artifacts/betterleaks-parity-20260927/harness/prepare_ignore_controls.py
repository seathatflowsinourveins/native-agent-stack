#!/usr/bin/env python3
"""Inputs for the fingerprint-suppression control (local integration helper, scratch only). Takes one
fingerprint from each recorded --redact'ed betterleaks report (git mode: commit:file:rule:line; dir mode:
file:rule:line) that names exactly one finding, preferring a row triaged as a false positive, writes it
to a scratch ignore file and creates an empty directory for the no-extra-file run. Prints the chosen
rule, file and line only; the fingerprint, and so the commit, stays in the scratch file."""
import collections
import json
import sys
from pathlib import Path

D = Path(sys.argv[1])
PREFERRED = "observability/backends/configure.py"  # triaged false_positive in parity.json
(D / "repair/empty").mkdir(parents=True, exist_ok=True)
for mode, report in (("git", "reports/betterleaks-git-attempt2.json"), ("dir", "reports/betterleaks-dir.json")):
    findings = json.loads((D / report).read_text())
    counts = collections.Counter(f["Fingerprint"] for f in findings)
    unique = sorted((f for f in findings if counts[f["Fingerprint"]] == 1),
                    key=lambda f: (f["File"] != PREFERRED, f["File"], f["StartLine"], f["RuleID"], f["Fingerprint"]))
    chosen = unique[0]
    (D / f"repair/ignore-{mode}.txt").write_text(chosen["Fingerprint"] + "\n")
    print(json.dumps({"mode": mode, "recorded_findings": len(findings), "fingerprints_naming_one_finding": len(unique),
                      "chosen": [chosen["RuleID"], chosen["File"], chosen["StartLine"]]}))
