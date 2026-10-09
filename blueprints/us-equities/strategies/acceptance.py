"""Generate the source-bound T22 behaviour receipt in the exact T13 rc5 runtime.

Runs only this repository's synthetic suite; it does not install, sync, acquire
data or contact a broker. The companion simulation module generates the matrix.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if importlib.metadata.version("nautilus-trader") != "2.0.0rc5":
        raise ValueError("unqualified_native_version")
    root = Path(__file__).resolve().parents[3]
    command = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_us_equities_strategies",
        "-v",
    ]
    # The test process inherits no credential-bearing environment values.
    env = {
        "PATH": os.defpath,
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    completed = subprocess.run(
        command, cwd=root, env=env, capture_output=True, text=True, check=False
    )
    count = re.search(r"Ran (\d+) tests", completed.stderr)
    source = [
        *sorted(Path(__file__).parent.glob("*.py")),
        root / "tests/test_us_equities_strategies.py",
        root / "blueprints/us-equities/adaptive-paper/exits.py",
        root / "blueprints/us-equities/adaptive-paper/sessions.py",
        root / "blueprints/us-equities/adaptive-paper/native_adapter.py",
        root / "blueprints/us-equities/adaptive-paper/safety.py",
        root / "tests/test_adaptive_paper_native.py",
    ]
    skipped = "skipped" in completed.stderr
    receipt = {
        "schema_version": 1,
        "kind": "t22_strategy_test_receipt",
        "status": "passed"
        if completed.returncode == 0 and count and not skipped
        else "failed",
        "evidence_class": "synthetic",
        "engine_version": "2.0.0rc5",
        "runtime_install": "T13 unchanged uv sync --locked from ee3883699870d972058516192b1ee1c6e3ffb762",
        "command": "ENGINE_PYTHON -m unittest tests.test_us_equities_strategies -v",
        "generator": "ENGINE_PYTHON -m blueprints.us-equities.strategies.acceptance --output test-acceptance.json",
        "exit": completed.returncode,
        "tests_run": int(count.group(1)) if count else 0,
        "native_tests_skipped": skipped,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "passed_tests": [
            line.split(" (")[0]
            for line in completed.stderr.splitlines()
            if line.endswith(" ... ok")
        ],
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source
        },
        "scope": "ten exact classes plus restart and multi-instance regressions in BacktestEngine/LiveNode; synthetic ports and real local ledger only",
        "broker_e2e": "NOT_RUN",
        "historical_layer15_e2e": "NOT_RUN",
        "strategy_performance": "NOT_CITED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if receipt["status"] != "passed":
        # The exact full-output hashes remain in the receipt; avoid repeating
        # every subtest traceback when one native contract fails across a grid.
        print(completed.stderr[-6000:], file=sys.stderr)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "tests_run": receipt["tests_run"],
                "path": str(args.output),
            }
        )
    )
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
