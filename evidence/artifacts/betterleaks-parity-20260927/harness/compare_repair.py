#!/usr/bin/env python3
"""Compare the repair-round reports with the recorded ones (local integration helper, scratch only).
Keys are rule, file, line and column positions, plus the commit in git mode; only counts and booleans
are printed, never a value, commit or fingerprint."""
import collections
import json
import sys
from pathlib import Path

D = Path(sys.argv[1])


def load(name):
    return json.loads((D / name).read_text()) or []


def keys(findings, git):
    return collections.Counter((f["RuleID"], f["File"], f["StartLine"], f["EndLine"], f["StartColumn"], f["EndColumn"])
                               + ((f["Commit"],) if git else ()) for f in findings)


out = {}
for mode, recorded, git in (("git", "reports/betterleaks-git-attempt2.json", True), ("dir", "reports/betterleaks-dir.json", False)):
    prefix = "G" if git else "T"
    rec = load(recorded)
    job, one, empty = (load(f"repair/{prefix}{n}.json") for n in ("1-job-argv", "2-one-fingerprint", "3-empty-dir"))
    ignored = (D / f"repair/ignore-{mode}.txt").read_text().strip()
    dropped = [f for f in job if f["Fingerprint"] == ignored]
    out[mode] = {
        "recorded": len(rec), "job_argv": len(job), "one_fingerprint": len(one), "empty_dir": len(empty),
        "job_argv_same_findings_as_recorded": keys(job, git) == keys(rec, git),
        "one_fingerprint_equals_job_argv_minus_that_fingerprint": keys(one, git) == keys(job, git) - keys(dropped, git),
        "findings_named_by_the_fingerprint": len(dropped),
        "empty_dir_same_findings_as_job_argv": keys(empty, git) == keys(job, git),
        "secret_fields_redacted": all(f["Secret"] == "REDACTED" for f in rec + job + one + empty),
    }
print(json.dumps(out, indent=1))
