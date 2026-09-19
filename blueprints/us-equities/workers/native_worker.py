#!/usr/bin/env python3
"""Small official Codex SDK example; not a trading engine or durable job queue."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from pathlib import Path

from openai_codex import AsyncCodex, ApprovalMode, CodexConfig, Sandbox
from openai_codex.client import CodexClient
from openai_codex.generated.v2_all import GetAccountRateLimitsResponse

MODEL = "gpt-6-astra"


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


async def run(config: CodexConfig, prompt: str, deadline: float, receipt: dict) -> dict:
    policy = Path(__file__).with_name("policy.md").read_text()
    async with AsyncCodex(config) as codex:
        thread = await codex.thread_start(
            cwd=config.cwd, model=MODEL, ephemeral=True,
            sandbox=Sandbox.read_only, approval_mode=ApprovalMode.deny_all,
            developer_instructions=policy)
        selected = (await thread.read()).thread
        receipt["configured_model"] = selected.model
        receipt["configured_provider"] = selected.model_provider
        if selected.model != MODEL or selected.model_provider != "openai":
            return {"status": "blocked_model_or_provider_mismatch", "usage": None}
        turn = await thread.turn(prompt, model=MODEL)
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
                "items": [item.model_dump(by_alias=True, mode="json") for item in result.items],
                "usage": result.usage.model_dump(by_alias=True, mode="json")
                if result.usage is not None else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "run"))
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--context-mode-start", type=Path,
                        help="installed upstream start.mjs; scopes this worker's MCP server")
    parser.add_argument("--turn-deadline-seconds", type=float, default=180,
                        help="turn-stream deadline; excludes startup and readiness")
    args = parser.parse_args()
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
    overrides = ()
    if args.context_mode_start is not None:
        if not args.context_mode_start.is_file():
            parser.error("Context Mode start.mjs must already be installed")
        fields = {"command": "node", "args": [str(args.context_mode_start.resolve())],
                  "cwd": str(args.workspace.resolve()),
                  "env.CONTEXT_MODE_PLATFORM": "codex",
                  "env.CONTEXT_MODE_PROJECT_DIR": str(args.workspace.resolve())}
        overrides = tuple("mcp_servers.context-mode." + key + "=" + json.dumps(value)
                          for key, value in fields.items())
    config = CodexConfig(codex_bin=args.codex_bin, cwd=str(args.workspace.resolve()),
                         config_overrides=overrides,
                         env={"CODEX_HOME": str(args.codex_home.resolve()),
                              "CONTEXT_MODE_PROJECT_DIR": str(args.workspace.resolve())})
    result = {"mode": args.mode, "model_inference_submitted": False,
              "usage": None, "usage_status": "not_requested"}
    exit_code = 1
    # Reserve a private receipt before any possible model request.
    fd = os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        try:
            with CodexClient(config) as client:
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
            else:
                result.update(asyncio.run(run(config, prompt, args.turn_deadline_seconds, result)))
                exit_code = 0 if result["status"] == "completed" else 1
        except Exception as error:
            # This PRIVATE artifact may include service errors. Review before sharing.
            result.update(status="failed", error_type=type(error).__name__, error=str(error))
            result["usage_status"] = "unavailable_after_failure"
        finally:
            output.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "model_inference_submitted": result["model_inference_submitted"]}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
