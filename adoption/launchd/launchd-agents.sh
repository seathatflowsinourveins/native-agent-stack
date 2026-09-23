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
    '      label as one this script itself enabled.' \
    '  status  [--label ID ...]' \
    '      launchctl print each selected label in the current GUI session.' \
    '  remove  [--label ID ...]' \
    '      launchctl bootout each selected label, but only one this script' \
    '      itself recorded as enabled (never one it did not install); never' \
    '      deletes data, logs, or the copied plist file.' \
    '' \
    'Labels (no trailing .plist), default: every one of the three below.' \
    '  com.native-stack.qdrant' \
    '  com.native-stack.ai-memory' \
    '  com.native-stack.llama-embed'
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
    for label in "${all_labels[@]}"; do
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

cmd_install() {
  [[ -d "$render_dir" ]] || {
    printf 'Nothing rendered yet at %s; run the render subcommand first.\n' "$render_dir" >&2
    exit 1
  }
  mkdir -p "$launch_agents_dir"
  local label source_plist dest_plist
  while IFS= read -r label; do
    source_plist="$render_dir/$label.plist"
    [[ -f "$source_plist" ]] || {
      printf 'No rendered plist for %s at %s; run the render subcommand first.\n' "$label" "$source_plist" >&2
      exit 1
    }
    dest_plist="$launch_agents_dir/$label.plist"
    cp -- "$source_plist" "$dest_plist"
    launchctl bootstrap "gui/$(id -u)" "$dest_plist"
    record_enabled_label "$label"
    printf 'Installed and bootstrapped %s (%s)\n' "$label" "$dest_plist"
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
  local label removed_count=0 skipped_count=0
  while IFS= read -r label; do
    if is_enabled_label "$label"; then
      launchctl bootout "gui/$(id -u)/$label" || printf '%s: launchctl bootout exited %s (already unloaded?)\n' "$label" "$?" >&2
      forget_enabled_label "$label"
      removed_count=$((removed_count + 1))
      printf 'Booted out %s (data and logs kept; the copied plist under %s is kept too).\n' "$label" "$launch_agents_dir"
    else
      printf '%s was not enabled by this script; skipping (never removes a label it did not install).\n' "$label" >&2
      skipped_count=$((skipped_count + 1))
    fi
  done < <(selected_labels)
  printf 'Booted out %s label(s); skipped %s not-enabled label(s).\n' "$removed_count" "$skipped_count"
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
