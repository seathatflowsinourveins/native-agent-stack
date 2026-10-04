#!/usr/bin/env python3
"""Compose native SDK configuration without starting a conversation or LLM call.

Sources: OpenHands/software-agent-sdk v1.50.1 at
1e1390acc8788346ba4804c34323284009bf3f5e:
  examples/01_standalone_sdk/{01_hello_world,07_mcp_integration,10_persistence,
  14_context_condenser}.py
  examples/05_skills_and_plugins/{01_loading_agentskills,02_loading_plugins}/main.py
  openhands-sdk/openhands/sdk/llm/llm.py
  openhands-sdk/openhands/sdk/utils/path.py

Set the SDK's OH_PERSISTENCE_DIR before importing this module to scope user-level
state and extension caches. CLI OPENHANDS_PERSISTENCE_DIR is a separate interface.

The returned mapping is passed directly to the upstream Conversation constructor.
Skill loading, MCP connection, plugin installation, and provider execution retain
their upstream lifecycle; this module supplies no agent loop or orchestrator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from openhands.sdk import LLM, Agent, AgentContext, Tool
from openhands.sdk.context.condenser import LLMSummarizingCondenser
from openhands.sdk.mcp import MCPServer
from openhands.sdk.plugin import PluginSource
from openhands.sdk.skills import load_skills_from_dir
from openhands.sdk.utils.path import get_user_persistence_dir
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool


def native_conversation_kwargs(
    *,
    model: str,
    canonical_model: str,
    base_url: str,
    workspace: Path,
    persistence_dir: Path,
    skills_dir: Path | None = None,
    mcp_config: dict[str, dict[str, Any]] | None = None,
    plugin_source: str | None = None,
    plugin_ref: str | None = None,
) -> dict[str, Any]:
    """Return upstream constructor arguments; make no provider request."""
    llm = LLM(
        usage_id="agent",
        model=model,
        model_canonical_name=canonical_model,
        base_url=base_url,
        api_mode="responses",
        reasoning_effort="max",
        native_tool_calling=True,
        caching_prompt=True,
        num_retries=2,
        timeout=180,
        stream_idle_timeout=180,
        capability_overrides={
            "supports_reasoning_effort": True,
            "supports_sampling_params": False,
            "supports_responses_api": True,
        },
    )
    agent_skills = load_skills_from_dir(skills_dir)[2] if skills_dir else {}
    context = AgentContext(
        skills=list(agent_skills.values()),
        load_user_skills=False,
        load_public_skills=False,
        load_project_skills=False,
        load_memory=False,
    )
    condenser = LLMSummarizingCondenser(
        llm=llm.model_copy(update={"usage_id": "condenser"}),
        max_size=80,
        keep_first=2,
        max_tokens=60_000,
    )
    agent = Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
            Tool(name=TaskTrackerTool.name),
        ],
        agent_context=context,
        condenser=condenser,
        mcp_config={
            name: MCPServer.model_validate(config)
            for name, config in (mcp_config or {}).items()
        },
    )
    plugins = (
        [PluginSource(source=plugin_source, ref=plugin_ref)] if plugin_source else []
    )
    return {
        "agent": agent,
        "workspace": str(workspace),
        "persistence_dir": str(persistence_dir),
        "plugins": plugins,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--canonical-model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--persistence-dir", required=True, type=Path)
    parser.add_argument("--skills-dir", type=Path)
    parser.add_argument("--mcp-config", type=json.loads, default={})
    parser.add_argument("--plugin-source")
    parser.add_argument("--plugin-ref")
    args = parser.parse_args()
    kwargs = native_conversation_kwargs(
        model=args.model,
        canonical_model=args.canonical_model,
        base_url=args.base_url,
        workspace=args.workspace,
        persistence_dir=args.persistence_dir,
        skills_dir=args.skills_dir,
        mcp_config=args.mcp_config,
        plugin_source=args.plugin_source,
        plugin_ref=args.plugin_ref,
    )
    agent = kwargs["agent"]
    print(
        json.dumps(
            {
                "llm": agent.llm.model_dump(
                    mode="json",
                    include={
                        "model", "model_canonical_name", "base_url", "api_mode",
                        "reasoning_effort", "native_tool_calling", "caching_prompt",
                        "num_retries", "timeout", "stream_idle_timeout",
                        "capability_overrides", "usage_id",
                    },
                ),
                "skills": [skill.name for skill in agent.agent_context.skills],
                "mcp_servers": sorted(agent.mcp_config),
                "condenser": agent.condenser.model_dump(
                    mode="json", include={"max_size", "keep_first", "max_tokens"}
                ),
                "condenser_usage_id": agent.condenser.llm.usage_id,
                "tools": [tool.name for tool in agent.tools],
                "plugin_sources": [
                    plugin.model_dump(mode="json") for plugin in kwargs["plugins"]
                ],
                "persistence_configured": bool(kwargs["persistence_dir"]),
                "native_user_persistence_dir": str(get_user_persistence_dir()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
