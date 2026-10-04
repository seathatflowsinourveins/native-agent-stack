#!/usr/bin/env python3
"""Cross-arm comparison for the mcporter qualification: x = 0.14.1 candidate, y = 0.13.13 baseline."""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
X = json.loads((HERE / "results-x.json").read_text())
Y = json.loads((HERE / "results-y.json").read_text())
sx = {s["name"]: s for s in X["steps"]}
sy = {s["name"]: s for s in Y["steps"]}
names = [s["name"] for s in Y["steps"]] + [n for n in sx if n not in sy]

rows, only_x_fail, only_y_fail, mismatch = [], [], [], []
for n in names:
    a, b = sx.get(n), sy.get(n)
    px, py = (a or {}).get("pass"), (b or {}).get("pass")
    rows.append((n, px, py, (a or {}).get("exit"), (b or {}).get("exit"), (a or {}).get("wall_s"), (b or {}).get("wall_s")))
    if px != py:
        mismatch.append(n)
        (only_x_fail if py and not px else only_y_fail).append(n)


def raw(arm, name):
    d = HERE / "raw" / arm
    f = sorted(d.glob(f"*-{name}.out"))
    return f[0].read_text() if f else ""


checks = {}
for srv in ("ai-memory", "jcodemunch"):
    n = f"S4-list-{srv}"
    checks[f"{n} tool names equal"] = sx[n].get("tool_names") == sy[n].get("tool_names")
    checks[f"{n} tool count x/y"] = [sx[n].get("tool_count"), sy[n].get("tool_count")]
checks["B2d brief tool names equal"] = sx.get("B2d-list-context-mode-brief", {}).get("brief_tool_names") == sy.get("B2d-list-context-mode-brief", {}).get("brief_tool_names")
checks["B2d brief tool count x/y"] = [len(sx.get("B2d-list-context-mode-brief", {}).get("brief_tool_names") or []),
                                      len(sy.get("B2d-list-context-mode-brief", {}).get("brief_tool_names") or [])]
checks["B2d brief output sha256 equal"] = sx.get("B2d-list-context-mode-brief", {}).get("brief_output_sha256") == sy.get("B2d-list-context-mode-brief", {}).get("brief_output_sha256")
checks["A4 memory_status top-level keys equal"] = sx["A4-ai-memory-status"].get("top_level_keys") == sy["A4-ai-memory-status"].get("top_level_keys")
checks["A4 keys"] = sx["A4-ai-memory-status"].get("top_level_keys")
hx = [l for l in raw("x", "R-socraticode-use-1").splitlines() if l.startswith("[")]
hy = [l for l in raw("y", "R-socraticode-use-1").splitlines() if l.startswith("[")]
checks["socraticode health [..] lines equal"] = hx == hy
checks["socraticode health lines"] = hx
for n in ("R-socraticode-use-2", "R-socraticode-use-3"):
    rx = re.search(r"oracle ranks (\{[^}]*\})", raw("x", n))
    ry = re.search(r"oracle ranks (\{[^}]*\})", raw("y", n))
    checks[f"{n} oracle ranks x|y"] = [rx.group(1) if rx else None, ry.group(1) if ry else None]
for n in ("B3b-probe-while-lock-held-fails", "B3c-probe-after-holder-exit-recovers", "B2a-probe-refuses-after-daemon-sigkill"):
    checks[f"{n} wall_s x/y"] = [sx.get(n, {}).get("wall_s"), sy.get(n, {}).get("wall_s")]
checks["A3 ppid chain x"] = sx["A3-probe-persistence-and-ppid-chain"].get("ppid_chain_to_daemon")
checks["A3 ppid chain y"] = sy["A3-probe-persistence-and-ppid-chain"].get("ppid_chain_to_daemon")

summary = {
    "x_version": X["version"], "y_version": Y["version"],
    "x_passed": X["passed"], "y_passed": Y["passed"],
    "x_steps": len(X["steps"]), "y_steps": len(Y["steps"]),
    "x_failed": [s["name"] for s in X["steps"] if not s["pass"]],
    "y_failed": [s["name"] for s in Y["steps"] if not s["pass"]],
    "outcome_mismatches": mismatch, "fail_only_on_candidate": only_x_fail, "fail_only_on_baseline": only_y_fail,
    "checks": checks,
    "x_cleanup": X.get("cleanup"), "y_cleanup": Y.get("cleanup"),
    "x_exception": X.get("harness_exception"), "y_exception": Y.get("harness_exception"),
}
(HERE / "compare.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
print(json.dumps(summary, indent=1))
print("\nstep                                         x    y   exit x/y  wall x/y")
for n, px, py, ex, ey, wx, wy in rows:
    print(f"{n:44s} {str(px)[0] if px is not None else '-'}    {str(py)[0] if py is not None else '-'}   {ex}/{ey}    {wx}/{wy}")
