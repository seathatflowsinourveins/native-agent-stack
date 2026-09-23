#!/usr/bin/env python3
"""Effective Codex config snapshot for one CODEX_HOME (no inference). Round 3 of the agent-sdks gap wave.

Records config/read (with layers), mcpServerStatus/list, hooks/list and skills/list for the workspace
cwd, plus which instruction files exist in CODEX_HOME.
Usage: iso_config.py CODEX_BIN CODEX_HOME WORKSPACE OUT [--no-mcp-status]
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from openai_codex.client import CodexClient, CodexConfig


class Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


def call(client, method, params):
    try:
        return client.request(method, params, response_model=Loose).model_dump(mode="json", by_alias=True)
    except Exception as error:  # record, do not hide
        return {"error_type": type(error).__name__, "error": str(error)[:500]}


def main() -> int:
    codex_bin, home, ws, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    with_mcp_status = "--no-mcp-status" not in sys.argv[5:]
    cfg = CodexConfig(codex_bin=codex_bin, cwd=str(ws), env={"CODEX_HOME": str(home)})
    rec = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "codex_bin_sha256": hashlib.sha256(Path(codex_bin).read_bytes()).hexdigest()}
    with CodexClient(cfg) as client:
        init = client.initialize()
        rec["server_info"] = getattr(init, "model_dump", lambda **k: str(init))(mode="json", by_alias=True) \
            if hasattr(init, "model_dump") else str(init)
        conf = call(client, "config/read", {"cwd": str(ws), "includeLayers": True})
        # The parent snapshot skips mcpServerStatus/list so that no host MCP server is started for it.
        rec["mcp_status"] = call(client, "mcpServerStatus/list", {}) if with_mcp_status else {"skipped": True}
        rec["hooks"] = call(client, "hooks/list", {"cwds": [str(ws)]})
        rec["skills"] = call(client, "skills/list", {"cwds": [str(ws)]})
    c = conf.get("config") or {}
    servers = c.get("mcp_servers") or {}
    rec["summary"] = {
        "features": {k: (c.get("features") or {}).get(k) for k in ("hooks", "plugin_hooks", "apps")},
        "plugins": {n: (v or {}).get("enabled") for n, v in (c.get("plugins") or {}).items()},
        "mcp_servers_configured": sorted(servers),
        "mcp_status_names": sorted((s or {}).get("name") for s in (rec["mcp_status"].get("data") or [])),
        "hook_count": sum(len((e or {}).get("hooks") or []) for e in (rec["hooks"].get("data") or [])),
        "skill_count": sum(len((e or {}).get("skills") or []) for e in (rec["skills"].get("data") or [])),
        "otel": {k: (c.get("otel") or {}).get(k) for k in ("exporter", "metrics_exporter")},
        "layer_sources": [((layer or {}).get("name") or {}) for layer in (conf.get("layers") or [])],
        "codex_home_instruction_files": sorted(p.name for p in home.glob("*.md")),
        "config_top_level_keys": sorted(c),
    }
    rec["config_read_error"] = conf.get("error")
    rec["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out.write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps(rec["summary"], default=str)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
