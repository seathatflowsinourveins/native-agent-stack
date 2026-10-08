#!/usr/bin/env bash
# anthropics/sandbox-runtime@d9aac2098351ca17f3743fbaf6ecbd0051b7e00e:README.md:166-179, src/cli.ts:274-341.
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
umask 077
srt_state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/sandbox-runtime-srt"
mkdir -p -- "$srt_state_root"
srt_session_probe="$(mktemp -d "$srt_state_root/run.XXXXXX")"
# Codex inherit=none drops exported fixtures; shell-quote only these synthetic
# values into the supplied command instead of changing the client's policy.
# Source: https://developers.openai.com/codex/config-reference/#shell_environment_policyinherit
# TMPDIR stays in the validated allowed fixture; Node v24.21.0 doc/api/os.md:418-420.
printf -v srt_fixture_bindings 'SRT_ACCEPT_POLICY=%q\nSRT_ACCEPT_DENY_READ=%q\nSRT_ACCEPT_DENY_WRITE=%q\nSRT_ACCEPT_ALLOWED_DIR=%q\nSRT_ACCEPT_DENIED_URL=%q\nTMPDIR=%q\nexport TMPDIR\n' \
  "$SRT_ACCEPT_POLICY" "$SRT_ACCEPT_DENY_READ" "$SRT_ACCEPT_DENY_WRITE" "$SRT_ACCEPT_ALLOWED_DIR" "$SRT_ACCEPT_DENIED_URL" "$SRT_ACCEPT_ALLOWED_DIR"
srt_native_recipe="$(cat <<'SRT'
set -euo pipefail
srt echo "hello world" || exit "$?"
printf 'SRT_HELLO_EXIT=0\n'
# Unsandboxed controls must succeed before each denial can count.
cat "$SRT_ACCEPT_DENY_READ" >/dev/null || exit "$?"
printf 'SRT_READ_CONTROL_EXIT=0\n'
sh -c 'printf "unsandboxed control\n" >> "$1"' _ "$SRT_ACCEPT_DENY_WRITE" || exit "$?"
printf 'SRT_WRITE_CONTROL_EXIT=0\n'
curl -fsS --max-time 15 --output /dev/null "$SRT_ACCEPT_DENIED_URL" || exit "$?"
printf 'SRT_NETWORK_CONTROL_EXIT=0\n'
# A permitted operation with this same policy must succeed.
srt --settings "$SRT_ACCEPT_POLICY" -- sh -c 'printf "allowed write\n" > "$1/srt-allowed.txt"' _ "$SRT_ACCEPT_ALLOWED_DIR" || exit "$?"
printf 'SRT_ALLOW_WRITE_EXIT=0\n'
srt_allowed_text="$(cat "$SRT_ACCEPT_ALLOWED_DIR/srt-allowed.txt")" || exit "$?"
test "$srt_allowed_text" = 'allowed write' || exit "$?"
printf 'SRT_ALLOW_WRITE_VERIFY_EXIT=0\n'
# The identical append child succeeds on an allowed path (policy-negative control).
srt --settings "$SRT_ACCEPT_POLICY" -- sh -c 'printf "sandboxed write\n" >> "$1"' _ "$SRT_ACCEPT_ALLOWED_DIR/srt-allowed.txt" || exit "$?"
printf 'SRT_APPEND_CONTROL_EXIT=0\n'
srt_appended_text="$(tail -n 1 "$SRT_ACCEPT_ALLOWED_DIR/srt-allowed.txt")" || exit "$?"
test "$srt_appended_text" = 'sandboxed write' || exit "$?"
printf 'SRT_APPEND_VERIFY_EXIT=0\n'
printf 'SRT_ALLOW_WRITE_CONTROL=passed\n'
srt_write_before="$(sha256sum "$SRT_ACCEPT_DENY_WRITE")" || exit "$?"
printf 'SRT_WRITE_DIGEST_CONTROL_EXIT=0\n'
srt_deny_read_rc=0
srt --settings "$SRT_ACCEPT_POLICY" cat "$SRT_ACCEPT_DENY_READ" >/dev/null || srt_deny_read_rc=$?
test "$srt_deny_read_rc" -ne 0 || exit 1
printf 'SRT_DENY_READ_EXIT=%s\n' "$srt_deny_read_rc"
srt_deny_write_rc=0
srt --settings "$SRT_ACCEPT_POLICY" -- sh -c 'printf "sandboxed write\n" >> "$1"' _ "$SRT_ACCEPT_DENY_WRITE" || srt_deny_write_rc=$?
test "$srt_deny_write_rc" -ne 0 || exit 1
srt_write_after="$(sha256sum "$SRT_ACCEPT_DENY_WRITE")" || exit "$?"
test "$srt_write_after" = "$srt_write_before" || exit 1
printf 'SRT_DENY_WRITE_PRESERVATION=passed\n'
printf 'SRT_DENY_WRITE_EXIT=%s\n' "$srt_deny_write_rc"
srt_deny_network_rc=0
srt --settings "$SRT_ACCEPT_POLICY" curl -fsS --max-time 15 --output /dev/null "$SRT_ACCEPT_DENIED_URL" || srt_deny_network_rc=$?
test "$srt_deny_network_rc" -ne 0 || exit 1
printf 'SRT_DENY_NETWORK_EXIT=%s\n' "$srt_deny_network_rc"
printf 'SRT_NATIVE_USE_OK\n'
SRT
)"
srt_native_recipe="$srt_fixture_bindings$srt_native_recipe"
srt_prompt="Use Claude Bash or Codex native exec_command first to execute the following Bash recipe as one command, exactly as supplied. The recipe binds its existing synthetic fixture paths. Do not create or replace a policy. Report the command exit code. A version check cannot satisfy this task.

$srt_native_recipe"
case "${SRT_ACCEPT_CLIENT:-claude}" in
  claude)
    (cd -- "$srt_fixture_root" && env CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 flock -w 3600 "${NATIVE_STACK_CLAUDE_SESSION_LOCK:-$HOME/.local/state/native-agent-stack/coordination/ns2604-coop/claude-session.lock}" claude -p "$srt_prompt" --max-turns 48 --append-system-prompt-file "$(dirname -- "${BASH_SOURCE[0]}")/acceptance-execution-instructions.txt" --effort max --tools Bash --output-format stream-json --verbose --allowedTools Bash) \
      </dev/null > "$srt_session_probe/events.jsonl" 2> "$srt_session_probe/stderr"
    ;;
  codex)
    codex exec --json --ephemeral --skip-git-repo-check -C "$srt_fixture_root" "$srt_prompt" \
      </dev/null > "$srt_session_probe/events.jsonl" 2> "$srt_session_probe/stderr"
    ;;
  *) printf 'SRT_ACCEPT_CLIENT must be claude or codex.\n' >&2; exit 2 ;;
esac
# Inspect returned native events, not the model's prose. Print no transcript.
python3 - "$srt_session_probe/events.jsonl" "${SRT_ACCEPT_CLIENT:-claude}" "$srt_native_recipe" <<'PY'
import json
import re
import shlex
import sys
from pathlib import Path

# Reuse accept.sh's bounded native-wrapper decoding; compare the inner Bash
# source exactly, since shlex tokens alone erase multiline/expansion distinctions.
def same_recipe(actual, expected):
    actual = actual.replace("\r\n", "\n").rstrip("\n")
    expected = expected.replace("\r\n", "\n").rstrip("\n")
    for _ in range(3):
        try:
            parts = shlex.split(actual)
        except ValueError:
            return False
        if parts[:2] == ["rtk", "proxy"]:
            actual = re.sub(r"^\s*rtk\s+proxy\s+", "", actual, count=1)
        elif parts[:1] == ["rtk"]:
            actual = re.sub(r"^\s*rtk\s+", "", actual, count=1)
        elif len(parts) == 3 and Path(parts[0]).name == "bash" and parts[1] in ("-c", "-lc"):
            actual = parts[2]
        else:
            break
    return actual.replace("\r\n", "\n").rstrip("\n") == expected

def controls_passed(text):
    positive = ("HELLO", "READ_CONTROL", "WRITE_CONTROL", "NETWORK_CONTROL",
                "ALLOW_WRITE", "ALLOW_WRITE_VERIFY", "APPEND_CONTROL", "APPEND_VERIFY",
                "WRITE_DIGEST_CONTROL")
    for name in positive:
        values = re.findall(r"^SRT_" + name + r"_EXIT=([^\r\n]*)$", text, re.MULTILINE)
        if values != ["0"]:
            return False
    for name in ("READ", "WRITE", "NETWORK"):
        values = re.findall(r"^SRT_DENY_" + name + r"_EXIT=([^\r\n]*)$", text, re.MULTILINE)
        if len(values) != 1 or not re.fullmatch(r"[1-9][0-9]{0,2}", values[0]) or not 1 <= int(values[0]) <= 255:
            return False
    for marker in ("SRT_ALLOW_WRITE_CONTROL=passed", "SRT_DENY_WRITE_PRESERVATION=passed",
                   "SRT_NATIVE_USE_OK"):
        if text.splitlines().count(marker) != 1:
            return False
    return "hello world" in text.splitlines()

def completed_foreground_shell_calls(events):
    # Claude 2.1.289 native tool IDs and background semantics; integration proof.
    calls, complete = {}, set()
    partial = ("_(timed out after ", "_(process backgrounded after ",
               "Command did not complete within its ", "Command was manually backgrounded by user with ID:", "Command was moved to the background (ID:", "Command running in background with ID:", "Exit code:")
    for event in events:
        content = (event.get("message") if isinstance(event.get("message"), dict) else {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                name, args = block.get("name", ""), block.get("input", {})
                if name == "Bash":
                    calls[block["id"]] = not args.get("run_in_background", False)
                elif name.endswith("__ctx_execute") and args.get("language") == "shell":
                    calls[block["id"]] = not args.get("background", False)
            elif block.get("type") == "tool_result" and calls.get(block.get("tool_use_id")) and not block.get("is_error", False):
                value = block.get("content", "")
                text = value if isinstance(value, str) else "\n".join(
                    b.get("text", "") for b in value if isinstance(b, dict) and b.get("type") == "text")
                if not any(line.startswith(partial) for line in text.splitlines()):
                    complete.add(block["tool_use_id"])
    return complete

events = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
required = ('srt echo "hello world"', 'srt --settings', 'SRT_DENY_READ_EXIT=',
            'SRT_DENY_WRITE_EXIT=', 'SRT_DENY_NETWORK_EXIT=', 'SRT_ALLOW_WRITE_CONTROL=passed')
if sys.argv[2] == 'claude':
    calls = {}
    successful = set()
    for event in events:
        message = event.get('message') or {}
        content = message.get('content', []) if isinstance(message, dict) else []
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                command = (block.get('input') or {}).get('command', '')
                if same_recipe(command, sys.argv[3]) and all(part in command for part in required):
                    calls[block['id']] = command
            if isinstance(block, dict) and block.get('type') == 'tool_result' and not block.get('is_error', False):
                content = block.get('content', '')
                text = content if isinstance(content, str) else "\n".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
                if controls_passed(text):
                    successful.add(block.get('tool_use_id'))
    terminals = [e for e in events if e.get('type') == 'result']
    complete = (len(terminals) == 1 and terminals[0].get('subtype') == 'success'
                and not terminals[0].get('is_error', False)
                and not any(e.get('type') == 'error' for e in events))
    passed = complete and bool(set(calls) & successful & completed_foreground_shell_calls(events))
else:
    complete = (sum(e.get('type') == 'turn.completed' for e in events) == 1
                and not any(e.get('type') in ('error', 'turn.failed') for e in events))
    passed = complete and any(
        e.get('type') == 'item.completed'
        and (item := e.get('item', {})).get('type') == 'command_execution'
        and item.get('status') == 'completed'
        and item.get('exit_code') == 0
        and same_recipe(item.get('command', ''), sys.argv[3])
        and all(part in item.get('command', '') for part in required)
        and controls_passed(item.get('aggregated_output', ''))
        for e in events)
if not passed:
    raise SystemExit('srt: fresh native shell execution and successful controls were not observed')
print(f'srt | fresh-{sys.argv[2]}-shell=passed | policy-controls=passed', file=sys.stderr)
PY
