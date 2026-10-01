#!/usr/bin/env bash
# Run a command in a private network namespace (loopback only), / read-only, /mnt hidden, and a scratch
# CODEX_HOME, so no run touches ~/.codex (auth, state databases, sessions) or reaches a real provider.
# Usage: sandbox.sh ARM_DIR command [args...]
set -euo pipefail
arm="$1"; shift
mkdir -p "$arm/home" "$arm/tmp" "$arm/codex-home"
exec bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --tmpfs /mnt \
  --bind "$arm" "$arm" \
  --unshare-net --unshare-pid --unshare-ipc --die-with-parent --new-session \
  --setenv HOME "$arm/home" --setenv TMPDIR "$arm/tmp" --setenv CODEX_HOME "$arm/codex-home" \
  --unsetenv CODEX_COMPANION_SESSION_ID --unsetenv CODEX_COMPANION_TRANSCRIPT_PATH \
  --chdir "$arm" \
  "$@"
