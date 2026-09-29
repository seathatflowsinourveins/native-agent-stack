"""Check that round 3's two orders carry the same evidence once the A/B labels are mapped back to lanes: round 2's
check_orders.py (the revised one that sorts per-text clauses and exits 1 on a difference), over round 3's keys.

usage: check_orders_r3.py PACKETS_DIR MAPPING_JSON
The keys whose text names the returns (the comparisons, round 2's outcome and points) are compared after the labels
are mapped back to lanes, as sorted lines with the per-text clauses in each line sorted; every other key must be
byte-identical between the orders. Exits 1 on any difference.
"""
import json
import re
import sys
from pathlib import Path

P = Path(sys.argv[1])
m = json.loads(Path(sys.argv[2]).read_text())
CLAUSE = re.compile(r"\[[gc]\] [^;.)]*")
LABELLED = ("comparison_k1_k3", "comparison_k4", "comparison_k5_k6", "round_2", "round_2_points")


def norm(t, o):
    t = "\n".join(t) if isinstance(t, list) else t
    t = t.replace("Return A's text", f"[{m[o]['A']}]").replace("Return B's text", f"[{m[o]['B']}]")
    lines = []
    for line in t.splitlines():
        clauses = iter(sorted(CLAUSE.findall(line)))
        lines.append(CLAUSE.sub(lambda _: next(clauses), line))
    return sorted(lines)


pk = {o: json.loads((P / f"x9.{o}.json").read_text()) for o in ("AB", "BA")}
ok = True
for key in LABELLED:
    a, b = (norm(pk[o][key], o) for o in ("AB", "BA"))
    for x in [x for x in a if x not in b]:
        print(key, "AB only:", x[:230])
    for x in [x for x in b if x not in a]:
        print(key, "BA only:", x[:230])
    ok &= a == b
rest = [k for k in pk["AB"] if k not in LABELLED]
same_rest = set(pk["AB"]) == set(pk["BA"]) and all(pk["AB"][k] == pk["BA"][k] for k in rest)
print("same evidence in both orders:", ok, "| other packet keys identical:", same_rest, rest)
sys.exit(0 if ok and same_rest else 1)
