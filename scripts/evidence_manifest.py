#!/usr/bin/env python3
"""Normalize manifests/evidence.json's files[] to sorted-by-path order.

Keeping files[] sorted by path makes independent additions in parallel PRs
land as conflict-friendly inserts instead of always colliding on the same
tail of the array. This never changes any entry's fields, and never
reorders the manifest's other top-level keys (schema_version, receipts,
files, convergence_records keep their existing order); only the files[]
list itself is reordered.

  python3 scripts/evidence_manifest.py --check   # exit 1 if files[] is out of order
  python3 scripts/evidence_manifest.py --write   # rewrite files[] in sorted order
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .catalog_decisions import safe_file, unique_json
except ImportError:
    from catalog_decisions import safe_file, unique_json


EVIDENCE = "manifests/evidence.json"


def sorted_paths(files: list) -> list[str]:
    return [entry.get("path", "") if isinstance(entry, dict) else "" for entry in files]


def is_sorted(files: list) -> bool:
    paths = sorted_paths(files)
    return paths == sorted(paths) and len(set(paths)) == len(paths)


def normalize(evidence: dict) -> dict:
    """Return a copy of evidence with files[] sorted by path; every other
    top-level key and every entry's own fields are left exactly as they are."""
    files = evidence.get("files", [])
    ordered = sorted(files, key=lambda entry: entry.get("path", "") if isinstance(entry, dict) else "")
    return {**evidence, "files": ordered}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Rewrite files[] in sorted order")
    mode.add_argument("--check", action="store_true", help="Check files[] is already sorted (default)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    path = safe_file(root, EVIDENCE)
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"{EVIDENCE}: invalid JSON ({error})")
        return 1
    files = evidence.get("files")
    if not isinstance(files, list):
        print(f"{EVIDENCE}: files must be an array")
        return 1
    if args.write:
        path.write_text(json.dumps(normalize(evidence), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "written", "files": len(files)}, sort_keys=True))
        return 0
    if not is_sorted(files):
        print(f"{EVIDENCE}: files[] is not sorted by path (or has duplicate paths); "
              "run `python3 scripts/evidence_manifest.py --write` to sort it")
        return 1
    print(json.dumps({"status": "passed", "files": len(files)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
