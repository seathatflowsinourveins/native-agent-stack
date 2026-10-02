#!/usr/bin/env bash
# Same persistent contract as CLI dispatch. Pass GPTR_RUN_ID or --run-id.
set -euo pipefail
umask 077
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$recipe_dir/dispatch.py" run --mode e2e "$@"
