#!/usr/bin/env python3
"""Write the compact, sanitized evidence files of the S1, S2 and R1 runs (local integration script).

    build_evidence.py --state DIR --out DIR [--entry URL] [--upstream URL]

Reads DIR/runs/*/result.json (run_task.py) and DIR/runs/*/r1.json (run_r1.py), joins each run id to the entry and upstream
gateways' call logs through gateway_usage.py (numeric fields only) and writes one JSON file per stage into --out:
s1-runs.json (tag s1v2), s2-runs.json (tag s2) and r1.json. A run carries the pi-reported usage per request, the tool lanes,
the RTK tracker delta, the fixture check and the gateway rows; no prompt, model output, host path, account, connection or key
field is copied. A run with no matching gateway row keeps requests 0, which means unknown, not zero usage.
"""
import argparse
import json
from pathlib import Path

import gateway_usage as gu

STAGES = {"s1v2": "S1", "s2": "S2"}


def gw_block(logs, name, run_id):
    if logs.get(name) is None:
        return None
    t = gu.totals(logs[name], run_id)
    return {k: t[k] for k in ("requests", "status", "in", "out", "cacheRead", "cacheWrite", "reasoning", "compressed", "duration_ms", "rows")}


def label(result):
    off = (result.get("arm_headers") or {}).get("x-omniroute-compression") == "off"
    return result["arm"] + ("-gwoff" if result["arm"] != "plain" and off else "")


def compact_pi(pi):
    return {"usage": pi["usage"], "assistant_messages": pi["assistant_messages"], "last_stop_reason": pi["last_stop_reason"],
            "auto_retries": pi["auto_retries"], "first_error": pi["first_error"], "tools": pi["tools"], "tool_errors": pi["tool_errors"],
            "lanes": pi["lanes"], "per_request": pi["per_request"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--entry", default="http://127.0.0.1:20129")
    parser.add_argument("--upstream", default="http://127.0.0.1:20128")
    a = parser.parse_args()
    logs = {}
    for name, base in (("entry", a.entry), ("upstream", a.upstream)):
        try:
            logs[name] = gu.fetch(base, 5000)
        except Exception as error:
            logs[name] = None
            print(f"# {name}: {error!r}")
    a.out.mkdir(parents=True, exist_ok=True)
    stages = {"S1": [], "S2": []}
    for path in sorted((a.state / "runs").glob("*/result.json")):
        r = json.loads(path.read_text())
        tag = r["run_id"].rsplit("-", 1)[-1]
        if tag not in STAGES:
            continue
        stages[STAGES[tag]].append({
            "run_id": r["run_id"], "arm": label(r), "client_arm": r["arm"], "task": r["task"], "attempt": r["attempt"],
            "started_utc": r["started_utc"], "wall_seconds": r["wall_seconds"], "exit_code": r["exit_code"], "timed_out": r["timed_out"],
            "fixture_commit": r["fixture_commit"], "passed": r["check"]["passed"], "check": r["check"]["detail"],
            "arm_headers": r["arm_headers"], "gateway_state_before": r["gateway_state_before"], "rtk_tracker_delta": r["rtk_tracker_delta"],
            "pi": compact_pi(r["pi_reported"]),
            "gateway_entry": gw_block(logs, "entry", r["run_id"]), "gateway_upstream": gw_block(logs, "upstream", r["run_id"])})
    for stage, name in (("S1", "s1-runs.json"), ("S2", "s2-runs.json")):
        runs = sorted(stages[stage], key=lambda x: x["run_id"])
        (a.out / name).write_text(json.dumps({"stage": stage, "runs": runs}, indent=1) + "\n")
        print(name, len(runs), "runs")
    for path in sorted((a.state / "runs").glob("*/r1.json")):
        r = json.loads(path.read_text())
        s2 = r.get("segment2") or {}
        out = {"stage": "R1", "run_id": r["run_id"], "resume_run_id": r["resume_run_id"], "arm": r["arm"], "task": r["task"],
               "fixture_commit": r["fixture_commit"], "kill_after_responses": r["kill_after_responses"],
               "responses_seen_before_kill": r["responses_seen_before_kill"], "killed": r["killed"], "descendants_at_kill": r["descendants_at_kill"],
               "survivors_after_3s": r["survivors_after_3s"], "session_files": r["session_files"], "session_roles_kept": r["session_roles_kept"],
               "gateway_state_before": r["gateway_state_before"], "segment1": {"wall_seconds": r["segment1_wall_s"], "pi": compact_pi(r["segment1"]),
                                                                            "gateway_entry": gw_block(logs, "entry", r["run_id"])},
               "segment2": {"exit_code": s2.get("exit_code"), "timed_out": s2.get("timed_out"), "wall_seconds": s2.get("wall_s"),
                            "pi": compact_pi(s2["pi_reported"]) if s2 else None, "gateway_entry": gw_block(logs, "entry", r["resume_run_id"])},
               "passed": r["check"]["passed"], "check": r["check"]["detail"]}
        (a.out / "r1.json").write_text(json.dumps(out, indent=1) + "\n")
        print("r1.json", r["run_id"])


if __name__ == "__main__":
    main()
