#!/bin/sh
# Source: docker/docker-compose.yaml:105; explicit container-interface listener.
set -eu
ip="$(python -c 'import socket; print(socket.gethostbyname(socket.gethostname()))')"
cd /app/backend
exec uv run --no-sync uvicorn app.gateway.app:app --host "$ip" --port 8001 --workers 1
