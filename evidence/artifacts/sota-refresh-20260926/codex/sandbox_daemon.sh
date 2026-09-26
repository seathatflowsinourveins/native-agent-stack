#!/usr/bin/env bash
# sandbox.sh plus what an interactive launch and a background server need hidden: /run/user (the host
# session bus, the systemd user manager and the runtime directory) is an empty tmpfs, the session bus address is
# unset and XDG_RUNTIME_DIR is a scratch directory. Private network (loopback only), / read-only, /mnt hidden, a
# scratch HOME and CODEX_HOME per arm, and a private PID namespace, so every process started inside, including a
# detached background server, ends with the sandbox. The arm is mounted at /tmp/arm inside: the server's control
# socket (CODEX_HOME/app-server-control/app-server-control.sock) must fit in a 108-byte sun_path, and the first
# attempt, with the arm at its long scratch path, failed with "path must be shorter than SUN_LEN".
# Usage: sandbox_daemon.sh ARM_DIR command [args...]   (the command sees ARM_DIR as /tmp/arm)
set -euo pipefail
arm="$1"; shift
inner=/tmp/arm
mkdir -p "$arm/home" "$arm/tmp" "$arm/codex-home" "$arm/run"
chmod 700 "$arm/run"
exec bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --tmpfs /mnt --tmpfs /run/user \
  --bind "$arm" "$inner" \
  --unshare-net --unshare-pid --unshare-ipc --die-with-parent --new-session \
  --setenv HOME "$inner/home" --setenv TMPDIR "$inner/tmp" --setenv CODEX_HOME "$inner/codex-home" \
  --setenv XDG_RUNTIME_DIR "$inner/run" --setenv TERM xterm-256color \
  --unsetenv DBUS_SESSION_BUS_ADDRESS \
  --unsetenv CODEX_COMPANION_SESSION_ID --unsetenv CODEX_COMPANION_TRANSCRIPT_PATH \
  --chdir "$inner" \
  "$@"
