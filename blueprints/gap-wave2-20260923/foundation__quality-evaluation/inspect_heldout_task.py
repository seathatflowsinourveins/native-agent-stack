"""Inspect AI task over the same frozen held-out cases as the Promptfoo run.

The solver sees only the payload; the scorer compares with the Sample target.
Billed endpoint tokens are stored per sample in Score metadata because no
Inspect model provider is involved (Inspect's own model_usage stays empty).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heldout_common import load_cases, predict  # noqa: E402

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import Generate, TaskState, solver


@solver
def embed_retrieve():
    async def solve(state: TaskState, generate: Generate):
        pred, tokens = predict(state.input_text)
        state.output.completion = str(pred)
        state.metadata["billed_input_tokens"] = tokens
        return state
    return solve


@scorer(metrics=[accuracy()])
def exact_index_match():
    async def score(state: TaskState, target: Target):
        pred = state.output.completion.strip()
        return Score(value=1.0 if pred == target.text else 0.0, answer=pred,
                     metadata={"billed_input_tokens": state.metadata.get("billed_input_tokens")})
    return score


@task
def heldout_retrieval(cases: str = "cases.json"):
    rows = load_cases(cases)
    return Task(
        dataset=[Sample(input=p, target=str(lab), id=f"case-{i:02d}") for i, (p, lab) in enumerate(rows)],
        solver=embed_retrieve(),
        scorer=exact_index_match(),
    )
