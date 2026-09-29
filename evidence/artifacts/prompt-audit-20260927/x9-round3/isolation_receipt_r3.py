"""Receipt for round 3's pre-dispatch isolation and dispatch: the isolation script (worktrees removed, work moved into
the held directory, root scanned, orders checked), the configuration-text scan of the prompts and the GPT-6 judges'
start, taken from the coordinator session's own log (commands, their outputs and timestamps only). Round 2's
isolation_receipt.py with round 3's steps and window.

usage: isolation_receipt_r3.py SESSION_TRANSCRIPT OUT_JSON
Selects the Bash calls whose command matches one of STEPS between 08:36:40Z and 08:37:45Z on 2026-09-28, and their
tool results. Host paths are replaced as in package_x9_round3.py.
"""
import json
import re
import sys
from pathlib import Path

X3 = Path(__file__).resolve().parent
W3 = X3.parent
HOLD = W3.parent
S = HOLD.parent
STEPS = {"isolation script": r"isolate_r3\.sh",
         "configuration-text scan of the sent prompts": r"CONFIG = re\.compile",
         "GPT-6 judges started": r"codex_call\.sh --work-dir \$J/runs start x9r3-judge-AB"}
SUBS = sorted([(str(S / "j3" / "x9" / "root"), "<root>"), (str(S / "j3" / "x9"), "<judges>"),
               (str(S / "convergence-r3"), "<work>"), (str(HOLD), "<hold>"), (str(S), "<scratch>"),
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
                and "2026-09-28T08:36:40" <= ts <= "2026-09-28T08:37:45":
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
                         "output": clean(results.get(c["id"], ""))[:2500]})
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
for s in out["steps"]:
    print(s["at"], s["step"], "|", s["output"][:160].replace("\n", " / "))
