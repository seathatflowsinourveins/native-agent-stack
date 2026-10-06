"""CL6: one Claude Agent SDK (Python, claude-agent-sdk 0.2.163) session, written from the SDK README's query() example.

Run by launcher.py inside the same lock, meter and timeout as CL2. Every message the SDK yields is serialized to stdout
as one JSON line in the CLI's stream-json shape where the SDK keeps the raw fields (system messages carry their raw
data; rate_limit_event carries rate_limit_info.raw), so one grader reads CL2 and CL6.

prepare.py writes this file as the trial root's bin/run.py behind a two-line header that puts the SDK venv's
site-packages first on sys.path (the venv path names an experiment word, so it stays out of argv), and compiles the
result at stage 1. The header precedes everything here, so this file carries no `from __future__` import, which would
have to come first (smoke-20261006a: the header ahead of one was a SyntaxError and the CL6 trial exited at once).
"""
import argparse
import asyncio
import dataclasses
import json
import sys


def block_json(block) -> dict:
    name = type(block).__name__
    data = dataclasses.asdict(block) if dataclasses.is_dataclass(block) else {"value": str(block)}
    kind = {"TextBlock": "text", "ToolUseBlock": "tool_use", "ToolResultBlock": "tool_result",
            "ThinkingBlock": "thinking", "ServerToolUseBlock": "server_tool_use"}.get(name, name)
    return {"type": kind, **data}


def message_json(message) -> dict:
    name = type(message).__name__
    if name == "RateLimitEvent":
        info = message.rate_limit_info
        return {"type": "rate_limit_event", "rate_limit_info": getattr(info, "raw", None) or dataclasses.asdict(info),
                "uuid": message.uuid, "session_id": message.session_id}
    from claude_agent_sdk.types import SystemMessage
    if isinstance(message, SystemMessage):
        data = dict(message.data or {})
        data.setdefault("type", "system")
        data.setdefault("subtype", message.subtype)
        return data
    if name == "AssistantMessage":
        return {"type": "assistant", "parent_tool_use_id": message.parent_tool_use_id, "session_id": message.session_id,
                "uuid": message.uuid, "message": {"id": message.message_id, "model": message.model,
                                                  "content": [block_json(b) for b in message.content],
                                                  "usage": message.usage, "stop_reason": message.stop_reason}}
    if name == "UserMessage":
        content = message.content if isinstance(message.content, str) else [block_json(b) for b in message.content]
        return {"type": "user", "parent_tool_use_id": message.parent_tool_use_id, "uuid": message.uuid,
                "tool_use_result": message.tool_use_result, "message": {"role": "user", "content": content}}
    if name == "ResultMessage":
        data = dataclasses.asdict(message)
        data["type"] = "result"
        return data
    data = dataclasses.asdict(message) if dataclasses.is_dataclass(message) else {"value": str(message)}
    data["type"] = data.get("type") or name
    return data


async def main() -> int:
    parser = argparse.ArgumentParser()
    for flag in ("--trial-id", "--cwd", "--prompt-file", "--settings", "--cli-path", "--otel", "--gh-config-dir"):
        parser.add_argument(flag, required=True)
    args = parser.parse_args()
    from claude_agent_sdk import ClaudeAgentOptions, query
    options = ClaudeAgentOptions(
        cwd=args.cwd, cli_path=args.cli_path, system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=["user", "project", "local"], settings=args.settings, permission_mode="bypassPermissions",
        model="opus", effort="max", session_id=args.trial_id, include_hook_events=True,
        env={"OTEL_RESOURCE_ATTRIBUTES": args.otel, "GH_CONFIG_DIR": args.gh_config_dir})
    prompt = open(args.prompt_file, encoding="utf-8").read()
    async for message in query(prompt=prompt, options=options):
        sys.stdout.write(json.dumps(message_json(message), default=str) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
