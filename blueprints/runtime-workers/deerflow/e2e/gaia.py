"""Inspect Evals v0.22.0 GAIA task with a DeerFlow transport solver.

References: inspect_evals/gaia/gaia.py; Inspect AI 0.3.271 docs/solvers.qmd.
The upstream dataset, prompt, scorer and metrics are retained. No local verdict.
Only no-attachment validation IDs are supported by this bounded transport.
"""
import asyncio
import sys
from pathlib import Path

from inspect_ai import task
from inspect_ai.model import ModelOutput
from inspect_ai.solver import solver
from inspect_evals.gaia import gaia

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import run_worker


@solver
def deerflow():
    async def solve(state, generate):
        result = await asyncio.to_thread(run_worker, state.input_text, str(state.sample_id), state.epoch)
        state.output = ModelOutput.from_content(model=result["model"], content=result["completion"])
        state.metadata["deerflow_observation"] = result["receipt"]
        state.completed = True
        return state

    return solve


@task
def deerflow_gaia(instance_ids: str | list[str]):
    ids = [instance_ids] if isinstance(instance_ids, str) else instance_ids
    if not ids or any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("freeze nonempty, unique GAIA validation instance IDs before running")
    result = gaia(instance_ids=ids, split="validation", solver=deerflow())
    # Public Task.sandbox attribute. The custom worker owns its own labeled Docker
    # container; Inspect must not create the default GAIA Docker sandbox too.
    result.sandbox = None
    if {str(sample.id) for sample in result.dataset} != set(ids):
        raise ValueError("one or more frozen IDs are absent from GAIA validation")
    if any(sample.files for sample in result.dataset):
        raise ValueError("GAIA attachment staging is pending; select frozen no-attachment IDs")
    return result
