#!/usr/bin/env python3
"""Independent own-process and sentinel observer; no SDK imports or state reads.

Uses Python's supported pathlib and /proc process metadata. It reads only the
assigned capture receipt, the named sentinel's existence and the named owned
processes' stat/comm metadata. It never reads environment, transcripts or auth.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["interrupt", "recover", "decline"])
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=240)
    args = parser.parse_args()
    os.umask(0o077)
    args.captures.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt = args.captures / f"{args.mode}-receipt.json"
    sentinel = args.captures / "decline-workspace" / "approval-sentinel.txt"
    output = args.captures / f"{args.mode}-independent-observation.json"
    began = time.monotonic()
    samples = []
    seen_processes = {}
    sentinel_seen = False
    ended = False
    while time.monotonic() - began <= args.max_seconds:
        capture = json.loads(receipt.read_text()) if receipt.exists() else {}
        for process in capture.get("native_processes", []):
            seen_processes[process["pid"]] = process
        # AsyncCodexClient starts Popen from asyncio.to_thread (pinned
        # async_client.py:73-81,93-95). Linux children is task-specific, so
        # independently inspect every task of this exact owned Python worker.
        worker_pid = capture.get("worker_pid")
        if worker_pid is not None:
            try:
                task_paths = list(Path(f"/proc/{worker_pid}/task").iterdir())
            except FileNotFoundError:
                task_paths = []
            for task_path in task_paths:
                try:
                    children = (task_path / "children").read_text().split()
                except FileNotFoundError:
                    continue
                for child in children:
                    try:
                        stat = Path(f"/proc/{child}/stat").read_text().rsplit(") ", 1)[1].split()
                        comm = Path(f"/proc/{child}/comm").read_text().strip()
                    except FileNotFoundError:
                        continue
                    seen_processes[int(child)] = {"pid": int(child), "comm": comm,
                                                  "start_ticks": stat[19]}
        observation = {"at": now(), "capture_receipt_seen": bool(capture),
                       "sentinel_exists": sentinel.exists(), "processes": []}
        sentinel_seen |= observation["sentinel_exists"]
        for pid, process in seen_processes.items():
            try:
                stat = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
                observation["processes"].append({"pid": pid, "same_process_alive":
                    stat[19] == process["start_ticks"], "state": stat[0]})
            except FileNotFoundError:
                observation["processes"].append({"pid": pid, "same_process_alive": False})
        samples.append(observation)
        if capture.get("ended_at"):
            ended = True
            break
        time.sleep(0.1)
    result = {"kind": "independent_native_control_observation", "mode": args.mode,
              "observer_pid": os.getpid(), "started_at": samples[0]["at"], "ended_at": now(),
              "sampling_interval_seconds": 0.1, "capture_ended_seen": ended,
              "sentinel_seen_anytime": sentinel_seen, "samples": samples,
              "native_owned_processes_seen": list(seen_processes.values()),
              "all_observed_owned_processes_gone": bool(seen_processes)
                  and all(not p["same_process_alive"] for p in samples[-1]["processes"]),
              "limitations": "Existence polling, not provider-side cancellation; process termination exit code is not independently observed."}
    output.write_text(json.dumps(result, indent=2) + "\n")
    output.chmod(0o600)
    print(json.dumps({"mode": args.mode, "capture_ended_seen": ended,
                      "process_cleanup_observed": result["all_observed_owned_processes_gone"],
                      "sentinel_seen_anytime": sentinel_seen, "sample_count": len(samples)}))
    return 0 if ended else 2


if __name__ == "__main__":
    raise SystemExit(main())
