#!/usr/bin/env bash
# Reference: DeerFlow v2.1.0 scripts/deploy.sh and .github/workflows/container.yaml.
set -euo pipefail
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$recipe_dir/recipe.py" install "${1:?Usage: install.sh /private/host.json}"
