"""Save a subagent's final JSON return from its transcript, without printing the transcript.

usage: save_claude_return.py TRANSCRIPT OUT_JSON ID...
Exits 1 unless the last assistant text parses as {"items": [...]} with exactly the given ids.
"""
import json
import re
import sys
from pathlib import Path

transcript, out, ids = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
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
got = [i["id"] for i in data["items"]]
if sorted(got) != sorted(ids) or len(got) != len(set(got)):
    sys.exit(f"ids {got} != {ids}")
for i in data["items"]:
    if i["verdict"] not in ("agree", "amend", "reject"):
        sys.exit(f"bad verdict {i['verdict']}")
    if (i["verdict"] == "amend") != bool(i["resolution_text"]):
        sys.exit(f"{i['id']}: resolution_text must be set exactly for amend")
out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
print(json.dumps({i["id"]: [i["verdict"], i["confidence"]] for i in data["items"]}))
