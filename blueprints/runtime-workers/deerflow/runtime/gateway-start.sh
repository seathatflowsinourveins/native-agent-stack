#!/bin/sh
# Source: docker/docker-compose.yaml:105; explicit container-interface listener.
set -eu
if [ -f /run/secrets/redis-password ]; then
  DEER_FLOW_STREAM_BRIDGE_REDIS_URL="redis://:$(cat /run/secrets/redis-password)@redis:6379/0"
  export DEER_FLOW_STREAM_BRIDGE_REDIS_URL
fi
ip="$(python -c 'import socket; print(socket.gethostbyname(socket.gethostname()))')"
cd /app/backend
exec uv run --no-sync uvicorn app.gateway.app:app --host "$ip" --port 8001 --workers 1
