#!/usr/bin/env python3
"""Disposable fixture: does a Dagu in-flight step RESUME after the run
process is killed mid-step (SIGKILL), or does the interrupted step simply
re-execute from its beginning on retry?

Never touches the live dagu-equities service. Uses a brand-new, caller-supplied
private work directory as both DAGU_HOME and the DAG's working_dir.

Usage: fixture.py --dagu /path/to/dagu --work /new/private/dir [--label L]
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import uuid

HOLD_SECONDS = 120
from datetime import datetime, timezone
from pathlib import Path


def sh(argv, cwd, env, timeout=30):
    p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def read_marker(path):
    return path.read_text().strip() if path.exists() else None


def run(dagu, work, sleep_s=20, label="inflight"):
    if not work.is_absolute() or work.exists() or work.is_symlink():
        raise ValueError("--work must name a new absolute private directory")
    dagu = dagu.resolve(strict=True)
    work.mkdir(mode=0o700, parents=True)
    home = work / "dagu-home"
    home.mkdir()
    started_marker = work / "STARTED_MARKER"
    finished_marker = work / "FINISHED_MARKER"
    after_marker = work / "AFTER_MARKER"
    dag_path = work / "inflight.yaml"
    dag_path.write_text(
        "\n".join([
            "type: graph",
            "timeout_sec: 120",
            "working_dir: " + json.dumps(str(work)),
            "steps:",
            "  - id: longstep",
            "    command: >",
            "      sh -c 'date +%s%N > STARTED_MARKER; sleep " + str(sleep_s) + "; date +%s%N > FINISHED_MARKER'",
            "  - id: afterstep",
            "    depends: [longstep]",
            "    command: sh -c 'echo after > AFTER_MARKER'",
            "",
        ]), encoding="utf-8")
    env = {"HOME": str(work), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "DAGU_HOME": str(home),
           "TMPDIR": str(work), "DO_NOT_TRACK": "1"}
    base = [str(dagu), "--context", "local", "--dagu-home", str(home)]
    run_id = f"{label}-" + uuid.uuid4().hex[:12]

    version_code, version_out, _ = sh([str(dagu), "version"], work, env)
    version_out = version_out.strip()

    result = {"schema": "dagu-inflight-fixture-v1", "dagu_path": str(dagu), "dagu_version": version_out,
              "run_id": run_id, "sleep_s": sleep_s, "started_at_utc": datetime.now(timezone.utc).isoformat()}

    # Phase 1: start the DAG in the background, wait for the mid-step marker, then SIGKILL.
    with (work / "start1.stdout").open("w") as out, (work / "start1.stderr").open("w") as err:
        proc = subprocess.Popen(base + ["start", "--run-id", run_id, str(dag_path)],
                                 cwd=work, env=env, stdout=out, stderr=err, start_new_session=True)
    deadline = time.monotonic() + 30
    saw_started = False
    while time.monotonic() < deadline:
        if started_marker.exists():
            saw_started = True
            break
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    result["saw_started_before_kill"] = saw_started
    result["finished_marker_present_before_kill"] = finished_marker.exists()
    started_value_before_kill = read_marker(started_marker)
    result["started_marker_value_before_kill"] = started_value_before_kill

    # SIGKILL the whole process group (dagu forks children for step commands).
    kill_ok = True
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        kill_ok = False
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        kill_ok = False
    result["killpg_issued"] = kill_ok
    result["proc_group_reaped"] = proc.poll() is not None
    time.sleep(1)
    result["finished_marker_present_after_kill"] = finished_marker.exists()

    hist_code, hist_out, hist_err = sh(base + ["history", "--run-id", run_id, "--format", "json"], work, env)
    result["history_after_kill_exit"] = hist_code
    result["history_after_kill_raw"] = hist_out[:4000]

    ps_code, ps_out, _ = sh([str(dagu), "--context", "local", "--dagu-home", str(home), "ps"], work, env)
    result["ps_after_kill_exit"] = ps_code
    result["ps_after_kill_raw"] = ps_out[:2000]

    # Immediate check (~1-2s after kill, matching the earlier inconclusive run) is
    # already captured above via history_after_kill_raw/ps_after_kill_raw. No
    # separate probe DAG-run is issued here: an earlier version of this fixture tried
    # a same-DAG noop probe under a different run-id, but that probe itself started a
    # fresh 20s longstep in the foreground and timed out its own 10s subprocess call,
    # so it is removed rather than fixed with a longer timeout that would just delay
    # the hold below.

    # Hold past both documented thresholds (30s lock-stale, 90s heartbeat-stale) before the real recovery attempt.
    hold_s = HOLD_SECONDS
    result["hold_seconds_before_recovery_attempt"] = hold_s
    result["hold_started_utc"] = datetime.now(timezone.utc).isoformat()
    time.sleep(hold_s)
    result["hold_ended_utc"] = datetime.now(timezone.utc).isoformat()

    hist_posthold_code, hist_posthold_out, _ = sh(base + ["history", "--run-id", run_id, "--format", "json"], work, env)
    result["history_after_hold_raw"] = hist_posthold_out[:4000]

    # Phase 2a: does re-issuing `start` with the SAME run-id automatically resume, now past both thresholds?
    restart_same_id_code, restart_same_id_out, restart_same_id_err = sh(
        base + ["start", "--run-id", run_id, str(dag_path)], work, env, timeout=40)
    result["restart_same_run_id_exit"] = restart_same_id_code
    result["restart_same_run_id_stdout"] = restart_same_id_out[:2000]
    result["restart_same_run_id_stderr"] = restart_same_id_err[:2000]
    result["started_marker_value_after_restart_attempt"] = read_marker(started_marker)
    result["finished_marker_present_after_restart_attempt"] = finished_marker.exists()

    # Phase 2b: the documented mechanism -- `dagu retry --run-id`, also past both thresholds.
    retry_code, retry_out, retry_err = sh(base + ["retry", "--run-id", run_id, str(dag_path)], work, env, timeout=40)
    result["retry_exit"] = retry_code
    result["retry_stdout"] = retry_out[:2000]
    result["retry_stderr"] = retry_err[:2000]

    deadline2 = time.monotonic() + 30
    while time.monotonic() < deadline2 and not after_marker.exists():
        time.sleep(0.1)

    started_value_after_retry = read_marker(started_marker)
    result["started_marker_value_after_retry"] = started_value_after_retry
    result["finished_marker_present_after_retry"] = finished_marker.exists()
    result["after_marker_present_after_retry"] = after_marker.exists()
    result["longstep_reexecuted_from_scratch"] = (
        started_value_before_kill is not None and started_value_after_retry is not None
        and started_value_after_retry != started_value_before_kill
    )

    hist2_code, hist2_out, _ = sh(base + ["history", "--run-id", run_id, "--format", "json"], work, env)
    result["history_after_retry_exit"] = hist2_code
    result["history_after_retry_raw"] = hist2_out[:6000]

    result["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    (work / "result.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dagu", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--sleep", type=int, default=20)
    parser.add_argument("--label", default="inflight")
    args = parser.parse_args()
    out = run(args.dagu, args.work, sleep_s=args.sleep, label=args.label)
    print(json.dumps(out, indent=2))
