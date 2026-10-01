#!/usr/bin/env bash
# 2026-09-26: run bootstrap-linux.sh's rtk_config_reminder, extracted verbatim, against this
# host's installed rtk and its own environment (read-only: `rtk hook check` writes nothing).
# Usage: reminder-readback-20260926.sh <path to adoption/bootstrap-linux.sh>
set -Eeuo pipefail
fn=$(awk '/^rtk_config_reminder\(\) \{$/{f=1} f{print} f&&/^\}$/{exit}' "$1")
echo "## rtk_config_reminder sha256 $(printf '%s\n' "$fn" | sha256sum | cut -d' ' -f1)"
eval "$fn"
bin_dir="$HOME/.local/share/codex-ecosystem/bin"
echo "## $("$bin_dir/rtk" --version) at bin/rtk; config ${XDG_CONFIG_HOME:+\$XDG_CONFIG_HOME}${XDG_CONFIG_HOME:-~/.config}/rtk/config.toml"
out=$(rtk_config_reminder)
echo "## reminder output: ${out:-<none: every probe answered No rewrite for, exit 1>}" | sed "s#$HOME#~#g"
