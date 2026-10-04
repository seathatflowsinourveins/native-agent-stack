#!/bin/sh
# Read-only inventory of the host state that the 2026-09-26 P1 trial batch still leaves behind,
# taken for the batch README's host-state accounting (second polish pass). It lists names, types,
# apparent sizes (du -sb) and UTC birth and modification times. It opens one file only, the
# hf_xet log of the first pass's unpinned-device download, and only to count lines naming vidore.
# It never opens a credential-bearing file and changes nothing.
#
# Usage: SCRATCH=<session scratch dir> sh inventory-remaining.sh <out-file>
set -u
out=${1:?out file}
SCRATCH=${SCRATCH:?set SCRATCH to the session scratch directory}
RUNDIR="/run/user/$(id -u)"
HFC="$HOME/.cache/huggingface"
XETLOG="$HFC/xet/logs/xet_20260925T224355622-0400_3896841.log"
# The directory prefixes ByteRover 3.16.1's upstream unit tests create under os.tmpdir()
# (byterover-cli/source-review.json#suite-tmpdir-*), plus its fixed test paths and the tool-output
# directory (#suite-fixed-tmp-paths, #tool-output-temp-dir).
SUITE_PREFIXES="brv-consolidate-test- brv-synthesize-test- brv-undo-test- brv-prune-test- brv-path-test- brv-projdir-test- migrate-fm- folder-pack-executor-"

utc() { if [ "${1:-0}" -gt 0 ] 2>/dev/null; then date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; else echo unknown; fi; }
entry() {  # entry <path>: type, apparent bytes, UTC birth and modification time, path
  if [ -e "$1" ] || [ -L "$1" ]; then
    printf '%s\t%s\tborn %s\tmodified %s\t%s\n' "$(stat -c %F "$1")" "$(du -sb "$1" | cut -f1)" \
      "$(utc "$(stat -c %W "$1")")" "$(utc "$(stat -c %Y "$1")")" "$1"
  else
    printf 'absent\t\t\t\t%s\n' "$1"
  fi
}
suite_entries() {  # NUL-separated top-level /tmp entries of this user with the given name prefix
  # stderr is dropped: other sessions' temporary entries can vanish while find reads /tmp.
  find /tmp -mindepth 1 -maxdepth 1 -user "$(id -u)" -name "$1*" -print0 2>/dev/null
}

{
  echo "# Remaining host state of the 2026-09-26 P1 trial batch, $(date -u +%Y-%m-%dT%H:%M:%SZ) (times UTC)"
  echo "## Outside the session scratch directory"
  echo "### Hugging Face cache (first pass's unpinned-device ColPali runs and slice build)"
  entry "$HFC"
  entry "$HFC/hub"
  for path in "$HFC/hub"/* "$HFC/hub/.locks" "$HFC/hub/.locks"/*; do entry "$path"; done
  entry "$HFC/datasets"
  for path in "$HFC/datasets"/*; do entry "$path"; done
  entry "$XETLOG"
  if [ -f "$XETLOG" ]; then echo "lines of that hf_xet log naming vidore: $(grep -c vidore "$XETLOG")"; fi
  if command -v hf > /dev/null 2>&1; then
    echo "\$ hf cache ls"
    hf cache ls 2>&1
  fi
  echo "### mteb, MIRIX and pgserver"
  entry "$HOME/.cache/mteb"
  entry "$HOME/.mirix"
  for path in "$HOME/.mirix"/*; do entry "$path"; done
  entry "$RUNDIR/python_PostgresServer"
  for path in "$RUNDIR/python_PostgresServer/.lockfile" "$RUNDIR/python_PostgresServer"/*; do entry "$path"; done
  echo "### ByteRover upstream test-suite residue in /tmp (entries of this user)"
  printf 'prefix\tentries\tapparent bytes\tfirst born\tlast born\n'
  total=0
  for prefix in $SUITE_PREFIXES; do
    count=$(suite_entries "$prefix" | tr -cd '\0' | wc -c)
    total=$((total + count))
    if [ "$count" -eq 0 ]; then printf '%s*\t0\n' "$prefix"; continue; fi
    bytes=$(suite_entries "$prefix" | xargs -0 du -sbc | tail -1 | cut -f1)
    births=$(suite_entries "$prefix" | xargs -0 stat -c %W | sort -n)
    printf '%s*\t%s\t%s\t%s\t%s\n' "$prefix" "$count" "$bytes" "$(utc "$(echo "$births" | head -1)")" "$(utc "$(echo "$births" | tail -1)")"
  done
  echo "prefixed directories in total: $total"
  for path in /tmp/brv-test-blobs /tmp/brv-test-storage /tmp/byterover-tool-outputs; do entry "$path"; done
  if [ -d /tmp/byterover-tool-outputs ]; then
    echo "files in /tmp/byterover-tool-outputs: $(find /tmp/byterover-tool-outputs -type f | wc -l)"
  fi
  echo "births of the prefixed directories per minute (one cluster per upstream suite run):"
  for prefix in $SUITE_PREFIXES; do suite_entries "$prefix"; done | xargs -0 -r stat -c %W \
    | while read -r born; do date -u -d "@$born" +%Y-%m-%dT%H:%MZ; done | sort | uniq -c
  echo "## Inside the session scratch directory"
  echo "### First-pass trees deleted by the first polish pass (expected absent)"
  for name in trial-colpali trial-mirix trial-byterover exec; do entry "$SCRATCH/$name"; done
  echo "### Trees that remain"
  for name in trials-2 wt-trials trials-pol wt-trials2; do entry "$SCRATCH/$name"; done
  printf 'git worktree branch of <scratch>/wt-trials: %s\n' "$(git --no-optional-locks -C "$SCRATCH/wt-trials" branch --show-current 2>/dev/null)"
  printf 'uncommitted entries in <scratch>/wt-trials: %s\n' "$(git --no-optional-locks -C "$SCRATCH/wt-trials" status --porcelain 2>/dev/null | wc -l)"
  echo "### Other session scratch directories under the same root (names withheld)"
  root=$(dirname "$(dirname "$SCRATCH")")
  for dir in "$root"/*/; do
    [ "${dir%/}" = "$(dirname "$SCRATCH")" ] && continue
    printf 'session scratch dir, mtime %s\n' "$(stat -c %y "$dir" | cut -c1-10)"
  done | sort | uniq -c
  echo "## Trial processes and ports"
  # Each alternative has a bracketed character so that this grep's own command line never matches.
  procs=$(ps -eo pid,args | grep -E 'start_server[.]py|brv[-]server|agent[-]process|brv [u]pdate|pgserve[r]|pginstall/bin/postgre[s]|vidore[-]benchmark')
  if [ -n "$procs" ]; then echo "$procs"; else echo "no MIRIX, ByteRover, pgserver or vidore-benchmark process"; fi
  ports=$(ss -ltn 2>/dev/null | grep -E ':(18531|18000|18533|7700)\b')
  if [ -n "$ports" ]; then echo "$ports"; else echo "ports 18531, 18000, 18533 and 7700 closed"; fi
  if command -v brv > /dev/null 2>&1; then echo "brv on PATH"; else echo "brv not on PATH"; fi
} > "$out" 2>&1
echo "wrote $out"
