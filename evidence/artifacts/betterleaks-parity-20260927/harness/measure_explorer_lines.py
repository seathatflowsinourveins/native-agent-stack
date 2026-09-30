#!/usr/bin/env python3
"""Byte sizes behind betterleaks's git-mode findings in the generated explorer HTML (local integration
helper). Reads commit, file and line positions from the --redact'ed report, reads each blob with
`git show`, and prints only counts and byte lengths: never a value, commit or fingerprint.

gitleaks 8.30.1 builds one git-mode fragment per diff hunk from that hunk's added lines (sources/git.go
lines 394-402) and skips a fragment when len(raw) / 1_000_000 exceeds --max-target-megabytes
(detect/detect.go lines 431-438). At --max-target-megabytes 2 it therefore skips a fragment of 3,000,000
bytes or more. A finding's line is one of the added lines of its commit's hunk, so that line's length is a
lower bound on the fragment gitleaks sees."""
import json
import subprocess
import sys
from pathlib import Path

report, repo = Path(sys.argv[1]), Path(sys.argv[2])
PATH = "docs/ecosystem/index.html"
SKIP_FROM = 3_000_000
rows = [f for f in json.loads(report.read_text()) if f["File"] == PATH]
blobs, lengths = {}, []
for f in rows:
    if f["Commit"] not in blobs:
        raw = subprocess.run(["git", "show", f"{f['Commit']}:{PATH}"], cwd=repo, capture_output=True, check=True).stdout
        blobs[f["Commit"]] = (len(raw), raw.split(b"\n"))
    size, lines = blobs[f["Commit"]]
    lengths.append((f["Commit"], f["StartLine"], len(lines[f["StartLine"] - 1])))
line_bytes = {(c, n): b for c, n, b in lengths}
summary = {
    "file": PATH,
    "findings": len(rows),
    "distinct_commits": len(blobs),
    "distinct_lines": len(line_bytes),
    "line_bytes": {"min": min(line_bytes.values()), "max": max(line_bytes.values())},
    "blob_bytes": {"min": min(s for s, _ in blobs.values()), "max": max(s for s, _ in blobs.values())},
    "newlines_per_blob": {"min": min(len(ls) - 1 for _, ls in blobs.values()), "max": max(len(ls) - 1 for _, ls in blobs.values())},
    "findings_on_lines_of_at_least_3000000_bytes": sum(1 for _, _, b in lengths if b >= SKIP_FROM),
}
print(json.dumps(summary))
