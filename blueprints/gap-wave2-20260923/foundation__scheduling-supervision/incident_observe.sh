#!/usr/bin/env bash
# Fix round 2: read-only observation for incident-1. No writes to the live Dagu tree.
set -u
D="$HOME/.local/share/dagu/data"
echo "== date"; date -Iseconds
echo "== ps 366"; ps -o pid,ppid,lstart,user,args -p 366
echo "== cmdline 366"; tr '\0' ' ' < /proc/366/cmdline; echo
echo "== cwd 366"; readlink /proc/366/cwd
echo "== environ 366 (filtered: only HOME, XDG_*, DAGU_*HOME*/DIR*/PATH*/CONFIG*; all other names and values suppressed)"
tr '\0' '\n' < /proc/366/environ | grep -E '^(HOME|XDG_[A-Z_]+|DAGU_[A-Z_]*(HOME|DIR|PATH|CONFIG)[A-Z_]*)=' || echo "(no matching variable)"
echo "== environ 366 variable count, and count of DAGU_* names (names/values not printed)"
tr '\0' '\n' < /proc/366/environ | wc -l; tr '\0' '\n' < /proc/366/environ | grep -c '^DAGU_' || true
echo "== open fds of 366 pointing into dagu trees"
for f in /proc/366/fd/*; do l=$(readlink "$f" 2>/dev/null); case "$l" in *dagu*) echo "$f -> $l";; esac; done
echo "== open fd count"; ls /proc/366/fd | wc -l
echo "== maps of 366 mentioning dagu (files only)"; grep -o '/[^ ]*dagu[^ ]*' /proc/366/maps | sort -u
echo "== listeners of 366"; ss -Hltnp 2>/dev/null | grep 'pid=366,' || echo "(none visible)"
echo "== config files"; ls -la "$HOME/.config/dagu" 2>&1; for c in "$HOME/.config/dagu/config.yaml" "$HOME/.config/dagu/base.yaml"; do [ -f "$c" ] && { echo "-- $c (keys only)"; grep -oE '^[A-Za-z_]+:' "$c"; }; done
echo "== birth/modify times of the 28 incident paths (%w birth, %y mtime)"
for p in "" dag-settings notifications notifications/channels notifications/dags notifications/routes notifications/routes/workspaces notifications/monitor-state.json notifications/monitor-state.json.lock notifications/monitor-state.json.lock.flock incidents incidents/providers incidents/policies incidents/policies/dags incidents/policies/workspaces incidents/states incidents/monitor-state.json incidents/monitor-state.json.lock incidents/monitor-state.json.lock.flock service-registry service-registry/scheduler scheduler scheduler/state.json scheduler/checkpoint.json scheduler/locks scheduler/.dagu_record_locks scheduler/.dagu_record_locks/4b scheduler/.dagu_record_locks/47; do
  t="$D/$p"; stat -c 'birth=%w | mtime=%y | %F | %n' "$t" 2>&1
done
echo "== top-level of data dir with birth times"
for t in "$D"/*; do stat -c 'birth=%w | mtime=%y | %F | %n' "$t"; done
echo "== any path under data dir born or modified since 2026-09-22 23:26:00 (to see later activity by pid 366)"
find "$D" -newermt "2026-09-22 23:26:00" -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' 2>/dev/null | sort | head -100
echo "== current checkpoint.json"; cat "$D/scheduler/checkpoint.json" 2>&1; echo
echo "== end"; date -Iseconds
