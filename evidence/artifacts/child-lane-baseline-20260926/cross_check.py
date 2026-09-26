#!/usr/bin/env python3
"""Independent re-derivation of the baseline's headline counts, by a different code path than
child-usage.mjs --lanes-sweep and skill_usage.py --lanes. It reads the same native transcripts and
prints aggregates only (no paths, ids or text):

    python3 cross_check.py --claude-root ~/.claude/projects --codex-root ~/.codex/sessions \
        --rtk-db ~/.local/share/rtk/history.db --since 2026-09-25T17:18:00Z --until 2026-09-26T15:05:00Z

Claude side: a row counts when its timestamp is inside [since, until); tool_use blocks are
deduplicated by id; the marker is looked for in the first user row only. Codex side: sessions are
split by the marker substring in any developer message (the critic's method), not by the skill
catalog the report uses, so agreement of the two splits is itself a check.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sqlite3
from datetime import datetime

MARKER = "<context_window_protection>"


def ts(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def claude(root: str, since: float, until: float, db_path: str | None) -> dict:
    decisions = {}
    if db_path:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        decisions = dict(con.execute("SELECT tool_use_id, decision FROM hook_decisions ORDER BY id"))
        con.close()
    out = collections.Counter()
    skills, servers, joined = collections.Counter(), collections.Counter(), collections.Counter()
    marker_by_spawn = collections.Counter()
    for path in sorted(set(glob.glob(os.path.join(root, "**", "subagents", "**", "agent-*.jsonl"), recursive=True))):
        spawn = "workflow" if "/subagents/workflows/wf_" in path else "agent_tool"
        rows = []
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        times = [t for t in (ts(r.get("timestamp")) for r in rows if isinstance(r, dict)) if t is not None]
        if not any(since <= t < until for t in times):
            continue
        out["children"] += 1
        out["children_" + spawn] += 1
        first_user = next((r for r in rows if isinstance(r, dict) and r.get("type") == "user"), None)
        content = (first_user or {}).get("message", {}).get("content")
        if MARKER in (content if isinstance(content, str) else json.dumps(content)):
            marker_by_spawn[spawn] += 1
        seen = set()
        for row in rows:
            t = ts(row.get("timestamp")) if isinstance(row, dict) else None
            if t is None or not since <= t < until or row.get("type") != "assistant":
                continue
            for block in (row.get("message") or {}).get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("id") in seen:
                    continue
                seen.add(block.get("id"))
                name = str(block.get("name"))
                if name == "Bash":
                    out["bash_calls"] += 1
                    joined[decisions.get(block.get("id"), "not_logged")] += 1
                elif name == "Skill":
                    skills[str((block.get("input") or {}).get("skill"))] += 1
                elif name.startswith("mcp__"):
                    servers[name.split("__")[1]] += 1
    return {**dict(out), "first_prompt_marker_by_spawn": dict(marker_by_spawn),
            "skill_calls": sum(skills.values()), "mcp_calls_by_server": dict(sorted(servers.items())),
            "rtk_decisions": dict(sorted(joined.items())) if db_path else None}


def codex(root: str, since: float, until: float) -> dict:
    split = {True: collections.Counter(), False: collections.Counter()}
    servers = {True: collections.Counter(), False: collections.Counter()}
    for path in glob.glob(os.path.join(root, "**", "rollout-*.jsonl"), recursive=True):
        injected, inside, counts, mcp = False, False, collections.Counter(), collections.Counter()
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                t = ts(record.get("timestamp"))
                if t is None or t >= until:
                    continue
                payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                if (record.get("type") == "response_item" and payload.get("type") == "message"
                        and payload.get("role") == "developer" and MARKER in json.dumps(payload.get("content"))):
                    injected = True
                inside |= t >= since
                if t < since or record.get("type") != "event_msg" or payload.get("type") != "item_completed":
                    continue
                item = payload.get("item") or {}
                if item.get("type") == "McpToolCall":
                    mcp[str(item.get("server"))] += 1
                elif item.get("type") == "CommandExecution":
                    counts["shell_calls"] += 1
                    command = item.get("command") or []
                    script = command[2] if len(command) > 2 else " ".join(map(str, command))
                    counts["rtk_prefixed"] += bool(re.match(r"\s*rtk\s", script))
                elif item.get("type") == "Extension" and (item.get("action") or {}).get("type") == "openPage":
                    counts["web_open_page"] += 1
        if inside:
            split[injected]["sessions"] += 1
            split[injected].update(counts)
            servers[injected].update(mcp)
    return {label: {**dict(split[key]), "mcp_calls_by_server": dict(sorted(servers[key].items()))}
            for label, key in (("marker_sessions", True), ("no_marker_sessions", False))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--claude-root", required=True)
    parser.add_argument("--codex-root", required=True)
    parser.add_argument("--rtk-db")
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    args = parser.parse_args()
    since, until = ts(args.since), ts(args.until)
    print(json.dumps({"claude": claude(args.claude_root, since, until, args.rtk_db),
                      "codex": codex(args.codex_root, since, until)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
