# DeerFlow runtime worker candidate

DeerFlow 2.1.0 is a **draft multi-agent runtime-worker recipe**, powered by GPT-6 through the local OmniRoute gateway. The deliverable is configuration, installation instructions, and a DeerFlow transport solver for the upstream GAIA benchmark. Source inspection and offline integration checks are evidence for this recipe; Docker startup, model calls, and runtime acceptance must be measured by the coordinator. No host installation, image pull, service start, production-service modification, or live E2E was performed while building it. This belongs to `lane:foundation`; the trading DeerFlow/codex-acp recipe is reference only.

## Native qualification, 2026-09-30

An isolated native backend installation and CLI check completed. Three selected
unchanged upstream backend files returned **309 passed**; the unchanged GAIA
scorer tests returned **eight passed**. Backend `uv pip check` still exits 1 for
the upstream's explicit websockets override; no service/model/GAIA task score is
claimed. Exact commands, original source comparisons and retained failures are
in the [native receipt](../../../evidence/artifacts/runtime-roster-20260930/deerflow-native.json)
and [qualification note](../../../evidence/artifacts/runtime-roster-20260930/README-deerflow.md).
The construction records below describe the earlier source/offline rounds.

The selected source is [bytedance/deer-flow v2.1.0](https://github.com/bytedance/deer-flow/releases/tag/v2.1.0), annotated tag object `f6e747be2486d3f75b0d66a8b17d8fb0ffd5f8ce`, commit **`345f08be00c8a9495079b732a39b46aa9af1584e`**. [pins.json](pins.json) is the machine-readable artifact record. The exact archive and upstream lockfile hashes, calculated from returned bytes on 2026-09-27, are:

| Artifact | SHA256 |
| --- | --- |
| GitHub codeload archive at the commit | `de309ec407d0b5b9ef1855a2cdcd97d9a9c2c95d0b0029cde6c79b9212518ffe` |
| `backend/uv.lock` | `3cc643cd34374384c62de7fd8cef49cc4608df01ea11eff85daeea51f5cf0d5f` |
| `frontend/pnpm-lock.yaml` | `cee8007d2e1b10eb84c853971130cbb8ba5e0893fd0c0a381f840e77b6a2ed5b` |
| Official backend image manifest | `68426f84f06f91a44f61c9620c9badffec162133615d351f1d40db0982a753e6` |
| Official frontend image manifest | `2f10108592ddb2f93ff5c62f670e010cd4123c4e93eed6bc0ce5fd2bf426f0db` |
| Upstream `redis:7-alpine` manifest index, resolved 2026-09-27 | `858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499` |
| Upstream `nginx:alpine` manifest index, resolved 2026-09-27 | `df221db836e1754089190208cee7eeda94f233197056426eda74a43ab1abeac2` |

Registry metadata was fetched without downloading image layers. SHA256 of each manifest response matched its `Docker-Content-Digest` header. The backend and frontend image configuration labels matched the selected source revision and `v2.1.0`; their manifests are `linux/amd64`. Redis and nginx are dated resolutions of tags used by upstream, not pins published in the DeerFlow release. The upstream [container publication workflow, lines 15–114](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/.github/workflows/container.yaml#L15-L114) builds and publishes the official images. Attestations were not verified. Pulling these digests preserves the built artifacts; it does not establish reproducibility of upstream's mutable APT, NodeSource, npm, and base-image build inputs.

Upstream supports these installation paths:

| Path | Source at the pin | Decision |
| --- | --- | --- |
| Docker development: `make docker-init`, `make docker-start` | [README:283–299](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/README.md#L283-L299) | Supported; avoid development dependency synchronization for this recipe. |
| Production Compose: `scripts/deploy.sh build/start/down` | [README:500–528](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/README.md#L500-L528), [Compose:27–162](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/docker/docker-compose.yaml#L27-L162) | **Chosen:** same gateway/frontend/Redis/nginx topology, using official release digests and private worker paths. |
| Native source: `make check`, `make install`, `make dev` | [README:377–424](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/README.md#L377-L424), [Makefile:94–101](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/Makefile#L94-L101) | Alternative for host-resident stdio tools. Do not invoke `make install` here: it also installs pre-commit and changes Git hooks. |
| Locked dependency installation inside upstream images | [backend/Dockerfile:61–74](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/Dockerfile#L61-L74), [frontend/Dockerfile:10–40](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/frontend/Dockerfile#L10-L40) | `uv sync --locked --extra redis` and `pnpm install --frozen-lockfile` already ran in the published builds. This installer verifies/pulls image digests instead of repeating those builds. |

The recipe remains a draft. Round 3 changes configuration and host-side adapters; it does not claim installation, container networking, native dispatch, or a GAIA score. The repair used the installed search-first, find-skills, tdd and verification-before-completion guidance inline. The maintained reference is the upstream `claude-to-deerflow` skill at the selected DeerFlow commit, with its Gateway API; no additional skill or runtime was installed. See [round3-verification.md](round3-verification.md) and [round3-verification.json](round3-verification.json) for findings, sources, failing controls, passing checks and remaining host gates.

## Workflow dispatch

Workflow children use [deerflow-run](deerflow-run), a Bash entry point for the native Gateway HTTP API. It follows **bytedance/deer-flow@345f08be00c8a9495079b732a39b46aa9af1584e**, [skills/public/claude-to-deerflow/scripts/chat.sh:24–90,140–164](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/scripts/chat.sh#L24) and [backend/app/gateway/routers/thread_runs.py:923–939,1143–1168,1528–1560](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/routers/thread_runs.py#L923). The wrapper adds Bearer authentication, background create/poll, a caller-supplied stable ID, private result files and explicit evidence exits. Python's standard HTTP client keeps the PAT out of process arguments. Redirects and ambient HTTP proxies are refused for authenticated API calls.

The coordinator first installs the recipe, starts the chosen server arm, initializes the first user in the UI at `http://127.0.0.1:3771`, and creates a PAT from that user's interactive session. Required scopes are `threads:write`, `threads:read`, `runs:create`, `runs:read`, and `runs:cancel`. Save it as a caller-owned mode-0600 file outside every worktree and export **only its path** as `DEERFLOW_PAT_FILE`. Source: DeerFlow@345f08be [backend/app/gateway/auth/pat.py:28–40,53–116](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/auth/pat.py#L28), [routers/auth.py:651–704](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/routers/auth.py#L651), and [csrf_middleware.py:230–234](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/csrf_middleware.py#L230). Authentication remains enabled; the wrapper does not use the internal service token.

These are the exact commands a Bash workflow child runs after that setup:

```sh
export PYTHONDONTWRITEBYTECODE=1
export DEERFLOW_RECIPE="$HOME/.local/share/codex-ecosystem/tools/deerflow-2.1.0"
export DEERFLOW_PAT_FILE=/private/path/deerflow-workflow.pat
export RUNTIME_WORKER_ARM=control

rtk bash "$DEERFLOW_RECIPE/deerflow-run" start \
  --run-id wf-example-001 --arm "$RUNTIME_WORKER_ARM" \
  --caller workflow-name/stage-name --mode pro 'The bounded research task'
rtk bash "$DEERFLOW_RECIPE/deerflow-run" wait \
  --run-id wf-example-001 --arm "$RUNTIME_WORKER_ARM" --timeout 540 --interval 10
rtk bash "$DEERFLOW_RECIPE/deerflow-run" result \
  --run-id wf-example-001 --arm "$RUNTIME_WORKER_ARM"
# When cancellation is required:
rtk bash "$DEERFLOW_RECIPE/deerflow-run" cancel \
  --run-id wf-example-001 --arm "$RUNTIME_WORKER_ARM"
```

Keep `wait --timeout` below the child's Bash timeout; use the child's supported background Bash mode for long waits, or call `wait` again after exit 3. Modes `flash`, `standard`, `pro`, `ultra` copy the upstream context flags, with max provider effort enforced independently of those flags: DeerFlow@345f08be [skills/public/claude-to-deerflow/SKILL.md:104–108](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/SKILL.md#L104). `on_disconnect: continue` and background `POST /runs` avoid tying the run to a waiting Bash process: [backend/app/gateway/run_models.py:29–58](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/run_models.py#L29).

The state root is `$HOME/.local/state/native-agent-stack/runtime-workers/deerflow`. For `wf-example-001`, deterministic private paths are:

- `dispatch/wf-example-001/status.json`: written before the first HTTP call; contains native IDs, arm, caller, idempotency key and current state.
- `dispatch/wf-example-001/result.json`: initialized at start; final answer, exit classification and receipt pointer after `result`.
- `dispatch/wf-example-001/receipt.json`: sanitized run counters, independent gateway observations and compression delta, without native, trace or correlation IDs.
- `dispatch.jsonl`: one private mode-0600 ledger entry per acknowledged native run. Native IDs and trace IDs stay here and in status, outside receipts.

Every command prints JSON containing deterministic artifact paths. `start` also returns native thread/run IDs. Retrying an identical stable ID reuses the native idempotency key; a changed prompt, caller or mode is refused. If create's response is lost after thread creation, exit 3 preserves the active slot for retry. Dispatches are serial. The native messages endpoint returns `{data, has_more}`; the wrapper follows `before_seq` pages and unwraps each RunEvent content field and extracts the final lead-agent AI text, including text blocks. Middleware/child messages cannot replace the lead answer. The envelope is specified in DeerFlow@345f08be `backend/packages/harness/deerflow/runtime/events/store/base.py:32–43,54–55` and `runtime/journal.py:512–522`. Source: DeerFlow@345f08be [thread_runs.py:1528–1560](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/routers/thread_runs.py#L1528) and [pagination.py:6–15](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/pagination.py#L6).

| Exit | Meaning |
| --- | --- |
| 0 | `start`: accepted; `wait`: native success; `result`: native success, nonempty answer and complete independent gateway/effort evidence. Generic dispatch has no answer-quality grader. |
| 1 | Negative native outcome (`error`, `timeout`, `cancelled`), or an official GAIA accuracy below 1 in the E2E adapter. |
| 2 | Setup/configuration/authentication/transport failure. |
| 3 | Still running at the wait deadline, interrupted, ambiguous create, requested cancellation awaiting observation, or incomplete evidence. A correct GAIA answer with missing evidence also returns 3. |

Count Claude-side invocations from child-usage and OTel **Bash tool events**, matching this entry point and stable `--run-id` (normalize the `rtk bash` prefix and do not count wait/result polls as new invocations). Reconcile with the private ledger and native `GET /threads/{tid}/runs/{rid}` records by native run ID. Native `llm_call_count` counts model calls, not wrapper invocations. Keep these lanes separate. Sources: DeerFlow@345f08be [thread_runs.py:223–242](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/routers/thread_runs.py#L223), [console.py:278–425](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/app/gateway/routers/console.py#L278). Console aggregates require the owning user's login session; the PAT route policy does not include console routes. Host OTel/child-usage collection and native-record reconciliation remain unmeasured.

## Arms

**`RUNTIME_WORKER_ARM=control|engines-on`**, default `control`, is the arm switch. `--arm` overrides it for a dispatch or E2E invocation. The only optional control-model override is **`DEERFLOW_CONTROL_MODEL=cx/gpt-6-<variant>-max`**, preserving the recipe's existing GPT-6 max routes; the private host file's `model` is the fallback. Engines-on always selects `sharedgw/gpt-6-astra-max` with exactly one slash.

| Arm | Host gateway | Container model base URL | Model | Experimental header |
| --- | --- | --- | --- | --- |
| control | `http://127.0.0.1:20128/v1` | `http://10.0.2.2:20128/v1` | `cx/gpt-6-astra-max` | None |
| engines-on | `http://127.0.0.1:20129/v1` | `http://10.0.2.2:20129/v1` | `sharedgw/gpt-6-astra-max` | `x-omniroute-compression: allow-lossy` |

The arm table is the coordinator's 2026-09-27 round-3 gateway contract. The previous review's `sharedgw/cx/...` proposal is declined in favor of this contract. Config uses `$DEERFLOW_BASE_URL` and `$DEERFLOW_MODEL`; their container environment values are derived from the arm, not arbitrary user endpoints. Both arms retain conversation affinity and per-call idempotency, omit temperature and send Responses `reasoning.effort=max`. No `X-OmniRoute-No-Cache` header is sent. Receipts record the arm, model, base URL, effort and **header names only**.

The HTTP client remains the pinned LangChain `ChatOpenAI`, including native sync/async streaming, tools, retries and structured-output parser. Config sets `include_response_headers: true` and explicit `openai_proxy: http://egress:3128`. The fixed forwarding service is the only network path to the selected model gateway. Sources: **langchain-ai/langchain, langchain-openai==1.2.1**, SHA256-verified sdist in [pins.json](pins.json), `langchain_openai/chat_models/base.py:668–670,934–935,1220–1242,1404–1411,1462–1469,1683–1712,3327–3345`; DeerFlow@345f08be [config/app_config.py:432,565](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/config/app_config.py#L565), [models/factory.py:248–285](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/models/factory.py#L248).

Embedded GAIA selects its arm per invocation. The persistent HTTP Gateway has one active arm: the coordinator selects it without reinstalling, after finishing existing dispatches:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 RUNTIME_WORKER_ARM=control \
  bash blueprints/runtime-workers/deerflow/lifecycle.sh up
# For a later engines-on run:
rtk env PYTHONDONTWRITEBYTECODE=1 RUNTIME_WORKER_ARM=engines-on \
  bash blueprints/runtime-workers/deerflow/lifecycle.sh up
```

`up` re-renders and recreates owned services, including the fixed forwarder. It refuses a switch while a recorded dispatch is active. A workflow child validates the running Gateway's immutable arm/model/base-URL labels before posting; it cannot change model endpoints through the API. An arm mismatch is setup failure. This preserves the upstream model-config boundary, rather than claiming that a per-request context can replace server transport settings.

Native summarization, tool-output externalization, token budgets, deferred skill/tool discovery and bounded subagents remain configured in [config.yaml.template](config.yaml.template). Lead and summary model name is `worker`; subagents inherit it. Structured output uses upstream function calling with `strict=False` and the native parser. Direct raw JSON modes remain refused. Feature sources at DeerFlow@345f08be: `config/summarization_config.py:55–94`, `tool_output_config.py:12–118`, `token_budget_config.py:6–20`, `subagents_config.py:74–174`, `subagent_runtime_config.py:8–36`, `skills_config.py:18–39` under `backend/packages/harness/deerflow`.

## Usage accounting

The entry gateway is the only SQL counter source: control reads `~/.local/share/omniroute/storage.sqlite`; engines-on reads `~/.local/share/omniroute-fw/storage.sqlite`. SQLite opens with `?mode=ro`, never creates a missing database, and uses an authorizer limited to `call_logs` and the permitted columns. **The coordinator must verify that the engines-on path belongs to port 20129 before acceptance.** A missing/unreadable store produces `unavailable`, not zero usage. The 20128 forwarding leg is never added to the 20129 entry counters.

Read columns are `timestamp`, `path`, `status`, `model`, `tokens_in`, `tokens_cache_read`, `tokens_reasoning`, `correlation_id`, plus `reasoning_effort_requested` and `reasoning_effort_upstream` required by common requirement 3. Correlation IDs are used transiently to join and are omitted from receipts. Duplicate IDs in matching SQL rows are ambiguous and make evidence incomplete. Cache-read and reasoning counters are reported separately; no sum of subset counters is presented as total provider usage. The authorized projection does not contain output-token totals.

For isolated E2E, the independent nginx forwarding container captures every returned `X-Correlation-Id` in its native access log; the host saves that log outside every model-visible mount. Generic dispatch extracts headers that the native run's messages expose. SQL observations require matching window, model, path and captured correlation IDs. Complete correlated rows produce entry-gateway counter sums. With no IDs, the explicit fallback is **time window + model + path at the arm's entry gateway**; concurrent traffic may be included, attribution remains unknown and `usage_total` is null. Partial dispatch visibility, such as missing summary/subagent response headers, remains incomplete when correlation count differs from native `llm_call_count`.

Source: **diegosouzapw/OmniRoute@a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3**, `src/sse/handlers/chat.ts:436`, `src/sse/handlers/chatHelpers.ts:1172–1184`, and [src/lib/usage/callLogs.ts:628–653,779–800](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L628). The host runs a patched build; its exact match to the coordinator's common contract remains a host check.

Effort reporting separates rows with returned reasoning from rows with zero returned reasoning. For positive reasoning tokens, logged requested/upstream effort must both be max before evidence is complete; non-max and unobserved effort have separate counts. **Null effort does not mean effort was missing:** the pinned `callLogs.ts:646–653` fills those columns only for encrypted reasoning. Rows with zero reasoning do not falsely fail a max check, but a run with no observed max reasoning row cannot establish max effort.

Engines-on snapshots `GET http://127.0.0.1:20129/api/analytics/compression?since=all` before/after the run. It reports deltas of `totalRequests`, `totalTokensSaved` and `totalSkipped` separately from SQL/provider counters. These are gateway-wide analytics; other traffic can contribute. Counter resets, missing fields or denied management access remain unknown. Source: OmniRoute@a58000c [src/app/api/analytics/compression/route.ts:13–24](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/app/api/analytics/compression/route.ts#L13) and [src/lib/db/compressionAnalytics.ts:52–82](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/db/compressionAnalytics.ts#L52). No analytics request was made in this repair session.

Native skill/tool observations remain worker-reported. Both pinned ToolMessage serializations omit top-level status; a skill read must now contain its frontmatter `name:` before it can count. A returned result is not semantic success certification. Source: DeerFlow@345f08be [backend/packages/harness/deerflow/client.py:527–564](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/client.py#L527). Raw traces and gated GAIA data remain private.

## Security posture

All model execution stays in the rootless Docker context. No host HOME, Docker socket, host-network mode, host PID namespace or host-executing MCP is exposed. The internal worker network has no external default route. A separate nginx forwarder joins that network and an egress network, forwarding only POST `/v1/responses` and `/v1/chat/completions` to the selected, fixed `10.0.2.2:20128` or `:20129`. Caller-controlled destinations and CONNECT are not forwarded. Every other path is denied. Gateway shells cannot use that service to reach ai-memory, Qdrant, the other gateway port, or arbitrary host listeners. **This is source-backed configuration, not a measured reachability claim**: verify direct host/bridge routes and allowed/denied ports under the actual rootless daemon before E2E.

Sources: **compose-spec/compose-spec@914ec15d1fa498969c0df5c1d672306db3256089**, [06-networks.md:215–218](https://github.com/compose-spec/compose-spec/blob/914ec15d1fa498969c0df5c1d672306db3256089/06-networks.md#L215), [05-services.md:171–175,1839–1841,1955–1963,2029–2046,2080–2082](https://github.com/compose-spec/compose-spec/blob/914ec15d1fa498969c0df5c1d672306db3256089/05-services.md#L171); **nginx/nginx@release-1.28.0**, [src/http/modules/ngx_http_proxy_module.c:305–358,417–457](https://github.com/nginx/nginx/blob/release-1.28.0/src/http/modules/ngx_http_proxy_module.c#L305). The forwarder reuses the existing digest-pinned nginx image; its actual binary/config acceptance remains a host gate.

This narrow forwarding policy also blocks general web egress. Raw ai-memory HTTP and SocratiCode's Qdrant/embedding connections are disabled, and their former ports are not forwarded. They need separately qualified authenticated/scoped service adapters before re-enabling. Public-web GAIA tasks therefore remain unqualified under this network policy. The four in-container stdio servers remain configured: context-mode, Serena, jCodeMunch and lexical QMD. Serena's dashboard and GUI log window are off. Native disabled-server handling is DeerFlow@345f08be `config/extensions_config.py:209–215,559–565`; the existing adoption command is preserved apart from the explicit Serena dashboard flag.

Every service drops ALL capabilities, sets `no-new-privileges:true`, and has a read-only root with explicit writable state/tmpfs. nginx and the egress forwarder run as UID/GID `101:101`. Gateway, frontend and Redis retain the release/default UID: **the blanket non-root override is declined in this round**, because the current rootless bind state and private configuration are host-owned 0700/0600 and no mapped-UID lifecycle has been qualified. An arbitrary UID would make the installed recipe unreadable/unwritable. This residual is explicit, not a non-root claim. Source: DeerFlow@345f08be [backend/Dockerfile:94–127](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/Dockerfile#L94) and Compose's `user` override cited above. Rootless container root is not host root, but writable binds remain in its trust domain.

Each E2E attempt builds a fresh two-service Compose project and unique internal/egress networks. It mounts new `/state` and `/work`, copies an immutable host-retained QMD seed, and never inherits the persistent stack's `env_file`, JWT store, internal token, Redis connection or shared writable MCP state. Skills/config/dependencies are read-only; events, input hashes, status, grading logs, forwarding logs and receipts are host-written outside model-writable mounts. Shutdown removes only that owned project and reports failed cleanup as incomplete. Persistent Redis now requires a private mode-0600 password, read into its config without putting the value on argv: **redis/redis@7.4.2**, [redis.conf:1041–1050](https://github.com/redis/redis/blob/7.4.2/redis.conf#L1041). The persistent Gateway's own local execution and authentication state remain one single-user trust domain; this is not a multi-tenant sandbox.

Resolved dependency mounts are allowlisted to adopted `bin`, versioned `tools/<name>-<version>` prefixes and the declared four QMD collections. Resolved credential paths, their ancestors/descendants, home ancestors, socket files, writable shared mounts and symlink escapes are refused. Required interpreter/library targets must fit that narrow layout and be available in the backend container; host preflight must establish it. No host authentication store was read in this repair.

The grader's 96-package lock targets Linux x86_64 / CPython 3.13. It was compiled with **astral-sh/uv@0.12.17**, [docs/pip/compile.md:24–28](https://github.com/astral-sh/uv/blob/0.12.17/docs/pip/compile.md#L24), and installed CLI `uv pip compile --help` (`--generate-hashes`, `--only-binary`, `--no-build`). A second wheel-only resolution reproduced the lock hash. `install_grader` verifies that hash, installs with pip `--require-hashes --only-binary=:all: --no-deps`, then runs `pip check` and checks the exact Inspect versions. No package was installed during this repair. The lock source/hash are in [pins.json](pins.json). Other platforms/Python versions require a newly compiled reviewed lock.

## Installation and official GAIA grading

The coordinator prepares [host.json.example](host.json.example) in a private mode-0600 file, installs the separately owned skills manifest using the existing project/universal installer, and supplies the native rootless Docker executable and adopted in-container dependencies. The skills manifest/CLI extension remains a separate coordinator dependency. The QMD seed must contain exactly the four adopted nonempty collections; SQLite backup reads the original in read-only mode. Source: **tobi/qmd@v2.8.3**, `src/collections.ts:101–125`, `src/store.ts:636–653,1181–1270` (same selected reference as round 2).

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 bash blueprints/runtime-workers/deerflow/install.sh /private/path/deerflow-host.json
rtk env PYTHONDONTWRITEBYTECODE=1 bash blueprints/runtime-workers/deerflow/lifecycle.sh check
rtk env PYTHONDONTWRITEBYTECODE=1 bash blueprints/runtime-workers/deerflow/lifecycle.sh upstream-tests
rtk env PYTHONDONTWRITEBYTECODE=1 RUNTIME_WORKER_ARM=control \
  bash blueprints/runtime-workers/deerflow/run-e2e.sh FROZEN_GAIA_VALIDATION_ID gaia-control-001
rtk env PYTHONDONTWRITEBYTECODE=1 RUNTIME_WORKER_ARM=engines-on \
  bash blueprints/runtime-workers/deerflow/run-e2e.sh FROZEN_GAIA_VALIDATION_ID gaia-engines-001
rtk env PYTHONDONTWRITEBYTECODE=1 bash blueprints/runtime-workers/deerflow/lifecycle.sh down
```

The host publishes only nginx on `127.0.0.1:3771`. Prefix is `$HOME/.local/share/codex-ecosystem/tools/deerflow-2.1.0`; state is the private root documented above. Install copies the reviewed dispatch entry point and dependencies there without starting services. `check` is configuration/MCP/skill discovery; `upstream-tests` selects the unchanged model-factory, MCP-client-config and embedded-client tests through upstream pytest. `down` removes the five literal owned service names and two named networks while preserving persistent bind data. All resources retain the `com.native-agent-stack.owner=gpt6-omniroute-framework-integration` label.

GAIA uses **UKGovernmentBEIS/inspect_evals@41c72eaa2b807ce43f35fac6f3f399318adc7e9d** (`v0.22.0`) and **UKGovernmentBEIS/inspect_ai@c2b63a0b0560f9c3b5b5230365e0a8fe08cd3df0** (`0.3.271`). Dataset revision remains `682dd723ee1e1697e00360edccf2366dc8418dd9`, validation split, frozen no-attachment IDs. The existing adapter preserves the upstream dataset, input instructions, answer target, `gaia_scorer` and metrics. Only the worker transport is replaced. No upstream grading container or grader resource limit is modified. Sources: Inspect Evals@v0.22.0 `src/inspect_evals/gaia/{gaia.py,dataset.py,scorer.py,README.md}` and `tests/gaia/test_scorer.py`; the attachment-free prompt expansion is `dataset.py:78–104`.

[run-e2e.sh](run-e2e.sh) now uses Inspect's built-in **`--model none`**, `--log-format json`, explicit arm/model/base-URL metadata, and deterministic `runs/<run-id>/inspect` logs. It neither needs the optional OpenAI provider nor supplies `OPENAI_API_KEY` or a model base URL to Inspect. Source: Inspect AI@0.3.271 [src/inspect_ai/model/_providers/providers.py:361–365](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/src/inspect_ai/model/_providers/providers.py#L361). Inspect's process exit indicates eval completion, not answer correctness: [_cli/eval.py:1681–1682](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/src/inspect_ai/_cli/eval.py#L1681).

`runs/<run-id>/result.json` gives the exact native JSON log path, Inspect exit, mapped verdict and receipt path. `status.json` exists before Inspect starts. The adapter reads the unchanged `results.scores[].metrics.accuracy.value` and completion counts; accuracy below 1 yields exit 1. Accuracy 1 still needs matching completed attempts, cleanup, skill-read observations and independent max/usage evidence before exit 0. `DEERFLOW_EPOCHS` defaults to 1. Source: Inspect AI@0.3.271 [src/inspect_ai/log/_log.py:798–820,848–895](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/src/inspect_ai/log/_log.py#L798).

Freeze the same IDs, prompts, versions, skills, budgets and task contract across the two arms; counterbalance order. Preserve failures. Provider rows, framework counters, compression analytics, official correctness and native lifecycle acceptance are separate evidence. Neither these local tests nor a version check is a new model run, a GAIA score or proof of savings.

The coordinator must re-register changed hashes in `manifests/evidence.json` and rerun `python3 scripts/validate.py`. This worker deliberately leaves that shared file and all Git metadata unchanged.
