"""Check that attempt 2's two orders carry the same evidence once the A/B labels are mapped back to lanes.

usage: check_orders.py PACKETS_DIR MAPPING_JSON
PACKETS_DIR holds x9.AB.json and x9.BA.json. Each order lists its Return A first, so after mapping the labels back
([g], [c]) the table rows and the per-text clauses inside a line ("[c] 3; [g] 2") come in a different order; rows
are compared as sorted lists and the per-text clauses inside a line are sorted in place. Exits 1 on any difference.
Revised 2026-09-28 after review: the first version did not sort the clauses inside a line, so it printed False on
the same evidence, and it exited 0 either way.
"""
import json
import re
import sys
from pathlib import Path

P = Path(sys.argv[1])
m = json.loads(Path(sys.argv[2]).read_text())
CLAUSE = re.compile(r"\[[gc]\] [^;.)]*")


def norm(t, o):
    t = t.replace("Return A's text", f"[{m[o]['A']}]").replace("Return B's text", f"[{m[o]['B']}]")
    lines = []
    for line in t.splitlines():
        clauses = iter(sorted(CLAUSE.findall(line)))
        lines.append(CLAUSE.sub(lambda _: next(clauses), line))
    return sorted(lines)


ok = True
for key in ("comparison_k1_k3", "comparison_k4"):
    a, b = (norm(json.loads((P / f"x9.{o}.json").read_text())[key], o) for o in ("AB", "BA"))
    for x in [x for x in a if x not in b]:
        print(key, "AB only:", x[:230])
    for x in [x for x in b if x not in a]:
        print(key, "BA only:", x[:230])
    ok &= a == b
rest = [k for k in json.loads((P / "x9.AB.json").read_text()) if k not in ("comparison_k1_k3", "comparison_k4")]
same_rest = all(json.loads((P / "x9.AB.json").read_text())[k] == json.loads((P / "x9.BA.json").read_text())[k]
                for k in rest)
print("same evidence in both orders:", ok, "| other packet keys identical:", same_rest, rest)
sys.exit(0 if ok and same_rest else 1)
