#!/bin/sh
# Safe form of connect-local-llm.sh, the first pass's local-model connection recipe.
#
# connect-local-llm.sh stays as the record of what the first pass ran, and it is unsafe:
# it put the llama.cpp API key into two process argument lists (curl's -H value and
# `brv providers connect --api-key`). Any local user can read a running process's arguments
# through /proc/<pid>/cmdline or `ps`, however carefully the saved output is redacted.
#
# Usage: sh connect-local-llm-safe.sh <key-file> [<base-url> [<models-out>]]
#   <key-file>    the private file (mode 0600, outside every worktree) whose first line is the
#                 key. Pass a pointer variable, never the value:
#                 sh connect-local-llm-safe.sh "$LLAMACPP_KEY_FILE"
#   <base-url>    default http://127.0.0.1:18232/v1
#   <models-out>  where the /models response goes; default llamacpp-v1-models.json
# Do not run it with `sh -x`, which would trace the header line.
#
# Step 1, reachability, is automatic. The shell's `read` builtin loads the key, and curl gets
# the Authorization header on standard input (`-H @-`, curl 7.55.0 and later). `printf` is a
# shell builtin in sh and bash, so the key never enters an argument list or an environment.
# The only thing on a command line is the key file's path.
#
# Step 2, ByteRover's provider connection, is manual, because ByteRover 3.16.1 has no stdin,
# file or environment option for a provider key. It takes the key in only three ways:
#   - `--api-key <key>`: puts the key on the command line. Never use it.
#   - the CLI wizard (`brv providers connect` with no arguments): its openai-compatible key
#     prompt is a plain input prompt, not the masked password prompt other providers get,
#     so it echoes the key on screen (src/oclif/commands/providers/connect.ts:383-390,
#     725-730; masked prompt 286-296). The key reaches no argument list, but use the wizard
#     only in a private terminal that is not being recorded.
#   - the web UI's provider flow: base URL, then a password field that hides the key, for
#     openai-compatible too (src/webui/features/provider/components/provider-flow/
#     api-key-step.tsx:46-56, provider-flow-dialog.tsx:214-217, 350-353, 429-438). This is
#     the one ByteRover itself masks.
# The script prints the web UI steps. The daemon serves the web UI on 127.0.0.1 only
# (src/server/constants.ts:43). ByteRover then stores the key encrypted in its data
# directory, and `brv providers disconnect openai-compatible` deletes it
# (../source-review.json#connect-*, #webui-*, #transport-host-loopback, #provider-keychain,
# #disconnect-deletes-key).
set -eu
keyfile=${1:?usage: sh connect-local-llm-safe.sh <key-file> [<base-url> [<models-out>]]}
base_url=${2:-http://127.0.0.1:18232/v1}
models_out=${3:-llamacpp-v1-models.json}
[ -f "$keyfile" ] || { echo "no such key file" >&2; exit 2; }

KEY=""
IFS= read -r KEY < "$keyfile" || [ -n "$KEY" ]
[ -n "$KEY" ] || { echo "the key file's first line is empty" >&2; exit 2; }

echo "== reachability: $base_url/models (header on curl's standard input)"
code=$(printf 'Authorization: Bearer %s\n' "$KEY" | curl -sS -o "$models_out" -w '%{http_code}' -H @- "$base_url/models")
KEY=""
unset KEY
echo "http_code=$code"

cat <<EOF
== provider connection: in ByteRover's web UI, not on a command line
1. Run \`brv webui\`; it prints the URL (http://localhost:7700 by default) and tries to open a browser.
2. Providers -> OpenAI Compatible -> base URL: $base_url
3. API key: type or paste it into the password field, which hides it -> Change.
4. Pick the model (qwen3.8-27b-local on the workstation).
Then confirm without the key: brv providers list --format json; brv model --format json
Remove it again with: brv providers disconnect openai-compatible --format json
EOF
