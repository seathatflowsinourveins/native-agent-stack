#!/usr/bin/env bash
# Gap 1: run each package's catalog native_workflow snippet or a minimal local run
# from its own uv venv. Usage: run_package_checks.sh OUTDIR [inspect|mlflow|river|mteb|phoenix ...]
set -uo pipefail
OUT=$1; shift; mkdir -p "$OUT"
C=${HOME}/.cache/gap-wave2-20260923/evaluation-experiments
stamp() { date -u +%FT%T.%3NZ; }
log() { echo "$(stamp) $*" | tee -a "$OUT/timeline.txt"; }
free_port() { python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
ver() { "$C/venv-$1/bin/python" -c "import importlib.metadata as m;print(m.version('$2'))"; }
for pkg in "$@"; do case $pkg in
inspect)
  log "inspect version $(ver inspect inspect-ai)"
  "$C/venv-inspect/bin/inspect" --help > "$OUT/inspect-help.txt" 2>&1; log "inspect --help exit=$?" ;;
river)
  log "river version $(ver river river)"
  "$C/venv-river/bin/python" - > "$OUT/river-snippet.txt" 2>&1 <<'PY'
from river import linear_model, preprocessing, metrics
model = preprocessing.StandardScaler() | linear_model.LinearRegression()
metric = metrics.MAE()
for x, y in [({'x': 1.}, 2.), ({'x': 2.}, 4.), ({'x': 3.}, 6.)]:
    prediction = model.predict_one(x)
    metric.update(y, prediction)
    model.learn_one(x, y)
print(metric)
PY
  log "river snippet exit=$?" ;;
mlflow)
  log "mlflow version $(ver mlflow mlflow)"
  ( cd "$(mktemp -d "$C/tmp-mlflow-XXXX")" && MLFLOW_DISABLE_TELEMETRY=true DO_NOT_TRACK=true "$C/venv-mlflow/bin/python" - ) > "$OUT/mlflow-snippet.txt" 2>&1 <<'PY'
import tempfile
import mlflow
with tempfile.TemporaryDirectory() as directory:
    mlflow.set_tracking_uri('sqlite:///' + directory + '/mlflow.db')
    mlflow.set_experiment('synthetic-catalog-demo')
    with mlflow.start_run():
        mlflow.log_param('input_kind', 'synthetic')
        mlflow.log_metric('row_count', 3)
        print(mlflow.get_tracking_uri())
PY
  log "mlflow snippet exit=$?"
  P=$(free_port); D=$(mktemp -d "$C/tmp-mlflow-server-XXXX")
  ( cd "$D" && MLFLOW_DISABLE_TELEMETRY=true DO_NOT_TRACK=true exec "$C/venv-mlflow/bin/mlflow" server --host 127.0.0.1 --port "$P" \
      --backend-store-uri "sqlite:///$D/mlflow.db" --default-artifact-root "$D/artifacts" ) > "$OUT/mlflow-server.log" 2>&1 &
  SP=$!
  for i in $(seq 1 90); do curl -sf "http://127.0.0.1:$P/health" > "$OUT/mlflow-health.txt" 2>/dev/null && break; sleep 1; done
  log "mlflow server port=$P health=$(cat "$OUT/mlflow-health.txt" 2>/dev/null) after=${i}s"
  curl -sf -X POST "http://127.0.0.1:$P/api/2.0/mlflow/experiments/search" -H 'Content-Type: application/json' -d '{"max_results":10}' > "$OUT/mlflow-experiments.json"; log "mlflow experiments/search exit=$?"
  pkill -TERM -P $SP 2>/dev/null; kill -TERM $SP 2>/dev/null; wait $SP 2>/dev/null; sleep 1
  log "mlflow server stopped; listeners on port: $(ss -ltn "sport = :$P" | tail -n +2 | wc -l)" ;;
mteb)
  log "mteb version $(ver mteb mteb) torch $(ver mteb torch)"
  HF_HOME="$C/hf-home" MTEB_CACHE="$C/mteb-cache" HF_HUB_DISABLE_TELEMETRY=1 "$C/venv-mteb/bin/python" "$(dirname "$0")/mteb_minimal.py" "$OUT/mteb-results" > "$OUT/mteb-run.txt" 2>&1
  log "mteb minimal run exit=$?" ;;
phoenix)
  log "phoenix version $(ver phoenix arize-phoenix)"
  P=$(free_port); G=$(free_port); D=$(mktemp -d "$C/tmp-phoenix-XXXX")
  ( cd "$D" && exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PHOENIX_WORKING_DIR="$D" PHOENIX_HOST=127.0.0.1 PHOENIX_PORT="$P" PHOENIX_GRPC_PORT="$G" \
      PHOENIX_TELEMETRY_ENABLED=false PHOENIX_ENABLE_MCP_SERVER=false PHOENIX_ALLOWED_PROVIDERS=NONE \
      "$C/venv-phoenix/bin/phoenix" serve ) > "$OUT/phoenix-server.log" 2>&1 &
  SP=$!
  for i in $(seq 1 120); do curl -sf "http://127.0.0.1:$P/healthz" > "$OUT/phoenix-health.txt" 2>/dev/null && break; sleep 1; done
  log "phoenix port=$P grpc=$G healthz=$(cat "$OUT/phoenix-health.txt" 2>/dev/null) after=${i}s"
  "$C/venv-phoenix/bin/python" "$(dirname "$0")/phoenix_span_roundtrip.py" "http://127.0.0.1:$P" > "$OUT/phoenix-roundtrip.json" 2> "$OUT/phoenix-roundtrip.err"
  log "phoenix span roundtrip exit=$?"
  kill -TERM $SP 2>/dev/null; wait $SP 2>/dev/null; sleep 1
  log "phoenix stopped; listeners: http=$(ss -ltn "sport = :$P" | tail -n +2 | wc -l) grpc=$(ss -ltn "sport = :$G" | tail -n +2 | wc -l)" ;;
esac; done
