#!/usr/bin/env bash
# 2026-09-26 re-test of the Claude-hook exclude_commands mitigation after the
# post-merge review of #291 found that the 2026-09-25 pattern "^git show [^ ]*:"
# misses ordinary blob-read spellings. Compares no config, the 2026-09-25 narrow
# pattern and the widened 2026-09-26 pattern through `rtk hook check` and through
# the real `rtk hook claude` PreToolUse JSON path, then executes selected blob
# reads under each decision and compares their bytes with native git.
# Uses a scratch XDG_CONFIG_HOME, XDG_DATA_HOME and RTK_DB_PATH; never ~/.config/rtk.
set -u
S="$HOME/.local/share/codex-ecosystem"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
NARROW='^git show [^ ]*:'
WIDE='^git(\s+\S+)*\s+show(\s+\S+)*\s+(:\S|[^\s-]\S*:)'
mkdir -p "$W/none/rtk" "$W/narrow/rtk" "$W/wide/rtk"
printf '%s\n' '[hooks]' "exclude_commands = ['$NARROW', \"diff\"]" > "$W/narrow/rtk/config.toml"
printf '%s\n' '[hooks]' "exclude_commands = ['$WIDE', \"diff\"]" > "$W/wide/rtk/config.toml"
echo "## narrow config (2026-09-25)"; cat "$W/narrow/rtk/config.toml"
echo "## wide config (2026-09-26)"; cat "$W/wide/rtk/config.toml"
python3 -c 'import sys,tomllib;print("tomllib read-back:",tomllib.load(open(sys.argv[1],"rb"))["hooks"]["exclude_commands"])' "$W/wide/rtk/config.toml"

# Fixture: a repository whose blob is far larger than the ~8 KiB window.
R="$W/repo"; mkdir -p "$R"
( cd "$R" && git init -q && for i in $(seq 1 4000); do printf 'row %04d %s\n' "$i" 'padding-padding-padding-padding'; done > big.txt \
  && printf 'a\nb\n' > a.txt && printf '1\n2\n3\n4\n' > README.md && git add . \
  && git -c user.name=fixture -c user.email=fixture@example.invalid -c core.hooksPath=/dev/null commit -qm fixture \
  && git -c user.name=fixture -c user.email=fixture@example.invalid -c core.hooksPath=/dev/null commit -q --allow-empty -m two \
  && git -c user.name=fixture -c user.email=fixture@example.invalid -c core.hooksPath=/dev/null commit -q --allow-empty -m three )

TAB=$'\t'
EXCLUDE_EXPECTED=(
  "git show HEAD:big.txt | tail -n 5"
  "git show --no-color HEAD:big.txt | tail -n 5"
  "git -C . show HEAD:big.txt | tail -n 5"
  "git show  HEAD:big.txt | tail -n 5"
  "git show${TAB}HEAD:big.txt | tail -n 5"
  "git --no-pager show HEAD:big.txt"
  "git -c color.ui=never show HEAD:big.txt | tail -n 5"
  "git show HEAD:big.txt 2>&1 | tail -n 5"
  "GIT_PAGER=cat git show HEAD:big.txt | tail -n 5"
  "/usr/bin/git show HEAD:big.txt | tail -n 5"
  "cd . && git show HEAD:big.txt | tail -n 5"
  "git show :big.txt"
  "git show HEAD~1:big.txt"
  "diff a.txt missing.txt"
)
REWRITE_EXPECTED=(
  "git show HEAD~2"
  "git show --stat HEAD"
  "git show HEAD --format=%h:%s"
  "git show-branch"
  "git diff"
  "git status"
  "git log -3"
  "head -3 README.md"
)

check() { # ver cfg cmd -> "rc=N :: output"
  local o rc
  o=$(cd "$R" && env XDG_CONFIG_HOME="$W/$2" XDG_DATA_HOME="$W/data-$1" RTK_DB_PATH="$W/data-$1/history.db" RTK_TELEMETRY_DISABLED=1 \
      "$S/tools/rtk-$1/rtk" hook check "$3" 2>&1); rc=$?
  printf 'rc=%s :: %s' "$rc" "$(printf '%s' "$o" | tr '\n' ' ' | sed 's/\t/<TAB>/g' | head -c 150)"
}
hookjson() { # ver cfg cmd -> rewritten command or SILENT(native)
  local out
  out=$(cd "$R" && python3 -c 'import json,os,sys;print(json.dumps({"session_id":"codex-postmerge-rtk","tool_use_id":"codex-postmerge-rtk-1","cwd":os.getcwd(),"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":sys.argv[1]}}))' "$3" \
      | env XDG_CONFIG_HOME="$W/$2" XDG_DATA_HOME="$W/data-$1" RTK_DB_PATH="$W/data-$1/history.db" RTK_TELEMETRY_DISABLED=1 "$S/tools/rtk-$1/rtk" hook claude 2>/dev/null)
  if [ -n "$out" ]; then printf '%s' "$out" | python3 -c 'import json,sys;print(json.load(sys.stdin)["hookSpecificOutput"]["updatedInput"]["command"])'
  else echo "SILENT(native)"; fi
}
show() { printf '%s' "$1" | sed 's/\t/<TAB>/g'; }

for v in 0.50.0 0.49.0; do
  for group in EXCLUDE_EXPECTED REWRITE_EXPECTED; do
    echo "## rtk $v hook check, $group (no config | narrow | wide)"
    eval "cases=(\"\${${group}[@]}\")"
    for c in "${cases[@]}"; do
      printf '[%s]\n  none:   %s\n  narrow: %s\n  wide:   %s\n' "$(show "$c")" "$(check $v none "$c")" "$(check $v narrow "$c")" "$(check $v wide "$c")"
    done
  done
done

echo "## rtk 0.50.0 hook claude (PreToolUse JSON), wide config"
for c in "${EXCLUDE_EXPECTED[@]}" "${REWRITE_EXPECTED[@]}"; do
  printf '  %-58s -> %s\n' "[$(show "$c")]" "$(hookjson 0.50.0 wide "$c")"
done

echo "## executed through the 0.50.0 hook decision: bytes compared with native git"
NATIVE=$(cd "$R" && git show HEAD:big.txt | tail -n 5 | sha256sum | cut -d' ' -f1)
echo "  native sha256 $NATIVE"
for cfg in none narrow wide; do
  for c in "git show HEAD:big.txt | tail -n 5" "git show --no-color HEAD:big.txt | tail -n 5" "git -C . show HEAD:big.txt | tail -n 5" "git show  HEAD:big.txt | tail -n 5"; do
    d=$(hookjson 0.50.0 "$cfg" "$c"); [ "$d" = "SILENT(native)" ] && run="$c" || run="$d"
    got=$(cd "$R" && PATH="$S/tools/rtk-0.50.0:$PATH" XDG_CONFIG_HOME="$W/$cfg" XDG_DATA_HOME="$W/data-x" RTK_DB_PATH="$W/data-x/history.db" RTK_TELEMETRY_DISABLED=1 bash -c "$run" 2>/dev/null)
    sha=$(printf '%s\n' "$got" | sha256sum | cut -d' ' -f1)
    [ "$sha" = "$NATIVE" ] && verdict="== native" || verdict="DIFFERS: $(printf '%s' "$got" | head -n 1 | head -c 60)"
    printf '  %-6s %-50s %s\n' "$cfg" "[$c]" "$verdict"
  done
done

echo "## explicit rtk invocation is outside exclude_commands (wide config)"
got=$(cd "$R" && env XDG_CONFIG_HOME="$W/wide" XDG_DATA_HOME="$W/data-x" RTK_DB_PATH="$W/data-x/history.db" RTK_TELEMETRY_DISABLED=1 \
      "$S/tools/rtk-0.50.0/rtk" git show HEAD:big.txt 2>/dev/null | tail -n 5)
sha=$(printf '%s\n' "$got" | sha256sum | cut -d' ' -f1)
[ "$sha" = "$NATIVE" ] && echo "  [rtk git show HEAD:big.txt | tail -n 5] == native" || { echo "  [rtk git show HEAD:big.txt | tail -n 5] DIFFERS from native:"; printf '%s\n' "$got" | sed 's/^/    /'; }
printf '  hook check of an explicit rtk command: %s\n' "$(check 0.50.0 wide "rtk git show HEAD:big.txt | tail -n 5")"
got=$(cd "$R" && env XDG_CONFIG_HOME="$W/wide" XDG_DATA_HOME="$W/data-x" RTK_DB_PATH="$W/data-x/history.db" RTK_TELEMETRY_DISABLED=1 \
      "$S/tools/rtk-0.50.0/rtk" proxy git show HEAD:big.txt 2>/dev/null | tail -n 5)
sha=$(printf '%s\n' "$got" | sha256sum | cut -d' ' -f1)
[ "$sha" = "$NATIVE" ] && echo "  [rtk proxy git show HEAD:big.txt | tail -n 5] == native" || echo "  [rtk proxy git show HEAD:big.txt | tail -n 5] DIFFERS from native"
echo "## diff on a missing file, wide config: executed natively"
d=$(hookjson 0.50.0 wide "diff a.txt missing.txt"); echo "  hook -> $d"
(cd "$R" && diff a.txt missing.txt >/dev/null 2>&1); echo "  native rc=$?"
