"""Facts from one uncounted round-3 probe, fixture-related only: never the host's own servers, plugins or tool results.

usage: probe_facts.py PROBE_NAME [--answer]
Prints the init event's version, model, permission mode and session id; the fixture plugin's entry in init.plugins
and init.plugin_errors; the fixture server's init status and its tools in init.tools; the count of each hook event
subtype in the stream and of those naming the fixture plugin; the run's hook marker and server log (with times
relative to the server's start); the tool calls (name, is_error) in order; and, with --answer, the final answer.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
name = sys.argv[1]
path = HERE / "probe" / f"{name}.jsonl"
init, hooks, calls, results, final = {}, {}, [], {}, {}
for line in path.read_text().splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    t, st = e.get("type"), e.get("subtype")
    if t == "system" and st == "init":
        init = e
    elif t == "system" and str(st).startswith("hook"):
        key = f"{st}:{e.get('hook_event') or e.get('hook_event_name') or '?'}"
        hooks.setdefault(key, [0, 0])
        hooks[key][0] += 1
        hooks[key][1] += "workspace-guard" in json.dumps(e)
    elif t == "assistant":
        calls += [(c.get("id"), c.get("name"), (c.get("input") or {}).get("query"))
                  for c in e["message"].get("content", []) if c.get("type") == "tool_use"]
    elif t == "user" and isinstance(e.get("message", {}).get("content"), list):
        results.update({c.get("tool_use_id"): bool(c.get("is_error")) for c in e["message"]["content"]
                        if c.get("type") == "tool_result"})
    elif t == "result":
        final = e
plugins = [p for p in init.get("plugins") or [] if "workspace-guard" in json.dumps(p)]
errors = [p for p in init.get("plugin_errors") or [] if "workspace-guard" in json.dumps(p)]
server = [s for s in init.get("mcp_servers") or [] if s.get("name") == "ticket-tracker"]
sid = init.get("session_id") or ""
marker = HERE / "fixtures" / "workspace-guard" / "state" / f"{sid}.log"
log = path.with_suffix(".mcplog")
ev = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
t0 = ev[0]["ts"] if ev else 0
print(json.dumps({
    "version": init.get("claude_code_version"), "model": init.get("model"),
    "permission_mode": init.get("permissionMode"), "session_id_set": bool(sid),
    "fixture_plugin_in_init": [{"name": p.get("name"), "path_tail": str(p.get("path"))[-40:]} for p in plugins],
    "fixture_plugin_errors": errors, "init_plugin_count": len(init.get("plugins") or []),
    "fixture_server_in_init": server,
    "fixture_tools_in_init": [t for t in init.get("tools") or [] if str(t).startswith("mcp__ticket-tracker__")],
    "hook_events": hooks,
    "hook_marker": marker.read_text().splitlines() if marker.exists() else None,
    "server_log": [{**{k: v for k, v in d.items() if k != "ts"}, "t": round(d["ts"] - t0, 2)} for d in ev],
    "calls": [{"name": n, "query": q, "is_error": results.get(i)} for i, n, q in calls],
    "result": {k: final.get(k) for k in ("subtype", "num_turns", "duration_ms", "total_cost_usd")},
}, indent=1))
if "--answer" in sys.argv:
    print("ANSWER:", final.get("result"))
