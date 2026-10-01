#!/usr/bin/env bash
# Read-only production fingerprint. Usage: snapshot.sh OUTDIR
set -u
O="$1"; mkdir -p "$O"
E="$HOME/.local/share/codex-ecosystem"
date -u +%Y-%m-%dT%H:%M:%SZ > "$O/at_utc.txt"
# (a) refuter's 7-file stat of the live headroom workspace (missing files print nothing)
( cd "$HOME/.headroom" 2>/dev/null && stat -c '%n %s %Y' ccr_store.db ccr_store.db-wal ccr_store.db-shm savings_events.jsonl session_stats.jsonl update_check.json config/install_id 2>/dev/null ) > "$O/headroom7.txt"
# (b) full ~/.headroom tree: relative name, type, size, mtime, mode (no content read)
find "$HOME/.headroom" -printf '%P\t%y\t%s\t%T@\t%m\n' 2>/dev/null | sort > "$O/headroom_tree.tsv"
# (c) pinned 0.37.0 uv tool env: every entry with size+mtime+mode
find "$E/python-tools/headroom-ai" -printf '%P\t%y\t%s\t%T@\t%m\n' | sort > "$O/pinned_prefix.tsv"
# (d) shared bin dir: names, types, symlink targets
find "$E/bin" -maxdepth 1 -printf '%P\t%y\t%l\n' | sort > "$O/bin.tsv"
readlink "$E/bin/headroom" > "$O/bin_headroom_link.txt"
# (e) tools dir top level
find "$E/tools" -maxdepth 1 -mindepth 1 -printf '%P\n' | sort > "$O/tools_top.txt"
# (f) uv-managed pythons
find "$HOME/.local/share/uv/python" -maxdepth 1 -mindepth 1 -printf '%P\t%y\t%l\n' | sort > "$O/uv_pythons.tsv"
# (g) running user services with their invocation ids (restart would change the id)
systemctl --user list-units --type=service --state=running --no-legend --plain 2>/dev/null | awk '{print $1}' | sort | while read -r u; do printf '%s\t%s\n' "$u" "$(systemctl --user show -p InvocationID --value "$u")"; done > "$O/user_services.tsv"
# (h) headroom processes (bracketed to avoid self-match)
ps -eo pid=,ppid=,etimes=,args= | grep -E '[b]in/headroom (mcp|--version|savings|telemetry)' > "$O/headroom_procs.txt" 2>/dev/null || true
for f in headroom7.txt headroom_tree.tsv pinned_prefix.tsv bin.tsv tools_top.txt uv_pythons.tsv user_services.tsv; do printf '%s\t%s\t%s\n' "$f" "$(wc -l < "$O/$f")" "$(sha256sum < "$O/$f" | cut -c1-16)"; done > "$O/summary.tsv"
cat "$O/summary.tsv"
