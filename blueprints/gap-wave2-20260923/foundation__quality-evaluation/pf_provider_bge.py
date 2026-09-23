"""Promptfoo Python provider (fix round 2): second model, BAAI/bge-small-en-v1.5 via fastembed.

fastembed 0.8.1 serves Qdrant's quantised ONNX export of the model. Queries get
the BGE model card's retrieval instruction; passages are embedded as-is. Prints
only the prediction. No token usage is reported (local CPU inference).
"""
import json
import math
import os

from fastembed import TextEmbedding

INSTRUCTION = "Represent this sentence for searching relevant passages: "
_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = TextEmbedding("BAAI/bge-small-en-v1.5", cache_dir=os.environ["FE_CACHE_DIR"], local_files_only=True)
    return _MODEL


def _cos(a, b):
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = math.sqrt(sum(float(x) ** 2 for x in a))
    nb = math.sqrt(sum(float(y) ** 2 for y in b))
    return dot / (na * nb) if na and nb else 0.0


def call_api(prompt, options, context):
    payload = json.loads(prompt)
    m = _model()
    q = list(m.embed([INSTRUCTION + payload["query"]]))[0]
    docs = list(m.embed(payload["candidates"]))
    sims = [_cos(q, d) for d in docs]
    return {"output": f"pred={sims.index(max(sims))}"}
