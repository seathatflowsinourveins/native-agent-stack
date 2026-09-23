#!/usr/bin/env python3
"""Temporal port of the frozen job-recovery fixture (temporalio 1.33.0).

Workflow `Recovery(work)`: activity `checkpoint` (exactly one attempt allowed, so a
re-execution would surface as a failure) then activity `finalize` (heartbeats every
0.5 s; heartbeat timeout 5 s; up to 5 attempts). Each activity runs the unchanged
fixture as a subprocess: `python3 -B WORK/fixture.py <action> WORK`.

Temporal cannot stop an arbitrary subprocess by itself: on activity cancellation this
adapter terminates the fixture subprocess (recorded as harness-assisted in the result).

Usage: temporal_worker.py ADDRESS TASK_QUEUE FIXTURE_PYTHON
"""

import asyncio
from datetime import timedelta
import subprocess
import sys

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

FIXTURE_PYTHON = sys.argv[3] if len(sys.argv) > 3 else "/usr/bin/python3"


async def run_fixture(action, work):
    proc = subprocess.Popen([FIXTURE_PYTHON, "-B", f"{work}/fixture.py", action, work],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        while proc.poll() is None:
            activity.heartbeat(action)
            await asyncio.sleep(0.5)
    except (asyncio.CancelledError, Exception):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        raise
    output = proc.stdout.read().decode(errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"fixture {action} exited {proc.returncode}: {output[-400:]}")
    return action


@activity.defn(name="checkpoint")
async def checkpoint(work: str) -> str:
    return await run_fixture("checkpoint", work)


@activity.defn(name="finalize")
async def finalize(work: str) -> str:
    return await run_fixture("finalize", work)


@workflow.defn(name="Recovery")
class Recovery:
    @workflow.run
    async def run(self, work: str) -> str:
        await workflow.execute_activity(
            "checkpoint", work, start_to_close_timeout=timedelta(seconds=60),
            heartbeat_timeout=timedelta(seconds=5), retry_policy=RetryPolicy(maximum_attempts=1),
            cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED)
        await workflow.execute_activity(
            "finalize", work, start_to_close_timeout=timedelta(seconds=150),
            heartbeat_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=1)),
            cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED)
        return "completed"


async def main():
    client = await Client.connect(sys.argv[1])
    worker = Worker(client, task_queue=sys.argv[2], workflows=[Recovery], activities=[checkpoint, finalize])
    print("worker-ready", flush=True)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
