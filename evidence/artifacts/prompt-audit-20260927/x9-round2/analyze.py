"""Tabulate the X9 round-2 comparison from promptfoo's results.json, per the preregistration (prereg.json).

usage: uv run --no-project --with scipy==1.18.1 python3 analyze.py results.json analysis.json
Recomputes every grader with metrics.compute on the same output and counts disagreements with promptfoo's own
per-assertion results (expected 0), applies the preregistered exclusions, and writes per-arm and per-case counts,
median turns, median duration and cost without each arm's first run (it pays the shared prefix's cache writes), summed
cost, and two-sided Fisher exact tests between arms on `correct` and
`no_builtin_skill` (descriptive only: 9 runs per arm cannot show equivalence).
"""
import itertools
import json
import statistics
import sys
from pathlib import Path

from scipy.stats import fisher_exact

import metrics

rows = json.loads(Path(sys.argv[1]).read_text())["results"]["results"]
runs, excluded, mismatches = [], [], 0
for r in rows:
    arm = (r.get("provider") or {}).get("label", "?").removeprefix("arm-")
    v = r.get("vars") or (r.get("testCase") or {}).get("vars") or {}
    out = (r.get("response") or {}).get("output")
    try:
        s = metrics.facts(out)
    except (TypeError, ValueError):
        excluded.append({"arm": arm, "case": v.get("case"), "reason": f"no summary: {str(r.get('error'))[:120]}"})
        continue
    why = ("exit %s" % s["exit"] if s.get("exit") else None) or \
          (None if s.get("result_subtype") == "success" else f"result {s.get('result_subtype')}") or \
          (None if (s.get("init") or {}).get("mcp_servers") else "no init")
    if why:
        excluded.append({"arm": arm, "case": v.get("case"), "transcript": s.get("transcript"), "reason": why})
        continue
    m = metrics.compute(s, v["case"], v.get("target", ""))
    for c in (r.get("gradingResult") or {}).get("componentResults") or []:
        name = (c.get("assertion") or {}).get("metric")
        if name in m and bool(c.get("pass")) != m[name]:
            mismatches += 1
    runs.append({"arm": arm, "case": v["case"], "transcript": s.get("transcript"), **m,
                 "calls": [c["name"] + (f"({c['skill']})" if c.get("skill") else "") +
                           ("!" if c.get("is_error") else "") for c in s.get("calls") or []],
                 "turns": s.get("num_turns"), "duration_ms": s.get("duration_ms"), "cost_usd": s.get("cost_usd"),
                 "final_head": (s.get("final") or "")[:240]})


def med(xs):
    return round(statistics.median(xs), 4) if xs else None


arms = sorted({r["arm"] for r in runs} | {e["arm"] for e in excluded})
table = {}
for a in arms:
    rs = [r for r in runs if r["arm"] == a]
    later = sorted(rs, key=lambda r: r["transcript"])[1:]  # the arm's first run pays the shared prefix's cache writes
    table[a] = {"n": len(rs), "excluded": sum(e["arm"] == a for e in excluded),
                "counts": {k: sum(r[k] for r in rs) for k in metrics.METRICS},
                "by_case": {k: {c: sum(r[k] for r in rs if r["case"] == c) for c in ("K1", "K2", "K3")}
                            for k in metrics.METRICS},
                "median_turns": statistics.median([r["turns"] for r in rs]) if rs else None,
                "median_duration_s_after_first": med([r["duration_ms"] / 1000 for r in later]),
                "median_cost_usd_after_first": med([r["cost_usd"] or 0 for r in later]),
                "sum_cost_usd": round(sum(r["cost_usd"] or 0 for r in rs), 4)}
fisher = {}
for a, b in itertools.combinations(arms, 2):
    for k in ("correct", "no_builtin_skill"):
        ta, tb = table[a], table[b]
        grid = [[ta["counts"][k], ta["n"] - ta["counts"][k]], [tb["counts"][k], tb["n"] - tb["counts"][k]]]
        fisher[f"{a}-{b}:{k}"] = {"table": grid, "p_two_sided": round(float(fisher_exact(grid)[1]), 4)}
result = {"rows": len(rows), "included": len(runs), "excluded": excluded, "grader_mismatches": mismatches,
          "per_arm": table, "fisher": fisher, "runs": runs}
Path(sys.argv[2]).write_text(json.dumps(result, indent=1) + "\n")
print(json.dumps({k: result[k] for k in ("rows", "included", "excluded", "grader_mismatches")}))
for a in arms:
    t = table[a]
    print(a, t["n"], t["counts"], t["median_turns"], t["median_duration_s_after_first"],
          t["median_cost_usd_after_first"], t["sum_cost_usd"])
print(json.dumps(fisher))
