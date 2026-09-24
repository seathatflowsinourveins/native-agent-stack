#!/usr/bin/env bash
# Dagu arm of us-equities/observability-hosting gap 0 (gap wave 2, 2026-09-23).
# Real Dagu DAG -> native otel traces + step log files -> otelcol-contrib
# (spanmetrics connector, filelog receiver) -> Prometheus / Loki; kill -9 retention;
# hot restic backup + restore of Dagu history and both stores; srt egress denial
# for a sandboxed DAG step. Loopback ports only, temp HOME, stops what it starts.
# Usage: [OTEL_EP=... OTEL_INSECURE=true] dagu_arm.sh <scratch-dir>   (writes logs there)
# Round 1 used the defaults (HTTP /v1/traces endpoint; Dagu 2.16.6 sent it to its gRPC
# exporter and failed). Round 2: OTEL_EP=127.0.0.1:34317 OTEL_INSECURE=true.
# Round 3 (after review): Loki listen addresses bound to 127.0.0.1 (rounds 1-2 left them
# empty = all interfaces), listener probe, in-script PASS/FAIL assertions, process count.
# Round 3 hung: Loki's query frontend advertised the WSL interface IP while gRPC was on
# 127.0.0.1 ('dial tcp <lan-ip>:33101: connect: connection refused'). Round 4 adds
# frontend.address: 127.0.0.1.
set -uo pipefail
R=${1:?scratch dir}; mkdir -p "$R"/{cfg,data/prom,data/loki,dagu,home,logs,restore}
H0=$HOME  # real home, captured before HOME is replaced below
T=$H0/.local/share/codex-ecosystem/tools
OTEL=$T/otelcol-contrib-0.161.0/otelcol-contrib
PROM=$T/ecosystem-prometheus-3.14.0/prometheus
LOKI=$T/ecosystem-loki-3.7.8/loki-linux-amd64
BIN=$H0/.local/share/codex-ecosystem/bin
MARK="obsgap-$(date -u +%H%M%S)"; SVC=dagu-obsgap-20260923
export HOME="$R/home" DAGU_HOME="$R/dagu" RESTIC_PASSWORD=gap-wave2-local-throwaway
export PATH="$BIN:$PATH"
S="$R/logs/steps.txt"; : > "$S"
note(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$S"; }

cat > "$R/cfg/prometheus.yml" <<EOF
global:
  scrape_interval: 2s
EOF
cat > "$R/cfg/loki.yml" <<EOF
auth_enabled: false
server: {http_listen_address: 127.0.0.1, http_listen_port: 33100, grpc_listen_address: 127.0.0.1, grpc_listen_port: 33101}
common:
  path_prefix: $R/data/loki
  storage: {filesystem: {chunks_directory: $R/data/loki/chunks, rules_directory: $R/data/loki/rules}}
  replication_factor: 1
  ring: {instance_addr: 127.0.0.1, kvstore: {store: inmemory}}
schema_config:
  configs: [{from: 2024-01-01, store: tsdb, object_store: filesystem, schema: v13, index: {prefix: index_, period: 24h}}]
frontend: {address: 127.0.0.1}
limits_config: {allow_structured_metadata: true}
EOF
cat > "$R/cfg/otelcol.yml" <<EOF
receivers:
  otlp:
    protocols: {grpc: {endpoint: 127.0.0.1:34317}, http: {endpoint: 127.0.0.1:34318}}
  filelog:
    include: ["$R/dagu/logs/**/*.out", "$R/dagu/logs/**/*.err"]
    start_at: beginning
    include_file_path: true
connectors:
  spanmetrics: {metrics_flush_interval: 2s}
exporters:
  prometheusremotewrite: {endpoint: "http://127.0.0.1:39090/api/v1/write"}
  otlphttp/loki: {logs_endpoint: "http://127.0.0.1:33100/otlp/v1/logs", tls: {insecure: true}}
  debug: {verbosity: basic}
processors:
  batch: {timeout: 1s}
  resource/dagulogs:
    attributes: [{key: service.name, value: $SVC, action: upsert}]
service:
  telemetry: {metrics: {level: none}}
  pipelines:
    traces: {receivers: [otlp], processors: [batch], exporters: [spanmetrics, debug]}
    metrics: {receivers: [otlp, spanmetrics], processors: [batch], exporters: [prometheusremotewrite]}
    logs: {receivers: [filelog], processors: [resource/dagulogs, batch], exporters: [otlphttp/loki]}
EOF
mkdir -p "$R/dagu/dags"
cat > "$R/dagu/dags/obsgap.yaml" <<EOF
name: obsgap
otel:
  enabled: true
  endpoint: ${OTEL_EP:-http://127.0.0.1:34318/v1/traces}
  insecure: ${OTEL_INSECURE:-false}
  resource: {service.name: $SVC}
steps:
  - name: fill-log
    command: echo "order-filled receipt_id=$MARK symbol=SPY qty=1 mode=simulation"
  - name: risk-check
    command: echo "risk-check passed receipt_id=$MARK"
    depends: [fill-log]
  - name: sandboxed-worker
    command: srt -d -c 'sleep 1; curl -sS -m 8 -o /dev/null -w "HTTPSTATUS:%{http_code} EXIT:%{exitcode}\n" https://example.com'
    depends: [risk-check]
    continue_on: {failure: true}
EOF

start_stack(){
  "$PROM" --config.file="$R/cfg/prometheus.yml" --storage.tsdb.path="$R/data/prom" \
    --web.listen-address=127.0.0.1:39090 --web.enable-remote-write-receiver >>"$R/logs/prom.log" 2>&1 & PPID_PROM=$!
  "$LOKI" -config.file="$R/cfg/loki.yml" >>"$R/logs/loki.log" 2>&1 & PPID_LOKI=$!
  for i in $(seq 60); do curl -fs 127.0.0.1:39090/-/ready >/dev/null && curl -fs 127.0.0.1:33100/ready >/dev/null && break; sleep 1; done
  "$OTEL" --config="$R/cfg/otelcol.yml" >>"$R/logs/otelcol.log" 2>&1 & PPID_OTEL=$!
  sleep 3
  note "stack pids prom=$PPID_PROM loki=$PPID_LOKI otel=$PPID_OTEL ready_prom=$(curl -s 127.0.0.1:39090/-/ready) ready_loki=$(curl -s 127.0.0.1:33100/ready)"
}
q_prom(){ curl -s -G 127.0.0.1:39090/api/v1/query --data-urlencode "query=$1"; }
q_loki(){ curl -s -G 127.0.0.1:33100/loki/api/v1/query_range --data-urlencode "query=$1" \
  --data-urlencode "start=$(( $(date +%s) - 3600 ))000000000" --data-urlencode "limit=100"; }
PQ="sum by (span_name) ({__name__=~\"traces_span_metrics_calls.*\",service_name=\"$SVC\"})"
LQ="{service_name=\"$SVC\"} |= \"$MARK\""
query_all(){ # $1 tag
  q_prom "$PQ" > "$R/logs/prom-$1.json"; q_loki "$LQ" > "$R/logs/loki-$1.json"
  note "$1 prom=$(head -c 600 "$R/logs/prom-$1.json")"
  note "$1 loki_lines=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(sum(len(s['values']) for s in d['data']['result']))" "$R/logs/loki-$1.json" 2>&1)"
}

note "versions dagu=$(dagu version 2>&1|head -1) otel=$("$OTEL" --version) prom=$("$PROM" --version|head -1) loki=$("$LOKI" --version|head -1) restic=$(restic version) srt=$(srt --version)"
start_stack
listeners(){ note "listeners $1: $(ss -ltnpH 2>/dev/null | grep -E "pid=($2)," | awk '{print $4}' | sort -u | tr '\n' ' ')"; }
listeners initial "$PPID_PROM|$PPID_LOKI|$PPID_OTEL"
note "dagu start"; dagu start "$R/dagu/dags/obsgap.yaml" > "$R/logs/dagu-start.log" 2>&1; note "dagu start exit=$?"
dagu status "$R/dagu/dags/obsgap.yaml" > "$R/logs/dagu-status.log" 2>&1; note "dagu status exit=$?"
sleep 12; query_all before-kill
note "srt step output: $(grep -rh -E 'denying|HTTPSTATUS|CONNECT tunnel' "$R/dagu/logs" | head -5 | tr '\n' ' ')"

note "kill -9"; kill -9 $PPID_OTEL $PPID_PROM $PPID_LOKI; wait $PPID_OTEL $PPID_PROM $PPID_LOKI 2>/dev/null
start_stack; listeners after-restart "$PPID_PROM|$PPID_LOKI|$PPID_OTEL"; sleep 8; query_all after-restart

note "restic hot backup (stack running)"
restic -r "$R/restic-repo" init > "$R/logs/restic.log" 2>&1
restic -r "$R/restic-repo" backup "$R/dagu" "$R/data/prom" "$R/data/loki" --tag obsgap >> "$R/logs/restic.log" 2>&1; note "backup exit=$?"
restic -r "$R/restic-repo" check --read-data >> "$R/logs/restic.log" 2>&1; note "check exit=$?"
restic -r "$R/restic-repo" restore latest --target "$R/restore" --verify >> "$R/logs/restic.log" 2>&1; note "restore exit=$?"
diff -rq "$R/dagu" "$R/restore$R/dagu" > "$R/logs/diff-dagu.log" 2>&1; note "diff -rq dagu exit=$? lines=$(wc -l < "$R/logs/diff-dagu.log")"
DAGU_HOME="$R/restore$R/dagu" dagu history > "$R/logs/dagu-history-restored.log" 2>&1; note "dagu history on restored home exit=$?"
DAGU_HOME="$R/restore$R/dagu" dagu status "$R/restore$R/dagu/dags/obsgap.yaml" > "$R/logs/dagu-status-restored.log" 2>&1; note "dagu status on restored home exit=$?"

RR="$R/restore$R"  # restored-store query parity on separate loopback ports
sed -e "s#$R/data/loki#$RR/data/loki#g" -e 's/33100/33110/; s/33101/33111/' "$R/cfg/loki.yml" > "$R/cfg/loki-restored.yml"
"$PROM" --config.file="$R/cfg/prometheus.yml" --storage.tsdb.path="$RR/data/prom" \
  --web.listen-address=127.0.0.1:39091 >>"$R/logs/prom-restored.log" 2>&1 & RP=$!
"$LOKI" -config.file="$R/cfg/loki-restored.yml" >>"$R/logs/loki-restored.log" 2>&1 & RL=$!
for i in $(seq 60); do curl -fs 127.0.0.1:39091/-/ready >/dev/null && curl -fs 127.0.0.1:33110/ready >/dev/null && break; sleep 1; done
curl -s -G 127.0.0.1:39091/api/v1/query --data-urlencode "query=$PQ" > "$R/logs/prom-restored.json"
curl -s -G 127.0.0.1:33110/loki/api/v1/query_range --data-urlencode "query=$LQ" \
  --data-urlencode "start=$(( $(date +%s) - 3600 ))000000000" --data-urlencode "limit=100" > "$R/logs/loki-restored.json"
note "restored prom=$(head -c 600 "$R/logs/prom-restored.json")"
note "restored loki_lines=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(sum(len(s['values']) for s in d['data']['result']))" "$R/logs/loki-restored.json" 2>&1)"
listeners restored "$RP|$RL"
kill $RP $RL
python3 - "$R/logs" <<'PY' | tee -a "$S"
import json,sys
L=sys.argv[1]
sp=lambda t: sorted(x['metric']['span_name'] for x in json.load(open(f"{L}/prom-{t}.json"))['data']['result'])
lt=lambda t: {v[0] for s in json.load(open(f"{L}/loki-{t}.json"))['data']['result'] for v in s['values']}
want=['DAG: obsgap','Step: fill-log','Step: risk-check','Step: sandboxed-worker']
for t in ('before-kill','after-restart','restored'):
    print(('PASS' if sp(t)==want else 'FAIL'), 'prom span names', t, sp(t))
pre=lt('before-kill')
print(('PASS' if len(pre)>=2 else 'FAIL'), 'loki marker lines before kill', len(pre))
for t in ('after-restart','restored'):
    print(('PASS' if pre and pre<=lt(t) else 'FAIL'), 'loki pre-kill timestamps present', t, len(lt(t)))
PY

note "stop stack"; kill $PPID_OTEL $PPID_PROM $PPID_LOKI; wait 2>/dev/null
note "processes left for scratch path: $(pgrep -f -- "$R" | grep -v -w $$ | wc -l)"
note "listeners left: $(ss -ltn | grep -c -E ':(34317|34318|39090|39091|33100|33101|33110|33111) ' )"
echo "MARK=$MARK" >> "$S"
