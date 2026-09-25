#!/usr/bin/env bash
# Open a new terminal window for credential work that must never pass through an agent,
# a chat, a command line or shell history.
#
#   tools/credentials/open_credential_terminal.sh <entry-id>        # store or rotate a stored key
#   tools/credentials/open_credential_terminal.sh alpaca-paper --probe
#                                   # store the paper pair, then probe its rate limit
#   ... --dry-run                   # print the plan and the generated session script; open nothing
#
# Live broker keys are out of scope for this repository and are never handled here.
#
# The window runs a generated session script that holds commands only, never values. The
# script lives in the private state directory (mode 0700) and deletes itself on exit. Before
# anything is typed it prints the checkout's commit and refuses if the credential tools have
# uncommitted changes, so the code you type into is the committed code.
set -euo pipefail

usage="usage: open_credential_terminal.sh <entry-id> [--probe] [--dry-run]"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
entry=""; probe=0; dry_run=0
while [ $# -gt 0 ]; do
  case "$1" in
    --probe) probe=1; shift ;;
    --dry-run) dry_run=1; shift ;;
    -*) echo "$usage" >&2; exit 2 ;;
    *) [ -z "$entry" ] || { echo "$usage" >&2; exit 2; }; entry="$1"; shift ;;
  esac
done
[[ "$entry" =~ ^[a-z0-9-]+$ ]] || { echo "$usage" >&2; exit 2; }
[ "$probe" -eq 0 ] || [ "$entry" = alpaca-paper ] || { echo "--probe applies only to alpaca-paper" >&2; exit 2; }

safe_path='^[A-Za-z0-9._/-]+$'
state="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
session="$state/credential-sessions/session-$stamp-$$.sh"
result=""
if [ "$probe" -eq 1 ]; then result="$state/rate-limit/paper-$stamp.json"; fi
for p in "$root" "$state" "$session" ${result:+"$result"}; do
  [[ "$p" =~ $safe_path ]] || { echo "refused: path has characters a launcher cannot pass safely: $p" >&2; exit 2; }
done
install -d -m 700 "$state" "$state/credential-sessions"
find "$state/credential-sessions" -maxdepth 1 -name 'session-*.sh' -mmin +1440 -delete 2>/dev/null || true

umask 077
{
  echo '#!/usr/bin/env bash'
  echo 'set -u'
  echo 'unset PYTHONPATH PYTHONHOME PYTHONSTARTUP BASH_ENV ENV LD_PRELOAD LD_LIBRARY_PATH'
  echo "trap 'rm -f -- $session' EXIT"
  echo "cd $root || exit 1"
  echo 'echo "native-agent-stack: credential work outside any agent or chat"'
  echo 'if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then'
  echo '  echo "checkout: $(git rev-parse --short HEAD) ($(pwd))"'
  echo '  if [ -n "$(git status --porcelain -- tools/credentials scripts/credential_status.py adoption/credential-inventory.json)" ]; then'
  echo '    echo "refused: the credential tools have uncommitted changes in this checkout."'
  echo '    read -r -p "Press Enter to close this window. " _; exit 1'
  echo '  fi'
  echo 'else'
  echo '  echo "warning: not a git checkout, so these tools cannot be checked for local edits."'
  echo '  echo "Prefer running from a clone of the default branch."'
  echo 'fi'
  echo 'echo'
  echo "python3 -I tools/credentials/set_credential.py $entry"
  if [ "$probe" -eq 1 ]; then
    echo 'if [ $? -eq 0 ]; then'
    echo '  echo; echo "Read-only paper rate-limit probe (one GET /v2/account; no orders):"'
    echo "  python3 -I tools/credentials/alpaca_rate_limit_probe.py --out $result"
    echo 'fi'
  fi
  echo 'echo'
  echo 'read -r -p "Done. Press Enter to close this window. " _'
} > "$session"
chmod 700 "$session"

launch=(); launch_dir="${TMPDIR:-/tmp}"
if grep -qi microsoft /proc/version 2>/dev/null && [ -x /mnt/c/Windows/System32/cmd.exe ] \
   && [[ "${WSL_DISTRO_NAME:-}" =~ ^[A-Za-z0-9._-]+$ ]] && [[ "$(id -un)" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  launch_dir=/mnt/c
  wsl_args=(wsl.exe -d "$WSL_DISTRO_NAME" -u "$(id -un)" --exec bash "$session")
  if (cd /mnt/c && /mnt/c/Windows/System32/cmd.exe /c where wt.exe) >/dev/null 2>&1; then
    launch=(/mnt/c/Windows/System32/cmd.exe /c start "" wt.exe -w new "${wsl_args[@]}")
  else
    launch=(/mnt/c/Windows/System32/cmd.exe /c start "" "${wsl_args[@]}")
  fi
elif [ "$(uname -s)" = Darwin ]; then
  launch=(osascript -e 'on run argv' -e 'tell application "Terminal"'
          -e 'do script "bash " & quoted form of (item 1 of argv)' -e 'activate'
          -e 'end tell' -e 'end run' "$session")
elif [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  for term in x-terminal-emulator gnome-terminal konsole xterm; do
    if command -v "$term" >/dev/null 2>&1; then
      case "$term" in
        gnome-terminal) launch=(gnome-terminal -- bash "$session") ;;
        *) launch=("$term" -e bash "$session") ;;
      esac
      break
    fi
  done
fi

if [ "$dry_run" -eq 1 ]; then
  echo "mode: store $entry$([ "$probe" -eq 1 ] && echo ' + paper rate-limit probe')"
  echo "session script: $session"
  [ -z "$result" ] || echo "probe result: $result"
  if [ ${#launch[@]} -gt 0 ]; then printf 'would launch:'; printf ' %q' "${launch[@]}"; echo; else echo "would print: bash $session"; fi
  echo "--- session script ---"
  cat "$session"
  rm -f -- "$session"
  exit 0
fi

manual() { echo "Run this in your own terminal instead:"; echo "  bash $session"; }
if [ ${#launch[@]} -eq 0 ]; then
  echo "No desktop terminal found."; manual; exit 0
fi
confirmed=1
case "${launch[0]}" in
  gnome-terminal|x-terminal-emulator|konsole|xterm)
    # X terminals block until closed, so they run in the background and cannot be confirmed here.
    (cd "$launch_dir" && "${launch[@]}") >/dev/null 2>&1 & disown; rc=0; confirmed=0 ;;
  *) set +e; (cd "$launch_dir" && "${launch[@]}") >/dev/null 2>&1; rc=$?; set -e ;;
esac
if [ "$rc" -ne 0 ]; then
  echo "Could not open a terminal window (exit $rc)."; manual; exit 1
fi
if [ "$confirmed" -eq 1 ]; then
  echo "Opened a terminal window. Type the values there; nothing is shown here."
else
  echo "Asked the desktop to open a terminal window. If none appears:"; manual
fi
[ -z "$result" ] || echo "The non-secret probe result will be written to: $result"
