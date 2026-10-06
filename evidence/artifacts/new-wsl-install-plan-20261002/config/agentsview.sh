#!/usr/bin/env bash
# Owned placement glue for kenn-io/agentsview@v0.43.0 (9be7745a).
# Source: internal/config/config.go:1920-1944,1997-2002; README.md:40-89,695.
set -euo pipefail
export AGENTSVIEW_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/agentsview"
export AGENTSVIEW_TELEMETRY_ENABLED=0
export AGENTSVIEW_DISABLE_UPDATE_CHECK=1
export AGENTSVIEW_ARCHIVE_CONTENT=usage
exec "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/tools/agentsview-0.43.0/agentsview" "$@"
