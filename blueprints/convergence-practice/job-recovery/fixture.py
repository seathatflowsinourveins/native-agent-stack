#!/usr/bin/env python3
"""Two deterministic local steps; no model, service or external side effects."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exclusive(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")


def source_hashes(work):
    return {name: digest(work / "source" / name) for name in ("planner.py", "test_planner.py")}


def check_source(work):
    expected = json.loads((work / "expected.json").read_text())
    if source_hashes(work) != expected:
        raise ValueError("Frozen source or oracle changed")
    return expected


def oracle(work, label):
    check_source(work)
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "-v", "test_planner"],
                            cwd=work / "source", capture_output=True, text=True, timeout=20,
                            env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    with (work / f"{label}.log").open("x", encoding="utf-8") as handle:
        handle.write(result.stdout + result.stderr)
    if result.returncode != 0 or "Ran 12 tests" not in result.stderr or not result.stderr.rstrip().endswith("OK"):
        raise ValueError("The unchanged 12-test oracle did not pass")
    check_source(work)


def verify_checkpoint(work):
    record = json.loads((work / "checkpoint.json").read_text())
    if record != {"execution_count": 1, "tests": 12, "sources": check_source(work)}:
        raise ValueError("Checkpoint content changed")
    if json.loads((work / "checkpoint-started.json").read_text()) != {"execution_count": 1}:
        raise ValueError("Checkpoint execution count changed")
    return digest(work / "checkpoint.json")


def checkpoint(work):
    # Exclusive claim precedes the oracle: a duplicate step cannot silently pass.
    exclusive(work / "checkpoint-started.json", {"execution_count": 1})
    oracle(work, "checkpoint-tests")
    exclusive(work / "checkpoint.json", {"execution_count": 1, "tests": 12, "sources": check_source(work)})


def finalize(work):
    before = verify_checkpoint(work)
    retry = (work / "release-finalize").exists()
    exclusive(work / ("retry-ready.json" if retry else "finalize-ready.json"), {"pid": os.getpid()})
    deadline = time.monotonic() + 60
    while not (work / "release-finalize").exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("Finalizer release was not supplied within 60 seconds")
        time.sleep(0.05)
    oracle(work, "final-tests")
    if verify_checkpoint(work) != before:
        raise ValueError("Checkpoint changed during finalization")
    exclusive(work / "completed.json", {"checkpoint_sha256": before, "tests": 12, "execution_count": 1})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("checkpoint", "finalize"))
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    {"checkpoint": checkpoint, "finalize": finalize}[args.action](args.work)
