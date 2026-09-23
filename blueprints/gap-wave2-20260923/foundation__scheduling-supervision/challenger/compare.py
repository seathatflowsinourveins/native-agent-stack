#!/usr/bin/env python3
"""Gaps 4 and 6: run the frozen job-recovery cases on Dagu 2.16.6, Prefect 3.8.6 and a
Temporal dev server (CLI 1.9.1, temporalio 1.33.0) through ONE shared oracle.

The workload in every engine is the unchanged blueprints/convergence-practice/job-recovery
fixture.py (checkpoint: exclusive claim + unchanged 12-test oracle; finalize: waits for a
release file, reruns the 12 tests, writes one exclusive completed.json). Engines differ only
in how they schedule the two steps and in their native stop/retry/recovery verbs.

Scenario A (one fresh case per engine): start -> finalize waiting -> native stop ->
release -> native retry. Cases scored: stop, retry, checkpoint_reuse.
Scenario B (one fresh case per engine): start -> finalize waiting -> SIGKILL every process
of the executor tree -> release -> native recovery attempts within --window seconds.
Case scored: sigkill.

Oracle fields follow blueprints/gap-resolution-20260922/dagu-2170-checkpoint-parity/run_parity.py.
Only loopback ports and directories under --work are used; every started process is stopped.

Usage: compare.py --work /new/absolute/dir [--engines dagu,prefect,temporal] [--window 150]
                  [--dagu-recovery none|scheduler]

Fix round 1 (review of b7aec6b): the default window is the preregistered 150 s bound
(preregistrations/4.json); `--dagu-recovery none` is the preregistered Dagu protocol (bare
retries, no scheduler) and `--dagu-recovery scheduler` is the post-hoc variant (a scheduler
started after the kill). Every Dagu case uses a private config with `scheduler.port: 0`, and
the scheduler variant samples TCP listeners owned by the scheduler tree.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import dagu_common as dc  # noqa: E402

ROOT = HERE.parents[3]
JOB = ROOT / "blueprints/convergence-practice/job-recovery"
sys.path.insert(0, str(JOB))
import fixture  # noqa: E402  (unmodified job-recovery/fixture.py)

CH = Path.home() / ".cache/gap-wave2-20260923/scheduling-supervision/challengers"
PREFECT_PY = CH / "prefect-3.8.6/bin/python"
PREFECT_CLI = CH / "prefect-3.8.6/bin/prefect"
TEMPORAL_PY = CH / "temporalio-1.33.0/bin/python"
TEMPORAL_CLI = CH / "temporal-cli/temporal"
FIXTURE_PY = "/usr/bin/python3"
BASE_ENV = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "DO_NOT_TRACK": "1"}


def now():
    return datetime.now(timezone.utc).isoformat()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def prepare_case(case):
    case.mkdir(mode=0o700, parents=True)
    (case / "source").mkdir()
    for name, src in {"planner.py": ROOT / "blueprints/convergence-practice/native-worker/accepted/planner.py",
                      "test_planner.py": ROOT / "blueprints/convergence-practice/native-worker/seed/test_planner.py"}.items():
        shutil.copyfile(src, case / "source" / name)
    fixture.exclusive(case / "expected.json", fixture.source_hashes(case))
    shutil.copyfile(JOB / "fixture.py", case / "fixture.py")
    return {"fixture_sha256": fixture.digest(case / "fixture.py"), "expected": json.loads((case / "expected.json").read_text())}


def tests_ran(log):
    return 12 if log.exists() and "Ran 12 tests" in log.read_text() and log.read_text().rstrip().endswith("OK") else 0


def oracle(case, before_sha):
    started = json.loads((case / "checkpoint-started.json").read_text()) if (case / "checkpoint-started.json").exists() else None
    try:
        sha = fixture.verify_checkpoint(case)
    except Exception as exc:  # noqa: BLE001 - recorded, not hidden
        sha = f"error: {exc}"
    completed = json.loads((case / "completed.json").read_text()) if (case / "completed.json").exists() else None
    return {"checkpoint_execution_count": (started or {}).get("execution_count"),
            "checkpoint_sha256_unchanged": sha == before_sha, "checkpoint_sha256": sha,
            "checkpoint_tests": tests_ran(case / "checkpoint-tests.log"), "final_tests": tests_ran(case / "final-tests.log"),
            "completed": completed,
            "completed_matches": completed == {"checkpoint_sha256": before_sha, "tests": 12, "execution_count": 1},
            "retry_ready_written": (case / "retry-ready.json").exists()}


def alive(identities):
    """Identity-matched processes that are still running; zombies (exited, awaiting reap) do not count."""
    out = subprocess.run(["/bin/ps", "-axo", "pid=,stat=,lstart=,args="], capture_output=True, text=True).stdout
    rows = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 7:
            rows[int(parts[0])] = (parts[1], " ".join(parts[2:7]), " ".join(parts[7:])[:160])
    return {pid: rows[pid][2] for pid, started in identities.items()
            if pid in rows and rows[pid][1] == started and not rows[pid][0].startswith("Z")}


def run_scoped(engine):
    """Processes that belong to the in-flight run: every `fixture.py` process under the executor
    plus its ancestors below the long-lived executor (Dagu's `dagu start` is itself run-scoped).
    Long-lived executor helpers (e.g. Prefect's multiprocessing resource tracker) are excluded
    and listed separately."""
    table = dc.process_table()
    tree = engine.executor_tree(include_self=True)
    args = {pid: subprocess.run(["/bin/ps", "-o", "args=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
            for pid in tree}
    scoped = set()
    for pid in [p for p, a in args.items() if "fixture.py" in a]:
        while pid in tree and pid != engine.proc.pid:
            scoped.add(pid)
            pid = table[pid][0]
    if engine.name == "dagu":
        scoped = set(tree)
    excluded = sorted(a[:160] for p, a in args.items() if p not in scoped and p != engine.proc.pid)
    return {p: tree[p] for p in scoped}, excluded


def kill_tree(identities, direct=None):
    for pid in identities:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if direct is not None:
        try:
            direct.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    return dc.wait_for(lambda: not alive(identities), 15)


def spawn(argv, cwd, env, log_prefix):
    out = open(f"{log_prefix}.stdout", "a")
    err = open(f"{log_prefix}.stderr", "a")
    return subprocess.Popen(argv, cwd=cwd, env=env, stdout=out, stderr=err, start_new_session=True)


# ---------------------------------------------------------------- Dagu 2.16.6
class Dagu:
    name = "dagu"
    stopped_states = {"aborted"}

    def __init__(self, root, recovery_mode="none"):
        self.root, self.recovery_mode, self.isolation = root, recovery_mode, None
        self.setup = {"install": "existing pinned binary (sha256 %s), no new download" % dc.DAGU_2166_SHA256,
                      "long_running_processes": ["none for stop/retry (dagu start runs the DAG in-process)",
                                                 "dagu scheduler during SIGKILL recovery only (--dagu-recovery scheduler)"],
                      "sigkill_recovery_mode": recovery_mode, "private_config": dc.PRIVATE_CONFIG,
                      "version": subprocess.run([str(dc.DAGU), "version"], capture_output=True, text=True).stdout.strip()}

    def begin(self, case):
        home, dags = case / "dagu-home", case / "dags"
        home.mkdir()
        dags.mkdir()
        (case / "config.yaml").write_text(dc.PRIVATE_CONFIG)
        self.wf = dags / "recovery.yaml"
        cmd = {a: json.dumps(f"{FIXTURE_PY} -B {case}/fixture.py {a} {case}") for a in ("checkpoint", "finalize")}
        self.wf.write_text("\n".join(["type: graph", "timeout_sec: 600", "max_active_runs: 1",
                                      "working_dir: " + json.dumps(str(case)), "steps:", "  - id: checkpoint",
                                      "    run: " + cmd["checkpoint"], "  - id: finalize", "    depends: [checkpoint]",
                                      "    run: " + cmd["finalize"], ""]))
        self.env = dict(BASE_ENV, HOME=str(case), DAGU_HOME=str(home), TMPDIR=str(case))
        self.base = [str(dc.DAGU), "--context", "local", "--dagu-home", str(home), "--config", str(case / "config.yaml")]
        self.rec = dc.Recorder(case, self.env)
        self.run_id = "recovery-" + os.urandom(8).hex()
        self.proc = spawn(self.base + ["start", "--run-id", self.run_id, str(self.wf)], case, self.env, case / "native" / "start")
        self.case = case
        return self.run_id

    def status(self):
        rows = [r for r in dc.history_rows(self.rec.call("history", self.base + ["history", "--run-id", self.run_id, "--format", "json"], check=False) or "[]") if r.get("dagRunId") == self.run_id]
        return rows[0]["status"] if rows else None

    def executor_tree(self, include_self=True):
        return dc.descendants(self.proc.pid, include_self)

    def stop(self):
        self.rec.call("stop", self.base + ["stop", "--run-id", self.run_id, str(self.wf)])
        self.proc.wait(timeout=60)
        return self.status()

    def retry(self):
        self.rec.call("retry", self.base + ["retry", "--run-id", self.run_id, "--step", "finalize", str(self.wf)], timeout=120)
        return self.status(), self.run_id

    def recover(self, window):
        attempts, deadline = [], time.monotonic() + window
        sched, samples = None, []
        if self.recovery_mode == "scheduler":
            sched = spawn(self.base + ["scheduler", "--dags", str(self.wf.parent)], self.case, self.env, self.case / "native" / "scheduler")
            self.isolation = {"listener_probe_self_test": dc.listener_probe_self_test(), "samples": samples}
        try:
            while time.monotonic() < deadline:
                for _ in range(3):
                    time.sleep(5)
                    if sched is not None and sched.poll() is None:
                        tree = dc.descendants(sched.pid, include_self=True)
                        samples.append({"at": now(), "scheduler_tree_pids": len(tree), "listeners": dc.listeners(tree)})
                label = f"recover-retry-{len(attempts) + 1}"
                self.rec.call(label, self.base + ["retry", "--run-id", self.run_id, "--step", "finalize", str(self.wf)], check=False, timeout=90)
                status = self.status()
                attempts.append({"at": now(), "verb": "dagu retry --step finalize", "exit": self.rec.codes[label],
                                 "stderr_tail": (self.case / "native" / f"{label}.stderr").read_text()[-300:], "status_after": status})
                if status == "succeeded":
                    break
        finally:
            dc.stop_group(sched)
        if sched is not None:
            log = (self.case / "native" / "scheduler.stderr").read_text()
            self.isolation.update({
                "health_server_disabled_logged": "Health check server disabled" in log,
                "health_server_started_logged": "Starting health check server" in log,
                "sample_count": len(samples),
                "listener_rows_owned_by_scheduler_tree": sum(len(x["listeners"]) for x in samples)})
            return self.status(), attempts, ["dagu scheduler started after the kill (zombie detection), private config scheduler.port 0",
                                              "dagu retry --run-id --step finalize every 15 s"]
        return self.status(), attempts, ["no scheduler (preregistered protocol)", "dagu retry --run-id --step finalize every 15 s"]

    def finish(self):
        dc.stop_group(self.proc)

    def teardown(self):
        pass


# ---------------------------------------------------------------- Prefect 3.8.6
class Prefect:
    name = "prefect"
    stopped_states = {"CANCELLED"}

    def __init__(self, root):
        self.root = root / "prefect-server"
        self.root.mkdir(parents=True)
        self.port = free_port()
        self.env = dict(BASE_ENV, HOME=str(self.root), PREFECT_HOME=str(self.root / "home"),
                        PREFECT_API_URL=f"http://127.0.0.1:{self.port}/api", PREFECT_SERVER_ANALYTICS_ENABLED="false",
                        PREFECT_UI_ENABLED="false", PREFECT_LOCAL_STORAGE_PATH=str(self.root / "results"),
                        PREFECT_RUNNER_POLL_FREQUENCY="2", PREFECT_LOGGING_LEVEL="INFO")
        server_env = {k: v for k, v in self.env.items() if k != "PREFECT_API_URL"}
        t0 = time.monotonic()
        self.server = spawn([str(PREFECT_CLI), "server", "start", "--host", "127.0.0.1", "--port", str(self.port), "--no-ui"],
                            self.root, server_env, self.root / "server")
        ready = dc.wait_for(self._healthy, 180, 1)
        self.setup = {"install": "uv venv + `uv pip install prefect==3.8.6` in a new prefix (network download of the wheel tree)",
                      "long_running_processes": ["prefect server start (loopback, sqlite under the work dir)",
                                                 "prefect_flow.py serve runner (flow.serve)"],
                      "server_ready_seconds": round(time.monotonic() - t0, 1), "server_ready": ready,
                      "version": subprocess.run([str(PREFECT_CLI), "version"], capture_output=True, text=True, env=self.env).stdout.split("\n")[0].strip()}
        if not ready:
            raise RuntimeError("Prefect server did not become healthy")

    def _healthy(self):
        try:
            return urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/health", timeout=2).status == 200
        except Exception:  # noqa: BLE001
            return False

    def _ctl(self, *args, timeout=120):
        out = subprocess.run([str(PREFECT_PY), str(HERE / "prefect_ctl.py"), *args], cwd=HERE, env=self.env,
                             capture_output=True, text=True, timeout=timeout)
        if out.returncode:
            raise RuntimeError(f"prefect_ctl {args} failed: {out.stderr[-500:]}")
        return json.loads(out.stdout.strip().splitlines()[-1])

    def _runner(self):
        return spawn([str(PREFECT_PY), str(HERE / "prefect_flow.py")], HERE, self.env, self.case / "native" / "runner")

    def begin(self, case):
        self.case = case
        self.rec = dc.Recorder(case, self.env, default_timeout=120)
        self.proc = self._runner()
        t0 = time.monotonic()
        while True:
            try:
                self.run_id = self._ctl("trigger", str(case))["flow_run_id"]
                break
            except RuntimeError:
                if time.monotonic() - t0 > 90:
                    raise
                time.sleep(2)
        return self.run_id

    def state(self):
        return self._ctl("state", self.run_id)

    def status(self):
        return self.state()["state_type"]

    def executor_tree(self, include_self=True):
        return dc.descendants(self.proc.pid, include_self)

    def stop(self):
        self.rec.call("stop", [str(PREFECT_CLI), "flow-run", "cancel", self.run_id])
        dc.wait_for(lambda: self.status() in ("CANCELLED", "COMPLETED", "FAILED", "CRASHED"), 90, 1)
        return self.status()

    def retry(self):
        self.rec.call("retry", [str(PREFECT_CLI), "flow-run", "retry", self.run_id], check=False)
        dc.wait_for(lambda: self.status() in ("COMPLETED", "FAILED", "CRASHED", "CANCELLED"), 150, 1)
        return self.status(), self.run_id

    def recover(self, window):
        attempts, deadline = [], time.monotonic() + window
        self.proc = self._runner()
        while time.monotonic() < deadline:
            time.sleep(15)
            label = f"recover-retry-{len(attempts) + 1}"
            self.rec.call(label, [str(PREFECT_CLI), "flow-run", "retry", self.run_id], check=False)
            dc.wait_for(lambda: self.status() == "COMPLETED", 10, 1)
            st = self.state()
            attempts.append({"at": now(), "verb": "prefect flow-run retry", "exit": self.rec.codes[label],
                             "output_tail": ((self.case / "native" / f"{label}.stdout").read_text() + (self.case / "native" / f"{label}.stderr").read_text())[-300:],
                             "status_after": st["state_type"], "state_name": st["state_name"]})
            if st["state_type"] == "COMPLETED":
                break
        return self.status(), attempts, ["restart the flow.serve runner", "prefect flow-run retry <id> every 15 s"]

    def finish(self):
        self.task_runs = self.state()
        dc.stop_group(self.proc)

    def teardown(self):
        dc.stop_group(self.server, grace=20)


# ---------------------------------------------------------------- Temporal dev server
class Temporal:
    name = "temporal"
    stopped_states = {"CANCELED"}

    def __init__(self, root):
        self.root = root / "temporal-server"
        self.root.mkdir(parents=True)
        self.port = free_port()
        self.addr = f"127.0.0.1:{self.port}"
        self.env = dict(BASE_ENV, HOME=str(self.root))
        t0 = time.monotonic()
        self.server = spawn([str(TEMPORAL_CLI), "server", "start-dev", "--ip", "127.0.0.1", "--port", str(self.port),
                             "--ui-port", str(free_port()), "--http-port", str(free_port()), "--metrics-port", str(free_port()),
                             "--headless", "--db-filename", str(self.root / "temporal.db"), "--log-level", "error"],
                            self.root, self.env, self.root / "server")
        ready = dc.wait_for(lambda: subprocess.run([str(TEMPORAL_CLI), "operator", "cluster", "health", "--address", self.addr],
                                                   capture_output=True, env=self.env).returncode == 0, 120, 1)
        self.setup = {"install": "temporal CLI 1.9.1 release archive (sha256 09a0326a..., matches checksums.txt and the GitHub asset digest) + uv venv `temporalio==1.33.0`",
                      "long_running_processes": ["temporal server start-dev (loopback, sqlite file under the work dir)",
                                                 "temporal_worker.py worker"],
                      "server_ready_seconds": round(time.monotonic() - t0, 1), "server_ready": ready,
                      "version": subprocess.run([str(TEMPORAL_CLI), "--version"], capture_output=True, text=True).stdout.strip()}
        if not ready:
            raise RuntimeError("Temporal dev server did not become healthy")

    def _cli(self, label, args, check=True, timeout=60):
        return self.rec.call(label, [str(TEMPORAL_CLI), *args, "--address", self.addr], check=check, timeout=timeout)

    def _worker(self):
        n = len(list((self.case / "native").glob("worker*.stdout")))
        log = self.case / "native" / f"worker{n + 1}"
        proc = spawn([str(TEMPORAL_PY), str(HERE / "temporal_worker.py"), self.addr, self.queue, FIXTURE_PY], HERE, self.env, log)
        dc.wait_for(lambda: "worker-ready" in Path(f"{log}.stdout").read_text(), 60, 0.2)
        return proc

    def begin(self, case):
        self.case = case
        self.rec = dc.Recorder(case, self.env)
        self.queue = "q-" + os.urandom(4).hex()
        self.wid = "recovery-" + os.urandom(6).hex()
        self.proc = self._worker()
        self._cli("start", ["workflow", "start", "--type", "Recovery", "--task-queue", self.queue, "--workflow-id", self.wid,
                            "--input", json.dumps(str(case))])
        return self.wid

    def describe(self):
        out = self._cli("describe", ["workflow", "describe", "--workflow-id", self.wid, "--output", "json"], check=False)
        info = json.loads(out).get("workflowExecutionInfo", {}) if out.strip() else {}
        return str(info.get("status", "")).replace("WORKFLOW_EXECUTION_STATUS_", "").upper(), info.get("execution", {}).get("runId")

    def status(self):
        return self.describe()[0]

    def executor_tree(self, include_self=True):
        return dc.descendants(self.proc.pid, include_self)

    def stop(self):
        self._cli("stop", ["workflow", "cancel", "--workflow-id", self.wid])
        dc.wait_for(lambda: self.status() in ("CANCELED", "COMPLETED", "FAILED", "TERMINATED"), 60, 1)
        return self.status()

    def retry(self):
        events = json.loads(self._cli("history", ["workflow", "show", "--workflow-id", self.wid, "--output", "json"])).get("events", [])
        norm = [(int(e["eventId"]), str(e.get("eventType", "")).replace("EVENT_TYPE_", "").replace("_", "").upper(), e) for e in events]
        done = [i for i, t, _ in norm if t == "ACTIVITYTASKCOMPLETED"]
        reset_to = next(i for i, t, _ in norm if t == "WORKFLOWTASKCOMPLETED" and i > done[0])
        self.reset_event = {"checkpoint_activity_completed_event": done[0], "reset_event_id": reset_to}
        before_run = self.describe()[1]
        self._cli("retry", ["workflow", "reset", "--workflow-id", self.wid, "--event-id", str(reset_to), "--reason", "gap-wave2 retry"])
        dc.wait_for(lambda: self.status() in ("COMPLETED", "FAILED", "TERMINATED", "CANCELED"), 150, 1)
        status, after_run = self.describe()
        self.run_ids = {"before_reset": before_run, "after_reset": after_run}
        return status, self.wid

    def recover(self, window):
        attempts, deadline = [], time.monotonic() + window
        self.proc = self._worker()
        attempts.append({"at": now(), "verb": "start a new worker (no manual retry verb)"})
        dc.wait_for(lambda: self.status() in ("COMPLETED", "FAILED", "TERMINATED"), window, 2)
        attempts.append({"at": now(), "status_after": self.status()})
        return self.status(), attempts, ["start a new worker process; the server retries the finalize activity after its 5 s heartbeat timeout"]

    def finish(self):
        self.history = self._cli("final-history", ["workflow", "show", "--workflow-id", self.wid, "--output", "json"], check=False)
        dc.stop_group(self.proc)

    def teardown(self):
        dc.stop_group(self.server, grace=20)


SUCCESS = {"dagu": "succeeded", "prefect": "COMPLETED", "temporal": "COMPLETED"}


def scenario_a(engine, case):
    frozen = prepare_case(case)
    record = {"frozen": frozen, "started_at": now()}
    run = engine.begin(case)
    if not dc.wait_for(lambda: (case / "finalize-ready.json").exists(), 120, 0.05):
        raise RuntimeError(f"{engine.name}: finalizer not reached")
    owned, excluded = run_scoped(engine)
    before = fixture.verify_checkpoint(case)
    stop_status = engine.stop()
    dc.wait_for(lambda: not alive(owned), 30)
    remaining = alive(owned)
    record.update({"native_run": run, "before_retry_status": stop_status, "completed_before_retry": (case / "completed.json").exists(),
                   "observed_owned_processes_remaining": len(remaining), "remaining_process_commands": sorted(remaining.values()),
                   "owned_processes_observed": len(owned), "executor_helpers_not_run_scoped": excluded})
    (case / "release-finalize").touch(exist_ok=False)
    after_status, after_run = engine.retry()
    record.update({"after_retry_status": after_status, "same_native_run_id": after_run == run})
    if engine.name == "temporal":
        record["temporal_run_ids"] = engine.run_ids
        record["temporal_reset"] = engine.reset_event
        record["same_native_run_id_note"] = "workflow id retained; reset creates a new run id under it"
    retry_pid = json.loads((case / "retry-ready.json").read_text())["pid"] if (case / "retry-ready.json").exists() else None
    record["retry_finalizer_remaining"] = retry_pid in dc.process_table() if retry_pid else None
    engine.finish()
    if engine.name == "prefect":
        record["prefect_state_after"] = engine.task_runs
    record["oracle"] = oracle(case, before)
    o = record["oracle"]
    record["cases"] = {
        "stop": stop_status in engine.stopped_states and not record["completed_before_retry"] and record["observed_owned_processes_remaining"] == 0,
        "retry": after_status == SUCCESS[engine.name] and o["completed"] is not None,
        "checkpoint_reuse": o["checkpoint_execution_count"] == 1 and o["checkpoint_sha256_unchanged"] and o["checkpoint_tests"] == 12
                            and o["final_tests"] == 12 and o["completed_matches"],
    }
    record["completed_at"] = now()
    return record


def scenario_b(engine, case, window):
    frozen = prepare_case(case)
    record = {"frozen": frozen, "started_at": now(), "window_seconds": window}
    run = engine.begin(case)
    if not dc.wait_for(lambda: (case / "finalize-ready.json").exists(), 120, 0.05):
        raise RuntimeError(f"{engine.name}: finalizer not reached")
    before = fixture.verify_checkpoint(case)
    tree = engine.executor_tree(include_self=True)
    record["killed_process_count"] = len(tree)
    record["all_killed"] = kill_tree(tree, direct=engine.proc)
    record["alive_after_kill"] = sorted(alive(tree).values())
    record["status_after_kill"] = engine.status()
    time.sleep(2)
    record["status_after_kill_2s"] = engine.status()
    (case / "release-finalize").touch(exist_ok=False)
    t0 = time.monotonic()
    final_status, attempts, steps = engine.recover(window)
    record.update({"native_run": run, "recovery_seconds": round(time.monotonic() - t0, 1), "final_status": final_status,
                   "recovery_attempts": attempts, "operational_steps": steps})
    engine.finish()
    record["oracle"] = oracle(case, before)
    o = record["oracle"]
    record["cases"] = {"sigkill": final_status == SUCCESS[engine.name] and o["checkpoint_execution_count"] == 1
                                  and o["checkpoint_sha256_unchanged"] and o["completed_matches"] and o["final_tests"] == 12}
    record["sigkill_within_preregistered_150s"] = record["cases"]["sigkill"] and record["recovery_seconds"] <= 150
    record["scheduler_isolation"] = getattr(engine, "isolation", None)
    record["completed_at"] = now()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--engines", default="dagu,prefect,temporal")
    parser.add_argument("--window", type=int, default=150)
    parser.add_argument("--dagu-recovery", choices=("none", "scheduler"), default="none")
    args = parser.parse_args()
    if not args.work.is_absolute() or args.work.exists():
        raise SystemExit("--work must name a new absolute directory")
    args.work.mkdir(mode=0o700, parents=True)
    os.umask(0o077)
    result = {"started_at": now(), "platform": platform.system() + " " + platform.release(), "python": platform.python_version(),
              "inputs": {p.name: fixture.digest(p) for p in sorted(HERE.glob("*.py")) + [HERE.parent / "dagu_common.py"]},
              "job_recovery_fixture_sha256": fixture.digest(JOB / "fixture.py"), "engines": {},
              "protocol": {"window_seconds": args.window, "dagu_recovery": args.dagu_recovery}}
    classes = {"dagu": Dagu, "prefect": Prefect, "temporal": Temporal}
    for name in args.engines.split(","):
        entry = {}
        engine = None
        try:
            engine = Dagu(args.work, args.dagu_recovery) if name == "dagu" else classes[name](args.work)
            entry["setup"] = engine.setup
            entry["scenario_a"] = scenario_a(engine, args.work / name / "stop-retry")
            entry["scenario_b"] = scenario_b(engine, args.work / name / "sigkill", args.window)
        except Exception as exc:  # noqa: BLE001 - retained as the engine's result
            entry["error"] = f"{type(exc).__name__}: {exc}"
            try:
                engine and engine.finish()
            except Exception:  # noqa: BLE001
                pass
        finally:
            if engine is not None:
                engine.teardown()
        cases = dict(entry.get("scenario_a", {}).get("cases", {}), **entry.get("scenario_b", {}).get("cases", {}))
        entry["case_table"] = {c: cases.get(c) for c in ("stop", "retry", "checkpoint_reuse", "sigkill")}
        result["engines"][name] = entry
        print(name, json.dumps(entry["case_table"]), entry.get("error", ""), flush=True)
    leftovers = subprocess.run(["/bin/ps", "-eo", "pid,args"], capture_output=True, text=True).stdout
    result["leftover_processes_mentioning_work_dir"] = [l.strip()[:200] for l in leftovers.splitlines() if str(args.work) in l]
    result["completed_at"] = now()
    fixture.exclusive(args.work / "result.json", result)
    print(json.dumps({n: e["case_table"] for n, e in result["engines"].items()}, indent=2))


if __name__ == "__main__":
    main()
