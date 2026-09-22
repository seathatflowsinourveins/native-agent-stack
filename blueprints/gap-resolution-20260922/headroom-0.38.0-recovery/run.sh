#!/usr/bin/env bash
# Install headroom-ai[mcp]==0.38.0 into a NEW isolated uv-tool prefix (never
# touches the pinned 0.37.0 at
# /home/example/.local/share/codex-ecosystem/python-tools-versioned/headroom-ai-0.37.0/),
# then run the same guarded MCP compress/retrieve recovery check the 0.37.0
# receipt (evidence/receipts/native-headroom-mcp-20260920.json) ran, using this
# repo's owned fixtures/rag-note.md as the compressed artifact.
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
