#!/bin/sh
# Trial-owned host state cleanup for the 2026-09-26 P1 trial batch (ByteRover CLI, MIRIX, ColPali).
#
# Usage: sh host-cleanup.sh plan|apply <log-dir>
#
# Acts only on the literal targets listed below, after asserting what each one is. `plan` prints the
# assertions and changes nothing. `apply` runs ByteRover's own lifecycle commands first (providers
# disconnect, logout, restart), then `npm uninstall --global --prefix`, then removes the literal
# ByteRover state paths, the two /tmp alias symlinks, and stops the three orphaned MIRIX trial servers
# with SIGTERM. Credential files are only stat-ed (name, size, mtime), never read.
set -u
mode=${1:?plan|apply}
logdir=${2:?log dir}
mkdir -p "$logdir"
log="$logdir/cleanup-$mode.log"
: > "$log"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$log"; }
fail() { say "ABORT: $*"; exit 1; }

PREFIX="$HOME/.local/share/codex-ecosystem/tools/byterover-cli-3.16.1"
BINLINK="$HOME/.local/share/codex-ecosystem/bin/brv"
BRV="$PREFIX/bin/brv"
STATE_DIRS="$HOME/.config/brv $HOME/.local/share/brv $HOME/.local/state/brv $HOME/.cache/brv"
NOTIFIER_FILE="$HOME/.config/configstore/update-notifier-byterover-cli.json"
CONFIGSTORE_DIR="$HOME/.config/configstore"
ALIASES="/tmp/nas-mirix-trial /tmp/nas-colpali-trial"
SCRATCH=<scratch>
# pid:port:expected cwd suffix
MIRIX_SERVERS="2657580:18531:trial-mirix/mirix-src 2823903:18000:trial-mirix/mirix-src 2853428:18533:trial-mirix/mirix-main-src"

export DO_NOT_TRACK=1 NO_UPDATE_NOTIFIER=1 npm_config_update_notifier=false BRV_DISABLE_AUTOUPDATE=1 \
  MCP_AUTO_OPEN_ENABLED=false BRV_ENV=production

listing() {  # names, types, sizes and mtimes only
  for target in "$@"; do
    if [ -e "$target" ] || [ -L "$target" ]; then
      find "$target" -printf '%y %s %TY-%Tm-%TdT%TH:%TM %p\n' 2>/dev/null | sort -k4 | sed "s#$HOME#~#g"
    else
      echo "absent $target" | sed "s#$HOME#~#g"
    fi
  done
}

say "mode=$mode"
say "== assertions"
[ -d "$PREFIX" ] || fail "npm prefix missing"
[ -x "$BRV" ] || fail "brv binary missing in the prefix"
"$BRV" --version >> "$log" 2>&1 || fail "brv --version failed"
[ -L "$BINLINK" ] || fail "bin link is not a symlink"
[ "$(readlink "$BINLINK")" = "$BRV" ] || fail "bin link does not point at the prefix's brv"
for dir in $STATE_DIRS; do [ -d "$dir" ] || fail "state dir missing: $dir"; done
[ -f "$NOTIFIER_FILE" ] || fail "update-notifier file missing"
for alias in $ALIASES; do
  [ -L "$alias" ] || fail "$alias is not a symlink"
  case "$(readlink "$alias")" in "$SCRATCH"/trial-*) ;; *) fail "$alias points outside the trial scratch dirs" ;; esac
done
for entry in $MIRIX_SERVERS; do
  pid=${entry%%:*}; rest=${entry#*:}; port=${rest%%:*}; suffix=${rest#*:}
  [ -d "/proc/$pid" ] || fail "MIRIX server pid $pid is gone"
  cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline")
  case "$cmd" in "python scripts/start_server.py --port $port "*) ;; *) fail "pid $pid is not the port-$port MIRIX server: $cmd" ;; esac
  [ "$(readlink "/proc/$pid/cwd")" = "$SCRATCH/$suffix" ] || fail "pid $pid cwd is not $suffix"
  say "pid $pid: $cmd (cwd <scratch>/$suffix)"
done
say "all literal targets asserted"
say "== before"
listing "$PREFIX/bin" "$BINLINK" $STATE_DIRS "$NOTIFIER_FILE" "$CONFIGSTORE_DIR" $ALIASES >> "$log"
du -sh "$PREFIX" $STATE_DIRS 2>/dev/null | sed "s#$HOME#~#g" >> "$log"
ps -eo pid,etimes,cmd | grep -E 'start_server.py|brv-server|agent-process|autoupdate' | grep -v grep | sed "s#$HOME#~#g" >> "$log"
if [ "$mode" != apply ]; then say "plan only; nothing changed"; exit 0; fi

say "== ByteRover lifecycle commands (from a throwaway cwd)"
cwd=$(mktemp -d)
( cd "$cwd" && timeout 180 "$BRV" providers disconnect openai-compatible --format json ) >> "$log" 2>&1; say "providers disconnect exit=$?"
( cd "$cwd" && timeout 120 "$BRV" logout --format json ) >> "$log" 2>&1; say "logout exit=$?"
( cd "$cwd" && timeout 120 "$BRV" restart ) >> "$log" 2>&1; say "restart exit=$?"
rm -rf "$cwd"
sleep 2
procs=$(ps -eo pid,cmd | grep -E 'brv-server|agent-process|brv update' | grep -v grep)
if [ -n "$procs" ]; then echo "$procs" | sed "s#$HOME#~#g" >> "$log"; say "WARNING: ByteRover processes still running"; else say "no ByteRover processes running"; fi

say "== npm uninstall"
npm uninstall --global --no-audit --no-fund --prefix "$PREFIX" byterover-cli >> "$log" 2>&1; say "npm uninstall exit=$?"
[ -e "$BRV" ] && fail "brv binary still present after npm uninstall"
rm "$BINLINK" && say "removed symlink ~/.local/share/codex-ecosystem/bin/brv"
say "left in the prefix after npm uninstall:"; find "$PREFIX" -printf '%y %s %P\n' | sed "s#$HOME#~#g" >> "$log"
find "$PREFIX" -depth -type d -empty -delete
if [ -e "$PREFIX" ]; then say "WARNING: prefix still holds files (listed above); not removed"; else say "prefix removed (only empty directories were left)"; fi

say "== ByteRover state paths"
for dir in $STATE_DIRS; do rm -rf "$dir" && say "removed $(echo "$dir" | sed "s#$HOME#~#")"; done
rm "$NOTIFIER_FILE" && say "removed ~/.config/configstore/update-notifier-byterover-cli.json"
rmdir "$CONFIGSTORE_DIR" 2>/dev/null && say "removed empty ~/.config/configstore" || say "kept ~/.config/configstore (not empty)"

say "== /tmp alias symlinks"
for alias in $ALIASES; do rm "$alias" && say "removed symlink $alias"; done

say "== MIRIX trial servers (SIGTERM)"
for entry in $MIRIX_SERVERS; do pid=${entry%%:*}; kill -TERM "$pid" && say "SIGTERM sent to $pid"; done
for i in 1 2 3 4 5 6 7 8 9 10; do
  alive=""; for entry in $MIRIX_SERVERS; do pid=${entry%%:*}; [ -d "/proc/$pid" ] && alive="$alive $pid"; done
  [ -z "$alive" ] && break; sleep 1
done
[ -n "$alive" ] && say "WARNING: still alive after 10 s:$alive" || say "all three MIRIX servers exited"

say "== after"
listing "$PREFIX" "$BINLINK" $STATE_DIRS "$NOTIFIER_FILE" "$CONFIGSTORE_DIR" $ALIASES >> "$log"
ports=$(ss -ltn 2>/dev/null | grep -E ':(18531|18000|18533|7700)\b')
if [ -n "$ports" ]; then echo "$ports" >> "$log"; say "WARNING: a trial port is still listening"; else say "ports 18531, 18000, 18533 and 7700 are closed"; fi
procs=$(ps -eo pid,cmd | grep -E 'start_server.py|brv-server|agent-process' | grep -v grep)
if [ -n "$procs" ]; then echo "$procs" | sed "s#$HOME#~#g" >> "$log"; say "WARNING: trial server processes remain"; else say "no trial server processes"; fi
command -v brv >> "$log" 2>&1 && say "WARNING: brv still on PATH" || say "brv no longer on PATH"
say "done"
