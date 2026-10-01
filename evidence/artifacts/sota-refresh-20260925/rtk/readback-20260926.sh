#!/usr/bin/env bash
# Read-only read-back of the host's rtk hook config after the 2026-09-26 widening.
# Parses ~/.config/rtk/config.toml with tomllib and runs `rtk hook check` against it;
# history goes to a scratch RTK_DB_PATH. Home paths print as ~.
set -u
S="$HOME/.local/share/codex-ecosystem"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/rtk/config.toml"
WIDE='^git(\s+\S+)*\s+show(\s+\S+)*\s+(:\S|[^\s-]\S*:)'
echo "## rtk: $("$S/bin/rtk" --version) -> $(readlink -f "$S/bin/rtk" | sed "s#^$HOME#~#")"
echo "## $(printf '%s' "$CFG" | sed "s#^$HOME#~#") (sha256 $(sha256sum < "$CFG" | cut -d' ' -f1))"
cat "$CFG"
python3 -c 'import sys,tomllib
e=tomllib.load(open(sys.argv[1],"rb")).get("hooks",{}).get("exclude_commands")
print("parsed [hooks].exclude_commands:", e)
print("holds the recommended regex exactly:", sys.argv[2] in e, "| holds diff:", "diff" in e)' "$CFG" "$WIDE"
echo "## rtk hook check with the host config (scratch history)"
for c in "git show HEAD:x | tail -n 5" "git show --no-color HEAD:x | tail -n 5" "git -C . show HEAD:x | tail -n 5" \
         "git show  HEAD:x | tail -n 5" "git --no-pager show HEAD:x" "git show :x" "diff a missing" \
         "git show HEAD~2" "git show --stat HEAD" "git show HEAD --format=%h:%s" "git show-branch" \
         "git diff" "git status" "git log -3" "head -3 README.md"; do
  o=$(cd "$W" && RTK_DB_PATH="$W/history.db" RTK_TELEMETRY_DISABLED=1 "$S/bin/rtk" hook check "$c" 2>&1); rc=$?
  printf '  rc=%s [%s] :: %s\n' "$rc" "$c" "$(printf '%s' "$o" | tr '\n' ' ' | head -c 120)"
done
