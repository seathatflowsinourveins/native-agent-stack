#!/usr/bin/env python3
"""Capture native vendor commands; this script implements no MCP protocol.

References: modelcontextprotocol/conformance v0.1.16 README.md (client/server
commands and results), and Linux proc_pid_smaps(5) for Pss in smaps_rollup.
Run once per labelled observation; logs and commands remain explicit evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from datetime import datetime, timezone


def process_tree(pid):
    pending, found = [pid], set()
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        try:
            children = Path(f"/proc/{current}/task/{current}/children").read_text()
            pending.extend(int(value) for value in children.split())
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return found


def pss_kib(pid):
    total, observed = 0, 0
    for child in process_tree(pid):
        try:
            lines = Path(f"/proc/{child}/smaps_rollup").read_text().splitlines()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        for line in lines:
            if line.startswith("Pss:"):
                total += int(line.split()[1])
                observed += 1
                break
    return total, observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or "/" in args.label or ".." in args.label:
        parser.error("a command and a simple label are required")
    args.out.mkdir(parents=True, exist_ok=True)
    paths = {kind: args.out / f"{args.label}.{kind}" for kind in ("stdout", "stderr", "json")}
    if paths["json"].exists():
        parser.error("an existing observation is immutable; choose a new label")
    started = datetime.now(timezone.utc).isoformat()
    before = time.perf_counter()
    samples, peak, process_count, timed_out = 0, 0, 0, False
    with paths["stdout"].open("wb") as stdout, paths["stderr"].open("wb") as stderr:
        process = subprocess.Popen(command, cwd=args.cwd, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        while process.poll() is None:
            memory, count = pss_kib(process.pid)
            peak, process_count = max(peak, memory), max(process_count, count)
            samples += 1
            if time.perf_counter() - before > args.timeout:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                break
            time.sleep(0.05)
    record = {
        "label": args.label, "started_utc": started,
        "command": command, "cwd": str(args.cwd), "return_code": process.returncode,
        "timed_out": timed_out, "elapsed_seconds": round(time.perf_counter() - before, 6),
        "pss": {"peak_process_tree_kib": peak, "max_observed_processes": process_count,
                "samples": samples, "interval_seconds": 0.05,
                "source": "/proc/<owned-pid>/smaps_rollup:Pss",
                "scope": "owned command process tree; shared host servers excluded"},
        "logs": {kind: {"path": path.name, "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                 for kind, path in paths.items() if kind != "json"}
    }
    paths["json"].write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({key: record[key] for key in ("label", "return_code", "elapsed_seconds", "pss")}))


if __name__ == "__main__":
    main()
