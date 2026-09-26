# shellcheck shell=bash
# Sourced by the shell drivers here (added after the recorded runs; the as-run drivers are in as-run/).
# The drivers delete and rewrite paths under the WORK directory they are given, so they only accept a
# WORK they may own: a path that does not exist, an empty directory, or a directory holding the marker
# file that mark_work writes into every WORK a driver creates. Anything else ends the driver with exit
# status 2 before it deletes, downloads or writes anything. So does a WORK that begins with '-', which
# rm, mkdir and find would read as an option (pass ./-name for such a directory). Each driver sources
# this file with `|| exit 2` and calls claim_work with `|| exit 2`, so a driver copied without this file
# stops too.

work_marker=.bootstrap-integrity-work

claim_work() {  # claim_work DIR: return if the drivers may delete and rewrite DIR, else exit 2
  local dir="$1" listed entry
  if [[ -z "$dir" ]]; then
    echo "refusing: WORK is an empty string" >&2
    exit 2
  fi
  if [[ "$dir" == -* ]]; then
    echo "refusing: WORK begins with '-', which rm, mkdir and find read as an option: $dir (pass ./$dir)" >&2
    exit 2
  fi
  if [[ -L "$dir" ]]; then
    echo "refusing: WORK is a symbolic link: $dir" >&2
    exit 2
  fi
  if [[ ! -e "$dir" ]]; then
    return 0
  fi
  if [[ ! -d "$dir" ]]; then
    echo "refusing: WORK exists and is not a directory: $dir" >&2
    exit 2
  fi
  if [[ -f "$dir/$work_marker" && ! -L "$dir/$work_marker" ]]; then
    return 0
  fi
  # find takes a lone '!' or '(' as part of its expression, not as a path, so a relative WORK is listed
  # as ./WORK. A listing that fails (no find, no permission) refuses too: an unreadable directory is not
  # empty.
  listed="$dir"
  [[ "$listed" == /* ]] || listed="./$listed"
  if [[ ! -r "$dir" || ! -x "$dir" ]] || ! entry="$(find "$listed" -mindepth 1 -maxdepth 1 -print -quit)"; then
    echo "refusing: WORK cannot be listed: $dir" >&2
    exit 2
  fi
  if [[ -n "$entry" ]]; then
    echo "refusing: WORK is not empty and holds no $work_marker, so no driver here created it: $dir" >&2
    echo "Pass a new or empty directory." >&2
    exit 2
  fi
}

mark_work() {  # mark_work DIR: record that a driver created DIR, so a later run may replace it
  : >"$1/$work_marker"
}
