"""Check native connection retention; never inspect HTTP session tokens."""

import json
import os
from pathlib import Path
import subprocess
import time

BASE = Path(os.environ.get("TRIAL_ROOT", "~/.local/state/native-agent-stack/research/api-surfaces-trials/inspector")).expanduser()
OUT = Path(__file__).parent
MCPDO = BASE / "install/bin/mcpdo"
MCPORTER = os.environ.get("MCPORTER_BIN", "mcporter")
for key, value in {"MCP_INSPECTOR_DAEMON_DIR": str(BASE / "d"),
                   "MCPORTER_DAEMON_DIR": str(BASE / "m"),
                   "MCP_STORAGE_DIR": str(BASE / "s")}.items():
    if os.environ.get(key) != value:
        raise SystemExit("Missing private namespace: " + key)


def invoke(args):
    proc = subprocess.run([str(a) for a in args], capture_output=True, timeout=40, check=True)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def inspector(*args):
    return [MCPDO, "--format", "json", *args]


def mcporter(*args):
    return [MCPORTER, "--config", BASE / "mcporter.json", *args]


def safe_mcpdo_connections():
    data = invoke(inspector("connections/list"))
    entries = data if isinstance(data, list) else data.get("connections", [])
    return [{key: entry.get(key) for key in ("name", "connectedAt", "protocolEra")}
            for entry in entries]


def safe_mcporter_connections():
    data = invoke(mcporter("daemon", "status", "--json"))
    return {"pid": data.get("pid"), "servers": [
        {key: server.get(key) for key in ("name", "connectionId", "connectionGeneration", "connected")}
        for server in data.get("servers", [])
    ]}


result = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "scope": "Native named MCP connection retention, not HTTP session-token identity",
          "endpoint": "http://127.0.0.1:29374/mcp", "http_session_tokens_read": False}
try:
    invoke(inspector("--config", str(BASE / "mcpdo.json"), "connect", "trial-ai-memory"))
    invoke(mcporter("list", "trial-ai-memory", "--schema", "--json"))
    result["inspector_before"] = safe_mcpdo_connections()
    result["mcporter_before"] = safe_mcporter_connections()
    if len(result["inspector_before"]) != 1 or len(result["mcporter_before"]["servers"]) != 1:
        raise RuntimeError("Expected one initial native MCP connection in each arm")
    invoke(inspector("--connection", "trial-ai-memory", "tools/call", "memory_status", "{}"))
    invoke(mcporter("call", "trial-ai-memory.memory_status", "--args", "{}", "--output", "json"))
    result["inspector_after"] = safe_mcpdo_connections()
    result["mcporter_after"] = safe_mcporter_connections()
    result["inspector_connection_unchanged"] = result["inspector_before"] == result["inspector_after"]
    result["mcporter_connection_unchanged"] = result["mcporter_before"] == result["mcporter_after"]
    # A different native task type may receive a distinct retained transport.
    # Repeat the same task pair to distinguish a warm retained set from growth.
    invoke(inspector("--connection", "trial-ai-memory", "tools/list"))
    invoke(mcporter("list", "trial-ai-memory", "--schema", "--json"))
    invoke(inspector("--connection", "trial-ai-memory", "tools/call", "memory_status", "{}"))
    invoke(mcporter("call", "trial-ai-memory.memory_status", "--args", "{}", "--output", "json"))
    result["inspector_after_repeat"] = safe_mcpdo_connections()
    result["mcporter_after_repeat"] = safe_mcporter_connections()
    result["inspector_warm_set_unchanged"] = result["inspector_after"] == result["inspector_after_repeat"]
    result["mcporter_warm_set_unchanged"] = result["mcporter_after"] == result["mcporter_after_repeat"]
finally:
    invoke(inspector("daemon", "stop"))
    invoke(mcporter("daemon", "stop"))
    inspector_status = invoke(inspector("daemon", "status"))
    mcporter_status = invoke(mcporter("daemon", "status", "--json"))
    result["cleanup_verified"] = inspector_status.get("running") is False and mcporter_status is None
    (OUT / "persistence.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
