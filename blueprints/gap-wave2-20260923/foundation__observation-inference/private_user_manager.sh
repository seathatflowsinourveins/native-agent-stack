#!/usr/bin/env bash
# Gap 2, fix round 3 (preregistered in preregistrations.json fix_round_3.gaps.2 before this ran).
# Try a PRIVATE systemd --user in an unprivileged user+pid+mount namespace with the pipeline timer's [Timer]
# settings copied verbatim and a harmless service (appends a UTC timestamp to a marker file). Phases:
# enable+start the timer, daemon-reload, manager SIGTERM+restart; a phase counts as fired only when a new
# marker line appears after the event within 180 s. The live runtime dir /run/user/<uid> is hidden under a
# tmpfs inside the namespace, XDG_RUNTIME_DIR/HOME/XDG_* point into a temp root, DBUS_SESSION_BUS_ADDRESS is
# unset and SYSTEMD_UNIT_PATH holds only the temp unit dir, so no call can reach the live user manager.
# Usage: ecosystem-bounded-run bash private_user_manager.sh OUTPREFIX   (outer; re-execs itself inside the namespace)
# Attempt 1 (without ecosystem-bounded-run, manager as namespace root) failed: see raw/2-fr3-private-manager-diag.txt.
set -u
if [ "${1:-}" != "--inner" ] && [ "${1:-}" != "--inner2" ]; then
  OUT=$1
  ROOT=$(mktemp -d "$HOME/.cache/gap-wave2-20260923/observation-inference/private-systemd-XXXXXXXX")
  echo "outer_started=$(date -u +%FT%TZ) root=${ROOT/#$HOME/\$HOME} host_uid=$(id -u) cgroup=$(cat /proc/self/cgroup)"
  timeout 1100 unshare --user --map-root-user --pid --fork --mount-proc --mount -- /bin/bash "$0" --inner "$ROOT" "$(id -u)" "$(id -g)"
  rc=$?
  echo "inner_exit=$rc outer_stopped=$(date -u +%FT%TZ)"
  cat "$ROOT/manager.log" "$ROOT/manager.stderr" > "$OUT.manager-log.txt" 2>/dev/null
  cp "$ROOT/marker.txt" "$OUT.marker.txt" 2>/dev/null
  sed -i "s#$HOME#\$HOME#g" "$OUT".manager-log.txt "$OUT".marker.txt 2>/dev/null
  pgrep -f "$ROOT" >/dev/null && echo "LEFTOVER PROCESSES under root" || echo "no leftover processes"
  exit $rc
fi

ROOT=$2; HUID=$3; HGID=${4:-}
say() { echo "$(date -u +%FT%T.%3NZ) $*"; }
if [ "$1" = "--inner" ]; then
  say "inner pid=$$ uid_in_ns=$(id -u)"
  mount -t tmpfs -o size=1m tmpfs "/run/user/$HUID" || { say "BLOCKER: cannot hide /run/user/$HUID"; exit 3; }
  [ -e "/run/user/$HUID/systemd/private" ] && { say "BLOCKER: live manager socket still visible"; exit 3; }
  say "live runtime dir hidden: $(ls -A /run/user/$HUID | wc -l) entries visible"
  # Attempt 3: the user manager logs to /dev/console; keep it in a temp file inside this mount namespace.
  : > "$ROOT/manager.log"; mount --bind "$ROOT/manager.log" /dev/console && say "/dev/console bound to manager.log" || say "cannot bind /dev/console"
  # Attempt 2: drop to a nested user namespace mapping the host uid/gid, so the manager and systemctl share
  # one uid (the private bus only accepts its own uid) and the scope's uid-owned cgroup files are writable.
  exec unshare --user --map-user="$HUID" --map-group="$HGID" -- /bin/bash "$0" --inner2 "$ROOT" "$HUID"
fi
say "inner2 pid=$$ uid_in_ns=$(id -u) cgroup=$(cat /proc/self/cgroup)"
export HOME=$ROOT/"home" XDG_CONFIG_HOME=$ROOT/"home"/.config XDG_DATA_HOME=$ROOT/"home"/.local/share \
       XDG_STATE_HOME=$ROOT/"home"/.local/state XDG_CACHE_HOME=$ROOT/"home"/.cache XDG_RUNTIME_DIR=$ROOT/run
unset DBUS_SESSION_BUS_ADDRESS
U=$XDG_CONFIG_HOME/systemd/user
export SYSTEMD_UNIT_PATH=$U
mkdir -p "$U" "$XDG_RUNTIME_DIR" "$XDG_DATA_HOME" "$XDG_STATE_HOME" "$XDG_CACHE_HOME"; chmod 700 "$XDG_RUNTIME_DIR"
MARK=$ROOT/marker.txt; : > "$MARK"
cat > "$U/default.target" <<EOF
[Unit]
Description=private default
Wants=timers.target
EOF
# Attempt 4: user services require basic.target via default dependencies; copy the stock targets verbatim
# (unit files only, no .wants directories, so no stock service is pulled in).
for t in basic sockets paths shutdown; do cp /usr/lib/systemd/user/$t.target "$U/"; done
# Attempt 3: a user manager handles SIGTERM by starting exit.target; provide one that exits the manager.
cat > "$U/exit.target" <<EOF
[Unit]
Description=private exit
DefaultDependencies=no
SuccessAction=exit-force
EOF
cat > "$U/timers.target" <<EOF
[Unit]
Description=private timers
EOF
# [Timer] section copied verbatim from `systemctl --user cat ecosystem-native-data.timer` (2026-09-23)
cat > "$U/ecosystem-native-data.timer" <<EOF
[Unit]
Description=Refresh selected native dashboard data

[Timer]
OnBootSec=45s
OnUnitActiveSec=2min
AccuracySec=10s
Unit=ecosystem-native-data.service

[Install]
WantedBy=timers.target
EOF
# Service replaced by a harmless marker append (the real ExecStart would publish to the live stores).
cat > "$U/ecosystem-native-data.service" <<EOF
[Unit]
Description=private stand-in for ecosystem-native-data.service

[Service]
Type=oneshot
UMask=0077
TimeoutStartSec=90
ExecStart=/bin/sh -c 'date -u +%%Y-%%m-%%dT%%H:%%M:%%SZ >> $MARK'
EOF

start_mgr() {
  /usr/lib/systemd/systemd --user --log-target=console --log-level=info </dev/null >> "$ROOT/manager.stderr" 2>&1 &
  MGR=$!
  for _ in $(seq 1 100); do
    [ -S "$XDG_RUNTIME_DIR/systemd/private" ] && systemctl --user is-system-running >/dev/null 2>&1 && break
    kill -0 $MGR 2>/dev/null || { say "BLOCKER: private manager exited early (see manager.log)"; wait $MGR; say "manager exit=$?"; return 1; }
    sleep 0.2
  done
  say "manager pid=$MGR state=$(systemctl --user is-system-running 2>&1)"
}
lines() { wc -l < "$MARK"; }
wait_new() {  # $1 = label, $2 = baseline count
  local t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt 180 ]; do
    if [ "$(lines)" -gt "$2" ]; then say "PHASE $1: fired after $(( $(date +%s) - t0 )) s (marker lines $(lines))"; return 0; fi
    sleep 1
  done
  say "PHASE $1: NOT fired within 180 s"; return 1
}
state() { systemctl --user show ecosystem-native-data.timer -p UnitFileState,ActiveState,Result,LastTriggerUSec,NextElapseUSecMonotonic 2>&1 | tr '\n' ' '
  echo -n "| service: "; systemctl --user show ecosystem-native-data.service -p ActiveState,Result,ExecMainCode,ExecMainStatus,NRestarts 2>&1 | tr '\n' ' '; echo; }
stop_mgr() {  # SIGTERM, bounded 30 s, then SIGKILL (recorded)
  kill -TERM $MGR; local t0=$(date +%s)
  while kill -0 $MGR 2>/dev/null && [ $(( $(date +%s) - t0 )) -lt 30 ]; do sleep 0.5; done
  if kill -0 $MGR 2>/dev/null; then kill -KILL $MGR; say "manager did not exit on SIGTERM within 30 s; SIGKILL sent"; fi
  wait $MGR; say "manager stop exit=$?"; }

start_mgr || exit 4
systemctl --user enable ecosystem-native-data.timer 2>&1 | sed "s#$ROOT#<root>#g"
systemctl --user start ecosystem-native-data.timer 2>&1
say "after enable+start: $(state)"
R=0
wait_new enable-start 0 || R=1
say "after phase enable-start: $(state)"
b=$(lines); systemctl --user daemon-reload 2>&1; say "daemon-reload issued; $(state)"
wait_new daemon-reload "$b" || R=1
say "after phase daemon-reload: $(state)"
b=$(lines); stop_mgr; sleep 1
start_mgr || exit 4
say "after manager restart: $(state)"
wait_new manager-restart "$b" || R=1
say "marker: $(tr '\n' ' ' < "$MARK")"
systemctl --user list-timers --all --no-pager 2>&1 | sed "s#$ROOT#<root>#g"
systemctl --user status ecosystem-native-data.service --no-pager -l 2>&1 | sed "s#$ROOT#<root>#g" | head -20
stop_mgr
exit $R
