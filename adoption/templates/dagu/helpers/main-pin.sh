#!/bin/bash
# Port of NativeStack native-agent-stack-main-pin.service, read 2026-10-06T04:26:27Z.
# Unit SHA256 719bb289c70b7c3a16ac43aeab278257949390e55ca2569fa1626222bce54c43.
# Git 2.53.0: git/git@67ad42147a7acc2af6074753ebd03d904476118f.
set -euo pipefail
umask 0077

repository=${1:?usage: main-pin.sh REPOSITORY}
cd "$repository"
git -c gc.auto=0 -c maintenance.auto=false -c fetch.prune=false fetch -q origin main
if git diff --quiet && git diff --cached --quiet; then
  git checkout -q --detach origin/main
  git rev-parse --short=9 HEAD
else
  echo "tracked changes present; HEAD left at $(git rev-parse --short=9 HEAD)"
fi
