"""When each GPT-6 run before and in adjudication attempt 2 read ~/.codex/RTK.md (review repair, 2026-09-28).

usage: rtk_read_facts.py HOLD OUT.json
For the round-1 probe, the round-1 lane and attempt 2's two judges: the runner's start time, the number of completed
command executions, and the ordinal of each command that names RTK.md. Only `command_execution` items are parsed, and
no command text is written.
"""
import json
import sys
from pathlib import Path

hold, out = Path(sys.argv[1]), Path(sys.argv[2])
runs = {"round-1 probe": "convergence-r3/gpt6/gpt6-probe-r3", "round-1 lane": "convergence-r3/gpt6/lane-a-gpt6",
        "attempt-2 judge, A/B": "j6/x5/runs/gpt6/x5-adj-AB", "attempt-2 judge, B/A": "j6/x5/runs/gpt6/x5-adj-BA"}
facts = {"note": "Command ordinals of the RTK.md read in each GPT-6 run's event log; attempt 2 was dispatched after "
                 "both round-1 runs finished. Only command_execution items were parsed; no command text is kept.",
         "runs": {}}
for label, rel in runs.items():
    d, n, hits = hold / rel, 0, []
    for line in (d / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if '"command_execution"' not in line:
            continue
        event = json.loads(line)
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "command_execution":
            n += 1
            if "RTK.md" in item.get("command", ""):
                hits.append(n)
    facts["runs"][label] = {"started": (d / "started").read_text().strip(), "finished": (d / "finished").read_text().strip(),
                            "commands": n, "rtk_md_read_at_command": hits}
out.write_text(json.dumps(facts, indent=1) + "\n")
print(json.dumps(facts["runs"]))
