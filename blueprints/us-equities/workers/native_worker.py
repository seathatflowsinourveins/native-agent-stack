#!/usr/bin/env python3
"""Small official Codex SDK example; not a trading engine or durable job queue."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import tomllib
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

import openai_codex
from openai_codex import AsyncCodex, ApprovalMode, CodexConfig, Sandbox
from openai_codex.client import CodexClient
from openai_codex.generated.v2_all import GetAccountRateLimitsResponse

MODEL = "gpt-6-astra"
GATEWAY_MODEL = "cx/gpt-6-astra-max"


def gateway_base_url(value: str) -> str:
    """Keep the adopted keyless inference service inside its loopback scope."""
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path.rstrip("/") != "/v1"
            or parsed.port is None):
        raise ValueError("gateway base URL must be a port-qualified HTTP loopback /v1 endpoint")
    return value.rstrip("/")


def route_overrides(provider: str, base_url: str, extra: tuple[str, ...]) -> tuple[str, ...]:
    """Use native Codex provider settings; do not create a second agent loop.

    Sources: openai/codex rust-v0.159.2 sdk/python and the official
    https://developers.openai.com/codex/config-reference/ provider contract.
    """
    if provider == "openai":
        return (*extra, 'model_reasoning_effort="max"')
    if provider != "omniroute":
        raise ValueError("unsupported provider")
    base_url = gateway_base_url(base_url)
    for override in extra:
        parsed = tomllib.loads(override)
        if {"model", "model_provider", "model_reasoning_effort", "model_providers"} & parsed.keys():
            raise ValueError("extra overrides must not replace the OmniRoute route contract")
    return (*extra, 'model_provider="omniroute"', 'model_reasoning_effort="max"',
            'model_providers.omniroute.name="OmniRoute clean GPT lane"',
            "model_providers.omniroute.base_url=" + json.dumps(base_url),
            'model_providers.omniroute.wire_api="responses"',
            "model_providers.omniroute.requires_openai_auth=false")


def gateway_readiness(base_url: str) -> dict:
    """Inspect advertised models only; this is not a successful model run.

    The custom provider uses gateway readiness rather than the native account's
    subscription allowance. No sign-in or authentication store is read here.
    """
    endpoint = gateway_base_url(base_url) + "/models"
    with urlopen(endpoint, timeout=10) as response:
        raw = response.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("gateway model listing exceeds the bounded readiness contract")
    listing = json.loads(raw)
    available = any(model.get("id") == GATEWAY_MODEL for model in listing.get("data", []))
    return {"model": GATEWAY_MODEL, "model_available": available,
            "provider": "omniroute", "evidence_level": "advertised_model_only",
            "ready": available}


def process_telemetry_env(scope: str) -> dict[str, str]:
    """Identify each native subprocess without reusing a parent's metric writer ID."""
    retained = [part.strip() for part in os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "").split(",")
                if part.strip() and part.strip().split("=", 1)[0]
                not in {"service.instance.id", "ecosystem.client.scope"}]
    return {"OTEL_RESOURCE_ATTRIBUTES": ",".join([
        *retained, f"service.instance.id={uuid.uuid4()}", f"ecosystem.client.scope={scope}"])}


def write_observation(directory: Path, result: dict) -> None:
    """Atomically publish bounded metadata, without additive token claims.

    Codex rust-v0.159.2 _run.py returns ThreadTokenUsage: total accumulates across
    the thread and last describes only the last request. Neither is a per-turn
    delta. Preserve the native usage in the private result; without a serialized
    preceding baseline this observation has no additive usage to publish.
    """
    identifier = str(uuid.uuid4())
    observation = {"observation_id": identifier}
    observation.update({key: result.get(key) for key in (
        "status", "configured_model", "duration_ms", "usage_status", "usage_scope")})
    observation["usage"] = None
    temporary = directory / (identifier + ".pending")
    final = directory / (identifier + ".json")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as output:
            output.write(json.dumps(observation, indent=2) + "\n")
            output.flush()
            os.fsync(output.fileno())
        # A link publishes the completed file atomically and refuses replacement.
        os.link(temporary, final)
    finally:
        temporary.unlink(missing_ok=True)


def readiness(models: dict, limits: dict) -> dict:
    """Publish an allowlist of fields; never the account object or session IDs."""
    available = any(m.get("model") == MODEL for m in models.get("data", []))
    bucket = (limits.get("rateLimitsByLimitId") or {}).get("codex")
    bucket = bucket or limits.get("rateLimits") or {}
    windows = {k: {f: (bucket.get(k) or {}).get(f)
                   for f in ("usedPercent", "resetsAt", "windowDurationMins")}
               for k in ("primary", "secondary") if bucket.get(k)}
    ordinary = limits.get("ordinaryUsageAllowed")
    known = bool(windows) and all(
        isinstance(w.get("usedPercent"), (int, float))
        and not isinstance(w["usedPercent"], bool)
        and math.isfinite(w["usedPercent"]) and 0 <= w["usedPercent"] <= 100
        for w in windows.values())
    exhausted = known and any(w["usedPercent"] >= 100 for w in windows.values())
    # Unknown allowance is not authorization to fall back to a paid API/model.
    ready = available and ordinary is True and known and not exhausted
    return {"model": MODEL, "model_available": available,
            "ordinary_usage_allowed": ordinary, "windows": windows,
            "ready": ready}


async def run(config: CodexConfig, prompt: str, deadline: float, receipt: dict,
              thread_options: dict | None = None) -> dict:
    """Run one turn. Defaults keep the original ephemeral, read-only, deny-all thread.

    thread_options may set persistent (keep the thread for a later resume),
    resume_thread_id (continue an earlier persistent thread in this new process),
    sandbox and approval_mode.
    """
    options = thread_options or {}
    model = options.get("model", MODEL)
    provider = options.get("provider", "openai")
    sandbox = options.get("sandbox", Sandbox.read_only)
    approval_mode = options.get("approval_mode", ApprovalMode.deny_all)
    policy = Path(__file__).with_name("policy.md").read_text()
    async with AsyncCodex(config) as codex:
        metadata = codex.metadata.model_dump(by_alias=True, mode="json")
        receipt["native_runtime"] = {"server_info": metadata.get("serverInfo"),
                                     "user_agent": metadata.get("userAgent")}
        if options.get("resume_thread_id"):
            thread = await codex.thread_resume(
                options["resume_thread_id"], cwd=config.cwd, model=model,
                sandbox=sandbox, approval_mode=approval_mode,
                developer_instructions=policy)
            receipt["thread_id"] = thread.id
            receipt["thread_mode"] = "resumed"
        else:
            persistent = bool(options.get("persistent"))
            thread = await codex.thread_start(
                cwd=config.cwd, model=model, ephemeral=not persistent,
                sandbox=sandbox, approval_mode=approval_mode,
                developer_instructions=policy)
            receipt["thread_mode"] = "persistent" if persistent else "ephemeral"
            if persistent:
                # PRIVATE receipt only: needed to resume this thread from a new process.
                receipt["thread_id"] = thread.id
        selected = (await thread.read()).thread
        receipt["configured_model"] = selected.model
        receipt["configured_provider"] = selected.model_provider
        if selected.model != model or selected.model_provider != provider:
            return {"status": "blocked_model_or_provider_mismatch", "usage": None}
        turn = await thread.turn(prompt, model=model)
        receipt["model_inference_submitted"] = True
        pending = asyncio.create_task(turn.run())
        try:
            result = await asyncio.wait_for(asyncio.shield(pending), deadline)
        except TimeoutError:
            try:
                await asyncio.wait_for(turn.interrupt(), 10)
            finally:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            return {"status": "deadline_interrupt_requested", "usage": None,
                    "usage_status": "unavailable_after_timeout"}
        return {"status": result.status.value,
                "final_response": result.final_response,
                "duration_ms": result.duration_ms,
                "usage_status": "reported" if result.usage is not None else "unavailable",
                "usage_scope": "native_thread_cumulative" if result.usage is not None else None,
                "items": [item.model_dump(by_alias=True, mode="json") for item in result.items],
                "usage": result.usage.model_dump(by_alias=True, mode="json")
                if result.usage is not None else None}


class LookupTool:
    """One read-only custom tool: a key-value lookup from a local JSON file.

    Answers the app-server's `item/tool/call` request for the registered name and
    declines every command or file approval request (the tool path is deny-all).
    """

    def __init__(self, spec_file: Path):
        data = json.loads(spec_file.read_text())
        self.name = str(data["name"])
        self.values = {str(k): str(v) for k, v in dict(data["values"]).items()}
        self.spec = {"type": "function", "name": self.name,
                     "description": str(data.get("description") or "Return the stored value for a key."),
                     "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}},
                                     "required": ["key"], "additionalProperties": False}}
        self.calls: list[dict] = []
        self.declined: list[str] = []

    def __call__(self, method: str, params: dict | None) -> dict:
        if method == "item/tool/call":
            p = params or {}
            key = str((p.get("arguments") or {}).get("key", ""))
            ok = p.get("tool") == self.name and key in self.values
            self.calls.append({"tool": p.get("tool"), "key": key, "answered": ok})
            text = self.values[key] if ok else "unknown tool or key"
            return {"contentItems": [{"type": "inputText", "text": text}], "success": ok}
        self.declined.append(method)
        if method in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval"):
            return {"decision": "decline"}
        return {}


def run_with_tool(config: CodexConfig, prompt: str, deadline: float, receipt: dict,
                  thread_options: dict, tool: LookupTool) -> dict:
    """Run one deny-all turn with one custom tool registered through the SDK client.

    The high-level AsyncCodex.thread_start has no dynamic-tool field in 0.159.2, so
    this path uses the SDK's CodexClient: its approval_handler answers the tool
    call and its thread_start/thread_resume accept the app-server's JSON params.
    """
    from openai_codex.generated.v2_all import (
        ItemCompletedNotification, ThreadTokenUsageUpdatedNotification, TurnCompletedNotification)
    import threading
    policy = Path(__file__).with_name("policy.md").read_text()
    sandbox = "workspace-write" if thread_options["sandbox"] == Sandbox.workspace_write else "read-only"
    model = thread_options.get("model", MODEL)
    provider = thread_options.get("provider", "openai")
    common = {"cwd": config.cwd, "model": model, "sandbox": sandbox, "approvalPolicy": "never",
              "developerInstructions": policy}
    with CodexClient(config, approval_handler=tool) as client:
        metadata = client.initialize().model_dump(by_alias=True, mode="json")
        receipt["native_runtime"] = {"server_info": metadata.get("serverInfo"),
                                     "user_agent": metadata.get("userAgent")}
        receipt["dynamic_tool"] = {"name": tool.name, "registered": False}
        if thread_options.get("resume_thread_id"):
            thread_id = client.thread_resume(thread_options["resume_thread_id"], common).thread.id
            receipt["thread_id"], receipt["thread_mode"] = thread_id, "resumed"
            receipt["dynamic_tool"]["registered"] = "at_thread_start_of_resumed_thread"
        else:
            persistent = bool(thread_options.get("persistent"))
            thread_id = client.thread_start({**common, "ephemeral": not persistent,
                                             "dynamicTools": [tool.spec]}).thread.id
            receipt["thread_mode"] = "persistent" if persistent else "ephemeral"
            receipt["dynamic_tool"]["registered"] = True
            if persistent:
                # PRIVATE receipt only: needed to resume this thread from a new process.
                receipt["thread_id"] = thread_id
        selected = client.thread_read(thread_id).thread
        receipt["configured_model"] = selected.model
        receipt["configured_provider"] = selected.model_provider
        if selected.model != model or selected.model_provider != provider:
            return {"status": "blocked_model_or_provider_mismatch", "usage": None}
        turn_id = client.turn_start(thread_id, prompt, {"model": model}).turn.id
        receipt["model_inference_submitted"] = True
        box: dict = {"items": [], "usage": None}

        def drain() -> None:
            try:
                while True:
                    payload = client.next_turn_notification(turn_id).payload
                    if isinstance(payload, ItemCompletedNotification):
                        box["items"].append(payload.item)
                    elif isinstance(payload, ThreadTokenUsageUpdatedNotification):
                        box["usage"] = payload.token_usage
                    elif isinstance(payload, TurnCompletedNotification):
                        box["completed"] = payload.turn
                        return
            except Exception as error:
                box["error"] = error

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        reader.join(deadline)
        receipt["dynamic_tool"]["calls"] = tool.calls
        receipt["dynamic_tool"]["declined_server_requests"] = tool.declined
        if "completed" not in box:
            if "error" in box:
                raise box["error"]
            client.turn_interrupt(thread_id, turn_id)
            return {"status": "deadline_interrupt_requested", "usage": None,
                    "usage_status": "unavailable_after_timeout"}
    turn, usage = box["completed"], box["usage"]
    items = [item.model_dump(by_alias=True, mode="json") for item in box["items"]]
    messages = [i for i in items if i.get("type") == "agentMessage"]
    final = next((m for m in reversed(messages) if m.get("phase") == "final_answer"), None) \
        or (messages[-1] if messages else None)
    return {"status": turn.status.value, "final_response": final.get("text") if final else None,
            "duration_ms": turn.duration_ms,
            "usage_status": "reported" if usage is not None else "unavailable",
            "usage_scope": "native_thread_cumulative" if usage is not None else None,
            "items": items,
            "usage": usage.model_dump(by_alias=True, mode="json") if usage is not None else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "run"))
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--provider", choices=("openai", "omniroute"), default="openai",
                        help="native account control or the clean loopback GPT worker lane")
    parser.add_argument("--gateway-base-url", default="http://127.0.0.1:20128/v1",
                        help="port-qualified loopback /v1 endpoint; used only for OmniRoute")
    parser.add_argument("--context-mode-start", type=Path,
                        help="installed upstream start.mjs; scopes this worker's MCP server")
    parser.add_argument("--turn-deadline-seconds", type=float, default=180,
                        help="turn-stream deadline; excludes startup and readiness")
    parser.add_argument("--persistent", action="store_true",
                        help="keep the thread (not ephemeral) and record its id in the private receipt")
    parser.add_argument("--resume-thread-id",
                        help="resume an earlier persistent thread by id in this new process")
    parser.add_argument("--sandbox", choices=("read-only", "workspace-write"), default="read-only")
    parser.add_argument("--approval-mode", choices=("deny_all", "auto_review"), default="deny_all",
                        help="non-interactive approval behaviour; deny_all maps to approval policy never")
    parser.add_argument("--config-override", action="append", default=[], metavar="KEY=TOML",
                        help="extra native Codex -c override for this worker process (repeatable)")
    parser.add_argument("--lookup-tool", type=Path, metavar="JSON",
                        help="register one read-only custom lookup tool: {name, description, values}; deny_all only")
    parser.add_argument("--observation-dir", type=Path,
                        default=os.environ.get("ECOSYSTEM_SDK_OBSERVATION_DIR"),
                        help="optional existing private directory watched by the native Collector file receiver")
    args = parser.parse_args()
    if args.observation_dir is not None and not args.observation_dir.is_dir():
        parser.error("observation directory must already exist")
    if not args.workspace.is_dir() or not args.codex_home.is_dir():
        parser.error("workspace and native Codex home must already exist")
    if args.receipt.exists():
        parser.error("choose a new private receipt path; existing files are preserved")
    if not 1 <= args.turn_deadline_seconds <= 600:
        parser.error("deadline must be between 1 and 600 seconds")
    prompt = ""
    if args.mode == "run":
        if args.prompt is None:
            parser.error("run requires --prompt")
        raw = args.prompt.read_bytes()
        if not 1 <= len(raw) <= 12288:
            parser.error("prompt must be 1..12288 bytes; retrieve focused context first")
        prompt = raw.decode("utf-8")
    if args.persistent and args.resume_thread_id:
        parser.error("--persistent starts a thread; --resume-thread-id continues one")
    tool = None
    if args.lookup_tool is not None:
        if args.approval_mode != "deny_all":
            parser.error("--lookup-tool runs deny_all only")
        tool = LookupTool(args.lookup_tool)
    try:
        overrides = route_overrides(args.provider, args.gateway_base_url, tuple(args.config_override))
    except (ValueError, tomllib.TOMLDecodeError) as error:
        parser.error(str(error))
    if args.context_mode_start is not None:
        if not args.context_mode_start.is_file():
            parser.error("Context Mode start.mjs must already be installed")
        fields = {"command": "node", "args": [str(args.context_mode_start.resolve())],
                  "cwd": str(args.workspace.resolve()),
                  "env.CONTEXT_MODE_PLATFORM": "codex",
                  "env.CONTEXT_MODE_PROJECT_DIR": str(args.workspace.resolve())}
        overrides += tuple("mcp_servers.context-mode." + key + "=" + json.dumps(value)
                           for key, value in fields.items())
    def config_for_process() -> CodexConfig:
        return CodexConfig(codex_bin=args.codex_bin, cwd=str(args.workspace.resolve()),
                           config_overrides=overrides,
                           env={"CODEX_HOME": str(args.codex_home.resolve()),
                                "CONTEXT_MODE_PROJECT_DIR": str(args.workspace.resolve()),
                                **process_telemetry_env("sdk-worker")})
    result = {"mode": args.mode, "model_inference_submitted": False,
              "usage": None, "usage_status": "not_requested", "usage_scope": None,
              "sdk_version": openai_codex.__version__, "sandbox": args.sandbox,
              "route_contract": {"provider": args.provider,
                                 "model": GATEWAY_MODEL if args.provider == "omniroute" else MODEL,
                                 "reasoning_effort": "max", "wire_api": "responses"},
              "approval_mode": args.approval_mode, "config_overrides": list(overrides)}
    thread_options = {"persistent": args.persistent, "resume_thread_id": args.resume_thread_id,
                      "model": GATEWAY_MODEL if args.provider == "omniroute" else MODEL,
                      "provider": args.provider,
                      "sandbox": Sandbox.workspace_write if args.sandbox == "workspace-write" else Sandbox.read_only,
                      "approval_mode": ApprovalMode(args.approval_mode)}
    exit_code = 1
    # Reserve a private receipt before any possible model request.
    fd = os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        try:
            if args.provider == "omniroute":
                result["readiness"] = gateway_readiness(args.gateway_base_url)
            else:
                with CodexClient(config_for_process()) as client:
                    client.initialize()
                    models = client.model_list().model_dump(by_alias=True, mode="json")
                    limits = client.request("account/rateLimits/read", {},
                        response_model=GetAccountRateLimitsResponse).model_dump(
                            by_alias=True, mode="json")
                result["readiness"] = readiness(models, limits)
            if args.mode == "inspect":
                result["status"] = "discovery_complete"
                exit_code = 0
            elif not result["readiness"]["ready"]:
                result["status"] = "blocked_native_allowance_or_model"
                exit_code = 2
            elif tool is not None:
                result.update(run_with_tool(config_for_process(), prompt, args.turn_deadline_seconds,
                                            result, thread_options, tool))
                exit_code = 0 if result["status"] == "completed" else 1
            else:
                result.update(asyncio.run(run(config_for_process(), prompt, args.turn_deadline_seconds,
                                              result, thread_options)))
                exit_code = 0 if result["status"] == "completed" else 1
        except Exception as error:
            # This PRIVATE artifact may include service errors. Review before sharing.
            result.update(status="failed", error_type=type(error).__name__, error=str(error))
            result["usage_status"] = "unavailable_after_failure"
        finally:
            if args.observation_dir is not None:
                try:
                    write_observation(args.observation_dir, result)
                    result["observation_status"] = "published_local_receipt"
                except Exception as error:
                    result["observation_status"] = "failed"
                    result["observation_error_type"] = type(error).__name__
                    exit_code = 1
            output.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "model_inference_submitted": result["model_inference_submitted"],
                      "observation_status": result.get("observation_status", "not_configured")}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
