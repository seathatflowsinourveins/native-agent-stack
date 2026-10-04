"""Check that attempt 2's two orders carry the same evidence once the A/B labels are mapped back to lanes."""
import json
import sys
from pathlib import Path

J = Path(sys.argv[1])
m = json.loads(Path(sys.argv[2]).read_text())


def norm(t, o):
    return t.replace("Return A's text", f"[{m[o]['A']}]").replace("Return B's text", f"[{m[o]['B']}]")


ok = True
for key in ("comparison_k1_k3", "comparison_k4"):
    lines = {o: norm(json.loads((J / f"packets/x9.{o}.json").read_text())[key], o).splitlines() for o in ("AB", "BA")}
    only_ab = [x for x in lines["AB"] if x not in lines["BA"]]
    only_ba = [x for x in lines["BA"] if x not in lines["AB"]]
    for x in only_ab:
        print(key, "AB only:", x[:230])
    for x in only_ba:
        print(key, "BA only:", x[:230])
    ok &= not only_ab and not only_ba and sorted(lines["AB"]) == sorted(lines["BA"])
print("same evidence in both orders:", ok)
