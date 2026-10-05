#!/usr/bin/env bash
# Shared host/CI vector: source this file, then call sync_trading_2604.
# The caller supplies safe (a clean-environment command-prefix array), project
# and runtime_python (the managed interpreter). Failures stop the vector even
# if the caller invokes the function from a shell conditional.
# Reuse commands directly, as validate.yml does with its install-command pins.
# https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/sync.md
readonly python_pin=3.12.3
readonly uv_pin=0.12.17
readonly exclude_newer=2026-10-06T04:00:00Z

sync_trading_2604() {
    step=lock-check
    "${safe[@]}" uv --no-config lock --check --project "$project" --python "$runtime_python" \
        --no-python-downloads --prerelease if-necessary \
        --default-index https://pypi.org/simple --exclude-newer "$exclude_newer" || return "$?"
    step=package-sync
    "${safe[@]}" uv --no-config sync --project "$project" --python "$runtime_python" \
        --no-python-downloads --locked --no-dev --prerelease if-necessary \
        --default-index https://pypi.org/simple --exclude-newer "$exclude_newer" || return "$?"
    step=dependency-check
    "${safe[@]}" uv --no-config pip check --python "$project/.venv/bin/python" || return "$?"
}
