"""Count-only follow-up to task-stop.py: TaskStop results whose toolUseResult is not an object. Their toolUseResult type, is_error, the
length class and first word class of the result text, and whether the call's input task_id names a task started in the same transcript.
Prints type names, booleans and counts only."""
import json
import os
import sys
from collections import Counter

c = Counter()
for root in sys.argv[1:]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl") or name == "journal.jsonl":
                continue
            try:
                with open(os.path.join(dirpath, name), "rb") as fh:
                    rows = [json.loads(raw) for raw in fh if raw.strip().startswith(b"{")]
            except (OSError, ValueError):
                continue
            calls, started = {}, set()
            for r in rows:
                if not isinstance(r, dict):
                    continue
                m = r.get("message") if isinstance(r.get("message"), dict) else {}
                content = m.get("content")
                if r.get("type") == "assistant" and isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            calls[b.get("id")] = (b.get("name"), b.get("input") if isinstance(b.get("input"), dict) else {})
                if r.get("type") != "user" or not isinstance(content, list):
                    continue
                tur = r.get("toolUseResult")
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                        continue
                    name_, inp = calls.get(b.get("tool_use_id"), (None, {}))
                    if isinstance(tur, dict):
                        for k in ("backgroundTaskId", "taskId", "agentId"):
                            if isinstance(tur.get(k), str):
                                started.add(tur[k])
                    if name_ != "TaskStop" or isinstance(tur, dict):
                        continue
                    text = b.get("content") if isinstance(b.get("content"), str) else json.dumps(b.get("content"))
                    c["type:" + type(tur).__name__ + ":is_error=" + str(bool(b.get("is_error")))] += 1
                    c["input_task_started_here=" + str(inp.get("task_id") in started) + ":is_error=" + str(bool(b.get("is_error")))] += 1
                    c["starts_with_tool_use_error=" + str(text.startswith("<tool_use_error>"))] += 1
                    c["starts_with_Error=" + str(isinstance(tur, str) and tur.startswith("Error"))] += 1
print(json.dumps(dict(sorted(c.items())), indent=1))
