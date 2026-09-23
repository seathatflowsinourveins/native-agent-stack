#!/usr/bin/env bash
# Re-run of the ai-memory half of local-ai-memory-qdrant-rebind with explicit server isolation.
# The first run's status/search reads reached the live server (default server_url), so they
# compared the live store with itself. Here every client read names its disposable server.
set -u
S=~/codex-ecosystem/state/gap-resolution-20260922/recovery/app-state
O=$S/rerun-isolated
rm -rf "$O" && mkdir -p "$O"
export RESTIC_PASSWORD=gap-resolution-20260922-test   # fixed disposable test string (see receipt limitations)
unset AI_MEMORY_SERVER_URL AI_MEMORY_DATA_DIR
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$O/steps.log"; }

log "versions"; { restic version; ai-memory --version; } > "$O/versions.txt" 2>&1
log "snapshots"; restic -r "$S/repo" snapshots --json > "$O/snapshots.json" 2> "$O/snapshots.err"; echo "exit=$?" >> "$O/steps.log"
log "check --read-data"; restic -r "$S/repo" check --read-data > "$O/check.log" 2>&1; echo "exit=$?" >> "$O/steps.log"
log "restore latest"; restic -r "$S/repo" restore latest --target "$O/restored2" > "$O/restore.log" 2>&1; echo "exit=$?" >> "$O/steps.log"
R2=$(find "$O/restored2" -type d -name ai-memory-copy | head -1)
log "restored dir: ${R2#$O/}"
log "diff pre-backup copy vs fresh restore"; diff -r "$S/ai-memory-copy" "$R2" > "$O/diff-copy-vs-restore.txt" 2>&1; echo "exit=$?" >> "$O/steps.log"
log "baseline dir = copy of the pre-backup copy (server bookkeeping must not touch the original)"; cp -a "$S/ai-memory-copy" "$O/baseline-dir"

ai-memory serve --transport http --bind 127.0.0.1:49411 --data-dir "$O/baseline-dir" --allow-insecure-no-auth --no-watcher > "$O/baseline-server.log" 2>&1 &
BP=$!
ai-memory serve --transport http --bind 127.0.0.1:49412 --data-dir "$R2" --allow-insecure-no-auth --no-watcher > "$O/restored-server.log" 2>&1 &
RP=$!
for i in $(seq 1 90); do
  grep -q 'server ready' "$O/baseline-server.log" && grep -q 'server ready' "$O/restored-server.log" && break
  sleep 1
done
log "servers baseline_pid=$BP restored_pid=$RP ready_after=${i}s"

for arm in baseline restored; do
  if [ $arm = baseline ]; then URL=http://127.0.0.1:49411; DIR=$O/baseline-dir; else URL=http://127.0.0.1:49412; DIR=$R2; fi
  AI_MEMORY_SERVER_URL=$URL ai-memory status --data-dir "$DIR" --json > "$O/$arm-status.json" 2> "$O/$arm-status.err"; echo "$arm status exit=$?" >> "$O/steps.log"
  AI_MEMORY_SERVER_URL=$URL ai-memory search "handoff" --data-dir "$DIR" --workspace agent-lab --project agent-lab --limit 3 --json > "$O/$arm-search.json" 2> "$O/$arm-search.err"; echo "$arm search exit=$?" >> "$O/steps.log"
done
kill "$BP" "$RP"; wait "$BP" "$RP" 2>/dev/null
log "servers stopped"
