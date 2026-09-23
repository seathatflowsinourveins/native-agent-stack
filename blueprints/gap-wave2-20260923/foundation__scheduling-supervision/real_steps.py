#!/usr/bin/env python3
"""Real-workload Dagu steps for gap-wave2 scheduling-supervision (gaps 2 and 11).

The workload is this repository's own maintenance checks run on a frozen
`git archive` snapshot: scripts/validate.py (checkpoint) and
scripts/build_ecosystem.py --check plus a second validate.py (finalize).
When WORK/model-enabled exists, the checkpoint also makes ONE bounded
`codex exec` call that judges the validate output (a real model step).

The shape mirrors blueprints/convergence-practice/job-recovery/fixture.py:
an exclusive execution claim precedes the work, so a re-executed checkpoint
(or a second model call) fails loudly instead of silently passing.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REAL_HOME = os.environ.get("GW2_REAL_HOME", "")


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return digest_bytes(Path(path).read_bytes())


def exclusive(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write("\n")


def run_script(work, argv, label):
    result = subprocess.run([sys.executable, "-B", *argv], cwd=work / "snapshot", capture_output=True,
                            text=True, timeout=120,
                            env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(work)})
    with (work / f"{label}.log").open("x", encoding="utf-8") as handle:
        handle.write(result.stdout + result.stderr)
    first = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    parsed = json.loads(first)
    if result.returncode != 0 or parsed.get("status") != "passed":
        raise ValueError(f"{label} did not pass")
    return {"exit": result.returncode, "stdout_first_line": first, "stdout_first_line_sha256": digest_bytes(first.encode())}


def find_usage(value):
    if isinstance(value, dict):
        if "usage" in value and isinstance(value["usage"], dict):
            return value["usage"]
        for item in value.values():
            found = find_usage(item)
            if found is not None:
                return found
    if isinstance(value, list):
        for item in value:
            found = find_usage(item)
            if found is not None:
                return found
    return None


def model_step(work, validate_line):
    # A second model call for this run cannot create this claim file.
    exclusive(work / "model-call-claim.json", {"model_calls": 1})
    cwd = work / "model-cwd"
    cwd.mkdir()
    prompt = ("You are one triage step in a repository maintenance job. Below is the one-line JSON output "
              "of the repository's validation script. Reply with exactly one word and nothing else: PASS if "
              "its status field is \"passed\", otherwise FAIL.\n\n" + validate_line)
    env = {"PATH": os.environ.get("GW2_CODEX_PATH", "/usr/bin:/bin"), "HOME": REAL_HOME}
    # Fix round 1: wait while 2 or more other real `codex exec` processes run; record it.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import dagu_common
    gate = dagu_common.codex_gate()
    started = time.time()
    result = subprocess.run(["codex", "exec", "--json", "--sandbox", "read-only", "--ephemeral",
                             "--skip-git-repo-check", "-C", str(cwd), prompt],
                            capture_output=True, text=True, timeout=240, env=env, stdin=subprocess.DEVNULL)
    elapsed = round(time.time() - started, 1)
    (work / "model-events.jsonl").write_text(result.stdout)
    (work / "model-stderr.txt").write_text(result.stderr)
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith("{")]
    messages = [e["item"].get("text", "") for e in events
                if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"]
    verdict = messages[-1].strip() if messages else ""
    usage = find_usage([e for e in events if e.get("type") == "turn.completed"])
    if result.returncode != 0 or verdict not in ("PASS", "FAIL") or usage is None:
        raise ValueError("Model step did not return a verdict and usage")
    return {"exit": result.returncode, "verdict": verdict, "usage": usage, "elapsed_s": elapsed, "codex_gate": gate,
            "event_types": [e.get("type") for e in events]}


def verify_checkpoint(work):
    record = json.loads((work / "checkpoint.json").read_text())
    if record.get("execution_count") != 1:
        raise ValueError("Checkpoint content changed")
    if json.loads((work / "checkpoint-started.json").read_text()) != {"execution_count": 1}:
        raise ValueError("Checkpoint execution count changed")
    return digest(work / "checkpoint.json")


def checkpoint(work):
    exclusive(work / "checkpoint-started.json", {"execution_count": 1})
    validate = run_script(work, ["scripts/validate.py"], "checkpoint-validate")
    record = {"execution_count": 1, "validate": validate}
    if (work / "model-enabled").exists():
        record["model"] = model_step(work, validate["stdout_first_line"])
    exclusive(work / "checkpoint.json", record)


def finalize(work):
    before = verify_checkpoint(work)
    retry = (work / "release-finalize").exists()
    exclusive(work / ("retry-ready.json" if retry else "finalize-ready.json"), {"pid": os.getpid()})
    deadline = time.monotonic() + 180
    while not (work / "release-finalize").exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("Finalizer release was not supplied within 180 seconds")
        time.sleep(0.05)
    ecosystem = run_script(work, ["scripts/build_ecosystem.py", "--check"], "final-ecosystem")
    validate = run_script(work, ["scripts/validate.py"], "final-validate")
    if verify_checkpoint(work) != before:
        raise ValueError("Checkpoint changed during finalization")
    exclusive(work / "completed.json", {"checkpoint_sha256": before, "ecosystem": ecosystem, "validate": validate})


if __name__ == "__main__":
    action, work = sys.argv[1], Path(sys.argv[2])
    {"checkpoint": checkpoint, "finalize": finalize}[action](work)
