#!/usr/bin/env bash
# Gap 2 fix round 3 diagnosis: why does a private `systemd --user` exit 1 silently in an unprivileged
# namespace? Runs it once under strace (strace 6.8 extracted from the Ubuntu noble .deb into the cache dir,
# not installed) and prints the failing syscalls. Same isolation as private_user_manager.sh.
# Usage: private_user_manager_diag.sh STRACE_BIN
set -u
ST=$1
if [ "${2:-}" != "--inner" ]; then
  D=$(mktemp -d "$HOME/.cache/gap-wave2-20260923/observation-inference/private-systemd-diag-XXXXXXXX")
  echo "started=$(date -u +%FT%TZ) cgroup_of_caller=$(cat /proc/self/cgroup) cgroup_dir_owner=$(stat -c %U:%G /sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup))"
  timeout 60 unshare --user --map-root-user --pid --fork --mount-proc --mount -- /bin/bash "$0" "$ST" --inner "$D"
  echo "stopped=$(date -u +%FT%TZ)"
  echo "--- failing syscalls (EACCES/EPERM) and exit, from strace -f:"
  grep -E 'EACCES|EPERM|exit_group' "$D/st.txt" | sed -E "s#$HOME#\$HOME#g; s#^[0-9]+ +##"
  exit 0
fi
D=$3
mount -t tmpfs tmpfs /run/user/1000
export HOME=$D XDG_RUNTIME_DIR=$D/run XDG_CONFIG_HOME=$D/cfg SYSTEMD_UNIT_PATH=$D/cfg/systemd/user
unset DBUS_SESSION_BUS_ADDRESS
mkdir -p "$D/run" "$D/cfg/systemd/user"; chmod 700 "$D/run"
printf '[Unit]\nDescription=private default\n' > "$D/cfg/systemd/user/default.target"
for mode in ns-root nested-uid1000; do
  if [ $mode = ns-root ]; then pre=(); else pre=(unshare --user --map-user=1000 --map-group=1000 --); fi
  timeout 8 "${pre[@]}" "$ST" -f -o "$D/st-$mode.txt" /usr/lib/systemd/systemd --user --log-target=console --log-level=debug </dev/null
  echo "mode=$mode systemd_exit=$?"
  { echo "## $mode"; cat "$D/st-$mode.txt"; } >> "$D/st.txt"
done
