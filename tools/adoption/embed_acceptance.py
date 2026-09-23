#!/usr/bin/env python3
"""Embedding acceptance check against a Linux reference vector, stdlib only.

Round 3h (2026-09-23 readiness audit): the llama-embed launchd agent had no
model file argument at all, so nothing could ever prove a macOS run's
embedding endpoint actually serves the pinned model correctly. This sends
the EXACT request body recorded in a reference JSON (captured once, on
Linux/WSL2, against the same pinned GGUF through llama.cpp -- see
evidence/artifacts/macos-embed-reference-20260923/ and
adoption/platforms/macos-arm64.md's "Embedding backend decision") to a
running llama-server's /v1/embeddings endpoint, and checks:

  - the response embedding's dimension matches the reference's own
    ``dimension`` field;
  - the cosine similarity between the response embedding and the
    reference's own ``embedding`` is at least the reference's own
    ``acceptance.threshold`` (0.99).

Never claims Metal vs CPU by itself: the caller (a real Mac, or the hosted
macOS CI step) must record which backend llama-server's own log reports;
this script only checks the response, over plain HTTP to a local port.

Usage:
    python3 tools/adoption/embed_acceptance.py <url> <reference.json>

``url`` is the running llama-server's base URL (e.g. ``http://127.0.0.1:8232``);
this script appends the reference's own ``request.endpoint`` to it.

Exit 0 and a JSON result with "passed": true on success; exit 1 (still
printing a JSON result, with "passed": false and an "error" field where
applicable) otherwise -- a network failure, a malformed response, a
dimension mismatch or a cosine below threshold are all reported the same
way, never a bare traceback, so a CI step's own log always has the actual
numbers.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request


class AcceptanceError(RuntimeError):
    """A recoverable failure this script reports as a JSON result, not a traceback."""


def load_reference(path: str) -> dict:
    try:
        with open(path, "rb") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"could not read reference file {path}: {exc}") from exc


def post_json(url: str, body: dict, timeout: float) -> dict:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.URLError as exc:
        raise AcceptanceError(f"request to {url} failed: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AcceptanceError(f"response from {url} was not valid JSON: {exc}") from exc


def extract_embedding(response: dict) -> list[float]:
    """Handles both llama-server's OpenAI-compatible /v1/embeddings shape
    (``{"data": [{"embedding": [...]}]}``) and its native /embedding shape
    (``[{"embedding": [[...]]}]``, one row per input token pooling), since
    the exact response shape has changed across llama.cpp releases and is
    not itself a stable API this script should assume without checking."""
    node = response
    if isinstance(node, dict) and "data" in node:
        node = node["data"]
    if isinstance(node, list):
        if not node:
            raise AcceptanceError("response contained no embedding entries")
        node = node[0]
    if isinstance(node, dict) and "embedding" in node:
        node = node["embedding"]
    # Native llama.cpp /embedding can nest one more level (per-token, then
    # pooled): a list of lists collapses to its first (pooled) row.
    if isinstance(node, list) and node and isinstance(node[0], list):
        node = node[0]
    if not isinstance(node, list) or not all(isinstance(x, (int, float)) for x in node):
        raise AcceptanceError(f"could not locate a numeric embedding vector in the response: {response!r:.500}")
    return [float(x) for x in node]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise AcceptanceError(f"vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        raise AcceptanceError("a zero-norm vector cannot have a meaningful cosine similarity")
    return dot / (norm_a * norm_b)


def run(url: str, reference_path: str, timeout: float = 30.0) -> dict:
    try:
        reference = load_reference(reference_path)
        endpoint = reference["request"]["endpoint"]
        body = reference["request"]["body"]
        full_url = url.rstrip("/") + endpoint
        response = post_json(full_url, body, timeout)
        actual = extract_embedding(response)
        expected = reference["embedding"]
        expected_dimension = reference["dimension"]
        threshold = reference["acceptance"]["threshold"]
        dimension_match = len(actual) == expected_dimension
        if not dimension_match:
            return {
                "passed": False,
                "dimension_expected": expected_dimension,
                "dimension_actual": len(actual),
                "cosine": None,
                "threshold": threshold,
                "url": full_url,
                "error": f"dimension mismatch: expected {expected_dimension}, got {len(actual)}",
            }
        cosine = cosine_similarity(actual, expected)
        passed = cosine >= threshold
        result = {
            "passed": passed,
            "dimension_expected": expected_dimension,
            "dimension_actual": len(actual),
            "cosine": cosine,
            "threshold": threshold,
            "url": full_url,
        }
        if not passed:
            result["error"] = f"cosine {cosine!r} below threshold {threshold!r}"
        return result
    except AcceptanceError as exc:
        return {"passed": False, "error": str(exc), "url": url}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="Running llama-server's base URL, e.g. http://127.0.0.1:8232")
    parser.add_argument("reference", help="Path to the reference JSON (embedding, request body, threshold)")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds (default: 30)")
    args = parser.parse_args(argv)

    result = run(args.url, args.reference, args.timeout)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
