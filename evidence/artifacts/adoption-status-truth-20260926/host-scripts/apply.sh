#!/usr/bin/env bash
# u5 host apply: G13 (move the primary checkout to a revision carrying the fixes) and G5a (enroll named worker
# worktrees in ai-memory capture through the native .worktreeinclude recipe). G9 itself is repository-only: the
# fixed scripts/adoption_status.py reaches this host through step A (and through ecosystem-live-clone-sync.timer
# for ~/code/native-agent-stack-live, which needs nothing from this script).
#
#   apply.sh [--dry-run | --apply] [--main DIR] [--target SHA] [--fetch] [--allow-live-sessions]
#            [--enroll-worktree DIR]... [--ai-memory-data-dir DIR] [--backup-dir DIR]
#
# --dry-run (default) prints every precondition and planned action and changes nothing in the checkout or a
# worktree (no checkout, no copy). With --fetch it first runs `git fetch origin main`, which updates only
# remote-tracking refs. It resolves --target (default origin/main) and prints the full SHA to pass to --apply.
# --apply acts only on a reviewed revision: --target must be that full 40-character SHA and --fetch is refused, so
# the checkout moves to exactly what the dry run showed. It is idempotent: a second run finds HEAD at the target
# and each marker present, and does nothing. Every precondition is checked, and the tools step B needs are found,
# before step A acts.
#
# Step A  Move the primary checkout (default ~/code/native-agent-stack) fast-forward to the target.
#         Preconditions: detached HEAD, clean status, HEAD an ancestor of the target, the target carrying the u5
#         changes (.worktreeinclude naming .ai-memory.toml; scripts/adoption_status.py with codex_hooks_json and
#         ai_memory_hook_events_trusted; checked even when HEAD is already there), and no process other than this
#         one with its working directory in the checkout (read from /proc/<pid>/cwd; listed by pid and command
#         name). Every Claude Code or Codex session there, a coordinator included, would see CLAUDE.md, AGENTS.md,
#         .claude/settings.json and every repository file change under it; close them or pass
#         --allow-live-sessions after accepting that. Backup: the old HEAD, plus a copy of every ignored file at a
#         path the target adds (git would overwrite it silently); an untracked, not ignored file at such a path
#         refuses the step. Action: `git checkout --detach <target>`.
# Step B  For each literal --enroll-worktree DIR (a linked worktree of the same repository, not the primary, not a
#         blind-lane checkout with BLIND-MANIFEST.json): Worktrunk's native `wt -C DIR step copy-ignored
#         --require-include`, which copies only what the primary's .worktreeinclude lists and git ignores, i.e. the
#         host's .ai-memory.toml; then `ai-memory --data-dir <the installed hook's> hook --check-capture` must
#         report capture_mode "allowlist", marker_present true and admits_capture true, or the copied marker is
#         removed again and the script stops. The data dir is the --data-dir that the ai-memory hook commands in
#         ${CODEX_HOME:-~/.codex}/hooks.json carry (--ai-memory-data-dir overrides it): without it the check reads
#         the default data dir, where a missing capture-mode file means denylist mode, which admits everything.
#         Before step A, that data dir must already be in allowlist mode with the primary checkout's marker
#         found. A worktree that already has a marker is skipped. Backup: DIR and the marker's sha256 in enrolled.tsv
#         (the file did not exist before), so rollback.sh removes only an unchanged copy.
#
# What enrolling means: new Claude Code and Codex sessions in an enrolled worktree write observations to the
# ai-memory project local/native-agent-stack, and at SessionStart ai-memory's hook also fetches the project's
# pending handoff and injects it into that session's context. That fetch consumes the handoff (ai-memory 2.4.1
# hook.rs: "the GET is destructive"), so a worker session can take a handoff meant for the user's next session and
# receives shared memory context. Enroll only a lane that should have both: never an independent-review lane or a
# blind lane. --enroll-worktree names each lane explicitly; nothing is enrolled by default.
#
# Affects: see step A for sessions in the primary checkout. nativestack-memory.service only has the checkout as
# WorkingDirectory; the timers read ~/code/native-agent-stack-live.
set -euo pipefail

mode=dry-run
main="${HOME}/code/native-agent-stack"
target=""
fetch=0
live_ok=0
backup=""
data_dir=""
enroll=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) mode=dry-run; shift ;;
    --apply) mode=apply; shift ;;
    --main) main="$2"; shift 2 ;;
    --target) target="$2"; shift 2 ;;
    --fetch) fetch=1; shift ;;
    --allow-live-sessions) live_ok=1; shift ;;
    --enroll-worktree) enroll+=("$2"); shift 2 ;;
    --ai-memory-data-dir) data_dir="$2"; shift 2 ;;
    --backup-dir) backup="$2"; shift 2 ;;
    -h|--help) sed -n '2,48p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
say() { printf '%s\n' "${*//$HOME/\~}"; }
die() { say "REFUSED: $*" >&2; exit 1; }
blocked=0
# A failed precondition stops --apply before anything changes; a dry run reports it and goes on planning.
block() { if [ "$mode" = apply ]; then die "$*"; fi; say "BLOCKED: $*"; blocked=1; }
g() { git --no-optional-locks -C "$main" "$@"; }
[ -d "$main/.git" ] || [ -f "$main/.git" ] || die "$main is not a git checkout"
main="$(cd "$main" && pwd -P)"
cd /  # this script's own working directory is never inside the checkout it moves
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="${backup:-${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/apply-backups/u5-$stamp}"
say "mode: $mode; primary checkout: $main; backup dir (apply only): $backup"
if [ "$mode" = apply ]; then
  [ "$fetch" = 0 ] || die "--fetch belongs to the dry run; --apply moves only to the --target SHA it printed"
  printf '%s' "$target" | grep -Eqx '[0-9a-f]{40}' \
    || die "--apply needs --target with the full 40-character SHA the dry run printed, not ${target:-a default}"
fi

# Processes (other than this script) whose working directory is the checkout or below it: pid and command name.
live_sessions() {
  local proc cwd
  [ -d /proc/self ] || { echo "? /proc is unavailable, so live sessions cannot be listed"; return; }
  for proc in /proc/[0-9]*; do
    [ "${proc#/proc/}" != "$$" ] || continue
    cwd="$(readlink "$proc/cwd" 2>/dev/null)" || continue
    case "$cwd/" in "$main"/*) printf '%s %s\n' "${proc#/proc/}" "$(cat "$proc/comm" 2>/dev/null || echo '?')" ;; esac
  done
}

# The --data-dir that the installed Codex ai-memory hook commands carry (the first one found), or nothing.
hook_data_dir() {
  python3 - "${CODEX_HOME:-$HOME/.codex}/hooks.json" <<'PY'
import json, shlex, sys
from pathlib import PurePosixPath
try:
    hooks = json.load(open(sys.argv[1], encoding="utf-8")).get("hooks", {})
except (OSError, ValueError, AttributeError):
    raise SystemExit(0)
for groups in hooks.values() if isinstance(hooks, dict) else []:
    for group in groups if isinstance(groups, list) else []:
        for handler in (group.get("hooks") or []) if isinstance(group, dict) else []:
            try:
                argv = shlex.split(handler.get("command") or "") if isinstance(handler, dict) else []
            except ValueError:
                continue
            if argv and PurePosixPath(argv[0]).name == "ai-memory" and "hook" in argv[1:]:
                before = argv[1:argv.index("hook")]
                for index, item in enumerate(before):
                    if item == "--data-dir" and index + 1 < len(before):
                        print(before[index + 1]); raise SystemExit(0)
                    if item.startswith("--data-dir="):
                        print(item.split("=", 1)[1]); raise SystemExit(0)
PY
}

# ai-memory's own capture verdict for a cwd, as JSON: capture_mode, marker_present, admits_capture.
check_capture() {
  jq -cn --arg cwd "$1" '{cwd: $cwd, session_id: "u5-apply"}' \
    | ai-memory --data-dir "$data_dir" hook --event pre-tool-use --agent codex \
        --server-url "${AI_MEMORY_HOOK_URL:-http://127.0.0.1:49474}" --check-capture
}

# ---------- Preconditions for both steps, before anything acts ----------
if [ "${#enroll[@]}" -gt 0 ]; then
  for tool in wt jq ai-memory python3 sha256sum cmp; do
    command -v "$tool" >/dev/null || block "step B needs $tool on PATH"
  done
  if [ -z "$data_dir" ] && command -v python3 >/dev/null; then data_dir="$(hook_data_dir)"; fi
  [ -n "$data_dir" ] || block "no --data-dir found in the Codex ai-memory hooks; pass --ai-memory-data-dir"
  if [ -n "$data_dir" ] && command -v ai-memory >/dev/null && command -v jq >/dev/null; then
    primary="$(check_capture "$main" | jq -c '{capture_mode, marker_present, admits_capture}' || true)"
    say "ai-memory data dir (from the installed Codex hooks unless given): $data_dir"
    say "primary checkout's capture verdict: ${primary:-none}"
    printf '%s' "$primary" | jq -e '.capture_mode == "allowlist" and .marker_present == true' >/dev/null 2>&1 \
      || block "that data dir is not in allowlist mode with the primary checkout's marker found, so no enrollment could be confirmed"
  fi
fi

# ---------- Step A ----------
say ""
say "== Step A: move the primary checkout to a revision carrying the u5 changes"
if [ "$fetch" = 1 ]; then g fetch --quiet origin main; say "fetched origin main (remote-tracking refs only)"; fi
target="${target:-origin/main}"
head="$(g rev-parse HEAD)"
tsha="$(g rev-parse --verify --quiet "$target^{commit}" || true)"
[ -n "$tsha" ] || die "target $target does not resolve in $main (fetch first, or pass --target)"
say "HEAD $head; target $target = $tsha; $(g rev-list --count "$head..$tsha") commits ahead"
g show "$tsha:.worktreeinclude" 2>/dev/null | grep -qx '\.ai-memory\.toml' \
  || block "the target has no .worktreeinclude naming .ai-memory.toml: the u5 change is not merged there yet"
for marker in codex_hooks_json ai_memory_hook_events_trusted; do
  g grep -q "$marker" "$tsha" -- scripts/adoption_status.py \
    || block "the target's scripts/adoption_status.py predates the u5 fix (no $marker)"
done
step_a=todo
if [ "$head" = "$tsha" ]; then
  say "already at the target: nothing to move"
  step_a="done"
else
  if g symbolic-ref -q HEAD >/dev/null; then
    block "HEAD is on a branch ($(g symbolic-ref --short HEAD)); this step moves only a detached checkout"
  fi
  [ -z "$(g status --porcelain)" ] || block "the checkout has local changes; keep them and resolve first (git status)"
  g merge-base --is-ancestor "$head" "$tsha" || block "the target is not a descendant of HEAD; refusing a non-fast-forward move"
  sessions="$(live_sessions)"
  if [ -n "$sessions" ]; then
    say "processes with their working directory in the checkout: $(printf '%s\n' "$sessions" | wc -l)"
    printf '%s\n' "$sessions" | while IFS= read -r line; do say "  $line"; done
    [ "$live_ok" = 1 ] || block "live processes work in the checkout; close them, or pass --allow-live-sessions after accepting that their files change"
  else
    say "processes with their working directory in the checkout: 0"
  fi
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
    step_a="done"
  elif [ "$blocked" = 0 ]; then
    say "would run: git -C $main checkout --detach $tsha"
  else
    say "step A is blocked; it would not run"
  fi
fi
[ "$mode" = apply ] || say "to apply exactly this revision: --apply --target $tsha"

# ---------- Step B ----------
say ""
say "== Step B: enroll ${#enroll[@]} named worker worktree(s) in ai-memory capture"
[ "${#enroll[@]}" -gt 0 ] || say "no --enroll-worktree given: nothing to do"
[ "${#enroll[@]}" = 0 ] || say "an enrolled worktree's new sessions are captured and consume the project's pending handoff at SessionStart"
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
  if [ "$step_a" != "done" ] || [ "$blocked" = 1 ]; then
    say "   would run after step A: wt -C $wt step copy-ignored --require-include, then the capture check"
    continue
  fi
  plan="$(wt -C "$wt" step copy-ignored --require-include --dry-run --format json)"
  entries="$(printf '%s' "$plan" | jq -c '[.entries[].path]')"
  [ "$entries" = '[".ai-memory.toml"]' ] || { say "   skip: Worktrunk plans $entries, not exactly the marker"; continue; }
  if [ "$mode" != apply ]; then say "   would run: wt -C $wt step copy-ignored --require-include (plans $entries), then the capture check"; continue; fi
  mkdir -p "$backup"; chmod 700 "$backup"
  printf '%s\t%s\n' "$wt" "$(sha256sum < "$main/.ai-memory.toml" | cut -d' ' -f1)" >> "$backup/enrolled.tsv"
  wt -C "$wt" step copy-ignored --require-include --format json | jq -c '{outcome, files, written}'
  cmp -s "$main/.ai-memory.toml" "$wt/.ai-memory.toml" || die "copied marker differs from the primary's"
  verdict="$(check_capture "$wt" | jq -c '{capture_mode, marker_present, admits_capture}' || true)"
  if ! printf '%s' "$verdict" | jq -e '.capture_mode == "allowlist" and .marker_present == true
                                       and .admits_capture == true' >/dev/null 2>&1; then
    rm -- "$wt/.ai-memory.toml"
    die "the capture check did not confirm $wt (${verdict:-no verdict}); the copied marker was removed"
  fi
  say "   enrolled: $verdict"
done
say ""
if [ "$blocked" = 1 ]; then say "dry run found blockers: --apply would refuse"; exit 3; fi
say "done ($mode). Verify with prove.sh${enroll:+ plus --worktree for each enrolled worktree}."
