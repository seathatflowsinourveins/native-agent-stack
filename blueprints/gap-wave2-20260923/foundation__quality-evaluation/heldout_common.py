"""Shared held-out retrieval logic for the Promptfoo and Inspect harnesses.

Both harnesses import this module, so they send byte-identical inputs to the
same endpoint. The system under test sees only the query and candidates; the
label stays with the harness (Promptfoo test vars, Inspect Target).
"""
import json
import math
import random
import urllib.request

URL = "http://127.0.0.1:8231/v2/embed"
MODEL = "nvidia/Nemotron-3-Embed-1B-BF16"


def load_cases(path):
    """Return [(payload_json, label)] with a seed-42 candidate shuffle."""
    rng = random.Random(42)
    rows = []
    for case in json.load(open(path)):
        candidates = [case["correct"]] + case["distractors"]
        order = list(range(4))
        rng.shuffle(order)
        payload = {"query": case["query"], "candidates": [candidates[j] for j in order]}
        rows.append((json.dumps(payload, sort_keys=True), order.index(0)))
    return rows


def embed(texts):
    body = json.dumps({"model": MODEL, "texts": texts}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["embeddings"]["float"], int(data["meta"]["billed_units"]["input_tokens"])


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def predict(payload_json):
    """Return (predicted index, billed input tokens) for one payload."""
    payload = json.loads(payload_json)
    vecs, tokens = embed([payload["query"]] + payload["candidates"])
    sims = [cosine(vecs[0], v) for v in vecs[1:]]
    return sims.index(max(sims)), tokens


# Fix round 2: the model card's call. predict() above is unchanged, because the
# gap-4 harness comparison used it; predict_typed() is the recommended form from
# the pinned NVIDIA card (retained upstream-example.py): queries and documents in
# separate requests with input_type "query" / "document".
def embed_typed(input_type, texts):
    body = json.dumps({"model": MODEL, "input_type": input_type, "texts": texts,
                       "embedding_types": ["float"], "truncate": "END"}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["embeddings"]["float"], int(data["meta"]["billed_units"]["input_tokens"])


def predict_typed(payload_json):
    """Return (predicted index, billed input tokens) using the model card's input types."""
    payload = json.loads(payload_json)
    qv, qt = embed_typed("query", [payload["query"]])
    dv, dt = embed_typed("document", payload["candidates"])
    sims = [cosine(qv[0], v) for v in dv]
    return sims.index(max(sims)), qt + dt
