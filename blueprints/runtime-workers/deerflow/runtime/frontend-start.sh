#!/bin/sh
# Source: frontend/Dockerfile prod CMD; Next.js start hostname option.
set -eu
ip="$(hostname -i)"
cd /app/frontend
exec pnpm start --hostname "$ip"
