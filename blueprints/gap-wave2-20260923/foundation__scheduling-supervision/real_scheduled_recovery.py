#!/usr/bin/env python3
"""Gap 2: a real project workflow, triggered by the native Dagu 2.16.6 scheduler,
stopped with `dagu stop` mid-run and recovered with `dagu retry --step finalize`.

Oracle fields follow blueprints/convergence-practice/job-recovery/run.py (native
aborted -> selected-step retry -> succeeded under one run ID, checkpoint executed
once and unchanged, owned processes retired) plus output integrity against a
direct reference run of the same scripts on the same snapshot.

Usage: real_scheduled_recovery.py --work /new/absolute/dir [--base-commit SHA] [--no-model]
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import time

import dagu_common as dc
import real_steps as rs


def snapshot(work, commit):
    (work / "snapshot").mkdir()
    archive = subprocess.run(["git", "-C", str(dc.ROOT), "archive", commit], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(work / "snapshot")], input=archive.stdout, check=True)
    return {"commit": commit, "archive_sha256": rs.digest_bytes(archive.stdout)}


def reference(work):
    out = {}
    for label, argv in {"validate": ["scripts/validate.py"],
                        "ecosystem": ["scripts/build_ecosystem.py", "--check"]}.items():
        out[label] = rs.run_script(work, argv, "reference-" + label)["stdout_first_line"]
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--base-commit", default="41d39b3")
    parser.add_argument("--no-model", action="store_true")
    args = parser.parse_args()
    work = args.work
    if not work.is_absolute() or work.exists():
        raise SystemExit("--work must name a new absolute directory")
    work.mkdir(mode=0o700, parents=True)
    os.umask(0o077)
    home, dags = work / "dagu-home", work / "dags"
    home.mkdir()
    dags.mkdir()
    if dc.DAGU.exists() and rs.digest(dc.DAGU) != dc.DAGU_2166_SHA256:
        raise SystemExit("Dagu binary is not the pinned 2.16.6 executable")
    snap = snapshot(work, args.base_commit)
    ref = reference(work)
    if not args.no_model:
        (work / "model-enabled").touch()
    config = work / "config.yaml"
    config.write_text(dc.PRIVATE_CONFIG, encoding="utf-8")  # fix round 1: scheduler.port 0 (no wildcard /health bind)
    now = datetime.now().astimezone()
    fire = (now + timedelta(seconds=45)).replace(second=0, microsecond=0) + timedelta(minutes=1)
    cron = f"{fire.minute} {fire.hour} * * *"
    steps = {a: shlex.join([sys.executable, "-B", str(dc.HERE / "real_steps.py"), a, str(work)])
             for a in ("checkpoint", "finalize")}
    workflow = dags / "realmaint.yaml"
    workflow.write_text("\n".join([
        "type: graph", "schedule: " + json.dumps(cron), "timeout_sec: 600", "max_active_runs: 1",
        "working_dir: " + json.dumps(str(work)),
        "env:", "  - GW2_REAL_HOME: " + json.dumps(str(Path.home())),
        "  - GW2_CODEX_PATH: " + json.dumps(dc.CODEX_BIN_DIR + ":/usr/bin:/bin"),
        "steps:", "  - id: checkpoint", "    run: " + json.dumps(steps["checkpoint"]),
        "  - id: finalize", "    depends: [checkpoint]", "    run: " + json.dumps(steps["finalize"]), ""]),
        encoding="utf-8")
    env = {"HOME": str(work), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "DAGU_HOME": str(home),
           "TMPDIR": str(work), "XDG_CONFIG_HOME": str(work / "xdg-config"),
           "XDG_CACHE_HOME": str(work / "xdg-cache"), "DO_NOT_TRACK": "1"}
    base = [str(dc.DAGU), "--context", "local", "--dagu-home", str(home), "--config", str(config)]
    rec = dc.Recorder(work, env)
    frozen = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "snapshot": snap, "reference": ref,
              "cron": cron, "planned_fire_local": fire.isoformat(),
              "inputs": {p.name: rs.digest(p) for p in [dc.HERE / "real_steps.py", dc.HERE / "dagu_common.py",
                                                         Path(__file__).resolve(), workflow, config]},
              "dagu_binary_sha256": rs.digest(dc.DAGU), "python_version": platform.python_version()}
    rs.exclusive(work / "freeze.json", frozen)
    version = rec.call("version", [str(dc.DAGU), "version"]).strip()
    rec.call("validate", base + ["validate", str(workflow)])
    timeline = []
    scheduler = None
    try:
        out, err = (work / "native" / "scheduler.stdout").open("x"), (work / "native" / "scheduler.stderr").open("x")
        scheduler = subprocess.Popen(base + ["scheduler", "--dags", str(dags)], cwd=work, env=env,
                                     stdout=out, stderr=err, start_new_session=True)
        timeline.append(("scheduler_started", datetime.now(timezone.utc).isoformat()))
        listener_samples = []

        def sampled_ready():
            if scheduler.poll() is None and (not listener_samples or time.monotonic() - listener_samples[-1]["t"] >= 5):
                tree = dc.descendants(scheduler.pid, include_self=True)
                listener_samples.append({"t": time.monotonic(), "at": datetime.now(timezone.utc).isoformat(),
                                         "scheduler_tree_pids": len(tree), "listeners": dc.listeners(tree)})
            return (work / "finalize-ready.json").exists() or scheduler.poll() is not None
        if not dc.wait_for(sampled_ready, 420):
            raise ValueError("Finalizer was not reached by the scheduled run")
        if scheduler.poll() is not None:
            raise ValueError("Scheduler exited early")
        timeline.append(("finalize_ready", datetime.now(timezone.utc).isoformat()))
        rows = dc.history_rows(rec.call("history-running", base + ["history", "realmaint", "--format", "json"]))
        if len(rows) != 1:
            raise ValueError(f"Expected one scheduled run, saw {len(rows)}")
        run_id, running_row = rows[0]["dagRunId"], rows[0]
        owned = dc.descendants(scheduler.pid, include_self=False)
        before = rs.verify_checkpoint(work)
        rec.call("stop", base + ["stop", "--run-id", run_id, str(workflow)])
        timeline.append(("stop_issued", datetime.now(timezone.utc).isoformat()))
        dc.wait_for(lambda: not dc.live(owned), 30)
        stopped = [r for r in dc.history_rows(rec.call("history-aborted", base + ["history", "--run-id", run_id, "--format", "json"])) if r.get("dagRunId") == run_id]
        owned_after_stop = len(dc.live(owned))
        if len(stopped) != 1 or stopped[0]["status"] != "aborted" or owned_after_stop:
            raise ValueError(f"Native aborted status and process retirement are required: {stopped} {owned_after_stop}")
        if (work / "completed.json").exists():
            raise ValueError("Completed effect exists before retry")
        (work / "release-finalize").touch(exist_ok=False)
        rec.call("retry", base + ["retry", "--run-id", run_id, "--step", "finalize", str(workflow)], timeout=240)
        timeline.append(("retry_returned", datetime.now(timezone.utc).isoformat()))
        succeeded = [r for r in dc.history_rows(rec.call("history-succeeded", base + ["history", "--run-id", run_id, "--format", "json"])) if r.get("dagRunId") == run_id]
        all_rows = dc.history_rows(rec.call("history-all", base + ["history", "realmaint", "--format", "json"]))
        completed = json.loads((work / "completed.json").read_text())
        checkpoint = json.loads((work / "checkpoint.json").read_text())
        finalizer = json.loads((work / "retry-ready.json").read_text())["pid"]
        checks = {
            "scheduler_created_run": len(rows) == 1,
            "before_retry_status_aborted": stopped[0]["status"] == "aborted",
            "after_retry_status_succeeded": len(succeeded) == 1 and succeeded[0]["status"] == "succeeded",
            "same_native_run_id": len(succeeded) == 1 and succeeded[0]["dagRunId"] == run_id,
            "single_run_in_history": len(all_rows) == 1,
            "checkpoint_unchanged": rs.verify_checkpoint(work) == before == completed["checkpoint_sha256"],
            "checkpoint_execution_count_one": checkpoint["execution_count"] == 1,
            "model_call_claim_single": args.no_model or json.loads((work / "model-call-claim.json").read_text()) == {"model_calls": 1},
            "model_verdict_pass": args.no_model or checkpoint["model"]["verdict"] == "PASS",
            "model_usage_present": args.no_model or bool(checkpoint["model"]["usage"]),
            "validate_equals_reference": checkpoint["validate"]["stdout_first_line"] == ref["validate"] == completed["validate"]["stdout_first_line"],
            "ecosystem_equals_reference": completed["ecosystem"]["stdout_first_line"] == ref["ecosystem"],
            "owned_processes_retired_after_stop": owned_after_stop == 0,
            "retry_finalizer_exited": finalizer not in dc.process_table(),
        }
        result = {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
                  "dagu_version": version, "platform": platform.system() + " " + platform.release(),
                  "run_id": run_id, "running_row": running_row, "aborted_row": stopped[0],
                  "succeeded_row": succeeded[0] if succeeded else None, "history_rows_total": len(all_rows),
                  "timeline_utc": timeline, "checkpoint": checkpoint, "completed": completed,
                  "command_exit_codes": rec.codes, "frozen": frozen}
    finally:
        dc.stop_group(scheduler)
    # Native per-attempt records: the first attempt's triggerType identifies who created the run
    # (integer enum; its mapping is verified against the pinned Dagu source separately).
    attempts = []
    for status_file in sorted(home.glob("data/dag-runs/realmaint/dag-runs/*/*/*/*/*/status.jsonl")):
        last = json.loads(status_file.read_text().splitlines()[-1])
        attempts.append({"attempt_dir": status_file.parent.name, "status": last.get("status"),
                         "triggerType": last.get("triggerType"), "dagRunId": last.get("dagRunId")})
    result["native_attempts"] = attempts
    log = (work / "native" / "scheduler.stderr").read_text()
    result["scheduler_isolation"] = {
        "private_config": dc.PRIVATE_CONFIG, "listener_probe_self_test": dc.listener_probe_self_test(),
        "health_server_disabled_logged": "Health check server disabled" in log,
        "health_server_started_logged": "Starting health check server" in log,
        "sample_count": len(listener_samples),
        "listener_rows_owned_by_scheduler_tree": sum(len(x["listeners"]) for x in listener_samples),
        "samples": [{k: v for k, v in x.items() if k != "t"} for x in listener_samples]}
    iso = result["scheduler_isolation"]
    iso["isolation_ok"] = (iso["health_server_disabled_logged"] and not iso["health_server_started_logged"]
                           and iso["sample_count"] > 0 and iso["listener_rows_owned_by_scheduler_tree"] == 0
                           and iso["listener_probe_self_test"]["detected"])
    result["scheduler_stopped"] = scheduler.poll() is not None
    result["owned_processes_remaining_after_scheduler_stop"] = len(dc.live(owned))
    rs.exclusive(work / "result.json", result)
    print(json.dumps({k: result[k] for k in ("status", "checks", "run_id", "history_rows_total")}, indent=2))


if __name__ == "__main__":
    main()
