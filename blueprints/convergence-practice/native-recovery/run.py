#!/usr/bin/env python3
"""Explicit, metered native recovery attempt. Never invoked by repository tests.

Full protocol logs and native identifiers stay in --run-dir, outside Git.
The caller reviews the sanitized receipt before copying it into the blueprint.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

from fixture import EXPECTED, Fixture, assess, digest

HERE = Path(__file__).resolve().parent
TOOL = {
    "type": "function", "name": "recovery_step", "deferLoading": False,
    "description": "Owned synthetic recovery fixture. checkpoint writes one durable effect; wait remains pending for native interruption; finalize verifies that effect after same-thread resume.",
    "inputSchema": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["checkpoint", "wait", "finalize"]}},
        "required": ["action"], "additionalProperties": False},
}
RESUME = "Continue the interrupted recovery task from its existing checkpoint. The owned wait was cancelled. Finalize the existing result without repeating checkpoint creation. Use only recovery_step and report the returned digest and execution count."


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


class RPC:
    def __init__(self, executable, cwd, run_dir, label):
        self.events = queue.Queue()
        self.serial = 0
        self.config_read_ids = set()
        self.history = []
        self.label = label
        self.log = (run_dir / (label + ".protocol.jsonl")).open("x")
        self.err = (run_dir / (label + ".stderr.txt")).open("x")
        self.proc = subprocess.Popen(
            [str(executable), "app-server", "--strict-config", "--listen", "stdio://"],
            cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err,
            text=True, bufsize=1,
        )
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                value = {"invalid_stdout": line}
            self.events.put(value)
        self.events.put({"eof": True})

    def send(self, obj):
        self.log.write(json.dumps({"direction": "client", "message": obj}) + "\n")
        self.log.flush()
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params):
        self.serial += 1
        if method == "config/read":
            self.config_read_ids.add(self.serial)
        self.send({"id": self.serial, "method": method, "params": params})
        return self.serial

    def log_message(self, message):
        if message.get("id") in self.config_read_ids and "result" in message:
            config = message["result"].get("config", {})
            message = {"id": message["id"], "result": {
                "config": {key: config.get(key) for key in ("model", "model_reasoning_effort")},
                "other_configuration_omitted": True}}
        self.log.write(json.dumps({"direction": "server", "message": message}) + "\n")

    def receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("native_stage_deadline")
        try:
            value = self.events.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError("native_stage_deadline") from exc
        self.log_message(value)
        self.log.flush()
        self.history.append(value)
        if value.get("eof") or "invalid_stdout" in value:
            raise RuntimeError("native_protocol_closed_or_invalid")
        return value

    def response(self, request_id, seconds=45):
        deadline = time.monotonic() + seconds
        while True:
            obj = self.receive(deadline)
            if obj.get("id") == request_id and "method" not in obj:
                if "error" in obj:
                    raise RuntimeError("native_rpc_error")
                return obj["result"]
            if "id" in obj and "method" in obj:
                raise RuntimeError("unexpected_server_request_during_handshake")

    def call(self, method, params, seconds=45):
        return self.response(self.request(method, params), seconds)

    def initialize(self):
        self.call("initialize", {"clientInfo": {
            "name": "native_recovery_qualification", "version": "1.0.0"},
            "capabilities": {"experimentalApi": True}})
        self.send({"method": "initialized", "params": {}})

    def stop(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
        self.reader.join(timeout=2)
        # Preserve queued terminal protocol output without interpreting it as a new run.
        while not self.events.empty():
            obj = self.events.get_nowait()
            self.history.append(obj)
            self.log_message(obj)
        self.log.close()
        self.err.close()
        return self.proc.returncode


def tool_response(rpc, obj, value):
    rpc.send({"id": obj["id"], "result": {"success": True,
              "contentItems": [{"type": "inputText", "text": json.dumps(value)}]}})


def stage(rpc, fixture, thread_id, turn_id, phase, timeout):
    deadline = time.monotonic() + timeout
    while True:
        obj = rpc.receive(deadline)
        method, params = obj.get("method"), obj.get("params", {})
        if method == "item/tool/call":
            if (params.get("threadId") != thread_id or params.get("turnId") != turn_id
                    or params.get("tool") != "recovery_step"):
                raise RuntimeError("unexpected_dynamic_tool_scope")
            action = params["arguments"]["action"]
            if action == "wait" and phase == 1:
                fixture.wait()
                return {"pending_request": obj, "status": "pending"}
            if action == "checkpoint" and phase == 1:
                tool_response(rpc, obj, fixture.checkpoint())
            elif action == "finalize" and phase == 2:
                tool_response(rpc, obj, fixture.finalize())
            else:
                fixture.calls.append(action)
                raise RuntimeError("unexpected_action_or_checkpoint_replay")
        elif "id" in obj and method:
            raise RuntimeError("unexpected_approval_or_server_request")
        elif method == "item/started" and params.get("item", {}).get("type") in (
                "commandExecution", "fileChange", "collabAgentToolCall"):
            raise RuntimeError("unexpected_builtin_tool")
        elif method == "turn/completed" and params.get("turn", {}).get("id") == turn_id:
            return {"status": params["turn"]["status"]}


def run(args):
    run_dir = Path(args.run_dir).expanduser().resolve()
    repo = HERE.parents[2]
    if run_dir == repo or repo in run_dir.parents:
        raise ValueError("private_run_dir_must_be_outside_public_repository")
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    executable = Path(shutil.which(args.codex) or args.codex).resolve(strict=True)
    version = subprocess.check_output([str(executable), "--version"], text=True).strip()
    frozen = {p.relative_to(repo).as_posix(): digest(p.read_bytes()) for p in (
        HERE / "seed/input.json", HERE / "seed/TASK.md", HERE / "fixture.py",
        HERE / "run.py", repo / "tests/test_native_recovery.py", HERE / "plan.json")}
    dump(run_dir / "freeze.json", {"frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                  "files": frozen})
    workspace = run_dir / "fixture"
    workspace.mkdir()
    shutil.copyfile(HERE / "seed/input.json", workspace / "input.json")
    shutil.copyfile(HERE / "seed/TASK.md", workspace / "TASK.md")
    subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "add", "input.json", "TASK.md"], check=True)
    subprocess.run(["git", "-C", str(workspace), "-c", "user.name=Recovery Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "Freeze recovery input"], check=True)
    fixture = Fixture(workspace)
    clients = []
    checks = {}
    thread_id = turn_id = None
    failed_stage = "initialize"
    error = None
    started = time.monotonic()
    native_models = []
    try:
        first = RPC(executable, workspace, run_dir, "connection-1")
        clients.append(first)
        first.initialize()
        config = first.call("config/read", {"includeLayers": False})["config"]
        if config.get("model") != "gpt-6-astra" or config.get("model_reasoning_effort") != "ultra":
            raise RuntimeError("native_default_model_or_effort_differs")
        failed_stage = "thread_start"
        started_thread = first.call("thread/start", {
            "cwd": str(workspace), "approvalPolicy": "never", "sandbox": "read-only",
            "ephemeral": False, "dynamicTools": [TOOL]})
        thread_id = started_thread["thread"]["id"]
        session_id = started_thread["thread"].get("sessionId")
        native_models.append({"model": started_thread.get("model"),
                              "effort": started_thread.get("reasoningEffort")})
        dump(run_dir / "native-identifiers.json", {"thread_id": thread_id, "session_id": session_id})
        failed_stage = "checkpoint_and_pending_tool"
        turn = first.call("turn/start", {"threadId": thread_id,
                          "input": [{"type": "text", "text": (HERE / "seed/TASK.md").read_text()}]})
        turn_id = turn["turn"]["id"]
        pending = stage(first, fixture, thread_id, turn_id, 1, args.timeout)
        checks["pending_native_tool_observed"] = pending["status"] == "pending"
        if not checks["pending_native_tool_observed"]:
            raise RuntimeError("turn_finished_before_pending_tool")
        before = (workspace / "checkpoint.json").read_bytes()
        failed_stage = "interrupt"
        reply = first.call("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
        checks["interrupt_acknowledged"] = reply == {}
        # Completion can precede the interrupt RPC response: inspect retained events first.
        def interrupted():
            return any(x.get("method") == "turn/completed" and
                       x.get("params", {}).get("turn", {}).get("id") == turn_id and
                       x["params"]["turn"].get("status") == "interrupted" for x in first.history)
        deadline = time.monotonic() + 30
        while not interrupted():
            first.receive(deadline)
        checks["interrupted_turn_observed"] = True
        first.stop()
        failed_stage = "resume"
        second = RPC(executable, workspace, run_dir, "connection-2")
        clients.append(second)
        second.initialize()
        checks["second_connection_initialized"] = True
        resumed = second.call("thread/resume", {"threadId": thread_id})
        checks["same_thread_id"] = resumed["thread"]["id"] == thread_id
        checks["same_session_id"] = bool(session_id) and resumed["thread"].get("sessionId") == session_id
        native_models.append({"model": resumed.get("model"), "effort": resumed.get("reasoningEffort")})
        checks["model_and_effort_preserved"] = all(
            m == {"model": "gpt-6-astra", "effort": "ultra"} for m in native_models)
        failed_stage = "finalization"
        turn = second.call("turn/start", {"threadId": thread_id,
                          "input": [{"type": "text", "text": RESUME}]})
        turn_id = turn["turn"]["id"]
        final = stage(second, fixture, thread_id, turn_id, 2, args.timeout)
        checks["resumed_turn_completed"] = final["status"] == "completed"
        checks["checkpoint_unchanged"] = (workspace / "checkpoint.json").read_bytes() == before == EXPECTED
        value = json.loads((workspace / "final.json").read_text())
        checks["final_matches_oracle"] = value == {"checkpoint_sha256": digest(EXPECTED),
                                                  "execution_count": 1, "status": "complete"}
        failed_stage = None
    except Exception as exc:
        error = {"type": type(exc).__name__, "reason": str(exc)}
        # Details may contain private native data; keep them in the private run directory.
        dump(run_dir / "failure-private.json", {"stage": failed_stage, "error": error})
        if clients and clients[-1].proc.poll() is None and thread_id and turn_id:
            try:
                clients[-1].call("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}, 15)
            except Exception:
                pass
    finally:
        for client in clients:
            if not client.log.closed:
                client.stop()
    checks["owned_servers_stopped"] = bool(clients) and all(c.proc.poll() is not None for c in clients)
    checks["checkpoint_executed_once"] = fixture.calls.count("checkpoint") == 1
    checks["exact_action_order"] = fixture.calls == ["checkpoint", "wait", "finalize"]
    checks["frozen_inputs_unchanged"] = all(digest((repo / p).read_bytes()) == h for p, h in frozen.items())
    snapshots = []
    for client in clients:
        for obj in client.history:
            if obj.get("method") == "thread/tokenUsage/updated" and obj.get("params", {}).get("threadId") == thread_id:
                snapshots.append({"connection": client.label, "native": obj["params"]["tokenUsage"]})
    dump(run_dir / "usage-private.json", snapshots)
    totals = [x["native"]["total"] for x in snapshots]
    monotonic = bool(totals) and all(a["totalTokens"] <= b["totalTokens"] for a, b in zip(totals, totals[1:]))
    receipt = {
        "schema_version": 1, "kind": "native_tool_turn_recovery", "attempt": 1,
        "status": "passed" if assess(checks) else "failed",
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "platform": "macOS", "native_version": version,
        "executable_sha256": digest(executable.read_bytes()),
        "scope": "One owned synthetic dynamic-tool checkpoint, native turn interruption, new app-server process and same-thread resume on one Mac",
        "wall_seconds": round(time.monotonic() - started, 3),
        "model_configurations_observed": native_models,
        "checks": checks, "action_sequence": fixture.calls,
        "checkpoint_expected_sha256": digest(EXPECTED),
        "frozen_files": frozen,
        "failure": None if error is None else {"stage": failed_stage, "type": error["type"]},
        "owned_server_exit_codes": [c.proc.returncode for c in clients],
        "usage": {"scope": "Native same-thread cumulative snapshots; final total counted once when monotonic",
                  "snapshot_count": len(snapshots), "cumulative_total_monotonic": monotonic,
                  "final_native_total": totals[-1] if monotonic else None,
                  "native_retries": None, "billed_cost": None,
                  "coordinator_and_review_usage": None, "savings_claim": None},
        "private_protocol_sha256": {c.label: digest((run_dir / (c.label + ".protocol.jsonl")).read_bytes()) for c in clients},
        "limitations": [
            "One synthetic attempt and two native turns; no matched baseline or savings claim.",
            "Dynamic tool service is owned by this harness; no arbitrary shell, remote provider cancellation, network outage, host power-loss or independent-host restore was tested.",
            "The coordinator sends a concise continuation after resume; it does not replay messages or create a replacement native thread.",
            "The unchanged checkpoint and exact action sequence establish one observed effect, not an exactly-once distributed-system guarantee.",
            "Existing native authentication, configuration, caches and persisted session stores are used; worktree isolation is not account or service isolation.",
            "Full native protocol, identifiers and paths remain private. Hashes identify retained logs, not independent provider attestation.",
        ],
    }
    dump(run_dir / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "failure_stage": failed_stage,
                      "checks": checks, "wall_seconds": receipt["wall_seconds"]}))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True, help="Existing native executable; never installs a client")
    parser.add_argument("--run-dir", required=True, help="New private directory outside Git")
    parser.add_argument("--timeout", type=int, default=180, help="Maximum seconds for each of two model stages")
    raise SystemExit(run(parser.parse_args()))
