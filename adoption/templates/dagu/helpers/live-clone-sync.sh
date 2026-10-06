#!/bin/bash
# Port of NativeStack ecosystem-live-clone-sync.service, read 2026-10-06T04:26:27Z.
# Unit SHA256 9a92c52099510268044277035d468ff62460a00b05c04c9c5146a9a0adf7bc87.
# Git 2.53.0: git/git@67ad42147a7acc2af6074753ebd03d904476118f.
set -euo pipefail
umask 0077

repository=${1:?usage: live-clone-sync.sh REPOSITORY [QMD_EXECUTABLE]}
qmd_executable=${2:-qmd}
cd "$repository"
# Keep the status command's exit code; an unreadable tree is not a clean tree.
local_changes=$(git status --porcelain)
if test -n "$local_changes"; then
  echo "live clone has local changes; not syncing" >&2
  exit 1
fi
git fetch -q origin main
git checkout -q --detach origin/main
git log -1 --format="synced %h %cI"
"$qmd_executable" --index native-agent-stack-catalog update >/dev/null
echo qmd-index-updated
