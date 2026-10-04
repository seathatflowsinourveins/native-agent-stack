#!/usr/bin/env bash
# Run a command in a private network namespace (loopback only) with Windows paths hidden.
# Usage: sandbox.sh ARM_DIR command [args...]
# - --unshare-net: listeners are private to the namespace; nothing on the host can reach them and no host port is used.
# - --tmpfs /mnt: /mnt/c and every Windows executable are absent, so no browser or powershell.exe can start.
# - / is read-only; only ARM_DIR is writable; HOME points inside ARM_DIR.
# - MCP_AUTO_OPEN_ENABLED=false as the documented agent setting (PR #275).
set -euo pipefail
arm="$1"; shift
mkdir -p "$arm/home" "$arm/tmp"
exec bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --tmpfs /mnt \
  --bind "$arm" "$arm" \
  --unshare-net --unshare-pid --unshare-ipc --die-with-parent --new-session \
  --setenv HOME "$arm/home" --setenv TMPDIR "$arm/tmp" \
  --setenv MCP_AUTO_OPEN_ENABLED false --setenv NO_UPDATE_NOTIFIER 1 --setenv NPM_CONFIG_UPDATE_NOTIFIER false \
  --chdir "$arm" \
  "$@"
