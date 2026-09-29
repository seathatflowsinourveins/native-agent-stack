"""Save a Claude judge's or lane's return from its subagent transcript: the text of the last assistant message
(without a surrounding code fence, if it has one), parsed as JSON and written unchanged (keys and values) to OUT.

usage: save_return_a.py TRANSCRIPT OUT
Exits 1 when the last assistant text is not one JSON object.
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
    if e.get("type") != "assistant":
        continue
    texts = [c.get("text", "") for c in (e.get("message") or {}).get("content") or []
             if isinstance(c, dict) and c.get("type") == "text"]
    if any(t.strip() for t in texts):
        last = "".join(texts).strip()
if last and last.startswith("```"):  # a fenced JSON block: drop the opening and closing fence lines
    body = last.split("\n", 1)[1] if "\n" in last else ""
    last = body.rsplit("```", 1)[0].strip()
try:
    ret = json.loads(last)
except (TypeError, ValueError):
    print("last assistant text is not JSON")
    sys.exit(1)
if not isinstance(ret, dict):
    print("last assistant text is not a JSON object")
    sys.exit(1)
Path(sys.argv[2]).write_text(json.dumps(ret, ensure_ascii=False, indent=1) + "\n")
print("saved", sys.argv[2], {i["id"]: i.get("choice") for i in ret.get("items") or []}, "leak:", ret.get("leak"))
