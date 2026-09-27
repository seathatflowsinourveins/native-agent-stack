#!/usr/bin/env bash
# Native Docker Compose lifecycle; configuration is in the private installed prefix.
set -euo pipefail
NAS_CRAWL4AI_RECIPE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$NAS_CRAWL4AI_RECIPE/common.sh"
NAS_CRAWL4AI_ACTION="${1:?start|stop|status|start-e2e|stop-e2e|logs-e2e}"
NAS_CRAWL4AI_DOCKER="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get docker)"
NAS_CRAWL4AI_CONTEXT="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get docker_context)"
NAS_CRAWL4AI_PROJECT=rw-crawl4ai-persistent
export NAS_CRAWL4AI_STORE=persistent
export NAS_CRAWL4AI_INTERNAL_URLS=false
NAS_CRAWL4AI_PORT_KEY=api_port
if [[ "$NAS_CRAWL4AI_ACTION" == *-e2e ]]; then
  NAS_CRAWL4AI_PROJECT=rw-crawl4ai-e2e
  export NAS_CRAWL4AI_STORE=e2e
  NAS_CRAWL4AI_PORT_KEY=e2e_api_port
  export NAS_CRAWL4AI_INTERNAL_URLS=true
fi
export NAS_CRAWL4AI_PORT="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get "$NAS_CRAWL4AI_PORT_KEY")"
CRAWL4AI_MODEL="$(python3 "$NAS_CRAWL4AI_RECIPE/worker.py")"
export CRAWL4AI_MODEL
NAS_CRAWL4AI_CONTAINER="rw-crawl4ai-$NAS_CRAWL4AI_STORE"
NAS_CRAWL4AI_NETWORK="rw-crawl4ai-$NAS_CRAWL4AI_STORE-net"
NAS_CRAWL4AI_CLIENT=("$NAS_CRAWL4AI_DOCKER" --context "$NAS_CRAWL4AI_CONTEXT")
NAS_CRAWL4AI_COMPOSE=("$NAS_CRAWL4AI_DOCKER" --context "$NAS_CRAWL4AI_CONTEXT" compose --project-name "$NAS_CRAWL4AI_PROJECT" -f "$NAS_CRAWL4AI_PREFIX/recipe/config/compose.yaml")
case "$NAS_CRAWL4AI_ACTION" in
  start|start-e2e) "${NAS_CRAWL4AI_COMPOSE[@]}" up --detach --pull never --no-build ;;
  stop|stop-e2e)
    # Docker CLI literal-name removal only. A failed daemon query fails cleanup.
    NAS_CRAWL4AI_FOUND="$("${NAS_CRAWL4AI_CLIENT[@]}" container ls --all --filter "name=^/$NAS_CRAWL4AI_CONTAINER$" --format '{{.Names}}')"
    if [[ "$NAS_CRAWL4AI_FOUND" == "$NAS_CRAWL4AI_CONTAINER" ]]; then
      "${NAS_CRAWL4AI_CLIENT[@]}" container stop --time 30 "$NAS_CRAWL4AI_CONTAINER"
      "${NAS_CRAWL4AI_CLIENT[@]}" container rm --force "$NAS_CRAWL4AI_CONTAINER"
    fi
    NAS_CRAWL4AI_FOUND="$("${NAS_CRAWL4AI_CLIENT[@]}" network ls --filter "name=^$NAS_CRAWL4AI_NETWORK$" --format '{{.Name}}')"
    if [[ "$NAS_CRAWL4AI_FOUND" == "$NAS_CRAWL4AI_NETWORK" ]]; then
      "${NAS_CRAWL4AI_CLIENT[@]}" network rm "$NAS_CRAWL4AI_NETWORK"
    fi ;;
  status) "${NAS_CRAWL4AI_COMPOSE[@]}" ps ;;
  logs-e2e) "${NAS_CRAWL4AI_COMPOSE[@]}" logs --no-color --since "${2:?run start timestamp required}" ;;
  *) echo 'Unknown lifecycle operation' >&2; exit 2 ;;
esac
