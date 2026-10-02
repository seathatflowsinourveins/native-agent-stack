#!/usr/bin/env bash
# One run of the gate: start one server, wait until it is ready, run the fixed Codex task once,
# stop the server, score the event log with the frozen pass rule.
# usage: gate_run.sh <llama|ollama> <label>      label: warmup-A, warmup-B, A1, B1, A2, B2, A3, B3
# Local wrapper, not an upstream component.
source "$(dirname "${BASH_SOURCE[0]}")/gate_env.sh"
ARM="$1"; LABEL="$2"
RUN="$S/runs/$LABEL"; PIDFILE="$S/runs/pids.tsv"
if [ -e "$RUN/events.jsonl" ]; then echo "run $LABEL already exists" >&2; exit 2; fi
mkdir -p "$RUN"
case "$ARM" in
  llama)  PROFILE=llamacpp-gate; READY="http://127.0.0.1:$PORT_LLAMA/health";       start_llama "$RUN/server.log" ;;
  ollama) PROFILE=ollama-launch; READY="http://127.0.0.1:$PORT_OLLAMA/api/version"; start_ollama "$RUN/server.log" ;;
  *) echo "unknown arm $ARM" >&2; exit 2 ;;
esac
PID=$SERVER_PID
META="$RUN/run-meta.txt"
{ echo "label=$LABEL"; echo "arm=$ARM"; echo "profile=$PROFILE"; echo "server_pid=$PID"; echo "server_started_utc=$(utc)"; } >"$META"
if ! wait_ready "$READY" "$PID"; then
  echo "server_ready=no" >>"$META"; echo "codex_exit=not-run" >>"$META"
  stop_server "$PID" "$PIDFILE" "$LABEL" "$ARM-server"
  exit 3
fi
echo "server_ready_utc=$(utc)" >>"$META"
set +e
( cd "$S/work" && hermetic OPENAI_API_KEY=ollama timeout --signal=TERM --kill-after=20 "$RUN_TIMEOUT_SEC" \
    "$CODEX_BIN" exec --profile "$PROFILE" --json --skip-git-repo-check -C "$S/work" \
    -o "$RUN/last-message.txt" "$PROMPT" </dev/null >"$RUN/events.jsonl" 2>"$RUN/codex-stderr.txt" )
RC=$?
set -e
echo "codex_exit=$RC" >>"$META"; echo "codex_finished_utc=$(utc)" >>"$META"
stop_server "$PID" "$PIDFILE" "$LABEL" "$ARM-server"
echo "server_stopped_utc=$(utc)" >>"$META"
echo "server_alive_after_stop=$(kill -0 "$PID" 2>/dev/null && echo yes || echo no)" >>"$META"
python3 "$HERE/gate_score.py" "$RUN/events.jsonl" "$RC" >"$RUN/score.json"
cat "$META"; cat "$RUN/score.json"
