#!/usr/bin/env bash
# modelcontextprotocol/inspector@2.9.0:docs/cli-smoke-testing.md:502
# modelcontextprotocol/inspector@2.9.0:docs/environment-variables.md:28,50,81
# mksglu/context-mode@6f0cc6841c687e754059f36714a11233fda1a02b:hooks/core/routing.mjs:731-785
# https://docs.kernel.org/networking/ip-sysctl.html#ip-variables
# iproute2/iproute2@v6.19.0:misc/ss.c:236,251,6010-6017
set -euo pipefail
root="${1:?Supply the owned output directory}"
client="${2:?Supply claude or codex}"
[[ "$client" == claude || "$client" == codex ]]
[[ -d "$root" ]]
[[ "${MCP_AUTO_OPEN_ENABLED:-}" == false ]]
printf '%s\n' "$MCP_AUTO_OPEN_ENABLED" >"$root/$client-env.txt"
export TMPDIR="$root/$client-tmp"
mkdir -p -- "$TMPDIR"

MCP_INSPECTOR_SECRET_STORE=memory npx -y @modelcontextprotocol/inspector@2.9.0 \
  --cli qmd --index native-agent-stack-catalog mcp -- --method tools/list \
  >"$root/$client-tools.json" 2>"$root/$client-cli.stderr"
printf 'INSPECTOR_CLI_OK\n'

server_pid=
read -r ephemeral_first ephemeral_last </proc/sys/net/ipv4/ip_local_port_range
if (( 16399 >= ephemeral_first && 16399 <= ephemeral_last )); then
  printf 'Inspector acceptance port is inside the host ephemeral range\n' >&2
  exit 1
fi
bound_sockets="$(ss -H -tan '( sport = :16399 )')"
if [[ -n "$bound_sockets" ]]; then
  printf 'Inspector acceptance port is already occupied\n' >&2
  exit 1
fi
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill -TERM -- "-$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT
MCP_INSPECTOR_SECRET_STORE=memory HOST=127.0.0.1 CLIENT_PORT=16399 \
  setsid npx -y @modelcontextprotocol/inspector@2.9.0 --web -- \
  qmd --index native-agent-stack-catalog mcp \
  >"$root/$client-web.stdout" 2>"$root/$client-web.stderr" &
server_pid=$!
ready=false
for attempt in {1..90}; do
  if curl --silent --show-error --fail --max-time 2 \
    --output "$root/$client-page.html" http://127.0.0.1:16399/ \
    2>"$root/$client-curl.stderr"; then
    kill -0 "$server_pid"
    ready=true
    break
  fi
  kill -0 "$server_pid"
  sleep 1
done
[[ "$ready" == true ]]
printf 'INSPECTOR_WEB_OK\n'
cleanup
server_pid=
trap - EXIT
printf 'INSPECTOR_STOPPED\n'
