#!/usr/bin/env python3
"""Apply the frozen pass rule of the local model server gate to one `codex exec --json` event log.

usage: gate_score.py EVENTS_JSONL CODEX_EXIT_CODE

A run passes when (1) the event log holds a completed `mcp_tool_call` item for server `time`, tool
`get_current_time`, with status `completed`, no error and a result that carries a `datetime` string,
and (2) the last `agent_message` of the run contains that `datetime` string as a substring.
The exit code is recorded and used only to name a timeout; it is not part of the pass rule.
Local scoring script, not an upstream component.
"""
import collections
import json
import re
import sys

SERVER, TOOL = "time", "get_current_time"


def extract_datetime(result):
    if not isinstance(result, dict):
        return None
    structured = result.get("structured_content")
    if isinstance(structured, dict) and isinstance(structured.get("datetime"), str):
        return structured["datetime"]
    for block in result.get("content") or []:
        text = block.get("text") if isinstance(block, dict) else None
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and isinstance(parsed.get("datetime"), str):
                return parsed["datetime"]
        except ValueError:
            pass
        match = re.search(r'"datetime"\s*:\s*"([^"]+)"', text)
        if match:
            return match.group(1)
    return None


def main(path, exit_code):
    items, error_events, turn_status, non_json = [], [], None, 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                non_json += 1
                continue
            kind = event.get("type")
            if kind == "item.completed" and isinstance(event.get("item"), dict):
                items.append(event["item"])
            if kind in ("error", "turn.failed"):
                message = event.get("message") or (event.get("error") or {}).get("message")
                error_events.append(str(message or json.dumps(event))[:400])
            if kind in ("turn.completed", "turn.failed"):
                turn_status = kind
    calls = [item for item in items if item.get("type") == "mcp_tool_call"]
    target = [c for c in calls if c.get("server") == SERVER and c.get("tool") == TOOL]
    call_rows, datetimes = [], []
    for call in calls:
        value = None
        if call in target and call.get("status") == "completed" and not call.get("error") and call.get("result"):
            value = extract_datetime(call["result"])
            if value:
                datetimes.append(value)
        call_rows.append({
            "server": call.get("server"), "tool": call.get("tool"), "status": call.get("status"),
            "arguments": call.get("arguments"),
            "error": (call.get("error") or {}).get("message") if isinstance(call.get("error"), dict) else call.get("error"),
            "result_datetime": value,
        })
    messages = [item.get("text") or "" for item in items if item.get("type") == "agent_message"]
    final = messages[-1] if messages else None
    completed = bool(datetimes)
    contains = bool(final) and any(value in final for value in datetimes)
    run_pass = completed and contains
    if run_pass:
        reason = "pass"
    elif exit_code in (124, 137):
        reason = "timeout"
    elif not calls and error_events:
        reason = "codex_or_server_error"
    elif not calls:
        reason = "tool_not_called"
    elif not completed:
        errors = " ".join(str(row["error"] or "") for row in call_rows).lower()
        reason = "approval_denied" if "approval" in errors else "tool_call_failed"
    elif final is None:
        reason = "no_final_answer"
    else:
        reason = "answer_mismatch"
    json.dump({
        "codex_exit_code": exit_code,
        "turn_status": turn_status,
        "completed_item_types": dict(collections.Counter(item.get("type") for item in items)),
        "non_json_lines": non_json,
        "mcp_tool_calls": call_rows,
        "tool_call_completed": completed,
        "tool_result_datetimes": datetimes,
        "final_answer": final,
        "final_answer_contains_result": contains,
        "run_pass": run_pass,
        "reason": reason,
        "error_events": error_events,
    }, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
