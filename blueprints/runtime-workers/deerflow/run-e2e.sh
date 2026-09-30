#!/usr/bin/env bash
# Inspect AI@0.3.271 providers.py:361-365; log/_log.py:798-895.
set -euo pipefail
umask 077
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$recipe_dir/e2e/evaluate.py" "$@"
