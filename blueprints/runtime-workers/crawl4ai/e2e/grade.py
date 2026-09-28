#!/usr/bin/env python3
"""Invoke unchanged Promptfoo 0.123.1 assertions; retain its verdict and output.

Sources: pinned standalone-assertions docs; src/util/config/load.ts:789-820;
src/node/doEval.ts exit codes; src/types/index.ts report envelope. No custom
scoring, model calls, service or installation. See research.md for exact URLs.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = "0.123.1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def grade(directory, executable):
    directory = Path(directory).resolve()
    env = dict(os.environ, PROMPTFOO_CONFIG_DIR=str(directory / "promptfoo-state"),
               PROMPTFOO_LOG_DIR=str(directory / "promptfoo-state/logs"),
               PROMPTFOO_CACHE_PATH=str(directory / "promptfoo-state/cache"),
               PROMPTFOO_DISABLE_TELEMETRY="1", PROMPTFOO_DISABLE_UPDATE="1",
               PROMPTFOO_PASS_RATE_THRESHOLD="100", PROMPTFOO_FAILED_TEST_EXIT_CODE="100",
               PYTHONDONTWRITEBYTECODE="1")
    version = subprocess.run([str(executable), "--version"], env=env, cwd=directory,
                             capture_output=True, text=True, timeout=30, check=True)
    if version.stdout.strip() != VERSION:
        raise ValueError("Promptfoo 0.123.1 required; no fallback grader")
    with (directory / "model-outputs.json").open("w") as stream:
        subprocess.run([sys.executable, str(HERE / "check.py"), str(directory / "result.json")],
                       env=env, stdout=stream, check=True, timeout=30)
    command = [str(executable), "eval", "--assertions", "assertions.json", "--model-outputs",
               os.path.relpath(directory / "model-outputs.json", HERE), "--no-cache", "--no-share",
               "--no-write", "--no-progress-bar", "--no-table", "--max-concurrency", "1",
               "-o", str(directory / "promptfoo.json")]
    with (directory / "promptfoo.stdout").open("w") as out, (directory / "promptfoo.stderr").open("w") as err:
        result = subprocess.run(command, cwd=HERE, env=env, stdout=out, stderr=err, timeout=120)
    info = {"harness": "promptfoo", "version": VERSION, "exit_code": result.returncode,
            "source_sha256": digest(directory / "result.json"),
            "report_sha256": digest(directory / "promptfoo.json"),
            "assertions_sha256": digest(HERE / "assertions.json"),
            "expected_sha256": digest(HERE / "expected.json")}
    (directory / "grader.json").write_text(json.dumps(info, indent=2) + "\n")
    return info


def observation(directory, info=None):
    """Read upstream success, checking binding/completeness, never re-score data."""
    directory = Path(directory)
    result = {"harness": "promptfoo", "version": VERSION, "passed": False, "status": "unavailable"}
    try:
        if info is None:
            info = json.loads((directory / "grader.json").read_text())
        report = json.loads((directory / "promptfoo.json").read_text())
        rows = report["results"]["results"]
        stats = report["results"]["stats"]
        bound = (info["harness"] == "promptfoo" and info["version"] == VERSION
                 and info["source_sha256"] == digest(directory / "result.json")
                 and info["report_sha256"] == digest(directory / "promptfoo.json")
                 and info["assertions_sha256"] == digest(HERE / "assertions.json")
                 and info["expected_sha256"] == digest(HERE / "expected.json")
                 and len(rows) == 1
                 # Promptfoo trims the rendered echo prompt. Original bytes stay
                 # bound by source_sha256; whitespace is not a product verdict.
                 and rows[0]["response"]["output"] == (directory / "result.json").read_text().strip())
        if not bound:
            result["status"] = "unbound_or_incomplete"
            return result
        result.update(status="observed", exit_code=info["exit_code"],
                      report_sha256=info["report_sha256"],
                      source_sha256=info["source_sha256"],
                      passed=(info["exit_code"] == 0 and rows[0]["success"] is True
                              and stats["successes"] == 1 and stats["failures"] == 0 and stats["errors"] == 0))
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    return result


def run_controls(directory, executable):
    """Three synthetic controls through the same transport and upstream grader."""
    directory = Path(directory)
    correct = (HERE / "expected.json").read_text()
    controls = {"known-pass": correct, "known-fail": correct.replace("24.90", "999.00"),
                "malformed-output": '{"records": [BROKEN'}
    output = {}
    for name, value in controls.items():
        case = directory / name
        case.mkdir(parents=True)
        (case / "result.json").write_text(value)
        output[name] = grade(case, executable)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--executable", default=os.environ.get("NAS_CRAWL4AI_GRADER", "promptfoo"))
    parser.add_argument("--controls", action="store_true")
    args = parser.parse_args()
    if args.controls:
        controls = run_controls(args.directory, args.executable)
        print(json.dumps(controls, indent=2))
        raise SystemExit(0 if {k: v["exit_code"] for k, v in controls.items()} == {
            "known-pass": 0, "known-fail": 100, "malformed-output": 100} else 1)
    raise SystemExit(grade(args.directory, args.executable)["exit_code"])
