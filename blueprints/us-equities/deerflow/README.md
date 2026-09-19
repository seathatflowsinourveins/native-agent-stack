# DeerFlow research runtime: native, model-free acceptance

The pinned DeerFlow backend and maintained Codex ACP adapter were installed and
exercised on Linux/WSL on 2026-09-19. This acceptance establishes backend startup,
SDK discovery and native ACP session configuration. It does **not** establish a
completed research task, broker connection, inference quality or token savings.
The temporary Gateway and ACP processes exited after the checks; neither is a
standing service.

## Versions and integration boundary

- DeerFlow source: `42334f26d7025d905678f9075b079fc65f9beaf9` (MIT). This is a
  reviewed development snapshot whose backend declares `2.1.0-rc0`. The latest
  stable GitHub release at review time was `v2.0.0`, commit
  `7e7f0410797693cf882594555ba414e0361d4c6f`, released 2026-06-25.
- Native ACP adapter: `@agentclientprotocol/codex-acp@1.12.0` (Apache-2.0).
  Its upstream predecessor, `@zed-industries/codex-acp`, redirects new installs
  to the maintained package. `CODEX_PATH` selects the existing native Codex
  binary instead of the adapter's bundled version.
- The native session returned model `gpt-6-astra`, reasoning `high`, and mode
  `read-only`. Model discovery and session creation do not demonstrate inference.

DeerFlow's `CodexChatModel` directly reads an OAuth credential store and calls the
ChatGPT backend. Its Claude OAuth provider follows a similar credential-reuse
pattern. This profile does not configure either provider. ACP starts the native
Codex App Server and leaves authentication inside Codex. No login, credential
export, authentication-store inspection or account change was performed.

## Native installation

Use a new, explicit installation directory. These commands do not replace an
existing checkout. Set `DEERFLOW_HOME` to that checkout, `STACK_REPO` to this
repository, and `ACP_PREFIX` to a separate npm installation prefix.

```bash
git clone https://github.com/bytedance/deer-flow.git "$DEERFLOW_HOME"
git -C "$DEERFLOW_HOME" checkout 42334f26d7025d905678f9075b079fc65f9beaf9
cd "$DEERFLOW_HOME/backend"
uv sync --locked

npm install --global --prefix "$ACP_PREFIX" \
  --ignore-scripts --no-audit --no-fund @agentclientprotocol/codex-acp@1.12.0
```

The recorded UV operation resolved 250 packages and installed 224; the ACP
operation installed 20 npm packages. Python 3.12+ and uv suffice for these
backend checks. The full web application additionally needs the frontend and
reverse proxy. No Docker, frontend, nginx or new model weights were installed.

Use the source workspace: the public PyPI endpoints for `deerflow-harness` and
`deerflow-extension-api` returned 404 during this review, while the upstream UV
workspace resolves both packages locally. Full `make install` would also
install frontend dependencies and overwrite pre-commit hooks; it was unnecessary.

## SDK and local health

`config.discovery.yaml` disables models, tools, memory, scheduling and host shell
execution. It uses an in-memory database for this bounded startup check. It
deliberately does not claim durable application storage.

```bash
export DEER_FLOW_CONFIG_PATH="$STACK_REPO/blueprints/us-equities/deerflow/config.discovery.yaml"
export DEER_FLOW_HOME="$DEERFLOW_HOME/.runtime-discovery"
cd "$DEERFLOW_HOME/backend"

uv run --locked python -c \
  'from deerflow.client import DeerFlowClient; import json; c=DeerFlowClient(); print(json.dumps({"models": c.list_models(), "skills": c.list_skills()}))'

uv run --locked uvicorn app.gateway.app:app --host 127.0.0.1 --port 8232
```

From another terminal, while that owned process runs:

```bash
curl --fail --silent http://127.0.0.1:8232/health
```

Recorded results: **0 configured models, 23 upstream skills, HTTP 200** with
`{"status":"healthy","service":"deer-flow-gateway"}`. Unauthenticated
`GET /api/models` returned **401**, as required by the Gateway's access control.
No authentication workaround was attempted. Stop the foreground Gateway with
Ctrl+C after the check; the recorded process completed graceful shutdown.

## Native ACP discovery without inference

The helper uses the same upstream Python ACP SDK primitives as DeerFlow's ACP
tool: process startup, `initialize`, and `new_session`. It intentionally never
calls `prompt`. It forwards a bounded ordinary environment plus native Codex
configuration, denies permission requests, and creates no extra MCP bindings.
This is protocol acceptance, not a completed invocation of DeerFlow's
`invoke_acp_agent` tool; that tool would necessarily submit a prompt.

Set these explicit paths before running it:

```bash
export ACP_NODE="$(command -v node)"
export ACP_ENTRYPOINT="$ACP_PREFIX/lib/node_modules/@agentclientprotocol/codex-acp/dist/index.js"
export CODEX_PATH="$(command -v codex)"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export ACP_WORKSPACE="$DEERFLOW_HOME/.acp-discovery"
mkdir -p "$ACP_WORKSPACE"
cd "$DEERFLOW_HOME/backend"
uv run --locked python "$STACK_REPO/blueprints/us-equities/deerflow/acp-discovery.py"
```

The response may contain local session identifiers or paths; retain it privately
and publish only reviewed fields, as in `native-receipt.json`. Configuring a
future DeerFlow ACP worker should keep `auto_approve_permissions: false`, use
the maintained adapter and preserve the native read-only session preset.

## Research and execution remain separate

A future research worker may produce timestamped claims, citations and structured
research artifacts. The broker service must own deterministic validation,
idempotent order identifiers, limits and reconciliation. No broker credential or
order-submission tool belongs in this discovery profile. The existing shared
memory and RAG stack remains separate; DeerFlow memory was not enabled or migrated.

DeerFlow's newer scheduled-task queue and lease recovery are research-job
capabilities, not proof of exactly-once broker effects. Its local sandbox is a
filesystem convenience, not a secure shell isolation boundary. The configuration
therefore leaves host shell execution disabled.

## Upstream references

- [Pinned native backend commands](https://github.com/bytedance/deer-flow/blob/42334f26d7025d905678f9075b079fc65f9beaf9/backend/Makefile)
- [Pinned embedded client](https://github.com/bytedance/deer-flow/blob/42334f26d7025d905678f9075b079fc65f9beaf9/backend/packages/harness/deerflow/client.py)
- [Pinned ACP integration](https://github.com/bytedance/deer-flow/blob/42334f26d7025d905678f9075b079fc65f9beaf9/backend/packages/harness/deerflow/tools/builtins/invoke_acp_agent_tool.py)
- [Maintained native Codex ACP adapter](https://github.com/agentclientprotocol/codex-acp)
- [Stable DeerFlow 2.0 release](https://github.com/bytedance/deer-flow/releases/tag/v2.0.0)
