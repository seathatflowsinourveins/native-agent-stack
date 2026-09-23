#!/usr/bin/env bash
# Runs one blind judge claude -p call. Usage: run-judge.sh <label> <prompt-file>
set -uo pipefail
LABEL="$1"
PROMPT_FILE="$2"
STATE="$HOME/codex-ecosystem/state/gap-wave3-20260923"
RAW="$STATE/native-clients/raw/judge"
mkdir -p "$RAW"
OUT="$RAW/judge-${LABEL}.json"
flock "$STATE/claude.lock" claude -p "$(cat "$PROMPT_FILE")" \
  --output-format json --effort medium --allowedTools "" \
  > "$OUT" 2> "${OUT%.json}.stderr"
EXIT=$?
sleep 20
echo "LABEL=$LABEL EXIT=$EXIT OUT=$OUT"
exit "$EXIT"
