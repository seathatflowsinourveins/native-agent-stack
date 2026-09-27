#!/usr/bin/env bash
# Upstream SDK sequence: GPTResearcher -> conduct_research -> write_report.
set -euo pipefail
umask 077
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="$HOME/.local/share/codex-ecosystem/tools/gpt-researcher-3.7.0"
state="$HOME/.local/state/native-agent-stack/runtime-workers/gpt-researcher"
host_file="${GPTR_HOST_FILE:-$state/host.json}"
model="${GPTR_MODEL:-cx/gpt-6-astra-max}"
judge_model="${GPTR_JUDGE_MODEL:-cx/gpt-6-astra-max}"
mkdir -p "$state/runs" "$state/work" "$state/cache" "$state/config" "$state/context-mode"
chmod 700 "$state" "$state/runs" "$state/work" "$state/cache" "$state/config" "$state/context-mode"
exec 9>"$state/e2e.lock"
flock -n 9 || { printf '%s\n' 'A GPT Researcher acceptance run is already active.' >&2; exit 1; }
run_dir="$(mktemp -d "$state/runs/attempt-XXXXXXXX")"
# env -i makes dotenv/provider inheritance explicit; the runner enters a private,
# empty working directory before importing upstream. Native MCP tools keep HOME.
run_status=0
timeout --signal=TERM --kill-after=20s 3700s env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 \
  XDG_CACHE_HOME="$state/cache" XDG_CONFIG_HOME="$state/config" \
  XDG_STATE_HOME="$state" UV_CACHE_DIR="$state/cache/uv" \
  HF_HOME="$state/cache/huggingface" NLTK_DATA="$state/cache/nltk" \
  PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 \
  "$prefix/venv/bin/python" "$recipe_dir/e2e/run.py" \
  --run-dir "$run_dir" --prefix "$prefix" --host-file "$host_file" --model "$model" \
  --judge-model "$judge_model" || run_status=$?
if [[ ! -f "$run_dir/receipt.json" ]]; then
  PYTHONDONTWRITEBYTECODE=1 python3 "$recipe_dir/e2e/receipt.py" "$run_dir" "$model" "$run_status"
fi
exit "$run_status"
