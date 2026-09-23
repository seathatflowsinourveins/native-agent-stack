#!/usr/bin/env python3
"""Round 4, gap 11: a paused ("zombie") Temporal worker resumes after its activity was retried elsewhere.

controller: starts a loopback Temporal dev server (temporalio.testing, CLI reused from round 1's
download dir), starts one workflow, launches worker A, waits until attempt 1 has heartbeated and
entered its slow section, then SIGSTOPs worker A (a stand-in for a network partition or a long pause).
The activity's heartbeat timeout (3 s) makes the server schedule attempt 2, which worker B runs and
completes; the workflow finishes. Only then is worker A resumed with SIGCONT. Its attempt 1 carries on
and tries the effect write:
  - effects (PRIMARY KEY idempotency key, INSERT OR IGNORE): the stale write must be refused;
  - effects_nokey (no key, plain INSERT): negative control, the stale write lands a second row.
Worker A's late completion is then rejected by the server (logged by the worker SDK). The history is
replayed with Replayer. Activities are synchronous (thread pool) so the frozen thread resumes exactly
where it stopped; attempt 1 does not heartbeat after it resumes. Run 1 (without the retry below) showed the
SDK injecting a cancellation into the resumed thread, which rolled back the stale transaction before
commit; the retry makes the stale write land so the idempotency key, not that race, is what is tested.
worker: runs the workflow and activity against the given address.
Usage: temporal_zombie.py controller WORKDIR CLI_DIR OUT | worker ADDRESS LOGFILE
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Replayer, Worker

TASK_QUEUE = "gap11-zombie-queue"


def _db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS attempts(n INTEGER PRIMARY KEY, attempt INT, pid INT, phase TEXT, at REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS effects(key TEXT PRIMARY KEY, attempt INT, pid INT, at REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS effects_nokey(n INTEGER PRIMARY KEY, key TEXT, attempt INT, pid INT, at REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS writes(n INTEGER PRIMARY KEY, attempt INT, pid INT, keyed_applied INT, at REAL)")
    return con


def _write_effect(db: str, key: str, attempt: int) -> bool:
    """One transaction: keyed effect (INSERT OR IGNORE), unkeyed control row and a write record."""
    con = _db(db)
    try:
        cur = con.execute("INSERT OR IGNORE INTO effects(key, attempt, pid, at) VALUES (?,?,?,?)",
                          (key, attempt, os.getpid(), time.time()))
        applied = cur.rowcount == 1
        con.execute("INSERT INTO effects_nokey(key, attempt, pid, at) VALUES (?,?,?,?)", (key, attempt, os.getpid(), time.time()))
        con.execute("INSERT INTO writes(attempt, pid, keyed_applied, at) VALUES (?,?,?,?)",
                    (attempt, os.getpid(), int(applied), time.time()))
        con.commit()
        return applied
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


@activity.defn
def apply_effect(args: list[str]) -> str:
    db, key = args
    info = activity.info()
    con = _db(db)
    con.execute("INSERT INTO attempts(attempt, pid, phase, at) VALUES (?,?,?,?)", (info.attempt, os.getpid(), "start", time.time()))
    con.commit()
    activity.heartbeat("start")
    if info.attempt == 1:
        con.execute("INSERT INTO attempts(attempt, pid, phase, at) VALUES (?,?,?,?)", (info.attempt, os.getpid(), "slow", time.time()))
        con.commit()
        try:
            time.sleep(4)  # the controller freezes this process here; no heartbeat is sent after it resumes
        except BaseException as error:  # cancellation injected by the SDK after resume
            con.execute("INSERT INTO attempts(attempt, pid, phase, at) VALUES (?,?,?,?)",
                        (info.attempt, os.getpid(), "cancel-during-sleep:" + type(error).__name__, time.time()))
            con.commit()
    con.close()
    # An effect already dispatched cannot be recalled by a later cancellation. To test the idempotency key
    # (not the SDK's cancellation race), attempt 1 retries its transaction if a cancellation lands inside it.
    for _ in range(3):
        try:
            applied = _write_effect(db, key, info.attempt)
            break
        except BaseException as error:
            if info.attempt != 1:
                raise
            c2 = _db(db)
            c2.execute("INSERT INTO attempts(attempt, pid, phase, at) VALUES (?,?,?,?)",
                       (info.attempt, os.getpid(), "cancel-during-write:" + type(error).__name__, time.time()))
            c2.commit()
            c2.close()
    else:
        applied = None
    return f"attempt={info.attempt} keyed_applied={applied} pid={os.getpid()}"


@workflow.defn
class ZombieWorkflow:
    @workflow.run
    async def run(self, db: str) -> dict:
        key = f"effect-{workflow.info().workflow_id}"
        out = await workflow.execute_activity(
            apply_effect, [db, key], start_to_close_timeout=timedelta(seconds=60),
            heartbeat_timeout=timedelta(seconds=3),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=5))
        return {"activity": out, "key": key}


async def run_worker(address: str) -> None:
    client = await Client.connect(address)
    with ThreadPoolExecutor(max_workers=4) as pool:
        async with Worker(client, task_queue=TASK_QUEUE, workflows=[ZombieWorkflow], activities=[apply_effect],
                          activity_executor=pool):
            await asyncio.Event().wait()


def rows(db: str, sql: str, cols: tuple) -> list[dict]:
    con = _db(db)
    out = [dict(zip(cols, r)) for r in con.execute(sql)]
    con.close()
    return out


async def controller(workdir: str, cli_dir: str, out: str) -> dict:
    from temporalio.testing import WorkflowEnvironment
    db = os.path.join(workdir, "ledger.sqlite")
    rec: dict = {"controller_pid": os.getpid()}
    env = await WorkflowEnvironment.start_local(ip="127.0.0.1", download_dest_dir=cli_dir,
                                                dev_server_database_filename=os.path.join(workdir, "temporal.db"))
    procs: list[subprocess.Popen] = []
    try:
        address = env.client.service_client.config.target_host
        rec["server_address_is_loopback"] = address.startswith("127.0.0.1:")

        def spawn(tag: str) -> subprocess.Popen:
            p = subprocess.Popen([sys.executable, __file__, "worker", address],
                                 stdout=subprocess.DEVNULL, stderr=open(os.path.join(workdir, f"worker-{tag}.err"), "w"))
            procs.append(p)
            return p

        wa = spawn("A")
        rec["worker_a_pid"] = wa.pid
        await asyncio.sleep(2)
        handle = await env.client.start_workflow(ZombieWorkflow.run, db, id="gap11-zombie-wf", task_queue=TASK_QUEUE)
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                if rows(db, "SELECT phase FROM attempts WHERE attempt=1 AND phase='slow'", ("phase",)):
                    break
            except sqlite3.OperationalError:
                pass
            await asyncio.sleep(0.1)
        os.kill(wa.pid, signal.SIGSTOP)
        rec["worker_a_stopped_at"] = time.time()
        wb = spawn("B")
        rec["worker_b_pid"] = wb.pid
        rec["result"] = await asyncio.wait_for(handle.result(), 120)
        rec["workflow_completed_at"] = time.time()
        rec["effects_before_resume"] = rows(db, "SELECT key, attempt, pid FROM effects", ("key", "attempt", "pid"))
        os.kill(wa.pid, signal.SIGCONT)
        rec["worker_a_resumed_at"] = time.time()
        end = time.time() + 30
        while time.time() < end and not rows(db, "SELECT n FROM writes WHERE attempt=1", ("n",)):
            await asyncio.sleep(0.2)
        await asyncio.sleep(5)  # let worker A try to report its late completion
        desc = await handle.describe()
        rec["workflow_status_after_resume"] = str(desc.status)
        history = await handle.fetch_history()
        rec["history_events"] = len(history.events)
        rec["activity_events"] = [e.WhichOneof("attributes") for e in history.events if "activity" in (e.WhichOneof("attributes") or "")]
        replay = await Replayer(workflows=[ZombieWorkflow]).replay_workflow(history, raise_on_replay_failure=False)
        rec["replay_failure"] = None if replay.replay_failure is None else repr(replay.replay_failure)[:400]
        rec["attempts"] = rows(db, "SELECT attempt, pid, phase, at FROM attempts", ("attempt", "pid", "phase", "at"))
        rec["writes"] = rows(db, "SELECT attempt, pid, keyed_applied, at FROM writes", ("attempt", "pid", "keyed_applied", "at"))
        rec["effects"] = rows(db, "SELECT key, attempt, pid FROM effects", ("key", "attempt", "pid"))
        rec["effects_nokey"] = rows(db, "SELECT key, attempt, pid FROM effects_nokey", ("key", "attempt", "pid"))
    finally:
        for p in procs:
            try:
                os.kill(p.pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        await env.shutdown()
    rec["server_stopped"] = True
    for tag in ("A", "B"):
        text = open(os.path.join(workdir, f"worker-{tag}.err")).read()
        rec[f"worker_{tag.lower()}_log_lines_mentioning_completion_or_not_found"] = [
            ln[:300] for ln in text.splitlines() if any(s in ln.lower() for s in ("not found", "complet", "heartbeat"))][:10]
    stale = [w for w in rec["writes"] if w["attempt"] == 1]
    rec["checks"] = {
        "attempt1_on_worker_a": any(a["attempt"] == 1 and a["pid"] == rec["worker_a_pid"] for a in rec["attempts"]),
        "attempt2_on_worker_b": any(a["attempt"] >= 2 and a["pid"] == rec["worker_b_pid"] for a in rec["attempts"]),
        "result_from_worker_b": f"pid={rec['worker_b_pid']}" in rec["result"]["activity"],
        "stale_write_attempted_after_resume": bool(stale) and all(w["at"] > rec["worker_a_resumed_at"] for w in stale),
        "stale_keyed_write_refused": bool(stale) and all(w["keyed_applied"] == 0 for w in stale),
        "keyed_effect_rows": len(rec["effects"]),
        "unkeyed_control_rows": len(rec["effects_nokey"]),
        "replay_clean": rec["replay_failure"] is None,
    }
    with open(out, "w") as f:
        json.dump(rec, f, indent=2, default=str)
    return rec


def main() -> int:
    if sys.argv[1] == "worker":
        asyncio.run(run_worker(sys.argv[2]))
        return 0
    rec = asyncio.run(controller(sys.argv[2], sys.argv[3], sys.argv[4]))
    print(json.dumps(rec["checks"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
