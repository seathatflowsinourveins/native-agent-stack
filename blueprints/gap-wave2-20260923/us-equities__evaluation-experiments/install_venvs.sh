#!/usr/bin/env bash
set -uo pipefail
C=${HOME}/.cache/gap-wave2-20260923/evaluation-experiments
export UV_CACHE_DIR=$C/uv-cache UV_PYTHON_INSTALL_DIR=$C/pythons UV_NO_CONFIG=1
PY=${HOME}/.local/share/codex-ecosystem/bin/python3.13
inst() { name=$1; shift; echo "== $name $(date -u +%FT%TZ)"; uv venv -q --python "$PY" $C/venv-$name && uv pip install --python $C/venv-$name/bin/python "$@"; echo "exit[$name]=$? $(date -u +%FT%TZ)"; }
inst inspect 'inspect-ai==0.3.266'
inst river 'river==0.26.1'
inst mlflow 'mlflow==3.16.1'
inst phoenix 'arize-phoenix==20.14.0' 'opentelemetry-exporter-otlp-proto-http' 'opentelemetry-sdk'
echo "== mteb $(date -u +%FT%TZ)"; uv venv -q --python "$PY" $C/venv-mteb && uv pip install --python $C/venv-mteb/bin/python --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cpu 'mteb==2.21.0' 'torch==*+cpu'; echo "exit[mteb]=$? $(date -u +%FT%TZ)"
echo "== skfolio-lock"; uv venv -q --python "$PY" $C/venv-skfolio && uv pip sync --python $C/venv-skfolio/bin/python --require-hashes "$(cd "$(dirname "$0")/../../.." && pwd)"/blueprints/us-equities/research-evaluation/requirements.lock; echo "exit[skfolio]=$?"
echo "== py314"; uv python install 3.14.7; echo "exit[py314]=$?"
