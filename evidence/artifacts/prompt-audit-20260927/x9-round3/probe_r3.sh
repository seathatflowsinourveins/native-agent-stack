#!/usr/bin/env bash
# promptfoo exec provider for the X9 round-3 comparison (K5, K6): round 2's run_arm.sh, the same contract
# (promptfoo 0.123.1, src/providers/scriptCompletion.ts: argv is this script's own args, then the prompt, the provider
# options JSON and the call context JSON; stdout, trimmed, is the output), plus:
# - the model pinned on the command line, and the permission mode and setting sources stated explicitly, each equal
#   to the host default that round 2's runs recorded;
# - the fixture plugin (--plugin-dir) and the fixture MCP server (--mcp-config) in every run, next to the host's own;
# - each run's own ground truth, kept out of the session's environment: the plugin's hook writes to its state
#   directory under the session id, and the server gets its log path and exit delay from a per-run MCP config
#   (the server entry's env), not from the environment the session's tools inherit.
# Uncounted probes: run_arm_r3.sh with the output named by the caller under probe/.
# usage: probe_r3.sh <arm> <name> <prompt>
set -u
arm=$1 name=$2 prompt=$3
X=$(cd "$(dirname "$0")" && pwd)
S=$(dirname "$(dirname "$X")")
wt=$S/wt-x9r3-$arm
mkdir -p "$X/probe"
stamp=$(date -u +%Y%m%dT%H%M%SZ)-$$
out=$X/probe/$name.jsonl
python3 - "$X" "$out" <<'EOF'
import json, sys
from pathlib import Path
x, out = Path(sys.argv[1]), Path(sys.argv[2])
cfg = {"mcpServers": {"ticket-tracker": {
    "type": "stdio", "command": str(x.parent / "mcp-venv" / "bin" / "python"),
    "args": [str(x / "fixtures" / "ticket-tracker" / "server.py")],
    "env": {"R3_MCP_LOG": str(out.with_suffix(".mcplog")), "R3_EXIT_AFTER_S": "1"}}}}
out.with_suffix(".mcpconfig.json").write_text(json.dumps(cfg, indent=1) + "\n")
EOF
start=$(date +%s%3N)
(cd "$wt" && timeout 300 claude -p "$prompt" --output-format stream-json --verbose --max-turns 10 \
  --model 'claude-opus-5-5[1m]' --permission-mode bypassPermissions --setting-sources user,project,local \
  --plugin-dir "$X/fixtures/workspace-guard" --mcp-config "${out%.jsonl}.mcpconfig.json" \
  < /dev/null > "$out" 2> "$out.err")
rc=$?
python3 "$X/summarize_r3.py" "$arm" "$out" "$rc" "$(( $(date +%s%3N) - start ))"
