#!/usr/bin/env bash
# Runs one arm (claude or codex) of the frozen research task and writes raw
# output under $HOME/codex-ecosystem/state/gap-wave3-20260923/native-clients/raw/.
# Usage: run-arm.sh <claude|codex> <run-label> <prompt-file>
set -uo pipefail
ARM="$1"
LABEL="$2"
PROMPT_FILE="$3"
STATE="$HOME/codex-ecosystem/state/gap-wave3-20260923"
RAW="$STATE/native-clients/raw"
mkdir -p "$RAW"
OUT="$RAW/${LABEL}.json"
ERR="$RAW/${LABEL}.stderr"

if [ "$ARM" = "claude" ]; then
  flock "$STATE/claude.lock" claude -p "$(cat "$PROMPT_FILE")" \
    --output-format json --effort medium --allowedTools Bash \
    > "$OUT" 2> "$ERR"
  EXIT=$?
  sleep 20
elif [ "$ARM" = "codex" ]; then
  while [ "$(ps -eo args= | awk '$1 ~ /(^|\/)codex$/ && $2=="exec"' | wc -l)" -ge 2 ]; do
    sleep 5
  done
  flock "$STATE/codex.lock" codex exec --json \
    -c model_reasoning_effort=medium \
    -s workspace-write \
    - < "$PROMPT_FILE" \
    > "$OUT" 2> "$ERR"
  EXIT=$?
else
  echo "unknown arm: $ARM" >&2
  exit 2
fi
echo "ARM=$ARM LABEL=$LABEL EXIT=$EXIT OUT=$OUT"
exit 0
