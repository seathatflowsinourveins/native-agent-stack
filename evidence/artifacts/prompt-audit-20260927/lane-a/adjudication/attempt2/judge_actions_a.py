"""List what lane A's X5a/X5c judges ran or opened (commands, web searches, tool inputs), never outputs or results.

usage: judge_actions.py J CLAUDE_AB_TRANSCRIPT CLAUDE_BA_TRANSCRIPT [OUT_JSON]
Each path is classed as inside the allowed set (the repository root, the judge's own input, packet and prompt, the
runner's own directory) or outside it. Informational: the void rule is void_patterns.py, not this list.
"""
import json
import re
import sys
from pathlib import Path

J = Path(sys.argv[1])
ALLOWED = (str(J / "root"), str(J / "adjudication-inputs"), str(J / "packets"), str(J / "prompts"), str(J / "runs"),
           str(J / "schemas"))
PATH = re.compile(r"(/[^\s'\"`;|&<>()]+)")


def outside(text):
    return sorted({p for p in PATH.findall(text or "")
                   if p.startswith(("/tmp", "/home", "/Users", "/root", "/etc", "/var", "/mnt", "/opt"))
                   and not p.startswith(ALLOWED)})


out = {}
for order in ("AB", "BA"):
    acts = []
    for line in (J / "runs" / "gpt6" / f"x5-adj-{order}" / "events.jsonl").read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        it = e.get("item") or {}
        if e.get("type") != "item.completed":
            continue
        if it.get("type") == "command_execution":
            acts.append({"command": it.get("command"), "exit": it.get("exit_code"),
                         "outside_paths": outside(it.get("command"))})
        elif it.get("type") == "web_search":
            acts.append({"web_search": it.get("query"), "action": it.get("action")})
    out[f"gpt6-{order}"] = acts
for order, path in (("AB", sys.argv[2]), ("BA", sys.argv[3])):
    acts = []
    for line in Path(path).read_text().splitlines():
        e = json.loads(line)
        for b in (e.get("message") or {}).get("content") or [] if isinstance((e.get("message") or {}).get("content"),
                                                                               list) else []:
            if b.get("type") in ("tool_use", "server_tool_use") and e.get("type") == "assistant":
                inp = b.get("input") or {}
                acts.append({"tool": b.get("name"), "input": {k: inp[k] for k in inp if k != "prompt"},
                             "outside_paths": outside(json.dumps(inp))})
    out[f"claude-{order}"] = acts
if len(sys.argv) > 4:
    Path(sys.argv[4]).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
for k, acts in out.items():
    print(f"== {k}: {len(acts)} actions; outside the allowed set: "
          f"{sorted({p for a in acts for p in a.get('outside_paths', [])})}")
    for a in acts:
        s = json.dumps({x: y for x, y in a.items() if x != "outside_paths"}, ensure_ascii=False)
        print("  ", s.replace(str(J), "<J>")[:260])
