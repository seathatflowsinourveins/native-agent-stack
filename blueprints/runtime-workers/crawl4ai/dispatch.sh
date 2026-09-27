#!/usr/bin/env bash
# CPython subprocess lifecycle over the installed upstream worker; see dispatch.py.
set -euo pipefail
NAS_CRAWL4AI_RECIPE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$NAS_CRAWL4AI_RECIPE/common.sh"
exec python3 "$NAS_CRAWL4AI_PREFIX/recipe/dispatch.py" "$@"
