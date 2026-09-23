"""Gap 5 diagnostic: per-year count of differing raw closes (aggregates only) between two sources."""
import sys, json, collections
from decimal import Decimal
sys.path.insert(0, sys.argv[1])
import compare_multi as cm
ref = cm.open_source(sys.argv[2], set(sys.argv[4].split(",")), sys.argv[5], sys.argv[6])
pro = cm.open_source(sys.argv[3], set(sys.argv[4].split(",")), sys.argv[5], sys.argv[6])
out = {}
for s in sys.argv[4].split(","):
    r, p = ref.bars.get(s, {}), pro.bars.get(s, {})
    by = collections.defaultdict(lambda: [0, 0, Decimal(0)])
    for d in sorted(r.keys() & p.keys()):
        delta = abs(Decimal(p[d]) - Decimal(r[d])); y = by[d[:4]]
        y[0] += 1; y[1] += delta != 0; y[2] = max(y[2], delta)
    out[s] = {y: {"compared": v[0], "different": v[1], "max_abs": str(v[2])} for y, v in sorted(by.items())}
print(json.dumps(out, indent=1))
