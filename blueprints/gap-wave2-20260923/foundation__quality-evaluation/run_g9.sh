#!/usr/bin/env bash
# Gap 9: probe the resident embedding vLLM for chat support, run two unmodified
# upstream Inspect examples (inspect_ai tag 0.3.268) against a temporary
# loopback vLLM chat server, log each run to a temporary loopback MLflow server,
# retrieve run records by REST, then stop MLflow and confirm the port is closed.
# The temporary vLLM chat server is started and stopped by the caller.
# Usage: run_g9.sh WORKDIR OUT VENV INSPECT_EXAMPLES_DIR HELDOUT_INSPECT_LOG
set -u
WORK=$1; OUT=$2; VENV=$3; EX=$4; HELDOUT_LOG=$5; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$WORK" "$OUT"
rc() { echo "$2" > "$OUT/$1.exit"; echo "$1 exit=$2"; }
export MLFLOW_DISABLE_AGENT_HINT=1 MLFLOW_DISABLE_TELEMETRY=true DO_NOT_TRACK=1 INSPECT_DISABLE_TELEMETRY=1
CHAT=http://127.0.0.1:18431/v1; MLPORT=15005

# Detection probe: which server offers chat completions (status code + model list).
{ echo "resident 8231 /v1/models:"; curl -s -m 5 http://127.0.0.1:8231/v1/models | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"
  echo "resident 8231 POST /v1/chat/completions status: $(curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8231/v1/chat/completions -H 'content-type: application/json' -d '{"model":"nvidia/Nemotron-3-Embed-1B-BF16","messages":[{"role":"user","content":"hi"}],"max_tokens":1}')"
  echo "temporary 18431 /v1/models:"; curl -s -m 5 $CHAT/models | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"
  echo "temporary 18431 POST /v1/chat/completions status: $(curl -s -m 60 -o /dev/null -w '%{http_code}' -X POST $CHAT/chat/completions -H 'content-type: application/json' -d '{"model":"qwen2.5-7b-instruct-awq","messages":[{"role":"user","content":"hi"}],"max_tokens":1}')"
} > "$OUT/chat-endpoint-probe.txt" 2>&1

# Upstream examples, unmodified, via Inspect's vllm provider pointed at the running server.
export VLLM_BASE_URL=$CHAT VLLM_API_KEY=local-no-auth
for t in hello_world security_guide; do
  ( cd "$EX" && "$VENV/bin/inspect" eval $t.py --model vllm/qwen2.5-7b-instruct-awq --log-dir "$WORK/inspect-logs-$t" --log-format json --max-connections 4 ) > "$OUT/inspect-$t.stdout" 2> "$OUT/inspect-$t.stderr"
  rc inspect-$t $?
done
sha256sum "$EX/hello_world.py" "$EX/security_guide.py" | sed "s#$EX/##" > "$OUT/upstream-example.sha256"

# Temporary loopback MLflow tracking server.
"$VENV/bin/mlflow" server --host 127.0.0.1 --port $MLPORT --workers 1 \
  --backend-store-uri "sqlite:///$WORK/mlflow.db" --default-artifact-root "$WORK/mlflow-artifacts" \
  > "$OUT/mlflow-server.log" 2>&1 &
MLPID=$!
for i in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:$MLPORT/health >/dev/null && break; sleep 1; done
echo "mlflow health: $(curl -s -m 2 http://127.0.0.1:$MLPORT/health)" > "$OUT/mlflow-health.txt"
"$VENV/bin/python" "$HERE/log_inspect_to_mlflow.py" http://127.0.0.1:$MLPORT "$OUT/mlflow-logged-runs.json" \
  "$WORK"/inspect-logs-hello_world/*.json "$WORK"/inspect-logs-security_guide/*.json "$HELDOUT_LOG" > "$OUT/mlflow-log.stdout" 2> "$OUT/mlflow-log.stderr"
rc mlflow-log $?
for id in $(python3 -c "import json,sys; print(' '.join(r['run_id'] for r in json.load(open(sys.argv[1]))))" "$OUT/mlflow-logged-runs.json"); do
  curl -s -m 5 "http://127.0.0.1:$MLPORT/api/2.0/mlflow/runs/get?run_id=$id" > "$OUT/mlflow-run-$id.json"
done
kill $MLPID; wait $MLPID 2>/dev/null; pkill -f "mlflow.*--port $MLPORT" 2>/dev/null; sleep 2
{ curl -s -m 3 -o /dev/null -w 'http %{http_code}\n' http://127.0.0.1:$MLPORT/health; echo "curl exit=$?"; ss -ltn | grep -c ":$MLPORT " ; } > "$OUT/mlflow-after-stop.txt" 2>&1
