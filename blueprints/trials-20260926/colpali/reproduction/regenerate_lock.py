#!/usr/bin/env python3
"""Rebuild the ColPali trial's requirements lock from environment-record.json, only on explicit request.

The trial ran with torch 2.8.0 and transformers 4.53.1, which carry known advisories that no
release inside colpali-engine 0.3.13's range fixes. The repository therefore keeps that
environment as data (environment-record.json) instead of an installable lockfile. This tool
prints the advisory ids and refuses unless called with --accept-known-advisories; then it
writes requirements-lock.txt into a new private temporary directory outside any Git work
tree, checks the bytes against the recorded size and sha256,
and prints the lock's path on standard output. Standard library only.

Exit status: 0 regenerated and identical; 1 mismatch or unusable record; 2 refused or bad usage.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

RECORD = Path(__file__).resolve().with_name("environment-record.json")
LOCK_NAME = "requirements-lock.txt"


def inside_git_work_tree(directory: Path) -> bool:
    return any((candidate / ".git").exists() for candidate in (directory, *directory.parents))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--accept-known-advisories", action="store_true",
                        help="regenerate the lock despite the recorded known advisories")
    parser.add_argument("--record", type=Path, default=RECORD, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    record = json.loads(args.record.read_text(encoding="utf-8"))
    advisories = record["known_advisories"]
    ids = [" / ".join(item["ids"]) + f" ({item['package']} {item['version']}, {item['severity']})"
           for item in advisories["advisories"]]
    print(f"{len(ids)} known advisories in this environment ({advisories['scanner_summary']}):", file=sys.stderr)
    for line in ids:
        print(f"  {line}", file=sys.stderr)
    if not args.accept_known_advisories:
        print("refusing: this environment has known vulnerabilities; rerun with --accept-known-advisories "
              "to write its lock into a temporary directory", file=sys.stderr)
        return 2
    print("WARNING: regenerating a known-vulnerable environment (torch 2.8.0, transformers 4.53.1) "
          "for trial reproduction only; install it only into a disposable, isolated environment.", file=sys.stderr)

    temp_root = Path(tempfile.gettempdir()).resolve()
    if inside_git_work_tree(temp_root):
        print("refusing: the temporary directory is inside a Git work tree", file=sys.stderr)
        return 2

    expected = record["original_lock"]
    data = "".join(item["line"] + "\n" for item in record["requirements"]).encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != expected["bytes"] or digest != expected["sha256"]:
        print(f"MISMATCH: regenerated {len(data)} bytes sha256 {digest}; record says "
              f"{expected['bytes']} bytes sha256 {expected['sha256']}; nothing written", file=sys.stderr)
        return 1
    for item in record["requirements"]:
        fields = item["line"].split()
        pin = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", fields[0])
        hashes = [field.removeprefix("--hash=") for field in fields[1:]]
        if (pin is None or pin.groups() != (item["name"], item["version"])
                or any(not field.startswith("--hash=") for field in fields[1:])
                or hashes != item["hashes"]):
            print("MISMATCH: structured requirement fields differ from the recorded line; nothing written",
                  file=sys.stderr)
            return 1

    # Python tempfile.mkdtemp provides exclusive creation and a private directory.
    # See ../../security-repair-sources.md for the upstream API references.
    target = Path(tempfile.mkdtemp(prefix="colpali-trial-lock-", dir=temp_root))
    lock = target / LOCK_NAME
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        written = lock.read_bytes()
        if written != data:
            raise OSError("written lock differs from validated bytes")
    except BaseException:
        lock.unlink(missing_ok=True)
        target.rmdir()
        raise
    print(f"regenerated {LOCK_NAME}: {len(data)} bytes, sha256 {digest} (equals the original lock)", file=sys.stderr)
    print(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
