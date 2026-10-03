#!/usr/bin/env bash
# A2 of the local-model preregistration (amendment 3b): one run of the function-calling cases through one surface of
# the measurement Ollama server. Runs the evaluation package unchanged; decides nothing. A label that exists is
# refused, so no run is repeated.
# usage: a2_run_bfcl.sh <ollama model> <chat|responses|messages> <limit, e.g. 100 or 101-103> <label>
set -u
MODEL="${1:?model}"; SURFACE="${2:?surface}"; LIMIT="${3:?limit}"; LABEL="${4:?label}"
A="$HOME/measure/a2"; LOG="$A/logs/$LABEL"; BASE=http://127.0.0.1:21434
[ ! -e "$LOG" ] || { echo "label $LABEL already exists"; exit 2; }
mkdir -p "$LOG"
extra=""
case "$SURFACE" in
  chat)      spec="openai-api/ollama/$MODEL"; export OLLAMA_BASE_URL="$BASE/v1"; export OLLAMA_API_KEY=local-placeholder ;;
  responses) spec="openai/$MODEL"; export OPENAI_BASE_URL="$BASE/v1"; export OPENAI_API_KEY=local-placeholder; extra="-M responses_api=true" ;;
  messages)  spec="anthropic/$MODEL"; export ANTHROPIC_BASE_URL="$BASE"; export ANTHROPIC_API_KEY=local-placeholder ;;
  *) echo "unknown surface $SURFACE"; exit 2 ;;
esac
export PATH="/usr/lib/wsl/lib:$PATH" INSPECT_LOG_DIR="$LOG" NO_COLOR=1
{
  echo "label=$LABEL model=$MODEL surface=$SURFACE limit=$LIMIT started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "gpu_before=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
} > "$LOG/run-meta.txt"
start=$SECONDS
# shellcheck disable=SC2086
"$A/venv/bin/inspect" eval inspect_evals/bfcl -T categories=simple_python --model "$spec" $extra \
  --sample-shuffle 20260927 --limit "$LIMIT" --max-tokens 16384 --reasoning-effort medium \
  --max-connections 1 --max-retries 0 --no-fail-on-error --timeout 900 --log-dir "$LOG" --display plain \
  > "$LOG/inspect-stdout.txt" 2> "$LOG/inspect-stderr.txt"
rc=$?
{
  echo "inspect_exit=$rc seconds=$((SECONDS - start)) finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "gpu_after=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  echo "resident=$(curl -fsS -m 10 $BASE/api/ps | python3 -c 'import json,sys; print([(m["name"], m.get("size"), m.get("size_vram"), m.get("context_length")) for m in json.load(sys.stdin).get("models", [])])')"
} >> "$LOG/run-meta.txt"
cat "$LOG/run-meta.txt"
tail -n 12 "$LOG/inspect-stdout.txt" | cut -c1-200
[ $rc -eq 0 ] || tail -n 6 "$LOG/inspect-stderr.txt" | cut -c1-300
"$A/venv/bin/python" -B "$A/harness/a2_validity.py" "$LOG" > "$LOG/validity.jsonl" 2> "$LOG/validity.err"; echo "validity exit $?"
tail -n 1 "$LOG/validity.jsonl" | cut -c1-400
