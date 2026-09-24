#!/usr/bin/env bash
# Gap 6 fix round, arm R1b: does ai-memory 2.4.0 with the default (unset) embedding_provider report
# embedding enabled once its background model fetch completes and the server restarts?
# Isolated serve on 127.0.0.1:27375, temp --data-dir and HOME, AI_MEMORY_SERVER_URL set to it.
# Network: the server fetches all-MiniLM-L6-v2 (~87 MB) itself. Usage: r1b_default_embedding.sh OUT_FILE
set -uo pipefail
OUT=${1:?out file}
G=$HOME/.cache/gap-wave2-20260923/agents-models-workers/fix6b
BIN=$HOME/.cache/sota-refresh-20260923/pins-mem/ai-memory-2.4.0/ai-memory
rm -rf "$G" && mkdir -p "$G/data" "$G/home"
export AI_MEMORY_SERVER_URL=http://127.0.0.1:27375
: > "$OUT"
start() { HOME=$G/home "$BIN" serve --data-dir "$G/data" --transport http --bind 127.0.0.1:27375 >> "$G/serve.log" 2>&1 & echo $! > "$G/pid";
          for _ in $(seq 1 60); do ss -ltn | grep -q '127.0.0.1:27375 ' && return 0; sleep 0.5; done; return 1; }
stop() { kill "$(cat "$G/pid")"; for _ in $(seq 1 20); do ss -ltn | grep -q '127.0.0.1:27375 ' || return 0; sleep 0.5; done; }
status() { printf '\n### %s  (%s)\n' "$1" "$(date -u +%FT%TZ)" >> "$OUT"; HOME=$G/home "$BIN" status --data-dir "$G/data" 2>/dev/null | sed -n '/embeddings:/p;/providers:/,$p' >> "$OUT"; }
start; status "start 1 (fresh data dir, embedding_provider unset)"
t0=$(date +%s)
prev=-1; stable=0
while :; do  # done when the models dir is > 80 MB and unchanged for 10 s, or the server logs a load/fetch failure
  cur=$(du -sb "$G/data/models" | cut -f1)
  if [ "$cur" = "$prev" ] && [ "$cur" -gt 80000000 ]; then stable=$((stable + 2)); else stable=0; fi; prev=$cur
  [ "$stable" -ge 10 ] && break
  sed 's/\x1b\[[0-9;]*m//g' "$G/serve.log" | grep -q -i -E 'model load failed|fetch.*(failed|error)' && { echo "server logged a fetch/load failure" >> "$OUT"; break; }
  (( $(date +%s) - t0 > 600 )) && { echo "fetch wait timed out at 600 s" >> "$OUT"; break; }; sleep 2; done
printf '\n### models dir after fetch wait (%s s)\n' "$(( $(date +%s) - t0 ))" >> "$OUT"; ls -la "$G/data/models/all-MiniLM-L6-v2" >> "$OUT"; du -sh "$G/data/models" >> "$OUT"
stop; start; sleep 3; status "start 2 (after model fetch, restart)"
HOME=$G/home "$BIN" write-page --data-dir "$G/data" --workspace g2fix --project emb --path notes/a.md --title A --body "The central bank raised its policy rate." >/dev/null 2>&1
sleep 3; status "after one write-page"
stop
printf '\n### serve log (model/embedding lines)\n' >> "$OUT"; sed 's/\x1b\[[0-9;]*m//g' "$G/serve.log" | grep -E '^2026' | grep -i -E 'embed|model|fetch' | grep -v 'applying migration' >> "$OUT"
printf '\n### listeners after stop (expect none)\n' >> "$OUT"; ss -ltn | grep ':27375 ' >> "$OUT" || echo none >> "$OUT"
