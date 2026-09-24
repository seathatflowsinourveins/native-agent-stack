#!/usr/bin/env python3
"""Small Prefect client helper: `trigger WORK` prints a new flow-run id for the served
deployment; `state ID` prints the flow run's state and its task runs as JSON."""

import asyncio
import json
import sys
from uuid import UUID

from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.deployments import run_deployment


async def state(run_id):
    async with get_client() as client:
        run = await client.read_flow_run(UUID(run_id))
        tasks = await client.read_task_runs(flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[UUID(run_id)])))
        return {"flow_run_id": run_id, "state_type": run.state.type.value if run.state else None,
                "state_name": run.state.name if run.state else None, "run_count": run.run_count,
                "task_runs": sorted([{"name": t.name, "state_type": t.state.type.value if t.state else None,
                                      "state_name": t.state.name if t.state else None, "run_count": t.run_count}
                                     for t in tasks], key=lambda t: t["name"])}


if __name__ == "__main__":
    if sys.argv[1] == "trigger":
        run = run_deployment("recovery/recovery-deploy", parameters={"work": sys.argv[2]}, timeout=0)
        print(json.dumps({"flow_run_id": str(run.id)}))
    else:
        print(json.dumps(asyncio.run(state(sys.argv[2]))))
