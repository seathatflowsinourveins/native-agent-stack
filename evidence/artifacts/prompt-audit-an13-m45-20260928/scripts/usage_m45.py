"""Provider usage of the M4/M5 convergence, each counter kept separate and never added across providers or fields.

usage: usage_m45.py OUT LABEL=TRANSCRIPT... -- LABEL=RUNNER_RECORD...
Claude: every assistant API call in a subagent transcript, counted once (deduplicated by message id); Anthropic's
four usage fields are disjoint and listed side by side. The transcripts' locations and the subagents' ids are
arguments and are not written. Server-side advisor calls are counted; their own model usage is not in these fields.
GPT-6: the packaged runner's own usage record per job; cached input is a subset of input and reasoning output a
subset of output, as the runner reports them. The coordinator session is not included.
"""
import json
import sys
from pathlib import Path

FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
out = Path(sys.argv[1])
split = sys.argv.index("--")
claude_args, gpt_args = sys.argv[2:split], sys.argv[split + 1:]
result = {"claude": {}, "gpt6": {}}
for arg in claude_args:
    label, path = arg.split("=", 1)
    p = Path(path).resolve()
    meta_path = p.with_name(p.name.replace(".jsonl", ".meta.json"))
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    calls, models, advisor = {}, [], 0
    for line in p.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "assistant" and e["message"].get("id"):
            calls[e["message"]["id"]] = e["message"].get("usage") or {}
            mdl = e["message"].get("model")
            if mdl and mdl not in models:
                models.append(mdl)
            advisor += sum(1 for b in e["message"].get("content") or []
                           if isinstance(b, dict) and b.get("type") == "server_tool_use" and b.get("name") == "advisor")
    result["claude"][label] = {"agent_type": meta.get("agentType"), "models": models, "api_calls": len(calls),
                               "advisor_calls": advisor,
                               "provider_usage": {f: sum(int(u.get(f) or 0) for u in calls.values()) for f in FIELDS}}
for arg in gpt_args:
    label, path = arg.split("=", 1)
    rec = json.loads(Path(path).read_text())
    result["gpt6"][label] = {k: rec.get(k) for k in ("model", "effort", "codex_version", "status", "exit", "limit",
                                                    "started", "finished", "usage", "usage_status")}
out.write_text(json.dumps(result, indent=1) + "\n")
print(json.dumps({k: list(v) for k, v in result.items()}))
