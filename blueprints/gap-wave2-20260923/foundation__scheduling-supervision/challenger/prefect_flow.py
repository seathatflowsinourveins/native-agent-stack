#!/usr/bin/env python3
"""Prefect 3.8.6 port of the frozen job-recovery fixture.

Flow `recovery(work)`: task `checkpoint` (persisted result, default cache policy, no
retries) then task `finalize` (no cache). Each runs the unchanged fixture as a
subprocess: `python3 -B WORK/fixture.py <action> WORK`. Executed through the native
`flow.serve()` runner so `prefect flow-run cancel` and `prefect flow-run retry` apply.

Usage: prefect_flow.py   (serves the deployment `recovery/recovery-deploy`)
"""

import subprocess

from prefect import flow, task
from prefect.cache_policies import NO_CACHE

FIXTURE_PYTHON = "/usr/bin/python3"


def run_fixture(action, work):
    result = subprocess.run([FIXTURE_PYTHON, "-B", f"{work}/fixture.py", action, work],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"fixture {action} exited {result.returncode}: {(result.stdout + result.stderr)[-400:]}")
    return action


@task(name="checkpoint", persist_result=True, retries=0)
def checkpoint(work: str) -> str:
    return run_fixture("checkpoint", work)


@task(name="finalize", persist_result=False, retries=0, cache_policy=NO_CACHE)
def finalize(work: str) -> str:
    return run_fixture("finalize", work)


@flow(name="recovery", persist_result=True)
def recovery(work: str) -> str:
    checkpoint(work)
    finalize(work)
    return "completed"


if __name__ == "__main__":
    recovery.serve(name="recovery-deploy")
