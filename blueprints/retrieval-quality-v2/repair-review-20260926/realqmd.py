"""Two real-qmd checks of the committed run.py (Arm A only; no model is loaded).

decoy:   INDEX_PATH/QMD_CONFIG_DIR point at a decoy "host" directory; the run must never create it.
sigterm: SIGTERM reaches the runner while a real `qmd search` runs; the run must record the stop,
         kill that qmd's process group, write every output and end by SIGTERM.
Usage: realqmd.py <worktree> <out-dir> <python>
"""
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time

WT = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
PY = sys.argv[3]
RUN = WT / "blueprints/retrieval-quality-v2/run.py"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)


def run_id(offset=0):
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=offset)).strftime("%Y%m%dT%H%M%SZ")


def sanitize(text):
    return str(text).replace(str(OUT), "<CHECK>").replace(str(WT), "<STACK_REPO>").replace(str(pathlib.Path.home()), "~")


def qmd_processes(marker):
    found = []
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if any(marker.encode() == a for a in argv) and any(a.endswith(b"qmd") or a.endswith(b"qmd.js") for a in argv):
            found.append(int(entry.name))
    return found


def summary(out_dir, rid, proc):
    results = json.loads((out_dir / f"results-{rid}.json").read_text())
    native = json.loads((out_dir / f"native-{rid}.json").read_text())
    last = native["records"][-1]
    return {
        "run_id": rid,
        "argv": [sanitize(a) for a in proc.args],
        "exit_status": proc.returncode,
        "stdout_first_line": proc.stdout.splitlines()[0] if proc.stdout else "",
        "stderr_tail": sanitize(proc.stderr.strip()[-300:]),
        "results_sha256": hashlib.sha256((out_dir / f"results-{rid}.json").read_bytes()).hexdigest(),
        "native_sha256": hashlib.sha256((out_dir / f"native-{rid}.json").read_bytes()).hexdigest(),
        "report_exists": (out_dir / f"report-{rid}.md").is_file(),
        "status": results["status"],
        "harness_sha256": results["harness"]["sha256"],
        "qmd_version_raw": results["qmd_version_raw"],
        "caller_qmd_variables_not_inherited": results["environment"]["qmd_env"]["caller_qmd_variables_not_inherited"],
        "index_documents_verified": (results["index"].get("content_verification") or {}).get("documents_verified"),
        "arm_a_status": results["arm_a"]["status"],
        "arm_a_scored_queries": len(results["arm_a"]["per_query"]),
        "arm_a_mean_ndcg_at_10": (results["arm_a"]["summary"] or {}).get("mean_ndcg_at_10"),
        "arm_b_status": results["arm_b"]["status"],
        "native_bench_status": results["native_bench"]["status"],
        "interruption": results["interruption"],
        "signals_received": results["signals_received"],
        "abort_reason": results.get("abort_reason"),
        "native_records": len(native["records"]),
        "last_native_record": {k: last[k] for k in ("id", "exit_code", "timed_out", "interrupted_by",
                                                    "process_group_killed", "output_complete", "elapsed_ms",
                                                    "stdout_raw_bytes", "stderr_raw_bytes")},
    }


checks = {}

# 1. Decoy routing variables.
decoy = OUT / "decoy-host"
rid = run_id()
env = dict(os.environ, INDEX_PATH=str(decoy / "host.sqlite"), QMD_CONFIG_DIR=str(decoy / "config"))
proc = subprocess.run([PY, str(RUN), "--repo", str(WT), "--scratch-home", str(OUT / "decoy-home"),
                       "--output-dir", str(OUT / "decoy-out"), "--run-id", rid, "--skip-arm-b", "--skip-native-bench"],
                      env=env, capture_output=True, text=True, timeout=900)
checks["decoy"] = summary(OUT / "decoy-out", rid, proc)
checks["decoy"]["caller_set"] = ["INDEX_PATH=<CHECK>/decoy-host/host.sqlite", "QMD_CONFIG_DIR=<CHECK>/decoy-host/config"]
checks["decoy"]["decoy_directory_exists_after_run"] = decoy.exists()

# 2. SIGTERM while a real qmd search runs.
time.sleep(1.1)
rid = run_id()
index_name = "rqv2-sigterm-check"
argv = [PY, str(RUN), "--repo", str(WT), "--scratch-home", str(OUT / "sigterm-home"), "--output-dir",
        str(OUT / "sigterm-out"), "--run-id", rid, "--index-name", index_name, "--skip-arm-b", "--skip-native-bench"]
child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
seen = []
deadline = time.monotonic() + 300
while time.monotonic() < deadline and child.poll() is None:
    pids = [p for p in qmd_processes(index_name)
            if b"search" in pathlib.Path(f"/proc/{p}/cmdline").read_bytes().split(b"\0")]
    if pids:
        seen = pids
        os.kill(child.pid, signal.SIGTERM)
        break
    time.sleep(0.01)
out, err = child.communicate(timeout=300)
proc = subprocess.CompletedProcess(argv, child.returncode, out, err)
time.sleep(1.0)
checks["sigterm"] = summary(OUT / "sigterm-out", rid, proc)
checks["sigterm"]["qmd_search_pids_seen_before_signal"] = len(seen)
checks["sigterm"]["qmd_processes_for_index_after_run"] = len(qmd_processes(index_name))
checks["sigterm"]["seen_pids_alive_after_run"] = sum(1 for p in seen if pathlib.Path(f"/proc/{p}").exists()
                                                    and pathlib.Path(f"/proc/{p}/stat").read_text().split(")")[-1].split()[0] != "Z")
print(json.dumps(checks, indent=2))
(OUT / "checks.json").write_text(json.dumps(checks, indent=2) + "\n")
