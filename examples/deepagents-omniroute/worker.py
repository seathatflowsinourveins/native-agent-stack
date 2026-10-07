#!/usr/bin/env python3
"""Supported DeepAgents composition for a bounded, persisted research trial."""

import argparse
import hashlib
import ipaddress
import pathlib
import socket
import sys
import urllib.parse
import importlib.metadata
import json
import os
import uuid
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
GATEWAY_VARIABLES = ("OPENAI_BASE_URL", "OPENAI_API_BASE")
GATEWAY_OVERRIDES = ()
GATEWAY_HOMES = ()

if __name__ == "__main__":
    gateway_check(sys.argv[1:], GATEWAY_FLAGS, GATEWAY_VARIABLES, GATEWAY_OVERRIDES, GATEWAY_HOMES)

os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"

import httpx

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.load import dumps
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver

MODEL = "cx/gpt-6.1-sol-max"
RUN_MARKER = "nas-deepagents-omniroute"




def emit(event, native):
    # Native Serializable.to_json replaces registered secrets with references.
    print(dumps({"event": event, "native": native}), flush=True)


def chat_model(api_key_env, base_url):
    # The caller supplies an existing child-route credential through this pointer.
    session_tag = RUN_MARKER + "-" + uuid.uuid4().hex
    return ChatOpenAI(
        model=MODEL,
        base_url=base_url,
        api_key=os.environ[api_key_env],
        # langchain@026c3da2 base.py:1067-1070: supply both native clients.
        http_client=httpx.Client(trust_env=False, follow_redirects=False),
        http_async_client=httpx.AsyncClient(trust_env=False, follow_redirects=False),
        # langchain@026c3da2 base.py:1016,1467; OmniRoute@2f42a9ac
        # attemptLogging.ts:296-299 persists this native header as session_tag.
        # sessionAffinityPin.ts:197-215 reads X-Session-Id for native affinity.
        # Distinct census tags; effective reasoning-replay isolation is unqualified.
        default_headers={
            "X-OmniRoute-Session-Id": session_tag,
            "X-Session-Id": session_tag,
        },
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
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
        "--base-url", default=None, help="default: this host's recorded gateway"
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
    parser.add_argument("--unrecorded-gateway-reason", metavar="TEXT")
    parser.add_argument("--gateway-check", action="store_true")
    args = parser.parse_args(argv)
    try:
        gateway = resolve_gateway(args.base_url, args.unrecorded_gateway_reason, GATEWAY_VARIABLES)
        args.base_url = gateway["endpoint"]
        probe_gateway(args.base_url)
    except GatewayRefused as error:
        if args.describe:
            emit("configuration", {"underlying_lane": None, "gateway_refusal": str(error)})
            return 2
        parser.error(f"gateway refused: {error}")
    config = {
        "configurable": {"thread_id": args.thread_id},
        "recursion_limit": 32,
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
                "underlying_lane": gateway["endpoint"],
                "gateway": gateway,
                "run_marker_prefix": RUN_MARKER + "-",
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
        return 0
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
    raise SystemExit(main())
