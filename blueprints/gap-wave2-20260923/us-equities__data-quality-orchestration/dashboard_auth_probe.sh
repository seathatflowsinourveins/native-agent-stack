#!/usr/bin/env bash
# Gap 2: record the dashboard auth mode of the running dagu-equities service
# with GET requests only, and prove the same probe detects basic auth on
# loopback control instances of the same pinned binary (disposable DAGU_HOME,
# dummy generated credential that is never a real account secret).
#   dashboard_auth_probe.sh <dagu-binary> <work-dir> <live-port>
set -uo pipefail
DAGU=$1; WORK=$2; LIVE_PORT=$3
mkdir -p "$WORK"
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
# Basic credential via curl's config on stdin (fix round 3), so no
# user:password pair appears on a curl command line.
code_basic() { printf 'user = "%s"\n' "$1" | curl -s -o /dev/null -w '%{http_code}' --config - "$2"; }
served_mode() { curl -s "$1/" | grep -o -E 'authMode: "[a-z]+"' | head -1; }

control() {  # control <name> <port> <mode>
  local name=$1 port=$2 mode=$3 home
  home=$(mktemp -d "$WORK/control-$name.XXXX"); mkdir -p "$home/dags"
  local user=probe pass
  pass=$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')
  {
    printf 'host: 127.0.0.1\nport: %s\ncheck_updates: false\nmetrics: private\n' "$port"
    printf 'auth:\n  mode: %s\n' "$mode"
    if [ "$mode" = basic ]; then printf '  basic:\n    username: %s\n    password: %s\n' "$user" "$pass"; fi
    printf 'permissions:\n  write_dags: false\n  run_dags: false\n'
  } > "$home/config.yaml"; chmod 600 "$home/config.yaml"
  env -i HOME="$home" PATH=/usr/bin:/bin DAGU_HOME="$home" setsid "$DAGU" server > "$home/server.log" 2>&1 &
  local pid=$!
  for _ in $(seq 1 40); do [ "$(code "http://127.0.0.1:$port/api/v1/dags")" != 000 ] && break; sleep 0.5; done
  local base="http://127.0.0.1:$port"
  echo "control=$name mode_configured=$mode served=[$(served_mode "$base")]"
  echo "  anonymous GET /api/v1/dags -> $(code "$base/api/v1/dags")"
  echo "  anonymous WWW-Authenticate: [$(curl -s -D - -o /dev/null "$base/api/v1/dags" | grep -i '^www-authenticate' | tr -d '\r')]"
  echo "  basic(correct) GET /api/v1/dags -> $(code_basic "$user:$pass" "$base/api/v1/dags")"
  echo "  basic(wrong) GET /api/v1/dags -> $(code_basic "$user:wrong-$pass" "$base/api/v1/dags")"
  kill -TERM -- "-$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  for _ in $(seq 1 20); do [ "$(code "$base/api/v1/dags")" = 000 ] && break; sleep 0.5; done
  echo "  stopped: port answers $(code "$base/api/v1/dags")"
}

echo "probe started $(date -u +%FT%TZ)"
echo "binary: $("$DAGU" version 2>&1)"
control none 18632 none
control basic 18633 basic

LIVE="http://127.0.0.1:$LIVE_PORT"
echo "live service: $(systemctl --user show dagu-equities.service -p ActiveState -p SubState -p ExecMainStartTimestamp | tr '\n' ' ')"
echo "live served=[$(served_mode "$LIVE")]"
echo "live anonymous GET /api/v1/dags -> $(code "$LIVE/api/v1/dags")"
echo "live anonymous WWW-Authenticate: [$(curl -s -D - -o /dev/null "$LIVE/api/v1/dags" | grep -i '^www-authenticate' | tr -d '\r')]"
echo "live dummy-basic GET /api/v1/dags -> $(code_basic "probe:not-a-real-credential" "$LIVE/api/v1/dags")"
echo "live anonymous GET / -> $(code "$LIVE/")"
echo "live service after probe: $(systemctl --user show dagu-equities.service -p ActiveState -p ExecMainStartTimestamp | tr '\n' ' ')"
echo "probe finished $(date -u +%FT%TZ)"
