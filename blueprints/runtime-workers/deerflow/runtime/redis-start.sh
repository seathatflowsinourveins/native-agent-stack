#!/bin/sh
# Source: upstream Compose redis command; Redis image entrypoint normally chowns
# a host bind to its redis UID. Root inside rootless Docker retains the host user's
# ownership here, and is not host root. Only the private bridge address listens.
set -eu
ip="$(hostname -i)"
# redis/redis@7.4.2 redis.conf:1042-1050 (requirepass); secret is never argv.
printf 'bind %s\nappendonly yes\nrequirepass %s\n' "$ip" "$(cat /run/secrets/redis-password)" > /tmp/redis.conf
chmod 600 /tmp/redis.conf
exec redis-server /tmp/redis.conf
