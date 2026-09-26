#!/usr/bin/env bash
# u5 host apply: G13 (move the primary checkout to a revision carrying the fixes) and G5a (enroll named worker
# worktrees in ai-memory capture through the native .worktreeinclude recipe). G9 itself is repository-only: the
# fixed scripts/adoption_status.py reaches this host through step A (and through ecosystem-live-clone-sync.timer
# for ~/code/native-agent-stack-live, which needs nothing from this script).
#
#   apply.sh [--dry-run | --apply] [--main DIR] [--target REV] [--fetch] [--enroll-worktree DIR]... [--backup-dir DIR]
#
# --dry-run (default) prints every precondition and planned action and changes nothing (no fetch, no checkout, no
# copy). --apply acts, idempotently: a second run finds HEAD at the target and each marker present, and does nothing.
#
# Step A  Move the primary checkout (default ~/code/native-agent-stack) fast-forward to --target (default
#         origin/main; --fetch runs `git fetch origin main` first, with --apply only). Preconditions: detached HEAD,
#         clean status, HEAD an ancestor of the target, and the target carrying the u5 changes (.worktreeinclude
#         naming .ai-memory.toml; scripts/adoption_status.py with ai_memory_hook_events_trusted). Backup: the old
#         HEAD, plus a copy of every ignored file at a path the target adds (git would overwrite it silently); an
#         untracked, not ignored file at such a path refuses the step. Action: `git checkout --detach <target>`.
# Step B  For each literal --enroll-worktree DIR (a linked worktree of the same repository, not the primary, not a
#         blind-lane checkout with BLIND-MANIFEST.json): Worktrunk's native `wt -C DIR step copy-ignored
#         --require-include`, which copies only what the primary's .worktreeinclude lists and git ignores, i.e. the
#         host's .ai-memory.toml; then `ai-memory hook --check-capture` must report admits_capture true. A worktree
#         that already has a marker is skipped. Backup: DIR and the marker's sha256 in enrolled.tsv (the file did
#         not exist before), so rollback.sh removes only an unchanged copy.
#
# Affects: every Claude Code or Codex session whose cwd is the primary checkout (CLAUDE.md, AGENTS.md, .claude/
# settings.json and all repository files change under it; start new sessions afterwards, and run step A in a
# quiet window). nativestack-memory.service only has the checkout as WorkingDirectory; the timers read
# ~/code/native-agent-stack-live. Step B enrolls the named worktrees in capture: new Claude/Codex sessions there
# start writing observations to the ai-memory project local/native-agent-stack.
set -euo pipefail

mode=dry-run
main="${HOME}/code/native-agent-stack"
target=""
fetch=0
backup=""
enroll=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) mode=dry-run; shift ;;
    --apply) mode=apply; shift ;;
    --main) main="$2"; shift 2 ;;
    --target) target="$2"; shift 2 ;;
    --fetch) fetch=1; shift ;;
    --enroll-worktree) enroll+=("$2"); shift 2 ;;
    --backup-dir) backup="$2"; shift 2 ;;
    -h|--help) sed -n '2,31p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
say() { printf '%s\n' "${*//$HOME/\~}"; }
die() { say "REFUSED: $*" >&2; exit 1; }
blocked=0
# A failed precondition stops --apply; a dry run reports it and goes on planning.
block() { if [ "$mode" = apply ]; then die "$*"; fi; say "BLOCKED: $*"; blocked=1; }
g() { git --no-optional-locks -C "$main" "$@"; }
[ -d "$main/.git" ] || [ -f "$main/.git" ] || die "$main is not a git checkout"
main="$(cd "$main" && pwd -P)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="${backup:-${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/apply-backups/u5-$stamp}"
say "mode: $mode; primary checkout: $main; backup dir (apply only): $backup"

# ---------- Step A ----------
say ""
say "== Step A: move the primary checkout to a revision carrying the u5 changes"
if [ "$fetch" = 1 ]; then
  if [ "$mode" = apply ]; then g fetch --quiet origin main; else say "would run: git -C $main fetch origin main"; fi
fi
target="${target:-origin/main}"
head="$(g rev-parse HEAD)"
tsha="$(g rev-parse --verify --quiet "$target^{commit}" || true)"
[ -n "$tsha" ] || die "target $target does not resolve in $main (fetch first, or pass --target)"
say "HEAD $head; target $target = $tsha; $(g rev-list --count "$head..$tsha") commits ahead"
step_a=todo
if [ "$head" = "$tsha" ]; then
  say "already at the target: nothing to do"
  step_a=done
else
  if g symbolic-ref -q HEAD >/dev/null; then
    block "HEAD is on a branch ($(g symbolic-ref --short HEAD)); this step moves only a detached checkout"
  fi
  [ -z "$(g status --porcelain)" ] || block "the checkout has local changes; keep them and resolve first (git status)"
  g merge-base --is-ancestor "$head" "$tsha" || block "the target is not a descendant of HEAD; refusing a non-fast-forward move"
  g show "$tsha:.worktreeinclude" 2>/dev/null | grep -qx '\.ai-memory\.toml' \
    || block "the target has no .worktreeinclude naming .ai-memory.toml: the u5 change is not merged there yet"
  g grep -q ai_memory_hook_events_trusted "$tsha" -- scripts/adoption_status.py \
    || block "the target's scripts/adoption_status.py predates the u5 fix"
  overwritten=()
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    if [ -e "$main/$path" ] || [ -L "$main/$path" ]; then
      if g check-ignore -q -- "$path"; then overwritten+=("$path")
      else block "untracked file $path would be replaced by the target; move it aside first"; fi
    fi
  done < <(g diff --name-only --no-renames --diff-filter=A "$head" "$tsha")
  say "ignored files the target would overwrite (backed up first): ${#overwritten[@]}"
  for path in "${overwritten[@]}"; do say "  $path"; done
  if [ "$mode" = apply ]; then
    mkdir -p "$backup/overwritten"
    chmod 700 "$backup"
    printf '{"main": "%s", "old_head": "%s", "target": "%s", "moved_at_utc": "%s"}\n' \
      "$main" "$head" "$tsha" "$stamp" > "$backup/main-checkout.json"
    for path in "${overwritten[@]}"; do
      mkdir -p "$backup/overwritten/$(dirname "$path")"
      cp -a "$main/$path" "$backup/overwritten/$path"
    done
    g -c advice.detachedHead=false checkout --quiet --detach "$tsha"
    [ "$(g rev-parse HEAD)" = "$tsha" ] || die "checkout did not reach $tsha"
    [ -z "$(g status --porcelain)" ] || say "WARNING: status not clean after the move"
    say "moved: $head -> $tsha (old HEAD saved in $backup/main-checkout.json)"
    step_a=done
  elif [ "$blocked" = 0 ]; then
    say "would run: git -C $main checkout --detach $tsha"
  else
    say "step A is blocked; it would not run"
  fi
fi

# ---------- Step B ----------
say ""
say "== Step B: enroll ${#enroll[@]} named worker worktree(s) in ai-memory capture"
[ "${#enroll[@]}" -gt 0 ] || say "no --enroll-worktree given: nothing to do"
common="$(cd "$main" && cd "$(git rev-parse --git-common-dir)" && pwd -P)"
for wt in "${enroll[@]}"; do
  say "-- $wt"
  [ -d "$wt" ] || { say "   skip: not a directory"; continue; }
  wt="$(cd "$wt" && pwd -P)"
  [ "$wt" != "$main" ] || { say "   skip: that is the primary checkout"; continue; }
  wcommon="$(cd "$wt" && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P || true)"
  [ "$wcommon" = "$common" ] || { say "   skip: not a worktree of $main"; continue; }
  [ ! -e "$wt/BLIND-MANIFEST.json" ] || { say "   skip: blind-lane checkout, never enrolled"; continue; }
  [ -f "$main/.ai-memory.toml" ] || { say "   skip: the primary checkout is not enrolled (no .ai-memory.toml)"; continue; }
  if [ -e "$wt/.ai-memory.toml" ]; then say "   already has a marker: nothing to do"; continue; fi
  if [ "$step_a" != done ]; then
    say "   would run after step A: wt -C $wt step copy-ignored --require-include"
    continue
  fi
  plan="$(wt -C "$wt" step copy-ignored --require-include --dry-run --format json)"
  entries="$(printf '%s' "$plan" | jq -c '[.entries[].path]')"
  [ "$entries" = '[".ai-memory.toml"]' ] || { say "   skip: Worktrunk plans $entries, not exactly the marker"; continue; }
  if [ "$mode" != apply ]; then say "   would run: wt -C $wt step copy-ignored --require-include (plans $entries)"; continue; fi
  mkdir -p "$backup"; chmod 700 "$backup"
  printf '%s\t%s\n' "$wt" "$(sha256sum < "$main/.ai-memory.toml" | cut -d' ' -f1)" >> "$backup/enrolled.tsv"
  wt -C "$wt" step copy-ignored --require-include --format json | jq -c '{outcome, files, written}'
  cmp -s "$main/.ai-memory.toml" "$wt/.ai-memory.toml" || die "copied marker differs from the primary's"
  verdict="$(printf '{"cwd":"%s","session_id":"u5-apply"}' "$wt" \
    | ai-memory hook --event pre-tool-use --agent codex --server-url "${AI_MEMORY_HOOK_URL:-http://127.0.0.1:49474}" --check-capture \
    | jq -c '{marker_present, admits_capture}')"
  say "   enrolled: $verdict"
done
say ""
if [ "$blocked" = 1 ]; then say "dry run found blockers: --apply would refuse"; exit 3; fi
say "done ($mode). Verify with prove.sh${enroll:+ plus --worktree for each enrolled worktree}."
