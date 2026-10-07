#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["claude-agent-sdk==0.2.162"]
# ///
"""A worker-scoped OmniRoute transport for the official Claude Agent SDK.

Source: anthropics/claude-agent-sdk-python v0.2.162,
f2204bb956bab02907aaf3cb88eb9dead28eaa35, client.py and types.py.
The SDK, not this script, owns the agent loop, tools, context and session store.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import math
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

SDK_VERSION = "0.2.162"
SDK_COMMIT = "f2204bb956bab02907aaf3cb88eb9dead28eaa35"
OMNIROUTE_LAUNCH_COMMIT = "2f42a9ac19d1a247ec9ce5473b790843724b3061"
DEFAULT_GATEWAY = "http://127.0.0.1:20128"
MODEL_ID = re.compile(r"(?:[A-Za-z0-9_.:-]+/)?claude-[A-Za-z0-9_.:-]+\Z")
USAGE_COUNTERS = {
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "reasoning_tokens",
}
MODEL_COUNTERS = {
    "inputTokens",
    "outputTokens",
    "cacheReadInputTokens",
    "cacheCreationInputTokens",
    "webSearchRequests",
    "costUSD",
    "contextWindow",
    "maxOutputTokens",
}


def loopback_root(value: str) -> str:
    """Claude's Anthropic transport appends /v1/messages to this root."""
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise ValueError("invalid gateway root") from None
    if (
        parts.scheme not in {"http", "https"}
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or port is None
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("gateway must be a credential-free loopback root with a port")
    return value.rstrip("/")


def build_options(args: argparse.Namespace) -> ClaudeAgentOptions:
    """Compose SDK options; opaque explicit gateway credentials stay in memory."""
    if "CLAUDE_CODE_EFFORT_LEVEL" in os.environ:
        raise ValueError("inherited CLAUDE_CODE_EFFORT_LEVEL must be unset before launch")
    if not MODEL_ID.fullmatch(args.model):
        raise ValueError("worker model must be an explicit Claude-family model ID")
    if not args.cwd.is_dir():
        raise ValueError("worker cwd must be an existing directory")
    if args.resume is not None:
        try:
            uuid.UUID(args.resume)
        except ValueError:
            raise ValueError("resume must be a native session UUID") from None
    if args.skill is None or args.skill == ["all"]:
        skills: list[str] | Literal["all"] = "all"
    elif "all" in args.skill:
        raise ValueError("select all or exact skill names, not both")
    else:
        skills = args.skill
    for path in args.plugin or []:
        if not path.is_dir():
            raise ValueError("local plugin path must be an existing directory")
    if args.mcp_config is not None and not args.mcp_config.is_file():
        raise ValueError("MCP configuration path must be an existing file")
    gateway = loopback_root(args.gateway)
    auth_token = "omniroute-no-auth"
    if args.gateway_token_env is not None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.gateway_token_env):
            raise ValueError("gateway-token-env must name an application environment variable")
        if args.gateway_token_env.startswith("ANTHROPIC_"):
            raise ValueError(
                "use a gateway-specific token binding, separate from native Anthropic credentials"
            )
        auth_token = os.environ.get(args.gateway_token_env)
        if not auth_token or not auth_token.strip():
            raise ValueError("the explicit gateway token environment binding is missing or empty")
    return ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code"},
        model=args.model,
        effort="max",
        cwd=args.cwd.resolve(),
        # OmniRoute buildClaudeEnv, pinned above; retain native compaction policy.
        env={
            "ANTHROPIC_BASE_URL": gateway,
            "ANTHROPIC_AUTH_TOKEN": auth_token,
            "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
        },
        setting_sources=args.setting_source or ["user", "project"],
        skills=skills,
        plugins=[{"type": "local", "path": str(p.resolve())} for p in args.plugin or []],
        mcp_servers=str(args.mcp_config.resolve()) if args.mcp_config else {},
        allowed_tools=args.allow_tool or [],
        permission_mode=args.permission_mode,
        max_turns=args.max_turns,
        resume=args.resume,
        fork_session=args.fork_session,
    )


def prepare_worker_environment() -> int:
    """Strip native Anthropic env only in this standalone worker process.

    The SDK merges options.env onto os.environ and cannot delete inherited keys.
    OmniRoute's native buildClaudeEnv uses the same ANTHROPIC_* key filter.
    No credential value is inspected, returned or written to disk.
    """
    keys = [key for key in os.environ if key.startswith("ANTHROPIC_")]
    for key in keys:
        del os.environ[key]
    return len(keys)


def preflight(options: ClaudeAgentOptions) -> dict[str, Any]:
    """Small configuration evidence; no request, activation or identity claim."""
    if importlib.metadata.version("claude-agent-sdk") != SDK_VERSION:
        raise ValueError("installed SDK does not match the script pin")
    return {
        "evidence_class": "configuration_only",
        "sdk_version": SDK_VERSION,
        "sdk_commit": SDK_COMMIT,
        "omniroute_launch_commit": OMNIROUTE_LAUNCH_COMMIT,
        "python_version": sys.version.split()[0],
        "requested_model": options.model,
        "provider_identity_verified": False,
        "effort": options.effort,
        "system_prompt_preset": "claude_code",
        "tools_unrestricted": options.tools is None,
        "skills": options.skills,
        "setting_sources": options.setting_sources,
        "plugin_count": len(options.plugins),
        "mcp_config_explicit": isinstance(options.mcp_servers, str),
        "gateway_loopback": True,
        "gateway_port": urlsplit(options.env["ANTHROPIC_BASE_URL"]).port,
        "gateway_auth_injected": "ANTHROPIC_AUTH_TOKEN" in options.env,
        "gateway_model_discovery": True,
        "cwd_exists": Path(options.cwd).is_dir(),
        "resumed": options.resume is not None,
        "fork_session": options.fork_session,
        "max_turns": options.max_turns,
        "permission_mode": options.permission_mode,
    }


def numeric_counters(value: Any, keys: set[str]) -> dict[str, int | float] | None:
    if not isinstance(value, dict):
        return None
    return {
        key: number
        for key, number in value.items()
        if key in keys
        and isinstance(number, (int, float))
        and not isinstance(number, bool)
        and math.isfinite(number)
    }


@dataclass
class Observation:
    """Last native snapshots, never summed with cache subsets or prior turns."""

    session_id: str | None = None
    status: str = "running"
    result_count: int = 0
    tool_calls: dict[str, int] = field(default_factory=dict)
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    init: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    last_result: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    model_usage: dict[str, Any] | None = None
    native_cost_usd: float | None = None
    interrupt_sent: bool = False

    def observe(self, message: Any) -> None:
        if isinstance(message, SystemMessage) and message.subtype == "init":
            self.session_id = message.data.get("session_id")
            for key in ("tools", "skills", "agents", "mcp_servers"):
                values = message.data.get(key)
                if isinstance(values, list):
                    self.init[key + "_count"] = len(values)
                    self.init[key] = [
                        value
                        if isinstance(value, str)
                        else {
                            field: value[field]
                            for field in ("name", "status")
                            if field in value and isinstance(value[field], str)
                        }
                        for value in values
                        if isinstance(value, (str, dict))
                    ]
            self.init["reported_model"] = message.data.get("model")
            self.init["reported_cli_version"] = message.data.get("claude_code_version")
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    self.tool_calls[block.name] = self.tool_calls.get(block.name, 0) + 1
                    event = {"id": block.id, "name": block.name}
                    if block.name == "Skill" and isinstance(block.input.get("skill"), str):
                        event["skill"] = block.input["skill"]
                    self.tool_events.append(event)
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    self.tool_results.append(
                        {"tool_use_id": block.tool_use_id, "is_error": block.is_error}
                    )
        elif isinstance(message, ResultMessage):
            self.result_count += 1
            self.session_id = message.session_id
            self.result = message.result
            self.status = "native_error" if message.is_error else "completed"
            self.last_result = {
                "subtype": message.subtype,
                "is_error": message.is_error,
                "num_turns": message.num_turns,
                "duration_ms": message.duration_ms,
                "duration_api_ms": message.duration_api_ms,
                "terminal_reason": message.terminal_reason,
                "stop_reason": message.stop_reason,
                "api_error_status": message.api_error_status,
                "error_count": len(message.errors or []),
            }
            self.usage = numeric_counters(message.usage, USAGE_COUNTERS)
            self.model_usage = (
                None
                if message.model_usage is None
                else {
                    model: numeric_counters(counters, MODEL_COUNTERS)
                    for model, counters in message.model_usage.items()
                }
            )
            self.native_cost_usd = message.total_cost_usd

    def summary(self) -> dict[str, Any]:
        result_bytes = self.result.encode() if self.result is not None else None
        return {
            "evidence_class": "local_sdk_runtime_observation",
            "status": self.status,
            "session_id": self.session_id,
            "init": copy.deepcopy(self.init),
            "tool_calls": dict(self.tool_calls),
            "tool_events": copy.deepcopy(self.tool_events),
            "tool_results": copy.deepcopy(self.tool_results),
            "result_count": self.result_count,
            "last_result": copy.deepcopy(self.last_result),
            "result_bytes": len(result_bytes) if result_bytes is not None else None,
            "result_sha256": hashlib.sha256(result_bytes).hexdigest()
            if result_bytes is not None
            else None,
            "interrupt_sent": self.interrupt_sent,
            "usage_last_native_result": copy.deepcopy(self.usage),
            "model_usage_latest_session_snapshot": copy.deepcopy(self.model_usage),
            "usage_snapshots_summed": False,
            "cache_counters_added_to_input": False,
            "native_reported_cost_usd": self.native_cost_usd,
            "billing_cost_usd": None,
            "provider_identity_verified": False,
        }


async def run_worker(
    options: ClaudeAgentOptions,
    prompt: str,
    *,
    timeout: float,
    interrupt_after: float | None = None,
    client_factory: Any = ClaudeSDKClient,
) -> Observation:
    """Use the native client lifecycle and interrupt; no retry or model loop."""
    observation = Observation()
    client = None
    connected = False

    async def timed_interrupt(client: Any) -> None:
        assert interrupt_after is not None
        await anyio.sleep(interrupt_after)
        await client.interrupt()
        observation.interrupt_sent = True

    try:
        try:
            # Enter belongs to the operation deadline. __aexit__ must also run
            # when __aenter__ is cancelled (f2204bb client.py:623-630).
            with anyio.move_on_after(timeout) as scope:
                client = client_factory(options=options)
                await client.__aenter__()
                connected = True
                async with anyio.create_task_group() as group:
                    if interrupt_after is not None:
                        group.start_soon(timed_interrupt, client)
                    await client.query(prompt)
                    async for message in client.receive_response():
                        observation.observe(message)
                    group.cancel_scope.cancel()
            if scope.cancel_called:
                observation.status = "timeout"
                # A partial connect has no query to interrupt or drain.
                if connected:
                    with anyio.move_on_after(4, shield=True):
                        await client.interrupt()
                        observation.interrupt_sent = True
                        async for message in client.receive_response():
                            observation.observe(message)
                observation.status = "timeout"
            elif observation.last_result is None:
                observation.status = "missing_native_result"
            elif observation.last_result["terminal_reason"] in {
                "aborted_streaming",
                "aborted_tools",
            }:
                observation.status = "interrupted"
            elif observation.last_result["terminal_reason"] not in {
                None,
                "completed",
            }:
                observation.status = "native_incomplete"
        finally:
            if client is not None:
                # Only cleanup receives the extra grace, shielded from the
                # operation/parent cancellation as in AnyIO's finalization guide.
                with anyio.fail_after(5, shield=True):
                    await client.__aexit__(*sys.exc_info())
    except TimeoutError:
        observation.status = "timeout"
    except Exception as error:
        # Native exception text can contain prompts, paths or credentials.
        observation.status = "sdk_error"
        observation.last_result = {"exception_type": type(error).__name__}
    return observation


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "--preflight", action="store_true", help="configuration only; no model request"
    )
    cli.add_argument("--cwd", type=Path, default=Path.cwd())
    cli.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY,
        help="loopback Anthropic root, without /v1",
    )
    cli.add_argument(
        "--gateway-token-env",
        help="optional application env binding for gateway auth; values are never printed",
    )
    cli.add_argument(
        "--model",
        required=True,
        help="explicit advertised Claude-family gateway candidate; no implicit Opus route",
    )
    cli.add_argument("--setting-source", action="append", choices=["user", "project", "local"])
    cli.add_argument(
        "--skill", action="append", help="all or repeat exact task-matched skill names"
    )
    cli.add_argument("--plugin", type=Path, action="append", help="selected local plugin directory")
    cli.add_argument(
        "--mcp-config",
        type=Path,
        help="native MCP JSON path; contents are not read here",
    )
    cli.add_argument(
        "--allow-tool",
        action="append",
        help="native permission auto-approval, not a tool restriction",
    )
    cli.add_argument(
        "--permission-mode",
        default="dontAsk",
        choices=["default", "dontAsk", "acceptEdits", "plan", "auto"],
    )
    cli.add_argument("--max-turns", type=int, default=12)
    cli.add_argument("--timeout", type=float, default=300)
    cli.add_argument(
        "--interrupt-after",
        type=float,
        help="send one native interrupt after this many seconds",
    )
    cli.add_argument("--resume", help="same native session UUID and cwd; no implicit resubmission")
    cli.add_argument("--fork-session", action="store_true")
    cli.add_argument(
        "--result-output",
        type=Path,
        help="new private 0600 file for returned text; summary stdout omits text",
    )
    return cli


def main() -> int:
    args = parser().parse_args()
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0 or args.max_turns <= 0:
            raise ValueError("timeout and max-turns must be positive")
        if args.interrupt_after is not None and not 0 < args.interrupt_after < args.timeout:
            raise ValueError("interrupt-after must be positive and smaller than timeout")
        options = build_options(args)
        configuration = preflight(options)
        if args.preflight:
            print(json.dumps(configuration, sort_keys=True))
            return 0
        prompt = sys.stdin.read()
        if not prompt.strip():
            raise ValueError("a non-empty prompt is required on stdin")
        if args.result_output is not None and args.result_output.exists():
            raise ValueError("result-output must be a new private file")
        # This CLI process is the owned worker child, not the native coordinator.
        configuration["native_anthropic_env_keys_removed"] = prepare_worker_environment()
        observation = anyio.run(
            lambda: run_worker(
                options,
                prompt,
                timeout=args.timeout,
                interrupt_after=args.interrupt_after,
            )
        )
        if args.result_output is not None and observation.result is not None:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            try:
                with os.fdopen(os.open(args.result_output, flags, 0o600), "w") as output:
                    output.write(observation.result)
            except OSError:
                # Keep native usage and identifiers even when artifact writing fails.
                observation.status = "result_artifact_error"
        print(
            json.dumps(
                {"configuration": configuration, "observation": observation.summary()},
                sort_keys=True,
            )
        )
        return 0 if observation.status == "completed" else 1
    except (ValueError, OSError) as error:
        # Configuration errors are authored here; OS errors may carry private paths.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps({"status": "preflight_failed", "error": message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
