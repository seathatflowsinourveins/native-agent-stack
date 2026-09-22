#!/usr/bin/env bash
# HISTORICAL / SUPERSEDED — kept unmodified as the exact record of what this
# script actually ran (fix-round blocker finding, 2026-09-22).
#
# This script installs headroom-ai[mcp]==0.38.0 into a NEW isolated uv-tool
# prefix (correctly isolated from the pinned 0.37.0 install), but the MCP
# server it launches was NOT isolated: it omits HEADROOM_WORKSPACE_DIR,
# HEADROOM_OFFLINE and HEADROOM_TELEMETRY, so running it wrote into the live
# default Headroom store at ~/.headroom (ccr_store.db, session_stats.jsonl)
# and made an online update check (update_check.json), confirmed by file
# mtimes and content at the time of the fix-round finding. Its fixture
# (fixtures/rag-note.md, 351 bytes) also only ever triggered Headroom's
# no-op router, so it never exercised a real compressing transform. See
# run_v2.sh for the corrected, isolated re-run (disposable
# HEADROOM_WORKSPACE_DIR, HEADROOM_OFFLINE=1, HEADROOM_TELEMETRY=off, and a
# larger fixture that does trigger compression) and
# evidence/artifacts/gap-resolution-20260922/token-efficiency/
# headroom-0.38.0-upgrade-recovery.json for the corrected receipt. The
# ~/.headroom entries this script wrote were left in place: the fix-round
# task authorized removing them only with explicit coordinator authorization,
# which this round did not grant.
set -euo pipefail

PREFIX=/home/example/.local/share/codex-ecosystem/tools/headroom-ai-0.38.0
mkdir -p "$PREFIX/uv-tool-dir" "$PREFIX/bin"
export UV_TOOL_DIR="$PREFIX/uv-tool-dir"
export UV_TOOL_BIN_DIR="$PREFIX/bin"
export UV_PYTHON=/home/example/.local/share/codex-ecosystem/bin/python3.13

uv tool install --python 3.13 'headroom-ai[mcp]==0.38.0'

HB="$PREFIX/bin/headroom"
"$HB" --version
"$HB" --help | grep -iE 'compress|mcp' || true
"$HB" mcp --help

FIXTURE=/home/example/code/nas-wt-gap-token-observation/fixtures/rag-note.md
CONTENT_JSON=$(python3 -c "import json,sys; print(json.dumps({'content': open(sys.argv[1]).read()}))" "$FIXTURE")

OUT=${1:-/tmp/headroom-038-mcp-check}
mkdir -p "$OUT"

mcporter call --stdio "$HB" --stdio-arg mcp --stdio-arg serve \
  --stdio-arg --proxy-url --stdio-arg http://127.0.0.1:1 \
  --name headroom038check --tool headroom_compress \
  --args "$CONTENT_JSON" --output json --no-oauth > "$OUT/compress.json"

HASH=$(python3 -c "import json; print(json.load(open('$OUT/compress.json'))['hash'])")

mcporter call --stdio "$HB" --stdio-arg mcp --stdio-arg serve \
  --stdio-arg --proxy-url --stdio-arg http://127.0.0.1:1 \
  --name headroom038check --tool headroom_retrieve \
  --args "{\"hash\":\"$HASH\"}" --output json --no-oauth > "$OUT/retrieve.json"

mcporter call --stdio "$HB" --stdio-arg mcp --stdio-arg serve \
  --stdio-arg --proxy-url --stdio-arg http://127.0.0.1:1 \
  --name headroom038check --tool headroom_stats \
  --args '{}' --output json --no-oauth > "$OUT/stats.json"

python3 -c "
import json, hashlib
orig = open('$FIXTURE').read()
retrieved = json.load(open('$OUT/retrieve.json'))['original_content']
print('exact_match:', orig == retrieved)
print('orig_sha256:', hashlib.sha256(orig.encode()).hexdigest())
print('retrieved_sha256:', hashlib.sha256(retrieved.encode()).hexdigest())
"
