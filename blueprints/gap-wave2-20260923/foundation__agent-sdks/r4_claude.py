#!/usr/bin/env python3
"""Round 4: Claude Agent SDK against the loopback vLLM provider (agent-sdks gap wave, 2026-09-23).

Run under `env -i` with HOME and CLAUDE_CONFIG_DIR pointing at a fresh temp directory,
ANTHROPIC_BASE_URL=http://127.0.0.1:28431 (vLLM's Anthropic Messages endpoint) and a dummy
ANTHROPIC_API_KEY. No Claude account, OAuth store or credential file is involved. The custom tool
is an in-process SDK MCP server (create_sdk_mcp_server); built-in tools are off (tools=[]) and no
filesystem settings load (setting_sources=[]). Phases:

  session  process 1: query 1 must call vault_lookup and reply with the value; query 2 asks for a
           long listing and is interrupted after streaming starts, with provider /metrics sampled
           before, at the interrupt and after two settle windows, next to ResultMessage usage and
           the native session JSONL usage.
  resume   process 2 (new OS process): ClaudeAgentOptions.resume with the session id and a decoy
           tool value; asks for the turn-1 value without calling any tool.

Usage: r4_claude.py PHASE --workspace WS --state PRIVATE --out OUT
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r4_common import delta, metrics, wait_idle  # noqa: E402

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool  # noqa: E402
from claude_agent_sdk.types import (AssistantMessage, ResultMessage, StreamEvent, SystemMessage,  # noqa: E402
                                    TextBlock, ToolResultBlock, ToolUseBlock, UserMessage)

import claude_agent_sdk._internal.client as _internal_client  # noqa: E402
import claude_agent_sdk._internal.message_parser as _message_parser  # noqa: E402

RAW_SEEN: list = []
_ORIGINAL_PARSE = _message_parser.parse_message


def _tapped_parse(data):
    """Fix round: record every raw CLI message before the SDK parses it (unknown types are dropped as None)."""
    out = _ORIGINAL_PARSE(data)
    RAW_SEEN.append({"type": (data or {}).get("type"), "subtype": (data or {}).get("subtype"),
                     "parsed": type(out).__name__ if out is not None else None})
    return out


def install_tap() -> None:
    _message_parser.parse_message = _tapped_parse
    _internal_client.parse_message = _tapped_parse


def tap_summary() -> dict:
    counts: dict = {}
    for r in RAW_SEEN:
        k = f"{r['type']}" + (f":{r['subtype']}" if r.get("subtype") else "") + f"->{r['parsed']}"
        counts[k] = counts.get(k, 0) + 1
    probe = _ORIGINAL_PARSE({"type": "zzz_unknown"})
    return {"raw_total": len(RAW_SEEN), "raw_counts": dict(sorted(counts.items())),
            "dropped_or_untyped": sorted({str(r["type"]) for r in RAW_SEEN if r["parsed"] is None}),
            "detector": {"unknown_type_dropped_as_none": probe is None}}


MODEL = "qwen3-4b"
LONG = ("This is a plain writing task: do not use any tool and do not refuse. In your reply, write the "
        "integers from 1 to 3000, one per line, each followed by a colon and its square.")
TYPED = (AssistantMessage, ResultMessage, StreamEvent, SystemMessage, UserMessage)


def make_server(value: str, calls: list):
    @tool("vault_lookup", "Return the stored value for a key from the caller's private vault.", {"key": str})
    async def vault_lookup(args):
        calls.append({"at": time.time(), "arguments": args})
        return {"content": [{"type": "text", "text": value}]}

    return create_sdk_mcp_server(name="vault", version="1.0.0", tools=[vault_lookup])


def options(ws: Path, server, resume: str | None = None) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(model=MODEL, fallback_model=None, cwd=str(ws), setting_sources=[], tools=[],
                              mcp_servers={"vault": server}, allowed_tools=["mcp__vault__vault_lookup"],
                              include_partial_messages=True, permission_mode="default", max_turns=4,
                              resume=resume)


def rec_msg(msg, events: list, rec: dict):
    e = {"at": time.time(), "type": type(msg).__name__, "typed": isinstance(msg, TYPED)}
    if isinstance(msg, SystemMessage):
        e["subtype"] = msg.subtype
        if msg.subtype == "init":
            d = msg.data or {}
            rec.setdefault("init", {k: d.get(k) for k in ("model", "tools", "mcp_servers", "permissionMode",
                                                          "claude_code_version", "apiKeySource")})
            rec["session_id"] = d.get("session_id")
    elif isinstance(msg, StreamEvent):
        ev = msg.event or {}
        e["event"] = ev.get("type")
        if ev.get("type") in ("message_start", "message_delta"):
            e["usage"] = (ev.get("message") or {}).get("usage") or ev.get("usage")
    elif isinstance(msg, AssistantMessage):
        e["blocks"] = [type(b).__name__ for b in msg.content]
        e["text"] = "".join(b.text for b in msg.content if isinstance(b, TextBlock))[:400]
        e["tool_uses"] = [b.name for b in msg.content if isinstance(b, ToolUseBlock)]
        e["usage"] = getattr(msg, "usage", None)
    elif isinstance(msg, UserMessage):
        e["tool_results"] = sum(1 for b in (msg.content if isinstance(msg.content, list) else [])
                                if isinstance(b, ToolResultBlock))
    elif isinstance(msg, ResultMessage):
        e["result"] = {"subtype": msg.subtype, "is_error": msg.is_error, "num_turns": msg.num_turns,
                       "stop_reason": msg.stop_reason, "terminal_reason": getattr(msg, "terminal_reason", None),
                       "usage": msg.usage, "total_cost_usd": msg.total_cost_usd, "result": (msg.result or "")[:400],
                       "model_usage": {k: vars(v) if hasattr(v, "__dict__") else v for k, v in (msg.model_usage or {}).items()}}
        rec["session_id"] = msg.session_id
    events.append(e)
    return e


def counts(events: list) -> dict:
    c: dict = {}
    for e in events:
        k = e["type"] + (":" + e["event"] if e.get("event") else "") + (":" + e["subtype"] if e.get("subtype") else "")
        c[k] = c.get(k, 0) + 1
    return c


def session_usage(session_id: str) -> dict:
    base = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects"
    hits = list(base.glob(f"*/{session_id}.jsonl"))
    if not hits:
        return {"session_jsonl_found": False}
    by_id: dict = {}
    lines = hits[0].read_text().splitlines()
    for line in lines:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = r.get("message") or {}
        if r.get("type") == "assistant" and isinstance(m.get("usage"), dict):
            by_id[m.get("id")] = {"stop_reason": m.get("stop_reason"),
                                  **{k: m["usage"].get(k) for k in ("input_tokens", "output_tokens")}}
    return {"session_jsonl_found": True, "lines": len(lines), "final_usage_per_message": list(by_id.values())}


async def phase_session(args) -> dict:
    value = "vc-" + secrets.token_hex(6)
    calls: list = []
    rec: dict = {"phase": "session", "pid": os.getpid()}
    async with ClaudeSDKClient(options=options(args.workspace, make_server(value, calls))) as client:
        ev1: list = []
        m0 = wait_idle()
        await client.query("Call the vault_lookup tool with key \"alpha\". Then reply with only the exact value it returned.")
        async for msg in client.receive_response():
            rec_msg(msg, ev1, rec)
        m1 = metrics()
        final = next((e["result"]["result"] for e in reversed(ev1) if e.get("result")), "")
        rec["turn1"] = {"event_counts": counts(ev1), "tool_host_calls": calls, "final_answer": final,
                        "answer_contains_value": value in final, "provider_delta": delta(m0, m1),
                        "result": next((e["result"] for e in ev1 if e.get("result")), None),
                        "untyped": [e["type"] for e in ev1 if not e["typed"]]}
        rec["turn1"]["tool_round_trip"] = bool(calls) and rec["turn1"]["answer_contains_value"]
        # query 2: interrupted essay
        ev2: list = []
        first = asyncio.Event()
        s_before = wait_idle()
        await client.query(LONG)

        async def consume():
            async for msg in client.receive_response():
                e = rec_msg(msg, ev2, rec)
                if e.get("event") == "content_block_delta":
                    first.set()

        task = asyncio.create_task(consume())
        t2: dict = {}
        try:
            await asyncio.wait_for(first.wait(), args.first_delta_timeout)
            t2["streaming_observed_before_interrupt"] = True
            await asyncio.sleep(args.stream_seconds)
        except TimeoutError:
            t2["streaming_observed_before_interrupt"] = False
        s_int = metrics()
        t2["interrupt_requested_at"] = time.time()
        await client.interrupt()
        await asyncio.wait_for(task, args.deadline)
        s_1s = metrics()
        await asyncio.sleep(args.settle)
        s1 = metrics()
        await asyncio.sleep(args.settle)
        s2 = metrics()
        t2.update({"event_counts": counts(ev2), "untyped": [e["type"] for e in ev2 if not e["typed"]],
                   "result": next((e["result"] for e in ev2 if e.get("result")), None),
                   "stream_usage_events": [e["usage"] for e in ev2 if e.get("usage")],
                   "events_after_interrupt": sum(1 for e in ev2 if e["at"] > t2["interrupt_requested_at"]),
                   "samples": {"before": s_before, "at_interrupt": s_int, "after_result_1s": s_1s,
                               "settle1": s1, "settle2": s2},
                   "provider_delta_before_to_interrupt": delta(s_before, s_int),
                   "provider_delta_before_to_settle1": delta(s_before, s1),
                   "provider_delta_settle1_to_settle2": delta(s1, s2),
                   "running_at_settle1": s1.get("vllm:num_requests_running")})
        t2["consumption_stopped"] = (t2["provider_delta_settle1_to_settle2"]["vllm:generation_tokens_total"] == 0
                                     and not s1.get("vllm:num_requests_running"))
        rec["turn2_interrupt"] = t2
    rec["session_log"] = session_usage(rec["session_id"]) if rec.get("session_id") else None
    if args.tap:
        rec["tap"] = tap_summary()
    args.state.write_text(json.dumps({"session_id": rec["session_id"], "value": value}))
    os.chmod(args.state, 0o600)
    return rec


async def phase_resume(args) -> dict:
    st = json.loads(args.state.read_text())
    decoy = "decoy-" + secrets.token_hex(4)
    calls: list = []
    rec: dict = {"phase": "resume", "pid": os.getpid()}
    events: list = []
    m0 = wait_idle()
    async with ClaudeSDKClient(options=options(args.workspace, make_server(decoy, calls), resume=st["session_id"])) as client:
        await client.query("Without calling any tool, what exact value did vault_lookup return earlier in this "
                           "conversation? Reply with only that value.")
        async for msg in client.receive_response():
            rec_msg(msg, events, rec)
    final = next((e["result"]["result"] for e in reversed(events) if e.get("result")), "")
    rec.update({"event_counts": counts(events), "untyped": [e["type"] for e in events if not e["typed"]],
                "final_answer": final, "tool_calls_in_resume": calls,
                "resumed_same_session": rec.get("session_id") == st["session_id"],
                "answer_contains_turn1_value": st["value"] in final, "answer_contains_decoy": decoy in final,
                "provider_delta": delta(m0, metrics()),
                "result": next((e["result"] for e in events if e.get("result")), None)})
    rec["resume_recall"] = rec["resumed_same_session"] and rec["answer_contains_turn1_value"] and not calls
    if args.tap:
        rec["tap"] = tap_summary()
    rec["session_id_private_in_state"] = True
    rec.pop("session_id", None)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=("session", "resume"))
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--deadline", type=float, default=300)
    ap.add_argument("--first-delta-timeout", type=float, default=120)
    ap.add_argument("--stream-seconds", type=float, default=4)
    ap.add_argument("--settle", type=float, default=10)
    ap.add_argument("--tap", action="store_true", help="fix round: record every raw CLI message before parsing")
    args = ap.parse_args()
    if args.tap:
        install_tap()
    if args.out.exists():
        ap.error("refusing to overwrite an existing output")
    started = time.time()
    try:
        rec = asyncio.run({"session": phase_session, "resume": phase_resume}[args.phase](args))
        rec["status"] = "ok"
        code = 0
    except Exception as error:
        rec = {"status": "failed", "error_type": type(error).__name__, "error": str(error)[:3000]}
        code = 1
    rec.pop("session_id", None)
    rec.update({"sdk": "claude-agent-sdk", "started_at": started, "finished_at": time.time(),
                "env_keys": sorted(os.environ)})
    args.out.write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps({"phase": args.phase, "status": rec["status"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
