#!/usr/bin/env bash
# One frozen GPU window for blueprints/convergence-practice/local-inference-latest-20260926.
# Preregistered; the change that adds it does not run it. Read README.md first.
#
#   window.sh --arms C0[,C1,C2,M] --acquisition DIR --inputs-sha256 HEX \
#             --runtime-dir DIR --models-dir DIR --state-dir DIR \
#             [--production-unit NAME|none] [--production-health URL]
#
# Stops only the production generation unit, runs each named arm once on
# 127.0.0.1:18299 in its own systemd scope with a host-memory cap, samples
# whole-device GPU memory at 1 Hz and stops only that scope below the reserve.
# The exit trap always starts the production unit again and waits for /health 200.
# It never closes Windows applications, never touches other units and never
# runs wsl --terminate or --shutdown.
set -Eeuo pipefail
umask 077

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly HERE
readonly PLAN="$HERE/plan.json"
readonly EVAL="$HERE/eval_arm.py"
readonly PORT=18299
readonly ADMISSION_FLOOR_MIB=16384
readonly MINIMUM_FREE_MIB=3072
readonly WINDOW_SECONDS=10800
readonly ARM_SECONDS=9000
readonly STARTUP_SECONDS=300
readonly RESTORE_RESERVE_SECONDS=900
readonly MINIMUM_ARM_SECONDS=600
readonly MEMORY_MAX=20G
readonly MEMORY_MAX_BYTES=21474836480
readonly COORDINATION_LINE='GPU trials: TRIALS DONE'

die() {
  printf 'window: %s\n' "$*" >&2
  exit 2
}

ARMS_CSV='' ACQUISITION='' INPUTS_SHA256='' RUNTIME_DIR='' MODELS_DIR='' STATE_DIR=''
PRODUCTION_UNIT=nativestack-generation.service
PRODUCTION_HEALTH=http://127.0.0.1:18232/health
while (($#)); do
  case $1 in
    --arms) ARMS_CSV=${2:?}; shift 2 ;;
    --acquisition) ACQUISITION=${2:?}; shift 2 ;;
    --inputs-sha256) INPUTS_SHA256=${2:?}; shift 2 ;;
    --runtime-dir) RUNTIME_DIR=${2:?}; shift 2 ;;
    --models-dir) MODELS_DIR=${2:?}; shift 2 ;;
    --state-dir) STATE_DIR=${2:?}; shift 2 ;;
    --production-unit) PRODUCTION_UNIT=${2:?}; shift 2 ;;
    --production-health) PRODUCTION_HEALTH=${2:?}; shift 2 ;;
    *) die "unknown argument: $1" ;;
  esac
done
[[ -n $ARMS_CSV && -n $ACQUISITION && -n $INPUTS_SHA256 && -n $RUNTIME_DIR && -n $MODELS_DIR && -n $STATE_DIR ]] ||
  die "usage: window.sh --arms C0[,C1,C2,M] --acquisition DIR --inputs-sha256 HEX --runtime-dir DIR --models-dir DIR --state-dir DIR"
[[ $INPUTS_SHA256 =~ ^[0-9a-f]{64}$ ]] || die "--inputs-sha256 must be 64 lowercase hex digits"
IFS=, read -r -a ARMS <<<"$ARMS_CSV"
seen=' '
for arm in "${ARMS[@]}"; do
  case $arm in
    C0 | C1 | C2 | M) ;;
    *) die "arm $arm is not runnable under this plan (B and X are runtime_unsupported)" ;;
  esac
  [[ $seen != *" $arm "* ]] || die "arm $arm is listed twice"
  seen+="$arm "
done

if [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then
  NVSMI=/usr/lib/wsl/lib/nvidia-smi
else
  NVSMI=$(command -v nvidia-smi || true)
fi
readonly NVSMI

MEM_USED='' MEM_FREE=''
read_memory() {
  local line used free
  line=$("$NVSMI" --query-gpu=memory.used,memory.free --format=csv,noheader,nounits --id=0 2>/dev/null) || return 1
  IFS=', ' read -r used free <<<"$line"
  [[ $used =~ ^[0-9]+$ && $free =~ ^[0-9]+$ ]] || return 1
  MEM_USED=$used
  MEM_FREE=$free
}

# --- read-only preflight: nothing is stopped until all of this passes -------
grep -qxF "$COORDINATION_LINE" "$HERE/README.md" ||
  die "README.md does not contain the line '$COORDINATION_LINE'; another session owns GPU trials"
[[ -n $NVSMI && -x $NVSMI ]] || die "nvidia-smi not found"
command -v systemd-run >/dev/null || die "systemd-run not found"
python3 "$EVAL" verify-frozen --plan "$PLAN"
python3 "$EVAL" verify-inputs --acquisition "$ACQUISITION" --inputs-sha256 "$INPUTS_SHA256"
verify_args=()
for arm in "${ARMS[@]}"; do
  verify_args+=(--arm "$arm")
done
python3 "$EVAL" verify-arms --plan "$PLAN" "${verify_args[@]}" --runtime-dir "$RUNTIME_DIR" --models-dir "$MODELS_DIR"
python3 "$EVAL" port-free --port "$PORT" || die "port $PORT is already in use"
read_memory || die "nvidia-smi memory query failed"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
readonly STAMP
readonly WINDOW_DIR="$STATE_DIR/runs/w-$STAMP"
mkdir -p "$STATE_DIR/runs" # umask 077: every created level is 0700
mkdir -m 700 "$WINDOW_DIR"
WINDOW_START=$(date +%s)
readonly WINDOW_START
readonly WINDOW_END=$((WINDOW_START + WINDOW_SECONDS))
STARTED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
readonly STARTED_UTC

PRODUCTION_INITIAL=none
if [[ $PRODUCTION_UNIT != none ]]; then
  PRODUCTION_INITIAL=$(systemctl --user is-active "$PRODUCTION_UNIT" 2>/dev/null || true)
fi
PRODUCTION_STOPPED=0
FREE_BEFORE=$MEM_FREE FREE_AFTER_STOP=null FREE_AFTER_RESTORE=null
USED_BEFORE=$MEM_USED USED_AFTER_STOP=null USED_AFTER_RESTORE=null
SERVER_PID='' SERVER_UNIT='' GUARD_PID='' GUARD_STOP='' SERVER_EXIT=null CHILD_PID=''

# Long-running helpers run in the background and are waited for, so an INT or
# TERM trap fires at once instead of after the foreground child finishes.
run_child() {
  local rc=0
  "$@" &
  CHILD_PID=$!
  wait "$CHILD_PID" || rc=$?
  CHILD_PID=''
  return "$rc"
}

stop_arm_processes() {
  if [[ -n $CHILD_PID ]]; then
    kill -TERM "$CHILD_PID" 2>/dev/null || true
    wait "$CHILD_PID" 2>/dev/null || true
    CHILD_PID=''
  fi
  if [[ -n $GUARD_PID ]]; then
    if [[ -n $GUARD_STOP ]]; then
      : >"$GUARD_STOP"
    fi
    wait "$GUARD_PID" 2>/dev/null || true
    GUARD_PID=''
  fi
  if [[ -n $SERVER_PID ]]; then
    if [[ -n $SERVER_UNIT ]]; then
      systemctl --user stop "$SERVER_UNIT" >/dev/null 2>&1 || true
    fi
    kill -TERM "$SERVER_PID" 2>/dev/null || true
    if wait "$SERVER_PID" 2>/dev/null; then
      SERVER_EXIT=0
    else
      SERVER_EXIT=$?
    fi
    SERVER_PID='' SERVER_UNIT=''
  fi
}

json_events() {
  local file=$1 out='' line
  if [[ -f $file ]]; then
    while IFS= read -r line; do
      [[ $line =~ ^[A-Za-z0-9:._-]+$ ]] || line=unrecognized-event
      out+="${out:+,}\"$line\""
    done <"$file"
  fi
  printf '[%s]' "$out"
}

write_arm_json() {
  local dir=$1 arm=$2 status=$3 required=$4 free=$5 cold=$6 verified=$7 started=$8 after=$9
  printf '{"schema_version":1,"kind":"local_inference_latest_window_arm","window":"w-%s","arm":"%s","status":"%s","admission_required_mib":%s,"admission_free_mib":%s,"free_mib_after_stop":%s,"cold_load_ms":%s,"server_exit":%s,"memory_max":"%s","memory_max_verified":%s,"guard_events":%s,"started_utc":"%s","finished_utc":"%s"}\n' \
    "$STAMP" "$arm" "$status" "$required" "$free" "$after" "$cold" "$SERVER_EXIT" "$MEMORY_MAX" "$verified" \
    "$(json_events "$dir/events.txt")" "$started" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$dir/window.json"
}

write_summary() {
  local rc=$1 health=$2
  printf '{"schema_version":1,"kind":"local_inference_latest_window","window":"w-%s","arms":"%s","production_unit":"%s","production_initial_state":"%s","production_stopped":%s,"production_health":"%s","free_mib_before":%s,"used_mib_before":%s,"free_mib_after_stop":%s,"used_mib_after_stop":%s,"free_mib_after_restore":%s,"used_mib_after_restore":%s,"window_seconds":%s,"started_utc":"%s","finished_utc":"%s","exit_code":%s}\n' \
    "$STAMP" "$ARMS_CSV" "$PRODUCTION_UNIT" "$PRODUCTION_INITIAL" "$PRODUCTION_STOPPED" "$health" \
    "$FREE_BEFORE" "$USED_BEFORE" "$FREE_AFTER_STOP" "$USED_AFTER_STOP" "$FREE_AFTER_RESTORE" \
    "$USED_AFTER_RESTORE" "$WINDOW_SECONDS" "$STARTED_UTC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc" \
    >"$WINDOW_DIR/window-summary.json"
}

cleanup() {
  local rc=$? health=not-stopped
  trap - EXIT
  trap '' INT TERM # finish restoring production; SIGKILL remains the operator's override
  set +e
  stop_arm_processes
  if ((PRODUCTION_STOPPED)); then
    systemctl --user start "$PRODUCTION_UNIT"
    if run_child python3 "$EVAL" wait-health --url "$PRODUCTION_HEALTH" --timeout "$STARTUP_SECONDS"; then
      health=ok
    else
      health=failed
      rc=1
      printf 'window: %s did not return /health 200 after restart\n' "$PRODUCTION_UNIT" >&2
    fi
  fi
  if read_memory; then
    FREE_AFTER_RESTORE=$MEM_FREE
    USED_AFTER_RESTORE=$MEM_USED
  fi
  write_summary "$rc" "$health"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

guard_loop() {
  local dir=$1 line used free
  while [[ ! -e $GUARD_STOP ]]; do
    if line=$("$NVSMI" --query-gpu=memory.used,memory.free --format=csv,noheader,nounits --id=0 2>/dev/null) &&
      IFS=', ' read -r used free <<<"$line" && [[ $used =~ ^[0-9]+$ && $free =~ ^[0-9]+$ ]]; then
      printf '%s,%s,%s\n' "$(date +%s%3N)" "$used" "$free" >>"$dir/memory.csv"
      if ((free < MINIMUM_FREE_MIB)); then
        echo device-memory-reserve-breached >>"$dir/events.txt"
        break
      fi
    else
      echo memory-monitor-failed >>"$dir/events.txt"
      break
    fi
    sleep 1
  done
  if [[ ! -e $GUARD_STOP ]]; then
    systemctl --user kill --signal=SIGTERM "$SERVER_UNIT" >/dev/null 2>&1 || true
    kill -TERM "$SERVER_PID" 2>/dev/null || true
  fi
}

verify_memory_max() {
  local value
  for _ in {1..20}; do
    value=$(systemctl --user show -p MemoryMax --value "$SERVER_UNIT" 2>/dev/null || true)
    if [[ $value == "$MEMORY_MAX_BYTES" ]]; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

classify_startup() {
  local dir=$1 log="$1/server.private.log" event=startup-failed
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    event=startup-deadline
  elif grep -qi 'unknown model architecture' "$log"; then
    event=runtime-unsupported-architecture
  elif grep -qiE 'failed to load draft model|failed to create MTP context' "$log"; then
    event=runtime-unsupported-draft
  elif grep -qiE 'invalid ggml type|unknown (tensor )?type' "$log"; then
    event=runtime-unsupported-type
  elif grep -qiE 'out of memory|cudaMalloc failed' "$log"; then
    event=device-memory-oom
  fi
  echo "$event" >>"$dir/events.txt"
}

run_arm() {
  local arm=$1 budget=$2 dir required status=completed cold=null verified=false started t0 deadline
  local free=null after=null lower
  local -a argv=()
  dir="$WINDOW_DIR/$arm"
  mkdir -m 700 "$dir" "$dir/home"
  : >"$dir/events.txt"
  started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  SERVER_EXIT=null
  required=$(python3 "$EVAL" admission --plan "$PLAN" --arm "$arm")
  if ((required < ADMISSION_FLOOR_MIB)); then
    write_arm_json "$dir" "$arm" plan-error "$required" "$free" "$cold" "$verified" "$started" "$after"
    return 0
  fi
  if ! read_memory; then
    echo memory-monitor-failed >>"$dir/events.txt"
    write_arm_json "$dir" "$arm" memory-query-failed "$required" "$free" "$cold" "$verified" "$started" "$after"
    return 0
  fi
  free=$MEM_FREE
  if ((free < required)); then
    write_arm_json "$dir" "$arm" admission-refused "$required" "$free" "$cold" "$verified" "$started" "$after"
    return 0
  fi
  mapfile -d '' -t argv < <(python3 "$EVAL" argv --plan "$PLAN" --arm "$arm" --runtime-dir "$RUNTIME_DIR" --models-dir "$MODELS_DIR")
  if ((${#argv[@]} == 0)); then
    write_arm_json "$dir" "$arm" argv-failed "$required" "$free" "$cold" "$verified" "$started" "$after"
    return 0
  fi
  lower=$(printf '%s' "$arm" | tr '[:upper:]' '[:lower:]')
  SERVER_UNIT="li26-$lower-$STAMP.scope"
  GUARD_STOP="$dir/guard.stop"
  t0=$(date +%s%3N)
  systemd-run --user --scope --quiet --collect --unit="${SERVER_UNIT%.scope}" \
    -p MemoryMax="$MEMORY_MAX" -p MemorySwapMax=0 -- \
    env -i PATH=/usr/bin:/bin HOME="$dir/home" CUDA_VISIBLE_DEVICES=0 LD_LIBRARY_PATH="$RUNTIME_DIR" \
    "${argv[@]}" >"$dir/server.private.log" 2>&1 &
  SERVER_PID=$!
  guard_loop "$dir" &
  GUARD_PID=$!
  if verify_memory_max; then
    verified=true
  else
    status=memory-limit-unverified
    echo memory-limit-unverified >>"$dir/events.txt"
  fi
  if [[ $status == completed ]]; then
    if run_child python3 "$EVAL" wait-health --url "http://127.0.0.1:$PORT/health" \
      --timeout "$STARTUP_SECONDS" --pid "$SERVER_PID"; then
      cold=$(($(date +%s%3N) - t0))
      deadline=$((t0 / 1000 + budget))
      if ! run_child python3 "$EVAL" run --plan "$PLAN" --arm "$arm" --acquisition "$ACQUISITION" \
        --inputs-sha256 "$INPUTS_SHA256" --endpoint "http://127.0.0.1:$PORT" \
        --out "$dir/eval" --deadline-epoch "$deadline"; then
        status=eval-stopped
      fi
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo server-exited >>"$dir/events.txt"
        status=server-exited
      fi
    else
      status=startup-failed
      classify_startup "$dir"
    fi
  fi
  stop_arm_processes
  if read_memory; then
    after=$MEM_FREE
  fi
  write_arm_json "$dir" "$arm" "$status" "$required" "$free" "$cold" "$verified" "$started" "$after"
}

if [[ $PRODUCTION_UNIT != none ]]; then
  PRODUCTION_STOPPED=1 # set first: an interrupted stop is still restarted by the trap
  systemctl --user stop "$PRODUCTION_UNIT"
  sleep 5
  if read_memory; then
    FREE_AFTER_STOP=$MEM_FREE
    USED_AFTER_STOP=$MEM_USED
  fi
fi

for arm in "${ARMS[@]}"; do
  budget=$((WINDOW_END - RESTORE_RESERVE_SECONDS - $(date +%s)))
  if ((budget < MINIMUM_ARM_SECONDS)); then
    mkdir -m 700 "$WINDOW_DIR/$arm"
    SERVER_EXIT=null
    echo window-deadline >>"$WINDOW_DIR/$arm/events.txt"
    write_arm_json "$WINDOW_DIR/$arm" "$arm" window-deadline null null null false \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" null
    continue
  fi
  if ((budget > ARM_SECONDS)); then
    budget=$ARM_SECONDS
  fi
  run_arm "$arm" "$budget"
done
