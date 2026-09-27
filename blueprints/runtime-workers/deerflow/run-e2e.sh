#!/usr/bin/env bash
# Reference: DeerFlow v2.1.0 DeerFlowClient.stream, client.py:770-910.
set -euo pipefail
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$recipe_dir/e2e/run.py"
