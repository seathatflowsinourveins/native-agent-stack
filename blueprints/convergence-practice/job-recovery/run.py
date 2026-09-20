#!/usr/bin/env python3
"""Run the frozen no-model recovery fixture in a NEW private task directory."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid

import fixture

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def process_table():
    result = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,lstart="],
                            capture_output=True, text=True, check=True)
    return {int(parts[0]): (int(parts[1]), " ".join(parts[2:]))
            for line in result.stdout.splitlines() if len(parts := line.split()) >= 7}


def descendants(pid):
    table, found = process_table(), {pid}
    while True:
        more = {child for child, (parent, _) in table.items() if parent in found}
        if more <= found:
            return {child: table[child][1] for child in found if child in table}
        found |= more


def live(identities):
    current = process_table()
    return [pid for pid, started in identities.items() if pid in current and current[pid][1] == started]


def history_row(stdout, run_id):
    value = json.loads(stdout)
    rows = value if isinstance(value, list) else value.get("runs", [])
    rows = [row for row in rows if row.get("dagRunId") == run_id]
    if len(rows) != 1:
        raise ValueError("Expected exactly one native history row for the run")
    return rows[0]


def run(dagu, work):
    # Refuse reuse, including dangling symlinks. No global state is loaded.
    if not work.is_absolute() or work.exists() or work.is_symlink():
        raise ValueError("--work must name a new absolute private directory")
    if any(parent.is_symlink() for parent in work.parents):
        raise ValueError("Symlink ancestors are not allowed")
    dagu = dagu.resolve(strict=True)
    work.mkdir(mode=0o700)
    os.umask(0o077)
    home = work / "dagu-home"
    home.mkdir()
    (work / "source").mkdir()
    for name, source in {
        "planner.py": ROOT / "blueprints/convergence-practice/native-worker/accepted/planner.py",
        "test_planner.py": ROOT / "blueprints/convergence-practice/native-worker/seed/test_planner.py",
    }.items():
        shutil.copyfile(source, work / "source" / name)
    fixture.exclusive(work / "expected.json", fixture.source_hashes(work))
    shutil.copyfile(HERE / "fixture.py", work / "fixture.py")
    config = work / "config.yaml"
    config.write_text("check_updates: false\n", encoding="utf-8")
    workflow = work / "recovery.yaml"
    commands = {action: shlex.join([sys.executable, "-B", str(work / "fixture.py"), action, str(work)])
                for action in ("checkpoint", "finalize")}
    workflow.write_text("\n".join([
        "type: graph", "timeout_sec: 90", "max_active_runs: 1",
        "working_dir: " + json.dumps(str(work)), "steps:", "  - id: checkpoint",
        "    run: " + json.dumps(commands["checkpoint"]), "  - id: finalize",
        "    depends: [checkpoint]", "    run: " + json.dumps(commands["finalize"]), ""]), encoding="utf-8")
    env = {"HOME": str(work), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "DAGU_HOME": str(home),
           "TMPDIR": str(work), "XDG_CONFIG_HOME": str(work / "xdg-config"),
           "XDG_CACHE_HOME": str(work / "xdg-cache"), "DO_NOT_TRACK": "1"}
    run_id = "recovery-" + uuid.uuid4().hex
    base = [str(dagu), "--context", "local", "--dagu-home", str(home), "--config", str(config)]
    frozen = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(),
              "repository_inputs": {str(path.relative_to(ROOT)): fixture.digest(path) for path in
                                    [HERE / "plan.json", HERE / "run.py", HERE / "fixture.py",
                                     ROOT / "blueprints/convergence-practice/native-worker/accepted/planner.py",
                                     ROOT / "blueprints/convergence-practice/native-worker/seed/test_planner.py"]},
              "private_inputs": {path.name: fixture.digest(path) for path in
                                 [config, workflow, work / "expected.json", work / "fixture.py"]},
              "dagu_binary_sha256": fixture.digest(dagu), "python_version": platform.python_version()}
    fixture.exclusive(work / "freeze.json", frozen)
    codes = {}

    def call(label, argv):
        child = subprocess.Popen(argv, cwd=work, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = child.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGTERM)
            try:
                stdout, stderr = child.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                stdout, stderr = child.communicate(timeout=5)
        (work / (label + ".stdout")).write_text(stdout)
        (work / (label + ".stderr")).write_text(stderr)
        codes[label] = child.returncode
        if child.returncode or timed_out:
            raise ValueError(f"Native command failed: {label}; private evidence retained")
        return stdout

    version = call("version", [str(dagu), "version"]).strip()
    if "2.16.6" not in version.split():
        raise ValueError("This frozen fixture requires Dagu 2.16.6")
    call("validate", base + ["validate", str(workflow)])
    owned = {}
    process = None
    try:
        with (work / "start.stdout").open("x") as out, (work / "start.stderr").open("x") as err:
            process = subprocess.Popen(base + ["start", "--run-id", run_id, str(workflow)],
                                       cwd=work, env=env, stdout=out, stderr=err, start_new_session=True)
            deadline = time.monotonic() + 30
            while not (work / "finalize-ready.json").exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise ValueError("Finalizer was not reached; private evidence retained")
                time.sleep(0.05)
            owned.update(descendants(process.pid))
            before = fixture.verify_checkpoint(work)
            call("stop", base + ["stop", "--run-id", run_id, str(workflow)])
            codes["start"] = process.wait(timeout=30)
        stopped = history_row(call("history-aborted", base + ["history", "--run-id", run_id, "--format", "json"]), run_id)
        if stopped["status"] != "aborted" or live(owned):
            raise ValueError("Native aborted status and process retirement are required")
        # An input signal releases ONLY the selected final step; source is unchanged.
        (work / "release-finalize").touch(exist_ok=False)
        call("retry", base + ["retry", "--run-id", run_id, "--step", "finalize", str(workflow)])
        succeeded = history_row(call("history-succeeded", base + ["history", "--run-id", run_id, "--format", "json"]), run_id)
        finalizer = json.loads((work / "retry-ready.json").read_text())["pid"]
        if succeeded["status"] != "succeeded" or finalizer in process_table():
            raise ValueError("Native success and finalizer retirement are required")
        completed = json.loads((work / "completed.json").read_text())
        if fixture.verify_checkpoint(work) != before or completed != {"checkpoint_sha256": before, "tests": 12, "execution_count": 1}:
            raise ValueError("Checkpoint reuse acceptance failed")
        if any(fixture.digest(ROOT / path) != sha for path, sha in frozen["repository_inputs"].items()):
            raise ValueError("Frozen repository input changed during execution")
        result = {"status": "passed", "platform": platform.system() + " " + platform.release(),
                  "architecture": platform.machine(), "dagu_version": "2.16.6", "python_version": platform.python_version(),
                  "completed_at_utc": datetime.now(timezone.utc).isoformat(), "command_exit_codes": codes,
                  "before_retry_status": stopped["status"], "after_retry_status": succeeded["status"],
                  "same_native_run_id": stopped["dagRunId"] == succeeded["dagRunId"],
                  "checkpoint_execution_count": 1, "checkpoint_sha256_unchanged": before,
                  "checkpoint_tests": 12, "final_tests": 12, "observed_owned_processes_remaining": len(live(owned)),
                  "retry_finalizer_remaining": False, "model_calls": 0,
                  "frozen_inputs": frozen, "retained_native_outputs": {
                      p.name: fixture.digest(p) for p in sorted(work.glob("*.stdout")) + sorted(work.glob("*.stderr"))}}
        fixture.exclusive(work / "result.json", result)
        return result
    finally:
        # Failure cleanup is limited to this still-owned process group, never global jobs.
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dagu", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.dagu, args.work), indent=2))
