#!/usr/bin/env bash
# Common settings for the local model server gate (2026-10-01). Local wrapper, not an upstream component.
# Sourced by gate_setup.sh and gate_run.sh. GATE_STATE names the owned state directory (mode 0700,
# outside every checkout) that holds the downloads, the two servers, the model and the scratch home.
set -euo pipefail
: "${GATE_STATE:?set GATE_STATE to the owned state directory}"
S="$GATE_STATE"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PORT_LLAMA=20231
PORT_OLLAMA=20232
MODEL_ALIAS=gate-qwen3-8b
GGUF="$S/models/Qwen3-8B-Q4_K_M.gguf"
CTX=32768
LLAMA_BIN="$S/llama/llama-b11146/llama-server"
OLLAMA_BIN="$S/ollama/bin/ollama"
CODEX_BIN="$S/bin/codex"            # symlink to the unchanged upstream codex 0.159.3 binary
RUN_TIMEOUT_SEC=1200
SCRATCH_HOME="$S/scratch-home"   # HOME of every gate process; holds .codex and .ollama
READY_TIMEOUT_SEC=180

# The one fixed prompt (frozen in PREREGISTRATION.md).
PROMPT='Use the MCP tool get_current_time from the MCP server named time, with the argument timezone set to "UTC". Do not run any shell command. After the tool returns, reply with exactly the datetime value it returned and nothing else.'

# Every process of the gate runs in an emptied environment: no inherited variable reaches a server,
# the client or the MCP server. HOME and CODEX_HOME point into the state directory; logs are in UTC.
HERMETIC=(env -i PATH="$S/bin:/usr/bin:/bin" HOME="$SCRATCH_HOME" CODEX_HOME="$SCRATCH_HOME/.codex" LANG=C.UTF-8 TZ=UTC)
OLLAMA_ENV=(CUDA_VISIBLE_DEVICES=-1 OLLAMA_HOST="127.0.0.1:$PORT_OLLAMA" OLLAMA_MODELS="$S/ollama-models" OLLAMA_NO_CLOUD=1
  OLLAMA_CONTEXT_LENGTH="$CTX" OLLAMA_NUM_PARALLEL=1 OLLAMA_DEBUG=1)
hermetic() { "${HERMETIC[@]}" "$@"; }
ollama_env() { "${HERMETIC[@]}" "${OLLAMA_ENV[@]}" "$@"; }

utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

port_is_free() { ! ss -ltnH "sport = :$1" | grep -q .; }

# Both servers run on the CPU only (CUDA_VISIBLE_DEVICES=-1; llama-server also gets --device none -ngl 0):
# on this workstation GPU allocations beyond about 4.5 GiB failed although 16 GiB was reported free.
# The servers are started as simple commands (not through a shell function) so that $! is the server itself.
# start_llama LOGFILE -> sets SERVER_PID
start_llama() {
  port_is_free "$PORT_LLAMA" || { echo "port $PORT_LLAMA is in use" >&2; return 1; }
  "${HERMETIC[@]}" CUDA_VISIBLE_DEVICES=-1 "$LLAMA_BIN" -m "$GGUF" --alias "$MODEL_ALIAS" --host 127.0.0.1 --port "$PORT_LLAMA" \
    -c "$CTX" -np 1 --device none -ngl 0 --jinja --temp 0.6 --top-k 20 --top-p 0.95 --repeat-penalty 1.0 --verbose \
    >"$1" 2>&1 &
  SERVER_PID=$!
}

# start_ollama LOGFILE -> sets SERVER_PID
start_ollama() {
  port_is_free "$PORT_OLLAMA" || { echo "port $PORT_OLLAMA is in use" >&2; return 1; }
  "${HERMETIC[@]}" "${OLLAMA_ENV[@]}" "$OLLAMA_BIN" serve >"$1" 2>&1 &
  SERVER_PID=$!
}

# wait_ready URL PID
wait_ready() {
  local deadline=$((SECONDS + READY_TIMEOUT_SEC))
  while (( SECONDS < deadline )); do
    kill -0 "$2" 2>/dev/null || { echo "server pid $2 exited before it was ready" >&2; return 1; }
    if curl -fsS -m 3 -o /dev/null "$1" 2>/dev/null; then return 0; fi
    sleep 1
  done
  echo "server pid $2 not ready after ${READY_TIMEOUT_SEC}s" >&2
  return 1
}

# stop_server PID PIDFILE LABEL ROLE: stops only the process this script started, and its children.
stop_server() {
  local pid="$1" pidfile="$2" label="$3" role="$4" kids k
  kids="$(pgrep -P "$pid" || true)"
  printf '%s\t%s\t%s\t%s\n' "$label" "$role" "$pid" "$(echo $kids | tr ' ' ',')" >>"$pidfile"
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  if kill -0 "$pid" 2>/dev/null; then kill -KILL "$pid" 2>/dev/null || true; sleep 1; fi
  wait "$pid" 2>/dev/null || true
  for k in $kids; do
    for _ in $(seq 1 15); do kill -0 "$k" 2>/dev/null || break; sleep 1; done
    if kill -0 "$k" 2>/dev/null; then kill -KILL "$k" 2>/dev/null || true; fi
  done
}

gpu_used_mib() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 || echo unknown; }
