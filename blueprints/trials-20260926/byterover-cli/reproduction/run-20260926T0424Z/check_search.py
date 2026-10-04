#!/usr/bin/env python3
"""Check one retained `brv search --format json` output against an explicit expectation.

Usage: check_search.py <search-output.json> --total N [--path PATH --text TEXT]

Passes (exit 0) only when the file holds exactly one JSON object whose `success` is true,
whose `data.status` is "completed", whose `data.totalFound` is the integer N, whose
`data.results` has N entries and, when --path is given, whose first result has that exact
`path` and an `excerpt` containing TEXT. Otherwise exits 1 and names each failed condition.

`brv search` submits a daemon task and reports a failed task as `"success": false` without a
failing exit code (src/oclif/commands/search.ts at v3.16.1), so the process exit code alone
is not evidence. This checker is local integration glue around the retained native output.
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--path")
    parser.add_argument("--text")
    args = parser.parse_args()
    failures: list[str] = []
    try:
        with open(args.output, encoding="utf-8") as handle:
            document = json.loads(handle.read())
    except (OSError, ValueError) as error:
        print(json.dumps({"output": args.output, "pass": False, "failures": [f"unreadable JSON: {error}"]}))
        return 1
    data = document.get("data") if isinstance(document, dict) else None
    data = data if isinstance(data, dict) else {}
    results = data.get("results") if isinstance(data.get("results"), list) else []
    total = data.get("totalFound")
    if document.get("success") is not True:
        failures.append(f"success is {document.get('success')!r}, expected true")
    if data.get("status") != "completed":
        failures.append(f"data.status is {data.get('status')!r}, expected 'completed'")
    if type(total) is not int or total != args.total:
        failures.append(f"data.totalFound is {total!r}, expected exactly {args.total}")
    if len(results) != args.total:
        failures.append(f"{len(results)} results returned, expected {args.total}")
    first = results[0] if results and isinstance(results[0], dict) else {}
    if args.path is not None and first.get("path") != args.path:
        failures.append(f"first result path is {first.get('path')!r}, expected {args.path!r}")
    if args.text is not None and args.text not in str(first.get("excerpt", "")):
        failures.append(f"first result excerpt does not contain {args.text!r}")
    verdict = {
        "output": args.output,
        "expected": {"total": args.total, "path": args.path, "text": args.text},
        "observed": {"success": document.get("success"), "status": data.get("status"), "totalFound": total,
                     "paths": [item.get("path") for item in results if isinstance(item, dict)]},
        "pass": not failures,
        "failures": failures,
    }
    print(json.dumps(verdict))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
