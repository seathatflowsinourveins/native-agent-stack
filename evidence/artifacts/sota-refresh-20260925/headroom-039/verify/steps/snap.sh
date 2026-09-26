#!/usr/bin/env bash
# Verifier's read-only production fingerprint. Usage: snap.sh OUTDIR
set -u
O="$1"; mkdir -p "$O"
E="$HOME/.local/share/codex-ecosystem"
date -u +%Y-%m-%dT%H:%M:%SZ > "$O/at_utc.txt"
( cd "$HOME/.headroom" 2>/dev/null && stat -c '%n %s %Y' ccr_store.db ccr_store.db-wal ccr_store.db-shm savings_events.jsonl session_stats.jsonl update_check.json config/install_id 2>/dev/null ) > "$O/headroom7.txt"
find "$HOME/.headroom" -printf '%P\t%y\t%s\t%T@\t%m\n' 2>/dev/null | sort > "$O/headroom_tree.tsv"
find "$E/python-tools/headroom-ai" -printf '%P\t%y\t%s\t%T@\t%m\n' | sort > "$O/pinned_prefix.tsv"
find "$E/tools/headroom-ai-0.39.0" -printf '%P\t%y\t%s\t%T@\t%m\t%l\n' | sort > "$O/candidate_prefix.tsv"
find "$E/bin" -maxdepth 1 -printf '%P\t%y\t%l\n' | sort > "$O/bin.tsv"
readlink "$E/bin/headroom" > "$O/bin_headroom_link.txt"
find "$E/tools" -maxdepth 1 -mindepth 1 -printf '%P\n' | sort > "$O/tools_top.txt"
find "$HOME/.local/share/uv/python" -maxdepth 1 -mindepth 1 -printf '%P\t%y\t%l\n' | sort > "$O/uv_pythons.tsv"
systemctl --user list-units --type=service --state=running --no-legend --plain 2>/dev/null | awk '{print $1}' | sort | while read -r u; do printf '%s\t%s\n' "$u" "$(systemctl --user show -p InvocationID --value "$u")"; done > "$O/user_services.tsv"
systemctl --user list-units --type=service --state=running --no-legend --plain 2>/dev/null | awk '{print $1}' | sort | while read -r u; do printf '%s\t%s\t%s\n' "$u" "$(systemctl --user show -p ActiveEnterTimestamp --value "$u")" "$(systemctl --user show -p MainPID --value "$u")"; done > "$O/user_services_start.tsv"
find "$HOME/.config/systemd/user" -printf '%P\t%y\t%s\t%T@\t%l\n' 2>/dev/null | sort > "$O/systemd_user_units.tsv"
for f in "$HOME/.claude/settings.json" "$HOME/.claude/settings.local.json" "$HOME/.codex/config.toml" "$HOME/code/native-agent-stack/.claude/settings.json" "$HOME/code/native-agent-stack/.claude/settings.local.json" "$HOME/.claude.json"; do
  if [ -e "$f" ]; then printf '%s\t%s\t%s\n' "${f/#$HOME/~}" "$(stat -c '%s %Y' "$f")" "$(date -u -d @"$(stat -c %Y "$f")" +%Y-%m-%dT%H:%M:%SZ)"; else printf '%s\tabsent\n' "${f/#$HOME/~}"; fi
done > "$O/config_stats.tsv"
ps -eo pid=,ppid=,etimes=,args= | grep -E '[h]eadroom' | grep -v -E 'snap.sh|grep' > "$O/headroom_procs.txt" 2>/dev/null || true
for f in headroom7.txt headroom_tree.tsv pinned_prefix.tsv candidate_prefix.tsv bin.tsv tools_top.txt uv_pythons.tsv user_services.tsv systemd_user_units.tsv; do printf '%s\t%s\t%s\n' "$f" "$(wc -l < "$O/$f")" "$(sha256sum < "$O/$f" | cut -c1-16)"; done > "$O/summary.tsv"
cat "$O/summary.tsv"
