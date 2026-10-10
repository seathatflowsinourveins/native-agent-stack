"""Retain GNU time measurements for the native Linux CI scanner commands.

GNU time 1.9: %e elapsed seconds, %M peak RSS KiB, %x command exit status.
Only fixed GitHub scope fields, counts and source hashes enter the receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess


def record(args):
    timing = json.loads(args.timing.read_text())
    elapsed = timing["elapsed_seconds"]
    rss = timing["peak_rss_kib"]
    status = timing["exit_status"]
    if (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0
        or type(rss) is not int or rss < 0 or type(status) is not int
        or status != args.exit_status or not 0 <= status <= 255):
        raise ValueError("Invalid native timer evidence")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("No exact checked-out revision")
    count = None
    if args.report and args.report.is_file():
        findings = json.loads(args.report.read_text())
        if findings is not None and not isinstance(findings, list):
            raise ValueError("Invalid redacted scanner report")
        count = len(findings or [])
    bindings = {}
    for name in (".github/workflows/validate.yml", ".gitleaks.toml", ".gitleaksignore"):
        bindings[name] = hashlib.sha256(Path(name).read_bytes()).hexdigest()
    value = {
        "schema_version": 1, "kind": "full_uncapped_secret_scan",
        "scanner": args.scanner, "mode": args.mode, "scanner_version": args.version,
        "measurement": "GNU time", "platform": platform.system(),
        "elapsed_seconds": elapsed, "peak_rss_kib": rss, "exit_status": status,
        "findings": count, "report_only": args.scanner == "betterleaks",
        "checked_out_commit": revision, "history_scope": "HEAD" if args.mode == "git" else None,
        "event_name": os.environ.get("GITHUB_EVENT_NAME"), "ref": os.environ.get("GITHUB_REF"),
        "github_sha": os.environ.get("GITHUB_SHA"), "repository": os.environ.get("GITHUB_REPOSITORY"),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "job": os.environ.get("GITHUB_JOB"), "job_timeout_minutes": args.timeout_minutes,
        "source_sha256": bindings,
        "boundary": "Per-command resource measurement; native API job duration includes checkout/install/regressions/post steps",
    }
    args.output.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    print(json.dumps(value, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--scanner", choices=("gitleaks", "betterleaks"), required=True)
    parser.add_argument("--mode", choices=("git", "dir"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--exit-status", type=int, required=True)
    parser.add_argument("--timeout-minutes", type=int, required=True)
    args = parser.parse_args()
    try:
        record(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        print("Native secret-scan timing evidence is unavailable or invalid.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
