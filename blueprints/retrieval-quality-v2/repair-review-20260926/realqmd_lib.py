import hashlib, json, os, pathlib

def argv_of(pid):
    try:
        return (pathlib.Path(f"/proc/{pid}/cmdline")).read_bytes().split(b"\0")
    except OSError:
        return []

def qmd_processes(marker):
    found = []
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        argv = argv_of(entry.name)
        if marker.encode() in argv and any(a.endswith(b"qmd") or a.endswith(b"qmd.js") for a in argv):
            found.append(int(entry.name))
    return found

def alive(pid):
    stat = pathlib.Path(f"/proc/{pid}/stat")
    try:
        return stat.read_text().split(")")[-1].split()[0] != "Z"
    except OSError:
        return False

def summary(out_root, wt, out_dir, rid, proc):
    def sanitize(text):
        return str(text).replace(str(out_root), "<CHECK>").replace(str(wt), "<STACK_REPO>").replace(str(pathlib.Path.home()), "~")
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
        "index_documents_verified": (results["index"].get("content_verification") or {}).get("documents_verified"),
        "arm_a_status": results["arm_a"]["status"],
        "arm_a_mean_ndcg_at_10": (results["arm_a"]["summary"] or {}).get("mean_ndcg_at_10"),
        "arm_b_status": results["arm_b"]["status"],
        "arm_b_model_provenance_recorded": results["arm_b"]["model_provenance"] is not None,
        "native_bench_status": results["native_bench"]["status"],
        "interruption": results["interruption"],
        "signals_received": results["signals_received"],
        "abort_reason": results.get("abort_reason"),
        "native_records": len(native["records"]),
        "last_native_record": {k: last[k] for k in ("id", "exit_code", "timed_out", "interrupted_by",
                                                    "process_group_killed", "output_complete", "elapsed_ms",
                                                    "stdout_raw_bytes", "stderr_raw_bytes")},
    }
