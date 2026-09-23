set -uo pipefail
D=$HOME/.cache/gap-wave2-20260923/durable-memory/snap-probe
SNAP=$HOME/.cache/gap-wave2-20260923/durable-memory/snap-probe-copy
rm -rf "$D" "$SNAP"
mkdir -p "$D"
ip link set lo up
ai-memory init --data-dir "$D" >/dev/null 2>&1
sed -i 's/bind = "127.0.0.1:49374"/bind = "127.0.0.1:49591"/' "$D/config.toml"
export AI_MEMORY_EMBEDDING_PROVIDER=none
export AI_MEMORY_SERVER_URL=http://127.0.0.1:49591
nohup ai-memory serve --data-dir "$D" --transport http --bind 127.0.0.1:49591 --no-watcher >"$D/serve.log" 2>&1 &
SPID=$!
sleep 1.2
# concurrent write-page load: 8 pages fired in parallel
for i in $(seq 1 8); do
  ai-memory write-page --data-dir "$D" --path "scratch/concurrent-$i.md" --body "# concurrent probe $i" --title "concurrent $i" --workspace disposable-ws --project disposable-proj >/dev/null 2>&1 &
done
# take the snapshot mid-flight (best-effort race window)
sleep 0.05
cp -r "$D" "$SNAP" 2>/dev/null
wait
sleep 0.3
echo "== final status (source of truth after all writes land) =="
ai-memory status --data-dir "$D" | grep -E "pages|storage"
echo "== wiki files present in SOURCE dir now =="
find "$D/wiki" -iname 'concurrent-*.md' 2>/dev/null | wc -l
echo "== wiki files present in mid-flight SNAPSHOT copy =="
find "$SNAP/wiki" -iname 'concurrent-*.md' 2>/dev/null | wc -l
echo "== sqlite page rows for concurrent-* in SOURCE db (final) =="
sqlite3 "$D/db/memory.sqlite" "select count(*) from pages where path like 'scratch/concurrent-%';" 2>&1
echo "== sqlite page rows for concurrent-* in SNAPSHOT db (mid-flight copy, raw file copy of a live-written sqlite file) =="
sqlite3 "$SNAP/db/memory.sqlite" "select count(*) from pages where path like 'scratch/concurrent-%';" 2>&1
echo "== snapshot db integrity_check (raw-copied while being written) =="
sqlite3 "$SNAP/db/memory.sqlite" "pragma integrity_check;" 2>&1 | head -5
kill "$SPID" 2>/dev/null || true
wait "$SPID" 2>/dev/null || true
