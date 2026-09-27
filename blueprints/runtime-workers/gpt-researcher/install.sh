#!/usr/bin/env bash
# Native source + PEP 517 build: upstream v3.7.0 pyproject.toml and getting-started.md.
set -euo pipefail
umask 077
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="$HOME/.local/share/codex-ecosystem/tools/gpt-researcher-3.7.0"
state="$HOME/.local/state/native-agent-stack/runtime-workers/gpt-researcher"
python_bin="${GPTR_PYTHON:-/usr/bin/python3.12}"
command -v uv >/dev/null
"$python_bin" -c 'import sys,platform; assert sys.version_info[:2] == (3,12) and platform.system() == "Linux" and platform.machine() == "x86_64", "lock target: Linux x86_64 / Python 3.12"'
mkdir -p "$state" "$state/cache" "$state/downloads" "$state/runs" "$state/work" "$state/config"
chmod 700 "$state" "$state/cache" "$state/downloads" "$state/runs" "$state/work" "$state/config"
exec 9>"$state/install.lock"
flock 9
export UV_CACHE_DIR="$state/cache/uv" UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME="$state/cache" XDG_CONFIG_HOME="$state/config"
"$python_bin" "$recipe_dir/install_support.py" "$recipe_dir" "$prefix" "$state"
if [[ ! -x "$prefix/venv/bin/python" ]]; then
  uv venv --python "$python_bin" --no-python-downloads "$prefix/venv"
fi
uv pip install --python "$prefix/venv/bin/python" --require-hashes --only-binary=:all: --no-deps -r "$recipe_dir/build-requirements.lock"
uv pip install --python "$prefix/venv/bin/python" --require-hashes --no-build-isolation --no-deps -r "$recipe_dir/requirements.lock"
# Source archive is verified before extraction. Build dependencies are already hash locked.
uv pip install --python "$prefix/venv/bin/python" --no-deps --no-build-isolation "$prefix/source/gpt-researcher-0957c301ed06c2a5857b834358c7227c739041d4"
if [[ ! -x "$prefix/proxy-venv/bin/python" ]]; then
  uv venv --python "$python_bin" --no-python-downloads "$prefix/proxy-venv"
fi
uv pip install --python "$prefix/proxy-venv/bin/python" --require-hashes --only-binary=:all: --no-deps -r "$recipe_dir/proxy-requirements.lock"
uv pip check --python "$prefix/venv/bin/python"
uv pip check --python "$prefix/proxy-venv/bin/python"
# DRB-II README installation: uv sync; retain its own native lock, separate from GPTR.
grader_source="$prefix/grader-source/DeepResearch-Bench-II-b38f360603db9531b102aef8c166cedb8509b6f6"
UV_PROJECT_ENVIRONMENT="$prefix/grader-venv" uv sync --locked --project "$grader_source" --python "$python_bin"
uv pip check --python "$prefix/grader-venv/bin/python"
"$prefix/venv/bin/python" -c 'from importlib.metadata import version; assert version("gpt-researcher") == "0.16.0"; from gpt_researcher.context.select import resolve_context_filter; assert resolve_context_filter("keyword") == "keyword"; print("source package 0.16.0; keyword filter import passed")'
cp "$recipe_dir/pins.json" "$prefix/installation-pins.json"
chmod 600 "$prefix/installation-pins.json"
printf '%s\n' 'Installed GPT Researcher v3.7.0 and pinned DRB-II grader. Live acceptance remains unmeasured.'
