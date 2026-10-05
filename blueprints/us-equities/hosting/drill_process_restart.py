#!/usr/bin/env python3
"""Operator-only drill: kill an existing start-all, observe restart and next due run.

Run later on the chosen operating host (user decision 2), with its locked trading
Python. This script never installs, enables or starts a unit. The operator must
have deployed the private templates and have supplied fresh local research input.

Sources: systemd/systemd@v255:man/systemd.service.xml:830-836;
dagucloud/dagu@v2.16.6:internal/cmd/startall.go:32-45;
internal/cmd/history.go:568-602; internal/persis/file/dagrun/dagrun.go:55-59;
internal/ir/run_status.go:156-179; internal/ir/status.go:10-18,133-149.
Process restart is not reboot, missed-run or independent-alert acceptance.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import session_day


def unit_state(unit: str) -> dict:
    completed = subprocess.run(
        ["systemctl", "--user", "show", unit, "--property=MainPID,NRestarts,ActiveState,Restart,ExecStart"],
        capture_output=True, text=True, timeout=15, check=False)
    if completed.returncode:
        raise ValueError(f"systemctl show failed (exit {completed.returncode})")
    return dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)


def due_run(status: dict, due: datetime, run_ids: set[str]) -> bool:
    """A successful native record must attest the exact slot and scheduler trigger."""
    if not (status.get("name") == "equity-research-evidence" and
            status.get("dagRunId") in run_ids and status.get("triggerType") == 1 and
            status.get("status") == 4):
        return False
    slot = status.get("scheduleTime")
    return bool(slot and datetime.fromisoformat(slot) == due)


def last_status(path: Path) -> dict:
    # Upstream status.jsonl is appended while running, then compacted after finish.
    # Ignore an incomplete trailing write and retain the last complete native record.
    last = {}
    with path.open() as stream:
        for line in stream:
            try:
                last = json.loads(line)
            except json.JSONDecodeError:
                continue
    return last


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", default="dagu-equities.service")
    parser.add_argument("--dagu-bin", type=Path, required=True)
    parser.add_argument("--dagu-home", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dag-history", type=Path, required=True,
                        help="the chosen host's native history directory for this one DAG")
    parser.add_argument("--due-at", required=True, help="the next 16:30 New York session slot, with offset")
    parser.add_argument("--wait-seconds", type=int, default=900)
    args = parser.parse_args(argv)
    try:
        due = datetime.fromisoformat(args.due_at)
        now = datetime.now(timezone.utc)
        if due.utcoffset() is None or not 1 <= args.wait_seconds <= 3600:
            raise ValueError("use an aware due time and a wait bound of 1..3600 seconds")
        market = due.astimezone(session_day.MARKET_ZONE)
        if (market.hour, market.minute, market.second, market.microsecond) != (16, 30, 0, 0):
            raise ValueError("--due-at must be the named schedule's 16:30 New York slot")
        if not now + timedelta(seconds=15) < due < now + timedelta(seconds=args.wait_seconds - 180):
            raise ValueError("run the drill shortly before the next due slot; reserve 180 seconds for completion")
        # Normal helper command validates the package pin; do not kill anything on a holiday.
        checked = subprocess.run([os.sys.executable, str(Path(session_day.__file__)), "--at", due.isoformat()],
                                 capture_output=True, text=True, timeout=60, check=False)
        if checked.returncode or checked.stdout.strip() != "session":
            raise ValueError(f"locked session check refused the due slot (exit {checked.returncode})")
        config = args.config.read_text()
        if "run_dags: false" not in config or not args.dag_history.is_dir():
            raise ValueError("use the deployed read-only UI config and this DAG's history directory")
        before = unit_state(args.unit)
        if (before.get("ActiveState") != "active" or before.get("Restart") != "on-failure" or
                "start-all" not in before.get("ExecStart", "") or str(args.config) not in before["ExecStart"]):
            raise ValueError("the chosen existing unit must run start-all with this config and on-failure restart")
        pid = int(before["MainPID"])
        # Linux operating-host drill: verify identity before signalling this one process.
        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        if pid <= 1 or b"start-all" not in command or Path(f"/proc/{pid}/exe").resolve() != args.dagu_bin.resolve():
            raise ValueError("MainPID is not the chosen start-all executable")
        deadline = time.monotonic() + args.wait_seconds
        os.kill(pid, signal.SIGKILL)  # SIGTERM is a clean exit and need not trigger on-failure.
        restart_deadline = min(deadline, time.monotonic() + 90)
        while True:
            after = unit_state(args.unit)
            if (after.get("ActiveState") == "active" and int(after.get("MainPID", "0")) not in (0, pid) and
                    int(after.get("NRestarts", "0")) > int(before["NRestarts"])):
                break
            if time.monotonic() >= restart_deadline:
                raise ValueError("start-all did not restart within 90 seconds")
            time.sleep(2)
        history_command = [str(args.dagu_bin), "history", "--context", "local", "--dagu-home",
                           str(args.dagu_home), "--config", str(args.config), "--format", "json",
                           "--from", due.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "--limit", "1000", "--status", "succeeded", "equity-research-evidence"]
        while time.monotonic() < deadline:
            history = subprocess.run(history_command, capture_output=True, text=True, timeout=30, check=False)
            if history.returncode:
                raise ValueError(f"dagu history failed (exit {history.returncode})")
            ids = {row["dagRunId"] for row in json.loads(history.stdout)}
            # The public history rendering omits triggerType/scheduleTime. Corroborate in
            # the original native status records instead of accepting an unrelated manual run.
            for path in args.dag_history.rglob("status.jsonl"):
                status = last_status(path)
                if due_run(status, due, ids):
                    print(json.dumps({"result": "passed", "pid_changed": True,
                                      "automatic_restart_observed": True, "next_due_run": "succeeded",
                                      "scheduler_trigger_observed_with_run_dags_false": True,
                                      "due_at": due.isoformat(), "native_status_sha256":
                                      hashlib.sha256(path.read_bytes()).hexdigest(),
                                      "gate": "same-host process restart only"}, sort_keys=True))
                    return 0
            time.sleep(5)
        raise ValueError("the next exact due slot has no successful scheduler-triggered run")
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        reason = str(error) if type(error) is ValueError else type(error).__name__
        print(json.dumps({"result": "failed", "reason": reason}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
