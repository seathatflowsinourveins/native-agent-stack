#!/usr/bin/env bash
# 2026-09-26, reconciling #314 with #318: the adopted recipe is #318's four-entry
# exclude_commands block, and bootstrap-linux.sh's rtk_config_reminder combines
# #318's text check (the exact four-entry key, exactly once) with #314's
# behavioural check (the installed `rtk hook check` must answer "No rewrite for"
# with exit 1 for five probes).
# Part 1: `rtk hook check` on the probes under scratch configs (XDG_CONFIG_HOME).
# Part 2: the reminder, extracted verbatim from the given bootstrap-linux.sh, on
#         scratch configs with a scratch bin_dir holding the installed rtk.
# Part 3: the same reminder with this host's own environment (read-only).
# Usage: combined-reminder-20260926.sh <path to adoption/bootstrap-linux.sh>
set -Eeuo pipefail
S="$HOME/.local/share/codex-ecosystem"
R="$S/tools/rtk-0.50.0/rtk"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
fn=$(awk '/^rtk_config_reminder\(\) \{$/{f=1} f{print} f&&/^\}$/{exit}' "$1")
eval "$fn"
FOUR=$(cat <<'EOF'
[hooks]
exclude_commands = [
  "^git show [^ ]*:",
  "diff",
  '^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*show\s+(?:[^\n]*\s)?[^\s]*:',
  '^git\s+(?:(?:-C|-c|--git-dir|--work-tree)\s+\S+\s+|--\S+\s+)*branch(?:\s|$)',
]
EOF
)
write() { mkdir -p "$W/$1/rtk"; printf '%s\n' "$2" > "$W/$1/rtk/config.toml"; }
write four-entry "$FOUR"
write four-entry-tracking-without-history-days "$FOUR"$'\n[tracking]\nenabled = false'
write four-entry-tracking-with-history-days "$FOUR"$'\n[tracking]\nenabled = false\nhistory_days = 90'
write single-regex-alternative $'[hooks]\nexclude_commands = [\'^git(\\s+\\S+)*\\s+show(\\s+\\S+)*\\s+(:\\S|[^\\s-]\\S*:)\', "diff"]'
write two-entry-20260925 $'[hooks]\nexclude_commands = ["^git show [^ ]*:", "diff"]'
mkdir -p "$W/no-config"
echo "## $("$R" --version); rtk_config_reminder sha256 $(printf '%s\n' "$fn" | sha256sum | cut -d' ' -f1)"
echo "## part 1: rtk hook check on the reminder's probes"
for cfg in four-entry four-entry-tracking-without-history-days four-entry-tracking-with-history-days; do
  echo "# $cfg"
  for probe in 'git show HEAD:x | tail -n 5' 'git -C . show --no-color HEAD:x | tail -n 5' 'diff a missing' 'git branch -a' 'git -C . branch'; do
    rc=0; out=$(cd "$W" && env XDG_CONFIG_HOME="$W/$cfg" RTK_DB_PATH="$W/history.db" RTK_TELEMETRY_DISABLED=1 "$R" hook check "$probe" </dev/null 2>&1) || rc=$?
    printf '  rc=%s [%s] :: %s\n' "$rc" "$probe" "$(printf '%s' "$out" | tr '\n' ' ')"
  done
done
echo "## part 2: rtk_config_reminder on scratch configs (bin_dir holds the installed rtk)"
mkdir -p "$W/bin"; ln -s "$R" "$W/bin/rtk"
for cfg in four-entry four-entry-tracking-without-history-days four-entry-tracking-with-history-days single-regex-alternative two-entry-20260925 no-config; do
  out=$(cd "$W" && bin_dir="$W/bin" XDG_CONFIG_HOME="$W/$cfg" RTK_DB_PATH="$W/history.db" RTK_TELEMETRY_DISABLED=1 rtk_config_reminder | sed "s#$W#<scratch>#g")
  if [ -z "$out" ]; then echo "  $cfg: silent"; else
    case "$out" in *"rtk ignores a config it cannot load"*) kind="reminder, text passes but rtk fails";; *) kind="reminder, text check fails";; esac
    echo "  $cfg: $kind :: ${out:0:120}..."; fi
done
echo "## part 3: rtk_config_reminder with this host's environment (read-only)"
out=$(bin_dir="$S/bin" rtk_config_reminder)
echo "  $("$S/bin/rtk" --version) at bin/rtk: ${out:-silent (text matches and every probe answered No rewrite for, exit 1)}" | sed "s#$HOME#~#g"
