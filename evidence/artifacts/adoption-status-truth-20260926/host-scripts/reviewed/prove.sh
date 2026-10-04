#!/usr/bin/env bash
# u5 E2E proof, read-only and safe to run any time (G9 adoption_status truth; G13 hygiene incl. the G5a marker recipe).
#
#   prove.sh [--checkout DIR] [--main DIR] [--worktree DIR]...
#
# --checkout  the checkout whose scripts/adoption_status.py and files are proven (default: --main)
# --main      the host's primary checkout, the .worktreeinclude source (default: ~/code/native-agent-stack)
# --worktree  an enrolled worker worktree that must admit ai-memory capture (repeatable)
#
# local_integration: prove.py compares upstream commands and native APIs (codex debug prompt-input, codex app-server
# hooks/list, codex/claude --version, ai-memory hook --check-capture, wt step copy-ignored --dry-run, the anonymous
# loopback Prometheus query API) with the checker's own JSON. It writes nothing to the host: Codex may log its own
# probe start as any Codex start does. Exit 0 only when every check passes; before apply it is expected to fail.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
main="${HOME}/code/native-agent-stack"
checkout=""
worktrees=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --checkout) checkout="$2"; shift 2 ;;
    --main) main="$2"; shift 2 ;;
    --worktree) worktrees+=(--worktree "$2"); shift 2 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
checkout="${checkout:-$main}"
for tool in codex claude ai-memory wt git uv; do
  command -v "$tool" >/dev/null || { echo "FAIL  prerequisite: $tool is not on PATH" >&2; exit 1; }
done
# The adoption manifest supports Python 3.13 only; this is the documented runner (docs/token-efficiency-stack.md).
python_cmd="uv run --no-project --python 3.13 python"
export PYTHONDONTWRITEBYTECODE=1  # no __pycache__ in the checkout under test
exec $python_cmd "$here/prove.py" --checkout "$checkout" --main "$main" --python "$python_cmd" "${worktrees[@]}"
