#!/bin/sh
# CC runs after landing. This installs only the isolated sampler runtime,
# never services, timers, accounts, settings or credentials.
set -eu
if [ "$#" -ne 1 ]; then
  echo 'usage: sh install-runtime.sh /absolute/path/to/claude-usage-runtime' >&2
  exit 2
fi
task_runtime=$1
case "$task_runtime" in
  /*) ;;
  *) echo 'runtime target must be an absolute path' >&2; exit 2 ;;
esac
source_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
python3 -m venv "$task_runtime"
"$task_runtime/bin/python" -m pip install --disable-pip-version-check --no-input \
  --require-hashes --only-binary=:all: --index-url https://pypi.org/simple \
  -r "$source_dir/claude-usage/requirements.txt"
install -m 0644 "$source_dir/claude_usage_metrics.py" "$task_runtime/claude_usage_metrics.py"
install -m 0644 "$source_dir/claude_usage_sampler.py" "$task_runtime/claude_usage_sampler.py"
