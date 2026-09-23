#!/usr/bin/env python3
"""Tiny MLX generation smoke test for .github/workflows/hardware-profile-smoke.yml.

Runs a small pinned Hugging Face model (a specific revision SHA, not a moving
tag) through mlx-lm on an Apple Silicon runner and records tokens/s and peak
memory. This script only runs where mlx-lm is importable (macOS/Apple Silicon);
it is not exercised on Linux.

Evidence class: native_proven for the tokens/s and peak-memory numbers it
prints, measured on the exact runner it executes on (e.g. GitHub's macos-15
arm64 hosted runner). tokens_per_second and peak_memory_gb come straight from
mlx_lm.generate.stream_generate's GenerationResponse (generation_tps,
peak_memory), mlx-lm's own generation-loop timing, not a wall-clock estimate
that also bills model load/tokenizer setup/prompt prefill against a re-encoded
output length. It performs real network access to Hugging Face to fetch the
pinned model revision; there is no offline mode.
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Hugging Face repo id, e.g. mlx-community/Qwen2.5-0.5B-Instruct-4bit")
    parser.add_argument("--revision", required=True, help="Exact Hugging Face revision SHA to pin the download to")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        from mlx_lm import load
        from mlx_lm.generate import stream_generate
    except ImportError as exc:  # pragma: no cover - exercised only on macOS CI
        print(f"mlx-lm/mlx unavailable: {exc}", file=sys.stderr)
        return 1

    model, tokenizer = load(args.model, tokenizer_config={}, revision=args.revision)

    # stream_generate's GenerationResponse reports generation_tps and
    # peak_memory (GB, decimal 1e9) directly from mlx-lm's own generation
    # loop timing (mlx_lm/generate.py); this is what mlx-lm itself considers
    # the tokens/s and peak memory for a run, not a wall-clock estimate that
    # also includes model load, tokenizer setup, and prompt prefill divided
    # by a re-encoded output length.
    start = time.perf_counter()
    text = ""
    response = None
    for response in stream_generate(
        model, tokenizer, prompt=args.prompt, max_tokens=args.max_tokens,
    ):
        text += response.text
    elapsed = time.perf_counter() - start

    if response is None:
        print("mlx-lm generated no tokens", file=sys.stderr)
        return 1

    report = {
        "schema": "mlx-smoke-report-v1",
        "model": args.model,
        "revision": args.revision,
        "prompt": args.prompt,
        "max_tokens": args.max_tokens,
        "output_text": text,
        "elapsed_seconds": round(elapsed, 4),
        "prompt_tokens": response.prompt_tokens,
        "generation_tokens": response.generation_tokens,
        "tokens_per_second": round(response.generation_tps, 2),
        "peak_memory_gb": round(response.peak_memory, 3),
        "evidence_class": "native_proven",
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
