"""Save a blind-adjudicator's final JSON return from its transcript, without printing the transcript.

usage: save_claude_judgment.py TRANSCRIPT OUT_JSON UNIT
Exits 1 unless the last assistant text parses as {"leak", "leak_text", "items"} with one item for UNIT (or no items
when leak is true) and a choice of A, B or neither.
"""
import json
import re
import sys
from pathlib import Path

transcript, out, unit = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
last = None
for line in transcript.read_text().splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("type") == "assistant":
        texts = [b.get("text", "") for b in e["message"].get("content") or []
                 if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()]
        if texts:
            last = "\n".join(texts)
if last is None:
    sys.exit("no assistant text")
m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", last, re.S)
data = json.loads(m.group(1) if m else last)
if data.get("leak"):
    if data.get("items"):
        sys.exit("a leak return must have no items")
else:
    items = data.get("items") or []
    if [i.get("id") for i in items] != [unit] or items[0].get("choice") not in ("A", "B", "neither"):
        sys.exit(f"bad items: {items!r:.300}")
out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
print(json.dumps({"leak": bool(data.get("leak")), "choice": None if data.get("leak") else data["items"][0]["choice"]}))
