#!/usr/bin/env python3
"""Temporal dev-server durability probe: forced worker kill mid-effect, restart, replay.

controller: starts a loopback Temporal dev server (temporalio.testing), starts one
workflow, launches worker process #1, waits until the activity has written its
idempotency-keyed effect row, SIGKILLs worker #1 mid-activity, launches worker #2,
awaits the result, fetches the history and replays it with Replayer (a
nondeterminism error would raise). The sqlite ledger counts activity attempts
(one row per attempt) and effects (unique by idempotency key).
worker: runs the workflow and activity against the given address.
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
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Replayer, Worker

TASK_QUEUE = "gap8-queue"


@activity.defn
async def apply_effect(args: list[str]) -> str:
    db, key = args
    info = activity.info()
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS attempts(n INTEGER PRIMARY KEY, attempt INT, pid INT, at REAL)")
    con.execute("CREATE TABLE IF NOT EXISTS effects(key TEXT PRIMARY KEY, pid INT, at REAL)")
    con.execute("INSERT INTO attempts(attempt, pid, at) VALUES (?,?,?)", (info.attempt, os.getpid(), time.time()))
    # Idempotent effect: a retried attempt with the same key cannot apply it twice.
    cur = con.execute("INSERT OR IGNORE INTO effects(key, pid, at) VALUES (?,?,?)", (key, os.getpid(), time.time()))
    applied = cur.rowcount == 1
    con.commit()
    con.close()
    if info.attempt == 1:
        await asyncio.sleep(60)  # the controller kills this worker here, after the effect write
    return f"attempt={info.attempt} applied_now={applied} pid={os.getpid()}"


@workflow.defn
class EffectWorkflow:
    @workflow.run
    async def run(self, db: str) -> dict:
        key = f"effect-{workflow.info().workflow_id}"
        first = await workflow.execute_activity(
            apply_effect, [db, key], start_to_close_timeout=timedelta(seconds=8),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=5))
        await workflow.sleep(timedelta(seconds=1))
        return {"activity": first, "key": key}


@workflow.defn(name="EffectWorkflow")
class ChangedEffectWorkflow:
    """Negative control: a timer before the activity must be flagged as nondeterministic on replay."""

    @workflow.run
    async def run(self, db: str) -> dict:
        await workflow.sleep(timedelta(seconds=5))
        key = f"effect-{workflow.info().workflow_id}"
        first = await workflow.execute_activity(
            apply_effect, [db, key], start_to_close_timeout=timedelta(seconds=8))
        return {"activity": first, "key": key}


async def run_worker(address: str) -> None:
    client = await Client.connect(address)
    async with Worker(client, task_queue=TASK_QUEUE, workflows=[EffectWorkflow], activities=[apply_effect]):
        await asyncio.Event().wait()


async def controller(workdir: str, out: str) -> dict:
    from temporalio.testing import WorkflowEnvironment
    db = os.path.join(workdir, "ledger.sqlite")
    rec: dict = {"controller_pid": os.getpid()}
    os.makedirs(os.path.join(workdir, "cli"), exist_ok=True)
    env = await WorkflowEnvironment.start_local(ip="127.0.0.1", download_dest_dir=os.path.join(workdir, "cli"),
                                                dev_server_database_filename=os.path.join(workdir, "temporal.db"))
    try:
        address = env.client.service_client.config.target_host
        rec["server_address"] = address
        handle = await env.client.start_workflow(EffectWorkflow.run, db, id="gap8-wf", task_queue=TASK_QUEUE)
        spawn = lambda: subprocess.Popen([sys.executable, __file__, "worker", address],
                                         stdout=subprocess.DEVNULL, stderr=open(os.path.join(workdir, "worker.err"), "a"))
        w1 = spawn()
        rec["worker1_pid"] = w1.pid
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                con = sqlite3.connect(db)
                n = con.execute("SELECT COUNT(*) FROM effects").fetchone()[0]
                con.close()
                if n:
                    break
            except sqlite3.OperationalError:
                pass
            await asyncio.sleep(0.2)
        os.kill(w1.pid, signal.SIGKILL)
        w1.wait()
        rec["worker1_killed_at"] = time.time()
        rec["worker1_returncode"] = w1.returncode
        w2 = spawn()
        rec["worker2_pid"] = w2.pid
        rec["result"] = await asyncio.wait_for(handle.result(), 120)
        history = await handle.fetch_history()
        events = [e for e in history.events]
        rec["history_events"] = len(events)
        rec["history_event_types"] = sorted({type(e).__name__ if False else e.WhichOneof("attributes") for e in events})
        replay = await Replayer(workflows=[EffectWorkflow]).replay_workflow(history, raise_on_replay_failure=False)
        rec["replay_failure"] = None if replay.replay_failure is None else repr(replay.replay_failure)
        control = await Replayer(workflows=[ChangedEffectWorkflow]).replay_workflow(history, raise_on_replay_failure=False)
        rec["negative_control_replay_failure"] = None if control.replay_failure is None else repr(control.replay_failure)[:400]
        w2.terminate()
        w2.wait(10)
        con = sqlite3.connect(db)
        rec["attempts"] = [dict(zip(("n", "attempt", "pid", "at"), r)) for r in con.execute("SELECT * FROM attempts")]
        rec["effects"] = [dict(zip(("key", "pid", "at"), r)) for r in con.execute("SELECT * FROM effects")]
        con.close()
    finally:
        await env.shutdown()
    rec["server_stopped"] = True
    with open(out, "w") as f:
        json.dump(rec, f, indent=2, default=str)
    return rec


def main() -> int:
    if sys.argv[1] == "worker":
        asyncio.run(run_worker(sys.argv[2]))
        return 0
    rec = asyncio.run(controller(sys.argv[2], sys.argv[3]))
    print(json.dumps({k: rec[k] for k in ("result", "replay_failure", "attempts", "effects", "history_events")}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
