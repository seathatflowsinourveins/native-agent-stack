#!/usr/bin/env bash
# Drafted, not run: launchctl bootstrap/print/bootout below act on a real
# macOS user's launchd session; no macOS host has run this script (see
# adoption/platforms/macos-arm64.md, "What a hosted run proves"). Keep this
# script bash 3.2 compatible: a stock Mac has /bin/bash 3.2, so this avoids
# reading lines into an array in one builtin call, associative arrays,
# lowercase-expansion, and array-length expansion (an explicit counter
# variable is used instead).
set -Eeuo pipefail

# Round 3k (coordinator, WSL-host CPU-load flakiness fix): exported purely
# for offline fault-injection tests. A shim that must signal THIS script's
# own top-level process reads this instead of $PPID -- $PPID is correct
# today for every foreign command this script calls directly (none of
# them run inside a $(...) or a pipeline, so $PPID already equals $$ at
# each call site), but that is not an invariant future edits are
# guaranteed to preserve; bootout_and_wait's own subshell-vs-plain-call
# comment below records exactly how that assumption broke once already.
# No production code path reads this variable.
export ADOPTION_SCRIPT_PID="$$"

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
    '      Stage each selected rendered plist as a temp file beside its' \
    '      destination under ~/Library/LaunchAgents and lint it; if the' \
    '      label is currently loaded FROM THAT SAME destination path,' \
    '      bootout and wait for it to unload; rename the temp file into' \
    '      place; launchctl enable and bootstrap it. Refuses outright,' \
    '      touching nothing, if the label is loaded from any OTHER path or' \
    '      its load state cannot be confirmed (brew-services semantics: no' \
    '      backup, no rollback, no ownership file -- see' \
    '      adoption/platforms/macos-arm64.md for why rounds 3b-3f'"'"'s' \
    '      transactional backup/reconcile design was replaced with this).' \
    '      If a run is interrupted or a step fails, re-running install is' \
    '      the recovery path, exactly like brew services.' \
    '  status  [--label ID ...]' \
    '      launchctl print each selected label in the current GUI session.' \
    '  remove  [--label ID ...]' \
    '      If the label is currently loaded FROM ITS OWN destination path,' \
    '      bootout, wait for it to unload, then delete the plist under' \
    '      ~/Library/LaunchAgents so it cannot reload at the next login. If' \
    '      it is not loaded at all, deletes the plist directly if one is' \
    '      present. Refuses outright, touching nothing, if the label is' \
    '      loaded from any OTHER path or its load state cannot be' \
    '      confirmed. Never deletes the component'"'"'s own data or logs.' \
    '' \
    'Labels (no trailing .plist): com.native-stack.qdrant,' \
    'com.native-stack.ai-memory and com.native-stack.llama-embed are the' \
    'default set for install/status/remove when no --label is given.'
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
repo_root="$(cd -- "$script_dir/../.." >/dev/null 2>&1 && pwd -P)"

eco_root="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
ai_memory_url="${AI_MEMORY_URL:-127.0.0.1:49374}"
# Round 3h: the path install_embed_model (adoption/bootstrap-macos.sh)
# downloads and sha256-verifies the pinned embedding model to; the
# llama-embed template's own -m flag names this same path.
embed_model_path="${EMBED_MODEL_PATH:-$eco_root/state/models/embeddinggemma-300M-Q8_0.gguf}"
state_dir="$eco_root/state/launchd"
default_render_dir="$state_dir/rendered"
launch_agents_dir="$HOME/Library/LaunchAgents"

all_labels=(com.native-stack.qdrant com.native-stack.ai-memory com.native-stack.llama-embed)
# Round 3j (Codex P2 review thread 1): llama-embed used to be left out of
# the default install/status/remove set because it needed a model file
# argument this draft did not have yet. Round 3h's install_embed_model
# (adoption/bootstrap-macos.sh) downloads and sha256-verifies that model
# unconditionally, and the template's -m flag names it via
# EMBED_MODEL_PATH above, so there is no longer a reason to leave it out
# of the default set -- an explicit --label was the only way to reach it
# before this.
default_labels=(com.native-stack.qdrant com.native-stack.ai-memory com.native-stack.llama-embed)

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

# Round 3g: converges on the maintained upstream pattern (Homebrew/brew
# Library/Homebrew/services/cli.rb @ 8e3a5dc0a7, 2026-09-07: `stop` boots out
# and deletes the service file; `install_service_file` writes a temp file,
# removes the old one and installs the new one, then `launchctl_load` calls
# `launchctl enable` and `launchctl bootstrap`; there is no backup, no
# rollback and no ownership file -- recovery is re-running the command).
# Five rounds (3b-3f) of a transactional backup/reconcile design each found a
# NEW recovery defect the previous round's fix had not covered (round 3f's
# own review of 0e1e0d4 found four more: remove booting out an unrelated
# service, a print error on fresh install deleting an already-loaded plist,
# a signal during bootout or restore leaving the service stopped with no
# retry path built in, and an ownership-write failure falsely reporting
# success) -- see adoption/platforms/macos-arm64.md's dated decision for why
# that whole approach is retired rather than patched a sixth time.
#
# STATELESS OWNERSHIP: there is no ownership file, no record_enabled_label,
# no is_enabled_label, no was_already_enabled, and no backup of any kind.
# "Ours" means: the label is one of this script's own (com.native-stack.*,
# validated above), and -- if launchd currently reports it loaded at all --
# the "path = " line in `launchctl print` names dest_plist itself, never
# some other, unrelated service that merely happens to share the label.
# launchctl_label_state below still reports the same FOUR states round 3f
# introduced (loaded_here / loaded_elsewhere / not_found / unknown); the
# change is that install and remove both now refuse OUTRIGHT, touching
# nothing, on loaded_elsewhere or unknown -- neither ever again "resolves"
# an uncertain state by deleting or claiming a file the way the old
# reconcile_install's own bugs repeatedly did.
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
# loaded_elsewhere or unknown, in EITHER install or remove.
#
# Round 3i (Codex Medium): resolves symlinks in a path's PARENT directory
# only, then reattaches the path's own final component unresolved -- never
# requires the path itself to exist. This is deliberately NOT `-ef`
# (device+inode comparison): two DISTINCT hard-linked filenames sharing the
# same inode are two different names for the same data, but they are not
# the same NAME, and launchctl_label_state must never treat a label loaded
# from a hard-linked alias of dest_plist as loaded_here -- `-ef` collapsed
# that distinction (reproduced: an unmodified classifier reported
# loaded_here for a distinct hard link, letting remove below bootout an
# elsewhere-loaded label). Resolving only the parent directory (not the
# final component) is what keeps a SYMLINKED ANCESTOR comparing equal to
# its real target (what launchctl itself may report) while still keeping
# two hard-linked leaf names distinct: neither `cd -P` nor python3's
# os.path.realpath ever collapses a hard link's own pathname the way
# device+inode identity does, since a hard link has no stored "canonical
# name" to resolve to in the first place.
#
# Round 3i follow-up (Codex): the LEAF is resolved too when it is itself a
# symlink (launchctl may report a symlinked plist by its resolved target), by
# following readlink one hop at a time and re-resolving the parent each time.
# Hard links are still never collapsed (they are not symlinks), and a symlink
# loop stops after 40 hops and compares unresolved, i.e. as loaded_elsewhere.
canonical_plist_path() {
  local target="$1"
  local dir base resolved_dir link hops=0
  while :; do
    dir="$(dirname -- "$target")"
    base="$(basename -- "$target")"
    resolved_dir="$(cd -P -- "$dir" 2>/dev/null && pwd -P)" || break
    target="$resolved_dir/$base"
    if [[ -L "$target" && "$hops" -lt 40 ]]; then
      link="$(readlink "$target")" || break
      case "$link" in
        /*) target="$link" ;;
        *) target="$resolved_dir/$link" ;;
      esac
      hops=$((hops + 1))
      continue
    fi
    printf '%s\n' "$target"
    return
  done
  # The parent directory does not exist (unusual: $launch_agents_dir is
  # always created first, but never crash on it) -- python3's
  # os.path.realpath tolerates a non-existent path entirely, matching
  # adoption/bootstrap-macos.sh's own canonical_path for the same reason.
  if command -v python3 >/dev/null 2>&1; then
    local resolved
    resolved="$(python3 -c 'import os, sys
print(os.path.realpath(sys.argv[1]))' "$target" 2>/dev/null)" && [[ -n "$resolved" ]] && {
      printf '%s\n' "$resolved"
      return
    }
  fi
  # Neither worked: the original, unresolved path is still a meaningful
  # comparison (it still correctly distinguishes two hard-linked names --
  # only a symlinked ancestor would go undetected here).
  printf '%s\n' "$target"
}

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
  if [[ -n "$loaded_path" ]] \
     && [[ "$(canonical_plist_path "$loaded_path")" == "$(canonical_plist_path "$dest_plist")" ]]; then
    printf 'loaded_here\n'
  else
    printf 'loaded_elsewhere\n'
  fi
}

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

# Round 3i (Codex Medium): a `launchctl bootout` that returns nonzero
# because teardown is ALREADY under way -- EINPROGRESS, Darwin errno 36 --
# is not a genuine failure: something (this run's own retry of an earlier
# interrupted attempt, or another process entirely) already started
# tearing this label down and simply has not finished yet. The pinned
# Homebrew implementation this project converges on
# (Library/Homebrew/services/cli.rb @ 8e3a5dc0a7, around line 311) checks
# exactly `exit_status == Errno::EINPROGRESS::Errno` for the identical
# reason, then keeps waiting rather than treating it as a failure.
# Reproduced without this fix: an interrupted run's own bootout leaves
# teardown in progress, and a clean retry's bootout call returns
# EINPROGRESS, which an unconditional `if ! launchctl bootout` refused
# outright -- abandoning the in-progress teardown with no wait and no
# reload ever attempted, leaving the service stopped until a human
# notices. This project's offline harness cannot independently confirm
# launchctl surfaces exactly 36 as its own raw process exit status (no
# real launchd to observe); this is source-supported inference from
# Homebrew's own pinned source, not a native observation. Shared by
# cmd_install and cmd_remove so both benefit identically; sets the global
# bootout_and_wait_result to one of "ok", "bootout_failed" or
# "wait_timeout" so each caller reports in its own already-established
# wording. Deliberately NOT `result="$(bootout_and_wait ...)"`: a bash
# command substitution forks a subshell, and empirically (verified with a
# real SIGINT against a shimmed launchctl) a signal delivered while a
# foreign command runs INSIDE that subshell is silently swallowed there --
# it never reaches this script's own INT/TERM/HUP traps at all, unlike a
# signal during a directly-called (non-substituted) foreign command. Using
# a plain function call plus a global result variable keeps bootout_and_
# wait running in the SAME process as its caller, preserving the exact
# signal-deferral behavior every other step in this script already
# depends on.
bootout_and_wait_result=""
bootout_and_wait() {
  local label="$1"
  local bootout_status=0
  launchctl bootout "gui/$(id -u)/$label" || bootout_status=$?
  if [[ "$bootout_status" != 0 ]] && [[ "$bootout_status" != 36 ]]; then
    bootout_and_wait_result="bootout_failed"
    return 1
  fi
  if ! wait_until_unloaded "$label"; then
    bootout_and_wait_result="wait_timeout"
    return 1
  fi
  bootout_and_wait_result="ok"
  return 0
}

# Round 3g: the ONLY thing an interrupted run needs cleaned up is its own
# still-inert temp file (never dest_plist itself: nothing ever renames INTO
# a partially-written dest_plist -- see cmd_install's step 1/3). There is no
# recovery logic here any more -- no backup to restore, no ownership to
# reconcile -- because there is nothing transactional left to reconcile:
# whatever state a signal or a failure leaves behind (the label still
# loaded from the old plist, unloaded with the old plist still on disk,
# unloaded with the new plist on disk, or the new plist loaded) is simply
# read fresh, from scratch, the next time install or remove runs. Cleared
# the moment the rename it is guarding succeeds, so this never fires on a
# file that no longer exists at that path anyway (rm -f is a no-op then
# regardless).
current_temp_file=""
cleanup() {
  set +e
  [[ -n "$current_temp_file" ]] && rm -f -- "$current_temp_file"
  set -Eeuo pipefail
}
trap cleanup EXIT
# INT, TERM and HUP are explicitly trapped -- not left at their default,
# untrapped disposition -- so bash always defers acting on a caught signal
# until whatever foreign command is currently running (cp, mv, launchctl)
# actually finishes, guaranteeing the EXIT handler above only ever observes
# a completed step, never one still in flight. Each handler does nothing
# but exit with the conventional 128+signal code, which is itself what
# triggers the EXIT trap.
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

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

# Lints one plist file in place: plutil if present, a python3 plistlib
# parse otherwise (same fallback cmd_lint itself uses). No output on
# success; the caller decides what, if anything, to report.
lint_one_plist() {
  local path="$1"
  if command -v plutil >/dev/null; then
    plutil -lint -- "$path" >/dev/null 2>&1
  else
    python3 -c 'import plistlib, sys
with open(sys.argv[1], "rb") as handle:
    plistlib.load(handle)' "$path" >/dev/null 2>&1
  fi
}

cmd_render() {
  mkdir -p "$render_dir"
  local render_args=(--out "$render_dir")
  if [[ -n "$host" ]]; then
    render_args+=(--host "$host")
  else
    render_args+=(--set "HOME=$HOME" --set "ECO_ROOT=$eco_root" --set "AI_MEMORY_URL=$ai_memory_url" \
                  --set "EMBED_MODEL_PATH=$embed_model_path")
  fi
  python3 "$repo_root/tools/adoption/render_launchd.py" "${render_args[@]}"
}

cmd_lint() {
  [[ -d "$render_dir" ]] || {
    printf 'Nothing rendered yet at %s; run the render subcommand first.\n' "$render_dir" >&2
    exit 1
  }
  local plutil_bin failure_count=0 checked_count=0 plist expected_label actual_label
  plutil_bin="$(command -v plutil || true)"
  for plist in "$render_dir"/*.plist; do
    [[ -e "$plist" ]] || continue
    checked_count=$((checked_count + 1))
    if [[ -n "$plutil_bin" ]]; then
      if ! "$plutil_bin" -lint "$plist"; then
        failure_count=$((failure_count + 1))
        continue
      fi
    elif python3 -c 'import plistlib, sys
with open(sys.argv[1], "rb") as handle:
    plistlib.load(handle)' "$plist"; then
      printf '%s: OK (python3 plistlib fallback; plutil unavailable on this host)\n' "$plist"
    else
      failure_count=$((failure_count + 1))
      continue
    fi
    # Round 3j (Codex P2 thread 7): the rendered filename IS the label
    # every other subcommand addresses this plist by (dest_plist ==
    # "$launch_agents_dir/$label.plist", and --label/selected_labels
    # match it exactly); launchd itself also expects the plist's own
    # Label key to agree with its filename. A mismatch here -- a rendered
    # template whose Label was edited without renaming the file, or vice
    # versa -- would install and bootstrap under one label while the file
    # on disk claims another, silently. Only reached once the file has
    # already passed syntax lint above, so plist_value's own plutil/
    # plistlib fallback can trust it parses.
    # Pure bash parameter expansion (never an external basename call): the
    # rest of cmd_lint has no dependency beyond plutil-or-python3, and this
    # keeps it that way.
    expected_label="${plist##*/}"
    expected_label="${expected_label%.plist}"
    actual_label="$(plist_value "$plist" Label)"
    if [[ "$actual_label" != "$expected_label" ]]; then
      printf '%s: Label %s does not match its own filename (expected %s).\n' \
        "$plist" "$actual_label" "$expected_label" >&2
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

# --- cmd_install step table (round 3g: brew-services semantics) -----------
# INT, TERM and HUP are explicitly trapped (script-wide; see above), so bash
# always defers a caught signal until whatever foreign command is currently
# running finishes -- every step's outcome is the same whether it fails
# outright or is interrupted by a signal. There is no backup and no
# reconcile step any more: if a run stops anywhere below, re-running
# "install --label <label>" is simply a fresh attempt against whatever is
# now actually on disk and actually loaded -- exactly the way `brew
# services` itself recovers, with no transactional machinery to reconcile.
# Step                                     | State this can leave behind
# 1. Stage source_plist as a temp file     | dest_plist untouched; the temp file is inert (never read by anything
#    beside dest_plist and lint it         | live) until step 3's rename. A lint failure exits here; nothing else
#                                           | is touched. The EXIT trap removes this temp file on any exit before
#                                           | step 3 clears current_temp_file.
# 2. launchctl_label_state, then bootout   | loaded_here: bootout, then wait_until_unloaded (bounded). Either
#    + wait if loaded_here                 | failing refuses outright and exits -- dest_plist and the temp file
#                                           | are both left exactly as they were (steps 3-5 never run).
#                                           | loaded_elsewhere/unknown: refuses outright, touching nothing at all.
#                                           | not_found: nothing loaded; proceeds straight to step 3.
# 3. Rename the temp file over dest_plist  | dest_plist is now the NEW content (a single same-directory rename,
#                                           | not a partial-copy state a signal could leave behind).
#                                           | current_temp_file is cleared immediately after.
# 4. launchctl enable + bootstrap          | dest_plist is NEW, on disk, but not yet confirmed loaded until
#                                           | bootstrap's own exit code (enable is best-effort: it only clears a
#                                           | previous "disabled" override, matching brew services' own
#                                           | launchctl_load).
# 5. Bootstrap failure                     | Reported with the exact recovery command (re-run install, or run
#                                           | remove); exits non-zero. The NEW plist is left in place, unloaded --
#                                           | never rolled back to whatever was there before, because there is no
#                                           | backup to roll back to (brew services does not roll back either).
# ---------------------------------------------------------------------------
cmd_install() {
  [[ -d "$render_dir" ]] || {
    printf 'Nothing rendered yet at %s; run the render subcommand first.\n' "$render_dir" >&2
    exit 1
  }
  mkdir -p "$launch_agents_dir"
  local label source_plist dest_plist temp_plist state declared_path key
  while IFS= read -r label; do
    source_plist="$render_dir/$label.plist"
    [[ -f "$source_plist" ]] || {
      printf 'No rendered plist for %s at %s; run the render subcommand first.\n' "$label" "$source_plist" >&2
      exit 1
    }
    dest_plist="$launch_agents_dir/$label.plist"

    # Step 1: stage in the SAME directory as dest_plist (never this
    # script's own state_dir: ECO_INSTALL_ROOT may legitimately be a
    # separate mounted volume, and step 3's rename is only genuinely atomic
    # on the same filesystem) and lint before anything live is touched. Its
    # name never ends in ".plist", so launchd's own directory scan never
    # treats it as a unit definition to auto-load.
    temp_plist="$dest_plist.new.$$"
    current_temp_file="$temp_plist"
    cp -- "$source_plist" "$temp_plist"
    if ! lint_one_plist "$temp_plist"; then
      printf 'Refusing to install %s: the rendered plist failed lint; nothing was touched under %s.\n' \
        "$label" "$dest_plist" >&2
      exit 1
    fi

    # Step 2: stateless ownership. "Ours" means this label, loaded from
    # dest_plist's own path if it is loaded at all -- never a historical
    # ownership record, and never any successful `launchctl print` whose
    # path was not actually checked (round 3f's remove finding, fixed here
    # for install and remove alike by sharing the exact same check).
    state="$(launchctl_label_state "$label" "$dest_plist")"
    case "$state" in
      loaded_here)
        # A re-run on a label that is still loaded (e.g. reinstalling after
        # a re-render) would otherwise have the rename below replace the
        # live service's own plist file, then `launchctl bootstrap` fail
        # because the label is already bootstrapped (launchctl error 5).
        # Unload it first, so the fresh bootstrap further down actually
        # applies.
        # Never bootstrap the new content over a service that never
        # actually stopped. Round 3f finding 4 (delayed teardown) no longer
        # has a "trust one transitional read" failure mode to fix here:
        # this IS the one and only check, made before the rename, not a
        # later reconcile re-deriving what already happened. bootout_and_
        # wait also absorbs EINPROGRESS (round 3i) rather than refusing on
        # it outright.
        if ! bootout_and_wait "$label"; then
          case "$bootout_and_wait_result" in
            bootout_failed)
              printf 'Refusing to install %s: it is currently loaded and launchctl bootout failed; leaving it running, unmodified.\n' \
                "$label" >&2
              ;;
            *)
              printf 'Refusing to install %s: launchctl bootout succeeded but the service did not report unloaded (launchctl print never returned 113) within the bounded wait; leaving it as is.\n' \
                "$label" >&2
              ;;
          esac
          exit 1
        fi
        ;;
      not_found)
        : # Nothing loaded under this label; proceed straight to the rename.
        ;;
      loaded_elsewhere)
        # Never bootout something whose CURRENT loaded instance is not
        # confirmed to be dest_plist itself -- an unrelated service could
        # hold the same label from somewhere else entirely. Refuse and
        # touch nothing (the temp file is cleaned up by the EXIT trap).
        printf 'Refusing to install %s: it is loaded from somewhere other than %s; leaving it running, unmodified. Investigate launchctl print gui/%s/%s.\n' \
          "$label" "$dest_plist" "$(id -u)" "$label" >&2
        exit 1
        ;;
      unknown)
        # Only exit 113 ("Could not find service") is confidently "not
        # loaded"; any other launchctl print failure (permission, launchd
        # itself unresponsive, ...) must refuse rather than silently assume
        # "not loaded" and bootstrap over state print could not determine.
        printf 'Refusing to install %s: launchctl print did not confidently report loaded, not-found, or a matching path; leaving it as is. Investigate launchctl print gui/%s/%s.\n' \
          "$label" "$(id -u)" "$label" >&2
        exit 1
        ;;
    esac

    # Round 3j (Codex P2 thread 2): moved here, AFTER the ownership check
    # above, not before it -- on loaded_elsewhere or unknown, install must
    # touch nothing at all (both branches already exit 1 above), and
    # creating these directories before that check ran meant a refused
    # install still left new, empty directories behind under whatever this
    # plist declares, even for a label this run has no business touching.
    # Every directory this plist writes into or runs from comes from ITS
    # OWN declared StandardOutPath/StandardErrorPath/WorkingDirectory, never
    # this shell's ECO_INSTALL_ROOT: a plist rendered with --host against a
    # different host's value file can point anywhere, and launchd does not
    # create missing parent directories for any of the three on its own.
    for key in StandardOutPath StandardErrorPath; do
      declared_path="$(plist_value "$source_plist" "$key")"
      [[ -n "$declared_path" ]] && mkdir -p "$(dirname -- "$declared_path")"
    done
    declared_path="$(plist_value "$source_plist" WorkingDirectory)"
    [[ -n "$declared_path" ]] && mkdir -p "$declared_path"

    # Step 3: rename into place -- a single same-directory rename(2), never
    # a partial-copy state a signal or a disk-full error could leave
    # behind. Cleared immediately after: from here on there is nothing left
    # for the EXIT trap to clean up for this label.
    mv -f -- "$temp_plist" "$dest_plist"
    current_temp_file=""

    # Step 4: launchctl enable clears any previous "disabled" override for
    # this label -- without it, a label a prior run or the user disabled
    # can silently fail to actually start even though bootstrap itself
    # reports success. Matches brew services' own launchctl_load, which
    # calls enable immediately before bootstrap; best-effort, since its own
    # failure is not itself informative the way bootstrap's is.
    launchctl enable "gui/$(id -u)/$label" >/dev/null 2>&1 || true
    if ! launchctl bootstrap "gui/$(id -u)" "$dest_plist"; then
      # Step 5: no rollback -- there is no backup to roll back to, and
      # brew services does not roll back either. The new plist is left in
      # place, unloaded; the exact recovery commands are printed.
      printf 'Failed to bootstrap %s from %s; the new plist is in place but not loaded. Re-run "launchd-agents.sh install --label %s" or "launchd-agents.sh remove --label %s".\n' \
        "$label" "$dest_plist" "$label" "$label" >&2
      exit 1
    fi
    printf 'Installed %s (%s)\n' "$label" "$dest_plist"
  done < <(selected_labels)
}

cmd_status() {
  # Round 3j (Codex P2 thread 8): status used to always exit 0, even when
  # every requested label's launchctl print failed -- absent (exit 113)
  # or launchd itself unavailable (any other nonzero exit) both silently
  # reported success to a caller checking only the exit code, never its
  # printed output. Any nonzero print (not just 113) counts, matching how
  # cmd_remove already treats "not confidently loaded" for the same call.
  local label print_status failed_count=0
  while IFS= read -r label; do
    printf -- '-- %s --\n' "$label"
    print_status=0
    launchctl print "gui/$(id -u)/$label" || print_status=$?
    if [[ "$print_status" != 0 ]]; then
      printf '%s: launchctl print exited %s\n' "$label" "$print_status"
      failed_count=$((failed_count + 1))
    fi
  done < <(selected_labels)
  [[ "$failed_count" -eq 0 ]]
}

# Round 3g: brew services' own `stop` (cli.rb @ 8e3a5dc0a7, roughly lines
# 229-247) boots out, then removes the service file -- no ownership file
# consulted, no ownership file updated. This mirrors that exactly, sharing
# launchctl_label_state with cmd_install so the SAME path-verified
# loaded_here/loaded_elsewhere/not_found/unknown states gate both: round 3f
# finding 1 (remove booting out an unrelated service on stale ownership
# plus a successful-but-unchecked print) is fixed by never trusting
# anything OTHER than a path-verified loaded_here to decide what is safe to
# bootout and delete.
cmd_remove() {
  local label dest_plist state removed_count=0 skipped_count=0 failed_count=0
  while IFS= read -r label; do
    dest_plist="$launch_agents_dir/$label.plist"
    state="$(launchctl_label_state "$label" "$dest_plist")"
    case "$state" in
      loaded_here)
        # bootout_and_wait absorbs EINPROGRESS (round 3i) rather than
        # refusing on it outright: teardown already under way, from this
        # or an earlier interrupted run, is not a genuine bootout failure.
        if ! bootout_and_wait "$label"; then
          case "$bootout_and_wait_result" in
            bootout_failed)
              # Kept, not deleted: a failed bootout means the plist can
              # still reload at the next login, so a retry (or remove
              # again) needs to find it right where it was.
              printf '%s: launchctl bootout failed; %s was NOT removed (it can still reload at the next login). Retry remove, or inspect launchctl print gui/%s/%s.\n' \
                "$label" "$dest_plist" "$(id -u)" "$label" >&2
              ;;
            *)
              printf '%s: launchctl bootout succeeded but the service did not report unloaded (launchctl print never returned 113) within the bounded wait; %s was NOT removed. Retry remove, or inspect launchctl print gui/%s/%s.\n' \
                "$label" "$dest_plist" "$(id -u)" "$label" >&2
              ;;
          esac
          failed_count=$((failed_count + 1))
          continue
        fi
        # Deleted, not left behind: RunAtLoad plus the plist still sitting
        # under ~/Library/LaunchAgents would make launchd reload it at the
        # next login regardless of this bootout. This removes only the
        # copied unit-definition file this script itself placed there,
        # never the component's own data or logs.
        rm -f -- "$dest_plist"
        removed_count=$((removed_count + 1))
        printf 'Booted out %s and removed %s (component data and logs kept).\n' "$label" "$dest_plist"
        ;;
      not_found)
        if [[ -e "$dest_plist" ]]; then
          # 113 is launchctl's own "Could not find service" -- genuinely
          # not loaded (already unloaded outside this script, crashed, or
          # never finished bootstrapping), so `bootout` would just fail on
          # something that is not there. Clean up directly instead.
          rm -f -- "$dest_plist"
          removed_count=$((removed_count + 1))
          printf '%s was not loaded; removed %s directly (component data and logs kept).\n' "$label" "$dest_plist"
        else
          skipped_count=$((skipped_count + 1))
          printf '%s was not loaded and %s does not exist; nothing to do.\n' "$label" "$dest_plist"
        fi
        ;;
      loaded_elsewhere)
        # Round 3f finding 1: never bootout or delete anything for a label
        # whose CURRENT loaded instance is not confirmed to be dest_plist
        # itself -- an unrelated service could hold the same label from
        # somewhere else entirely. Refuse and touch nothing.
        printf '%s: refusing to remove it -- it is loaded from somewhere other than %s; leaving it running, unmodified. Investigate launchctl print gui/%s/%s.\n' \
          "$label" "$dest_plist" "$(id -u)" "$label" >&2
        failed_count=$((failed_count + 1))
        ;;
      unknown)
        # Only exit 113 is confidently "not loaded"; any other launchctl
        # print failure is neither a safe direct cleanup nor a safe bootout
        # target. Touch nothing, rather than guess either way.
        printf '%s: refusing to remove it -- launchctl print did not confidently report loaded, not-found, or a matching path; touched nothing. Investigate launchctl print gui/%s/%s.\n' \
          "$label" "$(id -u)" "$label" >&2
        failed_count=$((failed_count + 1))
        ;;
    esac
  done < <(selected_labels)
  printf 'Booted out %s label(s); skipped %s not-installed label(s); %s failed.\n' \
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
