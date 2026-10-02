#!/usr/bin/env bash
# Upstream SDK wheel install; uv lock hashes + uv's documented no-build-isolation.
set -euo pipefail
umask 077
prefix="$1"
export UV_CACHE_DIR=/state/cache/uv
export UV_PYTHON_DOWNLOADS=never
export UV_NO_CONFIG=1
export XDG_CACHE_HOME=/state/cache
if [[ ! -x "$prefix/venv/bin/python" ]]; then
  /bin/uv venv --python /usr/local/bin/python "$prefix/venv"
fi
# func-timeout is an sdist. Preinstall every build prerequisite from the same
# upstream lock, then prohibit isolated build dependency downloads.
/bin/uv pip install --python "$prefix/venv/bin/python" --require-hashes --no-deps \
  --only-binary :all: --index-url https://pypi.org/simple \
  -r /recipe/build-requirements.lock
/bin/uv pip install --python "$prefix/venv/bin/python" --require-hashes --no-deps \
  --no-build-isolation --index-url https://pypi.org/simple -r /recipe/requirements.lock
/bin/uv pip check --python "$prefix/venv/bin/python"
"$prefix/venv/bin/python" -c 'import importlib.metadata as m; assert m.version("openhands-sdk") == m.version("openhands-tools") == "1.50.0"; from openhands.sdk import LLM, Agent, Conversation; from openhands.tools.terminal import TerminalTool; from openhands.tools.file_editor import FileEditorTool; print("SDK/tools 1.50.0 imports passed; no model request")'
