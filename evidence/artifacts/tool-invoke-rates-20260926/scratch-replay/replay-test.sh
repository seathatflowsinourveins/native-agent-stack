#!/usr/bin/env bash
# u6 replay test (parameterized copy of the scratch harness that produced replay-receipt.json; see ../README.md).
#
# 1. otelcol-contrib validate on this checkout's collector.yaml (pinned 0.161.0).
# 2. A scratch logs-only Collector, built from the SAME logs-pipeline processors (copied verbatim from
#    collector.yaml), replays: your own capture files (if you pass any) plus this file's synthetic sentinel
#    records; a file exporter writes the result, and the assertions compare it with the inputs. With no capture
#    files, the synthetic-only path uses a recent default timestamp and synthetic assertions.
#    Historical-count assertions require the complete A/B/C/Codex capture set.
# 3. Unless --no-loki: a scratch Loki (pinned 3.7.8, the repo's own ecosystem-loki template on scratch ports)
#    receives the same export, and every invoke-rate dashboard target is evaluated there and compared with the
#    exported file. With the complete historical capture set, prove_check.py's live-scenario checks also run.
#
# USAGE: REPO=/path/to/this/checkout ./replay-test.sh [--no-loki] [capture-file ...]
#   REPO             required: a checkout of this repository (this PR or later). No path in this script is
#                     specific to any one machine or session.
#   capture-file ...  optional: your own real OTLP/JSON export files (Claude/Codex file-exporter captures,
#                     never included in this receipt -- see ../README.md for why). With none given, this
#                     script passes --synthetic with no input files. Empty input files also work.
# Env: TOOLS_DIR (default: ~/.local/share/codex-ecosystem/tools), UV_BIN (default: PATH's uv), PY (override the
#      interpreter list run before design/replay.py, e.g. to skip `uv run`).
# Scratch processes use loopback ports 45700-45799 and are stopped by their literal PIDs. Outputs stay under
# $RUN_DIR (default: a mktemp -d; mode 700): they may include your own capture files' derived output. Prints
# PASS/FAIL per assertion; exit 1 on any FAIL.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${REPO:?set REPO to a checkout of this repository, e.g. REPO=$HOME/code/native-agent-stack}"
[ -f "$REPO/observability/collector/collector.yaml" ] || { echo "FAIL REPO does not look like this repository (no observability/collector/collector.yaml)"; exit 1; }
COLLECTOR_YAML="$REPO/observability/collector/collector.yaml"
DASHBOARD="$REPO/observability/backends/templates/ecosystem-dashboard.json.example"
LOKI_TEMPLATE="$REPO/observability/backends/templates/ecosystem-loki.yml.example"
TOOLS="${TOOLS_DIR:-$HOME/.local/share/codex-ecosystem/tools}"
OTELCOL="${OTELCOL_BIN:-$TOOLS/otelcol-0.161.0/otelcol-contrib}"
LOKI_BIN="${LOKI_BIN:-$TOOLS/ecosystem-loki-3.7.8/loki-linux-amd64}"
UV="${UV_BIN:-$(command -v uv || echo "$HOME/.local/share/codex-ecosystem/bin/uv")}"
PY_DEFAULT=("$UV" run -q --no-project --with pyyaml python "$HERE/replay.py")
read -r -a PY <<<"${PY:-}"
[ "${#PY[@]}" -gt 0 ] || PY=("${PY_DEFAULT[@]}")
WITH_LOKI=1
INPUTS=()
for a in "$@"; do
  if [ "$a" = "--no-loki" ]; then WITH_LOKI=0; else INPUTS+=("$a"); fi
done
RUN_DIR="${RUN_DIR:-$(mktemp -d)}"
umask 077; mkdir -p "$RUN_DIR"; chmod 700 "$RUN_DIR"
if [ "${#INPUTS[@]}" -eq 0 ]; then
  echo "INFO no capture files given: synthetic sentinel records only"
fi

TASK="u6-replay-$(cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen 2>/dev/null || date +%s%N)"
PASS=0; FAIL=0
result() { if [ "$1" = 0 ]; then PASS=$((PASS + 1)); echo "PASS $2"; else FAIL=$((FAIL + 1)); echo "FAIL $2"; fi; }
tally() {
  local line; line=$(grep -E '^SUMMARY ' "$1" | tail -1)
  [ -n "$line" ] || return 0
  PASS=$((PASS + $(sed -E 's/.*: ([0-9]+) passed.*/\1/' <<<"$line"))); FAIL=$((FAIL + $(sed -E 's/.*, ([0-9]+) failed/\1/' <<<"$line")))
}
COLLECTOR_PID=""; LOKI_PID=""
stop() {
  [ -n "$1" ] || return 0
  kill "$1" 2>/dev/null
  for _ in $(seq 1 40); do kill -0 "$1" 2>/dev/null || break; sleep 0.25; done
  if kill -0 "$1" 2>/dev/null; then kill -9 "$1" 2>/dev/null; result 1 "$2 ($1) stopped"; else result 0 "$2 ($1) stopped"; fi
}
trap 'stop "$COLLECTOR_PID" "scratch collector"; stop "$LOKI_PID" "scratch Loki"' EXIT

for f in "$OTELCOL" "$UV" "${INPUTS[@]}" "$COLLECTOR_YAML" "$DASHBOARD"; do
  [ -e "$f" ] || { echo "FAIL missing input: $f"; exit 1; }
done
echo "run dir: $RUN_DIR  otelcol: $("$OTELCOL" --version)"

used=$(ss -ltnH | awk '{print $4}' | sed -E 's/.*:([0-9]+)$/\1/')
PORTS=()
for p in $(seq 45700 45799); do grep -qx "$p" <<<"$used" || PORTS+=("$p"); [ "${#PORTS[@]}" -ge 4 ] && break; done
OTLP_PORT=${PORTS[0]}; HEALTH_PORT=${PORTS[1]}; LOKI_HTTP=${PORTS[2]}; LOKI_GRPC=${PORTS[3]}
echo "ports: otlp=$OTLP_PORT health=$HEALTH_PORT loki_http=$LOKI_HTTP loki_grpc=$LOKI_GRPC"

mkdir -p "$RUN_DIR/validate-data/collector/queue" "$RUN_DIR/validate-data/sdk-receipts"
ECOSYSTEM_OBSERVABILITY_DATA="$RUN_DIR/validate-data" "$OTELCOL" validate --config="$COLLECTOR_YAML" > "$RUN_DIR/validate.log" 2>&1
result $? "otelcol-contrib 0.161.0 validate --config $REPO/observability/collector/collector.yaml"

if [ "$WITH_LOKI" = 1 ] && [ -x "$LOKI_BIN" ] && [ -f "$LOKI_TEMPLATE" ]; then
  sed -e "s#@DATA_ROOT@#$RUN_DIR/loki-data#g" -e "s#http_listen_port: 13100#http_listen_port: $LOKI_HTTP#" \
      -e "s#grpc_listen_port: 19095#grpc_listen_port: $LOKI_GRPC#" "$LOKI_TEMPLATE" > "$RUN_DIR/loki.yml"
  ! grep -qE '13100|19095|@DATA_ROOT@' "$RUN_DIR/loki.yml"
  result $? "scratch Loki config rendered from the repo's own template with scratch ports and data root only"
  "$LOKI_BIN" -config.file="$RUN_DIR/loki.yml" > "$RUN_DIR/loki.log" 2>&1 &
  LOKI_PID=$!
  ready=1
  for _ in $(seq 1 240); do
    [ "$(curl -s --max-time 2 "http://127.0.0.1:$LOKI_HTTP/ready")" = "ready" ] && { ready=0; break; }
    kill -0 "$LOKI_PID" 2>/dev/null || break
    sleep 0.5
  done
  result $ready "scratch Loki 3.7.8 ready (pid $LOKI_PID)"
  [ $ready = 0 ] || exit 1
else
  WITH_LOKI=0
  [ -x "$LOKI_BIN" ] && [ -f "$LOKI_TEMPLATE" ] || echo "SKIP scratch Loki (--no-loki, or LOKI_BIN/LOKI_TEMPLATE not found -- set TOOLS_DIR / OTELCOL_BIN / LOKI_BIN, or pass --no-loki explicitly)"
fi
LOKI_ARG=(); [ "$WITH_LOKI" = 1 ] && LOKI_ARG=(--loki-port "$LOKI_HTTP")

"${PY[@]}" receipts --dir "$RUN_DIR/sdk-receipts" > "$RUN_DIR/receipts.log" 2>&1
grep -E '^(PASS|FAIL) ' "$RUN_DIR/receipts.log"; tally "$RUN_DIR/receipts.log"
"${PY[@]}" build-config --collector "$COLLECTOR_YAML" --out "$RUN_DIR/collector.yaml" --otlp-port "$OTLP_PORT" \
  --health-port "$HEALTH_PORT" --file "$RUN_DIR/out-logs.json" --receipts-dir "$RUN_DIR/sdk-receipts" \
  --receipts-file "$RUN_DIR/out-receipts.json" "${LOKI_ARG[@]}" > "$RUN_DIR/build.log" 2>&1
grep -E '^(PASS|FAIL) ' "$RUN_DIR/build.log"; tally "$RUN_DIR/build.log"
grep -q '^SUMMARY' "$RUN_DIR/build.log" || { FAIL=$((FAIL + 1)); echo "FAIL config builder crashed (see $RUN_DIR/build.log)"; }
"$OTELCOL" validate --config="$RUN_DIR/collector.yaml" > "$RUN_DIR/validate-scratch.log" 2>&1
result $? "otelcol-contrib validate --config scratch replay config"
"$OTELCOL" --config="$RUN_DIR/collector.yaml" > "$RUN_DIR/collector.log" 2>&1 &
COLLECTOR_PID=$!
ready=1
for _ in $(seq 1 120); do
  curl -sf --max-time 2 "http://127.0.0.1:$HEALTH_PORT/" > /dev/null && { ready=0; break; }
  kill -0 "$COLLECTOR_PID" 2>/dev/null || break
  sleep 0.25
done
result $ready "scratch collector ready (pid $COLLECTOR_PID)"
[ "$ready" = 0 ] || exit 1

"${PY[@]}" post --port "$OTLP_PORT" --tags "$RUN_DIR/tags.json" --task-id "$TASK" --synthetic "${INPUTS[@]}" > "$RUN_DIR/post.log" 2>&1
result $? "replay posted: $(grep -E '^posted' "$RUN_DIR/post.log")"
prev=-1
for i in $(seq 1 40); do
  cur=$(stat -c %s "$RUN_DIR/out-logs.json" 2>/dev/null || echo 0)
  [ "$cur" = "$prev" ] && [ "$i" -gt 6 ] && break
  prev=$cur; sleep 0.5
done
stop "$COLLECTOR_PID" "scratch collector"; COLLECTOR_PID=""
! grep -qiE 'error|panic' "$RUN_DIR/collector.log"
result $? "scratch collector log has no errors ($(wc -l < "$RUN_DIR/collector.log") lines)"

"${PY[@]}" assert-receipts --out "$RUN_DIR/out-receipts.json" > "$RUN_DIR/assert-receipts.log" 2>&1
grep -E '^(PASS|FAIL) ' "$RUN_DIR/assert-receipts.log"; tally "$RUN_DIR/assert-receipts.log"
grep -q '^SUMMARY' "$RUN_DIR/assert-receipts.log" || { FAIL=$((FAIL + 1)); echo "FAIL receipt assertions crashed"; }

"${PY[@]}" assert --out "$RUN_DIR/out-logs.json" --tags "$RUN_DIR/tags.json" --collector "$COLLECTOR_YAML" "${INPUTS[@]}" \
  > "$RUN_DIR/assert.log" 2>&1
grep -E '^(PASS|FAIL|INFO) ' "$RUN_DIR/assert.log"; tally "$RUN_DIR/assert.log"
grep -q '^SUMMARY' "$RUN_DIR/assert.log" || { FAIL=$((FAIL + 1)); echo "FAIL assertion harness crashed (see $RUN_DIR/assert.log)"; }

if [ "$WITH_LOKI" = 1 ]; then
  "${PY[@]}" loki --port "$LOKI_HTTP" --collector "$COLLECTOR_YAML" --out "$RUN_DIR/out-logs.json" --dashboard "$DASHBOARD" \
    --window 3h > "$RUN_DIR/loki-check.log" 2>&1
  grep -E '^(PASS|FAIL) ' "$RUN_DIR/loki-check.log"; tally "$RUN_DIR/loki-check.log"
  grep -q '^SUMMARY' "$RUN_DIR/loki-check.log" || { FAIL=$((FAIL + 1)); echo "FAIL Loki harness crashed (see $RUN_DIR/loki-check.log)"; }
  if grep -qx 'INFO historical capture set: present' "$RUN_DIR/post.log"; then
    "${PY[@]}" forbidden --out "$RUN_DIR/forbidden.txt" "${INPUTS[@]}" > "$RUN_DIR/forbidden.log" 2>&1
    grep -E '^(PASS|FAIL) ' "$RUN_DIR/forbidden.log"; tally "$RUN_DIR/forbidden.log"
    "${PY[@]:0:${#PY[@]}-1}" "$HERE/../checker-fix/prove_check.py" "http://127.0.0.1:$LOKI_HTTP" "$TASK" 30 --window 3h \
      --forbidden-file "$RUN_DIR/forbidden.txt" --collector "$COLLECTOR_YAML" > "$RUN_DIR/prove-check.log" 2>&1
    grep -E '^(PASS|FAIL|INFO) ' "$RUN_DIR/prove-check.log" | sed -E 's/^(PASS|FAIL|INFO) /\1 [fixed checker on scratch Loki] /'
    tally "$RUN_DIR/prove-check.log"
    grep -q '^SUMMARY' "$RUN_DIR/prove-check.log" || { FAIL=$((FAIL + 1)); echo "FAIL prove_check crashed (see $RUN_DIR/prove-check.log)"; }
  else
    echo "SKIP live-proof scenario checks: complete historical capture set absent; synthetic dashboard assertions run above"
  fi
  stop "$LOKI_PID" "scratch Loki"; LOKI_PID=""
else
  echo "SKIP scratch Loki dashboard queries (--no-loki or Loki binary/template missing)"
fi

left=$(ss -ltnH | awk '{print $4}' | grep -cE ":($OTLP_PORT|$HEALTH_PORT|$LOKI_HTTP|$LOKI_GRPC)\$")
result "$left" "no scratch listener left on the replay ports"
echo "TOTAL: $PASS passed, $FAIL failed"
echo "run directory kept at: $RUN_DIR"
[ "$FAIL" = 0 ]
