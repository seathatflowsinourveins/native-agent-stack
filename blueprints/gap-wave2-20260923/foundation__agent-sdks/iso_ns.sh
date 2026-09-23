#!/usr/bin/env bash
# Filesystem- and network-isolated launcher for one Codex SDK worker (agent-sdks gap wave 2, round 3).
#
# Run it as:
#   pasta --config-net -T none -U none -t none -u none --no-map-gw --quiet -- \
#     unshare --mount --pid --fork --mount-proc bash iso_ns.sh STAGE PROFILE -- CMD...
# pasta gives a user+network namespace with outbound internet but no forwarding to host loopback ports
# (-T/-U none, --no-map-gw). This script, as namespace root, then hides the host:
#   tmpfs over /tmp, /mnt (resolv.conf re-bound), /run/user and $HOME;
#   binds back only the SDK venv + its Python, node, the workers and helper directories (read-only), and
#   STAGE/codex-home (as $HOME/.codex, writable), STAGE/ws, STAGE/out.
#   The native sign-in file is bind-mounted read-only at $HOME/.codex/auth.json (never copied; the
#   staging directory only holds an empty placeholder).
# PROFILE ctxmode additionally binds $HOME/.bun read-only (the Context Mode plugin re-execs under Bun).
# It then drops to uid/gid 1000 in a nested user namespace and execs CMD under env -i with a minimal env.
set -euo pipefail
STAGE=$1; PROFILE=$2; [ "$3" = "--" ] || { echo "usage: iso_ns.sh STAGE PROFILE -- CMD..." >&2; exit 2; }; shift 3
H=$HOME
C=$H/.cache/gap-wave2-20260923/agent-sdks
HELPERS=$(cd "$(dirname "$0")" && pwd)
WORKERS=$(cd "$(dirname "$0")/../../../blueprints/us-equities/workers" && pwd)
PYHOME=$H/.local/share/codex-ecosystem/python/cpython-3.13.15-linux-x86_64-gnu
NODEHOME=$H/.local/share/codex-ecosystem/tools/node-v24.21.0
K=/tmp/keep
mount -t tmpfs -o mode=755 tmpfs /tmp
mkdir -p $K
keep() { if [ -d "$1" ]; then mkdir -p "$K/$2"; else touch "$K/$2"; fi; mount --rbind "$1" "$K/$2"; }
place() {  # place NAME DEST ro|rw
  if [ -d "$K/$1" ]; then mkdir -p "$2"; else mkdir -p "$(dirname "$2")"; [ -e "$2" ] || touch "$2"; fi
  mount --rbind "$K/$1" "$2"
  if [ "$3" = ro ]; then mount -o remount,bind,ro "$2"; fi
}
keep "$C/codex-sdk-01551" venv
keep "$PYHOME" py
keep "$NODEHOME" node
keep "$WORKERS" workers
keep "$HELPERS" helpers
keep "$STAGE/codex-home" codexhome
keep "$STAGE/ws" ws
keep "$STAGE/out" out
keep "$H/.codex/auth.json" auth
keep /mnt/wsl/resolv.conf resolv
[ "$PROFILE" = ctxmode ] && keep "$H/.bun" bun
mount -t tmpfs -o mode=755 tmpfs /mnt
place resolv /mnt/wsl/resolv.conf ro
mount -t tmpfs -o mode=755 tmpfs /run/user
mount -t tmpfs -o mode=755 tmpfs "$H"
place venv "$C/codex-sdk-01551" ro
place py "$PYHOME" ro
place py "$(dirname "$PYHOME")/cpython-3.13-linux-x86_64-gnu" ro  # the venv home is this symlink name
place node "$NODEHOME" ro
place workers "$WORKERS" ro
place helpers "$HELPERS" ro
place codexhome "$H/.codex" rw
place auth "$H/.codex/auth.json" ro
place ws "$STAGE/ws" rw
place out "$STAGE/out" rw
[ "$PROFILE" = ctxmode ] && place bun "$H/.bun" ro
# Hide the staging binds: detach /tmp/keep and cover /tmp with a fresh tmpfs.
for m in "$K"/*; do umount -R -l "$m"; done
mount -t tmpfs -o mode=1777 tmpfs /tmp
cd "$STAGE/ws"
exec unshare --user --map-user=1000 --map-group=1000 \
  env -i HOME="$H" USER=isolated PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 TMPDIR=/tmp "$@"
