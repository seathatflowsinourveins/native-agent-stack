"""Receipt for attempt 2's pre-dispatch isolation: the coordinator's worktree removal, the moves into the held
directory, the root scan and the dispatch, taken from the coordinator session's own log (commands, their outputs
and timestamps only).

usage: isolation_receipt.py SESSION_TRANSCRIPT OUT_JSON
Selects the Bash calls whose command matches one of STEPS, between 03:00Z and the dispatch at 03:09:15Z on
2026-09-28, and their tool results. Host paths are replaced as in package_x9_attempt2.py.
"""
import json
import re
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
S = WORK.parent
STEPS = {"worktrees removed": r"git worktree remove",
         "moved into the held directory": r"mkdir \$S/\.hold",
         "root scanned": r"hits = \{\"MAPPING\"",
         "GPT-6 judges started": r"codex_call\.sh --work-dir \$J/runs start"}
SUBS = sorted([(str(S / "j2" / "x9" / "root"), "<root>"), (str(S / "j2" / "x9"), "<attempt2>"), (str(S), "<scratch>"),
               (str(S.parent), "<session>")], key=lambda p: -len(p[0]))


def clean(text):
    for old, new in SUBS:
        text = text.replace(old, new)
    text = re.sub(r"/home/[A-Za-z0-9_.-]+", "~", text)
    return re.sub(r"-home-[A-Za-z0-9_]+-[A-Za-z0-9_-]+", "<project-dir>", text)


calls, results = [], {}
for line in Path(sys.argv[1]).read_text().splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    ts = e.get("timestamp") or ""
    content = (e.get("message") or {}).get("content")
    if not isinstance(content, list):
        continue
    for c in content:
        if e.get("type") == "assistant" and c.get("type") == "tool_use" and c.get("name") == "Bash" \
                and "2026-09-28T03:00" <= ts <= "2026-09-28T03:09:16":
            for step, rx in STEPS.items():
                if re.search(rx, c["input"].get("command", "")):
                    calls.append({"step": step, "at": ts, "id": c["id"], "command": c["input"]["command"]})
        elif e.get("type") == "user" and c.get("type") == "tool_result":
            body = c.get("content")
            results[c["tool_use_id"]] = body if isinstance(body, str) else "\n".join(
                b.get("text", "") for b in body or [] if isinstance(b, dict))
out = {"note": __doc__.split("\n\n", 1)[0], "steps": []}
for c in calls:
    out["steps"].append({"step": c["step"], "at": c["at"], "command": clean(c["command"]),
                         "output": clean(results.get(c["id"], ""))[:1500]})
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
for s in out["steps"]:
    print(s["at"], s["step"], "|", s["output"][:200].replace("\n", " / "))
