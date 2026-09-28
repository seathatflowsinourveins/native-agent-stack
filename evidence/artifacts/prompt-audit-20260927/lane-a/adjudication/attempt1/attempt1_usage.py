"""Usage of attempt 1's two GPT-6 runner jobs, read without reading their returns (review repair, 2026-09-28).

usage: attempt1_usage.py JOBS_DIR OUT.json
From each job directory: the runner's exit, model, codex_version, started and finished files, and the `usage` object of
each `turn.completed` event in events.jsonl. No other event, item or message is parsed or written, so the two returns
stay unread (adjudication/attempt1/void.json).
"""
import json
import sys
from pathlib import Path

jobs, out = Path(sys.argv[1]), Path(sys.argv[2])
record = {"note": "Attempt 1's GPT-6 runner jobs, void before any return was read. Usage is the `usage` object of each "
                  "`turn.completed` event in the runner's event log; Codex counts cached input inside input_tokens "
                  "and reasoning output inside output_tokens. No return, item or message was read.",
          "jobs": {}}
for job in ("x5-adj-AB", "x5-adj-BA"):
    d = jobs / job
    turns = []
    for line in (d / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if '"turn.completed"' not in line:
            continue
        event = json.loads(line)
        if event.get("type") == "turn.completed":
            turns.append(event.get("usage"))
    record["jobs"][job] = {k: (d / k).read_text().strip() for k in ("exit", "model", "codex_version", "started",
                                                                     "finished")} | {"turn_usage": turns}
out.write_text(json.dumps(record, indent=1) + "\n")
print({j: v["turn_usage"] for j, v in record["jobs"].items()})
