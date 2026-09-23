#!/usr/bin/env python3
"""One bounded Claude Agent SDK query, interrupted mid-turn (agent-sdks gap wave 2026-09-23).

Exactly one model query is submitted. No filesystem settings are loaded
(setting_sources=[]), so user/project hooks and MCP servers do not run; no tools
are offered. Native sign-in is used by the CLI itself; this script opens no
credential file. After the ResultMessage, the native session JSONL for the same
session id is read and its assistant `usage` records are compared with the
SDK-returned usage.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, StreamEvent, SystemMessage


def session_usage(home: Path, session_id: str) -> dict:
    hits = list((home / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
    if not hits:
        return {"session_jsonl_found": False}
    rows = []
    for line in hits[0].read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = rec.get("message") or {}
        if rec.get("type") == "assistant" and isinstance(msg.get("usage"), dict):
            u = msg["usage"]
            rows.append({"timestamp": rec.get("timestamp"), "message_id": msg.get("id"),
                         "stop_reason": msg.get("stop_reason"),
                         **{k: u.get(k) for k in ("input_tokens", "output_tokens",
                                                  "cache_creation_input_tokens", "cache_read_input_tokens")}})
        elif rec.get("type") in ("user", "system") and "interrupt" in json.dumps(rec)[:4000].lower():
            rows.append({"timestamp": rec.get("timestamp"), "event": f"{rec.get('type')}_mentions_interrupt"})
    # Streaming writes one record per content block; the same message id repeats with cumulative usage.
    by_id: dict = {}
    for r in rows:
        if r.get("message_id"):
            by_id[r["message_id"]] = r
    return {"session_jsonl_found": True, "session_jsonl_name": hits[0].name, "entries": rows,
            "final_usage_per_message": list(by_id.values())}


async def run(args) -> dict:
    rec: dict = {"mode": "claude-interrupt", "model_requested": args.model}
    opts = ClaudeAgentOptions(model=args.model, cwd=str(args.workspace), setting_sources=[], tools=[],
                              allowed_tools=[], max_turns=1, include_partial_messages=True,
                              permission_mode="default")
    first_text = asyncio.Event()
    events: list[dict] = []
    async with ClaudeSDKClient(options=opts) as client:
        await client.query("Without using any tool, write a detailed 3000-word essay on the history of "
                           "double-entry bookkeeping, with numbered sections.")
        rec["query_submitted_at"] = time.time()

        async def consume():
            async for msg in client.receive_response():
                e = {"at": time.time(), "type": type(msg).__name__}
                if isinstance(msg, SystemMessage):
                    e["subtype"] = msg.subtype
                    if msg.subtype == "init":
                        d = msg.data or {}
                        e["init"] = {k: d.get(k) for k in ("model", "tools", "mcp_servers", "permissionMode",
                                                           "claude_code_version", "apiKeySource")}
                        rec["session_id"] = d.get("session_id")
                elif isinstance(msg, StreamEvent):
                    ev = msg.event or {}
                    e["event"] = ev.get("type")
                    if ev.get("type") == "content_block_delta":
                        first_text.set()
                    if ev.get("type") in ("message_start", "message_delta"):
                        e["usage"] = (ev.get("message") or {}).get("usage") or ev.get("usage")
                elif isinstance(msg, AssistantMessage):
                    e["stop"] = getattr(msg, "stop_reason", None)
                    e["usage"] = getattr(msg, "usage", None)
                elif isinstance(msg, ResultMessage):
                    rec["result"] = {"subtype": msg.subtype, "is_error": msg.is_error, "num_turns": msg.num_turns,
                                     "session_id": msg.session_id, "stop_reason": msg.stop_reason,
                                     "terminal_reason": msg.terminal_reason, "usage": msg.usage,
                                     "model_usage": {k: vars(v) if hasattr(v, "__dict__") else v
                                                     for k, v in (msg.model_usage or {}).items()},
                                     "total_cost_usd": msg.total_cost_usd, "duration_ms": msg.duration_ms,
                                     "errors": msg.errors}
                    rec["session_id"] = msg.session_id
                events.append(e)

        task = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(first_text.wait(), args.first_text_timeout)
            rec["streaming_observed_before_interrupt"] = True
            await asyncio.sleep(2)
        except TimeoutError:
            rec["streaming_observed_before_interrupt"] = False
        rec["interrupt_requested_at"] = time.time()
        await client.interrupt()
        await asyncio.wait_for(task, args.deadline)
    rec["result_at"] = next((e["at"] for e in events if e["type"] == "ResultMessage"), None)
    rec["event_type_counts"] = {}
    for e in events:
        key = e["type"] + ((":" + e["event"]) if e.get("event") else "") + ((":" + e["subtype"]) if e.get("subtype") else "")
        rec["event_type_counts"][key] = rec["event_type_counts"].get(key, 0) + 1
    rec["init"] = next((e.get("init") for e in events if e.get("init")), None)
    rec["stream_usage_events"] = [e for e in events if e.get("usage")]
    rec["events_after_interrupt"] = sum(1 for e in events if e["at"] > rec["interrupt_requested_at"])
    await asyncio.sleep(args.settle)
    if rec.get("session_id"):
        rec["session_log_after_settle"] = session_usage(Path.home(), rec["session_id"])
        await asyncio.sleep(args.settle)
        rec["session_log_after_second_settle"] = session_usage(Path.home(), rec["session_id"])
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--first-text-timeout", type=float, default=60)
    ap.add_argument("--deadline", type=float, default=90)
    ap.add_argument("--settle", type=float, default=15)
    args = ap.parse_args()
    if args.out.exists():
        ap.error("refusing to overwrite an existing output")
    started = time.time()
    try:
        rec = asyncio.run(run(args))
        rec["status"] = "ok"
        code = 0
    except Exception as error:
        rec = {"status": "failed", "error_type": type(error).__name__, "error": str(error)[:2000]}
        code = 1
    rec.update({"sdk": "claude-agent-sdk", "started_at": started, "finished_at": time.time()})
    args.out.write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps({"status": rec["status"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
