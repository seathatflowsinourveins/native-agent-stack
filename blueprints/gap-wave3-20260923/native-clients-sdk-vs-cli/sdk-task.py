#!/usr/bin/env python3
"""Gap 12: run the frozen research task through the Claude Agent SDK, either
as a fresh session (mode=main) or resuming a prior session (mode=resume).
Writes a JSON result (no session UUIDs) to --out, and separately writes the
raw session id to a local, out-of-repo id file so a later resume call in this
same unit can use it.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys

from claude_agent_sdk import query, ClaudeAgentOptions

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TASK_PROMPT = open(os.path.join(BASE_DIR, "native-clients-research-task", "task-prompt.txt")).read().strip()
RESUME_PROMPT = open(os.path.join(BASE_DIR, "native-clients-research-task", "resume-followup-prompt.txt")).read().strip()


async def run(mode: str, resume_id_file: str, out_file: str, id_out_file: str):
    options_kwargs = dict(
        cwd=os.environ.get("CTX_SDK_CWD", os.getcwd()),
        allowed_tools=["Bash"],
        max_turns=3,
        effort="medium",
    )
    prompt = TASK_PROMPT
    if mode == "resume":
        with open(resume_id_file) as f:
            resume_id = f.read().strip()
        options_kwargs["resume"] = resume_id
        prompt = RESUME_PROMPT
    options = ClaudeAgentOptions(**options_kwargs)

    # CORRECTION (fix round): the original version of this script read only
    # result/session_id/usage/is_error and the receipts derived from it
    # claimed the SDK "exposes no native total_cost_usd field at all". That
    # claim was false: claude_agent_sdk.types.ResultMessage defines a
    # total_cost_usd: float | None field (see the installed SDK's types.py).
    # This script simply never read it. total_cost_usd is now captured below
    # so a future rerun of this harness records SDK-arm cost; it was not
    # captured for the runs already recorded in this unit's receipts, and
    # this script edit does not retroactively change or fabricate a cost
    # figure for those already-completed runs.
    result_text = None
    session_id = None
    usage = {}
    is_error = None
    total_cost_usd = None
    async for message in query(prompt=prompt, options=options):
        cls_name = type(message).__name__
        if cls_name == "ResultMessage":
            result_text = getattr(message, "result", None)
            session_id = getattr(message, "session_id", None)
            usage = getattr(message, "usage", None) or {}
            is_error = getattr(message, "is_error", None)
            total_cost_usd = getattr(message, "total_cost_usd", None)

    payload = {
        "mode": mode,
        "result": result_text,
        "is_error": is_error,
        "usage": usage,
        "total_cost_usd": total_cost_usd,
        "session_id_sha256_12": hashlib.sha256((session_id or "").encode()).hexdigest()[:12] if session_id else None,
    }
    with open(out_file, "w") as f:
        json.dump(payload, f, indent=2)
    if session_id:
        with open(id_out_file, "w") as f:
            f.write(session_id)
    print(json.dumps({k: v for k, v in payload.items() if k != "result"}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["main", "resume"], required=True)
    ap.add_argument("--resume-id-file", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--id-out", required=True)
    args = ap.parse_args()
    asyncio.run(run(args.mode, args.resume_id_file, args.out, args.id_out))
