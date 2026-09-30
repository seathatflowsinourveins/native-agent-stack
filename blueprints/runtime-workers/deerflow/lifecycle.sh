#!/usr/bin/env bash
# Reference: DeerFlow v2.1.0 scripts/deploy.sh {start,down}, backend/Makefile.
set -euo pipefail
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$recipe_dir/recipe.py" lifecycle "${1:?Usage: lifecycle.sh up|down|check|upstream-tests}"
