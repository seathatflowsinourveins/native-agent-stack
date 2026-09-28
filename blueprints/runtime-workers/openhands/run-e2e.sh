#!/usr/bin/env bash
# Real execution is explicitly deferred to the coordinator; no auto-install.
set -euo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="$HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6"
state="$HOME/.local/state/native-agent-stack/runtime-workers/openhands"
exec python3 "$recipe_dir/host.py" run --prefix "$prefix" --state "$state" "$@"
