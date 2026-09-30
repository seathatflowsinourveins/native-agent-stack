#!/usr/bin/env python3
"""Transport only: wrap one retained output string for Promptfoo 0.123.1.

Source: promptfoo/promptfoo 0.123.1
site/docs/configuration/expected-outputs/index.md, standalone assertions.
Exit 0 means readable input was transported, NEVER a quality verdict. Invalid
JSON, empty outputs and wrong answers reach the unchanged upstream assertions.
"""
import json
import sys
from pathlib import Path


def transport(path):
    return [Path(path).read_bytes().decode("utf-8")]


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("one retained output file required")
        print(json.dumps(transport(sys.argv[1])))
    except (OSError, UnicodeError, ValueError):
        print("Transport unavailable; no upstream verdict", file=sys.stderr)
        raise SystemExit(2)
