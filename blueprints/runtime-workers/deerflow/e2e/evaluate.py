"""Supervise unchanged Inspect GAIA scoring; never compute an answer score.

Inspect AI@0.3.271 model/_providers/providers.py:361-365 (none),
_cli/eval.py:1681-1682 (exit reports completion, not correctness),
log/_log.py:798-820,848-895 (scores/metrics). Status and result are host-written.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recipe import HERE, PREFIX, STATE, arm_settings, read, write


def verdict(log, evidence_complete):
    results = log.get("results") or {}
    if (log.get("status") != "success" or not results.get("total_samples")
            or results.get("completed_samples") != results["total_samples"]):
        return 3, "incomplete"
    scores = [s for s in results.get("scores", []) if s.get("name", "").split("/")[-1] == "gaia_scorer"]
    if len(scores) != 1:
        return 3, "incomplete"
    value = scores[0].get("metrics", {}).get("accuracy", {}).get("value")
    if type(value) not in (int, float) or not 0 <= value <= 1:
        return 3, "incomplete"
    if value < 1:
        return 1, "negative"
    return (0, "pass") if evidence_complete else (3, "incomplete")


def evaluate(frozen_id, run_id, arm, epochs):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id) or not frozen_id or epochs < 1:
        raise ValueError("provide a safe stable run ID, a frozen GAIA ID and positive epochs")
    selection = arm_settings(read(STATE / "host.json") if (STATE / "host.json").is_file() else {}, arm)
    run = STATE / "runs" / run_id
    run.mkdir(parents=True, mode=0o700, exist_ok=False)
    result_path = run / "result.json"
    write(run / "status.json", {"status":"starting", "arm":arm, "result_path":str(result_path)})
    write(result_path, {"arm":arm, "verdict":"incomplete", "exit_code":3})
    print(json.dumps({"status_path":str(run / "status.json"), "result_path":str(result_path)}), flush=True)
    logs = run / "inspect"
    logs.mkdir(mode=0o700)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", DEERFLOW_RUN_ID=run_id,
               RUNTIME_WORKER_ARM=arm, INSPECT_EVALS_CACHE_DIR=str(STATE / "eval-cache"))
    command = [str(PREFIX / "grader/bin/inspect"), "eval", str(HERE / "e2e/gaia.py@deerflow_gaia"),
               "-T", "instance_ids=" + frozen_id, "--model", "none", "--max-samples", "1",
               "--epochs", str(epochs), "--log-format", "json", "--log-dir", str(logs)]
    for name in ("arm", "model", "base_url"):
        command.extend(["--metadata", name + "=" + selection[name]])
    try:
        if not (STATE / "host.json").is_file():
            raise ValueError("host setup is missing")
        with (run / "inspect-output.log").open("w") as output:
            completed = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, check=False)
        paths = sorted(logs.glob("*.json"))
        log = read(paths[0]) if len(paths) == 1 else {}
        attempts = [read(p) for p in sorted(run.glob("attempt-*/receipt.json"))]
        evidence = len(attempts) == epochs and all(
            a["transport"]["ok"] and a["gateway"].get("evidence_complete")
            and a["observations"]["required_skills_activated"]
            and all(v == "absent" for v in a["cleanup"].values()) for a in attempts)
        code, label = verdict(log, evidence)
        if completed.returncode and code == 0:
            code, label = 3, "incomplete"
        result = {**selection, "exit_code":code, "verdict":label,
                  "inspect_exit_code":completed.returncode,
                  "inspect_log":str(paths[0]) if len(paths) == 1 else None,
                  "receipt_path":str(run / "receipt.json")}
        write(run / "receipt.json", {**selection, "grader":{
            "name":"inspect_evals.gaia.gaia_scorer", "version":"0.22.0",
            "verdict":label, "accuracy":next((s.get("metrics", {}).get("accuracy", {}).get("value")
                for s in (log.get("results") or {}).get("scores", []) if s.get("name", "").split("/")[-1] == "gaia_scorer"), None)},
            "attempts":attempts})
    except (OSError, ValueError, KeyError):
        code = 2
        result = {**selection, "exit_code":code, "verdict":"setup-failure"}
    write(result_path, result)
    write(run / "status.json", {"status":result["verdict"], "arm":arm, "result_path":str(result_path), "exit_code":code})
    print(json.dumps({"result_path":str(result_path), "exit_code":code}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen_id")
    parser.add_argument("run_id")
    parser.add_argument("--arm", choices=("control", "engines-on"), default=os.environ.get("RUNTIME_WORKER_ARM", "control"))
    parser.add_argument("--epochs", type=int, default=int(os.environ.get("DEERFLOW_EPOCHS", "1")))
    args = parser.parse_args()
    os.umask(0o077)
    try:
        return evaluate(args.frozen_id, args.run_id, args.arm, args.epochs)
    except (OSError, ValueError):
        print(json.dumps({"exit_code":2, "verdict":"setup-failure"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
