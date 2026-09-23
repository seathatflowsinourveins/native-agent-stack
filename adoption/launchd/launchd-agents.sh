#!/usr/bin/env bash
# Drafted, not run: launchctl bootstrap/print/bootout below act on a real
# macOS user's launchd session; no macOS host has run this script (see
# adoption/platforms/macos-arm64.md, "What a hosted run proves"). Keep this
# script bash 3.2 compatible: a stock Mac has /bin/bash 3.2, so this avoids
# reading lines into an array in one builtin call, associative arrays,
# lowercase-expansion, and array-length expansion (an explicit counter
# variable is used instead).
set -Eeuo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash launchd-agents.sh render|lint|install|status|remove [options]' \
    '' \
    'Subcommands:' \
    '  render  [--host NAME] [--dir DIR]' \
    '      Render adoption/launchd/*.plist.template with' \
    '      tools/adoption/render_launchd.py into DIR (default:' \
    '      under ECO_INSTALL_ROOT/state/launchd/rendered). Without --host,' \
    '      values come from HOME, ECO_INSTALL_ROOT and AI_MEMORY_URL in this' \
    '      shell.' \
    '  lint    [--dir DIR]' \
    '      plutil -lint each rendered plist when plutil is present, otherwise' \
    '      a python3 plistlib parse as a fallback.' \
    '  install [--dir DIR] [--label ID ...]' \
    '      Copy each selected rendered plist into ~/Library/LaunchAgents and' \
    '      launchctl bootstrap it into the current GUI session; records the' \
    '      label as one this script itself enabled. Refuses to overwrite an' \
    '      existing destination plist that is not already one of its own' \
    '      recorded labels. If a run is interrupted or a step fails, the' \
    '      one recovery path -- as with brew services -- is running' \
    '      install again for that label: it converges to whichever of the' \
    '      previous or the new plist is actually on disk and loaded,' \
    '      never replaying a half-finished step.' \
    '  status  [--label ID ...]' \
    '      launchctl print each selected label in the current GUI session.' \
    '  remove  [--label ID ...]' \
    '      launchctl bootout each selected label, but only one this script' \
    '      itself recorded as enabled (never one it did not install). On a' \
    '      successful bootout, deletes the copied plist under' \
    '      ~/Library/LaunchAgents so it cannot reload at the next login;' \
    '      never deletes the component'"'"'s own data or logs. On a failed' \
    '      bootout, ownership is kept (not forgotten) so a retry can find it.' \
    '' \
    'Labels (no trailing .plist): com.native-stack.qdrant and' \
    'com.native-stack.ai-memory are the default set for install/status/remove' \
    'when no --label is given; com.native-stack.llama-embed is left out of' \
    'that default until a model argument exists (adoption/platforms/' \
    'macos-arm64.md), but render/lint always cover it, and an explicit' \
    '--label com.native-stack.llama-embed still installs it.'
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
repo_root="$(cd -- "$script_dir/../.." >/dev/null 2>&1 && pwd -P)"

eco_root="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
ai_memory_url="${AI_MEMORY_URL:-127.0.0.1:49374}"
state_dir="$eco_root/state/launchd"
default_render_dir="$state_dir/rendered"
enabled_state_file="$state_dir/enabled-labels.txt"
launch_agents_dir="$HOME/Library/LaunchAgents"

all_labels=(com.native-stack.qdrant com.native-stack.ai-memory com.native-stack.llama-embed)
# llama-embed needs a model file argument this draft does not have yet (see
# adoption/platforms/macos-arm64.md); it stays a valid --label (still in
# all_labels, above, for validation) but is left out of the default set for
# install/status/remove until that exists. render/lint are unaffected: they
# iterate every rendered template, not this list, so llama-embed can still
# be previewed and lint-checked by default.
default_labels=(com.native-stack.qdrant com.native-stack.ai-memory)

[[ $# -ge 1 ]] || { usage >&2; exit 2; }
subcommand="$1"
shift

host=""
render_dir="$default_render_dir"
labels=()
label_count=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || { printf -- '--host requires a value.\n' >&2; exit 2; }
      host="$2"
      shift 2
      ;;
    --host=*)
      host="${1#--host=}"
      shift
      ;;
    --dir)
      [[ $# -ge 2 ]] || { printf -- '--dir requires a value.\n' >&2; exit 2; }
      render_dir="$2"
      shift 2
      ;;
    --dir=*)
      render_dir="${1#--dir=}"
      shift
      ;;
    --label)
      [[ $# -ge 2 ]] || { printf -- '--label requires a value.\n' >&2; exit 2; }
      labels+=("$2")
      label_count=$((label_count + 1))
      shift 2
      ;;
    --label=*)
      labels+=("${1#--label=}")
      label_count=$((label_count + 1))
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

for requested_label in ${labels[@]+"${labels[@]}"}; do
  known=0
  for known_label in "${all_labels[@]}"; do
    [[ "$requested_label" == "$known_label" ]] && { known=1; break; }
  done
  [[ "$known" == 1 ]] || {
    printf 'Unknown --label %s. Known labels: %s\n' "$requested_label" "${all_labels[*]}" >&2
    exit 2
  }
done

# Prints one label per line: the requested --label set, or every known label.
selected_labels() {
  if [[ "$label_count" -gt 0 ]]; then
    local label
    for label in "${labels[@]}"; do
      printf '%s\n' "$label"
    done
  else
    local label
    for label in "${default_labels[@]}"; do
      printf '%s\n' "$label"
    done
  fi
}

record_enabled_label() {
  local label="$1"
  mkdir -p "$state_dir"
  touch "$enabled_state_file"
  grep -Fxq "$label" "$enabled_state_file" 2>/dev/null || printf '%s\n' "$label" >>"$enabled_state_file"
}

is_enabled_label() {
  local label="$1"
  [[ -f "$enabled_state_file" ]] && grep -Fxq "$label" "$enabled_state_file"
}

forget_enabled_label() {
  local label="$1"
  [[ -f "$enabled_state_file" ]] || return 0
  grep -Fxv "$label" "$enabled_state_file" >"$enabled_state_file.tmp" 2>/dev/null || true
  mv -- "$enabled_state_file.tmp" "$enabled_state_file"
}

# Round 3e: replaces marker-based rollback (round 3b/c/d -- each fix closed
# one edge case and opened another; Codex's round-3e review found two more:
# a partial hard-copy backup, and a reload never attempted at the bootout/
# reload-marker boundary) with idempotent, state-based CONVERGENCE, the way
# `brew services` works: nothing here remembers what STEP install was on
# when it stopped. reconcile_install instead reads what is ACTUALLY true --
# which plist is currently on disk at dest_plist (told apart from the
# backup by inode via `-ef`, since the backup is a hard link: the same
# file, under a second name, until something replaces one of the two names)
# and whether launchd currently reports the label loaded -- and takes
# whichever ONE action converges that state. Calling it twice, or after
# nothing happened at all (no backup exists), is always either a no-op or a
# genuine step toward convergence, never a replay of a specific failure.
# This is also why it is the ONLY recovery logic in this file: called
# explicitly after an ordinary install attempt AND registered as the EXIT
# trap, both cases run the identical, pure function of current state.
#
# `set +e`: must never itself become fatal under the script's own `set -e`,
# whether invoked as an ordinary call or as the EXIT trap.
# Round 3f (Codex Medium: tri-state print / an unrelated loaded label):
# reports one of FOUR states for a label, never collapsing to a binary
# loaded/not-loaded the way a single `launchctl print; $?` check did:
#   loaded_here      print succeeded AND its own "path = " line names
#                    dest_plist itself -- the only state that confirms the
#                    RUNNING instance is genuinely this plist, not a
#                    same-labeled but unrelated service holding the label
#                    from somewhere else entirely.
#   loaded_elsewhere print succeeded but the path does not match dest_plist
#                    (or no path line could be read at all).
#   not_found        exit 113 -- genuinely unloaded.
#   unknown          any other exit code (permission, launchd itself
#                    unresponsive, ...).
# Callers must never take a destructive or ownership-claiming action on
# loaded_elsewhere or unknown.
launchctl_label_state() {
  local label="$1" dest_plist="$2"
  local print_output print_status
  print_output="$(launchctl print "gui/$(id -u)/$label" 2>/dev/null)"
  print_status=$?
  if [[ "$print_status" == 113 ]]; then
    printf 'not_found\n'
    return 0
  fi
  if [[ "$print_status" != 0 ]]; then
    printf 'unknown\n'
    return 0
  fi
  local loaded_path
  loaded_path="$(printf '%s\n' "$print_output" | sed -n 's/^[[:space:]]*path = //p' | head -n 1)"
  if [[ -n "$loaded_path" ]] && [[ "$loaded_path" -ef "$dest_plist" ]]; then
    printf 'loaded_here\n'
  else
    printf 'loaded_elsewhere\n'
  fi
}

current_install_label=""
# Set by cmd_install right after a successful `launchctl bootout` it issued
# this run, cleared once reconcile_install has resolved whatever ambiguity
# that leaves (round 3f finding 4: delayed teardown). A bootout returning
# success does not guarantee launchd has actually finished tearing the old
# instance down; while this flag is set, a "loaded" read is a transitional
# snapshot, not a settled one.
current_install_bootout_pending=""
reconcile_install() {
  set +e
  local label="$current_install_label"
  if [[ -z "$label" ]]; then
    set -Eeuo pipefail
    return 0
  fi
  local dest_plist="$launch_agents_dir/$label.plist"
  local backup_plist="$dest_plist.bak"
  local result=0
  local state

  if [[ ! -e "$backup_plist" ]]; then
    # No backup: either a genuine first install for this label (nothing to
    # compare dest_plist against) or an earlier reconcile already resolved
    # and removed it. Ownership is recorded HERE, never earlier (round 3f
    # finding 3): only once state confirms dest_plist's OWN content, by
    # path, is what launchd actually has loaded, so a later run's L2
    # bootout gate can never be tricked into tearing down an unrelated
    # service that merely happens to share this label.
    #
    # This whole verify-or-remove path applies ONLY when the label is not
    # already owned: an ALREADY-owned, previously-confirmed install with no
    # backup here simply means nothing is currently mid-reinstall for it --
    # there is nothing to reconcile, and a transient launchctl print hiccup
    # at this exact moment must never delete a working install. cmd_install
    # 's own bootout-gate check (with its own launchctl_label_state call,
    # immediately before it would do anything destructive) is where an
    # already-owned label's CURRENT load state is actually verified.
    if [[ -e "$dest_plist" ]] && ! is_enabled_label "$label"; then
      state="$(launchctl_label_state "$label" "$dest_plist")"
      case "$state" in
        loaded_here)
          record_enabled_label "$label"
          ;;
        not_found)
          if launchctl bootstrap "gui/$(id -u)" "$dest_plist" >/dev/null 2>&1; then
            record_enabled_label "$label"
            printf 'Converged %s: loaded a fresh install.\n' "$label" >&2
          else
            rm -f -- "$dest_plist"
            printf 'WARNING: %s could not be loaded; removed the unconfirmed %s (never recorded as enabled). Re-running "launchd-agents.sh install --label %s" starts fresh.\n' \
              "$label" "$dest_plist" "$label" >&2
            result=1
          fi
          ;;
        loaded_elsewhere|unknown)
          # Never claim it, never touch what might be running under it:
          # only the FILE this run itself wrote (never loaded, never
          # recorded) is removed.
          rm -f -- "$dest_plist"
          printf 'WARNING: %s: refusing to claim it (%s); removed the unconfirmed %s, touched nothing else. Re-running "launchd-agents.sh install --label %s" retries.\n' \
            "$label" "$([[ "$state" == unknown ]] && printf 'its load state could not be confirmed' || printf 'it is already loaded from a different path')" \
            "$dest_plist" "$label" >&2
          result=1
          ;;
      esac
    fi
    current_install_bootout_pending=""
    set -Eeuo pipefail
    return "$result"
  fi

  state="$(launchctl_label_state "$label" "$dest_plist")"
  # Round 3f finding 4 (delayed teardown): if this run attempted a bootout
  # and state still reads as loaded (either identity), that may simply be
  # launchd not having finished tearing the old instance down yet -- a
  # transitional read. Re-derive it with the SAME bounded poll the
  # pre-bootstrap check already uses (never a fresh, unbounded one) rather
  # than trusting a single snapshot a moment later would have read
  # differently.
  if [[ "$current_install_bootout_pending" == 1 ]] \
     && { [[ "$state" == loaded_here ]] || [[ "$state" == loaded_elsewhere ]]; }; then
    if wait_until_unloaded "$label"; then
      state=not_found
    else
      state=unknown
    fi
  fi
  current_install_bootout_pending=""

  if [[ "$state" == unknown ]]; then
    # Finding 2: on unknown, no destructive action and no bootstrap either
    # way -- keep the backup and report, regardless of which branch below
    # would otherwise apply.
    printf 'WARNING: %s needs attention: its load state could not be confirmed (backup at %s, kept). Re-running "launchd-agents.sh install --label %s" converges it, the way brew services does.\n' \
      "$label" "$backup_plist" "$label" >&2
    set -Eeuo pipefail
    return 1
  fi

  if [[ -e "$dest_plist" ]] && [[ "$dest_plist" -ef "$backup_plist" ]]; then
    # dest_plist is still the backup's own original (untouched, or already
    # restored by an earlier reconcile). Dropping the backup NAME is always
    # harmless in this branch regardless of state (the invariant): the same
    # data stays reachable via dest_plist's own name either way.
    if [[ "$state" == not_found ]]; then
      if launchctl bootstrap "gui/$(id -u)" "$dest_plist" >/dev/null 2>&1; then
        rm -f -- "$backup_plist"
        printf 'Converged %s: reloaded the previous install.\n' "$label" >&2
      else
        printf 'WARNING: %s needs attention (backup at %s). Re-running "launchd-agents.sh install --label %s" converges it, the way brew services does.\n' \
          "$label" "$backup_plist" "$label" >&2
        result=1
      fi
    else
      rm -f -- "$backup_plist"
    fi
  elif [[ -e "$dest_plist" ]]; then
    # A different identity from the backup: the new plist is on disk. Per
    # the invariant, the backup is deleted or consumed ONLY once the
    # service is confirmed loaded from dest_plist itself.
    if [[ "$state" == loaded_here ]]; then
      rm -f -- "$backup_plist"
    elif [[ "$state" == not_found ]]; then
      if launchctl bootstrap "gui/$(id -u)" "$dest_plist" >/dev/null 2>&1; then
        rm -f -- "$backup_plist"
        printf 'Converged %s: reloaded the new install.\n' "$label" >&2
      elif mv -f -- "$backup_plist" "$dest_plist" 2>/dev/null; then
        if launchctl bootstrap "gui/$(id -u)" "$dest_plist" >/dev/null 2>&1; then
          printf 'Converged %s: the new install would not load; restored and reloaded the previous one.\n' "$label" >&2
        else
          printf 'WARNING: %s needs attention: restored the previous plist, but it also failed to reload. Run: launchctl bootstrap "gui/%s" %q\n' \
            "$label" "$(id -u)" "$dest_plist" >&2
          result=1
        fi
      else
        printf 'WARNING: %s needs attention (backup at %s). Re-running "launchd-agents.sh install --label %s" converges it, the way brew services does.\n' \
          "$label" "$backup_plist" "$label" >&2
        result=1
      fi
    else
      # loaded_elsewhere: never confirmed as OUR content, so never drop or
      # consume the backup, and never attempt bootstrap either -- exactly
      # what an unrelated, already-loaded label needs: touched nothing.
      printf 'WARNING: %s needs attention: it is loaded from somewhere other than %s (backup at %s, kept). Re-running "launchd-agents.sh install --label %s" converges it, the way brew services does.\n' \
        "$label" "$dest_plist" "$backup_plist" "$label" >&2
      result=1
    fi
  else
    # dest_plist is missing entirely; only the backup remains.
    printf 'WARNING: %s needs attention (dest_plist missing; backup at %s). Re-running "launchd-agents.sh install --label %s" converges it, the way brew services does.\n' \
      "$label" "$backup_plist" "$label" >&2
    result=1
  fi
  set -Eeuo pipefail
  return "$result"
}
trap reconcile_install EXIT
# INT, TERM and HUP are explicitly trapped -- not left at their default,
# untrapped disposition -- so bash always defers acting on a caught signal
# until whatever foreign command is currently running (ln, cp, mv,
# launchctl) actually finishes, guaranteeing the EXIT handler above only
# ever observes a completed step, never one still in flight. Each handler
# does nothing but exit with the conventional 128+signal code, which is
# itself what triggers the EXIT trap; recovery logic lives in
# reconcile_install alone.
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# L4: launchctl bootout can return success before the service's own teardown
# has actually finished (real launchd; not something an offline shim can
# prove by itself). Trusting its exit code alone and immediately calling
# bootstrap can then race a service that has not actually stopped yet. Polls
# launchctl print for a bounded number of attempts -- checked BEFORE any
# sleep, so the common case (already unloaded by the time bootout returns)
# costs no wall-clock time at all -- until it reports 113 ("Could not find
# service", genuinely unloaded). WAIT_UNTIL_UNLOADED_ATTEMPTS/_INTERVAL are
# overridable so a test can force either a fast success or a bounded,
# fast-failing timeout without a real multi-second sleep.
wait_until_unloaded() {
  local label="$1"
  local attempts_left="${WAIT_UNTIL_UNLOADED_ATTEMPTS:-10}"
  local interval="${WAIT_UNTIL_UNLOADED_INTERVAL:-1}"
  local status
  while :; do
    status=0
    launchctl print "gui/$(id -u)/$label" >/dev/null 2>&1 || status=$?
    [[ "$status" == 113 ]] && return 0
    attempts_left=$((attempts_left - 1))
    [[ "$attempts_left" -gt 0 ]] || return 1
    sleep "$interval"
  done
}

# Reads one string-valued key from a plist file. Empty (never an error exit
# under set -e's callers, since this is always read with `$(...)`) when the
# key is absent. Prefers plutil (present on every real Mac); falls back to
# python3 plistlib where plutil is absent, same as cmd_lint.
plist_value() {
  local path="$1" key="$2"
  if command -v plutil >/dev/null; then
    plutil -extract "$key" raw -o - "$path" 2>/dev/null || true
  else
    python3 -c '
import plistlib, sys
with open(sys.argv[1], "rb") as handle:
    data = plistlib.load(handle)
value = data.get(sys.argv[2])
if isinstance(value, str):
    print(value)
' "$path" "$key" 2>/dev/null || true
  fi
}

cmd_render() {
  mkdir -p "$render_dir"
  local render_args=(--out "$render_dir")
  if [[ -n "$host" ]]; then
    render_args+=(--host "$host")
  else
    render_args+=(--set "HOME=$HOME" --set "ECO_ROOT=$eco_root" --set "AI_MEMORY_URL=$ai_memory_url")
  fi
  python3 "$repo_root/tools/adoption/render_launchd.py" "${render_args[@]}"
}

cmd_lint() {
  [[ -d "$render_dir" ]] || {
    printf 'Nothing rendered yet at %s; run the render subcommand first.\n' "$render_dir" >&2
    exit 1
  }
  local plutil_bin failure_count=0 checked_count=0 plist
  plutil_bin="$(command -v plutil || true)"
  for plist in "$render_dir"/*.plist; do
    [[ -e "$plist" ]] || continue
    checked_count=$((checked_count + 1))
    if [[ -n "$plutil_bin" ]]; then
      "$plutil_bin" -lint "$plist" || failure_count=$((failure_count + 1))
    elif python3 -c 'import plistlib, sys
with open(sys.argv[1], "rb") as handle:
    plistlib.load(handle)' "$plist"; then
      printf '%s: OK (python3 plistlib fallback; plutil unavailable on this host)\n' "$plist"
    else
      failure_count=$((failure_count + 1))
    fi
  done
  [[ "$checked_count" -gt 0 ]] || {
    printf 'No rendered *.plist files under %s.\n' "$render_dir" >&2
    exit 1
  }
  if [[ "$failure_count" -gt 0 ]]; then
    printf '%s of %s rendered plist(s) failed lint.\n' "$failure_count" "$checked_count" >&2
    exit 1
  fi
  printf 'All %s rendered plist(s) passed lint.\n' "$checked_count"
}

# --- cmd_install step table (round 3f) ------------------------------------
# INT, TERM and HUP are explicitly trapped (script-wide; see above), so bash
# always defers a caught signal until whatever foreign command is currently
# running finishes -- every step's outcome is the same whether it fails
# outright or is interrupted by a signal. If a run stops anywhere below,
# re-running "install --label <label>" converges it (the way `brew
# services` does): reconcile_install (called both explicitly at the end of
# a normal attempt and via the EXIT trap) is the ONLY recovery logic, and it
# is a pure function of what is actually on disk and actually loaded, never
# a replay of a specific step. Round 3f moved TWO things relative to round
# 3e's table, both load-bearing for the fixes below: ownership
# (record_enabled_label) is no longer recorded at step 1 -- only inside
# reconcile_install (step 9), once launchctl_label_state has path-confirmed
# dest_plist itself is what is actually loaded -- and a failed preflight
# (step 2) now ABORTS this run instead of continuing past it.
# Step                                    | State this can leave behind                                   | What reconcile_install does with it
# 1. snapshot was_already_enabled + set   | dest_plist/backup untouched; ownership NOT yet recorded even   | (a pure bookkeeping step; nothing to
#    current_install_label                | for a fresh install (round 3f: moved to step 9)                | reconcile from it alone)
# 2. reconcile any stale backup from a    | (reconcile_install is itself idempotent/safe to interrupt)     | round 3f High: this call's OWN
#    previous run (pre-flight)            |                                                                 | failure now aborts (`|| exit 1`) --
#                                         |                                                                 | it no longer continues past an
#                                         |                                                                 | unresolved prior backup into step 3
# 3. ln dest_plist -> backup_plist        | either exists completely or not at all (a hard link is atomic) | dest_plist -ef backup_plist: "old"
#    (hard link, only if dest existed)    |                                                                 | case below
# 4. bootout gate (only if                | round 3f findings 2 and 3: launchctl_label_state must confirm  | refuses and exits BEFORE any of
#    was_already_enabled): launchctl_     | loaded_here (a path match, not just any successful print) --   | steps 5-8 run at all on
#    label_state, then bootout if         | loaded_elsewhere or unknown refuses outright, touching nothing | loaded_elsewhere/unknown; re-derives
#    loaded_here                          |                                                                 | loaded via launchctl print itself
# 5. wait_until_unloaded (best effort --  | current_install_bootout_pending=1 while this is unresolved     | otherwise (steps 5-8 proceed as
#    its own timeout is not itself a      | (round 3f finding 4: a bootout success does not guarantee      | before)
#    failure branch, but install DOES     | teardown has actually finished)                                |
#    refuse if it never resolves)         |                                                                 |
# 6. cp source_plist -> dest_plist.new    | dest_plist unchanged; dest_plist.new may be partial (inert,    | same as 4-5 (dest_plist still "old")
#    (staging)                            | never read by anything live)                                   |
# 7. mv dest_plist.new -> dest_plist      | dest_plist now the NEW content (a different inode from backup) | dest_plist not -ef backup_plist:
#    (same-directory rename-into-place)  |                                                                 | "new" case -- loaded_here drops the
#                                         |                                                                 | backup and records ownership; not_
#                                         |                                                                 | found bootstraps it or (that failing)
#                                         |                                                                 | restores+reloads the backup;
#                                         |                                                                 | loaded_elsewhere/unknown never
#                                         |                                                                 | touches the backup or bootstraps
# 8. launchctl bootstrap (best effort --  | dest_plist is NEW; loaded state unknown until reconcile checks | same as 7
#    its own success/failure is not       |                                                                 |
#    itself a failure branch)             |                                                                 |
# 9. reconcile_install (explicit, always  | converged: backup dropped and ownership recorded (only once    | (this IS the recovery step; nothing
#    called -- see above)                 | loaded_here is path-confirmed), or kept with the exact manual  | further to reconcile from it). If
#                                         | command printed (needs attention). Round 3f finding 4: if this | current_install_bootout_pending is
#                                         | run's own bootout is still pending, re-polls (reusing step 5's | still set here, re-polls before
#                                         | wait_until_unloaded) rather than trusting one transitional read| trusting a "loaded" read (see step 5)
# ---------------------------------------------------------------------------
cmd_install() {
  [[ -d "$render_dir" ]] || {
    printf 'Nothing rendered yet at %s; run the render subcommand first.\n' "$render_dir" >&2
    exit 1
  }
  mkdir -p "$launch_agents_dir"
  local label source_plist dest_plist backup_plist
  while IFS= read -r label; do
    source_plist="$render_dir/$label.plist"
    [[ -f "$source_plist" ]] || {
      printf 'No rendered plist for %s at %s; run the render subcommand first.\n' "$label" "$source_plist" >&2
      exit 1
    }
    dest_plist="$launch_agents_dir/$label.plist"
    # Snapshotted once, before record_enabled_label (right below) makes
    # is_enabled_label true for the rest of this iteration regardless: L2's
    # bootout gate further down needs to know whether this label was ALREADY
    # ours before this run started, never whether it is ours NOW.
    local was_already_enabled=0
    is_enabled_label "$label" && was_already_enabled=1
    if [[ -e "$dest_plist" ]] && [[ "$was_already_enabled" != 1 ]]; then
      printf 'Refusing to overwrite %s: it already exists and %s is not recorded as a label this script itself enabled (%s). Move or remove it yourself first if it is safe to replace.\n' \
        "$dest_plist" "$label" "$enabled_state_file" >&2
      exit 1
    fi

    # Only from here on is this label's own state this run's responsibility
    # to reconcile, including via the EXIT trap. Ownership itself is
    # recorded inside reconcile_install, never here (round 3f finding 3):
    # only once a label's state is confirmed loaded from dest_plist's own
    # path can a later run's L2 bootout gate safely trust it.
    current_install_label="$label"
    backup_plist="$dest_plist.bak"

    # Converge any incomplete attempt from an EARLIER run for this exact
    # label first (brew-services style): a leftover backup here means a
    # previous install never finished, and building this run on top of that
    # would only compound it. Round 3f High: its OWN failure to reach a
    # clean, converged state must abort this run -- continuing past it
    # (the previous design's `|| true`) let execution reach the backup
    # step below with an UNRESOLVED prior backup still describing the last
    # known-good install, immediately overwriting that description with a
    # fresh hard link to whatever (possibly unusable) content dest_plist
    # currently holds, permanently losing the only way back.
    reconcile_install || exit 1

    # Every directory this plist writes into or runs from comes from ITS
    # OWN declared StandardOutPath/StandardErrorPath/WorkingDirectory, never
    # this shell's ECO_INSTALL_ROOT: a plist rendered with --host against a
    # different host's value file can point anywhere, and launchd does not
    # create missing parent directories for any of the three on its own.
    local declared_path key
    for key in StandardOutPath StandardErrorPath; do
      declared_path="$(plist_value "$source_plist" "$key")"
      [[ -n "$declared_path" ]] && mkdir -p "$(dirname -- "$declared_path")"
    done
    declared_path="$(plist_value "$source_plist" WorkingDirectory)"
    [[ -n "$declared_path" ]] && mkdir -p "$declared_path"

    if [[ -e "$dest_plist" ]]; then
      # A hard link either exists completely or it does not exist at all --
      # unlike `cp`, there is no partial-copy state a signal or a disk-full
      # error could leave behind (Codex round-3e High). Same directory as
      # dest_plist (never this script's own state_dir): a restore-by-rename
      # is only genuinely atomic when guaranteed to be on the same
      # filesystem, which only dest_plist's own directory guarantees
      # (ECO_INSTALL_ROOT may legitimately be a separate mounted volume).
      # Its name never ends in ".plist", so launchd's own directory scan
      # never treats it as a unit definition to auto-load.
      rm -f -- "$backup_plist"
      ln -- "$dest_plist" "$backup_plist"
    fi

    # A re-run on an owned label that is still loaded (e.g. reinstalling
    # after a re-render) would otherwise have the rename below replace the
    # live service's own plist file, then `launchctl bootstrap` fail
    # because the label is already bootstrapped (launchctl error 5).
    # Unload it first, so the fresh bootstrap further down actually
    # applies. Only ever probed or unloaded for a label this script ALREADY
    # owned before this run (L2, was_already_enabled): a label that merely
    # happens to be loaded by something else entirely -- no destination
    # plist yet, never previously recorded as enabled -- is never this
    # script's to bootout.
    if [[ "$was_already_enabled" == 1 ]]; then
      local pre_bootout_state
      pre_bootout_state="$(launchctl_label_state "$label" "$dest_plist")"
      case "$pre_bootout_state" in
        loaded_here)
          if ! launchctl bootout "gui/$(id -u)/$label"; then
            printf 'Refusing to reinstall %s: it is currently loaded and launchctl bootout failed; leaving it running, unmodified.\n' \
              "$label" >&2
            exit 1
          fi
          # Round 3f finding 4: bootout returning success does not
          # guarantee teardown has actually finished. Flagged for
          # reconcile_install (below, and the EXIT trap): if a signal or an
          # error reaches it before wait_until_unloaded resolves this, it
          # re-derives the settled state with the same bounded poll rather
          # than trusting a transitional "still loaded" read.
          current_install_bootout_pending=1
          # Never bootstrap the new content over a service that never
          # actually stopped.
          if ! wait_until_unloaded "$label"; then
            printf 'Refusing to reinstall %s: launchctl bootout succeeded but the service did not report unloaded (launchctl print never returned 113) within the bounded wait; leaving it as is.\n' \
              "$label" >&2
            exit 1
          fi
          current_install_bootout_pending=""
          ;;
        not_found)
          : # Nothing loaded under this label; proceed straight to staging.
          ;;
        loaded_elsewhere)
          # Round 3f finding 3: even for a label this script has recorded
          # owning before, never bootout something whose CURRENT loaded
          # instance is not confirmed to be dest_plist itself -- an
          # unrelated service could have since taken the same label.
          # Refuse and touch nothing.
          printf 'Refusing to reinstall %s: it is loaded from somewhere other than %s; leaving it running, unmodified. Investigate launchctl print gui/%s/%s.\n' \
            "$label" "$dest_plist" "$(id -u)" "$label" >&2
          exit 1
          ;;
        unknown)
          # L5: only exit 113 ("Could not find service") is confidently
          # "not loaded"; any other launchctl print failure (permission,
          # launchd itself unresponsive, ...) must refuse rather than
          # silently assume "not loaded" and bootstrap over state print
          # could not determine -- exactly what remove already does for
          # the same exit code, below.
          printf 'Refusing to reinstall %s: launchctl print did not confidently report loaded, not-found, or a matching path; leaving it as is. Investigate launchctl print gui/%s/%s.\n' \
            "$label" "$(id -u)" "$label" >&2
          exit 1
          ;;
      esac
    fi

    # Stage in the same directory, then rename into place: a failed `cp`
    # here never reaches the live dest_plist at all (nothing ever reads
    # dest_plist.new -- it is inert until this rename succeeds).
    cp -- "$source_plist" "$dest_plist.new"
    mv -f -- "$dest_plist.new" "$dest_plist"
    launchctl bootstrap "gui/$(id -u)" "$dest_plist" >/dev/null 2>&1 || true
    local reconcile_status=0
    reconcile_install || reconcile_status=$?
    # Cleared once this label has been explicitly reconciled (whichever way
    # it went): the EXIT trap's own reconcile_install call, should this
    # process go on to exit for any reason (including this one, below),
    # then sees no current_install_label and does nothing further -- one
    # reconciliation per attempt, not two duplicate reports for the same
    # outcome.
    current_install_label=""
    [[ "$reconcile_status" == 0 ]] || exit 1
    printf 'Installed %s (%s)\n' "$label" "$dest_plist"
  done < <(selected_labels)
}

cmd_status() {
  local label
  while IFS= read -r label; do
    printf -- '-- %s --\n' "$label"
    launchctl print "gui/$(id -u)/$label" || printf '%s: launchctl print exited %s\n' "$label" "$?"
  done < <(selected_labels)
}

cmd_remove() {
  local label removed_count=0 skipped_count=0 failed_count=0
  while IFS= read -r label; do
    if is_enabled_label "$label"; then
      local print_status=0
      launchctl print "gui/$(id -u)/$label" >/dev/null 2>&1 || print_status=$?
      if [[ "$print_status" == 113 ]]; then
        # 113 is launchctl's own "Could not find service" -- genuinely not
        # loaded (already unloaded outside this script, crashed, or never
        # finished bootstrapping), so `bootout` would just fail on something
        # that is not there. Clean up directly instead of calling it.
        rm -f -- "$launch_agents_dir/$label.plist"
        forget_enabled_label "$label"
        removed_count=$((removed_count + 1))
        printf '%s was not loaded; removed %s directly (component data and logs kept).\n' \
          "$label" "$launch_agents_dir/$label.plist"
      elif [[ "$print_status" -ne 0 ]]; then
        # Any other launchctl print failure (permission, launchd itself
        # unresponsive, ...) is not confidently "not loaded", so this is
        # neither a safe direct cleanup nor a safe bootout target. Keep
        # ownership and report, rather than guess either way.
        printf '%s: launchctl print failed with exit %s (not 113/"not found"); ownership kept, nothing removed. Investigate launchctl print gui/%s/%s.\n' \
          "$label" "$print_status" "$(id -u)" "$label" >&2
        failed_count=$((failed_count + 1))
      elif launchctl bootout "gui/$(id -u)/$label"; then
        # Deleted, not left behind: RunAtLoad plus the plist still sitting
        # under ~/Library/LaunchAgents would make launchd reload it at the
        # next login regardless of this bootout. This removes only the
        # copied unit-definition file this script itself placed there,
        # never the component's own data or logs.
        rm -f -- "$launch_agents_dir/$label.plist"
        forget_enabled_label "$label"
        removed_count=$((removed_count + 1))
        printf 'Booted out %s and removed %s (component data and logs kept).\n' \
          "$label" "$launch_agents_dir/$label.plist"
      else
        # Ownership is kept, not forgotten: a failed bootout means the
        # plist can still reload at the next login, so this label stays
        # this script's problem to retry, not a silently dropped one.
        printf '%s: launchctl bootout failed; ownership kept and %s was NOT removed (it can still reload at the next login). Retry remove, or inspect launchctl print gui/%s/%s.\n' \
          "$label" "$launch_agents_dir/$label.plist" "$(id -u)" "$label" >&2
        failed_count=$((failed_count + 1))
      fi
    else
      printf '%s was not enabled by this script; skipping (never removes a label it did not install).\n' "$label" >&2
      skipped_count=$((skipped_count + 1))
    fi
  done < <(selected_labels)
  printf 'Booted out %s label(s); skipped %s not-enabled label(s); %s failed.\n' \
    "$removed_count" "$skipped_count" "$failed_count"
  [[ "$failed_count" -eq 0 ]]
}

case "$subcommand" in
  render) cmd_render ;;
  lint) cmd_lint ;;
  install) cmd_install ;;
  status) cmd_status ;;
  remove) cmd_remove ;;
  --help|-h) usage ;;
  *)
    printf 'Unknown subcommand: %s\n' "$subcommand" >&2
    usage >&2
    exit 2
    ;;
esac
