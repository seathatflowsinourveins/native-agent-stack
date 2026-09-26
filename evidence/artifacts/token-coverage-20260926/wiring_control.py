#!/usr/bin/env python3
"""Discriminating control for the coverage check's client wiring, with its passing run beside it.

In the checkout given, this runs

    python scripts/adoption_status.py --profile token-efficiency --client-wiring --pinned-versions --json

twice with this interpreter: first with CODEX_HOME set to a new empty directory, so the check finds no Codex
user scope (the condition absent), then with the environment it was started with. Each run's stdout is written
byte for byte to --out-dir, as `coverage-<UTC start>-codex-home-empty.json` and `coverage-<UTC start>.json`.
It prints, per run, the exit status, whether the checkout had a project `.codex/config.toml` just before it,
the report's sha256 and size, the stderr byte count, the UTC start and end, and the report's own
`client_wiring.complete`, `codex.mcp_servers_present` and `project.codex_mcp_servers_present`; then the
interpreter version and whether it runs in a virtual environment, the checkout's HEAD, a count of the paths
`git status --porcelain` lists, and the sha256 of the checkout's `scripts/adoption_status.py`. No path, file
text or environment value is printed; the empty directory is removed afterwards.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CHECK = ["scripts/adoption_status.py", "--profile", "token-efficiency", "--client-wiring", "--pinned-versions",
         "--json"]
SERVERS = ("serena", "socraticode", "ai-memory")


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(checkout: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True, check=True).stdout


def run(checkout: Path, out_dir: Path, label: str, suffix: str, env: dict) -> None:
    project_config = (checkout / ".codex" / "config.toml").exists()
    start = utc()
    completed = subprocess.run([sys.executable, *CHECK], cwd=checkout, env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, check=False)
    end = utc()
    name = f"coverage-{start.replace('-', '').replace(':', '')}{suffix}.json"
    (out_dir / name).write_bytes(completed.stdout)
    print(f"== {label}")
    print(f"exit status: {completed.returncode}; stderr: {len(completed.stderr)} bytes; UTC: {start} to {end}")
    print(f"project .codex/config.toml present before the run: {project_config}")
    print(f"report: {name}, sha256 {hashlib.sha256(completed.stdout).hexdigest()}, {len(completed.stdout)} bytes")
    try:
        wiring = json.loads(completed.stdout)["client_wiring"]
        print(f"client_wiring.complete: {json.dumps(wiring['complete'])}")
        for scope, key in (("codex", "mcp_servers_present"), ("project", "codex_mcp_servers_present")):
            present = wiring[scope][key]
            print(f"client_wiring.{scope}.{key}: "
                  + ", ".join(f"{server}={json.dumps(present.get(server))}" for server in SERVERS))
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"report not readable as the check's JSON: {type(error).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    head = git(checkout, "rev-parse", "HEAD").strip()
    changed = len([line for line in git(checkout, "status", "--porcelain", "--untracked-files=all").splitlines()
                   if line])
    script = hashlib.sha256((checkout / "scripts/adoption_status.py").read_bytes()).hexdigest()
    print(f"command (working directory: the checkout): python {' '.join(CHECK)}")
    with tempfile.TemporaryDirectory(prefix="empty-codex-home-") as empty:
        run(checkout, args.out_dir, "control: CODEX_HOME set to a new empty directory", "-codex-home-empty",
            {**os.environ, "CODEX_HOME": empty})
    run(checkout, args.out_dir, "the environment this driver was started with", "", dict(os.environ))
    virtual = sys.prefix != sys.base_prefix
    print(f"interpreter: Python {sys.version.split()[0]}; virtual environment: {virtual}")
    print(f"checkout HEAD: {head}; paths changed from HEAD (git status --porcelain): {changed}")
    print(f"scripts/adoption_status.py sha256: {script}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
