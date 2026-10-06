#!/usr/bin/env bash
# Owned placement glue for kenn-io/agentsview@v0.44.0 (413a87f7bfbd67b2815b1119ac51abc1efbeeaba).
# Source: internal/config/config.go:2051,2136,2139; scripts/install.sh:142-160.
set -euo pipefail
export AGENTSVIEW_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/agentsview"
export AGENTSVIEW_TELEMETRY_ENABLED=0
export AGENTSVIEW_DISABLE_UPDATE_CHECK=1
export AGENTSVIEW_ARCHIVE_CONTENT=usage
exec "${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}/tools/agentsview-0.44.0/agentsview" "$@"
