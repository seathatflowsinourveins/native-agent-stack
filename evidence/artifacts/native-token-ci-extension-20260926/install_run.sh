#!/bin/sh
# One --install run of scripts/native_token_ci.py under hosted-runner-like conditions:
# a PATH holding only the Node runtime and system directories (no ambient copy of any
# measured tool, MCPorter or uv), a new empty throwaway HOME, and no TMPDIR override.
# Usage: install_run.sh <name>   (writes <name>-out/, <name>.* beside this script)
set -u
here=$(cd "$(dirname "$0")" && pwd)
name=$1
checkout=$here/../wt-ws2b
python=$here/../ci-venv/bin/python
node_bin=$(dirname "$(readlink -f "$(command -v node)")")
out=$here/$name-out
home=$here/home-$name
[ -e "$out" ] && { echo "refusing: $out exists" >&2; exit 2; }
[ -e "$home" ] && { echo "refusing: $home exists" >&2; exit 2; }
mkdir -m 700 "$home"
clean_path=$node_bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
for tool in rtk qmd repomix toon markitdown ast-grep ccusage codebase-memory-mcp headroom \
            jcodemunch-mcp mcporter uv uvx; do
  if PATH=$clean_path command -v "$tool" >/dev/null 2>&1; then
    echo "refusing: $tool is on the clean PATH" >&2; exit 2
  fi
done
ls -A /tmp/cbm-daemon-"$(id -u)" 2>/dev/null | sort > "$here/$name.host-rendezvous.before"
sha256sum "$checkout/scripts/native_token_ci.py" | cut -d' ' -f1 > "$here/$name.script.sha256"
git -C "$checkout" status --porcelain=v1 > "$here/$name.git-status.before"
date -u +%Y-%m-%dT%H:%M:%SZ > "$here/$name.started"
env -i PATH="$clean_path" HOME="$home" LANG=C.UTF-8 MCP_AUTO_OPEN_ENABLED=false \
  "$python" "$checkout/scripts/native_token_ci.py" --install --output "$out" \
  > "$here/$name.stdout" 2> "$here/$name.stderr"
rc=$?
date -u +%Y-%m-%dT%H:%M:%SZ > "$here/$name.finished"
echo "rc=$rc" > "$here/$name.rc"
git -C "$checkout" status --porcelain=v1 > "$here/$name.git-status.after"
ls -A /tmp/cbm-daemon-"$(id -u)" 2>/dev/null | sort > "$here/$name.host-rendezvous.after"
(cd "$home" && find . -mindepth 1 | sort) > "$here/$name.home-after"
# Processes still running from this run's temporary directory (executable or cwd).
: > "$here/$name.leftover"
for proc in /proc/[0-9]*; do
  exe=$(readlink "$proc/exe" 2>/dev/null || true)
  cwd=$(readlink "$proc/cwd" 2>/dev/null || true)
  case "$exe $cwd" in
    */native-token-ci-*) echo "${proc#/proc/} ${exe##*/}" >> "$here/$name.leftover" ;;
  esac
done
cat "$here/$name.stdout"
exit "$rc"
