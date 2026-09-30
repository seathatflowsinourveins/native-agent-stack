"""Count-only scan for PR-A item 6 (incomplete returns): background task starts and their notifications, and the shape of
each transcript's final assistant row. Prints key names, tool names, enum values and counts only: no ids, paths or text."""
import json
import os
import sys
from collections import Counter, defaultdict

TAG_OPEN, TAG_CLOSE = "<task-id>", "</task-id>"


def task_ids(text):
    """Every <task-id>...</task-id> value inside text that also holds <task-notification>: linear find loop."""
    out = []
    if "<task-notification>" not in text:
        return out
    at = 0
    while True:
        i = text.find(TAG_OPEN, at)
        if i < 0:
            return out
        j = text.find(TAG_CLOSE, i + len(TAG_OPEN))
        if j < 0:
            return out
        out.append(text[i + len(TAG_OPEN):j].strip())
        at = j + len(TAG_CLOSE)


c = Counter()
result_keys = defaultdict(Counter)   # tool -> toolUseResult key (task/background-like keys only)
bg_inputs = Counter()                # tool -> calls with input.run_in_background true
final_kind = Counter()
notif_where = Counter()
status_values = Counter()
for root in sys.argv[1:]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl") or name == "journal.jsonl":
                continue
            path = os.path.join(dirpath, name)
            sub = "/subagents/" in path.replace("\\", "/")
            try:
                fh = open(path, "rb")
            except OSError:
                continue
            c["files_subagent" if sub else "files_main"] += 1
            names, started, notified, last_assistant, rows = {}, set(), set(), None, []
            notified_before_last = set()
            with fh:
                for raw in fh:
                    try:
                        row = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(row, dict):
                        continue
                    rows.append(row)
            for idx, row in enumerate(rows):
                t = row.get("type")
                msg = row.get("message") if isinstance(row.get("message"), dict) else {}
                content = msg.get("content")
                if t == "assistant":
                    last_assistant = idx
                    if isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "tool_use":
                                names[b.get("id")] = b.get("name")
                                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                                if inp.get("run_in_background") is True:
                                    bg_inputs[str(b.get("name"))] += 1
                elif t == "user":
                    tur = row.get("toolUseResult")
                    tool = None
                    if isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "tool_result":
                                tool = names.get(b.get("tool_use_id"), "(orphan)")
                            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                                ids = task_ids(b["text"])
                                if ids:
                                    notif_where["user_text_block"] += 1
                                    notified.update(("n", x) for x in ids)
                    elif isinstance(content, str):
                        ids = task_ids(content)
                        if ids:
                            notif_where["user_string_content"] += 1
                            notified.update(("n", x) for x in ids)
                    if isinstance(tur, dict):
                        for k in tur:
                            kl = k.lower()
                            if "task" in kl or "background" in kl or "shell" in kl or "agentid" in kl or k in ("status", "isAsync", "async"):
                                result_keys[str(tool)][k] += 1
                        if isinstance(tur.get("backgroundTaskId"), str):
                            started.add(("n", tur["backgroundTaskId"]))
                            c["started_backgroundTaskId"] += 1
                        if tool in ("Agent", "Task") and isinstance(tur.get("status"), str):
                            status_values["agent_status:" + tur["status"]] += 1
                elif t == "attachment":
                    a = row.get("attachment") if isinstance(row.get("attachment"), dict) else {}
                    if a.get("type") == "queued_command":
                        c["queued_command_rows"] += 1
                        p = a.get("prompt")
                        text = p if isinstance(p, str) else json.dumps(p) if p is not None else ""
                        ids = task_ids(text)
                        if ids:
                            notif_where["queued_command_prompt"] += 1
                            notified.update(("n", x) for x in ids)
                            if last_assistant is None or True:
                                pass
                    elif isinstance(a.get("type"), str) and "task" in a["type"].lower():
                        c["attachment_type:" + a["type"]] += 1
            # pending at the last assistant row: notifications after it do not count
            if last_assistant is not None:
                seen_started, seen_notified = set(), set()
                for row in rows[: last_assistant + 1]:
                    tur = row.get("toolUseResult") if row.get("type") == "user" else None
                    if isinstance(tur, dict) and isinstance(tur.get("backgroundTaskId"), str):
                        seen_started.add(tur["backgroundTaskId"])
                    texts = []
                    if row.get("type") == "attachment" and isinstance(row.get("attachment"), dict) and row["attachment"].get("type") == "queued_command":
                        p = row["attachment"].get("prompt")
                        texts.append(p if isinstance(p, str) else json.dumps(p) if p is not None else "")
                    if row.get("type") == "user":
                        m = row.get("message") if isinstance(row.get("message"), dict) else {}
                        cc = m.get("content")
                        if isinstance(cc, str):
                            texts.append(cc)
                        elif isinstance(cc, list):
                            texts += [b.get("text") for b in cc if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
                    for tx in texts:
                        seen_notified.update(task_ids(tx))
                pending = seen_started - seen_notified
                if seen_started:
                    c[("sub" if sub else "main") + "_actors_with_background_start"] += 1
                if pending:
                    c[("sub" if sub else "main") + "_actors_with_pending_at_last_assistant"] += 1
                notified_unmatched = seen_notified - seen_started
                if notified_unmatched:
                    c[("sub" if sub else "main") + "_actors_with_notification_of_an_id_not_started_here"] += 1
                last = rows[last_assistant]
                m = last.get("message") if isinstance(last.get("message"), dict) else {}
                blocks = [b for b in (m.get("content") or []) if isinstance(b, dict)] if isinstance(m.get("content"), list) else []
                kinds = {b.get("type") for b in blocks}
                kind = "tool_use" if "tool_use" in kinds else "text" if "text" in kinds else "other:" + ",".join(sorted(str(k) for k in kinds)) if kinds else "empty"
                final_kind[("sub:" if sub else "main:") + kind] += 1
                if not isinstance(m.get("id"), str):
                    c["final_assistant_row_without_message_id"] += 1
                # rows of the final message: do they repeat blocks?
                mid = m.get("id")
                if isinstance(mid, str):
                    same = [r for r in rows if r.get("type") == "assistant" and isinstance(r.get("message"), dict) and r["message"].get("id") == mid]
                    c["final_message_rows_" + ("1" if len(same) == 1 else "2" if len(same) == 2 else "3plus")] += 1
                    blob = [json.dumps(r["message"].get("content"), sort_keys=True) for r in same]
                    if len(set(blob)) < len(blob):
                        c["final_message_rows_with_identical_content"] += 1
                    # each row one block?
                    if all(isinstance(r["message"].get("content"), list) and len(r["message"]["content"]) == 1 for r in same):
                        c["final_message_rows_one_block_each"] += 1
            else:
                c[("sub" if sub else "main") + "_files_without_assistant_row"] += 1
print(json.dumps({"counts": dict(sorted(c.items())), "run_in_background_inputs_by_tool": dict(bg_inputs),
                  "task_like_result_keys_by_tool": {k: dict(v) for k, v in sorted(result_keys.items())},
                  "notification_locations": dict(notif_where), "agent_status_values": dict(status_values),
                  "final_row_kind": dict(sorted(final_kind.items()))}, indent=1, sort_keys=True))
