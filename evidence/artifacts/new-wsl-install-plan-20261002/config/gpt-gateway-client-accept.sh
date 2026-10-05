#!/usr/bin/env bash
# openai/codex@rust-v0.160.0:codex-rs/exec/src/cli.rs (--json, --ephemeral),
# https://developers.openai.com/codex/noninteractive (turn.completed).
# The destination profile is rendered by tools/adoption/new_wsl_client_config.py
# from adoption/templates/codex.omniroute.config.toml, with base_url on 21128.
# This literal is the recorded keyless-loopback placeholder, never a credential.
set -euo pipefail
gateway_session_probe="$(mktemp -d)"
trap 'rm -rf -- "$gateway_session_probe"' EXIT
gateway_session_rc=0
OMNIROUTE_API_KEY=keyless-loopback codex exec -p omniroute --json --ephemeral \
  'Reply with exactly GATEWAY_OK. Do not use tools.' </dev/null > "$gateway_session_probe/events.jsonl" || gateway_session_rc=$?
printf 'gpt-gateway | native-codex-exit=%s\n' "$gateway_session_rc" >&2
(( gateway_session_rc == 0 )) || exit "$gateway_session_rc"
python3 - "$gateway_session_probe/events.jsonl" <<'PY'
import json
import sys
from pathlib import Path

events = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
if any(event.get('type') == 'turn.failed' for event in events):
    raise SystemExit('gpt-gateway: native turn.failed')
if not any(event.get('type') == 'turn.completed' for event in events):
    raise SystemExit('gpt-gateway: native turn.completed was not observed')
if not any(event.get('type') == 'item.completed'
           and event.get('item', {}).get('type') == 'agent_message'
           and event['item'].get('text', '').strip() == 'GATEWAY_OK'
           for event in events):
    raise SystemExit('gpt-gateway: fixed native response was not observed')
print('gpt-gateway | fresh-codex-turn=completed | fixed-response=passed', file=sys.stderr)
PY
