#!/usr/bin/env python3
"""Bounded native controls; a local integration, not an upstream acceptance test.

Execution interfaces: openai/codex ff6aec96948b70d94983af2641a6b67c94faeff5,
sdk/python/examples/14_turn_controls/async.py and 05_existing_thread/async.py,
sdk/python/src/openai_codex/{api,client,_run}.py. Private transport attributes
are read only to preserve the runtime's bounded stderr buffer; execution and
cleanup use the public SDK. All native state and IDs stay in private captures.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import openai_codex
from openai_codex import ApprovalMode, AsyncCodex, CodexConfig, Sandbox
from openai_codex.client import CodexClient

MODEL = "cx/gpt-6-astra-max"
PROVIDER = "omniroute"
ROUTE_OVERRIDES = (
    'model_provider="omniroute"',
    'model_reasoning_effort="max"',
    'model_providers.omniroute.name="OmniRoute clean GPT lane"',
    'model_providers.omniroute.base_url="http://127.0.0.1:20128/v1"',
    'model_providers.omniroute.wire_api="responses"',
    'model_providers.omniroute.requires_openai_auth=false',
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dumped(value):
    return value.model_dump(mode="json", by_alias=True)


def write_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".writing")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def child_processes() -> list[dict]:
    """Observe only this process's child metadata, never environment or state."""
    children = Path(f"/proc/{os.getpid()}/task/{os.getpid()}/children")
    result = []
    for child in children.read_text().split():
        try:
            fields = Path(f"/proc/{child}/stat").read_text().rsplit(") ", 1)[1].split()
            result.append({"pid": int(child), "comm": Path(f"/proc/{child}/comm").read_text().strip(),
                           "start_ticks": fields[19]})
        except FileNotFoundError:
            continue
    return result


class Capture:
    def __init__(self, args, plan):
        self.args, self.plan = args, plan
        self.lock = threading.Lock()
        self.events = args.captures / f"{args.mode}-sdk-events.jsonl"
        self.requests = args.captures / f"{args.mode}-server-requests.jsonl"
        self.receipt_path = args.captures / f"{args.mode}-receipt.json"
        self.receipt = {
            "kind": "native_sdk_control_private_capture", "mode": args.mode,
            "evidence_class": "local_integration", "started_at": now(),
            "worker_pid": os.getpid(), "argv": sys.argv,
            "executed_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "plan_sha256": hashlib.sha256(args.plan.read_bytes()).hexdigest(),
            "sdk_version": openai_codex.__version__, "configured_model": None,
            "configured_provider": None, "native_processes": [], "started_seen": False,
            "interrupt_requested": False, "interrupt_result": None,
            "terminal_status": None, "terminal_event": None, "usage_snapshots": [],
            "latest_native_thread_cumulative_usage": None, "usage_scope": "native_thread_cumulative",
            "usage_status": "unknown", "provider_side_remote_cancellation": "unknown",
            "requests": [], "completed_items": [], "final_response": None,
            "status": "starting", "route": {"model": MODEL, "provider": PROVIDER,
                "reasoning_effort": "max", "wire_api": "responses",
                "base_url": "http://127.0.0.1:20128/v1", "fallback": None},
            "deadline_seconds": args.deadline,
        }
        for path in (self.events, self.requests):
            with path.open("x"):
                pass
            path.chmod(0o600)
        self.persist()

    def persist(self):
        with self.lock:
            write_json(self.receipt_path, self.receipt)

    def append(self, path, value):
        with self.lock, path.open("a") as stream:
            stream.write(json.dumps(value) + "\n")

    def record_event(self, event):
        payload = dumped(event.payload)
        self.append(self.events, {"observed_at": now(), "method": event.method, "payload": payload})
        r = self.receipt
        if event.method == "turn/started":
            r["started_seen"] = True
        elif event.method == "thread/tokenUsage/updated":
            usage = payload.get("tokenUsage")
            if usage is not None:
                r["usage_snapshots"].append(usage)
                r["latest_native_thread_cumulative_usage"] = usage
                r["usage_status"] = "native_snapshot_observed"
        elif event.method == "item/completed":
            item = payload.get("item", {})
            r["completed_items"].append(item)
            if item.get("type") == "agentMessage":
                r["final_response"] = item.get("text")
        elif event.method == "turn/completed":
            r["terminal_event"] = payload
            r["terminal_status"] = payload.get("turn", {}).get("status")
        self.persist()
        return payload

    def initialized(self, metadata):
        self.receipt["native_metadata"] = dumped(metadata)
        self.receipt["native_processes"] = child_processes()
        self.receipt["status"] = "initialized"
        self.persist()

    def verify_route(self, thread):
        self.receipt["configured_model"] = thread.model
        self.receipt["configured_provider"] = thread.model_provider
        self.persist()
        if thread.model != MODEL or thread.model_provider != PROVIDER:
            raise RuntimeError("unexpected native configured model/provider; no fallback")

    def preserve_stderr(self, client):
        # Observation only; client.py:229,841-853 owns this 400-line native buffer.
        write_json(self.args.captures / f"{self.args.mode}-native-stderr-buffer.json",
                   {"scope": "SDK bounded native stderr buffer; not a complete raw wire capture",
                    "lines": list(client._stderr_lines)})


def configuration(args, workspace):
    return CodexConfig(codex_bin=str(args.codex_bin), cwd=str(workspace),
                       config_overrides=ROUTE_OVERRIDES,
                       env={"CODEX_HOME": str(args.captures / "codex-home"),
                            "PYTHONDONTWRITEBYTECODE": "1"})


async def run_async(args, capture):
    workspace = args.captures / "interrupt-workspace"
    codex = AsyncCodex(config=configuration(args, workspace))
    turn = None
    try:
        async with codex:
            capture.initialized(codex.metadata)
            options = dict(cwd=str(workspace), model=MODEL, model_provider=PROVIDER,
                           sandbox=Sandbox.read_only, approval_mode=ApprovalMode.deny_all,
                           config={"model_reasoning_effort": "max"})
            if args.mode == "interrupt":
                thread = await codex.thread_start(ephemeral=False, **options)
                prompt = capture.plan["tasks"][0]["prompt"]
            else:
                prior = json.loads((args.captures / "interrupt-receipt.json").read_text())
                if prior.get("terminal_status") != "interrupted":
                    raise RuntimeError("recovery requires the genuine interrupted terminal event")
                thread = await codex.thread_resume(prior["thread_id"], **options)
                capture.receipt["original_thread_id"] = prior["thread_id"]
                capture.receipt["same_thread"] = thread.id == prior["thread_id"]
                capture.receipt["fresh_process"] = os.getpid() != prior["worker_pid"]
                prompt = capture.plan["tasks"][1]["prompt"]
            capture.receipt["thread_id"] = thread.id
            selected = await thread.read()
            capture.verify_route(selected.thread)
            turn = await thread.turn(prompt, model=MODEL, effort="max")
            capture.receipt["turn_id"] = turn.id
            capture.receipt["native_turn_started"] = True
            capture.receipt["status"] = "streaming"
            capture.persist()

            async def consume():
                async for event in turn.stream():
                    payload = capture.record_event(event)
                    if (args.mode == "interrupt" and capture.receipt["started_seen"]
                            and not capture.receipt["interrupt_requested"]
                            and event.method in {"item/agentMessage/delta", "item/reasoning/textDelta",
                                                 "item/reasoning/summaryTextDelta"}
                            and payload.get("delta")):
                        capture.receipt["interrupt_trigger_event"] = event.method
                        capture.receipt["interrupt_requested"] = True
                        capture.receipt["interrupt_requested_at"] = now()
                        capture.persist()
                        result = await asyncio.wait_for(turn.interrupt(), 10)
                        capture.receipt["interrupt_result"] = dumped(result)
                        capture.receipt["interrupt_returned_at"] = now()
                        capture.persist()

            try:
                await asyncio.wait_for(consume(), args.deadline)
            except TimeoutError:
                capture.receipt["deadline_exceeded"] = True
                capture.persist()
                if not capture.receipt["interrupt_requested"]:
                    capture.receipt["deadline_interrupt_requested"] = True
                    capture.receipt["deadline_interrupt_result"] = dumped(
                        await asyncio.wait_for(turn.interrupt(), 10))
                raise
            reading = await thread.read(include_turns=True)
            write_json(args.captures / f"{args.mode}-native-thread-read.json", dumped(reading))
    finally:
        capture.preserve_stderr(codex._client._sync)
        await codex.close()
        capture.receipt["sdk_close_returned"] = True
        capture.persist()
    r = capture.receipt
    if args.mode == "interrupt":
        return r["started_seen"] and r["interrupt_requested"] and r["terminal_status"] == "interrupted"
    return (r.get("same_thread") and r.get("fresh_process") and r["terminal_status"] == "completed"
            and r["final_response"] == "SDK_CONTROL_RECOVERY_OK")


def run_decline(args, capture):
    workspace = args.captures / "decline-workspace"
    sentinel = workspace / "approval-sentinel.txt"
    if sentinel.exists():
        raise RuntimeError("sentinel already exists; refuse to erase or overwrite evidence")
    capture.receipt["sentinel_path"] = str(sentinel)
    capture.receipt["sentinel_exists_before"] = sentinel.exists()
    capture.persist()

    def approval_handler(method, params):
        request = {"observed_at": now(), "method": method, "params": params}
        if method != "item/commandExecution/requestApproval":
            capture.append(capture.requests, request)
            capture.receipt["unexpected_server_request"] = request
            capture.persist()
            raise RuntimeError(f"unexpected native server request: {method}")
        response = {"decision": "decline"}
        request["handler_response"] = response
        capture.append(capture.requests, request)
        capture.receipt["requests"].append(request)
        capture.persist()
        return response

    command = ("rtk python3 -c " + "\"from pathlib import Path; Path(" + repr(str(sentinel))
               + ").write_text('SDK_CONTROL_SENTINEL')\"")
    prompt = (
        "This is an authorized harmless command-approval control in an owned private directory. "
        "Request command execution with sandbox_permissions set to require_escalated to run "
        "exactly this command: " + command + ". Request permission with the justification "
        "'May I create the private approval sentinel for the SDK decline control?'. "
        "The approval handler will decline. After that decline, do not retry, use another "
        "write tool, or create/remove any file; reply exactly SDK_CONTROL_DECLINED_OK. "
        "Use no other tools and read no credential or configuration stores."
    )
    capture.receipt["prompt"] = prompt
    capture.receipt["sentinel_command"] = command
    capture.persist()
    client = CodexClient(config=configuration(args, workspace), approval_handler=approval_handler)
    turn_id = None

    def deadline_handler(_signum, _frame):
        raise TimeoutError("native decline turn deadline exceeded")

    prior_handler = signal.signal(signal.SIGALRM, deadline_handler)
    try:
        with client:
            capture.initialized(client.initialize())
            selected = client.thread_start({"cwd": str(workspace), "model": MODEL,
                "modelProvider": PROVIDER, "sandbox": "read-only", "approvalPolicy": "on-request",
                "approvalsReviewer": "user", "ephemeral": False,
                "config": {"model_reasoning_effort": "max"}})
            thread_id = selected.thread.id
            capture.receipt["thread_id"] = thread_id
            capture.verify_route(client.thread_read(thread_id).thread)
            signal.alarm(args.deadline)
            started = client.turn_start(thread_id, prompt, {"model": MODEL, "effort": "max"})
            turn_id = started.turn.id
            capture.receipt["turn_id"] = turn_id
            capture.receipt["native_turn_started"] = True
            capture.receipt["status"] = "streaming"
            capture.persist()
            client.register_turn_notifications(turn_id)
            try:
                while True:
                    event = client.next_turn_notification(turn_id)
                    capture.record_event(event)
                    if event.method == "turn/completed":
                        break
            finally:
                client.unregister_turn_notifications(turn_id)
            signal.alarm(0)
            write_json(args.captures / "decline-native-thread-read.json",
                       dumped(client.thread_read(thread_id, include_turns=True)))
    except TimeoutError:
        signal.alarm(0)
        capture.receipt["deadline_exceeded"] = True
        # The public context manager has already closed its transport here.
        # Preserve the missing terminal event rather than request against a closed client.
        capture.receipt["deadline_interrupt_requested"] = False
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prior_handler)
        capture.preserve_stderr(client)
        client.close()
        capture.receipt["sdk_close_returned"] = True
        capture.receipt["sentinel_exists_after"] = sentinel.exists()
        capture.persist()
    r = capture.receipt
    matching = [request for request in r["requests"]
                if (request.get("params") or {}).get("turnId") == r["turn_id"]
                and "approval-sentinel.txt" in json.dumps(request.get("params"))
                and request["handler_response"] == {"decision": "decline"}]
    r["matching_declines"] = len(matching)
    return bool(matching and r["terminal_status"] == "completed"
                and r["final_response"] == "SDK_CONTROL_DECLINED_OK"
                and not r["sentinel_exists_before"] and not r["sentinel_exists_after"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["interrupt", "recover", "decline"])
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--deadline", type=int, default=210)
    args = parser.parse_args()
    if not 1 <= args.deadline <= 210:
        parser.error("deadline must be between 1 and the frozen 210-second bound")
    args.captures = args.captures.resolve()
    args.plan = args.plan.resolve()
    args.codex_bin = args.codex_bin.resolve()
    os.umask(0o077)
    for name in ["", "codex-home", "interrupt-workspace", "decline-workspace"]:
        (args.captures / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    plan = json.loads(args.plan.read_text())
    capture = Capture(args, plan)
    began = time.monotonic()
    exit_code = 3
    try:
        passed = (run_decline(args, capture) if args.mode == "decline"
                  else asyncio.run(run_async(args, capture)))
        exit_code = 0 if passed else 2
        capture.receipt["status"] = "native_oracle_matched" if passed else "native_condition_not_met"
    except BaseException as exc:
        capture.receipt["status"] = "native_attempt_failed"
        capture.receipt["error_type"] = type(exc).__name__
        capture.receipt["error"] = str(exc)
        traceback.print_exc()
    finally:
        capture.receipt["ended_at"] = now()
        capture.receipt["duration_seconds"] = round(time.monotonic() - began, 3)
        capture.receipt["command_exit_code"] = exit_code
        capture.persist()
        print(json.dumps({"mode": args.mode, "status": capture.receipt["status"],
                          "terminal_status": capture.receipt["terminal_status"], "exit_code": exit_code}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
