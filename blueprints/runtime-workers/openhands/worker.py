"""Run the pinned SDK examples' agent/conversation inside the owned container.

The only LLM adaptation adds gateway headers through public generate/agenerate
kwargs. It preserves upstream retries, Responses serialization and condensation.
See README.md for source lines and unmeasured host acceptance boundaries.
"""

from __future__ import annotations

import importlib.metadata
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import shlex
import sys
import uuid

from recipe import HERE, environment_selection, llm_config, read_json, tool_filter


def headers_for_call(static_headers):
    return {**(static_headers or {}), "Idempotency-Key": str(uuid.uuid4())}


def worker_llm_config(environment, dispatch_id):
    # The phase-2 proxy replaces these three headers with its own fixed values
    # (config/proxy-nginx.conf); the SDK copies stay equal to them by design.
    cfg = read_json(HERE / "config/worker.json")
    selection = environment_selection(environment)
    fields = llm_config(cfg, selection["requested_model"], arm=selection["arm"],
                        base_url=selection["base_url"], compression=selection["compression_combo"])
    fields["extra_headers"].update({"x-omniroute-session": dispatch_id, "X-Correlation-Id": dispatch_id})
    fields["usage_id"] = "agent"
    return fields


def response_correlation(response):
    # SDK@fcc102a llm.py:1130-1138 preserves raw_response. LiteLLM@v1.93.0
    # llms/openai/responses/transformation.py:262-272 preserves raw headers.
    raw = getattr(response, "raw_response", None)
    hidden = getattr(raw, "_hidden_params", {})
    headers = hidden.get("headers", {}) if isinstance(hidden, dict) else {}
    if isinstance(headers, dict):
        for key, value in headers.items():
            if key.lower() == "x-correlation-id" and isinstance(value, str) and 0 < len(value) <= 256:
                return value
    return None


@contextmanager
def gateway_transport(llm_type, correlation_callback=None):
    """Scope header transport to this single worker process, preserving LLM type.

    SDK agent/base.py:739-775 registers only exact LLM objects. A subclass skips
    native usage/context binding. Keep the objects native and restore methods
    after the conversation. Upstream retries remain within the original method.
    """
    original_generate, original_agenerate = llm_type.generate, llm_type.agenerate

    def call_kwargs(llm, kwargs):
        if kwargs.get("response_format") is not None or kwargs.get("text") is not None:
            raise ValueError("use_native_tool_calling_for_structured_output")
        if kwargs.get("temperature") is not None and kwargs["temperature"] <= 0.1:
            raise ValueError("gateway_temperature_must_exceed_0_1_or_be_omitted")
        static = llm.extra_headers or {}
        if not static.get("x-omniroute-session"):
            raise ValueError("conversation_affinity_required")
        return {**kwargs, "extra_headers": headers_for_call({**(kwargs.get("extra_headers") or {}), **static})}

    @wraps(original_generate)
    def generate(llm, *args, **kwargs):
        response = original_generate(llm, *args, **call_kwargs(llm, kwargs))
        if correlation_callback:
            correlation_callback(response_correlation(response))
        return response

    @wraps(original_agenerate)
    async def agenerate(llm, *args, **kwargs):
        response = await original_agenerate(llm, *args, **call_kwargs(llm, kwargs))
        if correlation_callback:
            correlation_callback(response_correlation(response))
        return response

    llm_type.generate, llm_type.agenerate = generate, agenerate
    try:
        yield
    finally:
        llm_type.generate, llm_type.agenerate = original_generate, original_agenerate


def build_agent(environment, dispatch_id):
    # Imports belong inside this entry point; offline recipe tests need no SDK.
    from openhands.sdk import Agent, AgentContext, LLM, Tool
    from openhands.sdk.context.condenser import LLMSummarizingCondenser
    from openhands.sdk.mcp.config import coerce_mcp_config
    from openhands.sdk.skills import load_skills_from_dir
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.terminal import TerminalTool

    cfg = read_json(HERE / "config/worker.json")
    policy = read_json(HERE / "config/mcp-policy.json")
    pins = read_json(HERE / "pins.json")
    versions = {name: importlib.metadata.version(name) for name in ("openhands-sdk", "openhands-tools")}
    if any(version != pins["version"] for version in versions.values()):
        raise RuntimeError("installed_version_mismatch")
    llm = LLM(**worker_llm_config(environment, dispatch_id))
    condenser_fields = {k: v for k, v in cfg["condenser"].items() if k != "kind"}
    condenser = LLMSummarizingCondenser(
        llm=llm.model_copy(update={"usage_id": "condenser"}), **condenser_fields,
    )
    _, _, skills = load_skills_from_dir("/workspace/.agents/skills")
    expected = set(read_json("/run-input/skills.json")["names"])
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
    return agent, versions, sorted(skills)


def worker_hooks():
    from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher
    return HookConfig(pre_tool_use=[HookMatcher(
        matcher="qmd_query", hooks=[HookDefinition(
            command=f"{shlex.quote(sys.executable)} {shlex.quote(str(HERE / 'mcp_guard.py'))}", timeout=10,
        )],
    )])


def start_request(task, run_id, arm):
    """Native request example: SDK@fcc102a conversation_router.py:72-86.

    expose_secrets serializes only the fixed keyless placeholder; the server
    auth key is never part of this body. pydantic_secrets.py:24-37,48-68.
    """
    from openhands.sdk import TextContent
    from openhands.sdk.workspace import LocalWorkspace
    from openhands.sdk.conversation.request import StartConversationRequest, SendMessageRequest
    agent, _, _ = build_agent({**os.environ, "OPENHANDS_ARM": arm}, run_id)
    request = StartConversationRequest(
        agent=agent, workspace=LocalWorkspace(working_dir="/workspace"),
        initial_message=SendMessageRequest(role="user", content=[TextContent(text=task)], run=True),
        max_iterations=read_json(HERE / "config/worker.json")["runtime"]["max_iteration_per_run"],
        hook_config=worker_hooks(), tags={"source": "ultracode", "dispatch": run_id, "arm": arm},
    )
    return request.model_dump(exclude_defaults=True, mode="json", context={"expose_secrets": True})


def capture_correlation(value):
    # Private, explicitly worker-reported. Never copy identifiers into receipts.
    with Path("/run-output/correlation.jsonl").open("a") as stream:
        stream.write(json.dumps({"correlation_id": value}) + "\n")


def run_worker():
    os.umask(0o077)
    from openhands.sdk import Conversation
    cfg = read_json(HERE / "config/worker.json")
    agent, versions, skills = build_agent(os.environ, os.environ.get("OPENHANDS_RUN_ID", str(uuid.uuid4())))
    output = Path("/run-output")
    output.mkdir(exist_ok=True)
    def record_event(event):
        # Native event fields, not claimed tool use inferred from a prompt/config.
        # Full upstream events remain in private SDK persistence. Export only the
        # fields needed for native tool/skill observations.
        kind = type(event).__name__
        selected = {}
        for key in ("tool_name", "tool_call_id", "action", "observation"):
            value = getattr(event, key, None)
            if value is not None:
                selected[key] = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        if selected:
            selected.update({"kind": kind})
            with (output / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(selected) + "\n")

    # Discovery is recorded before the first call; activation still requires
    # the SDK's successful InvokeSkillObservation in its own trace.
    (output / "skills-startup.json").write_text(json.dumps({
        "listed_skills": sorted(skills), "loader": "openhands.sdk.skills.load_skills_from_dir",
    }) + "\n")
    conversation = Conversation(
        agent=agent, workspace="/workspace", persistence_dir="/run-output/conversations",
        callbacks=[record_event], token_callbacks=[lambda *_: None], hook_config=worker_hooks(),
        max_iteration_per_run=cfg["runtime"]["max_iteration_per_run"], visualizer=None,
    )
    try:
        conversation.send_message(Path("/run-input/task.txt").read_text())
        conversation.run()
        state = conversation.state
        summary = {
            "versions": versions,
            "execution_status": str(state.execution_status),
            "invoked_skills": list(state.invoked_skills),
            "listed_skills": sorted(skills),
            "native_metrics": conversation.conversation_stats.get_combined_metrics().model_dump(mode="json"),
        }
        (output / "native-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    finally:
        conversation.close()
    return 0


def main():
    if not Path("/.dockerenv").exists() or os.environ.get("OPENHANDS_OWNED_CONTAINER") != "1":
        raise RuntimeError("worker_requires_owned_container")
    if sys.argv[1:] == ["--request"]:
        body = start_request(Path("/run-input/task.txt").read_text(),
                             os.environ["OPENHANDS_RUN_ID"], os.environ["OPENHANDS_ARM"])
        Path("/run-output/start.json").write_text(json.dumps(body) + "\n")
        return 0
    from openhands.sdk import LLM
    with gateway_transport(LLM, correlation_callback=capture_correlation):
        return run_worker()


if __name__ == "__main__":
    raise SystemExit(main())
