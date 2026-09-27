#!/usr/bin/env bash
# Native Docker Compose lifecycle; configuration is in the private installed prefix.
set -euo pipefail
NAS_CRAWL4AI_RECIPE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$NAS_CRAWL4AI_RECIPE/common.sh"
NAS_CRAWL4AI_ACTION="${1:?start|stop|status|start-e2e|stop-e2e|logs-e2e}"
NAS_CRAWL4AI_DOCKER="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get docker)"
NAS_CRAWL4AI_CONTEXT="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get docker_context)"
NAS_CRAWL4AI_PROJECT=nas-crawl4ai
export NAS_CRAWL4AI_STORE=persistent
export NAS_CRAWL4AI_INTERNAL_URLS=false
NAS_CRAWL4AI_PORT_KEY=api_port
if [[ "$NAS_CRAWL4AI_ACTION" == *-e2e ]]; then
  NAS_CRAWL4AI_PROJECT=nas-crawl4ai-e2e
  export NAS_CRAWL4AI_STORE=e2e
  NAS_CRAWL4AI_PORT_KEY=e2e_api_port
  export NAS_CRAWL4AI_INTERNAL_URLS=true
fi
export NAS_CRAWL4AI_PORT="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get "$NAS_CRAWL4AI_PORT_KEY")"
export CRAWL4AI_MODEL="${CRAWL4AI_MODEL:-$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llm"]["model"])' "$NAS_CRAWL4AI_RECIPE/config/worker.json")}"
NAS_CRAWL4AI_COMPOSE=("$NAS_CRAWL4AI_DOCKER" --context "$NAS_CRAWL4AI_CONTEXT" compose --project-name "$NAS_CRAWL4AI_PROJECT" -f "$NAS_CRAWL4AI_PREFIX/recipe/config/compose.yaml")
case "$NAS_CRAWL4AI_ACTION" in
  start|start-e2e) "${NAS_CRAWL4AI_COMPOSE[@]}" up --detach --pull never --no-build ;;
  stop|stop-e2e) "${NAS_CRAWL4AI_COMPOSE[@]}" down --timeout 30 ;;
  status) "${NAS_CRAWL4AI_COMPOSE[@]}" ps ;;
  logs-e2e) "${NAS_CRAWL4AI_COMPOSE[@]}" logs --no-color --since "${2:?run start timestamp required}" ;;
  *) echo 'Unknown lifecycle operation' >&2; exit 2 ;;
esac
