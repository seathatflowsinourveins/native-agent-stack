#!/usr/bin/env bash
# GPT-6 (Codex CLI) lane runner for the landscape sweep. The workflow's wrapper agents call:
#   codex_call.sh [--work-dir DIR] start  <job-id> <prompt-file> <schema-file>
#   codex_call.sh [--work-dir DIR] wait   <job-id> [seconds]
#   codex_call.sh [--work-dir DIR] result <job-id>
# codex_job.py next to this file holds the logic and its documentation: the detached codex exec (gpt-6-astra,
# effort max, --search, --ignore-user-config, read-only sandbox, stdin from /dev/null), the semaphore slots and
# the usage-limit marker. Locking, detaching and the timeout use the Python standard library, so this runs
# unchanged on Linux/WSL2 and on macOS (bash 3.2, no flock, setsid or timeout commands).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$here/codex_job.py" "$@"
