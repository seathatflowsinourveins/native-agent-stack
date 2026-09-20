"""Deterministic external effect used by the native recovery qualification."""
import hashlib
import json
from pathlib import Path

EXPECTED = b'{"ids":["alpha","bravo","charlie","delta"],"total":18}\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Fixture:
    def __init__(self, root):
        self.root = Path(root)
        self.calls = []

    def checkpoint(self):
        self.calls.append("checkpoint")
        if self.calls.count("checkpoint") != 1:
            raise ValueError("checkpoint_repeated")
        records = json.loads((self.root / "input.json").read_text())["records"]
        result = {"ids": sorted(r["id"] for r in records),
                  "total": sum(r["value"] for r in records)}
        payload = (json.dumps(result, separators=(",", ":")) + "\n").encode()
        if payload != EXPECTED:
            raise ValueError("checkpoint_oracle_mismatch")
        # Exclusive creation makes an existing external effect visible as failure.
        with (self.root / "checkpoint.json").open("xb") as out:
            out.write(payload)
            out.flush()
            import os
            os.fsync(out.fileno())
        return {"checkpoint_sha256": digest(payload), "execution_count": 1}

    def wait(self):
        self.calls.append("wait")
        if self.calls != ["checkpoint", "wait"]:
            raise ValueError("wait_order_mismatch")
        return None  # The RPC host deliberately withholds this tool response.

    def finalize(self):
        self.calls.append("finalize")
        if self.calls != ["checkpoint", "wait", "finalize"]:
            raise ValueError("finalization_order_mismatch")
        payload = (self.root / "checkpoint.json").read_bytes()
        if payload != EXPECTED:
            raise ValueError("checkpoint_changed")
        result = {"checkpoint_sha256": digest(payload), "execution_count": 1,
                  "status": "complete"}
        with (self.root / "final.json").open("x") as out:
            json.dump(result, out, sort_keys=True)
            out.write("\n")
        return result


def assess(checks):
    required = (
        "same_thread_id", "same_session_id", "pending_native_tool_observed",
        "interrupt_acknowledged", "interrupted_turn_observed",
        "second_connection_initialized", "resumed_turn_completed",
        "checkpoint_unchanged", "checkpoint_executed_once",
        "exact_action_order", "final_matches_oracle", "frozen_inputs_unchanged",
        "owned_servers_stopped", "model_and_effort_preserved",
    )
    return all(checks.get(key) is True for key in required)
