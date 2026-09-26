#!/usr/bin/env python3
"""Run the token-efficiency coverage check once in a checkout and retain how it ran.

In the checkout given, this first checks whether a project `.codex/config.toml` exists, then runs

    python scripts/adoption_status.py --profile token-efficiency --client-wiring --pinned-versions --json

there with this interpreter. It writes the check's stdout byte for byte to
`coverage-<UTC start>.json` in --out-dir and prints its provenance, status lines first: the exit status,
whether the project Codex config existed, the checkout's HEAD, the sha256 of the checkout's
`scripts/adoption_status.py` and of the report, the interpreter version, the UTC start and end, and the
stderr byte count. `git status --porcelain` is summarized as a count of changed paths. No path, file text or
environment value is printed.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
from pathlib import Path
import subprocess
import sys

CHECK = ["scripts/adoption_status.py", "--profile", "token-efficiency", "--client-wiring", "--pinned-versions",
         "--json"]


def utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def git(checkout: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True, check=True).stdout


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
    project_config = (checkout / ".codex" / "config.toml").exists()
    start = utc()
    completed = subprocess.run([sys.executable, *CHECK], cwd=checkout, stdin=subprocess.DEVNULL,
                               capture_output=True, check=False)
    end = utc()
    name = f"coverage-{start.strftime('%Y%m%dT%H%M%SZ')}.json"
    (args.out_dir / name).write_bytes(completed.stdout)
    print(f"exit status: {completed.returncode}")
    print(f"project .codex/config.toml present before the run: {project_config}")
    print(f"report: {name}, sha256 {hashlib.sha256(completed.stdout).hexdigest()}, {len(completed.stdout)} bytes")
    print(f"stderr: {len(completed.stderr)} bytes")
    print(f"command (working directory: the checkout): python {' '.join(CHECK)}")
    print(f"interpreter: Python {sys.version.split()[0]}")
    print(f"checkout HEAD: {head}; paths changed from HEAD (git status --porcelain): {changed}")
    print(f"scripts/adoption_status.py sha256: {script}")
    print(f"UTC: {start.isoformat().replace('+00:00', 'Z')} to {end.isoformat().replace('+00:00', 'Z')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
