# DeerFlow research runtime: native ACP inference

The pinned DeerFlow backend and maintained Codex ACP adapter completed a bounded
read-only Astra research task on Linux/WSL on 2026-09-19. DeerFlow's actual
`invoke_acp_agent` tool read two public evidence files through native Codex and
returned their correct numerical results and remaining Alpaca paper acceptance
steps. The native turn completed in **31.027 seconds**, reporting **41,737 input
tokens, including 24,320 cached tokens, and 608 output tokens**. The measured
output includes 53 reasoning tokens. These are usage counters, not net savings.

[research-receipt.json](research-receipt.json) records this inference separately
from the earlier model-free [native-receipt.json](native-receipt.json).
[research-result.md](research-result.md) preserves the returned text. The result
reviews the two historical inputs; its statement that the earlier discovery did
not prove inference remains accurate. This is embedded tool acceptance with no
DeerFlow planner model, web UI, durable job service or broker connection. All
owned processes exited, and no listening service was started for the research.

**Permission limitation:** ACP 1.12.0's mode ID `read-only` maps to a
`workspaceWrite` sandbox, `networkAccess: false`, and `approvalPolicy: on-request`;
its display name is "Ask for approval". Both source and this native turn confirm
that policy. The task performed a read only, but the mode permits workspace
writes without an approval request. It is **not** strict read-only enforcement.
Use the [official SDK worker](../workers/native_worker.py), which explicitly sets
`Sandbox.read_only`, when that enforcement is required. Do not adopt this ACP
profile as a protected unattended worker until upstream supports the required
policy. A `CODEX_CONFIG` sandbox setting does not establish that guarantee because
the adapter supplies its own per-turn policy.

## Versions and integration boundary

- DeerFlow source: `42334f26d7025d905678f9075b079fc65f9beaf9` (MIT). This is a
  reviewed development snapshot whose backend declares `2.1.0-rc0`. The latest
  stable GitHub release at review time was `v2.0.0`, commit
  `7e7f0410797693cf882594555ba414e0361d4c6f`, released 2026-06-25.
- Native ACP adapter: `@agentclientprotocol/codex-acp@1.12.0` (Apache-2.0).
  Its upstream predecessor, `@zed-industries/codex-acp`, redirects new installs
  to the maintained package. `CODEX_PATH` selects the existing native Codex
  binary instead of the adapter's bundled version.
- Both discovery and the subsequent research selected `gpt-6-astra`, reasoning
  `high`, and the ACP mode ID `read-only` (see its effective policy above).
  The research's native thread reported provider
  `openai`; no model-reroute event was observed. This is the native client's
  reported identity, not independent provider attestation.

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

## Real embedded research invocation

`native-research.py` constructs the upstream `ACPAgentConfig`, calls the unmodified
`build_invoke_acp_agent_tool`, and invokes its native LangChain `.ainvoke` method.
It does not implement a replacement ACP prompt loop or read OAuth stores.
`config.research.yaml` keeps the DeerFlow planner, tools, memory and scheduling
disabled while configuring this explicitly invoked ACP tool. The helper replaces
only its Node and adapter installation paths. In a standalone DeerFlow config,
set those paths yourself; `$...` expansion is upstream-supported for `env`
values, not arbitrary `command` or `args` fields.

First inspect the existing native account with the installed official SDK
environment (`WORKER_PYTHON`). Select the Linux native `CODEX_PATH` and `CODEX_HOME`
explicitly when the invoking Desktop process uses a different home. `PRIVATE_RUN`
must be a private directory outside the repository; `research-1` must not exist.
The helper requires a ready discovery receipt less than 30 minutes old.

```bash
mkdir -p "$PRIVATE_RUN"
"$WORKER_PYTHON" "$STACK_REPO/blueprints/us-equities/workers/native_worker.py" inspect \
  --codex-bin "$CODEX_PATH" --codex-home "$CODEX_HOME" \
  --workspace "$STACK_REPO" --receipt "$PRIVATE_RUN/readiness.json"

"$DEERFLOW_HOME/backend/.venv/bin/python" \
  "$STACK_REPO/blueprints/us-equities/deerflow/native-research.py" \
  --node "$ACP_NODE" --adapter "$ACP_ENTRYPOINT" \
  --codex-bin "$CODEX_PATH" --codex-home "$CODEX_HOME" \
  --state-dir "$PRIVATE_RUN/research-1" --readiness "$PRIVATE_RUN/readiness.json"
```

The actual run used a native allowance check reporting Astra available, ordinary
usage allowed and 50% of the weekly bucket used. It copied only the two published
receipts into DeerFlow's dedicated ACP workspace. Native Codex read them with:

```bash
head -c 24000 -- engine-receipt.json deerflow-discovery.json
```

The command exited 0. One ACP prompt completed with **3,943 LEAN data points,
3 simulated orders, 0 failed data requests, 0 historical configured DeerFlow
models, 23 skills, and 0 historical ACP prompts**. No MCP tool or broker request
was made by this task. ACP's `read-only` mode ID and DeerFlow's default denial of
permission requests stayed in effect; no permissions were auto-approved.
The inherited native client may still discover its configured MCP servers:
read-only filesystem sandboxing is not remote-tool authorization or full account
isolation. A future task needing approval must use a client that supports normal
interactive approval, not set DeerFlow's blanket auto-approval switch.

DeerFlow's upstream collecting client returns text and discards ACP prompt
completion and usage fields. Therefore a returned string alone is insufficient
proof. This run enabled the adapter's supported `APP_SERVER_LOGS` and reviewed
its native `turn/completed` and `thread/tokenUsage/updated` events. Use the final
**cumulative** usage for the new thread; do not add intermediate snapshots or
mistake its final request's `last` usage for the entire turn. The adapter log
contains local account/session metadata and must stay private. The public receipt
selects safe fields and retains the private log's hash for provenance.

The helper bounds the upstream prompt to 180 seconds and the overall invocation
to 240 seconds, refuses an existing output directory and writes private evidence.
It forwards ordinary process variables and the existing native home rather than
credentials. It is a small replay example, not a persistent research scheduler.

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
