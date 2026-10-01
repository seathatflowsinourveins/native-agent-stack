#!/usr/bin/env bash
# local_integration fixture for the u5 host scripts: runs one apply.sh/rollback.sh pair through the same scenarios
# in an owned test repository with a sandboxed HOME, so no host checkout, client home or ai-memory store is touched.
# It uses the host's real `wt` (Worktrunk) and `ai-memory` (hook --check-capture spools nothing and contacts no
# server) against fixture paths only.
#
#   host_scripts_fixture.sh SCRIPT_DIR WORK_DIR     # SCRIPT_DIR holds apply.sh and rollback.sh
#
# WORK_DIR must not exist yet: the fixture creates it and works only inside it, so it never deletes or reuses a
# directory it did not create. Git sees only that sandbox, as git's own t/test-lib.sh (v2.43.0) arranges: every
# inherited GIT_* variable is unset (a caller's GIT_DIR or GIT_CONFIG_GLOBAL would aim the fixture's commits or its
# `git config --global` at the caller's repository or configuration), with no system configuration or attributes,
# no repository discovery above WORK_DIR, and HOME inside WORK_DIR.
#
# Each scenario prints its commands' exit codes and the lines that decide it, then "EXPECT ... : ok|NOT MET" for
# what the fixed scripts must do. Exit 0 only when every expectation is met; 2 on a usage error.
set -uo pipefail
if [ "$#" -ne 2 ] || [ -z "$1" ] || [ -z "$2" ]; then
  echo "usage: host_scripts_fixture.sh SCRIPT_DIR WORK_DIR   (WORK_DIR must not exist yet)" >&2
  exit 2
fi
scripts="$(cd "$1" && pwd -P)" || { echo "no such SCRIPT_DIR: $1" >&2; exit 2; }
work="$2"
if [ -e "$work" ] || [ -L "$work" ]; then
  echo "refusing: WORK_DIR $work exists; pass a path the fixture can create, e.g. \"\$(mktemp -d)/fx\"" >&2
  exit 2
fi
mkdir -- "$work" || { echo "cannot create WORK_DIR $work" >&2; exit 2; }  # no -p: it fails if the path appeared
work="$(cd "$work" && pwd -P)"
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep '^GIT_')
export GIT_CONFIG_NOSYSTEM=1 GIT_ATTR_NOSYSTEM=1 GIT_CEILING_DIRECTORIES="$work/.."
unmet=0
expect() {  # expect "description" condition...
  local what="$1"; shift
  if "$@"; then echo "EXPECT $what: ok"; else echo "EXPECT $what: NOT MET"; unmet=$((unmet + 1)); fi
}
aimem="$(dirname "$(command -v ai-memory)")"
export HOME="$work/fakehome" XDG_STATE_HOME="$work/fakehome/.local/state"
unset AI_MEMORY_DATA_DIR XDG_DATA_HOME XDG_CONFIG_HOME XDG_CACHE_HOME CODEX_HOME
mkdir -p "$HOME/.codex" "$work/aimem-allow" "$work/aimem-deny"
echo allowlist > "$work/aimem-allow/capture-mode"   # the installed hook's data dir: allowlist mode
hook_cmd() { printf '%s/ai-memory --data-dir %s hook --event %s --agent codex --server-url http://127.0.0.1:9' "$aimem" "$1" "$2"; }
write_hooks() {  # the Codex hooks.json of the sandboxed home, its ai-memory hook on data dir $1
  jq -n --arg c "$(hook_cmd "$1" session-start)" '{hooks: {SessionStart: [{matcher: "", hooks: [{type: "command", command: $c}]}]}}' \
    > "$HOME/.codex/hooks.json"
}
write_hooks "$work/aimem-allow"

git config --global user.email fixture@example.invalid >/dev/null 2>&1 || true
git config --global user.name fixture >/dev/null 2>&1 || true
git config --global init.defaultBranch main >/dev/null 2>&1 || true
repo() {  # a bare origin with base A, target B (the u5 change) and C (no u5 content); primary detached at A
  local root="$1"
  git init -q --bare "$root/origin.git"
  git clone -q "$root/origin.git" "$root/primary" 2>/dev/null
  cd "$root/primary" || exit 1
  echo '/.ai-memory.toml' >> .git/info/exclude   # as the host's primary checkout keeps its opt-in out of status
  mkdir scripts; echo "old checker" > scripts/adoption_status.py; echo base > README.md
  printf 'cache.txt\n' > .gitignore
  git add -A; git commit -qm A
  git push -q origin HEAD:main
  a="$(git rev-parse HEAD)"
  printf '# worktree copies\n.ai-memory.toml\n' > .worktreeinclude
  printf 'cache.txt\n/.ai-memory.toml\n' > .gitignore
  printf 'def codex_hooks_json(): ...\nai_memory_hook_events_trusted = 0\n' > scripts/adoption_status.py
  git add -A; git commit -qm B
  b="$(git rev-parse HEAD)"
  git checkout -q --detach "$a"
  echo "noted" > NOTES.md; git add NOTES.md; git commit -qm C
  c="$(git rev-parse HEAD)"
  git push -q origin "$b:main"
  git checkout -q --detach "$a"
  git fetch -q origin
  cp "$work/marker.toml" .ai-memory.toml   # ignored at B; untracked at A (the host's opt-in)
  git worktree add -q --detach "$root/worker" "$b"
  cd /
}
printf 'workspace = "local"\nproject = "fixture"\n' > "$work/marker.toml"
run() {  # run LABEL CMD...: print the command's output and exit code
  local label="$1"; shift
  echo "--- $label: $(printf '%s ' "$@" | sed -e "s|$work|\$WORK|g" -e "s|$scripts/||g")"
  "$@" > "$work/out.txt" 2>&1; rc=$?
  sed -e "s|$work|\$WORK|g" -e "s|$scripts/||g" "$work/out.txt"
  echo "--- exit $rc"
}
head_of() { git -C "$1" rev-parse HEAD; }
# The reviewed scripts predate --allow-live-sessions; pass it only to scripts that accept it.
live=(); grep -q -- "--allow-live-sessions" "$scripts/apply.sh" && live=(--allow-live-sessions)

echo "=== S1 --apply without a reviewed --target (origin/main can move after the dry run)"
repo "$work/s1"
run "dry run" "$scripts/apply.sh" --main "$work/s1/primary"
run "apply, no --target" "$scripts/apply.sh" --apply --main "$work/s1/primary" "${live[@]}"
expect "S1 refused: the checkout stays at A" test "$(head_of "$work/s1/primary")" = "$a"

echo "=== S2 --apply --fetch (resolves origin/main again at apply time)"
repo "$work/s2"
run "apply with --fetch" "$scripts/apply.sh" --apply --fetch --main "$work/s2/primary" --target "$b" "${live[@]}"
expect "S2 refused: the checkout stays at A" test "$(head_of "$work/s2/primary")" = "$a"

echo "=== S3 a live process works in the checkout"
repo "$work/s3"
(cd "$work/s3/primary/scripts" && exec sleep 300) & sleeper=$!
sleep 0.3
run "dry run" "$scripts/apply.sh" --main "$work/s3/primary" --target "$b"
expect "S3 the dry run lists the process" grep -q "processes with their working directory in the checkout: 1" "$work/out.txt"
run "apply" "$scripts/apply.sh" --apply --main "$work/s3/primary" --target "$b"
expect "S3 refused while it lives: the checkout stays at A" test "$(head_of "$work/s3/primary")" = "$a"
run "apply, accepted" "$scripts/apply.sh" --apply --main "$work/s3/primary" --target "$b" "${live[@]}" \
  --backup-dir "$work/s3/backup"
expect "S3 moves once accepted" test "$(head_of "$work/s3/primary")" = "$b"
run "rollback" "$scripts/rollback.sh" --apply --backup-dir "$work/s3/backup"
expect "S3 rollback refused while it lives: still at B" test "$(head_of "$work/s3/primary")" = "$b"
kill "$sleeper" 2>/dev/null; wait "$sleeper" 2>/dev/null
run "rollback, nothing live" "$scripts/rollback.sh" --apply --backup-dir "$work/s3/backup"
expect "S3 rollback returns to A" test "$(head_of "$work/s3/primary")" = "$a"

echo "=== S4 HEAD already at a target that lacks the u5 change"
repo "$work/s4"
git -C "$work/s4/primary" checkout -q --detach "$c"
run "dry run at C" "$scripts/apply.sh" --main "$work/s4/primary" --target "$c"
expect "S4 blocked, not reported done" grep -q "BLOCKED: the target has no .worktreeinclude" "$work/out.txt"

echo "=== S5 step B's tools missing: nothing may move first"
repo "$work/s5"
mkdir -p "$work/nowt"
for tool in git jq python3 sha256sum cmp readlink cat sed grep date dirname cut wc ls find mkdir chmod cp rm env bash; do
  ln -sf "$(command -v "$tool")" "$work/nowt/$tool"
done
ln -sf "$(command -v ai-memory)" "$work/nowt/ai-memory"
run "apply, no wt on PATH" env PATH="$work/nowt" "$scripts/apply.sh" --apply --main "$work/s5/primary" --target "$b" \
  "${live[@]}" --enroll-worktree "$work/s5/worker" --backup-dir "$work/s5/backup"
expect "S5 refused before step A: the checkout stays at A" test "$(head_of "$work/s5/primary")" = "$a"

echo "=== S6 enrollment when the installed hook's data dir is not in allowlist mode"
repo "$work/s6"
write_hooks "$work/aimem-deny"   # no capture-mode file: denylist, which admits every repository
run "apply and enroll" "$scripts/apply.sh" --apply --main "$work/s6/primary" --target "$b" "${live[@]}" \
  --enroll-worktree "$work/s6/worker" --backup-dir "$work/s6/backup"
expect "S6 refused before step A: the checkout stays at A" test "$(head_of "$work/s6/primary")" = "$a"
expect "S6 refused: not reported enrolled" bash -c "! grep -q 'enrolled:' '$work/out.txt'"
expect "S6 the copied marker is removed again" test ! -e "$work/s6/worker/.ai-memory.toml"
write_hooks "$work/aimem-allow"

echo "=== S7 enrollment checked against the hook's own data dir (allowlist)"
repo "$work/s7"
run "apply and enroll" "$scripts/apply.sh" --apply --main "$work/s7/primary" --target "$b" "${live[@]}" \
  --enroll-worktree "$work/s7/worker" --backup-dir "$work/s7/backup"
expect "S7 enrolled through its marker under allowlist" \
  grep -q '"capture_mode":"allowlist","marker_present":true,"admits_capture":true' "$work/out.txt"
expect "S7 the marker is the primary's" cmp -s "$work/s7/primary/.ai-memory.toml" "$work/s7/worker/.ai-memory.toml"
run "rerun (idempotent)" "$scripts/apply.sh" --apply --main "$work/s7/primary" --target "$b" \
  --enroll-worktree "$work/s7/worker" --backup-dir "$work/s7/backup2"
expect "S7 rerun changes nothing" grep -q "already has a marker: nothing to do" "$work/out.txt"
run "rollback" "$scripts/rollback.sh" --apply --backup-dir "$work/s7/backup"
expect "S7 rollback removes the marker and returns to A" \
  bash -c "test ! -e '$work/s7/worker/.ai-memory.toml' && test \"\$(git -C '$work/s7/primary' rev-parse HEAD)\" = '$a'"

echo "=== summary: $unmet expectation(s) not met"
[ "$unmet" = 0 ]
