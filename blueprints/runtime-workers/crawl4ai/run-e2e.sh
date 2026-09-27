#!/usr/bin/env bash
# The coordinator runs this after installation; the builder runs offline tests only.
set -euo pipefail
NAS_CRAWL4AI_RECIPE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$NAS_CRAWL4AI_RECIPE/common.sh"
export TMPDIR="$NAS_CRAWL4AI_STATE/tmp"
exec "$NAS_CRAWL4AI_PREFIX/venv/bin/python" "$NAS_CRAWL4AI_PREFIX/recipe/e2e/run.py"
