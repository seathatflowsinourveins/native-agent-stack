"""Tabulate K4 from promptfoo's results-k4.json, per prereg-k4.json.

usage: python3 analyze_k4.py results-k4.json analysis-k4.json
Recomputes every grader with metrics_k4.compute_k4 and counts disagreements with promptfoo's per-assertion results
(expected 0), applies the exclusions of prereg.json, and writes per-arm counts and every run's calls, first sentence
and flags. Descriptive only: 3 runs per arm.
"""
import json
import sys
from pathlib import Path

import metrics_k4

rows = json.loads(Path(sys.argv[1]).read_text())["results"]["results"]
runs, excluded, mismatches = [], [], 0
for r in rows:
    arm = (r.get("provider") or {}).get("label", "?").removeprefix("arm-")
    try:
        s = metrics_k4.metrics.facts((r.get("response") or {}).get("output"))
    except (TypeError, ValueError):
        excluded.append({"arm": arm, "reason": f"no summary: {str(r.get('error'))[:120]}"})
        continue
    why = ("exit %s" % s["exit"] if s.get("exit") else None) or \
          (None if s.get("result_subtype") == "success" else f"result {s.get('result_subtype')}") or \
          (None if (s.get("init") or {}).get("mcp_servers") else "no init")
    if why:
        excluded.append({"arm": arm, "transcript": s.get("transcript"), "reason": why})
        continue
    m = metrics_k4.compute_k4(s)
    for c in (r.get("gradingResult") or {}).get("componentResults") or []:
        name = (c.get("assertion") or {}).get("metric")
        if name in m and bool(c.get("pass")) != m[name]:
            mismatches += 1
    runs.append({"arm": arm, "transcript": s.get("transcript"), **m,
                 "calls": [c["name"] + (f"({c['skill']})" if c.get("skill") else "") +
                           ("!" if c.get("is_error") else "") for c in s.get("calls") or []],
                 "turns": s.get("num_turns"), "cost_usd": s.get("cost_usd"), "final_head": (s.get("final") or "")[:400]})
arms = sorted({r["arm"] for r in runs} | {e["arm"] for e in excluded})
per_arm = {a: {"n": sum(r["arm"] == a for r in runs), "excluded": sum(e["arm"] == a for e in excluded),
               "counts": {k: sum(r[k] for r in runs if r["arm"] == a) for k in metrics_k4.METRICS},
               "sum_cost_usd": round(sum(r["cost_usd"] or 0 for r in runs if r["arm"] == a), 4)} for a in arms}
out = {"rows": len(rows), "included": len(runs), "excluded": excluded, "grader_mismatches": mismatches,
       "per_arm": per_arm, "runs": runs}
Path(sys.argv[2]).write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("rows", "included", "excluded", "grader_mismatches")}))
for a in arms:
    print(a, per_arm[a]["n"], per_arm[a]["counts"], per_arm[a]["sum_cost_usd"])
