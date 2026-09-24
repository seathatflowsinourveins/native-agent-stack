"""Disposable-DAGU_HOME harness for the wave-2 Dagu checks (gaps 3 and 7).

Scenarios (each selectable with --scenario, all run with the given binary):
  hosting  - the hosting receipt's checks: exit-23 failure fixture (status
             failed, dependent aborted, CLI exit), `dagu stop` cancellation
             (status aborted, stop and cancelled-CLI exits), and history
             preserved across a `dagu server` restart (CLI history plus the
             server's /api/v1/dags API, before and after the restart).
  kill     - two-step kill-mid-step DAG: SIGKILL the executing `dagu start`
             process group while step1 sleeps, record history immediately,
             `dagu retry` after >30 s and >90 s (lock and heartbeat stale
             thresholds), then start an isolated `dagu scheduler` and poll the
             run's status for up to --scheduler-wait seconds, retrying once the
             status leaves 'running' (or at the end). Scrapes the server's
             Prometheus metrics endpoint as Dagu's telemetry surface.

Nothing outside --work is written except Dagu's own abstract/tmp unix sockets.
Every process started here runs in its own session and is killed at the end.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

T0 = time.monotonic()


def now():
    return round(time.monotonic() - T0, 1)


class Home:
    def __init__(self, dagu, work: Path, port: int, sched_port: int):
        self.dagu = dagu
        self.home = work / "dagu-home"
        self.dags = self.home / "dags"
        self.marks = work / "marks"
        for d in (self.dags, self.marks):
            d.mkdir(parents=True, exist_ok=True)
        self.port = port
        (self.home / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {port}\ncheck_updates: false\nmetrics: private\n"
            f"auth:\n  mode: none\npermissions:\n  write_dags: false\n  run_dags: false\n"
            f"scheduler:\n  port: {sched_port}\n")
        self.env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin", "DAGU_HOME": str(self.home),
                    "MARKS": str(self.marks)}
        self.log = []
        self.procs = []

    def run(self, *args, timeout=120):
        cmd = [self.dagu, *args]
        p = subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=timeout)
        rec = {"t": now(), "cmd": "dagu " + " ".join(args), "exit": p.returncode,
               "stdout_tail": p.stdout[-600:], "stderr_tail": p.stderr[-600:]}
        self.log.append(rec)
        return rec

    def spawn(self, *args, logname):
        out = open(self.home / f"{logname}.log", "w")
        p = subprocess.Popen([self.dagu, *args], env=self.env, stdout=out, stderr=subprocess.STDOUT,
                             start_new_session=True)
        self.procs.append(p)
        self.log.append({"t": now(), "spawn": "dagu " + " ".join(args), "pid": p.pid})
        return p

    def history(self, dag):
        p = subprocess.run([self.dagu, "history", "--dagu-home", str(self.home), "--format", "json", dag],
                           env=self.env, capture_output=True, text=True, timeout=60)
        try:
            rows = json.loads(p.stdout)
        except Exception:
            rows = None
        self.log.append({"t": now(), "cmd": f"dagu history --format json {dag}", "exit": p.returncode,
                         "rows": [{k: r.get(k) for k in ("dagRunId", "status", "startedAt", "finishedAt", "duration")}
                                  for r in (rows if isinstance(rows, list) else [])],
                         "stderr_tail": p.stderr[-300:]})
        return rows if isinstance(rows, list) else None

    def dag(self, name, body):
        path = self.dags / f"{name}.yaml"
        path.write_text(body)
        return path

    def http(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
                return r.status, r.read().decode()
        except Exception as exc:  # connection refused etc.
            return None, type(exc).__name__

    def wait_http(self, up=True, secs=30):
        for _ in range(secs * 2):
            status, _ = self.http("/api/v1/dags")
            if (status == 200) == up:
                return True
            time.sleep(0.5)
        return False

    def cleanup(self):
        for p in self.procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.wait(timeout=10)


def run_status(rows, run_id):
    for r in rows or []:
        if r.get("dagRunId") == run_id:
            return r.get("status")
    return None


def hosting(h: Home, tag: str):
    res = {}
    h.dag(f"{tag}-failure", "type: graph\nsteps:\n  - id: fail\n    run: exit 23\n  - id: after\n    run: echo after\n    depends: [fail]\n")
    rec = h.run("start", "--dagu-home", str(h.home), "--run-id", f"{tag}-failure-1", str(h.dags / f"{tag}-failure.yaml"))
    st = h.run("status", "--dagu-home", str(h.home), "--run-id", f"{tag}-failure-1", f"{tag}-failure")
    res["failure_fixture"] = {"requested_step_exit": 23, "cli_exit": rec["exit"],
                              "status": run_status(h.history(f"{tag}-failure"), f"{tag}-failure-1"),
                              "status_cmd_stdout": st["stdout_tail"]}
    h.dag(f"{tag}-cancel", "type: graph\nsteps:\n  - id: long\n    run: sleep 60\n  - id: after\n    run: echo after\n    depends: [long]\n")
    p = h.spawn("start", "--dagu-home", str(h.home), "--run-id", f"{tag}-cancel-1", str(h.dags / f"{tag}-cancel.yaml"),
                logname="cancel-start")
    for _ in range(40):
        if run_status(h.history(f"{tag}-cancel"), f"{tag}-cancel-1") == "running":
            break
        time.sleep(0.5)
    stop = h.run("stop", "--dagu-home", str(h.home), "--run-id", f"{tag}-cancel-1", f"{tag}-cancel")
    try:
        cancelled_exit = p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        cancelled_exit = "timeout"
    st = h.run("status", "--dagu-home", str(h.home), "--run-id", f"{tag}-cancel-1", f"{tag}-cancel")
    res["cancellation_fixture"] = {"stop_exit": stop["exit"], "cancelled_cli_exit": cancelled_exit,
                                   "status": run_status(h.history(f"{tag}-cancel"), f"{tag}-cancel-1"),
                                   "status_cmd_stdout": st["stdout_tail"]}
    h.dag(f"{tag}-ok", "type: graph\nsteps:\n  - id: one\n    run: echo one\n  - id: two\n    run: echo two\n    depends: [one]\n")
    ok = h.run("start", "--dagu-home", str(h.home), "--run-id", f"{tag}-ok-1", str(h.dags / f"{tag}-ok.yaml"))
    res["success_fixture"] = {"cli_exit": ok["exit"], "status": run_status(h.history(f"{tag}-ok"), f"{tag}-ok-1")}

    def snapshot():
        cli = {d: run_status(h.history(d), f"{d}-1") for d in (f"{tag}-failure", f"{tag}-cancel", f"{tag}-ok")}
        code, body = h.http("/api/v1/dags")
        api = {}
        if code == 200:
            for item in json.loads(body).get("dags", []):
                latest = item.get("latestDAGRun") or {}
                api[item.get("fileName")] = {"dagRunId": latest.get("dagRunId"), "statusLabel": latest.get("statusLabel")}
        return {"cli_history": cli, "api_http": code, "api_latest_runs": api}

    s1 = h.spawn("server", "--dagu-home", str(h.home), logname="server-1")
    up1 = h.wait_http(True)
    before = snapshot()
    os.killpg(s1.pid, signal.SIGTERM)
    s1.wait(timeout=30)
    down = h.wait_http(False)
    s2 = h.spawn("server", "--dagu-home", str(h.home), logname="server-2")
    up2 = h.wait_http(True)
    after = snapshot()
    os.killpg(s2.pid, signal.SIGTERM)
    s2.wait(timeout=30)
    res["restart_history"] = {"server_up_before": up1, "server_down_between": down, "server_up_after": up2,
                              "before": before, "after": after,
                              "prior_history_rows_preserved": before["cli_history"] == after["cli_history"]
                              and before["api_latest_runs"] == after["api_latest_runs"] and bool(after["api_latest_runs"])}
    return res


def kill(h: Home, tag: str, step_sleep: int, scheduler_wait: int):
    res = {}
    name = f"{tag}-kill"
    # Fix round 1 (2026-09-23): the first run referenced $MARKS inside the
    # step, but Dagu 2.16.6 only passes env names listed in env_passthrough,
    # so the markers were written to "/" and failed. Embed the absolute path.
    m = str(h.marks)
    h.dag(name, "type: graph\nsteps:\n"
          f"  - id: step1\n    run: sh -c 'date +%s >> {m}/step1.started; sleep {step_sleep}; date +%s >> {m}/step1.finished'\n"
          f"  - id: step2\n    run: sh -c 'date +%s >> {m}/step2.ran'\n    depends: [step1]\n")
    run_id = f"{name}-1"
    p = h.spawn("start", "--dagu-home", str(h.home), "--run-id", run_id, str(h.dags / f"{name}.yaml"), logname="kill-start")
    started = h.marks / "step1.started"
    for _ in range(60):
        if started.exists():
            break
        time.sleep(0.25)
    res["step1_started_before_kill"] = started.exists()
    time.sleep(2)
    t_kill = now()
    os.killpg(p.pid, signal.SIGKILL)
    p.wait(timeout=10)
    res["kill"] = {"t": t_kill, "signal": "SIGKILL to the dagu start process group", "reaped": p.poll() is not None}
    res["immediately_after_kill"] = {"status": run_status(h.history(name), run_id),
                                     "ps": h.run("ps", "--dagu-home", str(h.home))["stdout_tail"]}
    attempts = []
    for threshold in (35, 95):
        wait = t_kill + threshold - now()
        if wait > 0:
            time.sleep(wait)
        rec = h.run("retry", "--dagu-home", str(h.home), "--run-id", run_id, name, timeout=step_sleep + 60)
        attempts.append({"seconds_after_kill": round(now() - t_kill, 1), "retry_exit": rec["exit"],
                         "retry_stderr_tail": rec["stderr_tail"][-300:], "retry_stdout_tail": rec["stdout_tail"][-300:],
                         "status_after": run_status(h.history(name), run_id)})
        if rec["exit"] == 0:
            break
    res["manual_retries_without_scheduler"] = attempts
    res["scheduler_phase"] = None
    if all(a["retry_exit"] != 0 for a in attempts):
        sched = h.spawn("scheduler", "--dagu-home", str(h.home), logname="scheduler")
        t_s = now()
        polls = []
        status = None
        while now() - t_s < scheduler_wait:
            status = run_status(h.history(name), run_id)
            polls.append({"seconds_after_kill": round(now() - t_kill, 1), "status": status})
            if status != "running":
                break
            time.sleep(15)
        rec = h.run("retry", "--dagu-home", str(h.home), "--run-id", run_id, name, timeout=step_sleep + 60)
        res["scheduler_phase"] = {"scheduler_started_seconds_after_kill": round(t_s - t_kill, 1),
                                  "polls": polls, "status_when_poll_ended": status,
                                  "retry_after_scheduler": {"seconds_after_kill": round(now() - t_kill, 1),
                                                            "exit": rec["exit"], "stderr_tail": rec["stderr_tail"][-300:],
                                                            "status_after": run_status(h.history(name), run_id)}}
        os.killpg(sched.pid, signal.SIGTERM)
        sched.wait(timeout=30)
    res["final_status"] = run_status(h.history(name), run_id)
    res["markers"] = {m.name: m.read_text().split() for m in sorted(h.marks.iterdir())}
    # telemetry surface: the server's Prometheus endpoint in the same DAGU_HOME
    s = h.spawn("server", "--dagu-home", str(h.home), logname="server-metrics")
    h.wait_http(True)
    code, body = h.http("/api/v1/metrics")
    os.killpg(s.pid, signal.SIGTERM)
    s.wait(timeout=30)
    res["telemetry"] = {"endpoint": "/api/v1/metrics", "http": code,
                        "dagu_metric_lines": [ln for ln in body.splitlines() if ln.startswith("dagu_") and "{" in ln or ln.startswith("dagu_dag_runs")][:40]}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dagu", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--scenario", choices=["hosting", "kill"], required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--sched-port", type=int, required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--step-sleep", type=int, default=20)
    ap.add_argument("--scheduler-wait", type=int, default=240)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=False)
    h = Home(a.dagu, work, a.port, a.sched_port)
    version = subprocess.run([a.dagu, "version"], capture_output=True, text=True).stdout.strip() or \
        subprocess.run([a.dagu, "version"], capture_output=True, text=True).stderr.strip()
    out = {"dagu_version": version, "scenario": a.scenario, "tag": a.tag}
    try:
        out["result"] = hosting(h, a.tag) if a.scenario == "hosting" else kill(h, a.tag, a.step_sleep, a.scheduler_wait)
    finally:
        h.cleanup()
        out["command_log"] = h.log
        out["elapsed_s"] = now()
        Path(a.out).write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["result"], indent=1)[:4000])


if __name__ == "__main__":
    main()
