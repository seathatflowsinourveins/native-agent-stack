#!/usr/bin/env bash
# GPTR@0957c301 cli.py:359-362; see dispatch.py for the persistent job contract.
set -euo pipefail
umask 077
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$recipe_dir/dispatch.py" "$@"
