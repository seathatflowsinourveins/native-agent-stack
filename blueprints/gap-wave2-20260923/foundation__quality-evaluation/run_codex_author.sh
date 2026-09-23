#!/usr/bin/env bash
# Fix round 2, gap 0: one Codex call authors the 30-case hard-negative set.
# Read-only sandbox, ephemeral session, user config and hooks disabled, empty
# working directory, prompt on stdin, schema-constrained final message.
# Usage: run_codex_author.sh PACKET_DIR OUT_DIR
set -u
PK=$1; OUT=$2; mkdir -p "$OUT"
EMPTY=$(mktemp -d "$HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround2/author-cwd.XXXX")
echo "real codex exec processes before call: $(pgrep -f '^[^ ]*codex[^ ]* .*exec' | wc -l)" > "$OUT/codex-author-timing.txt"
echo "started_at $(date -u +%FT%TZ)" >> "$OUT/codex-author-timing.txt"; S=$(date +%s%N)
( cd "$EMPTY" && timeout 900 codex exec --ignore-user-config --disable hooks --sandbox read-only --ephemeral \
    --skip-git-repo-check -C "$EMPTY" -m gpt-6-astra -c 'model_reasoning_effort="medium"' \
    --output-schema "$PK/schema.json" -o "$OUT/codex-author-last-message.json" --json - < "$PK/prompt.txt" \
    > "$OUT/codex-author-events.jsonl" 2> "$OUT/codex-author.stderr" )
R=$?; E=$(date +%s%N)
echo "exit $R" >> "$OUT/codex-author-timing.txt"; echo "wall_ms $(( (E - S) / 1000000 ))" >> "$OUT/codex-author-timing.txt"
echo "finished_at $(date -u +%FT%TZ)" >> "$OUT/codex-author-timing.txt"
rmdir "$EMPTY" 2>/dev/null; echo "exit=$R"
