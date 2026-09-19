#!/usr/bin/env python3
"""Use the upstream ACP SDK to discover a native Codex session, without a prompt.

Run with DeerFlow's locked Python environment. ACP_NODE, ACP_ENTRYPOINT,
CODEX_PATH and ACP_WORKSPACE must identify explicit local native installations.
The JSON result may contain local paths; review and sanitize before publishing.
"""

import asyncio
import json
import os
from pathlib import Path

from acp import Client, PROTOCOL_VERSION, RequestPermissionResponse, spawn_agent_process
from acp.schema import ClientCapabilities, DeniedOutcome, Implementation


class DiscoveryClient(Client):
    async def session_update(self, session_id, update, **kwargs):
        pass

    async def request_permission(self, options, session_id, tool_call, **kwargs):
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))


async def main():
    node = os.environ["ACP_NODE"]
    entrypoint = os.environ["ACP_ENTRYPOINT"]
    workspace = str(Path(os.environ["ACP_WORKSPACE"]).resolve(strict=True))
    environment = {name: os.environ[name] for name in ("HOME", "PATH", "LANG", "TERM", "TMPDIR") if name in os.environ}
    environment.update({
        "CODEX_PATH": os.environ["CODEX_PATH"],
        "CODEX_HOME": os.environ["CODEX_HOME"],
        "INITIAL_AGENT_MODE": "read-only",
        "CODEX_CONFIG": json.dumps({"model": "gpt-6-astra", "model_reasoning_effort": "high"}),
    })
    async with asyncio.timeout(60):
        async with spawn_agent_process(DiscoveryClient(), node, entrypoint, env=environment, cwd=workspace) as (connection, process):
            initialized = await connection.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(),
                client_info=Implementation(name="native-stack-discovery", version="1.0.0"),
            )
            session = await connection.new_session(cwd=workspace, mcp_servers=[])
            print(json.dumps({
                "initialize": initialized.model_dump(mode="json", by_alias=True, exclude_none=True),
                "session": session.model_dump(mode="json", by_alias=True, exclude_none=True),
                "prompt_calls": 0,
                "model_requests": 0,
                "process_id": process.pid,
            }, indent=2), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
