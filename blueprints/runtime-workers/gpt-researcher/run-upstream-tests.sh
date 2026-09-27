#!/usr/bin/env bash
# Run unchanged, non-network tests from the verified upstream source archive.
set -euo pipefail
umask 077
prefix="$HOME/.local/share/codex-ecosystem/tools/gpt-researcher-3.7.0"
state="$HOME/.local/state/native-agent-stack/runtime-workers/gpt-researcher"
source_dir="$prefix/source/gpt-researcher-0957c301ed06c2a5857b834358c7227c739041d4"
mkdir -p "$state/upstream-tests"
chmod 700 "$state/upstream-tests"
output="$(mktemp "$state/upstream-tests/result-XXXXXXXX.txt")"
cd "$source_dir"
status=0
env -i HOME="$HOME" PATH="$PATH" PYTHON_DOTENV_DISABLED=1 \
  XDG_CACHE_HOME="$state/cache" OPENAI_API_KEY=local-loopback \
  CONTEXT_FILTER=keyword \
  "$prefix/venv/bin/python" -m pytest -q -p no:cacheprovider \
  tests/test_lexical_context_filter.py tests/test_llm_kwargs_override.py \
  tests/test_llm_max_tokens.py tests/test_mcp_client_config.py \
  tests/test_mcp_client_non_dict_config.py tests/test_mcp_client_uppercase_url_schemes.py \
  >"$output" 2>&1 || status=$?
cat "$output"
printf 'upstream pytest exit code: %s\n' "$status" >>"$output"
exit "$status"
