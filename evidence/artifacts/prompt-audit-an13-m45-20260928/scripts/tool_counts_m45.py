"""Tool calls per Claude subagent transcript, counted by tool name, with no input or output copied: the evidence for
which tools each Claude run used. The transcripts' locations and the subagents' ids are arguments and are not
written.

usage: tool_counts_m45.py OUT LABEL=TRANSCRIPT...
"""
import json
import sys
from collections import Counter
from pathlib import Path

out = {}
for arg in sys.argv[2:]:
    label, path = arg.split("=", 1)
    counts = Counter()
    for line in Path(path).read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") != "assistant":
            continue
        for b in e["message"].get("content") or []:
            if isinstance(b, dict) and b.get("type") in ("tool_use", "server_tool_use"):
                counts[b.get("name")] += 1
    out[label] = dict(sorted(counts.items()))
Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out))
