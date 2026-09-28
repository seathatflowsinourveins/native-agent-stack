"""Compact facts from one X9 round-3 run, as JSON on stdout: round 2's summarize.py output plus the run's ground truth.

usage: summarize_r3.py ARM TRANSCRIPT EXIT_CODE DURATION_MS
Adds, from the transcript's init event and the files the run's fixtures wrote:
- session_id and target_tools_in_init: the init event's session id, and how many of its tools belong to the fixture
  server (mcp__ticket-tracker__...);
- hook: the fixture plugin's marker (fixtures/workspace-guard/state/<session id>.log): whether it exists and how many
  lines it holds; the hook writes one line per run, so a missing marker means it did not run;
- mcp: the fixture server's event log (<transcript stem>.mcplog): its events in order, an exit written as
  `exit:<reason>`, such as `start`, `tools/list`, `exit:timer`.
Facts only, no judgment. The init event's MCP server statuses and plugins come from summarize.py unchanged.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
arm, path = sys.argv[1], Path(sys.argv[2])
base = json.loads(subprocess.run([sys.executable, str(HERE / "summarize.py"), *sys.argv[1:5]],
                                 capture_output=True, text=True, check=True).stdout)
init = {}
for line in path.read_text().splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("type") == "system" and e.get("subtype") == "init":
        init = e
        break
sid = init.get("session_id") or ""
base["session_id"] = sid
base["target_tools_in_init"] = sum(str(t).startswith("mcp__ticket-tracker__") for t in init.get("tools") or [])
marker = HERE / "fixtures" / "workspace-guard" / "state" / f"{sid}.log"
base["hook"] = {"exists": bool(sid) and marker.exists(),
                "lines": len(marker.read_text().splitlines()) if sid and marker.exists() else 0}
log = path.with_suffix(".mcplog")
events = []
if log.exists():
    for line in log.read_text().splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            events.append("unparsed")
            continue
        events.append(d.get("event") + (f":{d['reason']}" if d.get("reason") else ""))
base["mcp"] = {"exists": log.exists(), "events": events}
print(json.dumps(base))
