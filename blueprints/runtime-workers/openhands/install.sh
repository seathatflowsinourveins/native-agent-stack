#!/usr/bin/env bash
# Source: SDK v1.50.0 Dockerfile and wheel installation path; pins.json + README.md.
set -euo pipefail
umask 077
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="$HOME/.local/share/codex-ecosystem/tools/openhands-1.50.0"
state="$HOME/.local/state/native-agent-stack/runtime-workers/openhands"
# host.py checks rootless Docker, the locked grader, source/requirement sha256, private host values
# before downloading or installing. Project skills use the shared installer
# when a task workspace is created. No sudo, no service changes.
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$recipe_dir/host.py" install --prefix "$prefix" --state "$state"
