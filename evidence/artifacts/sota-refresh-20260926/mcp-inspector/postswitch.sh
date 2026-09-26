#!/usr/bin/env bash
# Post-switch check through the production PATH entry, mirroring the host use receipt
# nativestack-5975wx-20260925--mcp-inspector--use--20260925-2 (CLI mode only; no web UI, no --version).
export MCP_AUTO_OPEN_ENABLED=false
set -euo pipefail
INSPECTOR=$(command -v mcp-inspector) || { echo "mcp-inspector not on PATH" >&2; exit 1; }
RESOLVED=$(readlink -f "$INSPECTOR")
echo "mcp-inspector resolves: $INSPECTOR -> $RESOLVED"
PREFIX="${RESOLVED%%/lib/node_modules/*}"
NPM_LS=$(npm ls --global --prefix "$PREFIX" --depth=0 --json)
INSTALLED_VERSION=$(printf '%s' "$NPM_LS" | python3 -c "import json,sys; print(json.load(sys.stdin)['dependencies']['@modelcontextprotocol/inspector']['version'])")
echo "installed version (npm ls, not --version): $INSTALLED_VERSION"
test "$INSTALLED_VERSION" = "2.8.0"
QMD=$(command -v qmd) || { echo "qmd not on PATH" >&2; exit 1; }
echo "qmd: $("$QMD" --version)"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/docs"
MARK="mcpi-post-$$-$RANDOM"
printf '# Scratch fixture\n\n%s appears exactly once in this fresh fixture file.\n' "$MARK" > "$T/docs/note.md"
( cd "$T" && "$QMD" init >/dev/null && "$QMD" collection add "$T/docs" --name scratch >/dev/null && "$QMD" update >/dev/null )
printf '{"mcpServers":{"qmd":{"type":"stdio","command":"%s","args":["mcp"]}}}' "$QMD" > "$T/mcp.json"
LIST_JSON=$(timeout 60 "$INSPECTOR" --cli --config "$T/mcp.json" --server qmd --method tools/list --format json --stored-auth-only --cwd "$T")
python3 -c "
import json, sys
d = json.loads(sys.argv[1])
names = sorted(t['name'] for t in d['result']['tools'])
assert names == ['get', 'multi_get', 'query', 'status'], names
print('tools/list OK, tool names:', names)
" "$LIST_JSON"
CALL_ARGS=$(printf '{"searches":[{"type":"lex","query":"%s"}],"limit":5,"collections":["scratch"],"rerank":false}' "$MARK")
CALL_JSON=$(timeout 60 "$INSPECTOR" --cli --config "$T/mcp.json" --server qmd --method tools/call --tool-name query --tool-args-json "$CALL_ARGS" --format json --stored-auth-only --cwd "$T")
python3 -c "
import json, sys
d = json.loads(sys.argv[1]); mark = sys.argv[2]
text = d['result']['content'][0]['text']; hits = d['result']['structuredContent']['results']
assert 'Found 1 result' in text and mark in text, text
assert len(hits) == 1 and hits[0]['file'] == 'scratch/note.md' and hits[0]['score'] == 1, hits
print('tools/call query OK, hit:', hits[0]['file'])
" "$CALL_JSON" "$MARK"
set +e
timeout 60 "$INSPECTOR" --cli --config "$T/mcp.json" --server qmd --method tools/call --tool-name does_not_exist_probe --tool-args-json '{}' --format json --stored-auth-only --cwd "$T" >/dev/null 2>"$T/err.json"
RC=$?
set -e
echo "positive-control exit code: $RC"
test "$RC" -eq 5
python3 -c "
import json, sys
d = json.loads(open(sys.argv[1]).read().strip().splitlines()[-1])
assert d['error']['code'] == 'tool_not_found', d
print('positive control OK: exit 5,', d['error']['code'])
" "$T/err.json"
echo "ALL CHECKS PASSED"
