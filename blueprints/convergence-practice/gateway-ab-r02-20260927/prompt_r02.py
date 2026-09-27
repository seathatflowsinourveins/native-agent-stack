"""promptfoo Python prompt function for R02: li26's own prompt for one filing.

promptfoo calls `build_prompt(context)` with the test's vars (promptfoo@0.123.1:
site/docs/configuration/prompts.md:222-238; src/evaluatorHelpers.ts:396-397). The text comes from li26's
code, not a copy: eval_arm.prompt_template(eval_arm.load_plan()) enforces li26's frozen plan and prompt
sha256, and MARKER is replaced once with the filing input, as eval_arm.build_request does. The result must
match the prompt_sha256 that build_r02.py recorded for this filing, otherwise the call is never sent.
"""
import hashlib
import importlib.util
from pathlib import Path

LI26 = Path(__file__).resolve().parent.parent / "local-inference-latest-20260926"
_EVAL_ARM = []


def _eval_arm():
    if not _EVAL_ARM:
        spec = importlib.util.spec_from_file_location("r02_prompt_li26_eval_arm", LI26 / "eval_arm.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _EVAL_ARM.append(module)
    return _EVAL_ARM[0]


def build_prompt(context):
    eval_arm = _eval_arm()
    variables = context["vars"]
    text = eval_arm.prompt_template(eval_arm.load_plan()).replace(eval_arm.MARKER, variables["document"], 1)
    if hashlib.sha256(text.encode()).hexdigest() != variables["prompt_sha256"]:
        raise ValueError(f"{variables.get('accession')}: prompt differs from the one recorded for this filing")
    return text
