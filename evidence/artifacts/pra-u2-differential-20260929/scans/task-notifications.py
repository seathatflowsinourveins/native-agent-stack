"""Count-only scan for PR-A item 6: which tool started each task a <task-notification> names, the notification's tag names and
<status> values, and whether each start source's tasks were still unnotified (or only non-terminally notified) at the final
assistant row. Prints tool names, tag names, status values and counts only: no ids, paths or text."""
import json
import os
import sys
from collections import Counter, defaultdict


def between(text, open_tag, close_tag, at=0):
    i = text.find(open_tag, at)
    if i < 0:
        return None, -1
    j = text.find(close_tag, i + len(open_tag))
    if j < 0:
        return None, -1
    return text[i + len(open_tag):j].strip(), j + len(close_tag)


def notifications(text):
    """[(task_id, status, tag_names)] for each <task-notification>...</task-notification> block: linear find loop."""
    out, at = [], 0
    while True:
        i = text.find("<task-notification>", at)
        if i < 0:
            return out
        j = text.find("</task-notification>", i)
        block = text[i:j if j >= 0 else len(text)]
        tid, _ = between(block, "<task-id>", "</task-id>")
        status, _ = between(block, "<status>", "</status>")
        tags, k = set(), 0
        while True:
            a = block.find("<", k)
            if a < 0:
                break
            b = block.find(">", a)
            if b < 0:
                break
            tag = block[a + 1:b]
            if tag and not tag.startswith("/") and len(tag) < 40 and all(ch.isalnum() or ch in "-_" for ch in tag):
                tags.add(tag)
            k = b + 1
        out.append((tid, status, tags))
        at = (j + 1) if j >= 0 else len(text)


c = Counter()
tag_names, statuses, source_of_notified = Counter(), Counter(), Counter()
status_by_source = defaultdict(Counter)
pending_by_source = Counter()
notif_count_per_task = defaultdict(Counter)
for root in sys.argv[1:]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl") or name == "journal.jsonl":
                continue
            path = os.path.join(dirpath, name)
            sub = "/subagents/" in path.replace("\\", "/")
            try:
                with open(path, "rb") as fh:
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
            names, source, last_assistant = {}, {}, None
            for idx, r in enumerate(rows):
                if r.get("type") == "assistant":
                    last_assistant = idx
            state = {}  # task id -> 'started' | 'notified:<status>'
            notified_any = defaultdict(list)
            for idx, r in enumerate(rows):
                t = r.get("type")
                msg = r.get("message") if isinstance(r.get("message"), dict) else {}
                content = msg.get("content")
                texts = []
                if t == "assistant" and isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            names[b.get("id")] = b.get("name")
                elif t == "user":
                    tool = None
                    if isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "tool_result":
                                tool = names.get(b.get("tool_use_id"))
                            elif isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                                texts.append(("user_text_block", b["text"]))
                    elif isinstance(content, str):
                        texts.append(("user_string", content))
                    tur = r.get("toolUseResult")
                    if isinstance(tur, dict):
                        started = None
                        if isinstance(tur.get("backgroundTaskId"), str):
                            started = ("Bash.backgroundTaskId", tur["backgroundTaskId"])
                        elif tool == "Monitor" and isinstance(tur.get("taskId"), str):
                            started = ("Monitor.taskId", tur["taskId"])
                        elif tool == "Workflow" and isinstance(tur.get("taskId"), str):
                            started = ("Workflow.taskId", tur["taskId"])
                        elif tool in ("Agent", "Task") and tur.get("isAsync") is True and isinstance(tur.get("agentId"), str):
                            started = ("Agent.agentId(isAsync)", tur["agentId"])
                        if started:
                            source[started[1]] = started[0]
                            if last_assistant is not None and idx <= last_assistant:
                                state[started[1]] = "started"
                            c["starts:" + started[0]] += 1
                elif t == "attachment":
                    a = r.get("attachment") if isinstance(r.get("attachment"), dict) else {}
                    if a.get("type") == "queued_command":
                        p = a.get("prompt")
                        texts.append(("queued_command", p if isinstance(p, str) else json.dumps(p) if p is not None else ""))
                for where, text in texts:
                    for tid, status, tags in notifications(text):
                        c["notifications@" + where] += 1
                        for tag in tags:
                            tag_names[tag] += 1
                        statuses[str(status)] += 1
                        src = source.get(tid, "(not started in this transcript)")
                        source_of_notified[src] += 1
                        status_by_source[src][str(status)] += 1
                        notif_count_per_task[src][tid] += 1
                        if last_assistant is not None and idx <= last_assistant and tid in state:
                            state[tid] = "notified:" + str(status)
            for tid, st in state.items():
                pending_by_source[("sub:" if sub else "main:") + source[tid] + ":" + ("never_notified" if st == "started" else st)] += 1
multi = {src: sum(1 for n in per.values() if n > 1) for src, per in notif_count_per_task.items()}
print(json.dumps({"counts": dict(sorted(c.items())), "notification_tag_names": dict(tag_names.most_common(30)),
                  "notification_status_values": dict(statuses), "notified_task_start_source": dict(source_of_notified),
                  "status_by_source": {k: dict(v) for k, v in status_by_source.items()},
                  "tasks_with_more_than_one_notification_by_source": multi,
                  "task_state_at_final_assistant_row": dict(sorted(pending_by_source.items()))}, indent=1, sort_keys=True))
