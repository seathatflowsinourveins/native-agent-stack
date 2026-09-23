#!/usr/bin/env python3
"""Tiny MLX generation smoke test for .github/workflows/hardware-profile-smoke.yml.

Runs a small pinned Hugging Face model (a specific revision SHA, not a moving
tag) through mlx-lm on an Apple Silicon runner and records tokens/s and peak
memory. This script only runs where mlx-lm is importable (macOS/Apple Silicon);
it is not exercised on Linux.

Evidence class: native_proven for the tokens/s and peak-memory numbers it
prints, measured on the exact runner it executes on (e.g. GitHub's macos-15
arm64 hosted runner). It performs real network access to Hugging Face to fetch
the pinned model revision; there is no offline mode.
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
        import mlx.core as mx
        from mlx_lm import load, generate
    except ImportError as exc:  # pragma: no cover - exercised only on macOS CI
        print(f"mlx-lm/mlx unavailable: {exc}", file=sys.stderr)
        return 1

    model, tokenizer = load(args.model, tokenizer_config={}, revision=args.revision)

    start = time.perf_counter()
    text = generate(
        model, tokenizer, prompt=args.prompt, max_tokens=args.max_tokens, verbose=False,
    )
    elapsed = time.perf_counter() - start

    # generate() consumes the prompt plus up to max_tokens generated tokens;
    # report generated-token throughput using the requested ceiling as an
    # upper-bound estimate when the exact generated count is not exposed by
    # this mlx-lm version's return type (a plain string).
    generated_tokens = len(tokenizer.encode(text)) if isinstance(text, str) else args.max_tokens
    tokens_per_second = generated_tokens / elapsed if elapsed > 0 else 0.0
    peak_memory_gb = round(mx.get_peak_memory() / (1024.0 ** 3), 3) if hasattr(mx, "get_peak_memory") else None

    report = {
        "schema": "mlx-smoke-report-v1",
        "model": args.model,
        "revision": args.revision,
        "prompt": args.prompt,
        "max_tokens": args.max_tokens,
        "output_text": text,
        "elapsed_seconds": round(elapsed, 4),
        "tokens_per_second": round(tokens_per_second, 2),
        "peak_memory_gb": peak_memory_gb,
        "evidence_class": "native_proven",
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
