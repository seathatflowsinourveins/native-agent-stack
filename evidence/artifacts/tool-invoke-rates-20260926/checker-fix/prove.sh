#!/usr/bin/env bash
# u6 host proof, to run AFTER the apply plan in DESIGN.md. Read-only toward the observability stack: it changes no
# config and restarts nothing; it only queries loopback health, Collector self-metrics and Loki.
#
# It runs one real `claude -p` (the u6 probe prompt: ToolSearch + context-mode MCP, Skill codebase-design, one Agent
# general-purpose subagent with qmd MCP + Bash, one Workflow child with qmd MCP) and one `codex exec` (ctx_stats MCP,
# git log, one sub-agent running pwd), both with the live settings and a fresh OTEL_RESOURCE_ATTRIBUTES
# ecosystem.task.id, then asserts that production Loki shows the per-server, per-skill, per-subagent and per-client
# counts for that id within 120 s (Claude launches from the accepted tool_decision), with no command or prompt text
# and no model-typed name (workflow name, Codex agent path, custom agent type) stored. Model calls cost money: about
# 0.2-0.4 USD for Claude (u6 probe estimates) plus Codex quota.
#
# Usage: prove.sh [--dry-run]
#   --dry-run  no model call: preflight plus every Loki query for a fresh id (all must parse and return nothing).
# Env: PROVE_WORKDIR / REPO (default: the native-agent-stack checkout; must be a checkout of this PR or later
#      -- read for the staged collector.yaml/dashboard, exactly as replay-test.sh's REPO), PROVE_DEADLINE
#      (default 120 seconds), PROVE_U6_DIR (default: this script's own directory; no session path is
#      hard-coded), PROVE_OUT_DIR (default: a fresh mktemp -d; raw run output, including real prompts/
#      transcripts, is never written inside a committed/tracked directory), PROVE_PROMPT_FILE (required for a
#      live run: your own Claude probe prompt -- not committed here; see ../README.md).
#
# This committed copy is a reference copy: STAGED_COLLECTOR/STAGED_DASHBOARD read from $REPO directly (this
# receipt's scratch-replay/ already confirmed those files are byte-identical to what the original scratch
# copy staged), run_panel_queries.py is read from ../scratch-replay/, and prove_check.py sits next to this
# script. See ../README.md before running it live.
#
# Fixed 2026-09-26 (window-2 finding 2 / decision-thread PRRT_kwDOUg_LrM6mT7_M): the forbidden-string list this
# script builds was filtered to lines of 12+ characters, so the probe's own short executed command (`pwd`) was
# never a candidate to check; it is now added explicitly, with no length floor, and prove_check.py (see its own
# header) now asserts every tagged record's body against the fixed placeholder instead of only substring-searching
# a list of long sentences.
set -u
U6="${PROVE_U6_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)}"
REPO="${REPO:-${PROVE_WORKDIR:-$HOME/code/native-agent-stack}}"
LOKI="${PROVE_LOKI:-http://127.0.0.1:13100}"          # production Loki, read-only queries
HEALTH="${PROVE_HEALTH:-http://127.0.0.1:24333/}"     # production Collector health_check
SELF="${PROVE_SELF:-http://127.0.0.1:28888/metrics}"  # production Collector self-metrics
GRAFANA="${PROVE_GRAFANA:-http://127.0.0.1:13000}"    # production Grafana, anonymous Viewer (read-only API)
STAGED_COLLECTOR="$REPO/observability/collector/collector.yaml"
STAGED_DASHBOARD="$REPO/observability/backends/templates/ecosystem-dashboard.json.example"
RUN_PANEL_QUERIES="$U6/../scratch-replay/run_panel_queries.py"
EVENTS_GLOB="${PROVE_EVENTS_GLOB:-$HOME/.local/share/codex-ecosystem/observability/collector/events*.jsonl}"
WORKDIR="${PROVE_WORKDIR:-$HOME/code/native-agent-stack}"
DEADLINE="${PROVE_DEADLINE:-120}"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
TASK="u6-prove-$(cat /proc/sys/kernel/random/uuid)"
RAW_BASE="${PROVE_OUT_DIR:-$(mktemp -d)}"
OUT="$RAW_BASE/prove-$(date -u +%Y%m%dT%H%M%SZ)"
umask 077; mkdir -p "$OUT"; chmod 700 "$RAW_BASE" "$OUT"
PASS=0; FAIL=0
result() { if [ "$1" = 0 ]; then PASS=$((PASS + 1)); echo "PASS $2"; else FAIL=$((FAIL + 1)); echo "FAIL $2"; fi; }
echo "task id: $TASK  mode: $([ $DRY = 1 ] && echo dry-run || echo live)  out: raw/$(basename "$OUT")"

# Preflight (read-only)
[ "$(curl -s --max-time 5 "$LOKI/ready")" = "ready" ]; result $? "production Loki ready"
curl -sf --max-time 5 "$HEALTH" > /dev/null; result $? "production Collector health_check answers"
curl -s --max-time 5 "$SELF" > "$OUT/self-metrics-before.txt"
grep -q 'otelcol-contrib' "$OUT/self-metrics-before.txt" && grep -q 'service_version="0.161.0"' "$OUT/self-metrics-before.txt"
result $? "production Collector is otelcol-contrib 0.161.0"
# Only key names and truthiness of three env keys are read from the live Claude settings; no value is printed.
python3 - "$HOME/.claude/settings.json" > "$OUT/settings-flags.txt" <<'PY'
import json, sys
env = json.load(open(sys.argv[1])).get("env", {})
def on(name):
    return str(env.get(name, "")).strip().lower() not in ("", "0", "false", "no", "off")
print("tool_details", on("OTEL_LOG_TOOL_DETAILS"))
print("session_id", on("OTEL_METRICS_INCLUDE_SESSION_ID"))
print("resource_attributes_in_settings", "OTEL_RESOURCE_ATTRIBUTES" in env)
PY
precondition() {  # counted in a live run; informational in a dry run (it may precede the apply)
  if [ "$DRY" = 1 ]; then echo "INFO precondition $([ "$1" = 0 ] && echo met || echo 'not met yet'): $2"; else result "$1" "$2"; fi
}
grep -qx 'tool_details True' "$OUT/settings-flags.txt"
precondition $? "live Claude settings have OTEL_LOG_TOOL_DETAILS on (apply step 7)"
grep -qx 'resource_attributes_in_settings False' "$OUT/settings-flags.txt"
precondition $? "live Claude settings do not pin OTEL_RESOURCE_ATTRIBUTES (the proof's task id reaches the events)"
grep -q 'processor="transform/tool_names"' "$OUT/self-metrics-before.txt"
precondition $? "production Collector already reports transform/tool_names (after apply and some traffic)"
# The deployed dashboard (Grafana's provisioned copy), not the staged file, must carry the invoke-rate row.
curl -s --max-time 10 "$GRAFANA/api/dashboards/uid/ecosystem-native" > "$OUT/deployed-dashboard.json"
python3 - "$OUT/deployed-dashboard.json" "$STAGED_DASHBOARD" > "$OUT/dashboard-compare.txt" <<'PY'
import json, sys
deployed = json.load(open(sys.argv[1])).get("dashboard", {})
staged = json.load(open(sys.argv[2]))
row = lambda d: {p["id"]: [t["expr"] for t in p.get("targets", [])] for p in d.get("panels", []) if p["id"] >= 28}
print("deployed row matches staged" if row(deployed) and row(deployed) == row(staged) else "deployed row differs or is absent")
PY
grep -qx 'deployed row matches staged' "$OUT/dashboard-compare.txt"
DEPLOYED=$?
precondition $DEPLOYED "Grafana serves the invoke-rate row exactly as staged (apply step 6)"

if [ "$DRY" = 1 ]; then
  python3 "$U6/prove_check.py" "$LOKI" "$TASK" 0 --dry-run --collector "$STAGED_COLLECTOR" \
    | tee "$OUT/checks.txt" | grep -E '^(PASS|FAIL)'
  line=$(grep '^SUMMARY' "$OUT/checks.txt")
  PASS=$((PASS + $(sed -E 's/.*: ([0-9]+) passed.*/\1/' <<<"$line"))); FAIL=$((FAIL + $(sed -E 's/.*, ([0-9]+) failed/\1/' <<<"$line")))
  python3 "$RUN_PANEL_QUERIES" "$LOKI" "$STAGED_DASHBOARD" 1h \
    > "$OUT/panels.txt"; result $? "every new dashboard target parses on production Loki ($(tail -1 "$OUT/panels.txt"))"
  echo "TOTAL: $PASS passed, $FAIL failed (dry run: no model call)"
  [ "$FAIL" = 0 ]; exit
fi
[ "$FAIL" = 0 ] || { echo "TOTAL: $PASS passed, $FAIL failed (preflight failed; no model call made)"; exit 1; }

# 1. Claude Code: one headless run with the live settings (production Collector), fresh top-level session
PROMPT="$(cat "${PROVE_PROMPT_FILE:?set PROVE_PROMPT_FILE to your probe prompt file -- not committed here, see ../README.md}")"
( cd "$WORKDIR" && env -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_CHILD_SESSION -u CLAUDE_CODE_MESSAGING_SOCKET \
    -u CLAUDE_CODE_MESSAGING_TOKEN -u CLAUDE_CODE_SESSION_ATTENDED -u CLAUDE_PID -u CLAUDECODE \
    -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_EFFORT -u CLAUDE_CODE_EXECPATH -u CLAUDE_PLUGIN_DATA \
    OTEL_RESOURCE_ATTRIBUTES="ecosystem.task.id=$TASK" \
    timeout 900 claude -p --model claude-sonnet-5 --output-format json "$PROMPT" \
    > "$OUT/claude-result.json" 2> "$OUT/claude-stderr.txt" < /dev/null )
result $? "claude -p probe run exited 0"

# 2. Codex: one exec run with the live config (production Collector); stdin closed (exec can wait on stdin)
CODEX_TASK='Do exactly these steps and nothing else. Do not modify any files.
1. Call the context-mode MCP tool ctx_stats exactly once (no arguments).
2. Run the shell command: git log --oneline -1
3. Spawn exactly one sub-agent whose only task is to run the shell command pwd once and report its output. Wait for that sub-agent to finish and read its result. If you cannot spawn a sub-agent, do not work around it; state the exact reason.
Then reply with exactly three lines: "ctx_stats: ok" or "ctx_stats: failed <reason>"; "git: <the git log line>"; "subagent: <the pwd output>" or "subagent: unavailable <reason>".'
OTEL_RESOURCE_ATTRIBUTES="ecosystem.task.id=$TASK" timeout 1200 codex exec -m gpt-6-astra -c model_reasoning_effort=max \
  --json --sandbox read-only --skip-git-repo-check -C "$WORKDIR" "$CODEX_TASK" \
  < /dev/null > "$OUT/codex-exec.jsonl" 2> "$OUT/codex-stderr.txt"
result $? "codex exec probe run exited 0"

# Strings that must never reach Loki or the events file: every sentence of both prompts, plus every literal
# shell command either probe executes (explicitly; a bare command like `pwd` will not survive sentence-splitting
# a descriptive prompt into its own line). No minimum length: prove_check.py matches parsed values, not raw text,
# so a short literal cannot false-positive on JSON structure.
{ printf '%s\n' "$PROMPT" "$CODEX_TASK" | tr '.' '\n'; echo "git log --oneline -1"; echo "pwd"; } \
  | sed -E 's/^[[:space:]0-9.]*//; s/[[:space:]]+$//' | awk 'NF' | sort -u > "$OUT/forbidden.txt"

# 3. Production Loki within the deadline (read-only)
python3 "$U6/prove_check.py" "$LOKI" "$TASK" "$DEADLINE" --forbidden-file "$OUT/forbidden.txt" \
  --collector "$STAGED_COLLECTOR" --events-glob "$EVENTS_GLOB" | tee "$OUT/checks.txt" | grep -E '^(PASS|FAIL|INFO)'
line=$(grep '^SUMMARY' "$OUT/checks.txt")
if [ -n "$line" ]; then
  PASS=$((PASS + $(sed -E 's/.*: ([0-9]+) passed.*/\1/' <<<"$line"))); FAIL=$((FAIL + $(sed -E 's/.*, ([0-9]+) failed/\1/' <<<"$line")))
else
  result 1 "Loki check harness completed"
fi
curl -s --max-time 5 "$SELF" > "$OUT/self-metrics-after.txt"
grep -q 'processor="transform/tool_names"' "$OUT/self-metrics-after.txt"
result $? "production Collector reports the transform/tool_names processor"
python3 "$RUN_PANEL_QUERIES" "$LOKI" "$OUT/deployed-dashboard.json" 1h \
  > "$OUT/panels.txt"; result $? "every deployed invoke-rate target returns on production Loki ($(tail -1 "$OUT/panels.txt"))"
echo "TOTAL: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
