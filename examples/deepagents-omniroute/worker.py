#!/usr/bin/env python3
"""Supported DeepAgents composition for a bounded, persisted research trial."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path

os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"

from deepagents import (  # noqa: E402
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import FilesystemBackend  # noqa: E402
from langchain.agents.middleware import ToolCallLimitMiddleware  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402

BASE_URL = "http://127.0.0.1:20128/v1"
MODEL = "cx/gpt-6.1-sol-max"


def serialize(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported native event type: {type(value).__name__}")


def emit(event, native):
    print(json.dumps({"event": event, "native": native}, default=serialize), flush=True)


def chat_model(api_key_env, base_url):
    # The caller supplies an existing child-route credential through this pointer.
    return ChatOpenAI(
        model=MODEL,
        base_url=base_url,
        api_key=os.environ[api_key_env],
        use_responses_api=True,
        use_previous_response_id=False,
        reasoning={"effort": "max"},
        timeout=120,
        max_retries=0,
    )


def build_graph(workspace, skills, saver, api_key_env, base_url):
    register_harness_profile(
        f"openai:{MODEL}",
        HarnessProfile(
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
            excluded_tools=frozenset({"execute"}),
        ),
    )
    specialist = {
        "name": "source-reviewer",
        "description": "Inspect the supplied primary sources and write cited research findings.",
        "model": chat_model(api_key_env, base_url),
        "skills": skills,
        "tools": [],
        "system_prompt": (
            "Research only the assigned question using the supplied primary-source files. "
            "Follow the selected skill and write the assigned specialist artifact. "
            "Cite source paths and line numbers. Do not delegate further."
        ),
    }
    return create_deep_agent(
        model=chat_model(api_key_env, base_url),
        name="persisted-research-worker",
        system_prompt=(
            "Complete the supplied bounded research task using the selected skill. "
            "Use source-reviewer only when the task requests specialist work. "
            "Preserve source uncertainty and write only requested artifacts."
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        skills=skills,
        subagents=[specialist],
        middleware=[
            ToolCallLimitMiddleware(
                tool_name="task", run_limit=1, exit_behavior="error"
            )
        ],
        checkpointer=saver,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument(
        "--skill",
        action="append",
        required=True,
        help="Virtual parent of selected skill directories",
    )
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument(
        "--base-url", default=BASE_URL, help="Explicit child endpoint or owned observer"
    )
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument(
        "--inspect", action="store_true", help="Read native checkpoint; no model call"
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Configuration only; no graph/model call",
    )
    args = parser.parse_args()
    config = {
        "configurable": {"thread_id": args.thread_id},
        "recursion_limit": 24,
        "max_concurrency": 2,
    }
    if args.describe:
        emit(
            "configuration",
            {
                "versions": {
                    name: importlib.metadata.version(name)
                    for name in (
                        "deepagents",
                        "langchain-openai",
                        "langgraph-checkpoint-sqlite",
                    )
                },
                "base_url": args.base_url,
                "underlying_lane": BASE_URL,
                "model": MODEL,
                "reasoning": {"effort": "max"},
                "api_key_env": args.api_key_env,
                "skills": args.skill,
                "use_responses_api": True,
                "use_previous_response_id": False,
                "request_timeout_seconds": 120,
                "max_retries": 0,
                "specialist": "source-reviewer",
                "task_run_limit": 1,
                "implicit_general_purpose": False,
                "shell_tool": False,
                "strict_msgpack": True,
                "config": config,
                "required_external_deadline_seconds": 600,
            },
        )
        return
    if not args.inspect and args.prompt_file is None:
        parser.error(
            "--prompt-file is required unless --inspect or --describe is selected"
        )
    workspace, checkpoint = args.workspace.resolve(), args.checkpoint.resolve()
    if not workspace.is_dir():
        parser.error("--workspace must be an existing owned directory")
    if checkpoint.is_relative_to(workspace):
        parser.error("--checkpoint must be outside the model-visible workspace")
    if args.api_key_env not in os.environ:
        parser.error("The selected child credential environment pointer is unset")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
        graph = build_graph(
            workspace, args.skill, saver, args.api_key_env, args.base_url
        )
        state = graph.get_state(config)
        emit("checkpoint_before", {"values": state.values, "next": state.next})
        if args.inspect:
            return
        prompt = args.prompt_file.read_text(encoding="utf-8")
        for namespace, update in graph.stream(
            {"messages": [("user", prompt)]},
            config,
            stream_mode="updates",
            subgraphs=True,
        ):
            emit("graph_update", {"namespace": namespace, "update": update})
        state = graph.get_state(config)
        emit("checkpoint_after", {"values": state.values, "next": state.next})


if __name__ == "__main__":
    main()
