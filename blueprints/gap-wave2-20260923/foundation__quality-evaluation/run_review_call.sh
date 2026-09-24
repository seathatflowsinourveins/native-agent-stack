#!/usr/bin/env bash
# One bounded native review call (codex | claude) on the frozen 20-case packet,
# with user hooks disabled and a process poller watching for ai-memory hook
# processes. The call runs in its own session (setsid), so only hook processes
# in that session are attributed to it; other sessions' hooks on this host are
# logged but not counted. Stdin is the prompt file, never an open terminal.
# Fix-round-2 note: the per-session attribution is withdrawn. Every sampled
# ai-memory hook process on this host is its own session leader (pid == sid), so a
# hook spawned by the reviewed CLI would not share the call's session either. The
# no-hook conclusion rests on disabled hooks, no tool calls and tool-use-only events
# (receipt 5). Parent-pid ancestry is not captured by this poller.
# Usage: run_review_call.sh codex|claude PACKET_DIR OUT_DIR
set -u
WHO=$1; PK=$2; OUT=$3; mkdir -p "$OUT"
EMPTY=$(mktemp -d $HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/review-cwd.XXXX)
POLL="$OUT/$WHO-hook-poller.txt"; SUM="$OUT/$WHO-hook-summary.txt"
poll() { while :; do ps -eo pid=,sid=,args= | grep -E 'ai-memory[^ ]* .*hook' | grep -v grep >> "$POLL"; sleep 0.02; done; }
: > "$POLL"; poll & PP=$!
# Sensitivity check: a 100 ms process with matching argv in its own session must be caught with that session id.
setsid bash -c 'exec -a "ai-memory-sensitivity-probe x hook --event probe" sleep 0.1' & PS=$!; wait $PS; sleep 0.2
echo "# sensitivity probe (sid $PS) caught: $(awk -v s=$PS '$2==s' "$POLL" | grep -c sensitivity-probe)" > "$SUM"
echo "# real codex exec processes before call: $(pgrep -f '^[^ ]*codex[^ ]* .*exec' | wc -l)" >> "$SUM"
echo "started_at $(date -u +%FT%TZ)" > "$OUT/$WHO-timing.txt"; S=$(date +%s%N)
if [ "$WHO" = codex ]; then
  setsid bash -c 'cd "$1" && exec timeout 900 codex exec --ignore-user-config --disable hooks --sandbox read-only --ephemeral \
      --skip-git-repo-check -C "$1" -m gpt-6-astra -c "model_reasoning_effort=\"medium\"" \
      --output-schema "$2/schema.json" -o "$3/codex-last-message.json" --json - < "$2/prompt.txt" > "$3/codex-events.jsonl" 2> "$3/codex.stderr"' \
      _ "$EMPTY" "$PK" "$OUT" & CP=$!
else
  setsid bash -c 'cd "$1" && exec timeout 900 claude -p --model sonnet --effort medium --setting-sources project --strict-mcp-config \
      --tools "" --no-session-persistence --output-format json --json-schema "$(cat "$2/schema.json")" < "$2/prompt.txt" > "$3/claude-result.json" 2> "$3/claude.stderr"' \
      _ "$EMPTY" "$PK" "$OUT" & CP=$!
fi
wait $CP; R=$?; E=$(date +%s%N)
echo "exit $R" >> "$OUT/$WHO-timing.txt"; echo "wall_ms $(( (E - S) / 1000000 ))" >> "$OUT/$WHO-timing.txt"
sleep 1; kill $PP; wait $PP 2>/dev/null
echo "# call session id: $CP" >> "$SUM"
echo "# ai-memory hook processes in the call's session: $(awk -v s=$CP '$2==s' "$POLL" | wc -l)" >> "$SUM"
echo "# ai-memory hook process samples from other sessions on this host (not attributed): $(awk -v s=$CP -v p=$PS '$2!=s && $2!=p' "$POLL" | wc -l)" >> "$SUM"
rmdir "$EMPTY" 2>/dev/null; echo "exit=$R"
