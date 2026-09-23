#!/usr/bin/env bash
# Gap 6 fix round, arm R1: capture the ai-memory 2.3.2 and 2.4.0 CLI surface, default config and
# a disposable lifecycle, each against an isolated `serve` this script starts (temp --data-dir,
# temp HOME, loopback port) with AI_MEMORY_SERVER_URL pointing at that server. Never uses the
# live service (127.0.0.1:49374). Usage: r1_surface.sh OUT_DIR
set -uo pipefail
OUT=${1:?out dir}
G=$HOME/.cache/gap-wave2-20260923/agents-models-workers/fix6
BIN23=$HOME/.local/share/codex-ecosystem/bin/ai-memory
BIN24=$HOME/.cache/sota-refresh-20260923/pins-mem/ai-memory-2.4.0/ai-memory
rm -rf "$G" && mkdir -p "$G" "$OUT"
LOG="$OUT/6-r1-transcript.txt"; : > "$LOG"

run() { # label, then command; records exact argv, env and output
  local label=$1; shift
  { printf '\n### %s\n$ %s\n' "$label" "$*"; "$@" 2>&1; printf '[exit %s]\n' "$?"; } >> "$LOG"
}

for V in 23 24; do
  bin=BIN$V; bin=${!bin}; port=$((27351 + V))  # 2.3.2 -> 27374, 2.4.0 -> 27375
  mkdir -p "$G/s$V-data" "$G/s$V-home" "$G/i$V-data" "$G/i$V-home"
  HOME=$G/s$V-home AI_MEMORY_SERVER_URL=http://127.0.0.1:$port \
    "$bin" serve --data-dir "$G/s$V-data" --transport http --bind 127.0.0.1:$port > "$G/serve$V.log" 2>&1 &
  echo $! > "$G/serve$V.pid"
done
for port in 27374 27375; do
  for _ in $(seq 1 60); do ss -ltn | grep -q "127.0.0.1:$port " && break; sleep 0.5; done
done
{ echo "### listeners after start"; ss -ltnp 2>/dev/null | grep -E ':2737[45] ' ; } >> "$LOG"

for V in 23 24; do
  bin=BIN$V; bin=${!bin}; port=$((27351 + V))
  export HOME=$G/i$V-home AI_MEMORY_SERVER_URL=http://127.0.0.1:$port
  { printf '\n## version %s  HOME=%s AI_MEMORY_SERVER_URL=%s\n' "$V" "$HOME" "$AI_MEMORY_SERVER_URL"; sha256sum "$bin"; } >> "$LOG"
  run "v$V --version" "$bin" --version
  run "v$V --help" "$bin" --help
  run "v$V backfill --help" "$bin" backfill --help
  run "v$V bootstrap --help" "$bin" bootstrap --help
  run "v$V embed --help" "$bin" embed --help
  run "v$V init" "$bin" init --data-dir "$G/i$V-data"
  grep -v '^\s*#' "$G/i$V-data/config.toml" | grep -v '^\s*$' | grep -v token_pepper > "$OUT/6-config-noncomment-v$V.toml"
  run "v$V status (server data dir)" "$bin" status --data-dir "$G/s$V-data"
  run "v$V status --json (server data dir)" "$bin" status --data-dir "$G/s$V-data" --json
  # MCP tool surface of the isolated server (stateless Streamable HTTP): initialize, then tools/list.
  H=(-sS -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2025-06-18')
  run "v$V MCP initialize" curl "${H[@]}" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"g2fix","version":"0"}}}' "http://127.0.0.1:$port/mcp"
  curl "${H[@]}" -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' "http://127.0.0.1:$port/mcp" > "$OUT/6-mcp-tools-v$V.raw" 2>&1
  { printf '\n### v%s MCP tools/list names (full response: 6-mcp-tools-v%s.raw)\n' "$V" "$V"; sed -n 's/^data: //p; /^{/p' "$OUT/6-mcp-tools-v$V.raw" | python3 -c 'import json,sys; [print(t["name"]) for l in sys.stdin if l.strip() for t in json.loads(l).get("result",{}).get("tools",[])]'; } >> "$LOG"
done

# Disposable lifecycle on 2.4.0 against its isolated server.
export HOME=$G/i24-home AI_MEMORY_SERVER_URL=http://127.0.0.1:27375
D="$G/s24-data"
run "v24 write-page" "$BIN24" write-page --data-dir "$D" --workspace g2fix --project lifecycle --path notes/probe.md --title Probe --body "gap6 fix-round lifecycle probe marker zebra-quartz"
run "v24 search" "$BIN24" search --data-dir "$D" --workspace g2fix --project lifecycle "zebra-quartz" --json
run "v24 read-page" "$BIN24" read-page --data-dir "$D" --workspace g2fix --project lifecycle --path notes/probe.md
run "v24 handoffs" "$BIN24" handoffs --data-dir "$D" --workspace g2fix --project lifecycle
run "v24 status after write" "$BIN24" status --data-dir "$D"
run "v24 backup" "$BIN24" backup --data-dir "$D" --to "$G/backup24.tar.gz"
unset HOME AI_MEMORY_SERVER_URL; export HOME=$(getent passwd "$(id -u)" | cut -d: -f6)

{ printf '\n### non-comment default config diff (token_pepper excluded)\n'; diff "$OUT/6-config-noncomment-v23.toml" "$OUT/6-config-noncomment-v24.toml"; printf '[diff exit %s]\n' "$?"; } >> "$LOG"
{ printf '\n### toolchain probe on the default PATH\n$ command -v cargo rustc\n'; command -v cargo rustc; printf '[exit %s]\n' "$?"; } >> "$LOG"
{ printf '\n### requests seen by the isolated servers (detection that calls reached them)\n'; for V in 23 24; do printf 'serve%s.log lines: %s\n' "$V" "$(wc -l < "$G/serve$V.log")"; done; } >> "$LOG"
cp "$G/serve23.log" "$OUT/6-serve23.log"; cp "$G/serve24.log" "$OUT/6-serve24.log"

for V in 23 24; do kill "$(cat "$G/serve$V.pid")" 2>/dev/null; done
sleep 2
{ printf '\n### listeners after stop (expect none)\n'; ss -ltn | grep -E ':2737[45] ' || echo none; } >> "$LOG"
