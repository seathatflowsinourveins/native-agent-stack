#!/usr/bin/env python3
"""Decision statistic of A2 (PREREGISTRATION-local-models.md, Part A2): the difference of the two arms' shares of
first-pass valid tool calls over all cases and surfaces that both arms ran, with a 95% paired bootstrap interval over
cases (10,000 resamples, seed 20260927). A case is one function-calling sample id; it carries its result on every
surface for both arms. usage: a2_bootstrap.py <arm A name> <arm B name> <surface>=<validity A>,<validity B> [...]"""
import json
import random
import sys

name_a, name_b = sys.argv[1], sys.argv[2]
per_case = {}
surfaces = []
for spec in sys.argv[3:]:
    surface, files = spec.split("=", 1)
    path_a, path_b = files.split(",")
    rows = []
    for path in (path_a, path_b):
        table = {}
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            if not row.get("summary"):
                table[row["id"]] = 1 if row["valid"] else 0
        rows.append(table)
    if set(rows[0]) != set(rows[1]):
        raise SystemExit(f"surface {surface}: the two arms did not run the same cases "
                         f"({len(set(rows[0]) ^ set(rows[1]))} ids differ)")
    surfaces.append(surface)
    for case in rows[0]:
        per_case.setdefault(case, []).append((rows[0][case], rows[1][case]))
cases = sorted(per_case)
if any(len(per_case[c]) != len(surfaces) for c in cases):
    raise SystemExit("a case is missing on one surface")


def difference(ids):
    a = sum(x for c in ids for x, _ in per_case[c])
    b = sum(y for c in ids for _, y in per_case[c])
    n = len(ids) * len(surfaces)
    return a / n, b / n, (a - b) / n


share_a, share_b, diff = difference(cases)
rng = random.Random(20260927)
draws = sorted(difference([rng.choice(cases) for _ in cases])[2] for _ in range(10000))
low, high = draws[249], draws[9749]
print(json.dumps({"arms": [name_a, name_b], "surfaces": surfaces, "cases": len(cases),
                  "share": {name_a: round(share_a, 4), name_b: round(share_b, 4)}, "difference": round(diff, 4),
                  "interval_95": [round(low, 4), round(high, 4)], "resamples": 10000, "seed": 20260927,
                  "tie": low <= 0 <= high}))
