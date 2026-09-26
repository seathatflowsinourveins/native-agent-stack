#!/usr/bin/env bash
# One frozen GPU window for blueprints/convergence-practice/local-inference-latest-20260926.
# Preregistered; the change that adds it does not run it. Read README.md first.
#
#   window.sh --arms C0[,C1,C2,M] --acquisition DIR --inputs-sha256 HEX \
#             --runtime-dir DIR --models-dir DIR --state-dir DIR \
#             [--production-unit nativestack-generation.service|none]
#
# Before touching anything it checks the coordination line, every frozen hash,
# the acquisition, runtime and model files, each arm's next segment and the
# free device memory predicted once production stops. It then arms a transient
# timer that restores production at the window deadline even if this script
# hangs or is killed, stops only the production generation unit, and runs one
# segment of each named arm on 127.0.0.1:18299 in its own systemd scope with a
# host-memory cap. A 1 Hz guard with bounded queries stops only that scope below
# the device reserve. The exit trap stops the arm, starts the production unit
# again, waits for /health 200 and cancels the timer; every step in it is
# bounded. It never closes Windows applications, never touches other units and
# never runs wsl --terminate or --shutdown.
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
readonly ARM_SECONDS=9600
readonly STARTUP_SECONDS=300
readonly RESTORE_RESERVE_SECONDS=900
readonly MINIMUM_SEGMENT_SECONDS=1200
readonly QUERY_TIMEOUT_SECONDS=10
readonly STOP_TIMEOUT_SECONDS=120
readonly GUARD_WAIT_SECONDS=15
readonly SETTLE_SECONDS=5
readonly MEMORY_MAX=20G
readonly MEMORY_MAX_BYTES=21474836480
readonly COORDINATION_LINE='GPU trials: TRIALS DONE'
readonly PRODUCTION_UNIT_NAME=nativestack-generation.service
readonly PRODUCTION_HEALTH=http://127.0.0.1:18232/health

die() {
  printf 'window: %s\n' "$*" >&2
  exit 2
}

need_value() {
  (($1 >= 2)) || die "$2 needs a value"
}

ARMS_CSV='' ACQUISITION='' INPUTS_SHA256='' RUNTIME_DIR='' MODELS_DIR='' STATE_DIR=''
PRODUCTION_UNIT=$PRODUCTION_UNIT_NAME
while (($#)); do
  case $1 in
    --arms) need_value $# "$1"; ARMS_CSV=$2; shift 2 ;;
    --acquisition) need_value $# "$1"; ACQUISITION=$2; shift 2 ;;
    --inputs-sha256) need_value $# "$1"; INPUTS_SHA256=$2; shift 2 ;;
    --runtime-dir) need_value $# "$1"; RUNTIME_DIR=$2; shift 2 ;;
    --models-dir) need_value $# "$1"; MODELS_DIR=$2; shift 2 ;;
    --state-dir) need_value $# "$1"; STATE_DIR=$2; shift 2 ;;
    --production-unit) need_value $# "$1"; PRODUCTION_UNIT=$2; shift 2 ;;
    *) die "unknown argument: $1" ;;
  esac
done
# The only unit this script may ever stop; checked before anything else runs.
case $PRODUCTION_UNIT in
  "$PRODUCTION_UNIT_NAME" | none) ;;
  *) die "--production-unit must be $PRODUCTION_UNIT_NAME or none; no other unit is ever stopped" ;;
esac
readonly PRODUCTION_UNIT
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

NVSMI=$(command -v nvidia-smi || true)
if [[ -z $NVSMI && -x /usr/lib/wsl/lib/nvidia-smi ]]; then
  NVSMI=/usr/lib/wsl/lib/nvidia-smi
fi
readonly NVSMI

# Every device-memory query is bounded; a hung nvidia-smi is a failed query.
query_memory() {
  local line used free
  line=$(timeout --kill-after=2 "$QUERY_TIMEOUT_SECONDS" "$NVSMI" --query-gpu=memory.used,memory.free \
    --format=csv,noheader,nounits --id=0 2>/dev/null) || return 1
  IFS=', ' read -r used free <<<"$line"
  [[ $used =~ ^[0-9]+$ && $free =~ ^[0-9]+$ ]] || return 1
  printf '%s %s\n' "$used" "$free"
}

MEM_USED='' MEM_FREE=''
read_memory() {
  local out
  out=$(query_memory) || return 1
  read -r MEM_USED MEM_FREE <<<"$out"
}

scope_name() {
  printf 'li26-%s-%s.scope' "${1,,}" "$STAMP"
}

# --- preflight: nothing is stopped until all of this passes ----------------
grep -qxF "$COORDINATION_LINE" "$HERE/README.md" ||
  die "README.md does not contain the line '$COORDINATION_LINE'; another session owns GPU trials"
for tool in systemd-run systemctl timeout flock pkill; do
  command -v "$tool" >/dev/null || die "$tool not found"
done
[[ -n $NVSMI && -x $NVSMI ]] || die "nvidia-smi not found"
mkdir -p "$STATE_DIR/runs" # umask 077: every created level is 0700
exec 9>"$STATE_DIR/window.lock"
flock -n 9 || die "another window holds $STATE_DIR/window.lock"
python3 "$EVAL" verify-frozen --plan "$PLAN"
python3 "$EVAL" verify-inputs --acquisition "$ACQUISITION" --inputs-sha256 "$INPUTS_SHA256"
arm_args=()
for arm in "${ARMS[@]}"; do
  arm_args+=(--arm "$arm")
done
python3 "$EVAL" verify-arms --plan "$PLAN" "${arm_args[@]}" --runtime-dir "$RUNTIME_DIR" --models-dir "$MODELS_DIR"
python3 "$EVAL" port-free --port "$PORT" || die "port $PORT is already in use"
declare -A SEGMENT=() PREVIOUS=()
for arm in "${ARMS[@]}"; do
  answer=$(python3 "$EVAL" next-segment --plan "$PLAN" --state-dir "$STATE_DIR" --arm "$arm") ||
    die "arm $arm cannot run in this window"
  read -r number previous <<<"$answer"
  [[ $number =~ ^[1-9]$ && ($previous == - || $previous =~ ^w-[0-9]{8}T[0-9]{6}Z$) ]] ||
    die "unexpected next-segment answer for arm $arm"
  SEGMENT[$arm]=$number
  PREVIOUS[$arm]=${previous#-}
done
PRODUCTION_INITIAL=none
if [[ $PRODUCTION_UNIT != none ]]; then
  PRODUCTION_INITIAL=$(timeout --kill-after=5 30 systemctl --user is-active "$PRODUCTION_UNIT" 2>/dev/null || true)
fi
readonly PRODUCTION_INITIAL
read_memory || die "nvidia-smi memory query failed"
production_active=0
if [[ $PRODUCTION_INITIAL == active ]]; then
  production_active=1
fi
python3 "$EVAL" predict --plan "$PLAN" "${arm_args[@]}" --free "$MEM_FREE" --production-active "$production_active" ||
  die "predicted free device memory after stopping production is below these arms' admission threshold; close Windows-side GPU applications first (README step 3) or run fewer arms"

# --- the window -------------------------------------------------------------
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
readonly STAMP
readonly WINDOW_DIR="$STATE_DIR/runs/w-$STAMP"
readonly RESTORE_UNIT="li26-restore-$STAMP"
mkdir -m 700 "$WINDOW_DIR"
WINDOW_START=$(date +%s)
readonly WINDOW_START
readonly WINDOW_END=$((WINDOW_START + WINDOW_SECONDS))
STARTED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
readonly STARTED_UTC

PRODUCTION_STOPPED=0 RESTORE_STATE=not-armed
FREE_BEFORE=$MEM_FREE FREE_AFTER_STOP=null FREE_AFTER_RESTORE=null
USED_BEFORE=$MEM_USED USED_AFTER_STOP=null USED_AFTER_RESTORE=null
SERVER_PID='' SERVER_UNIT='' GUARD_PID='' GUARD_STOP='' CHILD_PID=''
CURRENT_ARM='' CURRENT_DIR='' CURRENT_STARTED=''

reset_arm_fields() {
  ARM_REQUIRED=null ARM_FREE=null ARM_AFTER=null ARM_COLD=null ARM_VERIFIED=false
  SERVER_EXIT=null SERVER_STARTED_MS=null MONITOR_STOPPED_MS=null SERVER_LAUNCHED=0
}
reset_arm_fields

# Waits at most $2 seconds for process $1 to end (bash reaps its children itself).
wait_gone() {
  local pid=$1 limit=$((SECONDS + $2))
  while kill -0 "$pid" 2>/dev/null; do
    ((SECONDS < limit)) || return 1
    sleep 0.2
  done
}

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

stop_child() {
  local pid=$CHILD_PID
  [[ -n $pid ]] || return 0
  CHILD_PID=''
  kill -TERM "$pid" 2>/dev/null || true
  if ! wait_gone "$pid" 30; then
    kill -KILL "$pid" 2>/dev/null || true
    wait_gone "$pid" 5 || return 0
  fi
  wait "$pid" 2>/dev/null || true
}

stop_guard() {
  local pid=$GUARD_PID
  [[ -n $pid ]] || return 0
  GUARD_PID=''
  if [[ -n $GUARD_STOP ]]; then
    : >"$GUARD_STOP"
  fi
  MONITOR_STOPPED_MS=$(date +%s%3N)
  if ! wait_gone "$pid" "$GUARD_WAIT_SECONDS"; then
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
    if ! wait_gone "$pid" 5; then
      kill -KILL "$pid" 2>/dev/null || true
      wait_gone "$pid" 5 || return 0
    fi
  fi
  wait "$pid" 2>/dev/null || true
}

stop_server() {
  local pid=$SERVER_PID unit=$SERVER_UNIT
  [[ -n $pid ]] || return 0
  SERVER_PID='' SERVER_UNIT=''
  timeout --kill-after=5 "$STOP_TIMEOUT_SECONDS" systemctl --user stop "$unit" >/dev/null 2>&1 || true
  kill -TERM "$pid" 2>/dev/null || true
  if ! wait_gone "$pid" 60; then
    kill -KILL "$pid" 2>/dev/null || true
    if ! wait_gone "$pid" 10; then
      echo server-stop-failed >>"$CURRENT_DIR/events.txt"
      return 0
    fi
  fi
  if wait "$pid" 2>/dev/null; then
    SERVER_EXIT=0
  else
    SERVER_EXIT=$?
  fi
}

stop_arm_processes() {
  stop_child
  stop_guard
  stop_server
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
  local status=$1 previous=null
  if [[ -n ${PREVIOUS[$CURRENT_ARM]} ]]; then
    previous="\"${PREVIOUS[$CURRENT_ARM]}\""
  fi
  printf '{"schema_version":1,"kind":"local_inference_latest_window_arm","window":"w-%s","arm":"%s","segment":%s,"previous_window":%s,"status":"%s","admission_required_mib":%s,"free_mib_at_admission":%s,"free_mib_after_arm":%s,"cold_load_ms":%s,"server_started_ms":%s,"monitor_stopped_ms":%s,"server_exit":%s,"memory_max":"%s","memory_max_verified":%s,"guard_events":%s,"started_utc":"%s","finished_utc":"%s"}\n' \
    "$STAMP" "$CURRENT_ARM" "${SEGMENT[$CURRENT_ARM]}" "$previous" "$status" "$ARM_REQUIRED" "$ARM_FREE" \
    "$ARM_AFTER" "$ARM_COLD" "$SERVER_STARTED_MS" "$MONITOR_STOPPED_MS" "$SERVER_EXIT" "$MEMORY_MAX" \
    "$ARM_VERIFIED" "$(json_events "$CURRENT_DIR/events.txt")" "$CURRENT_STARTED" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$CURRENT_DIR/window.json.tmp"
  mv -f "$CURRENT_DIR/window.json.tmp" "$CURRENT_DIR/window.json"
}

begin_arm() {
  CURRENT_ARM=$1
  CURRENT_DIR="$WINDOW_DIR/$1"
  CURRENT_STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  reset_arm_fields
  mkdir -m 700 "$CURRENT_DIR" "$CURRENT_DIR/home"
  : >"$CURRENT_DIR/events.txt"
  write_arm_json pending
}

finish_arm() {
  write_arm_json "$1"
  CURRENT_ARM='' CURRENT_DIR=''
}

write_summary() {
  local rc=$1 health=$2
  printf '{"schema_version":1,"kind":"local_inference_latest_window","window":"w-%s","arms":"%s","production_unit":"%s","production_initial_state":"%s","production_stopped":%s,"production_health":"%s","restore_timer":"%s","free_mib_before":%s,"used_mib_before":%s,"free_mib_after_stop":%s,"used_mib_after_stop":%s,"free_mib_after_restore":%s,"used_mib_after_restore":%s,"window_seconds":%s,"started_utc":"%s","finished_utc":"%s","exit_code":%s}\n' \
    "$STAMP" "$ARMS_CSV" "$PRODUCTION_UNIT" "$PRODUCTION_INITIAL" "$PRODUCTION_STOPPED" "$health" \
    "$RESTORE_STATE" "$FREE_BEFORE" "$USED_BEFORE" "$FREE_AFTER_STOP" "$USED_AFTER_STOP" \
    "$FREE_AFTER_RESTORE" "$USED_AFTER_RESTORE" "$WINDOW_SECONDS" "$STARTED_UTC" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc" >"$WINDOW_DIR/window-summary.json"
}

cleanup() {
  local rc=$? health=not-stopped
  trap - EXIT
  trap '' INT TERM # every step below is bounded; SIGKILL stays the override and the restore timer still fires
  set +e
  if [[ -n $CURRENT_ARM ]]; then
    stop_arm_processes
    if ((SERVER_LAUNCHED)); then
      echo interrupted >>"$CURRENT_DIR/events.txt"
      if read_memory; then
        ARM_AFTER=$MEM_FREE
      fi
      finish_arm interrupted
    else
      finish_arm not-started-interrupted
    fi
  fi
  if ((PRODUCTION_STOPPED)); then
    timeout --kill-after=5 "$STOP_TIMEOUT_SECONDS" systemctl --user start "$PRODUCTION_UNIT"
    if timeout --kill-after=5 $((STARTUP_SECONDS + 30)) \
      python3 "$EVAL" wait-health --url "$PRODUCTION_HEALTH" --timeout "$STARTUP_SECONDS"; then
      health=ok
    else
      health=failed
      rc=1
      printf 'window: %s did not return /health 200 after restart\n' "$PRODUCTION_UNIT" >&2
    fi
  fi
  if [[ $RESTORE_STATE == armed ]]; then
    if timeout --kill-after=5 "$STOP_TIMEOUT_SECONDS" systemctl --user stop "$RESTORE_UNIT.timer"; then
      RESTORE_STATE=cancelled
    else
      RESTORE_STATE=cancel-failed
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
  local dir=$1 out used free
  while [[ ! -e $GUARD_STOP ]]; do
    if out=$(query_memory); then
      read -r used free <<<"$out"
      printf '%s,%s,%s\n' "$(date +%s%3N)" "$used" "$free" >>"$dir/memory.csv"
      if ((free < MINIMUM_FREE_MIB)); then
        echo device-memory-reserve-breached >>"$dir/events.txt"
        break
      fi
    else
      if [[ -e $GUARD_STOP ]]; then
        break
      fi
      echo memory-monitor-failed >>"$dir/events.txt"
      break
    fi
    sleep 1
  done
  if [[ ! -e $GUARD_STOP ]]; then
    timeout --kill-after=5 30 systemctl --user kill --signal=SIGTERM "$SERVER_UNIT" >/dev/null 2>&1 || true
    kill -TERM "$SERVER_PID" 2>/dev/null || true
  fi
}

verify_memory_max() {
  local value
  for _ in {1..20}; do
    value=$(timeout --kill-after=5 10 systemctl --user show -p MemoryMax --value "$SERVER_UNIT" 2>/dev/null || true)
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
  elif grep -qiE 'failed to create MTP context' "$log"; then
    event=runtime-unsupported-draft
  elif grep -qiE 'invalid ggml type|unknown (tensor )?type' "$log"; then
    event=runtime-unsupported-type
  elif grep -qiE 'out of memory|cudaMalloc failed' "$log"; then
    event=device-memory-oom
  fi
  echo "$event" >>"$dir/events.txt"
}

run_arm() {
  local arm=$1 budget=$2 status=running rc deadline t0
  local -a argv=() eval_args=()
  begin_arm "$arm"
  if ! ARM_REQUIRED=$(python3 "$EVAL" admission --plan "$PLAN" --arm "$arm") ||
    ! [[ $ARM_REQUIRED =~ ^[0-9]+$ ]] || ((ARM_REQUIRED < ADMISSION_FLOOR_MIB)); then
    ARM_REQUIRED=null
    finish_arm plan-error
    return 0
  fi
  if ! read_memory; then
    finish_arm memory-query-failed
    return 0
  fi
  ARM_FREE=$MEM_FREE
  if ((ARM_FREE < ARM_REQUIRED)); then
    finish_arm admission-refused
    return 0
  fi
  mapfile -d '' -t argv < <(python3 "$EVAL" argv --plan "$PLAN" --arm "$arm" --runtime-dir "$RUNTIME_DIR" --models-dir "$MODELS_DIR")
  if ((${#argv[@]} == 0)); then
    finish_arm argv-failed
    return 0
  fi
  SERVER_UNIT=$(scope_name "$arm")
  GUARD_STOP="$CURRENT_DIR/guard.stop"
  write_arm_json running
  t0=$(date +%s%3N)
  SERVER_STARTED_MS=$t0
  SERVER_LAUNCHED=1
  systemd-run --user --scope --quiet --collect --unit="${SERVER_UNIT%.scope}" \
    -p MemoryMax="$MEMORY_MAX" -p MemorySwapMax=0 -- \
    env -i PATH=/usr/bin:/bin HOME="$CURRENT_DIR/home" CUDA_VISIBLE_DEVICES=0 LD_LIBRARY_PATH="$RUNTIME_DIR" \
    "${argv[@]}" >"$CURRENT_DIR/server.private.log" 2>&1 9>&- &
  SERVER_PID=$!
  guard_loop "$CURRENT_DIR" 9>&- &
  GUARD_PID=$!
  if verify_memory_max; then
    ARM_VERIFIED=true
  else
    status=memory-limit-unverified
    echo memory-limit-unverified >>"$CURRENT_DIR/events.txt"
  fi
  if [[ $status == running ]]; then
    if run_child timeout --kill-after=5 $((STARTUP_SECONDS + 30)) python3 "$EVAL" wait-health \
      --url "http://127.0.0.1:$PORT/health" --timeout "$STARTUP_SECONDS" --pid "$SERVER_PID"; then
      ARM_COLD=$(($(date +%s%3N) - t0))
      deadline=$((t0 / 1000 + budget))
      eval_args=(run --plan "$PLAN" --arm "$arm" --acquisition "$ACQUISITION" --inputs-sha256 "$INPUTS_SHA256"
        --endpoint "http://127.0.0.1:$PORT" --out "$CURRENT_DIR/eval" --deadline-epoch "$deadline"
        --segment "${SEGMENT[$arm]}")
      if [[ -n ${PREVIOUS[$arm]} ]]; then
        eval_args+=(--previous "$STATE_DIR/runs/${PREVIOUS[$arm]}/$arm/eval")
      fi
      rc=0
      run_child timeout --kill-after=10 $((deadline - $(date +%s) + 120)) python3 "$EVAL" "${eval_args[@]}" || rc=$?
      case $rc in
        0) status=completed ;;
        4) status=segment-boundary ;;
        *) status=eval-stopped ;;
      esac
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo server-exited >>"$CURRENT_DIR/events.txt"
        status=server-exited
      fi
    else
      status=startup-failed
      classify_startup "$CURRENT_DIR"
    fi
  fi
  stop_arm_processes
  if read_memory; then
    ARM_AFTER=$MEM_FREE
  fi
  finish_arm "$status"
}

# The independent deadline: even if this script hangs or is killed, the timer
# stops this window's arm scopes and starts production at the window's end.
restore_command="systemctl --user stop"
for arm in "${ARMS[@]}"; do
  restore_command+=" $(scope_name "$arm")"
done
if [[ $PRODUCTION_UNIT != none ]]; then
  restore_command+="; systemctl --user start $PRODUCTION_UNIT"
fi
timeout --kill-after=5 "$STOP_TIMEOUT_SECONDS" systemd-run --user --quiet --collect --unit="$RESTORE_UNIT" \
  --on-active="${WINDOW_SECONDS}s" --timer-property=AccuracySec=1s -- /bin/sh -c "$restore_command" ||
  die "could not arm the restore timer $RESTORE_UNIT; nothing was stopped"
RESTORE_STATE=armed

if [[ $PRODUCTION_UNIT != none ]]; then
  PRODUCTION_STOPPED=1 # set first: an interrupted stop is still restarted by the trap
  timeout --kill-after=5 "$STOP_TIMEOUT_SECONDS" systemctl --user stop "$PRODUCTION_UNIT" ||
    die "stopping $PRODUCTION_UNIT did not finish"
  sleep "$SETTLE_SECONDS"
  if read_memory; then
    FREE_AFTER_STOP=$MEM_FREE
    USED_AFTER_STOP=$MEM_USED
  fi
fi

for arm in "${ARMS[@]}"; do
  budget=$((WINDOW_END - RESTORE_RESERVE_SECONDS - $(date +%s)))
  if ((budget > ARM_SECONDS)); then
    budget=$ARM_SECONDS
  fi
  if ((budget < MINIMUM_SEGMENT_SECONDS)); then
    begin_arm "$arm"
    finish_arm not-started-window-budget
    continue
  fi
  run_arm "$arm" "$budget"
done
