"""Write x9-round2/<OUT_NAME>: per-call provider usage of named Claude subagents of this session.

usage: claude_usage.py OUT_NAME ROLE=AGENT_ID... [--harness JSON]

As claude_usage_round2.py: each assistant API call appears once per content block with the same message id, so calls
are deduplicated by id; Anthropic usage fields are disjoint, so they are listed side by side and never added into one
total. Server-side advisor calls are counted; their own model usage is not in these fields. The harness's completion
counters, when given, are kept beside them. The coordinator session is not included.
"""
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
D = Path.home() / ".claude/projects/<project-dir>/<session-id>/subagents"
FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
args = sys.argv[2:]
harness = {}
if "--harness" in args:
    i = args.index("--harness")
    harness = json.loads(args[i + 1])
    args = args[:i] + args[i + 2:]
out = {"note": "Per-call provider usage of these Claude subagents, read from their transcripts and deduplicated by API "
               "message id. Anthropic usage fields are disjoint (input_tokens excludes cache reads and cache writes), "
               "so they are listed side by side, never added. advisor_calls counts server-side advisor calls, whose "
               "own model usage is not in these fields. harness_counters are the completion notification's own "
               "counters. The coordinator session is not included."}
for pair in args:
    role, agent = pair.split("=", 1)
    meta = json.loads((D / f"agent-{agent}.meta.json").read_text())
    calls, models, advisor = {}, [], 0
    for line in (D / f"agent-{agent}.jsonl").read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "assistant" and e["message"].get("id"):
            calls[e["message"]["id"]] = e["message"].get("usage") or {}
            m = e["message"].get("model")
            if m and m not in models:
                models.append(m)
            advisor += sum(1 for c in e["message"].get("content") or []
                           if c.get("type") == "server_tool_use" and c.get("name") == "advisor")
    out[role] = {"agent_type": meta["agentType"], "models": sorted(models), "api_calls": len(calls),
                 "advisor_calls": advisor, "provider_usage": {k: sum(u.get(k) or 0 for u in calls.values())
                                                              for k in FIELDS},
                 **({"harness_counters": harness[role]} if role in harness else {})}
    print(role, out[role]["agent_type"], out[role]["models"], out[role]["api_calls"], "advisor", advisor,
          out[role]["provider_usage"])
(WORK / "x9-round2" / sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
