"""Provider usage of one Claude review subagent, from its transcript: every assistant API call, each counted once
(deduplicated by message id). Anthropic usage fields are disjoint, so they are listed side by side and never added.
Server-side advisor calls are counted; their own model usage is not in these fields. The coordinator session is not
included. The subagent's id and the transcript's location are arguments, and neither is written to the output.

usage: review_usage.py TRANSCRIPT_DIR AGENT_ID LABEL [--harness JSON]
"""
import json
import sys
from pathlib import Path

FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
d, agent, label = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
harness = json.loads(sys.argv[sys.argv.index("--harness") + 1]) if "--harness" in sys.argv else {}
meta = json.loads((d / f"agent-{agent}.meta.json").read_text())
calls, models, advisor = {}, [], 0
for line in (d / f"agent-{agent}.jsonl").read_text().splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("type") == "assistant" and e["message"].get("id"):
        calls[e["message"]["id"]] = e["message"].get("usage") or {}
        m = e["message"].get("model")
        if m and m not in models:
            models.append(m)
        advisor += sum(1 for b in e["message"].get("content") or []
                       if isinstance(b, dict) and b.get("type") == "server_tool_use" and b.get("name") == "advisor")
if not calls:
    sys.exit("no assistant calls found")
print(json.dumps({label: {"agent_type": meta.get("agentType"), "models": models, "api_calls": len(calls),
                          "advisor_calls": advisor,
                          "provider_usage": {f: sum(int(u.get(f) or 0) for u in calls.values()) for f in FIELDS},
                          "harness_counters": harness}}, indent=1))
