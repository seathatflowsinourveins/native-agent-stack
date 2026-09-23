#!/usr/bin/env bash
# Fix round 4 (gap 2 wording): does dagu reject an auth.basic block when
# auth.mode is none? Loopback control, disposable DAGU_HOME, random dummy
# password that is never printed. Reports exit status, port answer, log lines.
#   auth_none_with_basic_block.sh <dagu-binary> <work-dir> <port>
set -uo pipefail
DAGU=$1; WORK=$2; PORT=$3
mkdir -p "$WORK"; home=$(mktemp -d "$WORK/control-none-basic.XXXX"); mkdir -p "$home/dags"
pass=$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')
printf 'host: 127.0.0.1\nport: %s\ncheck_updates: false\nauth:\n  mode: none\n  basic:\n    username: probe\n    password: %s\npermissions:\n  write_dags: false\n  run_dags: false\n' "$PORT" "$pass" > "$home/config.yaml"; chmod 600 "$home/config.yaml"
code() { curl --max-time 2 -s -o /dev/null -w '%{http_code}' "$@"; }
echo "check started $(date -u +%FT%TZ)"
echo "binary: $("$DAGU" version 2>&1)"
env -i HOME="$home" PATH=/usr/bin:/bin DAGU_HOME="$home" setsid "$DAGU" server > "$home/server.log" 2>&1 &
pid=$!
ans=000
for _ in $(seq 1 30); do
  if ! kill -0 "$pid" 2>/dev/null; then break; fi
  ans=$(code "http://127.0.0.1:$PORT/api/v1/dags"); [ "$ans" != 000 ] && break; sleep 0.5
done
if kill -0 "$pid" 2>/dev/null; then
  echo "server alive: yes; anonymous GET /api/v1/dags -> $ans; served=[$(curl --max-time 2 -s "http://127.0.0.1:$PORT/" | grep -o -E 'authMode: "[a-z]+"' | head -1)]"
  echo "basic(correct) GET -> $(printf 'user = "probe:%s"\n' "$pass" | curl --max-time 2 -s -o /dev/null -w '%{http_code}' --config - "http://127.0.0.1:$PORT/api/v1/dags")"
  kill -TERM -- "-$pid" 2>/dev/null; wait "$pid" 2>/dev/null
else
  wait "$pid"; echo "server alive: no; exit status $?"
fi
echo "log lines mentioning auth/basic/error/warn (password redacted):"
grep -i -E 'auth|basic|error|warn|invalid|fail' "$home/server.log" | sed "s/$pass/<redacted>/g" | cut -c1-400 | head -20
rm -f "$home/config.yaml"
echo "stopped: port answers $(code "http://127.0.0.1:$PORT/api/v1/dags")"
echo "check finished $(date -u +%FT%TZ)"
