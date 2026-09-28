"""workspace-guard's SessionStart hook, the K5 fixture of the X9 round-3 comparison.

Reads the hook input from stdin (https://code.claude.com/docs/en/hooks.md: a JSON object with session_id and
hook_event_name, and for SessionStart a source such as "startup") and appends one JSON line to
<plugin root>/state/<session_id>.log. It prints nothing and exits 0, so it adds nothing to the model's context
(hooks.md: SessionStart adds plain-text stdout to Claude's context; features-overview.md: hooks cost "Zero, unless
hook returns additional context").
"""
import json
import re
import sys
import time
from pathlib import Path

data = json.load(sys.stdin)
sid = re.sub(r"[^A-Za-z0-9-]", "", str(data.get("session_id") or "unknown"))
state = Path(__file__).resolve().parent.parent / "state"
state.mkdir(exist_ok=True)
with open(state / f"{sid}.log", "a", encoding="utf-8") as f:
    f.write(json.dumps({"ts": round(time.time(), 3), "event": data.get("hook_event_name"),
                        "source": data.get("source")}) + "\n")
