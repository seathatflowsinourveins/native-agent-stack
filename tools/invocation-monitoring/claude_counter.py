#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read-only native Claude counters; stdout contains metadata and counts only.

Integration reference: examples/claude-native/workflows/child-usage.mjs at
425a3784fa50c2f1fe6b4dadaf4333908ee7eb4f, lines 2854-2878, 3197-3261.
No transcript text, shell commands, cwd, input values, or credentials are emitted.
Optional output is an exclusively created 0600 file in a private 0700 directory.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen


SOURCE_PIN = "425a3784fa50c2f1fe6b4dadaf4333908ee7eb4f"
DEFAULT_WINDOWS = [
    ("before_90m", "2026-10-06T13:55:00Z", "2026-10-06T15:25:00Z"),
    ("before_246m", "2026-10-06T13:55:00Z", "2026-10-06T18:01:00Z"),
]
COHORTS = ("provisional_prompt_filtered", "tool_named_prompt", "first_post_relaunch_turn", "unresolved")
NAME = re.compile(r"^[A-Za-z0-9_.:@/+\-]{1,120}$")
TOOL_PROMPT = re.compile(
    r"\b(?:Skill|Agent|Workflow|Bash|ToolSearch|WebSearch|WebFetch)\b"
    r"|\bmcp__[\w-]+__[\w-]+\b"
    r"|\b(?i:serena|jcodemunch|socraticode|semble|qmd|headroom|RTK)\b"
    r"|\b(?i:ai-memory|context-mode|codebase-memory|promptfoo|skill-creator|"
    r"ctx_execute|ctx_batch_execute|ctx_search|memory_query|search_graph)\b",
)
MARKERS = {
    "context_mode": ("context_guidance", "context-mode", "ctx_execute"),
    "token_lanes": ("token-lanes", "token lanes", "Token lanes"),
    "codebase_memory": ("codebase-memory",),
    "serena": ("serena",),
}
COOP_REFERENCE = re.compile(r"/home/[^\s/'\"`<>]+/\.local/state/native-agent-stack/coordination/ns2604-coop/[^\s'\"`<>]+\.(?:md|txt|json)")


def task_text(text):
    # Client-injected standing guidance does not establish a task-specific name.
    return re.sub(r"<(INSTRUCTIONS|system-reminder|skills_instructions|context_guidance|hcom_system_context)\b[^>]*>.*?</\1>", "", text, flags=re.S | re.I)


def names_this_call(text, call):
    tool = call["tool"]
    aliases = [(tool, tool.startswith("mcp__"))]
    for field in ("skill", "subagent_type", "script_name"):
        if call.get(field) and not call[field].startswith("("):
            aliases.append((call[field], True))
    if call.get("mcp_server"):
        server = call["mcp_server"]
        aliases.append((server, True))
        if "_" in call.get("mcp_tool", ""):
            aliases.append((call["mcp_tool"], True))
        for component in ("context-mode", "ai-memory", "codebase-memory", "serena", "jcodemunch", "socraticode", "semble", "qmd", "headroom", "agentsview"):
            if component in server:
                aliases.append((component, True))
    if tool == "Bash" and call.get("rtk_first") is True:
        aliases.append(("rtk", True))
    return any(alias and re.search(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", text, flags=re.I if insensitive else 0) for alias, insensitive in aliases)


def stamp(value):
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if date.tzinfo is None:
            return None
        return date.timestamp()
    except (ValueError, TypeError):
        return None


def label(value, missing="(missing)"):
    return value if isinstance(value, str) and NAME.fullmatch(value) else missing


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text", ""), str)
        )
    return ""


def blocks_of(row):
    content = row.get("message", {}).get("content", [])
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def native_files(roots):
    """Use native layout; never infer identity from cwd or follow symlinks."""
    found = set()
    for root in roots:
        for directory, directories, files in os.walk(root, followlinks=False):
            directories[:] = sorted(
                d for d in directories if not (Path(directory) / d).is_symlink()
            )
            for name in sorted(files):
                path = Path(directory) / name
                if not name.endswith(".jsonl") or path.is_symlink():
                    continue
                parts = path.parts
                if "subagents" in parts:
                    if not re.fullmatch(r"agent-[\w-]+\.jsonl", name):
                        continue
                    position = parts.index("subagents")
                    ancestor = parts[position - 1]
                    scope = "workflow" if "workflows" in parts[position + 1 :] else "agent_tool"
                    run = next((p for p in parts if p.startswith("wf_")), None)
                else:
                    if not re.fullmatch(r"[0-9a-f-]{36}\.jsonl", name):
                        continue
                    ancestor, scope, run = path.stem, "main", None
                resolved = str(path.resolve())
                if resolved not in found:
                    found.add(resolved)
                    yield path, ancestor, scope, run


def scan(roots, end):
    calls, results, messages, prompts, hooks = {}, {}, {}, {}, {}
    identities, actors, links = {}, {}, {}
    integrity = Counter()
    snapshots = []
    for path, ancestor, scope, run in native_files(roots):
        integrity["files_read"] += 1
        integrity[f"files_{scope}"] += 1
        digest = hashlib.sha256()
        actor_fallback = "main" if scope == "main" else path.stem.removeprefix("agent-")
        parent_call = None
        agent_type = "main" if scope == "main" else "(missing)"
        meta = path.with_suffix(".meta.json")
        if scope != "main" and meta.exists() and not meta.is_symlink():
            try:
                native_meta = json.loads(meta.read_text())
                parent_call = native_meta.get("toolUseId")
                agent_type = label(native_meta.get("agentType"))
            except (OSError, ValueError):
                integrity["meta_parse_errors"] += 1
        state, prompt_id = "unresolved", None
        local_seen = set()
        try:
            handle = path.open("rb")
        except OSError:
            integrity["unreadable_files"] += 1
            continue
        with handle:
            for raw in handle:
                digest.update(raw)
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    integrity["jsonl_parse_errors"] += 1
                    continue
                if not isinstance(row, dict):
                    integrity["non_object_rows"] += 1
                    continue
                native_session = row.get("sessionId", row.get("session_id"))
                session = label(native_session, ancestor)
                if native_session and native_session != ancestor:
                    integrity["native_session_ancestry_mismatches"] += 1
                if row.get("type") == "agent-name":
                    identities[session] = label(row.get("agentName"), "(unnamed)")
                elif row.get("type") == "custom-title" and session not in identities:
                    identities[session] = label(row.get("customTitle"), "(unnamed)")
                time = stamp(row.get("timestamp"))
                if time is None or time >= end:
                    continue
                actor = label(row.get("agentId"), actor_fallback)
                actor_key = (session, actor)
                actors[actor_key] = {
                    "session_id": session,
                    "actor_id": actor,
                    "scope": scope,
                    "agent_type": agent_type,
                    "workflow_run_id": label(run) if run else None,
                }
                if parent_call:
                    links[actor_key] = (session, str(parent_call))
                content = blocks_of(row)
                row_type = row.get("type")
                message = row.get("message", {})
                if row_type == "user" and not any(b.get("type") == "tool_result" for b in content):
                    origin = row.get("origin", {})
                    origin = origin if isinstance(origin, dict) else {}
                    human = (
                        row.get("turnOrigin") == "human"
                        or origin.get("kind") == "human"
                        or row.get("promptSource") in ("typed", "queued", "suggestion_accepted")
                    )
                    child_task = scope != "main" and prompt_id is None
                    if not row.get("isMeta") and (human or child_task):
                        prompt_id = row.get("promptId") or row.get("uuid")
                        state = "tool_named_prompt" if TOOL_PROMPT.search(text_of(message.get("content"))) else "provisional_prompt_filtered"
                        prompt_key = (session, actor, prompt_id or f"time:{time}")
                        prompt_text = task_text(text_of(message.get("content")))
                        prompts.setdefault(prompt_key, {"at": time, "session": session, "scope": scope, "cohort": state, "text": prompt_text, "references": set(COOP_REFERENCE.findall(prompt_text)), "reconstructed": {}})
                if row_type == "assistant":
                    mid = message.get("id")
                    if mid:
                        key = (session, mid)
                        if key in messages:
                            integrity["repeated_assistant_message_rows"] += 1
                        messages.setdefault(key, {"at": time, "session": session, "scope": scope})
                    else:
                        integrity["assistant_rows_without_native_message_id"] += 1
                    for block in content:
                        if block.get("type") != "tool_use":
                            continue
                        tid = block.get("id")
                        if not isinstance(tid, str):
                            integrity["tool_uses_without_native_id"] += 1
                            continue
                        key = (session, tid)
                        if key in calls:
                            integrity["repeated_tool_use_blocks"] += 1
                            continue
                        name = label(block.get("name"))
                        data = block.get("input", {})
                        data = data if isinstance(data, dict) else {}
                        details = {}
                        if name == "Skill":
                            details["skill"] = label(data.get("skill"))
                        elif name == "Agent":
                            details["subagent_type"] = label(data.get("subagent_type"))
                        elif name == "Workflow":
                            details["script_name"] = label(Path(data["scriptPath"]).name) if isinstance(data.get("scriptPath"), str) else "(inline_or_missing)"
                        elif name == "Bash":
                            command = data.get("command")
                            details["rtk_first"] = bool(re.match(r"^\s*rtk(?:\s|$)", command)) if isinstance(command, str) else None
                        elif name.startswith("mcp__"):
                            fields = name.split("__", 2)
                            if len(fields) == 3:
                                details.update(mcp_server=label(fields[1]), mcp_tool=label(fields[2]))
                        pkey = (session, actor, prompt_id or f"time:{time}") if prompt_id else None
                        prompt = prompts.get(pkey, {})
                        read_reference = data.get("file_path") if name == "Read" else None
                        calls[key] = {"at": time, "session": session, "actor": actor, "scope": scope, "agent_type": agent_type, "tool": name, "prompt_key": pkey, "read_coop_reference": read_reference if read_reference in prompt.get("references", set()) else None, "prompt_cohort": state, **details}
                if row_type == "user":
                    for block in content:
                        if block.get("type") != "tool_result":
                            continue
                        tid = block.get("tool_use_id")
                        if not isinstance(tid, str):
                            integrity["tool_results_without_native_id"] += 1
                            continue
                        key = (session, tid)
                        if key in results:
                            integrity["repeated_tool_result_blocks"] += 1
                            continue
                        results[key] = {"at": time, "session": session, "actor": actor, "scope": scope, "is_error": block.get("is_error")}
                        request = calls.get(key, {})
                        referenced = request.get("read_coop_reference")
                        if referenced and block.get("is_error") is not True:
                            prompt = prompts.get(request.get("prompt_key"))
                            if prompt:
                                prompt["reconstructed"][referenced] = task_text(text_of(block.get("content")))
                attachment = row.get("attachment", {})
                if isinstance(attachment, dict) and attachment.get("type") == "hook_additional_context":
                    hid = row.get("uuid")
                    if not hid:
                        integrity["hook_rows_without_native_uuid"] += 1
                        continue
                    key = (session, actor, hid)
                    if key in hooks:
                        integrity["repeated_hook_context_rows"] += 1
                    value = text_of(attachment.get("content"))
                    if not value and isinstance(attachment.get("content"), list):
                        value = "\n".join(v for v in attachment["content"] if isinstance(v, str))
                    hooks.setdefault(key, {"at": time, "session": session, "scope": scope, "event": label(attachment.get("hookEvent")), "markers": [k for k, needles in MARKERS.items() if any(n in value for n in needles)]})
                if row_type == "system" and row.get("hookAdditionalContext"):
                    # Summary fields are a separate counter, never added to insertion rows.
                    sid = row.get("uuid")
                    if sid and sid not in local_seen:
                        local_seen.add(sid)
                        hooks.setdefault((session, actor, "summary:" + sid), {"at": time, "session": session, "scope": scope, "event": "summary_field", "markers": []})
        snapshots.append({"session_id_from_layout": ancestor, "actor_id_from_layout": actor_fallback, "scope": scope, "sha256": digest.hexdigest()})
    # Evaluate each call against only names of that tool. Native Agent ancestry
    # inherits the parent's prompt documents, rather than its boolean verdict.
    for call in calls.values():
        documents, missing = [], False
        current, seen = call, set()
        for _ in range(16):
            prompt = prompts.get(current.get("prompt_key"))
            if prompt:
                documents.append(prompt["text"])
                documents.extend(prompt["reconstructed"].values())
                missing |= bool(prompt["references"] - prompt["reconstructed"].keys())
            elif current is call:
                missing = True
            parent_key = links.get((current["session"], current["actor"]))
            if not parent_key or parent_key in seen or parent_key not in calls:
                break
            seen.add(parent_key)
            current = calls[parent_key]
        call["prompt_cohort"] = "tool_named_prompt" if any(names_this_call(t, call) for t in documents) else "unresolved" if missing else "provisional_prompt_filtered"
        call["referenced_coop_block_gap"] = missing
    integrity["prompt_references_unreconstructed"] = sum(len(p["references"] - p["reconstructed"].keys()) for p in prompts.values())
    integrity["calls_with_prompt_or_referenced_block_gap"] = sum(c["referenced_coop_block_gap"] for c in calls.values())
    return calls, results, messages, prompts, hooks, identities, actors, integrity, snapshots


def add_call(target, call, outcome=None):
    target["calls"] += 1
    target["tools"][call["tool"]] += 1
    for key in ("agent_type", "skill", "subagent_type", "script_name", "mcp_server", "mcp_tool"):
        if key in call:
            name = f'{call.get("mcp_server", "")}::{call[key]}' if key == "mcp_tool" else call[key]
            target[key][name] += 1
    if call["tool"] == "Bash":
        target["bash_rtk_first"][str(call.get("rtk_first")).lower()] += 1
    if outcome:
        target["outcomes"][outcome] += 1


def first_turn_policy(calls, path):
    if path is None:
        return {"status": "not_requested"}
    try:
        raw = path.read_bytes()
        native = json.loads(raw)
    except (OSError, ValueError) as error:
        return {"status": "unavailable", "error_type": type(error).__name__}
    boundaries = native.get("lanes", {})
    excluded, matched = 0, set()
    for call in calls.values():
        for lane, row in boundaries.items():
            start, end = stamp(row.get("first_turn_started")), stamp(row.get("first_turn_ended"))
            if call["session"] == row.get("thread") and start is not None and start <= call["at"] and (end is None or call["at"] < end):
                call["prompt_cohort"] = "first_post_relaunch_turn"
                excluded += 1
                matched.add(lane)
                break
    starts = [stamp(row.get("first_turn_started")) for row in boundaries.values()]
    return {"status": "read", "sha256": hashlib.sha256(raw).hexdigest(), "written": native.get("written"), "lanes": len(boundaries), "earliest_start": min((s for s in starts if s is not None), default=None), "matched_native_sessions": len(matched), "excluded_calls": excluded, "qualification": "Applies only where a boundary's native thread equals the Claude native session ID; Codex-only thread IDs do not establish Claude lineage. A missing end is conservatively open-ended"}


def bucket():
    out = {"calls": 0, **{k: Counter() for k in ("tools", "agent_type", "skill", "subagent_type", "script_name", "mcp_server", "mcp_tool", "bash_rtk_first", "outcomes")}}
    out["tools"].update({"Skill": 0, "Agent": 0, "Workflow": 0, "Bash": 0})
    return out


def window_report(data, name, start, end):
    calls, results, messages, prompts, hooks, identities, actors, integrity, snapshots = data
    lo, hi = stamp(start), stamp(end)
    counts = defaultdict(bucket)
    role_counts = defaultdict(bucket)
    inside = lambda item: lo <= item["at"] < hi
    for key, call in calls.items():
        if not inside(call):
            continue
        result = results.get(key)
        outcome = "unobserved_by_window_end"
        if result and result["at"] < hi:
            outcome = "error" if result["is_error"] is True else "non_error" if result["is_error"] is False else "result_without_error_flag"
        for scope in (call["scope"], "all"):
            for cohort in ("raw", call["prompt_cohort"]):
                add_call(counts[(call["session"], scope, cohort)], call, outcome)
        for cohort in ("raw", call["prompt_cohort"]):
            add_call(role_counts[(call["session"], call["agent_type"], cohort)], call, outcome)
    observed_results = Counter()
    for key, result in results.items():
        if not inside(result):
            continue
        call = calls.get(key)
        match = "matched_request_in_window" if call and inside(call) else "matched_request_before_window" if call else "orphan_result"
        observed_results[(result["session"], result["scope"], match)] += 1
    session_ids = sorted(
        {x[0] for x in counts}
        | {x[0] for x in observed_results}
        | {p["session"] for p in hooks.values() if inside(p)}
        | {p["session"] for p in messages.values() if inside(p)}
        | {p["session"] for p in prompts.values() if inside(p)}
    )
    sessions = []
    for session in session_ids:
        scopes = {}
        for scope in ("main", "agent_tool", "workflow", "all"):
            scopes[scope] = {cohort: counts[(session, scope, cohort)] for cohort in ("raw", *COHORTS)}
        sessions.append({
            "session_id": session,
            "session_name": identities.get(session, "(unnamed)"),
            "scopes": scopes,
            "role_agent_types": {agent_type: {cohort: role_counts[(session, agent_type, cohort)] for cohort in ("raw", *COHORTS)} for agent_type in sorted({key[1] for key in role_counts if key[0] == session})},
            "assistant_messages": dict(Counter(m["scope"] for m in messages.values() if m["session"] == session and inside(m))),
            "prompt_episodes_any_tool_name": dict(Counter(p["cohort"] for p in prompts.values() if p["session"] == session and inside(p))),
            "result_cohort": {scope: {match: observed_results[(session, scope, match)] for match in ("matched_request_in_window", "matched_request_before_window", "orphan_result")} for scope in ("main", "agent_tool", "workflow")},
            "hook_context_insertions": dict(Counter(p["event"] for p in hooks.values() if p["session"] == session and inside(p) and p["event"] != "summary_field")),
            "hook_context_insertions_by_scope": {scope: dict(Counter(p["event"] for p in hooks.values() if p["session"] == session and p["scope"] == scope and inside(p) and p["event"] != "summary_field")) for scope in ("main", "agent_tool", "workflow")},
            "hook_context_summary_fields": sum(p["session"] == session and inside(p) and p["event"] == "summary_field" for p in hooks.values()),
            "hook_context_marker_insertions": dict(Counter(k for p in hooks.values() if p["session"] == session and inside(p) for k in p["markers"])),
        })
    return {"name": name, "start_inclusive": start, "end_exclusive": end, "sessions": sessions, "request_totals": {cohort: sum(s["scopes"]["all"][cohort]["calls"] for s in sessions) for cohort in ("raw", *COHORTS)}}


def loki_check(url, windows):
    parsed = urlsplit(url)
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.password:
        raise ValueError("Loki must be a credential-free loopback URL")
    reports = []
    for name, start, end in windows:
        duration = int(stamp(end) - stamp(start))
        query = f'sum by(session_id,actor,tool_name,mcp_server_name,mcp_tool_name)(count_over_time({{service_name="claude-code"}}|event_name="tool_result"[{duration}s]))'
        # LogQL range is (left, right]; shifting by 1 ns implements [start, end).
        right_ns = int(stamp(end)) * 1_000_000_000 - 1
        evaluation_time = f"{right_ns // 1_000_000_000}.{right_ns % 1_000_000_000:09d}"
        endpoint = url.rstrip("/") + "/loki/api/v1/query?" + urlencode({"query": query, "time": evaluation_time})
        try:
            with urlopen(endpoint, timeout=20) as response:
                payload = json.load(response)
            values = payload.get("data", {}).get("result", [])
            groups = [{"labels": {k: label(v) for k, v in v.get("metric", {}).items()}, "rows": float(v["value"][1])} for v in values]
            reports.append({"window": name, "query": query, "evaluation_time": evaluation_time, "status": payload.get("status"), "native_tool_result_rows": groups})
        except Exception as error:
            reports.append({"window": name, "status": "unavailable", "error_type": type(error).__name__})
    return reports


def write_private(path, report):
    parent = path.parent.resolve(strict=True)
    if parent.stat().st_mode & 0o077:
        raise ValueError("Output parent must be private (0700)")
    if any((ancestor / ".git").exists() for ancestor in (parent, *parent.parents)):
        raise ValueError("Private counter output must be outside a checkout")
    descriptor = os.open(parent / path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def self_test():
    """Local synthetic fixtures, explicitly not upstream acceptance or model runs."""
    with tempfile.TemporaryDirectory(prefix="claude-counter-fixture-") as tmp:
        root = Path(tmp)
        from uuid import UUID
        session = str(UUID(int=1))
        def row(kind, at, content, **extra):
            return {"type": kind, "timestamp": at, "sessionId": session, "uuid": f"{kind}-{at}", "message": {"id": "m1" if kind == "assistant" else None, "content": content}, **extra}
        use = lambda tid, name, **data: {"type": "tool_use", "id": tid, "name": name, "input": data}
        rows = [
            row("user", "2026-10-06T13:54:00Z", "Check native-agent-stack results and workflow information", promptSource="typed"),
            row("assistant", "2026-10-06T13:55:00Z", [use("t1", "Bash", command="rtk git status")]),
            row("assistant", "2026-10-06T13:55:01Z", [use("t1", "Bash", command="rtk git status"), use("t2", "Skill", skill="sample")]),
            row("user", "2026-10-06T13:56:00Z", [{"type": "tool_result", "tool_use_id": "t1", "is_error": False, "content": "redacted"}]),
            row("user", "2026-10-06T13:57:00Z", "Use serena and Agent", promptSource="typed"),
            row("assistant", "2026-10-06T13:58:00Z", [use("t3", "Agent", subagent_type="source-scout")]),
            row("assistant", "2026-10-06T15:25:00Z", [use("boundary", "Skill", skill="outside")]),
            row("user", "2026-10-06T15:26:00Z", [{"type": "tool_result", "tool_use_id": "t2", "is_error": True, "content": "redacted"}]),
        ]
        earlier = row("assistant", "2026-10-06T13:54:30Z", [use("earlier", "Bash", command="git status")])
        earlier["message"]["id"] = "m-earlier"
        rows.insert(1, earlier)
        rows.extend([
            row("user", "2026-10-06T14:01:00Z", [{"type": "tool_result", "tool_use_id": "earlier", "is_error": False, "content": "redacted"}]),
            row("user", "2026-10-06T14:02:00Z", [{"type": "tool_result", "tool_use_id": "orphan", "is_error": True, "content": "redacted"}]),
            row("attachment", "2026-10-06T14:03:00Z", [], attachment={"type": "hook_additional_context", "hookEvent": "SessionStart", "content": ["context_guidance ctx_execute"]}),
        ])
        rows.append(rows[-1])
        (root / f"{session}.jsonl").write_text("\n".join(map(json.dumps, rows)))
        sub = root / session / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-child.meta.json").write_text(json.dumps({"toolUseId": "t3"}))
        child_rows = [row("user", "2026-10-06T13:59:00Z", "Check result", agentId="child"), row("assistant", "2026-10-06T14:00:00Z", [use("t4", "mcp__serena__find_symbol")], agentId="child")]
        (sub / "agent-child.jsonl").write_text("\n".join(map(json.dumps, child_rows)))
        data = scan([root], stamp(DEFAULT_WINDOWS[-1][2]))
        report = window_report(data, *DEFAULT_WINDOWS[0])
        session_report = report["sessions"][0]
        scopes = session_report["scopes"]
        assert scopes["main"]["raw"]["calls"] == 3
        assert scopes["main"]["provisional_prompt_filtered"]["calls"] == 2
        assert scopes["main"]["tool_named_prompt"]["calls"] == 1
        assert scopes["agent_tool"]["tool_named_prompt"]["calls"] == 1  # Parent names serena specifically.
        assert scopes["main"]["raw"]["outcomes"]["unobserved_by_window_end"] == 2
        assert scopes["main"]["raw"]["bash_rtk_first"]["true"] == 1
        assert data[7]["repeated_tool_use_blocks"] == 1
        assert session_report["assistant_messages"]["main"] == 1
        assert not TOOL_PROMPT.search("Check native-agent-stack results and workflow information")
        assert TOOL_PROMPT.search("Use Workflow and context-mode")
        assert session_report["result_cohort"]["main"]["matched_request_before_window"] == 1
        assert session_report["result_cohort"]["main"]["orphan_result"] == 1
        assert session_report["hook_context_insertions"]["SessionStart"] == 1
        assert session_report["hook_context_marker_insertions"]["context_mode"] == 1
        assert data[7]["repeated_hook_context_rows"] == 1
        assert not names_this_call("Use rtk", {"tool": "mcp__ai-memory__memory_query", "mcp_server": "ai-memory", "mcp_tool": "memory_query"})
        assert names_this_call("Use ai-memory", {"tool": "mcp__ai-memory__memory_query", "mcp_server": "ai-memory", "mcp_tool": "memory_query"})
        assert not names_this_call(task_text("<INSTRUCTIONS>Use ai-memory</INSTRUCTIONS>Check result"), {"tool": "mcp__ai-memory__memory_query", "mcp_server": "ai-memory", "mcp_tool": "memory_query"})
        print(json.dumps({"kind": "local_synthetic_fixture", "assertions": 18, "status": "passed", "upstream_acceptance": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path)
    parser.add_argument("--window", action="append", nargs=3, metavar=("NAME", "START", "END"))
    parser.add_argument("--live-agents", action="store_true", help="Read claude agents --json for native session names")
    parser.add_argument("--loki-url", help="Optional read-only loopback native result-row cross-check")
    parser.add_argument("--output", type=Path, help="Create a new private JSON file; never overwrite")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--first-turn-boundaries", type=Path, help="Native session-ID-bound whole-first-turn exclusions")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    windows = args.window or DEFAULT_WINDOWS
    for _, start, end in windows:
        if stamp(start) is None or stamp(end) is None or stamp(start) >= stamp(end):
            parser.error("Each window needs timezone-aware START < END")
    data = scan(args.root or [Path.home() / ".claude/projects"], max(stamp(w[2]) for w in windows))
    relaunch = first_turn_policy(data[0], args.first_turn_boundaries)
    live = {"status": "not_requested"}
    if args.live_agents:
        try:
            process = subprocess.run(["rtk", "proxy", "claude", "agents", "--json"], capture_output=True, text=True, timeout=20, check=True)
            native = json.loads(process.stdout)
            native = native if isinstance(native, list) else native.get("agents", native.get("sessions", []))
            mapping = {a["sessionId"]: label(a.get("name"), "(unnamed)") for a in native if isinstance(a, dict) and a.get("sessionId")}
            data[5].update(mapping)
            live = {"status": "read", "session_names": mapping, "exit_code": process.returncode}
        except Exception as error:
            live = {"status": "unavailable", "error_type": type(error).__name__}
    report = {
        "kind": "claude_native_session_counter", "schema_version": 3,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": {"repository": "seathatflowsinourveins/native-agent-stack", "pin": SOURCE_PIN, "integration_reference": "examples/claude-native/workflows/child-usage.mjs:2854,3197"},
        "counter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "overlap_warning": "Windows overlap; their counts must never be added together",
        "contract": {
            "identity": "Native row sessionId/session_id and agentId; native ancestor layout fallback; live claude agents sessionId names; cwd never used",
            "dedup": "Tool use/result: (session_id, native tool_use_id); assistant message: (session_id, native message.id); hook insertion: (session_id, actor_id, native uuid)",
            "requests": "First native request timestamp in [start,end); outcome observed before end, including outside-window earlier result; never count post-end outcome as completed",
            "results": "Separate result timestamp cohort, matched in-window request / pre-window request / orphan",
            "provisional_prompt_filtered": "Per tool: excludes iff observed task/human/queued prompt names this native tool, Skill name, Agent subtype, Workflow script basename, MCP server/tool or distinctive native server alias. Native Agent parents contribute their specific prompt documents. Standing tagged guidance is removed. An explicitly referenced co-op block is reconstructed only from a retained successful native Read result; unavailable blocks make otherwise-organic calls unresolved",
            "bash": "Recorded Bash input begins with rtk after whitespace; lexical prefix only, no claims about hook rewriting or executed descendants",
            "hooks": "Native hook_additional_context attachment UUIDs; system hookAdditionalContext summaries separate",
        },
        "limitations": [
            "Only explicitly selected native roots; other distributions, private config homes and SDK stores remain outside coverage",
            "Per-tool naming is lexical classification, not proof of causality; generated task/user messages other than initial child tasks do not reset human cohort",
            "Referenced co-op blocks read through Bash/context-mode cannot yet be reconstructed reliably; missing blocks stay unresolved. Current mutable block files are never substituted for historical returned content",
            "Workflow parent exclusion cannot be inherited without a native parent toolUseId in actor metadata",
            "Loki emits result rows rather than native tool-use IDs; telemetry counts cannot deduplicate calls or establish organic use",
            "Historical transcript identity names are latest retained labels; live identity read describes observation time",
            "Source files can grow during scan; hashes bind the bytes read, not a locked filesystem snapshot",
            "Tool outcomes without explicit is_error remain a separate class; successful transport is not semantic task success",
        ],
        "live_session_identity": live,
        "first_post_relaunch_turn_policy": relaunch,
        "integrity": dict(data[7]),
        "transcript_snapshots": data[8],
        "windows": [window_report(data, *window) for window in windows],
        "loki_actor_crosscheck": loki_check(args.loki_url, windows) if args.loki_url else {"status": "not_requested"},
    }
    report['organic_acceptance'] = {
        'status': 'not_yet_measured',
        'reason': 'Referenced cooperation blocks, untagged standing guidance and Workflow parent linkage remain incompletely resolved; numeric prompt-filtered bins are provisional.'}
    if args.output:
        write_private(args.output, report)
        print(json.dumps({"status": "written", "sessions": [len(w["sessions"]) for w in report["windows"]], "files_read": report["integrity"].get("files_read", 0)}))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
