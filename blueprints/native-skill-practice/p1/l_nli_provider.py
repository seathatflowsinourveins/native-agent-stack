"""Arm L: a local three-class NLI checkpoint as a promptfoo 0.123.1 Python provider (skeleton).

Report r1 section 5.1, "Arm L" row: one of the two candidates below, named and hashed at freeze,
both loaded without custom code; entailment maps to supported, contradiction to contradicted and
neutral to insufficient. Labels are mapped by the checkpoint's own id2label names, never by index,
because the two candidates order their classes differently. The premise is the excerpt and the
hypothesis is the claim; when the pair exceeds the model's maximum length only the premise is
truncated, and the result says so, because L then saw less than the other arms.

This file imports torch and transformers only inside call_api and refuses to run until the config
names a listed checkpoint and its full 40-hex revision. Nothing here has been run.
"""

from __future__ import annotations

import re
import time

CANDIDATES = {
    # checkpoint: revision prefix recorded in report r1 section 5.1 (re-read 2026-10-03)
    "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli": "b3546ea6",
    "cross-encoder/nli-deberta-v3-large": "bab4bc71",
}
MAPPING = {"entailment": "supported", "contradiction": "contradicted", "neutral": "insufficient"}
LABELS = ("supported", "contradicted", "insufficient")
MAX_LENGTH = 512
_LOADED: dict = {}


def frozen_choice(config: dict) -> tuple[str, str] | None:
    checkpoint, revision = config.get("checkpoint"), config.get("revision")
    if checkpoint not in CANDIDATES or not isinstance(revision, str):
        return None
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or not revision.startswith(CANDIDATES[checkpoint]):
        return None
    return checkpoint, revision


def _load(checkpoint: str, revision: str):
    key = (checkpoint, revision)
    if key not in _LOADED:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(checkpoint, revision=revision, trust_remote_code=False)
        model = AutoModelForSequenceClassification.from_pretrained(checkpoint, revision=revision,
                                                                   trust_remote_code=False)
        model.eval()
        names = {name.lower() for name in model.config.id2label.values()}
        if names != set(MAPPING):
            raise RuntimeError(f"unexpected NLI labels {sorted(names)}")
        _LOADED[key] = (tokenizer, model)
    return _LOADED[key]


def call_api(prompt, options, context):
    config = (options or {}).get("config") or {}
    choice = frozen_choice(config)
    if choice is None:
        return {"error": "arm L is not frozen: set a listed checkpoint and its full 40-hex revision"}
    variables = (context or {}).get("vars") or {}
    premise, hypothesis = variables.get("source"), variables.get("claim")
    if not isinstance(premise, str) or not isinstance(hypothesis, str):
        return {"error": "arm L needs the source and claim vars"}
    import torch

    tokenizer, model = _load(*choice)
    full = tokenizer(premise, hypothesis, truncation=False)["input_ids"]
    inputs = tokenizer(premise, hypothesis, truncation="only_first", max_length=MAX_LENGTH, return_tensors="pt")
    started = time.monotonic()
    with torch.no_grad():
        logits = model(**inputs).logits[0]
    elapsed = time.monotonic() - started
    probabilities_by_name = {model.config.id2label[index].lower(): float(value)
                             for index, value in enumerate(torch.softmax(logits, dim=-1).tolist())}
    probabilities = {MAPPING[name]: probabilities_by_name[name] for name in MAPPING}
    answer = max(LABELS, key=lambda label: (probabilities[label], -LABELS.index(label)))
    return {
        "output": answer,
        "metadata": {"model": choice[0], "revision": choice[1], "probabilities": probabilities,
                     "confidence": probabilities[answer], "inference": "live",
                     "truncated": len(full) > MAX_LENGTH, "input_tokens": len(full), "compute_s": elapsed},
    }
