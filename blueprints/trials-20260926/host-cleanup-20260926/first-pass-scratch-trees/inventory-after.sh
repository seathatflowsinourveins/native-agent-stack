#!/bin/sh
# Inventory of the 2026-09-26 P1 trial batch's host state that still exists after the polish
# pass deleted the first pass's scratch trees. Read-only: lists names, types, sizes and
# timestamps (credential-bearing files are never opened), and checks for trial processes and ports.
#
# Usage: SCRATCH=<session scratch dir> sh inventory-after.sh <out-file>
set -u
out=${1:?out file}
SCRATCH=${SCRATCH:?set SCRATCH to the session scratch directory}
RUNDIR="/run/user/$(id -u)"
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
entry() {  # entry <path>: type, apparent bytes, birth and modification time (local, UTC-4)
  if [ -e "$1" ] || [ -L "$1" ]; then
    printf '%s\t%s\t%s\t%s\t%s\n' "$(stat -c %F "$1")" "$(du -sb "$1" | cut -f1)" \
      "birth $(stat -c %w "$1" | cut -c1-19)" "mtime $(stat -c %y "$1" | cut -c1-19)" "$1"
  else
    printf 'absent\t\t\t\t%s\n' "$1"
  fi
}
{
  echo "# Host-state inventory after the polish pass ($(stamp)); times are host local (UTC-4)"
  echo "## First-pass scratch trees deleted by the polish pass (expected absent)"
  for name in trial-colpali trial-mirix trial-byterover exec; do entry "$SCRATCH/$name"; done
  echo "## Trial-owned state outside the scratch directory (not deleted: outside this pass's scope)"
  entry "$HOME/.cache/huggingface/hub"
  for path in "$HOME/.cache/huggingface/hub"/* "$HOME/.cache/huggingface/hub"/.locks "$HOME/.cache/huggingface/hub"/.locks/*; do entry "$path"; done
  entry "$HOME/.cache/huggingface/datasets"
  for path in "$HOME/.cache/huggingface/datasets"/*; do entry "$path"; done
  entry "$HOME/.cache/mteb"
  entry "$HOME/.mirix"
  for path in "$HOME/.mirix"/*; do printf '%s\t%s\t%s\n' "$(stat -c %F "$path")" "$(stat -c %s "$path")" "$path"; done
  entry "$RUNDIR/python_PostgresServer"
  for path in "$RUNDIR/python_PostgresServer"/.lockfile "$RUNDIR/python_PostgresServer"/*; do entry "$path"; done
  echo "## Scratch trees that remain (not first-pass trial trees)"
  for name in trials-2 wt-trials trials-pol wt-trials2; do entry "$SCRATCH/$name"; done
  printf 'git worktree branch of <scratch>/wt-trials: %s\n' "$(git --no-optional-locks -C "$SCRATCH/wt-trials" branch --show-current 2>/dev/null)"
  printf 'uncommitted entries in <scratch>/wt-trials: %s\n' "$(git --no-optional-locks -C "$SCRATCH/wt-trials" status --porcelain 2>/dev/null | wc -l)"
  echo "## Other session scratch directories under the same root (names withheld)"
  root=$(dirname "$(dirname "$SCRATCH")")
  for dir in "$root"/*/; do
    [ "${dir%/}" = "$(dirname "$SCRATCH")" ] && continue
    printf 'session scratch dir, mtime %s\n' "$(stat -c %y "$dir" | cut -c1-10)"
  done | sort | uniq -c
  echo "## Trial processes and ports"
  procs=$(ps -eo pid,args | grep -E 'start_server.py|brv-server|agent-process|brv update|pgserver|pginstall/bin/postgres' | grep -v grep)
  if [ -n "$procs" ]; then echo "$procs"; else echo "no MIRIX, ByteRover or pgserver process"; fi
  ports=$(ss -ltn 2>/dev/null | grep -E ':(18531|18000|18533|7700)\b')
  if [ -n "$ports" ]; then echo "$ports"; else echo "ports 18531, 18000, 18533 and 7700 closed"; fi
  command -v brv > /dev/null 2>&1 && echo "brv on PATH" || echo "brv not on PATH"
} > "$out" 2>&1
echo "wrote $out"
