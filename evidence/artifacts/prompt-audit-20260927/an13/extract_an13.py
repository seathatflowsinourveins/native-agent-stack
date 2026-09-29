"""Write an13-runs.json: the facts of both AN-13 runs (a headless `/doctor prompt-audit`), from each run's own files.

usage: extract_an13.py FIRST_RUN_DIR RERUN_DIR OUT
Each run directory holds the client's stream-json log (run.jsonl), its stderr (stderr.txt) and the wrapper's
started, finished and exit files. Kept:
- from the init event, the client version, the model and the permission mode;
- from the result event, the outcome, timing, turn count, the reported cost and its basis, both usage blocks as
  reported, the subagent statistics, the tool names of permission denials and the length of the result;
- counts of the background-task and permission events;
- stderr, when it is one short line.
Not kept: the result text, prompts, tool calls and returns, paths, session ids, and the plugin, skill and MCP
inventories.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

USAGE = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
MODEL_USAGE = ("inputTokens", "cacheCreationInputTokens", "cacheReadInputTokens", "outputTokens", "thinkingTokens",
               "costUSD", "costBasis")
EVENTS = ("task_started", "task_updated", "task_notification", "background_tasks_changed", "permission_denied")
PRIVATE = re.compile(r"/tmp/|/home/|/Users/|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}|@", re.I)


def run(d):
    d = Path(d)
    init = result = None
    events = Counter()
    for line in (d / "run.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            init = e
        elif e.get("type") == "system" and e.get("subtype") in EVENTS:
            events[e["subtype"]] += 1
        elif e.get("type") == "result":
            result = e
    stderr = (d / "stderr.txt").read_text(encoding="utf-8").strip()
    if "\n" in stderr or len(stderr) > 300 or PRIVATE.search(stderr):
        sys.exit(f"{d.name}: stderr is not one short line without private content")
    usage = result.get("usage") or {}
    return {
        "started": (d / "started").read_text().strip(),
        "finished": (d / "finished").read_text().strip(),
        "exit": int((d / "exit").read_text().strip().split("=")[-1]),
        "stderr": stderr,
        "client": init.get("claude_code_version"),
        "model": init.get("model"),
        "permission_mode": init.get("permissionMode"),
        "result": {k: result.get(k) for k in ("subtype", "is_error", "stop_reason", "terminal_reason", "duration_ms",
                                               "duration_api_ms", "num_turns", "total_cost_usd")},
        "result_chars": len(result.get("result") or ""),
        "usage": {**{k: usage.get(k) for k in USAGE},
                  "thinking_tokens": (usage.get("output_tokens_details") or {}).get("thinking_tokens")},
        "model_usage": {m: {k: v.get(k) for k in MODEL_USAGE} for m, v in (result.get("modelUsage") or {}).items()},
        "subagent_stats": result.get("subagent_stats"),
        "permission_denials": [p.get("tool_name") for p in result.get("permission_denials") or []],
        "events": {k: events[k] for k in EVENTS},
    }


out = {"note": "Facts of the two AN-13 runs, from each run's stream-json init and result events, its stderr and the "
               "wrapper's time and exit files. 'usage' and 'model_usage' are the result event's two usage blocks as "
               "the client reports them; they overlap and are never added. total_cost_usd is the client's own "
               "figure at list prices (costBasis), not a bill.",
       "first_run": run(sys.argv[1]), "rerun": run(sys.argv[2])}
Path(sys.argv[3]).write_text(json.dumps(out, indent=1) + "\n")
for k in ("first_run", "rerun"):
    r = out[k]
    print(k, r["exit"], r["result"]["num_turns"], r["result_chars"], r["subagent_stats"]["killed"], r["events"])
