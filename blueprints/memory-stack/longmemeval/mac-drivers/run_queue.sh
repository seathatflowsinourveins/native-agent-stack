#!/bin/zsh
# A13 GPU queue: one GPU workload at a time, in decision order. Replaces run_tail.sh and the C3/C6/C5 chain.
#   C3 → C4 (reranker, idle GPU, embeddings from the cache) → C6 → D3 → quant runs (resumed) → AIPerf → C5
# Every embedding arm goes through the byte-exact cache proxy on 11439 (upstream: embed server 11436).
set -u
B=$HOME/.local/share/agent-ecosystem/bench
L=$B/longmemeval
OLL=$HOME/.local/share/agent-ecosystem/ollama/current/ollama
LMS="/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms"
PROXY=http://127.0.0.1:11439
export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"
log() { print -r -- "$(date +%H:%M:%S) $*"; }
pid_of() { awk '{print $NF}' "$1"; }
unload() {  # $1 = Ollama base URL
  for m in $(curl -s "$1/api/ps" | python3 -c 'import json,sys; print(" ".join(m["name"] for m in json.load(sys.stdin).get("models",[])))'); do
    curl -s "$1/api/generate" -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null
  done
}
bench_ollama() {  # $1 port, $2 parallel, $3 context length, $4 pidfile
  env -i HOME="$HOME/.local/share/agent-ecosystem/ollama/runtime-home" PATH=/usr/bin:/bin OLLAMA_HOST=127.0.0.1:$1 \
    OLLAMA_MODELS="$HOME/.local/share/agent-ecosystem/ollama/models" OLLAMA_NUM_PARALLEL=$2 OLLAMA_KEEP_ALIVE=60m \
    OLLAMA_CONTEXT_LENGTH=$3 OLLAMA_NO_CLOUD=1 OLLAMA_NOHISTORY=1 OLLAMA_MAX_LOADED_MODELS=1 "$OLL" serve > "$4.log" 2>&1 &
  echo "pid $!" > "$4"
  for i in {1..60}; do curl -sf "http://127.0.0.1:$1/api/version" >/dev/null && return 0; sleep 1; done; return 1
}
arm() {  # $1 arm name, then extra VAR=value settings
  local name=$1; shift
  curl -sf --max-time 5 $PROXY/api/version >/dev/null || { log "embed cache proxy is down; queue stopped before $name"; exit 1; }
  log "arm $name: start"
  (cd $L && env LME_EMBED_URL=$PROXY "$@" .venv-official/bin/python lme_harness.py $name) >> $L/logs/queue-$name.log 2>&1
  log "arm $name: exit=$? rows=$(wc -l < $L/results/$name.jsonl | tr -d ' ') errors=$(grep -c '"error": "' $L/results/$name.jsonl)"
}

arm aimem-qwen3

log "C4: reranker LLM on a parallel instance (port 11437)"
bench_ollama 11437 4 4096 $B/ollama-rerank.pid || log "rerank instance failed to start"
arm aimem-qwen3-rerank LME_LLM_URL=http://127.0.0.1:11437
kill "$(pid_of $B/ollama-rerank.pid)" 2>/dev/null

arm aimem-qwen3-0.6b
arm am-qwen3
unload http://127.0.0.1:11436

log "quant: resuming the frozen runs ($(cat $B/quant/frozen.pids))"
for p in $(cat $B/quant/frozen.pids); do kill -CONT $p 2>/dev/null && log "resumed $p"; done
while pgrep -f 'quant/run_quant.sh' >/dev/null; do sleep 60; done
log "quant runs finished; stopping their instance and removing the -eval tags"
kill "$(pid_of $B/quant/ollama-bench/pid)" 2>/dev/null; sleep 5
OLLAMA_HOST=127.0.0.1:11434 "$OLL" rm qwen3.8-27b-4bit-eval qwen3.8-27b-8bit-eval >/dev/null 2>&1
unload http://127.0.0.1:11434

# AIPerf: model-card sampling, thinking on (so outputs reach 256 tokens), cold caches per request.
mkdir -p $B/speed/runs
ap() {  # label url model isl conc seed
  local tag="$1-isl$4-c$5-s$6"
  aiperf profile --model "$3" --url "$2" --endpoint-type chat --streaming --tokenizer Qwen/Qwen3.8-27B --apply-chat-template \
    --isl "$4" --isl-stddev 0 --osl 256 --use-legacy-max-tokens --prompt-corpus coding --random-seed "$6" \
    --cache-bust warmup_isolation_first_turn --warmup-request-count 2 --concurrency "$5" --request-count $((4 * $5)) \
    --extra-inputs '{"temperature":1.0,"top_p":0.95,"top_k":20}' --artifact-dir "$B/speed/runs/$tag" > "$B/speed/runs/$tag.log" 2>&1
  log "aiperf $tag exit=$?"
  sleep 30
}
log "AIPerf: Ollama production instance (4-bit, 8-bit)"
for s in 11 12 13; do ap ollama-4bit http://127.0.0.1:11434 qwen3.8-27b-4bit-64k 8192 1 $s; done
for s in 11 12 13; do ap ollama-4bit http://127.0.0.1:11434 qwen3.8-27b-4bit-64k 32768 1 $s; done
unload http://127.0.0.1:11434
for s in 11 12 13; do ap ollama-8bit http://127.0.0.1:11434 qwen3.8-27b-8bit-64k 8192 1 $s; done
unload http://127.0.0.1:11434

log "AIPerf: Ollama with 4 parallel slots (batch throughput)"
bench_ollama 11438 4 16384 $B/ollama-par.pid
printf 'FROM qwen3.8-27b-4bit-64k\nPARAMETER num_ctx 16384\n' > $B/speed/Modelfile.16k
OLLAMA_HOST=127.0.0.1:11438 "$OLL" create qwen3.8-27b-4bit-16k -f $B/speed/Modelfile.16k >/dev/null 2>&1
for s in 11 12 13; do ap ollama-4bit-par4 http://127.0.0.1:11438 qwen3.8-27b-4bit-16k 8192 4 $s; done
OLLAMA_HOST=127.0.0.1:11438 "$OLL" rm qwen3.8-27b-4bit-16k >/dev/null 2>&1
kill "$(pid_of $B/ollama-par.pid)" 2>/dev/null; sleep 5

log "AIPerf: LM Studio Splash runtime"
"$LMS" server start --port 1234 >/dev/null 2>&1
"$LMS" runtime select splash-mac-arm64-apple-metal-advsimd@0.0.5 >/dev/null 2>&1
if "$LMS" load qwen3.8-27b-splash --context-length 65536 --identifier q38-splash -y >/dev/null 2>&1; then
  for s in 11 12 13; do ap lmstudio-splash http://127.0.0.1:1234 q38-splash 8192 1 $s; done
  for s in 11 12 13; do ap lmstudio-splash http://127.0.0.1:1234 q38-splash 32768 1 $s; done
  "$LMS" unload q38-splash >/dev/null 2>&1
else
  log "LM Studio Splash failed to load"
fi
"$LMS" runtime select mlx-llm-mac-arm64-apple-metal-nax-advsimd@1.11.0 >/dev/null 2>&1
"$LMS" server stop >/dev/null 2>&1

arm aimem-qwen3-8b
unload http://127.0.0.1:11436
log "queue complete"
