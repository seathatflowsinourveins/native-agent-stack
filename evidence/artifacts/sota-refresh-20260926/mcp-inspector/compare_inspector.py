#!/usr/bin/env python3
"""Compare the two Inspector arms step by step (exit, pass, stdout identity) and write compare.json."""
import json, sys
from pathlib import Path
base = Path(sys.argv[1])
a = json.loads((base / "arms/2.7.0/results.json").read_text())
b = json.loads((base / "arms/2.8.0/results.json").read_text())
sa = {s["step"]: s for s in a["steps"]}
sb = {s["step"]: s for s in b["steps"]}
rows = []
for step in sa:
    x, y = sa[step], sb.get(step, {})
    row = {"step": step}
    for key in ("exit", "pass", "gate", "auth_line", "api_config_no_header", "api_config_wrong_token",
                "api_config_scratch_token", "tool_names", "hits", "error_code", "counts", "opening_browser_line"):
        if key in x or key in y:
            row[key] = {"2.7.0": x.get(key), "2.8.0": y.get(key)}
    if "stdout_sha256" in x:
        row["stdout_identical"] = x["stdout_sha256"] == y.get("stdout_sha256")
        row["stderr_identical"] = x["stderr_sha256"] == y.get("stderr_sha256")
    diffs = [k for k, v in row.items() if isinstance(v, dict) and v["2.7.0"] != v["2.8.0"]]
    row["differs_in"] = diffs
    rows.append(row)
summary = {
    "gated_pass": {"2.7.0": a["gated_pass"], "2.8.0": b["gated_pass"]},
    "gated_steps": {v: sum(1 for s in r["steps"] if not s["step"].startswith("A8")) for v, r in (("2.7.0", a), ("2.8.0", b))},
    "gated_steps_passed": {v: sum(1 for s in r["steps"] if not s["step"].startswith("A8") and s.get("pass")) for v, r in (("2.7.0", a), ("2.8.0", b))},
    "web_auth_gate": {"2.7.0": a["web_auth_gate"], "2.8.0": b["web_auth_gate"]},
    "steps_with_differences": [r["step"] for r in rows if r["differs_in"]],
}
out = {"summary": summary, "rows": rows}
(base / "compare.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(summary, indent=1))
for r in rows:
    if r["differs_in"] or not r.get("stdout_identical", True):
        print(r["step"], "differs_in", r["differs_in"], "stdout_identical", r.get("stdout_identical"), "stderr_identical", r.get("stderr_identical"))
