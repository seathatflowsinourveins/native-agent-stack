#!/usr/bin/env bash
# 2026-09-26 (Codex review of #314): a TOML-valid rtk config can still be ignored.
# rtk 0.50.0 deserializes config.toml into Config; TrackingConfig has no serde
# default for history_days (src/core/config.rs:152-158 at 1d87b8e7), so a
# [tracking] table without it fails Config::load, and cached_config() falls
# back to Config::default() with no exclude_commands (config.rs:261-281).
# Runs the installed binary's `rtk hook check` on the bootstrap reminder's
# probes under a scratch XDG_CONFIG_HOME; never reads or writes ~/.config/rtk.
set -u
S="$HOME/.local/share/codex-ecosystem"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
WIDE='^git(\s+\S+)*\s+show(\s+\S+)*\s+(:\S|[^\s-]\S*:)'
BASE=$(printf '%s\n' '[hooks]' "exclude_commands = ['$WIDE', \"diff\"]")
write() { mkdir -p "$W/$1/rtk"; printf '%s\n' "$2" > "$W/$1/rtk/config.toml"; }
write recommended "$BASE"
write tracking-without-history-days "$BASE"$'\n[tracking]\nenabled = false'
write tracking-with-history-days "$BASE"$'\n[tracking]\nenabled = false\nhistory_days = 90'
echo "## rtk $("$S/tools/rtk-0.50.0/rtk" --version)"
for cfg in recommended tracking-without-history-days tracking-with-history-days; do
  echo "## $cfg"
  sed 's/^/  | /' "$W/$cfg/rtk/config.toml"
  python3 -c 'import sys,tomllib;d=tomllib.load(open(sys.argv[1],"rb"));print("  tomllib: valid; [hooks].exclude_commands =",d["hooks"]["exclude_commands"])' "$W/$cfg/rtk/config.toml"
  for probe in 'git show HEAD:x | tail -n 5' 'git -C . show --no-color HEAD:x | tail -n 5' 'diff a missing'; do
    out=$(cd "$W" && env XDG_CONFIG_HOME="$W/$cfg" XDG_DATA_HOME="$W/data" RTK_DB_PATH="$W/data/history.db" RTK_TELEMETRY_DISABLED=1 \
          "$S/tools/rtk-0.50.0/rtk" hook check "$probe" </dev/null 2>&1); rc=$?
    printf '  rc=%s [%s] :: %s\n' "$rc" "$probe" "$(printf '%s' "$out" | tr '\n' ' ')"
  done
done
