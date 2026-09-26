#!/bin/sh
# UNSAFE AS RUN - DO NOT REUSE. Published record of the first pass's script: the commands
# below are unchanged (only the credential location and the scratch path are redacted).
# The curl line sends the key inside a -H argument, and `brv providers connect --api-key
# "$KEY"` passes it as an argument too. Any local user can read a running process's
# arguments through /proc/<pid>/cmdline or `ps`, and redacting the saved output does not
# undo that. Use connect-local-llm-safe.sh instead: the header goes to curl on standard input,
# and the key is typed into ByteRover's masked web UI field. credential-argv-probe.py shows
# the difference with a dummy value (../native-outputs/credential-argv-probe-20260926T111651Z.txt).
#
# Reads the local llama.cpp API key into an env var only; never echoes it.
# Not committed anywhere; lives only in the scratch dir.
set -eu
ECO="$HOME/.local/share/codex-ecosystem"
export PATH="$ECO/bin:$PATH"
export DO_NOT_TRACK=1 NO_UPDATE_NOTIFIER=1 MCP_AUTO_OPEN_ENABLED=false BRV_ENV=production

keydir="<credential location: not published>"
keyfile="<credential location: not published>"
KEY="$(cat "$keydir/$keyfile")"

echo "== reachability: llama.cpp :18232 /v1/models (key redacted) =="
code=$(curl -s -o <scratch>/trial-byterover/llamacpp-models.json -w '%{http_code}' "http://127.0.0.1:18232/v1/models" -H "Authorization: Bearer $KEY")
echo "http_code=$code"

echo "== brv providers connect openai-compatible (key redacted) =="
brv providers connect openai-compatible --base-url "http://127.0.0.1:18232/v1" --api-key "$KEY" --model qwen3.8-27b-local --format json
echo "connect_exit=$?"

unset KEY
echo "== brv providers list --format json =="
brv providers list --format json
echo "== brv providers --format json =="
brv providers --format json
echo "== brv model --format json =="
brv model --format json
