#!/usr/bin/env python3
"""codex-native-sdk arm: reuse the committed c20 helper (blueprints/us-equities/workers/
native_worker.py) unchanged for readiness() and run(); only the native config overrides
differ: lifecycle hooks are disabled so no ai-memory hook call reaches the live store, and
optional extra MCP registrations (e.g. an isolated ai-memory, a disposable SocratiCode, a
synthetic broker mock) are added with `-c` style overrides.

Usage:
  sdk_arm.py inspect --workspace DIR --receipt OUT.json
  sdk_arm.py run --workspace DIR --prompt FILE --receipt OUT.json [--override k=v ...]
"""
import argparse
import asyncio
import importlib.util
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
spec = importlib.util.spec_from_file_location("native_worker", REPO / "blueprints/us-equities/workers/native_worker.py")
nw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nw)

from openai_codex import CodexConfig  # noqa: E402
from openai_codex.client import CodexClient  # noqa: E402
from openai_codex.generated.v2_all import GetAccountRateLimitsResponse  # noqa: E402

BASE_OVERRIDES = ("features.hooks=false", "features.plugin_hooks=false")


async def run_custom(config, prompt, deadline, receipt, developer_instructions):
    """nw.run() with the developer instructions replaced; everything else identical."""
    from openai_codex import AsyncCodex, ApprovalMode, Sandbox
    async with AsyncCodex(config) as codex:
        thread = await codex.thread_start(cwd=config.cwd, model=nw.MODEL, ephemeral=True, sandbox=Sandbox.read_only,
                                          approval_mode=ApprovalMode.deny_all, developer_instructions=developer_instructions)
        selected = (await thread.read()).thread
        receipt["configured_model"], receipt["configured_provider"] = selected.model, selected.model_provider
        turn = await thread.turn(prompt, model=nw.MODEL)
        receipt["model_inference_submitted"] = True
        result = await asyncio.wait_for(turn.run(), deadline)
        return {"status": result.status.value, "final_response": result.final_response, "duration_ms": result.duration_ms,
                "usage_status": "reported" if result.usage is not None else "unavailable",
                "items": [i.model_dump(by_alias=True, mode="json") for i in result.items],
                "usage": result.usage.model_dump(by_alias=True, mode="json") if result.usage is not None else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("inspect", "run"))
    ap.add_argument("--codex-bin", default=os.path.expanduser("~/.local/share/codex-ecosystem/bin/codex"))
    ap.add_argument("--codex-home", default=os.path.expanduser("~/.codex"))
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--prompt", type=Path)
    ap.add_argument("--receipt", type=Path, required=True)
    ap.add_argument("--override", action="append", default=[])
    ap.add_argument("--deadline", type=float, default=300)
    ap.add_argument("--developer-instructions", type=Path, help="replace policy.md (default: the c20 policy)")
    a = ap.parse_args()
    overrides = BASE_OVERRIDES + tuple(a.override)

    def cfg():
        return CodexConfig(codex_bin=a.codex_bin, cwd=str(a.workspace.resolve()), config_overrides=overrides,
                           env={"CODEX_HOME": a.codex_home, **nw.process_telemetry_env("gap-wave2-sdk-arm")})

    result = {"mode": a.mode, "overrides": list(overrides), "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "model_inference_submitted": False}
    t0 = time.monotonic()
    try:
        with CodexClient(cfg()) as client:
            client.initialize()
            models = client.model_list().model_dump(by_alias=True, mode="json")
            limits = client.request("account/rateLimits/read", {}, response_model=GetAccountRateLimitsResponse
                                    ).model_dump(by_alias=True, mode="json")
        result["readiness"] = nw.readiness(models, limits)
        if a.mode == "run":
            if not result["readiness"]["ready"]:
                result["status"] = "blocked_native_allowance_or_model"
            else:
                if a.developer_instructions:
                    result["developer_instructions"] = str(a.developer_instructions)
                    result.update(asyncio.run(run_custom(cfg(), a.prompt.read_text(), a.deadline, result,
                                                         a.developer_instructions.read_text())))
                else:
                    result.update(asyncio.run(nw.run(cfg(), a.prompt.read_text(), a.deadline, result)))
        else:
            result["status"] = "discovery_complete"
    except Exception as e:  # keep the raw error
        result.update(status="failed", error_type=type(e).__name__, error=str(e))
    result["wall_seconds"] = round(time.monotonic() - t0, 3)
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    a.receipt.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({k: result.get(k) for k in ("status", "wall_seconds", "usage_status")}))


if __name__ == "__main__":
    main()
