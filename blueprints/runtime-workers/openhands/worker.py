"""Run the pinned SDK examples' agent/conversation inside the owned container.

The owned LLM adaptation adds gateway headers and dispatches public completion
calls through native generate/agenerate when Responses is configured. Native
profiles, retries, serialization, call context and condensation remain upstream.
See README.md for the integration scope and unmeasured host boundaries.
"""

from __future__ import annotations

import importlib.metadata
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import re
import shlex
import sys
import uuid

from recipe import HERE, environment_selection, llm_config, profile_skills, read_json, task_profile, tool_filter


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
    # SDK@dcf401a llm/llm.py preserves raw_response. LiteLLM@v1.93.0
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

    Keep exact native LLM objects for upstream usage/context binding and restore
    methods after the owned process scope. SDK@dcf401a llm.py and call_context.py
    retain native retries, serialization and conversation-owned call context.
    """
    original_generate, original_agenerate = llm_type.generate, llm_type.agenerate
    original_completion = getattr(llm_type, "completion", None)
    original_acompletion = getattr(llm_type, "acompletion", None)

    def call_kwargs(llm, kwargs):
        if kwargs.get("response_format") is not None or kwargs.get("text") is not None:
            raise ValueError("use_native_tool_calling_for_structured_output")
        if any(kwargs.get(key) is not None for key in ("temperature", "top_p", "top_k")):
            raise ValueError("gpt6_sampling_parameters_must_be_omitted")
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

    # SDK@dcf401a llm.py generate:1577-1607 is the API-mode dispatcher;
    # completion:1645-1773 explicitly uses Chat Completions. Goal's judge.py
    # calls completion even with a Responses LLM. Route that call through the
    # native dispatcher without replacing the model loop or request serializer.
    def completion(llm, messages, tools=None, add_security_risk_prediction=False,
                   on_token=None, call_context=None, **kwargs):
        method = generate if llm.uses_responses_api() else original_completion
        return method(llm, messages=messages, tools=tools,
                      add_security_risk_prediction=add_security_risk_prediction,
                      on_token=on_token, call_context=call_context, **kwargs)

    async def acompletion(llm, messages, tools=None, add_security_risk_prediction=False,
                          on_token=None, call_context=None, **kwargs):
        method = agenerate if llm.uses_responses_api() else original_acompletion
        return await method(llm, messages=messages, tools=tools,
                            add_security_risk_prediction=add_security_risk_prediction,
                            on_token=on_token, call_context=call_context, **kwargs)

    llm_type.generate, llm_type.agenerate = generate, agenerate
    if original_completion is not None:
        llm_type.completion = completion
    if original_acompletion is not None:
        llm_type.acompletion = acompletion
    try:
        yield
    finally:
        llm_type.generate, llm_type.agenerate = original_generate, original_agenerate
        if original_completion is not None:
            llm_type.completion = original_completion
        if original_acompletion is not None:
            llm_type.acompletion = original_acompletion


def build_agent(environment, dispatch_id, *, child_llm=None):
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
    fields = worker_llm_config(environment, dispatch_id)
    profile_name, profile = task_profile(environment)
    if child_llm is None:
        llm = LLM(**fields)
    else:
        # Native TaskManager clones and resets the parent's metrics before the
        # registered factory. Keep that native object, and verify every route
        # requirement explicitly rather than relying on ambient child defaults.
        for key in ("model", "base_url", "api_mode", "reasoning_effort", "native_tool_calling"):
            if getattr(child_llm, key) != fields[key]:
                raise RuntimeError("child_route_mismatch")
        llm = child_llm.model_copy(update={"usage_id": "child-" + profile_name})
    condenser_fields = {k: v for k, v in cfg["condenser"].items() if k != "kind"}
    condenser = LLMSummarizingCondenser(
        llm=llm.model_copy(update={"usage_id": "condenser"}), **condenser_fields,
    )
    _, _, skills = load_skills_from_dir("/workspace/.agents/skills")
    skill_manifest = read_json("/run-input/skills.json")
    expected = set(skill_manifest["names"])
    if set(skills) != expected:
        raise RuntimeError("skill_discovery_mismatch")
    skills = profile_skills(skills, skill_manifest, profile)
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
    tools = [Tool(name=TerminalTool.name, params={"terminal_type": "subprocess"}), Tool(name=FileEditorTool.name)]
    allowed = []
    if profile["planning"]:
        from openhands.tools.preset.planning import get_planning_agent
        planning_agent = get_planning_agent(llm)
        # Keep the upstream planning prompt, restricted editor and condenser.
        tools = planning_agent.tools
        allowed.extend(re.escape(tool.name) for tool in tools)
        condenser = planning_agent.condenser
    if profile["browser"]:
        from openhands.tools.browser_use import BrowserToolSet
        tools.append(Tool(name=BrowserToolSet.name))
        allowed.append(r"browser_[A-Za-z][A-Za-z0-9_]*")
    if profile["children"]:
        from openhands.tools.task import TaskToolSet
        register_worker_agents(environment, dispatch_id, profile)
        tools.append(Tool(name=TaskToolSet.name))
        allowed.append(r"task")
    fields = dict(
        llm=llm, condenser=condenser, agent_context=context,
        tools=tools,
        include_default_tools=["FinishTool"],
        mcp_config=mcp_config, filter_tools_regex=tool_filter(policy, allowed),
        tool_concurrency_limit=profile["delegation"]["tool_concurrency_limit"] if profile["children"] else 1,
    )
    agent = planning_agent.model_copy(update=fields) if profile["planning"] else Agent(**fields)
    return agent, versions, sorted(skills)


def register_worker_agents(environment, dispatch_id, profile=None):
    """Native registration and bounded AgentDefinition, from examples 25 and 41.

    Each owned server is one task/dispatch. Factories are installed in both the
    offline serializer and the server startup process. Children cannot delegate
    recursively; their profiles omit TaskToolSet. TaskAction.max_turns is
    deprecated and ignored upstream, so bounds use the native agent definition.
    """
    if profile is None:
        _, profile = task_profile(environment)
    if not profile["children"]:
        return
    from openhands.sdk.subagent import register_agent_if_absent
    from openhands.sdk.subagent.schema import AgentDefinition
    for name in profile["children"]:
        agent_name = "worker-" + name
        child_environment = {**environment, "OPENHANDS_PROFILE": name}
        def factory(llm, child_environment=child_environment):
            return build_agent(child_environment, dispatch_id, child_llm=llm)[0]
        child_profile = task_profile(child_environment)[1]
        child_skills = profile_skills(
            {name: None for name in read_json("/run-input/skills.json")["names"]},
            read_json("/run-input/skills.json"), child_profile,
        )
        register_agent_if_absent(
            name=agent_name, factory_func=factory,
            description=AgentDefinition(
                name=agent_name, description=f"Task-scoped {name} worker; same GPT Responses/max route.",
                model=worker_llm_config(child_environment, dispatch_id)["model"],
                tools=["terminal", "file_editor"],
                skills=sorted(child_skills), hooks=worker_hooks(),
                max_iteration_per_run=profile["delegation"]["child_max_iteration_per_run"],
            ),
        )


def worker_hooks():
    from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher
    return HookConfig(pre_tool_use=[HookMatcher(
        matcher="qmd_query|task", hooks=[HookDefinition(
            command=f"{shlex.quote(sys.executable)} {shlex.quote(str(HERE / 'mcp_guard.py'))}", timeout=10,
        )],
    )])


def start_request(task, run_id, arm):
    """Native request: SDK@dcf401a conversation/request.py and conversation_router.py.

    expose_secrets serializes only the fixed keyless placeholder; the server
    auth key is never part of this body. pydantic_secrets.py:24-37,48-68.
    """
    from openhands.sdk import TextContent
    from openhands.sdk.workspace import LocalWorkspace
    from openhands.sdk.conversation.request import StartConversationRequest, SendMessageRequest
    agent, _, _ = build_agent({**os.environ, "OPENHANDS_ARM": arm}, run_id)
    _, profile = task_profile(os.environ)
    request = StartConversationRequest(
        agent=agent, workspace=LocalWorkspace(working_dir="/workspace"),
        initial_message=None if profile["goal_review"] else SendMessageRequest(
            role="user", content=[TextContent(text=task)], run=True),
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
        task = Path("/run-input/task.txt").read_text()
        _, profile = task_profile(os.environ)
        outcome = None
        judge_metrics = None
        if profile["goal_review"]:
            from openhands.sdk import LLM
            from openhands.sdk.conversation.goal import run_goal
            judge_llm = LLM(**{**worker_llm_config(os.environ, os.environ["OPENHANDS_RUN_ID"]),
                               "usage_id": profile["goal"]["usage_id"]})
            outcome = run_goal(conversation, task, judge_llm, max_iterations=profile["goal"]["max_iterations"])
            judge_metrics = judge_llm.metrics.model_dump(mode="json")
        else:
            conversation.send_message(task)
            conversation.run()
        state = conversation.state
        summary = {
            "versions": versions,
            "execution_status": str(state.execution_status),
            "invoked_skills": list(state.invoked_skills),
            "listed_skills": sorted(skills),
            "native_metrics": conversation.conversation_stats.get_combined_metrics().model_dump(mode="json"),
            "goal": {"status": outcome.status, "iterations": outcome.iterations} if outcome else None,
            "goal_judge_metrics": judge_metrics,
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
