#!/usr/bin/env python3
"""Exact oracle, frozen before provider execution. Synthetic fixture evidence only.

Reference: Crawl4AI v0.9.4 docs/examples/llm_extraction_openai_pricing.py's
schema extraction output; docs/acceptance-evidence-policy.md's negative control.
"""
import json
import sys
from pathlib import Path


def canonical(payload):
    if not isinstance(payload, dict) or set(payload) != {"records"}:
        raise ValueError("expected records envelope")
    rows = payload["records"]
    if not isinstance(rows, list) or len(rows) != 3 or not all(isinstance(row, dict) for row in rows):
        raise ValueError("expected three records")
    # Sorting only removes page-completion ordering; no values are normalized.
    rows = sorted(rows, key=lambda row: row["sku"])
    return json.dumps(rows, sort_keys=True, allow_nan=False, separators=(",", ":"))


def check(path):
    try:
        expected = json.loads((Path(__file__).parent / "expected.json").read_text())
        return canonical(json.loads(Path(path).read_text())) == canonical(expected)
    except (OSError, ValueError, KeyError, TypeError):
        return False


if __name__ == "__main__":
    passed = len(sys.argv) == 2 and check(sys.argv[1])
    print("PASS: all 18 fields match exactly" if passed else "FAIL: expected three exact product records")
    raise SystemExit(0 if passed else 1)
