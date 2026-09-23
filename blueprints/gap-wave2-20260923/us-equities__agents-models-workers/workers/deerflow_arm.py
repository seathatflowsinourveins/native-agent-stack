#!/usr/bin/env python3
"""DeerFlow/codex-acp arm: same upstream path as blueprints/us-equities/deerflow/native-research.py
(unmodified ACPAgentConfig + build_invoke_acp_agent_tool + .ainvoke), parametrised with this
unit's inputs and prompt. Differences from that helper: CODEX_CONFIG additionally disables
native lifecycle hooks (isolation rule: no ai-memory hook call may reach the live store), and
the final cumulative usage is extracted from the adapter's APP_SERVER_LOGS.

Run with the pinned DeerFlow backend venv python.
Usage: deerflow_arm.py --state-dir NEW_DIR --prompt FILE --input NAME=PATH [--input ...]
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
DF_CONFIG = REPO / "blueprints/us-equities/deerflow/config.research.yaml"
TOOLS = Path.home() / ".local/share/codex-ecosystem"


def usage_from_logs(log_dir: Path):
    events, hooks = [], []
    for f in sorted(log_dir.glob("*.log")):
        for line in f.read_text(errors="replace").splitlines():
            if "tokenUsage" in line:
                m = re.search(r'"total"\s*:\s*(\{[^{}]*\})', line)
                if m:
                    try:
                        events.append(json.loads(m.group(1)))
                    except ValueError:
                        pass
            if re.search(r'"hook/(started|completed)"|hookCompleted|hooks?/completed', line):
                hooks.append(line[:200])
    return (events[-1] if events else None), len(events), hooks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", type=Path, required=True)
    ap.add_argument("--prompt", type=Path, required=True)
    ap.add_argument("--input", action="append", default=[])
    ap.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    a = ap.parse_args()
    os.umask(0o077)
    state = a.state_dir.resolve()
    state.mkdir(mode=0o700, parents=False, exist_ok=False)
    workspace = state / "runtime" / "acp-workspace"
    workspace.mkdir(parents=True)
    hashes = {}
    for spec in a.input:
        name, src = spec.split("=", 1)
        shutil.copyfile(src, workspace / name)
        hashes[name] = hashlib.sha256(Path(src).read_bytes()).hexdigest()
    ext = state / "extensions.json"
    ext.write_text('{"mcpServers":{}}\n')
    os.environ.update({
        "PYTHON_DOTENV_DISABLED": "1",
        "DEER_FLOW_HOME": str(state / "runtime"),
        "DEER_FLOW_CONFIG_PATH": str(DF_CONFIG),
        "DEER_FLOW_EXTENSIONS_CONFIG_PATH": str(ext),
        "CODEX_PATH": str(TOOLS / "bin/codex"),
        "CODEX_HOME": str(a.codex_home),
        "APP_SERVER_LOGS": str(state / "adapter-logs"),
        "OTEL_RESOURCE_ATTRIBUTES": f"service.instance.id={uuid.uuid4()},ecosystem.client.scope=gap-wave2-deerflow-arm",
    })
    import yaml
    from deerflow.config.acp_config import ACPAgentConfig
    from deerflow.tools.builtins.invoke_acp_agent_tool import build_invoke_acp_agent_tool

    settings = yaml.safe_load(DF_CONFIG.read_text())["acp_agents"]["codex"]
    settings.update(command=str(TOOLS / "bin/node"),
                    args=[str(TOOLS / "tools/codex-acp-1.12.0/lib/node_modules/@agentclientprotocol/codex-acp/dist/index.js")])
    cc = json.loads(settings["env"]["CODEX_CONFIG"])
    cc["features"] = {"hooks": False, "plugin_hooks": False}
    settings["env"]["CODEX_CONFIG"] = json.dumps(cc)
    agent = ACPAgentConfig(**settings)
    if agent.auto_approve_permissions or agent.env["INITIAL_AGENT_MODE"] != "read-only":
        raise SystemExit("requires the ACP read-only mode ID and denied approvals")
    tool = build_invoke_acp_agent_tool({"codex": agent})
    prompt = a.prompt.read_text()
    receipt = {"upstream_tool": tool.name, "inputs_sha256": hashes, "codex_config": cc,
               "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    t0 = time.monotonic()

    async def invoke():
        async with asyncio.timeout(300):
            return await tool.ainvoke({"agent": "codex", "prompt": prompt})

    try:
        resp = asyncio.run(invoke())
        receipt["response"] = resp
        receipt["status"] = "tool_error" if resp.startswith(("Error:", "Error invoking ")) or resp == "(no response)" else "returned_text"
    except Exception as e:
        receipt.update(status="exception", error_type=type(e).__name__, error=str(e))
    receipt["elapsed_seconds"] = round(time.monotonic() - t0, 3)
    total, n_events, hooks = usage_from_logs(state / "adapter-logs")
    receipt["usage_cumulative_last_event"] = total
    receipt["usage_events_seen"] = n_events
    receipt["hook_lines_seen"] = hooks[:10]
    receipt["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (state / "receipt.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps({k: receipt.get(k) for k in ("status", "elapsed_seconds", "usage_cumulative_last_event", "usage_events_seen")}))


if __name__ == "__main__":
    main()
