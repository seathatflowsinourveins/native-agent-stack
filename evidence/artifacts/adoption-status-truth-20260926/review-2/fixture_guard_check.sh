#!/usr/bin/env bash
# local_integration check of host_scripts_fixture.sh's own boundary: it may create and change only its WORK_DIR.
# Runs FIXTURE three times inside SANDBOX, with stub apply.sh and rollback.sh that exit 1 (so only the fixture's own
# actions can touch anything):
#   G1 WORK_DIR is an existing directory holding a file: the file must survive;
#   G2 the caller exports GIT_CONFIG_GLOBAL naming its configuration file: that file must be unchanged;
#   G3 the caller exports GIT_DIR naming its repository: HEAD, refs, configuration and index must be unchanged.
#
#   fixture_guard_check.sh FIXTURE SANDBOX        # SANDBOX must not exist yet; everything happens inside it
#
# Exit 0 only when all three hold.
set -uo pipefail
if [ "$#" -ne 2 ] || [ -z "$2" ] || [ -e "$2" ] || [ -L "$2" ]; then
  echo "usage: fixture_guard_check.sh FIXTURE SANDBOX   (SANDBOX must not exist yet)" >&2
  exit 2
fi
fixture="$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
mkdir -- "$2" || exit 2
box="$(cd "$2" && pwd -P)"
mkdir "$box/stubs"
printf '#!/bin/sh\nexit 1\n' > "$box/stubs/apply.sh"
cp "$box/stubs/apply.sh" "$box/stubs/rollback.sh"
chmod +x "$box/stubs/apply.sh" "$box/stubs/rollback.sh"
unmet=0
expect() {  # expect "description" condition...
  local what="$1"; shift
  if "$@"; then echo "EXPECT $what: ok"; else echo "EXPECT $what: NOT MET"; unmet=$((unmet + 1)); fi
}
fx() {  # fx LABEL WORK [NAME=VALUE...]: one bounded fixture run with the caller's extra environment
  local label="$1" work="$2"; shift 2
  ( for assignment in "$@"; do export "${assignment?}"; done  # each is NAME=VALUE
    exec timeout -k 10 600 "$fixture" "$box/stubs" "$work" ) > "$box/$label.log" 2>&1
  echo "fixture exit $?; first lines:"
  head -n 2 "$box/$label.log" | sed -e "s|$box|\$SANDBOX|g" -e 's/^/  /'
}
echo "fixture under test: $(basename "$(dirname "$fixture")")/$(basename "$fixture") sha256 $(sha256sum < "$fixture" | cut -c1-16)"

echo "=== G1 WORK_DIR already exists and holds a file"
mkdir -p "$box/g1/existing"
echo keep > "$box/g1/existing/keep.txt"
fx g1 "$box/g1/existing"
expect "G1 the existing directory's file survives" test -f "$box/g1/existing/keep.txt"

echo "=== G2 the caller's GIT_CONFIG_GLOBAL"
mkdir "$box/g2"
printf '[user]\n\temail = caller@example.invalid\n' > "$box/g2/caller.gitconfig"
before="$(sha256sum < "$box/g2/caller.gitconfig")"
fx g2 "$box/g2/work" "GIT_CONFIG_GLOBAL=$box/g2/caller.gitconfig"
echo "caller's user.email now: $(git config -f "$box/g2/caller.gitconfig" user.email)"
expect "G2 the caller's configuration file is unchanged" test "$(sha256sum < "$box/g2/caller.gitconfig")" = "$before"

echo "=== G3 the caller's GIT_DIR"
caller="$box/g3/caller"
git init -q "$caller"
git -C "$caller" -c user.email=caller@example.invalid -c user.name=caller commit -q --allow-empty -m caller
state() {  # HEAD, every ref, the local configuration and the index, as one digest
  { git -C "$caller" rev-parse HEAD; git -C "$caller" for-each-ref; cat "$caller/.git/config"
    cat "$caller/.git/index" 2>/dev/null; } | sha256sum
}
before="$(state)"
fx g3 "$box/g3/work" "GIT_DIR=$caller/.git"
echo "caller's commits now: $(git -C "$caller" rev-list --count --all), core.bare: $(git -C "$caller" config core.bare)"
expect "G3 the caller's repository is unchanged" test "$(state)" = "$before"

echo "=== summary: $unmet expectation(s) not met"
[ "$unmet" = 0 ]
