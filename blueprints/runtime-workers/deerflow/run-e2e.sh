#!/usr/bin/env bash
# References: Inspect Evals v0.22.0 GAIA README; Inspect AI 0.3.271 CLI.
set -euo pipefail
umask 077
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
frozen_id="${1:?Usage: run-e2e.sh FROZEN_GAIA_VALIDATION_ID (no attachments)}"
worker_state="$HOME/.local/state/native-agent-stack/runtime-workers/deerflow"
grader="$HOME/.local/share/codex-ecosystem/tools/deerflow-2.1.0/grader/bin/inspect"
test -x "$grader"
export PYTHONDONTWRITEBYTECODE=1
export INSPECT_EVALS_CACHE_DIR="$worker_state/eval-cache"
mkdir -p "$worker_state/runs" "$INSPECT_EVALS_CACHE_DIR"
run_logs="$(mktemp -d "$worker_state/runs/inspect-XXXXXXXX")"
model="$(PYTHONPATH="$recipe_dir" python3 -c 'from recipe import STATE, read, worker_model; print(worker_model(read(STATE / "host.json")))' 2>/dev/null)"
# No Inspect model call: the solver uses DeerFlow; gaia_scorer is deterministic.
export OPENAI_API_KEY=local-loopback
exec "$grader" eval "$recipe_dir/e2e/gaia.py@deerflow_gaia" \
  -T "instance_ids=$frozen_id" --model "openai/$model" \
  --model-base-url http://127.0.0.1:20128/v1 \
  --max-samples 1 --epochs "${DEERFLOW_EPOCHS:-1}" --log-dir "$run_logs"
