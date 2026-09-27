#!/usr/bin/env bash
# v0.9.4 entrypoint.sh:20-39; native supervisor/Gunicorn accepts two --binds.
set -euo pipefail
export SECRET_KEY="$(cat /run/secrets/secret_key)"
export PLAYWRIGHT_BROWSERS_PATH="$(python3 -c 'import pwd; from pathlib import Path; print(Path(pwd.getpwnam("appuser").pw_dir) / ".cache/ms-playwright")')"
# Only these dedicated worker mounts are initialized. Baked browser files stay
# at their upstream image path. Dockerfile:180-191,204-209 and supervisor user=appuser.
mkdir -p /var/lib/crawl4ai /var/lib/redis /var/cache/crawl4ai/tmp
chown appuser:appuser /var/lib/crawl4ai /var/lib/redis /var/cache/crawl4ai /var/cache/crawl4ai/tmp
chmod 0700 /var/lib/crawl4ai /var/lib/redis /var/cache/crawl4ai /var/cache/crawl4ai/tmp
# Explicit interface + a second loopback bind in supervisord.conf for MCP's proxy.
NAS_CRAWL4AI_IP="$(python3 -c 'import socket; print(socket.gethostbyname(socket.gethostname()))')"
export GUNICORN_BIND="${NAS_CRAWL4AI_IP}:11235"
cd /app
exec /bin/bash /app/entrypoint.sh
