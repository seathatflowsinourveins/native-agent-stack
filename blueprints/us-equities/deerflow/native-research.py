#!/usr/bin/env python3
"""Invoke DeerFlow's upstream ACP tool once using explicit native installations.

Run with the pinned DeerFlow backend environment after a current native allowance
check. The new private state directory retains adapter logs and the raw response;
neither is automatically suitable for publication. No upstream code is patched.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    for name in ("node", "adapter", "codex_bin", "readiness"):
        if not getattr(args, name).is_file():
            parser.error(f"{name} must be an existing native file")
    if not args.codex_home.is_dir():
        parser.error("codex-home must be the existing native home")
    readiness = json.loads(args.readiness.read_text())
    if readiness.get("readiness", {}).get("ready") is not True:
        parser.error("native allowance/model discovery must report ready")
    if time.time() - args.readiness.stat().st_mtime > 1800:
        parser.error("repeat native allowance discovery: receipt is over 30 minutes old")
    # Restrictive process umask applies to native adapter evidence too.
    os.umask(0o077)
    state = args.state_dir.resolve()
    if state.is_relative_to(here.parents[2]):
        parser.error("state-dir must be outside the public repository")
    state.mkdir(mode=0o700, parents=False, exist_ok=False)
    workspace = state / "runtime" / "acp-workspace"
    workspace.mkdir(parents=True)
    inputs = {"engine-receipt.json": here.parent / "engine" / "receipt.json",
              "deerflow-discovery.json": here / "native-receipt.json"}
    input_hashes = {}
    for name, source in inputs.items():
        shutil.copyfile(source, workspace / name)
        input_hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    extensions = state / "extensions.json"
    extensions.write_text('{"mcpServers":{}}\n')
    # Avoid implicit dotenv loading; only these documented native paths are set.
    os.environ.update({
        "PYTHON_DOTENV_DISABLED": "1",
        "DEER_FLOW_HOME": str(state / "runtime"),
        "DEER_FLOW_CONFIG_PATH": str(here / "config.research.yaml"),
        "DEER_FLOW_EXTENSIONS_CONFIG_PATH": str(extensions),
        "CODEX_PATH": str(args.codex_bin.absolute()),
        "CODEX_HOME": str(args.codex_home.resolve()),
        "APP_SERVER_LOGS": str(state / "adapter-logs"),
    })
    import yaml
    from deerflow.config.acp_config import ACPAgentConfig
    from deerflow.tools.builtins.invoke_acp_agent_tool import build_invoke_acp_agent_tool

    config = yaml.safe_load((here / "config.research.yaml").read_text())
    settings = config["acp_agents"]["codex"]
    settings.update(command=str(args.node.absolute()), args=[str(args.adapter.resolve())])
    agent = ACPAgentConfig(**settings)
    if agent.auto_approve_permissions or agent.env["INITIAL_AGENT_MODE"] != "read-only":
        raise ValueError("this recipe requires the ACP read-only mode ID and denied approvals")
    tool = build_invoke_acp_agent_tool({"codex": agent})
    prompt = (here / "research-task.md").read_text()
    started = time.monotonic()
    receipt = {"upstream_tool": tool.name, "invocations": 1,
               "inputs_sha256": input_hashes, "status": "started"}
    (state / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    async def invoke():
        # Upstream has a prompt timeout; this additionally bounds initialization.
        async with asyncio.timeout(240):
            return await tool.ainvoke({"agent": "codex", "prompt": prompt})

    try:
        response = asyncio.run(invoke())
        (state / "response.md").write_text(response + "\n")
        failed = response.startswith(("Error:", "Error invoking ")) or response == "(no response)"
        receipt["status"] = "tool_error" if failed else "returned_text"
        receipt["response_sha256"] = hashlib.sha256((response + "\n").encode()).hexdigest()
        receipt["response_characters"] = len(response)
        # DeerFlow returns only collected text, discarding ACP stop/usage fields.
        # Review native adapter logs for turn completion, identity and usage.
        receipt["native_completion_and_usage"] = "requires_private_adapter_log_review"
    except Exception as error:
        receipt.update(status="exception", error_type=type(error).__name__, error=str(error))
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (state / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "elapsed_seconds": receipt["elapsed_seconds"]}))
    return 0 if receipt["status"] == "returned_text" else 1


if __name__ == "__main__":
    raise SystemExit(main())
