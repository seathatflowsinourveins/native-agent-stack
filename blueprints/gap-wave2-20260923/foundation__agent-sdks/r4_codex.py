#!/usr/bin/env python3
"""Round 4: Codex SDK against the loopback vLLM provider (agent-sdks gap wave, 2026-09-23).

The CODEX_HOME passed in is a fresh directory whose config.toml selects a custom model provider
(`localvllm`, wire_api responses, base_url http://127.0.0.1:28431/v1) and has no auth.json, so
no account or credential is involved. Phases:

  session  process 1: thread/start with one dynamic tool (vault_lookup); turn 1 must call it and
           reply with the value; turn 2 asks for a long listing and is interrupted after streaming
           starts, with provider /metrics sampled before, at the interrupt and after two settle
           windows, next to the SDK token-usage notifications and the rollout token_count events.
  resume   process 2 (new OS process): thread/resume by id with a decoy tool value; turn 3 asks
           for the turn-1 value without calling any tool.
  events   gap 10: one thread driven through client requests and a turn so that more documented
           notification types arrive; collectors drain the turn queue and the global queue.

Usage: r4_codex.py PHASE --codex-bin BIN --codex-home HOME --workspace WS --state PRIVATE --out OUT
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codex_probe import TOOL_SPEC, collect, rollout_token_counts, summarize  # noqa: E402
from r4_common import delta, metrics, wait_idle  # noqa: E402

from pydantic import BaseModel, ConfigDict  # noqa: E402

from openai_codex.client import CodexClient, CodexConfig  # noqa: E402
from openai_codex.generated.notification_registry import NOTIFICATION_MODELS  # noqa: E402
from openai_codex.models import UnknownNotification  # noqa: E402

MODEL = "qwen3-4b"
LONG = ("This is a plain writing task: do not use any tool and do not refuse. In your reply, write the "
        "integers from 1 to 3000, one per line, each followed by a colon and its square.")


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


def raw(client: CodexClient, method: str, params: dict | None) -> dict:
    return client.request(method, params, response_model=Loose).model_dump(mode="json", by_alias=True)


class Host:
    def __init__(self, value: str):
        self.value = value
        self.calls: list[dict] = []
        self.other: list[str] = []

    def __call__(self, method: str, params: dict | None) -> dict:
        if method == "item/tool/call":
            p = params or {}
            ok = p.get("tool") == "vault_lookup"
            self.calls.append({"at": time.time(), "tool": p.get("tool"), "arguments": p.get("arguments"),
                               "answered": ok})
            return {"contentItems": [{"type": "inputText", "text": self.value if ok else "unknown tool"}],
                    "success": ok}
        self.other.append(method)
        if method.endswith("requestApproval"):
            return {"decision": "decline"}
        return {}


def install_tap(client: CodexClient, sink: list) -> None:
    """Record every notification the SDK receives, before routing (fix round: gap-9 typed check)."""
    router = client._router
    original = router.route_notification

    def tap(n):
        sink.append({"at": time.time(), "method": n.method, "typed": not isinstance(n.payload, UnknownNotification)})
        return original(n)

    router.route_notification = tap


def tap_summary(client: CodexClient, sink: list) -> dict:
    counts: dict[str, int] = {}
    for e in sink:
        counts[e["method"]] = counts.get(e["method"], 0) + 1
    unknown = client._coerce_notification("zzz/unknown", {})
    malformed = client._coerce_notification("turn/completed", {"unexpected": 1})
    return {"tapped_total": len(sink), "tapped_counts": dict(sorted(counts.items())),
            "tapped_untyped": sorted({e["method"] for e in sink if not e["typed"]}),
            "tapped_undocumented": sorted(set(counts) - set(NOTIFICATION_MODELS)),
            "detector": {"unknown_method_untyped": isinstance(unknown.payload, UnknownNotification),
                         "malformed_known_method_untyped": isinstance(malformed.payload, UnknownNotification)}}


def cfg(args) -> CodexConfig:
    return CodexConfig(codex_bin=args.codex_bin, cwd=str(args.workspace), env={"CODEX_HOME": str(args.codex_home)})


def final_text(client: CodexClient, thread_id: str) -> str:
    data = raw(client, "thread/read", {"threadId": thread_id, "includeTurns": True})
    turns = (data.get("thread") or {}).get("turns") or []
    msgs = [it.get("text") or "" for it in (turns[-1].get("items") if turns else []) if it.get("type") == "agentMessage"]
    return msgs[-1].strip() if msgs else ""


def phase_session(args) -> dict:
    value = "vx-" + secrets.token_hex(6)
    host = Host(value)
    rec: dict = {"phase": "session", "pid": os.getpid()}
    sink: list = []
    with CodexClient(cfg(args), approval_handler=host) as client:
        if args.tap:
            install_tap(client, sink)
        client.initialize()
        conf = raw(client, "config/read", {"cwd": str(args.workspace), "includeLayers": False}).get("config") or {}
        rec["effective_provider"] = {"model": conf.get("model"), "model_provider": conf.get("model_provider"),
                                     "providers": {k: {kk: vv for kk, vv in (v or {}).items() if kk in ("base_url", "wire_api", "name")}
                                                   for k, v in (conf.get("model_providers") or {}).items()}}
        rec["account"] = raw(client, "account/read", {})
        thread_id = raw(client, "thread/start", {
            "cwd": str(args.workspace), "model": MODEL, "ephemeral": False, "sandbox": "read-only",
            "approvalPolicy": "never", "dynamicTools": [TOOL_SPEC],
            "developerInstructions": "You are a test worker. Use only the vault_lookup tool when asked; run no shell commands."})["thread"]["id"]
        # turn 1: custom tool round trip
        m0 = wait_idle()
        t1 = client.turn_start(thread_id, "Call the vault_lookup tool with key \"alpha\". Then reply with only the exact "
                               "value it returned.", {"model": MODEL})
        ev1, done1 = collect(client, t1.turn.id, time.time() + args.deadline)
        m1 = metrics()
        rec["turn1"] = {**summarize(ev1), "turn_completed": done1, "final_answer": final_text(client, thread_id)[:300],
                        "tool_host_calls": host.calls, "provider_delta": delta(m0, m1)}
        rec["turn1"]["answer_contains_value"] = value in rec["turn1"]["final_answer"]
        rec["turn1"]["tool_round_trip"] = (bool(host.calls) and all(c["answered"] for c in host.calls)
                                          and rec["turn1"]["answer_contains_value"])
        # turn 2: interrupted essay with provider sampling
        s_before = wait_idle()
        t2 = client.turn_start(thread_id, LONG, {"model": MODEL})
        first = threading.Event()
        box: dict = {}

        def on_event(e):
            if e["method"] == "item/agentMessage/delta":
                first.set()

        th = threading.Thread(target=lambda: box.update(zip(("events", "completed"),
                                                            collect(client, t2.turn.id, time.time() + args.deadline, on_event))),
                              daemon=True)
        th.start()
        first.wait(args.first_delta_timeout)
        rec_t2: dict = {"streaming_observed_before_interrupt": first.is_set()}
        time.sleep(args.stream_seconds if first.is_set() else 0)
        s_interrupt = metrics()
        rec_t2["interrupt_requested_at"] = time.time()
        try:
            rec_t2["interrupt_response"] = client.turn_interrupt(thread_id, t2.turn.id).model_dump(mode="json", by_alias=True)
        except Exception as error:  # keep the rest of the record (e.g. the turn ended before the interrupt)
            rec_t2["interrupt_error"] = f"{type(error).__name__}: {str(error)[:300]}"
        th.join(args.deadline)
        ev2, done2 = box.get("events", []), box.get("completed")
        s_1s = metrics()
        time.sleep(args.settle)
        s_settle1 = metrics()
        time.sleep(args.settle)
        s_settle2 = metrics()
        path = (raw(client, "thread/read", {"threadId": thread_id, "includeTurns": False}).get("thread") or {}).get("path")
        rec_t2.update(summarize(ev2))
        rec_t2["turn_completed"] = done2
        rec_t2["samples"] = {"before": s_before, "at_interrupt": s_interrupt, "after_completed_1s": s_1s,
                             "settle1": s_settle1, "settle2": s_settle2}
        rec_t2["provider_delta_before_to_interrupt"] = delta(s_before, s_interrupt)
        rec_t2["provider_delta_before_to_settle1"] = delta(s_before, s_settle1)
        rec_t2["provider_delta_settle1_to_settle2"] = delta(s_settle1, s_settle2)
        rec_t2["running_at_settle1"] = s_settle1.get("vllm:num_requests_running")
        rec_t2["consumption_stopped"] = (rec_t2["provider_delta_settle1_to_settle2"]["vllm:generation_tokens_total"] == 0
                                         and not s_settle1.get("vllm:num_requests_running"))
        rec_t2["sdk_token_usage_notifications"] = [e.get("tokenUsage") for e in ev2 if e.get("tokenUsage")]
        rec_t2["rollout"] = rollout_token_counts(path)
        rec["turn2_interrupt"] = rec_t2
        if args.tap:
            rec["tap"] = tap_summary(client, sink)
    args.state.write_text(json.dumps({"thread_id": thread_id, "value": value}))
    os.chmod(args.state, 0o600)
    rec["thread_id_private_in_state"] = True
    return rec


def phase_resume(args) -> dict:
    st = json.loads(args.state.read_text())
    decoy = "decoy-" + secrets.token_hex(4)
    host = Host(decoy)
    rec: dict = {"phase": "resume", "pid": os.getpid()}
    sink: list = []
    with CodexClient(cfg(args), approval_handler=host) as client:
        if args.tap:
            install_tap(client, sink)
        client.initialize()
        resumed = raw(client, "thread/resume", {"threadId": st["thread_id"], "model": MODEL, "cwd": str(args.workspace),
                                                "sandbox": "read-only", "approvalPolicy": "never"})
        rec["resumed_same_thread"] = (resumed.get("thread") or {}).get("id") == st["thread_id"]
        m0 = wait_idle()
        t3 = client.turn_start(st["thread_id"], "Without calling any tool, what exact value did vault_lookup return "
                               "earlier in this conversation? Reply with only that value.", {"model": MODEL})
        ev, done = collect(client, t3.turn.id, time.time() + args.deadline)
        rec.update(summarize(ev))
        rec["turn_completed"] = done
        rec["final_answer"] = final_text(client, st["thread_id"])[:300]
        rec["provider_delta"] = delta(m0, metrics())
        if args.tap:
            rec["tap"] = tap_summary(client, sink)
    rec["tool_calls_in_resume"] = host.calls
    rec["answer_contains_turn1_value"] = st["value"] in rec["final_answer"]
    rec["answer_contains_decoy"] = decoy in rec["final_answer"]
    rec["resume_recall"] = rec["resumed_same_thread"] and rec["answer_contains_turn1_value"] and not host.calls
    return rec


def phase_events(args) -> dict:
    value = "ve-" + secrets.token_hex(6)
    host = Host(value)
    events: list[dict] = []
    lock = threading.Lock()
    rec: dict = {"phase": "events", "pid": os.getpid(), "steps": []}

    def record(source, n):
        with lock:
            events.append({"at": time.time(), "source": source, "method": n.method,
                           "typed": not isinstance(n.payload, UnknownNotification)})

    def step(name, fn):
        try:
            out = fn()
            rec["steps"].append({"step": name, "ok": True, "keys": sorted(out)[:10] if isinstance(out, dict) else None})
        except Exception as error:
            rec["steps"].append({"step": name, "ok": False, "error": f"{type(error).__name__}: {str(error)[:300]}"})

    with CodexClient(cfg(args), approval_handler=host) as client:
        client.initialize()

        def drain():
            try:
                while True:
                    record("global", client.next_notification())
            except Exception as error:
                rec["global_drain_end"] = type(error).__name__

        threading.Thread(target=drain, daemon=True).start()
        tid = raw(client, "thread/start", {"cwd": str(args.workspace), "model": MODEL, "ephemeral": False,
                                           "sandbox": "workspace-write", "approvalPolicy": "never",
                                           "dynamicTools": [TOOL_SPEC],
                                           "developerInstructions": "You are a test worker in a disposable workspace."})["thread"]["id"]
        step("thread/name/set", lambda: raw(client, "thread/name/set", {"threadId": tid, "name": "r4-events"}))
        prompt = ("Do these steps in order: 1) call your update_plan tool with a three-step plan; 2) run the shell "
                  "command `echo events-ok`; 3) create the file notes.txt containing the line hello with apply_patch; "
                  "4) call vault_lookup with key \"alpha\". Finally reply with the value it returned.")
        t = client.turn_start(tid, prompt, {"model": MODEL})
        end = time.time() + args.deadline
        while time.time() < end:
            n = client.next_turn_notification(t.turn.id)
            record("turn", n)
            if n.method == "turn/completed":
                break
        step("thread/compact/start", lambda: raw(client, "thread/compact/start", {"threadId": tid}))
        time.sleep(15)
        step("thread/archive", lambda: raw(client, "thread/archive", {"threadId": tid}))
        step("thread/unarchive", lambda: raw(client, "thread/unarchive", {"threadId": tid}))
        step("fuzzyFileSearch/sessionStart", lambda: raw(client, "fuzzyFileSearch/sessionStart",
                                                          {"sessionId": "r4", "roots": [str(args.workspace)]}))
        step("fuzzyFileSearch/sessionUpdate", lambda: raw(client, "fuzzyFileSearch/sessionUpdate",
                                                           {"sessionId": "r4", "query": "notes"}))
        time.sleep(3)
        step("fuzzyFileSearch/sessionStop", lambda: raw(client, "fuzzyFileSearch/sessionStop", {"sessionId": "r4"}))
        step("command/exec", lambda: raw(client, "command/exec", {"command": ["echo", "exec-ok"], "cwd": str(args.workspace),
                                                                  "streamStdoutStderr": True}))
        step("thread/unsubscribe", lambda: raw(client, "thread/unsubscribe", {"threadId": tid}))
        time.sleep(3)
    counts: dict[str, int] = {}
    for e in events:
        counts[e["method"]] = counts.get(e["method"], 0) + 1
    documented = set(NOTIFICATION_MODELS)
    rec.update({"method_counts": dict(sorted(counts.items())),
                "untyped_methods": sorted({e["method"] for e in events if not e["typed"]}),
                "documented_types": len(documented),
                "received_documented": sorted(set(counts) & documented),
                "received_undocumented": sorted(set(counts) - documented),
                "tool_calls": host.calls, "other_server_requests": sorted(set(host.other)),
                "notes_txt_created": (args.workspace / "notes.txt").is_file()})
    rec["received_documented_count"] = len(rec["received_documented"])
    return rec


def phase_events2(args) -> dict:
    """Gap 10, second pass: tap every notification the SDK routes, then drive many client requests.

    The tap wraps the SDK's private MessageRouter.route_notification, so turn-routed notifications of
    turns this script never subscribed to (compaction, shell command, queued and goal turns) are seen
    before the router prunes them. The app-server runs with HOME set to a temp directory.
    """
    import base64
    value = "ve-" + secrets.token_hex(6)
    host = Host(value)
    events: list[dict] = []
    lock = threading.Lock()
    rec: dict = {"phase": "events2", "pid": os.getpid(), "steps": []}
    ws = args.workspace

    def step(name, fn, pause=0.0):
        try:
            out = fn()
            rec["steps"].append({"step": name, "ok": True, "at": time.time(),
                                 "result_keys": sorted(out)[:12] if isinstance(out, dict) else None})
            time.sleep(pause)
            return out
        except Exception as error:
            rec["steps"].append({"step": name, "ok": False, "at": time.time(),
                                 "error": f"{type(error).__name__}: {str(error)[:300]}"})
            time.sleep(pause)
            return None

    def wait_turns_idle(tid, timeout=180):
        end = time.time() + timeout
        while time.time() < end:
            data = raw(client, "thread/read", {"threadId": tid, "includeTurns": True})
            turns = (data.get("thread") or {}).get("turns") or []
            if not any((t.get("status") == "inProgress") for t in turns):
                return len(turns)
            time.sleep(1)
        return None

    tmp_home = args.codex_home.parent / "events2-home"
    tmp_home.mkdir(exist_ok=True)
    config = CodexConfig(codex_bin=args.codex_bin, cwd=str(ws),
                         env={"CODEX_HOME": str(args.codex_home), "HOME": str(tmp_home)})
    with CodexClient(config, approval_handler=host) as client:
        router = client._router
        original = router.route_notification

        def tap(n):
            with lock:
                events.append({"at": time.time(), "method": n.method,
                               "typed": not isinstance(n.payload, UnknownNotification)})
            return original(n)

        router.route_notification = tap
        client.initialize()

        def drain():
            try:
                while True:
                    client.next_notification()
            except Exception as error:
                rec["global_drain_end"] = type(error).__name__

        threading.Thread(target=drain, daemon=True).start()
        base = {"cwd": str(ws), "model": MODEL, "ephemeral": False, "sandbox": "workspace-write",
                "approvalPolicy": "never", "dynamicTools": [TOOL_SPEC],
                "developerInstructions": "You are a test worker in a disposable workspace."}
        tid = raw(client, "thread/start", base)["thread"]["id"]
        step("fs/watch", lambda: raw(client, "fs/watch", {"path": str(ws), "watchId": "w1"}))
        step("fs/writeFile", lambda: raw(client, "fs/writeFile", {"path": str(ws / "fs.txt"),
                                                                  "dataBase64": base64.b64encode(b"fs-ok\n").decode()}), 2)
        step("process/spawn", lambda: raw(client, "process/spawn", {"command": ["sh", "-c", "echo proc-ok"], "cwd": str(ws),
                                                                    "processHandle": "p1", "streamStdoutStderr": True}), 2)
        step("command/exec", lambda: raw(client, "command/exec", {"command": ["echo", "exec-ok"], "cwd": str(ws),
                                                                  "processId": "c1", "streamStdoutStderr": True}), 1)
        step("thread/settings/update", lambda: raw(client, "thread/settings/update", {"threadId": tid, "model": MODEL}), 1)
        # turn with an approval-requiring policy: the command approval is declined -> serverRequest/resolved
        def approval_turn():
            t = client.turn_start(tid, "First call your update_plan tool with a two-step plan. Then run the shell "
                                  "command `echo approval-test`. Then create notes.txt containing hello with apply_patch. "
                                  "Then reply DONE.", {"model": MODEL, "approvalPolicy": "untrusted"})
            end = time.time() + args.deadline
            while time.time() < end:
                n = client.next_turn_notification(t.turn.id)
                if n.method == "turn/completed":
                    return {"turn": "completed"}
            return {"turn": "deadline"}
        step("turn/start(untrusted)", approval_turn)
        step("thread/shellCommand", lambda: raw(client, "thread/shellCommand", {"threadId": tid, "command": "echo shell-ok"}))
        step("wait(shellCommand)", lambda: {"turns": wait_turns_idle(tid)})
        step("thread/compact/start", lambda: raw(client, "thread/compact/start", {"threadId": tid}), 2)
        step("wait(compact)", lambda: {"turns": wait_turns_idle(tid)})
        step("thread/goal/set", lambda: raw(client, "thread/goal/set", {"threadId": tid, "objective": "Reply with the word GOAL once."}), 3)
        step("wait(goal)", lambda: {"turns": wait_turns_idle(tid, 120)})
        step("thread/goal/clear", lambda: raw(client, "thread/goal/clear", {"threadId": tid}), 2)
        step("thread/queue/add", lambda: raw(client, "thread/queue/add", {"threadId": tid, "clientUserMessageId": "q1",
                                                                          "input": [{"type": "text", "text": "Reply with the word QUEUED."}]}), 3)
        step("wait(queue)", lambda: {"turns": wait_turns_idle(tid, 120)})
        step("thread/rollback", lambda: raw(client, "thread/rollback", {"threadId": tid, "numTurns": 1}), 1)
        step("project/create", lambda: raw(client, "project/create", {"idempotencyKey": "r4-" + secrets.token_hex(3),
                                                                      "name": "r4-events", "roots": [str(ws)]}), 1)
        (ws / "skills").mkdir(exist_ok=True)
        step("skills/extraRoots/set", lambda: raw(client, "skills/extraRoots/set", {"extraRoots": [str(ws / "skills")]}), 1)
        fork = step("thread/fork", lambda: raw(client, "thread/fork", {"threadId": tid}), 1)
        fork_id = ((fork or {}).get("thread") or {}).get("id")

        def error_turn():
            t = client.turn_start(tid, "Reply OK.", {"model": "no-such-model"})
            end = time.time() + 120
            while time.time() < end:
                n = client.next_turn_notification(t.turn.id)
                if n.method == "turn/completed":
                    return {"turn": "completed"}
            return {"turn": "deadline"}
        step("turn/start(bad model)", error_turn, 1)
        if fork_id:
            step("thread/delete(fork)", lambda: raw(client, "thread/delete", {"threadId": fork_id}), 1)
        step("thread/unsubscribe", lambda: raw(client, "thread/unsubscribe", {"threadId": tid}), 3)
    counts: dict[str, int] = {}
    for e in events:
        counts[e["method"]] = counts.get(e["method"], 0) + 1
    documented = set(NOTIFICATION_MODELS)
    rec.update({"method_counts": dict(sorted(counts.items())),
                "untyped_methods": sorted({e["method"] for e in events if not e["typed"]}),
                "documented_types": len(documented),
                "received_documented": sorted(set(counts) & documented),
                "received_undocumented": sorted(set(counts) - documented),
                "tool_calls": host.calls, "other_server_requests": sorted(set(host.other)),
                "collector": "tap on openai_codex MessageRouter.route_notification (private attribute) plus a global drain"})
    rec["received_documented_count"] = len(rec["received_documented"])
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=("session", "resume", "events", "events2"))
    ap.add_argument("--codex-bin", required=True)
    ap.add_argument("--codex-home", type=Path, required=True)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--deadline", type=float, default=300)
    ap.add_argument("--first-delta-timeout", type=float, default=90)
    ap.add_argument("--stream-seconds", type=float, default=4)
    ap.add_argument("--settle", type=float, default=10)
    ap.add_argument("--tap", action="store_true", help="fix round: record every notification before routing")
    args = ap.parse_args()
    if args.out.exists():
        ap.error("refusing to overwrite an existing output")
    started = time.time()
    try:
        rec = {"session": phase_session, "resume": phase_resume, "events": phase_events, "events2": phase_events2}[args.phase](args)
        rec["status"] = "ok"
        code = 0
    except Exception as error:
        rec = {"status": "failed", "error_type": type(error).__name__, "error": str(error)[:3000]}
        code = 1
    rec.update({"sdk": "openai-codex", "started_at": started, "finished_at": time.time()})
    args.out.write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps({"phase": args.phase, "status": rec["status"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
