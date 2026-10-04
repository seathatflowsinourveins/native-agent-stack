#!/usr/bin/env python3
"""Prometheus 3.14.0 -> 3.15.0 rehearsal on copies of the live TSDB, with the live unit untouched.

Usage: rehearse.py <tools-root> <live-config> <live-data-dir> <work-dir>

  R0  promtool check config / check rules on the live files with both promtool versions (read-only)
  R1  copy the live TSDB once (cp -a while the live server runs) and duplicate it for two arms
  R2  scratch config = live config with `alerting` removed and the self-scrape target moved to the arm's port
      (other targets are the live loopback exporters, scraped read-only; no alert is ever sent)
  R3  run 3.14.0 (arm A, 127.0.0.1:29190) and 3.15.0 (arm B, 127.0.0.1:29191) side by side; per arm: time to
      /-/ready, buildinfo, runtimeinfo, tsdb status, `up` by job/instance, rules health, target health, a
      historical query_range ending before the copy (both arms read identical blocks and WAL), SIGHUP reload
  R4  rollback: stop arm B cleanly, start 3.14.0 on the data 3.15.0 wrote (127.0.0.1:29192), check ready, the
      same historical query and the samples 3.15.0 wrote
  R5  scan every arm log for level=ERROR / level=WARN lines
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml  # PyYAML from the uv environment

tools, live_config, live_data, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
work.mkdir(parents=True, exist_ok=False)
BIN = {v: tools / f"ecosystem-prometheus-{v}" for v in ("3.14.0", "3.15.0")}
results: dict = {"steps": [], "arms": {}}


def log(step: str, **data) -> None:
    results["steps"].append({"step": step, **data})
    print(step, json.dumps(data, default=str)[:400], flush=True)


def run(argv, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in argv], capture_output=True, text=True, stdin=subprocess.DEVNULL, **kw)


def get(port: int, path: str, params: dict | None = None, timeout: float = 10):
    url = f"http://127.0.0.1:{port}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read()
        return response.status, body


def api(port: int, path: str, params: dict | None = None):
    status, body = get(port, path, params)
    return json.loads(body)


# R0 config and rules checks on the live files
rules_file = yaml.safe_load(live_config.read_text())["rule_files"][0]
for version, prefix in BIN.items():
    cfg = run([prefix / "promtool", "check", "config", live_config])
    rules = run([prefix / "promtool", "check", "rules", rules_file])
    (work / f"R0-check-config-{version}.out").write_text(cfg.stdout + cfg.stderr)
    (work / f"R0-check-rules-{version}.out").write_text(rules.stdout + rules.stderr)
    log(f"R0-promtool-{version}", check_config_exit=cfg.returncode, check_rules_exit=rules.returncode,
        check_config=(cfg.stdout + cfg.stderr).strip().replace(str(Path.home()), "~"),
        check_rules=(rules.stdout + rules.stderr).strip().replace(str(Path.home()), "~"))

# R1 copy the live TSDB
src = work / "tsdb-src"
copy_started = time.time()
shutil.copytree(live_data, src, symlinks=True, ignore=shutil.ignore_patterns("lock", "queries.active"))
copy_finished = time.time()
copy_bytes = sum(p.stat().st_size for p in src.rglob("*") if p.is_file())
arm_dirs = {"A": work / "tsdb-A", "B": work / "tsdb-B"}
for directory in arm_dirs.values():
    shutil.copytree(src, directory, symlinks=True)
log("R1-copy", copy_started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(copy_started)),
    copy_seconds=round(copy_finished - copy_started, 2), bytes=copy_bytes,
    blocks=sorted(p.name for p in src.iterdir() if p.is_dir() and p.name not in ("wal", "chunks_head")))

# R2 scratch configs
live = yaml.safe_load(live_config.read_text())
PORTS = {"A": 29190, "B": 29191, "B-rollback": 29192}


def scratch_config(port: int) -> Path:
    cfg = json.loads(json.dumps(live))
    cfg.pop("alerting", None)
    for job in cfg["scrape_configs"]:
        if job["job_name"] == "prometheus":
            job["static_configs"] = [{"targets": [f"127.0.0.1:{port}"]}]
    path = work / f"prometheus-{port}.yml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return path


def start(label: str, version: str, data: Path, port: int):
    cfg = scratch_config(port)
    log_path = work / f"arm-{label}.log"
    handle = open(log_path, "wb")
    argv = [BIN[version] / "prometheus", f"--config.file={cfg}", f"--storage.tsdb.path={data}",
            "--storage.tsdb.retention.time=7d", "--storage.tsdb.retention.size=512MB",
            f"--web.listen-address=127.0.0.1:{port}"]
    started = time.monotonic()
    proc = subprocess.Popen([str(a) for a in argv], stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            start_new_session=True)
    ready_s = None
    for _ in range(600):
        try:
            if get(port, "/-/ready", timeout=2)[0] == 200:
                ready_s = round(time.monotonic() - started, 2)
                break
        except Exception:
            pass
        if proc.poll() is not None:
            break
        time.sleep(0.25)
    return proc, handle, ready_s, log_path


def stop(proc, handle) -> int:
    proc.send_signal(signal.SIGTERM)
    try:
        code = proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = proc.wait()
    handle.close()
    return code


def snapshot(label: str, port: int, hist_end: float) -> dict:
    out = {}
    out["buildinfo"] = api(port, "/api/v1/status/buildinfo")["data"]
    runtime = api(port, "/api/v1/status/runtimeinfo")["data"]
    out["runtimeinfo"] = {k: runtime.get(k) for k in ("reloadConfigSuccess", "storageRetention", "lastConfigTime")}
    tsdb = api(port, "/api/v1/status/tsdb")["data"]
    out["tsdb_head"] = tsdb.get("headStats")
    up = api(port, "/api/v1/query", {"query": "up"})["data"]["result"]
    out["up"] = sorted((r["metric"]["job"], r["metric"]["instance"], r["value"][1]) for r in up)
    groups = api(port, "/api/v1/rules")["data"]["groups"]
    rules = [r for g in groups for r in g["rules"]]
    out["rules"] = {"groups": len(groups), "rules": len(rules), "health": sorted({r["health"] for r in rules}),
                    "names": sorted(r["name"] for r in rules)}
    targets = api(port, "/api/v1/targets")["data"]["activeTargets"]
    out["targets"] = sorted((t["labels"]["job"], t["health"]) for t in targets)
    hist = api(port, "/api/v1/query_range", {"query": "up", "start": f"{hist_end - 6 * 3600:.3f}",
                                             "end": f"{hist_end:.3f}", "step": "300"})["data"]["result"]
    canon = json.dumps(sorted(hist, key=lambda r: json.dumps(r["metric"], sort_keys=True)), sort_keys=True)
    out["historical_up_6h"] = {"series": len(hist), "samples": sum(len(r["values"]) for r in hist),
                               "sha256": hashlib.sha256(canon.encode()).hexdigest()}
    count = api(port, "/api/v1/query", {"query": 'count_over_time(up{job="vllm"}[1h])',
                                         "time": f"{hist_end:.3f}"})["data"]["result"]
    out["vllm_up_samples_1h_before_copy"] = [r["value"][1] for r in count]
    return out


# R3 side-by-side arms
hist_end = copy_started - 120  # two minutes before the copy began: identical data in both arms
procs = {}
for label, version in (("A", "3.14.0"), ("B", "3.15.0")):
    proc, handle, ready_s, log_path = start(label, version, arm_dirs[label], PORTS[label])
    procs[label] = (proc, handle, log_path)
    log(f"R3-start-{label}-{version}", ready_seconds=ready_s, port=PORTS[label])
time.sleep(75)  # five scrape and rule-evaluation intervals
for label in ("A", "B"):
    snap = snapshot(label, PORTS[label], hist_end)
    results["arms"][label] = snap
    log(f"R3-snapshot-{label}", version=snap["buildinfo"]["version"], up=snap["up"], rules=snap["rules"]["health"],
        rule_count=snap["rules"]["rules"], historical=snap["historical_up_6h"],
        vllm=snap["vllm_up_samples_1h_before_copy"], head=snap["tsdb_head"])
# SIGHUP reload on both
for label in ("A", "B"):
    before = api(PORTS[label], "/api/v1/status/runtimeinfo")["data"]["lastConfigTime"]
    os.kill(procs[label][0].pid, signal.SIGHUP)
    time.sleep(3)
    after = api(PORTS[label], "/api/v1/status/runtimeinfo")["data"]
    log(f"R3-reload-{label}", last_config_before=before, last_config_after=after["lastConfigTime"],
        reload_success=after["reloadConfigSuccess"])
a, b = results["arms"]["A"], results["arms"]["B"]
comparison = {
    "up_jobs_instances_equal": [x[:2] for x in a["up"]] == [x[:2] for x in b["up"]],
    "up_values_equal": a["up"] == b["up"],
    "rules_equal": a["rules"] == b["rules"],
    "targets_equal": a["targets"] == b["targets"],
    "historical_equal": a["historical_up_6h"] == b["historical_up_6h"],
    "vllm_count_equal": a["vllm_up_samples_1h_before_copy"] == b["vllm_up_samples_1h_before_copy"],
}
log("R3-compare", **comparison)

# R4 rollback: 3.14.0 on the data 3.15.0 wrote
stop_a = stop(*procs["A"][:2])
b_stop_utc = time.time()
stop_b = stop(*procs["B"][:2])
log("R4-stop", arm_A_exit=stop_a, arm_B_exit=stop_b)
proc, handle, ready_s, log_path = start("B-rollback", "3.14.0", arm_dirs["B"], PORTS["B-rollback"])
log("R4-rollback-start", ready_seconds=ready_s, port=PORTS["B-rollback"])
time.sleep(20)
snap = snapshot("B-rollback", PORTS["B-rollback"], hist_end)
written = api(PORTS["B-rollback"], "/api/v1/query",
              {"query": 'count_over_time(up{instance="127.0.0.1:29191"}[10m])', "time": f"{b_stop_utc:.3f}"})
written_by_b = [r["value"][1] for r in written["data"]["result"]]
results["arms"]["B-rollback"] = snap
log("R4-rollback-snapshot", version=snap["buildinfo"]["version"], historical=snap["historical_up_6h"],
    historical_equal_to_B=snap["historical_up_6h"] == b["historical_up_6h"],
    self_samples_written_by_3150=written_by_b, up=snap["up"], rules=snap["rules"]["health"])
stop_r = stop(proc, handle)
log("R4-rollback-stop", exit=stop_r)

# R5 log scan
for label in ("A", "B", "B-rollback"):
    text = (work / f"arm-{label}.log").read_text(errors="replace")
    lines = text.splitlines()
    errors = [l for l in lines if "level=ERROR" in l]
    warns = [l for l in lines if "level=WARN" in l]
    log(f"R5-log-{label}", lines=len(lines), errors=len(errors), warnings=len(warns),
        error_samples=[e[:300] for e in errors[:5]], warning_samples=[w[:300] for w in warns[:8]])

(work / "rehearsal.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
print("DONE")
