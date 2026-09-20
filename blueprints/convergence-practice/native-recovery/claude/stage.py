"""Owned deterministic Bash effect; deliberately unfinished wait for recovery."""
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

EXPECTED = b'{"ids":["alpha","bravo","charlie","delta"],"total":18}\n'


def durable(path, data, exclusive=True):
    with path.open("xb" if exclusive else "wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def actions(root):
    path = root / "actions.jsonl"
    return [json.loads(line)["action"] for line in path.read_text().splitlines()] if path.exists() else []


def execute(root, action):
    root = Path(root)
    before = actions(root)
    with (root / "actions.jsonl").open("a") as out:
        out.write(json.dumps({"action": action}) + "\n")
        out.flush()
        os.fsync(out.fileno())
    if action == "checkpoint":
        if before:
            raise ValueError("checkpoint_repeated_or_wrong_order")
        records = json.loads((root / "input.json").read_text())["records"]
        payload = (json.dumps({"ids": sorted(r["id"] for r in records),
                              "total": sum(r["value"] for r in records)}, separators=(",", ":")) + "\n").encode()
        if payload != EXPECTED:
            raise ValueError("input_oracle_mismatch")
        durable(root / "checkpoint.json", payload)
    elif action == "wait":
        if before != ["checkpoint"]:
            raise ValueError("wait_wrong_order")
        # Identity remains private; the supervisor verifies start ticks before cleanup.
        stat = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
        marker = {"pid": os.getpid(), "start_ticks": stat[19]}
        durable(root / "wait-started.json", (json.dumps(marker) + "\n").encode())
        def interrupted(signum, _frame):
            durable(root / "wait-interrupted.json", (json.dumps({"signal": signum}) + "\n").encode())
            raise SystemExit(128 + signum)
        signal.signal(signal.SIGINT, interrupted)
        signal.signal(signal.SIGTERM, interrupted)
        time.sleep(120)
        durable(root / "wait-finished-naturally.json", b"{}\n")
        raise RuntimeError("wait_was_not_interrupted")
    elif action == "finalize":
        if before != ["checkpoint", "wait"]:
            raise ValueError("finalize_wrong_order")
        if not (root / "resume-authorized.json").exists():
            raise ValueError("resume_not_authorized_by_supervisor")
        if (root / "checkpoint.json").read_bytes() != EXPECTED:
            raise ValueError("checkpoint_changed")
        result = {"checkpoint_sha256": hashlib.sha256(EXPECTED).hexdigest(),
                  "execution_count": 1, "status": "complete"}
        durable(root / "final.json", (json.dumps(result, sort_keys=True) + "\n").encode())
    else:
        raise ValueError("unknown_action")
    return {"checkpoint_sha256": hashlib.sha256(EXPECTED).hexdigest(),
            "execution_count": actions(root).count("checkpoint"), "action": action}


if __name__ == "__main__":
    print(json.dumps(execute(Path(__file__).resolve().parent, sys.argv[1])))
