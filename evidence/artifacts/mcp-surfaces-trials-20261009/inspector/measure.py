"""Measure vendor clients; this script supplies no MCP implementation or adapter.

Only numeric status counters, tool-schema digests, timings, and process PSS are
retained. The shared MCP server, daemon tokens, and credential stores are never
read. Vendor private daemon namespaces are required by the invoking command.
"""

import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time


PREFIX = Path(os.environ.get("TRIAL_ROOT", "~/.local/state/native-agent-stack/research/api-surfaces-trials/inspector")).expanduser()
OUT = Path(__file__).parent
MCPDO = PREFIX / "install/bin/mcpdo"
MCPORTER = os.environ.get("MCPORTER_BIN", "mcporter")
EXPECTED_ENV = {
    "MCP_INSPECTOR_DAEMON_DIR": str(PREFIX / "d"),
    "MCPORTER_DAEMON_DIR": str(PREFIX / "m"),
    "MCP_STORAGE_DIR": str(PREFIX / "s"),
}
for key, expected in EXPECTED_ENV.items():
    if os.environ.get(key) != expected:
        raise SystemExit(f"Missing lane-owned namespace: {key}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def descendants(root):
    """Read process metadata only, never cmdline or environ."""
    parents = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            tail = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            parents[int(entry.name)] = int(tail[1])
        except (OSError, ValueError, IndexError):
            continue
    found = {root}
    pending = [root]
    while pending:
        parent = pending.pop()
        children = {pid for pid, ppid in parents.items() if ppid == parent}
        children -= found
        found.update(children)
        pending.extend(children)
    return found


def pss(pids):
    total = 0
    measured = []
    for pid in sorted(pids):
        try:
            lines = Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines()
            value = next(int(line.split()[1]) for line in lines if line.startswith("Pss:"))
            total += value
            measured.append({"pid": pid, "pss_kib": value})
        except (OSError, StopIteration, ValueError):
            continue
    return {"total_kib": total, "processes": measured}


def invoke(argv, daemon_pid=None):
    start = time.monotonic_ns()
    proc = subprocess.Popen([str(arg) for arg in argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    samples = []
    stop_sampling = threading.Event()

    def sample_processes():
        while not stop_sampling.is_set():
            pids = descendants(proc.pid)
            if daemon_pid is not None:
                pids |= descendants(daemon_pid)
            sample = pss(pids)
            if sample["processes"]:
                samples.append(sample)
            stop_sampling.wait(0.025)

    sampler = threading.Thread(target=sample_processes, daemon=True)
    sampler.start()
    try:
        stdout, stderr = proc.communicate(timeout=40)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate(timeout=5)
        raise RuntimeError("Native client exceeded 40-second trial bound")
    finally:
        stop_sampling.set()
        sampler.join(timeout=5)
    elapsed_ms = (time.monotonic_ns() - start) / 1_000_000
    record = {
        "argv": [str(arg) for arg in argv],
        "rc": proc.returncode,
        "elapsed_ms": round(elapsed_ms, 3),
        "stdout_sha256": digest(stdout),
        "stdout_bytes": len(stdout),
        "stderr_sha256": digest(stderr),
        "stderr_bytes": len(stderr),
        "peak_client_plus_daemon_pss_kib": max((s["total_kib"] for s in samples), default=0),
        "pss_sample_count": len(samples),
    }
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = None
    if proc.returncode != 0:
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            record["error_code"] = data["error"].get("code")
        raise RuntimeError("Native client failed: " + json.dumps(record))
    return record, data


def inspector(*args):
    return [MCPDO, "--format", "json", *args]


def mcporter(*args):
    return [MCPORTER, "--config", PREFIX / "mcporter.json", *args]


def daemon_status(arm):
    argv = inspector("daemon", "status") if arm == "inspector" else mcporter("daemon", "status", "--json")
    rec, value = invoke(argv)
    # mcporter emits the JSON literal null when no daemon is running.
    if value is None and arm == "mcporter":
        value = {"running": False, "pid": None}
    if not isinstance(value, dict):
        raise RuntimeError("Native daemon status is not an object")
    return rec, value


def daemon_pid(value):
    if isinstance(value.get("pid"), int):
        return value["pid"]
    return None


def normalized(task, data):
    if task == "tools/list":
        if not isinstance(data, dict) or not isinstance(data.get("tools"), list):
            raise RuntimeError("Missing native tool discovery result")
        selected = [{"name": t["name"], "inputSchema": t["inputSchema"]} for t in data["tools"]]
        selected.sort(key=lambda item: item["name"])
        return {"tool_count": len(selected), "name_input_schema_sha256": digest(canonical(selected))}
    if not isinstance(data, dict):
        raise RuntimeError("Missing native tool-call result")
    if "content" in data:
        if data.get("isError"):
            raise RuntimeError("Tool returned MCP isError")
        texts = [part["text"] for part in data["content"] if part.get("type") == "text"]
        if len(texts) != 1:
            raise RuntimeError("Expected one status text result")
        data = json.loads(texts[0])
    counts = data.get("counts")
    if not isinstance(counts, dict) or not all(isinstance(v, (int, float)) for v in counts.values()):
        raise RuntimeError("Status counters are not numeric")
    return {"counts": counts, "counts_sha256": digest(canonical(counts))}


def command(arm, task):
    if arm == "inspector":
        if task == "tools/list":
            return inspector("--connection", "trial-ai-memory", "tools/list")
        return inspector("--connection", "trial-ai-memory", "tools/call", "memory_status", "{}")
    if task == "tools/list":
        return mcporter("list", "trial-ai-memory", "--schema", "--json")
    return mcporter("call", "trial-ai-memory.memory_status", "--args", "{}", "--output", "json")


def stop(arm):
    argv = inspector("daemon", "stop") if arm == "inspector" else mcporter("daemon", "stop")
    record, _ = invoke(argv)
    return record


rows = []
result = {
    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "endpoint": "http://127.0.0.1:29374/mcp",
    "inspector": "2.10.1",
    "mcporter": "0.14.2",
    "inspector_protocol_era": "legacy",
    "tasks": ["tools/list", "tools/call memory_status {}"],
    "pss_source": "/proc/<pid>/smaps_rollup Pss (KiB)",
    "pss_scope": "Native CLI process tree plus this arm's private persistent daemon; shared server excluded",
    "sample_period_seconds": 0.025,
    "timing_limit": "CLI latency includes polling and PSS sampling overhead, identical in both arms",
    "cleanup": [],
}
try:
    for arm in ("inspector", "mcporter"):
        result["cleanup"].append({"phase": "before", "arm": arm, **stop(arm)})
    for arm in ("inspector", "mcporter"):
        stages = []
        if arm == "inspector":
            rec, _ = invoke(inspector("--config", str(PREFIX / "mcpdo.json"), "connect", "trial-ai-memory"))
            stages.append(rec)
        rec, value = invoke(command(arm, "tools/list"))
        stages.append(rec)
        rows.append({"phase": "cold", "arm": arm, "task": "tools/list", "stages": stages,
                     "elapsed_ms": round(sum(stage["elapsed_ms"] for stage in stages), 3),
                     "normalized": normalized("tools/list", value)})
    daemon_pids = {}
    result["persistent_pss"] = {}
    for arm in ("inspector", "mcporter"):
        _, value = daemon_status(arm)
        pid = daemon_pid(value)
        if pid is None:
            raise RuntimeError(f"No private daemon PID for {arm}")
        daemon_pids[arm] = pid
        result["persistent_pss"][arm] = pss(descendants(pid))
    for repetition in range(10):
        order = ("inspector", "mcporter") if repetition % 2 == 0 else ("mcporter", "inspector")
        for task in ("tools/list", "memory_status"):
            for arm in order:
                rec, value = invoke(command(arm, task), daemon_pids[arm])
                rows.append({"phase": "warm", "repetition": repetition, "arm": arm, "task": task,
                             **rec, "normalized": normalized(task, value)})
    for arm, pid in daemon_pids.items():
        result["persistent_pss"][arm + "_after"] = pss(descendants(pid))
    result["rows"] = rows
    result["paired"] = []
    for repetition in range(10):
        for task in ("tools/list", "memory_status"):
            pair = [r for r in rows if r.get("repetition") == repetition and r["task"] == task]
            result["paired"].append({"repetition": repetition, "task": task,
                                     "same_normalized_result": pair[0]["normalized"] == pair[1]["normalized"]})
    result["summary"] = {}
    for arm in ("inspector", "mcporter"):
        for task in ("tools/list", "memory_status"):
            selected = [r for r in rows if r["phase"] == "warm" and r["arm"] == arm and r["task"] == task]
            times = [r["elapsed_ms"] for r in selected]
            peaks = [r["peak_client_plus_daemon_pss_kib"] for r in selected]
            result["summary"][arm + ":" + task] = {
                "n": len(times), "latency_median_ms": round(statistics.median(times), 3),
                "latency_min_ms": min(times), "latency_max_ms": max(times),
                "pss_peak_median_kib": statistics.median(peaks), "pss_peak_max_kib": max(peaks),
            }
finally:
    for arm in ("inspector", "mcporter"):
        record = stop(arm)
        status_record, value = daemon_status(arm)
        pid = daemon_pid(value)
        alive = pid is not None and Path(f"/proc/{pid}").exists()
        result["cleanup"].append({"phase": "after", "arm": arm, "stop_rc": record["rc"],
                                  "status_rc": status_record["rc"], "daemon_alive": alive})
    (OUT / "measurements.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"summary": result.get("summary"), "pairs": len(result.get("paired", [])),
                  "matching_pairs": sum(p["same_normalized_result"] for p in result.get("paired", [])),
                  "persistent_pss": result.get("persistent_pss"),
                  "cleanup_verified": all(not r.get("daemon_alive", False) for r in result["cleanup"] if r["phase"] == "after")}))
