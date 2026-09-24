#!/usr/bin/env python3
"""Round 3, gap 13: one bounded Claude Agent SDK query that resumes an earlier session in a new process.

The earlier session is this unit's round-1 interrupted query (claude_probe.py), whose first user
message asked for an essay on a specific subject. This process passes ClaudeAgentOptions.resume with
that session id and asks which subject was requested, without naming it. No tools, no filesystem
settings (setting_sources=[]), max_turns=1. Exactly one query. The session id is read from the
private (unredacted) round-1 output and never written to this script's output unredacted.
Usage: claude_resume.py --session-file PRIVATE_JSON --workspace DIR --out OUT
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import AssistantMessage, ResultMessage, SystemMessage, TextBlock

PROMPT = ("Look back at my first message in this conversation. Which subject did it ask you to write an "
          "essay about? Reply with only the subject, in at most six words.")


def red(i: str | None) -> str | None:
    return None if i is None else "redacted-id:" + hashlib.sha256(i.encode()).hexdigest()[:16]


async def run(args, sid: str) -> dict:
    rec: dict = {"mode": "claude-resume", "resumed_session": red(sid), "prompt": PROMPT,
                 "prompt_mentions_subject": any(w in PROMPT.lower() for w in ("bookkeeping", "double-entry", "double entry"))}
    opts = ClaudeAgentOptions(model=args.model, cwd=str(args.workspace), resume=sid, setting_sources=[],
                              tools=[], allowed_tools=[], max_turns=1, permission_mode="default")
    texts: list[str] = []
    async for msg in query(prompt=PROMPT, options=opts):
        if isinstance(msg, SystemMessage) and msg.subtype == "init":
            d = msg.data or {}
            rec["init"] = {"model": d.get("model"), "session_id": red(d.get("session_id")),
                           "mcp_servers": d.get("mcp_servers"), "claude_code_version": d.get("claude_code_version")}
        elif isinstance(msg, AssistantMessage):
            texts.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage):
            rec["result"] = {"subtype": msg.subtype, "is_error": msg.is_error, "num_turns": msg.num_turns,
                             "session_id": red(msg.session_id), "session_id_equals_resumed": msg.session_id == sid,
                             "usage": msg.usage, "total_cost_usd": msg.total_cost_usd, "duration_ms": msg.duration_ms,
                             "model_usage": {k: vars(v) if hasattr(v, "__dict__") else v
                                             for k, v in (msg.model_usage or {}).items()}}
    answer = " ".join(texts).strip()
    rec["answer"] = answer
    low = answer.lower()
    rec["answer_names_subject"] = ("double-entry" in low or "double entry" in low) and "bookkeeping" in low
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session-file", type=Path, required=True)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="haiku")
    args = ap.parse_args()
    if args.out.exists():
        ap.error("refusing to overwrite an existing output")
    sid = json.loads(args.session_file.read_text())["session_id"]
    jsonl = list((Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl"))
    before = len(jsonl[0].read_text().splitlines()) if jsonl else None
    started = time.time()
    try:
        rec = asyncio.run(run(args, sid))
        rec["status"] = "ok"
        code = 0
    except Exception as error:
        rec = {"status": "failed", "error_type": type(error).__name__, "error": str(error)[:2000]}
        code = 1
    after = len(jsonl[0].read_text().splitlines()) if jsonl else None
    rec.update({"sdk": "claude-agent-sdk", "new_process_pid": __import__("os").getpid(), "started_at": started,
                "finished_at": time.time(), "session_jsonl_lines_before": before, "session_jsonl_lines_after": after})
    args.out.write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps({"status": rec["status"], "answer_names_subject": rec.get("answer_names_subject")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
