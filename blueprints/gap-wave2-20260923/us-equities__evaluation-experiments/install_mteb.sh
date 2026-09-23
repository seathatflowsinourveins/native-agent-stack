#!/usr/bin/env bash
set -uo pipefail
C=${HOME}/.cache/gap-wave2-20260923/evaluation-experiments
export UV_CACHE_DIR=$C/uv-cache UV_NO_CONFIG=1
echo "== mteb $(date -u +%FT%TZ)"; uv pip install --python $C/venv-mteb/bin/python --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cpu 'mteb==2.21.0' torch; echo "exit[mteb]=$? $(date -u +%FT%TZ)"
