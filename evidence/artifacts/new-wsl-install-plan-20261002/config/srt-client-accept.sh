#!/usr/bin/env bash
# anthropics/sandbox-runtime@v0.0.78:README.md:166-179, src/cli.ts:276-324.
# Fresh-session integration, separate from the unchanged upstream smoke.
# Fixtures are existing disposable deny/allow controls from the host executor;
# never point these variables at credentials or operator files.
# Native session/receipt formats: Claude Code headless docs and
# openai/codex@rust-v0.160.0:codex-rs/exec/src/cli.rs, --json/--ephemeral.
set -euo pipefail
: "${SRT_ACCEPT_FIXTURE_ROOT:?Set the existing disposable fixture directory}"
: "${SRT_ACCEPT_POLICY:?Set an existing policy JSON in the fixture directory}"
: "${SRT_ACCEPT_DENY_READ:?Set an existing synthetic denyRead file}"
: "${SRT_ACCEPT_DENY_WRITE:?Set an existing disposable protected file}"
: "${SRT_ACCEPT_ALLOWED_DIR:?Set the existing allowWrite directory}"
SRT_ACCEPT_DENIED_URL="${SRT_ACCEPT_DENIED_URL:-https://example.com}"
srt_fixture_root="$(realpath -e -- "$SRT_ACCEPT_FIXTURE_ROOT")"
for fixture in "$SRT_ACCEPT_POLICY" "$SRT_ACCEPT_DENY_READ" "$SRT_ACCEPT_DENY_WRITE" "$SRT_ACCEPT_ALLOWED_DIR"; do
  case "$(realpath -e -- "$fixture")" in
    "$srt_fixture_root"/*) ;;
    *) printf 'srt: every fixture must be inside SRT_ACCEPT_FIXTURE_ROOT.\n' >&2; exit 1 ;;
  esac
done
test -f "$SRT_ACCEPT_POLICY"
test -f "$SRT_ACCEPT_DENY_READ"
test -f "$SRT_ACCEPT_DENY_WRITE"
test -d "$SRT_ACCEPT_ALLOWED_DIR"
export SRT_ACCEPT_POLICY SRT_ACCEPT_DENY_READ SRT_ACCEPT_DENY_WRITE SRT_ACCEPT_ALLOWED_DIR SRT_ACCEPT_DENIED_URL
srt_session_probe="$(mktemp -d)"
trap 'rm -rf -- "$srt_session_probe"' EXIT
srt_native_recipe="$(cat <<'SRT'
set -euo pipefail
srt echo "hello world"
# Unsandboxed controls must succeed before each denial can count.
cat "$SRT_ACCEPT_DENY_READ" >/dev/null
sh -c 'printf "unsandboxed control\n" >> "$1"' _ "$SRT_ACCEPT_DENY_WRITE"
curl -fsS --max-time 15 --output /dev/null "$SRT_ACCEPT_DENIED_URL"
# A permitted operation with this same policy must succeed.
srt --settings "$SRT_ACCEPT_POLICY" -- sh -c 'printf "allowed write\n" > "$1/srt-allowed.txt"' _ "$SRT_ACCEPT_ALLOWED_DIR"
test "$(cat "$SRT_ACCEPT_ALLOWED_DIR/srt-allowed.txt")" = 'allowed write'
# The identical append child succeeds on an allowed path (policy-negative control).
srt --settings "$SRT_ACCEPT_POLICY" -- sh -c 'printf "sandboxed write\n" >> "$1"' _ "$SRT_ACCEPT_ALLOWED_DIR/srt-allowed.txt"
test "$(tail -n 1 "$SRT_ACCEPT_ALLOWED_DIR/srt-allowed.txt")" = 'sandboxed write'
printf 'SRT_ALLOW_WRITE_CONTROL=passed\n'
srt_write_before="$(sha256sum "$SRT_ACCEPT_DENY_WRITE")"
srt_deny_read_rc=0
srt --settings "$SRT_ACCEPT_POLICY" cat "$SRT_ACCEPT_DENY_READ" >/dev/null || srt_deny_read_rc=$?
test "$srt_deny_read_rc" -ne 0
printf 'SRT_DENY_READ_EXIT=%s\n' "$srt_deny_read_rc"
srt_deny_write_rc=0
srt --settings "$SRT_ACCEPT_POLICY" -- sh -c 'printf "sandboxed write\n" >> "$1"' _ "$SRT_ACCEPT_DENY_WRITE" || srt_deny_write_rc=$?
test "$srt_deny_write_rc" -ne 0
test "$(sha256sum "$SRT_ACCEPT_DENY_WRITE")" = "$srt_write_before"
printf 'SRT_DENY_WRITE_EXIT=%s\n' "$srt_deny_write_rc"
srt_deny_network_rc=0
srt --settings "$SRT_ACCEPT_POLICY" curl -fsS --max-time 15 --output /dev/null "$SRT_ACCEPT_DENIED_URL" || srt_deny_network_rc=$?
test "$srt_deny_network_rc" -ne 0
printf 'SRT_DENY_NETWORK_EXIT=%s\n' "$srt_deny_network_rc"
printf 'SRT_NATIVE_USE_OK\n'
SRT
)"
srt_prompt="Use your native shell tool to execute the following Bash recipe as one command, exactly as supplied. The SRT_ACCEPT_* variables name existing synthetic fixtures. Do not create or replace a policy. Report the command exit code. A version check cannot satisfy this task.

$srt_native_recipe"
case "${SRT_ACCEPT_CLIENT:-claude}" in
  claude)
    claude -p --effort max --output-format stream-json --verbose --allowedTools Bash --max-turns 4 "$srt_prompt" > "$srt_session_probe/events.jsonl"
    ;;
  codex)
    codex exec --json --ephemeral "$srt_prompt" </dev/null > "$srt_session_probe/events.jsonl"
    ;;
  *) printf 'SRT_ACCEPT_CLIENT must be claude or codex.\n' >&2; exit 2 ;;
esac
# Inspect returned native events, not the model's prose. Print no transcript.
python3 - "$srt_session_probe/events.jsonl" "${SRT_ACCEPT_CLIENT:-claude}" <<'PY'
import json
import sys
from pathlib import Path

events = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
required = ('srt echo "hello world"', 'srt --settings', 'SRT_DENY_READ_EXIT=',
            'SRT_DENY_WRITE_EXIT=', 'SRT_DENY_NETWORK_EXIT=', 'SRT_ALLOW_WRITE_CONTROL=passed')
if sys.argv[2] == 'claude':
    calls = {}
    successful = set()
    for event in events:
        for block in (event.get('message') or {}).get('content', []):
            if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                command = (block.get('input') or {}).get('command', '')
                if all(part in command for part in required):
                    calls[block['id']] = command
            if isinstance(block, dict) and block.get('type') == 'tool_result' and not block.get('is_error', False):
                content = block.get('content', '')
                text = content if isinstance(content, str) else json.dumps(content)
                if 'SRT_NATIVE_USE_OK' in text and 'hello world' in text:
                    successful.add(block.get('tool_use_id'))
    complete = any(e.get('type') == 'result' and e.get('subtype') == 'success' and not e.get('is_error', False) for e in events)
    passed = complete and bool(set(calls) & successful)
else:
    complete = any(e.get('type') == 'turn.completed' for e in events)
    passed = complete and any(
        e.get('type') == 'item.completed'
        and (item := e.get('item', {})).get('type') == 'command_execution'
        and item.get('exit_code') == 0
        and all(part in item.get('command', '') for part in required)
        and 'SRT_NATIVE_USE_OK' in item.get('aggregated_output', '')
        and 'hello world' in item.get('aggregated_output', '')
        for e in events)
if not passed:
    raise SystemExit('srt: fresh native shell execution and successful controls were not observed')
print(f'srt | fresh-{sys.argv[2]}-shell=passed | policy-controls=passed', file=sys.stderr)
PY
