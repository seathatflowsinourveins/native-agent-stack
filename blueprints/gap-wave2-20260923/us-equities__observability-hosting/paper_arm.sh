#!/usr/bin/env bash
# Paper-runtime (simulated-port) arm of us-equities/observability-hosting gap 0 (gap wave 2,
# round 5, 2026-09-23). A Dagu DAG runs the adaptive-paper runtime's native path
# (paper_sim_workload.py -> runner.run_native on NautilusTrader 2.0.0rc5 against the
# synthetic SimulatedPort: no network, no credentials, no broker) inside srt, while a
# parallel step takes a hot restic snapshot of the live SQLite WAL journal. Telemetry:
# Dagu native otel spans (span metrics) and the step log (runtime event JSON lines) via
# otelcol-contrib filelog -> Loki, plus a count connector -> Prometheus. Then kill -9
# retention, cold restic backup/restore fidelity (byte diff, sqlite integrity/counts),
# restored-store query parity, and three srt probes with unsandboxed controls.
# Loopback ports only (Loki frontend.address pinned, see round 4), temp HOME/DAGU_HOME,
# stops what it starts. Usage: paper_arm.sh <scratch-dir>
# Round 5 exported TMPDIR globally; srt's bridge socket path then exceeded 108 bytes and srt
# exited before the workload. Round 6 sets TMPDIR only inside the sandboxed step script.
# Round 7: filelog read offsets persisted with file_storage (round 6 re-ingested every line
# after the collector restart); count series via a loopback prometheus exporter scraped by
# Prometheus (round 6's delta_to_cumulative + remote write undercounted); exact assertions.
# Round 8: round 7's exporter showed only recent deltas, so counts return to delta_to_cumulative
# + remote write with collector self-telemetry (loopback :38888, scraped) exposing drops; per-
# metric max_over_time; LogQL count_over_time as an independent log-derived metric query.
set -uo pipefail
R=${1:?scratch dir}; mkdir -p "$R"/{cfg,data/prom,data/loki,data/otelcol-storage,dagu,home,logs,restore,work,decoy,outside,check}
H0=$HOME  # real home, captured before HOME is replaced below
T=$H0/.local/share/codex-ecosystem/tools
OTEL=$T/otelcol-contrib-0.161.0/otelcol-contrib
PROM=$T/ecosystem-prometheus-3.14.0/prometheus
LOKI=$T/ecosystem-loki-3.7.8/loki-linux-amd64
PY=$T/adaptive-paper-20260921/bin/python   # pinned nautilus-trader 2.0.0rc5 + alpaca-py 0.44.0 env, used read-only
BIN=$H0/.local/share/codex-ecosystem/bin
HERE=$(cd "$(dirname "$0")" && pwd)
MARK="obsgap-paper-$(date -u +%H%M%S)"; SVC=paper-obsgap-20260923
export HOME="$R/home" DAGU_HOME="$R/dagu" RESTIC_PASSWORD=gap-wave2-local-throwaway
export PATH="$BIN:$PATH"
S="$R/logs/steps.txt"; : > "$S"
note(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$S"; }
echo "decoy-not-a-secret" > "$R/decoy/decoy.txt"

cat > "$R/cfg/prometheus.yml" <<EOF
global:
  scrape_interval: 2s
scrape_configs:
  - job_name: otelcol-self
    static_configs: [{targets: ["127.0.0.1:38888"]}]
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
    storage: file_storage
extensions:
  file_storage: {directory: $R/data/otelcol-storage}
connectors:
  spanmetrics: {metrics_flush_interval: 2s}
  count:
    logs:
      paper.runtime.log.records:
        description: runtime log lines of the paper-sim step
        conditions: ['IsMatch(body, "$MARK")']
      paper.runtime.intents:
        description: runtime intent events
        conditions: ['IsMatch(body, "$MARK") and IsMatch(body, "type.: .intent")']
exporters:
  prometheusremotewrite: {endpoint: "http://127.0.0.1:39090/api/v1/write"}
  otlphttp/loki: {logs_endpoint: "http://127.0.0.1:33100/otlp/v1/logs", tls: {insecure: true}}
  debug: {verbosity: basic}
processors:
  batch: {timeout: 1s}
  delta_to_cumulative: {}
  resource/paperlogs:
    attributes: [{key: service.name, value: $SVC, action: upsert}]
service:
  extensions: [file_storage]
  telemetry: {metrics: {level: detailed, readers: [{pull: {exporter: {prometheus: {host: 127.0.0.1, port: 38888}}}}]}}
  pipelines:
    traces: {receivers: [otlp], processors: [batch], exporters: [spanmetrics, debug]}
    metrics: {receivers: [otlp, spanmetrics], processors: [batch], exporters: [prometheusremotewrite]}
    metrics/count: {receivers: [count], processors: [delta_to_cumulative, batch], exporters: [prometheusremotewrite]}
    logs: {receivers: [filelog], processors: [resource/paperlogs, batch], exporters: [otlphttp/loki, count]}
EOF
cat > "$R/cfg/srt.json" <<EOF
{"network": {"allowedDomains": [], "deniedDomains": []},
 "filesystem": {"denyRead": ["$R/decoy"], "allowRead": [], "allowWrite": ["$R/work"], "denyWrite": []}}
EOF
cat > "$R/cfg/probes.sh" <<'EOF'
# $1 = outside dir, $2 = decoy file. Each probe prints its exit code; success would show as EXIT:0 / rc=0.
curl -sS -m 8 -o /dev/null -w "PROBE egress HTTPSTATUS:%{http_code} EXIT:%{exitcode}\n" https://example.com; echo "PROBE egress curl_rc=$?"
( echo x > "$1/probe-write.txt" ) 2>&1; echo "PROBE write_outside rc=$?"
cat "$2" 2>&1; echo "PROBE read_decoy rc=$?"
EOF
cat > "$R/cfg/paper_step.sh" <<EOF
cd "$R/work"; export TMPDIR="$R/work"
"$PY" "$HERE/paper_sim_workload.py" --journal "$R/work/journal.db" --result "$R/work/result.json" --mark "$MARK" --seconds 30
echo "PAPER_RC=\$?"
sh "$R/cfg/probes.sh" "$R/outside" "$R/decoy/decoy.txt"
EOF
RESTIC=$(command -v restic); SRT=$(command -v srt)
cat > "$R/cfg/hot_step.sh" <<EOF
sleep 12
export RESTIC_PASSWORD=$RESTIC_PASSWORD HOME="$R/home"
"$RESTIC" -r "$R/restic-hot" init && "$RESTIC" -r "$R/restic-hot" backup "$R/work" --tag hot && echo HOT_BACKUP_OK
EOF
mkdir -p "$R/dagu/dags"
cat > "$R/dagu/dags/obsgap-paper.yaml" <<EOF
name: obsgap-paper
otel:
  enabled: true
  endpoint: 127.0.0.1:34317
  insecure: true
  resource: {service.name: $SVC}
steps:
  - name: paper-runtime
    command: $SRT -d -s $R/cfg/srt.json -c "sh $R/cfg/paper_step.sh"
  - name: hot-backup
    command: sh $R/cfg/hot_step.sh
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
PQS="sum by (span_name) ({__name__=~\"traces_span_metrics_calls.*\",service_name=\"$SVC\"})"
PQC="{__name__=~\"paper_runtime_.*\"}"
PQM1="max_over_time(paper_runtime_log_records_total[1h])"; PQM2="max_over_time(paper_runtime_intents_total[1h])"
PQD="{__name__=~\"otelcol_deltatocumulative.*|otelcol_processor_.*|otelcol_exporter_send_failed.*|otelcol_exporter_sent.*\"}"
LQC="sum(count_over_time({service_name=\"$SVC\"} |= \"$MARK\" [1h]))"
LQ="{service_name=\"$SVC\"} |= \"$MARK\""
q_all(){ # $1 tag, $2 prom port, $3 loki port
  curl -s -G 127.0.0.1:$2/api/v1/query --data-urlencode "query=$PQS" > "$R/logs/prom-spans-$1.json"
  curl -s -G 127.0.0.1:$2/api/v1/query --data-urlencode "query=$PQC" > "$R/logs/prom-count-$1.json"
  curl -s -G 127.0.0.1:$2/api/v1/query --data-urlencode "query=$PQM1" > "$R/logs/prom-countmax-records-$1.json"
  curl -s -G 127.0.0.1:$2/api/v1/query --data-urlencode "query=$PQM2" > "$R/logs/prom-countmax-intents-$1.json"
  curl -s -G 127.0.0.1:$2/api/v1/query --data-urlencode "query=max_over_time($PQD[1h])" > "$R/logs/prom-otelself-$1.json"
  curl -s -G 127.0.0.1:$3/loki/api/v1/query --data-urlencode "query=$LQC" > "$R/logs/loki-countovertime-$1.json"
  curl -s -G 127.0.0.1:$3/loki/api/v1/query_range --data-urlencode "query=$LQ" \
    --data-urlencode "start=$(( $(date +%s) - 3600 ))000000000" --data-urlencode "limit=1000" > "$R/logs/loki-$1.json"
  note "$1 spans=$(head -c 500 "$R/logs/prom-spans-$1.json")"
  note "$1 count=$(head -c 700 "$R/logs/prom-count-$1.json")"
  note "$1 countmax records=$(head -c 400 "$R/logs/prom-countmax-records-$1.json") intents=$(head -c 400 "$R/logs/prom-countmax-intents-$1.json")"
  note "$1 logql count_over_time=$(head -c 400 "$R/logs/loki-countovertime-$1.json")"
  note "$1 loki_lines=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(sum(len(s['values']) for s in d['data']['result']))" "$R/logs/loki-$1.json" 2>&1)"
}
listeners(){ note "listeners $1: $(ss -ltnpH 2>/dev/null | grep -E "pid=($2)," | awk '{print $4}' | sort -u | tr '\n' ' ')"; }

note "versions dagu=$(dagu version 2>&1|head -1) otel=$("$OTEL" --version) prom=$("$PROM" --version|head -1) loki=$("$LOKI" --version|head -1) restic=$(restic version) srt=$(srt --version) py=$("$PY" -c 'import nautilus_trader,sys;print(sys.version.split()[0],nautilus_trader.__version__)')"
start_stack; listeners initial "$PPID_PROM|$PPID_LOKI|$PPID_OTEL"
note "dagu start"; timeout 600 dagu start "$R/dagu/dags/obsgap-paper.yaml" > "$R/logs/dagu-start.log" 2>&1; note "dagu start exit=$?"
dagu status "$R/dagu/dags/obsgap-paper.yaml" > "$R/logs/dagu-status.log" 2>&1; note "dagu status exit=$?"
sleep 12; q_all before-kill 39090 33100
note "step output: $(grep -rh -E 'PAPER_RC|PROBE|denying|HOT_BACKUP_OK|paper_sim_end' "$R/dagu/logs" | cut -c1-400 | tr '\n' ' ')"

note "controls (unsandboxed; must succeed)"
curl -sS -m 8 -o /dev/null -w "CONTROL egress HTTPSTATUS:%{http_code} EXIT:%{exitcode}\n" https://example.com | tee -a "$S"
( echo x > "$R/outside/control-write.txt" ); note "CONTROL write_outside rc=$?"
cat "$R/decoy/decoy.txt" >/dev/null; note "CONTROL read_decoy rc=$?"

note "kill -9"; kill -9 $PPID_OTEL $PPID_PROM $PPID_LOKI; wait $PPID_OTEL $PPID_PROM $PPID_LOKI 2>/dev/null
start_stack; listeners after-restart "$PPID_PROM|$PPID_LOKI|$PPID_OTEL"; sleep 8; q_all after-restart 39090 33100

note "restic backup (stack running, workload finished)"
restic -r "$R/restic-repo" init > "$R/logs/restic.log" 2>&1
restic -r "$R/restic-repo" backup "$R/work" "$R/dagu" "$R/data/prom" "$R/data/loki" --tag obsgap-paper >> "$R/logs/restic.log" 2>&1; note "backup exit=$?"
restic -r "$R/restic-repo" check --read-data >> "$R/logs/restic.log" 2>&1; note "check exit=$?"
restic -r "$R/restic-repo" restore latest --target "$R/restore" --verify >> "$R/logs/restic.log" 2>&1; note "restore exit=$?"
restic -r "$R/restic-hot" check --read-data > "$R/logs/restic-hot.log" 2>&1; note "hot check exit=$?"
restic -r "$R/restic-hot" restore latest --target "$R/restore-hot" --verify >> "$R/logs/restic-hot.log" 2>&1; note "hot restore exit=$?"
RR="$R/restore$R"
diff -rq "$R/work" "$RR/work" > "$R/logs/diff-work.log" 2>&1; note "diff -rq work exit=$? lines=$(wc -l < "$R/logs/diff-work.log")"
diff -rq "$R/dagu" "$RR/dagu" > "$R/logs/diff-dagu.log" 2>&1; note "diff -rq dagu exit=$? lines=$(wc -l < "$R/logs/diff-dagu.log")"
DAGU_HOME="$RR/dagu" dagu status "$RR/dagu/dags/obsgap-paper.yaml" > "$R/logs/dagu-status-restored.log" 2>&1; note "dagu status on restored home exit=$?"
cp -a "$RR/work" "$R/check/cold"; cp -a "$R/restore-hot$R/work" "$R/check/hot"   # open copies, never the restored originals
python3 - "$R" <<'PY' | tee "$R/logs/journal-check.json"
import json,sqlite3,sys
R=sys.argv[1]; T=("intents","requests","events","positions","marks","trials"); out={}
for tag in ("cold","hot"):
    try:
        db=sqlite3.connect(f"{R}/check/{tag}/journal.db")
        out[tag]={"integrity":db.execute("PRAGMA integrity_check").fetchone()[0],
                  "counts":{t:db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in T}}
        db.close()
    except Exception as e: out[tag]={"error":repr(e)}
print(json.dumps(out))
PY

sed -e "s#$R/data/loki#$RR/data/loki#g" -e 's/33100/33110/; s/33101/33111/' "$R/cfg/loki.yml" > "$R/cfg/loki-restored.yml"
"$PROM" --config.file="$R/cfg/prometheus.yml" --storage.tsdb.path="$RR/data/prom" \
  --web.listen-address=127.0.0.1:39091 >>"$R/logs/prom-restored.log" 2>&1 & RP=$!
"$LOKI" -config.file="$R/cfg/loki-restored.yml" >>"$R/logs/loki-restored.log" 2>&1 & RL=$!
for i in $(seq 60); do curl -fs 127.0.0.1:39091/-/ready >/dev/null && curl -fs 127.0.0.1:33110/ready >/dev/null && break; sleep 1; done
q_all restored 39091 33110
listeners restored "$RP|$RL"
kill $RP $RL

python3 - "$R" "$MARK" <<'PY' | tee -a "$S"
import glob,json,re,sys
R=sys.argv[1]; L=R+"/logs"; MARK=sys.argv[2]
ok=lambda c,*m: print('PASS' if c else 'FAIL', *m)
steplog="\n".join(open(p,errors="replace").read() for p in glob.glob(R+"/dagu/logs/**/*.out",recursive=True)+glob.glob(R+"/dagu/logs/**/*.err",recursive=True))
end=[json.loads(l) for l in steplog.splitlines() if l.startswith("{") and '"paper_sim_end"' in l]
ok(len(end)==1 and end[0]["status"]=="passed" and end[0]["flat"] and end[0]["native_fill_events"]>0,
   "paper runtime passed flat with fills", end[0] if end else None)
ok("PAPER_RC=0" in steplog, "paper step rc 0")
ok(re.search(r"PROBE egress HTTPSTATUS:000 EXIT:[1-9]", steplog) and "denying: example.com:443" in steplog, "sandboxed egress denied")
ok(re.search(r"PROBE write_outside rc=[1-9]", steplog), "sandboxed write outside allowWrite denied")
ok(re.search(r"PROBE read_decoy rc=[1-9]", steplog) and "decoy-not-a-secret" not in steplog, "sandboxed decoy read denied")
st=open(L+"/steps.txt").read()
ok(re.search(r"CONTROL egress HTTPSTATUS:[23]\d\d EXIT:0", st) and "CONTROL write_outside rc=0" in st and "CONTROL read_decoy rc=0" in st, "unsandboxed controls succeed")
ok("HOT_BACKUP_OK" in steplog, "hot backup during the run")
sp=lambda t: sorted(x['metric'].get('span_name') for x in res(f"{L}/prom-spans-{t}.json"))
cn=lambda t: {x['metric']['__name__']: float(x['value'][1]) for x in res(f"{L}/prom-count-{t}.json")}
def res(path):
    try: return json.load(open(path)).get('data',{}).get('result',[])
    except Exception as e: return []
cm=lambda t,m: [float(x['value'][1]) for x in res(f"{L}/prom-countmax-{m}-{t}.json")]
lc=lambda t: [float(x['value'][1]) for x in res(f"{L}/loki-countovertime-{t}.json")]
nlines=len([l for l in steplog.splitlines() if MARK in l]); nint=len([l for l in steplog.splitlines() if MARK in l and '"type": "intent"' in l])
lt=lambda t: {v[0] for s in res(f"{L}/loki-{t}.json") for v in s['values']}
want=['DAG: obsgap-paper','Step: hot-backup','Step: paper-runtime']
for t in ('before-kill','after-restart','restored'):
    ok(sp(t)==want, 'prom span names', t, sp(t))
    if t=='before-kill':
        c=cn(t); ok(c.get('paper_runtime_log_records_total')==nlines and c.get('paper_runtime_intents_total')==nint, 'prom exact counts before kill (records, intents)', c, nlines, nint)
    ok(cm(t,'records')==[float(nlines)] and cm(t,'intents')==[float(nint)], 'prom max_over_time counts equal step log (records, intents)', t, cm(t,'records'), cm(t,'intents'), nlines, nint)
    ok(lc(t)==[float(nlines)], 'logql count_over_time equals step log', t, lc(t), nlines)
nv=lambda t: sum(len(s['values']) for s in res(f"{L}/loki-{t}.json"))
pre=lt('before-kill')
ok(nlines>=2 and nv('before-kill')==nlines, 'loki MARK lines before kill vs step-log MARK lines', nv('before-kill'), nlines)
for t in ('after-restart','restored'):
    ok(pre and pre<=lt(t), 'loki pre-kill timestamps present', t, len(lt(t)))
    ok(nv(t)==nlines, 'loki no duplicate re-ingest', t, nv(t), nlines)
st2=open(L+"/steps.txt").read()
for k in ("backup exit=0","check exit=0","restore exit=0","hot check exit=0","hot restore exit=0","diff -rq work exit=0","diff -rq dagu exit=0"):
    ok(k in st2, k)
j=json.load(open(L+"/journal-check.json"))
ok(end and j["cold"].get("integrity")=="ok" and j["cold"].get("counts")==end[0]["journal_counts"], "cold-restored journal integrity and counts", j["cold"])
ok(j["hot"].get("integrity")=="ok", "hot-snapshot journal integrity", j["hot"])
PY

note "stop stack"; kill $PPID_OTEL $PPID_PROM $PPID_LOKI; wait 2>/dev/null
ANC=" $$ "; p=$$; while [ "$p" -gt 1 ]; do p=$(ps -o ppid= -p "$p" | tr -d ' '); ANC="$ANC$p "; done
pgrep -f -- "$R" > "$R/logs/pgrep.txt"; : > "$R/logs/procs-left.txt"   # no subshell: forks would match
while read -r q; do case "$ANC" in *" $q "*) ;; *) ps -o pid=,args= -p "$q" >> "$R/logs/procs-left.txt" 2>/dev/null;; esac; done < "$R/logs/pgrep.txt"
note "processes left for scratch path (excluding this script's ancestors$ANC): $(wc -l < "$R/logs/procs-left.txt")"
note "listeners left: $(ss -ltn | grep -c -E ':(34317|34318|38888|39090|39091|33100|33101|33110|33111) ' )"
echo "MARK=$MARK" >> "$S"
