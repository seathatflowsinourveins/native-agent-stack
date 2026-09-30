"""Count-only scan of tool results over 5,120 UTF-8 bytes (item 4): per tool class, the content shape, whether the text is JSON as is,
after removing a cat -n line-number prefix (Read), or after removing the context-mode code echo (ctx_execute, ctx_execute_file).
Prints counts only."""
import json
import os
import re
import sys
from collections import Counter, defaultdict

LIMIT = 5120
CAT_N = re.compile(r"^ *\d+\t")  # applied per line, anchored, one bounded class: linear


def klass(name):
    if not isinstance(name, str):
        return "(orphan)"
    if name.startswith("mcp__") and "__ctx_" in name:
        return "ctx:" + name.rsplit("__", 1)[1]
    if name.startswith("mcp__"):
        return "other_mcp"
    return name if name in ("Bash", "Read", "WebFetch", "WebSearch", "Grep", "Glob", "Agent", "Task", "Skill", "ToolSearch") else "other"


def echo(inp, with_path):
    lang = inp.get("language") if isinstance(inp.get("language"), str) else ""
    code = inp.get("code") if isinstance(inp.get("code"), str) else ""
    clip = code if len(code) <= 2000 else code[:2000] + "\n… (truncated)"
    header = ("path=" + inp["path"] + "\n") if with_path and isinstance(inp.get("path"), str) and inp.get("path") else ""
    return header + "```" + lang + "\n" + clip + "\n```\n\n"


def is_json(t):
    s = t.strip()
    if not s or s[0] not in "[{":
        return False
    try:
        json.loads(s)
        return True
    except ValueError:
        return False


c = defaultdict(Counter)
for root in sys.argv[1:]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl"):
                continue
            calls = {}
            try:
                fh = open(os.path.join(dirpath, name), "rb")
            except OSError:
                continue
            with fh:
                for raw in fh:
                    if b'"tool_use"' not in raw and b'"tool_result"' not in raw:
                        continue
                    try:
                        row = json.loads(raw)
                    except ValueError:
                        continue
                    msg = row.get("message") if isinstance(row, dict) else None
                    blocks = msg.get("content") if isinstance(msg, dict) and isinstance(msg.get("content"), list) else []
                    for b in blocks:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "tool_use" and isinstance(b.get("id"), str):
                            calls.setdefault(b["id"], (b.get("name"), b.get("input") if isinstance(b.get("input"), dict) else {}))
                        elif b.get("type") == "tool_result":
                            name_, inp = calls.get(b.get("tool_use_id"), (None, {}))
                            k = klass(name_)
                            ct = b.get("content")
                            if isinstance(ct, str):
                                text, shape = ct, "string"
                            elif isinstance(ct, list):
                                if all(isinstance(x, dict) and x.get("type") == "text" and isinstance(x.get("text"), str) for x in ct):
                                    text, shape = "".join(x["text"] for x in ct), "text_blocks%s" % ("1" if len(ct) == 1 else "n")
                                else:
                                    text, shape = None, "has_non_text_block"
                            else:
                                text, shape = None, type(ct).__name__
                            if text is None:
                                n = len(json.dumps(ct).encode()) if ct is not None else 0
                            else:
                                n = len(text.encode("utf-8", "surrogatepass"))
                            if n <= LIMIT:
                                continue
                            c["large_by_class_shape"][k + " " + shape] += 1
                            if text is None:
                                continue
                            direct = is_json(text)
                            c["json_as_is"][k + " " + str(direct)] += 1
                            if k == "Read":
                                lines = text.split("\n")
                                numbered = sum(1 for l in lines if CAT_N.match(l))
                                allnum = numbered == len([l for l in lines if l != ""]) and numbered > 0
                                c["read_line_numbered"]["all_lines" if allnum else "some" if numbered else "none"] += 1
                                if numbered:
                                    stripped = "\n".join(CAT_N.sub("", l, count=1) for l in lines)
                                    c["read_json_after_cat_n_strip"][str(is_json(stripped))] += 1
                            if k in ("ctx:ctx_execute", "ctx:ctx_execute_file"):
                                e = echo(inp, k.endswith("_file"))
                                starts = text.startswith(e)
                                c["ctx_echo_prefix"][k + " " + str(starts)] += 1
                                if starts:
                                    c["ctx_json_after_echo"][k + " " + str(is_json(text[len(e):]))] += 1
print(json.dumps({k: dict(v) for k, v in c.items()}, indent=1, sort_keys=True))
