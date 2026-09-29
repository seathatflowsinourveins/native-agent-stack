"""Tabulate the X9 round-3 comparison (K5, K6) from promptfoo's results-r3.json, per prereg-r3.json.

usage: python3 analyze_r3.py results-r3.json analysis-r3.json
Adapted from round 2's k4/analyze_k4.py. Recomputes every grader with metrics_r3.compute_r3 and counts disagreements
with promptfoo's per-assertion results (expected 0), applies prereg-r3.json's exclusions, and writes per-arm and
per-case counts, every run's calls, first sentence and flags, and the preregistered metric order between g and c
(decision_rule step 2). Arm 0 is a control and is never ranked.
"""
import json
import sys
from pathlib import Path

import metrics_r3

MODEL = "claude-opus-5-5[1m]"
TOKENS = {"g": 96, "c": 72, "0": 30}  # o200k, gpt-tokenizer 3.4.0, W3/tok/arm-token-counts.txt
MAX_EXCLUDED = 4

rows = json.loads(Path(sys.argv[1]).read_text())["results"]["results"]
runs, excluded, mismatches = [], [], 0
for r in rows:
    arm = (r.get("provider") or {}).get("label", "?").removeprefix("arm-")
    case = ((r.get("testCase") or {}).get("vars") or r.get("vars") or {}).get("case", "?")
    try:
        s = metrics_r3.metrics.facts((r.get("response") or {}).get("output"))
    except (TypeError, ValueError):
        excluded.append({"arm": arm, "case": case, "reason": f"no summary: {str(r.get('error'))[:120]}"})
        continue
    init = s.get("init") or {}
    why = ("exit %s" % s["exit"] if s.get("exit") else None) or \
          (None if s.get("result_subtype") == "success" else f"result {s.get('result_subtype')}") or \
          (None if init.get("model") == MODEL else f"model {init.get('model')}") or \
          (None if case != "K6" or (metrics_r3.metrics.servers(s).get(metrics_r3.TARGETS["K6"]) == "connected"
                                    and s.get("target_tools_in_init") == 2)
           else "fixture server not connected with its 2 tools in init") or \
          (None if case != "K5" or (s.get("hook") or {}).get("exists") else "hook marker missing")
    if why:
        excluded.append({"arm": arm, "case": case, "transcript": s.get("transcript"), "reason": why})
        continue
    m = metrics_r3.compute_r3(s, case)
    for c in (r.get("gradingResult") or {}).get("componentResults") or []:
        name = (c.get("assertion") or {}).get("metric")
        if name in m and bool(c.get("pass")) != m[name]:
            mismatches += 1
    runs.append({"arm": arm, "case": case, "transcript": s.get("transcript"), **m,
                 "non_answer": not m["status_given"] and not m["question_only"],
                 "init_status": metrics_r3.metrics.servers(s).get(metrics_r3.TARGETS["K6"]),
                 "hook": s.get("hook"), "mcp_events": (s.get("mcp") or {}).get("events"),
                 "calls": [c["name"] + (f"({c['skill']})" if c.get("skill") else "") +
                           ("!" if c.get("is_error") else "") for c in s.get("calls") or []],
                 "turns": s.get("num_turns"), "duration_ms": s.get("duration_ms"), "cost_usd": s.get("cost_usd"),
                 "final_head": (s.get("final") or "")[:400]})

KEYS = metrics_r3.METRICS + ("non_answer",)
arms = sorted({r["arm"] for r in runs} | {e["arm"] for e in excluded})


def counts(sel):
    return {k: sum(bool(r[k]) for r in sel) for k in KEYS}


per_arm = {a: {"n": sum(r["arm"] == a for r in runs), "excluded": sum(e["arm"] == a for e in excluded),
               "counts": counts([r for r in runs if r["arm"] == a]),
               "per_case": {k: dict(n=sum(r["arm"] == a and r["case"] == k for r in runs),
                                    **counts([r for r in runs if r["arm"] == a and r["case"] == k]))
                            for k in ("K5", "K6")},
               "sum_cost_usd": round(sum(r["cost_usd"] or 0 for r in runs if r["arm"] == a), 4),
               "o200k_tokens": TOKENS.get(a)} for a in arms}

complete = len(excluded) <= MAX_EXCLUDED and len(rows) == 30
order = None
if complete and {"g", "c"} <= set(per_arm):
    g, c = per_arm["g"]["counts"], per_arm["c"]["counts"]
    steps = [("wrong_status", g["wrong_status"], c["wrong_status"], "fewer"),
             ("correct_status", g["correct_status"], c["correct_status"], "more"),
             ("non_answer", g["non_answer"], c["non_answer"], "fewer"),
             ("o200k_tokens", TOKENS["g"], TOKENS["c"], "fewer")]
    order = {"steps": [], "winner": None}
    for name, gv, cv, better in steps:
        order["steps"].append({"metric": name, "g": gv, "c": cv, "better": better})
        if gv != cv:
            order["winner"] = ("g" if gv < cv else "c") if better == "fewer" else ("g" if gv > cv else "c")
            order["decided_by"] = name
            break

out = {"rows": len(rows), "included": len(runs), "excluded": excluded, "grader_mismatches": mismatches,
       "complete": complete, "metric_order": order, "per_arm": per_arm, "runs": runs}
Path(sys.argv[2]).write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("rows", "included", "excluded", "grader_mismatches", "complete",
                                      "metric_order")}))
for a in arms:
    print(a, per_arm[a]["n"], per_arm[a]["counts"], per_arm[a]["sum_cost_usd"])
