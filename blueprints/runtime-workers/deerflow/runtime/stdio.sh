#!/bin/sh
# Source: DeerFlow v2.1.0 mcp/client.py:25-33 forwards command/args/env, not cwd.
# Preserve the adoption template's executable and argv while fixing its cwd.
set -eu
cd /work
exec "$@"
