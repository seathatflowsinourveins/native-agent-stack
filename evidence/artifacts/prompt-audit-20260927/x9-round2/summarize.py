"""Compact facts from one `claude -p --output-format stream-json --verbose` transcript, as JSON on stdout.

usage: summarize.py ARM TRANSCRIPT EXIT_CODE DURATION_MS
Facts only, no judgment: the init event's MCP server statuses and plugins, every tool call in order (with the Skill
name, a Bash command, and whether its result was an error), the final result text, turns, cost and usage.
"""
import json
import sys
from pathlib import Path

arm, path, rc, ms = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
init, calls, results, final = {}, [], {}, {}
for line in path.read_text().splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("type") == "system" and e.get("subtype") == "init":
        init = {"version": e.get("claude_code_version"), "model": e.get("model"),
                "permission_mode": e.get("permissionMode"),
                "mcp_servers": {s.get("name"): s.get("status") for s in e.get("mcp_servers", [])},
                "plugins": sorted(p.get("name") if isinstance(p, dict) else str(p) for p in e.get("plugins", []))}
    elif e.get("type") == "assistant":
        for c in e.get("message", {}).get("content", []):
            if c.get("type") == "tool_use":
                i = c.get("input") or {}
                calls.append({"id": c.get("id"), "name": c.get("name"), "skill": i.get("skill"),
                              "command": (i.get("command") or "")[:300], "query": (i.get("query") or "")[:200]})
    elif e.get("type") == "user":
        content = e.get("message", {}).get("content", [])
        for c in content if isinstance(content, list) else []:
            if c.get("type") == "tool_result":
                results[c.get("tool_use_id")] = bool(c.get("is_error"))
    elif e.get("type") == "result":
        final = e
for c in calls:
    c["is_error"] = results.get(c.pop("id"))
print(json.dumps({"arm": arm, "transcript": path.name, "exit": rc, "duration_ms": ms, "init": init, "calls": calls,
                  "result_subtype": final.get("subtype"), "final": final.get("result"),
                  "num_turns": final.get("num_turns"), "cost_usd": final.get("total_cost_usd"),
                  "usage": {k: v for k, v in (final.get("usage") or {}).items() if k.endswith("tokens")}}))
