"""Count-only scan for PR-A item 6: TaskStop calls. Whether the task a TaskStop result names was started in the same transcript (and by
which source), whether the result is an error, and whether a terminal <task-notification> for that task arrives after the stop. Prints
key names, tool names, enum values and counts only: no ids, paths or text."""
import json
import os
import sys
from collections import Counter

TERMINAL = {"completed", "failed", "killed", "stopped"}


def blocks(text):
    out, at = [], 0
    while True:
        i = text.find("<task-notification>", at)
        if i < 0:
            return out
        j = text.find("</task-notification>", i)
        block = text[i:j if j >= 0 else len(text)]

        def tag(name):
            a = block.find("<" + name + ">")
            b = block.find("</" + name + ">", a + 1) if a >= 0 else -1
            return block[a + len(name) + 2:b].strip() if a >= 0 and b >= 0 else None
        out.append((tag("task-id"), tag("status")))
        at = (j + 1) if j >= 0 else len(text)


c = Counter()
input_keys, result_keys, task_types = Counter(), Counter(), Counter()
for root in sys.argv[1:]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl") or name == "journal.jsonl":
                continue
            try:
                with open(os.path.join(dirpath, name), "rb") as fh:
                    rows = []
                    for raw in fh:
                        try:
                            r = json.loads(raw)
                        except ValueError:
                            continue
                        if isinstance(r, dict):
                            rows.append(r)
            except OSError:
                continue
            names, source, stops, notes = {}, {}, [], []
            for idx, r in enumerate(rows):
                m = r.get("message") if isinstance(r.get("message"), dict) else {}
                content = m.get("content")
                if r.get("type") == "assistant" and isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            names[b.get("id")] = (b.get("name"), b.get("input") if isinstance(b.get("input"), dict) else {})
                            if b.get("name") == "TaskStop":
                                for k in (b.get("input") or {}):
                                    input_keys[k] += 1
                texts = []
                if r.get("type") == "user":
                    tool, err = None, None
                    if isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "tool_result":
                                tool, err = names.get(b.get("tool_use_id"), (None, {}))[0], b.get("is_error")
                            elif isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                                texts.append(b["text"])
                    elif isinstance(content, str):
                        texts.append(content)
                    tur = r.get("toolUseResult")
                    if isinstance(tur, dict):
                        if isinstance(tur.get("backgroundTaskId"), str):
                            source[tur["backgroundTaskId"]] = "Bash"
                        elif tool in ("Monitor", "Workflow") and isinstance(tur.get("taskId"), str):
                            source[tur["taskId"]] = tool
                        elif tool in ("Agent", "Task") and tur.get("isAsync") is True and isinstance(tur.get("agentId"), str):
                            source[tur["agentId"]] = "Agent"
                    if tool == "TaskStop":
                        c["taskstop_results"] += 1
                        c["taskstop_is_error:" + str(bool(err))] += 1
                        if isinstance(tur, dict):
                            for k in tur:
                                result_keys[k] += 1
                            task_types[str(tur.get("task_type"))] += 1
                            tid = tur.get("task_id")
                            stops.append((idx, tid, bool(err)))
                        else:
                            c["taskstop_result_not_object"] += 1
                elif r.get("type") == "attachment" and isinstance(r.get("attachment"), dict) and r["attachment"].get("type") == "queued_command":
                    p = r["attachment"].get("prompt")
                    texts.append(p if isinstance(p, str) else json.dumps(p) if p is not None else "")
                for tx in texts:
                    for tid, status in blocks(tx):
                        notes.append((idx, tid, status))
            for idx, tid, err in stops:
                src = source.get(tid, "(not started in this transcript)")
                c["stop_of:" + src + (":error" if err else ":ok")] += 1
                later = [s for i2, t2, s in notes if t2 == tid and i2 > idx]
                terminal_after = any(s in TERMINAL for s in later)
                c["stop_of:" + src + (":error" if err else ":ok") + ":terminal_notification_after=" + str(terminal_after)] += 1
                later_status = sorted({str(s) for s in later})
                for s in later_status:
                    c["stop_of:" + src + ":later_status:" + s] += 1
print(json.dumps({"counts": dict(sorted(c.items())), "taskstop_input_keys": dict(input_keys), "taskstop_result_keys": dict(result_keys),
                  "taskstop_task_types": dict(task_types)}, indent=1, sort_keys=True))
