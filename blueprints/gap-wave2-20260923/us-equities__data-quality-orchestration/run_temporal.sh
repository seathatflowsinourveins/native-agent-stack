#!/usr/bin/env bash
# Start a loopback-only Temporal dev server with a temp sqlite file, drive the
# temporal_arm.py scenarios, restart the server to check history retention,
# scrape its /metrics endpoint, then stop everything.
#   run_temporal.sh <temporal-cli> <venv-python> <work-dir> <grpc-port> <metrics-port>
set -uo pipefail
T=$1; PY=$2; W=$3; GP=$4; MP=$5
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$W"; ADDR=127.0.0.1:$GP
start_server() {
  setsid "$T" server start-dev --headless --ip 127.0.0.1 --port "$GP" --http-port $((GP+1)) \
    --metrics-port "$MP" --db-filename "$W/temporal.db" --log-level warn > "$W/server-$1.log" 2>&1 &
  echo $! > "$W/server.pid"
  for _ in $(seq 1 60); do "$T" operator cluster health --address "$ADDR" >/dev/null 2>&1 && return 0; sleep 0.5; done
  return 1
}
stop_server() { kill -TERM -- "-$(cat "$W/server.pid")" 2>/dev/null; for _ in $(seq 1 40); do kill -0 "$(cat "$W/server.pid")" 2>/dev/null || return 0; sleep 0.5; done; kill -KILL -- "-$(cat "$W/server.pid")" 2>/dev/null; }
echo "run started $(date -u +%FT%TZ)"
"$T" --version
start_server 1 && echo "server 1 healthy"
"$PY" "$HERE/temporal_arm.py" drive --address "$ADDR" --temporal "$T" --work "$W" --spans "$W/spans-client.jsonl" --out "$W/drive.json"
echo "drive exit $?"
curl -s "http://127.0.0.1:$MP/metrics" > "$W/server-metrics.txt"; echo "metrics lines $(wc -l < "$W/server-metrics.txt")"
"$T" workflow list --address "$ADDR" --output json > "$W/list-before-restart.json"
stop_server; echo "server 1 stopped"
start_server 2 && echo "server 2 healthy"
"$T" workflow list --address "$ADDR" --output json > "$W/list-after-restart.json"
"$T" workflow show --address "$ADDR" --workflow-id g2-kill --output json > "$W/history-g2-kill-after-restart.json"
stop_server; echo "server 2 stopped"
echo "run finished $(date -u +%FT%TZ)"
