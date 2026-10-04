#!/usr/bin/env bash
# Fresh-session E2E of the token stack on one WSL, with upstream commands only (the user's directive of 2026-10-04 21:30Z:
# "install cleanly with upstreamcommands, best sota practice natively, and e2e with upstream commands with new session
# launched e2e for our wsls").
#
#   fresh_session_e2e.sh <label>      # nativestack | nativestack2604; run inside that distribution
#
# It sequences upstream commands in a brand-new project directory, so that nothing registered per project can help, and reads
# their own output with jq: `rtk --version`, `rtk init --show`, `rtk gain -f json` (before and after), `claude mcp list`,
# `codex mcp list`, a headless `claude -p --output-format stream-json --verbose --include-hook-events` session (hook
# lifecycle events, the MCP servers of its init event, its result and usage) and a headless `codex exec --json --ephemeral`
# session. Local monitoring of what this host does today, never an A/B. Costs two trivial sessions per run (one Haiku
# probe pair, one Codex Sol low-effort probe).
set -u
label=${1:?usage: fresh_session_e2e.sh <label>}
base=${E2E_OUT:-$HOME/.local/state/native-agent-stack/e2e}
repo=${E2E_REPO:-$PWD}   # a checkout that may carry per-project MCP registrations
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out=$base/fresh-$label-$stamp
mkdir -p "$out"
project=$(mktemp -d "$HOME/.cache/native-agent-stack-e2e-project-XXXXXX")
cleanup() { case $project in "$HOME"/.cache/native-agent-stack-e2e-project-*) rm -rf "$project" ;; esac; }
trap cleanup EXIT
git -C "$project" init -q
mkdir -p "$project/a/x" "$project/b/x" "$project/c"
for f in a/x/util.py b/x/util.py c/util.py; do echo needle > "$project/$f"; done
echo nothing > "$project/c/other.py"

step() { name=$1; shift; "$@" > "$out/$name.out" 2> "$out/$name.err" < /dev/null; echo $? > "$out/$name.rc"; }
names() { grep -E '^[A-Za-z:_-]+: .* - .*(Connected|Failed|authentication)' "$1" 2>/dev/null | sed 's/: .*//' | sort; }  # server lines of `claude mcp list`
cd "$project" || exit 2

step rtk-version rtk --version
step rtk-init-show rtk init --show
step claude-version claude --version
step codex-version codex --version
step gain-before rtk gain -f json
step mcp-claude-fresh timeout 120 claude mcp list
step mcp-codex-fresh timeout 60 codex mcp list
( cd "$repo" && step mcp-claude-repo timeout 120 claude mcp list ) 2>/dev/null

timeout 240 claude -p --model haiku --output-format stream-json --verbose --include-hook-events --max-turns 4 \
  "With the Bash tool run exactly this command: git status then reply DONE." > "$out/claude-git.jsonl" 2> "$out/claude-git.err" < /dev/null
echo $? > "$out/claude-git.rc"
timeout 240 claude -p --model haiku --output-format stream-json --verbose --include-hook-events --max-turns 4 \
  "With the Bash tool run exactly this command: grep -rl needle . then reply with how many files it listed." \
  > "$out/claude-grep.jsonl" 2> "$out/claude-grep.err" < /dev/null
echo $? > "$out/claude-grep.rc"
timeout 300 codex exec --json --ephemeral --skip-git-repo-check -m gpt-6.1-sol -c model_reasoning_effort='"low"' \
  "Run git status once with the shell tool, then reply with the single word DONE." \
  > "$out/codex-git.jsonl" 2> "$out/codex-git.err" < /dev/null
echo $? > "$out/codex-git.rc"
step gain-after rtk gain -f json
step gain-project rtk gain -p

{
  echo "# Fresh-session E2E: $label, $stamp (upstream commands only; local monitoring, not an A/B)"
  echo
  echo "## Versions"
  echo "- $(cat "$out/rtk-version.out" | head -1); claude $(head -1 "$out/claude-version.out"); $(head -1 "$out/codex-version.out")"
  echo "## rtk init --show"
  sed -n '1,12p' "$out/rtk-init-show.out" | sed 's/^/    /'
  echo "## MCP servers a fresh directory sees (claude mcp list / codex mcp list)"
  echo "- claude, names: $(names "$out/mcp-claude-fresh.out" | tr '\n' ' ')"
  echo "- claude, connected: $(grep -c 'Connected' "$out/mcp-claude-fresh.out") of $(names "$out/mcp-claude-fresh.out" | wc -l)"
  echo "- claude, only in $repo (local or project scope, so a new project lacks it): $(comm -13 <(names "$out/mcp-claude-fresh.out") <(names "$out/mcp-claude-repo.out") | tr '\n' ' ')"
  echo "- codex, names: $(awk 'NF && $1!="Name" && $1!="Url" && $1 !~ /^[-]/ {print $1}' "$out/mcp-codex-fresh.out" | sort -u | tr '\n' ' ')"
  for session in claude-git claude-grep; do
    echo "## Claude fresh session: $session"
    jq -r 'select(.type=="system" and .subtype=="init") | "- init: claude_code_version \(.claude_code_version), model \(.model), permissionMode \(.permissionMode), tools \(.tools|length), plugins \(.plugins|length)\n- MCP servers in the init event: \([.mcp_servers[]? | "\(.name)=\(.status)"] | join(", "))"' "$out/$session.jsonl"
    echo "- hook events (event, name, outcome, count):"
    jq -r 'select(.type=="system" and .subtype=="hook_response") | "\(.hook_event)\t\(.hook_name)\t\(.outcome)"' "$out/$session.jsonl" | sort | uniq -c | sed 's/^ */    /'
    echo "- asked for / rewritten to:"
    jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | "    asked: \(.input.command)"' "$out/$session.jsonl"
    jq -r 'select(.type=="system" and .subtype=="hook_response" and .hook_event=="PreToolUse") | select(.stdout|test("updatedInput")) | .stdout | fromjson | .hookSpecificOutput | "    \(.permissionDecisionReason): \(.updatedInput.command)"' "$out/$session.jsonl"
    jq -r 'select(.type=="user") | .message.content[]? | select(.type=="tool_result") | "    result: \(.content|tostring|.[0:300])"' "$out/$session.jsonl"
    jq -r 'select(.type=="result") | "- result: \(.subtype), turns \(.num_turns), cost $\(.total_cost_usd), tokens in \(.usage.input_tokens) out \(.usage.output_tokens) cache-read \(.usage.cache_read_input_tokens)"' "$out/$session.jsonl"
  done
  echo "## Codex fresh session: codex-git"
  jq -r 'select(.type=="item.completed" and .item.type=="command_execution") | "- executed: \(.item.command) (exit \(.item.exit_code)): \(.item.aggregated_output|tostring|.[0:120])"' "$out/codex-git.jsonl"
  jq -r 'select(.type=="turn.completed") | "- usage: input \(.usage.input_tokens), cached \(.usage.cached_input_tokens), output \(.usage.output_tokens)"' "$out/codex-git.jsonl"
  echo "## rtk gain (upstream counter, whole host: the delta spans the E2E's interval and includes any other session's commands; the project-scoped block below is this E2E's own)"
  jq -n --slurpfile b "$out/gain-before.out" --slurpfile a "$out/gain-after.out" \
    '"- commands \($b[0].summary.total_commands) -> \($a[0].summary.total_commands) (+\($a[0].summary.total_commands - $b[0].summary.total_commands)); saved tokens \($b[0].summary.total_saved) -> \($a[0].summary.total_saved) (+\($a[0].summary.total_saved - $b[0].summary.total_saved)); average saving \($a[0].summary.avg_savings_pct)%"' -r
  echo "- rtk gain -p (this fresh project only):"
  sed -n '1,14p' "$out/gain-project.out" | sed 's/^/    /'
} > "$out/summary.md" 2>&1
echo "$out"
