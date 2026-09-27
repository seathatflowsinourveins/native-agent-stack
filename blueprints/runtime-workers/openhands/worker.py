"""Run the pinned SDK examples' agent/conversation inside the owned container.

The only LLM adaptation adds gateway headers through public generate/agenerate
kwargs. It preserves upstream retries, Responses serialization and condensation.
See README.md for source lines and unmeasured host acceptance boundaries.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import shlex
import sys
import uuid

from recipe import HERE, inventory, llm_config, read_json, tool_filter


def headers_for_call(static_headers):
    return {**(static_headers or {}), "Idempotency-Key": str(uuid.uuid4())}


def main():
    os.umask(0o077)
    if not Path("/.dockerenv").exists() or os.environ.get("OPENHANDS_OWNED_CONTAINER") != "1":
        raise RuntimeError("worker_requires_owned_container")
    # Imports belong inside this entry point; offline recipe tests need no SDK.
    from openhands.sdk import Agent, AgentContext, Conversation, LLM, Tool
    from openhands.sdk.context.condenser import LLMSummarizingCondenser
    from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher
    from openhands.sdk.mcp.config import coerce_mcp_config
    from openhands.sdk.skills import load_skills_from_dir
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.terminal import TerminalTool

    class GatewayLLM(LLM):
        """Per logical SDK call, including condenser calls; retries reuse the key."""

        def generate(self, *args, **kwargs):
            kwargs["extra_headers"] = headers_for_call(self.extra_headers)
            return super().generate(*args, **kwargs)

        async def agenerate(self, *args, **kwargs):
            kwargs["extra_headers"] = headers_for_call(self.extra_headers)
            return await super().agenerate(*args, **kwargs)

    cfg = read_json(HERE / "config/worker.json")
    policy = read_json(HERE / "config/mcp-policy.json")
    pins = read_json(HERE / "pins.json")
    versions = {name: importlib.metadata.version(name) for name in ("openhands-sdk", "openhands-tools")}
    if any(version != pins["version"] for version in versions.values()):
        raise RuntimeError("installed_version_mismatch")
    llm = GatewayLLM(
        **llm_config(cfg, os.environ.get(cfg["model_env"])),
        usage_id="agent",
        extra_headers={"x-omniroute-session": str(uuid.uuid4())},
    )
    condenser_fields = {k: v for k, v in cfg["condenser"].items() if k != "kind"}
    condenser = LLMSummarizingCondenser(
        llm=llm.model_copy(update={"usage_id": "condenser"}), **condenser_fields,
    )
    _, _, skills = load_skills_from_dir("/skills")
    expected = {entry["name"] for entry in read_json(HERE / "config/skills.lock.json")["skills"]}
    if set(skills) != expected:
        raise RuntimeError("skill_discovery_mismatch")
    context = AgentContext(
        **cfg["agent_context"], skills=list(skills.values()),
        system_message_suffix=(
            "Use focused original reads for known source. Retrieve only relevant excerpts; "
            "do not preload catalogs. Use context-mode to contain large output, recover "
            "originals before correctness decisions. Skills are available via invoke_skill. "
            "QMD queries must use explicit collections, typed lex searches, rerank:false. "
            "No embeddings are available from OmniRoute. Count native usage once; unknown "
            "usage remains unknown. MCP tools are capabilities, not mandatory steps."
        ),
    )
    # Native SDK MCP config; Codex-only keys have been translated, not passed through.
    mcp_config = coerce_mcp_config(read_json("/run-input/mcp.json"))
    if len([s for s in mcp_config.values() if s.enabled]) < 2:
        raise RuntimeError("multi_server_namespace_required")
    agent = Agent(
        llm=llm, condenser=condenser, agent_context=context,
        tools=[Tool(name=TerminalTool.name, params={"terminal_type": "subprocess"}), Tool(name=FileEditorTool.name)],
        include_default_tools=["FinishTool"],
        mcp_config=mcp_config, filter_tools_regex=tool_filter(policy),
    )
    output = Path("/run-output")
    output.mkdir(exist_ok=True)
    hooks = HookConfig(pre_tool_use=[HookMatcher(
        matcher="qmd_query", hooks=[HookDefinition(
            command=f"{shlex.quote(sys.executable)} {shlex.quote(str(HERE / 'mcp_guard.py'))}", timeout=10,
        )],
    )])

    def record_event(event):
        # Native event fields, not claimed tool use inferred from a prompt/config.
        # Full upstream events remain in private SDK persistence. Export only the
        # fields needed for file-scope/test ordering and tool/skill observations.
        kind = type(event).__name__
        selected = {}
        for key in ("tool_name", "tool_call_id", "action", "observation"):
            value = getattr(event, key, None)
            if value is not None:
                selected[key] = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        if selected:
            selected.update({"kind": kind, "workspace": inventory("/workspace")})
            with (output / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(selected) + "\n")

    conversation = Conversation(
        agent=agent, workspace="/workspace", persistence_dir="/run-output/conversations",
        callbacks=[record_event], token_callbacks=[lambda *_: None], hook_config=hooks,
        max_iteration_per_run=cfg["runtime"]["max_iteration_per_run"], visualizer=None,
    )
    try:
        conversation.send_message((HERE / "e2e/task.txt").read_text())
        conversation.run()
        state = conversation.state
        summary = {
            "versions": versions,
            "execution_status": str(state.execution_status),
            "invoked_skills": list(state.invoked_skills),
            "native_metrics": conversation.conversation_stats.get_combined_metrics().model_dump(mode="json"),
        }
        (output / "native-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    finally:
        conversation.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
