#!/usr/bin/env bash
# The LongMemEval-S lane on VelaNext (PREREGISTRATION.md A15-A16.3). Run setup_velanext.sh first.
#
#   bash evals/longmemeval/run_velanext.sh [options] COMMAND
#   COMMAND: gates | cpu | mteb | arms | a16 | x | amb | pooled | report | collect | status | all
#     gates    the oracle ceilings, the v4-v3 equivalence check, the agentmemory slot smoke, the embedding
#              servers' reference-output and batch-invariance gates, the A13 cache self-test, the reranker LLM smoke,
#              the A16 smoke; writes logs/gates/passed.json. Every other stage that runs an arm needs it.
#     cpu      the CPU-only arms (A0, B1, C1, C2, D1, D2, D2h, M2) and the vendors' own harnesses (with M1)
#     mteb     upstream mteb on LMEB's LongMemEval task for every embedder (first-line; decides nothing; offline)
#     arms     the GPU arms in A15's order, one GPU workload at a time
#     a16      K1 (Hindsight 0.10.1 with the H1 build's LLM) on its preregistered subset (A16, A16.1)
#     x        the exploratory cross-encoder stage over the best arm's top 50
#     amb      Hindsight's own agent-memory-benchmark, unmodified, on K1's subset (A16 diagnostic)
#     pooled   the pooled-store stress run for the top two systems (A16.1 rule; diagnostic, runs last)
#     report   the summarizer (confirmatory, after the gates), the mteb table and the vendor comparison
#     collect  sanitize rows, report, gate results, cache statistics, GPU and CPU logs and the receipt into the
#              repository (nothing is written there if anything private is found)
#     status   every expected arm: rows, errors, stop conditions (MISSING when absent)
#     all      gates; the cpu stream as its own process beside mteb and arms 2-4; the stream joined before H1, H2 and
#              K1; then a16, x, amb, report, collect, pooled, and the final report and collect
#   options: --aimem-workers 16 --rerank-workers 3 --am-slots 8 --dense-batch 64 --llama-slots 16
#            --llama-ubatch 8192 --mp-workers 16 --k1-workers 4 --continue-after-fallback --mteb-after
#            --final (with report: the operator declares the queue finished; A16.3)
#
# Everything lives under the lane's own prefix, $LME_BENCH_ROOT (default ~/.local/share/lme-bench), never in the
# workstation's production layout (review pins P3, lane F8). Every embedding request goes through the A13 byte-exact
# cache (embed_cache_proxy.py, fingerprinted by upstream and device), which serves byte-identical repeats only.
# GGUF embedders are served by llama.cpp's llama-server behind gguf_embed_front.py (A15.1); BF16 references by
# embed_server_st.py. A16.3: C4, F and H compute their own embeddings on the same GPU server as their reference arm,
# and the reranker LLM shares the GPU, offloading what does not fit. Reranker LLMs run on Ollama, except H1 and H2
# (and K1's LLM, the H1 build), which run on llama-server with MoE expert offload; their placement is recorded.
# One GPU workload at a time: GPU stages hold a host lock, check that the GPU is idle before each workload, and stop
# their services on exit. The CPU stream never overlaps H1, H2 or K1 (their experts use the host's CPU and RAM).
# Stop conditions (LANE.md): any gate failure, env errors, more than 1% infra or unclassified errors, more than 1%
# of questions with failed memory operations (K1), and more than 5% rerank fallbacks for C4, F or H (A12, A15.2,
# A16.2; --continue-after-fallback overrides only the last). The per-arm thresholds are checked when an arm ends.
set -euo pipefail

LANE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$LANE/../.." && pwd)"
pin() { python3 -c "import json,sys; v=json.load(open(sys.argv[1]))
for k in sys.argv[2].split('.'): v=v[int(k)] if k.isdigit() else v[k]
print(v)" "$LANE/pins.json" "$1"; }
LB="${LME_BENCH_ROOT:-$HOME/.local/share/lme-bench}"
LME_HOME="$LB/longmemeval"
TOOLS="$LB/tools"
SRC="$LB/src"
RES="$LME_HOME/results-velanext"
LOGS="$LME_HOME/logs"
OFF="$LME_HOME/official-logs-velanext"
PY_OFF="$LME_HOME/.venv-official/bin/python"
PY_EMB="$LME_HOME/.venv-embed/bin/python"
OLL="$LB/ollama/v$(pin ollama.version)/bin/ollama"
OLL_HOME="$LB/ollama/runtime-home"
LLAMA="$TOOLS/llama.cpp-$(pin llama_cpp.build)"
NODE_BIN="$TOOLS/node-v$(pin node.version)/bin"
AIMEM_DIR="$TOOLS/ai-memory-$(pin ai_memory.workspace_version)+$(pin ai_memory.commit | cut -c1-7)"
AM_ROOT="$LB/agentmemory"
OFFICIAL="$SRC/LongMemEval"
AMREPO="$SRC/agentmemory-v$(pin agentmemory.version)"
MPREPO="$SRC/mempalace-v$(pin mempalace.version)"
AMBREPO="$SRC/agent-memory-benchmark"
K1_SUBSET="$LANE/k1-subset.json"
P_PROXY=11439 P_EMBED=11436 P_LLAMA=11440 P_LLM=11437 P_HS=11441
AIMEM_WORKERS=16 RERANK_WORKERS=3 AM_SLOTS=8 DENSE_BATCH=64 LLAMA_NP=16 LLAMA_UBATCH=8192 MP_WORKERS=16 K1_WORKERS=4
LLM_NP=4  # parallel requests per reranker LLM, as OLLAMA_NUM_PARALLEL
H1_BUILD=qwen3.6-35b-a3b-64k  # A16: K1's LLM
GPU_IDLE_MIB="${LME_GPU_IDLE_MIB:-2048}" GPU_IDLE_UTIL="${LME_GPU_IDLE_UTIL:-10}"
LLM_RAM_HEADROOM_GIB="${LME_LLM_RAM_HEADROOM_GIB:-16}"
CONTINUE_AFTER_FALLBACK=0 MTEB_AFTER=0 FINAL=0
cpu_pid="" CMD=""
EMBED_SHARED_NP=4  # embedding slots while a reranker LLM shares the GPU (A16.3)
OPTS=()

export LME_HOME LME_BENCH_ROOT="$LB" LME_DATA="$LME_HOME/data/longmemeval_s_cleaned.json" LME_OFFICIAL_DIR="$OFFICIAL"
export LME_NODE="$NODE_BIN/node" LME_AIMEM_BIN="$AIMEM_DIR/ai-memory" LME_AM_ROOT="$AM_ROOT" LME_III_BIN="$AM_ROOT/bin/iii"
export LME_MINILM_DIR="$LME_HOME/models/all-MiniLM-L6-v2" LME_AM_SLOT_POOL=16
export LME_EMBED_URL="http://127.0.0.1:$P_PROXY" LME_EMBED_UPSTREAM="http://127.0.0.1:$P_EMBED" LME_LLM_URL="http://127.0.0.1:$P_LLM"
export HF_HOME="$LME_HOME/hf-home" OLLAMA_MODELS="$LB/ollama/models" PATH="$NODE_BIN:$PATH"
export LME_MEMPALACE_VENV="$LME_HOME/.venv-mempalace" LME_MEMPALACE_ONNX="$LME_HOME/models/chroma-onnx/all-MiniLM-L6-v2"
export LME_HINDSIGHT_URL="http://127.0.0.1:$P_HS"
mkdir -p "$RES" "$LOGS"/{gates,cache,ollama,pids,arms} "$OFF" "$LME_HOME/vendor"

log() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOGS/run.log" >&2; }
die() { log "STOP: $*"; exit 1; }
slug() { printf '%s' "$1" | tr '/:' '__'; }

# ---------------------------------------------------------------- owned background services (review, lane F4)
# A pid file holds "PID TICKS BOOT EXE": the start time in clock ticks since boot (/proc/<pid>/stat field 22, which a
# wall-clock step cannot change), the boot id, and the executable the command ends in. A pid is signalled only while
# it still has that identity, so a stale file (after a crash, a reboot or a clock step) never reaches a reused pid.
# Each invocation stops only the names it started (OWNED). Background processes never inherit the GPU lock (fd 9).
OWNED=()
LAUNCHERS=" nohup env setsid bash sh "
proc_ticks() {  # the start time in ticks (Linux); ps's lstart where there is no /proc (the unit tests on macOS)
  if [ -r "/proc/$1/stat" ]; then sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | cut -d' ' -f20
  else ps -o lstart= -p "$1" 2>/dev/null | tr -s ' ' | sed 's/^ //; s/ $//' | tr ' ' '_'; fi
}
boot_id() { cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo none; }
proc_exe() { readlink "/proc/$1/exe" 2>/dev/null || ps -o comm= -p "$1" 2>/dev/null || true; }
exe_of() {  # the executable a command line ends in, past `env`, its options and VAR=value assignments; a script
  local w f line words=()   # (a console entry point) resolves to its interpreter, as /proc/<pid>/exe shows
  for w in "$@"; do
    case "$w" in env|-i|*=*) continue ;; esac
    f=$(readlink -f "$(command -v "$w" 2>/dev/null || echo "$w")" 2>/dev/null || echo "$w")
    if [ -f "$f" ] && [ "$(head -c 2 "$f" 2>/dev/null)" = "#!" ]; then
      read -r line < "$f"
      read -r -a words <<< "${line#\#!}"
      if [ "$(basename "${words[0]}")" = env ]; then words=("${words[@]:1}"); fi
      f=$(readlink -f "$(command -v "${words[0]}" 2>/dev/null || echo "${words[0]}")" 2>/dev/null || echo "${words[0]}")
    fi
    echo "$f"
    return 0
  done
}
pid_record() {  # pid_record NAME PID EXE: write the pid file and own the name
  echo "$2 $(proc_ticks "$2") $(boot_id) $3" > "$LOGS/pids/$1.pid"
  OWNED+=("$1")
}
same_process() {  # same_process PID TICKS BOOT EXE: is the pid still that process (still exec'ing counts)?
  local now
  [ -n "$2" ] && [ "$(proc_ticks "$1")" = "$2" ] && [ "$(boot_id)" = "$3" ] || return 1
  now=$(proc_exe "$1")
  [ -z "$4" ] || [ "$now" = "$4" ] || [ "$(basename "$now")" = "$(basename "$4")" ] \
    || case "$LAUNCHERS" in *" $(basename "$now") "*) return 0 ;; *) return 1 ;; esac
}
start_bg() {  # start_bg NAME CMD...: a background service with its own log and pid file
  local name="$1"; shift
  nohup "$@" > "$LOGS/$name.log" 2>&1 9>&- &
  pid_record "$name" "$!" "$(exe_of "$@")"
}
owned_pid() {  # owned_pid NAME: print the pid when it is still the process that was launched; drop a stale file
  local f="$LOGS/pids/$1.pid" pid ticks boot exe
  [ -f "$f" ] || return 1
  read -r pid ticks boot exe < "$f" || true
  if [ -n "${pid:-}" ] && same_process "$pid" "${ticks:-}" "${boot:-}" "${exe:-}"; then
    echo "$pid"
    return 0
  fi
  log "stale pid file $1 (the process is gone or the pid was reused); not signalling it"
  rm -f "$f"
  return 1
}
stop_bg() {  # stop_bg NAME [group]: group signals the whole process group the pid leads (the CPU stream)
  local pid ticks boot exe target
  pid=$(owned_pid "$1") || return 0
  read -r _ ticks boot exe < "$LOGS/pids/$1.pid" || true
  target="$pid"; [ "${2:-}" = group ] && target="-$pid"
  kill -TERM -- "$target" 2>/dev/null || true
  for _ in $(seq 40); do same_process "$pid" "$ticks" "$boot" "$exe" || break; sleep 0.5; done
  if same_process "$pid" "$ticks" "$boot" "$exe"; then kill -9 -- "$target" 2>/dev/null || true; fi
  if [ "${2:-}" = group ]; then  # the leader may be gone while its group lives on
    kill -TERM -- "-$pid" 2>/dev/null || true
    sleep 1
    kill -9 -- "-$pid" 2>/dev/null || true
  fi
  rm -f "$LOGS/pids/$1.pid"
}
wait_http() {  # wait_http URL SECONDS [NAME]: NAME's process must be alive before any answer counts
  local url="$1" secs="$2" name="${3:-}"
  for _ in $(seq "$secs"); do
    if [ -n "$name" ] && ! owned_pid "$name" >/dev/null 2>&1; then return 1; fi
    curl -sf --max-time 5 "$url" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

# ---------------------------------------------------------------- one GPU workload at a time (review, lane F3)
gpu_guard() {  # hold the host-wide GPU lock for this invocation; stop what this invocation started on exit
  exec 9> "$LOGS/pids/gpu.lock"
  flock -n 9 || die "another GPU stage holds the lock ($(cat "$LOGS/pids/gpu.holder" 2>/dev/null)); run GPU stages one at a time"
  echo "pid $$ stage $CMD since $(date -Is)" > "$LOGS/pids/gpu.holder"
  trap cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
}
cleanup() {  # the CPU stream first, as a whole process group, and only if this invocation started it; then own names
  local name
  if [ -n "$cpu_pid" ]; then stop_bg cpu-stream group; cpu_pid=""; fi
  for name in "${OWNED[@]+"${OWNED[@]}"}"; do
    [ "$name" = cpu-stream ] && continue
    stop_bg "$name"
  done
  OWNED=()
  rm -f "$LOGS/pids/gpu.holder"
}
gpu_idle() {  # gpu_idle WHAT: stop unless the GPU is idle (the owner has drained other inference services)
  local used util busy=0 sample
  for sample in 1 2 3; do
    IFS=', ' read -r used util < <(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits | head -1)
    case "${used:-x}${util:-x}" in
      *[!0-9]*) die "cannot read the GPU's state before $1 (nvidia-smi said '${used:-} ${util:-}'); check the driver" ;;
    esac
    if [ "$used" -gt "$GPU_IDLE_MIB" ] || [ "$util" -gt "$GPU_IDLE_UTIL" ]; then busy=$((busy + 1)); fi
    [ "$sample" = 3 ] || sleep 1
  done
  [ -f "$LOGS/gates/gpu-baseline.json" ] || printf '{"memory_used_mib": %s, "utilization": %s, "at": "%s"}\n' \
    "$used" "$util" "$(date -Is)" > "$LOGS/gates/gpu-baseline.json"
  [ "$busy" -lt 3 ] || die "the GPU is busy before $1 (${used} MiB used, ${util}% utilization; limits ${GPU_IDLE_MIB} MiB and \
${GPU_IDLE_UTIL}%): drain other inference services first (docs/vela-workstation.md)"
}
gpu_begin() { hs_down; llm_down; embed_down; gpu_idle "$1"; }

# ---------------------------------------------------------------- the CPU stream, its own process (review, lane F6)
cpu_alive() { owned_pid cpu-stream >/dev/null 2>&1; }
cpu_check() {  # between GPU arms: a stopped CPU stream stops the run at the next arm boundary
  [ -z "$cpu_pid" ] && return 0
  if ! kill -0 "$cpu_pid" 2>/dev/null; then
    local rc=0
    wait "$cpu_pid" || rc=$?
    cpu_pid=""
    [ "$rc" = 0 ] || die "the CPU stream stopped (exit $rc; logs/cpu-stream.log)"
  fi
}
cpu_join() {  # before H1, H2 and K1: their MoE experts run on the host's CPU and RAM (review, infra F8)
  if [ -n "$cpu_pid" ]; then
    log "waiting for the CPU stream before the CPU-offloaded LLM arms"
    local rc=0
    wait "$cpu_pid" || rc=$?
    cpu_pid=""
    rm -f "$LOGS/pids/cpu-stream.pid"
    [ "$rc" = 0 ] || die "the CPU stream stopped (exit $rc; logs/cpu-stream.log)"
  elif cpu_alive; then
    die "the cpu stage is running: H1, H2 and K1 never overlap it (wait for it to finish)"
  fi
}
require_gates() {  # A15.2: v4 reproduces v3 and the oracles pass before any arm, in every ordering (review P6)
  "$PY_OFF" "$LANE/lane_tools.py" gates-check "$LOGS/gates" > /dev/null \
    || die "the gates have not passed (run: run_velanext.sh gates); no arm runs before them"
  [ -f "$LOGS/gates/passed.json" ] || die "the gates did not finish (logs/gates/passed.json is missing)"
}

# ---------------------------------------------------------------- GPU and CPU sampling (A15.1; review, lane F7)
gpu_start() {  # appended per segment, with the date, so a resumed arm keeps every segment
  printf '# segment %s\n' "$(date -Is)" >> "$LOGS/gpu-$1.log"
  if timeout 15 nvidia-smi dmon -s u -d 1 -c 1 >/dev/null 2>&1; then
    nohup nvidia-smi dmon -s u -d 5 -o DT >> "$LOGS/gpu-$1.log" 2>&1 9>&- &
  else  # WSL builds without dmon: the same utilization through the query interface
    nohup nvidia-smi --query-gpu=timestamp,utilization.gpu,utilization.memory,memory.used --format=csv,noheader -l 5 \
      >> "$LOGS/gpu-$1.log" 2>&1 9>&- &
  fi
  pid_record "gpu-$1" "$!" "$(exe_of nvidia-smi)"
}
gpu_stop() { stop_bg "gpu-$1"; }
cpu_sample_start() {  # load average and available memory every 5 s (review, infra F8), as load-<name>
  printf '# segment %s\n' "$(date -Is)" >> "$LOGS/load-$1.log"
  # shellcheck disable=SC2016  # expanded by the sampler's own shell
  nohup bash -c 'while :; do printf "%s %s %s\n" "$(date -Is)" "$(cut -d" " -f1-3 /proc/loadavg)" \
    "$(awk "/MemAvailable/ {print \$2}" /proc/meminfo)"; sleep 5; done' >> "$LOGS/load-$1.log" 2>&1 9>&- &
  pid_record "load-$1" "$!" "$(exe_of bash)"
}
cpu_sample_stop() { stop_bg "load-$1"; }

# ---------------------------------------------------------------- embedding servers, always behind the A13 proxy
embed_down() { stop_bg proxy; stop_bg front; stop_bg st; stop_bg llama; sleep 1; }
gguf_single() {  # exit 0 when the model's batch-invariance gate failed, so it runs single-sequence (A15.1)
  local report
  report="$LOGS/gates/gguf-$(slug "$1").json"
  [ -f "$report" ] && ! python3 -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))['batch_invariance']['pass'] else 1)" "$report"
}
gguf_up() {  # gguf_up MODEL [selftest|shared]: shared leaves room for a reranker LLM on the same GPU (A16.3)
  local model="$1" blob np="$LLAMA_NP" single=()
  embed_down
  blob=$("$PY_OFF" "$LANE/lane_tools.py" gguf-blob "$OLLAMA_MODELS" "$model")
  [ "${2:-}" = shared ] && np="$EMBED_SHARED_NP"
  if gguf_single "$model"; then single=(--single-sequence); np=1; fi
  start_bg llama env LD_LIBRARY_PATH="$(cat "$LLAMA/LD_LIBRARY_PATH")" "$LLAMA/llama-server" -m "$blob" --embeddings \
    --pooling last -np "$np" -c $((np * 4608)) --no-kv-unified -b "$LLAMA_UBATCH" -ub "$LLAMA_UBATCH" -ngl all -fa on \
    --no-cache-prompt --cache-ram 0 --no-webui --host 127.0.0.1 --port "$P_LLAMA"
  wait_http "http://127.0.0.1:$P_LLAMA/health" 600 llama || die "llama-server did not start for $model (logs/llama.log)"
  if [ "${2:-}" = selftest ]; then
    (cd "$LANE" && "$PY_OFF" gguf_embed_front.py --upstream "http://127.0.0.1:$P_LLAMA" --name "$model" --selftest \
      --gate-report "$LOGS/gates/gguf-$(slug "$model").json" --log "$LOGS/front-selftest.log") || true
    return 0
  fi
  start_bg front "$PY_OFF" "$LANE/gguf_embed_front.py" --upstream "http://127.0.0.1:$P_LLAMA" --port "$P_EMBED" --name "$model" \
    "${single[@]}" --log "$LOGS/front-requests.log"
  wait_http "http://127.0.0.1:$P_EMBED/api/version" 120 front || die "gguf_embed_front did not start for $model"
  IDENTITY="llama.cpp $(pin llama_cpp.release) ($(pin llama_cpp.build)) | $model | GGUF $(basename "$blob") | pooling last | cap 4096 | device cuda"
  CANARY_MODEL="$model"
}
st_batch_tokens() { case "$1" in *8B*) echo 16384 ;; *4B*) echo 32768 ;; *) echo 65536 ;; esac; }
st_up() {  # st_up REPO REVISION [selftest|shared]: shared uses a quarter of the batch budget (A16.3)
  local repo="$1" rev="$2" report tokens
  embed_down
  tokens=$(st_batch_tokens "$repo")
  [ "${3:-}" = shared ] && tokens=$((tokens / 4))
  if [ "${3:-}" = selftest ]; then
    HF_HUB_OFFLINE=1 "$PY_EMB" "$LANE/embed_server_st.py" --model "$repo" --revision "$rev" --device cuda \
      --batch-tokens "$(st_batch_tokens "$repo")" --gate-report "$LOGS/gates/st-$(slug "$repo").json" --selftest \
      --log "$LOGS/st-selftest.log"
    return $?
  fi
  report="$LOGS/gates/st-$(slug "$repo")-cuda-$(date +%Y%m%dT%H%M%S).json"
  start_bg st env HF_HUB_OFFLINE=1 "$PY_EMB" "$LANE/embed_server_st.py" --model "$repo" --revision "$rev" --port "$P_EMBED" \
    --device cuda --batch-tokens "$tokens" --gate-report "$report" --log "$LOGS/st-requests.log"
  wait_http "http://127.0.0.1:$P_EMBED/health" 3600 st || die "embed_server_st stopped for $repo (a reference gate failure exits 3; logs/st.log)"
  IDENTITY="embed_server_st lane-v4 | $repo@$rev | bfloat16 sdpa | normalized | cap 4096 | device cuda"
  CANARY_MODEL="$repo"
}
proxy_free() {  # nothing may answer on the proxy port before a new proxy starts (review, infra F2)
  stop_bg proxy
  ! curl -sf --max-time 2 "http://127.0.0.1:$P_PROXY/__stats" >/dev/null 2>&1 \
    || die "port $P_PROXY already has a listener that this run did not start (a stale embed_cache_proxy?)"
}
proxy_verify() {  # the answering proxy is the one just started: its /__stats names the database its log names
  local db
  db=$(sed -n 's/.*; db \(.*\)$/\1/p' "$LOGS/proxy.log" | tail -1)
  curl -sf "http://127.0.0.1:$P_PROXY/__stats" | python3 -c "import json,sys,os; s=json.load(sys.stdin)
sys.exit(0 if s['db'] == os.path.basename(sys.argv[1]) else 1)" "$db" || die "the proxy answering on $P_PROXY is not the one just started"
}
proxy_up() {  # proxy_up ARM: the fingerprinted cache in front of the embedding server that is up
  proxy_free
  start_bg proxy "$PY_OFF" "$LANE/embed_cache_proxy.py" "http://127.0.0.1:$P_EMBED" "$P_PROXY" "$LME_HOME/cache/proxy" \
    --identity "$IDENTITY" --canary-model "$CANARY_MODEL" --stats "$LOGS/cache/$1.stats.json"
  wait_http "http://127.0.0.1:$P_PROXY/__stats" 300 proxy || die "the cache proxy refused its database or upstream (logs/proxy.log)"
  proxy_verify
}
# ---------------------------------------------------------------- reranker LLMs (A12, A15.2, A16)
llm_down() { stop_bg ollama-llm; stop_bg llama-llm; sleep 1; }
llama_llm_base() {  # the pinned Ollama model whose GGUF a llama-served tag uses; empty for Ollama-served tags
  case "$1" in
    qwen3.6-35b-a3b-64k) echo qwen3.6:35b-a3b ;;
    nemotron-3.5-lightning-30b-a3b-64k) echo nemotron-3.5-lightning:30b-a3b ;;
    *) echo "" ;;
  esac
}
llama_llm_up() {  # llama_llm_up TAG LABEL: H1, H2 and K1's LLM on llama-server with MoE expert offload
  local tag="$1" label="$2" base blob ctx rest sampling=() rec
  cpu_join
  base=$(llama_llm_base "$tag")
  blob=$("$PY_OFF" "$LANE/lane_tools.py" gguf-blob "$OLLAMA_MODELS" "$base")
  rec="$LOGS/ollama/$(slug "$tag").$label"
  "$PY_OFF" "$LANE/lane_tools.py" ram-check "$blob" --headroom-gib "$LLM_RAM_HEADROOM_GIB" > "$rec.ram.json" \
    || die "the WSL VM has too little memory for $tag with CPU-offloaded experts ($rec.ram.json); raise memory= in .wslconfig"
  read -r ctx rest < <("$PY_OFF" "$LANE/lane_tools.py" modelfile-args "$LANE/ollama/$tag.Modelfile")
  read -r -a sampling <<< "$rest"
  # --fit on with the context fixed: llama.cpp keeps num_ctx per slot and moves MoE expert tensors to the CPU until
  # the rest fits in VRAM (common/fit.cpp); the Modelfile's sampling are the server defaults, as in Ollama.
  start_bg llama-llm env LD_LIBRARY_PATH="$(cat "$LLAMA/LD_LIBRARY_PATH")" "$LLAMA/llama-server" -m "$blob" --alias "$tag" \
    --jinja -np "$LLM_NP" -c $((LLM_NP * ctx)) --no-kv-unified -fa on --fit on "${sampling[@]}" \
    --no-webui --host 127.0.0.1 --port "$P_LLM"
  wait_http "http://127.0.0.1:$P_LLM/health" 1800 llama-llm || die "llama-server could not load $tag (logs/llama-llm.log)"
  curl -sf "http://127.0.0.1:$P_LLM/props" > "$rec.props" || true
  "$PY_OFF" "$LANE/lane_tools.py" llama-placement "$LOGS/llama-llm.log" --props "$rec.props" --tag "$tag" > "$rec.json"
  rm -f "$rec.props"
}
OLLAMA_CHECKED=0
llm_up() {  # llm_up TAG LABEL: the reranker LLM, production parameters (A15.2); it shares the GPU with the embedder (A16.3)
  local tag="$1" label="${2:-smoke}"
  llm_down
  if [ -n "$(llama_llm_base "$tag")" ]; then llama_llm_up "$tag" "$label"; return 0; fi
  if [ "$OLLAMA_CHECKED" = 0 ]; then  # the pinned binary, built from the pinned commit (review pins P3)
    "$PY_OFF" "$LANE/lane_tools.py" ollama-check "$OLL" > "$LOGS/gates/ollama-binary.json" \
      || die "the Ollama binary is not the pinned one ($LOGS/gates/ollama-binary.json)"
    OLLAMA_CHECKED=1
  fi
  mkdir -p "$OLL_HOME"
  start_bg ollama-llm env -i HOME="$OLL_HOME" PATH=/usr/bin:/bin OLLAMA_HOST="127.0.0.1:$P_LLM" \
    OLLAMA_MODELS="$OLLAMA_MODELS" OLLAMA_NUM_PARALLEL="$LLM_NP" OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=60m \
    OLLAMA_CONTEXT_LENGTH=4096 OLLAMA_NO_CLOUD=1 OLLAMA_NOHISTORY=1 "$OLL" serve
  wait_http "http://127.0.0.1:$P_LLM/api/version" 120 ollama-llm || die "Ollama did not start"
  curl -sf "http://127.0.0.1:$P_LLM/api/generate" -d "{\"model\":\"$tag\",\"prompt\":\"ok\",\"stream\":false,\"options\":{\"num_predict\":1}}" \
    >/dev/null || die "Ollama could not load $tag"
  {  # A15.2: the effective context and parameters, and the template's digest (review pins P5)
    printf '{"tag": "%s", "label": "%s", "version": ' "$tag" "$label"; curl -sf "http://127.0.0.1:$P_LLM/api/version"
    printf ', "ps": '; curl -sf "http://127.0.0.1:$P_LLM/api/ps"
    printf ', "show": '; curl -sf "http://127.0.0.1:$P_LLM/api/show" -d "{\"model\":\"$tag\"}" | python3 -c \
      "import hashlib,json,sys; d=json.load(sys.stdin); out={k: d.get(k) for k in ('parameters', 'details', 'capabilities', 'modified_at')}
out['template_sha256'] = hashlib.sha256((d.get('template') or '').encode()).hexdigest(); print(json.dumps(out))"
    printf '}\n'
  } > "$LOGS/ollama/$(slug "$tag").$label.json"
}

# ---------------------------------------------------------------- Hindsight 0.10.1 (A16 K1)
hs_down() { stop_bg hindsight; }
hs_up() {  # the API server on its embedded PostgreSQL; local embedder and reranker on the CPU; LLM = the H1 build
  hs_down
  cpu_join
  mkdir -p "$LME_HOME/hindsight-home"
  start_bg hindsight env -i HOME="$LME_HOME/hindsight-home" PATH="$LME_HOME/.venv-hindsight/bin:/usr/bin:/bin" LANG=C.UTF-8 \
    HF_HOME="$LME_HOME/hf-home-hindsight" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LITELLM_LOCAL_MODEL_COST_MAP=True \
    HINDSIGHT_API_LLM_PROVIDER=openai HINDSIGHT_API_LLM_BASE_URL="http://127.0.0.1:$P_LLM/v1" HINDSIGHT_API_LLM_API_KEY=local \
    HINDSIGHT_API_LLM_MODEL="$H1_BUILD" HINDSIGHT_API_LLM_REASONING_EFFORT=low \
    HINDSIGHT_API_EMBEDDINGS_LOCAL_FORCE_CPU=true HINDSIGHT_API_RERANKER_LOCAL_FORCE_CPU=true \
    "$LME_HOME/.venv-hindsight/bin/hindsight-api" --host 127.0.0.1 --port "$P_HS"
  wait_http "http://127.0.0.1:$P_HS/health" 1800 hindsight || die "Hindsight did not start (logs/hindsight.log)"
}

# ---------------------------------------------------------------- one arm
services_survived() {  # a service that died during an arm is an environment fault (e.g. out of memory), never a result
  local name
  for name in "$@"; do
    owned_pid "$name" >/dev/null 2>&1 || die "env: $name exited during the arm (possible out-of-memory: check \
logs/$name.log, dmesg and .wslconfig memory=); the arm needs a full rerun (A4)"
  done
}
run_arm() {  # run_arm ARM WORKERS [cpu|rerank|llm]: cpu arms take no GPU samples or cache snapshots
  local arm="$1" workers="$2" kind="${3:-}" since rc=0 status services=()
  since=$(date +%s)
  [ "$kind" = cpu ] || cpu_check
  if [ "$kind" != cpu ] && curl -sf --max-time 5 "http://127.0.0.1:$P_PROXY/__stats" >/dev/null 2>&1; then
    "$PY_OFF" "$LANE/lane_tools.py" proxy-snapshot "http://127.0.0.1:$P_PROXY" "$LOGS/cache/$arm.before.json"
  fi
  case "$kind" in rerank|llm)
    for name in llama-llm ollama-llm hindsight; do owned_pid "$name" >/dev/null 2>&1 && services+=("$name"); done ;;
  esac
  log "arm $arm: start ($workers workers)"
  if [ "$kind" = cpu ]; then cpu_sample_start "$arm"; else gpu_start "$arm"; cpu_sample_start "$arm"; fi
  (cd "$LANE" && env LME_AM_SLOTS="$AM_SLOTS" LME_DENSE_BATCH="$DENSE_BATCH" \
    "$PY_OFF" lme_harness.py "$arm" --workers "$workers" --out "$RES") >> "$LOGS/arms/$arm.log" 2>&1 || rc=$?
  cpu_sample_stop "$arm"
  [ "$kind" = cpu ] || gpu_stop "$arm"
  if [ "$kind" != cpu ] && curl -sf --max-time 5 "http://127.0.0.1:$P_PROXY/__stats" >/dev/null 2>&1; then
    "$PY_OFF" "$LANE/lane_tools.py" proxy-snapshot "http://127.0.0.1:$P_PROXY" "$LOGS/cache/$arm.after.json" --since "$since"
  fi
  [ ${#services[@]} = 0 ] || services_survived "${services[@]}"
  local fb=(); [ "$kind" = rerank ] && fb=(--limit-fallback 0.05)
  [ "$arm" = hindsight-qwen3.6 ] && fb+=(--subset "$K1_SUBSET")
  status=$("$PY_OFF" "$LANE/lane_tools.py" arm-status "$RES/$arm.jsonl" "${fb[@]}" || true)
  local overlap=false; { [ -n "$cpu_pid" ] || cpu_alive; } && overlap=true
  python3 -c "import json,sys; s=json.loads(sys.argv[1]); s['cpu_stream_active']=sys.argv[2]=='true'; print(json.dumps(s))" \
    "$status" "$overlap" > "$LOGS/arms/$arm.status.json"
  log "arm $arm: exit=$rc $status"
  [ "$rc" = 0 ] || die "$arm: the harness exited $rc (preflight, env error or lock; logs/arms/$arm.log)"
  if python3 -c "import json,sys; s=json.loads(sys.argv[1]); sys.exit(1 if s['stop'] else 0)" "$status"; then return 0; fi
  if [ "$CONTINUE_AFTER_FALLBACK" = 1 ] && python3 -c \
    "import json,sys; s=json.loads(sys.argv[1]); sys.exit(0 if all('fallbacks' in r for r in s['stop']) else 1)" "$status"; then
    log "arm $arm: fallbacks over 5% recorded; continuing as the user authorized (--continue-after-fallback)"
    return 0
  fi
  die "$arm: stop condition: $status"
}

# ---------------------------------------------------------------- gates (A15 step 1, A15.2, A16)
llm_smoke() {  # llm_smoke TAG: a 30-candidate rerank prompt through the OpenAI-compatible endpoint
  python3 - "$1" "$P_LLM" <<'EOF'
import json, sys, time, urllib.request
tag, port = sys.argv[1], sys.argv[2]
cands = [{"candidate": i + 1, "title": f"session {i}", "text": ("The user mentioned a blue notebook bought in May. " * 12)[:600]}
         for i in range(30)]
schema = {"type": "object", "properties": {"scores": {"type": "array", "items": {"type": "object", "properties": {
    "candidate": {"type": "integer"}, "relevance": {"type": "number"}}, "required": ["candidate", "relevance"]}}}, "required": ["scores"]}
body = {"model": tag, "reasoning_effort": "low", "max_tokens": 4000, "temperature": 0.1,
        "response_format": {"type": "json_schema", "json_schema": {"name": "rerank", "schema": schema}},
        "messages": [{"role": "system", "content": "Score how well each candidate answers the query. Reply with JSON only."},
                     {"role": "user", "content": json.dumps({"query": "Where did I buy my blue notebook?", "candidates": cands})}]}
t0 = time.time()
req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
out = json.load(urllib.request.urlopen(req, timeout=600))
scores = json.loads(out["choices"][0]["message"]["content"])["scores"]
print(json.dumps({"tag": tag, "seconds": round(time.time() - t0, 1), "scored": len(scores), "usage": out.get("usage")}))
sys.exit(0 if len(scores) == 30 else 1)
EOF
}
cmd_gates() {
  local ids=() v3dir="$LME_HOME/v3check"
  rm -f "$LOGS/gates/passed.json"
  log "gate: official oracle (A6)"
  (cd "$OFFICIAL/src/retrieval" && PYTHONPATH="$OFFICIAL" "$PY_OFF" run_retrieval.py --in_file "$LME_DATA" \
    --out_dir "$OFF" --retriever oracle --granularity session) > "$LOGS/official-oracle.log" 2>&1 || die "the official oracle failed"
  (cd "$LANE" && "$PY_OFF" lane_tools.py official-rows --logs "$OFF" --out "$RES") || die "official-rows failed"
  (cd "$LANE" && "$PY_OFF" lme_summarize.py --oracle-gate --results "$RES" --official-logs "$OFF") > "$LOGS/gates/oracle.json" \
    || die "oracle ceilings not reached (logs/gates/oracle.json)"

  log "gate: v4 reproduces v3 (A15.2), the 20 listed questions as C1 and as B1"
  mapfile -t ids < "$LANE/reference/v3-check-ids.txt"
  mkdir -p "$v3dir/bin" "$v3dir/v3" "$v3dir/v4"
  cp "$LANE/reference/lme_harness_v3.py" "$v3dir/lme_harness.py"
  cp "$LANE/eligible-manifest.json" "$v3dir/"
  ln -sfn "$LME_HOME/data" "$v3dir/data"
  # shellcheck disable=SC2016  # the shim's own $1 and $2
  printf '#!/bin/sh\n[ "$1" = which ] && [ "$2" = node ] && echo "%s" && exit 0\nexit 1\n' "$LME_NODE" > "$v3dir/bin/mise"
  chmod +x "$v3dir/bin/mise"
  # v3 hard-codes ~/.local/share/agent-ecosystem/{src/LongMemEval, tools/ai-memory-2.5.0-19b6429, bench/agentmemory}: it
  # runs unmodified under a HOME whose links point at the lane's installs, never at the production layout.
  "$PY_OFF" "$LANE/lane_tools.py" v3-shim "$v3dir/home" --official "$OFFICIAL" --aimem "$AIMEM_DIR/ai-memory" \
    --agentmemory "$AM_ROOT" > "$LOGS/gates/v3-shim.json" || die "the v3 shim could not be built"
  for arm in aimem-fts bm25-full; do
    rm -f "$v3dir/v3/$arm.jsonl" "$v3dir/v4/$arm.jsonl"
    (cd "$v3dir" && HOME="$v3dir/home" PATH="$v3dir/bin:$PATH" "$PY_OFF" lme_harness.py "$arm" --ids "${ids[@]}" \
      --out "$v3dir/v3") > "$LOGS/gates/v3-$arm.log" 2>&1 \
      || die "v3 failed on $arm (logs/gates/v3-$arm.log)"
    (cd "$LANE" && "$PY_OFF" lme_harness.py "$arm" --ids "${ids[@]}" --out "$v3dir/v4") > "$LOGS/gates/v4-$arm.log" 2>&1 \
      || die "v4 failed on $arm (logs/gates/v4-$arm.log)"
    "$PY_OFF" "$LANE/lane_tools.py" v3-equivalence "$v3dir/v3/$arm.jsonl" "$v3dir/v4/$arm.jsonl" \
      --ids-file "$LANE/reference/v3-check-ids.txt" > "$LOGS/gates/v3-v4-$arm.json" \
      || die "v4 does not reproduce v3 on $arm (logs/gates/v3-v4-$arm.json)"
    "$PY_OFF" "$LANE/lane_tools.py" v3-equivalence "$LANE/reference/mac-rows/$arm.jsonl" "$v3dir/v4/$arm.jsonl" \
      --ids-file "$LANE/reference/v3-check-ids.txt" > "$LOGS/gates/mac-v4-$arm.json" \
      || log "note: VelaNext v4 differs from the Mac's v3 rows on $arm (reported, not a gate)"
  done

  log "gate: agentmemory slot smoke (8 parallel slots reproduce sequential rankings)"
  rm -rf "$LME_HOME/results-smoke-slots"
  (cd "$LANE" && LME_AM_SLOTS=1 "$PY_OFF" lme_harness.py am-keyless --ids "${ids[@]:0:8}" --workers 1 \
    --out "$LME_HOME/results-smoke-slots/seq") > "$LOGS/gates/slots-seq.log" 2>&1 || die "slot smoke (sequential) failed"
  (cd "$LANE" && LME_AM_SLOTS=8 "$PY_OFF" lme_harness.py am-keyless --ids "${ids[@]:0:8}" --workers 8 \
    --out "$LME_HOME/results-smoke-slots/par") > "$LOGS/gates/slots-par.log" 2>&1 || die "slot smoke (parallel) failed"
  "$PY_OFF" "$LANE/lane_tools.py" v3-equivalence "$LME_HOME/results-smoke-slots/seq/am-keyless.jsonl" \
    "$LME_HOME/results-smoke-slots/par/am-keyless.jsonl" --ids-file "$LANE/reference/v3-check-ids.txt" --first 8 \
    > "$LOGS/gates/slots.json" || die "parallel slots changed rankings"

  gpu_begin "the reference gates"
  gpu_start gate-embedders
  log "gate: reference outputs and batch invariance of the BF16 servers (A15, A15.1)"
  while read -r repo rev; do
    st_up "$repo" "$rev" selftest || die "$repo failed its reference-output gate (logs/gates/st-$(slug "$repo").json)"
  done < <(python3 -c "import json; d=json.load(open('$LANE/embed_gates.json'))['models']
for k, v in d.items(): print(k, v['revision'])")
  log "gate: batch invariance of the GGUF embedders under llama-server (A15.1)"
  for model in qwen3-embedding:0.6b qwen3-embedding:4b qwen3-embedding:8b; do
    gguf_up "$model" selftest
    [ -f "$LOGS/gates/gguf-$(slug "$model").json" ] || die "no gate report for $model"
  done
  log "gate: A13 cache self-test"
  gguf_up qwen3-embedding:4b
  (cd "$LANE" && "$PY_OFF" embed_cache_proxy.py "http://127.0.0.1:$P_EMBED" $((P_PROXY + 10)) "$LME_HOME/cache/proxy-selftest" \
    --identity "$IDENTITY" --canary-model "$CANARY_MODEL" --selftest "$CANARY_MODEL") > "$LOGS/gates/proxy-selftest.log" 2>&1 \
    || die "the A13 cache self-test failed"
  gpu_stop gate-embedders
  embed_down

  log "gate: reranker LLM smoke, effective context and placement (A15.2)"
  gpu_start gate-llm
  for tag in qwen3.5-9b-64k qwen3.6-35b-a3b-64k nemotron-3.5-lightning-30b-a3b-64k lfm2.5-2.6b-64k; do
    gpu_begin "the $tag smoke"
    llm_up "$tag" gate
    llm_smoke "$tag" > "$LOGS/gates/llm-$tag.json" || die "reranker LLM smoke failed for $tag"
  done
  log "gate: A16 smoke, K1 on one subset question with the H1 build and Hindsight"
  gpu_begin "the K1 smoke"
  llm_up "$H1_BUILD" gate-k1; hs_up
  rm -rf "$LME_HOME/results-smoke-a16"
  (cd "$LANE" && "$PY_OFF" lme_harness.py hindsight-qwen3.6 --limit 1 --out "$LME_HOME/results-smoke-a16") \
    > "$LOGS/gates/smoke-k1.log" 2>&1 || die "K1 smoke failed (logs/gates/smoke-k1.log)"
  "$PY_OFF" "$LANE/lane_tools.py" arm-status "$LME_HOME/results-smoke-a16/hindsight-qwen3.6.jsonl" --subset "$K1_SUBSET" \
    > "$LOGS/gates/smoke-k1.json" || true
  python3 -c "import json,sys; r=[json.loads(x) for x in open(sys.argv[1])]; sys.exit(0 if r and not r[0]['error'] and r[0]['ranking'] else 1)" \
    "$LME_HOME/results-smoke-a16/hindsight-qwen3.6.jsonl" || die "K1 smoke returned an error or an empty ranking"
  hs_down; llm_down
  gpu_stop gate-llm
  log "gate: mteb's LongMemEval task loads offline from the verified cache (first-line evaluation)"
  (cd "$LANE" && HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PY_EMB" mteb_lmeb.py --dry-load) \
    > "$LOGS/gates/mteb-dry-load.json" 2> "$LOGS/gates/mteb-dry-load.log" || die "mteb's task data does not load offline"
  log "gate: A16 smoke, M2 on two questions through MemPalace's hook path and MCP search"
  (cd "$LANE" && "$PY_OFF" lme_harness.py mempalace-palace --ids "${ids[@]:0:2}" --workers 2 --out "$LME_HOME/results-smoke-a16") \
    > "$LOGS/gates/smoke-m2.log" 2>&1 || die "M2 smoke failed (logs/gates/smoke-m2.log)"
  python3 -c "import json,sys; r=[json.loads(x) for x in open(sys.argv[1])]; sys.exit(0 if len(r) == 2 and all(not x['error'] and x['ranking'] for x in r) else 1)" \
    "$LME_HOME/results-smoke-a16/mempalace-palace.jsonl" || die "M2 smoke returned an error or an empty ranking"
  "$PY_OFF" "$LANE/lane_tools.py" gates-check "$LOGS/gates" > "$LOGS/gates/passed.json" || die "the gate reports do not pass"
  log "gates passed"
}

# ---------------------------------------------------------------- CPU-only arms and the vendor harnesses (A15.1)
agentmemory_vendor() {  # the vendor bench writes into its checkout's tracked benchmark/data: keep a lane copy only
  local mode="$1" dst="$LME_HOME/vendor/agentmemory/$1.json" out="$AMREPO/benchmark/data/longmemeval_results_$1.json"
  [ -s "$dst" ] && return 0
  mkdir -p "$(dirname "$dst")"
  : > "$dst.start"
  if (cd "$AMREPO" && ./node_modules/.bin/tsx benchmark/longmemeval-bench.ts "$mode") > "$LOGS/vendor-agentmemory-$mode.log" 2>&1 \
    && [ "$out" -nt "$dst.start" ]; then
    cp "$out" "$dst.part" && mv "$dst.part" "$dst"
  else
    log "vendor agentmemory $mode failed or wrote nothing new (reported)"
  fi
  git -C "$AMREPO" checkout -- "benchmark/data/longmemeval_results_$mode.json" 2>/dev/null || true
  rm -f "$dst.start"
}
cmd_cpu() {
  require_gates
  local other
  if other=$(owned_pid cpu-stream 2>/dev/null) && [ "$other" != "$$" ]; then die "another cpu stage is running (pid $other)"; fi
  pid_record cpu-stream "$$" "$(exe_of bash)"
  OWNED=()  # the cpu stage installs no cleanup and owns nothing another stage may stop
  log "cpu stream: A0 official flat-bm25"
  if [ ! -s "$RES/A0-official-bm25.jsonl" ]; then
    (cd "$OFFICIAL/src/retrieval" && PYTHONPATH="$OFFICIAL" "$PY_OFF" run_retrieval.py --in_file "$LME_DATA" \
      --out_dir "$OFF" --retriever flat-bm25 --granularity session) > "$LOGS/official-bm25.log" 2>&1 || die "A0 (official flat-bm25) failed"
    (cd "$LANE" && "$PY_OFF" lane_tools.py official-rows --logs "$OFF" --out "$RES") || die "official-rows failed"
    [ -s "$RES/A0-official-bm25.jsonl" ] || die "A0 wrote no rows"
  fi
  run_arm bm25-full 8 cpu
  run_arm aimem-fts "$AIMEM_WORKERS" cpu
  run_arm am-keyless "$AM_SLOTS" cpu
  run_arm aimem-minilm "$AIMEM_WORKERS" cpu
  run_arm am-minilm "$AM_SLOTS" cpu
  run_arm am-minilm-hooks "$AM_SLOTS" cpu
  run_arm mempalace-palace "$MP_WORKERS" cpu  # A16 M2
  log "cpu stream: the vendors' own LongMemEval harnesses, unmodified"
  for mode in none local; do
    if ! ls "$LME_HOME/vendor/ai-memory/$mode"/*-retrieval/report.json >/dev/null 2>&1; then
      mkdir -p "$LME_HOME/vendor/ai-memory/$mode"
      (cd "$SRC/ai-memory" && ./target/release/ai-memory-eval retrieval --fetch --server-bin "$AIMEM_DIR/ai-memory" \
        --embeddings "$mode" --out "$LME_HOME/vendor/ai-memory/$mode") > "$LOGS/vendor-ai-memory-$mode.log" 2>&1 \
        || log "vendor ai-memory $mode failed (reported)"
    fi
  done
  agentmemory_vendor bm25
  agentmemory_vendor hybrid
  log "cpu stream: M1, MemPalace's raw mode through its own benchmarks/longmemeval_bench.py (unmodified, A16)"
  local m1="$LME_HOME/vendor/mempalace/m1-raw.jsonl" m1home="$LME_HOME/vendor/mempalace/home"
  if [ ! -s "$m1" ]; then
    mkdir -p "$m1home/.cache/chroma/onnx_models"
    ln -sfn "$LME_MEMPALACE_ONNX" "$m1home/.cache/chroma/onnx_models/all-MiniLM-L6-v2"
    if (cd "$MPREPO" && env -i HOME="$m1home" PATH="$LME_MEMPALACE_VENV/bin:/usr/bin:/bin" LANG=C.UTF-8 HF_HUB_OFFLINE=1 \
      "$LME_MEMPALACE_VENV/bin/python" benchmarks/longmemeval_bench.py "$LME_DATA" --mode raw --out "$m1.part") \
      > "$LOGS/vendor-mempalace-m1.log" 2>&1; then
      mv "$m1.part" "$m1"
    else
      log "M1 failed (diagnostic; logs/vendor-mempalace-m1.log)"
    fi
  fi
  if [ -s "$m1" ]; then (cd "$LANE" && "$PY_OFF" lane_tools.py m1-rows --log "$m1" --out "$RES") || die "m1-rows failed"; fi
  rm -f "$LOGS/pids/cpu-stream.pid"
  log "cpu stream: done"
}

# ---------------------------------------------------------------- mteb, first-line (user directive), offline
cmd_mteb() {
  local offline=(env HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1) failed=0 ran=0
  "$PY_EMB" "$LANE/lane_tools.py" verify-hf --select mteb,data > "$LOGS/mteb-verify.log" \
    || die "the pinned mteb models or data are not in the verified cache (logs/mteb-verify.log)"
  for repo in nvidia/Nemotron-3-Embed-8B-BF16 nvidia/Nemotron-3-Embed-1B-BF16 microsoft/harrier-oss-v1-0.6b Qwen/Qwen3-Embedding-4B \
              Qwen/Qwen3-Embedding-0.6B Qwen/Qwen3-Embedding-8B sentence-transformers/all-MiniLM-L6-v2; do
    [ -f "$LME_HOME/mteb-lmeb/$(slug "$repo").json" ] && continue
    log "mteb LMEB LongMemEval: $repo"
    gpu_begin "mteb $repo"
    gpu_start "mteb-$(slug "$repo")"
    ran=$((ran + 1))
    if ! (cd "$LANE" && "${offline[@]}" "$PY_EMB" mteb_lmeb.py --model "$repo" --out "$LME_HOME/mteb-lmeb") \
      > "$LOGS/mteb-$(slug "$repo").log" 2>&1; then
      failed=$((failed + 1))
      log "mteb failed for $repo (reported; logs/mteb-$(slug "$repo").log)"
    fi
    gpu_stop "mteb-$(slug "$repo")"
  done
  [ "$ran" = 0 ] || [ "$failed" -lt "$ran" ] || die "mteb failed for every model this stage ran (logs/mteb-*.log)"
  (cd "$LANE" && "${offline[@]}" "$PY_EMB" mteb_lmeb.py --summary --out "$LME_HOME/mteb-lmeb")
}

# ---------------------------------------------------------------- GPU arms in A15's order (A15.2 for F and H)
E_F_EMBEDDERS=("nemotron-8b nvidia/Nemotron-3-Embed-8B-BF16 d1f2f25730bbd775b99b29185134bc86653bf2d1"
  "nemotron-1b nvidia/Nemotron-3-Embed-1B-BF16 c0c9fea93ea424587517f2c59e20db9f1d6bf615"
  "harrier-0.6b microsoft/harrier-oss-v1-0.6b f9b9dc8d367d443f2479d27aa5d8d2850c0774ee")
cmd_arms_until_h() {
  local short repo rev entry
  # 2. C3, then C4. A16.3: C4 computes its own embeddings on the same GPU server and device as C3 (its page bodies
  # carry wall-clock timestamps, so nothing repeats byte for byte); the reranker LLM shares the GPU, offloading
  # what does not fit. The embedding server starts first, so the LLM's placement sees the memory left.
  gpu_begin C3; gguf_up qwen3-embedding:4b; proxy_up aimem-qwen3; run_arm aimem-qwen3 "$AIMEM_WORKERS"
  gpu_begin C4; gguf_up qwen3-embedding:4b shared; proxy_up aimem-qwen3-rerank; llm_up qwen3.5-9b-64k aimem-qwen3-rerank
  run_arm aimem-qwen3-rerank "$RERANK_WORKERS" rerank
  # 3. E1-E3, then F1-F3 (each F after its cache-fill pass; A15.2), F on the same GPU server as its fill (A16.3)
  for entry in "${E_F_EMBEDDERS[@]}"; do
    read -r short repo rev <<< "$entry"
    gpu_begin "am-$short"; st_up "$repo" "$rev"; proxy_up "am-$short"; run_arm "am-$short" "$AM_SLOTS"
  done
  for entry in "${E_F_EMBEDDERS[@]}"; do
    read -r short repo rev <<< "$entry"
    gpu_begin "aimem-$short-fill"; st_up "$repo" "$rev"; proxy_up "aimem-$short-fill"; run_arm "aimem-$short-fill" "$AIMEM_WORKERS"
    gpu_begin "aimem-$short"; st_up "$repo" "$rev" shared; proxy_up "aimem-$short"; llm_up qwen3.5-9b-64k "aimem-$short"
    run_arm "aimem-$short" "$RERANK_WORKERS" rerank  # A16.2: A12's 5% rule on F's own fallbacks
  done
  # 4. the rest of the original family's GPU arms
  gpu_begin B2; gguf_up qwen3-embedding:4b; proxy_up dense-qwen3; run_arm dense-qwen3 1
  proxy_up am-qwen3; run_arm am-qwen3 "$AM_SLOTS"
  gpu_begin C6; gguf_up qwen3-embedding:0.6b; proxy_up aimem-qwen3-0.6b; run_arm aimem-qwen3-0.6b "$AIMEM_WORKERS"
  gpu_begin C5; gguf_up qwen3-embedding:8b; proxy_up aimem-qwen3-8b; run_arm aimem-qwen3-8b "$AIMEM_WORKERS"
  embed_down
}
cmd_arms_from_h() {
  local arm tag short repo rev entry
  cpu_join  # H1 and H2 keep their experts on the host: the CPU stream has finished (review, infra F8)
  # 5. H1-H3: C3's GPU embedding server, shared with the reranker LLM (A16.3); production parameters (A15.2)
  while read -r arm tag; do
    gpu_begin "$arm"; gguf_up qwen3-embedding:4b shared; proxy_up "$arm"; llm_up "$tag" "$arm"
    run_arm "$arm" "$RERANK_WORKERS" rerank
  done < <(printf '%s\n' "aimem-qwen3-rerank-qwen3.6 qwen3.6-35b-a3b-64k" \
    "aimem-qwen3-rerank-nemotron-lightning nemotron-3.5-lightning-30b-a3b-64k" "aimem-qwen3-rerank-lfm2.5 lfm2.5-2.6b-64k")
  # 6. G0-G3
  gpu_begin G0; st_up Qwen/Qwen3-Embedding-4B 5cf2132abc99cad020ac570b19d031efec650f2b; proxy_up dense-qwen3-bf16; run_arm dense-qwen3-bf16 1
  for entry in "${E_F_EMBEDDERS[@]}"; do
    read -r short repo rev <<< "$entry"
    gpu_begin "dense-$short"; st_up "$repo" "$rev"; proxy_up "dense-$short"; run_arm "dense-$short" 1
  done
  llm_down; embed_down
}
cmd_arms() { require_gates; cmd_arms_until_h; cmd_arms_from_h; }

# ---------------------------------------------------------------- A16: K1, AMB and the pooled stress run
cmd_a16() {  # K1 with the H1 build on the GPU (expert offload), Hindsight's embedder and reranker on the CPU
  require_gates
  gpu_begin K1; llm_up "$H1_BUILD" hindsight-qwen3.6; hs_up
  run_arm hindsight-qwen3.6 "$K1_WORKERS" llm
  hs_down; llm_down
}

cmd_amb() {  # Hindsight's agent-memory-benchmark at its AMB_REF, unmodified, question by question on K1's subset
  local out="$LME_HOME/vendor/amb" qid
  require_gates
  mkdir -p "$out/home"
  gpu_begin AMB; llm_up "$H1_BUILD" amb; hs_up
  gpu_start amb; cpu_sample_start amb
  for qid in $(python3 -c "import json,sys; print(' '.join(json.load(open(sys.argv[1]))['question_ids']))" "$K1_SUBSET"); do
    if python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if any(r['query_id']==sys.argv[2] for r in d['results']) else 1)" \
      "$out/outputs/longmemeval/k1-subset/rag/s.json" "$qid" 2>/dev/null; then continue; fi
    # AMB's own code, run from its source tree with its locked dependencies (uv sync --frozen --no-install-project):
    # no unpinned build backend is involved (review pins P6).
    (cd "$AMBREPO" && env -i HOME="$out/home" PATH="$AMBREPO/.venv/bin:/usr/bin:/bin" LANG=C.UTF-8 PYTHONPATH="$AMBREPO/src" \
      LONGMEMEVAL_DATA_PATH="$LME_DATA" HINDSIGHT_HTTP_URL="http://127.0.0.1:$P_HS" \
      OPENAI_BASE_URL="http://127.0.0.1:$P_LLM/v1" OPENAI_API_KEY=local OMB_ANSWER_LLM=openai OMB_ANSWER_MODEL="$H1_BUILD" \
      OMB_JUDGE_LLM=openai OMB_JUDGE_MODEL="$H1_BUILD" \
      "$AMBREPO/.venv/bin/python" -c 'import sys; from memory_bench.cli import app; sys.argv[0] = "amb"; app()' \
      run --dataset longmemeval --split s --memory hindsight-http --llm openai --query-id "$qid" \
      --output-dir "$out/outputs" --name k1-subset) >> "$LOGS/vendor-amb.log" 2>&1 || log "AMB failed on $qid (diagnostic)"
  done
  cpu_sample_stop amb; gpu_stop amb
  hs_down; llm_down
}

pooled_services() {  # pooled_services ARM: the services an arm's pooled run needs (descriptive; A12 does not apply)
  case "$1" in
    aimem-qwen3) gguf_up qwen3-embedding:4b; proxy_up "pooled-$1" ;;
    aimem-qwen3-rerank) gguf_up qwen3-embedding:4b shared; proxy_up "pooled-$1"; llm_up qwen3.5-9b-64k "pooled-$1" ;;
    hindsight-qwen3.6) llm_up "$H1_BUILD" "pooled-$1"; hs_up ;;
    am-minilm-hooks|mempalace-palace) ;;
    *) die "no pooled services for $1" ;;
  esac
}
cmd_pooled() {  # A16.1: the top two systems by the confirmatory point estimate, one store of every eligible session
  local arm
  require_gates
  "$PY_OFF" "$LANE/lane_tools.py" pooled-pick --results "$RES" --data "$LME_DATA" --json > "$LOGS/gates/pooled-pick.json" \
    || die "pooled-pick failed"
  for arm in $("$PY_OFF" "$LANE/lane_tools.py" pooled-pick --results "$RES" --data "$LME_DATA"); do
    log "pooled: $arm (one store for every eligible session; descriptive)"
    gpu_begin "pooled-$arm"
    pooled_services "$arm"
    gpu_start "pooled-$arm"; cpu_sample_start "pooled-$arm"
    (cd "$LANE" && "$PY_OFF" lme_harness.py "$arm" --pooled --out "$RES") >> "$LOGS/arms/pooled-$arm.log" 2>&1 \
      || log "pooled $arm stopped (descriptive; logs/arms/pooled-$arm.log)"
    cpu_sample_stop "pooled-$arm"; gpu_stop "pooled-$arm"
    hs_down; llm_down; embed_down
    "$PY_OFF" "$LANE/lane_tools.py" arm-status "$RES/pooled-$arm.jsonl" > "$LOGS/arms/pooled-$arm.status.json" || true
  done
}

cmd_x() {
  require_gates
  for r in ettin-400m memreranker-4b qwen3-reranker-4b kalm-small; do
    log "X: $r over the best arm's top 50"
    gpu_begin "X $r"
    gpu_start "x-$r"
    (cd "$LANE" && HF_HUB_OFFLINE=1 "$PY_EMB" rerank_stage.py --reranker "$r" --base auto --results "$RES") >> "$LOGS/arms/x-$r.log" 2>&1 \
      || log "X $r failed (exploratory; logs/arms/x-$r.log)"
    gpu_stop "x-$r"
  done
}

cmd_report() {
  local final=(); [ "$FINAL" = 1 ] && final=(--final)
  (cd "$LANE" && "$PY_OFF" lane_tools.py official-rows --logs "$OFF" --out "$RES") || die "official-rows failed"
  (cd "$LANE" && "$PY_OFF" lme_summarize.py --results "$RES" --official-logs "$OFF" --platform VelaNext --confirmatory \
    --gates "$LOGS/gates" "${final[@]}" --gpu-logs "$LOGS" --out "$RES/report") > "$LOGS/report.log" 2>&1 \
    || die "the summarizer failed or refused (logs/report.log)"
  if [ -d "$LME_HOME/mteb-lmeb" ]; then
    (cd "$LANE" && HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$PY_EMB" mteb_lmeb.py --summary \
      --out "$LME_HOME/mteb-lmeb") > /dev/null
  fi
  (cd "$LANE" && "$PY_OFF" lane_tools.py vendor-parse --ai-memory "$LME_HOME/vendor/ai-memory" \
    --agentmemory "$LME_HOME/vendor/agentmemory" --mempalace "$LME_HOME/vendor/mempalace/m1-raw.jsonl" \
    --amb "$LME_HOME/vendor/amb/outputs/longmemeval/k1-subset/rag/s.json" --results "$RES" --out "$RES/vendor-harnesses.json") > /dev/null
  log "report: $RES/report.md"
}

cmd_collect() {  # sanitize() writes the destination only when nothing private is left (review, lane F5)
  local stage="$LME_HOME/collect" dest="$LANE/results-velanext"
  rm -rf "$stage"
  mkdir -p "$stage"/{rows,gates,cache,ollama,gpu,cpu,mteb,arms}
  cp "$RES"/*.jsonl "$stage/rows/"
  cp "$RES/report.md" "$RES/report.json" "$RES/vendor-harnesses.json" "$stage/" 2>/dev/null || true
  cp "$LOGS"/gates/*.json "$stage/gates/" 2>/dev/null || true
  cp "$LOGS"/cache/*.json "$stage/cache/" 2>/dev/null || true
  cp "$LOGS"/ollama/*.json "$stage/ollama/" 2>/dev/null || true
  cp "$LOGS"/gpu-*.log "$stage/gpu/" 2>/dev/null || true
  cp "$LOGS"/load-*.log "$stage/cpu/" 2>/dev/null || true
  cp "$LOGS"/arms/*.status.json "$stage/arms/" 2>/dev/null || true
  cp "$LME_HOME"/mteb-lmeb/*.json "$LME_HOME"/mteb-lmeb/_summary.md "$stage/mteb/" 2>/dev/null || true
  (cd "$LANE" && "$PY_OFF" lane_tools.py receipt --out "$stage/environment-receipt.json" --results "$RES" --logs "$LOGS") \
    || die "the receipt failed"
  "$PY_OFF" "$LANE/lane_tools.py" sanitize "$stage" "$dest" \
    || die "sanitizing found private data; nothing was written to $dest (the files and positions are listed above)"
  (cd "$REPO" && python3 scripts/validate.py) || die "scripts/validate.py failed on the collected results"
  log "collected into $dest"
}

EXPECTED_ARMS="A0-official-bm25 A1-official-oracle bm25-full aimem-fts am-keyless aimem-minilm am-minilm am-minilm-hooks
mempalace-palace aimem-qwen3 aimem-qwen3-rerank am-nemotron-8b am-nemotron-1b am-harrier-0.6b aimem-nemotron-8b-fill
aimem-nemotron-8b aimem-nemotron-1b-fill aimem-nemotron-1b aimem-harrier-0.6b-fill aimem-harrier-0.6b dense-qwen3 am-qwen3
aimem-qwen3-0.6b aimem-qwen3-8b aimem-qwen3-rerank-qwen3.6 aimem-qwen3-rerank-nemotron-lightning aimem-qwen3-rerank-lfm2.5
dense-qwen3-bf16 dense-nemotron-8b dense-nemotron-1b dense-harrier-0.6b hindsight-qwen3.6"
cmd_status() {  # every expected arm, with the same stop conditions run_arm applies (review, lane F6)
  local arm flags
  for arm in $EXPECTED_ARMS; do
    if [ ! -f "$RES/$arm.jsonl" ]; then printf '%-45s MISSING\n' "$arm"; continue; fi
    flags=()
    case "$arm" in  # C4, H and F (A12, A15.2, A16.2)
      aimem-qwen3-rerank|aimem-qwen3-rerank-*|aimem-nemotron-8b|aimem-nemotron-1b|aimem-harrier-0.6b) flags=(--limit-fallback 0.05) ;;
    esac
    [ "$arm" = hindsight-qwen3.6 ] && flags+=(--subset "$K1_SUBSET")
    [ "$arm" = A1-official-oracle ] && flags+=(--track official)
    printf '%-45s %s\n' "$arm" "$("$PY_OFF" "$LANE/lane_tools.py" arm-status "$RES/$arm.jsonl" "${flags[@]}" || true)"
  done
}

main() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --aimem-workers|--rerank-workers|--am-slots|--dense-batch|--llama-slots|--llama-ubatch|--mp-workers|--k1-workers)
        OPTS+=("$1" "$2")
        case "$1" in
          --aimem-workers) AIMEM_WORKERS="$2" ;; --rerank-workers) RERANK_WORKERS="$2" ;; --am-slots) AM_SLOTS="$2" ;;
          --dense-batch) DENSE_BATCH="$2" ;; --llama-slots) LLAMA_NP="$2" ;; --llama-ubatch) LLAMA_UBATCH="$2" ;;
          --mp-workers) MP_WORKERS="$2" ;; --k1-workers) K1_WORKERS="$2" ;;
        esac
        shift 2 ;;
      --continue-after-fallback) CONTINUE_AFTER_FALLBACK=1; OPTS+=("$1"); shift ;;
      --final) FINAL=1; shift ;;  # A16.3: the operator declares the queue finished (report only)
      --mteb-after) MTEB_AFTER=1; shift ;;
      -*) echo "unknown option $1" >&2; exit 2 ;;
      *) CMD="$1"; shift ;;
    esac
  done
  [ -n "$CMD" ] || { sed -n '2,39p' "$0"; exit 2; }
  [ "$FINAL" = 0 ] || [ "$CMD" = report ] || [ "$CMD" = all ] || { echo "--final goes with report" >&2; exit 2; }
  case "$CMD" in
    gates|mteb|arms|a16|x|amb|pooled|all) gpu_guard ;;
  esac
  case "$CMD" in
    gates) cmd_gates ;;
    cpu) cmd_cpu ;;
    mteb) cmd_mteb ;;
    arms) cmd_arms ;;
    a16) cmd_a16 ;;
    amb) cmd_amb ;;
    pooled) cmd_pooled ;;
    x) cmd_x ;;
    report) cmd_report ;;
    collect) cmd_collect ;;
    status) cmd_status ;;
    all)
      cmd_gates
      require_gates
      rm -f "$LOGS/cpu-stream.failed"
      # its own process and process group, with its own errexit, and without the GPU lock (review, lane F6)
      setsid bash "$0" "${OPTS[@]+"${OPTS[@]}"}" cpu > "$LOGS/cpu-stream.log" 2>&1 9>&- &
      cpu_pid=$!
      pid_record cpu-stream "$cpu_pid" "$(exe_of bash)"
      [ "$MTEB_AFTER" = 1 ] || cmd_mteb
      cpu_check
      cmd_arms_until_h
      cmd_arms_from_h  # joins the CPU stream first
      cmd_a16
      cmd_x
      [ "$MTEB_AFTER" = 0 ] || cmd_mteb
      cmd_amb
      cmd_report
      cmd_collect
      cmd_pooled  # descriptive, last: it never holds up the confirmatory report
      FINAL=1
      cmd_report
      cmd_collect ;;
    *) echo "unknown command $CMD" >&2; exit 2 ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then main "$@"; fi
