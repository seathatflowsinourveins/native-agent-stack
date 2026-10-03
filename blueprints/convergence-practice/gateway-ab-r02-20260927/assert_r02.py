"""promptfoo Python assertion for R02: li26's own parser and per-filing scorer.

promptfoo calls `get_assert(output, context)` and reads a GradingResult dict with `pass`, `score`, `reason`
and `namedScores` (promptfoo@0.123.1:site/docs/configuration/expected-outputs/python.md:119-210). Scoring is
li26's: eval_arm.parse_items (valid, fenced_valid or invalid) and analyze.filing_scores (TP/FP/FN). Loading
li26's analyze.py only runs its imports and loads eval_arm.py (analyze.py:23-31). Pass means parse_items
returned items (valid or fenced_valid, both of which li26 scores) and promptfoo's rendered prompt is the one
recorded for this filing. li26's parse status is a separate named score; it is not strict-schema validity, which
the configs' second assertion, promptfoo's is-json with the schema the request sends, decides (build_r02.config).
"""
import hashlib
import importlib.util
import json
from pathlib import Path

LI26 = Path(__file__).resolve().parent.parent / "local-inference-latest-20260926"
STATUSES = ("valid", "fenced_valid", "invalid")
_ANALYZE = []


def _analyze():
    if not _ANALYZE:
        spec = importlib.util.spec_from_file_location("r02_assert_li26_analyze", LI26 / "analyze.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ANALYZE.append(module)
    return _ANALYZE[0]


def get_assert(output, context):
    analyze = _analyze()
    variables = context["vars"]
    gold = json.loads(variables["labels_json"])
    predicted, status = analyze.eval_arm.parse_items(output)
    scores = analyze.filing_scores(gold, predicted)
    prompt = context.get("prompt")
    prompt_ok = isinstance(prompt, str) and \
        hashlib.sha256(prompt.encode()).hexdigest() == variables["prompt_sha256"]
    named = {"tp": scores["tp"], "fp": scores["fp"], "fn": scores["fn"], "prompt_ok": int(prompt_ok)}
    named.update({f"status_{name}": int(status == name) for name in STATUSES})
    return {"pass": predicted is not None and prompt_ok, "score": scores["f1"],
            "reason": f"parse={status}; prompt={'ok' if prompt_ok else 'mismatch'}", "namedScores": named}
