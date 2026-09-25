#!/usr/bin/env python3
"""Re-run the Nemotron-3-Embed-1B model-card retrieval check against a live vLLM server.

This repeats the example-level qualification recorded on 2026-09-21
(docs/hf-memory-model-qualification.md, evidence/receipts/hf-memory-models-20260921.json)
on another host. It sends read-only HTTP requests to the server and prints a
compact summary. It never starts, stops or configures a server.

Modes:
  v2          Extract NVIDIA's "Recommended Retrieval Endpoint" example from the
              served model directory's README.md, check both sha256 values, change
              only the URL, run it with this interpreter, and check the printed
              matrix: every query ranks its intended document first, and the
              largest difference from the card's printed expected output is at
              most --tolerance.
  v1          Send the same queries and documents to /v1/embeddings with the
              card's "query: " and "passage: " prefixes. Check 8 vectors, 2048
              dimensions, unit norms, intended-first ranking, and the largest
              difference from the 2026-09-21 laptop scores.
  v1-rotated  Discriminating control: the v1 check with the documents rotated by
              one. The ranking assertion must fail (0/4 intended first). This mode
              exits 0 only when it does fail.

Exit 0 when the mode's bars hold, 1 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

MODEL = "nvidia/Nemotron-3-Embed-1B-BF16"
CARD_SHA256 = "6e811480c966ca54fca9a5cbd0e5ae60df15244bfc70bb9db155c2b92fa23f8e"
EXAMPLE_SHA256 = "09df5e6a97308b18b576f6ab29e8c652ee67a81b5ecc9390f00219edc8d3aa32"
CARD_URL = "http://localhost:8000/v2/embed"
REPO = Path(__file__).resolve().parents[4]
LAPTOP_RESULTS = REPO / "evidence/artifacts/hf-memory-models-20260921/native-results.json"


def served_root(base: str) -> Path:
    with urllib.request.urlopen(base + "/v1/models", timeout=10) as response:
        model = json.load(response)["data"][0]
    if model["id"] != MODEL:
        raise SystemExit("served model is " + model["id"])
    return Path(model["root"])


def card_text(root: Path) -> str:
    raw = (root / "README.md").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CARD_SHA256:
        raise SystemExit("README.md sha256 differs from the reviewed revision")
    return raw.decode("utf-8")


def example_and_expected(card: str) -> tuple[str, list[list[float]]]:
    section = card.split("#### Recommended Retrieval Endpoint", 1)[1]
    code = re.search(r"```python\n(.*?)```", section, re.S).group(1)
    if hashlib.sha256(code.encode()).hexdigest() != EXAMPLE_SHA256:
        raise SystemExit("example code sha256 differs from the reviewed revision")
    expected_block = re.search(r"```text\n(.*?)```", section, re.S).group(1)
    return code, parse_matrix(expected_block)


def parse_matrix(text: str) -> list[list[float]]:
    return [[float(x) for x in line.split()[1:]] for line in text.splitlines() if line.startswith("q[")]


def ranking(matrix) -> list[int]:
    return [row.index(max(row)) for row in matrix]


def max_delta(a, b) -> float:
    return max(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra, rb))


def card_inputs(code: str) -> tuple[list[str], list[str]]:
    namespace: dict = {}
    body = code.split("def embed", 1)[0]
    exec(compile(body.replace("import numpy as np\nimport requests\n", ""), "card", "exec"), namespace)
    return namespace["QUERIES"], namespace["DOCUMENTS"]


def run_v2(base: str, tolerance: float) -> int:
    code, expected = example_and_expected(card_text(served_root(base)))
    if code.count(CARD_URL) != 1:
        raise SystemExit("the card URL does not appear exactly once")
    executed = code.replace(CARD_URL, base + "/v2/embed")
    result = subprocess.run([sys.executable, "-I", "-c", executed], capture_output=True, text=True,
                            timeout=180)
    observed = parse_matrix(result.stdout)
    order = ranking(observed) if len(observed) == 4 else None
    delta = max_delta(observed, expected) if order is not None else None
    ok = result.returncode == 0 and order == [0, 1, 2, 3] and delta <= tolerance
    print(json.dumps({"route": "/v2/embed", "example_exit": result.returncode,
                      "executed_sha256": hashlib.sha256(executed.encode()).hexdigest()[:16],
                      "scores": observed, "top": order,
                      "max_abs_delta_to_card_expected": None if delta is None else round(delta, 4),
                      "tolerance": tolerance, "pass": ok}, separators=(",", ":")))
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-2000:])
    return 0 if ok else 1


def v1_scores(base: str, queries, documents):
    texts = ["query: " + q for q in queries] + ["passage: " + d for d in documents]
    request = urllib.request.Request(base + "/v1/embeddings",
                                     data=json.dumps({"model": MODEL, "input": texts}).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    vectors = [item["embedding"] for item in sorted(payload["data"], key=lambda item: item["index"])]
    norms = [math.sqrt(sum(x * x for x in v)) for v in vectors]
    unit = [[x / n for x in v] for v, n in zip(vectors, norms)]
    q, d = unit[:len(queries)], unit[len(queries):]
    scores = [[sum(x * y for x, y in zip(qv, dv)) for dv in d] for qv in q]
    return vectors, norms, scores, payload.get("usage", {}).get("prompt_tokens")


def run_v1(base: str, tolerance: float, rotated: bool) -> int:
    code, _ = example_and_expected(card_text(served_root(base)))
    queries, documents = card_inputs(code)
    if rotated:
        documents = documents[1:] + documents[:1]
    vectors, norms, scores, tokens = v1_scores(base, queries, documents)
    laptop = json.loads(LAPTOP_RESULTS.read_text())["derived_observations"]["vector_checks"]["v1_similarity_scores"]
    order = ranking(scores)
    intended_first = sum(1 for i, top in enumerate(order) if top == i)
    dims = sorted({len(v) for v in vectors})
    norm_ok = all(abs(n - 1.0) <= 1e-5 for n in norms)
    summary = {"route": "/v1/embeddings", "documents": "rotated by one" if rotated else "card order",
               "vectors": len(vectors), "dims": dims, "prompt_tokens": tokens,
               "norm_range": [round(min(norms), 7), round(max(norms), 7)],
               "scores": [[round(x, 4) for x in row] for row in scores], "top": order,
               "intended_first": f"{intended_first}/4"}
    if rotated:
        ranking_ok = intended_first == 4
        summary["ranking_assertion"] = "pass" if ranking_ok else "fail"
        summary["control_as_expected"] = not ranking_ok
        print(json.dumps(summary, separators=(",", ":")))
        return 0 if not ranking_ok else 1
    delta = max_delta(scores, laptop)
    summary["max_abs_delta_to_laptop_20260921"] = round(delta, 4)
    summary["tolerance"] = tolerance
    ok = len(vectors) == 8 and dims == [2048] and norm_ok and intended_first == 4 and delta <= tolerance
    summary["pass"] = ok
    print(json.dumps(summary, separators=(",", ":")))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("v2", "v1", "v1-rotated"))
    parser.add_argument("--base", default="http://127.0.0.1:18231")
    parser.add_argument("--tolerance", type=float, default=0.005)
    args = parser.parse_args()
    if args.mode == "v2":
        return run_v2(args.base, args.tolerance)
    return run_v1(args.base, args.tolerance, rotated=args.mode == "v1-rotated")


if __name__ == "__main__":
    raise SystemExit(main())
