#!/usr/bin/env python3
"""Freeze snapshot for the #381 window W: CLI skeleton (failing-first commit).

This revision has the command-line surface and writes empty item lists. It collects nothing, compares nothing and checks
nothing, so tests/test_freeze_snapshot.py fails on its assertions and not on an import error. The implementation follows
in the next commit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

TOOL_VERSION = "0"
SCHEMA = "freeze-snapshot/1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="freeze_snapshot.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture")
    capture.add_argument("--label", required=True)
    capture.add_argument("--out", required=True)
    capture.add_argument("--repo")
    capture.add_argument("--config")
    capture.add_argument("--platform", choices=("linux", "darwin"))
    capture.add_argument("--no-usage-probe", action="store_true")
    compare = commands.add_parser("compare")
    compare.add_argument("first")
    compare.add_argument("second")
    compare.add_argument("--full", action="store_true")
    check = commands.add_parser("check")
    check.add_argument("capture")
    check.add_argument("--expected", required=True)
    check.add_argument("--quiet", action="store_true")
    listing = commands.add_parser("list-frozen")
    listing.add_argument("--config")
    listing.add_argument("--repo")
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "capture":
        record = {"schema": SCHEMA, "label": args.label, "items": []}
        os.makedirs(args.out, exist_ok=True)
        for name, mode in ((f"freeze-{args.label}.json", 0o600), (f"freeze-{args.label}.sanitized.json", 0o644)):
            with open(os.path.join(args.out, name), "w", encoding="utf-8") as handle:
                json.dump(record, handle)
            os.chmod(os.path.join(args.out, name), mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
