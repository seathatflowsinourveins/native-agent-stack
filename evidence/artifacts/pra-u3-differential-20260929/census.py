#!/usr/bin/env python3
"""Count-only census of the Codex code-mode forms behind PR-A U3 commits 7 and 8 (research-u3.design.md section 7).

Reads every rollout-*.jsonl under ROOT with the checkout's own tools/skill-usage/skill_usage.py (its TURN_EVENTS,
MODEL_CALL_TYPES, code_mode_fetch_sites and http_script_mentions) and prints only counts: no id, path, host name or text.
Records at or after --until are ignored; a sub-agent's records copied from its parent (ordinal below
subagent_history_start_ordinal) are not its own. It does not reuse measure_codex_records: it recomputes the two nesting rules
side by side, so a delta in the host differential can be traced to its items.

- clients: the first session_meta's cli_version and history_mode, per rollout;
- nesting: each emitted item (a CommandExecution that is not user_shell or unified_exec_interaction, an McpToolCall, a
  web.search Extension) without a model call id, by the span rule before commit 7 (open until the exec's first output,
  the next direct call or task_started/task_complete/turn_aborted) and by the turn rule of commit 7 (an own exec call earlier
  in the same turn); wait calls without a namespace by position; web_search_call records;
- outer code: exec calls, HTTP_SCRIPT mentions, mentions in exec calls with no nested ctx code item attributed, static
  fetch-capable sites (bracket accesses apart), and exec calls with a site and no attributed item;
- notify: exec calls with more than one output record (code-mode notify() adds one per call, description.rs:34).

Usage: python3 -B census.py --repo <checkout> --root <codex sessions> [--until 2026-09-29T00:00:00Z]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

CTX_CODE_TOOLS = ("ctx_execute", "ctx_execute_file", "ctx_batch_execute")
OLD_BOUNDARY = ("task_started", "task_complete", "turn_aborted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--until", default="2026-09-29T00:00:00Z")
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo / "tools" / "skill-usage"))
    import skill_usage as S  # noqa: E402  (the checkout's own module)

    until = S.parse_iso(args.until)
    counts = collections.Counter()
    for path in sorted(args.root.rglob("rollout-*.jsonl")):
        records = []
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
        counts["rollouts"] += 1
        meta = next((r.get("payload") for r in records if r.get("type") == "session_meta"), None)
        meta = meta if isinstance(meta, dict) else {}
        version = meta.get("cli_version")
        counts["client.cli_version=" + (version if isinstance(version, str) and len(version) < 16 else "(other)")] += 1
        counts["client.history_mode=" + str(meta.get("history_mode") == "paginated" and "paginated" or "not_paginated")] += 1
        start = meta.get("subagent_history_start_ordinal")
        child = isinstance(start, int) and not isinstance(start, bool)
        visible = []
        for record in records:
            try:
                at = S.parse_iso(record.get("timestamp"))
            except (ValueError, TypeError, AttributeError):
                continue
            if at >= until or (child and isinstance(record.get("ordinal"), int) and record["ordinal"] < start):
                continue
            visible.append(record)
        model_ids = {(r.get("payload") or {}).get("call_id") or (r.get("payload") or {}).get("id") for r in visible
                     if r.get("type") == "response_item" and (r.get("payload") or {}).get("type") in S.MODEL_CALL_TYPES}
        span, turn_exec, execs, outputs = set(), None, {}, collections.Counter()
        for record in visible:
            payload = record.get("payload") or {}
            if record.get("type") == "response_item":
                kind = payload.get("type")
                key = payload.get("call_id") or payload.get("id")
                if kind == "web_search_call":
                    counts["web_search_call"] += 1
                if kind in ("function_call", "custom_tool_call"):
                    is_exec = kind == "custom_tool_call" and S.codex_call_name(payload).rsplit(".", 1)[-1] == "exec"
                    if is_exec:
                        span.add(key)
                        turn_exec = key
                        code = payload.get("input") if isinstance(payload.get("input"), str) else ""
                        execs.setdefault(key, {"sites": S.code_mode_fetch_sites(code), "http": S.http_script_mentions(code),
                                               "brackets": code_bracket_sites(S, code), "items": 0, "ctx_code": 0})
                    else:
                        if kind == "function_call" and payload.get("name") == S.CODE_MODE_WAIT and not payload.get("namespace"):
                            counts["wait." + ("after_exec_in_turn" if turn_exec is not None else "no_exec_in_turn")] += 1
                        span.clear()
                elif kind == "local_shell_call":
                    span.clear()
                elif kind in ("function_call_output", "custom_tool_call_output"):
                    if kind == "custom_tool_call_output" and key in execs:
                        outputs[key] += 1
                    span.discard(key)
            elif record.get("type") == "event_msg":
                event = payload.get("type")
                if event in OLD_BOUNDARY:
                    span.clear()
                if event in S.TURN_EVENTS:
                    turn_exec = None
                if event != "item_completed":
                    continue
                item = payload.get("item") or {}
                item_type = item.get("type")
                source = item.get("source")
                emitted = (item_type == "McpToolCall" or (item_type == "Extension" and item.get("kind") == "web.search")
                           or (item_type == "CommandExecution"
                               and not (isinstance(source, str) and source in S.SKIPPED_COMMAND_SOURCES)))
                if not emitted:
                    continue
                label = "web.search" if item_type == "Extension" else item_type
                if item.get("id") in model_ids:
                    counts[f"item.{label}.model_call"] += 1
                    continue
                old, new = bool(span), turn_exec is not None
                counts[f"item.{label}.span_rule={'nested' if old else 'direct'}.turn_rule={'nested' if new else 'direct'}"] += 1
                if new:
                    execs[turn_exec]["items"] += 1
                    execs[turn_exec]["ctx_code"] += item_type == "McpToolCall" and item.get("tool") in CTX_CODE_TOOLS
        for key, facts in execs.items():
            counts["exec.calls"] += 1
            counts["exec.sites"] += facts["sites"]
            counts["exec.sites.bracket"] += facts["brackets"]
            counts["exec.with_sites"] += facts["sites"] > 0
            counts["exec.with_sites.no_attributed_item"] += facts["sites"] > 0 and not facts["items"]
            counts["exec.http_mentions"] += facts["http"]
            counts["exec.with_http_mentions"] += facts["http"] > 0
            counts["exec.http_mentions.no_nested_ctx_code_item"] += facts["http"] if not facts["ctx_code"] else 0
            counts["exec.with_http_mentions.no_nested_ctx_code_item"] += facts["http"] > 0 and not facts["ctx_code"]
            counts["exec.more_than_one_output"] += outputs[key] > 1
            counts["exec.extra_outputs"] += max(0, outputs[key] - 1)
    for key in sorted(counts):
        print(f"{key}\t{counts[key]}")
    return 0


def code_bracket_sites(S, code: str) -> int:
    """How many of code_mode_fetch_sites' sites are bracket accesses: the sites minus those left when every '[' after the
    global tools is blanked out (a count-only split; the rule itself is code_mode_fetch_sites)."""
    return S.code_mode_fetch_sites(code) - S.code_mode_fetch_sites(code.replace("[", " "))


if __name__ == "__main__":
    raise SystemExit(main())
