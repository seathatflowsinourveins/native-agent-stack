"""Write a subagent transcript's last assistant text to OUT, with the worktree prefix replaced by <worktree>.

usage: final_text.py TRANSCRIPT WORKTREE OUT
"""
import json
import sys
from pathlib import Path

last = None
for line in Path(sys.argv[1]).read_text().splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("type") == "assistant":
        texts = [b.get("text", "") for b in e["message"].get("content") or []
                 if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()]
        if texts:
            last = "\n".join(texts)
text = last.replace(sys.argv[2], "<worktree>")
Path(sys.argv[3]).write_text(text.rstrip() + "\n")
print(len(text), "characters; first line:", text.splitlines()[0])
