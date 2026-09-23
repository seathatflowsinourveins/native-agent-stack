"""Arm 2: inspect-ai 0.3.266 mock-model task over the frozen 8-case catalog pack.

No provider is called. The model is inspect's built-in mockllm/model with a
callable that evaluates the promptfoo echo provider's exact-text transform
(read verbatim from promptfooconfig.yaml). The scorer runs the unmodified
gate.cjs and the same three promptfoo assertion expressions via node.
"""
import asyncio
import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput, ModelUsage, get_model
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer
from inspect_ai.solver import Generate, TaskState, generate, solver

HERE = Path(__file__).resolve().parent
PRACTICE = HERE.parents[2] / "native-skill-practice"
CASES = PRACTICE / "catalog-cases.json"
CONFIG = PRACTICE / "promptfooconfig.yaml"
BRIDGE = HERE / "bridge.cjs"
FROZEN_CASES_SHA256 = "7cc28c50afb9842de3d8dc923e80159bf99d0f0e9acd643684a99b61b3ad3a40"
NODE = os.environ.get("ARM2_NODE", "node")


def _config():
    return yaml.safe_load(CONFIG.read_text())


def _bridge(request):
    done = subprocess.run([NODE, str(BRIDGE)], input=json.dumps(request), capture_output=True,
                          text=True, timeout=30, check=True)
    return json.loads(done.stdout)


def _render(vars_):
    # promptfoo prompt template: '{"source": {{ source | dump }}, "claim": {{ claim | dump }}}'
    return json.dumps({"source": vars_["source"], "claim": vars_["claim"]}, ensure_ascii=False)


def _samples():
    raw = CASES.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_CASES_SHA256:
        raise ValueError("frozen catalog-cases.json hash mismatch")
    defaults = _config()["defaultTest"]["vars"]
    samples = []
    for case in json.loads(raw):
        vars_ = {**defaults, **case["vars"]}
        samples.append(Sample(id=case["metadata"]["case_id"], input=_render(vars_),
                              target=vars_["expected"], metadata={"vars": vars_,
                              "description": case["description"]}))
    return samples


def exact_text_baseline(messages, tools, tool_choice, config):
    """mockllm custom_outputs callable: the promptfoo echo transform, evaluated by node."""
    prompt = json.loads(messages[-1].text)
    expr = next(p for p in _config()["providers"] if p.get("label") == "exact-text-baseline-v1")["transform"]
    verdict = _bridge({"mode": "baseline", "expr": expr, "vars": prompt})["output"]
    output = ModelOutput.from_content(model="mockllm/model", content=verdict)
    output.usage = ModelUsage(input_tokens=0, output_tokens=0, total_tokens=0)
    return output


@solver
def fault_and_delay(delay: float = 0.0, fail_once_case: str = "", marker_dir: str = ""):
    """Test-only hooks: a per-sample delay (interrupt/resume check) and a one-shot injected error."""
    async def solve(state: TaskState, generate_fn: Generate) -> TaskState:
        if delay:
            await asyncio.sleep(delay)
        if fail_once_case and state.sample_id == fail_once_case:
            marker = Path(marker_dir) / f"{fail_once_case}.failed-once"
            if not marker.exists():
                marker.write_text("1")
                raise RuntimeError(f"injected transient failure for {fail_once_case} (first attempt)")
        return state
    return solve


@scorer(metrics=[accuracy()])
def promptfoo_equivalent_assertions():
    async def score(state: TaskState, target: Target) -> Score:
        cfg = _config()
        asserts = [a["value"] for a in cfg["defaultTest"]["assert"]]
        vars_ = state.metadata["vars"]
        result = _bridge({"mode": "score", "vars": vars_, "output": state.output.completion,
                          "asserts": asserts})
        if "gate_error" in result:
            return Score(value=INCORRECT, answer=state.output.completion,
                         explanation="gate error: " + result["gate_error"], metadata=result)
        failed = [r for r in result["results"] if not r["pass"]]
        return Score(value=CORRECT if not failed else INCORRECT, answer=state.output.completion,
                     explanation="; ".join(f"FAILED {r['value']}" for r in failed) or "all 3 assertions passed",
                     metadata={"gated": json.loads(result["gated"]), "assertions": result["results"]})
    return score


@task
def catalog_cases(delay: float = 0.0, fail_once_case: str = "", marker_dir: str = ""):
    return Task(
        dataset=_samples(),
        solver=[fault_and_delay(delay, fail_once_case, marker_dir), generate()],
        scorer=promptfoo_equivalent_assertions(),
        model=get_model("mockllm/model", custom_outputs=exact_text_baseline),
    )
