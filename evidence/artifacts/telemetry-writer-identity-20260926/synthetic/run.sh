#!/usr/bin/env bash
# Local integration (synthetic fixture, no model call, no host service touched):
# private otelcol-contrib + Prometheus pairs on unused loopback ports, old vs new collector profile,
# identical synthetic OTLP input. Output goes to $RUN_DIR (default: a new temporary directory); every
# process started here is stopped on exit. OLD_REF names the commit whose collector.yaml is the old profile
# (default ca8e37f136ee, the base of the writer-identity change); the new profile is $WT's working copy.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WT="${WT:?worktree}"
PY="${PY:?python with PyYAML}"
ECO="$HOME/.local/share/codex-ecosystem"
OTELCOL="$ECO/tools/otelcol-0.161.0/otelcol-contrib"
PROM="$ECO/tools/ecosystem-prometheus-3.15.0/prometheus"
RUN="${RUN_DIR:-$(mktemp -d -t writer-identity-XXXXXX)}"
mkdir -p "$RUN"
OLD_REF="${OLD_REF:-ca8e37f136ee}"
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; wait 2>/dev/null || true; }
trap cleanup EXIT

# WSL mirrored networking shares the port space with Windows, which ss cannot see: probe by binding.
python3 - <<'PORTS' || { echo "a private port is not bindable" >&2; exit 2; }
import socket, sys
bad = []
for base in (41000, 42000):
    for port in (base + 317, base + 318, base + 333, base + 888, base + 889, base + 90):
        s = socket.socket()
        try:
            s.bind(('127.0.0.1', port))
        except OSError:
            bad.append(port)
        finally:
            s.close()
sys.exit(1 if bad else 0)
PORTS

git -C "$WT" show "$OLD_REF:observability/collector/collector.yaml" > "$RUN/collector.old.src.yaml"
cp "$WT/observability/collector/collector.yaml" "$RUN/collector.new.src.yaml"
for mode in old new; do
  base=41000; [[ $mode == new ]] && base=42000
  mkdir -p "$RUN/$mode"
  "$PY" "$HERE/make_config.py" --source "$RUN/collector.$mode.src.yaml" --output "$RUN/$mode/collector.yaml" \
    --data "$RUN/$mode" --port-base "$base"
  "$OTELCOL" validate --config="$RUN/$mode/collector.yaml"
  cat > "$RUN/$mode/prometheus.yml" <<EOF
global:
  scrape_interval: 5s
  evaluation_interval: 5s
scrape_configs:
  - job_name: collector-native
    honor_labels: true
    static_configs:
      - targets: ['127.0.0.1:$((base + 889))']
  - job_name: collector-health
    static_configs:
      - targets: ['127.0.0.1:$((base + 888))']
EOF
  "$OTELCOL" --config="$RUN/$mode/collector.yaml" > "$RUN/$mode/otelcol.log" 2>&1 &
  pids+=($!)
  features=promql-extended-range-selectors
  [[ $mode == new ]] && features=created-timestamp-zero-ingestion,promql-extended-range-selectors
  "$PROM" --config.file="$RUN/$mode/prometheus.yml" --storage.tsdb.path="$RUN/$mode/tsdb" \
    --web.listen-address="127.0.0.1:$((base + 90))" --enable-feature="$features" > "$RUN/$mode/prometheus.log" 2>&1 &
  pids+=($!)
done
for url in http://127.0.0.1:41333/ http://127.0.0.1:42333/ http://127.0.0.1:41090/-/ready http://127.0.0.1:42090/-/ready; do
  curl --silent --fail --connect-timeout 1 --max-time 2 --retry 30 --retry-connrefused --retry-all-errors --retry-delay 1 -o /dev/null "$url"
done
sleep 6  # one scrape of the empty exporters first
"$PY" "$HERE/send.py" --old http://127.0.0.1:41318 --new http://127.0.0.1:42318 --expected "$RUN/expected.json" > "$RUN/send.log"
sleep 22  # final exports scraped
"$PY" "$HERE/check.py" --expected "$RUN/expected.json" --prom old=http://127.0.0.1:41090 --prom new=http://127.0.0.1:42090 \
  --output "$RUN/report.json" | tee "$RUN/check.txt"
grep -h -i -E 'error|warn' "$RUN"/*/otelcol.log | cut -c1-300 | sort | uniq -c | head -20 || true
echo "run dir: $RUN"
