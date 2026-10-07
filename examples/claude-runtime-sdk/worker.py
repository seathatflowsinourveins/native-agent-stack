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
import ipaddress
import pathlib
import socket
import urllib.parse
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

# --- host-gateway contract v2 (identical in every holder; tests/test_host_gateway_contract.py) ---
# needs (stdlib, Python >= 3.9): argparse, hashlib, ipaddress, json, os, pathlib, socket, sys, urllib.parse;
# tomllib (3.11+) and pwd are imported lazily, inside the functions that need them
HOST_GATEWAY_SCHEMA = "native-agent-stack/host-gateway/v1"
HOST_GATEWAY_RECORD = ".config/agent-stack-host/gateway.json"  # under the passwd home; never $HOME or XDG
HOST_GATEWAY_WRITER = "tools/omniroute/host_gateway.py write"
HOST_GATEWAY_OVERRIDE = "--unrecorded-gateway-reason"
LOOPBACK_NO_PROXY = ("127.0.0.1", "localhost", "::1")
ENDPOINT_OVERRIDE_KEYS = frozenset({"openai_base_url", "chatgpt_base_url", "model_provider", "model_providers",
                                    "profile", "profiles"})  # Codex's own endpoint denylist
CODEX_ENDPOINT_KEYS = ("base_url", "openai_base_url", "chatgpt_base_url")  # a loopback value under these is a route
_RECORD_WHERE = f"the passwd home's {HOST_GATEWAY_RECORD} (not $HOME)"
_OVERRIDE_FIX = f"pass the gateway flag together with {HOST_GATEWAY_OVERRIDE} TEXT"


class GatewayRefused(ValueError):
    """No endpoint may be used; the message says what was checked and what to run."""


def gateway_endpoint(value):
    """The one shape contract: exactly http://127.0.0.1:<port>/v1 (a trailing slash is dropped)."""
    if isinstance(value, str) and "${" in value:
        raise GatewayRefused(f"{value!r} is an unexpanded variable; set it, or leave it empty for this host's record")
    try:
        parts = urllib.parse.urlsplit(value.strip())
        port = parts.port
        ok = (parts.scheme == "http" and port is not None and port > 0 and parts.netloc == f"127.0.0.1:{port}"
              and not parts.query and not parts.fragment and parts.path.rstrip("/") == "/v1")
    except (AttributeError, TypeError, ValueError):
        ok = False
    if not ok:
        raise GatewayRefused(f"{value!r} is not a gateway endpoint; write it as http://127.0.0.1:<port>/v1")
    return f"http://127.0.0.1:{port}/v1"


def loopback_port(value):
    """The port of an http(s) URL whose host is any loopback or unspecified spelling; otherwise None."""
    try:
        parts = urllib.parse.urlsplit(value.strip())
        port, host = parts.port, (parts.hostname or "").rstrip(".")
        if parts.scheme not in ("http", "https") or port is None or not host:
            return None
        if host == "localhost" or host.endswith(".localhost"):
            return port
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = ipaddress.ip_address(socket.inet_aton(host))  # short IPv4 forms such as 127.1
        address = getattr(address, "ipv4_mapped", None) or address
        return port if address.is_loopback or address.is_unspecified else None
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def installation_id():
    """sha256 of this installation's /etc/machine-id (machine-id(5): 32 lowercase hex digits). There is no default."""
    try:
        text = pathlib.Path("/etc/machine-id").read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise GatewayRefused(f"/etc/machine-id cannot be read here ({type(error).__name__}), so no host gateway "
                             f"record can be bound to this installation; {_OVERRIDE_FIX}") from None
    if len(text) != 32 or text.strip("0123456789abcdef") or not text.strip("0"):
        raise GatewayRefused(f"/etc/machine-id is not a 32-digit lowercase hex id; {_OVERRIDE_FIX}")
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def recorded_gateway():
    """This host's own gateway, as its writer recorded it. There is no default."""
    try:
        import pwd
    except ImportError:
        raise GatewayRefused(f"this platform has no passwd database and so no host gateway record; "
                             f"{_OVERRIDE_FIX}") from None
    try:
        home = pathlib.Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        raise GatewayRefused("this uid has no passwd entry in this context (a user namespace or container); "
                             f"{_OVERRIDE_FIX}") from None
    try:
        text = (home / HOST_GATEWAY_RECORD).read_text(encoding="utf-8")
    except FileNotFoundError:
        try:
            visible = home.is_dir()
        except OSError:
            visible = False
        if not visible:
            raise GatewayRefused("the passwd home is not visible in this context (a sandbox); run outside it, "
                                 f"or {_OVERRIDE_FIX}") from None
        raise GatewayRefused(f"no host gateway record at {_RECORD_WHERE}. If this host runs a gateway: python3 "
                             f"<checkout>/{HOST_GATEWAY_WRITER} --port <PORT> --unit <UNIT>. If it has none: "
                             f"{_OVERRIDE_FIX}") from None
    except OSError as error:
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} exists but cannot be read here "
                             f"({error.strerror}); run outside the sandbox, or {_OVERRIDE_FIX}") from None
    try:
        record = json.loads(text)
        host, endpoint, machine = record["host"], record["endpoint"], record["machine_id_sha256"]
        if (record.get("schema") != HOST_GATEWAY_SCHEMA or not isinstance(host, str) or not isinstance(endpoint, str)
                or not isinstance(machine, str) or len(machine) != 64 or machine.strip("0123456789abcdef")):
            raise ValueError  # a missing, null, empty or malformed machine_id_sha256 is malformed
    except (AttributeError, KeyError, TypeError, ValueError):
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} is malformed or has another schema; "
                             f"rewrite it: python3 <checkout>/{HOST_GATEWAY_WRITER} --replace --port <PORT>") from None
    if host != socket.gethostname():
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} was written under another host name; "
                             f"if this host runs a gateway: python3 <checkout>/{HOST_GATEWAY_WRITER} --replace "
                             "--port <PORT>")
    if machine != installation_id():  # installation_id() refuses when this installation's machine id cannot be read
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} was written by another installation "
                             f"(the machine id differs); python3 <checkout>/{HOST_GATEWAY_WRITER} --replace "
                             "--port <PORT>")
    try:
        return gateway_endpoint(endpoint)
    except GatewayRefused:
        raise GatewayRefused(f"the host gateway record at {_RECORD_WHERE} names an endpoint outside the "
                             "contract") from None


def resolve_gateway(explicit, reason, variables):
    """The rule. Returns {endpoint, source, reason} or raises GatewayRefused."""
    explicit = explicit if isinstance(explicit, str) and explicit.strip() else None  # empty means no flag
    if explicit is not None:
        explicit = gateway_endpoint(explicit)
    if reason is not None:
        if explicit is None or not reason.strip():
            raise GatewayRefused(f"{HOST_GATEWAY_OVERRIDE} needs an explicit gateway and a non-blank reason")
        return {"endpoint": explicit, "source": "unrecorded", "reason": reason.strip()}
    recorded = recorded_gateway()
    if explicit is not None and explicit != recorded:
        raise GatewayRefused(f"{explicit} is not this host's recorded gateway ({recorded}); to use it "
                             f"deliberately add {HOST_GATEWAY_OVERRIDE} TEXT")
    port = urllib.parse.urlsplit(recorded).port
    for name in variables:
        found = loopback_port(os.environ.get(name) or "")
        if found is not None and found != port:
            raise GatewayRefused(f"{name} names a loopback gateway on port {found}, not this host's recorded "
                                 f"gateway ({recorded}); unset it (env -u {name} ...), or pass the gateway "
                                 f"explicitly with {HOST_GATEWAY_OVERRIDE} TEXT")
    return {"endpoint": recorded, "source": "host-record", "reason": None}


def _toml():
    try:
        import tomllib
    except ImportError:
        raise GatewayRefused("this Python has no tomllib (3.11+), so the endpoint check cannot run; use Python "
                             "3.11 or later for a gateway run") from None
    return tomllib


def refuse_endpoint_overrides(overrides):
    """A generic Codex -c value may not choose or redefine a provider endpoint; only the gateway flag may."""
    if not overrides:
        return
    tomllib = _toml()
    for override in overrides:
        try:
            keys = set(tomllib.loads(override)) & ENDPOINT_OVERRIDE_KEYS
        except (TypeError, tomllib.TOMLDecodeError):
            raise GatewayRefused(f"{override!r} is not a KEY=TOML override") from None
        if keys:
            raise GatewayRefused(f"{override!r} sets {', '.join(sorted(keys))}; an endpoint is chosen only by "
                                 "the gateway flag and this host's record")


def home_endpoint_ports(home):
    """(file:key, port) for each loopback endpoint that a Codex home's *config.toml files name."""
    paths = sorted(pathlib.Path(home).glob("*config.toml"))
    if not paths:
        return []
    tomllib, found = _toml(), []
    for path in paths:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise GatewayRefused(f"{path.name} in the Codex home cannot be read or parsed "
                                 f"({type(error).__name__}); fix it before a gateway run") from None
        stack = [((), data)]
        while stack:
            keys, node = stack.pop()
            if isinstance(node, dict):
                stack.extend(((*keys, key), value) for key, value in node.items())
            elif isinstance(node, str) and keys and keys[-1] in CODEX_ENDPOINT_KEYS:
                port = loopback_port(node)
                if port is not None:
                    found.append((path.name + ":" + ".".join(keys), port))
    return found


def refuse_home_endpoints(home, gateway, variables=()):
    """C1 for the Codex-home channel: a home may name no loopback endpoint but the run's gateway."""
    found = home_endpoint_ports(home)
    if not found:
        return  # no loopback route in the home: no record is read
    gateway = gateway or resolve_gateway(None, None, variables)
    port = urllib.parse.urlsplit(gateway["endpoint"]).port
    for where, other in found:
        if other != port:
            raise GatewayRefused(f"the Codex home names a loopback gateway on port {other} ({where}), not "
                                 f"{gateway['endpoint']}; use a Codex home that names this run's gateway or none")


def probe_gateway(endpoint, timeout=3.0):
    """A bounded TCP connect before any side effect: on mirrored WSL an unbound loopback port hangs."""
    try:
        socket.create_connection(("127.0.0.1", urllib.parse.urlsplit(endpoint).port), timeout=timeout).close()
    except OSError as error:
        raise GatewayRefused(f"gateway {endpoint} did not accept a TCP connection within {timeout:g} s "
                             f"({type(error).__name__}); start this host's gateway unit, then run python3 "
                             "<checkout>/tools/omniroute/host_gateway.py check") from None


def child_env(env):
    """A child's environment with loopback exempt from every proxy (NO_PROXY and no_proxy)."""
    env = dict(env)
    for name in ("NO_PROXY", "no_proxy"):
        entries = [item.strip() for item in (env.get(name) or "").split(",") if item.strip()]
        env[name] = ",".join(entries + [host for host in LOOPBACK_NO_PROXY if host not in entries])
    return env


def gateway_check(argv, flags, variables, overrides=(), homes=()):
    """--gateway-check, called at module top before any SDK import: resolve, print one JSON line, exit 0 or 2.
    flags maps each gateway flag of the holder to a function that returns a /v1 URL from the flag's value;
    overrides names its generic Codex -c flags and homes its Codex-home flags, which are checked too."""
    names = ("--gateway-check", HOST_GATEWAY_OVERRIDE, *flags, *overrides, *homes)
    pre = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    pre.add_argument("--gateway-check", action="store_true")
    pre.add_argument(HOST_GATEWAY_OVERRIDE, dest="reason")
    for index, flag in enumerate(flags):
        pre.add_argument(flag, dest=f"gateway_{index}")
    for index, flag in enumerate(overrides):
        pre.add_argument(flag, dest=f"override_{index}", action="append", default=[])
    for index, flag in enumerate(homes):
        pre.add_argument(flag, dest=f"home_{index}")
    known, rest = pre.parse_known_args(argv)
    if not known.gateway_check:
        return
    try:
        for item in rest:
            name = item.split("=", 1)[0]
            if name.startswith("--") and any(full != name and full.startswith(name) for full in names):
                raise GatewayRefused(f"{name} is an abbreviation; spell the option in full")
        values = [getattr(known, f"gateway_{index}") for index in range(len(flags))]
        given = [convert(value) for convert, value in zip(flags.values(), values) if value and value.strip()]
        results = [resolve_gateway(value, known.reason, variables) for value in given]
        result = results[0] if results else resolve_gateway(None, known.reason, variables)
        refuse_endpoint_overrides([item for index in range(len(overrides))
                                   for item in getattr(known, f"override_{index}")])
        for index in range(len(homes)):
            if getattr(known, f"home_{index}"):
                refuse_home_endpoints(getattr(known, f"home_{index}"), result, variables)
    except GatewayRefused as error:
        print(f"gateway refused: {error}", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps({"gateway": result}, sort_keys=True))
    raise SystemExit(0)
# --- end host-gateway contract v2 ---

GATEWAY_FLAGS = {"--gateway": lambda v: v.strip().rstrip("/") + "/v1"}
GATEWAY_VARIABLES = ("ANTHROPIC_BASE_URL",)
GATEWAY_OVERRIDES = ()
GATEWAY_HOMES = ()

if __name__ == "__main__":
    gateway_check(sys.argv[1:], GATEWAY_FLAGS, GATEWAY_VARIABLES, GATEWAY_OVERRIDES, GATEWAY_HOMES)

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
DEFAULT_MODEL = "dva/claude-opus-5-max"
RUN_MARKER = "nas-claude-runtime-sdk"
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






def build_options(args: argparse.Namespace) -> ClaudeAgentOptions:
    """Compose SDK options only after this host's gateway has been admitted."""
    explicit = GATEWAY_FLAGS["--gateway"](args.gateway) if args.gateway and args.gateway.strip() else None
    args.gateway_resolution = resolve_gateway(
        explicit, args.unrecorded_gateway_reason, GATEWAY_VARIABLES
    )
    probe_gateway(args.gateway_resolution["endpoint"])
    gateway = args.gateway_resolution["endpoint"][:-3]
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
        # SDK@f2204bb9 subprocess_cli.py:657-660 forwards this as --settings,
        # the highest user-controlled settings layer. Managed settings remain native.
        settings=json.dumps({"env": {"ANTHROPIC_BASE_URL": gateway}}),
        env=child_env({
            "NO_PROXY": os.environ.get("NO_PROXY", ""),
            "no_proxy": os.environ.get("no_proxy", ""),
            "ANTHROPIC_BASE_URL": gateway,
            "ANTHROPIC_AUTH_TOKEN": auth_token,
            # SDK@f2204bb9 subprocess_cli.py:819-825 passes native CLI env.
            # ANTHROPIC_CUSTOM_HEADERS is the documented Claude header interface.
            "ANTHROPIC_CUSTOM_HEADERS": (
                "X-OmniRoute-Session-Id: " + RUN_MARKER + "-" + uuid.uuid4().hex
            ),
            "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
        }),
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
        "run_marker_prefix": RUN_MARKER + "-",
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
    cli = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    cli.add_argument(
        "--preflight", action="store_true", help="configuration only; no model request"
    )
    cli.add_argument("--cwd", type=Path, default=Path.cwd())
    cli.add_argument(
        "--gateway",
        default=None,
        help="default: this host's recorded gateway; explicit Anthropic root without /v1",
    )
    cli.add_argument("--unrecorded-gateway-reason", metavar="TEXT")
    cli.add_argument("--gateway-check", action="store_true")
    cli.add_argument(
        "--gateway-token-env",
        help="optional application env binding for gateway auth; values are never printed",
    )
    cli.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="explicit advertised Claude-family candidate",
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


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0 or args.max_turns <= 0:
            raise ValueError("timeout and max-turns must be positive")
        if args.interrupt_after is not None and not 0 < args.interrupt_after < args.timeout:
            raise ValueError("interrupt-after must be positive and smaller than timeout")
        options = build_options(args)
        configuration = {**preflight(options), "gateway": args.gateway_resolution}
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
