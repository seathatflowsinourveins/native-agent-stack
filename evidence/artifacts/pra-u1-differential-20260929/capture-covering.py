"""The shell texts the covering test suites feed the kernel: a private list (JSON array of strings) and counts only.

    python3 capture-covering.py --repo <checkout> --out <commands.json>

A scratch mirror of the checkout's tracked files is built (the kernel with log lines added at the head of analyzeScript and executedText)
and the three Python modules that drive the kernel run in it with the log path in CU_LOG. The commands are test fixtures, not host data, but the list is not committed: output is counts and the file's location.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
repo = Path(args.repo).resolve()
workflows = "examples/claude-native/workflows"

kernel = (repo / workflows / "child-usage.mjs").read_text()
# The linear-time tests feed the kernel inputs of up to 768,000 characters: timing inputs, on which the scanner reading that the differential
# compares against is quadratic (minutes). They are counted (their length is logged) and left out of the compared list.
LIMIT = 5000
LOG = "process.env.CU_LOG && __log(process.env.CU_LOG, JSON.stringify(String(command || '').length > %d ? { src: 'SRC', over: String(command || '').length } : { src: 'SRC', command: String(command || '') }) + '\\n')\n" % LIMIT
hooks = [
    ("import { readFileSync, existsSync,", "import { appendFileSync as __log } from 'node:fs'\nimport { readFileSync, existsSync,"),
    ("function analyzeScript(command) {\n", "function analyzeScript(command) {\n  " + LOG.replace("SRC", "lanes")),
    ("export function executedText(command, { inlineHttp = false } = {}) {\n", "export function executedText(command, { inlineHttp = false } = {}) {\n  " + LOG.replace("SRC", "executedText")),
]
for old, new in hooks:
    if kernel.count(old) != 1:
        sys.exit("capture hook anchor not found exactly once: " + old[:60])
    kernel = kernel.replace(old, new)

with tempfile.TemporaryDirectory(prefix="covering-") as scratch:
    mirror = Path(scratch)
    tracked = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout.split(b"\0")
    for name in filter(None, (t.decode() for t in tracked)):
        source = repo / name
        if source.is_file():
            (mirror / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, mirror / name, follow_symlinks=False)
    (mirror / workflows / "child-usage.mjs").write_text(kernel)
    log = mirror / "log.jsonl"
    env = {**os.environ, "CU_LOG": str(log)}
    run = subprocess.run([sys.executable, "-m", "unittest", "tests.test_token_measurement", "tests.test_skill_usage", "tests.test_child_usage_suite"],
                         cwd=mirror, env=env, capture_output=True, text=True, check=False)
    summary = [line for line in run.stderr.splitlines() if line.startswith(("Ran", "OK", "FAILED"))]
    failing = sorted({line.split()[1] for line in run.stderr.splitlines() if line.startswith(("ERROR:", "FAIL:"))})
    if failing:
        print("failing tests in the mirror: " + ", ".join(failing[:6]) + (" ..." if len(failing) > 6 else ""), file=sys.stderr)
        print("first error: " + next((line for line in run.stderr.splitlines() if "Error" in line and not line.startswith(("ERROR", "FAIL"))), ""), file=sys.stderr)
    rows = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
commands = sorted({row["command"] for row in rows if "command" in row})
over = len({row["over"] for row in rows if "over" in row})  # distinct lengths: the over-long inputs are not kept
Path(args.out).write_text(json.dumps(commands))
os.chmod(args.out, 0o600)
print(json.dumps({"suites_exit": run.returncode, "suites": " | ".join(summary), "log_rows": len(rows), "compared_commands": len(commands),
                  "read_for_lanes": len({row["command"] for row in rows if row["src"] == "lanes" and "command" in row}),
                  "distinct_lengths_over_%d_characters_left_out" % LIMIT: over}))
