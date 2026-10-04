"""Real-qmd check: SIGTERM while a real `qmd pull` runs (Arm B setup). The scratch model cache is
hardlinked from an earlier run home, so qmd only compares ETags over HTTPS and loads no model.
Usage: realqmd_pull.py <worktree> <out-dir> <python> <cached-home>"""
import datetime, json, os, pathlib, shutil, signal, subprocess, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
WT, OUT, PY, CACHED = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3], pathlib.Path(sys.argv[4])
RUN = WT / "blueprints/retrieval-quality-v2/run.py"
shutil.rmtree(OUT, ignore_errors=True)
home = OUT / "pull-home"
models = home / ".cache/qmd/models"
models.mkdir(parents=True)
for f in (CACHED / ".cache/qmd/models").iterdir():
    os.link(f, models / f.name)
import realqmd_lib as lib
rid = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
index_name = "rqv2-sigterm-pull-check"
argv = [PY, str(RUN), "--repo", str(WT), "--scratch-home", str(home), "--output-dir", str(OUT / "pull-out"),
        "--run-id", rid, "--index-name", index_name, "--skip-native-bench"]
child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
seen, seen_at = [], None
deadline = time.monotonic() + 600
while time.monotonic() < deadline and child.poll() is None:
    pids = [p for p in lib.qmd_processes(index_name) if b"pull" in lib.argv_of(p)]
    if pids:
        seen, seen_at = pids, time.monotonic()
        time.sleep(0.3)  # let the runner settle into its poll loop around this call
        seen = sorted(set(seen) | set(p for p in lib.qmd_processes(index_name) if b"pull" in lib.argv_of(p)))
        os.kill(child.pid, signal.SIGTERM)
        break
    time.sleep(0.01)
out, err = child.communicate(timeout=300)
time.sleep(1.0)
proc = subprocess.CompletedProcess(argv, child.returncode, out, err)
check = lib.summary(OUT, WT, OUT / "pull-out", rid, proc)
check["model_cache"] = "hardlinked from the 2026-09-26 restart's scratch HOME (3 GGUF files and their .etag files)"
check["qmd_pull_pids_seen_before_signal"] = len(seen)
check["qmd_processes_for_index_after_run"] = len(lib.qmd_processes(index_name))
check["seen_pids_alive_after_run"] = sum(1 for p in seen if lib.alive(p))
print(json.dumps(check, indent=2))
(OUT / "checks.json").write_text(json.dumps(check, indent=2) + "\n")
