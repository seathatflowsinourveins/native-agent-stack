#!/usr/bin/env python3
"""Compare per-test (RuleID, File, StartLine) records from the gitleaks and betterleaks fixture runs
(local integration helper, scratch only). Prints no values."""
import collections
import json
import sys

gl, bl = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
out = {}
for tid in sorted(gl.keys() | bl.keys()):
    g = collections.Counter(tuple(x) for r in gl.get(tid, []) for x in r["findings"])
    b = collections.Counter(tuple(x) for r in bl.get(tid, []) for x in r["findings"])
    nulls = sum(1 for r in bl.get(tid, []) if r["report"] == "null")
    name = tid.split(".")[-1]
    row = {"gitleaks": sum(g.values()), "betterleaks": sum(b.values()), "betterleaks_null_reports": nulls,
           "missing_in_betterleaks": [list(k) + [n] for k, n in sorted((g - b).items())],
           "extra_in_betterleaks": [list(k) + [n] for k, n in sorted((b - g).items())]}
    out[name] = row
    tag = "SAME" if g == b else "DIFF"
    print(f"{tag} {name}: gitleaks={row['gitleaks']} betterleaks={row['betterleaks']}"
          + (f" (betterleaks empty report written as null x{nulls})" if nulls else ""))
    for rule, path, line, n in row["missing_in_betterleaks"]:
        print(f"      missing in betterleaks: {rule} {path}:{line}" + (f" x{n}" if n > 1 else ""))
    for rule, path, line, n in row["extra_in_betterleaks"]:
        print(f"      extra in betterleaks:   {rule} {path}:{line}" + (f" x{n}" if n > 1 else ""))
if len(sys.argv) > 3:
    json.dump(out, open(sys.argv[3], "w"), indent=1, sort_keys=True)
