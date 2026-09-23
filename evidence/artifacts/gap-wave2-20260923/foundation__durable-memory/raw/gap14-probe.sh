set -euo pipefail
D=$HOME/.cache/gap-wave2-20260923/durable-memory/net-probe
rm -rf "$D"
mkdir -p "$D"
ip link set lo up
echo "== ip addr (namespace) =="
ip addr show
echo "== ip route (namespace, expect empty) =="
ip route show || true
ai-memory init --data-dir "$D"
sed -i 's/bind = "127.0.0.1:49374"/bind = "127.0.0.1:49590"/' "$D/config.toml" || true
grep -n bind "$D/config.toml" || true
export AI_MEMORY_EMBEDDING_PROVIDER=none
export AI_MEMORY_SERVER_URL=http://127.0.0.1:49590
nohup ai-memory serve --data-dir "$D" --transport http --bind 127.0.0.1:49590 --no-watcher >"$D/serve.log" 2>&1 &
SPID=$!
sleep 1.5
echo "== rx/tx bytes BEFORE writes (all interfaces) =="
cat /proc/net/dev
ai-memory status --data-dir "$D"
ai-memory write-page --data-dir "$D" --path scratch/net-probe.md --body '# net probe unique-marker-net-14' --title 'net probe' --workspace disposable-ws --project disposable-proj
sleep 0.5
echo "== rx/tx bytes AFTER writes (all interfaces) =="
cat /proc/net/dev
ai-memory status --data-dir "$D"
kill "$SPID" 2>/dev/null || true
wait "$SPID" 2>/dev/null || true
echo "== serve.log tail =="
tail -30 "$D/serve.log"
