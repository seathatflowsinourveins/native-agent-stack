#!/usr/bin/env python3
"""Round 3 diagnostic (no inference, added after the events turn; labelled late in the receipts).

Starts an ephemeral thread in the isolated CODEX_HOME without submitting a turn and records every
mcpServer/startupStatus/updated notification payload, to name the servers behind the two such
notifications seen in the gap-10 events turn. Usage: mcp_startup_probe.py CODEX_BIN CODEX_HOME WORKSPACE OUT
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from openai_codex.client import CodexClient, CodexConfig


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


def main() -> int:
    codex_bin, home, ws, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    seen: list[dict] = []
    with CodexClient(CodexConfig(codex_bin=codex_bin, cwd=str(ws), env={"CODEX_HOME": str(home)})) as client:
        client.initialize()

        def drain():
            try:
                while True:
                    n = client.next_notification()
                    seen.append({"method": n.method, "params": n.payload.model_dump(mode="json", by_alias=True)})
            except Exception:
                pass

        threading.Thread(target=drain, daemon=True).start()
        client.request("thread/start", {"cwd": str(ws), "ephemeral": True, "sandbox": "read-only",
                                        "approvalPolicy": "never"}, response_model=Loose)
        time.sleep(8)
        status = client.request("mcpServerStatus/list", {}, response_model=Loose).model_dump(mode="json", by_alias=True)
    rec = {"model_inference_submitted": False,
           "startup_status": [s["params"] for s in seen if s["method"] == "mcpServer/startupStatus/updated"],
           "global_methods": sorted({s["method"] for s in seen}),
           "mcp_status_after_thread_start": [d.get("name") for d in (status.get("data") or [])]}
    out.write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps(rec)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
