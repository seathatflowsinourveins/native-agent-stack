#!/bin/sh
# Source: upstream Compose redis command; Redis image entrypoint normally chowns
# a host bind to its redis UID. Root inside rootless Docker retains the host user's
# ownership here, and is not host root. Only the private bridge address listens.
set -eu
ip="$(hostname -i)"
exec redis-server --bind "$ip" --appendonly yes
