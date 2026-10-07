#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "openai-codex==0.160.0",
# ]
# ///
"""One native Codex SDK turn, or metadata preflight, through OmniRoute.

Derived from openai/codex rust-v0.160.0, commit
a956835d020762cb2b570053af06f643a11c0ecc, sdk/python/examples/{01,05,14}_*
and sdk/python/src/openai_codex/{api,client,_run,async_client}.py. Preflight uses
exactly pinned SDK internals in generated/v2_all.py and the native app-server
request_processors/mcp_processor.rs. See README.md for sources.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import pathlib
import socket
import urllib.parse
import asyncio
import json
import os
import re
import sys
import uuid
from collections import Counter
from pathlib import Path
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

GATEWAY_FLAGS = {"--base-url": lambda value: value}
GATEWAY_VARIABLES = ("OPENAI_BASE_URL", "WORKER_BASE_URL")
GATEWAY_OVERRIDES = ()
GATEWAY_HOMES = ("--codex-home",)

if __name__ == "__main__":
    gateway_check(sys.argv[1:], GATEWAY_FLAGS, GATEWAY_VARIABLES, GATEWAY_OVERRIDES, GATEWAY_HOMES)

from openai_codex import ApprovalMode, AsyncCodex, CodexConfig, Sandbox
from openai_codex.async_client import AsyncCodexClient
from openai_codex.generated.v2_all import (
    ConfigReadResponse,
    ListMcpServerStatusResponse,
    SkillsListResponse,
)
from openai_codex.types import ReasoningEffort

SDK_VERSION = "0.160.0"
PROVIDER = "omniroute_runtime"
DEFAULT_MODEL = "cx/gpt-6.1-sol-max"
# OmniRoute 0585aba5589d5a1f49243a13a8db249558e7c9e3:
# open-sse/executors/codex/reasoningSuffix.ts: suffix tokens for a lexical
# fail-closed guard, independent of gateway alias sets.
GATEWAY_EFFORT_SUFFIXES = (
    "-none", "-low", "-medium", "-high", "-xhigh", "-max", "-ultra", "(max)", "(ultra)"
)
CLEANUP_TIMEOUT = 5.0
_CLEANUP_TASKS: set[asyncio.Task] = set()




def _cleanup_finished(task: asyncio.Task) -> None:
    _CLEANUP_TASKS.discard(task)
    if not task.cancelled():
        task.exception()


async def close_runtime(codex, startup: asyncio.Task | None, record: dict) -> None:
    """Settle owned startup before close; a cleanup deadline is unresolved.

    The pinned async_client.py:73-99 offloads start/close with to_thread.
    Retain and shield tasks as documented by Python 3.13 asyncio.shield.
    """

    async def settle_and_close():
        if startup is not None:
            try:
                await startup
            except Exception:
                # The caller records startup failure; still close its child.
                pass
        await codex.close()

    cleanup = asyncio.create_task(settle_and_close())
    _CLEANUP_TASKS.add(cleanup)
    cleanup.add_done_callback(_cleanup_finished)
    try:
        await asyncio.wait_for(asyncio.shield(cleanup), CLEANUP_TIMEOUT)
        record["cleanup_status"] = "closed"
    except TimeoutError:
        # Ownership continues while the embedding loop runs. A standalone
        # caller must treat this as unresolved rather than certified cleanup.
        record.update(cleanup_status="unresolved", cleanup_error_type="TimeoutError")
    except asyncio.CancelledError:
        record.update(cleanup_status="unresolved", cleanup_error_type="CancelledError")
        raise
    except Exception as exc:
        record.update(status="cleanup_failed", cleanup_status=type(exc).__name__)




def request_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", value):
        raise argparse.ArgumentTypeError("request id must be 1–96 ASCII identifier characters")
    return value


def positive_seconds(value: str) -> float:
    seconds = float(value)
    if not 0 < seconds <= 3600:
        raise argparse.ArgumentTypeError(
            "timeout must be greater than zero and at most 3600 seconds"
        )
    return seconds


def runtime_config(args: argparse.Namespace) -> CodexConfig:
    """Only the SDK child receives these supported native CLI overrides."""
    prefix = f"model_providers.{PROVIDER}."
    quoted = lambda value: json.dumps(value, ensure_ascii=False)  # noqa: E731
    overrides = (
        "model_provider=" + quoted(PROVIDER),
        "model=" + quoted(args.model),
        "model_reasoning_effort=" + quoted(args.effort),
        # Native curated-plugin startup sync is unused by this worker.
        # a956835d core-plugins/src/manager.rs:748-763; core/config.schema.json:7038.
        "features.plugins=false",
        # Custom providers default to false (a956835d model-provider-info/src/lib.rs:194-196).
        "features.standalone_web_search=true",
        prefix + 'name="OmniRoute runtime workers"',
        prefix + "base_url=" + quoted(args.base_url),
        prefix + 'wire_api="responses"',
        prefix + "requires_openai_auth=false",
        prefix + "supports_websockets=false",
        prefix + "supports_standalone_web_search=true",
        prefix + 'http_headers={"x-request-id"=' + quoted(args.request_id) + "}",
    )
    if args.api_key_env:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.api_key_env):
            raise ValueError("api-key-env must name an environment variable")
        # Canonical keyed filters merge by name; never mix them with legacy arrays.
        # a956835d config/src/shell_environment_policy.rs:28-35,106-110.
        overrides += (
            prefix + "env_key=" + quoted(args.api_key_env),
            "shell_environment_policy.filters." + quoted(args.api_key_env) + '="exclude"',
            "features.shell_snapshot=false",
        )
    # Native retry settings remain native. The caller may disarm them for a
    # measured acceptance attempt; there is no wrapper retry or agent loop.
    if args.no_provider_retries:
        overrides += (prefix + "request_max_retries=0", prefix + "stream_max_retries=0")
    env = {"CONTEXT_MODE_PROJECT_DIR": str(args.workspace.resolve())}
    if args.codex_home:
        env["CODEX_HOME"] = str(args.codex_home.resolve())
    return CodexConfig(
        codex_bin=str(args.codex_bin.resolve()) if args.codex_bin else None,
        config_overrides=overrides,
        cwd=str(args.workspace.resolve()),
        env=child_env({**os.environ, **env}),
        client_name="omniroute_codex_runtime_worker",
        client_title="OmniRoute Codex runtime worker",
    )


def result_record(result) -> dict:
    """Retain native snapshots; total is cumulative and last is not a turn sum."""
    kinds = Counter(
        item.model_dump(mode="json", by_alias=True).get("type") for item in result.items
    )
    return {
        "status": result.status.value,
        "turn_id": result.id,
        "final_response": result.final_response,
        "duration_ms": result.duration_ms,
        "item_counts": dict(kinds),
        "usage_status": "reported" if result.usage is not None else "unknown",
        "usage_scope": "native_thread_cumulative" if result.usage is not None else None,
        "usage": result.usage.model_dump(mode="json", by_alias=True)
        if result.usage is not None
        else None,
    }


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")), flush=True)


def initial_record(args: argparse.Namespace) -> dict:
    return {
        "request_id": args.request_id,
        "gateway": args.gateway,
        "requested_model": args.model,
        "requested_effort": args.effort,
        "provider": PROVIDER,
        "model_inference_submitted": False,
        "usage_status": "unknown",
        "usage_scope": None,
        "usage": None,
    }


def native_runtime(metadata) -> dict:
    # Match the pinned SDK's _initialize_metadata.py normalization using public
    # response fields. Low-level initialize() returns serverInfo=None on 0.160.0.
    server = metadata.serverInfo
    name = (server.name or "").strip() if server is not None else ""
    version = (server.version or "").strip() if server is not None else ""
    source = "serverInfo"
    if not name or not version:
        source = "userAgent"
        user_agent = (metadata.userAgent or "").strip()
        if "/" in user_agent:
            parsed_name, parsed_version = user_agent.split("/", 1)
        else:
            parts = user_agent.split(maxsplit=1)
            parsed_name = parts[0] if parts else ""
            parsed_version = parts[1] if len(parts) == 2 else ""
        name = name or parsed_name.strip()
        version = version or parsed_version.strip()
    if not name or not version or version.split()[0] != SDK_VERSION:
        raise RuntimeError("native runtime does not match the qualified SDK pin")
    return {"name": name, "version": version.split()[0], "metadata_source": source}


def mcp_catalog_ready(server: dict) -> bool:
    return bool(
        server["configured"]
        and server["enabled"]
        and server["tool_names"]
        and not server["tools_error"]
    )


def preflight_output(record: dict, *, catalog_details: bool = False) -> dict:
    """Keep CLI receipts compact; explicit diagnostics retain native catalogs."""
    if catalog_details:
        return record
    compact = dict(record)
    if "mcp_servers" in record:
        compact["mcp_servers"] = [
            {
                **{key: value for key, value in server.items() if key != "tool_names"},
                "tool_count": len(server["tool_names"]),
                "catalog_ready": mcp_catalog_ready(server),
            }
            for server in record["mcp_servers"]
        ]
    if "skills" in record:
        available = {skill["name"] for skill in record["skills"] if skill["enabled"]}
        compact["skills"] = {
            "total_count": len(record["skills"]),
            "enabled_count": sum(skill["enabled"] for skill in record["skills"]),
            "required": {name: name in available for name in record["requirements"]["skills"]},
        }
    return compact


async def read_effective_gateway(client, args: argparse.Namespace):
    """Check native config/read before a turn, on start and on resume.

    openai/codex@a956835d api.py:316-324 exposes AsyncCodexClient as
    _client; async_client.py:132 supports the native typed request.
    Config keeps provider definitions in model_extra (v2_all.py:10581-10584).
    """
    effective = await client.request(
        "config/read",
        {"cwd": str(args.workspace.resolve()), "includeLayers": False},
        response_model=ConfigReadResponse,
    )
    providers = (effective.config.model_extra or {}).get("model_providers")
    provider = effective.config.model_provider
    definition = providers.get(provider) if isinstance(providers, dict) else None
    endpoint = definition.get("base_url") if isinstance(definition, dict) else None
    if endpoint is None:
        raise GatewayRefused("config/read did not report the effective provider base_url")
    try:
        normalized = gateway_endpoint(endpoint)
    except GatewayRefused:
        # Config/read is provider data: never echo an invalid URL's userinfo
        # or query in the public refusal. Same boundary as run_worker's errors.
        raise GatewayRefused(
            "config/read effective provider base_url is outside the host-gateway contract"
        ) from None
    if normalized != args.gateway["endpoint"]:
        raise GatewayRefused(
            f"config/read effective provider base_url {normalized} differs from "
            f"this run's gateway {args.gateway['endpoint']}"
        )
    return effective


async def run_preflight(
    args: argparse.Namespace, *, sdk_factory=AsyncCodexClient, on_event=None
) -> dict:
    """Inspect native catalogs without a thread, model turn or tool call.

    Exactly pinned SDK internals own a separate app-server for this invocation.
    Native 0.160.0 ignores CLI profile selection in app-server mode; configuration
    comes from CODEX_HOME/config.toml and supported config_overrides instead.
    """
    codex = sdk_factory(config=runtime_config(args))
    startup = None
    phase = "initialize"
    record = {
        **initial_record(args),
        "preflight": True,
        "evidence_scope": "native_catalog_discovery",
    }

    async def initialize():
        await codex.start()
        return await codex.initialize()

    try:
        async with asyncio.timeout(args.timeout):
            startup = asyncio.create_task(initialize())
            record["native_runtime"] = native_runtime(await asyncio.shield(startup))
            phase = "configuration_read"
            effective = await read_effective_gateway(codex, args)
            record["effective_config"] = {
                "model": effective.config.model,
                "model_provider": effective.config.model_provider,
                "model_reasoning_effort": effective.config.model_reasoning_effort.value
                if effective.config.model_reasoning_effort is not None
                else None,
            }
            if effective.config.model != args.model or effective.config.model_provider != PROVIDER:
                raise RuntimeError("native configuration did not retain the requested routing")
            # Config's public extra fields carry native MCP/agent configuration.
            # Keep only names, enabled flags and routing metadata, never the
            # full configuration, environment values, descriptions or paths.
            extra = effective.config.model_extra or {}
            configured_mcp = extra.get("mcp_servers") or {}
            agents = extra.get("agents") or {}
            record["agent_defaults"] = {
                key: agents[key]
                for key in (
                    "enabled",
                    "max_concurrent_threads_per_session",
                    "default_subagent_model",
                    "default_subagent_reasoning_effort",
                )
                if key in agents
            }
            record["configured_roles"] = [
                {"name": name} for name, role in sorted(agents.items()) if isinstance(role, dict)
            ]
            phase = "mcp_discovery"
            servers, cursor, seen_cursors = [], None, set()
            while True:
                page = await codex.request(
                    "mcpServerStatus/list",
                    {"cursor": cursor, "limit": 100, "detail": "full"},
                    response_model=ListMcpServerStatusResponse,
                )
                for server in page.data:
                    configured = configured_mcp.get(server.name)
                    servers.append(
                        {
                            "name": server.name,
                            "configured": isinstance(configured, dict),
                            "enabled": isinstance(configured, dict)
                            and configured.get("enabled", True) is True,
                            # Without threadId, native status is null. Preserve
                            # unknown; catalog discovery is not tool execution.
                            "runtime_status": server.runtime_status.value
                            if server.runtime_status is not None
                            else None,
                            "auth_status": server.auth_status.value,
                            "tool_names": sorted(server.tools),
                            "tools_error": server.tools_error is not None,
                        }
                    )
                cursor = page.next_cursor
                if cursor is None:
                    break
                if cursor in seen_cursors:
                    raise RuntimeError("native MCP pagination did not advance")
                seen_cursors.add(cursor)
            record["mcp_servers"] = sorted(servers, key=lambda server: server["name"])
            phase = "skills_discovery"
            listed = await codex.request(
                "skills/list",
                {"cwds": [str(args.workspace.resolve())], "forceReload": True},
                response_model=SkillsListResponse,
            )
            record["skills"] = [
                {"name": skill.name, "enabled": skill.enabled, "scope": skill.scope.value}
                for entry in listed.data
                for skill in entry.skills
            ]
            record["skill_error_count"] = sum(len(entry.errors) for entry in listed.data)
            available_mcp = {server["name"] for server in servers if mcp_catalog_ready(server)}
            available_skills = {skill["name"] for skill in record["skills"] if skill["enabled"]}
            record["requirements"] = {
                "mcp": args.require_mcp,
                "skills": args.require_skill,
                "unavailable_mcp": sorted(set(args.require_mcp) - available_mcp),
                "unavailable_skills": sorted(set(args.require_skill) - available_skills),
            }
            if on_event is not None:
                on_event({"event": "preflight_discovered", **record})
            phase = "require_capabilities"
            record["status"] = (
                "unavailable"
                if record["requirements"]["unavailable_mcp"]
                or record["requirements"]["unavailable_skills"]
                else "ready"
            )
    except (TimeoutError, asyncio.CancelledError) as exc:
        record.update(
            status="deadline_exceeded" if isinstance(exc, TimeoutError) else "cancelled",
            phase=phase,
        )
        if isinstance(exc, asyncio.CancelledError):
            raise
    except GatewayRefused as exc:
        record.update(status="gateway_refused", error=str(exc), phase=phase)
    except Exception as exc:
        record.update(status="failed", error_type=type(exc).__name__, phase=phase)
    finally:
        await close_runtime(codex, startup, record)
    return record


async def run_worker(
    args: argparse.Namespace, prompt: str, *, sdk_factory=AsyncCodex, on_event=emit
) -> dict:
    """Use native start/resume/turn/interrupt/close, with one overall deadline."""
    codex = None
    startup = None
    turn = None
    native_output = None
    native_saved = False
    phase = "reserve_native_result" if args.native_result else "initialize"
    record = initial_record(args)
    try:
        async with asyncio.timeout(args.timeout):
            if args.native_result and args.native_result.exists():
                raise FileExistsError("native-result must be a new private file")
            phase = "initialize"
            codex = sdk_factory(config=runtime_config(args))
            startup = asyncio.create_task(codex.__aenter__())
            await asyncio.shield(startup)
            record["native_runtime"] = native_runtime(codex.metadata)
            phase = "configuration_read"
            await read_effective_gateway(codex._client, args)
            if args.native_result:
                phase = "reserve_native_result"
                fd = os.open(args.native_result, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                native_output = os.fdopen(fd, "w", encoding="utf-8")
            options = {
                "cwd": str(args.workspace.resolve()),
                "model": args.model,
                "model_provider": PROVIDER,
                "sandbox": Sandbox(args.sandbox),
                "approval_mode": ApprovalMode(args.approval_mode),
            }
            phase = "thread_resume" if args.resume else "thread_start"
            if args.resume:
                thread = await codex.thread_resume(args.resume, **options)
            else:
                thread = await codex.thread_start(ephemeral=False, **options)
            record["thread_id"] = thread.id
            record["thread_mode"] = "resumed" if args.resume else "started"
            selected = (await thread.read()).thread
            if selected.model != args.model or selected.model_provider != PROVIDER:
                raise RuntimeError("native thread did not retain the requested model and provider")
            on_event({"event": "thread_ready", **record})
            phase = "turn_start"
            # Codex owns tools, MCP discovery, skills, caching and compaction.
            # There is no extra skill carrier or Responses prompt rewrite here.
            record["model_inference_submitted"] = True
            turn = await thread.turn(prompt, model=args.model, effort=ReasoningEffort(args.effort))
            phase = "turn_run"
            result = await turn.run()
            record.update(result_record(result))
            if native_output is not None:
                phase = "retain_native_result"
                native = {
                    **record,
                    "items": [item.model_dump(mode="json", by_alias=True) for item in result.items],
                }
                json.dump(native, native_output, ensure_ascii=False, indent=2)
                native_output.write("\n")
                native_output.flush()
                native_saved = True
            phase = "thread_status"
            try:
                record["thread_status"] = (await thread.read()).thread.status.model_dump(
                    mode="json", by_alias=True
                )
            except Exception as exc:
                record["thread_status_error_type"] = type(exc).__name__
    except (TimeoutError, asyncio.CancelledError) as exc:
        completed = record.get("status") == "completed" and phase == "thread_status"
        if completed:
            record["thread_status_error_type"] = type(exc).__name__
        else:
            record.update(
                status="deadline_exceeded" if isinstance(exc, TimeoutError) else "cancelled",
                phase=phase,
            )
        if turn is not None and not completed:
            try:
                await asyncio.wait_for(turn.interrupt(), CLEANUP_TIMEOUT)
                record["interrupt_status"] = "requested"
            except Exception as interrupt_error:
                record["interrupt_status"] = type(interrupt_error).__name__
        if isinstance(exc, asyncio.CancelledError):
            raise
    except GatewayRefused as exc:
        record.update(status="gateway_refused", error=str(exc), phase=phase)
    except Exception as exc:
        # Error messages may carry private tool/provider content. Leave them in
        # native private state; the public-facing result retains type and phase.
        record.update(status="failed", error_type=type(exc).__name__, phase=phase)
    finally:
        try:
            if codex is not None:
                await close_runtime(codex, startup, record)
            else:
                record["cleanup_status"] = "not_started"
        finally:
            if native_output is not None:
                try:
                    if not native_saved:
                        # Keep failures/cancellation inspectable in the reserved private file.
                        native_output.seek(0)
                        native_output.truncate()
                        json.dump(record, native_output, ensure_ascii=False, indent=2)
                        native_output.write("\n")
                finally:
                    native_output.close()
    return record


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--prompt", default="-", help="one bounded task, or - to read stdin")
    parser.add_argument("--resume", help="native thread id from an earlier invocation")
    parser.add_argument(
        "--preflight", action="store_true", help="inspect native catalogs without model inference"
    )
    parser.add_argument(
        "--catalog-details",
        action="store_true",
        help="preflight includes complete sanitized tool and skill catalogs in its result",
    )
    parser.add_argument(
        "--require-mcp",
        action="append",
        default=[],
        help="preflight requires this enabled server's native tool catalog; repeatable",
    )
    parser.add_argument(
        "--require-skill",
        action="append",
        default=[],
        help="preflight requires this enabled native skill name; repeatable",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="explicit native/gateway model id; default Sol/max route",
    )
    parser.add_argument(
        "--effort",
        choices=[ReasoningEffort.max.value, ReasoningEffort.ultra.value],
        default=ReasoningEffort.max.value,
        help=(
            "requested native reasoning effort; default max; "
            "ultra requires a suffixless --model (e.g. cx/gpt-6.1-sol)"
        ),
    )
    parser.add_argument("--base-url", default=None, help="default: this host's recorded gateway")
    parser.add_argument("--unrecorded-gateway-reason", metavar="TEXT")
    parser.add_argument("--gateway-check", action="store_true")
    parser.add_argument("--request-id", type=request_id, default=uuid.uuid4().hex)
    parser.add_argument("--timeout", type=positive_seconds, default=300.0)
    parser.add_argument(
        "--sandbox",
        choices=[Sandbox.read_only.value, Sandbox.workspace_write.value],
        default=Sandbox.workspace_write.value,
    )
    parser.add_argument(
        "--approval-mode",
        choices=[mode.value for mode in ApprovalMode],
        default=ApprovalMode.deny_all.value,
    )
    parser.add_argument(
        "--codex-bin",
        type=Path,
        help="explicit native 0.160.0 binary; defaults to the pinned SDK bundle",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        help="optional private worker config/state; inherited when omitted",
    )
    parser.add_argument(
        "--api-key-env",
        help="optional gateway credential variable name; no credential value is accepted",
    )
    parser.add_argument(
        "--no-provider-retries",
        action="store_true",
        help="disarm native request/stream retries for a measured attempt",
    )
    parser.add_argument(
        "--native-result", type=Path, help="retain full native items in a new private 0600 file"
    )
    args = parser.parse_args(argv)
    try:
        args.gateway = resolve_gateway(args.base_url, args.unrecorded_gateway_reason, GATEWAY_VARIABLES)
        if args.codex_home:
            refuse_home_endpoints(args.codex_home, args.gateway, GATEWAY_VARIABLES)
        args.base_url = args.gateway["endpoint"]
        probe_gateway(args.base_url)
    except GatewayRefused as error:
        parser.error(f"gateway refused: {error}")
    if not args.workspace.is_dir():
        parser.error("workspace must be an existing directory")
    if args.codex_home and not args.codex_home.is_dir():
        parser.error("codex-home must be an existing private state directory")
    if not args.model.strip():
        parser.error("model must be nonempty")
    if args.effort == ReasoningEffort.ultra.value and args.model.endswith(GATEWAY_EFFORT_SUFFIXES):
        parser.error(
            "--effort ultra requires a suffixless --model (e.g. cx/gpt-6.1-sol); "
            "lexical fail-closed check also refuses IDs whose own name ends "
            "in a listed token, regardless of gateway alias recognition"
        )
    if (args.require_mcp or args.require_skill) and not args.preflight:
        parser.error("require-mcp and require-skill require --preflight")
    if args.catalog_details and not args.preflight:
        parser.error("catalog-details requires --preflight")
    if any(not name.strip() for name in [*args.require_mcp, *args.require_skill]):
        parser.error("required capability names must be nonempty")
    if args.preflight and (args.resume or args.native_result):
        parser.error("preflight cannot resume a thread or retain turn items")
    return args


def main() -> int:
    args = parse_args()
    prompt = ""
    if not args.preflight:
        prompt = sys.stdin.read() if args.prompt == "-" else args.prompt
    if not args.preflight and not prompt.strip():
        raise SystemExit("prompt must contain a bounded task")
    try:
        result = asyncio.run(run_preflight(args) if args.preflight else run_worker(args, prompt))
    except KeyboardInterrupt:
        emit(
            {
                "event": "cancelled",
                "request_id": args.request_id,
                "usage_status": "unknown",
                "usage": None,
            }
        )
        return 130
    output = (
        preflight_output(result, catalog_details=args.catalog_details) if args.preflight else result
    )
    emit({"event": "result", **output})
    return (
        0
        if result["status"] in {"completed", "ready"} and result["cleanup_status"] == "closed"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
