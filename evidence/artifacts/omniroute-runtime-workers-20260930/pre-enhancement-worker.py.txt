#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "openai-codex==0.159.2",
# ]
# ///
"""One native Codex SDK turn through an invocation-scoped OmniRoute provider.

Derived from openai/codex rust-v0.159.2, commit
ff6aec96948b70d94983af2641a6b67c94faeff5, sdk/python/examples/{01,05,14}_*
and sdk/python/src/openai_codex/{api,client,_run}.py. See README.md for sources.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from openai_codex import ApprovalMode, AsyncCodex, CodexConfig, Sandbox
from openai_codex.types import ReasoningEffort

SDK_VERSION = "0.159.2"
PROVIDER = "omniroute_runtime"
DEFAULT_MODEL = "cx/gpt-6.1-sol-max"
DEFAULT_BASE_URL = "http://127.0.0.1:20128/v1"
CLEANUP_TIMEOUT = 5.0


def gateway_url(value: str) -> str:
    """Keep the owned gateway and any explicit observer on HTTP loopback /v1."""
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/v1"
    ):
        raise argparse.ArgumentTypeError("expected a port-qualified HTTP loopback /v1 URL")
    return value.rstrip("/")


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
        'model_reasoning_effort="max"',
        prefix + 'name="OmniRoute runtime workers"',
        prefix + "base_url=" + quoted(args.base_url),
        prefix + 'wire_api="responses"',
        prefix + "requires_openai_auth=false",
        prefix + "supports_websockets=false",
        prefix + 'http_headers={"x-request-id"=' + quoted(args.request_id) + "}",
    )
    if args.api_key_env:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.api_key_env):
            raise ValueError("api-key-env must name an environment variable")
        overrides += (prefix + "env_key=" + quoted(args.api_key_env),)
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
        env=env,
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


async def run_worker(
    args: argparse.Namespace, prompt: str, *, sdk_factory=AsyncCodex, on_event=emit
) -> dict:
    """Use native start/resume/turn/interrupt/close, with one overall deadline."""
    codex = sdk_factory(config=runtime_config(args))
    turn = None
    phase = "initialize"
    record = {
        "request_id": args.request_id,
        "requested_model": args.model,
        "requested_effort": "max",
        "provider": PROVIDER,
        "model_inference_submitted": False,
        "usage_status": "unknown",
        "usage_scope": None,
        "usage": None,
    }
    try:
        async with asyncio.timeout(args.timeout):
            await codex.__aenter__()
            server = codex.metadata.serverInfo
            if server is None or server.version.split()[0] != SDK_VERSION:
                raise RuntimeError("native runtime does not match the qualified SDK pin")
            record["native_runtime"] = {"name": server.name, "version": server.version}
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
            turn = await thread.turn(prompt, model=args.model, effort=ReasoningEffort.max)
            phase = "turn_run"
            result = await turn.run()
            record.update(result_record(result))
            if args.native_result:
                phase = "retain_native_result"
                native = {
                    **record,
                    "items": [item.model_dump(mode="json", by_alias=True) for item in result.items],
                }
                fd = os.open(args.native_result, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as output:
                    json.dump(native, output, ensure_ascii=False, indent=2)
                    output.write("\n")
    except (TimeoutError, asyncio.CancelledError) as exc:
        record.update(
            status="deadline_exceeded" if isinstance(exc, TimeoutError) else "cancelled",
            phase=phase,
        )
        if turn is not None:
            try:
                await asyncio.wait_for(turn.interrupt(), CLEANUP_TIMEOUT)
                record["interrupt_status"] = "requested"
            except Exception as interrupt_error:
                record["interrupt_status"] = type(interrupt_error).__name__
        if isinstance(exc, asyncio.CancelledError):
            raise
    except Exception as exc:
        # Error messages may carry private tool/provider content. Leave them in
        # native private state; the public-facing result retains type and phase.
        record.update(status="failed", error_type=type(exc).__name__, phase=phase)
    finally:
        try:
            await asyncio.wait_for(codex.close(), CLEANUP_TIMEOUT)
            record["cleanup_status"] = "closed"
        except Exception as exc:
            record.update(status="cleanup_failed", cleanup_status=type(exc).__name__)
    return record


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--prompt", default="-", help="one bounded task, or - to read stdin")
    parser.add_argument("--resume", help="native thread id from an earlier invocation")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="explicit native/gateway model id; default Sol/max route",
    )
    parser.add_argument("--base-url", type=gateway_url, default=DEFAULT_BASE_URL)
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
        help="explicit native 0.159.2 binary; defaults to the pinned SDK bundle",
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
    if not args.workspace.is_dir():
        parser.error("workspace must be an existing directory")
    if args.codex_home and not args.codex_home.is_dir():
        parser.error("codex-home must be an existing private state directory")
    if not args.model.strip():
        parser.error("model must be nonempty")
    return args


def main() -> int:
    args = parse_args()
    prompt = sys.stdin.read() if args.prompt == "-" else args.prompt
    if not prompt.strip():
        raise SystemExit("prompt must contain a bounded task")
    try:
        result = asyncio.run(run_worker(args, prompt))
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
    emit({"event": "result", **result})
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
