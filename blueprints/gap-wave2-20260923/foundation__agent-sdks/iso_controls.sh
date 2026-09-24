#!/usr/bin/env bash
# Round 3, gap 2: deterministic reachability controls (no model). Run once outside and once inside
# iso_ns.sh; the outside run is the positive control. Usage: iso_controls.sh PORT TOKEN
# It never starts a host MCP server: outside, start.mjs is only tested for existence.
PORT=$1; TOKEN=$2
CM="$HOME/.codex/plugins/cache/context-mode/context-mode/1.0.169/start.mjs"
j() { printf '{"check":"%s","result":"%s"}\n' "$1" "$2"; }
m=$(command -v mcporter 2>/dev/null) && j mcporter_on_path "yes:${m/#$HOME/\$HOME}" || j mcporter_on_path no
[ -e "$CM" ] && j context_mode_start_mjs exists || j context_mode_start_mjs absent
n=$(find "$HOME" -maxdepth 9 -name start.mjs -path '*context-mode*' 2>/dev/null | wc -l); j context_mode_start_mjs_found_under_home "$n"
[ -e "$HOME/.codex/AGENTS.md" ] && j codex_home_agents_md exists || j codex_home_agents_md absent
[ -e "$HOME/.claude" ] && j claude_dir exists || j claude_dir absent
[ -e "$HOME/code/agent-lab" ] && j agent_lab_checkout exists || j agent_lab_checkout absent
[ -e "$HOME/.local/share/codex-ecosystem/bin" ] && j ecosystem_bin exists || j ecosystem_bin absent
[ -e /mnt/c/Users ] && j windows_drive exists || j windows_drive absent
[ -e /run/user/1000/bus ] && j user_bus exists || j user_bus absent
r=$(curl -s --max-time 3 "http://127.0.0.1:$PORT/" 2>/dev/null); [ "$r" = "$TOKEN" ] && j own_loopback_listener reached || j own_loopback_listener unreachable
j process_count "$(ls -d /proc/[0-9]* | wc -l)"
if [ ! -e "$CM" ]; then node "$CM" </dev/null >/dev/null 2>&1; j node_start_mjs_exit "$?"; fi
