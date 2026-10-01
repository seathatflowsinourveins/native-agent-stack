#!/usr/bin/env bash
# Undo apply.sh from its backup directory. Dry-run by default; acts only with --apply.
#
#   rollback.sh --backup-dir DIR [--dry-run | --apply] [--allow-live-sessions]
#   rollback.sh --latest [--dry-run | --apply] [--allow-live-sessions]  # newest ${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/apply-backups/u5-*
#
# Step B first: for each worktree in enrolled.tsv, remove .ai-memory.toml only while it is still byte-identical to
# the marker apply.sh copied (same sha256); a changed or missing file is left alone and reported.
# Step A: only when main-checkout.json exists, the primary checkout's HEAD is still the target apply.sh moved it to
# and its status is clean: `git checkout --detach <old HEAD>`, then restore each ignored file apply.sh saved under
# overwritten/. Anything else (moved again since, local changes) is refused, never forced. Like apply.sh, it refuses
# to move the checkout while another process has its working directory there, unless --allow-live-sessions.
set -euo pipefail
mode=dry-run
backup=""
live_ok=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) mode=dry-run; shift ;;
    --apply) mode=apply; shift ;;
    --backup-dir) backup="$2"; shift 2 ;;
    --latest) backup="$( (ls -1d "${XDG_STATE_HOME:-$HOME/.local/state}"/native-agent-stack/apply-backups/u5-* 2>/dev/null || true) | tail -n 1)"; shift ;;
    --allow-live-sessions) live_ok=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
say() { printf '%s\n' "${*//$HOME/\~}"; }
die() { say "REFUSED: $*" >&2; exit 1; }
[ -n "$backup" ] && [ -d "$backup" ] || die "no backup directory (pass --backup-dir DIR or --latest)"
backup="$(cd "$backup" && pwd -P)"
cd /  # this script's own working directory is never inside the checkout it moves
say "mode: $mode; backup: $backup"

say ""
say "== Step B: remove enrolled markers that are unchanged"
if [ -f "$backup/enrolled.tsv" ]; then
  while IFS=$'\t' read -r wt digest; do
    [ -n "$wt" ] || continue
    marker="$wt/.ai-memory.toml"
    if [ ! -f "$marker" ]; then say "-- $wt: no marker (already removed)"; continue; fi
    now="$(sha256sum < "$marker" | cut -d' ' -f1)"
    if [ "$now" != "$digest" ]; then say "-- $wt: marker changed since apply; left in place"; continue; fi
    if [ "$mode" = apply ]; then rm -- "$marker"; say "-- $wt: removed .ai-memory.toml"
    else say "-- $wt: would remove .ai-memory.toml"; fi
  done < "$backup/enrolled.tsv"
else
  say "nothing enrolled by apply.sh"
fi

say ""
say "== Step A: return the primary checkout to its old HEAD"
if [ ! -f "$backup/main-checkout.json" ]; then
  say "apply.sh did not move the checkout: nothing to do"
  exit 0
fi
main="$(jq -r .main "$backup/main-checkout.json")"
old="$(jq -r .old_head "$backup/main-checkout.json")"
target="$(jq -r .target "$backup/main-checkout.json")"
g() { git --no-optional-locks -C "$main" "$@"; }
head="$(g rev-parse HEAD)"
if [ "$head" = "$old" ]; then say "already at the old HEAD $old: nothing to do"; exit 0; fi
[ "$head" = "$target" ] || die "HEAD is $head, not the $target apply.sh moved to; the checkout moved again since"
[ -z "$(g status --porcelain)" ] || die "the checkout has local changes; keep them and resolve first"
live=0
if [ -d /proc/self ]; then
  for proc in /proc/[0-9]*; do
    [ "${proc#/proc/}" != "$$" ] || continue
    cwd="$(readlink "$proc/cwd" 2>/dev/null)" || continue
    case "$cwd/" in "$main"/*) live=$((live + 1)); say "  live: ${proc#/proc/} $(cat "$proc/comm" 2>/dev/null || echo '?')" ;; esac
  done
else
  live=1; say "  /proc is unavailable, so live sessions cannot be listed"
fi
say "processes with their working directory in the checkout: $live"
[ "$live" = 0 ] || [ "$live_ok" = 1 ] || [ "$mode" != apply ] \
  || die "live processes work in the checkout; close them, or pass --allow-live-sessions after accepting that their files change"
if [ "$mode" = apply ]; then
  g -c advice.detachedHead=false checkout --quiet --detach "$old"
  if [ -d "$backup/overwritten" ]; then
    (cd "$backup/overwritten" && find . -type f -o -type l) | while IFS= read -r path; do
      mkdir -p "$main/$(dirname "$path")"
      cp -a "$backup/overwritten/$path" "$main/$path"
      say "restored $path"
    done
  fi
  say "moved back: $target -> $old"
else
  say "would run: git -C $main checkout --detach $old"
  if [ -d "$backup/overwritten" ]; then
    say "would restore $(find "$backup/overwritten" -type f | wc -l) saved ignored file(s)"
  fi
fi
