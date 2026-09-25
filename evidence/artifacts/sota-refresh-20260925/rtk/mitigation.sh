#!/usr/bin/env bash
# Scratch test of candidate [hooks] exclude_commands mitigations through the real hook JSON path.
# Uses a scratch XDG_CONFIG_HOME (never ~/.config/rtk) and scratch data dirs.
set -u
IMPL=$(cd "$(dirname "$0")" && pwd); S="$HOME/.local/share/codex-ecosystem"
FX=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["FX"])' "$IMPL/out/a2/a2-paths.json")
M=$(mktemp -d "$IMPL/tmp/mitig.XXXXXX"); trap 'rm -rf "$M"' EXIT
mkdir -p "$M/config/rtk"
printf '%s\n' '[hooks]' 'exclude_commands = ["^git show [^ ]*:", "diff"]' > "$M/config/rtk/config.toml"
cat "$M/config/rtk/config.toml"
decide() { # ver cwd cmd -> prints rewrite or SILENT, plus hook rc
  local v=$1 cwd=$2 cmd=$3 out rc
  out=$(cd "$cwd" && python3 -c 'import json,os,sys;print(json.dumps({"session_id":"sota-refresh-rtk-mitig","tool_use_id":"sota-refresh-rtk-mitig-1","cwd":os.getcwd(),"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$cmd" \
      | env XDG_CONFIG_HOME="$M/config" XDG_DATA_HOME="$M/data-$v" RTK_DB_PATH="$M/data-$v/history.db" RTK_TELEMETRY_DISABLED=1 "$S/tools/rtk-$v/rtk" hook claude 2>"$M/err"); rc=$?
  if [ -n "$out" ]; then R=$(printf '%s' "$out" | python3 -c 'import json,sys;print(json.load(sys.stdin)["hookSpecificOutput"]["updatedInput"]["command"])'); else R=""; fi
  printf '  %-6s hook_rc=%s %-45s -> %s\n' "$v" "$rc" "[$cmd]" "${R:-SILENT(native)}"
}
for v in 0.49.0 0.50.0; do
  echo "## $v with mitigation config"
  decide $v "$FX/repo" "git show HEAD:big.txt | tail -n 5"
  decide $v "$FX/repo" "git show HEAD:big.txt"
  decide $v "$FX/repo" "git show HEAD~2"
  decide $v "$FX/repo" "git show --stat HEAD"
  decide $v "$FX/repo" "git diff"
  decide $v "$FX/repo" "git status"
  decide $v "$FX" "diff a.txt missing.txt"
  decide $v "$FX" "diff a.txt b.txt"
done
echo "## executed under mitigation (0.50.0): git show HEAD:big.txt | tail -n 5"
decide 0.50.0 "$FX/repo" "git show HEAD:big.txt | tail -n 5"
got=$(cd "$FX/repo" && PATH="$S/tools/rtk-0.50.0:$PATH" XDG_DATA_HOME="$M/data-x" RTK_DB_PATH="$M/data-x/history.db" RTK_TELEMETRY_DISABLED=1 bash -c "${R:-git show HEAD:big.txt | tail -n 5}" | sha256sum)
nat=$(cd "$FX/repo" && git show HEAD:big.txt | tail -n 5 | sha256sum)
[ "$got" = "$nat" ] && echo "  output == native (sha256 ${nat%% *})" || echo "  output differs from native"
echo "## executed under mitigation (0.50.0): diff a.txt missing.txt"
decide 0.50.0 "$FX" "diff a.txt missing.txt"
(cd "$FX" && bash -c "${R:-diff a.txt missing.txt}" >/dev/null 2>"$M/d.err"); echo "  rc=$? stderr=[$(tr '\n' ' ' < "$M/d.err")]"
echo "## rtk hook check (0.50.0, scratch config)"
for c in "git show HEAD:big.txt | tail -n 5" "git show HEAD~2" "diff a.txt missing.txt" "git status"; do
  o=$(cd "$FX/repo" && XDG_CONFIG_HOME="$M/config" XDG_DATA_HOME="$M/data-hc" RTK_DB_PATH="$M/data-hc/history.db" RTK_TELEMETRY_DISABLED=1 "$S/tools/rtk-0.50.0/rtk" hook check "$c" 2>&1); rc=$?
  printf '  rc=%s [%s] :: %s\n' "$rc" "$c" "$(printf '%s' "$o" | tr '\n' ' ' | head -c 160)"
done
echo "## control: 0.50.0 WITHOUT mitigation config"
for c in "git show HEAD:big.txt | tail -n 5" "diff a.txt missing.txt"; do
  out=$(cd "$FX/repo" && python3 -c 'import json,os,sys;print(json.dumps({"session_id":"sota-refresh-rtk-mitig","tool_use_id":"x","cwd":os.getcwd(),"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$c" | env XDG_CONFIG_HOME="$M/emptycfg" XDG_DATA_HOME="$M/data-c" RTK_DB_PATH="$M/data-c/history.db" RTK_TELEMETRY_DISABLED=1 "$S/tools/rtk-0.50.0/rtk" hook claude 2>/dev/null)
  printf '  [%s] -> %s\n' "$c" "$(printf '%s' "$out" | python3 -c 'import json,sys;s=sys.stdin.read().strip();print(json.loads(s)["hookSpecificOutput"]["updatedInput"]["command"] if s else "SILENT")')"
done
