#!/usr/bin/env bash
# Source: SDK v1.49.6 Dockerfile and wheel installation path; pins.json + README.md.
set -euo pipefail
umask 077
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="$HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6"
state="$HOME/.local/state/native-agent-stack/runtime-workers/openhands"
# host.py checks rootless Docker, source/requirement sha256, private host values
# and skill hashes before downloading or installing. No sudo, no service changes.
exec python3 "$recipe_dir/host.py" install --prefix "$prefix" --state "$state"
