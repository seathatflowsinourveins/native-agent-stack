#!/bin/sh
# Source: docker/docker-compose.yaml:57-59 and docker/nginx/nginx.conf:40-41.
set -eu
ip="$(hostname -i)"
sed -e "s/listen 2026 default_server;/listen ${ip}:2026 default_server;/" \
    -e '/listen \[::\]:2026 default_server;/d' /config/nginx.conf > /etc/nginx/nginx.conf
exec nginx -g 'daemon off;'
