"""Bash workflow adapter for DeerFlow's native Gateway, not an MCP server.

Reference: bytedance/deer-flow@345f08be00c8a9495079b732a39b46aa9af1584e
skills/public/claude-to-deerflow/scripts/chat.sh:24-90,140-164;
backend/app/gateway/routers/thread_runs.py:223-242,923-939,1143-1168,1528-1560;
backend/app/gateway/auth/pat.py:28-40,53-116. Deviations: Bearer PAT auth,
background create/poll, stable private host artifacts, explicit arm/evidence exits.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid

from recipe import HERE, REPO, STATE, arm_settings, read, usage_database, write
sys.path.insert(0, str(HERE / "e2e"))
from receipt import compression_delta, compression_snapshot, gateway_observation

MODES = {"flash":(False,False,False), "standard":(True,False,False),
         "pro":(True,True,False), "ultra":(True,True,True)}
COUNTERS = ("llm_call_count", "total_tokens", "total_input_tokens", "total_output_tokens", "message_count")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api(method, path, body=None, headers=None):
    base = os.environ.get("DEERFLOW_URL", "http://127.0.0.1:3771").rstrip("/")
    if base != "http://127.0.0.1:3771" or not path.startswith("/threads"):
        raise ValueError("dispatch is restricted to the local DeerFlow threads/runs API")
    token_path = Path(os.environ["DEERFLOW_PAT_FILE"])
    if token_path.resolve().is_relative_to(REPO.resolve()):
        raise ValueError("PAT must be outside every worktree")
    with os.fdopen(os.open(token_path, os.O_RDONLY | os.O_NOFOLLOW), "r") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise ValueError("PAT file must be owned by the caller with mode 0600")
        token = source.read(4097).strip()
    if not re.fullmatch(r"dfp_[A-Za-z0-9]{16,128}", token):
        raise ValueError("invalid PAT file")
    request = Request(base + "/api/langgraph" + path,
        data=json.dumps(body).encode() if body is not None else None, method=method,
        headers={**(headers or {}), "Content-Type":"application/json", "Authorization":"Bearer " + token})
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=30) as response:
        raw = response.read(16_000_001)
        if len(raw) > 16_000_000:
            raise ValueError("DeerFlow response exceeds bound")
        data = json.loads(raw) if raw else {}
        trace = response.headers.get("X-Trace-Id")
    return data, trace


def require_server_arm(selection):
    """Inspect immutable launch labels, never Config.Env (which contains secrets)."""
    settings = read(STATE / "host.json")
    response = subprocess.run([settings["docker_bin"], "--context", "rootless", "inspect",
        "--format", "{{json .Config.Labels}}", "rw-deerflow-gateway"],
        capture_output=True, text=True, check=True, timeout=15)
    labels = json.loads(response.stdout)
    for name in ("arm", "model", "base_url"):
        if labels.get("com.native-agent-stack." + name) != selection[name]:
            raise ValueError("running DeerFlow service does not match the selected arm; coordinator must switch lifecycle")


def directory(run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("invalid stable run ID")
    run = STATE / "dispatch" / run_id
    if run.is_symlink():
        raise ValueError("run directory cannot be a symlink")
    return run


def pointers(run):
    return {"status_path":str(run / "status.json"), "result_path":str(run / "result.json"),
            "receipt_path":str(run / "receipt.json")}


def state_for(run_id, arm):
    run = directory(run_id)
    state = read(run / "status.json")
    if state["arm"] != arm:
        raise ValueError("arm must match the stored run")
    return run, state


def start(run_id, arm, prompt, mode, caller):
    if not prompt.strip() or mode not in MODES or not re.fullmatch(r"[A-Za-z0-9_./:-]{1,160}", caller):
        raise ValueError("a prompt, supported mode and bounded caller name are required")
    selection = arm_settings(read(STATE / "host.json") if (STATE / "host.json").is_file() else {}, arm)
    run = directory(run_id)
    run.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    with (STATE / "dispatch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if run.exists():
            _, state = state_for(run_id, arm)
            if state.get("prompt_sha256") != digest or state.get("mode") != mode or state.get("caller") != caller:
                raise ValueError("stable run ID is already assigned to another invocation")
            if state.get("run_id"):
                return 0, {**pointers(run), "thread_id":state["thread_id"], "run_id":state["run_id"]}
        else:
            run.mkdir(mode=0o700)
            state = {**selection, "status":"starting", "start_epoch":time.time(), "end_epoch":None,
                "mode":mode, "caller":caller, "prompt_sha256":digest, "idempotency_key":str(uuid.uuid4())}
            write(run / "status.json", state)
            write(run / "result.json", {"verdict":"incomplete", "exit_code":3, **pointers(run)})
        try:
            require_server_arm(selection)
            for other in run.parent.glob("*/status.json"):
                if other.parent != run and read(other).get("status") in {"starting", "pending", "running"}:
                    raise ValueError("another dispatch is active; wait for it first")
            if "compression_before" not in state:
                state["compression_before"] = compression_snapshot(arm)
            if not state.get("thread_id"):
                thread, trace = api("POST", "/threads", {})
                state.update(thread_id=thread["thread_id"], trace_id=trace)
                write(run / "status.json", state)
            tid = state["thread_id"]
            thinking, plan, children = MODES[mode]
            body = {"assistant_id":"lead_agent", "input":{"messages":[{"type":"human",
                "content":[{"type":"text","text":prompt}]}]}, "config":{"recursion_limit":1000},
                "context":{"thinking_enabled":thinking, "is_plan_mode":plan,
                    "subagent_enabled":children, "thread_id":tid, "model_name":"worker"},
                "metadata":{"source":"claude-code", "caller":caller, "arm":arm, "dispatch_id":run_id},
                "on_disconnect":"continue"}
            native, trace = api("POST", "/threads/" + quote(tid, safe="") + "/runs", body,
                                {"Idempotency-Key":state["idempotency_key"]})
            state.update(run_id=native["run_id"], status=native["status"], trace_id=trace)
            write(run / "status.json", state)
            ledger = STATE / "dispatch.jsonl"
            with os.fdopen(os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600), "a") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(json.dumps({"ts":time.time(), "thread_id":tid, "run_id":state["run_id"],
                    "status":state["status"], "trace_id":trace, "caller":caller, "arm":arm}) + "\n")
            return 0, {**pointers(run), "thread_id":tid, "run_id":state["run_id"]}
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            # A timed-out create may already have started on the server. Keep
            # the slot occupied; retry this same ID/body/Idempotency-Key safely.
            code = 3 if state.get("thread_id") else 2
            state.update(status="pending" if code == 3 else "setup-failure", error_class=type(exc).__name__)
            write(run / "status.json", state)
            write(run / "result.json", {"verdict":"incomplete" if code == 3 else "setup-failure", "exit_code":code, **pointers(run)})
            return code, {**pointers(run), "exit_code":code, "error_class":type(exc).__name__}


def run_path(state):
    return "/threads/" + quote(state["thread_id"], safe="") + "/runs/" + quote(state["run_id"], safe="")


def wait_run(run_id, arm, timeout, interval):
    if timeout < 0 or interval <= 0:
        raise ValueError("timeout must be nonnegative and interval positive")
    run, state = state_for(run_id, arm)
    deadline = time.monotonic() + timeout
    while True:
        native, trace = api("GET", run_path(state))
        status = native.get("status")
        state.update(status=status, trace_id=trace, server_reported={
            k:native[k] if type(native.get(k)) is int and native[k] >= 0 else None for k in COUNTERS})
        write(run / "status.json", state)
        if status not in {"pending", "running"}:
            if state.get("end_epoch") is None:
                state.update(end_epoch=time.time(), compression_after=compression_snapshot(arm))
                write(run / "status.json", state)
            code = 0 if status == "success" else 1 if status in {"error", "timeout", "cancelled"} else 3
            write(run / "result.json", {**pointers(run), "status":status, "exit_code":code if code else 3,
                "verdict":"negative" if code == 1 else "incomplete"})
            return code, {**pointers(run), "status":status, "stop_reason":native.get("stop_reason"),
                          **state["server_reported"], "updated_at":native.get("updated_at")}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return 3, {**pointers(run), "status":status, "exit_code":3}
        time.sleep(min(interval, remaining))


def result_run(run_id, arm):
    code, observed = wait_run(run_id, arm, 0, 1)
    run, state = state_for(run_id, arm)
    if code:
        return code, observed
    messages, before = [], None
    for _ in range(50):
        path = run_path(state) + "/messages?limit=200" + ("&before_seq=" + str(before) if before is not None else "")
        page, _ = api("GET", path)
        data = page["data"]
        if not isinstance(data, list):
            raise ValueError("unsupported native messages page")
        messages = data + messages
        if not page["has_more"]:
            break
        next_before = min(m["seq"] for m in data)
        if before is not None and next_before >= before:
            raise ValueError("messages pagination did not advance")
        before = next_before
    else:
        return 3, {**pointers(run), "exit_code":3, "status":"message-bound-reached"}
    answer = ""
    correlations = set()
    for event in messages:
        # /messages returns RunEvent envelopes, unlike chat.sh's SSE values.
        # DeerFlow@345f08be runtime/journal.py:13,124,153-173 stores model_dump
        # in event.content; runtime/events/store/base.py:32-43,54-55 defines it.
        message = event.get("content")
        if event.get("category") != "message" or not isinstance(message, dict):
            continue
        headers = (message.get("response_metadata") or {}).get("headers", {})
        for key, value in headers.items():
            if key.lower() == "x-correlation-id" and isinstance(value, str):
                correlations.add(value)
        caller = event.get("metadata", {}).get("caller", "lead_agent")
        if (message.get("type") == "ai" and not message.get("tool_calls")
                and caller == "lead_agent" and not message.get("additional_kwargs", {}).get("hide_from_ui")):
            content = message.get("content", "")
            text = content if isinstance(content, str) else "\n".join(
                p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in {"text", "output_text"})
            if text.strip():
                answer = text
    gateway = gateway_observation(usage_database(arm), state, correlations)
    counters = state["server_reported"]
    complete = (bool(answer) and gateway.get("evidence_complete")
                and type(counters.get("llm_call_count")) is int and counters["llm_call_count"] > 0
                and len(correlations) == counters["llm_call_count"])
    code = 0 if complete else 3
    selection = {k:state[k] for k in ("arm", "model", "base_url", "header_names", "reasoning_effort")}
    receipt = {**selection, "verdict":"pass" if complete else "incomplete", "exit_code":code,
        "scope":"native run completion and independent entry-gateway evidence; no answer-quality grader",
        "server_reported":counters, "gateway":gateway,
        "compression":compression_delta(state.get("compression_before", {}), state.get("compression_after", {})),
        "invocation_count":1, "answer_sha256":hashlib.sha256(answer.encode()).hexdigest()}
    write(run / "receipt.json", receipt)
    result = {**pointers(run), "exit_code":code, "verdict":receipt["verdict"], "answer":answer}
    write(run / "result.json", result)
    return code, result


def cancel(run_id, arm):
    run, state = state_for(run_id, arm)
    api("POST", run_path(state) + "/cancel", {})
    return 3, {**pointers(run), "status":"cancel-requested", "exit_code":3}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "wait", "result", "cancel"))
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arm", choices=("control", "engines-on"), default=os.environ.get("RUNTIME_WORKER_ARM", "control"))
    parser.add_argument("--caller", default="claude-code/workflow")
    parser.add_argument("--mode", choices=tuple(MODES), default="pro")
    parser.add_argument("--timeout", type=float, default=540)
    parser.add_argument("--interval", type=float, default=10)
    # The prompt may follow the options (start --run-id ID PROMPT). parse_args() on Python 3.12 binds the optional
    # positional before the options and then rejects PROMPT; intermixed parsing is argparse's documented mode for it.
    args = parser.parse_intermixed_args()
    os.umask(0o077)
    try:
        if args.action == "start":
            code, result = start(args.run_id, args.arm, args.prompt or "", args.mode, args.caller)
        elif args.action == "wait":
            code, result = wait_run(args.run_id, args.arm, args.timeout, args.interval)
        elif args.action == "result":
            code, result = result_run(args.run_id, args.arm)
        else:
            code, result = cancel(args.run_id, args.arm)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        code, result = 2, {"exit_code":2, "error_class":type(exc).__name__}
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
