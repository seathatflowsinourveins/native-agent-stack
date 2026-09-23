#!/usr/bin/env bash
# Run ccusage 20.0.24 over this host's real native Claude logs (default
# config dir auto-discovery, no --config override) and report only aggregate
# counts (never message content). Compare the ccusage session grouped by
# sessionId == the workflow run id against the same workflow's
# child-usage.mjs totals to check whether ccusage attributes child/subagent
# usage.
set -euo pipefail

OUT=${1:-/tmp/ccusage-real-check}
mkdir -p "$OUT"

ccusage --version
ccusage claude daily --json --offline --no-cost > "$OUT/daily.json"
ccusage claude session --json --offline --no-cost > "$OUT/session.json"

WF_JOURNAL_DIR=/home/example/.claude/projects/<project-slug>/EXAMPLE-CLAUDE-SESSION-ID/subagents/workflows/wf_76e829b6-778
node /home/example/code/agent-lab/.claude/workflows/child-usage.mjs "$WF_JOURNAL_DIR" > "$OUT/child-usage-mjs-wf_76e829b6-778.json"

python3 - "$OUT" <<'PYEOF'
import json, sys
out = sys.argv[1]
session = json.load(open(f"{out}/session.json"))
wf = next((s for s in session["sessions"] if s["sessionId"] == "wf_76e829b6-778"), None)
child = json.load(open(f"{out}/child-usage-mjs-wf_76e829b6-778.json"))
tot = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
for c in child["children"]:
    for k in tot:
        tot[k] += c["usage"].get(k, 0)
print("ccusage wf_76e829b6-778 session entry:", json.dumps(wf, indent=2) if wf else None)
print("child-usage.mjs summed totals:", tot)
if wf:
    print("input_tokens match:", wf["inputTokens"] == tot["input_tokens"])
    print("output_tokens match:", wf["outputTokens"] == tot["output_tokens"])
    print("cache_read match:", wf["cacheReadTokens"] == tot["cache_read_input_tokens"])
    print("cache_creation match:", wf["cacheCreationTokens"] == tot["cache_creation_input_tokens"])
PYEOF
