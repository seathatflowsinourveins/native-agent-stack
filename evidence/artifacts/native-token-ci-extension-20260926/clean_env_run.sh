#!/bin/sh
# Start one Python script under hosted-runner-like conditions and record independent
# observations. Used for the 2026-09-26 polish-pass runs; unlike install_run.sh it takes
# every location as an argument and writes nothing next to itself or in the checkout.
#
# Usage: clean_env_run.sh <checkout> <python> <scratch-dir> <name> <script> [args...]
#
# The script runs under `env -i` with a PATH of only the Node runtime's directory and the
# system directories (the wrapper refuses to start if any measured tool, MCPorter or uv
# resolves there), a new empty HOME and TMPDIR under <scratch-dir>/<name>/, LANG=C.UTF-8,
# MCP_AUTO_OPEN_ENABLED=false and PYTHONDONTWRITEBYTECODE=1 (no bytecode cache in the
# checkout). An argument spelled @OUT@ becomes <scratch-dir>/<name>/out.
#
# codebase-memory-mcp's rendezvous socket must fit a Unix socket address, which the harness
# checks before starting it: with a 4-digit uid, <scratch-dir>/<name>/tmp may be at most 36
# bytes long (for example /tmp/n/r1/tmp). A longer TMPDIR makes that fixture fail by design.
# Observations written to <scratch-dir>/<name>/: sha256 of the harness and script, git status
# of the checkout before and after, the entry names of the account-default codebase-memory-mcp
# rendezvous (/tmp/cbm-daemon-<uid>) before and after, what HOME and TMPDIR hold afterwards,
# processes left running from <scratch-dir>/<name>/, timestamps, stdout, stderr and exit code.
set -u
[ $# -ge 5 ] || { echo "usage: $0 <checkout> <python> <scratch-dir> <name> <script> [args...]" >&2; exit 64; }
checkout=$(cd "$1" && pwd -P) || exit 2
python=$2
scratch=$(cd "$3" && pwd -P) || exit 2
name=$4
script=$5
shift 5
case "$scratch/" in
  "$checkout"/*) echo "refusing: $scratch is inside the checkout" >&2; exit 2 ;;
esac
base=$scratch/$name
[ -e "$base" ] && { echo "refusing: $base exists" >&2; exit 2; }
mkdir "$base" && mkdir -m 700 "$base/home" "$base/tmp" || exit 2
node_bin=$(dirname "$(readlink -f "$(command -v node)")")
clean_path=$node_bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
for tool in rtk qmd repomix toon markitdown ast-grep ccusage codebase-memory-mcp headroom \
            jcodemunch-mcp mcporter uv uvx; do
  if PATH=$clean_path command -v "$tool" >/dev/null 2>&1; then
    echo "refusing: $tool is on the clean PATH" >&2; exit 2
  fi
done
for arg do
  shift
  [ "$arg" = @OUT@ ] && arg=$base/out
  set -- "$@" "$arg"
done
sha256sum "$checkout/scripts/native_token_ci.py" "$script" > "$base/sources.sha256"
git -C "$checkout" status --porcelain=v1 > "$base/git-status.before"
ls -A "/tmp/cbm-daemon-$(id -u)" 2>/dev/null | sort > "$base/host-rendezvous.before"
date -u +%Y-%m-%dT%H:%M:%SZ > "$base/started"
env -i PATH="$clean_path" HOME="$base/home" TMPDIR="$base/tmp" LANG=C.UTF-8 \
  MCP_AUTO_OPEN_ENABLED=false PYTHONDONTWRITEBYTECODE=1 \
  "$python" "$script" "$@" > "$base/stdout" 2> "$base/stderr"
rc=$?
date -u +%Y-%m-%dT%H:%M:%SZ > "$base/finished"
echo "rc=$rc" > "$base/rc"
git -C "$checkout" status --porcelain=v1 > "$base/git-status.after"
ls -A "/tmp/cbm-daemon-$(id -u)" 2>/dev/null | sort > "$base/host-rendezvous.after"
(cd "$base/home" && find . -mindepth 1 | sort) > "$base/home-after"
(cd "$base/tmp" && find . -mindepth 1 | sort) > "$base/tmp-after"
: > "$base/leftover"
for proc in /proc/[0-9]*; do
  exe=$(readlink "$proc/exe" 2>/dev/null || true)
  cwd=$(readlink "$proc/cwd" 2>/dev/null || true)
  case "$exe $cwd" in
    *"$base"/*) echo "${proc#/proc/} ${exe##*/}" >> "$base/leftover" ;;
  esac
done
cat "$base/stdout"
exit "$rc"
