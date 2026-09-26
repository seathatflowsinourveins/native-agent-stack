#!/bin/sh
# Delete the first trial pass's own working trees inside this session's scratch directory
# (polish pass of the 2026-09-26 P1 trial batch). Nothing outside the scratch directory is
# touched.
#
# Usage: SCRATCH=<session scratch dir> sh delete-first-pass-trees.sh plan|apply <log-dir>
#
# Acts only on four literal directories directly under $SCRATCH: trial-colpali, trial-mirix,
# trial-byterover and exec (the first pass's MIRIX, ColPali and ByteRover trees and its receipt
# recorder's working directory). Before anything is deleted each must be a real directory (not a
# symlink) whose resolved path is exactly $SCRATCH/<name>, and no process may have its working
# directory or an open file inside it. `plan` asserts and lists; `apply` also deletes and checks
# that each one is gone. The port's own tree (trials-2) and the first pass's git worktree
# (wt-trials) are deliberately not in the set.
set -u
mode=${1:?plan|apply}
logdir=${2:?log dir}
SCRATCH=${SCRATCH:?set SCRATCH to the session scratch directory}
TARGETS="trial-colpali trial-mirix trial-byterover exec"
mkdir -p "$logdir"
log="$logdir/first-pass-trees-$mode.log"
: > "$log"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | sed "s#$SCRATCH#<scratch>#g" | tee -a "$log"; }
fail() { say "ABORT: $*"; exit 1; }

say "mode=$mode"
say "== assertions"
case "$SCRATCH" in /tmp/claude-*/*/scratchpad) ;; *) fail "SCRATCH is not a session scratchpad path" ;; esac
[ -d "$SCRATCH" ] && [ ! -L "$SCRATCH" ] || fail "SCRATCH is not a real directory"
for name in $TARGETS; do
  target="$SCRATCH/$name"
  [ -d "$target" ] || fail "$target is not a directory"
  [ -L "$target" ] && fail "$target is a symlink"
  [ "$(realpath "$target")" = "$target" ] || fail "$target does not resolve to itself"
  users=""
  for proc in /proc/[0-9]*; do
    cwd=$(readlink "$proc/cwd" 2>/dev/null) || continue
    case "$cwd" in "$target"|"$target"/*) users="$users ${proc#/proc/}(cwd)" ;; esac
    for fd in "$proc"/fd/*; do
      open=$(readlink "$fd" 2>/dev/null) || continue
      case "$open" in "$target"/*) users="$users ${proc#/proc/}(fd)"; break ;; esac
    done
  done
  [ -z "$users" ] || fail "$target is in use by:$users"
  say "ok $target: real directory, not in use, $(du -sb "$target" | cut -f1) apparent bytes"
done
say "all literal targets asserted"
if [ "$mode" != apply ]; then say "plan only; nothing changed"; exit 0; fi

say "== delete"
for name in $TARGETS; do
  target="$SCRATCH/$name"
  rm -rf -- "$target"
  if [ -e "$target" ] || [ -L "$target" ]; then say "WARNING: $target still present"; else say "removed $target"; fi
done
say "== after"
for name in $TARGETS; do
  if [ -e "$SCRATCH/$name" ]; then say "present $SCRATCH/$name"; else say "absent $SCRATCH/$name"; fi
done
say "done"
