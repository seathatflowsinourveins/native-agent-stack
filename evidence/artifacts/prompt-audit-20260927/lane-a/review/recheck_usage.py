"""Write claude-recheck-usage.json: the provider usage of the re-check, the review's Claude subagent resumed once.

usage: recheck_usage.py AGENT_ID [--harness JSON]

The resumed subagent appends to the review's transcript. The re-check starts at the first user entry whose text holds
"Re-check request:". Only assistant API calls after it are counted, each once (deduplicated by message id). Anthropic
usage fields are disjoint, so they are listed side by side and never added. Server-side advisor calls are counted;
their own model usage is not in these fields. The coordinator session is not included.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = Path.home() / ".claude/projects/<project-dir>/<session-id>/subagents"
FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
agent = sys.argv[1]
harness = json.loads(sys.argv[sys.argv.index("--harness") + 1]) if "--harness" in sys.argv else {}
meta = json.loads((D / f"agent-{agent}.meta.json").read_text())


def text_of(message):
    content = message.get("content")
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


started, calls, models, advisor = False, {}, [], 0
for line in (D / f"agent-{agent}.jsonl").read_text().splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if not started:
        started = e.get("type") == "user" and "Re-check request:" in text_of(e.get("message") or {})
        continue
    if e.get("type") == "assistant" and e["message"].get("id"):
        calls[e["message"]["id"]] = e["message"].get("usage") or {}
        m = e["message"].get("model")
        if m and m not in models:
            models.append(m)
        advisor += sum(1 for b in e["message"].get("content") or []
                       if isinstance(b, dict) and b.get("type") == "server_tool_use" and b.get("name") == "advisor")
if not started or not calls:
    sys.exit("no re-check calls found")
out = {"note": "Provider usage of the re-check only: the review's Claude subagent, resumed once with the repair list. "
               "Calls after the re-check request, deduplicated by API message id; Anthropic usage fields are disjoint, "
               "so they are listed side by side, never added. advisor_calls counts server-side advisor calls, whose "
               "own model usage is not in these fields. harness_counters are the completion notification's own "
               "counters. The coordinator session is not included.",
       "recheck-x5": {"agent_type": meta.get("agentType"), "models": models, "api_calls": len(calls),
                      "advisor_calls": advisor,
                      "provider_usage": {f: sum(int(u.get(f) or 0) for u in calls.values()) for f in FIELDS},
                      "harness_counters": harness}}
(HERE / "claude-recheck-usage.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out["recheck-x5"]))
